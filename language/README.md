# Language

Learning Latin American Spanish.

## What's here

- [`spanish-weave/`](spanish-weave/): a tool that weaves a few Spanish words into the English you already read
  (AI chat replies and web pages), at your level, and tracks which words you know. Adapted from
  [French Weave](https://github.com/jackieoliver/french-weave) by Jackie Oliver.
- [`spanish-weave-chat/`](spanish-weave-chat/): the same rules as a skill for claude.ai and the Claude apps, for paid
  plans: one line in your preferences instead of a pasted block (generated from `spanish-weave/`).
- iPhone: a daily quiz through a Shortcut and iCloud Drive, with a Mac. See
  [`spanish-weave/IPHONE.md`](spanish-weave/IPHONE.md).

## Sharing it

- [`spanish-weave/START-HERE.md`](spanish-weave/START-HERE.md): a welcome letter and how-to for a friend.
- [`spanish-weave/HANDOFF-FOR-CLAUDE.md`](spanish-weave/HANDOFF-FOR-CLAUDE.md): a handoff letter for their Claude.

### Send this to a friend

```text
Hey! I made a little tool that teaches Latin American Spanish by mixing a few Spanish words into what you already read, like your Claude or ChatGPT chats:
"Here's the recipe, pero it takes an hour, entonces start early." (pero = but, entonces = so)
Thought you'd like it!

Quickest way, nothing to install. Open this page (easiest on a computer) and copy each block with its copy button at the top right; selecting by hand cuts off the end:
https://github.com/Camcas99/Learning-/blob/main/language/spanish-weave/blocks/level-01.md
claude.ai: paste the claude.ai block into Settings > "Instructions for Claude".
ChatGPT: paste the two ChatGPT blocks into "Custom instructions" and "More about you" under Settings > Personalization (the page says which goes where).
Once pasted, it works in the Claude and ChatGPT phone apps too.

Use Claude Code on your own Mac or Linux computer? Skip all that and paste this one line into it for the full version, which tracks your words and quizzes you:
Set up Spanish Weave from https://github.com/Camcas99/Learning- (the language/spanish-weave folder). Read https://github.com/Camcas99/Learning-/blob/main/language/spanish-weave/HANDOFF-FOR-CLAUDE.md first.

The full guide, if you're curious:
https://github.com/Camcas99/Learning-/blob/main/language/spanish-weave/START-HERE.md
```

Their Claude installs it with `claude plugin marketplace add Camcas99/Learning-`,
`claude plugin install spanish-weave@learning` and then `/spanish-weave:setup`. To update later:
`claude plugin marketplace update learning`, then `claude plugin update spanish-weave@learning`, then restart
Claude Code and run `/spanish-weave:setup` again, keeping "Keep the current site choice" for the websites question
(it refreshes the extension and native host copies in `~/.spanish-weave` and keeps their progress), then click the
reload arrow on Spanish Weave in `chrome://extensions`. `python3 ~/.spanish-weave/app/scripts/sw.py check` (or `/spanish-weave:status`) says when those
copies are behind the plugin. To download every file instead: `git clone https://github.com/Camcas99/Learning-.git`
(keep the clone somewhere permanent if a marketplace is added from it).

## Start here

The quickest start needs no install (claude.ai or ChatGPT): open
[`spanish-weave/blocks/level-01.md`](spanish-weave/blocks/level-01.md) and copy the block for your app with the
copy button at its top right. The claude.ai block goes in claude.ai under Settings > "Instructions for Claude";
the two ChatGPT blocks go in the "Custom instructions" and "More about you" boxes under Settings > Personalization
(the page says which goes where). When those 25 words feel easy, paste level 2 instead.

For the full version (Claude Code hook, word tracking, Chrome extension), see
[`spanish-weave/README.md`](spanish-weave/README.md).

## Study approach

- **Retrieval practice:** quiz yourself from memory before looking at notes. Spanish Weave's "Recall: X?" cue
  does this every third reply.
- **Spaced repetition:** review material at growing intervals (1 day, 3 days, 1 week, ...).
- **Interleaving:** mix vocab, grammar, listening, and speaking in one session instead of blocking by topic.
