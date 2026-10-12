"""The flames of the ship engines: a straight, dense jet of burning gas that comes out of each nozzle.

Every flame is a short film (FRAMES pictures that loop in LOOP_SEC, side by side in assets/sprites/engines/KIND_COLOUR.png,
made by tools/make_engine_flames.py; if a file is missing the film is calculated when first needed) from a
temperature field: white-hot out of the nozzle, then yellow, orange... and a fade at the end of the jet (no point, no
sway). The colours of each hull are kept: Phoenix argent / blue / gold, Shield red / green / violet, Phenix red / blue.
At each frame the film is stretched to the thrust (longer and wider the harder the ship pushes) and drawn BEHIND the
hull, so the root of the jet is hidden in the nozzle.

Where the jets come out is read on the hull pictures (x from the middle of the ship, y from its middle, in pixels):
NOZZLES. `draw` is the only call the ship needs; `prepare` makes the film in advance (so nothing is built in the
middle of a mission).
"""
import math

import os

import numpy as np
import pygame

from errlog import log_exc
from settings import asset_path

FRAMES = 24                  # pictures in a loop of the film
LOOP_SEC = 1.0               # every wave of the turbulence makes a whole number of turns in this time (the loop has no jump)
SUPERSAMPLE = 3              # the film is calculated 3 times bigger, then shrunk: smooth edges

# colour of the jet from its cold edge (0) to its white-hot core (1): position, (r, g, b)
RAMPS = {
    "argent": ((0.00, (10, 40, 160)), (0.25, (30, 110, 240)), (0.50, (60, 190, 255)), (0.78, (170, 235, 255)), (1.0, (245, 252, 255))),
    "blue": ((0.00, (8, 25, 130)), (0.25, (20, 60, 210)), (0.50, (50, 120, 255)), (0.78, (150, 200, 255)), (1.0, (235, 245, 255))),
    "gold": ((0.00, (120, 55, 5)), (0.25, (200, 110, 15)), (0.50, (245, 175, 40)), (0.78, (255, 225, 120)), (1.0, (255, 252, 225))),
    "red": ((0.00, (110, 10, 3)), (0.25, (190, 35, 8)), (0.50, (245, 100, 18)), (0.78, (255, 185, 60)), (1.0, (255, 245, 200))),
    "green": ((0.00, (6, 50, 18)), (0.25, (20, 130, 40)), (0.50, (60, 205, 60)), (0.78, (170, 255, 90)), (1.0, (240, 255, 200))),
    "violet": ((0.00, (60, 12, 105)), (0.25, (130, 25, 170)), (0.50, (200, 55, 205)), (0.78, (255, 150, 180)), (1.0, (255, 230, 240))),
    "phenix_red": ((0.00, (110, 12, 3)), (0.25, (180, 30, 6)), (0.50, (240, 80, 12)), (0.78, (255, 170, 40)), (1.0, (255, 245, 190))),
    "phenix_blue": ((0.00, (30, 90, 200)), (0.25, (60, 150, 245)), (0.50, (120, 205, 255)), (0.78, (200, 240, 255)), (1.0, (255, 255, 255))),
}

# kind of jet -> where it comes out (x, y of each nozzle, from the middle of the ship), half width and length of the jet at
# full thrust. "phoenix" and "shield" are the two hulls, "phenix" the Phoenix transformed.
NOZZLES = {
    "phoenix": {"xs": (-9.0, 7.5), "ys": (41.5, 41.5), "half": 5.4, "length": 42.0},
    "shield": {"xs": (-13.0, -0.5, 12.0), "ys": (32.5, 37.5, 32.5), "half": 4.6, "length": 38.0},
    "phenix": {"xs": (-12.0, 11.0), "ys": (46.0, 46.0), "half": 9.0, "length": 66.0},
}

MIN_LENGTH = 0.30            # the length of the jet at idle (thrust 0), as a part of the full jet; thrust 1 gives the whole of it
MIN_WIDTH = 0.80             # the same for the width
SHOW_FROM = 0.05             # under this thrust there is no flame
BURST_LENGTH = 2.0           # flying up to the next stage (burst 1): the jet is this many times longer...
BURST_WIDTH = 1.12           # ...and a very little wider


def ramp_key(kind, palette):
    """The colours of a jet: `kind` "phoenix" / "shield" / "phenix", `palette` the hull's tint."""
    if kind == "phenix":
        return "phenix_blue" if palette == "blue" else "phenix_red"
    return palette if palette in RAMPS else ("red" if kind == "shield" else "argent")


def _colour(key, temp):
    pts = RAMPS[key]
    xs = [p[0] for p in pts]
    return np.stack([np.interp(temp, xs, [p[1][c] for p in pts]) for c in range(3)], axis=-1)


def _frame(key, half, length, t, ss=SUPERSAMPLE):
    """One picture of the jet (RGBA array, the nozzle at the middle of the top edge) at the time `t` of the loop."""
    width = int(half * 2 * 3.2) | 1
    height = int(length + 8)
    w, h = width * ss, height * ss
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    s = ys / (length * ss)                                    # 0 at the nozzle, 1 at the end of the jet
    sc = np.clip(s, 0.0, 1.0)
    cx = (w - 1) / 2.0
    # the width: a little flare out of the nozzle, then a slow narrowing; it never closes to a point, it fades out
    flare = 1.0 + 0.16 * np.sin(math.pi * np.minimum(1.0, sc / 0.30))
    edge = half * ss * flare * (1.0 - 0.50 * sc ** 1.3)
    # ragged edge: turbulence that runs down the jet (it does not wave the jet)
    rag = 1.0 + 0.07 * np.sin(2 * math.pi * (5.5 * sc - 6.0 * t)) + 0.04 * np.sin(2 * math.pi * (11.0 * sc - 9.0 * t))
    u = (xs - cx) / np.maximum(edge * rag, 1e-3)
    radial = np.clip(1.0 - np.abs(u) ** 3.2, 0.0, 1.0)         # dense across, then a quick edge
    # temperature along the jet: white-hot out of the nozzle, yellow, then orange as it cools and thins
    axial = np.clip(1.0 - sc, 0.0, 1.0) ** 0.75
    streaks = 1.0 + 0.12 * np.sin(2 * math.pi * (4.0 * sc - 5.0 * t)) + 0.07 * np.sin(2 * math.pi * (9.5 * sc - 8.0 * t))
    temp = radial * axial * streaks * 1.12
    temp = temp * (1.0 + 0.8 * np.exp(-(s / 0.14) ** 2))       # the bright head of the jet, at the nozzle
    temp = np.where(s < 0, 0.0, temp)
    soft = np.clip(s / 0.16, 0.0, 1.0)
    soft = soft * soft * (3.0 - 2.0 * soft)                    # the halo comes in gently under the nozzle
    halo = np.exp(-(u / 1.9) ** 2) * np.clip(1.0 - sc, 0.0, 1.0) * 0.75 * soft
    rgb = _colour(key, np.clip(np.maximum(temp, halo * 0.65) * 0.98, 0.0, 1.0))
    fade = np.clip(1.0 - sc, 0.0, 1.0) ** 0.8                  # the end of the jet is a fade, not a point
    alpha = np.maximum(np.clip(radial * 2.2, 0.0, 1.0) ** 0.8 * fade ** 0.6, halo * 0.55)
    alpha = np.where(s < 0, 0.0, alpha)
    rgba = np.dstack([rgb, alpha * 255.0]).astype(np.uint8)
    if ss == 1:
        small = rgba
    else:
        # shrink by the mean of each block of ss x ss pictures points (colours weighted by their opacity: no dark fringe)
        block = rgba.reshape(height, ss, width, ss, 4).astype(np.float32)
        a = block[..., 3]
        wsum = np.maximum(a.sum(axis=(1, 3)), 1e-3)
        col = (block[..., :3] * a[..., None]).sum(axis=(1, 3)) / wsum[..., None]
        small = np.dstack([col, a.mean(axis=(1, 3))]).astype(np.uint8)
    return small


def cell_size(kind):
    """Size (width, height) of one picture of the film of a kind of jet."""
    spec = NOZZLES[kind]
    return int(spec["half"] * 2 * 3.2) | 1, int(spec["length"] + 8)


def render_strip(kind, key):
    """The whole film of a jet as one picture: FRAMES cells side by side (what tools/make_engine_flames.py saves)."""
    spec = NOZZLES[kind]
    cw, ch = cell_size(kind)
    strip = pygame.Surface((cw * FRAMES, ch), pygame.SRCALPHA, 32)
    for i in range(FRAMES):
        arr = _frame(key, spec["half"], spec["length"], LOOP_SEC * i / FRAMES)
        strip.blit(pygame.image.frombuffer(arr.tobytes(), (cw, ch), "RGBA"), (i * cw, 0))
    return strip


def strip_path(kind, key):
    name = key if key.startswith(kind + "_") else "%s_%s" % (kind, key)       # phenix_red, phenix_blue / phoenix_argent...
    return asset_path("sprites", "engines", name + ".png")


_films = {}                  # (kind, colour key) -> list of FRAMES pictures, or None when it could not be made


def _cut(strip, kind):
    cw, ch = cell_size(kind)
    if strip.get_size() != (cw * FRAMES, ch):
        raise ValueError("engine flame picture has the wrong size: %s" % (strip.get_size(),))
    return [strip.subsurface((i * cw, 0, cw, ch)).copy() for i in range(FRAMES)]


def film(kind, key):
    """The loop of pictures of a jet (made once), or None."""
    k = (kind, key)
    if k not in _films:
        pics = None
        try:
            path = strip_path(kind, key)
            if os.path.isfile(path):
                pics = _cut(pygame.image.load(path), kind)
        except Exception:
            log_exc("engine_flame.film(load)")
        try:
            if pics is None:
                pics = _cut(render_strip(kind, key), kind)
            try:
                pics = [p.convert_alpha() for p in pics]
            except Exception:
                pass                                           # (no display yet: the pictures are drawn as they are)
            _films[k] = pics
        except Exception:
            log_exc("engine_flame.film")
            _films[k] = None
    return _films[k]


def prepare(kind, palette):
    """Make the film now (a few milliseconds): so that nothing is built in the middle of a mission."""
    return film(kind, ramp_key(kind, palette)) is not None


def draw(surface, kind, palette, x, y, thrust, clock, engine=0, size=1.0, flicker=True, burst=0.0):
    """One jet whose nozzle is at (x, y) on `surface`.

    `thrust` 0..1 (how hard the ship pushes), `clock` the time in seconds, `engine` the number of the nozzle (two nozzles do
    not show the same picture at the same moment), `size` scales the whole jet (a ship that grows or shrinks), `burst` 0..1 the
    flight up to the next stage (longer jet, a little wider).
    """
    if thrust < SHOW_FROM:
        return False
    pics = film(kind, ramp_key(kind, palette))
    if not pics:
        return False
    thrust = min(1.0, float(thrust))
    pic = pics[(int(clock * FRAMES / LOOP_SEC) + engine * (FRAMES // 3)) % FRAMES]
    # the jet flickers a little in length (it is longer when the ship pushes and shorter when it idles)
    wobble = 1.0
    if flicker:
        wobble = (0.88 + 0.12 * math.sin(clock * 27.0)) * (0.93 + 0.07 * math.sin(clock * 19.0 + engine * 2.1))
    burst = max(0.0, min(1.0, float(burst)))
    sx = (MIN_WIDTH + (1.0 - MIN_WIDTH) * thrust) * size * (1.0 + (BURST_WIDTH - 1.0) * burst)
    sy = (MIN_LENGTH + (1.0 - MIN_LENGTH) * thrust) * wobble * size * (1.0 + (BURST_LENGTH - 1.0) * burst)
    w = max(1, int(round(pic.get_width() * sx)))
    h = max(1, int(round(pic.get_height() * sy)))
    if (w, h) != pic.get_size():
        pic = pygame.transform.smoothscale(pic, (w, h))
    surface.blit(pic, (int(round(x - w / 2.0)), int(round(y - 1))))
    return True
