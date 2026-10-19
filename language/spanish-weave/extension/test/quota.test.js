import { expect, it } from 'bun:test';
import { DAILY_MODEL_CALLS, SITE_SHARE, callsToday, countCall, quotaError, siteCallsToday } from '../src/quota.js';
import { memoryStorage } from '../src/cache.js';

it('counts model calls per day and starts over the next day', async () => {
  const storage = memoryStorage();
  expect(await callsToday(storage, '2026-10-14')).toBe(0);
  for (let i = 0; i < DAILY_MODEL_CALLS; i++) await countCall(storage, '2026-10-14');
  expect(await callsToday(storage, '2026-10-14')).toBe(DAILY_MODEL_CALLS);
  expect(await callsToday(storage, '2026-10-15')).toBe(0);
  await countCall(storage, '2026-10-15');
  expect(await callsToday(storage, '2026-10-15')).toBe(1);
});

it('caps each site at its share of the day, so one page can\'t stop Spanish everywhere', async () => {
  const storage = memoryStorage();
  const day = '2026-10-14';
  for (let i = 0; i < DAILY_MODEL_CALLS * SITE_SHARE; i++) await countCall(storage, day, 'busy.example');
  expect(await siteCallsToday(storage, 'busy.example', day)).toBe(DAILY_MODEL_CALLS * SITE_SHARE);
  expect(await quotaError(storage, 'busy.example', day)).toContain("This site used its share of today's");
  expect(await quotaError(storage, 'x.com', day)).toBe('');
  for (let i = 0; i < DAILY_MODEL_CALLS * (1 - SITE_SHARE); i++) await countCall(storage, day, 'x.com');
  expect(await quotaError(storage, 'x.com', day)).toContain('Daily limit');
  expect(await quotaError(storage, 'x.com', '2026-10-15')).toBe(''); // a new day starts over
  expect(await siteCallsToday(storage, 'busy.example', '2026-10-15')).toBe(0);
});
