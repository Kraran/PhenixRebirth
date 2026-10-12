"""The return to base by the quantum anchor, shown when a mission is lost (Normal mode).

The Shield-NX01 is destroyed and its quantum double appears again at the base, with its pilot. On screen: the last picture of
the mission turns into a whirlwind, faster and faster towards the middle, and is drawn into it, shrinking to a point
(SWIRL_SEC); the point opens in a flash (FLASH_SEC); the flash fades and the mission map is back under it (FADE_SEC).

The vortex is made from the last picture of the mission, on a smaller canvas (RENDER) that is scaled up, so it costs a few
milliseconds a frame: each pixel of the result takes the colour of the pixel of the picture that the vortex has carried to
it. The picture of the mission is shown as it was for the first few frames (BLEND_SEC), so the effect starts without a jump.
Needs numpy (without it `make` gives None and the game goes back to the map at once, as it did).

It is a vortex of space, not of colour: what is behind the picture is the colour of the scrolling background (COLOR_BG),
with stars of the scrolling's own colours that the vortex draws in (each one leaves a short curved trail, the faster the
nearer to the middle), and the light of the middle and the flash are white, not blue.
"""
import math
import random

import pygame

from settings import COLOR_BG

try:
    import numpy as np
except ImportError:          # pragma: no cover - exercised by a test that hides numpy
    np = None

SWIRL_SEC = 1.6              # the picture turns and is drawn into the middle
FLASH_SEC = 0.30             # the point opens in a flash
FADE_SEC = 0.90              # the flash fades, the map is back
TOTAL_SEC = SWIRL_SEC + FLASH_SEC + FADE_SEC
BLEND_SEC = 0.15             # at the start the real picture shows through, so nothing jumps
SHRINK = 3.2                 # the picture is divided in size by exp(SHRINK * progress ** SHRINK_POW) at the end
SHRINK_POW = 1.8
TWIST = 14.0                 # radians of turn of the middle at the end (the outside turns less)
RENDER = (400, 225)          # size of the canvas the vortex is calculated on
LUT_SIZE = 1024
SPACE = COLOR_BG             # what is behind the picture: the colour of the scrolling background
GLOW_COLOUR = (255, 246, 228)   # the light of the middle
FLASH_COLOUR = (255, 250, 240)
STARS = 500                  # stars drawn into the vortex
STAR_REACH = 2.2             # the farthest star starts this many times farther than the corner of the screen
STAR_SEED = 7                # the stars are always the same ones (and the game's random numbers are not used)
TRAIL_FROM, TRAIL_TO = 0.008, 0.030      # how far back in the swirl (0..1) the trail of a star reaches, at the start / at the end
# the colours of the stars of the scrolling (src/starfield.py), far / middle / near layer, and the size of their dot
STAR_COLOURS = (
    ((40, 60, 140), (50, 70, 160), (30, 50, 120), (60, 80, 180)),
    ((80, 120, 220), (100, 140, 255), (70, 100, 200), (120, 160, 255)),
    ((160, 190, 255), (200, 220, 255), (140, 180, 255), (180, 210, 255)),
)
STAR_SIZES = (1, 2, 3)
CAPTION_FROM = 0.45          # the legend comes in between these two moments of the swirl
CAPTION_FULL = 0.70


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


class AnchorReturn:
    def __init__(self, snapshot, title=None, sub=None, render=RENDER):
        """`snapshot`: the last picture of the mission (a Surface of the size of the game canvas). `title` and `sub`:
        the two lines of the legend, already drawn (Surfaces), or None."""
        self.t = 0.0
        self.size = snapshot.get_size()
        self.sharp = snapshot.copy()
        w, h = render
        self.render = (w, h)
        small = pygame.transform.smoothscale(snapshot.convert(24) if snapshot.get_bitsize() != 24 else snapshot, (w, h))
        base = pygame.surfarray.array3d(small).astype(np.float32)             # (w, h, 3)
        self.mips = [base]
        while min(self.mips[-1].shape[0], self.mips[-1].shape[1]) >= 8 and len(self.mips) < 5:
            m = self.mips[-1]
            mw, mh = m.shape[0] // 2 * 2, m.shape[1] // 2 * 2
            self.mips.append(m[:mw, :mh].reshape(mw // 2, 2, mh // 2, 2, 3).mean(axis=(1, 3)))
        self.cx, self.cy = (w - 1) / 2.0, (h - 1) / 2.0
        x, y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32), indexing="ij")
        self.dx, self.dy = x - self.cx, y - self.cy
        r = np.hypot(self.dx, self.dy)
        self.far = float(math.hypot(w, h) / 2.0)                              # the corner is this far from the middle
        # Most of what the vortex does depends only on the distance from the middle: it is calculated for LUT_SIZE distances
        # each frame and looked up for each pixel (a lookup costs far less than a cosine)
        self.rings = np.linspace(0.0, self.far, LUT_SIZE).astype(np.float32)
        self.ring_of = np.clip(np.rint(r / self.far * (LUT_SIZE - 1)), 0, LUT_SIZE - 1).astype(np.int32)
        self._make_stars()
        self.title = title.copy() if title is not None else None
        self.sub = sub.copy() if sub is not None else None
        self._veil = pygame.Surface(self.size)
        self._veil.fill(FLASH_COLOUR)

    # --- time ---
    @property
    def done(self):
        return self.t >= TOTAL_SEC

    @property
    def phase(self):
        """"swirl", "flash" or "fade" (then "done")."""
        if self.t < SWIRL_SEC:
            return "swirl"
        if self.t < SWIRL_SEC + FLASH_SEC:
            return "flash"
        return "fade" if self.t < TOTAL_SEC else "done"

    def update(self, dt):
        self.t += max(0.0, float(dt))

    def skip(self):
        """Go on to the end of the flash: the map comes back at once."""
        self.t = max(self.t, SWIRL_SEC + FLASH_SEC)

    # --- the picture ---
    def _layer(self, progress, flash=0.0):
        """The vortex of the render canvas as (colour, alpha): colour (width, height, 3) floats 0..255, alpha (width, height)
        0..1. Where alpha is 0 nothing of the picture is there (the space and its stars show through)."""
        p = max(0.0, min(1.0, float(progress)))
        far, ring, ring_of = self.far, self.rings, self.ring_of
        shrink = math.exp(SHRINK * p ** SHRINK_POW)                          # how many times the picture is smaller
        turn = TWIST * p * p / (1.0 + ring / (0.18 * far))                   # the middle turns much more than the outside
        cos_t, sin_t = np.cos(turn)[ring_of], np.sin(turn)[ring_of]
        level = int(max(0, min(len(self.mips) - 1, math.floor(math.log2(max(1.0, shrink))))))
        mip, k = self.mips[level], float(2 ** level)
        mw, mh = mip.shape[0], mip.shape[1]
        sk = shrink / k
        xi = np.rint(self.cx / k + sk * (self.dx * cos_t - self.dy * sin_t)).astype(np.int32)
        yi = np.rint(self.cy / k + sk * (self.dx * sin_t + self.dy * cos_t)).astype(np.int32)
        inside = (xi >= 0) & (xi < mw) & (yi >= 0) & (yi < mh)
        # What does not depend on the picture depends only on the distance from the middle: it is made for the LUT_SIZE
        # distances, then looked up for each pixel. The middle shines more and more (white): the picture and the stars
        # fade into it.
        u = p ** 1.2
        glow = np.exp(-(ring / (far * (0.04 + 0.22 * u * u))) ** 2) * (0.35 + 0.65 * u) * u
        space, white = np.array(SPACE, np.float32), np.array(GLOW_COLOUR, np.float32)
        lit = np.clip(glow * 8.0, 0.0, 1.0)[:, None]                         # outside the picture: from space to white at once
        ring_colour = space + lit * (white - space)                          # (LUT_SIZE, 3): the colour of space at each distance
        ring_alpha = glow.astype(np.float32)
        f = max(0.0, min(1.0, float(flash)))
        if f > 0.0:
            reach = 1.3 * far * f ** 1.3
            cover = np.clip((reach - ring) / (0.25 * far), 0.0, 1.0).astype(np.float32)
        colour = ring_colour[ring_of]                                        # space everywhere ...
        alpha = ring_alpha[ring_of]
        flat = np.clip(xi, 0, mw - 1) * mh + np.clip(yi, 0, mh - 1)
        img = np.take(mip.reshape(-1, 3), flat[inside], axis=0)              # ... and the picture where it is
        g = ring_alpha[ring_of[inside]][:, None]
        colour[inside] = img + g * (white - img)
        alpha[inside] = 1.0
        if f > 0.0:
            c = cover[ring_of]
            colour += c[..., None] * (np.array(FLASH_COLOUR, np.float32) - colour)
            alpha += (1.0 - alpha) * c
        return colour, alpha

    def vortex(self, progress, flash=0.0):
        """The vortex (without the stars) as an array (width, height, 3) of the render canvas, over the colour of space:
        `progress` 0..1 of the swirl, `flash` 0..1 of the flash that opens from the middle."""
        colour, alpha = self._layer(progress, flash)
        space = np.array(SPACE, np.float32)
        return np.clip(space + alpha[..., None] * (colour - space), 0, 255).astype(np.uint8)

    # --- the stars ---
    def _make_stars(self):
        """The stars the vortex draws in: always the same (a generator of their own), spread over a disc wider than the screen."""
        rng = random.Random(STAR_SEED)
        w, h = self.size
        self.star_far = math.hypot(w, h) / 2.0
        layer = np.array([rng.choice((0, 0, 0, 1, 1, 2)) for _ in range(STARS)], np.int32)
        self.star_r0 = np.array([self.star_far * STAR_REACH * math.sqrt(rng.random()) + 20.0 for _ in range(STARS)], np.float32)
        self.star_a0 = np.array([rng.uniform(0.0, 2.0 * math.pi) for _ in range(STARS)], np.float32)
        self.star_depth = np.array([rng.uniform(0.75, 1.25) for _ in range(STARS)], np.float32)   # far ones fall in slower
        self.star_layer = layer
        self.star_colour = np.array([rng.choice(STAR_COLOURS[int(l)]) for l in layer], np.float32)
        self.star_size = np.array([STAR_SIZES[int(l)] for l in layer], np.int32)

    def _star_xy(self, p):
        """Where every star is at `p` (0..1 of the swirl): drawn in with the picture (same shrinking, same turn)."""
        shrink = math.exp(SHRINK * p ** SHRINK_POW)
        r = self.star_r0 / np.power(shrink, self.star_depth)
        a = self.star_a0 - TWIST * p * p / (1.0 + r / (0.18 * self.star_far))
        return self.size[0] / 2.0 + r * np.cos(a), self.size[1] / 2.0 + r * np.sin(a), r

    def _draw_stars(self, surface, p):
        w, h = self.size
        dp = TRAIL_FROM + (TRAIL_TO - TRAIL_FROM) * p
        x, y, r = self._star_xy(p)
        idx = np.nonzero((x > -30) & (x < w + 30) & (y > -30) & (y < h + 30))[0]
        if idx.size == 0:
            return
        k = 0.45 + 0.55 * np.minimum(1.0, r[idx] / (0.5 * self.star_far))
        light = np.clip(self.star_colour[idx] * (0.5 + 0.5 * k)[:, None] + 40.0 * self.star_layer[idx][:, None] * p ** 1.2,
                        0, 255).astype(np.int32).tolist()
        size = self.star_size[idx].tolist()
        xs, ys = x[idx], y[idx]
        head = list(zip(xs.tolist(), ys.tolist()))
        trails = None
        if p > 0.02:                                       # the trail: four points on the way the star came by
            back = [self._star_xy(max(0.0, p - dp * f)) for f in (1.0, 0.66, 0.33)]
            trails = [list(zip(b[0][idx].tolist(), b[1][idx].tolist())) for b in back]
        lines, circle, put = pygame.draw.lines, pygame.draw.circle, surface.set_at
        for n in range(len(head)):
            col, sz, (px, py) = tuple(light[n]), size[n], head[n]
            if trails is not None:
                (bx, by) = trails[0][n]
                if abs(bx - px) + abs(by - py) > 1.5:
                    lines(surface, col, False, [(bx, by), trails[1][n], trails[2][n], (px, py)], max(1, sz - (1 if sz > 2 else 0)))
            if sz >= 2:
                circle(surface, col, (int(px), int(py)), sz - 1 if sz > 2 else 1)
            else:
                put((int(px), int(py)), col)

    def _picture_layer(self, p, q):
        """The vortex of the picture, with its transparency, at the size of the canvas (a Surface)."""
        colour, alpha = self._layer(p, q)
        small = pygame.surfarray.make_surface(np.clip(colour, 0, 255).astype(np.uint8)).convert_alpha()
        pygame.surfarray.pixels_alpha(small)[:] = np.clip(alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)
        return pygame.transform.smoothscale(small, self.size)

    def draw(self, surface):
        """The effect over `surface` (the canvas of the game). While the map is coming back, the map must already be drawn on
        `surface`: the flash fades over it."""
        t = self.t
        if t < SWIRL_SEC + FLASH_SEC:
            p = min(1.0, t / SWIRL_SEC)
            q = max(0.0, (t - SWIRL_SEC) / FLASH_SEC)
            surface.fill(SPACE)                           # the whole canvas is painted over: space, its stars, the picture
            self._draw_stars(surface, p)
            big = self._picture_layer(p, q)
            if t < BLEND_SEC:
                surface.blit(self.sharp, (0, 0))
                big.set_alpha(int(255 * t / BLEND_SEC))
            surface.blit(big, (0, 0))
            self._caption(surface, p, q)
        elif t < TOTAL_SEC:
            q = (t - SWIRL_SEC - FLASH_SEC) / FADE_SEC
            self._veil.set_alpha(int(round(255 * (1.0 - _smooth(q)))))
            surface.blit(self._veil, (0, 0))

    def _caption(self, surface, p, q):
        alpha = _smooth((p - CAPTION_FROM) / (CAPTION_FULL - CAPTION_FROM)) * (1.0 - _smooth(q * 1.4))
        if alpha <= 0.01:
            return
        cx, cy = self.size[0] // 2, self.size[1] // 2
        y = cy - 70
        for line in (self.title, self.sub):
            if line is None:
                continue
            line.set_alpha(int(255 * alpha))
            surface.blit(line, (cx - line.get_width() // 2, y))
            y += line.get_height() + 8


def make(snapshot, title=None, sub=None):
    """The effect for the last picture `snapshot` of a mission, or None when it cannot be made (no numpy, no picture)."""
    if np is None or snapshot is None:
        return None
    try:
        return AnchorReturn(snapshot, title, sub)
    except Exception:
        from errlog import log_exc
        log_exc("anchor_fx.make")
        return None
