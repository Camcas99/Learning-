// Level schedule, word lists, and guards. Pure: no DOM, no chrome APIs.

// L3/L4 prompts are not built yet; anything above this uses L2 rules.
export const MAX_BUILT_LEVEL = 2;

// stage: from the Claude Code plugin's word state (0 when there is none); chosen: after the popup override;
// effective: what the prompt uses.
export function resolveLevel(settings = {}, stage = 0) {
  const override = Number(settings.levelOverride) || 0;
  const synced = Number(stage) >= 1 && Number(stage) <= 4 ? Number(stage) : 0;
  const chosen = override >= 1 && override <= 4 ? override : synced || 1;
  return { stage: synced, chosen, effective: Math.min(chosen, MAX_BUILT_LEVEL) };
}

// note: a usage note shown after the gloss, mostly false friends.
const W = (es, en, hint, note = '') => ({ es, en, hint, note });

// Level 1: the bundled starter list, used when the Claude Code plugin's word state isn't available.
export const L1_WORDS = [
  W('y', 'and', 'ee'),
  W('pero', 'but', 'PEH-roh'),
  W('o', 'or', 'oh'),
  W('entonces', 'so', 'en-TOHN-ses'),
  W('porque', 'because', 'POR-keh'),
  W('con', 'with', 'kohn'),
  W('sin', 'without', 'seen'),
  W('para', 'for', 'PAH-rah'),
  W('muy', 'very', 'mwee'),
  W('también', 'also', 'tahm-BYEN'),
  W('bien', 'well / good', 'byen'),
  W('mucho', 'a lot', 'MOO-choh'),
  W('un poco', 'a little', 'oon POH-koh'),
  W('ahora', 'now', 'ah-OH-rah'),
  W('siempre', 'always', 'SYEM-preh'),
  W('tal vez', 'maybe', 'tahl bes'),
  W('aquí', 'here', 'ah-KEE'),
  W('listo', 'ready / done', 'LEES-toh'),
  W('sí', 'yes', 'see'),
  W('claro', 'of course', 'KLAH-roh'),
  W('gracias', 'thank you', 'GRAH-syahs'),
  W('el problema', 'the problem', 'el proh-BLEH-mah'),
  W('la pregunta', 'the question', 'lah preh-GOON-tah'),
  W('la idea', 'the idea', 'lah ee-DEH-ah'),
  W('la respuesta', 'the answer', 'lah rres-PWES-tah'),
  W('importante', 'important', 'eem-por-TAHN-teh'),
  W('posible', 'possible', 'poh-SEE-bleh'),
  W('difícil', 'difficult', 'dee-FEE-seel'),
];

// Level 2: L1 plus frequent words, cognates, and fixed phrases (~150 total).
export const L2_EXTRA = [
  // question words and connectors
  W('si', 'if', 'see'),
  W('como', 'like / as', 'KOH-moh'),
  W('cuando', 'when', 'KWAHN-doh'),
  W('dónde', 'where', 'DOHN-deh'),
  W('por qué', 'why', 'por KEH'),
  W('cómo', 'how', 'KOH-moh'),
  W('quién', 'who', 'kyen'),
  W('qué', 'what', 'keh'),
  W('así que', 'so (therefore)', 'ah-SEE keh'),
  W('en realidad', 'actually', 'en rreh-ah-lee-DAHD'),
  W('por ejemplo', 'for example', 'por eh-HEM-ploh'),
  // adverbs
  W('nunca', 'never', 'NOON-kah'),
  W('otra vez', 'again', 'OH-trah bes'),
  W('ya', 'already', 'yah'),
  W('a menudo', 'often', 'ah meh-NOO-doh'),
  W('a veces', 'sometimes', 'ah BEH-ses'),
  W('de verdad', 'really', 'deh behr-DAHD'),
  W('solo', 'only', 'SOH-loh'),
  W('demasiado', 'too much', 'deh-mah-SYAH-doh'),
  W('bastante', 'enough', 'bahs-TAHN-teh'),
  W('casi', 'almost', 'KAH-see'),
  W('sobre todo', 'especially', 'SOH-breh TOH-doh'),
  W('juntos', 'together', 'HOON-tohs'),
  W('pronto', 'soon', 'PROHN-toh'),
  W('hoy', 'today', 'oy'),
  W('mañana', 'tomorrow', 'mah-NYAH-nah'),
  W('ayer', 'yesterday', 'ah-YEHR'),
  W('esta noche', 'tonight', 'ES-tah NOH-cheh'),
  W('allí', 'there', 'ah-YEE'),
  W('más', 'more', 'mahs'),
  W('menos', 'less', 'MEH-nohs'),
  W('mejor', 'better', 'meh-HOR'),
  W('peor', 'worse', 'peh-OR'),
  W('por supuesto', 'of course', 'por soo-PWES-toh'),
  W('de acuerdo', 'okay / agreed', 'deh ah-KWEHR-doh'),
  W('para nada', 'not at all', 'PAH-rah NAH-dah'),
  // pronouns and quantifiers
  W('todo', 'everything / all', 'TOH-doh'),
  W('nada', 'nothing', 'NAH-dah'),
  W('algo', 'something', 'AHL-goh'),
  W('alguien', 'someone', 'AHL-gyen'),
  W('todo el mundo', 'everyone', 'TOH-doh el MOON-doh'),
  W('mismo', 'same', 'MEES-moh'),
  W('otro', 'other', 'OH-troh'),
  W('eso', 'that', 'EH-soh'),
  // prepositions
  W('en', 'in', 'en'),
  W('sobre', 'about (a topic) / on top of', 'SOH-breh'),
  W('entre', 'between', 'EN-treh'),
  W('después de', 'after', 'des-PWES deh'),
  W('antes de', 'before', 'AHN-tes deh'),
  W('durante', 'during', 'doo-RAHN-teh'),
  W('desde', 'since (a time) / from', 'DES-deh'),
  // nouns
  W('el tiempo', 'time / the weather', 'el TYEM-poh'),
  W('la vida', 'life', 'lah BEE-dah'),
  W('el mundo', 'the world', 'el MOON-doh'),
  W('la casa', 'the house / home', 'lah KAH-sah'),
  W('el trabajo', 'work', 'el trah-BAH-hoh'),
  W('la cosa', 'the thing', 'lah KOH-sah'),
  W('el día', 'the day', 'el DEE-ah'),
  W('la semana', 'the week', 'lah seh-MAH-nah'),
  W('el año', 'the year', 'el AH-nyoh'),
  W('el amigo', 'the friend', 'el ah-MEE-goh'),
  W('la familia', 'the family', 'lah fah-MEE-lyah'),
  W('la ciudad', 'the city', 'lah syoo-DAHD'),
  W('el final', 'the end', 'el fee-NAHL'),
  W('la razón', 'the reason', 'lah rrah-SOHN'),
  W('el momento', 'the moment', 'el moh-MEN-toh'),
  W('la suerte', 'luck', 'lah SWEHR-teh'),
  W('la historia', 'the story / history', 'lah ees-TOH-ryah'),
  W('la música', 'music', 'lah MOO-see-kah'),
  W('el gato', 'the cat', 'el GAH-toh'),
  W('el perro', 'the dog', 'el PEH-rroh'),
  W('la escuela', 'school', 'lah es-KWEH-lah'),
  // adjectives
  W('bueno', 'good', 'BWEH-noh'),
  W('malo', 'bad', 'MAH-loh'),
  W('grande', 'big', 'GRAHN-deh'),
  W('pequeño', 'small', 'peh-KEH-nyoh'),
  W('nuevo', 'new', 'NWEH-boh'),
  W('viejo', 'old', 'BYEH-hoh'),
  W('joven', 'young', 'HOH-ben'),
  W('bonito', 'pretty / nice', 'boh-NEE-toh'),
  W('verdadero', 'true', 'behr-dah-DEH-roh'),
  W('falso', 'false / fake', 'FAHL-soh'),
  W('fácil', 'easy', 'FAH-seel'),
  W('fuerte', 'strong', 'FWEHR-teh'),
  W('largo', 'long', 'LAHR-goh', "not 'large' (that's grande)"),
  W('caliente', 'hot (to the touch)', 'kah-LYEN-teh', "not hot weather or feeling hot (that's calor)"),
  W('frío', 'cold', 'FREE-oh'),
  W('feliz', 'happy', 'feh-LEES'),
  W('triste', 'sad', 'TREES-teh'),
  W('libre', 'free', 'LEE-breh'),
  W('seguro', 'sure', 'seh-GOO-roh'),
  W('sencillo', 'simple', 'sen-SEE-yoh'),
  W('interesante', 'interesting', 'een-teh-reh-SAHN-teh'),
  W('increíble', 'incredible', 'een-kreh-EE-bleh'),
  W('perfecto', 'perfect', 'pehr-FEK-toh'),
  W('pésimo', 'awful', 'PEH-see-moh'),
  W('excelente', 'excellent', 'ek-seh-LEN-teh'),
  W('diferente', 'different', 'dee-feh-REN-teh'),
  W('común', 'common', 'koh-MOON'),
  W('rápido', 'fast', 'RRAH-pee-doh'),
  W('último', 'last', 'OOL-tee-moh'),
  W('primero', 'first', 'pree-MEH-roh'),
  W('próximo', 'next', 'PROHK-see-moh'),
  W('gratis', 'free (no cost)', 'GRAH-tees'),
  W('serio', 'serious', 'SEH-ryoh'),
  W('gracioso', 'funny', 'grah-SYOH-soh'),
  W('loco', 'crazy', 'LOH-koh'),
  W('genial', 'great / cool', 'heh-NYAHL'),
  W('imposible', 'impossible', 'eem-poh-SEE-bleh'),
  // fixed phrases and greetings
  W('es', "it's / is (what something is)", 'es', "a state or place takes está (está listo = it's ready)"),
  W('hay', 'there is / there are', 'eye'),
  W('creo que', 'I think that', 'KREH-oh keh'),
  W('hay que', 'you have to / we need to', 'eye keh'),
  W('me gusta', 'I like', 'meh GOOS-tah'),
  W('sé', 'I know', 'seh'),
  W('no sé', "I don't know", 'noh SEH'),
  W('por favor', 'please', 'por fah-BOR'),
  W('hola', 'hello', 'OH-lah'),
  W('lo siento', 'sorry', 'loh SYEN-toh'),
  W('qué tal', "how's it going", 'KEH tahl'),
];

export const L2_WORDS = [...L1_WORDS, ...L2_EXTRA];

export function wordsForLevel(level) {
  return level <= 1 ? L1_WORDS : L2_WORDS;
}

// "también", "tambien" and "También " all map to the same entry.
export function normalizeEs(s) {
  return String(s)
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[’‘`]/g, "'")
    .replace(/\s+/g, ' ')
    .trim();
}

const ARTICLE_RE = /^(?:los|las|el|la|unos|unas|una|un)\s+/i;
export const exactEs = (s) => String(s).normalize('NFC').toLowerCase().replace(/[’‘`]/g, "'").replace(/\s+/g, ' ').trim();

// Feminine nouns that take "el"/"un" for sound (stressed a- or ha-): el agua, un alma.
const EL_FEMININE = new Set(['agua', 'alma', 'hambre', 'águila', 'aula', 'área', 'arma', 'hacha', 'ave', 'ala', 'hada',
  'habla', 'ancla'].map(normalizeEs));
// Fixed phrases that start with un/una but are not nouns, so they get no gender cue.
const NOT_NOUNS = new Set(['un poco', 'una vez más'].map(normalizeEs));

// 'm' or 'f' from a list entry's article ("el problema", "las ganas"); '' without one.
export function genderOf(es) {
  const s = normalizeEs(es);
  const m = /^(el|los|un|unos|la|las|una|unas) (\S+)/.exec(s);
  if (!m || NOT_NOUNS.has(s)) return '';
  return /^(la|las|una|unas)$/.test(m[1]) || EL_FEMININE.has(m[2]) ? 'f' : 'm';
}

const indexCache = new Map();
function indexFor(level, sharedWords) {
  const lvl = level <= 1 ? 1 : 2;
  if (!sharedWords && indexCache.has(lvl)) return indexCache.get(lvl);
  const idx = new Map();
  for (const w of sharedWords || wordsForLevel(lvl)) {
    const full = exactEs(w.es);
    // Gender and note belong to the noun, so the bare form keeps them.
    const about = { word: w.es, status: w.status, gn: genderOf(w.es), note: w.note || '' };
    idx.set(full, { ...about, canon: w.es, en: w.en, hint: w.hint });
    const stripped = full.replace(ARTICLE_RE, '');
    if (stripped !== full && !idx.has(stripped)) {
      // Accept the bare noun ("canción" for "song") and keep the accents from the list.
      const canon = w.es.replace(ARTICLE_RE, '');
      idx.set(stripped, { ...about, canon, en: w.en.replace(/^the /, ''), hint: w.hint.replace(/^(el|lah|lohs|lahs|oon|oo-nah|oo-nohs|oo-nahs) /i, '') });
    }
  }
  const folded = new Map();
  for (const [key, value] of idx) {
    const fold = normalizeEs(key);
    folded.set(fold, folded.has(fold) ? null : value);
  }
  const result = { exact: idx, folded };
  if (!sharedWords) indexCache.set(lvl, result);
  return result;
}

export function matchCase(es, original) {
  if (/^\p{Lu}/u.test(original) && !/^\p{Lu}{2}/u.test(original)) {
    return es.charAt(0).toUpperCase() + es.slice(1);
  }
  return es;
}

// Fail closed: keep only swaps whose Spanish is on the list (the plugin's word state, else the level's bundled list).
// Canonicalizes accents, fills gloss and hint from the list, matches capitalization of the original.
// Adds gn (noun gender) and n (usage note) when the word has them.
export function validateSwaps(level, swaps, sharedWords) {
  if (!Array.isArray(swaps)) return [];
  const idx = indexFor(level, sharedWords);
  const out = [];
  for (const s of swaps) {
    if (!s || typeof s.o !== 'string' || typeof s.es !== 'string') continue;
    const o = s.o.trim();
    if (!o || !s.es.trim()) continue;
    const hit = idx.exact.get(exactEs(s.es)) || idx.folded.get(normalizeEs(s.es));
    if (!hit) continue;
    out.push({
      o,
      es: matchCase(hit.canon, o),
      g: hit.en,
      h: hit.hint,
      ctx: typeof s.ctx === 'string' ? s.ctx.trim() : '',
      ...(sharedWords ? { word: hit.word, ...(hit.status ? { status: hit.status } : {}) } : {}),
      ...(hit.gn ? { gn: hit.gn } : {}),
      ...(hit.note ? { n: hit.note } : {}),
    });
  }
  return out;
}

export function sentenceCount(text) {
  return Math.max(1, String(text).split(/[.!?…]+(?:\s|$)|\n+/).filter((s) => wordCount(s) >= 3).length);
}

// Density ceiling per passage, one use per Spanish word, learning words (active/shaky) kept before known ones.
export function capSwaps(level, swaps, text, sharedWords) {
  const max = (level <= 1 ? 1 : 2) * sentenceCount(text);
  const status = new Map((sharedWords || []).map((w) => [w.es, w.status]));
  const rank = (s) => (status.get(s.word) && status.get(s.word) !== 'known' ? 0 : 1);
  const used = new Set();
  const unique = swaps.filter((s) => { const k = exactEs(s.word || s.es); if (used.has(k)) return false; used.add(k); return true; });
  const keep = new Set([...unique].sort((a, b) => rank(a) - rank(b)).slice(0, max));
  return unique.filter((s) => keep.has(s));
}

export function wordCount(text) {
  const t = String(text).trim();
  return t ? t.split(/\s+/).length : 0;
}

// Small, conservative client-side guard for the zero-Spanish topics. The model rule does the real work;
// this just guarantees the obvious cases never leave the page.
const ZERO_SPANISH = [
  /\b(doctor|hospital|diagnos\w*|symptoms?|medication|meds|ibuprofen|tylenol|prescription|overdose|vaccine|cancer|surgery|pregnan\w*|therapist|antidepressants?|ssri|adderall|stimulants?|chemo)\b/i,
  /\b(lawsuit|attorney|lawyer|sued|indict\w*|court order|legal advice|subpoena)\b/i,
  /\b(invest\w*|stock market|crypto|bitcoin|mortgage|loan|taxes|salary|bank account|financial advice)\b/i,
  /\b(911|emergency|evacuat\w*|shooting|wildfire|earthquake|hurricane|tornado|active shooter)\b/i,
  /\b(driving|drunk driv\w*|car crash|dui|speed limit|seat ?belt)\b/i,
];

export function isZeroSpanish(text) {
  return ZERO_SPANISH.some((re) => re.test(text));
}
