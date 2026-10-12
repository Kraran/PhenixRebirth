"""Build the animated sprite of a background rock (starfield) from a video.

    python tools/make_planet_strip.py ID VIDEO.mp4 [--frames 72] [--box 160]

Writes assets/sprites/planets/ID_anim.png: FRAMES cells side by side, one full turn of the video, every cell
the same size (the union of what the picture covers, shrunk so its longest side is --box pixels). The flat
background is removed like in make_item_sprites.py. Prints the numbers the game needs (frames, cell size, and
the size of the main body relative to the cell, to keep the rock the size it had as a still picture).

Needs (not for the game, only for this tool): numpy, Pillow, scipy, and ffmpeg (imageio-ffmpeg).
"""
import argparse
import glob
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_item_sprites import extract_frames, fit, key_frame  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "assets", "sprites", "planets")


def close_shadows(rgb, rgba, reach=7):
    """A shadow on the rock (the moon's) is as black as space, so the keying cuts a hole in it: close the
    outline and fill what lies inside it with the picture's own (dark) pixels."""
    solid = rgba[..., 3] > 25
    closed = ndimage.binary_fill_holes(ndimage.binary_closing(solid, iterations=reach, border_value=0))
    gap = closed & ~solid
    out = rgba.copy()
    out[gap, :3] = rgb[gap].astype(np.float32)
    out[gap, 3] = 255.0
    return out


def build(name, video, frames, box):
    with tempfile.TemporaryDirectory() as tmp:
        files = extract_frames(video, tmp)
        step = len(files) / frames
        picks = [files[int(i * step)] for i in range(frames)]
        keyed = []
        for p in picks:
            rgb = np.asarray(Image.open(p).convert("RGB"))
            keyed.append(close_shadows(rgb, key_frame(rgb)))
    cover = np.any([k[..., 3] > 25 for k in keyed], axis=0)
    ys, xs = np.where(cover)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    # main body = the biggest blob that is there in every frame
    lab, n = ndimage.label(np.all([k[..., 3] > 25 for k in keyed], axis=0))
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    body = lab == (1 + int(np.argmax(sizes)))
    by, bx = np.where(body)
    body_h = by.max() + 1 - by.min()
    cells = [fit(k[y0:y1, x0:x1], box) for k in keyed]
    cw, ch = cells[0].size
    strip = Image.new("RGBA", (cw * frames, ch), (0, 0, 0, 0))
    for i, c in enumerate(cells):
        strip.paste(c, (i * cw, 0))
    os.makedirs(OUT, exist_ok=True)
    strip.save(os.path.join(OUT, f"{name}_anim.png"), optimize=True)
    print(name, "frames", frames, "cell", (cw, ch), "body height / cell height %.3f" % (body_h / (y1 - y0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("video")
    ap.add_argument("--frames", type=int, default=72)
    ap.add_argument("--box", type=int, default=160)
    a = ap.parse_args()
    build(a.name, a.video, a.frames, a.box)


if __name__ == "__main__":
    main()
