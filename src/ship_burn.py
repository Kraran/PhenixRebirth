"""Guardian laser destruction of the ship: cached hull/form-specific blaze, charring and scattered ash (src/fire_death.py)."""
import math

import pygame

import fire_death

DURATION = 2.4
FRAME_COUNT = 32
SIZE = (360, 380)                  # the size of every picture
HULL = (130, 240)                  # where the middle of the hull is in it
_CACHE = {}


def _source(ship, active):
    layers = [ship.image]
    if active and ship.phenix_frames:
        if ship.uses_shield:
            layers.append(ship.phenix_frames[0])
        else:
            layers = [ship.phenix_frames[0]]
    width = max(layer.get_width() for layer in layers)
    height = max(layer.get_height() for layer in layers)
    source = pygame.Surface((width, height), pygame.SRCALPHA)
    for layer in layers:
        source.blit(layer, layer.get_rect(center=(width // 2, height // 2)))
    return source


def frames(ship, active):
    key = (ship.ship_id, ship.palette, bool(active))
    if key in _CACHE:
        return _CACHE[key]
    source = _source(ship, active)
    w, h = source.get_size()
    # The hull sits at HULL inside the picture: room above for the flames, to the right for the wind that scatters the ash.
    origin = (HULL[0] - w // 2, HULL[1] - h // 2)
    _CACHE[key] = fire_death.frames(source, FRAME_COUNT, fire_death.SHIP, SIZE, origin)
    return _CACHE[key]


def prepare(ship):
    """Called at mission setup, so impacts and drawing only use cached frames."""
    frames(ship, False)
    frames(ship, True)


class ShipBurn:
    def __init__(self, ship):
        self.active_form = ship.is_phenix
        self.frames = frames(ship, self.active_form)
        self.x, self.y = ship.x, ship.y
        self.offset = HULL                 # (the middle of the hull in the picture)
        self.age = 0.0

    @property
    def finished(self):
        return self.age >= DURATION

    def update(self, dt):
        self.age += dt

    def draw(self, surface, angle=None, scale=1.0):
        """`angle`: the degrees (counter-clockwise, as pygame.transform.rotate) the ship was turned by, or None; `scale`:
        the size of the picture (the ship of the SpaceWar level is drawn at half its size)."""
        if not self.finished:
            frame = self.frames[min(FRAME_COUNT - 1, int(self.age / DURATION * FRAME_COUNT))]
            if angle is not None or scale != 1.0:
                frame = pygame.transform.rotozoom(frame, angle or 0.0, scale)
                rad = math.radians(angle or 0.0)
                # the hull is off the middle of the picture: that point stays on the ship
                dx = self.offset[0] - SIZE[0] / 2
                dy = self.offset[1] - SIZE[1] / 2
                cx = self.x - scale * (dx * math.cos(rad) + dy * math.sin(rad))
                cy = self.y - scale * (-dx * math.sin(rad) + dy * math.cos(rad))
                surface.blit(frame, frame.get_rect(center=(round(cx), round(cy))))
                return
            surface.blit(frame, (round(self.x - self.offset[0]), round(self.y - self.offset[1])))
