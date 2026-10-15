---
description: Export your Spanish Weave words as an Anki import file
argument-hint: "[--all]"
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" anki $ARGUMENTS --out "$HOME/spanish-weave-anki.txt"`

Tell the user in two plain-English lines where the file is and how to import it: in Anki, File > Import, then pick
the file; the deck (Spanish Weave), note type (Basic and reversed card) and tags come from the file, so Anki quizzes
both directions on its own spaced-repetition schedule. Mention that `--all` exports the whole word list instead of
only the words they have met. No Spanish.
