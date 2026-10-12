"""A Veteran who dies in the Adventure gets the real GAME OVER of the game (explosion, GAME OVER card, announcer voice, pad
rumble), then the slot list where his save is a memorial. The fall is written down at the moment of death."""
import pygame
import pytest

import story_state as ss
from test_smoke import run  # noqa: F401  (fixture)


def _launch(g, mode):
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    g.menu_screen = "story_hub"
    g.story.open_slot(1)
    g.story.map_index = 0
    spec = g.story._launch_selected()
    assert spec
    g._begin_adventure(spec)
    g.input_grace = 0
    return spec


def _die(run, g):
    run.frames(30)
    g.player.lives = 0
    g.player.alive = False


class _Voice:
    def __init__(self, real):
        self._real = real
        self.vo = []

    def play_vo(self, name, *a, **k):
        self.vo.append(name)

    def __getattr__(self, name):
        return getattr(self._real, name)


def _frames_until(run, cond, limit=900):
    for i in range(limit):
        if cond():
            return i
        run.frames(1)
    raise AssertionError("never happened")


def test_a_dying_veteran_gets_the_hold_then_the_game_over_card_then_the_memorial(run):
    g = run.game
    _launch(g, "veteran")
    g.sounds = _Voice(g.sounds)
    _die(run, g)
    run.frames(1)
    assert g.started and g.adventure is not None                       # not thrown out at once: the explosion is seen
    assert g.hotseat_pending == "adventure_over" and g.hotseat_hold > 1.0 and not g.game_over
    _frames_until(run, lambda: g.game_over and g.hs_phase == "card")
    assert g.go_card_after == "adventure" and g.sounds.vo == ["gameover_vo"]       # the normal GAME OVER, with its voice
    assert g.started and g.adventure is not None                       # the playfield is still behind the card
    _frames_until(run, lambda: not g.started)
    assert g.menu_screen == "story_hub" and g.adventure is None and not g.game_over
    assert g.anchor_fx is None and g.story.screen == "slots"           # a fallen Veteran has no anchor: the memorial
    assert ss.load_state(ss.story_path(1))["fallen"] is True


def test_the_card_lasts_as_long_as_the_one_of_the_arcade(run):
    g = run.game
    _launch(g, "veteran")
    _die(run, g)
    t_hold = _frames_until(run, lambda: g.game_over and g.hs_phase == "card")
    t_card = _frames_until(run, lambda: not g.started)
    assert 100 <= t_hold <= 140                                         # HOTSEAT_HOLD_FINAL (1.95 s) at 60 Hz
    assert 120 <= t_card <= 140                                         # 2.15 s card


def test_the_fall_is_saved_at_the_moment_of_death_not_at_the_end_of_the_card(run):
    g = run.game
    _launch(g, "veteran")
    _die(run, g)
    run.frames(2)
    assert g.hotseat_pending == "adventure_over"
    assert ss.load_state(ss.story_path(1))["fallen"] is True            # closing the game now does not save him
    assert g.adventure["banked"] is True


def test_the_result_is_written_once(run):
    g = run.game
    _launch(g, "veteran")
    calls = []
    real = g.story.apply_result
    g.story.apply_result = lambda *a, **k: (calls.append(a), real(*a, **k))[1]
    _die(run, g)
    _frames_until(run, lambda: not g.started)
    assert len(calls) == 1


def test_skipping_the_card_works_like_in_the_arcade(run):
    g = run.game
    _launch(g, "veteran")
    _die(run, g)
    _frames_until(run, lambda: g.game_over and g.hs_phase == "card")
    run.frames(70)                                                      # after one second the card can be skipped
    g._skip_gameover_card()
    assert not g.started and g.menu_screen == "story_hub" and g.story.screen == "slots"


@pytest.mark.parametrize("mode", ["normal", "novice"])
def test_normal_and_novice_still_fall_back_to_base_at_once(run, mode):
    g = run.game
    _launch(g, mode)
    _die(run, g)
    run.frames(1)
    assert not g.started and g.menu_screen == "story_hub" and g.adventure is None   # no game over card, as before
    assert not g.game_over and g.hotseat_pending is None
    assert g.anchor_fx is not None                                      # the quantum anchor
    assert not ss.load_state(ss.story_path(1)).get("fallen")


def test_a_won_mission_of_a_veteran_is_not_a_game_over(run):
    g = run.game
    _launch(g, "veteran")
    run.frames(10)
    g._end_adventure(True)
    assert not g.started and not g.game_over and g.hotseat_pending is None
    assert not ss.load_state(ss.story_path(1)).get("fallen")


def test_a_fallen_veteran_does_not_pay_for_a_picture_he_will_never_see(run):
    g = run.game
    _launch(g, "veteran")
    shots = []
    real = g._anchor_snapshot
    g._anchor_snapshot = lambda: (shots.append(1), real())[1]
    _die(run, g)
    _frames_until(run, lambda: not g.started)
    assert shots == []                                                  # no anchor, so no snapshot of the mission
