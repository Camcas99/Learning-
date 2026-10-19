import { test, expect } from 'bun:test';
import { readFileSync } from 'node:fs';
import { Window } from 'happy-dom';
import { hashKey } from '../src/hash.js';

// A fresh worker and content module (the query strings; runtime.test.js has its own) with a compact fake Chrome:
// the storage access level, setup vs popup site choice, syncing stale word state, site toggles that keep cached
// swaps, and which sightings count as seen.
test('sync: storage access fallback, latest site choice, stale state, site toggles, hidden and local-day sightings', async () => {
  const win = new Window({ url: 'https://example.com/article' });
  const RealDate = Date;
  const originalGlobals = Object.fromEntries(['chrome', 'fetch', 'document', 'window', 'location', 'MutationObserver', 'IntersectionObserver', 'setInterval'].map((k) => [k, globalThis[k]]));
  const local = { apiKey: 'synthetic-gemini', settings: { levelOverride: 1 } };
  const messageListeners = [], contentListeners = [];
  const pageEvents = []; // seen/peek/flip messages the content script sent to the worker
  let stateRequests = 0;
  let modelCalls = 0;
  let hostState = { version: 's.1', stage: 1, paused: false, prefs: {}, words: [
    { es: 'y', en: 'and', hint: 'ee', status: 'active' },
    { es: 'muy', en: 'very', hint: 'mwee', status: 'shaky' },
  ] };
  const manifest = JSON.parse(readFileSync(new URL('../manifest.json', import.meta.url), 'utf8'));
  const listener = (arr) => ({ addListener: (fn) => arr.push(fn) });
  const page = () => ({ id: 'sw-test', tab: { id: 1 }, url: win.location.href });
  const popup = { id: 'sw-test', url: 'chrome-extension://sw-test/src/popup.html' };
  const dispatch = (msg, sender) => new Promise((done) => {
    let handled = false;
    for (const fn of messageListeners) if (fn(msg, sender, done)) handled = true;
    if (!handled) done(undefined);
  });
  const io = [];
  class IO {
    constructor(callback, options) { this.cb = callback; this.options = options; this.elements = new Set(); io.push(this); }
    observe(el) { this.elements.add(el); if (this.options.rootMargin) queueMicrotask(() => { if (this.elements.has(el)) this.cb([{ target: el, isIntersecting: true, intersectionRatio: 1 }]); }); }
    unobserve(el) { this.elements.delete(el); }
    disconnect() { this.elements.clear(); }
  }
  Object.assign(globalThis, {
    window: win, document: win.document, location: win.location, MutationObserver: win.MutationObserver, IntersectionObserver: IO,
    setInterval: win.setInterval.bind(win),
    chrome: {
      storage: { local: {
        async setAccessLevel() { throw new Error('Access level not supported for this storage area'); }, // older Chromium
        async get(keys) { return structuredClone(keys == null ? local : Object.fromEntries((typeof keys === 'string' ? [keys] : keys).filter((k) => k in local).map((k) => [k, local[k]]))); },
        async set(values) { for (const [k, v] of Object.entries(values)) local[k] = structuredClone(v); },
        async remove(keys) { for (const k of keys) delete local[k]; },
      } },
      runtime: {
        id: 'sw-test', getURL: (path) => `chrome-extension://sw-test/${path}`, getManifest: () => manifest,
        onMessage: listener(messageListeners), onInstalled: listener([]), onStartup: listener([]),
        sendMessage: (msg) => { if (msg.type === 'event') pageEvents.push(`${msg.word}:${msg.event}`); return dispatch(msg, page()); },
        sendNativeMessage: async (_host, msg) => {
          if (msg.type === 'state') { stateRequests++; return { ok: true, ...structuredClone(hostState) }; }
          if (msg.type === 'events') return { ok: true, applied: msg.events.length };
          return { ok: false };
        },
      },
      tabs: { query: async () => [{ id: 1, url: win.location.href }], sendMessage: async (_id, msg) => { for (const fn of contentListeners) fn(msg); } },
      alarms: { create: async () => {}, onAlarm: listener([]) },
      permissions: { getAll: async () => ({ origins: ['https://*/*', 'http://*/*'] }), onAdded: listener([]), onRemoved: listener([]) },
      scripting: { getRegisteredContentScripts: async () => [], updateContentScripts: async () => {}, unregisterContentScripts: async () => {}, registerContentScripts: async () => {} },
    },
    fetch: async (_url, init) => {
      modelCalls++;
      const items = JSON.parse(JSON.parse(init.body).contents[0].parts[0].text.replace(/^Passages:\n/, ''));
      const passages = items.map(({ id, text }) => ({ id, swaps: text.includes(' and ') ? [{ o: 'and', es: 'y', ctx: '' }] : [] }));
      return { ok: true, status: 200, json: async () => ({ candidates: [{ content: { parts: [{ text: JSON.stringify({ passages }) }] } }] }) };
    },
  });
  const call = (msg) => dispatch(msg, popup);
  const config = () => dispatch({ type: 'config' }, page());
  const wait = (ms = 400) => new Promise((done) => setTimeout(done, ms));
  // A US evening and the next local morning share one UTC day.
  const localDayIs = (date) => {
    globalThis.Date = class extends RealDate {
      getFullYear() { return 2030; } getMonth() { return 0; } getDate() { return date; }
      toISOString() { return '2030-01-02T03:00:00.000Z'; }
    };
  };
  try {
    await import('../src/background.js?sync');

    // A browser that rejects the storage access level still answers.
    expect((await config()).settings).toMatchObject({ enabled: true, levelOverride: 1 });
    expect(await call({ type: 'syncWords' })).toEqual({ ok: true, error: null, count: 2, stage: 1 });
    expect((await config()).settings.newSitesEnabled).toBe(true);

    // The latest site choice wins: a popup choice made before setup's --sites follows setup after a sync.
    await call({ type: 'save', settings: { newSitesEnabled: false } });
    expect((await config()).settings.newSitesEnabled).toBe(false);
    hostState = { ...hostState, prefs: { extension_sites: 'all', extension_sites_at: Math.floor(local.settings.newSitesAt / 1000) + 1 } };
    await call({ type: 'syncWords' });
    expect((await config()).settings.newSitesEnabled).toBe(true);

    // Word state over 2 minutes old and a pause in Claude Code since: a page's request syncs first, gets a stale
    // reply and sends nothing to Gemini.
    local.wordState.fetchedAt = Date.now() - 3 * 60000;
    hostState = { ...hostState, paused: true };
    const requests = stateRequests;
    const { revision } = await config();
    const text = 'I enjoy cats and dogs every single day.';
    const paused = await dispatch({ type: 'swaps', revision, items: [{ key: `${revision}:${hashKey(text)}`, text }] }, page());
    expect(paused).toEqual({ results: {}, stale: true });
    expect(stateRequests).toBe(requests + 1);
    expect(modelCalls).toBe(0);
    expect((await config()).paused).toBe(true);
    hostState = { ...hostState, paused: false };
    await call({ type: 'syncWords' });

    const beforeContent = messageListeners.length;
    win.document.head.innerHTML = '<style>.hide-swaps .sw-word { opacity: 0; }</style>';
    win.document.body.innerHTML = `<main><p id="reading" class="hide-swaps">${text}</p></main>`;
    await import('../src/content.js?sync');
    contentListeners.push(...messageListeners.splice(beforeContent));
    await wait();
    expect(modelCalls).toBe(1);
    const el = win.document.querySelector('#reading');
    const span = el.querySelector('.sw-word');
    expect(span?.textContent).toBe('y');

    // A swap the page hides with CSS is on screen but not seen; once it shows, it counts.
    const visibility = io.findLast((o) => !o.options.rootMargin);
    const sighting = () => visibility.cb([{ target: span, isIntersecting: true, intersectionRatio: 1 }]);
    sighting(); await wait(20);
    expect(pageEvents).toEqual([]);
    el.classList.remove('hide-swaps');
    sighting(); await wait(20);
    expect(pageEvents).toEqual(['y:seen']);

    // Seen counts once per local day, like the plugin, not once per UTC day.
    try {
      localDayIs(1); sighting(); await wait(20);
      localDayIs(2); sighting(); await wait(20);
      sighting(); await wait(20);
    } finally { globalThis.Date = RealDate; }
    expect(pageEvents).toEqual(['y:seen', 'y:seen', 'y:seen']);
    expect(local.pendingEvents.map((e) => e.day).slice(-2)).toEqual(['2030-01-01', '2030-01-02']);

    // Another site's toggle changes nothing here: same revision, same span, no model call.
    const shown = (await config()).revision;
    await call({ type: 'save', siteOverride: { host: 'news.example', enabled: false } }); await wait();
    expect((await config()).revision).toBe(shown);
    expect(el.querySelector('.sw-word')).toBe(span);
    expect(modelCalls).toBe(1);

    // Turning this site off reverts it; turning it back on repaints from the cache, with no model call.
    await call({ type: 'save', siteOverride: { host: 'example.com', enabled: false } }); await wait(20);
    expect(el.querySelector('.sw-word')).toBeNull();
    expect(el.textContent).toBe(text);
    await call({ type: 'save', siteOverride: { host: 'example.com', enabled: true } }); await wait();
    expect(el.querySelector('.sw-word')?.textContent).toBe('y');
    expect(modelCalls).toBe(1);
  } finally {
    globalThis.Date = RealDate;
    await win.happyDOM.close();
    Object.assign(globalThis, originalGlobals);
  }
}, 20000);
