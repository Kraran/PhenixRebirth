"""What the player sees in the Lunar Lander level (src/lander.py): the sky, the ground (a texture of the body, lit from the
upper left, darker with the depth), the landing zones and the HUD. The ship itself is drawn by the Player, in the middle.

Five bodies (lander.BODIES): the asteroid, Titan, Europa, Deimos and Triton, each with its own texture of ground, its sky and
its mother planet in the sky (Saturn, Jupiter, Mars, Neptune; the other asteroids for the asteroid), made from what the real
places look like. Everything heavy is made once per body: the sky and the two tiles of texture of the ground. A frame only slides and scales
those tiles, cuts the ground out of them with the polygon of the relief and lays the light on its edge.
"""
import math
import threading

import numpy as np
import pygame
import loading

import announce
import lander
from settings import BASE_HEIGHT, BASE_WIDTH, asset_path

W, H = BASE_WIDTH, BASE_HEIGHT
CX, CY = W / 2.0, H / 2.0
COLUMN = 8.0                                # one point of the relief every COLUMN px OF THE WORLD (the points follow the ground, not the screen: a peak never blinks)
TILES = ((1024, 1024), (768, 768))          # (texture size in px, size of the tile in the world in px)
CHUNK = 160                                 # width of the chunks of columns of the ground
ZQ = 256                                    # the zoom drawn is a multiple of 1/ZQ: the tiles (1024 and 768 world px) then have a whole size
HUD_COLOR = (120, 235, 255)
_CACHE = {}                                 # per body: sky, textures
_LOCK = threading.RLock()                   # (a body is made once, by whoever asks first: the menu or the background)
WARM_UP = True                              # the menu makes the pictures of the other settings in the background (off in the tests)
_warming = False
# What differs from one body to the next: the sky ("haze": the orange sky of Titan, "stars": black with stars), the seed of the
# textures, the colour of the boulders and of the lit edge of the ground.
LOOKS = {
    "ice": {"sky": "haze", "seed": 11, "plain": (150, 120, 92), "lip": (255, 232, 200)},
    "rock": {"sky": "stars", "seed": 23, "plain": (92, 90, 86), "lip": (205, 205, 200)},
    "europa": {"sky": "stars", "seed": 31, "plain": (206, 200, 192), "lip": (248, 250, 255)},
    "deimos": {"sky": "stars", "seed": 47, "plain": (84, 74, 66), "lip": (200, 182, 160)},
    "triton": {"sky": "stars", "seed": 59, "plain": (196, 164, 160), "lip": (255, 228, 226)},
}
GLOW = {"saturn": (200, 160, 100), "jupiter": (190, 165, 130), "mars": (190, 100, 60), "neptune": (50, 100, 220)}   # the halo of each
PLANET_DRAW = {                             # the mother planet: (width of its picture in px, where, tint, the share of its light kept,
    "saturn": (640, (900, 200), (255, 196, 140), 0.78, 0.22),   # the radius of the disc in widths of the picture: Saturn has its rings)
    "jupiter": (600, (330, 190), (255, 255, 255), 1.0, 0.5),    # (Saturn is seen through the orange haze of Titan)
    "mars": (380, (930, 210), (255, 255, 255), 1.0, 0.5),
    "neptune": (430, (320, 200), (255, 255, 255), 1.0, 0.5),
}


# ------------------------------------------------------------------ textures (made once)
def _octave(size, cells, rng):
    lattice = rng.random((cells, cells))
    t = np.arange(size) * cells / float(size)
    i = np.floor(t).astype(int)
    f = t - i
    f = f * f * (3 - 2 * f)
    j = (i + 1) % cells
    # the same bilinear blend, but along x first on the `cells` rows of the lattice only (small), then along y: two big gathers
    # instead of four, a third of the work
    across = lattice[:, i] * (1 - f)[None, :] + lattice[:, j] * f[None, :]
    return across[i] * (1 - f)[:, None] + across[j] * f[:, None]


def _fbm(size, base, octaves, rng):
    """A noise that loops on all four sides (value noise on a looping lattice)."""
    total, amp, norm = np.zeros((size, size)), 1.0, 0.0
    for o in range(octaves):
        total += amp * _octave(size, base * (2 ** o), rng)
        loading.report()
        norm += amp
        amp *= 0.5
    return total / norm


def _mix(a, b, k):
    """a * (1 - k) + b * k, with k a field (size, size) and a, b colours or fields."""
    k = np.asarray(k)[..., None]
    return a * (1 - k) + np.asarray(b, dtype=float) * k


def _worley(size, count, rng):
    """The distance to the nearest (f1) and the second nearest (f2) of `count` random points, on a torus, in units of the
    mean distance between points: the cells of a cantaloupe."""
    pts = rng.random((count, 2)) * size
    # the squared distances, from the two small 1-D tables of each point (a torus distance in x and in y): one add and three
    # min/max per point instead of a dozen operations on whole fields; the square roots are taken once at the end
    line = np.arange(size, dtype=np.float32)
    f1 = np.full((size, size), 1e18, dtype=np.float32)
    f2 = f1.copy()
    d = np.empty_like(f1)
    tmp = np.empty_like(f1)
    for px, py in pts:
        dx = np.abs(line - np.float32(px))
        dx = np.minimum(dx, size - dx) ** 2
        dy = np.abs(line - np.float32(py))
        dy = np.minimum(dy, size - dy) ** 2
        np.add(dy[:, None], dx[None, :], out=d)
        np.maximum(f1, d, out=tmp)
        np.minimum(f2, tmp, out=f2)
        np.minimum(f1, d, out=f1)
    f1, f2 = np.sqrt(f1), np.sqrt(f2)
    unit = size / math.sqrt(count)
    return f1 / unit, f2 / unit


def _craters(size, count, r_lo, r_hi, rng):
    """The light of `count` craters laid on a looping tile: (size, size) around 0 (positive on the rim that faces the light
    from the upper left, negative inside, on the far side of the bowl)."""
    height = np.zeros((size, size))
    for _ in range(count):
        cx, cy = int(rng.integers(0, size)), int(rng.integers(0, size))
        r = float(rng.uniform(r_lo, r_hi)) * float(rng.uniform(0.5, 1.0)) ** 0.5
        reach = int(r * 1.5) + 2
        iy, ix = np.arange(cy - reach, cy + reach + 1), np.arange(cx - reach, cx + reach + 1)
        d = np.hypot(ix[None, :] - cx, iy[:, None] - cy) / r
        bowl = -np.clip(1 - d * d, 0, 1) * 0.55
        rim = 0.32 * np.exp(-(((d - 1.0) / 0.16) ** 2))
        height[np.ix_(iy % size, ix % size)] += bowl + rim
    return (height - np.roll(np.roll(height, 2, 0), 2, 1)) * 5.0


def _smear(field, steps, shift, axis):
    """A field stretched along an axis (the mean of itself shifted: streaks)."""
    out = np.zeros_like(field)
    for k in range(steps):
        out += np.roll(field, k * shift, axis)
    return out / steps


def _texture(style, size, seed):
    rng = np.random.default_rng(seed)
    big = _fbm(size, 3, 4, rng)
    mid = _fbm(size, 10, 4, rng)
    fine = _fbm(size, 48, 3, rng)
    if style == "ice":
        pale, tan, dark = np.array([212, 205, 190.0]), np.array([178, 128, 82.0]), np.array([74, 52, 40.0])
        col = tan * (1 - big[..., None]) + pale * big[..., None]
        shade = np.clip(mid - 0.5, 0, 1)[..., None] * 2
        col = col * (1 - 0.3 * shade) + dark * (0.3 * shade)
        crack = np.abs(_fbm(size, 9, 4, rng) - 0.5)                         # fine cracks in the crust
        col = col * (1 - 0.28 * (crack < 0.008)[..., None])
        col = col * (0.88 + 0.22 * fine[..., None])
    elif style == "europa":
        # Europa: a bright ice, white with a blue-grey tinge, crossed by long ridges and fractures of a reddish brown (the
        # "lineae" of the photographs of Galileo), with mottled patches of a darker tan (the chaos terrain)
        cream, blue = np.array([236, 232, 222.0]), np.array([206, 218, 232.0])
        col = _mix(cream, blue, big)
        brown, tan = np.array([150, 86, 58.0]), np.array([186, 146, 116.0])
        # the lineae: long straight fractures that cross each other (a line of a whole direction (a, b) comes round on the
        # tile), a little bent by a slow wave, each with its dark reddish stain and its fine pale core
        ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
        bend = ((_fbm(size, 4, 2, rng) - 0.5) * 40.0).astype(np.float32)
        dirs = [(1, 0), (0, 1), (1, 1), (1, -1), (1, 2), (2, 1), (1, -2), (2, -1), (3, 1), (1, 3), (3, -1), (1, -3)]
        wide, core = np.zeros((size, size)), np.zeros((size, size))
        big_n, thin_n = (7, 4) if size >= 1000 else (3, 3)                   # (the second tile, fainter, has fewer)
        for k in range(big_n + thin_n):
            a_, b_ = dirs[int(rng.integers(0, len(dirs)))]
            x0, y0 = float(rng.uniform(0, size)), float(rng.uniform(0, size))
            f = (-b_ * (xs - x0) + a_ * (ys - y0)) + bend * float(rng.uniform(0.6, 1.4))
            dist = np.abs((f + size / 2.0) % size - size / 2.0) / math.hypot(a_, b_)
            w = float(rng.uniform(3.0, 9.0)) * (1.5 if k < big_n else 1.0)
            wide = np.maximum(wide, np.clip(1 - dist / (w * 4.5), 0, 1) ** 2 * (0.45 if k < big_n else 0.18))
            core = np.maximum(core, np.clip(1 - dist / w, 0, 1) * (0.85 if k < big_n else 0.55))
        col = _mix(col, brown, wide)
        col = _mix(col, np.array([120, 66, 46.0]), core)
        col = _mix(col, np.array([226, 214, 200.0]), 0.5 * np.clip(1 - (core > 0.5) * 0 - np.abs(core - 0.95) / 0.05, 0, 1) * (core > 0.85))
        chaos = np.clip((mid - 0.56) / 0.1, 0, 1)
        col = _mix(col, tan, 0.65 * chaos)
        col = col * (0.9 + 0.2 * fine[..., None]) * (1 - 0.12 * chaos[..., None] * (fine[..., None] - 0.4))
    elif style == "deimos":
        # Deimos: a dark brown-grey rock blanketed with dust, smooth and soft; lighter streaks of dust slide down the slopes
        dark, light = np.array([66, 58, 52.0]), np.array([126, 112, 99.0])
        col = _mix(dark, light, big * 0.9 + mid * 0.1)
        streak = _smear(_fbm(size, 22, 2, rng), 12, 3, 0)
        col = col * (1 + 0.55 * (streak[..., None] - 0.5))
        col = col * (0.92 + 0.16 * fine[..., None])
        dust = np.clip((mid - 0.55) / 0.12, 0, 1)                            # patches of finer, redder dust
        col = _mix(col, np.array([112, 92, 76.0]), 0.35 * dust)
        crat = _craters(size, 46 if size >= 1000 else 30, 16, 110, rng)             # (soft, worn craters: the dust fills them)
        col = col * (1 + 0.55 * np.clip(crat, -0.6, 0.6)[..., None])
    elif style == "triton":
        # Triton: a nitrogen ice of a pinkish cream, in the cells and the ridges of the "cantaloupe" terrain, with dark
        # streaks left by the geysers, all stretched the same way by the wind
        cells = 110 if size >= 1000 else 150
        f1, f2 = _worley(size, cells, rng)
        edge = np.clip(1 - (f2 - f1) / 0.22, 0, 1)
        cream, pink = np.array([236, 214, 200.0]), np.array([214, 168, 166.0])
        col = _mix(cream, pink, big * 0.8 + mid * 0.2)
        col = col * (0.86 + 0.2 * (1 - np.clip(f1, 0, 1.2) / 1.2)[..., None])        # each cell a little dimple
        col = _mix(col, np.array([112, 90, 108.0]), 0.7 * edge)                      # the ridges between them
        bump = (f1 - np.roll(np.roll(f1, 3, 0), 3, 1)) * -6.0                         # each cell a bowl lit from the upper left
        col = col * (1 + 0.5 * np.clip(bump, -0.5, 0.5)[..., None])
        streak = _smear(_fbm(size, 16, 3, rng), 14, 3, 1)
        dark = np.clip((streak - 0.52) / 0.08, 0, 1)
        col = _mix(col, np.array([66, 50, 52.0]), 0.55 * dark)
        col = col * (0.92 + 0.16 * fine[..., None])
    else:
        light, grey, dark = np.array([128, 124, 118.0]), np.array([88, 85, 81.0]), np.array([44, 43, 42.0])
        col = grey * (1 - big[..., None]) + light * big[..., None]
        shade = np.clip(mid - 0.5, 0, 1)[..., None] * 2
        col = col * (1 - 0.35 * shade) + dark * (0.35 * shade)
        col = col * (0.72 + 0.5 * fine[..., None] ** 1.2)
    emb = (big - np.roll(np.roll(big, 3, 0), 3, 1)) * 5.0                    # a little relief of the surface
    col = col * (1 + emb[..., None] * (0.25 if style == "rock" else 0.18))
    return pygame.surfarray.make_surface(np.clip(col, 0, 255).astype(np.uint8).swapaxes(0, 1)).convert()


def _sky(style):
    sky = pygame.Surface((W, H))
    if LOOKS[style]["sky"] == "haze":
        top, low = np.array([48, 26, 12.0]), np.array([205, 128, 58.0])
        k = (np.clip(np.arange(H) / (H * 0.95), 0, 1) ** 1.3)[:, None, None]
        arr = np.repeat(top + (low - top) * k, W, axis=1)
        pygame.surfarray.blit_array(sky, np.clip(arr, 0, 255).astype(np.uint8).swapaxes(0, 1))
    else:
        sky.fill((2, 2, 5))
    return sky


def _stars(sky):
    """The sky of a body without air (one flat colour) with its stars, as one opaque picture (an opaque blit is much faster)."""
    rng = np.random.default_rng(4)
    layer = sky.copy()
    for _ in range(300):
        x, y = int(rng.integers(0, W)), int(rng.integers(0, H))
        v = int(rng.uniform(70, 255))
        layer.set_at((x, y), (v, v, min(255, int(v * 1.05))))
        if rng.random() < 0.08:
            layer.set_at(((x + 1) % W, y), (v, v, v))
    return layer


def _planet_picture(name, width, tint=(255, 255, 255), keep=1.0, disc=0.5):
    """The mother planet, from the photograph of the game (assets/sprites/planets/<name>.jpg: the planet on black), cut to its
    outline and scaled to `width` px, with a soft glow around it. The picture is on black: it is laid on the sky with an
    ADD blit, so the black disappears. `tint` and `keep` dim it (Saturn is seen through the haze of Titan)."""
    img = pygame.image.load(asset_path("sprites", "planets", name + ".jpg")).convert()
    arr = pygame.surfarray.array3d(img).max(axis=2)
    xs, ys = np.nonzero(arr > 14)
    box = pygame.Rect(int(xs.min()), int(ys.min()), int(xs.max() - xs.min()) + 1, int(ys.max() - ys.min()) + 1)
    crop = img.subsurface(box).copy()
    height = max(1, int(round(width * box.height / box.width)))
    crop = pygame.transform.smoothscale(crop, (int(width), height))
    pad = int(width * 0.22)
    canvas = pygame.Surface((int(width) + 2 * pad, height + 2 * pad))
    # the glow: a halo that fades out around the middle of the disc
    yy, xx = np.mgrid[0:canvas.get_height(), 0:canvas.get_width()].astype(np.float32)
    r = np.hypot(xx - canvas.get_width() / 2.0, yy - canvas.get_height() / 2.0) / (width * disc)
    glow = np.clip(1.0 - (r - 1.0) / 0.3, 0, 1) ** 2.5 * (r >= 1.0) * 0.45         # (only outside the disc)
    halo = np.stack([glow * c for c in GLOW.get(name, (70, 85, 120))], axis=2)
    pygame.surfarray.blit_array(canvas, np.clip(halo, 0, 255).astype(np.uint8).swapaxes(0, 1))
    canvas.blit(crop, (pad, pad), special_flags=pygame.BLEND_ADD)
    dim = pygame.Surface(canvas.get_size())
    dim.fill(tuple(int(c * keep) for c in tint))
    canvas.blit(dim, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    # the body of the planet, in black, to lay under it: the stars pass BEHIND the planet (the picture itself is ADDed, which
    # would let them shine through). Its opacity follows the light of the photograph (the rings of Saturn keep their gaps); a
    # round planet is filled to its whole disc, the dark side included.
    seen = pygame.surfarray.array3d(crop).max(axis=2).astype(np.float32).T          # (rows, columns)
    body = np.clip((seen - 6.0) / 26.0, 0.0, 1.0)
    if disc >= 0.5:
        cy, cx = (height - 1) / 2.0, (int(width) - 1) / 2.0
        yy2, xx2 = np.mgrid[0:height, 0:int(width)].astype(np.float32)
        body = np.maximum(body, np.clip((width * disc - 0.5 - np.hypot(xx2 - cx, yy2 - cy)) / 1.5, 0.0, 1.0))
    back = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
    back.fill((0, 0, 0, 0))
    alpha = np.zeros((canvas.get_width(), canvas.get_height()), dtype=np.uint8)
    alpha[pad:pad + int(width), pad:pad + height] = (body * 255).astype(np.uint8).T
    pygame.surfarray.pixels_alpha(back)[:] = alpha
    return canvas, back.convert_alpha()


def _asteroid_items():
    """Other asteroids in the sky of the asteroid: a few rocks of the game (assets/sprites/planets), turned and dimmed by their
    distance. (picture, x, y, parallax: how far it slides when the ship moves, in px)."""
    rng = np.random.default_rng(7)
    sources = [pygame.image.load(asset_path("sprites", "planets", n)).convert_alpha()
               for n in ("asteroid_pallas.png", "asteroid_dinkinesh.png")]
    plan = ((230, 0.9), (150, 0.8), (110, 0.7), (84, 0.65), (62, 0.55), (46, 0.5), (34, 0.45), (26, 0.42), (20, 0.4))
    items = []
    for i, (size, light) in enumerate(plan):
        img = sources[i % 2]
        k = size / float(max(img.get_size()))
        pic = pygame.transform.rotozoom(img, float(rng.uniform(0, 360)), k)
        shade = pygame.Surface(pic.get_size(), pygame.SRCALPHA)
        shade.fill((int(255 * light),) * 3 + (255,))
        pic.blit(shade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        x = float(rng.uniform(80, W - 80))
        y = float(rng.uniform(40, H * 0.62))
        items.append((pic, x, y, 40.0 + size * 0.6))
    return items


def assets(style):
    """The sky and the textures of a body (made the first time, then kept)."""
    got = _CACHE.get(style)
    if got is None:
        with _LOCK:
            got = _CACHE.get(style) or _make_assets(style)
    return got


def _make_assets(style):
    look = LOOKS[style]
    sky = _sky(style)
    planet = lander.BODIES[style]["planet"]
    mother = None
    if planet in PLANET_DRAW:
        width, pos, tint, keep, disc = PLANET_DRAW[planet]
        mother = _planet_picture(planet, width, tint, keep, disc) + (pos,)
    got = {
        "sky": sky,
        "stars": _stars(sky) if look["sky"] == "stars" else None,
        "tiles": [_texture(style, size, look["seed"] + k) for k, (size, _) in enumerate(TILES)],
        "planet": mother,                                    # (picture, its black body, where its middle is on the screen) or None
        "rocks": _asteroid_items() if planet == "asteroids" else [],
    }
    _CACHE[style] = got
    return got


PREVIEW_SIZE = (720, 405)
_PREVIEWS = {}


def preview(style):
    """A picture of a setting for the menu of the test (made once): the sky with its mother planet, a stretch of the ground and a
    landing zone, seen from the middle zoom."""
    pic = _PREVIEWS.get(style)
    if pic is None:
        with _LOCK:
            pic = _PREVIEWS.get(style) or _make_preview(style)
    return pic


def _make_preview(style):
    import random
    form = lander.LanderFormation(style=style, seed=5, rng=random.Random(1))
    form.view = View(style)
    pad = form.terrain.pads[0]
    form.x, form.y, form.zoom = pad["x"] - 120.0, pad["y"] - 330.0, 0.5
    full = pygame.Surface((W, H))
    form.view.draw(full, form)
    _PREVIEWS[style] = pygame.transform.smoothscale(full, PREVIEW_SIZE)
    return _PREVIEWS[style]


def warm(order):
    """Make the pictures of the menu (and with them the textures of the flight) in the background, in this order, while the
    player reads the first one: moving the cursor then costs nothing, and neither does the launch. Once per run."""
    global _warming
    if not WARM_UP or _warming:
        return None
    _warming = True

    def work():
        for style in order:
            try:
                preview(style)
            except Exception:                    # (the screen is closed: nothing to do)
                return

    thread = threading.Thread(target=work, name="lander-warm-up", daemon=True)
    thread.start()
    return thread


def snap_zoom(zoom):
    """The zoom as it is drawn: the nearest multiple of 1/ZQ (never 0)."""
    return max(1, int(round(zoom * ZQ))) / ZQ


def tile_origin(tw, z, cam_x, cam_y):
    """The screen (x, y) of the first tile that begins left of / above the screen, for tiles of `tw` px (their world square
    scaled by z): the tile n starts at CX + (n * world - cam_x) * z, so the texture slides at the very speed of the ground."""
    return int(round((CX - cam_x * z) % tw)) - tw, int(round((CY - cam_y * z) % tw)) - tw


def relief(terrain, z, cam_x, cam_y):
    """The points of the outline of the ground: (screen x, world x, height, screen y). They are fixed in the WORLD (every
    COLUMN px) and slide with the camera: sampled on a grid of the screen, a narrow peak slid between two samples and blinked
    as the ground scrolled."""
    k0 = int(math.floor((cam_x - CX / z) / COLUMN)) - 1
    k1 = int(math.ceil((cam_x + (W - CX) / z) / COLUMN)) + 1
    wx = np.arange(k0, k1 + 1, dtype=float) * COLUMN
    gy = terrain.ground(wx)
    return CX + (wx - cam_x) * z, wx, gy, CY + (gy - cam_y) * z


class View:
    """The picture of the level, kept from one frame to the next (the surfaces are reused)."""

    def __init__(self, style):
        self.style = style
        self.assets = assets(style)
        self.layer = pygame.Surface((W, H), pygame.SRCALPHA)
        self.mask = pygame.Surface((W, H), pygame.SRCALPHA)
        self.light = pygame.Surface((W, H), pygame.SRCALPHA)
        self.scaled = {}                                        # (tile, quantised zoom) -> the tile at that size
        self.fonts = {}
        self.depth_bars = [None] + [self._bar(255 - int(min(190, i * 9.0))) for i in range(1, 24)]     # the shade of each depth strip
        self.boulder_cols = {}                                  # id(terrain) -> (terrain, the colours of its boulders)
        self.slopes = {}                                        # id(terrain) -> the table of the light on its slopes

    @staticmethod
    def _bar(grey):
        bar = pygame.Surface((W, 104))
        bar.fill((grey, grey, grey))
        return bar

    # --- helpers
    def _tile(self, k, zoom):
        """The tile k at the zoom `zoom` (a value of snap_zoom): its size in px is EXACTLY the size of its world square at that
        zoom, so that the texture slides at the very speed of the ground."""
        q = max(1, int(round(zoom * ZQ)))
        key = (k, q)
        pic = self.scaled.get(key)
        if pic is None:
            if len(self.scaled) > 12:
                self.scaled.clear()
            size = TILES[k][1] * q // ZQ
            pic = pygame.transform.smoothscale(self.assets["tiles"][k], (size, size))
            self.scaled[key] = pic
        return pic

    def _font(self, size):
        f = self.fonts.get(size)
        if f is None:
            f = self.fonts[size] = pygame.font.SysFont("dejavusansmono", size, bold=True)
        return f

    # --- the picture
    def draw(self, surface, form):
        z, cam_x, cam_y = snap_zoom(form.zoom), form.x, form.y
        if self.assets["stars"] is not None:
            ox, oy = int(-cam_x * 0.03) % W, int(-cam_y * 0.03) % H
            for dx in (ox - W, ox):
                for dy in (oy - H, oy):
                    surface.blit(self.assets["stars"], (dx, dy))
        else:
            surface.blit(self.assets["sky"], (0, 0))
        self._mother(surface, cam_x, cam_y)
        if LOOKS[self.style]["sky"] == "haze":
            self._haze(surface, cam_x, cam_y, z)
        terrain = form.terrain
        sxs, wx, gy, sy = relief(terrain, z, cam_x, cam_y)
        if float(sy.min()) < H + 10:
            self._ground(surface, form, sxs, sy, wx, z, cam_x, cam_y)
        self._boulders(surface, terrain, z, cam_x, cam_y)
        self._pads(surface, form, z, cam_x, cam_y)

    def _mother(self, surface, cam_x, cam_y):
        """The mother planet in the sky (or the other asteroids). They slide a little when the ship moves (the nearer, the more),
        in a loop with the world so that nothing jumps when the ground comes round."""
        turn = math.sin(2 * math.pi * cam_x / lander.WORLD)
        rise = (cam_y - lander.START_Y) * 0.012                  # (they rise a little while the ship comes down)
        mother = self.assets["planet"]
        if mother is not None:
            pic, back, (px, py) = mother
            where = (round(px - pic.get_width() / 2 - 34 * turn), round(py - pic.get_height() / 2 - rise))
            if self.assets["stars"] is not None:
                surface.blit(back, where)                        # (the planet hides the stars behind it; Titan keeps its haze)
            surface.blit(pic, where, special_flags=pygame.BLEND_ADD)
        for pic, x, y, amp in self.assets["rocks"]:
            surface.blit(pic, (round(x - pic.get_width() / 2 - amp * turn), round(y - pic.get_height() / 2 - rise * amp / 60.0)))

    def _haze(self, surface, cam_x, cam_y, z):
        """Titan: two ranges of hills in the orange haze, far behind the ground."""
        for far, (col, k, hh) in enumerate((((150, 92, 45), 0.18, 140), ((112, 68, 34), 0.35, 110))):
            pts = [(0, H)]
            for sx in range(0, W + 16, 16):
                u = (cam_x * k + (sx - CX) * (0.6 + far * 0.2)) / (170.0 + far * 60)
                n = math.sin(u * 1.3 + far * 2.1) * 0.5 + math.sin(u * 3.1 + far) * 0.3 + math.sin(u * 7.3) * 0.15
                pts.append((sx, H * 0.70 + 55 * far + n * hh * 0.5 - (cam_y + 1750) * 0.04 * z))
            pts.append((W, H))
            pygame.draw.polygon(surface, col, pts)

    def _slope_table(self, terrain):
        """The light on each stretch of the ground (the stretch k runs from k * COLUMN to (k + 1) * COLUMN in the world), made
        once for the terrain: (alpha, lit) arrays. The slopes that face the light (upper left) are lit, the others fall in the
        dark; nearly flat stretches (alpha < 6) are not drawn."""
        tab = self.slopes.get(id(terrain))
        if tab is None or tab[2] is not terrain:
            n = int(round(lander.WORLD / COLUMN))
            g = terrain.ground(np.arange(n + 1, dtype=float) * COLUMN)
            facing = np.clip(0.5 - np.diff(g) / COLUMN * 1.15, 0.0, 1.0)
            k = (facing - 0.5) * 2.0
            lit = k > 0
            alpha = np.where(lit, (120 * k).astype(int), (150 * -k).astype(int))
            alpha[alpha < 6] = 0
            tab = self.slopes[id(terrain)] = (alpha, lit, terrain)
        return tab

    def _ground(self, surface, form, sxs, sy, wx, z, cam_x, cam_y):
        top = max(0, int(float(sy.min())) - 14)
        region = pygame.Rect(0, top, W, H - top)
        band_h = max(3.0, min(46.0, 34.0 * z))
        # under `edge` the ground is whole (the outline and the lit slopes are all above it): the work of the outline (light,
        # cut-out) is done on the band above it only
        edge = min(H, max(top, int(float(sy.max()) + band_h) + 4))
        band = pygame.Rect(0, top, W, edge - top)
        layer, mask, light = self.layer, self.mask, self.light
        # the ground is made by chunks of columns: above its outline a chunk has nothing to show (the cut-out would erase it), so
        # every chunk only works from where ITS outline begins (the picture is the same, the pixels thrown away are not made)
        sp = float(sxs[1] - sxs[0]) + 2.0 if len(sxs) > 1 else 2.0
        chunks = []
        for cx in range(0, W, CHUNK):
            near = sy[(sxs >= cx - sp) & (sxs <= cx + CHUNK + sp)]
            if not len(near):
                near = sy
            ctop = max(top, int(float(near.min())) - 14)
            chunks.append((pygame.Rect(cx, ctop, CHUNK, H - ctop), float(near.min()), float(near.max())))
        # the texture: two tiles of different sizes, slid and scaled with the world
        origins = []
        for k, (_, world) in enumerate(TILES):
            tile = self._tile(k, z)
            if k == 1:
                tile.set_alpha(110)
            origins.append((tile, tile.get_width()) + tuple(tile_origin(tile.get_width(), z, cam_x, cam_y)))
        # darker with the depth (world y): strips of a growing shade (a multiplication of the colours by a grey bar: the fast
        # blit of pygame)
        edges = [int(CY + (-520.0 + i * 100.0 - cam_y) * z) for i in range(25)]
        for rect, _, _ in chunks:
            layer.set_clip(rect)
            for tile, tw, x0, y0 in origins:
                yy = y0 + ((rect.top - y0) // tw) * tw          # the first tile that reaches the chunk
                x = x0 + ((rect.left - x0) // tw) * tw
                while yy < H:
                    xx = x
                    while xx < rect.right:
                        layer.blit(tile, (xx, yy))
                        xx += tw
                    yy += tw
            for i in range(1, 24):
                y0 = max(edges[i], rect.top)
                h = min(edges[i + 1], H) - y0
                if h > 0:
                    layer.blit(self.depth_bars[i], (rect.left, y0), (0, 0, rect.w, h), special_flags=pygame.BLEND_RGB_MULT)
        if band.height > 0:
            # light from the upper left, only on the band of the outline
            alpha, lit, _ = self._slope_table(form.terrain)
            n = len(alpha)
            first = int(round(float(wx[0]) / COLUMN))
            idx = (np.arange(len(sxs) - 1) + first) % n
            al = alpha[idx]
            xs, ys = sxs.tolist(), sy.tolist()
            light.set_clip(band)
            light.fill((0, 0, 0, 0))
            for i in np.nonzero(al)[0].tolist():
                colour = (255, 236, 205, int(al[i])) if lit[idx[i]] else (0, 0, 0, int(al[i]))
                x0, x1, y0, y1 = xs[i], xs[i + 1] + 1, ys[i], ys[i + 1]
                pygame.draw.polygon(light, colour, [(x0, y0), (x1, y1), (x1, y1 + band_h), (x0, y0 + band_h)])
            # cut the ground out
            mask.set_clip(band)
            mask.fill((0, 0, 0, 0))
            pts = list(zip(xs, ys)) + [(xs[-1], H + 4), (xs[0], H + 4)]
            pygame.draw.polygon(mask, (255, 255, 255, 255), pts)
            for rect, lo, hi in chunks:
                layer.set_clip(None)
                # the light only lies on the strip of the outline of the chunk; the cut-out on the band
                strip = pygame.Rect(rect.left, int(lo) - 2, rect.w, int(hi + band_h) - int(lo) + 6).clip(band)
                if strip.height > 0:
                    layer.blit(light, strip.topleft, strip)
                cut = rect.clip(band)
                if cut.height > 0:
                    layer.blit(mask, cut.topleft, cut, special_flags=pygame.BLEND_RGBA_MULT)
        layer.set_clip(None)
        lip = list(zip(sxs.tolist(), sy.tolist()))
        pygame.draw.lines(layer, LOOKS[self.style]["lip"], False, lip,
                          max(1, int(round(2.2 * z + 0.6))))
        for rect, _, _ in chunks:
            surface.blit(layer, rect.topleft, rect)
        for s in (layer, mask, light):
            s.set_clip(None)

    def _boulder_colours(self, terrain):
        """The three colours (shadow, body, highlight) of every boulder of the terrain, made once."""
        got = self.boulder_cols.get(id(terrain))
        if got is None or got[0] is not terrain:
            plain = LOOKS[self.style]["plain"]
            cols = []
            for tone in terrain.boulder_tone.tolist():
                base = tuple(int(v * (0.85 + 0.3 * tone)) for v in plain)
                cols.append((tuple(int(v * 0.55) for v in base), base, tuple(min(255, int(v * 1.3)) for v in base)))
            got = self.boulder_cols[id(terrain)] = (terrain, cols)
        return got[1]

    def _boulders(self, surface, terrain, z, cam_x, cam_y):
        d = (terrain.boulder_x - cam_x + lander.WORLD / 2) % lander.WORLD - lander.WORLD / 2
        px_all = CX + d * z
        gy_all = CY + (terrain.boulder_y - cam_y) * z
        seen = np.nonzero((px_all > -60) & (px_all < W + 60) & (gy_all > -40) & (gy_all < H + 40))[0]
        if not len(seen):
            return
        cols = self._boulder_colours(terrain)
        for i in seen.tolist():
            px, gy, r = float(px_all[i]), float(gy_all[i]), float(terrain.boulder_r[i])
            shadow, base, light = cols[i]
            rr = max(1.0, r * z)
            rect = pygame.Rect(0, 0, int(rr * 2.2), max(2, int(rr * 1.5)))
            rect.midbottom = (int(px), int(gy + rr * 0.35))
            pygame.draw.ellipse(surface, shadow, rect.move(int(rr * 0.25), int(rr * 0.1)))
            pygame.draw.ellipse(surface, base, rect)
            hi = rect.inflate(-int(rect.width * 0.5), -int(rect.height * 0.5))
            hi.topleft = (rect.left + int(rr * 0.3), rect.top + int(rr * 0.15))
            if hi.width > 0 and hi.height > 0:
                pygame.draw.ellipse(surface, light, hi)

    def _pads(self, surface, form, z, cam_x, cam_y):
        blink = 0.5 + 0.5 * math.sin(form.time * 5.0)
        for p in form.terrain.pads:
            d = (p["x"] - cam_x + lander.WORLD / 2) % lander.WORLD - lander.WORLD / 2
            px = CX + d * z
            pw = p["w"] * z
            if px + pw / 2 + 80 * z < 0 or px - pw / 2 - 80 * z > W:
                continue
            gy = CY + (p["y"] - cam_y) * z
            if gy < -80 or gy > H + 80:
                continue
            plate = pygame.Rect(int(px - pw / 2), int(gy - max(1.0, 3 * z)), int(pw), max(2, int(7 * z)))
            pygame.draw.rect(surface, (200, 205, 215), plate)
            pygame.draw.rect(surface, (240, 245, 250), (plate.left, plate.top, plate.width, max(1, int(2 * z))))
            stripe = max(2, int(10 * z))
            for k in range(0, plate.width // stripe + 1, 2):
                pygame.draw.rect(surface, (240, 190, 40), (plate.left + k * stripe, plate.top + max(1, int(2 * z)),
                                                           min(stripe, plate.right - plate.left - k * stripe),
                                                           max(1, plate.height - max(1, int(2 * z)))))
            for side in (-1, 1):                                              # a beacon at each end
                bx = px + side * (pw / 2 + 2 * z)
                pygame.draw.line(surface, (180, 180, 190), (bx, gy), (bx, gy - 34 * z), max(1, int(2 * z)))
                glow = (255, int(40 + 70 * blink), 40)
                pygame.draw.circle(surface, glow, (int(bx), int(gy - 36 * z)), max(2, int(5 * z)))
            lab = self._font(max(10, int(34 * z))).render(p["kind"].upper().replace("X", "×"), True, (255, 235, 140))
            surface.blit(lab, lab.get_rect(midbottom=(int(px), int(gy - 42 * z))))


# ------------------------------------------------------------------ the HUD
def _tone(value, perfect, rough):
    v = abs(value)
    return (90, 255, 120) if v <= perfect else (255, 190, 70) if v <= rough else (255, 80, 60)


ROW_GAP = 30
HUD_TOP = 84
HUD_GAP = 24                                # between the longest label and the longest value


def hud_layout(game, font, rows):
    """(x of the labels, x where the values end, y of the first row) of the readings at the top right: the labels start far
    enough to the left for the longest one (INCLINAISON, VIT. HORIZ.) never to touch a value."""
    right_x = BASE_WIDTH - 16
    label_w = max(game._txt(font, label, HUD_COLOR).get_width() for label, _, _ in rows)
    value_w = max(game._txt(font, "+000.0", HUD_COLOR).get_width(), max(game._txt(font, v, HUD_COLOR).get_width() for _, v, _ in rows))
    return right_x - value_w - HUD_GAP - label_w, right_x, HUD_TOP


def draw_hud(game, form):
    """Fuel, altitude and speeds (green = a perfect landing, orange = a rough one, red = a crash), the end message."""
    from i18n import t
    surface, font = game.game_surface, game.font
    p = game.player
    tilt = math.degrees(lander.lean(p.ast_angle))
    if (p.ast_angle + math.pi / 2 + math.pi) % (2 * math.pi) - math.pi < 0:
        tilt = -tilt
    rows = [
        (t("lander_alt"), "%4d" % (form.altitude() / 10.0), HUD_COLOR),
        (t("lander_hs"), "%+5.1f" % (form.vx / 10.0), _tone(form.vx, lander.PERFECT[1], lander.ROUGH[1])),
        (t("lander_vs"), "%+5.1f" % (form.vy / 10.0), _tone(form.vy if form.vy > 0 else lander.ROUGH[0] * 9, lander.PERFECT[0], lander.ROUGH[0])),
        (t("lander_tilt"), "%+4d°" % round(tilt), _tone(math.radians(abs(tilt)), lander.PERFECT[2], lander.ROUGH[2])),
    ]
    left_x, right_x, y = hud_layout(game, font, rows)
    for label, value, colour in rows:
        surface.blit(game._txt(font, label, HUD_COLOR), (left_x, y))
        right = game._txt(font, value, colour)
        surface.blit(right, (right_x - right.get_width(), y))
        y += ROW_GAP
    # the tank, under the last row (the top left is the gauge of the hull)
    low = form.fuel <= lander.FUEL_LOW
    blink = (not low) or form.fuel <= 0 or int(form.time * 4) % 2 == 0
    label = game._txt(font, "%s %3d" % (t("lander_fuel"), int(form.fuel)), (255, 80, 60) if low and blink else HUD_COLOR)
    y += 8
    surface.blit(label, (left_x, y))
    bar = pygame.Rect(left_x, y + label.get_height() + 4, right_x - left_x, 10)
    pygame.draw.rect(surface, (30, 40, 60), bar)
    fill = bar.copy()
    fill.width = int(bar.width * max(0.0, min(1.0, form.fuel / form.fuel_max)))
    pygame.draw.rect(surface, (255, 80, 60) if low else (90, 255, 120), fill)
    pygame.draw.rect(surface, HUD_COLOR, bar, 1)
    if form.fuel <= 0 and form.phase == "flying":
        announce.draw(game, surface, t("lander_empty"), "danger", "discreet", (BASE_WIDTH // 2, 96))
    msg = lander.message(form)
    if msg is not None:
        key, ctype = msg
        text = t(key)
        announce.draw(game, surface, text, ctype, "major", (BASE_WIDTH // 2, BASE_HEIGHT // 2 - 150))
        if form.phase == "landed":
            detail = t("lander_points").format(p=form.points, b=form.bonus, z=lander.PAD_BONUS[form.pad["kind"]])
            announce.draw(game, surface, detail, "gain", "standard", (BASE_WIDTH // 2, BASE_HEIGHT // 2 - 20))
