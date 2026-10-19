// Preferences, stored under chrome.storage.local["settings"]. The Gemini key is stored apart from these, so
// the config pages get never carries it.
export const DEFAULT_SETTINGS = {
  enabled: true,
  model: 'gemini-3.8-flash',
  levelOverride: 0, // 0 = follow the Claude Code stage (Level 1 without the plugin)
  newSitesEnabled: null, // null = what setup chose (prefs.extension_sites); off until the native host answers
  newSitesAt: 0, // when newSitesEnabled was chosen in the popup (ms), so a later setup --sites can win
  siteOverrides: {}, // hostname -> true/false, set from the popup
  speak: false, // say a word aloud when its gloss shows (Alt+click speaks either way)
  genderColors: true, // tint noun underlines by gender, with masc./fem. in the gloss
};

// The only settings that change which swaps are chosen, so the only ones in the revision. The rest say where swaps
// run (on/off, site choices) or how they look or sound: content.js applies those in place, with no model calls.
export const swapSettings = (s) => ({ model: s.model, levelOverride: s.levelOverride });

export function cleanSettings(s = {}) {
  const d = { ...DEFAULT_SETTINGS, siteOverrides: {} };
  if (typeof s.enabled === 'boolean') d.enabled = s.enabled;
  if (typeof s.newSitesEnabled === 'boolean') d.newSitesEnabled = s.newSitesEnabled;
  if (Number.isFinite(s.newSitesAt) && s.newSitesAt >= 0) d.newSitesAt = s.newSitesAt;
  if (typeof s.speak === 'boolean') d.speak = s.speak;
  if (typeof s.genderColors === 'boolean') d.genderColors = s.genderColors;
  if (['gemini-3.8-flash', 'gemini-3.5-flash-lite'].includes(s.model)) d.model = s.model;
  if (Number.isInteger(s.levelOverride) && s.levelOverride >= 0 && s.levelOverride <= 4) d.levelOverride = s.levelOverride;
  for (const [host, enabled] of Object.entries(s.siteOverrides || {})) {
    if (/^(?=.{1,253}$)[a-z0-9]+(?:[a-z0-9.-]*[a-z0-9])?$/.test(host) && typeof enabled === 'boolean') d.siteOverrides[host] = enabled;
  }
  return d;
}

// The latest choice wins: the popup's, unless setup's --sites came after it (sitesAt, in seconds); then setup's
// answer ("ask" = off until turned on). With no word state from the native host (sites undefined), sites stay off
// until turned on, so a setup "ask" never quietly becomes every site.
export function newSitesDefault(settings, sites, sitesAt = 0) {
  const chosen = typeof settings.newSitesEnabled === 'boolean' && (settings.newSitesAt || 0) >= sitesAt * 1000;
  return chosen ? settings.newSitesEnabled : sites === 'all';
}

// Webmail, messaging, AI chat and local or intranet addresses start off even when every site is on, so their text
// never goes to Gemini unless the user turns the site on from the popup.
const OFF_HOSTS = new Set(['mail.google.com', 'outlook.live.com', 'outlook.office.com', 'outlook.office365.com',
  'outlook.cloud.microsoft', 'www.icloud.com', 'icloud.com', 'mail.aol.com', 'mail.zoho.com', 'app.fastmail.com',
  'app.tuta.com', 'mail.proton.me', 'mail.yahoo.com', 'www.messenger.com', 'messenger.com', 'web.whatsapp.com',
  'web.telegram.org', 'discord.com', 'app.slack.com', 'teams.microsoft.com', 'teams.live.com', 'claude.ai',
  'chatgpt.com', 'chat.openai.com', 'gemini.google.com', 'copilot.microsoft.com', 'www.perplexity.ai', 'chat.mistral.ai',
  'chat.deepseek.com', 'grok.com']);
export function offByDefault(hostname) {
  const host = hostname.replace(/\.$/, '');
  // No dot: an intranet name like http://wiki/ (IPv6 literals start with "[" and are off too).
  return OFF_HOSTS.has(host) || !host.includes('.') || host === '0.0.0.0' || host.startsWith('[') ||
    /\.(local|localhost|internal|lan|test|home\.arpa|ts\.net|corp|home|localdomain|intranet|private)$/.test(host) ||
    /^(127|10)\.\d+\.\d+\.\d+$/.test(host) || /^(192\.168|169\.254)\.\d+\.\d+$/.test(host) ||
    /^172\.(1[6-9]|2\d|3[01])\.\d+\.\d+$/.test(host) || /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+$/.test(host);
}

// `settings` here has newSitesEnabled resolved to a boolean (see newSitesDefault). A popup choice wins.
export function siteOn(settings, hostname) {
  return settings.siteOverrides[hostname] ?? (settings.newSitesEnabled && !offByDefault(hostname));
}

export function siteEnabled(settings, url) {
  try {
    const u = new URL(url);
    return /^https?:$/.test(u.protocol) && settings.enabled && siteOn(settings, u.hostname);
  } catch { return false; }
}

export function hasSiteAccess(url, origins = []) {
  try {
    const u = new URL(url);
    return origins.some((pattern) => {
      if (pattern === '<all_urls>') return /^https?:$/.test(u.protocol);
      const m = pattern.match(/^(https?|\*):\/\/([^/]+)\/\*$/);
      return m && (m[1] === '*' || u.protocol === m[1] + ':') &&
        (m[2] === '*' || u.host === m[2] || u.hostname === m[2] || (m[2].startsWith('*.') && (u.hostname === m[2].slice(2) || u.hostname.endsWith(m[2].slice(1)))));
    });
  } catch { return false; }
}
