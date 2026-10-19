import { describe, expect, it } from 'bun:test';
import { parseState, readCached, refresh, queueEvents, flushEvents, shownToday, STATE_KEY, PENDING_KEY } from '../src/hostsource.js';
import { memoryStorage } from '../src/cache.js';
import { validateSwaps } from '../src/levels.js';
import { buildSystemPrompt } from '../src/prompt.js';

// Shape the native host sends (scripts/sw_host.py "state").
const REPLY = {
  ok: true,
  version: 'abc123',
  stage: 1,
  paused: false,
  words: [
    { es: 'entonces', en: 'so / then', hint: 'en-TOHN-ses', status: 'active' },
    { es: 'muy', en: 'very', hint: 'mwee', status: 'shaky' },
    { es: 'y', en: 'and', hint: 'ee', status: 'known' },
  ],
  geminiKey: 'KEY',
};
const host = (reply) => async () => reply;

describe('parseState', () => {
  it('reads the host reply shape', () => {
    const s = parseState(REPLY);
    expect(s).toEqual({ version: 'abc123', stage: 1, paused: false, sites: 'all', sitesAt: 0, words: REPLY.words });
  });
  it('reads the site default setup chose; anything but "ask" means all sites', () => {
    expect(parseState({ ...REPLY, prefs: { extension_sites: 'ask' } }).sites).toBe('ask');
    expect(parseState({ ...REPLY, prefs: { extension_sites: 'all' } }).sites).toBe('all');
    expect(parseState({ ...REPLY, prefs: { extension_sites: 'bogus' } }).sites).toBe('all');
  });
  it('reads when setup last chose the sites (seconds), so a later popup choice can win', () => {
    expect(parseState({ ...REPLY, prefs: { extension_sites: 'ask', extension_sites_at: 1800000000 } }).sitesAt).toBe(1800000000);
    for (const at of [undefined, 'soon', -5, null]) expect(parseState({ ...REPLY, prefs: { extension_sites_at: at } }).sitesAt).toBe(0);
  });
  it('drops unusable rows and duplicates; bad stage falls back to 1', () => {
    const s = parseState({ stage: 9, words: [{ es: 'y', en: 'and' }, { es: 'y', en: 'x' }, { es: ' ', en: 'y' }, null, { es: 'pero' }] });
    expect(s.words).toEqual([{ es: 'y', en: 'and', hint: '', status: 'active' }]);
    expect(s.stage).toBe(1);
  });
  it('throws when nothing usable is left', () => {
    expect(() => parseState({ words: [] })).toThrow();
  });
  it('keeps a usage note when there is one: trimmed, one line, capped; anything else is dropped', () => {
    const s = parseState({ words: [
      { es: 'el éxito', en: 'success', hint: 'el EK-see-toh', status: 'active', note: "  not 'exit'\n(that's la salida) " },
      { es: 'largo', en: 'long', note: 'x'.repeat(300) },
      { es: 'y', en: 'and', note: '   ' },
      { es: 'muy', en: 'very', note: 42 },
    ] });
    expect(s.words[0]).toEqual({ es: 'el éxito', en: 'success', hint: 'el EK-see-toh', status: 'active', note: "not 'exit' (that's la salida)" });
    expect(s.words[1].note).toHaveLength(120);
    expect(s.words[1].note.endsWith('…')).toBe(true);
    expect('note' in s.words[2]).toBe(false);
    expect('note' in s.words[3]).toBe(false);
    // The note reaches the tooltip as the swap's n; it never goes into the model prompt.
    expect(validateSwaps(1, [{ o: 'success', es: 'éxito' }], s.words)[0].n).toBe("not 'exit' (that's la salida)");
    expect(buildSystemPrompt(1, s.words)).not.toContain('salida');
  });
});

describe('refresh', () => {
  it('stores the state and the setup key; a new version reports changed', async () => {
    const storage = memoryStorage();
    const r = await refresh({ storage, send: host(REPLY), now: () => 5 });
    expect(r.error).toBeNull();
    expect(r.changed).toBe(true);
    expect((await readCached(storage)).fetchedAt).toBe(5);
    expect((await storage.get(['hostKey'])).hostKey).toBe('KEY');
    const again = await refresh({ storage, send: host(REPLY) });
    expect(again.changed).toBe(false);
  });
  it('keeps the last good list when the host is missing or answers badly', async () => {
    const storage = memoryStorage();
    await refresh({ storage, send: host(REPLY) });
    const missing = await refresh({ storage, send: async () => { throw new Error('Specified native messaging host not found.'); } });
    expect(missing.error).toContain('not found');
    expect(missing.state.version).toBe('abc123');
    const bad = await refresh({ storage, send: host({ ok: true, words: [] }) });
    expect(bad.error).toBeTruthy();
    expect((await readCached(storage)).words).toHaveLength(3);
  });
  it('a synced list drives validation and the prompt', () => {
    const s = parseState(REPLY);
    expect(validateSwaps(1, [{ o: 'so', es: 'entonces', ctx: 'so then' }], s.words)[0].es).toBe('entonces');
    expect(validateSwaps(1, [{ o: 'but', es: 'pero', ctx: 'x' }], s.words)).toEqual([]);
    const prompt = buildSystemPrompt(1, s.words);
    expect(prompt).toContain('entonces = so / then; muy = very');
    expect(prompt).toContain('KNOWN words (filler only):\ny');
  });
});

describe('events', () => {
  it('counts a word as seen or peeked once per day, keeps every flip', async () => {
    const storage = memoryStorage();
    await queueEvents(storage, [{ word: 'Muy', kind: 'seen' }, { word: 'muy', kind: 'seen' }, { word: 'y', kind: 'flip' },
      { word: 'muy', kind: 'peek' }, { word: 'muy', kind: 'peek' }], '2026-10-01');
    await queueEvents(storage, [{ word: 'muy', kind: 'seen' }, { word: 'y', kind: 'flip' }, { word: 'x', kind: 'bogus' }], '2026-10-01');
    await queueEvents(storage, [{ word: 'muy', kind: 'seen' }], '2026-10-02');
    const { [PENDING_KEY]: pending } = await storage.get([PENDING_KEY]);
    expect(pending).toEqual([
      { word: 'muy', kind: 'seen', day: '2026-10-01' },
      { word: 'y', kind: 'flip', day: '2026-10-01' },
      { word: 'muy', kind: 'peek', day: '2026-10-01' },
      { word: 'y', kind: 'flip', day: '2026-10-01' },
      { word: 'muy', kind: 'seen', day: '2026-10-02' },
    ]);
  });
  it('flush sends and clears; a failed flush keeps the queue', async () => {
    const storage = memoryStorage();
    await queueEvents(storage, [{ word: 'y', kind: 'flip' }], '2026-10-01');
    const failed = await flushEvents({ storage, send: async () => { throw new Error('no host'); } });
    expect(failed.error).toBe('no host');
    expect((await storage.get([PENDING_KEY]))[PENDING_KEY]).toHaveLength(1);
    const sent = [];
    const ok = await flushEvents({ storage, send: async (m) => { sent.push(m); return { ok: true, applied: 1 }; } });
    expect(ok).toEqual({ sent: 1, applied: 1 });
    expect(sent[0].type).toBe('events');
    expect((await storage.get([PENDING_KEY]))[PENDING_KEY]).toEqual([]);
  });
  it('words seen today come back for the prompt; peeks and other days do not', async () => {
    const storage = memoryStorage();
    await queueEvents(storage, [{ word: 'muy', kind: 'seen' }, { word: 'y', kind: 'peek' }], '2026-10-01');
    expect(await shownToday(storage, '2026-10-01')).toEqual(['muy']);
    expect(await shownToday(storage, '2026-10-02')).toEqual([]);
  });
  it('readCached ignores empty state', async () => {
    expect(await readCached(memoryStorage({ [STATE_KEY]: { words: [] } }))).toBeNull();
  });
});
