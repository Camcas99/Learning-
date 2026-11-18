// Spanish in text messages without a model: the list words a message's English can take, by the rules in
// chatrules.js, at about the extension's density (one swap in ten words, two a sentence, each list word once). It runs
// where the message is read, with no network and no key, and leaves one-time codes and serious topics in English.
// Pure: no DOM.
import { allCaps, exactEs, isZeroSpanish } from './levels.js';
import { CHAT_RULES } from './chatrules.js';

// Statuses that weave: learning and shaky words first, then known ones. Words not introduced yet never show.
const RANK = { shaky: 0, active: 0, known: 1 };
// Longer messages stay English: nobody reads an essay as a text, and it bounds the work on odd input.
const MAX_LENGTH = 4000;

// Links, addresses, handles and code are opaque: never swapped, and no phrase runs across them. A link stops before
// punctuation that ends its sentence. Email and domain matches only start at the start of a run, so a long run of
// dots or hyphens is scanned once. Words keep inner apostrophes and hyphens ("don't", "so-so"), so a compound never
// matches one of its parts, and start with a letter or digit, so an emoji's variation selector is not a word.
const TRAIL = String.raw`(?=[.,!?…:;)\]"'’]*(?:\s|$))`;
const JOIN = String.raw`['’\-‐‑]`;
const TOKEN = new RegExp([
  String.raw`(?<opaque>(?:https?:\/\/|www\.)\S+?${TRAIL}|`
    + String.raw`(?<![\p{L}\p{N}._%+-])[\p{L}\p{N}._%+-]+@[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)+|`
    + String.raw`(?<![\p{L}\p{N}.-])[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)*\.(?:com|org|net|io|co|app|ly|gg|tv|edu|gov|us|uk|ca|dev)`
    + String.raw`(?![\p{L}\p{N}])(?:\/\S*?${TRAIL})?|[@#][\p{L}\p{N}_]+|\x60[^\x60]*\x60)`,
  String.raw`(?<word>[\p{L}\p{N}][\p{L}\p{M}\p{N}]*(?:${JOIN}[\p{L}\p{N}][\p{L}\p{M}\p{N}]*)*)`,
  String.raw`(?<space>[^\S\n]+)`,
  String.raw`(?<line>\n)`,
  String.raw`(?<mark>.)`,
].join('|'), 'gsu');
// A word joined to one of these is part of something else ("and/or", "R&B", "x+y"), so it stays as written.
const GLUE = /^[/&+=*_~|\\<>^%]$/;
const SENTENCE_END = /^[.!?…]$/;
// A period after these, or after a single letter ("a.m.", "U.S."), or inside a number, ends no sentence.
const ABBREVIATION = new Set(['mr', 'mrs', 'ms', 'dr', 'st', 'vs', 'jr', 'sr', 'etc', 'eg', 'ie', 'approx', 'ft', 'mt', 'ave',
  'blvd', 'inc', 'ltd', 'prof', 'sgt', 'capt', 'gen', 'lt']);
const NEGATIVE = /^(?:not|no|never|nothing|nobody|none|nowhere|neither|nor|cannot|without|hardly|barely|rarely|seldom|dont|doesnt|didnt|cant|wont|isnt|arent|wasnt|werent|havent|hasnt|hadnt|couldnt|shouldnt|wouldnt|aint)$|n't$/;
// "not red but blue": only these count as the negative sino corrects, not a reply's "no, but".
const STRICT_NEGATIVE = /^(?:not|never|dont|doesnt|didnt|cant|wont|isnt|arent|wasnt|werent)$|n't$/;
const NUMBER = /^\p{N}+$/u;
const YEAR = /^(?:19|20)\p{N}{2}$/u;
// How a sentence typed without its "?" still opens as a question: "do you", "when are you", "need anything".
const QUESTION_FIRST = new Set(['do', 'does', 'did', 'is', 'are', 'was', 'were', 'can', 'could', 'would', 'will', 'should',
  'shall', 'have', 'has', 'had', 'am', 'want', 'wanna', 'need', 'any', 'anything', 'u', 'r', "how's", "what's", "where's",
  "who's", "when's", "why's"]);
const WH = new Set(['who', 'what', 'when', 'where', 'why', 'how', 'which', 'whose']);
const QUESTION_SECOND = new Set(['are', 'is', 'was', 'were', 'do', 'does', 'did', 'can', 'could', 'would', 'will', 'should',
  'have', 'has', 'had', 'am', 'u', 'r', 'ur']);
// A plural subject earlier in the clause: a Spanish adjective after it would need its plural.
const PLURAL = new Set(['we', 'they', 'these', 'those', 'guys', 'both', "y'all", 'yall', "we're", "they're", "we've",
  "they've", 'ppl', 'people', 'kids', 'parents', 'men', 'women', 'children', 'things']);
// A plural noun before one of these: "the kids are", "things look".
const ARE = new Set(['are', 'were', "aren't", "weren't", 'look', 'seem', 'feel', 'sound', 'get', 'got']);
const NOT_PLURAL_S = new Set(['this', 'his', 'its', 'is', 'was', 'us', 'yes', 'bus', 'gas', 'plus', 'always', 'less', 'class',
  'boss', 'glass', 'miss', 'news', 'thus', 'unless', 'kiss', 'dress', 'mess', 'guess', 'address', 'pass']);

// ---- whole-message skips ----

// One-time codes. A code-like number is four to eight digits, or digits in groups (123 456, 12-34-56, 4 8 2 9 1 3),
// but not a price or a decimal. It counts with a word that names a code anywhere in the message, or right after
// "enter", "use", "PIN" or "code is". Codes with letters count after a code word. "zip code" and "area code" don't.
const SEP = String.raw`[\s  \-‐-―]`;
const NUM = String.raw`(?<![\p{N}$€£¥.,:])(?:\p{N}{4,8}|\p{N}{3}${SEP}\p{N}{3}|\p{N}{2}${SEP}\p{N}{2}${SEP}\p{N}{2}|`
  + String.raw`\p{N}(?:${SEP}\p{N}){5,7})(?!\p{N})`;
const NOT_A_CODE = String.raw`(?<!\b(?:zip|area|dress|postal|post|country|color|colour|morse|source|bar|qr)\s)`;
const CODE_NUMBER = new RegExp(NUM, 'u');
const CODE_WORD = new RegExp(String.raw`${NOT_A_CODE}\bcodes?\b|\bpasscodes?\b|\bpasswords?\b|\botp\b|\b2fa\b|`
  + String.raw`\btwo[- ]factor\b|\bone[- ]time\b|\bverif\w*|\bauthenticat\w*|\bauthoriz\w*|\btokens?\b|`
  + String.raw`\btemporary (?:id|code|pin|password)\b|\bapproval (?:number|code)\b|\bsecurity code\b|\bsafekey\b|`
  + String.raw`\b(?:do not|don't|never) (?:share|give)\b|\baccess (?:number|code)\b|\bexpires? in \p{N}+ ?min\w*`, 'iu');
const CODE_FRAME = new RegExp(String.raw`\b(?:enter|use|type|input|reply with)\s+(?:(?:the )?code\s+)?${NUM}|`
  + String.raw`${NOT_A_CODE}\b(?:pin|code|otp|passcode)\s*(?:is|was|:|=|#)?\s*${NUM}`, 'iu');
const CODE_MIXED = /(?<!\b(?:zip|area)\s)\b(?:codes?|passcodes?|passwords?|pin|otp|key|token)\b(?:\s+(?:is|was))?\s*[:=]?\s*((?:[\p{L}\p{N}]+-)*[\p{L}\p{N}]+)(?![\p{L}\p{N}])/iu;
const CODE_CAPS = /\b(?:codes?|passcodes?|pin|otp)\b(?:\s+(?:is|was))?\s*[:=]?\s*(\p{L}{4,})(?![\p{L}\p{N}])/iu;
const CODE_ALONE = /\b\p{Lu}{1,3}-\p{N}{5,8}\b/u;
const CODE_LINK = /(?:\b(?:sign|log)[- ]?in\b|\bverify\b|\bmagic link\b|\breset your password\b)[^\n]{0,80}?(?:https?:\/\/|www\.)\S+|[?&](?:token|code|otp|key|auth)=/i;

// Everyday phrases that only sound serious, taken out before the topic check: "I'm dying laughing", "my phone is
// dead", "not urgent", "a hair appointment".
const NOT_SERIOUS = new RegExp([
  String.raw`\b(?:i'm|im|i am|i was|we're|i literally|i just|i|literally) (?:dead|dying|died|deceased)\b(?=[^\n]*(?:😂|🤣|💀|😭|\blo+l\b|\blo+l(?:o+l)+\b|\blmf?ao|\bhaha|\blaugh))`,
  String.raw`\b(?:scared|bored|freaked|worried|annoyed|love|loved|tickled) (?:me |myself |you |him |her |them )?to death\b`,
  String.raw`\bshooting (?:my|his|her|your) shot\b|\bwalking dead\b|\bgrateful dead\b|\bdead by daylight\b`,
  String.raw`\bflood(?:ed|ing|s)? with (?:notifications|messages|texts|calls|emails|requests|orders|likes)\b`,
  String.raw`\b(?:got|we|they|were|was|get) robbed\b(?=[^\n]*\b(?:refs?|umps?|referees?|call|calls)\b)`,
  String.raw`\b(?:dying|died|dead) (?:laughing|of laughter|of embarrassment|inside)\b`,
  String.raw`\bdead (?:tired|serious|set|end|last|center|wrong|asleep)\b`,
  String.raw`\b(?:phone|battery|laptop|game|party|bar|place|club|town|chat|mall|vibe|iphone|airpods|charger|controller|plant|plants|show|thread)(?: is| was|'s)? (?:totally |so |completely |kinda |basically )?(?:dead|dying|died)\b`,
  String.raw`\bdying (?:for|to|my hair|her hair|his hair)\b`,
  String.raw`\b(?:not|nothing|no) urgent\b|\bno rush\b`,
  String.raw`\btriple threat\b`,
  String.raw`\bdriving me (?:crazy|nuts|insane|mad|up the wall)\b`,
  String.raw`\b(?:hair|nail|nails|lash|brow|wax|tattoo|massage) appointments?\b`,
  String.raw`\bshooting (?:hoops|pool|a video|the breeze|stars?)\b`,
  String.raw`\binvested (?:so much |a lot of |all this )?(?:time|energy|effort)\b`,
  String.raw`\b(?:ice cream|snack|fashion|pizza|coffee|chocolate) emergency\b`,
  String.raw`\bdriving (?:test|lessons?|school|range|license|permit)\b`,
].join('|'), 'giu');
// Topics that stay English in a friend's message, on top of the extension's list (levels.js isZeroSpanish): death and
// grief, self-harm, illness and injury, violence, accidents and disasters, police and courts, money trouble, driving.
const SERIOUS = new RegExp([
  String.raw`\b(?:died|dies|dying|dead|death|deaths|funerals?|burial|memorial service|hospice|miscarr\w*|stillborn|condolences|rest in peace)\b`,
  String.raw`\bpassed (?:away|on|this morning|last night|yesterday|today|peacefully|in (?:his|her|their) sleep)\b`,
  String.raw`\blost (?:my |our |his |her |their )?(?:mom|mother|dad|father|grandma|grandpa|grandmother|grandfather|brother|sister|son|daughter|husband|wife|baby|uncle|aunt|cousin|best friend|dog|cat)\b(?!')`,
  String.raw`\bsorry for your loss\b`,
  String.raw`\bsuicid\w*|\bkill (?:myself|yourself|himself|herself|themselves)\b|\b(?:want|wanna|going|gonna|ready)(?: to)? die\b`,
  String.raw`(?<!\p{N}\s?)\bkms\b|\bkys\b|\bend (?:it all|my life)\b|\b(?:don't|dont|do not) want to (?:live|be alive|be here anymore|exist)\b`,
  String.raw`\bself[- ]harm\w*|\bhurt(?:ing)? (?:myself|himself|herself|themselves)\b|\bcut(?:ting)? myself\b|\boverdos\w*`,
  String.raw`\bheart attack\b|\bstroke\b(?! of)|\bemergency room\b|\btested positive\b|\bcovid\b|\bbiops\w*|\bfever\b|\bseizures?\b`,
  String.raw`\bpanic attacks?\b|\bdepressed\b|\bdepression\b|\banxiety attacks?\b|\bconcussion\b|\bfood poisoning\b`,
  String.raw`\bbroke (?:my|his|her|their) (?:arm|leg|wrist|ankle|foot|hand|nose|back|hip|ribs?|neck)\b`,
  String.raw`\b(?:got|getting|feel|feeling|felt|i'm|im|am|been|be|he's|she's|he is|she is|they're|we're) sick\b(?! of)`,
  String.raw`\bthrowing up\b|\bthrew up\b|\bin (?:so much )?pain\b`,
  String.raw`\b(?:back|head|leg|arm|knee|stomach|chest|tooth|ear|throat) (?:hurts|is killing me)\b`,
  String.raw`\b(?:got|is|was|been|badly|seriously|really) (?:hurt|injured)\b|\binjur\w*|\bbleeding\b|\bambulance\b|\bparamedics?\b`,
  String.raw`\bx-?rays?\b|\bstitches\b|\brehab\b|\brelapse\w*`,
  String.raw`\brap(?:e|ed|es|ist)\b|\bharass\w*|\bmolest\w*|\bgrop(?:e|ed|ing)\b|\bdomestic violence\b|\brestraining order\b`,
  String.raw`\babus\w*|\bassault\w*|\bhitting me\b(?! up)|\bstabb\w*|\bgunshots?\b|\bshooter\b|\bshooting\b|\bthreaten\w*`,
  String.raw`\b(?:he|she|they|my (?:ex|dad|mom|husband|wife|boyfriend|girlfriend|bf|gf|partner)) (?:hit|hits|keeps hitting|punched|slapped|choked|kicked|beat|beats|pushed|shoved) me\b(?! (?:up|at|in|to)\b)`,
  String.raw`\b(?:got|was|been|were|get) (?:shot|stabbed|jumped|attacked)\b|\bdeath threats?\b|\bstalking me\b|\bstalker\b|\bbeing stalked\b`,
  String.raw`(?<!\b(?:by|on|happy|little) )\baccidents?\b|\bcrash(?:ed)? (?:into|my car|the car|his car|her car|our car)\b|\bcar crash\b`,
  String.raw`\brear[- ]ended\b|\btotaled\b|\b(?:house|apartment|building|kitchen) (?:is )?on fire\b`,
  String.raw`\bfire in (?:the|our|my|his|her) (?:building|house|apartment)\b|\bflood(?:ed|ing)\b|\bbroke into\b|\bbreak[- ]in\b`,
  String.raw`\brobbed\b(?! by the (?:refs?|umps?|referees?))|\bmugged\b|\bburglar\w*|\blockdown\b|\bevacuat\w*`,
  String.raw`\b(?:i|we) (?:really |seriously )?need help\b(?! with| \w+ing\b| to\b)|\bhelp\s*!+`,
  String.raw`\bhelp me\b(?! (?:pick|choose|find|decide|move|plan|cook|with|out|understand|figure|carry|set|think|get|write|lol|pls|please|remember|come|name))`,
  String.raw`\bmissing person\b|\bamber alert\b`,
  String.raw`\barrest\w*|\bjail\w*|\bprison\b|\bbail (?:money|out|hearing|bond)\b|\bpost(?:ed)? bail\b`,
  String.raw`\b(?:have|got|go to|going to|went to|in|missed|missing) court\b|\bwarrant\b|\bprobation\b|\bparole\b|\bdeport\w*`,
  String.raw`\bimmigration\b|\bdetained\b|\bpulled over\b|\bofficers?\b|\bsheriff\b|\bhandcuff\w*|\bcharged with\b|\bpolice\b`,
  String.raw`\bcops\b|\b(?:a|the|that|this) cop\b|\blawsuit\b|\bsued\b|\bsuing\b`,
  String.raw`\b(?:got|been|was|get|getting) fired\b|\bfired me\b|\bunemploy\w*|\bevict\w*|\bdebt\b|\boverdra\w*|\bbankrupt\w*`,
  String.raw`\brepossess\w*|\bforeclos\w*|\blend me (?:some )?(?:money|cash|\$?\p{N}+)|\bcan't (?:pay|afford) (?:the |my )?(?:rent|bills)\b`,
  String.raw`\blost my job\b|\blaid off\b|\bbehind the wheel\b|\b(?:i'm|im|i am) on the road\b`,
  String.raw`\bcall me (?:now|asap|right now|back asap)\b|\burgent(?:ly)?\b|\b911\b`,
].join('|'), 'iu');
// Capitalized only: "ER" and "ICU", not the filler "er"; "RIP" and "ICE" the agency, not "rip" and "ice".
const SERIOUS_CAPS = /\b(?:ER|ICU|RIP|ICE)\b/u;

// Why a message stays English as a whole: 'code', 'topic', 'long', or '' when it may be woven.
export function skipReason(text) {
  const t = String(text).replace(/[’‘]/g, "'");
  if (t.length > MAX_LENGTH) return 'long';
  const caps = CODE_CAPS.exec(t);
  // A code with letters has a digit and a letter and at least four characters: K7XQ9P, LKQ-7MP.
  const mixed = CODE_MIXED.exec(t)?.[1].replace(/-/g, '') || '';
  const lettersAndDigits = mixed.length >= 4 && /\p{N}/u.test(mixed) && /\p{L}/u.test(mixed);
  if (CODE_ALONE.test(t) || CODE_LINK.test(t) || lettersAndDigits || CODE_FRAME.test(t)
    || (caps && caps[1] === caps[1].toUpperCase() && /\p{Lu}/u.test(caps[1]))
    || (CODE_WORD.test(t) && CODE_NUMBER.test(t))) return 'code';
  const plain = t.replace(NOT_SERIOUS, ' ');
  if (isZeroSpanish(plain) || SERIOUS.test(plain) || SERIOUS_CAPS.test(plain)) return 'topic';
  return '';
}

// ---- reading a message ----

const lower = (s) => s.toLowerCase().replace(/’/g, "'").replace(/[‐‑]/g, '-');

// The words of a message with what a rule may ask about each: the token on either side (a word, a mark, or START and
// END at the text's edges and line breaks), its sentence and clause, whether it is glued to a symbol, whether its
// sentence is a question, and where the last negative before it in its clause is.
function analyze(text) {
  const toks = [];
  for (const m of text.matchAll(TOKEN)) {
    toks.push({ kind: Object.keys(m.groups).find((k) => m.groups[k] !== undefined), text: m[0], at: m.index });
  }
  const isWord = (n) => n && (n.kind === 'word' || n.kind === 'opaque');
  const words = [];
  const sentQ = [false];
  let sent = 0;
  let clause = 0;
  for (let t = 0; t < toks.length; t++) {
    const tok = toks[t];
    if (isWord(tok)) {
      const glued = [toks[t - 1], toks[t + 1]].some((n) => n && (n.kind === 'opaque' || (n.kind === 'mark' && GLUE.test(n.text))));
      words.push({ t, text: tok.text, low: lower(tok.text), opaque: tok.kind === 'opaque', glued, sent, clause });
      continue;
    }
    if (tok.kind === 'space' || (tok.kind === 'mark' && GLUE.test(tok.text))) continue;
    if (tok.text === '.') {
      const before = toks[t - 1];
      const after = toks[t + 1];
      if (before?.kind === 'word' && (ABBREVIATION.has(lower(before.text)) || [...before.text].length === 1)) continue;
      if (before?.kind === 'word' && after?.kind === 'word' && NUMBER.test(before.text) && NUMBER.test(after.text)) continue;
    }
    clause++;
    if (tok.text === '?') sentQ[sent] = true;
    if (tok.kind === 'line' || SENTENCE_END.test(tok.text)) {
      sent++;
      sentQ[sent] = false;
    }
  }
  const side = (t, step) => {
    for (let k = t + step; k >= 0 && k < toks.length; k += step) {
      const n = toks[k];
      if (n.kind === 'space') continue;
      if (n.kind === 'line') break;
      return n.kind === 'mark' ? n.text : lower(n.text);
    }
    return step < 0 ? 'START' : 'END';
  };
  // The next word as written, to tell a name ("but Sam can") from a common word.
  const rawAfter = (t) => {
    for (let k = t + 1; k < toks.length; k++) {
      if (toks[k].kind === 'space') continue;
      return toks[k].kind === 'word' ? toks[k].text : '';
    }
    return '';
  };
  const firstOf = new Map();
  let lastNeg = -1;
  let lastStrict = -1;
  words.forEach((w, k) => {
    w.k = k;
    w.before = side(w.t, -1);
    w.after = side(w.t, 1);
    w.afterRaw = rawAfter(w.t);
    if (!w.opaque && !firstOf.has(w.sent)) firstOf.set(w.sent, k);
    w.first = firstOf.get(w.sent) === k;
    if (k > 0 && words[k - 1].clause !== w.clause) [lastNeg, lastStrict] = [-1, -1];
    w.negBefore = lastNeg;
    w.strictNegBefore = lastStrict;
    if (NEGATIVE.test(w.low)) lastNeg = k;
    if (STRICT_NEGATIVE.test(w.low)) lastStrict = k;
  });
  // A sentence is a question with a "?", or when it opens like one: "do you", "when are you", "when you coming".
  for (const [s, k] of firstOf) {
    const [a, b, c] = [0, 1, 2].map((d) => (words[k + d]?.sent === s ? words[k + d].low : ''));
    if (QUESTION_FIRST.has(a) || (WH.has(a) && (QUESTION_SECOND.has(b) || (/^(?:you|we|they|he|she|i|u)$/.test(b) && c.endsWith('ing'))))) {
      sentQ[s] = true;
    }
  }
  for (const w of words) w.question = Boolean(sentQ[w.sent]);
  return { toks, words };
}

const isEdge = (tok) => tok === 'START' || tok === 'END' || !/[\p{L}\p{N}]/u.test(tok);

function compileSet(spec) {
  if (spec === undefined) return null;
  const words = new Set();
  const suffixes = [];
  for (const item of String(spec).split('|')) {
    if (item.startsWith('*')) suffixes.push(item.slice(1));
    else words.add(item);
  }
  return { words, suffixes };
}

function inSet(set, tok, raw = '') {
  if (isEdge(tok)) return set.words.has(tok) || set.words.has('START') || set.words.has('END');
  if (set.words.has(tok)) return true;
  if (set.words.has('NAME') && /^\p{Lu}/u.test(raw) && tok !== 'i' && !tok.startsWith("i'")) return true;
  if (set.words.has('NUM') && NUMBER.test(tok)) return true;
  if (set.words.has('YEAR') && YEAR.test(tok)) return true;
  return set.suffixes.some((s) => tok.length > s.length + 1 && tok.endsWith(s));
}

const SETS = ['prev', 'notPrev', 'next', 'notNext', 'next2', 'notNext2', 'next3', 'notIn'];
const compiled = new WeakMap();
function compileRule(rule) {
  if (!compiled.has(rule)) {
    const c = { ...rule, toks: rule.en.split(' ') };
    for (const k of SETS) c[k] = compileSet(rule[k]);
    compiled.set(rule, c);
  }
  return compiled.get(rule);
}

// The rules for one word list, by the first English word, longest phrases first, then learning words before known
// ones, then list order. Kept for the last list seen, by its words and statuses, so a list changed in place is seen.
let cache = null;
function indexFor(given, rules) {
  const words = (Array.isArray(given) ? given : []).filter((w) => w && typeof w.es === 'string' && Object.hasOwn(RANK, w.status));
  const sig = words.map((w) => `${w.es}\u0000${w.status}\u0000${w.en}\u0000${w.hint}`).join('\u0001');
  if (cache && cache.rules === rules && cache.sig === sig) return cache.index;
  const list = new Map();
  for (const w of words) if (!list.has(exactEs(w.es))) list.set(exactEs(w.es), { ...w });
  const index = new Map();
  rules.forEach((rule, order) => {
    const word = list.get(exactEs(rule.es));
    if (!word) return;
    const c = { ...compileRule(rule), word, rank: RANK[word.status], order };
    if (!index.has(c.toks[0])) index.set(c.toks[0], []);
    index.get(c.toks[0]).push(c);
  });
  for (const cands of index.values()) cands.sort((a, b) => b.toks.length - a.toks.length || a.rank - b.rank || a.order - b.order);
  cache = { rules, sig, index };
  return index;
}

const capitalized = (w) => /^\p{Lu}/u.test(w.text) && w.low !== 'i' && !w.low.startsWith("i'");

function pluralBefore(words, i, clause) {
  for (let k = i - 1; k >= 0 && words[k].clause === clause; k--) {
    const w = words[k].low;
    if (PLURAL.has(w)) return true;
    const p = k > 0 && words[k - 1].clause === clause ? words[k - 1].low : '';
    if (ARE.has(w) && p.length > 3 && p.endsWith('s') && !p.endsWith('ss') && !NOT_PLURAL_S.has(p)) return true;
  }
  return false;
}

// Whether rule c fits the phrase starting at words[i].
function fits(c, words, i) {
  const n = c.toks.length;
  if (i + n > words.length) return false;
  const head = words[i];
  for (let k = 0; k < n; k++) {
    const w = words[i + k];
    if (w.opaque || w.glued || w.low !== c.toks[k] || allCaps(w.text)) return false;
    if (k > 0 && (w.clause !== head.clause || w.t !== words[i + k - 1].t + 2)) return false;
    // A capital inside a sentence is a name or a title ("Thank You Notes", "Always Sunny"): leave it.
    if ((k > 0 || !w.first) && capitalized(w)) return false;
  }
  const tail = words[i + n - 1];
  if (c.start === true && !head.first) return false;
  if (c.start === false && head.first) return false;
  if (c.q === true && !head.question) return false;
  if (c.q === false && head.question) return false;
  if (c.prev && !inSet(c.prev, head.before)) return false;
  if (c.notPrev && inSet(c.notPrev, head.before)) return false;
  if (c.next && !inSet(c.next, tail.after, tail.afterRaw)) return false;
  if (c.notNext && inSet(c.notNext, tail.after, tail.afterRaw)) return false;
  if (c.next2 || c.notNext2 || c.next3) {
    // The token after the next word, and after the one after that (a word, a mark or END).
    const beyond = (w) => (w && !isEdge(w.after) ? words[w.k + 1] : null);
    const w1 = beyond(tail);
    const w2 = beyond(w1);
    const after2 = w1 ? w1.after : 'END';
    const after3 = w2 ? w2.after : 'END';
    if (c.next2 && !inSet(c.next2, after2)) return false;
    if (c.notNext2 && inSet(c.notNext2, after2)) return false;
    if (c.next3 && !inSet(c.next3, after3)) return false;
  }
  if (c.notIn) {
    for (let k = i - 1; k >= 0 && words[k].clause === head.clause; k--) if (inSet(c.notIn, words[k].low)) return false;
  }
  if (c.sing && pluralBefore(words, i, head.clause)) return false;
  if (c.neg) {
    const negated = c.neg === 'near' ? head.strictNegBefore >= 0 && i - head.strictNegBefore <= 2 : head.negBefore >= 0;
    if (c.neg === 'no' ? negated : !negated) return false;
  }
  return true;
}

// The gloss and sound hint for a noun shown without its article ("problema" for "el problema").
function bare(word, as) {
  if (!as || exactEs(as) === exactEs(word.es)) return { g: word.en, h: word.hint };
  return { g: String(word.en).split(/\s*\/\s*/).map((m) => m.replace(/^the /, '')).join(' / '),
    h: String(word.hint || '').replace(/^(el|lah|lohs|lahs|oon|oo-nah|oo-nohs|oo-nahs) /i, '') };
}

// weave(text, words) -> { parts, swaps, skipped }. words: the word list ({es, en, hint, status}, as the Mac shares it);
// opts.rules replaces CHAT_RULES, and opts.cap false drops the density limits (for checking every rule).
// parts: the message in order, plain strings and swaps { o, es, g, h, word, status }: o the English it replaces, es
// the Spanish shown, g and h the meaning and sound hint, word the list entry. skipped: 'code', 'topic', 'long' or ''.
export function weave(text, words, { rules = CHAT_RULES, cap = true } = {}) {
  const message = String(text ?? '');
  const skipped = skipReason(message);
  if (skipped) return { parts: message ? [message] : [], swaps: 0, skipped };
  const index = indexFor(words, rules);
  const { toks, words: ws } = analyze(message);
  const found = [];
  for (let i = 0; i < ws.length;) {
    const c = (index.get(ws[i].low) || []).find((cand) => fits(cand, ws, i));
    if (c) {
      found.push({ c, from: i, to: i + c.toks.length - 1, sent: ws[i].sent, k: found.length });
      i += c.toks.length;
    } else i++;
  }
  const counted = ws.filter((w) => !w.opaque && /\p{L}/u.test(w.text)).length;
  const max = cap ? Math.max(1, Math.floor(counted / 10)) : Infinity;
  const used = new Set();
  const perSentence = new Map();
  let keep = [];
  for (const f of [...found].sort((a, b) => a.c.rank - b.c.rank || a.k - b.k)) {
    if (keep.length >= max) break;
    const key = exactEs(f.c.word.es);
    if (cap && (used.has(key) || (perSentence.get(f.sent) || 0) >= 2)) continue;
    used.add(key);
    perSentence.set(f.sent, (perSentence.get(f.sent) || 0) + 1);
    keep.push(f);
  }
  keep.sort((a, b) => a.from - b.from);
  for (const f of keep) f.shown = f.c.as || f.c.word.es;
  const touching = (f, g) => g && ws[g.from].t === ws[f.to].t + 2;
  // "a causa de" then "el tiempo" would read "de el": Spanish writes del, so the second swap stays English.
  keep = keep.filter((g, k) => !(k > 0 && touching(keep[k - 1], g) && /(?:^|\s)(?:de|a)$/i.test(keep[k - 1].shown)
    && /^el\s/i.test(g.shown)));
  const parts = [];
  let at = 0;
  keep.forEach((f, k) => {
    const start = toks[ws[f.from].t].at;
    const last = toks[ws[f.to].t];
    const end = last.at + last.text.length;
    if (start > at) parts.push(message.slice(at, start));
    const o = message.slice(start, end);
    let shown = f.shown;
    let extra = bare(f.c.word, f.c.as);
    // y is e before an i sound, and o is u before an o sound, when the next word is Spanish too.
    const next = touching(f, keep[k + 1]) ? keep[k + 1].shown.toLowerCase() : '';
    if (shown === 'y' && /^h?[ií](?![aeáé])/.test(next)) [shown, extra] = ['e', { ...extra, h: 'eh' }];
    if (shown === 'o' && /^h?[oó]/.test(next)) [shown, extra] = ['u', { ...extra, h: 'oo' }];
    const es = ws[f.from].first && /^\p{Lu}/u.test(o) ? shown.charAt(0).toUpperCase() + shown.slice(1) : shown;
    parts.push({ o, es, ...extra, word: f.c.word.es, status: f.c.word.status });
    at = end;
  });
  if (at < message.length) parts.push(message.slice(at));
  return { parts, swaps: keep.length, skipped: '' };
}

// The woven message as one string, for a banner.
export const wovenText = (parts) => parts.map((p) => (typeof p === 'string' ? p : p.es)).join('');
