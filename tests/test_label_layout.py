"""Label placement regressions using authored fonts and layout rectangles."""
import copy
from dataclasses import replace
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

from shs_runtime.dialogue import DialogueLayout
from shs_runtime.fonts import BitmapFont, Glyph, TextStyle, layout_label
from shs_runtime.runtime import SaveError, Session
from shs_runtime.scene_badge import SceneBadge
from shs_runtime.speaker_names import NameFontState, SpeakerNames, speaker_label
from shs_runtime.ui_assets import Rect
from test_runtime import Resources, answer_screen, host_call, text_words
from test_vm import program


def authored_font(line_height=16, ink_height=12, yoffset=2):
    glyphs = {code: Glyph(code, 0, 0, 8, ink_height, 0, yoffset, 5 if code == 32 else 9)
              for code in range(32, 127)}
    return BitmapFont('Authored label font', 16, line_height, 'unused.png', glyphs, {})


def authored_dialogue():
    # A compact layout bank, constructed without copying an APK resource.
    rects = {0x4c: Rect(8, 265, 190, 31), 0x43: Rect(8, 233, 190, 63),
             0x4e: Rect(196, 225, 128, 128), 8: Rect(40, 304, 240, 98),
             0x2e: Rect(122, 265, 190, 31), 0x25: Rect(122, 233, 190, 63),
             0x30: Rect(-6, 225, 128, 128),
             0x6a: Rect(18, 265, 284, 31), 0x61: Rect(18, 233, 284, 63)}
    layout = DialogueLayout.__new__(DialogueLayout)
    layout.bank = SimpleNamespace(rectangle=lambda bank, node: rects[node])
    name_font, body_font = authored_font(33, 30, 0), authored_font()
    layout.font = lambda name: name_font if name.startswith('PajamaHip') else body_font
    return layout


class SpeakerPlacementTests(unittest.TestCase):
    def assert_name_fits(self, page):
        if not page.name.glyphs:
            return
        x, y = page.name_origin
        left, top, right, bottom = page.name.ink_bounds
        scale = page.name_scale
        body_top = page.body_origin[1] + page.body.ink_bounds[1]
        self.assertLessEqual(y + scale * bottom, body_top + 1e-6)
        self.assertGreaterEqual(x + scale * left, -1e-6)
        self.assertLessEqual(x + scale * right, 320 + 1e-6)
        if page.portrait:
            if page.portrait.x < 0:
                self.assertGreaterEqual(x + scale * left, page.portrait.x + page.portrait.width - 1e-6)
            else:
                self.assertLessEqual(x + scale * right, page.portrait.x + 1e-6)
        previous_bottom = None
        for line in page.name.lines:
            row = [g for g in page.name.glyphs if line.start <= g.index < line.end]
            if row:
                if previous_bottom is not None:
                    self.assertGreaterEqual(min(g.y for g in row), previous_bottom)
                previous_bottom = max(g.y + g.glyph.height for g in row)

    def test_native_named_branches_and_retained_size_are_distinct_from_generic_fit(self):
        layout = authored_dialogue()
        for text, width, height, scale in (("Howard's Mom", 235, 63, .9),
                                           ("Howard's Dad", 223, 63, .9),
                                           ('French Teacher', 225, 81, .8),
                                           ("Neighbor's Wife", 270, 91, .8)):
            with self.subTest(text=text):
                result = speaker_label(text, 2, 1, layout.bank, layout.font, {})
                self.assertEqual(result.content_size, (width, height))
                self.assertEqual((result.flags, result.scale), (0x3d, scale))
                self.assertEqual(result.text, text)
        states = {'PajamaHip26': NameFontState(width=242, height=77)}
        result = speaker_label('Brendizzle', 1, 1, layout.bank, layout.font, states)
        self.assertEqual((result.content_size, result.scale), ((242, 77), .9))

    def test_native_spacing_rewrites_and_previous_line_count(self):
        layout = authored_dialogue()
        for mode, text, expected in ((2, 'The Boss', 'Th e Boss '),
                                     (2, 'The Mayor', 'Th e Mayor'),
                                     (2, 'Judge Tigh', 'Judge Ti gh'),
                                     (2, 'Animal Thief', 'Animal Th ief'),
                                     (3, 'The team', 'Th e team'),
                                     (3, 'The Whole Room', 'Th e Whole Room'),
                                     (3, 'The Crowd', 'Th e Crowd')):
            with self.subTest(text=text):
                self.assertEqual(speaker_label(text, mode, 1, layout.bank, layout.font, {}).text, expected)
        states = {'PajamaHip26': NameFontState(lines=2)}
        result = speaker_label('Spud The Stud', 2, 1, layout.bank, layout.font, states)
        self.assertEqual((result.text, result.scale, result.content_size),
                         ('Spud Th e Stud', .7, (270, 61)))
        states = {'PajamaHip26': NameFontState(lines=2)}
        result = speaker_label('A very long speaker name', 2, 1, layout.bank, layout.font, states)
        self.assertEqual((result.content_size, result.scale), ((300, 95), .7))
        self.assertEqual(states['PajamaHip26'].gap, 8)

    def test_all_modes_fit_long_and_multiline_names_after_spacing_changes(self):
        layout, names = authored_dialogue(), SpeakerNames()
        labels = ('A very long speaker name', 'Mr. Fernley', 'Miss Harper', 'Mrs. West',
                  'Alex', 'A\nSecond\nThird', 'W' * 60, "Howard's Mom", "Howard's Dad")
        for mode in (2, 1, 3):
            for theme in (1, 2, 3, -1):
                for speaker in labels:
                    with self.subTest(mode=mode, theme=theme, speaker=speaker):
                        details = dict(presentation_mode=mode, theme=theme, emphasis_theme=1,
                                       speaker=speaker, text='Please read the question.')
                        layout.prepare_name(details, names)
                        before = copy.deepcopy(names)
                        page = layout.page(details, names=names)
                        self.assert_name_fits(page)
                        self.assertEqual(layout.page(details, names=names), page)
                        self.assertEqual(names, before)

    def test_eleven_byte_names_clear_the_body_without_moving_or_repaginating_it(self):
        layout = authored_dialogue()
        details = dict(presentation_mode=2, theme=1, emphasis_theme=1,
                       speaker='Ms. Vale', text='Read the question. ' * 30)
        short = layout.page(details)
        for speaker in ('Mr. Fernley', 'Miss Harper'):
            with self.subTest(speaker=speaker):
                details['speaker'] = speaker
                original = copy.deepcopy(details)
                page = layout.page(details)
                name_bottom = page.name_origin[1] + page.name_scale * page.name.ink_bounds[3]
                body_top = page.body_origin[1] + page.body.ink_bounds[1]
                self.assertLessEqual(name_bottom, body_top)
                self.assertLess(body_top - name_bottom, 5)
                self.assertEqual((page.box, page.body, page.body_origin, page.portrait, page.end),
                                 (short.box, short.body, short.body_origin, short.portrait, short.end))
                self.assertEqual(details, original)

    def test_name_placement_preserves_pending_vm_and_saved_page(self):
        words, (ref,) = text_words('Read the question. ' * 30)
        resources = Resources(program(*host_call(13, ref, 1), 0x33, words=words))
        resources.dialogue_layout = lambda: authored_dialogue()
        session = Session(resources)
        session.engine.character_names[1] = 'Mr. Fernley'
        session.engine.character_art_variants[1] = [100] * 5
        session.advance()
        session.tick(1000)
        original = session.snapshot()
        page = session.dialogue_page()
        self.assertEqual(session.snapshot(), original)
        restored = Session.from_snapshot(resources, original)
        self.assertEqual(restored.snapshot(), original)
        self.assertEqual(restored.dialogue_page(), page)
        answer_screen(restored)
        self.assertEqual(restored.pending.details['page_start'], page.end)
        self.assertEqual(restored.vm.snapshot(), session.vm.snapshot())
        self.assertEqual(restored.dialogue_page().name_origin, page.name_origin)

    def test_font_history_survives_save_and_old_saves_reflow_without_vm_replay(self):
        words, (ref,) = text_words('Read the question. ' * 30)
        resources = Resources(program(*host_call(13, ref, 1), *host_call(13, ref, 2),
                                      0x33, words=words))
        resources.dialogue_layout = lambda: authored_dialogue()
        session = Session(resources)
        session.engine.character_names = {1: 'A very long speaker name', 2: 'Mr. Fernley'}
        session.engine.character_art_variants = {1: [100] * 5, 2: [200] * 5}
        session.advance()
        self.assertEqual(session.engine.speaker_names.fonts['PajamaHip26'].gap, 8)
        while session.pending.details['character_id'] == 1:
            answer_screen(session)
        self.assert_name_fits(session.dialogue_page())
        answer_screen(session)
        self.assertGreater(session.pending.details['page_start'], 0)
        original = session.snapshot()
        restored = Session.from_snapshot(resources, original)
        self.assertEqual(restored.snapshot(), original)
        self.assertEqual(restored.dialogue_page(), session.dialogue_page())
        for bank, key, value in (('fonts', 'gap', 7), ('fonts', 'width', -1),
                                 ('basis', 'lines', -1), ('fonts', 'indents', [200]),
                                 ('fonts', 'lines', 15)):
            bad = copy.deepcopy(original)
            bad['engine']['speaker_names'][bank]['PajamaHip26'][key] = value
            with self.subTest(bank=bank, key=key), self.assertRaises(SaveError):
                Session.from_snapshot(resources, bad)
        bad = copy.deepcopy(original)
        bad['engine']['speaker_names']['basis'] = None
        with self.assertRaises(SaveError):
            Session.from_snapshot(resources, bad)
        old = copy.deepcopy(original)
        old['version'] = 9
        del old['engine']['speaker_names']
        untouched = copy.deepcopy(old)
        restored = Session.from_snapshot(resources, old)
        self.assertEqual(old, untouched)
        self.assertEqual(restored.vm.snapshot(), session.vm.snapshot())
        self.assertEqual(restored.pending.details['page_start'],
                         original['pending']['details']['page_start'])
        self.assertEqual(restored.engine.numbers, session.engine.numbers)
        self.assertEqual(restored.engine.random48, session.engine.random48)

    def test_name_clears_taller_body_glyphs_on_later_pages_without_moving(self):
        words, (ref,) = text_words('Read the question.\n' * 15 + 'QQQQ\n')
        resources = Resources(program(*host_call(13, ref, 1), 0x33, words=words))
        layout, body_font = authored_dialogue(), authored_font()
        body_font.glyphs[ord('Q')] = replace(body_font.glyphs[ord('Q')], yoffset=-5)
        native_font = layout.font
        layout.font = lambda name: native_font(name) if name.startswith('PajamaHip') else body_font
        resources.dialogue_layout = lambda: layout
        session = Session(resources)
        session.engine.character_names[1] = 'Mr. Fernley'
        session.engine.character_art_variants[1] = [100] * 5
        session.engine.speaker_names.fonts['PajamaHip26'] = NameFontState(gap=8)
        session.advance()
        origin = session.dialogue_page().name_origin
        pages = 0
        while session.pending.name == 'dialogue':
            page = session.dialogue_page()
            self.assert_name_fits(page)
            self.assertEqual(page.name_origin, origin)
            pages += 1
            answer_screen(session)
        self.assertGreater(pages, 1)

    @unittest.skipUnless(Path('.shs-library/library.json').is_file(), 'user library is not present')
    def test_original_roster_and_parent_teacher_sequence_clear_dialogue_and_portraits(self):
        from shs_runtime.content import ContentError, ContentLibrary

        with ContentLibrary(Path('.shs-library')) as library:
            try:
                library.select('Football Star')
            except ContentError:
                self.skipTest('Football Star is not in the local library')
            resources = library.open_episode('Football Star')
            session = Session(resources)
            session.advance()  # Original initialization supplies the character metadata.
            layout = resources.dialogue_layout()
            names = SpeakerNames()
            characters = [26, 27, 17, 19, 16, 18, 20, *session.engine.character_names]
            for character in characters:
                details = session.engine.present_dialogue(character, 0, 'Read the question.', 0)
                if details['presentation_mode'] not in (1, 2):
                    continue
                with self.subTest(speaker=details['speaker']):
                    layout.prepare_name(details, names)
                    page = layout.page(details, names=names)
                    self.assert_name_fits(page)


class NativeLabelTests(unittest.TestCase):
    def test_alignment_indents_and_height_limit_use_line_boxes_before_glyph_ink(self):
        font = authored_font()
        style = TextStyle(16, 8, indents=(0, 5))
        left = layout_label(font, 'AA\nAA', 40, 80, style, 0x11)
        center = layout_label(font, 'AA\nAA', 40, 80, style, 0x1a)
        bottom = layout_label(font, 'AA\nAA', 40, 80, style, 0x3d)
        self.assertEqual([(l.x, l.y) for l in left.lines], [(0, 0), (5, 24)])
        self.assertEqual([(l.x, l.y) for l in center.lines], [(11, -20), (13.5, 4)])
        self.assertEqual([(l.x, l.y) for l in bottom.lines], [(0, -36), (5, -12)])
        clipped = layout_label(font, 'AA\nAA\nAA', 40, 36, style, 0x35)
        self.assertEqual([g.index for g in clipped.glyphs], [0, 1])
        self.assertEqual(len(clipped.lines), 1)


@unittest.skipUnless(importlib.util.find_spec('pygame'), 'desktop extra is not installed')
class BadgeDrawingTests(unittest.TestCase):
    def test_badge_text_is_inside_the_frame_and_left_aligned_on_every_line(self):
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        import pygame
        from shs_runtime.desktop import Desktop
        from shs_runtime.desktop_text import BitmapTextRenderer

        pygame.display.init()
        pygame.display.set_mode((480, 720))
        self.addCleanup(pygame.quit)
        atlas = pygame.Surface((8, 12), pygame.SRCALPHA)
        atlas.fill((255, 255, 255, 255))
        ui = Desktop.__new__(Desktop)
        ui.story_text = BitmapTextRenderer(None)
        ui.story_text.fonts['ArialRoundedMTBold16'] = (authored_font(), atlas)
        frame = pygame.Surface((171, 60), pygame.SRCALPHA)  # Only text contributes pixels.
        ui.dialogue_renderer = SimpleNamespace(frame=lambda *args: frame)
        ui._image = lambda asset: None
        ui.canvas = pygame.Surface((480, 720), pygame.SRCALPHA)
        for label, line_count in (('Evening', 1), ('Authored Office', 2),
                                  ('Unsupervised Study', 2), ('Before School', 2)):
            with self.subTest(label=label):
                ui.canvas.fill((0, 0, 0, 0))
                badge = SceneBadge(1, label, False, 200)
                original = copy.deepcopy(badge)
                ui._draw_scene_badge(badge)
                glyphs = pygame.mask.from_surface(ui.canvas).get_bounding_rects()
                rows = sorted({rect.top for rect in glyphs})
                self.assertEqual(len(rows), line_count)
                lefts = [min(rect.left for rect in glyphs if rect.top == y) for y in rows]
                self.assertEqual(len(set(lefts)), 1)
                # Logical badge interior is y=10..50 and text sits after the icon.
                # At the desktop's 1.5 scale and top inset 15 these avoid both borders.
                self.assertGreaterEqual(min(rows), 30)
                self.assertLessEqual(max(rect.bottom for rect in glyphs), 90)
                self.assertTrue(all(115 <= x <= 135 for x in lefts))
                self.assertEqual(badge, original)
