"""The test level "SpaceWar" (story_state.py, id `test_spacewar`): a remake of Spacewar!, the 1962 game of the PDP-1
that Cinematronics made an arcade game of in 1977, with the ship of the hangar and the birds of the game.

The rules of the original, kept here:

- A STAR in the middle of the screen (Jupiter) pulls the ships with a NEWTONIAN gravity (g = GM / r^2): the nearer, the
  harder, with no friction at all. The torpedoes are NOT pulled by it.
- INERTIA: a ship keeps its speed when the thrusters are off; the turn is a constant angular speed that does not change
  the way the ship travels, only where its nose points; the thrust adds speed in the direction of the nose.
- The screen is joined on its four sides (what goes out by one comes back by the opposite one, on the same path), for the
  ships and the torpedoes.
- A ship is destroyed by a torpedo, by touching the star, or by touching another ship (the two are lost).
- The torpedoes are few (a stock, a delay between two shots, a few in the air at once).
- The "CBS opening": the ship is at rest and falls towards the star; the pilot turns the ship perpendicular to the axis
  of the star and pushes for two or three seconds: that is a stable orbit, from which the opponent can be shot.

The player flies the real Player of the game (Player.asteroid_mode, with `sw_physics` for this physics: Player.
_update_asteroid calls `fly`), with ONE life: when it is destroyed it goes in pixel dust (ship_burn) and the level is over.
The opponents are the blue and the green birds, which have the same physics (`Bird`) and a small pilot (`Bird.think`);
they are faster at each of the three levels (LEVELS: 1 blue / 1 blue and 1 green / 2 blue and 2 green). The level ends
when the player is destroyed, when the three levels are won (`all_dead()`), or when nobody has a torpedo left.

`SpaceWarFormation` looks like a formation without enemies to the rest of the game; `tick(game)` runs it every frame.
"""
import math
import random

import pygame

import asteroids
from errlog import log_exc
from settings import BASE_HEIGHT, BASE_WIDTH, asset_path

CX, CY = BASE_WIDTH / 2.0, BASE_HEIGHT / 2.0            # the star
# The central planet (PLANETS; set_planet() chooses it for the level, Jupiter by default): its pull g = GM / r^2, the disc
# as it is seen (a ship that touches it is destroyed; the rings of Saturn are NOT in the zone), the thrust of the ships
# (POWER: a lighter planet makes for slower ships) and where the player starts. The sizes and the pulls follow the real
# planets (Saturn 0.84 of Jupiter's radius, Uranus and Neptune about 0.36) but are brought closer to Jupiter's, so that
# the discs stay pretty and the game playable.
PLANETS = {
    "jupiter": {"gm": 5.0e6, "r": 76.0, "draw": 160, "power": 1.0, "start": 340.0, "glow": (255, 190, 120)},
    "saturn": {"gm": 2.7e6, "r": 64.0, "draw": 320, "power": 0.6, "start": 260.0, "glow": (240, 215, 150)},
    "uranus": {"gm": 1.5e6, "r": 40.0, "draw": 100, "power": 0.6, "start": 260.0, "glow": (150, 225, 235)},
    "neptune": {"gm": 1.6e6, "r": 38.0, "draw": 100, "power": 0.6, "start": 260.0, "glow": (80, 130, 255)},
}
PLANET_KEYS = tuple(PLANETS)
PLANET = "jupiter"
GM = PLANETS["jupiter"]["gm"]                           # its pull: g = GM / r^2
MIN_R = 20.0                                            # (the pull stops growing inside this: never infinite)
STAR_DRAW = PLANETS["jupiter"]["draw"]                  # the picture of the star (px)
STAR_R = PLANETS["jupiter"]["r"]                        # the disc as it is seen: a ship that touches it is destroyed
POWER = 1.0                                             # the thrust of every ship is multiplied by this
CRASH_SHARE = 0.5                                       # (the centre of a ship is lost this share of its radius inside the disc)
PLAYER_RADIUS = 9.0                                     # the ship of the player is drawn at half its size
BIRD_RADIUS = 17.0
THRUST = 58.0                                           # px/s^2: the thrusters of a bird (before its level's scale)
PLAYER_THRUST = 110.0                                   # ... and those of the player: stronger
TURN_SPEED = 3.0                                        # rad/s, constant
MAX_SPEED = 900.0                                       # (only so that nothing can jump over the star in one step)
SUBSTEP = 1.0 / 120.0
START_RADIUS = PLANETS["jupiter"]["start"]              # where the player starts: left of the star, at rest, nose up
LEVELS = [(1, 0, 0), (1, 1, 0), (2, 1, 1)]               # (blue birds, green birds, boss saucers) of the three levels; the last
                                                        # level is won when its saucer is destroyed
LEVEL_SCALE = [1.0, 1.15, 1.3]                          # the birds' thrust, turn and rate of fire, per level
PLAYER_TORPEDOES = 20                                   # the stock of the player, filled again at each level
BIRD_TORPEDOES = 8                                      # the stock of each bird
TORPEDO_SPEED = 430.0                                   # px/s, on top of the speed of the ship that fires it
TORPEDO_LIFE = 1.9                                      # seconds
BIRD_TORPEDO_SPEED = 230.0                              # the torpedoes of the enemies are slow: they can be dodged
BIRD_TORPEDO_LIFE = 3.4                                 # (so they last longer: about the same reach)
SAUCER = 3                                              # the kind of the boss saucer
SAUCER_RADIUS = 27.0
SAUCER_HP = 3                                           # torpedoes that destroy it
SAUCER_TORPEDOES = 14
SAUCER_IN_AIR = 3
HIT_FLASH = 0.25                                        # seconds a hit saucer stays lit
TORPEDO_RADIUS = 5.0
PLAYER_GAP = 0.4                                        # seconds between two torpedoes of the player (the reload)
PLAYER_IN_AIR = 4                                       # his torpedoes in the air at once
FIRST_FIRE = (4.5, 6.5)                                 # seconds before a bird's first torpedo (the player's opening)
AIM_ERROR = 0.07                                        # rad: a bird is not a perfect shot
BIRD_GAP = 2.0                                          # (per bird, divided by LEVEL_SCALE)
BIRD_IN_AIR = 2
SELF_SAFE = 0.3                                         # seconds a torpedo spares the ship that fired it
PLAYER_SCALE = 0.5                                      # the ship of the player is drawn at half its size
ROCK_FIRST = (7.0, 11.0)                                # seconds before the first small asteroid of a level
ROCK_GAP = (10.0, 18.0)                                 # ... and between two
ROCK_SPEED = (300.0, 480.0)
ROCK_CRASH_KEEP = 0.15                                  # a path that ends in the star is kept this often (so well under 1 in 3)
ROCK_MARGIN = 40.0                                      # how far outside the screen it comes in from
LEVEL_PAUSE = 2.2                                       # seconds between two levels
END_PAUSE = 1.6                                         # after the last bird of the last level
EXHAUST_PAUSE = 2.4                                     # after the last torpedo
ANNOUNCE = 2.0
HINT_SECONDS = 9.0
AIM_TOLERANCE = 0.10                                    # rad
BIRD_RANGE = 650.0
LANES = (192.0, 244.0, 296.0, 340.0)                    # the circular orbits the birds start on (one each: no two of them meet)
COAST_MAX = 0.35                                        # seconds the longest push along the nose lasts
COAST_GAP = 40.0                                        # ... and the orbit it makes must keep this far (in distance from the star) from theirs
COAST_FAR = 345.0                                       # ... and stay inside the screen
LOOKAHEAD = 4.0                                         # seconds the bird looks ahead for the star
LOOK_STEP = 0.2
LOOK_SUBSTEP = 1.0 / 60.0
THINK_GAP = 0.1
SAFE_MARGIN = 52.0

_frames = {}


# ------------------------------------------------------------------ the planet
def set_planet(key):
    """Choose the central planet of the level (a key of PLANETS; Jupiter when unknown). The module keeps it in GM, STAR_R,
    STAR_DRAW, START_RADIUS and POWER, which the physics (and the player's `fly` calls) read."""
    global PLANET, GM, STAR_R, STAR_DRAW, START_RADIUS, POWER
    if key not in PLANETS:
        key = "jupiter"
    d = PLANETS[key]
    PLANET = key
    GM, STAR_R, STAR_DRAW, START_RADIUS, POWER = d["gm"], d["r"], d["draw"], d["start"], d["power"]
    return key


# ------------------------------------------------------------------ physics
def gravity(x, y):
    """The pull of the star on (x, y): (ax, ay), towards the middle of the screen."""
    dx, dy = CX - x, CY - y
    r = max(MIN_R, math.hypot(dx, dy))
    g = GM / (r * r)
    return g * dx / r, g * dy / r


def orbit_band(x, y, vx, vy):
    """The nearest and the farthest distance from the star of the orbit a ship follows from here with this speed and no
    thrust (the Kepler ellipse), or None when it is not a closed orbit."""
    dx, dy = x - CX, y - CY
    r = math.hypot(dx, dy)
    energy = 0.5 * (vx * vx + vy * vy) - GM / max(MIN_R, r)
    if energy >= 0:
        return None
    ang = dx * vy - dy * vx
    a = -GM / (2.0 * energy)
    e = math.sqrt(max(0.0, 1.0 + 2.0 * energy * ang * ang / (GM * GM)))
    return a * (1.0 - e), a * (1.0 + e)


def circular_speed(r):
    return math.sqrt(GM / max(MIN_R, r))


def fly(obj, dt, turn, push, scale=1.0, thrust=THRUST, radius=BIRD_RADIUS):
    """One frame of a ship (the player or a bird: anything with x, y, ast_vx, ast_vy, ast_angle): turn at a constant
    speed, push along the nose, be pulled by the star, keep the speed. True when the ship has touched the star."""
    obj.ast_angle = (obj.ast_angle + turn * TURN_SPEED * scale * dt + math.pi) % (2 * math.pi) - math.pi
    steps = max(1, int(math.ceil(dt / SUBSTEP)))
    h = dt / steps
    ca, sa = math.cos(obj.ast_angle), math.sin(obj.ast_angle)
    crashed = False
    for _ in range(steps):
        gx, gy = gravity(obj.x, obj.y)
        ax, ay = gx, gy
        if push:
            ax += ca * thrust * scale * POWER
            ay += sa * thrust * scale * POWER
        obj.ast_vx += ax * h
        obj.ast_vy += ay * h
        speed = math.hypot(obj.ast_vx, obj.ast_vy)
        if speed > MAX_SPEED:
            obj.ast_vx *= MAX_SPEED / speed
            obj.ast_vy *= MAX_SPEED / speed
        obj.x = (obj.x + obj.ast_vx * h) % BASE_WIDTH
        obj.y = (obj.y + obj.ast_vy * h) % BASE_HEIGHT
        if math.hypot(obj.x - CX, obj.y - CY) < STAR_R + CRASH_SHARE * radius:
            crashed = True
    return crashed


def periapsis_danger(x, y, vx, vy, horizon=LOOKAHEAD, margin=SAFE_MARGIN, push=None):
    """Does the free fall of a ship (no thrust) go inside the safety ring of the star within `horizon` seconds? `push` =
    (ax, ay, seconds): the ship first pushes with that acceleration for that long, then falls free."""
    t = 0.0
    ax = ay = 0.0
    push_t = 0.0
    if push is not None:
        ax, ay, push_t = push
    steps = int(round(LOOK_STEP / LOOK_SUBSTEP))
    while t < horizon:
        for n in range(steps):
            gx, gy = gravity(x, y)
            on = t + n * LOOK_SUBSTEP < push_t
            vx += (gx + (ax if on else 0.0)) * LOOK_SUBSTEP
            vy += (gy + (ay if on else 0.0)) * LOOK_SUBSTEP
            x += vx * LOOK_SUBSTEP
            y += vy * LOOK_SUBSTEP
        if math.hypot(x - CX, y - CY) < STAR_R + margin:
            return True
        t += LOOK_STEP
    return False


def start_state():
    """The player at the start of a level: left of the star, at rest, nose up (perpendicular to the axis of the star)."""
    return CX - START_RADIUS, CY, 0.0, 0.0, -math.pi / 2


def angle_diff(a, b):
    """b - a, in -pi..pi."""
    return (b - a + math.pi) % (2 * math.pi) - math.pi


# ------------------------------------------------------------------ pictures
def star_image():
    """The picture of the planet of the level (centred on the star; Saturn's is wider: its rings are not in the zone)."""
    key = ("star", PLANET)
    img = _frames.get(key)
    if img is None:
        d = PLANETS[PLANET]
        try:
            img = pygame.image.load(asset_path("sprites", "spacewar", PLANET + ".png")).convert_alpha()
            if img.get_width() != d["draw"]:
                img = pygame.transform.smoothscale(img, (d["draw"], d["draw"]))
        except Exception:
            log_exc("spacewar.star_image")
            n = int(d["draw"])
            img = pygame.Surface((n, n), pygame.SRCALPHA)
            pygame.draw.circle(img, d["glow"], (n // 2, n // 2), int(d["r"]))
        _frames[key] = img
    return img


def bird_images(kind):
    """The two flaps of a bird: kind 1 = the blue one, 2 = the green one (sprites of the game, nose up)."""
    key = ("bird", kind)
    imgs = _frames.get(key)
    if imgs is None:
        imgs = []
        for n in range(2):
            try:
                imgs.append(pygame.image.load(asset_path("sprites", "bird%d_flap%d.png" % (kind, n))).convert_alpha())
            except Exception:
                log_exc("spacewar.bird_images")
        if not imgs:
            ball = pygame.Surface((38, 36), pygame.SRCALPHA)
            pygame.draw.polygon(ball, (90, 150, 255) if kind == 1 else (120, 200, 90), [(19, 2), (36, 32), (2, 32)])
            imgs = [ball]
        _frames[key] = imgs
    return imgs


# ------------------------------------------------------------------ things
class Torpedo:
    def __init__(self, x, y, vx, vy, owner):
        self.x, self.y, self.vx, self.vy = float(x), float(y), float(vx), float(vy)
        self.owner = owner                  # "player" or the Bird that fired it
        self.life = TORPEDO_LIFE if owner == "player" else BIRD_TORPEDO_LIFE
        self.age = 0.0
        self.wrap = owner == "player"       # the torpedoes of the birds do NOT come round the screen: they end at the edge

    def update(self, dt):
        # (not pulled by the star: a straight line; the player's go round the joined screen)
        if self.wrap:
            self.x = (self.x + self.vx * dt) % BASE_WIDTH
            self.y = (self.y + self.vy * dt) % BASE_HEIGHT
        else:
            self.x += self.vx * dt
            self.y += self.vy * dt
            if not (0.0 <= self.x < BASE_WIDTH and 0.0 <= self.y < BASE_HEIGHT):
                self.life = 0.0
        self.life -= dt
        self.age += dt


class SpaceRock:
    """The small asteroid of the Asteroids level that crosses the screen now and then: it comes in from outside, is pulled
    by the star like a ship, and goes out by an edge (the screen does not wrap for it). It destroys what it touches."""

    def __init__(self, x, y, vx, vy, rng):
        self.x, self.y, self.vx, self.vy = float(x), float(y), float(vx), float(vy)
        self.radius = float(asteroids.ROCK_RADIUS[1])
        self.variant = rng.randrange(asteroids.ROCK_VARIANTS)
        self.phase = rng.uniform(0, asteroids.ROCK_FRAMES)
        self.spin = rng.uniform(6.0, 14.0) * rng.choice((-1, 1))
        self.rot = 0.0
        self.rspin = rng.uniform(-90.0, 90.0)
        self.inside = False                 # it has been on the screen
        self.age = 0.0

    def update(self, dt):
        steps = max(1, int(math.ceil(dt / SUBSTEP)))
        h = dt / steps
        for _ in range(steps):
            gx, gy = gravity(self.x, self.y)
            self.vx += gx * h
            self.vy += gy * h
            self.x += self.vx * h
            self.y += self.vy * h
        self.phase = (self.phase + self.spin * dt) % asteroids.ROCK_FRAMES
        self.rot = (self.rot + self.rspin * dt) % 360
        self.age += dt
        if 0 <= self.x < BASE_WIDTH and 0 <= self.y < BASE_HEIGHT:
            self.inside = True

    def on_star(self):
        return math.hypot(self.x - CX, self.y - CY) < STAR_R + CRASH_SHARE * self.radius

    def gone(self):
        """Out by an edge after having been in (or lost far outside)."""
        m = self.radius + 2
        out = not (-m <= self.x < BASE_WIDTH + m and -m <= self.y < BASE_HEIGHT + m)
        return (self.inside and out) or self.age > 40.0

    def image(self):
        cells = asteroids.rock_frames(1, self.variant)
        img = cells[int(self.phase) % len(cells)]
        return pygame.transform.rotate(img, self.rot)


def rock_crashes(x, y, vx, vy):
    """Does a rock that comes in at this point with this speed end on the star (and not out by an edge)?"""
    rock = SpaceRock(x, y, vx, vy, random.Random(0))
    while not rock.gone():
        rock.update(1.0 / 30.0)
        if rock.on_star():
            return True
    return False


def launch_rock(rng):
    """A small asteroid: where it comes in (just outside an edge), at what speed and which way. The path is chosen so that
    it ends on the star rarely: one that does is only kept ROCK_CRASH_KEEP of the time (and never at the last try)."""
    best = None
    for attempt in range(30):
        edge = rng.randrange(4)
        if edge == 0:
            x, y = -ROCK_MARGIN, rng.uniform(0, BASE_HEIGHT)
        elif edge == 1:
            x, y = BASE_WIDTH + ROCK_MARGIN, rng.uniform(0, BASE_HEIGHT)
        elif edge == 2:
            x, y = rng.uniform(0, BASE_WIDTH), -ROCK_MARGIN
        else:
            x, y = rng.uniform(0, BASE_WIDTH), BASE_HEIGHT + ROCK_MARGIN
        tx, ty = CX + rng.uniform(-430, 430), CY + rng.uniform(-260, 260)
        a = math.atan2(ty - y, tx - x)
        sp = rng.uniform(*ROCK_SPEED)
        vx, vy = math.cos(a) * sp, math.sin(a) * sp
        best = (x, y, vx, vy)
        if not rock_crashes(x, y, vx, vy) or (rng.random() < ROCK_CRASH_KEEP and attempt < 29):
            break
    return SpaceRock(best[0], best[1], best[2], best[3], rng)


class Bird:
    """An opponent: a blue or green bird flying with the physics of the player (and a small pilot)."""

    def __init__(self, kind, x, y, vx, vy, angle, scale, rng):
        self.kind = kind
        self.x, self.y, self.ast_vx, self.ast_vy, self.ast_angle = float(x), float(y), float(vx), float(vy), float(angle)
        self.scale = float(scale)
        self.rng = rng
        self.alive = True
        self.radius = SAUCER_RADIUS if kind == SAUCER else BIRD_RADIUS
        self.hp = SAUCER_HP if kind == SAUCER else 1
        self.hit = 0.0                                        # seconds left of the flash of a hit
        self.torpedoes = SAUCER_TORPEDOES if kind == SAUCER else BIRD_TORPEDOES
        self.fire_cd = rng.uniform(*FIRST_FIRE) / self.scale
        self.phase = rng.uniform(0, 4)
        self.push = False
        self.turn = 0.0
        self.think_in = 0.0
        self.danger = False
        self.sense = 1.0 if rng.random() < 0.5 else -1.0      # which way it goes round when it has no side speed
        self.mates = []                                       # the other birds of the level (it keeps away from them)
        self.clear_ahead = True
        self.coast_in = rng.uniform(1.5, 3.5)
        self.coast = 0.0

    def think(self, dt, target):
        """The pilot: (turn, push, fire). Keep out of the star first; else turn to the player (leading him) and fire."""
        self.fire_cd = max(0.0, self.fire_cd - dt)
        self.think_in -= dt
        if self.think_in <= 0:                       # (looking ahead is the costly part: ten times a second is enough)
            self.think_in = THINK_GAP
            self.danger = periapsis_danger(self.x, self.y, self.ast_vx, self.ast_vy)
            self.clear_ahead = not periapsis_danger(
                self.x, self.y, self.ast_vx + math.cos(self.ast_angle) * THRUST * POWER * self.scale * 0.7,
                self.ast_vy + math.sin(self.ast_angle) * THRUST * POWER * self.scale * 0.7, 2.0, SAFE_MARGIN + 25)
        if self.danger:
            diff = angle_diff(self.ast_angle, self._escape_angle())
            self.turn = max(-1.0, min(1.0, diff * 4.0))
            self.push = abs(diff) < 0.7
            return self.turn, self.push, False
        if target is None:
            self.turn, self.push = 0.0, False
            return self.turn, self.push, False
        dx, dy = asteroids.wrapped_delta(self.x, self.y, target.x, target.y)
        dist = math.hypot(dx, dy) or 1.0
        t = dist / BIRD_TORPEDO_SPEED
        goal = math.atan2(dy + (target.ast_vy - self.ast_vy) * t, dx + (target.ast_vx - self.ast_vx) * t)
        diff = angle_diff(self.ast_angle, goal)
        self.turn = max(-1.0, min(1.0, diff * 5.0))
        fire = (abs(diff) < AIM_TOLERANCE and dist < BIRD_RANGE and self.fire_cd <= 0 and self.torpedoes > 0)
        # now and then a short push along the nose, so that the bird does not sit on one orbit for ever (only while the
        # way ahead stays clear of the star)
        self.coast_in -= dt
        if self.coast > 0:
            self.coast = max(0.0, self.coast - dt)
        elif self.coast_in <= 0:
            self.coast_in = self.rng.uniform(3.0, 6.0)
            if self._coast_is_safe():
                self.coast = self.rng.uniform(0.15, COAST_MAX)
            else:
                self.coast_in = self.rng.uniform(0.5, 1.2)               # (not now: it tries again soon)
        self.push = self.coast > 0 and abs(diff) < 1.2 and self.clear_ahead
        if self.coast > 0:                           # (it holds its heading while it pushes: that is the push that was checked)
            self.turn, fire = 0.0, False
        return self.turn, self.push, fire

    def _coast_is_safe(self):
        """May the bird push along its nose for a moment now? Only if its orbit after the push (the longest one) stays out of
        the star, inside the screen, and does not share any distance from the star with the orbit of another bird (plus a
        gap): the pushes change the orbit, and orbits that crossed were the cause of the collisions between birds."""
        kick = THRUST * POWER * self.scale * COAST_MAX
        band = orbit_band(self.x, self.y, self.ast_vx + math.cos(self.ast_angle) * kick,
                          self.ast_vy + math.sin(self.ast_angle) * kick)
        if band is None or band[0] < STAR_R + SAFE_MARGIN + 40 or band[1] > COAST_FAR:
            return False
        for o in self.mates:
            if o is self or not o.alive:
                continue
            other = orbit_band(o.x, o.y, o.ast_vx, o.ast_vy)
            if other is None or (band[0] - COAST_GAP < other[1] and other[0] - COAST_GAP < band[1]):
                return False
        return True

    def _escape_angle(self):
        """The way to push to keep out of the star: sideways (the pull is too strong to push straight against it, so the
        orbit is raised the way of the CBS opening), along the sideways speed the bird already has, a little outward."""
        ox, oy = self.x - CX, self.y - CY
        r = math.hypot(ox, oy) or 1.0
        ux, uy = ox / r, oy / r
        radial = self.ast_vx * ux + self.ast_vy * uy
        side = 1.0 if (self.ast_vx * -uy + self.ast_vy * ux) >= 0 else -1.0
        if abs(self.ast_vx * -uy + self.ast_vy * ux) < 8.0:
            side = self.sense
        gx = -uy * side
        gy = ux * side
        w = 0.35 if radial < 0 else 0.12
        return math.atan2(gy * (1.0 - w) + uy * w, gx * (1.0 - w) + ux * w)

    def image(self):
        if self.kind == SAUCER:                      # (the saucer does not turn: it only shows a red flash when it is hit)
            img = asteroids.saucer_frame(self.phase)
            if self.hit > 0:
                img = img.copy()
                k = int(150 * min(1.0, self.hit / HIT_FLASH))
                img.fill((k, k, k, 0), special_flags=pygame.BLEND_RGB_ADD)
            return img
        imgs = bird_images(self.kind)
        img = imgs[int(self.phase * 6) % len(imgs)]
        return pygame.transform.rotate(img, -math.degrees(self.ast_angle) - 90.0)


class SpaceWarFormation:
    """The field of the level: the star, the birds, the torpedoes, the dust. Looks like a formation without enemies to
    the rest of the game."""

    def __init__(self, speed_mult=1.0, rng=None):
        self.enemies = []
        self.bullets = []
        self.swarm = None
        self.sounds = None
        self.font = None
        self.text_cache = None
        self.rng = rng if rng is not None else random.Random()
        self.speed_mult = float(speed_mult)
        self.level = 1
        self.birds = []
        self.torpedoes = []
        self.sparks = []
        self.rock = None                    # the small asteroid that crosses the screen now and then
        self.rock_in = self.rng.uniform(*ROCK_FIRST)
        self.player_torpedoes = PLAYER_TORPEDOES
        self.fire_cd = 0.0
        self.time = 0.0
        self.level_time = 0.0
        self.destroyed = 0                  # birds destroyed so far
        self.pause = 0.0                    # seconds before the next level
        self.end_timer = 0.0
        self.exhaust_timer = 0.0
        self.won = False
        self.exhausted = False
        self.started = False
        self.tip = (180, 220, 255)

    # --- what the rest of the game asks of a formation ---
    def update(self, dt, player_x):
        return None

    def get_alive_enemies(self):
        return []

    def get_hittable_enemies(self):
        return []

    def remaining(self):
        return sum(1 for b in self.birds if b.alive)

    def level_done(self):
        """Is the level won? The last one when its saucer is destroyed (the birds that are left do not matter), the others
        when no bird is left."""
        bosses = [b for b in self.birds if b.kind == SAUCER]
        if bosses:
            return not any(b.alive for b in bosses)
        return self.remaining() == 0

    def swarm_remaining(self):
        return self.remaining()

    def all_dead(self):
        """The three levels are won (and a short pause to see the last explosion)."""
        return self.won and self.end_timer >= END_PAUSE

    # --- the levels ---
    def start_level(self, number, player=None):
        """Put the birds of level `number` (1..3) in orbit and the player back at the start, with a full stock."""
        self.level = max(1, min(len(LEVELS), int(number)))
        blue, green, boss = LEVELS[self.level - 1]
        scale = LEVEL_SCALE[self.level - 1] * max(0.5, self.speed_mult)
        kinds = [1] * blue + [2] * green + [SAUCER] * boss
        self.rng.shuffle(kinds)
        angles = [0.0, math.pi / 2, -math.pi / 2, math.pi / 4][:len(kinds)]
        sense = 1.0 if self.rng.random() < 0.5 else -1.0          # all the birds go round the same way (none meets another head on)
        lanes = list(LANES)
        self.rng.shuffle(lanes)
        self.birds = []
        for kind, a, r in zip(kinds, angles, lanes):
            x, y = CX + math.cos(a) * r, CY + math.sin(a) * r
            v = circular_speed(r) * self.rng.uniform(0.99, 1.01)
            vx, vy = -math.sin(a) * v * sense, math.cos(a) * v * sense
            heading = math.atan2(vy, vx)
            self.birds.append(Bird(kind, x, y, vx, vy, heading, scale, self.rng))
        for b in self.birds:
            b.mates = self.birds
        self.torpedoes = []
        self.rock = None
        self.rock_in = self.rng.uniform(*ROCK_FIRST)
        self.player_torpedoes = PLAYER_TORPEDOES
        self.fire_cd = 0.0
        self.level_time = 0.0
        self.pause = 0.0
        if player is not None:
            player.x, player.y, player.ast_vx, player.ast_vy, player.ast_angle = start_state()
            player.rect.center = (int(player.x), int(player.y))

    def torpedoes_left(self):
        return self.player_torpedoes + sum(b.torpedoes for b in self.birds if b.alive)

    def debris(self, x, y, kind, n, speed, life=(0.4, 1.0), size=(2.0, 5.0)):
        for _ in range(n):
            a = self.rng.uniform(0, math.tau)
            sp = self.rng.uniform(0.15, 1.0) * speed
            self.sparks.append(asteroids.Spark(x, y, math.cos(a) * sp, math.sin(a) * sp, self.rng.uniform(*life), kind,
                                               self.rng.uniform(*size)))

    # --- drawing ---
    def _say(self, surface, text, color, cy):
        font = self.font
        if font is None or not text:
            return
        try:
            img = self.text_cache.get(font, text, color) if self.text_cache is not None else font.render(text, True, color)
        except Exception:
            log_exc("spacewar._say")
            return
        surface.blit(img, (BASE_WIDTH // 2 - img.get_width() // 2, int(cy - img.get_height() / 2)))

    def _life_bar(self, surface, b):
        w = 56
        x, y = int(b.x - w / 2), int(b.y - b.radius - 22)
        pygame.draw.rect(surface, (30, 12, 12), (x - 1, y - 1, w + 2, 7))
        pygame.draw.rect(surface, (230, 70, 50), (x, y, int(w * b.hp / SAUCER_HP), 5))

    def draw(self, surface):
        img = star_image()
        asteroids._add_glow(surface, PLANETS[PLANET]["glow"], (CX, CY), int(STAR_R * 2) + 70)
        surface.blit(img, (int(CX - img.get_width() / 2), int(CY - img.get_height() / 2)))
        for b in self.birds:
            if b.alive:
                asteroids._blit_wrapped(surface, b.image(), b.x, b.y)
                if b.kind == SAUCER:
                    self._life_bar(surface, b)
        if self.rock is not None:
            img = self.rock.image()
            surface.blit(img, (int(self.rock.x - img.get_width() / 2), int(self.rock.y - img.get_height() / 2)))
        for p in self.sparks:
            a = max(0.0, p.life / p.max)
            if p.kind == "rock":
                c = (int(150 * a + 40), int(135 * a + 35), int(120 * a + 30))
                pygame.draw.circle(surface, c, (int(p.x), int(p.y)), max(1, int(p.size * (0.5 + 0.5 * a))))
            elif p.kind == "fire":
                asteroids._add_glow(surface, (255, 170, 60), (p.x, p.y), max(4, int(p.size * 7 * a + 4)))
            elif p.kind == "spark":
                pygame.draw.line(surface, (255, int(220 * a), int(120 * a)), (p.x, p.y), (p.x - p.vx * 0.04, p.y - p.vy * 0.04), 2)
            elif p.kind == "flash":
                k = 1.0 - a
                asteroids._add_glow(surface, (255, 150, 40), (p.x, p.y), int(p.size * 2 * (1.0 + 1.2 * k)))
        for tp in self.torpedoes:
            sp = math.hypot(tp.vx, tp.vy) or 1.0
            ux, uy = tp.vx / sp, tp.vy / sp
            if tp.owner == "player":
                draw_torpedo(surface, tp.x, tp.y, ux, uy, self.tip)
            else:
                asteroids._add_glow(surface, (255, 60, 40), (tp.x, tp.y), 24)
                pygame.draw.circle(surface, (255, 200, 180), (int(tp.x), int(tp.y)), 3)
        if self.level_time < ANNOUNCE and self.started:
            self._say(surface, _label("story_spacewar_level").format(n=self.level, m=len(LEVELS)), (255, 215, 120), 150)
        if self.level_time < ANNOUNCE and self.started and any(b.kind == SAUCER for b in self.birds):
            self._say(surface, _label("story_spacewar_boss"), (255, 120, 100), 182)
        if self.pause > 0 and self.level < len(LEVELS):
            self._say(surface, _label("story_spacewar_next"), (140, 255, 170), 200)
        if self.exhausted:
            self._say(surface, _label("story_spacewar_empty"), (255, 120, 100), 200)
        if self.level == 1 and self.time < HINT_SECONDS and self.started:
            self._say(surface, _label("story_spacewar_hint"), (170, 200, 255), BASE_HEIGHT - 40)


def draw_torpedo(surface, x, y, ux, uy, tip):
    """A torpedo of the player, drawn as an air-to-air missile: a slim white fuselage with an ogive nose in the colour of the
    hull, a seeker band, two small canards in front, four swept tail fins behind (two seen from the side) and a flame that
    ends in a thin plume. (ux, uy) is the way it flies; (x, y) the middle of the body."""
    vx, vy = -uy, ux                                       # (sideways)

    def pt(a, b):
        return (x + ux * a + vx * b, y + uy * a + vy * b)

    asteroids._add_glow(surface, (255, 170, 80), pt(-15, 0), 17)                         # the engine
    pygame.draw.polygon(surface, (255, 150, 60), [pt(-13, 1.9), pt(-13, -1.9), pt(-25, 0)])                    # the plume
    pygame.draw.polygon(surface, (255, 235, 150), [pt(-13, 1.1), pt(-13, -1.1), pt(-20, 0)])
    for side in (1, -1):                                                                                          # the tail fins
        pygame.draw.polygon(surface, (118, 126, 146), [pt(-5, side * 2.2), pt(-11, side * 6.8), pt(-13.5, side * 6.8),
                                                       pt(-13, side * 2.2)])
        pygame.draw.line(surface, (190, 198, 214), pt(-5, side * 2.4), pt(-11, side * 6.6), 1)
    pygame.draw.polygon(surface, (224, 228, 238), [pt(-13, 2.4), pt(7, 2.4), pt(7, -2.4), pt(-13, -2.4)])     # the fuselage
    pygame.draw.polygon(surface, (168, 175, 192), [pt(-13, -0.3), pt(7, -0.3), pt(7, -2.4), pt(-13, -2.4)])   # (its shaded side)
    pygame.draw.polygon(surface, (214, 70, 54), [pt(-9, 2.4), pt(-6.5, 2.4), pt(-6.5, -2.4), pt(-9, -2.4)])   # a red band
    pygame.draw.polygon(surface, (60, 66, 82), [pt(-13, 2.4), pt(-12, 2.4), pt(-12, -2.4), pt(-13, -2.4)])    # the nozzle
    pygame.draw.polygon(surface, tip, [pt(7, 2.4), pt(10.5, 1.9), pt(13.5, 1.0), pt(16.5, 0), pt(13.5, -1.0),
                                       pt(10.5, -1.9), pt(7, -2.4)])                                           # the ogive nose
    for side in (1, -1):                                                                                          # the canards
        pygame.draw.polygon(surface, (150, 158, 176), [pt(4, side * 2.4), pt(2.5, side * 5.0), pt(0.5, side * 5.0),
                                                       pt(1, side * 2.4)])


def _label(key):
    from i18n import t
    return t(key)


# ------------------------------------------------------------------ every frame
def active(game):
    form = getattr(game, "formation", None)
    return form if isinstance(form, SpaceWarFormation) else None


def _boom(game, form, x, y, big=False):
    game.explosions.append(game._boom(x, y, kind="gameover" if big else "enemy"))
    game.shake_amount = max(game.shake_amount, 22.0 if big else 8.0)
    try:
        game.sounds.play("explosion_big" if big else "explosion", x=x)
    except Exception:
        log_exc("spacewar._boom")
    form.debris(x, y, "fire", 30 if big else 22, 300, life=(0.4, 1.2), size=(3.0, 7.0))
    form.debris(x, y, "spark", 14, 360, life=(0.3, 0.9), size=(2.0, 3.0))
    form.debris(x, y, "flash", 1, 0, life=(0.35, 0.35), size=(40.0, 40.0))


def _kill_player(game, form):
    p = game.player
    if not p.alive or p.dying:
        return
    if p.burn_by_guardian(blast=True):  # the big blast (ship_blast): one life, no dome, no Phenix form that saves
        game.shake_amount = max(game.shake_amount, 30.0)
        try:
            game.sounds.play("explosion_big", x=p.x)
        except Exception:
            log_exc("spacewar._kill_player")
        form.debris(p.x, p.y, "spark", 18, 360, life=(0.3, 0.9), size=(2.0, 3.0))


def _kill_bird(game, form, bird):
    if not bird.alive:
        return
    bird.alive = False
    form.destroyed += 1
    _boom(game, form, bird.x, bird.y)


def _hurt_bird(game, form, bird):
    """A torpedo (or the rock) hits a bird: it is destroyed, or, for the boss saucer, it loses one of its hit points."""
    bird.hp -= 1
    if bird.hp > 0:
        bird.hit = HIT_FLASH
        form.debris(bird.x, bird.y, "spark", 10, 260, life=(0.2, 0.6), size=(2.0, 3.0))
        try:
            game.sounds.play("explosion", volume=0.6, x=bird.x)
        except Exception:
            log_exc("spacewar._hurt_bird")
        return
    _kill_bird(game, form, bird)


def _fire(form, owner, ship, mult=1.0, error=0.0):
    ca, sa = math.cos(ship.ast_angle + error), math.sin(ship.ast_angle + error)
    speed = TORPEDO_SPEED * mult if owner == "player" else BIRD_TORPEDO_SPEED
    reach = 26 if owner == "player" else ship.radius + 9
    form.torpedoes.append(Torpedo(ship.x + ca * reach, ship.y + sa * reach, ship.ast_vx + ca * speed,
                                  ship.ast_vy + sa * speed, owner))


def tick(game):
    """Every frame of the level: the birds fly and fire, the torpedoes, the collisions, the levels and the end. A no-op in
    any other mission."""
    form = active(game)
    if form is None or game.stage_transition is not None:
        return
    p = game.player
    dt = game.dt
    form.time += dt
    form.level_time += dt
    form.tip = asteroids.tip_color(p)
    if not form.started:
        form.started = True
        form.start_level(1, p)
    player_up = p.alive and not p.dying
    # --- the player: the star (Player._update_asteroid made the move), his torpedoes
    if player_up and getattr(p, "sw_crash", False):
        _kill_player(game, form)
        player_up = False
    p.sw_crash = False
    form.fire_cd = max(0.0, form.fire_cd - dt)
    if player_up and getattr(p, "ast_fire", False) and form.fire_cd <= 0 and form.player_torpedoes > 0 and \
            sum(1 for tp in form.torpedoes if tp.owner == "player") < PLAYER_IN_AIR and form.pause <= 0:
        form.fire_cd = PLAYER_GAP
        form.player_torpedoes -= 1
        _fire(form, "player", p, float(getattr(p, "bullet_speed_mult", 1.0) or 1.0))
        try:
            game.sounds.play("shoot", volume=0.45, x=p.x)
        except Exception:
            log_exc("spacewar.tick")
    p.ast_fire = False
    # --- the birds
    for b in form.birds:
        if not b.alive:
            continue
        b.phase += dt
        b.hit = max(0.0, b.hit - dt)
        turn, push, fire = b.think(dt, p if player_up else None)
        if fire and sum(1 for tp in form.torpedoes if tp.owner is b) < (SAUCER_IN_AIR if b.kind == SAUCER else BIRD_IN_AIR):
            b.fire_cd = BIRD_GAP / b.scale
            b.torpedoes -= 1
            _fire(form, b, b, 1.0, form.rng.uniform(-AIM_ERROR, AIM_ERROR))
            try:
                game.sounds.play("enemy_shoot", x=b.x)
            except Exception:
                log_exc("spacewar.tick")
        if fly(b, dt, turn, push, b.scale, THRUST, b.radius):
            _kill_bird(game, form, b)
    # --- torpedoes and dust
    for tp in form.torpedoes:
        tp.update(dt)
    form.torpedoes = [tp for tp in form.torpedoes if tp.life > 0]
    for tp in list(form.torpedoes):                      # the star stops a torpedo (it does not pull it)
        if math.hypot(tp.x - CX, tp.y - CY) < STAR_R:
            form.torpedoes.remove(tp)
            form.debris(tp.x, tp.y, "spark", 6, 200, life=(0.2, 0.5), size=(2.0, 3.0))
            form.debris(tp.x, tp.y, "fire", 3, 120, life=(0.2, 0.5), size=(2.0, 4.0))
    for sp in form.sparks:
        sp.x += sp.vx * dt
        sp.y += sp.vy * dt
        sp.life -= dt
        damp = math.exp(-1.6 * dt)
        sp.vx *= damp
        sp.vy *= damp
    form.sparks = [sp for sp in form.sparks if sp.life > 0]
    # --- torpedoes against ships
    for tp in list(form.torpedoes):
        if tp not in form.torpedoes:
            continue
        for b in form.birds:
            if not b.alive or (tp.owner is b and tp.age < SELF_SAFE):
                continue
            dx, dy = asteroids.wrapped_delta(tp.x, tp.y, b.x, b.y)
            if dx * dx + dy * dy < (b.radius + TORPEDO_RADIUS) ** 2:
                form.torpedoes.remove(tp)
                _hurt_bird(game, form, b)
                break
        else:
            if player_up and not (tp.owner == "player" and tp.age < SELF_SAFE):
                dx, dy = asteroids.wrapped_delta(tp.x, tp.y, p.x, p.y)
                if dx * dx + dy * dy < (PLAYER_RADIUS + TORPEDO_RADIUS) ** 2:
                    form.torpedoes.remove(tp)
                    _kill_player(game, form)
                    player_up = False
    # --- ships against ships (both are lost)
    crew = [b for b in form.birds if b.alive]
    if player_up:
        for b in crew:
            dx, dy = asteroids.wrapped_delta(p.x, p.y, b.x, b.y)
            if dx * dx + dy * dy < (PLAYER_RADIUS + b.radius) ** 2:
                if b.kind != SAUCER:                 # (the boss saucer is not hurt by the wreck of the ship)
                    _kill_bird(game, form, b)
                _kill_player(game, form)
                player_up = False
                break
    crew = [b for b in form.birds if b.alive]
    for i, a in enumerate(crew):
        for c in crew[i + 1:]:
            dx, dy = asteroids.wrapped_delta(a.x, a.y, c.x, c.y)
            if a.alive and c.alive and dx * dx + dy * dy < (a.radius + c.radius) ** 2:
                for x in (a, c):
                    if x.kind != SAUCER:             # (the boss saucer shrugs off a bird that crashes into it)
                        _kill_bird(game, form, x)
    # --- the small asteroid: it comes in now and then, is pulled by the star, goes out by an edge; it destroys ships
    if form.pause <= 0 and not form.won and form.rock is None:
        form.rock_in -= dt
        if form.rock_in <= 0:
            form.rock = launch_rock(form.rng)
            form.rock_in = form.rng.uniform(*ROCK_GAP)
    rock = form.rock
    if rock is not None:
        rock.update(dt)
        if rock.on_star():
            form.debris(rock.x, rock.y, "rock", 12, 220, life=(0.5, 1.2), size=(2.0, 4.0))
            form.debris(rock.x, rock.y, "fire", 6, 160, life=(0.3, 0.7), size=(3.0, 5.0))
            form.rock = rock = None
        elif rock.gone():
            form.rock = rock = None
    if rock is not None:
        for tp in list(form.torpedoes):
            if math.hypot(tp.x - rock.x, tp.y - rock.y) < rock.radius + TORPEDO_RADIUS:
                form.torpedoes.remove(tp)
                form.debris(rock.x, rock.y, "rock", 14, 240, life=(0.5, 1.2), size=(2.0, 4.0))
                form.rock = rock = None
                try:
                    game.sounds.play("explosion", x=tp.x)
                except Exception:
                    log_exc("spacewar.tick")
                break
    if rock is not None:
        hit = rock.radius * 0.8
        for b in form.birds:
            if b.alive and math.hypot(b.x - rock.x, b.y - rock.y) < hit + b.radius:
                _hurt_bird(game, form, b)
        if player_up and math.hypot(p.x - rock.x, p.y - rock.y) < hit + PLAYER_RADIUS:
            _kill_player(game, form)
            player_up = False
    # --- the levels and the end
    if not player_up:
        return
    if form.pause > 0:
        form.pause -= dt
        if form.pause <= 0:
            form.start_level(form.level + 1, p)
        return
    if form.won:
        form.end_timer += dt
        return
    if form.level_done() and form.level_time > 0.5:
        if form.level >= len(LEVELS):
            form.won = True
            form.end_timer = 0.0
        else:
            form.pause = LEVEL_PAUSE
        return
    # nobody has a torpedo left (and none is in the air): the level is over
    if form.torpedoes_left() == 0 and not form.torpedoes:
        form.exhausted = True
        form.exhaust_timer += dt
        if form.exhaust_timer >= EXHAUST_PAUSE:
            game._end_adventure(False)
    else:
        form.exhausted = False
        form.exhaust_timer = 0.0
