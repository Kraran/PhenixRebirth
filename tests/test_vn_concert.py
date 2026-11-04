"""The concert of Lyra Voss after the two best endings of the visual novel (story_state.CONCERT_SCENES, story.py): Romance
goes on with concertmars, Amitie with concertmars_ecran; the picture alone for 2 seconds, then the film once with its
sound, then the picture again, the text going by over it as in every scene. The two other endings have no concert."""
import os

import pygame
import pytest

import i18n
import story_state as ss
import story_vn
import videoclip
from settings import BASE_HEIGHT, BASE_WIDTH, asset_path
from story import StoryHub
from test_vn_endings import TOTALS, _hub, _skip_pages


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((64, 64))
    yield


@pytest.fixture(autouse=True)
def _natural(monkeypatch):
    monkeypatch.setattr(ss, "film_files", lambda film_id: None)
    monkeypatch.setattr(story_vn, "order", lambda sid, shuffled=True: list(range(len(story_vn.scene(sid)["answers"]))))


class _Clip:
    """Stands for videoclip.ClipPlayer: `frames` frames, then ended."""
    made = []

    def __init__(self, path, size, shade=None, loop=True, fit="cover", hard_clock=False, frames=5, **kw):
        self.path, self.size, self.loop, self.fit, self.hard_clock = path, size, loop, fit, hard_clock
        self.left = frames
        self.failed = False
        self.closed = False
        self.surface = None
        _Clip.made.append(self)

    @property
    def ready(self):
        return True

    @property
    def playing(self):
        return self.surface is not None

    @property
    def ended(self):
        return self.left <= 0

    def pump(self):
        if self.left > 0:
            self.left -= 1
            self.surface = pygame.Surface(self.size)
            self.surface.fill((200, 10, 10))

    def close(self):
        self.closed = True


@pytest.fixture
def fake_clip(monkeypatch):
    _Clip.made = []
    monkeypatch.setattr(videoclip, "ClipPlayer", _Clip)
    heard = []
    monkeypatch.setattr(StoryHub, "_start_film_sound", lambda self, path: heard.append(path))
    stopped = []
    monkeypatch.setattr(pygame.mixer.music, "stop", lambda: stopped.append(True))
    return heard, stopped


def _to_the_end(total):
    """A save whose five answers give `total`, the ending read: what follows it is on screen."""
    hub = _hub(TOTALS[total])
    assert hub.start_vn_ending(back_to="map")
    _skip_pages(hub)
    return hub


# ------------------------------------------------------------------ which ending, which concert
@pytest.mark.parametrize("total,scene,picture", [(17, "vn_concert_1", "concertmars"), (20, "vn_concert_1", "concertmars"),
                                                 (13, "vn_concert_2", "concertmars_ecran"),
                                                 (16, "vn_concert_2", "concertmars_ecran")])
def test_the_two_best_endings_go_on_with_their_concert(total, scene, picture, fake_clip):
    hub = _to_the_end(total)
    assert hub.screen == "intro" and hub.scene_id == scene
    assert hub.intro_slides == [(picture, "story_" + scene.replace("vn_concert_", "vn_concert_"))]
    assert hub.intro_return == "map"


@pytest.mark.parametrize("total", (6, 8, 9, 12))
def test_the_two_other_endings_have_no_concert(total, fake_clip):
    hub = _to_the_end(total)
    assert hub.screen == "hub" and hub.pane == "map"
    assert not _Clip.made


def test_the_concerts_of_the_endings():
    assert ss.VN_CONCERTS == {"romance": "vn_concert_1", "amitie": "vn_concert_2"}
    assert ss.concert_of_ending("fachery") is None and ss.concert_of_ending("distance") is None
    for scene, video in (("vn_concert_1", "concertmars"), ("vn_concert_2", "concertmars_ecran")):
        spec = ss.film_bg(scene)
        assert spec is not None and spec["video"] == video and spec["still"] == 2.0
        assert spec["files"] == (asset_path("video", video + ".mp4"), asset_path("video", video + ".ogg"))
        assert os.path.isfile(asset_path("story", video + ".jpg"))
    assert ss.film_bg("ch1_sortie") is None               # (an ordinary scene: its picture, or its looping clip)


def test_closing_the_concert_goes_back_where_the_visual_novel_was(fake_clip):
    hub = _to_the_end(17)
    hub.intro_t = 99.0
    hub.confirm()
    assert hub.screen == "hub" and hub.pane == "map"


# ------------------------------------------------------------------ the picture, the film once, the picture again
def test_the_picture_shows_alone_for_two_seconds_then_the_film_plays_once_with_its_sound(fake_clip):
    heard, stopped = fake_clip
    hub = _to_the_end(17)
    still = hub._intro_backdrop("concertmars")
    hub.intro_t = 1.9
    assert hub._intro_backdrop("concertmars") is still and not _Clip.made       # the picture alone
    hub.intro_t = 2.0
    frame = hub._intro_backdrop("concertmars")
    assert len(_Clip.made) == 1
    clip = _Clip.made[0]
    assert frame is clip.surface and frame is not still
    assert clip.loop is False and clip.hard_clock and clip.fit == "cover"
    assert clip.path == asset_path("video", "concertmars.mp4") and clip.size == (BASE_WIDTH, BASE_HEIGHT)
    assert heard == [asset_path("video", "concertmars.ogg")]                     # the sound with the first picture
    assert hub.film_playing()                                                    # (the game leaves the music to it)
    for _ in range(10):
        last = hub._intro_backdrop("concertmars")
    assert last is still and clip.closed                                         # the film is over: the picture again
    hub.intro_t = 50.0
    assert hub._intro_backdrop("concertmars") is still and len(_Clip.made) == 1  # it does not play again
    assert heard == [asset_path("video", "concertmars.ogg")] and not stopped    # (the song ended with it)


def test_the_text_goes_by_over_the_film(fake_clip):
    hub = _to_the_end(13)
    font = pygame.font.Font(None, 30)
    hub.intro_t = 3.0
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    hub._draw_intro(surf, font, font)
    assert _Clip.made and hub.intro_slides[0][1] == "story_vn_concert_2"
    for _ in range(200):
        hub.update(0.1)
    assert hub.intro_pos > 0                                                     # it rises as in every scene


def test_skipping_the_concert_stops_the_film_and_its_song(fake_clip):
    heard, stopped = fake_clip
    hub = _to_the_end(20)
    hub.intro_t = 2.5
    hub._intro_backdrop("concertmars")
    clip = _Clip.made[0]
    hub.back()                                                                   # B / Esc
    assert hub.screen == "hub" and clip.closed and stopped
    assert not hub.film_playing()                                                # the music of the menus comes back


def test_without_its_files_the_concert_is_the_picture_alone(fake_clip, monkeypatch):
    monkeypatch.setattr(ss, "film_bg", lambda scene_id: None)
    hub = _to_the_end(17)
    assert hub.screen == "intro" and hub.scene_id == "vn_concert_1"
    hub.intro_t = 10.0
    assert hub._intro_backdrop("concertmars") is not None and not _Clip.made
    assert not hub.film_playing()


def test_a_film_that_cannot_play_leaves_the_picture(fake_clip, monkeypatch):
    class _Broken(_Clip):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.failed = True
    monkeypatch.setattr(videoclip, "ClipPlayer", _Broken)
    hub = _to_the_end(17)
    still = hub._intro_backdrop("concertmars")
    hub.intro_t = 3.0
    assert hub._intro_backdrop("concertmars") is still
    hub.intro_t = 4.0
    assert hub._intro_backdrop("concertmars") is still and len(_Clip.made) == 1  # (not tried again at each frame)


def test_watched_again_with_the_ending_from_the_journal(fake_clip):
    hub = _hub(TOTALS[13], told=True)
    hub.state["credits"] = 10
    assert hub.start_vn("vn_5", back_to="log")
    _skip_pages(hub)
    assert hub.screen == "intro" and hub.scene_id == "vn_concert_2" and hub.state["credits"] == 10


# ------------------------------------------------------------------ the texts
@pytest.mark.parametrize("lang", ("fr", "en"))
def test_the_texts_of_the_concerts(lang):
    before = i18n.get_lang()
    i18n.set_lang(lang)
    try:
        one = "\n".join(ss.intro_lines(i18n.t, "story_vn_concert_1", "NOVA"))
        two = "\n".join(ss.intro_lines(i18n.t, "story_vn_concert_2", "NOVA"))
        assert "NOVA" in one and "{name}" not in one                             # the pilot's name in the romance
        assert "NOVA" not in two
        assert "When We Looked Up" in one and "When We Looked Up" in two
        assert i18n.t("story_vn_concert_t") != "story_vn_concert_t"
    finally:
        i18n.set_lang(before)


def test_the_french_texts_are_kraran_s(monkeypatch):
    before = i18n.get_lang()
    i18n.set_lang("fr")
    try:
        one = i18n.t("story_vn_concert_1")
        two = i18n.t("story_vn_concert_2")
        assert one.startswith("Le soir du concert, Eloncity tout entière semblait retenir son souffle.")
        assert "Celui qui veille sur Phobos... et sur moi. {name}, celle-ci est pour toi. »" in one
        assert "Les pilotes, les mécanos, tous ceux qui tiennent la ligne là-haut" in two
        for text in (one, two):
            assert text.endswith("plus personne à Eloncity n'a regardé le ciel avec peur.")
            assert text.count("\n\n") == 4                                       # five paragraphs
    finally:
        i18n.set_lang(before)


# ------------------------------------------------------------------ the real files
@pytest.mark.skipif(videoclip.find_ffmpeg() is None, reason="no ffmpeg")
def test_the_film_of_the_concert_really_plays():
    import time
    path = asset_path("video", "concertmars.mp4")
    clip = videoclip.ClipPlayer(path, (BASE_WIDTH, BASE_HEIGHT), None, loop=False, fit="cover", hard_clock=True)
    try:
        end = time.time() + 15
        while time.time() < end and clip.surface is None and not clip.failed:
            clip.pump()
            time.sleep(0.02)
        assert not clip.failed and clip.surface is not None
        assert clip.surface.get_size() == (BASE_WIDTH, BASE_HEIGHT)
    finally:
        clip.close()
