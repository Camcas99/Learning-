import { test, expect } from 'bun:test';
import { Window } from 'happy-dom';
import { cleanSettings } from '../src/settings.js';
import { validateSwaps } from '../src/levels.js';
import { FEED } from './instagram-fixture.js';

// Touch on swaps: the event orders real engines send for a tap, a long press and a scroll, replayed with their
// pointerType, next to the mouse and keyboard paths that must not change. Each test loads its own copy of content.js
// (the query string) on a touch page (navigator.maxTouchPoints 5) with a fake worker and a fake speechSynthesis.
const WORDS = [
  { es: 'y', en: 'and', hint: 'ee', status: 'active' },
  { es: 'la casa', en: 'the house / home', hint: 'lah KAH-sah', status: 'active' },
];
const model = (text) => [['and', 'y'], ['house', 'casa']]
  .filter(([o]) => new RegExp(`\\b${o}\\b`).test(text)).map(([o, es]) => ({ o, es, ctx: '' }));
class IO {
  constructor(callback, options) { this.cb = callback; this.options = options; this.elements = new Set(); }
  observe(el) { this.elements.add(el); if (this.options.rootMargin) queueMicrotask(() => { if (this.elements.has(el)) this.cb([{ target: el, isIntersecting: true, intersectionRatio: 1 }]); }); }
  unobserve(el) { this.elements.delete(el); }
  disconnect() { this.elements.clear(); }
}
const wait = (ms = 400) => new Promise((done) => setTimeout(done, ms));

async function touchPage(load) {
  const win = new Window({ url: 'https://www.instagram.com/', settings: { navigator: { maxTouchPoints: 5 } } });
  const names = ['chrome', 'document', 'window', 'location', 'MutationObserver', 'IntersectionObserver', 'setInterval', 'speechSynthesis', 'SpeechSynthesisUtterance'];
  const originalGlobals = Object.fromEntries(names.map((k) => [k, globalThis[k]]));
  const events = [];
  const spoken = [];
  const listeners = [];
  const settings = { ...cleanSettings(), newSitesEnabled: true };
  const config = () => ({ settings: { ...settings }, level: 2, revision: 'r1', hasKey: true, paused: false, origins: ['https://www.instagram.com/*'], stage: 2 });
  Object.assign(globalThis, {
    window: win, document: win.document, location: win.location, MutationObserver: win.MutationObserver, IntersectionObserver: IO,
    setInterval: win.setInterval.bind(win),
    speechSynthesis: { getVoices: () => [{ lang: 'es-MX', name: 'Paulina' }], speak: (u) => spoken.push(u.text), cancel() {} },
    SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
    chrome: { runtime: {
      id: 'sw-test',
      onMessage: { addListener: (fn) => listeners.push(fn) },
      sendMessage: async (msg) => {
        if (msg.type === 'config') return config();
        if (msg.type === 'event') { events.push(`${msg.word}:${msg.event}`); return { ok: true }; }
        const results = {};
        for (const i of msg.items) results[i.key] = validateSwaps(2, model(i.text), WORDS);
        return { results };
      },
    } },
  });
  const user = (e) => Object.defineProperty(e, 'isTrusted', { value: true }); // happy-dom has no real user input
  const at = { clientX: 20, clientY: 20 };
  const P = (type, init = {}) => user(new win.PointerEvent(type, { bubbles: !/enter|leave/.test(type), cancelable: true, composed: true, pointerId: 2, isPrimary: true, pointerType: 'touch', ...at, ...init }));
  const M = (type, init = {}) => user(new win.MouseEvent(type, { bubbles: !/enter|leave/.test(type), cancelable: true, ...at, ...init }));
  const fire = (el, list) => list.map((e) => { el.dispatchEvent(e); return e; });
  win.document.body.innerHTML = FEED;
  await load();
  await wait();
  const caption = win.document.getElementById('caption');
  return {
    win, events, spoken, settings, user, P, M, fire, caption,
    y: caption.querySelector('[data-es="y"]'),
    casa: caption.querySelector('[data-es="casa"]'),
    gloss: () => win.document.querySelector('sw-gloss.sw-gloss-on'),
    // iOS Safari: pointer events with the touch, then the emulated mouse events and click after the finger lifts.
    // Before Safari 18.2 the click was a MouseEvent; since then a PointerEvent.
    tapWebKit: (el, click = M('click')) => fire(el, [P('pointerover'), P('pointerenter'), P('pointerdown'), P('pointerup'), P('pointerout'), P('pointerleave'),
      M('mouseover'), M('mousemove'), M('mousedown'), M('mouseup'), click]).at(-1),
    // Pointer Events 3, section 11.3 (devices without hover): mouseover comes before pointerdown.
    tapSpec: (el) => fire(el, [M('mousemove'), P('pointerover'), P('pointerenter'), M('mouseover'), M('mouseenter'), P('pointerdown'), M('mousedown'),
      P('pointerup'), M('mouseup'), P('pointerout'), P('pointerleave'), M('mouseout'), M('mouseleave'), P('click')]).at(-1),
    broadcast: () => { for (const fn of listeners) fn({ type: 'config', config: config() }); },
    // The extension is reloaded: this copy is cut off (no runtime id, and sendMessage throws), as in content.test.js.
    reload: () => {
      chrome.runtime.id = undefined;
      chrome.runtime.sendMessage = () => { throw new Error('Extension context invalidated.'); };
    },
    async close() { await win.happyDOM.close(); Object.assign(globalThis, originalGlobals); },
  };
}

test('touch: a tap peeks, a second tap or a long press flips, scrolls and mice are unchanged', async () => {
  const t = await touchPage(() => import('../src/content.js?touch'));
  const { win, events, spoken, settings, user, P, M, fire, caption, y, casa, gloss, tapWebKit, tapSpec } = t;
  try {
    expect([y.textContent, casa.textContent]).toEqual(['y', 'casa']);

    // 0. A finger whose click never comes (the page cancels touchstart, or iOS keeps it for a double-tap zoom): its
    // emulated mouseover and focus start no gloss timer, so nothing shows later and no peek is recorded.
    fire(casa, [P('pointerover'), P('pointerdown'), P('pointerup'), M('mouseover'), user(new win.FocusEvent('focusin', { bubbles: true }))]);
    await wait(800);
    expect(gloss()).toBeNull();
    expect(events).toEqual([]);
    await wait(300);

    // 1. Nothing changes while a finger's pointer events and emulated mouseover, mousemove and focus are dispatched
    // (iOS would then treat the tap as a hover and hold back its click), and no gloss timer starts from them.
    const changed = [];
    const mo = new win.MutationObserver((r) => changed.push(...r));
    mo.observe(win.document.documentElement, { attributes: true, childList: true, subtree: true, characterData: true });
    fire(y, [P('pointerover'), P('pointerdown'), P('pointerup'), M('mouseover'), M('mousemove'), user(new win.FocusEvent('focusin', { bubbles: true }))]);
    changed.push(...mo.takeRecords());
    expect(changed).toHaveLength(0);
    mo.disconnect();
    // The click after the lift shows the gloss at once, with a speaker, and records one peek.
    fire(y, [M('mousedown'), M('mouseup'), M('click')]);
    expect(gloss()?.textContent).toBe('y = and · "ee"');
    expect(gloss().querySelector('sw-say svg')).not.toBeNull();
    expect(y.textContent).toBe('y');
    expect(events).toEqual(['y:peek']);
    await wait(800);
    expect(events).toEqual(['y:peek']); // no hover peek or second gloss from the emulated mouseover or focus

    // 2. A second tap on the same word flips it: one flip, gloss gone, and the page's own click handler never sees it.
    let pageClicks = 0;
    caption.addEventListener('click', () => pageClicks++);
    const click2 = tapWebKit(y);
    expect(click2.defaultPrevented).toBe(true);
    expect(y.textContent).toBe('and');
    expect(gloss()).toBeNull();
    expect(events).toEqual(['y:peek', 'y:flip']);
    tapWebKit(y); // a tap on the English word turns it back and records nothing
    expect(y.textContent).toBe('y');
    expect(events).toEqual(['y:peek', 'y:flip']);
    expect(pageClicks).toBe(0);
    await wait(1100);

    // 3. The spec's order (mouseover before pointerdown) and a PointerEvent click: same result. A press elsewhere
    // closes the gloss, and the next tap only shows it again (a peek counts once a day).
    tapSpec(casa);
    expect(gloss()?.textContent).toStartWith('casa = house');
    expect(events).toEqual(['y:peek', 'y:flip', 'la casa:peek']);
    win.document.body.dispatchEvent(P('pointerdown', { clientY: 400 }));
    expect(gloss()).toBeNull();
    tapWebKit(casa, P('click'));
    expect(gloss()).not.toBeNull();
    expect(casa.textContent).toBe('casa');
    expect(events).toEqual(['y:peek', 'y:flip', 'la casa:peek']);

    // 4. The speaker in a tapped gloss speaks without flipping, recording or closing the gloss, even though iOS sends
    // the word a mouseout and a focusout when the next tap lands on the speaker.
    const say = gloss().querySelector('sw-say');
    expect(say).not.toBeNull();
    fire(say, [P('pointerdown'), P('pointerup')]);
    fire(casa, [M('mouseout', { relatedTarget: say }), user(new win.FocusEvent('focusout', { bubbles: true }))]);
    const sayClick = fire(say, [M('mouseover'), M('mousedown'), M('mouseup'), M('click')]).at(-1);
    expect(sayClick.defaultPrevented).toBe(true);
    expect(spoken).toEqual(['casa']);
    expect(gloss()).not.toBeNull();
    expect(casa.textContent).toBe('casa');
    expect(events).toEqual(['y:peek', 'y:flip', 'la casa:peek']);
    win.document.body.dispatchEvent(P('pointerdown', { clientY: 400 }));
    await wait(1100);

    // 5. Long press (iOS: the held finger, then pointerup and maybe a click): one flip at 500 ms, the trailing click
    // eaten. A later, separate tap turns the word back.
    fire(y, [P('pointerover'), P('pointerdown')]);
    await wait(300);
    expect(y.textContent).toBe('y'); // not yet
    await wait(300);
    expect(y.textContent).toBe('and');
    expect(events.at(-1)).toBe('y:flip');
    let n = events.length;
    const trailing = fire(y, [P('pointerup'), P('pointerout'), P('pointerleave'), M('mouseover'), M('mousemove'), M('mousedown'), M('mouseup'), M('click')]).at(-1);
    expect(trailing.defaultPrevented).toBe(true);
    expect(y.textContent).toBe('and'); // the click after the long press did not flip it back
    expect(events).toHaveLength(n);
    tapWebKit(y);
    expect(y.textContent).toBe('y');
    expect(events).toHaveLength(n);
    await wait(1100);
    // A finger that slides off after the long press has flipped the word: its click is still eaten.
    y.dispatchEvent(P('pointerdown'));
    await wait(600);
    expect(y.textContent).toBe('and');
    n = events.length;
    const slid = fire(y, [P('pointermove', { clientY: 60 }), P('pointerup', { clientY: 60 }), M('mouseover'), M('mousedown'), M('mouseup'), M('click')]).at(-1);
    expect(slid.defaultPrevented).toBe(true);
    expect(y.textContent).toBe('and');
    expect(events).toHaveLength(n);
    tapWebKit(y);
    expect(y.textContent).toBe('y');
    await wait(1100);

    // 6. Chrome on Android: stationary pointermoves, then its own contextmenu (a PointerEvent with pointerType touch)
    // before our timer, then pointercancel. One flip, the menu cancelled, no second flip from the timer.
    fire(casa, [P('pointerdown'), P('pointermove', { clientX: 22 }), P('pointermove', { clientX: 21 })]);
    await wait(300);
    const menu = P('contextmenu');
    casa.dispatchEvent(menu);
    expect(menu.defaultPrevented).toBe(true);
    casa.dispatchEvent(P('pointercancel'));
    await wait(400);
    expect(casa.textContent).toBe('house');
    expect(events.filter((e) => e === 'la casa:flip')).toHaveLength(1);
    const sel = user(new win.Event('selectstart', { bubbles: true, cancelable: true }));
    casa.firstChild.dispatchEvent(sel);
    expect(sel.defaultPrevented).toBe(false); // no finger held now, so selection is the page's business
    tapWebKit(casa);
    expect(casa.textContent).toBe('casa');
    await wait(1100);

    // 7. A scroll that starts on a word: the finger moves past the slop, then pointercancel. Nothing flips, nothing
    // is recorded, and the pointerdown itself is never cancelled.
    const before = events.length;
    const downEvt = P('pointerdown');
    y.dispatchEvent(downEvt);
    expect(downEvt.defaultPrevented).toBe(false);
    const selDuring = user(new win.Event('selectstart', { bubbles: true, cancelable: true }));
    y.firstChild.dispatchEvent(selDuring);
    expect(selDuring.defaultPrevented).toBe(true); // while a finger is held on the word, no selection starts
    y.dispatchEvent(P('pointermove', { clientY: 60 }));
    await wait(600); // still held, but moved past the slop: not a long press
    expect(y.textContent).toBe('y');
    y.dispatchEvent(P('pointercancel', { clientY: 60 }));
    await wait(100);
    expect(y.textContent).toBe('y');
    expect(gloss()).toBeNull();
    expect(events).toHaveLength(before);
    // The page scrolling under a held finger also ends the press.
    y.dispatchEvent(P('pointerdown'));
    win.dispatchEvent(new win.Event('scroll'));
    await wait(600);
    expect(y.textContent).toBe('y');
    y.dispatchEvent(P('pointercancel'));
    // A second finger (a pinch) also ends it.
    fire(y, [P('pointerdown'), P('pointerdown', { pointerId: 3, isPrimary: false, clientX: 200 })]);
    await wait(600);
    expect(y.textContent).toBe('y');
    fire(y, [P('pointerup', { pointerId: 3, isPrimary: false }), P('pointerup')]);
    expect(events).toHaveLength(before);
    await wait(1100);

    // 8. Mouse: unchanged. Hover shows the gloss after the beat (no speaker), click flips, right-click keeps the
    // page's menu.
    fire(y, [P('pointerover', { pointerType: 'mouse' }), M('mouseover')]);
    await wait(300);
    expect(gloss()).toBeNull(); // still the beat to recall it first
    await wait(500);
    expect(y.classList.contains('sw-tip')).toBe(true);
    expect(gloss().querySelector('sw-say')).toBeNull();
    fire(y, [P('pointerdown', { pointerType: 'mouse' }), P('pointerup', { pointerType: 'mouse' })]);
    const mouseClick = P('click', { pointerType: 'mouse' });
    y.dispatchEvent(mouseClick);
    expect(mouseClick.defaultPrevented).toBe(true);
    expect(y.textContent).toBe('and');
    expect(events.at(-1)).toBe('y:flip');
    const rightClick = P('contextmenu', { pointerType: 'mouse', button: 2 });
    y.dispatchEvent(rightClick);
    expect(rightClick.defaultPrevented).toBe(false);
    y.dispatchEvent(M('click'));
    expect(y.textContent).toBe('y');
    fire(y, [M('mouseout')]);
    expect(gloss()).toBeNull();

    // 9. A laptop with a touchscreen: a tap, then the real mouse a moment later hovers again at once (its pointermove
    // ends the touch window).
    tapWebKit(casa);
    expect(gloss()).not.toBeNull();
    fire(win.document.body, [P('pointerdown', { clientY: 400 })]);
    fire(y, [P('pointermove', { pointerType: 'mouse' }), M('mouseover')]);
    await wait(800);
    expect(y.classList.contains('sw-tip')).toBe(true);
    // A tap on a word whose gloss a hover opened is a first tap: the tapped gloss, not a flip.
    tapWebKit(y);
    expect(y.textContent).toBe('y');
    expect(gloss().querySelector('sw-say')).not.toBeNull();
    win.document.body.dispatchEvent(P('pointerdown', { clientY: 400 }));
    expect(gloss()).toBeNull();

    // 10. Keyboard and assistive technology (a click with no pointerdown before it, pointerType ''): flip as before.
    y.dispatchEvent(user(new win.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })));
    expect(y.textContent).toBe('and');
    y.dispatchEvent(P('click', { pointerType: '', pointerId: -1 }));
    expect(y.textContent).toBe('y');
    // A page's forged touch, long press and menu do nothing.
    const flips = events.filter((e) => e.endsWith(':flip')).length;
    y.dispatchEvent(new win.PointerEvent('pointerdown', { bubbles: true, pointerType: 'touch', isPrimary: true }));
    await wait(600);
    y.dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
    const forgedMenu = new win.PointerEvent('contextmenu', { bubbles: true, cancelable: true, pointerType: 'touch' });
    y.dispatchEvent(forgedMenu);
    expect(forgedMenu.defaultPrevented).toBe(false);
    expect(y.textContent).toBe('y');
    expect(events.filter((e) => e.endsWith(':flip'))).toHaveLength(flips);
    await wait(1100);

    // 11. "Say words aloud when the meaning shows": a tapped gloss speaks inside the click (iOS needs the gesture).
    settings.speak = true; t.broadcast();
    const heard = spoken.length;
    tapWebKit(casa);
    expect(spoken.slice(heard)).toEqual(['casa']);
    win.document.body.dispatchEvent(P('pointerdown', { clientY: 400 }));
    await wait(1100);

    // 12. The extension is reloaded while a finger is held on a word: the page retires (back to English), the long
    // press never fires, and later gestures neither throw nor record.
    const sent = events.length;
    y.dispatchEvent(P('pointerdown'));
    t.reload();
    win.dispatchEvent(new win.Event('online')); // asks for the config, finds the extension gone, and retires
    await wait(600);
    expect(win.document.querySelectorAll('.sw-word')).toHaveLength(0);
    expect(caption.textContent).toContain(' and ');
    expect(() => {
      fire(caption, [P('pointerup'), M('click')]);
      tapWebKit(caption);
      fire(caption, [P('pointerdown'), P('contextmenu'), P('pointercancel')]);
    }).not.toThrow();
    await wait(600);
    expect(events).toHaveLength(sent);
  } finally {
    await t.close();
  }
}, 40000);

test('touch: a tap after the extension is reloaded retires the page instead of recording a peek', async () => {
  const t = await touchPage(() => import('../src/content.js?touch-reload'));
  try {
    expect(t.y.textContent).toBe('y');
    t.reload();
    expect(() => t.tapWebKit(t.y)).not.toThrow();
    await wait(50);
    expect(t.win.document.querySelectorAll('.sw-word')).toHaveLength(0);
    expect(t.gloss()).toBeNull();
    expect(t.events).toEqual([]);
  } finally {
    await t.close();
  }
}, 10000);
