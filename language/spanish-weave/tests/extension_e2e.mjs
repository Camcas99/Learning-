// End-to-end extension check (needs `npm i playwright && npx playwright install chromium`; Google Chrome ignores
// --load-extension, so this uses Playwright's Chromium). Run setup first, registering the profile dir used here:
//   python3 scripts/sw.py setup --user-data-dir /tmp/sw-profile [--gemini-key-file KEY]
//   PROFILE=/tmp/sw-profile node tests/extension_e2e.mjs
// To leave your own setup alone, give both commands a scratch SPANISH_WEAVE_HOME (and setup a scratch HOME, so
// it writes no host manifest into your real browsers).
// Loads a temporary copy of ~/.spanish-weave/extension (or $SPANISH_WEAVE_HOME/extension) with website access
// granted up front, since Chrome's grant dialog can't be clicked from a script. Serves a fake x.com timeline, a
// fake Instagram feed and profile, and a fake article on another site (synthetic text), and prints what happened:
// native host sync, real Gemini swaps (a few requests), delayed hover tip, Alt+click speaking instead of flipping,
// click flip, health text untouched, links and forms intact, Instagram captions, comments and bio swapped once
// (usernames, hashtags, buttons and nested caption spans untouched), seen/flip events flushed back to the word
// state, forged page events ignored, no swaps on webmail, and the article reverting when its site is turned off.
import { chromium } from 'playwright';
import { homedir, tmpdir } from 'node:os';
import { join } from 'node:path';
import { cpSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { FEED as IG_FEED, PROFILE as IG_PROFILE } from '../extension/test/instagram-fixture.js';

const INSTALLED = join(process.env.SPANISH_WEAVE_HOME || join(homedir(), '.spanish-weave'), 'extension');
const EXT = mkdtempSync(join(tmpdir(), 'sw-ext-'));
cpSync(INSTALLED, EXT, { recursive: true });
const manifest = JSON.parse(readFileSync(join(EXT, 'manifest.json'), 'utf8'));
manifest.host_permissions.push(...manifest.optional_host_permissions); // same key, so the same extension ID
writeFileSync(join(EXT, 'manifest.json'), JSON.stringify(manifest));
const tweets = [
  ['t1', 'en', 'Finally shipped the new search page and it is very fast now, but the old filters still need work.'],
  ['t2', 'en', 'I always forget my umbrella, so of course it rained again today and I got soaked without one.'],
  ['t3', 'en', 'Maybe the best part of the weekend was cooking with friends and trying a new recipe together.'],
  ['t4', 'en', 'Went to the doctor about the migraine medication and the symptoms are still there, ugh.'],
  ['t5', 'en', 'Reading <a href="/someone">@someone</a> and their thread about compilers, also very good, check <a href="https://t.co/abc"><span>https://</span>example.com</a> now'],
];
const html = `<!doctype html><html><head><meta charset="utf-8"><title>Home / X</title></head><body><main>${tweets
  .map(([id, lang, t]) => `<article data-testid="tweet" id="${id}"><div lang="${lang}" dir="auto" data-testid="tweetText"><span>${t}</span></div></article>`)
  .join('\n')}</main></body></html>`;
// Instagram pages from the extension's test fixture: modeled on instagram.com's markup, which changes often.
const instagram = (title, body) => `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${title}</title></head><body>${body}</body></html>`;

const ARTICLE_URL = 'https://reading.example/2026/10/notes';
const article = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Notes</title></head><body>
<header><nav><a href="/">Home</a> and <a href="/about">About</a></nav></header>
<main><article>
<h1>What I learned from a slow week</h1>
<p id="a1">The garden was very quiet this week, and I finally read the book my friend gave me last year.</p>
<p id="a2">Maybe the best part was walking home every evening without my phone, because the light was always so warm.</p>
<p id="a3">My doctor changed the dose of my medication, and the side effects are still there, so I am resting.</p>
<p id="a4">We also cooked a big dinner together now that the kitchen is finally fixed, and it was a lot of fun.</p>
<form><p id="a5">Write your comment here and tell us what you think about the article today.</p><textarea></textarea></form>
</article></main></body></html>`;

const userDataDir = process.env.PROFILE || mkdtempSync(join(tmpdir(), 'sw-profile-'));
const ctx = await chromium.launchPersistentContext(userDataDir, {
  channel: 'chromium', // the default headless shell cannot load extensions
  headless: true,
  args: ['--headless=new', `--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`],
});
const out = {};
try {
  let [sw] = ctx.serviceWorkers();
  if (!sw) sw = await ctx.waitForEvent('serviceworker', { timeout: 20000 });
  out.extensionId = sw.url().split('/')[2];
  for (let i = 0; i < 40 && !(await sw.evaluate(() => !!globalThis.chrome?.storage)); i++) await new Promise((r) => setTimeout(r, 250));
  // Wait for the install-time sync from the native host.
  let state = {};
  for (let i = 0; i < 40 && !state.wordState; i++) {
    state = await sw.evaluate(() => chrome.storage.local.get(['wordState', 'hostKey']));
    if (!state.wordState) await new Promise((r) => setTimeout(r, 500));
  }
  out.synced = state.wordState ? { stage: state.wordState.stage, words: state.wordState.words.map((w) => w.es), version: state.wordState.version } : null;
  out.hostKeyFromSetup = !!state.hostKey;

  await ctx.route('https://x.com/**', (route) => route.fulfill({ status: 200, contentType: 'text/html', body: html }));
  const page = await ctx.newPage();
  page.on('console', (m) => { if (/spanish-weave/.test(m.text())) (out.console ||= []).push(m.text()); });
  await page.goto('https://x.com/home');
  await page.waitForSelector('.sw-word', { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(3000);
  out.swaps = await page.$$eval('.sw-word', (els) => els.map((e) => ({ tweet: e.closest('article').id, es: e.dataset.es, en: e.dataset.en, tip: e.dataset.tip })));
  out.healthTouched = await page.$$eval('#t4 .sw-word', (els) => els.length);
  out.linksIntact = await page.$eval('#t5', (el) => [...el.querySelectorAll('a')].map((a) => a.textContent));
  out.texts = await page.$$eval('[data-testid=tweetText]', (els) => els.map((e) => e.textContent));
  if (out.swaps.length) {
    const first = page.locator('.sw-word').first();
    await first.hover();
    await page.waitForTimeout(1000); // the gloss shows after a short dwell, which also counts as a peek
    out.hoverAfter = await first.evaluate((e) => getComputedStyle(e, '::after').content);
    await first.click({ modifiers: ['Alt'] }); // speaks the word (if Chromium has a voice) instead of flipping it; no event
    out.afterAltClick = await first.evaluate((e) => ({ text: e.textContent, english: e.classList.contains('sw-en') }));
    await first.click();
    out.afterClick = await first.evaluate((e) => ({ text: e.textContent, english: e.classList.contains('sw-en') }));
    await first.click();
    out.afterSecondClick = await first.textContent();
    await first.click(); // leave it flipped to English: one flip event
    // Events: seen + flip are queued, then flushed to the host after ~10 s.
    await page.waitForTimeout(13000);
    out.pendingAfterFlush = await sw.evaluate(() => chrome.storage.local.get('pendingEvents').then((o) => o.pendingEvents));
    out.identifyingAttrs = await page.$$eval('[data-sw-key],[data-sw-word]', (els) => els.length);
    // The page itself can't forge events: synthetic clicks and hovers, on a real swap or on its own sw-word span.
    out.forged = await page.evaluate(async () => {
      const real = document.querySelector('.sw-word');
      const before = real.textContent;
      const fake = Object.assign(document.createElement('span'), { className: 'sw-word', textContent: 'muy' });
      fake.dataset.swWord = 'muy';
      document.querySelector('main').append(fake);
      for (const el of [real, fake]) {
        el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
        el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      }
      await new Promise((r) => setTimeout(r, 1500));
      return { realUnchanged: real.textContent === before, fakeUnchanged: fake.textContent === 'muy' };
    });
    out.forged.pending = await sw.evaluate(() => chrome.storage.local.get('pendingEvents').then((o) => o.pendingEvents || []));
  }
  // Instagram is in the manifest too: a feed post (the caption nests another span[dir=auto]) and a profile bio,
  // which Instagram puts in <header>.
  await ctx.route('https://www.instagram.com/**', (route) => route.fulfill({ status: 200, contentType: 'text/html',
    body: new URL(route.request().url()).pathname === '/' ? instagram('Instagram', IG_FEED) : instagram('Sofia (@sofia.travels) • Instagram', IG_PROFILE) }));
  const ig = await ctx.newPage();
  ig.on('console', (m) => { if (/spanish-weave/.test(m.text())) (out.console ||= []).push(m.text()); });
  const igState = () => ig.evaluate(() => ({
    swaps: [...document.querySelectorAll('.sw-word')].map((e) => ({ in: e.closest('[id]')?.id || e.parentElement.tagName, es: e.dataset.es, en: e.dataset.en, gender: e.dataset.swGender || '', tip: e.dataset.tip })),
    links: [...document.querySelectorAll('a')].map((a) => a.textContent),
    nestedSwaps: document.querySelectorAll('.sw-word .sw-word').length,
    wronglySwapped: ['author', 'follow', 'more', 'comment-short', 'comment-health'].filter((id) => document.querySelector(`#${id} .sw-word`)),
  }));
  await ig.goto('https://www.instagram.com/');
  await ig.waitForSelector('.sw-word', { timeout: 60000 }).catch(() => {});
  await ig.waitForTimeout(3000);
  out.instagramFeed = await igState();
  await ig.goto('https://www.instagram.com/sofia.travels/');
  await ig.waitForSelector('.sw-word', { timeout: 60000 }).catch(() => {});
  await ig.waitForTimeout(3000);
  out.instagramProfile = await igState();
  // A plain article on another site: the dynamically registered content script runs there too.
  for (let i = 0; i < 40; i++) {
    const ids = await sw.evaluate(() => chrome.scripting.getRegisteredContentScripts().then((s) => s.map((x) => x.id)));
    if (ids.includes('weave-sites')) break;
    await new Promise((r) => setTimeout(r, 250));
  }
  await ctx.route('https://reading.example/**', (route) => route.fulfill({ status: 200, contentType: 'text/html', body: article }));
  const reading = await ctx.newPage();
  reading.on('console', (m) => { if (/spanish-weave/.test(m.text())) (out.console ||= []).push(m.text()); });
  await reading.goto(ARTICLE_URL);
  await reading.waitForSelector('.sw-word', { timeout: 60000 }).catch(() => {});
  await reading.waitForTimeout(3000);
  out.articleSwaps = await reading.$$eval('.sw-word', (els) => els.map((e) => ({ p: e.closest('[id]')?.id || e.parentElement.tagName, es: e.dataset.es, en: e.dataset.en })));
  out.articleHealthTouched = await reading.$$eval('#a3 .sw-word', (els) => els.length);
  out.articleFormTouched = await reading.$$eval('form .sw-word', (els) => els.length);
  out.articleNavIntact = await reading.$eval('nav', (n) => n.textContent);

  // Webmail starts off even with every site on: no swaps, so no page text sent.
  await ctx.route('https://mail.google.com/**', (route) => route.fulfill({ status: 200, contentType: 'text/html', body: article }));
  const calls = () => sw.evaluate(() => chrome.storage.local.get('modelCalls').then((o) => o.modelCalls?.count || 0));
  const callsBeforeMail = await calls();
  const mail = await ctx.newPage();
  await mail.goto('https://mail.google.com/mail/u/0/');
  await mail.waitForTimeout(8000);
  out.mailSwaps = await mail.$$eval('.sw-word', (els) => els.length);
  out.mailModelCalls = (await calls()) - callsBeforeMail;

  const popup = await ctx.newPage();
  await popup.goto(`chrome-extension://${out.extensionId}/src/popup.html`);
  await popup.waitForTimeout(1500);
  out.popup = await popup.$eval('body', (b) => b.innerText);
  // Turning the site off from the popup reverts the open article.
  await popup.evaluate(() => chrome.runtime.sendMessage({ type: 'save', siteOverride: { host: 'reading.example', enabled: false } }));
  await reading.waitForTimeout(1500);
  out.articleSwapsAfterSiteOff = await reading.$$eval('.sw-word', (els) => els.length);
  out.articleTextAfterSiteOff = await reading.$eval('#a1', (e) => e.textContent);
} finally {
  await ctx.close();
}
console.log(JSON.stringify(out, null, 1));
