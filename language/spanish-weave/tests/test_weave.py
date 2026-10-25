"""Offline tests for the hook, word state, native host and setup. Run: python3 -m unittest discover -s tests"""
import argparse
import contextlib
import datetime as dt
import io
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
os.environ['SPANISH_WEAVE_NO_REFRESH'] = '1'
for name in ('CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_SESSION_ATTENDED', 'SPANISH_WEAVE_FORCE', 'SPANISH_WEAVE_OFF'):
    os.environ.pop(name, None)  # tests set these explicitly

import swlib  # noqa: E402
import weave  # noqa: E402
import sw_host  # noqa: E402
import sw  # noqa: E402
import export  # noqa: E402
import hints  # noqa: E402
import make_blocks  # noqa: E402
import placement  # noqa: E402


def line(text, day='2026-10-09', sidechain=False):
    return json.dumps({'type': 'assistant', 'isSidechain': sidechain, 'timestamp': day + 'T12:00:00',
                       'message': {'content': [{'type': 'text', 'text': text}]}})


# How Claude Code 2.1.299 marks a prompt's source in a transcript (seen in real terminal and desktop sessions).
TYPED = {'origin': {'kind': 'human'}, 'turnOrigin': 'human', 'promptSource': 'typed'}  # terminal
TYPED_DESKTOP = {'origin': {'kind': 'human'}, 'promptSource': 'sdk'}  # desktop app, before turnOrigin was recorded
FROM_SESSION = {'turnOrigin': 'sdk', 'promptSource': 'sdk'}  # the first prompt of a session another session started
SCHEDULED = {'origin': {'kind': 'task-notification', 'subkind': 'scheduled-trigger', 'fireReason': 'scheduled'},
             'turnOrigin': 'scheduled', 'promptSource': 'system'}
NOTICE = {'origin': {'kind': 'task-notification'}, 'turnOrigin': 'task_notification', 'promptSource': 'system'}


def prompt(text, day='2026-10-09', **marks):
    return json.dumps({'type': 'user', 'isSidechain': False, 'timestamp': day + 'T11:00:00',
                       'message': {'role': 'user', 'content': text}, **marks})


def word(es, status='known'):
    return {'es': es, 'en': 'meaning', 'hint': 'hint', 'status': status, 'added': '2026-10-01', 'changed': '',
            'days': [], 'last_bad': ''}


class Home(unittest.TestCase):
    """Each test gets its own state dir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {'SPANISH_WEAVE_HOME': str(self.home / 'sw'),
                                                'CLAUDE_CONFIG_DIR': str(self.home / 'claude')})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()


class Matching(unittest.TestCase):
    def hits(self, es, text):
        return bool(swlib.pattern(es).search(swlib.norm(text)))

    def test_word_matching(self):
        self.assertTrue(self.hits('el error', 'el error is gone'))
        self.assertFalse(self.hits('el error', 'the error is gone'))  # unaccented nouns need a Spanish determiner
        self.assertTrue(self.hits('el error', 'los errores are gone'))
        self.assertTrue(self.hits('la canción', 'that canción is great'))  # accented ones can't be English
        self.assertTrue(self.hits('sin', 'sin the cache'))
        self.assertFalse(self.hits('sin', 'call sin(x) here'))
        self.assertTrue(self.hits('y', 'the build passes, y the cache is warm'))
        self.assertFalse(self.hits('y', 'plot x and y'))
        self.assertFalse(self.hits('y', 'label the y-axis'))
        self.assertFalse(self.hits('o', 'runs in O(n) time'))
        self.assertTrue(self.hits('sí', 'sí, it failed'))
        self.assertFalse(self.hits('si', 'sí, it failed'))
        self.assertTrue(self.hits('todo', 'todo works now'))
        self.assertFalse(self.hits('todo', 'leave a TODO here'))
        self.assertFalse(self.hits('todo', 'TODO: fix later'))
        self.assertFalse(self.hits('algo', 'the algo is off'))
        self.assertIn('todos', swlib.UNMEASURABLE)  # English TODOs come in too many forms to tell apart
        self.assertFalse(self.hits('es', 'switch to ES modules'))
        self.assertFalse(self.hits('en', 'en route to prod'))
        self.assertFalse(self.hits('con', 'install conda'))


class Hints(unittest.TestCase):
    def test_respelling_rules(self):
        cases = {
            'y': 'ee', 'hay': 'eye', 'muy': 'mwee', 'estoy': 'es-TOY',  # a final y is a vowel, and counts as a consonant for stress
            'también': 'tahm-BYEN', 'difícil': 'dee-FEE-seel', 'día': 'DEE-ah',  # written accents win
            'entonces': 'en-TOHN-ses', 'ciudad': 'syoo-DAHD', 'feliz': 'feh-LEES',  # stress by the last letter
            'aquí': 'ah-KEE', 'guerra': 'GEH-rrah', 'seguir': 'seh-GEER', 'agua': 'AH-gwah', 'pingüino': 'peen-GWEE-noh',
            'gente': 'HEN-teh', 'trabajo': 'trah-BAH-hoh', 'llamar': 'yah-MAHR', 'mañana': 'mah-NYAH-nah',
            'vez': 'bes', 'nuevo': 'NWEH-boh', 'rápido': 'RRAH-pee-doh', 'siempre': 'SYEM-preh',
            'éxito': 'EK-see-toh', 'excelente': 'ek-seh-LEN-teh', 'México': 'MEH-hee-koh', 'bailar': 'bye-LAHR',
            'reloj': 'rreh-LOH',
            'rápidamente': 'RRAH-pee-dah-MEN-teh', 'el problema': 'el proh-BLEH-mah', 'una idea': 'OO-nah ee-DEH-ah',
            # In a phrase a written accent shows a one-syllable word's stress, so por qué doesn't read like porque.
            'por qué': 'por KEH', 'no sé': 'noh SEH', 'una vez más': 'OO-nah bes MAHS', 'un poco': 'oon POH-koh',
            'xilófono': 'see-LOH-foh-noh', 'texto': 'TEKS-toh', 'mexicana': 'meh-hee-KAH-nah', 'Texas': 'TEH-hahs',
            'Oaxaca': 'wah-HAH-kah',
        }
        self.assertEqual({word: hints.respell(word) for word in cases}, cases)


class Scan(unittest.TestCase):
    def test_scan_dedupes_and_skips(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chat = root / 'proj' / 'a.jsonl'
            chat.parent.mkdir()
            chat.write_text('\n'.join([
                line('Done, y the build passes.'),
                line('Done, y the build passes.'),  # forked copy: counted once
                line('y inside a subagent', sidechain=True),
                line('Run `git add y` then check https://x.test/y'),
                line('Spanish Weave notes: y, entonces'),
                line('Old reply, y it predates install.', day='2026-09-01'),
            ]) + '\n' + line('partial entonces'))  # no newline: half-written
            (root / 'proj' / 's' / 'subagents').mkdir(parents=True)
            (root / 'proj' / 's' / 'subagents' / 'b.jsonl').write_text(line('y entonces') + '\n')
            index = swlib.scan(['y', 'entonces', 'solo'], {}, root, start='2026-09-19')
            self.assertEqual(index['words']['y'], {'n': 1, 'days': ['2026-10-09']})
            self.assertEqual(index['words']['entonces'], {'n': 0, 'days': []})
            self.assertNotIn('solo', index['words'])  # spelled like English "solo": never counted
            with open(chat, 'a') as file:
                file.write('\n' + line('Y again, y entonces.', day='2026-10-11') + '\n')
            index = swlib.scan(['y', 'entonces', 'solo'], index, root, start='2026-09-19')
            self.assertEqual(index['words']['y'], {'n': 2, 'days': ['2026-10-09', '2026-10-11']})
            self.assertEqual(index['words']['entonces']['n'], 2)  # the finished partial line and the new one


class Rules(Home):
    def test_lexicon_is_well_formed(self):
        words = swlib.load_lexicon()
        self.assertEqual(len({swlib.key(w['es']) for w in words}), len(words))
        for w in words:
            self.assertTrue(w['en'] and w['hint'], w)
            self.assertRegex(w['hint'], r'^[A-Za-z -]+$', w)  # plain letters; capitals mark the stressed syllable
        self.assertEqual([w['es'] for w in words if w['hint'] != hints.respell(w['es'])], [])  # hints follow the rules

    def test_new_state_starts_small(self):
        state = swlib.new_state('2026-10-01')
        active = [w['es'] for w in state['words'] if w['status'] == 'active']
        self.assertEqual(active, ['y', 'pero', 'entonces', 'con', 'sin'])  # 5 new a day
        self.assertEqual(swlib.stage_for(state), 1)
        for day in ('2026-10-02', '2026-10-03', '2026-10-04', '2026-10-05'):
            swlib.promote(state, day, {})
        self.assertEqual(sum(w['status'] == 'active' for w in state['words']), swlib.WINDOW)  # full at 20

    def test_graduation_needs_three_clean_days(self):
        state = swlib.new_state('2026-10-01')
        chat = {'y': {'n': 5, 'days': ['2026-10-01', '2026-10-02']}}
        swlib.promote(state, '2026-10-02', chat)
        self.assertEqual(swlib.find(state, 'y')['status'], 'active')  # 2 days
        swlib.apply_event(state, 'y', 'seen', '2026-10-03')  # extension day + chat days
        swlib.promote(state, '2026-10-03', chat)
        self.assertEqual(swlib.find(state, 'y')['status'], 'known')

    def test_peek_blocks_graduation_and_assumed_alone_never_graduates(self):
        state = swlib.new_state('2026-10-01')
        chat = {'pero': {'n': 3, 'days': ['2026-10-01', '2026-10-02', '2026-10-03']}}
        swlib.apply_event(state, 'pero', 'peek', '2026-10-02')
        swlib.promote(state, '2026-10-03', chat)
        self.assertEqual(swlib.find(state, 'pero')['status'], 'active')  # peek inside the last 3 days
        chat['pero']['days'] += ['2026-10-04', '2026-10-05']
        swlib.promote(state, '2026-10-05', chat)
        self.assertEqual(swlib.find(state, 'pero')['status'], 'known')  # last 3 days (03-05) are peek-free
        for day in ('2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04'):
            swlib.apply_event(state, 'entonces', 'assumed', day)
        swlib.promote(state, '2026-10-04', {})
        self.assertEqual(swlib.find(state, 'entonces')['status'], 'active')  # 4 assumed days, never seen
        swlib.apply_event(state, 'entonces', 'seen', '2026-10-05')
        swlib.promote(state, '2026-10-05', {})
        self.assertEqual(swlib.find(state, 'entonces')['status'], 'known')

    def test_flip_makes_shaky_and_recovers_after_7_clean_days(self):
        state = swlib.new_state('2026-10-01')
        swlib.apply_event(state, 'con', 'flip', '2026-10-04')
        swlib.promote(state, '2026-10-10', {})
        self.assertEqual(swlib.find(state, 'con')['status'], 'shaky')
        swlib.apply_event(state, 'con', 'peek', '2026-10-09')  # restarts the clock
        swlib.promote(state, '2026-10-16', {})
        self.assertEqual(swlib.find(state, 'con')['status'], 'shaky')  # a clean week, but not seen since: no evidence
        swlib.apply_event(state, 'con', 'seen', '2026-10-12')
        swlib.promote(state, '2026-10-15', {})
        self.assertEqual(swlib.find(state, 'con')['status'], 'shaky')
        swlib.promote(state, '2026-10-16', {})
        self.assertEqual(swlib.find(state, 'con')['status'], 'known')
        swlib.apply_event(state, 'solo', 'asked', '2026-10-16')  # chat can't count solo: a clean week is enough
        swlib.promote(state, '2026-10-23', {})
        self.assertEqual(swlib.find(state, 'solo')['status'], 'known')

    def test_merge_takes_corrected_glosses(self):
        state = swlib.new_state('2026-10-01')
        swlib.find(state, 'pero').update(en='old gloss', hint='old hint')
        before = swlib.version(state)
        swlib.merge_lexicon(state)
        self.assertEqual((swlib.find(state, 'pero')['en'], swlib.find(state, 'pero')['hint']), ('but', 'PEH-roh'))
        self.assertNotEqual(swlib.version(state), before)  # the extension refetches swaps with the new gloss

    def test_pause_keeps_the_version_so_cached_swaps_survive(self):
        """The extension clears its swap cache when the version changes. A pause reaches it as its own field, which
        stops and starts pages, so pausing and resuming must not cost a model call per passage afterwards."""
        state = swlib.new_state('2026-10-01')
        before = swlib.version(state)
        state['paused'] = True
        self.assertEqual(swlib.version(state), before)
        self.assertTrue(swlib.public_state(state)['paused'])

    def test_known_word_peeked_twice_in_a_week_becomes_shaky(self):
        state = swlib.new_state('2026-10-01')
        swlib.apply_event(state, 'sin', 'known', '2026-10-01')
        swlib.apply_event(state, 'sin', 'peek', '2026-10-02')
        self.assertEqual(swlib.find(state, 'sin')['status'], 'known')
        swlib.apply_event(state, 'sin', 'peek', '2026-10-02')  # same day: once
        self.assertEqual(swlib.find(state, 'sin')['status'], 'known')
        swlib.apply_event(state, 'sin', 'peek', '2026-10-08')
        self.assertEqual(swlib.find(state, 'sin')['status'], 'shaky')

    def test_refill_cap_and_shaky_block(self):
        state = swlib.new_state('2026-10-01')
        for day in ('2026-10-02', '2026-10-03', '2026-10-04'):
            swlib.promote(state, day, {})
        for es in ('y', 'pero', 'entonces', 'con', 'sin', 'muy'):
            swlib.apply_event(state, es, 'known', '2026-10-05')
        swlib.promote(state, '2026-10-05', {})
        self.assertEqual(sum(w['status'] == 'active' for w in state['words']), swlib.WINDOW - 1)  # 20-6+5
        for es in ('también', 'ahora', 'para', 'porque', 'siempre'):
            swlib.apply_event(state, es, 'flip', '2026-10-06')
        before = sum(w['status'] != 'queue' for w in state['words'])
        swlib.promote(state, '2026-10-06', {})
        self.assertEqual(sum(w['status'] != 'queue' for w in state['words']), before)  # 5 shaky: no new words

    def test_stage_auto_and_pinned(self):
        state = swlib.new_state('2026-10-01')
        stages = []
        for i, w in enumerate(state['words'][:400], 1):
            swlib.apply_event(state, w['es'], 'known', '2026-10-01')
            if i in (39, 40, 149, 150, 399, 400):
                stages.append(swlib.stage_for(state))
        self.assertEqual(stages, [1, 2, 2, 3, 3, 4])
        state['stage'], state['stage_pinned'] = 1, True
        self.assertEqual(swlib.stage_for(state), 1)

    def test_find_accepts_bare_nouns_case_and_missing_accents(self):
        state = swlib.new_state('2026-10-01')
        self.assertEqual(swlib.find(state, 'Problema')['es'], 'el problema')
        self.assertEqual(swlib.find(state, 'Canción')['es'], 'la canción')
        self.assertEqual(swlib.find(state, 'tambien')['es'], 'también')
        self.assertEqual(swlib.find(state, 'cancion')['es'], 'la canción')
        self.assertEqual(swlib.find(state, 'ano')['es'], 'el año')
        self.assertEqual(swlib.find(state, 'manana')['es'], 'mañana')  # the exact spelling beats "la mañana"
        self.assertEqual(swlib.find(state, 'si')['es'], 'si')  # "si" (if) is its own word, not a missing-accent "sí"
        self.assertIsNone(swlib.find(state, 'nope'))

    def test_assumed_days_never_bring_a_shaky_word_back(self):
        state = swlib.new_state('2026-10-01')
        swlib.apply_event(state, 'el tiempo', 'asked', '2026-10-02')  # /spanish-weave:learn on a word never met
        export.log_chat_day(state, '2026-10-10')
        swlib.promote(state, '2026-10-10', {})
        self.assertEqual(swlib.find(state, 'el tiempo')['status'], 'shaky')  # a clean week, but never really seen
        swlib.apply_event(state, 'el tiempo', 'seen', '2026-10-11')
        swlib.promote(state, '2026-10-11', {})
        self.assertEqual(swlib.find(state, 'el tiempo')['status'], 'known')

    def test_late_events_never_override_a_newer_change(self):
        state = swlib.new_state('2026-10-01')
        swlib.apply_event(state, 'pero', 'known', '2026-10-09')
        swlib.apply_event(state, 'pero', 'flip', '2026-10-01')  # queued in a browser that stayed closed for a week
        pero = swlib.find(state, 'pero')
        self.assertEqual((pero['status'], pero['changed'], pero['box']), ('known', '2026-10-09', 3))
        swlib.apply_event(state, 'con', 'asked', '2026-10-08')  # learn
        swlib.apply_event(state, 'con', 'seen', '2026-10-09')
        swlib.apply_event(state, 'con', 'flip', '2026-10-02')  # older than the learn
        swlib.promote(state, '2026-10-10', {})
        con = swlib.find(state, 'con')
        self.assertEqual((con['status'], con['changed'], con['last_bad']), ('shaky', '2026-10-08', '2026-10-08'))

    def test_peeks_from_learning_days_never_count_against_a_known_word(self):
        state = swlib.new_state('2026-10-01')
        swlib.apply_event(state, 'sin', 'peek', '2026-10-01')  # hovered on its first day: the normal way to learn it
        for day in ('2026-10-02', '2026-10-03', '2026-10-04'):
            swlib.apply_event(state, 'sin', 'seen', day)
        swlib.promote(state, '2026-10-04', {})
        self.assertEqual(swlib.find(state, 'sin')['status'], 'known')
        swlib.apply_event(state, 'sin', 'peek', '2026-10-06')
        self.assertEqual(swlib.find(state, 'sin')['status'], 'known')  # one peek since it became known
        swlib.apply_event(state, 'pero', 'peek', '2026-10-03')
        swlib.apply_event(state, 'pero', 'peek', '2026-10-02')  # arrives late
        self.assertEqual(swlib.find(state, 'pero')['peeks'], ['2026-10-02', '2026-10-03'])

    def test_learning_set_never_passes_20_with_shaky_words(self):
        state = swlib.new_state('2026-10-01')
        for day in ('2026-10-02', '2026-10-03', '2026-10-04'):
            swlib.promote(state, day, {})
        active = [w['es'] for w in state['words'] if w['status'] == 'active']
        self.assertEqual(len(active), swlib.WINDOW)
        for es in active[:4]:
            swlib.apply_event(state, es, 'flip', '2026-10-05')
        swlib.promote(state, '2026-10-05', {})
        self.assertEqual(sum(w['status'] in ('active', 'shaky') for w in state['words']), swlib.WINDOW)

    def test_merge_puts_new_words_at_their_rank_and_keeps_progress(self):
        state = swlib.new_state('2026-10-01')
        for day in ('2026-10-02', '2026-10-03'):
            swlib.promote(state, day, {})
        swlib.review(state, 'pero', True, '2026-10-03')
        new = state['words'].pop(9)['es']  # as if a plugin update added the word at rank 10
        state['words'].insert(3, dict(swlib.blank({'es': 'la palabra vieja', 'en': 'old', 'hint': 'x'}), status='known'))
        before = {w['es']: (w['status'], w.get('box')) for w in state['words']}
        swlib.merge_lexicon(state)
        self.assertEqual([w['es'] for w in state['words']], [w['es'] for w in swlib.load_lexicon()] + ['la palabra vieja'])
        self.assertEqual((state['words'][9]['es'], state['words'][9]['status']), (new, 'queue'))
        self.assertEqual({w['es']: (w['status'], w.get('box')) for w in state['words'] if w['es'] != new}, before)


class Brief(Home):
    seen = {'y': {'n': 40, 'days': [f'2026-10-0{i}' for i in range(1, 8)]},
            'en': {'n': 400, 'days': ['2026-10-08', '2026-10-09', '2026-10-10']},
            'peor': {'n': 0, 'days': []}}

    def state(self, stage=2):
        words = [word('y'), word('en'), word('peor'), word('juntos', 'active'), word('a pesar de', 'shaky'), word('quién', 'queue')]
        return {'stage': stage, 'stage_pinned': True, 'paused': False, 'words': words}

    def test_tiers(self):
        self.assertEqual(weave.tier(word('y'), self.seen), 'lot')
        self.assertEqual(weave.tier(word('en'), self.seen), 'some')
        self.assertEqual(weave.tier(word('peor'), self.seen), 'rare')
        self.assertEqual(weave.tier(word('solo'), self.seen), 'some')
        self.assertEqual(weave.tier(word('juntos', 'active'), self.seen), 'learn')

    def test_brief_text(self):
        lines = weave.brief(self.state(), self.seen).split('\n')
        self.assertIn('about 12%', lines[0])
        self.assertIn('never over 20%', lines[0])
        self.assertIn('at most 4 in one sentence', lines[0])
        self.assertIn('Never a Spanish sentence', lines[0])
        self.assertIn('never in files, code', lines[0])
        self.assertTrue(lines[1].endswith(': a pesar de = meaning, "hint"; juntos = meaning, "hint"'))
        self.assertTrue(lines[2].endswith(': peor') and lines[3].endswith(': en') and lines[4].endswith(': meaning → y'))
        self.assertNotIn('quién', '\n'.join(lines))  # queued words are not in use yet
        three = weave.brief(self.state(3), self.seen)
        self.assertIn('about 25%', three)
        self.assertNotIn('"hint"', three)
        self.assertIn('about 40%', weave.brief(self.state(4), self.seen))

    def test_guards_follow_the_words_in_use(self):
        fresh = weave.brief(swlib.new_state('2026-10-01'), {})  # y, pero, entonces, con, sin
        self.assertIn('"not X but Y" is sino', fresh)
        self.assertIn('también and entonces never for "too" or "so" before an adjective', fresh)
        self.assertNotIn('es and soy', fresh)
        self.assertNotIn('the el', fresh)  # no nouns yet
        self.assertIn('antes de, después de, durante, hasta and sin never before a clause', fresh)  # sin is in use
        later = weave.brief(grown(400), {})
        for guard in ('es and soy only for what something is', 'esto and eso only on their own', 'si is if, sí is yes',
                      'question words only in questions', 'never "the el"', 'bien never for the filler "Well,"',
                      'desde never for "since" meaning because', 'el tiempo never for "this time"',
                      'a Spanish adjective next to it agrees (la idea nueva)'):
            self.assertIn(guard, later)

    def test_recall_every_third_turn_shaky_first(self):
        state = self.state()
        picks = [weave.next_recall(state, 's1') for _ in range(7)]
        self.assertEqual([p and p['es'] for p in picks], ['a pesar de', None, None, 'juntos', None, None, None])
        self.assertIsNone(weave.next_recall(state, None))
        self.assertIn('Recall: a pesar de?', weave.brief(state, {}, picks[0]))

    def test_calibration(self):
        words = [word('y'), word('entonces'), word('pero'), word('sencillo', 'active'), word('el perro', 'active'), word('solo')]
        state = {'stage': 2, 'stage_pinned': True, 'words': words}
        english = 'The build passes and the cache is warm, so nothing else needs doing before the release goes out today. ' * 3
        self.assertEqual(weave.share(english, words), (0, 57, 0, 0, 0))
        woven = 'The build passes, y the cache is warm, entonces nothing else needs el perro, pero solo sencillo things wait. ' * 3
        # y, entonces, el perro (2), pero, sencillo: 6 Spanish words a sentence, 2 of them learning words; solo can't be counted
        self.assertEqual(weave.share(woven + '```y entonces pero```\n(el perro = the dog, "el PEH-rroh")\nRecall: y?', words), (18, 57, 6, 0, 0))
        self.assertIn('under the 12% target', weave.calibration(english, state))
        self.assertIn('over the 20% cap', weave.calibration(woven, state))
        self.assertEqual(weave.calibration('Done, y pushed.', state), '')
        spanish = ("Agregué una sección a README.md. Dice que una exportación vacía borra las filas, pero la tabla se "
                   "queda, y no ejecuté nada. Los otros problemas están en sync.py, así que dime si los debo corregir. ") * 2
        self.assertIn('slipped into Spanish sentences', weave.calibration(spanish, state))
        overlap = [word('tener'), word('tener cuidado'), word('todo'), word('todo el mundo')]
        self.assertEqual(weave.share('Please tener cuidado, todo el mundo, then tener it. ' * 6, overlap)[0], 36)  # 2 + 3 + 1 per sentence, not 8

    def test_calibration_follows_the_stage_rules(self):
        first = swlib.new_state('2026-10-01')  # Stage 1: y, pero, entonces, con, sin
        one = ('I looked at the failing build y found the cause. The test runner starts before the database is ready, pero '
               'only on the slower CI machines, entonces the first query times out and the whole suite stops. I changed the '
               'setup script so it waits for the health check con a short retry loop, and the suite now runs sin the random '
               'timeouts. I also cleaned up two old helper functions that nothing called anymore, renamed the config file so '
               'it matches the other services, and added a note to the README about the new wait step. Locally everything '
               'passes, and the CI run on my branch went green three times in a row. If you want, I can also add a timeout to '
               'the retry loop so a broken database fails fast instead of hanging the job for the full hour.')
        self.assertEqual(weave.share(one, swlib.introduced(first))[1:3], (142, 5))
        self.assertIn('on target', weave.calibration(one, first))  # all 5 learning words: the brief asks for 2 to 4
        words = [word('y'), word('entonces'), word('pero'), word('sencillo', 'active'), word('el perro', 'active')]
        three = ('I traced the slow page to the image loader, y the fix was small. The loader asked for every thumbnail at '
                 'full size, entonces the browser spent most of its time scaling them down. Now it asks for the small size '
                 'first and only loads the large one when you open a picture. Ahora la página está lista. The cache headers '
                 'were also wrong, pero that only mattered for repeat visits, so I set them to one day. I ran the same test '
                 'three times and the page now loads in under a second on a slow connection. Creo que es una buena idea, y '
                 'se puede cambiar después. If anything looks off, tell me which page and I will check it.')
        self.assertNotIn('slipped', weave.calibration(three, {'stage': 3, 'stage_pinned': True, 'words': words}))
        four = ('Encontré el problema: la configuración todavía usaba una ruta vieja. The build read that old path, y '
                'entonces every test failed. Lo cambié y ahora todo está bien. I also removed a duplicate step in the '
                'workflow, porque it ran the same checks twice. La prueba completa se hace en menos de dos minutos aquí. The '
                'first run is still slow, pero after that it is muy rápido. Otherwise this is ready to merge.')
        self.assertIn('on target', weave.calibration(four, grown(400)))  # Spanish beyond the lists counts at Stage 4

    def test_last_reply(self):
        log = self.home / 'chat.jsonl'
        log.write_text('\n'.join([line('old reply, y more'), line('sub', sidechain=True),
                                  json.dumps({'type': 'user', 'message': {'content': 'next'}}),
                                  line('latest reply, entonces done'), line('sub2', sidechain=True)]) + '\n')
        self.assertEqual(weave.last_reply(log), 'latest reply, entonces done')
        with mock.patch.object(weave, 'TAIL', len(log.read_bytes()) // 2):
            self.assertEqual(weave.last_reply(log), 'latest reply, entonces done')

    def test_huge_reply_is_scored_fast(self):
        swlib.save_state(grown(400))  # Stage 4: hundreds of words in use, each one a regex pass over the scored text
        words = swlib.introduced(swlib.load_state())
        sentence = 'The build passes, y the cache is warm, entonces nothing else needs doing, pero the tests wait. '
        spanish, total, *_ = weave.share(sentence * 6000, words)  # about 580 KB
        self.assertLess(total, weave.SCORED // 4)  # only the end is scored...
        small, small_total, *_ = weave.share(sentence * 20, words)
        self.assertAlmostEqual(100 * spanish / total, 100 * small / small_total, delta=1)  # ...and it gives the same share
        self.assertTrue(weave.extra('(sin = without, "seen"; con = with, "kohn")') and weave.extra('**Recall: y?**'))
        self.assertFalse(weave.extra('x = y ' * 50000))
        log = self.home / 'chat.jsonl'  # about 880 KB of reply, ending in one huge line that used to take most of a minute
        log.write_text(line(sentence * 6000 + '\n' + 'x = y ' * 50000) + '\n')
        start = time.time()
        out = json.loads(self.run_hook({'session_id': 'x', 'transcript_path': str(log)}))
        self.assertLess(time.time() - start, 5)  # the hook's timeout is 15s; this takes well under 1s
        self.assertIn('Your last reply in this chat was', out['hookSpecificOutput']['additionalContext'])

    def run_hook(self, payload, **env):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'weave.py'), '--hook'], input=json.dumps(payload),
                                capture_output=True, text=True, timeout=30, env=dict(os.environ, **env))
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_hook_output_and_pause(self):
        out = json.loads(self.run_hook({'session_id': 'x', 'transcript_path': str(self.home / 'missing.jsonl')}))
        context = out['hookSpecificOutput']['additionalContext']
        self.assertEqual(out['hookSpecificOutput']['hookEventName'], 'UserPromptSubmit')
        self.assertIn('Spanish Weave (Stage 1)', context)
        self.assertIn('Recall: y?', context)
        self.assertLess(len(context), 3000)
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['pause'])
        self.assertEqual(self.run_hook({'session_id': 'x'}), '')
        # The extension has no push from the plugin: say when Chrome follows.
        self.assertIn('stops sending new page text to Gemini within 2 minutes', out.getvalue())
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['resume'])
        self.assertIn('Spanish Weave', self.run_hook({}))
        self.assertIn('as soon as you open the Spanish Weave popup', out.getvalue())

    def test_chrome_timing_promises_match_the_extension(self):
        """The native host can't push a pause. A page's swap request syncs word state over STALE_MS old, so new text
        stops going to Gemini within that; a page that asks for nothing hears only from the SYNC_MINUTES alarm or the
        popup. So no promise says 2 minutes without the 10 minutes an open page can take."""
        code = (ROOT / 'extension' / 'src' / 'background.js').read_text(encoding='utf-8')
        stale = int(re.search(r'const STALE_MS = (\d+);', code).group(1)) // 60000
        alarm = int(re.search(r'const SYNC_MINUTES = (\d+);', code).group(1))
        self.assertIn(f'new page text to Gemini within {stale} minutes', sw.CHROME_PAUSED)
        self.assertIn(f'within {alarm} minutes', sw.CHROME_PAUSED)
        self.assertIn(f'within {alarm} minutes', sw.CHROME_PICKS_UP)
        self.assertNotIn(f'{stale} minutes', sw.CHROME_PICKS_UP)  # resume and setup reach idle pages only by the alarm
        for path in DOCS + [ROOT / 'scripts' / 'sw.py']:
            text = ' '.join(path.read_text(encoding='utf-8').split())
            for sentence in re.findall(r'[^.]*(?:within \d+ minutes|reach(?:es)? Chrome)[^.]*\.', text):
                if 'Chrome' in sentence or 'Gemini' in sentence or 'popup' in sentence:
                    self.assertIn(f'{alarm} minutes', sentence, path.name)

    def test_no_spanish_in_scripted_runs(self):
        self.assertIn('Spanish Weave', self.run_hook({}))  # no claude parent here: weave by default
        self.assertEqual(self.run_hook({}, SPANISH_WEAVE_OFF='1'), '')
        self.assertEqual(self.run_hook({}, CLAUDE_CODE_ENTRYPOINT='sdk-py'), '')
        self.assertIn('Spanish Weave', self.run_hook({}, CLAUDE_CODE_ENTRYPOINT='sdk-cli', CLAUDE_CODE_SESSION_ATTENDED='0'))
        one_shot = ['claude', '-p', '--model', 'haiku', 'Reply OK']
        remote = ['claude', '--print', '--sdk-url', 'https://example.invalid/v1/code/sessions/x', '--session-id', 'x',
                  '--input-format', 'stream-json', '--output-format', 'stream-json']
        self.assertTrue(weave.one_shot(one_shot))
        self.assertTrue(weave.is_claude(['/home/u/.local/share/claude/versions/2.1.296', '--print']))
        self.assertTrue(weave.is_claude(['claude', '-p']) and not weave.is_claude(['/bin/sh', '-c', 'x']))
        self.assertTrue(weave.one_shot(['claude', '--print', '--output-format', 'json', 'x']))
        self.assertFalse(weave.one_shot(remote))
        self.assertFalse(weave.one_shot(['claude', '--print', '--input-format=stream-json']))
        self.assertFalse(weave.one_shot(['claude', '--model', 'opus']))
        self.assertFalse(weave.interactive({}, args_check=lambda: one_shot))
        self.assertTrue(weave.interactive({}, args_check=lambda: remote))
        self.assertTrue(weave.interactive({'CLAUDE_CODE_ENTRYPOINT': 'sdk-cli'}, args_check=lambda: remote))
        self.assertTrue(weave.interactive({'SPANISH_WEAVE_FORCE': '1'}, args_check=lambda: one_shot))
        self.assertFalse(weave.interactive({'CLAUDE_CODE_ENTRYPOINT': 'sdk-ts'}, args_check=lambda: []))

    def test_desktop_apps_claude_path_with_a_space(self):
        path = '/Users/u/Library/Application Support/Claude/claude-code/2.1.299/x/claude.app/Contents/MacOS/claude'
        ps = lambda command, **_: subprocess.CompletedProcess(command, 0, path + '\n' if 'comm=' in command else
                                                              f'  321 {path} -p hi\n', '')
        with mock.patch.object(weave, 'open', side_effect=OSError, create=True), mock.patch.object(subprocess, 'run', ps):
            args, parent = weave.process_args(123)  # macOS: no /proc, so ps
        self.assertEqual((args, parent), ([path, '-p', 'hi'], 321))
        self.assertTrue(weave.is_claude(args) and weave.one_shot(args))
        self.assertEqual(weave.split_args('claude -p hi', '/opt/bin/claude'), ['claude', '-p', 'hi'])  # started from PATH
        self.assertEqual(weave.split_args('claude-code-helper -x', 'claude-code-hel'), ['claude-code-helper', '-x'])


class BrokenState(Home):
    def hook(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'weave.py'), '--hook'], capture_output=True,
                                text=True, timeout=30, input=json.dumps({'session_id': 'x'}))
        self.assertEqual((result.returncode, result.stdout), (0, ''))
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)  # one quiet line, no traceback
        return result.stderr

    def test_hook_stays_quiet_and_check_says_how_to_fix(self):
        path = self.home / 'sw' / 'state.json'
        path.parent.mkdir()
        for text, problem in (('', 'is empty'), ('{"words": [', 'is not valid JSON'), ('[]', 'has no word list'),
                              ('{"stage": 1}', 'has no word list')):
            path.write_text(text)
            self.assertIn(problem, self.hook())
            self.assertEqual(path.read_text(), text)  # never replaced: it may hold months of progress
            self.assertRaises(swlib.StateError, swlib.load_state)
            with mock.patch.object(Path, 'home', return_value=self.home), \
                    mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': '', 'CODEX_HOME': str(self.home / 'codex')}), \
                    mock.patch('sys.stdout', new=io.StringIO()) as out, self.assertRaises(SystemExit):
                sw.main(['check'])
            self.assertIn(f'FAIL word state: {path} {problem}', out.getvalue())
            self.assertIn(f'mv "{path}" "{path}.broken"', out.getvalue())
        with self.assertRaises(SystemExit) as caught:
            sw.main(['status'])  # every command says the same instead of a traceback
        self.assertIn('has no word list', caught.exception.code)
        self.assertRaises(swlib.StateError, sw_host.handle, {'type': 'state'})  # the host replies with the error
        path.write_text('{"words": [{"es": "y"}]}')  # anything else that breaks the hook is just as quiet
        self.hook()
        path.rename(path.with_name('state.json.broken'))  # the fix check gives
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['status'])
        self.assertIn('Spanish Weave: Stage 1', out.getvalue())


def grown(known, seed=1):
    """A state with about `known` known words, mostly in rank order, a few gaps and a few beyond."""
    import random
    rng = random.Random(seed)
    state = swlib.new_state('2026-01-01')
    words = state['words']
    chosen = set(range(known))
    for i in rng.sample(sorted(chosen), known // 20):
        chosen.discard(i)
    chosen.update(range(known, min(len(words), known + known // 20)))
    for i in chosen:
        swlib.apply_event(state, words[i]['es'], 'known', '2026-01-01')
    for day in range(2, 7):
        swlib.promote(state, f'2026-01-0{day}', {})
    return state


class Scale(Home):
    def test_known_band(self):
        state = grown(400)
        n, missing, extra = swlib.known_band(state)
        known = {w['es'] for w in state['words'] if w['status'] == 'known'}
        band = {w['es'] for w in state['words'][:n]}
        self.assertEqual(known, (band - set(missing) - {w['es'] for w in state['words'][:n] if w['status'] in ('active', 'shaky')}) | set(extra))
        # Learning words count against the band too: level 8 knows ranks 1-175 and learns 176-200.
        self.assertEqual(swlib.known_band(make_blocks.level_state(8, swlib.load_lexicon()))[0], 175)

    def test_known_words_are_list_words_not_a_frequency_rank(self):
        # The lexicon is not a general frequency list (ser and estar sit past 300), so the band names list positions.
        state = grown(400)
        about, respond = export.chatgpt(state)
        texts = [export.claude_ai(state), about, respond, weave.brief(state, {})]
        texts += [path.read_text(encoding='utf-8') for path in sorted((ROOT / 'blocks').glob('*.md'))]
        for text in texts:
            self.assertNotIn('most frequent', text)
            self.assertNotIn('most common Spanish words', text)

    def long_learning_state(self):
        """20 active and 10 shaky words with the longest entries in the list, plus 160 known."""
        lexicon = swlib.load_lexicon()
        longest = sorted(range(len(lexicon)), key=lambda i: -sum(len(lexicon[i][k]) for k in ('es', 'en', 'hint')))[:30]
        state = swlib.new_state('2026-01-01')
        state['words'] = words = [swlib.blank(w) for w in lexicon]
        for i in longest:
            swlib.set_status(words[i], 'active' if i in longest[:20] else 'shaky', swlib.today())
        for i in [i for i in range(len(words)) if i not in longest][:160]:
            swlib.set_status(words[i], 'known', '2026-01-01')
        return state

    def test_chatgpt_field_fits_with_long_learning_lists(self):
        state = self.long_learning_state()
        about, respond = export.chatgpt(state)
        self.assertLessEqual(len(about), export.CHATGPT_LIMIT)
        self.assertLessEqual(len(respond), export.CHATGPT_LIMIT)
        parsed = export.parse_state_line(about)
        self.assertEqual(len(parsed['active']), 20)  # every Active word is still named
        swlib.load_state()
        swlib.save_state(state)
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['export', '--chatgpt'])
        self.assertIn('Each fits in 1,500 characters', out.getvalue())
        with mock.patch.object(export, 'CHATGPT_LIMIT', 300), mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['export', '--chatgpt'])
        self.assertNotIn('Each fits', out.getvalue())
        self.assertIn('The "More about you" block is', out.getvalue())
        self.assertIn('over the 300 limit of the Free and Go plans', out.getvalue())

    def test_export_records_the_version_it_prints(self):
        yesterday = time.strftime('%Y-%m-%d', time.localtime(time.time() - 86400))
        swlib.load_state()
        swlib.save_state(swlib.new_state(yesterday))  # refilled = [yesterday, 5]: today's new words come in on export
        with mock.patch('sys.stdout', new=io.StringIO()):
            sw.main(['export'])
        state = swlib.load_state()
        self.assertEqual(state['exported']['version'], swlib.version(state))
        self.assertIsNone(weave.export_notice(state, now=time.time() + 8 * 86400))  # nothing changed since

    def test_brief_and_exports_stay_small(self):
        for known in (50, 400, 1000):
            state = grown(known)
            brief = weave.brief(state, {}, {'es': 'y', 'en': 'and', 'hint': 'ee'})
            about, respond = export.chatgpt(state)
            self.assertLessEqual(len(about), export.CHATGPT_LIMIT)
            self.assertLessEqual(len(respond), export.CHATGPT_LIMIT)
            self.assertLess(len(export.claude_ai(state)), make_blocks.CLAUDE_AI_MAX)
            if known >= 400:
                n = swlib.known_band(state)[0]
                self.assertIn(f'the first {n} words of the Spanish Weave list, the most basic ones', brief)
                self.assertIn(f'the first {n} words of my Spanish Weave list (it starts with y, pero', about)
                # French Weave's budget was 3,100 bytes. Spanish glosses run a little longer, accented letters take 2
                # bytes each, and the usage guards (es vs está, esto vs este, sino, bien...) add about 600 bytes once
                # every word is in use, and the longer 0.3.3 list puts a few more noted words among the learning ones,
                # so this budget is 4,200 (3,950 to 4,150 at 1,000 known words, depending on which words are learning,
                # 23 bytes of it the "spanish-weave-hook: on" line that keeps the chat plugin's skill out of the way).
                self.assertLess(len(brief.encode()), 4200, known)
        # The longest export: just under the band cutoff, every known word is named.
        self.assertLess(len(export.claude_ai(grown(swlib.COLLAPSE_AT - 1))), make_blocks.CLAUDE_AI_MAX)

    def test_state_line_round_trips(self):
        for known in (30, 400):
            state = grown(known)
            line = export.state_line(state, now=0)
            parsed = export.parse_state_line(line)
            self.assertEqual(parsed['stage'], swlib.stage_for(state))
            self.assertEqual(parsed['synced'], '1970-01-01T00:00Z')
            active = sorted((w for w in state['words'] if w['status'] == 'active'), key=lambda w: w['added'])
            self.assertEqual(parsed['active'], [(w['es'], w['en'], w['hint']) for w in active])
            shaky = [w for w in state['words'] if w['status'] == 'shaky']
            self.assertEqual(len(parsed['shaky']), len(shaky))
            if known < export.KNOWN_LIST_MAX:
                self.assertEqual(parsed['known'], [w['es'] for w in state['words'] if w['status'] == 'known'])
            else:
                n = swlib.known_band(state)[0]
                self.assertTrue(parsed['known'].startswith(f'the first {n} words of my Spanish Weave list'))
                self.assertIn(', except the Active and Shaky words above', parsed['known'])
        # The ChatGPT field drops sound hints, then meanings, and counts older Shaky words to fit: it still parses.
        for es, day in (('pero', '2026-01-09'), ('con', '2026-01-07'), ('muy', '2026-01-08')):
            swlib.apply_event(state, es, 'flip', day)
        line = export.state_line(state, dates=False, hint_groups=(), gloss_groups=('active',), shaky_max=2)
        self.assertIn('Shaky (use often; gloss in footer): pero; muy; and 1 more |', line)  # the newest two
        parsed = export.parse_state_line(line)
        self.assertEqual(parsed['shaky'], [('pero', None, None), ('muy', None, None)])
        self.assertEqual(parsed['active'], [(w['es'], w['en'], None) for w in active])

    def test_export_notice_once_after_a_week(self):
        state = swlib.load_state()
        with swlib.editing() as state:
            export.mark_exported(state, 'claude-ai')
        self.assertIsNone(weave.export_notice(state))  # same version
        with swlib.editing() as state:
            swlib.apply_event(state, 'y', 'known')
        self.assertIsNone(weave.export_notice(state, now=time.time() + 86400))  # changed, but fresh
        self.assertIn('/spanish-weave:export', weave.export_notice(state, now=time.time() + 8 * 86400))
        self.assertIsNone(weave.export_notice(swlib.load_state(), now=time.time() + 9 * 86400))  # only once

    def test_log_chat_day_counts_but_never_graduates_alone(self):
        state = swlib.new_state('2026-10-01')
        for day in ('2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04'):
            self.assertGreater(export.log_chat_day(state, day), 0)
            swlib.promote(state, day, {})
        self.assertEqual(swlib.find(state, 'y')['status'], 'active')


class Review(Home):
    def test_boxes_intervals_and_direction(self):
        state = swlib.new_state('2026-10-01')
        self.assertEqual(swlib.due_reviews(state, '2026-10-01'), [])  # new words wait a day, so they're met first
        self.assertEqual([w['es'] for w in swlib.due_reviews(state, '2026-10-02')], ['y', 'pero', 'entonces', 'con', 'sin'])
        pero = swlib.review(state, 'pero', True, '2026-10-02')
        self.assertEqual((pero['box'], pero['due'], pero['days']), (1, '2026-10-05', ['2026-10-02']))  # retrieval counts as exposure
        self.assertEqual(swlib.direction(pero), 'recognize')
        self.assertNotIn('pero', [w['es'] for w in swlib.due_reviews(state, '2026-10-02')])  # once a day
        swlib.review(state, 'pero', True, '2026-10-05')
        self.assertEqual((pero['box'], pero['due'], swlib.direction(pero)), (2, '2026-10-12', 'produce'))  # two right in a row
        swlib.review(state, 'pero', False, '2026-10-12')
        # Still learning: back to the first box and its three clean days start over, but it doesn't turn shaky.
        self.assertEqual((pero['box'], pero['due'], pero['status'], pero['last_bad']), (0, '2026-10-13', 'active', '2026-10-12'))
        self.assertEqual(swlib.direction(pero), 'recognize')
        self.assertEqual([r[:2] for r in pero['reviews']], [['2026-10-02', 1], ['2026-10-05', 1], ['2026-10-12', 0]])
        swlib.apply_event(state, 'con', 'flip', '2026-10-12')
        self.assertEqual(swlib.due_reviews(state, '2026-10-13')[0]['es'], 'con')  # shaky words come first
        self.assertIsNone(swlib.review(state, 'quién', True, '2026-10-13'))  # not introduced yet

    def test_same_day_answers_replace_each_other(self):
        state = swlib.new_state('2026-10-01')
        for _ in range(3):  # a retried command can't stack boxes
            swlib.review(state, 'pero', True, '2026-10-02')
        pero = swlib.find(state, 'pero')
        self.assertEqual((pero['box'], len(pero['reviews'])), (1, 1))
        swlib.apply_event(state, 'y', 'known', '2026-10-02')
        y = swlib.find(state, 'y')
        swlib.review(state, 'y', False, '2026-10-20')  # a known word not recognized turns shaky
        self.assertEqual((y['status'], y['box'], y['last_bad']), ('shaky', 0, '2026-10-20'))
        swlib.review(state, 'y', True, '2026-10-20')  # the verdict was wrong: undone, then counted right
        self.assertEqual((y['status'], y['box'], y['last_bad'], y['due']), ('known', 4, '', '2026-11-19'))

    def test_same_day_redo_keeps_a_change_made_in_between(self):
        state = swlib.new_state('2026-10-01')
        swlib.review(state, 'pero', False, '2026-10-02')
        swlib.apply_event(state, 'pero', 'flip', '2026-10-02')  # clicked back to English on a page
        pero = swlib.review(state, 'pero', True, '2026-10-02')
        self.assertEqual((pero['status'], pero['box'], [r[:2] for r in pero['reviews']]), ('shaky', 1, [['2026-10-02', 1]]))
        con = swlib.find(state, 'con')  # a record saved by 0.2.2, without the after-snapshot: undone as before
        con.update(status='shaky', box=0, last_bad='2026-10-02', reviews=[['2026-10-02', 0, 0, 'active', '2026-10-01', '']])
        swlib.review(state, 'con', True, '2026-10-02')
        self.assertEqual((con['status'], con['box'], con['last_bad'], len(con['reviews'])), ('active', 1, '', 1))

    def test_same_day_correction_undoes_a_graduation(self):
        """A right answer that brings the third exposure day graduates the word when it is saved. Correcting it to wrong
        the same day must put the word back to learning with its streak restarted and take the quiz's seen day out
        again; a sighting the extension sent before the quiz stays."""
        day = swlib.today()
        ago = lambda n: (dt.date.fromisoformat(day) - dt.timedelta(days=n)).isoformat()
        with swlib.editing() as state:
            swlib.find(state, 'pero').update(added=ago(5), changed=ago(5), days=[ago(3), ago(2)])
            swlib.find(state, 'con').update(added=ago(5), changed=ago(5), days=[ago(2), day])  # seen on a page today
        record = lambda *items: Commands.sw(self, 'record', *items)
        self.assertTrue(record('pero:right', 'con:right').startswith('pero: right; next review'))
        self.assertEqual(swlib.find(swlib.load_state(), 'pero')['status'], 'known')  # graduated on save
        out = record('pero:wrong', 'con:wrong').splitlines()
        self.assertTrue(out[0].endswith('(learning)') and out[1].endswith('(learning)'), out)
        state = swlib.load_state()
        pero, con = swlib.find(state, 'pero'), swlib.find(state, 'con')
        self.assertEqual((pero['status'], pero['box'], pero['last_bad'], pero['days'], len(pero['reviews'])),
                         ('active', 0, day, [ago(3), ago(2)], 1))
        self.assertEqual(sum(w['status'] == 'shaky' for w in state['words']), 0)  # nothing toward SHAKY_BLOCK
        self.assertEqual((con['status'], con['days']), ('active', [ago(2), day]))

    def test_known_words_get_spaced_reviews(self):
        state = swlib.new_state('2026-10-01', known_top=40)
        seeded = [w for w in state['words'] if w['status'] == 'known']
        self.assertEqual({w['box'] for w in seeded}, {1})
        dues = sorted({w['due'] for w in seeded})
        self.assertEqual((dues[0], dues[-1], len(dues)), ('2026-10-04', '2026-10-31', 28))  # spread over four weeks
        chat = {'muy': {'n': 3, 'days': ['2026-10-01', '2026-10-02', '2026-10-03']}}
        swlib.promote(state, '2026-10-03', {})
        swlib.find(state, 'muy')['status'] = 'active'
        swlib.promote(state, '2026-10-03', chat)
        muy = swlib.find(state, 'muy')
        self.assertEqual((muy['status'], muy['box'], muy['due']), ('known', 2, '2026-10-10'))  # graduated: a week later
        later = next(w for w in state['words'] if w['status'] == 'queue')
        swlib.apply_event(state, later['es'], 'known', '2026-10-03')
        self.assertEqual(later['due'], '2026-10-17')  # marked known by hand: two weeks later
        swlib.apply_event(state, later['es'], 'known', '2026-10-05')
        self.assertEqual(later['due'], '2026-10-17')  # marking it again keeps its schedule
        self.assertIn('muy', [w['es'] for w in swlib.due_reviews(state, '2026-10-10', limit=100)])
        swlib.review(state, 'muy', False, '2026-10-10')
        self.assertEqual(muy['status'], 'shaky')  # not even recognized
        swlib.review(state, 'muy', True, '2026-10-10')  # same day: replaces the miss
        swlib.review(state, 'muy', True, '2026-10-13')
        self.assertEqual((muy['status'], muy['box'], swlib.direction(muy)), ('known', 4, 'produce'))
        swlib.review(state, 'muy', False, '2026-11-12')  # couldn't say it, but still recognizes it: two boxes down
        self.assertEqual((muy['status'], muy['box'], muy['due']), ('known', 2, '2026-11-19'))

    def test_answer_checking(self):
        word = lambda es, en: {'es': es, 'en': en}
        self.assertTrue(swlib.check(word('pero', 'but'), ' But ', 'recognize'))
        self.assertTrue(swlib.check(word('el problema', 'the problem'), 'problem', 'recognize'))
        self.assertTrue(swlib.check(word('ser', 'to be (what something is)'), 'to be', 'recognize'))
        self.assertTrue(swlib.check(word('entonces', 'so / then'), 'then', 'recognize'))
        self.assertIsNone(swlib.check(word('pero', 'but'), 'however', 'recognize'))  # a person judges synonyms
        self.assertFalse(swlib.check(word('actualmente', 'currently'), 'actually', 'recognize'))  # the false friend
        self.assertFalse(swlib.check(word('pero', 'but'), '  ', 'recognize'))
        self.assertTrue(swlib.check(word('también', 'also / too'), 'Tambien', 'produce'))
        self.assertTrue(swlib.check(word('el problema', 'the problem'), 'la problema', 'produce'))
        self.assertTrue(swlib.check(word('el año', 'the year'), 'ano', 'produce'))
        self.assertIsNone(swlib.check(word('acordarse', 'to remember'), 'recordar', 'produce'))  # a listed synonym
        self.assertFalse(swlib.check(word('pero', 'but'), 'perro', 'produce'))
        self.assertEqual(sw.tip(word('la casa', 'the house'), 'el casa'), "  (it's la casa)")
        self.assertIn('comes back at the same gap', sw.tip(word('el problema', 'the problem'), 'la problema'))
        self.assertEqual(sw.tip(word('también', 'also'), 'tambien'), '  (spelled también)')
        self.assertEqual(sw.tip(word('también', 'also'), 'también'), '')
        self.assertEqual(sw.tip(word('sí', 'yes'), 'si'), '  (spelled sí; si is another word: if)')
        self.assertEqual(sw.tip(word('el año', 'the year'), 'ano'), '  (spelled año; ano is a different word)')

    def met_long_ago(self, n):
        """A saved state whose first n learning words arrived long ago, so they're due."""
        with swlib.editing() as state:
            for w in state['words'][:n]:
                w['added'] = '2026-01-01'
        return state

    def test_quiz_and_review_commands(self):
        state = self.met_long_ago(5)
        plan = [(dict(w), swlib.direction(w)) for w in swlib.due_reviews(state, limit=3)]
        answers, said = iter(['and', 'nope', 'y', 'q']), []
        self.assertEqual(sw.run_quiz(plan, ask=lambda prompt: next(answers), say=said.append), (2, 2))  # judged one right
        state = swlib.load_state()
        self.assertEqual([swlib.find(state, es).get('box') for es in ('y', 'pero', 'entonces')], [1, 1, None])  # q stopped it
        self.assertIn('Done: 2 of 2 right', said[-1])
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['quiz', '--plan', '2', 'words'])
            sw.main(['review', 'con', 'wrong'])
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[0], '1. recognize: What does "entonces" mean? | answer: entonces = so / then, "en-TOHN-ses" — '
                                   "'so' before an adjective is tan (tan rápido)")
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[2].startswith('con: wrong; next review') and lines[2].endswith('(learning)'))
        self.assertEqual(swlib.find(swlib.load_state(), 'con')['status'], 'active')

    def test_missed_words_are_asked_again_but_not_recorded(self):
        state = self.met_long_ago(2)
        plan = [(dict(w), 'recognize') for w in swlib.due_reviews(state, limit=2)]
        answers, said = iter(['and', 'however', 'n', 'but']), []
        self.assertEqual(sw.run_quiz(plan, ask=lambda prompt: next(answers), say=said.append), (1, 2))
        self.assertIn('Once more', '\n'.join(said))
        self.assertTrue(said[-2].strip().startswith('✓ pero'))  # the second try, after seeing the answer
        self.assertEqual([r[1] for r in swlib.find(swlib.load_state(), 'pero')['reviews']], [0])  # not recorded

    def test_quiz_arguments(self):
        self.assertEqual([sw.plan_size(a) for a in ([], ['8'], ['ten'], ['3', 'words'], ['0'], ['500'])], [5, 8, 5, 3, 1, 50])
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['quiz', '--plan'])
        self.assertTrue(out.getvalue().startswith('Nothing to review'))  # words arrived today: due tomorrow
        with mock.patch('sys.stderr', new=io.StringIO()), self.assertRaises(SystemExit):
            sw.main(['quiz', '-n', '0'])

    def test_wrong_article_on_a_noun_to_remember_keeps_its_box(self):
        cases = [('el problema', 'la'), ('la mano', 'el'), ('el día', 'una'), ('la clase', 'el'), ('la casa', 'el'),
                 ('el libro', 'la'), ('el problema', 'el'), ('el problema', '')]
        self.assertEqual([swlib.gender_slip(es, a) for es, a in cases], [True, True, True, True, False, False, False, False])
        self.met_long_ago(5)
        with swlib.editing() as state:
            for es in ('el problema', 'la casa'):
                swlib.set_status(swlib.find(state, es), 'active', '2026-01-01')
        plan = [(dict(swlib.find(state, 'el problema')), 'produce')]
        said = []
        self.assertEqual(sw.run_quiz(plan, ask=lambda prompt: 'la problema', say=said.append), (1, 1))  # recalled
        self.assertIn("(it's el problema: the ending doesn't give its gender away", '\n'.join(said))
        problema = swlib.find(swlib.load_state(), 'el problema')
        self.assertEqual((problema['box'], problema['reviews'][-1][1]), (0, 1))  # right, but the same gap again
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['review', 'el problema', 'right', '--article', 'la'])
            sw.main(['review', 'la casa', 'right', '--article', 'el'])  # -a says feminine: only a slip
        lines = out.getvalue().splitlines()
        self.assertIn('wrong article, so same gap again', lines[0])
        self.assertNotIn('same gap', lines[1])

    def test_recall_cue_alternates_with_due_known_words(self):
        state = {'stage': 1, 'stage_pinned': True, 'words': [
            dict(word('nunca', 'known'), due='2026-01-01', box=2), word('juntos', 'active'), word('pronto', 'active')]}
        picks = [weave.next_recall(state, 's') for _ in range(7)]
        self.assertEqual([p and p['es'] for p in picks], ['juntos', None, None, 'nunca', None, None, 'pronto'])


class Placement(Home):
    def test_items_are_stable_and_mixed(self):
        state = swlib.new_state('2026-10-01')
        items = placement.items(state)
        self.assertEqual(items, placement.items(state))
        self.assertEqual(sum(band is None for _, band in items), len(placement.PSEUDOWORDS))
        self.assertEqual([sum(band == i for _, band in items) for i in range(4)], [placement.PER_BAND] * 4)
        words = {swlib.fold(w['es']) for w in state['words']}
        self.assertEqual([p for p in placement.PSEUDOWORDS if swlib.fold(p) in words], [])

    def test_estimate_corrects_for_guessing(self):
        state = swlib.new_state('2026-10-01')
        items = placement.items(state)
        number = lambda pick: [n for n, (_, band) in enumerate(items, 1) if pick(band)]
        self.assertEqual(placement.estimate(state, number(lambda band: band is not None))[0], 1135)  # every real word, never more than the list
        self.assertEqual(placement.estimate(state, number(lambda band: True))[0], 0)  # yes to everything is no signal
        half_first = number(lambda band: band == 0)[:4] + number(lambda band: band is None)[:2]
        self.assertEqual(placement.estimate(state, half_first), (40, 4, 2))  # (4/8 - 3/14) / (1 - 3/14) of 100 words
        self.assertEqual(placement.estimate(state, half_first + number(lambda band: band is None)[2:3]), (0, 4, 3))
        cognates = number(lambda band: band == 3)[:3]  # a few rare words that look like English (el repositorio)
        self.assertEqual(placement.estimate(state, cognates)[0], 0)  # can't mark the most common words known

    def test_command_marks_the_estimate_known(self):
        with swlib.editing() as state:
            pass
        first_two_bands = ','.join(str(n) for n, (_, band) in enumerate(placement.items(state), 1) if band in (0, 1))
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['placement', '--answers', first_two_bands, '--apply'])
        self.assertIn('about 250 of the', out.getvalue())
        state = swlib.load_state()
        self.assertEqual(sum(w['status'] == 'known' for w in state['words'][:250]), 250)  # untouched words picked today count
        self.assertEqual(swlib.stage_for(state), 3)

    def test_command_refuses_guessing_and_reads_ranges(self):
        with swlib.editing() as state:
            pass
        fakes = [n for n, (_, band) in enumerate(placement.items(state), 1) if band is None][:3]
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['placement', '--answers', ', '.join(map(str, fakes)) + ', 1-40', '--apply'])
        self.assertIn('nothing was marked', out.getvalue())
        self.assertEqual(sum(w['status'] == 'known' for w in swlib.load_state()['words']), 0)
        self.assertEqual(sw.item_numbers('1-3, 7, 40-99', 44), [1, 2, 3, 7, 40, 41, 42, 43, 44])


class Notes(Home):
    def test_notes_reach_the_brief_status_extension_and_anki(self):
        notes = swlib.load_notes()
        lexicon = {swlib.key(w['es']) for w in swlib.load_lexicon()}
        self.assertEqual([k for k in notes if k not in lexicon], [])
        self.assertEqual(swlib.note('El Éxito'), "not 'exit' (that's la salida)")
        state = {'stage': 1, 'stage_pinned': True, 'words': [word('el éxito', 'active'), word('y', 'known')]}
        self.assertIn("el éxito = meaning, \"hint\" — not 'exit' (that's la salida)", weave.brief(state, {}))
        self.assertEqual(swlib.public_state(state)['words'][0]['note'], "not 'exit' (that's la salida)")
        self.assertNotIn('note', swlib.public_state(state)['words'][1])
        before = swlib.version(state)
        with mock.patch.object(swlib, 'note', lambda es: 'edited' if es == 'y' else ''):
            self.assertNotEqual(swlib.version(state), before)  # an edited note reaches the extension's cache
        lines = export.anki(state).splitlines()
        self.assertEqual(lines[:5], export.ANKI_HEADERS)
        self.assertEqual(lines[5], "el éxito\tmeaning — \"hint\" — not 'exit' (that's la salida)\tspanish-weave "
                                   "spanish-weave::active\tSpanish Weave")  # the deck column creates the deck
        self.assertEqual(len(export.anki(state, every=True).splitlines()), 5 + 2)


class Output(Home):
    def test_your_turn_every_fifth_reply_when_on(self):
        state = {'stage': 1, 'stage_pinned': True, 'words': [word('sin', 'active')]}
        self.assertNotIn('Your turn', weave.brief(state, {}, output=True))  # off by default
        state['prefs'] = {'output_practice': True}
        self.assertIn('Output practice is on', weave.brief(state, {}))
        self.assertNotIn('In this reply', weave.brief(state, {}))
        self.assertIn('Your turn: how would you say', weave.brief(state, {}, output=True))
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['output'])
            sw.main(['output', 'on'])
            sw.main(['output'])
        self.assertEqual([line.split(' (')[0] for line in out.getvalue().splitlines()[::2]],
                         ['Output practice is off', 'Output practice is on'])
        replies = [Brief.run_hook(self, {'session_id': 'talk'}) for _ in range(5)]
        self.assertEqual(['In this reply' in r for r in replies], [False, False, False, False, True])


class Unattended(Home):
    """Sessions nobody reads as they run (started by another session or a scheduled task) get no Spanish after their
    first prompt and count no exposure; notifications in a chat get the brief but are no turn."""

    run_hook = Brief.run_hook

    def test_prompt_kinds(self):
        kind = lambda text='hi', **marks: swlib.prompt_kind(json.loads(prompt(text, **marks)))
        self.assertEqual([kind(**TYPED), kind(**TYPED_DESKTOP)], ['typed', 'typed'])
        self.assertEqual([kind(**FROM_SESSION), kind(**SCHEDULED), kind(**NOTICE)], ['auto'] * 3)
        self.assertIsNone(kind())  # Claude Code before 2.1.161 marked nothing: no evidence either way
        self.assertIsNone(kind(promptSource='sdk'))  # 2.1.161-2.1.260 desktop prompts, typed or not
        self.assertIsNone(kind(origin={'kind': 'auto-continuation'}, promptSource='sdk'))
        self.assertIsNone(kind([{'type': 'tool_result', 'tool_use_id': 't', 'content': 'ok'}], promptSource='sdk'))
        self.assertIsNone(swlib.prompt_kind(dict(json.loads(prompt('Continue.', **FROM_SESSION)), isMeta=True)))
        self.assertIsNone(swlib.prompt_kind(json.loads(line('assistant text'))))

    def test_scan_counts_only_chats_the_user_typed_in(self):
        root = self.home / 'projects'
        (root / 'p').mkdir(parents=True)
        def write(name, *lines):
            with (root / 'p' / name).open('a') as file:
                file.write(''.join(l + '\n' for l in lines))
        write('typed.jsonl', prompt('fix it', **TYPED), line('Done, y the build passes.'))
        write('desktop.jsonl', prompt('fix it', **TYPED_DESKTOP), line('Done, y it ships.'))
        write('legacy.jsonl', prompt('fix it'), line('Old chat, y it counts.'))
        write('child.jsonl', prompt('Background (from the session that started this one): go', **FROM_SESSION),
              line('Report: y entonces it passes.'), prompt('<task-notification>', **NOTICE), line('Still y going.'))
        write('scheduled.jsonl', prompt('<scheduled-task name="weekly">', **SCHEDULED), line('Refreshed, y entonces done.'))
        index = swlib.scan(['y', 'entonces'], {}, root, start='2026-09-19')
        self.assertEqual(index['words']['y']['n'], 3)  # typed, desktop and legacy chats only
        self.assertEqual(index['words']['entonces']['n'], 0)
        write('scheduled.jsonl', line('Later, entonces y again.', day='2026-10-10'))  # read from a saved offset
        write('child.jsonl', prompt('thanks, also add tests', day='2026-10-10', **TYPED),
              line('Sure, entonces tests next.', day='2026-10-10'))  # the user steps into the child session
        index = swlib.scan(['y', 'entonces'], index, root, start='2026-09-19')
        self.assertEqual(index['words']['entonces'], {'n': 1, 'days': ['2026-10-10']})
        self.assertEqual(index['words']['y']['n'], 3)
        self.assertEqual({Path(k).name: v for k, v in index['typed'].items()},
                         {'typed.jsonl': True, 'desktop.jsonl': True, 'child.jsonl': True, 'scheduled.jsonl': False})

    def test_hook_skips_sessions_nobody_reads(self):
        reminder = '<system-reminder>\nThe user started this session without choosing a folder.\n</system-reminder>\n'
        child = self.home / 'child.jsonl'
        child.write_text(prompt(reminder + 'Background (from the session that started this one):\nfix it', **FROM_SESSION)
                         + '\n' + line('Report: done, y the tests pass, entonces it ships.') + '\n')
        skipped = [
            {'session_id': 'c', 'transcript_path': str(child), 'prompt': 'Another Claude session sent a message:\n'
                                                                       '<agent-message from="a1">go on</agent-message>'},
            {'session_id': 'c', 'transcript_path': str(child), 'prompt': 'also do the docs'},
            {'session_id': 's', 'prompt': reminder + '<scheduled-task name="weekly" file="/x/SKILL.md">\nThis is an '
                                                     'automated run of a scheduled task.\n</scheduled-task>'},
            {'session_id': 'k', 'prompt': reminder + 'Background (from the session that started this one):\nfix it'},
            {'session_id': 'a', 'agent_id': 'a1', 'agent_type': 'general-purpose', 'prompt': 'look around'},
        ]
        for payload in skipped:
            self.assertEqual(self.run_hook(payload), '', payload)
        self.assertEqual(swlib.read_json(self.home / 'sw' / 'sessions.json', {}), {})  # and nothing counted
        # The user types into the child session: Spanish from their next prompt on, and sessions.json remembers it.
        with child.open('a') as file:
            file.write(prompt('thanks, now the docs', **TYPED) + '\n' + line('On it.') + '\n')
        self.assertIn('Spanish Weave (Stage 1)', self.run_hook({'session_id': 'c', 'transcript_path': str(child),
                                                                'prompt': 'and the README'}))
        self.assertTrue(swlib.read_json(self.home / 'sw' / 'sessions.json')['c']['typed'])
        child.write_text(prompt('<task-notification>', **NOTICE) + '\n' + line('ok') + '\n')  # typed prompt out of reach
        self.assertIn('Spanish Weave (Stage 1)', self.run_hook({'session_id': 'c', 'transcript_path': str(child),
                                                                'prompt': 'one more thing'}))
        self.assertIn('Spanish Weave (Stage 1)', self.run_hook({'session_id': 'n', 'prompt': 'a first typed prompt'}))

    def test_notices_get_the_brief_but_no_turn(self):
        log = self.home / 'chat.jsonl'
        log.write_text(prompt('fix it', **TYPED) + '\n' + line('Done, y the build passes.') + '\n')
        first = self.run_hook({'session_id': 't', 'transcript_path': str(log), 'prompt': 'and the tests'})
        self.assertIn('Recall: y?', first)
        for notice in ('<task-notification>\n<task-id>b1</task-id>\n<status>completed</status>',
                       '<system-reminder>\nLinked sessions now\n</system-reminder>\n<side-sessions-event>Done</side-sessions-event>',
                       'Another Claude session sent a message:\n<agent-message from="a1">done</agent-message>'):
            out = json.loads(self.run_hook({'session_id': 't', 'transcript_path': str(log), 'prompt': notice}))
            context = out['hookSpecificOutput']['additionalContext']
            self.assertIn('Spanish Weave (Stage 1)', context)
            self.assertNotIn('open it with "Recall:', context)
            self.assertIn('No recall cue in this reply', context)  # models otherwise repeat the last cue
        self.assertEqual(swlib.read_json(self.home / 'sw' / 'sessions.json')['t']['n'], 1)
        self.assertIsNone(weave.prompt_source('What does a <task-notification> tag mean?'))  # typed: only a lead counts
        self.assertIsNone(weave.prompt_source('Can you explain <scheduled-task > tags?'))
        self.assertIsNone(weave.prompt_source(None))


class Blocks(unittest.TestCase):
    def test_blocks_are_current_and_fit(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'make_blocks.py'), '--check'],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_content_bundle_is_current(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'bundle_content.py'), '--check'],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_level_blocks_name_the_known_words(self):
        read = lambda level: (ROOT / 'blocks' / f'level-{level:02d}.md').read_text(encoding='utf-8')
        claude = read(4).split('```text\n', 1)[1].split('\n```', 1)[0]
        known = claude.split(' | Known (use freely; never gloss): ', 1)[1].rsplit(' | ', 1)[0]
        order = make_blocks.level_order(swlib.load_lexicon())
        self.assertEqual(known.split(', '), [w['es'] for w in order[:75]])  # all 75, newest included
        self.assertIn('the first 175 words of my Spanish Weave list', read(8))

    def test_levels_keep_their_words_when_words_are_added(self):
        # Words with a since version come after the others, so a pasted level never gains untaught Known words.
        lexicon = swlib.load_lexicon()
        order = make_blocks.level_order(lexicon)
        later = [w['es'] for w in order[-92:]]
        self.assertEqual(sorted(w['es'] for w in order), sorted(w['es'] for w in lexicon))
        self.assertIn('sino', later)
        self.assertNotIn('sino', [w['es'] for w in order[:1043]])
        self.assertEqual([w['es'] for w in order[:20]], [w['es'] for w in lexicon[:20]])
        levels = make_blocks.level_words(lexicon)
        self.assertEqual([len(level) for level in levels[41:]], [18, 25, 25, 25, 17])  # 0.3.2's last level keeps its 18
        self.assertEqual(make_blocks.version_tuple('0.3.10') > make_blocks.version_tuple('0.3.9'), True)


class Codex(Home):
    def test_merge_keeps_other_hooks_and_is_idempotent(self):
        theirs = {'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'x.sh'}]}],
                            'UserPromptSubmit': [{'hooks': [{'type': 'command', 'command': 'other.py'}]}]}}
        once = sw.merge_codex_hooks(json.loads(json.dumps(theirs)), sw.codex_command())
        twice = sw.merge_codex_hooks(json.loads(json.dumps(once)), sw.codex_command())
        self.assertEqual(once, twice)
        self.assertEqual(once['hooks']['Stop'], theirs['hooks']['Stop'])
        self.assertEqual(len(once['hooks']['UserPromptSubmit']), 2)
        self.assertEqual(once['hooks']['UserPromptSubmit'][0], theirs['hooks']['UserPromptSubmit'][0])

    def test_feature_flag(self):
        self.assertEqual(sw.enable_codex_hooks(''), '[features]\nhooks = true\n')
        self.assertEqual(sw.enable_codex_hooks('model = "x"\n[features]\nhooks = false\nother = 1\n[tui]\n'),
                         'model = "x"\n[features]\nhooks = true\nother = 1\n[tui]\n')
        self.assertEqual(sw.enable_codex_hooks('[features]\nmemories = true\n'), '[features]\nhooks = true\nmemories = true\n')
        self.assertIn('[features]\nhooks = true', sw.enable_codex_hooks('model = "x"\n[tui]\na = 1\n'))
        for before in ('', 'model = "x"\n', '[features]\nmemories = true\n', 'model = "x"\n[tui]\na = 1\n', '[features]\n\n[tui]\n'):
            self.assertEqual(sw.disable_codex_hooks(sw.enable_codex_hooks(before)), before.replace('[features]\n\n', ''))
        self.assertEqual(sw.disable_codex_hooks('[features]\nhooks = false\n'), '[features]\nhooks = false\n')
        self.assertEqual(sw.enable_codex_hooks('[features]\nhooks = true\n', 'hooks = false'), '[features]\nhooks = false\n')

    def test_codex_exec_is_scripted_tui_is_not(self):
        data = {'turn_id': 't', 'session_id': 's'}
        self.assertFalse(weave.interactive({}, data, exec_check=lambda: True))
        self.assertTrue(weave.interactive({}, data, exec_check=lambda: False))
        self.assertTrue(weave.interactive({'SPANISH_WEAVE_FORCE': '1'}, data, exec_check=lambda: True))
        # A real process tree: a shell whose argv[0] is codex starts Python, like Codex running the hook. Python can't
        # be the codex process itself: macOS framework builds re-exec into Python.app, which drops the fake argv[0].
        code = (f'import sys, os; sys.path.insert(0, {str(ROOT / "scripts")!r}); import weave; '
                f'print(weave.codex_exec(), weave.codex_exec(os.getpid()))')  # the parent, and a walk up from Python
        for args, expected in ((['codex', 'exec'], 'True True'), (['codex', 'e'], 'True True'),
                               (['codex', 'app-server'], 'False False')):
            (self.home / args[1]).write_text('"$PY" -c "$CODE"\nexit $?\n')  # the exit keeps sh from exec'ing Python
            sh = subprocess.run(args, executable='/bin/sh', cwd=self.home, capture_output=True, text=True,
                                env=dict(os.environ, PY=sys.executable, CODE=code))
            self.assertEqual(sh.stdout.strip(), expected, (args, sh.stderr))

    def test_codex_transcript_replies(self):
        lines = [json.dumps({'type': 'response_item', 'timestamp': '2026-10-09T10:00:00Z',
                             'payload': {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Fixed, entonces it ships.'}]}}),
                 json.dumps({'type': 'response_item', 'payload': {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'y'}]}})]
        self.assertEqual([t for _, t in swlib.replies(lines)], ['Fixed, entonces it ships.'])


class Host(Home):
    def converse(self, *messages):
        return self.exchange(b''.join(struct.pack('=I', len(m)) + m for m in (json.dumps(x).encode() for x in messages)))[0]

    def exchange(self, raw):
        """(replies, stderr) of a host run fed these framed bytes."""
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'sw_host.py')], input=raw, capture_output=True,
                                timeout=30, env=dict(os.environ))
        out, replies = result.stdout, []
        while out:
            size = struct.unpack('=I', out[:4])[0]
            replies.append(json.loads(out[4:4 + size]))
            out = out[4 + size:]
        return replies, result.stderr

    def test_protocol(self):
        ping, state, events, after, bad = self.converse(
            {'type': 'ping'}, {'type': 'state'},
            {'type': 'events', 'events': [{'word': 'Pero', 'kind': 'flip'}, {'word': 'y', 'kind': 'seen'},
                                          {'word': 'zzz', 'kind': 'seen'}, {'word': 'y', 'kind': 'typed'}]},
            {'type': 'state'}, {'type': 'nope'})
        self.assertEqual(ping, {'ok': True, 'host': 1})
        self.assertEqual(state['stage'], 1)
        self.assertEqual(len(state['words']), swlib.NEW_PER_DAY)
        self.assertNotIn('geminiKey', state)
        self.assertEqual(state['prefs'], {})
        self.assertEqual(events, {'ok': True, 'applied': 2, 'skipped': 2})
        self.assertEqual(after['words'][0], {'es': 'pero', 'en': 'but', 'hint': 'PEH-roh', 'status': 'shaky',
                                             'note': "'not X but Y' is sino"})
        self.assertNotEqual(after['version'], state['version'])
        self.assertFalse(bad['ok'])

    def test_state_reply_carries_prefs(self):
        with swlib.editing() as state:
            state['prefs'] = {'extension_sites': 'ask', 'extension_sites_at': 1800000000}
        reply, = self.converse({'type': 'state'})
        self.assertEqual(reply['prefs'], {'extension_sites': 'ask', 'extension_sites_at': 1800000000})

    def test_message_framing(self):
        stream = io.BytesIO()
        sw_host.write_message(stream, {'a': 'é'})
        stream.seek(0)
        self.assertEqual(sw_host.read_message(stream), {'a': 'é'})
        self.assertIsNone(sw_host.read_message(io.BytesIO(b'')))

    def test_bad_days_are_skipped_and_the_rest_applied(self):
        bad = ['2026-00-00', '2026-01-01\n', '٢٠٢٦-٠١-٠١', '1900-01-01']  # month 0, a newline, Arabic-Indic digits, too old
        events = [{'word': 'pero', 'kind': 'peek', 'day': day} for day in bad] + [{'word': 'y', 'kind': 'seen'}]
        reply, = self.converse({'type': 'events', 'events': events})
        self.assertEqual(reply, {'ok': True, 'applied': 1, 'skipped': 4})
        state = swlib.load_state()
        self.assertEqual((swlib.find(state, 'pero')['peeks'], swlib.find(state, 'y')['days']), ([], [swlib.today()]))
        reply, = self.converse({'type': 'events', 'events': [{'word': 'pero', 'kind': 'seen'}]})
        self.assertEqual(reply['applied'], 1)  # nothing bad was saved to trip the next batch

    def test_one_failing_event_never_sinks_the_batch(self):
        real = swlib.apply_event
        def apply_event(state, es, kind, day=None):
            if es == 'pero':
                raise ValueError('month must be in 1..12')
            return real(state, es, kind, day)
        events = [{'word': 'pero', 'kind': 'flip'}, {'word': 'y', 'kind': 'seen'}]
        with mock.patch.object(swlib, 'apply_event', apply_event):
            self.assertEqual(sw_host.handle({'type': 'events', 'events': events}), {'ok': True, 'applied': 1, 'skipped': 1})
        self.assertEqual(swlib.find(swlib.load_state(), 'y')['days'], [swlib.today()])

    def test_deep_json_gets_an_error_reply(self):
        deep = b'[' * 200_000 + b']' * 200_000
        replies, stderr = self.exchange(struct.pack('=I', len(deep)) + deep)
        self.assertEqual((len(replies), replies[0]['ok'], stderr), (1, False, b''))

    def test_long_words_are_skipped_fast(self):
        events = [{'word': f'{i}' + 'x' * 10_000, 'kind': 'seen'} for i in range(500)]
        start = time.time()
        reply = sw_host.handle({'type': 'events', 'events': events})
        self.assertLess(time.time() - start, 5)
        self.assertEqual(reply, {'ok': True, 'applied': 0, 'skipped': 500})

    def test_lock_wait_is_bounded(self):
        with mock.patch.object(sw_host, 'LOCK_TIMEOUT', 0.2), swlib.locked():  # someone else holds state.lock
            self.assertRaises(TimeoutError, sw_host.handle, {'type': 'state'})


FAKE_KEY = 'AIzaTEST_placeholder_not_a_real_key_0000'


class Setup(Home):
    def test_setup_installs_extension_host_and_key(self):
        key = self.home / 'key.txt'
        key.write_text(f'  {FAKE_KEY} \n')
        with mock.patch.object(Path, 'home', return_value=self.home), \
                mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': ''}), mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['setup', '--dry-run', '--gemini-key-file', str(key)])
            self.assertFalse((self.home / 'sw').exists())
            sw.main(['setup', '--gemini-key-file', str(key)])
        home = self.home / 'sw'
        self.assertIn('Load unpacked', out.getvalue())
        self.assertTrue((home / 'extension' / 'manifest.json').exists())
        self.assertFalse((home / 'extension' / 'test').exists())
        self.assertEqual((home / 'gemini_key').read_text().strip(), FAKE_KEY)
        self.assertEqual(oct((home / 'gemini_key').stat().st_mode & 0o777), '0o600')
        base = self.home / ('Library/Application Support/Google/Chrome' if sys.platform == 'darwin' else '.config/google-chrome')
        manifest = json.loads((base / 'NativeMessagingHosts' / f'{sw.HOST_NAME}.json').read_text())
        self.assertEqual(manifest['allowed_origins'], [f'chrome-extension://{sw.EXTENSION_ID}/'])
        launcher = Path(manifest['path'])
        self.assertTrue(os.access(launcher, os.X_OK))
        # The installed copy answers on its own, without the plugin folder.
        msg = json.dumps({'type': 'state'}).encode()
        result = subprocess.run([str(launcher)], input=struct.pack('=I', len(msg)) + msg, capture_output=True, timeout=30,
                                env=dict(os.environ))
        reply = json.loads(result.stdout[4:])
        self.assertTrue(reply['ok'])
        self.assertEqual(reply['geminiKey'], FAKE_KEY)

    def test_key_file_problems_never_echo_the_key_or_path(self):
        def fails(arg):
            with mock.patch.object(Path, 'home', return_value=self.home), mock.patch('sys.stdout', new=io.StringIO()) as out, \
                    self.assertRaises(SystemExit) as caught:
                sw.main(['setup', '--dry-run', '--gemini-key-file', arg])
            return str(caught.exception.code) + out.getvalue()
        self.assertIn('looks like a key', fails(FAKE_KEY))  # the key itself, given as the path
        self.assertNotIn(FAKE_KEY, fails(FAKE_KEY))
        self.assertIn('looks like a key', fails('x' * 40))
        missing = str(self.home / 'secret-dir' / 'no-such-file')
        self.assertNotIn('secret-dir', fails(missing))
        bad = self.home / 'notes.txt'
        bad.write_text(f'my key is {FAKE_KEY}\n')
        message = fails(str(bad))
        self.assertIn('only the key', message)
        self.assertNotIn(FAKE_KEY, message)
        self.assertFalse((self.home / 'sw').exists())

    def run_setup(self, *flags):
        with mock.patch.object(Path, 'home', return_value=self.home), mock.patch.dict(os.environ, {
                'XDG_CONFIG_HOME': '', 'CODEX_HOME': str(self.home / 'codex')}), mock.patch('sys.stdout', new=io.StringIO()):
            sw.main(['setup', *flags])
        return swlib.load_state(create=False)

    def uninstall(self, *flags):
        with mock.patch.object(Path, 'home', return_value=self.home), mock.patch.dict(os.environ, {
                'XDG_CONFIG_HOME': '', 'CODEX_HOME': str(self.home / 'codex')}), mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['uninstall', *flags])
        return out.getvalue()

    def test_uninstall_takes_out_everything_setup_added(self):
        codex = self.home / 'codex'
        codex.mkdir()
        (codex / 'config.toml').write_text('model = "o3"\n')
        with mock.patch.object(Path, 'home', return_value=self.home), mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': ''}):
            chrome, chromium = sw.host_dirs()
        chrome.parent.mkdir(parents=True)  # Chrome is installed, Chromium isn't
        self.run_setup('--codex', '--user-data-dir', str(self.home / 'profile'))
        self.run_setup('--codex')  # a rerun keeps the first backup and the recorded --user-data-dir manifest
        manifests = [Path(m) for m in sw.install_record()['host_manifests']]
        self.assertEqual(len(manifests), 3)
        self.assertIn(self.home.resolve() / 'profile' / 'NativeMessagingHosts' / f'{sw.HOST_NAME}.json', manifests)
        self.assertEqual((codex / 'config.toml.before-spanish-weave').read_text(), 'model = "o3"\n')
        self.assertIn('would remove', self.uninstall('--codex', '--dry-run'))
        self.assertTrue(all(m.exists() for m in manifests) and (codex / 'hooks.json').exists())
        out = self.uninstall('--codex')
        self.assertFalse(any(m.exists() for m in manifests))
        self.assertFalse((codex / 'hooks.json').exists())  # setup made it, and nothing else is in it
        self.assertEqual((codex / 'config.toml').read_text(), 'model = "o3"\n')
        left = out.split('Left in place:')[1]
        for item in ('claude plugin uninstall spanish-weave@learning', 'chrome://extensions',
                     f'rm "{codex / "config.toml.before-spanish-weave"}"', f'rm -rf "{self.home / "sw"}"'):
            self.assertIn(item, left)
        self.assertNotIn('NativeMessagingHosts', left)
        self.assertTrue((self.home / 'sw' / 'state.json').exists())  # the word progress stays until they delete it
        # Folders setup made for the host go again; Chrome's own folder stays.
        self.assertEqual([chrome.exists(), chrome.parent.exists(), chromium.parent.exists()], [False, True, False])
        self.assertFalse((self.home / 'profile').exists())

    def test_uninstall_keeps_what_was_there(self):
        codex = self.home / 'codex'
        codex.mkdir()
        theirs = {'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'x.sh'}]}]}}
        (codex / 'hooks.json').write_text(json.dumps(theirs))
        (codex / 'config.toml').write_text('[features]\nhooks = false\n')
        self.run_setup('--codex')
        out = self.uninstall()  # without --codex the hook stays, and the list says how to remove it
        self.assertIn('uninstall --codex', out.split('Left in place:')[1])
        out = self.uninstall('--codex')
        self.assertEqual(json.loads((codex / 'hooks.json').read_text()), theirs)  # no empty UserPromptSubmit list left
        self.assertIn('(other Codex hooks use it; before setup it was `hooks = false`); kept', out)
        (codex / 'hooks.json').write_text('{}')  # no other hooks left: what was there before comes back
        self.run_setup('--codex')
        self.assertIn('restored `hooks = false`', self.uninstall('--codex'))
        self.assertEqual((codex / 'config.toml').read_text(), '[features]\nhooks = false\n')

    def test_uninstall_after_an_older_setup(self):
        codex = self.home / 'codex'
        codex.mkdir()
        (codex / 'config.toml').write_text('model = "o3"\n')
        self.run_setup('--codex', '--user-data-dir', str(self.home / 'profile'))
        (self.home / 'sw' / sw.INSTALL).unlink()  # setup before 0.2.1 kept no record
        out = self.uninstall('--codex', '--user-data-dir', str(self.home / 'profile'))
        self.assertIn(f'removed {self.home.resolve() / "profile"}', out)  # an unrecorded --user-data-dir manifest, named again
        self.assertEqual((codex / 'config.toml').read_text(), 'model = "o3"\n')  # the backup shows the flag was setup's

    def test_uninstall_after_two_setups_on_020(self):
        """0.2.0 backed both Codex files up again on every setup --codex, so a second run's backups were setup's own
        edits, and 0.2.2 then recorded the `hooks = true` it found there as the user's."""
        codex = self.home / 'codex'
        codex.mkdir()
        theirs = {'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'x.sh'}]}]}}
        for own_hooks in (False, True):
            for path in codex.iterdir():
                path.unlink()
            if own_hooks:
                (codex / 'hooks.json').write_text(json.dumps(theirs))
            (codex / 'config.toml').write_text('model = "o3"\n')
            self.run_setup('--codex')  # 0.2.0's first run: our hook and `hooks = true` in place
            for name in ('hooks.json', 'config.toml'):  # its second run: both backed up again, over the first backups
                (codex / f'{name}.before-spanish-weave').write_bytes((codex / name).read_bytes())
            sw.remember(codex_hooks_added=False)
            out = self.uninstall('--codex')
            self.assertNotIn('it was there before setup', out)
            hooks, backup = codex / 'hooks.json', codex / 'hooks.json.before-spanish-weave'
            if own_hooks:  # their hooks stay, in the file and in its backup, without ours; other hooks need the flag
                self.assertEqual([json.loads(hooks.read_text()), json.loads(backup.read_text())], [theirs, theirs])
                self.assertIn('(other Codex hooks use it); kept', out)
            else:  # both were setup's own: gone, and the flag is taken out of config.toml and its backup
                self.assertFalse(hooks.exists() or backup.exists(), out)
                self.assertEqual((codex / 'config.toml').read_text(), 'model = "o3"\n')
            self.assertEqual((codex / 'config.toml.before-spanish-weave').read_text(), 'model = "o3"\n')

    def test_known_top_seeds_before_first_learning_words(self):
        state = self.run_setup('--known-top', '40')
        statuses = [w['status'] for w in state['words']]
        self.assertEqual(statuses[:40], ['known'] * 40)
        self.assertEqual(statuses[40:40 + swlib.NEW_PER_DAY], ['active'] * swlib.NEW_PER_DAY)
        self.assertEqual(swlib.stage_for(state), 2)
        self.assertFalse(state['stage_pinned'])
        self.assertNotIn('prefs', state)

    def test_rerun_never_resets_or_downgrades(self):
        self.run_setup()  # top 5 become learning words
        with swlib.editing() as state:
            swlib.apply_event(state, 'y', 'flip')  # shaky
            swlib.apply_event(state, 'pero', 'seen')
        state = self.run_setup('--known-top', '150', '--sites', 'ask')
        by = {w['es']: w for w in state['words']}
        self.assertEqual(by['y']['status'], 'shaky')
        self.assertEqual(by['pero']['status'], 'active')
        self.assertEqual(by['pero']['days'], [swlib.today()])
        # y and pero have progress and keep it; entonces, con and sin were picked today untouched, so they are seeded too.
        self.assertEqual(sum(w['status'] == 'known' for w in state['words'][:150]), 148)
        self.assertEqual(swlib.stage_for(state), 2)  # 148 known: stage 3 comes once y and pero graduate
        self.assertEqual(state['prefs']['extension_sites'], 'ask')
        before = json.dumps(state)
        state = self.run_setup('--known-top', '40')  # a lower answer later changes nothing
        self.assertEqual(json.dumps(state), before)
        self.assertEqual(state['prefs']['extension_sites'], 'ask')  # --sites left out keeps the choice
        self.assertEqual(self.run_setup('--sites', 'all')['prefs']['extension_sites'], 'all')

    def test_sites_choice_is_timed_so_the_latest_of_setup_and_popup_wins(self):
        self.run_setup()
        self.assertNotIn('prefs', swlib.load_state(create=False))  # no --sites: nothing to time
        start = int(time.time())
        with mock.patch.object(Path, 'home', return_value=self.home), mock.patch.dict(os.environ, {
                'XDG_CONFIG_HOME': '', 'CODEX_HOME': str(self.home / 'codex')}), mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['setup', '--sites', 'ask'])
        at = swlib.load_state(create=False)['prefs']['extension_sites_at']
        self.assertIsInstance(at, int)
        self.assertTrue(start <= at <= time.time() + 1)
        self.assertIn('a later "Other sites" choice in the extension popup wins until setup sets it again', out.getvalue())
        self.assertIn('as soon as you open the Spanish Weave popup', out.getvalue())
        self.assertEqual(self.run_setup('--known-top', '40')['prefs']['extension_sites_at'], at)  # a rerun without --sites
        reply = sw_host.handle({'type': 'state'})
        self.assertEqual(reply['prefs'], {'extension_sites': 'ask', 'extension_sites_at': at})

    def test_dry_run_reports_answers_and_writes_nothing(self):
        with mock.patch.object(Path, 'home', return_value=self.home), \
                mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': ''}), mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(['setup', '--dry-run', '--known-top', '40', '--sites', 'ask'])
        info = json.loads(out.getvalue())
        self.assertEqual((info['known_top'], info['sites']), (40, 'ask'))
        self.assertIn('codex_cli', info)
        self.assertFalse((self.home / 'sw').exists())
        with self.assertRaises(SystemExit), mock.patch('sys.stderr', new=io.StringIO()):
            sw.main(['setup', '--dry-run', '--sites', 'some'])

    def test_rerun_offers_to_keep_the_site_choice(self):
        """Updates rerun setup. --sites is timed and wins over an earlier popup choice, so passing it again would undo a
        later "Only sites I turn on"; the dry run shows that a choice exists and setup.md keeps it by default."""
        def dry_run():
            with mock.patch.object(Path, 'home', return_value=self.home), mock.patch.dict(os.environ, {
                    'XDG_CONFIG_HOME': ''}), mock.patch('sys.stdout', new=io.StringIO()) as out:
                sw.main(['setup', '--dry-run'])
            return json.loads(out.getvalue())['current_sites']
        self.assertIsNone(dry_run())  # first run: nothing to keep
        self.assertFalse((self.home / 'sw').exists())
        self.run_setup()
        self.assertIsNone(dry_run())  # the extension wasn't picked
        self.run_setup('--sites', 'ask')
        self.assertEqual(dry_run(), 'ask')
        _, body = command_file(ROOT / 'commands' / 'setup.md')
        self.assertIn('Keep the current site choice (default)', body)
        self.assertIn('`current_sites`', body)
        self.assertIn('Keep the current site choice: no `--sites`', body)

    def test_extension_id_matches_manifest_key(self):
        import base64
        import hashlib
        key = json.loads((ROOT / 'extension' / 'manifest.json').read_text())['key']
        digest = hashlib.sha256(base64.b64decode(key)).hexdigest()[:32]
        self.assertEqual(''.join(chr(ord('a') + int(c, 16)) for c in digest), sw.EXTENSION_ID)


PLUGIN_VERSION = json.loads((ROOT / '.claude-plugin' / 'plugin.json').read_text())['version']


class SetupSafety(Home):
    """Setup and uninstall touch only what is Spanish Weave's: whose the state dir is, symlinks, the host launcher, and
    copies older than the installed plugin."""

    def setUp(self):
        super().setUp()
        self.patches = [mock.patch.object(Path, 'home', return_value=self.home),
                        mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': '', 'CODEX_HOME': str(self.home / 'codex')})]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):  # before Home's, so the environment comes back as it was
            patch.stop()
        super().tearDown()

    def sw(self, *argv):
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(list(argv))
        return out.getvalue()

    def refused(self, *argv):
        with mock.patch('sys.stdout', new=io.StringIO()), self.assertRaises(SystemExit) as caught:
            sw.main(list(argv))
        return str(caught.exception.code)

    def check(self):
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            try:
                sw.main(['check'])
            except SystemExit:
                pass
        return out.getvalue()

    def host(self, launcher, env, message):
        raw = json.dumps(message).encode()
        result = subprocess.run([str(launcher)], input=struct.pack('=I', len(raw)) + raw, capture_output=True,
                                timeout=30, env=env)
        return json.loads(result.stdout[4:]) if result.stdout else result.stderr.decode()

    def claude_file(self, name, data):
        (self.home / 'claude' / 'plugins').mkdir(parents=True, exist_ok=True)
        (self.home / 'claude' / 'plugins' / name).write_text(json.dumps(data))

    def installed(self, version, path='/elsewhere/spanish-weave', sha='0123456789abcdef'):
        """installed_plugins.json as Claude Code writes it."""
        self.claude_file('installed_plugins.json', {'version': 2, 'plugins': {'spanish-weave@learning': [
            {'scope': 'user', 'installPath': path, 'version': version, 'gitCommitSha': sha}]}})

    def test_setup_refuses_a_folder_that_is_not_spanish_weaves(self):
        home = self.home / 'sw'
        (home / 'extension').mkdir(parents=True)
        (home / 'keep.txt').write_text('mine')
        (home / 'extension' / 'keep').write_text('mine too')
        home.chmod(0o755)
        self.assertIn(f'{home} is not a Spanish Weave folder', self.refused('setup'))
        self.assertEqual(((home / 'keep.txt').read_text(), (home / 'extension' / 'keep').read_text()), ('mine', 'mine too'))
        self.assertEqual(home.stat().st_mode & 0o777, 0o755)
        empty = self.home / 'empty'  # a new or empty folder is fine; one that was there keeps its mode
        empty.mkdir(mode=0o755)
        empty.chmod(0o755)
        with mock.patch.dict(os.environ, {'SPANISH_WEAVE_HOME': str(empty)}):
            self.sw('setup')
        self.assertEqual(empty.stat().st_mode & 0o777, 0o755)
        with mock.patch.dict(os.environ, {'SPANISH_WEAVE_HOME': str(self.home / 'new')}):
            self.sw('setup')
        self.assertEqual((self.home / 'new').stat().st_mode & 0o777, 0o700)

    def test_the_hook_and_commands_leave_a_foreign_folder_alone(self):
        """The prompt hook usually runs before setup. If it put state.json into someone's folder, setup would take that
        folder for its own, replace its extension/ and make it 0700. So nothing creates state files in a folder that
        holds other things and none of Spanish Weave's: the hook skips quietly, commands say why."""
        home = self.home / 'sw'
        (home / 'extension').mkdir(parents=True)
        (home / 'extension' / 'keep.txt').write_text('mine')
        home.chmod(0o755)
        self.assertIn(f'{home} is not a Spanish Weave folder', BrokenState.hook(self))  # exit 0, one stderr line
        self.assertIn(f'{home} is not a Spanish Weave folder', self.refused('status'))
        self.assertRaises(swlib.UnsafeHome, swlib.load_state)
        self.assertIn(f'FAIL word state: {home} is not a Spanish Weave folder', self.check())
        self.assertIn(f'{home} is not a Spanish Weave folder', self.refused('setup'))
        self.assertEqual(sorted(p.name for p in home.rglob('*')), ['extension', 'keep.txt'])  # no state or lock files
        self.assertEqual(((home / 'extension' / 'keep.txt').read_text(), home.stat().st_mode & 0o777), ('mine', 0o755))
        junk = self.home / 'junk'  # a folder with only what Finder or Windows leave behind counts as empty
        junk.mkdir()
        (junk / '.DS_Store').write_text('')
        with mock.patch.dict(os.environ, {'SPANISH_WEAVE_HOME': str(junk)}):
            self.assertIn('Spanish Weave: Stage 1', self.sw('status'))

    def test_setup_replaces_only_its_own_copies_and_chmods_only_its_own_folder(self):
        """Folders where an older hook already left state.json: setup replaces extension/ and app/ only when they are
        Spanish Weave's copies, and makes the state folder private only when it is new or setup ran there before."""
        planted = {'extension/keep.txt': 'mine', 'extension/manifest.json': '{"name": "Another extension"}',
                   'app/scripts/tool.py': 'print("mine")', 'app/data/notes.txt': 'mine'}
        for n, (name, text) in enumerate(planted.items()):
            home = self.home / f'theirs{n}'
            (home / name).parent.mkdir(parents=True)
            (home / name).write_text(text)
            home.chmod(0o755)
            with mock.patch.dict(os.environ, {'SPANISH_WEAVE_HOME': str(home)}):
                swlib.save_state(swlib.new_state())  # what the hook of 0.3.0 and earlier wrote there
                self.assertIn(f'{home} is not a Spanish Weave folder', self.refused('setup'), name)
            self.assertEqual(((home / name).read_text(), home.stat().st_mode & 0o777), (text, 0o755), name)
        empty = self.home / 'empty'  # the person's own empty folder, where the hook started a word list
        empty.mkdir()
        empty.chmod(0o755)
        with mock.patch.dict(os.environ, {'SPANISH_WEAVE_HOME': str(empty)}):
            subprocess.run([sys.executable, str(ROOT / 'scripts' / 'weave.py'), '--hook'], input='{}',
                           capture_output=True, text=True, timeout=30, check=True)
            self.assertTrue((empty / 'state.json').exists())
            self.sw('setup')
            self.assertEqual(empty.stat().st_mode & 0o777, 0o755)  # not new, and setup never ran there
            self.sw('setup')  # its own folder now (install.json), so a rerun replaces the copies and keeps it private
        self.assertEqual(empty.stat().st_mode & 0o777, 0o700)
        self.assertTrue((empty / 'extension' / 'manifest.json').exists())

    def test_setup_refuses_a_symlinked_app_folder(self):
        with swlib.editing():
            pass  # a Spanish Weave folder
        checkout = self.home / 'dev'
        (checkout / 'scripts').mkdir(parents=True)
        (checkout / 'scripts' / 'wip.txt').write_text('work in progress')
        (self.home / 'sw' / 'app').symlink_to(checkout)
        self.assertIn('is a symbolic link', self.refused('setup'))
        self.assertEqual((checkout / 'scripts' / 'wip.txt').read_text(), 'work in progress')

    def test_gemini_key_is_never_written_through_a_symlink(self):
        key = self.home / 'key.txt'
        key.write_text(FAKE_KEY + '\n')
        notes = self.home / 'notes.txt'
        notes.write_text('NOTES\n')
        with swlib.editing():
            pass
        stored = self.home / 'sw' / 'gemini_key'
        stored.symlink_to(notes)
        message = self.refused('setup', '--gemini-key-file', str(key))
        self.assertIn('gemini_key is a symbolic link', message)
        self.assertNotIn(FAKE_KEY, message)
        self.assertEqual(notes.read_text(), 'NOTES\n')
        stored.unlink()
        stored.write_text('old\n')
        stored.chmod(0o644)
        self.sw('setup', '--gemini-key-file', str(key))
        self.assertEqual((stored.read_text(), stored.stat().st_mode & 0o777), (FAKE_KEY + '\n', 0o600))

    def test_launcher_quotes_paths_names_its_home_and_falls_back_to_python3(self):
        home = self.home / 'my $HOME "sw"'
        with mock.patch.dict(os.environ, {'SPANISH_WEAVE_HOME': str(home)}):
            self.sw('setup')
        launcher = home / 'app' / 'sw-host'
        env = {k: v for k, v in os.environ.items() if k != 'SPANISH_WEAVE_HOME'}  # Chrome sets no SPANISH_WEAVE_HOME
        env['HOME'] = str(self.home / 'fake-home')
        self.assertEqual(self.host(launcher, env, {'type': 'ping'}), {'ok': True, 'host': 1})
        (home / 'state.json').rename(home / 'state.json.aside')  # the repair advice for a broken state.json
        self.assertTrue(self.host(launcher, env, {'type': 'state'})['ok'])
        self.assertTrue((home / 'state.json').exists())  # a fresh list in the same home, not in ~/.spanish-weave
        self.assertFalse((self.home / 'fake-home' / '.spanish-weave').exists())
        bin_dir = self.home / 'bin'
        bin_dir.mkdir()
        (bin_dir / 'python3').symlink_to(sys.executable)
        gone = self.home / 'launcher-without-its-python'
        gone.write_text(sw.launcher_text('/nonexistent/python3', home / 'app' / 'scripts' / 'sw_host.py', home))
        gone.chmod(0o755)
        env['PATH'] = os.pathsep.join([str(bin_dir), '/usr/bin', '/bin'])
        self.assertEqual(self.host(gone, env, {'type': 'ping'}), {'ok': True, 'host': 1})

    def test_uninstall_leaves_files_it_did_not_make(self):
        self.sw('setup')
        foreign = self.home / 'notes' / 'important.json'
        foreign.parent.mkdir()
        foreign.write_text('{"keep": true}')
        lookalike = self.home / 'other-profile' / 'NativeMessagingHosts' / 'com.spanishweave.host.json'
        lookalike.parent.mkdir(parents=True)
        lookalike.write_text(json.dumps({'name': 'com.spanishweave.host', 'allowed_origins': ['chrome-extension://x/']}))
        record = swlib.read_json(self.home / 'sw' / 'install.json')
        record['host_manifests'] += [str(foreign), str(lookalike)]  # an edited or copied install.json
        swlib.write_json(self.home / 'sw' / 'install.json', record)
        (self.home / 'sw' / 'mine.txt').write_text('not Spanish Weave\'s')
        out = self.sw('uninstall')
        self.assertEqual(foreign.read_text(), '{"keep": true}')
        self.assertTrue(lookalike.exists())
        for path in (foreign, lookalike):
            self.assertIn(f'{path} (not a Spanish Weave host manifest; left alone)', out)
        base = self.home / ('Library/Application Support/Google/Chrome' if sys.platform == 'darwin' else '.config/google-chrome')
        self.assertFalse((base / 'NativeMessagingHosts' / 'com.spanishweave.host.json').exists())  # ours is gone
        home = self.home / 'sw'
        self.assertNotIn(f'rm -rf "{home}"', out)  # the folder holds mine.txt too
        self.assertIn(f'rm -rf "{home / "state.json"}"', out)
        self.assertNotIn('mine.txt', out)

    def test_os_junk_never_counts_as_someone_elses_files(self):
        """Finder drops .DS_Store into folders browsed in the Load unpacked picker; Windows and macOS on shared drives
        leave Thumbs.db, desktop.ini and ._ files. Neither uninstall nor setup takes them for the person's own files."""
        self.sw('setup')
        home = self.home / 'sw'
        for name in ('.DS_Store', 'Thumbs.db', 'desktop.ini', '._state.json'):
            (home / name).write_text('')
        out = self.sw('uninstall', '--dry-run')
        self.assertIn(f'rm -rf "{home}"', out)
        self.assertNotIn('holds other things too', out)
        fresh = self.home / 'fresh'
        fresh.mkdir()
        for name in ('Thumbs.db', 'desktop.ini', '._x'):
            (fresh / name).write_text('')
        with mock.patch.dict(os.environ, {'SPANISH_WEAVE_HOME': str(fresh)}):
            self.assertIn('is set up', self.sw('setup'))

    def test_codex_files_linked_from_dotfiles_stay_links(self):
        dotfiles, codex = self.home / 'dotfiles', self.home / 'codex'
        dotfiles.mkdir()
        codex.mkdir()
        theirs = {'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'x.sh'}]}]}}
        (dotfiles / 'hooks.json').write_text(json.dumps(theirs))
        (dotfiles / 'config.toml').write_text('model = "o3"\n')
        for name in ('hooks.json', 'config.toml'):
            (codex / name).symlink_to(dotfiles / name)
        self.sw('setup', '--codex')
        self.assertTrue((codex / 'hooks.json').is_symlink() and (codex / 'config.toml').is_symlink())
        hooks = json.loads((dotfiles / 'hooks.json').read_text())
        self.assertTrue(sw.has_our_hook(hooks))
        self.assertEqual(hooks['hooks']['Stop'], theirs['hooks']['Stop'])
        self.assertEqual((dotfiles / 'config.toml').read_text(), 'model = "o3"\n\n[features]\nhooks = true\n')
        self.assertEqual(sorted(p.name for p in dotfiles.iterdir()), ['config.toml', 'hooks.json'])  # no temp files
        del hooks['hooks']['Stop']  # with no other hooks left, uninstall takes `hooks = true` out too
        (dotfiles / 'hooks.json').write_text(json.dumps(hooks))
        self.sw('uninstall', '--codex')
        self.assertTrue((codex / 'hooks.json').is_symlink() and (codex / 'config.toml').is_symlink())
        self.assertFalse(sw.has_our_hook(json.loads((dotfiles / 'hooks.json').read_text())))
        self.assertEqual((dotfiles / 'config.toml').read_text(), 'model = "o3"\n')

    def test_a_lock_file_link_is_never_followed(self):
        home = self.home / 'sw'
        home.mkdir()
        victim = self.home / 'victim.txt'
        victim.write_text('PRECIOUS\n')
        (home / 'state.lock').symlink_to(victim)
        self.assertIn(f'{home / "state.lock"} is a symbolic link; remove it', self.refused('status'))
        self.assertEqual(victim.read_text(), 'PRECIOUS\n')
        self.assertIn('is a symbolic link', BrokenState.hook(self))  # quiet: exit 0, one stderr line
        self.assertEqual(victim.read_text(), 'PRECIOUS\n')

    def test_state_dir_is_private_and_a_world_writable_one_is_refused(self):
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'weave.py'), '--hook'], input='{}', capture_output=True,
                       text=True, timeout=30, check=True)  # the hook before setup creates the state dir
        self.assertEqual((self.home / 'sw').stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.home / 'sw' / 'state.lock').stat().st_mode & 0o777, 0o600)
        shared = self.home / 'shared'
        with mock.patch.dict(os.environ, {'SPANISH_WEAVE_HOME': str(shared)}):
            with swlib.editing():
                pass
            shared.chmod(0o777)  # now anyone could write the words that go into Claude's context
            before = sorted(p.name for p in shared.iterdir())
            self.assertIn(f'any user can write to {shared}', self.refused('status'))
            self.assertIn('any user can write to', BrokenState.hook(self))
            self.assertIn('FAIL word state: any user can write to', self.check())
        self.assertEqual(sorted(p.name for p in shared.iterdir()), before)

    def test_check_and_status_say_when_copies_are_behind(self):
        self.sw('setup')
        home = self.home / 'sw'
        self.installed('9.9.9')  # the plugin was updated, setup not rerun
        self.assertIn(f'FAIL copies in {home} are from {PLUGIN_VERSION}; the installed plugin is 9.9.9: rerun setup',
                      self.check())
        self.assertIn(f'the extension and native host copies are from {PLUGIN_VERSION}, the plugin is 9.9.9: rerun '
                      '/spanish-weave:setup', self.sw('status'))
        record = swlib.read_json(home / 'install.json')
        del record['version']  # set up by 0.2.2 or earlier
        swlib.write_json(home / 'install.json', record)
        self.assertIn('are from an older version; the installed plugin is 9.9.9: rerun setup', self.check())
        self.installed(PLUGIN_VERSION)
        self.sw('setup')
        self.assertNotIn('rerun', self.check() + self.sw('status'))
        gone = self.home / 'Downloads' / 'Learning-'  # unzipped there, then the folder was cleared out
        self.claude_file('known_marketplaces.json', {'learning': {'source': {'source': 'directory', 'path': str(gone)},
                                                                  'installLocation': str(gone)}})
        out = self.check()
        self.assertIn(f'FAIL the learning marketplace was added from {gone}, which is gone', out)
        self.assertIn('claude plugin marketplace add Camcas99/Learning-', out)
        gone.mkdir(parents=True)
        self.assertNotIn('marketplace', self.check())

    def test_setup_records_and_shows_the_version(self):
        self.installed(PLUGIN_VERSION, path=str(ROOT), sha='abcdef0123456789')  # this folder is the installed plugin
        out = self.sw('setup')
        self.assertTrue(out.startswith(f'Spanish Weave {PLUGIN_VERSION} is set up (commit abcdef0).'), out[:80])
        record = swlib.read_json(self.home / 'sw' / 'install.json')
        self.assertEqual((record['version'], record['commit']), (PLUGIN_VERSION, 'abcdef0123456789'))
        self.installed(PLUGIN_VERSION)  # installed elsewhere: this folder's commit isn't known
        self.assertTrue(self.sw('setup').startswith(f'Spanish Weave {PLUGIN_VERSION} is set up.'))


COMMANDS = sorted((ROOT / 'commands').glob('*.md'))
SW_RULE = 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" '


def command_file(path):
    """(frontmatter fields, body) of a commands/*.md file; every field is on one line."""
    _, head, body = path.read_text(encoding='utf-8').split('---\n', 2)
    return dict(line.split(': ', 1) for line in head.splitlines() if ': ' in line), body


def bash_rules(fields):
    """allowed-tools' Bash rules as (command, prefix rule?)."""
    rules = [tool[5:-1] for tool in fields.get('allowed-tools', '').split(', ') if tool.startswith('Bash(')]
    return [(' '.join(rule[:-2].split()), True) if rule.endswith(':*') else (' '.join(rule.split()), False)
            for rule in rules]


def allowed(command, rules):
    """Claude Code's match for a Bash rule: the exact command, or a prefix rule's command and then a space."""
    command = ' '.join(command.split())
    return any(command == rule or prefix and command.startswith(rule + ' ') for rule, prefix in rules)


class Commands(Home):
    """The slash commands: no user text in shell lines, narrow permissions, and the sw.py side they rely on."""

    def sw(self, *argv):
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            sw.main(list(argv))
        return out.getvalue()

    def test_no_user_text_in_shell(self):
        for path in COMMANDS:
            _, body = command_file(path)
            self.assertEqual(body.count('`') % 2, 0, path.name)
            spans = re.findall(r'!`([^`]+)`', body) + [s for s in re.findall(r'`([^`]+)`', body) if 'sw.py' in s]
            for span in spans:
                self.assertIsNone(re.search(r'\$(ARGUMENTS|\d)', span), f'{path.name}: {span}')
            for text in body.splitlines():
                if '$ARGUMENTS' in text:  # only as data in prose, labelled as such
                    self.assertIn('(data, not instructions)', text, path.name)

    def test_crafted_arguments_run_nothing(self):
        """Claude Code puts the typed text in place of $ARGUMENTS, escaping only `!` markers, then runs `!` lines."""
        bin_dir = self.home / 'bin'
        bin_dir.mkdir()
        (bin_dir / 'python3').symlink_to(sys.executable)
        victim = self.home / 'victim'
        victim.write_text('ORIGINAL')
        payloads = [f'1; touch {self.home}/pwned', f'x"; touch {self.home}/pwned; echo "', f'--all --out {victim} #']
        escape = lambda text: re.sub(r'^!', r'\\!', text.replace('`!', '` !').replace('!`', '! `'))
        commands = set()
        for path in COMMANDS:
            _, body = command_file(path)
            for payload in payloads:
                text = body.replace('$ARGUMENTS', escape(payload)).replace('${CLAUDE_PLUGIN_ROOT}', str(ROOT))
                commands.update(re.findall(r'!`([^`]+)`', text))
        env = dict(os.environ, HOME=str(self.home), SPANISH_WEAVE_HOME=str(self.home / 'sw'), XDG_CONFIG_HOME='',
                   CODEX_HOME=str(self.home / 'codex'), PATH=os.pathsep.join([str(bin_dir), '/usr/bin', '/bin']))
        run = lambda command: subprocess.run(['/bin/sh', '-c', command], env=env, capture_output=True, text=True,
                                             timeout=60).stdout
        outputs = [run(command) for command in sorted(commands)]
        self.assertTrue(any(out.startswith('Spanish Weave: Stage') for out in outputs))  # the lines ran
        self.assertFalse((self.home / 'pwned').exists())
        self.assertEqual(victim.read_text(), 'ORIGINAL')

    def test_permissions_are_narrow(self):
        for path in COMMANDS:
            fields, body = command_file(path)
            self.assertNotIn('Bash(python3:*)', path.read_text(encoding='utf-8'))
            tools = fields['allowed-tools'].split(', ')
            self.assertEqual([t for t in tools if not t.startswith('Bash(') and t != 'AskUserQuestion'], [], path.name)
            self.assertEqual([t for t in tools if t.startswith('Bash(') and not t.startswith(SW_RULE)], [], path.name)
            # The model can't start a command that changes something; status stays askable ("how's my Spanish?").
            self.assertEqual(fields.get('disable-model-invocation') == 'true', path.name != 'status.md', path.name)
            bangs = re.findall(r'!`([^`]+)`', body)
            templates = [s for s in re.findall(r'`([^`]+)`', body) if 'sw.py' in s]
            self.assertTrue(bangs or templates, path.name)
            for command in bangs + templates:
                self.assertTrue(allowed(command, bash_rules(fields)), f'{path.name}: {command}')
                # Claude Code asks before a command with a $ expansion ("$HOME/..."), even one a rule matches.
                self.assertNotIn('$', command.replace('${CLAUDE_PLUGIN_ROOT}', ''), f'{path.name}: {command}')
            for command in bangs:
                self.assertIsNone(re.search(r'[;&|#`]|\$\(', command), f'{path.name}: {command}')

    def test_quiz_plan_stays_out_of_the_transcript(self):
        """Claude Code shows Bash tool output in the transcript, and every plan line carries its answer, so the plan
        comes from a `!` line (part of the hidden command prompt) with no typed text in it. The model asks only the
        first N questions and can't run the plan itself."""
        fields, body = command_file(ROOT / 'commands' / 'quiz.md')
        self.assertEqual(re.findall(r'!`([^`]+)`', body), ['python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" quiz --plan 50'])
        templates = re.findall(r'`([^`]+)`', re.sub(r'!`[^`]+`', '', body))
        self.assertEqual([t for t in templates if ' quiz' in t], [])
        self.assertFalse(allowed('python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw.py" quiz --plan 5', bash_rules(fields)))
        self.assertIn('only the first', body)
        self.assertEqual(sw.plan_size(['50']), 50)  # the line asks for the most a quiz can have

    def test_stage_without_value(self):
        with swlib.editing():
            pass
        before = (self.home / 'sw' / 'state.json').read_bytes()
        self.assertEqual(self.sw('stage'), 'Stage 1 (automatic)\n')
        self.assertEqual((self.home / 'sw' / 'state.json').read_bytes(), before)  # shown, not saved
        self.assertEqual(self.sw('stage', '2'), 'Stage 2 (pinned)\n')
        self.assertEqual(self.sw('stage'), 'Stage 2 (pinned)\n')

    def test_bare_aliases(self):
        out = self.sw('export', 'chatgpt')
        self.assertIn('--- "Custom instructions" box', out)
        self.assertIn('--- "More about you" box', out)
        self.assertTrue(self.sw('export', 'claude.ai').startswith('claude.ai > Settings'))
        with mock.patch('sys.stderr', new=io.StringIO()), self.assertRaises(SystemExit):
            sw.main(['export', 'chatgpt', 'claude-ai'])
        with mock.patch('sys.stderr', new=io.StringIO()), self.assertRaises(SystemExit):
            sw.main(['export', 'everything'])
        deck = self.home / 'deck.txt'
        self.sw('anki', 'all', '--out', str(deck))
        lines = deck.read_text(encoding='utf-8').splitlines()
        self.assertEqual(lines[:len(export.ANKI_HEADERS)], export.ANKI_HEADERS)
        self.assertEqual([n.split('\t')[0] for n in lines[len(export.ANKI_HEADERS):]],
                         [w['es'] for w in swlib.load_lexicon()])

    def test_phrases_quotes_punctuation(self):
        status = lambda es: swlib.find(swlib.load_state(), es)['status']
        self.assertEqual(self.sw('known', 'sin embargo'), 'Known: sin embargo\n')
        self.assertEqual((status('sin embargo'), status('sin')), ('known', 'active'))
        self.assertEqual(self.sw('known', '"tal vez"'), 'Known: tal vez\n')  # not la vez
        self.assertEqual((status('tal vez'), status('la vez')), ('known', 'queue'))
        self.assertEqual(self.sw('known', 'sin', 'embargo', 'pero'), 'Known: sin embargo, pero\n')  # a split phrase
        self.assertEqual(status('sin'), 'active')
        self.assertEqual(self.sw('known', 'por favor'), 'Known: por favor\n')
        self.assertEqual(self.sw('known', '¡hola!'), 'Known: hola\n')
        self.assertEqual(self.sw('learn', '“sin embargo”, zzz'),
                         'Back to learning: sin embargo\nNot in the word list: zzz\n')
        before = (self.home / 'sw' / 'state.json').read_bytes()
        self.assertEqual(self.sw('known', ','), 'Give one or more words from the list, like: known pero, sin embargo\n')
        self.assertEqual(self.sw('learn'), 'Give one or more words from the list, like: learn pero, sin embargo\n')
        self.assertEqual((self.home / 'sw' / 'state.json').read_bytes(), before)

    def test_record_batch(self):
        Review.met_long_ago(self, 5)
        with mock.patch('sys.stdout', new=io.StringIO()) as out, self.assertRaises(SystemExit) as caught:
            sw.main(['record', 'y:right', 'pero:wrong', 'zzz:right'])
        self.assertEqual(caught.exception.code, 1)
        state = swlib.load_state()
        self.assertEqual((swlib.find(state, 'y')['box'], swlib.find(state, 'pero')['last_bad']), (1, swlib.today()))
        lines = out.getvalue().splitlines()
        self.assertTrue(lines[0].startswith('y: right; next review'))
        self.assertTrue(lines[1].startswith('pero: wrong; next review'))
        self.assertIn('Not saved: zzz:right', lines[2])
        with mock.patch('sys.stdout', new=io.StringIO()) as out, self.assertRaises(SystemExit):
            sw.main(['record', 'con', 'con:right:le', 'con:maybe'])
        self.assertEqual([line.split(' (')[0] for line in out.getvalue().splitlines()],
                         ['Not saved: con', 'Not saved: con:right:le', 'Not saved: con:maybe'])
        self.assertNotIn('reviews', swlib.find(swlib.load_state(), 'con'))
        with swlib.editing() as state:
            swlib.set_status(swlib.find(state, 'el problema'), 'active', '2026-01-01')
        out = self.sw('record', 'el problema:right:la', 'entonces:right')
        self.assertIn('el problema: right with the wrong article, so same gap again', out)
        problema = swlib.find(swlib.load_state(), 'el problema')
        self.assertEqual((problema['box'], problema['reviews'][-1][1]), (0, 1))  # right, but the same gap again

    def test_anki_out_refuses_other_files(self):
        notes = self.home / 'notes.txt'
        notes.write_text('ORIGINAL\n')
        with self.assertRaises(SystemExit) as caught:
            self.sw('anki', '--out', str(notes))
        self.assertIn('is not an earlier Spanish Weave Anki export', str(caught.exception.code))
        self.assertEqual(notes.read_text(), 'ORIGINAL\n')
        earlier = self.home / 'earlier.txt'
        earlier.write_text(export.ANKI_HEADERS[0] + '\nold\tnote\n')
        link = self.home / 'link.txt'
        link.symlink_to(earlier)
        with self.assertRaises(SystemExit) as caught:
            self.sw('anki', '--out', str(link))
        self.assertIn('symlink', str(caught.exception.code))
        self.assertEqual(earlier.read_text(), export.ANKI_HEADERS[0] + '\nold\tnote\n')
        with self.assertRaises(SystemExit):
            self.sw('anki', '--out', str(self.home))  # a folder
        self.assertIn('Wrote', self.sw('anki', '--out', str(earlier)))  # an earlier export is replaced
        self.assertEqual(earlier.read_text(encoding='utf-8'), export.anki(swlib.load_state()))
        with mock.patch.dict(os.environ, {'HOME': str(self.home)}):  # anki.md passes '~/...' with no shell expansion
            out = self.sw('anki', '--out', '~/fresh.txt')
        self.assertIn(f'notes to {self.home / "fresh.txt"}.', out)
        self.assertEqual((self.home / 'fresh.txt').read_text(encoding='utf-8'), export.anki(swlib.load_state()))


DOCS = sorted(ROOT.glob('*.md')) + COMMANDS + [p for p in [ROOT.parent / 'README.md'] if p.exists()]


def section(path, title):
    """The text under a `## title` heading of a markdown file, up to the next `## ` heading."""
    text = path.read_text(encoding='utf-8')
    return text.split(f'\n## {title}\n', 1)[1].split('\n## ', 1)[0] if f'\n## {title}\n' in text else ''


class Docs(unittest.TestCase):
    """The docs friends and their agents follow: commands that run as written, and claims that match the code."""

    def test_versions_agree(self):
        """Installed copies update only when the version changes, so the plugin and extension move together."""
        versions = [json.loads((ROOT / path).read_text())['version']
                    for path in ('.claude-plugin/plugin.json', 'extension/manifest.json', 'extension/package.json')]
        self.assertEqual(len(set(versions)), 1, versions)
        self.assertGreaterEqual(tuple(int(part) for part in versions[0].split('.')), (0, 3, 0))

    def test_agent_docs_define_sw(self):
        """An agent's shell keeps no variables between commands, so a block that runs "$SW" sets it first."""
        text = (ROOT / 'INSTALL-FOR-AGENTS.md').read_text(encoding='utf-8')
        blocks = re.findall(r'```sh\n(.*?)```', text, re.S)
        self.assertTrue(any('"$SW"' in block for block in blocks))
        for block in blocks:
            defined = False
            for command in block.splitlines():
                defined = defined or command.startswith('SW=')
                if 'sw.py' in command and not command.startswith('SW='):
                    self.assertIn('~/.spanish-weave/app/scripts/sw.py', command)  # the copy that outlives the plugin
                if '"$SW"' in command and not command.startswith('SW='):
                    self.assertTrue(defined, f'"$SW" used before SW= in:\n{block}')

    def test_docs_avoid_sort_tail_lookup(self):
        """`find | sort | tail -1` picked the marketplace clone, and 0.2.9 over 0.2.10."""
        for path in DOCS:
            self.assertFalse('| sort | tail -1' in path.read_text(encoding='utf-8'), path.name)

    def test_update_steps_keep_the_site_choice(self):
        """Rerunning setup "with the same answers as the first time" passed --sites again, which turned every site back
        on for someone who had since picked "Only sites I turn on" in the popup."""
        for path in DOCS:
            text = ' '.join(path.read_text(encoding='utf-8').split())
            self.assertFalse('same answers' in text, path.name)
        update = section(ROOT / 'INSTALL-FOR-AGENTS.md', 'Update')
        self.assertIn('python3 "$SW" setup\n', update)
        self.assertNotIn('setup --sites', update)
        for name in ('README.md', 'START-HERE.md', 'HANDOFF-FOR-CLAUDE.md'):
            text = ' '.join((ROOT / name).read_text(encoding='utf-8').split())
            self.assertTrue('Keep the current site choice' in text, name)

    def test_docs_dont_say_everything_stays_local(self):
        """The word lists go to Claude, Codex and Gemini, so the Privacy sections can't say everything stays local."""
        for name in ('README.md', 'START-HERE.md'):
            privacy = section(ROOT / name, 'Privacy')
            self.assertIn('Gemini', privacy, name)
            for claim in ('Everything stays on your machine', 'Your words and progress stay on your computer'):
                self.assertFalse(claim in privacy, f'{name}: {claim}')


if __name__ == '__main__':
    unittest.main()


class UpstreamPorts(Home):
    """Improvements ported from French Weave (Jackie Oliver, MIT) in 0.3.2 and 0.3.3."""

    def test_gap_words_are_listed_and_the_first_words_stay(self):
        es = [w['es'] for w in swlib.load_lexicon()]
        for word in ('sino', 'tampoco', 'tan', 'aunque', 'no funciona', 'el sistema', 'desplegar', 'chistoso'):
            self.assertIn(word, es)
        self.assertLess(es.index('sino'), 100)  # the pero note points to it
        self.assertEqual(es[:5], ['y', 'pero', 'entonces', 'con', 'sin'])
        self.assertIn('tan', swlib.UNMEASURABLE)  # "a tan coat" is English

    def test_a_phrase_is_counted_before_the_words_inside_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chat = root / 'proj' / 'a.jsonl'
            chat.parent.mkdir()
            chat.write_text(line('The fix is small, es decir one line, and vale la pena.') + '\n')
            index = swlib.scan(['es decir', 'decir', 'vale la pena', 'la pena', 'resolver'], {}, root, start='2026-09-19')
            self.assertEqual(index['words']['es decir']['n'], 1)
            self.assertEqual(index['words']['decir']['n'], 0)  # only inside "es decir"
            self.assertEqual(index['words']['la pena']['n'], 0)
            self.assertNotIn('resolver', index['words'])  # "the DNS resolver" is English

    def test_each_use_goes_to_the_word_spelled_like_it(self):
        words = ['mañana', 'la mañana', 'al final', 'el final', 'es decir', 'decir']
        patterns = {es: swlib.pattern(es) for es in words}
        count = lambda text: swlib.uses(swlib.norm(text), patterns)[0]
        self.assertEqual(count('See you mañana, then.'), {'mañana': 1})
        self.assertEqual(count('Early in la mañana it rains.'), {'la mañana': 1})
        self.assertEqual(count('It worked al final.'), {'al final': 1})
        self.assertEqual(count('Read el final first.'), {'el final': 1})
        self.assertEqual(count('One line, es decir small.'), {'es decir': 1})
        self.assertEqual(count('Hard to decir.'), {'decir': 1})

    def test_quiz_keeps_una_vez_and_la_vez_apart(self):
        once = {'es': 'una vez', 'en': 'once'}
        time_ = {'es': 'la vez', 'en': 'the time (occasion)'}
        self.assertTrue(swlib.check(once, 'una vez', 'produce'))
        self.assertFalse(swlib.check(once, 'la vez', 'produce'))
        self.assertFalse(swlib.check(once, 'vez', 'produce'))
        self.assertFalse(swlib.check(time_, 'una vez', 'produce'))
        self.assertTrue(swlib.check(time_, 'vez', 'produce'))  # a missing article is fine for a noun
        self.assertFalse(swlib.check({'es': 'un poco', 'en': 'a little'}, 'poco', 'produce'))
        # A bare answer that is also another listed word: the learner decides ("mañana" is tomorrow too).
        self.assertIsNone(swlib.check({'es': 'la mañana', 'en': 'the morning'}, 'mañana', 'produce'))
        self.assertTrue(swlib.check({'es': 'la mañana', 'en': 'the morning'}, 'la mañana', 'produce'))

    def test_unaccented_donde_marks_the_dónde_being_learned(self):
        import sw
        state = swlib.new_state('2026-10-01')
        dónde = swlib.find(state, 'dónde')
        dónde.update(status='active', added='2026-10-01')
        swlib.save_state(state)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            sw.mark('asked')(argparse.Namespace(words=['donde'], command='learn'))
        self.assertEqual(out.getvalue().strip(), 'Back to learning: dónde')
        state = swlib.load_state()
        self.assertEqual(swlib.find(state, 'dónde')['status'], 'shaky')
        self.assertEqual(swlib.find(state, 'donde')['status'], 'queue')
        with contextlib.redirect_stdout(io.StringIO()) as out:
            sw.mark('known')(argparse.Namespace(words=['donde'], command='known'))
        self.assertEqual(out.getvalue().strip(), 'Known: dónde')  # known too: the word in use
        # A typed accent keeps the exact spelling: with donde in use, "known dónde" marks dónde, never donde.
        state = swlib.new_state('2026-10-01')
        swlib.find(state, 'donde').update(status='active', added='2026-10-01')
        swlib.save_state(state)
        with contextlib.redirect_stdout(io.StringIO()):
            sw.mark('known')(argparse.Namespace(words=['dónde'], command='known'))
        state = swlib.load_state()
        self.assertEqual(swlib.find(state, 'dónde')['status'], 'known')
        self.assertEqual(swlib.find(state, 'donde')['status'], 'active')

    def test_export_can_copy_the_claude_ai_block(self):
        import sw
        from unittest import mock
        with mock.patch.object(sw.shutil, 'which', lambda cmd: '/usr/bin/pbcopy' if cmd == 'pbcopy' else None), \
                mock.patch.object(sw.subprocess, 'run') as run:
            self.assertTrue(sw.copy_to_clipboard('block'))
        self.assertEqual(run.call_args.args[0], ['pbcopy'])
        self.assertEqual(run.call_args.kwargs['input'], b'block')  # UTF-8 bytes, read under a UTF-8 locale
        self.assertEqual(run.call_args.kwargs['env']['LC_ALL'], 'en_US.UTF-8')
        with mock.patch.object(sw.shutil, 'which', lambda cmd: None):
            self.assertFalse(sw.copy_to_clipboard('block'))  # no clipboard tool: the printed block still works

    def test_new_sense_guards_appear_with_their_words(self):
        import weave
        texts = dict((words, text) for words, text in weave.GUARDS)
        self.assertIn('"here\'s"', texts[('aquí',)])
        self.assertIn('never "just"', texts[('ya',)])
        self.assertIn('never for the verb "like"', texts[('como',)])

    def test_glosses_cover_the_common_senses(self):
        import csv
        rows = {row[0]: row[1] for row in csv.reader(open(ROOT / 'data' / 'lexicon.csv', encoding='utf-8'))}
        self.assertIn('happen', rows['pasar'])
        self.assertIn('email', rows['el correo'])
        self.assertIn('loud', rows['fuerte'])
        self.assertIn('quickly', rows['rápido'])


class SeedAfterHook(unittest.TestCase):
    """--known-top N gives N known even when the prompt hook created the state first (after French Weave, MIT)."""

    def test_known_top_after_a_prompt_already_created_the_state(self):
        day = swlib.today()
        state = swlib.new_state()
        swlib.refill(state, day)
        self.assertEqual(sum(w['status'] == 'active' for w in state['words']), 5)
        swlib.seed_known(state, 40, day)
        self.assertEqual(sum(w['status'] == 'known' for w in state['words'][:40]), 40)
        self.assertEqual(state['refilled'][1], 0)  # today's allowance is back, so refill can pick 5 new words
        swlib.refill(state, day)
        self.assertEqual(sum(w['status'] == 'active' for w in state['words']), 5)

    def test_words_with_progress_are_never_seeded(self):
        day = swlib.today()
        state = swlib.new_state()
        swlib.refill(state, day)
        swlib.apply_event(state, 'pero', 'seen', day)
        swlib.seed_known(state, 40, day)
        self.assertEqual({w['es']: w['status'] for w in state['words']}['pero'], 'active')

    def test_new_gemini_key_format_is_accepted(self):
        import sw
        self.assertTrue(sw.KEY_SHAPE.match('AQ.' + 'A' * 40))
        self.assertTrue(sw.KEY_SHAPE.match('AIza' + 'b' * 35))
        self.assertFalse(sw.KEY_SHAPE.match('AQ.short'))
        self.assertFalse(sw.KEY_SHAPE.match('not a key at all, has spaces and is long enough'))


class OutsideEvents(Home):
    """Events from outside the Mac's own commands: the extension (through the native host) and the phone inbox."""

    def test_quiz_answers_from_outside_are_checked_and_recorded_like_the_quiz(self):
        state = swlib.new_state('2026-10-20')
        pero = swlib.find(state, 'pero')
        events = [
            {'word': 'pero', 'kind': 'quiz', 'result': 'right', 'day': '2026-10-21'},
            {'word': 'pero', 'kind': 'quiz', 'result': 'wrong', 'day': '2026-10-21'},  # that day is answered
            {'word': 'la idea', 'kind': 'quiz', 'result': 'right', 'day': '2026-10-21'},  # not in use yet
            {'word': 'pero', 'kind': 'quiz', 'result': 'maybe', 'day': '2026-10-21'},
            {'word': 'pero', 'kind': 'quiz', 'result': 'right', 'day': '1999-01-01'},  # too old
            {'word': 'x' * 65, 'kind': 'quiz', 'result': 'right'},
            'junk',
        ]
        applied, skipped = swlib.apply_events(state, events, kinds=('quiz',), today_='2026-10-22')
        self.assertEqual((applied, skipped), (1, 6))
        self.assertEqual(pero['box'], 1)
        self.assertEqual(pero['reviews'][-1][:2], ['2026-10-21', 1])
        # A later answer from the Mac's own quiz wins over an older phone answer that arrives late.
        swlib.review(state, 'pero', False, day='2026-10-23')
        self.assertEqual(swlib.apply_events(state, [{'word': 'pero', 'kind': 'quiz', 'result': 'right', 'day': '2026-10-22'}],
                                            kinds=('quiz',), today_='2026-10-23'), (0, 1))
        # The extension's path never takes quiz answers.
        self.assertEqual(swlib.apply_events(state, [{'word': 'pero', 'kind': 'quiz', 'result': 'right'}]), (0, 1))
