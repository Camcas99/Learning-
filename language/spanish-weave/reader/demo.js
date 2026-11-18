// Made-up threads and a word list for trying the reader with no Mac helper. Nothing here is a real message or person.
// The words copy data/lexicon.csv (reader.test.js checks), with statuses like a learner's first weeks.
const W = (es, en, hint, status) => ({ es, en, hint, status });

export const DEMO_WORDS = [
  W('y', 'and', 'ee', 'known'),
  W('pero', 'but', 'PEH-roh', 'known'),
  W('entonces', 'so / then', 'en-TOHN-ses', 'known'),
  W('con', 'with', 'kohn', 'known'),
  W('también', 'also / too', 'tahm-BYEN', 'known'),
  W('ahora', 'now', 'ah-OH-rah', 'known'),
  W('para', 'for / in order to', 'PAH-rah', 'known'),
  W('porque', 'because', 'POR-keh', 'known'),
  W('siempre', 'always', 'SYEM-preh', 'known'),
  W('sí', 'yes', 'see', 'known'),
  W('claro', 'of course / sure', 'KLAH-roh', 'known'),
  W('muy', 'very', 'mwee', 'shaky'),
  W('tal vez', 'maybe', 'tahl bes', 'active'),
  W('gracias', 'thank you', 'GRAH-syahs', 'active'),
  W('el problema', 'the problem', 'el proh-BLEH-mah', 'active'),
  W('o', 'or', 'oh', 'active'),
  W('donde', 'where (not a question)', 'DOHN-deh', 'active'),
  W('bien', 'well / fine', 'byen', 'active'),
  W('un poco', 'a little', 'oon POH-koh', 'active'),
  W('hay', 'there is / there are', 'eye', 'active'),
  W('más', 'more', 'mahs', 'active'),
  W('ya', 'already', 'yah', 'active'),
  W('todavía', 'still / yet', 'toh-dah-BEE-ah', 'active'),
  W('otra vez', 'again', 'OH-trah bes', 'active'),
  W('nunca', 'never', 'NOON-kah', 'active'),
  W('la respuesta', 'the answer', 'lah rres-PWES-tah', 'shaky'),
  W('mañana', 'tomorrow', 'mah-NYAH-nah', 'queue'),
];

const M = (id, from, minutesAgo, text) => ({ id, from, minutesAgo, text });

export const DEMO_THREADS = [
  { id: 'maya', name: 'Maya', messages: [
    M('m1', 'Maya', 96, 'Hey! Are you still coming tonight?'),
    M('m2', 'me', 94, "Yes, I'll be there around 8. Is that ok?"),
    M('m3', 'Maya', 93, "Perfect. There's parking behind the building, and the gate code is 4417"),
    M('m4', 'Maya', 92, "Thanks again for helping me move last week, you're the best"),
    M('m5', 'me', 90, 'Of course! It was fun, even the couch part'),
    M('m6', 'Maya', 41, 'Maybe we can get tacos after? I know a place where they make them fresh'),
  ] },
  { id: 'crew', name: 'Climbing crew', group: true, messages: [
    M('c1', 'Jordan', 300, "Who's in for Saturday? The weather looks good but it might rain later"),
    M('c2', 'Sam', 290, "I'm in! I have to leave early though"),
    M('c3', 'Priya', 285, "Me too. I've never climbed outdoors, so be patient with me"),
    M('c4', 'Jordan', 280, "No problem, we'll start with the easy routes. Bring water and a little snack"),
    M('c5', 'me', 200, 'Count me in. I can bring more rope if we need it'),
    M('c6', 'Sam', 180, 'Perfect, there is more room in my car now anyway'),
  ] },
  { id: 'dad', name: 'Dad', messages: [
    M('d1', 'Dad', 1500, 'Did you call your grandma yet? She asked about you again'),
    M('d2', 'me', 1490, "Not yet, I'll call her tonight"),
    M('d3', 'Dad', 1480, 'Good. Also the doctor said my knee is fine, nothing to worry about'),
    M('d4', 'Dad', 1470, 'Love you, talk soon'),
  ] },
  { id: 'code', name: '45678', messages: [
    M('v1', '45678', 2900, 'Your verification code is 381204. Do not share it with anyone.'),
  ] },
];
