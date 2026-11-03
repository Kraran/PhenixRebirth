"""
The look of the menus of the Adventure: the station of Phobos (black riveted steel, copper and amber lamps).

Everything here is drawn once and kept by its size, so a menu costs a few blits per frame:

- `plate`: a steel plate (a dark gradient, a bevel, four rivets), with a hazard strip (yellow and black) on request;
- `lit`: the lit frame behind the chosen row (a warm fill and a gold edge, as before but squarer);
- `title`: the title of a screen in a copper cartouche, with a glow like a lamp;
- `badge`: a small steel plate with a line of text (the pilot, the hull);
- `holo`: a holographic card (blue glass with a grid and cut corners), lit in gold when it is the chosen one;
- `crt`: a CRT screen (dark green glass, scan lines, a steel bezel), for the terminals;
- `meter`: a row of small cells, some of them lit (a level);
- `tab`: a tab of the strip at the bottom;
- `band`: the steel band of the help bar;
- `backdrop`: the picture behind a pane (assets/story/ui_<name>.jpg, already darkened), or None.

The classic game keeps menu_ui.py (the rounded blue-grey panels): only the Adventure uses this module.
"""
import os

import pygame

from errlog import log_exc
from settings import BASE_HEIGHT, BASE_WIDTH, asset_path

STEEL_TOP = (36, 40, 49)
STEEL_BOTTOM = (20, 23, 29)
STEEL_EDGE = (58, 65, 77)
STEEL_LIGHT = (84, 93, 108)
STEEL_DARK = (11, 13, 17)
RIVET = (112, 120, 138)
COPPER = (184, 116, 44)
AMBER = (255, 179, 71)
GOLD = (255, 210, 90)
HAZARD = (232, 176, 44)
HAZARD_DARK = (21, 23, 28)
LIT_FILL = (62, 44, 16)
LIT_EDGE = (255, 210, 90)
TAB_TOP = (31, 35, 42)
TAB_BOTTOM = (18, 21, 26)

PLATE_ALPHA = 226                 # a steel plate is nearly solid: a little of the picture shows through, the rest shows around it
HAZARD_H = 8
CACHE_MAX = 160

_layers = {}


def _keep(key, img):
    if len(_layers) > CACHE_MAX:
        _layers.clear()
    _layers[key] = img
    return img


def _gradient(w, h, top, bottom, alpha):
    img = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
    for y in range(img.get_height()):
        f = y / max(1, img.get_height() - 1)
        c = tuple(int(top[i] * (1 - f) + bottom[i] * f) for i in range(3))
        img.fill(c + (alpha,), (0, y, img.get_width(), 1))
    return img


def _hazard_strip(w):
    """Yellow and black diagonal stripes, `HAZARD_H` px tall."""
    img = pygame.Surface((max(1, w), HAZARD_H))
    img.fill(HAZARD_DARK)
    step = 20
    for x in range(-HAZARD_H, w + HAZARD_H, step):
        pygame.draw.polygon(img, HAZARD, [(x, HAZARD_H), (x + 10, HAZARD_H), (x + 10 + HAZARD_H, 0), (x + HAZARD_H, 0)])
    return img


def _rivet(img, x, y):
    pygame.draw.circle(img, STEEL_DARK + (255,), (x, y + 1), 4)
    pygame.draw.circle(img, RIVET + (255,), (x, y), 3)
    pygame.draw.circle(img, (200, 208, 224, 255), (x - 1, y - 1), 1)


def plate(surface, rect, hazard=False, alpha=PLATE_ALPHA, rivets=True):
    """A steel plate. `hazard`: the yellow and black strip along its top edge."""
    r = pygame.Rect(rect)
    key = ("plate", r.w, r.h, bool(hazard), int(alpha), bool(rivets))
    img = _layers.get(key)
    if img is None:
        img = _gradient(r.w, r.h, STEEL_TOP, STEEL_BOTTOM, int(alpha))
        pygame.draw.rect(img, STEEL_EDGE + (255,), img.get_rect(), 2, border_radius=3)
        pygame.draw.line(img, STEEL_LIGHT + (255,), (3, 2), (r.w - 4, 2), 1)                 # the lit upper edge
        pygame.draw.rect(img, STEEL_DARK + (255,), img.get_rect().inflate(-8, -8), 1, border_radius=2)
        if rivets and r.w >= 40 and r.h >= 30:
            for x, y in ((11, 11), (r.w - 12, 11), (11, r.h - 12), (r.w - 12, r.h - 12)):
                _rivet(img, x, y)
        if hazard:
            img.blit(_hazard_strip(r.w - 4), (2, 2))
            pygame.draw.line(img, STEEL_DARK + (255,), (2, 2 + HAZARD_H), (r.w - 3, 2 + HAZARD_H), 1)
        _keep(key, img)
    surface.blit(img, r.topleft)
    return r


def lit(surface, rect):
    """The lit frame behind the chosen row: a warm fill, a gold edge, a thin dark line inside it."""
    r = pygame.Rect(rect)
    key = ("lit", r.w, r.h)
    img = _layers.get(key)
    if img is None:
        img = _gradient(r.w, r.h, (74, 52, 18), LIT_FILL, 225)
        pygame.draw.rect(img, LIT_EDGE + (255,), img.get_rect(), 2, border_radius=2)
        pygame.draw.rect(img, (96, 70, 24, 255), img.get_rect().inflate(-6, -6), 1)
        _keep(key, img)
    surface.blit(img, r.topleft)
    return r


DANGER_EDGE = (235, 84, 70)


def danger(surface, rect):
    """The lit frame of an answer that destroys something (YES of the delete question): the same plate, in red."""
    r = pygame.Rect(rect)
    key = ("danger", r.w, r.h)
    img = _layers.get(key)
    if img is None:
        img = _gradient(r.w, r.h, (86, 28, 24), (46, 14, 12), 235)
        pygame.draw.rect(img, DANGER_EDGE + (255,), img.get_rect(), 2, border_radius=2)
        pygame.draw.rect(img, (120, 40, 34, 255), img.get_rect().inflate(-6, -6), 1)
        _keep(key, img)
    surface.blit(img, r.topleft)
    return r


def _glow(text_img, colour, spread=5):
    """The text again, blurred and tinted: the light of a lamp behind the letters."""
    w, h = text_img.get_size()
    small = pygame.transform.smoothscale(text_img, (max(1, w // 4), max(1, h // 4)))
    big = pygame.transform.smoothscale(small, (w + spread * 2, h + spread * 2))
    tint = pygame.Surface(big.get_size(), pygame.SRCALPHA)
    tint.fill(colour + (255,))
    tint.blit(big, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return tint


def title(surface, font, text, centerx, top, colour=AMBER):
    """The title of a screen in a copper cartouche. Returns its rect."""
    key = ("title", id(font), text, tuple(colour))
    img = _layers.get(key)
    if img is None:
        txt = font.render(text, True, colour)
        pad_x, pad_y = 44, 3
        w, h = txt.get_width() + pad_x * 2, txt.get_height() + pad_y * 2
        img = pygame.Surface((w + 24, h + 24), pygame.SRCALPHA)
        halo = pygame.Surface((w + 24, h + 24), pygame.SRCALPHA)
        for i, a in enumerate((14, 18, 24)):
            pygame.draw.rect(halo, COPPER + (a,), pygame.Rect(12 - 8 + i * 3, 12 - 8 + i * 3, w + 16 - i * 6, h + 16 - i * 6),
                             border_radius=6)
        img.blit(halo, (0, 0))
        body = _gradient(w, h, (44, 30, 17), (22, 15, 9), 245)
        pygame.draw.rect(body, COPPER + (255,), body.get_rect(), 2, border_radius=3)
        pygame.draw.rect(body, (110, 70, 30, 255), body.get_rect().inflate(-8, -8), 1)
        img.blit(body, (12, 12))
        glow = _glow(txt, colour)
        glow.set_alpha(150)
        img.blit(glow, (12 + pad_x - 5, 12 + pad_y - 5))
        img.blit(txt, (12 + pad_x, 12 + pad_y))
        _keep(key, img)
    r = img.get_rect(midtop=(centerx, top - 12))
    surface.blit(img, r.topleft)
    return r.inflate(-24, -24)


def badge(surface, font, text, colour, cy, left=None, right=None, max_w=None):
    """A small steel plate with one line of text, `cy` the centre line, anchored on `left` or `right`."""
    key = ("badge", id(font), text, tuple(colour), max_w)
    img = _layers.get(key)
    if img is None:
        txt = font.render(text, True, colour)
        if max_w is not None and txt.get_width() > max_w - 40:
            k = (max_w - 40) / txt.get_width()
            txt = pygame.transform.smoothscale(txt, (max(1, int(txt.get_width() * k)), max(1, int(txt.get_height() * k))))
        w, h = txt.get_width() + 40, txt.get_height() + 10
        img = pygame.Surface((w, h), pygame.SRCALPHA)
        plate(img, img.get_rect(), rivets=False)
        img.blit(txt, (20, 5))
        _keep(key, img)
    r = img.get_rect(centery=int(cy))
    if left is not None:
        r.left = int(left)
    elif right is not None:
        r.right = int(right)
    surface.blit(img, r.topleft)
    return r


def tab(surface, rect, lit_on):
    """The plate of one tab; the open one is lit."""
    r = pygame.Rect(rect)
    key = ("tab", r.w, r.h, bool(lit_on))
    img = _layers.get(key)
    if img is None:
        if lit_on:
            img = _gradient(r.w, r.h, (74, 52, 18), LIT_FILL, 255)
            halo = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            pygame.draw.rect(halo, AMBER + (40,), halo.get_rect(), border_radius=3)
            img.blit(halo, (0, 0))
            pygame.draw.rect(img, LIT_EDGE + (255,), img.get_rect(), 2, border_radius=3)
        else:
            img = _gradient(r.w, r.h, TAB_TOP, TAB_BOTTOM, 255)
            pygame.draw.rect(img, STEEL_EDGE + (255,), img.get_rect(), 1, border_radius=3)
            pygame.draw.line(img, STEEL_LIGHT + (255,), (3, 1), (r.w - 4, 1), 1)
        _keep(key, img)
    surface.blit(img, r.topleft)
    return r


HOLO_EDGE = (61, 139, 214)
HOLO_TEXT = (125, 175, 225)
CRT = (79, 209, 197)              # the phosphor of the screens
CRT_DIM = (58, 168, 157)          # an entry of a terminal list
CRT_TEXT = (111, 224, 212)        # what is read on a terminal
CRT_BG = (4, 18, 15)


def _chamfer(w, h, c):
    return [(c, 0), (w - c - 1, 0), (w - 1, c), (w - 1, h - c - 1), (w - c - 1, h - 1), (c, h - 1), (0, h - c - 1), (0, c)]


def holo(surface, rect, chosen=False, glass=None):
    """A holographic card: dark blue glass, a faint grid, cut corners. `chosen`: lit in gold (the hull that flies). `glass`: None for clear glass, else its opacity (0-255)."""
    r = pygame.Rect(rect)
    key = ("holo", r.w, r.h, bool(chosen), glass)
    img = _layers.get(key)
    if img is None:
        img = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pts = _chamfer(r.w, r.h, 12)
        if glass is None:
            pygame.draw.polygon(img, (40, 110, 190, 40), pts)             # clear glass: the picture shows through (cards)
        else:
            pygame.draw.polygon(img, (10, 22, 42, int(glass)), pts)       # solid glass: a long text is read on it
        grid = (AMBER if chosen else HOLO_EDGE) + (26,)
        lines = img if glass is None else pygame.Surface((r.w, r.h), pygame.SRCALPHA)      # (solid glass: blended, not a hole)
        for x in range(20, r.w - 14, 20):
            pygame.draw.line(lines, grid, (x, 8), (x, r.h - 9))
        for y in range(20, r.h - 14, 20):
            pygame.draw.line(lines, grid, (8, y), (r.w - 9, y))
        if lines is not img:
            img.blit(lines, (0, 0))
        if chosen:
            pygame.draw.polygon(img, (255, 179, 71, 60), pts, 5)             # a soft glow inside the edge
        pygame.draw.polygon(img, (LIT_EDGE if chosen else HOLO_EDGE) + (255,), pts, 2)
        _keep(key, img)
    surface.blit(img, r.topleft)
    return r


def crt(surface, rect):
    """A CRT screen: dark green glass with a glow along the edge, scan lines and a steel bezel."""
    r = pygame.Rect(rect)
    key = ("crt", r.w, r.h)
    img = _layers.get(key)
    if img is None:
        img = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.rect(img, CRT_BG + (238,), img.get_rect(), border_radius=4)
        for i, a in enumerate((46, 30, 18, 9)):                                 # the glow, brighter at the edge
            pygame.draw.rect(img, CRT + (a,), img.get_rect().inflate(-6 - i * 4, -6 - i * 4), 4, border_radius=4)
        lines = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        for y in range(1, r.h - 3, 3):
            pygame.draw.line(lines, (0, 0, 0, 70), (3, y), (r.w - 4, y))
        img.blit(lines, (0, 0))                                                 # (blended: a darker line, not a hole)
        pygame.draw.rect(img, STEEL_EDGE + (255,), img.get_rect(), 3, border_radius=4)
        pygame.draw.rect(img, STEEL_DARK + (255,), img.get_rect().inflate(-6, -6), 1, border_radius=3)
        _keep(key, img)
    surface.blit(img, r.topleft)
    return r


def phosphor(surface, rect):
    """The chosen row of a terminal list: lit phosphor (dark letters go on it), with the scan lines of the screen."""
    r = pygame.Rect(rect)
    key = ("phosphor", r.w, r.h)
    img = _layers.get(key)
    if img is None:
        img = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.rect(img, CRT + (246,), img.get_rect(), border_radius=2)
        lines = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        for y in range(1, r.h, 3):
            pygame.draw.line(lines, (0, 40, 36, 40), (0, y), (r.w, y))
        img.blit(lines, (0, 0))
        _keep(key, img)
    surface.blit(img, r.topleft)
    return r


def meter(surface, x, y, filled, total, cell_w=16, cell_h=5, gap=3, colour=CRT):
    """`total` small cells side by side from (x, y), the first `filled` lit. Returns the rect of the row."""
    total = max(0, int(total))
    filled = max(0, min(total, int(filled)))
    key = ("meter", filled, total, cell_w, cell_h, gap, tuple(colour))
    img = _layers.get(key)
    if img is None:
        w = total * cell_w + max(0, total - 1) * gap
        img = pygame.Surface((max(1, w), cell_h), pygame.SRCALPHA)
        for i in range(total):
            cell = pygame.Rect(i * (cell_w + gap), 0, cell_w, cell_h)
            if i < filled:
                pygame.draw.rect(img, tuple(colour) + (255,), cell)
                pygame.draw.rect(img, tuple(colour) + (70,), cell.inflate(2, 2), 1)
            else:
                pygame.draw.rect(img, (42, 47, 57, 255), cell)
        _keep(key, img)
    surface.blit(img, (x, y))
    return pygame.Rect(x, y, img.get_width(), cell_h)


_band = None


def band():
    """The band of the help bar: nearly black steel with a bevelled upper edge."""
    global _band
    if _band is None:
        _band = pygame.Surface((BASE_WIDTH, 46), pygame.SRCALPHA)
        _band.fill(STEEL_DARK + (236,))
        pygame.draw.line(_band, STEEL_EDGE + (255,), (0, 0), (BASE_WIDTH, 0), 2)
        pygame.draw.line(_band, STEEL_LIGHT + (255,), (0, 2), (BASE_WIDTH, 2), 1)
    return _band


# --- the pictures behind the panes ----------------------------------------------------------------------------------
BACKDROPS = {"map": "ui_map", "hangar": "ui_hangar", "bestiary": "ui_bestiary", "log": "ui_log", "extras": "ui_extras",
             "gate": "ui_log"}            # the screens before the hub (games, mode, name, ...) share the pilot's quarters
_backdrops = {}


def backdrop(pane):
    """The picture behind a pane of the hub (darkened when it was made, see tools/make_ui_backdrops.py), loaded on
    first use. None when the file is missing or broken: the starfield shows then, as before."""
    name = BACKDROPS.get(pane)
    if name is None:
        return None
    if name in _backdrops:
        return _backdrops[name]
    img = None
    path = asset_path("story", name + ".jpg")
    if os.path.isfile(path):
        try:
            img = pygame.image.load(path).convert()
            if img.get_size() != (BASE_WIDTH, BASE_HEIGHT):
                img = pygame.transform.smoothscale(img, (BASE_WIDTH, BASE_HEIGHT))
        except Exception:
            log_exc("phobos_ui.backdrop")
            img = None
    _backdrops[name] = img
    return img
