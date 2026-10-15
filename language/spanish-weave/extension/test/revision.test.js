import { test, expect } from 'bun:test';
import { swapRevision, SWAP_FORMAT } from '../src/revision.js';

test('revision: the swap format, the extension version and every swap input change it', () => {
  const parts = { extension: '0.2.0', epoch: 'e1', settings: { level: 'auto' }, level: 2, words: 'v1', paused: false, hasKey: true,
    origins: ['https://x.com/*'] };
  const base = swapRevision(parts);
  expect(swapRevision({ ...parts })).toBe(base);
  expect(swapRevision(parts, SWAP_FORMAT + 1)).not.toBe(base);
  const changes = { extension: '0.3.0', epoch: 'e2', settings: { level: '1' }, level: 1, words: 'v2', paused: true, hasKey: false,
    origins: [] };
  for (const [name, value] of Object.entries(changes)) expect([name, swapRevision({ ...parts, [name]: value })]).not.toEqual([name, base]);
});
