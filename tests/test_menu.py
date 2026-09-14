import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

from shs_runtime.content import ContentError, ContentLibrary, digest, import_game
from shs_runtime.menu import MenuFont, MenuState, MenuStrings, default_library, remember_library
from shs_runtime.runtime import SaveError
from test_content import FAKE_NATIVE, archive, make_apk, metadata
from test_vm import program


class MenuContractTests(unittest.TestCase):
    def test_ui_strings_are_offsets_and_byte_text_not_exp_metadata(self):
        payload = b'Play\0Caf\xe9\0'
        data = struct.pack('>iBhh2h', 1, 0, 0, 2, 13, 18) + payload
        strings = MenuStrings.parse(data)
        self.assertEqual(strings.strings, ('Play', 'Café'))
        with self.assertRaises(ContentError):
            MenuStrings.parse(data[:-1])
        invalid = bytearray(data)
        struct.pack_into('>h', invalid, 9, 1)
        with self.assertRaises(ContentError):
            MenuStrings.parse(bytes(invalid))

    def test_embedded_glyph_colors_and_spacing_are_read_from_content(self):
        data = struct.pack('>bBbhb', 3, 0, -1, 1, 2) + b'A' + struct.pack('>hhBB', -1, 1, 2, 2)
        data += bytes((128, 10, 20, 30)) * 4
        font = MenuFont.parse(data)
        self.assertEqual((font.space, font.tracking, font.height), (3, -1, 2))
        self.assertEqual(font.glyph('a').pixels, bytes((10, 20, 30, 128)) * 4)
        for bad in (data[:-1], data + b'bad'):
            with self.assertRaises(ContentError):
                MenuFont.parse(bad)

    def test_frozen_default_never_uses_working_directory(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'linux'), \
                patch.dict(os.environ, {'XDG_DATA_HOME': '/tmp/shs-test-data'}):
            self.assertEqual(default_library(), Path('/tmp/shs-test-data/SHS Runtime/library'))

    def test_chosen_library_is_remembered_across_working_directories(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch('shs_runtime.menu.user_data_directory', return_value=Path(directory) / 'preferences'):
            chosen = Path(directory) / 'my-game'
            remember_library(chosen)
            with patch.object(sys, 'frozen', True, create=True):
                self.assertEqual(default_library(), chosen.resolve())
            self.assertEqual(default_library(), chosen.resolve())  # Also overrides a checkout's library.
            self.assertEqual(json.loads((Path(directory) / 'preferences/launcher.json').read_text())['version'], 1)


class LibraryMenuTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        profile = patch('shs_runtime.content.NATIVE_SHA256', digest(FAKE_NATIVE))
        profile.start()
        self.addCleanup(profile.stop)
        self.episode = archive({1: metadata(), 25001: program(0x33).to_bytes()})
        self.apk = self.root / 'input.apk'
        make_apk(self.apk, self.episode)
        self.directory = self.root / 'library'
        import_game(self.apk, [], self.directory)
        self.library = ContentLibrary(self.directory)
        self.addCleanup(self.library.close)

    def test_incremental_import_deduplicates_and_validates_whole_batch(self):
        state = MenuState(self.library)
        session = state.session(state.selected)
        session.advance()
        state.checkpoint(session)
        checkpoint = state.resume_path(state.selected).read_bytes()
        first = self.root / 'first.exp'
        first.write_bytes(archive({1: metadata('Second'), 25001: program(0x33).to_bytes()}))
        second = self.root / 'bad.exp'
        second.write_bytes(b'not an EXP')
        before = (self.directory / 'library.json').read_bytes()
        with self.assertRaises(ContentError):
            self.library.add_episodes([first, second])
        self.assertEqual((self.directory / 'library.json').read_bytes(), before)
        self.assertFalse(list((self.directory / 'content').glob('*.exp')))
        self.assertEqual(self.library.add_episodes([first]), 1)
        self.assertEqual(self.library.add_episodes([first]), 0)
        self.assertEqual(state.resume_path(state.selected).read_bytes(), checkpoint)
        self.assertEqual(self.library.read_asset(42), b'base image')
        with ContentLibrary(self.directory) as reopened:
            self.assertEqual(reopened.open_episode('Second').archive.metadata().title, 'Second')

    def test_checkpoints_preserve_manual_saves_and_resume_survives_reopen(self):
        state = MenuState(self.library)
        session = state.session(state.selected)
        session.advance()
        manual = session.save()
        before = manual.read_bytes()
        session.engine.music_id = 8201
        state.music = False
        state.checkpoint(session)
        automatic = state.save_path(state.selected, automatic=True)
        os.utime(manual, ns=(1, 1))
        self.assertEqual(manual.read_bytes(), before)
        restored = MenuState(self.library)
        self.assertFalse(restored.music)
        self.assertEqual(restored.resume_path(restored.selected), automatic)
        self.assertEqual(restored.session(restored.selected).snapshot(), session.snapshot())
        fresh = restored.session(restored.selected, resume=False)
        self.assertIsNone(fresh.pending)
        self.assertNotEqual(fresh.engine.music_id, session.engine.music_id)

    def test_corrupt_resume_is_reported_without_resetting_progress(self):
        state = MenuState(self.library)
        path = state.save_path(state.selected, automatic=True)
        path.parent.mkdir()
        path.write_text('{ broken')
        with self.assertRaises(SaveError):
            state.session(state.selected)
        self.assertEqual(path.read_text(), '{ broken')
        with self.assertRaises(ContentError):
            state.save_path('../../outside')


@unittest.skipUnless(importlib.util.find_spec('pygame'), 'desktop extra is not installed')
class ApplicationTests(unittest.TestCase):
    def setUp(self):
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def make_app(self, library=False):
        from shs_runtime.application import Application
        path = self.root / 'library'
        if library:
            source = Path('.shs-library').resolve()
            path.mkdir()
            (path / 'content').mkdir()
            (path / 'library.json').write_bytes((source / 'library.json').read_bytes())
            # Share immutable input bytes, never the user's save directory.
            for item in (source / 'content').iterdir():
                (path / 'content' / item.name).symlink_to(item)
        app = Application(path, audio=False)
        self.addCleanup(app.close)
        return app

    def test_first_launch_needs_no_assets_and_drop_events_form_one_batch(self):
        import pygame
        app = self.make_app()
        app.render()
        self.assertEqual(app.screen, 'setup')
        app.command(('browse', 'apk'))
        app.tick(200)
        app.render()
        self.assertEqual(app.screen, 'browser')
        with patch.object(app, 'import_paths') as importer:
            app.handle_event(pygame.event.Event(pygame.DROPBEGIN))
            app.handle_event(pygame.event.Event(pygame.DROPFILE, file='/tmp/game.apk'))
            app.tick(16)
            importer.assert_not_called()
            app.handle_event(pygame.event.Event(pygame.DROPFILE, file='/tmp/story.exp'))
            app.handle_event(pygame.event.Event(pygame.DROPCOMPLETE))
            importer.assert_called_once_with([Path('/tmp/game.apk'), Path('/tmp/story.exp')])

    @unittest.skipUnless(Path('.shs-library/library.json').is_file(), 'user content is unavailable')
    def test_main_menu_navigation_resizing_pause_and_live_resume(self):
        import pygame
        app = self.make_app(library=True)
        self.assertEqual(app.message, '')
        app.tick(2400)
        app.render()
        self.assertFalse(app.buttons)  # Entrance input gate.
        app.tick(600)
        app.window = pygame.display.set_mode((800, 600), pygame.RESIZABLE)
        app.render()
        self.assertEqual(len(app.buttons), 6)
        rect, command = app.buttons[0]
        point = (app.viewport.x + rect.centerx * app.viewport.width / 320,
                 app.viewport.y + rect.centery * app.viewport.height / 480)
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))
        self.assertEqual(app.screen, 'main')
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=point))
        self.assertEqual(app.screen, 'episodes')
        app.tick(200)
        app.render()
        app.command(('episode', app.library.select('The_New_Girl.exp')['id']))
        app.command(('start', True))
        app.render()
        self.assertIsNone(app.game.error)
        self.assertEqual(app.game.window.get_size(), (800, 600))
        before = app.game.session.snapshot()
        app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        app.tick(5000)
        self.assertEqual(app.game.session.snapshot(), before)
        app.game.command(('main_menu',))
        self.assertEqual(app.screen, 'main')
        app.tick(5000)
        self.assertEqual(app.game.session.snapshot(), before)
        automatic = app.state.resume_path(app.selected)
        self.assertTrue(automatic.is_file())
        app.command(('start', True))
        self.assertEqual(app.game.session.snapshot(), before)
        app.return_to_menu()
        for screen in ('options', 'help', 'library'):
            app.show(screen)
            app.tick(200)
            app.render()
        app.command(('toggle', 'sound'))
        self.assertFalse(MenuState(app.library).sound)
        app.browse('episodes')
        app.tick(200)
        app.render()

    @unittest.skipUnless(Path('.shs-library/library.json').is_file(), 'user content is unavailable')
    def test_long_episode_list_search_and_hit_testing(self):
        import pygame
        app = self.make_app(library=True)
        source = app.library.episodes[0]
        # Authored list entries suffice for scrolling; no story data are copied.
        app.library.episodes = [dict(source, id=f'{i:064x}', titles=[f'Episode {i:02}', '', '', '', '']) for i in range(30)]
        app.show('episodes')
        app.scope = 'all'
        app.command(('episode_groups',))
        app.tick(200)
        app.render()
        app.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=-20))
        app.render()
        rows = [command for _, command in app.buttons if command[0] == 'episode']
        self.assertEqual(rows[0], ('episode', f'{16:064x}'))
        app.command(('search',))
        app.handle_event(pygame.event.Event(pygame.TEXTINPUT, text='Episode 29'))
        app.render()
        rows = [command for _, command in app.buttons if command[0] == 'episode']
        self.assertEqual(rows, [('episode', f'{29:064x}')])

    @unittest.skipUnless(Path('.shs-library/library.json').is_file(), 'user content is unavailable')
    def test_added_episode_appears_in_play_before_and_after_restarting(self):
        from shs_runtime.application import Application
        app = self.make_app(library=True)
        episode = self.root / 'added.exp'
        episode.write_bytes(archive({1: metadata('An imported story'), 25001: program(0x33).to_bytes()}))
        self.assertEqual(app.library.add_episodes([episode]), 1)
        key = digest(episode.read_bytes())
        app.scope = 'play'
        self.assertIn(key, [e['id'] for e in app.visible_episodes()])
        self.assertNotIn(key, app.saved)  # A save is not required for visibility.
        reopened = Application(app.directory, audio=False)
        self.addCleanup(reopened.close)
        reopened.scope = 'play'
        self.assertIn(key, [e['id'] for e in reopened.visible_episodes()])
        self.assertNotIn(key, reopened.saved)

    @unittest.skipUnless(Path('.shs-library/library.json').is_file(), 'user content is unavailable')
    def test_episode_order_uses_numeric_pack_and_episode_ids(self):
        app = self.make_app(library=True)
        source = app.library.episodes[0]
        rows = [(2, 1, 'Z'), (1, 10, 'A'), (1, 2, 'B')]
        app.library.episodes = [dict(source, id=f'{i:064x}', pack_id=pack, episode_id=episode,
                                     titles=[title, '', '', '', '']) for i, (pack, episode, title) in enumerate(rows)]
        self.assertEqual([e['titles'][0] for e in app.visible_episodes()], ['B', 'A', 'Z'])
        app.command(('order',))
        self.assertEqual([e['titles'][0] for e in app.visible_episodes()], ['A', 'B', 'Z'])
        self.assertEqual(MenuState(app.library).order, 'title')


if __name__ == '__main__':
    unittest.main()
