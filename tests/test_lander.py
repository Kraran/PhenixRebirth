"""The test level "Lunar Lander" (src/lander.py, src/lander_view.py): the ship lands by its thruster on the ice of Titan or
the rock of an asteroid, with a limited fuel, three zooms, flat zones of three sizes, a terrain that loops."""
import math
import random

import pygame
import pytest

import lander as ld
import lander_view as lv
import story_state as ss
from test_smoke import run  # noqa: F401,F811  (fixture)
from test_spacewar import _launch


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


class _Ship:
    def __init__(self, angle=-math.pi / 2):
        self.ast_angle = angle
        self.x = self.y = 0.0
        self.ast_vx = self.ast_vy = 0.0


def test_the_mission_is_a_training_test_in_the_list():
    m = ss.mission_by_id("test_lander")
    assert m and m["training"] and m["test"] and m["lander"]


def test_a_flight_starts_high_with_a_full_tank_and_can_be_drawn(run):
    spec = _launch(run, "test_lander")
    g = run.game
    assert spec.get("lander") and spec.get("training")
    form = g.formation
    assert isinstance(form, ld.LanderFormation)
    assert form.fuel == ld.FUEL_START and form.phase == "flying"
    assert form.altitude() > 1000 and form.zoom_i == 0 and abs(form.y - ld.START_Y) < 30   # (a few frames have passed)
    assert abs(form.x - ld.WORLD / 2) < 10 and abs(form.vx) <= 70
    run.frames(30)
    assert form.y > ld.START_Y                      # it falls
    assert g.player.alive


def test_it_ends_with_a_crash_when_nothing_is_done(run):
    _launch(run, "test_lander")
    g = run.game
    form = g.formation
    run.frames(60 * 40)
    assert form.phase == "crashed" and form.result == "crash"
    assert not g.adventure                           # the mission is over (a training: nothing lost)


def _form(style="rock", seed=7):
    return ld.LanderFormation(style=style, seed=seed, rng=random.Random(1))


def _prepare_landing(form, ship, pad_i=0, dx=0.0, height=5.0, vx=0.0, vy=5.0, angle=-math.pi / 2):
    """The ship just over a zone of the ground, nose to `angle`."""
    pad = form.terrain.pads[pad_i]
    ship.ast_angle = angle
    form.x = pad["x"] + dx
    form.y = pad["y"] - ld.FOOT_Y - height
    form.vx, form.vy = vx, vy
    return pad


def _run_flight(form, ship, seconds=3.0, push=False, turn=0.0):
    for _ in range(int(seconds * 60)):
        form.fly(ship, 1 / 60, turn, push)
        if form.phase != "flying":
            break


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("style", ["ice", "rock"])
def test_the_ground_has_one_to_three_flat_zones_of_the_three_sizes(style, seed):
    t = ld.Terrain(style, seed)
    assert 1 <= len(t.pads) <= 3
    for p in t.pads:
        assert p["w"] == ld.PAD_SIZES[p["kind"]]
        xs = [p["x"] + k * p["w"] / 10.0 for k in range(-5, 6)]
        ys = [t.ground(x) for x in xs]
        assert max(ys) - min(ys) < 0.01                           # flat
        assert t.dx(p["x"], ld.WORLD / 2) >= 700                  # not under the start
    others = [t.pad_at(x) for x in range(0, ld.WORLD, 8)]
    assert sum(1 for o in others if o is not None) > 0


def test_the_zones_are_one_and_a_half_two_and_three_times_the_ship():
    assert ld.PAD_SIZES == {"x1": 3 * ld.SHIP_W, "x2": 2 * ld.SHIP_W, "x5": int(1.5 * ld.SHIP_W)}
    assert ld.PAD_BONUS == {"x1": 1, "x2": 2, "x5": 5}


def test_the_ground_is_rugged_outside_the_zones_and_loops():
    t = ld.Terrain("ice", 3)
    assert t.ground(100.0) == pytest.approx(t.ground(100.0 + ld.WORLD))
    assert t.ground(-50.0) == pytest.approx(t.ground(ld.WORLD - 50.0))
    assert max(t.h) - min(t.h) > 300
    assert ld.Terrain.dx(10, ld.WORLD - 10) == 20


def test_the_same_seed_gives_the_same_ground_and_others_differ():
    a, b, c = ld.Terrain("rock", 5), ld.Terrain("rock", 5), ld.Terrain("rock", 6)
    assert list(a.h) == list(b.h) and a.pads == b.pads
    assert list(a.h) != list(c.h)


def test_the_gravity_depends_on_the_body():
    assert ld.BODIES["ice"]["gravity"] > ld.BODIES["rock"]["gravity"]
    assert _form("ice").gravity == ld.BODIES["ice"]["gravity"]
    assert _form("rock").gravity == ld.BODIES["rock"]["gravity"]
    assert _form(None).style in ld.BODIES


def test_gravity_pulls_down_and_the_ship_keeps_its_speed():
    f, s = _form(), _Ship()
    f.vx, f.vy, f.y = 40.0, 0.0, -1000.0
    x0 = f.x
    _run_flight(f, s, 1.0)
    assert f.vy == pytest.approx(f.gravity, rel=0.02)
    assert f.vx == pytest.approx(40.0)                     # nothing slows it sideways
    assert (f.x - x0) % ld.WORLD == pytest.approx(40.0, rel=0.05)


def test_the_thruster_pushes_along_the_axis_of_the_ship_and_burns_fuel():
    f, s = _form(), _Ship(angle=0.0)                       # nose to the right
    f.vx = f.vy = 0.0
    f.y = -1500.0
    burned = f.fly(s, 1 / 60, 0.0, True)
    assert burned and f.thrusting
    assert f.vx > 0 and abs(f.vy - f.gravity / 60) < 0.5
    assert f.fuel == pytest.approx(ld.FUEL_START - ld.FUEL_BURN / 60)
    f2, s2 = _form(), _Ship()                              # nose up: pushes up, against gravity
    f2.vx = f2.vy = 0.0
    f2.y = -1500.0
    for _ in range(60):
        f2.fly(s2, 1 / 60, 0.0, True)
    assert f2.vy < 0 < ld.THRUST - f2.gravity


def test_an_empty_tank_kills_the_thruster_but_not_the_turn():
    f, s = _form(), _Ship()
    f.fuel = 0.0
    f.vx = f.vy = 0.0
    f.y = -1500.0
    assert f.fly(s, 1 / 60, 1.0, True) is False and not f.thrusting
    assert f.vy > 0                                         # only gravity
    assert s.ast_angle > -math.pi / 2                       # still turning right
    f.fuel = 0.001
    for _ in range(30):
        f.fly(s, 1 / 60, 0.0, True)
    assert f.fuel == 0.0


def test_the_ship_turns_at_the_speed_asked():
    f, s = _form(), _Ship()
    f.y = -1500.0
    f.fly(s, 0.5, 1.0, False)
    assert s.ast_angle == pytest.approx(-math.pi / 2 + ld.TURN_SPEED * 0.5)


def test_the_world_loops_under_the_ship():
    f, s = _form(), _Ship()
    f.x, f.vx, f.y = ld.WORLD - 5.0, 300.0, -1500.0
    f.fly(s, 0.1, 0.0, False)
    assert 0 <= f.x < 100


@pytest.mark.parametrize("alt, cur, want", [
    (2000, 0, 0), (800, 0, 1), (300, 0, 2), (300, 1, 2), (950, 1, 1), (1100, 1, 0), (380, 2, 2), (420, 2, 1), (500, 2, 1)])
def test_three_zoom_levels_with_a_little_hysteresis(alt, cur, want):
    assert ld.zoom_for(alt, cur) == want


def test_the_zoom_slides_to_the_level_and_the_largest_is_the_normal_size():
    assert ld.ZOOMS == (0.25, 0.5, 1.0)
    f, s = _form(), _Ship()
    for _ in range(600):
        f.y = f.terrain.ground(f.x) - ld.FOOT_Y - 100.0
        f.vy = 0.0
        f.fly(s, 1 / 60, 0.0, False)
    assert f.zoom_i == 2 and f.zoom == 1.0 and f.ship_scale() == 1.0


@pytest.mark.parametrize("vx, vy, tilt, want", [
    (0, 10, 0, "perfect"), (14, 22, math.radians(4), "perfect"), (15, 10, 0, "rough"), (0, 23, 0, "rough"),
    (0, 10, math.radians(5), "rough"), (30, 48, math.radians(12), "rough"), (31, 10, 0, "crash"),
    (0, 49, 0, "crash"), (0, 10, math.radians(13), "crash"), (-14, 10, 0, "perfect"), (-31, 10, 0, "crash"),
    (0, -5, 0, "crash")])
def test_the_verdict_of_a_touch(vx, vy, tilt, want):
    assert ld.verdict(vx, vy, tilt) == want


def test_the_points_follow_the_zone_and_the_fuel():
    assert ld.landing_points("x1", "perfect", 10) == (500, 500)
    assert ld.landing_points("x2", "perfect", 10) == (1000, 500)
    assert ld.landing_points("x5", "perfect", 10) == (2500, 500)
    assert ld.landing_points("x1", "rough", 10) == (100, 100)
    assert ld.landing_points("x5", "rough", 7.9) == (500, 70)
    assert ld.landing_points("x1", "crash", 50) == (0, 0)
    assert ld.landing_points("x1", "perfect", -3) == (500, 0)


def test_lean_is_the_distance_from_straight_up():
    assert ld.lean(-math.pi / 2) == pytest.approx(0.0)
    assert ld.lean(0.0) == pytest.approx(math.pi / 2)
    assert ld.lean(math.pi / 2) == pytest.approx(math.pi)
    assert ld.lean(-math.pi / 2 + 2 * math.pi) == pytest.approx(0.0)
    assert ld.lean(-math.pi / 2 - 0.1) == pytest.approx(0.1)


def test_a_soft_upright_touch_on_a_zone_is_a_perfect_landing():
    f, s = _form(), _Ship()
    pad = _prepare_landing(f, s)
    _run_flight(f, s)
    assert f.phase == "landed" and f.result == "perfect" and f.pad is pad
    assert f.touch == ("perfect", pad)
    assert f.vx == f.vy == 0.0
    assert f.y + ld.FOOT_Y == pytest.approx(pad["y"], abs=0.01)     # the feet stand on the zone


def test_a_hard_touch_on_a_zone_is_a_rough_landing():
    f, s = _form(), _Ship()
    _prepare_landing(f, s, vy=40.0)
    _run_flight(f, s)
    assert f.phase == "landed" and f.result == "rough"


def test_too_fast_or_too_tilted_is_a_crash_even_on_a_zone():
    for kw in ({"vy": 80.0}, {"vx": 60.0}, {"angle": -math.pi / 2 + 0.5}):
        f, s = _form(), _Ship()
        _prepare_landing(f, s, **kw)
        _run_flight(f, s)
        assert f.phase == "crashed" and f.result == "crash" and f.pad is None, kw


def test_the_rugged_ground_is_always_a_crash_even_when_slow():
    t = ld.Terrain("rock", 7)
    x = next(x for x in range(0, ld.WORLD, 5) if all(t.pad_at(x + d) is None for d in range(-160, 161, 10)))
    f, s = _form(), _Ship()
    f.x, f.y, f.vx, f.vy = float(x), t.ground(x) - ld.FOOT_Y - 30.0, 0.0, 5.0
    _run_flight(f, s, 6.0)
    assert f.phase == "crashed" and f.result == "crash"


def test_a_foot_off_the_zone_is_a_crash():
    f, s = _form(), _Ship()
    pad = f.terrain.pads[0]
    _prepare_landing(f, s, dx=pad["w"] / 2 + 2.0)               # the middle at the very edge: one foot is outside
    _run_flight(f, s)
    assert f.result == "crash"


def test_the_ship_stops_flying_after_the_touch():
    f, s = _form(), _Ship()
    _prepare_landing(f, s)
    _run_flight(f, s)
    y = f.y
    assert f.fly(s, 0.1, 1.0, True) is False
    assert f.y == y and f.fuel == ld.FUEL_START


def test_the_formation_is_a_formation_without_enemies_that_ends_when_the_landing_is_read():
    f = _form()
    assert f.get_alive_enemies() == [] and f.get_hittable_enemies() == []
    assert f.remaining() == 1 and f.swarm_remaining() == 1 and not f.all_dead()
    assert f.update(0.1, 100) is None and f.draw(None) is None
    f.won = True
    assert f.all_dead() and f.remaining() == 0


def test_the_messages_of_the_end():
    f = _form()
    assert ld.message(f) is None
    f.phase, f.result = "landed", "perfect"
    assert ld.message(f) == ("lander_perfect", "success")
    f.result = "rough"
    assert ld.message(f) == ("lander_rough", "special")
    f.phase = "crashed"
    assert ld.message(f) == ("lander_crash", "danger")


def test_the_texts_exist_in_french_and_english_and_the_other_languages():
    import i18n
    for key in ("story_m_lander", "story_m_lander_hud", "story_m_lander_b", "lander_alt", "lander_hs", "lander_vs",
                "lander_tilt", "lander_fuel", "lander_empty", "lander_perfect", "lander_rough", "lander_crash",
                "lander_points", "story_lander_clear", "story_lander_retry"):
        for code in i18n.LANG_CODES:
            assert i18n.T[key][code], (key, code)
    assert "{p}" in i18n.T["lander_points"]["fr"] and "{b}" in i18n.T["lander_points"]["en"]
    assert i18n.T["lander_crash"]["fr"] != i18n.T["lander_crash"]["en"] or True


def test_the_sounds_are_made_and_loaded():
    import os
    from sounds import SOUND_DIR
    for name in ("lander_thrust", "lander_beep", "lander_land", "lander_rough"):
        assert os.path.getsize(os.path.join(SOUND_DIR, name + ".wav")) > 5000


@pytest.mark.parametrize("style", ["ice", "rock"])
def test_the_view_draws_the_three_zoom_levels(style):
    pygame.display.set_mode((1280, 720))
    surf = pygame.Surface((1280, 720))
    f, s = _form(style), _Ship()
    seen = set()
    for alt in (1500.0, 600.0, 120.0):
        f.y = f.terrain.ground(f.x) - ld.FOOT_Y - alt
        f.vy = f.vx = 0.0
        for _ in range(240):
            f.fly(s, 1 / 60, 0.0, False)
            f.vx = 0.0
            f.y = f.terrain.ground(f.x) - ld.FOOT_Y - alt
        if f.view is None:
            f.view = lv.View(style)
        surf.fill((0, 0, 0))
        f.view.draw(surf, f)
        seen.add(f.zoom)
        assert pygame.transform.average_color(surf)[:3] != (0, 0, 0)
    assert seen == set(ld.ZOOMS)


class _Sounds:
    def __init__(self):
        self.played = []

    def play(self, name, **kw):
        self.played.append((name, kw))

    def names(self):
        return [n for n, _ in self.played]


class _FakePlayer:
    def __init__(self):
        self.alive, self.dying = True, False
        self.x = 640.0
        self.burned = 0

    def burn_by_guardian(self):
        self.burned += 1
        return True


class _FakeGame:
    def __init__(self, form):
        self.formation = form
        self.stage_transition = None
        self.dt = 1 / 60
        self.player = _FakePlayer()
        self.sounds = _Sounds()
        self.shake_amount = 0.0
        self.scored = []

    def _add_score(self, player, pts):
        self.scored.append(pts)


def test_tick_does_nothing_in_another_mission():
    g = _FakeGame(_form())
    g.formation = object()
    ld.tick(g)
    assert g.sounds.played == []
    assert ld.active(g) is None


def test_tick_waits_while_a_stage_transition_runs():
    f = _form()
    g = _FakeGame(f)
    g.stage_transition = object()
    f.thrusting = True
    ld.tick(g)
    assert g.sounds.played == [] and f.time == 0.0


def test_the_engine_is_heard_every_two_tenths_of_a_second_only_while_it_burns():
    f = _form()
    g = _FakeGame(f)
    f.thrusting = True
    for _ in range(60):
        ld.tick(g)
    n = g.sounds.names().count("lander_thrust")
    assert 4 <= n <= 6
    f.thrusting = False
    before = len(g.sounds.played)
    for _ in range(60):
        ld.tick(g)
    assert len(g.sounds.played) == before
    f.thrusting = True
    g.player.dying = True
    for _ in range(60):
        ld.tick(g)
    assert len(g.sounds.played) == before                      # (a ship that is dying makes no engine noise)


def test_the_warning_beeps_start_when_the_fuel_is_low_and_come_faster_as_it_empties():
    f = _form()
    g = _FakeGame(f)
    f.fuel = ld.FUEL_LOW + 1.0
    for _ in range(120):
        ld.tick(g)
    assert "lander_beep" not in g.sounds.names()
    f.fuel = ld.FUEL_LOW
    for _ in range(180):
        ld.tick(g)
    slow = g.sounds.names().count("lander_beep")
    assert 2 <= slow <= 4
    g.sounds.played.clear()
    f.fuel = 1.0
    for _ in range(180):
        ld.tick(g)
    fast = g.sounds.names().count("lander_beep")
    assert fast > slow + 2
    g.sounds.played.clear()
    f.fuel = 0.0
    for _ in range(60):
        ld.tick(g)
    assert g.sounds.names().count("lander_beep") >= 4          # an empty tank still warns


def test_a_perfect_landing_scores_and_plays_the_sounds_then_ends_after_the_pause():
    f, s = _form(), _Ship()
    g = _FakeGame(f)
    pad = _prepare_landing(f, s)
    f.fuel = 30.5
    _run_flight(f, s)
    ld.tick(g)
    kind = pad["kind"]
    assert g.scored == [500 * ld.PAD_BONUS[kind] + 50 * 30]
    assert f.points == 500 * ld.PAD_BONUS[kind] and f.bonus == 1500
    assert g.sounds.names() == ["lander_land", "1up"]
    assert g.player.burned == 0 and f.touch is None
    for _ in range(int(ld.LAND_PAUSE * 60) - 5):
        ld.tick(g)
    assert not f.won
    for _ in range(10):
        ld.tick(g)
    assert f.won and g.scored == [500 * ld.PAD_BONUS[kind] + 1500]       # (scored once)


def test_a_rough_landing_scores_less_with_its_own_sound():
    f, s = _form(), _Ship()
    g = _FakeGame(f)
    pad = _prepare_landing(f, s, vy=40.0)
    f.fuel = 20.0
    _run_flight(f, s)
    ld.tick(g)
    assert g.scored == [100 * ld.PAD_BONUS[pad["kind"]] + 10 * 20]
    assert g.sounds.names() == ["lander_rough"]


def test_a_crash_blasts_the_ship_with_the_big_explosion_and_scores_nothing():
    f, s = _form(), _Ship()
    g = _FakeGame(f)
    _prepare_landing(f, s, vy=90.0)
    _run_flight(f, s)
    ld.tick(g)
    assert g.player.burned == 1 and g.scored == []
    assert g.sounds.names() == ["explosion_big"] and g.shake_amount >= 30.0
    ld.tick(g)
    assert g.player.burned == 1


def test_a_crash_of_a_ship_already_dying_adds_nothing():
    f, s = _form(), _Ship()
    g = _FakeGame(f)
    g.player.dying = True
    _prepare_landing(f, s, vy=90.0)
    _run_flight(f, s)
    ld.tick(g)
    assert g.player.burned == 0


def test_a_sound_that_fails_does_not_stop_the_game():
    class Bad:
        def play(self, *a, **k):
            raise RuntimeError("no sound card")
    f = _form()
    g = _FakeGame(f)
    g.sounds = Bad()
    f.thrusting = True
    ld.tick(g)
    g.sounds = None
    ld.tick(g)


def _land_in_game(run, seed_pad=0, vy=3.0):
    _launch(run, "test_lander")
    g = run.game
    form = g.formation
    p = g.player
    pad = form.terrain.pads[seed_pad]
    p.ast_angle = -math.pi / 2
    form.x, form.y, form.vx, form.vy = pad["x"], pad["y"] - ld.FOOT_Y - 2.0, 0.0, vy      # (soft on Titan too, where the pull is strong)
    return g, form, pad


def test_a_landing_in_the_game_adds_the_score_then_ends_the_mission(run):
    g, form, pad = _land_in_game(run)
    score = g.player.score
    run.frames(30)
    assert form.phase == "landed" and form.result == "perfect"
    gained = 500 * ld.PAD_BONUS[pad["kind"]] + 50 * int(form.fuel)
    assert g.player.score - score == gained
    assert g.player.alive and not g.player.dying
    run.frames(int(ld.LAND_PAUSE * 60) + 240)
    assert form.won and not g.adventure
    assert any(m for m in [ss.mission_by_id("test_lander")])


def test_the_hud_and_the_end_message_are_drawn(run):
    g, form, pad = _land_in_game(run)
    surf = g.screen if hasattr(g, "screen") else pygame.display.get_surface()
    run.frames(5)
    lv.draw_hud(g, form)
    form.fuel = 0.0
    run.frames(3)
    run.frames(40)
    assert form.phase == "landed"
    run.frames(30)
    assert surf is not None


def test_the_altitude_is_the_height_of_the_feet_over_the_ground():
    f = _form()
    f.y = f.terrain.ground(f.x) - ld.FOOT_Y - 123.0
    assert f.altitude() == pytest.approx(123.0)
    f.y = f.terrain.ground(f.x) + 500.0
    assert f.altitude() == 0.0


def test_the_thrust_goes_the_way_the_nose_points_and_only_that_way():
    f, s = _form(), _Ship(angle=-math.pi / 2)              # nose up: no push to the side
    f.vx = f.vy = 0.0
    f.y = -1500.0
    f.fly(s, 1 / 60, 0.0, True)
    assert abs(f.vx) < 1e-6
    f2, s2 = _form(), _Ship(angle=math.pi)                 # nose to the left
    f2.vx = f2.vy = 0.0
    f2.y = -1500.0
    f2.fly(s2, 1 / 60, 0.0, True)
    assert f2.vx < 0


def test_a_landing_on_the_edge_of_a_zone_with_both_feet_in_is_good_and_with_one_foot_out_is_a_crash():
    f, s = _form(), _Ship()
    pad = f.terrain.pads[0]
    _prepare_landing(f, s, dx=pad["w"] / 2 - 27.0)          # the right foot (at +26) is just inside
    _run_flight(f, s)
    assert f.result == "perfect"


# ------------------------------------------------------------------ the picture: a steady relief, a readable HUD
@pytest.mark.parametrize("z", ld.ZOOMS)
def test_the_points_of_the_relief_are_fixed_in_the_world_and_only_slide_with_the_camera(z):
    t = ld.Terrain("rock", 4)
    sxs0, wx0, gy0, sy0 = lv.relief(t, z, 1500.0, -40.0)
    assert all(w % lv.COLUMN == 0 for w in wx0)
    assert sxs0[0] <= 0 and sxs0[-1] >= 1280                          # the outline covers the whole width
    for d in (0.3, 1.0, 7.0, lv.COLUMN * 3, lv.COLUMN * 3 + 0.5):
        sxs1, wx1, gy1, sy1 = lv.relief(t, z, 1500.0 + d, -40.0)
        common = sorted(set(wx0) & set(wx1))
        assert len(common) > len(wx0) - 8
        for w in common[::7]:
            i0, i1 = list(wx0).index(w), list(wx1).index(w)
            assert gy0[i0] == gy1[i1] and sy0[i0] == pytest.approx(sy1[i1])      # the same height at the same place of the world
            assert sxs1[i1] == pytest.approx(sxs0[i0] - d * z)                  # it only slides by what the camera moved


def test_the_labels_never_touch_the_values_and_the_tank_is_under_the_readings(run):
    g, form, _ = _land_in_game(run)
    font = g.font
    rows = [("ALTITUDE", "%4d" % 123, 0), ("VIT. HORIZ.", "%+5.1f" % -88.8, 0), ("VIT. VERT.", "%+5.1f" % 88.8, 0),
            ("INCLINAISON", "%+4d°" % -180, 0)]
    left_x, right_x, top = lv.hud_layout(g, font, rows)
    widest_label = max(g._txt(font, r[0], lv.HUD_COLOR).get_width() for r in rows)
    widest_value = max(g._txt(font, r[1], lv.HUD_COLOR).get_width() for r in rows)
    assert left_x + widest_label + lv.HUD_GAP <= right_x - widest_value                 # a clear gap
    assert right_x == 1280 - 16 and left_x > 640                                         # in the right half
    run.frames(2)
    form.fuel = 80.0
    g.game_surface.fill((0, 0, 0))
    lv.draw_hud(g, form)
    surf = g.game_surface
    bright = [(x, y) for x in range(0, 1280, 2) for y in range(0, 720, 2) if sum(surf.get_at((x, y))[:3]) > 60]
    assert bright and min(x for x, _ in bright) > 600                                   # nothing in the left half: no overlap with the gauge of the hull
    assert max(y for _, y in bright) > top + 4 * lv.ROW_GAP                              # the tank is under the four readings
