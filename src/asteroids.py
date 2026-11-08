"""The mission "Asteroids" (story_state.py, ids `ast_1`, `ast_2`, `ast_3`: the prelude of the main series of each act): the game of Atari's Asteroids, played with
the ship of the hangar.

The ship turns (left / right), pushes (up) and fires; it keeps its speed, and what leaves one side of the screen comes
back by the opposite one (for the rocks, the shots, the saucer's shots and the ship). No hyperspace. The Player is the
real one of the game (lives, dome, death, jets, invulnerability): its `asteroid_mode` makes it fly free (Player.
_update_asteroid) and draws it turned (Player._draw_asteroid). Everything else is here:

- ROCKS: big, medium, small. A rock that is hit breaks in two of the size below; a small one is destroyed. Every rock
  hit counts, the fragments too: after TARGET the mission is won, once the screen is empty. While the target is not
  reached the field is topped up as the rocks are destroyed: when what is left of it (MASS) gets low, a new big rock
  comes in from OUTSIDE the screen, drifting in (it only starts to wrap around once it is wholly in). After the target
  nothing comes any more (no rock, no saucer) and a rock that is hit is just gone, it no longer breaks in two. When
  the last one is gone the mission ends after a short pause (END_DELAY): no flight up, no level change.
- THE SAUCER: the miniature saucer of the paint missions (invaders.saucer_image), now and then (about every 20 s,
  so 4 or 5 times in a mission, more in a long one) it crosses the screen zigzagging and fires at the ship, a little
  wide of it. Its shots break the rocks too. No saucer after the target is reached.
- Shots: at most MAX_SHOTS on the screen, they carry the speed of the ship and die after SHOT_LIFE seconds.
- Points (paid in the hangar like any mission, see story_state): ROCK_POINTS, SAUCER_POINTS.

THE ENDLESS LEVEL (`endless`: the mission "BONUS - Asteroids", once the game is finished): pure Asteroids, level after
level until the ship is lost. Every big rock of a level is there from its start (ENDLESS_ROCKS: 4, 6, 8, 10, then 11
from level 5 on), nothing comes in from outside; a level ends when no rock is left, not even a small one, and the next
one starts after LEVEL_PAUSE. The saucer comes as in the belts and fires SAUCER_LEVEL_STEP (10 %) faster each level;
every TWIN_EVERY levels (5, 10, 15...) the saucers come by two, one from each side of the screen at different heights.
There is no target and the mission is never won: it ends with the GAME OVER of the ship, its score is banked then
(story_state.record_result; leaving it by the pause menu gains nothing and loses nothing), and the best one is kept in the save and shown at the top of the screen (not in the high scores).

`AsteroidFormation` is the formation of the mission (nothing a bird has: no enemy, no bullet in the generic lists);
`tick(game)` runs it every frame and `draw(surface)` draws it. The pictures of the rocks are made by
tools/make_asteroids.py (assets/sprites/asteroids/).
"""
import math
import random

import pygame

import invaders
from errlog import log_exc
from settings import BASE_HEIGHT, BASE_WIDTH, asset_path

TARGET = 60                          # rocks to destroy (every piece counts) to win
FIRST_WAVE = 4                       # big rocks at the start
ROCK_MASS = {3: 4, 2: 2, 1: 1}       # what a rock weighs in the field (a big one = 2 mediums = 4 smalls)
MASS_LOW = 10                        # below this a new big rock is sent in (the start is 4 big ones = 16)
REPOP_GAP = (0.8, 1.6)               # seconds before the next one, so that they do not all come at once
ENTER_SPEED = (55.0, 95.0)           # a rock that comes in from outside
END_DELAY = 1.2                      # seconds between the last rock and the end of the mission
MAX_SHOTS = 4                        # the player's shots on the screen
SHOT_SPEED = 780.0                   # px / s, on top of the speed of the ship
SHOT_LIFE = 0.85                     # seconds
SHOT_GAP = 0.16                      # seconds between two shots
TURN_SPEED = 4.4                     # rad / s
THRUST = 430.0                       # px / s per second
DRAG = 0.30                          # per second: the ship slows down a little, by itself
MAX_SPEED = 480.0
SHIP_RADIUS = 22                     # what a rock must touch
DOME_RADIUS = 52                     # ... when the dome of the Shield is on
ROCK_RADIUS = {3: 53, 2: 31, 1: 18}  # a share of the picture (the rocks are lumpy balls)
ROCK_CELL = {3: 132, 2: 78, 1: 44}   # the cell of a picture, per size
ROCK_FRAMES = 24
ROCK_VARIANTS = 3                    # the shapes of a rock (tools/make_asteroids.py): lumpy, long, angular; one at random
ROCK_SPEED = {3: (40.0, 85.0), 2: (70.0, 150.0), 1: (90.0, 190.0)}
ROCK_POINTS = {3: 10, 2: 20, 1: 40}
SAUCER_POINTS = 100
SAUCER_SCALE = 1.4                   # the miniature of the paint missions is 72 px wide: this much bigger here
SAUCER_GAP = (11.0, 17.0)            # seconds between two saucers (once the last one has left), the first one after SAUCER_FIRST
SAUCER_FIRST = (8.0, 11.0)
SAUCER_FIRE_GAP = 1.5
SAUCER_AIM_ERROR = 0.45              # rad: the saucer is not a good shot
SAUCER_SHOT_SPEED = 340.0
SAUCER_SHOT_LIFE = 2.2
SAUCER_HALF = (46, 19)               # what a shot of the ship must touch
SPAWN_CLEAR = 190                    # a rock never comes in this close to the ship
ENDLESS_ROCKS = (4, 6, 8, 10, 11)    # the endless level: big rocks of levels 1, 2, 3, 4, then 5 and up (the cap)
LEVEL_PAUSE = 1.6                    # seconds between the last rock of a level and the next level
LEVEL_BANNER = 2.0                   # seconds the number of a new level is shown
SAUCER_LEVEL_STEP = 0.10             # the saucer fires this much faster at each level (level 3: 20 % faster than level 1)
TWIN_EVERY = 5                       # the endless level: at levels 5, 10, 15... the saucers come by two, from both sides
TWIN_GAP = 220                       # px: at least this far apart in height, the two saucers of a pair

_strips = {}
_saucer_cache = {}


# ------------------------------------------------------------------ pictures
def rock_frames(size, variant):
    """The cells of the picture of a rock (a list of Surfaces; a plain ball if the picture is missing)."""
    key = (size, variant)
    if key in _strips:
        return _strips[key]
    cell = ROCK_CELL[size]
    letter = {3: "L", 2: "M", 1: "S"}[size]
    frames = []
    try:
        strip = pygame.image.load(asset_path("sprites", "asteroids", "rock_%s_%d.png" % (letter, variant))).convert_alpha()
        n = max(1, strip.get_width() // cell)
        frames = [strip.subsurface((i * cell, 0, cell, strip.get_height())).copy() for i in range(n)]
    except Exception:
        log_exc("asteroids.rock_frames")
    if not frames:
        ball = pygame.Surface((cell, cell), pygame.SRCALPHA)
        pygame.draw.circle(ball, (130, 120, 110), (cell // 2, cell // 2), int(cell * 0.4))
        frames = [ball]
    _strips[key] = frames
    return frames


def saucer_frame(age):
    """The picture of the saucer `age` seconds old (the red parts pulse, as in the paint missions), a bit enlarged."""
    i = invaders.saucer_frame_at(age)
    if i not in _saucer_cache:
        img = invaders.saucer_image(i)
        w, h = img.get_size()
        _saucer_cache[i] = pygame.transform.smoothscale(img, (int(w * SAUCER_SCALE), int(h * SAUCER_SCALE)))
    return _saucer_cache[i]


def wrapped_delta(ax, ay, bx, by):
    """The shortest way from a to b on a screen whose sides are joined."""
    dx = (bx - ax + BASE_WIDTH / 2) % BASE_WIDTH - BASE_WIDTH / 2
    dy = (by - ay + BASE_HEIGHT / 2) % BASE_HEIGHT - BASE_HEIGHT / 2
    return dx, dy


# ------------------------------------------------------------------ things
class Rock:
    def __init__(self, size, x, y, vx, vy, rng, entering=False):
        self.size = size
        self.entering = bool(entering)    # coming in from outside the screen: it does not wrap until it is wholly in
        self.coming = 0.0
        self.x, self.y, self.vx, self.vy = float(x), float(y), float(vx), float(vy)
        self.variant = rng.randrange(ROCK_VARIANTS)
        self.phase = rng.uniform(0, ROCK_FRAMES)
        self.spin = rng.uniform(3.0, 7.0) * rng.choice((-1, 1)) * (1.4 if size == 1 else 1.0)    # cells / s
        self.rot = rng.uniform(0, 360)
        self.rspin = rng.uniform(-25.0, 25.0)                                                     # degrees / s

    @property
    def radius(self):
        return ROCK_RADIUS[self.size]

    def update(self, dt):
        if self.entering:
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.coming += dt
            m = self.radius + 2
            if m <= self.x <= BASE_WIDTH - m and m <= self.y <= BASE_HEIGHT - m:
                self.entering = False
            elif self.coming > 30.0:                  # (never seen to happen: it would wrap like the others)
                self.entering = False
                self.x %= BASE_WIDTH
                self.y %= BASE_HEIGHT
        else:
            self.x = (self.x + self.vx * dt) % BASE_WIDTH
            self.y = (self.y + self.vy * dt) % BASE_HEIGHT
        self.phase = (self.phase + self.spin * dt) % ROCK_FRAMES
        self.rot = (self.rot + self.rspin * dt) % 360

    def delta_to(self, x, y):
        """From this rock to (x, y): the shortest way round the joined screen, or the plain way while it is coming in
        (the screen is not joined for it yet: it cannot hit what is on the other side)."""
        if self.entering:
            return x - self.x, y - self.y
        return wrapped_delta(self.x, self.y, x, y)

    def image(self):
        cells = rock_frames(self.size, self.variant)
        img = cells[int(self.phase) % len(cells)]
        return pygame.transform.rotate(img, self.rot) if self.rspin else img


class Shot:
    def __init__(self, x, y, vx, vy, life, mine):
        self.x, self.y, self.vx, self.vy, self.life, self.mine = float(x), float(y), float(vx), float(vy), float(life), mine

    def update(self, dt):
        self.x = (self.x + self.vx * dt) % BASE_WIDTH
        self.y = (self.y + self.vy * dt) % BASE_HEIGHT
        self.life -= dt


class Saucer:
    def __init__(self, left, rng, y=None):
        self.x = -60.0 if left else BASE_WIDTH + 60.0
        self.y = rng.uniform(150, BASE_HEIGHT - 150) if y is None else float(y)
        self.vx = invaders.SAUCER_SPEED * (1 if left else -1)
        self.vy = 0.0
        self.age = 0.0
        self.fire_in = 1.2
        self.alive = True

    def update(self, dt, rng):
        before = self.age
        self.age += dt
        if int(self.age / 1.4) != int(before / 1.4):
            self.vy = rng.choice((-110.0, 0.0, 110.0))        # a zigzag, a new heading every 1.4 s
        self.x += self.vx * dt
        self.y = max(60.0, min(BASE_HEIGHT - 60.0, self.y + self.vy * dt))
        self.fire_in -= dt
        return self.x < -90 or self.x > BASE_WIDTH + 90        # True: it left the screen

    def delta_to(self, x, y):
        """From the saucer to (x, y), the plain way: it crosses the screen once and never wraps round it (nothing on
        the other side can touch it, it shows nowhere else)."""
        return x - self.x, y - self.y


class Spark:
    """A bit of debris or dust (cosmetic)."""

    def __init__(self, x, y, vx, vy, life, kind, size):
        self.x, self.y, self.vx, self.vy = float(x), float(y), float(vx), float(vy)
        self.life = self.max = float(life)
        self.kind, self.size = kind, float(size)


# ------------------------------------------------------------------ the formation of the mission
class AsteroidFormation:
    """The field: rocks, the saucer, the shots, the debris. It looks like a formation without enemies to the rest of
    the game (`all_dead()` says when the mission is won)."""

    def __init__(self, speed_mult=1.0, rng=None, target=TARGET, endless=False):
        self.enemies = []
        self.bullets = []
        self.swarm = None
        self.sounds = None
        self.font = None
        self.rng = rng if rng is not None else random.Random()
        self.speed_mult = float(speed_mult)
        self.target = int(target)
        self.rocks = []
        self.shots = []
        self.sparks = []
        self.saucers = []                 # on the screen: one, or two at the twin levels of the endless level
        self.time = 0.0
        self.destroyed = 0                # rocks hit so far (every piece counts)
        self.waves = 0                    # 0: the first rocks are not placed yet
        self.fire_cd = 0.0
        self.saucer_in = self.rng.uniform(*SAUCER_FIRST)
        self.repop = True                 # the field is topped up while the target is not reached
        self.spawn_in = None              # seconds before the next rock comes in (None: the field is full)
        self.end_timer = 0.0              # seconds since the last rock and the saucer are gone (target reached)
        self.tip = (180, 220, 255)        # the colour of the shots: the hull's
        self.started = False
        self.endless = bool(endless)      # the endless level: no target, a level after the other (see the docstring)
        self.level = 1
        self.next_in = 0.0                # seconds since the last rock of the level is gone (endless)
        self.banner = 0.0                 # seconds the number of the level is still shown (endless)
        if self.endless:
            self.repop = False

    @property
    def saucer(self):
        """The saucer on the screen (the first one when there are two), or None."""
        return self.saucers[0] if self.saucers else None

    @saucer.setter
    def saucer(self, s):
        self.saucers = [] if s is None else [s]

    def twin_level(self):
        """The endless level sends its saucers by two at levels 5, 10, 15..."""
        return self.endless and self.level % TWIN_EVERY == 0

    def send_saucers(self):
        """A saucer comes in from one side (two at a twin level: one from each side, at heights well apart)."""
        left = self.rng.random() < 0.5
        first = Saucer(left, self.rng)
        self.saucers = [first]
        if self.twin_level():
            lo, hi = 150.0, BASE_HEIGHT - 150.0
            choices = [y for y in (first.y - TWIN_GAP, first.y + TWIN_GAP) if lo <= y <= hi] or [lo if first.y > (lo + hi) / 2 else hi]
            y = self.rng.choice(choices) if len(choices) > 1 else choices[0]
            self.saucers.append(Saucer(not left, self.rng, y=y))
        return self.saucers

    # --- what the rest of the game asks of a formation ---
    def update(self, dt, player_x):
        return None

    def get_alive_enemies(self):
        return []

    def get_hittable_enemies(self):
        return []

    @property
    def reached(self):
        return not self.endless and self.destroyed >= self.target

    def remaining(self):
        """Rocks still on the screen once the target is reached (and in the endless level); before it, the rocks still
        to be destroyed."""
        return len(self.rocks) if (self.reached or self.endless) else max(0, self.target - self.destroyed)

    def swarm_remaining(self):
        return self.remaining()

    def all_dead(self):
        """The mission is won: the target reached, the screen empty, and a short pause to see the last explosion. (The
        endless level is never won: it ends with the ship.)"""
        return self.reached and not self.rocks and self.saucer is None and self.end_timer >= END_DELAY

    def field_mass(self):
        """What is left of the field (see ROCK_MASS)."""
        return sum(ROCK_MASS[r.size] for r in self.rocks)

    def rocks_for_level(self, level=None):
        """The big rocks a level of the endless level starts with (FIRST_WAVE in the belts)."""
        if not self.endless:
            return FIRST_WAVE
        level = max(1, int(self.level if level is None else level))
        return ENDLESS_ROCKS[min(level, len(ENDLESS_ROCKS)) - 1]

    def saucer_fire_gap(self):
        """Seconds between two shots of the saucer: SAUCER_LEVEL_STEP faster at each level of the endless level."""
        if not self.endless:
            return SAUCER_FIRE_GAP
        return SAUCER_FIRE_GAP / (1.0 + SAUCER_LEVEL_STEP * (max(1, self.level) - 1))

    # --- the field ---
    def new_wave(self, player=None):
        """The first rocks of the mission (or of a level of the endless level): big ones, at the edges but already in,
        never close to the ship."""
        self.waves += 1
        px, py = (player.x, player.y) if player is not None else (BASE_WIDTH / 2, BASE_HEIGHT / 2)
        for _ in range(self.rocks_for_level()):
            for _try in range(12):
                side = self.rng.choice("lrtb")
                x = self.rng.uniform(0, BASE_WIDTH) if side in "tb" else (0.0 if side == "l" else BASE_WIDTH - 1.0)
                y = self.rng.uniform(0, BASE_HEIGHT) if side in "lr" else (0.0 if side == "t" else BASE_HEIGHT - 1.0)
                dx, dy = wrapped_delta(px, py, x, y)
                if dx * dx + dy * dy > SPAWN_CLEAR ** 2:
                    break
            a = self.rng.uniform(0, math.tau)
            sp = self.rng.uniform(*ROCK_SPEED[3]) * self.speed_mult
            self.rocks.append(Rock(3, x, y, math.cos(a) * sp, math.sin(a) * sp, self.rng))

    def spawn_rock(self, player=None):
        """A big rock comes in from OUTSIDE the screen: it starts just beyond an edge (not in front of the ship) and
        drifts toward a point inside, so that it slides in smoothly (it wraps only once it is wholly in)."""
        px, py = (player.x, player.y) if player is not None else (BASE_WIDTH / 2, BASE_HEIGHT / 2)
        margin = ROCK_RADIUS[3] + 36
        lane = ROCK_RADIUS[3] + 40                      # along the edge it keeps clear of the corners, so it does come in
        x = y = 0.0
        for _try in range(12):
            side = self.rng.choice("lrtb")
            if side in "lr":
                x = -margin if side == "l" else BASE_WIDTH + margin
                y = self.rng.uniform(lane, BASE_HEIGHT - lane)
            else:
                y = -margin if side == "t" else BASE_HEIGHT + margin
                x = self.rng.uniform(lane, BASE_WIDTH - lane)
            dx, dy = wrapped_delta(px, py, x, y)
            if dx * dx + dy * dy > (SPAWN_CLEAR + 60) ** 2:
                break
        tx = self.rng.uniform(BASE_WIDTH * 0.2, BASE_WIDTH * 0.8)       # a point well inside: it is sure to come in
        ty = self.rng.uniform(BASE_HEIGHT * 0.2, BASE_HEIGHT * 0.8)
        a = math.atan2(ty - y, tx - x) + self.rng.uniform(-0.15, 0.15)
        sp = self.rng.uniform(*ENTER_SPEED) * self.speed_mult
        self.rocks.append(Rock(3, x, y, math.cos(a) * sp, math.sin(a) * sp, self.rng, entering=True))

    def debris(self, x, y, kind, n, speed, life=(0.4, 1.0), size=(2.0, 5.0)):
        for _ in range(n):
            a = self.rng.uniform(0, math.tau)
            sp = self.rng.uniform(0.15, 1.0) * speed
            self.sparks.append(Spark(x, y, math.cos(a) * sp, math.sin(a) * sp, self.rng.uniform(*life), kind,
                                     self.rng.uniform(*size)))

    def break_rock(self, game, rock):
        """A rock was hit: points, debris, two smaller rocks (a small one is just gone)."""
        if rock in self.rocks:
            self.rocks.remove(rock)
        self.destroyed += 1
        game._add_score(game.player, ROCK_POINTS[rock.size])
        big = rock.size == 3
        self.debris(rock.x, rock.y, "rock", {3: 22, 2: 14, 1: 9}[rock.size], {3: 190, 2: 220, 1: 240}[rock.size],
                    size=(2.0, 5.0 if rock.size > 1 else 3.5))
        self.debris(rock.x, rock.y, "dust", {3: 12, 2: 8, 1: 5}[rock.size], 70, life=(0.5, 1.1),
                    size=(10.0, 22.0) if big else (7.0, 14.0))
        self.sparks.append(Spark(rock.x, rock.y, 0, 0, 0.22, "flash", 50 if big else 32))
        try:
            game.sounds.play("enemy_explosion", volume={3: 0.55, 2: 0.45, 1: 0.35}[rock.size], x=rock.x)
        except Exception:
            log_exc("asteroids.break_rock")
        if rock.size > 1 and not self.reached:
            for _ in range(2):
                a = self.rng.uniform(0, math.tau)
                sp = self.rng.uniform(70.0, 150.0) * (1.2 if rock.size == 2 else 1.0) * self.speed_mult
                self.rocks.append(Rock(rock.size - 1, rock.x, rock.y, rock.vx * 0.6 + math.cos(a) * sp,
                                       rock.vy * 0.6 + math.sin(a) * sp, self.rng))
        # (once the target is reached a rock that is hit is just gone: the screen only has to be emptied)

    def blow_saucer(self, game, s=None):
        s = s if s is not None else self.saucer
        if s is None or s not in self.saucers:
            return
        self.saucers.remove(s)
        game._add_score(game.player, SAUCER_POINTS)
        self.debris(s.x, s.y, "fire", 40, 300, life=(0.4, 1.2), size=(3.0, 8.0))
        self.debris(s.x, s.y, "spark", 22, 380, life=(0.3, 0.9), size=(2.0, 3.0))
        self.sparks.append(Spark(s.x, s.y, 0, 0, 0.35, "flash", 90))
        game.explosions.append(game._boom(s.x, s.y, kind="enemy"))
        try:
            if not self.saucers:
                game.sounds.stop_sfx("saucer_pass", 150)
            game.sounds.play("explosion", volume=0.7, x=s.x)
        except Exception:
            log_exc("asteroids.blow_saucer")

    # --- drawing ---
    def draw(self, surface):
        for r in sorted(self.rocks, key=lambda r: -r.size):
            _blit_wrapped(surface, r.image(), r.x, r.y, wrap=not r.entering)
        for s in self.saucers:
            _blit_wrapped(surface, saucer_frame(s.age), s.x, s.y + math.sin(s.age * 5.0) * 2.0, wrap=False)
        for p in self.sparks:
            a = max(0.0, p.life / p.max)
            if p.kind == "dust":
                c = (int(70 * a), int(62 * a), int(55 * a))
                pygame.draw.circle(surface, c, (int(p.x), int(p.y)), max(1, int(p.size * (1.7 - a))))
        for p in self.sparks:
            a = max(0.0, p.life / p.max)
            if p.kind == "rock":
                c = (int(150 * a + 40), int(135 * a + 35), int(120 * a + 30))
                pygame.draw.circle(surface, c, (int(p.x), int(p.y)), max(1, int(p.size * (0.5 + 0.5 * a))))
            elif p.kind == "fire":
                _add_glow(surface, (255, 170, 60), (p.x, p.y), max(4, int(p.size * 7 * a + 4)))
            elif p.kind == "spark":
                pygame.draw.line(surface, (255, int(220 * a), int(120 * a)), (p.x, p.y), (p.x - p.vx * 0.04, p.y - p.vy * 0.04), 2)
            elif p.kind == "flash":
                k = 1.0 - a
                _add_glow(surface, (255, 150, 40), (p.x, p.y), int(p.size * 2 * (1.0 + 1.2 * k)))
                if a > 0.55:
                    _add_glow(surface, (255, 240, 200), (p.x, p.y), int(p.size * 1.2))
        for b in self.shots:
            sp = math.hypot(b.vx, b.vy) or 1.0
            ux, uy = b.vx / sp, b.vy / sp
            if b.mine:
                mid = tuple(min(255, (c + 255) // 2) for c in self.tip)
                for length, width, col in ((22, 6, self.tip), (16, 3, mid)):
                    pygame.draw.line(surface, col, (b.x - ux * length, b.y - uy * length), (b.x, b.y), width)
                _add_glow(surface, (255, 240, 200), (b.x, b.y), 22)
            else:
                _add_glow(surface, (255, 60, 40), (b.x, b.y), 26)
                pygame.draw.circle(surface, (255, 200, 180), (int(b.x), int(b.y)), 4)


_glows = {}


def _add_glow(surface, color, pos, size):
    """A soft round light added to the picture (made once per colour and size)."""
    size = max(2, int(size))
    key = (color, size)
    g = _glows.get(key)
    if g is None:
        r = size // 2
        g = pygame.Surface((size, size))
        for i in range(r, 0, -1):
            k = (1.0 - i / r) ** 2
            pygame.draw.circle(g, (int(color[0] * k), int(color[1] * k), int(color[2] * k)), (r, r), i)
        if len(_glows) > 200:
            _glows.clear()
        _glows[key] = g
    surface.blit(g, (int(pos[0] - size // 2), int(pos[1] - size // 2)), special_flags=pygame.BLEND_RGB_ADD)


def _blit_wrapped(surface, img, x, y, wrap=True):
    """Draw `img` centred on (x, y), and again on the other side when it sticks out of the screen (not for a rock that
    is still coming in from outside: it slides in, nothing shows on the other side)."""
    w, h = img.get_size()
    xs = [0]
    ys = [0]
    if not wrap:
        surface.blit(img, (int(x - w / 2), int(y - h / 2)))
        return
    if x > BASE_WIDTH - w / 2:
        xs.append(-BASE_WIDTH)
    elif x < w / 2:
        xs.append(BASE_WIDTH)
    if y > BASE_HEIGHT - h / 2:
        ys.append(-BASE_HEIGHT)
    elif y < h / 2:
        ys.append(BASE_HEIGHT)
    for ox in xs:
        for oy in ys:
            surface.blit(img, (int(x + ox - w / 2), int(y + oy - h / 2)))


def tip_color(player):
    return {
        "blue": (120, 170, 255), "gold": (255, 200, 90), "red": (255, 120, 110), "green": (120, 255, 150),
        "violet": (210, 130, 255), "argent": (210, 220, 235),
    }.get(getattr(player, "palette", "argent"), (180, 220, 255))


# ------------------------------------------------------------------ every frame
def active(game):
    form = getattr(game, "formation", None)
    return form if isinstance(form, AsteroidFormation) else None


def _ship_circle(player):
    dome = getattr(player, "uses_shield", False) and getattr(player, "is_phenix", False)
    return DOME_RADIUS if dome else SHIP_RADIUS, dome


def _ship_hit(game, form):
    """The ship is struck. The dome absorbs; invulnerable, nothing; else a life goes (and the ship comes back to the
    middle, still, nose up). Returns True when the hit took a life."""
    p = game.player
    if getattr(p, "is_phenix", False):
        if getattr(p, "uses_shield", False):
            game._shield_absorb(p, p.x, p.y)             # the dome of the Shield absorbs
        return False                                      # (and the Phenix form is immune anyway)
    if p.invulnerable > 0 or not p.alive or p.dying:
        return False
    old = (p.x, p.y)
    p.hit()
    kind = "gameover" if p.dying else "bullet"
    game._ship_boom(p, kind)                              # (the big blast of the ship, at the place it was hit)
    game.shake_amount = 22.0 if p.dying else 12.0
    game.sounds.play("explosion_big" if p.dying else "explosion", x=old[0])
    form.debris(old[0], old[1], "fire", 36, 330, life=(0.5, 1.3), size=(3.0, 8.0))
    form.debris(old[0], old[1], "rock", 12, 260, life=(0.6, 1.4), size=(2.0, 4.0))
    if not p.dying:
        p.ast_recenter()
    return True


def tick(game):
    """Every frame of the mission: the ship's shots, the rocks, the saucer, the collisions, the end. A no-op in any other
    mission."""
    form = active(game)
    if form is None or game.stage_transition is not None:
        return
    p = game.player
    dt = game.dt
    form.time += dt
    form.tip = tip_color(p)
    form.started = True
    if form.waves == 0:
        form.new_wave(p)
        form.banner = LEVEL_BANNER if form.endless else 0.0
    form.banner = max(0.0, form.banner - dt)
    # --- the ship fires
    form.fire_cd = max(0.0, form.fire_cd - dt)
    if p.alive and not p.dying and getattr(p, "ast_fire", False) and form.fire_cd <= 0 and \
            sum(1 for s in form.shots if s.mine) < MAX_SHOTS:
        form.fire_cd = SHOT_GAP
        ca, sa = math.cos(p.ast_angle), math.sin(p.ast_angle)
        mult = float(getattr(p, "bullet_speed_mult", 1.0) or 1.0)
        form.shots.append(Shot(p.x + ca * 36, p.y + sa * 36, p.ast_vx + ca * SHOT_SPEED * mult,
                               p.ast_vy + sa * SHOT_SPEED * mult, SHOT_LIFE, True))
        try:
            game.sounds.play("shoot", volume=0.45, x=p.x)
        except Exception:
            log_exc("asteroids.tick")
    p.ast_fire = False
    # --- movement
    for r in form.rocks:
        r.update(dt)
    for s in form.shots:
        s.update(dt)
    form.shots = [s for s in form.shots if s.life > 0]
    for sp in form.sparks:
        sp.x += sp.vx * dt
        sp.y += sp.vy * dt
        sp.life -= dt
        damp = math.exp(-1.6 * dt)
        sp.vx *= damp
        sp.vy *= damp
    form.sparks = [sp for sp in form.sparks if sp.life > 0]
    # --- the saucer
    if not form.saucers and not form.reached:
        form.saucer_in -= dt
        if form.saucer_in <= 0:
            form.send_saucers()
            form.saucer_in = form.rng.uniform(*SAUCER_GAP)
            try:
                game.sounds.play_voice("saucer_pass", x=form.saucer.x)
            except Exception:
                log_exc("asteroids.tick")
    if form.saucers:
        for s in list(form.saucers):
            if s.update(dt, form.rng):
                form.saucers.remove(s)
            elif s.fire_in <= 0 and p.alive and not p.dying:
                s.fire_in = form.saucer_fire_gap()
                dx, dy = wrapped_delta(s.x, s.y, p.x, p.y)
                a = math.atan2(dy, dx) + form.rng.uniform(-SAUCER_AIM_ERROR, SAUCER_AIM_ERROR)
                form.shots.append(Shot(s.x, s.y, math.cos(a) * SAUCER_SHOT_SPEED, math.sin(a) * SAUCER_SHOT_SPEED,
                                       SAUCER_SHOT_LIFE, False))
                game.sounds.play("enemy_shoot", x=s.x)
        if form.saucers:
            try:
                game.sounds.follow_voice("saucer_pass", x=form.saucer.x, paused=bool(game.paused))
            except Exception:
                log_exc("asteroids.tick")
        else:
            game.sounds.stop_sfx("saucer_pass", 150)
    # --- shots against rocks and the saucer
    for shot in list(form.shots):
        if shot not in form.shots:
            continue
        hit = None
        for r in form.rocks:
            dx, dy = r.delta_to(shot.x, shot.y)
            if dx * dx + dy * dy < (r.radius + 4) ** 2:
                hit = r
                break
        if hit is not None:
            form.shots.remove(shot)
            form.break_rock(game, hit)
            continue
        struck = next((s for s in form.saucers if shot.mine
                       and abs(s.delta_to(shot.x, shot.y)[0]) < SAUCER_HALF[0]
                       and abs(s.delta_to(shot.x, shot.y)[1]) < SAUCER_HALF[1]), None)
        if struck is not None:
            form.shots.remove(shot)
            form.blow_saucer(game, struck)
            continue
        if not shot.mine and p.alive and not p.dying:
            radius, dome = _ship_circle(p)
            dx, dy = wrapped_delta(shot.x, shot.y, p.x, p.y)
            if dx * dx + dy * dy < (radius + 4) ** 2:
                form.shots.remove(shot)
                _ship_hit(game, form)
    # --- the ship against rocks and the saucer
    if p.alive and not p.dying:
        radius, dome = _ship_circle(p)
        if p.invulnerable <= 0 or dome:
            for r in list(form.rocks):
                dx, dy = r.delta_to(p.x, p.y)
                if dx * dx + dy * dy < (r.radius + radius) ** 2:
                    form.break_rock(game, r)
                    _ship_hit(game, form)
                    break
            for s in list(form.saucers):
                if not p.alive or p.dying:
                    break
                dx, dy = s.delta_to(p.x, p.y)
                if abs(dx) < SAUCER_HALF[0] + radius * 0.6 and abs(dy) < SAUCER_HALF[1] + radius * 0.6:
                    form.blow_saucer(game, s)
                    _ship_hit(game, form)
    # --- the field is topped up with rocks coming in from outside, and the end
    if form.repop and not form.reached:
        if form.field_mass() < MASS_LOW:
            if form.spawn_in is None:
                form.spawn_in = form.rng.uniform(*REPOP_GAP)          # the field got thin: one comes in after a pause
            form.spawn_in -= dt
            if form.spawn_in <= 0:
                form.spawn_rock(p)
                form.spawn_in = form.rng.uniform(*REPOP_GAP)
        else:
            form.spawn_in = None
    if form.reached and not form.rocks and form.saucer is None:
        form.end_timer += dt
    else:
        form.end_timer = 0.0
    if form.endless:
        _next_level(game, form, p)


def _next_level(game, form, p):
    """The endless level: once no rock is left (not even a small one), the next level comes after LEVEL_PAUSE."""
    if form.rocks:
        form.next_in = 0.0
        return
    form.next_in += game.dt
    if form.next_in < LEVEL_PAUSE:
        return
    form.next_in = 0.0
    form.level += 1
    form.new_wave(p)
    form.banner = LEVEL_BANNER
    adv = getattr(game, "adventure", None)
    if isinstance(adv, dict):
        adv["level"] = form.level                    # (the HUD shows it after the name of the mission)
    try:
        game._play_level_vo(form.level)              # the announcer says the level, as at the start ("Level 2"...)
    except Exception:
        log_exc("asteroids._next_level")
