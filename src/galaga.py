"""
The BONUS mission of the Adventure ("the two-dimensional impulse reactor"): waves of birds that come in like in
Namco's Galaga.

The birds come in chains that follow a curved path (they fly in, make loops over the screen, bomb the ship) and
leave. The ones that are still alive when their chain leaves join the next wave, which is thus bigger and deadlier;
the fourth and last wave comes back until every bird is destroyed (or the ship is).

GalagaFormation has the same face as EnemyFormation (enemies, bullets, update, draw, all_dead...), so the rest of
the game (shots, collisions, score, stage clear) does not know the difference. Its choices (which figure, which bird
is blue or khaki, when a bird shoots) come from its own random generator; the mission is Adventure only, so the
global `random` stream of the arcade game (and its golden replay) is never involved.
"""
import bisect
import math
import random

import pygame

from settings import BASE_WIDTH, BASE_HEIGHT
from enemy import Enemy, EnemyBullet

WAVES = 4                                  # the waves of the mission
FRESH = (11, 11, 14, 14)                     # new birds of each wave (the survivors of the one before come on top)
CHAIN_MAX = 8                              # birds in one chain; more than that makes another chain
CHAIN_GAP = 58.0                           # distance between two birds of a chain, along the path (pixels)
BASE_SPEED = 330.0                         # pixels per second along the path, before the level speed
WAVE_SPEEDUP = 0.07                        # every wave goes a little faster
START_DELAY = 1.6                          # seconds before the first wave comes in
WAVE_PAUSE = 1.1                           # seconds of calm between the end of a wave and the next
CHAIN_STAGGER = 1.7                        # a wave with more than two chains sends them one pair after the other
FIRE_MEAN = (4.0, 3.5, 3.0, 2.6)           # seconds between two shots of one bird, by wave (they shoot a lot)
FIRE_NEAR = 150                            # a bird above the ship (this close in x) shoots faster
FIRE_NEAR_BOOST = 1.8
MAX_BULLETS = 44
SOUND_GAP = 0.07                           # seconds between two shot sounds (a wave would saturate the mixer)
BANK_MAX = 70.0                            # degrees the bird leans into its turns


# ---------------------------------------------------------------- paths
def _spline(points, per=16):
    """Smooth curve through the points (Catmull-Rom), as a list of (x, y)."""
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for k in range(per):
            u = k / per
            u2, u3 = u * u, u * u * u
            out.append((
                0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * u + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * u2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * u3),
                0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * u + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * u2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * u3),
            ))
    out.append(points[-1])
    return out


def _loop(cx, cy, r, start_deg, turns=1.0, clockwise=True, step=30):
    """Points of a circle (screen coordinates: y points down, so a growing angle turns clockwise)."""
    n = max(2, int(abs(turns) * 360 / step))
    sign = 1.0 if clockwise else -1.0
    pts = []
    for i in range(1, n + 1):
        a = math.radians(start_deg + sign * i * (360.0 * abs(turns) / n))
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _at_angle(cx, cy, r, deg):
    a = math.radians(deg)
    return (cx + r * math.cos(a), cy + r * math.sin(a))


class Path:
    """A curve sampled in short segments, read by distance travelled (`at`)."""

    def __init__(self, pts):
        self.pts = list(pts)
        self.cum = [0.0]
        for (x0, y0), (x1, y1) in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + math.hypot(x1 - x0, y1 - y0))
        self.length = self.cum[-1]

    def mirrored(self):
        return Path([(BASE_WIDTH - x, y) for x, y in self.pts])

    def at(self, s):
        """(x, y, heading in radians) after travelling `s` pixels. Before the start the path goes on in a straight
        line backwards, so that a bird that has not come in yet waits out of the screen."""
        pts = self.pts
        if s <= 0.0:
            (x0, y0), (x1, y1) = pts[0], pts[1]
            h = math.atan2(y1 - y0, x1 - x0)
            return x0 + math.cos(h) * s, y0 + math.sin(h) * s, h
        if s >= self.length:
            (x0, y0), (x1, y1) = pts[-2], pts[-1]
            h = math.atan2(y1 - y0, x1 - x0)
            over = s - self.length
            return x1 + math.cos(h) * over, y1 + math.sin(h) * over, h
        i = bisect.bisect_right(self.cum, s) - 1
        i = max(0, min(len(pts) - 2, i))
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        seg = max(1e-6, self.cum[i + 1] - self.cum[i])
        u = (s - self.cum[i]) / seg
        return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, math.atan2(y1 - y0, x1 - x0)


def _tangent(deg, clockwise):
    """Unit direction of travel on a circle at angle `deg` (screen coordinates)."""
    a = math.radians(deg)
    return (-math.sin(a), math.cos(a)) if clockwise else (math.sin(a), -math.cos(a))


def _circuit(cx, cy, r, deg, clockwise, lead=95.0):
    """A full turn of a circle, entered and left along its tangent, so that the curve has no kink there:
    (point before, the turn, point after)."""
    tx, ty = _tangent(deg, clockwise)
    px, py = _at_angle(cx, cy, r, deg)
    before = (px - tx * lead, py - ty * lead)
    turn = [(px, py)] + _loop(cx, cy, r, deg, turns=1.0, clockwise=clockwise)
    after = (px + tx * lead, py + ty * lead)
    return before, turn, after


def _build_swoop():
    """Comes in from the upper left, loops over the middle of the screen, sweeps low and leaves by the top right."""
    before, turn, after = _circuit(640.0, 320.0, 105.0, 300.0, True)
    entry = [(-90.0, 70.0), (200.0, 110.0), (430.0, 150.0)]
    leave = [(900.0, 400.0), (1040.0, 350.0), (1120.0, 200.0), (1200.0, 40.0), (1300.0, -90.0)]
    return _spline(entry + [before] + turn + [after] + leave)


def _build_wave():
    """A long wave over the whole screen: low sweeps over the ship, then up and out."""
    pts = [(-90.0, 250.0), (160.0, 360.0), (380.0, 430.0), (560.0, 330.0), (700.0, 200.0), (840.0, 330.0),
           (1000.0, 440.0), (1180.0, 380.0), (1240.0, 200.0), (1330.0, -90.0)]
    return _spline(pts)


def _build_double_loop():
    """Dives from the top on the left, makes a big loop low on the left, then a small one on the right."""
    b1, t1, a1 = _circuit(330.0, 330.0, 120.0, 180.0, False, lead=60.0)
    b2, t2, a2 = _circuit(860.0, 250.0, 85.0, 225.0, True)
    entry = [(200.0, -90.0), (205.0, 110.0)]
    bridge = [(300.0, 445.0), (430.0, 445.0), (545.0, 390.0), (650.0, 320.0)]
    leave = [(1000.0, 80.0), (1300.0, -90.0)]
    return _spline(entry + [b1] + t1 + [a1] + bridge + [b2] + t2 + [a2] + leave)


_BUILDERS = (_build_swoop, _build_wave, _build_double_loop)
VARIANTS = len(_BUILDERS)
_CACHE = {}


def path_for(variant, side):
    """The path of a variant: side +1 comes in from the left, side -1 is its mirror image."""
    key = (variant % VARIANTS, 1 if side >= 0 else -1)
    if key not in _CACHE:
        base = Path(_BUILDERS[key[0]]())
        _CACHE[key] = base if key[1] > 0 else base.mirrored()
    return _CACHE[key]


# ---------------------------------------------------------------- the birds
_ROTATED = {}


def _rotated(kind, frame_i, frame, bucket):
    key = (kind, frame_i, bucket)
    img = _ROTATED.get(key)
    if img is None:
        img = pygame.transform.rotate(frame, bucket * 5.0) if bucket else frame
        _ROTATED[key] = img
    return img


class GalagaBird(Enemy):
    """A blue (1) or khaki (2) bird that flies along its chain's path. It rams like a diving bird (state "diving")."""

    def __init__(self, kind, index=0):
        super().__init__(-200.0, -200.0, formation_index=index, stage=kind)
        self.state = "diving"
        self.kind = kind
        self.heading = math.pi / 2
        self.bank = 0.0
        self.fire_t = 1.0
        self.frame_i = 0

    def place(self, x, y, heading):
        self.x, self.y = float(x), float(y)
        self.heading = heading
        # lean into the turn: 0 when the bird flies down, up to BANK_MAX to either side
        dev = math.degrees(heading - math.pi / 2)
        dev = (dev + 180.0) % 360.0 - 180.0
        self.bank = max(-BANK_MAX, min(BANK_MAX, dev * 0.6))
        self.rect.center = (int(self.x), int(self.y))

    def update(self, dt, formation_offset_x=0.0, player_x=0.0):
        if not self.alive:
            return
        if self.dying:
            return super().update(dt)                    # the death animation of the ordinary bird
        self.time += dt
        self.anim_t += dt
        self.shoot_cooldown = max(0.0, self.shoot_cooldown - dt)
        if self.frames and len(self.frames) >= 2:
            t = self.anim_t + self.anim_phase
            flap = int(t * self.flap_rate) % 2
            glow = (t % self.glow_period) < self.glow_len
            self.frame_i = flap + (2 if glow and len(self.frames) >= 4 else 0)
            self.image = self.frames[self.frame_i]

    def draw(self, surface):
        if not self.alive:
            return
        if self.dying:
            return super().draw(surface)
        bucket = int(round(self.bank / 5.0))
        img = _rotated(self.kind, self.frame_i, self.image, bucket)
        surface.blit(img, (int(self.x - img.get_width() // 2), int(self.y - img.get_height() // 2)))


class _Chain:
    """Birds one behind the other on one path."""

    def __init__(self, birds, path, delay):
        self.birds = list(birds)
        self.path = path
        self.delay = float(delay)
        self.run = 0.0                                   # distance the head has travelled

    def done(self):
        """Every bird has left through the end of the path (the dead do not count)."""
        tail = self.run - (len(self.birds) - 1) * CHAIN_GAP
        return self.delay <= 0.0 and tail >= self.path.length + 60.0


class GalagaFormation:
    """Four waves of birds that come in in chains, loop, bomb and leave; the survivors come back in the next wave."""

    def __init__(self, speed_mult=1.0, rng=None, fresh=FRESH, fire_mult=1.0):
        self.enemies = []
        self.bullets = []
        self.offset_x = 0.0
        self.direction = 1
        self.speed = 0.0
        self.time = 0.0
        self.stage = 1
        self.speed_mult = float(speed_mult)
        self.fire_mult = max(0.1, float(fire_mult))      # 1.5: the birds shoot one and a half times as often
        self.max_bullets = max(1, round(MAX_BULLETS * self.fire_mult))
        self.sounds = None
        self.swarm = None
        self.rng = rng if rng is not None else random.Random()
        self.fresh = tuple(fresh)
        self.wave = 0                                    # waves that have come in (the last one comes back)
        self.chains = []
        self.carry = []                                  # alive birds out of the screen, waiting for the next wave
        self.pause = START_DELAY
        self._sound_t = 0.0
        self._variant = self.rng.randrange(VARIANTS)

    # --- bookkeeping ---
    @property
    def waves(self):
        return len(self.fresh)

    def pending_fresh(self):
        """New birds that have not come in yet."""
        return sum(self.fresh[self.wave:])

    def remaining(self):
        """Birds still to be destroyed to win."""
        alive = sum(1 for e in self.enemies if e.alive and not e.dying)
        return alive + len(self.carry) + self.pending_fresh()

    def get_alive_enemies(self):
        return [e for e in self.enemies if e.alive]

    def get_hittable_enemies(self):
        return [e for e in self.enemies if e.alive and not e.dying]

    def all_dead(self):
        if self.pending_fresh() > 0 or self.carry:
            return False
        return not any(e.alive for e in self.enemies)

    # --- waves ---
    def _launch(self):
        """The next wave comes in: the survivors of the one before, and the new birds."""
        idx = min(self.wave, self.waves - 1)
        fresh = self.fresh[self.wave] if self.wave < self.waves else 0
        squad = list(self.carry)
        self.carry = []
        kinds = [1, 2] * ((fresh + 1) // 2)
        self.rng.shuffle(kinds)                          # blue and khaki mixed
        for i in range(fresh):
            squad.append(GalagaBird(kinds[i], index=len(self.enemies) + i))
        self.rng.shuffle(squad)
        if self.wave < self.waves:
            self.wave += 1
        n_chains = max(1, -(-len(squad) // CHAIN_MAX))
        per = -(-len(squad) // n_chains)
        speed = BASE_SPEED * self.speed_mult * (1.0 + WAVE_SPEEDUP * idx)
        self._speed = speed
        self._fire_mean = FIRE_MEAN[min(idx, len(FIRE_MEAN) - 1)] / self.fire_mult
        for j in range(n_chains):
            birds = squad[j * per:(j + 1) * per]
            side = 1 if j % 2 == 0 else -1
            variant = self._variant + (j // 2)
            chain = _Chain(birds, path_for(variant, side), delay=(j // 2) * CHAIN_STAGGER)
            for b in birds:
                b.fire_t = self.rng.uniform(0.4, 1.0) * self._fire_mean
                b.place(-300.0, -300.0, math.pi / 2)
                if b not in self.enemies:
                    self.enemies.append(b)
            self.chains.append(chain)
        self._variant += 1 + (n_chains + 1) // 2         # the next wave flies another figure

    def _move_chain(self, chain, dt):
        if chain.delay > 0.0:
            chain.delay -= dt
            if chain.delay > 0.0:
                return
            chain.delay = 0.0
        chain.run += self._speed * dt
        for i, b in enumerate(chain.birds):
            if not b.alive or b.dying:
                continue
            x, y, h = chain.path.at(chain.run - i * CHAIN_GAP)
            b.place(x, y, h)

    def _fire(self, b, dt, player_x):
        on_screen = 24 < b.x < BASE_WIDTH - 24 and 20 < b.y < BASE_HEIGHT - 150
        if not on_screen:
            return
        step = dt * (FIRE_NEAR_BOOST if abs(b.x - player_x) < FIRE_NEAR else 1.0)
        b.fire_t -= step
        if b.fire_t > 0.0 or len(self.bullets) >= self.max_bullets:
            return
        b.fire_t = self.rng.uniform(0.6, 1.4) * self._fire_mean
        bullet = EnemyBullet(b.x, b.y + 16, stage=b.kind)
        bullet.owner_id = id(b)
        self.bullets.append(bullet)
        if self.sounds and self._sound_t <= 0.0:
            self._sound_t = SOUND_GAP
            self.sounds.play("enemy_shoot", x=b.x)

    def update(self, dt, player_x):
        self.time += dt
        self._sound_t = max(0.0, self._sound_t - dt)
        for chain in self.chains:
            self._move_chain(chain, dt)
        for b in self.enemies:
            b.update(dt)
            if b.alive and not b.dying and b.state == "diving":
                self._fire(b, dt, player_x)
        # a chain that has left: the birds still alive wait for the next wave
        for chain in [c for c in self.chains if c.done()]:
            self.chains.remove(chain)
            for b in chain.birds:
                if b.alive and not b.dying:
                    self.carry.append(b)
                    if b in self.enemies:
                        self.enemies.remove(b)
        if not self.chains and (self.carry or self.pending_fresh() > 0):
            self.pause -= dt
            if self.pause <= 0.0:
                self.pause = WAVE_PAUSE
                self._launch()
        for bullet in self.bullets[:]:
            bullet.update(dt)
            if not bullet.alive:
                self.bullets.remove(bullet)
        if any((not e.alive and not e.dying) for e in self.enemies):
            self.enemies = [e for e in self.enemies if e.alive or e.dying]

    def draw(self, surface):
        for b in self.enemies:
            if b.alive or b.dying:
                b.draw(surface)
        for bullet in self.bullets:
            if bullet.alive:
                bullet.draw(surface)
