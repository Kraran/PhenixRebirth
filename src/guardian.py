"""Sentinelle test encounter: telegraphed, finite fire-laser bolts.

The formation implements the ordinary enemy/bullet interface. Its timing is in
seconds and independent of adventure act, difficulty and arcade random state.
"""
import math

import pygame

from settings import BASE_HEIGHT, BASE_WIDTH, asset_path

CHARGE_SECONDS = 0.95
LASER_SPEED = 260.0
LASER_LENGTH = 144
LASER_WIDTH = 10
SHOT_GAP = 1.1
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
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.origin_y = self.y
        self.prev_y = self.y
        self.alive = True

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
    diving = False
    width = 116
    height = 100

    def __init__(self, x, y, index):
        self.x, self.y = float(x), float(y)
        self.home_x = self.x
        self.index = index
        self.time = 0.0
        self.move_time = 0.0
        self.x += math.sin(index) * 70
        self.alive = True
        self.dying = False
        self.charge = 0.0
        self.firing = 0.0
        self.frames = art()[0]

    def update(self, dt):
        self.time += dt
        self.firing = max(0.0, self.firing - dt)
        if not self.charge:
            self.move_time += dt
            self.x = self.home_x + math.sin(self.move_time * 0.7 + self.index) * 70

    def get_hitbox(self):
        # The solid body is the target, not the translucent wing tips.
        return pygame.Rect(round(self.x - 24), round(self.y - 19), 48, 58)

    def kill(self, flash=True):
        self.alive = False
        self.dying = False
        self.charge = 0.0

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
        self.shooter = None
        self.shot_wait = SHOT_GAP
        self.destroyed = 0
        self._spawn()

    def _spawn(self):
        self.wave += 1
        self.enemies = [Guardian(BASE_WIDTH * (i + 1) / 4, 150 + (self.wave - 1) * 35, i)
                        for i in range(PER_WAVE)]

    def update(self, dt, player_x):
        for bolt in self.bullets:
            bolt.update(dt)
        self.bullets = [bolt for bolt in self.bullets if bolt.alive]
        for bird in self.enemies:
            if bird.alive:
                bird.update(dt)
        living = self.get_alive_enemies()
        self.destroyed = (self.wave - 1) * PER_WAVE + PER_WAVE - len(living)
        if not living:
            self.shooter = None
            if self.wave < self.waves and not self.bullets:
                self.wait -= dt
                if self.wait <= 0:
                    self._spawn()
                    self.wait = 1.5
                    self.shot_wait = SHOT_GAP
            return
        if self.shooter is not None:
            if not self.shooter.alive:
                self.shooter = None
                self.shot_wait = SHOT_GAP
                return
            self.shooter.charge += dt
            if self.shooter.charge >= CHARGE_SECONDS:
                bird = self.shooter
                self.bullets.append(FireLaser(bird.x, bird.y + 16))
                bird.charge = 0.0
                bird.firing = 0.2
                if self.sounds:
                    self.sounds.play("enemy_shoot", x=bird.x)
                self.shooter = None
                self.shot_wait = SHOT_GAP
            return
        if not self.bullets:
            self.shot_wait -= dt
            if self.shot_wait <= 0:
                self.shooter = min(living, key=lambda bird: abs(bird.x - player_x))
                self.shooter.charge = 1e-9

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
