"""The jukebox screen, in two styles: "arcade" (the main menu: stars and blue panels) and "adventure" (opened from the
Extras of the Adventure: the bar of the station, a steel plate, holographic glass and the CRT of the log, phobos_ui).

  left            the whole track list in groups (Phenix, Lyra Voss - Eternal Dawn, the video): number, title (what is in
                  brackets smaller, squeezed rather than cut), length; the track playing has the amber play mark, the
                  cursor the lit frame; the list scrolls only when it no longer fits
  right, top      "now playing": the cover, the title, artist and album, a compact LED rack (pheq.py), the seek bar and
                  the clock on one line
  right, bottom   the lyrics: the line sung in the middle, bigger, its translation under it, the lines sung before it
                  dimmed; the panel fades out at the top and the bottom instead of cutting a line in half

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
import phobos_ui
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
        if img is None and key.startswith("lyra_"):  # the "Eternal Dawn" album, shared by every Lyra track
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                p = os.path.join(COVER_DIR, "lyra_album" + ext)
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


# --- the screen -------------------------------------------------------------------------------------------------------
LIST_BOX = pygame.Rect(36, 78, 440, 586)
NOW_BOX = pygame.Rect(492, 78, 752, 232)
LYRICS_BOX = pygame.Rect(492, 322, 752, 342)
ROW_H = 36                     # a track of the list
HEAD_H = 30                    # the title of a group
COVER = 196
RACK_CELLS = 10
PLAYING = (255, 200, 120)

# colours by style: title of a group, a track, the track playing, the cursor, the dim parts (number, length, brackets)
STYLES = {
    "arcade": {"head": menu_ui.TITLE, "rule": (60, 66, 96), "text": menu_ui.TEXT, "sel": menu_ui.TEXT_SEL,
               "dim": (110, 110, 140), "dim_sel": (200, 180, 120), "title": menu_ui.TEXT_SEL, "sub": (150, 150, 180),
               "label": menu_ui.TITLE, "track": (40, 42, 60), "frame": (60, 66, 96),
               "rack": ((110, 240, 150), (255, 220, 90), (255, 110, 90)),
               "rack_off": ((22, 40, 30), (44, 38, 18), (44, 22, 20)),
               "ly_head": menu_ui.TITLE, "ly_tag": (120, 120, 150), "ly_cur": menu_ui.TEXT_SEL, "ly_next": menu_ui.TEXT,
               "ly_past": (96, 96, 124), "tr_cur": (150, 175, 215), "tr_next": (112, 118, 150), "tr_past": (80, 84, 110),
               "ly_bar": (255, 200, 120)},
    "adventure": {"head": phobos_ui.HOLO_TEXT, "rule": phobos_ui.STEEL_EDGE, "text": (196, 202, 214),
                  "sel": phobos_ui.GOLD, "dim": (120, 128, 146), "dim_sel": (220, 190, 120), "title": phobos_ui.GOLD,
                  "sub": (150, 170, 200), "label": phobos_ui.HOLO_TEXT, "track": phobos_ui.STEEL_DARK,
                  "frame": phobos_ui.STEEL_EDGE,
                  "rack": (phobos_ui.CRT, (255, 200, 110), (235, 110, 80)),
                  "rack_off": ((10, 36, 34), (40, 32, 16), (40, 20, 18)),
                  "ly_head": phobos_ui.CRT, "ly_tag": phobos_ui.CRT_DIM, "ly_cur": (220, 255, 248),
                  "ly_next": phobos_ui.CRT_TEXT, "ly_past": (40, 120, 112), "tr_cur": (150, 205, 235),
                  "tr_next": (70, 150, 142), "tr_past": (40, 110, 104), "ly_bar": phobos_ui.CRT},
}

_squeezed = {}
_fades = {}


def style_of(game):
    """"adventure" when the jukebox was opened from the Adventure (the bar of the station behind it), else "arcade"."""
    door = getattr(game, "_door_picture", None)
    return "adventure" if door is not None and door() is not None else "arcade"


def split_title(title):
    """("Lyra Voss", "Eternal Dawn", "(Aventure)") from "Lyra Voss - Eternal Dawn (Aventure)"."""
    artist, _sep, name = title.partition(" - ")
    if not name:
        artist, name = "", title
    main, _p, rest = name.partition(" (")
    return artist.strip(), main.strip(), ("(" + rest) if rest else ""


def group_of(key, kind):
    if kind == "video":
        return "video"
    return "lyra" if key.startswith("lyra_") else "phenix"


def group_title(group):
    return {"phenix": "PHENIX", "lyra": "LYRA VOSS · ETERNAL DAWN"}.get(group) or t("juke_group_video")


def mmss(sec):
    sec = max(0, int(sec))
    return f"{sec // 60}:{sec % 60:02d}"


def _squeeze(img, w):
    """`img` at most `w` wide: squeezed horizontally (cached), never cut."""
    if img.get_width() <= w:
        return img
    ck = (id(img), w)
    out = _squeezed.get(ck)
    if out is None:
        if len(_squeezed) > 200:
            _squeezed.clear()
        out = _squeezed[ck] = pygame.transform.smoothscale(img, (max(1, w), img.get_height()))
    return out


def list_lines(cat):
    """The lines of the list: ("head", group) before each group, ("track", index in the catalog)."""
    out, last = [], None
    for i, (key, _tk, kind) in enumerate(cat):
        g = group_of(key, kind)
        if g != last:
            out.append(("head", g))
            last = g
        out.append(("track", i))
    return out


def list_window(lines, index, height, top=0):
    """(first line shown, last line shown + 1): every line when they fit, else a window that keeps the cursor in view
    and moves only when it leaves it (`top`: the first line shown so far)."""
    def h(line):
        return HEAD_H if line[0] == "head" else ROW_H
    if sum(h(ln) for ln in lines) <= height:
        return 0, len(lines)
    sel = next((k for k, ln in enumerate(lines) if ln == ("track", index)), 0)
    top = max(0, min(top, len(lines) - 1))
    if sel < top:
        top = sel
        if top > 0 and lines[top - 1][0] == "head":            # (the title of its group with it)
            top -= 1
    while True:
        used, end = 0, top
        while end < len(lines) and used + h(lines[end]) <= height:
            used += h(lines[end])
            end += 1
        if sel < end or top >= sel:
            return top, end
        top += 1


def draw_list(game, surface, box, cat, index, playing_key, paused, durations, titles, style):
    st = STYLES[style]
    f_row, f_head, f_small = fonts.text(20), fonts.title(14), fonts.body(16)
    lines = list_lines(cat)
    inner_h = box.h - (30 if style == "adventure" else 24)
    top, end = list_window(lines, index, inner_h, int(getattr(game, "_juke_top", 0) or 0))
    game._juke_top = top
    y = box.y + (18 if style == "adventure" else 12)            # (below the hazard strip of the plate)
    numbers = {}
    for key, _tk, kind in cat:
        if kind == "music":
            numbers[key] = len(numbers) + 1
    for line in lines[top:end]:
        if line[0] == "head":
            h = game._txt(f_head, group_title(line[1]), st["head"])
            surface.blit(h, (box.x + 18, y + (HEAD_H - h.get_height()) // 2 + 2))
            ly = y + HEAD_H // 2 + 2
            pygame.draw.line(surface, st["rule"], (box.x + 26 + h.get_width(), ly), (box.right - 18, ly), 1)
            y += HEAD_H
            continue
        i = line[1]
        key, _tk, kind = cat[i]
        r = pygame.Rect(box.x + 10, y, box.w - 20, ROW_H - 4)
        sel = i == index
        playing = key == playing_key
        if sel:
            if style == "adventure":
                phobos_ui.lit(surface, r)
            else:
                menu_ui.highlight(surface, r)
        col = st["sel"] if sel else (PLAYING if playing else st["text"])
        dim = st["dim_sel"] if sel else st["dim"]
        cy = r.centery
        if playing:
            play_mark(surface, r.x + 12, cy, PLAYING, paused)
        elif kind == "video":
            film_mark(surface, r.x + 10, cy, dim)
        else:
            num = game._txt(f_small, f"{numbers.get(key, 0):02d}", dim)
            surface.blit(num, (r.x + 10, cy - num.get_height() // 2))
        length = durations.get(key) or 0
        right = r.right - 10
        if length > 1:
            d = game._txt(f_small, mmss(length), dim)
            surface.blit(d, (right - d.get_width(), cy - d.get_height() // 2))
        _artist, main, rest = split_title(titles[key])
        label = game._txt(f_row, main, col)
        suffix = game._txt(f_small, rest, dim) if rest else None
        room = r.w - 42 - 64
        need = label.get_width() + (8 + suffix.get_width() if suffix else 0)
        if need > room:                                         # squeezed a little, never cut
            k = room / need
            label = _squeeze(label, int(label.get_width() * k))
            if suffix:
                suffix = _squeeze(suffix, int(suffix.get_width() * k))
        surface.blit(label, (r.x + 42, cy - label.get_height() // 2))
        if suffix:
            surface.blit(suffix, (r.x + 42 + label.get_width() + 8, cy - suffix.get_height() // 2 + 2))
        y += ROW_H
    arrows(surface, box, top > 0, end < len(lines), st["sel"])
    return top, end


def arrows(surface, box, up, down, col):
    """Small arrows on the edges of the list when there is more above or below."""
    cx = box.centerx
    for show, y, way in ((up, box.top + 4, -1), (down, box.bottom - 5, 1)):
        if show:
            pygame.draw.polygon(surface, col, [(cx - 9, y - way * 3), (cx + 9, y - way * 3), (cx, y + way * 5)])


def play_mark(surface, x, cy, col, paused=False):
    if paused:
        pygame.draw.rect(surface, col, (x, cy - 7, 4, 14))
        pygame.draw.rect(surface, col, (x + 8, cy - 7, 4, 14))
    else:
        pygame.draw.polygon(surface, col, [(x, cy - 8), (x, cy + 8), (x + 13, cy)])


def film_mark(surface, x, cy, col):
    pygame.draw.rect(surface, col, (x, cy - 7, 16, 14), 2, border_radius=2)
    pygame.draw.polygon(surface, col, [(x + 6, cy - 4), (x + 6, cy + 4), (x + 12, cy)])


def draw_now(game, surface, box, key, path, title, state, pos, dur, bands, peaks, style):
    """The card of the track playing (`state` "play" / "pause"), or of the one under the cursor ("idle")."""
    st = STYLES[style]
    art = cover(key, path, COVER)
    cx, cy = box.x + 16, box.y + 16
    if style == "adventure":
        pygame.draw.rect(surface, st["frame"], (cx - 4, cy - 4, COVER + 8, COVER + 8), 3, border_radius=3)
    else:
        pygame.draw.rect(surface, st["frame"], (cx - 3, cy - 3, COVER + 6, COVER + 6), 2, border_radius=4)
    surface.blit(art, (cx, cy))
    x = cx + COVER + 26
    w = box.right - 22 - x
    label = {"play": "juke_now_playing", "pause": "juke_paused"}.get(state, "juke_selected")
    surface.blit(game._txt(fonts.title(14), t(label), st["label"]), (x, box.y + 18))
    artist, main, rest = split_title(title)
    f_t = fonts.text(30)
    y = box.y + 40
    for part in _wrap(f_t, main, w)[:2]:
        img = _squeeze(game._txt(f_t, part, st["title"]), w)
        surface.blit(img, (x, y))
        y += f_t.get_linesize() - 2
    sub = [p for p in (artist, "Eternal Dawn" if key.startswith("lyra_") else "", rest.strip("()")) if p]
    if sub:
        img = _squeeze(game._txt(fonts.body(18), "  ·  ".join(sub), st["sub"]), w)
        surface.blit(img, (x, y + 2))
    draw_rack(surface, pygame.Rect(x, box.y + 112, w, 62), bands, peaks, style)
    if state != "idle" and dur > 1.0:
        draw_seek(game, surface, x, box.y + 196, w, pos, dur, style)


def draw_rack(surface, rect, bands, peaks, style):
    """The LED rack, compact: one column of RACK_CELLS cells per band, green, then yellow, then red; the peak cell lit."""
    st = STYLES[style]
    n = len(bands) or 40
    gap = 2
    cw = (rect.w - gap * (n - 1)) / n
    ch = (rect.h - (RACK_CELLS - 1) * 2) / RACK_CELLS
    for i in range(n):
        v = bands[i] if i < len(bands) else 0.0
        pk = peaks[i] if i < len(peaks) else 0.0
        lit_n = int(round(max(0.0, min(1.0, v)) * RACK_CELLS))
        peak = int(round(max(0.0, min(1.0, pk)) * RACK_CELLS)) - 1
        rx = int(rect.x + i * (cw + gap))
        for c in range(RACK_CELLS):
            zone = 0 if c < 6 else (1 if c < 8 else 2)
            on = c < lit_n or (c == peak and peak >= 0)
            ry = int(rect.bottom - (c + 1) * ch - c * 2)
            colour = (st["rack"] if on else st["rack_off"])[zone]
            pygame.draw.rect(surface, colour, (rx, ry, max(1, int(cw)), max(1, int(ch))))


def draw_seek(game, surface, x, y, w, pos, dur, style):
    """The seek bar and the clock, on one line."""
    st = STYLES[style]
    clock = game._txt(fonts.text(20), f"{mmss(pos)} / {mmss(dur)}", PLAYING)
    bar_w = w - clock.get_width() - 18
    pygame.draw.rect(surface, st["track"], (x, y - 3, bar_w, 6), border_radius=3)
    fill = int(bar_w * max(0.0, min(1.0, pos / dur))) if dur > 0 else 0
    pygame.draw.rect(surface, (255, 190, 90), (x, y - 3, fill, 6), border_radius=3)
    pygame.draw.circle(surface, (255, 230, 170), (x + fill, y), 7)
    surface.blit(clock, (x + bar_w + 18, y - clock.get_height() // 2))


def _fade(size, edge=46):
    """A mask that fades the top and the bottom of the lyrics."""
    out = _fades.get((size, edge))
    if out is None:
        out = pygame.Surface(size, pygame.SRCALPHA)
        out.fill((255, 255, 255, 255))
        w, h = size
        for k in range(edge):
            a = int(255 * (k / edge) ** 1.3)
            pygame.draw.line(out, (255, 255, 255, a), (0, k), (w, k))
            pygame.draw.line(out, (255, 255, 255, a), (0, h - 1 - k), (w, h - 1 - k))
        _fades[(size, edge)] = out
    return out


def draw_lyrics(game, surface, rect, key, pos, dur, playing, style="arcade"):
    """The lyrics of `key` in `rect` (the panel itself is drawn by the caller)."""
    st = STYLES[style]
    hdr = game._txt(fonts.title(16), t("juke_lyrics"), st["ly_head"])
    surface.blit(hdr, (rect.x + 20, rect.y + 14))
    data = lyrics(key) if key else None
    inner = pygame.Rect(rect.x + 22, rect.y + 46, rect.w - 44, rect.h - 58)
    if data is None:
        msg = t("juke_no_lyrics") if (key or "").startswith("lyra_") else t("juke_instrumental")
        img = game._txt(fonts.text(22), msg, st["ly_tag"])
        surface.blit(img, (inner.centerx - img.get_width() // 2, inner.centery - img.get_height() // 2))
        return
    lang = get_lang()
    sung = data["lang"]
    show_tr = sung != lang
    tag = game._txt(fonts.body(15), f"{sung.upper()}  →  {lang.upper()}" if show_tr else sung.upper(), st["ly_tag"])
    surface.blit(tag, (rect.right - 20 - tag.get_width(), rect.y + 16))
    lines = data["lines"]
    cur = _current_line(lines, pos, dur)[0] if (playing or pos > 0) else -1
    sung_lines = [i for i, ln in enumerate(lines) if ln.get("text")]
    if not sung_lines:
        return
    after = [k for k, i in enumerate(sung_lines) if i >= cur] if cur >= 0 else [0]
    k_cur = next((k for k, i in enumerate(sung_lines) if i == cur), None)
    focus = k_cur if k_cur is not None else (after[0] if after else len(sung_lines) - 1)
    f_cur, f_main, f_trc, f_tr = fonts.text(26), fonts.text(21), fonts.body(19), fonts.body(17)
    text_w = inner.w - 20
    pick = range(max(0, focus - 3), min(len(sung_lines), focus + 6))
    blocks = []
    for k in pick:
        ln = lines[sung_lines[k]]
        rel = 0 if k == k_cur else (-1 if (k_cur is not None and k < k_cur) or k < focus else 1)
        is_cur = rel == 0
        c_main = st["ly_cur"] if is_cur else (st["ly_past"] if rel < 0 else st["ly_next"])
        c_tr = st["tr_cur"] if is_cur else (st["tr_past"] if rel < 0 else st["tr_next"])
        fm, ft = (f_cur, f_trc) if is_cur else (f_main, f_tr)
        imgs = [game._txt(fm, p, c_main) for p in _wrap(fm, ln.get("text", ""), text_w)]
        tr = (ln.get("tr") or {}).get(lang, "") if show_tr else ""
        if tr:
            imgs += [game._txt(ft, p, c_tr) for p in _wrap(ft, tr, text_w)]
        blocks.append((k, imgs, is_cur))
    gap = 14
    heights = [sum(im.get_height() for im in imgs) for _k, imgs, _c in blocks]
    fi = next(n for n, (k, _i, _c) in enumerate(blocks) if k == focus)
    ys = [0] * len(blocks)
    ys[fi] = (int(inner.h * 0.40) - heights[fi] // 2) if k_cur is not None else 34     # (idle: below the fade)
    for n in range(fi - 1, -1, -1):
        ys[n] = ys[n + 1] - gap - heights[n]
    for n in range(fi + 1, len(blocks)):
        ys[n] = ys[n - 1] + heights[n - 1] + gap
    layer = pygame.Surface(inner.size, pygame.SRCALPHA)
    for (_k, imgs, is_cur), y0, h in zip(blocks, ys, heights):
        if y0 + h < 0 or y0 > inner.h:
            continue
        if is_cur:
            bar = pygame.Rect(0, y0 - 6, inner.w, h + 12)
            pygame.draw.rect(layer, st["ly_bar"] + (24,), bar, border_radius=6 if style == "arcade" else 3)
            pygame.draw.rect(layer, st["ly_bar"] + (255,), (0, bar.y + 4, 3, bar.h - 8))
        yy = y0
        for im in imgs:
            layer.blit(im, (14, yy))
            yy += im.get_height()
    layer.blit(_fade(inner.size), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(layer, inner.topleft)


def draw_header(game, surface, style):
    if style == "adventure":
        phobos_ui.title(surface, game.medium_font, t("jukebox"), surface.get_width() // 2, 10)
        story = getattr(game, "story", None)
        state = getattr(story, "state", None) or {}
        if state.get("name"):
            mode = t("story_mode_" + str(state.get("mode", "normal")))
            phobos_ui.badge(surface, game.font, f"{state['name']}  -  {mode}", (200, 205, 222), 40, left=56, max_w=330)
        return
    hdr = game._txt(game.medium_font, t("jukebox"), menu_ui.TITLE)
    surface.blit(hdr, (surface.get_width() // 2 - hdr.get_width() // 2, 28))


def panel(surface, rect, which, style):
    """The three panels: the list, the card of the track playing, the lyrics."""
    if style == "adventure":
        if which == "list":
            phobos_ui.plate(surface, rect, hazard=True)
        elif which == "now":
            phobos_ui.holo(surface, rect, glass=225)
        else:
            phobos_ui.crt(surface, rect)
    else:
        menu_ui.panel(surface, rect)
