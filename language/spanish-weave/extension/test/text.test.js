import { describe, test, expect } from 'bun:test';
import { readFileSync } from 'node:fs';
import { Window } from 'happy-dom';
import { flatten, locate, applySwaps, revert, toggle, tipFor } from '../src/text.js';

const win = new Window();
const document = win.document;

// Markup shapes copied from x.com on 2026-09-20.
function tweet(inner) {
  const wrap = document.createElement('div');
  wrap.innerHTML = `<div dir="auto" lang="en" data-testid="tweetText">${inner}</div>`;
  return wrap.firstElementChild;
}
const S = (swap) => ({ g: swap.g || 'and', h: swap.h || 'ee', ctx: '', ...swap });

describe('flatten', () => {
  test('collapses whitespace and keeps a map back to raw offsets', () => {
    const el = tweet('<span>one\n\ntwo  three</span>');
    const f = flatten(el);
    expect(f.text).toBe('one two three');
    expect(f.raw).toBe('one\n\ntwo  three');
    expect(f.raw.slice(f.map[4], f.map[6] + 1)).toBe('two');
  });
  test('emoji alt text and link text are in the text but not touchable', () => {
    const el = tweet('<span>fire </span><img alt="🔥"><span> and </span><a href="https://t.co/x"><span>https://</span>bit.ly/abc</a>');
    const f = flatten(el);
    expect(f.text).toBe('fire 🔥 and https://bit.ly/abc');
    expect(f.segs.filter((s) => s.ok).length).toBe(2);
    expect(f.segs.filter((s) => !s.ok).length).toBe(3);
  });
  test('trims ends', () => {
    expect(flatten(tweet('<span>  hi there  </span>')).text).toBe('hi there');
  });
});

describe('locate', () => {
  test('ctx disambiguates repeated words', () => {
    const f = flatten(tweet('<span>cats and dogs and birds</span>'));
    expect(locate(f, 'and', 'cats and dogs')).toEqual({ start: 5, end: 8 });
    expect(locate(f, 'and', 'dogs and birds')).toEqual({ start: 14, end: 17 });
    expect(locate(f, 'and', '')).toBeNull();
    expect(locate(f, 'and', 'no such context')).toBeNull();
  });
  test('word boundaries: "and" never matches inside "brand"', () => {
    const f = flatten(tweet('<span>brand new and shiny</span>'));
    expect(locate(f, 'and', '')).toEqual({ start: 10, end: 13 });
    expect(locate(f, 'and', 'brand new')).toEqual({ start: 10, end: 13 }); // ctx has no whole-word "and" -> whole-text fallback
    expect(locate(flatten(tweet('<span>brand new</span>')), 'and', '')).toBeNull();
  });
  test('phrases and punctuation neighbours', () => {
    const f = flatten(tweet('<span>late, because I slept.</span>'));
    expect(locate(f, 'because', 'late, because I')).toEqual({ start: 6, end: 13 });
    const g = flatten(tweet('<span>this is a little odd</span>'));
    expect(locate(g, 'a little', '')).toEqual({ start: 8, end: 16 });
  });
});

describe('applySwaps', () => {
  test('wraps exactly the word, leaves the rest untouched', () => {
    const el = tweet('<span>cats and dogs and birds</span>');
    const n = applySwaps(el, [S({ o: 'and', es: 'y', ctx: 'dogs and birds' })]);
    expect(n).toBe(1);
    expect(el.innerHTML).toBe('<span>cats and dogs <span class="sw-word" data-en="and" data-es="y" data-tip="and · &quot;ee&quot;" data-sw-split="1" tabindex="0" role="button" aria-label="y: and. Show English">y</span> birds</span>');
    expect(el.textContent).toBe('cats and dogs y birds');
  });
  test('two swaps in one text node, applied in any order', () => {
    const el = tweet('<span>cats and dogs and birds</span>');
    const n = applySwaps(el, [
      S({ o: 'and', es: 'y', ctx: 'cats and dogs' }),
      S({ o: 'and', es: 'y', ctx: 'dogs and birds' }),
    ]);
    expect(n).toBe(2);
    expect(el.textContent).toBe('cats y dogs y birds');
    expect(el.querySelectorAll('.sw-word').length).toBe(2);
  });
  test('mentions: ctx may straddle the link, the swap lands in plain text, handles are never touched', () => {
    const el = tweet('<span>thanks </span><div><span><a href="/foo">@foo</a></span></div><span> and you too friend</span>');
    const n = applySwaps(el, [
      S({ o: 'and', es: 'y', ctx: '@foo and you' }),
      S({ o: '@foo', es: 'y', ctx: 'thanks @foo and' }),
    ]);
    expect(n).toBe(1);
    expect(el.querySelector('a').textContent).toBe('@foo');
    expect(el.textContent).toBe('thanks @foo y you too friend');
  });
  test('emoji alt in ctx, link text never swapped', () => {
    const el = tweet('<span>fire </span><img alt="🔥"><span> and ice </span><a href="https://t.co/x"><span>https://</span>bit.ly/and</a>');
    const n = applySwaps(el, [
      S({ o: 'and', es: 'y', ctx: '🔥 and ice' }),
      S({ o: 'bit.ly/and', es: 'y', ctx: 'https://bit.ly/and' }),
    ]);
    expect(n).toBe(1);
    expect(el.querySelector('a').textContent).toBe('https://bit.ly/and');
    expect(el.textContent).toBe('fire  y ice https://bit.ly/and');
  });
  test('code is never touched', () => {
    const el = tweet('<span>run </span><code>git rebase and squash</code><span> and ship</span>');
    const n = applySwaps(el, [S({ o: 'and', es: 'y', ctx: 'and ship' })]);
    expect(n).toBe(1);
    expect(el.querySelector('code').textContent).toBe('git rebase and squash');
  });
  test('swap spanning two nodes is dropped; newline inside the phrase is dropped', () => {
    const el = tweet('<span>a </span><span>little</span><span> odd and fun</span>');
    expect(applySwaps(el, [S({ o: 'a little', es: 'un poco', ctx: 'a little odd' })])).toBe(0);
    const el2 = tweet('<span>this is a\nlittle odd and fun</span>');
    expect(applySwaps(el2, [S({ o: 'a little', es: 'un poco', ctx: 'a little odd' })])).toBe(0);
    expect(el2.textContent).toBe('this is a\nlittle odd and fun');
  });
  test('newlines in the node survive a swap elsewhere in it', () => {
    const el = tweet('<span>one\n\ntwo and three</span>');
    applySwaps(el, [S({ o: 'and', es: 'y', ctx: 'two and three' })]);
    expect(el.textContent).toBe('one\n\ntwo y three');
  });
  test('overlapping swaps: first wins', () => {
    const el = tweet('<span>not because of that, honestly</span>');
    const n = applySwaps(el, [
      S({ o: 'because', es: 'porque', ctx: 'not because of' }),
      S({ o: 'because of', es: 'porque', ctx: 'because of that' }),
    ]);
    expect(n).toBe(1);
    expect(el.textContent).toBe('not porque of that, honestly');
  });
  test('missing or ambiguous anchors are dropped, nothing else changes', () => {
    const el = tweet('<span>cats and dogs and birds</span>');
    const before = el.innerHTML;
    expect(applySwaps(el, [S({ o: 'and', es: 'y', ctx: '' }), S({ o: 'zebra', es: 'y', ctx: 'zebra' })])).toBe(0);
    expect(el.innerHTML).toBe(before);
  });
  test('tip without hint is just the gloss', () => {
    expect(tipFor({ g: 'and', h: '' })).toBe('and');
    expect(tipFor({ g: 'and', h: 'ee' })).toBe('and · "ee"');
  });
  test('tip: gloss, gender, sound hint, then a usage note', () => {
    expect(tipFor({ g: 'long', h: 'LAHR-goh', n: "not 'large' (that's grande)" })).toBe(`long · "LAHR-goh" · not 'large' (that's grande)`);
    expect(tipFor({ g: 'success', h: 'EK-see-toh', gn: 'm', n: "not 'exit' (that's la salida)" }))
      .toBe(`success · masc. · "EK-see-toh" · not 'exit' (that's la salida)`);
    expect(tipFor({ g: 'house', h: '', gn: 'f' })).toBe('house · fem.');
    expect(tipFor({ g: 'and', h: 'ee', gn: 'x' })).toBe('and · "ee"');
  });
});

describe('noun gender', () => {
  const nouns = [
    S({ o: 'house', es: 'casa', g: 'house', h: 'KAH-sah', gn: 'f', ctx: 'the house and' }),
    S({ o: 'day', es: 'día', g: 'day', h: 'DEE-ah', gn: 'm', ctx: 'the day' }),
    S({ o: 'and', es: 'y', ctx: 'house and the' }),
  ];
  test('a noun swap carries data-sw-gender and says masc. or fem. in the tooltip and its label', () => {
    const el = tweet('<span>the house and the day</span>');
    expect(applySwaps(el, nouns)).toBe(3);
    const [casa, y, dia] = el.querySelectorAll('.sw-word');
    expect(casa.getAttribute('data-sw-gender')).toBe('f');
    expect(casa.getAttribute('data-tip')).toBe('house · fem. · "KAH-sah"');
    expect(casa.getAttribute('aria-label')).toBe('casa: house, feminine. Show English');
    expect(dia.getAttribute('data-sw-gender')).toBe('m');
    expect(dia.getAttribute('data-tip')).toBe('day · masc. · "DEE-ah"');
    expect(y.hasAttribute('data-sw-gender')).toBe(false);
    expect(y.getAttribute('data-tip')).toBe('and · "ee"');
  });
  test('with gender colors off: no attribute, so no color, and no label', () => {
    const el = tweet('<span>the house and the day</span>');
    applySwaps(el, nouns, { gender: false });
    for (const span of el.querySelectorAll('.sw-word')) {
      expect(span.hasAttribute('data-sw-gender')).toBe(false);
      expect(span.getAttribute('data-tip')).not.toMatch(/masc|fem/);
      expect(span.getAttribute('aria-label')).not.toMatch(/masculine|feminine/);
    }
    expect(nouns[0].gn).toBe('f'); // the cached swap itself is untouched
  });
  test('only m and f become an attribute', () => {
    const el = tweet('<span>the house and more</span>');
    applySwaps(el, [S({ o: 'house', es: 'casa', gn: 'constructor', ctx: 'the house' })]);
    expect(el.querySelector('.sw-word').hasAttribute('data-sw-gender')).toBe(false);
  });
});

describe('content.css', () => {
  const css = readFileSync(new URL('../src/content.css', import.meta.url), 'utf8');
  test('swaps reveal with a short blur-and-fade keyframe that never changes text, off for reduced motion', () => {
    const keyframes = /@keyframes sw-reveal\s*\{([\s\S]*?\})\s*\}/.exec(css)?.[1] || '';
    expect(keyframes).toMatch(/opacity/);
    expect(keyframes).toMatch(/blur/);
    expect(keyframes).not.toMatch(/content\s*:/);
    // Only a first appearance (.sw-new) animates; a plain .sw-word never does, so repaints stay still.
    expect(/\.sw-word\s*\{[^}]*animation/.test(css)).toBe(false);
    const duration = Number(/\.sw-word\.sw-new\s*\{[^}]*animation:\s*sw-reveal\s+(\d+)ms/.exec(css)?.[1]);
    expect(duration).toBeGreaterThanOrEqual(400);
    expect(duration).toBeLessThanOrEqual(600);
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.sw-word\.sw-new\s*\{\s*animation:\s*none;?\s*\}/);
  });
  test('masculine and feminine nouns get different underline colors', () => {
    const color = (g) => new RegExp(`\\.sw-word\\[data-sw-gender="${g}"\\]\\s*\\{\\s*text-decoration-color:\\s*([^;]+);`).exec(css)?.[1];
    expect(color('m')).toBeTruthy();
    expect(color('f')).toBeTruthy();
    expect(color('m')).not.toBe(color('f'));
    const known = (g) => new RegExp(`\\.sw-word\\[data-sw-status="known"\\]\\[data-sw-gender="${g}"\\]\\s*\\{\\s*text-decoration-color:\\s*([^;]+);`).exec(css)?.[1];
    for (const g of ['m', 'f']) {
      expect(known(g)).toBeTruthy();
      expect(known(g)).not.toBe(color(g)); // known nouns fade, so learning ones stand out
    }
  });
});

describe('revert and toggle', () => {
  test('a framework replacing its original text node does not regain stale split suffixes', () => {
    const el = tweet('<span>cats and dogs and birds</span>');
    const original = el.querySelector('span').firstChild;
    applySwaps(el, [S({ o: 'and', es: 'y', ctx: 'cats and dogs' }), S({ o: 'and', es: 'y', ctx: 'dogs and birds' })]);
    original.data = 'A newly edited sentence with completely different words.';
    revert(el);
    expect(el.textContent).toBe('A newly edited sentence with completely different words.');
    expect(el.querySelector('span').firstChild).toBe(original);
    expect(el.querySelector('span').childNodes.length).toBe(1);
  });
  test('revert restores the original DOM and the same text node object', () => {
    const el = tweet('<span>cats and dogs and birds</span>');
    const original = el.querySelector('span').firstChild;
    const before = el.innerHTML;
    applySwaps(el, [
      S({ o: 'and', es: 'y', ctx: 'cats and dogs' }),
      S({ o: 'and', es: 'y', ctx: 'dogs and birds' }),
    ]);
    expect(el.querySelectorAll('.sw-word').length).toBe(2);
    expect(revert(el)).toBe(2);
    expect(el.innerHTML).toBe(before);
    expect(el.querySelector('span').firstChild).toBe(original);
    expect(el.querySelector('span').childNodes.length).toBe(1);
    expect(revert(el)).toBe(0);
  });
  test('revert after a swap at offset 0 and at the very end', () => {
    const el = tweet('<span>and then and</span>');
    const before = el.innerHTML;
    applySwaps(el, [S({ o: 'and', es: 'y', ctx: 'and then' }), S({ o: 'and', es: 'y', ctx: 'then and' })]);
    expect(el.textContent).toBe('y then y');
    revert(el);
    expect(el.innerHTML).toBe(before);
  });
  test('apply again after revert gives the same result', () => {
    const el = tweet('<span>cats and dogs</span>');
    const swaps = [S({ o: 'and', es: 'y', ctx: 'cats and dogs' })];
    applySwaps(el, swaps);
    const first = el.innerHTML;
    revert(el);
    applySwaps(el, swaps);
    expect(el.innerHTML).toBe(first);
  });
  test('toggle flips between Spanish and English, underline span stays', () => {
    const el = tweet('<span>cats and dogs</span>');
    applySwaps(el, [S({ o: 'And', es: 'Y', ctx: 'cats And' }), S({ o: 'and', es: 'y', ctx: 'cats and dogs' })]);
    const span = el.querySelector('.sw-word');
    expect(span.textContent).toBe('y');
    expect(toggle(span)).toBe(true);
    expect(span.textContent).toBe('and');
    expect(span.classList.contains('sw-en')).toBe(true);
    expect(toggle(span)).toBe(false);
    expect(span.textContent).toBe('y');
    expect(el.querySelectorAll('.sw-word').length).toBe(1);
  });
});
