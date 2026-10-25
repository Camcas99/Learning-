#!/usr/bin/env python3
"""Writes blocks/level-NN.md: ready-made Spanish Weave blocks for claude.ai and ChatGPT, no install needed.

Each level learns up to PER_LEVEL words and knows every word of the levels before it. The first levels take the
lexicon's words in its (frequency/usefulness) order. Words added to the list after the blocks were first published
(lexicon.csv's since column) come after them, one batch per version, oldest first, each batch starting a new level. So
a published level never changes its words: someone who pasted level 5 and moves to level 6 is never told that words
no block taught them are known. (With the plugin, new words are queued at their list rank instead, since its state
knows what each learner has met.) The claude.ai block names every known word up to 150; past that it says "the first N words of my Spanish
Weave list" and names the newest 40 (the list is not a general frequency rank, so it never says "most common"). The
ChatGPT field names as many as fit. Same rules source and state-line format as `sw.py export`, so the blocks can't
drift from it.
Usage: python3 scripts/make_blocks.py [--check]   (--check: fail if blocks/ is out of date or a block is too long)
"""
import argparse
import csv
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export  # noqa: E402
import swlib  # noqa: E402

PER_LEVEL = 25  # Spanish entries run longer than French ones, so 25 keep the ChatGPT field under 1,500
KNOWN_NAMED = swlib.COLLAPSE_AT  # known words named one by one, as in `sw.py export`; above this, the band
# claude.ai doesn't document a limit for personal preferences; stay well inside a few pages. The longest block is
# level 7, with all 150 known words named, at about 7,100 characters.
CLAUDE_AI_MAX = 7500
OUT = swlib.PLUGIN_ROOT / 'blocks'


def version_tuple(text):
    return tuple(int(n) for n in re.findall(r'\d+', text))


def level_words(lexicon, path=swlib.LEXICON):
    """The levels, each a list of up to PER_LEVEL words: the original words in list order, then each later version's
    additions (lexicon.csv's since column), oldest version first, each starting a new level."""
    with open(path, encoding='utf-8', newline='') as file:
        since = {swlib.key(r['es']): (r.get('since') or '').strip() for r in csv.DictReader(file)}
    chunk = lambda words: [words[i:i + PER_LEVEL] for i in range(0, len(words), PER_LEVEL)]
    batches = sorted({v for v in since.values() if v}, key=version_tuple)
    levels = chunk([w for w in lexicon if not since.get(swlib.key(w['es']))])
    for version in batches:
        levels += chunk([w for w in lexicon if since.get(swlib.key(w['es'])) == version])
    return levels


def level_order(lexicon, path=swlib.LEXICON):
    """Every word in level order."""
    return [w for level in level_words(lexicon, path) for w in level]


def level_state(level, lexicon):
    levels = level_words(lexicon)
    known = {swlib.key(w['es']) for chunk in levels[:level - 1] for w in chunk}
    active = {swlib.key(w['es']) for w in levels[level - 1]}
    words = []
    for w in (w for chunk in levels for w in chunk):
        k = swlib.key(w['es'])
        status = 'known' if k in known else 'active' if k in active else 'queue'
        words.append(dict(swlib.blank(w), status=status, added='2026-01-01' if status != 'queue' else ''))
    return {'stage': 1, 'stage_pinned': False, 'paused': False, 'words': words}


def block(level, levels, lexicon):
    state = level_state(level, lexicon)
    stage = swlib.stage_for(state)
    nxt = f'level-{level + 1:02d}.md' if level < levels else None
    tail = f'Level {level} of {levels}' + (f' (next: {nxt})' if nxt else '')
    claude = export.claude_ai(state, tail=tail, known_max=KNOWN_NAMED, recent=export.RECENT_NAMED)
    about, respond = export.chatgpt(state, tail=tail)
    learning = sum(w['status'] == 'active' for w in state['words'])
    known = f'the words of level{"s 1 to" if level > 2 else ""} {level - 1}' if level > 1 else 'none yet'
    text = (f'# Spanish Weave level {level} of {levels} (Stage {stage})\n\n'
            f'Learning: {learning} words. Known: {known}. '
            + (f'When these feel easy, paste [level {level + 1}]({nxt}) instead.\n\n' if nxt else 'This is the last level.\n\n')
            + '## claude.ai\n\nSettings > "Instructions for Claude" (on a computer, click your initials at the bottom '
              'left to open Settings; older layouts call the box "What personal preferences should Claude consider in '
              'responses?"). Copy the whole block with the copy button at its top right (on a phone the lines run off '
              'the screen, so selecting by hand cuts them off), then paste it in place of any older Spanish Weave '
              'block.\n\n'
            + f'```text\n{claude}\n```\n\n'
            + '## ChatGPT\n\nSettings > Personalization (in the phone app: Settings > Customize ChatGPT; turn on '
              '"Enable customization" if it is off). Copy each block with its copy button and paste it in place of '
              'what is in its box. Each block fits in 1,500 characters, the Free and Go limit; the first one alone uses '
              f'{len(respond):,}, so copy anything you want to keep from that box first. When you move up a level, only '
              'the "More about you" box changes.\n\n'
            + 'Paste into the "Custom instructions" box (older layout: "How would you like ChatGPT to respond?"):\n\n'
            + f'```text\n{respond}\n```\n\n'
            + 'Paste into the "More about you" box, under About you (older layout: "What would you like ChatGPT to know '
              'about you?"):\n\n'
            + f'```text\n{about}\n```\n')
    sizes = (len(claude), len(about), len(respond))
    return text, sizes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    lexicon = swlib.load_lexicon()
    levels = len(level_words(lexicon))
    stale, worst = [], [0, 0, 0]
    for level in range(1, levels + 1):
        text, sizes = block(level, levels, lexicon)
        worst = [max(a, b) for a, b in zip(worst, sizes)]
        if sizes[0] > CLAUDE_AI_MAX or max(sizes[1:]) > export.CHATGPT_LIMIT:
            sys.exit(f'level {level} too long: {sizes}')
        path = OUT / f'level-{level:02d}.md'
        if args.check:
            if not path.exists() or path.read_text() != text:
                stale.append(path.name)
        else:
            OUT.mkdir(exist_ok=True)
            path.write_text(text)
    if stale:
        sys.exit(f'blocks out of date: {", ".join(stale)}; run python3 scripts/make_blocks.py')
    print(f'{levels} levels; longest claude.ai block {worst[0]} chars, ChatGPT fields {worst[1]} / {worst[2]} '
          f'(limit {export.CHATGPT_LIMIT})')


if __name__ == '__main__':
    main()
