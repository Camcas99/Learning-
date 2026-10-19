import { test, expect } from 'bun:test';
import { readFileSync } from 'node:fs';
import { Window } from 'happy-dom';
import { cleanSettings } from '../src/settings.js';

// popup.html and popup.js with a fake worker: the speech and gender toggles show what is saved and save changes.
test('popup: "Say words aloud" and "Color noun gender" toggles', async () => {
  const win = new Window({ url: 'chrome-extension://sw-test/src/popup.html' });
  const names = ['chrome', 'document', 'window'];
  const originalGlobals = Object.fromEntries(names.map((k) => [k, globalThis[k]]));
  const html = readFileSync(new URL('../src/popup.html', import.meta.url), 'utf8');
  win.document.body.innerHTML = /<body>([\s\S]*)<\/body>/.exec(html)[1].replace(/<script[\s\S]*?<\/script>/, '');
  let settings = { ...cleanSettings({ speak: true }), newSitesEnabled: true };
  const saves = [];
  Object.assign(globalThis, {
    window: win, document: win.document,
    chrome: {
      tabs: { query: async () => [{ id: 1, url: 'https://example.com/post' }] },
      permissions: { contains: async () => true, request: async () => false },
      runtime: { sendMessage: async (msg) => {
        if (msg.type === 'save') { saves.push(msg.settings); settings = cleanSettings({ ...settings, ...msg.settings }); return { ok: true }; }
        return { config: { settings, stage: 1, origins: ['https://*/*'], hasKey: true, paused: false }, words: 0, pastedKey: true, hostKey: false, modelStatus: null };
      } },
    },
  });
  const wait = (ms = 50) => new Promise((done) => setTimeout(done, ms));
  try {
    await import('../src/popup.js?popup');
    await wait();
    const speak = win.document.getElementById('speak');
    const gender = win.document.getElementById('genderColors');
    expect([speak.checked, gender.checked]).toEqual([true, true]); // both show what is saved
    expect(win.document.body.textContent).toContain('Alt+click');
    speak.checked = false; speak.dispatchEvent(new win.Event('change'));
    await wait();
    gender.checked = false; gender.dispatchEvent(new win.Event('change'));
    await wait();
    expect(saves).toEqual([{ speak: false }, { genderColors: false }]);
    expect([speak.checked, gender.checked]).toEqual([false, false]);
    expect(win.document.getElementById('notice').textContent).toBe('');
  } finally {
    await win.happyDOM.close();
    Object.assign(globalThis, originalGlobals);
  }
});

// Pause and setup reruns live in the plugin, and the native host can't push them: opening the popup picks them up.
test('popup: opening it syncs words over a minute old, quietly; fresh ones are left alone', async () => {
  const names = ['chrome', 'document', 'window'];
  const originalGlobals = Object.fromEntries(names.map((k) => [k, globalThis[k]]));
  const html = readFileSync(new URL('../src/popup.html', import.meta.url), 'utf8');
  const wait = (ms = 50) => new Promise((done) => setTimeout(done, ms));
  try {
    for (const [age, syncs] of [[5 * 60000, 1], [5000, 0]]) {
      const win = new Window({ url: 'chrome-extension://sw-test/src/popup.html' });
      win.document.body.innerHTML = /<body>([\s\S]*)<\/body>/.exec(html)[1].replace(/<script[\s\S]*?<\/script>/, '');
      const settings = { ...cleanSettings(), newSitesEnabled: true };
      const asked = [];
      Object.assign(globalThis, {
        window: win, document: win.document,
        chrome: {
          tabs: { query: async () => [{ id: 1, url: 'https://example.com/post' }] },
          permissions: { contains: async () => true, request: async () => false },
          runtime: { sendMessage: async (msg) => {
            asked.push(msg.type);
            if (msg.type === 'syncWords') return { ok: false, error: 'Specified native messaging host not found.' };
            return { config: { settings, stage: 1, origins: ['https://*/*'], hasKey: true, paused: false }, words: 5,
              fetchedAt: Date.now() - age, pastedKey: false, hostKey: true, modelStatus: null };
          } },
        },
      });
      await import(`../src/popup.js?age${age}`);
      await wait();
      expect([age, asked.filter((t) => t === 'syncWords').length]).toEqual([age, syncs]);
      expect(win.document.getElementById('notice').textContent).toBe(''); // a failed quiet sync shows nothing
      expect(win.document.getElementById('wordInfo').textContent).toContain('5 from Claude Code');
      await win.happyDOM.close();
    }
  } finally {
    Object.assign(globalThis, originalGlobals);
  }
});
