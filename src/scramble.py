"""The test level "Scramble" (story_state.py, id `test_scramble`): a remake of Konami's Scramble (1981) with the ships of the
hangar, in the settings of the Lunar Lander (the asteroid, Titan, Europa, Deimos, Triton: lander.BODIES).

The rules:

- A side-scrolling shoot'em up: the ship is turned a quarter round, its nose to the right. The ground and the ceiling slide
  from right to left at a constant speed (SCROLL px/s, by the clock: the same at 60 and at 144 Hz); the ship moves freely
  inside the screen (forward, back, up, down) and fires to the right.
- The course is about two and a half minutes long, in sections (SECTIONS): rolling hills, a cavern, an open stretch (the
  comets of the original, later), mountain peaks, narrows with steps. A passage at least GAP_MIN px high (three times the
  height of the turned ship) always runs between the ceiling and the ground, as wide as the ship is long.
- At the end the rock thins out, the scroll slows down and stops (a uniform braking over BRAKE px): the arena of the enemy
  base (src/scramble_base, later). Until it is there, reaching the arena wins the mission.
- Any touch of the rock costs a life; the ship then goes on from where it was, put back in the middle of the passage, and
  blinks for a while (it passes through nothing: the rock pushes it out). The Phenix form and the dome of the Shield are
  not hurt by the rock either: it pushes them out.
- The lives are those of the workshop; the dome and the Phenix form work as in every mission.

The player flies the real Player of the game (`Player.asteroid_mode` with `Player.scramble` set to the formation below). The
formation looks like one without enemies to the rest of the game; `tick(game)` runs it every frame; the view is in
src/scramble_view.py. The world is the course: x runs along it (0 = the start, the camera `cam` is the world x of the left
edge of the screen), y is the y of the screen (the view never moves up or down).
"""
import math
import random

import numpy as np

import lander
from errlog import log_exc
from settings import BASE_HEIGHT, BASE_WIDTH, BULLET_SPEED

W, H = BASE_WIDTH, BASE_HEIGHT
STEP = 8                          # one height of the ground and of the ceiling every STEP px of the course
SCROLL = 180.0                    # px/s: the speed of the scroll (3 px a frame at 60 Hz, 1.25 at 144 Hz)
SHIP_SPAN = 60                    # the height of the turned ship (both hulls: measured on their sprites)
SHIP_LEN = 88                     # ... and its length (the Phenix, the longer of the two)
GAP_MIN = 3 * SHIP_SPAN           # the passage between the ceiling and the ground, never lower than this...
GAP_WINDOW = SHIP_LEN + 2 * STEP  # ... over this length (the ship must fit in it, not only a line)
BAND_MIN = 18                     # the thinnest band of rock at the top and at the bottom of the screen
SLOPE_MAX = 2.4                   # the steepest slope of the rock (dy/dx): no wall is quite upright
X_MIN, X_MAX = 56.0, W * 0.62     # where the middle of the ship may be on the screen
START_X = 230.0
CALM = 1400.0                     # px of the course at the start where the rock is gentle
TRANSITION = 420.0                # px over which one section melts into the next
BRAKE = 1500.0                    # px of the course over which the scroll brakes to a stop (2 * BRAKE / SCROLL seconds)
ARENA_BAND = (34.0, 40.0)         # the ceiling and the ground of the arena of the base (px)
SOFT_REACH = 160.0                # px: how far the rock may come back over the edge of a carving, at its far end
ARENA_WAIT = 2.0                 # seconds in the arena before the mission is won (until the base is there)
# The sections of the course, in order: (name, seconds at full speed, the depth of the ceiling and of the ground: (base, waves,
# rough), and what stands out of them: "drips" = stalactites, "peaks" = sharp mountains, "steps" = terraces).
SECTIONS = (
    ("hills", 26.0, {"ceil": (24, 6, 3), "floor": (150, 95, 10), "peaks": 0, "drips": 0, "steps": 0}),
    ("cavern", 30.0, {"ceil": (150, 85, 10), "floor": (150, 70, 10), "peaks": 0, "drips": 14, "steps": 0}),
    ("comets", 20.0, {"ceil": (26, 6, 3), "floor": (48, 14, 6), "peaks": 0, "drips": 0, "steps": 0}),
    ("peaks", 28.0, {"ceil": (60, 30, 6), "floor": (150, 60, 12), "peaks": 13, "drips": 0, "steps": 0}),
    ("narrows", 26.0, {"ceil": (210, 70, 4), "floor": (220, 70, 4), "peaks": 0, "drips": 0, "steps": 46}),
    ("approach", 12.0, {"ceil": (70, 20, 4), "floor": (80, 22, 4), "peaks": 0, "drips": 0, "steps": 0}),
)
SECTION_KEYS = tuple(s[0] for s in SECTIONS)
MENU_ORDER = lander.MENU_ORDER    # the choice of the test (story.py, screen "lander_pick" for the Scramble)
BODY_KEYS = lander.BODY_KEYS
MAX_SHOTS = 3                     # the ship's shots on the screen
SHOT_GAP = 0.14                   # seconds between two shots
SHOT_SPEED = BULLET_SPEED         # px/s on the screen (to the right)
# the outline of the turned ship (nose to the right), for the touch of the rock: (x along the hull, half its height there)
HULL = ((-40.0, 10.0), (-30.0, 22.0), (-14.0, 29.0), (2.0, 26.0), (18.0, 15.0), (32.0, 8.0), (42.0, 2.0))


def _smooth(values, passes):
    out = np.asarray(values, dtype=float)
    for _ in range(passes):
        out = np.concatenate(([out[0]], (out[:-2] + 2 * out[1:-1] + out[2:]) / 4.0, [out[-1]]))
    return out


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Course:
    """The rock of the whole course: the y of the ceiling (`ceil`: its lower edge) and of the ground (`floor`: its upper edge)
    every STEP px, with where each section begins, where the scroll stops (`stop`) and the length of the world (`length`)."""

    def __init__(self, style, seed=None):
        self.style = style
        self.seed = random.getrandbits(32) if seed is None else int(seed)
        rng = np.random.default_rng(self.seed)
        # where the sections are (world px): the scroll runs at full speed until the braking, which ends at `stop`
        starts, x = [], 0.0
        for _, seconds, _ in SECTIONS:
            starts.append(x)
            x += seconds * SCROLL
        self.starts = starts
        self.course_end = x                          # the end of the last section: the braking starts BRAKE before
        self.stop = x                                # the camera stops here (the arena fills the screen from there)
        self.brake_from = self.stop - BRAKE
        self.length = self.stop + W + 4 * STEP
        n = int(math.ceil(self.length / STEP)) + 2
        self.n = n
        xs = np.arange(n) * float(STEP)
        self.xs = xs
        ceil_d = np.zeros(n)
        floor_d = np.zeros(n)
        weights = self._weights(xs)
        for k, (_, _, look) in enumerate(SECTIONS):
            w = weights[k]
            if not w.any():
                continue
            c = self._profile(xs, look["ceil"], rng) + self._drips(xs, look["drips"], k, rng)
            f = self._profile(xs, look["floor"], rng) + self._peaks(xs, look["peaks"], k, rng)
            if look["steps"]:
                c = self._terraces(c, look["steps"])
                f = self._terraces(f, look["steps"])
            ceil_d += w * c
            floor_d += w * f
        # the start is gentle (a low ground, a thin ceiling): the player gets the feel of it
        calm = smoothstep((xs - 300.0) / CALM)
        ceil_d = ceil_d * calm + 24.0 * (1 - calm)
        floor_d = floor_d * calm + 110.0 * (1 - calm)
        # the arena: from the start of the braking the rock thins down to the bands of the base
        thin = smoothstep((xs - self.brake_from) / BRAKE)
        ceil_d = ceil_d * (1 - thin) + ARENA_BAND[0] * thin
        floor_d = floor_d * (1 - thin) + ARENA_BAND[1] * thin
        self.ceil = np.maximum(ceil_d, BAND_MIN)
        self.floor = H - np.maximum(floor_d, BAND_MIN)
        self._limit_slopes()
        self._open_passage()
        self._limit_slopes()                         # (the carving only ever takes rock away: still a passage)

    # --- making it
    def _weights(self, xs):
        """The share of each section at each x (they melt into one another over TRANSITION px)."""
        out = []
        bounds = list(self.starts[1:])
        for k in range(len(SECTIONS)):
            rise = smoothstep((xs - (bounds[k - 1] - TRANSITION / 2)) / TRANSITION) if k > 0 else np.ones_like(xs)
            fall = 1 - smoothstep((xs - (bounds[k] - TRANSITION / 2)) / TRANSITION) if k < len(bounds) else np.ones_like(xs)
            out.append(rise * fall)
        total = np.sum(out, axis=0)
        return [w / total for w in out]

    @staticmethod
    def _profile(xs, look, rng):
        base, amp, rough = look
        h = np.full(len(xs), float(base))
        for wave, share in ((1100.0, 1.0), (520.0, 0.6), (250.0, 0.34), (120.0, 0.16)):
            h += amp * share * np.sin(2 * math.pi * xs / wave * rng.uniform(0.8, 1.25) + rng.uniform(0, 2 * math.pi))
        grit = _smooth(rng.normal(0.0, 1.0, len(xs)), 3)
        return h + grit * rough * 2.2

    def _drips(self, xs, count, k, rng):
        """Stalactites hanging from the ceiling of the section k."""
        out = np.zeros(len(xs))
        lo, hi = self._span(k)
        for _ in range(count):
            cx, w, a = rng.uniform(lo, hi), rng.uniform(26, 70), rng.uniform(70, 170)
            out += a * np.exp(-((xs - cx) / w) ** 2)
        return out

    def _peaks(self, xs, count, k, rng):
        """Sharp mountains standing on the ground of the section k."""
        out = np.zeros(len(xs))
        lo, hi = self._span(k)
        for _ in range(count):
            cx, w, a = rng.uniform(lo, hi), rng.uniform(110, 240), rng.uniform(110, 260)
            out = np.maximum(out, a * np.clip(1 - np.abs(xs - cx) / w, 0, 1) ** 1.25)
        return out

    @staticmethod
    def _terraces(depth, step):
        """Flat steps (the city of the original, in rock)."""
        stepped = np.round(depth / step) * step
        return _smooth(stepped, 1)

    def _span(self, k):
        lo = self.starts[k]
        hi = self.starts[k + 1] if k + 1 < len(self.starts) else self.course_end
        return lo + TRANSITION / 2, hi - TRANSITION / 2

    def _limit_slopes(self):
        """No slope steeper than SLOPE_MAX: the rock is taken away (the ground lowered, the ceiling raised) where it rises too
        fast, in both directions."""
        d = SLOPE_MAX * STEP
        f, c = self.floor, self.ceil
        for _ in range(2):
            for i in range(1, self.n):
                f[i] = max(f[i], f[i - 1] - d)
                c[i] = min(c[i], c[i - 1] + d)
            for i in range(self.n - 2, -1, -1):
                f[i] = max(f[i], f[i + 1] - d)
                c[i] = min(c[i], c[i + 1] + d)
        np.clip(f, BAND_MIN + GAP_MIN, H - BAND_MIN, out=f)
        np.clip(c, BAND_MIN, H - BAND_MIN - GAP_MIN, out=c)

    def _open_passage(self):
        """Where the ship would not fit (over GAP_WINDOW px the lowest ceiling and the highest ground are less than GAP_MIN
        apart), the rock is carved: a passage of GAP_MIN centred between them, with soft edges."""
        half = int(math.ceil(GAP_WINDOW / 2 / STEP))
        soft = 10                                     # samples over which a carving fades out on each side
        bowl = np.cos(np.linspace(0, math.pi / 2, soft + 1)[1:]) ** 2      # (from nearly 1 next to it down to 0)
        for _ in range(6):
            changed = False
            for i in range(self.n):
                a, b = max(0, i - half), min(self.n, i + half + 1)
                low_ceil = float(self.ceil[a:b].max())
                high_floor = float(self.floor[a:b].min())
                if high_floor - low_ceil >= GAP_MIN - 0.01:
                    continue
                mid = (low_ceil + high_floor) / 2.0
                mid = min(max(mid, BAND_MIN + GAP_MIN / 2.0), H - BAND_MIN - GAP_MIN / 2.0)
                top, bottom = mid - GAP_MIN / 2.0 - 1.0, mid + GAP_MIN / 2.0 + 1.0
                self.ceil[a:b] = np.minimum(self.ceil[a:b], top)
                self.floor[a:b] = np.maximum(self.floor[a:b], bottom)
                for j, k in enumerate(bowl):              # (the edges of the carving fade out: no step in the rock)
                    reach = (1.0 - k) * SOFT_REACH
                    for idx in (a - 1 - j, b + j):
                        if 0 <= idx < self.n:
                            self.ceil[idx] = min(self.ceil[idx], top + reach)
                            self.floor[idx] = max(self.floor[idx], bottom - reach)
                changed = True
            if not changed:
                break

    # --- asking it
    def _at(self, arr, x):
        f = np.clip(np.asarray(x, dtype=float), 0.0, (self.n - 1) * STEP) / STEP
        i = np.minimum(np.floor(f).astype(int), self.n - 2)
        t = f - i
        value = arr[i] * (1.0 - t) + arr[i + 1] * t
        return float(value) if np.ndim(value) == 0 else value

    def ceiling(self, x):
        """The y of the lower edge of the ceiling at the world x (a number or an array)."""
        return self._at(self.ceil, x)

    def ground(self, x):
        """The y of the upper edge of the ground at the world x (a number or an array)."""
        return self._at(self.floor, x)

    def passage(self, x):
        """The middle of the passage at x, and its height."""
        c, f = self.ceiling(x), self.ground(x)
        return (c + f) / 2.0, f - c

    def section_at(self, x):
        """The name of the section at the world x."""
        name = SECTION_KEYS[0]
        for (key, _, _), start in zip(SECTIONS, self.starts):
            if x >= start:
                name = key
        return name


def hull_points(x, y):
    """The points of the outline of the turned ship whose middle is at (x, y): its upper and its lower edge."""
    top = [(x + lx, y - hy) for lx, hy in HULL]
    low = [(x + lx, y + hy) for lx, hy in HULL]
    return top, low


class Shot:
    def __init__(self, x, y, vx, vy):
        self.x, self.y, self.vx, self.vy = float(x), float(y), float(vx), float(vy)
        self.alive = True


class Spark:
    """A bit of debris (cosmetic), in world coordinates."""

    def __init__(self, x, y, vx, vy, life, size):
        self.x, self.y, self.vx, self.vy = float(x), float(y), float(vx), float(vy)
        self.life = self.max = float(life)
        self.size = float(size)


class ScrambleFormation:
    """The field of the level: the course, the scroll, the ship's shots and the end. Looks like a formation without enemies to
    the rest of the game."""

    def __init__(self, style=None, seed=None, speed_mult=1.0, rng=None):
        self.rng = rng if rng is not None else random.Random()
        self.style = style if style in lander.BODIES else self.rng.choice(BODY_KEYS)
        self.course = Course(self.style, seed)
        self.enemies = []
        self.bullets = []
        self.swarm = None
        self.sounds = None
        self.font = None
        self.text_cache = None
        self.view = None                    # scramble_view.View, made by the first draw
        self.cam = 0.0                      # the world x of the left edge of the screen
        self.speed = SCROLL
        self.time = 0.0
        self.phase = "flying"               # flying -> arena (the scroll has stopped) -> won
        self.arena_time = 0.0
        self.shots = []
        self.sparks = []
        self.fire_cd = 0.0
        self.tip = (180, 220, 255)
        self.started = False
        self.won = False
        self.deaths = 0

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
        """The course is flown (and, later, the base is destroyed)."""
        return self.won

    def draw(self, surface):
        """The shots and the sparks (the rock is drawn by the view, under everything)."""
        import scramble_view
        scramble_view.draw_items(surface, self)

    # --- the scroll
    def speed_at(self, cam):
        """The speed of the scroll with the camera at `cam`: full speed, then a uniform braking to a stop at `stop`."""
        c = self.course
        if cam >= c.stop:
            return 0.0
        if cam <= c.brake_from:
            return SCROLL
        return SCROLL * math.sqrt(max(0.0, c.stop - cam) / BRAKE)

    def advance(self, dt):
        """Slide the camera for `dt` seconds (exact for the braking: the same at any frame rate). Returns how far it went."""
        c = self.course
        before = self.cam
        left = dt
        if self.cam < c.brake_from:
            run = min(left, (c.brake_from - self.cam) / SCROLL)
            self.cam += run * SCROLL
            left -= run
        if left > 0 and self.cam < c.stop:
            # the braking: v = SCROLL * sqrt(rest / BRAKE), so the rest falls as a square in time
            rest = c.stop - self.cam
            u = math.sqrt(rest) - SCROLL * left / (2.0 * math.sqrt(BRAKE))
            self.cam = c.stop - (u * u if u > 0 else 0.0)
            if self.cam > c.stop - 0.05:
                self.cam = c.stop
        self.speed = self.speed_at(self.cam)
        return self.cam - before

    def progress(self):
        return max(0.0, min(1.0, self.cam / self.course.stop))

    # --- the ship
    def ship_world(self, player):
        return self.cam + player.x, player.y

    def fly(self, player, dt, dx, dy, speed):
        """One frame of the ship, called by the player (Player._update_asteroid): it moves on the screen, nose to the right,
        and stays inside its part of the screen and of the passage's screen."""
        player.ast_angle = 0.0
        if self.phase == "won":
            return False
        mag = math.hypot(dx, dy)
        if mag > 1.0:
            dx, dy = dx / mag, dy / mag
        player.x = min(X_MAX, max(X_MIN, player.x + dx * speed * dt))
        player.y = min(H - 30.0, max(30.0, player.y + dy * speed * dt))
        player.ast_vx, player.ast_vy = dx * speed + self.speed, dy * speed
        return bool(dx > 0)

    def rock_overlap(self, player):
        """How far the outline of the ship is in the rock: (into the ceiling, into the ground), both 0 when it is clear."""
        wx, y = self.ship_world(player)
        top, low = hull_points(wx, y)
        xs = np.array([p[0] for p in top])
        c = self.course.ceiling(xs)
        f = self.course.ground(xs)
        up = float(np.max(c - np.array([p[1] for p in top])))
        down = float(np.max(np.array([p[1] for p in low]) - f))
        return max(0.0, up), max(0.0, down)

    def push_out(self, player):
        """Put the ship back in the passage (it touched the rock while nothing can hurt it)."""
        up, down = self.rock_overlap(player)
        if up > 0 and down > 0:
            self.recentre(player)
        elif up > 0:
            player.y += up
        elif down > 0:
            player.y -= down

    def recentre(self, player):
        """The middle of the passage under the ship (where it goes on after a lost life)."""
        wx, _ = self.ship_world(player)
        xs = np.linspace(wx - SHIP_LEN / 2, wx + SHIP_LEN / 2, 7)
        c = float(np.max(self.course.ceiling(xs)))
        f = float(np.min(self.course.ground(xs)))
        player.y = (c + f) / 2.0


def active(game):
    form = getattr(game, "formation", None)
    return form if isinstance(form, ScrambleFormation) else None


def _immune(player):
    return bool(getattr(player, "is_phenix", False)) or player.invulnerable > 0


def _ship_hit(game, form):
    """The ship touched the rock (or, later, a shot or an enemy): a life goes; it goes on from where it was, in the middle of
    the passage. Returns True when a life was taken."""
    p = game.player
    if not p.alive or p.dying or _immune(p):
        return False
    old = (p.x, p.y)
    p.hit()
    if not p.just_lost_life and not p.dying:
        return False
    form.deaths += 1
    game._ship_boom(p, "gameover" if p.dying else "bullet")
    game.shake_amount = 22.0 if p.dying else 12.0
    _play(getattr(game, "sounds", None), "explosion_big" if p.dying else "explosion", x=old[0])
    wx = form.cam + old[0]
    for _ in range(26):
        a = form.rng.uniform(0, 2 * math.pi)
        v = form.rng.uniform(80, 330)
        form.sparks.append(Spark(wx, old[1], math.cos(a) * v, math.sin(a) * v, form.rng.uniform(0.4, 1.1),
                                 form.rng.uniform(2.0, 5.0)))
    if not p.dying:
        form.recentre(p)
    return True


def tick(game):
    """Every frame of the level: the scroll, the ship's shots, the touch of the rock, the end. A no-op in any other mission."""
    form = active(game)
    if form is None or game.stage_transition is not None:
        return
    p = game.player
    dt = game.dt
    form.time += dt
    form.started = True
    import asteroids
    form.tip = asteroids.tip_color(p)
    form.advance(dt)
    alive = p.alive and not p.dying
    # --- the ship fires (to the right)
    form.fire_cd = max(0.0, form.fire_cd - dt)
    if alive and getattr(p, "ast_fire", False) and form.fire_cd <= 0 and len(form.shots) < MAX_SHOTS \
            and not (getattr(p, "uses_shield", False) and p.is_phenix):
        form.fire_cd = SHOT_GAP
        mult = float(getattr(p, "bullet_speed_mult", 1.0) or 1.0)
        form.shots.append(Shot(form.cam + p.x + 44, p.y, SHOT_SPEED * mult + form.speed, 0.0))
        _play(getattr(game, "sounds", None), "shoot", volume=0.45, x=p.x)
    p.ast_fire = False
    # --- the shots: they fly on, die in the rock or out of the screen
    course = form.course
    for s in form.shots:
        s.x += s.vx * dt
        s.y += s.vy * dt
        if s.x > form.cam + W + 40:
            s.alive = False
        elif s.y <= course.ceiling(s.x) or s.y >= course.ground(s.x):
            s.alive = False
            for _ in range(5):
                a = form.rng.uniform(math.pi * 0.5, math.pi * 1.5)
                v = form.rng.uniform(60, 200)
                form.sparks.append(Spark(s.x, s.y, math.cos(a) * v, math.sin(a) * v, form.rng.uniform(0.15, 0.4),
                                         form.rng.uniform(1.0, 2.5)))
    form.shots = [s for s in form.shots if s.alive]
    for sp in form.sparks:
        sp.x += sp.vx * dt
        sp.y += sp.vy * dt
        sp.vy += 220.0 * dt
        sp.life -= dt
    form.sparks = [sp for sp in form.sparks if sp.life > 0]
    # --- the rock
    if alive:
        up, down = form.rock_overlap(p)
        if up > 0 or down > 0:
            if _immune(p):
                form.push_out(p)
            else:
                _ship_hit(game, form)
    # --- the end: the scroll has stopped in the arena (the base comes in a later step)
    if form.phase == "flying" and form.cam >= course.stop:
        form.phase = "arena"
    if form.phase == "arena" and alive:
        form.arena_time += dt
        if form.arena_time >= ARENA_WAIT:
            form.phase = "won"
            form.won = True


def _play(snd, name, **kw):
    if snd is None:
        return
    try:
        snd.play(name, **kw)
    except Exception:
        log_exc("scramble._play")
