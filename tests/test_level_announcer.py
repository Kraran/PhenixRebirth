"""The announcer says the stage at the start of every level, from 1 to 31 (assets/sounds/level<n>.wav, played like every
other level callout on the announcer channel). Level 31 is "To boldly go where no one has gone before" (it used to be
level 21); past 31 the announcer stays silent."""
import os

import pygame
import pytest

import game as game_mod
from settings import asset_path
from sounds import SoundManager
from test_smoke import run  # noqa: F401  (fixture)

LAST = 31


class _Voice:
    def __init__(self, real):
        self._real = real
        self.vo = []

    def play_vo(self, name, *a, **k):
        self.vo.append((name, k.get("volume")))

    def __getattr__(self, name):
        return getattr(self._real, name)


def _length(n):
    return pygame.mixer.Sound(asset_path("sounds", "level%d.wav" % n)).get_length()


def test_the_last_announced_level_is_31():
    assert game_mod.LAST_ANNOUNCED_LEVEL == LAST


@pytest.mark.parametrize("n", range(1, LAST + 1))
def test_every_level_from_1_to_31_has_its_recording(n):
    assert os.path.isfile(asset_path("sounds", "level%d.wav" % n))


def test_there_is_no_recording_past_level_31():
    assert not os.path.exists(asset_path("sounds", "level%d.wav" % (LAST + 1)))


def test_every_recording_is_loaded_by_the_sound_manager_at_the_level_volume(run):
    s = run.game.sounds
    for n in range(1, LAST + 1):
        assert "level%d" % n in s.sounds, n
        assert s._base_volumes["level%d" % n] == 0.88, n


@pytest.mark.parametrize("n", range(21, 32))
def test_the_new_recordings_are_wavs_like_the_others(n):
    """Same format as level1..20: 16-bit PCM, 44.1 kHz, stereo; one to five seconds."""
    import wave
    with wave.open(asset_path("sounds", "level%d.wav" % n)) as w:
        assert (w.getsampwidth(), w.getframerate(), w.getnchannels()) == (2, 44100, 2)
        assert 1.0 < w.getnframes() / w.getframerate() < 5.0


def test_level_31_is_the_old_boldly_go_and_level_21_is_a_short_callout(run):
    """The long "To boldly go where no one has gone before" (3.08 s) moved from level 21 to level 31."""
    assert abs(_length(31) - 3.077) < 0.01
    assert _length(21) < 2.2
    assert _length(25) > 3.5 and _length(30) > 3.5               # the two "Warning" callouts are the longest


@pytest.mark.parametrize("n", [1, 7, 20, 21, 22, 25, 30, 31])
def test_the_arcade_announces_the_stage(run, n):
    g = run.game
    real = g.sounds
    g.sounds = _Voice(real)
    try:
        g._play_level_vo(n)
        assert g.sounds.vo == [("level%d" % n, 0.88)]
    finally:
        g.sounds = real


@pytest.mark.parametrize("n", [0, -3, 32, 33, 99])
def test_beyond_the_recordings_the_announcer_is_silent(run, n):
    g = run.game
    real = g.sounds
    g.sounds = _Voice(real)
    try:
        g._play_level_vo(n)
        assert g.sounds.vo == []
    finally:
        g.sounds = real


def test_the_next_level_after_a_cleared_stage_is_announced_up_to_31(run):
    """update_play asks for stage + 1: clearing stage 30 announces 31, clearing 31 announces nothing."""
    g = run.game
    real = g.sounds
    g.sounds = _Voice(real)
    try:
        g._play_level_vo(30 + 1)
        g._play_level_vo(31 + 1)
        assert [v[0] for v in g.sounds.vo] == ["level31"]
    finally:
        g.sounds = real
