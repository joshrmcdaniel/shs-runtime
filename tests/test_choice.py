import copy
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from shs_runtime.choice import ChoiceLayout
from shs_runtime.content import ContentLibrary
from shs_runtime.runtime import Session
from test_runtime import answer_screen, host_call, text_words
from test_vm import program


@unittest.skipUnless(Path('.shs-library/library.json').is_file(), 'user library is not present')
class ChoiceTests(unittest.TestCase):
    def resources(self):
        library = ContentLibrary(Path('.shs-library'))
        self.addCleanup(library.close)
        return library.open_episode('The_New_Girl.exp')

    def test_original_fonts_portrait_insets_and_variable_option_lengths(self):
        layout = ChoiceLayout(self.resources())
        details = dict(title='Make your choice!', text='Are you gonna make a move on her?',
                       options=['Definitely.', "Take another man's girl? No way!", "She's not really my type."],
                       enabled=[True, False, True])
        original = copy.deepcopy(details)
        page = layout.page(details, theme=1, has_portrait=True)
        self.assertEqual(details, original)
        self.assertEqual((page.box.x, page.box.width), (20, 280))
        self.assertEqual(page.title_font, 'PajamaHip26')
        self.assertEqual(len(page.title.lines), 2)
        self.assertEqual(page.portrait.center[0], 57)
        self.assertEqual([row.rect.height for row in page.rows], [44, 44, 44])
        self.assertEqual([row.index for row in page.rows], [0, 1, 2])
        self.assertFalse(page.rows[1].enabled)
        self.assertGreater(page.description.lines[0].x, 0)
        plain = layout.page(details, theme=2, has_portrait=False)
        self.assertEqual(plain.title_font, 'PajamaHip266')
        self.assertIsNone(plain.portrait)
        self.assertEqual(plain.description.lines[0].x, 0)

        details['options'] = ['A long option with multiple lines. ' * 4] * 9
        details['enabled'] = [True] * 9
        long = layout.page(details, theme=1, has_portrait=True)
        self.assertGreater(long.max_scroll, 0)
        self.assertEqual(len(long.rows), 9)
        for row in long.rows:
            _, top, _, bottom = row.text.ink_bounds
            self.assertGreater(row.rect.height, 44)
            self.assertGreaterEqual(row.origin[1] + top, row.rect.y)
            self.assertLessEqual(row.origin[1] + bottom, row.rect.y + row.rect.height)

    @unittest.skipUnless(importlib.util.find_spec('pygame'), 'desktop extra is not installed')
    def test_translucent_panel_matches_on_rgb_and_cocoa_default_canvases(self):
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        from shs_runtime.desktop import Desktop
        import pygame

        self.addCleanup(pygame.quit)
        resources = self.resources()
        ui = Desktop(Session(resources), audio=False)
        for _ in range(35):
            answer_screen(ui.session)
        saved = ui.session.snapshot()
        ui.render()
        expected = pygame.image.tobytes(ui.canvas, 'RGB')
        surface = pygame.Surface

        def cocoa_surface(size, flags=0, depth=0, masks=None):
            if depth == 0 and masks is None:
                return surface(size, flags, 32, (0xff0000, 0xff00, 0xff, 0xff000000))
            return surface(size, flags, depth) if masks is None else surface(size, flags, depth, masks)

        with patch('pygame.Surface', side_effect=cocoa_surface):
            simulated = Desktop(Session.from_snapshot(resources, saved), audio=False)
            simulated.render()
            self.assertIsNone(simulated.error)
            self.assertEqual(pygame.image.tobytes(simulated.canvas, 'RGB'), expected)

    @unittest.skipUnless(importlib.util.find_spec('pygame'), 'desktop extra is not installed')
    def test_native_choice_menu_timer_save_and_resized_selection(self):
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        from shs_runtime.desktop import Desktop
        import pygame

        self.addCleanup(pygame.quit)
        resources = self.resources()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        resources.library.directory = Path(temporary.name)
        words, (title, prompt, no, yes) = text_words('Make your choice!', 'A timed question.', 'No', 'Yes')
        resources.programs[65000] = program(
            *host_call(2, title, prompt, 1000, 1, -1, 0),
            *host_call(3, no, 77, 0), *host_call(3, yes, 88, 1),
            *host_call(4, 0), 0x21, (0x1f, 0xfe01), words=words)
        ui = Desktop(Session(resources, start_script=65000), audio=False)
        before = ui.session.snapshot()
        ui.render()
        self.assertIsNone(ui.error)
        self.assertEqual(before, ui.session.snapshot())
        self.assertEqual([command for _, command in ui.buttons], [('choose', 1), ('menu',)])

        ui.command(('menu',))
        ui.render()
        ui.tick(5000)
        ui.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2))
        self.assertEqual(before, ui.session.snapshot())
        ui.command(('save',))
        self.assertTrue(ui.session.save_path.is_file())
        ui.command(('load',))
        self.assertFalse(ui.menu_open)
        self.assertEqual(before, ui.session.snapshot())
        ui.tick(250)
        self.assertEqual(ui.session.remaining_ms, 750)

        ui.window = pygame.display.set_mode((800, 600), pygame.RESIZABLE)
        ui.render()
        rect = next(rect for rect, command in ui.buttons if command == ('choose', 1))
        x = ui.viewport.x + rect.centerx * ui.viewport.width / 480
        y = ui.viewport.y + rect.centery * ui.viewport.height / 720
        ui.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(x, y)))
        self.assertEqual(ui.session.pending.request.args, (88,))
        self.assertEqual(ui.session.engine.result_cells[0], 88)
        self.assertIsNone(ui.error)

    @unittest.skipUnless(importlib.util.find_spec('pygame'), 'desktop extra is not installed')
    def test_real_choice_survives_rendering_and_scroll_keeps_last_index_reachable(self):
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        from shs_runtime.desktop import Desktop
        import pygame

        self.addCleanup(pygame.quit)
        resources = self.resources()
        ui = Desktop(Session(resources), audio=False)
        for _ in range(35):
            answer_screen(ui.session)
        before = ui.session.snapshot()
        ui.render()
        self.assertIsNone(ui.error)
        self.assertEqual(before, ui.session.snapshot())
        self.assertEqual([c for _, c in ui.buttons], [('choose', 0), ('choose', 1), ('menu',)])
        for choice, pc in ((0, 336), (1, 352)):
            ui.session = Session.from_snapshot(resources, before)
            ui.render()
            ui.command(('choose', choice))
            self.assertEqual(ui.session.pending.request.pc, pc)

        words, (title, options, prompt) = text_words('Make your choice!', '|'.join(['An option'] * 9), 'Pick one.')
        resources.programs[65000] = program(*host_call(1, title, options, prompt, 0, -1, -1, 0, 1),
                                            0x21, (0x1f, 0xfe01), words=words)
        ui.session = Session(resources, start_script=65000)
        ui.session.advance()
        ui.render()
        self.assertGreater(ui.max_scroll, 0)
        ui.scroll = ui.max_scroll
        ui.render()
        rect = next(rect for rect, command in ui.buttons if command == ('choose', 8))
        gear = next(rect for rect, command in ui.buttons if command == ('menu',))
        self.assertFalse(rect.colliderect(gear))
        ui.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
        self.assertEqual(ui.session.pending.request.args, (8,))
