---
description: Set up Spanish Weave (asks a few questions, then installs the word state, extension folder and native host)
argument-hint: [--gemini-key-file <path>]
allowed-tools: Bash(python3:*), AskUserQuestion
---
Setup plan (a dry run; nothing changed yet; don't show it to the user):
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" setup --dry-run`

If the plan shows `platform` win32, or it failed because `python3` was not found, don't run setup. Tell them the
Claude Code and Chrome parts need a Mac or Linux computer for now, and point them to the claude.ai and ChatGPT
blocks at https://github.com/Camcas99/Learning-/blob/main/language/spanish-weave/blocks/level-01.md instead.

Write no Spanish in anything you say during setup. Ask these four questions in ONE AskUserQuestion call, the
default option first with "(default)" in its label. Leave Codex CLI out of question 2 if `codex_cli` above is null.

1. "How much Spanish do you know already?" None (default) / A few basic words / I can read simple Spanish / Not
   sure: take a 2-minute placement test.
2. "Where should Spanish show up?" (multi-select) Claude Code (always on with the plugin) / Codex CLI (default when
   installed) / The Chrome extension on websites (default) / A claude.ai or ChatGPT preferences block to paste.
3. "If you picked the Chrome extension, which websites?" Every site; turn any off from the toolbar (default) /
   Only sites I turn on.
4. "If you picked the Chrome extension, your Gemini API key (free at https://aistudio.google.com/apikey, 18+)?" Paste it
   into the extension's popup at the end (default) / A file that contains it: type its path under Other. Never
   paste the key itself here.

Skipped questions get the default. Never ask for the key in chat, and never print it. If the answer to question 4
looks like a key rather than a file path (for example it starts with `AIza`), don't run setup with it, don't repeat
it, and tell them to paste it into the extension popup instead. Then run, with the `source` folder from the plan
above:

`python3 <source>/scripts/sw.py setup $ARGUMENTS` plus:
- question 1: `--known-top 0`, `--known-top 40` or `--known-top 150` (placement test: `--known-top 0`, then the test).
  The prompt hook has usually created the word state already, so the count can come out up to 5 short and the
  stage one lower until those words graduate; report the stage setup prints.
- Codex CLI picked: `--codex`
- Chrome extension picked: `--sites all` or `--sites ask`, and `--gemini-key-file <path>` if they gave a file

Relay the human steps from the output to the user as a short numbered list, in plain English, leaving out the
Chrome steps if they didn't pick the extension. Keep the hidden-folder tip (Cmd+Shift+G or Ctrl+L) and the pin
step. If setup failed, say why and how to fix it.

If they chose the placement test, run it after setup: `python3 <source>/scripts/sw.py placement --items`, show the
intro line and numbered list exactly as printed in one code block, ask for the numbers of the words they know (never
say which are made up), then run `python3 <source>/scripts/sw.py placement --answers "<their numbers>" --apply` and
relay the estimate and stage in plain English.

If they picked the preferences block, run `python3 <source>/scripts/sw.py export` and `... export --chatgpt` after
the placement test (if any), so the block includes the words the test marked known, and show each block exactly as
printed, in its own code block, with where to paste it.
