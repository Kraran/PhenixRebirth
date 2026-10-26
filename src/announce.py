"""Colours and sizes of the on-screen announcements (one table for the whole game).

A colour means one thing everywhere:

    gain        1UP, points, a caught item             cyan
    success     mission / level won                    bright green
    reward      achievement, new record, new mission   pink
    info        level, mission name, counters          blue
    danger      failure, death, broken dome, pad lost  bright red
    special     cheat codes and their banners          orange
    neutral     system messages, hints, details        grey

and an announcement has one of three sizes, whatever its colour:

    major       64 px, a strong plate   GAME OVER, mission won, new record
    standard    32 px, a medium plate   1UP, achievements, codes
    discreet    28 px, a light plate    pad unplugged, screenshot

The HUD of the ships (score, gauge, name) is NOT part of this table: its colours tell the hull and the player
apart, so they stay as they are (see Game._palette_score_color and hud_gauge). The colours below are kept far
from them (tests/test_announce.py measures it).
"""
import pygame

from settings import BASE_WIDTH

GAIN = (25, 255, 236)
SUCCESS = (70, 255, 0)
REWARD = (255, 25, 148)
INFO = (90, 120, 255)
DANGER = (255, 20, 10)
SPECIAL = (255, 132, 0)
NEUTRAL = (140, 145, 170)

COLORS = {
    "gain": GAIN,
    "success": SUCCESS,
    "reward": REWARD,
    "info": INFO,
    "danger": DANGER,
    "special": SPECIAL,
    "neutral": NEUTRAL,
}

# font: name of the Game font; plate: opacity of the dark plate (0-255); pad: margins around the text;
# border: width of the thin frame in the colour of the announcement.
LEVELS = {
    "major": {"font": "big_font", "plate": 165, "pad": (32, 18), "border": 2},
    "standard": {"font": "medium_font", "plate": 125, "pad": (24, 12), "border": 2},
    "discreet": {"font": "font", "plate": 90, "pad": (16, 8), "border": 1},
}
FONT_ORDER = ("big_font", "medium_font", "font", "menu_font")      # what an announcement that is too wide steps down to
MAX_WIDTH = BASE_WIDTH - 80

# The banner kinds of the game (Game.cheat_kind) -> (colour type, level).
KIND_STYLE = {
    "1up": ("gain", "standard"),
    "ach": ("reward", "standard"),
    "live": ("special", "standard"),
    "phen": ("special", "standard"),
    "stage": ("special", "standard"),
    "vn": ("special", "standard"),
    "pad": ("danger", "discreet"),
    "system": ("neutral", "discreet"),
}
DEFAULT_STYLE = ("neutral", "discreet")

# Story toasts (StoryHub.toast_kind) -> colour type; the results of a mission are standard, the rest discreet.
TOAST_COLOR = {
    "success": "success",
    "danger": "danger",
    "reward": "reward",
    "gain": "gain",
    "special": "special",
    "info": "info",
}
TOAST_LEVEL = {"success": "standard", "danger": "standard"}

_plates = {}


def style_of(kind):
    """(colour type, level) of a banner kind."""
    return KIND_STYLE.get(str(kind or ""), DEFAULT_STYLE)


def color_of(ctype):
    return COLORS.get(ctype, NEUTRAL)


def mix(a, b, k):
    """Colour a -> b by k (0..1)."""
    return tuple(int(round(x + (y - x) * k)) for x, y in zip(a, b))


def shade(color, k):
    """The colour at brightness k (1 = itself)."""
    return tuple(max(0, min(255, int(round(c * k)))) for c in color)


def fit_font(game, level, text, max_width=MAX_WIDTH, pad_x=0):
    """The font of the level, stepping down while the text (and its margins) is wider than the screen allows."""
    name = LEVELS[level]["font"]
    start = FONT_ORDER.index(name) if name in FONT_ORDER else 0
    font = getattr(game, name, None) or game.font
    for fname in FONT_ORDER[start:]:
        font = getattr(game, fname, None) or font
        if font.size(str(text))[0] + 2 * pad_x <= max_width:
            break
    return font


def plate(width, height, level, color):
    """The dark plate behind an announcement (kept from one frame to the next)."""
    spec = LEVELS[level]
    key = (int(width), int(height), level, tuple(color))
    surf = _plates.get(key)
    if surf is None:
        surf = pygame.Surface((key[0], key[1]), pygame.SRCALPHA)
        rect = surf.get_rect()
        pygame.draw.rect(surf, (0, 0, 0, spec["plate"]), rect, border_radius=8)
        if spec["border"]:
            pygame.draw.rect(surf, tuple(color) + (110,), rect, spec["border"], border_radius=8)
        if len(_plates) >= 48:
            _plates.clear()
        _plates[key] = surf
    return surf


def draw(game, surface, text, ctype, level, center, color=None, glow=0.0, show_plate=True, alpha=255):
    """One announcement: the plate, then the text, centred on `center`. `color` overrides the colour of the text
    (a pulse or a blink of the colour of the type); `glow` (0..1) adds the soft halo of the banners."""
    alpha = max(0, min(255, round(alpha * 0.92)))
    base = color_of(ctype)
    col = color if color is not None else base
    pad_x, pad_y = LEVELS[level]["pad"]
    font = fit_font(game, level, text, pad_x=pad_x)
    img = game._txt(font, text, col)
    cx, cy = center
    if show_plate:
        p = plate(img.get_width() + pad_x * 2, img.get_height() + pad_y * 2, level, base)
        if alpha < 255:                          # a fade: the plate fades with the text
            p = p.copy()
            p.set_alpha(int(alpha))
        surface.blit(p, (cx - p.get_width() // 2, cy - p.get_height() // 2))
    if glow > 0:
        halo = img.copy()                        # the cached picture is shared: its opacity is never touched
        halo.set_alpha(int((50 + 60 * glow) * alpha / 255))
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1)):
            surface.blit(halo, (cx - img.get_width() // 2 + ox, cy - img.get_height() // 2 + oy))
    if alpha < 255:
        img = img.copy()
        img.set_alpha(int(alpha))
    else:
        img.set_alpha(255)
    surface.blit(img, (cx - img.get_width() // 2, cy - img.get_height() // 2))
    return img
