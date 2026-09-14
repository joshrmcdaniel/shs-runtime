import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from shs_runtime.content import ContentError, ContentLibrary, ExpArchive, digest, import_game
from shs_runtime.episode_catalog import CatalogEntry, EpisodeCatalog, read_options_catalog
from shs_runtime.menu import group_episodes
from test_content import FAKE_NATIVE, archive, make_apk, metadata
from test_vm import program


def text(value):
    data = value.encode('utf-8') if isinstance(value, str) else value
    return struct.pack('>H', len(data)) + data


def entry(pack, episode, title, category, filename, translated=None):
    titles = [title, translated or title, title, title, title]
    return (struct.pack('>BHH', 1, pack, episode)
            + b''.join(text(s) for s in [*titles, *([category] * 5), filename]) + struct.pack('>i', -1))


def options(entries, *, prefix=32, version=18):
    header = b'SHS_OPTIONS\0' + struct.pack('>ii', version, 0) + bytes(prefix - 20)
    # Current episode is absent. Native runtime strings are deliberately
    # present to check that only catalog metadata reaches the new library.
    return (header + b'\0' + struct.pack('>i', len(entries)) + b''.join(entries)
            + struct.pack('>h', 1) + text('$PLAYER') + text('Private player name')
            + bytes([1] * (version - 16)))


def record(identity, pack, episode, title, name='story.exp'):
    return dict(id=f'{identity:064x}', pack_id=pack, episode_id=episode,
                titles=[title] * 5, name=name)


class CatalogTests(unittest.TestCase):
    def test_reads_native_sections_from_both_validated_prefixes(self):
        entries = [entry(301, 57, 'First', 'Season Three', 'one.exp', b'Caf\xe9'),
                   entry(301, 58, 'Second', 'Season Four', 'two.exp')]
        for prefix in (32, 36):
            for version in (16, 17, 18):
                with self.subTest(prefix=prefix, version=version):
                    catalog = read_options_catalog(options(entries, prefix=prefix, version=version))
                    self.assertEqual([e.category for e in catalog.entries], ['Season Three', 'Season Four'])
                    self.assertEqual(catalog.category(record(1, 301, 58, 'Second', 'renamed.exp')), 'Season Four')
                    serialized = catalog.to_data()
                    self.assertNotIn('Private player name', json.dumps(serialized))
                    self.assertEqual(EpisodeCatalog.from_data(serialized).entries, catalog.entries)

    def test_invalid_catalog_does_not_accept_partial_records_or_scan_for_magic(self):
        good = options([entry(1, 2, 'Story', 'Chapter Set', 'story.exp')])
        bad_count = bytearray(good)
        struct.pack_into('>i', bad_count, 33, 1000000)
        invalid_string = bytearray(good)
        struct.pack_into('>H', invalid_string, 42, 32768)
        corruptions = [good[:length] for length in (0, 12, 32, 37, len(good) - 1)]
        corruptions += [good + b'junk', b'prefix' + good, bytes(bad_count), bytes(invalid_string),
                        options([], version=19), good[:-1] + b'\x02']
        for data in corruptions:
            with self.subTest(size=len(data)), self.assertRaises(ContentError):
                read_options_catalog(data)
        for data in ({}, [dict(pack_id=True, episode_id=2, title='x', category='a', filename='x')], [None]):
            with self.assertRaises(ContentError):
                EpisodeCatalog.from_data(data)

    def test_filename_matches_native_alias_ids_and_conflicting_categories_stay_unknown(self):
        catalog = EpisodeCatalog([
            CatalogEntry(3737, 3737, 'Catalog Title', 'Novel Group', 'Assets/novel.exp'),
            CatalogEntry(1, 2, 'Shared Title', 'First Set', 'a.exp'),
            CatalogEntry(1, 2, 'Shared Title', 'Second Set', 'b.exp')])
        self.assertEqual(catalog.category(record(1, 7, 230, 'Embedded Title', 'NOVEL.EXP')), 'Novel Group')
        self.assertEqual(catalog.category(record(2, 1, 2, 'Shared Title', 'b.exp')), 'Second Set')
        self.assertIsNone(catalog.category(record(3, 1, 2, 'Shared Title', 'renamed.exp')))
        self.assertIsNone(catalog.category(record(4, 1, 3, 'Another Title')))

    def test_grouping_uses_catalog_and_keeps_saves_as_shortcuts(self):
        records = [record(1, 301, 57, 'Before'), record(2, 301, 58, 'After'),
                   record(3, 501, 1, 'Unknown')]
        catalog = EpisodeCatalog([CatalogEntry(301, 57, 'Before', 'Season Three', 'a.exp'),
                                  CatalogEntry(301, 58, 'After', 'Season Four', 'b.exp')])
        sections = group_episodes(records, catalog, mega_label='Included Stories', novel_label='Novel',
                                  saved_label='Saved Games', saved={records[1]['id']})
        self.assertEqual([s.title for s in sections], ['Saved Games', 'Season Three', 'Season Four', 'Pack 501'])
        self.assertEqual(sections[0].episodes, (records[1],))
        self.assertEqual(sections[2].episodes, (records[1],))
        self.assertEqual(sum(len(s.episodes) for s in sections[1:]), len(records))

    @unittest.skipUnless(Path('Episodes/shs_options.sav').is_file() and Path('.shs-library/library.json').is_file(),
                         'original user catalog is unavailable')
    def test_original_catalog_covers_local_corpus_and_crosses_pack_boundary(self):
        catalog = read_options_catalog(Path('Episodes/shs_options.sav').read_bytes())
        with ContentLibrary('.shs-library') as library:
            for episode in library.episodes:
                self.assertIsNotNone(catalog.category(episode), episode['name'])
            a = next(e for e in library.episodes if (e['pack_id'], e['episode_id']) == (301, 57))
            b = next(e for e in library.episodes if (e['pack_id'], e['episode_id']) == (301, 58))
            self.assertEqual(catalog.category(a), 'SEASON 3')
            self.assertEqual(catalog.category(b), 'SEASON 4')


class CatalogImportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        profile = patch('shs_runtime.content.NATIVE_SHA256', digest(FAKE_NATIVE))
        profile.start()
        self.addCleanup(profile.stop)
        self.episode = archive({1: metadata('Test Story'), 25001: program(0x33).to_bytes()})
        self.apk = self.root / 'input.apk'
        make_apk(self.apk, self.episode)
        self.folder = self.root / 'episodes'
        self.folder.mkdir()
        (self.folder / 'story.exp').write_bytes(self.episode)
        meta = ExpArchive(self.episode).metadata()
        self.options = options([entry(meta.pack_id, meta.episode_id, meta.title, 'Original Section', 'story.exp')])
        (self.folder / 'shs_options.sav').write_bytes(self.options)

    def test_folder_import_and_later_catalog_only_import_persist_without_affecting_identity(self):
        first, second = self.root / 'first', self.root / 'second'
        import_game(self.apk, [self.folder], first)
        import_game(self.apk, [], second)
        with ContentLibrary(second) as library:
            resources = library.open_episode('Test Story')
            identity = resources.identity
            self.assertEqual(library.add_episodes([self.folder / 'shs_options.sav']), 0)
            self.assertEqual(resources.identity, identity)
            manifest = (second / 'library.json').read_bytes()
            self.assertEqual(library.add_episodes([self.folder / 'story.exp']), 0)
            self.assertEqual((second / 'library.json').read_bytes(), manifest)
        for directory in (first, second):
            with ContentLibrary(directory) as reopened:
                self.assertEqual(reopened.catalog.category(reopened.episodes[0]), 'Original Section')
                self.assertNotIn('Private player name', (directory / 'library.json').read_text())
                self.assertFalse((directory / 'shs_options.sav').exists())
        self.assertEqual((self.folder / 'shs_options.sav').read_bytes(), self.options)

    def test_failed_batch_publishes_neither_catalog_nor_episode(self):
        directory = self.root / 'library'
        import_game(self.apk, [], directory)
        with ContentLibrary(directory) as library:
            before = (directory / 'library.json').read_bytes()
            bad = self.folder / 'bad.exp'
            bad.write_bytes(b'corrupt')
            with self.assertRaises(ContentError):
                library.add_episodes([self.folder])
            self.assertFalse(library.catalog.entries)
            self.assertEqual((directory / 'library.json').read_bytes(), before)
            bad.unlink()
            (self.folder / 'shs_options.sav').write_bytes(self.options[:-1])
            with self.assertRaises(ContentError):
                library.add_episodes([self.folder / 'story.exp'])
            self.assertEqual((directory / 'library.json').read_bytes(), before)


@unittest.skipUnless(importlib.util.find_spec('pygame') and Path('.shs-library/library.json').is_file(),
                     'desktop extra or user artwork is unavailable')
class CatalogBrowserTests(unittest.TestCase):
    def test_collapse_search_navigation_and_scrolled_hit_targets(self):
        import pygame
        from shs_runtime.application import Application
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        with tempfile.TemporaryDirectory() as directory:
            root, source = Path(directory), Path('.shs-library').resolve()
            (root / 'library.json').write_bytes((source / 'library.json').read_bytes())
            (root / 'content').symlink_to(source / 'content', target_is_directory=True)
            app = Application(root, audio=False)
            self.addCleanup(app.close)
            app.library.catalog = EpisodeCatalog()
            app.query = app.renderer.strings[82]  # APK-derived category, no options sidecar.
            self.assertIn(app.library.select('footballseason')['id'], [e['id'] for e in app.visible_episodes()])
            app.query = ''
            template = app.library.episodes[0]
            records = [dict(template, **record(i + 1, 301, i + 1, f'Story {i:02}', f'{i}.exp')) for i in range(20)]
            app.library.episodes = records
            app.library.catalog = EpisodeCatalog(CatalogEntry(301, i + 1, f'Story {i:02}',
                                                             'First Season' if i < 10 else 'Second Season',
                                                             f'{i}.exp') for i in range(20))
            app.show('episodes')
            app.scope = 'all'
            app.tick(200)
            app.render()
            headers = [(rect, cmd) for rect, cmd in app.buttons if cmd[0] == 'episode_group']
            self.assertEqual(len(headers), 2)
            self.assertFalse([cmd for _, cmd in app.buttons if cmd[0] == 'episode'])
            app.command(headers[1][1])
            app.render()
            self.assertEqual([cmd for _, cmd in app.buttons if cmd[0] == 'episode'][0], ('episode', records[10]['id']))
            app._scroll(140)
            app.render()
            row_rect, row_command = next((r, c) for r, c in app.buttons if c[0] == 'episode')
            self.assertGreaterEqual(row_rect.top, 150)
            scroll = app.scroll
            point = (app.viewport.x + row_rect.centerx * app.viewport.width / 320,
                     app.viewport.y + row_rect.centery * app.viewport.height / 480)
            for type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                app.handle_event(pygame.event.Event(type, button=1, pos=point))
            self.assertEqual(app.screen, 'episode')
            self.assertEqual(app.selected, row_command[1])
            app.back()
            self.assertEqual(app.scroll, scroll)
            self.assertIn('category:second season', app.expanded_groups)
            app.command(('search',))
            app.tick(200)
            app.handle_event(pygame.event.Event(pygame.TEXTINPUT, text='First Season'))
            app.render()
            self.assertEqual(len(app.visible_episodes()), 10)
            self.assertTrue([c for _, c in app.buttons if c[0] == 'episode'])
            self.assertNotIn('category:first season', app.expanded_groups)
            app.command(('clear_search',))
            self.assertEqual(len(app.visible_episodes()), 20)
            app.command(('episode_groups',))
            self.assertTrue({'category:first season', 'category:second season'} <= app.expanded_groups)
            app.command(('episode_groups',))
            self.assertFalse(app.episode_rows()[0][0][3])
            self.assertEqual(len(app.episode_rows()[0]), 2)


if __name__ == '__main__':
    unittest.main()
