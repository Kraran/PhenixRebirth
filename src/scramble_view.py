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
        self.fonts = {}

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
        else:
            surface.blit(self.assets["sky"], (0, 0))
        mother = self.assets["planet"]
        if mother is not None:
            pic, back, (px, py) = mother
            where = (round(px + 160 - cam * PLANET_SKY - pic.get_width() / 2), round(py - 40 - pic.get_height() / 2))
            if stars is not None:
                surface.blit(back, where)
            surface.blit(pic, where, special_flags=pygame.BLEND_ADD)
        for pic, x, y, amp in self.assets["rocks"]:
            sx = (x - cam * PLANET_SKY * amp / 40.0) % (W + 300) - 150
            surface.blit(pic, (round(sx - pic.get_width() / 2), round(y - 60 - pic.get_height() / 2)))
        if stars is not None:
            ox = int(-cam * NEAR_SKY) % W
            surface.blit(self.near, (ox - W, 0))
            surface.blit(self.near, (ox, 0))

    def draw(self, surface, form):
        self._sky(surface, form.cam)
        self._rock(surface, form.cam)


def draw_items(surface, form):
    """The shots of the ship and the sparks, over the rock."""
    import asteroids
    cam_i = int(round(form.cam))
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
    x, y, w, h = SECTION_BAR
    course = form.course
    total = course.stop
    here = course.section_at(form.cam + scramble.START_X)
    for (key, _, _), start, end in zip(scramble.SECTIONS, course.starts, list(course.starts[1:]) + [course.stop]):
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
    if form.phase in ("arena", "won"):
        announce.draw(game, surface, t("scramble_arena"), "success", "major", (BASE_WIDTH // 2, BASE_HEIGHT // 2 - 150))


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
