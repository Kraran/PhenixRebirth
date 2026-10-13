"""A loot item falling through a mission (Adventure), and the pictures of the items.

assets/items/<id>.png is the falling sprite: FRAMES cells side by side, one loop (tools/make_item_sprites.py);
assets/items/<id>_icon.png is the bigger picture the hangar shop shows. The rules (what falls, when, what it does)
are in story_items.py.
"""
import os
import random

import pygame

from errlog import log_exc
from settings import BASE_HEIGHT, BASE_WIDTH, asset_path
import story_items

FRAMES = 36              # cells in a sprite strip
ANIM_FPS = 8.0           # a little faster than the source video (6 s for the 36 cells)
FALL_SPEED = 130.0       # px per second: about 5 s from the top of the screen to the ship
MARGIN = 60              # the item never falls closer than this to the side walls
START_Y = -30.0

_frames = {}
_icons = {}


def _load(name):
    try:
        return pygame.image.load(asset_path("items", name)).convert_alpha()
    except Exception:
        log_exc("loot._load")
        return None


def _picture(item):
    """Name of the picture of `item` (the two reactors share one)."""
    return story_items.SPRITES.get(item, item)


def frames(item):
    """The cells of the falling sprite of `item` (a list of Surfaces; [] if the picture is missing)."""
    if item not in _frames:
        strip = _load(_picture(item) + ".png")
        out = []
        if strip is not None:
            w = strip.get_width() // FRAMES
            out = [strip.subsurface((i * w, 0, w, strip.get_height())).copy() for i in range(FRAMES)]
        _frames[item] = out
    return _frames[item]


def icon(item, height=None, width=None):
    """The picture of `item` for menus and the HUD, shrunk to fit `height` and `width` pixels (None: as it is)."""
    key = (item, height, width)
    if key not in _icons:
        img = _load(_picture(item) + "_icon.png")
        if img is not None and (height or width):
            k = min((height or 10 ** 6) / img.get_height(), (width or 10 ** 6) / img.get_width())
            if k != 1.0:
                img = pygame.transform.smoothscale(img, (max(1, round(img.get_width() * k)),
                                                         max(1, round(img.get_height() * k))))
        _icons[key] = img
    return _icons[key]


_shop_cells = {}


def shop_frame(item, t, height=34, width=40):
    """The picture of `item` for a hangar row at time `t` (seconds): the turning sprite of the mission, shrunk to fit
    `height` x `width` pixels (the still icon if the sprite is missing)."""
    cells = frames(item)
    if not cells:
        return icon(item, height, width)
    i = int(max(0.0, t) * ANIM_FPS) % len(cells)
    key = (item, i, height, width)
    if key not in _shop_cells:
        cell = cells[i]
        k = min(height / max(1, cell.get_height()), width / max(1, cell.get_width()))
        _shop_cells[key] = pygame.transform.smoothscale(
            cell, (max(1, round(cell.get_width() * k)), max(1, round(cell.get_height() * k))))
    return _shop_cells[key]


class FallingItem:
    """One item falling from the top of the screen to the bottom, in a straight line."""

    def __init__(self, item, x):
        self.item = item
        self.x = float(x)
        self.y = START_Y
        self.t = 0.0
        self.alive = True
        self.cells = frames(item)
        first = self.cells[0] if self.cells else None
        self.w = first.get_width() if first else 40
        self.h = first.get_height() if first else 40

    @staticmethod
    def pick_x(player_x, player_speed, player_y, rand=random):
        """Where it starts: anywhere on the screen the ship can still reach before the item gets to its height."""
        reach = max(0.0, player_speed * 0.75 * (player_y - START_Y) / FALL_SPEED)
        lo = max(MARGIN, player_x - reach)
        hi = min(BASE_WIDTH - MARGIN, player_x + reach)
        if hi <= lo:
            return min(BASE_WIDTH - MARGIN, max(MARGIN, player_x))
        return rand.uniform(lo, hi)

    def update(self, dt):
        self.t += dt
        self.y += FALL_SPEED * dt
        if self.y - self.h > BASE_HEIGHT:
            self.alive = False

    def rect(self):
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h / 2), self.w, self.h)

    def draw(self, surface):
        if not self.cells:
            pygame.draw.circle(surface, (120, 200, 255), (int(self.x), int(self.y)), 16, 3)
            return
        img = self.cells[int(self.t * ANIM_FPS) % len(self.cells)]
        surface.blit(img, (int(self.x - self.w / 2), int(self.y - self.h / 2)))
