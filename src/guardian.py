"""The Guardians: telegraphed, finite fire-laser bolts. GuardianSquad: the Guardians that come with the waves of some
missions of the Adventure. Their timing is in seconds and independent of act, difficulty and arcade random state.
"""
import math
import random

import pygame

import fire_death
import guardian_parts

from settings import BASE_HEIGHT, BASE_WIDTH, asset_path

CHARGE_SECONDS = 0.95
LASER_SPEED = 780.0
LASER_LENGTH = 158
LASER_FRAMES = 3                 # fire animation: frames side by side in laser.png
LASER_FPS = 14.0
LASER_WIDTH = 10
SHOT_GAP = 1.1
CHARGE_STAGGER = 0.32
FIRE_STAGGER = 0.18
DIVE_WARNING = 0.55
DIVE_SPEED = 340.0
RETURN_SPEED = 300.0
PER_WAVE = 5
MAX_HP = 3                       # three hits on the body
WING_REGEN = 3.2                 # same as the gargoyles' wings: a destroyed wing is back after 3.2 s
WING_GROW = 0.8                  # ...and its last 0.8 s are the regrowth animation
HURT_FLASH = 0.13                # white flash on the whole bird after a hit
BAR_FLASH = 0.45                 # the segment just lost blinks in the life bar
FX_LIMIT = 48
_ART = None
_PARTS = None


def art():
    global _ART
    if _ART is None:
        sheet = pygame.image.load(asset_path("sprites", "guardian", "sentinelle.png")).convert_alpha()
        frames = [[sheet.subsurface((i * 160, row * 160, 160, 160)).copy() for i in range(4)]
                  for row in range(2)]
        strip = pygame.image.load(asset_path("sprites", "guardian", "laser.png")).convert_alpha()
        fw = strip.get_width() // LASER_FRAMES
        laser = [strip.subsurface((i * fw, 0, fw, strip.get_height())).copy() for i in range(LASER_FRAMES)]
        _ART = frames, laser
    return _ART


def parts():
    """The sheet cut into body and wings with the wounds baked in (src/guardian_parts.py), built once."""
    global _PARTS
    if _PARTS is None:
        _PARTS = guardian_parts.Parts(art()[0])
    return _PARTS


class FireLaser:
    """A detached downward bolt, not a hitscan beam or a homing projectile."""
    def __init__(self, x, y, owner_id=None):
        self.x, self.y = float(x), float(y)
        self.origin_y = self.y
        self.prev_y = self.y
        self.alive = True
        self.owner_id = owner_id
        self.age = 0.0
        self.eaten = 0.0                 # px of its tip already split on the reflective coating (src/laser_split.py)

    def update(self, dt):
        self.age += dt
        self.prev_y = self.y
        self.y += LASER_SPEED * dt
        if self.y - LASER_LENGTH > BASE_HEIGHT:
            self.alive = False

    def get_hitbox(self):
        # Swept bounds avoid tunnelling at a low frame rate. The tail never
        # extends behind the mouth when a bolt is first emitted.
        top = max(self.origin_y, self.prev_y - LASER_LENGTH)
        return pygame.Rect(round(self.x - LASER_WIDTH / 2), math.floor(top),
                           LASER_WIDTH, max(1, math.ceil(self.y - self.eaten - top)))

    def hits_moving_rect(self, previous, current):
        """Continuous overlap with a moving bird, including the growing tail."""
        # Each gap must be nonnegative at the same time in this tick.
        # tail=max(origin, tip-length), so both tail constraints must hold.
        gaps = (
            (previous.right - (self.x - LASER_WIDTH / 2),
             current.right - (self.x - LASER_WIDTH / 2)),
            (self.x + LASER_WIDTH / 2 - previous.left,
             self.x + LASER_WIDTH / 2 - current.left),
            (self.prev_y - self.eaten - previous.top, self.y - self.eaten - current.top),
            (previous.bottom - self.origin_y, current.bottom - self.origin_y),
            (previous.bottom - self.prev_y + LASER_LENGTH,
             current.bottom - self.y + LASER_LENGTH),
        )
        enter, leave = 0.0, 1.0
        for start, end in gaps:
            if start < 0 and end < 0:
                return False
            if start < 0:
                enter = max(enter, -start / (end - start))
            elif end < 0:
                leave = min(leave, start / (start - end))
        return enter <= leave

    def draw(self, surface):
        if not self.alive:
            return
        pic = art()[1][int(self.age * LASER_FPS) % LASER_FRAMES]
        visible = min(LASER_LENGTH, max(0, int(self.y - self.origin_y)))
        shown = visible - int(self.eaten)                # (its tip split on the coating is drawn by src/laser_split.py)
        if shown > 0:
            surface.blit(pic, (round(self.x - pic.get_width() / 2), round(self.y - visible)),
                         (0, LASER_LENGTH - visible, pic.get_width(), shown))


_SPIN = {}


def _spun(surf, angle):
    """A wing fragment turned by ``angle`` degrees, cached by 24-degree steps (a few dozen small pictures at most)."""
    step = int(round(angle / 24.0)) % 15
    key = (id(surf), step)
    pic = _SPIN.get(key)
    if pic is None:
        pic = _SPIN[key] = pygame.transform.rotate(surf, step * 24)
    return pic


def _lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


class Guardian:
    stage = 3
    width = 116
    height = 100
    scale = 1.0                          # (the Alpha is bigger: everything it draws and its hitboxes)
    bestiary_kind = "guardian"           # its entry of the Bestiary of the Adventure (story_state.BESTIARY)
    point_mult = 1

    def __init__(self, x, y, index, squad=PER_WAVE):
        self.x, self.y = float(x), float(y)
        self.home_x = self.x
        self.home_y = self.y
        self.index = index
        self.squad = squad                   # how many fly together (they spread around the ship by their index)
        self.owner_id = index
        self.time = 0.0
        self.anim = 0.0
        self.alive = True
        self.dying = False
        self.charge = 0.0
        self.firing = 0.0
        self.emission = None
        self.state = "patrol"
        self.shot_wait = SHOT_GAP + index * 0.38
        self.dive_wait = 4.6 + index * 1.2
        self.warning = 0.0
        self.target = None
        self.vx = self.vy = 0.0
        self.frames = art()[0]
        self.parts = parts()
        # Health and wings: three hits on the body, and wings that the gargoyles' rules apply to (3.2 s to regrow).
        self.max_hp = MAX_HP
        self.hp = MAX_HP
        self.WING_REGEN = WING_REGEN
        self.wing_left = True
        self.wing_right = True
        self.wing_left_timer = 0.0
        self.wing_right_timer = 0.0
        # Looks: the hit flash, the knock-back, the blink of the lost segment, smoke/embers/flames and tumbling wings.
        # A private generator: the effects never touch the arcade's random state (the replays depend on it).
        self.rng = random.Random(1009 + index)
        self.hurt = 0.0
        self.bar_flash = 0.0
        self.kick_x = self.kick_y = 0.0
        self.fx = []
        self.fragments = []
        self._acc = {"smoke": 0.0, "ember": 0.0, "flame": 0.0, "spark": 0.0}

    @property
    def diving(self):
        return self.alive and self.state == "dive"

    @property
    def level(self):
        """0 = intact (3 HP), 1 = wounded (2 HP), 2 = nearly dead (1 HP); the Alpha: by thirds of its health."""
        if self.max_hp != MAX_HP:
            lost = (self.max_hp - self.hp) * MAX_HP // self.max_hp
            return max(0, min(guardian_parts.LEVELS - 1, lost))
        return max(0, min(guardian_parts.LEVELS - 1, self.max_hp - self.hp))

    def fire_lasers(self):
        """The laser(s) it fires (the first one holds it in place until it leaves its emitter)."""
        return [FireLaser(self.x, self.y + 16 * self.scale, self.owner_id)]

    @property
    def has_wing(self):
        return self.wing_left or self.wing_right

    @property
    def has_both_wings(self):
        return self.wing_left and self.wing_right

    @property
    def laser_attached(self):
        """The bolt's growing tail still touches its emission point."""
        bolt = self.emission
        return (bolt is not None and bolt.alive
                and bolt.y - bolt.origin_y <= LASER_LENGTH)

    def can_shoot(self):
        """Like the gargoyles: a bird that lost both wings cannot shoot."""
        return self.alive and self.has_wing

    def start_dive(self, player_x, player_y):
        if self.laser_attached or not self.has_both_wings:
            return
        self.state = "windup"
        self.warning = DIVE_WARNING
        self.target = (max(96, min(BASE_WIDTH - 96, player_x)),
                       max(self.y + 180, min(BASE_HEIGHT - 48, player_y)))
        self.charge = 0.0
        self.dive_wait = 6.0 + self.index * 0.8

    # ---- wings ---------------------------------------------------------------------------------------------------
    def wing_grow(self, side):
        """0 while a destroyed wing is still a stump, then 0..1 during the regrowth animation (the last 0.8 s)."""
        if getattr(self, "wing_" + side):
            return 1.0
        t = getattr(self, "wing_%s_timer" % side)
        return max(0.0, min(1.0, (t - (self.WING_REGEN - WING_GROW)) / WING_GROW))

    def _tick_wings(self, dt):
        for side in guardian_parts.SIDES:
            if getattr(self, "wing_" + side):
                continue
            timer = getattr(self, "wing_%s_timer" % side) + dt
            if timer >= self.WING_REGEN:
                timer = 0.0
                setattr(self, "wing_" + side, True)
                self._burst(self._wing_centre(side), "ember", 7, (60, 160))
            setattr(self, "wing_%s_timer" % side, timer)

    def _pose(self):
        row = int(self.charge > 0 or self.firing > 0)
        return row, int(self.anim) % 4

    def _wing_centre(self, side):
        row, frame = self._pose()
        part = self.parts.wing[row][frame][side][self.level]
        k = self.scale
        return (self.x + (part.ox + part.surf.get_width() / 2 - 80) * k,
                self.y + (part.oy + part.surf.get_height() / 2 - 80) * k)

    def _box(self, dx, dy, w, h):
        k = self.scale
        return pygame.Rect(round(self.x + dx * k), round(self.y + dy * k), round(w * k), round(h * k))

    def get_left_wing_hitbox(self):
        if not self.wing_left or not self.alive:
            return pygame.Rect(0, 0, 0, 0)
        return self._box(-78, -58, 58, 90)

    def get_right_wing_hitbox(self):
        if not self.wing_right or not self.alive:
            return pygame.Rect(0, 0, 0, 0)
        return self._box(20, -58, 58, 90)

    def hit_wing(self, side):
        """Shoot a wing off: it tumbles away and regrows after WING_REGEN seconds. Returns False if it was already gone."""
        if not self.alive or not getattr(self, "wing_" + side):
            return False
        self._shed(side, kick=True)
        setattr(self, "wing_" + side, False)
        setattr(self, "wing_%s_timer" % side, 0.0)
        self.hurt = HURT_FLASH * 0.6
        self.kick_x = -3.0 if side == "left" else 3.0
        self.kick_y = 4.0
        return True

    def _shed(self, side, kick):
        row, frame = self._pose()
        part = self.parts.wing[row][frame][side][self.level]
        cx, cy = self._wing_centre(side)
        sign = -1 if side == "left" else 1
        spin = self.rng.uniform(150, 260) * sign
        speed = self.rng.uniform(70, 150) if kick else self.rng.uniform(120, 220)
        self.fragments.append([cx, cy, sign * speed, -self.rng.uniform(90, 150), 0.0, spin, 0.0, 1.0, part.surf])
        self._burst((cx, cy), "chip", 7, (50, 150))
        self._burst((cx, cy), "ember", 5, (40, 130))

    # ---- health --------------------------------------------------------------------------------------------------
    def hit(self, damage=1):
        """One shot in the body. Returns True when it was the last health point (the bird is dead)."""
        if not self.alive:
            return False
        self.hp = max(0, self.hp - damage)
        if self.hp <= 0:
            self.kill()
            return True
        self.hurt = HURT_FLASH
        self.bar_flash = BAR_FLASH
        self.kick_x = self.rng.choice((-3.0, 3.0))
        self.kick_y = 9.0
        origin = (self.x, self.y)
        self._burst(origin, "chip", 9 + 4 * self.level, (60, 190))
        self._burst(origin, "ember", 6 + 4 * self.level, (50, 160))
        self._burst(origin, "spark", 3, (150, 260))
        return False

    def kill(self, flash=True):
        if not self.alive:
            return
        if flash:
            for side in guardian_parts.SIDES:
                if getattr(self, "wing_" + side):
                    self._shed(side, kick=False)
            origin = (self.x, self.y)
            self._burst(origin, "chip", 12, (60, 220))
            self._burst(origin, "ember", 14, (50, 200))
            self._burst(origin, "smoke", 5, (10, 40))
        self.hp = 0
        self.alive = False
        self.dying = False
        self.charge = 0.0
        self.state = "dead"

    # ---- effects -------------------------------------------------------------------------------------------------
    def _spawn(self, kind, x, y, vx, vy, life):
        if len(self.fx) >= FX_LIMIT:
            self.fx.pop(0)
        self.fx.append([x, y, vx, vy, 0.0, life, kind])

    def _burst(self, origin, kind, count, speed):
        ox, oy = origin
        for _ in range(count):
            angle = self.rng.uniform(0, math.tau)
            v = self.rng.uniform(*speed)
            life = {"smoke": 0.9, "spark": 0.2}.get(kind, self.rng.uniform(0.45, 0.95))
            self._spawn(kind, ox + math.cos(angle) * 6, oy + math.sin(angle) * 6,
                        math.cos(angle) * v, math.sin(angle) * v - 25, life)

    def fx_active(self):
        return bool(self.fx or self.fragments)

    def _emit(self, dt):
        """A wounded bird leaks smoke; at 1 HP it burns: flames, embers falling, sparks, thick smoke."""
        level = self.level
        if level == 0:
            return
        rates = ({"smoke": 2.4, "ember": 0.0, "flame": 0.0, "spark": 0.6} if level == 1 else
                 {"smoke": 9.0, "ember": 7.0, "flame": 11.0, "spark": 1.8})
        rng = self.rng
        for kind, rate in rates.items():
            self._acc[kind] += rate * dt
            while self._acc[kind] >= 1.0:
                self._acc[kind] -= 1.0
                px = self.x + rng.uniform(-13, 13)
                if kind == "smoke":
                    self._spawn(kind, px, self.y + rng.uniform(-26, 4), rng.uniform(-8, 8), rng.uniform(-45, -25), 1.0)
                elif kind == "flame":
                    self._spawn(kind, px, self.y + rng.uniform(-34, -14), rng.uniform(-14, 14), rng.uniform(-110, -60),
                                rng.uniform(0.3, 0.5))
                elif kind == "ember":
                    self._spawn(kind, px, self.y + rng.uniform(-10, 30), rng.uniform(-35, 35), rng.uniform(-70, -10),
                                rng.uniform(0.5, 0.9))
                else:
                    angle = rng.uniform(0, math.tau)
                    v = rng.uniform(150, 260)
                    self._spawn(kind, px, self.y + rng.uniform(-20, 20), math.cos(angle) * v, math.sin(angle) * v, 0.2)

    def tick_fx(self, dt):
        """Particles and tumbling wings; they outlive the bird that shed them."""
        alive = []
        for p in self.fx:
            p[4] += dt
            if p[4] >= p[5]:
                continue
            kind = p[6]
            if kind in ("ember", "chip"):
                p[3] += (380 if kind == "ember" else 560) * dt
            elif kind == "flame":
                p[3] -= 60 * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            alive.append(p)
        self.fx = alive
        kept = []
        for f in self.fragments:
            f[6] += dt
            if f[6] >= f[7]:
                continue
            f[3] += 560 * dt
            f[0] += f[2] * dt
            f[1] += f[3] * dt
            f[4] += f[5] * dt
            if self.rng.random() < 18 * dt:                       # a burning wing leaves embers behind
                self._spawn("ember", f[0], f[1], f[2] * 0.2, 20.0, 0.5)
            kept.append(f)
        self.fragments = kept

    # ---- motion --------------------------------------------------------------------------------------------------
    def update(self, dt, player_x=None, player_y=BASE_HEIGHT - 95):
        self.time += dt
        self.anim += dt * (6.5 if self.hp <= 1 else 8.0)          # a nearly dead bird beats its wings more slowly
        self.hurt = max(0.0, self.hurt - dt)
        self.bar_flash = max(0.0, self.bar_flash - dt)
        decay = math.exp(-14 * dt)
        self.kick_x *= decay
        self.kick_y *= decay
        self._tick_wings(dt)
        self._emit(dt)
        self.tick_fx(dt)
        self.firing = max(0.0, self.firing - dt)
        self.shot_wait = max(0.0, self.shot_wait - dt)
        self.dive_wait = max(0.0, self.dive_wait - dt)
        if self.laser_attached:
            return  # freeze both axes until this Guardian's own laser detaches
        if self.state == "windup":
            self.warning -= dt
            if self.warning <= 0:
                dx, dy = self.target[0] - self.x, self.target[1] - self.y
                length = max(1, math.hypot(dx, dy))
                self.vx, self.vy = dx / length * DIVE_SPEED, dy / length * DIVE_SPEED
                self.state = "dive"
            return
        if self.state == "dive":
            self.x += self.vx * dt
            self.y += self.vy * dt
            if self.y > BASE_HEIGHT + 85 or self.x < -85 or self.x > BASE_WIDTH + 85:
                # Wrap only once the whole sprite is off-screen, as gargoyles
                # do: return from above instead of flying back up past the ship.
                self.x = max(100, min(BASE_WIDTH - 100, self.x))
                self.y = -85.0
                self.state = "recover"
                self.fx.clear()                                    # the trail does not teleport with the bird
            return
        if self.state == "recover":
            dx, dy = self.home_x - self.x, self.home_y - self.y
            distance = math.hypot(dx, dy)
            if distance <= RETURN_SPEED * dt:
                self.x, self.y = self.home_x, self.home_y
                self.state = "patrol"
                self.shot_wait = max(0.35, self.shot_wait)
            else:
                self.x += dx / distance * RETURN_SPEED * dt
                self.y += dy / distance * RETURN_SPEED * dt
            return
        if not self.charge:
            aim = self.home_x if player_x is None else player_x + (self.index - (self.squad - 1) / 2) * 150
            target_x = max(100, min(BASE_WIDTH - 100, aim + math.sin(self.time * 0.9 + self.index) * 65))
            target_y = self.home_y + math.sin(self.time * 0.7 + self.index) * 24
            self.x += max(-110 * dt, min(110 * dt, target_x - self.x))
            self.y += max(-45 * dt, min(45 * dt, target_y - self.y))

    def get_hitbox(self):
        # The solid body is the target, not the translucent wing tips.
        return self._box(-24, -19, 48, 58)

    # ---- drawing -------------------------------------------------------------------------------------------------
    def _blit_part(self, surface, part, cx, cy):
        surface.blit(part.surf, (cx + part.ox, cy + part.oy))

    def _draw_wing(self, surface, side, row, frame, cx, cy):
        level = self.level
        if getattr(self, "wing_" + side):
            bank = self.parts.white_wing if self.hurt > 0 else self.parts.wing
            self._blit_part(surface, bank[row][frame][side][level], cx, cy)
            return
        part = self.parts.wing[row][frame][side][level]
        progress = self.wing_grow(side)
        w, h = part.surf.get_size()
        if progress > 0:
            # Regrowth: the wing unfolds from the shoulder outwards, its front glowing white-hot.
            shown = max(1, min(w, int(math.ceil(progress * w))))
            if side == "left":
                surface.blit(part.surf, (cx + part.ox + w - shown, cy + part.oy), (w - shown, 0, shown, h))
                front = cx + part.ox + w - shown
            else:
                surface.blit(part.surf, (cx + part.ox, cy + part.oy), (0, 0, shown, h))
                front = cx + part.ox + shown
            for k in range(6):
                fy = cy + part.oy + int(h * (0.12 + 0.15 * k) + math.sin(self.time * 18 + k * 1.7) * 3)
                pygame.draw.circle(surface, (255, 235, 150), (front, fy), 2)
                pygame.draw.circle(surface, (255, 140, 40), (front + (2 if side == "left" else -2), fy), 1)
            return
        # Stump: the torn root smoulders.
        for k, (ex, ey) in enumerate(self.parts.edge[side]):
            if k % 2 or not 10 <= ey <= 76:
                continue
            pulse = 0.5 + 0.5 * math.sin(self.time * 9 + k * 0.9)
            pygame.draw.circle(surface, _lerp((150, 40, 20), (255, 190, 70), pulse), (cx + ex, cy + ey), 1)

    def _draw_bar(self, surface, ox, oy):
        width = 2 + 14 * self.max_hp                    # (44 for 3 HP; the Alpha's is longer)
        left, top = ox - width // 2, oy - round(58 * self.scale)
        pygame.draw.rect(surface, (12, 10, 16), (left, top, width, 8))
        pygame.draw.rect(surface, (110, 100, 112), (left, top, width, 8), 1)
        level = self.level
        if level >= 2:
            pulse = 0.5 + 0.5 * math.sin(self.time * 10)
            colour = _lerp((255, 60, 40), (255, 170, 140), pulse)
        else:
            colour = (240, 190, 50) if level == 1 else (90, 225, 105)
        for seg in range(self.max_hp):
            rect = (left + 2 + seg * 14, top + 2, 12, 4)
            if seg < self.hp:
                pygame.draw.rect(surface, colour, rect)
            elif self.bar_flash > 0 and seg == self.hp:        # the segment just lost blinks white, then goes out
                pygame.draw.rect(surface, _lerp((40, 24, 24), (255, 255, 255), self.bar_flash / BAR_FLASH), rect)
            else:
                pygame.draw.rect(surface, (40, 24, 24), rect)

    def _draw_fx(self, surface, smoke):
        for x, y, _vx, _vy, age, life, kind in self.fx:
            if (kind == "smoke") != smoke:
                continue
            t = age / life
            px, py = round(x), round(y)
            if kind == "smoke":
                pic = self.parts.smoke[min(guardian_parts.SMOKE_STEPS - 1, int(t * guardian_parts.SMOKE_STEPS))]
                surface.blit(pic, (px - pic.get_width() // 2, py - pic.get_height() // 2))
            elif kind == "flame":
                colour = _lerp((255, 235, 140), (255, 90, 20), min(1.0, t * 1.6)) if t < 0.65 else _lerp((255, 90, 20), (90, 25, 10), (t - 0.65) / 0.35)
                pygame.draw.circle(surface, colour, (px, py), max(1, round(5 * (1 - t))))
            elif kind == "ember":
                pygame.draw.rect(surface, _lerp((255, 200, 80), (190, 40, 20), t), (px, py, 2, 2))
            elif kind == "chip":
                pygame.draw.rect(surface, (70, 62, 66) if int(x + y) % 2 else (150, 60, 40), (px, py, 3, 2))
            else:
                pygame.draw.line(surface, (255, 240, 170), (px, py), (round(x - _vx * 0.03), round(y - _vy * 0.03)))

    def draw(self, surface):
        self._draw_fx(surface, True)
        for fx_, fy_, _vx, _vy, rot, _vr, age, life, img in self.fragments:
            pic = _spun(img, math.degrees(rot))
            pic.set_alpha(255 if age < life * 0.55 else max(0, round(255 * (1 - (age / life - 0.55) / 0.45))))
            surface.blit(pic, (round(fx_ - pic.get_width() / 2), round(fy_ - pic.get_height() / 2)))
        if self.alive:
            row, frame = self._pose()
            level = self.level
            tremble = round(math.sin(self.time * 47)) if level == 2 else 0     # a nearly dead bird shudders
            cx = round(self.x - 80 + self.kick_x) + tremble
            cy = round(self.y - 80 + self.kick_y)
            self._draw_bird(surface, row, frame, level, cx, cy)
            self._draw_bar(surface, cx + 80, cy + 80)
        self._draw_fx(surface, False)


    def _draw_bird(self, surface, row, frame, level, cx, cy):
        """The wings, the body, its glowing cracks and the charge of the laser, in the 160 x 160 cell at (cx, cy)."""
        for side in guardian_parts.SIDES:
            self._draw_wing(surface, side, row, frame, cx, cy)
        bank = self.parts.white_body if self.hurt > 0 else self.parts.body
        self._blit_part(surface, bank[row][frame][level], cx, cy)
        if level == 2:                                                      # the cracks glow, pulsing
            for group in guardian_parts.CRACKS:
                for k, line in enumerate(group):
                    mx, my = line[len(line) // 2]
                    pulse = 0.5 + 0.5 * math.sin(self.time * 8 + k * 2.1)
                    pygame.draw.circle(surface, _lerp((255, 120, 30), (255, 230, 120), pulse), (cx + mx, cy + my), 1)
        if self.charge:
            radius = 3 + int(6 * min(1, self.charge / CHARGE_SECONDS))
            for ex in self.charge_points():
                pygame.draw.circle(surface, (255, 145, 35), (cx + ex, cy + 96), radius)
                pygame.draw.circle(surface, (255, 245, 180), (cx + ex, cy + 96), max(2, radius // 2))

    def charge_points(self):
        """Where the laser charges, in the 160 x 160 cell (one point; the Alpha: two)."""
        return (80,)


_HALOS = {}


def _halo(side, step):
    """The golden glow behind the Alpha (added to the screen: brighter in the middle, nothing at the edge), five
    strengths for its slow pulse, made once."""
    key = (side, step)
    if key not in _HALOS:
        surf = pygame.Surface((side, side))
        c, most = side // 2, side * 0.42
        for r in range(int(most), 0, -2):
            k = (1 - r / most) ** 1.6 * (0.45 + 0.12 * step)
            pygame.draw.circle(surf, (round(150 * k), round(95 * k), round(25 * k)), (c, c), r)
        _HALOS[key] = surf
    return _HALOS[key]


ALPHA_SCALE = 1.4                # the Alpha Guardian of Gardiens III: bigger ...
ALPHA_HP = 6                     # ... twice the health ...
ALPHA_SPREAD = 22                # ... and a double laser, this far on each side of its middle (in the 160 cell)
ALPHA_POINTS = 10                # ... worth ten Guardians
ALPHA_DROP = 34                  # it patrols a little lower than the others (its health bar clear of the HUD)


class AlphaGuardian(Guardian):
    """The Alpha of Gardiens III: a bigger Guardian (ALPHA_SCALE) with 6 HP and a double laser, crowned with a halo."""
    scale = ALPHA_SCALE
    bestiary_kind = "alpha"
    point_mult = ALPHA_POINTS
    width = round(Guardian.width * ALPHA_SCALE)
    height = round(Guardian.height * ALPHA_SCALE)

    def __init__(self, x, y, index, squad=PER_WAVE):
        super().__init__(x, y, index, squad)
        self.max_hp = self.hp = ALPHA_HP
        self._cell = None

    def fire_lasers(self):
        y = self.y + 16 * self.scale
        d = ALPHA_SPREAD * self.scale
        return [FireLaser(self.x - d, y, self.owner_id), FireLaser(self.x + d, y, self.owner_id)]

    def charge_points(self):
        return (80 - ALPHA_SPREAD, 80 + ALPHA_SPREAD)

    def _draw_bird(self, surface, row, frame, level, cx, cy):
        if self._cell is None:
            self._cell = pygame.Surface((160, 160), pygame.SRCALPHA)
        cell = self._cell
        cell.fill((0, 0, 0, 0))
        super()._draw_bird(cell, row, frame, level, 0, 0)
        side = round(160 * self.scale)
        big = pygame.transform.smoothscale(cell, (side, side))
        mx, my = cx + 80, cy + 80
        pulse = 0.5 + 0.5 * math.sin(self.time * 3.2)
        surface.blit(_halo(side, round(4 * pulse)), (mx - side // 2, my - side // 2 - 8), special_flags=pygame.BLEND_RGB_ADD)
        surface.blit(big, (mx - side // 2, my - side // 2))


# Burning frames are prepared once per colour, never transformed during draw.
BURN_SECONDS = 1.35
BURN_FRAME_COUNT = 28
_BURN_ART = {}


def burning_frames(stage, source):
    """Ignition, flames, charred silhouette, then the ash scattered by the wind (src/fire_death.py)."""
    if stage in _BURN_ART:
        return _BURN_ART[stage]
    size = max(128, source.get_width() + 64, source.get_height() + 64)
    origin = ((size - source.get_width()) // 2, (size - source.get_height()) // 2)
    _BURN_ART[stage] = fire_death.frames(source, BURN_FRAME_COUNT, fire_death.BIRD, (size, size), origin)
    return _BURN_ART[stage]


def gargoyle_picture(bird, wing_left=True, wing_right=True):
    """A gargoyle (enemy.BigBird) drawn alone, wings up, on a transparent picture just big enough (its wings as given)."""
    bw, bh = bird.body_img.get_size()
    ww, wh = bird.wing_up.get_size()
    w, h = bw + 2 * ww + 8, max(bh, wh) + 24
    pic = pygame.Surface((w, h), pygame.SRCALPHA)
    pic.fill((0, 0, 0, 0))
    saved = (bird.x, bird.y, bird.flap, bird.wing_left, bird.wing_right, bird.dying)
    try:
        bird.x, bird.y, bird.flap, bird.dying = w / 2.0, h / 2.0, math.pi / 2, False
        bird.wing_left, bird.wing_right = wing_left, wing_right
        bird.draw(pic)
    finally:
        bird.x, bird.y, bird.flap, bird.wing_left, bird.wing_right, bird.dying = saved
    return pic


def gargoyle_burning_frames(bird):
    """The fire and the ash of a gargoyle (as for a bird), with the wings it still has. Made once per kind of gargoyle and
    wings (about a third of a second): the one with both wings is made before the mission (warm_gargoyle_ash)."""
    key = ("garg", int(getattr(bird, "stage", 3)), bool(bird.wing_left), bool(bird.wing_right))
    if key not in _BURN_ART:
        pic = gargoyle_picture(bird, key[2], key[3])
        size = max(128, pic.get_width() + 64, pic.get_height() + 64)
        origin = ((size - pic.get_width()) // 2, (size - pic.get_height()) // 2)
        _BURN_ART[key] = fire_death.frames(pic, BURN_FRAME_COUNT, fire_death.BIRD, (size, size), origin)
    return _BURN_ART[key]


def warm_gargoyle_ash(stages=(3, 4)):
    """Make the ash of the gargoyles beforehand (behind the loading bar of a mission whose Guardians can burn gargoyles),
    so that a burning gargoyle never holds the game: with both wings, and with only one (a gargoyle often loses a wing to
    the shots of the ship before a laser burns it). The two kinds of small birds a laser can burn are made too."""
    from enemy import BigBird, Enemy
    state = random.getstate()
    try:
        for stage in (1, 2):
            burning_frames(stage, Enemy(0, 0, 0, stage).frames[0])
        for stage in stages:
            bird = BigBird(0, 0, 0, stage)
            for left, right in ((True, True), (True, False), (False, True)):
                saved = (bird.wing_left, bird.wing_right)
                bird.wing_left, bird.wing_right = left, right
                try:
                    gargoyle_burning_frames(bird)
                finally:
                    bird.wing_left, bird.wing_right = saved
    finally:
        random.setstate(state)                      # (a gargoyle made here must not change the game's draws)


def can_burn(bird):
    """Has `bird` a picture to burn and to fall to ash: a bird of the arcade (its frames) or a gargoyle (its body)."""
    frames = getattr(bird, "frames", None)
    if frames and isinstance(frames, list) and isinstance(frames[0], pygame.Surface):
        return True
    return isinstance(getattr(bird, "body_img", None), pygame.Surface) and isinstance(getattr(bird, "wing_up", None),
                                                                                    pygame.Surface)


class BurningBird:
    def __init__(self, bird):
        self.x, self.y = bird.x, bird.y
        frames = getattr(bird, "frames", None)
        if frames and isinstance(frames, list) and isinstance(frames[0], pygame.Surface):
            self.frames = burning_frames(bird.stage, frames[0])
        else:
            self.frames = gargoyle_burning_frames(bird)          # (a gargoyle: its body and the wings it has left)
        self.age = 0.0

    @property
    def alive(self):
        return self.age < BURN_SECONDS

    def update(self, dt):
        self.age += dt

    def draw(self, surface):
        if self.alive:
            index = min(len(self.frames) - 1, int(self.age / BURN_SECONDS * len(self.frames)))
            frame = self.frames[index]
            surface.blit(frame, frame.get_rect(center=(round(self.x), round(self.y))))


def burn_birds(owner, birds, previous_boxes):
    """The lasers of `owner.bullets` burn the birds they cross (`previous_boxes`: where each bird was a tick ago, so a
    fast bolt cannot jump over one). The birds burn and fall to ash (BurningBird, in `owner.effects`), worth no points,
    the gargoyles too. A bird with no picture to burn (a bird of the Galaga waves) just explodes. Returns how many burned."""
    burned = 0
    for bolt in owner.bullets:
        if not isinstance(bolt, FireLaser):
            continue
        # A bolt leaving the screen can still cross a bird this tick.
        for bird in birds:
            if not bird.alive or bird.dying:
                continue
            current = bird.get_hitbox()
            previous = previous_boxes.get(bird, current)
            # Wrapping from below to above is a teleport, not a sweep
            # through every laser on screen.
            if abs(previous.centery - current.centery) > BASE_HEIGHT / 2:
                previous = current
            if bolt.hits_moving_rect(previous, current):
                burn_bird(owner, bird)
                burned += 1
    return burned


def burn_bird(owner, bird):
    """A laser (or a half of one split on the reflective coating) burns `bird`: it burns and falls to ash (BurningBird,
    in `owner.effects`), worth no points; the gargoyles too. A bird with no picture to burn just explodes."""
    effects = getattr(owner, "effects", None)
    if can_burn(bird) and effects is not None:
        effects.append(BurningBird(bird))
        bird.kill(flash=False)
    else:
        try:
            bird.kill(flash=False)
        except TypeError:
            bird.kill()
    if getattr(owner, "sounds", None):
        owner.sounds.play("enemy_explosion", volume=0.35, x=bird.x)


def guardian_attacks(owner, dt, player_x, player_y):
    """The Guardians of `owner` (owner.guardians, owner.bullets, owner.clock, owner.next_charge, owner.next_fire,
    owner.sounds) charge and fire their lasers, one after the other, and dive one at a time. `owner.volley` (Gardiens II):
    they charge all together, every VOLLEY_GAP seconds, and fire at the same time: a wall of lasers."""
    living = [bird for bird in owner.guardians if bird.alive]
    together = bool(getattr(owner, "volley", False))
    if together and owner.clock >= owner.next_charge:
        ready = [b for b in living if b.state == "patrol" and not b.charge and b.can_shoot() and not b.laser_attached
                 and not any(getattr(x, "owner_id", None) == b.owner_id for x in owner.bullets)]
        if ready:
            for b in ready:
                b.charge = 1e-9
            owner.next_charge = owner.clock + VOLLEY_GAP
    for bird in living:
        active = any(getattr(b, "owner_id", None) == bird.owner_id for b in owner.bullets)
        if bird.charge and not bird.has_wing:
            bird.charge = 0.0            # no wing left: the shot is cancelled, like a gargoyle that cannot shoot
            bird.shot_wait = max(bird.shot_wait, 0.5)
            continue
        if bird.charge:
            bird.charge += dt
            if bird.charge >= CHARGE_SECONDS and (together or owner.clock >= owner.next_fire) and not active:
                lasers = bird.fire_lasers()
                bird.emission = lasers[0]
                owner.bullets.extend(lasers)
                bird.charge = 0.0
                bird.firing = 0.2
                bird.shot_wait = SHOT_GAP + bird.index * 0.15
                owner.next_fire = owner.clock + FIRE_STAGGER
                if owner.sounds:
                    owner.sounds.play("enemy_shoot", x=bird.x)
            continue
        if bird.state != "patrol" or bird.laser_attached:
            continue
        if bird.dive_wait <= 0 and bird.has_both_wings and not any(b.state in ("windup", "dive") for b in living):
            bird.start_dive(player_x, player_y)
        elif not together and bird.can_shoot() and not active and bird.shot_wait <= 0 and owner.clock >= owner.next_charge:
            bird.charge = 1e-9
            owner.next_charge = owner.clock + CHARGE_STAGGER


SQUAD_Y = 126                    # where the Guardians of an arcade wave patrol: above the birds of the formation ...
SQUAD_BOSS_Y = 440               # ... or, with the boss, below its saucer: a barrage in front of it
SQUAD_ENTRY = 1.2                # ... they come down from the top of the screen, a little after the wave
SQUAD_STEP = 0.6                 # ... one after the other
VOLLEY_GAP = 2.6                 # Gardiens II: the whole squad charges together, this often


class GuardianSquad:
    """Guardians flying with the birds of an arcade wave of the Adventure (story_state.MISSIONS "guardians_at"): they
    come down from the top, patrol above the birds, charge and fire their lasers (which burn the birds they cross) and
    dive. They live beside the formation, whatever it is (a wave, the swarm, the Galaga chains, a boss): the game adds them to the targets of the shots, to the attacks against the ship and to the end of the wave
    (`targets`, `clear`). Their lasers go into the formation's own list of shots (so they are cleared with it)."""

    def __init__(self, count, sounds=None, y=SQUAD_Y, volley=False, alpha=False, alphas=0):
        """`volley`: they charge and fire together (Gardiens II); `alpha`: the Alpha Guardian comes too, in the middle
        (Gardiens III); `alphas`: that many Alphas, side by side in the middle (BONUS FINAL - Gardiens)."""
        self.volley = bool(volley)
        self.count = int(count)
        self.sounds = sounds
        self.clock = 0.0
        self.next_charge = SQUAD_ENTRY + 1.2
        self.next_fire = 0.0
        self.effects = []
        self.burned = 0
        self.bullets = []                    # (the formation's, set by tick)
        self.guardians = []
        big = max(int(alphas or 0), 1 if alpha else 0)
        n = self.count + big
        first = n // 2 if big == 1 else (n - big) // 2            # (the Alphas: in the middle of the row)
        for i in range(n):
            kind = AlphaGuardian if first <= i < first + big else Guardian
            g = kind(BASE_WIDTH * (i + 1) / (n + 1), y, i, squad=n)
            if kind is AlphaGuardian:
                g.home_y = y + ALPHA_DROP
            g.owner_id = ("guardian", i)             # (its lasers: never mistaken for a bird's shots)
            g.y = -90.0 - i * 40.0
            g.state = "recover"                          # (flying to its place: they come down from the top)
            g.entry = SQUAD_ENTRY + i * SQUAD_STEP
            g.shot_wait = SHOT_GAP + 1.0 + i * 0.38
            g.dive_wait = 6.0 + i * 1.6
            self.guardians.append(g)

    def targets(self):
        """The Guardians the shots can hit (and that hit the ship when they dive)."""
        return [g for g in self.guardians if g.alive and not g.dying and g.entry <= 0]

    def alive(self):
        return [g for g in self.guardians if g.alive]

    def clear(self):
        """True when every Guardian is down (the wave can end)."""
        return not any(g.alive for g in self.guardians)

    def kill_all(self):
        for g in self.guardians:
            if g.alive:
                g.kill()

    def tick(self, dt, player_x, player_y, bullets, birds):
        """One step: the Guardians fly in, patrol, charge, fire into `bullets` (the formation's), dive; their lasers burn
        the `birds` they cross."""
        self.clock += dt
        self.bullets = bullets
        held = {id(b) for b in bullets}
        for g in self.guardians:                         # a laser dropped from the list (the shots cleared): let go of it
            if g.emission is not None and id(g.emission) not in held:
                g.emission = None
        for effect in self.effects:
            effect.update(dt)
        self.effects = [e for e in self.effects if e.alive]
        previous = {bird: bird.get_hitbox() for bird in birds if bird.alive and not bird.dying}
        for g in self.guardians:
            if g.entry > 0:
                g.entry -= dt
                continue
            if g.alive:
                g.update(dt, player_x, player_y)
            else:
                g.tick_fx(dt)
        flying = [g for g in self.guardians if g.entry <= 0]
        keep = self.guardians
        self.guardians = flying
        try:
            guardian_attacks(self, dt, player_x, player_y)
        finally:
            self.guardians = keep
        self.burned += burn_birds(self, birds, previous)

    def draw(self, surface):
        for g in self.guardians:
            if g.entry <= 0:
                g.draw(surface)
        for effect in self.effects:
            effect.draw(surface)


def squad(game):
    """The Guardians of the wave in play, or None (src/game.py sets game.guardian_squad)."""
    return getattr(game, "guardian_squad", None)


def targets(game):
    """The enemies the shots of the ship can hit: those of the formation, then the Guardians of the wave."""
    out = list(game.formation.get_hittable_enemies())
    sq = squad(game)
    if sq is not None:
        out += sq.targets()
    return out
