"""Build the pictures of the asteroids of the BONUS mission "Asteroids" (src/asteroids.py).

    python tools/make_asteroids.py [--frames 24] [--variants 2] [out_dir]

Writes assets/sprites/asteroids/rock_<size>_<variant>.png, size = L (large), M (medium) or S (small): a strip of
FRAMES cells side by side, one turn of the rock on its own axis. The rocks are NOT drawn as vectors: each one is a lumpy
ball, lit from the upper left, whose surface (grey rock, pits, craters, small bumps that catch the light) is made of
3D noise and turns under the light, so the shadows stay where they are while the rock spins. Everything is
deterministic (fixed seeds): running the tool again gives the same files.

Needs (not for the game, only for this tool): numpy and pygame.
"""
import argparse
import math
import os

import numpy as np

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "assets", "sprites", "asteroids")
SIZES = {"L": 132, "M": 78, "S": 44}       # the pixels of one cell: large, medium, small


def _lattice(seed, n=32):
    rng = np.random.RandomState(seed)
    return rng.rand(n, n, n).astype(np.float32)

def _vnoise(lat, x, y, z):
    n = lat.shape[0]
    xi = np.floor(x).astype(np.int32); yi = np.floor(y).astype(np.int32); zi = np.floor(z).astype(np.int32)
    xf = x - xi; yf = y - yi; zf = z - zi
    xf = xf * xf * (3 - 2 * xf); yf = yf * yf * (3 - 2 * yf); zf = zf * zf * (3 - 2 * zf)
    def g(a, b, c): return lat[(xi + a) % n, (yi + b) % n, (zi + c) % n]
    c00 = g(0,0,0) * (1-xf) + g(1,0,0) * xf; c10 = g(0,1,0) * (1-xf) + g(1,1,0) * xf
    c01 = g(0,0,1) * (1-xf) + g(1,0,1) * xf; c11 = g(0,1,1) * (1-xf) + g(1,1,1) * xf
    return (c00 * (1-yf) + c10 * yf) * (1-zf) + (c01 * (1-yf) + c11 * yf) * zf

def _fbm(lat, p, octaves=4, base=2.0):
    x, y, z = p
    tot = 0; amp = 0.5; norm = 0; f = base
    for _ in range(octaves):
        tot = tot + amp * _vnoise(lat, x * f, y * f, z * f)
        norm += amp; amp *= 0.5; f *= 2.03
    return tot / norm

def _craters(rng, count):
    out = []
    for _ in range(count):
        v = rng.randn(3); v /= np.linalg.norm(v)
        out.append((v, rng.uniform(0.18, 0.42)))
    return out

def make_rock(size, seed, frames=24, tint=(1.0, 0.97, 0.93)):
    """-> list of `frames` Surfaces (size x size, alpha) of one rock turning on its axis."""
    rng = np.random.RandomState(seed)
    lat = _lattice(seed)
    lat2 = _lattice(seed + 101)
    # lumpy silhouette: radius as a function of the angle, a few random harmonics
    harm = [(k, rng.uniform(0.07, 0.19) / (k ** 0.55), rng.uniform(0, 6.283)) for k in (2, 3, 4, 5, 7)]
    R = size / 2.0
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
    dx = (xs + 0.5 - R) / R; dy = (ys + 0.5 - R) / R
    ang = np.arctan2(dy, dx); rr = np.sqrt(dx * dx + dy * dy)
    edge = np.ones_like(rr) * 0.80
    for k, a, ph in harm:
        edge += a * np.sin(k * ang + ph)
    edge = np.clip(edge, 0.50, 0.98)
    u = rr / edge                                  # 0 centre .. 1 silhouette
    alpha = np.clip((1.0 - u) * R * 1.4, 0, 1)     # soft 1-px edge
    inside = u < 1.0
    uu = np.clip(u, 0, 0.999)
    nz = np.sqrt(1 - uu * uu)                       # sphere normal z
    nx = dx / edge; ny = dy / edge
    n3 = np.stack([nx, ny, nz])                     # (3,h,w): the point on the unit sphere
    craters = _craters(rng, 4 + int(size // 40))
    light = np.array([-0.55, -0.62, 0.56], np.float32); light /= np.linalg.norm(light)
    tilt = rng.uniform(-0.6, 0.6)
    surfaces = []
    for f in range(frames):
        th = 2 * math.pi * f / frames
        c, s = math.cos(th), math.sin(th)
        ct, st = math.cos(tilt), math.sin(tilt)
        # rotate about the (tilted) vertical axis: first around y by th, then tilt around z
        x1 = n3[0] * c + n3[2] * s; z1 = -n3[0] * s + n3[2] * c; y1 = n3[1]
        px = x1 * ct - y1 * st; py = x1 * st + y1 * ct; pz = z1
        P = (px * 1.7 + 8, py * 1.7 + 8, pz * 1.7 + 8)
        h = _fbm(lat, P, 5, 1.2)                     # height / albedo
        h2 = _fbm(lat2, (px * 5 + 3, py * 5 + 3, pz * 5 + 3), 3, 1.0)
        # craters: bowl (dark rim shadow side) on the rotating sphere
        cr = np.zeros_like(h)
        for v, rad in craters:
            d = np.sqrt((px - v[0]) ** 2 + (py - v[1]) ** 2 + (pz - v[2]) ** 2)
            bowl = np.clip(1 - d / rad, 0, 1)
            cr += -bowl * bowl * 0.9 + np.clip(1 - np.abs(d - rad * 1.05) / (rad * 0.35), 0, 1) * 0.14
        height = h * 0.9 + h2 * 0.25 + cr * 0.35
        # bump: gradient of the height on the screen plane
        gx = np.gradient(height, axis=1) * size * 0.9
        gy = np.gradient(height, axis=0) * size * 0.9
        nxp = n3[0] - gx * 0.55; nyp = n3[1] - gy * 0.55; nzp = n3[2]
        ln = np.sqrt(nxp * nxp + nyp * nyp + nzp * nzp) + 1e-6
        lam = np.clip((nxp * light[0] + nyp * light[1] + nzp * light[2]) / ln, 0, 1)
        shade = 0.20 + 0.95 * lam ** 0.9
        shade *= 0.80 + 0.35 * np.clip(h, 0, 1)
        # rim darkening toward the silhouette, soft
        shade *= 0.55 + 0.45 * nz ** 0.5
        base = np.array([0.66, 0.63, 0.60], np.float32)
        warm = np.clip(h2 - 0.4, 0, 1)[..., None]
        col = (base[None, None, :] * (1 + 0.22 * warm * np.array([0.7, 0.15, -0.4], np.float32))) * np.array(tint, np.float32)[None, None, :]
        rgb = col * shade[..., None]
        # a touch of cool rim light on the dark side
        rim = (1 - nz) ** 3 * 0.10
        rgb = rgb + np.array([0.25, 0.30, 0.45], np.float32)[None, None, :] * rim[..., None] * (1 - lam[..., None])
        rgb = np.clip(rgb, 0, 1)
        out = np.zeros((size, size, 4), np.uint8)
        out[..., :3] = (rgb * 255).astype(np.uint8)
        out[..., 3] = (alpha * inside * 255).astype(np.uint8)
        surf = pygame.image.frombuffer(out.tobytes(), (size, size), "RGBA").convert_alpha()
        surfaces.append(surf)
    return surfaces


def build(out_dir, frames=24, variants=2):
    pygame.init()
    pygame.display.set_mode((8, 8))
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for k, (name, size) in enumerate(SIZES.items()):
        for v in range(variants):
            cells = make_rock(size, 10 * (k + 1) + v, frames=frames)
            strip = pygame.Surface((size * frames, size), pygame.SRCALPHA)
            for i, cell in enumerate(cells):
                strip.blit(cell, (i * size, 0))
            path = os.path.join(out_dir, "rock_%s_%d.png" % (name, v))
            pygame.image.save(strip, path)
            written.append(path)
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", nargs="?", default=OUT)
    ap.add_argument("--frames", type=int, default=24)
    ap.add_argument("--variants", type=int, default=2)
    args = ap.parse_args()
    for p in build(args.out_dir, args.frames, args.variants):
        print(p, os.path.getsize(p))
