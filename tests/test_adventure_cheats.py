"""The codes LIVE and PHEN in the Adventure (and in its Scramble test level): typed on the mission map, in the hangar or on the
high scores, they give infinite lives / a Phenix gauge always full to every mission flown, and the Adventure is a cheated one
(nothing saved, the banner on)."""
import pygame
import pytest

import scramble as sc
import story_state as ss
from test_smoke import run  # noqa: F401,F811  (fixture)
from test_spacewar import _launch, _state

pytestmark = pytest.mark.usefixtures("training_missions")   # (the TEST missions, out of the Adventure)


def _hub(run, **kw):
    g = run.game
    ss.save_state(ss.story_path(1), _state(**kw))
    g.story.open_slot(1)
    g.story.screen = "hub"
    g.story.pane = "map"
    return g


def _type(story, code):
    for ch in code:
        story.feed_cheat(ch)


@pytest.mark.parametrize("pane", ("map", "hangar"))
def test_live_typed_in_the_adventure_turns_it_on_and_saves_nothing(run, pane):
    g = _hub(run)
    story = g.story
    story.pane = pane
    assert not story.cheating
    _type(story, "LIVE")
    assert story.cheat_live and story.cheating and story.toast


def test_a_mission_flown_after_live_has_infinite_lives(run):
    g = _hub(run)
    _type(g.story, "LIVE")
    cheat = g.story.cheat_live
    spec = _launch(run, "test_scramble")            # (_launch opens the slot again: the code is typed once more after)
    assert spec
    g.story.cheat_live = cheat
    g._begin_adventure(spec)
    p = g.player
    assert p.infinite_lives and p.lives == 99 and g.used_cheat


def _scramble_with(run, code):
    g = run.game
    _launch(run, "test_scramble")
    _type(g.story, code)
    g.story.pane = "map"
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    run.frames(2)
    return g


def test_live_in_the_scramble_level_the_rock_costs_nothing_but_the_ship_still_blows_up(run):
    g = _scramble_with(run, "LIVE")
    p, form = g.player, g.formation
    assert p.infinite_lives
    p.invulnerable = 0.0
    lives = p.lives
    explosions = len(g.explosions)
    p.y = form.course.ground(form.cam + p.x) - 5
    run.frames(1)
    assert p.lives == lives and not p.dying
    assert form.deaths == 1 and len(g.explosions) > explosions      # the blast, as for a life lost
    assert form.rock_overlap(p) == (0.0, 0.0) and p.invulnerable > 0  # back in the middle of the passage, blinking


def test_phen_in_the_adventure_keeps_the_gauge_full_and_gives_the_shield_its_dome(run):
    g = _scramble_with(run, "PHEN")
    p = g.player
    assert g.story.cheat_phen and p.phenix_auto_refill and p.adventure_dome and g.adventure["dome"]
    assert p.phenix_gauge >= 10.0 and p.phenix_cooldown == 0.0 and g.used_cheat


def test_live_and_phen_typed_on_the_high_scores_reach_the_adventure(run):
    import main_menu
    import menu_actions
    g = run.game
    g.started = g.game_over = False
    g.cheat_buffer = ""
    g.menu_screen = "highscores"
    for ch in "LIVEPHEN":
        g._feed_cheat(ch)
    assert g.cheat_live and g.phenix_cheat
    g.menu_screen = "main"
    g.menu_index = list(main_menu.MAIN).index("story")
    menu_actions.menu_confirm(g)                     # the Adventure entry of the main menu
    assert g.menu_screen == "story_hub"
    assert "LIVE" in g.story.pending_cheats and "PHEN" in g.story.pending_cheats
    ss.save_state(ss.story_path(1), _state())
    g.story.open_slot(1)
    g.story.screen = "hub"
    g.story._apply_pending_cheats()
    assert g.story.cheat_live and g.story.cheat_phen and g.story.cheating


def test_loading_the_save_again_clears_live_and_phen(run):
    g = _hub(run)
    _type(g.story, "LIVE")
    _type(g.story, "PHEN")
    assert g.story.cheating
    g.story.open_slot(1)
    assert not g.story.cheat_live and not g.story.cheat_phen and not g.story.cheating


def test_a_cheated_adventure_is_not_saved(run):
    g = _hub(run)
    _type(g.story, "LIVE")
    before = ss.load_state(ss.story_path(1))
    g.story.state["credits"] = 123456
    g.story.save()
    after = ss.load_state(ss.story_path(1))
    assert after.get("credits") == before.get("credits")


def test_without_a_code_the_missions_are_as_before(run):
    _launch(run, "test_scramble")
    g = run.game
    assert not g.player.infinite_lives and g.player.lives < 99 and not g.player.phenix_auto_refill


def test_the_scramble_hit_still_costs_a_life_without_the_code(run):
    _launch(run, "test_scramble")
    g = run.game
    p, form = g.player, g.formation
    p.lives = 3
    p.invulnerable = 0.0
    p.y = form.course.ground(form.cam + p.x) - 5
    run.frames(1)
    assert p.lives == 2 and form.deaths == 1
