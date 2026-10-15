---
description: Quiz yourself on the Spanish Weave words that are due (spaced repetition)
argument-hint: "[how many words, default 5]"
allowed-tools: Bash(python3:*)
---
Quiz plan, questions with their answers (never show an answer before the user replies):
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" quiz --plan $ARGUMENTS`

Run a short quiz in plain English from the plan above. Ask one question at a time, as written, and wait for the
user's reply before going on. Judge leniently: missing accents, a missing or different el/la, capitals, any listed
meaning and close synonyms of it count as right. After each reply, say in one short line whether it was right and
give the answer from the plan (Spanish, meaning, sound hint, and the note after the — if there is one), then record
it with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" review "<the Spanish from the plan>" right` (or `wrong`). If
the user wants to stop, stop. At the end, give the score in one line. If the plan says there is nothing to review,
say so in one line. Write no other Spanish during the quiz.
