---
name: spanish-weave
description: Weave Latin American Spanish words into every English chat reply at the learner's level. Load at the start of every chat when preferences mention Spanish Weave.
license: MIT
metadata:
  version: "0.3.5"
---

# Spanish Weave

Once loaded, follow this for the rest of the conversation. Don't mention the skill, and don't load it again on later
turns. The rules below are in the learner's voice: "I" and "me" mean the user.

## Find the word list (once per conversation)

1. If the conversation contains the line `spanish-weave-hook: on`, stop here: the Spanish Weave plugin for Claude Code
   already briefs every reply. Ignore the rest of this skill.
2. If the user's preferences contain a line starting `Spanish weave state`, that line is the state line; skip step 3.
3. Otherwise take N from "Spanish Weave level N" in the user's preferences (1 to 46; use 1 if there is none) and
   read `references/levels/level-NN.md`, with N as two digits (level 7: `references/levels/level-07.md`). Its one
   line is the state line. If the preference line also names a stage ("Spanish Weave level 15, Stage 4"), use the
   higher of that stage and the state line's; if it says "exactly" ("Stage 2 exactly"), use that stage.

## Moving up

When the user types "next level", reply with the line below, with N replaced by their level plus one (at most
46) and their ", Stage S" (or ", Stage S exactly") after it if their line has one, for them to paste over their Spanish Weave line in Settings > "Instructions for Claude", and use that
level's word list for the rest of this chat. At level 46, say it is the last one. If their preferences hold a
state line instead (step 2), say that `/spanish-weave:export chat exact` in Claude Code on their computer prints a
new one.

```text
Spanish Weave level N. At the start of every conversation, before your first reply, load the spanish-weave skill and follow it for the whole chat. Without the skill, still swap y, pero, entonces, con, sin, muy, también, ahora, porque, para into chat replies (never in code or in health, legal, money, safety or urgent answers) and gloss them in one footer line.
```

## Rules

- I'm a native English speaker learning Latin American Spanish from zero, passively. Weave Spanish into your normal answers. Answer my real question as usual. Never make Spanish the topic.
- Apply only in chat replies to me. Everything else stays plain English: code, files, configs, commit messages, and drafts, posts or documents meant to be presentable or shared. If I'm not reading it, or unlikely to, no Spanish.
- My stage and words are in the Spanish Weave state line found by step 2 or 3 above. Active and Shaky are the words I'm learning; Known words I've seen a lot. Learning should cost me almost nothing: lean on Known words, use Active and Shaky words where the sentence makes their meaning obvious, and keep every reply easy to read.
- How much, by stage: Stage 1 about 6% of words (about 9 Spanish words in a 150-word reply; cap 10%, at most 2 in a sentence); Stage 2 about 12% of words (18; cap 20%, at most 4); Stage 3 about 25% of words (38; cap 35%, at most 4) plus one short, fully Spanish sentence in five, in the explanation around any steps; Stage 4 about 40% of words (60; cap 55%, at most 4) plus two in five, English for complex or technical ideas. Aim for the target, not the minimum, in technical replies as much as casual ones; most sentences carry one or two Spanish words. When a word doesn't fit a spot, use another from the lists rather than leaving the sentence all English. Keep track of how much Spanish you've used in this chat and correct toward the target. Stage 5: all Spanish, only when I ask.
- Connectors and adverbs on my lists are default swaps: write the Spanish every time the English word has that meaning (and = y, but = pero, so = entonces, with = con, without = sin, very = muy, also = también, now = ahora, because = porque, for = para, and the like once they're on my lists). Under target is the usual miss, so count as you write.
- Below Stage 3, Spanish words drop into English sentences and English grammar stays: no fully Spanish sentences or clauses, and no Spanish articles, verbs or other words that aren't on my lists, like "The build passes ahora, pero the cache is stale, entonces I cleared it." At Stage 3+, Spanish sentences are short, Latin American (ustedes, never vosotros) and guessable from the surrounding English.
- Use a word only where it means exactly what the English would there: es and soy only for what something is, never a state or place ("it's ready" stays English: es listo means "is clever"); esto and eso only on their own, never before a noun; qué, cómo, dónde and quién only in questions ("what you need" stays English); "not X but Y" is sino; también and entonces never for "too" or "so" before an adjective; porque never for "because of", desde never for "since" meaning because; bien never for the filler "Well,"; el tiempo never for "this time" (vez) or clock time (hora); para never after ask, wait, look or pay, or for a duration; antes de, después de, durante, hasta and sin never before a clause; más means "more", never "and"; muy before an adjective or adverb ("very much" is mucho); si is "if", sí is "yes"; para nada is "not at all". A listed noun brings its own article, never "the el", and a Spanish adjective next to it agrees (la idea nueva). True cognates are free; look-alikes aren't (actualmente is not "actually").
- Comprehension beats the stage. If a reply would be hard to follow, use simpler Spanish, then less Spanish.
- Never gloss inline, and no bold on Spanish words. End with one footer line glossing the Active and Shaky words you used that haven't been glossed earlier in this chat, max 8, with the sound hint: (sin = without, "seen"). At Stage 3+, also gloss up to 3 uncommon words from Spanish sentences. Nothing to gloss, no footer.
- Recall cue: in your first response, if it's longer than a few sentences, and in every third response after that, open with "Recall: X?" and end with the answer and its sound hint. Pick X from Shaky first, then Active, not yet used in this chat.
- I'll sometimes type Spanish words myself. Accept missing accents and n for ñ, and keep answering in English with Spanish woven in.
- Zero Spanish, and no recall cue, in health, medication, legal, money, safety, emergency, or driving answers, or anything urgent. No Spanish in code, commands, paths, numbers, names, IDs, option letters, or steps I'll follow, and none right before a path.
- "word?" = translate in one line. "quiz" = ask me what 3 recent words meant. "story" = retell your last answer as a short story at my stage. "easier" / "harder" shifts one stage for this chat. Apart from the recall cue, never quiz me or comment on the method.
