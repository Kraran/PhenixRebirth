"""The four slides of the Adventure intro (Huygens, its destruction, Phobos, Kamarasov) and the Veteran's last one
(Kamarasov's death) are video clips (assets/story/<name>.mp4, made by tools/encode_clip.py) instead of stills."""
import os
import re
import subprocess
import time

import pygame
import pytest

import story_state as ss
import videoclip
from settings import asset_path
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)
from test_story_clip import FFMPEG, FakePlayer, fake, needs_ffmpeg  # noqa: F401  (fixture)

# picture -> frames of the clip (the video given, at 24 images a second, minus the 12 of the dissolve of the loop)
FRAMES = {"huygens": 145 - 12, "huygens_destroyed": 145 - 12, "phobos": 241 - 12, "kamarasov": 145 - 12,
          "kamarasov_veteran": 145 - 12}


def _hub(mode):
    st = ss.create_slot(1, "NOVA", mode)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.start_intro()
    assert hub.screen == "intro" and hub.state.get("mode") == mode
    return hub


def test_every_slide_of_the_intro_is_a_video_with_its_still_as_the_poster():
    for mode in ("normal", "veteran"):
        slides = ss.intro_slides(mode)
        assert len(slides) == 4
        for picture, _ in slides:
            assert ss.clip_path(picture) == asset_path("story", picture + ".mp4"), (mode, picture)
            assert os.path.isfile(ss.clip_path(picture))
            assert os.path.exists(asset_path("story", picture + ".jpg")), picture


def test_the_two_modes_have_their_own_last_video():
    normal, veteran = ss.intro_slides("normal"), ss.intro_slides("veteran")
    assert [p for p, _ in normal] == ["huygens", "huygens_destroyed", "phobos", "kamarasov"]
    assert [p for p, _ in veteran] == ["huygens", "huygens_destroyed", "phobos", "kamarasov_veteran"]
    assert os.path.getsize(ss.clip_path("kamarasov")) != os.path.getsize(ss.clip_path("kamarasov_veteran"))


@pytest.mark.parametrize("mode", ["normal", "veteran"])
def test_each_slide_plays_its_own_video_and_stops_the_one_before(run, fake, mode):
    hub = _hub(mode)
    players = []
    for index, (picture, _) in enumerate(hub.intro_slides):
        assert hub.intro_index == index
        hub._intro_backdrop(picture)
        assert fake.made[-1].path == ss.clip_path(picture)
        assert not fake.made[-1].closed
        if players:
            assert players[-1].closed and fake.made[-1] is not players[-1]
        players.append(fake.made[-1])
        hub.intro_t = 60.0
        hub.confirm()
    assert hub.screen == "hub" and players[-1].closed and hub._clip is None
    assert len(players) == 4 and len({p.path for p in players}) == 4


@pytest.mark.parametrize("mode", ["normal", "veteran"])
def test_the_intro_draws_the_video_of_its_slide(run, fake, mode):
    hub = _hub(mode)
    g = run.game
    surf = pygame.Surface((1280, 720))
    for _ in range(3):
        hub.update(1 / 60)
        hub.draw(surf, g.font, g.medium_font, g.font)
    assert len(fake.made) == 1 and fake.made[0].path == ss.clip_path(hub.intro_slides[0][0])
    fake.made[0].ready = True
    hub.draw(surf, g.font, g.medium_font, g.font)
    hub.draw(surf, g.font, g.medium_font, g.font)
    assert fake.made[0].surface is not None and fake.made[0].pumps >= 3


@needs_ffmpeg
def test_the_five_clips_are_the_videos_given_without_sound():
    for picture, frames in FRAMES.items():
        path = ss.clip_path(picture)
        out = subprocess.run([FFMPEG, "-hide_banner", "-i", path, "-f", "null", "-"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stderr
        assert "752x416" in out and "Audio:" not in out and "Video: h264" in out, picture
        assert int(re.findall(r"frame=\s*(\d+)", out)[-1]) == frames, picture
        assert os.path.getsize(path) < 1024 * 1024, picture                              # a few hundred kilobytes each
        info = videoclip.mp4_info(path)
        assert info and (info["width"], info["height"]) == (752, 416), picture


@needs_ffmpeg
@pytest.mark.parametrize("mode", ["normal", "veteran"])
def test_the_real_videos_play_through_the_intro(run, mode):
    hub = _hub(mode)
    g = run.game
    surf = pygame.Surface((1280, 720))
    for picture, _ in hub.intro_slides:
        end = time.time() + 8
        while time.time() < end and not (hub._clip is not None and hub._clip.playing):
            hub.update(1 / 60)
            hub.draw(surf, g.font, g.medium_font, g.font)
            time.sleep(0.01)
        assert hub._clip is not None and hub._clip.playing, picture
        assert hub._intro_backdrop(picture) is hub._clip.surface
        proc = hub._clip._proc
        hub.intro_t = 60.0
        hub.confirm()
        end = time.time() + 3
        while proc.poll() is None and time.time() < end:
            time.sleep(0.05)
        assert proc.poll() is not None, picture                                         # no ffmpeg left running
    assert hub.screen == "hub" and hub._clip is None
