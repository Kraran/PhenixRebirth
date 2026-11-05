"""The jukebox screen: the track list on the left, the cover of the album in the middle, the lyrics on the right
(for the songs of Lyra Voss), with the LED rack, the seek bar and the clock under them (pheq.py).

Covers, in this order:
  1. assets/music/covers/<key>.png / .jpg      (key: the jukebox key, e.g. lyra_oldest_fear, menu, credits)
  2. the picture inside the MP3 (ID3v2 APIC frame)
  3. a picture of the Adventure (Lyra Voss: assets/story/lyra_voss.jpg or concertmars.jpg)
  4. a drawn placeholder (a disc)

Lyrics: assets/music/lyrics/<key>.json
  {"lang": "en",                        the language the song is sung in
   "lines": [                           one entry per line ("" text = an empty line between two verses)
     {"t": 12.5,                        optional: second where the line starts (the line lights up then)
      "text": "the line as sung",
      "tr": {"fr": "...", "de": "..."}} the translations, by interface language (a missing one: the line alone)
   ]}
A file with no line (or no file) shows "lyrics to come". With no "t" at all, the lines scroll along the song.
"""
import json
import os
import struct

import pygame

import fonts
import menu_ui
from errlog import log_exc
from i18n import get_lang, t
from settings import asset_path

COVER_DIR = asset_path("music", "covers")
LYRICS_DIR = asset_path("music", "lyrics")
LYRA_FALLBACK = {"lyra_when_we_looked_up": "concertmars.jpg", "lyra_when_we_looked_up_unplugged": "concertmars.jpg"}

AMBER = (255, 200, 120)
DIM = (120, 120, 150)
TR_COL = (150, 175, 215)

_covers = {}
_lyrics = {}
_wraps = {}


# --- covers ---------------------------------------------------------------------------------------------------------

def _apic(path):
    """The bytes of the first picture of an ID3v2.3/2.4 tag, or None."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(10)
            if len(head) < 10 or head[:3] != b"ID3":
                return None
            ver = head[3]
            size = ((head[6] & 0x7F) << 21) | ((head[7] & 0x7F) << 14) | ((head[8] & 0x7F) << 7) | (head[9] & 0x7F)
            data = fh.read(size)
    except OSError:
        return None
    i = 0
    while i + 10 <= len(data):
        fid = data[i:i + 4]
        if fid[:1] == b"\0":
            break
        if ver == 4:
            b = data[i + 4:i + 8]
            fsize = ((b[0] & 0x7F) << 21) | ((b[1] & 0x7F) << 14) | ((b[2] & 0x7F) << 7) | (b[3] & 0x7F)
        else:
            fsize = struct.unpack(">I", data[i + 4:i + 8])[0]
        body = data[i + 10:i + 10 + fsize]
        if fid == b"APIC" and body:
            enc = body[0]
            j = body.index(b"\0", 1) + 1               # MIME type
            j += 1                                      # picture type
            if enc in (1, 2):                           # UTF-16 description: ends on a double zero
                while j + 1 < len(body) and body[j:j + 2] != b"\0\0":
                    j += 2
                j += 2
            else:
                j = body.index(b"\0", j) + 1
            return body[j:]
        i += 10 + fsize
    return None


def _placeholder(size):
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    surf.fill((14, 16, 26, 255))
    c = size // 2
    for r, col in ((int(size * 0.42), (28, 30, 44)), (int(size * 0.40), (20, 22, 32))):
        pygame.draw.circle(surf, col, (c, c), r)
    for k in range(6):
        pygame.draw.circle(surf, (34, 36, 52), (c, c), int(size * (0.18 + k * 0.035)), 1)
    pygame.draw.circle(surf, (255, 170, 80), (c, c), int(size * 0.12))
    pygame.draw.circle(surf, (14, 16, 26), (c, c), int(size * 0.025))
    return surf


def _square(img, size):
    w, h = img.get_size()
    s = min(w, h)
    img = img.subsurface(pygame.Rect((w - s) // 2, (h - s) // 2, s, s)).copy()
    return pygame.transform.smoothscale(img, (size, size))


def cover(key, path, size):
    """The cover of a track, size×size, cached."""
    ck = (key, size)
    if ck in _covers:
        return _covers[ck]
    img = None
    try:
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            p = os.path.join(COVER_DIR, key + ext)
            if os.path.isfile(p):
                img = pygame.image.load(p)
                break
        if img is None and path and path.lower().endswith(".mp3"):
            raw = _apic(path)
            if raw:
                import io
                img = pygame.image.load(io.BytesIO(raw))
        if img is None and key.startswith("lyra_"):
            p = asset_path("story", LYRA_FALLBACK.get(key, "lyra_voss.jpg"))
            if os.path.isfile(p):
                img = pygame.image.load(p)
    except Exception:
        log_exc("jukebox_ui.cover")
        img = None
    out = _square(img, size) if img is not None else _placeholder(size)
    _covers[ck] = out
    return out


# --- lyrics ---------------------------------------------------------------------------------------------------------

def lyrics(key):
    """{"lang", "lines"} of a song, or None when it has no lyrics yet."""
    if key in _lyrics:
        return _lyrics[key]
    data = None
    p = os.path.join(LYRICS_DIR, key + ".json")
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
            lines = [ln for ln in data.get("lines", []) if isinstance(ln, dict)]
            data = {"lang": data.get("lang", "en"), "lines": lines} if any(ln.get("text") for ln in lines) else None
        except (OSError, ValueError, AttributeError):
            log_exc("jukebox_ui.lyrics")
            data = None
    _lyrics[key] = data
    return data


def _current_line(lines, pos, dur):
    timed = [i for i, ln in enumerate(lines) if isinstance(ln.get("t"), (int, float))]
    if timed:
        cur = -1
        for i in timed:
            if lines[i]["t"] <= pos:
                cur = i
        return cur, True
    if dur > 1.0:
        return int(len(lines) * max(0.0, min(0.999, pos / dur))), False
    return 0, False


def _wrap(font, text, width):
    ck = (id(font), text, width)
    if ck in _wraps:
        return _wraps[ck]
    out, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if font.size(trial)[0] <= width or not line:
            line = trial
        else:
            out.append(line)
            line = word
    out.append(line)
    _wraps[ck] = out
    return out


def draw_lyrics(game, surface, rect, key, pos, dur, playing):
    menu_ui.panel(surface, rect)
    head_font = fonts.title(18)
    hdr = game._txt(head_font, t("juke_lyrics"), menu_ui.TITLE)
    surface.blit(hdr, (rect.x + 18, rect.y + 12))
    data = lyrics(key) if key else None
    inner = pygame.Rect(rect.x + 18, rect.y + 44, rect.w - 36, rect.h - 56)
    if data is None:
        msg = t("juke_no_lyrics") if (key or "").startswith("lyra_") else t("juke_instrumental")
        img = game._txt(fonts.text(22), msg, DIM)
        surface.blit(img, (inner.centerx - img.get_width() // 2, inner.centery - img.get_height() // 2))
        return
    lang = get_lang()
    show_tr = data["lang"] != lang
    f_main, f_tr = fonts.text(22), fonts.body(18)
    lines = data["lines"]
    cur, _timed = _current_line(lines, pos, dur) if playing or pos > 0 else (-1, False)
    blocks = []                                         # (index, [(img), ...]) laid out one under the other
    for i, ln in enumerate(lines):
        imgs = []
        text = ln.get("text", "")
        col = menu_ui.TEXT_SEL if i == cur else (menu_ui.TEXT if cur < 0 or i > cur else DIM)
        for part in _wrap(f_main, text, inner.w) if text else [""]:
            imgs.append(game._txt(f_main, part, col) if part else None)
        tr = (ln.get("tr") or {}).get(lang, "") if show_tr else ""
        if tr:
            for part in _wrap(f_tr, tr, inner.w):
                imgs.append(game._txt(f_tr, part, TR_COL if i == cur else DIM))
        blocks.append(imgs)
    gap, lh = 8, f_main.get_linesize()
    heights = [sum((im.get_height() if im is not None else lh // 2) for im in b) + gap for b in blocks]
    focus = max(0, cur)
    y_focus = sum(heights[:focus])
    offset = max(0, min(y_focus - inner.h // 3, sum(heights) - inner.h))
    clip = surface.get_clip()
    surface.set_clip(inner)
    y = inner.y - offset
    for b, h in zip(blocks, heights):
        if y + h >= inner.y and y <= inner.bottom:
            yy = y
            for im in b:
                if im is None:
                    yy += lh // 2
                    continue
                surface.blit(im, (inner.x, yy))
                yy += im.get_height()
        y += h
    surface.set_clip(clip)
