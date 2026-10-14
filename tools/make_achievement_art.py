"""Make the illustration of every achievement: assets/achievements/<id>.png (128 x 128, opaque).

    python tools/make_achievement_art.py            # needs pygame only
    python tools/make_achievement_art.py first_blood razor   # only these ones

Each picture is a small scene composed for its achievement: the game's own sprites (birds, gargoyles, saucer,
ships, Phenix, planets, items) put on stage with drawn effects (laser shots, explosions, lightning, glows, objects).
The game draws the card around it (src/achievements_screen.py): the metal of the frame is the tier, a locked
achievement is shown in grey, a secret one not found yet is a "?". Change a scene here and run the tool again.
Nothing is random from one run to the next (every scene has its own seed).
"""
import math
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
OUT_DIR = os.path.join(ASSETS, "achievements")
N = 128                      # size of a picture
C = N // 2


# --- helpers ---------------------------------------------------------------------------------------------------------
def load(*parts):
    return pygame.image.load(os.path.join(ASSETS, *parts)).convert_alpha()


def fit(img, w=None, h=None, rot=0):
    """`img` scaled to a width (or a height), then turned by `rot` degrees."""
    iw, ih = img.get_size()
    if w and not h:
        h = max(1, int(ih * w / iw))
    elif h and not w:
        w = max(1, int(iw * h / ih))
    if w and h:
        img = pygame.transform.smoothscale(img, (int(w), int(h)))
    if rot:
        img = pygame.transform.rotozoom(img, rot, 1.0)
    return img


def spr(name, w=None, h=None, rot=0):
    return fit(load("sprites", name), w, h, rot)


def trimmed(img):
    """The image cut to what is drawn (planets come with a transparent margin)."""
    return img.subsurface(img.get_bounding_rect(min_alpha=8)).copy()


def planet(name, size, rot=0):
    return fit(trimmed(load("sprites", "planets", name)), size, rot=rot)


def blit_c(dst, img, cx, cy):
    dst.blit(img, img.get_rect(center=(int(cx), int(cy))))


def glow(dst, cx, cy, r, col, strength=120, steps=24):
    """Additive light: brightest in the middle, nothing at radius r."""
    layer = pygame.Surface((N, N))
    layer.fill((0, 0, 0))
    k = strength / 255.0
    for i in range(steps, 0, -1):
        f = k * (1 - i / steps) ** 1.8
        pygame.draw.circle(layer, tuple(int(c * f) for c in col), (int(cx), int(cy)), max(1, int(r * i / steps)))
    dst.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)


def burst(dst, cx, cy, r, spikes=10, seed=1, cols=((255, 250, 210), (255, 200, 80), (255, 110, 40))):
    """A cartoon explosion: three star shapes, one inside the other."""
    rnd = random.Random(seed)
    for k, col in enumerate(reversed(cols)):
        rr = r * (1 - 0.28 * (len(cols) - 1 - k))
        pts = []
        for i in range(spikes * 2):
            a = math.pi * i / spikes + rnd.uniform(-0.12, 0.12)
            d = (rr if i % 2 == 0 else rr * 0.45) * rnd.uniform(0.8, 1.1)
            pts.append((cx + math.cos(a) * d, cy + math.sin(a) * d))
        pygame.draw.polygon(dst, col, pts)


def sparks(dst, cx, cy, r0, r1, n, seed, col=(255, 200, 80)):
    rnd = random.Random(seed)
    for _ in range(n):
        a, d = rnd.uniform(0, 2 * math.pi), rnd.uniform(r0, r1)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        pygame.draw.line(dst, col, (x, y), (x + math.cos(a) * 3, y + math.sin(a) * 3), 1)


def space(seed, top=(14, 20, 52), bottom=(4, 5, 14), stars=26):
    """The background: a dark blue gradient and a few stars."""
    s = pygame.Surface((N, N))
    for y in range(N):
        f = y / (N - 1)
        pygame.draw.line(s, [int(top[i] * (1 - f) + bottom[i] * f) for i in range(3)], (0, y), (N, y))
    rnd = random.Random(seed)
    for _ in range(stars):
        x, y = rnd.randrange(N), rnd.randrange(N)
        b = rnd.randrange(110, 230)
        s.set_at((x, y), (b, b, min(255, b + 20)))
        if rnd.random() < 0.15:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                s.set_at(((x + dx) % N, (y + dy) % N), (b // 2, b // 2, b // 2 + 10))
    return s


def lightning(dst, x, y0, y1, seed, col=(150, 230, 255), wobble=5):
    rnd = random.Random(seed)
    pts, y = [], y0
    while y < y1:
        pts.append((x + rnd.uniform(-wobble, wobble), y))
        y += rnd.uniform(5, 10)
    pts.append((x, y1))
    layer = pygame.Surface((N, N), pygame.SRCALPHA)
    pygame.draw.lines(layer, (*col, 70), False, pts, 9)
    pygame.draw.lines(layer, (*col, 160), False, pts, 4)
    pygame.draw.lines(layer, (240, 255, 255, 255), False, pts, 2)
    dst.blit(layer, (0, 0))


def beam(dst, x0, y0, x1, y1, col=(255, 70, 70), core=(255, 190, 170), width=9):
    """A laser shot: a soft wide line and a bright core."""
    layer = pygame.Surface((N, N), pygame.SRCALPHA)
    pygame.draw.line(layer, (*col, 80), (x0, y0), (x1, y1), width)
    pygame.draw.line(layer, (*col, 170), (x0, y0), (x1, y1), max(2, width // 2))
    pygame.draw.line(layer, (*core, 255), (x0, y0), (x1, y1), 2)
    dst.blit(layer, (0, 0))


def alpha(img, a):
    img = img.copy()
    img.set_alpha(a)
    return img


def note(dst, x, y, col, size=1.0):
    """A quaver."""
    r = int(6 * size)
    pygame.draw.ellipse(dst, col, (x - r * 2 + 2, y + int(18 * size), int(r * 2.2), int(r * 1.7)))
    pygame.draw.line(dst, col, (x + 1, y + int(22 * size)), (x + 1, y - int(8 * size)), max(2, int(3 * size)))
    pygame.draw.polygon(dst, col, [(x + 1, y - int(8 * size)), (x + int(13 * size), y - int(2 * size)),
                                   (x + int(13 * size), y + int(4 * size)), (x + 1, y - int(2 * size))])


def digits(dst, text, cx, cy, h, col, glow_col=None, off=(30, 34, 40)):
    """Numbers drawn as seven-segment digits (no font needed); `off`: colour of the unlit segments (None: not drawn)."""
    segs = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc",
            "7": "abc", "8": "abcdefg", "9": "abcfgd"}
    w = h // 2
    gap = w // 2
    total = len(text) * w + (len(text) - 1) * gap
    x = cx - total // 2
    t = max(2, h // 9)
    for ch in text:
        on = segs.get(ch, "")
        pos = {"a": (x, cy - h // 2, w, t), "g": (x, cy - t // 2, w, t), "d": (x, cy + h // 2 - t, w, t),
               "f": (x, cy - h // 2, t, h // 2), "b": (x + w - t, cy - h // 2, t, h // 2),
               "e": (x, cy, t, h // 2), "c": (x + w - t, cy, t, h // 2)}
        for name, rect in pos.items():
            colour = col if name in on else off
            if colour is not None:
                pygame.draw.rect(dst, colour, rect)
        x += w + gap
    if glow_col:
        glow(dst, cx, cy, total // 2 + 14, glow_col, 70)


def gear(dst, cx, cy, r, teeth, col, hole=(20, 22, 30)):
    pts = []
    for i in range(teeth * 4):
        a = 2 * math.pi * i / (teeth * 4)
        d = r if (i % 4) in (1, 2) else r * 0.78
        pts.append((cx + math.cos(a) * d, cy + math.sin(a) * d))
    pygame.draw.polygon(dst, col, pts)
    pygame.draw.circle(dst, hole, (int(cx), int(cy)), int(r * 0.32))


def laurel(dst, cx, cy, r, col=(230, 190, 70)):
    for side in (-1, 1):
        for i in range(7):
            a = math.radians(110 + i * 18) if side < 0 else math.radians(70 - i * 18)
            x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
            leaf = [(x, y - 5), (x + 4 * side, y), (x, y + 5), (x - 4 * side, y)]
            pygame.draw.polygon(dst, col, leaf)


# --- the scenes: page ARCADE -----------------------------------------------------------------------------------------
def first_blood(s):
    glow(s, C, C - 4, 50, (255, 120, 40), 110)
    beam(s, C, N, C, C + 14)
    blit_c(s, spr("bird1_flap0.png", 80), C, C - 8)
    burst(s, C, C + 16, 12, spikes=8, seed=3)
    rnd = random.Random(4)
    for _ in range(10):
        x, y = C + rnd.uniform(-40, 40), C + rnd.uniform(10, 40)
        pygame.draw.line(s, (110, 160, 255), (x, y), (x + rnd.uniform(-5, 5), y + 5), 2)


def stage2(s):
    earth = planet("earth.png", 230)
    blit_c(s, earth, C, N + 70)
    glow(s, C, N + 20, 90, (90, 170, 255), 150)
    for i, dx in enumerate((-4, 0, 4)):
        pygame.draw.line(s, (255, 200, 120), (C + dx, C + 30), (C + dx * 3, N - 18 + i * 3), 2)
    glow(s, C, C + 30, 18, (255, 170, 80), 220)
    blit_c(s, spr("player_ship.png", 38), C, C + 4)


def boss_down(s):
    glow(s, C, C + 10, 50, (255, 90, 30), 110)
    blit_c(s, spr("boss_saucer.png", 112, rot=-14), C, C + 6)
    crack = [(C - 22, C - 6), (C - 10, C + 2), (C - 14, C + 10), (C + 2, C + 16), (C - 2, C + 26), (C + 14, C + 30)]
    pygame.draw.lines(s, (255, 230, 150), False, crack, 3)
    pygame.draw.lines(s, (255, 255, 255), False, crack, 1)
    burst(s, C + 26, C - 4, 16, spikes=9, seed=7)
    burst(s, C - 26, C + 20, 10, spikes=7, seed=8)
    sparks(s, C, C + 6, 26, 52, 18, 9)


def loop(s):
    # the ship comes back round: a loop of light that ends in an arrow, a 6 in its middle
    layer = pygame.Surface((N, N), pygame.SRCALPHA)
    rect = pygame.Rect(C - 42, C - 42, 84, 84)
    for w, a in ((11, 50), (6, 120), (2, 255)):
        pygame.draw.arc(layer, (120, 200, 255, a), rect, math.radians(-40), math.radians(250), w)
    s.blit(layer, (0, 0))
    tip = (C + math.cos(math.radians(-40)) * 42, C - math.sin(math.radians(-40)) * 42)
    pygame.draw.polygon(s, (200, 240, 255), [(tip[0] - 9, tip[1] - 4), (tip[0] + 7, tip[1] - 8), (tip[0] + 2, tip[1] + 9)])
    blit_c(s, spr("player_ship.png", 24, rot=100), C - 30, C - 30)
    digits(s, "6", C, C + 2, 34, (255, 200, 90), (255, 160, 60), off=None)


def one_up_1337(s):
    pygame.draw.rect(s, (12, 16, 14), (10, 30, N - 20, 50), border_radius=6)
    pygame.draw.rect(s, (60, 80, 70), (10, 30, N - 20, 50), 2, border_radius=6)
    digits(s, "1337", C, 55, 30, (90, 255, 140), (60, 255, 120))
    blit_c(s, spr("player_ship.png", 24), C - 18, 104)
    up = [(C + 8, 108), (C + 18, 96), (C + 28, 108)]
    pygame.draw.polygon(s, (90, 255, 140), up)
    pygame.draw.rect(s, (90, 255, 140), (C + 14, 107, 8, 10))


def elite_8086(s):
    # a chip of the old times, its pins and its number
    body = pygame.Rect(22, 30, 84, 66)
    for i in range(8):
        x = body.x + 8 + i * 10
        pygame.draw.rect(s, (200, 200, 210), (x, body.y - 9, 5, 10))
        pygame.draw.rect(s, (200, 200, 210), (x, body.bottom - 1, 5, 10))
    pygame.draw.rect(s, (28, 28, 34), body, border_radius=4)
    pygame.draw.rect(s, (70, 70, 84), body, 2, border_radius=4)
    pygame.draw.circle(s, (60, 60, 72), (body.x + 10, body.y + 10), 4)
    digits(s, "8086", C, C + 4, 22, (230, 230, 240))
    glow(s, C, C + 4, 60, (90, 130, 255), 60)


def phenix_wake(s):
    glow(s, C, C + 6, 64, (255, 110, 20), 230)
    glow(s, C, C + 26, 34, (255, 220, 120), 200)
    blit_c(s, spr("phenix/phenix_00.png", 84), C, C + 6)
    rnd = random.Random(12)
    for _ in range(18):
        x, y = C + rnd.uniform(-44, 44), C + rnd.uniform(10, 54)
        pygame.draw.circle(s, (255, rnd.randrange(140, 230), 40), (int(x), int(y)), rnd.choice((1, 1, 2)))


def iron_curtain(s):
    blit_c(s, spr("player_ship_shield.png", 40), C, C + 22)
    dome = pygame.Surface((N, N), pygame.SRCALPHA)
    pygame.draw.circle(dome, (90, 220, 255, 50), (C, C + 22), 38)
    for r in range(38, 32, -1):
        pygame.draw.circle(dome, (140, 240, 255, 30 + (38 - r) * 18), (C, C + 22), r, 1)
    for hy in range(-3, 3):
        for hx in range(-3, 4):
            x, y = C + hx * 13 + (6 if hy % 2 else 0), C + 22 + hy * 11
            if (x - C) ** 2 + (y - C - 22) ** 2 < 34 ** 2:
                pts = [(x + 6 * math.cos(a), y + 6 * math.sin(a)) for a in [math.pi / 3 * i + math.pi / 6 for i in range(6)]]
                pygame.draw.polygon(dome, (160, 245, 255, 60), pts, 1)
    s.blit(dome, (0, 0))
    for bx, by, ang in ((C - 30, C - 30, 0.6), (C + 4, C - 38, -0.2), (C + 30, C - 26, -0.9)):
        hx, hy = bx + math.sin(ang) * 12, by + 14
        pygame.draw.line(s, (255, 80, 80), (bx, by), (hx, hy), 3)
        pygame.draw.circle(s, (255, 220, 200), (int(hx), int(hy)), 3)
        glow(s, hx, hy, 9, (120, 230, 255), 160)


def mixed_squad(s):
    planet_img = planet("neptune.png", 70)
    blit_c(s, alpha(planet_img, 200), C + 34, C - 30)
    beam(s, C - 22, C - 6, C - 22, -4, col=(120, 180, 255), core=(220, 240, 255), width=6)
    beam(s, C + 22, C - 6, C + 22, -4, col=(255, 120, 60), core=(255, 230, 190), width=6)
    blit_c(s, spr("player_ship.png", 36), C - 22, C + 24)
    blit_c(s, spr("player_ship_shield.png", 36), C + 22, C + 24)


def survivor(s):
    rnd = random.Random(15)
    for _ in range(14):
        x = rnd.choice((rnd.uniform(6, C - 20), rnd.uniform(C + 20, N - 6)))
        y = rnd.uniform(4, N - 10)
        pygame.draw.line(s, (255, 90, 80), (x, y), (x, y + 10), 3)
        pygame.draw.circle(s, (255, 210, 190), (int(x), int(y + 10)), 2)
    glow(s, C, C + 10, 36, (120, 255, 170), 120)
    blit_c(s, spr("player_ship.png", 40), C, C + 12)


def ten_flags(s):
    blit_c(s, alpha(spr("boss_saucer.png", 120), 220), C, N - 18)
    pygame.draw.line(s, (210, 210, 220), (C - 18, N - 36), (C - 18, 14), 3)
    cloth = [(C - 16, 16), (C + 42, 22), (C + 34, 36), (C + 44, 50), (C - 16, 46)]
    pygame.draw.polygon(s, (190, 36, 46), cloth)
    pygame.draw.polygon(s, (240, 90, 90), cloth, 2)
    digits(s, "10", C + 12, 32, 18, (255, 230, 200), off=None)
    glow(s, C, 30, 50, (255, 120, 80), 60)


def veteran_clear(s):
    glow(s, C, C - 6, 58, (200, 40, 40), 150)
    blit_c(s, spr("boss_core_00.png", 96), C, C - 8)
    blit_c(s, spr("icon_veteran.png", h=44), C + 34, C + 34)


def no_edge(s):
    lightning(s, 14, 0, N, 21)
    lightning(s, N - 14, 0, N, 22)
    for i, x in enumerate((C - 6, C + 6, C)):
        pygame.draw.line(s, (120, 160, 255), (x, C + 30 + i * 4), (x, N), 1)
    blit_c(s, spr("player_ship.png", 36), C, C + 14)
    glow(s, C, C + 40, 18, (120, 180, 255), 200)


def hotseat(s):
    # two arcade sticks: the first one is put down, the second one is taken
    for cx, col, lit in ((C - 26, (60, 120, 255), False), (C + 26, (255, 70, 70), True)):
        base = pygame.Rect(cx - 22, C + 26, 44, 18)
        pygame.draw.rect(s, (40, 40, 52), base, border_radius=6)
        pygame.draw.rect(s, (90, 90, 110), base, 2, border_radius=6)
        top = (cx + (8 if lit else 0), C - 6)
        pygame.draw.line(s, (200, 200, 210), (cx, C + 28), top, 4)
        pygame.draw.circle(s, col, top, 11)
        pygame.draw.circle(s, (255, 255, 255), (top[0] - 3, top[1] - 4), 3)
        if lit:
            glow(s, top[0], top[1], 24, col, 160)
    digits(s, "2", C + 26, 22, 18, (255, 220, 120), off=None)
    digits(s, "1", C - 26, 22, 18, (90, 110, 150), off=None)


def gauge_max(s):
    x0, y0 = C - 14, 14
    for i in range(10):
        y = y0 + (9 - i) * 10
        col = (255, 60 + i * 18, 30)
        pygame.draw.rect(s, col, (x0, y, 28, 8), border_radius=2)
    pygame.draw.rect(s, (200, 200, 220), (x0 - 4, y0 - 4, 36, 104), 2, border_radius=4)
    glow(s, C, C, 60, (255, 130, 40), 140)
    sparks(s, C, 16, 6, 26, 14, 33, (255, 230, 120))
    blit_c(s, spr("phenix_gauge_label.png", 40), C, N - 10)


def credits_watch(s):
    # lines of text rising towards the stars, smaller and smaller
    for i in range(9):
        f = i / 8
        y = N - 14 - i * 12
        w = int(96 * (1 - 0.7 * f))
        col = (int(255 - 80 * f), int(220 - 90 * f), int(120 - 60 * f))
        rnd = random.Random(40 + i)
        x = C - w // 2
        while x < C + w // 2:
            ww = int(rnd.uniform(6, 18) * (1 - 0.6 * f))
            pygame.draw.rect(s, col, (x, y, min(ww, C + w // 2 - x), max(1, int(4 * (1 - 0.6 * f)))))
            x += ww + max(2, int(5 * (1 - 0.6 * f)))
    glow(s, C, 10, 40, (255, 220, 160), 60)


def listen_menu(s):
    cx, cy = C - 4, C + 8
    pygame.draw.circle(s, (20, 20, 26), (cx, cy), 40)
    for r in range(38, 16, -3):
        pygame.draw.circle(s, (44, 44, 56), (cx, cy), r, 1)
    pygame.draw.arc(s, (120, 120, 150), (cx - 34, cy - 34, 68, 68), 2.2, 2.9, 2)
    pygame.draw.circle(s, (240, 150, 60), (cx, cy), 14)
    pygame.draw.circle(s, (255, 210, 120), (cx, cy), 14, 2)
    pygame.draw.circle(s, (20, 20, 26), (cx, cy), 2)
    glow(s, C + 26, C - 14, 22, (255, 200, 80), 80)
    note(s, C + 26, C - 22, (255, 220, 90))
    # a dawn behind: Eternal Dawn
    glow(s, C, N + 10, 70, (255, 120, 60), 120)


def listen_hs(s):
    # a cassette
    body = pygame.Rect(16, 34, 96, 62)
    pygame.draw.rect(s, (36, 36, 46), body, border_radius=6)
    pygame.draw.rect(s, (100, 100, 120), body, 2, border_radius=6)
    pygame.draw.rect(s, (220, 70, 70), (24, 40, 80, 18), border_radius=3)
    pygame.draw.line(s, (255, 230, 230), (30, 49), (98, 49), 2)
    pygame.draw.rect(s, (16, 16, 20), (36, 62, 56, 22), border_radius=8)
    for x in (48, 80):
        pygame.draw.circle(s, (200, 200, 210), (x, 73), 8)
        pygame.draw.circle(s, (16, 16, 20), (x, 73), 3)
    pygame.draw.polygon(s, (60, 60, 74), [(36, 96), (44, 86), (84, 86), (92, 96)])
    note(s, C + 34, 6, (255, 220, 90), 0.7)
    glow(s, C, C + 10, 64, (255, 80, 80), 50)


def listen_credits(s):
    # the last coin, spinning, a note above it
    glow(s, C, C + 12, 50, (255, 200, 60), 130)
    pygame.draw.circle(s, (180, 130, 30), (C, C + 14), 34)
    pygame.draw.circle(s, (240, 200, 70), (C, C + 12), 34)
    pygame.draw.circle(s, (255, 230, 130), (C, C + 12), 34, 3)
    pygame.draw.circle(s, (200, 150, 40), (C, C + 12), 25, 2)
    digits(s, "1", C, C + 12, 26, (150, 100, 20), off=None)
    note(s, C + 34, C - 50, (255, 220, 90), 0.7)


def listen_nostalgie_start(s):
    # an old radio, waves coming out of it
    body = pygame.Rect(18, 40, 92, 64)
    pygame.draw.rect(s, (120, 70, 40), body, border_radius=16)
    pygame.draw.rect(s, (170, 110, 60), body, 3, border_radius=16)
    pygame.draw.circle(s, (60, 40, 30), (48, 72), 20)
    for r in range(18, 4, -4):
        pygame.draw.circle(s, (90, 60, 40), (48, 72), r, 1)
    pygame.draw.rect(s, (230, 210, 150), (76, 56, 26, 12), border_radius=2)
    pygame.draw.line(s, (200, 60, 50), (88, 56), (88, 68), 2)
    for k in (82, 96):
        pygame.draw.circle(s, (200, 170, 110), (k, 86), 5)
    for r in (12, 20, 28):
        pygame.draw.arc(s, (255, 210, 120), (C - r, 26 - r, 2 * r, 2 * r), math.radians(30), math.radians(150), 2)
    glow(s, C, 26, 30, (255, 190, 90), 70)


def listen_nostalgie_elise(s):
    # piano keys, a note
    y0 = C + 4
    for i in range(9):
        pygame.draw.rect(s, (235, 235, 230), (6 + i * 13, y0, 12, 50))
        pygame.draw.rect(s, (150, 150, 150), (6 + i * 13, y0, 12, 50), 1)
    for i in (0, 1, 3, 4, 5, 7):
        pygame.draw.rect(s, (20, 20, 24), (14 + i * 13, y0, 8, 30))
    pygame.draw.rect(s, (255, 220, 120), (6 + 4 * 13, y0, 12, 50), 3)
    glow(s, 6 + 4 * 13 + 6, y0 + 10, 30, (255, 200, 100), 120)
    note(s, C + 18, 10, (255, 230, 150), 0.9)
    note(s, C - 22, 20, (200, 220, 255), 0.6)


def listen_music_all(s):
    # a jukebox
    body = [(C - 40, N - 6), (C - 40, 46), (C + 40, 46), (C + 40, N - 6)]
    pygame.draw.polygon(s, (110, 40, 40), body)
    pygame.draw.circle(s, (110, 40, 40), (C, 46), 40)
    for r, col in ((36, (255, 170, 60)), (30, (255, 90, 160)), (24, (110, 200, 255))):
        pygame.draw.arc(s, col, (C - r, 46 - r, 2 * r, 2 * r), 0, math.pi, 4)
    pygame.draw.rect(s, (30, 30, 40), (C - 26, 52, 52, 30), border_radius=4)
    for i in range(5):
        pygame.draw.line(s, (255, 220, 140), (C - 20, 58 + i * 5), (C + 20, 58 + i * 5), 1)
    for i, col in enumerate(((255, 170, 60), (255, 90, 160), (110, 200, 255), (120, 255, 150))):
        pygame.draw.rect(s, col, (C - 30 + i * 16, 92, 12, 18), border_radius=3)
    glow(s, C, 40, 52, (255, 150, 80), 90)


def clean_shot(s):
    for r, col in ((44, (200, 50, 50)), (34, (235, 235, 235)), (24, (200, 50, 50)), (14, (235, 235, 235)), (6, (200, 50, 50))):
        pygame.draw.circle(s, col, (C, C), r)
    for dx, dy in ((0, 0), (3, -2), (-2, 2), (1, 3)):
        pygame.draw.circle(s, (30, 30, 30), (C + dx, C + dy), 2)
    pygame.draw.line(s, (120, 255, 160), (C - 56, C), (C + 56, C), 1)
    pygame.draw.line(s, (120, 255, 160), (C, C - 56), (C, C + 56), 1)
    glow(s, C, C, 20, (255, 240, 200), 120)


def razor(s):
    lightning(s, N - 22, 0, N, 51, wobble=6)
    glow(s, N - 26, C, 50, (120, 220, 255), 120)
    blit_c(s, spr("player_ship.png", 34, rot=-35), C - 10, C + 8)
    burst(s, C + 18, C - 4, 18, spikes=9, seed=52, cols=((240, 255, 255), (150, 230, 255), (60, 140, 255)))
    sparks(s, C + 18, C - 4, 18, 40, 16, 53, (180, 240, 255))


def butcher(s):
    beam(s, C - 30, N, C - 6, C + 10)
    blit_c(s, spr("bird2_flap0.png", 66, rot=-150), C + 4, C - 6)
    for i in range(4):
        pygame.draw.line(s, (160, 220, 120), (C + 24 + i * 6, C - 46 + i * 4), (C + 40 + i * 6, C - 62 + i * 4), 1)
    burst(s, C - 6, C + 10, 12, spikes=8, seed=55)


def wrecker(s):
    rnd = random.Random(60)
    for row in range(4):
        for col in range(7):
            x = 4 + col * 18 + (9 if row % 2 else 0)
            y = 54 + row * 12
            if rnd.random() < 0.28 and row < 3:
                continue
            pygame.draw.rect(s, (90, 90, 104), (x, y, 16, 10))
            pygame.draw.rect(s, (140, 140, 156), (x, y, 16, 10), 1)
    for _ in range(8):
        x, y = rnd.uniform(20, 108), rnd.uniform(14, 48)
        pygame.draw.rect(s, (120, 120, 134), (x, y, rnd.randrange(4, 9), rnd.randrange(3, 7)))
    beam(s, C + 10, N, C + 10, 60)
    burst(s, C + 10, 58, 14, spikes=8, seed=61)


def cutter(s):
    deco = spr("saucer_deco_dish_l.png", 90)
    w, h = deco.get_size()
    top = deco.subsurface((0, 0, w, h // 2)).copy()
    bottom = deco.subsurface((0, h // 2, w, h - h // 2)).copy()
    s.blit(top, (C - w // 2 - 6, C - h // 2 - 8))
    s.blit(bottom, (C - w // 2 + 6, C + 4))
    beam(s, 0, C - 2, N, C - 2, col=(255, 90, 60), core=(255, 230, 200), width=5)
    sparks(s, C, C - 2, 6, 30, 16, 62)


def duo_fire(s):
    glow(s, C - 26, C + 6, 44, (255, 110, 30), 200)
    blit_c(s, spr("phenix/phenix_00.png", 54), C - 26, C + 4)
    blit_c(s, spr("player_ship_shield.png", 30), C + 28, C + 18)
    dome = pygame.Surface((N, N), pygame.SRCALPHA)
    pygame.draw.circle(dome, (90, 220, 255, 60), (C + 28, C + 18), 26)
    pygame.draw.circle(dome, (160, 245, 255, 200), (C + 28, C + 18), 26, 2)
    s.blit(dome, (0, 0))
    glow(s, C + 28, C + 18, 30, (90, 220, 255), 90)


def marathon(s):
    # a stopwatch, its hand running, the numbers turning
    pygame.draw.rect(s, (200, 200, 210), (C - 6, 14, 12, 10), border_radius=2)
    pygame.draw.circle(s, (210, 210, 220), (C, C + 8), 42)
    pygame.draw.circle(s, (20, 24, 36), (C, C + 8), 36)
    for i in range(12):
        a = 2 * math.pi * i / 12
        pygame.draw.line(s, (200, 200, 220), (C + math.cos(a) * 30, C + 8 + math.sin(a) * 30),
                         (C + math.cos(a) * 34, C + 8 + math.sin(a) * 34), 2)
    layer = pygame.Surface((N, N), pygame.SRCALPHA)
    pygame.draw.polygon(layer, (255, 170, 60, 90), [(C, C + 8)] + [(C + math.cos(a) * 33, C + 8 + math.sin(a) * 33)
                                                                 for a in [math.radians(d) for d in range(-90, 200, 10)]])
    s.blit(layer, (0, 0))
    pygame.draw.line(s, (255, 220, 120), (C, C + 8), (C + math.cos(math.radians(200)) * 30, C + 8 + math.sin(math.radians(200)) * 30), 3)
    pygame.draw.circle(s, (255, 220, 120), (C, C + 8), 4)


def pleiades(s):
    neb = pygame.Surface((N, N))
    neb.fill((0, 0, 0))
    glow(neb, C + 10, C - 4, 58, (60, 90, 200), 150)
    glow(neb, C - 14, C + 10, 40, (110, 70, 200), 120)
    s.blit(neb, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    for dx, dy, r in ((-24, -14, 5), (-12, -22, 4), (2, -12, 6), (-6, 0, 4), (14, -2, 5), (24, -18, 3), (10, 14, 4)):
        x, y = C + dx, C + dy + 4
        glow(s, x, y, r * 3, (150, 190, 255), 255)
        pygame.draw.line(s, (220, 235, 255), (x - r * 2, y), (x + r * 2, y), 1)
        pygame.draw.line(s, (220, 235, 255), (x, y - r * 2), (x, y + r * 2), 1)
        pygame.draw.circle(s, (255, 255, 255), (x, y), max(1, r // 2))


def port_pair(s):
    for side, x in (("l", C - 30), ("r", C + 30)):
        blit_c(s, spr("saucer_deco_port_%s.png" % side, 60), x, C + 6)
        burst(s, x, C + 4, 14, spikes=8, seed=70 if side == "l" else 71)
    pygame.draw.line(s, (255, 230, 150), (C - 50, C + 30), (C + 50, C + 30), 1)
    sparks(s, C, C, 20, 60, 20, 72)


def boldly_go(s):
    px, py = C - 24, C + 30
    pygame.draw.ellipse(s, (200, 150, 90), (px - 52, py - 8, 104, 16), 3)
    blit_c(s, planet("mars.png", 52), px, py)
    pygame.draw.arc(s, (240, 190, 120), (px - 52, py - 8, 104, 16), math.pi, 2 * math.pi, 3)
    beam(s, C - 10, C + 10, C + 30, C - 30, col=(120, 200, 255), core=(220, 245, 255), width=7)
    blit_c(s, spr("player_ship.png", 22, rot=-45), C + 32, C - 32)
    glow(s, C + 44, C - 44, 14, (255, 255, 220), 200)


# --- the scenes: page AVENTURE ---------------------------------------------------------------------------------------
def adv_pilot(s):
    card = pygame.Rect(18, 26, 92, 74)
    pygame.draw.rect(s, (210, 214, 224), card, border_radius=8)
    pygame.draw.rect(s, (80, 120, 200), (card.x, card.y, card.w, 16), border_top_left_radius=8, border_top_right_radius=8)
    # helmet
    pygame.draw.circle(s, (90, 96, 110), (44, 68), 20)
    pygame.draw.ellipse(s, (255, 150, 60), (30, 58, 28, 16))
    pygame.draw.ellipse(s, (255, 220, 150), (34, 60, 10, 6))
    for i in range(4):
        pygame.draw.line(s, (90, 96, 110), (72, 50 + i * 8), (102, 50 + i * 8), 3)
    for i in range(12):
        pygame.draw.line(s, (30, 30, 40), (72 + i * 2 + (i % 3), 88), (72 + i * 2 + (i % 3), 96), 1 + (i % 2))
    pygame.draw.circle(s, (255, 220, 120), (100, 34), 4)


def _flight(s, sprite, planet_name, seed, tint=None):
    blit_c(s, planet(planet_name, 120), C + 30, N + 10)
    rnd = random.Random(seed)
    for (x, y, w, rot) in ((C - 26, 36, 34, 8), (C + 14, 28, 30, -6), (C - 4, 64, 40, 0)):
        blit_c(s, spr(sprite, w, rot=rot + rnd.uniform(-4, 4)), x, y)


def adv_sortie(s):
    _flight(s, "bird1_flap0.png", "mars.png", 101)


def adv_kaki(s):
    _flight(s, "bird2_flap1.png", "venus.png", 102)


def adv_garg(s):
    blit_c(s, alpha(planet("saturn.png", 150), 230), C + 10, N - 8)
    glow(s, C, C - 14, 50, (150, 160, 200), 70)
    blit_c(s, spr("garg3_full.png", 128), C, C - 14)


def adv_shadow(s):
    blit_c(s, alpha(planet("uranus.png", 110), 170), C - 20, N)
    glow(s, C, C, 50, (160, 60, 200), 90)
    blit_c(s, spr("garg4_body.png", 64), C + 4, C - 6)
    blit_c(s, spr("garg4_wing_up.png", 46), C - 32, C - 18)
    blit_c(s, pygame.transform.flip(spr("garg4_wing_up.png", 46), True, False), C + 40, C - 18)


def adv_domes(s):
    blit_c(s, spr("player_ship_shield.png", 34), C, C + 20)
    dome = load("sprites", "shield", "loop_00.png")
    blit_c(s, fit(dome, 84), C, C + 16)
    for i in range(5):
        a = math.radians(200 + i * 35)
        x, y = C + math.cos(a) * 52, C + 16 + math.sin(a) * 52
        pygame.draw.circle(s, (120, 230, 255), (int(x), int(y)), 6, 2)
        pygame.draw.circle(s, (200, 250, 255), (int(x), int(y)), 2)


def adv_reactor(s):
    beam(s, C, 0, C, N, col=(90, 200, 255), core=(200, 245, 255), width=30)
    glow(s, C, C, 50, (90, 200, 255), 160)
    blit_c(s, fit(load("items", "reactor_icon.png"), 70), C, C)


def adv_act2(s):
    # the gate to the second act: a ring of light, the ship flying through
    blit_c(s, alpha(fit(load("sprites", "nebulae", "nebula_helix.png"), 150), 200), C, C)
    layer = pygame.Surface((N, N), pygame.SRCALPHA)
    pygame.draw.ellipse(layer, (255, 200, 120, 220), (C - 40, C - 24, 80, 48), 4)
    s.blit(layer, (0, 0))
    blit_c(s, spr("player_ship.png", 26), C, C + 6)
    for x in (C - 6, C + 6):
        pygame.draw.rect(s, (255, 230, 170), (x - 2, 8, 5, 22))
    pygame.draw.rect(s, (255, 230, 170), (C - 12, 6, 24, 3))
    pygame.draw.rect(s, (255, 230, 170), (C - 12, 30, 24, 3))


def adv_commander(s):
    blit_c(s, alpha(planet("earth.png", 150), 200), C, N + 30)
    glow(s, C, C - 10, 54, (220, 40, 40), 120)
    blit_c(s, spr("boss_core_00.png", 100), C, C - 12)


def adv_phenix(s):
    glow(s, C, N, 80, (255, 140, 40), 220)
    blit_c(s, alpha(spr("phenix/phenix_00.png", 110), 170), C, C - 4)
    blit_c(s, spr("player_ship.png", 36), C, C + 30)


def adv_paint(s):
    pygame.draw.rect(s, (110, 120, 140), (C - 40, C - 40, 34, 26), border_radius=4)
    pygame.draw.rect(s, (70, 76, 92), (C - 40, C - 40, 34, 26), 2, border_radius=4)
    pygame.draw.ellipse(s, (60, 200, 140), (C - 38, C - 44, 30, 9))
    pygame.draw.polygon(s, (60, 200, 140), [(C - 10, C - 30), (C + 2, C - 26), (C + 6, C - 12), (C + 4, C + 2), (C, C + 2), (C - 2, C - 14)])
    ship = spr("player_ship_shield.png", 46)
    tint = ship.copy()
    tint.fill((60, 200, 140, 255), special_flags=pygame.BLEND_RGBA_MULT)
    half = pygame.Surface(ship.get_size(), pygame.SRCALPHA)
    half.blit(ship, (0, 0))
    half.blit(tint, (0, 0), area=pygame.Rect(0, 0, ship.get_width(), ship.get_height() // 2))
    blit_c(s, half, C + 8, C + 30)
    for x, y, r in ((C + 18, C + 4, 3), (C - 2, C + 12, 2), (C + 26, C + 18, 2)):
        pygame.draw.circle(s, (60, 200, 140), (x, y), r)


def adv_colour(s):
    for name, x, rot in (("player_ship_shield.png", C - 32, 14), ("player_ship_shield_green.png", C, 0),
                         ("player_ship_shield_violet.png", C + 32, -14)):
        glow(s, x, C + 12, 26, (255, 255, 255), 40)
        blit_c(s, spr(name, 42, rot=rot), x, C + 12 + abs(rot) // 2)
    for i, col in enumerate(((220, 60, 60), (60, 200, 120), (160, 90, 230))):
        pygame.draw.circle(s, col, (C - 24 + i * 24, 18), 7)
        pygame.draw.circle(s, (255, 255, 255), (C - 26 + i * 24, 16), 2)


def adv_mechanic(s):
    gear(s, C - 18, C + 6, 30, 10, (150, 156, 170))
    gear(s, C + 28, C - 26, 18, 8, (200, 160, 70))
    # a wrench across
    pygame.draw.line(s, (220, 224, 232), (C - 6, C + 46), (C + 40, C), 9)
    pygame.draw.circle(s, (220, 224, 232), (C + 42, C - 2), 12)
    pygame.draw.circle(s, (20, 22, 30), (C + 47, C - 7), 7)
    glow(s, C + 28, C - 26, 30, (255, 200, 90), 70)


def adv_saver(s):
    glow(s, C, C + 20, 56, (255, 200, 60), 110)
    for k, (x, n) in enumerate(((C - 28, 4), (C, 7), (C + 28, 5))):
        for i in range(n):
            y = N - 22 - i * 9
            pygame.draw.ellipse(s, (180, 130, 30), (x - 14, y + 2, 28, 10))
            pygame.draw.ellipse(s, (240, 200, 70), (x - 14, y, 28, 10))
            pygame.draw.ellipse(s, (255, 230, 140), (x - 14, y, 28, 10), 1)
    sparks(s, C, 30, 4, 20, 10, 90, (255, 240, 170))


def adv_flawless(s):
    glow(s, C, C + 4, 44, (120, 255, 170), 110)
    laurel(s, C, C + 6, 44)
    blit_c(s, spr("player_ship.png", 38), C, C + 4)
    for x, y in ((C - 22, C - 30), (C + 26, C - 20), (C + 14, C + 34)):
        pygame.draw.line(s, (255, 255, 255), (x - 5, y), (x + 5, y), 1)
        pygame.draw.line(s, (255, 255, 255), (x, y - 5), (x, y + 5), 1)


def adv_veteran(s):
    glow(s, C, C, 56, (200, 30, 30), 120)
    pygame.draw.polygon(s, (150, 20, 30), [(C - 22, 0), (C + 22, 0), (C + 8, C - 6), (C - 8, C - 6)])
    pygame.draw.polygon(s, (220, 60, 60), [(C - 22, 0), (C + 22, 0), (C + 8, C - 6), (C - 8, C - 6)], 2)
    blit_c(s, spr("icon_veteran.png", h=78), C, C + 14)


def adv_bestiary(s):
    book = [(C - 46, C - 22), (C, C - 16), (C + 46, C - 22), (C + 46, C + 30), (C, C + 36), (C - 46, C + 30)]
    pygame.draw.polygon(s, (90, 50, 30), [(x, y + 4) for x, y in book])
    pygame.draw.polygon(s, (230, 220, 190), [(C - 44, C - 22), (C - 1, C - 16), (C - 1, C + 32), (C - 44, C + 26)])
    pygame.draw.polygon(s, (240, 232, 205), [(C + 44, C - 22), (C + 1, C - 16), (C + 1, C + 32), (C + 44, C + 26)])
    pygame.draw.line(s, (150, 130, 100), (C, C - 16), (C, C + 33), 2)
    blit_c(s, spr("garg4_body.png", 30), C - 22, C + 4)
    for i in range(6):
        y = C - 10 + i * 6
        pygame.draw.line(s, (120, 110, 95), (C + 8, y), (C + 38 - (i % 3) * 5, y - 1), 1)
    glow(s, C, C - 30, 30, (255, 220, 140), 50)


def adv_hunter(s):
    plaque = [(C - 36, 24), (C + 36, 24), (C + 40, 60), (C, 112), (C - 40, 60)]
    pygame.draw.polygon(s, (110, 64, 34), plaque)
    pygame.draw.polygon(s, (170, 110, 60), plaque, 3)
    blit_c(s, spr("garg3_body.png", 56), C, 58)
    star = [(C + 30 + 10 * math.cos(math.radians(-90 + i * 36)) * (1 if i % 2 == 0 else 0.45),
             26 + 10 * math.sin(math.radians(-90 + i * 36)) * (1 if i % 2 == 0 else 0.45)) for i in range(10)]
    pygame.draw.polygon(s, (255, 210, 60), star)
    glow(s, C + 30, 26, 20, (255, 210, 80), 140)


def adv_cinema(s):
    strip = pygame.Surface((150, 52), pygame.SRCALPHA)
    strip.fill((24, 24, 28))
    for i in range(10):
        pygame.draw.rect(strip, (200, 200, 210), (6 + i * 15, 4, 7, 6), border_radius=1)
        pygame.draw.rect(strip, (200, 200, 210), (6 + i * 15, 42, 7, 6), border_radius=1)
    pics = ("bird1_flap0.png", "garg3_full.png", "bird2_flap0.png")
    for i, name in enumerate(pics):
        frame = pygame.Rect(6 + i * 48, 13, 42, 26)
        pygame.draw.rect(strip, (40, 60, 110), frame)
        img = spr(name, h=22)
        strip.blit(img, img.get_rect(center=frame.center))
    s.blit(pygame.transform.rotozoom(strip, 18, 1.0), (-14, 30))
    glow(s, 100, 20, 30, (255, 240, 200), 120)


def adv_bar(s):
    blit_c(s, planet("mars.png", 62), C + 18, C - 14)
    glass = [(C - 34, C - 10), (C + 6, C - 10), (C - 14, C + 16)]
    pygame.draw.polygon(s, (255, 120, 180), [(C - 30, C - 7), (C + 2, C - 7), (C - 14, C + 12)])
    pygame.draw.polygon(s, (220, 240, 255), glass, 2)
    pygame.draw.line(s, (220, 240, 255), (C - 14, C + 16), (C - 14, C + 40), 2)
    pygame.draw.line(s, (220, 240, 255), (C - 26, C + 40), (C - 2, C + 40), 3)
    pygame.draw.circle(s, (120, 220, 90), (C - 4, C - 12), 4)
    pygame.draw.line(s, (255, 240, 160), (C - 18, C - 26), (C - 6, C - 4), 2)


SCENES = {fn.__name__: fn for fn in (
    first_blood, stage2, boss_down, loop, one_up_1337, elite_8086, phenix_wake, iron_curtain, mixed_squad, survivor,
    ten_flags, veteran_clear, no_edge, hotseat, gauge_max, credits_watch, listen_menu, listen_hs, listen_credits,
    listen_nostalgie_start, listen_nostalgie_elise, listen_music_all, clean_shot, razor, butcher, wrecker, cutter,
    duo_fire, marathon, pleiades, port_pair, boldly_go,
    adv_pilot, adv_sortie, adv_kaki, adv_garg, adv_shadow, adv_domes, adv_reactor, adv_act2, adv_commander,
    adv_phenix, adv_paint, adv_colour, adv_mechanic, adv_saver, adv_flawless, adv_veteran, adv_bestiary, adv_hunter,
    adv_cinema, adv_bar,
)}


def make(aid):
    s = space(sum(map(ord, aid)))
    SCENES[aid](s)
    return s


def main(names):
    pygame.init()
    pygame.display.set_mode((8, 8))
    os.makedirs(OUT_DIR, exist_ok=True)
    for aid in names or SCENES:
        path = os.path.join(OUT_DIR, aid + ".png")
        pygame.image.save(make(aid), path)
        print("written", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main(sys.argv[1:])
