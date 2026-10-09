"""Act 2 Bestiary hunt of the saucer and its commander: the arcade boss level (5), replayable, one level
more after each victory (boss of level 5, 10, 15...). Also the trumpets when the Shield is painted."""
import os

import pytest

import story_state as ss
from boss import BossSaucer
from i18n import t
from settings import asset_path
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

ID = "best_boss"


def _act2():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    return st


def _launch(g, st, cheat=False):
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.cheat_unlock = cheat
    g.story.map_index = [m["id"] for m in g.story.missions()].index(ID)
    spec = g.story._launch_selected()
    assert spec
    g._begin_adventure(spec)
    return spec


# ------------------------------------------------------------------ the mission
def test_the_mission_is_a_replayable_act_2_hunt_on_the_boss_level():
    m = ss.mission_by_id(ID)
    assert ss.is_hunt(m) and m["acts"] == (2,) and m["need"] == "act2" and not m.get("once")
    assert m["content"] == 5 and ss.mission_waves(m) == [5]
    assert ss.hunt_stage(m, 1) == 5


def test_it_is_on_the_map_of_act_2_only_after_the_hunts_and_before_the_phenix():
    ids = [m["id"] for m in ss.visible_missions(_act2())]
    assert ids.index(ID) == ids.index("best_s4") + 1 and ids.index(ID) + 1 == ids.index("phenix_1")
    assert ID not in [m["id"] for m in ss.visible_missions(ss.create_slot(1, "A", "normal"))]
    assert ID in [m["id"] for m in ss.visible_missions(ss.create_slot(1, "A", "normal"), cheat=True)]


def test_it_opens_with_act_2_and_not_before():
    st = ss.create_slot(1, "NOVA", "normal")
    m = ss.mission_by_id(ID)
    assert not ss.mission_playable(st, m)
    assert ss.mission_playable(_act2(), m)
    assert ss.mission_playable(st, m, cheat=True)


def test_the_level_goes_up_by_one_at_each_victory_and_plays_the_next_boss():
    st = _act2()
    m = ss.mission_by_id(ID)
    for wins in range(5):
        assert ss.hunt_level(st, ID) == wins + 1 and ss.hunt_stage(m, wins + 1) == 5 * (wins + 1)
        ss.record_result(st, ID, 500, True, {"boss": 1})
    assert ss.mission_playable(st, m)                               # always replayable


def test_a_lost_run_keeps_the_level_and_the_mission_stays_open():
    st = _act2()
    ss.record_result(st, ID, 100, False, {"boss": 0})
    assert ss.hunt_level(st, ID) == 1 and ss.mission_playable(st, ss.mission_by_id(ID))
    ss.record_result(st, ID, 500, True, {"boss": 1})
    ss.record_result(st, ID, 100, False, {})
    assert ss.hunt_level(st, ID) == 2


def test_the_journal_lines_follow_the_first_victory():
    st = _act2()
    ss.record_result(st, ID, 500, True, {"boss": 1})
    entries = ss.journal_entries(st)
    i = entries.index({"key": "story_log_bestboss"})
    assert entries[i + 1] == {"level": 2, "mission": ID} and entries[i + 2] == {"kills": 1, "mission": ID}
    assert ss.log_text(entries[i], t) == t("story_log_bestboss")


def test_the_texts_exist_in_every_language():
    from i18n import T, LANG_CODES
    for key in ("story_m_bestboss", "story_m_bestboss_b", "story_log_bestboss"):
        assert set(T[key]) == set(LANG_CODES) and t(key)
    assert "soucoupe" in t("story_m_bestboss_b").lower()


# ------------------------------------------------------------------ in the game
def test_level_one_flies_the_boss_of_stage_five(run):
    g = run.game
    spec = _launch(g, _act2())
    assert spec["level"] == 1 and spec["waves"] == [5] and spec["id"] == ID
    assert g.stage == 5 and isinstance(g.boss_saucer, BossSaucer)


@pytest.mark.parametrize("wins,stage", [(1, 10), (2, 15), (3, 20)])
def test_higher_levels_fly_the_boss_of_the_next_rounds(run, wins, stage):
    g = run.game
    st = _act2()
    for _ in range(wins):
        ss.record_result(st, ID, 500, True, {"boss": 1})
    spec = _launch(g, st)
    assert spec["level"] == wins + 1 and spec["waves"] == [stage]
    assert g.stage == stage and isinstance(g.boss_saucer, BossSaucer)
    assert g._boss_kill_points() == 500 + 10 * ((stage - 1) // 5)


def test_killing_the_commander_wins_the_mission_and_raises_the_level(run):
    import update_play
    g = run.game
    _launch(g, _act2())
    run.frames(120)
    g.score = 700
    g._boss_kill_points()                                          # the commander is destroyed...
    update_play.boss_cataclysm(g)                                  # ...the saucer blows up
    for _ in range(900):
        run.frames(1)
        if g.adventure is None:
            break
    assert g.adventure is None and g.menu_screen == "story_hub"
    st = g.story.state
    assert ID in st["cleared"] and ss.hunt_level(st, ID) == 2
    assert st["bestiary"].get("boss", 0) >= 1
    assert ss.mission_total_kills(st, ID) >= 1


# ------------------------------------------------------------------ the trumpets of the paint shop
def test_the_fanfare_sound_file_exists_and_is_loaded(run):
    assert os.path.exists(asset_path("sounds", "paint_fanfare.wav"))
    assert "paint_fanfare" in run.game.sounds.sounds


def _paint_hub():
    st = _act2()
    st["paint"] = {"step": 0, "runs": 1, "token": True}
    st["credits"] = 5000
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


def test_painting_the_shield_asks_for_the_fanfare_once():
    hub = _paint_hub()
    hub.paint_mode, hub.paint_choice = True, 1                      # green
    assert hub.confirm() is None
    assert hub.take_sounds() == ["paint_fanfare"] and hub.take_sounds() == []
    assert hub.toast == t("story_paint_done") and not hub.paint_mode


def test_no_fanfare_when_nothing_is_painted():
    hub = _paint_hub()
    shield = next(sl for sl in hub.state["slots"] if sl["id"] == "shield")
    hub.paint_mode, hub.paint_choice = True, ss.PAINT_TINTS.index(shield.get("tint") or "red")
    hub.confirm()                                                   # the colour already worn: nothing is spent
    assert hub.take_sounds() == []
    hub.state["credits"] = 0
    hub.paint_mode, hub.paint_choice = True, 2
    hub.confirm()                                                   # not enough points
    assert hub.take_sounds() == []


def test_the_game_plays_the_fanfare_when_the_paint_is_validated(run):
    import menu_actions
    g = run.game
    played = []
    real = g.sounds.play
    g.sounds.play = lambda name, *a, **k: played.append(name) or real(name, *a, **k)
    g.story = _paint_hub()
    g.story.pane = "hangar"
    g.story.paint_mode, g.story.paint_choice = True, 1
    g.menu_screen = "story_hub"
    menu_actions.menu_confirm(g)
    assert played.count("paint_fanfare") == 1
