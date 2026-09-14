import copy
import json
from pathlib import Path
import unittest

from shs_runtime.content import ContentLibrary
from shs_runtime.minigames import NativeRandom
from shs_runtime.runtime import SaveError, Session
from shs_runtime.word_grid import GridProblem, WordGrid
from test_runtime import Resources, host_call, text_words
from test_vm import program


def resources(*, tutorial=False):
    words, refs = text_words('Find a word', 'CAT', 'cat', 'catx', 'cat\ncat', 'Learn',
                             'Trace the letters', 'Correct', 'Try again')
    table = len(words)
    words += [3, 2, *refs[:4], 1, 0, 1, -1]
    tutor = len(words)
    words += [refs[5], refs[6], 1, 0, 0, 3, 2, refs[0], refs[1], refs[2], 1,
              refs[4], 1, 1, 0, 0, -2]
    args = [2, 200, 1000, 500, 0, -1, -1, 0, -1, 0, 0, 1, table,
            1, refs[7], refs[8], 0, 0, int(tutorial), tutor]
    return Resources(program(*host_call(96, *args), 0x21, (0x1f, 0xfe01), words=[w & 0xffff for w in words]))


def play_phase(session):
    for _ in range(60):
        if session.engine.word_grid.phase == 1:
            return
        session.tick(250)
    raise AssertionError('Grid did not enter active play')


class GridTests(unittest.TestCase):
    def test_native_random_uses_full_product_and_signed_absolute_value(self):
        r = NativeRandom(1)
        self.assertEqual(r.next(), 16838)
        self.assertEqual(r.state, 1103527590)
        # High multiplication bits must survive; ANSI rand() returns 5758 here.
        self.assertEqual(r.next(), 1507104382)
        self.assertEqual(r.state, 2524885223)

    def test_diagonal_paths_no_reuse_and_cumulative_start_score(self):
        s = Session(resources(tutorial=True)); s.advance(); play_phase(s)
        g = s.engine.word_grid
        self.assertEqual(g.board, list('catcat'))
        self.assertEqual(g.starts, [0, 3])
        held = s.vm.snapshot()
        s.grid_pointer('down', 0)
        s.grid_pointer('move', 2)  # Cannot jump over the middle tile.
        self.assertEqual(g.selection, [0])
        s.grid_pointer('move', 4)  # Diagonal C -> A.
        s.grid_pointer('move', 0)  # Cannot revisit the C.
        self.assertEqual(g.selection, [0, 4])
        s.grid_pointer('move', 2)  # Diagonal A -> T; submit without mouse-up.
        self.assertEqual((g.score, g.starts), (100, [3]))
        self.assertEqual(g.selection, [])
        self.assertEqual(s.engine.sound_ids, [8110, 8111])
        s.grid_pointer('up')
        # Previously used starting cell cannot score a second time.
        for event, i in [('down', 0), ('move', 1), ('move', 2), ('up', None)]:
            s.grid_pointer(event, i)
        self.assertEqual(g.score, 100)
        for event, i in [('down', 3), ('move', 1), ('move', 5)]:
            s.grid_pointer(event, i)
        self.assertEqual(g.score, 300)
        self.assertEqual(g.phase, 3)
        self.assertEqual(s.vm.snapshot(), held)
        for _ in range(5): s.tick(250)
        self.assertFalse(g.tutorial)
        self.assertEqual(g.score, 0)  # Tutorial points are cleared on entering play.

    def test_clocks_callback_and_result_cells_are_distinct(self):
        for score, expected in [(100, 0), (200, 1)]:
            s = Session(resources());s.advance();g=s.engine.word_grid
            self.assertEqual(g.remaining_ms, 2000)
            s.tick(99999)
            self.assertEqual(g.phase_ms, 750)  # Native clamps a single frame to 250.
            self.assertEqual(g.remaining_ms, 2000)
            play_phase(s)
            g.score = score
            s.engine.result_cells[0] = 19
            for _ in range(160):
                a = s.tick(250)
                if a.name != 'word_grid': break
            self.assertEqual(a.request.args, (expected,))
            self.assertEqual(s.engine.result_cells[0], 19)
            self.assertIsNone(s.engine.word_grid)

    def test_save_mid_drag_and_continue_same_random_boards(self):
        r = resources(tutorial=True);s=Session(r);s.advance();play_phase(s)
        s.grid_pointer('down', 0);s.grid_pointer('move', 4)
        saved = json.loads(json.dumps(s.snapshot()))
        restored = Session.from_snapshot(r, saved)
        self.assertEqual(restored.snapshot(), s.snapshot())
        for stage, i in [('move', 2), ('up', None), ('down', 3), ('move', 4), ('move', 5), ('up', None)]:
            s.grid_pointer(stage, i);restored.grid_pointer(stage, i)
        for _ in range(80):
            s.tick(33);restored.tick(33)
            self.assertEqual(s.snapshot(), restored.snapshot())
        for key, value in [('board', []), ('selection', [0, 0]), ('starts', [2]),
                            ('order', [1]), ('remaining_ms', -1), ('score', -1)]:
            state = copy.deepcopy(saved); state['engine']['word_grid'][key] = value
            with self.subTest(key=key), self.assertRaises(SaveError): Session.from_snapshot(r, state)

    def test_generated_boards_are_solvable_and_restore_without_redrawing(self):
        for seed in range(30):
            s = Session(resources());s.engine.random=NativeRandom(seed);s.advance()
            g=s.engine.word_grid
            self.assertGreaterEqual(len(g.starts), 1)
            for start in g.starts:
                self.assertEqual(''.join(g.board[i] for i in g.find_path(start, 'cat')), 'cat')
            restored=Session.from_snapshot(s.resources,s.snapshot())
            self.assertEqual(restored.snapshot(),s.snapshot())

    @unittest.skipUnless(Path('.shs-library/library.json').exists(), 'user library absent')
    def test_actual_new_girl_grid_records(self):
        with ContentLibrary(Path('.shs-library')) as lib:
            r=lib.open_episode('The_New_Girl.exp');s=Session(r,start_script=25003)
            # Exercise the original frame-building instructions and original data
            # table directly; this is a diagnostic entry, not a production skip.
            s.vm.pc=75;s.vm._push(16362);s.vm.fp=0;s.engine.random=NativeRandom(1)
            a=s.advance();g=s.engine.word_grid
            self.assertEqual(a.name,'word_grid')
            self.assertEqual((g.duration_ms,g.target,g.round_limit_ms,g.bonus_ms),(45000,1800,10000,5000))
            self.assertEqual([p.words for p in g.problems],[['drive'],['avoid'],['careful']])
            self.assertEqual(g.board,list('beirvbrrbriievdd'))
            self.assertEqual(g.starts,[14])
            self.assertEqual(Session.from_snapshot(r,s.snapshot()).snapshot(),s.snapshot())
