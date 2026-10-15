"""The films of the Adventure (story_state.FILMS): a video with its sound, full screen. The first one, Lyra Voss's
private concert (1. Eternal Dawn), comes right after the scene of the VIP rescue, then the journal keeps it."""
import pygame
import pytest

import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

FILM = "lyra_1"


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


@pytest.fixture
def french():
    from i18n import get_lang, set_lang
    before = get_lang()
    set_lang("fr")
    yield
    set_lang(before)


class _Clip:
    """A stand-in for videoclip.ClipPlayer: ready at once, `ended` when the test says so."""

    def __init__(self, *a, **k):
        self.failed = False
        self.ended = False
        self.ready = True
        self.surface = pygame.Surface((64, 36))
        self.closed = False

    def pump(self, now=None):
        return True

    def close(self):
        self.closed = True


@pytest.fixture
def fake_clip(monkeypatch):
    import videoclip
    monkeypatch.setattr(videoclip, "ClipPlayer", _Clip)
    return _Clip


def _hub():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.screen, hub.pane = "hub", "map"
    return hub


def _scene_then_end(hub):
    hub.start_scene(ss.VIP_SCENE, back_to="map")
    hub.back()                                   # (skipped or read to the end: the same way out)


# ------------------------------------------------------------------ the film and its files
def test_the_concert_is_a_film_after_the_scene_of_the_vip_rescue(french):
    from i18n import t
    film = ss.FILMS[FILM]
    assert ss.film_after(ss.VIP_SCENE) == FILM and film["video"] == "lyra_1_eternal_dawn"
    assert t(film["title"]) == "Concert privé Lyra Voss - 1. Eternal Dawn"
    video, sound = ss.film_files(FILM)
    assert video.endswith("lyra_1_eternal_dawn.mp4") and sound.endswith("lyra_1_eternal_dawn.ogg")


def test_the_video_is_silent_and_the_sound_is_apart():
    import subprocess
    import videoclip
    exe = videoclip.find_ffmpeg()
    if not exe:
        return
    video, _sound = ss.film_files(FILM)
    info = subprocess.run([exe, "-hide_banner", "-i", video], capture_output=True, text=True).stderr
    assert "Audio:" not in info and "1280x720" in info and " 24 fps" in info
    meta = videoclip.mp4_info(video)
    assert 300 < meta["duration"] < 320                                     # about five minutes


# ------------------------------------------------------------------ after the scene
def test_it_starts_when_the_scene_is_over_and_b_skips_it(fake_clip):
    hub = _hub()
    _scene_then_end(hub)
    assert hub.screen == "film" and hub.film_id == FILM and hub.film_playing()
    hub.update(1 / 60)
    assert hub.film_t > 0
    assert hub.confirm() is None and hub.screen == "film"                  # A does nothing: no skip by accident
    clip = hub._film
    assert hub.back()
    assert hub.screen == "hub" and hub.pane == "map" and clip.closed and not hub.film_playing()
    assert ss.film_seen(hub.state, FILM)
    assert ss.film_seen(ss.load_state(ss.story_path(1)), FILM)             # saved


def test_it_ends_by_itself_at_the_end_of_the_video(fake_clip):
    hub = _hub()
    _scene_then_end(hub)
    hub._film.ended = True
    hub.update(1 / 60)
    assert hub.screen == "hub" and ss.film_seen(hub.state, FILM)


def test_the_scene_watched_again_does_not_bring_the_film_back(fake_clip):
    hub = _hub()
    _scene_then_end(hub)
    hub.back()
    _scene_then_end(hub)
    assert hub.screen == "hub"


def test_without_its_files_there_is_no_film_but_it_counts_as_seen(monkeypatch):
    monkeypatch.setattr(ss, "film_files", lambda film_id: None)
    hub = _hub()
    _scene_then_end(hub)
    assert hub.screen == "hub" and ss.film_seen(hub.state, FILM)


# ------------------------------------------------------------------ the journal
def test_the_journal_keeps_it_right_after_its_scene(fake_clip, french):
    hub = _hub()
    _scene_then_end(hub)
    hub.back()
    entries = hub.replay_entries()
    i = entries.index({"scene": ss.VIP_SCENE})
    assert entries[i + 1] == {"film": FILM}
    assert ss.log_text({"film": FILM}, __import__("i18n").t) == "Revoir : Concert privé Lyra Voss - 1. Eternal Dawn"
    hub.pane = "log"
    hub.log_cursor = i + 1
    assert hub.confirm() is None
    assert hub.screen == "film" and hub.film_return == "log"
    hub.back()
    assert hub.screen == "hub" and hub.pane == "log"


def test_not_in_the_journal_before_it_is_seen():
    hub = _hub()
    ss.mark_scene_seen(hub.state, ss.VIP_SCENE)
    assert {"film": FILM} not in hub.replay_entries()


# ------------------------------------------------------------------ in the game
def _film_in_game(run):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    ss.save_state(ss.story_path(1), st)
    g.menu_screen = "story_hub"
    g.story.open_slot(1)
    g.story.screen, g.story.pane = "hub", "map"
    g.input_grace = 0
    _scene_then_end(g.story)
    run.frames(3)
    return g


def test_the_game_leaves_the_music_to_the_film_then_the_menu_theme_comes_back(run, fake_clip):
    g = _film_in_game(run)
    assert g.story.screen == "film" and g.sounds.current_music_key() == "film"
    run.frames(10)
    assert g.sounds.current_music_key() == "film"                         # the menu theme did not come back over it
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="", mod=0, scancode=0))
    run.frames(3)
    assert g.story.screen == "hub" and g.menu_screen == "story_hub"
    assert g.sounds.current_music_key() == "menu"


def test_the_screen_is_the_video_and_nothing_over_it_but_the_title_for_a_moment(run, fake_clip):
    g = _film_in_game(run)
    hub = g.story
    assert hub.covers_screen()
    assert hub.help_items()[0] == [("back", "hint_skip")]
    hub.film_t = hub.FILM_TITLE_SEC + 1
    assert hub.help_items()[0] == []                                       # the bar would hide the words of the song
    from story_feats import _news
    _news.append(("adv_pilot", None))
    g._feat_queue = []
    run.frames(3)
    assert g._feat_queue                                                   # the banners wait for the end of the film
    _news.clear()
    run.frames(2)
