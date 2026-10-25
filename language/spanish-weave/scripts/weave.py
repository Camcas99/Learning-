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
HEAD = 1_000_000  # bytes at the start of a transcript searched for the first prompt (see transcript)
SHORT = 40  # replies with fewer prose words are too short to measure
SCORED = 10_000  # characters of prose at the end of a reply that are scored: enough for the share, fast at any stage
RECALL_EVERY = 3
OUTPUT_EVERY = 5  # with output practice on, every fifth reply invites the user to write a little Spanish
# Most known words listed per tier, so the brief stays small at Stages 3-4 (hundreds of known words).
LIMITS = {'rare': 24, 'some': 60, 'lot': 80}
# Spanish grammar words on no list: several in one reply mean it slipped into Spanish sentences.
# Left out on purpose: words English also uses (son, era, he, has, me, a, no, de, del, la, los, las, su, mi, and todos,
# as in "the TODOs").
GRAMMAR = set("yo tú él ella nosotros nosotras ellos ellas usted ustedes una unos unas eres somos están estamos "
              "estaban estuvo fue fueron sido estoy está tiene tienen tenemos hemos han hizo hace hacen puede pueden "
              "podría debe nuestro nuestra nuestros nuestras estos estas aquel aquella les nos se lo le que por tu voy "
              "donde cual".split())
ACCENTED = re.compile('[áéíóúñü]')  # an off-list word with one of these is Spanish too (counted from Stage 3)
RECALL, GLOSS = re.compile(r'\s*\**recall:', re.I), re.compile(r'\s=\s')  # recall cue and footer gloss lines (see extra)
# Words that are easy to swap in the wrong sense, and the guard for each; a guard is in the brief once any of its
# words is in use. These are the most frequent mis-weavings: "it's ready" is not es listo (that means "is clever").
GUARDS = [
    (('es', 'no es', 'soy'), 'es and soy only for what something is, never a state or place ("it\'s ready" stays English)'),
    (('esto', 'eso'), 'esto and eso only on their own, never before a noun'),
    (('qué', 'cómo', 'dónde', 'quién', 'cuál', 'cuánto', 'por qué'), 'question words only in questions'),
    (('pero',), '"not X but Y" is sino'),
    (('también', 'entonces'), 'también and entonces never for "too" or "so" before an adjective'),
    (('porque', 'desde'), 'porque never for "because of", desde never for "since" meaning because'),
    (('bien',), 'bien never for the filler "Well,"'),
    (('el tiempo',), 'el tiempo never for "this time" (vez) or clock time (hora)'),
    (('para',), 'para never after ask, wait, look or pay, or for a duration'),
    (('antes de', 'después de', 'durante', 'hasta', 'sin'), 'antes de, después de, durante, hasta and sin never before '
                                                             'a clause'),
    (('más',), 'más means more, never and'),
    (('muy', 'mucho'), 'muy before an adjective or adverb, "very much" is mucho'),
    (('si', 'sí'), 'si is if, sí is yes'),
    (('aquí',), 'aquí never for "here\'s"'),
    (('cualquier',), 'cualquier never after not or in a question'),
    (('ya',), 'ya means already, never "just"'),
    (('como',), 'como never for the verb "like"'),
]


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


def guards(state):
    """The usage guards for the words in use, as a parenthetical (empty when none apply)."""
    in_use = {swlib.key(w['es']) for w in swlib.introduced(state)}
    texts = [text for words, text in GUARDS if in_use.intersection(words)]
    if any(re.match(swlib.ARTICLE, es) for es in in_use):
        texts.append('a listed noun brings its own article, never "the el", and a Spanish adjective next to it agrees '
                     '(la idea nueva)')
    return f' ({"; ".join(texts)})' if texts else ''


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
               'around it, like "La prueba pasa ahora." or "Es la mejor opción." Steps stay English; put the Spanish '
               'sentences in the explanation around them. The other sentences stay English with Spanish words swapped in. '
               'At this stage use any common Latin American Spanish the user would follow, not only the lists (ustedes, '
               'never vosotros). ')
    text = (f'Spanish Weave (Stage {stage}): the user is a native English speaker learning Latin American Spanish passively. Write your chat '
            f'reply in English and swap in Spanish words from the lists below: about {target}% of the words in a reply (about '
            f'{round(target * 1.5)} in a 150-word reply{", so most sentences carry one or two" if stage <= 2 else ""}), '
            f'never over {cap}%, at most {per_sentence} in one sentence. Under target is the usual miss, so count as you write. '
            f'{grammar}Use a word only where it means exactly what the English would; otherwise use another from the '
            f'lists{guards(state)}. If a reply runs long on Spanish, cut {"known" if banded else "seen-a-lot"} words first. Plain English for code, '
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
    else:  # without this, models repeat the last recall cue on every turn (from French Weave by Jackie Oliver, MIT)
        text += '\nNo recall cue in this reply: no "Recall:" lines, even if an earlier reply had one.'
    if (state.get('prefs') or {}).get('output_practice'):
        text += ('\nOutput practice is on: if the user\'s message answers your last "Your turn" line, open with one short line '
                 'of feedback (their Spanish, corrected if needed), then answer as usual.')
        if output:
            text += (' In this reply, if the topic allows, end with one optional line inviting the user to write a few words '
                     'of Spanish with a learning word, like: Your turn: how would you say "without the cache"? (sin). '
                     'Skip it in code-heavy, urgent or zero-Spanish answers.')
    return text + '\n' + swlib.HOOK_MARKER  # tells the chat plugin's skill, if it loads here too, to stay out


DEFAULT_SWAPS = 12  # in band mode: the top-ranked known words (connectors and adverbs) written in Spanish every time


def band_line(state):
    n, missing, extra = swlib.known_band(state)
    swaps = [w for w in state['words'] if w['status'] == 'known'][:DEFAULT_SWAPS]
    defaults = ('Default swaps (write the Spanish every time the English word has that meaning): '
                + '; '.join(f'{w["en"]} → {w["es"]}' for w in swaps) + '\n') if swaps else ''
    cut = lambda xs: ', '.join(xs[:swlib.EXCEPTIONS_MAX]) + (f' and {len(xs) - swlib.EXCEPTIONS_MAX} more' if len(xs) > swlib.EXCEPTIONS_MAX else '')
    return defaults + (f'Known (use freely, never gloss): the first {n} words of the Spanish Weave list, the most basic ones'
            + (f', except these not learned yet: {cut(missing)}' if missing else '')
            + (f'; also known: {cut(extra)}' if extra else '') + '.')


def transcript(path):
    """(text of the latest main-thread assistant reply or None, whether the user typed in this chat) from a Claude
    Code transcript. The second is True once a typed prompt shows, False when every marked prompt came from elsewhere
    (see swlib.prompt_kind), None when no prompt is marked (an older Claude Code, or Codex). Only the head, where the
    first prompt is, and the last TAIL bytes are read."""
    with open(path, 'rb') as file:
        size = file.seek(0, 2)
        file.seek(0)
        if size > HEAD + TAIL:
            raws = file.read(HEAD).split(b'\n')[:-1]  # without the cut line
            file.seek(size - TAIL)
            file.readline()  # skip the cut line
            raws += list(file)
        else:
            raws = list(file)
    kinds = set()
    texts = [text for _, text in swlib.replies([raw.decode('utf-8', 'replace') for raw in raws], kinds.add)
             if text.strip()]
    return (texts[-1] if texts else None), ('typed' in kinds if kinds else None)


def last_reply(path):
    """Text of the latest main-thread assistant reply in a Claude Code transcript, or None."""
    return transcript(path)[0]


# How a prompt the user didn't type starts (after the app's leading <system-reminder> blocks). 'start': the first
# prompt of a scheduled task, or of a session another session started; nobody reads those replies as they come.
# 'notice': a notification the app or another session sends into a chat; its reply is read, but it is no turn.
PROMPT_STARTS = {'start': ('<scheduled-task ', 'Background (from the session that started this one):'),
                 'notice': ('<task-notification>', '<side-sessions-event>', '<ci-monitor-event>', '<agent-message ',
                            '<teammate-message ', 'Another Claude session sent a message:')}
REMINDERS = re.compile(r'\s*(?:<system-reminder>.*?</system-reminder>\s*)*', re.S)


def prompt_source(prompt):
    """'start', 'notice' (see PROMPT_STARTS) or None for anything else, such as what the user typed."""
    text = prompt if isinstance(prompt, str) else ''
    text = text[REMINDERS.match(text).end():]
    return next((name for name, starts in PROMPT_STARTS.items() if text.startswith(starts)), None)


def extra(line):
    """True for the recall cue and footer gloss lines (an " = " with a quote after it), in time linear in the line."""
    gloss = GLOSS.search(line)
    return bool(RECALL.match(line) or gloss and '"' in line[gloss.end():])


def share(text, words):
    """(Spanish words, prose words, learning words used, Spanish grammar words off the lists, all Spanish off the
    lists) in a reply. Off-list Spanish is the grammar words plus any other word with an accent, ñ or ü; Stages 3-4
    allow Spanish beyond the lists, so it counts toward their share.

    Code, links, glosses and the recall cue are skipped. Only the last SCORED characters of prose are scored, so a
    huge reply costs no more than a long one (every listed word is a regex pass over the text)."""
    prose = swlib.norm(swlib.CODE.sub(' ', text))
    if len(prose) > SCORED:
        prose = prose[-SCORED:].split(maxsplit=1)[-1]  # without the word the cut may have split
    prose = '\n'.join(line for line in prose.split('\n') if not extra(line))
    total = len(re.findall(r"[^\W\d_]+(?:['-][^\W\d_]+)*", prose))
    spanish = learning = 0
    # Non-overlapping uses, the longest first: "sin embargo" is not also "sin" (swlib.uses).
    measured = [w for w in words if swlib.norm(w['es']) not in swlib.UNMEASURABLE]
    counts, rest = swlib.uses(prose, {w['es']: swlib.pattern(w['es']) for w in measured})
    for word in measured:
        n = counts.get(word['es'], 0)
        spanish += n * len(word['es'].split())
        learning += n if word['status'] != 'known' else 0
    tokens = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", rest)
    grammar = sum(token in GRAMMAR for token in tokens)
    offlist = sum(token in GRAMMAR or bool(ACCENTED.search(token)) for token in tokens)
    return spanish, total, learning, grammar, offlist


def calibration(text, state):
    """One line on how much Spanish the last reply in this chat had, so the next one corrects toward the target. It
    follows the stage brief: Spanish sentences are a slip only at Stages 1-2, Spanish beyond the lists counts from
    Stage 3, and a reply with 2 or more learning words (the brief asks for 2 to 4) is never told to use more."""
    stage = swlib.stage_for(state)
    spanish, total, learning, grammar, offlist = share(text, swlib.introduced(state))
    if total < SHORT:
        return ''
    if stage >= 3:
        spanish += offlist
    target, cap, _ = STAGES[min(stage, 4)]
    percent = 100 * spanish / total
    verdict = ('it slipped into Spanish sentences, so this time write English sentences with only list words in Spanish'
               if stage <= 2 and grammar >= 4 else f'over the {cap}% cap, so use less Spanish this time' if percent > cap
               else f'under the {target}% target, so use more this time unless the topic needs zero Spanish'
               if percent < 0.7 * target and learning < 2 else 'on target')
    return (f'\nYour last reply in this chat was {percent:.0f}% Spanish ({spanish} of {total} words, {learning} '
            f'learning word{"" if learning == 1 else "s"}): {verdict}.')


def next_recall(state, session, typed=False):
    """Every third turn in a chat (1st, 4th, ...): the recall word, shaky first, then active, not yet used here.
    typed records that the user typed in this chat (see session)."""
    if not session:
        return None
    path = swlib.home() / 'sessions.json'
    with swlib.locked('sessions.lock'):
        sessions = swlib.read_json(path, {}) or {}
        entry = sessions.setdefault(session, {'n': 0, 'recalled': []})
        entry['n'] += 1
        entry['t'] = int(time.time())
        if typed:
            entry['typed'] = True
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


def session(session_id):
    """This chat's sessions.json entry: n, how many turns it has had (next_recall counts them), and typed, once the
    user is known to have typed in it, which stays known when that prompt is too far back to read again."""
    return ((swlib.read_json(swlib.home() / 'sessions.json', {}) or {}).get(session_id) or {}) if session_id else {}


def turn(session_id):
    """How many turns this chat has had."""
    return session(session_id).get('n', 0)


def split_args(text, comm):
    """ps's args= text as a list. It loses the boundaries between arguments, so the executable comes from comm= (its
    full path on macOS), which may hold spaces: the desktop app's own claude is under ~/Library/Application Support."""
    if comm and (text + ' ').startswith(comm + ' '):
        return [comm] + text[len(comm):].split()
    return text.split()


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
        ps = lambda *columns: subprocess.run(['ps', *columns, '-p', str(pid)], capture_output=True, text=True,
                                             timeout=5).stdout.strip()
        parent, _, args = ps('-o', 'ppid=', '-o', 'args=').partition(' ')
        return split_args(args.lstrip(), ps('-o', 'comm=')), int(parent)
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
    source = prompt_source(data.get('prompt'))
    reply = typed = None
    if hook:
        # Nobody reads these as they run: a subagent's prompt, the first prompt of a scheduled task or of a session
        # another session started, and later turns of a chat whose transcript shows no typed prompt.
        if data.get('agent_id') or source == 'start':
            return 0
        try:
            reply, typed = transcript(data['transcript_path'])
        except Exception:
            pass  # no transcript yet (a first prompt) or unreadable: the brief alone still helps
    try:
        state = swlib.load_state()
    except Exception as error:  # never block a prompt because of Spanish; Claude Code shows no stderr on exit 0
        reason = error if isinstance(error, (swlib.StateError, swlib.UnsafeHome)) else error.__class__.__name__
        print(f'Spanish Weave: skipped, {reason}; /spanish-weave:status says how to fix it', file=sys.stderr)
        return 0
    if state.get('paused'):
        return 0
    if hook and not typed and session(data.get('session_id')).get('typed'):
        typed = True
    if typed is False:
        return 0
    counted = hook and source != 'notice'  # a notification gets the brief, but no recall cue or "Your turn"
    recall = next_recall(state, data.get('session_id'), typed) if counted else None
    count = turn(data.get('session_id')) if counted else 0
    text = brief(state, exposure(), recall, output=count > 0 and count % OUTPUT_EVERY == 0)
    if hook:
        try:
            text += calibration(reply, state) if reply else ''
        except Exception:
            pass
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
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # in a hook, any other failure also leaves the prompt alone: one line, exit 0
        if '--hook' not in sys.argv[1:]:
            raise
        reason = error if isinstance(error, swlib.UnsafeHome) else error.__class__.__name__  # a lock-file link, say
        print(f'Spanish Weave: skipped ({reason}); run sw.py check', file=sys.stderr)
        sys.exit(0)
