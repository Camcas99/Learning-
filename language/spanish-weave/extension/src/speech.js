// Pronunciation through the Web Speech API: Alt+click (Option+click) or Alt+Enter on a swap, and the gloss when
// the popup's "Say words aloud when the meaning shows" is on. synth and Utterance are injectable, so tests use fakes.
export const RATE = 0.9; // a touch slower than normal speech, for a learner
const LATAM = ['es-mx', 'es-us', 'es-419'];
const tag = (voice) => String(voice?.lang || '').replace(/_/g, '-').toLowerCase(); // Android says es_MX

// Latin American Spanish first (es-MX, es-US, es-419), then any Spanish voice; null when none is installed.
export function pickVoice(voices = []) {
  for (const lang of LATAM) {
    const hit = voices.find((v) => tag(v) === lang);
    if (hit) return hit;
  }
  return voices.find((v) => /^es(-|$)/.test(tag(v))) || null;
}

// Speaks one word; false when the browser has no speech API. The window has one shared speech queue, so a new word
// cuts off whatever is playing (a page's own read-aloud too) rather than waiting behind it.
export function speak(text, { synth = globalThis.speechSynthesis, Utterance = globalThis.SpeechSynthesisUtterance } = {}) {
  if (!text || !synth || typeof Utterance !== 'function') return false;
  const u = new Utterance(String(text).toLowerCase()); // a capital "Y" alone can be read as the letter's name
  const voice = pickVoice(synth.getVoices?.() || []); // can be empty until Chrome has loaded its voices
  if (voice) u.voice = voice;
  u.lang = voice ? voice.lang : 'es-MX'; // none installed: the browser picks a voice for the language
  u.rate = RATE;
  synth.cancel();
  synth.speak(u);
  return true;
}
