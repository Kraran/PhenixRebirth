"""Raid sur les bases avioïdes: the five levels of difficulty of the Scramble (scramble.LEVELS) and the five raid missions of
the Adventure (story_state.MISSIONS "raid_*")."""

import numpy as np
import pytest

import lander
import scramble as sc
import scramble_base as scb
import scramble_birds as sb
import scramble_view as sv
import story_state as ss
from test_smoke import run  # noqa: F401,F811  (fixture)
from test_scramble import _Game, _Pilot, _station_ahead

RAIDS = ("raid_deimos", "raid_rock", "raid_europa", "raid_titan", "raid_triton")


def _seconds(c):
    return c.brake_from / c.scroll + 2 * sc.BRAKE / c.scroll


# ---------------------------------------------------------------- the levels
def test_the_top_level_is_the_scramble_of_the_test():
    t = sc.Tune(sc.LEVEL_MAX)
    assert sc.Tune().level == sc.LEVEL_MAX == 5 and sc.Tune(None).level == 5
    assert [(k, s) for k, s, _ in t.sections] == [(k, s) for k, s, _ in sc.SECTIONS]
    assert t.scroll == sc.SCROLL and t.gap_min == sc.GAP_MIN and t.reload == sc.STATION_RELOAD
    assert t.stations == t.homing == t.comets == 1.0
    assert t.wave_gap == sb.WAVE_GAP and t.green == sb.GREEN_SHARE
    assert t.columns == scb.COLUMNS and t.turret_rows == scb.TURRET_ROWS
    assert t.bullets == scb.BULLET_MAX and t.boss_hp == scb.BOSS_HP
    c = sc.Course("rock", 7)
    assert c.tune.level == 5 and c.scroll == sc.SCROLL and c.gap_min == sc.GAP_MIN
    assert np.array_equal(c.floor, sc.Course("rock", 7, 5).floor)


def test_out_of_range_levels_are_clamped():
    assert sc.Tune(0).level == 5 and sc.Tune(-3).level == 1 and sc.Tune(9).level == 5 and sc.Tune(2).level == 2


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_every_level_keeps_its_passage_and_its_order(level):
    for style in ("deimos", "triton"):
        c = sc.Course(style, 11, level)
        half = int(np.ceil(sc.GAP_WINDOW / 2 / sc.STEP))
        for i in range(0, c.n, 3):
            a, b = max(0, i - half), min(c.n, i + half + 1)
            assert c.floor[a:b].min() - c.ceil[a:b].max() >= c.gap_min - 0.01, (style, level, i)
        keys = [k for k, _, _ in c.sections]
        assert keys == [k for k in sc.SECTION_KEYS if k in keys]       # (the order of the full course)
        assert keys[0] == "hills" and keys[-1] == "approach"
        assert c.section_at(c.stop - 10) == "approach"


def test_the_levels_get_harder_one_after_the_other():
    tunes = [sc.Tune(lv) for lv in range(1, 6)]
    for a, b in zip(tunes, tunes[1:]):
        assert a.scroll < b.scroll and a.gap_min > b.gap_min and a.reload > b.reload
        assert a.stations < b.stations and a.homing <= b.homing and a.comets <= b.comets
        assert a.wave_gap[0] > b.wave_gap[0] and a.green[1] < b.green[1]
        assert a.columns <= b.columns and len(a.turret_rows) <= len(b.turret_rows)
        assert a.bullets <= b.bullets and a.boss_hp <= b.boss_hp
        assert len(a.sections) <= len(b.sections)
    secs = [_seconds(sc.Course("rock", 3, lv)) for lv in range(1, 6)]
    assert secs == sorted(secs) and len(set(secs)) == 5
    assert 80 < secs[0] < 100 and 140 < secs[4] < 160             # (about 1:30 ... 2:30)
    assert tunes[0].keys == ("hills", "cavern", "approach") and "comets" not in tunes[1].keys
    assert "comets" in tunes[2].keys and "narrows" not in tunes[2].keys and "narrows" in tunes[3].keys
    assert tunes[0].homing == tunes[1].homing == 0.0 and tunes[0].comets == 0.0


def test_the_lower_levels_have_fewer_stations():
    counts = []
    for lv in (1, 3, 5):
        n = 0
        for seed in range(4):
            f = sc.ScrambleFormation("europa", seed, level=lv)
            n += len(f.stations) / (f.course.brake_from / 1000.0)     # (stations per 1000 px of the course)
        counts.append(n)
    assert counts[0] < counts[1] < counts[2]


def test_the_base_follows_the_level():
    for lv in range(1, 6):
        f = sc.ScrambleFormation("rock", 5, level=lv)
        t, base = f.tune, f.base
        assert f.tune is f.course.tune and t.level == lv
        assert base.columns == t.columns and len(base.bricks) == base.rows * t.columns
        assert {b.col for b in base.bricks} == set(range(t.columns))
        assert base.back == base.face + t.columns * scb.BRICK_W
        assert [tr.row for tr in base.turrets] == list(t.turret_rows)
        assert base.boss.hp == base.boss.max_hp == t.boss_hp
    assert sc.ScrambleFormation("rock", 5, level=1).base.boss.hp == 1


def test_the_boss_fires_no_more_than_its_level_allows():
    f = sc.ScrambleFormation("rock", 5, level=1)
    ship = _Pilot()
    ship.invulnerable = 1e9
    g = _Game(f, ship)
    base = f.base
    base.started = True
    peak = 0
    for _ in range(60 * 20):
        base.tick(g, 1 / 60, True)
        peak = max(peak, sum(1 for b in base.bullets if b.alive))
    assert 0 < peak <= 3


def test_the_scroll_runs_at_the_speed_of_the_level():
    f = sc.ScrambleFormation("deimos", 3, level=1)
    assert f.speed == 150.0
    cam = f.cam
    f.advance(1.0)
    assert abs(f.cam - cam - 150.0) < 1e-6 and f.speed_at(0.0) == 150.0
    t, last = 0.0, 150.0                                   # (the braking ends at the stop, from the speed of the level)
    f.cam = f.course.brake_from
    while f.cam < f.course.stop and t < 60:
        f.advance(1 / 60)
        t += 1 / 60
        assert f.speed <= last + 1e-9
        last = f.speed
    assert abs(t - 2 * sc.BRAKE / 150.0) < 0.1


def test_the_stations_of_the_low_levels_fire_straight_missiles_less_often():
    f = sc.ScrambleFormation("rock", 2, level=1)
    st = _station_ahead(f, "floor", 300.0)
    st.lead = 99.0
    ship = _Pilot()
    ship.invulnerable = 1e9
    g = _Game(f, ship)
    for _ in range(60 * 4):
        f.cam = st.x - sc.START_X - 300.0
        f.recentre(ship)
        sc.tick(g)
        if f.missiles:
            break
    assert f.missiles and not f.missiles[0].homing and st.reload == 3.6


def _slide(level):
    f = sc.ScrambleFormation("rock", 2, level=level)
    f.stations = []
    ship = _Pilot()
    ship.invulnerable = 1e9
    wx = f.cam + ship.x
    m = sc.Missile(wx + 300.0, float(f.course.ground(wx + 300.0)) - 30.0, -1)
    m.homing = f.tune.homing > 0
    f.course.ceil[:] = 0.0
    f.missiles = [m]
    g = _Game(f, ship)
    f.speed = 0.0
    top = 0.0
    for _ in range(240):
        sc._missiles(g, f, 1 / 60, ship)
        top = max(top, abs(m.vx))
    return top


def test_the_missiles_home_in_as_hard_as_the_level_says():
    assert _slide(1) == 0.0
    half, full = _slide(3), _slide(5)
    assert 0 < half <= sc.HOMING_VX * 0.5 + 1e-6 and half < full <= sc.HOMING_VX + 1e-6


def test_no_comets_where_there_is_no_comet_section():
    f = sc.ScrambleFormation("rock", 2, level=2)
    for x in np.linspace(0, f.course.stop, 60):
        f.cam = float(x)
        assert not f.sky.comets_due()
    f = sc.ScrambleFormation("rock", 2, level=3)
    k = f.tune.keys.index("comets")
    f.cam = f.course.starts[k] + 400.0
    assert f.sky.comets_due()
    ship = _Pilot()
    ship.invulnerable = 1e9
    g = _Game(f, ship)
    f.sky.comet_in = 0.0
    f.sky.tick(g, 1 / 60, True)
    assert sb.COMET_GAP[0] * 2 - 1e-9 <= f.sky.comet_in <= sb.COMET_GAP[1] * 2 + 1e-9     # (half as many)


# ---------------------------------------------------------------- the missions
def test_the_five_raids_are_on_the_maps_of_their_acts():
    want = {"raid_deimos": ("deimos", 1, (1, 2, 3)), "raid_rock": ("rock", 2, (1, 2, 3)),
            "raid_europa": ("europa", 3, (2, 3)), "raid_titan": ("ice", 4, (2, 3)), "raid_triton": ("triton", 5, (3,))}
    for mid, (body, level, acts) in want.items():
        m = ss.mission_by_id(mid)
        assert m["scramble"] and m["body"] == body and m["body"] in lander.BODIES and m["raid"] == level
        assert tuple(m["acts"]) == acts and m["once"] and m["extra"] and not m.get("training") and not m.get("secret")
        assert ss.mission_group(m) == ss.GROUP_EXTRA
    st = ss.create_slot(1, "NOVA", "normal")
    m = ss.mission_by_id("raid_deimos")
    assert not ss.mission_open(st, m)
    st["flags"][m["need"]] = True
    assert ss.mission_playable(st, m) and ss.next_mission(st, [m]) is None     # (optional: never what the map suggests)


def test_a_raid_launches_its_setting_and_its_level_without_a_menu(run):
    g = run.game
    from test_spacewar import _state
    st = _state(act=2)
    st["flags"].update({"dome_s2": True, "dome_s4": True, "phenix_s1": True, "phenix_s3": True})
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.pane = "map"
    g.story.screen = "hub"
    ids = [m["id"] for m in g.story.missions()]
    assert all(r in ids for r in RAIDS[:4]) and "raid_triton" not in ids
    g.story.map_index = ids.index("raid_titan")
    spec = g.story.confirm()
    assert spec and spec["scramble"] and spec["body"] == "ice" and spec["raid"] == 4
    assert not spec.get("training") and g.story.screen != "lander_pick"
    g._begin_adventure(spec)
    g.input_grace = 0.0
    run.frames(3)
    form = g.formation
    assert isinstance(form, sc.ScrambleFormation) and form.style == "ice" and form.tune.level == 4
    assert form.speed == 172.0


def test_the_test_and_the_bonus_stay_at_the_full_scramble(run):
    g = run.game
    from test_spacewar import _state
    ss.save_state(ss.story_path(1), _state())
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index("test_scramble")
    g.story.lander_index = 3
    g.story.screen = "lander_pick"
    g.story.pick_for = "scramble"
    spec = g.story.confirm()
    assert "raid" not in spec and spec["body"] == lander.MENU_ORDER[3]
    g._begin_adventure(spec)
    run.frames(2)
    assert g.formation.tune.level == sc.LEVEL_MAX


def test_a_raid_pays_its_points_once_and_a_failure_costs():
    from test_spacewar import _state
    st = _state()
    st["flags"]["dome_s2"] = True
    st["credits"] = 1000
    m = ss.mission_by_id("raid_deimos")
    res = ss.record_result(st, "raid_deimos", 0, False)
    assert res["lost"] > 0 and st["credits"] < 1000 and ss.mission_playable(st, m)
    before = st["credits"]
    res = ss.record_result(st, "raid_deimos", 4200, True)
    assert res["cleared"] and st["credits"] == before + 4200
    assert not ss.mission_playable(st, m)                            # (once, until the ending has been told)
    st["flags"][ss.ENDING_DONE] = True
    assert ss.mission_playable(st, m)


def test_the_hud_of_a_low_level_draws_its_short_course_and_its_boss(run):
    g = run.game
    from test_spacewar import _state
    st = _state()
    st["flags"]["dome_s2"] = True
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index("raid_deimos")
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    run.frames(2)
    form = g.formation
    surf = g.game_surface
    surf.fill((0, 0, 0))
    sv.draw_hud(g, form)                                          # (the bar of the three sections)
    form.cam = form.course.stop
    form.phase = "arena"
    form.arena_time = 5.0
    surf.fill((0, 0, 0))
    sv.draw_hud(g, form)
    x, y, w, h = sv.WALL_BAR
    assert surf.get_at((int(x + w / 2), y + h + 15))[:3] == (220, 40, 40)      # (one point of life: one whole segment)
    run.frames(2)
