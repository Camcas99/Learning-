---
description: Pin your Spanish Weave stage (1-4) or set it back to auto
argument-hint: 1|2|3|4|auto
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" stage $ARGUMENTS`

Tell the user in one plain-English line what changed, using the output above. No Spanish.
