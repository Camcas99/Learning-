// The private reader: message threads with Spanish woven into the bubbles, a tap on a word for its meaning, and the
// English one tap away. It only reads: replies go through the real app. Messages come from a source ({ words,
// threads }: the made-up demo for now, the Mac's read-only helper later) and are drawn as text, never as HTML, so a
// message can't add markup or scripts. Nothing is stored and nothing is sent anywhere.
import { weave, wovenText } from '../extension/src/chatweave.js';

const el = (doc, tag, cls, text) => {
  const node = doc.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};

const initials = (name) => String(name).trim().split(/\s+/).slice(0, 2).map((w) => [...w][0] || '').join('').toUpperCase();

// "9:41 AM" today, "Yesterday", else a short date, in the phone's own language; '' with no date.
function when(date, now) {
  if (!date) return '';
  const day = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((day(now) - day(date)) / 86400000);
  if (days <= 0) return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  if (days === 1) return 'Yesterday';
  if (days < 7) return date.toLocaleDateString(undefined, { weekday: 'long' });
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// mount(root, source, { win, now }) draws the reader into root and follows the address bar: #/t/<id> is a thread,
// anything else the list. Returns { route } for tests.
export function mount(root, source, { win = root.ownerDocument.defaultView, now = new Date(), demo = false } = {}) {
  const doc = root.ownerDocument;
  const words = Array.isArray(source?.words) ? source.words : [];
  // Only plain records with a usable id; a message's time is its own, else minutesAgo, else none.
  const isRecord = (x) => x !== null && typeof x === 'object';
  const dateOf = (m) => {
    const d = m.at !== undefined ? new Date(m.at) : new Date(now.getTime() - (Number(m.minutesAgo) || 0) * 60000);
    return Number.isNaN(d.getTime()) ? null : d;
  };
  const threads = (Array.isArray(source?.threads) ? source.threads : []).filter(isRecord)
    .map((t) => ({ ...t, id: String(t.id ?? ''), name: String(t.name ?? ''),
      messages: (Array.isArray(t.messages) ? t.messages : []).filter(isRecord)
        .map((m) => ({ ...m, from: String(m.from ?? ''), text: String(m.text ?? ''), at: dateOf(m) })) }))
    .filter((t) => t.id && t.id.isWellFormed());
  const woven = new Map();
  const result = (m) => {
    if (!woven.has(m)) woven.set(m, weave(m.text, words));
    return woven.get(m);
  };
  let english = false;
  let current = null;

  root.replaceChildren();
  const bar = el(doc, 'header', 'bar');
  const back = el(doc, 'a', 'back', 'Messages');
  back.href = '#';
  const title = el(doc, 'h1', 'title');
  title.tabIndex = -1;
  const toggle = el(doc, 'button', 'toggle');
  toggle.type = 'button';
  bar.append(back, title, toggle);
  const view = el(doc, 'main', 'view');
  const sheet = el(doc, 'div', 'sheet');
  sheet.hidden = true;
  const card = el(doc, 'div', 'card');
  card.setAttribute('role', 'dialog');
  card.setAttribute('aria-modal', 'true');
  card.setAttribute('aria-labelledby', 'sheet-es');
  const sheetEs = el(doc, 'p', 'card-es');
  sheetEs.id = 'sheet-es';
  sheetEs.lang = 'es';
  const sheetHint = el(doc, 'p', 'card-hint');
  const sheetMeaning = el(doc, 'p', 'card-meaning');
  const sheetOriginal = el(doc, 'p', 'card-original');
  const done = el(doc, 'button', 'card-done', 'Done');
  done.type = 'button';
  card.append(sheetEs, sheetHint, sheetMeaning, sheetOriginal, done);
  sheet.append(card);
  root.append(bar, view, sheet);

  let opener = null;
  function openSheet(part, button) {
    opener = button;
    sheetEs.textContent = part.es;
    sheetHint.textContent = part.h ? `Sounds like ${part.h}` : '';
    sheetMeaning.textContent = part.g ? `Means ${part.g}` : '';
    sheetOriginal.textContent = `In the message: “${part.o}”`;
    sheet.hidden = false;
    // The page behind can't be tabbed to or read out while the sheet is open.
    bar.inert = true;
    view.inert = true;
    done.focus();
  }
  function closeSheet() {
    if (sheet.hidden) return;
    sheet.hidden = true;
    bar.inert = false;
    view.inert = false;
    opener?.focus();
    opener = null;
  }
  done.addEventListener('click', closeSheet);
  sheet.addEventListener('click', (e) => { if (e.target === sheet) closeSheet(); });
  doc.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });

  // The message as text nodes and word buttons; the English ones only when the toggle shows it.
  function fill(node, m) {
    for (const part of result(m).parts) {
      if (typeof part === 'string') node.append(doc.createTextNode(part));
      else if (english) node.append(doc.createTextNode(part.o));
      else {
        const word = el(doc, 'button', 'sw', part.es);
        word.type = 'button';
        word.lang = 'es';
        word.setAttribute('aria-haspopup', 'dialog');
        word.setAttribute('aria-label', `${part.es}, means ${part.g}`);
        word.addEventListener('click', () => openSheet(part, word));
        node.append(word);
      }
    }
  }

  function showList() {
    const from = current;
    current = null;
    doc.title = 'Messages';
    title.textContent = 'Messages';
    back.hidden = true;
    toggle.hidden = true;
    const list = el(doc, 'ul', 'threads');
    const latest = (t) => t.messages[t.messages.length - 1];
    const sorted = threads.filter((t) => t.messages.length).sort((a, b) => (latest(b).at || 0) - (latest(a).at || 0));
    for (const t of sorted) {
      const last = latest(t);
      const item = el(doc, 'li');
      const link = el(doc, 'a', 'thread');
      link.href = `#/t/${encodeURIComponent(t.id)}`;
      link.dataset.id = t.id;
      const face = el(doc, 'span', 'face', initials(t.name));
      face.setAttribute('aria-hidden', 'true');
      const text = el(doc, 'span', 'thread-text');
      const top = el(doc, 'span', 'thread-top');
      top.append(el(doc, 'span', 'thread-name', t.name), el(doc, 'span', 'thread-time', when(last.at, now)));
      const preview = el(doc, 'span', 'thread-preview');
      preview.textContent = `${last.from === 'me' ? 'You: ' : t.group ? `${last.from}: ` : ''}${wovenText(result(last).parts)}`;
      text.append(top, preview);
      link.append(face, text);
      item.append(link);
      list.append(item);
    }
    const parts = [];
    if (demo) parts.push(el(doc, 'p', 'note', 'Made-up messages for trying the reader. Your real threads appear here once the Mac helper is set up.'));
    parts.push(sorted.length ? list : el(doc, 'p', 'empty', 'No messages yet.'));
    view.replaceChildren(...parts);
    // Back from a thread, focus returns to its row.
    if (from) [...list.querySelectorAll('.thread')].find((a) => a.dataset.id === from.id)?.focus({ preventScroll: true });
  }

  function showThread(t) {
    current = t;
    doc.title = t.name;
    title.textContent = t.name;
    back.hidden = false;
    toggle.hidden = false;
    toggle.textContent = english ? 'Spanish' : 'English';
    toggle.setAttribute('aria-pressed', String(english));
    toggle.setAttribute('aria-label', english ? 'Show the Spanish words' : 'Show the messages in English');
    const log = el(doc, 'ol', 'log');
    let prev = null;
    for (const m of t.messages) {
      const mine = m.from === 'me';
      const row = el(doc, 'li', `msg ${mine ? 'out' : 'in'}`);
      if (t.group && !mine && (!prev || prev.from !== m.from)) row.append(el(doc, 'span', 'who', m.from));
      const bubble = el(doc, 'p', 'bubble');
      fill(bubble, m);
      row.append(bubble);
      if (m.at) {
        const time = el(doc, 'time', 'stamp', when(m.at, now));
        time.dateTime = m.at.toISOString();
        row.append(time);
      }
      log.append(row);
      prev = m;
    }
    const reply = el(doc, 'p', 'reply', 'Replies go in the Messages app. This reader never sends anything.');
    view.replaceChildren(log, reply);
    title.focus({ preventScroll: true });
  }

  toggle.addEventListener('click', () => {
    english = !english;
    if (current) showThread(current);
  });

  function route() {
    closeSheet();
    const m = /^#\/t\/(.+)$/.exec(win.location.hash);
    let id = null;
    try {
      id = m && decodeURIComponent(m[1]);
    } catch {
      id = null; // a broken escape in the address names no thread
    }
    const t = id && threads.find((x) => x.id === id);
    if (t) showThread(t);
    else showList();
    view.scrollTop = 0;
    if (t) win.scrollTo?.(0, doc.documentElement.scrollHeight);
    else win.scrollTo?.(0, 0);
  }
  win.addEventListener('hashchange', route);
  route();
  return { route };
}
