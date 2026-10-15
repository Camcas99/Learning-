# Welcome to Spanish Weave

Hi! I built this with Claude so I could pick up Spanish from the reading I already do, and I wanted you to have
it too. Here's everything you need, in the order you'll need it.

## What it is

Spanish Weave swaps a few Spanish words into English you're already reading: Claude's replies, and (if you want)
web pages in Chrome. You read normally; the words sink in.

> The build passes ahora, pero the cache is stale, entonces I cleared it.
> (ahora = now, "ah-OH-rah"; pero = but, "PEH-roh"; entonces = so, "en-TOHN-ses")

It teaches Latin American Spanish, the Spanish of Mexico, Central and South America and the US.

## How it works, in 60 seconds

- **You start with about 5 words** (y = and, pero = but, entonces = so, con = with, sin = without) and get up to 5
  new ones a day, never more than 20 at once.
- **A word becomes "known"** once you've seen it on 3 different days without needing to look it up. Words you look
  up a lot, or forget after you knew them, become "shaky" and show up more until they stick.
- **The Spanish grows with you.** Stage 1 is about 1 word in 16; at 40 known words you reach Stage 2, then 3 (150
  words) and 4 (400 words), where short, easy Spanish sentences start to appear.
- **It never gets in the way.** No Spanish in code, files or anything you'd share, and none at all on health,
  legal, money, safety, emergency or driving topics.

Why it works: you learn words best from text you can mostly understand, with a little that's new, and every time
you have to pull a meaning out of memory (instead of looking it up), it sticks better.

## Pick how to start

**1. Try it in 2 minutes, no install (claude.ai or ChatGPT).**
Open [`blocks/level-01.md`](blocks/level-01.md), copy the claude.ai block, and paste it into claude.ai under
Settings > Profile > personal preferences (or the ChatGPT boxes under Settings > Personalization > Custom
instructions). Chat as usual. When those 25 words feel easy, paste level 2 instead.

**2. The full version, with Claude Code (recommended).**
Tell Claude Code: *"Set up Spanish Weave from https://github.com/Camcas99/Learning- (the language/spanish-weave
folder). Read language/spanish-weave/HANDOFF-FOR-CLAUDE.md first."* It asks a few questions and does the rest.
This version tracks your words for you, quizzes you, and can place you at your level.

**3. Everywhere you read, with the Chrome extension.**
During setup, say yes to the Chrome extension. You'll need a free Gemini API key from
https://aistudio.google.com/apikey, which you paste into the extension's popup yourself (never into a chat). Then
in Chrome: `chrome://extensions` > Developer mode > Load unpacked > the folder Claude names > click the Spanish
Weave icon > Allow all websites. It works on X, Instagram's website, articles, anything with English text.

Already know some Spanish? Pick "Not sure: take a 2-minute placement test" during setup, or run
`/spanish-weave:placement` later. You'll mark the words you know from a list; a few are made up, so only mark ones
you could actually translate (pick three made-up ones and it asks you to try again). The words it marks known still
come up in your quizzes over the next few weeks, so any you don't really know go back to learning.

## The best way to use it

1. **Just read.** Don't stop to study every Spanish word. Let the sentence tell you what it means.
2. **Guess before you look.** In Chrome the meaning shows only after a short pause on purpose: try to recall it
   first. In chat, the meanings are in the footer at the end.
3. **Answer the "Recall: ...?" question in your head** before you read the answer at the end of the reply. It
   shows up every few replies, and it's the most valuable 3 seconds of the day.
4. **Quiz for 3 to 5 minutes most days** with `/spanish-weave:quiz`. Words you get right come back after longer and
   longer gaps (3 days, a week, two weeks...). Missed words come back soon, and the quiz asks them once more at the
   end, so you always finish on a right answer. That spacing is what turns "I've seen it" into "I know it".
5. **Say words out loud.** The hints show the stressed syllable in capitals: `también` = `tahm-BYEN`. In Chrome,
   Alt+click (Option+click on a Mac) a Spanish word to hear it, or turn on "Say words aloud when the meaning shows"
   in the extension's popup. Underline colors tell you a noun's gender: teal for masculine (el), rose for feminine
   (la), a little fainter once you know the word.
6. **Once you know about 40 words, try writing a little:** `/spanish-weave:output on` adds an optional "Your turn"
   line every fifth reply. Answer it and you'll get a gentle one-line correction.
7. **Keep it honest.** `/spanish-weave:known pero` for words you truly know; `/spanish-weave:learn pero` for ones you
   want back. Accents are optional when you type.
8. **Watch the false friends.** Some words look like English but aren't: el éxito = success (not "exit"),
   embarazada = pregnant (not "embarrassed"). Those words carry a note, so you'll see it in the gloss.
9. **Add real Spanish when you're ready:** a podcast, a show with Spanish subtitles, a few Instagram accounts in
   Spanish. Spanish Weave builds the vocabulary; real input makes it fluent.

## Reading the sound hints

| Hint | Means |
|---|---|
| CAPITALS | the stressed syllable: ahora = `ah-OH-rah` |
| `ah eh ee oh oo` | the five Spanish vowels, short and clean |
| `rr` | a rolled r: perro = `PEH-rroh` |
| `b` | both b and v (they sound the same): vez = `bes` |
| `h` | a breathy h for j, and for g before e/i: trabajo = `trah-BAH-hoh`. A written h is silent: hola = `OH-lah` |
| `s` | z, and c before e/i: gracias = `GRAH-syahs` |
| `y` / `ny` | ll and ñ: llamar = `yah-MAHR`, mañana = `mah-NYAH-nah` |

## Commands (in Claude Code)

| Type this | To |
|---|---|
| `/spanish-weave:status` | see your stage, words, and what's due for review |
| `/spanish-weave:quiz` | do a short spaced-repetition quiz |
| `/spanish-weave:placement` | take the placement test |
| `/spanish-weave:known <word>` / `learn <word>` | mark a word known, or bring it back |
| `/spanish-weave:stage 1-4` / `stage auto` | set the amount of Spanish yourself, or let it follow your progress |
| `/spanish-weave:output on` / `off` | turn "Your turn" practice on or off |
| `/spanish-weave:pause` / `resume` | take a break from Spanish everywhere |
| `/spanish-weave:export` | get an up-to-date block for claude.ai or ChatGPT (refresh it weekly) |
| `/spanish-weave:anki` | export your words to Anki, if you use it |

With the pasted block in claude.ai or ChatGPT, you can type a word with a question mark ("pero?") for a quick
translation, "quiz" for a three-word quiz, "story" to retell the last answer as a short story at your level, or
"easier" / "harder". In Claude Code, just ask ("what does pero mean?") or use the commands above.

## Instagram and your phone

- **Instagram's website** (instagram.com in Chrome): yes. Captions, comments and bios get the same treatment as
  everything else. Your direct messages are never touched.
- **The Instagram app**: no. Phone apps can't be changed by other software; that's how iPhone and Android keep
  apps safe. On a phone, open instagram.com in a browser that supports extensions instead.

## Privacy

Your words and progress stay on your computer, in a `.spanish-weave` folder. The Claude Code part reads your local
chat history only to count which words you've seen, and never sends it anywhere. The Chrome extension sends the
text of pages it runs on to Google's Gemini with your own key (free keys allow Google to use it for training).
Email, AI chat sites and local addresses are off by default, Instagram messages are never read, and you can turn
off any site from the toolbar.

## If something's off

- **No Spanish in Claude's replies:** open a new Claude Code session (the plugin loads at start), and check
  `/spanish-weave:status` isn't paused.
- **No Spanish on websites:** click the Spanish Weave icon. Is it on, is there a Gemini key, and is the site allowed?
- **Too much or too little:** type "easier" or "harder" in a chat, or `/spanish-weave:stage 1`.
- **Anything else:** ask your Claude to read `language/spanish-weave/HANDOFF-FOR-CLAUDE.md` and help.

Have fun with it. ¡Buena suerte! (good luck, "BWEH-nah SWEHR-teh")

— Cameron

*Spanish Weave is adapted from [French Weave](https://github.com/jackieoliver/french-weave) by Jackie Oliver, MIT
license.*
