"""The birds and the comets of the Scramble level (src/scramble.py).

THE BIRDS. Every so often (WAVE_GAP) a wave of the game's birds comes in from the right: blue ones (stage 1) or green ones
(stage 2, quicker, and they fire more), the green ones more often as the course goes on. Three shapes of wave:

- "snake": five birds in a line, weaving up and down as they cross the screen;
- "vee": five birds fly in as a V, hold still on the right of the screen a moment, then dive at the ship one after the other;
- "swoop": four birds come in high and low by turns and curve towards the height of the ship, then fly off to the left.

They fly in the air of the screen (their x and y are those of the screen), never into the rock: they keep to the passage. They
fire at the ship now and then (BIRD_SHOT_*), while they are in front of it. A shot of the ship kills a bird: it pays its
points and counts in the Bestiary like any bird of the game (game._enemy_kill_points). Touching a bird or one of its shots
costs a life; the Phenix form burns the birds (and pays them), the dome of the Shield takes their shots and kills the birds
it meets. No wave in the comets section, nor once the scroll brakes (the base is there).

THE COMETS. In the comets section (the stretch with almost no rock, as in the original) comets streak across the screen from
right to left, slanting a little, one every COMET_GAP seconds. They are the comets of the game's sky (assets/sprites/comet),
smaller. Nothing destroys them: a shot dies on their head. Touching one costs a life (the Phenix form and the dome go through,
the dome breaks it).
"""
import math

import scramble as sc

W, H = sc.W, sc.H
WAVE_GAP = (6.5, 10.0)            # seconds between two waves of birds
FIRST_WAVE = sc.STATION_FIRST     # no bird before this (world px)
GREEN_SHARE = (0.25, 0.65)        # the chance of a green wave at the start of the course and at its end
BIRD_SPEED = {1: 1.0, 2: 1.2}     # how fast each kind flies (a share of the speeds below)
SNAKE_SPEED = 230.0               # px/s, to the left, on the screen
SNAKE_WAVE = (70.0, 2.6)          # the weaving of a snake: its height (px) and how fast (rad/s)
SNAKE_STEP = 0.32                 # seconds between two birds of a snake
VEE_IN = 340.0                    # px/s: a V flies in ...
VEE_HOLD = (W * 0.70, 1.3)        # ... to this x, and holds there this long
VEE_GAP = 0.45                    # seconds between two dives
DIVE_SPEED = 380.0
DIVE_TURN = 2.4                   # rad/s: how fast a diving bird turns towards the ship
SWOOP_SPEED = 300.0
SWOOP_PULL = 1.8                  # how hard a swooping bird is drawn to the height of the ship (1/s)
SWOOP_STEP = 0.55
BIRD_RADIUS = 16.0                # what a shot of the ship must touch
BIRD_REACH = 20.0                 # ... and the ship (on top of the half of its box)
BIRD_MARGIN = 26.0                # a bird keeps this far from the rock
BIRD_SHOT_SPEED = 330.0
BIRD_SHOT_GAP = {1: (2.8, 4.6), 2: (1.4, 2.6)}       # seconds between two shots of a bird
BIRD_SHOT_MAX = 6                 # their shots on the screen
BIRD_SHOT_RADIUS = 6.0
COMET_GAP = (0.375, 0.675)        # seconds between two comets (twice as many on the screen as at first)
COMET_SPEED = (430.0, 620.0)      # px/s, to the left
COMET_SLANT = 0.47                # dy/dx of a comet (the slant of the picture)
COMET_RADIUS = 15.0               # its head
COMET_SCALE = 0.55                # the comets of the sky, at this size
COMET_HEAD = (350.0, 185.0)       # where the head is in the picture of the sky (480 x 270), going down to the right


class Bird:
    """One bird of a wave, in the coordinates of the screen."""

    def __init__(self, stage, pattern, x, y, delay=0.0):
        self.stage = int(stage)                    # 1 = blue, 2 = green (game._enemy_kill_points reads it)
        self.pattern = pattern
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = 0.0, 0.0
        self.t = -float(delay)                     # (it starts when t reaches 0)
        self.alive = True
        self.phase = 0.0
        self.base_y = float(y)
        self.state = "in"
        self.dive_at = 0.0
        self.shot_in = 1.0
        self.flap = 0.0

    @property
    def waiting(self):
        return self.t < 0


class BirdShot:
    def __init__(self, x, y, vx, vy):
        self.x, self.y, self.vx, self.vy = float(x), float(y), float(vx), float(vy)
        self.alive = True


class Comet:
    """A comet of the comets section, on the screen; `down`: it slants down as it goes left (else up)."""

    def __init__(self, x, y, speed, down):
        self.x, self.y = float(x), float(y)
        self.vx = -float(speed)
        self.vy = float(speed) * COMET_SLANT * (1 if down else -1)
        self.down = bool(down)
        self.alive = True
        self.age = 0.0


class Sky:
    """The birds and the comets of a course (made by ScrambleFormation)."""

    def __init__(self, form):
        self.form = form
        self.birds = []
        self.shots = []
        self.comets = []
        self.wave_in = form.rng.uniform(*WAVE_GAP) * 0.5
        self.comet_in = 0.0
        self.waves = 0

    # --- the waves
    def section(self):
        f = self.form
        return f.course.section_at(f.cam + W)

    def can_send_wave(self):
        f = self.form
        return (f.cam + W >= FIRST_WAVE and f.cam < f.course.brake_from - W * 0.5 and self.section() != "comets"
                and f.course.section_at(f.cam) != "comets")

    def send_wave(self, pattern=None, stage=None):
        """A new wave comes in from the right."""
        f = self.form
        rng = f.rng
        k = f.progress()
        if stage is None:
            green = GREEN_SHARE[0] + (GREEN_SHARE[1] - GREEN_SHARE[0]) * k
            stage = 2 if rng.random() < green else 1
        pattern = pattern or rng.choice(("snake", "vee", "swoop"))
        mid, gap = f.course.passage(f.cam + W * 0.8)
        top, bottom = mid - gap / 2 + BIRD_MARGIN + 20, mid + gap / 2 - BIRD_MARGIN - 20
        if pattern == "snake":
            y = rng.uniform(top + SNAKE_WAVE[0] * 0.5, max(top + SNAKE_WAVE[0] * 0.5, bottom - SNAKE_WAVE[0] * 0.5))
            phase = rng.uniform(0, 2 * math.pi)
            for i in range(5):
                b = Bird(stage, "snake", W + 40, y, delay=i * SNAKE_STEP)
                b.phase = phase
                self.birds.append(b)
        elif pattern == "vee":
            y = (top + bottom) / 2
            for i, (dx, dy) in enumerate(((0, 0), (46, -40), (46, 40), (92, -80), (92, 80))):
                b = Bird(stage, "vee", W + 40 + dx, y + dy * min(1.0, (bottom - top) / 200.0))
                b.base_y = b.y
                b.hold_x = VEE_HOLD[0] + dx
                b.dive_at = VEE_HOLD[1] + i * VEE_GAP
                self.birds.append(b)
        else:
            for i in range(4):
                high = i % 2 == 0
                b = Bird(stage, "swoop", W + 40, top if high else bottom, delay=i * SWOOP_STEP)
                self.birds.append(b)
        for b in self.birds[-5:]:
            if b.stage == stage:
                b.shot_in = rng.uniform(*BIRD_SHOT_GAP[stage]) * 0.6
        self.waves += 1
        return pattern

    # --- every frame
    def tick(self, game, dt, ship_alive):
        f = self.form
        p = game.player
        # the waves
        if self.can_send_wave():
            self.wave_in -= dt
            if self.wave_in <= 0 and not self.birds:
                self.send_wave()
                self.wave_in = f.rng.uniform(*WAVE_GAP)
            elif self.wave_in <= 0:
                self.wave_in = 0.5                      # (the last wave is still there: a little later)
        for b in self.birds:
            self._fly(b, dt, p, ship_alive)
            if ship_alive and b.alive and not b.waiting:
                self._fire(game, b, dt, p)
        self.birds = [b for b in self.birds if b.alive]
        # their shots
        for s in self.shots:
            s.x += s.vx * dt
            s.y += s.vy * dt
            wx = f.cam + s.x
            if s.x < -20 or s.x > W + 20 or s.y < -20 or s.y > H + 20:
                s.alive = False
            elif s.y <= f.course.ceiling(wx) or s.y >= f.course.ground(wx):
                s.alive = False
        self.shots = [s for s in self.shots if s.alive]
        # the comets
        if self.comets_due():
            self.comet_in -= dt
            if self.comet_in <= 0:
                self._comet()
                self.comet_in = f.rng.uniform(*COMET_GAP)
        for c in self.comets:
            c.age += dt
            c.x += c.vx * dt
            c.y += c.vy * dt
            wx = f.cam + c.x
            if c.x < -60 or c.y < -60 or c.y > H + 60:
                c.alive = False
            elif c.y <= f.course.ceiling(wx) or c.y >= f.course.ground(wx):
                c.alive = False
                sc._blast(game, f, wx, c.y, small=True)
        self.comets = [c for c in self.comets if c.alive]

    def comets_due(self):
        """True while comets come in: the right edge of the screen is in the comets section (past its first stretch)."""
        f = self.form
        k = sc.SECTION_KEYS.index("comets")
        x = f.cam + W
        return f.course.starts[k] + 300.0 < x < f.course.starts[k + 1]

    def _comet(self):
        f = self.form
        down = f.rng.random() < 0.5
        speed = f.rng.uniform(*COMET_SPEED)
        mid, gap = f.course.passage(f.cam + W)
        top, bottom = mid - gap / 2 + 20, mid + gap / 2 - 20
        # it starts so that it crosses the left half of the screen inside the passage
        span = W * 0.6 * COMET_SLANT
        y = f.rng.uniform(top, max(top, bottom - span)) if down else f.rng.uniform(min(bottom, top + span), bottom)
        self.comets.append(Comet(W + 30, y, speed, down))
        sc._play(getattr(f, "sounds", None), "scramble_comet", volume=0.35, x=W * 0.8)

    def _keep_in(self, b):
        """A bird never goes into the rock."""
        f = self.form
        wx = f.cam + b.x
        top = f.course.ceiling(wx) + BIRD_MARGIN
        bottom = f.course.ground(wx) - BIRD_MARGIN
        if top > bottom:
            b.y = (top + bottom) / 2
        else:
            b.y = min(bottom, max(top, b.y))

    def _fly(self, b, dt, p, ship_alive):
        b.t += dt
        if b.waiting:
            return
        b.flap += dt
        sp = BIRD_SPEED.get(b.stage, 1.0)
        if b.pattern == "snake":
            b.x -= SNAKE_SPEED * sp * dt
            amp, rate = SNAKE_WAVE
            b.y = b.base_y + amp * math.sin(b.phase + rate * b.t)
        elif b.pattern == "vee":
            if b.state == "in":
                b.x = max(b.hold_x, b.x - VEE_IN * sp * dt)
                b.y = b.base_y + 6 * math.sin(b.t * 3.0 + b.hold_x * 0.05)
                if b.t >= b.dive_at:
                    b.state = "dive"
                    b.vx, b.vy = -DIVE_SPEED * sp, 0.0
            else:
                if ship_alive and b.x > p.x + 40:
                    want = math.atan2(p.y - b.y, p.x - b.x)
                    have = math.atan2(b.vy, b.vx)
                    turn = (want - have + math.pi) % (2 * math.pi) - math.pi
                    have += max(-DIVE_TURN * dt, min(DIVE_TURN * dt, turn))
                    speed = DIVE_SPEED * sp
                    b.vx, b.vy = math.cos(have) * speed, math.sin(have) * speed
                    if b.vx > -60:                         # (never back to the right)
                        b.vx = -60
                b.x += b.vx * dt
                b.y += b.vy * dt
        else:                                              # swoop
            b.x -= SWOOP_SPEED * sp * dt
            if ship_alive and b.x > p.x:
                b.vy += (p.y - b.y) * SWOOP_PULL * dt * 2.0 - b.vy * 1.6 * dt
            b.y += b.vy * dt
        self._keep_in(b)
        if b.x < -60:
            b.alive = False

    def _fire(self, game, b, dt, p):
        b.shot_in -= dt
        if b.shot_in > 0 or not (p.x + 150 < b.x < W - 30) or len(self.shots) >= BIRD_SHOT_MAX:
            return
        b.shot_in = self.form.rng.uniform(*BIRD_SHOT_GAP[b.stage])
        dx, dy = p.x - b.x, p.y - b.y
        d = math.hypot(dx, dy) or 1.0
        self.shots.append(BirdShot(b.x - 12, b.y, dx / d * BIRD_SHOT_SPEED, dy / d * BIRD_SHOT_SPEED))
        sc._play(getattr(game, "sounds", None), "enemy_shoot", volume=0.45, x=b.x)

    # --- the shots of the ship, the ship
    def shot_target(self, x0, x1, y, cam):
        """The bird or the comet a shot of the ship meets going from x0 to x1 (world x, at the height y), the nearest first:
        (thing, its world x), or None."""
        best = None
        for b in self.birds:
            if b.alive and not b.waiting and abs(b.y - y) <= BIRD_RADIUS:
                bx = cam + b.x
                if x0 - BIRD_RADIUS <= bx <= x1 + BIRD_RADIUS and (best is None or bx < best[1]):
                    best = (b, bx)
        for c in self.comets:
            if abs(c.y - y) <= COMET_RADIUS:
                cx = cam + c.x
                if x0 - COMET_RADIUS <= cx <= x1 + COMET_RADIUS and (best is None or cx < best[1]):
                    best = (c, cx)
        return best

    def kill_bird(self, game, b):
        """A bird is destroyed: its points (and the Bestiary), its explosion."""
        if not b.alive:
            return
        b.alive = False
        sc.charge(game.player)
        game._add_score(game.player, game._enemy_kill_points(b))
        self.form.kills["bird%d" % b.stage] = self.form.kills.get("bird%d" % b.stage, 0) + 1
        try:
            game.explosions.append(game._boom(b.x, b.y, kind="enemy"))
        except Exception:
            sc.log_exc("scramble_birds.kill_bird")
        sc._play(getattr(game, "sounds", None), "enemy_explosion", volume=0.6, x=b.x)

    def touch_ship(self, game, p):
        """The birds, their shots and the comets against the ship."""
        f = self.form
        fire_bird = bool(p.is_phenix) and not getattr(p, "uses_shield", False)
        dome = bool(p.is_phenix) and getattr(p, "uses_shield", False)
        hx, hy = sc.SHIP_BOX
        for b in self.birds:
            if b.alive and not b.waiting and abs(b.x - p.x) < hx + BIRD_REACH * 0.6 and abs(b.y - p.y) < hy + BIRD_REACH * 0.6:
                if fire_bird or dome:
                    self.kill_bird(game, b)
                    continue
                self.kill_bird(game, b)
                sc._ship_hit(game, f)
                return
        for s in self.shots:
            if s.alive and abs(s.x - p.x) < hx + BIRD_SHOT_RADIUS and abs(s.y - p.y) < hy * 0.8 + BIRD_SHOT_RADIUS:
                s.alive = False
                if dome:
                    game._shield_absorb(p, s.x, s.y)
                    continue
                if fire_bird:
                    continue
                sc._ship_hit(game, f)
                break
        self.shots = [s for s in self.shots if s.alive]
        for c in self.comets:
            if c.alive and abs(c.x - p.x) < hx + COMET_RADIUS and abs(c.y - p.y) < hy + COMET_RADIUS * 0.6:
                if dome:
                    c.alive = False
                    sc._blast(game, f, f.cam + c.x, c.y, small=True)
                    continue
                if fire_bird:
                    continue
                c.alive = False
                sc._ship_hit(game, f)
                break
        self.comets = [c for c in self.comets if c.alive]
