"""Original Phenix Rebirth jukebox EQ — PHEQ1 sequences.

File format (little-endian), baked at 24 fps / 40 log bands / 22050 Hz:
  magic     5 bytes  b'PHEQ1'
  nbar      u16
  fps       u16
  sr        f32
  nframes   u32
  data      nframes * nbar bytes  (0..255)

Do not regenerate these files. Play the ones next to the MP3s.
"""
from __future__ import annotations

import os
import struct

PHEQ_MAGIC = b"PHEQ1"
HEADER_SIZE = 17

# Jukebox key -> filename in assets/music/
PHEQ_FILES = {
    "menu": "Phenix-EternalDawn.pheq",
    "gameover": "Phenix-EternalDawn-Game-Over.pheq",
    "credits": "Phenix-LastCoin-Credits.pheq",
    "nostalgie_start": "Phenix-Nostalgie-Interdite.pheq",
    "nostalgie_elise": "Phenix-Nostalgie-Elise.pheq",
}


def load_pheq(path):
    """Return dict {fps, n, frames} or None."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    if len(raw) < HEADER_SIZE or raw[:5] != PHEQ_MAGIC:
        return None
    nbar, fps = struct.unpack_from("<HH", raw, 5)
    nfr = struct.unpack_from("<I", raw, 13)[0]
    need = int(nbar) * int(nfr)
    blob = raw[HEADER_SIZE:HEADER_SIZE + need]
    if nbar < 4 or nfr < 2 or len(blob) < need:
        return None
    frames = [blob[i * nbar:(i + 1) * nbar] for i in range(nfr)]
    return {"fps": int(fps), "n": int(nbar), "frames": frames}


def resolve_path(asset_path_fn, key):
    """Prefer assets/music/<original name>.pheq — never the remake in music/eq/."""
    name = PHEQ_FILES.get(key, key + ".pheq")
    candidates = [
        asset_path_fn("music", name),
        asset_path_fn("music", key + ".pheq"),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


def sample(seq, pos_sec):
    """Lerp 24 fps frame at playhead. Returns list of 0..1 floats."""
    n = seq["n"]
    frames = seq["frames"]
    last = len(frames) - 1
    x = max(0.0, float(pos_sec)) * float(seq["fps"])
    i0 = int(x)
    if i0 >= last:
        row = frames[last]
        return [row[i] / 255.0 for i in range(n)]
    f = x - i0
    a, b = frames[i0], frames[i0 + 1]
    inv = 1.0 - f
    return [(inv * a[i] + f * b[i]) / 255.0 for i in range(n)]


def tick(bands, peaks, target, playing, dt):
    """Classic analyzer: instant attack, exponential fall, peak hold."""
    n = len(bands)
    fall = (0.55 ** (dt * 24.0)) if playing else (0.20 ** max(dt, 0.001))
    pk_d = 0.55 * max(dt, 0.008)
    for i in range(n):
        v = target[i] if playing else 0.0
        if v >= bands[i]:
            bands[i] = v
        else:
            bands[i] = bands[i] * fall
        if bands[i] > peaks[i]:
            peaks[i] = bands[i]
        else:
            peaks[i] = max(bands[i], peaks[i] - pk_d)


SEEK_Y_FROM_BOTTOM = 88
EQ_H = 78
EQ_GAP_ABOVE_SEEK = 12
CLOCK_GAP_ABOVE_EQ = 44


def clock_y(base_h):
    """Y for mm:ss / mm:ss — above the equalizer, never inside it."""
    eq_y = base_h - SEEK_Y_FROM_BOTTOM - EQ_H - EQ_GAP_ABOVE_SEEK
    return eq_y - CLOCK_GAP_ABOVE_EQ


def draw(surface, pygame, bands, peaks, base_w, base_h):
    """Original look: solid neon bars, no frame, no panel, above the seek bar."""
    n = len(bands)
    if n <= 0:
        return
    eq_w = base_w - 440
    eq_h = EQ_H
    eq_x = 220
    eq_y = base_h - SEEK_Y_FROM_BOTTOM - eq_h - EQ_GAP_ABOVE_SEEK
    gap = 2
    bw = max(3, (eq_w - gap * (n - 1)) // n)
    ox = eq_x + (eq_w - (n * bw + (n - 1) * gap)) // 2
    den = max(1, n - 1)
    for i in range(n):
        v = bands[i]
        if v < 0.0:
            v = 0.0
        elif v > 1.0:
            v = 1.0
        h = max(2, int(v * eq_h))
        t = i / den
        col = (
            int(70 + 185 * t),
            int(210 - 90 * abs(t - 0.42)),
            int(255 - 175 * t),
        )
        glow = (col[0] // 4, col[1] // 4, col[2] // 4)
        x = ox + i * (bw + gap)
        pygame.draw.rect(surface, glow, (x - 1, eq_y + eq_h - min(eq_h, h + 6), bw + 2, min(eq_h, h + 6)))
        pygame.draw.rect(surface, col, (x, eq_y + eq_h - h, bw, h))
        cap = max(2, h // 6)
        hi = (min(255, col[0] + 55), min(255, col[1] + 45), min(255, col[2] + 25))
        pygame.draw.rect(surface, hi, (x, eq_y + eq_h - h, bw, cap))
        pk = peaks[i]
        if pk < 0.0:
            pk = 0.0
        elif pk > 1.0:
            pk = 1.0
        py = eq_y + eq_h - max(2, int(pk * eq_h))
        pygame.draw.rect(surface, (255, 248, 220), (x, py, bw, 2))
