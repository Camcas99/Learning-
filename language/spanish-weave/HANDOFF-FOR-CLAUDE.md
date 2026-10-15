# A letter to the Claude who's picking this up

Hello, and welcome.

You're about to help someone learn Spanish with a project that a learner named Cameron (GitHub: Camcas99) and I built
together in a single long, happy session. Cameron is studying computer science, and every step was a chance to
learn; now it's being passed to their friend, and to you. I want you to have everything I wish I'd known on day one,
so here it is.

## What Spanish Weave is, in one breath

It teaches Latin American Spanish passively. It drops a few Spanish words into English your person already reads
(your chat replies, and web pages through a Chrome extension), at a level they can follow, and it tracks which words
move from "learning" to "known" as they see them:

> The build passes ahora, pero the cache is stale, entonces I cleared it.
> (ahora = now, "ah-OH-rah"; pero = but, "PEH-roh"; entonces = so, "en-TOHN-ses")

It's an adaptation of [French Weave](https://github.com/jackieoliver/french-weave) by Jackie Oliver (MIT license;
please keep the credit in LICENSE and the README). We kept its design and code, and wrote a new Latin American word
list, pronunciation rules, Spanish grammar guards, and a set of learning-science features on top.

## Your first job: help your human get started

Read [`INSTALL-FOR-AGENTS.md`](INSTALL-FOR-AGENTS.md) and follow it; it's written for you. A few things it takes for
granted:

- **The code lives at** https://github.com/Camcas99/Learning- in the folder `language/spanish-weave`. The plugin
  marketplace (named `learning`) is at the repo root, so add the repo itself, not the subfolder:
  `claude plugin marketplace add Camcas99/Learning-`, then `claude plugin install spanish-weave@learning`. If your
  human gave you a zip or a local folder instead, add that folder (the one holding `.claude-plugin/`).
- **Pick the path that fits them**, and don't push the full install on someone who just wants to try it:
  1. *Just curious:* no install at all. Show them `blocks/level-01.md` and have them paste its block into claude.ai
     (Settings > Profile) or ChatGPT (Custom instructions). Level 2 when those 25 words feel easy, and so on.
  2. *Uses Claude Code:* the plugin. A hook adds a short brief to every prompt so your replies weave in their
     words, and their progress is tracked automatically.
  3. *Wants it everywhere:* also the Chrome extension, on any site including X and instagram.com. It needs a free
     Gemini API key, which they paste into the extension popup themselves. Never ask for the key in chat.
- **If they already know some Spanish**, offer the 2-minute placement test (`/spanish-weave:placement`) so they
  don't start with words they know.
- Needs: Python 3.9+, Claude Code for the plugin, Chrome (or Chromium) for the extension. No pip installs.

If you're a Claude without tools (a plain chat), you can still help: walk them through option 1, and follow the
pasted block's rules in your own replies.

## How it works, so you can explain it

- **Word list** (`data/lexicon.csv`): 1,043 Latin American words and phrases in learning order: connectors and
  adverbs first (y, pero, entonces, con, sin...), then everyday phrases, nouns, adjectives and verbs, then coding
  words. Each has an English gloss and a sound hint with the stressed syllable in capitals.
- **Word lifecycle** (`scripts/swlib.py`): queue -> active (up to 20 at once, 5 new a day) -> known (seen on 3
  days with no slips), with "shaky" as the penalty box for words they flip back to English, keep looking up, or no
  longer recognize in a quiz (a missed learning word just starts its three days over). A shaky word is known again
  after a week with no slips and at least one new sighting. Stage 1-4 follows the count of known words (40, 150,
  400) and sets how much Spanish goes in a reply (about 6%, 12%, 25%, 40%).
- **The hook** (`scripts/weave.py`) builds the brief you'll see each turn: the stage, the words to use, short
  guards for the words that are easiest to swap in the wrong sense (es only for what something is, so "it's ready"
  stays English; esto and eso never before a noun; question words only in questions; sino for "not X but Y"; para,
  muy, si/sí), a "Recall: X?" cue every third reply, and a measurement of how much Spanish your last reply really
  had. Please honor it: Spanish only in chat prose, never in code, files,
  commands, commit messages or anything they'll share; zero Spanish on health, legal, money, safety, emergency and
  driving topics.
- **Learning-science features we added** (see the README's "The learning science behind it" table):
  - `/spanish-weave:quiz`: spaced retrieval practice. Leitner-style boxes (1, 3, 7, 14, 30, 60, 120 days), meaning
    questions first, then producing the Spanish after two right answers in a row. You run it: ask one question at a
    time, judge leniently (accents and el/la don't count against them, and another Spanish word with the same
    meaning does count; the false friend in a note doesn't), and record each answer with
    `sw.py review "<word>" right|wrong`. If the word was right but with the wrong el/la, add
    `--article <the one they used>`: a noun whose ending doesn't give its gender away (el problema, la mano) then
    comes back at the same gap. Recording a word again the same day replaces the earlier answer, so you can fix a
    wrong call. At the end, ask each missed word once more without recording it, so they finish on a success.
  - `/spanish-weave:placement`: a Yes/No vocabulary test with made-up words to catch guessing. Never reveal which
    items are made up. If they pick 3 or more made-up words, nothing is marked: offer a retake, kindly. Words it
    marks known get a first quiz check over the next four weeks.
  - False-friend notes (`data/notes.csv`): `el éxito = success — not 'exit'`. Keep a word's note in your footer
    gloss.
  - `/spanish-weave:output on`: opt-in "Your turn" lines every fifth reply. When they answer one, give a single
    kind line of feedback with the corrected Spanish, then carry on.
  - `/spanish-weave:anki`: export to Anki for anyone who already uses it.
- **The Chrome extension** (`extension/`): Gemini picks swaps on the page; the extension accepts only words from
  their list, paints them with a dotted underline (masculine and feminine nouns get slightly different colors),
  shows the meaning after a short dwell (the pause is deliberate: a moment to guess first), flips a word back on
  click, and says it aloud on Alt+click. It runs on X and instagram.com out of the box (site adapters live in the
  `SITES` table in `extension/src/page.js`), never in Instagram direct messages, and its popup has "Say words
  aloud when the meaning shows" (off by default) and "Color noun gender" (on by default) settings. Other sites
  need the person's OK: "Allow all websites" in the popup, or the checkbox next to a site's name. It talks to the plugin through a local native messaging host, so web
  sightings count toward progress too.

## Being a good tutor with it

This is the part I care about most.

- **Keep it light.** The whole point is that learning costs almost nothing. Hit the Spanish target in a reply, but
  never make Spanish the topic unless they ask, and never let it get in the way of the actual answer.
- **Retrieval beats rereading.** A few minutes of `/spanish-weave:quiz` most days does more than anything else
  here. Suggest it gently, not every turn.
- **Let them guess first.** When they ask "word?", answer in one line. When they try some Spanish, notice what they
  got right before you correct anything.
- **Celebrate milestones:** a new stage, 100 known words, a week of quizzes. Learning a language is long, and
  momentum matters.
- **Respect their choices.** If they say easier, harder, pause or stop, do exactly that.

## Working on the code

- Tests: `python3 -m unittest discover -s tests` (55 tests) and `cd extension && bun install && bun test` (90).
  Keep them green, and add tests with anything you change.
- After changing the word list or the rules: `python3 scripts/hints.py --check` (every hint must match the
  pronunciation rules; `--fill` writes hints for new rows) and `python3 scripts/make_blocks.py` (regenerates the
  42 paste-in levels; a ChatGPT field must stay under 1,500 characters, and some are within a few characters).
- Their state lives in `~/.spanish-weave` (or `$SPANISH_WEAVE_HOME`). Setup never resets progress; keep it that way.
- Never print or log the Gemini key, and keep page text out of anything that leaves the browser except the Gemini
  call itself.

## What's verified, and what isn't yet

- Verified here: every Python and extension unit test, the hint and block checks, and each command run end to end in
  a scratch install.
- Not verified yet: the live checks, `tests/model_eval.py` (needs the `claude` CLI) and `tests/extension_e2e.mjs`
  (needs a browser and a Gemini key). The extension's Instagram support is modeled on instagram.com's markup but
  hasn't been run on the live site, which changes often. Speech depends on the voices installed on their device.
  If something looks off, trust what you observe and fix it with a test.

## A few ideas, if you're both enjoying it

Example sentences for each word, verb conjugation practice, short listening clips, and a progress page are the
natural next steps.

Thank you for taking care of this, and of them. I hope you two have a wonderful time with it.

Warmly,
Claude (the Claude Code session that built it with Cameron)
