"""What the player sees in the Lunar Lander level (src/lander.py): the sky, the ground (a texture of the body, lit from the
upper left, darker with the depth), the landing zones and the HUD. The ship itself is drawn by the Player, in the middle.

Everything heavy is made once per body: the sky and the two tiles of texture of the ground. A frame only slides and scales
those tiles, cuts the ground out of them with the polygon of the relief and lays the light on its edge.
"""
import math

import numpy as np
import pygame

import announce
import lander
from settings import BASE_HEIGHT, BASE_WIDTH

W, H = BASE_WIDTH, BASE_HEIGHT
CX, CY = W / 2.0, H / 2.0
COLUMN = 8.0                                # one point of the relief every COLUMN px OF THE WORLD (the points follow the ground, not the screen: a peak never blinks)
TILES = ((1024, 1024), (768, 768))          # (texture size in px, size of the tile in the world in px)
ZQ = 256                                    # the zoom drawn is a multiple of 1/ZQ: the tiles (1024 and 768 world px) then have a whole size
HUD_COLOR = (120, 235, 255)
_CACHE = {}                                 # per body: sky, textures


# ------------------------------------------------------------------ textures (made once)
def _octave(size, cells, rng):
    lattice = rng.random((cells, cells))
    t = np.arange(size) * cells / float(size)
    i = np.floor(t).astype(int)
    f = t - i
    f = f * f * (3 - 2 * f)
    j = (i + 1) % cells
    fx, fy = f[None, :], f[:, None]
    a, b = lattice[i][:, i], lattice[i][:, j]
    c, d = lattice[j][:, i], lattice[j][:, j]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _fbm(size, base, octaves, rng):
    """A noise that loops on all four sides (value noise on a looping lattice)."""
    total, amp, norm = np.zeros((size, size)), 1.0, 0.0
    for o in range(octaves):
        total += amp * _octave(size, base * (2 ** o), rng)
        norm += amp
        amp *= 0.5
    return total / norm


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
    if style == "ice":
        top, low = np.array([48, 26, 12.0]), np.array([205, 128, 58.0])
        k = (np.clip(np.arange(H) / (H * 0.95), 0, 1) ** 1.3)[:, None, None]
        arr = np.repeat(top + (low - top) * k, W, axis=1)
        pygame.surfarray.blit_array(sky, np.clip(arr, 0, 255).astype(np.uint8).swapaxes(0, 1))
    else:
        sky.fill((2, 2, 5))
    return sky


def _stars(sky):
    """The sky of an asteroid (one flat colour) with its stars, as one opaque picture (an opaque blit is much faster)."""
    rng = np.random.default_rng(4)
    layer = sky.copy()
    for _ in range(300):
        x, y = int(rng.integers(0, W)), int(rng.integers(0, H))
        v = int(rng.uniform(70, 255))
        layer.set_at((x, y), (v, v, min(255, int(v * 1.05))))
        if rng.random() < 0.08:
            layer.set_at(((x + 1) % W, y), (v, v, v))
    return layer


def assets(style):
    """The sky and the textures of a body (made the first time, then kept)."""
    got = _CACHE.get(style)
    if got is None:
        seed = 11 if style == "ice" else 23
        sky = _sky(style)
        got = {
            "sky": sky,
            "stars": _stars(sky) if style == "rock" else None,
            "tiles": [_texture(style, size, seed + k) for k, (size, _) in enumerate(TILES)],
        }
        _CACHE[style] = got
    return got


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
        if self.style == "rock":
            ox, oy = int(-cam_x * 0.03) % W, int(-cam_y * 0.03) % H
            for dx in (ox - W, ox):
                for dy in (oy - H, oy):
                    surface.blit(self.assets["stars"], (dx, dy))
        else:
            surface.blit(self.assets["sky"], (0, 0))
            self._haze(surface, cam_x, cam_y, z)
        terrain = form.terrain
        sxs, wx, gy, sy = relief(terrain, z, cam_x, cam_y)
        if float(sy.min()) < H + 10:
            self._ground(surface, form, sxs, sy, wx, z, cam_x, cam_y)
        self._boulders(surface, terrain, z, cam_x, cam_y)
        self._pads(surface, form, z, cam_x, cam_y)

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
        layer.set_clip(region)
        # the texture: two tiles of different sizes, slid and scaled with the world
        for k, (_, world) in enumerate(TILES):
            tile = self._tile(k, z)
            tw = tile.get_width()
            x0, y0 = tile_origin(tw, z, cam_x, cam_y)
            if k == 1:
                tile.set_alpha(110)
            y = y0
            while y < H:
                x = x0
                while x < W:
                    if y + tw > top:
                        layer.blit(tile, (x, y))
                    x += tw
                y += tw
        # darker with the depth (world y): strips of a growing shade (a multiplication of the colours by a grey bar: the fast
        # blit of pygame)
        edges = [int(CY + (-520.0 + i * 100.0 - cam_y) * z) for i in range(25)]
        for i in range(1, 24):
            y0 = max(edges[i], top)
            h = min(edges[i + 1], H) - y0
            if h > 0:
                layer.blit(self.depth_bars[i], (0, y0), (0, 0, W, h), special_flags=pygame.BLEND_RGB_MULT)
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
            layer.blit(light, band.topleft, band)
            # cut the ground out
            mask.set_clip(band)
            mask.fill((0, 0, 0, 0))
            pts = list(zip(xs, ys)) + [(xs[-1], H + 4), (xs[0], H + 4)]
            pygame.draw.polygon(mask, (255, 255, 255, 255), pts)
            layer.blit(mask, band.topleft, band, special_flags=pygame.BLEND_RGBA_MULT)
        lip = list(zip(sxs.tolist(), sy.tolist()))
        pygame.draw.lines(layer, (255, 232, 200) if self.style == "ice" else (205, 205, 200), False, lip,
                          max(1, int(round(2.2 * z + 0.6))))
        surface.blit(layer, region.topleft, region)
        for s in (layer, mask, light):
            s.set_clip(None)

    def _boulder_colours(self, terrain):
        """The three colours (shadow, body, highlight) of every boulder of the terrain, made once."""
        got = self.boulder_cols.get(id(terrain))
        if got is None or got[0] is not terrain:
            plain = (92, 90, 86) if self.style == "rock" else (150, 120, 92)
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
    fill.width = int(bar.width * max(0.0, min(1.0, form.fuel / lander.FUEL_START)))
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
            announce.draw(game, surface, detail, "gain", "standard", (BASE_WIDTH // 2, BASE_HEIGHT // 2 - 90))
