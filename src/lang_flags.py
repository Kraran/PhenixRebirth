"""The little flags of the languages (the "Language" row of the options): one per code of i18n.LANGS, drawn with
pygame (no picture file), four times bigger then smoothed down, and kept once made.

    lang_flags.flag(code, height=22)   the flag of a language, or None for an unknown code
"""
import math

import pygame

W, H = 33, 22                  # the size of a flag at height 22 (3:2)
K = 4                          # drawn this many times bigger, then smoothed down (clean edges and diagonals)
BORDER = (20, 20, 30)
_CACHE = {}

WHITE = (255, 255, 255)


def _bands(s, colors, vertical, weights=None):
    w, h = s.get_size()
    weights = weights or [1] * len(colors)
    total = float(sum(weights))
    pos = 0.0
    for color, k in zip(colors, weights):
        a = round(pos / total * (w if vertical else h))
        pos += k
        b = round(pos / total * (w if vertical else h))
        rect = (a, 0, b - a, h) if vertical else (0, a, w, b - a)
        s.fill(color, rect)


def _nordic(s, back, cross, inner=None):
    """A Nordic cross: its upright a little to the hoist side (proportions of the Swedish flag, 5:2:9 x 4:2:4); `inner`
    a thinner cross inside it (Norway)."""
    w, h = s.get_size()
    s.fill(back)
    x0, x1 = round(w * 5 / 16), round(w * 7 / 16)
    y0, y1 = round(h * 4 / 10), round(h * 6 / 10)
    s.fill(cross, (x0, 0, x1 - x0, h))
    s.fill(cross, (0, y0, w, y1 - y0))
    if inner is not None:
        dx, dy = (x1 - x0) // 4, (y1 - y0) // 4
        s.fill(inner, (x0 + dx, 0, x1 - x0 - 2 * dx, h))
        s.fill(inner, (0, y0 + dy, w, y1 - y0 - 2 * dy))


def _star(s, color, cx, cy, r, turn=-math.pi / 2):
    pts = []
    for i in range(10):
        a = turn + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.40
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    pygame.draw.polygon(s, color, pts)


def _union_jack(s):
    w, h = s.get_size()
    blue, red = (1, 33, 105), (200, 16, 46)
    s.fill(blue)
    t = h / 5.0                                          # the white saltire
    pygame.draw.line(s, WHITE, (0, 0), (w, h), round(t))
    pygame.draw.line(s, WHITE, (0, h), (w, 0), round(t))
    pygame.draw.line(s, red, (0, 0), (w, h), round(t / 3))
    pygame.draw.line(s, red, (0, h), (w, 0), round(t / 3))
    cw = round(h / 3.0)                                  # the white cross, the red one inside it
    s.fill(WHITE, (w // 2 - cw // 2, 0, cw, h))
    s.fill(WHITE, (0, h // 2 - cw // 2, w, cw))
    rw = round(h / 5.0)
    s.fill(red, (w // 2 - rw // 2, 0, rw, h))
    s.fill(red, (0, h // 2 - rw // 2, w, rw))


def _portugal(s):
    w, h = s.get_size()
    green, red, yellow = (0, 102, 0), (255, 0, 0), (255, 225, 0)
    split = round(w * 2 / 5)
    s.fill(green, (0, 0, split, h))
    s.fill(red, (split, 0, w - split, h))
    r = round(h * 0.26)
    pygame.draw.circle(s, yellow, (split, h // 2), r)
    pygame.draw.circle(s, red, (split, h // 2), round(r * 0.62))
    sw, sh = round(r * 0.8), round(r * 0.95)
    pygame.draw.rect(s, WHITE, (split - sw // 2, h // 2 - sh // 2, sw, sh), border_radius=max(1, sw // 3))


def _turkey(s):
    w, h = s.get_size()
    red = (227, 10, 23)
    s.fill(red)
    cx, cy = w * 0.36, h / 2
    r = h * 0.25
    pygame.draw.circle(s, WHITE, (round(cx), round(cy)), round(r))
    pygame.draw.circle(s, red, (round(cx + r * 0.25), round(cy)), round(r * 0.8))
    _star(s, WHITE, cx + r * 1.05, cy, r * 0.42, turn=math.pi)


def _spain(s):
    _bands(s, ((170, 21, 27), (241, 191, 0), (170, 21, 27)), vertical=False, weights=(1, 2, 1))


_PAINT = {
    "fr": lambda s: _bands(s, ((0, 35, 149), WHITE, (237, 41, 57)), vertical=True),
    "en": _union_jack,
    "es": _spain,
    "de": lambda s: _bands(s, ((0, 0, 0), (221, 0, 0), (255, 206, 0)), vertical=False),
    "it": lambda s: _bands(s, ((0, 146, 70), WHITE, (206, 43, 55)), vertical=True),
    "pt": _portugal,
    "nl": lambda s: _bands(s, ((174, 28, 40), WHITE, (33, 70, 139)), vertical=False),
    "pl": lambda s: _bands(s, (WHITE, (220, 20, 60)), vertical=False),
    "tr": _turkey,
    "sv": lambda s: _nordic(s, (0, 106, 167), (254, 204, 0)),
    "no": lambda s: _nordic(s, (186, 12, 47), WHITE, inner=(0, 32, 91)),
    "da": lambda s: _nordic(s, (200, 16, 46), WHITE),
    "ru": lambda s: _bands(s, (WHITE, (0, 57, 166), (213, 43, 30)), vertical=False),
}


def flag(code, height=H):
    """The flag of the language `code` at `height` px (3:2, a thin dark edge), or None for a code without one."""
    paint = _PAINT.get(code)
    if paint is None:
        return None
    height = max(6, int(height))
    key = (code, height)
    img = _CACHE.get(key)
    if img is None:
        w = round(height * W / H)
        big = pygame.Surface((w * K, height * K))
        paint(big)
        img = pygame.transform.smoothscale(big, (w, height))
        pygame.draw.rect(img, BORDER, img.get_rect(), 1)
        _CACHE[key] = img
    return img
