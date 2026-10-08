"""Act 2: the map of the act, the five Phenix missions, the Phenix hull and its workshop; the 5 % penalty."""
import pygame
import pytest

import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

HUNTS = ["ch1_sortie", "best_s2", "best_s3", "best_s4"]
DOME = ["dome_1", "dome_2", "dome_3", "dome_4", "dome_5", "act2_gate"]
PHENIX = ["phenix_1", "phenix_2", "phenix_3", "phenix_4", "phenix_5"]
PAINT = ["paint_1", "paint_2", "paint_3"]


def _act2():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["flags"].update(bestiary_s2=True, bestiary_s3=True, bestiary_s4=True, ch1_speed=True, ch1_life_2=True,
                       ch1_wall=True, dome_s1=True, dome_s2=True, dome_s3=True, dome_s4=True, dome_s5=True,
                       dome_online=True, act2=True)
    st["cleared"] = ["ch1_sortie", "best_s2", "best_s3", "best_s4"] + DOME
    st["act"] = 2
    return st


def _win(st, mission_id, score=100):
    return ss.record_result(st, mission_id, score, True, {})


def _ids(missions):
    return [m["id"] for m in missions]


# ------------------------------------------------------------------ the 5 % penalty
def test_a_failed_mission_costs_five_percent():
    assert ss.PENALTY_RATE == 0.05
    st = ss.create_slot(1, "NOVA", "normal")
    st["credits"] = 1000
    res = ss.record_result(st, "ch1_sortie", 500, False, {})
    assert res["lost"] == 50 and st["credits"] == 950
    assert ss.failure_penalty(0) == 0 and ss.failure_penalty(9) == 0 and ss.failure_penalty(10) == 1


def test_veteran_still_dies_for_good():
    st = ss.create_slot(1, "NOVA", "veteran")
    st["credits"] = 1000
    res = ss.record_result(st, "ch1_sortie", 500, False, {})
    assert res["fallen"] and st["fallen"] and st["credits"] == 1000


# ------------------------------------------------------------------ the map of each act
def test_the_map_of_act_1_has_no_phenix_mission():
    st = ss.create_slot(1, "NOVA", "normal")
    assert _ids(ss.visible_missions(st)) == HUNTS + DOME + ["ch2_tease"]


def test_the_map_of_act_2_keeps_the_hunts_and_drops_the_dome_missions():
    st = _act2()
    assert _ids(ss.visible_missions(st)) == HUNTS + PHENIX + PAINT


def test_the_cheat_lists_every_mission():
    st = _act2()
    assert _ids(ss.visible_missions(st, cheat=True)) == _ids(ss.MISSIONS)
    assert set(DOME + PHENIX + HUNTS) <= set(_ids(ss.MISSIONS))


def test_the_gate_starts_act_2():
    st = ss.create_slot(1, "NOVA", "normal")
    st["flags"]["dome_s5"] = True
    res = _win(st, "act2_gate")
    assert res["act"] == 2 and st["act"] == 2 and ss.flag(st, "act2")
    assert _ids(ss.visible_missions(st)) == HUNTS + PHENIX + PAINT


def test_the_hunts_stay_replayable_in_act_2_with_their_level():
    st = _act2()
    st["mission_clears"] = {"ch1_sortie": 2}
    hunt = ss.mission_by_id("ch1_sortie")
    assert ss.mission_playable(st, hunt) and ss.hunt_level(st, "ch1_sortie") == 3
    _win(st, "ch1_sortie")
    assert ss.hunt_level(st, "ch1_sortie") == 4


# ------------------------------------------------------------------ the five Phenix missions
def test_the_series_is_chained_and_flown_once():
    st = _act2()
    for i, mid in enumerate(PHENIX):
        mission = ss.mission_by_id(mid)
        assert mission["once"] and mission["acts"] == (2,)
        assert ss.mission_playable(st, mission), mid
        for later in PHENIX[i + 1:]:
            assert not ss.mission_playable(st, ss.mission_by_id(later)), (mid, later)
        _win(st, mid)
        assert not ss.mission_playable(st, mission), mid          # not renewable
    assert all(m in st["cleared"] for m in PHENIX)


def test_the_series_is_not_open_before_act_2():
    st = ss.create_slot(1, "NOVA", "normal")
    assert not ss.mission_open(st, ss.mission_by_id("phenix_1"))


def test_the_series_climbs_above_the_gate():
    waves = [ss.mission_waves(ss.mission_by_id(m)) for m in PHENIX]
    assert waves == [[16, 17], [], [18, 19], [16, 17, 18, 19], [16, 17, 18, 19, 20]]
    swarm = ss.mission_by_id("phenix_2")
    assert swarm["swarm"] and swarm["stage"] == 16
    assert min(w for ws in waves for w in ws) > 15                 # all of it is harder than the gate


def test_a_lost_run_does_not_advance_the_series():
    st = _act2()
    st["credits"] = 400
    res = ss.record_result(st, "phenix_1", 100, False, {})
    assert res["lost"] == 20 and "phenix_1" not in st["cleared"] and not ss.flag(st, "phenix_s1")
    assert ss.mission_playable(st, ss.mission_by_id("phenix_1"))


def test_each_mission_writes_its_line_in_the_journal():
    from i18n import t
    st = _act2()
    for mid in PHENIX:
        _win(st, mid)
    keys = [e["key"] for e in st["log"] if isinstance(e, dict)]
    assert keys[-5:] == ["story_log_ph%d" % i for i in range(1, 6)]
    for k in keys[-5:]:
        assert t(k) != k and len(t(k)) > 10


# ------------------------------------------------------------------ the Phenix hull
def test_the_hangar_starts_without_the_phenix():
    st = _act2()
    assert not st["slots"][1]["owned"]
    assert ss.loadout(st)["ship_id"] == "shield"


def test_the_fifth_mission_hands_over_the_phenix():
    st = _act2()
    for mid in PHENIX[:4]:
        res = _win(st, mid)
        assert not st["slots"][1]["owned"] and not res.get("hull"), mid
    res = _win(st, "phenix_5")
    assert st["slots"][1]["owned"] and res["hull"] == "phoenix" and ss.flag(st, "phenix_owned")
    assert st["slots"][1]["tint"] == "argent" and st["slots"][1]["lives"] == 1 and st["slots"][1]["speed"] == 60


def test_the_hull_is_not_handed_twice_or_on_a_loss():
    st = _act2()
    ss.record_result(st, "phenix_5", 100, False, {})
    assert not st["slots"][1]["owned"]
    _win(st, "phenix_5")
    st["slots"][1]["lives"] = 2
    assert _win(st, "phenix_5").get("hull") is None
    assert st["slots"][1]["lives"] == 2


def test_the_phenix_survives_a_save(tmp_path):
    st = _act2()
    _win(st, "phenix_5")
    path = str(tmp_path / "s.json")
    ss.save_state(path, st)
    back = ss.load_state(path)
    assert back["slots"][1]["owned"] and back["act"] == 2 and ss.flag(back, "phenix_owned")


# ------------------------------------------------------------------ the Phenix workshop
def _with_phenix(credits=10000):
    st = _act2()
    _win(st, "phenix_5")
    st["selected_slot"] = 1
    st["credits"] = credits
    return st


def test_the_shield_workshop_is_unchanged():
    st = _act2()
    assert ss.shop_for(st) == ss.SHOP + [ss.PAINT_ROW]              # plus the paint shop, from Act 2 on
    assert [r[0] for r in ss.shop_for(st)] == ["speed_60", "speed_80", "lives_2", "wall_slow", "dome_on", "paint"]


def test_the_phenix_has_its_own_rows():
    st = _with_phenix()
    assert [r[0] for r in ss.shop_for(st)] == ["speed_80", "lives_2", "wall_slow", "phenix_cap_80"]


def test_the_phenix_buys_its_upgrades_for_its_own_hull_only():
    st = _with_phenix()
    assert ss.buy(st, "speed_80") and st["slots"][1]["speed"] == 80 and st["slots"][0]["speed"] == 40
    assert ss.buy(st, "lives_2") and st["slots"][1]["lives"] == 2 and st["slots"][0]["lives"] == 1
    assert ss.buy(st, "wall_slow") and st["slots"][1]["wall"] == "slow"
    assert not ss.buy(st, "dome_on") and not st["slots"][1].get("dome")      # the dome is the Shield's


def test_the_phenix_gauge_goes_from_60_to_80_once():
    st = _with_phenix()
    assert ss.phenix_cap(st["slots"][1]) == 60
    before = st["credits"]
    assert ss.buy(st, "phenix_cap_80")
    assert ss.phenix_cap(st["slots"][1]) == 80 and st["credits"] == before - 1000
    assert not ss.buy(st, "phenix_cap_80")                               # already owned
    assert ss.upgrade_note(st, "phenix_cap_80") == "story_owned"
    assert ss.loadout(st)["phenix_pct"] == 80


def test_the_gauge_upgrade_needs_the_phenix_and_its_flag():
    st = _act2()
    assert ss.upgrade_note(st, "phenix_cap_80") == "story_locked"
    st["credits"] = 5000
    assert not ss.buy(st, "phenix_cap_80")
    st["flags"]["phenix_owned"] = True                                   # the flag alone is not enough: the hull is the Shield
    assert not ss.buy(st, "phenix_cap_80") and ss.phenix_cap(st["slots"][0]) == 60


def test_a_damaged_gauge_value_is_clamped():
    for junk, expected in ((None, 60), ("x", 60), (10, 60), (80, 80), (500, 100), (True, 60)):
        assert ss.phenix_cap({"phenix_cap": junk}) == expected, junk


def test_the_workshop_cannot_buy_without_enough_points():
    st = _with_phenix(credits=999)
    assert not ss.buy(st, "phenix_cap_80") and ss.phenix_cap(st["slots"][1]) == 60


# ------------------------------------------------------------------ in the hub
def _hub(st):
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


def _texts(hub, run):
    import story
    seen = []
    real, real_fit = story._text, story._text_fit

    def spy(surface, font, text, *a, **k):
        seen.append(str(text))
        return real(surface, font, text, *a, **k)

    def spy_fit(surface, font, text, *a, **k):
        seen.append(str(text))
        return real_fit(surface, font, text, *a, **k)

    story._text, story._text_fit = spy, spy_fit
    try:
        g = run.game
        hub.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
    finally:
        story._text, story._text_fit = real, real_fit
    return seen


def test_the_act_2_map_shows_the_phenix_series_and_not_the_dome(run):
    from i18n import t
    hub = _hub(_act2())
    hub.pane = "map"
    shown = _texts(hub, run)
    assert t("story_ch2") in shown and t("story_ch1") not in shown
    assert any(t("story_m_best2") in x for x in shown)
    assert any(t("story_m_ph1") in x for x in shown)
    assert not any(t("story_m_dome1") in x or t("story_m_gate2") in x for x in shown)


def test_the_act_1_map_still_says_chapter_1(run):
    from i18n import t
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    hub = _hub(st)
    hub.pane = "map"
    shown = _texts(hub, run)
    assert t("story_ch1") in shown
    assert not any(t("story_m_ph1") in x for x in shown)


def test_the_map_cursor_walks_the_act_2_list_only():
    hub = _hub(_act2())
    hub.pane = "map"
    for _ in range(30):
        hub.nav_v(1)
    assert hub._mission()["id"] == "paint_3" and hub.map_index == len(HUNTS + PHENIX + PAINT) - 1


def test_winning_the_gate_puts_the_cursor_on_the_new_map():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["flags"]["dome_s5"] = True
    hub = _hub(st)
    hub.map_index = [m["id"] for m in hub.missions()].index("act2_gate")
    hub.apply_result("act2_gate", 100, True)
    from i18n import t
    assert hub.state["act"] == 2 and hub.map_index == 0 and hub.toast == t("story_act_start").format(n=2)
    assert _ids(hub.missions()) == HUNTS + PHENIX + PAINT


def test_the_gift_toast_after_the_fifth_mission():
    from i18n import t
    st = _act2()
    for mid in PHENIX[:4]:
        _win(st, mid)
    hub = _hub(st)
    hub.apply_result("phenix_5", 100, True)
    assert hub.toast == t("story_phenix_gift") and hub.state["slots"][1]["owned"]


def test_the_cheat_keeps_the_focused_mission(run):
    from types import SimpleNamespace
    hub = _hub(_act2())
    hub.pane = "map"
    hub.map_index = [m["id"] for m in hub.missions()].index("phenix_2")
    for ch in "UNLK":
        hub.type_key(SimpleNamespace(key=ord(ch.lower()), unicode=ch))
    assert hub.cheat_unlock and hub._mission()["id"] == "phenix_2"
    assert len(hub.missions()) == len(ss.MISSIONS)


def test_the_hangar_switches_to_the_phenix_with_its_own_rows_and_stats(run):
    from i18n import t
    hub = _hub(_with_phenix())
    hub.state["selected_slot"] = 0
    hub.pane = "hangar"
    hub.zone = "slots"
    hub.nav_h(1)
    assert hub.state["selected_slot"] == 1
    assert [r[0] for r in hub.shop_rows()] == ["speed_80", "lives_2", "wall_slow", "phenix_cap_80"]
    shown = _texts(hub, run)
    assert t("story_stat_phenix") in shown and "60%" in shown
    assert any(t("story_shop_phenix80") in x for x in shown) and t("story_stat_dome") not in shown
    hub.nav_v(1)
    for _ in range(10):
        hub.nav_v(1)
    assert hub.shop_index == 3                                           # four rows, the cursor stops on the last
    hub.confirm()
    assert ss.phenix_cap(hub.state["slots"][1]) == 80
    hub.zone = "slots"
    hub.nav_h(-1)
    assert hub.state["selected_slot"] == 0 and len(hub.shop_rows()) == 6


def test_the_phenix_slot_stays_empty_before_the_gift(run):
    hub = _hub(_act2())
    hub.pane = "hangar"
    hub.zone = "slots"
    hub.nav_h(1)
    assert hub.state["selected_slot"] == 0


# ------------------------------------------------------------------ in the game
def _launch(g, st, mission_id):
    for earlier in PHENIX[:PHENIX.index(mission_id)] if mission_id in PHENIX else []:
        _win(st, earlier)                                                # the series is chained
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = _ids(g.story.missions()).index(mission_id)
    spec = g.story._launch_selected()
    assert spec, mission_id
    g._begin_adventure(spec)
    return spec


def test_the_first_phenix_mission_flies_level_16_at_1_3(run):
    g = run.game
    spec = _launch(g, _act2(), "phenix_1")
    assert spec["waves"] == [16, 17] and g.stage == 16
    assert {e.stage for e in g.formation.enemies} == {1}
    assert {round(e.speed_mult, 6) for e in g.formation.enemies} == {round(1.3 * g.difficulty_speed_mult(), 6)}


def test_the_second_phenix_mission_is_the_swarm_at_level_16(run):
    g = run.game
    spec = _launch(g, _act2(), "phenix_2")
    assert spec["swarm"] and spec["stage"] == 16 and g.stage == 16 and g.formation.swarm is not None
    assert {round(e.speed_mult, 6) for e in g.formation.enemies} == {round(1.3 * g.difficulty_speed_mult(), 6)}


def test_the_last_phenix_mission_ends_on_the_boss(run):
    g = run.game
    spec = _launch(g, _act2(), "phenix_5")
    assert spec["waves"] == [16, 17, 18, 19, 20]
    g.adventure["wave_i"] = 4
    g._setup_stage(1)
    assert g.stage == 20 and g.boss_saucer is not None


def test_a_won_phenix_mission_comes_back_through_the_game(run):
    g = run.game
    st = _act2()
    _launch(g, st, "phenix_1")
    g.score = 400
    g._end_adventure(True)
    assert "phenix_1" in g.story.state["cleared"] and ss.flag(g.story.state, "phenix_s1")


def test_the_phenix_flies_with_its_own_hull_and_a_shorter_form(run):
    g = run.game
    st = _with_phenix()
    _launch(g, st, "ch1_sortie")
    assert g.player.ship_id == "phoenix"
    assert g.player.phenix_sec_per_point == pytest.approx(0.6 * 0.6)
    assert g.player.lives == 1
    ss.buy(st, "phenix_cap_80")
    _launch(g, st, "ch1_sortie")
    assert g.player.phenix_sec_per_point == pytest.approx(0.6 * 0.8)


def test_the_shield_keeps_the_full_arcade_timing(run):
    g = run.game
    st = _with_phenix()
    st["selected_slot"] = 0
    _launch(g, st, "ch1_sortie")
    assert g.player.ship_id == "shield" and g.player.phenix_sec_per_point == pytest.approx(0.6)
