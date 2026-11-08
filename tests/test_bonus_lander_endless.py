"""BONUS FINAL - Lunar Lander (lander.py `endless`): landing after landing until the fuel runs out. After a landing the level
starts again from the top on a new ground, with the fuel left plus 50 (perfect) or 25 (rough), and fewer big zones each
level; a crash, or a tank empty for more than 2 seconds, ends the run with the GAME OVER; its points pay, leaving it gains
nothing, one record per setting at the top of the screen."""
import math

import pytest

import lander as ld
import story_state as ss
from test_smoke import run  # noqa: F401  (fixture)

MID = "bonus_lander"


def _state(credits=1000):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    st["credits"] = credits
    ss.complete_ending(st)
    return st


def _launch(run, body="rock", credits=1000):
    g = run.game
    ss.save_state(ss.story_path(1), _state(credits))
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(MID)
    spec = g.story._launch_selected(body)
    g._begin_adventure(spec)
    g.input_grace = 0.0
    g.stage_transition = None
    return spec


def _land(run, g, result="perfect"):
    """Put the ship on the first zone, upright, slow enough for `result`, and let it touch down."""
    form = g.formation
    pad = form.terrain.pads[0]
    g.player.ast_angle = -math.pi / 2
    form.x, form.y = pad["x"], pad["y"] - ld.FOOT_Y - 3.0
    form.vx, form.vy = 0.0, (10.0 if result == "perfect" else 35.0)
    for _ in range(30):
        run.frames(1)
        if form.phase != "flying":
            break
    return pad


# ------------------------------------------------------------------ the zones of each level
@pytest.mark.parametrize("level, x1, x2, x5", [(1, 3, 1, 0), (2, 2, 1, 1), (3, 1, 1, 1), (4, 0, 3, 1), (5, 0, 2, 1),
                                               (6, 0, 1, 1), (7, 0, 0, 3), (8, 0, 0, 2), (9, 0, 0, 1), (20, 0, 0, 1)])
def test_the_zones_get_rarer_level_after_level(level, x1, x2, x5):
    kinds = ld.endless_pads(level)
    assert (kinds.count("x1"), kinds.count("x2"), kinds.count("x5")) == (x1, x2, x5)
    terrain = ld.Terrain("rock", seed=level, kinds=kinds)
    assert sorted(p["kind"] for p in terrain.pads) == sorted(kinds)      # (all of them fit on the ground)


def test_the_launch_is_endless_on_the_setting_chosen():
    from story import StoryHub
    ss.save_state(ss.story_path(1), _state())
    hub = StoryHub()
    hub.open_slot(1)
    hub.screen, hub.pane = "hub", "map"
    hub.map_index = [m["id"] for m in hub.missions()].index(MID)
    spec = hub._launch_selected("europa")
    assert spec["lander"] and spec["endless"] and spec["body"] == "europa" and spec["level"] == 1


# ------------------------------------------------------------------ in the game
@pytest.mark.parametrize("result, gain", [("perfect", 50.0), ("rough", 25.0)])
def test_a_landing_refuels_and_the_next_level_starts_from_the_top(run, result, gain):
    _launch(run)
    g = run.game
    form = g.formation
    said = []
    g._play_level_vo = lambda n: said.append(n)
    run.frames(2)
    form.fuel = 40.0
    _land(run, g, result)
    assert form.phase == "landed" and form.result == result
    assert form.fuel == pytest.approx(40.0 + gain, abs=0.5) and g.score > 0
    fuel = form.fuel
    old = form.terrain
    run.frames(int(ld.LAND_PAUSE * 60) + 3)
    assert form.level == 2 and form.phase == "flying" and form.terrain is not old and not form.won
    assert form.y == pytest.approx(ld.START_Y, abs=5) and form.fuel == pytest.approx(fuel, abs=0.5)
    assert sorted(p["kind"] for p in form.terrain.pads) == sorted(ld.endless_pads(2))
    assert g.adventure is not None and g.adventure["level"] == 2 and said == [2]


def test_a_crash_ends_the_run_with_game_over_pays_and_keeps_the_best_of_the_setting(run):
    _launch(run, body="ice", credits=1000)
    g = run.game
    form = g.formation
    run.frames(2)
    g.score = 4200
    g.player.ast_angle = 0.0                                             # (on its side)
    form.y = float(form.terrain.ground(form.x)) - ld.FOOT_Y - 2.0
    form.vy = 200.0
    seen = False
    for _ in range(60 * 20):
        run.frames(1)
        seen = seen or (g.game_over and g.hs_phase == "card")
        if g.adventure is None:
            break
    st = ss.load_state(ss.story_path(1))
    assert seen and g.adventure is None and not st.get("fallen")
    assert st["credits"] == 1000 + 4200
    assert ss.endless_best(st, MID + ":ice") == 4200 and ss.endless_best(st, MID + ":rock") == 0


def test_an_empty_tank_ends_the_run_after_2_seconds(run):
    _launch(run, credits=500)
    g = run.game
    form = g.formation
    run.frames(2)
    g.score = 300
    form.fuel = 0.0
    form.y = ld.CEILING                                                  # (high: no landing in time)
    form.vy = -50.0
    run.frames(int(ld.EMPTY_GRACE * 60) - 10)
    assert not form.over and g.adventure is not None                     # (time for a landing at the last moment)
    run.frames(20)
    assert form.over
    st = ss.load_state(ss.story_path(1))
    assert st["credits"] == 800 and ss.endless_best(st, MID + ":rock") == 300
    seen = False
    for _ in range(60 * 15):
        seen = seen or (g.game_over and g.hs_phase == "card")
        if g.adventure is None:
            break
        run.frames(1)
    assert seen and g.adventure is None


def test_a_landing_in_extremis_with_an_empty_tank_goes_on(run):
    _launch(run)
    g = run.game
    form = g.formation
    run.frames(2)
    form.fuel = 0.0
    run.frames(30)                                                       # (empty for half a second, then it lands)
    _land(run, g, "perfect")
    assert form.phase == "landed" and form.fuel == pytest.approx(50.0) and not form.over
    run.frames(int(ld.LAND_PAUSE * 60) + 3)
    assert form.level == 2 and not form.over and g.adventure is not None


def test_leaving_it_gains_nothing(run):
    _launch(run, credits=300)
    g = run.game
    run.frames(2)
    g.score = 900
    g._quit_to_menu()
    st = ss.load_state(ss.story_path(1))
    assert st["credits"] == 300 and ss.endless_best(st, MID + ":rock") == 0


def test_the_record_of_the_setting_is_shown_at_the_top(run, monkeypatch):
    import draw_frame
    import i18n
    _launch(run, body="deimos")
    g = run.game
    g.story.state[ss.ENDLESS_BEST] = {MID + ":deimos": 9000, MID + ":rock": 1}
    assert g.endless_key() == MID + ":deimos" and draw_frame.endless_record(g, g.adventure) == 9000
    asked = []
    real = i18n.t
    monkeypatch.setattr("draw_frame.t", lambda k, *a, **kw: (asked.append(k), real(k, *a, **kw))[1])
    run.frames(2)
    assert "story_ast_record" in asked


def test_the_records_of_the_settings_are_kept_in_the_save():
    st = _state()
    ss.record_result(st, MID, 700, True, best_key=MID + ":triton")
    ss.record_result(st, MID, 300, True, best_key=MID + ":triton")
    st[ss.ENDLESS_BEST]["nope:rock"] = 5
    clean = ss.migrate_state(st)
    assert ss.endless_best(clean, MID + ":triton") == 700 and "nope:rock" not in clean[ss.ENDLESS_BEST]
