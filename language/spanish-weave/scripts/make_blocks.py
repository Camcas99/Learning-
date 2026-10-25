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

It also writes the chat-only plugin next to this one (../spanish-weave-chat), for claude.ai and the Claude apps: its
plugin.json (with this plugin's version), LICENSE (a copy of this one), skills/spanish-weave/SKILL.md (the same rules)
and one file per level holding that level's state line. Only its README.md is written by hand.
Usage: python3 scripts/make_blocks.py [--check]   (--check: fail if blocks/ or the chat plugin is out of date, a
                                                   block is too long, or the two plugins' versions differ)
"""
import argparse
import csv
import json
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

# The chat-only plugin: skills only, so claude.ai and the Claude apps (iPhone included) can install it.
CHAT = swlib.PLUGIN_ROOT.parent / 'spanish-weave-chat'
SKILL = 'skills/spanish-weave'  # the skill's folder in it; the folder name must be the skill's name
SKILL_NAME = 'spanish-weave'
SKILL_DESCRIPTION = ("Weave Latin American Spanish words into every English chat reply at the learner's level. Load at "
                     "the start of every chat when preferences mention Spanish Weave.")
DESCRIPTION_MAX = 200  # claude.ai's help center limit for an uploaded skill (the skill spec allows 1,024)
SKILL_LINES_MAX = 500  # the skill guides' limit for SKILL.md
# claude.ai won't install a plugin with a top-level bin/, commands would load in chat as extra skills, and the rest
# would do nothing there.
NOT_IN_CHAT = ('bin', 'hooks', 'commands', 'agents', 'scripts', '.mcp.json')
README_WORDS = 40  # the chat plugin's hand-written README says what it does and how to install it


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


def nearest_level(state, lexicon=None):
    """The published level closest to a plugin learner's words, for `sw.py export --chat`: the level whose Known words
    (every word of the levels before it) best match the words known in state. Calling a word Known that isn't counts
    twice as much as leaving out one that is, since a word used freely without a gloss costs more than a gloss
    someone didn't need; ties go to the lower level. So a level counts as passed once more than two thirds of its
    words are known, and one shaky word from an early level doesn't hold anyone back."""
    levels = level_words(lexicon or swlib.load_lexicon())
    known = {swlib.key(w['es']) for w in state['words'] if w['status'] == 'known'}
    cost = sum(swlib.key(w['es']) in known for level in levels for w in level)  # level 1: every known word left out
    best, lowest = 1, cost
    for n, level in enumerate(levels[:-1], 2):  # level n calls the words of levels 1 to n - 1 Known
        cost += sum(-1 if swlib.key(w['es']) in known else 2 for w in level)
        if cost < lowest:
            best, lowest = n, cost
    return best


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


def plugin_version(root=swlib.PLUGIN_ROOT):
    """The version in a plugin's .claude-plugin/plugin.json, or None."""
    data = swlib.read_json(root / '.claude-plugin' / 'plugin.json', {})
    return data.get('version') if isinstance(data, dict) else None


def level_line(level, levels, lexicon):
    """A level's state line for the skill: the claude.ai block's line without its placeholder dates and file link."""
    return export.state_line(level_state(level, lexicon), dates=False, tail=f'Level {level} of {levels}')


def skill_text(version, levels):
    """SKILL.md: how the skill finds the learner's state line, how they move up a level, then the pasted rules."""
    return f'''---
name: {SKILL_NAME}
description: {SKILL_DESCRIPTION}
license: MIT
metadata:
  version: "{version}"
---

# Spanish Weave

Once loaded, follow this for the rest of the conversation. Don't mention the skill, and don't load it again on later
turns. The rules below are in the learner's voice: "I" and "me" mean the user.

## Find the word list (once per conversation)

1. If the conversation contains the line `{swlib.HOOK_MARKER}`, stop here: the Spanish Weave plugin for Claude Code
   already briefs every reply. Ignore the rest of this skill.
2. If the user's preferences contain a line starting `Spanish weave state`, that line is the state line; skip step 3.
3. Otherwise take N from "Spanish Weave level N" in the user's preferences (1 to {levels}; use 1 if there is none) and
   read `references/levels/level-NN.md`, with N as two digits (level 7: `references/levels/level-07.md`). Its one
   line is the state line.

## Moving up

When the user types "next level", reply with the line below, with N replaced by their level plus one (at most
{levels}), for them to paste over their Spanish Weave line in Settings > "Instructions for Claude", and use that
level's word list for the rest of this chat. At level {levels}, say it is the last one. If their preferences hold a
state line instead (step 2), say that `/spanish-weave:export chat exact` in Claude Code on their computer prints a
new one.

```text
{export.chat_line("N")}
```

## Rules

{export.rules(skill=True)}
'''


def chat_files(lexicon, levels, version):
    """{path in the chat plugin: text} for every file make_blocks writes there."""
    manifest = {
        'name': 'spanish-weave-chat',
        'displayName': 'Spanish Weave for chat',
        'version': version,  # always this plugin's: claude.ai and Claude Code only pull a changed version
        'description': ("Weaves a few Latin American Spanish words into Claude's replies on claude.ai and the Claude "
                        'apps (iPhone included), at a level you set in one line of your preferences. Skills only: no '
                        'hooks, no scripts.'),
        'author': {'name': 'Camcas99'},
        'repository': 'https://github.com/Camcas99/Learning-',
        'license': 'MIT',
        'keywords': ['spanish', 'language-learning', 'skills'],
    }
    files = {'.claude-plugin/plugin.json': json.dumps(manifest, indent=2, ensure_ascii=False) + '\n',
             'LICENSE': (swlib.PLUGIN_ROOT / 'LICENSE').read_text(encoding='utf-8'),
             f'{SKILL}/SKILL.md': skill_text(version, levels)}
    for level in range(1, levels + 1):
        files[f'{SKILL}/references/levels/level-{level:02d}.md'] = level_line(level, levels, lexicon) + '\n'
    return files


def frontmatter(text):
    """(top-level fields, raw frontmatter text) of a SKILL.md; nested fields (metadata) stay out of the dict."""
    _, head, _ = text.split('---\n', 2)
    fields = dict(line.split(': ', 1) for line in head.splitlines() if ': ' in line and not line.startswith(' '))
    return fields, head


def skill_problems(text):
    """What breaks the published limits for a skill's SKILL.md (claude.ai, the Agent Skills spec)."""
    fields, head = frontmatter(text)
    name, description = fields.get('name', ''), fields.get('description', '')
    problems = []
    if name != SKILL_NAME or SKILL.rsplit('/', 1)[1] != name or not re.fullmatch(r'[a-z0-9-]{1,64}', name):
        problems.append(f'the name must be lowercase letters, digits and hyphens, and match its folder: {name}')
    if 'claude' in name or 'anthropic' in name:
        problems.append(f'the name may not contain "claude" or "anthropic": {name}')
    if not description or len(description) > DESCRIPTION_MAX:
        problems.append(f'the description must be 1 to {DESCRIPTION_MAX} characters, not {len(description)}')
    if ': ' in description or ' #' in description or description[:1] in '\'"[{&*!|>%@`':
        problems.append('the description must read as plain YAML text (no ": ", " #" or leading quote or symbol)')
    if '<' in head or '>' in head:
        problems.append('no XML tags (no < or >) in the frontmatter')
    if fields.get('license') != 'MIT':
        problems.append('license: MIT')
    if len(text.splitlines()) >= SKILL_LINES_MAX:
        problems.append(f'SKILL.md must stay under {SKILL_LINES_MAX} lines')
    return problems


def chat_problems(files, version, root=CHAT):
    """What is wrong with the chat plugin folder: a version other than this plugin's, generated files missing or out of
    date, level files no published level matches, folders it must not have, or a missing README."""
    problems = []
    have = plugin_version(root)
    if have != version:
        problems.append(f'its version is {have}, but spanish-weave is {version}; they must match')
    stale = [name for name, text in files.items()
             if not (root / name).is_file() or (root / name).read_text(encoding='utf-8') != text]
    if stale:
        more = f' and {len(stale) - 4} more' if len(stale) > 4 else ''
        problems.append(f'out of date: {", ".join(stale[:4])}{more}')
    folder = root / SKILL / 'references' / 'levels'
    extra = sorted(p.name for p in folder.iterdir() if f'{SKILL}/references/levels/{p.name}' not in files) \
        if folder.is_dir() else []
    if extra:
        problems.append(f'not a published level, remove: {", ".join(extra)}')
    present = [name for name in NOT_IN_CHAT if (root / name).exists()]
    if present:
        problems.append(f'a chat plugin has no {", ".join(present)} (claude.ai refuses bin/; commands load as skills)')
    readme = root / 'README.md'
    if not readme.is_file() or len(readme.read_text(encoding='utf-8').split()) < README_WORDS:
        problems.append(f'README.md, written by hand, of {README_WORDS} words or more')
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    lexicon = swlib.load_lexicon()
    levels = len(level_words(lexicon))
    version = plugin_version()
    if not version:
        sys.exit(f'no version in {swlib.PLUGIN_ROOT / ".claude-plugin" / "plugin.json"}')
    files = chat_files(lexicon, levels, version)
    problems = skill_problems(files[f'{SKILL}/SKILL.md'])
    if problems:
        sys.exit(f'{SKILL}/SKILL.md breaks the skill limits: {"; ".join(problems)}')
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
    if not args.check:
        for name, text in files.items():
            path = CHAT / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
    problems = chat_problems(files, version)
    if problems:
        sys.exit(f'{CHAT.name}: {"; ".join(problems)}' + ('; run python3 scripts/make_blocks.py' if args.check else ''))
    print(f'{levels} levels; longest claude.ai block {worst[0]} chars, ChatGPT fields {worst[1]} / {worst[2]} '
          f'(limit {export.CHATGPT_LIMIT}); {CHAT.name} {version}: SKILL.md and {levels} level files')


if __name__ == '__main__':
    main()
