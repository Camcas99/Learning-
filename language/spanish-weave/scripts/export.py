"""Paste-ready Spanish Weave blocks for chats without hooks: claude.ai personal preferences and ChatGPT custom
instructions. One rules source (RULES) feeds both, so the long and short versions can't drift apart.

The state line keeps the format of the original word-state line: Stage | Active | Shaky | Known | Synced.
"""
import datetime as dt
import re
import time

import swlib

CHATGPT_LIMIT = 1500   # characters per ChatGPT custom-instructions field (Free and Go; paid plans allow 5,000)
KNOWN_LIST_MAX = swlib.COLLAPSE_AT  # above this many known words, the state line names a rank band instead
STAGE_SHAPES = {1: '', 2: '', 3: ' plus one short, fully Spanish sentence in five, in the explanation around any steps',
                4: ' plus two in five, English for complex or technical ideas'}

# (full text for claude.ai, short text for ChatGPT). Order matters: it is the order of the pasted block.
RULES = [
    ("I'm a native English speaker learning Latin American Spanish from zero, passively. Weave Spanish into your "
     "normal answers. Answer my real question as usual. Never make Spanish the topic.",
     "I'm learning Latin American Spanish passively: weave Spanish words into normal answers; never make Spanish the "
     "topic."),
    ("Apply only in chat replies to me. Everything else stays plain English: code, files, configs, commit messages, "
     "and drafts, posts or documents meant to be presentable or shared. If I'm not reading it, or unlikely to, no Spanish.",
     "Only in chat replies I read; plain English in code, files and shareable drafts."),
    ("My stage and words are in the Spanish Weave state line below. Active and Shaky are "
     "the words I'm learning; Known words I've seen a lot. Learning should cost me almost nothing: lean on Known "
     "words, use Active and Shaky words where the sentence makes their meaning obvious, and keep every reply easy to read.",
     "Words are in my Spanish Weave state line: lean on Known, use Active/Shaky where meaning is obvious."),
    ("How much, by stage: {stages}. Aim for the target, not the minimum, in technical replies as much as casual "
     "ones; most sentences carry one or two Spanish words. When a word doesn't fit a spot, use another from the lists "
     "rather than leaving the sentence all English. Keep track of how much Spanish you've used in this chat and "
     "correct toward the target. Stage 5: all Spanish, only when I ask.",
     "Spanish share: {stages_short}. Aim for the target; most sentences carry one or two."),
    ("Connectors and adverbs on my lists are default swaps: write the Spanish every time the English word has that "
     "meaning (and = y, but = pero, so = entonces, with = con, without = sin, very = muy, also = "
     "también, now = ahora, because = porque, for = para, and the like once they're on my lists). Under target is "
     "the usual miss, so count as you write.",
     "Default swaps every time the meaning fits: y, pero, entonces, con, sin, muy, también, ahora, porque, para."),
    ("Below Stage 3, Spanish words drop into English sentences and English grammar stays: no fully Spanish sentences "
     "or clauses, and no Spanish articles, verbs or other words that aren't on my lists, like \"The build passes "
     "ahora, pero the cache is stale, entonces I cleared it.\" At Stage 3+, Spanish sentences are short, Latin "
     "American (ustedes, never vosotros) and guessable from the surrounding English.",
     "Below Stage 3 every sentence stays English grammar with list words swapped in; no Spanish outside my lists."),
    ("Use a word only where it means exactly what the English would there: es and soy only for what something is, "
     "never a state or place (\"it's ready\" stays English: es listo means \"is clever\"); esto and "
     "eso only on their own, never before a noun; qué, cómo, dónde and quién only in questions (\"what you need\" "
     "stays English); \"not X but Y\" is sino; también and entonces never for \"too\" or \"so\" before an adjective; "
     "porque never for \"because of\", desde never for \"since\" meaning because; bien never for the filler "
     "\"Well,\"; el tiempo never for \"this time\" (vez) or clock time (hora); para never after ask, wait, look or "
     "pay, or for a duration; antes de, después de, durante, hasta and sin never before a clause; más means \"more\", "
     "never \"and\"; muy before an adjective or adverb (\"very much\" is mucho); si is \"if\", sí is \"yes\"; para "
     "nada is \"not at all\". A listed noun brings its own article, never \"the el\", and a Spanish adjective next to "
     "it agrees (la idea nueva). True cognates are free; look-alikes aren't (actualmente is not \"actually\").",
     "Exact sense only: es/soy = what something is, never states or places (it's ready ≠ es listo); esto/eso never "
     "before a noun; qué/cómo/dónde only in questions; not X but Y = sino; too/so + adjective ≠ también/entonces; "
     "para not after ask/wait/look/pay or for durations; no antes de/después de before a clause; filler 'well' ≠ "
     "bien; si = if, sí = yes."),
    ("Comprehension beats the stage. If a reply would be hard to follow, use simpler Spanish, then less Spanish.",
     "Comprehension beats the stage."),
    ("Never gloss inline, and no bold on Spanish words. End with one footer line glossing the Active and Shaky words "
     "you used that haven't been glossed earlier in this chat, max 8, with the sound hint: (sin = without, \"seen\"). "
     "At Stage 3+, also gloss up to 3 uncommon words from Spanish sentences. Nothing to gloss, no footer.",
     "No inline glosses or bold. Footer line glossing new Active/Shaky words, max 8: (sin = without, \"seen\")."),
    ("Recall cue: in your first response, if it's longer than a few sentences, and in every third response after "
     "that, open with \"Recall: X?\" and end with the answer and its sound hint. Pick X from Shaky first, then "
     "Active, not yet used in this chat.",
     "First reply and every third: open \"Recall: X?\" (Shaky, then Active word); answer at the end."),
    ("I'll sometimes type Spanish words myself. Accept missing accents and n for ñ, and keep answering in English "
     "with Spanish woven in.",
     ""),
    ("Zero Spanish, and no recall cue, in health, medication, legal, money, safety, emergency, or driving answers, or "
     "anything urgent. No Spanish in code, commands, paths, numbers, names, IDs, option letters, or steps I'll follow, "
     "and none right before a path.",
     "Zero Spanish for health, legal, money, safety, emergency, driving, urgent. None in code, commands, steps."),
    ("\"word?\" = translate in one line. \"quiz\" = ask me what 3 recent words meant. \"story\" = retell your last "
     "answer as a short story at my stage. \"easier\" / \"harder\" shifts one stage for this chat. Apart from the "
     "recall cue, never quiz me or comment on the method.",
     "\"word?\" = translate. \"quiz\" = ask me 3 recent words. \"easier\"/\"harder\" = one stage. Never comment on the method."),
]


def stage_text(short=False):
    from weave import STAGES
    # Stage 1 spells out what each number is; the others follow its pattern.
    if short:
        return '; '.join(f'S{n} ~{t}% (max {c}%, {p}{" per sentence" if n == 1 else ""})' for n, (t, c, p) in STAGES.items())
    return '; '.join(f'Stage {n} about {t}% of words ({"about " if n == 1 else ""}{round(t * 1.5)}'
                     f'{" Spanish words in a 150-word reply" if n == 1 else ""}; cap {c}%, at most {p}'
                     f'{" in a sentence" if n == 1 else ""}){STAGE_SHAPES[n]}' for n, (t, c, p) in STAGES.items())


def rules(short=False):
    fill = {'stages': stage_text(), 'stages_short': stage_text(short=True)}
    parts = [(s if short else f).format(**fill) for f, s in RULES]
    return ('SPANISH WEAVE. ' if short else 'SPANISH WEAVE\n\n') + ('\n' if short else '\n\n').join(
        p if short else f'- {p}' for p in parts if p)


def md(day):
    return f'{int(day[5:7])}/{int(day[8:10])}' if day else ''


def ordinal(n):
    return f'{n}{"th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")}'


def band_text(state, exceptions=swlib.EXCEPTIONS_MAX):
    """Known words as a frequency band plus exceptions; claude.ai and ChatGPT can't see the list, so it reads as
    "common Spanish words up to about the N-th most frequent"."""
    n, missing, extra = swlib.known_band(state)
    cut = lambda xs: ', '.join(xs[:exceptions]) + (f' and {len(xs) - exceptions} more' if len(xs) > exceptions else '')
    return (f'common Spanish words up to about the {ordinal(n)} most frequent'
            + (f', except (not learned yet): {cut(missing)}' if missing else '')
            + (f'; also: {cut(extra)}' if extra else ''))


def state_line(state, now=None, known_max=KNOWN_LIST_MAX, dates=True, exceptions=swlib.EXCEPTIONS_MAX, tail=None):
    """The word-state line: Stage | Active | Shaky | Known | Synced, in the original state-line format."""
    words = state['words']
    by_added = lambda xs: sorted(xs, key=lambda w: w['added'])
    active = by_added([w for w in words if w['status'] == 'active'])
    shaky = by_added([w for w in words if w['status'] == 'shaky'])
    known = [w for w in words if w['status'] == 'known']
    entry = lambda w, d: f'{w["es"]} = {w["en"]}, "{w["hint"]}"' + (f' ({md(d)})' if dates else '')
    listing = lambda xs: '; '.join(xs) or 'none'
    known_text = (band_text(state, exceptions) if len(known) > known_max
                  else ', '.join(w['es'] for w in known[:known_max]) or 'none')
    if 0 <= known_max < len(known) <= KNOWN_LIST_MAX:  # trimmed listing (ChatGPT)
        shown = ', '.join(w['es'] for w in known[:known_max])
        known_text = (f'{shown} and {len(known) - known_max} more of the most common Spanish words' if shown
                      else f'the {len(known)} most common Spanish words')
    stamp = time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(time.time() if now is None else now))
    return (f'Spanish weave state{" (re-export about weekly)" if tail is None else ""} — Stage: {swlib.stage_for(state)}'
            f' | Active (use most; gloss in footer): {listing([entry(w, w["added"]) for w in active])}'
            f' | Shaky (use often; gloss in footer): {listing([entry(w, w["changed"]) for w in shaky])}'
            f' | Known (use freely; never gloss): {known_text}'
            f' | {tail or "Synced: " + stamp}')


def parse_state_line(line):
    """Inverse of state_line, for checking round trips: {stage, active, shaky, known, synced}."""
    sections = line.split(' | ')
    out = {'stage': int(re.search(r'Stage: (\d)', sections[0]).group(1))}
    entry = re.compile(r'^(.+?) = (.+), "([^"]*)"(?: \((\d+/\d+)\))?$')
    for section in sections[1:]:
        name, _, body = section.partition(': ')
        name = name.split(' ')[0].lower()
        if name in ('active', 'shaky'):
            out[name] = [] if body == 'none' else [entry.match(e).groups()[:3] for e in body.split('; ')]
        elif name == 'known':
            out['known'] = [] if body == 'none' else body if body.startswith('common Spanish words') else body.split(', ')
        elif name == 'synced':
            out['synced'] = body
    return out


def claude_ai(state, now=None, tail=None, known_max=KNOWN_LIST_MAX):
    """Personal preferences for claude.ai (Settings > Profile): the rules, then the state line."""
    return rules() + '\n\n' + state_line(state, now, tail=tail, known_max=known_max)


def chatgpt(state, now=None, limit=CHATGPT_LIMIT, tail=None):
    """Two ChatGPT custom-instructions fields, each within limit: (about you: the state line without dates, known
    words trimmed to fit; how to respond: the short rules)."""
    known = sum(w['status'] == 'known' for w in state['words'])
    if known > KNOWN_LIST_MAX:
        tries = [dict(exceptions=e) for e in range(swlib.EXCEPTIONS_MAX, -1, -5)]
    else:
        tries = [dict(known_max=k) for k in list(range(known, 0, -10)) + [0]]
    for kwargs in tries:
        line = state_line(state, now, dates=False, tail=tail, **kwargs)
        if len(line) <= limit:
            break
    return line, rules(short=True)


def mark_exported(state, target):
    state['exported'] = {'at': time.time(), 'version': swlib.version(state), 'target': target}


def log_chat_day(state, day=None):
    """Opt-in: count today as an "assumed" exposure day for every learning word (chats that can't be scanned)."""
    day = day or dt.date.today().isoformat()
    return sum(swlib.apply_event(state, w['es'], 'assumed', day) for w in state['words'] if w['status'] in ('active', 'shaky'))


# The deck goes in a column: Anki creates a deck named there (2.1.55+), but ignores a #deck: header naming a deck
# that doesn't exist yet (before 25.09).
ANKI_HEADERS = ['#separator:tab', '#html:false', '#notetype:Basic (and reversed card)', '#tags column:3',
                '#deck column:4']
ANKI_DECK = 'Spanish Weave'


def anki(state, every=False):
    """An Anki import file (File > Import; Anki 2.1.55+ reads the # headers): one "Basic (and reversed card)" note
    per word in a Spanish Weave deck, so Anki quizzes both directions on its own spaced-repetition schedule (FSRS).
    Front: the Spanish. Back: meaning, sound hint and note. Tags: spanish-weave and the word's status."""
    clean = lambda text: ' '.join(str(text).split())  # no tabs or newlines inside a field
    lines = list(ANKI_HEADERS)
    for w in state['words'] if every else swlib.introduced(state):
        back = f'{w["en"]} — "{w["hint"]}"' + (f' — {swlib.note(w["es"])}' if swlib.note(w['es']) else '')
        lines.append('\t'.join(clean(x) for x in (w['es'], back, f'spanish-weave spanish-weave::{w["status"]}', ANKI_DECK)))
    return '\n'.join(lines) + '\n'
