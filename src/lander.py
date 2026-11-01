"""The test level "Lunar Lander" (story_state.py, id `test_lander`): a remake of Atari's Lunar Lander (1979) with the ship of the
hangar, on the ice of Titan or on the rock of an asteroid.

The rules:

- The ship is always in the middle of the screen; the ground scrolls under it and loops (the world is WORLD px wide).
- GRAVITY pulls it down, constant, as strong as the body (Titan pulls harder than an asteroid); the ship keeps its speed
  (inertia). The thruster pushes along the axis of the ship, so its turn matters; every second of thrust burns fuel, and an
  empty tank means a dead thruster (the turn still works). There is no time limit: the fuel is the clock.
- The view zooms in as the ship comes down: three levels (ZOOMS), the last one showing the ship at its normal size.
- The ground is rugged and random; one to three flat landing zones only, each 1.5, 2 or 3 times as wide as the ship (bonus
  x5, x2, x1). A landing is judged at the first touch of the ground (`verdict`): upright and slow = perfect (500 points + 50
  per unit of fuel left), a bit fast or leaning = rough (100 + 10 per unit), anything else, or any other ground = crash.
  The points are multiplied by the bonus of the zone (not the fuel bonus).
- Beeps warn that the fuel is low (`tick`), and the thruster and the crash are heard.

The player flies the real Player of the game (`Player.asteroid_mode` with `Player.lander` set to the formation below), with ONE life.
The formation looks like one without enemies to the rest of the game; `tick(game)` runs it every frame; the view is in
src/lander_view.py. The unit of length is the pixel at the maximum zoom (the normal size of the ship).
"""
import math
import random

import numpy as np

from errlog import log_exc

WORLD = 6000                      # the width of the ground, which loops
STEP = 4                          # one height every STEP px
SHIP_W, SHIP_H = 60, 90           # the sprite of the ship at the maximum zoom
# the points of the hull that touch the ground (x, y with the nose up; the last two are the feet)
HULL = ((0.0, -45.0), (-30.0, 12.0), (30.0, 12.0), (-26.0, 44.0), (26.0, 44.0))
FEET = (3, 4)
FOOT_Y = 44.0                     # how far under the middle of the ship the feet are
PAD_SIZES = {"x1": SHIP_W * 3, "x2": SHIP_W * 2, "x5": int(SHIP_W * 1.5)}      # 180 / 120 / 90 px
PAD_BONUS = {"x1": 1, "x2": 2, "x5": 5}
PAD_BLEND = 28                    # samples over which the ground is brought to the level of a zone

# The two bodies: gravity (px/s^2) and the look of the ground (lander_view.py).
BODIES = {
    "ice": {"gravity": 55.0, "name": "Titan"},
    "rock": {"gravity": 26.0, "name": "asteroid"},
}
BODY_KEYS = tuple(BODIES)

THRUST = 190.0                    # px/s^2 along the axis of the ship
TURN_SPEED = 2.0                  # rad/s
FUEL_START = 120.0                # units
FUEL_BURN = 6.0                   # units per second of thrust
FUEL_LOW = 25.0                   # the beeps start below this
START_Y = -1750.0                 # where the ship starts (the ground is round 0, its peaks at about -450)
CEILING = -2300.0
START_VX = (-70.0, 70.0)
MAX_STEP = 1.0 / 120.0

ZOOMS = (0.25, 0.5, 1.0)          # the size of the ship (and of the world) at each level
ZOOM_ALT = (900.0, 350.0)         # under these altitudes the view goes to the 2nd and the 3rd level
ZOOM_HYST = 1.12                  # (to zoom out again the altitude must pass the limit by this much)
ZOOM_RATE = 3.2                   # how fast the view slides from one level to the next (1/s)

# What a landing may be (px/s and radians): (vertical speed, horizontal speed, lean)
PERFECT = (22.0, 14.0, math.radians(4.0))
ROUGH = (48.0, 30.0, math.radians(12.0))
PERFECT_POINTS, ROUGH_POINTS = 500, 100
PERFECT_FUEL, ROUGH_FUEL = 50, 10
LAND_PAUSE = 3.2                  # seconds the message stays before the mission ends
BEEP_FAR, BEEP_NEAR = 1.0, 0.18
THRUST_SOUND_GAP = 0.2


def lean(angle):
    """How far the nose is from straight up (radians, 0..pi); `angle` = where the nose points (-pi/2 = up)."""
    return abs((angle + math.pi / 2 + math.pi) % (2 * math.pi) - math.pi)


def verdict(vx, vy, tilt):
    """The judgement of a touch on a landing zone: "perfect", "rough" or "crash"."""
    ax, ay = abs(vx), abs(vy)
    if vy < 0:                                                  # (going up: it cannot be a landing)
        return "crash"
    if ay <= PERFECT[0] and ax <= PERFECT[1] and tilt <= PERFECT[2]:
        return "perfect"
    if ay <= ROUGH[0] and ax <= ROUGH[1] and tilt <= ROUGH[2]:
        return "rough"
    return "crash"


def landing_points(kind, result, fuel):
    """(points of the landing, bonus of the fuel) of a perfect or rough landing on a zone of the kind `kind`."""
    units = int(max(0, fuel))
    if result == "perfect":
        return PERFECT_POINTS * PAD_BONUS[kind], PERFECT_FUEL * units
    if result == "rough":
        return ROUGH_POINTS * PAD_BONUS[kind], ROUGH_FUEL * units
    return 0, 0


def zoom_for(alt, current):
    """The index of the zoom level for the altitude `alt`; `current` (the index now) gives the hysteresis."""
    want = 0
    if alt <= ZOOM_ALT[0]:
        want = 1
    if alt <= ZOOM_ALT[1]:
        want = 2
    if want < current:                                           # coming back out: a little further than the limit
        limit = ZOOM_ALT[want] if want < len(ZOOM_ALT) else 0.0
        if alt <= limit * ZOOM_HYST:
            return current
    return want


class Terrain:
    """The ground: a height every STEP px (y down: smaller = higher), looping, with its flat landing zones, its craters and
    its boulders."""

    def __init__(self, style, seed=None):
        self.style = style
        self.seed = random.getrandbits(32) if seed is None else int(seed)
        rng = np.random.default_rng(self.seed)
        n = WORLD // STEP
        self.n = n
        xs = np.arange(n) * float(STEP)
        h = np.zeros(n)
        for k, (amp, wave) in enumerate(((250, 1), (170, 2), (120, 4), (70, 8), (30, 17), (12, 36))):
            ph = rng.uniform(0, 2 * math.pi)
            h += amp * np.sin(2 * math.pi * wave * xs / WORLD + ph) * (1.0 if k < 4 else rng.uniform(0.4, 0.8))
        # a few steep ridges and a rough fine detail
        for _ in range(7):
            cx, w, a = rng.uniform(0, WORLD), rng.uniform(60, 220), rng.uniform(-120, 160)
            d = np.minimum(np.abs(xs - cx), WORLD - np.abs(xs - cx))
            h += a * np.exp(-(d / w) ** 2)
        rough = rng.normal(0.0, 1.0, n)
        for _ in range(5):                                       # (smoothed noise: a gritty ground)
            rough = (np.roll(rough, 1) + rough * 2 + np.roll(rough, -1)) / 4.0
        h += rough * 60.0
        # craters (bowl and rim), more of them on the rock
        for _ in range(14 if style == "rock" else 6):
            cx, r = rng.uniform(0, WORLD), rng.uniform(70, 230)
            d = np.minimum(np.abs(xs - cx), WORLD - np.abs(xs - cx))
            bowl = np.clip(1 - (d / r) ** 2, 0, 1)
            h += (-0.35 * r * bowl + 0.06 * r * np.exp(-((d - r) / (0.18 * r)) ** 2)) * (1.0 if style == "rock" else 0.6)
        h -= h.mean()
        self.h = h
        self.pads = self._place_pads(rng)
        self.boulders = []
        for _ in range(170):
            bx = float(rng.uniform(0, WORLD))
            if any(self.dx(bx, p["x"]) < p["w"] / 2 + 60 for p in self.pads):
                continue
            r = float(rng.uniform(5, 22) if style == "rock" else rng.uniform(4, 15))
            self.boulders.append((bx, r, float(rng.uniform(0, 1))))

    @staticmethod
    def dx(a, b):
        """The distance between two x of the looping world."""
        d = abs((a - b) % WORLD)
        return min(d, WORLD - d)

    def _place_pads(self, rng):
        count = int(rng.integers(1, 4))
        kinds = [str(k) for k in rng.choice(list(PAD_SIZES), size=count)]
        pads = []
        tries = 0
        while len(pads) < count and tries < 400:
            tries += 1
            cx = float(rng.uniform(0, WORLD))
            if self.dx(cx, WORLD / 2) < 700:                    # (not under the start)
                continue
            if any(self.dx(cx, p["x"]) < 1100 for p in pads):
                continue
            pads.append({"kind": kinds[len(pads)], "x": cx, "w": float(PAD_SIZES[kinds[len(pads)]])})
        for p in pads:
            lo, hi = int((p["x"] - p["w"] / 2) // STEP) - 1, int((p["x"] + p["w"] / 2) // STEP) + 1   # (a sample of margin)
            idx = np.arange(lo, hi + 1) % self.n
            level = float(self.h[idx].mean())
            for i in range(lo - PAD_BLEND, hi + 1 + PAD_BLEND):
                if lo <= i <= hi:
                    self.h[i % self.n] = level
                else:
                    k = (lo - i) / PAD_BLEND if i < lo else (i - hi) / PAD_BLEND
                    s = 1.0 - k
                    self.h[i % self.n] = self.h[i % self.n] * k + level * s
            p["y"] = level
        return pads

    def ground(self, x):
        """The height of the ground at `x` (a number or an array)."""
        f = (np.asarray(x, dtype=float) % WORLD) / STEP
        i = np.floor(f).astype(int)
        t = f - i
        value = self.h[i % self.n] * (1.0 - t) + self.h[(i + 1) % self.n] * t
        return float(value) if np.ndim(value) == 0 else value

    def pad_at(self, x, margin=0.0):
        """The landing zone that covers `x` (the middle of a foot), or None."""
        for p in self.pads:
            if self.dx(x, p["x"]) <= p["w"] / 2 - margin:
                return p
        return None


def points_of(angle, x, y):
    """The points of the hull in the world, for a ship at (x, y) whose nose points to `angle`."""
    a = angle + math.pi / 2
    c, s = math.cos(a), math.sin(a)
    return [(x + lx * c - ly * s, y + lx * s + ly * c) for lx, ly in HULL]


class LanderFormation:
    """The field of the level: the ground, the ship's flight (world position, speed, fuel), the zoom and the end. Looks like
    a formation without enemies to the rest of the game."""

    def __init__(self, style=None, seed=None, speed_mult=1.0, rng=None):
        self.rng = rng if rng is not None else random.Random()
        self.style = style if style in BODIES else self.rng.choice(BODY_KEYS)
        self.gravity = BODIES[self.style]["gravity"]
        self.terrain = Terrain(self.style, seed)
        self.enemies = []
        self.bullets = []
        self.swarm = None
        self.sounds = None
        self.font = None
        self.text_cache = None
        self.view = None                    # lander_view.View, made by the first draw
        self.x = WORLD / 2.0                # the ship in the world
        self.y = START_Y
        self.vx = self.rng.uniform(*START_VX)
        self.vy = 0.0
        self.fuel = FUEL_START
        self.zoom_i = 0
        self.zoom = ZOOMS[0]
        self.thrusting = False
        self.phase = "flying"               # flying -> landed / crashed
        self.result = None                  # "perfect", "rough" or "crash"
        self.pad = None                     # the zone it landed on
        self.points = 0
        self.bonus = 0
        self.end_timer = 0.0
        self.time = 0.0
        self.beep_timer = 0.0
        self.thrust_sound = 0.0
        self.touch = None                   # (result, pad) set by fly() at the first touch, taken by tick()
        self.won = False

    # --- what the rest of the game asks of a formation ---
    def update(self, dt, player_x):
        return None

    def get_alive_enemies(self):
        return []

    def get_hittable_enemies(self):
        return []

    def remaining(self):
        return 0 if self.won else 1

    def swarm_remaining(self):
        return self.remaining()

    def all_dead(self):
        """The ship has landed (and the message has been read)."""
        return self.won

    def draw(self, surface):
        return None                         # (the view is drawn by draw_frame, under the HUD)

    # --- the flight ---
    def altitude(self):
        """Height of the feet over the ground under the ship (px), never below 0."""
        return max(0.0, float(self.terrain.ground(self.x)) - (self.y + FOOT_Y))

    def lean_now(self, angle):
        return lean(angle)

    def ship_scale(self):
        return self.zoom

    def fly(self, player, dt, turn, push):
        """One frame of the flight, called by the player (Player._update_asteroid). Returns whether the thruster burned."""
        if self.phase != "flying":
            self.thrusting = False
            return False
        player.ast_angle = (player.ast_angle + turn * TURN_SPEED * dt + math.pi) % (2 * math.pi) - math.pi
        burn = bool(push) and self.fuel > 0.0
        steps = max(1, int(math.ceil(dt / MAX_STEP)))
        h = dt / steps
        for _ in range(steps):
            ax, ay = 0.0, self.gravity
            if burn and self.fuel > 0.0:
                ax += math.cos(player.ast_angle) * THRUST
                ay += math.sin(player.ast_angle) * THRUST
                self.fuel = max(0.0, self.fuel - FUEL_BURN * h)
            self.vx += ax * h
            self.vy += ay * h
            self.x = (self.x + self.vx * h) % WORLD
            self.y += self.vy * h
            if self.y < CEILING:
                self.y, self.vy = CEILING, max(0.0, self.vy)
            if self._touch(player):
                burn = False
                break
        self.thrusting = burn
        # the zoom: the level of the altitude, then a slide towards it
        self.zoom_i = zoom_for(self.altitude(), self.zoom_i)
        target = ZOOMS[self.zoom_i]
        self.zoom += (target - self.zoom) * min(1.0, ZOOM_RATE * dt)
        if abs(self.zoom - target) < 0.002:
            self.zoom = target
        return burn

    def _touch(self, player):
        """Did a point of the hull go under the ground? Then judge it (first touch only) and stop the ship."""
        pts = points_of(player.ast_angle, self.x, self.y)
        under = [i for i, (px, py) in enumerate(pts) if py >= self.terrain.ground(px)]
        if not under:
            return False
        feet_ok = all(self.terrain.pad_at(pts[i][0]) is not None for i in FEET)
        pad = self.terrain.pad_at(pts[FEET[0]][0]) if feet_ok else None      # (the zones are far apart: one for both feet)
        result = "crash"
        if pad is not None:
            result = verdict(self.vx, self.vy, lean(player.ast_angle))
        if result != "crash":
            # put the lowest foot on the zone
            low = max(py for _, py in (pts[i] for i in FEET))
            self.y -= low - pad["y"]
        self.touch = (result, pad if result != "crash" else None)
        self.result = result
        self.pad = self.touch[1]
        self.phase = "landed" if result != "crash" else "crashed"
        self.thrusting = False
        if result != "crash":
            self.vx = self.vy = 0.0
        return True


def active(game):
    form = getattr(game, "formation", None)
    return form if isinstance(form, LanderFormation) else None


def _label(key):
    from i18n import t
    return t(key)


def tick(game):
    """Every frame of the level: the sounds, the touch, the end. A no-op in any other mission."""
    form = active(game)
    if form is None or game.stage_transition is not None:
        return
    p = game.player
    dt = game.dt
    form.time += dt
    snd = getattr(game, "sounds", None)
    if form.phase == "flying":
        alive = p.alive and not p.dying
        if form.thrusting and alive:
            form.thrust_sound -= dt
            if form.thrust_sound <= 0.0:
                form.thrust_sound = THRUST_SOUND_GAP
                _play(snd, "lander_thrust", volume=0.5)
        else:
            form.thrust_sound = 0.0
        if alive and form.fuel <= FUEL_LOW:                    # the beeps: faster and faster as the tank empties
            form.beep_timer -= dt
            if form.beep_timer <= 0.0:
                k = max(0.0, min(1.0, form.fuel / FUEL_LOW))
                form.beep_timer = BEEP_NEAR + (BEEP_FAR - BEEP_NEAR) * k
                _play(snd, "lander_beep", volume=0.6)
    if form.touch is not None and form.phase != "flying":
        result, pad = form.touch
        form.touch = None
        if result == "crash":
            _crash(game, form)
        else:
            pts, bonus = landing_points(pad["kind"], result, form.fuel)
            form.points, form.bonus = pts, bonus
            game._add_score(p, pts + bonus)
            _play(snd, "lander_land" if result == "perfect" else "lander_rough", volume=0.8)
            if result == "perfect":
                _play(snd, "1up", volume=0.5)
    if form.phase == "landed":
        form.end_timer += dt
        if form.end_timer >= LAND_PAUSE:
            form.won = True


def _crash(game, form):
    p = game.player
    if not p.alive or p.dying:
        return
    if p.burn_by_guardian():             # the big blast (ship_blast): one life, nothing saves the ship
        game.shake_amount = max(game.shake_amount, 30.0)
        _play(getattr(game, "sounds", None), "explosion_big", x=p.x)


def _play(snd, name, **kw):
    if snd is None:
        return
    try:
        snd.play(name, **kw)
    except Exception:
        log_exc("lander._play")


def message(form):
    """The announcement of the end (i18n key, colour type), or None while the ship is flying."""
    if form.phase == "landed":
        return ("lander_perfect" if form.result == "perfect" else "lander_rough",
                "success" if form.result == "perfect" else "special")
    if form.phase == "crashed":
        return "lander_crash", "danger"
    return None
