"""Build the sprites of the loot items (Adventure) from their source video and picture.

    python tools/make_item_sprites.py ID VIDEO.mp4 POSTER.png [--box 44] [--frames 36] [--icon 96]

Writes assets/items/ID.png (the falling item: a strip of FRAMES cells side by side, one turn of the video) and
assets/items/ID_icon.png (a bigger picture for the hangar, from the poster).

The videos have a flat background (black, dark violet, light grey, navy): it is found from the border of
each frame, flooded away, and the edge of the item is un-mixed from that colour so there is no halo.
The cell is the same for every frame (the union of what the item covers) and is shrunk so that its longest
side is --box pixels, about the size of the birds of the stages 1 and 2 (38 x 36).

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
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

OUT = os.path.join(ROOT, "assets", "items")
T0, T1 = 10.0, 42.0          # colour distance (0..441) where the background stops / the item is whole


def key_frame(rgb):
    """RGB uint8 (h, w, 3) with a flat background -> RGBA float (h, w, 4), alpha in 0..1, colour un-mixed."""
    px = rgb.astype(np.float32)
    edge = np.concatenate([px[0], px[-1], px[:, 0], px[:, -1]])
    bg = np.median(edge, axis=0)
    d = np.sqrt(((px - bg) ** 2).sum(axis=2))
    lab, n = ndimage.label(d < T1)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    is_bg = np.isin(lab, list(border))
    near = ndimage.binary_dilation(is_bg, iterations=2)
    alpha = np.where(near & ~is_bg, np.clip((d - T0) / (T1 - T0), 0, 1), np.where(is_bg, 0.0, 1.0))
    a3 = np.maximum(alpha, 1e-3)[..., None]
    col = np.where(alpha[..., None] < 1, (px - (1 - a3) * bg) / a3, px)
    col = np.clip(col, 0, 255)
    return np.dstack([col, alpha * 255.0])


def extract_frames(video, folder):
    from videoclip import find_ffmpeg
    ff = find_ffmpeg()
    if not ff:
        sys.exit("ffmpeg not found")
    subprocess.run([ff, "-v", "error", "-i", video, "-an", os.path.join(folder, "f%03d.png")], check=True)
    return sorted(glob.glob(os.path.join(folder, "f*.png")))


def fit(arr_rgba, box):
    im = Image.fromarray(np.clip(arr_rgba, 0, 255).astype(np.uint8), "RGBA")
    w, h = im.size
    k = box / max(w, h)
    return im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)


def build(item, video, poster, box, frames, icon):
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        files = extract_frames(video, tmp)
        step = len(files) / frames
        picks = [files[int(i * step)] for i in range(frames)]
        keyed = [key_frame(np.asarray(Image.open(p).convert("RGB"))) for p in picks]
    cover = np.any([k[..., 3] > 25 for k in keyed], axis=0)
    ys, xs = np.where(cover)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    cells = [fit(k[y0:y1, x0:x1], box) for k in keyed]
    cw, ch = cells[0].size
    strip = Image.new("RGBA", (cw * frames, ch), (0, 0, 0, 0))
    for i, c in enumerate(cells):
        strip.paste(c, (i * cw, 0))
    strip.save(os.path.join(OUT, f"{item}.png"), optimize=True)

    pk = key_poster(np.asarray(Image.open(poster).convert("RGBA")))
    ys, xs = np.where(pk[..., 3] > 25)
    pic = fit(pk[ys.min():ys.max() + 1, xs.min():xs.max() + 1], icon)
    pic.save(os.path.join(OUT, f"{item}_icon.png"), optimize=True)
    print(item, "cell", (cw, ch), "frames", frames, "icon", pic.size)


def key_poster(rgba):
    """The posters carry a faint haze (alpha 3..60) instead of a clean background: cut it."""
    a = rgba[..., 3].astype(np.float32)
    a = np.clip((a - 70.0) / (200.0 - 70.0), 0, 1)
    lab, n = ndimage.label(a > 0.5)
    if n > 1:                                   # keep the item and what touches it (sparks), drop specks
        sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s > 40])
        a = np.where(ndimage.binary_dilation(keep, iterations=6), a, 0.0)
    out = rgba.astype(np.float32).copy()
    out[..., 3] = a * 255.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("item")
    ap.add_argument("video")
    ap.add_argument("poster")
    ap.add_argument("--box", type=int, default=44)
    ap.add_argument("--frames", type=int, default=36)
    ap.add_argument("--icon", type=int, default=96)
    a = ap.parse_args()
    build(a.item, a.video, a.poster, a.box, a.frames, a.icon)


if __name__ == "__main__":
    main()
