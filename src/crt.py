"""
CRT scanlines (Options > Display > Scanlines 0-3), drawn on the 1280 x 720 picture before it goes to the screen.

One scanline every 3 rows: 720 / 3 = 240 lines, like the arcade boards of the time. Each line has a profile across
its 3 rows (near the top of the beam, its centre, the dark gap) instead of hard bars, and the picture darkens a little
towards its corners (vignette). All of it is one multiply overlay, built once.

Levels 2 and 3 add the glow of a real tube: its beam gets wider where the picture is bright, so the bright parts
(ships, shots, explosions, text) bleed into the dark gaps while the lines show in the dark of space:

    out = max(picture * mask, picture - GLOW_DROP)

(a bright pixel loses at most GLOW_DROP in a gap, a dark one loses its share of the mask). Four full-screen blits
(copy, subtract, multiply, max), no per-pixel Python and no `fill` with a blend flag (pygame's blended fill is about
30 times slower than a blended blit).

The 3-row period stays even on screen at 1440p (6 px) and 4K (9 px); at 1080p it alternates 4 and 5 px.
"""
import pygame

# level: (profile of the 3 rows of a line as multiply factors, vignette strength, glow)
LEVELS = {
    1: ((0.95, 1.0, 0.74), 0.12, False),
    2: ((0.93, 1.0, 0.62), 0.18, True),
    3: ((0.88, 1.0, 0.48), 0.24, True),
}
GLOW_DROP = 60           # 0-255: the most a pixel loses in a gap with the glow (the bright parts stay bright)


def _surface(size, like):
    try:
        return pygame.Surface(size, 0, like)
    except Exception:
        return pygame.Surface(size)


def _vignette(size, like, strength):
    """Multiply map: 255 in the middle, darker towards the corners (wider than high, like a tube)."""
    w, h = size
    small = _surface((80, 45), like)
    for yy in range(45):
        for xx in range(80):
            dx, dy = (xx + 0.5) / 40.0 - 1.0, (yy + 0.5) / 22.5 - 1.0
            d = min(1.0, dx * dx * 0.85 + dy * dy)
            v = int(round(255 * (1.0 - strength * d ** 1.6)))
            small.set_at((xx, yy), (v, v, v))
    return pygame.transform.smoothscale(small, (w, h))


def build(level, size, like=None):
    """The layers of a level for pictures like `like` (same pixel format, so the blits stay fast), or None for 0.
    {"mask": multiply overlay, "glow": True at levels 2 and 3, "tmp": work surface, "drop": a plain GLOW_DROP grey}."""
    spec = LEVELS.get(int(level or 0))
    if spec is None:
        return None
    rows, vignette, glow = spec
    w, h = size
    mask = _surface(size, like)
    period = len(rows)
    for y in range(h):
        mask.fill((int(round(255 * rows[y % period])),) * 3, (0, y, w, 1))
    if vignette:
        mask.blit(_vignette(size, mask, vignette), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    layers = {"mask": mask, "glow": bool(glow), "tmp": None, "drop": None}
    if glow:
        layers["tmp"] = _surface(size, like)
        layers["drop"] = _surface(size, like)
        layers["drop"].fill((GLOW_DROP,) * 3)
    return layers


def apply(surface, layers):
    """Scanlines on `surface` (the 1280 x 720 picture), in place."""
    if not layers:
        return
    if layers["glow"]:
        tmp = layers["tmp"]
        tmp.blit(surface, (0, 0))
        tmp.blit(layers["drop"], (0, 0), special_flags=pygame.BLEND_RGB_SUB)      # the picture, a little dimmer
        surface.blit(layers["mask"], (0, 0), special_flags=pygame.BLEND_RGB_MULT)  # the lines
        surface.blit(tmp, (0, 0), special_flags=pygame.BLEND_RGB_MAX)             # the bright parts win over them
    else:
        surface.blit(layers["mask"], (0, 0), special_flags=pygame.BLEND_RGB_MULT)
