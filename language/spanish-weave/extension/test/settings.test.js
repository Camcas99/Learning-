import { expect, it } from 'bun:test';
import { cleanSettings, newSitesDefault, siteEnabled, swapSettings } from '../src/settings.js';

it('speech starts off and gender colors on; only booleans are kept', () => {
  expect(cleanSettings()).toMatchObject({ speak: false, genderColors: true });
  expect(cleanSettings({ speak: true, genderColors: false })).toMatchObject({ speak: true, genderColors: false });
  expect(cleanSettings({ speak: 'yes', genderColors: 0 })).toMatchObject({ speak: false, genderColors: true });
});

it('only the model and level pick swaps, so display and site settings ask the model nothing', () => {
  expect(swapSettings(cleanSettings({ speak: true, genderColors: false }))).toEqual(swapSettings(cleanSettings()));
  expect(swapSettings(cleanSettings({ enabled: false, newSitesEnabled: false, siteOverrides: { 'a.example': false } })))
    .toEqual(swapSettings(cleanSettings()));
  expect(swapSettings(cleanSettings({ levelOverride: 2 }))).not.toEqual(swapSettings(cleanSettings()));
  expect(Object.keys(swapSettings(cleanSettings()))).toEqual(['model', 'levelOverride']);
});

it('webmail, AI chat and local addresses start off; a popup choice wins', () => {
  const every = { ...cleanSettings(), newSitesEnabled: true };
  for (const url of ['https://example.com/a', 'https://news.ycombinator.com/', 'http://172.32.0.1/', 'https://mail.example.com/', 'http://100.128.0.1/', 'https://1.1.1.1/'])
    expect(siteEnabled(every, url)).toBe(true);
  for (const url of ['https://mail.google.com/mail/u/0/', 'https://outlook.office.com/mail/', 'https://mail.proton.me/u/0',
    'https://claude.ai/chat/1', 'https://chatgpt.com/c/1', 'https://gemini.google.com/app', 'http://localhost:3000/',
    'http://127.0.0.1/', 'http://[::1]/', 'http://10.0.0.5/', 'http://172.16.4.2/', 'http://192.168.1.1/', 'http://printer.local/',
    'https://mail.google.com./', 'http://[::ffff:127.0.0.1]/', 'http://0.0.0.0:8000/', 'http://169.254.1.1/', 'http://100.100.1.1:4100/',
    'https://box.example.ts.net/', 'http://router.lan/', 'http://app.test/', 'http://svc.internal/'])
    expect(siteEnabled(every, url)).toBe(false);
  const chosen = cleanSettings({ siteOverrides: { 'mail.google.com': true, 'example.com': false, 'localhost': true } });
  const withChoices = { ...chosen, newSitesEnabled: true };
  expect(siteEnabled(withChoices, 'https://mail.google.com/mail/')).toBe(true);
  expect(siteEnabled(withChoices, 'http://localhost:8080/')).toBe(true);
  expect(siteEnabled(withChoices, 'https://example.com/')).toBe(false);
  expect(siteEnabled({ ...chosen, newSitesEnabled: false }, 'https://mail.google.com/')).toBe(true);
});

it('intranet names, more webmail and messaging apps start off too', () => {
  const every = { ...cleanSettings(), newSitesEnabled: true };
  for (const url of ['http://wiki/', 'http://jira:8080/browse/X-1', 'http://nas.home/', 'http://srv.corp/', 'http://box.localdomain/',
    'http://hr.intranet/', 'http://files.private/', 'https://outlook.cloud.microsoft/mail/', 'https://www.icloud.com/mail/',
    'https://www.messenger.com/t/1', 'https://web.whatsapp.com/', 'https://app.slack.com/client/T1', 'https://discord.com/channels/1/2'])
    expect([url, siteEnabled(every, url)]).toEqual([url, false]);
  expect(siteEnabled(every, 'https://example.com/')).toBe(true);
  expect(siteEnabled(every, 'https://homes.example.com/')).toBe(true);
});

it('setup and the popup site choice: the latest wins; with no word state from the host, sites start off', () => {
  const setupAt = 1_800_000_000; // seconds, as setup stores prefs.extension_sites_at
  const popup = (on, at) => cleanSettings({ newSitesEnabled: on, newSitesAt: at });
  expect(newSitesDefault(popup(true, setupAt * 1000 - 60000), 'ask', setupAt)).toBe(false); // popup first, then setup
  expect(newSitesDefault(popup(false, setupAt * 1000 - 60000), 'all', setupAt)).toBe(true);
  expect(newSitesDefault(popup(true, setupAt * 1000 + 60000), 'ask', setupAt)).toBe(true); // setup first, then popup
  expect(newSitesDefault(popup(false, setupAt * 1000 + 60000), 'all', setupAt)).toBe(false);
  expect(newSitesDefault(popup(true, 5), 'ask')).toBe(true); // a setup from before it was timed loses to any choice
  expect(newSitesDefault(cleanSettings(), 'ask', setupAt)).toBe(false);
  expect(newSitesDefault(cleanSettings(), 'all', setupAt)).toBe(true);
  expect(newSitesDefault(cleanSettings(), undefined)).toBe(false); // the host never answered
  expect(newSitesDefault(popup(true, 5), undefined)).toBe(true);
  expect(cleanSettings({ newSitesAt: -1 }).newSitesAt).toBe(0);
  expect(cleanSettings({ newSitesAt: 'soon' }).newSitesAt).toBe(0);
  expect(cleanSettings({ newSitesAt: 12.5 }).newSitesAt).toBe(12.5);
});
