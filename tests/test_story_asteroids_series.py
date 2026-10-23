"""The Asteroids level as the prelude of the main series of each act: Ceinture I (60 rocks) before the Dome, II (80)
before the Phenix, III (100) before la Riposte. Replayable, paid each time, with a scene told before the first launch."""
import pygame
import pytest

import story
import story_state as ss
from i18n import LANG_CODES, T, set_lang, t
from story import StoryHub

PRELUDES = (("ast_1", "dome_1", "ast_s1", 60, 1), ("ast_2", "phenix_1", "ast_s2", 80, 2),
            ("ast_3", "final_1", "ast_s3", 100, 3))


@pytest.fixture(autouse=True)
def _french_again():
    yield
    set_lang("fr")


def _act1():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    return st


def _act2():
    st = _act1()
    ss.jump_to_act2(st)
    return st


def _act3(hull="shield"):
    st = _act1()
    ss.grant_phenix(st)
    ss.record_result(st, "act3_gate", 100, True)
    assert ss.choose_act3_ship(st, hull)
    return st


def _belt(st, mid):
    return ss.mission_by_id(mid)


@pytest.mark.parametrize("mid,first,flag,target,act", PRELUDES)
def test_the_missions_are_made_for_their_act(mid, first, flag, target, act):
    m = ss.mission_by_id(mid)
    assert m["acts"] == (act,) and m["asteroids"] is True and m["target"] == target and m["unlock"] == [flag]
    assert not m.get("once") and not m.get("test") and not m.get("hunt") and m["content"] == 1
    assert ss.mission_by_id(first)["need"] == flag
    assert ss.mission_group(m) == ss.GROUP_STORY


def test_no_test_mission_is_left():
    assert not [m["id"] for m in ss.MISSIONS if m.get("test") or m["id"] == "bonus_asteroids"]
    assert "bonus_asteroids" not in ss.SCENES


def test_the_dome_waits_for_the_belt_in_act_1():
    st = _act1()
    ast, dome = ss.mission_by_id("ast_1"), ss.mission_by_id("dome_1")
    assert ss.mission_playable(st, ast) and not ss.mission_playable(st, dome)
    assert ss.unlock_hint(st, dome) is ast
    ss.record_result(st, "ast_1", 300, True)
    assert ss.mission_playable(st, dome) and ss.flag(st, "ast_s1")


def test_the_phenix_series_waits_for_the_belt_in_act_2():
    st = _act2()
    ast, first = ss.mission_by_id("ast_2"), ss.mission_by_id("phenix_1")
    assert ss.mission_playable(st, ast) and not ss.mission_playable(st, first)
    assert ss.unlock_hint(st, first) is ast
    assert "ast_1" not in [m["id"] for m in ss.visible_missions(st)]
    ss.record_result(st, "ast_2", 300, True)
    assert ss.mission_playable(st, first)


def test_la_riposte_waits_for_the_belt_in_act_3():
    st = _act3()
    ast, first = ss.mission_by_id("ast_3"), ss.mission_by_id("final_1")
    assert not ss.mission_playable(st, ast)                                # the hull must be at 100 % first
    assert ss.unlock_hint(st, ast) is not None
    st["flags"]["ch3_ready"] = True
    assert ss.mission_playable(st, ast) and not ss.mission_playable(st, first)
    assert ss.unlock_hint(st, first) is ast
    ss.record_result(st, "ast_3", 300, True)
    assert ss.mission_playable(st, first)


@pytest.mark.parametrize("hull", ("shield", "phoenix"))
def test_the_belt_of_act_3_is_for_both_hulls(hull):
    st = _act3(hull)
    st["flags"]["ch3_ready"] = True
    assert ss.mission_playable(st, ss.mission_by_id("ast_3"))


def test_the_belt_is_replayable_and_paid_every_time():
    st = _act1()
    for n in range(3):
        before = st["credits"]
        res = ss.record_result(st, "ast_1", 400 + n, True)
        assert res["first"] is (n == 0) and st["credits"] == before + 400 + n
        assert ss.mission_playable(st, ss.mission_by_id("ast_1"))
    assert st["cleared"].count("ast_1") == 1 and st["log"] == [{"key": "story_log_ast1"}]


def test_the_belt_comes_first_in_the_story_part_of_the_map():
    st = _act1()
    ids = [m["id"] for m in ss.visible_missions(st)]
    assert ids.index("ast_1") + 1 == ids.index("dome_1")
    assert ss.mission_group(ss.mission_by_id("ch1_sortie")) == ss.GROUP_HUNT and ids.index("ch1_sortie") < ids.index("ast_1")
    st = _act2()
    ids = [m["id"] for m in ss.visible_missions(st)]
    assert ids.index("ast_2") + 1 == ids.index("phenix_1")
    st = _act3()
    st["flags"]["ch3_ready"] = True
    ids = [m["id"] for m in ss.visible_missions(st)]
    assert ids.index("ast_3") + 1 == ids.index("final_1")


def test_the_map_suggests_the_belt_when_the_hunts_are_done():
    st = _act1()
    for mid in ("ch1_sortie", "best_s2", "best_s3", "best_s4"):
        ss.record_result(st, mid, 100, True)
    nxt = ss.next_mission(st, ss.visible_missions(st))
    assert nxt["id"] == "ast_1"
    ss.record_result(st, "ast_1", 100, True)
    assert ss.next_mission(st, ss.visible_missions(st))["id"] == "dome_1"


@pytest.mark.parametrize("mode,lost,fallen", (("normal", 25, False), ("novice", 10, False), ("veteran", 0, True)))
def test_a_defeat_in_the_belt_is_a_defeat(mode, lost, fallen):
    st = _act1()
    st["mode"], st["credits"] = mode, 500
    res = ss.record_result(st, "ast_1", 900, False)
    assert (res["lost"], res["fallen"], res["cleared"]) == (lost, fallen, False)
    assert not ss.flag(st, "ast_s1") and "ast_1" not in st["cleared"]


# ---------------------------------------------------------------------- the cheats and the old saves
def test_the_act_2_cheat_counts_the_first_belt_as_crossed():
    st = _act1()
    ss.jump_to_act2(st)
    assert "ast_1" in st["cleared"] and ss.flag(st, "ast_s1")
    assert "ast_2" not in st["cleared"] and not ss.flag(st, "ast_s2")


def test_the_phenix_cheat_counts_the_second_belt_as_crossed():
    st = _act1()
    ss.grant_phenix(st)
    assert "ast_2" in st["cleared"] and ss.flag(st, "ast_s2") and ss.mission_playable(st, ss.mission_by_id("ast_2"))
    assert "ast_3" not in st["cleared"]


def test_the_unlock_cheat_lists_every_prelude():
    st = _act1()
    ids = [m["id"] for m in ss.visible_missions(st, cheat=True)]
    assert {"ast_1", "ast_2", "ast_3"} <= set(ids)
    assert all(ss.mission_playable(st, ss.mission_by_id(i), cheat=True) for i in ("ast_1", "ast_2", "ast_3"))


@pytest.mark.parametrize("mid,first,flag,target,act", PRELUDES)
def test_an_old_save_with_the_series_started_skips_the_belt(mid, first, flag, target, act):
    data = ss.default_state()
    data["cleared"] = [first]
    st = ss.migrate_state(data)
    assert ss.flag(st, flag) and mid in st["cleared"]
    assert st["cleared"].count(mid) == 1
    again = ss.migrate_state(st)                                   # (loading it again changes nothing)
    assert again["cleared"] == st["cleared"] and again["flags"] == st["flags"]


def test_an_old_save_without_the_series_meets_the_belt():
    data = ss.default_state()
    data["cleared"] = ["ch1_sortie", "best_s2"]
    st = ss.migrate_state(data)
    assert not ss.flag(st, "ast_s1") and "ast_1" not in st["cleared"] and st["cleared"] == ["ch1_sortie", "best_s2"]
    assert not ss.mission_playable(st, ss.mission_by_id("dome_1")) and ss.mission_playable(st, ss.mission_by_id("ast_1"))


def test_a_save_in_act_2_with_the_phenix_series_started_only_skips_that_belt():
    data = ss.default_state()
    data["act"] = 2
    data["cleared"] = ["dome_1", "phenix_1"]
    st = ss.migrate_state(data)
    assert {"ast_1", "ast_2"} <= set(st["cleared"]) and "ast_3" not in st["cleared"]


# ---------------------------------------------------------------------- the launch
@pytest.mark.parametrize("mid,first,flag,target,act", PRELUDES)
def test_the_launch_carries_the_rocks_to_destroy(mid, first, flag, target, act):
    st = {1: _act1, 2: _act2, 3: _act3}[act]()
    st["flags"]["ch3_ready"] = True
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.map_index = [m["id"] for m in hub.missions()].index(mid)
    spec = hub._launch_selected()
    assert spec["asteroids"] is True and spec["target"] == target and spec["id"] == mid and "test" not in spec


def test_the_blurb_gives_the_number_of_rocks():
    for mid, _first, _flag, target, _act in PRELUDES:
        assert str(target) in story.mission_blurb(ss.mission_by_id(mid))
    assert story.mission_blurb(ss.mission_by_id("dome_1")) == t("story_m_dome1_b")


# ---------------------------------------------------------------------- the narration
@pytest.mark.parametrize("mid", ("ast_1", "ast_2", "ast_3"))
def test_each_belt_has_a_scene_with_its_text(mid):
    scene = ss.scene_of(mid)
    assert scene and len(scene["slides"]) == 1
    pic, key = scene["slides"][0]
    assert pic == "ceinture_asteroides"                           # the picture will come later: a dark sky until then
    n = mid[-1]
    assert key == "story_scene_ast" + n and scene["title"] == "story_scene_ast%s_t" % n
    for code in ("fr", "en"):
        assert len(T[key][code]) > 400 and "..." not in T[key][code]
        assert T[scene["title"]][code]
    assert T[key]["fr"] != T[key]["en"]


def test_the_scenes_come_in_the_order_of_the_story():
    order = ss.SCENE_ORDER
    assert order.index("ast_1") + 1 == order.index("dome_1")
    assert order.index("ast_2") < order.index("paint_1") and order.index("best_boss") < order.index("ast_2")
    assert order.index("bonus_wreck_shield") < order.index("ast_3") < order.index("final_1")
    assert set(ss.SCENES) <= set(order)


def test_the_scene_is_told_before_the_first_launch_and_not_again():
    st = _act1()
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "map"
    hub.map_index = [m["id"] for m in hub.missions()].index("ast_1")
    assert hub._hub_confirm() is None and hub.screen == "intro" and hub.scene_id == "ast_1" and hub.scene_launch
    ss.mark_scene_seen(hub.state, "ast_1")
    hub.screen = "hub"
    assert hub._hub_confirm()["id"] == "ast_1"


def test_the_journal_lists_the_scene_once_seen():
    st = _act1()
    ss.mark_scene_seen(st, "ast_1")
    ss.mark_scene_seen(st, "dome_1")
    entries = ss.journal_entries(st)
    assert entries.index({"scene": "ast_1"}) + 1 == entries.index({"scene": "dome_1"})
    assert t("story_log_scene").format(title=t("story_scene_ast1_t")) in [ss.log_text(e, t) for e in entries]


def test_the_texts_of_the_missions_exist():
    for key in ("story_m_ast1", "story_m_ast2", "story_m_ast3", "story_m_ast_hud", "story_m_ast_b", "story_log_ast1",
                "story_log_ast2", "story_log_ast3", "story_asteroids_hud"):
        assert T[key]["fr"] and T[key]["en"], key
    assert "{n}" in T["story_m_ast_b"]["fr"] and "{n}" in T["story_m_ast_b"]["en"]
    assert "story_test_won" not in T and "story_test_over" not in T and "story_m_ast" not in T


@pytest.mark.parametrize("lang", LANG_CODES)
def test_every_language_has_a_blurb_that_formats(lang):
    set_lang(lang)
    assert "60" in story.mission_blurb(ss.mission_by_id("ast_1"))


# ---------------------------------------------------------------------- in the game
from test_smoke import run  # noqa: E402,F401  (fixture)


def _fly(g, st, mid):
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mid)
    spec = g.story._launch_selected()
    assert spec, mid
    g._begin_adventure(spec)
    g.input_grace = 0.0
    return spec


@pytest.mark.parametrize("mid,first,flag,target,act", PRELUDES)
def test_the_field_of_each_act_asks_for_its_number_of_rocks(run, mid, first, flag, target, act):
    st = {1: _act1, 2: _act2, 3: _act3}[act]()
    st["flags"]["ch3_ready"] = True
    _fly(run.game, st, mid)
    assert run.game.formation.target == target
    assert run.game.adventure["target"] == target


def test_winning_the_belt_opens_the_series_and_moves_the_cursor_on(run):
    g = run.game
    st = _act1()
    for hunt in ("ch1_sortie", "best_s2", "best_s3", "best_s4"):
        ss.record_result(st, hunt, 0, True)                       # (the hunts come first on the map: they are done)
    st["credits"] = 0
    _fly(g, st, "ast_1")
    g.story.apply_result("ast_1", 420, True, flawless=False)
    assert ss.flag(g.story.state, "ast_s1") and g.story.state["credits"] == 420
    assert g.story._mission()["id"] == "dome_1"                  # the cursor goes on to the series it opened
    assert g.story.toast == t("story_clear").format(pts=420)
