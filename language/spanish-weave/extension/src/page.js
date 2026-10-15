import { isZeroSpanish, wordCount } from './levels.js';
import { flatten } from './text.js';

export const TWEET = '[data-testid="tweetText"]';
// Instagram captions, comments and profile bios. A caption span can hold more span[dir=auto] inside it.
export const INSTAGRAM = 'h1[dir="auto"],span[dir="auto"]';
export const PROSE = 'p,li,blockquote,h1,h2,h3,h4,article,main';
// Site adapters, first hostname match wins; every other site reads PROSE. sel holds a post's own text, so the
// "contains other prose" rule is skipped. outer: only the outermost match counts, for markup that nests sel.
// skip: site-chrome containers, if not the usual ones. Adding a site is one entry here (and one in the manifest's
// content_scripts if it should work without the site-access step).
export const SITES = [
  { host: /^(www\.)?(x\.com|twitter\.com)$/, sel: TWEET },
  { host: /^(www\.)?instagram\.com$/, sel: INSTAGRAM, outer: true, skip: 'nav,footer' }, // profile bios sit in <header>
];
const CHROME = 'nav,header,footer';
const BLOCKED = 'a,button,input,textarea,select,form,code,pre,kbd,samp,script,style,[contenteditable]:not([contenteditable="false"]),[role="textbox"],[role="button"],[hidden],[aria-hidden="true"],[translate="no"],.notranslate';
export const siteFor = (url) => SITES.find((s) => s.host.test(new URL(url).hostname)) || null;
export function selector(url) { return siteFor(url)?.sel || PROSE; }
// The element a node's text is tracked under: the nearest match, or the outermost one where matches nest.
export function textRoot(node, url) {
  const site = siteFor(url);
  const sel = site?.sel || PROSE;
  let el = node?.closest(sel) || null;
  if (site?.outer) for (let up = el?.parentElement?.closest(sel); up; up = up.parentElement?.closest(sel)) el = up;
  return el;
}
export function readable(el, url) {
  const site = siteFor(url);
  if (!el.isConnected || el.closest(BLOCKED) || el.closest(site?.skip || CHROME)) return false;
  if (el.querySelector('input,textarea,select,form,[contenteditable]:not([contenteditable="false"]),[role="textbox"],[hidden],[aria-hidden="true"],script,style')) return false;
  if (/\/(?:login|signin|sign-in|checkout|payment|billing|settings|accounts?)(?:\/|$)/i.test(new URL(url).pathname)) return false;
  const lang = el.closest('[lang]')?.getAttribute('lang') || '';
  if (lang && !/^(en(?:-|$)|und$|qme$|zxx$|art$)/i.test(lang)) return false;
  // Elsewhere the innermost prose block is the passage; a site's match is the post itself, unless it sits in another.
  if (site ? site.outer && el.parentElement?.closest(site.sel) : el.querySelector(PROSE)) return false;
  const text = flatten(el).text;
  return text.length <= 2000 && wordCount(text) >= 6 && !isZeroSpanish(text);
}
