// Key changes in the worker: a new or re-pasted key gets a fresh start, a replaced key's late errors don't hold back
// the new one, and a refused key keeps saying so while it waits.
import { expect, test } from 'bun:test';
import { readFileSync } from 'node:fs';
import { hashKey } from '../src/hash.js';

const manifest = JSON.parse(readFileSync(new URL('../manifest.json', import.meta.url), 'utf8'));
const TEXT = 'This is a long enough passage and it is very nice to read today.';
let loads = 0;

async function boot({ local, fetchImpl, host = null }) {
  const listeners = [];
  const L = (arr) => ({ addListener: (fn) => arr.push(fn) });
  const data = structuredClone(local);
  const fetches = [];
  const broadcasts = [];
  const hostState = { geminiKey: host };
  globalThis.fetch = async (url, init) => { fetches.push(init.headers['x-api-key'] || init.headers['x-goog-api-key']); return fetchImpl(url, init); };
  globalThis.chrome = {
    storage: { local: {
      async setAccessLevel() {},
      async get(keys) { return structuredClone(keys == null ? data : Object.fromEntries([].concat(keys).filter((k) => k in data).map((k) => [k, data[k]]))); },
      async set(values) { for (const [k, v] of Object.entries(values)) data[k] = structuredClone(v); },
      async remove(keys) { for (const k of [].concat(keys)) delete data[k]; },
    } },
    runtime: { id: 'x', getURL: (p) => `chrome-extension://x/${p}`, getManifest: () => manifest, onMessage: L(listeners), onInstalled: L([]), onStartup: L([]),
      sendNativeMessage: async (_h, msg) => (hostState.geminiKey == null ? { ok: false, error: 'no host' }
        : msg.type === 'state' ? { ok: true, version: 'v1', stage: 1, prefs: { extension_sites: 'all' }, words: [{ es: 'y', en: 'and', hint: 'ee', status: 'active' }], geminiKey: hostState.geminiKey }
          : { ok: true, applied: 0 }) },
    tabs: { query: async () => [{ id: 1 }], sendMessage: async (_id, msg) => { broadcasts.push(msg.type); } },
    alarms: { create: () => {}, onAlarm: L([]) },
    permissions: { getAll: async () => ({ origins: ['https://*/*', ...manifest.host_permissions] }), onAdded: L([]), onRemoved: L([]) },
    scripting: { getRegisteredContentScripts: async () => [], registerContentScripts: async () => {}, updateContentScripts: async () => {}, unregisterContentScripts: async () => {} },
  };
  await import(`../src/background.js?keys${++loads}`);
  const send = (msg, sender) => new Promise((done) => { let handled = false; for (const fn of listeners) if (fn(msg, sender, done)) handled = true; if (!handled) done(undefined); });
  const page = { id: 'x', tab: { id: 1, title: 'A story' }, url: 'https://example.com/a' };
  const popup = { id: 'x', url: 'chrome-extension://x/src/popup.html' };
  let n = 0;
  const ask = async () => {
    const text = `${TEXT} Take ${++n}.`;
    const cfg = await send({ type: 'config' }, page);
    return send({ type: 'swaps', revision: cfg.revision, items: [{ key: `${cfg.revision}:${hashKey(text)}`, text }] }, page);
  };
  await new Promise((done) => setTimeout(done, 20));
  return { data, fetches, broadcasts, hostState, ask, popup: (msg) => send(msg, popup), sync: () => send({ type: 'syncWords' }, popup) };
}

const reply = (passages) => ({ ok: true, status: 200, json: async () => passages });
const geminiOk = (init) => {
  const ids = JSON.parse(JSON.parse(init.body).contents[0].parts[0].text.replace('Passages:\n', '')).map((p) => p.id);
  return reply({ candidates: [{ content: { parts: [{ text: JSON.stringify({ passages: ids.map((id) => ({ id, swaps: [] })) }) }] } }] });
};
const claudeOk = (init) => {
  const ids = JSON.parse(JSON.parse(init.body).messages[0].content.replace('Passages:\n', '')).map((p) => p.id);
  return reply({ stop_reason: 'end_turn', content: [{ type: 'text', text: JSON.stringify({ passages: ids.map((id) => ({ id, swaps: [] })) }) }] });
};
const daily429 = () => ({ ok: false, status: 429, headers: new Headers(), text: async () => JSON.stringify({ error: { details: [
  { violations: [{ quotaId: 'GenerateRequestsPerDayPerProjectPerModel-FreeTier' }] }, { retryDelay: '3600s' }] } }) });
const refused = () => ({ ok: false, status: 401, headers: new Headers(), text: async () => '' });
const settings = (model) => ({ model, newSitesEnabled: true, newSitesAt: Date.now() });

test('pasting the same Gemini key again lifts a spent day (billing turned on since)', async () => {
  let paid = false;
  const h = await boot({ local: { settings: settings('gemini-3.5-flash-lite'), apiKey: 'K' }, fetchImpl: async (_u, init) => (paid ? geminiOk(init) : daily429()) });
  expect((await h.ask()).error).toContain('daily quota');
  expect((await h.ask()).error).toContain('daily quota'); // waits: no new call
  expect(h.fetches).toEqual(['K']);
  paid = true;
  await h.popup({ type: 'save', apiKey: 'K' });
  expect(h.broadcasts.at(-1)).toBe('retry');
  expect((await h.ask()).error).toBeUndefined();
  expect(h.fetches).toEqual(['K', 'K']);
});

test("a replaced key's late error doesn't hold back the new key or come back in the popup", async () => {
  let release;
  const gate = new Promise((done) => { release = done; });
  const h = await boot({ local: { settings: settings('claude-haiku-5-5'), claudeKey: 'OLD' },
    fetchImpl: async (_u, init) => (init.headers['x-api-key'] === 'OLD' ? (await gate, refused()) : claudeOk(init)) });
  const inFlight = h.ask();
  await new Promise((done) => setTimeout(done, 20));
  await h.popup({ type: 'save', claudeKey: 'NEW' });
  release();
  expect((await inFlight).error).toContain('Claude key was refused');
  expect(h.data.modelStatus).toBeNull(); // the popup keeps the new key's fresh start
  expect((await h.ask()).error).toBeUndefined(); // no hour-long wait carried over to NEW
  expect(h.fetches).toEqual(['OLD', 'NEW']);
});

test('a refused Claude key keeps saying so while it waits, instead of "rate limit"', async () => {
  const h = await boot({ local: { settings: settings('claude-haiku-5-5'), claudeKey: 'BAD' }, fetchImpl: async () => refused() });
  expect((await h.ask()).error).toContain('Claude key was refused');
  expect((await h.ask()).error).toContain('Claude key was refused');
  expect(h.fetches).toEqual(['BAD']); // the second batch waits without a call
  expect(h.data.modelStatus.error).toContain('Claude key was refused');
});

test("a new key from setup gets the same fresh start as a pasted one", async () => {
  const h = await boot({ local: { settings: settings('gemini-3.5-flash-lite') }, host: 'OLD',
    fetchImpl: async (_u, init) => (init.headers['x-goog-api-key'] === 'NEW' ? geminiOk(init) : daily429()) });
  await h.sync();
  expect((await h.ask()).error).toContain('daily quota');
  h.hostState.geminiKey = 'NEW';
  await h.sync();
  expect(h.broadcasts.at(-1)).toBe('retry');
  expect(h.data.modelStatus).toBeNull();
  expect((await h.ask()).error).toBeUndefined();
  await h.sync();
  expect(h.broadcasts.at(-1)).toBe('config'); // the same key again: no restart
});
