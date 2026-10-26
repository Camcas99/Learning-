# Spanish Weave

Learn Latin American Spanish passively from the English you already read. Spanish Weave swaps a few Spanish words
into AI chat replies and the web pages you read, at your level, and moves words from learning to known as you see
them.

> The build passes ahora, pero the cache is stale, entonces I cleared it.
> (ahora = now, "ah-OH-rah"; pero = but, "PEH-roh"; entonces = so, "en-TOHN-ses")

New here? Read [START-HERE.md](START-HERE.md). Claude sessions picking this up: read
[HANDOFF-FOR-CLAUDE.md](HANDOFF-FOR-CLAUDE.md).

Adapted from [French Weave](https://github.com/jackieoliver/french-weave) by Jackie Oliver (MIT license): same
design and code, with a new Spanish word list, sound hints, grammar rules and prompts. Version 0.3.2 also ports
later French Weave improvements: wider default-off sites, a sensitive-title guard, no swaps inside contractions or
ALL-CAPS words, a 3-day swap cache, logged-out X support, and several sense guards and glosses. Version 0.3.3 adds
92 more words (sino, tampoco, aunque, no funciona...), a check that each web swap matches its word's meaning, faster
swaps while scrolling, a wait for Gemini's daily quota, a hover gloss pages can't clip, Claude Haiku as an optional
model, and a clipboard copy of the claude.ai export. With the plugin, the new words come in at their place in the
list, so if you already know many words, a few basic new ones (sino, tampoco, incluso...) come up for learning first.
The paste-in levels keep their words: the new words fill new levels 43 to 46.

## Set up

**Claude Code or Codex.** Tell your agent:

```
Set up Spanish Weave from https://github.com/Camcas99/Learning- (the language/spanish-weave folder)
```

Or install the plugin yourself in Claude Code, one line at a time:

```
/plugin marketplace add Camcas99/Learning-
/plugin install spanish-weave@learning
/reload-plugins
/spanish-weave:setup
```

On Claude Code 2.1.275 or later, `/plugin install spanish-weave --marketplace Camcas99/Learning-` does the first
two lines in one step (in a terminal, `claude plugin install spanish-weave --marketplace Camcas99/Learning-` needs
2.1.292 or later). The Claude Code and Chrome parts need macOS or Linux for now; on Windows, use the paste-in blocks
below.

Setup first asks a few questions in one go: how much Spanish you know already (none, a few basic words, or simple
Spanish, which starts you at Stage 1, 2 or 3), where Spanish should show up (Claude Code, Codex, the Chrome
extension, a claude.ai or ChatGPT block), whether the extension runs on every site or only ones you turn on (the
question says what goes to Gemini; see Privacy), and how you'll give it a Gemini key. Skip any question to take the
default. Rerunning setup (`/spanish-weave:setup`) asks again, with "Keep the current site choice" as the default for
the websites question, and never resets your progress. Words you've made progress on keep their status, so if you
rerun setup with a higher answer, you can start one stage lower until those words graduate, after about 3 days of
seeing them. The first learning words the plugin hands out on your first prompt don't count against you: if you
haven't seen them yet, setup marks them known along with the rest.

Then you do up to four things (your agent tells you when):
1. Extension: a free Gemini API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (Google requires you to be 18 or older), as a file path or pasted into the extension popup.
2. Extension: in Chrome, `chrome://extensions`, turn on **Developer mode**, **Load unpacked**, and pick the folder it names. It's inside a hidden folder: in the picker press Cmd+Shift+G on a Mac (Ctrl+L on Linux), paste the path, press Return, then click **Select**.
3. Extension: pin Spanish Weave from the puzzle-piece menu in Chrome's toolbar, click its icon (a gray "S"), and
   click **Allow all websites** (Chrome asks once; until then it runs only on X and Instagram). If you chose only
   sites you turn on, tick the checkbox next to the site's name in the same popup on each site you want.
4. Codex only: at the next `codex` start, choose **Trust all and continue** for the new hook.

**claude.ai or ChatGPT, with Claude Code installed.** Run `/spanish-weave:export` (or `/spanish-weave:export --chatgpt`)
and paste what it prints (on a Mac, or Linux with wl-copy or xclip, the claude.ai block is also put on your clipboard):
- claude.ai: Settings > "Instructions for Claude" (older layouts call it "What personal preferences should Claude
  consider in responses?"). Replace any older Spanish Weave block.
- ChatGPT: Settings > Personalization: one block in the "Custom instructions" box, the other in "More about you"
  (under About you), each in place of what was there. Each block fits the 1,500-character limit of the Free and Go
  plans (paid plans allow 5,000): with long word lists the "More about you" block names fewer known words, then
  drops sound hints, glosses and the older shaky words, to fit, and export says so if one still doesn't.

Re-export about once a week; Claude Code reminds you when the pasted block is more than a week behind.

**claude.ai or ChatGPT only, nothing to install.** Open [blocks/level-01.md](blocks/level-01.md) and copy its
claude.ai block, or its two ChatGPT blocks, into the same boxes (use the copy button at the top right of each
block). Chat as usual. When the 25 words in it feel easy, paste level 2 instead, and so on through the last level
(46). A level never changes its words: words added to the list later go into new levels after the last one. On a
Pro or Max plan, claude.ai can take one short line instead: see "On claude.ai and the Claude apps" below.

Agents: follow [INSTALL-FOR-AGENTS.md](INSTALL-FOR-AGENTS.md).

**Updates.** `claude plugin marketplace update learning`, then `claude plugin update spanish-weave@learning` (or
`/plugin marketplace update learning` and `/plugin update spanish-weave@learning` in chat). Then restart Claude Code
(the update reaches new sessions only) and rerun `/spanish-weave:setup`, picking the same places as the first time
and keeping the default "Keep the current site choice" for the websites question (a site answer would override a
later "Other sites" choice in the popup): the extension folder, native host and Codex hook run from copies in
`~/.spanish-weave` that only setup refreshes, and it never resets your progress. Last, click the reload arrow on
Spanish Weave in `chrome://extensions`, then reload the tabs you had open: until then they show English (before 0.3.4
they logged "Extension context invalidated" errors instead). `/spanish-weave:status` and `sw.py check` say when those copies are behind
the installed plugin, and `check` also flags a local folder the marketplace was added from that has gone missing.

### On claude.ai and the Claude apps

On a Pro or Max plan, claude.ai and the Claude apps (web, desktop, iPhone and Android) can load Spanish Weave as a
skill, so you paste one line instead of a 6 to 7 KB block, and fixes to the rules arrive as plugin updates:

1. On claude.ai or in the Claude desktop app, open Customize > Plugins > Add > Add marketplace, enter
   `Camcas99/Learning-`, and install **spanish-weave-chat** from it (the other plugin there, spanish-weave, is this
   Claude Code one). Turn on its automatic sync if offered. If you also use this Claude Code plugin, update it to
   0.3.5 or later first: its hook then tells a synced copy of the skill to stay out of Claude Code.
2. In Settings > Capabilities, leave "Code execution and file creation" on (newer apps call it "Create and edit
   files"); skills need it.
3. In Settings > "Instructions for Claude", replace any Spanish Weave block with this line, with your level in place
   of 1. With the Claude Code plugin, `/spanish-weave:export chat` prints it with the level nearest to your words,
   and `/spanish-weave:export chat exact` with your own word list instead.

   ```text
   Spanish Weave level 1. At the start of every conversation, before your first reply, load the spanish-weave skill and follow it for the whole chat. Without the skill, still swap y, pero, entonces, con, sin, muy, también, ahora, porque, para into chat replies (never in code or in health, legal, money, safety or urgent answers) and gloss them in one footer line.
   ```

4. When the words feel easy, type "next level" in a chat: Claude gives you the line for the next level.

The Free plan has no plugins, so keep using the paste-in blocks there. This hasn't been tested on an iPhone yet. And
Claude loads a skill when it chooses to: the line asks for it in every chat, but a chat can still start without it,
and then the rest of the line keeps a few swaps (y, pero, entonces...) going. In Claude Code, the hook's brief carries
the line `spanish-weave-hook: on`, which tells the skill to stay out, so a copy of the chat plugin synced from your
account doesn't double the Spanish; `sw.py check` notes when Claude Code has it. More in
[spanish-weave-chat's README](../spanish-weave-chat/README.md).

### On a phone

- **claude.ai or ChatGPT:** the pasted block (or the one line for the chat plugin above) is an account setting, so it
  works in their phone apps too.
- **Claude Code:** through Remote Control (Pro, Max, Team or Enterprise login, not an API key; on Team or Enterprise
  an Owner must enable it). Run `claude remote-control` on your computer and keep it running (or type
  `/remote-control` in a local Code session in the Claude desktop app), then open the session under Code in the
  Claude app. The computer has to stay on. The hook runs on your computer, so progress is kept. A cloud session
  started from the phone begins on a fresh machine each time, so its word state wouldn't last.
- **A daily quiz on the iPhone** (Mac only, opt-in): `/spanish-weave:phone on` puts today's due words in iCloud Drive >
  Shortcuts > Spanish Weave, and a Shortcut you build on the phone asks them and sends the answers back, where they
  count like `/spanish-weave:quiz` answers. Only those words, their meanings and hints go to iCloud Drive. Steps:
  [IPHONE.md](IPHONE.md). Not yet tested on a real iPhone.
- **Chrome extension:** computers only. Chrome on Android and iPhone doesn't run extensions. Some other Android
  browsers can load Chrome extensions, but Spanish Weave hasn't been tried in one, and without the native host it
  would only use its built-in word lists.

## What it does

- **Claude Code and Codex**: a prompt hook gives the model your stage and word lists every turn, plus a line on how
  much Spanish its last reply in that chat had, judged by the same stage rules. Sentences stay English sentences
  (Stages 3 and 4 add a few short Spanish ones), new words get a one-line gloss with a sound hint at the end, and
  every third reply opens with a recall cue. Never in code, files, commits or anything meant to be shared, and never in scripted
  runs (`claude -p`, `codex exec`).
- **claude.ai and ChatGPT**: the same rules as a pasted preferences block. No hooks there, so the block is static
  until you refresh it.
- **Any website in Chrome** (extension), including X and Instagram: a few English words on the page become Spanish.
  Hover for the meaning, click to flip back, Alt+click to hear it; on a touchscreen, tap for the meaning and tap
  again or press and hold to flip back. On for every site by default, except email, messaging, AI chat and local
  addresses; turn sites off from the toolbar popup, or set it to only the sites you turn on. Swaps are chosen by
  Gemini on your own key, at most 1,000 calls a day (8 passages each), and no one site more than half of them, so a
  page that keeps changing can't use up your key or stop Spanish everywhere. When Google's own daily free quota runs
  out, the popup says when Spanish resumes (just after midnight Pacific) and nothing is asked until then. With a paid
  Claude API key you can pick Claude Haiku 5.5 as the model in the popup instead: it makes fewer wrong swaps and
  Anthropic bills it per use. It never falls back to Gemini, so with Claude picked no page text goes to Google, even
  when a Gemini key is saved.

All of it shares one word list on your machine, so words you see on the web count toward the chat and the other way round.

### In Chrome

- **Swapped words** have a dotted underline and fade in the first time they appear. Hover for a moment and the
  meaning appears (the pause is deliberate: a beat to recall it first); click to flip a word back to English.
- **Touchscreens:** a tap shows the meaning at once (that counts as a peek, like a hover), with a speaker button to
  hear the word. Tap the word again while its meaning shows, or press and hold it, to flip it back to English; a tap
  on an English word turns it back to Spanish. Scrolling or zooming across words never counts.
- **Noun gender:** masculine nouns get a teal underline and feminine nouns a rose one, fainter once you know the
  word, and the gloss says "masc." or "fem." (el agua and el alma are feminine despite "el"). Turn it off with
  "Color noun gender" in the popup.
- **Notes:** false friends show their note after the gloss: `long · "LAHR-goh" · not 'large' (that's grande)`.
- **Hear it:** Alt+click (Option+click on a Mac) or Alt+Enter says the word aloud, preferring a Latin American
  voice and one installed on your computer, without flipping it. Chrome's own "Google" voices are online: when one
  is used, the word goes to Google. "Say words aloud when the meaning shows" in the popup speaks every gloss. Chrome
  may keep a page silent until you've clicked on it once.
- **Instagram:** instagram.com is supported out of the box, like X: captions, comments and profile bios. It hasn't
  been checked on the live site yet: the markup is modeled on instagram.com's structure, which changes often, so if
  Instagram gets no Spanish, the selectors
  in `extension/src/page.js` (the `SITES` table) are the place to look. Direct messages (instagram.com/direct, and
  X messages) are never read. The Instagram app itself can't be changed, and Chrome on phones doesn't run extensions
  (see "On a phone" above).

## Commands (Claude Code)

| Command | What it does |
|---|---|
| `/spanish-weave:status` | Stage, word counts, the words you're learning, and whether setup's copies are behind |
| `/spanish-weave:known <word>` | Mark a word known (no more glosses); accents optional, so `tambien` works, and listed phrases too |
| `/spanish-weave:learn <word>` | Put a word back into the learning set |
| `/spanish-weave:stage [1-4\|auto]` | Pin your stage, or let it follow your known words (no value: show it) |
| `/spanish-weave:pause` / `resume` | Stop or restart Spanish in chat and on websites |
| `/spanish-weave:export [chatgpt\|chat [exact]] [log-day]` | Paste-ready block for claude.ai or ChatGPT, or the one line for the chat plugin (dashes optional) |
| `/spanish-weave:quiz [N]` | Spaced-repetition quiz on the words that are due; the answers are saved at the end, with one approval |
| `/spanish-weave:placement` | 2-minute placement test that sets your starting words; one approval to save |
| `/spanish-weave:anki [all]` | Your words as an Anki import file |
| `/spanish-weave:output [on\|off]` | "Your turn" lines that invite you to write a little Spanish (no argument: is it on?) |
| `/spanish-weave:phone [on\|off\|sync\|status]` | Daily quiz on the iPhone through iCloud Drive, Mac only (see [IPHONE.md](IPHONE.md)) |

You type these yourself: Claude can't start them for you, except status. The same commands work from a terminal as
`python3 ~/.spanish-weave/app/scripts/sw.py <command>`.

## Reading the sound hints

Every word comes with a respelling for an English reader, like `también = also, "tahm-BYEN"`.

| In a hint | Means |
|---|---|
| CAPITALS | the stressed syllable: `ah-OH-rah` (ahora). One-syllable words have none, except in a phrase when a written accent marks the stress: por qué = `por KEH` (porque is `POR-keh`) |
| `ah eh ee oh oo` | the five Spanish vowels, always short and clean: casa = `KAH-sah` |
| `eye ay oy ow` | vowel pairs said as one sound: hay = `eye`, ley = `lay`, hoy = `oy`, restaurante = `rres-tow-RAHN-teh` |
| `rr` | a rolled r: perro = `PEH-rroh`; also any r at the start of a word: rojo = `RROH-hoh` |
| `b` | both b and v, which sound the same in Spanish: vez = `bes`, nuevo = `NWEH-boh` |
| `h` | j, and g before e or i (a breathy h): trabajo = `trah-BAH-hoh`, gente = `HEN-teh`. The written h is silent: hola = `OH-lah` |
| `s` | z, and c before e or i (Latin American): gracias = `GRAH-syahs`, vez = `bes` |
| `y` | ll: llamar = `yah-MAHR` |
| `ny` | ñ: mañana = `mah-NYAH-nah` |

Adverbs ending in -mente keep their own stress plus "MEN": rápidamente = `RRAH-pee-dah-MEN-teh`.

The hints are generated by rules, not written by hand, because Spanish spelling maps to sound almost one to one.
[`scripts/hints.py`](scripts/hints.py) splits a word into syllables, finds the stressed one (a written accent wins;
otherwise words ending in a vowel, n or s stress the second-to-last syllable, and the rest stress the last), then
respells each syllable. Try it: `python3 scripts/hints.py "la computadora"`.

## Quiz yourself (spaced repetition)

`/spanish-weave:quiz` (or `sw.py quiz` in a terminal) asks about the words that are due, one at a time. In Claude
Code, the answers are saved together at the end, so Claude Code asks at most once before saving them.

- A new word is first quizzed the day after it arrives, once you've had a chance to read it.
- Words ask for the meaning first ("What does "pero" mean?"). After two right answers in a row it asks for the
  Spanish ("How do you say "but" in Spanish?"): producing a word is harder than recognizing it, and builds a
  stronger memory. A miss goes back to asking for the meaning.
- Each right answer moves the word up a box, and each box waits longer before the next review: 1, 3, 7, 14, 30, 60,
  then 120 days.
- A wrong answer on a learning word sends it back to the first box (tomorrow) and starts its three clean days over.
  A known word you can't say in Spanish drops two boxes; one you don't even recognize turns shaky, so it shows up
  more in chat until it's known again.
- At the end, the quiz asks each missed word once more, after you've seen its answer. That second try is practice
  and isn't recorded, but it means every session ends on a successful recall.
- A right answer counts as an exposure day, so quizzing moves a learning word toward known faster.
- Known words come back too: a week after they graduate, two weeks after you mark them known, and words set by
  setup or the placement test get a first check spread over four weeks. Every other "Recall:" cue in chat picks a
  known word that is due.
- Missing accents, ñ typed as n, capitals and a wrong el/la don't count against you; the answer line shows the
  right spelling and article, and says when the accent makes it a different word (si is "if", sí is "yes"). When
  you answer with another Spanish word for the same meaning (recordar for acordarse), you decide if it counts.
- One exception for el/la: when a noun's ending doesn't give its gender away (el problema, el día, la mano, la
  clase), the wrong article still counts as recalled, but the word stays in its box and comes back at the same gap,
  because that gender has to be remembered. On la casa, whose -a says feminine, it's only a slip.
- Answering the same word again on the same day replaces the earlier answer, so a wrong call can be corrected
  (unless something else, like `known` or a flip, changed the word in between; then the new answer goes on top).

## Placement test

`/spanish-weave:placement` (or `sw.py placement`) shows 44 items: 32 real words, 8 from each of four frequency bands
(ranks 1-100, 101-250, 251-500, 501 and up), mixed with 12 made-up Spanish-looking words. You pick the ones you know.
Picking a made-up word shows some answers are guesses, so each band's score is corrected for guessing: (real words
picked - made-up words picked) / (1 - made-up words picked), as rates, with one extra made-up "yes" and "no" assumed
so a lucky run can't read as no guessing at all. Bands count in order: once a band is mostly unknown, rarer bands add
nothing, so a few look-alikes such as el repositorio can't mark the most common words known. Picking 3 or more
made-up words means too much guessing, and nothing is marked. The estimate marks that many of the most common words
known, like setup's `--known-top`, and those words come up in the quiz for a first check over the next four weeks;
any you miss go back to learning. Setup offers it as "Not sure: take a 2-minute placement test".

## False friends

Words that look like English but mean something else carry a note: `el éxito = success — not 'exit' (that's la
salida)`. Notes show in chat glosses, `/spanish-weave:status`, the quiz, the Chrome tooltip and the Anki export.
They live in [`data/notes.csv`](data/notes.csv): 48 of them. Most are false friends, including 11 classic ones added
to the list for this reason (embarazada, la librería, realizar, asistir, actualmente, recordar, sensible, el
pariente, la fábrica, el colegio, la lectura). The rest mark words that are easy to use in the wrong sense: es is
what something is, while a state or place takes está; "not X but Y" is sino, not pero; question words like dónde
only ask questions.

## Anki

`/spanish-weave:anki` writes `~/spanish-weave-anki.txt` (or `sw.py anki --out FILE`; `all` or `--all` for the whole
list instead of the words you've met). It replaces only an earlier Spanish Weave export there, never another file or
a symlink. In Anki 2.1.55 or later, File > Import reads the deck (Spanish Weave, created if
it doesn't exist), note type (Basic and reversed card) and tags from the file, so Anki quizzes both directions on
its own spaced-repetition schedule (FSRS). If Anki's menus are in another language, pick the "Basic (and reversed
card)" note type in the import window.

## Output practice

Off by default. With `/spanish-weave:output on`, every fifth reply ends with an optional "Your turn" line that asks
you to write a few words of Spanish with a learning word. Answer it, and the next reply opens with a one-line
correction before answering your message.

## The learning science behind it

| Method | Where it is in Spanish Weave | Research |
|---|---|---|
| Comprehensible input | About 6% Spanish at Stage 1 keeps a reply easy to follow | Krashen 1985; Hu & Nation 2000 |
| Frequency-ordered vocabulary | The word list starts with the words you meet most | Nation 2013 |
| Retrieval practice | The quiz and the "Recall:" cue | Roediger & Karpicke 2006 |
| Spaced repetition | Quiz boxes with growing gaps; known words come back | Leitner 1972; Cepeda et al. 2006 |
| Successive relearning | Missed quiz words are asked once more at the end | Rawson & Dunlosky 2011 |
| Productive recall | The quiz asks for the Spanish once you recognize a word | Slamecka & Graf 1978 |
| Vocabulary-size placement | Yes/No test with made-up words, corrected for guessing | Meara & Buxton 1987; Izura et al. 2014 |
| Contrastive notes | False-friend notes | Cross-linguistic influence (Odlin 1989) |
| Input enhancement | Gender colors and the fade-in make form noticeable | Sharwood Smith 1993; Schmidt 1990 |
| Hearing the word | Alt+click speech next to the respelled hint | Paivio 1986 (dual coding) |
| Pushed output | "Your turn" lines | Swain 1985 |
| Corrective feedback | Quiz answers, "Your turn" corrections | Lyster & Ranta 1997 |

Practice testing and spacing are the two techniques Dunlosky et al. (2013) rate "high utility" for learning, which
is why the quiz combines them. Paul Nation's "four strands" give the overall shape: reading woven text is
meaning-focused input, "Your turn" is meaning-focused output, the quiz and notes are language-focused learning, and
easy rereading ("story") builds fluency.

## Latin American Spanish

The word list and prompts use Latin American Spanish, the Spanish of Mexico, Central and South America and the US:
`la computadora` (not ordenador), `el carro`, `el celular`, `manejar` (to drive), `agregar` (to add), `el boleto`,
`apurarse`, `ahorita`, and *ustedes* for "you all" (never *vosotros*). Hints use Latin American pronunciation, where
z and soft c sound like s.

## How words advance

Words come from [`data/lexicon.csv`](data/lexicon.csv): about 1,100 Spanish words and short phrases in
frequency/usefulness order (connectors and adverbs first, then everyday phrases, nouns, adjectives and verbs, and
coding words at the end), each with a gloss and a sound hint.

- **Exposure day**: a day you saw the word in a Claude Code or Codex reply, or on a web page.
- **Learning**: at most 20 words at a time, shaky ones included; at most 5 new words a day, and none while 5 or more
  are shaky.
- **Learning -> known**: 3 exposure days, with no flip, `learn` or peek on the last 3.
- **Flip or `learn` -> shaky**: clicking a Spanish word on a web page back to English (on a touchscreen, a second tap
  or a press and hold), `/spanish-weave:learn`, or a known word you don't recognize in the quiz. A **peek** (hovering
  until the meaning shows, or a first tap) holds back a learning word; a known word peeked on 2 days within a week,
  both since it became known, turns shaky. **Shaky -> known** after 7 days with no flip, peek or quiz miss, once
  you've really seen the word again since the last one (days counted by `log-chat-day` don't count; solo, mayor,
  sensible, tan, resolver and todos, which chat can't count, need only the week).
- **Late browser events**: the extension sends flips, peeks and sightings in batches, and holds them while the
  native host can't be reached; a flip or peek dated before a word's last change never undoes that change.
- **Stage** follows your known words: 1 to start, 2 at 40 known, 3 at 150, 4 at 400.
  `/spanish-weave:stage N` pins it; `/spanish-weave:stage auto` unpins.

| Stage | Spanish in a reply | Per sentence | Shape |
|---|---|---|---|
| 1 | about 6%, never over 10% | at most 2 | English sentences with swapped words |
| 2 | about 12%, never over 20% | at most 4 | same |
| 3 | about 25%, never over 35% | at most 4 | plus one short Spanish sentence in five |
| 4 | about 40%, never over 55% | at most 4 | plus two in five |

From about 150 known words, the brief and exports stop listing them all: they name the stretch of the word list
you know ("the first 400 words of the Spanish Weave list"; the claude.ai block adds the words it starts with and the
40 newest) plus the exceptions, so with a thousand known words the brief stays under 4 KB and the claude.ai block is
about 6.5 KB (each ChatGPT field still fits its 1,500 characters). The list is in learning order, not a general
frequency rank, so it never says "the most common Spanish words".

**Words in the right sense.** The brief and the pasted blocks carry short guards for the words that are easiest to
swap in the wrong sense, each added once its word is in use: es and soy only for what something is ("it's ready"
stays English, since es listo means "is clever"), esto and eso never before a noun, question words only in
questions, sino for "not X but Y", también and entonces never for "too" or "so" before an adjective, bien never
for the filler "Well,", desde never for "since" meaning because, el tiempo never for "this time" (vez), para never
for a duration, no Spanish preposition before a clause, and a listed noun brings its own article (never "the el")
with any Spanish adjective next to it agreeing (la idea nueva). The extension's prompt has the same guards; the
ChatGPT block, kept under the 1,500-character limit of the Free and Go plans, carries the most common ones.

**Spanish that is also English.** Counting a word in a chat reply means telling the Spanish use from the English
one. Unaccented nouns need a Spanish article in front ("el error" counts, "the error" doesn't); `solo`, `mayor`,
`sensible`, `tan`, `resolver` and `todos` (English TODOs) are never counted from chat, since English uses them with
other meanings (the quiz, the extension or `known` can still move them); and a few words skip their English
uses: TODO, "the algo", `sin(x)`, ES modules, "en route", "x and y" and `O(n)`. A phrase is counted before the words
inside it, so "es decir" is not also a sighting of decir.

**Chats that can't be scanned** (claude.ai, ChatGPT) don't count toward exposure. If you mostly read Spanish there,
`sw.py log-chat-day` (or `export --log-day`) counts today as exposure for your learning words. It's off by default
because it's a guess: it never makes a word known on its own; a word still needs one real sighting.

**Chats, not scripts.** The hook weaves in every chat surface (terminal, desktop, IDE, Remote Control,
claude.ai/code, the Codex TUI) and stays silent only in one-shot scripted runs: `claude -p` without
`--sdk-url`/`--input-format stream-json`, Agent SDK scripts (`CLAUDE_CODE_ENTRYPOINT` `sdk-ts` or `sdk-py`) and
`codex exec`. Sessions nobody reads as they run get no Spanish either: subagents, scheduled tasks, and sessions
another session starts in the desktop app (their first prompt is recognized, and from then on Claude Code's
transcript shows no prompt you typed). Their replies count as no exposure: a chat counts from the first prompt you
type in it, so a child session you step into counts from there, and gets Spanish from your second prompt on. A task
notification or a message from another session in your own chat still gets Spanish but isn't a turn, so it brings no
recall cue or "Your turn" line. Telling later turns apart needs Claude Code 2.1.281 or later, which records where
every prompt came from; older versions weave and count more of them. A child session forked with the whole
conversation copies your typed prompts, so it still weaves: `/spanish-weave:pause` covers that, or
`SPANISH_WEAVE_OFF=1` in its environment; that variable switches it off anywhere else too, and
`SPANISH_WEAVE_FORCE=1` weaves in a script. Health, medication, legal, money, safety, emergency and driving topics
get no Spanish at all.

The extension's prompts are built for levels 1-2; at Stage 3-4 it uses the level 2 rules.

## Privacy

What Spanish Weave keeps, and what it sends:

- **Stored only on your machine**, in `~/.spanish-weave` (or `SPANISH_WEAVE_HOME`, which must be a new or empty
  folder, or an earlier Spanish Weave one, that you own; setup refuses any other, and the chat hook and commands
  write nothing into it): `state.json` (each word's status and dates, quiz answers and settings), `exposure.json`
  (how often and on which days each word showed up in chat, the transcript paths it has read, whether you typed in
  each, and short hashes of recent replies), `sessions.json` (chat ids, turn counts, recall words used and whether
  you typed in the chat) and, if setup stored it,
  `gemini_key` (mode 600). The hook reads your local Claude Code and Codex transcripts to count exposure and never
  sends them anywhere.
- **Sent with each prompt** to Anthropic through Claude Code, and to OpenAI through Codex: your word lists and stage
  (the brief the hook adds), and the Spanish share of the last reply.
- **Sent to Google's Gemini API with each page**, with your key: the readable text of the page, and your word lists
  and stage. With a free-tier key, Google may use that text to improve its products, human reviewers may read it,
  and Google asks that no personal or sensitive information be sent; in the EEA, UK and Switzerland the paid-tier
  data terms apply.
- **Sent to Anthropic's API with each page instead**, only if you pick Claude Haiku in the popup and paste a Claude
  key there: the same page text, word lists and stage, under Anthropic's API terms.
- **Put in iCloud Drive**, only if you turn on the iPhone quiz (`/spanish-weave:phone on`): today's due words with their
  meanings, sound hints and your stage, in iCloud Drive > Shortcuts > Spanish Weave; your phone's answers come back
  there as right or wrong per word, never what you typed. Apple can read iCloud Drive unless Advanced Data Protection
  is on.
- **Pasted by you** into claude.ai or ChatGPT: the export blocks, with your word lists (the claude.ai block with the
  day each learning word arrived), stage and sync time.
- **Kept in Chrome's storage** by the extension: its settings and site choices, your Gemini key (and Claude key, if you
  pasted one), a cache of
  chosen swaps with a few words of page text around each, and today's count of model calls for each site. Removing the extension deletes them; deleting
  `~/.spanish-weave` doesn't.

Which sites: by default the extension runs on every site you allow, except email, messaging and AI chat sites
(Gmail, Outlook, iCloud Mail, Yahoo Mail, Proton Mail, WhatsApp Web, Messenger, Telegram, Slack, Discord, Teams,
claude.ai, ChatGPT, Gemini, Copilot and others), Google Docs, Drive and Calendar, password managers, big banks and
payment, brokerage and credit sites, health portals, government sites (.gov, .mil, .gob.mx and similar), any site
whose name contains bank, creditunion, mychart or patient, and local or intranet addresses (localhost, private IPs,
names without a dot, and .local, .lan, .corp, .internal and similar), which start off. A listed site covers its
subdomains, and a page whose title is about money, health, legal matters or safety gets no swaps and sends nothing
to Gemini. Instagram direct messages
(instagram.com/direct) and X messages are never read, and on any site pages under paths like /messages, /inbox,
/chat, /account or /settings are skipped. Banking and health sites stay on unless you turn them off: passages about
balances, cards, insurance or appointments are skipped, but other text on those pages isn't, so turn them off in the
popup, or choose "Only sites I turn on". Setup's site choice and the popup's "Other sites" choice are the same
setting: whichever you made last wins. A pause stops new page text going to Gemini within 2 minutes; Spanish already
on an open page goes when you reload it after that, when you open the popup, or within 10 minutes. Resuming and setup
reruns reach Chrome within 10 minutes, or as soon as you open the popup. If the extension has never reached the
native host, sites stay off until you turn them on.

The extension talks to the plugin through a Chrome native messaging host that only this extension's ID may call. If
setup stored your Gemini key, the host hands it only to the extension's background worker, never to the pages it runs
on. The extension's ID is public (it comes from the key in `extension/manifest.json`), so only load Spanish Weave
from the folder setup makes from this repo: a lookalike unpacked extension with the same key would get the same ID,
and with it your Gemini key.

## Layout

```
.claude-plugin/   plugin.json (the marketplace that lists it is at the root of the Learning- repo)
hooks/            UserPromptSubmit hook -> scripts/weave.py
commands/         /spanish-weave:* slash commands
scripts/          swlib.py (state, rules, transcript scan), weave.py (hook), sw.py (CLI, setup),
                  sw_host.py (native host), export.py (claude.ai / ChatGPT blocks), make_blocks.py (blocks/),
                  hints.py (sound hints), placement.py (placement test)
data/lexicon.csv  ranked words: es, en, sound hint, since (the version that added a later word)
data/notes.csv    usage notes (false friends) by word
blocks/           ready-made claude.ai / ChatGPT blocks, one per level (generated)
extension/        Chrome MV3 extension (no build step, no runtime dependencies)
tests/            python tests, live model checks, extension end-to-end check
../spanish-weave-chat/  the skills-only plugin for claude.ai and the Claude apps (generated, except its README)
```

## Develop

```sh
python3 -m unittest discover -s tests            # hook, rules, hints, quiz, placement, notes, exports, host, setup, docs
python3 scripts/hints.py --check                 # every hint in the word list matches the rules
python3 scripts/make_blocks.py                   # regenerate blocks/ and ../spanish-weave-chat after changing the rules, lexicon or version
python3 scripts/bundle_content.py                # rebuild extension/src/content.bundle.js after changing content.js or its imports
cd extension && bun install && bun test           # extension (happy-dom)
python3 tests/model_eval.py --out /tmp/sw-eval    # live check via claude -p, isolated from your own config
python3 tests/model_eval.py --paste level-01 --stages 1 --out /tmp/sw-eval   # simulate claude.ai with a block
npm i playwright && npx playwright install chromium        # once, for the extension end-to-end check below
python3 scripts/sw.py setup --user-data-dir /tmp/sw-profile [--gemini-key-file KEY]   # registers the host for that profile
PROFILE=/tmp/sw-profile node tests/extension_e2e.mjs       # Playwright Chromium: fake X, Instagram and article pages + real Gemini
```

When you change anything the plugin runs (scripts, commands, data, the extension), raise `version` in
`.claude-plugin/plugin.json`, `extension/manifest.json` and `extension/package.json`, all three the same: installed
copies only update when the version changes. Then run `python3 scripts/make_blocks.py`, which gives the chat plugin
(`../spanish-weave-chat`) the same version; `make_blocks.py --check` fails while the two differ. To test with your
own state folder, point `SPANISH_WEAVE_HOME` at a new or empty folder you own (setup refuses one that holds other
things, and the hook and commands write nothing there).

To add a word, add a row `es,en,,VERSION` to `data/lexicon.csv` in the rank where it belongs, with the next version
in the since column (`quizás,perhaps,,0.3.4`). Run `python3 scripts/hints.py --fill` to generate its hint, then
`python3 scripts/make_blocks.py`. The plugin queues the word at its rank; the paste-in levels put each version's words
in new levels after the last one, so a level someone already pasted never changes.

## License

MIT. Copyright (c) 2026 Jackie Oliver (French Weave, the original) and Camcas99 (this Spanish adaptation); see
[LICENSE](LICENSE).
