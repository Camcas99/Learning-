"""Placement test: a Yes/No vocabulary test with made-up words (Meara & Buxton 1987; the same idea as LexTALE-Esp,
Izura, Cuetos & Brysbaert 2014).

The learner says which words they know. Real words are sampled from four frequency bands of the word list; made-up
Spanish-looking words catch guessing, and every "yes" to one lowers the estimate. The result is about how many of the
listed words the learner already knows, which seeds the word state like setup's --known-top.
"""
import random

# Spanish-looking words that don't exist: saying you know one means some answers are guesses.
PSEUDOWORDS = ['plinda', 'garnoso', 'bolchar', 'caltubo', 'frenuz', 'sotralar', 'mardiga', 'pelmuza', 'ventuspa',
               'el brucho', 'la tendrilla', 'el carpucho']
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


def estimate(state, known):
    """From the item numbers (1-based) the learner knows: (estimated known words, real words known, made-up words
    claimed). Each band's share is corrected for guessing, (hits - false alarms) / (1 - false alarms), then scaled
    up to the band's size."""
    test = items(state)
    yes = {test[n - 1] for n in known if 1 <= n <= len(test)}
    fake = sum(band is None for _, band in yes)
    false_alarms = fake / len(PSEUDOWORDS)
    total = 0.0
    for i, (first, last) in enumerate(bands(len(state['words']))):
        hits = sum(band == i for _, band in yes) / sum(band == i for _, band in test)
        share = max(0.0, (hits - false_alarms) / (1 - false_alarms)) if false_alarms < 1 else 0.0
        total += share * (last - first + 1)
    return int(round(total, -1)), sum(band is not None for _, band in yes), fake
