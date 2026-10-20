// Improvements ported from French Weave (Jackie Oliver, MIT) in 0.3.2.
import { expect, it } from 'bun:test';
import { offByDefault, siteOn } from '../src/settings.js';
import { locate } from '../src/text.js';
import { allCaps, matchCase } from '../src/levels.js';
import { createCache, memoryStorage, CACHE_MAX_AGE_MS } from '../src/cache.js';
import { TWEET } from '../src/page.js';

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
