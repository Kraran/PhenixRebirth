"""
Scrolling multi-layer starfield with parallax, planets, and nebulae.

Stars are procedural; planets use solar-system inspired art; nebulae use
Hubble-inspired assets. Usually one planet or one nebula; rarely both may share the screen.
"""
import pygame
import random
import os
import math
from settings import *

from settings import asset_path
NEBULA_DIR = asset_path("sprites", "nebulae")
PLANET_DIR = asset_path("sprites", "planets")

NEBULA_FILES = [
    "galaxy_andromeda.png",
    "galaxy_whirlpool.png",
    "galaxy_elliptical.png",
    "galaxy_blackhole.png",
    "galaxy_milkyway.png",
    "galaxy_collision.png",
    "nebula_orion.png",
    "nebula_helix.png",
    "nebula_dark.png",
]

PLANET_FILES = [
    "mercury.png",
    "venus.png",
    "earth.png",
    "mars.png",
    "jupiter.png",
    "fantasy_rings.png",
    "saturn.png",
    "uranus.png",
    "neptune.png",
]


class Star:
    __slots__ = (
        "layer", "x", "y", "size", "speed", "parallax", "color",
        "stamp", "ox", "oy",
    )

    def __init__(self, layer=0):
        self.layer = layer
        self.x = 0.0
        self.y = 0.0
        if layer == 0:
            self.size = random.choice([1, 1, 1, 2])
            self.speed = random.uniform(18, 35)
            self.parallax = 0.04
            self.color = random.choice([
                (40, 60, 140), (50, 70, 160), (30, 50, 120), (60, 80, 180)
            ])
        elif layer == 1:
            self.size = random.choice([1, 2, 2])
            self.speed = random.uniform(45, 75)
            self.parallax = 0.09
            self.color = random.choice([
                (80, 120, 220), (100, 140, 255), (70, 100, 200), (120, 160, 255)
            ])
        else:
            self.size = random.choice([2, 2, 3])
            self.speed = random.uniform(90, 140)
            self.parallax = 0.16
            self.color = random.choice([
                (160, 190, 255), (200, 220, 255), (140, 180, 255), (180, 210, 255)
            ])
        self.stamp = Star._stamp(self.size, self.color)
        self.ox = 0 if self.size <= 1 else self.size
        self.oy = self.ox
        self.reset(random_y=True)

    def reset(self, random_y=False):
        self.x = random.uniform(0, BASE_WIDTH)
        if random_y:
            self.y = random.uniform(0, BASE_HEIGHT)
        else:
            self.y = random.uniform(-20, -5)

    def update(self, dt, player_dx=0.0):
        self.y += self.speed * dt
        self.x -= player_dx * self.parallax

        if self.x < -5:
            self.x += BASE_WIDTH + 10
        elif self.x > BASE_WIDTH + 5:
            self.x -= BASE_WIDTH + 10

        if self.y > BASE_HEIGHT + 10:
            self.reset()

    # Shared stamps: (size, color) -> Surface
    _stamps = {}

    @classmethod
    def _stamp(cls, size, color):
        key = (size, color)
        s = cls._stamps.get(key)
        if s is not None:
            return s
        try:
            if size <= 1:
                s = pygame.Surface((1, 1))
                try:
                    s = s.convert()
                except Exception:
                    pass
                s.fill(color)
            else:
                d = size * 2 + 1
                s = pygame.Surface((d, d), pygame.SRCALPHA)
                pygame.draw.circle(s, color, (size, size), size)
                try:
                    s = s.convert_alpha()
                except Exception:
                    pass
        except Exception:
            s = pygame.Surface((max(1, size * 2 + 1), max(1, size * 2 + 1)))
            s.fill(color)
        cls._stamps[key] = s
        return s

    def draw(self, surface):
        surface.blit(self.stamp, (int(self.x) - self.ox, int(self.y) - self.oy))


class Planet:
    """Solar-system planet sprites — spawn above the top edge, scroll down."""

    _cache = {}

    def __init__(self):
        self.parallax = 0.08
        self.alive = True
        self.reset()

    @classmethod
    def _load_image(cls, filename):
        if filename not in cls._cache:
            path = os.path.join(PLANET_DIR, filename)
            img = pygame.image.load(path).convert_alpha()
            cls._cache[filename] = img
        return cls._cache[filename]

    def reset(self):
        filename = random.choice(PLANET_FILES)
        base = self._load_image(filename)
        # Ringed fantasy planet reads better a bit larger
        if "fantasy" in filename or "saturn" in filename:
            target_h = random.randint(48, 110)
        else:
            target_h = random.randint(36, 88)
        scale = target_h / max(1, base.get_height())
        w = max(1, int(base.get_width() * scale))
        h = max(1, int(base.get_height() * scale))
        self.image = pygame.transform.smoothscale(base, (w, h))
        if random.random() < 0.35:
            self.image = pygame.transform.flip(self.image, True, False)
        self.w = self.image.get_width()
        self.h = self.image.get_height()
        # Spawn fully above the top so the planet scrolls into view
        self.x = random.uniform(self.w // 2 + 40, BASE_WIDTH - self.w // 2 - 40)
        self.y = random.uniform(-self.h - 80, -self.h // 2 - 10)
        self.speed = random.uniform(14, 28)
        self.alive = True

    def update(self, dt, player_dx=0.0):
        self.y += self.speed * dt
        self.x -= player_dx * self.parallax
        if self.x < -self.w:
            self.x += BASE_WIDTH + self.w * 2
        elif self.x > BASE_WIDTH + self.w:
            self.x -= BASE_WIDTH + self.w * 2
        if self.y > BASE_HEIGHT + self.h:
            self.alive = False

    def draw(self, surface):
        surface.blit(
            self.image,
            (int(self.x - self.w // 2), int(self.y - self.h // 2)),
        )


class Galaxy:
    """Small distant galaxy / star cluster decoration."""

    def __init__(self):
        self.parallax = 0.03
        self.alive = True
        self.reset()

    def reset(self):
        self.x = random.uniform(40, BASE_WIDTH - 40)
        self.y = random.uniform(-30, -5)
        self.speed = random.uniform(8, 16)
        self.radius = random.randint(3, 7)
        self.color = random.choice([
            (80, 100, 160), (100, 80, 140), (60, 90, 150), (120, 100, 160)
        ])
        self.alive = True

    def update(self, dt, player_dx=0.0):
        self.y += self.speed * dt
        self.x -= player_dx * self.parallax
        if self.x < -20:
            self.x += BASE_WIDTH + 40
        elif self.x > BASE_WIDTH + 20:
            self.x -= BASE_WIDTH + 40
        if self.y > BASE_HEIGHT + 20:
            self.alive = False

    def draw(self, surface):
        pygame.draw.circle(
            surface, self.color,
            (int(self.x), int(self.y)), self.radius,
        )
        pygame.draw.circle(
            surface, (min(255, self.color[0] + 40), min(255, self.color[1] + 40), min(255, self.color[2] + 50)),
            (int(self.x), int(self.y)), max(1, self.radius // 2),
        )


class Nebula:
    """Hubble-inspired nebula / galaxy sprite — at most one on screen."""

    _cache = {}

    def __init__(self):
        self.parallax = 0.05
        self.alive = True
        self.reset()

    @classmethod
    def _load_image(cls, filename):
        if filename not in cls._cache:
            path = os.path.join(NEBULA_DIR, filename)
            img = pygame.image.load(path).convert_alpha()
            scale = random.uniform(0.55, 0.85)
            w = max(1, int(img.get_width() * scale))
            h = max(1, int(img.get_height() * scale))
            img = pygame.transform.smoothscale(img, (w, h))
            cls._cache[filename] = img
        return cls._cache[filename].copy()

    def reset(self):
        filename = random.choice(NEBULA_FILES)
        self.image = self._load_image(filename)
        if random.random() < 0.4:
            self.image = pygame.transform.flip(self.image, True, False)
        self.w = self.image.get_width()
        self.h = self.image.get_height()
        self.x = random.uniform(self.w // 2 + 40, BASE_WIDTH - self.w // 2 - 40)
        self.y = random.uniform(-self.h - 40, -self.h // 2)
        self.speed = random.uniform(12, 22)
        self.alive = True
        self._anim = 0.0

    def update(self, dt, player_dx=0.0):
        self.y += self.speed * dt
        self.x -= player_dx * self.parallax
        self._anim += dt
        if self.x < -self.w:
            self.x += BASE_WIDTH + self.w * 2
        elif self.x > BASE_WIDTH + self.w:
            self.x -= BASE_WIDTH + self.w * 2
        if self.y > BASE_HEIGHT + self.h:
            self.alive = False

    def draw(self, surface):
        # Pulse alpha on the instance surface — no per-frame copy
        alpha = int(200 + 40 * abs(math.sin(self._anim * 0.4)))
        self.image.set_alpha(alpha)
        surface.blit(self.image, (int(self.x - self.w // 2), int(self.y - self.h // 2)))


class Starfield:
    """Parallax star layers + occasional planet / nebula."""

    def __init__(self):
        self.stars = []
        for _ in range(STAR_FAR_COUNT):
            self.stars.append(Star(layer=0))
        for _ in range(STAR_MID_COUNT):
            self.stars.append(Star(layer=1))
        for _ in range(STAR_NEAR_COUNT):
            self.stars.append(Star(layer=2))
        self.stars_far = [s for s in self.stars if s.layer == 0]
        self.stars_mid = [s for s in self.stars if s.layer == 1]
        self.stars_near = [s for s in self.stars if s.layer == 2]
        for s in self.stars:
            Star._stamp(s.size, s.color)

        self.planets = []
        self.galaxies = []
        self.nebula = None

        if random.random() < 0.30:
            self.planets.append(Planet())
        if random.random() < 0.4:
            self.galaxies.append(Galaxy())

        # Planets slightly less common; nebulae a bit under planets
        self.planet_timer = random.uniform(16.0, 28.0)
        self.galaxy_timer = random.uniform(10.0, 18.0)
        self.nebula_timer = random.uniform(20.0, 36.0)

        self.last_player_x = BASE_WIDTH / 2

    def update(self, dt, player_x=None):
        player_dx = 0.0
        if player_x is not None:
            player_dx = player_x - self.last_player_x
            self.last_player_x = player_x

        for star in self.stars:
            star.update(dt, player_dx)

        for planet in self.planets[:]:
            planet.update(dt, player_dx)
            if not planet.alive:
                self.planets.remove(planet)

        for galaxy in self.galaxies[:]:
            galaxy.update(dt, player_dx)
            if not galaxy.alive:
                self.galaxies.remove(galaxy)

        if self.nebula is not None:
            self.nebula.update(dt, player_dx)
            if not self.nebula.alive:
                self.nebula = None

        self.planet_timer -= dt
        if self.planet_timer <= 0:
            # Prefer exclusive; when the other is already up, ~40% dual.
            # Also ~12% chance to invite a nebula right after a lone planet.
            if len(self.planets) == 0:
                if self.nebula is None or random.random() < 0.40:
                    self.planets.append(Planet())
                    if self.nebula is None and random.random() < 0.12:
                        self.nebula = Nebula()
                        self.nebula_timer = random.uniform(18.0, 32.0)
            self.planet_timer = random.uniform(16.0, 30.0)

        self.galaxy_timer -= dt
        if self.galaxy_timer <= 0:
            self.galaxies.append(Galaxy())
            self.galaxy_timer = random.uniform(12.0, 22.0)

        self.nebula_timer -= dt
        if self.nebula_timer <= 0:
            if self.nebula is None:
                if len(self.planets) == 0 or random.random() < 0.40:
                    self.nebula = Nebula()
                    if len(self.planets) == 0 and random.random() < 0.12:
                        self.planets.append(Planet())
                        self.planet_timer = random.uniform(14.0, 28.0)
            self.nebula_timer = random.uniform(22.0, 38.0)

    def draw(self, surface):
        # Depth (back → front): nebula / galaxies → stars → planets
        if self.nebula is not None:
            self.nebula.draw(surface)

        for galaxy in self.galaxies:
            galaxy.draw(surface)

        blit = surface.blit
        for star in self.stars_far:
            blit(star.stamp, (int(star.x) - star.ox, int(star.y) - star.oy))
        for star in self.stars_mid:
            blit(star.stamp, (int(star.x) - star.ox, int(star.y) - star.oy))
        for star in self.stars_near:
            blit(star.stamp, (int(star.x) - star.ox, int(star.y) - star.oy))

        for planet in self.planets:
            planet.draw(surface)
