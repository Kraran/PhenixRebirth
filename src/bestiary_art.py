"""Pictures of the Adventure enemies for the Bestiary screen.

Built from the same sprites the game uses (assets/sprites), so what the pilot reads about
is exactly what he fights: birds flap and glow, gargoyles beat their wings.
"""
import math
import os

import pygame

from settings import asset_path
from errlog import log_exc

# Same rhythm as the enemies in the game
BIRD_FLAP_RATE = 5.2        # wing beats per second
BIRD_GLOW_PERIOD = 2.0      # the eyes light up every 2 s ...
BIRD_GLOW_LEN = 0.35        # ... for this long
GARG_FLAP_SPEED = 12.0      # radians per second (the game uses 10-14)

_KINDS = {
    "bird1": ("bird", "bird1"),
    "bird2": ("bird", "bird2"),
    "garg3": ("garg", "garg3"),
    "garg4": ("garg", "garg4"),
}
_cache = {}


def _load(name):
    img = pygame.image.load(os.path.join(asset_path("sprites"), name + ".png"))
    try:
        return img.convert_alpha()
    except pygame.error:                 # no display yet (tests of the pure logic)
        return img


def _bird_frames(prefix):
    names = ("flap0", "flap1", "flap0_glow", "flap1_glow")
    return [_load(f"{prefix}_{n}") for n in names]


def _gargoyle(prefix, wings_up):
    """Body and both wings put together the way the game draws them."""
    body = _load(prefix + "_body")
    wing = _load(prefix + ("_wing_up" if wings_up else "_wing_down"))
    bw, bh = body.get_size()
    ww, wh = wing.get_size()
    flap_y = -5 if wings_up else 5
    width = bw + 2 * (ww - 6)
    height = max(bh, wh) + 12
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    cy = height // 2
    body_x = ww - 6
    surf.blit(wing, (0, cy - wh // 2 + flap_y))
    surf.blit(pygame.transform.flip(wing, True, False), (body_x + bw - 6, cy - wh // 2 + flap_y))
    surf.blit(body, (body_x, cy - bh // 2))
    return surf


def _frames(kind):
    """All pictures of one enemy, loaded once: {"still": Surface, "bird": [4] or "garg": [down, up]}."""
    hit = _cache.get(kind)
    if hit is not None:
        return hit
    family, prefix = _KINDS[kind]
    try:
        if family == "bird":
            frames = _bird_frames(prefix)
            hit = {"family": family, "frames": frames, "still": frames[0]}
        else:
            down, up = _gargoyle(prefix, False), _gargoyle(prefix, True)
            hit = {"family": family, "frames": [down, up], "still": down}
    except Exception:
        log_exc("bestiary_art._frames")
        blank = pygame.Surface((40, 40), pygame.SRCALPHA)
        hit = {"family": family, "frames": [blank], "still": blank}
    _cache[kind] = hit
    return hit


def still(kind):
    """The motionless picture."""
    return _frames(kind)["still"]


def animated(kind, t):
    """The picture at time `t` seconds: wings beating, eyes lighting up."""
    data = _frames(kind)
    frames = data["frames"]
    if data["family"] == "bird" and len(frames) >= 4:
        flap = int(t * BIRD_FLAP_RATE) % 2
        glow = (t % BIRD_GLOW_PERIOD) < BIRD_GLOW_LEN
        return frames[flap + (2 if glow else 0)]
    if data["family"] == "garg" and len(frames) >= 2:
        return frames[1] if math.sin(t * GARG_FLAP_SPEED) > 0 else frames[0]
    return data["still"]


def known_kinds():
    return tuple(_KINDS)
