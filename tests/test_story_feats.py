"""The achievements of the Adventure page (src/story_feats.py): read from the saves, the events the saves do not
keep (upgrades bought, missions without a life lost), the banners, a cheated Adventure that earns nothing."""
import pygame
import pytest

import achievements as ach
import story_feats as sf
import story_state as ss
from story import StoryHub


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    """Every test starts with no achievement, its own data in memory (no Game), no news waiting."""
    data = {"unlocked": {}, "progress": {}, "tiers": {}}
    monkeypatch.setattr(sf, "_game", None)
    monkeypatch.setattr(sf, "_data", lambda: data)
    monkeypatch.setattr(ach, "save_achievements", lambda d: d)
    sf.take_news()
    yield data
    sf.take_news()


def _state(**kw):
    st = ss.create_slot(1, "NOVA", kw.pop("mode", "normal"))
    st.update(kw)
    return st


def _win(st, mission_id, times=1, **kw):
    for _ in range(times):
        ss.record_result(st, mission_id, 100, True, **kw)


def test_every_mission_flown_again_has_bronze_silver_gold():
    """A mission that can be flown again (the Bestiary hunts, the paint series) has an achievement with tiers."""
    renewable = [m["id"] for m in ss.MISSIONS if ss.is_hunt(m) or ss.is_paint(m)]
    covered = set(sf.HUNTS.values()) | {"paint_1", "paint_2", "paint_3"}
    assert set(renewable) <= covered
    for aid in list(sf.HUNTS) + ["adv_paint"]:
        steps = ach.SCALABLE[aid]
        assert len(steps) == 4 and list(steps) == sorted(set(steps)), aid       # normal < bronze < silver < gold


def test_the_page_is_full_with_act_3():
    assert len(ach.CATALOG_ADV) == 32 and len(set(ach.ADV_IDS)) == 32
    assert set(ach.ADV_IDS).isdisjoint(ach.CATALOG_IDS)


# --- Act 3 --------------------------------------------------------------------------------------------------------------
def _act3(hull, mode="normal"):
    st = ss.create_slot(1, "NOVA", mode)
    ss.grant_phenix(st)
    ss.record_result(st, "act3_gate", 100, True)
    ss.choose_act3_ship(st, hull)
    return st


def test_the_raid_and_the_choice(fresh):
    st = _act3("phoenix")
    sf.check(st)
    assert {"adv_raid", "adv_anchor"} <= set(fresh["unlocked"])
    assert "adv_full" not in fresh["unlocked"]


@pytest.mark.parametrize("hull,buys", [("shield", ("speed_60", "speed_80", "speed_100", "lives_2", "lives_3",
                                                   "wall_slow", "wall_immune", "dome_dur", "dome_dur", "dome_dur")),
                                       ("phoenix", ("speed_80", "speed_100", "lives_2", "lives_3",
                                                    "phenix_cap_80", "phenix_cap_100"))])
def test_one_hundred_per_cent(fresh, hull, buys):
    st = _act3(hull)
    st["credits"] = 99999
    for name in ("ch1_speed", "ch1_life_2", "ch1_wall", "ch3_speed", "ch3_lives", "ch3_wall", "ch3_dome", "ch3_gauge"):
        st["flags"][name] = True
    for sid in buys:
        assert not sf.at_full(st)
        assert ss.buy(st, sid), sid
    assert sf.at_full(st)
    sf.check(st)
    assert "adv_full" in fresh["unlocked"]


def test_the_bonus_missions(fresh):
    st = _act3("shield")
    ss.record_result(st, "bonus_wreck_phenix", 100, True)
    ss.record_result(st, "bonus_singularity", 100, True)               # won, but the core was not caught
    sf.check(st)
    assert "adv_wreck" in fresh["unlocked"] and "adv_convoy" not in fresh["unlocked"]
    ss.record_result(st, "bonus_singularity", 100, True, loot="singularity")
    sf.check(st)
    assert "adv_convoy" in fresh["unlocked"]


@pytest.mark.parametrize("hull,mode,expected,absent", [
    ("shield", "normal", {"adv_triton", "adv_win_shield"}, {"adv_win_phenix", "adv_legend"}),
    ("phoenix", "veteran", {"adv_triton", "adv_win_phenix", "adv_legend"}, {"adv_win_shield"})])
def test_the_end_of_the_adventure(fresh, hull, mode, expected, absent):
    st = _act3(hull, mode)
    st["flags"]["ch3_ready"] = True
    for i, mid in enumerate(("final_1", "final_2", "final_3", "final_4")):
        ss.record_result(st, mid, 100, True)
    sf.check(st)
    assert ach.scalable_progress("adv_riposte", fresh) == 4 and ach.scalable_tier("adv_riposte", fresh) == "silver"
    assert "adv_triton" not in fresh["unlocked"]
    ss.record_result(st, "final_5", 100, True)
    sf.check(st)
    assert ach.scalable_tier("adv_riposte", fresh) == "gold"
    assert expected <= set(fresh["unlocked"]) and not absent & set(fresh["unlocked"])


def test_untouchable_only_for_triton_without_a_life_lost(fresh):
    st = _act3("shield")
    st["flags"]["final_s4"] = True
    st["flags"]["ch3_ready"] = True
    hub = _hub(st)
    hub.apply_result("final_4", 100, True, flawless=True)
    assert "adv_untouchable" not in fresh["unlocked"]
    hub.apply_result("final_5", 100, True, flawless=False)
    assert "adv_untouchable" not in fresh["unlocked"]
    hub.apply_result("final_5", 100, True, flawless=True)
    assert "adv_untouchable" in fresh["unlocked"] and "adv_untouchable" in ach.SECRETS


def test_a_golden_phenix(fresh):
    st = _act3("phoenix")
    st["paint"] = {"step": 0, "runs": 1, "token": True}
    st["credits"] = 5000
    assert ss.paint_change(st, "gold")
    sf.check(st)
    assert {"adv_gilded", "adv_colour"} <= set(fresh["unlocked"])


def test_a_new_pilot(fresh):
    news = sf.check(_state())
    assert ("adv_pilot", None) in news and "adv_pilot" in fresh["unlocked"]
    assert sf.check(_state()) == []                                    # nothing new the second time


def test_the_hunts_go_up_the_tiers(fresh):
    st = _state()
    _win(st, "ch1_sortie", 3)
    sf.check(st)
    assert ach.scalable_tier("adv_sortie", fresh) == "bronze"
    _win(st, "ch1_sortie", 5)
    news = sf.check(st)
    assert ("adv_sortie", "gold") in news and ach.scalable_progress("adv_sortie", fresh) == 8


def test_the_best_of_all_the_saves_is_kept(fresh):
    a = _state()
    _win(a, "best_s2", 5)
    sf.check(a)
    b = _state()
    _win(b, "best_s2", 1)
    sf.check(b)
    assert ach.scalable_progress("adv_kaki", fresh) == 5 and ach.scalable_tier("adv_kaki", fresh) == "silver"


def test_what_a_save_says(fresh):
    st = _state(mode="veteran", act=2, credits=2600)
    for m in ("dome_1", "dome_2", "phenix_1"):
        st.setdefault("cleared", []).append(m)
    st["bestiary"] = {"bird1": 250, "bird2": 3, "garg3": 1, "boss": 10}
    st["paint"] = {"step": 0, "runs": 2, "token": False}
    ss.mark_scene_seen(st, "ch1_sortie")
    ss.mark_scene_seen(st, ss.BAR_SCENE)
    st["slots"][0]["tint"] = "violet"
    counts = sf.counts(st)
    assert counts["adv_domes"] == 2 and counts["adv_phenix"] == 1 and counts["adv_paint"] == 2
    assert counts["adv_saver"] == 2600 and counts["adv_bestiary"] == 4 and counts["adv_hunter"] == 2
    assert counts["adv_cinema"] == 1                                   # the bar is not a mission scene
    assert sf.done(st) == {"adv_pilot", "adv_act2", "adv_veteran", "adv_colour", "adv_bar"}
    sf.check(st)
    assert ach.scalable_tier("adv_saver", fresh) == "bronze"            # 1000, 2500, 5000, 10000
    assert ach.scalable_tier("adv_hunter", fresh) == "bronze"


def test_the_reactor(fresh):
    st = _state()
    st["items"] = {"act": 1, "got": {"reactor_shield": "found"}, "since": 0}
    assert "adv_reactor" in sf.done(st)
    assert "adv_reactor" in ach.SECRETS


def test_a_normal_pilot_in_act_2_is_no_veteran():
    assert "adv_veteran" not in sf.done(_state(act=2))
    assert "adv_veteran" not in sf.done(_state(mode="veteran"))


# --- the Adventure hub -----------------------------------------------------------------------------------------------
def _hub(st):
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


def test_an_old_save_gets_what_it_has_earned_when_opened(fresh):
    st = _state()
    _win(st, "best_s3", 3)
    _hub(st)
    assert ach.scalable_tier("adv_garg", fresh) == "bronze"


def test_a_mission_won_counts_at_once(fresh):
    hub = _hub(_state())
    hub.apply_result("best_s4", 500, True)
    assert ach.scalable_progress("adv_shadow", fresh) == 1
    assert ("adv_shadow", "normal") in sf.take_news()


def test_a_mission_without_a_life_lost(fresh):
    hub = _hub(_state())
    hub.apply_result("ch1_sortie", 100, True, flawless=True)
    hub.apply_result("ch1_sortie", 100, True, flawless=False)
    hub.apply_result("ch1_sortie", 100, False, flawless=True)          # lost: does not count
    assert ach.scalable_progress("adv_flawless", fresh) == 1


def test_an_upgrade_bought(fresh):
    st = _state(credits=5000)
    st["flags"]["ch1_speed"] = True                                    # (opened by the first sortie)
    hub = _hub(st)
    assert hub._buy(("speed_60",))
    assert ach.scalable_progress("adv_mechanic", fresh) == 1
    assert not hub._buy(("speed_60",))                                 # refused: nothing counted
    assert ach.scalable_progress("adv_mechanic", fresh) == 1


def test_a_cheated_adventure_earns_nothing(fresh):
    st = _state(credits=5000)
    st["flags"]["ch1_speed"] = True
    hub = _hub(st)
    sf.take_news()
    fresh["unlocked"].clear()
    fresh["progress"].clear()
    hub.cheat_unlock = True
    hub._buy(("speed_60",))
    hub.apply_result("ch1_sortie", 100, True, flawless=True)
    assert fresh["unlocked"] == {} and fresh["progress"] == {} and sf.take_news() == []


# --- in the game -------------------------------------------------------------------------------------------------------
def test_a_life_lost_in_a_mission_is_remembered():
    import update_play

    class G:
        adventure = {"id": "ch1_sortie"}
    g = G()
    update_play._life_lost(g)
    assert g.stage_life_lost and g.adventure["life_lost"]


def test_the_game_shows_the_news_one_after_the_other(monkeypatch):
    from game import Game
    import i18n
    i18n.set_lang("fr")
    g = Game()
    g._intro_done = True
    sf._news.extend([("adv_pilot", None), ("adv_sortie", "gold")])
    g.started = False
    g.cheat_msg_timer = 0.0
    g._tick_story_feats()
    assert g.cheat_msg == "HAUT FAIT — Matricule" and g.cheat_kind == "ach"
    g._tick_story_feats()
    assert g.cheat_msg == "HAUT FAIT — Matricule"                      # the first one stays its time
    g.cheat_msg_timer = 0.0
    g._tick_story_feats()
    assert g.cheat_msg == "HAUT FAIT — Première sortie — Or"
    g.running = False


def test_the_game_shares_its_data(monkeypatch):
    """The hub writes into the Game's own copy: the next arcade unlock does not write the old one back."""
    from game import Game
    monkeypatch.undo()                                                  # the real story_feats._data and saving
    g = Game()
    sf.check(_state())
    assert "adv_pilot" in g.ach_data["unlocked"]
    assert "adv_pilot" in ach.load_achievements()["unlocked"]
    g.running = False
    pygame.event.clear()
