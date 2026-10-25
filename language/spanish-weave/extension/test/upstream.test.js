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
  await saveSpent(storage, daily, new Map(), 'key1', 'key1', at);
  expect([...(await spentToday(storage, 'key1', at)).keys()]).toEqual(['gemini-3.8-flash', 'gemini-3.5-flash-lite']);
  expect((await spentToday(storage, 'key1', Date.UTC(2026, 9, 21, 7, 2))).size).toBe(0);
  expect((await spentToday(storage, 'key2', at)).size).toBe(0); // a new key (pasted or from setup) starts fresh
  const late = memoryStorage();
  await saveSpent(late, daily, new Map(), 'key1', 'key2', at); // the old key's 429 landed after the key changed
  expect((await spentToday(late, 'key2', at)).size).toBe(0);
  expect((await spentToday(late, 'key1', at)).size).toBe(0);
});

it('Claude Haiku: structured JSON request with the key in a header, plain errors, and never a quiet Gemini fallback', async () => {
  const body = buildClaudeRequest({ model: 'claude-haiku-5-5', system: 'S', user: 'U', schema: { type: 'object', properties: { a: { type: 'object', properties: {} } } } });
  expect(body.output_config).toEqual({ effort: 'low', format: { type: 'json_schema', schema: { type: 'object', additionalProperties: false,
    properties: { a: { type: 'object', properties: {}, additionalProperties: false } } } } });
  expect(body.thinking).toBeUndefined();
  expect(cleanSettings({ model: 'claude-haiku-5-5' }).model).toBe('claude-haiku-5-5');
  const seen = [];
  const reply = { passages: [{ id: 'a', swaps: [{ o: 'and', es: 'y', g: 'and', h: 'ee', ctx: 'cats and dogs' }] }] };
  let claudeOk = false;
  const fetchImpl = async (url, init) => {
    seen.push({ url, headers: init.headers });
    if (url === CLAUDE_URL && !claudeOk) return { ok: false, status: 401, headers: { get: () => null }, text: async () => '{"error":{"message":"bad key sk-ant-SECRET"}}' };
    if (url === CLAUDE_URL) return { ok: true, json: async () => ({ stop_reason: 'end_turn', content: [{ type: 'text', text: JSON.stringify(reply) }] }) };
    return { ok: true, json: async () => ({ candidates: [{ content: { parts: [{ text: JSON.stringify(reply) }] } }] }) };
  };
  const batch = [{ id: 'a', text: 'cats and dogs play in the yard' }];
  const failed = await requestSwaps({ apiKey: 'G', claudeKey: 'C', model: 'claude-haiku-5-5', level: 1, batch, fetchImpl }).catch((e) => e);
  expect(seen.map((r) => r.url)).toEqual([CLAUDE_URL]); // the Gemini key is never used for a Claude pick
  expect(seen[0].headers['x-api-key']).toBe('C');
  expect(seen[0].headers['anthropic-version']).toBe('2023-06-01');
  expect(failed.message).toContain('Claude key was refused');
  expect(failed.message).not.toContain('SECRET');
  claudeOk = true;
  const r = await requestSwaps({ apiKey: 'G', claudeKey: 'C', model: 'claude-haiku-5-5', level: 1, batch, fetchImpl });
  expect([r.model, r.results.a.map((x) => x.es)]).toEqual(['claude-haiku-5-5', ['y']]);
  await expect(requestSwaps({ apiKey: 'G', claudeKey: '', model: 'claude-haiku-5-5', level: 1, batch, fetchImpl })).rejects.toThrow('Add a Claude key');
});

it('the bare-noun rule drops only el/la/los/las of the same word, and natural English still matches (0.3.3 review)', () => {
  const words = [
    { es: 'un poco', en: 'a little', hint: 'oon POH-koh', status: 'active' },
    { es: 'una vez', en: 'once', hint: 'OO-nah bes', status: 'active' },
    { es: 'la mañana', en: 'the morning', hint: 'lah mah-NYAH-nah', status: 'active' },
    { es: 'mañana', en: 'tomorrow', hint: 'mah-NYAH-nah', status: 'active' },
    { es: 'el cambio', en: 'the change', hint: 'el KAHM-byoh', status: 'active' },
    { es: 'funciona', en: 'it works', hint: 'foon-SYOH-nah', status: 'active' },
    { es: 'soy', en: 'I am (who or what I am)', hint: 'soy', status: 'active' },
    { es: 'hacer', en: 'to do / make', hint: 'ah-SEHR', status: 'active' },
    { es: 'el trabajo', en: 'work / the job', hint: 'el trah-BAH-hoh', status: 'active' },
  ];
  const one = (o, es) => validateSwaps(1, [{ o, es }], words)[0] || null;
  expect(one('a little', 'un poco').es).toBe('un poco'); // never "poco" (not much)
  expect(one('once', 'una vez').es).toBe('una vez');
  expect(one('once', 'una vez').gn).toBeUndefined(); // a phrase, not a noun
  const morning = one('morning', 'la mañana');
  expect([morning.es, morning.word, morning.g, morning.gn]).toEqual(['mañana', 'la mañana', 'morning', 'f']); // still "the morning", not "tomorrow"
  expect(one('a problem', 'el cambio')).toBeNull();
  expect(one('changed', 'el cambio')).toBeNull(); // a verb form is not a noun's gloss
  expect(one('to work', 'el trabajo')).toBeNull();
  expect(one('little', 'un poco')).toBeNull();
  expect(one('works', 'funciona').es).toBe('funciona');
  expect(one("I'm", 'soy').es).toBe('soy');
  expect(one('makes', 'hacer').es).toBe('hacer'); // every sense of a "to ..." gloss is a verb
  expect(glossMatch('stopped', 'to stop')).toBe('inflected');
  expect(glossMatch('studied', 'to study')).toBe('inflected');
  expect(glossMatch('looking for', 'to look for')).toBe('inflected');
  expect(glossMatch("isn't", "it isn't (what something isn't)")).toBe('exact');
});

it('a passage dropped because its element left the page forgets the element, so it is read again when it comes back', () => {
  const gone = { isConnected: false, getBoundingClientRect: () => ({ top: 0, bottom: 10 }) };
  const pending = new Map([['k', { text: 'k', els: new Set([gone]) }]]);
  const forgotten = [];
  expect(pickBatch(pending, new Set(), () => 'k', 800, 8, (el) => forgotten.push(el))).toEqual([]);
  expect(forgotten).toEqual([gone]);
});

it('shortened gloss forms never leave a lone function word, and set phrases take no verb endings (0.3.3 verification)', () => {
  const words = ['para que,so that', "se puede,you can / it's possible", 'no es,it isn\'t (what something isn\'t)',
    'pequeño,small', 'es decir,that is (to say)', 'a decir verdad,to tell the truth', 'encima,on top / on top of that',
    'algo así,something like that', 'vale la pena,it\'s worth it', 'creo que,I think that', 'parece que,it seems that',
    'ir,to go', 'no funciona,it doesn\'t work', 'es,it\'s / is (what something is)', "por eso,that's why"]
    .map((line) => { const [es, en] = line.split(/,(.+)/); return { es, en, hint: 'x', status: 'active' }; });
  const kept = (o, es) => validateSwaps(2, [{ o, es }], words).length === 1;
  for (const [o, es] of [['So', 'para que'], ['therefore', 'para que'], ['not', 'no es'], ['possible', 'se puede'],
    ['a little', 'pequeño'], ["That's", 'es decir'], ['tells the truth', 'a decir verdad'], ['on top of', 'encima']]) {
    expect([o, es, kept(o, es)]).toEqual([o, es, false]);
  }
  for (const [o, es] of [['worth it', 'vale la pena'], ['I think', 'creo que'], ['it seems', 'parece que'], ['goes', 'ir'],
    ['going', 'ir'], ["doesn't work", 'no funciona'], ["it's", 'es'], ["isn't", 'no es'], ['so that', 'para que'], ['tiny', 'pequeño'],
    ['That is why', 'por eso'], ["That's why", 'por eso']]) {
    expect([o, es, kept(o, es)]).toEqual([o, es, true]);
  }
});
