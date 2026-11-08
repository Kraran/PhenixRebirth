"""A step bought in the workshop gives way to the next step of its line when the workshop sells it (a tester read
"Vies 2 MAX" beside "Vies 3", in Act 3, as "two lives at most")."""

import pytest

import story_state as ss


def _act3(hull, lives=2, speed=80, flags=()):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act3(st)
    ss.choose_act3_ship(st, hull)
    slot = ss.selected_slot(st)
    slot["lives"], slot["speed"] = lives, speed
    for f in flags:
        st["flags"][f] = True
    return st


def _ids(st):
    return [r[0] for r in ss.shop_for(st)]


@pytest.mark.parametrize("hull", ["shield", "phoenix"])
def test_act3_lists_one_lives_row(hull):
    ids = _ids(_act3(hull))                                          # (Vies 2 bought, Vies 3 locked)
    assert "lives_3" in ids and "lives_2" not in ids
    ids = _ids(_act3(hull, flags=("ch3_lives",)))                    # (Vies 3 for sale)
    assert "lives_3" in ids and "lives_2" not in ids
    st = _act3(hull, lives=3, flags=("ch3_lives",))                  # (Vies 3 bought: MAX)
    assert "lives_2" not in _ids(st) and ss.upgrade_note(st, "lives_3") == "story_owned"


def test_act3_speed_shows_only_the_last_step():
    ids = _ids(_act3("shield", speed=80))
    assert "speed_100" in ids and "speed_60" not in ids and "speed_80" not in ids


def test_a_step_not_bought_stays():
    ids = _ids(_act3("shield", lives=1, speed=40))
    assert {"lives_2", "lives_3", "speed_60", "speed_80", "speed_100"} <= set(ids)


def test_a_step_without_its_next_one_still_shows_max():
    st = ss.create_slot(1, "NOVA", "normal")                         # Act 1: no Vies 3, Vies 2 stays at MAX
    ss.mark_intro_seen(st)
    ss.selected_slot(st)["lives"] = 2
    st["flags"]["ch1_life_2"] = True
    assert "lives_2" in _ids(st) and ss.upgrade_note(st, "lives_2") == "story_owned"

