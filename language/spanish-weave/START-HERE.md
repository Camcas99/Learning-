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

- **You start small.** With Claude Code: about 5 words (y = and, pero = but, entonces = so, con = with,
  sin = without), then up to 5 new ones a day, never more than 20 at once. With a pasted block: 25 words per
  level, and you paste the next level yourself when they feel easy.
- **In Claude Code, words move on by themselves.** A word becomes "known" once you've seen it on 3 different days
  without needing to look it up. Words you look up a lot, or forget after you knew them, become "shaky" and show up
  more until they stick. (A pasted block can't see what you've read, so nothing moves until you paste the next
  level.)
- **The Spanish grows with you.** Stage 1 is about 1 word in 16; at 40 known words you reach Stage 2, at 150 Stage
  3, where short, easy Spanish sentences start to appear in chat, and at 400 Stage 4. With pasted blocks the stage
  comes with the level: Stage 2 from level 3, Stage 3 from level 7, Stage 4 from level 17.
- **It never gets in the way.** No Spanish in code, files or anything you'd share, and none at all on health,
  legal, money, safety, emergency or driving topics.

Why it works: you learn words best from text you can mostly understand, with a little that's new, and every time
you have to pull a meaning out of memory (instead of looking it up), it sticks better.

## Pick how to start

**1. Try it in 2 minutes, no install (claude.ai or ChatGPT).**
Open [`blocks/level-01.md`](blocks/level-01.md) and copy the block for your app with the copy button at its top
right (the lines run off the screen, so don't select them by hand). The claude.ai block goes in claude.ai under
Settings > "Instructions for Claude" (on a computer, click your initials at the bottom left to open Settings; older
layouts call the box "What personal preferences should Claude consider in responses?"). ChatGPT gets its own two
shorter blocks, for the "Custom instructions" and "More about you" boxes under Settings > Personalization; the page
says which goes where. Chat as usual. When those 25 words feel easy, paste level 2 instead.

**2. The full version, with Claude Code (recommended).**
This one needs Claude Code on your own Mac or Linux computer (on Windows, use option 1 for now). Claude Code comes
with a paid Claude plan (Pro or Max, or a work Team or Enterprise account); the free plan doesn't include it, so on
the free plan use option 1. Don't have it yet? Install it with https://code.claude.com/docs/en/quickstart. Option 3
and "Everywhere, step by step" below also run through Claude Code.
Tell Claude Code: *"Set up Spanish Weave from https://github.com/Camcas99/Learning- (the language/spanish-weave
folder). Read https://github.com/Camcas99/Learning-/blob/main/language/spanish-weave/HANDOFF-FOR-CLAUDE.md first."*
It asks a few questions and does the rest. This version tracks your words for you, quizzes you, and can place you
at your level.

**3. Everywhere you read, with the Chrome extension.**
During setup, say yes to the Chrome extension. Setup then asks whether it should run on every site or only on sites
you turn on: the extension sends the readable text of each page it runs on to Google's Gemini (see Privacy below),
so pick "Only sites I turn on" if you'd rather choose site by site. You'll need a free Gemini API key from
https://aistudio.google.com/apikey (Google requires you to be 18 or older, and school or supervised Google accounts
are often blocked), which you paste into the extension's popup yourself (never into a chat). Then in Chrome:
`chrome://extensions` > Developer mode > Load unpacked > the folder Claude names > pin Spanish Weave from the
puzzle-piece menu > click its icon > Allow all websites. Step 3 of "Everywhere, step by step" below walks through
it, including how to reach the folder, which is hidden. It works on X, articles, anything with English text, and
should work on Instagram's website too (see below).

**Everywhere, step by step** (about 15 minutes, once; Mac or Linux):
1. On your computer, in Claude Code, type these one at a time: `/plugin marketplace add Camcas99/Learning-`,
   `/plugin install spanish-weave@learning`, `/reload-plugins`, then `/spanish-weave:setup`. Say yes to the Chrome
   extension. (On a Mac, if a window asks to install the command line developer tools, click Install, wait for it
   to finish, then run the command again.)
2. Get a free Gemini key at https://aistudio.google.com/apikey (you need to be 18+ and signed in with a personal
   Google account).
3. In Chrome: `chrome://extensions` > Developer mode (top right) > Load unpacked. The folder setup names is inside a
   hidden folder (`.spanish-weave`), so you won't see it by browsing: press Cmd+Shift+G on a Mac (Ctrl+L on Linux),
   paste the full path setup gave you, press Return, then click Select. New extensions start hidden, so click the
   puzzle-piece icon in Chrome's toolbar and pin Spanish Weave. Then click its icon (a gray "S"), paste the key,
   and click Allow all websites (if you chose only sites you turn on, tick the box next to the site's name on each
   site you want instead).
4. For claude.ai and ChatGPT, on the web and in their phone apps: run `/spanish-weave:export` and
   `/spanish-weave:export --chatgpt`, and paste each block where it says. Do it again about once a week; Claude Code
   reminds you.
5. For Claude Code on your phone (paid Claude plan needed): run `claude remote-control` on your computer and leave
   it running, then in the Claude app on your phone tap Code and open that session. See "On your phone and
   Instagram" below.

The only places it can't reach are web pages on a phone and the Instagram app (see "On your phone and Instagram" below).

Already know some Spanish? Pick "Not sure: take a 2-minute placement test" during setup, or run
`/spanish-weave:placement` later. You'll mark the words you know from a list; a few are made up, so only mark ones
you could actually translate (pick three made-up ones and it asks you to try again). Claude Code asks you once before
saving the result. The words it marks known still come up in your quizzes over the next few weeks, so any you don't
really know go back to learning.

## The best way to use it

1. **Just read.** Don't stop to study every Spanish word. Let the sentence tell you what it means.
2. **Guess before you look.** In Chrome the meaning shows only after a short pause on purpose: try to recall it
   first. On a touchscreen a tap shows it at once, so guess before you tap; tap again or press and hold to flip the
   word back to English. In chat, the meanings are in the footer at the end.
3. **Answer the "Recall: ...?" question in your head** before you read the answer at the end of the reply. It
   shows up every few replies, and it's the most valuable 3 seconds of the day.
4. **Quiz for 3 to 5 minutes most days** with `/spanish-weave:quiz`. Words you get right come back after longer and
   longer gaps (3 days, a week, two weeks...). Missed words come back soon, and the quiz asks them once more at the
   end, so you always finish on a right answer. Your answers are saved together at the end, so Claude Code asks you
   once to save them. That spacing is what turns "I've seen it" into "I know it".
5. **Say words out loud.** The hints show the stressed syllable in capitals: `también` = `tahm-BYEN`. In Chrome,
   Alt+click (Option+click on a Mac) a Spanish word to hear it (on a touchscreen, tap it and then the speaker in its
   meaning), or turn on "Say words aloud when the meaning shows" in the extension's popup. Underline colors tell you
   a noun's gender: teal for masculine (el), rose for feminine (la), a little fainter once you know the word.
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
| CAPITALS | the stressed syllable: ahora = `ah-OH-rah`; in a phrase, an accented short word too: por qué = `por KEH` |
| `ah eh ee oh oo` | the five Spanish vowels, short and clean |
| `rr` | a rolled r: perro = `PEH-rroh` |
| `b` | both b and v (they sound the same): vez = `bes` |
| `h` | a breathy h for j, and for g before e/i: trabajo = `trah-BAH-hoh`. A written h is silent: hola = `OH-lah` |
| `s` | z, and c before e/i: gracias = `GRAH-syahs` |
| `y` / `ny` | ll and ñ: llamar = `yah-MAHR`, mañana = `mah-NYAH-nah` |

## Commands (in Claude Code)

You type these yourself: Claude can't start them for you (except status).

| Type this | To |
|---|---|
| `/spanish-weave:status` | see your stage, words, and what's due for review |
| `/spanish-weave:quiz` | do a short spaced-repetition quiz (it asks once to save your answers) |
| `/spanish-weave:placement` | take the placement test (it asks once to save the result) |
| `/spanish-weave:known <word>` / `learn <word>` | mark a word known, or bring it back |
| `/spanish-weave:stage 1-4` / `stage auto` | set the amount of Spanish yourself, or let it follow your progress |
| `/spanish-weave:output on` / `off` | turn "Your turn" practice on or off |
| `/spanish-weave:pause` / `resume` | take a break from Spanish everywhere |
| `/spanish-weave:export` | get an up-to-date block for claude.ai or ChatGPT (refresh it weekly) |
| `/spanish-weave:export chat` | get the one line for the claude.ai chat plugin (see "On claude.ai and the Claude apps") |
| `/spanish-weave:anki` | export your words to Anki, if you use it |

With the pasted block in claude.ai or ChatGPT, you can type a word with a question mark ("pero?") for a quick
translation, "quiz" for a three-word quiz, "story" (claude.ai only) to retell the last answer as a short story at
your level, or "easier" / "harder" for that chat. In Claude Code, just ask ("what does pero mean?") or use the
commands above.

## On claude.ai and the Claude apps

Have a Pro or Max plan? Then claude.ai and the Claude apps (including the iPhone and Android apps) can use Spanish
Weave as a skill. You paste one short line instead of the long block, and fixes to the rules reach you on their own:

1. On claude.ai or in the Claude desktop app, open Customize > Plugins > Add > Add marketplace, type
   `Camcas99/Learning-`, and click Add. From its list, install **spanish-weave-chat** (not spanish-weave: that one
   is for Claude Code on a computer). If there's a switch to sync it automatically, turn it on.
2. In Settings > "Instructions for Claude", delete any Spanish Weave block and paste this line, with your level in
   place of 1:

   ```text
   Spanish Weave level 1. At the start of every conversation, before your first reply, load the spanish-weave skill and follow it for the whole chat. Without the skill, still swap y, pero, entonces, con, sin, muy, también, ahora, porque, para into chat replies (never in code or in health, legal, money, safety or urgent answers) and gloss them in one footer line.
   ```

3. Start a new chat. When the words feel easy, type "next level" and Claude gives you the line for the next level.

With Claude Code, `/spanish-weave:export chat` prints the line with the level closest to the words you know.

Two honest caveats. It hasn't been tested on an iPhone yet. And Claude decides for itself when to load a skill: the
line asks for it in every chat, but a chat can still start without it, and then the rest of the line still gets you
a few Spanish words (y, pero, entonces...). On the free plan there are no plugins, so keep using the paste-in blocks.

## On your phone and Instagram

- **claude.ai or ChatGPT on your phone: yes.** The pasted block is saved to your account, so it works in the Claude
  and ChatGPT phone apps too. Paste it on the website (easiest on a computer) and chat as usual; there's nothing to
  paste again on your phone.
- **Claude Code from your phone: yes, through your computer** (needs a paid Claude plan you sign in to, not an API
  key; on a work Team or Enterprise plan an admin may have to turn it on). Run `claude remote-control` in a terminal
  on your computer and leave it running, or in the Claude desktop app type `/remote-control` in a local Code
  session. Then in the Claude app on your phone, tap Code and open that session (from the terminal you can also
  press the spacebar and scan the QR code). Your computer has to stay on. It runs on your computer, so your words
  and progress are all there. A Claude Code session started in the cloud from your phone begins on a fresh computer
  every time, so it can't keep your progress.
- **A daily quiz on your iPhone: yes, with a Mac.** Run `/spanish-weave:phone on` in Claude Code on your Mac, then build
  a short Shortcut on your iPhone that asks your due words each day; your answers count on the Mac just like
  `/spanish-weave:quiz`. Only today's quiz words go to iCloud Drive. The steps are in [IPHONE.md](IPHONE.md); it hasn't
  been tried on a real iPhone yet.
- **The Chrome extension on your phone: no.** Chrome on phones doesn't run extensions, so web pages only get
  Spanish words on a computer.
- **Instagram's website** (instagram.com in Chrome on a computer): should work, but it hasn't been tried on the real
  site yet, and Instagram changes its pages often. Captions, comments and bios get the same treatment as everything
  else. Your direct messages are never touched. If Instagram gets no Spanish while other sites do, ask your Claude to
  fix it (the handoff note says where to look).
- **The Instagram app**: no. Phone apps can't be changed by other software; that's how iPhone and Android keep
  apps safe.

## Updates

Now and then there's a new version with fixes. In Claude Code, type these one at a time:
`/plugin marketplace update learning`, then `/plugin update spanish-weave@learning`. Then restart Claude Code, run
`/spanish-weave:setup` again (it keeps your progress): pick the same places as the first time, and for the websites
question keep the default, "Keep the current site choice", so a choice you made later in the extension's popup
stays. Then in Chrome open `chrome://extensions` and click the reload arrow on Spanish Weave, and reload the tabs you
had open (until then they show English).
`/spanish-weave:status` tells you when the copies setup made are behind the plugin, which means it's time to rerun
setup. With only a pasted block, copy your level's block again now and then to pick up fixes.

## Privacy

What's kept where, and what gets sent:

- **Only on your computer**, in a `.spanish-weave` folder: your word list with each word's status and dates, which
  words you've seen in chats (counted from your Claude Code and Codex history, which is never sent anywhere), and how
  many messages each chat has had.
- **To Claude (Anthropic), and to OpenAI if you use Codex:** your current word lists and stage go along with each
  message you send, so the reply can use them.
- **To Google's Gemini, with your own key:** the Chrome extension sends the readable text of each page it runs on,
  with your word lists and stage. With a free key, Google may use that text to improve its products and AI, and
  human reviewers may read it; Google asks free users not to send personal or sensitive information. (In the EEA,
  the UK and Switzerland, Google treats free keys like paid ones.)
- **To Anthropic instead, only if you choose it:** if you pick Claude Haiku as the model in the extension popup and
  paste a paid Claude API key there, that same page text goes to Anthropic's API instead of Gemini. With Claude picked
  nothing goes to Gemini, even if a Gemini key is saved; without a Claude key the extension waits for one.
- **Into claude.ai or ChatGPT:** the blocks you paste there, with your word lists.
- **In Chrome:** the extension keeps its settings, your key and a small cache of swapped words with a few words of
  page text around each, in Chrome's own storage. Removing the extension deletes them.

Email, messaging and AI chat sites (Gmail, Outlook, iCloud Mail, Yahoo, Proton, WhatsApp Web, Messenger, Slack,
Discord, Teams, claude.ai, ChatGPT, Gemini, Copilot and others), Google Docs and Drive, password managers, big banks,
payment and brokerage sites, health portals, government sites, and local or work-network addresses start off, and so
does any site whose name contains bank, creditunion, mychart or patient. Pages whose title is about money, health,
legal matters or safety get no Spanish either. Instagram and X direct messages are never read. Smaller banks and
other private sites can still be on in the default every-site mode, so turn those off from the toolbar, or set
"Other sites" in the extension's popup to "Only sites I turn on" (setup asks you this too; whichever you chose last
wins). A pause stops new page text going to Gemini within 2 minutes; Spanish
already on an open page goes when you reload it after that, when you open the popup, or within 10 minutes. Resuming,
or a setup rerun, reaches Chrome within 10 minutes, or as soon as you open the popup.

Only load the extension folder that setup gives you, never a copy someone sends you: the extension's ID is public,
and a lookalike with the same ID would be handed your Gemini key.

## If something's off

- **No Spanish in Claude's replies:** open a new Claude Code session (the plugin loads at start), and check
  `/spanish-weave:status` isn't paused.
- **No Spanish on websites:** click the Spanish Weave icon. Is it on, is there a Gemini key, and is the site allowed?
- **Spanish in automated work:** scheduled tasks, subagents and sessions another session starts get none (with
  Claude Code 2.1.281 or later). If some still do, such as a session forked with the whole conversation,
  `/spanish-weave:pause` while it runs, and `/spanish-weave:resume` after.
- **AI Studio won't make a key** (or sends you to an "available regions" page): Google only gives keys to accounts
  it knows are 18 or older. Verify your age in your Google Account settings, or use a personal account instead of a
  school or Family Link one.
- **Too much or too little:** in Claude Code, `/spanish-weave:stage 1` to `4` sets the amount yourself (1 is the
  lightest), and `/spanish-weave:stage auto` lets it follow your progress again. Still too much at Stage 1?
  `/spanish-weave:pause` takes a break. The Chrome extension follows that stage unless you pick a level under
  "Force level" in its popup. In claude.ai or ChatGPT, type "easier" or "harder" (it lasts for that chat).
- **Anything else:** ask your Claude to read
  https://github.com/Camcas99/Learning-/blob/main/language/spanish-weave/HANDOFF-FOR-CLAUDE.md and help.

Have fun with it. ¡Buena suerte! (good luck, "BWEH-nah SWEHR-teh")

— Cameron

*Spanish Weave is adapted from [French Weave](https://github.com/jackieoliver/french-weave) by Jackie Oliver, MIT
license.*
