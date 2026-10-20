// Preferences, stored under chrome.storage.local["settings"]. The Gemini and Claude keys are stored apart from these, so
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
  if (['gemini-3.8-flash', 'gemini-3.5-flash-lite', 'claude-haiku-5-5'].includes(s.model)) d.model = s.model;
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

// Webmail, messaging, personal documents, AI chat, password managers, banking, payments, health portals, government
// sites and local or intranet addresses start off even when every site is on, so their text never goes to Gemini
// unless the user turns the site on from the popup. A listed domain covers its subdomains. (Wider list adapted from
// French Weave by Jackie Oliver, MIT.)
const OFF_DOMAINS = new Set([
  // webmail, messaging, personal documents
  'mail.google.com', 'outlook.live.com', 'outlook.office.com', 'outlook.office365.com', 'outlook.cloud.microsoft',
  'icloud.com', 'mail.aol.com', 'mail.zoho.com', 'fastmail.com', 'hey.com', 'tuta.com', 'mail.proton.me',
  'mail.yahoo.com', 'messenger.com', 'web.whatsapp.com', 'messages.google.com', 'chat.google.com', 'web.telegram.org',
  'discord.com', 'app.slack.com', 'teams.microsoft.com', 'teams.live.com', 'docs.google.com', 'drive.google.com',
  'calendar.google.com', 'contacts.google.com', 'onedrive.live.com',
  // AI chat
  'claude.ai', 'chatgpt.com', 'chat.openai.com', 'gemini.google.com', 'aistudio.google.com', 'copilot.microsoft.com',
  'perplexity.ai', 'poe.com', 'chat.mistral.ai', 'chat.deepseek.com', 'grok.com',
  // password managers
  'proton.me', '1password.com', 'bitwarden.com', 'lastpass.com', 'dashlane.com', 'keepersecurity.com',
  // banking, payments, brokerage, credit
  'paypal.com', 'venmo.com', 'cash.app', 'wise.com', 'revolut.com', 'monzo.com', 'chase.com', 'wellsfargo.com',
  'citi.com', 'capitalone.com', 'americanexpress.com', 'discover.com', 'ally.com', 'sofi.com', 'chime.com', 'pnc.com',
  'schwab.com', 'fidelity.com', 'vanguard.com', 'robinhood.com', 'coinbase.com', 'creditkarma.com', 'intuit.com',
  'hsbc.com', 'barclays.co.uk', 'santander.co.uk', 'natwest.com', 'lloydsbank.com', 'mercadopago.com', 'nubank.com.br',
  // health portals
  'kp.org', 'followmyhealth.com', 'healow.com', 'athenahealth.com', 'onemedical.com', 'nhs.uk',
]);
// Hostnames that name a bank, credit union or patient portal (bankofamerica.com, mychart.example.org).
const OFF_WORDS = /bank|creditunion|mychart|patient/;
export function offByDefault(hostname) {
  const host = String(hostname).toLowerCase().replace(/\.$/, '');
  const labels = host.split('.');
  return labels.some((_, i) => OFF_DOMAINS.has(labels.slice(i).join('.'))) ||
    OFF_WORDS.test(labels.slice(0, -1).join('.')) ||
    // No dot: an intranet name like http://wiki/ (IPv6 literals start with "[" and are off too).
    !host.includes('.') || host === '0.0.0.0' || host.startsWith('[') ||
    /\.(gov|mil|bank|insurance)$/.test(host) || /\.(gov|gob|gouv|govt|gv|mil)\.[a-z]{2}$/.test(host) || /\.gc\.ca$/.test(host) ||
    /\.(local|localhost|internal|lan|test|home\.arpa|ts\.net|corp|home|localdomain|intranet|private)$/.test(host) ||
    /^(127|10)\.\d+\.\d+\.\d+$/.test(host) || /^(192\.168|169\.254)\.\d+\.\d+$/.test(host) ||
    /^172\.(1[6-9]|2\d|3[01])\.\d+\.\d+$/.test(host) || /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+$/.test(host);
}

// `settings` here has newSitesEnabled resolved to a boolean (see newSitesDefault). A popup choice wins.
export function siteOn(settings, hostname) {
  const host = String(hostname).toLowerCase().replace(/\.$/, ''); // "example.com." is the same site
  const override = Object.hasOwn(settings.siteOverrides, host) ? settings.siteOverrides[host] : undefined;
  return override ?? (settings.newSitesEnabled && !offByDefault(host));
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
