"""Original choice-panel artwork; selection values remain in the session."""
import math

import pygame

from .choice import BODY_FONT, FOOTER_FONT, ChoiceLayout
from .fonts import TextStyle
from .ui_assets import Rect


class ChoiceRenderer:
    def __init__(self, resources, text_renderer, artwork):
        self.resources, self.text, self.art = resources, text_renderer, artwork
        self.layout = None
        self.canvas = pygame.Surface((320, 480)).convert(32)
        self.cached_key = self.cached_page = None
        self.viewport = pygame.Rect(0, 0, 320, 421)

    def page(self, session):
        details = session.pending.details
        game = session.engine.word_game
        key = id(session), session.scene, session.vm.steps_executed, game.round if game else None
        if game:
            details = dict(details, options=game.options, enabled=[True] * 4, minigame=True)
        if key != self.cached_key:
            if self.layout is None:
                self.layout = ChoiceLayout(self.resources)
            character = details['character_id']
            theme = session.engine.numbers.get(session.engine.number_key(character, 651), 0)
            variants = session.engine.character_art_variants.get(character, ())
            self.cached_page = self.layout.page(details, theme=theme,
                                               has_portrait=character >= 0 and bool(variants) and variants[0] > 0)
            self.cached_key = key
        return self.cached_page

    def draw(self, target, session, *, scroll=0, pointer=None):
        page = self.page(session)
        scroll = min(page.max_scroll, max(0, scroll))
        self.canvas.set_clip(None)
        self.canvas.fill((0, 0, 0))
        background = self.art.image(session.engine.panel.background_id)
        if background is not None:
            self.canvas.blit(background, (160 - background.get_width() // 2,
                                          (240 if session.engine.word_game else 180) - background.get_height() // 2))
        self.canvas.set_clip(self.viewport)
        box = page.box
        self.art.box(self.canvas, Rect(box.x + 10, box.y + 10 - scroll,
                                       box.width - 20, box.height - 20), page.theme, alpha=243)
        buttons = []
        for row in page.rows:
            rect = pygame.Rect(row.rect.x, row.rect.y - scroll, row.rect.width, row.rect.height)
            hit = rect.clip(self.viewport)
            if row.enabled and pointer is not None and hit.collidepoint(pointer):
                color = (250, 214, 211, 180) if page.theme == 2 else (170, 225, 249, 180)
                highlight = pygame.Surface(rect.size, pygame.SRCALPHA)
                highlight.fill(color)
                self.canvas.blit(highlight, rect)
            pygame.draw.line(self.canvas, (178, 179, 179), rect.topleft, (rect.right - 1, rect.top))
            game = session.engine.word_game
            offset = 0
            if game and game.animation_ms:
                offset = (game.animation_ms / 200) * (-210 if row.index % 2 == 0 else 410)
            self.canvas.set_clip(hit)
            self.text.draw_layout(self.canvas, BODY_FONT, row.text, row.origin[0] + offset, row.origin[1] - scroll)
            self.canvas.set_clip(self.viewport)
            if row.enabled and hit.height:
                buttons.append((hit, ('choose', row.index)))
        if page.rows:
            rect = page.rows[-1].rect
            y = rect.y + rect.height - scroll
            pygame.draw.line(self.canvas, (178, 179, 179), (rect.x, y), (rect.x + rect.width - 1, y))

        if page.portrait is not None:
            cx, cy = page.portrait.center
            cy -= scroll
            for index in (37, {1: 38, 2: 39}.get(page.theme, 40)):
                image = self.art.frame(126, index)
                self.canvas.blit(image, image.get_rect(center=(cx, cy)))
            details = session.pending.details
            asset = session.engine.character_art_variants[details['character_id']][0]
            # FUN_000ae5d4 requests expression zero, independently of dialogue.
            image = self.art.portrait(asset, details['portrait_mode'] == 2 and page.theme != 3)
            if image is not None:
                # FUN_0005afbc removes the final 12 rows after masking.
                height = image.get_height() - 12
                if height > 0:
                    image = image.subsurface((0, 0, image.get_width(), height))
                bottom = cy + self.art.frame(126, 39).get_height() // 2
                self.canvas.blit(image, (cx - image.get_width() // 2, bottom - image.get_height()))
        self.text.draw_layout(self.canvas, page.title_font, page.title,
                              page.title_origin[0], page.title_origin[1] - scroll)
        self.text.draw_layout(self.canvas, BODY_FONT, page.description,
                              page.description_origin[0], page.description_origin[1] - scroll)
        self.canvas.set_clip(None)
        game = session.engine.word_game
        if game:
            pack = {1: 204, 2: 220, 3: 252}.get(page.theme, 236)
            self.canvas.blit(self.art.frame(pack, 9), (130, 353))
            self.canvas.blit(self.art.frame(pack, 10), (182, 375))
            self.canvas.blit(pygame.transform.scale(self.art.frame(pack, 11), (12, 39)), (221, 375))
            self.canvas.blit(self.art.frame(pack, 12), (233, 375))
            self.canvas.blit(self.art.frame(708, 0), (130, 353))
            timer = self.art.frame(709, 0).copy()
            fraction = 1 - max(0, game.remaining_ms) / game.duration_ms
            if fraction > 0:
                mask = pygame.Surface(timer.get_size(), pygame.SRCALPHA)
                cx, cy = timer.get_width() / 2, timer.get_height() / 2
                points = [(cx, cy)] + [(cx + 90 * math.sin(t), cy - 90 * math.cos(t))
                                      for t in (fraction * 2 * math.pi * i / 120 for i in range(121))]
                pygame.draw.polygon(mask, (255, 255, 255, 255), points)
                timer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                self.canvas.blit(timer, (130, 353))
            # Native score text is at (230,88) in GL coordinates (top y=392).
            score = self.text.layout(BODY_FONT, str(game.score), 60, TextStyle(14, 0, (255, 255, 255)))
            self.text.draw_layout(self.canvas, BODY_FONT, score, 230 - score.width / 2, 392)
            if game.animation_ms and game.last_delta:
                color = (37, 147, 56) if game.last_delta > 0 else (255, 0, 0)
                delta = self.text.layout(BODY_FONT, f'{game.last_delta:+d}', 40, TextStyle(14, 0, color))
                self.text.draw_layout(self.canvas, BODY_FONT, delta, 275, 365 + game.animation_ms / 10)
        self.canvas.blit(self.art.frame(126, 47), (0, 431))
        self.canvas.blit(self.art.frame(126, 49), (0, 408))
        hint = 'Touch the best choice'
        if session.remaining_ms is not None:
            hint = f'{hint}  {math.ceil(session.remaining_ms / 1000)}s'
        style = TextStyle(11, 0, (185, 185, 185))
        footer = self.text.layout(FOOTER_FONT, hint, 246, style)
        self.text.draw_layout(self.canvas, FOOTER_FONT, footer, 63 + (252 - footer.width) / 2, 460)
        if page.max_scroll:
            # A desktop affordance for unusually long options; no choices are
            # discarded or mapped to a different script-visible index.
            track = pygame.Rect(310, 40, 3, 378)
            pygame.draw.rect(self.canvas, (100, 100, 100), track)
            thumb = max(20, int(track.height * 390 / (390 + page.max_scroll)))
            y = track.y + int((track.height - thumb) * scroll / page.max_scroll)
            pygame.draw.rect(self.canvas, (225, 225, 225), (track.x, y, track.width, thumb))
        buttons.append((pygame.Rect(0, 422, 60, 58), ('menu',)))
        target.blit(pygame.transform.smoothscale(self.canvas, target.get_size()), (0, 0))
        return page, buttons
