// Claude Messages API call, the paid alternative to Gemini (French Weave measured Claude Haiku 5.5 at about 2% bad
// swaps against about 15% for its Gemini default). No chrome APIs; fetch is injectable for tests.
import { parseSwapsResponse } from './gemini.js';

export const CLAUDE_MODELS = { 'claude-haiku-5-5': 'Claude Haiku 5.5 (Claude key)' };
export const isClaude = (model) => Object.hasOwn(CLAUDE_MODELS, model);
export const CLAUDE_URL = 'https://api.anthropic.com/v1/messages';
export const CLAUDE_EFFORT = 'low'; // swaps are a short, routine judgment; low keeps each call cheap and fast

// Structured outputs need every object closed (additionalProperties: false), which Gemini's schema doesn't say.
const closed = (schema) => {
  if (!schema || typeof schema !== 'object') return schema;
  const out = Array.isArray(schema) ? schema.map(closed) : Object.fromEntries(Object.entries(schema).map(([k, v]) => [k, closed(v)]));
  if (out.type === 'object') out.additionalProperties = false;
  return out;
};

export function buildClaudeRequest({ model, system, user, schema, effort = CLAUDE_EFFORT }) {
  return {
    model,
    max_tokens: 16000,
    system,
    messages: [{ role: 'user', content: user }],
    output_config: { effort, format: { type: 'json_schema', schema: closed(schema) } },
  };
}

// Returns Map<id, swaps[]>. Throws on HTTP error, timeout, a refusal, or unparseable output. Only the status and a
// short fixed reason are kept from an error, never the body, so nothing stored or shown can carry the key.
export async function callClaude({ fetchImpl = globalThis.fetch, apiKey, body, timeoutMs = 20000 }) {
  const res = await fetchImpl(CLAUDE_URL, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'anthropic-dangerous-direct-browser-access': 'true', // the key is the reader's own, kept in extension storage
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) {
    const reason = { 401: 'Claude key was refused', 403: 'Claude key was refused', 402: 'Claude account has no credit',
      429: 'Claude rate limit', 529: 'Claude is overloaded' }[res.status];
    const error = new Error(reason ? `HTTP ${res.status} (${reason})` : `HTTP ${res.status}`);
    error.status = res.status;
    const delay = Number(res.headers?.get?.('retry-after'));
    if (delay > 0) error.retryAfterMs = Math.min(delay, 600) * 1000;
    // A refused key or an empty account won't fix itself in a minute: wait an hour unless a new key is saved.
    if ([401, 402, 403].includes(res.status)) error.retryAfterMs = 3600000;
    throw error;
  }
  const data = await res.json();
  if (data?.stop_reason === 'refusal') throw new Error('Claude declined this batch');
  const text = (data?.content || []).filter((b) => b?.type === 'text').map((b) => b.text || '').join('');
  return parseSwapsResponse(text);
}
