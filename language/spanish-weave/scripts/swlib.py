"""Spanish Weave shared state: word statuses, stage, chat exposure, extension events.

Python 3.9+ standard library only. One state directory per user (SPANISH_WEAVE_HOME, default ~/.spanish-weave)
holds everything; the Claude Code hook, the slash commands and the Chrome native messaging host all read and
write it through this module.

Statuses: queue -> active -> known, with shaky as the penalty box (see README "How words advance").
"""
import contextlib
import csv
import datetime as dt
import errno
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import unicodedata

try:
    import fcntl
except ImportError:  # Windows: no locking (untested platform)
    fcntl = None

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
LEXICON = PLUGIN_ROOT / 'data' / 'lexicon.csv'
NOTES = PLUGIN_ROOT / 'data' / 'notes.csv'

# ---- promotion rules (documented in README "How words advance") ----
WINDOW = 20             # most learning words (active plus shaky) at once
NEW_PER_DAY = 5         # new words per day, including the first day
SHAKY_BLOCK = 5         # no new words while this many or more are shaky
GRADUATE_DAYS = 3       # active -> known: exposure days needed, and length of the clean streak
SHAKY_DAYS = 7          # shaky -> known: days with no new flip, asked or peek, and a real sighting since the last one
PEEK_WINDOW = 7         # known -> shaky: peeked on 2 different days within this many days, both since it became known
ASSUMED_WEIGHT = 1      # a day with only opt-in "assumed" exposure (sw.py log-chat-day) counts this much
STAGES = [(400, 4), (150, 3), (40, 2)]  # (known words, stage): first match wins; otherwise Stage 1

# ---- spaced review: the quiz (README "Quiz yourself") ----
INTERVALS = [1, 3, 7, 14, 30, 60, 120]  # days to a word's next review, by box; each right answer moves it up a box
PRODUCE_AFTER = 2      # right answers in a row before the quiz asks for the Spanish (production) instead of the meaning
KNOWN_BOX = {'graduated': 2, 'recovered': 1, 'marked': 3}  # box a word starts in when it becomes known
FIRST_QUIZ_DAYS = 1    # a new learning word is first quizzed this many days after it arrives
SEED_SPREAD = 28       # words seeded known (setup, placement) get a first check spread over this many days


# Same spelling as an English word with another meaning, so Spanish use can't be told apart in English prose:
# never counted. (Words English borrowed with the same meaning, like gratis or loco, still count.)
UNMEASURABLE = {'solo', 'mayor', 'sensible', 'tan', 'resolver'}
DETERMINER = (r"(?:el|la|los|las|un|una|unos|unas|del|al|este|esta|estos|estas|ese|esa|esos|esas|mi|mis|tu|tus|su|sus"
              r"|nuestro|nuestra|nuestros|nuestras)\s+")
ARTICLE = r"(?:el|la|los|las) "
# Lookbehinds for an English determiner: "the algo" and "a TODO" are English, "algo" alone is Spanish.
ENGLISH_DETERMINER = ''.join(rf'(?<!\b{d} )' for d in ('a', 'an', 'the', 'this', 'that', 'our', 'your', 'my', 'its',
                                                       'any', 'each', 'every', 'one'))
# Spanish words that English also uses: (extra lookbehind, extra lookahead) that skip the English use.
SPECIAL = {
    'y': (r'(?<!\bx and )(?<!\bx, )', r'(?!\s*[=<>+*/^-])(?!\s+(?:axis|axes|coordinates?|values?|positions?|offsets?)\b)'),
    'o': ('', r'(?!\s*\()'),                                    # O(n)
    'sin': ('', r'(?!\s*\()'),                                  # sin(x)
    'es': ('', r'(?!\s*(?:modules?\b|\d))'),                    # ES modules, ES 2020
    'en': ('', r'(?!\s+(?:route|masse|dash|passant|bloc|suite)\b)'),
    'todo': (ENGLISH_DETERMINER, r'(?!\s*[:(])(?!\s+(?:lists?|apps?|items?|comments?)\b)'),
    # "the TODOs", "3 todos left", "todos.md" are English; "todos" alone is Spanish.
    'todos': (ENGLISH_DETERMINER + ''.join(rf'(?<!\b{d} )' for d in (
        'these', 'those', 'some', 'all', 'two', 'three', 'few', 'several', 'many', 'more', 'open', 'remaining', 'pending',
        'outstanding', 'new', 'old', 'any')) + r'(?<!\d )',
        r'(?!\.\w)(?!\s*[:(])(?!\s+(?:lists?|apps?|items?|comments?|left|remain(?:ing)?|in)\b)'),
    'algo': (ENGLISH_DETERMINER, ''),
}
CODE = re.compile(r"```.*?```|`[^`\n]*`|https?://\S+", re.S)
DEDUPE_DAYS = 45


def home():
    """The state dir: SPANISH_WEAVE_HOME, else the dir this copy was installed into by setup (<home>/app/scripts),
    else ~/.spanish-weave."""
    if os.environ.get('SPANISH_WEAVE_HOME'):
        return Path(os.environ['SPANISH_WEAVE_HOME']).expanduser()
    if PLUGIN_ROOT.name == 'app' and (PLUGIN_ROOT.parent / 'state.json').exists():
        return PLUGIN_ROOT.parent
    return Path.home() / '.spanish-weave'


def today():
    return dt.date.today().isoformat()


def days_between(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def norm(text):
    return unicodedata.normalize('NFC', str(text)).replace('’', "'").replace('‘', "'").lower().strip()


def key(es):
    return re.sub(r'\s+', ' ', norm(es))


def load_lexicon(path=LEXICON):
    with open(path, encoding='utf-8', newline='') as file:
        rows = [r for r in csv.DictReader(file) if (r.get('es') or '').strip()]
    seen, out = set(), []
    for r in rows:
        k = key(r['es'])
        if k not in seen:
            seen.add(k)
            out.append({'es': r['es'].strip(), 'en': r['en'].strip(), 'hint': r['hint'].strip()})
    return out


# ---- files ----

class UnsafeHome(Exception):
    """The state dir can't be trusted: another user owns it or can write to it, a lock file in it is a symlink, or it is
    someone else's folder. Nothing is read from it or written to it until that is fixed; the message says how."""


# What setup, the hook, the commands and the native host keep in the state dir, besides the extension and app copies.
OWN_FILES = {'state.json', 'install.json', 'exposure.json', 'sessions.json', 'state.lock', 'exposure.lock',
             'sessions.lock', 'gemini_key'}


def os_junk(name):
    """Files Finder, Windows or macOS on shared drives leave in any folder they show: never the person's own."""
    return name in ('.DS_Store', 'Thumbs.db', 'desktop.ini') or name.startswith('._')


def own_extension(directory):
    """True when directory/extension is a copy of Spanish Weave's extension (its manifest names it)."""
    manifest = read_json(Path(directory) / 'extension' / 'manifest.json')
    return isinstance(manifest, dict) and manifest.get('name') == 'Spanish Weave'


def own_app(directory):
    """True when directory/app is setup's copy of the scripts."""
    return (Path(directory) / 'app' / 'scripts' / 'sw.py').is_file()


def foreign(directory):
    """True when directory is a folder that holds other things (OS junk aside) and nothing of Spanish Weave's: someone
    else's, so no state file is created in it and setup never takes it over."""
    try:
        names = {p.name for p in Path(directory).iterdir() if not os_junk(p.name)}
    except (FileNotFoundError, NotADirectoryError):
        return False
    return bool(names) and not names & OWN_FILES and not own_extension(directory) and not own_app(directory)


def check_ours(directory):
    """Raises UnsafeHome when directory is foreign: the prompt hook runs before setup, and a state.json it left in
    someone's folder would make setup take that folder for its own."""
    if foreign(directory):
        raise UnsafeHome(f'{directory} is not a Spanish Weave folder: it holds other files and none of Spanish Weave\'s, '
                         'so nothing was written there; set SPANISH_WEAVE_HOME to a new or empty folder')


def check_owner(directory):
    """Raises UnsafeHome when directory (a symlinked one is followed) belongs to another user or anyone can write to
    it: whoever can write there could plant lock-file links, swap the native host or put words in Claude's context.
    Group-writable is allowed."""
    info = os.stat(directory)
    if hasattr(os, 'getuid') and info.st_uid != os.getuid():
        raise UnsafeHome(f'{directory} belongs to another user; set SPANISH_WEAVE_HOME to a folder of your own')
    if info.st_mode & 0o002:
        raise UnsafeHome(f'any user can write to {directory}; run chmod o-w "{directory}" or pick another folder')


def write_text(path, text):
    """Writes text atomically: a temp file in the same folder, then a rename, so a crash never leaves the file half
    written. A symlinked path keeps its link (dotfiles setups link ~/.codex files): the file it points to is replaced.
    An existing file keeps its mode; a new one is 0600."""
    path = Path(path)
    target = Path(os.path.realpath(path)) if path.is_symlink() else path
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=target.parent, delete=False, encoding='utf-8') as file:
            temporary = Path(file.name)
            file.write(text)
        with contextlib.suppress(FileNotFoundError):
            os.chmod(temporary, stat.S_IMODE(os.stat(target).st_mode))
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                temporary.unlink()


def write_json(path, data):
    write_text(path, json.dumps(data, ensure_ascii=False, indent=1) + '\n')


def read_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as file:
            return json.load(file)
    except (OSError, ValueError):
        return default


@contextlib.contextmanager
def locked(name='state.lock', blocking=True, timeout=None):
    """Exclusive lock in the state dir; yields False when non-blocking and someone else holds it. With a timeout
    (seconds), waits at most that long and then raises TimeoutError. A new state dir is made 0700, and one that fails
    check_owner or check_ours raises UnsafeHome, as does a lock file that is a symlink (opening it never follows the
    link or truncates anything)."""
    directory = home()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    check_owner(directory)
    check_ours(directory)
    path = directory / name
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    except OSError as error:
        if error.errno == errno.ELOOP or path.is_symlink():
            raise UnsafeHome(f'{path} is a symbolic link; remove it') from None
        raise
    with os.fdopen(fd, 'r+b') as handle:
        if fcntl is None:
            yield True
            return
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking and deadline is None else fcntl.LOCK_NB))
                break
            except OSError:
                if deadline is None:
                    yield False
                    return
            if time.monotonic() >= deadline:
                raise TimeoutError(f'{name} is busy')
            time.sleep(0.05)
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


# ---- state ----

def new_state(day=None, lexicon=None, known_top=0):
    """A fresh state; known_top marks the top lexicon words known before the first learning words are picked."""
    day = day or today()
    words = [blank(w) for w in (lexicon or load_lexicon())]
    state = {'schema': 1, 'created': day, 'stage': 1, 'stage_pinned': False, 'paused': False, 'words': words}
    seed_known(state, known_top, day)
    refill(state, day)
    return state


def untouched_today(word, day):
    """A learning word refill picked today that has no progress yet: no sighting, slip, peek or quiz answer."""
    return (word['status'] == 'active' and word.get('added') == day and not word.get('days') and
            not word.get('assumed') and not word.get('peeks') and not word.get('last_bad') and not word.get('box') and
            not word.get('reviews'))


def seed_known(state, n, day=None):
    """Marks the top n lexicon words known if they aren't introduced yet (queue), or were picked today by refill and have
    no progress yet (the prompt hook usually creates the state just before setup runs). Words with any progress keep
    their status, so seeding never resets progress. Today's new-word allowance is given back for the words taken from
    the learning set, so refill can pick new ones. Returns how many words changed. (After French Weave, MIT.)"""
    day = day or today()
    seeded = [w for w in state['words'][:max(n, 0)] if w['status'] == 'queue' or untouched_today(w, day)]
    taken = sum(w['status'] == 'active' for w in seeded)
    last_day, count = state.get('refilled') or ['', 0]
    if taken and last_day == day:
        state['refilled'] = [day, max(0, count - taken)]
    for i, w in enumerate(seeded):
        set_status(w, 'known', day)
        # A first check, spread out so a big seed doesn't come due all at once; a miss sends the word back to learning.
        w['box'] = 1
        w['due'] = (dt.date.fromisoformat(day) + dt.timedelta(days=INTERVALS[1] + i % SEED_SPREAD)).isoformat()
    return len(seeded)


def blank(word):
    """A lexicon entry as a queued word: days = extension seen days, assumed = opt-in unscanned chat days."""
    return dict(word, status='queue', added='', changed='', days=[], assumed=[], peeks=[], last_bad='')


def merge_lexicon(state, lexicon=None):
    """Puts the words in lexicon order, adding the ones the state doesn't have yet at their rank (a plugin update can
    grow the list; refill, seeding and the known band all follow this order), and takes the list's current meaning and
    sound hint, so a corrected gloss reaches everyone. Never drops a word: one no longer listed keeps its progress at
    the end."""
    have = {}
    for w in reversed(state['words']):
        have[key(w['es'])] = w  # the first of any duplicates wins; the others stay at the end
    words = []
    for w in lexicon or load_lexicon():
        mine = have.pop(key(w['es']), None)
        if mine is None:
            mine = blank(w)
        else:
            mine.update(en=w['en'], hint=w['hint'])
        words.append(mine)
    placed = {id(w) for w in words}
    state['words'] = words + [w for w in state['words'] if id(w) not in placed]
    return state


class StateError(ValueError):
    """state.json is there but holds no word state. It is never replaced on its own, since it may hold months of
    progress; `sw.py check` says how to fix it."""


def state_problem(path):
    """Why the state.json at path holds no word state, or None when it does or is not there."""
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        return f"can't be read ({error.__class__.__name__})"
    if not text.strip():
        return 'is empty'
    try:
        data = json.loads(text)
    except ValueError as error:
        return f'is not valid JSON ({getattr(error, "msg", error)}, line {getattr(error, "lineno", "?")})'
    return None if isinstance(data, dict) and isinstance(data.get('words'), list) else 'has no word list in it'


def load_state(create=True, lock=True):
    """The saved state; creates it on first use (create=False: None until then). lock=False when the caller already
    holds state.lock. Raises StateError when state.json is there but unreadable, and UnsafeHome when the state dir
    fails check_owner (someone else could have written the words that go into Claude's context) or, when it would
    create the state, check_ours (it is someone else's folder)."""
    directory = home()
    if directory.exists():
        check_owner(directory)
    path = directory / 'state.json'
    state = read_json(path)
    if isinstance(state, dict) and isinstance(state.get('words'), list):
        return state
    problem = state_problem(path)
    if problem:
        raise StateError(f'{path} {problem}')
    if not create:
        return None
    with locked() if lock else contextlib.nullcontext():
        if not path.exists():
            check_ours(directory)
            write_json(path, new_state())
    return load_state(create=False, lock=False)


def save_state(state):
    write_json(home() / 'state.json', state)


@contextlib.contextmanager
def editing(timeout=None):
    """Load, let the caller change, promote and save the state under the lock (timeout: see locked)."""
    with locked(timeout=timeout):
        state = load_state(lock=False)
        merge_lexicon(state)
        yield state
        promote(state)
        save_state(state)


def fold(text):
    """Without accents or tildes, so a word typed on an English keyboard still matches: "tambien", "ano"."""
    return ''.join(c for c in unicodedata.normalize('NFD', key(text)) if unicodedata.category(c) != 'Mn')


def find(state, es):
    k = key(es)
    bare = lambda w: re.sub('^' + ARTICLE, '', key(w['es']))
    for w in state['words']:
        if key(w['es']) == k:
            return w
    # Accept the bare noun for "el problema" style entries.
    for w in state['words']:
        if bare(w) == k:
            return w
    # Accept missing accents, but only when exactly one word matches ("si" and "sí" are different words).
    folded = fold(k)
    for spelling in (lambda w: key(w['es']), bare):
        hits = [w for w in state['words'] if fold(spelling(w)) == folded]
        if len(hits) == 1:
            return hits[0]
    return None


def set_status(word, status, day):
    word['status'] = status
    word['changed'] = day
    if not word['added']:
        word['added'] = day


def stage_for(state):
    if state.get('stage_pinned'):
        return state['stage']
    known = sum(w['status'] == 'known' for w in state['words'])
    return next((s for n, s in STAGES if known >= n), 1)


def exposure_days(word, chat=None):
    """{day: 'seen' | 'assumed'} since the word joined the learning set.

    'seen' (counts 1): extension seen events and the word in a Claude Code or Codex reply (scanned transcripts are
    genuine exposure). 'assumed' (counts ASSUMED_WEIGHT): opt-in log-chat-day marks for chats that can't be scanned."""
    since = word.get('added') or '0000'
    days = {d: 'assumed' for d in word.get('assumed') or [] if d >= since}
    for d in list(word.get('days') or []) + list((chat or {}).get(word['es'], {}).get('days', [])):
        if d >= since:
            days[d] = 'seen'
    return dict(sorted(days.items()))


def refill(state, day, cap=NEW_PER_DAY):
    """Fill the learning set (active and shaky words) up to WINDOW from lexicon order, at most cap new words per day,
    none while SHAKY_BLOCK or more words are shaky."""
    words = state['words']
    if sum(w['status'] == 'shaky' for w in words) >= SHAKY_BLOCK:
        return 0
    last_day, count = state.get('refilled') or ['', 0]
    count = count if last_day == day else 0
    room = min(WINDOW - sum(w['status'] in ('active', 'shaky') for w in words), cap - count)
    added = 0
    for w in words:
        if added >= room:
            break
        if w['status'] == 'queue':
            set_status(w, 'active', day)
            added += 1
    state['refilled'] = [day, count + added]
    return added


def graduates(word, chat=None):
    """active -> known: GRADUATE_DAYS of exposure, no flip/asked/peek on the last GRADUATE_DAYS exposure days,
    and at least one genuinely seen day (assumed days alone never graduate a word)."""
    days = exposure_days(word, chat)
    total = sum(1 if kind == 'seen' else ASSUMED_WEIGHT for kind in days.values())
    if total < GRADUATE_DAYS or len(days) < GRADUATE_DAYS:
        return False
    streak = list(days)[-GRADUATE_DAYS]
    peeks = word.get('peeks') or []
    clean = (not word['last_bad'] or word['last_bad'] < streak) and not (peeks and peeks[-1] >= streak)
    return clean and 'seen' in days.values()


def recovers(word, day, chat=None):
    """shaky -> known: SHAKY_DAYS with no slip (flip, asked or peek), and at least one genuinely seen day since the last
    one: a word nobody saw isn't relearned, and assumed days never count. Chat can't count UNMEASURABLE words, so for
    them the clean week alone has to do."""
    slip = word['last_bad'] or word['changed']
    if days_between(slip, day) < SHAKY_DAYS:
        return False
    return norm(word['es']) in UNMEASURABLE or any(d > slip and kind == 'seen'
                                                   for d, kind in exposure_days(word, chat).items())


def chat_exposure():
    """Chat exposure by word, from the transcript scan (exposure.json)."""
    return (read_json(home() / 'exposure.json', {}) or {}).get('words', {})


def promote_word(w, day, chat):
    """active -> known (graduates) or shaky -> known (recovers) for one word, if it is ready."""
    if w['status'] == 'active' and graduates(w, chat):
        set_status(w, 'known', day)
        schedule(w, day, max(w.get('box', 0), KNOWN_BOX['graduated']))
    elif w['status'] == 'shaky' and recovers(w, day, chat):
        set_status(w, 'known', day)
        schedule(w, day, max(w.get('box', 0), KNOWN_BOX['recovered']))


def promote(state, day=None, chat=None):
    """Applies the promotion rules for today. Idempotent: safe to call as often as you like."""
    day = day or today()
    if chat is None:
        chat = chat_exposure()
    for w in state['words']:
        promote_word(w, day, chat)
    refill(state, day)
    state['stage'] = stage_for(state)
    return state


EVENTS = ('seen', 'assumed', 'flip', 'asked', 'peek', 'known', 'active')


def apply_event(state, es, kind, day=None):
    """Extension and command events. Returns False for unknown words or kinds.

    seen / assumed: exposure. flip (clicked back to English) / asked: shaky. peek (hovered for the meaning):
    blocks graduation of an active word, restarts a shaky word's clock, and a known word peeked on 2 different
    days within PEEK_WINDOW days since it became known turns shaky. known / active: set directly (commands).
    A flip, asked or peek dated before the word's last change (a browser queue sent late) never undoes that change."""
    day = day or today()
    w = find(state, es)
    if w is None or kind not in EVENTS:
        return False
    since = w.get('changed') or ''
    if kind in ('seen', 'assumed'):
        field = 'days' if kind == 'seen' else 'assumed'
        if w['status'] != 'queue' and day not in (w.get(field) or []):
            w[field] = sorted((w.get(field) or []) + [day])[-60:]
    elif kind in ('flip', 'asked'):
        w['last_bad'] = max(w['last_bad'] or '', day)
        if day >= since:
            set_status(w, 'shaky', day)
            schedule(w, day, 0)  # a slip: quiz it again from the first box, starting tomorrow
    elif kind == 'peek':
        w['peeks'] = peeks = sorted(set((w.get('peeks') or []) + [day]))[-10:]
        if w['status'] == 'shaky' and day >= since:
            w['last_bad'] = max(w['last_bad'] or '', day)
        elif w['status'] == 'known' and day >= since and any(
                p >= since and p != day and abs(days_between(p, day)) < PEEK_WINDOW for p in peeks):
            # Only peeks since it became known count: hovering a word in its learning days is how it gets learned.
            w['last_bad'] = max(w['last_bad'] or '', peeks[-1])
            set_status(w, 'shaky', day)
            schedule(w, day, 0)
    elif kind == 'known':
        if w['status'] != 'known':  # marking an already known word again keeps its review schedule
            schedule(w, day, KNOWN_BOX['marked'])
        set_status(w, 'known', day)
    elif kind == 'active':
        w['last_bad'] = day  # restart its graduation count
        set_status(w, 'active', day)
    return True


def introduced(state):
    """Words in use (active, shaky, known), learning words first."""
    order = {'shaky': 0, 'active': 1, 'known': 2}
    words = [w for w in state['words'] if w['status'] in order]
    return sorted(words, key=lambda w: (order[w['status']], w['added']))


COLLAPSE_AT = 150      # from this many known words, the brief and exports name a rank band instead of listing them
EXCEPTIONS_MAX = 15    # most exceptions named on each side of the band


def known_band(state):
    """Compact description of the known set by lexicon rank (the lexicon is in frequency/usefulness order).

    Returns (n, missing, extra): known = words ranked 1..n, except `missing` (ranked <= n but not yet introduced;
    learning words are listed separately anyway), plus `extra` (known words ranked > n). n minimizes the number
    of exceptions, counting learning words inside the band as exceptions too, so the band ends at the last known
    rank rather than running over the words being learned; ties go to the larger band."""
    words = state['words']
    known_after = sum(w['status'] == 'known' for w in words)
    unknown_before = 0
    best = (known_after, 0)
    for rank, w in enumerate(words, 1):
        known_after -= w['status'] == 'known'
        unknown_before += w['status'] != 'known'
        if unknown_before + known_after <= best[0]:
            best = (unknown_before + known_after, rank)
    n = best[1]
    missing = [w['es'] for w in words[:n] if w['status'] == 'queue']
    extra = [w['es'] for w in words[n:] if w['status'] == 'known']
    return n, missing, extra


def version(state):
    # Glosses, hints and notes are in it too: the extension caches swaps with them, so an edited lexicon.csv or
    # notes.csv must look like a new list. The pause flag isn't: the extension clears its swap cache when this changes,
    # and it gets paused as a field of its own that stops and starts pages, so a pause keeps the cached swaps.
    blob = json.dumps([stage_for(state),
                       [(w['es'], w['status'], w['en'], w['hint'], note(w['es'])) for w in introduced(state)]])
    return hashlib.sha1(blob.encode()).hexdigest()[:10]


def public_state(state):
    """What the extension gets: stage, pause flag, and the words in use (with a usage note where there is one)."""
    words = []
    for w in introduced(state):
        words.append({k: w[k] for k in ('es', 'en', 'hint', 'status')})
        if note(w['es']):
            words[-1]['note'] = note(w['es'])
    return {'version': version(state), 'stage': stage_for(state), 'paused': bool(state.get('paused')), 'words': words}


# ---- usage notes ----

@functools.lru_cache(maxsize=None)
def load_notes(path=NOTES):
    """Usage notes, mostly false friends ("el éxito": "not 'exit' (that's la salida)"), by key. Shown next to the
    gloss in chat, the quiz, the extension and exports; never stored in the word state, so editing notes.csv is enough."""
    try:
        with open(path, encoding='utf-8', newline='') as file:
            return {key(r['es']): r['note'].strip() for r in csv.DictReader(file)
                    if (r.get('es') or '').strip() and (r.get('note') or '').strip()}
    except OSError:
        return {}


def note(es):
    return load_notes().get(key(es), '')


# ---- spaced review: the quiz ----

def schedule(word, day, box):
    """Puts the word in a box; its next review is INTERVALS[box] days after day."""
    word['box'] = max(0, min(box, len(INTERVALS) - 1))
    word['due'] = (dt.date.fromisoformat(day) + dt.timedelta(days=INTERVALS[word['box']])).isoformat()


def due_date(word):
    """When the word is next up for review: its schedule; a learning word never quizzed, the day after it arrived; a
    known word from before the quiz existed, a week after it became known. None: never reviewed (seeded long ago)."""
    if word.get('due'):
        return word['due']
    later = lambda day, days: (dt.date.fromisoformat(day) + dt.timedelta(days=days)).isoformat()
    if word['status'] in ('active', 'shaky') and word.get('added'):
        return later(word['added'], FIRST_QUIZ_DAYS)
    if word['status'] == 'known' and word.get('changed', '') > word.get('added', ''):
        return later(word['changed'], INTERVALS[KNOWN_BOX['graduated']])
    return None


def due_reviews(state, day=None, limit=10):
    """The quiz queue: introduced words due by day and not reviewed today, shaky first, then the most overdue."""
    day = day or today()
    ready = [w for w in state['words'] if w['status'] != 'queue' and (due_date(w) or '9999') <= day
             and not any(d == day for d, *_ in w.get('reviews') or [])]
    return sorted(ready, key=lambda w: (w['status'] != 'shaky', due_date(w)))[:limit]


def direction(word):
    """'produce' (how do you say it?) once the last PRODUCE_AFTER quiz answers were right, else 'recognize' (what does
    it mean?). Recognition comes first; producing a word is the harder retrieval and builds a stronger memory."""
    recent = [ok for _, ok, *_ in (word.get('reviews') or [])][-PRODUCE_AFTER:]
    return 'produce' if len(recent) == PRODUCE_AFTER and all(recent) else 'recognize'


def meanings(en):
    """English answers that match a gloss: "the problem" -> problem; "to be (state or place)" -> be; "so / then"."""
    out = set()
    for part in re.split(r'\s*/\s*', re.sub(r'\([^)]*\)', ' ', fold(en))):
        part = re.sub(r'\s+', ' ', part).strip(' .!?')
        if part:
            out |= {part, re.sub(r'^(the|to|a|an) ', '', part)}
    return out


GENDER_OF = {'el': 'm', 'los': 'm', 'un': 'm', 'unos': 'm', 'la': 'f', 'las': 'f', 'una': 'f', 'unas': 'f'}


def article_of(text):
    """The article a Spanish answer starts with ("la problema" -> "la"), or ''."""
    m = re.match(r'(el|la|los|las|un|una|unos|unas) ', key(text))
    return m.group(1) if m else ''


def gender_slip(es, article):
    """True when article gives the listed noun es the wrong gender and the noun's ending doesn't tell its gender, so it
    has to be remembered: la problema, el mano, la día, el clase. On la casa, whose -a says feminine, a wrong article
    is only a slip."""
    m = re.match(r'(el|la|los|las|un|una|unos|unas) (\S+)', key(es))
    given = GENDER_OF.get(key(article or ''))
    if not m or not given or given == GENDER_OF[m.group(1)]:
        return False
    gender, noun = GENDER_OF[m.group(1)], fold(m.group(2))
    return not (gender == 'm' and re.search(r'os?$', noun) or gender == 'f' and re.search(r'as?$', noun))


def bare_fold(text):
    """Folded, without a leading article: "La Canción" -> "cancion"."""
    return re.sub(r'^(el|la|los|las|un|una|unos|unas) ', '', fold(text))


@functools.lru_cache(maxsize=None)
def listed_meanings():
    """Every listed word (bare, folded) -> its meanings, to tell a synonym ("recordar" for acordarse) from a mistake."""
    out = {}
    for w in load_lexicon():
        out.setdefault(bare_fold(w['es']), set()).update(meanings(w['en']))
    return out


def check(word, answer, way):
    """True or False for a quiz answer, or None when a person should judge: an English answer that matches no listed
    meaning word for word, or another listed Spanish word with the same meaning. Accents, ñ, capitals and a missing or
    different el/la don't count against the answer."""
    given = fold(answer).strip(' .,!?¡¿"\'')
    if not given:
        return False
    if way == 'produce':
        if fold(given) == fold(word['es']):
            return True
        if bare_fold(given) == bare_fold(word['es']):
            if re.match(r'(un|una|unos|unas) ', key(word['es'])):
                return False  # the un/una is part of the phrase: "poco" is not "un poco", "la vez" not "una vez"
            if any(fold(w['es']) == fold(given) for w in load_lexicon()):
                return False  # another listed word: "una vez" (once) is not "la vez" (the time)
            return True  # a missing or different article
        return None if listed_meanings().get(bare_fold(given), set()) & meanings(word['en']) else False
    english = re.sub(r'^(the|to|a|an) ', '', given)
    if english in meanings(word['en']):
        return True
    lookalike = re.match(r"not '([^']+)'", note(word['es']))
    if lookalike and english in meanings(lookalike.group(1)):
        return False  # the false friend itself ("actually" for actualmente) is a mistake, not a synonym
    return None


# What an answer can change, saved with it before and after ([day, ok, *before, *after, added]) so a same-day redo can
# undo it; added is 1 when the answer added the day as a seen day (a sighting from before the answer stays).
UNDO = ('box', 'status', 'changed', 'last_bad')


def review(state, es, right, day=None, hold=False):
    """Records a quiz answer. A second answer the same day replaces the first (a retried command or a corrected
    verdict), so answers can't stack boxes and a wrong verdict can be taken back: the word gets back the box, status
    and dates it had, and loses the seen day the first answer added. The first answer is undone only if nothing else
    changed the word since (a known, learn or flip in between stays); otherwise the new answer goes on top.

    Right: the word moves up a box, so its next review comes later, and the day counts as an exposure day. With hold
    (right, but with a gender_slip), it stays in its box and comes back at the same gap.
    Wrong: a learning word starts its three clean days over and comes back tomorrow. A known word drops two boxes;
    if it wasn't even recognized, it turns shaky, so it shows up more in chat until it's known again.
    The answer's promotion (a third seen day graduates a learning word) happens here, as the save would do it, so the
    after-snapshot shows it and a same-day correction still finds the word as the answer left it."""
    day = day or today()
    w = find(state, es)
    if w is None or w['status'] == 'queue':
        return None
    fields = lambda: [w.get(k, 0 if k == 'box' else '') for k in UNDO]
    reviews = list(w.get('reviews') or [])
    if reviews and reviews[-1][0] == day:  # an earlier answer from today: this one replaces it
        saved, n = reviews.pop()[2:], len(UNDO)
        before, after, added = saved[:n], saved[n:2 * n], saved[2 * n:]
        if not after or after == fields():  # (0.2.2 records have no after-snapshot)
            w.update(zip(UNDO, before))
            if added and added[0]:
                w['days'] = [d for d in w.get('days') or [] if d != day]
    way, box = direction(dict(w, reviews=reviews)), w.get('box', 0)
    before, seen = fields(), day in (w.get('days') or [])
    if right:
        apply_event(state, w['es'], 'seen', day)
        schedule(w, day, box if hold else box + 1)
    elif w['status'] == 'known' and way == 'produce':
        schedule(w, day, box - 2)  # still recognized: only production slipped
    elif w['status'] == 'known':
        apply_event(state, w['es'], 'asked', day)  # not recognized: shaky, first box
    else:
        w['last_bad'] = day
        schedule(w, day, 0)
    promote_word(w, day, chat_exposure())
    added = int(not seen and day in (w.get('days') or []))
    w['reviews'] = (reviews + [[day, int(bool(right))] + before + fields() + [added]])[-10:]
    return w


# ---- chat exposure from Claude Code transcripts ----

def pattern(es):
    word = norm(es)
    noun = re.match(ARTICLE + '(.+)', word)
    if noun:
        noun = noun.group(1)
        # An unaccented noun can be English too ("error", "idea"), so it needs a Spanish determiner in front.
        lead = r"(?<!\w)" + (DETERMINER if noun.isascii() else '')
        return re.compile(lead + re.escape(noun) + r"(?:es|s)?(?!\w)")
    before, after = SPECIAL.get(word, ('', ''))
    if len(word) == 1:  # y, o: also not in y'all, x/y, x.y, y-axis or O(n)
        lead, tail = r"(?<![\w'/.-])", r"(?![\w'/.(-])"
    else:
        lead, tail = r"(?<![\w'-])", r"(?![\w'-])"
    return re.compile(lead + before + re.escape(word) + tail + after)


def codex_home():
    return Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex').expanduser()


def claude_config_dir():
    return Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude').expanduser()


def transcript_roots():
    """Chat transcripts to scan: SPANISH_WEAVE_TRANSCRIPTS, else Claude Code's projects and Codex's sessions."""
    if os.environ.get('SPANISH_WEAVE_TRANSCRIPTS'):
        return [Path(os.environ['SPANISH_WEAVE_TRANSCRIPTS']).expanduser()]
    return [claude_config_dir() / 'projects', codex_home() / 'sessions']


class Lines:
    """Complete lines of a log after a byte offset; .offset ends just past the last complete line read."""

    def __init__(self, path, offset):
        self.path, self.offset = path, offset

    def __iter__(self):
        with open(self.path, 'rb') as file:
            file.seek(self.offset)
            for raw in file:
                if not raw.endswith(b'\n'):
                    return  # half-written; read it next time
                self.offset += len(raw)
                yield raw.decode('utf-8', 'replace')


def prompt_kind(item):
    """'typed' for a prompt the user typed (in the terminal, desktop app, IDE or from a phone), 'auto' for one Claude
    Code marks as coming from elsewhere: the session or scheduled task that started this one, a task notification, a
    message from another session. None for anything else, including prompts Claude Code marked too little to tell.

    Claude Code records origin {"kind": "human"} on typed prompts from 2.1.205, and turnOrigin on every prompt from
    2.1.281 ("sdk" on the first prompt of a session another session started). Before that a desktop prompt carries
    only promptSource "sdk", typed or not, so that alone is no evidence."""
    content = (item.get('message') or {}).get('content') if isinstance(item.get('message'), dict) else None
    if (item.get('type') != 'user' or item.get('isMeta') or item.get('isSidechain') or isinstance(content, list)
            and any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in content)):
        return None
    origin = (item.get('origin') or {}).get('kind') if isinstance(item.get('origin'), dict) else None
    turn = item.get('turnOrigin')
    if origin == 'human' or turn == 'human' or item.get('promptSource') == 'typed':
        return 'typed'
    if origin not in (None, 'auto-continuation') or turn is not None or item.get('promptSource') == 'system':
        return 'auto'
    return None


def replies(lines, prompts=None):
    """Yield (day, text) for main-thread assistant replies in Claude Code or Codex transcript lines. prompts, if
    given, is called with each marked prompt's kind ('typed' or 'auto', see prompt_kind) in transcript order, before
    the replies that follow it are yielded."""
    for line in lines:
        if len(line) > 1_000_000 or '"assistant"' not in line and (prompts is None or '"user"' not in line):
            continue
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if prompts is not None and isinstance(item, dict) and item.get('type') == 'user':
            kind = prompt_kind(item)
            if kind:
                prompts(kind)
            continue
        day = local_day(item.get('timestamp'))
        if item.get('type') == 'assistant' and not item.get('isSidechain'):  # Claude Code
            for block in item.get('message', {}).get('content') or []:
                if isinstance(block, dict) and block.get('type') == 'text':
                    yield day, block.get('text', '')
        elif item.get('type') == 'response_item':  # Codex
            payload = item.get('payload') or {}
            if payload.get('type') == 'message' and payload.get('role') == 'assistant':
                yield day, ' '.join(b.get('text', '') for b in payload.get('content') or [] if isinstance(b, dict))


def local_day(stamp):
    try:
        return dt.datetime.fromisoformat(str(stamp).replace('Z', '+00:00')).astimezone().date().isoformat()
    except ValueError:
        return str(stamp)[:10]


def scan(words, index, roots=None, start='0000-00-00'):
    """Fold new transcript lines into the exposure index (mutated and returned).

    Replies count only in chats the user typed in, from the first typed prompt on: a session that another session,
    a scheduled task or the desktop app started runs unread, so its replies are no exposure (index['typed'] holds
    each marked chat's state, see prompt_kind). Transcripts without prompt marks (older Claude Code, Codex) count."""
    roots = [Path(r) for r in ([roots] if isinstance(roots, (str, Path)) else roots)] if roots else transcript_roots()
    patterns = {es: pattern(es) for es in words if norm(es) not in UNMEASURABLE}
    counts, offsets, recent = index.setdefault('words', {}), index.setdefault('offsets', {}), index.setdefault('recent', {})
    typed = index.setdefault('typed', {})
    for es in patterns:
        counts.setdefault(es, {'n': 0, 'days': []})
    since = time.mktime(time.strptime(start, '%Y-%m-%d')) if start > '0000' else 0
    for path in (p for root in roots if root.exists() for p in root.rglob('*.jsonl')):
        name = str(path)
        try:
            if 'subagents' in path.parts or path.stat().st_mtime < since:
                continue
            offset = offsets.get(name, 0)
            if path.stat().st_size < offset:
                offset = 0
        except OSError:
            continue
        lines = Lines(path, offset)
        mark = [typed.get(name) if offset else None]  # None: no marked prompt yet; else whether one was typed

        def note(kind):
            mark[0] = mark[0] or kind == 'typed'
        for day, text in replies(lines, note):
            if mark[0] is False or day < start or 'Spanish Weave' in text:
                continue
            digest = hashlib.sha1(text.encode()).hexdigest()[:16]
            if digest in recent:
                continue  # forked and resumed chats copy old replies
            recent[digest] = day
            rest = norm(CODE.sub(' ', text))
            # Longest first, each match removed before the next search, as the hook's share() does: "es decir" is not
            # also decir, "vale la pena" not also la pena.
            for es, regex in sorted(patterns.items(), key=lambda p: -len(p[0])):
                if regex.search(rest):
                    entry = counts[es]
                    entry['n'] += 1
                    if day not in entry['days']:
                        entry['days'] = sorted(entry['days'] + [day])[-60:]
                    rest = regex.sub(' ', rest)
        offsets[name] = lines.offset
        if mark[0] is not None:
            typed[name] = mark[0]
    cutoff = (dt.date.today() - dt.timedelta(days=DEDUPE_DAYS)).isoformat()
    index['recent'] = {k: v for k, v in recent.items() if v >= cutoff}
    index['offsets'] = {k: v for k, v in offsets.items() if os.path.exists(k)}
    index['typed'] = {k: v for k, v in typed.items() if k in index['offsets']}
    index['updated'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    return index


def refresh_exposure():
    """Scan new transcript lines, then re-apply promotion. Skips if another refresh is running."""
    with locked('exposure.lock', blocking=False) as got:
        if not got:
            return False
        state = load_state()
        path = home() / 'exposure.json'
        index = scan([w['es'] for w in state['words']], read_json(path, {}) or {}, start=state.get('created', '0000-00-00'))
        write_json(path, index)
    with editing():
        pass  # promotion runs on save
    return True
