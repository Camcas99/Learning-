# Spanish Weave

Learn Latin American Spanish passively from the English you already read. Spanish Weave swaps a few Spanish words
into AI chat replies and the web pages you read, at your level, and moves words from learning to known as you see
them.

> The build passes ahora, pero the cache is stale, entonces I cleared it.
> (ahora = now, "ah-OH-rah"; pero = but, "PEH-roh"; entonces = so, "en-TOHN-ses")

New here? Read [START-HERE.md](START-HERE.md). Claude sessions picking this up: read
[HANDOFF-FOR-CLAUDE.md](HANDOFF-FOR-CLAUDE.md).

Adapted from [French Weave](https://github.com/jackieoliver/french-weave) by Jackie Oliver (MIT license): same
design and code, with a new Spanish word list, sound hints, grammar rules and prompts.

## Set up

**Claude Code or Codex.** Tell your agent:

```
Set up Spanish Weave from https://github.com/Camcas99/Learning- (the language/spanish-weave folder)
```

Or install the plugin yourself in Claude Code (2.1.275 or later; on older versions, run
`/plugin marketplace add Camcas99/Learning-` first, then `/plugin install spanish-weave@learning`), then run
`/spanish-weave:setup`:

```
/plugin install spanish-weave --marketplace Camcas99/Learning-
```

Setup first asks a few questions in one go: how much Spanish you know already (none, a few basic words, or simple
Spanish, which starts you at Stage 1, 2 or 3), where Spanish should show up (Claude Code, Codex, the Chrome
extension, a claude.ai or ChatGPT block), whether the extension runs on every site or only ones you turn on, and
how you'll give it a Gemini key. Skip any question to take the default. Rerunning setup (`/spanish-weave:setup`)
asks again and never resets your progress.

Then you do up to four things (your agent tells you when):
1. Extension: a free Gemini API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey), as a file path or pasted into the extension popup.
2. Extension: in Chrome, `chrome://extensions`, turn on **Developer mode**, **Load unpacked**, pick the folder it names.
3. Extension: click the Spanish Weave toolbar icon and **Allow all websites** (Chrome asks once; until then it runs
   only on X and Instagram). If you chose only sites you turn on, tick the checkbox next to the site's name in the
   same popup on each site you want.
4. Codex only: at the next `codex` start, choose **Trust all and continue** for the new hook.

**claude.ai or ChatGPT, with Claude Code installed.** Run `/spanish-weave:export` (or `/spanish-weave:export --chatgpt`)
and paste the block it prints:
- claude.ai: Settings > Profile > "What personal preferences should Claude consider in responses?"
- ChatGPT: Settings > Personalization > Custom instructions (two boxes, each block fits 1,500 characters).

Re-export about once a week; Claude Code reminds you when the pasted block is more than a week behind.

**claude.ai or ChatGPT only, nothing to install.** Open [blocks/level-01.md](blocks/level-01.md), paste its block
into the same settings box, and chat as usual. When the 25 words in it feel easy, paste level 2 instead, and so on
through level 42.

Agents: follow [INSTALL-FOR-AGENTS.md](INSTALL-FOR-AGENTS.md).

## What it does

- **Claude Code and Codex**: a prompt hook gives the model your stage and word lists every turn. Every sentence
  stays an English sentence, new words get a one-line gloss with a sound hint at the end, and every third reply
  opens with a recall cue. Never in code, files, commits or anything meant to be shared, and never in scripted
  runs (`claude -p`, `codex exec`).
- **claude.ai and ChatGPT**: the same rules as a pasted preferences block. No hooks there, so the block is static
  until you refresh it.
- **Any website in Chrome** (extension), including X and Instagram: a few English words on the page become Spanish.
  Hover for the meaning, click to flip back, Alt+click to hear it. On for every site by default; turn sites off from the toolbar popup, or set it to only the
  sites you turn on. Swaps are chosen by Gemini on your own key.

All of it shares one word list on your machine, so words you see on the web count toward the chat and the other way round.

### In Chrome

- **Swapped words** have a dotted underline and fade in the first time they appear. Hover for a moment and the
  meaning appears (the pause is deliberate: a beat to recall it first); click to flip a word back to English.
- **Noun gender:** masculine nouns get a teal underline and feminine nouns a rose one, fainter once you know the
  word, and the gloss says "masc." or "fem." (el agua and el alma are feminine despite "el"). Turn it off with
  "Color noun gender" in the popup.
- **Notes:** false friends show their note after the gloss: `long · "LAHR-goh" · not 'large' (that's grande)`.
- **Hear it:** Alt+click (Option+click on a Mac) or Alt+Enter says the word aloud, preferring a Latin American
  voice, without flipping it. "Say words aloud when the meaning shows" in the popup speaks every gloss. Chrome may
  keep a page silent until you've clicked on it once.
- **Instagram:** instagram.com works out of the box, like X: captions, comments and profile bios. The markup is
  modeled on instagram.com's structure, which changes often, so if Instagram stops getting Spanish, the selectors
  in `extension/src/page.js` (the `SITES` table) are the place to look. Direct messages are never read, like
  webmail. The Instagram app itself can't be changed; on a phone, use instagram.com in a browser that supports
  extensions.

## Commands (Claude Code)

| Command | What it does |
|---|---|
| `/spanish-weave:status` | Stage, word counts, the words you're learning |
| `/spanish-weave:known <word>` | Mark a word known (no more glosses); accents optional, so `tambien` works |
| `/spanish-weave:learn <word>` | Put a word back into the learning set |
| `/spanish-weave:stage 1-4\|auto` | Pin your stage, or let it follow your known words |
| `/spanish-weave:pause` / `resume` | Stop or restart Spanish in chat and on websites |
| `/spanish-weave:export [--chatgpt] [--log-day]` | Paste-ready block for claude.ai or ChatGPT |
| `/spanish-weave:quiz [N]` | Spaced-repetition quiz on the words that are due |
| `/spanish-weave:placement` | 2-minute placement test that sets your starting words |
| `/spanish-weave:anki [--all]` | Your words as an Anki import file |
| `/spanish-weave:output [on\|off]` | "Your turn" lines that invite you to write a little Spanish (no argument: is it on?) |

The same commands work from a terminal as `python3 ~/.spanish-weave/app/scripts/sw.py <command>`.

## Reading the sound hints

Every word comes with a respelling for an English reader, like `también = also, "tahm-BYEN"`.

| In a hint | Means |
|---|---|
| CAPITALS | the stressed syllable: `ah-OH-rah` (ahora). One-syllable words have none |
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

`/spanish-weave:quiz` (or `sw.py quiz` in a terminal) asks about the words that are due, one at a time.

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
- Answering the same word again on the same day replaces the earlier answer, so a wrong call can be corrected.

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

`/spanish-weave:anki` writes `~/spanish-weave-anki.txt` (or `sw.py anki --out FILE`; `--all` for the whole list
instead of the words you've met). In Anki 2.1.55 or later, File > Import reads the deck (Spanish Weave, created if
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

Words come from [`data/lexicon.csv`](data/lexicon.csv): about 1,000 Spanish words and short phrases in
frequency/usefulness order (connectors and adverbs first, then everyday phrases, nouns, adjectives and verbs, and
coding words at the end), each with a gloss and a sound hint.

- **Exposure day**: a day you saw the word in a Claude Code or Codex reply, or on a web page.
- **Learning (active)**: up to 20 at a time; at most 5 new words a day, and none while 5 or more are shaky.
- **Learning -> known**: 3 exposure days, with no flip, `learn` or peek on the last 3.
- **Flip or `learn` -> shaky**: clicking a Spanish word on a web page back to English, `/spanish-weave:learn`, or a
  known word you don't recognize in the quiz. A **peek** (hovering until the meaning shows) holds back a learning
  word; a known word peeked on 2 days within a week turns shaky. **Shaky -> known** after 7 days with no flip, peek
  or quiz miss, once you've seen the word again since the last one (solo, mayor and sensible, which chat can't
  count, need only the week).
- **Stage** follows your known words: 1 to start, 2 at 40 known, 3 at 150, 4 at 400.
  `/spanish-weave:stage N` pins it; `/spanish-weave:stage auto` unpins.

| Stage | Spanish in a reply | Per sentence | Shape |
|---|---|---|---|
| 1 | about 6%, never over 10% | at most 2 | English sentences with swapped words |
| 2 | about 12%, never over 20% | at most 4 | same |
| 3 | about 25%, never over 35% | at most 4 | plus one short Spanish sentence in five |
| 4 | about 40%, never over 55% | at most 4 | plus two in five |

Once you know 150 words, the brief and exports stop listing them: they name the band ("about the 400 most common
Spanish words") plus the exceptions, so a thousand known words still fit in about 3.5 KB.

**Words in the right sense.** The brief and the pasted blocks carry short guards for the words that are easiest to
swap in the wrong sense, each added once its word is in use: es and soy only for what something is ("it's ready"
stays English, since es listo means "is clever"), esto and eso never before a noun, question words only in
questions, sino for "not X but Y", también and entonces never for "too" or "so" before an adjective, para
never for a duration, and a listed noun brings its own article (never "the el"). The extension's prompt has the same
guards.

**Spanish that is also English.** Counting a word in a chat reply means telling the Spanish use from the English
one. Unaccented nouns need a Spanish article in front ("el error" counts, "the error" doesn't); `solo`, `mayor` and
`sensible` are never counted from chat, since English uses them with other meanings (the quiz, the extension or
`known` can still move them); and a few words skip their English
uses: TODO, "the algo", `sin(x)`, ES modules, "en route", "x and y" and `O(n)`.

**Chats that can't be scanned** (claude.ai, ChatGPT) don't count toward exposure. If you mostly read Spanish there,
`sw.py log-chat-day` (or `export --log-day`) counts today as exposure for your learning words. It's off by default
because it's a guess: it never makes a word known on its own; a word still needs one real sighting.

**Only in conversations you read.** The hook weaves in every chat surface (terminal, desktop, IDE, Remote Control,
claude.ai/code, the Codex TUI) and stays silent only in one-shot scripted runs: `claude -p` without
`--sdk-url`/`--input-format stream-json`, Agent SDK scripts (`CLAUDE_CODE_ENTRYPOINT` `sdk-ts` or `sdk-py`) and
`codex exec`. Set `SPANISH_WEAVE_OFF=1` to switch it off for anything else, or `SPANISH_WEAVE_FORCE=1` to weave in a
script. Health, medication, legal, money, safety, emergency and driving topics get no Spanish at all.

The extension's prompts are built for levels 1-2; at Stage 3-4 it uses the level 2 rules.

## Privacy

Everything stays on your machine in `~/.spanish-weave` (override with `SPANISH_WEAVE_HOME`). The hook reads your
local Claude Code and Codex transcripts to count exposure and never sends them anywhere. By default the extension
runs on every site you allow, and readable page text from those sites goes to Google's Gemini API with your key
(free-tier keys allow Google to train on prompts); webmail, AI chat sites and local addresses start off, and
Instagram direct messages are never read. It talks
to the plugin through a Chrome native messaging host that only this extension's ID may call. If setup stored
your Gemini key, it sits in `~/.spanish-weave/gemini_key` (mode 600) and is handed only to the extension's
background worker, never to the pages it runs on.

## Layout

```
.claude-plugin/   plugin.json (the marketplace that lists it is at the root of the Learning- repo)
hooks/            UserPromptSubmit hook -> scripts/weave.py
commands/         /spanish-weave:* slash commands
scripts/          swlib.py (state, rules, transcript scan), weave.py (hook), sw.py (CLI, setup),
                  sw_host.py (native host), export.py (claude.ai / ChatGPT blocks), make_blocks.py (blocks/),
                  hints.py (sound hints), placement.py (placement test)
data/lexicon.csv  ranked words: es, en, sound hint
data/notes.csv    usage notes (false friends) by word
blocks/           ready-made claude.ai / ChatGPT blocks, one per level (generated)
extension/        Chrome MV3 extension (no build step, no runtime dependencies)
tests/            python tests, live model checks, extension end-to-end check
```

## Develop

```sh
python3 -m unittest discover -s tests            # hook, rules, hints, quiz, placement, notes, exports, host, setup
python3 scripts/hints.py --check                 # every hint in the word list matches the rules
python3 scripts/make_blocks.py                   # regenerate blocks/ after changing the rules or lexicon
cd extension && bun install && bun test           # extension (happy-dom)
python3 tests/model_eval.py --out /tmp/sw-eval    # live check via claude -p, isolated from your own config
python3 tests/model_eval.py --paste level-01 --stages 1 --out /tmp/sw-eval   # simulate claude.ai with a block
node tests/extension_e2e.mjs                      # after setup: Playwright Chromium + fake X and article pages + real Gemini
```

To add a word, append a row `es,en,` to `data/lexicon.csv` (in the rank where it belongs), run
`python3 scripts/hints.py --fill` to generate its hint, then `python3 scripts/make_blocks.py`.

## License

MIT. Copyright (c) 2026 Jackie Oliver (French Weave, the original) and Camcas99 (this Spanish adaptation); see
[LICENSE](LICENSE).
