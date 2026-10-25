"""Guardian laser destruction: cached hull/form-specific fire and disintegration."""
import math

import pygame

DURATION = 1.4
FRAME_COUNT = 32
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
    # Full form silhouette plus room for flames, debris and rising ash.
    width, height = w + 112, h + 144
    ox, oy = 56, 80
    pixels = [(x, y, source.get_at((x, y))) for y in range(h) for x in range(w)
              if source.get_at((x, y)).a > 24]
    result = []
    for index in range(FRAME_COUNT):
        t = index / (FRAME_COUNT - 1)
        pic = pygame.Surface((width, height), pygame.SRCALPHA)
        dissolve = max(0.0, (t - 0.22) / 0.48)
        heat = min(1.0, t / 0.16)
        char = min(0.94, max(0.0, (t - 0.22) / 0.4))
        for x, y, colour in pixels:
            noise = ((x * 73 + y * 151) % 127) / 126
            if t < 0.70 and noise >= dissolve:
                rgb = [int((colour[i] * (1 - heat) + (255, 115, 20)[i] * heat)
                           * (1 - char)) for i in range(3)]
                pic.set_at((ox + x, oy + y), (*rgb, colour.a))
        if 0 < t < 0.65:
            strength = math.sin(math.pi * t / 0.65)
            for j in range(15):
                px = ox + round(w * (j + 1) / 16)
                py = oy + round(h * (0.45 + (j % 3) * 0.13))
                length = max(1, int((25 + (j * 11 + index * 7) % 32) * strength))
                pygame.draw.polygon(pic, (255, 65 + j % 6 * 17, 10, 235),
                                    [(px - 7, py + 6), (px + 7, py + 6),
                                     (px + (j + index) % 7 - 3, py - length)])
                pygame.draw.line(pic, (255, 240, 130, 240),
                                 (px, py), (px, py - length // 2), 3)
        if pixels and 0.22 <= t < 1:
            drift = (t - 0.22) / 0.78
            count = min(96, len(pixels))
            for j in range(count):
                x, y, _ = pixels[j * len(pixels) // count]
                px = ox + x + math.sin(j * 2.4) * drift * 46
                py = oy + y - drift * (18 + j % 9 * 6)
                alpha = int(255 * (1 - drift))
                ember = t < 0.62 and j % 3 == 0
                colour = (255, 145, 30, alpha) if ember else (145, 140, 135, alpha)
                pygame.draw.circle(pic, colour, (round(px), round(py)), 1 + (j % 5 == 0))
        result.append(pic)
    _CACHE[key] = tuple(result)
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
        # Hull centre within the padded image (padding is deliberately asymmetric).
        width, height = self.frames[0].get_size()
        self.offset = (width // 2, height // 2 + 8)
        self.age = 0.0

    @property
    def finished(self):
        return self.age >= DURATION

    def update(self, dt):
        self.age += dt

    def draw(self, surface):
        if not self.finished:
            frame = self.frames[min(FRAME_COUNT - 1, int(self.age / DURATION * FRAME_COUNT))]
            surface.blit(frame, (round(self.x - self.offset[0]), round(self.y - self.offset[1])))
