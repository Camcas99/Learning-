"""Placement test: a Yes/No vocabulary test with made-up words (Meara & Buxton 1987; the same idea as LexTALE-Esp,
Izura, Cuetos & Brysbaert 2014).

The learner says which words they know. Real words are sampled from four frequency bands of the word list; made-up
Spanish-looking words catch guessing, and every "yes" to one lowers the estimate. The result is about how many of the
listed words the learner already knows, which seeds the word state like setup's --known-top.
"""
import random

# Spanish-looking words that don't exist: saying you know one means some answers are guesses.
# Checked against a 1.2-million-form Spanish frequency list and an English word list: none occurs, and none is one
# letter away from a common word in either language (brucho, an earlier choice, turned out to be a real word).
PSEUDOWORDS = ['nurpeño', 'quirmoso', 'bolchar', 'caltubo', 'frenuz', 'sotralar', 'tirguela', 'pelmuza', 'ventuspa',
               'el larbizo', 'la pindrolla', 'el brontejo']
PER_BAND = 8
EDGES = [1, 101, 251, 501]  # first rank of each band; the last band runs to the end of the list


def bands(total):
    """(first rank, last rank) of each frequency band."""
    edges = [e for e in EDGES if e <= total] + [total + 1]
    return list(zip(edges, [e - 1 for e in edges[1:]]))


def items(state):
    """The test, the same every time for a given word state: [(word, band index, or None for a made-up word)]."""
    rng = random.Random('placement:' + str(state.get('created', '')))
    words = [w['es'] for w in state['words']]
    test = [(w, i) for i, (first, last) in enumerate(bands(len(words)))
            for w in rng.sample(words[first - 1:last], min(PER_BAND, last - first + 1))]
    test += [(p, None) for p in PSEUDOWORDS]
    rng.shuffle(test)
    return test


TOO_MANY_FAKES = 3  # picking this many made-up words means the answers are mostly guesses: no estimate


def estimate(state, known):
    """From the item numbers (1-based) the learner knows: (estimated known words, real words known, made-up words
    picked). Each band's share is corrected for guessing, (hits - false alarms) / (1 - false alarms), and scaled to the
    band's size. The bands are cumulative: once a band is mostly unknown, rarer bands don't count, so a few cognates
    from the last band ("el repositorio") can't mark the most common words known."""
    test = items(state)
    yes = {test[n - 1] for n in known if 1 <= n <= len(test)}
    fake = sum(band is None for _, band in yes)
    real = len(yes) - fake
    if fake >= TOO_MANY_FAKES:
        return 0, real, fake
    # One extra made-up "yes" and "no" are assumed (Laplace smoothing), so lucky guessing can't read as a perfect zero.
    false_alarms = (fake + 1) / (len(PSEUDOWORDS) + 2)
    total = 0.0
    for i, (first, last) in enumerate(bands(len(state['words']))):
        hits = sum(band == i for _, band in yes) / sum(band == i for _, band in test)
        share = max(0.0, (hits - false_alarms) / (1 - false_alarms))
        total += share * (last - first + 1)
        if share < 0.5:
            break
    return min(int(round(total, -1)), len(state['words'])), real, fake  # never more than the list holds
