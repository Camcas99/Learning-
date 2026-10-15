import { describe, test, expect } from 'bun:test';
import {
  resolveLevel, L1_WORDS, L2_WORDS, validateSwaps, wordCount, isZeroSpanish, normalizeEs, matchCase, genderOf,
} from '../src/levels.js';

describe('level', () => {
  test('follows the synced stage, else 1; override wins; capped at the built level', () => {
    expect(resolveLevel({})).toEqual({ stage: 0, chosen: 1, effective: 1 });
    expect(resolveLevel({}, 2)).toEqual({ stage: 2, chosen: 2, effective: 2 });
    expect(resolveLevel({ levelOverride: 1 }, 2)).toEqual({ stage: 2, chosen: 1, effective: 1 });
    expect(resolveLevel({ levelOverride: 4 }, 1)).toEqual({ stage: 1, chosen: 4, effective: 2 });
    expect(resolveLevel({ levelOverride: 9 }, 7)).toEqual({ stage: 0, chosen: 1, effective: 1 });
  });
});

describe('word lists', () => {
  test('L1 is the bundled starter list', () => {
    const spec = ['y', 'pero', 'o', 'entonces', 'porque', 'con', 'sin', 'para', 'muy', 'también', 'bien', 'mucho', 'un poco',
      'ahora', 'siempre', 'tal vez', 'aquí', 'listo', 'sí', 'claro', 'gracias', 'el problema', 'la pregunta', 'la idea',
      'la respuesta', 'importante', 'posible', 'difícil'];
    expect(L1_WORDS.map((w) => w.es)).toEqual(spec);
  });
  test('L2 is about 150 words, includes L1 and the fixed phrases, every entry glossed with a hint', () => {
    expect(L2_WORDS.length).toBeGreaterThanOrEqual(140);
    expect(L2_WORDS.length).toBeLessThanOrEqual(160);
    const spanish = L2_WORDS.map((w) => w.es);
    for (const w of L1_WORDS) expect(spanish).toContain(w.es);
    for (const p of ['es', 'hay', 'creo que', 'hay que']) expect(spanish).toContain(p);
    expect(new Set(spanish).size).toBe(spanish.length);
    for (const w of L2_WORDS) {
      expect(w.en.length).toBeGreaterThan(0);
      expect(w.hint.length).toBeGreaterThan(0);
    }
  });
});

describe('validateSwaps', () => {
  test('keeps list words, canonicalizes accents, fills gloss and hint from the list', () => {
    const out = validateSwaps(1, [{ o: 'also', es: 'tambien', g: 'x', h: 'y', ctx: 'is also good' }]);
    expect(out).toEqual([{ o: 'also', es: 'también', g: 'also', h: 'tahm-BYEN', ctx: 'is also good' }]);
  });
  test('drops words off the level list and malformed entries', () => {
    expect(validateSwaps(1, [{ o: 'in', es: 'en' }])).toEqual([]);
    expect(validateSwaps(2, [{ o: 'in', es: 'en' }])[0].es).toBe('en');
    expect(validateSwaps(1, [{ o: 'and' }, null, { es: 'y' }, { o: '  ', es: 'y' }])).toEqual([]);
    expect(validateSwaps(1, 'nope')).toEqual([]);
  });
  test('accepts the bare noun and keeps accents', () => {
    const [s] = validateSwaps(2, [{ o: 'reason', es: 'razon' }]);
    expect(s.es).toBe('razón');
    expect(s.g).toBe('reason');
    expect(s.h).toBe('rrah-SOHN');
    const [t] = validateSwaps(2, [{ o: 'the reason', es: 'la razón' }]);
    expect(t.es).toBe('la razón');
  });
  test('matches capitalization of the original', () => {
    expect(validateSwaps(1, [{ o: 'And', es: 'y' }])[0].es).toBe('Y');
    expect(validateSwaps(1, [{ o: 'AND', es: 'y' }])[0].es).toBe('y');
    expect(validateSwaps(1, [{ o: 'Maybe', es: 'tal vez' }])[0].es).toBe('Tal vez');
    expect(matchCase('la idea', 'The idea')).toBe('La idea');
  });
  test('keeps accented homographs distinct and rejects blank replacements', () => {
    expect(validateSwaps(2, [{ o: 'if', es: 'si' }])[0].es).toBe('si');
    expect(validateSwaps(2, [{ o: 'yes', es: 'sí' }])[0].es).toBe('sí');
    expect(validateSwaps(2, [{ o: 'and', es: '' }, { o: 'and', es: '  ' }])).toEqual([]);
  });
  test('plugin words replace the bundled list and keep the event spelling and status', () => {
    const words = [{ es: 'la canción', en: 'the song', hint: 'lah kahn-SYOHN', status: 'active' }];
    expect(validateSwaps(1, [{ o: 'song', es: 'cancion' }, { o: 'and', es: 'y' }], words))
      .toEqual([{ o: 'song', es: 'canción', g: 'song', h: 'kahn-SYOHN', ctx: '', word: 'la canción', status: 'active', gn: 'f' }]);
  });
  test('nouns carry their gender, bare or with the article; other words carry none', () => {
    const [bare, full, conj] = validateSwaps(2, [{ o: 'problem', es: 'problema' }, { o: 'the house', es: 'la casa' }, { o: 'and', es: 'y' }]);
    expect([bare.es, bare.gn]).toEqual(['problema', 'm']);
    expect([full.es, full.gn]).toEqual(['la casa', 'f']);
    expect('gn' in conj).toBe(false);
    expect(validateSwaps(2, [{ o: 'day', es: 'dia' }])[0].gn).toBe('m');
    expect('gn' in validateSwaps(1, [{ o: 'a little', es: 'un poco' }])[0]).toBe(false);
  });
  test('usage notes ride along as n, from the bundled list or the synced word', () => {
    expect(L2_WORDS.find((w) => w.es === 'largo').note).toBe("not 'large' (that's grande)");
    expect(validateSwaps(2, [{ o: 'long', es: 'largo' }])[0].n).toBe("not 'large' (that's grande)");
    expect('n' in validateSwaps(2, [{ o: 'big', es: 'grande' }])[0]).toBe(false);
    const words = [{ es: 'el éxito', en: 'success', hint: 'el EK-see-toh', status: 'active', note: "not 'exit' (that's la salida)" }];
    expect(validateSwaps(1, [{ o: 'success', es: 'exito' }], words)).toEqual([{ o: 'success', es: 'éxito', g: 'success',
      h: 'EK-see-toh', ctx: '', word: 'el éxito', status: 'active', gn: 'm', n: "not 'exit' (that's la salida)" }]);
  });
  test('normalizeEs', () => {
    expect(normalizeEs(' También ')).toBe('tambien');
    expect(normalizeEs('Año  Nuevo')).toBe('ano nuevo');
  });
});

describe('genderOf', () => {
  test('the article gives the gender; stressed a- nouns take "el" but stay feminine; no article, no gender', () => {
    expect(genderOf('el agua')).toBe('f');
    expect(genderOf('el problema')).toBe('m');
    expect(genderOf('el día')).toBe('m');
    expect(genderOf('la mano')).toBe('f');
    expect(genderOf('los ojos')).toBe('m');
    expect(genderOf('las ganas')).toBe('f');
    expect(genderOf('entonces')).toBe('');
    expect(genderOf('un alma')).toBe('f');
    expect(genderOf('El Águila')).toBe('f');
    expect(genderOf('el hambre')).toBe('f');
    expect(genderOf('una idea')).toBe('f');
    expect(genderOf('unos días')).toBe('m');
    expect(genderOf('el fin de semana')).toBe('m');
    expect(genderOf('elegante')).toBe('');
  });
  test('adverbial phrases that open with un/una are not nouns', () => {
    expect(genderOf('un poco')).toBe('');
    expect(genderOf('una vez más')).toBe('');
  });
});

describe('guards', () => {
  test('wordCount', () => {
    expect(wordCount('')).toBe(0);
    expect(wordCount('  one two\n\nthree ')).toBe(3);
  });
  test('zero-Spanish topics', () => {
    expect(isZeroSpanish('if you take ibuprofen talk to your doctor first')).toBe(true);
    expect(isZeroSpanish('my lawyer says the lawsuit is fine')).toBe(true);
    expect(isZeroSpanish('call 911 in an emergency')).toBe(true);
    expect(isZeroSpanish('shipped the new onboarding flow today')).toBe(false);
    expect(isZeroSpanish('the taxi was late again')).toBe(false);
  });
});
