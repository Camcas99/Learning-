import { describe, test, expect } from 'bun:test';
import { pickVoice, speak, RATE } from '../src/speech.js';

const v = (lang) => ({ lang, name: `voice ${lang}` });
class Utterance { constructor(text) { this.text = text; } }
function fakeSynth(voices) {
  const synth = { spoken: [], cancels: 0, getVoices: () => voices, speak: (u) => synth.spoken.push(u), cancel: () => { synth.cancels++; } };
  return synth;
}

describe('pickVoice', () => {
  test('Latin American first: es-MX, then es-US, then es-419, then any Spanish voice', () => {
    const all = [v('en-US'), v('es-ES'), v('es-419'), v('es-US'), v('es-MX')];
    expect(pickVoice(all).lang).toBe('es-MX');
    expect(pickVoice(all.filter((x) => x.lang !== 'es-MX')).lang).toBe('es-US');
    expect(pickVoice([v('es-ES'), v('es-419'), v('en-GB')]).lang).toBe('es-419');
    expect(pickVoice([v('en-US'), v('es-ES')]).lang).toBe('es-ES');
    expect(pickVoice([v('es_MX'), v('es-ES')]).lang).toBe('es_MX'); // Android's tag style
    expect(pickVoice([v('en-US'), v('fr-FR'), v('et-EE')])).toBeNull();
    expect(pickVoice([])).toBeNull();
  });
});

describe('speak', () => {
  test('one utterance in the chosen voice at a learner pace, cutting off the last word', () => {
    const synth = fakeSynth([v('es-ES'), v('es-US')]);
    expect(speak('Y', { synth, Utterance })).toBe(true);
    expect(speak('también', { synth, Utterance })).toBe(true);
    expect(synth.spoken.map((u) => [u.text, u.lang, u.voice.lang, u.rate])).toEqual([['y', 'es-US', 'es-US', RATE], ['también', 'es-US', 'es-US', RATE]]);
    expect(RATE).toBe(0.9);
    expect(synth.cancels).toBe(2);
  });
  test('no Spanish voice installed (or not loaded yet): lang es-MX and the browser picks', () => {
    for (const voices of [[v('en-US')], []]) {
      const synth = fakeSynth(voices);
      speak('casa', { synth, Utterance });
      expect(synth.spoken[0].lang).toBe('es-MX');
      expect(synth.spoken[0].voice).toBeUndefined();
    }
  });
  test('no speech API or nothing to say: does nothing', () => {
    const synth = fakeSynth([v('es-MX')]);
    expect(speak('casa', { synth: null, Utterance })).toBe(false);
    expect(speak('casa', { synth, Utterance: null })).toBe(false);
    expect(speak('', { synth, Utterance })).toBe(false);
    expect(synth.spoken).toHaveLength(0);
  });
});
