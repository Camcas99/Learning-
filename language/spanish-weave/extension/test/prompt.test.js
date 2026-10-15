import { describe, test, expect } from 'bun:test';
import { buildSystemPrompt, buildUserContent, RESPONSE_SCHEMA } from '../src/prompt.js';
import { L1_WORDS, L2_WORDS } from '../src/levels.js';

describe('prompt', () => {
  test('L1 lists all 28 accented words and the sense rules', () => {
    const p = buildSystemPrompt(1);
    expect(p).toContain('Level 1');
    for (const w of L1_WORDS) expect(p).toContain(w.es);
    expect(p).toContain('también');
    expect(p).not.toContain('"also"->tambien');
    expect(p).toContain('Zero Spanish in passages about health');
    expect(p).toContain('Default is to swap');
  });
  test('L2 lists the fixed phrases; L3/L4 fall back to L2 for now', () => {
    const p = buildSystemPrompt(2);
    expect(p).toContain('Level 2');
    for (const w of L2_WORDS) expect(p).toContain(w.es);
    expect(p).toContain('hay que');
    expect(buildSystemPrompt(4)).toBe(p);
  });
  test('user content and schema shape', () => {
    expect(buildUserContent([{ id: 'a', text: 'hi', extra: 1 }])).toBe('Passages:\n[{"id":"a","text":"hi"}]');
    expect(RESPONSE_SCHEMA.properties.passages.items.required).toEqual(['id', 'swaps']);
    expect(RESPONSE_SCHEMA.properties.passages.items.properties.swaps.items.required).toEqual(['o', 'es', 'g', 'h', 'ctx']);
  });
  test('shared state: learning words are the target, unshown ones first; known words are filler; no fixed examples', () => {
    const words = [
      { es: 'grande', en: 'big', hint: 'GRAHN-deh', status: 'active' },
      { es: 'pequeño', en: 'small', hint: 'peh-KEH-nyoh', status: 'active' },
      { es: 'verdadero', en: 'true', hint: 'behr-dah-DEH-roh', status: 'shaky' },
      { es: 'y', en: 'and', hint: 'ee', status: 'known' },
    ];
    const p = buildSystemPrompt(2, words, ['grande']);
    expect(p).toContain('LEARNING words');
    expect(p).toContain('pequeño = small; verdadero = true; grande = big');
    expect(p).toContain('KNOWN words (filler only):\ny');
    expect(p).not.toContain('"but"->pero');
    expect(p).toContain('four or more swaps');
    expect(buildSystemPrompt(1, words)).toContain('two or more swaps');
  });
});
