"""The reflective coating (Gardiens III won: the mission's "reflect"). A Guardian's laser that meets the dome of the Shield
or the Phenix form splits where it touches: its two halves slide on a golden film around the ship, one on each side, then
fall straight down from its widest point and burn the birds they cross. The share of each side follows the point of
impact: half and half in the middle, almost all of it on one side near an edge. The laser is cut in slices; each one is
shared when it touches, so a ship that moves under the laser thickens one half and thins the other as it goes. The
modules move a little further out while halves run.

The slices live in game.laser_slices; the lasers keep what is left of them (FireLaser.eaten: the px of the tip split)."""

import math

import pygame

import guardian
from errlog import log_exc
from settings import BASE_HEIGHT

SHAPE = {"shield": (48.0, 58.0, -3.0), "phoenix": (52.0, 62.0, -2.0)}   # the film: half width, height above, centre dy
SPACING = 2.0                  # px of laser in one slice
WIDTH = 1.3                    # the width of a half: 1.3 x its share of the laser (half and half: 65 % each)
SHARE_MIN = 0.04               # the thinnest half (an impact at the very edge)
SPREAD = (30.0, 6.0)           # px the modules move further out (x) and down (y) while halves run
SPREAD_TIME = 0.15             # s to move out or back
FILM = (255, 200, 90)          # the golden film, lit where the halves slide
GLOW = 0.12                    # s the point of impact keeps glowing after the last slice


class Slice:
    __slots__ = ("ship", "side", "th", "w", "row", "x", "y", "falling", "stream")

    def __init__(self, ship, side, th, w, row, stream=None):
        self.ship, self.side, self.th, self.w, self.row = ship, side, th, w, row
        self.stream = stream if stream is not None else (id(ship), side)
        self.x = self.y = 0.0
        self.falling = False


def film(ship):
    """(half width, height above, centre x, centre y) of the film around the ship; its half width is always a little
    more than the reach of a laser that touches the ship."""
    a, b, dy = SHAPE["shield" if getattr(ship, "uses_shield", False) else "phoenix"]
    return max(a, reach(ship) + 3.0), b, float(ship.x), float(ship.y) + dy


def reach(ship):
    """How far from the centre of the ship a laser still touches it (px)."""
    return ship.get_hitbox().width / 2 + guardian.LASER_WIDTH / 2


def coated(game, ship):
    adv = getattr(game, "adventure", None) or {}
    return bool(adv.get("reflect")) and bool(getattr(ship, "is_phenix", False)) and ship.alive and not ship.dying


def share_right(ship, x):
    """The share of the laser that goes to the right of the ship when it touches at `x`."""
    return max(SHARE_MIN, min(1.0 - SHARE_MIN, 0.5 + 0.5 * (x - ship.x) / reach(ship)))


def _arc_step(a, b, th, side, dist):
    """Move `dist` px along the film from the angle `th` (0: the right end, pi: the left end). Returns (th, px left
    over once the end is reached, or -1)."""
    end = 0.0 if side > 0 else math.pi
    while dist > 0:
        speed = max(1e-3, math.hypot(a * math.sin(th), b * math.cos(th)))     # px per radian here
        step = min(dist, 2.0)
        th -= side * step / speed
        dist -= step
        if (side > 0 and th <= end) or (side < 0 and th >= end):
            return end, dist
    return th, -1.0


def split(game, ship):
    """Split the lasers that meet the film of `ship` this tick. Returns the lasers it holds (they no longer burn it)."""
    held = set()
    if not coated(game, ship):
        return held
    slices = game.__dict__.setdefault("laser_slices", [])
    a, b, cx, cy = film(ship)
    hw = reach(ship)
    for bolt in list(game.formation.bullets):
        if not isinstance(bolt, guardian.FireLaser) or not bolt.alive:
            continue
        dx = bolt.x - cx
        if abs(dx) >= hw:
            continue
        held.add(id(bolt))
        contact = cy - b * math.sqrt(max(0.0, 1.0 - (dx / a) ** 2))
        tip = bolt.y - bolt.eaten
        if tip < contact:
            continue
        before = bolt.eaten
        after = min(float(guardian.LASER_LENGTH), before + (tip - contact))
        if before <= 0:
            _first_touch(game, ship, bolt.x, contact)
        th0 = math.acos(max(-1.0, min(1.0, dx / a)))
        right = share_right(ship, bolt.x)
        k = math.ceil(before / SPACING - 1e-9)
        while k * SPACING < after:
            pos = k * SPACING
            row = max(0, guardian.LASER_LENGTH - 1 - int(pos))
            for side, w in ((1, right), (-1, 1.0 - right)):
                s = Slice(ship, side, th0, w, row, (id(bolt), side))
                _advance(s, after - pos)
                slices.append(s)
            k += 1
        bolt.eaten = after
        game.__dict__.setdefault("laser_glows", {})[id(ship)] = [bolt.x, contact, GLOW]
        if bolt.eaten >= guardian.LASER_LENGTH:
            bolt.alive = False
            for owner in (guardian.squad(game), game.formation):   # (the Guardian that fired it is free to move again)
                for g in getattr(owner, "guardians", None) or []:
                    if getattr(g, "emission", None) is bolt:
                        g.emission = None
    return held


def _first_touch(game, ship, x, y):
    try:
        if getattr(ship, "uses_shield", False):
            game._shield_absorb(ship, x, y)                       # (the dome: its ripple, where the laser touched)
        game.shake_amount = max(game.shake_amount, 3.0)
        game.sounds.play("shield_zap", volume=0.32, x=ship.x)
    except Exception:
        log_exc("laser_split.touch")


def _advance(s, dist):
    if dist <= 0:
        return
    if not s.falling:
        a, b, cx, cy = film(s.ship)
        s.th, left = _arc_step(a, b, s.th, s.side, dist)
        if left < 0:
            return
        s.falling = True
        s.x, s.y = cx + s.side * a, cy
        dist = left
    s.y += dist


def tick(game):
    """The halves slide and fall, and burn the birds they cross."""
    slices = getattr(game, "laser_slices", None)
    glows = getattr(game, "laser_glows", None)
    if glows:
        for key in list(glows):
            glows[key][2] -= game.dt
            if glows[key][2] <= 0:
                del glows[key]
    if not slices:
        return
    dist = guardian.LASER_SPEED * game.dt
    before = [(s.x, s.y) if s.falling else None for s in slices]
    for s in slices:
        _advance(s, dist)
    _burn(game, slices, before)
    game.laser_slices = [s for s in slices if not (s.falling and s.y > BASE_HEIGHT + 20)]


def _burn(game, slices, before):
    sq = guardian.squad(game)
    form = game.formation
    owner, birds = (sq if sq is not None else form), form.get_hittable_enemies()
    birds = [bird for bird in birds if bird.alive and not bird.dying]
    if not birds:
        return
    for s, was in zip(slices, before):
        if not s.falling:
            continue
        x0 = s.x + s.side * 4.0
        y0 = was[1] if was else s.y - guardian.LASER_SPEED * game.dt
        for bird in birds:
            if not bird.alive or bird.dying:
                continue
            box = bird.get_hitbox()
            if box.left - 4 <= x0 <= box.right + 4 and y0 <= box.bottom and s.y >= box.top:
                guardian.burn_bird(owner, bird)


def active(game, ship):
    """Do halves of a laser still run on this ship's film or under it?"""
    return any(s.ship is ship and (not s.falling or s.y < ship.y + 120) for s in getattr(game, "laser_slices", None) or [])


# ---------------------------------------------------------------- drawing
_BANDS = {}


def _bands(frame, row):
    """The colours of one row of the laser, from the outside in: [(half width px, colour)]."""
    key = (frame, row)
    out = _BANDS.get(key)
    if out is None:
        pic = guardian.art()[1][frame]
        mid = pic.get_width() / 2
        cols = [(c, pic.get_at((c, row))) for c in range(pic.get_width())]
        out = []
        for test, edge in ((lambda col: col.a > 60, True), (lambda col: col.a > 200, True),
                           (lambda col: col.r + col.g + col.b > 600, False)):
            picked = [(c, col) for c, col in cols if test(col)]
            if not picked:
                continue
            far = max(picked, key=lambda cc: abs(cc[0] + 0.5 - mid))
            half = abs(far[0] + 0.5 - mid)
            # the outer bands take the colour of their edge (the deep orange of the flame), the core its average
            colour = tuple(far[1])[:3] if edge else tuple(sum(col[i] for _, col in picked) // len(picked) for i in range(3))
            out.append((half, colour))
        _BANDS[key] = out
    return out


def _glow_pic(r, colour):
    key = ("glow", r, colour)
    pic = _BANDS.get(key)
    if pic is None:
        pic = pygame.Surface((r * 2, r * 2))
        pic.fill((0, 0, 0))
        for k in range(r, 0, -1):
            f = (1 - k / r) ** 2
            pygame.draw.circle(pic, tuple(int(c * f) for c in colour), (r, r), k)
        _BANDS[key] = pic
    return pic


def _placed(s, films, frame):
    """Where a slice is drawn: (middle x, y, normal x, y, bands, scale, inner edge x, y, on the film)."""
    if s.falling:
        x, y, nx, ny = s.x, s.y, float(s.side), 0.0
    else:
        f = films.get(id(s.ship))
        if f is None:
            f = films[id(s.ship)] = film(s.ship)
        a, b, cx, cy = f
        x, y = cx + a * math.cos(s.th), cy - b * math.sin(s.th)
        nx, ny = math.cos(s.th) / a, -math.sin(s.th) / b
        n = math.hypot(nx, ny) or 1.0
        nx, ny = nx / n, ny / n
    scale = WIDTH * s.w
    bands = _bands(frame, s.row)
    shift = (bands[0][0] * scale if bands else 0.0) + 1.0          # (its inner edge on the film)
    return x + nx * shift, y + ny * shift, nx, ny, bands, scale, x, y, not s.falling


def draw(game, surface):
    slices = getattr(game, "laser_slices", None)
    glows = getattr(game, "laser_glows", None)
    if not slices and not glows:
        return
    frame = int(pygame.time.get_ticks() / 1000.0 * guardian.LASER_FPS) % guardian.LASER_FRAMES
    films, streams = {}, {}
    for s in slices or []:
        streams.setdefault(s.stream, []).append(_placed(s, films, frame))
    for run in streams.values():
        # the film first (a thin golden line under the halves), then each band of the laser as a ribbon from one slice
        # to the next (from the outside in)
        for p, q in zip(run, run[1:]):
            if p[8] and q[8]:
                pygame.draw.line(surface, FILM, (p[6] - p[2], p[7] - p[3]), (q[6] - q[2], q[7] - q[3]), 2)
        for p, q in zip(run, run[1:] + [None]):
            mx, my, nx, ny, bands, scale = p[:6]
            for i, (half, colour) in enumerate(bands):
                h = max(0.6, half * scale)
                a1, a2 = (mx - nx * h, my - ny * h), (mx + nx * h, my + ny * h)
                if q is not None and i < len(q[4]) and abs(q[0] - mx) + abs(q[1] - my) < 8:
                    h2 = max(0.6, q[4][i][0] * q[5])
                    pygame.draw.polygon(surface, colour, (a1, a2, (q[0] + q[2] * h2, q[1] + q[3] * h2),
                                                          (q[0] - q[2] * h2, q[1] - q[3] * h2)))
                else:
                    pygame.draw.line(surface, colour, a1, a2, 2)
    for x, y, _t in (glows or {}).values():
        for r, colour in ((24, (255, 170, 60)), (8, (255, 245, 215))):
            surface.blit(_glow_pic(r, colour), (int(x) - r, int(y) - r), special_flags=pygame.BLEND_RGB_ADD)


def reset(game):
    game.laser_slices = []
    game.laser_glows = {}
