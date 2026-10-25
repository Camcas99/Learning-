# Spanish Weave for chat

[Spanish Weave](../spanish-weave/) as a skill, for claude.ai and the Claude apps (web, desktop chat, iPhone and
Android). Claude swaps a few Latin American Spanish words into its English replies, at the level you set, and glosses
the new ones in a footer line:

> The build passes ahora, pero the cache is stale, entonces I cleared it.
> (ahora = now, "ah-OH-rah"; pero = but, "PEH-roh"; entonces = so, "en-TOHN-ses")

Instead of pasting a 6 to 7 KB block into your settings, you paste one line, and fixes to the rules reach you as
plugin updates.

## Install (Pro or Max plan)

Plugins are for paid plans. On the free plan, keep using the paste-in blocks in
[`../spanish-weave/blocks/`](../spanish-weave/blocks/level-01.md).

1. On claude.ai or in the Claude desktop app: Customize > Plugins > Add > Add marketplace, enter
   `Camcas99/Learning-`, then Add. Turn on syncing for it if offered, so updates arrive by themselves.
2. In its list, add **spanish-weave-chat**. (The other one, spanish-weave, is the Claude Code plugin for your
   computer.)
3. Settings > Capabilities: leave "Code execution and file creation" on (it is on by default); skills need it.
4. Settings > "Instructions for Claude": delete any old Spanish Weave block and paste this one line, with your level
   in place of 1:

   ```text
   Spanish Weave level 1. At the start of every conversation, before your first reply, load the spanish-weave skill and follow it for the whole chat. Without the skill, still swap y, pero, entonces, con, sin, muy, también, ahora, porque, para into chat replies (never in code or in health, legal, money, safety or urgent answers) and gloss them in one footer line.
   ```

   With the Claude Code plugin on your Mac, `/spanish-weave:export chat` prints this line with the level nearest to
   your words, and `/spanish-weave:export chat exact` your own word list instead.
5. Start a new chat. When the words feel easy, type "next level": Claude gives you the new line to paste.

Plugins belong to your account rather than a device, so once this is set up it should reach the Claude phone apps
too (see the first point below).

## Good to know

- **Not yet tested on an iPhone.** The setup above follows Anthropic's docs; a test run on the phone is still to come.
- **Claude decides when to load a skill.** The line asks for it in every chat, but a chat can still start without it.
  The rest of the line keeps a few swaps going even then. If a chat has no Spanish, type / and pick spanish-weave.
- **No Spanish in incognito chats**, which can't use skills, or where an organization turned skills off.
- **In Claude Code**, the Spanish Weave hook's brief carries the line `spanish-weave-hook: on`, and this skill stands
  down when it sees it, so a reply never gets two word lists.

## Privacy

Text only: no scripts, no hooks, no network calls. Your level lives in your claude.ai preferences, and nothing about
your words leaves the chat.

## For maintainers

Everything here except this README is written by `python3 scripts/make_blocks.py` in `../spanish-weave/`, from the
same rules and word list as the paste-in blocks, and its version always matches the spanish-weave plugin's.
`make_blocks.py --check` fails when anything here is out of date or the versions differ.

MIT license; see [LICENSE](LICENSE). Adapted from [French Weave](https://github.com/jackieoliver/french-weave) by
Jackie Oliver.
