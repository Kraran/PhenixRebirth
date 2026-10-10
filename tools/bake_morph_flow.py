"""Compute how the pictures of the Phenix transformation move into one another, and save it for the game.

    python tools/bake_morph_flow.py            # writes assets/sprites/morph_flow.npz

The transformation goes ship -> morph_00 .. morph_03 -> phenix_00. For each two pictures in a row this finds, with
optical flow, where each pixel of the one goes in the other. The game (src/phenix_art.py, `morph_flow`) then makes the
pictures between them by moving the details along that flow instead of only fading one picture into the other, so the
hull no longer shows through the wings as a ghost.

This is the only place that needs OpenCV (pip install opencv-python-headless). The game itself needs only numpy: it reads
the result. Run it again if the drawn pictures change. The three colours of the ship have the same shape, so one
calculation (made on the silver ship) serves them all.

STRENGTH is how much of the flow is used for each pair. The last pair, where the wings come out of nothing, is made
gentler: with all the flow the feathers stretch to the corners.
"""
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import pygame  # noqa: E402

import phenix_art as pa  # noqa: E402

STRENGTH = (1.0, 1.0, 1.0, 1.0, 0.6)
SCALE = 3                      # the pictures are tiny: the flow is measured on them enlarged this many times


def gray(frame, size):
    rgb, alpha = pa._on_canvas(frame, size)                      # (w, h, 3), (w, h)
    lum = (rgb * (alpha / 255.0)[..., None]).mean(2)
    g = np.clip(0.6 * alpha + 0.4 * lum * 1.5, 0, 255).astype(np.uint8)
    return cv2.resize(g.T, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)


def flow(ga, gb, size):
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    dis.setUseSpatialPropagation(True)
    f = dis.calc(ga, gb, None)
    f = cv2.resize(f, size, interpolation=cv2.INTER_AREA) / float(SCALE)
    return f.transpose(1, 0, 2)                                  # (w, h, 2): x first, like the arrays of phenix_art


def main():
    pygame.init()
    pygame.display.set_mode((10, 10))
    sprites = os.path.join(ROOT, "assets", "sprites")
    load = lambda p: pygame.image.load(p).convert_alpha()
    keys = [load(os.path.join(sprites, "player_ship.png"))]
    keys += [load(os.path.join(sprites, "phenix", "morph_%02d.png" % i)) for i in range(4)]
    keys.append(load(os.path.join(sprites, "phenix", "phenix_00.png")))
    size = (max(k.get_width() for k in keys), max(k.get_height() for k in keys))
    grays = [gray(k, size) for k in keys]
    fab, fba = [], []
    for i, k in enumerate(STRENGTH):
        fab.append(flow(grays[i], grays[i + 1], size) * k)       # where a pixel of picture i goes in picture i + 1
        fba.append(flow(grays[i + 1], grays[i], size) * k)       # and where a pixel of picture i + 1 comes from in i
    out = os.path.join(sprites, "morph_flow.npz")
    np.savez_compressed(out, size=np.array(size), fab=np.array(fab, np.float16), fba=np.array(fba, np.float16))
    print("written", out, os.path.getsize(out), "bytes; canvas", size)


if __name__ == "__main__":
    main()
