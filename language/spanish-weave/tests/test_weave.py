"""Offline tests for the hook, word state, native host and setup. Run: python3 -m unittest discover -s tests"""
import io
import json
import os
from pathlib import Path
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
            'rápidamente': 'RRAH-pee-dah-MEN-teh', 'el problema': 'el proh-BLEH-mah', 'una idea': 'oo-nah ee-DEH-ah',
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
        swlib.promote(state, '2026-10-15', {})
        self.assertEqual(swlib.find(state, 'con')['status'], 'shaky')
        swlib.promote(state, '2026-10-16', {})
        self.assertEqual(swlib.find(state, 'con')['status'], 'known')

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
        sw.main(['pause'])
        self.assertEqual(self.run_hook({'session_id': 'x'}), '')
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
            self.assertLess(len(export.claude_ai(state)), 6000)
            if known >= 400:
                self.assertIn('most common Spanish words', brief)
                # French Weave's budget was 3,100 bytes; Spanish glosses run a little longer and accented letters
                # take 2 bytes each, so this budget is 3,300 (about 3,180 at 1,000 known words).
                self.assertLess(len(brief.encode()), 3300, known)

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

    def test_codex_exec_is_scripted_tui_is_not(self):
        data = {'turn_id': 't', 'session_id': 's'}
        self.assertFalse(weave.interactive({}, data, exec_check=lambda: True))
        self.assertTrue(weave.interactive({}, data, exec_check=lambda: False))
        self.assertTrue(weave.interactive({'SPANISH_WEAVE_FORCE': '1'}, data, exec_check=lambda: True))
        code = f'import sys, os; sys.path.insert(0, {str(ROOT / "scripts")!r}); import weave; print(weave.codex_exec(os.getpid()))'
        sh = subprocess.run(['codex', '-c', code, 'exec'], executable=sys.executable, capture_output=True, text=True)
        self.assertEqual(sh.stdout.strip(), 'True', sh.stderr)

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
        self.assertEqual(after['words'][0], {'es': 'pero', 'en': 'but', 'hint': 'PEH-roh', 'status': 'shaky'})
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


if __name__ == '__main__':
    unittest.main()
