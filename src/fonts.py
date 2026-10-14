"""
The game's own fonts, shipped in assets/fonts (free licences: the .txt files next to them).

- Audiowide: the titles of the screens and the main menu (game.big_font, game.medium_font);
- Play Bold: the menus, the help bar, the HUD (game.font, game.menu_font, hint_bar);
- Play Regular: what is read at length (the help of the options, the descriptions, the help pages, the Adventure's
  story) (game.body_font, game.read_font);
- DejaVu Sans Bold, reduced to Latin, Greek, Cyrillic and the symbols: what the others lack (the arrows first).
  It is also the font the menus used before, through the system: the sizes are measured against it.

Sizes are asked as before, in the size the old system font had: each font is scaled so that its capitals are as tall
as the old ones, and the layouts keep their room.

A missing letter: a title in a language its font cannot write (Audiowide has no Cyrillic) is written whole in
Play Bold, never two alphabets in one word. A missing symbol (← ↑ ↓ →) comes from DejaVu, the rest of the line staying
in its font. A missing or broken file: the system fonts used before take over, the game never stops for a font.
"""
import os
import struct

import pygame

from errlog import log_exc
from settings import asset_path

TITLE_FILE = "Audiowide-Regular.ttf"
BOLD_FILE = "Play-Bold.ttf"
REGULAR_FILE = "Play-Regular.ttf"
SPARE_FILE = "DejaVuSans-Bold-Spare.ttf"
SYSTEM = "dejavusans,segoe ui,arial,consolas,notosans"      # the fonts of the menus before, kept as the last resort

_fonts = {}            # (kind, size) -> font
_points = {}           # file -> set of the code points it can draw
_caps = {}             # file -> capital height for a size of 100


def codepoints(path):
    """The characters a TrueType / OpenType file can draw (read from its 'cmap' table, formats 4 and 12)."""
    with open(path, "rb") as fh:
        data = fh.read()
    count = struct.unpack(">H", data[4:6])[0]
    cmap = None
    for i in range(count):
        tag, _sum, off, _len = struct.unpack(">4sIII", data[12 + 16 * i:28 + 16 * i])
        if tag == b"cmap":
            cmap = off
    if cmap is None:
        return set()
    best = None
    for i in range(struct.unpack(">H", data[cmap + 2:cmap + 4])[0]):
        pid, eid, off = struct.unpack(">HHI", data[cmap + 4 + 8 * i:cmap + 12 + 8 * i])
        fmt = struct.unpack(">H", data[cmap + off:cmap + off + 2])[0]
        rank = {12: 2, 4: 1}.get(fmt, 0) if pid in (0, 3) else 0
        if rank and (best is None or rank > best[0]):
            best = (rank, cmap + off, fmt)
    points = set()
    if best is None:
        return points
    _rank, st, fmt = best
    if fmt == 12:
        groups = struct.unpack(">I", data[st + 12:st + 16])[0]
        for g in range(groups):
            first, last, _glyph = struct.unpack(">III", data[st + 16 + 12 * g:st + 28 + 12 * g])
            points.update(range(first, last + 1))
        return points
    seg2 = struct.unpack(">H", data[st + 6:st + 8])[0]
    ends = st + 14
    starts = ends + seg2 + 2
    deltas = starts + seg2
    offsets = deltas + seg2
    for s in range(seg2 // 2):
        end = struct.unpack(">H", data[ends + 2 * s:ends + 2 * s + 2])[0]
        start = struct.unpack(">H", data[starts + 2 * s:starts + 2 * s + 2])[0]
        delta = struct.unpack(">h", data[deltas + 2 * s:deltas + 2 * s + 2])[0]
        roff_at = offsets + 2 * s
        roff = struct.unpack(">H", data[roff_at:roff_at + 2])[0]
        for c in range(start, end + 1):
            if c == 0xFFFF:
                continue
            if roff == 0:
                glyph = (c + delta) & 0xFFFF
            else:
                at = roff_at + roff + 2 * (c - start)
                glyph = struct.unpack(">H", data[at:at + 2])[0]
                if glyph:
                    glyph = (glyph + delta) & 0xFFFF
            if glyph:
                points.add(c)
    return points


def _path(name):
    return asset_path("fonts", name)


def _cap(name):
    """Height of the capitals of a file's font at size 100."""
    h = _caps.get(name)
    if h is None:
        h = _caps[name] = max(1, pygame.font.Font(_path(name), 100).metrics("H")[0][3])
    return h


def _points_of(name):
    p = _points.get(name)
    if p is None:
        p = _points[name] = codepoints(_path(name))
    return p


class GameFont(pygame.font.Font):
    """A shipped font that hands what it cannot draw to others: a whole string to `whole` when a letter is missing
    (a title in Russian), a run of symbols to `spare` (the arrows). Otherwise a plain pygame font."""

    def __init__(self, name, size, spare=None, whole=None):
        super().__init__(_path(name), size)
        self._has = _points_of(name)
        self._spare = spare
        self._whole = whole

    def _lacks(self, text):
        return any(ord(ch) not in self._has and ch not in "\n\r\t" for ch in text)

    def _use_whole(self, text):
        return self._whole is not None and any(ch.isalpha() and ord(ch) not in self._has for ch in text)

    def _runs(self, text):
        runs = []
        for ch in text:
            mine = ord(ch) in self._has or self._spare is None
            if runs and runs[-1][0] == mine:
                runs[-1][1] += ch
            else:
                runs.append([mine, ch])
        return runs

    def _set_style(self, other):
        other.set_italic(self.get_italic())
        other.set_underline(self.get_underline())

    def _fit(self, img, other, background=None):
        """`img` (drawn with `other`) on this font's height, on the same baseline."""
        out = pygame.Surface((img.get_width(), self.get_height()), pygame.SRCALPHA)
        if background is not None:
            out.fill(background)
        out.blit(img, (0, max(0, self.get_ascent() - other.get_ascent())))
        return out

    def render(self, text, antialias=True, color=(255, 255, 255), background=None):
        text = "" if text is None else str(text)
        if not text or not self._lacks(text):
            return super().render(text, antialias, color, background)
        if self._use_whole(text):
            self._set_style(self._whole)
            return self._fit(self._whole.render(text, antialias, color), self._whole, background)
        runs = self._runs(text)
        if len(runs) == 1 and runs[0][0]:
            return super().render(text, antialias, color, background)
        imgs = []
        for mine, part in runs:
            if mine:
                imgs.append((super().render(part, antialias, color), 0))
            else:
                self._set_style(self._spare)
                img = self._spare.render(part, antialias, color)
                imgs.append((img, max(0, self.get_ascent() - self._spare.get_ascent())))
        out = pygame.Surface((sum(i.get_width() for i, _ in imgs), self.get_height()), pygame.SRCALPHA)
        if background is not None:
            out.fill(background)
        x = 0
        for img, dy in imgs:
            out.blit(img, (x, dy))
            x += img.get_width()
        return out

    def size(self, text):
        text = "" if text is None else str(text)
        if not text or not self._lacks(text):
            return super().size(text)
        if self._use_whole(text):
            self._set_style(self._whole)
            return (self._whole.size(text)[0], self.get_height())
        w = 0
        for mine, part in self._runs(text):
            if mine:
                w += super().size(part)[0]
            else:
                self._set_style(self._spare)
                w += self._spare.size(part)[0]
        return (w, self.get_height())


def _system(size):
    return pygame.font.SysFont(SYSTEM, size, bold=True)


def _scaled(name, size):
    """The size of `name` whose capitals are as tall as the old font's at `size`."""
    return max(6, int(round(size * _cap(SPARE_FILE) / _cap(name))))


def _make(kind, size):
    if kind == "spare":
        return pygame.font.Font(_path(SPARE_FILE), size)
    spare = get("spare", size)
    if kind == "title":
        return GameFont(TITLE_FILE, _scaled(TITLE_FILE, size), spare=spare, whole=get("bold", size))
    name = BOLD_FILE if kind == "bold" else REGULAR_FILE
    return GameFont(name, _scaled(name, size), spare=spare)


def get(kind, size):
    """A font: kind 'title', 'bold' (menus), 'regular' (reading) or 'spare' (DejaVu), `size` in the old font's size."""
    key = (kind, int(size))
    f = _fonts.get(key)
    if f is None:
        if not pygame.font.get_init():
            pygame.font.init()
        try:
            f = _make(kind, int(size))
        except Exception:
            log_exc("fonts.get")
            f = _system(int(size))
        _fonts[key] = f
    return f


def title(size):
    return get("title", size)


def text(size):
    return get("bold", size)


def body(size):
    return get("regular", size)
