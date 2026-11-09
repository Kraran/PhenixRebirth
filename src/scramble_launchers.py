"""The missile launchers of the base (src/scramble_base.py: Turret), as the player sees them: three looks to choose from
(LOOK), and the one of the first version ("current", scramble_view._turret_sprite).

A launcher is bolted on the face of the wall, its muzzle to the left. Each look is drawn standing (muzzle up, the wall
under it, on a canvas of 26 x 30 logical px, K times bigger), then turned a quarter to the left: the TURRET_W x TURRET_H
picture of the box of the turret (scramble_base.Turret.box), so nothing of the game changes, only its look. Its states:

- idle: its missile waits in it, the nose out, its lights steady;
- warn: in the last WARN seconds before it fires, its lights blink fast (the player sees it coming);
- fire: for FIRE seconds after a missile has left, a flash at the muzzle and a kick backwards;
- reload: until RELOAD seconds after it fired, empty, its lights blinking slowly;
- dead: shot down, its wreck stays on the wall, black and smoking (until the base blows up).

  A  "dome":   the launcher of the stations of the course (scramble_view._draw_station) laid on its side: a chrome dome, its
               rail, its glacier-blue lights; it fires the same chrome missile.
  B  "arcade": after the ground rockets of Konami's Scramble (1981): a red rocket with yellow fins in a cradle striped yellow
               and black, a red lamp; it fires that red rocket.
  C  "casemate": an armoured box in the gunmetal of the wall, a heavy tube behind a shutter, lit from inside in the red of
               the boss; it fires the chrome missile.
"""
import math

import pygame

LOOK = "current"                 # "current" (the first version), "A", "B" or "C"
LOOKS = ("current", "A", "B", "C")
K = 8                            # drawn 8 times bigger, then scaled (as the stations: smooth metal)
UP = (26, 30)                    # the logical canvas, standing (muzzle up)
FIRE = 0.22                      # seconds of the flash and the kick after a launch
RELOAD = 1.1                     # seconds without a missile after a launch
WARN = 0.5                       # seconds of fast blinking before a launch
KICK = 2.5                       # px it is pushed back to the wall by a launch
ICE = (120, 220, 255)
NOSE_OUT = {"A": 9, "B": 10, "C": 6}          # px of the waiting missile's nose out of the muzzle

_PICS = {}


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _sheen(pic, poly, stops):
    import scramble_view as sv
    sv._sheen(pic, poly, stops)


def _p(k, *pts):
    return [(x * k, y * k) for x, y in pts]


# ------------------------------------------------------------------ A: the chrome dome of the stations, on its side
A_LIGHTS = ((4, 27), (22, 27), (10, 4), (16, 4), (10, 9), (16, 9))  # (standing, logical): 2 on the plinth, 4 on the rail


def _a(pic, k, dead):
    w, h = pic.get_size()
    plinth = _p(k, (0, 30), (1.5, 25), (24.5, 25), (26, 30))
    _sheen(pic, plinth, [(0, (34, 38, 48)), (0.65, (104, 110, 128)), (1, (40, 44, 54))])
    pygame.draw.polygon(pic, (18, 20, 26), plinth, max(1, k // 2))
    for x in (3, 23):                                               # (the bolts on the wall)
        pygame.draw.circle(pic, (150, 156, 172), (x * k, int(28.2 * k)), int(0.9 * k))
    dome = pygame.Rect(1 * k, 7 * k, 24 * k, 36 * k)
    cx, cy, rx, ry = dome.centerx, dome.centery, dome.w / 2.0, dome.h / 2.0
    layer = pygame.Surface(pic.get_size(), pygame.SRCALPHA)
    hi, lo = ((235, 242, 255), (52, 60, 78)) if not dead else ((150, 134, 118), (34, 28, 26))
    for i in range(int(rx), 0, -1):
        t = i / rx
        pygame.draw.ellipse(layer, _mix(hi, lo, t ** 0.8) + (255,),
                            (cx - i + (1 - t) * 4 * k, cy - i * ry / rx - (1 - t) * 6 * k, 2 * i, 2 * i * ry / rx))
    clip = pygame.Surface(pic.get_size(), pygame.SRCALPHA)
    pygame.draw.ellipse(clip, (255, 255, 255, 255), dome)
    pygame.draw.rect(clip, (0, 0, 0, 0), (0, 25 * k, w, 5 * k))
    layer.blit(clip, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    pic.blit(layer, (0, 0))
    pygame.draw.arc(pic, (18, 20, 28), dome, 0, math.pi, max(1, k // 2))
    for dx in (-8 * k, 8 * k):                                      # its two ribs
        pygame.draw.line(pic, (60, 66, 84) if not dead else (30, 26, 24), (cx + dx, 25 * k), (cx + dx * 0.6, 11 * k),
                         max(1, k // 2))
    if dead:                                                       # torn open: a black hole, cracks, the rail broken off
        pygame.draw.ellipse(pic, (6, 4, 4), (8 * k, 12 * k, 11 * k, 9 * k))
        pygame.draw.ellipse(pic, (120, 40, 12), (10 * k, 15 * k, 6 * k, 4 * k))
        for a, b in (((13, 12), (8, 7)), ((17, 14), (22, 11)), ((10, 19), (5, 22)), ((16, 20), (20, 24))):
            pygame.draw.line(pic, (8, 6, 6), (a[0] * k, a[1] * k), (b[0] * k, b[1] * k), max(1, k // 3))
        stub = _p(k, (9, 13), (9, 6), (11, 4.5), (13, 6.5), (15, 3), (17, 5), (17, 13))
        pygame.draw.polygon(pic, (96, 90, 86), stub)
        pygame.draw.polygon(pic, (12, 10, 10), stub, max(1, k // 3))
    else:
        rail = _p(k, (8.5, 0), (17.5, 0), (17.5, 14), (8.5, 14))
        _sheen(pic, rail, [(0, (70, 76, 94)), (0.6, (210, 220, 236)), (1, (70, 76, 94))])
        pygame.draw.polygon(pic, (18, 20, 26), rail, max(1, k // 3))
        pygame.draw.rect(pic, (16, 18, 24), (11 * k, 0, 4 * k, 14 * k))           # the slot of the missile
    for lx, ly in A_LIGHTS:
        if not (dead and ly < 20):
            pygame.draw.circle(pic, (28, 52, 66) if not dead else (30, 28, 28), (lx * k, ly * k), int(1.0 * k))


# ------------------------------------------------------------------ B: the red rocket of the arcade, in its cradle
YELLOW, BLACK = (250, 196, 36), (26, 22, 18)
B_LIGHTS = ((13, 26),)


def _b(pic, k, dead):
    w, h = pic.get_size()
    # the plate on the wall, riveted, and its blast deflector
    plate = _p(k, (0, 30), (0, 24), (26, 24), (26, 30))
    _sheen(pic, plate, [(0, (44, 46, 54)), (0.65, (120, 124, 138) if not dead else (110, 100, 92)), (1, (48, 50, 58))])
    pygame.draw.polygon(pic, (16, 16, 20), plate, max(1, k // 3))
    for x in (2.2, 23.8):
        pygame.draw.circle(pic, (176, 180, 192), (int(x * k), 27 * k), int(0.9 * k))
    # the cradle: two arms striped yellow and black
    for side in (-1, 1):
        x0 = 13 + side * 6.5
        arm = _p(k, (x0 - 2, 24), (x0 + 2, 24), (x0 + 1.2, 5), (x0 - 1.2, 5)) if not dead else \
            _p(k, (x0 - 2, 24), (x0 + 2, 24), (x0 + 1.2 + side * 3, 13), (x0 - 1.2 + side * 4, 12))
        stripes = pygame.Surface(pic.get_size(), pygame.SRCALPHA)
        for y in range(0, 30, 3):
            pygame.draw.polygon(stripes, (YELLOW if not dead else (150, 116, 40)) + (255,),
                                _p(k, (0, y), (26, y - 2.2), (26, y - 0.7), (0, y + 1.5)))
            pygame.draw.polygon(stripes, (BLACK if not dead else (30, 24, 20)) + (255,),
                                _p(k, (0, y + 1.5), (26, y - 0.7), (26, y + 0.8), (0, y + 3)))
        mask = pygame.Surface(pic.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255), arm)
        stripes.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        pic.blit(stripes, (0, 0))
        pygame.draw.polygon(pic, (14, 12, 10), arm, max(1, k // 3))
    if not dead:
        for y in (8, 16):                                          # the clamps across
            pygame.draw.rect(pic, (70, 72, 82), (4.5 * k, y * k, 17 * k, 1.6 * k))
            pygame.draw.rect(pic, (170, 174, 186), (4.5 * k, y * k, 17 * k, 0.5 * k))
    else:
        pygame.draw.ellipse(pic, (10, 8, 8), (6 * k, 18 * k, 14 * k, 8 * k))      # scorched
        pygame.draw.ellipse(pic, (110, 36, 10), (10 * k, 21 * k, 6 * k, 3 * k))
        pygame.draw.line(pic, (60, 62, 70), (5 * k, 15 * k), (11 * k, 11 * k), int(1.4 * k))
    for lx, ly in B_LIGHTS:
        pygame.draw.circle(pic, (60, 16, 12) if not dead else (20, 18, 18), (lx * k, ly * k), int(1.2 * k))


def _b_rocket(pic, k):
    """The rocket of the cradle, nose up (logical 10 x 30): red, a white nose, yellow fins, as the arcade's."""
    w, h = pic.get_size()
    cx = w // 2
    body = [(cx - 3 * k, 8 * k), (cx + 3 * k, 8 * k), (cx + 3 * k, h - 5 * k), (cx - 3 * k, h - 5 * k)]
    _sheen(pic, body, [(0, (110, 14, 14)), (0.6, (255, 96, 80)), (0.8, (220, 40, 34)), (1, (120, 16, 16))])
    nose = [(cx, 0), (cx - 3 * k, 9 * k), (cx + 3 * k, 9 * k)]
    _sheen(pic, nose, [(0, (150, 140, 130)), (0.6, (255, 255, 250)), (1, (160, 150, 140))])
    pygame.draw.rect(pic, YELLOW, (cx - 3 * k, 12 * k, 6 * k, 1.5 * k))
    for side in (-1, 1):
        fin = [(cx + side * 3 * k, h - 13 * k), (cx + side * (w // 2 - 1), h - 3 * k), (cx + side * 3 * k, h - 5 * k)]
        pygame.draw.polygon(pic, YELLOW, fin)
        pygame.draw.polygon(pic, (150, 100, 10), fin, max(1, k // 3))
    pygame.draw.polygon(pic, YELLOW, [(cx - k, h - 13 * k), (cx + k, h - 13 * k), (cx + k, h - 4 * k), (cx - k, h - 4 * k)])
    pygame.draw.rect(pic, (60, 58, 62), (cx - 2.5 * k, h - 5 * k, 5 * k, 5 * k))


# ------------------------------------------------------------------ C: the armoured casemate, lit red from inside
C_LIGHTS = ((5, 26), (21, 26))


def _c(pic, k, dead):
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


DRAW = {"A": _a, "B": _b, "C": _c}


def picture(look, dead=False):
    """The picture of a launcher of that look (TURRET_W x TURRET_H, muzzle to the left), standing or a wreck (made once)."""
    import scramble_base as sb
    key = (look, bool(dead))
    pic = _PICS.get(key)
    if pic is None:
        big = pygame.Surface((UP[0] * K, UP[1] * K), pygame.SRCALPHA)
        DRAW[look](big, K, dead)
        big = pygame.transform.rotate(big, 90)                     # (muzzle up -> muzzle to the left)
        pic = _PICS[key] = pygame.transform.smoothscale(big, (sb.TURRET_W, sb.TURRET_H))
    return pic


def missile(look):
    """The missile of that look, nose up, at the size of the stations' (scramble_view.sprite("missile"))."""
    import scramble
    import scramble_view as sv
    if look != "B":
        return sv.sprite("missile", False)
    pic = _PICS.get("rocket")
    if pic is None:
        pic = _PICS["rocket"] = sv._aa(_b_rocket, (10, 30), (scramble.MISSILE_W, scramble.MISSILE_H), K)
    return pic


def flying(look, deg):
    """The missile in flight, its nose to the left, leaning `deg` degrees."""
    key = ("fly", look, deg)
    pic = _PICS.get(key)
    if pic is None:
        pic = _PICS[key] = pygame.transform.rotozoom(missile(look), 90 - deg, 1.0)
    return pic


def state(t):
    """(state, seconds into it) of a turret: "dead", "fire", "reload", "warn" or "idle"."""
    if not t.alive:
        return "dead", getattr(t, "dead_for", 0.0) or 0.0
    fired = getattr(t, "fired", None)
    if fired is not None and fired < FIRE:
        return "fire", fired
    if fired is not None and fired < RELOAD:
        return "reload", fired
    if t.fire_in < WARN:
        return "warn", t.fire_in
    return "idle", 0.0


def _lights(look):
    return {"A": A_LIGHTS, "B": B_LIGHTS, "C": C_LIGHTS}[look]


def _to_screen(l, tp, ux, uy):
    """A point of the standing drawing (logical) on the screen, the picture's top left at (l, tp)."""
    import scramble_base as sb
    return l + uy * sb.TURRET_W / UP[1], tp + (UP[0] - ux) * sb.TURRET_H / UP[0]


def draw(surface, t, l, tp, now, look=None, base_alive=True):
    """A turret whose box's top left is at (l, tp) on the screen, at the time `now`."""
    import asteroids
    import scramble_base as sb
    import scramble_view as sv
    look = look or LOOK
    st, age = state(t)
    cy = tp + sb.TURRET_H / 2.0
    if st == "dead":
        if not base_alive:
            return
        surface.blit(picture(look, True), (round(l), round(tp)))
        ember = 0.5 + 0.5 * math.sin(now * 9.0 + t.y)
        asteroids._add_glow(surface, (200, 70, 20), (l + 10, cy), int(10 + 8 * ember))
        for i in range(3):                                         # smoke rising from the wreck
            p = ((now * 0.55 + i / 3.0) % 1.0)
            r = int(3 + 6 * p)
            puff = pygame.Surface((2 * r + 1, 2 * r + 1), pygame.SRCALPHA)
            pygame.draw.circle(puff, (70, 66, 64, int(150 * (1 - p))), (r, r), r)
            surface.blit(puff, (round(l + 10 + 6 * math.sin(i * 2.1 + p * 3) - r), round(cy - 4 - 30 * p - r)))
        return
    kick = KICK * (1.0 - age / FIRE) if st == "fire" else 0.0
    x = l + kick
    loaded = st in ("idle", "warn")
    if loaded:                                                     # the missile waits in it, its nose out
        out = NOSE_OUT[look]
        mi = flying(look, 0)
        surface.blit(mi, (round(x - out), round(cy - mi.get_height() / 2)))
    surface.blit(picture(look), (round(x), round(tp)))
    # the lights
    if look == "A":
        base = int(round(4 + 4 * math.sin(now * 2.4 + t.y)))
        if st == "idle":
            rail = 8
        elif st == "warn":
            rail = 8 if int(now * 14) % 2 == 0 else 1
        else:
            rail = 8 if int(now * 6) % 2 == 0 else 1
        for i, (ux, uy) in enumerate(A_LIGHTS):
            sx, sy = _to_screen(x, tp, ux, uy)
            dot = sv._light(base if i < 2 else rail)
            half = dot.get_width() // 2
            surface.blit(dot, (round(sx) - half, round(sy) - half))
    else:
        if st == "idle":
            lvl = 0.55 + 0.25 * math.sin(now * 2.4 + t.y)
        elif st == "warn":
            lvl = 1.0 if int(now * 14) % 2 == 0 else 0.15
        else:
            lvl = 1.0 if int(now * 5) % 2 == 0 else 0.2
        for ux, uy in _lights(look):
            sx, sy = _to_screen(x, tp, ux, uy)
            asteroids._add_glow(surface, (255, 60, 40), (sx, sy), int(4 + 8 * lvl))
            pygame.draw.circle(surface, _mix((70, 20, 16), (255, 200, 180), lvl), (round(sx), round(sy)), 1)
        if look == "C":                                            # its eye: red, brighter as it is about to fire
            ex0, ey0 = _to_screen(x, tp, 6, 21.1)
            ex1, ey1 = _to_screen(x, tp, 20, 18.5)
            glow = {"idle": 0.45, "warn": 1.0, "fire": 1.0, "reload": 0.3}[st]
            if st == "warn":
                glow = 0.6 + 0.4 * math.sin(now * 40)
            col = _mix((60, 8, 8), (255, 70, 50), glow)
            pygame.draw.rect(surface, col, (round(ex0), round(ey1) + 1, max(1, round(ex1 - ex0)), round(ey0 - ey1) - 2))
            asteroids._add_glow(surface, (220, 30, 20), ((ex0 + ex1) / 2, (ey0 + ey1) / 2), int(10 + 10 * glow))
            if st in ("warn", "fire"):
                mx, my = _to_screen(x, tp, 13, 1)
                asteroids._add_glow(surface, (255, 60, 30), (mx, my), int(12 + 10 * glow))
    if st == "fire":                                               # the flash at the muzzle
        k = 1.0 - age / FIRE
        mx = l - 2
        col = {"A": (140, 220, 255), "B": (255, 200, 60), "C": (255, 120, 60)}[look]
        asteroids._add_glow(surface, col, (mx, cy), int(20 + 34 * k))
        star = [(mx - 14 * k - 4, cy), (mx - 2, cy - 4 * k - 1), (mx + 2, cy), (mx - 2, cy + 4 * k + 1)]
        pygame.draw.polygon(surface, _mix(col, (255, 255, 255), 0.6), star)
        if look == "B":                                            # the blast of the rocket against the deflector
            asteroids._add_glow(surface, (255, 150, 40), (l + sb.TURRET_W - 6, cy - 9), int(10 + 12 * k))
            asteroids._add_glow(surface, (255, 150, 40), (l + sb.TURRET_W - 6, cy + 9), int(10 + 12 * k))
