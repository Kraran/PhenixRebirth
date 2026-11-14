"""The lights of a blast (asteroids._add_glow): the big ones are cut out of a ring map and only their part on the screen
is made, the same pixels as drawing their circles (the ship's blast froze the game a few frames at every explosion)."""
import random

import numpy as np
import pygame

import asteroids
from test_smoke import run  # noqa: F401  (fixture: the display)


def _drawn(surface, color, pos, size):
    """The light the old way: its circles, from the outside in."""
    size = max(2, int(size))
    r = size // 2
    g = pygame.Surface((size, size))
    for i in range(r, 0, -1):
        k = (1.0 - i / r) ** 2
        pygame.draw.circle(g, (int(color[0] * k), int(color[1] * k), int(color[2] * k)), (r, r), i)
    surface.blit(g, (int(pos[0] - size // 2), int(pos[1] - size // 2)), special_flags=pygame.BLEND_RGB_ADD)


def test_the_big_lights_are_the_same_pixels_as_their_circles(run):
    rng = random.Random(7)
    asteroids.warm_glows()
    for _ in range(25):
        a = pygame.Surface((1280, 720))
        a.fill((rng.randrange(60),) * 3)
        b = a.copy()
        asteroids._glows.clear()
        for _ in range(3):
            color = (rng.randrange(256), rng.randrange(256), rng.randrange(256))
            size = rng.choice([rng.uniform(2, 300), rng.uniform(300, 1300)])
            pos = (rng.uniform(-400, 1680), rng.uniform(-300, 1020))
            _drawn(a, color, pos, size)
            asteroids._add_glow(b, color, pos, size)
        assert np.array_equal(pygame.surfarray.array3d(a), pygame.surfarray.array3d(b))


def test_a_light_off_the_screen_draws_nothing_and_a_cut_one_is_kept_as_cut(run):
    s = pygame.Surface((1280, 720))
    asteroids._glows.clear()
    asteroids._add_glow(s, (255, 255, 235), (-2000, -2000), 900)
    assert not pygame.surfarray.array3d(s).any() and not asteroids._glows
    asteroids._add_glow(s, (255, 255, 235), (640, 700), 900)          # (half of it below the screen)
    assert pygame.surfarray.array3d(s).any()
    assert ((255, 255, 235), 900) not in asteroids._glows               # (not as a whole light...)
    assert len(asteroids._glows) == 1                                   # (... but its part on the screen, kept)
    again = pygame.Surface((1280, 720))
    asteroids._add_glow(again, (255, 255, 235), (640, 700), 900)
    assert len(asteroids._glows) == 1 and np.array_equal(pygame.surfarray.array3d(s), pygame.surfarray.array3d(again))


def test_the_ring_map_is_made_at_start_up(run):
    rings, radius = asteroids._ring_map(1)
    assert rings is not None and radius >= 640           # (game_init: no 0.1 s pause at the first blast)
