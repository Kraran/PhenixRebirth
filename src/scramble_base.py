"""The enemy base at the end of the Scramble level (src/scramble.py).

When the scroll has braked to a stop, the arena fills the screen: thin bands of rock, and on the right the base. It stands
in the world (it slides in with the rock during the braking):

Until the scroll has stopped its shields are up: a shot sparks off it.

- THE WALL: COLUMNS columns of metal bricks from the ceiling to the ground, in the look of the hull of the boss saucer (pieces
  of its photograph, bevelled and riveted). A shot of the ship breaks the first brick it meets (1 point): the wall is cut
  down brick by brick.
- THE TURRETS: TURRETS missile launchers on the face of the wall. Each one fires now and then a missile to the left that homes
  in a little on the height of the ship (like the missiles of the stations, sideways). A shot destroys a missile (10 points)
  or a turret (the points of a station: a green bird).
- THE BOSS: the alien of the boss saucer, red here, behind the wall in its chamber; it rises and sinks slowly. It fires as
  it does in the saucer: up to BULLET_MAX shots on the screen, one every BULLET_GAP seconds, each from the face of the wall
  (the first brick of a row near the height of the ship), straight on, to the left. Only a shot through a hole in the wall
  reaches it: one hit kills it (the points of the boss of a saucer) and the base blows up, brick after brick. A moment later
  the mission is won.

What touches the ship (a shot, a missile) costs a life; the dome of the Shield takes them, the Phenix form passes through. The
ship cannot reach the wall (it stays in the left part of the screen).
"""
import math

import scramble as sc

W, H = sc.W, sc.H
BRICK_W, BRICK_H = 26, 20
COLUMNS = 4
WALL_FROM_RIGHT = 340             # px from the right edge of the screen (when the scroll has stopped) to the face of the wall
CHAMBER = 110                     # px from the back of the wall to the middle of the boss
BACK_FROM = 0                     # px from the back of the wall to the plates behind the boss (they close the chamber)
TURRET_ROWS = (5, 12, 19, 26)     # the rows of the wall the turrets stand on
TURRETS = len(TURRET_ROWS)
TURRET_W, TURRET_H = 30, 26
TURRET_GAP = (3.4, 5.4)           # seconds between two missiles of a turret
TURRET_FIRST = (1.0, 3.0)         # ... the first one, once the scroll has stopped
TURRET_MISSILES = 3               # the missiles of the turrets on the screen at once
MISSILE_SPEED = (90.0, 430.0)     # px/s, to the left
MISSILE_ACCEL = 520.0
MISSILE_HOMING = (1.2, 60.0, 160.0)          # it homes in on the height of the ship: for (s), at most (px/s), reached at (px/s^2)
BULLET_GAP = (0.35, 0.75)         # the boss fires as in the saucer ...
BULLET_MAX = 5
BULLET_SPEED = 280.0
BULLET_NEAR = 4                   # ... from one of the rows this close to the height of the ship
BULLET_START = 1.6                # seconds after the scroll has stopped
BOSS_SIZE = 140                   # px (the picture of the saucer's alien, scaled)
BOSS_SWING = (190.0, 7.0)         # how far it rises and sinks (px) and in how long (s)
BOSS_HIT = 0.8                    # the share of its picture a shot must touch
BLOW_TIME = 1.8                   # seconds over which the bricks blow up once the boss is dead
DONE_AFTER = 3.2                  # seconds from the death of the boss to the end of the mission
MISSILE_R = (16.0, 6.0)           # half the size of a missile (along, across)


class Brick:
    def __init__(self, col, row, x, y, tile):
        self.col, self.row = col, row
        self.x, self.y = float(x), float(y)       # its middle, in the world
        self.alive = True
        self.tile = tile                          # which picture (scramble_view)
        self.blow_at = None                       # (when the base blows up: when this one goes)

    def box(self):
        return self.x - BRICK_W / 2, self.y - BRICK_H / 2, self.x + BRICK_W / 2, self.y + BRICK_H / 2


class Turret:
    def __init__(self, row, x, y, first):
        self.row = row
        self.x, self.y = float(x), float(y)
        self.alive = True
        self.fire_in = first

    def box(self):
        return self.x - TURRET_W / 2, self.y - TURRET_H / 2, self.x + TURRET_W / 2, self.y + TURRET_H / 2


class BaseMissile:
    """A missile of a turret: it flies to the left and homes in a little on the height of the ship."""

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.speed = MISSILE_SPEED[0]
        self.vy = 0.0
        self.age = 0.0
        self.alive = True

    def box(self):
        return self.x - MISSILE_R[0], self.y - MISSILE_R[1], self.x + MISSILE_R[0], self.y + MISSILE_R[1]

    def tilt(self):
        return math.atan2(self.vy, self.speed)


class BaseBullet:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.alive = True


class Boss:
    """The alien behind the wall (its middle in the world)."""

    def __init__(self, x, y):
        self.x, self.y0 = float(x), float(y)
        self.y = float(y)
        self.t = 0.0
        self.alive = True
        self.dying = False
        self.death = 0.0
        self.hit_flash = 0.0

    def box(self):
        half = BOSS_SIZE * BOSS_HIT / 2
        return self.x - half, self.y - half, self.x + half, self.y + half


class Base:
    """The base of a course: its wall, its turrets, its boss, their shots."""

    def __init__(self, form):
        self.form = form
        course = form.course
        rng = form.rng
        self.top = sc.ARENA_BAND[0]
        self.bottom = H - sc.ARENA_BAND[1]
        self.rows = int((self.bottom - self.top) // BRICK_H)
        self.y0 = self.top + ((self.bottom - self.top) - self.rows * BRICK_H) / 2.0
        self.face = course.stop + W - WALL_FROM_RIGHT           # the world x of the face of the wall
        self.back = self.face + COLUMNS * BRICK_W
        self.bricks = []
        for row in range(self.rows):
            for col in range(COLUMNS):
                x = self.face + (col + 0.5) * BRICK_W
                y = self.y0 + (row + 0.5) * BRICK_H
                self.bricks.append(Brick(col, row, x, y, rng.randrange(16)))
        self.turrets = [Turret(r, self.face - TURRET_W / 2 + 4, self.y0 + (r + 0.5) * BRICK_H,
                               rng.uniform(*TURRET_FIRST)) for r in TURRET_ROWS if r < self.rows]
        self.boss = Boss(self.back + CHAMBER, (self.top + self.bottom) / 2.0)
        self.panel_x = self.back + BACK_FROM
        self.missiles = []
        self.bullets = []
        self.started = False
        self.fight = 0.0                            # seconds since the scroll stopped
        self.bullet_in = BULLET_START
        self.dead_for = None                        # seconds since the boss died (None: alive)
        self.done = False
        self.kills = {"brick": 0, "turret": 0, "missile": 0, "boss": 0}

    # --- asking it
    def row_of(self, y):
        r = int((y - self.y0) // BRICK_H)
        return r if 0 <= r < self.rows else None

    def front_brick(self, row):
        """The first standing brick of a row (the nearest to the ship), or None."""
        best = None
        for b in self.bricks:
            if b.row == row and b.alive and (best is None or b.col < best.col):
                best = b
        return best

    def standing(self):
        return sum(1 for b in self.bricks if b.alive)

    # --- every frame
    def tick(self, game, dt, ship_alive):
        f = self.form
        p = game.player
        boss = self.boss
        boss.t += dt
        boss.hit_flash = max(0.0, boss.hit_flash - dt)
        if boss.alive and not boss.dying:
            amp, period = BOSS_SWING
            boss.y = boss.y0 + amp * math.sin(2 * math.pi * boss.t / period)
        if self.dead_for is not None:
            self._blow_up(game, dt)
            return
        if not self.started:
            return
        self.fight += dt
        # the turrets fire their missiles
        for t in self.turrets:
            if not t.alive:
                continue
            t.fire_in -= dt
            if t.fire_in <= 0 and ship_alive and len(self.missiles) < TURRET_MISSILES:
                t.fire_in = f.rng.uniform(*TURRET_GAP)
                self.missiles.append(BaseMissile(t.x - TURRET_W / 2 - 8, t.y))
                sc._play(getattr(game, "sounds", None), "scramble_launch", volume=0.55, x=t.x - f.cam)
        # the boss fires, as in the saucer, from the face of the wall
        self.bullet_in -= dt
        if self.bullet_in <= 0 and ship_alive and boss.alive and not boss.dying:
            self.bullet_in = f.rng.uniform(*BULLET_GAP)
            if sum(1 for b in self.bullets if b.alive) < BULLET_MAX:
                src = self._bullet_source(p.y)
                if src is not None:
                    self.bullets.append(BaseBullet(src[0], src[1]))
        # the missiles and the bullets fly
        hom_t, hom_v, hom_a = MISSILE_HOMING
        for m in self.missiles:
            m.age += dt
            m.speed = min(MISSILE_SPEED[1], m.speed + MISSILE_ACCEL * dt)
            if ship_alive and m.age <= hom_t and m.x > f.cam + p.x:
                want = max(-hom_v, min(hom_v, (p.y - m.y) * 2.5))
                step = hom_a * dt
                m.vy += max(-step, min(step, want - m.vy))
            m.x -= m.speed * dt
            m.y += m.vy * dt
            if m.x < f.cam - 40:
                m.alive = False
            elif m.y <= f.course.ceiling(m.x) or m.y >= f.course.ground(m.x):
                m.alive = False
                sc._blast(game, f, m.x, m.y, small=True)
        self.missiles = [m for m in self.missiles if m.alive]
        for b in self.bullets:
            b.x -= BULLET_SPEED * dt
            if b.x < f.cam - 20:
                b.alive = False
        self.bullets = [b for b in self.bullets if b.alive]

    def _bullet_source(self, ship_y):
        """Where the next shot of the boss leaves the wall: the face of one of the rows nearest to the ship's height."""
        rows = []
        for row in range(self.rows):
            b = self.front_brick(row)
            if b is not None:
                rows.append((abs(b.y - ship_y), b))
        if not rows:
            return self.back, self.boss.y
        rows.sort(key=lambda r: r[0])
        _, b = rows[self.form.rng.randrange(min(BULLET_NEAR, len(rows)))]
        return b.x - BRICK_W / 2, b.y

    def start(self):
        """The scroll has stopped: the fight begins."""
        self.started = True

    # --- the shots of the ship
    def shot_target(self, x0, x1, y):
        """What a shot of the ship meets going from x0 to x1 (world x, at the height y), the nearest first: (thing, x)."""
        best = None

        def offer(thing, left):
            nonlocal best
            right = thing.box()[2]
            if left - 4 <= x1 and right + 4 >= x0 and (best is None or left < best[1]):
                best = (thing, left)

        for m in self.missiles:
            l, t, r, b = m.box()
            if t - 3 <= y <= b + 3:
                offer(m, l)
        for t in self.turrets:
            if t.alive:
                l, tp, r, b = t.box()
                if tp <= y <= b:
                    offer(t, l)
        row = self.row_of(y)
        if row is not None:
            front = self.front_brick(row)
            if front is not None:
                offer(front, front.box()[0])
        boss = self.boss
        if boss.alive and not boss.dying:
            l, t, r, b = boss.box()
            if t <= y <= b:
                offer(boss, l)
        return best

    def hit(self, game, thing):
        """A shot of the ship (or the Phenix form) struck `thing`."""
        f = self.form
        p = game.player
        snd = getattr(game, "sounds", None)
        if not self.started:                         # (the base slides in, its shields up: the shot sparks off it)
            l, t, r, b = thing.box()
            for _ in range(4):
                a = f.rng.uniform(math.pi * 0.6, math.pi * 1.4)
                v = f.rng.uniform(80, 220)
                f.sparks.append(sc.Spark(l, (t + b) / 2, math.cos(a) * v, math.sin(a) * v, 0.25, 2.0))
            sc._play(snd, "scramble_shield", volume=0.35, x=l - f.cam)
            return
        if isinstance(thing, Brick):
            thing.alive = False
            self.kills["brick"] += 1
            game._add_score(p, 1)
            for _ in range(7):                       # (bits of metal: light, a full explosion per brick is too much)
                a = f.rng.uniform(math.pi * 0.55, math.pi * 1.45)
                v = f.rng.uniform(90, 260)
                f.sparks.append(sc.Spark(thing.x - BRICK_W / 2, thing.y, math.cos(a) * v, math.sin(a) * v,
                                         f.rng.uniform(0.2, 0.45), f.rng.uniform(1.5, 3.0)))
            sc._play(snd, "scramble_brick", volume=0.5, x=thing.x - f.cam)
            game.shake_amount = max(getattr(game, "shake_amount", 0.0), 3.0)
        elif isinstance(thing, Turret):
            thing.alive = False
            self.kills["turret"] += 1
            game._add_score(p, game._enemy_points(sc.STATION_KIND))
            sc._blast(game, f, thing.x, thing.y, small=False)
        elif isinstance(thing, BaseMissile):
            thing.alive = False
            self.missiles = [m for m in self.missiles if m.alive]
            self.kills["missile"] += 1
            game._add_score(p, sc.MISSILE_POINTS)
            sc._blast(game, f, thing.x, thing.y, small=True)
        elif isinstance(thing, Boss):
            self._kill_boss(game)

    def _kill_boss(self, game):
        f = self.form
        boss = self.boss
        if boss.dying or not boss.alive:
            return
        boss.dying = True
        boss.hit_flash = 0.4
        self.kills["boss"] += 1
        game._add_score(game.player, game._boss_kill_points())
        self._boom(game, boss.x, boss.y, "gameover")
        game.shake_amount = 22.0
        sc._play(getattr(game, "sounds", None), "explosion_big", x=boss.x - f.cam)
        sc._play(getattr(game, "sounds", None), "boss_yell", volume=0.9, x=boss.x - f.cam)
        self.dead_for = 0.0
        self.missiles, self.bullets = [], []
        # the base blows up from the boss outwards: the nearer a brick, the sooner
        for b in self.bricks:
            if b.alive:
                d = math.hypot(b.x - boss.x, b.y - boss.y) / math.hypot(W * 0.4, H * 0.6)
                b.blow_at = 0.25 + BLOW_TIME * min(1.0, d) + f.rng.uniform(0.0, 0.25)
        for i, t in enumerate(self.turrets):
            t.blow_at = 0.4 + 0.3 * i if t.alive else None

    def _blow_up(self, game, dt):
        f = self.form
        self.dead_for += dt
        boss = self.boss
        if boss.dying:
            boss.death += dt
            if boss.death >= 1.2:
                boss.alive = False
        for b in self.bricks:
            if b.alive and b.blow_at is not None and self.dead_for >= b.blow_at:
                b.alive = False
                if f.rng.random() < 0.3:
                    self._boom(game, b.x, b.y, "enemy")
        for t in self.turrets:
            if t.alive and getattr(t, "blow_at", None) is not None and self.dead_for >= t.blow_at:
                t.alive = False
                self._boom(game, t.x, t.y, "collision")
        if self.dead_for >= 0.5 and int((self.dead_for - dt) * 3) != int(self.dead_for * 3) and self.dead_for < 2.5:
            self._boom(game, boss.x + f.rng.uniform(-90, 90), boss.y + f.rng.uniform(-90, 90), "gameover")
            sc._play(getattr(game, "sounds", None), "explosion_big", volume=0.7, x=boss.x - f.cam)
        if self.dead_for >= DONE_AFTER:
            self.done = True

    def _boom(self, game, wx, wy, kind):
        f = self.form
        try:
            boom = game._boom(wx - f.cam, wy, kind=kind)
            game.explosions.append(boom)
            f.booms.append(boom)
        except Exception:
            sc.log_exc("scramble_base._boom")

    # --- the ship
    def touch_ship(self, game, p):
        """The missiles and the shots of the base against the ship."""
        f = self.form
        dome = bool(p.is_phenix) and getattr(p, "uses_shield", False)
        fire_bird = bool(p.is_phenix) and not dome
        hx, hy = sc.SHIP_BOX
        ship = (f.cam + p.x - hx, p.y - hy, f.cam + p.x + hx, p.y + hy)
        for m in self.missiles:
            if m.alive and sc._overlap(ship, m.box()):
                if fire_bird:
                    self.hit(game, m)
                    continue
                m.alive = False
                sc._blast(game, f, m.x, m.y, small=True)
                if dome:
                    game._shield_absorb(p, m.x - f.cam, m.y)
                    continue
                sc._ship_hit(game, f)
                break
        self.missiles = [m for m in self.missiles if m.alive]
        for b in self.bullets:
            if b.alive and sc._overlap(ship, (b.x - 7, b.y - 3, b.x + 7, b.y + 3)):
                b.alive = False
                if dome:
                    game._shield_absorb(p, b.x - f.cam, b.y)
                    continue
                if fire_bird:
                    continue
                sc._ship_hit(game, f)
                break
        self.bullets = [b for b in self.bullets if b.alive]
