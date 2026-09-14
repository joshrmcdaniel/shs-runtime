"""Football art and hit regions recovered from the service-94 panel."""
from functools import lru_cache
import math

import pygame

from .atlas import SpriteAtlas
from .football import PLAY_FRAMES, TARGET_CENTERS
from .fonts import TextStyle
from .ui_assets import Rect


class FootballRenderer:
    def __init__(self, resources, text, art):
        self.resources, self.text, self.art = resources, text, art
        self.canvas = pygame.Surface((320, 480)).convert(32)

    @lru_cache(maxsize=1)
    def atlas(self):
        return SpriteAtlas.parse(self.resources.read_asset(290))

    @lru_cache(maxsize=154)
    def frame(self, index):
        r = self.atlas().raster(index)
        return pygame.image.frombytes(r.pixels, (r.width, r.height), 'RGBA').convert_alpha()

    def sprite(self, index, x, y, scale=1):
        if scale <= 0:
            return
        for ref, dx, dy in self.atlas().literals(index):
            image = self.frame(ref)
            if scale != 1:
                image = pygame.transform.smoothscale(image, (max(1, round(image.get_width() * scale)),
                                                              max(1, round(image.get_height() * scale))))
            self.canvas.blit(image, (round(x + dx * scale), round(y + dy * scale)))

    def label(self, text, x, y, width=300, size=14, center=False):
        markers = (('`', (24, 92, 219)), (';', (255, 51, 0)))
        layout = self.text.layout('ArialRoundedMTBold16', text, width, TextStyle(size, 4, markers=markers))
        self.text.draw_layout(self.canvas, 'ArialRoundedMTBold16', layout,
                              x - layout.width / 2 if center else x, y)

    def number(self, text, x, y, *, base=128, scale=1, center=False):
        indices = [base + int(c) if c.isdigit() else base + 10 if c == '-' else 150 if c == ':' else 117
                   for c in str(text) if c != ' ']
        width = sum(self.frame(i).get_width() for i in indices) * scale
        if center:
            x -= width / 2
        for i in indices:
            self.sprite(i, x, y, scale)
            x += self.frame(i).get_width() * scale

    @staticmethod
    def hit(position):
        # 000bc2ec: inclusive fixed bounds, independent of target zoom.
        px, py = position
        return next((i for i, (x, y) in enumerate(TARGET_CENTERS)
                     if x - 35 <= px <= x + 35 and y - 53 <= py <= y + 17), None)

    def field(self, game):
        # 000b8410 / 000b82f4: scrolling turf and authored chalk composites.
        y = -game.position * 45
        x = (y * -.40613848) % 320
        y = -((-y) % 480)
        for dx, dy in ((0, 0), (-320, 0), (0, 480), (-320, 480)):
            self.sprite(86, x + dx, y + dy)
        frames = (-83, -65, -69, -73, -77, -79, -76, -72, -68, -64, -84)
        start = int(game.position) - 6
        for yard in range(start, start + 14):
            if 0 <= yard <= 100 and yard % 5 == 0:
                y = 240 + (yard - game.position) * 45
                self.sprite(frames[yard // 10] if yard % 10 == 0 else -80,
                            int(y * -.4354067), int(y - 56))

    def draw(self, target, session):
        g = session.engine.football
        self.canvas.fill((0, 0, 0))
        self.field(g)
        # Original header art, with its baked-in down/yard labels.
        self.sprite(30, 10, 13)
        self.sprite(153 if g.defense else 152, 19, 4)
        self.label('Defense' if g.defense else 'Offense', 19, 7, 150, 14)
        self.label(f'{g.down + 1 if g.down < 4 else 4}', 97, 26, 20, 11)
        self.number(100 - g.position if g.defense else g.position, 195, 29, center=True)
        self.label(f'{g.home} - {g.away}', 177, 18, 100, 12, center=True)
        if g.half == 3:
            self.sprite(151, 170, 38)
        else:
            seconds = math.ceil(g.remaining_ms / 1000)
            self.number(f'{seconds // 60}:{seconds % 60:02}', 177, 50, center=True)
        for t, (x, y) in zip(g.targets, TARGET_CENTERS):
            if not t.visible:
                continue
            self.sprite(PLAY_FRAMES[t.code], x, y, t.scale)
            if t.code in (1, 2, 6, 7, -1, -2, -3):
                yards = t.yards + (5 if t.code in (6, 7) and not g.defense else 0)
                self.number(yards, x, y + 2, base=107 if yards > 0 else 91,
                            scale=t.scale, center=True)
        if 20 <= g.phase <= 23 or g.phase == 25:
            coach = self.frame(g.field_variant)
            self.canvas.blit(coach, (320 - coach.get_width(), 457 - coach.get_height()))
            self.sprite(64, 7, 126)
            title = 'Sudden Death' if g.half == 3 else 'Defense' if g.defense else 'Offense'
            self.label(title, 25, 142, 275, 22)
            self.label(g.instruction, 25, 188, 270, 14)
            if g.phase_elapsed_ms > (3500 if g.first_help else 900):
                self.label('Touch to continue', 160, 292, 270, 12, center=True)
        elif g.phase == 0:
            count = min(3, math.ceil(g.phase_ms / 800))
            self.sprite(count + 1, 120, 200)
        elif g.message_phase != -1 or g.phase in (1, 7, 26):
            self.sprite(66, -24, 240)
            self.label(g.message if g.phase != 7 else 'Change possession', 160, 244, 300, 24, center=True)
        self.canvas.blit(self.art.frame(126, 47), (0, 431))
        self.canvas.blit(self.art.frame(126, 49), (0, 408))
        self.label('Touch a play to select it', 70, 450, 240, 12)
        target.blit(pygame.transform.smoothscale(self.canvas, target.get_size()), (0, 0))
        return [(pygame.Rect(0, 422, 60, 58), ('menu',))]
