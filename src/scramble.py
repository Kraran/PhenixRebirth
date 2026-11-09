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
  base (src/scramble_base.py). Its boss killed and the base blown up, the mission is won.
- Any touch of the rock costs a life; the ship then goes on from where it was, put back in the middle of the passage, and
  blinks for a while (it passes through nothing: the rock pushes it out). The Phenix form and the dome of the Shield are
  not hurt by the rock either: it pushes them out.
- The lives are those of the workshop; the dome and the Phenix form work as in every mission.
- Missile stations stand on the rock (place_stations): each one fires its missiles straight up (or down from the ceiling)
  when the ship comes, timed to cross its height about when it gets there. A shot destroys a missile (MISSILE_POINTS) or a
  station (the points of a green bird); a missile or a station that touches the ship costs a life (the dome takes a
  missile, the Phenix form burns both).
- Waves of birds and, in the comets section, comets (src/scramble_birds.py).

THE ENDLESS RAID (BONUS FINAL - Scramble, `endless`): the base blown up, the run goes on: after LOOP_PAUSE the course starts
again from its beginning, a new one, with BOOST_STEP (10 %) more enemies each time (more missile stations firing sooner,
more waves of birds, more comets: Tune `boost`), until the last life is lost (the GAME OVER).

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
# The sections of the course, in order: (name, seconds at full speed, the depth of the ceiling and of the ground: (base, waves,
# rough), and what stands out of them: "drips" = stalactites, "peaks" = sharp mountains, "steps" = terraces).
SECTIONS = (
    ("hills", 26.0, {"ceil": (24, 6, 3), "floor": (150, 95, 10), "peaks": 0, "drips": 0, "steps": 0,
                     "stations": (230, 470, 0.0)}),
    ("cavern", 30.0, {"ceil": (150, 85, 10), "floor": (150, 70, 10), "peaks": 0, "drips": 14, "steps": 0,
                      "stations": (220, 460, 0.45)}),
    ("comets", 20.0, {"ceil": (26, 6, 3), "floor": (48, 14, 6), "peaks": 0, "drips": 0, "steps": 0,
                      "stations": None}),
    ("peaks", 28.0, {"ceil": (60, 30, 6), "floor": (150, 60, 12), "peaks": 13, "drips": 0, "steps": 0,
                     "stations": (230, 480, 0.2)}),
    ("narrows", 26.0, {"ceil": (210, 70, 4), "floor": (220, 70, 4), "peaks": 0, "drips": 0, "steps": 46,
                       "stations": (210, 430, 0.5)}),
    ("approach", 12.0, {"ceil": (70, 20, 4), "floor": (80, 22, 4), "peaks": 0, "drips": 0, "steps": 0,
                        "stations": (380, 700, 0.4)}),
)
# "stations": (the gap between two missile stations, from .. to, in px of the course; the share of them hanging from the
# ceiling), None: no station in that section.
SECTION_KEYS = tuple(s[0] for s in SECTIONS)
SECTION_LOOK = {key: look for key, _, look in SECTIONS}

# The difficulty of a course: five levels ("paliers"), for the raids of the Adventure on the five settings. 5 is the full
# Scramble of the test (the constants of the modules: every key left out of a level takes them). The sections: (name,
# seconds at full speed), in order. "gap": the lowest passage in ship heights; "stations": the share of missile stations
# (1: as many as at 5); "homing": how hard their missiles home in (0: they fly straight); "comets": the share of comets;
# "wave_gap" / "green": the waves of birds; "columns" / "turrets": the wall of the base and its turrets (rows of bricks);
# "bullets": the boss's shots on the screen at once; "boss_hp": shots through a hole to kill it (never fewer than 3).
LEVEL_MAX = 5
BOOST_STEP = 0.10                 # the endless raid: this many more enemies at each new course (10 %)
LOOP_PAUSE = 3.5                  # seconds between the base blown up and the next course (the endless raid)
LEVELS = {
    1: {"sections": (("hills", 30.0), ("cavern", 36.0), ("approach", 12.0)),
        "scroll": 150.0, "gap": 3.6, "stations": 0.6, "reload": 3.6, "homing": 0.0, "comets": 0.0,
        "wave_gap": (10.0, 14.0), "green": (0.0, 0.2), "columns": 2, "turrets": (9, 22), "bullets": 3, "boss_hp": 3},
    2: {"sections": (("hills", 26.0), ("cavern", 30.0), ("peaks", 28.0), ("approach", 12.0)),
        "scroll": 158.0, "gap": 3.45, "stations": 0.7, "reload": 3.3, "homing": 0.0, "comets": 0.0,
        "wave_gap": (9.0, 13.0), "green": (0.05, 0.3), "columns": 2, "turrets": (9, 22), "bullets": 3, "boss_hp": 3},
    3: {"sections": (("hills", 26.0), ("cavern", 28.0), ("comets", 20.0), ("peaks", 26.0), ("approach", 12.0)),
        "scroll": 165.0, "gap": 3.3, "stations": 0.8, "reload": 3.0, "homing": 0.5, "comets": 0.5,
        "wave_gap": (8.0, 12.0), "green": (0.15, 0.45), "columns": 3, "turrets": (5, 15, 26), "bullets": 4, "boss_hp": 4},
    4: {"sections": (("hills", 24.0), ("cavern", 27.0), ("comets", 18.0), ("peaks", 25.0), ("narrows", 20.0),
                     ("approach", 12.0)),
        "scroll": 172.0, "gap": 3.15, "stations": 0.9, "reload": 2.8, "homing": 0.75, "comets": 0.75,
        "wave_gap": (7.0, 11.0), "green": (0.2, 0.55), "columns": 3, "turrets": (5, 15, 26), "bullets": 4, "boss_hp": 4},
    5: {},
}


class Tune:
    """The numbers of one level of difficulty (LEVELS), read by the course, the sky and the base."""

    def __init__(self, level=LEVEL_MAX, boost=1.0):
        """`boost`: the endless raid makes its enemies that much more numerous (1.1 = 10 % more stations, waves, comets)."""
        import scramble_birds as sb
        import scramble_base as sbase
        self.level = max(1, min(LEVEL_MAX, int(level or LEVEL_MAX)))
        self.boost = max(1.0, float(boost or 1.0))
        d = LEVELS[self.level]
        plan = d.get("sections") or tuple((key, seconds) for key, seconds, _ in SECTIONS)
        self.sections = tuple((key, float(seconds), SECTION_LOOK[key]) for key, seconds in plan)
        self.keys = tuple(key for key, _, _ in self.sections)
        self.scroll = float(d.get("scroll", SCROLL))
        self.gap_min = GAP_MIN if "gap" not in d else d["gap"] * SHIP_SPAN
        self.stations = float(d.get("stations", 1.0))
        self.reload = float(d.get("reload", STATION_RELOAD))
        self.homing = float(d.get("homing", 1.0))
        self.comets = float(d.get("comets", 1.0))
        self.wave_gap = tuple(d.get("wave_gap", sb.WAVE_GAP))
        self.green = tuple(d.get("green", sb.GREEN_SHARE))
        self.columns = int(d.get("columns", sbase.COLUMNS))
        self.turret_rows = tuple(d.get("turrets", sbase.TURRET_ROWS))
        self.bullets = int(d.get("bullets", sbase.BULLET_MAX))
        self.boss_hp = int(d.get("boss_hp", sbase.BOSS_HP))
        if self.boost > 1.0:                       # (the endless raid: more stations, firing sooner; more birds, more comets)
            self.stations *= self.boost
            self.reload /= self.boost
            self.comets *= self.boost
            self.wave_gap = tuple(g / self.boost for g in self.wave_gap)
MENU_ORDER = lander.MENU_ORDER    # the choice of the test (story.py, screen "lander_pick" for the Scramble)
BODY_KEYS = lander.BODY_KEYS
MAX_SHOTS = 3                     # the ship's shots on the screen
SHOT_GAP = 0.14                   # seconds between two shots
SHOT_SPEED = BULLET_SPEED         # px/s on the screen (to the right)
# The missile stations (src/scramble_view.py draws them): small launchers standing on the ground or hanging from the ceiling.
# Each one holds STATION_MISSILES missiles; when the ship comes near (the station a little ahead of it on the screen) it fires
# them one by one, straight up (or down from the ceiling): the missile speeds up and flies on until it meets the rock or
# leaves the screen. Stations and missiles are destroyed by a shot.
STATION_W, STATION_H = 55.0, 37.0 # its footprint on the rock and how far it stands out of it
STATION_ROUGH = 44.0              # the rock under it may not vary more than this (px): it is then cut flat (a pad) ...
STATION_FLAT = 1.0                # ... so that, once it stands, the rock under it is flat to this
PAD_SLOPE = 1.5                   # the slope of the rock cut away on each side of a pad
STATION_FIRST = CALM + 600.0      # no station before this (world px)
STATION_MISSILES = 2
STATION_RELOAD = 2.6              # seconds between two missiles of a station
STATION_RANGE = (40.0, 900.0)     # it only fires while it is this far ahead of the ship on the screen (px) ...
STATION_LEAD = (-0.12, 0.45)      # ... at the moment its missile would cross the ship's height when the ship gets there, give
                                  # or take this (s, drawn for each station: some fire a little late, most a little early)
MISSILE_W, MISSILE_H = 12.0, 36.0
MISSILE_SPEED = (70.0, 470.0)     # px/s: at the launch and at the most
MISSILE_ACCEL = 560.0             # px/s^2
MISSILE_POINTS = 10
# The missiles home in a little: for their first HOMING_TIME seconds, and until they have passed the height of the ship, they
# slide sideways towards it (at most HOMING_VX px/s, reached at HOMING_ACCEL): enough to punish a ship that stays put, not
# enough to follow one that dodges.
HOMING_TIME = 1.0
HOMING_VX = 50.0
HOMING_ACCEL = 180.0
HOMING_GAIN = 2.5                 # (the wanted sideways speed for each px of distance, before the limit)
STATION_KIND = 2                  # a station is worth a green bird (game._enemy_points of the stage 2)
SHIP_BOX = (36.0, 22.0)           # half the size of the box of the ship against the missiles and the stations
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

    def __init__(self, style, seed=None, level=LEVEL_MAX, boost=1.0):
        self.style = style
        self.seed = random.getrandbits(32) if seed is None else int(seed)
        self.tune = tune = Tune(level, boost)
        self.sections = tune.sections                # (name, seconds, look) of this level
        self.scroll = tune.scroll
        self.gap_min = tune.gap_min
        rng = np.random.default_rng(self.seed)
        # where the sections are (world px): the scroll runs at full speed until the braking, which ends at `stop`
        starts, x = [], 0.0
        for _, seconds, _ in self.sections:
            starts.append(x)
            x += seconds * self.scroll
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
        for k, (_, _, look) in enumerate(self.sections):
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
        for k in range(len(self.sections)):
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
        gap = self.gap_min
        np.clip(f, BAND_MIN + gap, H - BAND_MIN, out=f)
        np.clip(c, BAND_MIN, H - BAND_MIN - gap, out=c)

    def _open_passage(self):
        """Where the ship would not fit (over GAP_WINDOW px the lowest ceiling and the highest ground are less than GAP_MIN
        apart), the rock is carved: a passage of GAP_MIN centred between them, with soft edges."""
        half = int(math.ceil(GAP_WINDOW / 2 / STEP))
        soft = 10                                     # samples over which a carving fades out on each side
        bowl = np.cos(np.linspace(0, math.pi / 2, soft + 1)[1:]) ** 2      # (from nearly 1 next to it down to 0)
        gap = self.gap_min                              # (this level's)
        for _ in range(6):
            changed = False
            for i in range(self.n):
                a, b = max(0, i - half), min(self.n, i + half + 1)
                low_ceil = float(self.ceil[a:b].max())
                high_floor = float(self.floor[a:b].min())
                if high_floor - low_ceil >= gap - 0.01:
                    continue
                mid = (low_ceil + high_floor) / 2.0
                mid = min(max(mid, BAND_MIN + gap / 2.0), H - BAND_MIN - gap / 2.0)
                top, bottom = mid - gap / 2.0 - 1.0, mid + gap / 2.0 + 1.0
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

    def cut_pad(self, x, side, level):
        """Cut the rock flat at `level` under a station at x (a pad as wide as the station), with slopes of PAD_SLOPE on each
        side. It only ever takes rock away: the passage can only grow."""
        half = STATION_W / 2 + STEP
        i0, i1 = max(0, int(math.floor((x - half) / STEP))), min(self.n - 1, int(math.ceil((x + half) / STEP)))
        arr = self.floor if side == "floor" else self.ceil
        cut = (lambda v, lim: max(v, lim)) if side == "floor" else (lambda v, lim: min(v, lim))
        sign = -1.0 if side == "floor" else 1.0
        for i in range(i0, i1 + 1):
            arr[i] = cut(arr[i], level)
        for start, step in ((i0 - 1, -1), (i1 + 1, 1)):        # (outwards, until the slope meets the rock)
            i, d = start, PAD_SLOPE * STEP
            while 0 <= i < self.n:
                lim = level + sign * d
                if arr[i] == cut(arr[i], lim):
                    break
                arr[i] = lim
                i += step
                d += PAD_SLOPE * STEP

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
        name = self.sections[0][0]
        for (key, _, _), start in zip(self.sections, self.starts):
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


class Station:
    """A missile launcher on the rock: its world x, the y of the rock under it, "floor" or "ceil"."""

    def __init__(self, x, base, side):
        self.x, self.base, self.side = float(x), float(base), side
        self.alive = True
        self.missiles = STATION_MISSILES
        self.reload = 0.0
        self.loaded = True                       # a missile stands on it, ready
        self.lead = 0.0                          # (STATION_LEAD: set by place_stations)

    @property
    def dir(self):
        """Where its missiles fly: -1 = up (a station on the ground), +1 = down (one on the ceiling)."""
        return -1 if self.side == "floor" else 1

    def box(self):
        """(left, top, right, bottom) in the world."""
        if self.side == "floor":
            return self.x - STATION_W / 2, self.base - STATION_H, self.x + STATION_W / 2, self.base
        return self.x - STATION_W / 2, self.base, self.x + STATION_W / 2, self.base + STATION_H

    def full_box(self):
        """Its box with the missile standing on it, while it is loaded: a shot on that missile blows the station up too."""
        l, t, r, b = self.box()
        if not self.loaded:
            return l, t, r, b
        mx, my = self.mouth()
        return (min(l, mx - MISSILE_W / 2), min(t, my - MISSILE_H / 2), max(r, mx + MISSILE_W / 2),
                max(b, my + MISSILE_H / 2))

    def mouth(self):
        """Where a missile leaves it (the middle of the missile)."""
        return self.x, self.base + self.dir * (STATION_H + MISSILE_H / 2 - 8)


class Missile:
    def __init__(self, x, y, direction):
        self.x, self.y, self.dir = float(x), float(y), int(direction)
        self.speed = MISSILE_SPEED[0]
        self.vx = 0.0                            # its sideways speed (it homes in a little)
        self.homing = True
        self.alive = True
        self.age = 0.0

    def tilt(self):
        """Its lean from upright (radians, positive = the nose to the right of its course)."""
        return math.atan2(self.vx, max(1.0, self.speed))

    def box(self):
        return self.x - MISSILE_W / 2, self.y - MISSILE_H / 2, self.x + MISSILE_W / 2, self.y + MISSILE_H / 2

    full_box = box

    def nose(self):
        return self.x, self.y + self.dir * MISSILE_H / 2


def place_stations(course, rng):
    """The stations of the course (sorted by x): in each section with stations, one every so often where the rock is flat
    enough and where it does not take the passage below GAP_MIN (it stands out of the rock)."""
    out = []
    share = course.tune.stations                      # (fewer stations at the lower levels: further apart)
    for k, (name, _, look) in enumerate(course.sections):
        plan = look.get("stations")
        if not plan:
            continue
        lo, hi = course._span(k)
        gap_lo, gap_hi, ceil_share = plan
        if share != 1.0:
            gap_lo, gap_hi = gap_lo / share, gap_hi / share
        x = max(lo, STATION_FIRST) + rng.uniform(0, gap_lo)
        while x < min(hi, course.brake_from):
            side = "ceil" if rng.random() < ceil_share else "floor"
            spot = _station_spot(course, x, side)
            if spot is None and side == "ceil":
                side = "floor"
                spot = _station_spot(course, x, side)
            if spot is not None:
                course.cut_pad(x, side, spot)
                st = Station(x, spot, side)
                st.lead = rng.uniform(*STATION_LEAD)
                out.append(st)
                x += rng.uniform(gap_lo, gap_hi)
            else:
                x += 24.0                              # (not here: a little further)
    return out


def _station_spot(course, x, side):
    """The y of the rock under a station at x on that side, or None when it cannot stand there."""
    xs = np.linspace(x - STATION_W / 2, x + STATION_W / 2, 7)
    edge = course.ground(xs) if side == "floor" else course.ceiling(xs)
    if float(edge.max() - edge.min()) > STATION_ROUGH:
        return None
    base = float(edge.max()) if side == "floor" else float(edge.min())        # (the pad: the rock is cut down to its lowest point)
    span = np.linspace(x - GAP_WINDOW, x + GAP_WINDOW, 13)
    room = float(np.min(course.ground(span)) - np.max(course.ceiling(span)))
    if room < course.gap_min + STATION_H + 12:
        return None
    if side == "ceil" and base < BAND_MIN + 20:
        return None                                    # (a ceiling that is only a thin band: nothing hangs from it)
    return base


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class Spark:
    """A bit of debris (cosmetic), in world coordinates."""

    def __init__(self, x, y, vx, vy, life, size):
        self.x, self.y, self.vx, self.vy = float(x), float(y), float(vx), float(vy)
        self.life = self.max = float(life)
        self.size = float(size)


class ScrambleFormation:
    """The field of the level: the course, the scroll, the ship's shots and the end. Looks like a formation without enemies to
    the rest of the game."""

    def __init__(self, style=None, seed=None, speed_mult=1.0, rng=None, level=LEVEL_MAX, endless=False, loop=1):
        self.rng = rng if rng is not None else random.Random()
        self.style = style if style in lander.BODIES else self.rng.choice(BODY_KEYS)
        self.level = level
        self.endless = bool(endless)        # BONUS FINAL - Scramble: course after course until the last life
        self.loop = max(1, int(loop))       # the course of the endless raid (1, 2, 3...): BOOST_STEP more enemies each
        self.loop_timer = 0.0               # seconds since the base blew up (the endless raid)
        self.course = Course(self.style, seed, level, 1.0 + BOOST_STEP * (self.loop - 1))
        self.tune = self.course.tune
        self.enemies = []
        self.bullets = []
        self.swarm = None
        self.sounds = None
        self.font = None
        self.text_cache = None
        self.view = None                    # scramble_view.View, made by the first draw
        self.cam = 0.0                      # the world x of the left edge of the screen
        self.speed = self.course.scroll
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
        self.stations = place_stations(self.course, random.Random(self.course.seed ^ 0x5C7A))
        self.missiles = []
        self.booms = []                     # the explosions of the game that belong to the world (they scroll with it)
        self.kills = {"station": 0, "missile": 0}
        import scramble_birds
        self.sky = scramble_birds.Sky(self)          # the waves of birds and the comets
        import scramble_base
        self.base = scramble_base.Base(self)         # the enemy base at the end

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
            return c.scroll
        return c.scroll * math.sqrt(max(0.0, c.stop - cam) / BRAKE)

    def advance(self, dt):
        """Slide the camera for `dt` seconds (exact for the braking: the same at any frame rate). Returns how far it went."""
        c = self.course
        before = self.cam
        left = dt
        if self.cam < c.brake_from:
            run = min(left, (c.brake_from - self.cam) / c.scroll)
            self.cam += run * c.scroll
            left -= run
        if left > 0 and self.cam < c.stop:
            # the braking: v = SCROLL * sqrt(rest / BRAKE), so the rest falls as a square in time
            rest = c.stop - self.cam
            u = math.sqrt(rest) - c.scroll * left / (2.0 * math.sqrt(BRAKE))
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
    if p.invulnerable <= 0 and not p.dying:
        return False                                      # (nothing happened: the hit did not count)
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
    import scramble_birds
    form.tip = asteroids.tip_color(p)
    moved = form.advance(dt)
    if moved:
        live = getattr(game, "explosions", [])
        form.booms = [b for b in form.booms if b in live]
        for b in form.booms:
            b.x -= moved                                  # (an explosion on the rock goes with the rock)
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
        before = s.x
        s.x += s.vx * dt
        s.y += s.vy * dt
        # what it meets first: a station or a missile, a bird or a comet, the base
        met = []
        target = _shot_target(form, before, s.x, s.y)
        if target is not None:
            met.append((target.full_box()[0], "rock", target))
        aloft = form.sky.shot_target(before, s.x, s.y, form.cam)
        if aloft is not None:
            met.append((aloft[1], "sky", aloft[0]))
        at_base = form.base.shot_target(before, s.x, s.y)
        if at_base is not None:
            met.append((at_base[1], "base", at_base[0]))
        if met:
            hit_x, where, thing = min(met, key=lambda m: m[0])
            s.alive = False
            if where == "rock":
                _destroy(game, form, thing)
            elif where == "base":
                form.base.hit(game, thing)
            elif isinstance(thing, scramble_birds.Bird):
                form.sky.kill_bird(game, thing)
            else:
                _blast(game, form, hit_x, s.y, small=True)           # (a comet: nothing destroys it)
        elif s.x > form.cam + W + 40:
            s.alive = False
            miss(p)                                       # (it met nothing: the Phenix gauge goes down, as in the game)
        elif s.y <= course.ceiling(s.x) or s.y >= course.ground(s.x):
            s.alive = False
            miss(p)
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
    # --- the stations fire, the missiles fly
    _stations(game, form, dt, alive)
    _missiles(game, form, dt, p if alive else None)
    form.sky.tick(game, dt, alive)
    form.base.tick(game, dt, alive)
    # --- the missiles and the stations against the ship
    if alive and p.alive and not p.dying:
        ship = (form.cam + p.x - SHIP_BOX[0], p.y - SHIP_BOX[1], form.cam + p.x + SHIP_BOX[0], p.y + SHIP_BOX[1])
        fire_bird = bool(p.is_phenix) and not getattr(p, "uses_shield", False)     # (the Phenix form burns what it meets)
        for m in form.missiles:
            if m.alive and _overlap(ship, m.box()):
                if fire_bird:
                    _destroy(game, form, m)
                    continue
                m.alive = False
                _blast(game, form, m.x, m.y, small=True)
                if p.is_phenix:
                    game._shield_absorb(p, m.x - form.cam, m.y)        # (the dome of the Shield takes it)
                _ship_hit(game, form)
                break
        for st in form.stations:
            if st.alive and _overlap(ship, st.full_box()):
                if fire_bird:
                    _destroy(game, form, st)
                elif not _immune(p):
                    _ship_hit(game, form)
                break
        form.missiles = [m for m in form.missiles if m.alive]
        if p.alive and not p.dying:
            form.sky.touch_ship(game, p)
        if p.alive and not p.dying:
            form.base.touch_ship(game, p)
    alive = p.alive and not p.dying
    # --- the rock
    if alive:
        up, down = form.rock_overlap(p)
        if up > 0 or down > 0:
            if _immune(p):
                form.push_out(p)
            else:
                _ship_hit(game, form)
    # --- the end: the scroll has stopped in the arena, the base fights; its boss dead and the base blown up, it is won
    if form.phase == "flying" and form.cam >= course.stop:
        form.phase = "arena"
        form.base.start()
        _play(getattr(game, "sounds", None), "scramble_alarm", volume=0.7)
        cry = getattr(game, "_play_boss_cry", None)
        if cry is not None:
            try:
                cry("boss_ready", volume=0.9, x=W * 0.85)          # (the alien of the base, as the boss of a saucer)
            except Exception:
                log_exc("scramble.tick")
    if form.phase == "arena":
        form.arena_time += dt
        if form.base.done:
            form.phase = "won"
            form.won = not form.endless             # (the endless raid: never won, the next course comes)
    if form.endless and form.phase == "won":
        form.loop_timer += dt
        if form.loop_timer >= LOOP_PAUSE:
            next_loop(game, form)


def next_loop(game, form):
    """The endless raid: the next course, from its beginning, a new one with BOOST_STEP more enemies; the ship goes on with
    its lives."""
    new = ScrambleFormation(style=form.style, seed=form.rng.getrandbits(32), rng=form.rng, level=form.level,
                            endless=True, loop=form.loop + 1)
    new.sounds, new.font, new.text_cache = form.sounds, form.font, form.text_cache
    new.deaths = form.deaths
    game.formation = new
    p = game.player
    p.scramble = new
    p.x, p.y, p.ast_angle = START_X, H / 2.0, 0.0
    new.recentre(p)
    p.invulnerable = max(float(getattr(p, "invulnerable", 0.0) or 0.0), 1.5)
    adv = getattr(game, "adventure", None)
    if isinstance(adv, dict):
        adv["level"] = new.loop                     # (the HUD shows it after the name of the mission)
    try:
        game._play_level_vo(new.loop)
    except Exception:
        log_exc("scramble.next_loop")
    return new


def _shot_target(form, x0, x1, y):
    """The missile or the station a shot meets as it goes from x0 to x1 (at the height y), the nearest first; or None."""
    best, best_x = None, None
    for m in form.missiles:
        if m.alive:
            l, t, r, b = m.box()
            if t - 3 <= y <= b + 3 and l - 3 <= x1 and x0 <= r + 3 and (best_x is None or l < best_x):
                best, best_x = m, l
    reach = STATION_W
    for st in form.stations:
        if st.x < x0 - reach:
            continue
        if st.x > x1 + reach:
            break                                         # (sorted by x: none further on can be met)
        if st.alive:
            l, t, r, b = st.full_box()
            if t <= y <= b and l <= x1 and x0 <= r and (best_x is None or l < best_x):
                best, best_x = st, l
    return best


STATION_BESTIARY = "station"      # the Bestiary of the Adventure: the missile launchers (stations and turrets of the base)
BOSS_BESTIARY = "redboss"         # ... the red commander of the base


def bestiary_points(game, kind, points):
    """`points` for an enemy of `kind` destroyed; in the Adventure it also counts for the Bestiary (once destroyed, the
    kind shows up there) and pays its bonus once the last tier is reached, like the enemies of the game."""
    adv = getattr(game, "adventure", None)
    story = getattr(game, "story", None)
    state = getattr(story, "state", None) if story is not None else None
    if not isinstance(adv, dict) or not isinstance(state, dict):
        return points
    kills = adv.setdefault("kills", {})
    kills[kind] = kills.get(kind, 0) + 1
    import story_state
    return points + story_state.kill_bonus(state, kind, kills[kind])


def charge(ship):
    """A valid hit (a bird, a missile, a launcher): the Phenix gauge goes up, as in the game (Player.register_valid_hit)."""
    hit = getattr(ship, "register_valid_hit", None)
    if hit is not None:
        hit()


def miss(ship):
    """A shot that met nothing: the Phenix gauge goes down, as in the game (Player.register_miss)."""
    lost = getattr(ship, "register_miss", None)
    if lost is not None:
        lost()


def _destroy(game, form, target):
    """A shot (or the Phenix form) destroyed a station or a missile: its points, its explosion (and the Phenix gauge)."""
    p = game.player
    charge(p)
    if isinstance(target, Missile):
        target.alive = False
        form.missiles = [m for m in form.missiles if m.alive]
        form.kills["missile"] += 1
        game._add_score(p, MISSILE_POINTS)
        _blast(game, form, target.x, target.y, small=True)
    else:
        target.alive = False
        form.kills["station"] += 1
        game._add_score(p, bestiary_points(game, STATION_BESTIARY, game._enemy_points(STATION_KIND)))
        if target.loaded:                                  # (the missile standing on it goes up with it)
            target.loaded = False
            form.kills["missile"] += 1
            game._add_score(p, MISSILE_POINTS)
            mx, my = target.mouth()
            _blast(game, form, mx, my, small=True)
        l, t, r, b = target.box()
        _blast(game, form, target.x, (t + b) / 2.0, small=False)


def _blast(game, form, wx, wy, small):
    """An explosion at a point of the world (it scrolls with the rock) and its sound."""
    try:
        boom = game._boom(wx - form.cam, wy, kind="enemy")
        game.explosions.append(boom)
        form.booms.append(boom)
    except Exception:
        log_exc("scramble._blast")
    for _ in range(8 if small else 18):
        a = form.rng.uniform(0, 2 * math.pi)
        v = form.rng.uniform(60, 260)
        form.sparks.append(Spark(wx, wy, math.cos(a) * v, math.sin(a) * v, form.rng.uniform(0.2, 0.6),
                                 form.rng.uniform(1.5, 3.5)))
    _play(getattr(game, "sounds", None), "explosion", volume=0.55 if small else 0.85, x=wx - form.cam)


def _stations(game, form, dt, alive):
    """The stations ahead of the ship fire their missiles, one by one, now and then."""
    p = game.player
    for st in form.stations:
        if not st.alive:
            continue
        sx = st.x - form.cam
        if sx < -80:
            continue
        if sx > W + 80:
            break                                         # (sorted by x: the others are further still)
        if not st.loaded:
            st.reload -= dt
            if st.reload <= 0 and st.missiles > 0:
                st.loaded = True
            continue
        ahead = sx - p.x
        if alive and STATION_RANGE[0] <= ahead <= STATION_RANGE[1] and \
                ahead / max(1.0, form.speed) <= rise_time(abs(p.y - st.mouth()[1])) + st.lead:
            x, y = st.mouth()
            m = Missile(x, y, st.dir)
            m.homing = form.tune.homing > 0
            form.missiles.append(m)
            st.missiles -= 1
            st.loaded = False
            st.reload = form.tune.reload
            _play(getattr(game, "sounds", None), "scramble_launch", volume=0.5, x=sx)


def rise_time(distance):
    """Seconds a missile takes to fly `distance` px from its station (it speeds up, to its top speed)."""
    v0, top = MISSILE_SPEED
    a = MISSILE_ACCEL
    d_top = (top * top - v0 * v0) / (2 * a)                   # (the distance over which it speeds up)
    if distance <= d_top:
        return (-v0 + math.sqrt(v0 * v0 + 2 * a * distance)) / a
    return (top - v0) / a + (distance - d_top) / top


def _missiles(game, form, dt, ship=None):
    """The missiles speed up, home in a little on the ship (`ship`, None when it is gone), and burst on the rock or leave
    the screen."""
    course = form.course
    for m in form.missiles:
        m.age += dt
        m.speed = min(MISSILE_SPEED[1], m.speed + MISSILE_ACCEL * dt)
        if m.homing and ship is not None and m.age <= HOMING_TIME and (ship.y - m.y) * m.dir > 0:
            k = form.tune.homing
            want = max(-HOMING_VX * k, min(HOMING_VX * k, (form.cam + ship.x - m.x) * HOMING_GAIN))
            step = HOMING_ACCEL * k * dt
            m.vx += max(-step, min(step, want - m.vx))
        else:
            m.homing = False                      # (once it has passed the ship, or given up: straight on)
        m.x += m.vx * dt
        m.y += m.dir * m.speed * dt
        nx, ny = m.nose()
        if m.x - form.cam < -60 or ny < -40 or ny > H + 40:
            m.alive = False
        elif m.age > 0.15 and (ny <= course.ceiling(nx) or ny >= course.ground(nx)):
            m.alive = False
            _blast(game, form, nx, ny, small=True)
    form.missiles = [m for m in form.missiles if m.alive]


def _play(snd, name, **kw):
    if snd is None:
        return
    try:
        snd.play(name, **kw)
    except Exception:
        log_exc("scramble._play")
