// Improvements ported from French Weave (Jackie Oliver, MIT) in 0.3.2 and 0.3.3.
import { expect, it } from 'bun:test';
import { offByDefault, siteOn } from '../src/settings.js';
import { locate } from '../src/text.js';
import { allCaps, glossMatch, matchCase, validateSwaps } from '../src/levels.js';
import { createCache, memoryStorage, CACHE_MAX_AGE_MS } from '../src/cache.js';
import { TWEET } from '../src/page.js';
import { pickBatch } from '../src/pick.js';
import { dailyQuota, dailyReset } from '../src/gemini.js';
import { requestSwaps } from '../src/engine.js';
import { saveSpent, spentToday } from '../src/quota.js';
import { buildClaudeRequest, CLAUDE_URL } from '../src/anthropic.js';
import { cleanSettings } from '../src/settings.js';

it('banking, payments, health, password and government sites start off, subdomains included', () => {
  for (const host of ['www.chase.com', 'secure.chase.com', 'bankofamerica.com', 'mychart.example.org', 'irs.gov',
    'sat.gob.mx', 'docs.google.com', 'vault.bitwarden.com', 'www.paypal.com', 'mail.google.com.', 'MAIL.GOOGLE.COM']) {
    expect(offByDefault(host)).toBe(true);
  }
  for (const host of ['en.wikipedia.org', 'news.ycombinator.com', 'x.com', 'www.nytimes.com', 'www.reddit.com']) {
    expect(offByDefault(host)).toBe(false);
  }
});

it('a site choice matches the host whatever its case or trailing dot, and a popup choice still wins', () => {
  const settings = { newSitesEnabled: true, siteOverrides: { 'www.chase.com': true, 'a.example': false } };
  expect(siteOn(settings, 'WWW.CHASE.COM.')).toBe(true);
  expect(siteOn(settings, 'A.Example')).toBe(false);
  expect(siteOn(settings, 'b.example')).toBe(true);
  expect(siteOn({ newSitesEnabled: true, siteOverrides: {} }, 'constructor')).toBe(false); // no prototype keys
});

it('never swaps inside a contraction or a hyphenated word', () => {
  expect(locate({ text: "Here's the plan for now." }, 'Here')).toBeNull();
  expect(locate({ text: 'The now-frozen lake is pretty now.' }, 'now')).toEqual({ start: 30, end: 33 });
  expect(locate({ text: "It isn't ready but it works" }, 'but')).toEqual({ start: 15, end: 18 });
});

it('"I think" mid-sentence stays lowercase in Spanish, and ALL-CAPS English stays English', () => {
  expect(matchCase('creo que', 'I think')).toBe('creo que');
  expect(matchCase('pero', 'But')).toBe('Pero');
  expect(matchCase('pero', 'BUT')).toBe('pero');
  expect(allCaps('WITHOUT')).toBe(true);
  expect(allCaps('OK')).toBe(false);
  expect(allCaps('Without')).toBe(false);
});

it('cached swaps are reused for 3 days, then asked for again', async () => {
  let t = 1_000_000_000_000;
  const cache = createCache(memoryStorage(), { now: () => t });
  await cache.setMany({ k: [{ o: 'and', es: 'y' }] });
  t += CACHE_MAX_AGE_MS - 1000;
  expect(await cache.getMany(['k'])).toEqual({ k: [{ o: 'and', es: 'y' }] });
  t += 2000;
  expect(await cache.getMany(['k'])).toEqual({});
});

it('logged-out X post text is found too', () => {
  expect(TWEET).toContain('[data-testid="tweetText"]');
  expect(TWEET).toContain('article div[dir="auto"]:not(:has(div[dir="auto"]))');
});

it('a swap must replace its own gloss, a synonym or an inflection of it, and a plural needs a plural word', () => {
  const words = [
    { es: 'entonces', en: 'so / then', hint: 'en-TOHN-ses', status: 'active' },
    { es: 'el problema', en: 'the problem', hint: 'el proh-BLEH-mah', status: 'active' },
    { es: 'arreglar', en: 'to fix', hint: 'ah-rreh-GLAHR', status: 'active' },
    { es: 'grande', en: 'big', hint: 'GRAHN-deh', status: 'known' },
    { es: 'la idea', en: 'the idea', hint: 'lah ee-DEH-ah', status: 'known' },
    { es: 'los zapatos', en: 'the shoes', hint: 'lohs sah-PAH-tohs', status: 'known' },
    { es: 'el zapato', en: 'the shoe', hint: 'el sah-PAH-toh', status: 'known' },
  ];
  const kept = (o, es) => validateSwaps(1, [{ o, es }], words).map((s) => s.es);
  expect(kept('to start', 'entonces')).toEqual([]);
  expect(kept('then', 'entonces')).toEqual(['entonces']);
  expect(kept('huge', 'grande')).toEqual(['grande']);
  expect(kept('fixed', 'arreglar')).toEqual(['arreglar']);
  expect(kept('the problem', 'el problema')).toEqual(['el problema']);
  expect(kept('problem', 'el problema')).toEqual(['problema']); // the page keeps its "the"
  expect(kept('ideas', 'la idea')).toEqual([]);
  expect(kept('the shoes', 'el zapato')).toEqual(['los zapatos']);
  expect(glossMatch('Problems', 'the problem')).toBe('plural');
  expect(glossMatch('fixing', 'to fix')).toBe('inflected');
  expect(glossMatch('right', 'the problem')).toBe('');
});

it('the next batch takes the passages nearest the window and drops ones that left the page', () => {
  const el = (top, connected = true) => ({ isConnected: connected, getBoundingClientRect: () => ({ top, bottom: top + 50 }) });
  const keyOf = new Map();
  const pending = new Map();
  const add = (key, e) => { keyOf.set(e, key); pending.set(key, { text: key, els: new Set([e]) }); };
  add('scrolled-past', el(-3000));
  add('gone', el(100, false));
  add('below', el(1200));
  add('on-screen-low', el(500));
  add('on-screen-top', el(10));
  add('out', el(20));
  const picked = pickBatch(pending, new Set(['out']), (e) => keyOf.get(e), 800, 3).map((i) => i.key);
  expect(picked).toEqual(['on-screen-top', 'on-screen-low', 'below']);
  expect(pending.has('gone')).toBe(false);
  expect(pending.has('scrolled-past')).toBe(true); // still waiting, just last
});

it("a spent daily quota waits until just after midnight Pacific, survives in storage, and a new batch doesn't ask", async () => {
  const at = Date.UTC(2026, 9, 20, 15, 0); // 8:00 AM Pacific (PDT)
  expect(dailyReset(at)).toBe(Date.UTC(2026, 9, 21, 7, 1)); // 12:01 AM PDT
  expect(dailyReset(Date.UTC(2026, 11, 1, 20, 0))).toBe(Date.UTC(2026, 11, 2, 8, 1)); // PST
  const body = JSON.stringify({ error: { status: 'RESOURCE_EXHAUSTED', details: [{ violations: [{ quotaId: 'GenerateRequestsPerDayPerProjectPerModel-FreeTier' }] }], message: 'key AIzaSECRET' } });
  expect(dailyQuota(body)).toBe(true);
  expect(dailyQuota(JSON.stringify({ error: { details: [{ violations: [{ quotaId: 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier' }] }] } }))).toBe(false);
  let calls = 0;
  const fetchImpl = async () => { calls++; return { ok: false, status: 429, text: async () => body, headers: { get: () => null } }; };
  const daily = new Map();
  const ask = () => requestSwaps({ apiKey: 'K', model: 'gemini-3.8-flash', level: 1, batch: [{ id: 'a', text: 'x and y' }], fetchImpl, daily, now: () => at });
  const first = await ask().catch((e) => e);
  expect(first.daily).toBe(true);
  expect(first.message).toContain("daily quota for this key is used up; Spanish resumes at");
  expect(first.message).not.toContain('SECRET');
  expect(first.retryAfterMs).toBe(Date.UTC(2026, 9, 21, 7, 1) - at);
  expect(calls).toBe(2); // both models
  await ask().catch(() => {});
  expect(calls).toBe(2); // nothing more until the reset
  const storage = memoryStorage();
  await saveSpent(storage, daily, new Map(), at);
  expect([...(await spentToday(storage, at)).keys()]).toEqual(['gemini-3.8-flash', 'gemini-3.5-flash-lite']);
  expect((await spentToday(storage, Date.UTC(2026, 9, 21, 7, 2))).size).toBe(0);
});

it('Claude Haiku: structured JSON request with the key in a header, plain errors, and Gemini as the fallback', async () => {
  const body = buildClaudeRequest({ model: 'claude-haiku-5-5', system: 'S', user: 'U', schema: { type: 'object', properties: { a: { type: 'object', properties: {} } } } });
  expect(body.output_config).toEqual({ effort: 'low', format: { type: 'json_schema', schema: { type: 'object', additionalProperties: false,
    properties: { a: { type: 'object', properties: {}, additionalProperties: false } } } } });
  expect(body.thinking).toBeUndefined();
  expect(cleanSettings({ model: 'claude-haiku-5-5' }).model).toBe('claude-haiku-5-5');
  const seen = [];
  const reply = { passages: [{ id: 'a', swaps: [{ o: 'and', es: 'y', g: 'and', h: 'ee', ctx: 'cats and dogs' }] }] };
  const fetchImpl = async (url, init) => {
    seen.push({ url, headers: init.headers });
    if (url === CLAUDE_URL) return { ok: false, status: 401, headers: { get: () => null }, text: async () => '{"error":{"message":"bad key sk-ant-SECRET"}}' };
    return { ok: true, json: async () => ({ candidates: [{ content: { parts: [{ text: JSON.stringify(reply) }] } }] }) };
  };
  const batch = [{ id: 'a', text: 'cats and dogs play in the yard' }];
  const r = await requestSwaps({ apiKey: 'G', claudeKey: 'C', model: 'claude-haiku-5-5', level: 1, batch, fetchImpl });
  expect(seen[0].headers['x-api-key']).toBe('C');
  expect(seen[0].headers['anthropic-version']).toBe('2023-06-01');
  expect(r.model).toBe('gemini-3.5-flash-lite');
  expect(r.errors.join()).toContain('Claude key was refused');
  expect(r.errors.join()).not.toContain('SECRET');
  await expect(requestSwaps({ apiKey: '', claudeKey: '', model: 'claude-haiku-5-5', level: 1, batch, fetchImpl })).rejects.toThrow('Add a Claude key');
});
