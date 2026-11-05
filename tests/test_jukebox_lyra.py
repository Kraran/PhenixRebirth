"""Lyra Voss in the jukebox: the three songs of her concert in the Adventure ("Lyra Voss - Eternal Dawn (Aventure)"...)
and Oldest Fear, each with its .pheq file (tools/make_pheq.py, the recipe of the original files); the list scrolls;
the LED rack, the seek bar and the clock stay on the track playing while the cursor moves, until another one is
played."""
import os
import struct
import sys

import pygame
import pytest

import game as game_mod
import pheq
from settings import asset_path
from test_smoke import run  # noqa: F401  (fixture)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

LYRA = {
    "lyra_eternal_dawn": ("Eternal Dawn", 307.5),
    "lyra_what_we_lost": ("What We Lost", 288.0),
    "lyra_no_mercy_left": ("No Mercy Left", 226.4),
    "lyra_oldest_fear": ("Oldest Fear", 251.2),
    "lyra_when_we_looked_up": ("When We Looked Up", 271.5),
    "lyra_when_we_looked_up_unplugged": ("When We Looked Up (Unplugged)", 269.1),
}


@pytest.fixture
def lang():
    from i18n import get_lang, set_lang
    before = get_lang()
    yield set_lang
    set_lang(before)


class _Music:
    """Stands for pygame.mixer.music: a track that plays, at `pos` seconds."""

    def __init__(self):
        self.path, self.pos, self.busy = None, 0.0, False

    def load(self, path):
        self.path = path

    def play(self, loops=0):
        self.busy = True

    def stop(self):
        self.busy = False

    def pause(self):
        pass

    def unpause(self):
        pass

    def set_volume(self, v):
        pass

    def fadeout(self, ms):
        self.busy = False

    def get_busy(self):
        return self.busy

    def get_pos(self):
        return int(self.pos * 1000)


@pytest.fixture
def music(monkeypatch):
    m = _Music()
    monkeypatch.setattr(pygame.mixer, "music", m)
    return m


# ------------------------------------------------------------------ the files
def test_the_generator_makes_the_original_files_again():
    import make_pheq
    import videoclip
    if not videoclip.find_ffmpeg():
        pytest.skip("no ffmpeg")
    name = "Phenix-Nostalgie-Elise"
    raw = open(asset_path("music", name + ".pheq"), "rb").read()
    n = struct.unpack("<I", raw[13:17])[0]
    made = make_pheq.make(make_pheq.decode(asset_path("music", name + ".mp3")))
    assert made.shape == (n, 40)
    import numpy as np
    original = np.frombuffer(raw[17:], np.uint8).reshape(n, 40).astype(int)
    diff = np.abs(made.astype(int) - original)
    assert (diff <= 1).mean() > 0.998                       # the same file, but for the rounding of a few values


@pytest.mark.parametrize("key", list(LYRA))
def test_each_song_has_its_sound_and_its_pheq(key):
    from sounds import LYRA_MUSIC
    folder, name, length = LYRA_MUSIC[key]
    assert os.path.isfile(asset_path(folder, name))
    path = pheq.resolve_path(asset_path, key)
    assert path and os.path.basename(path) == pheq.PHEQ_FILES[key]
    seq = pheq.load_pheq(path)
    assert seq["n"] == 40 and seq["fps"] == 24
    assert abs(len(seq["frames"]) / 24.0 - length) < 1.0 and abs(length - LYRA[key][1]) < 1.0
    mid = pheq.sample(seq, length / 2)
    assert len(mid) == 40 and max(mid) > 0.3                 # music, not silence


def test_the_concert_songs_are_the_sound_of_the_films():
    import story_state as ss
    from sounds import LYRA_MUSIC
    for fid, key in (("lyra_1", "lyra_eternal_dawn"), ("lyra_2", "lyra_what_we_lost"), ("lyra_3", "lyra_no_mercy_left")):
        assert ss.film_files(fid)[1] == asset_path(*LYRA_MUSIC[key][:2])
    assert ss.film_bg("vn_concert_1")["files"][1] == asset_path(*LYRA_MUSIC["lyra_when_we_looked_up"][:2])


# ------------------------------------------------------------------ the list
def test_the_four_songs_come_after_the_soundtrack_before_the_video(run):
    g = run.game
    keys = [k for k, _t, _kind in g._juke_catalog()]
    assert keys[-len(LYRA) - 1:] == list(LYRA) + ["intro"]
    for key in LYRA:
        assert os.path.isfile(g.sounds._music_paths[key])
        assert abs(g.sounds.music_duration(key) - LYRA[key][1]) < 1.0


def test_their_titles(run, lang):
    g = run.game
    lang("fr")
    assert g._juke_title("lyra_eternal_dawn") == "Lyra Voss - Eternal Dawn (Aventure)"
    assert g._juke_title("lyra_what_we_lost") == "Lyra Voss - What We Lost (Aventure)"
    assert g._juke_title("lyra_no_mercy_left") == "Lyra Voss - No Mercy Left (Aventure)"
    assert g._juke_title("lyra_oldest_fear") == "Lyra Voss - Oldest Fear"
    assert g._juke_title("lyra_when_we_looked_up") == "Lyra Voss - When We Looked Up"
    assert g._juke_title("lyra_when_we_looked_up_unplugged") == "Lyra Voss - When We Looked Up (Unplugged)"
    lang("en")
    assert g._juke_title("lyra_no_mercy_left") == "Lyra Voss - No Mercy Left (Adventure)"
    from mp3_title import title_from_path
    assert title_from_path(asset_path("music", "Lyra-Voss-Oldest-Fear.mp3")) == "Lyra Voss - Oldest Fear"   # its tag
    assert (title_from_path(asset_path("music", "Lyra-Voss-When-We-Looked-Up-Unplugged.mp3"))
            == "Lyra Voss - When We Looked Up (Unplugged)")


def test_the_whole_list_fits_in_groups(run):
    """Every track on screen at once, in three groups (Phenix, Lyra Voss, the video), each one a line of the list."""
    import jukebox_ui
    g = run.game
    cat = g._juke_catalog()
    lines = jukebox_ui.list_lines(cat)
    assert [ln[1] for ln in lines if ln[0] == "head"] == ["phenix", "lyra", "video"]
    assert [ln[1] for ln in lines if ln[0] == "track"] == list(range(len(cat)))
    for i in range(len(cat)):
        assert jukebox_ui.list_window(lines, i, jukebox_ui.LIST_BOX.h - 30) == (0, len(lines))


def test_a_list_too_long_scrolls_to_keep_the_cursor_on_screen(run):
    import jukebox_ui
    cat = run.game._juke_catalog()
    lines = jukebox_ui.list_lines(cat)
    height = 6 * jukebox_ui.ROW_H
    top = 0
    for i in list(range(len(cat))) + list(range(len(cat) - 1, -1, -1)):
        top, end = jukebox_ui.list_window(lines, i, height, top)
        shown = [ln for ln in lines[top:end]]
        assert ("track", i) in shown
        assert sum(jukebox_ui.HEAD_H if ln[0] == "head" else jukebox_ui.ROW_H for ln in shown) <= height
    assert jukebox_ui.list_window(lines, 0, height, top)[0] == 0


@pytest.mark.parametrize("door", (False, True))
def test_the_panels_never_overlap_and_stay_above_the_help_bar(run, door):
    """The list, the card of the track playing and the lyrics: side by side, above the help bar, in both styles."""
    import hint_bar
    import jukebox_ui
    import phobos_ui
    g = run.game
    if door:
        g.story_door = "jukebox"
        g._door_picture = lambda: pygame.Surface((1280, 720))
    g._open_jukebox()
    assert jukebox_ui.style_of(g) == ("adventure" if door else "arcade")
    surf = pygame.Surface((1280, 720)).convert()
    boxes = []
    real = jukebox_ui.panel

    def spy(surface, rect, which, style):
        boxes.append((which, pygame.Rect(rect), style))
        return real(surface, rect, which, style)
    jukebox_ui.panel = spy
    try:
        for i in range(len(g._juke_catalog())):
            g.juke_index = i
            g._draw_jukebox(surf)
    finally:
        jukebox_ui.panel = real
    rects = {which: r for which, r, _st in boxes}
    assert set(rects) == {"list", "now", "lyrics"}
    assert {st for _w, _r, st in boxes} == {"adventure" if door else "arcade"}
    for a in rects.values():
        assert a.bottom <= hint_bar.BAND_Y and a.right <= 1280 - 30 and a.top >= 70
        assert all(not a.colliderect(b) for b in rects.values() if b is not a)


def test_long_titles_are_squeezed_never_cut(run, monkeypatch):
    import jukebox_ui
    g = run.game
    drawn = []
    monkeypatch.setattr(g, "_txt", lambda font, text, col: drawn.append(text) or pygame.Surface((10 * len(text), 10)))
    surf = pygame.Surface((1280, 720))
    cat = g._juke_catalog()
    titles = {k: g._juke_title(k) for k, _t, _kind in cat}
    jukebox_ui.draw_list(g, surf, jukebox_ui.LIST_BOX, cat, 0, None, False, {}, titles, "arcade")
    assert "When We Looked Up" in drawn and "(Unplugged)" in drawn and "Eternal Dawn II" in drawn
    assert not any(text.endswith("…") for text in drawn)
    assert jukebox_ui.split_title("Lyra Voss - Eternal Dawn (Aventure)") == ("Lyra Voss", "Eternal Dawn", "(Aventure)")
    # a title too wide for its row (here, very wide letters): squeezed into the room between the number and the length
    monkeypatch.setattr(g, "_txt", lambda font, text, col: pygame.Surface((30 * len(text), 10)))
    widths = []
    real = jukebox_ui._squeeze
    monkeypatch.setattr(jukebox_ui, "_squeeze", lambda img, w: widths.append(w) or real(img, w))
    jukebox_ui.draw_list(g, surf, jukebox_ui.LIST_BOX, cat, 0, None, False, {}, titles, "arcade")
    room = jukebox_ui.LIST_BOX.w - 20 - 42 - 64
    assert widths and max(widths) <= room


def test_lyrics_original_and_translation(run, lang, tmp_path, monkeypatch):
    """A lyrics file: the line sung, and under it its translation in the interface language (not when the song is
    already in that language); an empty template counts as no lyrics."""
    import json
    import jukebox_ui
    monkeypatch.setattr(jukebox_ui, "LYRICS_DIR", str(tmp_path))
    jukebox_ui._lyrics.clear()
    (tmp_path / "lyra_x.json").write_text(json.dumps({"lang": "en", "lines": [
        {"t": 0, "text": "A", "tr": {"fr": "a-fr"}}, {"t": 5, "text": "B", "tr": {"fr": "b-fr"}}]}))
    (tmp_path / "lyra_empty.json").write_text(json.dumps({"lang": "en", "lines": []}))
    assert jukebox_ui.lyrics("lyra_empty") is None
    assert jukebox_ui._current_line(jukebox_ui.lyrics("lyra_x")["lines"], 6.0, 10.0)[0] == 1
    drawn = []
    g = run.game
    monkeypatch.setattr(g, "_txt", lambda font, text, col: drawn.append(text) or pygame.Surface((10, 10)))
    surf = pygame.Surface((1280, 720))
    for code, want in (("fr", True), ("en", False)):
        lang(code)
        drawn.clear()
        jukebox_ui.draw_lyrics(g, surf, pygame.Rect(0, 0, 400, 300), "lyra_x", 6.0, 10.0, True)
        jukebox_ui.draw_lyrics(g, surf, pygame.Rect(0, 0, 400, 300), "lyra_x", 6.0, 10.0, True, "adventure")
        assert "B" in drawn and ("b-fr" in drawn) == want
    jukebox_ui._lyrics.clear()


def test_covers_found(run):
    """Every track has a cover: its own file, the picture inside the MP3, Lyra's picture, or the drawn disc."""
    import jukebox_ui
    g = run.game
    paths = g.sounds._music_paths
    for key, _t, _k in g._juke_catalog():
        assert jukebox_ui.cover(key, paths.get(key), 120).get_size() == (120, 120)
    assert jukebox_ui._apic(paths["menu"])                          # the soundtrack MP3s carry their artwork
    assert os.path.isfile(os.path.join(jukebox_ui.COVER_DIR, "lyra_album.jpg"))   # the Eternal Dawn album


def test_real_lyrics_complete():
    """Every Lyra song carries its lyrics, translated into the 12 other languages on every sung line."""
    import json, jukebox_ui
    for key in ("lyra_eternal_dawn", "lyra_what_we_lost", "lyra_no_mercy_left", "lyra_oldest_fear",
                "lyra_when_we_looked_up", "lyra_when_we_looked_up_unplugged"):
        d = json.load(open(os.path.join(jukebox_ui.LYRICS_DIR, key + ".json"), encoding="utf-8"))
        sung = [l for l in d["lines"] if l["text"]]
        assert d["lang"] == "en" and len(sung) > 20
        for l in sung:
            assert len(l["tr"]) == 12 and all(l["tr"].values())


# ------------------------------------------------------------------ the rack stays on the track playing
def _seek_spy(monkeypatch):
    calls = []
    import jukebox_ui
    monkeypatch.setattr(jukebox_ui, "draw_seek", lambda game, surface, x, y, w, pos, dur, style: calls.append(dur))
    return calls


def test_the_rack_stays_while_the_cursor_moves_until_another_track_is_played(run, music, monkeypatch):
    g = run.game
    g._open_jukebox()
    surf = pygame.Surface((1280, 720)).convert()
    seeks = _seek_spy(monkeypatch)
    keys = [k for k, _t, _kind in g._juke_catalog()]
    g.juke_index = keys.index("lyra_eternal_dawn")
    g._juke_play_or_pause()
    music.pos = 60.0
    g._draw_jukebox(surf)
    assert seeks[-1] == pytest.approx(307.52, abs=0.1) and max(g._eq_bands) > 0
    for i in range(len(keys)):                                    # the whole list, the video included
        g.juke_index = i
        seeks.clear()
        g._draw_jukebox(surf)
        assert seeks == [pytest.approx(307.52, abs=0.1)]                   # still Eternal Dawn
    g.juke_index = keys.index("lyra_oldest_fear")
    g._juke_play_or_pause()                                       # another track: the rack follows it
    g.juke_index = 0
    seeks.clear()
    g._draw_jukebox(surf)
    assert g.sounds.current_music_key() == "lyra_oldest_fear" and seeks == [pytest.approx(251.18, abs=0.1)]
    assert "lyra_oldest_fear" in g._eq_seq and g._eq_seq["lyra_oldest_fear"] is not None


def test_paused_the_rack_stays_too(run, music, monkeypatch):
    g = run.game
    g._open_jukebox()
    surf = pygame.Surface((1280, 720)).convert()
    seeks = _seek_spy(monkeypatch)
    g.juke_index = 0
    g._juke_play_or_pause()
    g._juke_play_or_pause()                                       # pause
    assert g.juke_paused
    g.juke_index = 3
    g._draw_jukebox(surf)
    assert seeks and seeks[-1] == pytest.approx(g.sounds.music_duration("menu"))


def test_nothing_before_a_track_is_played(run, music, monkeypatch):
    g = run.game
    g._open_jukebox()
    surf = pygame.Surface((1280, 720)).convert()
    seeks = _seek_spy(monkeypatch)
    g._draw_jukebox(surf)
    assert seeks == []
