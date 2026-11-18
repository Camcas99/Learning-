import { describe, test, expect } from 'bun:test';
import { readFileSync } from 'node:fs';
import { Window } from 'happy-dom';
import { mount } from '../../reader/reader.js';
import { DEMO_THREADS, DEMO_WORDS } from '../../reader/demo.js';

const NOW = new Date('2026-11-07T18:00:00');

function open(source, hash = '') {
  const win = new Window({ url: `http://127.0.0.1:8765/reader/${hash}` });
  const root = win.document.createElement('div');
  win.document.body.append(root);
  const app = mount(root, source, { win, now: NOW, demo: true });
  const go = (h) => { win.location.hash = h; app.route(); };
  return { win, doc: win.document, root, go };
}
const demo = { words: DEMO_WORDS, threads: DEMO_THREADS };
const bubbles = (root) => [...root.querySelectorAll('.bubble')].map((b) => b.textContent);

describe('reader', () => {
  test('the demo words copy the lexicon', () => {
    const rows = new Map(readFileSync(new URL('../../data/lexicon.csv', import.meta.url), 'utf8').trim().split('\n').slice(1)
      .map((line) => line.split(',')).map(([es, en, hint]) => [es, { en, hint }]));
    for (const w of DEMO_WORDS) expect([w.es, w.en, w.hint]).toEqual([w.es, rows.get(w.es)?.en, rows.get(w.es)?.hint]);
  });

  test('lists threads newest first with a woven preview, and the demo note', () => {
    const { root } = open(demo);
    expect([...root.querySelectorAll('.thread-name')].map((n) => n.textContent)).toEqual(['Maya', 'Climbing crew', 'Dad', '45678']);
    expect(root.querySelector('.thread-preview').textContent).toBe('Tal vez we can get tacos after? I know a place where they make them fresh');
    expect(root.querySelector('.note').textContent).toContain('Made-up messages');
    expect(root.querySelector('.back').hidden).toBe(true);
    expect(root.querySelector('.toggle').hidden).toBe(true);
  });

  test('a thread shows Spanish as word buttons, and a word opens its meaning', () => {
    const { root, doc, go } = open(demo);
    go('#/t/maya');
    expect(root.querySelector('.title').textContent).toBe('Maya');
    expect(bubbles(root)[0]).toBe('Hey! Are you todavía coming tonight?');
    const word = root.querySelector('.sw');
    expect(word.textContent).toBe('todavía');
    expect(word.getAttribute('aria-label')).toBe('todavía, means still / yet');
    word.click();
    const sheet = root.querySelector('.sheet');
    expect(sheet.hidden).toBe(false);
    expect(root.querySelector('.card-es').textContent).toBe('todavía');
    expect(root.querySelector('.card-hint').textContent).toBe('Sounds like toh-dah-BEE-ah');
    expect(root.querySelector('.card-meaning').textContent).toBe('Means still / yet');
    expect(root.querySelector('.card-original').textContent).toBe('In the message: “still”');
    expect(doc.activeElement).toBe(root.querySelector('.card-done'));
    expect([root.querySelector('.view').inert, root.querySelector('.bar').inert]).toEqual([true, true]);
    root.querySelector('.card-done').click();
    expect(sheet.hidden).toBe(true);
    expect(doc.activeElement).toBe(word);
    expect([root.querySelector('.view').inert, root.querySelector('.bar').inert]).toEqual([false, false]);
    word.click();
    doc.dispatchEvent(new doc.defaultView.KeyboardEvent('keydown', { key: 'Escape' }));
    expect(sheet.hidden).toBe(true);
    word.click();
    root.querySelector('.card').click(); // a tap on the card itself keeps it open
    expect(sheet.hidden).toBe(false);
    sheet.click(); // a tap on the shade around it closes it
    expect(sheet.hidden).toBe(true);
  });

  test('focus moves to the thread title, and back to its row on the list', () => {
    const { root, doc, go } = open(demo);
    go('#/t/crew');
    expect(doc.activeElement).toBe(root.querySelector('.title'));
    go('');
    expect(doc.activeElement?.dataset.id).toBe('crew');
  });

  test('the toggle shows the English, and codes and serious topics never change', () => {
    const { root, go } = open(demo);
    go('#/t/maya');
    expect(bubbles(root)[2]).toBe("Perfect. There's parking behind the building, and the gate code is 4417");
    const toggle = root.querySelector('.toggle');
    expect(toggle.getAttribute('aria-pressed')).toBe('false');
    toggle.click();
    expect(root.querySelector('.toggle').getAttribute('aria-pressed')).toBe('true');
    expect(bubbles(root)).toEqual(DEMO_THREADS[0].messages.map((m) => m.text));
    expect(root.querySelectorAll('.sw').length).toBe(0);
    go('#/t/dad');
    root.querySelector('.toggle').click();
    expect(bubbles(root)[2]).toBe('Good. Also the doctor said my knee is fine, nothing to worry about');
    go('#/t/code');
    expect(root.querySelectorAll('.sw').length).toBe(0);
  });

  test('group threads name each sender once per run; mine sit on the right', () => {
    const { root, go } = open(demo);
    go('#/t/crew');
    expect([...root.querySelectorAll('.who')].map((n) => n.textContent)).toEqual(['Jordan', 'Sam', 'Priya', 'Jordan', 'Sam']);
    expect([...root.querySelectorAll('.msg')].map((n) => n.classList.contains('out'))).toEqual([false, false, false, false, true, false]);
  });

  test('names, senders, previews and message text are never markup', () => {
    const evil = '<img src=x onerror="alert(1)"><script>alert(1)</script> thanks and bye';
    const { root, go } = open({ words: DEMO_WORDS, threads: [{ id: '<b>x</b>', name: '<i>Eve</i>', group: true,
      messages: [{ id: 'e', from: '<u>Eve</u>', text: evil }] }] });
    const tags = 'img, script, b, i, u';
    expect(root.querySelector('.thread-name').textContent).toBe('<i>Eve</i>');
    expect(root.querySelector('.thread-preview').textContent).toBe(`<u>Eve</u>: ${evil.replace('thanks', 'gracias')}`);
    expect(root.querySelectorAll(tags).length).toBe(0);
    go(`#/t/${encodeURIComponent('<b>x</b>')}`);
    expect(root.querySelector('.who').textContent).toBe('<u>Eve</u>');
    expect(root.querySelector('.bubble').textContent).toContain('<img src=x');
    root.querySelector('.sw').click();
    expect(root.querySelector('.card-original').textContent).toBe('In the message: “thanks”');
    expect(root.querySelectorAll(tags).length).toBe(0);
  });

  test('odd sources: no threads, bad records, number ids, broken dates and addresses', () => {
    for (const source of [null, {}, { threads: 'x' }, { threads: [{ id: 'a', name: 'A' }] }, { threads: [null, 7] },
      { threads: [{ id: 'ab\uD83D', name: 'Bad id', messages: [{ text: 'hi' }] }] }]) {
      expect(open(source).root.querySelector('.empty').textContent).toBe('No messages yet.');
    }
    const { root, go } = open({ words: DEMO_WORDS, threads: [{ id: 42, name: 'Chat 42', messages: [null,
      { from: 'x', text: 'thanks and bye', at: 'yesterday-ish' }] }] });
    expect(root.querySelector('.thread-time').textContent).toBe('');
    go('#/t/42');
    expect(root.querySelector('.title').textContent).toBe('Chat 42');
    expect(bubbles(root)).toEqual(['gracias and bye']);
    expect(root.querySelectorAll('.stamp').length).toBe(0);
    for (const hash of ['#/t/%', '#/t/%E0%A4%A', '#/t/100%']) {
      go(hash);
      expect(root.querySelector('.title').textContent).toBe('Messages');
    }
  });

  test('an unknown thread goes back to the list', () => {
    const { root, go } = open(demo);
    go('#/t/nobody');
    expect(root.querySelector('.title').textContent).toBe('Messages');
    expect(root.querySelectorAll('.thread').length).toBe(4);
  });
});
