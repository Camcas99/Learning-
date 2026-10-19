import { describe, test, expect } from 'bun:test';
import { readFileSync } from 'node:fs';
import { Window } from 'happy-dom';
import { selector, readable, textRoot, siteFor, INSTAGRAM, TWEET, PROSE } from '../src/page.js';
import { applySwaps, flatten } from '../src/text.js';
import { FEED, PROFILE } from './instagram-fixture.js';

const win = new Window();
const document = win.document;
const IG = 'https://www.instagram.com/';
const page = (html) => { document.body.innerHTML = html; return document.body; };
// What content.js would track on url: the selector's matches that pass readable().
const accepted = (url) => [...document.querySelectorAll(selector(url))].filter((el) => readable(el, url)).map((el) => el.id || el.textContent);
const S = (swap) => ({ g: 'x', h: '', ctx: '', ...swap });

describe('site adapters', () => {
  test('instagram.com and www.instagram.com read captions, comments and bios; X keeps tweets; the rest reads prose', () => {
    for (const url of [IG, 'https://instagram.com/p/C0ffee/', 'https://www.instagram.com/sofia.travels/']) expect(selector(url)).toBe(INSTAGRAM);
    for (const url of ['https://x.com/home', 'https://twitter.com/someone', 'https://www.x.com/']) expect(selector(url)).toBe(TWEET);
    for (const url of ['https://example.com/', 'https://notinstagram.com/', 'https://instagram.com.evil.example/', 'https://about.instagram.com/blog'])
      expect(selector(url)).toBe(PROSE);
  });
  test('every site in the manifest has an adapter', () => {
    const manifest = JSON.parse(readFileSync(new URL('../manifest.json', import.meta.url), 'utf8'));
    const statics = manifest.content_scripts.flatMap((c) => c.matches);
    expect(statics).toEqual(expect.arrayContaining(['https://x.com/*', 'https://twitter.com/*', 'https://www.instagram.com/*', 'https://instagram.com/*']));
    for (const m of statics) expect(siteFor(m.replace('*', 'home'))).not.toBeNull();
  });
});

describe('Instagram', () => {
  test('feed: the caption and the long comment, never usernames, buttons, short or health comments, or a nested span', () => {
    page(FEED);
    expect(accepted(IG)).toEqual(['caption', 'comment-long']);
    const nested = document.getElementById('nested');
    expect(flatten(nested).text.split(' ').length).toBeGreaterThanOrEqual(6); // long enough: only the outer caption excludes it
    expect(readable(nested, IG)).toBe(false);
  });
  test('profile: the bio, though Instagram puts it in <header>', () => {
    page(PROFILE);
    expect(accepted('https://www.instagram.com/sofia.travels/')).toEqual(['bio']);
  });
  test('every other guard still applies', () => {
    const text = 'We walked along the quiet beach and watched the boats come home';
    const cases = {
      link: `<a href="/x/"><span dir="auto">${text}</span></a>`,
      button: `<button><span dir="auto">${text}</span></button>`,
      roleButton: `<div role="button"><span dir="auto">${text}</span></div>`,
      form: `<form><span dir="auto">${text}</span></form>`,
      editable: `<div contenteditable="true"><span dir="auto">${text}</span></div>`,
      hidden: `<div hidden><span dir="auto">${text}</span></div>`,
      ariaHidden: `<div aria-hidden="true"><span dir="auto">${text}</span></div>`,
      spanish: `<div lang="es"><span dir="auto">${text}</span></div>`,
      nav: `<nav><span dir="auto">${text}</span></nav>`,
      footer: `<footer><span dir="auto">${text}</span></footer>`,
      short: '<span dir="auto">So pretty and calm!</span>',
      long: `<span dir="auto">${'and so on '.repeat(250)}</span>`,
      health: '<span dir="auto">My doctor changed my medication again and I feel better today</span>',
    };
    for (const [name, html] of Object.entries(cases)) {
      page(html);
      expect([name, accepted(IG)]).toEqual([name, []]);
    }
    page(`<span dir="auto" id="ok">${text}</span>`);
    expect(accepted(IG)).toEqual(['ok']);
    for (const path of ['accounts/login/', 'accounts/edit/', 'accounts/password/change/']) expect(accepted(IG + path)).toEqual([]);
  });
  test('direct messages never leave the page', () => {
    page('<span dir="auto" id="dm">Can you send me the new address and the door code before tonight</span>');
    expect(accepted(IG)).toEqual(['dm']); // the same text in a caption would be read
    for (const path of ['direct/inbox/', 'direct/t/1234567890/', 'direct', 'direct/requests/']) expect(accepted(IG + path)).toEqual([]);
    expect(accepted(IG + 'directions.travel/')).toEqual(['dm']); // a profile whose name starts with "direct"
  });
  test('an edit inside a nested span belongs to the outer caption', () => {
    page(FEED);
    const caption = document.getElementById('caption');
    expect(textRoot(document.getElementById('nested'), IG)).toBe(caption);
    expect(textRoot(caption, IG)).toBe(caption);
    expect(textRoot(document.getElementById('post'), IG)).toBeNull();
  });
  test('swaps never touch usernames, hashtags or mentions', () => {
    page(FEED + PROFILE);
    const links = () => [...document.querySelectorAll('a')].map((a) => a.textContent);
    const before = links();
    const caption = document.getElementById('caption');
    const bio = document.getElementById('bio');
    const linked = ['#travel', 'travel', '@marco.eats', 'marco.eats', 'eats'].map((o) => S({ o, es: 'y' }));
    expect(applySwaps(caption, [...linked, S({ o: 'and', es: 'y', ctx: 'coast and the' }), S({ o: 'house', es: 'casa', gn: 'f', ctx: 'the house until' })])).toBe(2);
    expect(applySwaps(bio, [...linked.slice(2), S({ o: 'and', es: 'y', ctx: 'my dog and post' })])).toBe(1);
    expect(links()).toEqual(before);
    expect(caption.textContent.replace(/\s+/g, ' ').trim()).toBe('We finally reached the coast y the water was very warm, so we stayed by the casa until the light was gone #travel with @marco.eats');
  });
});

describe('X and other sites keep their rules', () => {
  test('a tweet reads as one passage; site chrome and prose containers still count elsewhere', () => {
    page('<header><div data-testid="tweetText" id="banner">We shipped the new search page and it is fast</div></header>' +
      '<main><div data-testid="tweetText" id="t1"><span>We shipped the new search page and it is fast</span></div></main>');
    expect(accepted('https://x.com/home')).toEqual(['t1']);
    page('<main><article id="a"><p id="p">We walked along the quiet beach and watched the boats come home</p></article></main>');
    expect(accepted('https://example.com/post')).toEqual(['p']);
    expect(textRoot(document.getElementById('p'), 'https://example.com/post').id).toBe('p');
    page('<header><p id="h">We walked along the quiet beach and watched the boats come home</p></header>');
    expect(accepted('https://example.com/post')).toEqual([]);
  });
  test('direct messages on X and message pages elsewhere are never read', () => {
    page('<main><div data-testid="tweetText" id="dm"><span>Can you send me the new address and the door code before tonight</span></div></main>');
    expect(accepted('https://x.com/home')).toEqual(['dm']); // the same text as a post is read
    for (const url of ['https://x.com/messages/1', 'https://x.com/messages', 'https://x.com/i/chat/1', 'https://twitter.com/messages/12-34'])
      expect([url, accepted(url)]).toEqual([url, []]);
    page('<main><p id="p">Can you send me the new address and the door code before tonight</p></main>');
    for (const url of ['https://www.linkedin.com/messaging/thread/1/', 'https://www.facebook.com/messages/t/1', 'https://example.com/inbox',
      'https://forum.example/chat/room-1', 'https://forum.example/dms/42', 'https://example.com/direct/9'])
      expect([url, accepted(url)]).toEqual([url, []]);
    for (const url of ['https://example.com/blog/inbox-zero-tips', 'https://example.com/chatting-with-friends', 'https://example.com/directions'])
      expect([url, accepted(url)]).toEqual([url, ['p']]);
  });
});
