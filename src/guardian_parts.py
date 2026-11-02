"""The Guardian sheet cut into a body and two wings, with wounds baked once (three health levels).

The 160 x 160 cells of ``sentinelle.png`` hold a whole bird. The wings must be destroyed, regrow and fall off on their own,
so each cell is split along a jagged line (torn edge) into a left wing, a body and a right wing. The three pieces are an exact
partition of the cell (the polygons are the same pixels on both sides), so the intact bird looks exactly like the sheet.

Health levels: 0 = 3 HP (intact), 1 = 2 HP (soot, glowing cracks, a tear in each wing), 2 = 1 HP (burnt, deep cracks, a shot-out
eye, a broken crest, ragged wings). Everything is drawn once here, never while playing; drawing only blits cached pictures.
"""
import math
import random

import pygame

CELL = 160
AXIS = 79                       # body axis of every cell (the eyes were aligned on it)
LEVELS = 3
SIDES = ("left", "right")

# The line along which a wing tears off the shoulder: straight above the claws, then it steps outward so the claws stay
# with the body. Jagged, because a torn wing leaves a ragged root.
_SPLIT_X = 18
_SPLIT_CLAW_X = 26
_CLAW_Y = 66

# Cracks in the armour (cell coordinates, the body is aligned in every cell): [level 1 (2 HP), added at level 2 (1 HP)]
CRACKS = (
    (((70, 60), (73, 66), (71, 72), (75, 78)), ((88, 64), (86, 70), (90, 75))),
    (((79, 50), (77, 57), (80, 63), (78, 70)), ((66, 80), (70, 84), (68, 90)), ((92, 82), (88, 87), (91, 93))),
)
SOOT = (
    ((66, 70, 9, 6), (92, 60, 7, 5)),
    ((74, 88, 10, 6), (84, 48, 7, 5), (96, 78, 7, 6)),
)

SMOKE_STEPS = 8


class Part:
    """A cropped picture and where its top-left corner sits in the 160 x 160 cell."""
    __slots__ = ("surf", "ox", "oy")

    def __init__(self, surf, ox, oy):
        self.surf, self.ox, self.oy = surf, ox, oy


def _crop(full):
    box = full.get_bounding_rect()
    if box.w == 0 or box.h == 0:
        return Part(pygame.Surface((1, 1), pygame.SRCALPHA), 0, 0)
    return Part(full.subsurface(box).copy(), box.x, box.y)


def split_line(side):
    """The jagged boundary points (cell coordinates) between a wing and the body, from the top to the bottom."""
    rng = random.Random(41)
    points = []
    for y in range(0, CELL + 1, 4):
        if y < _CLAW_Y:
            x = AXIS - _SPLIT_X
            if 8 <= y <= _CLAW_Y - 4:
                x += rng.choice((-3, -2, 0, 2, 3))
        elif y < _CLAW_Y + 12:
            x = AXIS - _SPLIT_X - (y - _CLAW_Y) * (_SPLIT_CLAW_X - _SPLIT_X) / 12
        else:
            x = AXIS - _SPLIT_CLAW_X
        points.append((round(x), y))
    if side == "right":
        points = [(2 * AXIS - x, y) for x, y in points]
    return points


def _region(side):
    pts = split_line(side)
    edge = (0, 0) if side == "left" else (CELL, 0)
    edge_end = (0, CELL) if side == "left" else (CELL, CELL)
    return [edge] + pts + [edge_end]


def _mask_surface(side=None):
    """White where a piece lives, transparent elsewhere; the body is what neither wing covers."""
    surf = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
    if side is None:
        surf.fill((255, 255, 255, 255))
        for s in SIDES:
            pygame.draw.polygon(surf, (0, 0, 0, 0), _region(s))
    else:
        pygame.draw.polygon(surf, (255, 255, 255, 255), _region(side))
    return surf


def _piece(frame, mask):
    out = frame.copy()
    out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return out


def _white_alpha(surf):
    """Same alpha, white colour: multiplies a drawing so that only the opaque pixels of ``surf`` keep it."""
    out = surf.copy()
    out.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return out


def _clip(layer, to):
    layer.blit(_white_alpha(to), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return layer


def _eyes(body):
    """Pixels of the two glowing eyes (yellow-green): [left, right]."""
    left, right = [], []
    for y in range(20, 110):
        for x in range(AXIS - 30, AXIS + 31):
            r, g, b, a = body.get_at((x, y))
            if a > 120 and r > 150 and g > 170 and b < 110:
                (left if x < AXIS else right).append((x, y))
    return left, right


def _wound_body(body, level):
    """Soot, glowing cracks, and at 1 HP a shot-out eye, a red failing eye and a broken crest."""
    out = body.copy()
    layer = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
    for group in SOOT[:level]:
        for cx, cy, rx, ry in group:
            pygame.draw.ellipse(layer, (8, 6, 6, 120 + 40 * (level - 1)), (cx - rx, cy - ry, rx * 2, ry * 2))
    for group in CRACKS[:level]:
        for line in group:
            pygame.draw.lines(layer, (10, 4, 4, 210), False, line, 3)
            pygame.draw.lines(layer, (255, 120 + 30 * level, 30, 255), False, line, 1)
    _clip(layer, body)
    out.blit(layer, (0, 0))
    if level >= 2:
        left, right = _eyes(body)
        for x, y in left:                         # the left eye is shot out: dead, with a red cinder at its heart
            out.set_at((x, y), (22, 8, 8, body.get_at((x, y)).a))
        if left:
            cx = sum(p[0] for p in left) // len(left)
            cy = sum(p[1] for p in left) // len(left)
            out.set_at((cx, cy), (255, 50, 20, 255))
        for x, y in right:                        # the other one burns red, the system is failing
            r, g, b, a = body.get_at((x, y))
            out.set_at((x, y), (255, max(20, g // 5), 10, a))
        top = body.get_bounding_rect().top
        pygame.draw.polygon(out, (0, 0, 0, 0), [(AXIS - 9, top - 1), (AXIS + 10, top - 1), (AXIS + 10, top + 5),
                                               (AXIS + 3, top + 9), (AXIS + 1, top + 4)])
        edge = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        pygame.draw.lines(edge, (255, 110, 30, 255), False, [(AXIS + 10, top + 5), (AXIS + 3, top + 9), (AXIS + 1, top + 4)], 1)
        _clip(edge, body)
        out.blit(edge, (0, 0))
    return out


def _opaque_points(wing, rng, count, margin):
    mask = pygame.mask.from_surface(wing, 120)
    width, height = wing.get_size()
    found = []
    for _ in range(400):
        x, y = rng.randrange(margin, width - margin), rng.randrange(margin, height - margin)
        if all(mask.get_at((x + dx, y + dy)) for dx in (-margin, 0, margin) for dy in (-margin, 0, margin)):
            if all(math.hypot(x - fx, y - fy) > 2 * margin + 2 for fx, fy in found):
                found.append((x, y))
                if len(found) == count:
                    break
    return found


def _wound_wing(wing, level, seed):
    """Burnt holes with glowing edges in the membrane: one tear at 2 HP, several ragged ones at 1 HP."""
    if level == 0:
        return wing
    out = wing.copy()
    rng = random.Random(seed)
    bright = (255, 110 + 40 * (level - 1), 30, 255)
    for x, y in _opaque_points(wing, rng, 1 if level == 1 else 3, 4 if level == 1 else 3):
        radius = rng.randint(4, 6) if level == 1 else rng.randint(3, 5)
        ragged = [(x + round(math.cos(a) * radius * rng.uniform(0.6, 1.25)),
                   y + round(math.sin(a) * radius * rng.uniform(0.6, 1.25)))
                  for a in [i * math.tau / 7 for i in range(7)]]
        rim = pygame.Surface(wing.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(rim, bright, ragged, 2)
        pygame.draw.polygon(rim, (25, 8, 8, 255), ragged, 1)
        _clip(rim, wing)
        out.blit(rim, (0, 0))
        pygame.draw.polygon(out, (0, 0, 0, 0), [(x + (px - x) * 3 // 4, y + (py - y) * 3 // 4) for px, py in ragged])
    return out


def _whiten(surf):
    out = surf.copy()
    out.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return out


def _smoke(step):
    size = 6 + step * 2
    surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
    alpha = max(0, 150 - step * 19)
    pygame.draw.circle(surf, (62, 58, 60, alpha), (size, size), size)
    pygame.draw.circle(surf, (96, 88, 86, alpha // 2), (size - 1, size - 1), max(1, size * 2 // 3))
    return surf


class Parts:
    """Everything the Guardian draws, baked once: ``body[row][frame][level]``, ``wing[row][frame][side][level]``."""

    def __init__(self, rows):
        masks = {"left": _mask_surface("left"), "right": _mask_surface("right"), None: _mask_surface()}
        self.body, self.wing = [], []
        self.white_body, self.white_wing = [], []
        for row_i, row in enumerate(rows):
            body_row, wing_row, white_body_row, white_wing_row = [], [], [], []
            for frame_i, frame in enumerate(row):
                seed = row_i * 10 + frame_i
                body = _piece(frame, masks[None])
                bodies = [_wound_body(body, level) for level in range(LEVELS)]
                body_row.append([_crop(b) for b in bodies])
                white_body_row.append([_crop(_whiten(b)) for b in bodies])
                wings, whites = {}, {}
                for side in SIDES:
                    base = _piece(frame, masks[side])
                    pics = [_wound_wing(base, level, seed * 7 + (side == "right")) for level in range(LEVELS)]
                    wings[side] = [_crop(p) for p in pics]
                    whites[side] = [_crop(_whiten(p)) for p in pics]
                wing_row.append(wings)
                white_wing_row.append(whites)
            self.body.append(body_row)
            self.wing.append(wing_row)
            self.white_body.append(white_body_row)
            self.white_wing.append(white_wing_row)
        self.smoke = [_smoke(i) for i in range(SMOKE_STEPS)]
        self.edge = {side: split_line(side) for side in SIDES}
