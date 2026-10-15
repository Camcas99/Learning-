"""Spanish Weave shared state: word statuses, stage, chat exposure, extension events.

Python 3.9+ standard library only. One state directory per user (SPANISH_WEAVE_HOME, default ~/.spanish-weave)
holds everything; the Claude Code hook, the slash commands and the Chrome native messaging host all read and
write it through this module.

Statuses: queue -> active -> known, with shaky as the penalty box (see README "How words advance").
"""
import contextlib
import csv
import datetime as dt
import functools
import hashlib
import json
import os
from pathlib import Path
import re
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
WINDOW = 20             # target number of active (learning) words
NEW_PER_DAY = 5         # new words per day, including the first day
SHAKY_BLOCK = 5         # no new words while this many or more are shaky
GRADUATE_DAYS = 3       # active -> known: exposure days needed, and length of the clean streak
SHAKY_DAYS = 7          # shaky -> known: days with no new flip, asked or peek
PEEK_WINDOW = 7         # a known word peeked on 2 different days within this many days becomes shaky
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
UNMEASURABLE = {'solo', 'mayor', 'sensible'}
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

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False, encoding='utf-8') as file:
            temporary = Path(file.name)
            json.dump(data, file, ensure_ascii=False, indent=1)
            file.write('\n')
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                temporary.unlink()


def read_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as file:
            return json.load(file)
    except (OSError, ValueError):
        return default


@contextlib.contextmanager
def locked(name='state.lock', blocking=True):
    """Exclusive lock in the state dir; yields False when non-blocking and someone else holds it."""
    directory = home()
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / name, 'w') as handle:
        if fcntl is None:
            yield True
            return
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except OSError:
            yield False
            return
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


def seed_known(state, n, day=None):
    """Marks the top n lexicon words known if they aren't introduced yet (queue). Words already learning, shaky or
    known keep their status, so seeding never resets progress. Returns how many words changed."""
    day = day or today()
    seeded = [w for w in state['words'][:max(n, 0)] if w['status'] == 'queue']
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
    """Adds lexicon words the state doesn't have yet (a plugin update can grow the list) and takes the list's current
    meaning and sound hint for the others, so a corrected gloss reaches everyone; never drops a word."""
    have = {key(w['es']): w for w in state['words']}
    for w in lexicon or load_lexicon():
        mine = have.get(key(w['es']))
        if mine is None:
            state['words'].append(blank(w))
        else:
            mine.update(en=w['en'], hint=w['hint'])
    return state


def load_state(create=True, lock=True):
    """The saved state; creates it on first use. lock=False when the caller already holds state.lock."""
    path = home() / 'state.json'
    state = read_json(path)
    if isinstance(state, dict) and isinstance(state.get('words'), list):
        return state
    if not create:
        return None
    with locked() if lock else contextlib.nullcontext():
        if not path.exists():
            write_json(path, new_state())
    return read_json(path)


def save_state(state):
    write_json(home() / 'state.json', state)


@contextlib.contextmanager
def editing():
    """Load, let the caller change, promote and save the state under the lock."""
    with locked():
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
    for spelling in (lambda w: key(w['es']), bare):
        hits = [w for w in state['words'] if fold(spelling(w)) == fold(k)]
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
    """Fill the learning set up to WINDOW from lexicon order, at most cap new words per day, none while
    SHAKY_BLOCK or more words are shaky."""
    words = state['words']
    if sum(w['status'] == 'shaky' for w in words) >= SHAKY_BLOCK:
        return 0
    last_day, count = state.get('refilled') or ['', 0]
    count = count if last_day == day else 0
    room = min(WINDOW - sum(w['status'] == 'active' for w in words), cap - count)
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


def promote(state, day=None, chat=None):
    """Applies the promotion rules for today. Idempotent: safe to call as often as you like."""
    day = day or today()
    if chat is None:
        chat = (read_json(home() / 'exposure.json', {}) or {}).get('words', {})
    for w in state['words']:
        if w['status'] == 'active' and graduates(w, chat):
            set_status(w, 'known', day)
            schedule(w, day, max(w.get('box', 0), KNOWN_BOX['graduated']))
        elif (w['status'] == 'shaky' and days_between(w['last_bad'] or w['changed'], day) >= SHAKY_DAYS
              and (any(d > (w['last_bad'] or w['changed']) for d in exposure_days(w, chat))
                   or norm(w['es']) in UNMEASURABLE)):
            # A week with no slips, and at least one sighting since the last one: a word nobody saw isn't relearned.
            # Chat can't count UNMEASURABLE words, so for them the clean week alone has to do.
            set_status(w, 'known', day)
            schedule(w, day, max(w.get('box', 0), KNOWN_BOX['recovered']))
    refill(state, day)
    state['stage'] = stage_for(state)
    return state


EVENTS = ('seen', 'assumed', 'flip', 'asked', 'peek', 'known', 'active')


def apply_event(state, es, kind, day=None):
    """Extension and command events. Returns False for unknown words or kinds.

    seen / assumed: exposure. flip (clicked back to English) / asked: shaky. peek (hovered for the meaning):
    blocks graduation of an active word, restarts a shaky word's clock, and a known word peeked on 2 different
    days within PEEK_WINDOW days becomes shaky. known / active: set directly (commands)."""
    day = day or today()
    w = find(state, es)
    if w is None or kind not in EVENTS:
        return False
    if kind in ('seen', 'assumed'):
        field = 'days' if kind == 'seen' else 'assumed'
        if w['status'] != 'queue' and day not in (w.get(field) or []):
            w[field] = sorted((w.get(field) or []) + [day])[-60:]
    elif kind in ('flip', 'asked'):
        w['last_bad'] = day
        set_status(w, 'shaky', day)
        schedule(w, day, 0)  # a slip: quiz it again from the first box, starting tomorrow
    elif kind == 'peek':
        peeks = w.setdefault('peeks', [])
        if not peeks or peeks[-1] != day:
            peeks.append(day)
            del peeks[:-10]
        if w['status'] == 'shaky':
            w['last_bad'] = day
        elif w['status'] == 'known' and len(peeks) >= 2 and days_between(peeks[-2], day) < PEEK_WINDOW:
            w['last_bad'] = day
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
    of exceptions; ties go to the larger band."""
    words = state['words']
    known_after = sum(w['status'] == 'known' for w in words)
    queue_before = 0
    best = (known_after, 0)
    for rank, w in enumerate(words, 1):
        known_after -= w['status'] == 'known'
        queue_before += w['status'] == 'queue'
        if queue_before + known_after <= best[0]:
            best = (queue_before + known_after, rank)
    n = best[1]
    missing = [w['es'] for w in words[:n] if w['status'] == 'queue']
    extra = [w['es'] for w in words[n:] if w['status'] == 'known']
    return n, missing, extra


def version(state):
    # Glosses, hints and notes are in it too: the extension caches swaps with them, so an edited lexicon.csv or
    # notes.csv must look like a new list.
    blob = json.dumps([stage_for(state), state.get('paused'),
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
        if bare_fold(given) == bare_fold(word['es']):
            return True
        return None if listed_meanings().get(bare_fold(given), set()) & meanings(word['en']) else False
    english = re.sub(r'^(the|to|a|an) ', '', given)
    if english in meanings(word['en']):
        return True
    lookalike = re.match(r"not '([^']+)'", note(word['es']))
    if lookalike and english in meanings(lookalike.group(1)):
        return False  # the false friend itself ("actually" for actualmente) is a mistake, not a synonym
    return None


UNDO = ('box', 'status', 'changed', 'last_bad')  # what an answer can change, saved with it so a same-day redo can undo it


def review(state, es, right, day=None, hold=False):
    """Records a quiz answer. A second answer the same day replaces the first (a retried command or a corrected
    verdict), so answers can't stack boxes and a wrong verdict can be taken back.

    Right: the word moves up a box, so its next review comes later, and the day counts as an exposure day. With hold
    (right, but with a gender_slip), it stays in its box and comes back at the same gap.
    Wrong: a learning word starts its three clean days over and comes back tomorrow. A known word drops two boxes;
    if it wasn't even recognized, it turns shaky, so it shows up more in chat until it's known again."""
    day = day or today()
    w = find(state, es)
    if w is None or w['status'] == 'queue':
        return None
    reviews = list(w.get('reviews') or [])
    if reviews and reviews[-1][0] == day:  # undo the earlier answer from today first
        w.update(zip(UNDO, reviews.pop()[2:]))
    way, box = direction(dict(w, reviews=reviews)), w.get('box', 0)
    before = [w.get(k, 0 if k == 'box' else '') for k in UNDO]
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
    w['reviews'] = (reviews + [[day, int(bool(right))] + before])[-10:]
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


def transcript_roots():
    """Chat transcripts to scan: SPANISH_WEAVE_TRANSCRIPTS, else Claude Code's projects and Codex's sessions."""
    if os.environ.get('SPANISH_WEAVE_TRANSCRIPTS'):
        return [Path(os.environ['SPANISH_WEAVE_TRANSCRIPTS']).expanduser()]
    claude = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude').expanduser() / 'projects'
    return [claude, codex_home() / 'sessions']


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


def replies(lines):
    """Yield (day, text) for main-thread assistant replies in Claude Code or Codex transcript lines."""
    for line in lines:
        if len(line) > 1_000_000 or '"assistant"' not in line:
            continue
        try:
            item = json.loads(line)
        except ValueError:
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
    """Fold new transcript lines into the exposure index (mutated and returned)."""
    roots = [Path(r) for r in ([roots] if isinstance(roots, (str, Path)) else roots)] if roots else transcript_roots()
    patterns = {es: pattern(es) for es in words if norm(es) not in UNMEASURABLE}
    counts, offsets, recent = index.setdefault('words', {}), index.setdefault('offsets', {}), index.setdefault('recent', {})
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
        for day, text in replies(lines):
            if day < start or 'Spanish Weave' in text:
                continue
            digest = hashlib.sha1(text.encode()).hexdigest()[:16]
            if digest in recent:
                continue  # forked and resumed chats copy old replies
            recent[digest] = day
            prose = norm(CODE.sub(' ', text))
            for es, regex in patterns.items():
                if regex.search(prose):
                    entry = counts[es]
                    entry['n'] += 1
                    if day not in entry['days']:
                        entry['days'] = sorted(entry['days'] + [day])[-60:]
        offsets[name] = lines.offset
    cutoff = (dt.date.today() - dt.timedelta(days=DEDUPE_DAYS)).isoformat()
    index['recent'] = {k: v for k, v in recent.items() if v >= cutoff}
    index['offsets'] = {k: v for k, v in offsets.items() if os.path.exists(k)}
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
