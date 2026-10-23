"""The films of the Adventure (story_state.FILMS): a video with its sound, full screen. Lyra Voss's private concert,
three songs in a row (1. Eternal Dawn, 2. What We Lost, 3. No Mercy Left), comes right after the scene of the VIP
rescue, then the journal keeps each song. The film of the Phobos bar (the visual novel) follows the third song."""
import pygame
import pytest

import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

FILM = "lyra_1"
SONGS = ["lyra_1", "lyra_2", "lyra_3"]
TITLES = ["Concert privé Lyra Voss - 1. Eternal Dawn", "Concert privé Lyra Voss - 2. What We Lost",
          "Concert privé Lyra Voss - 3. No Mercy Left"]


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


def _answer_vn(hub):
    """The scene of the visual novel that ends the concert: A through the pages of the text, the answer under the cursor,
    then what Lyra says to it."""
    assert hub.screen == "vn"
    for _ in range(40):
        if hub.screen != "vn":
            break
        hub.confirm()
    assert hub.screen == "hub"


def _skip_concert(hub):
    """B on each song, as long as one is playing. The songs seen, in order."""
    seen = []
    while hub.screen == "film" and len(seen) < 10:
        seen.append(hub.film_id)
        hub.back()
    return seen


# ------------------------------------------------------------------ the film and its files
def test_the_concert_is_three_films_after_the_scene_of_the_vip_rescue(french):
    from i18n import t
    assert ss.film_after(ss.VIP_SCENE) == FILM and ss.film_chain(ss.VIP_SCENE) == SONGS + ["vn_1"]
    videos = ["lyra_1_eternal_dawn", "lyra_2_what_we_lost", "lyra_3_no_mercy_left"]
    for fid, video, title in zip(SONGS, videos, TITLES):
        film = ss.FILMS[fid]
        assert film["video"] == video and t(film["title"]) == title
        mp4, sound = ss.film_files(fid)
        assert mp4.endswith(video + ".mp4") and sound.endswith(video + ".ogg")
    assert ss.film_after("lyra_3") == "vn_1" and ss.film_after("vn_1") is None      # the last song, then the bar


@pytest.mark.parametrize("fid,minutes", [("lyra_1", (5.0, 5.3)), ("lyra_2", (4.7, 4.9)), ("lyra_3", (3.7, 3.9))])
def test_the_videos_are_silent_and_the_sound_is_apart(fid, minutes):
    import subprocess
    import videoclip
    exe = videoclip.find_ffmpeg()
    if not exe:
        return
    video, _sound = ss.film_files(fid)
    info = subprocess.run([exe, "-hide_banner", "-i", video], capture_output=True, text=True).stderr
    assert "Audio:" not in info and "1280x720" in info and " 24 fps" in info
    meta = videoclip.mp4_info(video)
    assert minutes[0] * 60 < meta["duration"] < minutes[1] * 60


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
    assert clip.closed and ss.film_seen(hub.state, FILM)
    assert ss.film_seen(ss.load_state(ss.story_path(1)), FILM)             # saved
    assert hub.screen == "film" and hub.film_id == "lyra_2"                # B skips one song: the next one comes
    assert _skip_concert(hub) == ["lyra_2", "lyra_3", "vn_1"]
    assert hub.screen == "vn" and not hub.film_playing()                   # the scene of the bar comes after the songs
    assert all(ss.film_seen(hub.state, fid) for fid in SONGS + ["vn_1"])
    _answer_vn(hub)
    assert hub.pane == "map"


def test_the_three_songs_follow_each_other(fake_clip):
    hub = _hub()
    _scene_then_end(hub)
    played = []
    for _ in range(5):
        if hub.screen != "film":
            break
        played.append(hub.film_id)
        hub._film.ended = True                                             # the end of the song
        hub.update(1 / 60)
    assert played == SONGS + ["vn_1"] and hub.screen == "vn" and hub.vn_return == "map"


def test_it_ends_by_itself_at_the_end_of_the_video(fake_clip):
    hub = _hub()
    _scene_then_end(hub)
    hub._film.ended = True
    hub.update(1 / 60)
    assert ss.film_seen(hub.state, FILM) and hub.film_id == "lyra_2"


def test_the_scene_watched_again_does_not_bring_the_film_back(fake_clip):
    hub = _hub()
    _scene_then_end(hub)
    _skip_concert(hub)
    _scene_then_end(hub)
    assert hub.screen == "hub"


def test_without_its_files_there_is_no_film_but_it_counts_as_seen(monkeypatch):
    monkeypatch.setattr(ss, "film_files", lambda film_id: None)
    hub = _hub()
    _scene_then_end(hub)
    assert hub.screen == "hub" and ss.film_seen(hub.state, FILM)


def test_a_song_whose_files_are_missing_is_passed_over(fake_clip, monkeypatch):
    real = ss.film_files
    monkeypatch.setattr(ss, "film_files", lambda fid: None if fid == "lyra_2" else real(fid))
    hub = _hub()
    _scene_then_end(hub)
    assert _skip_concert(hub) == ["lyra_1"]
    assert ss.film_seen(hub.state, "lyra_2")


# ------------------------------------------------------------------ the journal
def test_the_journal_keeps_each_song_right_after_the_scene(fake_clip, french):
    hub = _hub()
    _scene_then_end(hub)
    _skip_concert(hub)
    _answer_vn(hub)
    entries = hub.replay_entries()
    i = entries.index({"scene": ss.VIP_SCENE})
    assert entries[i + 1:i + 4] == [{"film": fid} for fid in SONGS]
    assert entries[i + 4] == {"film": "vn_1"}
    from i18n import t
    assert [ss.log_text({"film": fid}, t) for fid in SONGS] == ["Revoir : " + title for title in TITLES]
    hub.pane = "log"
    hub.log_cursor = i + 2                                                 # the second song alone
    assert hub.confirm() is None
    assert hub.screen == "film" and hub.film_id == "lyra_2" and hub.film_return == "log"
    hub._film.ended = True
    hub.update(1 / 60)
    assert hub.screen == "hub" and hub.pane == "log"                      # (not the third one after it)


def test_the_journal_lists_only_the_songs_heard():
    hub = _hub()
    ss.mark_scene_seen(hub.state, ss.VIP_SCENE)
    ss.mark_film_seen(hub.state, "lyra_1")
    entries = hub.replay_entries()
    assert {"film": "lyra_1"} in entries and {"film": "lyra_2"} not in entries


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
    for song in SONGS + ["vn_1"]:
        assert g.story.film_id == song
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="", mod=0, scancode=0))
        run.frames(3)
    assert g.story.screen == "vn" and g.menu_screen == "story_hub"
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
