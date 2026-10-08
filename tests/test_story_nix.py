"""NIX2 in the hangar (all the Phenix missions won, the Phenix unlocked) and the smaller Phenix swarm."""
from types import SimpleNamespace

import pytest

import story_state as ss
from enemy import EnemyFormation, SWARM_NORMAL_COUNT, SWARM_SCREENS
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

PHENIX = ["phenix_1", "phenix_2", "phenix_3", "phenix_4", "phenix_5"]


def _hub(act=1):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    if act == 2:
        ss.jump_to_act2(st)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


def _type(hub, text):
    return [hub.type_key(SimpleNamespace(key=ord(c.lower()), unicode=c)) for c in text]


def _file():
    with open(ss.story_path(1), "rb") as f:
        return f.read()


def test_nix2_in_the_hangar_wins_the_phenix_missions_and_gives_the_phenix():
    hub = _hub(act=2)
    hub.pane = "hangar"
    assert [s["owned"] for s in hub.state["slots"]] == [True, False]
    before = _file()
    _type(hub, "NIX2")
    st = hub.state
    assert all(m in st["cleared"] for m in PHENIX)
    assert st["slots"][1]["owned"] and st["slots"][1]["id"] == "phoenix"
    assert ss.flag(st, "phenix_s1") and ss.flag(st, "phenix_s4")
    assert hub.toast and hub.cheating
    hub.save()
    assert _file() == before                                          # nothing is saved


def test_nix2_from_act_1_also_opens_act_2():
    hub = _hub(act=1)
    hub.pane = "hangar"
    _type(hub, "nix2")
    assert hub.state["act"] == 2 and hub.state["slots"][1]["owned"]


def test_nix2_does_nothing_outside_the_hangar():
    hub = _hub(act=2)
    for pane in ("map", "log", "bestiary"):
        hub.pane = pane
        hub.cheat_buf = ""
        _type(hub, "NIX2")
    assert not hub.state["slots"][1]["owned"] and not hub.cheating


def test_the_map_codes_do_nothing_in_the_hangar():
    hub = _hub(act=1)
    hub.pane = "hangar"
    _type(hub, "2222")
    _type(hub, "UNLK")
    assert hub.state["act"] == 1 and not hub.cheating


def test_the_phenix_missions_cleared_by_nix2_stay_cleared_on_the_map():
    hub = _hub(act=2)
    hub.pane = "hangar"
    _type(hub, "NIX2")
    ids = [m["id"] for m in hub.missions()]
    assert all(not ss.mission_playable(hub.state, ss.mission_by_id(m)) for m in PHENIX)
    assert "paint_1" in ids


def test_the_phenix_swarm_is_smaller_than_the_dome_swarm(run):
    mission = ss.mission_by_id("phenix_2")
    assert mission["swarm_screens"] < SWARM_SCREENS
    f = EnemyFormation()
    f.spawn_swarm(1.0, screens=mission["swarm_screens"])
    totals = {k: f.swarm["reserve"][k] + f.swarm_on_screen(k) for k in (1, 2, 3, 4)}
    assert totals == {k: SWARM_NORMAL_COUNT[k] for k in (1, 2, 3, 4)}
    big = EnemyFormation()
    big.spawn_swarm(1.0)
    assert sum(f.swarm["reserve"].values()) < sum(big.swarm["reserve"].values()) / 2
    assert ss.mission_by_id("dome_5").get("swarm_screens") is None


def test_the_launch_of_the_phenix_swarm_carries_its_size(run):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    st["flags"]["phenix_s1"] = True
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index("phenix_2")
    spec = g.story._launch_selected()
    assert spec["swarm"] and spec["swarm_screens"] == 1.0
    g._begin_adventure(spec)
    assert g.formation.swarm_remaining() == sum(SWARM_NORMAL_COUNT.values())


def test_a_total_never_falls_under_what_is_on_screen():
    f = EnemyFormation()
    f.spawn_swarm(1.0, screens=0.01)
    assert all(f.swarm["reserve"][k] == 0 for k in (1, 2, 3, 4))
