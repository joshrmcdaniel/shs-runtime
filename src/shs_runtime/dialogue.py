"""Dialogue geometry and pagination in the original 320 by 480 coordinates."""
from dataclasses import dataclass, replace
from functools import lru_cache

from .fonts import BitmapFont, TextLayout, TextStyle, layout_text
from .ui_assets import LayoutBank, Rect


BODY_FONT = 'ArialRoundedMTBold16'
NARRATOR_FONT = 'TrebuchetMS_Italic16'
NAME_FONTS = {-1: 'PajamaHipY26', 2: 'PajamaHip266', 3: 'PajamaHipG26'}
BLUE = (41, 104, 221)


def dialogue_styles(theme: int, *, narrator: bool = False, emphasis_theme: int = 1):
    if narrator:
        body_font = NARRATOR_FONT
        body = TextStyle(10, 7, (223, 163, 52), (('`', (125, 67, 0)),))
    else:
        body_font = BODY_FONT
        color = {1: BLUE, 2: (180, 78, 78), 3: (108, 108, 108)}.get(theme, (223, 163, 52))
        emphasis = BLUE if emphasis_theme == 2 else (254, 53, 0)
        body = TextStyle(14, 7, color, (('`', emphasis), (';', (1, 76, 215))))
    return NAME_FONTS.get(theme, 'PajamaHip26'), TextStyle(16, -16), body_font, body


@dataclass(frozen=True)
class DialoguePage:
    box: Rect  # The stretchable center; borders extend outside this rectangle.
    body_origin: tuple[float, float]
    body_font: str
    body: TextLayout
    portrait: Rect | None
    name_font: str
    name: TextLayout
    name_origin: tuple[float, float]
    name_scale: float
    start: int
    end: int


class DialogueLayout:
    def __init__(self, resources):
        self.resources = resources
        self.bank = LayoutBank.parse(resources.read_asset(14))

    @lru_cache(maxsize=8)
    def font(self, name):
        return BitmapFont.parse(self.resources.library.read_ui_asset(f'fonts/{name}.fnt'))

    def _name(self, text, mode, font_name, style):
        font = self.font(font_name)
        rect = self.bank.rectangle(17, {1: 0x2e, 2: 0x4c, 3: 0x6a}[mode])
        measured = layout_text(font, text, rect.width, style)
        unwrapped = layout_text(font, text, 100000, style).width
        extra = 8
        if (unwrapped > rect.width if mode == 2 else measured.height > rect.height):
            rect = self.bank.rectangle(17, {1: 0x25, 2: 0x43, 3: 0x61}[mode])
            extra = 40
            if mode in (1, 2):
                rect = replace(rect, y=rect.y - 40)
        if mode == 1:
            rect = replace(rect, x=rect.x + 1)
        elif mode == 2:
            rect = replace(rect, x=rect.x + (1 if len(text) == 8 else 5))

        # FUN_000a8544: default name-object sizing and alignment. Named
        # character exceptions are listed in the spec as remaining work.
        scale, offset = .9, 0
        width, height = rect.width + 20, rect.height + 30
        align = 'right' if mode == 1 and extra == 8 else 'left'
        if mode == 1:
            offset = -23 if extra == 8 and unwrapped < 127 else 0
            if len(measured.lines) >= 2:
                width = rect.width + (80 if len(text) < 14 else 40)
                scale = .8
        elif mode == 2:
            offset = 23 if unwrapped < 127 else 0
            if extra == 40:
                style = replace(style, gap=8)
            if len(text) in (8, 11):
                width, height = rect.width, rect.height + (34 if len(text) == 8 else 82)
                align = 'center' if len(text) == 8 else 'left'
            elif len(measured.lines) >= 2:
                width, height, scale = rect.width + 80, rect.height + 30, .8
            else:
                height = rect.height + 32
        else:
            align = 'center'
            height = rect.height + (34 if len(text) == 8 else 20)
            if len(text) >= 16:
                width, height, scale = 580, rect.height + 30, .6

        laid_out = layout_text(font, text, width, style)
        offsets = {line.start: (width - line.width) * (.5 if align == 'center' else 1)
                   if align != 'left' else 0 for line in laid_out.lines}
        glyphs = tuple(replace(g, x=g.x + offsets[line.start]) for line in laid_out.lines
                       for g in laid_out.glyphs if line.start <= g.index < line.end)
        laid_out = replace(laid_out, glyphs=glyphs)
        # The native label anchor is (.5,.5), and its text draws downward
        # from local zero. Vertical center alignment adds positive local Y.
        px = rect.x + offset - 10 + (rect.width + 20) // 2
        py = 480 - height + 19 - rect.y + (rect.height + 20) // 2
        origin = (px - scale * width / 2,
                  480 - py + scale * laid_out.height / 2)
        return laid_out, origin, scale, extra

    def page(self, details, start=0):
        mode, theme = details['presentation_mode'], details['theme']
        name_font, name_style, body_font, body_style = dialogue_styles(
            theme, narrator=mode == 4, emphasis_theme=details['emphasis_theme'])
        font = self.font(body_font)
        text = details['text'][start:]
        sizing_text = details['text']  # Page turns keep the original box size.
        portrait = None
        if mode == 4:
            name = layout_text(self.font(name_font), '', 1, name_style)
            name_origin, name_scale = (0, 0), .9
            # FUN_000858cc configures state+0xd180 with registry font 5,
            # height 16 and gap 9. Narrator sizing and drawing deliberately
            # use different fonts. This measuring object has no color markers.
            measured = layout_text(self.font(BODY_FONT), sizing_text, 220, TextStyle(16, 9))
            width = max(120, (int(measured.width) + 2) // 2 * 2)
            height = (int(min(200, measured.height)) + 5) // 2 * 2
            box = Rect(25, 115, width + 10, height + 10)
            origin = (30, 120)
        else:
            name, name_origin, name_scale, extra = self._name(details['speaker'], mode, name_font, name_style)
            rect = self.bank.rectangle(17, 8)
            if mode in (1, 2):
                portrait = self.bank.rectangle(17, 0x30 if mode == 1 else 0x4e)
                body_style = replace(body_style, indents=(85, 75, 0, 0) if mode == 1 else (-85, -75, 0, 0))
            measured = layout_text(font, sizing_text, rect.width, body_style)
            capacity = int((rect.height + body_style.gap) / (body_style.height + body_style.gap))
            count = min(capacity, max(3, len(measured.lines)))
            height = int(count * (body_style.height + body_style.gap) - body_style.gap + 7) if count else 8
            height += height % 2
            box = Rect(rect.x - 7, rect.y - extra, rect.width + 14, height + extra)
            origin = (rect.x - 7, rect.y - extra // 2)
        full = layout_text(font, text, box.width, body_style)
        capacity = max(1, int((box.height + body_style.gap) / (body_style.height + body_style.gap)))
        end = full.lines[capacity].start if len(full.lines) > capacity else len(text)
        body = layout_text(font, text[:end], box.width, body_style)
        return DialoguePage(box, origin, body_font, body, portrait, name_font,
                            name, name_origin, name_scale, start, start + end)
