import copy
import importlib.util
import json
import os
from pathlib import Path
import unittest

from shs_runtime.engine import EngineAction
from shs_runtime.runtime import SaveError, Session
from shs_runtime.vm import VMError
from test_runtime import Resources, host_call
from test_vm import program


def resources(argument, *, dynamic_count=False):
    call = [(0x1a, argument), (0x20, 1), (0x1e, 91)] if dynamic_count else host_call(91, argument)
    return Resources(program((0x1a, 77), *call, 0x21, (0x1f, 0xfe02), 0x33))


class LoadingTests(unittest.TestCase):
    def test_timer_gate_call_frame_return_and_save_for_both_argument_forms(self):
        for argument in (0, 1, -1):
            for dynamic in (False, True):
                with self.subTest(argument=argument, dynamic=dynamic):
                    r = resources(argument, dynamic_count=dynamic)
                    s = Session(r)
                    s.engine.result_cells[0] = 42
                    action = s.advance()
                    self.assertEqual(action.name, 'loading')
                    self.assertEqual(s.vm.stack, (77, argument) if argument else (77,))
                    self.assertEqual(s.vm.pending, action.request if argument else None)
                    self.assertEqual(s.vm.result, -1 if argument else 0)
                    frozen = s.vm.snapshot()
                    with self.assertRaises(VMError):
                        s.answer()
                    self.assertEqual(s.vm.snapshot(), frozen)
                    s.tick(1500)
                    self.assertEqual(s.pending.name, 'loading')  # Ignored native constructor argument.
                    s = Session.from_snapshot(r, json.loads(json.dumps(s.snapshot())))
                    self.assertEqual(s.engine.loading.frame, 26)
                    s.tick(1500)
                    self.assertEqual(s.pending.name, 'loading')  # Strict >, not >=.
                    self.assertEqual(s.vm.snapshot(), frozen)
                    s = Session.from_snapshot(r, s.snapshot())
                    self.assertEqual(s.tick(1).request.args, (77, 0))
                    self.assertIsNone(s.engine.loading)
                    self.assertEqual(s.engine.result_cells[0], 42)
                    self.assertEqual(Session.from_snapshot(r, s.snapshot()).snapshot(), s.snapshot())

    def test_old_unsupported_checkpoint_upgrades_without_replaying_script(self):
        for argument in (0, 1):
            r = resources(argument)
            s = Session(r)
            request = s.vm.run()
            s.pending = EngineAction('unhandled_yield', request, False)
            old = s.snapshot(); old['version'] = 5
            del old['engine']['loading']
            original = copy.deepcopy(old)
            restored = Session.from_snapshot(r, old)
            self.assertEqual(old, original)
            self.assertEqual(restored.pending.name, 'loading')
            self.assertEqual(restored.vm.steps_executed, s.vm.steps_executed)
            self.assertEqual(restored.tick(3001).request.args, (77, 0))

    def test_saved_gate_rejects_invalid_timer_argument_and_completed_call(self):
        for argument in (0, 1):
            r = resources(argument)
            s = Session(r); s.advance()
            changes = [(('engine', 'loading', 'elapsed_ms'), -1),
                       (('engine', 'loading', 'elapsed_ms'), 3001),
                       (('engine', 'loading', 'elapsed_ms'), True),
                       (('engine', 'loading', 'blocking'), not bool(argument)),
                       (('engine', 'loading'), None), (('pending',), None)]
            if argument == 0:
                changes += [(('vm', 'result'), 1), (('vm', 'pc'), s.vm.pc + 1)]
            for path, value in changes:
                state = s.snapshot(); target = state
                for key in path[:-1]: target = target[key]
                target[path[-1]] = value
                with self.subTest(argument=argument, path=path), self.assertRaises(SaveError):
                    Session.from_snapshot(r, state)

    @unittest.skipUnless(importlib.util.find_spec('pygame') and Path('.shs-library/library.json').is_file(),
                         'desktop extra and user content required')
    def test_original_frames_render_and_input_focus_pause_and_restore_preserve_timer(self):
        os.environ['SDL_VIDEODRIVER'] = os.environ['SDL_AUDIODRIVER'] = 'dummy'
        import pygame
        from shs_runtime.content import ContentLibrary
        from shs_runtime.desktop import Desktop
        self.addCleanup(pygame.quit)
        with ContentLibrary(Path('.shs-library')) as lib:
            r = lib.open_episode('Football Star')
            r.programs[25001] = resources(1).program(25001)
            ui = Desktop(Session(r), audio=False)
            ui.render(); self.assertIsNone(ui.error)
            first = pygame.image.tobytes(ui.canvas, 'RGB')
            # Desktop ticks are capped; a half second of active frames changes the icon.
            for _ in range(5): ui.tick(100)
            ui.render(); self.assertIsNone(ui.error)
            second = pygame.image.tobytes(ui.canvas, 'RGB')
            self.assertNotEqual(first, second)
            saved = ui.session.snapshot()
            ui.command(('continue',)); ui.command(('choose', 0))
            ui.command(('menu',)); ui.tick(5000); ui.command(('resume',))
            ui.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST)); ui.tick(5000)
            ui.handle_event(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
            self.assertEqual(ui.session.snapshot(), saved)
            ui.session = Session.from_snapshot(r, saved)
            ui.render(); self.assertIsNone(ui.error)
            self.assertEqual(pygame.image.tobytes(ui.canvas, 'RGB'), second)
