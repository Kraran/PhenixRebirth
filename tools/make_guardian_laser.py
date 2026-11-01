"""Bake assets/sprites/guardian/laser.png: 3 animation frames of the Guardian fire bolt (Comete de feu).

Run from the repo root: python tools/make_guardian_laser.py
"""
import math
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

pygame.init()
pygame.display.set_mode((64, 64))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEN1 = 158                     # 144 + 10 %
W = 48                         # image wider than the hitbox (10 px): the flames lick around it
SS = 4                         # supersampling


def lerp(a, b, k):
    return a + (b - a) * k


def mix(c1, c2, k):
    return tuple(int(lerp(c1[i], c2[i], k)) for i in range(3))


def glow(surf, x, y, rx, ry, color, alpha):
    """Soft ellipse made of a few nested ones."""
    for i in range(6):
        k = 1.0 - i / 6.0
        s = pygame.Surface((int(rx * 2 * k) + 2, int(ry * 2 * k) + 2), pygame.SRCALPHA)
        pygame.draw.ellipse(s, color + (int(alpha * (0.18 + 0.5 * (1 - k)) / 3.2),), s.get_rect())
        surf.blit(s, (x - s.get_width() / 2, y - s.get_height() / 2), special_flags=0)


def tongue(surf, x, y, length, width, color, alpha, lean=0.0):
    """A flame tongue: starts at (x, y) (the base, towards the tip of the bolt) and trails UP, ending in a point."""
    pts = []
    n = 10
    for i in range(n + 1):
        t = i / n
        w = width * math.sin(math.pi * min(1.0, t * 0.9 + 0.1)) * (1 - t * 0.35)
        cx = x + lean * t * t * length * 0.25
        pts.append((cx - w / 2, y - t * length))
    right = [(2 * x - px + 2 * lean * 0, py) for px, py in pts]
    poly = [(p[0], p[1]) for p in pts] + [(x + (x - p[0]) + 2 * lean * ((i / n) ** 2) * length * 0.25, p[1])
                                         for i, p in enumerate(reversed(pts))]
    s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(s, color + (alpha,), poly)
    surf.blit(s, (0, 0))


def finish(big, length):
    small = pygame.transform.smoothscale(big, (W, length))
    return small


def base_canvas(length):
    return pygame.Surface((W * SS, length * SS), pygame.SRCALPHA)


def core(surf, length, width, tip_round=True, taper_top=6):
    """White-hot core, yellow and orange sleeves."""
    cx = W * SS / 2
    L = length * SS
    for k, (color, wk, a) in enumerate((((255, 60, 10), 2.8, 150), ((255, 130, 20), 1.9, 190),
                                        ((255, 205, 80), 1.25, 230), ((255, 250, 225), 0.62, 255))):
        w = width * SS * wk
        s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        top = taper_top * SS
        pts = [(cx - w * 0.35, top), (cx + w * 0.35, top), (cx + w / 2, top + 24 * SS), (cx + w / 2, L - 3 * SS - w * 1.2)]
        tip = pygame.Rect(cx - w / 2, L - 3 * SS - w * 2.4, w, w * 2.4)
        poly = pts + [(cx, L - 3 * SS)] + [(2 * cx - p[0], p[1]) for p in reversed(pts)]
        pygame.draw.polygon(s, color + (a,), poly)
        pygame.draw.ellipse(s, color + (a,), tip)
        surf.blit(s, (0, 0))



FRAMES = 3


def prop_b(frame, length=LEN1):
    rng = random.Random(40 + frame)
    big = base_canvas(length)
    cx = W * SS / 2
    L = length * SS
    glow(big, cx, L * 0.78, 22 * SS, L * 0.3, (255, 90, 20), 150)
    for i in range(22):                                   # a long tail of flames, thick near the head, thin and dark at the top
        t = rng.random() ** 0.7                           # 0 head .. 1 top
        y = L - 14 * SS - t * (L - 30 * SS)
        x = cx + rng.uniform(-1, 1) * (3 + 7 * (1 - t)) * SS
        col = mix((255, 170, 40), (170, 25, 5), t)
        tongue(big, x, y, rng.uniform(18, 40) * SS * (1.2 - 0.5 * t), rng.uniform(6, 11) * SS * (1.1 - 0.4 * t),
               col, int(lerp(210, 70, t)), lean=rng.uniform(-0.3, 0.3))
    core(big, length, 3.7, taper_top=18)
    glow(big, cx, L - 18 * SS, 11 * SS, 15 * SS, (255, 190, 70), 255)       # the fireball
    glow(big, cx, L - 18 * SS, 6 * SS, 9 * SS, (255, 245, 200), 255)
    for i in range(9):
        ex = cx + rng.uniform(-16, 16) * SS
        ey = rng.uniform(0.1, 0.8) * L
        pygame.draw.circle(big, (255, rng.randrange(120, 200), 40, 220), (ex, ey), rng.uniform(0.6, 1.2) * SS)
    return finish(big, length)


if __name__ == "__main__":
    frames = [prop_b(i) for i in range(FRAMES)]
    strip = pygame.Surface((W * FRAMES, LEN1), pygame.SRCALPHA)
    for i, f in enumerate(frames):
        strip.blit(f, (i * W, 0))
    pygame.image.save(strip, REPO + "/assets/sprites/guardian/laser.png")
    print("laser.png", strip.get_size())
