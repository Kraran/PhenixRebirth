"""A slide picture can be a looping video clip (assets/story/<name>.mp4): the first sortie scene."""
import os
import re
import subprocess
import time

import pygame
import pytest

import story
import story_state as ss
import videoclip
from settings import asset_path
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

CLIP = "oiseaux_bleus"
FFMPEG = videoclip.find_ffmpeg()
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="no ffmpeg on this machine")


class FakePlayer:
    """Stands for videoclip.ClipPlayer: no process, a solid colour once `ready` is set."""
    made = []

    def __init__(self, path, size, shade=None, *a, **k):
        self.path, self.size, self.shade = path, size, shade
        self.surface, self.failed, self.closed, self.pumps, self.ready = None, False, False, 0, False
        FakePlayer.made.append(self)

    def pump(self, now=None):
        self.pumps += 1
        if self.ready and self.surface is None:
            self.surface = pygame.Surface(self.size)
            self.surface.fill((12, 34, 56))
        return self.ready

    @property
    def playing(self):
        return self.surface is not None and not self.failed

    def close(self):
        self.closed = True


@pytest.fixture
def fake(monkeypatch):
    FakePlayer.made = []
    monkeypatch.setattr(videoclip, "ClipPlayer", FakePlayer)
    return FakePlayer


def _hub(seen_scene=False):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    if seen_scene:
        ss.mark_scene_seen(st, "ch1_sortie")
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "map"
    hub.map_index = [m["id"] for m in hub.missions()].index("ch1_sortie")
    return hub


def _scene():
    hub = _hub()
    hub.confirm()
    assert hub.screen == "intro" and hub.scene_id == "ch1_sortie"
    return hub


# ------------------------------------------------------------------ the files
def test_the_first_sortie_picture_is_a_clip_with_a_still_poster():
    assert ss.scene_of("ch1_sortie")["slides"][0][0] == CLIP
    assert ss.clip_path(CLIP) == asset_path("story", CLIP + ".mp4") and os.path.isfile(ss.clip_path(CLIP))
    assert ss.clip_path("epave_shield") is None and ss.clip_path("no_such_picture") is None
    assert os.path.exists(asset_path("story", CLIP + ".jpg"))                         # the poster stays as the fallback
    assert not os.path.exists(asset_path("story", CLIP + "_frames"))                  # the loose frames are gone


def test_every_clip_is_small_silent_and_has_a_poster():
    clips = [n for n in os.listdir(asset_path("story")) if n.lower().endswith(".mp4")]
    assert CLIP + ".mp4" in clips
    for name in clips:
        path = asset_path("story", name)
        assert os.path.getsize(path) < 3 * 1024 * 1024                                # a few megabytes at most
        assert os.path.exists(asset_path("story", name[:-4] + ".jpg"))
        assert ss.clip_path(name[:-4]) == path


@needs_ffmpeg
def test_every_clip_is_h264_without_sound_at_the_pace_of_the_player():
    for name in os.listdir(asset_path("story")):
        if not name.lower().endswith(".mp4"):
            continue
        info = subprocess.run([FFMPEG, "-hide_banner", "-i", asset_path("story", name)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stderr
        assert "Video: h264" in info and "Audio:" not in info, name
        assert re.search(r"\b%g fps\b" % videoclip.CLIP_FPS, info), name
        w = int(re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", info).group(1))
        assert w <= 1280, name
        dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
        seconds = int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3))
        assert 5.0 <= seconds <= 12.0, name                                           # the 6 to 10 second videos


@needs_ffmpeg
def test_the_first_sortie_clip_is_the_given_video_without_sound():
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", ss.clip_path(CLIP), "-f", "null", "-"], capture_output=True,
                         text=True, encoding="utf-8", errors="replace").stderr
    assert "752x416" in out and int(re.findall(r"frame=\s*(\d+)", out)[-1]) == 241 - 12     # 10 s, minus the dissolve
    assert os.path.getsize(ss.clip_path(CLIP)) < 2 * 1024 * 1024                              # was 6.5 MB with sound


# ------------------------------------------------------------------ the picture behind the text
def test_the_still_shows_until_the_video_has_its_first_frame(run, fake):
    hub = _scene()
    still = hub._intro_backdrop(CLIP)
    assert still is hub._intro_bg[("band", CLIP)] and len(fake.made) == 1
    fake.made[0].ready = True
    moving = hub._intro_backdrop(CLIP)
    assert moving is fake.made[0].surface and moving is not still
    assert hub._intro_backdrop(CLIP) is moving                                          # the same picture frame after frame
    assert len(fake.made) == 1 and fake.made[0].pumps >= 3                              # one player, pumped every draw


def test_the_player_is_given_the_clip_the_canvas_and_the_reading_band(run, fake):
    hub = _scene()
    hub._intro_backdrop(CLIP)
    p = fake.made[0]
    assert p.path == ss.clip_path(CLIP) and p.size == (1280, 720)
    left = (1280 - (story.INTRO_TEXT_W + 120)) // 2
    assert p.shade.get_at((left - 1, 5))[:3] == (185, 185, 185)                         # the shade of the stills (70)
    assert p.shade.get_at((left, 5))[:3] == (98, 98, 98)                                # plus the dark band (120)
    assert p.shade.get_at((1280 - left, 5))[:3] == (185, 185, 185)
    assert p.shade.get_at((640, 700))[:3] == (98, 98, 98)


def test_a_failed_video_leaves_the_still_in_place(run, fake):
    hub = _scene()
    hub._intro_backdrop(CLIP)
    p = fake.made[0]
    p.ready, p.failed = True, True
    img = hub._intro_backdrop(CLIP)
    assert img is hub._intro_bg[("band", CLIP)] and len(fake.made) == 1                 # no new attempt every frame


def test_a_still_slide_never_starts_a_player(run, fake):
    hub = _hub()
    hub.cheat_unlock = True
    hub.map_index = [m["id"] for m in hub.missions()].index("dome_1")
    hub.confirm()
    assert hub.scene_id == "dome_1"
    for _ in range(5):
        hub.update(0.1)
        hub._intro_backdrop("epave_shield")
    assert fake.made == [] and hub._clip is None


def test_the_player_is_stopped_whenever_the_slide_is_left(run, fake):
    hub = _scene()
    hub._intro_backdrop(CLIP)
    p = fake.made[-1]
    assert not p.closed
    hub.intro_t = 5.0
    hub.back()                                                                         # skipping the scene
    assert p.closed and hub._clip is None and hub.screen == "hub"
    # a finished scene
    hub.pane, hub.zone = "map", "slots"
    hub.start_scene("ch1_sortie", back_to="map", launch=False)
    hub._intro_backdrop(CLIP)
    q = fake.made[-1]
    assert q is not p and not q.closed
    hub.intro_t = 60.0
    hub.confirm()
    assert q.closed and hub._clip is None


def test_leaving_the_screen_in_any_other_way_stops_the_player_too(run, fake):
    hub = _scene()
    hub._intro_backdrop(CLIP)
    p = fake.made[-1]
    hub.screen = "hub"                                                                 # whatever took the player away
    hub.update(0.016)
    assert p.closed and hub._clip is None


def test_a_replayed_scene_starts_the_video_over(run, fake):
    hub = _scene()
    hub._intro_backdrop(CLIP)
    first = fake.made[-1]
    hub.back()
    hub.start_scene("ch1_sortie", back_to="log")
    hub._intro_backdrop(CLIP)
    assert len(fake.made) == 2 and first.closed and not fake.made[-1].closed


def test_starting_a_slide_over_restarts_its_video(run, fake):
    hub = _scene()
    hub._intro_backdrop(CLIP)
    p = fake.made[-1]
    hub._reset_slide()
    assert p.closed and hub._clip is None
    hub._intro_backdrop(CLIP)
    assert len(fake.made) == 2


# ------------------------------------------------------------------ the whole scene
def test_the_scene_draws_over_the_clip_and_the_text_still_scrolls(run, fake):
    hub = _scene()
    g = run.game
    surf = pygame.Surface((1280, 720))
    tops = []
    for i in range(300):                                                                # five seconds
        if i == 20:
            fake.made[0].ready = True
        hub.update(1 / 60)
        hub.draw(surf, g.font, g.medium_font, g.font)
        tops.append(hub.intro_pos)
    assert tops[-1] > tops[60] > 0 and hub.covers_screen()
    assert surf.get_at((5, 5))[:3] == (12, 34, 56)                                      # the video is behind the text


def test_the_replay_from_the_journal_plays_the_clip_too(run, fake):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.mark_scene_seen(st, "ch1_sortie")
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "log"
    hub.nav_v(1)
    hub.confirm()
    assert hub.screen == "intro" and hub.scene_id == "ch1_sortie" and not hub.scene_launch
    hub._intro_backdrop(CLIP)
    assert len(fake.made) == 1 and fake.made[0].path == ss.clip_path(CLIP)


@needs_ffmpeg
def test_the_real_video_plays_behind_the_scene(run):
    hub = _scene()
    g = run.game
    surf = pygame.Surface((1280, 720))
    end = time.time() + 8
    while time.time() < end and not (hub._clip is not None and hub._clip.playing):
        hub.update(1 / 60)
        hub.draw(surf, g.font, g.medium_font, g.font)
        time.sleep(0.01)
    assert hub._clip is not None and hub._clip.playing
    assert hub._intro_backdrop(CLIP) is hub._clip.surface
    seen = set()
    for _ in range(40):                                                                 # about a second: the picture moves
        hub.update(1 / 60)
        hub.draw(surf, g.font, g.medium_font, g.font)
        seen.add(tuple(surf.get_at((x, y))[:3] for x in range(0, 1280, 160) for y in range(0, 100, 20)))
        time.sleep(1 / 40)
    assert len(seen) >= 8
    assert len({tuple(surf.get_at((x, y)))[:3] for x in range(0, 1280, 40) for y in range(0, 720, 40)}) > 40   # not a blank screen
    proc = hub._clip._proc
    hub.back()
    assert hub._clip is None
    end = time.time() + 3
    while proc.poll() is None and time.time() < end:
        time.sleep(0.05)
    assert proc.poll() is not None                                                      # no ffmpeg left running
