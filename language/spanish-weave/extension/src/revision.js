// The swap revision. Pages tag every request with it and cached swaps are keyed by it, so anything that can change
// swaps must change it. Display-only settings (speech, gender colors) stay out, so toggling them costs no model calls.
import { hashKey } from './hash.js';

// Bump when cached swaps gain fields or the prompt's sense rules change, so old ones are refetched
// (2: noun gender gn, usage note n; 3: sense rules for es, esto/eso, question words, sino).
export const SWAP_FORMAT = 3;

// extension: the extension's version, so an update that edits the bundled word list or notes refetches too.
// words: the plugin's word-state version (statuses, glosses, hints and notes), when the native host is there.
export function swapRevision({ extension = '', epoch = '', settings = {}, level = 0, words = '', paused = false, hasKey = false, origins = [] }, format = SWAP_FORMAT) {
  return hashKey(JSON.stringify([format, extension, epoch, settings, level, words, paused, hasKey, origins]));
}
