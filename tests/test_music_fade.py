"""The trumpets of the paint shop (the Shield painted at Wallems') play over the music: the music fades down while they sound
and comes back as they end (SoundManager.MUSIC_FADE, fade_music)."""
import pygame
import pytest

import menu_actions
from sounds import SoundManager
from test_smoke import run  # noqa: F401  (fixture)
from test_story_saucer_mission import _paint_hub


@pytest.fixture
def snd(run):
    s = run.game.sounds
    s.set_music_volume(0.8)
    s.play_music("menu", fade_ms=0)
    for _ in range(3):
        s.update(0.016)
    return s


def _run(snd, seconds, step=1 / 60):
    """The music volume wanted at every step (the mixer itself only knows steps of 1/128, see test_the_mixer_follows...)."""
    seen = []
    for _ in range(int(seconds / step)):
        snd.update(step)
        seen.append(snd._music_out())
    return seen


def test_the_trumpets_are_a_sound_that_fades_the_music():
    assert "paint_fanfare" in SoundManager.MUSIC_FADE
    assert not {"explosion", "enemy_shoot", "1up", "level1"} & set(SoundManager.MUSIC_FADE)


def test_the_music_fades_down_stays_low_and_comes_back(snd):
    base = snd._music_out()
    assert base > 0.1
    snd.fade_music(6.0, level=0.1, down=0.5, up=2.0)
    seen = _run(snd, 7.0)
    low = min(seen)
    assert abs(low - base * 0.1) < 0.01, (low, base)
    down_end = next(i for i, v in enumerate(seen) if v <= low + 0.002)
    assert 0.35 < down_end / 60 < 0.65                                      # down in half a second
    assert all(a >= b - 0.003 for a, b in zip(seen[:down_end], seen[1:down_end + 1]))     # steadily down...
    hold = [v for v in seen[down_end:down_end + 150]]
    assert max(hold) - min(hold) < 0.005                                   # ...stays low...
    back = next(i for i, v in enumerate(seen[down_end:], down_end) if v > low + 0.01)
    assert 3.4 < back / 60 < 4.4                                           # ...starts back about `up` seconds before the end
    assert abs(seen[-1] - base) < 0.001                                    # whole again
    tail = seen[back:]
    assert all(b >= a - 0.003 for a, b in zip(tail, tail[1:]))             # steadily up
    assert snd._dip_spec is None and snd._dip == 1.0


def test_no_jump_at_any_moment(snd):
    snd.fade_music(6.0)
    seen = _run(snd, 7.0)
    # no step bigger than what the smooth curve gives at its steepest (1.5 x the range over the time it takes, down = 0.5 s)
    steepest = 1.5 * (max(seen) - min(seen)) / (0.5 * 60)
    assert max(abs(a - b) for a, b in zip(seen, seen[1:])) < steepest * 1.05


def test_the_mixer_follows_the_wanted_volume_within_its_steps(snd):
    snd.fade_music(6.0, level=0.1)
    for _ in range(420):
        snd.update(1 / 60)
        assert abs(pygame.mixer.music.get_volume() - snd._music_out()) <= 1 / 128 + 1e-6


def test_a_short_sound_still_goes_down_and_up(snd):
    base = snd._music_out()
    snd.fade_music(1.0, level=0.2, down=0.5, up=2.0)                       # shorter than down + up: no stay, no jump
    seen = _run(snd, 3.0)
    assert min(seen) < base * 0.6 and abs(seen[-1] - base) < 0.001
    steepest = 1.5 * (base - min(seen)) / (0.5 * 60)
    assert max(abs(a - b) for a, b in zip(seen, seen[1:])) < steepest * 1.05


def test_the_fanfare_fades_the_music_for_as_long_as_it_lasts(snd):
    base = snd._music_out()
    length = snd.sounds["paint_fanfare"].get_length()
    assert snd.play("paint_fanfare") is not None
    seen = _run(snd, length + 0.2)
    assert min(seen) < base * 0.15
    assert seen[int((length - 3.0) * 60)] < base * 0.2                     # still low while the trumpets play
    seen2 = _run(snd, 3.0)
    assert abs(seen2[-1] - base) < 0.001                                   # and whole again a moment after


def test_the_trumpets_are_not_late_the_music_comes_back_by_the_end_of_them(snd):
    base = snd._music_out()
    length = snd.sounds["paint_fanfare"].get_length()
    snd.play("paint_fanfare")
    seen = _run(snd, length + 0.5)
    assert seen[-1] > base * 0.9


def test_other_sounds_do_not_touch_the_music(snd):
    base = snd._music_out()
    snd.play("explosion")
    snd.play("enemy_shoot")
    seen = _run(snd, 1.0)
    assert min(seen) == max(seen) == base and snd._dip_spec is None


def test_a_muted_game_has_no_fade(snd):
    snd.sfx_muted = True
    base = snd._music_out()
    assert snd.play("paint_fanfare") is None
    assert min(_run(snd, 1.0)) == base and snd._dip_spec is None
    snd.sfx_muted = False


def test_the_fade_and_the_announcer_duck_add_up(snd):
    base = snd._music_out()
    snd._duck = 0.5
    snd._dip = 0.2
    assert abs(snd._music_out() - base * 0.5 * 0.2) < 1e-9
    snd._duck = snd._dip = 1.0


def test_a_new_theme_starting_during_the_fade_starts_low(snd):
    snd.fade_music(6.0, level=0.1)
    _run(snd, 1.0)
    low = pygame.mixer.music.get_volume()
    snd.play_music("credits", fade_ms=0)
    for _ in range(40):
        snd.update(0.016)
    assert pygame.mixer.music.get_volume() <= low + 0.01


def test_a_second_fade_goes_on_from_where_the_music_is(snd):
    snd.fade_music(6.0, level=0.1)
    _run(snd, 2.0)
    now = snd._dip
    snd.fade_music(6.0, level=0.1)
    assert snd._dip_spec[0] == now and snd._dip == now
    seen = _run(snd, 0.1)
    assert max(abs(a - b) for a, b in zip(seen, seen[1:])) < 0.01


def test_changing_the_music_volume_during_the_fade_keeps_it_low(snd):
    snd.fade_music(6.0, level=0.1)
    _run(snd, 1.0)
    snd.set_music_volume(1.0)
    assert pygame.mixer.music.get_volume() < 0.05


def test_validating_the_paint_in_the_game_fades_the_music(run):
    g = run.game
    g.sounds.set_music_volume(0.8)
    g.sounds.play_music("menu", fade_ms=0)
    run.frames(3)
    base = pygame.mixer.music.get_volume()
    g.story = _paint_hub()
    g.story.pane = "hangar"
    g.story.paint_mode, g.story.paint_choice = True, 1
    g.menu_screen = "story_hub"
    menu_actions.menu_confirm(g)
    run.frames(70)
    assert pygame.mixer.music.get_volume() < base * 0.2
    for _ in range(int(9 * 60)):
        g.sounds.update(1 / 60)
    assert abs(pygame.mixer.music.get_volume() - base) < 0.001


def test_a_refused_paint_leaves_the_music_alone(run):
    g = run.game
    g.sounds.play_music("menu", fade_ms=0)
    run.frames(3)
    base = pygame.mixer.music.get_volume()
    g.story = _paint_hub()
    g.story.pane = "hangar"
    g.story.state["credits"] = 0
    g.story.paint_mode, g.story.paint_choice = True, 1
    g.menu_screen = "story_hub"
    menu_actions.menu_confirm(g)
    run.frames(60)
    assert pygame.mixer.music.get_volume() == base


def test_no_fade_when_the_trumpets_find_no_free_channel(snd, monkeypatch):
    monkeypatch.setattr(snd, "_play_on_channel", lambda *a, **k: None)
    assert snd.play("paint_fanfare") is None
    assert snd._dip_spec is None and min(_run(snd, 1.0)) == max(_run(snd, 0.1))


def test_the_curve_is_smooth_at_both_ends_of_each_slope(snd):
    snd.fade_music(6.0, level=0.1)
    seen = _run(snd, 7.0)
    linear = (max(seen) - min(seen)) / (0.5 * 60)                          # the step of a straight line down
    assert abs(seen[0] - seen[1]) < linear * 0.4                            # starts gently
    k = next(i for i, v in enumerate(seen) if v <= min(seen) + 1e-9)
    assert abs(seen[k - 1] - seen[k]) < linear * 0.4                        # lands gently
