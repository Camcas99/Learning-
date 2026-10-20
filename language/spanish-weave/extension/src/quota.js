// Daily cap on Gemini calls, so pages that keep changing their text can't use up the key's quota. No one site may use
// more than SITE_SHARE of it, so a busy or hostile page stops only its own Spanish, never every site's. The record
// starts over each day.
import { localDay } from './hostsource.js';

export const DAILY_MODEL_CALLS = 1000;
export const SITE_SHARE = 0.5;
const KEY = 'modelCalls';

async function today(storage, day) {
  const { [KEY]: used } = await storage.get([KEY]);
  return used?.day === day ? used : { day, count: 0, sites: {} };
}

export async function callsToday(storage, day = localDay()) {
  return (await today(storage, day)).count;
}

export async function siteCallsToday(storage, host, day = localDay()) {
  return (await today(storage, day)).sites?.[host] || 0;
}

// The reason no call may be made now for this host, or '' when one may.
export async function quotaError(storage, host, day = localDay()) {
  const used = await today(storage, day);
  if (used.count >= DAILY_MODEL_CALLS) return `Daily limit of ${DAILY_MODEL_CALLS} model calls reached; Spanish resumes tomorrow`;
  if ((used.sites?.[host] || 0) >= DAILY_MODEL_CALLS * SITE_SHARE) {
    return `This site used its share of today's ${DAILY_MODEL_CALLS} model calls; Spanish resumes here tomorrow`;
  }
  return '';
}

export async function countCall(storage, day = localDay(), host = '') {
  const used = await today(storage, day);
  const sites = { ...used.sites };
  if (host) sites[host] = (sites[host] || 0) + 1;
  await storage.set({ [KEY]: { day, count: used.count + 1, sites } });
}
