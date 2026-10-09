"""Give back to the Phenix their wing tips, cut by the edge of the frames.

    python tools/extend_wings.py ORIGINAL_DIR OUT_DIR

ORIGINAL_DIR holds the frames as they were drawn (phenix_00.png ...). OUT_DIR gets the same frames on a canvas
WING_PAD_X wider on each side and WING_PAD_Y taller above and below (see src/phenix_art.py): the pixels of the
original are copied unchanged, at the same distance from the centre of the canvas, so the ship keeps its size and
its place. Only the margin receives new pixels: the wings go on past the old edge and end in a point.
(The frames of the game were made from the ones of commit f5fdcf4: git show f5fdcf4:assets/sprites/phenix/NAME.)

This is an extrapolation, not the lost drawing: the wings go on along their own outline and their feathers are
taken from inside the wing. It needs only pygame and numpy.
"""
import argparse
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

import numpy as np  # noqa: E402
import pygame  # noqa: E402

from phenix_art import WING_PAD_X as PAD_X, WING_PAD_Y as PAD_Y  # noqa: E402

REACH = 15        # columns the wing goes on past the edge before it ends in a point
FIT = 9           # columns used to measure the slope of the outline
PERIOD = 7        # feathers are taken from inside the wing, shifted by a multiple of this
LEAN = 0.45       # sideways shift per row of the part that goes up: it leans outward
WING_ROWS = 60    # the wing is above this row; below are the body and the tail


def load_rgba(path):
    """(height, width, 4) float array of a PNG."""
    surf = pygame.image.load(path)
    rgb = pygame.surfarray.array3d(surf).astype(np.float32).transpose(1, 0, 2)
    alpha = pygame.surfarray.array_alpha(surf).astype(np.float32).T
    return np.dstack([rgb, alpha])


def save_rgba(arr, path):
    arr = np.ascontiguousarray(np.clip(arr, 0, 255).astype(np.uint8))
    surf = pygame.image.frombuffer(arr.tobytes(), (arr.shape[1], arr.shape[0]), "RGBA")
    pygame.image.save(surf, path)


def _span(alpha, x):
    ys = np.where(alpha[:WING_ROWS, x] > 40)[0]
    return (ys.min(), ys.max()) if len(ys) else None


def extend_sideways(rgba):
    """Left wing: go on past the left edge. Returns an array PAD_X columns wider on the left and PAD_Y rows
    taller on top, the original at (PAD_Y, PAD_X). (The right wing is this on the mirrored picture.)"""
    h, w, _ = rgba.shape
    out = np.zeros((h + PAD_Y, w + PAD_X, 4), np.float32)
    out[PAD_Y:, PAD_X:] = rgba
    al = rgba[..., 3]
    xs, tops, bots = [], [], []
    for x in range(0, FIT + 6):
        ys = np.where(al[:WING_ROWS, x] > 40)[0]
        if len(ys):
            xs.append(x)
            tops.append(ys.min())
            bots.append(ys.max())
    if len(xs) < 8:
        return out
    xs, tops, bots = np.array(xs, float), np.array(tops, float), np.array(bots, float)
    free = tops > 1                       # an outline touching the top edge is cut: it tells no slope
    if free.sum() >= 3:
        slope_top, _ = np.polyfit(xs[free], tops[free], 1)
    else:
        slope_top = 2.2                   # the wing climbs as it goes out
    slope_top = float(np.clip(slope_top, 0.9, 3.2))
    if free.sum() >= 3:
        top_at0 = tops[free].mean() - slope_top * xs[free].mean()
    else:
        top_at0 = -2.0
    slope_bot, _ = np.polyfit(xs[:8], bots[:8], 1)
    slope_bot = float(np.clip(slope_bot, -0.6, 0.9))
    bot_at0 = bots[:8].mean() - slope_bot * xs[:8].mean()
    first_top = top_at0
    first_bot = bots[:3].mean()
    for d in range(1, PAD_X + 1):                         # the column is x = -d
        k = d / float(REACH)
        if k >= 1.0:
            break
        x = -d
        top = top_at0 + slope_top * x
        thick = (first_bot - first_top) * (1.0 - k) ** 0.8
        bot = min(top + thick, bot_at0 + slope_bot * x + 6)
        if bot <= top + 1:
            break
        n = (d - 1) // PERIOD + 1
        sx = int(np.clip(-d + n * PERIOD, 0, w - 1))
        src = _span(al, sx)
        if src is None:
            continue
        s_top, s_bot = src
        s_thick = max(1, s_bot - s_top)
        for y in range(int(np.floor(top)), int(np.ceil(bot)) + 1):
            v = (y - top) / max(1e-3, bot - top)
            if v < 0.0 or v > 1.0:
                continue
            iy = int(np.clip(round(s_top + v * s_thick), 0, h - 1))
            px = rgba[iy, sx].copy()
            edge = min(1.0, (y - top + 0.5) * 1.2, (bot - y + 0.5) * 0.9 + 0.35)
            px[3] *= (1.0 - k) ** 0.6 * max(0.0, edge)       # the wing dies out toward its tip
            px[:3] *= 1.0 - 0.18 * k
            oy, ox = y + PAD_Y, x + PAD_X
            if 0 <= oy < out.shape[0] and 0 <= ox < out.shape[1] and out[oy, ox, 3] < px[3]:
                out[oy, ox] = px
    return out


def _runs(mask):
    runs, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        if not v and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask) - 1))
    return runs


def extend_upward(canvas):
    """The wings cut by the top edge go on upward, narrowing to a point and leaning outward."""
    height, width, _ = canvas.shape
    y0 = PAD_Y
    out = canvas.copy()
    for xa, xb in _runs(canvas[y0, :, 3] > 40):
        if xb - xa < 2:
            continue
        c = (xa + xb) / 2.0
        lean = LEAN if c < width / 2.0 else -LEAN
        for d in range(1, PAD_Y + 1):
            y = y0 - d
            k = d / float(PAD_Y + 1)
            f = 1.0 - 0.9 * k                                   # the strip narrows toward the point
            iy = y0 + (d - 1) % PERIOD + 3
            centre = c - lean * d
            for X in range(int(xa - 12), int(xb + 13)):
                ix = int(round(c + (X - centre) / f))
                if not (0 <= X < width and 0 <= ix < width and iy < height):
                    continue
                px = canvas[iy, ix].copy()
                px[3] *= (1.0 - k) ** 0.8
                px[:3] *= 1.0 - 0.2 * k
                if out[y, X, 3] < px[3]:
                    out[y, X] = px
    return out


def _components(mask):
    """Label of every 8-connected group of True pixels (0 = none), and the number of groups."""
    labels = np.zeros(mask.shape, int)
    n = 0
    for y, x in zip(*np.nonzero(mask)):
        if labels[y, x]:
            continue
        n += 1
        labels[y, x] = n
        stack = [(y, x)]
        while stack:
            cy, cx = stack.pop()
            for ny in range(max(0, cy - 1), min(mask.shape[0], cy + 2)):
                for nx in range(max(0, cx - 1), min(mask.shape[1], cx + 2)):
                    if mask[ny, nx] and not labels[ny, nx]:
                        labels[ny, nx] = n
                        stack.append((ny, nx))
    return labels, n


def clean(canvas, own):
    """Remove stray specks from the margin. `own` is True where the pixels come from the original frame."""
    a = canvas.copy()
    al = a[..., 3]
    al[(~own) & (al < 28)] = 0
    labels, n = _components(al > 0)
    for i in range(1, n + 1):
        m = labels == i
        if m.sum() < 25 and not (m & own).any():
            al[m] = 0
    for _ in range(2):                                          # a speck of the margin has 2 neighbours or more
        op = (al > 20).astype(int)
        nb = np.zeros_like(op)
        nb[1:] += op[:-1]
        nb[:-1] += op[1:]
        nb[:, 1:] += op[:, :-1]
        nb[:, :-1] += op[:, 1:]
        al[(~own) & (nb < 2)] = 0
    rows = np.arange(al.shape[0])[:, None].repeat(al.shape[1], 1)
    for _ in range(2):                                          # no thin horizontal line above the wings
        op = al > 20
        up = np.zeros_like(op)
        dn = np.zeros_like(op)
        up[1:] = op[:-1]
        dn[:-1] = op[1:]
        al[(~own) & ~(up & dn) & (rows < PAD_Y)] = 0
    return a


def extend_frame(rgba):
    """One frame (height, width, 4) -> the frame on the larger canvas, (height + 2*PAD_Y, width + 2*PAD_X, 4)."""
    h, w, _ = rgba.shape
    left = extend_sideways(rgba)
    right = extend_sideways(rgba[:, ::-1])[:, ::-1]
    canvas = np.zeros((h + PAD_Y, w + 2 * PAD_X, 4), np.float32)
    canvas[:, : w + PAD_X] = left
    shifted = np.zeros_like(canvas)
    shifted[:, PAD_X:] = right
    better = shifted[..., 3] > canvas[..., 3]
    canvas[better] = shifted[better]
    canvas = extend_upward(canvas)
    own = np.zeros(canvas.shape[:2], bool)
    own[PAD_Y:, PAD_X: PAD_X + w] = True
    canvas = clean(canvas, own)
    # the same margin below as above: the centre of the canvas stays the centre of the ship
    return np.vstack([canvas, np.zeros((PAD_Y, canvas.shape[1], 4), np.float32)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="folder of the original frames")
    ap.add_argument("out", help="folder that receives the frames on the larger canvas")
    args = ap.parse_args()
    names = sorted(n for n in os.listdir(args.src) if n.startswith("phenix_") and n.endswith(".png"))
    if not names:
        raise SystemExit("no phenix_NN.png in " + args.src)
    os.makedirs(args.out, exist_ok=True)
    for name in names:
        frame = extend_frame(load_rgba(os.path.join(args.src, name)))
        save_rgba(frame, os.path.join(args.out, name))
        print("%s -> %dx%d" % (name, frame.shape[1], frame.shape[0]))


if __name__ == "__main__":
    main()
