"""Service-96 artwork and pointer geometry, in native 320 × 480 units."""
from functools import lru_cache
import math

import pygame

from .atlas import AtlasFont, SpriteAtlas
from .fonts import TextStyle
from .ui_assets import Rect


class GridRenderer:
    def __init__(self, resources, text, art):
        self.resources, self.text, self.art = resources, text, art
        self.canvas = pygame.Surface((320, 480)).convert(32)
        self.cells = []

    @lru_cache(maxsize=12)
    def atlas(self, asset):
        return SpriteAtlas.parse(self.resources.read_asset(asset))

    @lru_cache(maxsize=96)
    def frame(self, asset, index):
        frame = self.atlas(asset).raster(index)
        return pygame.image.frombytes(frame.pixels, (frame.width, frame.height), 'RGBA').convert_alpha()

    @lru_cache(maxsize=4)
    def font(self, image, metrics):
        return AtlasFont.parse(self.resources.read_asset(metrics), self.atlas(image).image)

    @lru_cache(maxsize=256)
    def glyph(self, char):
        font = self.font(522, 523)
        glyph = font.glyph(char)
        if glyph is None:
            return None
        x, y, width = glyph
        return self.frame(522, 0).subsurface((x, y, width, font.height))

    def label(self, text, x, y, width=280, *, size=16, center=False, color=(255, 255, 255)):
        layout = self.text.layout('ArialRoundedMTBold16', text, width, TextStyle(size, 3, color))
        if center:
            x -= layout.width / 2
        self.text.draw_layout(self.canvas, 'ArialRoundedMTBold16', layout, x, y)
        return layout.height

    @staticmethod
    def project(width, height, x, y):
        # 000cc398 depth table; 000c7ef8 camera; 000c7f98 frustum.
        depth = -3800 if height == 5 else -3400 if (width, height) in ((5, 3), (4, 4), (5, 4)) else -3000
        x -= (width * 450 + (width - 1) * 72) / 2
        y = (height * 450 + (height - 1) * 72) / 2 + 480 - y
        z = depth - y * 0.5
        return 160 + 400 * x / -z, 240 - 400 * (y * math.cos(math.pi / 6) - 300) / -z

    def geometry(self, game):
        p = game.problem
        self.cells = []
        for row in range(p.height):
            for col in range(p.width):
                x, y = col * 522, row * 522
                quad = tuple(self.project(p.width, p.height, x + dx, y + dy)
                             for dx, dy in ((0, 0), (450, 0), (450, 450), (0, 450)))
                center = self.project(p.width, p.height, x + 225, y + 225)
                w = max(v[0] for v in quad) - min(v[0] for v in quad)
                h = quad[3][1] - quad[0][1]
                self.cells.append((quad, pygame.FRect(center[0] - w / 2, center[1] - h / 2, w, h)))

    def hit(self, position, game):
        self.geometry(game)
        # Native accepts a whole-cell hit at drag start, then a 65% inset.
        for col in range(game.problem.width):
            for row in range(game.problem.height):
                i = row * game.problem.width + col
                rect = self.cells[i][1].copy()
                if game.selection:
                    rect.inflate_ip(-rect.width * .35, -rect.height * .35)
                if rect.collidepoint(position):
                    return i
        return None

    def quad(self, image, points):
        """Scanline projection of the original sprite onto the board plane."""
        tl, tr, br, bl = points
        top, bottom = round(tl[1]), round(bl[1])
        height = max(1, bottom - top)
        source = pygame.transform.smoothscale(image, (image.get_width(), height))
        for y in range(height):
            t = (y + .5) / height
            left = tl[0] + (bl[0] - tl[0]) * t
            right = tr[0] + (br[0] - tr[0]) * t
            row = source.subsurface((0, y, source.get_width(), 1))
            self.canvas.blit(pygame.transform.smoothscale(row, (max(1, round(right - left)), 1)),
                             (round(left), top + y))

    def draw(self, target, session):
        game, details = session.engine.word_grid, session.pending.details
        self.geometry(game)
        self.canvas.fill((0, 0, 0))
        background = self.art.image(details['background_id'])
        if background is not None:
            self.canvas.blit(background, background.get_rect(center=(160, 240)))
        # Supplied character art remains in its episode namespace.
        for side, x in (('left', 15), ('right', 195)):
            variants = session.engine.character_art_variants.get(details[side + '_character'], ())
            if variants:
                portrait = self.art.image(variants[max(0, details[side + '_expression']) % len(variants)])
                if portrait is not None:
                    ratio = min(110 / portrait.get_width(), 135 / portrait.get_height())
                    image = pygame.transform.smoothscale(portrait, (round(portrait.get_width() * ratio),
                                                                    round(portrait.get_height() * ratio)))
                    self.canvas.blit(image, (x, 426 - image.get_height()))
        p = game.problem
        if not (game.tutorial and p.hide_board):
            for i, (quad, rect) in enumerate(self.cells):
                tile = self.frame(446, 33 if i in game.bad_prefix else 43 if i in game.selection
                                  else 41 if p.highlight and i in game.starts else 15).copy()
                glyph = self.frame(game.symbols[ord(game.board[i])], 0) if ord(game.board[i]) in game.symbols else self.glyph(game.board[i])
                if glyph is not None:
                    ratio = tile.get_height() * .85 / glyph.get_height()
                    image = pygame.transform.smoothscale(glyph, (max(1, round(glyph.get_width() * ratio)),
                                                                  max(1, round(glyph.get_height() * ratio))))
                    tile.blit(image, image.get_rect(center=tile.get_rect().center))
                self.quad(tile, quad)
            paths = [game.selection]
            if p.show_hints:
                for start in game.starts:
                    path = next((path for word in p.words if (path := game.find_path(start, word))), None)
                    if path:
                        paths.append(path)
            for path in paths:
                for a, b in zip(path, path[1:]):
                    start, end = self.cells[a][1].center, self.cells[b][1].center
                    angle = math.degrees(math.atan2(start[1] - end[1], end[0] - start[0]))
                    arrow = pygame.transform.rotozoom(self.frame(446, 5 if path is game.selection else 6), angle, .25)
                    self.canvas.blit(arrow, arrow.get_rect(center=((start[0]+end[0])/2, (start[1]+end[1])/2)))
        self.art.box(self.canvas, Rect(40, 41, 240, 62), 1, alpha=240)
        self.label(p.heading, 160, 36, 252, size=21, center=True, color=(1, 76, 215))
        self.label(p.prompt, 160, 78, 252, size=14, center=True, color=(1, 76, 215))
        self.label(f'{game.score} / {game.target}', 160, 366, center=True)
        if game.delta_ms:
            self.label(f'+{game.last_delta}', 260, 352, 60, color=(49, 213, 86))
        bar = pygame.Rect(81, 408, 158, 8)
        pygame.draw.rect(self.canvas, (15, 28, 60), bar, border_radius=4)
        pygame.draw.rect(self.canvas, (91, 182, 247), (bar.x, bar.y, round(bar.width * max(0, game.round_ms) / game.round_limit_ms), bar.height), border_radius=4)
        self.label(f'{math.ceil(game.remaining_ms / 1000)}', 160, 386, 80, center=True)
        overlay = None
        if game.phase == -1:
            overlay = 'Ready?'
        elif game.phase == 6:
            overlay = f'Score {game.target} points!'
        elif game.phase == 3:
            overlay = game.success_text if game.round_success else game.failure_text
        elif game.phase in (5, 7):
            overlay = f'{game.score} / {game.target}' if game.result_shown else "Time's up!"
        if overlay:
            self.art.box(self.canvas, Rect(40, 196, 240, 70), 1)
            self.label(overlay, 160, 215, 230, size=21, center=True, color=(1, 76, 215))
        if game.tutorial and p.tutorial_text and not game.tutorial_entry_ms:
            self.art.box(self.canvas, Rect(28, 327, 264, 89), 1)
            self.label(p.tutorial_title, 36, 329, 248, size=17, color=(1, 76, 215))
            self.label(p.tutorial_text, 36, 352, 248, size=12, color=(1, 76, 215))
        self.canvas.blit(self.art.frame(126, 47), (0, 431))
        self.canvas.blit(self.art.frame(126, 49), (0, 408))
        hint = 'Touch to continue' if game.tutorial and p.tap_to_advance else 'Slide your finger across the tiles'
        self.text.draw(self.canvas, 'ArialMT11', hint, 65, 450, 250, TextStyle(11, 0))
        target.blit(pygame.transform.smoothscale(self.canvas, target.get_size()), (0, 0))
        return [(pygame.Rect(0, 422, 60, 58), ('menu',))]
