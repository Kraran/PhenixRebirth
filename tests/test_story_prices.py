"""The prices of the workshop: the Phenix pays more than the Shield for the steps they share, the Act 3 rows are
dear, and the second step of the dome costs more than the first."""
import pytest

import story_state as ss

FLAGS = ("ch1_speed", "ch1_life_2", "ch1_wall", "dome_online", "ch3_speed", "ch3_lives", "ch3_wall", "ch3_dome",
         "ch3_gauge")


def _state(hull="shield", act=2, credits=100000, mode="normal"):
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    if act >= 2:
        ss.grant_phenix(st)
        ss.record_result(st, "phenix_5", 100, True)
    if act >= 3:
        ss.record_result(st, "act3_gate", 100, True)
        assert ss.choose_act3_ship(st, "phoenix" if hull == "phenix" else hull)
    for name in FLAGS:
        st["flags"][name] = True
    st["selected_slot"] = 1 if hull == "phenix" else 0
    st["credits"] = credits
    return st


def _price(st, sid):
    return {r[0]: r[2] for r in ss.shop_for(st)}[sid]


def _spent(st, sid):
    before = st["credits"]
    assert ss.buy(st, sid), sid
    return before - st["credits"]


def test_the_phenix_workshop_of_act_2():
    st = _state("phenix", act=2)
    assert [(r[0], r[2]) for r in ss.shop_for(st)[:4]] == [
        ("speed_80", 2000), ("lives_2", 4000), ("wall_slow", 3000), ("phenix_cap_80", 3000)]


def test_the_shield_keeps_its_old_prices_in_act_1_and_2():
    for act in (1, 2):
        st = _state("shield", act=act)
        assert [(r[0], r[2]) for r in ss.shop_for(st) if r[0] != "paint"] == [
            ("speed_60", 300), ("speed_80", 800), ("lives_2", 2000), ("wall_slow", 1000), ("dome_on", 800)]
    assert ss.PAINT_COST == 500


def test_the_shield_workshop_of_act_3():
    st = _state("shield", act=3)
    prices = {r[0]: r[2] for r in ss.shop_for(st)}
    assert (prices["speed_100"], prices["lives_3"], prices["wall_immune"], prices["dome_dur"]) == (4000, 5000, 4000, 2000)


def test_the_phenix_workshop_of_act_3():
    st = _state("phenix", act=3)
    prices = {r[0]: r[2] for r in ss.shop_for(st)}
    assert prices["speed_100"] == 4000 and prices["lives_3"] == 5000 and prices["phenix_cap_100"] == 5000
    assert (prices["speed_80"], prices["lives_2"], prices["wall_slow"], prices["phenix_cap_80"]) == (2000, 4000, 3000, 3000)
    assert "wall_immune" not in prices and "dome_dur" not in prices


def test_the_phenix_pays_these_prices_all_the_way():
    st = _state("phenix", act=3)
    order = ["speed_80", "lives_2", "wall_slow", "phenix_cap_80", "speed_100", "lives_3", "phenix_cap_100"]
    assert [(sid, _price(st, sid), _spent(st, sid)) for sid in order] == [
        ("speed_80", 2000, 2000), ("lives_2", 4000, 4000), ("wall_slow", 3000, 3000), ("phenix_cap_80", 3000, 3000),
        ("speed_100", 4000, 4000), ("lives_3", 5000, 5000), ("phenix_cap_100", 5000, 5000)]


def test_the_shield_pays_these_prices_all_the_way():
    st = _state("shield", act=3)
    order = ["speed_60", "speed_80", "lives_2", "wall_slow", "dome_on", "speed_100", "lives_3", "wall_immune"]
    assert [(sid, _price(st, sid), _spent(st, sid)) for sid in order] == [
        ("speed_60", 300, 300), ("speed_80", 800, 800), ("lives_2", 2000, 2000), ("wall_slow", 1000, 1000),
        ("dome_on", 800, 800), ("speed_100", 4000, 4000), ("lives_3", 5000, 5000), ("wall_immune", 4000, 4000)]


def test_the_dome_costs_2000_then_3000():
    st = _state("shield", act=3)
    ss.buy(st, "dome_on")
    assert ss.selected_slot(st)["dome_dur"] == 1.0
    assert _price(st, "dome_dur") == 2000 and _spent(st, "dome_dur") == 2000
    assert ss.selected_slot(st)["dome_dur"] == 1.5
    assert _price(st, "dome_dur") == 3000 and _spent(st, "dome_dur") == 3000
    assert ss.selected_slot(st)["dome_dur"] == 2.0
    before = st["credits"]
    assert not ss.buy(st, "dome_dur") and st["credits"] == before            # MAX: nothing taken


def test_the_dome_bought_straight_from_the_act_3_row_costs_the_first_step():
    st = _state("shield", act=3)
    assert not ss.selected_slot(st).get("dome")
    assert _price(st, "dome_dur") == 2000 and _spent(st, "dome_dur") == 2000


def test_the_second_dome_step_needs_the_whole_3000():
    st = _state("shield", act=3)
    ss.buy(st, "dome_on")
    ss.buy(st, "dome_dur")
    st["credits"] = 2999
    assert not ss.buy(st, "dome_dur") and st["credits"] == 2999 and ss.selected_slot(st)["dome_dur"] == 1.5
    st["credits"] = 3000
    assert ss.buy(st, "dome_dur") and st["credits"] == 0


@pytest.mark.parametrize("hull,sid,price", [("phenix", "speed_80", 2000), ("phenix", "wall_slow", 3000),
                                            ("phenix", "lives_2", 4000), ("phenix", "phenix_cap_80", 3000),
                                            ("shield", "wall_slow", 1000)])
def test_one_credit_short_buys_nothing(hull, sid, price):
    st = _state(hull, act=2, credits=price - 1)
    assert not ss.buy(st, sid) and st["credits"] == price - 1
    st["credits"] = price
    assert ss.buy(st, sid) and st["credits"] == 0


def test_novice_pays_the_same_prices_for_the_renamed_rows():
    st = _state("phenix", act=3, mode="novice")
    prices = {r[0]: r[2] for r in ss.shop_for(st)}
    assert prices["lives_2"] == 4000 and prices["lives_3"] == 5000


def test_unknown_row_has_no_price():
    assert ss.upgrade_cost(None, "nope") == 0


def test_a_dome_that_is_off_or_odd_costs_the_first_step():
    st = _state("shield", act=3)
    slot = ss.selected_slot(st)
    slot["dome"], slot["dome_dur"] = False, 1.5                 # off: the purchase turns it on at 1 s, the first step
    assert _price(st, "dome_dur") == 2000
    slot["dome"], slot["dome_dur"] = True, 0.25                 # a damaged save: never below the first price
    assert _price(st, "dome_dur") == 2000
