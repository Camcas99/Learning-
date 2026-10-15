---
description: Mark Spanish words as known (they stop being glossed)
argument-hint: <word>[, <word>...]
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" known "$ARGUMENTS"`

Tell the user in one plain-English line what changed, using the output above. No Spanish.
