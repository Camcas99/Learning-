// The swap revision. Pages tag every request with it and cached swaps are keyed by it, so anything that can change
// which swaps are chosen must change it. Display-only settings (speech, gender colors) stay out, so toggling them
// costs no model calls.
import { hashKey } from './hash.js';

// Bump when cached swaps gain fields or the prompt's sense rules change, so old ones are refetched
// (2: noun gender gn, usage note n; 3: sense rules for es, esto/eso, question words, sino).
export const SWAP_FORMAT = 3;

// extension: the extension's version, so an update that edits the bundled word list or notes refetches too.
// words: the plugin's word-state version (statuses, glosses, hints and notes), when the native host is there.
// Where swaps run (on/off, site choices, site access, a pause) stays out: content.js stops or starts the page for
// those, so turning a site off and on again repaints from the cache instead of asking the model.
export function swapRevision({ extension = '', epoch = '', settings = {}, level = 0, words = '', hasKey = false },
  format = SWAP_FORMAT) {
  return hashKey(JSON.stringify([format, extension, epoch, settings, level, words, hasKey]));
}
