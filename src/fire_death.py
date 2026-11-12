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
import loading

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
    """What never changes between two pictures: for every solid pixel (in reading order), where it is, its colour, its
    noise and when it ignites / turns to ash. Arrays (numpy), one value per pixel."""
    w, h = source.get_size()
    rgb = pygame.surfarray.array3d(source)                 # [x, y, channel]
    alpha = pygame.surfarray.array_alpha(source)
    ys, xs = np.nonzero(alpha.T >= 32)                     # (y major: the order of the old loops)
    n1 = ((xs * 73 + ys * 151) % 127) / 126.0
    n2 = ((xs * 31 + ys * 17 + 5) % 89) / 88.0
    front = P["front"]
    if front is from_the_nose:
        ti = P["ignite"] * (0.15 + 0.6 * (ys / h) + 0.25 * n1)
    else:
        ti = np.array([P["ignite"] * front(int(x), int(y), w, h, float(n)) for x, y, n in zip(xs, ys, n1)], dtype=float)
    ta = ti + P["burn"] * (0.7 + 0.6 * n2)
    return {"x": xs, "y": ys, "rgb": rgb[xs, ys].astype(np.int64), "a": alpha[xs, ys].astype(np.int64),
            "n1": n1, "n2": n2, "ti": ti, "ta": ta}


def _mix_arr(c1, c2, k):
    """_mix on arrays: c1, c2 (n, 3) or (3,), k (n,) -> ints (n, 3), the same truncation as _mix."""
    k = np.clip(k, 0.0, 1.0)[:, None]
    c1 = np.asarray(c1, dtype=np.int64)
    c2 = np.asarray(c2, dtype=np.int64)
    return (c1 + (c2 - c1) * k).astype(np.int64)


def _sin_each(values):
    """math.sin of every value (exactly the old numbers, numpy's sin may differ in the last bit)."""
    return np.fromiter((math.sin(v) for v in values.tolist()), dtype=float, count=len(values))


def _flame_colours(k):
    """flame_colour on an array: the same colours (tuples), one per value."""
    k = np.maximum(0.0, np.minimum(0.999, k)) * (len(FLAME) - 1)
    i = k.astype(np.int64)
    f = np.array(FLAME, dtype=np.int64)
    c = _mix_arr(f[i], f[i + 1], k - i)
    c = np.minimum(255, (c // 12) * 12)
    return [tuple(v) for v in c.tolist()]


def _tongues(glow, flames, t, P):
    """The tongues of flame of every burning pixel (`flames`: arrays x, y, n1, n2), worked out together, then added to
    the glow in one go: the same blobs, the same places as one by one."""
    fx, fy, fn1, fn2 = flames
    per_tongue = []
    for j in range(P["tongues"]):
        rate = P["flame_rate"] * (0.8 + 0.4 * fn2)
        phase = (fn1 * 3.7 + j * 0.37) % 1.0
        life = P["flame_life"] * (0.7 + 0.6 * ((fn1 * 5 + j) % 1.0))
        age = ((t * rate + phase) % 1.0) * life
        k = age / life
        rise = P["rise"] * (age / P["flame_life"])
        sway = _sin_each(age * 22 + fn1 * 40 + j) * P["sway"] * k + P["lean"] * k * k
        size = P["flame_size"] * (1.0 - 0.55 * k) * (0.7 + 0.6 * fn2)
        per_tongue.append(list(zip((fx + sway).tolist(), (fy - rise).tolist(), (size * 0.72).tolist(),
                                   (size * P["flame_tall"]).tolist(), _flame_colours(k * 0.9),
                                   (1.0 - k ** 1.6).tolist())))
    blits = []
    # (pixel after pixel, its tongues one after the other: the order of the old loop, which matters, as the first blob
    # made for a size is the one kept in _BLOBS)
    for tongues in zip(*per_tongue):
        for x, y, rx, ry, colour, st in tongues:
            pic = _blob(rx, ry, colour, st)
            blits.append((pic, (round(x - pic.get_width() / 2), round(y - pic.get_height() / 2)), None,
                          pygame.BLEND_RGB_ADD))
    glow.blits(blits, doreturn=False)


def render(source, t, style, canvas, origin, pixels=None):
    """The picture of the death at t (0..1), on a transparent surface of the size `canvas`; `origin` = where the top left
    corner of `source` is. (Worked on whole arrays of pixels: the same picture as pixel by pixel, a few times faster.)"""
    P = style
    if pixels is None:
        pixels = _pixels(source, P)
    out = pygame.Surface(canvas, pygame.SRCALPHA)
    glow = pygame.Surface(canvas)
    glow.fill((0, 0, 0))
    ox, oy = origin
    w, h = source.get_size()
    cx, cy = ox + w / 2, oy + h / 2
    X, Y, C, A = pixels["x"], pixels["y"], pixels["rgb"], pixels["a"]
    N1, N2, TI, TA = pixels["n1"], pixels["n2"], pixels["ti"], pixels["ta"]
    cw, ch = canvas
    rgb_out = pygame.surfarray.pixels3d(out)
    a_out = pygame.surfarray.pixels_alpha(out)
    # not burning yet: the hull heats up
    cold = t < TI
    if cold.any():
        heat = np.maximum(0.0, 1 - (TI[cold] - t) / 0.08) * 0.25
        col = _mix_arr(C[cold], (255, 130, 30), heat)
        px, py = ox + X[cold], oy + Y[cold]
        keep = (px >= 0) & (px < cw) & (py >= 0) & (py < ch)
        rgb_out[px[keep], py[keep]] = col[keep]
        a_out[px[keep], py[keep]] = A[cold][keep]
    # burning: hot, then charred, flickering
    burning = (~cold) & (t < TA)
    flames = []
    if burning.any():
        ti, ta, n1 = TI[burning], TA[burning], N1[burning]
        k = (t - ti) / (ta - ti)
        hot = _mix_arr(np.array((255, 190, 80)), (255, 100, 18), np.minimum(1.0, k * 2.2))
        charred = _mix_arr(hot, (28, 20, 18), np.maximum(0.0, (k - 0.35) / 0.65))
        flick = 0.8 + 0.2 * _sin_each(t * 60 + n1 * 30)
        col = (charred * flick[:, None]).astype(np.int64)
        xb, yb = X[burning], Y[burning]
        px, py = ox + xb, oy + yb
        keep = (px >= 0) & (px < cw) & (py >= 0) & (py < ch)
        rgb_out[px[keep], py[keep]] = col[keep]
        a_out[px[keep], py[keep]] = A[burning][keep]
        lit = (xb * 7 + yb * 13) % P["flame_every"] == 0
        if lit.any():
            flames = (px[lit], py[lit], n1[lit], N2[burning][lit])
    del rgb_out, a_out
    # tongues of flame rise from the burning pixels
    if flames:
        _tongues(glow, flames, t, P)
    # each burnt pixel is an ember, then a grey ash flake that the wind carries away
    gone = ~(cold | burning)
    if gone.any():
        ta, n1, n2 = TA[gone], N1[gone], N2[gone]
        ax, ay = (ox + X[gone]).astype(float), (oy + Y[gone]).astype(float)
        a = t - ta
        life = np.minimum(P["ash_life"] * (0.6 + 0.8 * n2), END - ta)
        live = ~((a > life) | (life <= 0))
        ta, n1, n2, ax, ay, a, life = ta[live], n1[live], n2[live], ax[live], ay[live], a[live], life[live]
        k = a / life
        ember = k < P["ember_k"]
        e = 1 - k / P["ember_k"]
        col_e = _mix_arr(np.array((170, 160, 150)), (255, 150, 40), e)
        col_a = _mix_arr(np.array((205, 198, 190)), (120, 116, 112), n1)
        colour = np.where(ember[:, None], col_e, col_a)
        alpha = np.where(ember, 1.0, np.maximum(0.0, 1.0 - (k - P["ember_k"]) / (1 - P["ember_k"])) ** 0.8)
        px = ax + (P["wind"] * (0.5 + n1) + (n2 - 0.5) * P["spread"]) * a + _sin_each(a * 9 + n1 * 20) * 3 * k
        py = ay + (-P["ash_rise"] * (0.3 + n2) + P["gravity"] * k) * a
        size = 1 + (n2 > 0.55).astype(int) + ((n1 > 0.9).astype(int) if P["big_ash"] else 0)
        shown = alpha > 0.02
        rx = np.array([round(v) for v in px.tolist()], dtype=np.int64)
        ry = np.array([round(v) for v in py.tolist()], dtype=np.int64)
        a255 = (255 * alpha).astype(np.int64)
        # the flakes, in order (a later one covers an earlier one), each a square of `size` pixels, cut at the edges
        if shown.any():
            idx = np.nonzero(shown)[0]
            big = int(size[idx].max())
            parts = [idx[(size[idx] > d) & (size[idx] > d2)] for d in range(big) for d2 in range(big)]
            offs = [(d, d2) for d in range(big) for d2 in range(big)]
            fx = np.concatenate([rx[sel] + d for sel, (d, d2) in zip(parts, offs)])
            fy = np.concatenate([ry[sel] + d2 for sel, (d, d2) in zip(parts, offs)])
            fc = np.concatenate([colour[sel] for sel in parts])
            fa = np.concatenate([a255[sel] for sel in parts])
            rank = np.concatenate(parts)                    # (the old loop drew flake after flake: a later one on top)
            o = np.argsort(rank, kind="stable")
            fx, fy, fc, fa = fx[o], fy[o], fc[o], fa[o]
            keep = (fx >= 0) & (fx < cw) & (fy >= 0) & (fy < ch)
            rgb_out = pygame.surfarray.pixels3d(out)
            a_out = pygame.surfarray.pixels_alpha(out)
            rgb_out[fx[keep], fy[keep]] = fc[keep]
            a_out[fx[keep], fy[keep]] = fa[keep]
            del rgb_out, a_out
        glowing = np.nonzero(ember & (k < P["ember_k"] * 0.8) & (n1 > 0.5))[0]
        for i in glowing.tolist():
            add_blob(glow, float(px[i]), float(py[i]), 3, 3, (255, 110, 20), 1.2 * (1 - float(k[i]) / P["ember_k"]))
    if P["extra"]:
        P["extra"](glow, out, t, cx, cy, w, h)
    out.blit(_glow_to_rgba(glow), (0, 0))
    return out


def frames(source, count, style, canvas, origin):
    """`count` pictures from t = 0 to t = 1 (the last one is empty)."""
    pixels = _pixels(source, style)
    out = []
    for i in range(count):
        out.append(render(source, i / (count - 1), style, canvas, origin, pixels))
        loading.report()                      # (the bar of a mission moves on while the flames are made)
    return tuple(out)
