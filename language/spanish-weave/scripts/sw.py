#!/usr/bin/env python3
"""Spanish Weave command line: setup, status, word and stage changes. Python 3.9+, standard library only.

  sw.py setup [--gemini-key-file FILE] [--user-data-dir DIR]... [--known-top N] [--sites all|ask] [--dry-run]
                                                     install the state dir, extension copy and native host;
                                                     --user-data-dir also registers the host for a browser run
                                                     with that --user-data-dir (Chromium looks there);
                                                     --known-top marks the top N lexicon words known unless
                                                     already introduced (40: some basics, 150: simple Spanish);
                                                     --sites: extension on every site (all) or only ones you
                                                     turn on (ask)
  sw.py status                                       stage, word counts, learning words
  sw.py known WORD...                                mark words as known
  sw.py learn WORD...                                put words back in the learning set (shaky)
  sw.py stage N|auto                                 pin the stage (1-4) or let it follow known words
  sw.py pause | resume                               stop or restart Spanish in chat and on websites
  sw.py refresh                                      rescan chat transcripts and apply the promotion rules
  sw.py setup --codex [--dry-run]                    also add the chat hook to Codex CLI (~/.codex or $CODEX_HOME)
  sw.py export [--claude-ai | --chatgpt] [--log-day] paste-ready block for claude.ai preferences or ChatGPT
  sw.py log-chat-day                                 opt-in: count today as exposure for your learning words
  sw.py check                                        verify the state, extension folder and native host
  sw.py quiz [-n N] [--plan [N]]                     spaced-repetition quiz on words that are due (--plan: list
                                                     N questions with answers instead, default 5, for Claude to ask)
  sw.py review WORD right|wrong                      record one quiz answer
  sw.py placement [--items] [--answers NUMS] [--apply]
                                                     2-minute placement test (Yes/No vocabulary test); NUMS like
                                                     "1, 4, 9-12"
  sw.py anki [--all] [--out FILE]                    your words as an Anki import file (tab-separated)
  sw.py output [on|off]                              "Your turn" lines that invite you to write some Spanish
  sw.py uninstall [--codex] [--dry-run]              remove the native host manifests (and the Codex hook)
"""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import swlib  # noqa: E402
import export  # noqa: E402
import placement  # noqa: E402

HOST_NAME = 'com.spanishweave.host'
EXTENSION_ID = 'papkhjkhjagpimlholdmecddkhhhcfje'  # fixed by the "key" in extension/manifest.json


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


def enable_codex_hooks(text):
    """config.toml text with `hooks = true` in its [features] table (added if missing)."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == '[features]'), None)
    if start is None:
        return text.rstrip('\n') + ('\n\n' if text.strip() else '') + '[features]\nhooks = true\n'
    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith('[')), len(lines))
    for i in range(start + 1, end):
        if re.match(r'\s*hooks\s*=', lines[i]):
            lines[i] = 'hooks = true'
            break
    else:
        lines.insert(start + 1, 'hooks = true')
    return '\n'.join(lines) + '\n'


def setup_codex(dry_run):
    codex = swlib.codex_home()
    hooks_path, config_path = codex / 'hooks.json', codex / 'config.toml'
    data = merge_codex_hooks(swlib.read_json(hooks_path, {}) if hooks_path.exists() else {}, codex_command())
    config = enable_codex_hooks(config_path.read_text() if config_path.exists() else '')
    if dry_run:
        print(json.dumps({'codex_hooks': str(hooks_path), 'codex_config': str(config_path), 'command': codex_command()},
                         indent=1))
        return
    if hooks_path.exists() and swlib.read_json(hooks_path) is None:
        sys.exit(f'{hooks_path} is not valid JSON; fix it, then rerun setup --codex.')
    codex.mkdir(parents=True, exist_ok=True)
    for path in (hooks_path, config_path):
        backup = path.with_name(path.name + '.before-spanish-weave')
        if path.exists() and not backup.exists():
            shutil.copy2(path, backup)
    swlib.write_json(hooks_path, data)
    config_path.write_text(config)
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


def setup(args):
    info = plan(args.user_data_dir)
    if sys.version_info < (3, 9):
        sys.exit(f'Spanish Weave needs Python 3.9 or newer; this is {info["python_version"]}.')
    root, home = swlib.PLUGIN_ROOT, swlib.home()
    if not (root / 'extension' / 'manifest.json').exists():
        sys.exit(f'No extension/ folder next to {root / "scripts"}; run setup from a full copy of the repo.')
    key = read_key_file(args.gemini_key_file) if args.gemini_key_file else None
    if args.dry_run:
        print(json.dumps(dict(info, dry_run=True, gemini_key='would be stored' if key else 'not given',
                              known_top=args.known_top, sites=args.sites), indent=1))
        if args.codex:
            setup_codex(True)
        return
    home.mkdir(parents=True, exist_ok=True)
    os.chmod(home, 0o700)
    # Stable copies: the plugin cache path changes on every update, Chrome needs fixed paths.
    for name, ignore in (('extension', shutil.ignore_patterns('test', 'node_modules', 'package.json', 'bun.lock')),
                         ('app/scripts', shutil.ignore_patterns('__pycache__')), ('app/data', None)):
        source = root / ('extension' if name == 'extension' else name.split('/')[1])
        target = home / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, ignore=ignore)
    launcher = home / 'app' / 'sw-host'
    launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{home / "app" / "scripts" / "sw_host.py"}" "$@"\n')
    launcher.chmod(0o755)
    manifest = {'name': HOST_NAME, 'description': 'Spanish Weave word state', 'path': str(launcher), 'type': 'stdio',
                'allowed_origins': [f'chrome-extension://{EXTENSION_ID}/']}
    for directory in host_dirs(args.user_data_dir):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f'{HOST_NAME}.json').write_text(json.dumps(manifest, indent=1) + '\n')
    if key:
        path = home / 'gemini_key'
        path.write_text(key + '\n')
        path.chmod(0o600)
    with swlib.locked():
        if not (home / 'state.json').exists():  # first run: seed known words before the first learning words
            swlib.save_state(swlib.new_state(known_top=args.known_top))
    with swlib.editing() as state:  # later runs: adds new lexicon words, seeds only words not yet introduced
        swlib.seed_known(state, args.known_top)
        if args.sites:
            state.setdefault('prefs', {})['extension_sites'] = args.sites
    if args.codex:
        setup_codex(False)
    print('Spanish Weave is set up.')
    print(f'  word state:  {home / "state.json"} (Stage {swlib.stage_for(state)}, '
          f'{sum(w["status"] == "known" for w in state["words"])} known, '
          f'{sum(w["status"] == "active" for w in state["words"])} learning words)')
    sites = (state.get('prefs') or {}).get('extension_sites', 'all')
    print(f'  extension:   {"every site; turn any off from the toolbar" if sites == "all" else "only sites you turn on"}')
    print(f'  native host: {", ".join(info["host_manifests"])}')
    print(f'  Gemini key:  {"stored for the extension" if key or (home / "gemini_key").exists() else "not stored; paste it in the extension popup"}')
    print('Human steps left (Chrome blocks scripts from doing these):')
    print('  1. Open chrome://extensions and switch on Developer mode (top right).')
    print(f'  2. Click "Load unpacked" and pick: {home / "extension"}')
    print('  3. Pin the Spanish Weave toolbar icon (puzzle piece menu) and click it:')
    if sites == 'all':
        print('     click "Allow all websites" (Chrome asks once; until then it runs only on X).')
    else:
        print('     on each site you want, tick "This site" (Chrome asks for that site).')
    if not key and not (home / 'gemini_key').exists():
        print('     Paste a Gemini API key (https://aistudio.google.com/apikey).')
    print('Chat weaving runs wherever the plugin is enabled; sessions opened from now on pick it up.')


def check(_args):
    """Prints one line per check; exits 1 if any failed."""
    import struct
    import subprocess
    home, ok = swlib.home(), True

    def report(passed, what):
        nonlocal ok
        ok = ok and passed
        print(f'{"ok  " if passed else "FAIL"} {what}')

    state = swlib.load_state(create=False)
    report(state is not None, f'word state at {home / "state.json"}' + (f' (Stage {swlib.stage_for(state)})' if state else ''))
    report((home / 'extension' / 'manifest.json').exists(), f'extension folder for Load unpacked: {home / "extension"}')
    for directory in host_dirs():
        path = directory / f'{HOST_NAME}.json'
        manifest = swlib.read_json(path)
        report(bool(manifest) and manifest.get('allowed_origins') == [f'chrome-extension://{EXTENSION_ID}/'],
               f'native host manifest {path}')
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


def uninstall(args):
    if args.codex:
        path = swlib.codex_home() / 'hooks.json'
        data = swlib.read_json(path, {}) or {}
        groups = (data.get('hooks') or {}).get('UserPromptSubmit') or []
        kept = [g for g in ({**g, 'hooks': [h for h in g.get('hooks', []) if not is_ours(h)]} for g in groups) if g['hooks']]
        if len(kept) != len(groups) or sum(len(g['hooks']) for g in kept) != sum(len(g.get('hooks', [])) for g in groups):
            print(('would remove' if args.dry_run else 'removed') + f' the Spanish Weave hook from {path}')
            if not args.dry_run:
                data['hooks']['UserPromptSubmit'] = kept
                swlib.write_json(path, data)
    for directory in host_dirs():
        path = directory / f'{HOST_NAME}.json'
        if path.exists():
            print(('would remove ' if args.dry_run else 'removed ') + str(path))
            if not args.dry_run:
                path.unlink()
    print(f'Your word state stays in {swlib.home()}; delete that folder to start over.')


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


def mark(kind):
    def run(args):
        missing, done = [], []
        with swlib.editing() as state:
            for chunk in (c for arg in args.words for c in arg.split(',')):
                chunk = chunk.strip()
                # "tal vez" is one word; "y pero" is two.
                for word in [chunk] if swlib.find(state, chunk) or ' ' not in chunk else chunk.split():
                    found = swlib.find(state, word)
                    if found and swlib.apply_event(state, word, kind):
                        done.append(found['es'])  # the list's spelling, accents included: "tambien" -> también
                    else:
                        missing.append(word)
        if done:
            print(f'{"Known" if kind == "known" else "Back to learning"}: {", ".join(done)}')
        if missing:
            print(f'Not in the word list: {", ".join(missing)}')
    return run


def stage(args):
    with swlib.editing() as state:
        if args.value == 'auto':
            state['stage_pinned'] = False
        else:
            state['stage'], state['stage_pinned'] = int(args.value), True
    print(f'Stage {swlib.stage_for(state)}{" (pinned)" if state["stage_pinned"] else " (automatic)"}')


def pause(value):
    def run(_args):
        with swlib.editing() as state:
            state['paused'] = value
        print('Spanish Weave paused: no Spanish in chat or on websites until you resume.' if value else 'Spanish Weave resumed.')
    return run


def export_cmd(args):
    with swlib.editing() as state:
        logged = export.log_chat_day(state) if args.log_day else 0
        export.mark_exported(state, 'chatgpt' if args.chatgpt else 'claude-ai')
    if args.chatgpt:
        about, respond = export.chatgpt(state)
        print(f'ChatGPT > Settings > Personalization > Custom instructions. Each field holds {export.CHATGPT_LIMIT} '
              'characters on every plan.\n')
        print(f'--- "What would you like ChatGPT to know about you?" ({len(about)} characters) ---\n{about}\n')
        print(f'--- "How would you like ChatGPT to respond?" ({len(respond)} characters) ---\n{respond}')
    else:
        block = export.claude_ai(state)
        print(f'claude.ai > Settings > Profile > personal preferences. Replace the old Spanish Weave block '
              f'({len(block)} characters):\n\n{block}')
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
            with swlib.editing() as state:
                swlib.review(state, word['es'], result[0])
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


def review_cmd(args):
    with swlib.editing() as state:
        word = swlib.review(state, args.word, args.result == 'right')
    if word is None:
        sys.exit(f'Not a word you are learning or know: {args.word}')
    status = {'active': 'learning', 'shaky': 'shaky', 'known': 'known'}[word['status']]
    print(f'{word["es"]}: {args.result}; next review {word["due"]} ({status})')


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


def anki_cmd(args):
    with swlib.editing() as state:
        pass
    text = export.anki(state, every=args.all)
    if args.out:
        Path(args.out).expanduser().write_text(text, encoding='utf-8')
        print(f'Wrote {text.count(chr(10)) - len(export.ANKI_HEADERS)} notes to {args.out}. In Anki: File > Import, '
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
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(run=uninstall)
    sub.add_parser('status').set_defaults(run=status)
    sub.add_parser('check').set_defaults(run=check)
    for name, kind in (('known', 'known'), ('learn', 'asked')):
        p = sub.add_parser(name)
        p.add_argument('words', nargs='+')
        p.set_defaults(run=mark(kind))
    p = sub.add_parser('stage')
    p.add_argument('value', choices=['1', '2', '3', '4', 'auto'])
    p.set_defaults(run=stage)
    sub.add_parser('pause').set_defaults(run=pause(True))
    sub.add_parser('resume').set_defaults(run=pause(False))
    sub.add_parser('refresh').set_defaults(run=refresh)
    p = sub.add_parser('export')
    target = p.add_mutually_exclusive_group()
    target.add_argument('--claude-ai', action='store_true')
    target.add_argument('--chatgpt', action='store_true')
    p.add_argument('--log-day', action='store_true', help='also count today as exposure (see log-chat-day)')
    p.set_defaults(run=export_cmd)
    sub.add_parser('log-chat-day').set_defaults(run=log_chat_day)
    p = sub.add_parser('quiz')
    p.add_argument('-n', type=positive, default=10, help='most words to ask')
    p.add_argument('--plan', nargs='*', metavar='N', help='print N questions with answers instead (default 5)')
    p.set_defaults(run=quiz)
    p = sub.add_parser('review')
    p.add_argument('word')
    p.add_argument('result', choices=['right', 'wrong'])
    p.set_defaults(run=review_cmd)
    p = sub.add_parser('placement')
    p.add_argument('--items', action='store_true', help='print the numbered test instead of asking')
    p.add_argument('--answers', metavar='NUMS', help='the item numbers you know, e.g. "1, 4, 9-12"')
    p.add_argument('--apply', action='store_true', help='mark the estimated words known without asking')
    p.set_defaults(run=placement_cmd)
    p = sub.add_parser('anki')
    p.add_argument('--all', action='store_true', help='every listed word, not only the ones you have met')
    p.add_argument('--out', metavar='FILE')
    p.set_defaults(run=anki_cmd)
    p = sub.add_parser('output')
    p.add_argument('value', nargs='?', choices=['on', 'off'])
    p.set_defaults(run=output_cmd)
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == '__main__':
    main()
