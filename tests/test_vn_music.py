"""The music of the visual novel (story_vn.scene_music): Lyra Voss's "When We Looked Up (Unplugged)" plays under scenes 3
(the observation deck) and 4 (the refuge), a little lower than normal; the other scenes keep the music of the menus."""
import os

import pygame
import pytest

import story_state as ss
import story_vn
from settings import asset_path
from sounds import LYRA_MUSIC
from test_smoke import run  # noqa: F401  (fixture)
from test_vn_endings import TOTALS, _hub

UNPLUGGED = "lyra_when_we_looked_up_unplugged"


@pytest.fixture(autouse=True)
def _natural(monkeypatch):
    monkeypatch.setattr(ss, "film_files", lambda film_id: None)
    monkeypatch.setattr(story_vn, "order", lambda sid, shuffled=True: list(range(len(story_vn.scene(sid)["answers"]))))


def test_scenes_3_and_4_have_the_unplugged_song_the_others_none():
    assert story_vn.scene_music("vn_3") == (UNPLUGGED, story_vn.VN_MUSIC_LEVEL)
    assert story_vn.scene_music("vn_4") == (UNPLUGGED, story_vn.VN_MUSIC_LEVEL)
    for sid in ("vn_1", "vn_2", "vn_5", "nothing"):
        assert story_vn.scene_music(sid) is None
    assert 0.3 < story_vn.VN_MUSIC_LEVEL < 1.0
    folder, name, _length = LYRA_MUSIC[UNPLUGGED]
    assert os.path.isfile(asset_path(folder, name))


@pytest.mark.parametrize("sid,want", [("vn_2", None), ("vn_3", UNPLUGGED), ("vn_4", UNPLUGGED), ("vn_5", None)])
def test_the_hub_asks_for_it_while_the_scene_is_on_screen(sid, want):
    pygame.init()
    hub = _hub(TOTALS[17], told=True)
    assert hub.scene_music() is None
    assert hub.start_vn(sid, back_to="log")
    got = hub.scene_music()
    assert (got[0] if got else None) == want
    hub.vn_phase = "react"
    assert (hub.scene_music() or (None,))[0] == want               # (and through Lyra's reaction)
    hub._end_vn()
    assert hub.scene_music() is None                                # back to the music of the menus


def test_in_the_game_the_song_comes_in_under_the_scene(run, monkeypatch):
    g = run.game
    played, levels = [], []
    monkeypatch.setattr(g.sounds, "play_music", lambda key, **kw: played.append(key))
    monkeypatch.setattr(g.sounds, "set_music_level", lambda level, seconds=0.0: levels.append(level))
    g.audio_mix = "sfx_music"
    g.started = False
    g.menu_screen = "story_hub"
    hub = _hub(TOTALS[17], told=True)
    g.story = hub
    assert hub.start_vn("vn_3", back_to="log")
    g._update_music()
    assert played[-1] == UNPLUGGED and levels[-1] == story_vn.VN_MUSIC_LEVEL
    assert g.sounds._music_paths.get(UNPLUGGED, "").endswith("Lyra-Voss-When-We-Looked-Up-Unplugged.mp3")
    hub._end_vn()
    g._update_music()
    assert played[-1] == "menu" and levels[-1] == 1.0
