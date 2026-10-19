// Service worker: word state and the Gemini key from the Claude Code plugin (native host), site access,
// one model call at a time, results back to pages, seen/flip/peek events back to the plugin.
// Keys stay here; pages only get a config without them.
import { createCache, chromeStorage } from './cache.js';
import { requestSwaps } from './engine.js';
import { cleanSettings, newSitesDefault, siteEnabled, hasSiteAccess, swapSettings } from './settings.js';
import { resolveLevel, exactEs, isZeroSpanish, wordCount } from './levels.js';
import { hashKey } from './hash.js';
import { swapRevision } from './revision.js';
import { HOST, refresh, readCached, queueEvents, flushEvents, shownToday } from './hostsource.js';
import { quotaError, countCall } from './quota.js';

const store = chrome.storage.local;
const cache = createCache(chromeStorage);
const send = (message) => chrome.runtime.sendNativeMessage(HOST, message);
const ALARM = 'sync';
// Word state syncs every SYNC_MINUTES, when the popup opens, and before a page's swap request once it is STALE_MS old.
// So after a pause in Claude Code no new page text goes to Gemini within STALE_MS, but a page that asks for nothing
// (all painted) keeps its Spanish until the alarm, the popup, or a request from any page brings the pause
// (sw.py's CHROME_PAUSED and CHROME_PICKS_UP say so).
const SYNC_MINUTES = 10;
const STALE_MS = 120000;
const FLUSH_DELAY_MS = 10000;
const cooldown = new Map(); // model -> rate-limit cooldown end; worker memory is enough

const serial = () => {
  let chain = Promise.resolve();
  return (fn) => { const p = chain.then(fn); chain = p.catch(() => {}); return p; };
};
const modelCall = serial(); // one model call at a time
const locked = serial(); // storage read-modify-writes one at a time, or concurrent ones drop data

const ready = (async () => {
  // Content scripts run on every enabled site, so stored keys are kept out of their reach. Some Chromium builds reject
  // this; page scripts still can't read extension storage, so the extension carries on without it.
  try {
    if (store.setAccessLevel) await store.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' });
  } catch { /* see above */ }
  const { settings } = await store.get('settings');
  if (settings?.apiKey) await store.set({ apiKey: settings.apiKey }); // 0.1 kept a pasted key in settings
  await store.set({ settings: cleanSettings(settings) });
})();

// What pages get. The revision changes whenever anything that affects which swaps are chosen does, so stale replies
// are dropped. Where swaps run (on/off, sites, access, pause) and how they look don't change it: pages stop or start
// for those, and cached swaps stay good, so toggling them costs no model calls.
async function context() {
  await ready;
  const data = await store.get(['settings', 'wordState', 'apiKey', 'hostKey', 'epoch']);
  const state = data.wordState?.words?.length ? data.wordState : null;
  const saved = cleanSettings(data.settings);
  const settings = { ...saved, newSitesEnabled: newSitesDefault(saved, state?.sites, state?.sitesAt) };
  const level = resolveLevel(saved, state?.stage).effective;
  const hasKey = !!(data.apiKey || data.hostKey);
  const paused = !!state?.paused;
  const { origins = [] } = await chrome.permissions.getAll();
  const revision = swapRevision({ extension: chrome.runtime.getManifest?.()?.version || '', epoch: data.epoch || '',
    settings: swapSettings(settings), level, words: state?.version || '', hasKey });
  return { settings, level, revision, hasKey, paused, origins, stage: state?.stage || 0 };
}

const activeOn = (ctx, url) => ctx.hasKey && !ctx.paused && siteEnabled(ctx.settings, url) && hasSiteAccess(url, ctx.origins);

async function broadcast(type = 'config') {
  const config = await context();
  const tabs = await chrome.tabs.query({});
  await Promise.allSettled(tabs.map((t) => chrome.tabs.sendMessage(t.id, { type, config })));
}

// The native host can't push a pause or a setup rerun, so a page asking for swaps with word state older than
// STALE_MS syncs first. lastAttempt keeps a missing host to one try per STALE_MS; requests meanwhile wait on it.
let lastAttempt = 0;
let syncing = Promise.resolve();
async function maybeSync() {
  const { wordState } = await store.get('wordState');
  const now = Date.now();
  if (now - (wordState?.fetchedAt || 0) >= STALE_MS && now - lastAttempt >= STALE_MS) {
    lastAttempt = now;
    syncing = syncWords().catch(() => {});
  }
  await syncing;
}

async function swaps(msg, sender) {
  await maybeSync();
  const ctx = await context();
  if (msg.revision !== ctx.revision || !activeOn(ctx, sender.url)) return { results: {}, stale: true };
  if (!Array.isArray(msg.items) || msg.items.length > 8) throw new Error('Invalid text batch');
  const items = msg.items.filter((i) => i && typeof i.text === 'string' && i.text.length <= 2000 &&
    wordCount(i.text) >= 6 && !isZeroSpanish(i.text) && i.key === `${ctx.revision}:${hashKey(i.text)}`);
  const results = await cache.getMany(items.map((i) => i.key));
  const misses = items.filter((i) => !(i.key in results));
  if (!misses.length) return { results };
  try {
    const fresh = await modelCall(async () => {
      const now = await context();
      if (now.revision !== ctx.revision || !activeOn(now, sender.url)) return null;
      const host = new URL(sender.url).host;
      const over = await quotaError(chromeStorage, host);
      if (over) throw new Error(over);
      const { wordState, apiKey, hostKey } = await store.get(['wordState', 'apiKey', 'hostKey']);
      const fetchImpl = async (...args) => { await countCall(chromeStorage, undefined, host); return fetch(...args); };
      return requestSwaps({ apiKey: apiKey || hostKey, model: ctx.settings.model, level: ctx.level, words: wordState?.words, fetchImpl,
        shownToday: await shownToday(chromeStorage), cooldown, batch: misses.map((i) => ({ id: i.key, text: i.text })) });
    });
    // Turned off, paused or changed during the request: nothing is cached or painted.
    return await locked(async () => {
      const now = await context();
      if (!fresh || now.revision !== ctx.revision || !activeOn(now, sender.url)) return { results: {}, stale: true };
      await cache.setMany(fresh.results);
      await store.set({ modelStatus: { at: Date.now(), error: '', model: fresh.model } });
      return { results: { ...results, ...fresh.results } };
    });
  } catch (e) {
    const error = e?.message || 'Model request failed';
    await store.set({ modelStatus: { at: Date.now(), error } });
    return { results, error, retryAfterMs: e?.retryAfterMs };
  }
}

const flush = () => locked(() => flushEvents({ storage: chromeStorage, send }));
let flushTimer = null;
function scheduleFlush() {
  clearTimeout(flushTimer);
  flushTimer = setTimeout(flush, FLUSH_DELAY_MS);
}

// Events only for words in the plugin's word state; queueEvents keeps seen and peek to once per word per day.
async function record(msg, sender) {
  const ctx = await context();
  if (!activeOn(ctx, sender.url) || !['seen', 'flip', 'peek'].includes(msg.event) || typeof msg.word !== 'string') return { ok: false };
  const word = (await readCached(chromeStorage))?.words.find((w) => exactEs(w.es) === exactEs(msg.word));
  if (!word) return { ok: false };
  await locked(() => queueEvents(chromeStorage, [{ word: word.es, kind: msg.event }]));
  scheduleFlush();
  return { ok: true };
}

// A new word-state version clears the decision cache, because cached swaps were chosen against the old list. The
// plugin leaves the pause flag out of that version (swlib.version), so a pause and resume keep the cache; the flag
// itself reaches pages through broadcast(), which stops or starts them.
async function syncWords() {
  await flush();
  const res = await refresh({ storage: chromeStorage, send });
  if (res.changed) await locked(() => cache.clear());
  await broadcast();
  return { ok: !res.error, error: res.error, count: res.state?.words?.length || 0, stage: res.state?.stage || 0 };
}

async function clearCache() {
  const removed = await locked(async () => {
    await store.set({ epoch: crypto.randomUUID() });
    return cache.clear();
  });
  await broadcast('retry');
  return { ok: true, removed };
}

// msg.settings: a partial patch; msg.siteOverride: { host, enabled: true | false | null (reset) }; msg.apiKey.
async function save(msg) {
  await locked(async () => {
    const saved = await store.get('settings');
    const merged = { ...saved.settings, ...msg.settings };
    // Timed, so whichever of this and setup's --sites came last wins (newSitesDefault).
    if (msg.settings && Object.hasOwn(msg.settings, 'newSitesEnabled')) merged.newSitesAt = Date.now();
    if (msg.siteOverride && typeof msg.siteOverride.host === 'string') {
      merged.siteOverrides = { ...saved.settings?.siteOverrides };
      if (msg.siteOverride.enabled === null) delete merged.siteOverrides[msg.siteOverride.host];
      else merged.siteOverrides[msg.siteOverride.host] = msg.siteOverride.enabled;
    }
    const patch = { settings: cleanSettings(merged) };
    if (typeof msg.apiKey === 'string') {
      if (msg.apiKey.length > 500) throw new Error('Key is too long');
      patch.apiKey = msg.apiKey.trim();
    }
    await store.set(patch);
  });
  await broadcast();
  return { ok: true };
}

async function status() {
  const config = await context();
  const data = await store.get(['wordState', 'apiKey', 'hostKey', 'modelStatus']);
  return { config, words: data.wordState?.words?.length || 0, fetchedAt: data.wordState?.fetchedAt || 0,
    pastedKey: !!data.apiKey, hostKey: !!data.hostKey, modelStatus: data.modelStatus || null };
}

// Pages may only ask for config, swaps and events; everything else is popup-only.
chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (!msg || sender.id !== chrome.runtime.id) return false;
  const popup = sender.url === chrome.runtime.getURL('src/popup.html');
  const page = sender.tab && /^https?:\/\//.test(sender.url || '');
  const handlers = {
    config: context,
    swaps: () => swaps(msg, sender),
    event: () => record(msg, sender),
    status, syncWords, clearCache,
    save: () => save(msg),
  };
  if (!handlers[msg.type] || (!popup && !(page && ['config', 'swaps', 'event'].includes(msg.type)))) return false;
  ready.then(handlers[msg.type]).then(reply, (e) => reply({ error: String(e?.message || e) }));
  return true;
});

// Granted origins (all sites, or one at a time from the popup) decide where the content script is injected.
// X and Instagram are in the manifest's content_scripts, so they work without a grant; the registered script
// excludes every manifest match, so no page gets the content script twice.
const manifestSites = () => chrome.runtime.getManifest().content_scripts.flatMap((c) => c.matches);
let registrations = Promise.resolve();
function registerSites() {
  const p = registrations.then(async () => {
    const { origins = [] } = await chrome.permissions.getAll();
    const matches = [...new Set(origins.flatMap((o) => o === '<all_urls>' ? ['http://*/*', 'https://*/*'] : [o]))]
      .filter((o) => /^(https?|\*):\/\//.test(o) && !o.includes('googleapis.com'));
    const existing = await chrome.scripting.getRegisteredContentScripts({ ids: ['weave-sites'] });
    if (!matches.length) {
      if (existing.length) await chrome.scripting.unregisterContentScripts({ ids: ['weave-sites'] });
      return;
    }
    const script = { id: 'weave-sites', matches, js: ['src/content.bundle.js'], css: ['src/content.css'], runAt: 'document_idle',
      excludeMatches: manifestSites() };
    if (existing.length) await chrome.scripting.updateContentScripts([script]);
    else await chrome.scripting.registerContentScripts([script]);
  });
  registrations = p.catch(() => {});
  return p;
}
const permissionsChanged = () => { void registerSites().then(() => broadcast('retry')).catch(() => {}); };
chrome.permissions.onAdded.addListener(permissionsChanged);
chrome.permissions.onRemoved.addListener(permissionsChanged);

// create() replaces an alarm of the same name, so calling it on both events is safe. Startup matters
// because disabling and re-enabling the extension clears alarms without firing onInstalled.
function arm() {
  chrome.alarms.create(ALARM, { periodInMinutes: SYNC_MINUTES });
  void syncWords().catch(() => {});
}
chrome.runtime.onInstalled.addListener(arm);
chrome.runtime.onStartup.addListener(arm);
chrome.alarms.onAlarm.addListener((a) => { if (a.name === ALARM) void syncWords().catch(() => {}); });
void ready.then(registerSites).catch(() => {});
