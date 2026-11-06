"""The escort modules: small gyroscope satellites on each side of the ship (Adventure).

A module is an open ring holding a sphere banded with light, its cannon to the front (up). The ring turns slowly. The Phenix
wears silver modules lit in blue (the light of its engines), the Shield copper-red ones lit in amber.

  placing     each one follows a point on its side of the ship (ANCHOR: by the cockpit) a little late, as on a spring; in
              the dome of the Shield or the Phenix form they move out and a little down (WIDE), out of the way of the
              animation (and of its harm)
  the wall    a module that touches the electric wall of the side of the screen is struck by its lightning and blows up
              (even with the Tesla seal: it protects the ship, not the modules)
  the ship    they blink with it while it is untouchable, and are not drawn while its hull blows up or once it is lost

  the shots  each salvo of the ship gets one more shot from the cannon of each module in working order (x2, then x3);
              a shot of a module that hits charges the Phenix gauge as the others do, one that misses costs nothing

Steps (claude/aventure-modules-plan.md): 1. on screen (this file, the TEST - Modules mission and its menu); 2. their shots
(player.py: Player.shoot, gun_points); 3. the harm done to them. The state of a mission is `game.gyro` (a Gyro, or None).
"""
import math
import random

import numpy as np
import pygame

import loading
from errlog import log_exc
from settings import BASE_WIDTH

SIZE = 40                       # px, on screen
ANCHOR = (52.0, -2.0)           # the point a module follows, from the centre of the ship (x: each side)
WIDE = (78.0, 26.0)             # ... in the dome or the Phenix form: further out and a little lower
WIDE_TIME = 0.3                 # s to move out or back
FOLLOW = 14.0                   # 1/s: how fast a module catches its point up (a light lag, as on a spring)
GRAZE = 5.0                     # px: how much closer than its point a module may come (it grazes the ship, never touches it)
SPIN = 60.0                     # degrees a second: the ring turns slowly
FRAMES = 24                     # pictures of the ring over half a turn (it has two gaps: half a turn looks the same)
WALL_X = 8                      # the electric walls (where the lightning of the ship strikes too)
STRUCK = 0.32                   # s in the lightning before the module blows up
FLASH = 0.14                    # s of white when a shot hits a module that holds
SMOKE_EVERY = 0.05              # s between two puffs of smoke of a damaged module
COUNTS = (1, 2)                 # one module (shots x2), then two (x3)
ARMOURS = (1, 2)                # the hits a module takes from shots (the bonus "reinforced": 2); a collision always kills

SHOT_COLOURS = {                # the shots of the modules: the light of their hull (tip, middle)
    "phoenix": ((120, 200, 255), (190, 230, 255)),
    "shield": ((255, 170, 70), (255, 215, 150)),
}

STYLES = {                      # the hull -> metal, light
    "phoenix": ((0.78, 0.80, 0.86), (0.35, 0.75, 1.0)),
    "shield": ((0.62, 0.36, 0.34), (1.0, 0.62, 0.18)),
}

_FRAMES = {}


# --- the pictures (made once per hull, behind the loading bar) ---------------------------------------------------------
_LIGHT = np.array([-0.55, -0.65, 0.52])
_LIGHT = _LIGHT / np.linalg.norm(_LIGHT)
_HALF = _LIGHT + np.array([0.0, 0.0, 1.0])
_HALF = _HALF / np.linalg.norm(_HALF)


def _grid(n):
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    return (x - n / 2 + 0.5) / (n / 2), (y - n / 2 + 0.5) / (n / 2)


def _shade(nx, ny, nz, base, spec=1.0, rough=30.0):
    dot = np.clip(nx * _LIGHT[0] + ny * _LIGHT[1] + nz * _LIGHT[2], 0, 1)
    sp = np.clip(nx * _HALF[0] + ny * _HALF[1] + nz * _HALF[2], 0, 1) ** rough
    col = base * (0.22 + 0.85 * dot)[..., None] + (spec * sp)[..., None]
    rim = np.clip(nx * 0.6 + ny * 0.7, 0, 1) ** 3 * 0.35            # a cold light from below (the stars)
    return col + rim[..., None] * np.array([0.35, 0.55, 0.9])


def _metal(n, tint, seed, x, y):
    """Brushed metal: fine circular streaks."""
    rng = np.random.default_rng(seed)
    streaks = rng.random(4096).astype(np.float32)
    r = np.sqrt(x * x + y * y)
    b = streaks[np.clip((r * 900).astype(int), 0, 4095)]
    return np.ones((n, n, 3), np.float32) * np.array(tint, np.float32) * (0.78 + 0.3 * b[..., None])


def _over(img, rgb, mask):
    m = mask.astype(np.float32)[..., None]
    img[..., :3] = img[..., :3] * (1 - m) + rgb * m
    img[..., 3] = np.maximum(img[..., 3], mask.astype(np.float32))


def _glow(img, colour, cx, cy, radius, strength, x, y):
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / radius
    g = np.exp(-d * d * 2.5) * strength
    img[..., :3] += g[..., None] * np.array(colour, np.float32)
    img[..., 3] = np.maximum(img[..., 3], np.clip(g, 0, 1))


def _picture(hull, turn, n=128):
    """One picture (n x n, RGBA floats) of the module of `hull`, its ring turned by `turn` radians."""
    tint, accent = STYLES.get(hull, STYLES["shield"])
    img = np.zeros((n, n, 4), np.float32)
    x, y = _grid(n)
    r = np.sqrt(x * x + y * y)
    ang = np.arctan2(y, x)
    a = ang - turn
    # the ring: a torus seen from the front, cut twice (on the axis of the arms turned by a quarter)
    R, w = 0.66, 0.11
    t = (r - R) / w
    ring = (np.abs(t) < 1) & (np.abs(np.cos(a)) > 0.17)
    tz = np.sqrt(np.clip(1 - t * t, 0, 1))
    col = _shade(x / (r + 1e-6) * t, y / (r + 1e-6) * t, tz, _metal(n, tint, 2, x, y), 1.0, 30)
    grooves = (np.abs(np.sin(a * 14)) < 0.12) & ring
    col = np.where(grooves[..., None], col * 0.6, col)
    _over(img, col, ring)
    # the two arms holding the sphere (they turn with the ring)
    ux, uy = math.cos(turn + math.pi / 2), math.sin(turn + math.pi / 2)
    along = x * ux + y * uy
    across = -x * uy + y * ux
    arm = (np.abs(across) < 0.04) & (np.abs(along) > 0.36) & (np.abs(along) < 0.58)
    an = np.clip(across / 0.04, -1, 1)
    acol = _shade(-an * uy, an * ux, np.sqrt(np.clip(1 - an * an, 0, 1)), _metal(n, tint, 5, x, y) * 0.8)
    _over(img, acol, arm)
    # the cannon, to the front (up)
    width, top, bottom = 0.07, -0.95, -0.25
    barrel = (np.abs(x) < width) & (y > top) & (y < bottom)
    u = np.clip(x / width, -1, 1)
    bcol = _shade(u, np.zeros_like(u), np.sqrt(np.clip(1 - u * u, 0, 1)), _metal(n, tint, 7, x, y), 1.1, 40)
    bands = (np.abs(((y - top) / (bottom - top)) * 5 % 1 - 0.5) < 0.06) & barrel
    bcol = np.where(bands[..., None], bcol * 0.55, bcol)
    _over(img, bcol, barrel)
    _over(img, np.array([0.05, 0.05, 0.07]), (np.abs(x) < width * 0.55) & (np.abs(y - top - 0.012) < 0.02))
    _glow(img, accent, 0.0, top + 0.01, 0.07, 0.9, x, y)
    # the sphere and its band of light
    d = 1 - (x * x + y * y) / (0.4 * 0.4)
    sphere = d > 0
    sz = np.sqrt(np.clip(d, 0, 1))
    scol = _shade(x / 0.4, y / 0.4, sz, _metal(n, [c * 0.85 for c in tint], 9, x, y), 1.2, 50)
    band = (np.abs(y) < 0.035) & sphere
    scol = np.where(band[..., None], np.array(accent) * 0.9 + scol * 0.2, scol)
    _over(img, scol, sphere)
    _glow(img, accent, 0, 0, 0.6, 0.22, x, y)
    return img


def _surface(arr, size):
    a = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
    rgb = np.ascontiguousarray(a[..., :3].transpose(1, 0, 2))
    surf = pygame.Surface((arr.shape[1], arr.shape[0]), pygame.SRCALPHA)
    pygame.surfarray.blit_array(surf, rgb)
    alpha = pygame.surfarray.pixels_alpha(surf)
    alpha[:] = a[..., 3].T
    del alpha
    return pygame.transform.smoothscale(surf, (size, size))


def frames(hull):
    """The FRAMES pictures of the ring turning (half a turn) for the modules of `hull` ("phoenix" / "shield")."""
    hull = "phoenix" if hull == "phoenix" else "shield"
    out = _FRAMES.get(hull)
    if out is None:
        out = []
        for k in range(FRAMES):
            out.append(_surface(_picture(hull, math.pi * k / FRAMES), SIZE))
            loading.report()
        _FRAMES[hull] = out
    return out


def frame_at(t):
    """The index of the picture shown `t` seconds after the ring started to turn (SPIN degrees a second)."""
    return int((t * SPIN) % 180.0 / 180.0 * FRAMES) % FRAMES


def scaled(hull, size):
    """The pictures of `frames(hull)` at `size` px (the workshop and the hangar), made once."""
    key = ("scaled", "phoenix" if hull == "phoenix" else "shield", int(size))
    out = _FRAMES.get(key)
    if out is None:
        out = [pygame.transform.smoothscale(img, (int(size), int(size))) for img in frames(hull)]
        _FRAMES[key] = out
    return out


def draw_icon(surface, hull, cx, cy, size, t, halves=(True, True), split=0.0, dim=False):
    """A module turning, `size` px, centred on (cx, cy), for the menus: `halves` (left, right) says which halves are shown
    (a piece of a module not yet assembled is one half) and `split` how far apart the two halves stand (px)."""
    img = scaled(hull, size)[frame_at(t)]
    if dim:
        img = img.copy()
        img.fill((110, 110, 120, 255), special_flags=pygame.BLEND_RGBA_MULT)
    half = int(size) // 2
    x0, y0 = int(cx - size / 2), int(cy - size / 2)
    if halves[0]:
        surface.blit(img, (x0 - int(split), y0), pygame.Rect(0, 0, half, int(size)))
    if halves[1]:
        surface.blit(img, (x0 + half + int(split), y0), pygame.Rect(half, 0, int(size) - half, int(size)))


def whites(hull):
    """The same pictures in white (the flash of the lightning)."""
    key = ("white", "phoenix" if hull == "phoenix" else "shield")
    out = _FRAMES.get(key)
    if out is None:
        out = []
        for img in frames(hull):
            w = img.copy()
            w.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGB_MAX)
            out.append(w)
        _FRAMES[key] = out
    return out


# --- a module ------------------------------------------------------------------------------------------------------
class Module:
    def __init__(self, side, armour, x, y):
        self.side = side                 # -1: on the left of the ship, 1: on its right
        self.hp = int(armour)
        self.armour = int(armour)
        self.x, self.y = float(x), float(y)
        self.alive = True
        self.struck = 0.0                # > 0: in the lightning of the wall, it blows up when it reaches STRUCK
        self.spin = random.uniform(0.0, 180.0)
        self.flash = 0.0                 # > 0: just hit by a shot (white)
        self.smoke_t = 0.0

    @property
    def damaged(self):
        return self.alive and self.hp < self.armour

    def rect(self):
        r = SIZE * 0.42
        return pygame.Rect(int(self.x - r), int(self.y - r), int(2 * r), int(2 * r))

    def touches_wall(self):
        r = SIZE * 0.42
        return self.x - r <= WALL_X or self.x + r >= BASE_WIDTH - WALL_X


class Gyro:
    """The modules of the ship in a mission: `count` (1: on the left, 2: both sides), `armour` (hits from shots)."""

    def __init__(self, hull, count, armour, ship=None):
        self.hull = "phoenix" if hull == "phoenix" else "shield"
        self.count = max(0, min(2, int(count)))
        self.armour = max(1, int(armour))
        self.wide = 0.0                  # 0: by the cockpit, 1: moved out (dome, Phenix form)
        sx, sy = (ship.x, ship.y) if ship is not None else (BASE_WIDTH / 2, 0.0)
        sides = (-1, 1)[:self.count]                 # one module: on the left; two: one on each side
        self.modules = [Module(s, self.armour, sx + s * ANCHOR[0], sy + ANCHOR[1]) for s in sides]
        self.lost = []                   # what happened to the modules lost: "wall", "shot", "crash"
        self.owned = False               # the pilot's modules (a module destroyed must be bought again)
        self.smoke = []                  # puffs of the damaged modules: [x, y, vx, vy, age, life, size]
        self.sparks = []                 # [x, y, vx, vy, age]
        frames(self.hull)

    def alive(self):
        return [m for m in self.modules if m.alive and m.struck <= 0]

    def sheltered(self):
        """In the dome of the Shield or the Phenix form the modules have moved out and down out of harm's way."""
        return self.wide >= 0.5

    def targets(self):
        """The modules the enemies can hit: in working order, not sheltered."""
        return [] if self.sheltered() else self.alive()

    def hit(self, game, m, kind):
        """A module is hit: "shot" (an enemy shot: one point of its armour) or "crash" (a bird, the hull of the boss,
        a laser of the Guardians: destroyed at once). True when it is destroyed."""
        if not m.alive or m.struck > 0:
            return False
        m.hp = 0 if kind == "crash" else m.hp - 1
        if m.hp <= 0:
            self._blow_up(game, m, kind)
            return True
        m.flash = FLASH
        try:
            game.sounds.play("shield_zap", x=m.x)
        except Exception:
            log_exc("gyro.hit")
        for _ in range(8):
            self._spark(m.x, m.y)
        return False

    def _spark(self, x, y):
        a = random.uniform(0, 2 * math.pi)
        v = random.uniform(80, 220)
        self.sparks.append([x, y, math.cos(a) * v, math.sin(a) * v, 0.0])

    def gun_points(self):
        """Where the shots of the modules leave from: (side, x, y) of the mouth of each cannon (the modules in working
        order)."""
        return [(m.side, m.x, m.y - SIZE * 0.48) for m in self.alive()]

    def target(self, ship, side):
        ax = ANCHOR[0] + (WIDE[0] - ANCHOR[0]) * self.wide
        ay = ANCHOR[1] + (WIDE[1] - ANCHOR[1]) * self.wide
        return ship.x + side * ax, ship.y + ay

    def update(self, game, ship, dt):
        out = 1.0 if _moved_out(ship) else 0.0
        step = dt / WIDE_TIME
        self.wide = min(out, self.wide + step) if out > self.wide else max(out, self.wide - step)
        k = 1.0 - math.exp(-FOLLOW * dt)
        self._puffs(dt)
        for m in self.modules:
            if not m.alive:
                continue
            m.spin = (m.spin + SPIN * dt) % 180.0
            m.flash = max(0.0, m.flash - dt)
            if m.damaged:                                        # one point of its armour left: it smokes, it crackles
                m.smoke_t -= dt
                if m.smoke_t <= 0:
                    m.smoke_t = SMOKE_EVERY
                    self.smoke.append([m.x + random.uniform(-6, 6), m.y + random.uniform(-4, 4), random.uniform(-12, 12),
                                       random.uniform(30, 60), 0.0, random.uniform(0.5, 0.8), random.uniform(4, 7)])
                    if random.random() < 0.18:
                        self._spark(m.x + random.uniform(-8, 8), m.y + random.uniform(-8, 8))
            if m.struck > 0:                                     # in the lightning: it stays where it was struck
                m.struck += dt
                if m.struck >= STRUCK:
                    self._blow_up(game, m, "wall")
                continue
            tx, ty = self.target(ship, m.side)
            m.x += (tx - m.x) * k
            m.y += (ty - m.y) * k
            # it may lag outwards as much as it likes, but never come in closer than GRAZE: when the ship darts
            # towards a module, the module is pushed along, it grazes the hull and does not touch it
            nearest = abs(tx - ship.x) - GRAZE
            if m.side * (m.x - ship.x) < nearest:
                m.x = ship.x + m.side * nearest
            if m.touches_wall():
                m.struck = 1e-6
                try:
                    game.sounds.play("electric", x=m.x)        # (the crackle of the electric wall)
                except Exception:
                    log_exc("gyro.update")

    def _puffs(self, dt):
        for p in self.smoke:
            p[0] += p[2] * dt
            p[1] += p[3] * dt                                    # (the smoke trails behind: the ship flies up the screen)
            p[4] += dt
        self.smoke = [p for p in self.smoke if p[4] < p[5]]
        for s in self.sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[4] += dt
        self.sparks = [s for s in self.sparks if s[4] < 0.25]

    def _blow_up(self, game, m, why):
        m.alive = False
        self.lost.append(why)
        if self.owned:
            story = getattr(game, "story", None)
            if story is not None:
                story.lose_module()                # one of the pilot's modules: lost for good, to buy again
        for _ in range(14):
            self._spark(m.x, m.y)
        try:
            game.explosions.append(game._boom(m.x, m.y, kind="enemy"))         # (the size of a bird: a module is small)
            game.sounds.play("explosion", x=m.x)
        except Exception:
            log_exc("gyro._blow_up")

    def draw(self, surface, ship):
        if ship is None or not ship.alive or ship.dying or getattr(ship, "blast_hide", 0) > 0:
            return
        for p in self.smoke:                                     # the smoke and the sparks, even while they blink
            k = p[4] / p[5]
            r = int(p[6] * (1 + 1.4 * k))
            puff = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            grey = int(150 - 70 * k)
            pygame.draw.circle(puff, (grey, grey, grey + 8, int(150 * (1 - k))), (r + 1, r + 1), r)
            surface.blit(puff, (int(p[0] - r - 1), int(p[1] - r - 1)))
        for s in self.sparks:
            k = s[4] / 0.25
            colour = (255, 240, 170) if k < 0.5 else (255, 170, 60)
            pygame.draw.line(surface, colour, (int(s[0]), int(s[1])), (int(s[0] - s[2] * 0.02), int(s[1] - s[3] * 0.02)), 1)
        if ship.invulnerable > 0 and int(ship.invulnerable * 12) % 2 == 0:
            return                                               # (they blink with the ship)
        pics = frames(self.hull)
        for m in self.modules:
            if not m.alive:
                continue
            k = int(m.spin / 180.0 * FRAMES) % FRAMES
            img = pics[k]
            if (m.struck > 0 and int(m.struck * 30) % 2 == 0) or m.flash > 0:
                img = whites(self.hull)[k]
            surface.blit(img, (int(m.x - SIZE / 2), int(m.y - SIZE / 2)))
            if m.struck > 0:
                _lightning(surface, m)


def _moved_out(ship):
    """The dome of the Shield, the Phenix form, or the change into one of them."""
    return bool(getattr(ship, "is_phenix", False) or getattr(ship, "morph_dir", 0))


def _lightning(surface, m):
    """The lightning of the wall on a module: bolts from the wall to it, and around it."""
    wall_x = WALL_X if m.x < BASE_WIDTH / 2 else BASE_WIDTH - WALL_X
    for _ in range(3):
        pts = [(wall_x, m.y + random.uniform(-22, 22))]
        for k in range(1, 5):
            t = k / 5
            pts.append((wall_x + (m.x - wall_x) * t + random.uniform(-6, 6), m.y + random.uniform(-14, 14)))
        pts.append((m.x + random.uniform(-8, 8), m.y + random.uniform(-8, 8)))
        colour = (200, 230, 255) if random.random() < 0.45 else (80, 160, 255)
        pygame.draw.lines(surface, colour, False, pts, 2 if colour[0] > 150 else 1)
    pygame.draw.circle(surface, (120, 190, 255), (int(m.x), int(m.y)), int(SIZE * 0.55 + random.uniform(-3, 3)), 1)


# --- the mission ------------------------------------------------------------------------------------------------------
def start(game, spec):
    """At the start of a mission: the modules of the spec ({"count", "armour"}), or none."""
    game.gyro = None
    want = (spec or {}).get("modules")
    if not want or getattr(game, "play_mode", "") == "coop":
        return
    if spec.get("lander") or spec.get("scramble") or spec.get("spacewar") or spec.get("asteroids"):
        return                                                   # (not in those modes for now)
    try:
        hull = "phoenix" if getattr(game.player, "ship_id", "") == "phoenix" else "shield"
        game.gyro = Gyro(hull, want.get("count", 2), want.get("armour", 1), game.player)
        game.gyro.owned = bool(want.get("owned"))                # the pilot's modules (not those of the test)
        game.player.gun_points = game.gyro.gun_points            # each salvo of the ship gets a shot from each module
        game.player.gun_colours = SHOT_COLOURS[hull]
    except Exception:
        log_exc("gyro.start")
        game.gyro = None


def _on(game):
    """The modules of the mission running (none after it: an arcade game never has them)."""
    g = getattr(game, "gyro", None)
    return g if g is not None and getattr(game, "adventure", None) and getattr(game, "started", False) else None


def tick(game):
    g = _on(game)
    if g is not None and getattr(game, "player", None) is not None:
        g.update(game, game.player, float(game.dt or 0.0))


def attacks(game):
    """The enemies against the modules, before they reach the ship (a module stands in the way): the shots of the birds
    and of the boss take one point of armour; a diving bird (both are destroyed, no points), the hull of the boss and a
    laser of the Guardians destroy a module at once. Nothing touches them while they shelter (dome, Phenix form)."""
    g = _on(game)
    if g is None:
        return
    mods = g.targets()
    if not mods:
        return
    try:
        _attacks(game, g, mods)
    except Exception:
        log_exc("gyro.attacks")


def _attacks(game, g, mods):
    from guardian import FireLaser            # (late: the Guardians import a lot)
    boss = getattr(game, "boss_saucer", None)
    for m in mods:
        if not m.alive:
            continue
        box = m.rect()
        if boss is not None and getattr(boss, "alive", False):
            hull = boss.get_hull_hitbox()
            if hull.width > 0 and box.colliderect(hull):
                g.hit(game, m, "crash")
                continue
            for b in boss.bullets:
                if b.alive and b.get_hitbox().colliderect(box):
                    b.alive = False
                    if g.hit(game, m, "shot"):
                        break
            if not m.alive:
                continue
        for b in game.formation.bullets:
            if b.alive and b.get_hitbox().colliderect(box):
                if isinstance(b, FireLaser):
                    g.hit(game, m, "crash")                # the laser goes through, as it goes through the birds
                    break
                b.alive = False
                if g.hit(game, m, "shot"):
                    break
        if not m.alive:
            continue
        for e in game.formation.get_hittable_enemies():
            if getattr(e, "diving", False) and e.get_hitbox().colliderect(box):
                try:
                    e.kill(flash=False)                    # the bird goes down with the module, worth nothing
                except TypeError:
                    e.kill()
                    e.hit_flash_frames = 0
                    e.alive = False
                    e.dying = False
                game.explosions.append(game._boom(e.x, e.y, kind="collision"))
                g.hit(game, m, "crash")
                break


def draw(game, surface):
    g = _on(game)
    if g is not None:
        g.draw(surface, getattr(game, "player", None))
