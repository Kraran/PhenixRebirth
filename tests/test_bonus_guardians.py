"""BONUS FINAL - Gardiens (story_state "bonus_gd_endless"): the arcade game level after level, with one more small Guardian
each level (five at most), then from level 6 one big Guardian (the Alpha) more every five levels; it ends with the
GAME OVER of the ship, its points paid, leaving it gains nothing, the best score kept and shown at the top."""
import pytest

import guardian as gd
import highscores
import story_state as ss
from test_smoke import run  # noqa: F401  (fixture)

MID = "bonus_gd_endless"


def _state(mode="normal", credits=1000, ending=True):
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    st["credits"] = credits
    if ending:
        ss.complete_ending(st)
    return st


def _launch(run, **kw):
    g = run.game
    ss.save_state(ss.story_path(1), _state(**kw))
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(MID)
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    g.player.infinite_lives = False
    return spec


def _kinds(sq):
    big = sum(1 for g in sq.guardians if isinstance(g, gd.AlphaGuardian))
    return len(sq.guardians) - big, big


# ------------------------------------------------------------------ the mission
def test_a_final_bonus_of_act_4_secret_until_the_end():
    m = ss.mission_by_id(MID)
    assert m["acts"] == (ss.ENDING_ACT,) and ss.mission_group(m) == ss.GROUP_FINAL and m["endless"]
    assert not ss.mission_open(_state(ending=False), m) and ss.mission_open(_state(), m)
    assert ss.next_mission(_state(), [m]) is None
    import i18n
    assert i18n.T[m["title"]]["fr"] == "BONUS FINAL - Gardiens"


@pytest.mark.parametrize("level, small, big", [(1, 1, 0), (2, 2, 0), (5, 5, 0), (6, 1, 1), (7, 2, 1), (10, 5, 1),
                                               (11, 1, 2), (12, 2, 2), (16, 1, 3)])
def test_the_guardians_of_each_level(level, small, big):
    assert ss.endless_guardians(level) == (small, big)


def test_a_squad_with_two_alphas_puts_them_in_the_middle():
    import pygame
    pygame.display.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 64))
    sq = gd.GuardianSquad(3, alphas=2)
    kinds = [isinstance(g, gd.AlphaGuardian) for g in sq.guardians]
    assert kinds == [False, True, True, False, False]
    assert [isinstance(g, gd.AlphaGuardian) for g in gd.GuardianSquad(2, alpha=True).guardians] == [False, True, False]


# ------------------------------------------------------------------ in the game
def test_the_levels_follow_one_another_with_their_guardians(run):
    spec = _launch(run)
    g = run.game
    assert spec["endless"] and spec["waves"] == [1] and g.stage == 1
    assert g.guardian_squad is not None and _kinds(g.guardian_squad) == (1, 0)
    for level in range(2, 13):
        assert g._next_adventure_wave() is True                         # (never the last one)
        assert g.stage == level and g.adventure["level"] == level
        assert _kinds(g.guardian_squad) == ss.endless_guardians(level), level


def test_each_new_level_is_announced(run):
    import update_play
    _launch(run)
    g = run.game
    said = []
    g._play_level_vo = lambda n: said.append(n)
    update_play.begin_stage_clear(g)
    assert said == [2] and g.stage_transition == "fly_up"


def test_the_loss_of_the_ship_shows_game_over_pays_and_keeps_the_best(run):
    _launch(run, credits=1000)
    g = run.game
    run.frames(2)
    g.score = 7777
    g.player.lives = 1
    g.player.alive = False
    g.player.dying = False
    run.frames(3)
    st = ss.load_state(ss.story_path(1))
    assert st["credits"] == 1000 + 7777 and ss.endless_best(st, MID) == 7777 and not st.get("fallen")
    seen = False
    for _ in range(60 * 15):
        seen = seen or (g.game_over and g.hs_phase == "card")
        if g.adventure is None:
            break
        run.frames(1)
    assert seen and g.adventure is None
    assert all(e.get("score") != 7777 for e in highscores.load_highscores())


def test_leaving_it_gains_nothing(run):
    _launch(run, credits=300)
    g = run.game
    run.frames(2)
    g.score = 900
    g._quit_to_menu()
    st = ss.load_state(ss.story_path(1))
    assert st["credits"] == 300 and ss.endless_best(st, MID) == 0


def test_the_record_is_shown_at_the_top(run, monkeypatch):
    import draw_frame
    import i18n
    _launch(run)
    g = run.game
    g.story.state[ss.ENDLESS_BEST] = {MID: 12000}
    g.score = 500
    assert draw_frame.endless_record(g, g.adventure) == 12000
    asked = []
    real = i18n.t
    monkeypatch.setattr("draw_frame.t", lambda k, *a, **kw: (asked.append(k), real(k, *a, **kw))[1])
    run.frames(2)
    assert "story_ast_record" in asked and "story_wave_n" not in asked
