"""The cheat code LVxx (typed on the HIGH SCORES screen) starts the game at any stage from 02 to 99 (it was LVL2 to LVL5);
the haut-fait "To boldly go" now asks for stage 31 (it asked for 21), the last stage the announcer says."""
import pygame
import pytest

import achievements
import game as game_mod
import i18n
import update_play
from settings import stage_content
from test_smoke import run  # noqa: F401  (fixture)


def _type(g, text):
    for ch in text:
        g._feed_cheat(ch)


def _fresh(run):
    g = run.game
    g.started, g.game_over, g.used_cheat = False, False, False
    g.cheat_buffer = ""
    g.menu_screen = "highscores"
    return g


# --- the code LVxx ---------------------------------------------------------------------------------------------------
def test_the_range_is_02_to_99():
    assert (game_mod.CHEAT_MIN_STAGE, game_mod.CHEAT_MAX_STAGE) == (2, 99)


@pytest.mark.parametrize("n", [2, 5, 6, 9, 10, 21, 31, 32, 50, 77, 99])
def test_lvxx_starts_the_game_at_that_stage(run, n):
    g = _fresh(run)
    _type(g, "LV%02d" % n)
    assert g.started and g.stage == n
    assert g.used_cheat is True                                      # a cheat run never reaches the high scores
    assert g.cheat_msg == i18n.t("cheat_stage").format(n=n) and g.cheat_kind == "stage"
    assert g.cheat_buffer == ""
    assert g.bosses_defeated == (n - 1) // 5
    if stage_content(n) == 5:
        assert g.boss_saucer is not None
    else:
        assert g.formation.get_alive_enemies()


def test_it_does_not_care_about_the_case_nor_what_was_typed_before(run):
    g = _fresh(run)
    _type(g, "xyzlv42")
    assert g.started and g.stage == 42


@pytest.mark.parametrize("text", ["LV00", "LV01", "LV1", "LV", "LV5", "LVL2", "LVL3", "LVL4", "LVL5", "VL02", "LW02", "LV0A", "LV-5"])
def test_other_codes_start_nothing(run, text):
    g = _fresh(run)
    _type(g, text)
    assert not g.started


@pytest.mark.parametrize("typed,stage", [("LV00LV42", 42), ("LV01LV33", 33), ("LV9LV17", 17)])
def test_a_refused_code_does_not_hide_the_next_one(run, typed, stage):
    g = _fresh(run)
    _type(g, typed)
    assert g.started and g.stage == stage


def test_lv0_then_5_is_stage_5_and_the_next_digit_is_not_a_second_code(run):
    g = _fresh(run)
    _type(g, "LV0")
    assert not g.started
    _type(g, "5")
    assert g.started and g.stage == 5


def test_the_other_codes_still_work(run):
    g = _fresh(run)
    g.player.infinite_lives = False
    _type(g, "LIVE")
    assert g.cheat_live and g.player.infinite_lives and g.player.lives == 99
    _type(g, "PHEN")
    assert g.phenix_cheat
    _type(g, "LV12")                                                  # stackable with the others
    assert g.stage == 12 and g.player.infinite_lives and g.player.phenix_auto_refill


def test_the_keys_of_the_high_score_screen_reach_the_code(run):
    g = _fresh(run)
    g.input_grace = 0.0
    for ch in "lv31":
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=ord(ch), unicode=ch, mod=0, scancode=0))
        run.frames(1)
    assert g.started and g.stage == 31


@pytest.mark.parametrize("n", [30, 55, 99])
def test_the_game_runs_at_a_high_stage(run, n):
    """The speed and the points keep growing past stage 30: a few seconds of play at the stage, boss stages included."""
    g = _fresh(run)
    _type(g, "LV%02d" % n)
    g.player.infinite_lives = True
    run.frames(240)
    assert g.stage == n and g.started


# --- "To boldly go" at stage 31 --------------------------------------------------------------------------------------
def test_the_haut_fait_asks_for_stage_31():
    assert achievements.BOLDLY_GO_STAGE == 31
    assert achievements.SCALABLE["boldly_go"] == (31, 31, 31, 31)


def test_its_description_says_31_in_every_language():
    for lang in i18n.LANG_CODES:
        text = i18n.T["ach_boldly_go_d"][lang]
        assert "31" in text and "21" not in text, (lang, text)


def _fly_up(g, stage):
    """Ships are off the top: the stage after `stage` is set up."""
    g.adventure = None
    g.stage = stage
    for ship in g._ships():
        ship.y = -200
    calls = []
    g._note_scalable = lambda aid, amount=1, absolute=False: calls.append((aid, amount, absolute))
    update_play.tick_fly_up(g)
    return calls


@pytest.mark.parametrize("stage", [20, 29])
def test_reaching_stages_20_to_30_no_longer_counts(run, stage):
    g = run.game
    calls = _fly_up(g, stage)
    assert g.stage == stage + 1
    assert not any(c[0] == "boldly_go" for c in calls)


@pytest.mark.parametrize("stage", [30, 31, 45])
def test_reaching_stage_31_or_more_counts(run, stage):
    g = run.game
    calls = _fly_up(g, stage)
    assert ("boldly_go", stage + 1, True) in calls


def test_a_cheat_run_never_earns_it(run, monkeypatch):
    g = run.game
    g.used_cheat, g.attract_mode, g.adventure = True, False, None
    seen = []
    monkeypatch.setattr(game_mod, "set_scalable_at_least", lambda *a, **k: seen.append(a) or (True, "gold"))
    g._note_scalable("boldly_go", 99, absolute=True)
    assert seen == []


def test_in_the_achievement_list_the_goal_is_31(run, monkeypatch):
    import achievements_screen as scr
    g = run.game
    data = {"unlocked": {}, "progress": {}, "tiers": {}}
    assert scr.progress_line("boldly_go", data) is not None
    assert "31" in scr.progress_line("boldly_go", data)
