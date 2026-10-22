"""Soft pink halo drawn behind the enemy shots, so they stay readable over the stars and the enemies.

The glow is a small radial gradient, built once and added (BLEND_RGB_ADD) under the shot: it only lights the
background, it never hides anything and it does not change the hitbox.
"""
import pygame

HALO_RADIUS = 18                 # px around the centre of the shot
HALO_COLOR = (255, 80, 200)      # the pink of the shots
HALO_STRENGTH = 0.55             # peak brightness of the glow (0..1)

_cache = {}


def halo_surface(radius=HALO_RADIUS, color=HALO_COLOR, strength=HALO_STRENGTH):
    """The glow, cached. Black at the edge, `color` * `strength` at the centre (it is blitted with BLEND_RGB_ADD)."""
    key = (radius, color, strength)
    surf = _cache.get(key)
    if surf is None:
        surf = pygame.Surface((2 * radius, 2 * radius), pygame.SRCALPHA)
        for k in range(radius, 0, -1):
            a = strength * (1 - k / radius) ** 2
            pygame.draw.circle(surf, (int(color[0] * a), int(color[1] * a), int(color[2] * a), 255), (radius, radius), k)
        _cache[key] = surf
    return surf


def draw_halo(surface, cx, cy):
    """Light the background around a shot whose centre is (cx, cy)."""
    r = HALO_RADIUS
    surface.blit(halo_surface(), (int(cx) - r, int(cy) - r), special_flags=pygame.BLEND_RGB_ADD)
