"""Original Phenix Rebirth jukebox EQ — PHEQ1 sequences.

File format (little-endian), baked at 24 fps / 40 log bands / 22050 Hz:
  magic     5 bytes  b'PHEQ1'
  nbar      u16
  fps       u16
  sr        f32
  nframes   u32
  data      nframes * nbar bytes  (0..255)

Do not regenerate the files of the soundtrack: play the ones next to the MP3s. A new track gets its own file from
tools/make_pheq.py (the same recipe, found by fitting it on the originals).
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
    "lyra_eternal_dawn": "Lyra-Voss-Eternal-Dawn.pheq",
    "lyra_what_we_lost": "Lyra-Voss-What-We-Lost.pheq",
    "lyra_no_mercy_left": "Lyra-Voss-No-Mercy-Left.pheq",
    "lyra_oldest_fear": "Lyra-Voss-Oldest-Fear.pheq",
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


# --- the look: a hi-fi LED rack of the 80s ---------------------------------------------------------------------------
# 32 columns of 12 diodes, green -> amber -> red from the bottom up, in a dark box; the unlit diodes stay faintly
# visible, the peak of each column is a white diode, the lit ones glow. The 40 bands of the PHEQ file are folded into
# the 32 columns. Everything that does not move (the box, the unlit diodes, a fully lit column) is drawn once.
COLS = 32
SEGS = 12
SEG_H = 8
SEG_GAP = 3
RACK_X0 = 250                       # the diodes go from here to base_w - RACK_X0
RACK_BOTTOM_FROM_BOTTOM = 104       # bottom of the lowest diodes, from the bottom of the screen
RACK_PAD = (24, 18, 22)             # the box around them: sides, top, bottom
SEEK_FROM_BOTTOM = 66               # the seek bar, under the box
GREEN, AMBER, RED = (60, 230, 90), (255, 200, 40), (255, 60, 50)
PEAK = (255, 255, 230)
SEEK_COL = (255, 180, 60)

_cache = {}


def seg_colour(s):
    """Colour of diode `s` (0 = the lowest)."""
    f = s / (SEGS - 1)
    return GREEN if f < 0.6 else (AMBER if f < 0.85 else RED)


def _geometry(base_w, base_h):
    y_bot = base_h - RACK_BOTTOM_FROM_BOTTOM
    col_h = SEGS * (SEG_H + SEG_GAP)
    x0, x1 = RACK_X0, base_w - RACK_X0
    panel = (x0 - RACK_PAD[0], y_bot - col_h - RACK_PAD[1], x1 - x0 + 2 * RACK_PAD[0],
             col_h + RACK_PAD[1] + RACK_PAD[2])
    return x0, x1, y_bot, col_h, panel


def clock_y(base_h, base_w=1280):
    """Y for mm:ss / mm:ss — above the rack, never inside it."""
    return _geometry(base_w, base_h)[4][1] - 38


def _art(pygame, base_w, base_h):
    key = (base_w, base_h)
    art = _cache.get(key)
    if art is not None:
        return art
    x0, x1, y_bot, col_h, panel = _geometry(base_w, base_h)
    px, py, pw, ph = panel
    cw = (x1 - x0) / COLS
    seg_w = max(2, int(cw) - 4)
    box = pygame.Surface((pw, ph), pygame.SRCALPHA)
    pygame.draw.rect(box, (12, 13, 20, 255), (0, 0, pw, ph), border_radius=10)
    pygame.draw.rect(box, (70, 74, 96, 255), (0, 0, pw, ph), 2, border_radius=10)
    for i in range(COLS):                                   # the unlit diodes, faint
        x = int(x0 + i * cw) + 2 - px
        for s in range(SEGS):
            c = seg_colour(s)
            y = y_bot - (s + 1) * (SEG_H + SEG_GAP) - py
            pygame.draw.rect(box, (c[0] // 9, c[1] // 9, c[2] // 9, 255), (x, y, seg_w, SEG_H))
    column = pygame.Surface((seg_w, col_h))                 # a fully lit column, cut to the height of each band
    for s in range(SEGS):
        column.fill(seg_colour(s), (0, col_h - (s + 1) * (SEG_H + SEG_GAP), seg_w, SEG_H))
    peak = pygame.Surface((seg_w, SEG_H))
    peak.fill(PEAK)
    layer = pygame.Surface((pw, ph))                        # the lit diodes of the frame, then their glow
    art = {"box": box, "column": column, "peak": peak, "layer": layer, "cw": cw, "seg_w": seg_w,
           "geo": (x0, x1, y_bot, col_h, panel)}
    _cache[key] = art
    return art


def _column_values(values):
    """The 40 bands (0..1) folded into COLS columns: each column takes the louder of its two bands."""
    n = len(values)
    out = []
    for i in range(COLS):
        a = values[min(n - 1, int(i * n / COLS))]
        b = values[min(n - 1, int((i + 0.5) * n / COLS))]
        out.append(max(0.0, min(1.0, max(a, b))))
    return out


def draw(surface, pygame, bands, peaks, base_w, base_h):
    """The LED rack, above the seek bar."""
    if not bands:
        return
    art = _art(pygame, base_w, base_h)
    x0, _x1, y_bot, col_h, panel = art["geo"]
    px, py, pw, ph = panel
    surface.blit(art["box"], (px, py))
    layer = art["layer"]
    layer.fill((0, 0, 0))
    column, peak, cw = art["column"], art["peak"], art["cw"]
    step = SEG_H + SEG_GAP
    for i, (v, pk) in enumerate(zip(_column_values(bands), _column_values(peaks))):
        x = int(x0 + i * cw) + 2 - px
        lit = int(v * SEGS + 0.5)
        if lit > 0:
            h = lit * step
            layer.blit(column, (x, y_bot - py - h), (0, col_h - h, column.get_width(), h))
        top = min(SEGS - 1, int(pk * SEGS))
        if top >= lit and top > 0:
            layer.blit(peak, (x, y_bot - py - (top + 1) * step))
    small = pygame.transform.smoothscale(layer, (max(1, pw // 6), max(1, ph // 6)))       # the glow of the diodes
    surface.blit(pygame.transform.smoothscale(small, (pw, ph)), (px, py), special_flags=pygame.BLEND_RGB_ADD)
    surface.blit(layer, (px, py), special_flags=pygame.BLEND_RGB_ADD)


def draw_seek(surface, pygame, pos, dur, base_w, base_h):
    """The seek bar under the rack: a thin track, the part played in amber, a glowing head."""
    _x0, _x1, _y, _h, panel = _art(pygame, base_w, base_h)["geo"]
    x0, x1 = panel[0], panel[0] + panel[2]
    y = base_h - SEEK_FROM_BOTTOM
    w = x1 - x0
    fill = 0.0 if dur <= 0 else max(0.0, min(1.0, pos / dur))
    fx = x0 + int(w * fill)
    pygame.draw.rect(surface, (36, 38, 56), (x0, y, w, 6), border_radius=3)
    if fx > x0:
        pygame.draw.rect(surface, SEEK_COL, (x0, y, fx - x0, 6), border_radius=3)
    head = _cache.get("head")
    if head is None:
        head = pygame.Surface((40, 40), pygame.SRCALPHA)
        for r, a in ((18, 30), (12, 60), (7, 140)):
            pygame.draw.circle(head, SEEK_COL + (a,), (20, 20), r)
        pygame.draw.circle(head, (255, 255, 255, 255), (20, 20), 4)
        _cache["head"] = head
    surface.blit(head, (fx - 20, y + 3 - 20))
