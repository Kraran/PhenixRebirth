"""The missile launchers of the base (src/scramble_base.py: Turret), as the player sees them: an armoured casemate in the
gunmetal of the wall, bolted on its face, a heavy tube to the left, a red slit of an eye lit from inside in the red of the
boss.

It is drawn standing (muzzle up, the wall under it, on a canvas of 26 x 30 logical px, K times bigger), then turned a quarter
to the left: the TURRET_W x TURRET_H picture of the box of the turret (scramble_base.Turret.box). Its states:

- idle: its missile waits in the tube, the nose out, its eye glowing softly;
- warn: in the last WARN seconds before it fires, its lights blink fast and its eye flares (the player sees it coming);
- fire: for FIRE seconds after a missile has left, a flash at the muzzle and a kick backwards;
- reload: until RELOAD seconds after it fired, the tube empty, its lights blinking slowly;
- wreck: shot down, its scorched wreck stays on the wall, smoking, embers glowing, until a second shot blows it away (or the
  base blows up).
"""
import math

import pygame

K = 8                            # drawn 8 times bigger, then scaled (as the stations: smooth metal)
UP = (26, 30)                    # the logical canvas, standing (muzzle up)
FIRE = 0.22                      # seconds of the flash and the kick after a launch
RELOAD = 1.1                     # seconds without a missile after a launch
WARN = 0.5                       # seconds of fast blinking before a launch
KICK = 2.5                       # px it is pushed back to the wall by a launch
NOSE_OUT = 6                     # px of the waiting missile's nose out of the muzzle

_PICS = {}


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _sheen(pic, poly, stops):
    import scramble_view as sv
    sv._sheen(pic, poly, stops)


def _p(k, *pts):
    return [(x * k, y * k) for x, y in pts]


C_LIGHTS = ((5, 26), (21, 26))


def _casemate(pic, k, dead):
    w, h = pic.get_size()
    hull = _p(k, (0, 30), (0, 12), (4, 7), (22, 7), (26, 12), (26, 30))
    _sheen(pic, hull, [(0, (30, 32, 38)), (0.3, (70, 74, 86)), (0.68, (150, 156, 170)), (1, (44, 46, 54))] if not dead
           else [(0, (22, 18, 16)), (0.3, (50, 44, 40)), (0.68, (112, 100, 90)), (1, (34, 30, 28))])
    pygame.draw.polygon(pic, (12, 12, 16), hull, max(1, k // 2))
    for y in (16, 23):                                             # the seams of its plates, bevelled
        pygame.draw.line(pic, (20, 20, 26), (0.5 * k, y * k), (25.5 * k, y * k), max(1, k // 3))
        pygame.draw.line(pic, (170, 176, 190), (0.5 * k, (y + 0.4) * k), (25.5 * k, (y + 0.4) * k), max(1, k // 5))
    for x, y in ((2, 13), (24, 13), (2, 19), (24, 19), (2, 28), (24, 28), (8, 28), (18, 28)):
        pygame.draw.circle(pic, (190, 194, 206), (x * k, y * k), int(0.6 * k))
        pygame.draw.circle(pic, (26, 26, 32), (x * k + k // 4, y * k + k // 4), int(0.6 * k), max(1, k // 4))
    # the tube, with its collar
    tube = _p(k, (8, 0), (18, 0), (18, 11), (8, 11)) if not dead else _p(k, (8, 6), (11, 3.5), (13, 5), (16, 2.5), (18, 5),
                                                                          (18, 11), (8, 11))
    _sheen(pic, tube, [(0, (36, 38, 46)), (0.65, (140, 146, 160)) if not dead else (0.65, (60, 56, 54)),
                       (1, (40, 42, 50))])
    pygame.draw.polygon(pic, (10, 10, 14), tube, max(1, k // 3))
    pygame.draw.rect(pic, (58, 60, 70), (7 * k, 9 * k, 12 * k, 2.4 * k))
    pygame.draw.rect(pic, (150, 154, 168), (7 * k, 9 * k, 12 * k, 0.6 * k))
    bore = (10 * k, 0, 6 * k, 9 * k) if not dead else (10 * k, 4 * k, 6 * k, 5 * k)
    pygame.draw.rect(pic, (8, 4, 4), bore)
    # the eye: a red slit in its brow
    eye = (6 * k, 18.5 * k, 14 * k, 2.6 * k)
    pygame.draw.rect(pic, (12, 8, 8), eye, border_radius=k)
    if dead:
        pygame.draw.polygon(pic, (8, 6, 6), _p(k, (14, 13), (20, 17), (17, 21), (22, 26), (15, 24), (12, 19)))
        pygame.draw.polygon(pic, (120, 40, 12), _p(k, (15, 17), (18, 19), (16, 21)))
    for lx, ly in C_LIGHTS:
        pygame.draw.circle(pic, (50, 14, 12) if not dead else (20, 18, 18), (lx * k, ly * k), int(0.9 * k))


def picture(dead=False):
    """The picture of a launcher (TURRET_W x TURRET_H, muzzle to the left), standing or its wreck (made once)."""
    import scramble_base as sb
    pic = _PICS.get(bool(dead))
    if pic is None:
        big = pygame.Surface((UP[0] * K, UP[1] * K), pygame.SRCALPHA)
        _casemate(big, K, dead)
        big = pygame.transform.rotate(big, 90)                     # (muzzle up -> muzzle to the left)
        pic = _PICS[bool(dead)] = pygame.transform.smoothscale(big, (sb.TURRET_W, sb.TURRET_H))
    return pic


def state(t):
    """(state, seconds into it) of a turret: "wreck", "gone", "fire", "reload", "warn" or "idle"."""
    if not t.alive:
        return ("wreck", t.dead_for) if t.wreck else ("gone", 0.0)
    if t.fired is not None and t.fired < FIRE:
        return "fire", t.fired
    if t.fired is not None and t.fired < RELOAD:
        return "reload", t.fired
    if t.fire_in < WARN:
        return "warn", t.fire_in
    return "idle", 0.0


def _to_screen(l, tp, ux, uy):
    """A point of the standing drawing (logical) on the screen, the picture's top left at (l, tp)."""
    import scramble_base as sb
    return l + uy * sb.TURRET_W / UP[1], tp + (UP[0] - ux) * sb.TURRET_H / UP[0]


def draw(surface, t, l, tp, now):
    """A turret (or its wreck) whose box's top left is at (l, tp) on the screen, at the time `now`."""
    import asteroids
    import scramble_base as sb
    import scramble_view as sv
    st, age = state(t)
    if st == "gone":
        return
    cy = tp + sb.TURRET_H / 2.0
    if st == "wreck":
        surface.blit(picture(True), (round(l), round(tp)))
        ember = 0.5 + 0.5 * math.sin(now * 9.0 + t.y)
        asteroids._add_glow(surface, (200, 70, 20), (l + 10, cy), int(10 + 8 * ember))
        for i in range(3):                                         # smoke rising from the wreck
            p = (now * 0.55 + i / 3.0) % 1.0
            r = int(3 + 6 * p)
            puff = pygame.Surface((2 * r + 1, 2 * r + 1), pygame.SRCALPHA)
            pygame.draw.circle(puff, (70, 66, 64, int(150 * (1 - p))), (r, r), r)
            surface.blit(puff, (round(l + 10 + 6 * math.sin(i * 2.1 + p * 3) - r), round(cy - 4 - 30 * p - r)))
        return
    x = l + (KICK * (1.0 - age / FIRE) if st == "fire" else 0.0)
    if st in ("idle", "warn"):                                     # the missile waits in the tube, its nose out
        mi = sv._base_missile(0.0)
        surface.blit(mi, (round(x - NOSE_OUT), round(cy - mi.get_height() / 2)))
    surface.blit(picture(), (round(x), round(tp)))
    if st == "idle":
        lvl = 0.55 + 0.25 * math.sin(now * 2.4 + t.y)
    elif st == "warn":
        lvl = 1.0 if int(now * 14) % 2 == 0 else 0.15
    else:
        lvl = 1.0 if int(now * 5) % 2 == 0 else 0.2
    for ux, uy in C_LIGHTS:
        sx, sy = _to_screen(x, tp, ux, uy)
        asteroids._add_glow(surface, (255, 60, 40), (sx, sy), int(4 + 8 * lvl))
        pygame.draw.circle(surface, _mix((70, 20, 16), (255, 200, 180), lvl), (round(sx), round(sy)), 1)
    # its eye: red, flaring as it is about to fire
    ex0, ey0 = _to_screen(x, tp, 6, 21.1)
    ex1, ey1 = _to_screen(x, tp, 20, 18.5)
    glow = {"idle": 0.45, "warn": 0.6 + 0.4 * math.sin(now * 40), "fire": 1.0, "reload": 0.3}[st]
    col = _mix((60, 8, 8), (255, 70, 50), glow)
    pygame.draw.rect(surface, col, (round(ex0), round(ey1) + 1, max(1, round(ex1 - ex0)), round(ey0 - ey1) - 2))
    asteroids._add_glow(surface, (220, 30, 20), ((ex0 + ex1) / 2, (ey0 + ey1) / 2), int(10 + 10 * glow))
    if st in ("warn", "fire"):
        mx, my = _to_screen(x, tp, 13, 1)
        asteroids._add_glow(surface, (255, 60, 30), (mx, my), int(12 + 10 * glow))
    if st == "fire":                                               # the flash at the muzzle
        k = 1.0 - age / FIRE
        mx = l - 2
        asteroids._add_glow(surface, (255, 120, 60), (mx, cy), int(20 + 34 * k))
        star = [(mx - 14 * k - 4, cy), (mx - 2, cy - 4 * k - 1), (mx + 2, cy), (mx - 2, cy + 4 * k + 1)]
        pygame.draw.polygon(surface, _mix((255, 120, 60), (255, 255, 255), 0.6), star)
