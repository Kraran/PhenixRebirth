"""Sentinelle test encounter: telegraphed, finite fire-laser bolts.

The formation implements the ordinary enemy/bullet interface. Its timing is in
seconds and independent of adventure act, difficulty and arcade random state.
"""
import math
import random

import pygame

import fire_death
from enemy import Enemy, EnemyBullet

from settings import BASE_HEIGHT, BASE_WIDTH, ENEMY_DIVE_SPEED, asset_path

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
WAVES = 1
PER_WAVE = 5
BIRDS_PER_COLOUR = 5
_ART = None


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


class FireLaser:
    """A detached downward bolt, not a hitscan beam or a homing projectile."""
    def __init__(self, x, y, owner_id=None):
        self.x, self.y = float(x), float(y)
        self.origin_y = self.y
        self.prev_y = self.y
        self.alive = True
        self.owner_id = owner_id
        self.age = 0.0

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
                           LASER_WIDTH, max(1, math.ceil(self.y - top)))

    def hits_moving_rect(self, previous, current):
        """Continuous overlap with a moving bird, including the growing tail."""
        # Each gap must be nonnegative at the same time in this tick.
        # tail=max(origin, tip-length), so both tail constraints must hold.
        gaps = (
            (previous.right - (self.x - LASER_WIDTH / 2),
             current.right - (self.x - LASER_WIDTH / 2)),
            (self.x + LASER_WIDTH / 2 - previous.left,
             self.x + LASER_WIDTH / 2 - current.left),
            (self.prev_y - previous.top, self.y - current.top),
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
        self.emission = None
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

    @property
    def laser_attached(self):
        """The bolt's growing tail still touches its emission point."""
        bolt = self.emission
        return (bolt is not None and bolt.alive
                and bolt.y - bolt.origin_y <= LASER_LENGTH)

    def start_dive(self, player_x, player_y):
        if self.laser_attached:
            return
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
            aim = self.home_x if player_x is None else player_x + (self.index - (PER_WAVE - 1) / 2) * 150
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


# Burning frames are prepared once per colour, never transformed during draw.
BURN_SECONDS = 1.35
BURN_FRAME_COUNT = 28
_BIRD_ART = {}
_BURN_ART = {}


def burning_frames(stage, source):
    """Ignition, flames, charred silhouette, then the ash scattered by the wind (src/fire_death.py)."""
    if stage in _BURN_ART:
        return _BURN_ART[stage]
    size = max(128, source.get_width() + 64, source.get_height() + 64)
    origin = ((size - source.get_width()) // 2, (size - source.get_height()) // 2)
    _BURN_ART[stage] = fire_death.frames(source, BURN_FRAME_COUNT, fire_death.BIRD, (size, size), origin)
    return _BURN_ART[stage]


class BurningBird:
    def __init__(self, bird):
        self.x, self.y = bird.x, bird.y
        self.frames = burning_frames(bird.stage, bird.frames[0])
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


class EscortBird(Enemy):
    """Ordinary blue/green birds, with local deterministic attack timings."""
    def _load_bird_frames(self, stage=1):
        if stage not in _BIRD_ART:
            _BIRD_ART[stage] = super()._load_bird_frames(stage)
        return _BIRD_ART[stage]

    def __init__(self, x, y, index, stage):
        rng_state = random.getstate()
        try:
            super().__init__(x, y, formation_index=index, stage=stage)
        finally:
            random.setstate(rng_state)
        self.owner_id = ("bird", index)
        self.anim_phase = index * 0.73
        self.flap_rate = 5.2
        self.glow_period = 2.0
        self.glow_len = 0.35
        self.attack_wait = 3.2 + index * 0.43
        self.shot_wait = 2.0 + index * 0.27
        burning_frames(stage, self.frames[0])

    def update_encounter(self, dt, clock, player_x):
        self.attack_wait = max(0.0, self.attack_wait - dt)
        self.shot_wait = max(0.0, self.shot_wait - dt)
        if not self.dying and self.attack_wait <= 0 and self.state == "formation":
            # Own lanes prevent all ten birds from stacking on the ship.
            self.state = "diving"
            self.dive_lane = max(28, min(BASE_WIDTH - 28, player_x + (self.formation_index % 5 - 2) * 90))
            self.dive_target_x = self.dive_lane
            self.attack_wait = 6.0 + self.formation_index * 0.2
        # The base bird animation/death remains unchanged. Its random dive wrap
        # is replaced here so this encounter never consumes arcade RNG per tick.
        if self.state == "diving" and not self.dying:
            self._tick_wings(dt)
            self.y += ENEMY_DIVE_SPEED * dt
            self.x += (self.dive_lane - self.x) * 0.55 * dt
            self.x += math.sin(self.time * 5.5 + self.formation_index) * 36 * dt
            self.x = max(20, min(BASE_WIDTH - 20, self.x))
            if self.y > BASE_HEIGHT + 50:
                self.y = -40
                self.state = "returning"
            self.rect.center = (round(self.x), round(self.y))
        else:
            super().update(dt, math.sin(clock * 0.7) * 45, player_x)


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
        self.burned = 0
        self.effects = []
        self._spawn()

    def _spawn(self):
        self.wave += 1
        self.guardians = [Guardian(BASE_WIDTH * (i + 1) / (PER_WAVE + 1), 130, i)
                          for i in range(PER_WAVE)]
        self.birds = [EscortBird(BASE_WIDTH * (i + 1) / (BIRDS_PER_COLOUR + 1),
                                 250 + (stage - 1) * 85,
                                 (stage - 1) * BIRDS_PER_COLOUR + i, stage)
                      for stage in (1, 2) for i in range(BIRDS_PER_COLOUR)]
        self.enemies = self.guardians + self.birds

    @property
    def total(self):
        return PER_WAVE + BIRDS_PER_COLOUR * 2

    def _burn_birds(self, previous_boxes):
        for bolt in self.bullets:
            if not isinstance(bolt, FireLaser):
                continue
            # A bolt leaving the screen can still cross a bird this tick.
            for bird in self.birds:
                if not bird.alive or bird.dying:
                    continue
                current = bird.get_hitbox()
                previous = previous_boxes.get(bird, current)
                # Wrapping from below to above is a teleport, not a sweep
                # through every laser on screen.
                if abs(previous.centery - current.centery) > BASE_HEIGHT / 2:
                    previous = current
                if bolt.hits_moving_rect(previous, current):
                    self.effects.append(BurningBird(bird))
                    bird.kill(flash=False)
                    self.burned += 1
                    if self.sounds:
                        self.sounds.play("enemy_explosion", volume=0.35, x=bird.x)

    def update(self, dt, player_x, player_y=BASE_HEIGHT - 95):
        self.clock += dt
        for effect in self.effects:
            effect.update(dt)
        self.effects = [effect for effect in self.effects if effect.alive]
        previous_boxes = {bird: bird.get_hitbox() for bird in self.birds
                          if bird.alive and not bird.dying}
        self.bullets = [bolt for bolt in self.bullets if bolt.alive]
        for bolt in self.bullets:
            bolt.update(dt)
        for bird in self.guardians:
            if bird.alive:
                bird.update(dt, player_x, player_y)
        for bird in self.birds:
            if bird.alive:
                bird.update_encounter(dt, self.clock, player_x)
        self._burn_birds(previous_boxes)
        self.bullets = [bolt for bolt in self.bullets if bolt.alive]
        self.destroyed = self.total - len(self.get_alive_enemies())
        living = [bird for bird in self.guardians if bird.alive]
        for bird in self.birds:
            if (bird.alive and not bird.dying and bird.shot_wait <= 0
                    and 0 < bird.y < player_y - 50
                    and not any(b.owner_id == bird.owner_id for b in self.bullets)):
                bolt = EnemyBullet(bird.x, bird.y + bird.height / 2, stage=bird.stage)
                bolt.owner_id = bird.owner_id
                self.bullets.append(bolt)
                bird.shot_wait = 2.4 + bird.formation_index * 0.1
        for bird in living:
            active = any(b.owner_id == bird.owner_id for b in self.bullets)
            if bird.charge:
                bird.charge += dt
                if bird.charge >= CHARGE_SECONDS and self.clock >= self.next_fire and not active:
                    bird.emission = FireLaser(bird.x, bird.y + 16, bird.owner_id)
                    self.bullets.append(bird.emission)
                    bird.charge = 0.0
                    bird.firing = 0.2
                    bird.shot_wait = SHOT_GAP + bird.index * 0.15
                    self.next_fire = self.clock + FIRE_STAGGER
                    if self.sounds:
                        self.sounds.play("enemy_shoot", x=bird.x)
                continue
            if bird.state != "patrol" or bird.laser_attached:
                continue
            if bird.dive_wait <= 0 and not any(b.state in ("windup", "dive") for b in living):
                bird.start_dive(player_x, player_y)
            elif not active and bird.shot_wait <= 0 and self.clock >= self.next_charge:
                bird.charge = 1e-9
                self.next_charge = self.clock + CHARGE_STAGGER

    def draw(self, surface):
        for bird in self.enemies:
            bird.draw(surface)
        for effect in self.effects:
            effect.draw(surface)
        for bolt in self.bullets:
            bolt.draw(surface)

    def get_alive_enemies(self):
        return [bird for bird in self.enemies if bird.alive and not bird.dying]

    def get_hittable_enemies(self):
        return self.get_alive_enemies()

    def all_dead(self):
        return (not any(b.alive for b in self.enemies) and not self.effects
                and not any(b.alive for b in self.bullets))
