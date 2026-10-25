"""Sentinelle test encounter: telegraphed, finite fire-laser bolts.

The formation implements the ordinary enemy/bullet interface. Its timing is in
seconds and independent of adventure act, difficulty and arcade random state.
"""
import math

import pygame

from settings import BASE_HEIGHT, BASE_WIDTH, asset_path

CHARGE_SECONDS = 0.95
LASER_SPEED = 780.0
LASER_LENGTH = 144
LASER_WIDTH = 10
SHOT_GAP = 1.1
CHARGE_STAGGER = 0.32
FIRE_STAGGER = 0.18
DIVE_WARNING = 0.55
DIVE_SPEED = 340.0
RETURN_SPEED = 300.0
WAVES = 2
PER_WAVE = 3
_ART = None


def art():
    global _ART
    if _ART is None:
        sheet = pygame.image.load(asset_path("sprites", "guardian", "sentinelle.png")).convert_alpha()
        frames = [[sheet.subsurface((i * 160, row * 160, 160, 160)).copy() for i in range(4)]
                  for row in range(2)]
        laser = pygame.image.load(asset_path("sprites", "guardian", "laser.png")).convert_alpha()
        _ART = frames, laser
    return _ART


class FireLaser:
    """A detached downward bolt, not a hitscan beam or a homing projectile."""
    def __init__(self, x, y, owner_id=None):
        self.x, self.y = float(x), float(y)
        self.origin_y = self.y
        self.prev_y = self.y
        self.alive = True
        self.owner_id = owner_id

    def update(self, dt):
        self.prev_y = self.y
        self.y += LASER_SPEED * dt
        if self.y - LASER_LENGTH > BASE_HEIGHT:
            self.alive = False

    def get_hitbox(self):
        # Swept bounds avoid tunnelling at a low frame rate. The tail never
        # extends behind the mouth when a bolt is first emitted.
        top = max(self.origin_y, self.prev_y - LASER_LENGTH)
        return pygame.Rect(round(self.x - LASER_WIDTH / 2), math.floor(top),
                           LASER_WIDTH, max(1, math.ceil(self.y - top)))

    def draw(self, surface):
        if not self.alive:
            return
        pic = art()[1]
        visible = min(LASER_LENGTH, max(0, int(self.y - self.origin_y)))
        if visible:
            surface.blit(pic, (round(self.x - pic.get_width() / 2), round(self.y - visible)),
                         (0, LASER_LENGTH - visible, pic.get_width(), visible))


class Guardian:
    stage = 3
    width = 116
    height = 100

    def __init__(self, x, y, index):
        self.x, self.y = float(x), float(y)
        self.home_x = self.x
        self.home_y = self.y
        self.index = index
        self.owner_id = index
        self.time = 0.0
        self.alive = True
        self.dying = False
        self.charge = 0.0
        self.firing = 0.0
        self.state = "patrol"
        self.shot_wait = SHOT_GAP + index * 0.38
        self.dive_wait = 4.6 + index * 1.2
        self.warning = 0.0
        self.target = None
        self.vx = self.vy = 0.0
        self.frames = art()[0]

    @property
    def diving(self):
        return self.alive and self.state == "dive"

    def start_dive(self, player_x, player_y):
        self.state = "windup"
        self.warning = DIVE_WARNING
        self.target = (max(96, min(BASE_WIDTH - 96, player_x)),
                       max(self.y + 180, min(BASE_HEIGHT - 48, player_y)))
        self.charge = 0.0
        self.dive_wait = 6.0 + self.index * 0.8

    def update(self, dt, player_x=None, player_y=BASE_HEIGHT - 95):
        self.time += dt
        self.firing = max(0.0, self.firing - dt)
        self.shot_wait = max(0.0, self.shot_wait - dt)
        self.dive_wait = max(0.0, self.dive_wait - dt)
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
            aim = self.home_x if player_x is None else player_x + (self.index - 1) * 150
            target_x = max(100, min(BASE_WIDTH - 100, aim + math.sin(self.time * 0.9 + self.index) * 65))
            target_y = self.home_y + math.sin(self.time * 0.7 + self.index) * 24
            self.x += max(-110 * dt, min(110 * dt, target_x - self.x))
            self.y += max(-45 * dt, min(45 * dt, target_y - self.y))

    def get_hitbox(self):
        # The solid body is the target, not the translucent wing tips.
        return pygame.Rect(round(self.x - 24), round(self.y - 19), 48, 58)

    def kill(self, flash=True):
        self.alive = False
        self.dying = False
        self.charge = 0.0
        self.state = "dead"

    def draw(self, surface):
        if not self.alive:
            return
        row = int(self.charge > 0 or self.firing > 0)
        frame = int(self.time * 8) % 4
        surface.blit(self.frames[row][frame], (round(self.x - 80), round(self.y - 80)))
        if self.charge:
            radius = 3 + int(6 * min(1, self.charge / CHARGE_SECONDS))
            pygame.draw.circle(surface, (255, 145, 35), (round(self.x), round(self.y + 16)), radius)
            pygame.draw.circle(surface, (255, 245, 180), (round(self.x), round(self.y + 16)), max(2, radius // 2))


class GuardianFormation:
    def __init__(self):
        self.enemies = []
        self.bullets = []
        self.sounds = None
        self.wave = 0
        self.waves = WAVES
        self.wait = 1.5
        self.clock = 0.0
        self.next_charge = 0.0
        self.next_fire = 0.0
        self.destroyed = 0
        self._spawn()

    def _spawn(self):
        self.wave += 1
        self.enemies = [Guardian(BASE_WIDTH * (i + 1) / 4, 150 + (self.wave - 1) * 35, i)
                        for i in range(PER_WAVE)]
        for bird in self.enemies:
            bird.owner_id = (self.wave - 1) * PER_WAVE + bird.index

    def update(self, dt, player_x, player_y=BASE_HEIGHT - 95):
        self.clock += dt
        for bolt in self.bullets:
            bolt.update(dt)
        self.bullets = [bolt for bolt in self.bullets if bolt.alive]
        for bird in self.enemies:
            if bird.alive:
                bird.update(dt, player_x, player_y)
        living = self.get_alive_enemies()
        self.destroyed = (self.wave - 1) * PER_WAVE + PER_WAVE - len(living)
        if not living:
            if self.wave < self.waves and not self.bullets:
                self.wait -= dt
                if self.wait <= 0:
                    self._spawn()
                    self.wait = 1.5
            return
        for bird in living:
            active = any(b.owner_id == bird.owner_id for b in self.bullets)
            if bird.charge:
                bird.charge += dt
                if bird.charge >= CHARGE_SECONDS and self.clock >= self.next_fire and not active:
                    self.bullets.append(FireLaser(bird.x, bird.y + 16, bird.owner_id))
                    bird.charge = 0.0
                    bird.firing = 0.2
                    bird.shot_wait = SHOT_GAP + bird.index * 0.15
                    self.next_fire = self.clock + FIRE_STAGGER
                    if self.sounds:
                        self.sounds.play("enemy_shoot", x=bird.x)
                continue
            if bird.state != "patrol":
                continue
            if bird.dive_wait <= 0 and not any(b.state in ("windup", "dive") for b in living):
                bird.start_dive(player_x, player_y)
            elif not active and bird.shot_wait <= 0 and self.clock >= self.next_charge:
                bird.charge = 1e-9
                self.next_charge = self.clock + CHARGE_STAGGER

    def draw(self, surface):
        for bird in self.enemies:
            bird.draw(surface)
        for bolt in self.bullets:
            bolt.draw(surface)

    def get_alive_enemies(self):
        return [bird for bird in self.enemies if bird.alive]

    def get_hittable_enemies(self):
        return self.get_alive_enemies()

    def all_dead(self):
        return self.wave >= self.waves and not self.get_alive_enemies() and not any(b.alive for b in self.bullets)
