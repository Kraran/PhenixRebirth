"""The Phenix frames (assets/sprites/phenix/phenix_NN.png) are drawn on a canvas larger than the ship.

The artwork used to be cut by the edge of its canvas: the tips of both wings were missing. The missing parts were
added (tools/extend_wings.py) in a margin of WING_PAD_X pixels on each side and WING_PAD_Y pixels above AND below
the ship. The margin is the same on both sides of an axis, so the centre of the canvas is still the centre of the
ship, and nothing the ship already showed moved by one pixel.

The size of the ship is the size of the canvas WITHOUT that margin. Whoever scales a frame to a wanted size must
scale by `ship_size`, never by the size of the canvas, or the ship shrinks by the margin it was given.

The transformation (ship -> Phenix, and back) is drawn from a few pictures that were made by hand. `morph_sequence`
puts pictures between them (cross-dissolves), so that the change is smooth at the pace of the screen and starts
and ends on exactly the pictures that come before and after it.
"""
import os

import pygame

try:                         # the pictures between the drawn ones need numpy; without it the drawn ones are used as they are
    import numpy as np
except ImportError:          # pragma: no cover - exercised by a test that hides numpy
    np = None

WING_PAD_X = 16
WING_PAD_Y = 12

LEAD_STEPS = 3               # pictures that fade the flight picture on show into the way back
MORPH_STEPS = 4              # pictures added between two drawn pictures: 6 drawn ones make 26 in all
FLASH_PEAK = 0.66            # where in the change (0 = ship, 1 = flight) the flash is the brightest: the wings open
FLASH_WIDTH = 0.128          # width of the flash, as a part of the change
FLASH_RADIUS = 110           # radius of the halo, in pixels of the picture (the ship in the game is 1 picture pixel = 1 pixel)
PREVIEW_FLASH_RADIUS = 75     # the same, in the ship select preview, where the pictures are bigger and the panel small
FLASH_GLOW = 0.80            # opacity of the halo at its brightest
FLASH_LIGHT = 190            # how much the ship itself is lightened at the peak (0..255)
SHIELD_IN_STEPS = 1          # pictures added between two drawn pictures of the dome forming (8 drawn make 15)
SHIELD_OUT_STEPS = 2         # the same for the dome going away (6 drawn make 16)
SHIELD_IN_SEC = 0.22         # the dome forming. Not only a look: the countdown of the bubble waits for it and
SHIELD_OUT_SEC = 0.26        # the cooldown starts after the dome going away, so changing them changes the game
PHENIX_MORPH_IN_SEC = 0.45   # ship -> Phenix
PHENIX_MORPH_OUT_SEC = 0.40  # Phenix -> ship
PREVIEW_MORPH_IN_SEC = 0.65  # the same in the ship select screen, where there is time to watch it
PREVIEW_MORPH_OUT_SEC = 0.60


def ship_size(frame):
    """(width, height) of the ship in a Phenix frame, the margin left out. `frame` is a pygame Surface."""
    return frame.get_width() - 2 * WING_PAD_X, frame.get_height() - 2 * WING_PAD_Y


def _on_canvas(frame, size):
    """(premultiplied colour, alpha) arrays of `frame` on a canvas of `size`, where the game puts it when it draws a
    picture centred: the picture's left edge is at centre - width // 2, so the offset here is size // 2 - width // 2."""
    cw, ch = size
    w, h = frame.get_size()
    ox, oy = cw // 2 - w // 2, ch // 2 - h // 2
    rgb = np.zeros((cw, ch, 3), np.float32)
    alpha = np.zeros((cw, ch), np.float32)
    rgb[ox: ox + w, oy: oy + h] = pygame.surfarray.array3d(frame)
    alpha[ox: ox + w, oy: oy + h] = pygame.surfarray.array_alpha(frame)
    return rgb, alpha


def _surface(rgb, alpha):
    cw, ch = alpha.shape
    px = np.zeros((cw, ch, 4), np.uint8)
    px[..., :3] = np.clip(np.rint(rgb), 0, 255)
    px[..., 3] = np.clip(np.rint(alpha), 0, 255)
    return pygame.image.frombuffer(px.transpose(1, 0, 2).tobytes(), (cw, ch), "RGBA").convert_alpha()


def _mix(a, b, t):
    """The picture t of the way from a to b (each a pair from _on_canvas), as a Surface."""
    rgb_a, alpha_a = a
    rgb_b, alpha_b = b
    pre_a, pre_b = rgb_a * (alpha_a / 255.0)[..., None], rgb_b * (alpha_b / 255.0)[..., None]
    alpha = (1.0 - t) * alpha_a + t * alpha_b
    pre = (1.0 - t) * pre_a + t * pre_b
    rgb = np.where(alpha[..., None] > 0.5, pre * 255.0 / np.maximum(alpha, 1e-3)[..., None], 0.0)
    return _surface(rgb, alpha)


FLOW_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sprites", "morph_flow.npz")
_flow_cache = {}


def morph_flow(path=None):
    """How the pictures of the transformation move into one another, as `(fab, fba)`: two lists with one array
    (width, height, 2) for each two pictures in a row (ship, the drawn pictures, first flight picture), made by
    tools/bake_morph_flow.py. `fab` says where a pixel of the first picture goes in the second, `fba` where a pixel of
    the second comes from in the first. Together with their canvas size. None when numpy or the file is missing or
    unreadable: the pictures between are then plain cross-dissolves."""
    if np is None:
        return None
    path = path or FLOW_FILE
    if path not in _flow_cache:
        try:
            with np.load(path) as data:
                size = tuple(int(v) for v in data["size"])
                fab, fba = data["fab"].astype(np.float32), data["fba"].astype(np.float32)
            _flow_cache[path] = (size, list(fab), list(fba))
        except Exception:      # missing, damaged, an older numpy: the game works without it
            _flow_cache[path] = None
    return _flow_cache[path]


def _warp(img, flow, k):
    """`img` (width, height, C) sampled at x + k * flow(x), bilinear, zero outside the picture."""
    cw, ch = img.shape[:2]
    gx, gy = np.meshgrid(np.arange(cw, dtype=np.float32), np.arange(ch, dtype=np.float32), indexing="ij")
    sx, sy = gx + k * flow[..., 0], gy + k * flow[..., 1]
    x0, y0 = np.floor(sx).astype(np.int32), np.floor(sy).astype(np.int32)
    fx, fy = (sx - x0)[..., None], (sy - y0)[..., None]
    out = np.zeros_like(img)
    for dx, dy, w in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xi, yi = x0 + dx, y0 + dy
        ok = ((xi >= 0) & (xi < cw) & (yi >= 0) & (yi < ch))[..., None]
        out += np.where(ok, img[np.clip(xi, 0, cw - 1), np.clip(yi, 0, ch - 1)], 0.0) * w
    return out


def _mix_flow(a, b, t, fab, fba):
    """Like `_mix`, but the details of `a` and `b` are first moved along the flow to where they are at t, so they
    do not show through each other as a ghost."""
    rgb_a, alpha_a = a
    rgb_b, alpha_b = b
    pa_ = np.dstack([rgb_a * (alpha_a / 255.0)[..., None], alpha_a])
    pb_ = np.dstack([rgb_b * (alpha_b / 255.0)[..., None], alpha_b])
    m = (1.0 - t) * _warp(pa_, fba, t) + t * _warp(pb_, fab, 1.0 - t)
    alpha = np.maximum(m[..., 3], 0.0)
    rgb = np.where(alpha[..., None] > 0.5, m[..., :3] * 255.0 / np.maximum(alpha, 1e-3)[..., None], 0.0)
    return _surface(rgb, alpha)


def flash_colour(flight):
    """The colour of the flash: the fire of the Phenix picture `flight` (the brightest fifth of its saturated pixels),
    at full strength and lifted a little toward white. About orange for the original, golden for the gold one, blue
    for the blue one."""
    rgb = pygame.surfarray.array3d(flight).astype(np.float32)
    alpha = pygame.surfarray.array_alpha(flight)
    top, low = rgb.max(2), rgb.min(2)
    fire = (alpha > 128) & (top - low > 80) & (top > 150)
    if not fire.any():
        return (255, 170, 70)
    light = rgb.sum(2)
    bright = fire & (light >= np.quantile(light[fire], 0.8))
    colour = rgb[bright].mean(0)
    colour = colour * (255.0 / max(1.0, colour.max()))
    colour = colour * 0.85 + 255.0 * 0.15
    return tuple(int(round(c)) for c in colour)


def flash_level(position):
    """How strong the flash is (0..1) at `position` in the change (0 = ship, 1 = first picture of the flight). It is
    exactly 0 at both ends, so the change starts and ends on the plain pictures."""
    g = np.exp(-((position - FLASH_PEAK) / FLASH_WIDTH) ** 2)
    floor = 0.02
    return float(max(0.0, g - floor) / (1.0 - floor))


def _with_flash(surf, level, colour, size, radius):
    """`surf` (premade picture) on a canvas of `size`, lightened and with a halo of `colour` behind it, `level` 0..1.
    The halo is a soft round glow, opaque at its heart and gone at `radius`."""
    rgb, alpha = _on_canvas(surf, size)
    if level <= 0.0:
        return _surface(rgb, alpha)
    cw, ch = size
    yy, xx = np.mgrid[0:cw, 0:ch].astype(np.float32)
    dist = np.hypot(xx - cw // 2, yy - ch // 2) / float(radius)
    halo = (np.clip(1.0 - dist, 0.0, 1.0) ** 2.2) * (FLASH_GLOW * level)
    light = np.array([0.65 * c + 0.35 * 255.0 for c in colour], np.float32) / 255.0 * (FLASH_LIGHT * level)
    body = np.clip(rgb + light[None, None, :], 0.0, 255.0)
    a_s = alpha / 255.0
    a_o = a_s + halo * (1.0 - a_s)
    halo_rgb = np.array(colour, np.float32)[None, None, :]
    mix = body * a_s[..., None] + halo_rgb * (halo * (1.0 - a_s))[..., None]
    out_rgb = np.where(a_o[..., None] > 1e-4, mix / np.maximum(a_o, 1e-4)[..., None], 0.0)
    return _surface(out_rgb, a_o * 255.0)


def dissolve(pictures, steps=MORPH_STEPS, flow=None):
    """The `pictures` in order, with `steps` cross-dissolves between each two, all on a canvas of the size of the biggest
    and placed in it the way the game draws them centred. Empty when numpy is missing or a picture is None.

    With `flow` (from `morph_flow`, when it fits the canvas and the number of pictures) the pictures between are made
    by moving the details along the flow as well as fading, which does not leave the one picture as a ghost in the other."""
    if np is None or not pictures or any(k is None for k in pictures):
        return []
    size = (max(k.get_width() for k in pictures), max(k.get_height() for k in pictures))
    arrays = [_on_canvas(k, size) for k in pictures]
    if flow is not None and not (flow[0] == size and len(flow[1]) == len(pictures) - 1 == len(flow[2])):
        flow = None
    out = []
    for i, a in enumerate(arrays):
        out.append(_surface(*a))
        if i == len(arrays) - 1:
            break
        for j in range(1, steps + 1):
            t = j / float(steps + 1)
            if flow is None:
                out.append(_mix(a, arrays[i + 1], t))
            else:
                out.append(_mix_flow(a, arrays[i + 1], t, flow[1][i], flow[2][i]))
    return out


def morph_sequence(ship, drawn, flight, steps=MORPH_STEPS, flash=False, flash_radius=FLASH_RADIUS, use_flow=True):
    """The pictures of the transformation, ship first and the first picture of the flight last: `ship`, then the
    `drawn` pictures, then `flight`, with `steps` cross-dissolves between each two.

    All the pictures have the size of the biggest and sit in it the way the game draws them centred, so each picture
    drawn centred at (x, y) puts every pixel of the original where it was. The drawn pictures themselves are not
    altered. Where a picture is transparent and the next is not, the pixel fades in (the colour is mixed
    premultiplied by the alpha, so a half-transparent pixel is not darkened). Empty when there is nothing drawn, or
    when numpy is missing (the caller then uses the drawn pictures).

    With `flash`, the pictures near the middle of the change are lightened and have a halo of the colour of the
    Phenix's fire (`flash_colour`) behind them, strongest when the wings open (`flash_level`). The pictures are then
    on a canvas big enough for the halo (radius `flash_radius`), still centred: the ship is where it was."""
    if np is None:
        return []
    keys = [ship] + list(drawn) + [flight]
    if not drawn or any(k is None for k in keys):
        return []
    size = (max(k.get_width() for k in keys), max(k.get_height() for k in keys))
    plain = dissolve(keys, steps, morph_flow() if use_flow else None)
    if not flash:
        return plain
    colour = flash_colour(flight)
    big = (max(size[0], 2 * flash_radius), max(size[1], 2 * flash_radius))
    last = float(len(plain) - 1)
    return [_with_flash(pic, flash_level(i / last), colour, big, flash_radius) for i, pic in enumerate(plain)]


def lead_in(start, end, steps=LEAD_STEPS):
    """`steps` pictures that fade `start` into `end`, neither of them included: they join the flight picture on show
    to the first picture of the way back, which is another one of the flight. Empty when numpy is missing."""
    if np is None:
        return []
    size = (max(start.get_width(), end.get_width()), max(start.get_height(), end.get_height()))
    a, b = _on_canvas(start, size), _on_canvas(end, size)
    return [_mix(a, b, j / float(steps + 1)) for j in range(1, steps + 1)]
