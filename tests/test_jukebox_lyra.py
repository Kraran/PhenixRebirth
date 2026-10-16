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


# ------------------------------------------------------------------ the list
def test_the_four_songs_come_after_the_soundtrack_before_the_video(run):
    g = run.game
    keys = [k for k, _t, _kind in g._juke_catalog()]
    assert keys[-5:] == list(LYRA) + ["intro"]
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
    lang("en")
    assert g._juke_title("lyra_no_mercy_left") == "Lyra Voss - No Mercy Left (Adventure)"
    from mp3_title import title_from_path
    assert title_from_path(asset_path("music", "Lyra-Voss-Oldest-Fear.mp3")) == "Lyra Voss - Oldest Fear"   # its tag


def test_the_list_scrolls_to_keep_the_cursor_on_screen(run):
    g = run.game
    n = len(g._juke_catalog())
    assert n > g.JUKE_ROWS
    g._juke_top = 0
    seen = []
    for i in range(n):
        top = g._juke_scroll(i, n)
        assert top <= i < top + g.JUKE_ROWS
        seen.append(top)
    assert seen[0] == 0 and seen[-1] == n - g.JUKE_ROWS
    assert g._juke_scroll(n - 2, n) == n - g.JUKE_ROWS            # going back up: the list stays where it is
    assert g._juke_scroll(0, n) == 0                              # wrapping to the top


def test_the_list_fits_above_the_clock(run):
    g = run.game
    g._open_jukebox()
    surf = pygame.Surface((1280, 720)).convert()
    boxes = []
    real = game_mod.menu_ui.draw_rows

    def spy(*a, **k):
        boxes.append(real(*a, **k))
        return boxes[-1]
    game_mod.menu_ui.draw_rows = spy
    try:
        for i in range(len(g._juke_catalog())):
            g.juke_index = i
            g._draw_jukebox(surf)
    finally:
        game_mod.menu_ui.draw_rows = real
    assert max(b.bottom for b in boxes) + 20 < pheq.clock_y(720)
    assert len({b.width for b in boxes}) == 1                     # the panel keeps its width while it scrolls


# ------------------------------------------------------------------ the rack stays on the track playing
def _seek_spy(monkeypatch):
    calls = []
    monkeypatch.setattr(game_mod, "pheq_draw_seek", lambda surface, pg, pos, dur, w, h: calls.append(dur))
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
