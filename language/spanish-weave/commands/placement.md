---
description: Take a 2-minute Spanish placement test (a Yes/No vocabulary test) to set your starting words
allowed-tools: Bash(python3:*)
---
The test:
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" placement --items`

Show the user the intro line and the numbered list above exactly as printed, in one code block, and ask them to
reply with the numbers of the words they know (they could say what it means), skipping any they're unsure of. Never
say which words are made up. When they reply, run
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" placement --answers "<their numbers>" --apply` and relay the result in
two plain-English lines: the estimate and the stage it set. No Spanish other than the list.
