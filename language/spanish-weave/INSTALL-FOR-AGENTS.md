# Installing Spanish Weave (instructions for a coding agent)

You are setting up Spanish Weave for the person you are working with. Follow these steps in order. Run every
command yourself; the person only does the steps marked HUMAN. Write no Spanish in anything you say during setup.

`<repo>` below is what the person gave you: the GitHub repo `Camcas99/Learning-`, its git URL, or a local clone of it.
Spanish Weave lives in that repo's `language/spanish-weave` folder; the plugin marketplace (named `learning`) is at
the repo root, so always add the repo itself, not the subfolder.

macOS or Linux only. On Windows, install nothing: offer the paste-in block (`blocks/level-01.md`) instead. Chrome
on Windows finds native hosts only through the registry, setup's host launcher is a `#!/bin/sh` script, and the
hook calls `python3`, so the full version doesn't work there yet.

## 0. Ask a few questions and list the human steps, in one batch, before you start

Run `codex --version` first: if it fails, leave Codex CLI out of question 2. Then, in Claude Code, send the
human steps below as a short message and ask all four questions in one AskUserQuestion call (question 2
multi-select, the default option first with "(default)" in its label). In Codex or anywhere else, send the
human steps and the numbered questions as one chat message. Anyone who skips a question gets the default.

Human steps (send as written):

> Setting up Spanish Weave. A few quick questions below; I'll do the rest, except these steps for you:
> 1. If you pick the Chrome extension: at the end, open `chrome://extensions`, switch on **Developer mode**, click
>    **Load unpacked**, and pick the folder I give you (it's hidden: press Cmd+Shift+G on a Mac or Ctrl+L on Linux
>    and paste the path), then pin the Spanish Weave toolbar icon (puzzle-piece menu), click it and **Allow all
>    websites** (or tick the checkbox next to each site's name, on each site you want). Chrome doesn't let scripts do
>    this part.
> 2. If you pick the Chrome extension: a Gemini API key (free at https://aistudio.google.com/apikey for anyone 18
>    or older), as a file path now or pasted into the extension's popup at the end.
> 3. If you pick Codex CLI: the next time you start `codex`, it asks you to review a new hook; choose
>    **Trust all and continue**.

Questions:

1. How much Spanish do you know already?
   - None (default)
   - A few basic words
   - I can read simple Spanish
   - Not sure: take a 2-minute placement test
2. Where should Spanish show up? (pick any)
   - Claude Code (always on with the plugin)
   - Codex CLI (default when installed; only offered if `codex --version` works)
   - The Chrome extension on websites (default)
   - A claude.ai / ChatGPT preferences block to paste
3. If you picked the Chrome extension, which websites?
   - Every site; turn any off from the toolbar (default)
   - Only sites I turn on
4. If you picked the Chrome extension, your Gemini API key:
   - Paste it into the extension's popup at the end (default)
   - A file that contains it: type its path (in Claude Code, under Other). Never paste the key itself here.

Steps 1 and 2 below don't depend on the answers: if you can keep working while the person answers, do them now;
otherwise do them right after. Never ask for the key in chat, and never print it. If an answer looks like a key
rather than a file path (for example it starts with `AIza`), don't pass it to setup or repeat it; tell the person to
paste it into the extension popup instead.

How the answers map to setup (step 3) and the hand-over (step 5):

| Answer | Effect |
| --- | --- |
| 1. None / a few basic words / simple Spanish | `--known-top 0` / `--known-top 40` / `--known-top 150` |
| 1. Placement test | `--known-top 0`, then the placement test after setup (step 5) |
| 2. Codex CLI | `--codex` |
| 2. Chrome extension | pass answers 3 and 4; give the Chrome steps at the end |
| 2. Preferences block | run `export` at the end |
| 3. Every site / only sites I turn on | `--sites all` / `--sites ask` |
| 4. A file path | `--gemini-key-file <path>` |

`--known-top N` marks as known those of the N most common words in `data/lexicon.csv` that aren't introduced yet;
words already learning or known keep their status, so a rerun never resets or lowers anyone's progress. On a new
word state that gives exactly N known (Stage 2 at 40, Stage 3 at 150). But the plugin's prompt hook creates the
state, with 5 learning words, on the first prompt after the plugin loads, so when the state already exists the
count can come out up to 5 short (35 is still Stage 1, 145 is Stage 2) until those words graduate. Report the stage
setup prints.

## 1. Check prerequisites

```sh
python3 -c 'import sys; assert sys.version_info >= (3, 9), sys.version; print(sys.version)'
git --version
claude --version
```

Python 3.9+, git (Claude Code uses it to download the plugin from GitHub) and Claude Code. Nothing else is needed:
no pip installs, no Node. On a Mac, `python3` and `git` come with Apple's command line developer tools. If either
command prints `xcode-select: note: No developer tools were found, requesting install`, macOS has just opened a
window on the person's screen (HUMAN): tell them to click Install in it, wait for it to finish (a few minutes) and
tell you, then rerun step 1. Elsewhere, if `git` is missing, it comes from the system package manager (for example
`sudo apt install git`; the person may need to run it, since it asks for their password); then rerun step 1.

## 2. Install the Claude Code plugin

```sh
claude plugin marketplace add <repo>
claude plugin install spanish-weave@learning
claude plugin list | grep -A3 spanish-weave
```

The plugin is enabled when the list shows it. It adds a prompt hook (the chat weaving) and `/spanish-weave:*` commands.

## 3. Run setup

Find the installed copy and run its setup script with the flags from the answers (table in step 0):

```sh
SW="$(find "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins" -path '*spanish-weave*' -path '*/scripts/sw.py' 2>/dev/null | sort | tail -1)"
echo "$SW"
python3 "$SW" setup --known-top 40 --sites all --gemini-key-file /path/to/key-file --codex   # for example
```

Without a key file, run setup without `--gemini-key-file`; the person pastes the key in the extension popup later.
With `--codex`, setup adds a UserPromptSubmit hook to `~/.codex/hooks.json` (other hooks are kept; backups end in
`.before-spanish-weave`) and sets `hooks = true` under `[features]` in `~/.codex/config.toml`. Codex runs a new hook
only after the person trusts it at the next `codex` start; setup cannot do that for them. No AGENTS.md change is
needed: the hook carries the rules every turn.

If `find` prints nothing, run setup from a clone of `<repo>` instead (`python3 <clone>/language/spanish-weave/scripts/sw.py setup ...`);
setup copies what it needs, so the clone can be deleted afterwards.

If the person runs Chrome or Chromium with a custom `--user-data-dir`, add `--user-data-dir <that dir>` (repeatable):
a browser started that way looks for native hosts only inside that dir.

Setup is safe to run again (it keeps the person's word progress; leaving out `--sites` keeps the earlier choice).
It always installs the extension folder and native host, even if the person didn't pick the extension. It creates:

- `~/.spanish-weave/` (or `$SPANISH_WEAVE_HOME`): word state, the extension folder to load, the native host
- Chrome and Chromium native messaging host manifests (user level, no sudo):
  - Linux: `~/.config/google-chrome/NativeMessagingHosts/`, `~/.config/chromium/NativeMessagingHosts/`
  - macOS: `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/`, `.../Chromium/NativeMessagingHosts/`

## 4. Verify

```sh
python3 "$SW" check
python3 "$SW" status
```

Every `check` line must say `ok` (a `note` about the Gemini key is fine if the person will paste it in the popup).
If one says `FAIL`, fix it before going on; rerunning setup fixes most.

## 5. Hand over

Tell the person, in plain English (leave out the items for things they didn't pick):

1. Chrome extension: the HUMAN Chrome step with the exact folder from `check` (`~/.spanish-weave/extension` expanded
   to a full path): `chrome://extensions` -> Developer mode on -> Load unpacked -> that folder. Tell them the folder
   is hidden, so in the picker they press Cmd+Shift+G (Mac) or Ctrl+L (Linux), paste the full path, press Return
   and click Select. Then the Spanish Weave toolbar icon (puzzle piece menu -> pin it): every-site mode, click
   **Allow all websites** (Chrome asks
   once; until then it runs only on X and Instagram); only-sites-I-turn-on mode, tick the checkbox next to the
   site's name in the popup, on each site they want.
2. Chrome extension, no key file given: click the Spanish Weave toolbar icon (puzzle piece menu -> pin it) and paste
   the Gemini key.
3. Codex CLI: at the next `codex` start, choose **Trust all and continue** when it asks about the new hook.
4. Chat weaving starts in the next Claude Code or Codex session they open (hooks load at session start), and never
   in one-shot `claude -p` or `codex exec` runs (`SPANISH_WEAVE_OFF=1` turns it off anywhere else).
5. Placement test, if they chose it: run `python3 "$SW" placement --items`, show the intro and numbered list as
   printed in one code block, ask for the numbers of the words they know (never say which are made up), then
   run `python3 "$SW" placement --answers "<their numbers>" --apply` and relay the estimate and stage. Do this
   before the preferences block (next item), so the block includes those words.
6. Preferences block: run `python3 "$SW" export` (claude.ai) and `python3 "$SW" export --chatgpt` (ChatGPT) and
   show each block as printed in a code block, with where to paste it; they use whichever applies. Re-export
   about once a week.
7. Commands: `/spanish-weave:status`, `/spanish-weave:known <word>`, `/spanish-weave:learn <word>`,
   `/spanish-weave:stage 1-4|auto`, `/spanish-weave:pause`, `/spanish-weave:resume`, `/spanish-weave:quiz`,
   `/spanish-weave:placement`, `/spanish-weave:anki`, `/spanish-weave:output on|off`, and `/spanish-weave:export`
   for a claude.ai or ChatGPT preferences block.

You are done when `check` is all `ok` and only the HUMAN steps above remain. If you cloned the repo only to read
these instructions, delete that clone (setup keeps its own copy in `~/.spanish-weave`).

## Update

```sh
claude plugin marketplace update learning
claude plugin update spanish-weave@learning
SW="$(find "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins" -path '*spanish-weave*' -path '*/scripts/sw.py' 2>/dev/null | sort | tail -1)"
python3 "$SW" setup
```

The extension folder, native host and Codex hook script run from copies in `~/.spanish-weave` that a plugin update
doesn't touch; setup refreshes them. With no flags it keeps word progress, the site choice and a stored key, and
asks nothing. Then the person clicks the reload arrow on Spanish Weave in `chrome://extensions` (HUMAN), and the
updated chat hook loads in the next Claude Code session.

## Uninstall

```sh
python3 "$SW" uninstall --codex  # removes the native host manifests and the Codex hook; keeps ~/.spanish-weave
claude plugin uninstall spanish-weave@learning
```

Then remove the extension in `chrome://extensions`, and delete `~/.spanish-weave` to drop the word progress.
