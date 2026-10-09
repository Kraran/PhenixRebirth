"""
Space Invaders clone for the Adventure paint missions.

A grid of 4 rows x 11 of our own enemies marches in step, left and right; when one touches a wall the
whole grid drops one line and turns back. Bottom to top: blue birds, khaki birds, gargoyles, dark
gargoyles (the enemies 1, 2, 3 and 4). Now and then a miniature of the boss saucer crosses the top of the
screen: it is worth 500 to 1000 points, the more the shot that kills it is centred, the more it gives.

The formation looks like `enemy.EnemyFormation` for the rest of the game (enemies, bullets, update, draw,
all_dead), so the shots, the scoring and the stage clear of the arcade code work unchanged.
"""
import os
import random

import pygame

from settings import BASE_HEIGHT, BASE_WIDTH, asset_path
from enemy import Enemy, EnemyBullet

COLS = 11
ROW_KINDS = (4, 3, 2, 1)              # top to bottom: dark gargoyles, gargoyles, khaki birds, blue birds
SPACING_X = 66
SPACING_Y = 46
STEP_PX = 14                          # one step of the march
DROP_PX = 22                          # one line down when a wall is touched
WALL_LEFT = 24
WALL_RIGHT = BASE_WIDTH - 24
START_Y = 130                         # centre of the top row at level 1
START_ROWS = 3                        # the 1st, 2nd, 3rd mission of a pass start 0, 1, 2 lines lower (then again)
FLAP_PERIOD = 0.3                     # seconds per wing position (all together, whatever the pace of the march)
INVASION_Y = 540                      # an enemy whose feet reach this line has invaded: the ship is lost
START_DELAY = 1.2                     # the march (and the shooting) starts after the ship has arrived

BASE_INTERVAL = 0.34                  # seconds between two steps with the whole grid alive (level 1)
LEVEL_INTERVAL = 0.9                  # each level: x 0.9
MIN_INTERVAL = 0.12
LAST_ONE_SHARE = 0.14                 # interval share when one enemy is left (the rest scales with the count)

SHOT_GAP = (0.9, 1.8)                 # seconds between two enemy shots at level 1 (x 0.9 per level, 0.35 min)
SHOT_AIM = 0.35                       # chance that a shot comes from the column facing the ship
BULLET_PAUSE_MIN = 0.35

SAUCER_GAP = (14.0, 22.0)             # seconds between two passes of the miniature saucer
SAUCER_SPEED = 170.0
SAUCER_Y = 88
SAUCER_W, SAUCER_H = 52, 37
SAUCER_HIT_W = 44                     # the width over which a shot counts as centred
SAUCER_MIN, SAUCER_MAX = 500, 1000
SAUCER_PASS = (BASE_WIDTH + 1.5 * SAUCER_W) / SAUCER_SPEED     # seconds the saucer takes to cross the screen
STEP_PITCHES = 11                     # the step sound exists in this many pitches...
STEP_PITCH_GAP = 0.025                # ...each this much higher (a fraction of the pitch) than the one before
STEP_PITCH_PER_SPEED = 0.03           # a march twice as fast as the first one: 3 % higher

_CACHE = {}


def _load(name):
    try:
        return pygame.image.load(asset_path("sprites", name)).convert_alpha()
    except Exception:
        return None


def _bird_frames(kind):
    """Two wing positions of the blue (kind 1) or khaki (kind 2) bird."""
    prefix = "bird2" if kind == 2 else "bird1"
    frames = [_load(f"{prefix}_flap0.png"), _load(f"{prefix}_flap1.png")]
    if any(f is None for f in frames):
        frames = [pygame.Surface((38, 36), pygame.SRCALPHA) for _ in range(2)]
        for f in frames:
            f.fill((60, 120, 230) if kind == 1 else (110, 170, 60))
    return frames


GARG_WIDTH = 56
WING_OVERLAP = 14


def _gargoyle_frames(kind):
    """Two wing positions of a gargoyle (kind 3) or a dark gargoyle (kind 4), shrunk to bird size."""
    prefix = "garg4" if kind >= 4 else "garg3"
    body = _load(f"{prefix}_body.png")
    ups = _load(f"{prefix}_wing_up.png")
    down = _load(f"{prefix}_wing_down.png")
    if body is None or ups is None or down is None:
        return _bird_frames(2)
    frames = []
    bw, bh = body.get_size()
    for pose, wing in enumerate((ups, down)):
        ww, wh = wing.get_size()
        # the flap must read at this size: wings raised and stretched, then lowered and squashed
        wing = pygame.transform.smoothscale(wing, (ww, int(wh * (1.0 if pose == 0 else 0.6))))
        wh = wing.get_height()
        width = bw + 2 * (ww - WING_OVERLAP)
        sheet = pygame.Surface((width, bh + 14), pygame.SRCALPHA)
        wy = 0 if pose == 0 else int(bh * 0.45)
        sheet.blit(wing, (0, wy))                                         # the wings go behind the body
        sheet.blit(pygame.transform.flip(wing, True, False), (width - ww, wy))
        sheet.blit(body, ((width - bw) // 2, 7))
        scale = GARG_WIDTH / width
        frames.append(pygame.transform.smoothscale(sheet, (GARG_WIDTH, max(1, int(sheet.get_height() * scale)))))
    return frames


def frames_for(kind):
    """The two animation frames of an enemy kind (1..4), built once."""
    kind = max(1, min(4, int(kind)))
    key = ("frames", kind)
    if key not in _CACHE:
        _CACHE[key] = _bird_frames(kind) if kind <= 2 else _gargoyle_frames(kind)
    return _CACHE[key]


SAUCER_BLINK = 0.25                   # seconds per position of the lights under the saucer


def _saucer_frame(lit):
    """The miniature saucer, bright on purpose: the old dark boss sprite was lost against the night sky (and
    under the score), so a shot could kill it unseen. `lit` picks which of the two light sets is on."""
    w, h = SAUCER_W, SAUCER_H
    img = pygame.Surface((w, h), pygame.SRCALPHA)
    halo = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(halo, (255, 70, 90, 70), pygame.Rect(0, 8, w, h - 10))
    img.blit(halo, (0, 0))
    pygame.draw.ellipse(img, (255, 235, 240), pygame.Rect(w // 2 - 13, 2, 26, 22))              # glass dome
    pygame.draw.ellipse(img, (255, 150, 170), pygame.Rect(w // 2 - 11, 4, 22, 18))
    pygame.draw.ellipse(img, (255, 255, 255), pygame.Rect(w // 2 - 7, 6, 8, 6))                 # its shine
    body = pygame.Rect(1, 14, w - 2, 18)
    pygame.draw.ellipse(img, (255, 235, 240), body)                                             # light rim
    pygame.draw.ellipse(img, (225, 40, 70), body.inflate(-4, -4))                               # red hull
    pygame.draw.ellipse(img, (255, 110, 120), pygame.Rect(8, 16, w - 16, 5))                    # top gleam
    for i in range(5):
        on = (i + lit) % 2 == 0
        pygame.draw.circle(img, (255, 235, 90) if on else (110, 20, 40), (9 + i * 8, 24), 2)
    return img


def saucer_frames():
    if "saucer" not in _CACHE:
        _CACHE["saucer"] = (_saucer_frame(0), _saucer_frame(1))
    return _CACHE["saucer"]


def saucer_image(frame=0):
    return saucer_frames()[frame % 2]


def level_interval(level):
    """Seconds between two steps with the whole grid alive."""
    return max(MIN_INTERVAL, BASE_INTERVAL * LEVEL_INTERVAL ** (max(1, int(level)) - 1))


def step_pitch_index(interval):
    """Which pitch of the step sound for a march with `interval` seconds between two steps: the first pace of
    level 1 is the plain sound, a faster march is very slightly higher (never more than a quarter higher)."""
    speed = BASE_INTERVAL / max(0.001, float(interval))
    k = round(STEP_PITCH_PER_SPEED * (speed - 1.0) / STEP_PITCH_GAP)
    return max(0, min(STEP_PITCHES - 1, int(k)))


def level_start_y(level):
    """Level 1 starts at the top, level 2 one line (a row of the grid) lower, level 3 two lines lower;
    levels 4, 5, 6 start like 1, 2, 3 (they are harder by their speed and their shots)."""
    return START_Y + SPACING_Y * ((max(1, int(level)) - 1) % START_ROWS)


def level_shot_gap(level):
    f = max(BULLET_PAUSE_MIN / SHOT_GAP[0], 0.9 ** (max(1, int(level)) - 1))
    return SHOT_GAP[0] * f, SHOT_GAP[1] * f


def level_max_bullets(level):
    return min(5, 2 + (max(1, int(level)) - 1) // 2)


def saucer_points(shot_x, saucer_x):
    """500 for a shot on the very edge of the saucer, 1000 for a shot in the middle, in proportion."""
    off = abs(float(shot_x) - float(saucer_x)) / (SAUCER_HIT_W / 2.0)
    return int(round(SAUCER_MIN + (SAUCER_MAX - SAUCER_MIN) * max(0.0, 1.0 - off)))


class Invader(Enemy):
    """One enemy of the grid. Dying, drawing and killing are the arcade enemy's own."""

    def __init__(self, x, y, kind, col, row):          # noqa: super().__init__ builds a bird we do not want
        self.x = float(x)
        self.y = float(y)
        self.start_x = self.x
        self.start_y = self.y
        self.stage = int(kind)
        self.col = col
        self.row = row
        self.formation_index = row * COLS + col
        self.alive = True
        self.dying = False
        self.death_timer = 0.0
        self.DEATH_DURATION = 0.24
        self.death_flash = False
        self._white_image = None
        self.hit_flash_frames = 0
        self.time = 0.0
        self.anim_t = 0.0
        self.state = "formation"
        self.shoot_cooldown = 0.0
        self.active_shots = 0
        self.speed_mult = 1.0
        self.frames = frames_for(kind)
        self.image = self.frames[0]
        self.width = self.image.get_width()
        self.height = self.image.get_height()
        if kind >= 3:
            self.hitbox_w, self.hitbox_h = 42, 24
        else:
            self.hitbox_w, self.hitbox_h = 30, 28
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def set_frame(self, i):
        self.image = self.frames[i % len(self.frames)]

    def update(self, dt, formation_offset_x=0.0, player_x=0.0):
        """Only the end of the enemy is animated here; the march belongs to the formation."""
        if not self.alive:
            return
        if self.dying:
            if int(self.hit_flash_frames or 0) > 0:
                self.hit_flash_frames -= 1
                return
            self.death_timer += dt
            self.death_flash = (int(self.death_timer * 20) % 2) == 0
            if self.death_timer >= self.DEATH_DURATION:
                self.alive = False
                self.dying = False
        self.rect.center = (int(self.x), int(self.y))


class Mothership:
    """The miniature boss saucer that crosses the top of the screen."""

    def __init__(self, direction):
        self.image = saucer_image()
        self.width, self.height = self.image.get_size()
        self.age = 0.0
        self.direction = 1 if direction >= 0 else -1
        self.x = -self.width / 2 if self.direction > 0 else BASE_WIDTH + self.width / 2
        self.y = float(SAUCER_Y)
        self.alive = True
        self.dying = False
        self.death_timer = 0.0

    def update(self, dt):
        if not self.alive:
            return
        if self.dying:
            self.death_timer += dt
            if self.death_timer >= 0.3:
                self.alive = False
            return
        self.age += dt
        self.x += self.direction * SAUCER_SPEED * dt
        if (self.direction > 0 and self.x > BASE_WIDTH + self.width) or \
                (self.direction < 0 and self.x < -self.width):
            self.alive = False

    def kill(self):
        if self.alive and not self.dying:
            self.dying = True
            self.death_timer = 0.0

    def on_screen(self):
        """A shot only counts on a saucer the player can see: its centre is inside the screen."""
        return 0 <= self.x <= BASE_WIDTH

    def get_hitbox(self):
        if not self.alive or self.dying or not self.on_screen():
            return pygame.Rect(0, 0, 0, 0)
        return pygame.Rect(int(self.x - SAUCER_HIT_W / 2), int(self.y - self.height / 2), SAUCER_HIT_W, self.height)

    def draw(self, surface):
        if not self.alive:
            return
        img = saucer_image(int(self.age / SAUCER_BLINK))
        if self.dying:
            img = img.copy()            # never touch the shared picture: its fade would stay on every later saucer
            if int(self.death_timer * 20) % 2 == 0:
                img.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGB_ADD)
            img.set_alpha(max(0, int(255 * (1.0 - self.death_timer / 0.3))))
        surface.blit(img, (int(self.x - self.width / 2), int(self.y - self.height / 2)))


class InvaderFormation:
    """The grid, its shots and the saucer. Same outside face as `enemy.EnemyFormation`."""

    def __init__(self, level=1, speed_mult=1.0):
        self.level = max(1, int(level))
        self.speed_mult = float(speed_mult or 1.0)
        self.enemies = []
        self.bullets = []
        self.offset_x = 0.0
        self.direction = 1
        self.speed = 0.0
        self.time = 0.0
        self.stage = 1
        self.sounds = None
        self.swarm = None
        self.font = None
        self.mothership = None
        self.popups = []                   # [x, y, text, age] points shown where the saucer fell
        self.invaded = False
        self.frame = 0
        self.steps = 0
        self.step_timer = 0.0
        self.delay = START_DELAY
        self.shot_timer = random.uniform(*level_shot_gap(self.level))
        self.saucer_timer = random.uniform(*SAUCER_GAP)
        self.total = COLS * len(ROW_KINDS)
        self.spawn()

    # --- the grid ---
    def spawn(self):
        self.enemies = []
        self.bullets = []
        start_x = (BASE_WIDTH - (COLS - 1) * SPACING_X) / 2
        y0 = level_start_y(self.level)
        for row, kind in enumerate(ROW_KINDS):
            for col in range(COLS):
                e = Invader(start_x + col * SPACING_X, y0 + row * SPACING_Y, kind, col, row)
                e.speed_mult = self.speed_mult
                self.enemies.append(e)
        self.total = len(self.enemies)

    def living(self):
        return [e for e in self.enemies if e.alive and not e.dying]

    def interval(self):
        """Time between two steps: the fewer enemies are left, the faster the march."""
        n = len(self.living())
        share = LAST_ONE_SHARE + (1.0 - LAST_ONE_SHARE) * (n - 1) / max(1, self.total - 1)
        return max(0.02, level_interval(self.level) * max(LAST_ONE_SHARE, share) / self.speed_mult)

    def _step(self):
        alive = self.living()
        if not alive:
            return
        lo = min(e.x - e.width / 2 for e in alive)
        hi = max(e.x + e.width / 2 for e in alive)
        dx = self.direction * STEP_PX
        if lo + dx < WALL_LEFT or hi + dx > WALL_RIGHT:
            for e in self.enemies:
                e.y += DROP_PX                 # one line down, all together, then the other way
            self.direction = -self.direction
        else:
            for e in self.enemies:
                e.x += dx
        self.steps += 1
        if self.sounds:
            lo = min(e.x - e.width / 2 for e in alive)
            hi = max(e.x + e.width / 2 for e in alive)
            self.sounds.play("invader_step_%d" % step_pitch_index(self.interval()), x=(lo + hi) / 2)     # centre of the group
        if max(e.y + e.height / 2 for e in alive) >= INVASION_Y:
            self.invaded = True

    # --- shots ---
    def _front_row(self):
        """The lowest living enemy of each column."""
        front = {}
        for e in self.living():
            if e.col not in front or e.row > front[e.col].row:
                front[e.col] = e
        return front

    def _shoot(self, player_x):
        front = self._front_row()
        if not front:
            return
        if random.random() < SHOT_AIM:
            shooter = min(front.values(), key=lambda e: abs(e.x - player_x))
        else:
            shooter = random.choice(list(front.values()))
        bullet = EnemyBullet(shooter.x, shooter.y + shooter.height / 2, stage=shooter.stage)
        bullet.owner_id = id(shooter)
        self.bullets.append(bullet)
        if self.sounds:
            self.sounds.play("enemy_shoot", x=shooter.x)

    # --- the saucer ---
    def mothership_hit(self, shot_x):
        """The player's shot reached the saucer: points by how centred it was (0 when there is none)."""
        m = self.mothership
        if m is None or not m.alive or m.dying:
            return 0
        pts = saucer_points(shot_x, m.x)
        m.kill()
        if self.sounds:
            self.sounds.stop_sfx("saucer_pass", 150)
        self.popups.append([m.x, m.y, str(pts), 0.0])
        return pts

    # --- frame ---
    def update(self, dt, player_x):
        self.time += dt
        frame = int(self.time / FLAP_PERIOD) % 2
        if frame != self.frame:
            self.frame = frame
            for e in self.enemies:
                e.set_frame(frame)
        for e in self.enemies:
            e.update(dt)
        for p in self.popups:
            p[3] += dt
        self.popups = [p for p in self.popups if p[3] < 1.2]
        if self.mothership is not None:
            self.mothership.update(dt)
            if not self.mothership.alive:
                self.mothership = None
        for bullet in self.bullets[:]:
            bullet.update(dt)
            if not bullet.alive:
                self.bullets.remove(bullet)
        if any((not e.alive and not e.dying) for e in self.enemies):
            self.enemies = [e for e in self.enemies if e.alive or e.dying]
        if self.delay > 0:
            self.delay -= dt
            return
        if not self.living():
            return
        self.step_timer += dt
        interval = self.interval()
        if self.step_timer >= interval:
            self.step_timer = 0.0
            self._step()
        self.shot_timer -= dt
        if self.shot_timer <= 0:
            lo, hi = level_shot_gap(self.level)
            self.shot_timer = random.uniform(lo, hi) / self.speed_mult
            if sum(1 for b in self.bullets if b.alive) < level_max_bullets(self.level):
                self._shoot(player_x)
        if self.mothership is None:
            self.saucer_timer -= dt
            if self.saucer_timer <= 0 and len(self.living()) > 1:
                self.mothership = Mothership(random.choice((-1, 1)))
                if self.sounds:
                    self.sounds.play_voice("saucer_pass", x=self.mothership.x)
                self.saucer_timer = random.uniform(*SAUCER_GAP)

    def draw(self, surface):
        for e in self.enemies:
            if e.alive or e.dying:
                e.draw(surface)
        if self.mothership is not None:
            self.mothership.draw(surface)
        for bullet in self.bullets:
            if bullet.alive:
                bullet.draw(surface)
        if self.font is not None:
            for x, y, text, age in self.popups:
                label = self.font.render(text, True, (255, 230, 120))
                surface.blit(label, (int(x - label.get_width() / 2), int(y - label.get_height() / 2 - age * 24)))

    # --- what the rest of the game asks of a formation ---
    def get_alive_enemies(self):
        return [e for e in self.enemies if e.alive]

    def get_hittable_enemies(self):
        return [e for e in self.enemies if e.alive and not e.dying]

    def all_dead(self):
        return not any(e.alive for e in self.enemies)

    def remaining(self):
        return len(self.get_alive_enemies())

    def swarm_remaining(self):
        return 0
