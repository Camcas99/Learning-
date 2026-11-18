// Where each list word may stand in for English in a text message, for the local chat matcher (chatweave.js). No
// model reads friends' messages, so these rules are the whole judgment: a word swaps only where its English keeps the
// one meaning the list gives it, and anything unsure stays English. A word with no rule never appears in chat.
// Words that change with the speaker's gender (listo, seguro, bueno, juntos) are left out: a text doesn't say who
// wrote it.
//
// R(es, en, opts): es is the list word, en the English it replaces (lowercase, words split by spaces, as written in a
// text: "i'm going to"). opts, all optional:
//   as      the Spanish to show instead of es: a noun without its article ("my problem" -> "my problema")
//   prev    the word just before must be one of these; notPrev: must not be
//   next    the word just after must be one of these; notNext: must not be
//   next2   the word after that must be one of these; notNext2: must not be. next3: the one after that
//           In these sets START and END stand for the edge of a clause (text start, a line break or punctuation), a
//           punctuation mark stands for itself (',' : followed by a comma), NUM for a number, YEAR for 1900 to 2099,
//           NAME for a capitalized word other than I, and '*ing' for any word ending in -ing.
//   notIn   none of these words earlier in the clause
//   sing    true: not after a plural subject in the clause ("we're free" would need libres)
//   start   true: only first in its sentence; false: never first
//   q       true: only in a question; false: never in one (a "?", or a sentence that opens like one: "when do you")
//   neg     'no': not after a negative earlier in its clause; 'yes': only after one; 'near': only within two words
//           after "not", "never" or an n't word ("not red but blue"; a reply's "no, but" doesn't count)
// Every rule's English must match the word's gloss in data/lexicon.csv (chatweave.test.js checks), through SYNONYMS in
// levels.js or CHAT_SYNONYMS below.

export const CHAT_SYNONYMS = {
  'for example': ['for instance'],
  despite: ['in spite of'],
  'the same thing': ['the same'],
  'like this': ['like that'],
  anyway: ['anyways'],
  'by the way': ['btw'],
  'what a pity': ['what a shame'],
  'it seems that': ['it seems like'],
  // Keys are spelled out the way levels.js compares glosses ("i'm" is "i am").
  'i am going to': ["i'm gonna"],
  'we are going to': ["we're gonna"],
  'right now': ['at the moment'],
  'once again': ['one more time'],
  'but rather': ['but'], // only in "not X but Y"
  free: ['for free'],
};

const R = (es, en, opts = {}) => ({ es, en, ...opts });

const POSS = 'my|your|his|her|our|their';
const THIS = `${POSS}|this|that`;
const SUBJ = "i|you|he|she|we|they|it|there|i'm|you're|we're|they're|he's|she's|it's|i'll|you'll|we'll|they'll|i've|i'd|you'd";
const OBJ = 'you|me|us|him|her|them';
const DAYS = 'monday|tuesday|wednesday|thursday|friday|saturday|sunday';
const MONTHS = 'january|february|march|april|may|june|july|august|september|october|november|december';
// Time words a preposition can take with no clause after them: "after lunch", "until tomorrow". No bare numbers:
// "after 3" is después de las 3.
const TIME = `${DAYS}|tomorrow|tonight|today|yesterday|noon|midnight|lunch|dinner|breakfast|brunch|work|school|class|bed|`
  + 'christmas|thanksgiving|then|now|next|last';
// The word after "before the party" (next3): a noun phrase ends there. "before the movie starts" is a clause (antes de
// que).
const NP_END = "END|of|at|in|on|with|for|and|or|so|lol|haha|tonight|today|tomorrow|then|too|though|i|we|you|they|he|she|"
  + "i'll|we'll|i'm|we're|let's";
// What can follow a noun the matcher swaps: the noun ends its phrase. "the dog park" and "the world cup" use the noun
// as a modifier, and "el perro park" would teach the wrong thing.
const NOUN_END = "END|is|was|are|were|has|had|have|will|would|can|could|should|did|does|do|isn't|wasn't|doesn't|didn't|"
  + "won't|can't|of|in|on|at|for|with|to|from|by|about|and|or|but|so|that|who|which|where|when|why|because|if|lol|haha|"
  + 'lmao|too|again|now|today|tonight|tomorrow|yesterday|right|though|tho|back|here|there|yet|already|still|just|really|'
  + 'always|never|got|gets|went|goes|looks|seems|sounds|feels|made|makes|said|says|after|before|rn|tmrw|i|you|he|she|we|'
  + 'they|it|me|him|us|them|*ed';
// Adjectives that follow "so", "too" and "how": "so tired" is tan, "so far" and "so long" are not.
const ADJ = 'good|bad|cute|funny|happy|sad|tired|nice|cool|beautiful|pretty|weird|hot|cold|busy|excited|proud|fast|slow|big|small|'
  + 'sweet|hard|easy|late|early|expensive|cheap|boring|bored|crazy|true|smart|kind|fun|great|lucky|close|young|old|loud|quiet|'
  + 'dark|scary|scared|sorry|glad|important|difficult|different|interesting|amazing|awesome|annoying|annoyed|stressed|stressful|'
  + 'hungry|thirsty|full|ready|worried|nervous|upset|mad|angry|jealous|lonely|rude|ugly|gross|delicious|perfect|simple|'
  + 'complicated|strange|random|serious|thankful|grateful|lovely|adorable|hilarious|exhausted|confused|real|stupid|dumb|lazy';
// Ways into a question someone else asked: "I don't know where" takes dónde, with the accent.
const ASKED = 'know|knew|sure|idea|wonder|wondering|tell|told|ask|asked|asking|remember|forgot|forget|see|guess|figure|out|'
  + 'explain|decide|understand|idk|dunno|check|checking|show';
const VERB = "are|is|was|were|do|does|did|can|could|should|would|will|have|has|had|am|u|r|ur";
const AUX = `${VERB}|i|you|we|they|he|she|it`;
const PLACES = 'place|places|house|home|city|town|spot|restaurant|bar|room|store|shop|area|part|point|park|street|beach|school|'
  + 'office|apartment|building|country|neighborhood|cafe|café|hotel|kitchen|one|somewhere|anywhere|everywhere|party|club|'
  + 'island|state|campus|gym|mall|airport|station';
// After these, "is" and "was" are a state: "I'm fine" is bien, "a fine" is not.
const BE = "i'm|im|it's|its|that's|thats|is|am|are|was|be|been|all|feel|feeling|feels|felt|looks|look|looked|sounds|sound|"
  + "seems|seem|we're|you're|they're|he's|she's|everything's|totally|just|perfectly|doing|so|very|really|pretty|too";
// Predicate position for an adjective: the next word isn't a noun it would have to agree with.
const PRED = 'END|to|that|for|because|than|enough|and|but|or|now|today|tonight|though|too|right|lol|haha';
// Going somewhere takes a, not en: "let's go somewhere" is vamos a algún lado.
const MOTION = 'go|goes|going|gone|went|get|gets|got|getting|move|moving|moved|drive|driving|come|comes|coming|came|travel|'
  + 'traveling|head|heading|headed|run|walk|walking|fly|flying|take|took|taking|send|sent|bring|brought|ride|riding';
// "a lot", "so much" and "how much" before a noun would have to agree with it (mucha comida), so only where none follows.
const AMOUNT_END = 'END|lol|haha|for|that|to|already|today|tonight|lately|recently|right|since|because|and|but|i|you|we|tbh';
// Who someone is, before a relative "who" (quien, no accent): "everyone I know who has a dog".
const PEOPLE = 'everyone|someone|anyone|people|everybody|somebody|anybody|guy|guys|girl|girls|person|those|one|friend|friends';
const PERSON = "he|she|we|they|i|you|i'm|you're|we're|they're|he's|she's|am|room|seat|spot|table|line|lane|space";
// "my calendar is free" means open, not costing nothing.
const NOT_FREE = `calendar|schedule|day|afternoon|morning|evening|night|weekend|week|tomorrow|tonight|${DAYS}|bathroom|restroom|toilet|`
  + 'time|spot|seat';
// "there's gonna be" is a future, "there's been" a perfect, and "there's Sarah!" points: none is hay.
const THERE_NOT = 'gonna|going|supposed|been|got|gotta|him|them|us|me|mom|dad|NAME';
// "let's go somewhere", "pick somewhere", "out of nowhere": not en ... lado.
const PLACE_NOT = `${MOTION}|out|back|over|off|pick|find|know|choose|from|of|have|has|had`;
// "have a good night" and "it was a good night" are an evening, not the greeting.
const GREETING_NOT = `a|an|the|one|${POSS}|this|that`;

export const CHAT_RULES = [
  // The first list words.
  R('y', 'and'),
  R('pero', 'but', { notPrev: 'nothing|anything|all|everything|everyone|everybody|anyone|anybody|nobody|none|last|one',
    notNext: 'not|still', neg: 'no' }),
  R('sino', 'but', { neg: 'near', notNext: `${SUBJ}|${POSS}|the|a|an|this|that|these|those|END|NAME|*'ll|*'d|*'ve|*'s|not|way|so|`
    + 'maybe|probably|still|also|kinda|pretty|really|worth|definitely|just|too|very|like|wait|fr|seriously' }),
  R('entonces', 'so', { start: true, next: ",|i|you|we|they|he|she|it|i'm|i'll|we're|we'll|you're|how|when|where|why|the" }),
  R('entonces', 'then', { prev: 'and|START', next: `${SUBJ}|what|,`, notIn: 'now|every' }),
  // "with me" and "with you" are conmigo and contigo.
  R('con', 'with', { notPrev: 'wrong|done|deal|deals|dealt|dealing|up|along|fine|okay|ok|over|go|goes|went|stick|break|broke|mess|love',
    notNext: 'me|you' }),
  R('sin', 'without', { notNext: `*ing|${SUBJ}|END` }),
  R('muy', 'very', { notPrev: 'the|this|that|my|your|his|her|our|their',
    notNext: 'much|many|END|first|last|own|best|end|beginning|next|top|bottom|same|least|most|thing|moment|idea|well' }),
  R('también', 'also', { notNext: 'END' }),
  R('también', 'as well', { next: 'END', notPrev: 'might|may|just|could' }),
  R('también', 'too', { next: 'END', notPrev: 'me|much|many|way|this|that|it|one' }),
  R('ahora', 'now', { notPrev: 'by|until|till|from|for|right|just|even|every', notNext: 'that|on|and' }),
  R('para', 'for', { next: OBJ, notPrev: 'wait|waiting|waited|ask|asking|asked|look|looking|looked|pay|paying|paid|thanks|thank|'
    + 'sorry|search|searching|care|cares|apply|applied|stand|stood|standing|account|go|went|vote|voted|fall|fell|fallen|feel|felt|'
    + 'happy|proud|responsible|famous|known|ready|call|called|calling|send|sent|hope|hoped|hoping|pray|praying|blame|forgive|'
    + 'excited|glad|bad|good|fight|fought|fighting|cover|covering|rooting|cheering|worried|scared|speak|speaks|spoke|sad|'
    + 'thankful|grateful|mad|angry|jealous|fault|mistake|reason|turn|anything|everything|back|die|died|dying|out|in|live|kill|fill' }),
  R('porque', 'because', { notNext: 'of' }),
  R('siempre', 'always'),
  R('tal vez', 'maybe'),
  R('tal vez', 'perhaps'),
  R('mucho', 'a lot', { next: AMOUNT_END, notPrev: 'thanks|thank|thx|you' }),
  R('sí', 'yes'),
  R('gracias', 'thank you'),
  R('gracias', 'thanks'),
  R('claro', 'of course', { q: false, next: 'END' }),
  R('claro', 'sure', { start: true, next: 'END', q: false }),
  R('importante', 'important', { next: PRED, sing: true }),
  R('posible', 'possible', { next: PRED, sing: true }),
  R('difícil', 'difficult', { next: PRED, sing: true }),
  R('el problema', 'the problem', { next: NOUN_END }),
  R('el problema', 'problem', { as: 'problema', prev: THIS, next: NOUN_END }),
  R('la pregunta', 'the question', { next: NOUN_END }),
  R('la pregunta', 'question', { as: 'pregunta', prev: THIS, next: NOUN_END }),
  R('la idea', 'the idea', { next: NOUN_END }),
  R('la respuesta', 'the answer', { next: NOUN_END }),
  R('la respuesta', 'answer', { as: 'respuesta', prev: THIS, next: NOUN_END }),
  R('o', 'or'),
  R('donde', 'where', { prev: PLACES, notNext: VERB }),
  R('bien', 'fine', { prev: BE, next: PRED }),
  R('bien', 'well', { prev: 'doing|did|does|do|done|went|go|goes|going|slept|sleep|sleeping|work|works|worked|working|play|played|'
    + 'playing|very|pretty|really|so|eat|eating|ate|cook|cooks|cooked|sing|sings|turned|turn|turns|ended|end|ends|sounds',
  next: PRED }),
  // "in a bit" is en un rato, a time; un poco is an amount.
  R('un poco', 'a little bit', { notPrev: 'in|for|quite|after|every' }),
  R('un poco', 'a bit', { notNext: 'of', notPrev: 'in|for|quite|after|every' }),
  R('un poco', 'a little', { notPrev: 'in|for|quite|after|every', next: 'END|more|less|late|early|longer|too|tired|sad|nervous|busy|worried|scared|'
    + 'weird|better|worse|slow|slower|faster|cold|hot|behind|confused|annoyed|stressed|excited|bored|different' }),
  R('aquí', 'here', { notPrev: 'over|hi|hey|same', notNext: 'is|are|you|we|it|comes|goes|go|u|ya' }),
  R('acá', 'here', { notPrev: 'over|hi|hey|same', notNext: 'is|are|you|we|it|comes|goes|go|u|ya' }),
  R('tan', 'so', { next: ADJ, notPrev: 'or|and|think|hope|guess|said|say|says|believe|not|i|far' }),
  R('hay', 'there is', { notNext: `no|not|nothing|nobody|none|never|END|the|${THIS}|these|those|${THERE_NOT}` }),
  R('hay', 'there are', { notNext: `no|not|nothing|nobody|none|never|END|the|${THIS}|these|those|${THERE_NOT}` }),
  R('hay', "there's", { notNext: `no|not|nothing|nobody|none|never|END|the|${THIS}|these|those|${THERE_NOT}`, notPrev: 'so|and' }),
  R('más', 'more', { notPrev: 'no|any|once|the|one|some|much|many|a|lot|bit|little|NUM|two|three|four|five|six|seven|eight|nine|ten|'
    + 'few|couple|several' }),
  R('menos', 'less', { notPrev: 'no|more|much|any' }),
  R('menos', 'fewer', { notPrev: 'no|much|any' }),
  R('ya', 'already'),
  R('todavía', 'still', { notPrev: 'stand|standing|stood|sit|sitting|sat|stay|staying|stayed|hold|holding|keep|be|lie|lying|but',
    notNext: ',|water|life' }),
  // "Have you eaten yet?" is ya; todavía is "not yet".
  R('todavía', 'yet', { next: 'END', start: false, notPrev: 'not', neg: 'yes', q: false }),
  // "what's his name again?" asks to be reminded; "then again" means on the other hand.
  R('otra vez', 'again', { notPrev: 'never|then', notIn: "what|what's|whats|where|where's|wheres|who|who's|when|how|how's" }),
  R('nunca', 'never', { notNext: 'mind|ever|again' }),

  // The next list words, in list order.
  R('a menudo', 'often', { notPrev: 'how|so|too|as|very' }),
  R('de verdad', 'for real'),
  R('de verdad', 'really', { next: 'END', notPrev: 'not|nothing|no|nah|never', neg: 'no' }),
  R('solo', 'only', { notPrev: 'the|an|my|your|his|her|our|their|if', notNext: 'END|child|one|ones|thing|things|person|way|reason|time|'
    + 'problem|downside|issue|catch|bad|good|difference|option|choice' }),
  R('casi', 'almost'),
  R('casi', 'nearly'),
  R('aunque', 'although'),
  R('aunque', 'even though'),
  R('demasiado', 'too much', { next: AMOUNT_END }),
  // "too bad" is qué lástima.
  R('demasiado', 'too', { next: `${ADJ.replace(/^bad\||\|bad\|/, '|')}|far|long|soon`, notPrev: 'me' }),
  R('bastante', 'quite', { notPrev: 'not', next: ADJ }),
  R('si', 'if', { notNext: 'END|only|so' }),
  // "when do you get off work" is a question (cuándo) even without its "?".
  R('cuando', 'when', { q: false, notPrev: `${ASKED}|until|since|till`, notNext: `${VERB}|END` }),
  R('durante', 'during'),
  R('antes de', 'before', { next: TIME, notPrev: 'day|week|month|year|night|morning' }),
  R('antes de', 'before', { next: `the|${POSS}`, next3: NP_END, notPrev: 'day|week|month|year|night|morning' }),
  R('después de', 'after', { next: TIME, notPrev: 'look|looking|looked|take|takes|took|ask|asked|asking|go|going|went|come|came|'
    + 'run|ran|day|week|month|year|night|morning' }),
  R('después de', 'after', { next: `the|${POSS}`, next3: NP_END, notPrev: 'look|looking|looked|take|takes|took|ask|asked|asking|go|'
    + 'going|went|come|came|run|ran|day|week|month|year|night|morning' }),
  R('entre', 'between'),
  R('entre', 'among'),
  // After a verb Spanish doubles the negative ("I saw nobody" is no vi a nadie), so only first in the sentence.
  R('nadie', 'nobody', { start: true }),
  R('nadie', 'no one', { start: true }),
  R('contra', 'against'),
  // "since you're here" is because (como, ya que); desde is a starting time.
  R('desde', 'since', { next: `then|yesterday|last|forever|YEAR|${DAYS}|${MONTHS}|morning|noon|lunch|breakfast|high|college|birth|`
    + 'childhood' }),
  R('creo que', 'i think that'),
  R('creo que', 'i think', { notNext: 'so|about|of|END|that|not|it|you|i|lol|haha|tho|though|otherwise|differently',
    notPrev: "don't|do|didn't|also|really|just|honestly|but" }),
  // "you have to come!" is said to one person; hay que is general, so only the "we" forms.
  R('hay que', 'we have to', { notPrev: 'do|did|why|will|would|if|when' }),
  R('hay que', 'we need to', { notPrev: 'do|did|why|will|would|if|when' }),
  R('por ejemplo', 'for example'),
  R('por ejemplo', 'for instance'),
  R('ya no', 'no longer'),
  R('en realidad', 'actually'),
  R('en realidad', 'in fact'),
  R('por supuesto', 'of course', { q: false, next: 'END' }),
  R('de acuerdo', 'okay', { start: true, next: 'END' }),
  R('de acuerdo', 'ok', { start: true, next: 'END' }),
  R('de acuerdo', 'agreed', { start: true, next: 'END' }),
  R('o sea', 'i mean', { start: true, next: ',' }),
  R('o sea', 'in other words'),
  R('todo', 'everything', { neg: 'no' }),
  // "I don't even know" is ni siquiera; incluso is only the positive "even".
  R('incluso', 'even', { neg: 'no', q: false, notPrev: "not|an|break|breaking|broke|get|got|getting|you|what|who|how|why|where|when|we're|"
    + "we|you're|they're|are|be|were|is",
    notNext: 'though|if|number|numbers|END|so|out' }),
  R('nada', 'nothing', { start: true }),
  R('algo', 'something'),
  R('todo el mundo', 'everyone'),
  R('todo el mundo', 'everybody'),
  R('el tiempo', 'the weather', { next: NOUN_END, notPrev: 'under' }),
  R('el día', 'the day', { next: NOUN_END }),
  R('el día', 'day', { as: 'día', prev: `${THIS}|nice|good|great|long|bad|whole|same|big|every|one`, next: NOUN_END }),
  R('la cosa', 'the thing', { next: NOUN_END }),
  R('el mundo', 'the world', { next: NOUN_END }),
  R('la vida', 'life', { as: 'vida', prev: POSS, next: NOUN_END }),
  R('por ahora', 'for now'),
  R('el trabajo', 'the job', { next: NOUN_END }),
  R('el trabajo', 'job', { as: 'trabajo', prev: POSS, next: NOUN_END }),
  R('el trabajo', 'work', { as: 'trabajo', prev: POSS, next: NOUN_END }),
  R('la razón', 'the reason', { next: NOUN_END }),
  R('la razón', 'reason', { as: 'razón', prev: `${THIS}|some|no|any|good|real|main|only`, next: NOUN_END }),
  R('la parte', 'the part', { next: NOUN_END }),
  R('la parte', 'part', { as: 'parte', prev: `${POSS}|best|worst|hardest|easiest|fun|funny|good|bad|first|last`, next: NOUN_END }),
  R('sino', 'but rather'),
  R('tampoco', 'either', { next: 'END', neg: 'yes' }),
  R('tampoco', 'neither', { prev: 'me', next: 'END' }),
  R('el lado', 'the side', { next: NOUN_END }),
  R('el lado', 'side', { as: 'lado', prev: `${POSS}|other|this|that|bright|dark|left|right`, next: NOUN_END }),
  R('el final', 'the end', { notPrev: 'in|at', next: NOUN_END }),
  R('el principio', 'the beginning', { next: NOUN_END }),
  R('grande', 'big', { next: PRED, notPrev: 'think|thinking|go|dream|the', sing: true }),
  R('de hecho', 'in fact'),
  R('lo mismo', 'the same thing'),
  R('lo mismo', 'the same', { next: 'END|for|as|here' }),
  R('fácil', 'easy', { next: PRED, notPrev: "take|taking|took|go|going|went|nice|it|things|i'm|im|you're|he's|she's", sing: true }),
  // "you better be there" is had better.
  R('mejor', 'better', { notPrev: "had|you'd|we'd|i'd|they'd|he'd|she'd|get|gets|getting|got|feel|feels|feeling|felt|the|you|we|i|they|"
    + 'he|she', notNext: '*s', sing: true }),
  R('peor', 'worse', { notPrev: 'the', sing: true }),
  R('sin embargo', 'however', { next: ',' }),
  R('sobre todo', 'especially'),
  R('sobre todo', 'above all'),
  R('luego', 'later', { notNext: 'than', notPrev: 'or|no|sooner|years|days|weeks|months|hours|minutes|the|little|bit|much|week|'
    + 'month|year|day|hour|minute|while|way|a|an|time' }),
  R('luego', 'then', { prev: 'and', next: `${SUBJ}|we|i|you|the|go|we'll|i'll`, notIn: 'now|every' }),
  R('por fin', 'finally'),
  R('por fin', 'at last'),
  R('primero', 'first', { next: 'END', notPrev: 'the|my|your|his|her|our|their|at|was|is|came|come|finished|finish' }),
  R('después', 'afterwards'),
  R('después', 'afterward'),
  R('después', 'after that'),
  R('excepto', 'except', { notNext: `${SUBJ}|that's|there's|everyone` }),
  R('según', 'according to'),
  R('a pesar de', 'despite'),
  R('a pesar de', 'in spite of'),
  R('dónde', 'where', { start: true, next: VERB }),
  R('dónde', 'where', { prev: ASKED }),
  R('por qué', 'why', { notPrev: "that's|thats|is|the|reason|that|exactly|just|literally|partly|probably|maybe" }),
  // "how tall is he" asks a degree (qué tan); "do it how you want" is the way.
  R('cómo', 'how', { notNext: `much|many|long|often|old|far|come|about|to|soon|*ing|*ful|*ible|*ic|*ous|*ly|${ADJ}`, notNext2: VERB,
    notPrev: "that|that's|thats|here's|is|the|this|know|knows|knew|learn|learned|learning|teach|taught|showed|show|it|them" }),
  R('quién', 'who', { start: true, q: true }),
  R('quién', 'who', { prev: ASKED, notIn: PEOPLE }),
  R('qué', 'what', { start: true, q: true, notNext: 'if|about|a|an|kind|else' }),
  R('cuál', 'which', { start: true, q: true, next: 'one|is|do|did|would|should' }),
  R('cuánto', 'how much', { next: `${VERB}|END|longer|i|you|we|they|he|she|it` }),
  R('a veces', 'sometimes'),
  R('pronto', 'soon', { notPrev: 'as|how|too|so' }),
  R('hoy', 'today'),
  R('mañana', 'tomorrow'),
  R('ayer', 'yesterday'),
  R('esta noche', 'tonight'),
  R('todos', 'everyone'),
  R('todos', 'all of them'),
  R('allí', 'there', { notNext: "is|are|was|were|will|isn't|aren't|wasn't|weren't|must|might|should|could|would|may|seems|seem|used|"
    + 'has|have|had|you|goes|it|they|we|i|he|she', notPrev: "is|are|was|were|isn't|aren't|over|hi|hey|so|out|in|than|START",
  next: 'END|now|yet|too|tonight|today|tomorrow|soon|already|right|at|with|by|in|on|for|before|after|together' }),
  R('así', 'like this', { prev: 'it|looks|look|looked|sounds|sounded|feels|felt|is|was|be|just|exactly|said|says|say|talk|talks|'
    + "talking|act|acting|things|something|stuff|always|it's|that's|done|works|work|happens|happened|went|go|goes",
  next: 'END|lol|haha|too|again|now|anymore|before|all|for|with|either|though|tho|right' }),
  R('así', 'like that', { prev: 'it|looks|look|looked|sounds|sounded|feels|felt|is|was|be|just|exactly|said|says|say|talk|talks|'
    + "talking|act|acting|things|something|stuff|always|it's|that's|done|works|work|happens|happened|went|go|goes",
  next: 'END|lol|haha|too|again|now|anymore|before|all|for|with|either|though|tho|right' }),
  R('allá', 'over there'),
  R('para nada', 'not at all'),
  R('alguien', 'someone'),
  R('alguien', 'somebody'),
  R('eso', 'that', { next: 'END', q: false, notPrev: "so|like|is|was|be|it|than|now|all|of|in|at|on|about|with|for|to|who's|what's|"
    + "where's|how's|it's|that's" }),
  R('esto', 'this', { next: 'END', q: false, notPrev: "like|is|was|be|it|than|all|of|in|at|on|about|with|for|to|who's|what's|"
    + "where's|how's|it's|that's" }),
  // "thinking about you" is pensar en.
  R('sobre', 'about', { prev: 'talks|talking|talked|know|knew|book|movie|show|article|story|news|question|questions|ask|asked|'
    + 'asking|hear|heard|read|write|wrote|writing|learn|learned|learning|video|post|podcast|conversation|joke|jokes|chat|chatting',
  notNext: 'NUM|to|it|that|this|what|how|time' }),
  R('la casa', 'the house', { next: NOUN_END }),
  R('la casa', 'house', { as: 'casa', prev: POSS, next: NOUN_END }),
  R('la casa', 'home', { as: 'casa', prev: 'at|go|going|went|get|got|getting|come|coming|came|back|stay|staying|headed|heading|'
    + 'walk|walking|way|from', next: NOUN_END }),
  R('la semana', 'the week', { next: NOUN_END }),
  R('la semana', 'week', { as: 'semana', prev: `${THIS}|next|last|every|per|whole|long|busy|crazy|good|great|rough`, next: NOUN_END }),
  R('el año', 'the year', { next: NOUN_END }),
  R('el año', 'year', { as: 'año', prev: `${THIS}|next|last|every|per|whole|new|good|great|rough|school`, next: NOUN_END }),
  // In a question "any" is algún ("any chance you can come?").
  R('cualquier', 'any', { next: 'time|day|place|kind|moment|size|color|reason', neg: 'no', q: false, start: false,
    notPrev: 'need|want|have|got|there|you|any|do|did' }),
  R('la familia', 'the family', { next: NOUN_END }),
  R('la familia', 'family', { as: 'familia', prev: POSS, next: NOUN_END }),
  R('la ciudad', 'the city', { next: NOUN_END }),
  R('la ciudad', 'city', { as: 'ciudad', prev: THIS, next: NOUN_END }),
  R('el momento', 'the moment', { next: NOUN_END }),
  R('el momento', 'moment', { as: 'momento', prev: 'this|that|one|any|perfect|right|wrong|best|worst|my|your|big', next: NOUN_END }),
  R('la suerte', 'luck', { as: 'suerte', notPrev: 'push|pushing|pushed', next: NOUN_END }),
  R('la historia', 'the story', { next: NOUN_END }),
  R('la historia', 'story', { as: 'historia', prev: THIS, next: NOUN_END }),
  R('la historia', 'history', { as: 'historia', notPrev: 'browser|search|chat|order|credit|medical|purchase', next: NOUN_END }),
  R('la música', 'the music', { next: NOUN_END }),
  R('la música', 'music', { as: 'música', prev: POSS, next: NOUN_END }),
  R('el gato', 'the cat', { next: NOUN_END }),
  R('el gato', 'cat', { as: 'gato', prev: POSS, next: NOUN_END }),
  R('el perro', 'the dog', { next: NOUN_END }),
  R('el perro', 'dog', { as: 'perro', prev: POSS, next: NOUN_END }),
  R('una vez', 'once', { notPrev: 'at|all|for', notNext: `again|more|upon|in|a|an|or|${SUBJ}|the|${THIS}|everyone|everybody|someone` }),
  R('la escuela', 'school', { as: 'escuela', prev: POSS, next: NOUN_END }),
  R('la escuela', 'the school', { next: NOUN_END }),
  R('joven', 'young', { next: PRED, sing: true }),
  R('fuerte', 'strong', { next: PRED, sing: true }),
  R('fuerte', 'loud', { next: PRED, sing: true, notIn: "i'm|im|you're|he's|she's|he|she|you|i|they|we" }),
  R('a ver', "let's see", { next: 'END|if|what|how|who|when|where|which|whether' }),
  R('feliz', 'happy', { next: `${PRED}|birthday|anniversary|new|thanksgiving|${DAYS}|with`, notPrev: 'the', sing: true }),
  R('triste', 'sad', { next: `${PRED}|about`, sing: true }),
  R('libre', 'free', { prev: "you|i'm|im|you're|he's|she's|am", next: `END|${TIME}|this|on|at|after|until|for`, sing: true }),
  R('interesante', 'interesting', { next: PRED, sing: true }),
  R('increíble', 'incredible', { next: PRED, sing: true }),
  R('increíble', 'amazing', { next: PRED, sing: true }),
  R('perfecto', 'perfect', { start: true, next: 'END' }),
  R('excelente', 'excellent', { next: PRED, sing: true }),
  R('diferente', 'different', { next: `${PRED}|from`, sing: true }),
  R('común', 'common', { next: PRED, sing: true }),
  R('rápido', 'quickly'),
  R('rápido', 'fast', { prev: 'run|runs|ran|running|go|goes|went|going|eat|eating|ate|talk|talking|walk|'
    + 'walking|type|typing|grow|grows|grew|growing|move|moves|moving|learn|learns|learning|happened|happens', next: PRED }),

  // Set phrases further down the list.
  R('gratis', 'for free'),
  R('gratis', 'free', { prev: "it's|its|is|was|totally|completely|it", next: 'END', notIn: `${PERSON}|${NOT_FREE}` }),
  R('genial', 'great', { prev: "that's|thats|START|sounds|so|it's|is|was|looks|really", next: 'END', sing: true }),
  // "it's cool" is often "it's fine"; "that's cool" and "sounds cool" are genial.
  R('genial', 'cool', { prev: "that's|thats|START|sounds|so|looks|really", next: 'END', sing: true }),
  R('imposible', 'impossible', { next: PRED, sing: true }),
  R('por favor', 'please', { notPrev: 'to|you|would|easy|hard|hoping' }),
  R('hola', 'hello', { start: true }),
  R('hola', 'hi', { start: true, notNext: 'there|to' }),
  R('lo siento', "i'm sorry", { notNext: 'for|to|about|that|but|you|if|what|huh', q: false }),
  R('lo siento', 'sorry', { start: true, notNext: 'for|to|about|that|i|you|if|but|what|huh', q: false }),
  R('qué tal', "how's it going"),
  R('oye', 'hey', { start: true }),
  R('mira', 'look', { start: true, next: ',' }),
  R('pues', 'well', { start: true, next: ',' }),
  R('ojalá', 'hopefully'),
  R('ojalá', 'i hope so'),
  R('ahorita', 'right now'),
  R('ahorita', 'in a moment'),
  R('cerca de', 'near', { next: `the|${POSS}|here|there|you|me|us|it|home|work|school|downtown`, notPrev: 'the|a' }),
  R('lejos de', 'far from'),
  R('debajo de', 'under', { next: `the|a|an|${POSS}|it|there|here|this|that`,
    notNext2: 'weather|name|impression|lot|stress|pressure|control|influence|radar|age' }),
  R('detrás de', 'behind', { next: `the|a|an|${POSS}|it|you|me|us|him|her|them|this|that` }),
  R('delante de', 'in front of'),
  R('hacia', 'toward'),
  R('hacia', 'towards'),
  R('más bien', 'rather', { notPrev: 'or|i|START', notIn: "would|i'd|id|you'd|we'd|they'd|he'd|she'd", notNext: 'than|not' }),
  R('tanto', 'so much', { notPrev: 'you|thanks|thank|thx|ty|it|that', next: AMOUNT_END }),
  R('a causa de', 'because of'),
  R('gracias a', 'thanks to'),
  R('en lugar de', 'instead of'),
  R('mientras tanto', 'meanwhile'),
  R('al lado de', 'next to'),
  R('al menos', 'at least'),
  R('más o menos', 'more or less'),
  R('seguramente', 'most likely'),
  R('mientras', 'while', { notPrev: 'a|the|for|in|once|worth|little|whole|long|short', notNext: 'END|ago|back|now|longer' }),
  // "can we do tomorrow instead" means in its place; en cambio contrasts ("Instead, ...").
  R('en cambio', 'instead', { start: true, next: ',' }),
  R('apenas', 'barely'),
  R('apenas', 'hardly', { notNext: 'ever' }),
  R('en cuanto', 'as soon as', { notNext: 'possible|you|we|i|they|he|she|it|END' }),
  R('hasta', 'until', { next: TIME }),
  R('hasta', 'until', { next: `the|${POSS}`, next3: NP_END }),
  // "it's so far away" is distance; hasta ahora is "up to now".
  R('hasta ahora', 'so far', { notNext: 'away|from|though|lol|behind|out|ahead|down|up|apart|off',
    notPrev: "it's|is|was|that's|too|very|be|not|its|isn't|wasn't|are|lives|live|so|seems|looks|come|came|gone|went|drove|driven|"
      + 'walked|ran|traveled|made|got|gotten' }),
  R('para que', 'so that', { start: false, next: SUBJ }),
  R('si no', 'otherwise', { notPrev: 'think|hear|heard|say|said|told|unless|do|did|know|knew|decide|decided|prove|believe|suggest' }),
  R('si no', 'if not'),
  R('aun así', 'even so'),
  R('de inmediato', 'right away'),
  R('totalmente', 'totally'),
  R('poco a poco', 'little by little'),
  R('rápidamente', 'quickly'),
  R('despacio', 'slowly'),
  R('suavemente', 'gently'),
  R('en otro lado', 'somewhere else', { notPrev: PLACE_NOT, notNext: 'around|between|like|to|near' }),
  R('en todos lados', 'everywhere', { notPrev: PLACE_NOT, notNext: 'around|between|like|to|near' }),
  R('en ningún lado', 'nowhere', { notPrev: PLACE_NOT, notNext: 'around|between|like|to|near' }),
  R('en algún lado', 'somewhere', { notNext: 'else|where|around|between|like|to|near|good|nice|fun|cheap|quiet', notPrev: PLACE_NOT }),
  R('adentro', 'inside', { next: 'END' }),
  R('afuera', 'outside', { next: 'END' }),
  R('arriba', 'upstairs', { next: 'END|and|now|lol|haha|already|right' }),
  R('abajo', 'downstairs', { next: 'END|and|now|lol|haha|already|right' }),
  R('últimamente', 'lately'),
  R('temprano', 'early', { next: 'END|today|tomorrow|tonight|in|on|for|and', notPrev: 'the|an|too|so|how' }),
  R('tarde', 'late', { next: 'END|today|tomorrow|tonight|again|for|and|to', notPrev: 'the|a|an|too|so|how|of' }),
  R('a tiempo', 'on time'),
  R('mucho tiempo', 'a long time'),
  R('al rato', 'in a little while'),
  R('antes', 'before', { next: 'END', prev: 'it|that|this|him|her|them|you|me|us|here|there|never|ever|once|twice|done|seen|been|met|'
    + 'heard|said|tried|day|week|month|year|night|minutes|hours|days|weeks|months|years|just|right|long|even' }),
  R('antes', 'earlier', { notNext: 'than|this|today|tonight', notPrev: 'the|an' }),
  R('de ahora en adelante', 'from now on'),
  R('aproximadamente', 'approximately'),
  R('aproximadamente', 'roughly'),
  R('por lo tanto', 'therefore'),
  R('exactamente', 'exactly'),
  R('probablemente', 'probably'),
  R('por suerte', 'luckily'),
  R('lamentablemente', 'unfortunately'),
  R('obviamente', 'obviously'),
  R('en serio', 'seriously'),
  R('sin duda', 'no doubt'),
  R('definitivamente', 'definitely'),
  R('completamente', 'completely'),
  R('simplemente', 'simply'),
  R('fácilmente', 'easily'),
  R('casi nunca', 'hardly ever'),
  R('normalmente', 'normally'),
  R('normalmente', 'usually'),
  R('en general', 'in general'),
  R('por cierto', 'by the way'),
  R('por cierto', 'btw'),
  R('a la vez', 'at the same time'),
  R('de todos modos', 'anyway'),
  R('de todos modos', 'anyways'),
  R('en todo caso', 'in any case'),
  R('por otro lado', 'on the other hand'),
  R('en cambio', 'on the other hand'),
  R('además', 'besides', { next: ',|START|END|that' }),
  R('encima', 'on top of that'),
  R('ni', 'nor'),
  R('ni', 'not even'),
  R('cada', 'each', { notNext: `END|other|of|one|${SUBJ}`, notPrev: 'for|to' }),
  R('cada', 'every', { next: `single|morning|night|day|week|month|year|weekend|summer|winter|${DAYS}|hour|minute|second` }),
  R('aquí está', 'here it is'),
  R('una vez más', 'once again'),
  R('una vez más', 'one more time'),
  R('todavía no', 'not yet'),
  R('nada mal', 'not bad', { start: true }),
  R('así así', 'so-so'),
  R('vamos', 'come on', { start: true, notNext: `in|over|down|up|back|out|by|then|NUM|${DAYS}` }),
  R('vamos', "let's go", { next: 'END' }),
  R('buena suerte', 'good luck'),
  R('bien hecho', 'well done', { next: 'END' }),
  R('hasta pronto', 'see you soon'),
  R('adiós', 'goodbye'),
  R('chao', 'bye', { notPrev: 'good' }),
  R('buenos días', 'good morning', { notPrev: GREETING_NOT }),
  R('buenas tardes', 'good afternoon', { notPrev: GREETING_NOT }),
  R('buenas noches', 'good night', { notPrev: GREETING_NOT }),
  R('buenas noches', 'good evening', { notPrev: GREETING_NOT }),
  R('perdón', 'excuse me', { start: true }),
  R('perdón', 'sorry', { start: true, next: `END|,|${SUBJ}` }),
  R('de nada', "you're welcome", { next: 'END' }),
  R('no hay problema', 'no problem', { next: 'END' }),
  R('eso es', 'exactly', { start: true, next: 'END', q: false }),
  R('es verdad', "that's true", { q: false }),
  R('por si acaso', 'just in case'),
  R('no pasa nada', "it's no big deal"),
  R('no pasa nada', 'no big deal'),
  R('qué lástima', 'what a pity'),
  R('qué lástima', 'what a shame'),
  R('depende', 'it depends'),
  R('funciona', 'it works', { next: 'END|now|fine|great|perfectly|for' }),
  // In a question "anything" is algo ("need anything?").
  R('cualquier cosa', 'anything', { neg: 'no', q: false, next: 'END|else',
    notPrev: 'if|is|was|than|need|want|eat|get|have|got|buy|else|you' }),
  R('en cualquier lado', 'anywhere', { neg: 'no', q: false, next: 'END', notPrev: `if|${MOTION}` }),
  R('cuando sea', 'whenever', { next: 'END' }),
  R('parece que', 'it seems that'),
  R('parece que', 'it seems like', { notNext: 'END|a|an|the|it|that|this' }),
  R('quiero', 'i want', { notNext: `${OBJ}|it|that|this|END`, notPrev: "don't|didn't|if|do|really|never" }),
  R('puedo', 'i can', { notNext: 'END|not|tell|see|imagine', notPrev: 'if|so|as|than|what|how' }),
  R('tengo que', 'i have to'),
  R('voy a', "i'm going to"),
  R('voy a', "i'm gonna"),
  R('podemos', 'we can', { notNext: 'END|not', notPrev: 'if|so|as|than|what|how' }),
  R('vamos a', "we're going to"),
  R('vamos a', "we're gonna"),
  R('vamos a', "let's", { notNext: `END|see|go|not|just|be|${OBJ}` }),
  R('había', 'there was', { notNext: `no|not|nothing|nobody|none|never|END|the|${THIS}|these|those|${THERE_NOT}` }),
  R('había', 'there were', { notNext: `no|not|nothing|nobody|none|never|END|the|${THIS}|these|those|${THERE_NOT}` }),
  // "I have" before a past participle is a helper verb (he), not tener.
  R('tengo', 'i have', { notNext: 'been|*ed|*en|done|seen|gone|had|got|gotten|made|to|never|already|just|always|said|told|heard|'
    + 'known|met|left|found|lost|bought|brought|thought|felt|kept|no|nothing|END|it|that|this|ever|not|become|come|run|won|begun|'
    + 'sent|spent|put|read|let|hit|cut|set|quit|paid|slept|chosen|taught|caught|fought|sold|understood|held|built|worn|grown|'
    + 'shown|thrown|flown|drunk|sung|swum|lent|meant|won|led|fed|struck|stuck|hung|dealt|heard|lit|shot|shut|split|spread|bet',
  notPrev: 'if|do|did|would|will|could|should' }),
  R('por eso', "that's why"),
  R('en este momento', 'right now'),
  R('en este momento', 'at the moment'),
  R('en mi opinión', 'in my opinion'),
  R('al final', 'in the end'),
  R('al principio', 'at first', { notNext: 'sight|glance' }),
  R('de vez en cuando', 'from time to time'),
  R('todos los días', 'every day'),
  // Before a clause it is cada vez que.
  R('cada vez', 'every time', { next: 'END|lol|haha|now|again|though|tho' }),
  R('cada vez', 'each time', { next: 'END|lol|haha|now|again|though|tho' }),
  R('la mayoría', 'the majority', { next: NOUN_END }),
  R('la mayoría', 'most', { next: 'of', notNext2: 'it|this|that|the', notPrev: 'the|at' }),
  R('el resto', 'the rest', { next: NOUN_END }),
  R('muchísimo', 'a whole lot'),
  R('me encanta', 'i love it', { next: 'END' }),
  R('me molesta', 'it bothers me'),
  R('la diferencia', 'the difference', { next: NOUN_END }),
  R('no me importa', "i don't care"),
  R('ya veremos', "we'll see", { next: 'END' }),
];
