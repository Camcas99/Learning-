---
description: Turn output practice on or off ("Your turn" lines that invite you to write a little Spanish)
argument-hint: "[on|off]"
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" output $ARGUMENTS`

Confirm in one plain-English line (with no argument, say whether it is on or off). No Spanish.
