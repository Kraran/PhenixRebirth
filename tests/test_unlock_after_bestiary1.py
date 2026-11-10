"""Ceinture I and Sentinelle I open once Bestiaire I - Première sortie is won; they are no longer available from the start."""
import story_state as ss

SIDES = ("ast_1", "sentinelle_1")


def _fresh():
    return ss.create_slot(1, "NOVA", "normal")


def test_a_fresh_save_keeps_the_belt_and_sentinelle_locked():
    st = _fresh()
    assert ss.mission_playable(st, ss.mission_by_id("ch1_sortie"))
    for mid in SIDES:
        m = ss.mission_by_id(mid)
        assert m in ss.visible_missions(st)
        assert not ss.mission_open(st, m) and not ss.mission_playable(st, m)
        assert ss.unlock_hint(st, m)["id"] == "ch1_sortie"
    assert not ss.flag(st, ss.CH1_SIDES)
    assert ss.mission_by_id("sentinelle_2") not in ss.visible_missions(st)


def test_winning_the_first_sortie_opens_them():
    st = _fresh()
    ss.record_result(st, "ch1_sortie", 100, True)
    assert ss.flag(st, ss.CH1_SIDES) and ss.flag(st, "ch1_sortie")
    for mid in SIDES:
        assert ss.mission_playable(st, ss.mission_by_id(mid)), mid
        assert ss.unlock_hint(st, ss.mission_by_id(mid)) is None
    assert ss.mission_by_id("sentinelle_2") not in ss.visible_missions(st)
    assert not ss.mission_playable(st, ss.mission_by_id("sentinelle_2"))


def test_the_sentinelle_chain_still_opens_in_order_after_the_first_sortie():
    st = _fresh()
    st["act"] = 2
    ss.record_result(st, "ch1_sortie", 100, True)
    assert ss.mission_playable(st, ss.mission_by_id("sentinelle_1"))
    assert not ss.mission_playable(st, ss.mission_by_id("sentinelle_2"))
    ss.record_result(st, "sentinelle_1", 100, True)
    assert ss.mission_playable(st, ss.mission_by_id("sentinelle_2"))
    assert not ss.mission_playable(st, ss.mission_by_id("sentinelle_3"))
    ss.record_result(st, "sentinelle_2", 100, True)
    assert ss.mission_playable(st, ss.mission_by_id("sentinelle_3"))


def test_an_old_save_that_already_won_the_first_sortie_sees_them_unlocked():
    data = ss.default_state()
    data["cleared"] = ["ch1_sortie"]
    data["flags"] = {"ch1_sortie": True, "ch1_speed": True}     # a save from before CH1_SIDES existed
    st = ss.migrate_state(data)
    assert ss.flag(st, ss.CH1_SIDES)
    for mid in SIDES:
        assert ss.mission_playable(st, ss.mission_by_id(mid)), mid


def test_an_old_save_that_already_won_the_belt_keeps_it():
    data = ss.default_state()
    data["cleared"] = ["ast_1"]
    data["flags"] = {"ast_s1": True}
    st = ss.migrate_state(data)
    assert ss.flag(st, ss.CH1_SIDES)
    assert ss.mission_playable(st, ss.mission_by_id("ast_1"))
    assert ss.mission_playable(st, ss.mission_by_id("sentinelle_1"))
    assert not ss.flag(st, "ch1_sortie") and not ss.mission_playable(st, ss.mission_by_id("best_s2"))


def test_an_old_save_that_already_won_sentinelle_1_keeps_it():
    data = ss.default_state()
    data["cleared"] = ["sentinelle_1"]
    data["flags"] = {"sentinelle_1": True}
    st = ss.migrate_state(data)
    assert ss.flag(st, ss.CH1_SIDES)
    assert ss.mission_open(st, ss.mission_by_id("sentinelle_1"))
    assert not ss.mission_playable(st, ss.mission_by_id("sentinelle_1"))   # flown once until the series is done
    assert ss.mission_playable(st, ss.mission_by_id("ast_1"))
    assert not ss.flag(st, "ch1_sortie")


def test_an_old_save_that_already_flew_them_keeps_them():
    data = ss.default_state()
    data["flags"] = {"scene_ast_1": True}                      # the briefing was told, the mission was started
    st = ss.migrate_state(data)
    assert ss.flag(st, ss.CH1_SIDES)
    assert ss.mission_playable(st, ss.mission_by_id("ast_1"))
    assert ss.mission_playable(st, ss.mission_by_id("sentinelle_1"))
    data = ss.default_state()
    data["flags"] = {"scene_sentinelle_1": True}
    st = ss.migrate_state(data)
    assert ss.mission_playable(st, ss.mission_by_id("sentinelle_1"))
    assert ss.mission_playable(st, ss.mission_by_id("ast_1"))


def test_an_old_save_that_never_touched_them_still_waits_for_the_sortie():
    data = ss.default_state()
    data["cleared"] = []
    st = ss.migrate_state(data)
    assert not ss.flag(st, ss.CH1_SIDES)
    for mid in SIDES:
        assert not ss.mission_playable(st, ss.mission_by_id(mid)), mid
    assert ss.mission_playable(st, ss.mission_by_id("ch1_sortie"))
