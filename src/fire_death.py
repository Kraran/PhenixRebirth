"""Death in the flames of the Guardians' fire bolt: the picture burns, chars and falls apart in ash that the wind scatters.

`render(source, t, style, canvas, origin)` draws ONE picture of that death at the time t (0 = the bolt touches, 1 = nothing is
left) on a transparent surface; ship_burn (the ship of the player) and guardian (the birds) bake a few dozen of them once,
at mission setup, so that nothing is made or scaled while the game runs. Everything is deterministic (no random numbers).

The look: the hull heats up and the fire runs through it (from the nose for the birds, from the middle for the ship); tongues
of flame rise from the burning pixels; each burnt pixel turns into an ember that cools into a grey ash flake blown away by
the wind. The ship also has a flash, a ring of heat and a big glow, and its ash cloud is far bigger and lasts longer.
"""
import math

import pygame

try:
    import numpy as np
except ImportError:                    # pragma: no cover - numpy is a requirement of the game
    np = None

END = 0.985                            # every flake is gone before the last picture, which is empty

FLAME = ((255, 215, 90), (255, 145, 28), (215, 55, 10), (110, 25, 8), (50, 12, 6))
_BLOBS = {}


def _lerp(a, b, k):
    return a + (b - a) * k


def _mix(c1, c2, k):
    k = 0.0 if k < 0.0 else 1.0 if k > 1.0 else k
    return (int(c1[0] + (c2[0] - c1[0]) * k), int(c1[1] + (c2[1] - c1[1]) * k), int(c1[2] + (c2[2] - c1[2]) * k))


def flame_colour(k):
    """0 = young flame (yellow) ... 1 = old flame (dark red), quantised so that few glow pictures are made."""
    k = max(0.0, min(0.999, k)) * (len(FLAME) - 1)
    i = int(k)
    c = _mix(FLAME[i], FLAME[i + 1], k - i)
    return tuple(min(255, (v // 12) * 12) for v in c)


def _blob(rx, ry, colour, strength):
    """A soft glowing ellipse (three nested ones) as a picture that is added to the glow layer."""
    key = (int(rx * 2), int(ry * 2), colour, round(strength * 8))
    pic = _BLOBS.get(key)
    if pic is None:
        w, h = max(2, int(rx * 2) + 2), max(2, int(ry * 2) + 2)
        pic = pygame.Surface((w, h))
        pic.fill((0, 0, 0))
        for scale, amount in ((1.0, 0.07), (0.62, 0.11), (0.3, 0.16)):
            part = pygame.Surface((w, h))
            part.fill((0, 0, 0))
            c = tuple(min(255, int(v * strength * amount)) for v in colour)
            box = pygame.Rect(0, 0, max(1, int(rx * 2 * scale)), max(1, int(ry * 2 * scale)))
            box.center = (w // 2, h // 2)
            pygame.draw.ellipse(part, c, box)
            pic.blit(part, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        _BLOBS[key] = pic
    return pic


def add_blob(glow, x, y, rx, ry, colour, strength):
    pic = _blob(rx, ry, colour, strength)
    glow.blit(pic, (round(x - pic.get_width() / 2), round(y - pic.get_height() / 2)), special_flags=pygame.BLEND_RGB_ADD)


# ------------------------------------------------------------------ where the fire starts
def from_the_nose(x, y, w, h, n):
    return 0.15 + 0.6 * (y / h) + 0.25 * n


def from_the_middle(x, y, w, h, n):
    d = math.hypot((x - w / 2) / (w / 2), (y - h / 2) / (h / 2))
    return 0.05 + 0.5 * min(1.0, d) + 0.2 * n


def _ship_extra(glow, out, t, cx, cy, w, h):
    """The flash, the ring of heat and the glow round the burning hull."""
    if t < 0.12:
        add_blob(glow, cx, cy, 50, 50, (255, 150, 50), (1 - t / 0.12) * 1.8)
    if 0.04 < t < 0.45:
        k = (t - 0.04) / 0.41
        radius = 20 + k * 110
        ring = pygame.Surface(glow.get_size())
        pygame.draw.circle(ring, tuple(int(v * (1 - k) * 0.9) for v in (255, 140, 40)), (round(cx), round(cy)), round(radius), 4)
        glow.blit(ring, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    if 0.05 < t < 0.65:
        add_blob(glow, cx, cy, 55, 80, (255, 90, 15), 1.1 * math.sin(math.pi * (t - 0.05) / 0.6))


_BASE = dict(front=from_the_nose, ignite=0.35, burn=0.30, flame_every=3, tongues=2, flame_rate=2.2, flame_life=0.30,
             rise=26, sway=3.0, lean=6, flame_size=5.0, flame_tall=1.6, ash_life=0.45, ember_k=0.3, wind=22,
             spread=14, ash_rise=40, gravity=10, big_ash=False, extra=None)

# "Flambée": a bird of the Guardians' mission
BIRD = dict(_BASE, ignite=0.22, burn=0.18, flame_size=4.6, rise=22, ash_life=0.38, wind=22, spread=16, ash_rise=42)
# "Brasier": the ship of the player (a huge fire, a long ash cloud)
SHIP = dict(_BASE, front=from_the_middle, ignite=0.22, burn=0.20, flame_every=2, tongues=3, flame_rate=2.4,
            flame_life=0.42, rise=95, sway=7, lean=22, flame_size=11.0, flame_tall=2.3, ash_life=0.70, ember_k=0.35,
            wind=60, spread=70, ash_rise=70, gravity=14, big_ash=True, extra=_ship_extra)


def _glow_to_rgba(glow):
    """The additive layer (on black) as a picture with an alpha channel: the brightest channel is the opacity."""
    out = pygame.Surface(glow.get_size(), pygame.SRCALPHA)
    rgb = pygame.surfarray.pixels3d(glow)
    alpha = rgb.max(axis=2)
    lit = np.nonzero(alpha)                          # (the glow is sparse: only these pixels are worked on)
    if len(lit[0]):
        a = alpha[lit].astype(np.uint16)
        colour = (rgb[lit].astype(np.uint16) * 255 // a[:, None]).astype(np.uint8)
        pygame.surfarray.pixels3d(out)[lit] = colour
        pygame.surfarray.pixels_alpha(out)[lit] = a.astype(np.uint8)
    del rgb
    return out


def _pixels(source, P):
    """What never changes between two pictures: for every solid pixel, its colour, its noise and when it ignites / turns to ash."""
    w, h = source.get_size()
    result = []
    for y in range(h):
        for x in range(w):
            c = source.get_at((x, y))
            if c.a < 32:
                continue
            n1 = ((x * 73 + y * 151) % 127) / 126.0
            n2 = ((x * 31 + y * 17 + 5) % 89) / 88.0
            ti = P["ignite"] * P["front"](x, y, w, h, n1)
            ta = ti + P["burn"] * (0.7 + 0.6 * n2)
            result.append((x, y, tuple(c), n1, n2, ti, ta))
    return result


def render(source, t, style, canvas, origin, pixels=None):
    """The picture of the death at t (0..1), on a transparent surface of the size `canvas`; `origin` = where the top left
    corner of `source` is."""
    P = style
    if pixels is None:
        pixels = _pixels(source, P)
    out = pygame.Surface(canvas, pygame.SRCALPHA)
    glow = pygame.Surface(canvas)
    glow.fill((0, 0, 0))
    ox, oy = origin
    w, h = source.get_size()
    cx, cy = ox + w / 2, oy + h / 2
    flames = []
    ash = []
    for x, y, c, n1, n2, ti, ta in pixels:
        if t < ti:
            heat = max(0.0, 1 - (ti - t) / 0.08) * 0.25
            out.set_at((ox + x, oy + y), (*_mix(c[:3], (255, 130, 30), heat), c[3]))
        elif t < ta:
            k = (t - ti) / (ta - ti)
            hot = _mix((255, 190, 80), (255, 100, 18), min(1.0, k * 2.2))
            charred = _mix(hot, (28, 20, 18), max(0.0, (k - 0.35) / 0.65))
            flick = 0.8 + 0.2 * math.sin(t * 60 + n1 * 30)
            out.set_at((ox + x, oy + y), (*(int(v * flick) for v in charred), c[3]))
            if (x * 7 + y * 13) % P["flame_every"] == 0:
                flames.append((ox + x, oy + y, n1, n2))
        else:
            ash.append((ox + x, oy + y, ta, n1, n2))
    # tongues of flame rise from the burning pixels
    for fx, fy, n1, n2 in flames:
        for j in range(P["tongues"]):
            rate = P["flame_rate"] * (0.8 + 0.4 * n2)
            phase = (n1 * 3.7 + j * 0.37) % 1.0
            life = P["flame_life"] * (0.7 + 0.6 * ((n1 * 5 + j) % 1.0))
            age = ((t * rate + phase) % 1.0) * life
            k = age / life
            rise = P["rise"] * (age / P["flame_life"])
            sway = math.sin(age * 22 + n1 * 40 + j) * P["sway"] * k + P["lean"] * k * k
            size = P["flame_size"] * (1.0 - 0.55 * k) * (0.7 + 0.6 * n2)
            add_blob(glow, fx + sway, fy - rise, size * 0.72, size * P["flame_tall"],
                     flame_colour(k * 0.9), 1.0 - k ** 1.6)
    # each burnt pixel is an ember, then a grey ash flake that the wind carries away
    for ax, ay, ta, n1, n2 in ash:
        a = t - ta
        life = min(P["ash_life"] * (0.6 + 0.8 * n2), END - ta)
        if a > life or life <= 0:
            continue
        k = a / life
        if k < P["ember_k"]:
            e = 1 - k / P["ember_k"]
            colour, alpha = _mix((170, 160, 150), (255, 150, 40), e), 1.0
        else:
            colour = _mix((205, 198, 190), (120, 116, 112), n1)
            alpha = max(0.0, 1.0 - (k - P["ember_k"]) / (1 - P["ember_k"])) ** 0.8
        px = ax + (P["wind"] * (0.5 + n1) + (n2 - 0.5) * P["spread"]) * a + math.sin(a * 9 + n1 * 20) * 3 * k
        py = ay + (-P["ash_rise"] * (0.3 + n2) + P["gravity"] * k) * a
        size = 1 + (n2 > 0.55) + (1 if (P["big_ash"] and n1 > 0.9) else 0)
        if alpha > 0.02:
            out.fill((*colour, int(255 * alpha)), (round(px), round(py), size, size))
        if k < P["ember_k"] * 0.8 and n1 > 0.5:
            add_blob(glow, px, py, 3, 3, (255, 110, 20), 1.2 * (1 - k / P["ember_k"]))
    if P["extra"]:
        P["extra"](glow, out, t, cx, cy, w, h)
    out.blit(_glow_to_rgba(glow), (0, 0))
    return out


def frames(source, count, style, canvas, origin):
    """`count` pictures from t = 0 to t = 1 (the last one is empty)."""
    pixels = _pixels(source, style)
    return tuple(render(source, i / (count - 1), style, canvas, origin, pixels) for i in range(count))
