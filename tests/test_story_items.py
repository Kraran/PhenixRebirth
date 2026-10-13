"""The loot items of the Adventure, rules and save (story_items.py, story_state.py): no window needed.

One item lives like this in an Act: lootable -> found (on sale in the hangar) -> installed (bought) -> used (the mission
that followed is over). Only one copy at a time, never twice in an Act, a new Act gives them all back, and loot is rare:
at most one mission in three.
"""
import random

import pytest

import story_items as si
import story_state as ss


def _state(credits=0, act=1):
    st = ss.default_state()
    st["credits"] = credits
    st["act"] = act
    return st


def test_the_four_items_and_their_prices():
    assert si.RANDOM_IDS == ("singularity", "genesis", "hyperion", "tesla")
    assert si.PRICES == {"singularity": 6000, "genesis": 6000, "hyperion": 4000, "tesla": 2000,
                         "reactor_shield": 2000, "reactor_phenix": 4000}


def test_a_new_pilot_has_every_item_to_find():
    st = _state()
    assert si.lootable(st) == list(si.RANDOM_IDS)
    assert si.shop(st) == [] and si.installed(st) == []


def test_a_caught_item_goes_on_sale_and_is_not_lootable_any_more():
    st = _state()
    assert si.find(st, "hyperion") is True
    assert si.status(st, "hyperion") == "found"
    assert si.shop(st) == ["hyperion"]
    assert "hyperion" not in si.lootable(st)


def test_only_one_copy_of_an_item_is_ever_caught():
    st = _state()
    assert si.find(st, "tesla") is True
    assert si.find(st, "tesla") is False                      # already held
    st["credits"] = 99999
    si.buy(st, "tesla")
    assert si.find(st, "tesla") is False                      # installed
    si.consume(st, ["tesla"])
    assert si.find(st, "tesla") is False                      # used: not again in this Act
    assert si.status(st, "tesla") == "used"


def test_an_unknown_item_is_never_caught():
    st = _state()
    assert si.find(st, "nope") is False and si.shop(st) == []


def test_buying_needs_the_item_and_the_credits():
    st = _state(credits=5999)
    assert si.buy(st, "genesis") is False                     # not found yet
    si.find(st, "genesis")
    assert si.buy(st, "genesis") is False                     # 5999 < 6000
    assert st["credits"] == 5999 and si.status(st, "genesis") == "found"
    st["credits"] = 6000
    assert si.buy(st, "genesis") is True
    assert st["credits"] == 0 and si.status(st, "genesis") == "installed"
    assert si.installed(st) == ["genesis"]


@pytest.mark.parametrize("item", si.RANDOM_IDS)
def test_each_item_costs_its_price(item):
    st = _state(credits=10000)
    si.find(st, item)
    assert si.buy(st, item)
    assert st["credits"] == 10000 - si.PRICES[item]


def test_an_installed_item_cannot_be_bought_again():
    st = _state(credits=20000)
    si.find(st, "tesla")
    assert si.buy(st, "tesla") and not si.buy(st, "tesla")
    assert st["credits"] == 18000


def test_the_mission_uses_up_the_installed_items_only():
    st = _state(credits=20000)
    for i in ("singularity", "tesla", "hyperion"):
        si.find(st, i)
    si.buy(st, "singularity")
    si.buy(st, "tesla")                                       # hyperion stays on the shelf
    assert si.consume(st, ["singularity", "tesla", "hyperion"]) == ["singularity", "tesla"]
    assert si.status(st, "singularity") == si.status(st, "tesla") == "used"
    assert si.status(st, "hyperion") == "found"
    assert si.shop(st) == ["hyperion"]                        # the used ones are gone from the shop
    assert si.installed(st) == []


def test_consuming_nothing_changes_nothing():
    st = _state(credits=20000)
    si.find(st, "tesla")
    si.buy(st, "tesla")
    assert si.consume(st, None) == [] and si.consume(st, []) == []
    assert si.installed(st) == ["tesla"]


def test_a_new_act_gives_every_item_back():
    st = _state(credits=20000)
    for i in si.RANDOM_IDS:
        si.find(st, i)
    si.buy(st, "tesla")
    si.consume(st, ["tesla"])
    st["act"] = 2
    assert si.lootable(st) == list(si.RANDOM_IDS)
    assert si.shop(st) == [] and si.installed(st) == []
    assert si.find(st, "tesla") is True                       # and it can be caught again, once, in Act 2


def test_an_installed_item_does_not_survive_into_the_next_act():
    st = _state(credits=20000)
    si.find(st, "tesla")
    si.buy(st, "tesla")
    st["act"] = 2
    assert si.installed(st) == []


def test_the_effects():
    none = si.effects([])
    assert none == {"fire_mult": 1.0, "extra_lives": 0, "speed_mult": 1.0, "electric_immune": False}
    assert si.effects(["singularity"])["fire_mult"] == 2.0
    assert si.effects(["genesis"])["extra_lives"] == 1
    assert si.effects(["hyperion"])["speed_mult"] == pytest.approx(1.4)
    assert si.effects(["tesla"])["electric_immune"] is True
    both = si.effects(list(si.RANDOM_IDS))
    assert both == {"fire_mult": 2.0, "extra_lives": 1, "speed_mult": 1.4, "electric_immune": True}


# ---------------------------------------------------------------- how often an item falls
def _missions(n, seed=1, state=None, take=False):
    """Fly n missions; `take` catches every item that falls (and keeps the pool full by starting a new Act)."""
    rng = random.Random(seed)
    st = state or _state()
    out = []
    for _ in range(n):
        plan = si.plan_drop(st, rng)
        out.append(plan)
        if plan and take:
            st["act"] += 1                                    # a fresh pool each time: the worst case for the rate
    return out


def test_loot_is_rare_never_two_missions_in_three():
    for seed in range(40):
        plans = _missions(300, seed=seed, take=True)
        hits = [i for i, p in enumerate(plans) if p]
        assert hits, "an item should fall now and then"
        assert all(b - a >= 3 for a, b in zip(hits, hits[1:])), (seed, hits[:10])      # one mission in three at most
        assert len(hits) < len(plans) / 3                      # and in fact fewer


def test_loot_does_fall_sometimes():
    plans = _missions(400, take=True)
    rate = sum(1 for p in plans if p) / len(plans)
    assert 0.15 < rate < 0.26, rate


def test_nothing_falls_when_every_item_is_held_or_used():
    st = _state(credits=99999)
    for i in si.RANDOM_IDS:
        si.find(st, i)
    assert not any(_missions(200, state=st))


def test_an_item_held_never_falls_again_in_the_act():
    st = _state()
    si.find(st, "tesla")
    si.find(st, "genesis")
    seen = {p["id"] for p in _missions(2000, seed=3, state=st) if p}
    assert seen <= {"singularity", "hyperion"} and seen


def test_every_lootable_item_can_fall():
    seen = {p["id"] for p in _missions(3000, seed=5, take=False) if p}
    assert seen == set(si.RANDOM_IDS)


def test_the_item_falls_some_time_into_the_mission():
    for p in (p for p in _missions(500, seed=2, take=True) if p):
        assert si.DROP_DELAY[0] <= p["t"] <= si.DROP_DELAY[1]


def test_the_first_mission_may_already_carry_an_item():
    rng = random.Random(0)
    rng.random = lambda: 0.0                                  # the luckiest dice
    assert si.plan_drop(_state(), rng) is not None


def test_an_item_that_fell_but_was_lost_may_fall_again():
    st = _state()
    plan = si.plan_drop(st, type("R", (), {"random": lambda s: 0.0, "choice": lambda s, p: p[0],
                                           "uniform": lambda s, a, b: a})())
    assert plan and si.status(st, plan["id"]) is None          # planning is not catching
    assert plan["id"] in si.lootable(st)


# ---------------------------------------------------------------- the save
def test_the_default_save_has_an_item_book():
    st = ss.default_state()
    assert st["items"]["got"] == {} and st["items"]["act"] == 1


def test_items_survive_a_save_and_a_load(tmp_path):
    st = _state(credits=7000)
    si.find(st, "tesla")
    si.find(st, "hyperion")
    si.buy(st, "tesla")
    path = str(tmp_path / "s.json")
    ss.save_state(path, st)
    back = ss.load_state(path)
    assert si.status(back, "tesla") == "installed" and si.status(back, "hyperion") == "found"
    assert back["credits"] == 5000


def test_an_old_save_without_items_loads_with_every_item_to_find():
    st = ss.default_state()
    del st["items"]
    st = ss.migrate_state(st)
    assert si.lootable(st) == list(si.RANDOM_IDS)


@pytest.mark.parametrize("junk", [None, 5, "x", [], {"got": 3}, {"got": {"tesla": "bogus", "nope": "found", "genesis": 7}},
                                  {"act": "z", "since": None}])
def test_a_damaged_item_book_is_cleaned(junk):
    st = ss.default_state()
    st["items"] = junk
    st = ss.migrate_state(st)
    assert set(st["items"]["got"]) <= set(si.RANDOM_IDS)
    assert all(v in ("found", "installed", "used") for v in st["items"]["got"].values())
    assert si.lootable(st) is not None


def test_a_valid_state_of_the_book_is_kept_by_the_migration():
    st = ss.default_state()
    st["items"] = {"act": 1, "got": {"tesla": "installed", "genesis": "used", "nope": "found"}, "since": 1}
    st = ss.migrate_state(st)
    assert st["items"]["got"] == {"tesla": "installed", "genesis": "used"}


# ---------------------------------------------------------------- the workshop and the mission result
def test_the_workshop_lists_the_items_found_after_the_upgrades():
    st = _state()
    base = [r[0] for r in ss.shop_for(st)]
    si.find(st, "tesla")
    si.find(st, "singularity")
    rows = ss.shop_for(st)
    assert [r[0] for r in rows] == base + ["item:singularity", "item:tesla"]
    assert rows[-1] == ("item:tesla", "item_tesla_name", 2000, None)


def test_the_phenix_workshop_sells_them_too():
    st = _state()
    st["selected_slot"] = 1
    si.find(st, "genesis")
    assert ss.shop_for(st)[-1][0] == "item:genesis"


def test_a_used_item_leaves_the_workshop():
    st = _state(credits=9000)
    si.find(st, "tesla")
    ss.buy(st, "item:tesla")
    assert ss.shop_for(st)[-1][0] == "item:tesla"
    si.consume(st, ["tesla"])
    assert all(not r[0].startswith("item:") for r in ss.shop_for(st))


def test_item_rows_are_recognised():
    assert ss.item_of("item:tesla") == "tesla"
    assert ss.item_of("item:nope") is None and ss.item_of("speed_60") is None and ss.item_of(None) is None


def test_buying_a_workshop_row_of_an_item():
    st = _state(credits=2500)
    si.find(st, "tesla")
    assert ss.upgrade_note(st, "item:tesla") is None
    assert ss.buy(st, "item:tesla") is True
    assert st["credits"] == 500 and ss.upgrade_note(st, "item:tesla") == "story_item_installed"
    assert ss.buy(st, "item:tesla") is False
    assert ss.buy(st, "item:genesis") is False                # not caught


@pytest.mark.parametrize("cleared", [True, False])
def test_the_item_caught_goes_on_sale_win_or_lose(cleared):
    st = _state()
    res = ss.record_result(st, "ch1_sortie", 100, cleared, {}, loot="tesla")
    assert res["loot"] == "tesla" and si.status(st, "tesla") == "found"


def test_a_mission_without_loot_records_none():
    st = _state()
    res = ss.record_result(st, "ch1_sortie", 100, True, {})
    assert res["loot"] is None and res["used"] == [] and si.shop(st) == []


@pytest.mark.parametrize("cleared", [True, False])
def test_the_mission_uses_up_its_installed_items_win_or_lose(cleared):
    st = _state(credits=9000)
    si.find(st, "tesla")
    si.buy(st, "tesla")
    res = ss.record_result(st, "ch1_sortie", 100, cleared, {}, used=["tesla"])
    assert res["used"] == ["tesla"] and si.status(st, "tesla") == "used"


def test_a_veteran_who_falls_still_uses_the_items_up():
    st = _state(credits=9000)
    st["mode"] = "veteran"
    si.find(st, "tesla")
    si.buy(st, "tesla")
    res = ss.record_result(st, "ch1_sortie", 0, False, {}, loot="genesis", used=["tesla"])
    assert res["fallen"] and si.status(st, "tesla") == "used" and si.status(st, "genesis") == "found"


def test_an_item_caught_in_a_mission_that_ends_the_act_belongs_to_the_old_act():
    st = _state()
    mission = next(m for m in ss.MISSIONS if m.get("act") == 2 and m.get("playable") is not False)
    ss.record_result(st, mission["id"], 100, True, {}, loot="tesla")
    assert st["act"] == 2
    assert si.lootable(st) == list(si.RANDOM_IDS)               # the new Act starts clean
