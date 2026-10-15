import { test, expect } from 'bun:test';
import { Window } from 'happy-dom';
import { cleanSettings } from '../src/settings.js';
import { validateSwaps } from '../src/levels.js';
import { flatten } from '../src/text.js';
import { FEED } from './instagram-fixture.js';

// content.js on the synthetic Instagram feed, with a fake worker (validating like background.js does) and a fake
// speechSynthesis. The query string loads a fresh module instance: runtime.test.js runs content.js on its own page.
test('content: Instagram passages, Alt+click speech, spoken gloss, gender cues and their setting', async () => {
  const win = new Window({ url: 'https://www.instagram.com/' });
  const names = ['chrome', 'document', 'window', 'location', 'MutationObserver', 'IntersectionObserver', 'setInterval', 'speechSynthesis', 'SpeechSynthesisUtterance'];
  const originalGlobals = Object.fromEntries(names.map((k) => [k, globalThis[k]]));
  const listeners = [];
  const sent = []; // passages handed to the worker, i.e. the only page text that could reach Gemini
  const events = [];
  const spoken = [];
  const settings = { ...cleanSettings(), newSitesEnabled: true };
  const config = () => ({ settings: { ...settings }, level: 2, revision: 'r1', hasKey: true, paused: false, origins: ['https://www.instagram.com/*'], stage: 2 });
  const WORDS = [
    { es: 'y', en: 'and', hint: 'ee', status: 'active' },
    { es: 'la casa', en: 'the house / home', hint: 'lah KAH-sah', status: 'active' },
    { es: 'el día', en: 'the day', hint: 'el DEE-ah', status: 'active' },
    { es: 'largo', en: 'long', hint: 'LAHR-goh', status: 'shaky', note: "not 'large' (that's grande)" },
  ];
  const model = (text) => [['and', 'y'], ['house', 'casa'], ['day', 'día'], ['long', 'largo']]
    .filter(([o]) => new RegExp(`\\b${o}\\b`).test(text)).map(([o, es]) => ({ o, es, ctx: '' }));
  class IO {
    constructor(callback, options) { this.cb = callback; this.options = options; this.elements = new Set(); }
    observe(el) { this.elements.add(el); if (this.options.rootMargin) queueMicrotask(() => { if (this.elements.has(el)) this.cb([{ target: el, isIntersecting: true, intersectionRatio: 1 }]); }); }
    unobserve(el) { this.elements.delete(el); }
    disconnect() { this.elements.clear(); }
  }
  Object.assign(globalThis, {
    window: win, document: win.document, location: win.location, MutationObserver: win.MutationObserver, IntersectionObserver: IO,
    setInterval: win.setInterval.bind(win),
    speechSynthesis: { getVoices: () => [{ lang: 'es-ES', name: 'Mónica' }, { lang: 'es-MX', name: 'Paulina' }], speak: (u) => spoken.push(u), cancel() {} },
    SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
    chrome: { runtime: {
      onMessage: { addListener: (fn) => listeners.push(fn) },
      sendMessage: async (msg) => {
        if (msg.type === 'config') return config();
        if (msg.type === 'event') { events.push(`${msg.word}:${msg.event}`); return { ok: true }; }
        const results = {};
        for (const i of msg.items) { sent.push(i.text); results[i.key] = validateSwaps(2, model(i.text), WORDS); }
        return { results };
      },
    } },
  });
  const wait = (ms = 400) => new Promise((done) => setTimeout(done, ms));
  const user = (e) => Object.defineProperty(e, 'isTrusted', { value: true }); // happy-dom has no real user input
  const broadcast = () => { for (const fn of listeners) fn({ type: 'config', config: config() }); };
  const $ = (id) => win.document.getElementById(id);
  try {
    win.document.body.innerHTML = FEED;
    const passages = ['caption', 'comment-long'].map((id) => flatten($(id)).text);
    const links = [...win.document.querySelectorAll('a')].map((a) => a.textContent);
    await import('../src/content.js?instagram');
    await wait();

    // Only the caption and the long comment leave the page; the nested caption span is painted once, as part of it.
    expect(sent).toEqual(passages);
    expect(sent[0]).toStartWith('We finally reached the coast and the water');
    const caption = $('caption');
    expect([...caption.querySelectorAll('.sw-word')].map((s) => s.textContent)).toEqual(['y', 'casa']);
    expect($('nested').querySelectorAll('.sw-word')).toHaveLength(1);
    expect(win.document.querySelectorAll('.sw-word .sw-word')).toHaveLength(0);
    expect($('comment-long').querySelector('.sw-word').textContent).toBe('y');
    expect([...win.document.querySelectorAll('a')].map((a) => a.textContent)).toEqual(links);
    const casa = caption.querySelector('[data-es="casa"]');
    expect(casa.dataset.swGender).toBe('f');
    expect(casa.dataset.tip).toBe('house / home · fem. · "KAH-sah"');
    expect(casa.classList.contains('sw-new')).toBe(true); // a first appearance animates
    // Keyboard focus shows the gloss after the pause; it isn't spoken unless "Say words aloud" is on.
    casa.dispatchEvent(user(new win.FocusEvent('focusin', { bubbles: true })));
    await wait(800);
    expect(casa.classList.contains('sw-tip')).toBe(true);
    expect(spoken).toHaveLength(0);
    casa.dispatchEvent(user(new win.FocusEvent('focusout', { bubbles: true })));

    // Alt+click and Alt+Enter speak the Spanish word in a Latin American voice: no flip, no event.
    const y = caption.querySelector('[data-es="y"]');
    y.dispatchEvent(user(new win.MouseEvent('click', { bubbles: true, altKey: true })));
    expect(spoken.map((u) => [u.text, u.lang, u.voice.name, u.rate])).toEqual([['y', 'es-MX', 'Paulina', 0.9]]);
    y.dispatchEvent(user(new win.KeyboardEvent('keydown', { key: 'Enter', altKey: true, bubbles: true })));
    expect(spoken).toHaveLength(2);
    expect(y.textContent).toBe('y');
    y.dispatchEvent(new win.MouseEvent('click', { bubbles: true, altKey: true })); // a page's synthetic click
    expect(spoken).toHaveLength(2);
    // Alt+click while the gloss is still waiting cancels it, so hearing a word never counts as a peek.
    y.dispatchEvent(user(new win.MouseEvent('mouseover', { bubbles: true })));
    await wait(100);
    y.dispatchEvent(user(new win.MouseEvent('click', { bubbles: true, altKey: true })));
    await wait(800);
    expect(y.classList.contains('sw-tip')).toBe(false);
    expect(spoken).toHaveLength(3);
    expect(events).toEqual([]);
    y.dispatchEvent(user(new win.MouseEvent('mouseout', { bubbles: true })));
    // A plain click still flips and records.
    y.dispatchEvent(user(new win.MouseEvent('click', { bubbles: true })));
    expect(y.textContent).toBe('and');
    expect(events).toEqual(['y:flip']);
    y.dispatchEvent(user(new win.MouseEvent('click', { bubbles: true })));
    expect(y.textContent).toBe('y');

    // "Say words aloud" keeps the revision: nothing is repainted or re-sent, and the gloss now speaks.
    settings.speak = true; broadcast();
    expect(caption.querySelector('[data-es="y"]')).toBe(y);
    y.dispatchEvent(user(new win.MouseEvent('mouseover', { bubbles: true })));
    await wait(800);
    expect(y.classList.contains('sw-tip')).toBe(true);
    expect(spoken.map((u) => u.text)).toEqual(['y', 'y', 'y', 'y']);
    expect(events).toEqual(['y:flip', 'y:peek']);
    y.dispatchEvent(user(new win.MouseEvent('mouseout', { bubbles: true })));

    // A comment loaded later: masculine noun, and a usage note after the hint.
    const li = win.document.createElement('li');
    li.innerHTML = '<a href="/lucia.r/" role="link"><span dir="auto">lucia.r</span></a> <span dir="auto" id="comment-new">It was a long day at the beach but so worth it</span>';
    win.document.querySelector('ul').append(li);
    await wait();
    const dia = $('comment-new').querySelector('[data-es="día"]');
    expect(dia.dataset.swGender).toBe('m');
    expect(dia.dataset.tip).toBe('day · masc. · "DEE-ah"');
    const largo = $('comment-new').querySelector('[data-es="largo"]');
    expect(largo.hasAttribute('data-sw-gender')).toBe(false);
    expect(largo.dataset.tip).toBe(`long · "LAHR-goh" · not 'large' (that's grande)`);
    expect(sent).toHaveLength(3);

    // An edit inside the nested span re-reads the whole caption.
    $('nested').append(' again');
    await wait();
    expect(sent).toHaveLength(4);
    expect(sent[3]).toContain('until the light was gone again #travel');
    expect([...caption.querySelectorAll('.sw-word')].map((s) => s.textContent)).toEqual(['y', 'casa']);

    // Gender colors off: switched in place without the attribute or label, no new requests; notes stay, and a word
    // flipped to English stays flipped.
    const flipped = caption.querySelector('[data-es="casa"]');
    flipped.dispatchEvent(user(new win.MouseEvent('click', { bubbles: true })));
    expect(flipped.textContent).toBe('house');
    settings.genderColors = false; broadcast();
    await wait(50);
    const spans = [...win.document.querySelectorAll('.sw-word')];
    expect(spans.map((s) => s.textContent)).toEqual(['y', 'house', 'y', 'largo', 'día']);
    expect(spans[1]).toBe(flipped);
    for (const s of spans) {
      expect(s.hasAttribute('data-sw-gender')).toBe(false);
      expect(s.dataset.tip).not.toMatch(/masc|fem/);
    }
    expect($('comment-new').querySelector('[data-es="largo"]').dataset.tip).toContain("not 'large'");
    expect($('comment-new').querySelector('[data-es="día"]').getAttribute('aria-label')).toBe('día: day. Show English');
    settings.genderColors = true; broadcast();
    await wait(50);
    expect(flipped.dataset.swGender).toBe('f');
    expect(flipped.dataset.tip).toBe('house / home · fem. · "KAH-sah"');
    expect(flipped.textContent).toBe('house');
    expect($('comment-new').querySelector('[data-es="día"]').getAttribute('aria-label')).toBe('día: day, masculine. Show English');
    expect(sent).toHaveLength(4);

    // A restart (as on single-page navigation) paints the same passages again without replaying the reveal.
    for (const fn of listeners) fn({ type: 'retry', config: config() });
    await wait();
    expect([...win.document.querySelectorAll('.sw-word')].map((s) => s.textContent)).toEqual(['y', 'casa', 'y', 'largo', 'día']);
    expect(win.document.querySelectorAll('.sw-word.sw-new')).toHaveLength(0);

    // Nothing in the DOM names a learning word beyond the visible Spanish one.
    const html = win.document.body.innerHTML;
    expect(html).not.toMatch(/data-sw-(word|key)/);
    for (const w of ['la casa', 'el día']) expect(html).not.toContain(w);
  } finally {
    await win.happyDOM.close();
    Object.assign(globalThis, originalGlobals);
  }
}, 20000);
