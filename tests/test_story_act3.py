"""Act 3 of the Adventure: the last mission of Act 2, the attack on Phobos and the choice of the hull that keeps the
quantum anchor, the repair series of the hull kept (to 100 %, like the arcade ship), the BONUS missions, the
missions kept from before, the final series and the end."""
import os

import pygame
import pytest

import story_items
import story_state as ss
from i18n import T, t
from story import StoryHub

SHIELD_UPS = ["up_shield_1", "up_shield_2", "up_shield_3", "up_shield_4"]
PHENIX_UPS = ["up_phenix_1", "up_phenix_2", "up_phenix_3"]
FINAL = ["final_1", "final_2", "final_3", "final_4", "final_5"]


def _act2(mode="normal"):
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    ss.grant_phenix(st)
    st["credits"] = 50000
    return st


def _hub(st):
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


def _act3(hull, mode="normal"):
    st = _act2(mode)
    ss.record_result(st, "act3_gate", 100, True)
    assert ss.choose_act3_ship(st, hull)
    return st


def _win(st, mission_id):
    return ss.record_result(st, mission_id, 100, True)


def _ids(missions):
    return [m["id"] for m in missions]


# --- the end of Act 2 ----------------------------------------------------------------------------------------------
def test_the_last_mission_of_act_2_waits_for_the_phenix():
    m = ss.mission_by_id("act3_gate")
    assert m["acts"] == (2,) and m["once"] and ss.mission_waves(m) == [21, 22, 23, 24, 25]
    st = ss.create_slot(1, "NOVA", "normal")
    ss.jump_to_act2(st)
    assert "act3_gate" in _ids(ss.visible_missions(st)) and not ss.mission_playable(st, m)
    ss.grant_phenix(st)
    assert ss.mission_playable(st, m)


def test_winning_it_waits_for_the_choice():
    st = _act2()
    res = _win(st, "act3_gate")
    assert res["act3"] and st["act"] == 2 and ss.act3_pending(st)
    assert "story_log_gate3" in [e.get("key") for e in st["log"]]


def test_the_choice_keeps_one_hull_and_destroys_the_other():
    st = _act2()
    assert not ss.choose_act3_ship(st, "shield")                     # nothing to choose before the raid is won
    _win(st, "act3_gate")
    assert ss.choose_act3_ship(st, "phoenix")
    shield, phenix = st["slots"]
    assert st["act"] == 3 and st["act3_ship"] == "phoenix" and ss.kept_hull(st) == "phoenix"
    assert phenix["owned"] and not shield["owned"] and shield["destroyed"] and ss.hull_lost(st, "shield")
    assert ss.selected_slot(st)["id"] == "phoenix" and ss.loadout(st)["ship_id"] == "phoenix"
    assert not ss.act3_pending(st) and ss.flag(st, "act3")
    assert st["log"][-1] == {"key": "story_log_lost_shield"}
    assert not ss.choose_act3_ship(st, "shield")                     # once only


# --- the scenes and the choice screen -------------------------------------------------------------------------------
def test_the_attack_is_told_then_the_choice_cannot_be_skipped():
    hub = _hub(_act2())
    hub.apply_result("act3_gate", 300, True)
    assert hub.screen == "intro" and hub.scene_id == ss.ACT3_ATTACK
    assert hub.intro_slides == ss.STORY_SCENES[ss.ACT3_ATTACK]["slides"]
    hub.back()                                                       # skipped: it still counts, the choice comes
    assert hub.screen == "choice" and ss.scene_seen(hub.state, ss.ACT3_ATTACK)
    hub.back()
    assert hub.screen == "choice"                                    # B does not leave the choice
    hub.nav_h(1)
    assert hub.choice_index == 1
    hub.confirm()
    assert hub.choice_ask and not hub.del_yes                        # "Keep the PHENIX?" with NO lit
    hub.confirm()
    assert hub.screen == "choice" and not hub.choice_ask and hub.state["act"] == 2
    hub.confirm()
    hub.nav_h(1)
    hub.confirm()                                                    # YES
    assert hub.state["act"] == 3 and hub.state["act3_ship"] == "phoenix"
    assert hub.screen == "intro" and hub.scene_id == "act3_kept_phoenix"
    hub.back()
    assert hub.screen == "hub" and hub.pane == "map" and ss.scene_seen(hub.state, "act3_kept_phoenix")


def test_a_choice_left_unmade_comes_back_with_the_save():
    st = _act2()
    _win(st, "act3_gate")
    hub = _hub(st)
    assert hub.screen == "intro" and hub.scene_id == ss.ACT3_ATTACK
    hub = _hub(st)                                                   # the game was closed during the scene
    hub._end_intro()
    assert hub.screen == "choice"


def test_the_veteran_hears_another_story():
    hub = _hub(_act2("veteran"))
    hub.apply_result("act3_gate", 300, True)
    assert [k for _p, k in hub.intro_slides] == ["story_scene_attack_1", "story_scene_attack_2v"]
    hub._end_intro()
    assert hub.screen == "choice"


def test_the_choice_screen_draws(run_surface):
    hub = _hub(_act2())
    hub.apply_result("act3_gate", 300, True)
    hub._end_intro()
    hub.draw(run_surface, *_fonts())
    hub.confirm()
    hub.draw(run_surface, *_fonts())
    labels = [label for _kind, label in hub.help_items()[0]]
    assert labels == ["hint_choose", "hint_ok", "hint_cancel"]


def test_the_cheat_3333_goes_to_the_attack_and_saves_nothing():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    hub = _hub(st)
    hub.pane = "map"
    with open(ss.story_path(1), "rb") as fh:
        before = fh.read()
    for ch in "3333":
        hub.feed_cheat(ch)
    assert hub.cheating and hub.screen == "intro" and hub.scene_id == ss.ACT3_ATTACK
    hub._end_intro()
    hub.nav_h(0)
    hub.confirm()
    hub.nav_h(1)
    hub.confirm()
    assert hub.state["act"] == 3
    with open(ss.story_path(1), "rb") as fh:
        assert fh.read() == before


def test_a_picture_still_to_come_is_a_dark_sky(monkeypatch, run_surface):
    import story
    hub = StoryHub()
    calls = []
    monkeypatch.setattr(story, "log_exc", lambda *a, **k: calls.append(a))
    img = hub._intro_picture("phobos_attaque")
    assert img.get_size() == (1280, 720) and not calls


# --- the map of Act 3 ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("hull,ups,wreck", [("shield", SHIELD_UPS, "bonus_wreck_phenix"),
                                            ("phoenix", PHENIX_UPS, "bonus_wreck_shield")])
def test_the_map_shows_the_version_of_the_hull_kept(hull, ups, wreck):
    st = _act3(hull)
    ids = _ids(ss.visible_missions(st))
    assert ids[:len(ups)] == ups                                     # Act 3 first: the repairs
    assert wreck in ids and "bonus_singularity" in ids and all(f in ids for f in FINAL)
    other = PHENIX_UPS if hull == "shield" else SHIELD_UPS
    assert not set(other) & set(ids)
    # the missions that can be flown again are still there
    assert {"ch1_sortie", "best_s2", "best_s3", "best_s4", "best_boss", "paint_1", "paint_2", "paint_3"} <= set(ids)
    # the dome series, the Phenix series and the gates are not
    assert not {"dome_1", "phenix_1", "act2_gate", "act3_gate"} & set(ids)
    assert ss.mission_playable(st, ss.mission_by_id(ups[0]))
    assert not ss.mission_playable(st, ss.mission_by_id(ups[1]))


def test_the_reactor_mission_of_the_lost_hull_goes_away():
    st = _act3("shield")
    ids = _ids(ss.visible_missions(st))
    assert "bonus_2d" in ids and "bonus_2d_phenix" not in ids
    assert not ss.mission_playable(st, ss.mission_by_id("bonus_2d_phenix"))


# --- the repairs: the hull kept at 100 % -----------------------------------------------------------------------------
def test_the_shield_reaches_the_arcade_ship():
    st = _act3("shield")
    rows = [r[0] for r in ss.shop_for(st)]
    assert {"speed_100", "lives_3", "wall_immune", "dome_dur", "paint"} <= set(rows)
    assert ss.upgrade_note(st, "speed_100") == "story_locked"
    for sid in ("speed_60", "speed_80", "lives_2", "wall_slow"):
        ss.buy(st, sid)
    st["flags"]["dome_online"] = True
    ss.buy(st, "dome_on")
    for i, mid in enumerate(SHIELD_UPS):
        assert ss.mission_playable(st, ss.mission_by_id(mid)), mid
        _win(st, mid)
    for sid in ("speed_100", "lives_3", "wall_immune", "dome_dur", "dome_dur"):
        assert ss.buy(st, sid), sid
    lo = ss.loadout(st)
    assert (lo["speed_pct"], lo["lives"], lo["wall"], lo["dome_dur"]) == (100, 3, "immune", 2.0)
    assert ss.act_caps(st) == {"speed": 100, "lives": 3}
    assert ss.flag(st, "ch3_ready") and ss.mission_playable(st, ss.mission_by_id("final_1"))


def test_the_phenix_reaches_the_arcade_ship():
    st = _act3("phoenix")
    rows = [r[0] for r in ss.shop_for(st)]
    assert {"speed_100", "lives_3", "phenix_cap_100", "paint"} <= set(rows) and "wall_immune" not in rows
    for sid in ("speed_80", "lives_2", "wall_slow", "phenix_cap_80"):
        assert ss.buy(st, sid), sid
    for mid in PHENIX_UPS:
        _win(st, mid)
    for sid in ("speed_100", "lives_3", "phenix_cap_100"):
        assert ss.buy(st, sid), sid
    lo = ss.loadout(st)
    assert (lo["speed_pct"], lo["lives"], lo["phenix_pct"], lo["wall"]) == (100, 3, 100, "slow")
    assert ss.mission_playable(st, ss.mission_by_id("final_1"))


def test_a_novice_reads_five_lives():
    st = _act3("shield", "novice")
    labels = dict((r[0], r[1]) for r in ss.shop_for(st))
    assert labels["lives_3"] == "story_shop_lives5"


# --- the BONUS missions ----------------------------------------------------------------------------------------------
def test_the_wreck_pays_its_parts_once():
    st = _act3("shield")
    before = st["credits"]
    res = _win(st, "bonus_wreck_phenix")
    assert res["reward"] == 5000 and st["credits"] == before + 100 + 5000
    assert not ss.mission_playable(st, ss.mission_by_id("bonus_wreck_phenix"))


def test_the_singularity_falls_once_and_the_mission_is_done_when_caught():
    import random
    st = _act3("phoenix")
    st["flags"]["ch3_speed"] = True
    m = ss.mission_by_id("bonus_singularity")
    assert ss.mission_playable(st, m)
    plan = story_items.item_plan(st, "singularity", random.Random(1))
    assert plan["id"] == "singularity" and plan["last_wave"]
    ss.record_result(st, m["id"], 100, False, loot="singularity")   # caught: it stays even when the mission is lost
    assert ss.mission_done(st, m) and not ss.mission_playable(st, m)
    assert story_items.item_plan(st, "singularity", random.Random(1)) is None
    assert "item:singularity" in [r[0] for r in ss.shop_for(st)]


def test_the_singularity_mission_finished_without_the_core_is_neither_won_nor_lost():
    st = _act3("phoenix")
    st["flags"]["ch3_speed"] = True
    st["credits"] = 900
    m = ss.mission_by_id("bonus_singularity")
    res = ss.record_result(st, m["id"], 300, True)
    assert res["no_item"] == "singularity" and res["cleared"] is False and res["lost"] == 0
    assert st["credits"] == 900 and m["id"] not in st["cleared"]
    assert ss.mission_playable(st, m) and not ss.mission_done(st, m)
    res = ss.record_result(st, m["id"], 300, True, loot="singularity")           # with the core, the win counts
    assert res["no_item"] is None and res["cleared"] is True and st["credits"] == 1200


def test_the_hub_launches_the_drop_mission_with_its_item():
    st = _act3("shield")
    st["flags"]["ch3_speed"] = True
    hub = _hub(st)
    hub._end_intro()
    hub.pane = "map"
    hub.map_index = _ids(hub.missions()).index("bonus_singularity")
    spec = hub._launch_selected()
    assert spec and spec["galaga"] and spec["stage"] == 21


# --- the final series and the end -----------------------------------------------------------------------------------
def test_the_final_series_goes_to_triton_and_ends_the_adventure():
    st = _act3("shield")
    st["flags"]["ch3_ready"] = True
    for i, mid in enumerate(FINAL):
        m = ss.mission_by_id(mid)
        assert ss.mission_playable(st, m), mid
        if i + 1 < len(FINAL):
            assert not ss.mission_playable(st, ss.mission_by_id(FINAL[i + 1]))
        res = _win(st, mid)
    assert res["epilogue"] and ss.flag(st, ss.GAME_WON)
    assert ss.mission_waves(ss.mission_by_id("final_5")) == [26, 27, 28, 29, 30]


def test_the_last_victory_tells_the_end():
    st = _act3("phoenix")
    st["flags"]["final_s4"] = True
    hub = _hub(st)
    hub._end_intro()
    hub.apply_result("final_5", 1000, True)
    assert hub.screen == "intro" and hub.scene_id == ss.EPILOGUE
    hub._end_intro()
    hub.apply_result("final_5", 1000, True)                          # (already won: told once, then in the journal)
    assert hub.screen == "hub"
    assert ss.EPILOGUE in ss.scenes_seen(hub.state)


def test_the_journal_tells_the_story_in_order():
    st = _act3("shield")
    for sid in (ss.EPILOGUE, "final_1", "act3_kept_shield", ss.ACT3_ATTACK, "paint_1", "ch1_sortie"):
        ss.mark_scene_seen(st, sid)
    assert ss.scenes_seen(st) == ["ch1_sortie", "paint_1", ss.ACT3_ATTACK, "act3_kept_shield", "final_1", ss.EPILOGUE]


# --- the paint of the Phenix and the hangar ---------------------------------------------------------------------------
def test_the_phenix_kept_can_be_painted():
    st = _act3("phoenix")
    assert ss.paint_tints(st) == ("argent", "blue", "gold") and ss.worn_tint(st) == "argent"
    st["paint"] = {"step": 0, "runs": 1, "token": True}
    assert ss.paint_change(st, "gold")
    assert st["slots"][1]["tint"] == "gold" and ss.loadout(st)["tint"] == "gold"
    hub = _hub(st)
    assert hub._hull_key(st["slots"][1]) == "phoenix_gold"


def test_the_shield_is_still_painted_in_act_2():
    st = _act2()
    st["paint"] = {"step": 0, "runs": 1, "token": True}
    assert ss.paint_tints(st) == ss.PAINT_TINTS and ss.paint_change(st, "violet")
    assert st["slots"][0]["tint"] == "violet"


def test_the_hangar_shows_the_lost_hull_and_cannot_select_it(run_surface):
    st = _act3("phoenix")
    hub = _hub(st)
    hub._end_intro()
    hub.pane = "hangar"
    hub.nav_h(-1)
    assert ss.selected_slot(hub.state)["id"] == "phoenix"
    hub.draw(run_surface, *_fonts())


# --- the texts --------------------------------------------------------------------------------------------------------
def test_every_text_is_there_in_french_and_english():
    keys = set()
    for m in ss.MISSIONS:
        keys |= {m[f] for f in ("title", "blurb", "log", "hud_title") if m.get(f)}
    for sid in list(ss.SCENES) + list(ss.STORY_SCENES):
        sc = ss.scene_of(sid)
        keys.add(sc["title"])
        keys |= {k for _p, k in sc["slides"] + sc.get("veteran", [])}
    keys |= {"story_choice_title", "story_choice_q", "story_choice_q_v", "story_choice_shield_d",
             "story_choice_phoenix_d", "story_choice_note", "story_choice_ask", "story_choice_warn", "story_ch3",
             "story_hull_lost", "story_reward", "story_act3_start", "story_cheat_act3", "story_log_lost_shield",
             "story_log_lost_phoenix", "story_shop_phenix100", "story_paint_title_phenix", "story_paint_argent",
             "story_paint_blue", "story_paint_gold"}
    for key in keys:
        assert T[key].get("fr") and T[key].get("en"), key
        assert "..." not in T[key]["fr"], key                        # the ellipsis is always "…"


def test_the_pilot_is_named_in_the_choice_and_the_end():
    for key in ("story_scene_attack_2", "story_scene_attack_2v", "story_scene_epilogue_2", "story_scene_epilogue_2v"):
        assert "{name}" in T[key]["fr"] and "{name}" in T[key]["en"], key
    assert "Kamarasov" not in T["story_scene_epilogue_2v"]["fr"].split("professeur")[0]


# --- helpers ----------------------------------------------------------------------------------------------------------
@pytest.fixture
def run_surface():
    pygame.display.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((8, 8))
    return pygame.Surface((1280, 720))


def _fonts():
    import fonts
    return fonts.text(28), fonts.title(32), fonts.text(22), fonts.body(22)
