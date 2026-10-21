// One batch, one model call (fallback model once on failure), validated swaps out.
import { buildSystemPrompt, buildUserContent, RESPONSE_SCHEMA } from './prompt.js';
import { buildRequest, callGemini, FALLBACK_MODEL } from './gemini.js';
import { buildClaudeRequest, callClaude, isClaude } from './anthropic.js';
import { validateSwaps, capSwaps } from './levels.js';

// cooldown: Map<model, until ms>. Rate-limited or overloaded models are skipped until then, so the
// free tier's per-minute limit does not cost every batch a failed request before the fallback.
export const COOLDOWN_MS = { 429: 60000, 503: 30000, timeout: 30000 };

// When a model with a spent daily quota may be asked again, in the reader's own time ("5:01 AM").
export const resumeAt = (ms) => new Date(ms).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

// daily: Map<model, until ms> for models whose daily quota is spent. The caller keeps it in storage, since it outlives
// the worker; requestSwaps adds to it. apiKey: the Gemini key; claudeKey: the Claude key. A model whose key is missing
// is skipped, so Claude Haiku falls back to Gemini Flash-Lite when both keys are saved.
export async function requestSwaps({ apiKey, claudeKey, model, level, batch, words, shownToday, fetchImpl, timeoutMs, cooldown = new Map(), daily = new Map(), now = Date.now }) {
  const system = buildSystemPrompt(level, words, shownToday);
  const user = buildUserContent(batch);
  const body = buildRequest({ system, user, schema: RESPONSE_SCHEMA });
  const candidates = [model, ...(FALLBACK_MODEL[model] ? [FALLBACK_MODEL[model]] : [])]
    .filter((m) => (isClaude(m) ? claudeKey : apiKey));
  if (!candidates.length) throw new Error(isClaude(model) ? 'Add a Claude key for Claude Haiku' : 'Add a Gemini key');
  const spent = () => candidates.every((m) => daily.get(m) > now());
  const dailyError = () => {
    const until = Math.min(...candidates.map((m) => daily.get(m)));
    return Object.assign(new Error(`Gemini's daily quota for this key is used up; Spanish resumes at ${resumeAt(until)}`),
      { daily: true, retryAfterMs: Math.max(1000, until - now()) });
  };
  if (spent()) throw dailyError();
  const models = candidates.filter((m) => !(cooldown.get(m) > now()) && !(daily.get(m) > now()));
  const errors = [];
  if (!models.length) {
    const error = new Error('Model rate limit; retrying shortly');
    error.retryAfterMs = Math.max(1000, Math.min(...candidates.map((m) => Math.max(cooldown.get(m) || 0, daily.get(m) || 0))) - now());
    throw error;
  }
  for (const m of models) {
    try {
      const byId = isClaude(m)
        ? await callClaude({ fetchImpl, apiKey: claudeKey, body: buildClaudeRequest({ model: m, system, user, schema: RESPONSE_SCHEMA }), timeoutMs })
        : await callGemini({ fetchImpl, apiKey, model: m, body, timeoutMs, now });
      // Passages the reply leaves out are no results (the page retries them); one passage telling the model to skip
      // the others can't sink the whole batch. A reply with none of them counts as a failure.
      const results = {};
      for (const { id, text } of batch) {
        if (byId.has(id)) results[id] = capSwaps(level, validateSwaps(level, byId.get(id), words), text, words);
      }
      if (batch.length && !Object.keys(results).length) throw new Error('Incomplete model response');
      return { results, model: m, errors };
    } catch (e) {
      const timeout = e?.name === 'TimeoutError';
      const wait = e?.retryAfterMs || COOLDOWN_MS[timeout ? 'timeout' : e?.status];
      if (e?.daily) daily.set(m, now() + wait);
      else if (wait) cooldown.set(m, now() + wait);
      errors.push(`${m}: ${timeout ? 'timeout' : e?.daily ? 'daily quota used up' : e?.message || e}`);
    }
  }
  if (spent()) throw dailyError();
  const error = new Error(errors.join('; '));
  const until = candidates.map((m) => Math.max(cooldown.get(m) || 0, daily.get(m) || 0)).filter((t) => t > now());
  if (until.length === candidates.length) error.retryAfterMs = Math.max(1000, Math.min(...until) - now());
  throw error;
}
