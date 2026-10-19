"""Offline tests for the hook, word state, native host and setup. Run: python3 -m unittest discover -s tests"""
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


def word(es, status='known'):
    return {'es': es, 'en': 'meaning', 'hint': 'hint', 'status': status, 'added': '2026-10-01', 'changed': '',
            'days': [], 'last_bad': ''}


class Home(unittest.TestCase):
    """Each test gets its own state dir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {'SPANISH_WEAVE_HOME': str(self.home / 'sw')})
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
        self.assertEqual(weave.share(english, words), (0, 57, 0, 0))
        woven = 'The build passes, y the cache is warm, entonces nothing else needs el perro, pero solo sencillo things wait. ' * 3
        # y, entonces, el perro (2), pero, sencillo: 6 Spanish words a sentence, 2 of them learning words; solo can't be counted
        self.assertEqual(weave.share(woven + '```y entonces pero```\n(el perro = the dog, "el PEH-rroh")\nRecall: y?', words), (18, 57, 6, 0))
        self.assertIn('under the 12% target', weave.calibration(english, state))
        self.assertIn('over the 20% cap', weave.calibration(woven, state))
        self.assertEqual(weave.calibration('Done, y pushed.', state), '')
        spanish = ("Agregué una sección a README.md. Dice que una exportación vacía borra las filas, pero la tabla se "
                   "queda, y no ejecuté nada. Los otros problemas están en sync.py, así que dime si los debo corregir. ") * 2
        self.assertIn('slipped into Spanish sentences', weave.calibration(spanish, state))
        overlap = [word('tener'), word('tener cuidado'), word('todo'), word('todo el mundo')]
        self.assertEqual(weave.share('Please tener cuidado, todo el mundo, then tener it. ' * 6, overlap)[0], 36)  # 2 + 3 + 1 per sentence, not 8

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
        spanish, total, _, _ = weave.share(sentence * 6000, words)  # about 580 KB
        self.assertLess(total, weave.SCORED // 4)  # only the end is scored...
        small, small_total, _, _ = weave.share(sentence * 20, words)
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
        with mock.patch('sys.stdout', new=io.StringIO()):
            sw.main(['pause'])
        self.assertEqual(self.run_hook({'session_id': 'x'}), '')
        with mock.patch('sys.stdout', new=io.StringIO()):
            sw.main(['resume'])
        self.assertIn('Spanish Weave', self.run_hook({}))

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

    def test_brief_and_exports_stay_small(self):
        for known in (50, 400, 1000):
            state = grown(known)
            brief = weave.brief(state, {}, {'es': 'y', 'en': 'and', 'hint': 'ee'})
            about, respond = export.chatgpt(state)
            self.assertLessEqual(len(about), export.CHATGPT_LIMIT)
            self.assertLessEqual(len(respond), export.CHATGPT_LIMIT)
            self.assertLess(len(export.claude_ai(state)), make_blocks.CLAUDE_AI_MAX)
            if known >= 400:
                self.assertIn('most common Spanish words', brief)
                # French Weave's budget was 3,100 bytes. Spanish glosses run a little longer, accented letters take 2
                # bytes each, and the usage guards (es vs está, esto vs este, sino, bien...) add about 600 bytes once
                # every word is in use, so this budget is 3,900 (about 3,800 at 1,000 known words).
                self.assertLess(len(brief.encode()), 3900, known)
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
                self.assertIn(f'up to about the {export.ordinal(n)} most frequent', parsed['known'])

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
        self.assertEqual(placement.estimate(state, number(lambda band: band is not None))[0], 1040)  # every real word
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
        self.assertEqual(sum(w['status'] == 'known' for w in state['words'][:250]), 245)  # the 5 learning words stay
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


class Blocks(unittest.TestCase):
    def test_blocks_are_current_and_fit(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'make_blocks.py'), '--check'],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


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
        raw = b''.join(struct.pack('=I', len(m)) + m for m in (json.dumps(x).encode() for x in messages))
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'sw_host.py')], input=raw, capture_output=True,
                                timeout=30, env=dict(os.environ))
        out, replies = result.stdout, []
        while out:
            size = struct.unpack('=I', out[:4])[0]
            replies.append(json.loads(out[4:4 + size]))
            out = out[4 + size:]
        return replies

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
        self.assertEqual(events, {'ok': True, 'applied': 2})
        self.assertEqual(after['words'][0], {'es': 'pero', 'en': 'but', 'hint': 'PEH-roh', 'status': 'shaky',
                                             'note': "'not X but Y' is sino"})
        self.assertNotEqual(after['version'], state['version'])
        self.assertFalse(bad['ok'])

    def test_state_reply_carries_prefs(self):
        with swlib.editing() as state:
            state['prefs'] = {'extension_sites': 'ask'}
        reply, = self.converse({'type': 'state'})
        self.assertEqual(reply['prefs'], {'extension_sites': 'ask'})

    def test_message_framing(self):
        stream = io.BytesIO()
        sw_host.write_message(stream, {'a': 'é'})
        stream.seek(0)
        self.assertEqual(sw_host.read_message(stream), {'a': 'é'})
        self.assertIsNone(sw_host.read_message(io.BytesIO(b'')))


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
        self.assertEqual(json.loads((codex / 'hooks.json').read_text())['hooks'], dict(theirs['hooks'], UserPromptSubmit=[]))
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
        self.assertEqual(sum(w['status'] == 'known' for w in state['words'][:150]), 145)
        self.assertEqual(swlib.stage_for(state), 2)  # 145 known: stage 3 comes once the learning words graduate
        self.assertEqual(state['prefs'], {'extension_sites': 'ask'})
        before = json.dumps(state)
        state = self.run_setup('--known-top', '40')  # a lower answer later changes nothing
        self.assertEqual(json.dumps(state), before)
        self.assertEqual(state['prefs'], {'extension_sites': 'ask'})  # --sites left out keeps the choice
        self.assertEqual(self.run_setup('--sites', 'all')['prefs'], {'extension_sites': 'all'})

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

    def test_extension_id_matches_manifest_key(self):
        import base64
        import hashlib
        key = json.loads((ROOT / 'extension' / 'manifest.json').read_text())['key']
        digest = hashlib.sha256(base64.b64decode(key)).hexdigest()[:32]
        self.assertEqual(''.join(chr(ord('a') + int(c, 16)) for c in digest), sw.EXTENSION_ID)


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


if __name__ == '__main__':
    unittest.main()
