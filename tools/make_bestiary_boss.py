"""Draws the Bestiary pictures of the boss saucer from the game's own boss (src/boss.py).

    python tools/make_bestiary_boss.py

Writes assets/sprites/bestiary_boss.png: FRAMES pictures side by side (a loop of the saucer, its core
flickering and its band scrolling), each FRAME_W x FRAME_H, transparent background. Run it again if the
boss art changes. The game never needs this script, only the picture it makes.
"""
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

FRAMES = 16             # one loop
STEP = 0.1              # seconds of boss time between two pictures
FRAME_W = 420           # the picture shown at "twice as big"; the first tiers show it at half size
OUT = os.path.join(ROOT, "assets", "sprites", "bestiary_boss.png")


def main():
    random.seed(7)
    pygame.init()
    pygame.display.set_mode((1280, 720))
    from boss import BossSaucer

    boss = BossSaucer()
    boss.speed = 0.0                 # it hovers: only the core and the band move
    boss.descend_speed = 0.0
    boss.can_shoot = False
    boss.bird_rate = 0
    shots = []
    for _ in range(FRAMES):
        boss.update(STEP, 640)
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        boss.draw(surf)
        shots.append(surf)
    box = shots[0].get_bounding_rect()
    for s in shots[1:]:
        box = box.union(s.get_bounding_rect())
    frame_h = int(round(box.h * FRAME_W / box.w))
    strip = pygame.Surface((FRAME_W * FRAMES, frame_h), pygame.SRCALPHA)
    for i, s in enumerate(shots):
        crop = s.subsurface(box).copy()
        strip.blit(pygame.transform.smoothscale(crop, (FRAME_W, frame_h)), (i * FRAME_W, 0))
    pygame.image.save(strip, OUT)
    print("written", OUT, strip.get_size(), "frame", (FRAME_W, frame_h), os.path.getsize(OUT) // 1024, "KB")


if __name__ == "__main__":
    main()
