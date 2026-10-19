# Installing Spanish Weave (instructions for a coding agent)

You are setting up Spanish Weave for the person you are working with. Follow these steps in order. Run every
command yourself; the person only does the steps marked HUMAN. Write no Spanish in anything you say during setup.

Spanish Weave lives in the GitHub repo `Camcas99/Learning-`, in its `language/spanish-weave` folder; the plugin
marketplace (named `learning`) is at the repo root, so always add the repo itself, not the subfolder. Add it from
GitHub whenever there is network access, even if the person gave you a zip or a clone (step 2 says why).

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
3. If you picked the Chrome extension, which websites? It sends the readable text of each page it runs on to
   Google's Gemini with your key; with a free key Google may use it to improve its AI and people may review it, so
   banking, health, work and private messaging sites are better left off.
   - Every site: common webmail, chat apps and local addresses start off; turn others off from the toolbar (default)
   - Only sites I turn on (most private)
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
claude plugin marketplace add Camcas99/Learning-
claude plugin install spanish-weave@learning
claude plugin list | grep -A3 spanish-weave
```

The plugin is enabled when the list shows it. It adds a prompt hook (the chat weaving) and `/spanish-weave:*` commands.

Add the GitHub repo whenever there is network access: Claude Code then keeps its own copy and can update it. Only
without network access, add a local clone or unzipped folder instead (`claude plugin marketplace add <folder>`, the
repo's top folder, whose `.claude-plugin/` holds `marketplace.json`, not `language/spanish-weave`). Claude Code loads
the plugin from that folder, so it must sit somewhere permanent (for example `~/src/Learning-`), not Downloads or a
temp folder: if it moves or is deleted, chat weaving silently stops. Never delete a folder that
`claude plugin marketplace list` shows as a source.

## 3. Run setup

Find the installed copy and run its setup script with the flags from the answers (table in step 0):

```sh
SW="$(python3 -c 'import json, os; p = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "plugins", "installed_plugins.json"); print(json.load(open(p))["plugins"]["spanish-weave@learning"][0]["installPath"] + "/scripts/sw.py")')"
echo "$SW"
python3 "$SW" setup --known-top 40 --sites all --gemini-key-file /path/to/key-file --codex   # for example
```

The `SW=` line reads where Claude Code installed the plugin from its `installed_plugins.json`. Many agent shells keep
no variables between commands, so run that line again in the same command before anything else that uses `"$SW"`.

Without a key file, run setup without `--gemini-key-file`; the person pastes the key in the extension popup later.
With `--codex`, setup adds a UserPromptSubmit hook to `~/.codex/hooks.json` (other hooks are kept; backups end in
`.before-spanish-weave`) and sets `hooks = true` under `[features]` in `~/.codex/config.toml`. Codex runs a new hook
only after the person trusts it at the next `codex` start; setup cannot do that for them. No AGENTS.md change is
needed: the hook carries the rules every turn.

If the `SW=` line fails (a Python error: the plugin isn't installed for this user), run setup from a full copy of the
repo instead (`python3 <folder>/language/spanish-weave/scripts/sw.py setup ...`). Setup copies what it needs into
`~/.spanish-weave`, so a clone made only for this can be deleted afterwards, unless it is the folder the marketplace
was added from (step 2).

If the person runs Chrome or Chromium with a custom `--user-data-dir`, add `--user-data-dir <that dir>` (repeatable):
a browser started that way looks for native hosts only inside that dir.

Setup is safe to run again (it keeps the person's word progress; leaving out `--sites` keeps the earlier choice,
and whichever came last of setup's `--sites` and the popup's "Other sites" choice wins).
It always installs the extension folder and native host, even if the person didn't pick the extension. It creates:

- `~/.spanish-weave/` (or `$SPANISH_WEAVE_HOME`, which must be a new or empty folder, or an earlier Spanish Weave
  one, that the person owns; setup refuses any other): word state, the extension folder to load, the native host
- Chrome and Chromium native messaging host manifests (user level, no sudo):
  - Linux: `~/.config/google-chrome/NativeMessagingHosts/`, `~/.config/chromium/NativeMessagingHosts/`
  - macOS: `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/`, `.../Chromium/NativeMessagingHosts/`

## 4. Verify

```sh
SW="$(python3 -c 'import json, os; p = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "plugins", "installed_plugins.json"); print(json.load(open(p))["plugins"]["spanish-weave@learning"][0]["installPath"] + "/scripts/sw.py")')"
python3 "$SW" check
python3 "$SW" status
```

Every `check` line must say `ok` (a `note` about the Gemini key is fine if the person will paste it in the popup).
If one says `FAIL`, fix it before going on; rerunning setup fixes most. `check` also fails when setup's copies in
`~/.spanish-weave` are older than the installed plugin (rerun setup), and when the `learning` marketplace was added
from a local folder that is gone: Claude Code can't load the plugin then, so re-add it from GitHub with the three
commands `check` prints.

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
   in one-shot `claude -p` or `codex exec` runs. Automated sessions the desktop app starts (scheduled tasks,
   workflows) can't be told apart yet and get Spanish too; `/spanish-weave:pause` or `SPANISH_WEAVE_OFF=1` stops it.
5. Placement test, if they chose it: with the `SW=` line from step 3 first, run `python3 "$SW" placement --items`,
   show the intro and numbered list as printed in one code block, ask for the numbers of the words they know (never
   say which are made up), then run `python3 "$SW" placement --answers '<their numbers>' --apply` (only the digits,
   commas, spaces and hyphens from their reply) and relay the estimate and stage. Do this before the preferences
   block (next item), so the block includes those words.
6. Preferences block: run `python3 "$SW" export` (claude.ai) and `python3 "$SW" export --chatgpt` (ChatGPT) and
   show each block as printed in a code block, with where to paste it; they use whichever applies. Re-export
   about once a week.
7. Commands, which they type themselves (Claude can't start them, except status): `/spanish-weave:status`,
   `/spanish-weave:known <word>`, `/spanish-weave:learn <word>`, `/spanish-weave:stage 1-4|auto`,
   `/spanish-weave:pause`, `/spanish-weave:resume`, `/spanish-weave:quiz`, `/spanish-weave:placement`,
   `/spanish-weave:anki`, `/spanish-weave:output on|off`, and `/spanish-weave:export` for a claude.ai or ChatGPT
   preferences block.
8. Updates: the steps in "Update" below. `/spanish-weave:status` says when the copies in `~/.spanish-weave` are
   behind the plugin.

You are done when `check` is all `ok` and only the HUMAN steps above remain. If you cloned the repo only to read
these instructions or to run setup, you may delete that clone (setup keeps its own copy in `~/.spanish-weave`), but
only if `claude plugin marketplace list` doesn't show it as a source.

## Update

```sh
claude plugin marketplace update learning
claude plugin update spanish-weave@learning
SW="$(python3 -c 'import json, os; p = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "plugins", "installed_plugins.json"); print(json.load(open(p))["plugins"]["spanish-weave@learning"][0]["installPath"] + "/scripts/sw.py")')"
python3 "$SW" setup
python3 "$SW" check
```

The extension folder, native host and Codex hook script run from copies in `~/.spanish-weave` that a plugin update
doesn't touch; setup refreshes them. With no flags it keeps word progress, the site choice and a stored key, and
asks nothing. `check` (and `/spanish-weave:status`) says when those copies are behind the installed plugin, and
`check` flags a local marketplace folder that is gone. Then the person clicks the reload arrow on Spanish Weave in
`chrome://extensions` (HUMAN), and the updated chat hook loads in the next Claude Code session. If the marketplace
was added from a local folder, bring that folder up to date first (`git pull` in it, or unzip the new version into
the same place), since `marketplace update` reads from it.

## Uninstall

Run these in this order. `uninstall` runs from the copy setup keeps in `~/.spanish-weave`, which outlives the plugin
(the installed plugin's copy goes with `plugin uninstall`, and the marketplace's clone with `marketplace remove`):

```sh
python3 ~/.spanish-weave/app/scripts/sw.py uninstall --codex  # --dry-run first to see what it would do
claude plugin uninstall spanish-weave@learning
claude plugin marketplace remove learning  # only if nothing else from that marketplace is installed
```

With a custom state folder, run `python3 "$SPANISH_WEAVE_HOME/app/scripts/sw.py" uninstall --codex` instead; if
there is no `app` folder there, setup never ran, so skip that line. A local folder the marketplace was added from
isn't part of the install; once `marketplace remove` has run, the person can delete it if they no longer want it.

`uninstall` removes every native host manifest setup wrote, including the `--user-data-dir` ones it recorded (setup
before 0.2.1 recorded none: pass the same `--user-data-dir <dir>` flags to `uninstall`). With `--codex` it also
removes the Codex hook and, when no other Codex hooks remain, the `hooks = true` line setup added to
`~/.codex/config.toml` (a `hooks = ...` line that was there before setup goes back to what it was). A
`hooks.json` or `config.toml` that setup created is deleted once nothing else is in it.

It ends with "Left in place:", each piece with the command that removes it. Relay that list to the person:

- the Claude Code plugin: the two `claude plugin` commands above. Remove it before `~/.spanish-weave`, or its hook
  starts a new word list there on the next prompt.
- the Chrome extension (HUMAN): `chrome://extensions` -> Remove on Spanish Weave.
- `~/.codex/hooks.json.before-spanish-weave` and `config.toml.before-spanish-weave`, if listed: the Codex files from
  before setup first changed them; `rm` them once they're not needed.
- `~/.spanish-weave` (or `$SPANISH_WEAVE_HOME`): the word progress, the extension folder, the native host and any
  stored Gemini key. `rm -rf` it only if the person wants their progress gone; it can't be recovered.
