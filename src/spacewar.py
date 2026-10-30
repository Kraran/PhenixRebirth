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
GM = 5.0e6                                              # its pull: g = GM / r^2 (55 px/s^2 at 300 px)
MIN_R = 20.0                                            # (the pull stops growing inside this: never infinite)
STAR_DRAW = 160                                         # the picture of the star (px)
STAR_KILL = 56.0                                        # what touches the star is destroyed (centre of a ship)
SHIP_RADIUS = 18.0
THRUST = 58.0                                           # px/s^2: a little more than the pull at the start distance
TURN_SPEED = 3.0                                        # rad/s, constant
MAX_SPEED = 900.0                                       # (only so that nothing can jump over the star in one step)
SUBSTEP = 1.0 / 120.0
START_RADIUS = 275.0                                    # where the player starts: left of the star, at rest, nose up
LEVELS = [(1, 0), (1, 1), (2, 2)]                       # (blue birds, green birds) of the three levels
LEVEL_SCALE = [1.0, 1.15, 1.3]                          # the birds' thrust, turn and rate of fire, per level
PLAYER_TORPEDOES = 20                                   # the stock of the player, filled again at each level
BIRD_TORPEDOES = 8                                      # the stock of each bird
TORPEDO_SPEED = 430.0                                   # px/s, on top of the speed of the ship that fires it
TORPEDO_LIFE = 1.9                                      # seconds
TORPEDO_RADIUS = 5.0
PLAYER_GAP = 0.4                                        # seconds between two torpedoes of the player (the reload)
PLAYER_IN_AIR = 4                                       # his torpedoes in the air at once
FIRST_FIRE = (4.5, 6.5)                                 # seconds before a bird's first torpedo (the player's opening)
AIM_ERROR = 0.07                                        # rad: a bird is not a perfect shot
BIRD_GAP = 2.0                                          # (per bird, divided by LEVEL_SCALE)
BIRD_IN_AIR = 2
SELF_SAFE = 0.3                                         # seconds a torpedo spares the ship that fired it
LEVEL_PAUSE = 2.2                                       # seconds between two levels
END_PAUSE = 1.6                                         # after the last bird of the last level
EXHAUST_PAUSE = 2.4                                     # after the last torpedo
ANNOUNCE = 2.0
HINT_SECONDS = 9.0
AIM_TOLERANCE = 0.10                                    # rad
BIRD_RANGE = 650.0
LOOKAHEAD = 4.0                                         # seconds the bird looks ahead for the star
LOOK_STEP = 0.2
LOOK_SUBSTEP = 1.0 / 60.0
THINK_GAP = 0.1
SAFE_MARGIN = 52.0

_frames = {}


# ------------------------------------------------------------------ physics
def gravity(x, y):
    """The pull of the star on (x, y): (ax, ay), towards the middle of the screen."""
    dx, dy = CX - x, CY - y
    r = max(MIN_R, math.hypot(dx, dy))
    g = GM / (r * r)
    return g * dx / r, g * dy / r


def circular_speed(r):
    return math.sqrt(GM / max(MIN_R, r))


def fly(obj, dt, turn, push, scale=1.0):
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
            ax += ca * THRUST * scale
            ay += sa * THRUST * scale
        obj.ast_vx += ax * h
        obj.ast_vy += ay * h
        speed = math.hypot(obj.ast_vx, obj.ast_vy)
        if speed > MAX_SPEED:
            obj.ast_vx *= MAX_SPEED / speed
            obj.ast_vy *= MAX_SPEED / speed
        obj.x = (obj.x + obj.ast_vx * h) % BASE_WIDTH
        obj.y = (obj.y + obj.ast_vy * h) % BASE_HEIGHT
        if math.hypot(obj.x - CX, obj.y - CY) < STAR_KILL:
            crashed = True
    return crashed


def periapsis_danger(x, y, vx, vy, horizon=LOOKAHEAD, margin=SAFE_MARGIN):
    """Does the free fall of a ship (no thrust) go inside the safety ring of the star within `horizon` seconds?"""
    t = 0.0
    while t < horizon:
        for _ in range(int(round(LOOK_STEP / LOOK_SUBSTEP))):
            gx, gy = gravity(x, y)
            vx += gx * LOOK_SUBSTEP
            vy += gy * LOOK_SUBSTEP
            x += vx * LOOK_SUBSTEP
            y += vy * LOOK_SUBSTEP
        if math.hypot(x - CX, y - CY) < STAR_KILL + margin:
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
    img = _frames.get("star")
    if img is None:
        try:
            img = pygame.image.load(asset_path("sprites", "spacewar", "jupiter.png")).convert_alpha()
            img = pygame.transform.smoothscale(img, (STAR_DRAW, STAR_DRAW))
        except Exception:
            log_exc("spacewar.star_image")
            img = pygame.Surface((STAR_DRAW, STAR_DRAW), pygame.SRCALPHA)
            pygame.draw.circle(img, (200, 160, 110), (STAR_DRAW // 2, STAR_DRAW // 2), STAR_DRAW // 2 - 4)
        _frames["star"] = img
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
        self.life = TORPEDO_LIFE
        self.age = 0.0

    def update(self, dt):
        # (not pulled by the star: a straight line, round the joined screen)
        self.x = (self.x + self.vx * dt) % BASE_WIDTH
        self.y = (self.y + self.vy * dt) % BASE_HEIGHT
        self.life -= dt
        self.age += dt


class Bird:
    """An opponent: a blue or green bird flying with the physics of the player (and a small pilot)."""

    def __init__(self, kind, x, y, vx, vy, angle, scale, rng):
        self.kind = kind
        self.x, self.y, self.ast_vx, self.ast_vy, self.ast_angle = float(x), float(y), float(vx), float(vy), float(angle)
        self.scale = float(scale)
        self.rng = rng
        self.alive = True
        self.torpedoes = BIRD_TORPEDOES
        self.fire_cd = rng.uniform(*FIRST_FIRE) / self.scale
        self.phase = rng.uniform(0, 4)
        self.push = False
        self.turn = 0.0
        self.think_in = 0.0
        self.danger = False
        self.sense = 1.0 if rng.random() < 0.5 else -1.0      # which way it goes round when it has no side speed
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
                self.x, self.y, self.ast_vx + math.cos(self.ast_angle) * THRUST * self.scale * 0.7,
                self.ast_vy + math.sin(self.ast_angle) * THRUST * self.scale * 0.7, 2.0, SAFE_MARGIN + 25)
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
        t = dist / TORPEDO_SPEED
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
            self.coast = self.rng.uniform(0.3, 0.7)
        self.push = self.coast > 0 and abs(diff) < 1.2 and self.clear_ahead
        return self.turn, self.push, fire

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

    def swarm_remaining(self):
        return self.remaining()

    def all_dead(self):
        """The three levels are won (and a short pause to see the last explosion)."""
        return self.won and self.end_timer >= END_PAUSE

    # --- the levels ---
    def start_level(self, number, player=None):
        """Put the birds of level `number` (1..3) in orbit and the player back at the start, with a full stock."""
        self.level = max(1, min(len(LEVELS), int(number)))
        blue, green = LEVELS[self.level - 1]
        scale = LEVEL_SCALE[self.level - 1] * max(0.5, self.speed_mult)
        kinds = [1] * blue + [2] * green
        self.rng.shuffle(kinds)
        angles = [0.0, math.pi / 2, -math.pi / 2, math.pi / 4][:len(kinds)]
        self.birds = []
        for kind, a in zip(kinds, angles):
            r = self.rng.uniform(235.0, 300.0) if abs(math.sin(a)) < 0.5 else self.rng.uniform(215.0, 255.0)
            x, y = CX + math.cos(a) * r, CY + math.sin(a) * r
            sense = 1.0 if self.rng.random() < 0.5 else -1.0
            v = circular_speed(r) * self.rng.uniform(0.95, 1.05)
            vx, vy = -math.sin(a) * v * sense, math.cos(a) * v * sense
            heading = math.atan2(vy, vx)
            self.birds.append(Bird(kind, x, y, vx, vy, heading, scale, self.rng))
        self.torpedoes = []
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

    def draw(self, surface):
        img = star_image()
        asteroids._add_glow(surface, (255, 190, 120), (CX, CY), STAR_DRAW + 60)
        surface.blit(img, (int(CX - img.get_width() / 2), int(CY - img.get_height() / 2)))
        for b in self.birds:
            if b.alive:
                asteroids._blit_wrapped(surface, b.image(), b.x, b.y)
        for p in self.sparks:
            a = max(0.0, p.life / p.max)
            if p.kind == "fire":
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
                mid = tuple(min(255, (c + 255) // 2) for c in self.tip)
                for length, width, col in ((18, 5, self.tip), (12, 3, mid)):
                    pygame.draw.line(surface, col, (tp.x - ux * length, tp.y - uy * length), (tp.x, tp.y), width)
                asteroids._add_glow(surface, (255, 240, 200), (tp.x, tp.y), 20)
            else:
                asteroids._add_glow(surface, (255, 60, 40), (tp.x, tp.y), 24)
                pygame.draw.circle(surface, (255, 200, 180), (int(tp.x), int(tp.y)), 3)
        if self.level_time < ANNOUNCE and self.started:
            self._say(surface, _label("story_spacewar_level").format(n=self.level, m=len(LEVELS)), (255, 215, 120), 150)
        if self.pause > 0 and self.level < len(LEVELS):
            self._say(surface, _label("story_spacewar_next"), (140, 255, 170), 200)
        if self.exhausted:
            self._say(surface, _label("story_spacewar_empty"), (255, 120, 100), 200)
        if self.level == 1 and self.time < HINT_SECONDS and self.started:
            self._say(surface, _label("story_spacewar_hint"), (170, 200, 255), BASE_HEIGHT - 40)


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
    if p.burn_by_guardian():            # the pixel dust (ship_burn): one life, no dome, no Phenix form that saves
        game.shake_amount = max(game.shake_amount, 22.0)
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


def _fire(form, owner, ship, mult=1.0, error=0.0):
    ca, sa = math.cos(ship.ast_angle + error), math.sin(ship.ast_angle + error)
    form.torpedoes.append(Torpedo(ship.x + ca * 26, ship.y + sa * 26, ship.ast_vx + ca * TORPEDO_SPEED * mult,
                                  ship.ast_vy + sa * TORPEDO_SPEED * mult, owner))


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
        turn, push, fire = b.think(dt, p if player_up else None)
        if fire and sum(1 for tp in form.torpedoes if tp.owner is b) < BIRD_IN_AIR:
            b.fire_cd = BIRD_GAP / b.scale
            b.torpedoes -= 1
            _fire(form, b, b, 1.0, form.rng.uniform(-AIM_ERROR, AIM_ERROR))
            try:
                game.sounds.play("enemy_shoot", x=b.x)
            except Exception:
                log_exc("spacewar.tick")
        if fly(b, dt, turn, push, b.scale):
            _kill_bird(game, form, b)
    # --- torpedoes and dust
    for tp in form.torpedoes:
        tp.update(dt)
    form.torpedoes = [tp for tp in form.torpedoes if tp.life > 0]
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
            if dx * dx + dy * dy < (SHIP_RADIUS + TORPEDO_RADIUS) ** 2:
                form.torpedoes.remove(tp)
                _kill_bird(game, form, b)
                break
        else:
            if player_up and not (tp.owner == "player" and tp.age < SELF_SAFE):
                dx, dy = asteroids.wrapped_delta(tp.x, tp.y, p.x, p.y)
                if dx * dx + dy * dy < (SHIP_RADIUS + TORPEDO_RADIUS) ** 2:
                    form.torpedoes.remove(tp)
                    _kill_player(game, form)
                    player_up = False
    # --- ships against ships (both are lost)
    crew = [b for b in form.birds if b.alive]
    if player_up:
        for b in crew:
            dx, dy = asteroids.wrapped_delta(p.x, p.y, b.x, b.y)
            if dx * dx + dy * dy < (2 * SHIP_RADIUS) ** 2:
                _kill_bird(game, form, b)
                _kill_player(game, form)
                player_up = False
                break
    crew = [b for b in form.birds if b.alive]
    for i, a in enumerate(crew):
        for c in crew[i + 1:]:
            dx, dy = asteroids.wrapped_delta(a.x, a.y, c.x, c.y)
            if a.alive and c.alive and dx * dx + dy * dy < (2 * SHIP_RADIUS) ** 2:
                _kill_bird(game, form, a)
                _kill_bird(game, form, c)
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
    if form.remaining() == 0 and form.level_time > 0.5:
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
