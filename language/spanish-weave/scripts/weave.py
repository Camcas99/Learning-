#!/usr/bin/env python3
"""UserPromptSubmit hook: prints a short Spanish Weave brief as additional context for the next reply.

Usage: weave.py --hook   (reads the hook JSON on stdin, prints hook JSON)
       weave.py          (prints the plain brief, for checking)
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import swlib  # noqa: E402

STALE = 30 * 60  # refresh chat exposure in the background when the index is older than this
# Stage: (target % of words in Spanish, cap %, max Spanish words in one sentence).
STAGES = {1: (6, 10, 2), 2: (12, 20, 4), 3: (25, 35, 4), 4: (40, 55, 4)}
LOT, SOME = (6, 30), (3, 10)  # chat exposure (distinct days, replies) for the "seen a lot" and "sometimes" tiers
TAIL = 2_000_000  # bytes at the end of a transcript searched for the last reply
SHORT = 40  # replies with fewer prose words are too short to measure
RECALL_EVERY = 3
OUTPUT_EVERY = 5  # with output practice on, every fifth reply invites the user to write a little Spanish
# Most known words listed per tier, so the brief stays small at Stages 3-4 (hundreds of known words).
LIMITS = {'rare': 24, 'some': 60, 'lot': 80}
# Spanish grammar words on no list: several in one reply mean it slipped into Spanish sentences.
# Left out on purpose: words English also uses (son, era, he, has, me, a, no, de, del, la, los, las, su, mi).
GRAMMAR = set("yo tú él ella nosotros nosotras ellos ellas usted ustedes una unos unas eres somos están estamos "
              "estaban estuvo fue fueron sido estoy está tiene tienen tenemos hemos han hizo hace hacen puede pueden "
              "podría debe nuestro nuestra nuestros nuestras estos estas aquel aquella les nos se lo le que por tu voy "
              "todos donde cual".split())
EXTRA = re.compile(r'\s*(?:\**recall:|.*\s=\s.*")', re.I)  # recall cue and footer gloss lines


def exposure():
    """Per-word chat exposure; starts a background refresh when the index is stale or missing."""
    path = swlib.home() / 'exposure.json'
    data = swlib.read_json(path, {}) or {}
    try:
        fresh = time.time() - path.stat().st_mtime < STALE
    except OSError:
        fresh = False
    if not fresh and not os.environ.get('SPANISH_WEAVE_NO_REFRESH'):
        subprocess.Popen([sys.executable, str(Path(__file__).resolve().with_name('sw.py')), 'refresh'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    return data.get('words', {})


def tier(word, seen):
    """'learn' for active and shaky words; known words by chat exposure: 'lot', 'some' or 'rare' (uncountable: 'some')."""
    if word['status'] != 'known':
        return 'learn'
    count = seen.get(word['es'])
    if count is None:
        return 'some'
    days, replies = len(count['days']), count['n']
    if days >= LOT[0] and replies >= LOT[1]:
        return 'lot'
    return 'some' if days >= SOME[0] and replies >= SOME[1] else 'rare'


def brief(state, seen, recall=None, output=False):
    stage = swlib.stage_for(state)
    target, cap, per_sentence = STAGES[min(stage, 4)]
    entry = lambda w: w['es'] if w['status'] == 'known' else (f'{w["es"]} = {w["en"]}' + (f', "{w["hint"]}"' if stage <= 2 else '')
                                                              + (f' — {swlib.note(w["es"])}' if swlib.note(w['es']) else ''))
    words = sorted(swlib.introduced(state), key=lambda w: (w['status'] != 'shaky', -seen.get(w['es'], {}).get('n', 0)))
    swap = lambda w: f'{w["en"]} → {w["es"]}'
    def group(name, show=entry):
        picked = [w for w in words if tier(w, seen) == name]
        if name == 'rare':  # least exposure first, so fading words get pushed back in
            picked.sort(key=lambda w: seen.get(w['es'], {}).get('n', 0))
        return '; '.join(show(w) for w in picked[:LIMITS.get(name)]) or 'none'
    banded = sum(w['status'] == 'known' for w in state['words']) >= swlib.COLLAPSE_AT
    grammar = ('Every sentence stays an English sentence with Spanish words swapped in, like "The build passes ahora, '
               'pero the cache is stale, entonces I cleared it." Never a Spanish sentence or clause, and no Spanish outside these '
               'lists (no Spanish articles, verbs or numbers); if a sentence starts turning Spanish, rewrite it in English. '
               if stage < 3 else
               f'About {"one sentence in five" if stage == 3 else "two sentences in five"} should be fully Spanish '
               f'({"2" if stage == 3 else "4"} in a ten-sentence reply): short, simple and guessable from the English '
               'around it, like "La prueba pasa ahora." or "Es la mejor opción." Steps stay English, so put '
               'the Spanish sentences in the explanation, summary and advice around them. The other sentences stay English '
               'with Spanish words swapped in. At this stage use any common Spanish word the user would follow, not only '
               'the lists. ')
    text = (f'Spanish Weave (Stage {stage}): the user is a native English speaker learning Latin American Spanish passively. Write your chat '
            f'reply in English and swap in Spanish words from the lists below: about {target}% of the words in a reply (about '
            f'{round(target * 1.5)} in a 150-word reply{", so most sentences carry one or two" if stage <= 2 else ""}), '
            f'never over {cap}%, at most {per_sentence} in one sentence. Under target is the usual miss, so count as you write. '
            f'{grammar}Use a word only where it means exactly what the English word would mean there; where one doesn\'t '
            'fit, use another from the lists instead (para never after ask, wait or thank, or for a duration; antes de, '
            'después de and durante only before a noun; más means more, never and; muy only before an adjective, '
            f'"very much" is mucho; si is if, sí is yes). If a reply runs long on Spanish, cut {"known" if banded else "seen-a-lot"} words first. Plain English for code, '
            'commands, paths, numbers, names, IDs, option letters and steps the user will follow, and no Spanish right before '
            'a path; zero Spanish, and no recall cue, for health, medication, legal, money, safety, emergency, driving or '
            'urgent topics. Spanish goes only in your chat reply: never in files, code, configs, commit or PR text, messages '
            'to other agents, subagent prompts, or drafts and documents meant to be shared. No bold on Spanish words and no '
            'inline glosses. End the reply with one footer line glossing the learning words you used that are not glossed '
            'earlier in this chat, at most 8, like: (sin = without, "seen"); keep a word\'s note (after the —) in its gloss; '
            'nothing to gloss, no footer.\n'
            f'Learning now (use 2 to 4 per reply): {group("learn")}\n'
            f'Rarely seen (pepper in a couple per reply where the sentence makes the meaning obvious): {group("rare")}\n'
            + (band_line(state) if banded else
               f'Seen sometimes (about 2 in 3 places one fits): {group("some")}\n'
               f'Seen a lot, as default swaps (write the Spanish every time the English word has that meaning): {group("lot", swap)}'))
    if recall:
        text += (f'\nIf this reply is longer than a few sentences, open it with "Recall: {recall["es"]}?" on its own line '
                 f'and end it, after the footer, with: Recall: {recall["es"]} = {recall["en"]}, "{recall["hint"]}"')
    if (state.get('prefs') or {}).get('output_practice'):
        text += ('\nOutput practice is on: if the user\'s message answers your last "Your turn" line, open with one short line '
                 'of feedback (their Spanish, corrected if needed), then answer as usual.')
        if output:
            text += (' In this reply, if the topic allows, end with one optional line inviting the user to write a few words '
                     'of Spanish with a learning word, like: Your turn: how would you say "without the cache"? (sin). '
                     'Skip it in code-heavy, urgent or zero-Spanish answers.')
    return text


DEFAULT_SWAPS = 12  # in band mode: the top-ranked known words (connectors and adverbs) written in Spanish every time


def band_line(state):
    n, missing, extra = swlib.known_band(state)
    swaps = [w for w in state['words'] if w['status'] == 'known'][:DEFAULT_SWAPS]
    defaults = ('Default swaps (write the Spanish every time the English word has that meaning): '
                + '; '.join(f'{w["en"]} → {w["es"]}' for w in swaps) + '\n') if swaps else ''
    cut = lambda xs: ', '.join(xs[:swlib.EXCEPTIONS_MAX]) + (f' and {len(xs) - swlib.EXCEPTIONS_MAX} more' if len(xs) > swlib.EXCEPTIONS_MAX else '')
    return defaults + (f'Known (use freely, never gloss): roughly the {n} most common Spanish words and phrases'
            + (f', except these not learned yet: {cut(missing)}' if missing else '')
            + (f'; also known: {cut(extra)}' if extra else '') + '.')


def last_reply(path):
    """Text of the latest main-thread assistant reply in a Claude Code transcript, or None."""
    with open(path, 'rb') as file:
        size = file.seek(0, 2)
        file.seek(max(0, size - TAIL))
        if size > TAIL:
            file.readline()  # skip the cut line
        lines = [raw.decode('utf-8', 'replace') for raw in file]
    texts = [text for _, text in swlib.replies(lines) if text.strip()]
    return texts[-1] if texts else None


def share(text, words):
    """(Spanish words, prose words, learning words used, Spanish grammar words off the lists) in a reply.

    Code, links, glosses and the recall cue are skipped."""
    prose = swlib.norm(swlib.CODE.sub(' ', text))
    prose = '\n'.join(line for line in prose.split('\n') if not EXTRA.match(line))
    total = len(re.findall(r"[^\W\d_]+(?:['-][^\W\d_]+)*", prose))
    spanish = learning = 0
    rest = prose
    # Longest first, each match removed before the next search: "faire attention" is not also "faire".
    for word in sorted(words, key=lambda w: -len(w['es'])):
        if swlib.norm(word['es']) not in swlib.UNMEASURABLE:
            regex = swlib.pattern(word['es'])
            uses = len(regex.findall(rest))
            spanish += uses * len(word['es'].split())
            learning += uses if word['status'] != 'known' else 0
            rest = regex.sub(' ', rest)
    grammar = sum(token in GRAMMAR for token in re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", rest))
    return spanish, total, learning, grammar


def calibration(text, state):
    """One line on how much Spanish the last reply in this chat had, so the next one corrects toward the target."""
    spanish, total, learning, grammar = share(text, swlib.introduced(state))
    if total < SHORT:
        return ''
    target, cap, _ = STAGES[min(swlib.stage_for(state), 4)]
    percent = 100 * spanish / total
    verdict = ('it slipped into Spanish sentences, so this time write English sentences with only list words in Spanish'
               if grammar >= 4 else f'over the {cap}% cap, so use less Spanish this time' if percent > cap else
               f'under the {target}% target, so use more this time unless the topic needs zero Spanish'
               if percent < 0.7 * target else 'on target')
    return (f'\nYour last reply in this chat was {percent:.0f}% Spanish ({spanish} of {total} words, {learning} '
            f'learning word{"" if learning == 1 else "s"}): {verdict}.')


def next_recall(state, session):
    """Every third turn in a chat (1st, 4th, ...): the recall word, shaky first, then active, not yet used here."""
    if not session:
        return None
    path = swlib.home() / 'sessions.json'
    with swlib.locked('sessions.lock'):
        sessions = swlib.read_json(path, {}) or {}
        entry = sessions.setdefault(session, {'n': 0, 'recalled': []})
        entry['n'] += 1
        entry['t'] = int(time.time())
        pick = None
        if (entry['n'] - 1) % RECALL_EVERY == 0:
            fresh = lambda w: w['es'] not in entry['recalled']
            learning = [w for w in swlib.introduced(state) if w['status'] in ('shaky', 'active') and fresh(w)]
            due = [w for w in swlib.due_reviews(state, limit=len(state['words'])) if w['status'] == 'known' and fresh(w)]
            # Every other cue goes to a known word whose spaced review is due, so known words stay known.
            first, then = (due, learning) if len(entry['recalled']) % 2 else (learning, due)
            pick = next(iter(first + then), None)
            if pick:
                entry['recalled'].append(pick['es'])
        if len(sessions) > 200:  # keep the newest chats only
            sessions = dict(sorted(sessions.items(), key=lambda kv: kv[1].get('t', 0))[-200:])
        swlib.write_json(path, sessions)
    return pick


def turn(session):
    """How many prompts this chat has had (next_recall counts them)."""
    return ((swlib.read_json(swlib.home() / 'sessions.json', {}) or {}).get(session) or {}).get('n', 0) if session else 0


def process_args(pid):
    """Command line of a process as a list (Linux /proc, else ps), and its parent pid."""
    try:
        with open(f'/proc/{pid}/cmdline', 'rb') as file:
            args = [a.decode('utf-8', 'replace') for a in file.read().split(b'\0') if a]
        with open(f'/proc/{pid}/stat') as file:
            parent = int(file.read().rsplit(')', 1)[1].split()[1])
        return args, parent
    except (OSError, ValueError, IndexError):
        pass
    try:
        out = subprocess.run(['ps', '-o', 'ppid=', '-o', 'args=', '-p', str(pid)], capture_output=True, text=True,
                             timeout=5).stdout.strip()
        parent, _, args = out.partition(' ')
        return args.split(), int(parent)
    except (OSError, ValueError, subprocess.SubprocessError):
        return [], 0


def codex_exec(pid=None):
    """True when a `codex exec` process starts this hook (directly or through a shell)."""
    pid = pid or os.getppid()
    for _ in range(3):
        args, parent = process_args(pid)
        if args and os.path.basename(args[0]).startswith('codex'):
            return 'exec' in args[1:] or 'e' in args[1:2]
        if parent <= 1:
            break
        pid = parent
    return False


def is_claude(args):
    """Claude Code's own process: `claude`, the native build under .../claude/versions/<version>, or node cli.js."""
    return bool(args) and (os.path.basename(args[0]) == 'claude' or '/claude/versions/' in args[0]
                           or any(os.path.basename(a) == 'cli.js' for a in args[:2]))


def claude_args(pid=None):
    """Command line of the Claude Code process that started this hook (directly or through a shell), or []."""
    pid = pid or os.getppid()
    for _ in range(3):
        args, parent = process_args(pid)
        if is_claude(args):
            return args
        if parent <= 1:
            break
        pid = parent
    return []


def one_shot(args):
    """True for a one-shot scripted `claude -p` run. Chat hosts also use --print (Remote Control, claude.ai/code,
    desktop and IDE hosts run `claude --print --sdk-url ... --input-format stream-json`), so those weave."""
    printing = any(a in ('-p', '--print') for a in args)
    streaming = any(a == '--sdk-url' or a.startswith('--sdk-url=') or a == '--input-format=stream-json' or
                    (a == '--input-format' and i + 1 < len(args) and args[i + 1] == 'stream-json')
                    for i, a in enumerate(args))
    return printing and not streaming


def interactive(env=None, data=None, exec_check=codex_exec, args_check=claude_args):
    """Weave by default; stay silent only in clear one-shot scripted runs, whose output must never get Spanish.

    Claude Code: skip `claude -p` without --sdk-url / --input-format stream-json (see one_shot), and Agent SDK
    library scripts (CLAUDE_CODE_ENTRYPOINT sdk-ts or sdk-py). Codex (its hook input has a turn_id): skip under
    `codex exec`; the Codex TUI runs hooks from its app-server instead. SPANISH_WEAVE_FORCE=1 weaves anyway;
    SPANISH_WEAVE_OFF=1 never weaves."""
    env = os.environ if env is None else env
    if env.get('SPANISH_WEAVE_OFF') == '1':
        return False
    if env.get('SPANISH_WEAVE_FORCE') == '1':
        return True
    if 'turn_id' in (data or {}):
        return not exec_check()
    if env.get('CLAUDE_CODE_ENTRYPOINT') in ('sdk-ts', 'sdk-py'):
        return False
    return not one_shot(args_check())


STALE_EXPORT_DAYS = 7


def export_notice(state, now=None):
    """Once per export: a nudge when a pasted claude.ai / ChatGPT block is over a week behind the word state."""
    exported = state.get('exported') or {}
    if not exported.get('at') or exported.get('noticed') or exported.get('version') == swlib.version(state):
        return None
    now = now or time.time()
    if now - exported['at'] < STALE_EXPORT_DAYS * 86400:
        return None
    with swlib.editing() as fresh:
        fresh.setdefault('exported', {})['noticed'] = True
    return ('Spanish Weave: the block you pasted into claude.ai or ChatGPT is over a week behind your word list. '
            'Run /spanish-weave:export to refresh it.')


def main(argv):
    hook = '--hook' in argv
    data = {}
    if hook:
        try:
            data = json.load(sys.stdin)
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if not interactive(data=data):
            return 0  # scripted run: no brief at all
    try:
        state = swlib.load_state()
    except Exception as error:  # never block a prompt because of Spanish
        print(f'Spanish Weave: state unreadable ({error.__class__.__name__}); run /spanish-weave:status', file=sys.stderr)
        return 0
    if state.get('paused'):
        return 0
    recall = next_recall(state, data.get('session_id')) if hook else None
    count = turn(data.get('session_id')) if hook else 0
    text = brief(state, exposure(), recall, output=count > 0 and count % OUTPUT_EVERY == 0)
    if hook:
        try:
            reply = last_reply(data['transcript_path'])
            text += calibration(reply, state) if reply else ''
        except Exception:
            pass  # no transcript yet or unreadable: the brief alone still helps
        out = {'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': text}}
        try:
            notice = export_notice(state)
        except Exception:
            notice = None
        if notice:
            out['systemMessage'] = notice  # shown to the user, outside the brief
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
