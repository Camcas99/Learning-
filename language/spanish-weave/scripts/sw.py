#!/usr/bin/env python3
"""Spanish Weave command line: setup, status, word and stage changes. Python 3.9+, standard library only.

  sw.py setup [--gemini-key-file FILE] [--user-data-dir DIR]... [--known-top N] [--sites all|ask] [--dry-run]
                                                     install the state dir, extension copy and native host; the
                                                     state dir (SPANISH_WEAVE_HOME) must be yours and new, empty or
                                                     an earlier Spanish Weave one, or setup refuses it;
                                                     --user-data-dir also registers the host for a browser run
                                                     with that --user-data-dir (Chromium looks there);
                                                     --known-top marks the top N lexicon words known unless
                                                     already introduced (40: some basics, 150: simple Spanish);
                                                     --sites: extension on every site (all) or only ones you
                                                     turn on (ask)
  sw.py status                                       stage, word counts, learning words, and a line when setup's
                                                     copies are behind the installed plugin
  sw.py known WORD...                                mark words as known; listed phrases too (known sin embargo,
                                                     pero), and quotes and ¡!¿? are fine
  sw.py learn WORD...                                put words back in the learning set (shaky)
  sw.py stage [N|auto]                               pin the stage (1-4) or let it follow known words; with no
                                                     value, show it
  sw.py pause | resume                               stop or restart Spanish in chat and on websites
  sw.py refresh                                      rescan chat transcripts and apply the promotion rules
  sw.py setup --codex [--dry-run]                    also add the chat hook to Codex CLI (~/.codex or $CODEX_HOME)
  sw.py export [--claude-ai | --chatgpt] [--log-day] paste-ready block for claude.ai preferences or ChatGPT
                                                     (the flags work without dashes too: export chatgpt)
  sw.py log-chat-day                                 opt-in: count today as exposure for your learning words
  sw.py check                                        verify the state, extension folder and native host, that
                                                     setup's copies match the installed plugin's version, and that
                                                     a local folder the marketplace was added from is still there
  sw.py quiz [-n N] [--plan [N]]                     spaced-repetition quiz on words that are due (--plan: list
                                                     N questions with answers instead, default 5, for Claude to ask)
  sw.py review WORD right|wrong [--article A]        record one quiz answer (--article: the el/la they used, if
                                                     it wasn't the listed one; a noun whose ending doesn't give
                                                     its gender away then stays in its box)
  sw.py record WORD:right|wrong[:A]...               record several quiz answers in one save, each as review does
                                                     (A: the --article); exits 1 if any was not saved
  sw.py placement [--items] [--answers NUMS] [--apply]
                                                     2-minute placement test (Yes/No vocabulary test); NUMS like
                                                     "1, 4, 9-12"
  sw.py anki [--all] [--out FILE]                    your words as an Anki import file (tab-separated; all works
                                                     without dashes too); --out replaces only an earlier export
  sw.py output [on|off]                              "Your turn" lines that invite you to write some Spanish
  sw.py uninstall [--codex] [--user-data-dir DIR]... [--dry-run]
                                                     remove the native host manifests (only Spanish Weave's; and
                                                     the Codex hook and the `hooks = true` setup added), then list
                                                     what is left
"""
import argparse
import errno
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import swlib  # noqa: E402
import export  # noqa: E402
import placement  # noqa: E402

HOST_NAME = 'com.spanishweave.host'
EXTENSION_ID = 'papkhjkhjagpimlholdmecddkhhhcfje'  # fixed by the "key" in extension/manifest.json
ORIGIN = f'chrome-extension://{EXTENSION_ID}/'
# The native host can't push changes. The extension syncs the word state when a page asks for swaps and its copy is
# over 2 minutes old, when the popup opens, and every 10 minutes (STALE_MS and SYNC_MINUTES in background.js). A page
# that asks for nothing (all painted, or stopped by a pause) hears only from the last two.
CHROME_PICKS_UP = 'Chrome picks this up within 10 minutes, or as soon as you open the Spanish Weave popup.'
CHROME_PAUSED = ('Chrome stops sending new page text to Gemini within 2 minutes; Spanish already on an open page goes '
                 'when you reload it after that, when you open the Spanish Weave popup, or within 10 minutes.')
PLUGIN_KEY = 'spanish-weave@learning'  # the plugin's name in Claude Code: plugin@marketplace
REPO = 'Camcas99/Learning-'  # the GitHub repo the marketplace comes from


def host_dirs(extra=()):
    """User-level NativeMessagingHosts folders for Google Chrome and Chromium on this OS, plus any extra
    browser user-data dirs (a browser started with --user-data-dir looks only inside that dir)."""
    home = Path.home()
    extra = [Path(d).expanduser().resolve() / 'NativeMessagingHosts' for d in extra]
    if sys.platform == 'darwin':
        base = home / 'Library' / 'Application Support'
        return [base / 'Google' / 'Chrome' / 'NativeMessagingHosts', base / 'Chromium' / 'NativeMessagingHosts'] + extra
    config = Path(os.environ.get('XDG_CONFIG_HOME') or home / '.config')
    return [config / 'google-chrome' / 'NativeMessagingHosts', config / 'chromium' / 'NativeMessagingHosts'] + extra


def plan(extra=()):
    root, home = swlib.PLUGIN_ROOT, swlib.home()
    return {
        'python': sys.executable,
        'python_version': platform.python_version(),
        'platform': sys.platform,
        'source': str(root),
        'state_dir': str(home),
        'extension_dir': str(home / 'extension'),
        'host_launcher': str(home / 'app' / 'sw-host'),
        'host_manifests': [str(d / f'{HOST_NAME}.json') for d in host_dirs(extra)],
        'extension_id': EXTENSION_ID,
        'codex_cli': shutil.which('codex'),
    }


CODEX_MARK = 'spanish-weave'  # our Codex hook command always contains this (the state dir path)


def codex_command():
    return f'"{sys.executable}" "{swlib.home() / "app" / "scripts" / "weave.py"}" --hook'


def is_ours(handler):
    command = handler.get('command', '') if isinstance(handler, dict) else ''
    return 'weave.py' in command and '--hook' in command and str(swlib.home()) in command


def merge_codex_hooks(data, command):
    """hooks.json with our UserPromptSubmit handler added or updated in place; other hooks untouched."""
    data = data if isinstance(data, dict) else {}
    groups = data.setdefault('hooks', {}).setdefault('UserPromptSubmit', [])
    for group in groups:
        for handler in group.get('hooks', []):
            if is_ours(handler):
                handler['command'] = command  # same place, so Codex keeps the trust if nothing changed
                return data
    groups.append({'hooks': [{'type': 'command', 'command': command}]})
    return data


def features_table(lines):
    """(header, end) line indexes of the [features] table in config.toml lines, or None."""
    start = next((i for i, line in enumerate(lines) if line.strip() == '[features]'), None)
    if start is None:
        return None
    return start, next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith('[')), len(lines))


def hooks_line(text):
    """The `hooks = ...` line in config.toml's [features] table, or None."""
    lines = text.splitlines()
    start, end = features_table(lines) or (0, 0)
    return next((lines[i] for i in range(start + 1, end) if re.match(r'\s*hooks\s*=', lines[i])), None)


def enable_codex_hooks(text, setting='hooks = true'):
    """config.toml text with `hooks = true` (or another hooks setting) in its [features] table (added if missing)."""
    lines = text.splitlines()
    if features_table(lines) is None:
        return text.rstrip('\n') + ('\n\n' if text.strip() else '') + f'[features]\n{setting}\n'
    start, end = features_table(lines)
    for i in range(start + 1, end):
        if re.match(r'\s*hooks\s*=', lines[i]):
            lines[i] = setting
            break
    else:
        lines.insert(start + 1, setting)
    return '\n'.join(lines) + '\n'


def disable_codex_hooks(text):
    """config.toml text without a `hooks = true` line in [features], and without [features] if nothing else is in it:
    what enable_codex_hooks added, taken out again."""
    lines = text.splitlines()
    table = features_table(lines)
    if table is None:
        return text
    start, end = table
    rest = [line for line in lines[start + 1:end] if not re.match(r'\s*hooks\s*=\s*true\s*(#.*)?$', line)]
    if len(rest) == end - start - 1:
        return text  # no `hooks = true` there
    if any(line.strip() for line in rest):
        lines[start + 1:end] = rest
    else:
        del lines[start:end]  # the table is empty without it
    out = '\n'.join(lines).rstrip('\n')
    return out + '\n' if out else ''


INSTALL = 'install.json'  # what setup put outside the state dir (host manifests, the Codex flag), for uninstall


def install_record():
    data = swlib.read_json(swlib.home() / INSTALL, {})
    return data if isinstance(data, dict) else {}


def remember(**changes):
    swlib.write_json(swlib.home() / INSTALL, dict(install_record(), **changes))


def has_our_hook(data):
    groups = ((data if isinstance(data, dict) else {}).get('hooks') or {}).get('UserPromptSubmit') or []
    return any(is_ours(h) for g in groups for h in g.get('hooks', []))


def backup_of(path):
    return path.with_name(path.name + '.before-spanish-weave')


def codex_flag_added(config_path, first):
    """Whether `hooks = true` in config.toml is setup's: setup backs config.toml up before it first changes it, so
    the backup (else, before a first setup, the file itself) shows what was there before."""
    before = backup_of(config_path) if backup_of(config_path).exists() else config_path if first else None
    return hooks_line(before.read_text() if before and before.exists() else '') is None


def setup_codex(dry_run):
    codex = swlib.codex_home()
    hooks_path, config_path = codex / 'hooks.json', codex / 'config.toml'
    existing = swlib.read_json(hooks_path, {}) if hooks_path.exists() else {}
    first = not has_our_hook(existing)  # a rerun keeps the first run's backups: they show what was there before
    data = merge_codex_hooks(existing, codex_command())
    config = enable_codex_hooks(config_path.read_text() if config_path.exists() else '')
    if dry_run:
        print(json.dumps({'codex_hooks': str(hooks_path), 'codex_config': str(config_path), 'command': codex_command()},
                         indent=1))
        return
    if hooks_path.exists() and swlib.read_json(hooks_path) is None:
        sys.exit(f'{hooks_path} is not valid JSON; fix it, then rerun setup --codex.')
    codex.mkdir(parents=True, exist_ok=True)
    if 'codex_hooks_added' not in install_record():  # so uninstall takes out only a `hooks = true` that setup added
        remember(codex_hooks_added=codex_flag_added(config_path, first))
    for path in (hooks_path, config_path):
        if first and path.exists() and not backup_of(path).exists():
            shutil.copy2(path, backup_of(path))
    swlib.write_json(hooks_path, data)  # both writes keep a symlinked file a link
    swlib.write_text(config_path, config)
    print(f'Codex: chat hook in {hooks_path}, hooks enabled in {config_path}.')
    print('  Human step: start `codex` once; at "Hooks need review" pick "Trust all and continue" (or review first).')
    print('  Codex never runs a new hook before that. `codex exec` runs stay Spanish-free either way.')


KEY_SHAPE = re.compile(r'^[A-Za-z0-9_-]{30,64}$')


def read_key_file(arg):
    """The key from a file. Never echoes the argument, the path or the contents, since any of them may be the key."""
    path = Path(arg).expanduser()
    if not path.is_file() and (arg.startswith('AIza') or KEY_SHAPE.match(arg)):
        sys.exit('That looks like a key, not a file path; paste the key into the extension popup instead.')
    try:
        key = path.read_text().strip()
    except (OSError, UnicodeDecodeError):
        sys.exit('Could not read the Gemini key file.')
    if not KEY_SHAPE.match(key):
        sys.exit('The Gemini key file should hold only the key (letters, digits, - and _).')
    return key


def installed_entries():
    """Claude Code's install records for the plugin (version, installPath, gitCommitSha), from
    <config>/plugins/installed_plugins.json; [] when it isn't installed (or runs from --plugin-dir)."""
    data = swlib.read_json(swlib.claude_config_dir() / 'plugins' / 'installed_plugins.json', {})
    plugins = data.get('plugins') if isinstance(data, dict) else None
    entries = plugins.get(PLUGIN_KEY) if isinstance(plugins, dict) else None
    entries = [entries] if isinstance(entries, dict) else entries if isinstance(entries, list) else []
    return [e for e in entries if isinstance(e, dict)]


def installed_plugin():
    return next(iter(installed_entries()), None)


def marketplace_entry():
    """known_marketplaces.json's entry for the marketplace the plugin comes from, or None."""
    data = swlib.read_json(swlib.claude_config_dir() / 'plugins' / 'known_marketplaces.json', {})
    entry = data.get(PLUGIN_KEY.split('@')[1]) if isinstance(data, dict) else None
    return entry if isinstance(entry, dict) else None


def plugin_version():
    """This copy's version from .claude-plugin/plugin.json, or None (the copies in <home>/app have no plugin.json)."""
    data = swlib.read_json(swlib.PLUGIN_ROOT / '.claude-plugin' / 'plugin.json', {})
    version = data.get('version') if isinstance(data, dict) else None
    return version if isinstance(version, str) else None


def copies_behind(home):
    """(version of setup's copies in home or None, the installed plugin's version) when they differ, else None. The
    extension, native host and Codex hook run from those copies, so a plugin update reaches them only through setup."""
    plugin = (installed_plugin() or {}).get('version')
    have = install_record().get('version')
    return (have, plugin) if plugin and (home / 'app').exists() and have != plugin else None


# Everything Spanish Weave keeps in its state dir: uninstall offers `rm -rf` on the dir only when nothing else is in it
# (OS junk like .DS_Store aside).
SW_NAMES = swlib.OWN_FILES | {'app', 'extension'}


def own_copy(home, name):
    """True when home/name (extension or app), which setup replaces whole, is missing, empty or Spanish Weave's own
    copy: the extension's manifest names it, or app holds sw.py (or, after an interrupted setup, only the word list)."""
    path = home / name
    if not path.exists():
        return True
    if not path.is_dir():
        return False
    if not [p for p in path.iterdir() if not swlib.os_junk(p.name)]:
        return True
    if name == 'extension':
        return swlib.own_extension(home)
    return swlib.own_app(home) or (path / 'data' / 'lexicon.csv').is_file()


def check_home(home):
    """Exits (one line naming the folder, never the key) when setup could damage the state dir: it is not a folder or
    not the user's own, it holds other things and no Spanish Weave files, a folder setup replaces (app, extension
    and those in app) is a symlink or leads outside it, or app or extension is there and isn't Spanish Weave's copy
    (state.json alone proves nothing: the prompt hook of 0.3.0 and earlier wrote it into any folder)."""
    if not home.exists() and not home.is_symlink():
        return
    if not home.is_dir():
        sys.exit(f'{home} is not a folder; set SPANISH_WEAVE_HOME to a new or empty folder.')
    swlib.check_owner(home)
    not_ours = f'{home} is not a Spanish Weave folder; pick a new or empty one (SPANISH_WEAVE_HOME).'
    if swlib.foreign(home):
        sys.exit(not_ours)
    inside = home.resolve()
    for name in ('app', 'extension', 'app/scripts', 'app/data', 'app/sw-host'):
        path = home / name
        if path.is_symlink() or path.exists() and inside not in path.resolve().parents:
            sys.exit(f'{path} is a symbolic link or leads outside {home}; remove it, then rerun setup.')
    if not (own_copy(home, 'extension') and own_copy(home, 'app')):
        sys.exit(not_ours)


def write_key(path, key):
    """Stores the Gemini key 0600 from the first byte, and never through a symlink (it could point anywhere)."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    except OSError as error:
        if error.errno == errno.ELOOP or path.is_symlink():
            sys.exit('gemini_key is a symbolic link; remove it, then rerun setup.')
        raise
    with os.fdopen(fd, 'w') as file:
        os.fchmod(fd, 0o600)  # an older key file may be 0644
        file.write(key + '\n')


def launcher_text(python, script, home):
    """The native host launcher. Chrome starts it without SPANISH_WEAVE_HOME, so it names the state dir itself; the
    paths are shell-quoted; and if the Python that ran setup is gone (a Homebrew cleanup, a deleted venv), python3 on
    PATH takes over."""
    python, script, home = (shlex.quote(str(x)) for x in (python, script, home))
    return (f'#!/bin/sh\nSPANISH_WEAVE_HOME={home}; export SPANISH_WEAVE_HOME\n'
            f'if [ -x {python} ]; then exec {python} {script} "$@"; fi\n'
            f'exec /usr/bin/env python3 {script} "$@"\n')


def setup(args):
    info = plan(args.user_data_dir)
    if sys.version_info < (3, 9):
        sys.exit(f'Spanish Weave needs Python 3.9 or newer; this is {info["python_version"]}.')
    root, home = swlib.PLUGIN_ROOT, swlib.home()
    if not (root / 'extension' / 'manifest.json').exists():
        sys.exit(f'No extension/ folder next to {root / "scripts"}; run setup from a full copy of the repo.')
    key = read_key_file(args.gemini_key_file) if args.gemini_key_file else None
    if args.dry_run:
        # current_sites: the site choice an earlier setup saved, so a rerun can offer to keep it (no --sites).
        state = swlib.read_json(home / 'state.json', {})
        prefs = state.get('prefs') if isinstance(state, dict) else None
        current = prefs.get('extension_sites') if isinstance(prefs, dict) else None
        print(json.dumps(dict(info, dry_run=True, gemini_key='would be stored' if key else 'not given',
                              known_top=args.known_top, sites=args.sites,
                              current_sites=current if current in ('all', 'ask') else None), indent=1))
        if args.codex:
            setup_codex(True)
        return
    check_home(home)
    existed = home.exists()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Never a folder of someone's that setup was only pointed at; state.json proves nothing, the hook may have made it.
    if not existed or (home / INSTALL).exists():
        os.chmod(home, 0o700)
    if key:
        write_key(home / 'gemini_key', key)
    # Stable copies: the plugin cache path changes on every update, Chrome needs fixed paths.
    for name, ignore in (('extension', shutil.ignore_patterns('test', 'node_modules', 'package.json', 'bun.lock')),
                         ('app/scripts', shutil.ignore_patterns('__pycache__')), ('app/data', None)):
        source = root / ('extension' if name == 'extension' else name.split('/')[1])
        target = home / name
        if target.exists():
            shutil.rmtree(target)  # check_home made sure it is Spanish Weave's own copy
        shutil.copytree(source, target, ignore=ignore)
    launcher = home / 'app' / 'sw-host'
    swlib.write_text(launcher, launcher_text(sys.executable, home / 'app' / 'scripts' / 'sw_host.py', home))
    launcher.chmod(0o755)
    manifest = {'name': HOST_NAME, 'description': 'Spanish Weave word state', 'path': str(launcher), 'type': 'stdio',
                'allowed_origins': [ORIGIN]}
    for directory in host_dirs(args.user_data_dir):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f'{HOST_NAME}.json').write_text(json.dumps(manifest, indent=1) + '\n')
    # The version of the copies, for check and status; the commit when this is the installed plugin's own folder.
    version = plugin_version() or install_record().get('version')
    commit = next((e.get('gitCommitSha') for e in installed_entries() if isinstance(e.get('installPath'), str)
                   and Path(e['installPath']).expanduser().resolve() == root), None)
    remember(host_manifests=list(dict.fromkeys((install_record().get('host_manifests') or []) + info['host_manifests'])),
             version=version, commit=commit)
    with swlib.locked():
        if not (home / 'state.json').exists():  # first run: seed known words before the first learning words
            swlib.save_state(swlib.new_state(known_top=args.known_top))
    with swlib.editing() as state:  # later runs: adds new lexicon words, seeds only words not yet introduced
        swlib.seed_known(state, args.known_top)
        if args.sites:  # timed, so the extension can tell whether this or a popup choice came last
            state.setdefault('prefs', {}).update(extension_sites=args.sites, extension_sites_at=int(time.time()))
    if args.codex:
        setup_codex(False)
    print(f'Spanish Weave{f" {version}" if version else ""} is set up'
          + (f' (commit {commit[:7]}).' if isinstance(commit, str) and commit else '.'))
    print(f'  word state:  {home / "state.json"} (Stage {swlib.stage_for(state)}, '
          f'{sum(w["status"] == "known" for w in state["words"])} known, '
          f'{sum(w["status"] == "active" for w in state["words"])} learning words)')
    sites = (state.get('prefs') or {}).get('extension_sites', 'all')
    print(f'  extension:   {"every site; turn any off from the toolbar" if sites == "all" else "only sites you turn on"}'
          ' (a later "Other sites" choice in the extension popup wins until setup sets it again)')
    print(f'               {CHROME_PICKS_UP}')
    print(f'  native host: {", ".join(info["host_manifests"])}')
    print(f'  Gemini key:  {"stored for the extension" if key or (home / "gemini_key").exists() else "not stored; paste it in the extension popup"}')
    print('Human steps left (Chrome blocks scripts from doing these):')
    print('  1. Open chrome://extensions and switch on Developer mode (top right).')
    print(f'  2. Click "Load unpacked" and pick: {home / "extension"}')
    if any(part.startswith('.') for part in home.parts):
        print('     The picker hides folders whose names start with a dot, so paste the path instead: press Cmd+Shift+G')
        print('     (Mac) or Ctrl+L (Linux), paste it, press Return, then click Select (or Open).')
    print('  3. Pin the Spanish Weave toolbar icon (puzzle piece menu; a gray "S") and click it:')
    if sites == 'all':
        print('     click "Allow all websites" (Chrome asks once; until then it runs only on X and Instagram).')
    else:
        print("     on each site you want, tick the checkbox next to the site's name (Chrome asks for that site).")
    if not key and not (home / 'gemini_key').exists():
        print('     Paste a Gemini API key (https://aistudio.google.com/apikey).')
    print('Chat weaving runs wherever the plugin is enabled; sessions opened from now on pick it up.')


def state_fix(error):
    """An unreadable state.json (swlib.StateError) and how to fix it, as lines."""
    path = swlib.home() / 'state.json'
    return (f'{error}. Chat weaving is off until it is fixed: repair the file by hand if you can, or move it aside\n'
            'and start a fresh word list (the progress in it is lost):\n'
            f'  mv "{path}" "{path}.broken"\n'
            f'  python3 "{Path(__file__).resolve()}" status\n'
            'Then take /spanish-weave:placement (or rerun setup with --known-top 40 or 150) if you knew some Spanish.')


def check(_args):
    """Prints one line per check; exits 1 if any failed."""
    import struct
    import subprocess
    home, ok = swlib.home(), True

    def report(passed, what):
        nonlocal ok
        ok = ok and passed
        print(f'{"ok  " if passed else "FAIL"} {what}')

    try:
        state = swlib.load_state(create=False)
        if state is None:
            swlib.check_ours(home)  # someone else's folder says so, not "run setup" (setup would refuse it)
        report(state is not None, f'word state at {home / "state.json"}' + (f' (Stage {swlib.stage_for(state)})' if state
                                                                            else ': not there yet; run setup'))
    except swlib.StateError as error:
        report(False, 'word state: ' + state_fix(error).replace('\n', '\n     '))
    except swlib.UnsafeHome as error:
        report(False, f'word state: {error}')
    report((home / 'extension' / 'manifest.json').exists(), f'extension folder for Load unpacked: {home / "extension"}')
    behind = copies_behind(home)
    if behind:
        report(False, f'copies in {home} are from {behind[0] or "an older version"}; the installed plugin is '
                      f'{behind[1]}: rerun setup')
    market = marketplace_entry() or {}
    source = market.get('source') if isinstance(market.get('source'), dict) else {}
    local = source.get('source') in ('directory', 'local')  # a GitHub marketplace has its own copy, kept by Claude Code
    folder = (source.get('path') or market.get('installLocation')) if local else None
    if isinstance(folder, str) and not Path(folder).expanduser().exists():
        name = PLUGIN_KEY.split('@')[1]
        report(False, f'the {name} marketplace was added from {folder}, which is gone, so Claude Code can\'t load the '
                      'plugin (no Spanish in chat). Add it again from GitHub:\n'
                      f'       claude plugin marketplace remove {name}\n'
                      f'       claude plugin marketplace add {REPO}\n'
                      f'       claude plugin install {PLUGIN_KEY}')
    for directory in host_dirs():
        path = directory / f'{HOST_NAME}.json'
        manifest = swlib.read_json(path)
        report(bool(manifest) and manifest.get('allowed_origins') == [ORIGIN], f'native host manifest {path}')
    launcher = home / 'app' / 'sw-host'
    try:
        message = json.dumps({'type': 'ping'}).encode()
        out = subprocess.run([str(launcher)], input=struct.pack('=I', len(message)) + message, capture_output=True,
                             timeout=20).stdout
        report(json.loads(out[4:]).get('ok') is True, f'native host answers: {launcher}')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report(False, f'native host answers: {launcher} ({error.__class__.__name__})')
    hooks = swlib.read_json(swlib.codex_home() / 'hooks.json', {}) or {}
    groups = (hooks.get('hooks') or {}).get('UserPromptSubmit') or []
    if any(is_ours(h) for g in groups for h in g.get('hooks', [])):
        config = (swlib.codex_home() / 'config.toml')
        enabled = config.exists() and enable_codex_hooks(config.read_text()) == config.read_text().rstrip('\n') + '\n'
        report(enabled, f'Codex hook in {swlib.codex_home() / "hooks.json"} with [features] hooks = true '
                        '(Codex asks you to trust it on first start)')
    has_key = (home / 'gemini_key').exists()
    print(f'{"ok  " if has_key else "note"} Gemini key {"stored by setup" if has_key else "not stored; paste it in the extension popup"}')
    if not ok:
        sys.exit(1)


def is_host_manifest(path):
    """True for our native host manifest: that file name, our host name and only our extension allowed."""
    data = swlib.read_json(path)
    return (path.name == f'{HOST_NAME}.json' and isinstance(data, dict) and data.get('name') == HOST_NAME
            and data.get('allowed_origins') == [ORIGIN])


def other_codex_hooks(data, config):
    """True when Codex has hooks besides ours (in hooks.json, or as hooks tables in config.toml)."""
    groups = [g for gs in (data.get('hooks') or {}).values() if isinstance(gs, list) for g in gs if isinstance(g, dict)]
    return (any(not is_ours(h) for g in groups for h in g.get('hooks') or [])
            or bool(re.search(r'^\s*\[\[?hooks\b', config, re.M)))


def uninstall(args):
    """Removes what setup put outside the state dir (a listed host manifest only if it is ours), then prints what is
    left and how to remove each piece: the state dir with one rm -rf only when nothing else is in it."""
    verb = 'would remove' if args.dry_run else 'removed'
    home, codex, record, left = swlib.home(), swlib.codex_home(), install_record(), []
    me = f'python3 "{Path(__file__).resolve()}"'
    hooks_path, config_path = codex / 'hooks.json', codex / 'config.toml'
    data = swlib.read_json(hooks_path, {})
    data = data if isinstance(data, dict) else {}
    config = config_path.read_text() if config_path.exists() else ''
    if has_our_hook(data) and not args.codex:
        left.append(f'the Codex chat hook in {hooks_path}:\n      {me} uninstall --codex')
    elif has_our_hook(data):
        groups = data['hooks']['UserPromptSubmit']
        kept = [{**g, 'hooks': [h for h in g.get('hooks', []) if not is_ours(h)]} for g in groups]
        data['hooks']['UserPromptSubmit'] = [g for g in kept if g['hooks']]
        if not backup_of(hooks_path).exists() and set(data) == {'hooks'} and not other_codex_hooks(data, ''):
            print(f'{verb} {hooks_path} (setup made it; nothing else is in it)')
            if not args.dry_run:
                hooks_path.unlink()
        else:
            print(f'{verb} the Spanish Weave hook from {hooks_path}')
            if not args.dry_run:
                swlib.write_json(hooks_path, data)
    line = hooks_line(config)
    if args.codex and line is not None:
        added = record.get('codex_hooks_added')
        if added is None:  # set up before 0.2.1, which kept no install.json
            added = codex_flag_added(config_path, first=False)
        others = other_codex_hooks(data, config)
        backup = backup_of(config_path)
        before = None if added or not backup.exists() else hooks_line(backup.read_text())  # setup may have flipped it on
        if not others and added and disable_codex_hooks(config) != config:
            rest = disable_codex_hooks(config)
            print(f'{verb} `{line.strip()}` from [features] in {config_path}' + ('' if rest else ' (and the file, now empty)'))
            if not args.dry_run and rest:
                swlib.write_text(config_path, rest)
            elif not args.dry_run:
                config_path.unlink()
            record.pop('codex_hooks_added', None)
        elif not others and before and before.strip() != line.strip():
            print(f'{"would restore" if args.dry_run else "restored"} `{before.strip()}` (from before setup) in [features] '
                  f'in {config_path}')
            if not args.dry_run:
                swlib.write_text(config_path, enable_codex_hooks(config, before.strip()))
            record.pop('codex_hooks_added', None)
        else:
            why = 'other Codex hooks use it' if others else 'it was there before setup' if not added else 'changed since setup'
            was = f'; before setup it was `{before.strip()}`' if before and before.strip() != line.strip() else ''
            left.append(f'`{line.strip()}` under [features] in {config_path} ({why}{was}); kept')
    manifests = [Path(m) for m in dict.fromkeys([str(d / f'{HOST_NAME}.json') for d in host_dirs(args.user_data_dir)]
                                                + (record.get('host_manifests') or []))]
    for path in manifests:
        if not path.exists():
            continue
        if not is_host_manifest(path):  # install.json may have been edited or copied from another machine
            left.append(f'{path} (not a Spanish Weave host manifest; left alone)')
            continue
        print(f'{verb} {path}')
        if not args.dry_run:
            try:
                path.unlink()
            except OSError as error:
                left.append(f'{path} (could not remove it: {error.strerror})')
    if not args.dry_run and (home / INSTALL).exists():
        swlib.write_json(home / INSTALL, dict(record, host_manifests=[str(m) for m in manifests
                                                                       if m.exists() and is_host_manifest(m)]))
    backups = [p for p in (hooks_path, config_path) if backup_of(p).exists()]
    print('Left in place:')
    print('  - the Claude Code plugin, if installed; its hook keeps weaving until it is gone. Remove it before the state '
          'folder, or the hook starts a new word list there on the next prompt:\n'
          '      claude plugin uninstall spanish-weave@learning\n'
          '      claude plugin marketplace remove learning   # only if nothing else from that marketplace is installed')
    print('  - the Chrome extension, if you loaded it: open chrome://extensions and click Remove on Spanish Weave')
    for item in left:
        print(f'  - {item}')
    for path in backups:
        print(f'  - {backup_of(path)}: your {path.name} from before setup first changed it; once you no longer need it:\n'
              f'      rm "{backup_of(path)}"')
    names = sorted(p.name for p in home.iterdir() if not swlib.os_junk(p.name)) if home.is_dir() else None
    ours = [name for name in names or [] if name in SW_NAMES]
    if names is not None and len(ours) == len(names):
        print(f'  - {home}: your word progress, the extension folder, the native host and any stored Gemini key:\n'
              f'      rm -rf "{home}"')
    elif ours:  # rm -rf on the folder would take the other things with it
        print(f'  - your word progress, the extension folder, the native host and any stored Gemini key, in {home}; '
              'it holds other things too, so delete only these:')
        for name in ours:
            print(f'      rm -rf "{home / name}"')


def status(_args):
    with swlib.editing() as state:
        pass
    by = {}
    for w in state['words']:
        by.setdefault(w['status'], []).append(w)
    stage = swlib.stage_for(state)
    print(f'Spanish Weave: Stage {stage}{" (pinned)" if state.get("stage_pinned") else ""}'
          f'{", PAUSED" if state.get("paused") else ""}')
    print(f'  known {len(by.get("known", []))}, learning {len(by.get("active", []))}, '
          f'shaky {len(by.get("shaky", []))}, not yet introduced {len(by.get("queue", []))}')
    chat = (swlib.read_json(swlib.home() / 'exposure.json', {}) or {}).get('words', {})
    for name in ('shaky', 'active'):
        for w in by.get(name, []):
            days = len(swlib.exposure_days(w, chat))
            print(f'  {name:6} {w["es"]} = {w["en"]}, "{w["hint"]}"  (seen on {days} day{"s" if days != 1 else ""})'
                  + (f'  {swlib.note(w["es"])}' if swlib.note(w['es']) else ''))
    uncounted = [w['es'] for w in by.get('shaky', []) + by.get('active', []) if swlib.norm(w['es']) in swlib.UNMEASURABLE]
    if uncounted:
        print(f'  {", ".join(uncounted)}: also English spelling{"s" if len(uncounted) > 1 else ""}, so chat can\'t count '
              f'{"them" if len(uncounted) > 1 else "it"}; the quiz, the extension or `known` can')
    nxt = next((n for n, s in sorted(swlib.STAGES) if swlib.stage_for(state) < s), None)
    if nxt and not state.get('stage_pinned'):
        print(f'  next stage at {nxt} known words')
    due = len(swlib.due_reviews(state, limit=len(state['words'])))
    print(f'  {due} word{"s" if due != 1 else ""} due for review: /spanish-weave:quiz or sw.py quiz' if due else
          f'  {nothing_due(state)[0].lower()}{nothing_due(state)[1:]}')
    behind = copies_behind(swlib.home())
    if behind:
        print(f'  the extension and native host copies are from {behind[0] or "an older version"}, the plugin is '
              f'{behind[1]}: rerun /spanish-weave:setup')


QUOTES = '"“”«»\'‘’'
LONGEST_PHRASE = 5  # tokens; the longest listed phrases have 4


def word_groups(words):
    """known/learn arguments as token lists, one per comma-separated group: the arguments joined (a shell may have
    split a phrase), quotes dropped, and Spanish punctuation taken off each token: '"tal vez", ¡hola!' ->
    [['tal', 'vez'], ['hola']]."""
    text = ' '.join(words).translate({ord(c): None for c in QUOTES})
    groups = [[t for t in (t.strip('¡!¿?.;:()') for t in group.split()) if t] for group in text.split(',')]
    return [group for group in groups if group]


def mark(kind):
    def run(args):
        groups = word_groups(args.words)
        if not groups:
            print(f'Give one or more words from the list, like: {args.command} pero, sin embargo')
            return
        missing, done = [], []
        with swlib.editing() as state:
            for tokens in groups:
                i = 0
                while i < len(tokens):
                    # Longest listed phrase first: "sin embargo pero" is sin embargo and pero, not sin.
                    for n in range(min(LONGEST_PHRASE, len(tokens) - i), 0, -1):
                        phrase = ' '.join(tokens[i:i + n])
                        found = swlib.find(state, phrase)
                        if found:
                            break
                    if found and swlib.apply_event(state, phrase, kind):
                        done.append(found['es'])  # the list's spelling, accents included: "tambien" -> también
                    else:
                        missing.append(phrase)
                    i += n
        if done:
            print(f'{"Known" if kind == "known" else "Back to learning"}: {", ".join(dict.fromkeys(done))}')
        if missing:
            print(f'Not in the word list: {", ".join(dict.fromkeys(missing))}')
    return run


def stage_line(state):
    return f'Stage {swlib.stage_for(state)}{" (pinned)" if state.get("stage_pinned") else " (automatic)"}'


def stage(args):
    if args.value is None:  # only shows it, so nothing is saved
        print(stage_line(swlib.load_state()))
        return
    with swlib.editing() as state:
        if args.value == 'auto':
            state['stage_pinned'] = False
        else:
            state['stage'], state['stage_pinned'] = int(args.value), True
    print(stage_line(state))


def pause(value):
    def run(_args):
        with swlib.editing() as state:
            state['paused'] = value
        print('Spanish Weave paused: no Spanish in chat or on websites until you resume.' if value else 'Spanish Weave resumed.')
        print(CHROME_PAUSED if value else CHROME_PICKS_UP)
    return run


def export_cmd(args):
    with swlib.editing() as state:
        logged = export.log_chat_day(state) if args.log_day else 0
        swlib.promote(state)  # today's refill first, so the stored version is the one printed below
        export.mark_exported(state, 'chatgpt' if args.chatgpt else 'claude-ai')
    if args.chatgpt:
        about, respond = export.chatgpt(state)
        limit = export.CHATGPT_LIMIT
        over = [f'The {box} block is {len(text):,} characters, over the {limit:,} limit of the Free and Go plans '
                '(paid plans allow 5,000).'
                for box, text in (('"Custom instructions"', respond), ('"More about you"', about)) if len(text) > limit]
        fits = ' '.join(over) or f'Each fits in {limit:,} characters, the Free and Go limit (paid plans allow 5,000).'
        print('ChatGPT > Settings > Personalization (phone app: Settings > Customize ChatGPT; turn on "Enable '
              f'customization" if it is off). Paste each block in place of what is in its box. {fits}\n')
        print(f'--- "Custom instructions" box (older layout: "How would you like ChatGPT to respond?") '
              f'({len(respond)} characters) ---\n{respond}\n')
        print(f'--- "More about you" box, under About you (older layout: "What would you like ChatGPT to know about '
              f'you?") ({len(about)} characters) ---\n{about}')
    else:
        block = export.claude_ai(state)
        print(f'claude.ai > Settings > "Instructions for Claude" (older layouts: personal preferences). Replace the old '
              f'Spanish Weave block ({len(block)} characters):\n\n{block}')
    if logged:
        print(f'\n(Counted today as chat exposure for {logged} learning words.)')


def log_chat_day(_args):
    with swlib.editing() as state:
        logged = export.log_chat_day(state)
    print(f'Counted today as chat exposure for {logged} learning words (never enough on its own to make a word known).')


def refresh(_args):
    swlib.refresh_exposure()


def question(word, way):
    return f'What does "{word["es"]}" mean?' if way == 'recognize' else f'How do you say "{word["en"]}" in Spanish?'


def answer_line(word):
    return f'{word["es"]} = {word["en"]}, "{word["hint"]}"' + (f' — {swlib.note(word["es"])}' if swlib.note(word['es']) else '')


# Spellings that are other words once an accent or tilde is dropped, beyond the ones in the word list.
OTHER_WORDS = {'ano', 'el', 'tu', 'mi', 'se', 'te', 'de', 'mas', 'aun', 'papa', 'pena'}


def tip(word, given):
    """For a right Spanish answer: the article it got wrong, or the accents it was missing, and whether the spelling
    without them is a different word (si is "if", sí is "yes"; ano is not año)."""
    article = r'^(el|la|los|las|un|una|unos|unas) '
    mine, theirs = re.match(article, swlib.key(word['es'])), re.match(article, swlib.key(given))
    if mine and theirs and mine.group(1) != theirs.group(1):
        if swlib.gender_slip(word['es'], theirs.group(1)):
            return f"  (it's {word['es']}: the ending doesn't give its gender away, so it comes back at the same gap)"
        return f"  (it's {word['es']})"
    typed, spelled = re.sub(article, '', swlib.key(given)), re.sub(article, '', word['es'])
    if typed == swlib.key(spelled):
        return ''
    other = next((w for w in swlib.load_lexicon() if swlib.key(w['es']) == typed), None)
    if other:
        return f'  (spelled {spelled}; {typed} is another word: {other["en"]})'
    return f'  (spelled {spelled}; {typed} is a different word)' if typed in OTHER_WORDS else f'  (spelled {spelled})'


def nothing_due(state):
    """The line for an empty quiz, with when the next words come up."""
    day = swlib.today()
    upcoming = sorted(d for d in (swlib.due_date(w) for w in state['words'] if w['status'] != 'queue') if d and d > day)
    if not upcoming:
        return 'Nothing to review yet: words come up for review the day after you first meet them.'
    n = upcoming.count(upcoming[0])
    return f'Nothing to review today. Next review: {upcoming[0]} ({n} word{"s" if n != 1 else ""}).'


def judge(word, way, ask, say, prefix):
    """Asks one question; returns (verdict, answer), or None to stop. The learner judges answers check() can't."""
    given = ask(f'{prefix}{question(word, way)}  > ')
    if given.strip().lower() in ('q', 'quit'):
        return None
    verdict = swlib.check(word, given, way)
    if verdict is None:  # a synonym or a meaning not on the list: the learner decides
        verdict = ask(f'      {answer_line(word)}. Count yours as right? [y/n] > ').strip().lower().startswith('y')
    say(f'      {"✓" if verdict else "✗"} {answer_line(word)}' + (tip(word, given) if verdict and way == 'produce' else ''))
    return verdict, given


def run_quiz(plan, ask=input, say=print):
    """Asks each (word, way) in plan and records every answer as it comes. Missed words are asked once more at the end,
    after their answers were shown, so the session ends on a successful recall; that second try isn't recorded.
    Returns (right, answered)."""
    if not plan:
        say('Nothing to review today. New words come in as you read; check back tomorrow.')
        return 0, 0
    say(f'Spanish Weave quiz: {len(plan)} word{"s" if len(plan) != 1 else ""}. Accents optional; q to stop.')
    right = answered = 0
    missed = []
    try:
        for n, (word, way) in enumerate(plan, 1):
            result = judge(word, way, ask, say, f'{n}/{len(plan)}  ')
            if result is None:
                break
            hold = result[0] and way == 'produce' and swlib.gender_slip(word['es'], swlib.article_of(result[1]))
            with swlib.editing() as state:
                swlib.review(state, word['es'], result[0], hold=hold)
            right += result[0]
            answered += 1
            if not result[0]:
                missed.append((word, way))
        else:
            if missed:
                say('Once more, the ones you missed (just practice, not recorded):')
                for word, way in missed:
                    if judge(word, way, ask, say, '      ') is None:
                        break
    except EOFError:
        pass
    say(f'Done: {right} of {answered} right. Missed words come back soon; the others come back later each time.')
    return right, answered


def plan_size(words):
    """The number of questions from --plan's words: the first whole number in them ("5", "5 words"), else 5."""
    number = next((int(n) for n in re.findall(r'\d+', ' '.join(words))), 5)
    return min(max(number, 1), 50)


def quiz(args):
    with swlib.editing() as state:
        pass  # promotion runs when this saves, so the plan sees today's statuses and new words
    plan = [(dict(w), swlib.direction(w))
            for w in swlib.due_reviews(state, limit=args.n if args.plan is None else plan_size(args.plan))]
    if not plan:
        print(nothing_due(state))
    elif args.plan is None:
        run_quiz(plan)
    else:
        for n, (word, way) in enumerate(plan, 1):
            print(f'{n}. {way}: {question(word, way)} | answer: {answer_line(word)}')


def record_answer(state, es, result, article=None):
    """Records one quiz answer. Returns (the word, or None when it isn't being learned or known; whether the gender
    hold applied)."""
    found = swlib.find(state, es)
    hold = bool(found and result == 'right' and swlib.gender_slip(found['es'], article))
    return swlib.review(state, es, result == 'right', hold=hold), hold


def recorded(word, result, hold):
    """The line for a recorded answer; called after the save, so it shows the status promotion left."""
    status = {'active': 'learning', 'shaky': 'shaky', 'known': 'known'}[word['status']]
    slip = f' with the wrong article, so same gap again (it\'s {word["es"]})' if hold else ''
    return f'{word["es"]}: {result}{slip}; next review {word["due"]} ({status})'


def review_cmd(args):
    with swlib.editing() as state:
        word, hold = record_answer(state, args.word, args.result, args.article)
    if word is None:
        sys.exit(f'Not a word you are learning or know: {args.word}')
    print(recorded(word, args.result, hold))


ITEM = re.compile(r'([^:]+):(right|wrong)(?::([^:]+))?')


def record_cmd(args):
    """A whole quiz's answers (WORD:right|wrong[:ARTICLE]) in one command and one save, so the quiz needs one
    permission at the end instead of one per answer. Each is recorded as review records it."""
    lines = []
    with swlib.editing() as state:
        for item in args.items:
            m = ITEM.fullmatch(item.strip())
            if not m:
                lines.append(f'Not saved: {item} (expected WORD:right or WORD:wrong, with an optional :ARTICLE)')
            elif m.group(3) and m.group(3) not in swlib.GENDER_OF:
                lines.append(f'Not saved: {item} (the article can be {", ".join(sorted(swlib.GENDER_OF))})')
            else:
                word, hold = record_answer(state, m.group(1), m.group(2), m.group(3))
                lines.append((word, m.group(2), hold) if word else
                             f'Not saved: {item} (not a word you are learning or know)')
    for line in lines:  # after the save, like review's line
        print(line if isinstance(line, str) else recorded(*line))
    if any(isinstance(line, str) for line in lines):
        sys.exit(1)


def item_numbers(text, last):
    """Item numbers from text like "1, 4, 9-12": ranges included, anything past the last item ignored."""
    numbers = []
    for first, end in re.findall(r'(\d+)(?:\s*[-–]\s*(\d+))?', text):
        numbers.extend(range(int(first), min(int(end or first), last) + 1))
    return numbers


def placement_cmd(args):
    with swlib.editing() as state:
        pass
    test = placement.items(state)
    intro = ('Placement test: say which Spanish words you know, meaning you could say what they mean. A few are made '
             'up, and saying yes to one lowers your result, so skip any you are unsure of.')
    if args.items:
        print(intro)
        for n, (word, _) in enumerate(test, 1):
            print(f'{n:2}. {word}')
        return
    finished = True
    if args.answers is not None:
        known = item_numbers(args.answers, len(test))
    else:
        print(intro)
        known = []
        for n, (word, _) in enumerate(test, 1):
            try:
                reply = input(f'{n:2}/{len(test)}  {word}  [y/n] > ').strip().lower()
            except EOFError:
                reply = 'q'
            if reply in ('q', 'quit'):
                finished = False
                break
            if reply.startswith('y'):
                known.append(n)
    guess, real, fake = placement.estimate(state, known)
    print(f'You know {real} of {sum(band is not None for _, band in test)} real words and picked {fake} of '
          f'{len(placement.PSEUDOWORDS)} made-up ones.')
    if fake >= placement.TOO_MANY_FAKES:
        print('That many made-up words means too many answers were guesses for a fair estimate, so nothing was '
              'marked. Take it again and pick only words you could translate.')
        return
    if fake:
        print('Each made-up word you picked lowers the estimate, since it shows some answers were guesses.')
    print(f'Estimate: you know about {guess} of the {len(state["words"])} listed words.')
    if not finished:
        print('The test stopped early, so nothing was marked.')
        return
    if guess == 0:
        print('Nothing to mark: you start from the most common words.')
        return
    apply = args.apply
    if args.answers is None and not args.apply:
        try:
            apply = input('Mark those words as known? [y/N] > ').strip().lower() in ('y', 'yes')
        except EOFError:
            apply = False
    if apply:
        with swlib.editing() as state:
            changed = swlib.seed_known(state, guess)
        print(f'Marked {changed} words known (the top {guess} of the list; words you are learning keep their '
              f'status). Stage {swlib.stage_for(state)}. They come up in the quiz for a quick check over the next four '
              'weeks, and any you miss go back to learning.')


def write_anki(path, text):
    """Writes an Anki export to path (~ is expanded here, so the slash command needs no shell expansion), which may be
    new or an earlier export but nothing else: a symlink, a folder or device, or any other file is left alone, so a
    mistyped or planted --out can't overwrite it. Returns the full path."""
    path = Path(path).expanduser()
    keep = (f'Left {path} alone: it is there and is not an earlier Spanish Weave Anki export. Move it, then run this '
            'again.')
    if path.is_symlink():
        sys.exit(f'Left {path} alone: it is a symlink, so it could point at another file.')
    if path.exists() and not path.is_file():
        sys.exit(keep)
    try:
        if path.exists():
            with open(path, encoding='utf-8', errors='replace') as file:
                if file.readline(200).rstrip('\r\n') != export.ANKI_HEADERS[0]:
                    sys.exit(keep)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o644)
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            file.write(text)
    except OSError as error:
        sys.exit(f'Could not write {path}: {error.strerror or error.__class__.__name__}.')
    return path


def anki_cmd(args):
    with swlib.editing() as state:
        pass
    text = export.anki(state, every=args.all)
    if args.out:
        path = write_anki(args.out, text)
        print(f'Wrote {text.count(chr(10)) - len(export.ANKI_HEADERS)} notes to {path}. In Anki: File > Import, '
              'pick the file (the deck, note type and tags are set by the file).')
    else:
        print(text, end='')


def output_cmd(args):
    if args.value is None:
        on = bool((swlib.load_state().get('prefs') or {}).get('output_practice'))
        print(f'Output practice is {"on" if on else "off"} (output {"off" if on else "on"} to turn it {"off" if on else "on"}).')
        return
    with swlib.editing() as state:
        state.setdefault('prefs', {})['output_practice'] = args.value == 'on'
    print('Output practice on: about every fifth reply ends with a "Your turn" line inviting you to write a little '
          'Spanish.' if args.value == 'on' else 'Output practice off.')


def positive(text):
    """argparse type: a whole number, 1 or more."""
    if not text.isdigit() or int(text) < 1:
        raise argparse.ArgumentTypeError(f'expected a whole number, 1 or more: {text}')
    return int(text)


def bare(*words):
    """argparse type for an option typed without its dashes (export chatgpt, anki all), as slash commands invite.
    choices= would do, but on Python 3.9 it rejects an empty nargs='*' list."""
    def check(text):
        if text not in words:
            raise argparse.ArgumentTypeError(f'expected {" or ".join(words)}, not {text}')
        return text
    return check


def main(argv=None):
    parser = argparse.ArgumentParser(description='Spanish Weave', formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('setup')
    p.add_argument('--gemini-key-file')
    p.add_argument('--user-data-dir', action='append', default=[])
    p.add_argument('--codex', action='store_true')
    p.add_argument('--known-top', type=int, default=0, metavar='N')
    p.add_argument('--sites', choices=['all', 'ask'])
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(run=setup)
    p = sub.add_parser('uninstall')
    p.add_argument('--codex', action='store_true')
    p.add_argument('--user-data-dir', action='append', default=[])
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(run=uninstall)
    sub.add_parser('status').set_defaults(run=status)
    sub.add_parser('check').set_defaults(run=check)
    for name, kind in (('known', 'known'), ('learn', 'asked')):
        p = sub.add_parser(name)
        p.add_argument('words', nargs='*')
        p.set_defaults(run=mark(kind))
    p = sub.add_parser('stage')
    p.add_argument('value', nargs='?', choices=['1', '2', '3', '4', 'auto'], help='leave out to show the stage')
    p.set_defaults(run=stage)
    sub.add_parser('pause').set_defaults(run=pause(True))
    sub.add_parser('resume').set_defaults(run=pause(False))
    sub.add_parser('refresh').set_defaults(run=refresh)
    p = sub.add_parser('export')
    target = p.add_mutually_exclusive_group()
    target.add_argument('--claude-ai', action='store_true')
    target.add_argument('--chatgpt', action='store_true')
    p.add_argument('--log-day', action='store_true', help='also count today as exposure (see log-chat-day)')
    p.add_argument('extra', nargs='*', metavar='chatgpt|claude-ai|log-day', help='the same flags without the dashes',
                   type=bare('chatgpt', 'claude-ai', 'claude.ai', 'log-day'))
    p.set_defaults(run=export_cmd)
    exporter = p
    sub.add_parser('log-chat-day').set_defaults(run=log_chat_day)
    p = sub.add_parser('quiz')
    p.add_argument('-n', type=positive, default=10, help='most words to ask')
    p.add_argument('--plan', nargs='*', metavar='N', help='print N questions with answers instead (default 5)')
    p.set_defaults(run=quiz)
    p = sub.add_parser('review')
    p.add_argument('word')
    p.add_argument('result', choices=['right', 'wrong'])
    p.add_argument('--article', choices=sorted(swlib.GENDER_OF), help='the el/la/un/una the learner used, if not the listed one')
    p.set_defaults(run=review_cmd)
    p = sub.add_parser('record')
    p.add_argument('items', nargs='+', metavar='WORD:right|wrong[:ARTICLE]')
    p.set_defaults(run=record_cmd)
    p = sub.add_parser('placement')
    p.add_argument('--items', action='store_true', help='print the numbered test instead of asking')
    p.add_argument('--answers', metavar='NUMS', help='the item numbers you know, e.g. "1, 4, 9-12"')
    p.add_argument('--apply', action='store_true', help='mark the estimated words known without asking')
    p.set_defaults(run=placement_cmd)
    p = sub.add_parser('anki')
    p.add_argument('--all', action='store_true', help='every listed word, not only the ones you have met')
    p.add_argument('--out', metavar='FILE', help='a new file or an earlier export; nothing else is overwritten')
    p.add_argument('extra', nargs='*', metavar='all', help='the same as --all', type=bare('all'))
    p.set_defaults(run=anki_cmd)
    p = sub.add_parser('output')
    p.add_argument('value', nargs='?', choices=['on', 'off'])
    p.set_defaults(run=output_cmd)
    args = parser.parse_args(argv)
    for word in getattr(args, 'extra', []):  # chatgpt -> --chatgpt, claude.ai -> --claude-ai, all -> --all
        setattr(args, re.sub(r'[-.]', '_', word), True)
    if args.command == 'export' and args.chatgpt and args.claude_ai:
        exporter.error('argument --chatgpt: not allowed with argument --claude-ai')
    try:
        args.run(args)
    except swlib.StateError as error:
        sys.exit(f'Spanish Weave: {state_fix(error)}')
    except swlib.UnsafeHome as error:
        sys.exit(f'Spanish Weave: {error}.')


if __name__ == '__main__':
    main()
