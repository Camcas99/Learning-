// Service worker: word state and the Gemini key from the Claude Code plugin (native host), a pasted Claude key, site access,
// one model call at a time, results back to pages, seen/flip/peek events back to the plugin.
// Keys stay here; pages only get a config without them.
import { createCache, chromeStorage } from './cache.js';
import { requestSwaps } from './engine.js';
import { isClaude } from './anthropic.js';
import { cleanSettings, newSitesDefault, siteEnabled, hasSiteAccess, swapSettings } from './settings.js';
import { resolveLevel, exactEs, isZeroSpanish, wordCount } from './levels.js';
import { hashKey } from './hash.js';
import { swapRevision } from './revision.js';
import { HOST, refresh, readCached, queueEvents, flushEvents, shownToday } from './hostsource.js';
import { quotaError, countCall, spentToday, saveSpent } from './quota.js';

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
// Per set of keys: model -> cooldown end, and model -> why. Worker memory is enough. Keyed by the keys in use, so a
// late error from a key that was just replaced never holds back the new one.
const cooldowns = new Map();
const cooldownFor = (id) => {
  if (!cooldowns.has(id)) cooldowns.set(id, { until: new Map(), why: new Map() });
  return cooldowns.get(id);
};

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
  const data = await store.get(['settings', 'wordState', 'apiKey', 'hostKey', 'claudeKey', 'epoch']);
  const state = data.wordState?.words?.length ? data.wordState : null;
  const saved = cleanSettings(data.settings);
  const settings = { ...saved, newSitesEnabled: newSitesDefault(saved, state?.sites, state?.sitesAt) };
  const level = resolveLevel(saved, state?.stage).effective;
  // A key for the chosen model: Claude Haiku needs the Claude key (it never falls back to Gemini), the others Gemini's.
  const hasKey = isClaude(settings.model) ? !!data.claudeKey : !!(data.apiKey || data.hostKey);
  const paused = !!state?.paused;
  const origins = await siteOrigins();
  const revision = swapRevision({ extension: chrome.runtime.getManifest?.()?.version || '', epoch: data.epoch || '',
    settings: swapSettings(settings), level, words: state?.version || '', hasKey });
  return { settings, level, revision, hasKey, paused, origins, stage: state?.stage || 0 };
}

// Granted site origins, without the API hosts the manifest itself asks for (Gemini, Anthropic): those are never sites
// to run on, so api.anthropic.com doesn't get the content script or count as an allowed site.
async function siteOrigins() {
  const api = new Set(chrome.runtime.getManifest?.()?.host_permissions || []);
  const { origins = [] } = await chrome.permissions.getAll();
  return origins.filter((o) => !api.has(o));
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
  // Title guard: a page whose title is about money, health, legal matters, safety or driving stays English, and its
  // text never goes to the model (from French Weave by Jackie Oliver, MIT).
  if (isZeroSpanish(String(sender.tab?.title || ''))) return { results: Object.fromEntries(items.map((i) => [i.key, []])) };
  const results = await cache.getMany(items.map((i) => i.key));
  const misses = items.filter((i) => !(i.key in results));
  if (!misses.length) return { results };
  let keys = ''; // the hash of the keys this request used
  const sameKeys = async () => {
    const k = await store.get(['apiKey', 'hostKey', 'claudeKey']);
    return hashKey(`${k.apiKey || k.hostKey || ''}\n${k.claudeKey || ''}`) === keys;
  };
  try {
    const fresh = await modelCall(async () => {
      const now = await context();
      if (now.revision !== ctx.revision || !activeOn(now, sender.url)) return null;
      const host = new URL(sender.url).host;
      const over = await quotaError(chromeStorage, host);
      if (over) throw new Error(over);
      const { wordState, apiKey, hostKey, claudeKey } = await store.get(['wordState', 'apiKey', 'hostKey', 'claudeKey']);
      const fetchImpl = async (...args) => { await countCall(chromeStorage, undefined, host); return fetch(...args); };
      const geminiKey = apiKey || hostKey;
      const keyId = geminiKey ? hashKey(geminiKey) : '';
      const daily = await spentToday(chromeStorage, keyId);
      const loaded = new Map(daily);
      keys = hashKey(`${geminiKey || ''}\n${claudeKey || ''}`);
      const cool = cooldownFor(keys);
      try {
        return await requestSwaps({ apiKey: geminiKey, claudeKey, model: ctx.settings.model, level: ctx.level, words: wordState?.words, fetchImpl,
          shownToday: await shownToday(chromeStorage), cooldown: cool.until, why: cool.why, daily, batch: misses.map((i) => ({ id: i.key, text: i.text })) });
      } finally {
        await locked(async () => {
          const stored = await store.get(['apiKey', 'hostKey']);
          const current = stored.apiKey || stored.hostKey;
          await saveSpent(chromeStorage, daily, loaded, keyId, current ? hashKey(current) : '');
        });
      }
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
    // An error from a key that was replaced meanwhile isn't the new key's: the popup keeps the fresh start.
    if (!keys || await sameKeys()) await store.set({ modelStatus: { at: Date.now(), error } });
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
  const { hostKey: before = '' } = await store.get('hostKey');
  const res = await refresh({ storage: chromeStorage, send });
  if (res.changed) await locked(() => cache.clear());
  const { hostKey: after = '' } = await store.get('hostKey');
  if (before !== after) {
    // Setup stored a new Gemini key: a fresh start, as for a pasted one (save).
    cooldowns.clear();
    await store.set({ modelStatus: null });
    await broadcast('retry');
  } else await broadcast();
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

// msg.settings: a partial patch; msg.siteOverride: { host, enabled: true | false | null (reset) }; msg.apiKey;
// msg.claudeKey.
async function save(msg) {
  const newKey = await locked(async () => {
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
      // A paste, even of the same key, lifts a spent day: after billing is turned on, Google takes the key again.
      patch.dailyQuota = null;
    }
    if (typeof msg.claudeKey === 'string') {
      if (msg.claudeKey.length > 500) throw new Error('Key is too long');
      patch.claudeKey = msg.claudeKey.trim();
    }
    const fresh = 'apiKey' in patch || 'claudeKey' in patch;
    if (fresh) {
      // A new key gets a fresh start: no cooldown or old error, and open pages ask again at once instead of waiting out
      // the old key's retry (an hour for a refused key, until midnight Pacific for a spent day). A new Gemini key has
      // no spent day of its own, because quota.js ties that record to the key.
      cooldowns.clear();
      patch.modelStatus = null;
    }
    await store.set(patch);
    return fresh;
  });
  await broadcast(newKey ? 'retry' : 'config');
  return { ok: true };
}

async function status() {
  const config = await context();
  const data = await store.get(['wordState', 'apiKey', 'hostKey', 'claudeKey', 'modelStatus']);
  return { config, words: data.wordState?.words?.length || 0, fetchedAt: data.wordState?.fetchedAt || 0,
    pastedKey: !!data.apiKey, hostKey: !!data.hostKey, claudeKey: !!data.claudeKey, modelStatus: data.modelStatus || null };
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
    const origins = await siteOrigins();
    const matches = [...new Set(origins.flatMap((o) => o === '<all_urls>' ? ['http://*/*', 'https://*/*'] : [o]))]
      .filter((o) => /^(https?|\*):\/\//.test(o));
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
