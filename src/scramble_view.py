"""What the player sees in the Scramble level (src/scramble.py): the sky of the setting (its stars and its mother planet, from
src/lander_view.py) sliding slowly behind, the rock of the ceiling and of the ground in the texture of the setting, the ship's
shots and the HUD (the sections of the course and where the ship is in it).

The rock is made in chunks (CHUNK px of the course wide), each one once, as two pictures with their own transparency: the
ceiling (from the top of the screen to its lower edge) and the ground (from its upper edge to the bottom). The edge is
smooth (the alpha follows the line to a fraction of a pixel), lit from the upper left on the slopes of the ground, darker
deeper in the rock. A frame only blits the chunks on the screen: nothing is cut out or lit any more while the course scrolls,
so the scroll stays smooth at 144 Hz on a small graphics chip. The chunks a little ahead of the screen are made in the
background (BACKGROUND), and the ones behind it are let go.
"""
import math
import threading

import numpy as np
import pygame
import loading

import announce
import lander
import lander_view
import scramble
from settings import BASE_HEIGHT, BASE_WIDTH

W, H = BASE_WIDTH, BASE_HEIGHT
CHUNK = 256                       # px of the course per chunk of rock
AHEAD = 3                         # chunks made in advance, to the right of the screen
BACKGROUND = True                 # the chunks ahead are made by a thread (off in the tests: everything is made when asked)
RIM = 10.0                        # px of the edge of the rock that take the light
DEEP = 240.0                      # px into the rock where it is darkest
TEX_MIX = 110 / 255.0             # the share of the second texture (the same as the Lunar Lander's)
HUD_COLOR = (120, 235, 255)
FAR_SKY = 0.05                    # how fast the stars and the planet slide, for one px of the course
NEAR_SKY = 0.22                   # ... the nearer stars
PLANET_SKY = 0.012


def _tex_arrays(style):
    """The two textures of the ground of the setting (lander_view), as arrays [x, y, rgb] (made once per setting)."""
    got = _TEX.get(style)
    if got is None:
        tiles = lander_view.assets(style)["tiles"]
        got = _TEX[style] = [pygame.surfarray.array3d(t).astype(np.float32) for t in tiles]
    return got


_TEX = {}


class View:
    """The picture of the level, kept from one frame to the next."""

    def __init__(self, style, course):
        self.style = style
        self.course = course
        self.assets = lander_view.assets(style)
        self.tex = _tex_arrays(style)
        self.lip = np.array(lander_view.LOOKS[style]["lip"], dtype=np.float32)
        self.chunks = {}                         # index -> (ceiling picture, ground picture, y of the ground picture)
        self.lock = threading.Lock()
        self.worker = None
        self.wanted = set()
        self.near = self._near_stars()
        self.far_rocks = [(self._dim(pic), x, y, amp) for pic, x, y, amp in self.assets["rocks"]]
        self.fonts = {}
        try:
            warm_sky()
        except Exception:                                # (no display yet: they are made when first drawn)
            pass

    # --- the rock
    def _colour(self, wx, wy):
        """The texture at the world points (wx[:, None], wy[None, :]): the two tiles laid one over the other."""
        t0, t1 = self.tex
        a = t0[(wx % t0.shape[0])[:, None], (wy % t0.shape[1])[None, :]]
        b = t1[(wx % t1.shape[0])[:, None], (wy % t1.shape[1])[None, :]]
        return a * (1.0 - TEX_MIX) + b * TEX_MIX

    def _piece(self, x0, y0, h, ground):
        """One picture of rock: CHUNK px wide from the world x0, h px high from the y y0; `ground`: the ground (else the
        ceiling)."""
        wx = np.arange(x0, x0 + CHUNK)
        wy = np.arange(y0, y0 + h)
        course = self.course
        edge_fn = course.ground if ground else course.ceiling
        edge = edge_fn(wx.astype(float) + 0.5)
        slope = (edge_fn(wx.astype(float) + 1.5) - edge_fn(wx.astype(float) - 0.5)) / 2.0
        col = self._colour(wx, wy)
        depth = (wy[None, :] + 0.5 - edge[:, None]) if ground else (edge[:, None] - wy[None, :] - 0.5)
        alpha = np.clip(depth + 0.5, 0.0, 1.0)
        shade = 1.0 - 0.55 * np.clip(depth / DEEP, 0.0, 1.0) ** 0.8
        rim = np.clip(1.0 - depth / RIM, 0.0, 1.0) * (depth > -1.0)
        if ground:
            facing = (0.8 - 0.6 * slope) / np.sqrt(1.0 + slope * slope)       # the light comes from the upper left
            lit = np.clip((facing - 0.45) / 0.55, 0.0, 1.0)[:, None]
            dark = np.clip((0.45 - facing) / 0.6, 0.0, 1.0)[:, None]
            k = rim * (0.15 + 0.55 * lit)
            col = col + (self.lip - col) * k[..., None]
            shade = shade * (1.0 - 0.45 * rim * dark)
        else:
            col = col + (self.lip - col) * (rim * 0.2)[..., None]               # (the underside of the ceiling is in the shade)
            shade = shade * 0.8
        col = col * shade[..., None]
        pic = pygame.Surface((CHUNK, h), pygame.SRCALPHA)
        px = pygame.surfarray.pixels3d(pic)
        px[:] = np.clip(col, 0, 255).astype(np.uint8)
        del px
        pa = pygame.surfarray.pixels_alpha(pic)
        pa[:] = (alpha * 255).astype(np.uint8)
        del pa
        return pic

    def make_chunk(self, i):
        """The two pictures of the chunk i (made once)."""
        got = self.chunks.get(i)
        if got is not None:
            return got
        x0 = i * CHUNK
        xs = np.arange(x0 - 1, x0 + CHUNK + 2, 2.0)
        ceil_h = int(min(H, math.ceil(float(np.max(self.course.ceiling(xs)))) + 2))
        floor_y = int(max(0, math.floor(float(np.min(self.course.ground(xs)))) - 2))
        top = self._piece(x0, 0, ceil_h, False) if ceil_h > 0 else None
        low = self._piece(x0, floor_y, H - floor_y, True) if floor_y < H else None
        got = (top, low, floor_y)
        with self.lock:
            self.chunks[i] = got
        return got

    def _ahead(self, first, last):
        """Make the chunks first..last in the background (one thread at a time)."""
        need = [i for i in range(first, last + 1) if i not in self.chunks]
        if not need or (self.worker is not None and self.worker.is_alive()):
            return

        def work():
            for i in need:
                try:
                    self.make_chunk(i)
                except Exception:                 # (the screen is closed: nothing to do)
                    return

        self.worker = threading.Thread(target=work, name="scramble-rock", daemon=True)
        self.worker.start()

    def _rock(self, surface, cam):
        first = int(cam // CHUNK)
        last = int((cam + W) // CHUNK)
        cam_i = int(round(cam))
        for i in range(first, last + 1):
            if i * CHUNK >= self.course.length:
                break
            top, low, floor_y = self.make_chunk(i)
            sx = i * CHUNK - cam_i
            if top is not None:
                surface.blit(top, (sx, 0))
            if low is not None:
                surface.blit(low, (sx, floor_y))
        if BACKGROUND:
            self._ahead(last + 1, last + AHEAD)
        else:
            for i in range(last + 1, last + 2):
                if i * CHUNK < self.course.length:
                    self.make_chunk(i)
        with self.lock:
            for i in [k for k in self.chunks if k < first - 1]:
                del self.chunks[i]                # (behind the screen: never seen again)

    # --- the sky
    @staticmethod
    def _dim(pic):
        """The other asteroids of the sky, darker: here they are far behind, not in the way of the ship."""
        out = pic.copy()
        shade = pygame.Surface(out.get_size(), pygame.SRCALPHA)
        shade.fill((105, 105, 115, 255))
        out.blit(shade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return out

    @staticmethod
    def _near_stars():
        """A few nearer stars, on a transparent layer (a colour key: a quick blit)."""
        rng = np.random.default_rng(9)
        layer = pygame.Surface((W, H))
        layer.fill((0, 0, 0))
        layer.set_colorkey((0, 0, 0))
        for _ in range(70):
            x, y = int(rng.integers(0, W)), int(rng.integers(0, H))
            v = int(rng.uniform(150, 255))
            layer.set_at((x, y), (v, v, min(255, v + 10)))
            layer.set_at(((x + 1) % W, y), (v // 2, v // 2, v // 2 + 5))
        return layer

    def _sky(self, surface, cam):
        stars = self.assets["stars"]
        if stars is not None:
            ox = int(-cam * FAR_SKY) % W
            surface.blit(stars, (ox - W, 0))
            surface.blit(stars, (ox, 0))
            ox = int(-cam * NEAR_SKY) % W                   # the nearer stars: still behind the planet and the rocks
            surface.blit(self.near, (ox - W, 0))
            surface.blit(self.near, (ox, 0))
        else:
            surface.blit(self.assets["sky"], (0, 0))
        mother = self.assets["planet"]
        if mother is not None:
            pic, back, (px, py) = mother
            where = (round(px + 160 - cam * PLANET_SKY - pic.get_width() / 2), round(py - 40 - pic.get_height() / 2))
            if stars is not None:
                surface.blit(back, where)
            surface.blit(pic, where, special_flags=pygame.BLEND_ADD)
        for pic, x, y, amp in self.far_rocks:
            sx = (x - cam * PLANET_SKY * amp / 40.0) % (W + 300) - 150
            surface.blit(pic, (round(sx - pic.get_width() / 2), round(y - 60 - pic.get_height() / 2)))

    def draw(self, surface, form):
        self._sky(surface, form.cam)
        self._rock(surface, form.cam)


_SPRITES = {}


def _aa(draw, logical, size, k=2):
    """A small picture drawn by `draw(surface, k)` on a canvas `k` times its `logical` size, then scaled down to `size`:
    smooth edges (and smooth shading for the bigger k)."""
    big = pygame.Surface((int(logical[0] * k), int(logical[1] * k)), pygame.SRCALPHA)
    draw(big, k)
    return pygame.transform.smoothscale(big, (int(size[0]), int(size[1])))


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _sheen(pic, poly, stops):
    """A metal sheen across `poly`, left to right: `stops` = [(0..1, colour), ...]."""
    xs = [p[0] for p in poly]
    x0, x1 = int(min(xs)), int(max(xs))
    layer = pygame.Surface(pic.get_size(), pygame.SRCALPHA)
    for x in range(x0, x1 + 1):
        t = (x - x0) / max(1, x1 - x0)
        col = stops[-1][1]
        for (ta, ca), (tb, cb) in zip(stops, stops[1:]):
            if ta <= t <= tb:
                col = _mix(ca, cb, (t - ta) / max(1e-6, tb - ta))
                break
        pygame.draw.line(layer, col + (255,), (x, 0), (x, pic.get_height()))
    mask = pygame.Surface(pic.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), poly)
    layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    pic.blit(layer, (0, 0))


STATION_K = 8                        # the launcher and its missile are drawn 8 times bigger, then scaled (smooth chrome)
ICE = (120, 220, 255)                # the lights of the launcher, and the nose of its missile: glacier blue
# where the lights are, on the drawing of the launcher (its logical 44 x 30, from the top left, the launcher standing):
LIGHTS_BASE = ((9, 23), (35, 23))                     # the two lights of the plinth: a slow pulse
LIGHTS_RAIL = ((18, 3), (26, 3), (18, 8), (26, 8))    # the four of the rail: steady with a missile on it, blinking without


def _draw_station(pic, k):
    """A launcher standing on the ground: a chrome dome on a dark plinth, the rail of its missile coming out of the top.
    Its lights are drawn over it in the game (draw_station: they blink), not here."""
    w, h = pic.get_size()
    plinth = [(1 * k, h), (3 * k, h - 5 * k), (w - 3 * k, h - 5 * k), (w - 1 * k, h)]
    _sheen(pic, plinth, [(0, (40, 44, 54)), (0.5, (96, 102, 118)), (1, (40, 44, 54))])
    pygame.draw.polygon(pic, (20, 22, 28), plinth, max(1, k // 2))
    dome = pygame.Rect(5 * k, h - 23 * k, w - 10 * k, 36 * k)
    cx, cy, rx, ry = dome.centerx, dome.centery, dome.w / 2.0, dome.h / 2.0
    layer = pygame.Surface(pic.get_size(), pygame.SRCALPHA)
    for i in range(int(rx), 0, -1):                     # a chrome bowl: rings brighter towards a light at the upper left
        t = i / rx
        pygame.draw.ellipse(layer, _mix((235, 242, 255), (52, 60, 78), t ** 0.8) + (255,),
                            (cx - i - (1 - t) * 4 * k, cy - i * ry / rx - (1 - t) * 6 * k, 2 * i, 2 * i * ry / rx))
    clip = pygame.Surface(pic.get_size(), pygame.SRCALPHA)
    pygame.draw.ellipse(clip, (255, 255, 255, 255), dome)
    pygame.draw.rect(clip, (0, 0, 0, 0), (0, h - 5 * k, w, 5 * k))
    layer.blit(clip, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    pic.blit(layer, (0, 0))
    pygame.draw.arc(pic, (20, 22, 30), dome, 0, math.pi, max(1, k // 2))
    for dx in (-11 * k, 11 * k):                        # two ribs
        pygame.draw.line(pic, (60, 66, 84), (cx + dx, h - 5 * k), (cx + dx * 0.55, h - 19 * k), max(1, k // 2))
    rail = pygame.Rect(w // 2 - 6 * k, h - 30 * k, 12 * k, 14 * k)
    _sheen(pic, [rail.topleft, rail.topright, rail.bottomright, rail.bottomleft],
           [(0, (70, 76, 94)), (0.5, (200, 210, 230)), (1, (70, 76, 94))])
    pygame.draw.rect(pic, (20, 22, 28), (w // 2 - 2 * k, h - 30 * k, 4 * k, 14 * k))      # the slot of the missile
    for lx, ly in LIGHTS_BASE + LIGHTS_RAIL:            # the lights, off (draw_station lights them)
        pygame.draw.circle(pic, (28, 52, 66), (lx * k, ly * k), int(1.1 * k if ly > 20 else 0.9 * k))


def _draw_missile(pic, k):
    """A missile, nose up, to go with the chrome launcher: a brushed metal body, a glacier-blue nose and band, dark chrome
    fins edged in blue."""
    w, h = pic.get_size()
    cx = w // 2
    body = [(cx - 3 * k, 8 * k), (cx + 3 * k, 8 * k), (cx + 3 * k, h - 6 * k), (cx - 3 * k, h - 6 * k)]
    _sheen(pic, body, [(0, (110, 118, 136)), (0.35, (236, 242, 252)), (0.6, (176, 184, 200)), (1, (86, 92, 108))])
    nose = [(cx, 0), (cx - 3 * k, 9 * k), (cx + 3 * k, 9 * k)]
    _sheen(pic, nose, [(0, (40, 120, 170)), (0.4, (190, 240, 255)), (1, (40, 110, 160))])
    pygame.draw.rect(pic, ICE, (cx - 3 * k, 13 * k, 6 * k, 2 * k))                       # the band
    for side in (-1, 1):
        fin = [(cx + side * 3 * k, h - 12 * k), (cx + side * (w // 2), h - 2 * k), (cx + side * 3 * k, h - 4 * k)]
        if side > 0:
            fin[1] = (w - 1, h - 2 * k)
        pygame.draw.polygon(pic, (58, 64, 80), fin)
        pygame.draw.line(pic, ICE, fin[0], fin[1], max(1, k // 2))
    pygame.draw.rect(pic, (70, 76, 92), (cx - 3 * k, h - 6 * k, 6 * k, 6 * k))           # the nozzle


def sprite(name, down):
    """The picture of a station or a missile ("station", "missile"), upside down for the ceiling (made once)."""
    key = (name, bool(down))
    pic = _SPRITES.get(key)
    if pic is None:
        if name == "station":
            pic = _aa(_draw_station, (44, 30), (scramble.STATION_W, scramble.STATION_H), STATION_K)
        else:
            pic = _aa(_draw_missile, (10, 30), (scramble.MISSILE_W, scramble.MISSILE_H), STATION_K)
        if down:
            pic = pygame.transform.flip(pic, False, True)
        _SPRITES[key] = pic
    return pic


_LIGHTS = {}


def _light(level):
    """A light of the launcher at `level` (0..8: off .. full): a blue core and its halo (made once per level)."""
    pic = _LIGHTS.get(level)
    if pic is None:
        r = 5
        pic = pygame.Surface((2 * r + 1, 2 * r + 1), pygame.SRCALPHA)
        k = level / 8.0
        for i in range(r, 0, -1):
            pygame.draw.circle(pic, ICE + (int(150 * k * (1 - i / r) ** 1.5),), (r, r), i)
        pygame.draw.circle(pic, _mix((28, 52, 66), (215, 248, 255), k) + (255,), (r, r), 1)
        _LIGHTS[level] = pic
    return pic


def light_levels(t, phase, loaded):
    """How bright the lights of a launcher are at time `t` (0..8): (the two of the plinth, the four of the rail). The
    plinth breathes slowly; the rail is lit while a missile stands on it and blinks, two by two, while it reloads."""
    base = int(round(4 + 4 * math.sin(t * 2.4 + phase)))
    if loaded:
        rail = (8, 8, 8, 8)
    else:
        on = int(t * 6.0 + phase) % 2 == 0
        rail = (8, 8, 1, 1) if on else (1, 1, 8, 8)
    return (base, base), rail


def draw_station(surface, x, y, down, t=0.0, phase=0.0, loaded=True):
    """A launcher at (x, y), the top left of its picture, upside down on the ceiling, with its lights at time `t`."""
    pic = sprite("station", down)
    surface.blit(pic, (round(x), round(y)))
    sx, sy = scramble.STATION_W / 44.0, scramble.STATION_H / 30.0
    base, rail = light_levels(t, phase, loaded)
    for (lx, ly), level in zip(LIGHTS_BASE + LIGHTS_RAIL, base + rail):
        dot = _light(level)
        py = (30 - ly) * sy if down else ly * sy
        half = dot.get_width() // 2                      # (the middle of the light: its pixel (half, half))
        surface.blit(dot, (round(x + lx * sx) - half, round(y + py) - half))


_TILTS = {}
_BIRDS = {}
_COMETS = {}


def bird_frames(stage):
    """The four pictures of a bird of the game (two wing beats, with and without the glow of its eyes), turned to face the
    left (made once per kind)."""
    got = _BIRDS.get(stage)
    if got is None:
        import os
        from settings import asset_path
        prefix = "bird2" if stage >= 2 else "bird1"
        got = []
        for name in ("flap0", "flap1", "flap0_glow", "flap1_glow"):
            path = asset_path("sprites", "%s_%s.png" % (prefix, name))
            if os.path.exists(path):
                got.append(pygame.transform.rotate(pygame.image.load(path).convert_alpha(), -90))
        if not got:                                    # (no picture: a plain disc)
            pic = pygame.Surface((36, 36), pygame.SRCALPHA)
            pygame.draw.circle(pic, (120, 170, 255) if stage == 1 else (130, 220, 110), (18, 18), 14)
            got = [pic]
        _BIRDS[stage] = got
    return got


def comet_frames(down, right=False):
    """The comet of the game's sky, smaller, heading left (and down, or up), or right for a traitor: (its pictures, where its
    head is in them)."""
    key = (bool(down), bool(right))
    got = _COMETS.get(key)
    if got is None:
        import scramble_birds as sb
        from starfield import Comet
        frames = []
        hx, hy = sb.COMET_HEAD
        size = (480, 270)
        for fr in Comet._load():
            size = fr.get_size()
            w, h = max(8, int(size[0] * sb.COMET_SCALE)), max(8, int(size[1] * sb.COMET_SCALE))
            img = pygame.transform.flip(pygame.transform.smoothscale(fr, (w, h)), not right, not down)
            frames.append(img)
        head = ((hx if right else size[0] - hx) * sb.COMET_SCALE, (hy if down else size[1] - hy) * sb.COMET_SCALE)
        got = _COMETS[key] = (frames, head)
    return got


def _tilted(down, lean):
    """The missile leaning by `lean` radians (by steps of 3 degrees, each made once)."""
    deg = int(round(math.degrees(lean) / 3.0)) * 3
    if deg == 0:
        return sprite("missile", down)
    key = (down, deg)
    pic = _TILTS.get(key)
    if pic is None:
        pic = _TILTS[key] = pygame.transform.rotozoom(sprite("missile", down), -deg, 1.0)
    return pic


def _draw_stations(surface, form, cam_i):
    import asteroids
    for st in form.stations:
        sx = st.x - cam_i
        if sx < -60:
            continue
        if sx > W + 60:
            break
        if not st.alive:
            continue
        down = st.side == "ceil"
        if st.loaded:                                  # (the next missile stands on its rail)
            mx, my = st.mouth()
            pic = sprite("missile", down)
            surface.blit(pic, (round(sx - pic.get_width() / 2), round(my - pic.get_height() / 2)))
        l, t, r, b = st.box()
        draw_station(surface, l - cam_i, t, down, form.time, st.x * 0.013, st.loaded)
    for m in form.missiles:
        sx = m.x - cam_i
        down = m.dir > 0
        tail_y = m.y - m.dir * (scramble.MISSILE_H / 2 + 4)
        flick = 0.75 + 0.25 * math.sin(m.age * 60.0)
        asteroids._add_glow(surface, (255, 150, 50), (sx, tail_y), int(26 * flick))
        asteroids._add_glow(surface, (255, 240, 190), (sx, tail_y), int(11 * flick))
        pic = _tilted(down, m.tilt() * (-1 if down else 1))
        surface.blit(pic, (round(sx - pic.get_width() / 2), round(m.y - pic.get_height() / 2)))


def _draw_sky(surface, form):
    """The comets, the birds and their shots (all in the coordinates of the screen)."""
    import asteroids
    sky = getattr(form, "sky", None)
    if sky is None:
        return
    for c in sky.comets:
        frames, (hx, hy) = comet_frames(c.down, getattr(c, "right", False))
        if frames:
            pic = frames[int(c.age * 10.0) % len(frames)]
            surface.blit(pic, (round(c.x - hx), round(c.y - hy)))
        else:
            asteroids._add_glow(surface, (90, 230, 255), (c.x, c.y), 40)
    for b in sky.birds:
        if b.waiting:
            continue
        frames = bird_frames(b.stage)
        k = int(b.flap * 5.2) % 2
        if len(frames) >= 4 and (b.flap % 2.2) < 0.35:
            k += 2                                     # (the glow of the eyes now and then)
        pic = frames[k % len(frames)]
        surface.blit(pic, (round(b.x - pic.get_width() / 2), round(b.y - pic.get_height() / 2)))
    for s in sky.shots:
        asteroids._add_glow(surface, (255, 80, 200), (s.x, s.y), 22)
        pygame.draw.circle(surface, (255, 190, 255), (int(s.x), int(s.y)), 4)


# ------------------------------------------------------------------ the enemy base (src/scramble_base.py)
_BASE = {}


def _saucer_metal():
    """The photograph of the boss saucer's hull, as arrays: (rgb [x, y], alpha [x, y]), or None."""
    got = _BASE.get("metal")
    if got is None:
        from settings import asset_path
        try:
            img = pygame.image.load(asset_path("sprites", "boss_saucer.png")).convert_alpha()
            got = (pygame.surfarray.array3d(img).astype(np.float32), pygame.surfarray.array_alpha(img))
        except Exception:
            got = False
        _BASE["metal"] = got
    return got or None


def _metal_spots(rgb, alpha, w, h, count, seed):
    """`count` places of the photograph where a w x h piece is all metal (opaque, not the red light of the band)."""
    rng = np.random.default_rng(seed)
    red = (rgb[..., 0] > 110) & (rgb[..., 0] > rgb[..., 1] * 1.6)
    spots = []
    W0, H0 = alpha.shape
    for x in range(0, W0 - w, 5):
        for y in range(0, H0 - h, 5):
            if alpha[x:x + w, y:y + h].min() > 235 and not red[x:x + w, y:y + h].any():
                spots.append((x, y))
    if not spots:
        return []
    picks = rng.choice(len(spots), size=min(count, len(spots)), replace=False)
    return [spots[int(i)] for i in picks]


def _bevel(col, k=1.0):
    """A plate of metal: lit on its upper left edge, in the shade on its lower right one, a dark outline, two rivets."""
    w, h = col.shape[:2]
    out = col.copy()
    out[:2, :, :] = out[:2, :, :] * 0.6 + 255 * 0.4 * k
    out[:, :2, :] = out[:, :2, :] * 0.6 + 255 * 0.4 * k
    out[-2:, :, :] *= 0.45
    out[:, -2:, :] *= 0.45
    out[0, :, :] *= 0.5
    out[:, 0, :] *= 0.5
    out[-1, :, :] *= 0.25
    out[:, -1, :] *= 0.25
    for rx, ry in ((4, 4), (w - 5, h - 5)):
        out[rx - 1:rx + 1, ry - 1:ry + 1, :] = (40, 38, 44)
        out[rx - 1, ry - 1, :] = (210, 210, 220)
    return out


def brick_tiles():
    """The 16 pictures of the bricks of the wall: pieces of the saucer's hull, bevelled and riveted (made once)."""
    got = _BASE.get("bricks")
    if got is None:
        import scramble_base as sb
        metal = _saucer_metal()
        w, h = sb.BRICK_W, sb.BRICK_H
        got = []
        if metal is not None:
            rgb, alpha = metal
            for x, y in _metal_spots(rgb, alpha, w, h, 16, 3):
                col = rgb[x:x + w, y:y + h, :]
                grey = col.mean(axis=2, keepdims=True)
                col = col * 0.55 + grey * 0.45                     # (a little less colour: steel)
                col = np.clip((col - 70.0) * 1.1 + 72.0, 0, 255)   # (the gunmetal of the saucer, a little more contrast)
                pic = pygame.Surface((w, h))
                pygame.surfarray.blit_array(pic, np.clip(_bevel(col), 0, 255).astype(np.uint8))
                got.append(pic)
        while len(got) < 16:                                       # (no photograph: plain steel)
            pic = pygame.Surface((w, h))
            g = 110 + 8 * (len(got) % 4)
            pic.fill((g, g, g + 8))
            arr = pygame.surfarray.array3d(pic).astype(np.float32)
            pygame.surfarray.blit_array(pic, np.clip(_bevel(arr), 0, 255).astype(np.uint8))
            got.append(pic)
        _BASE["bricks"] = got
    return got


def base_panel(width, height):
    """The plates behind the boss: big dark pieces of the hull (made once per size)."""
    key = ("panel", int(width), int(height))
    got = _BASE.get(key)
    if got is None:
        pw, ph = 52, 40
        pic = pygame.Surface((max(1, int(width)), max(1, int(height))))
        pic.fill((22, 22, 28))
        metal = _saucer_metal()
        spots = _metal_spots(*metal, pw // 2, ph // 2, 12, 8) if metal is not None else []
        for i, x in enumerate(range(0, int(width), pw)):
            for j, y in enumerate(range(0, int(height), ph)):
                if spots:
                    sx, sy = spots[(i * 7 + j * 3) % len(spots)]
                    piece = metal[0][sx:sx + pw // 2, sy:sy + ph // 2, :]
                    col = np.repeat(np.repeat(piece, 2, axis=0), 2, axis=1) * 0.45     # (a piece of the hull, twice as big)
                else:
                    col = np.full((pw, ph, 3), 48.0)
                plate = pygame.Surface((pw, ph))
                pygame.surfarray.blit_array(plate, np.clip(_bevel(col, 0.25), 0, 255).astype(np.uint8))
                pic.blit(plate, (x, y))
        got = _BASE[key] = pic
    return got


RED_SKIN_HUE = 358.0 / 360.0         # the red commander: the hue of its skin ...
RED_SKIN_SAT = 0.72                  # ... its saturation ...
RED_SKIN_GAIN = 1.45                 # ... and how much lighter than the green it was painted in
RED_ALPHA = (22.0, 2.4)              # its edges made crisp: alpha = (alpha - 22) * 2.4 (boss_core_*.png is already solid)


def redden(pic):
    """The green commander turned red (in place): only its skin, the pixels whose green stands over their red and blue,
    takes the red (its light kept); the beak, the mouth, the eyes (the bright spots at their height, off the middle) and
    the dark parts keep their colours. Made solid."""
    raw = pygame.surfarray.array3d(pic).astype(np.float32)
    r, g, b = raw[..., 0], raw[..., 1], raw[..., 2]
    v = raw.max(axis=2) / 255.0
    n = raw.shape[0]
    xs, ys = np.meshgrid(np.arange(n) / n, np.arange(raw.shape[1]) / raw.shape[1], indexing="ij")
    eyes = (v > 0.55) & (ys > 0.27) & (ys < 0.42) & (np.abs(xs - 0.5) > 0.07) & (np.abs(xs - 0.5) < 0.22)
    skin = (np.clip((g - np.maximum(r, b) + 1.0) / 6.0, 0.0, 1.0) * ~eyes)[..., None]     # (the eyes keep their light)
    k, s = RED_SKIN_HUE * 6.0, RED_SKIN_SAT                 # (the red of the skin, from the hue: HSV, the light of v)
    tone = np.array([min(1.0, abs(k - 3.0) - 1.0), min(1.0, 2.0 - abs(k - 2.0)), min(1.0, 2.0 - abs(k - 4.0))])
    tone = np.clip(tone, 0.0, 1.0)
    val = np.clip(v * RED_SKIN_GAIN, 0.0, 1.0)[..., None]
    red = val * (1.0 - s + s * tone) * 255.0
    out = raw * (1.0 - skin) + red * skin
    pixels = pygame.surfarray.pixels3d(pic)
    pixels[:] = np.clip(out, 0, 255).astype(np.uint8)
    del pixels
    alpha = pygame.surfarray.pixels_alpha(pic)
    alpha[:] = np.clip((alpha.astype(np.float32) - RED_ALPHA[0]) * RED_ALPHA[1], 0, 255).astype(np.uint8)
    del alpha
    return pic


def _keep_mouth_black(pic, white):
    """The inside of the alien's mouth (opaque black in boss_core_*.png) stays black when it flashes white."""
    from boss import MOUTH_BLACK
    rgb = pygame.surfarray.array3d(pic)
    mouth = (pygame.surfarray.array_alpha(pic) == 255) & (rgb.max(axis=2) <= MOUTH_BLACK)
    pixels = pygame.surfarray.pixels3d(white)
    pixels[mouth] = 0
    del pixels


def boss_frames(size=None):
    """The alien of the boss saucer, in red (its green skin turned red, the rest kept: redden), at the size of the base
    (or `size` px: the Bestiary shows it at the size of the saucer's): (frames, white frames)."""
    import scramble_base as sb
    side = int(size or sb.BOSS_SIZE)
    key = "boss" if side == sb.BOSS_SIZE else ("boss", side)
    got = _BASE.get(key)
    if got is None:
        from boss import BossCore
        BossCore._load_images()
        frames, whites = [], []
        size = (side, side)
        for fr in (BossCore._frames or []):
            pic = pygame.transform.smoothscale(redden(fr.copy()), size)      # (at the size it was drawn, then scaled)
            frames.append(pic)
            white = pic.copy()
            white.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
            _keep_mouth_black(pic, white)
            whites.append(white)
        got = _BASE[key] = (frames, whites)
    return got


def station_portrait():
    """A missile launcher with its missile on the rail, standing on a bit of ground: its picture in the Bestiary."""
    got = _BASE.get("portrait")
    if got is None:
        import scramble
        st = pygame.Surface(sprite("station", False).get_size(), pygame.SRCALPHA)
        draw_station(st, 0, 0, False)                   # (its lights on)
        mi = sprite("missile", False)
        w = max(st.get_width(), mi.get_width()) + 8
        rise = scramble.STATION_H + scramble.MISSILE_H / 2 - 8          # (Station.mouth: the middle of the missile)
        top = int(rise + scramble.MISSILE_H / 2)
        h = top + 6
        pic = pygame.Surface((w, h), pygame.SRCALPHA)
        cx = w // 2
        pic.blit(mi, (cx - mi.get_width() // 2, int(top - rise - mi.get_height() / 2)))
        pic.blit(st, (cx - st.get_width() // 2, top - st.get_height()))
        pygame.draw.rect(pic, (90, 86, 82), (0, top, w, 6))
        got = _BASE["portrait"] = pic
    return got


def _turret_sprite():
    got = _BASE.get("turret")
    if got is None:
        import scramble_base as sb

        def draw(pic, k):
            w, h = pic.get_size()
            steel, dark, edge = (90, 94, 108), (40, 42, 52), (170, 176, 192)
            body = pygame.Rect(w // 3, 2 * k, w - w // 3, h - 4 * k)
            pygame.draw.rect(pic, steel, body, border_radius=3 * k)
            pygame.draw.rect(pic, edge, body, max(1, k), border_radius=3 * k)
            tube = pygame.Rect(0, h // 2 - 4 * k, w // 2, 8 * k)
            pygame.draw.rect(pic, dark, tube)
            pygame.draw.rect(pic, edge, tube, max(1, k))
            pygame.draw.circle(pic, (255, 70, 50), (w - 7 * k, h // 2), int(2.5 * k))
        got = _BASE["turret"] = _aa(draw, (30, 26), (sb.TURRET_W, sb.TURRET_H))
    return got


def _base_missile(lean):
    """A missile of a turret, its nose to the left, leaning by `lean` (steps of 3 degrees)."""
    deg = int(round(math.degrees(lean) / 3.0)) * 3
    key = ("bm", deg)
    got = _BASE.get(key)
    if got is None:
        got = _BASE[key] = pygame.transform.rotozoom(sprite("missile", False), 90 - deg, 1.0)
    return got


def _wall_picture(base):
    """The wall as one picture (made again only when a brick has gone: bricks only ever go, so the number standing tells),
    with where its top left corner is in the world."""
    standing = base.standing()
    cached = getattr(base, "_wall_pic", None)
    x0, y0 = base.face, base.y0
    if cached is None or cached[0] != standing:
        tiles = brick_tiles()
        import scramble_base as sb
        pic = cached[1] if cached is not None else pygame.Surface(
            (base.columns * sb.BRICK_W, base.rows * sb.BRICK_H), pygame.SRCALPHA)
        pic.fill((0, 0, 0, 0))
        for b in base.bricks:
            if b.alive:
                l, t, r, bt = b.box()
                pic.blit(tiles[b.tile % len(tiles)], (round(l - x0), round(t - y0)))
        base._wall_pic = cached = (standing, pic)
    return cached[1], x0, y0


def _draw_base(surface, form, cam_i):
    import asteroids
    base = getattr(form, "base", None)
    if base is None:
        return
    left = base.face - 60 - cam_i
    if left > W:
        return                                                     # (not on the screen yet)
    # the plates behind the boss, and its chamber
    px = int(base.panel_x - cam_i)
    if px < W:
        surface.blit(base_panel(W - px + 40, base.bottom - base.top), (px, int(base.top)))
    boss = base.boss
    if boss.alive:
        bx, by = boss.x - cam_i, boss.y
        frames, whites = boss_frames()
        if boss.dying:
            k = 1.0 - min(1.0, boss.death / 1.2)
            asteroids._add_glow(surface, (255, 120, 60), (bx, by), int(60 + 200 * (1 - k)))
        elif frames:
            asteroids._add_glow(surface, (180, 30, 30), (bx, by), 190)
            i = int(boss.t * 8.0) % len(frames)
            pic = whites[i] if boss.hit_flash > 0 else frames[i]
            surface.blit(pic, (round(bx - pic.get_width() / 2), round(by - pic.get_height() / 2)))
    # the wall
    wall, wx, wy = _wall_picture(base)
    surface.blit(wall, (round(wx - cam_i), round(wy)))
    tur = _turret_sprite()
    for t in base.turrets:
        if t.alive:
            l, tp, r, b = t.box()
            surface.blit(tur, (round(l - cam_i), round(tp)))
    for m in base.missiles:
        sx = m.x - cam_i
        flick = 0.75 + 0.25 * math.sin(m.age * 60.0)
        asteroids._add_glow(surface, (255, 150, 50), (sx + 22, m.y), int(26 * flick))
        pic = _base_missile(m.tilt())
        surface.blit(pic, (round(sx - pic.get_width() / 2), round(m.y - pic.get_height() / 2)))
    for b in base.bullets:
        x, y = int(b.x - cam_i), int(b.y)
        asteroids._add_glow(surface, (255, 80, 200), (x + 7, y), 24)
        pygame.draw.rect(surface, (255, 80, 200), (x, y - 3, 14, 7))
        pygame.draw.rect(surface, (255, 180, 255), (x, y - 1, 14, 3))


def warm_sky():
    """Make the pictures of the birds and of the comets (at the start of the mission, not when the first one comes)."""
    brick_tiles()
    loading.report()
    boss_frames()
    loading.report()
    for stage in (1, 2):
        bird_frames(stage)
        loading.report()
    for down in (True, False):
        for right in (False, True):
            comet_frames(down, right)                  # (and the traitors, from the left)
            loading.report()


def draw_items(surface, form):
    """The stations and their missiles, the birds, the comets, the shots and the sparks, over the rock."""
    import asteroids
    cam_i = int(round(form.cam))
    _draw_stations(surface, form, cam_i)
    _draw_base(surface, form, cam_i)
    _draw_sky(surface, form)
    for sp in form.sparks:
        a = max(0.0, sp.life / sp.max)
        x, y = sp.x - cam_i, sp.y
        asteroids._add_glow(surface, (255, 170, 60), (x, y), max(4, int(sp.size * 5 * a + 3)))
    tip = form.tip
    mid = tuple(min(255, (c + 255) // 2) for c in tip)
    for s in form.shots:
        x, y = s.x - cam_i, s.y
        for length, width, col in ((26, 6, tip), (18, 3, mid)):
            pygame.draw.line(surface, col, (x - length, y), (x, y), width)
        asteroids._add_glow(surface, (255, 240, 200), (x, y), 22)


# ------------------------------------------------------------------ the HUD
SECTION_BAR = (BASE_WIDTH - 16 - 300, 50, 300, 10)


def draw_hud(game, form):
    """The sections of the course in a bar at the top right (as on the arcade machine), the one the ship is in lit, a mark
    where the ship is; and the message of the end."""
    from i18n import t
    surface, font = game.game_surface, game.font
    base = getattr(form, "base", None)
    if base is not None and form.phase in ("arena", "won"):
        _draw_wall_hud(game, surface, font, base)
    else:
        _draw_sections(game, surface, font, form)
    if base is not None and base.dead_for is not None:
        announce.draw(game, surface, t("scramble_won"), "success", "major", (BASE_WIDTH // 2, BASE_HEIGHT // 2 - 150))
    elif form.phase == "arena" and form.arena_time < 3.0:
        announce.draw(game, surface, t("scramble_arena"), "danger", "major", (BASE_WIDTH // 2, BASE_HEIGHT // 2 - 150))


WALL_BAR = (BASE_WIDTH - 340 - 10 - 190, 50, 190, 10)     # (in front of the wall, clear of the lives in the middle)


def _draw_wall_hud(game, surface, font, base):
    """In the arena: what is left of the wall (a gauge and its share), and under it the life of the boss (its bar)."""
    from i18n import t
    import scramble_base as sb
    x, y, w, h = WALL_BAR
    boss = base.boss
    by = y + h + 10
    label = game._txt(font, t("scramble_boss_hp"), (255, 120, 110))
    surface.blit(label, (x + w - label.get_width(), by + 14))
    seg = (w - 2 * (boss.max_hp - 1)) / float(boss.max_hp)
    flash = boss.hit_flash > 0 and int(boss.hit_flash * 16) % 2 == 0
    for i in range(boss.max_hp):
        r = pygame.Rect(int(x + i * (seg + 2)), by, int(seg), 10)
        on = i < boss.hp
        pygame.draw.rect(surface, ((255, 255, 255) if flash else (220, 40, 40)) if on else (50, 20, 24), r)
        pygame.draw.rect(surface, (255, 140, 130), r, 1)
    share = base.standing() / float(max(1, len(base.bricks)))
    pygame.draw.rect(surface, (30, 40, 60), (x, y, w, h))
    pygame.draw.rect(surface, (255, 120, 90) if share > 0.25 else (255, 200, 90), (x, y, int(w * share), h))
    pygame.draw.rect(surface, HUD_COLOR, (x, y, w, h), 1)
    label = game._txt(font, t("scramble_wall").format(p=int(round(share * 100))), HUD_COLOR)
    surface.blit(label, (x + w - label.get_width(), y - label.get_height() - 4))


def _draw_sections(game, surface, font, form):
    from i18n import t
    x, y, w, h = SECTION_BAR
    course = form.course
    total = course.stop
    here = course.section_at(form.cam + scramble.START_X)
    for (key, _, _), start, end in zip(course.sections, course.starts, list(course.starts[1:]) + [course.stop]):
        a = x + int(w * start / total)
        b = x + int(w * min(end, total) / total)
        rect = pygame.Rect(a + 1, y, max(2, b - a - 2), h)
        on = key == here
        pygame.draw.rect(surface, (255, 200, 90) if on else (40, 60, 90), rect)
        pygame.draw.rect(surface, HUD_COLOR, rect, 1)
    mark = x + int(w * form.progress())
    pygame.draw.polygon(surface, (255, 255, 255), [(mark, y + h + 2), (mark - 5, y + h + 9), (mark + 5, y + h + 9)])
    name = game._txt(font, t("scramble_sec_" + here), HUD_COLOR)
    surface.blit(name, (x + w - name.get_width(), y - name.get_height() - 4))


# ------------------------------------------------------------------ the menu of the test
PREVIEW_SIZE = lander_view.PREVIEW_SIZE
_PREVIEWS = {}
_LOCK = threading.RLock()
_warming = False


def preview(style):
    """A picture of a setting for the menu of the test (made once): its sky and a stretch of the cavern."""
    pic = _PREVIEWS.get(style)
    if pic is None:
        with _LOCK:
            pic = _PREVIEWS.get(style) or _make_preview(style)
    return pic


def _make_preview(style):
    import random
    form = scramble.ScrambleFormation(style=style, seed=5, rng=random.Random(1))
    view = View(style, form.course)
    form.cam = form.course.starts[1] + 900.0
    full = pygame.Surface((W, H))
    view.draw(full, form)
    _PREVIEWS[style] = pygame.transform.smoothscale(full, PREVIEW_SIZE)
    return _PREVIEWS[style]


def warm(order):
    """Make the pictures of the menu in the background, in this order (once per run); like lander_view.warm."""
    global _warming
    if not lander_view.WARM_UP or _warming:
        return None
    _warming = True

    def work():
        for style in order:
            try:
                preview(style)
            except Exception:
                return

    thread = threading.Thread(target=work, name="scramble-warm-up", daemon=True)
    thread.start()
    return thread
