"""
The VIP yacht of the escort mission (src/escort.py), cut out of the video Kraran made (a still yacht on a black
background, its reactor flame moving behind it):

    python tools/make_vip_yacht.py yacht.mp4

writes, at the size of the game:
- assets/sprites/vip_yacht.png        the hull, with its transparency (what the birds must touch, what blocks the ship)
- assets/sprites/vip_yacht_flame.png  the flame of the reactor, every frame of the video in a grid (FLAME_COLS a row)
                                      on black: the game adds it to the picture (no part of the hit box)

The hull is the median of every frame (the flame leaves it alone), cut where the background is: every dark pixel that
the edge of the picture can reach is background, the rest (windows, the dark tuyère) is the yacht.
Needs numpy and ffmpeg (the one the game finds, see src/videoclip.py).
"""
import os
import subprocess
import sys
from collections import deque

import numpy as np
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import videoclip  # noqa: E402

HULL_BOX = (468, 276, 998, 428)        # x0, y0, x1, y1 in the video (1280 x 720): the hull, the tuyère included
FLAME_BOX = (186, 288, 476, 440)       # the flame, behind the tuyère
HULL_W = 172                           # the hull in the game, px (the scale of everything)
FLAME_COLS = 16
DARK = 14                              # brighter than this (0-255) is not the black background


def frames(path):
    exe = videoclip.find_ffmpeg()
    if not exe:
        raise SystemExit("ffmpeg not found")
    out = subprocess.run([exe, "-loglevel", "error", "-i", path, "-map", "0:v:0", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, np.uint8).reshape(-1, 720, 1280, 3)


def background(img):
    """True where the pixel is background: dark, and reachable from the edge through dark pixels."""
    h, w = img.shape[:2]
    dark = img.max(axis=2) <= DARK
    seen = np.zeros((h, w), bool)
    todo = deque()
    for x in range(w):
        for y in (0, h - 1):
            if dark[y, x] and not seen[y, x]:
                seen[y, x] = True
                todo.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if dark[y, x] and not seen[y, x]:
                seen[y, x] = True
                todo.append((y, x))
    while todo:
        y, x = todo.popleft()
        for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= yy < h and 0 <= xx < w and dark[yy, xx] and not seen[yy, xx]:
                seen[yy, xx] = True
                todo.append((yy, xx))
    return seen


def surface(rgb, alpha=None):
    h, w = rgb.shape[:2]
    if alpha is None:
        return pygame.image.frombuffer(np.ascontiguousarray(rgb).tobytes(), (w, h), "RGB")
    rgba = np.dstack([rgb, alpha]).astype(np.uint8)
    return pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(), (w, h), "RGBA")


def main(path):
    pygame.init()
    pygame.display.set_mode((1, 1))
    video = frames(path)
    x0, y0, x1, y1 = HULL_BOX
    hull = np.median(video[:, y0:y1, x0:x1], axis=0).astype(np.uint8)
    alpha = np.where(background(hull), 0, 255).astype(np.uint8)
    k = HULL_W / float(x1 - x0)
    size = (HULL_W, int(round((y1 - y0) * k)))
    out_dir = os.path.join(ROOT, "assets", "sprites")
    hull_img = pygame.transform.smoothscale(surface(hull, alpha).convert_alpha(), size)
    pygame.image.save(hull_img, os.path.join(out_dir, "vip_yacht.png"))

    fx0, fy0, fx1, fy1 = FLAME_BOX
    fsize = (int(round((fx1 - fx0) * k)), int(round((fy1 - fy0) * k)))
    n = len(video)
    rows = -(-n // FLAME_COLS)
    sheet = pygame.Surface((fsize[0] * FLAME_COLS, fsize[1] * rows))
    sheet.fill((0, 0, 0))
    for i, fr in enumerate(video):
        img = pygame.transform.smoothscale(surface(fr[fy0:fy1, fx0:fx1]).convert(), fsize)
        sheet.blit(img, ((i % FLAME_COLS) * fsize[0], (i // FLAME_COLS) * fsize[1]))
    pygame.image.save(sheet, os.path.join(out_dir, "vip_yacht_flame.png"))
    print("hull", size, "flame frame", fsize, "frames", n, "grid", FLAME_COLS, "x", rows)
    print("flame offset from the hull's left edge: x %d, y %d" % (round((fx0 - x0) * k), round((fy0 - y0) * k)))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
