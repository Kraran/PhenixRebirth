"""A finished Adventure mission leaves nothing of itself behind: the next game (arcade or mission) starts from a clean run.

Bug: a mission lost for good went back to the map without the soft reset that "Quit game" does, so the dead ship (and
its mission settings) stayed in the game; the next arcade run began with that dead ship and its "game over" ran at once.
"""
import pygame
import pytest

import story_state as ss
from player import Player
from test_smoke import run  # noqa: F401  (fixture)


def _launch(g, mode="normal", mission="ch1_sortie"):
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.cheat_unlock = True
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mission)
    ss.mark_scene_seen(g.story.state, mission)
    spec = g.story._launch_selected()
    assert spec
    g._begin_adventure(spec)
    g.input_grace = 0.0
    return spec


def _lose(run, g):
    """The ship is shot down; wait until the mission is over and the map is back."""
    run.frames(30)
    g.player.lives = 1
    g.player.hit()
    for _ in range(600):
        run.frames(1)
        if g.adventure is None:
            return
    raise AssertionError("the mission never ended")


def _arcade(run, g):
    g.menu_screen = "main"
    g.play_mode = "solo"
    g._begin_run()
    g.input_grace = 0.0


def _no_sequence(g):
    return not g.game_over and g.hs_phase is None and g.hotseat_hold <= 0 and g.hotseat_pending is None


@pytest.mark.parametrize("mode", ["normal", "veteran"])
def test_an_arcade_game_after_a_lost_mission_is_a_new_game(run, mode):
    g = run.game
    _launch(g, mode)
    _lose(run, g)
    run.frames(60)                                                  # the player spends a while on the map
    _arcade(run, g)
    run.frames(1)
    assert g.player.alive and not g.player.dying and g.player.lives == 3 and g.stage == 1 and g.adventure is None
    for _ in range(300):
        run.frames(1)
        assert _no_sequence(g), "the old game over came back"
    assert g.started and g.player.alive


def test_the_ship_of_the_mission_does_not_follow_into_the_arcade(run):
    g = run.game
    fresh = Player(0, 0)
    _launch(g)
    run.frames(30)
    assert g.player.lives == 1 and g.player.speed != fresh.speed    # (the mission ship is the slow prototype)
    _lose(run, g)
    _arcade(run, g)
    assert g.player.speed == fresh.speed
    assert not getattr(g.player, "adventure_dome", False) and not hasattr(g.player, "adventure_wall")


def test_a_won_mission_does_not_leave_its_score_or_stage_either(run):
    g = run.game
    _launch(g)
    run.frames(30)
    g.score = 1234
    g.stage = 3
    g._end_adventure(True)
    assert g.score == 0 and g.stage == 1 and g.boss_saucer is None and g.explosions == []
    _arcade(run, g)
    run.frames(10)
    assert g.score == 0 and g.life_thresholds == [(1337, False), (8086, False)]


def test_the_end_of_a_mission_clears_every_part_of_the_run(run):
    g = run.game
    _launch(g)
    run.frames(30)
    g.hotseat_hold, g.hotseat_pending = 1.5, "gameover"             # a pending game over (nothing arms it in a mission)
    g.go_card_t, g.go_card_after, g.go_rumble_on = 1.0, "switch", True
    g.hs_queue, g.hs_coop_queue = [1], [2]
    g.lives_shared, g.hitstop, g.shake_amount = 1, 0.3, 4.0
    g._end_adventure(False)
    assert _no_sequence(g)
    assert (g.go_card_t, g.go_card_after, g.go_rumble_on) == (0.0, "hs", False)
    assert g.hs_queue == [] and g.hs_coop_queue == []
    assert g.lives_shared == 5 and g.hitstop == 0.0 and g.shake_amount == 0.0
    assert g.player.alive and not g.player.dying and g.player2 is None and not g.hotseat


def test_the_map_and_the_story_are_kept(run):
    g = run.game
    _launch(g)
    slot_no = g.story.slot_no
    _lose(run, g)
    assert g.menu_screen == "story_hub" and g.story.slot_no == slot_no and g.story.state is not None
    assert g.started is False and g.adventure is None


def test_quitting_by_the_pause_menu_just_after_the_death_leaves_no_old_game_over(run):
    g = run.game
    _launch(g)
    run.frames(30)
    g.player.lives = 1
    g.player.hit()
    run.frames(6)
    for key in (pygame.K_ESCAPE, pygame.K_DOWN, pygame.K_DOWN, pygame.K_DOWN, pygame.K_RETURN):      # Resume, Options, Help, Quit
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0))
        run.frames(2)
    assert g.started is False and g.adventure is None
    run.frames(90)
    _arcade(run, g)
    for _ in range(200):
        run.frames(1)
        assert _no_sequence(g)
    assert g.player.alive


def test_a_second_mission_after_a_lost_one_starts_clean(run):
    g = run.game
    _launch(g)
    _lose(run, g)
    run.frames(60)
    _launch(g)
    for _ in range(120):
        run.frames(1)
        assert _no_sequence(g) and g.adventure is not None
    assert g.player.alive


# What a run leaves behind, one by one: dirty value -> the value of a new game.
DIRTY = [
    ("player2", object(), None), ("tesla_fx", object(), None), ("game_over", True, False), ("hs_phase", "table", None),
    ("stage_transition", "fly_up", None), ("transition_timer", 5.0, 0.0), ("boss_saucer", object(), None),
    ("boss_bird_timer", 3.0, 0.0), ("_boss_angry_queue", [1], []), ("_boss_cry_quiet", 2.0, 0.0),
    ("bosses_defeated", 4, 0), ("life_flash_timer", 2.0, 0.0), ("life_flash_index", 3, -1),
    ("stage_life_lost", True, False), ("stage_touched_edge", True, False), ("paused", True, False),
    ("pause_index", 2, 0), ("pause_options", True, False), ("quit_confirm", True, False), ("hotseat", True, False),
    ("current_p", 1, 0), ("hotseat_wait", True, False), ("hotseat_next", 1, 0), ("hs_slot_label", 2, 1),
    ("go_card_player", 2, None), ("explosions", [object()], []), ("score", 99, 0), ("stage", 7, 1),
]


@pytest.mark.parametrize("name,dirty,clean", DIRTY, ids=[d[0] for d in DIRTY])
def test_every_part_of_the_run_is_forgotten(run, name, dirty, clean):
    g = run.game
    _launch(g)
    run.frames(10)
    setattr(g, name, dirty)
    g._end_adventure(False)
    assert getattr(g, name) == clean, name


def test_the_slots_and_the_formation_are_new(run):
    g = run.game
    _launch(g)
    run.frames(10)
    old_formation, old_player = g.formation, g.player
    g.slots = [{"x": 1}, {"y": 2}]
    g._end_adventure(False)
    assert g.slots == [None, None]
    assert g.formation is not old_formation and g.player is not old_player
    assert g.player.sounds is g.sounds and g.formation.sounds is g.sounds
