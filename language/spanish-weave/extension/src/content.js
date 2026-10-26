// Content script: watch readable text (tweets on X, captions, comments and bios on Instagram, prose elsewhere), ask
// the background for swaps, paint them, handle the delayed gloss, click/Enter flip, Alt+click/Alt+Enter speech, taps
// and long presses on touchscreens, and seen/peek/flip events. Every async reply belongs to one config generation.
import { flatten, applySwaps, revert, toggle, isSwap, swapWord, showGender, SWAP_CLASS } from './text.js';
import { hashKey } from './hash.js';
import { siteEnabled, hasSiteAccess } from './settings.js';
import { localDay } from './hostsource.js';
import { selector, readable, textRoot } from './page.js';
import { speak } from './speech.js';
import { pickBatch } from './pick.js';

let config = null;
let observer = null;
let near = null;
let visible = null;
let timer = null;
let generation = 0;
const memo = new Map();
const keys = new WeakMap(); // element -> revision:text hash, kept off the DOM so pages can't read it
const pending = new Map();
const inflight = new Set();
const tracked = new Set();
const visibleWords = new Set();
const seen = new Set();
const failures = new Map(); // text key -> failed model attempts; retried with backoff
// Text keys already painted once. A repaint (single-page navigation, a restart) doesn't replay the reveal animation.
// Kept across restarts; cleared when it gets large.
const painted = new Set();
const MAX_RETRIES = 3;
// Batches this page has out at once. The rest wait here rather than in the worker's queue, so each new batch is made
// of the passages on screen or nearest to it at that moment (pick.js), not of ones that scrolled away meanwhile.
const MAX_BATCHES_OUT = 2;
let batchesOut = 0;
const TIP_DELAY_MS = 700; // a beat to recall the word before the meaning appears
// Text that keeps changing (a live ticker, a reply streaming in, a page fighting the swaps) would cost a model call per
// version. After CHURN_MAX changes within CHURN_MS, an element waits until its text has held still for SETTLE_MS.
const CHURN_MAX = 3;
const CHURN_MS = 30000;
const SETTLE_MS = 5000;
const changes = new WeakMap(); // element -> times its text changed lately
const settling = new WeakMap(); // element -> timer that looks at it again once it holds still
const texts = new WeakMap(); // element -> the text last looked at, to tell a real change from a re-render
let tipTimer = null;
// Touch. A tap shows the gloss at once (a peek); a second tap on the same word, or a long press, flips it (a flip). A
// finger also sends emulated mouseover, focus and click events, which must never take the mouse path: on a phone
// that made every tap a flip. Each gesture is judged by the pointerType of the trusted pointerdown that started it.
const LONG_PRESS_MS = 500; // above the 350 ms WebKit watches timers for during a tap, so iOS never reads it as hover
const TOUCH_GRACE_MS = 1000; // a finger's emulated mouse events, focus and click arrive after its pointerup
const SLOP_PX = 10; // Chrome on Android sends pointermove while the finger holds still
let lastType = ''; // pointerType of the latest trusted pointer event of any kind
let lastAt = -Infinity;
let down = { type: '', span: null, at: -Infinity }; // the latest trusted pointerdown; pointerup refreshes `at`
const lifted = new WeakMap(); // word -> when a finger last lifted off it, which a later pointerdown elsewhere keeps
let press = null; // { span, id, x, y, timer, fired }: a finger held on a word
let swallow = null; // { span, until }: a long press flipped this word; its trailing click and menu do nothing
let tipBy = ''; // how the open gloss was opened: 'hover', 'focus' or 'tap'
let sayBox = null; // the speaker inside a tapped gloss
const fingery = (type) => type === 'touch' || type === 'pen';
const clock = () => performance.now();
// A finger is down, or lifted less than TOUCH_GRACE_MS ago: mouseover, mouseout and focus events are its echoes.
const touching = () => fingery(lastType) && (press !== null || clock() - lastAt < TOUCH_GRACE_MS);
// When the extension is reloaded or updated, this copy of the script stays on pages that were already open, cut off
// from the extension: chrome.runtime.id is gone and sendMessage throws "Extension context invalidated". It then retires:
// the page goes back to English and nothing more is sent or logged. The new copy runs on pages opened from then on.
let orphaned = false;
let navTimer = null;
const alive = () => { try { return !!chrome.runtime?.id; } catch { return false; } };
function retire() {
  if (orphaned) return;
  orphaned = true;
  stop();
  clearInterval(navTimer);
}
const send = (msg) => {
  if (orphaned || !alive()) { retire(); return Promise.reject(new Error('Spanish Weave was reloaded; reload the page')); }
  try { return Promise.resolve(chrome.runtime.sendMessage(msg)); }
  catch (error) { retire(); return Promise.reject(error); }
};
const on = () => !orphaned && config?.hasKey && !config.paused && siteEnabled(config.settings, location.href) && hasSiteAccess(location.href, config.origins);
const targets = () => selector(location.href);
// Only real user input on spans this extension made; pages can't forge flips, peeks or seen events.
const swapFor = (e) => {
  const span = e.isTrusted && e.target?.closest?.(`span.${SWAP_CLASS}`);
  return span && isSwap(span) ? span : null;
};
const say = (span) => speak(span.getAttribute('data-es')); // only the visible Spanish word, never the list

function record(span, event) {
  const word = swapWord(span);
  if (!word || !on()) return;
  const id = localDay() + ':' + event + ':' + word; // the local day, as the worker and the plugin count
  const daily = event === 'seen' || event === 'peek';
  if (daily && seen.has(id)) return;
  if (daily) seen.add(id);
  void send({ type: 'event', word, event }).then((r) => {
    if (!r?.ok && daily) seen.delete(id);
  }).catch(() => { if (daily) seen.delete(id); });
}
// The gloss is one box for the whole page, fixed to the viewport and placed over the word, so a container with
// overflow: hidden (quoted posts on X, comment threads) can't clip or hide it the way a box inside the word could. It
// sits outside every text block the extension reads, never takes the pointer, and is hidden from screen readers (the
// word's aria-label carries the gloss). From French Weave by Jackie Oliver (MIT).
let tipBox = null;
let tipSpan = null; // the word the box belongs to: when the page removes or reverts it, the box goes too
const TIP_GAP = 4;
const canSpeak = () => typeof globalThis.speechSynthesis?.speak === 'function';
// The speaker for a gloss opened by a tap, since a finger has no Alt+click. The icon is inline SVG built here, so a
// page's content security policy can't block it the way it could an image file.
function speaker() {
  const NS = 'http://www.w3.org/2000/svg';
  const box = document.createElement('sw-say');
  box.className = 'sw-say';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', '18');
  svg.setAttribute('height', '18');
  const cone = document.createElementNS(NS, 'path');
  cone.setAttribute('d', 'M3 9h4l5-4v14l-5-4H3z');
  cone.setAttribute('fill', 'currentColor');
  const waves = document.createElementNS(NS, 'path');
  waves.setAttribute('d', 'M14 8.5a4 4 0 0 1 0 7M16 5.5a7.5 7.5 0 0 1 0 13');
  waves.setAttribute('fill', 'none');
  waves.setAttribute('stroke', 'currentColor');
  waves.setAttribute('stroke-width', '2');
  waves.setAttribute('stroke-linecap', 'round');
  svg.append(cone, waves);
  box.append(svg);
  return box;
}
function placeTip(span, withSpeaker = false) {
  tipSpan = span;
  if (!tipBox?.isConnected) {
    tipBox = document.createElement('sw-gloss');
    tipBox.className = 'sw-gloss';
    tipBox.setAttribute('aria-hidden', 'true');
    document.documentElement.append(tipBox);
  }
  // Setting the text also drops the speaker a tapped gloss had; only a tap puts it back.
  tipBox.textContent = `${span.getAttribute('data-es') || ''} = ${span.getAttribute('data-tip') || ''}`;
  tipBox.classList.toggle('sw-gloss-touch', withSpeaker);
  if (withSpeaker && canSpeak()) {
    // The one part of the box that takes the pointer. It sits inside the box, so it never covers the word.
    if (!sayBox) sayBox = speaker();
    tipBox.append(sayBox);
  }
  tipBox.classList.add('sw-gloss-on');
  const word = span.getBoundingClientRect();
  const box = tipBox.getBoundingClientRect();
  const width = document.documentElement.clientWidth || window.innerWidth;
  const top = word.top - box.height - TIP_GAP >= 0 ? word.top - box.height - TIP_GAP : word.bottom + TIP_GAP;
  tipBox.style.left = `${Math.max(TIP_GAP, Math.min(word.left, width - box.width - TIP_GAP))}px`;
  tipBox.style.top = `${top}px`;
}
// The gloss appears only after a short dwell; reaching it counts as a peek (the reader needed the meaning).
function hideTip() {
  clearTimeout(tipTimer); tipTimer = null;
  for (const el of document.querySelectorAll(`.${SWAP_CLASS}.sw-tip`)) el.classList.remove('sw-tip');
  tipBox?.classList.remove('sw-gloss-on');
  tipSpan = null;
  tipBy = '';
}
function armTip(e) {
  if (touching()) return; // a finger's emulated mouseover or focus: the tap decides, and nothing may change here (iOS)
  const span = swapFor(e);
  if (!span || !on() || span.classList.contains('sw-tip')) return;
  hideTip();
  tipTimer = setTimeout(() => {
    tipTimer = null;
    if (!span.isConnected || span.classList.contains('sw-en')) return;
    span.classList.add('sw-tip');
    placeTip(span);
    tipBy = e.type === 'mouseover' ? 'hover' : 'focus';
    if (config.settings.speak) say(span);
    if (e.type === 'mouseover') record(span, 'peek'); // a page can focus a span from script, so focus never counts
  }, TIP_DELAY_MS);
}
function disarmTip(e) {
  if (touching()) return; // iOS sends the word a mouseout and focusout when the next tap lands elsewhere, the speaker too
  const span = swapFor(e);
  if (span && !span.contains(e.relatedTarget)) hideTip();
}
// On screen isn't enough: a page can hide swaps with CSS (opacity 0, visibility hidden) while they stay in place.
const showing = (span) => typeof span.checkVisibility !== 'function' ||
  span.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true });
function seenVisible() {
  if (document.visibilityState === 'hidden') return;
  for (const span of visibleWords) if (span.isConnected && showing(span)) record(span, 'seen');
}
function paint(el, key) {
  if (!on() || keys.get(el) !== key || !readable(el, location.href)) return;
  const swaps = memo.get(key);
  if (!swaps?.length) return;
  applySwaps(el, swaps, { gender: config.settings.genderColors });
  const first = !painted.has(key);
  if (painted.size > 5000) painted.clear();
  painted.add(key);
  for (const span of el.querySelectorAll(`.${SWAP_CLASS}`)) {
    if (!isSwap(span)) continue;
    if (first) span.classList.add('sw-new'); // content.css animates only these
    visible.observe(span);
  }
  observer?.takeRecords();
}
function consider(el) {
  if (!on() || !el.isConnected) return;
  if (el.querySelector(`.${SWAP_CLASS}`)) revert(el);
  observer?.takeRecords();
  if (!readable(el, location.href)) { keys.delete(el); return; }
  const text = flatten(el).text;
  const key = `${config.revision}:${hashKey(text)}`;
  keys.set(el, key);
  texts.set(el, text);
  if (memo.has(key)) { paint(el, key); return; }
  let p = pending.get(key);
  if (!p) { p = { text, els: new Set() }; pending.set(key, p); }
  p.els.add(el);
  if (!timer) timer = setTimeout(flush, 250);
}
async function flush() {
  timer = null;
  if (!on() || batchesOut >= MAX_BATCHES_OUT) return; // the reply to one out schedules the next
  const gen = generation;
  // A passage dropped because its element left the page forgets its key, so the element is read again if it comes back.
  const items = pickBatch(pending, inflight, (el) => keys.get(el), window.innerHeight || document.documentElement.clientHeight || 0,
    undefined, (el) => keys.delete(el));
  if (!items.length) return;
  for (const i of items) inflight.add(i.key);
  batchesOut++;
  let result;
  try { result = await send({ type: 'swaps', revision: config.revision, items }); }
  catch { result = { error: 'Extension unavailable' }; }
  if (gen !== generation) return; // stop() reset the count
  batchesOut--;
  if (!on()) return;
  for (const i of items) {
    inflight.delete(i.key);
    const p = pending.get(i.key);
    pending.delete(i.key);
    const swaps = result?.results?.[i.key];
    if (!Array.isArray(swaps)) {
      // A failed model call (usually the free tier's rate limit) is retried instead of leaving the passage English.
      const tries = (failures.get(i.key) || 0) + 1;
      failures.set(i.key, tries);
      if (p && tries <= MAX_RETRIES) {
        const wait = Math.max(result?.retryAfterMs || 0, 5000 * tries);
        setTimeout(() => { if (gen === generation) for (const el of p.els) if (keys.get(el) === i.key) { keys.delete(el); consider(el); } }, wait);
      }
      continue;
    }
    failures.delete(i.key);
    memo.set(i.key, swaps);
    if (p) for (const el of p.els) paint(el, i.key);
  }
  if (result?.stale) {
    try { update(await send({ type: 'config' })); } catch { /* the extension was reloaded: retired */ }
    return;
  }
  if ([...pending.keys()].some((k) => !inflight.has(k))) timer = setTimeout(flush, 50);
}
// An element whose text changed no longer waits for its old text's swaps; that text goes unasked if nothing else has it.
function unqueue(el, key) {
  const p = key && pending.get(key);
  if (!p) return;
  p.els.delete(el);
  if (!p.els.size && !inflight.has(key)) pending.delete(key);
}
function restless(el) {
  const now = Date.now();
  const recent = (changes.get(el) || []).filter((t) => now - t < CHURN_MS);
  recent.push(now);
  changes.set(el, recent);
  return recent.length > CHURN_MAX;
}
function track(root) {
  if (root.nodeType !== 1) return;
  const elements = root.matches(targets()) ? [root, ...root.querySelectorAll(targets())] : root.querySelectorAll(targets());
  for (const el of elements) {
    if (tracked.has(el) || !readable(el, location.href)) continue;
    tracked.add(el);
    near.observe(el);
  }
}
function mutations(records) {
  if (tipSpan && !tipSpan.isConnected) hideTip(); // no mouseout comes from a removed word
  const changed = new Set();
  for (const r of records) {
    for (const n of r.addedNodes || []) if (n.nodeType === 1) track(n);
    const base = r.target.nodeType === 1 ? r.target : r.target.parentElement;
    const el = textRoot(base, location.href); // on Instagram, an edit in a nested span belongs to the outer caption
    if (el && tracked.has(el)) changed.add(el);
    else if (el) track(el);
  }
  for (const el of changed) {
    if (el.querySelector(`.${SWAP_CLASS}`)) revert(el);
    unqueue(el, keys.get(el));
    keys.delete(el);
    if (!readable(el, location.href)) continue;
    near.unobserve(el);
    clearTimeout(settling.get(el));
    const moved = texts.has(el) && flatten(el).text !== texts.get(el); // a re-render with the same text isn't a change
    if (moved && restless(el)) {
      settling.set(el, setTimeout(() => {
        settling.delete(el);
        if (observer && el.isConnected && tracked.has(el)) near.observe(el);
      }, SETTLE_MS));
    } else near.observe(el);
  }
  observer?.takeRecords();
  for (const el of tracked) if (!el.isConnected) { tracked.delete(el); near.unobserve(el); }
  for (const span of visibleWords) if (!span.isConnected) { visibleWords.delete(span); visible.unobserve(span); }
  if (tipSpan && !tipSpan.isConnected) hideTip(); // the swap was reverted while its gloss showed
}
function start() {
  if (observer || !on()) return;
  visible = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting && e.intersectionRatio >= 0.5) visibleWords.add(e.target);
      else visibleWords.delete(e.target);
    }
    seenVisible();
  }, { threshold: [0, 0.5] });
  near = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting && !keys.has(e.target)) consider(e.target);
  }, { rootMargin: '600px' });
  observer = new MutationObserver(mutations);
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  track(document.documentElement);
}
function stop() {
  generation++;
  observer?.disconnect(); observer = null;
  near?.disconnect(); visible?.disconnect();
  clearTimeout(timer); timer = null;
  pending.clear(); inflight.clear(); memo.clear(); failures.clear(); hideTip(); cancelPress(); swallow = null;
  batchesOut = 0;
  for (const el of tracked) { revert(el); keys.delete(el); }
  tracked.clear(); visibleWords.clear();
}
function update(next, retry = false) {
  if (!next?.settings || !next.revision) return;
  if (!retry && next.revision === config?.revision) {
    // Same swaps: take the new config as it is and switch gender cues in place. On/off, site choices and a pause
    // stop or start the page; start() does nothing when already running, and restarts repaint from the cache.
    const regender = next.settings.genderColors !== config.settings.genderColors;
    config = next;
    if (regender) showGender(document.documentElement, config.settings.genderColors);
    if (on()) start(); else stop();
    return;
  }
  stop(); config = next; start();
}
function reveal(e) {
  const span = swapFor(e);
  if (!span || !on()) return;
  if (e.type === 'keydown' && !['Enter', ' '].includes(e.key)) return;
  e.preventDefault(); e.stopPropagation();
  if (e.altKey) {
    // Alt/Option: hear the word instead of flipping it. Records nothing, and a gloss still waiting won't become a peek.
    clearTimeout(tipTimer); tipTimer = null;
    say(span);
    return;
  }
  flip(span);
}
function flip(span) {
  hideTip();
  if (toggle(span)) record(span, 'flip');
  observer?.takeRecords();
}
// --- Touch -------------------------------------------------------------------------------------------------------
// Pointer listeners only watch (they are passive and never cancel), so scrolling, zooming and the page's own handlers
// go on as before. Nothing visible changes on pointerdown or mouseover except closing an open gloss, and no timer
// shorter than LONG_PRESS_MS starts there: iOS turns a tap that changes the page into a hover and drops its click.
// There are no touch* listeners either; with them, iOS VoiceOver would activate a word with simulated touches.
function cancelPress() {
  if (!press) return;
  clearTimeout(press.timer);
  // A press that already flipped its word still has a click to come when the finger lifts: that one does nothing.
  if (press.fired) swallow = { span: press.span, until: clock() + TOUCH_GRACE_MS };
  press = null;
}
function notePointer(e) {
  if (!e.isTrusted || orphaned) return;
  // A pen hovering above the screen (no button down) points like a mouse, so its hover shows the gloss as before.
  const hovering = e.pointerType === 'pen' && !e.buttons && (e.type === 'pointermove' || e.type === 'pointerover');
  lastType = hovering ? 'mouse' : e.pointerType || '';
  lastAt = clock();
}
function onPointerDown(e) {
  if (!e.isTrusted || orphaned) return;
  notePointer(e);
  const span = swapFor(e);
  down = { type: e.pointerType || '', span, at: clock() };
  // A press anywhere but the open word or its speaker closes the gloss (a finger has no mouseout).
  if (tipSpan && !tipSpan.contains(e.target) && !sayBox?.contains(e.target)) hideTip();
  cancelPress();
  swallow = null;
  // A mouse, a second finger, a pen's barrel or eraser button, or not a word: no long press.
  if (!fingery(e.pointerType) || !e.isPrimary || e.button !== 0 || !span || !on()) return;
  press = { span, id: e.pointerId, x: e.clientX, y: e.clientY, timer: null, fired: false };
  press.timer = setTimeout(() => longPress(span), LONG_PRESS_MS);
}
function onPointerMove(e) {
  if (!e.isTrusted || orphaned) return;
  notePointer(e); // a real mouse moving ends the touch window at once, so a laptop with a touchscreen hovers again
  const moved = press && e.pointerId === press.id && Math.hypot(e.clientX - press.x, e.clientY - press.y) > SLOP_PX;
  if (moved) cancelPress(); // a scroll or a drag, not a long press
}
function onPointerEnd(e) { // pointerup, and pointercancel when the browser takes the finger for a scroll or a zoom
  if (!e.isTrusted || orphaned) return;
  notePointer(e);
  if (e.type === 'pointerup' && down.span) { // the click comes after the lift
    down.at = clock();
    if (fingery(down.type)) lifted.set(down.span, down.at);
  }
  if (press && e.pointerId === press.id) cancelPress();
}
function longPress(span) {
  if (!press || press.span !== span || press.fired || !span.isConnected || !on()) return;
  press.fired = true; // kept until the finger lifts or slides away; cancelPress() then eats the click that may follow
  flip(span);
}
// A click from a finger: its own pointerType says so where the click is a PointerEvent (Chrome, Safari 18.2 and later),
// which holds even when the page is slow or swallowed the pointerdown; otherwise a finger pressed or lifted off this
// word just before (the latest pointerdown, or its lift kept per word, since the next finger can land before an iOS
// tap's late click). A click with none of these (a mouse, the keyboard, VoiceOver, TalkBack, switch control, whose
// pointerType is '' or 'mouse') keeps its old meaning.
const tapped = (span, e) => (e.isTrusted && fingery(e.pointerType)) || (fingery(down.type) && down.span === span &&
  clock() - down.at < TOUCH_GRACE_MS) || clock() - (lifted.get(span) ?? -Infinity) < TOUCH_GRACE_MS;
function onClick(e) {
  if (e.isTrusted && sayBox?.contains(e.target)) { // the speaker in a tapped gloss: sound only, nothing recorded
    e.preventDefault(); e.stopPropagation();
    if (on() && tipSpan?.isConnected) say(tipSpan); // inside the click: iOS speaks only during a user gesture
    return;
  }
  const span = swapFor(e);
  if (!span || !on()) return;
  if (swallow?.span === span && clock() < swallow.until) { // the click that trails a long press
    swallow = null;
    e.preventDefault(); e.stopPropagation();
    return;
  }
  if (!tapped(span, e)) { reveal(e); return; } // not a finger: as it always was
  e.preventDefault(); e.stopPropagation(); // the page's own handler (a post that opens on click) stays out of it
  if (e.altKey) { clearTimeout(tipTimer); tipTimer = null; say(span); return; } // Option+tap with an iPad keyboard
  if (span.classList.contains('sw-en') || (tipSpan === span && tipBy === 'tap')) { flip(span); return; }
  hideTip(); // also drops a gloss the tap's emulated focus may have queued
  span.classList.add('sw-tip');
  placeTip(span, true);
  tipBy = 'tap';
  if (config.settings.speak) say(span);
  record(span, 'peek'); // once a day per word, like a hover
}
function onContextMenu(e) {
  const span = swapFor(e);
  if (!span || !on()) return;
  // A pen counts only while it holds the word: a quick barrel-button press is its right-click.
  const finger = e.pointerType === 'touch' || press?.span === span || (swallow?.span === span && clock() < swallow.until);
  if (!finger) return; // a right-click or the menu key keeps the page's menu
  e.preventDefault(); e.stopPropagation();
  if (press?.span === span && !press.fired) { clearTimeout(press.timer); longPress(span); } // Android's own long press
}
function onSelectStart(e) {
  if (e.isTrusted && press?.span.contains(e.target)) e.preventDefault(); // no text selection from a held word
}
chrome.runtime.onMessage.addListener((msg) => {
  if (['config', 'retry'].includes(msg?.type)) update(msg.config, msg.type === 'retry');
});
const watch = { capture: true, passive: true };
document.addEventListener('pointerover', notePointer, watch);
document.addEventListener('pointerdown', onPointerDown, watch);
document.addEventListener('pointermove', onPointerMove, watch);
document.addEventListener('pointerup', onPointerEnd, watch);
document.addEventListener('pointercancel', onPointerEnd, watch);
document.addEventListener('contextmenu', onContextMenu, true);
document.addEventListener('selectstart', onSelectStart, true);
document.addEventListener('click', onClick, true);
document.addEventListener('keydown', reveal, true);
document.addEventListener('mouseover', armTip, true);
document.addEventListener('focusin', armTip, true);
document.addEventListener('mouseout', disarmTip, true);
document.addEventListener('focusout', disarmTip, true);
window.addEventListener('scroll', () => { hideTip(); cancelPress(); }, { passive: true, capture: true });
document.addEventListener('visibilitychange', seenVisible);
window.addEventListener('online', () => { void send({ type: 'config' }).then((c) => update(c, true)).catch(() => {}); });
// SPA navigation can reuse DOM nodes without changing their text.
let page = location.href;
navTimer = setInterval(() => {
  if (page !== location.href) { page = location.href; if (config && !orphaned) update(config, true); }
}, 1000);
void send({ type: 'config' }).then(update).catch(() => {});
