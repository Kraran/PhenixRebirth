"""Adventure rules and save data (story_state.py): no window needed."""
import json
import os

import pytest

import story_state as ss
from i18n import t


def _state(**flags):
    st = ss.default_state()
    st["credits"] = 100000
    for name in ("ch1_speed", "ch1_life_2", "ch1_wall", "ch3_open", "dome_online"):
        st["flags"][name] = flags.get(name, True)
    return st


def _ship(st):
    return st["slots"][0]


def test_default_hangar_is_the_weak_shield():
    st = ss.default_state()
    lo = ss.loadout(st)
    assert lo["ship_id"] == "shield"
    assert (lo["lives"], lo["speed_pct"], lo["dome"]) == (1, 40, False)
    assert (lo["dome_dur"], lo["dome_cd"]) == (1.0, 5.0)
    assert lo["wall"] == "instant"
    assert st["version"] == ss.SAVE_VERSION
    assert st["mode"] == "normal" and st["act"] == 1


def test_locked_phoenix_falls_back_to_shield():
    st = ss.default_state()
    st["selected_slot"] = 1
    assert ss.loadout(st)["ship_id"] == "shield"


def test_act1_workshop_reaches_80_percent_two_lives_the_slow_wall_and_the_first_dome():
    st = _state()
    assert [row[0] for row in ss.SHOP] == ["speed_60", "speed_80", "lives_2", "wall_slow", "dome_on"]
    for sid, *_ in ss.SHOP:
        assert ss.buy(st, sid), sid
    lo = ss.loadout(st)
    assert (lo["lives"], lo["speed_pct"], lo["dome"], lo["wall"]) == (2, 80, True, "slow")
    caps = ss.act_caps(st)
    assert (caps["speed"], caps["lives"]) == (80, 2)
    # everything the Act 1 workshop sells is bought: nothing more to buy
    for sid, *_ in ss.SHOP:
        assert ss.buy(st, sid) is False
        assert ss.upgrade_note(st, sid) == "story_owned"
    # only the first dome step is sold in Act 1: the shortest dome, the longer ones come later
    assert (st["slots"][0]["dome"], st["slots"][0]["dome_dur"], st["slots"][0]["dome_cd"]) == (True, 1.0, 5.0)


def test_later_acts_upgrades_finish_the_ship():
    st = _state()
    for sid in ("speed_60", "speed_80", "lives_2", "wall_slow", "speed_100", "lives_3",
                "dome_dur", "dome_dur", "dome_dur", "dome_lat", "dome_lat", "wall_immune"):
        assert ss.buy(st, sid), sid
    lo = ss.loadout(st)
    assert (lo["lives"], lo["speed_pct"], lo["dome"]) == (3, 100, True)
    assert (lo["dome_dur"], lo["dome_cd"], lo["wall"]) == (2.0, 3.0, "immune")


def test_dome_steps_are_half_second_and_one_second():
    st = _state()
    assert ss.buy(st, "dome_dur")
    assert (_ship(st)["dome"], _ship(st)["dome_dur"]) == (True, 1.0)
    assert ss.buy(st, "dome_dur") and _ship(st)["dome_dur"] == 1.5
    assert ss.buy(st, "dome_lat") and _ship(st)["dome_cd"] == 4.0


def test_buy_needs_flag_credits_and_order():
    st = _state(ch1_speed=False)
    assert ss.upgrade_note(st, "speed_60") == "story_locked"
    assert ss.buy(st, "speed_60") is False
    st = _state()
    assert ss.upgrade_note(st, "speed_80") == "story_need_prev"
    assert ss.buy(st, "speed_80") is False             # 60 % first
    assert ss.upgrade_note(st, "speed_100") == "story_need_prev"
    assert ss.upgrade_note(st, "lives_3") == "story_need_prev"
    assert ss.upgrade_note(st, "dome_lat") == "story_need_dome"
    assert ss.upgrade_note(st, "wall_slow") is None    # no dome needed any more
    assert ss.upgrade_note(st, "wall_immune") == "story_need_prev"
    st["credits"] = 299
    assert ss.buy(st, "speed_60") is False and st["credits"] == 299
    st["credits"] = 300
    assert ss.buy(st, "speed_60") is True and st["credits"] == 0
    assert ss.buy(st, "no_such_upgrade") is False


def test_each_act1_upgrade_waits_for_its_story_flag():
    for sid, flag_name in (("speed_60", "ch1_speed"), ("lives_2", "ch1_life_2"), ("wall_slow", "ch1_wall")):
        st = _state(**{flag_name: False})
        assert ss.upgrade_note(st, sid) == "story_locked"
        assert ss.buy(st, sid) is False


def test_the_wall_upgrade_only_goes_instant_then_slow():
    st = _state()
    assert _ship(st)["wall"] == "instant"
    assert ss.buy(st, "wall_slow") and _ship(st)["wall"] == "slow"
    assert ss.buy(st, "wall_slow") is False
    assert ss.buy(st, "wall_immune") and _ship(st)["wall"] == "immune"


def test_buy_refuses_a_hull_that_is_not_owned():
    st = _state()
    st["selected_slot"] = 1                              # Phoenix, locked
    assert ss.buy(st, "speed_60") is False


def test_note_price_row_has_no_note():
    st = _state()
    assert ss.upgrade_note(st, "speed_60") is None


def test_clear_banks_points_and_unlocks():
    st = ss.default_state()
    res = ss.record_result(st, "ch1_sortie", 100, True)
    assert res["first"] is True and res["lost"] == 0 and res["fallen"] is False
    assert st["credits"] == 100
    assert ss.flag(st, "ch1_speed") and st["cleared"] == ["ch1_sortie"]
    # clearing again: points, but no second journal line
    assert ss.record_result(st, "ch1_sortie", 10, True)["first"] is False
    assert st["credits"] == 110 and len(st["log"]) == 1


def test_failure_in_normal_mode_gains_nothing_and_loses_20_percent():
    st = ss.default_state()
    st["credits"] = 500
    res = ss.record_result(st, "ch1_sortie", 60, False)
    assert res["cleared"] is False and res["lost"] == 100 and res["fallen"] is False
    assert st["credits"] == 400                           # the 60 points are not banked
    assert not ss.flag(st, "ch1_speed") and st["cleared"] == [] and st["log"] == []


def test_penalty_is_a_fifth_of_the_credits():
    assert [ss.failure_penalty(c) for c in (0, 1, 2, 3, 10, 100, 1250, 999)] == [0, 0, 0, 1, 2, 20, 250, 200]
    assert ss.failure_penalty(None) == 0 and ss.failure_penalty(-50) == 0


def test_the_score_of_a_failed_run_does_not_change_the_penalty():
    a, b = ss.default_state(), ss.default_state()
    a["credits"] = b["credits"] = 1000
    ss.record_result(a, "ch1_sortie", 0, False)
    ss.record_result(b, "ch1_sortie", 9999, False)
    assert a["credits"] == b["credits"] == 800


def test_credits_never_go_below_zero():
    st = ss.default_state()
    st["credits"] = 4
    for _ in range(6):
        ss.record_result(st, "ch1_sortie", 0, False)
    assert st["credits"] >= 0
    st["credits"] = 0
    res = ss.record_result(st, "ch1_sortie", 0, False)
    assert res["lost"] == 0 and st["credits"] == 0


def test_failure_in_veteran_mode_is_a_permanent_death():
    st = ss.default_state()
    st["mode"] = "veteran"
    st["credits"] = 500
    res = ss.record_result(st, "ch1_sortie", 100, False)
    assert res["fallen"] is True and res["lost"] == 0
    assert st["fallen"] is True and st["credits"] == 500   # nothing banked, nothing paid
    # a veteran who clears the mission lives on
    live = ss.default_state()
    live["mode"] = "veteran"
    ss.record_result(live, "ch1_sortie", 100, True)
    assert live["fallen"] is False


def test_journal_stores_a_key_and_follows_the_language():
    st = ss.default_state()
    ss.record_result(st, "ch1_sortie", 0, True)
    entry = st["log"][0]
    assert entry == {"key": "story_log_sortie"}
    assert ss.log_text(entry, t) == t("story_log_sortie")
    assert ss.log_text("old plain text", t) == "old plain text"   # lines saved before v3


def test_missions_open_and_playable():
    st = ss.default_state()
    by_id = {m["id"]: m for m in ss.MISSIONS}
    assert ss.mission_playable(st, by_id["ch1_sortie"])
    assert not ss.mission_open(st, by_id["best_s2"])
    ss.record_result(st, "ch1_sortie", 0, True)
    assert ss.mission_playable(st, by_id["best_s2"])
    st["flags"]["act2"] = True                           # the end of Act 1 opens the teaser
    assert ss.mission_open(st, by_id["ch2_tease"])
    assert not ss.mission_playable(st, by_id["ch2_tease"])
    assert not ss.mission_open(st, None)


# ---------------------------------------------------------------- save files
def test_v2_save_is_migrated_to_seconds_then_to_the_act1_hangar():
    v2 = {
        "version": 2, "chapter": 1, "credits": 777,
        "flags": {"bestiary_s1": True, "ch1_speed_80": True},
        "cleared": ["ch1_sortie"], "log": ["old line"], "selected_slot": 0,
        "slots": [{"id": "shield", "owned": True, "lives": 3, "speed": 80, "dome": True,
                   "dome_dur": 90, "dome_cd": 240, "wall": "immune"}],
    }
    st = ss.migrate_state(v2)
    assert st["version"] == ss.SAVE_VERSION and st["act"] == 1 and st["mode"] == "normal"
    assert st["credits"] == 777 and st["cleared"] == ["ch1_sortie"] and st["log"] == ["old line"]
    ship = _ship(st)
    # speed ladder 60/80/100 -> 40/60/80, lives stop at 2, the dome goes back offline
    assert (ship["speed"], ship["lives"], ship["wall"]) == (60, 2, "slow")
    assert (ship["dome"], ship["dome_dur"], ship["dome_cd"]) == (False, 1.0, 5.0)
    assert len(st["slots"]) == 1                          # same merge rule as before
    assert ss.flag(st, "ch1_speed") and ss.flag(st, "bestiary_s1")
    assert "ch1_speed_80" not in st["flags"]


def test_v3_save_moves_down_one_speed_step_and_keeps_the_wall_rule():
    def v3(speed, wall):
        return {"version": 3, "slots": [{"id": "shield", "owned": True, "speed": speed,
                                         "lives": 1, "wall": wall}]}
    assert [_ship(ss.migrate_state(v3(sp, "instant")))["speed"] for sp in (60, 80, 100)] == [40, 60, 80]
    assert _ship(ss.migrate_state(v3(60, "instant")))["wall"] == "instant"
    assert _ship(ss.migrate_state(v3(60, "slow")))["wall"] == "slow"


def test_v3_flags_become_act1_flags():
    st = ss.migrate_state({"version": 3, "flags": {"ch1_speed_80": True, "bestiary_s3": True,
                                                   "dome_online": True}})
    assert ss.flag(st, "ch1_speed") and ss.flag(st, "ch1_wall")
    assert not ss.flag(st, "dome_online")
    none = ss.migrate_state({"version": 3, "flags": {}})
    assert not ss.flag(none, "ch1_speed") and not ss.flag(none, "ch1_wall")


def test_v2_slot_without_dome_times_keeps_the_defaults():
    st = ss.migrate_state({"version": 2, "slots": [{"id": "shield", "owned": True, "speed": 80}]})
    assert _ship(st)["dome_dur"] == 1.0 and _ship(st)["dome_cd"] == 5.0
    st = ss.migrate_state({"version": 2})
    assert _ship(st)["dome_dur"] == 1.0 and _ship(st)["dome_cd"] == 5.0


def test_a_current_save_is_not_converted_twice():
    st = _state()
    ss.buy(st, "speed_60")
    ss.buy(st, "speed_80")
    st["slots"][0].update(dome=True, dome_dur=1.5, dome_cd=4.0)    # as the later dome quests will do
    again = ss.migrate_state(json.loads(json.dumps(st)))
    assert again["slots"][0]["speed"] == 80
    assert again["slots"][0]["dome"] is True
    assert again["slots"][0]["dome_dur"] == 1.5 and again["slots"][0]["dome_cd"] == 4.0
    assert ss.flag(again, "ch1_speed")


def test_migrate_ignores_garbage():
    assert ss.migrate_state([1, 2]) is None
    st = ss.migrate_state({"mode": "godlike", "name": 12, "flags": "x", "slots": "no",
                           "cleared": 3, "log": None})
    assert st["mode"] == "normal" and st["name"] == "" and st["slots"] == ss.default_state()["slots"]


def test_damaged_numbers_do_not_crash_the_loadout():
    st = ss.default_state()
    st["slots"][0].update(lives="abc", speed=None, dome_dur="x", dome_cd=[], dome=True)
    lo = ss.loadout(st)
    assert (lo["lives"], lo["speed_pct"], lo["dome_dur"], lo["dome_cd"]) == (1, 40, 1.0, 5.0)


def test_save_and_load_roundtrip(tmp_path):
    path = str(tmp_path / "story_2.json")
    st = _state()
    st["name"] = "NOVA"
    ss.buy(st, "dome_dur")
    ss.save_state(path, st)
    back = ss.load_state(path)
    assert back["name"] == "NOVA" and back["slots"][0]["dome"] is True
    assert back["credits"] == st["credits"] and back["saved_at"]


def test_missing_and_corrupt_files(tmp_path):
    assert ss.load_state(str(tmp_path / "nope.json")) is None
    bad = tmp_path / "story_1.json"
    bad.write_text("{not json", encoding="utf-8")
    assert ss.load_state(str(bad)) is None
    assert (tmp_path / "story_1.json.corrupt").read_text(encoding="utf-8") == "{not json"


def test_each_slot_has_its_own_file():
    paths = {ss.story_path(i) for i in range(1, ss.SLOT_COUNT + 1)}
    assert len(paths) == 3
    assert all(os.path.basename(p) == "story_%d.json" % (i + 1) for i, p in enumerate(sorted(paths)))


def test_act1_workshop_prices():
    assert [(row[0], row[2]) for row in ss.SHOP] == [
        ("speed_60", 300), ("speed_80", 800), ("lives_2", 2000), ("wall_slow", 1000), ("dome_on", 800)]
