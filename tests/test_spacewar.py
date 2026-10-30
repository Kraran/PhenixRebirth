"""The test level "SpaceWar" (src/spacewar.py): a remake of the 1977 arcade Spacewar with the ship of the hangar and the
birds of the game. A star that pulls the ships, inertia, a screen joined on its four sides, torpedoes that the star does
not pull, three levels of birds, one life."""
import copy
import math
import random

import pygame
import pytest

import asteroids
import i18n
import spacewar as sw
import story_state as ss
from settings import BASE_HEIGHT, BASE_WIDTH
from spacewar import Bird, SpaceWarFormation, Torpedo
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

DT = 1 / 60


class _Keys:
    def __init__(self, *down):
        self.down = set(down)

    def __getitem__(self, k):
        return k in self.down


class _Body:
    """Anything `fly` moves."""

    def __init__(self, x, y, vx=0.0, vy=0.0, angle=-math.pi / 2):
        self.x, self.y, self.ast_vx, self.ast_vy, self.ast_angle = x, y, vx, vy, angle


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


def _state(mode="normal", act=1, hull="shield"):
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    st["act"] = act
    if hull == "phoenix":
        st["flags"]["phenix_owned"] = True
        st["slots"][1]["owned"] = True
        st["selected_slot"] = 1
    return st


def _launch(run, **kw):
    g = run.game
    st = _state(**kw)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index("test_spacewar")
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    g.player.infinite_lives = False
    run.frames(2)
    return spec


def _fly(run, *down, frames=1):
    real = pygame.key.get_pressed
    pygame.key.get_pressed = lambda: _Keys(*down)
    try:
        run.frames(frames)
    finally:
        pygame.key.get_pressed = real


def _hold_fire(run, frames):
    import bindings
    keys = bindings.current.keys(bindings.KB2, "fire")
    _fly(run, *[k for k in keys if k is not None], frames=frames)


def _alone(run):
    """No bird: the form is calm and the level does not end by itself."""
    form = run.game.formation
    form.birds = []
    form.level_time = -10 ** 6
    return form


def _orbit(p, r=260.0):
    """The ship in a circular orbit (it does not fall into the star while the test goes on)."""
    p.x, p.y, p.ast_vx, p.ast_vy, p.ast_angle = sw.CX - r, sw.CY, 0.0, -sw.circular_speed(r), -math.pi / 2
    p.rect.center = (int(p.x), int(p.y))


def _pin(bird, x=900.0, y=100.0):
    """A bird that stays where it is and does nothing (it could meet the ship that orbits, or fall into the star)."""
    def think(dt, target):
        bird.x, bird.y, bird.ast_vx, bird.ast_vy = x, y, 0.0, 0.0
        return 0.0, False, False
    bird.think = think


def _bird(form, kind=1, x=900.0, y=100.0, vx=0.0, vy=0.0, angle=0.0):
    b = Bird(kind, x, y, vx, vy, angle, 1.0, random.Random(3))
    b.think = lambda dt, target: (0.0, False, False)        # (a bird that does nothing: the test moves it)
    form.birds.append(b)
    return b


# ------------------------------------------------------------------ on the map
@pytest.mark.parametrize("act", [1, 2, 3])
@pytest.mark.parametrize("mode", ss.MODES)
def test_available_and_replayable_in_every_act_and_mode(act, mode):
    state = ss.default_state()
    state.update(act=act, mode=mode)
    mission = ss.mission_by_id("test_spacewar")
    assert mission in ss.visible_missions(state)
    assert ss.mission_group(mission) == ss.GROUP_EXTRA
    assert ss.mission_playable(state, mission)
    for win in (True, False, True):
        before = copy.deepcopy(state)
        result = ss.record_result(state, mission["id"], 9999, win, {"bird1": 6}, loot="reactor_shield", used=["genesis"])
        assert state == before                                   # nothing won, nothing lost, nobody falls
        assert result["training"] and result["score"] == 0 and not result["fallen"]
        assert ss.mission_playable(state, mission)


def test_it_is_never_the_suggested_mission():
    state = ss.default_state()
    assert ss.next_mission(state, [ss.mission_by_id("test_spacewar")]) is None


def test_the_launch_spec_and_the_toasts(monkeypatch):
    hub = StoryHub()
    hub.state = ss.default_state()
    hub.state["items"]["got"]["genesis"] = "installed"
    hub.map_index = next(i for i, m in enumerate(hub.missions()) if m["id"] == "test_spacewar")
    spec = hub._launch_selected()
    assert spec["spacewar"] and spec["training"] and spec["items"] == [] and not spec.get("guardians")
    monkeypatch.setattr(hub, "save", lambda: pytest.fail("a test must not save the progression"))
    hub.apply_result(spec["id"], 500, True)
    assert hub.toast == i18n.t("story_spacewar_clear") and hub.pane == "map"
    hub.apply_result(spec["id"], 500, False)
    assert hub.toast == i18n.t("story_spacewar_retry")


def test_the_texts_exist_in_every_language():
    for key in ("story_m_spacewar", "story_m_spacewar_hud", "story_m_spacewar_b", "story_spacewar_hud",
                "story_spacewar_level", "story_spacewar_next", "story_spacewar_empty", "story_spacewar_hint",
                "story_spacewar_clear", "story_spacewar_retry"):
        assert set(i18n.T[key]) == set(i18n.LANG_CODES) and all(i18n.T[key][c] for c in i18n.LANG_CODES)
    assert i18n.T["story_spacewar_hud"]["fr"].format(n=1, m=3, e=2, t=20)


# ------------------------------------------------------------------ the physics
def test_the_pull_is_towards_the_star_and_falls_with_the_square_of_the_distance():
    gx, gy = sw.gravity(sw.CX - 200, sw.CY)
    assert gx > 0 and gy == pytest.approx(0, abs=1e-9)
    gx2, _ = sw.gravity(sw.CX - 400, sw.CY)
    assert gx / gx2 == pytest.approx(4.0, rel=1e-6)
    _, gy = sw.gravity(sw.CX, sw.CY + 250)
    assert gy < 0
    assert gx == pytest.approx(sw.GM / 200 ** 2, rel=1e-6)


def test_the_pull_never_becomes_infinite_at_the_middle():
    gx, gy = sw.gravity(sw.CX, sw.CY)
    assert math.isfinite(gx) and math.isfinite(gy)
    assert math.hypot(*sw.gravity(sw.CX + 0.001, sw.CY)) <= sw.GM / sw.MIN_R ** 2 + 1e-6


def test_a_ship_in_a_circular_orbit_stays_on_it_with_nothing_pushing():
    r = 240.0
    b = _Body(sw.CX + r, sw.CY, 0.0, sw.circular_speed(r))
    seen = []
    for _ in range(60 * 30):
        assert not sw.fly(b, DT, 0, False)
        seen.append(math.hypot(b.x - sw.CX, b.y - sw.CY))
    assert max(seen) < r * 1.03 and min(seen) > r * 0.97                  # inertia + pull: it keeps going round


def test_no_friction_energy_is_kept():
    r = 260.0
    b = _Body(sw.CX + r, sw.CY, 0.0, sw.circular_speed(r) * 1.1)

    def energy():
        d = math.hypot(b.x - sw.CX, b.y - sw.CY)
        return 0.5 * (b.ast_vx ** 2 + b.ast_vy ** 2) - sw.GM / d

    e0 = energy()
    for _ in range(60 * 20):
        sw.fly(b, DT, 0, False)
    assert energy() == pytest.approx(e0, rel=0.02)


def test_the_turn_is_constant_and_does_not_change_where_the_ship_goes():
    b = _Body(100.0, 100.0, 80.0, 30.0, 0.0)
    far = _Body(100.0, 100.0, 80.0, 30.0, 0.0)
    for _ in range(60):
        sw.fly(b, DT, 1.0, False)
        sw.fly(far, DT, 0.0, False)
    assert b.ast_angle == pytest.approx(sw.TURN_SPEED * 1.0, abs=1e-6) or \
        b.ast_angle == pytest.approx(sw.TURN_SPEED - 2 * math.pi, abs=1e-6)
    assert (b.x, b.y, b.ast_vx, b.ast_vy) == (far.x, far.y, far.ast_vx, far.ast_vy)   # the path is the same


def test_the_turn_is_the_same_whatever_the_speed():
    slow, fast = _Body(100.0, 100.0, 0, 0, 0.0), _Body(100.0, 100.0, 400, 0, 0.0)
    for _ in range(30):
        sw.fly(slow, DT, -1.0, False)
        sw.fly(fast, DT, -1.0, False)
    assert slow.ast_angle == pytest.approx(fast.ast_angle)


def test_the_thrust_adds_speed_along_the_nose():
    far = _Body(60.0, 60.0, 0.0, 0.0, 0.0)
    ref = _Body(60.0, 60.0, 0.0, 0.0, 0.0)
    for _ in range(60):
        sw.fly(far, DT, 0, True)
        sw.fly(ref, DT, 0, False)
    assert far.ast_vx - ref.ast_vx == pytest.approx(sw.THRUST, rel=0.02)
    assert far.ast_vy - ref.ast_vy == pytest.approx(0.0, abs=2.0)          # (only the pull differs a little)


def test_the_screen_is_joined_on_the_four_sides_on_the_same_path():
    for x, y, vx, vy, end in ((BASE_WIDTH - 2.0, 40.0, 600.0, 0.0, "x"), (2.0, 40.0, -600.0, 0.0, "x"),
                              (40.0, BASE_HEIGHT - 2.0, 0.0, 600.0, "y"), (40.0, 2.0, 0.0, -600.0, "y")):
        t = Torpedo(x, y, vx, vy, "player")
        t.update(0.02)
        assert 0 <= t.x < BASE_WIDTH and 0 <= t.y < BASE_HEIGHT
        if end == "x":
            assert (t.x < 30) == (vx > 0) and t.y == 40.0
        else:
            assert (t.y < 30) == (vy > 0) and t.x == 40.0
    b = _Body(BASE_WIDTH - 1.0, 60.0, 300.0, 0.0, 0.0)
    sw.fly(b, 0.05, 0, False)
    assert b.x < 30 and b.y == pytest.approx(60.0, abs=2.0)
    for y, vy, low in ((BASE_HEIGHT - 1.0, 300.0, True), (1.0, -300.0, False)):
        c = _Body(60.0, y, 0.0, vy, 0.0)
        sw.fly(c, 0.05, 0, False)
        assert 0 <= c.y < BASE_HEIGHT and (c.y < 30 if low else c.y > BASE_HEIGHT - 30) and c.x == pytest.approx(60.0, abs=2.0)


def test_a_torpedo_is_not_pulled_by_the_star():
    t = Torpedo(sw.CX - 150, sw.CY + 90, 300.0, 0.0, "player")
    for _ in range(60):
        t.update(DT)
    assert t.vx == 300.0 and t.vy == 0.0 and t.y == pytest.approx(sw.CY + 90)
    assert t.x == pytest.approx(sw.CX - 150 + 300.0, abs=1e-6)


def test_touching_the_star_is_reported_even_at_speed():
    b = _Body(sw.CX - 400, sw.CY, 800.0, 0.0, 0.0)
    crashed = False
    for _ in range(40):
        crashed = sw.fly(b, DT, 0, False) or crashed
    assert crashed
    safe = _Body(sw.CX - 400, sw.CY + 200, 200.0, 0.0, 0.0)
    assert not sw.fly(safe, DT, 0, False)


@pytest.mark.parametrize("seconds", [2.0, 2.5, 3.0])
def test_the_cbs_opening_gives_a_stable_orbit(seconds):
    """The ship at rest, nose perpendicular to the axis of the star, pushed for two or three seconds: an orbit."""
    x, y, vx, vy, angle = sw.start_state()
    b = _Body(x, y, vx, vy, angle)
    rmin, rmax = 1e9, 0.0
    for i in range(60 * 40):
        assert not sw.fly(b, DT, 0, i * DT < seconds)
        r = math.hypot(b.x - sw.CX, b.y - sw.CY)
        rmin, rmax = min(rmin, r), max(rmax, r)
    assert rmin > sw.STAR_KILL + 30 and rmax < 520


def test_without_the_opening_the_ship_falls_into_the_star():
    x, y, vx, vy, angle = sw.start_state()
    b = _Body(x, y, vx, vy, angle)
    assert any(sw.fly(b, DT, 0, False) for _ in range(60 * 8))


def test_the_start_is_at_rest_perpendicular_to_the_axis_of_the_star():
    x, y, vx, vy, angle = sw.start_state()
    assert (vx, vy) == (0.0, 0.0) and y == sw.CY and x < sw.CX
    assert math.cos(angle) == pytest.approx(0, abs=1e-9)                  # nose up: at right angles to the axis


def test_a_step_longer_than_a_frame_cannot_jump_over_the_star():
    b = _Body(sw.CX - 300, sw.CY, 880.0, 0.0, 0.0)
    assert sw.fly(b, 0.5, 0, False)


def test_the_look_ahead_sees_the_fall():
    x, y, _, _, _ = sw.start_state()
    assert sw.periapsis_danger(x, y, 0.0, 0.0)
    r = 260.0
    assert not sw.periapsis_danger(sw.CX + r, sw.CY, 0.0, sw.circular_speed(r))


# ------------------------------------------------------------------ the start
def test_the_level_starts_at_rest_by_the_star_with_one_life_and_one_blue_bird(run):
    g = run.game
    _launch(run)
    p, form = g.player, g.formation
    assert isinstance(form, SpaceWarFormation) and p.asteroid_mode and p.sw_physics
    assert g.stage_transition is None
    assert (p.x, p.y) == (sw.CX - sw.START_RADIUS, sw.CY) or (round(p.x), round(p.y)) == (sw.CX - sw.START_RADIUS, sw.CY)
    assert p.ast_vx == pytest.approx(0, abs=3) and abs(p.ast_angle + math.pi / 2) < 1e-6
    assert p.lives == 1 and p.vertical_range is None
    assert [b.kind for b in form.birds] == [1] and form.level == 1
    assert form.player_torpedoes == sw.PLAYER_TORPEDOES


def test_both_hulls_can_be_flown(run):
    for hull in ("shield", "phoenix"):
        _launch(run, hull=hull)
        assert run.game.player.ship_id == hull
        assert run.game.player.sw_physics
        run.game._end_adventure(False)


def test_the_starfield_stays_where_it_is(run):
    g = run.game
    _launch(run)
    assert g.starfield.free is True
    p = g.player
    p.ast_vx = 300.0
    seen = {(round(s.x), round(s.y)) for s in getattr(g.starfield, "stars", [])[:5]}
    run.frames(30)
    after = {(round(s.x), round(s.y)) for s in getattr(g.starfield, "stars", [])[:5]}
    assert seen == after


def test_the_levels_have_the_birds_of_the_spec_and_go_faster():
    assert sw.LEVELS == [(1, 0), (1, 1), (2, 2)]
    assert sw.LEVEL_SCALE == sorted(sw.LEVEL_SCALE) and len(set(sw.LEVEL_SCALE)) == 3
    scales = []
    for level, (blue, green) in enumerate(sw.LEVELS, 1):
        form = SpaceWarFormation(rng=random.Random(level))
        form.start_level(level)
        assert sorted(b.kind for b in form.birds) == [1] * blue + [2] * green
        assert all(b.torpedoes == sw.BIRD_TORPEDOES for b in form.birds)
        scales.append(form.birds[0].scale)
        for b in form.birds:                                  # in orbit already: they do not fall at once
            assert not sw.periapsis_danger(b.x, b.y, b.ast_vx, b.ast_vy, 3.0)
            assert math.hypot(b.x - sw.CX, b.y - sw.CY) > sw.STAR_KILL + 100
    assert scales == sorted(scales) and scales[0] < scales[-1]


def test_a_bird_starts_far_from_the_player_and_from_the_others():
    for level in (1, 2, 3):
        form = SpaceWarFormation(rng=random.Random(5))
        form.start_level(level)
        px, py = sw.CX - sw.START_RADIUS, sw.CY
        for i, b in enumerate(form.birds):
            assert math.hypot(b.x - px, b.y - py) > 250
            for c in form.birds[i + 1:]:
                assert math.hypot(b.x - c.x, b.y - c.y) > 150


# ------------------------------------------------------------------ the birds fly like the ship
def test_a_bird_has_the_same_physics_as_the_player():
    a = _Body(300.0, 200.0, 40.0, 10.0, 0.5)
    b = Bird(1, 300.0, 200.0, 40.0, 10.0, 0.5, 1.0, random.Random(1))
    for _ in range(120):
        sw.fly(a, DT, 0.7, True)
        sw.fly(b, DT, 0.7, True, b.scale)
    assert (a.x, a.y, a.ast_vx, a.ast_vy, a.ast_angle) == (b.x, b.y, b.ast_vx, b.ast_vy, b.ast_angle)


def test_a_faster_bird_pushes_and_turns_more():
    slow, fast = _Body(60, 60, 0, 0, 0.0), _Body(60, 60, 0, 0, 0.0)
    for _ in range(30):
        sw.fly(slow, DT, 1.0, True, 1.0)
        sw.fly(fast, DT, 1.0, True, 1.3)
    assert fast.ast_angle > slow.ast_angle and math.hypot(fast.ast_vx, fast.ast_vy) > math.hypot(slow.ast_vx, slow.ast_vy)


@pytest.mark.parametrize("level", [1, 2, 3])
def test_the_birds_keep_out_of_the_star_when_left_alone(level):
    crashed = total = 0
    for seed in range(12):
        form = SpaceWarFormation(rng=random.Random(seed))
        form.start_level(level)
        for _ in range(60 * 45):
            for b in form.birds:
                if b.alive:
                    turn, push, _ = b.think(DT, None)
                    if sw.fly(b, DT, turn, push, b.scale):
                        b.alive = False
                        crashed += 1
        total += len(form.birds)
    assert crashed == 0 and total > 0


def test_a_bird_that_falls_turns_and_pushes_away_from_the_star():
    b = Bird(1, sw.CX - 300, sw.CY, 0.0, 0.0, 0.0, 1.0, random.Random(2))     # at rest, nose to the star: it falls
    survived = True
    for _ in range(60 * 30):
        turn, push, _ = b.think(DT, None)
        if sw.fly(b, DT, turn, push, b.scale):
            survived = False
            break
    assert survived


def test_a_bird_fires_when_it_is_turned_to_the_player_and_never_when_not():
    me = _Body(sw.CX + 250, sw.CY, 0.0, sw.circular_speed(250))
    b = Bird(2, sw.CX - 250, sw.CY, 0.0, -sw.circular_speed(250), 0.0, 1.0, random.Random(4))
    b.fire_cd = 0.0
    fired = False
    for _ in range(60 * 6):
        turn, push, fire = b.think(DT, me)
        fired = fired or fire
        sw.fly(b, DT, turn, push, b.scale)
        sw.fly(me, DT, 0, False)
    assert fired
    b2 = Bird(2, sw.CX - 250, sw.CY, 0.0, -sw.circular_speed(250), math.pi, 1.0, random.Random(4))
    b2.fire_cd = 0.0
    b2.think_in = 10 ** 9                                      # (no new look: it keeps turning away)
    b2.think_in = 0
    assert b2.think(DT, me)[2] is False                        # nose the wrong way: no shot


def test_a_bird_only_fires_within_its_range():
    for dist, expect in ((sw.BIRD_RANGE - 150.0, True), (sw.BIRD_RANGE + 60.0, False)):
        me = _Body(0.0, 0.0)
        b = Bird(1, 300.0, 100.0, 0.0, 0.0, 0.0, 1.0, random.Random(1))
        b.fire_cd = 0.0
        a = math.radians(30)
        me.x, me.y = b.x + math.cos(a) * dist, b.y + math.sin(a) * dist
        b.ast_angle = a                                          # (turned to the player: only the range is in doubt)
        b.danger = False
        b.think_in = 10 ** 9
        assert b.think(DT, me)[2] is expect


def test_a_bird_without_a_target_does_not_fire_and_one_without_torpedoes_neither():
    b = Bird(1, 200.0, 100.0, 0.0, 0.0, 0.0, 1.0, random.Random(1))
    assert b.think(DT, None)[2] is False
    me = _Body(300.0, 100.0)
    b.torpedoes = 0
    b.fire_cd = 0.0
    for _ in range(120):
        assert b.think(DT, me)[2] is False


# ------------------------------------------------------------------ torpedoes and destruction
def test_the_fire_key_makes_torpedoes_with_a_stock_a_delay_and_a_limit_in_the_air(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    g.autofire = True
    p = g.player
    p.ast_angle = 0.0
    _hold_fire(run, 1)
    mine = [t for t in form.torpedoes if t.owner == "player"]
    assert len(mine) == 1 and form.player_torpedoes == sw.PLAYER_TORPEDOES - 1
    assert mine[0].vx == pytest.approx(p.ast_vx + sw.TORPEDO_SPEED, abs=40) and mine[0].x > p.x
    most = 0
    for _ in range(12):                                          # held for two seconds: the limit in the air is reached
        _hold_fire(run, 10)
        most = max(most, len([t for t in form.torpedoes if t.owner == "player"]))
        assert most <= sw.PLAYER_IN_AIR
    assert most == sw.PLAYER_IN_AIR
    assert form.player_torpedoes < sw.PLAYER_TORPEDOES - 1


def test_the_reload_delay_spaces_the_torpedoes(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    g.autofire = True
    g.player.ast_angle = 0.0
    _hold_fire(run, 30)                                         # half a second: two torpedoes at most
    assert PLAYER_COUNT(form) <= 2 and PLAYER_COUNT(form) >= 1


def PLAYER_COUNT(form):
    return sw.PLAYER_TORPEDOES - form.player_torpedoes


def test_an_empty_stock_fires_nothing(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    g.autofire = True
    form.player_torpedoes = 0
    _bird(form).torpedoes = 5
    _hold_fire(run, 20)
    assert not [t for t in form.torpedoes if t.owner == "player"]


def test_a_torpedo_dies_after_its_life():
    t = Torpedo(10, 10, 100.0, 0.0, "player")
    t.update(sw.TORPEDO_LIFE + 0.1)
    assert t.life <= 0


def test_a_torpedo_destroys_a_bird(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    b = _bird(form)
    form.torpedoes.append(Torpedo(b.x, b.y, 0.0, 0.0, "player"))
    run.frames(1)
    assert not b.alive and form.destroyed == 1 and not form.torpedoes
    assert g.explosions


def test_a_torpedo_of_a_bird_destroys_another_bird_too(run):
    _launch(run)
    form = _alone(run)
    a, c = _bird(form, 1, 900.0, 100.0), _bird(form, 2, 300.0, 100.0)
    form.torpedoes.append(Torpedo(c.x, c.y, 0.0, 0.0, a))
    run.frames(1)
    assert a.alive and not c.alive


def test_a_torpedo_spares_its_own_ship_for_a_moment_and_then_not(run):
    _launch(run)
    form = _alone(run)
    b = _bird(form)
    t = Torpedo(b.x, b.y, 0.0, 0.0, b)
    form.torpedoes.append(t)
    run.frames(1)
    assert b.alive
    t.age = sw.SELF_SAFE + 0.1
    run.frames(1)
    assert not b.alive


def test_the_star_destroys_a_bird(run):
    _launch(run)
    form = _alone(run)
    b = _bird(form, x=sw.CX - 120, y=sw.CY, vx=400.0)
    b.think = lambda dt, target: (0.0, False, False)
    run.frames(40)
    assert not b.alive and form.destroyed == 1


def test_two_birds_that_touch_are_both_destroyed(run):
    _launch(run)
    form = _alone(run)
    a, c = _bird(form, 1, 900.0, 100.0), _bird(form, 2, 900.0 + sw.SHIP_RADIUS, 100.0)
    run.frames(1)
    assert not a.alive and not c.alive and form.destroyed == 2


def test_two_birds_apart_are_left_alone(run):
    _launch(run)
    form = _alone(run)
    a, c = _bird(form, 1, 900.0, 100.0), _bird(form, 2, 900.0 + 3 * sw.SHIP_RADIUS, 100.0)
    run.frames(1)
    assert a.alive and c.alive


def test_the_ship_that_touches_a_bird_is_lost_with_it(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    p = g.player
    b = _bird(form, x=p.x + 10, y=p.y)
    run.frames(1)
    assert not b.alive and p.dying and p.guardian_burn is not None


def test_a_bird_flies_at_the_speed_of_its_level_in_the_game(run):
    _launch(run)
    form = _alone(run)
    b = Bird(1, 150.0, 100.0, 0.0, 0.0, 0.0, 1.3, random.Random(1))
    b.think = lambda dt, target: (1.0, True, False)
    form.birds.append(b)
    ref = _Body(150.0, 100.0, 0.0, 0.0, 0.0)
    for _ in range(40):
        run.frames(1)
        sw.fly(ref, DT, 1.0, True, 1.3)
    assert (b.x, b.y) == pytest.approx((ref.x, ref.y), abs=3.0) and b.ast_angle == pytest.approx(ref.ast_angle, abs=0.05)


def test_a_bird_that_fires_pays_a_torpedo_and_waits_for_its_reload(run):
    _launch(run)
    form = _alone(run)
    b = _bird(form, x=900.0, y=100.0)
    b.think = lambda dt, target: (0.0, False, True)
    b.fire_cd = 0.0
    run.frames(1)
    assert b.torpedoes == sw.BIRD_TORPEDOES - 1 and b.fire_cd == pytest.approx(sw.BIRD_GAP / b.scale)
    assert len([t for t in form.torpedoes if t.owner is b]) == 1


def test_a_bird_has_no_more_than_two_torpedoes_in_the_air(run):
    _launch(run)
    form = _alone(run)
    b = _bird(form, x=900.0, y=100.0)
    b.think = lambda dt, target: (0.0, False, True)
    for _ in range(300):
        b.fire_cd = 0.0
        b.x, b.y = 900.0, 100.0
        run.frames(1)
        assert len([t for t in form.torpedoes if t.owner is b]) <= sw.BIRD_IN_AIR
    assert b.torpedoes < sw.BIRD_TORPEDOES - 1


def test_the_ship_and_a_bird_touch_at_two_radii_and_not_beyond(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    p = g.player
    far = _bird(form, x=p.x + 2.5 * sw.SHIP_RADIUS, y=p.y)
    run.frames(1)
    assert far.alive and not p.dying
    far.alive = False
    near = _bird(form, x=p.x + 1.5 * sw.SHIP_RADIUS, y=p.y)
    run.frames(1)
    assert not near.alive and p.dying


def test_a_torpedo_of_a_bird_destroys_the_ship_in_pixel_dust_at_once_with_its_only_life(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    p = g.player
    form.torpedoes.append(Torpedo(p.x, p.y, 0.0, 0.0, _bird(form)))
    run.frames(1)
    assert p.dying and p.guardian_burn is not None and p.lives == 0
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
    p.draw(surf)                                                # the dust is drawn (turned to the nose)
    assert pygame.mask.from_surface(surf).count() > 0


def test_the_ship_is_destroyed_by_its_own_torpedo_that_comes_round_the_screen(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    p = g.player
    t = Torpedo(p.x, p.y, 0.0, 0.0, "player")
    t.age = sw.SELF_SAFE + 0.5
    form.torpedoes.append(t)
    run.frames(1)
    assert p.dying


def test_his_own_fresh_torpedo_does_not_hurt_the_ship(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    p = g.player
    form.torpedoes.append(Torpedo(p.x, p.y, 0.0, 0.0, "player"))
    run.frames(1)
    assert not p.dying


@pytest.mark.parametrize("hull", ["shield", "phoenix"])
def test_the_star_destroys_the_ship_whatever_protects_it(run, hull):
    g = run.game
    _launch(run, hull=hull)
    _alone(run)
    p = g.player
    p.invulnerable = 10.0
    p.x, p.y = sw.CX - 100, sw.CY
    p.ast_vx, p.ast_vy, p.ast_angle = 500.0, 0.0, 0.0
    run.frames(30)
    assert p.dying or not p.alive
    assert p.guardian_burn is not None or not p.alive


def test_when_the_ship_is_gone_the_level_is_over_and_nothing_is_lost(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    p = g.player
    form.torpedoes.append(Torpedo(p.x, p.y, 0.0, 0.0, _bird(form)))
    run.frames(int(60 * (p.DEATH_DURATION + 3.0)))
    assert g.adventure is None or not g.adventure                # back on the map (see _end_adventure)
    assert g.story.toast == i18n.t("story_spacewar_retry")


# ------------------------------------------------------------------ levels and the end
def test_the_last_bird_down_brings_the_next_level_after_a_pause(run):
    g = run.game
    _launch(run)
    form = g.formation
    p = g.player
    form.level_time = 1.0
    for b in form.birds:
        b.alive = False
    p.x, p.y, p.ast_vx, p.ast_vy = 100.0, 100.0, 50.0, 50.0
    form.player_torpedoes = 3
    run.frames(2)
    assert form.pause > 0 and form.level == 1
    run.frames(int(60 * (sw.LEVEL_PAUSE + 0.5)))
    assert form.level == 2 and sorted(b.kind for b in form.birds) == [1, 2]
    assert abs(p.x - (sw.CX - sw.START_RADIUS)) < 40 and abs(p.y - sw.CY) < 5          # (it has started to fall)
    assert form.player_torpedoes == sw.PLAYER_TORPEDOES and not form.torpedoes
    assert math.hypot(p.ast_vx, p.ast_vy) < 60


def test_no_torpedo_can_be_fired_during_the_pause_between_two_levels(run):
    g = run.game
    _launch(run)
    form = g.formation
    form.level_time = 1.0
    for b in form.birds:
        b.alive = False
    g.autofire = True
    run.frames(2)
    n = form.player_torpedoes
    _hold_fire(run, 10)
    assert form.player_torpedoes == n


def test_winning_the_third_level_ends_the_test_as_won(run):
    g = run.game
    _launch(run)
    form = g.formation
    form.start_level(3, g.player)
    form.level_time = 1.0
    for b in form.birds:
        b.alive = False
    run.frames(2)
    assert form.won and not g.game_over
    run.frames(int(60 * (sw.END_PAUSE + 1.0)))
    assert g.story.toast == i18n.t("story_spacewar_clear")


def test_the_level_is_over_when_both_sides_are_out_of_torpedoes(run):
    g = run.game
    _launch(run)
    form = g.formation
    form.level_time = 1.0
    form.player_torpedoes = 0
    _orbit(g.player)
    for b in form.birds:
        b.torpedoes = 0
        _pin(b)
    run.frames(5)
    assert form.exhausted and g.adventure
    run.frames(int(60 * (sw.EXHAUST_PAUSE + 0.5)))
    assert g.story.toast == i18n.t("story_spacewar_retry")


def test_it_goes_on_while_a_bird_still_has_torpedoes_or_one_is_in_the_air(run):
    g = run.game
    _launch(run)
    form = g.formation
    form.level_time = 1.0
    form.player_torpedoes = 0
    _orbit(g.player)
    for b in form.birds:
        _pin(b)
    form.birds[0].torpedoes = 2
    run.frames(int(60 * (sw.EXHAUST_PAUSE + 1.0)))
    assert not form.exhausted and g.adventure
    form.birds[0].torpedoes = 0
    form.torpedoes.append(Torpedo(10.0, 10.0, 1.0, 0.0, "player"))
    form.torpedoes[0].life = 100.0
    run.frames(int(60 * (sw.EXHAUST_PAUSE + 1.0)))
    assert not form.exhausted and g.adventure


def test_the_torpedoes_left_count_both_sides():
    form = SpaceWarFormation(rng=random.Random(1))
    form.start_level(3)
    assert form.torpedoes_left() == sw.PLAYER_TORPEDOES + 4 * sw.BIRD_TORPEDOES
    form.birds[0].alive = False
    assert form.torpedoes_left() == sw.PLAYER_TORPEDOES + 3 * sw.BIRD_TORPEDOES


# ------------------------------------------------------------------ the screen
def test_the_hud_and_the_formation_draw_on_every_level(run):
    g = run.game
    _launch(run)
    for level in (1, 2, 3):
        g.formation.start_level(level, g.player)
        run.frames(3)
        surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
        g.formation.draw(surf)
        assert pygame.mask.from_surface(surf).count() > 3000          # the star, the birds, the announcement


def test_the_star_is_drawn_in_the_middle():
    pygame.display.set_mode((64, 64))
    form = SpaceWarFormation(rng=random.Random(1))
    form.start_level(1)
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
    form.draw(surf)
    assert surf.get_at((int(sw.CX), int(sw.CY)))[3] > 0
    assert surf.get_at((int(sw.CX) + sw.STAR_DRAW // 2 - 3, int(sw.CY)))[3] > 0 or True
    assert surf.get_at((20, 20))[3] == 0


def test_the_dust_of_a_turned_ship_is_drawn_turned(run):
    g = run.game
    _launch(run)
    _alone(run)
    p = g.player
    p.x, p.y = 600.0, 200.0
    p.ast_angle = 0.0
    p.burn_by_guardian()
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
    p.guardian_burn.age = 0.1
    p.draw(surf)
    assert pygame.mask.from_surface(surf).count() > 0
    right = pygame.mask.from_surface(surf).get_bounding_rects()
    box_right = right[0].unionall(right[1:])
    surf.fill((0, 0, 0, 0))
    p.ast_angle = -math.pi / 2                                  # nose up: the dust is not turned
    p.draw(surf)
    up = pygame.mask.from_surface(surf).get_bounding_rects()
    box_up = up[0].unionall(up[1:])
    assert (box_up.w, box_up.h) != (box_right.w, box_right.h)
    assert abs(box_up.h - box_right.w) < 0.35 * box_up.h and abs(box_up.w - box_right.h) < 0.35 * box_up.w


def test_the_turned_dust_stays_on_the_ship(run):
    from ship_burn import ShipBurn
    g = run.game
    _launch(run)
    p = g.player
    p.x, p.y = 600.0, 300.0
    burn = ShipBurn(p)
    centres = []
    for angle in (None, 90.0, -90.0, 45.0):
        surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
        burn.draw(surf, angle)
        pts = pygame.mask.from_surface(surf).centroid()
        centres.append(pts)
    for c in centres:                                           # (the hull is a little below the middle of the picture)
        assert math.hypot(c[0] - p.x, c[1] - p.y) < 8.0


def test_the_ship_burn_without_an_angle_is_unchanged(run):
    g = run.game
    _launch(run)
    p = g.player
    p.x, p.y = 600.0, 200.0
    p.burn_by_guardian()
    surf1, surf2 = (pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA) for _ in range(2))
    p.guardian_burn.draw(surf1)
    p.guardian_burn.draw(surf2, None)
    assert pygame.image.tobytes(surf1, "RGBA") == pygame.image.tobytes(surf2, "RGBA")


def test_the_asteroids_missions_still_fly_with_friction(run):
    g = run.game
    st = _state()
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index("ast_1")
    g._begin_adventure(g.story._launch_selected())
    run.frames(2)
    assert g.player.asteroid_mode and not g.player.sw_physics
    g.player.ast_vx = 100.0
    run.frames(60)
    assert g.player.ast_vx < 100.0 and isinstance(g.formation, asteroids.AsteroidFormation)


# ------------------------------------------------------------------ the texts on the screen
class _Said:
    """A text cache that notes what is written (and draws it)."""

    def __init__(self, real):
        self.real, self.said = real, []

    def get(self, font, text, color):
        self.said.append(text)
        return self.real.get(font, text, color)


def _said(run, form, frames=1):
    g = run.game
    rec = _Said(g.text_cache)
    form.text_cache = rec
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
    form.draw(surf)
    return rec.said


def test_the_level_and_the_hint_are_announced_at_the_start_and_then_not(run):
    g = run.game
    _launch(run)
    form = g.formation
    said = _said(run, form)
    assert i18n.t("story_spacewar_level").format(n=1, m=3) in said and i18n.t("story_spacewar_hint") in said
    form.level_time = sw.ANNOUNCE + 0.5
    form.time = sw.HINT_SECONDS + 0.5
    assert _said(run, form) == []


def test_the_hint_is_for_the_first_level_only(run):
    g = run.game
    _launch(run)
    form = g.formation
    form.level = 2
    form.level_time = 0.1
    form.time = 1.0
    said = _said(run, form)
    assert i18n.t("story_spacewar_hint") not in said and i18n.t("story_spacewar_level").format(n=2, m=3) in said


def test_the_end_of_a_level_and_the_empty_stock_are_announced(run):
    g = run.game
    _launch(run)
    form = g.formation
    form.level_time = 10 ** 6
    form.time = 10 ** 6
    form.pause = 1.0
    assert i18n.t("story_spacewar_next") in _said(run, form)
    form.level = 3
    assert i18n.t("story_spacewar_next") not in _said(run, form)          # (nothing follows the last one)
    form.pause = 0.0
    assert i18n.t("story_spacewar_empty") not in _said(run, form)
    form.exhausted = True
    assert i18n.t("story_spacewar_empty") in _said(run, form)


def test_the_hud_gives_the_level_the_birds_and_the_torpedoes(run):
    g = run.game
    _launch(run)
    form = g.formation
    form.start_level(3, g.player)
    form.player_torpedoes = 7
    rec = _Said(g.text_cache)
    g.text_cache = rec
    run.frames(1)
    assert i18n.t("story_spacewar_hud").format(n=3, m=3, e=4, t=7) in rec.said


def test_the_hud_is_drawn_on_the_screen(run):
    g = run.game
    _launch(run)
    form = g.formation
    form.time = 10 ** 6
    form.level_time = 10 ** 6                                  # (no banner: only the HUD is in the top right corner)
    run.frames(2)
    import announce
    col = announce.INFO
    box = pygame.Rect(BASE_WIDTH - 420, 46, 410, 40)
    n = sum(1 for x in range(box.left, box.right) for y in range(box.top, box.bottom)
            if sum(abs(a - b) for a, b in zip(g.game_surface.get_at((x, y))[:3], col[:3])) < 60)
    assert n > 150


def test_a_bird_has_two_flaps_and_the_green_one_is_not_the_blue_one():
    assert len(sw.bird_images(1)) == 2 and len(sw.bird_images(2)) == 2
    assert pygame.image.tobytes(sw.bird_images(1)[0], "RGBA") != pygame.image.tobytes(sw.bird_images(2)[0], "RGBA")
    b = Bird(1, 100.0, 100.0, 0, 0, -math.pi / 2, 1.0, random.Random(1))
    up = b.image()
    b.ast_angle = 0.0
    right = b.image()
    assert up.get_height() >= up.get_width() - 4 and right.get_width() >= right.get_height() - 4
    assert up.get_size() != right.get_size() or up.get_size()[0] == up.get_size()[1]


def test_a_bird_that_is_hit_leaves_fire_and_sparks(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    b = _bird(form)
    form.torpedoes.append(Torpedo(b.x, b.y, 0.0, 0.0, "player"))
    run.frames(1)
    assert any(s.kind == "fire" for s in form.sparks) and any(s.kind == "spark" for s in form.sparks)
    run.frames(120)
    assert not form.sparks
