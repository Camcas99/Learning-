import { describe, test, expect } from 'bun:test';
import { readFileSync } from 'node:fs';
import { CHAT_RULES, CHAT_SYNONYMS } from '../src/chatrules.js';
import { weave, wovenText, skipReason } from '../src/chatweave.js';
import { SYNONYMS, glossMatch, isVerbEntry, keepsMeaning, exactEs } from '../src/levels.js';

// The lexicon as the Mac would share it, every word in use: rules are checked one at a time, so status and density
// don't hide a wrong swap.
const LEXICON = readFileSync(new URL('../../data/lexicon.csv', import.meta.url), 'utf8').trim().split('\n').slice(1)
  .map((line) => {
    const cells = [...line.matchAll(/("([^"]*)"|[^,]*)(,|$)/g)].map((m) => m[2] ?? m[1]);
    return { es: cells[0], en: cells[1], hint: cells[2], status: 'active' };
  });
const all = (text) => wovenText(weave(text, LEXICON, { cap: false }).parts);
const list = (...pairs) => pairs.map(([es, status]) => ({ ...LEXICON.find((w) => w.es === es), status }));

describe('rules', () => {
  test('every rule names a list word and English that keeps its gloss', () => {
    const byEs = new Map(LEXICON.map((w) => [exactEs(w.es), w]));
    const synonyms = { ...SYNONYMS };
    for (const [k, v] of Object.entries(CHAT_SYNONYMS)) synonyms[k] = [...(synonyms[k] || []), ...v];
    for (const rule of CHAT_RULES) {
      const word = byEs.get(exactEs(rule.es));
      expect([rule.es, Boolean(word)]).toEqual([rule.es, true]);
      // A rule that needs a negative earlier in its clause ("I don't either") may be checked with it.
      const fits = (en) => Boolean(glossMatch(en, word.en, synonyms, isVerbEntry(word.es))) && keepsMeaning(en, word.en);
      const ok = fits(rule.en) || (rule.neg === 'yes' && fits(`not ${rule.en}`));
      expect([rule.es, rule.en, word.en, ok]).toEqual([rule.es, rule.en, word.en, true]);
    }
  });
  test('options are the documented ones, sets hold single tokens, a bare form drops only the article', () => {
    const known = new Set(['es', 'en', 'as', 'prev', 'notPrev', 'next', 'notNext', 'next2', 'notNext2', 'next3', 'notIn', 'sing',
      'start', 'q', 'neg']);
    for (const rule of CHAT_RULES) {
      for (const k of Object.keys(rule)) expect([rule.es, rule.en, k, known.has(k)]).toEqual([rule.es, rule.en, k, true]);
      for (const k of ['prev', 'notPrev', 'next', 'notNext', 'next2', 'notNext2', 'next3', 'notIn']) {
        if (rule[k] === undefined) continue;
        for (const item of rule[k].split('|')) expect([rule.en, k, item, /^\S+$/.test(item)]).toEqual([rule.en, k, item, true]);
      }
      expect(rule.en).toBe(rule.en.toLowerCase());
      if (rule.as) expect(rule.es.replace(/^(el|la|los|las) /, '')).toBe(rule.as);
      if (rule.neg) expect(['no', 'yes', 'near']).toContain(rule.neg);
      if (rule.sing !== undefined) expect(rule.sing).toBe(true);
    }
  });
  test('words that change with the speaker\'s gender have no rule', () => {
    const ruled = new Set(CHAT_RULES.map((r) => r.es));
    for (const es of ['listo', 'bueno', 'malo', 'seguro', 'pequeño', 'nuevo', 'cansado', 'contento', 'el amigo', 'es', 'soy', 'estaba']) {
      expect([es, ruled.has(es)]).toEqual([es, false]);
    }
  });
});

describe('where a word swaps', () => {
  test.each([
    ['Thanks so much for the ride, see you tomorrow!', 'Gracias so much for the ride, see you mañana!'],
    ["I'm not sure where it is. Where are you?", "I'm not sure dónde it is. Dónde are you?"],
    ["It's the place where we met", "It's the place donde we met"],
    ['Is this the place where we met?', 'Is this the place donde we met?'],
    ['Well, I think so', 'Pues, I think so'],
    ["It's fine, I'm doing well", "It's bien, I'm doing bien"],
    ["The answer is no. What's your answer?", "La respuesta is no. What's your respuesta?"],
    ['No problem! The problem is my car', 'No hay problema! El problema is my car'],
    ["There's a party tonight and there are snacks", 'Hay a party esta noche y hay snacks'],
    ["So, are you coming? I'm so tired lol", "Entonces, are you coming? I'm tan tired lol"],
    ['I love you too', 'I love you también'],
    ['This is for you', 'This is para you'],
    ["It's not red but blue", "It's not red sino blue"],
    ["I'll be there in a minute, a little late", "I'll be allí in a minute, un poco tarde"],
    ['Can you come here?', 'Can you come aquí?'],
    ['I still have it', 'I todavía have it'],
    ["I haven't eaten yet", "I haven't eaten todavía"],
    ['Not yet', 'Todavía no'],
    ['I never go there', 'I nunca go allí'],
    ['More or less', 'Más o menos'],
    ['It looks like that. Do it like this', 'It looks así. Do it así'],
    ['How are you? How much is it?', 'Cómo are you? Cuánto is it?'],
    ['Because of the rain', 'A causa de the rain'],
    ["Are you free tonight? It's free, we got it for free", "Are you libre esta noche? It's gratis, we got it gratis"],
    ['Happy birthday!! I\'m so happy for you', 'Feliz birthday!! I\'m tan feliz for you'],
    ["It's important to me", "It's importante to me"],
    ["Before the party, I need coffee. I've seen it before", "Antes de the party, I need coffee. I've seen it antes"],
    ['after work, after lunch', 'después de work, después de lunch'],
    ["I have to go. I'm gonna be late", "Tengo que go. Voy a be tarde"],
    ['We\'re going to the beach. Let\'s eat. Let\'s go!', 'Vamos a the beach. Vamos a eat. Vamos!'],
    ['By the way, anyway, seriously?', 'Por cierto, de todos modos, en serio?'],
    ["You're welcome. That's true.", 'De nada. Es verdad.'],
    ["I think it's great", "Creo que it's genial"],
    ['At home, my house, the house', 'At casa, my casa, la casa'],
    ['until tomorrow', 'hasta mañana'],
    ['Thanks for coming', 'Gracias for coming'],
    ['Nobody came, nothing happened', 'Nadie came, nothing happened'],
    ["I don't like it either", "I don't like it tampoco"],
    ['So far, so good', 'Hasta ahora, tan good'],
    ['since high school', 'desde high school'],
    ['I like it so far', 'I like it hasta ahora'],
    ['too much for me', 'demasiado para me'],
    ['even my mom came', 'incluso my mom came'],
    ['We talked about the trip', 'We talked sobre the trip'],
    ["i'm free after 3", "i'm libre after 3"],
    ['Sorry?', 'Perdón?'],
    // y is e before an i sound and o is u before an o sound, when the next word is Spanish too.
    ['it was fun and interesting', 'it was fun e interesante'],
    ['Today or again tomorrow', 'Hoy u otra vez mañana'],
    // "a causa de el tiempo" would need del: the second swap stays English.
    ['because of the weather', 'a causa de the weather'],
    ['@sam Thanks for coming', '@sam Gracias for coming'],
    ['❤️ Thank you so much', '❤️ Gracias so much'],
    ['Look at www.example.com. Thanks for coming', 'Look at www.example.com. Gracias for coming'],
  ])('%s', (text, woven) => expect(all(text)).toBe(woven));
});

describe('where English stays', () => {
  test.each([
    'Wait for me', // para never after wait
    "I'm going without you. Without asking?", // sin never before an -ing word ... or a clause
    "I don't like it but I'll eat it", // a negative earlier: pero or sino isn't clear
    "I don't have a car but my mom does", 'I dont want tea but coffee',
    'Stand still. Still, it is', 'i know but still', // still as an adjective, "however" or "even so"
    'Never mind', 'never again', 'The very first time', 'my very first concert', 'Very much', 'No more. One more thing',
    'I like that!', 'I know how to swim', 'What a day!', 'Is that ok?', "it's like that one movie",
    "I'm not sure. Make sure you eat", // seguro changes with the speaker's gender
    'An important meeting', // an adjective before its noun would have to agree
    'after we left', 'before we eat', 'since you left', 'until we meet', // clauses after a preposition
    'before it gets dark', 'before my mom gets home', 'after the kids go to bed', 'until it stops raining',
    'since this is your first time', 'once you get it',
    'each other', 'at once', 'once upon a time', 'home run', 'meet at the dog park', 'the world cup',
    'And/or whatever', 'Watching Always Sunny, THANK YOU', // glued words, names and titles, capitals
    'We watched Mr. Nobody last night', 'Have you seen Dr. Who?', 'a never‐ending story',
    "That's too bad", 'Me too', 'Hi there', 'same here', 'here u go', 'feeling under the weather',
    'How often do you go? How long?', "That's how I know", 'how exciting', 'how awful',
    'well-known', 'so-called', "We'd better go", 'rather not', 'might as well', 'i think otherwise', 'anyone but him',
    "i don't even know", 'did you even try', 'not really', 'see you in a bit', "it's so far away", 'thinking about you',
    'when do you get off work', 'until when', 'idk when he is coming', 'have you finished yet',
    'do you need anything', 'anything else?', 'Any chance you can come', 'I didnt say anything',
    'There\'s my bus', 'we\'re free', 'the kids are happy', 'he is free', 'so do i', 'so what', 'excited for you',
    'good for you', 'a week later', 'a little later than i thought', 'can we do it instead', "let's go somewhere else",
    'take it easy', 'nah it\'s cool', 'sure?', "that's it?", 'come on in', 'i have paid you back', 'you have to come',
    'so much food', 'how much food do we need',
    // Found by the second review.
    'no but fr that was the best night', 'i can\'t but Sam can', 'she doesn\'t drink but she\'ll come', 'not cheap but so worth it',
    'have a good night!!', 'it was a good night honestly', 'every time i see that meme i lose it', 'There was no one',
    "there's gonna be so much food", "there's been a change of plans", 'omg there\'s Sarah!!', 'im at the mall where are you',
    'where i live', 'come with me', "i'm in love with this song", "lol what's his name again?", 'then again',
    'once the movie ends', 'when you coming', 'would you rather go to the beach', "i'd much rather not", 'anything for you',
    'i came back for you', 'of course not', 'my calendar is free', 'the bathroom is free', "let's go out somewhere",
    'it came out of nowhere', 'better days are coming', 'life is short', 'i love music', 'pick up the kids from school',
    "it would be perfect except it's supposed to rain", 'happy holidays', 'the reservation is under my name', 'how tall is he',
    'just do it how you want', "you've come so far", '5 more minutes', "i'm easy, whatever you want", 'ate quite a bit',
    'after a bit it got better', 'i have nothing to wear', "ok we're even now lol", 'talk about awkward', 'love at first sight',
    'the upstairs neighbors', "only problem is i don't have a car", 'it was not bad at all',
  ])('%s', (text) => expect(all(text)).toBe(text));
  test.each([
    ['you guys are so fast', 'rápido'], ["you're so loud lol", 'fuerte'], ["that's exactly why i left early", 'por qué'],
    ["That's it, thanks!", 'Eso es'], ['you better be there', 'mejor'], ["most of the time he's fine", 'mayoría'],
  ])('%s keeps %s out', (text, es) => expect(all(text)).not.toContain(es));
});

describe('links, codes and serious topics', () => {
  test('links, addresses, handles and code are never woven, and phrases never cross them', () => {
    expect(all('Check out www.example.com and tell me')).toBe('Check out www.example.com y tell me');
    for (const text of ['https://and.com/but/now', 'mail me at but@now.com', '@always #maybe', '`and or but`', 'now.app']) {
      expect(all(text)).toBe(text);
    }
  });
  test.each([
    ['Your code is 482913. Do not share it.', 'code'],
    ['G-482913 is your Google verification code', 'code'],
    ['Use 123-456 to sign in', 'code'],
    ['Your Steam Guard code is 4VJ8K and you need it to log in.', 'code'],
    ['Your code is K7XQ9P. Enter it now', 'code'],
    ['Your code is 482 913. Enter it now', 'code'],
    ['Your Amazon one-time password is 48 29 13.', 'code'],
    ['Enter 482913 now to finish, and thanks', 'code'],
    ['482913 — don’t share this with anyone.', 'code'],
    ['Tap here to sign in now, it expires tonight: https://slack.com/z/AbCxyz123q', 'code'],
    ['Use code SAVE20 at checkout', 'code'],
    ['My grandma passed away last night and I am sad', 'topic'],
    ['My grandma passed this morning, can you come over tonight?', 'topic'],
    ['So sorry for your loss, I am here for you', 'topic'],
    ['Can you drive me to my doctor appointment tomorrow?', 'topic'],
    ['Call me now, it is urgent', 'topic'],
    ['I want to die', 'topic'],
    ['kms honestly, everything is too much right now', 'topic'],
    ['My dad had a heart attack, we are at the ER now', 'topic'],
    ['He hit me again last night', 'topic'],
    ['I got in an accident on the freeway, I am ok', 'topic'],
    ["There's a fire in our building, we are outside", 'topic'],
    ['He got arrested last night', 'topic'],
    ['I got fired today', 'topic'],
    ['My back hurts so much, I can barely walk', 'topic'],
    ['The funerals are on Saturday and Sunday', 'topic'],
    ["I'm on the road, text you when I get there", 'topic'],
    ['USAA: 482913 is your access number. Expires in 5 min.', 'code'],
    ['Your Slack confirmation code is LKQ-7MP', 'code'],
    ['The wake is on Friday and the burial is Saturday', 'topic'],
    ['Help! Come quick please', 'topic'],
    ["She's sick, she can't come", 'topic'],
    ['a '.repeat(2500), 'long'],
  ])('%s stays English: %s', (text, reason) => {
    expect(skipReason(text)).toBe(reason);
    const r = weave(text, LEXICON, { cap: false });
    expect([r.skipped, r.swaps, wovenText(r.parts)]).toEqual([reason, 0, text]);
  });
  test.each([
    'Meet at 1200 and then we can go', 'The game is at 7', "I'm dying laughing 😂 that was so good",
    'Dead tired, going to bed early', 'My phone is dead, I will call you later', 'Let me know asap if you want pizza',
    'Not urgent, but can you send me the recipe?', 'Did you sign in to the 2026 fantasy league yet?',
    'Security deposit is 1500, but the place is so nice', 'Our room is B-1204, come by after dinner',
    'I have a hair appointment at 3, then I am free', "You're driving me crazy lol", 'I deleted it by accident',
    'Can you lend me your charger?', 'My zip code is 94110', 'Can you help me pick a dress?', 'Rent is $2400 this month',
    'that concert was sick 🔥', "i'm sick of this", 'i need help picking an outfit', 'he hit me up last night',
    'she beat me at mario kart again', 'you scared me to death lmao', 'im dead lolol', 'the walking dead finale was insane',
    'we got robbed, that ref was blind', 'i deleted it on accident', 'I need help with my homework', 'I passed my driving test!',
  ])('%s may be woven', (text) => expect(skipReason(text)).toBe(''));
  test('odd input stays fast', () => {
    for (const text of ['-'.repeat(3999), 'a.'.repeat(1999), 'but '.repeat(999), `https://${'.'.repeat(3990)}`]) {
      const t0 = performance.now();
      weave(text, LEXICON);
      expect(performance.now() - t0).toBeLessThan(500);
    }
  });
});

describe('density and the word list', () => {
  test('one swap per ten words, at most two a sentence, each word once, learning words first', () => {
    const words = list(['y', 'known'], ['pero', 'known'], ['gracias', 'active'], ['mañana', 'shaky'], ['con', 'known']);
    const r = weave('Thanks and see you tomorrow, but I will come with you and with him and then we eat and go home', words);
    // 21 words: two swaps, the learning ones, though known words come first in the text.
    expect(r.swaps).toBe(2);
    expect(r.parts.filter((p) => typeof p !== 'string').map((p) => p.word)).toEqual(['gracias', 'mañana']);
    const short = weave('ok thanks and bye', words);
    expect(wovenText(short.parts)).toBe('ok gracias and bye'); // a short text still gets one
    expect(weave('Thanks and see you at the game but I will come with him', words).swaps).toBe(1); // 14 words
    const long = weave('And then and then and then and then and then and then. And yes and no and maybe and then', words);
    expect(long.parts.filter((p) => typeof p !== 'string').map((p) => p.word)).toEqual(['y']); // each word once
    // 30 words allow three, but one sentence takes two.
    const three = list(['gracias', 'active'], ['hoy', 'active'], ['mañana', 'active']);
    const text = 'thanks for today and see you tomorrow at the park with everyone from work and school and the rest of the team '
      + 'we love so much and miss a lot';
    expect(weave(text, three).swaps).toBe(2);
    expect(weave(text.replace('today and', 'today. and'), three).swaps).toBe(3);
  });
  test('words in the queue never show, and an unknown status is ignored', () => {
    const words = list(['y', 'queue'], ['pero', 'known'], ['gracias', 'retired']);
    expect(wovenText(weave('Thanks and good, but late', words).parts)).toBe('Thanks and good, pero late');
    expect(weave('Thanks and but', []).swaps).toBe(0);
    expect(weave('Thanks and but', undefined).swaps).toBe(0);
  });
  test('a list changed in place is seen', () => {
    const words = list(['gracias', 'active']);
    expect(weave('Thanks!', words).parts[0].status).toBe('active');
    words[0].status = 'known';
    expect(weave('Thanks!', words).parts[0].status).toBe('known');
    words[0].status = 'retired';
    expect(weave('Thanks!', words).swaps).toBe(0);
    words.push({ ...LEXICON.find((w) => w.es === 'mañana') });
    expect(wovenText(weave('see you tomorrow', words).parts)).toBe('see you mañana');
  });
  test('each swap carries its English, meaning, sound hint and list word; a bare noun loses its article', () => {
    const words = list(['el problema', 'active'], ['gracias', 'known']);
    const parts = weave('My problem? Thanks', words, { cap: false }).parts;
    expect(parts).toEqual([
      'My ',
      { o: 'problem', es: 'problema', g: 'problem', h: 'proh-BLEH-mah', word: 'el problema', status: 'active' },
      '? ',
      { o: 'Thanks', es: 'Gracias', g: 'thank you', h: 'GRAH-syahs', word: 'gracias', status: 'known' },
    ]);
    // The original is always recoverable from the parts.
    expect(parts.map((p) => (typeof p === 'string' ? p : p.o)).join('')).toBe('My problem? Thanks');
  });
  test('capitals follow the sentence: first word up, and I lowercase inside a sentence', () => {
    const words = list(['creo que', 'active'], ['gracias', 'active']);
    expect(wovenText(weave('I think we should. so I think we can', words, { cap: false }).parts))
      .toBe('Creo que we should. so creo que we can');
    expect(wovenText(weave('thanks!', words).parts)).toBe('gracias!');
    expect(wovenText(weave("Thanks, I'm gonna be late", words).parts)).toBe("Gracias, I'm gonna be late");
    expect(all('THANKS for everything')).toBe('THANKS for todo');
  });
  test('curly apostrophes match like straight ones', () => {
    expect(all('I’m gonna be late')).toBe('Voy a be tarde');
  });
  test('odd input does not throw', () => {
    for (const text of ['', null, undefined, 42, '???', '\n\n', '🙂🙂', 'a'.repeat(5000)]) {
      expect(() => weave(text, LEXICON)).not.toThrow();
    }
    expect(weave(null, LEXICON).parts).toEqual([]);
  });
});
