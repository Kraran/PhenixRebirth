"""A slide picture can be a looping video clip (frames in assets/story/<name>_frames): the first sortie scene."""
import os

import pygame
import pytest

import story
import story_state as ss
from settings import asset_path
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

CLIP = "oiseaux_bleus"


def _hub():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "map"
    hub.map_index = [m["id"] for m in hub.missions()].index("ch1_sortie")
    hub.confirm()
    assert hub.screen == "intro" and hub.scene_id == "ch1_sortie"
    return hub


def _digest(surf):
    return tuple(tuple(surf.get_at((x, y)))[:3] for x in range(0, 1280, 64) for y in range(0, 720, 48))


# ------------------------------------------------------------------ which frame, when
def test_the_clip_plays_its_frames_in_order_then_loops_without_a_jump():
    n, fps, f = 241, 24.0, ss.CLIP_FADE_FRAMES
    seq = [ss.clip_frame_at(q / fps, n, fps, f) for q in range(0, 24 * 60)]
    assert [s[0] for s in seq[:f + 3]] == list(range(f + 3)) and all(s[1] is None for s in seq[:f + 3])
    mains = [s for s in seq if s[1] is None]
    assert all(0 <= s[0] < n for s in seq)
    # outside the dissolve the clip only moves forward by one frame, and a later pass resumes right after the
    # frames the dissolve already showed
    dissolves = [i for i, s in enumerate(seq) if s[1] is not None]
    assert dissolves and len(dissolves) % f == 0
    first = dissolves[0]
    assert [seq[first + k][1] for k in range(f)] == list(range(f))                  # the beginning melts in
    assert [seq[first + k][0] for k in range(f)] == list(range(n - f, n))           # the end melts out
    assert seq[first + f][0] == f and seq[first + f][1] is None                      # then frame 12, not 0
    weights = [seq[first + k][2] for k in range(f)]
    assert weights == sorted(weights) and 0 < weights[0] < weights[-1] < 1
    assert all(m[2] == 0.0 for m in mains)


def test_every_pass_after_the_first_lasts_the_same_time():
    n, fps, f = 241, 24.0, ss.CLIP_FADE_FRAMES
    starts = [i for i in range(24 * 120) if ss.clip_frame_at(i / fps, n, fps, f)[1] == 0]
    assert len(starts) >= 4 and {b - a for a, b in zip(starts, starts[1:])} == {n - f}


def test_odd_clips_never_crash_the_frame_picker():
    assert ss.clip_frame_at(5.0, 0, 24.0) == (0, None, 0.0)
    assert ss.clip_frame_at(-3.0, 10, 24.0)[0] == 0
    for count in (1, 2, 5, 12, 30):
        for q in range(0, 400):
            a, b, w = ss.clip_frame_at(q / 24.0, count, 24.0)
            assert 0 <= a < count and (b is None or 0 <= b < count) and 0.0 <= w <= 1.0
    assert ss.clip_frame_at(7.0, 100, 24.0, fade=0)[1] is None


# ------------------------------------------------------------------ the files
def test_the_first_sortie_picture_is_a_clip_with_its_frames_and_a_still():
    assert ss.scene_of("ch1_sortie")["slides"][0][0] == CLIP and ss.clip_of(CLIP) and not ss.clip_of("epave_shield")
    folder = asset_path("story", CLIP + "_frames")
    frames = sorted(os.listdir(folder))
    assert len(frames) == 241 and frames[0] == "0001.jpg" and frames[-1] == "0241.jpg"
    assert abs(len(frames) / ss.clip_of(CLIP)["fps"] - 10.04) < 0.1                 # the 10 second video
    assert os.path.exists(asset_path("story", CLIP + ".jpg"))                        # the still stays as the fallback
    assert pygame.image.load(os.path.join(folder, frames[0])).get_size() == (752, 416)


def test_every_clip_has_frames_of_one_size():
    for name, info in ss.CLIPS.items():
        folder = asset_path("story", name + "_frames")
        frames = sorted(os.listdir(folder))
        assert len(frames) > 2 * ss.CLIP_FADE_FRAMES and info["fps"] > 0
        assert len({pygame.image.load(os.path.join(folder, f)).get_size() for f in frames[::20]}) == 1


# ------------------------------------------------------------------ the picture behind the text
def test_the_background_moves_with_the_time(run):
    hub = _hub()
    surf = pygame.Surface((1280, 720))
    seen = set()
    for _ in range(8):
        hub.intro_t += 1.0
        seen.add(_digest(hub._intro_backdrop(CLIP)))
    assert len(seen) >= 6                                                              # a different picture every second


def test_the_background_is_rebuilt_only_when_the_frame_changes(run, monkeypatch):
    hub = _hub()
    loads = []
    real = hub._clip_scaled
    monkeypatch.setattr(hub, "_clip_scaled", lambda path, dest: (loads.append(path), real(path, dest))[1])
    hub.intro_t = 2.0
    first = hub._intro_backdrop(CLIP)
    assert len(loads) == 1
    for extra in (0.0, 0.2, 0.4):                                                       # still the same frame
        hub.intro_t = 2.0 + extra / 24.0
        assert hub._intro_backdrop(CLIP) is first
    assert len(loads) == 1
    hub.intro_t = 2.0 + 1.5 / 24.0
    hub._intro_backdrop(CLIP)
    assert len(loads) == 2


def test_the_reading_band_and_the_shade_are_one_overlay(run):
    hub = _hub()
    hub._intro_backdrop(CLIP)
    ov = hub._clip_overlay
    assert ov.get_at((5, 5)).a == 70                                                   # the shade of the stills
    both = ov.get_at((640, 5)).a
    assert both == round(255 * (1 - (1 - 70 / 255) * (1 - 120 / 255))) == 157           # shade, then the dark band
    left = (1280 - (story.INTRO_TEXT_W + 120)) // 2
    assert ov.get_at((left - 1, 5)).a == 70 and ov.get_at((left, 5)).a == both


def test_the_dissolve_blends_two_frames(run, monkeypatch):
    hub = _hub()
    n = len(hub._clip_files(CLIP))
    colours = {}

    def fake(path, dest):
        dest.fill(colours.setdefault(path, (200, 0, 0) if not colours else (0, 0, 200)))

    monkeypatch.setattr(hub, "_clip_scaled", fake)
    hub.intro_t = (n - 12 + 5) / 24.0                                                  # inside the dissolve
    a, b, w = ss.clip_frame_at(hub.intro_t, n, 24.0)
    assert b is not None and 0 < w < 1
    pix = hub._intro_backdrop(CLIP).get_at((5, 5))                                     # outside the reading band
    dark = 1 - 70 / 255.0
    assert abs(pix.r - 200 * (1 - w) * dark) <= 3 and abs(pix.b - 200 * w * dark) <= 3 and pix.g == 0
    hub.intro_t = 40.0                                                                  # a plain frame: one colour only
    assert ss.clip_frame_at(hub.intro_t, n, 24.0)[1] is None
    pix = hub._intro_backdrop(CLIP).get_at((5, 5))
    assert (pix.r > 0) != (pix.b > 0)


def test_the_other_scenes_keep_their_still_picture(run):
    hub = _hub()
    moving = hub._intro_backdrop(CLIP)
    still = hub._intro_backdrop("epave_shield")
    assert still is not moving and hub._intro_backdrop("epave_shield") is still
    assert ("band", "epave_shield") in hub._intro_bg and ("band", CLIP) not in hub._intro_bg


def test_without_its_frames_the_still_takes_over(run, monkeypatch):
    hub = _hub()
    monkeypatch.setattr(hub, "_clip_files", lambda name: [])
    img = hub._intro_backdrop(CLIP)
    assert img is hub._intro_bg[("band", CLIP)] and img.get_size() == (1280, 720)


def test_a_broken_frame_gives_up_on_the_clip_and_shows_the_still(run, tmp_path, monkeypatch):
    hub = _hub()
    bad = tmp_path / "0001.jpg"
    bad.write_bytes(b"not a picture")
    hub._clip_lists[CLIP] = [str(bad)] * 30
    img = hub._intro_backdrop(CLIP)
    assert img is hub._intro_bg[("band", CLIP)]
    assert hub._clip_lists[CLIP] == []                                                 # it does not retry every frame
    assert hub._intro_backdrop(CLIP) is img


# ------------------------------------------------------------------ the whole scene
def test_the_scene_draws_over_the_clip_and_the_text_still_scrolls(run):
    hub = _hub()
    g = run.game
    surf = pygame.Surface((1280, 720))
    tops = []
    for _ in range(300):                                                                # five seconds
        hub.update(1 / 60)
        hub.draw(surf, g.font, g.medium_font, g.font)
        tops.append(hub.intro_pos)
    assert tops[-1] > tops[60] > 0 and hub.covers_screen()
    assert len({tuple(surf.get_at((x, y)))[:3] for x in range(0, 1280, 40) for y in range(0, 720, 40)}) > 40


def test_the_replay_from_the_journal_plays_the_clip_too(run):
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
    hub.intro_t = 3.0
    assert hub._intro_backdrop(CLIP) is hub._clip_cur[1]
