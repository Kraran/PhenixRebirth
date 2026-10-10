"""The return to base by the quantum anchor, shown when a mission is lost (Normal mode).

The Shield-NX01 is destroyed and its quantum double appears again at the base, with its pilot. On screen: the last picture of
the mission turns into a whirlwind, faster and faster towards the middle, and is drawn into it, shrinking to a point
(SWIRL_SEC); the point opens in a flash (FLASH_SEC); the flash fades and the mission map is back under it (FADE_SEC).

The vortex is made from the last picture of the mission, on a smaller canvas (RENDER) that is scaled up, so it costs a few
milliseconds a frame: each pixel of the result takes the colour of the pixel of the picture that the vortex has carried to
it. The picture of the mission is shown as it was for the first few frames (BLEND_SEC), so the effect starts without a jump.
Needs numpy (without it `make` gives None and the game goes back to the map at once, as it did).
"""
import math

import pygame

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
SPACE = (6, 10, 30)          # what is behind the picture
FLASH_COLOUR = (225, 245, 255)
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
        theta = np.arctan2(self.dy, self.dx)
        self.far = float(math.hypot(w, h) / 2.0)                              # the corner is this far from the middle
        # Most of what the vortex does depends only on the distance from the middle: it is calculated for LUT_SIZE distances
        # each frame and looked up for each pixel (a lookup costs far less than a cosine)
        self.rings = np.linspace(0.0, self.far, LUT_SIZE).astype(np.float32)
        self.ring_of = np.clip(np.rint(r / self.far * (LUT_SIZE - 1)), 0, LUT_SIZE - 1).astype(np.int32)
        self.cos3, self.sin3 = np.cos(3.0 * theta), np.sin(3.0 * theta)
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
    def vortex(self, progress, flash=0.0):
        """The vortex as an array (width, height, 3) of the render canvas: `progress` 0..1 of the swirl, `flash` 0..1 of the
        flash that opens from the middle."""
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
        flat = np.clip(xi, 0, mw - 1) * mh + np.clip(yi, 0, mh - 1)
        img = np.take(mip.reshape(-1, 3), flat, axis=0)
        u = p ** 1.2
        img = img.reshape(inside.shape + (3,))
        img *= np.array((1.0 - 0.55 * u, 1.0 - 0.25 * u, 1.0), np.float32)
        img += u * np.array((4.0, 10.0, 22.0), np.float32)
        out = np.where(inside[..., None], img, np.array(SPACE, np.float32))
        # behind the picture there are arms of light that turn with the vortex: cos(3 theta + c(r)), c depends on r only
        c = 3.0 * 0.6 * turn - 0.045 * ring + 6.0 * p
        arms = 0.5 + 0.5 * (self.cos3 * np.cos(c)[ring_of] - self.sin3 * np.sin(c)[ring_of])
        arms *= np.clip(1.0 - 0.7 * ring / far, 0.0, 1.0)[ring_of]
        arms *= u
        arms[inside] = 0.0
        out += arms[..., None] * np.array((30.0, 80.0, 170.0), np.float32)
        # the middle shines more and more
        glow = (np.exp(-(ring / (far * (0.04 + 0.22 * u * u))) ** 2) * (0.35 + 0.65 * u) * u)[ring_of]
        out += glow[..., None] * np.array((160.0, 215.0, 255.0), np.float32)
        f = max(0.0, min(1.0, float(flash)))
        if f > 0.0:
            reach = 1.3 * far * f ** 1.3
            cover = np.clip((reach - ring) / (0.25 * far), 0.0, 1.0)[ring_of][..., None]
            out = out * (1.0 - cover) + np.array(FLASH_COLOUR, np.float32) * cover
        return np.clip(out, 0, 255).astype(np.uint8)

    def draw(self, surface):
        """The effect over `surface` (the canvas of the game). While the map is coming back, the map must already be drawn on
        `surface`: the flash fades over it."""
        t = self.t
        if t < SWIRL_SEC + FLASH_SEC:
            p = min(1.0, t / SWIRL_SEC)
            q = max(0.0, (t - SWIRL_SEC) / FLASH_SEC)
            small = pygame.surfarray.make_surface(self.vortex(p, q))
            big = pygame.transform.smoothscale(small, self.size)
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
