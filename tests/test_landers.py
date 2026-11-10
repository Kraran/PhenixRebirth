"""Atterrissages: the five landing missions of the Adventure (story_state.MISSIONS "lander_*"), the Lunar Lander on one
setting each with its own tank."""

import pygame

import lander
import lander_view as lv
import story_state as ss
from test_smoke import run  # noqa: F401,F811  (fixture)

WANT = {"lander_deimos": ("deimos", 90, (1, 2, 3), "raid_deimos"), "lander_rock": ("rock", 80, (1, 2, 3), "raid_rock"),
        "lander_europa": ("europa", 70, (2, 3), "raid_europa"), "lander_titan": ("ice", 70, (2, 3), "raid_titan"),
        "lander_triton": ("triton", 60, (3,), "raid_triton")}


def test_the_five_landings_are_on_the_maps_of_their_acts_before_their_raids():
    ids = [m["id"] for m in ss.MISSIONS]
    for mid, (body, fuel, acts, raid) in WANT.items():
        m, r = ss.mission_by_id(mid), ss.mission_by_id(raid)
        assert m["lander"] and m["body"] == body and m["body"] in lander.BODIES and m["fuel"] == fuel
        assert tuple(m["acts"]) == acts and m["once"] and m["extra"] and not m.get("secret")
        assert ss.mission_group(m) == ss.GROUP_EXTRA
        assert m["need"] == r["need"] and m["acts"] == r["acts"] and r["body"] == body
        assert ids.index(mid) + 1 == ids.index(raid)                   # (side by side on the map)
    st = ss.create_slot(1, "NOVA", "normal")
    m = ss.mission_by_id("lander_deimos")
    assert not ss.mission_open(st, m)
    st["flags"][m["need"]] = True
    assert ss.mission_playable(st, m) and ss.next_mission(st, [m]) is None


def test_the_tank_holds_what_the_mission_gives():
    assert lander.LanderFormation("deimos", 3).fuel == lander.FUEL_START == 90.0
    f = lander.LanderFormation("deimos", 3, fuel=80)
    assert f.fuel == f.fuel_max == 80.0


def _gauge_fill(surf):
    """The width of the green fill of the fuel gauge: the longest run of its green on one row (the bar is 10 px high)."""
    green = (90, 255, 120)
    best = 0
    for y in range(surf.get_height()):
        run_len = 0
        for x in range(surf.get_width()):
            run_len = run_len + 1 if surf.get_at((x, y))[:3] == green else 0
            best = max(best, run_len)
    return best


def test_the_gauge_is_full_with_a_full_tank(run):
    g = run.game
    from test_spacewar import _state
    st = _state()
    st["flags"]["dome_s2"] = True
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index("lander_deimos")
    g._begin_adventure(g.story._launch_selected())
    g.input_grace = 0.0
    run.frames(2)
    form = g.formation
    seen = []
    for fuel in (90.0, 45.0):
        form.fuel = fuel
        surf = pygame.Surface(g.game_surface.get_size())
        surf.fill((0, 0, 0))
        g.game_surface, keep = surf, g.game_surface
        try:
            lv.draw_hud(g, form)
        finally:
            g.game_surface = keep
        seen.append(_gauge_fill(surf))
    assert seen[0] > 50 and abs(seen[1] / seen[0] - 0.5) < 0.03


def test_a_landing_launches_its_setting_and_its_tank_without_a_menu(run):
    g = run.game
    from test_spacewar import _state
    st = _state(act=2)
    st["flags"].update({"dome_s2": True, "dome_s4": True, "phenix_s1": True, "phenix_s3": True})
    for mid in WANT:
        ss.mark_scene_seen(st, mid)                               # (the briefing told before: tests/test_modules_scenes.py)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.pane = "map"
    g.story.screen = "hub"
    ids = [m["id"] for m in g.story.missions()]
    assert all(m in ids for m in list(WANT)[:4]) and "lander_triton" not in ids
    for mid in ("lander_rock", "lander_titan"):
        body, fuel, _, _ = WANT[mid]
        g.story.screen = "hub"
        g.story.map_index = ids.index(mid)
        spec = g.story.confirm()
        assert spec and spec["lander"] and spec["body"] == body and spec["fuel"] == fuel
        assert g.story.screen != "lander_pick"
    g._begin_adventure(spec)
    run.frames(2)
    form = g.formation
    assert isinstance(form, lander.LanderFormation) and form.style == "ice" and form.fuel_max == 70.0


def test_the_bonus_keep_their_menu_and_their_tank(run):
    g = run.game
    from test_spacewar import _open_bonus, _state
    ss.save_state(ss.story_path(1), _open_bonus(_state(), "bonus_lander"))
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index("bonus_lander")
    g.story.lander_index = 2
    g.story.screen = "lander_pick"
    g.story.pick_for = "lander"
    spec = g.story.confirm()
    assert spec["fuel"] == 90 and spec["body"] == lander.MENU_ORDER[2]
    g._begin_adventure(spec)
    run.frames(2)
    assert g.formation.fuel_max == lander.FUEL_START


def test_a_landing_pays_its_points_once_and_a_crash_costs():
    from test_spacewar import _state
    st = _state()
    st["flags"]["dome_s2"] = True
    st["credits"] = 1000
    m = ss.mission_by_id("lander_deimos")
    res = ss.record_result(st, "lander_deimos", 0, False)
    assert res["lost"] > 0 and st["credits"] < 1000 and ss.mission_playable(st, m)
    before = st["credits"]
    res = ss.record_result(st, "lander_deimos", 2750, True)
    assert res["cleared"] and st["credits"] == before + 2750
    assert not ss.mission_playable(st, m)
    st["flags"][ss.ENDING_DONE] = True
    assert ss.mission_playable(st, m)
