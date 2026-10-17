"""The BONUS test mission "Asteroids" (story_state.py, id `bonus_asteroids`): the game of Atari's Asteroids, played with
the ship of the hangar.

The ship turns (left / right), pushes (up) and fires; it keeps its speed, and what leaves one side of the screen comes
back by the opposite one (for the rocks, the shots, the saucer's shots and the ship). No hyperspace. The Player is the
real one of the game (lives, dome, death, jets, invulnerability): its `asteroid_mode` makes it fly free (Player.
_update_asteroid) and draws it turned (Player._draw_asteroid). Everything else is here:

- ROCKS: big, medium, small. A rock that is hit breaks in two of the size below; a small one is destroyed. Every rock
  hit counts, the fragments too: after TARGET the mission is won, once the screen is empty. When the screen is empty
  and the target is not reached, a new wave comes in from the edges. After the target nothing comes any more (no wave,
  no saucer) and a rock that is hit is just gone, it no longer breaks in two.
- THE SAUCER: the miniature saucer of the paint missions (invaders.saucer_image), now and then (about every 18 s,
  so 3 or 4 times in a mission, more in a long one) it crosses the screen zigzagging and fires at the ship, a little
  wide of it. Its shots break the rocks too. No saucer after the target is reached.
- Shots: at most MAX_SHOTS on the screen, they carry the speed of the ship and die after SHOT_LIFE seconds.
- Points (the test mission pays nothing in the hangar, see story_state): ROCK_POINTS, SAUCER_POINTS.

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

TARGET = 40                          # rocks to destroy (every piece counts) to win
FIRST_WAVE = 4                       # big rocks at the start
WAVE_ROCKS = (4, 6)                  # big rocks of a later wave: this many, more with every wave, at most the second
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
ROCK_VARIANTS = 2
ROCK_SPEED = {3: (40.0, 85.0), 2: (70.0, 150.0), 1: (90.0, 190.0)}
ROCK_POINTS = {3: 10, 2: 20, 1: 40}
SAUCER_POINTS = 100
SAUCER_SCALE = 1.4                   # the miniature of the paint missions is 72 px wide: this much bigger here
SAUCER_GAP = (14.0, 22.0)            # seconds between two saucers, the first one after SAUCER_FIRST
SAUCER_FIRST = (9.0, 13.0)
SAUCER_FIRE_GAP = 1.5
SAUCER_AIM_ERROR = 0.45              # rad: the saucer is not a good shot
SAUCER_SHOT_SPEED = 340.0
SAUCER_SHOT_LIFE = 2.2
SAUCER_HALF = (46, 19)               # what a shot of the ship must touch
SETTLE_MAX = 2.5                     # seconds the ship takes at most to turn its nose up once the rocks are gone
SPAWN_CLEAR = 190                    # a rock never comes in this close to the ship

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
    def __init__(self, size, x, y, vx, vy, rng):
        self.size = size
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
        self.x = (self.x + self.vx * dt) % BASE_WIDTH
        self.y = (self.y + self.vy * dt) % BASE_HEIGHT
        self.phase = (self.phase + self.spin * dt) % ROCK_FRAMES
        self.rot = (self.rot + self.rspin * dt) % 360

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
    def __init__(self, left, rng):
        self.x = -60.0 if left else BASE_WIDTH + 60.0
        self.y = rng.uniform(150, BASE_HEIGHT - 150)
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

    def __init__(self, speed_mult=1.0, rng=None, target=TARGET):
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
        self.saucer = None
        self.time = 0.0
        self.destroyed = 0                # rocks hit so far (every piece counts)
        self.waves = 0
        self.fire_cd = 0.0
        self.saucer_in = self.rng.uniform(*SAUCER_FIRST)
        self.settle = 0.0                 # seconds spent turning the nose up at the end
        self._aligned = False             # ... and the ship has its nose up and has stopped
        self.tip = (180, 220, 255)        # the colour of the shots: the hull's
        self.started = False

    # --- what the rest of the game asks of a formation ---
    def update(self, dt, player_x):
        return None

    def get_alive_enemies(self):
        return []

    def get_hittable_enemies(self):
        return []

    @property
    def reached(self):
        return self.destroyed >= self.target

    def remaining(self):
        """Rocks still on the screen once the target is reached; before it, the rocks still to be destroyed."""
        return len(self.rocks) if self.reached else max(0, self.target - self.destroyed)

    def swarm_remaining(self):
        return self.remaining()

    def all_dead(self):
        """The mission is won: the target reached, the screen empty, and the ship's nose turned up for its flight."""
        return self.reached and not self.rocks and self.saucer is None and self.settled()

    def settled(self):
        return self.settle >= SETTLE_MAX or self._aligned

    # --- the field ---
    def new_wave(self, player=None):
        """Big rocks come in from the edges, never close to the ship."""
        n = FIRST_WAVE if self.waves == 0 else min(WAVE_ROCKS[1], WAVE_ROCKS[0] + self.waves - 1)
        self.waves += 1
        px, py = (player.x, player.y) if player is not None else (BASE_WIDTH / 2, BASE_HEIGHT / 2)
        for _ in range(n):
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

    def blow_saucer(self, game):
        s = self.saucer
        if s is None:
            return
        self.saucer = None
        game._add_score(game.player, SAUCER_POINTS)
        self.debris(s.x, s.y, "fire", 40, 300, life=(0.4, 1.2), size=(3.0, 8.0))
        self.debris(s.x, s.y, "spark", 22, 380, life=(0.3, 0.9), size=(2.0, 3.0))
        self.sparks.append(Spark(s.x, s.y, 0, 0, 0.35, "flash", 90))
        game.explosions.append(game._boom(s.x, s.y, kind="enemy"))
        try:
            game.sounds.stop_sfx("saucer_pass", 150)
            game.sounds.play("explosion", volume=0.7, x=s.x)
        except Exception:
            log_exc("asteroids.blow_saucer")

    # --- drawing ---
    def draw(self, surface):
        for r in sorted(self.rocks, key=lambda r: -r.size):
            _blit_wrapped(surface, r.image(), r.x, r.y)
        if self.saucer is not None:
            s = self.saucer
            _blit_wrapped(surface, saucer_frame(s.age), s.x, s.y + math.sin(s.age * 5.0) * 2.0)
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


def _blit_wrapped(surface, img, x, y):
    """Draw `img` centred on (x, y), and again on the other side when it sticks out of the screen."""
    w, h = img.get_size()
    xs = [0]
    ys = [0]
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
    game.explosions.append(game._boom(old[0], old[1], kind=kind))
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
    if form.saucer is None and not form.reached:
        form.saucer_in -= dt
        if form.saucer_in <= 0:
            form.saucer = Saucer(form.rng.random() < 0.5, form.rng)
            form.saucer_in = form.rng.uniform(*SAUCER_GAP)
            try:
                game.sounds.play_voice("saucer_pass", x=form.saucer.x)
            except Exception:
                log_exc("asteroids.tick")
    if form.saucer is not None:
        s = form.saucer
        if s.update(dt, form.rng):
            form.saucer = None
        elif s.fire_in <= 0 and p.alive and not p.dying:
            s.fire_in = SAUCER_FIRE_GAP
            dx, dy = wrapped_delta(s.x, s.y, p.x, p.y)
            a = math.atan2(dy, dx) + form.rng.uniform(-SAUCER_AIM_ERROR, SAUCER_AIM_ERROR)
            form.shots.append(Shot(s.x, s.y, math.cos(a) * SAUCER_SHOT_SPEED, math.sin(a) * SAUCER_SHOT_SPEED,
                                   SAUCER_SHOT_LIFE, False))
            game.sounds.play("enemy_shoot", x=s.x)
        if form.saucer is not None:
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
            dx, dy = wrapped_delta(shot.x, shot.y, r.x, r.y)
            if dx * dx + dy * dy < (r.radius + 4) ** 2:
                hit = r
                break
        if hit is not None:
            form.shots.remove(shot)
            form.break_rock(game, hit)
            continue
        if shot.mine and form.saucer is not None:
            dx, dy = wrapped_delta(shot.x, shot.y, form.saucer.x, form.saucer.y)
            if abs(dx) < SAUCER_HALF[0] and abs(dy) < SAUCER_HALF[1]:
                form.shots.remove(shot)
                form.blow_saucer(game)
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
                dx, dy = wrapped_delta(p.x, p.y, r.x, r.y)
                if dx * dx + dy * dy < (r.radius + radius) ** 2:
                    form.break_rock(game, r)
                    _ship_hit(game, form)
                    break
            if form.saucer is not None and p.alive and not p.dying:
                dx, dy = wrapped_delta(p.x, p.y, form.saucer.x, form.saucer.y)
                if abs(dx) < SAUCER_HALF[0] + radius * 0.6 and abs(dy) < SAUCER_HALF[1] + radius * 0.6:
                    form.blow_saucer(game)
                    _ship_hit(game, form)
    # --- a new wave when the screen is empty, and the end
    if not form.rocks and not form.reached:
        form.new_wave(p)
    if form.reached and not form.rocks and form.saucer is None:
        p.ast_hold = True                       # the ship turns its nose up and stops: the flight to the map follows
        form.settle += dt
        form._aligned = bool(getattr(p, "ast_settled", False))
    else:
        p.ast_hold = False
        form.settle = 0.0
        form._aligned = False
