# Language

Learning Latin American Spanish.

## What's here

- [`spanish-weave/`](spanish-weave/): a tool that weaves a few Spanish words into the English you already read
  (AI chat replies and web pages), at your level, and tracks which words you know. Adapted from
  [French Weave](https://github.com/jackieoliver/french-weave) by Jackie Oliver.

## Sharing it

- [`spanish-weave/START-HERE.md`](spanish-weave/START-HERE.md): a welcome letter and how-to for a friend.
- [`spanish-weave/HANDOFF-FOR-CLAUDE.md`](spanish-weave/HANDOFF-FOR-CLAUDE.md): a handoff letter for their Claude.

### Send this to a friend

```text
I made a tool that teaches Latin American Spanish by mixing a few Spanish words into what you already read.
Start here: https://github.com/Camcas99/Learning-/blob/main/language/spanish-weave/START-HERE.md

If you use Claude Code, tell it:
Set up Spanish Weave from https://github.com/Camcas99/Learning- (the language/spanish-weave folder). Read language/spanish-weave/HANDOFF-FOR-CLAUDE.md first.

No Claude Code? Paste the block from this page into claude.ai (Settings > Profile) or ChatGPT (Custom instructions). It works on your phone too:
https://github.com/Camcas99/Learning-/blob/main/language/spanish-weave/blocks/level-01.md
```

Their Claude installs it with `claude plugin marketplace add Camcas99/Learning-` and
`claude plugin install spanish-weave@learning`, and later gets updates with `claude plugin marketplace update
learning` and `claude plugin update spanish-weave@learning`. To download every file instead:
`git clone https://github.com/Camcas99/Learning-.git`.

## Start here

The quickest start needs no install: open
[`spanish-weave/blocks/level-01.md`](spanish-weave/blocks/level-01.md), copy the claude.ai block, and paste it into
claude.ai under Settings > Profile > personal preferences. When those 25 words feel easy, paste level 2.

For the full version (Claude Code hook, word tracking, Chrome extension), see
[`spanish-weave/README.md`](spanish-weave/README.md).

## Study approach

- **Retrieval practice:** quiz yourself from memory before looking at notes. Spanish Weave's "Recall: X?" cue
  does this every third reply.
- **Spaced repetition:** review material at growing intervals (1 day, 3 days, 1 week, ...).
- **Interleaving:** mix vocab, grammar, listening, and speaking in one session instead of blocking by topic.
