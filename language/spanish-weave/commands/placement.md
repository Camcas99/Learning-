---
description: Take a 2-minute Spanish placement test (a Yes/No vocabulary test) to set your starting words
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" placement:*)
disable-model-invocation: true
---
The test:
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" placement --items`

Show the user the intro line and the numbered list above exactly as printed, in one code block, and ask them to
reply with the numbers of the words they know (they could say what it means), skipping any they're unsure of. Say
that Claude Code may ask once before saving the result. Never say which words are made up. When they reply, turn
any en or em dash into a hyphen, keep only the digits, commas, spaces and hyphens, and run
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" placement --answers '<what you kept>' --apply` (ranges like 3-7 are
fine). Relay the result in two plain-English lines: the estimate and the stage it set. If it says nothing was marked
because too many made-up words were picked, say so kindly and offer to run the test again. If the command is
declined, say that nothing was marked. No Spanish other than the list.
