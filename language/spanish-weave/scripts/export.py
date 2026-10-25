"""Paste-ready Spanish Weave blocks for chats without hooks: claude.ai personal preferences and ChatGPT custom
instructions. One rules source (RULES) feeds both, and the skill of the chat-only plugin (spanish-weave-chat, written
by make_blocks.py), so the long and short versions can't drift apart.

The state line keeps the format of the original word-state line: Stage | Active | Shaky | Known | Synced.
"""
import datetime as dt
import re
import time

import swlib

CHATGPT_LIMIT = 1500   # characters per ChatGPT custom-instructions field (Free and Go; paid plans allow 5,000)
KNOWN_LIST_MAX = swlib.COLLAPSE_AT  # above this many known words, the state line names a rank band instead
RECENT_NAMED = 40      # in the band, the claude.ai block also names this many of the newest known words
LEARNING = ('active', 'shaky')
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
    ("My stage and words are in the Spanish Weave state line {where}. Active and Shaky are "
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


# Where the full rules say the state line is: below them in a pasted block; in the chat skill (SKILL.md), wherever its
# steps found it (the user's preferences, or a level file).
WHERE = 'below'
SKILL_WHERE = 'found by step 2 or 3 above'


def rules(short=False, skill=False):
    """The pasted rules: full for claude.ai, short for ChatGPT. skill: the full rules as bare bullets for the chat
    skill's SKILL.md, which has its own heading and finds the state line by its own steps."""
    fill = {'stages': stage_text(), 'stages_short': stage_text(short=True), 'where': SKILL_WHERE if skill else WHERE}
    parts = [(s if short else f).format(**fill) for f, s in RULES]
    if skill:
        return '\n'.join(f'- {p}' for p in parts if p)
    return ('SPANISH WEAVE. ' if short else 'SPANISH WEAVE\n\n') + ('\n' if short else '\n\n').join(
        p if short else f'- {p}' for p in parts if p)


# The one line for claude.ai and the Claude apps with the spanish-weave-chat plugin (Settings > "Instructions for
# Claude"). Preferences reach every chat, but a skill loads only when Claude chooses to, so the line asks for it
# every time and carries a few default swaps for a chat where it still doesn't load.
CHAT_LOAD = ('At the start of every conversation, before your first reply, load the spanish-weave skill and follow it '
             'for the whole chat.')
CHAT_FALLBACK = ('Without the skill, still swap y, pero, entonces, con, sin, muy, también, ahora, porque, para into '
                 'chat replies (never in code or in health, legal, money, safety or urgent answers) and gloss them in '
                 'one footer line.')


def chat_line(level):
    """The preference line for a published level: the skill reads that level's word list."""
    return f'Spanish Weave level {level}. {CHAT_LOAD} {CHAT_FALLBACK}'


def chat_exact(state, now=None):
    """The preference text for this learner's own words: the same line, then their state line (which the skill takes
    in place of a level's)."""
    return (f'Spanish Weave: my word list is the state line below. {CHAT_LOAD} {CHAT_FALLBACK}\n'
            + state_line(state, now, dates=False))


def md(day):
    return f'{int(day[5:7])}/{int(day[8:10])}' if day else ''


def named(xs, most):
    """Up to `most` of xs by name and a count of the rest ("a, b and 3 more"), or only the count ("5 words")."""
    shown = ', '.join(xs[:most])
    rest = len(xs) - len(xs[:most])
    return (shown + (f' and {rest} more' if rest else '')) if shown else f'{rest} words'


def band_text(state, exceptions=swlib.EXCEPTIONS_MAX, recent=RECENT_NAMED):
    """Known words as a stretch of the Spanish Weave list plus exceptions. The list is not a general frequency rank
    (ser and estar sit past 300), and claude.ai and ChatGPT can't see it, so this names the words it starts with and
    the newest known ones (the highest ranks in the band): "the first N words of my Spanish Weave list (...)"."""
    words = state['words']
    n, missing, extra = swlib.known_band(state)
    newest = [w['es'] for w in reversed(words[:n]) if w['status'] == 'known'][:recent]
    learning = any(w['status'] in LEARNING for w in words[:n])
    return (f'the first {n} words of my Spanish Weave list (it starts with {", ".join(w["es"] for w in words[:4])}'
            + (f'; the newest: {", ".join(newest)}' if newest else '') + ')'
            + (', except the Active and Shaky words above' if learning else '')
            + (f'{", and" if learning else ", except"} these not learned yet: {named(missing, exceptions)}' if missing else '')
            + (f'; also: {named(extra, exceptions)}' if extra else ''))


def state_line(state, now=None, known_max=KNOWN_LIST_MAX, dates=True, exceptions=swlib.EXCEPTIONS_MAX, tail=None,
               recent=RECENT_NAMED, hint_groups=LEARNING, gloss_groups=LEARNING, shaky_max=None):
    """The word-state line: Stage | Active | Shaky | Known | Synced, in the original state-line format.

    To fit a small box (ChatGPT): known_max, recent and exceptions name fewer known words; Active or Shaky entries
    left out of hint_groups lose the sound hint, and those left out of gloss_groups show only the Spanish; shaky_max
    keeps the newest shaky words and counts the rest."""
    words = state['words']
    by_added = lambda xs: sorted(xs, key=lambda w: w['added'])
    active = by_added([w for w in words if w['status'] == 'active'])
    shaky = by_added([w for w in words if w['status'] == 'shaky'])
    known = [w for w in words if w['status'] == 'known']
    hidden = max(0, len(shaky) - shaky_max) if shaky_max is not None else 0
    if hidden:
        kept = {id(w) for w in sorted(shaky, key=lambda w: w['changed'])[hidden:]}
        shaky = [w for w in shaky if id(w) in kept]

    def entry(w, group, day):
        text = (w['es'] if group not in gloss_groups
                else f'{w["es"]} = {w["en"]}' + (f', "{w["hint"]}"' if group in hint_groups else ''))
        return text + (f' ({md(day)})' if dates else '')

    def listing(xs, more=0):
        return '; '.join(xs + ([f'and {more} more' if xs else f'{more} words'] if more else [])) or 'none'

    if len(known) <= known_max:
        known_text = ', '.join(w['es'] for w in known) or 'none'
    elif len(known) > KNOWN_LIST_MAX:
        known_text = band_text(state, exceptions, recent)
    else:  # trimmed listing (ChatGPT): the newest known words by name, newest first, and a count of the rest
        shown = ', '.join(w['es'] for w in reversed(known[len(known) - known_max:]))
        known_text = (f'{shown} and {len(known) - known_max} earlier, more basic words from my Spanish Weave list' if shown
                      else f'{len(known)} basic words from the start of my Spanish Weave list')
    stamp = time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(time.time() if now is None else now))
    return (f'Spanish weave state{" (re-export about weekly)" if tail is None else ""} — Stage: {swlib.stage_for(state)}'
            f' | Active (use most; gloss in footer): {listing([entry(w, "active", w["added"]) for w in active])}'
            f' | Shaky (use often; gloss in footer): {listing([entry(w, "shaky", w["changed"]) for w in shaky], hidden)}'
            f' | Known (use freely; never gloss): {known_text}'
            f' | {tail or "Synced: " + stamp}')


def parse_state_line(line):
    """Inverse of state_line, for checking round trips: {stage, active, shaky, known, synced}. Active and Shaky
    entries are (es, en, hint), with None for a part the line left out; a band or trimmed Known list stays text."""
    sections = line.split(' | ')
    out = {'stage': int(re.search(r'Stage: (\d)', sections[0]).group(1))}
    entry = re.compile(r'^(.+?)(?: = (.+?))?(?:, "([^"]*)")?(?: \((\d+/\d+)\))?$')
    count = re.compile(r'^(?:and \d+ more|\d+ words)$')
    for section in sections[1:]:
        name, _, body = section.partition(': ')
        name = name.split(' ')[0].lower()
        if name in ('active', 'shaky'):
            out[name] = [] if body == 'none' else [entry.match(e).groups()[:3] for e in body.split('; ')
                                                   if not count.match(e)]
        elif name == 'known':
            out['known'] = ([] if body == 'none' else body
                            if body.startswith('the first ') or body.endswith(' my Spanish Weave list') else body.split(', '))
        elif name == 'synced':
            out['synced'] = body
    return out


def claude_ai(state, now=None, tail=None, known_max=KNOWN_LIST_MAX, recent=RECENT_NAMED):
    """Instructions for claude.ai (Settings > "Instructions for Claude"): the rules, then the state line."""
    return rules() + '\n\n' + state_line(state, now, tail=tail, known_max=known_max, recent=recent)


def chatgpt(state, now=None, limit=None, tail=None):
    """Two ChatGPT custom-instructions fields: (about you: the state line without dates; how to respond: the short
    rules). The state line takes the first of these that fits the limit, each step keeping the ones before it:
    fewer known words named; no sound hints for Shaky, then Active words; no meanings for Shaky, then Active words;
    fewer Shaky words, newest kept. When even the last doesn't fit, it is returned anyway and the caller says so."""
    limit = CHATGPT_LIMIT if limit is None else limit
    known = sum(w['status'] == 'known' for w in state['words'])
    shaky = sum(w['status'] == 'shaky' for w in state['words'])
    if known > KNOWN_LIST_MAX:
        tries = [dict(recent=r, exceptions=e) for r in (30, 20, 10, 0) for e in range(swlib.EXCEPTIONS_MAX, -1, -5)]
    else:
        tries = [dict(known_max=k) for k in list(range(known, 0, -10)) + [0]]
    least = tries[-1]
    tries += [dict(least, hint_groups=groups) for groups in (('active',), ())]
    tries += [dict(least, hint_groups=(), gloss_groups=groups) for groups in (('active',), ())]
    tries += [dict(least, hint_groups=(), gloss_groups=(), shaky_max=n) for n in range(shaky - 1, -1, -1)]
    for kwargs in tries:
        line = state_line(state, now, dates=False, tail=tail, **kwargs)
        if len(line) <= limit:
            break
    return line, rules(short=True)


def mark_exported(state, target, level=None):
    """Records an export, for the hook's reminder (weave.export_notice); level: the level a chat line named."""
    state['exported'] = {'at': time.time(), 'version': swlib.version(state), 'target': target}
    if level:
        state['exported']['level'] = level


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
