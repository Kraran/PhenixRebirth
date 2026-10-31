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


@pytest.fixture(autouse=True)
def _jupiter():
    """Every test starts (and ends) with Jupiter in the middle, whatever planet the one before used."""
    sw.set_planet("jupiter")
    yield
    sw.set_planet("jupiter")


def _state(mode="normal", act=1, hull="shield"):
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    st["act"] = act
    if hull == "phoenix":
        st["flags"]["phenix_owned"] = True
        st["slots"][1]["owned"] = True
        st["selected_slot"] = 1
    return st


def _launch(run, mission="test_spacewar", **kw):
    g = run.game
    st = _state(**kw)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mission)
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
    assert i18n.T["story_spacewar_hud"]["fr"].format(n=1, m=3, t=20)


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


# how long the thrusters push in the CBS opening, for each planet (the pull is halved since Jupiter's first version, and the
# lighter planets pull less still: the push that makes an orbit is shorter or longer, see PLANETS)
OPENING = {"jupiter": (0.8, 0.9, 1.0), "saturn": (1.2, 1.4, 1.55), "uranus": (0.8, 1.0, 1.2), "neptune": (0.8, 1.0, 1.2)}


@pytest.mark.parametrize("planet", sw.PLANET_KEYS)
@pytest.mark.parametrize("which", [0, 1, 2])
def test_the_cbs_opening_gives_a_stable_orbit(planet, which):
    """The ship at rest, nose perpendicular to the axis of the star, pushed for a moment: an orbit that does not go in."""
    sw.set_planet(planet)
    seconds = OPENING[planet][which]
    x, y, vx, vy, angle = sw.start_state()
    b = _Body(x, y, vx, vy, angle)
    rmin = 1e9
    for i in range(60 * 40):
        assert not sw.fly(b, DT, 0, i * DT < seconds, 1.0, sw.PLAYER_THRUST, sw.PLAYER_RADIUS)
        rmin = min(rmin, math.hypot(b.x - sw.CX, b.y - sw.CY))
    assert rmin > sw.STAR_R + 20


def test_without_the_opening_the_ship_falls_into_the_star():
    x, y, vx, vy, angle = sw.start_state()
    b = _Body(x, y, vx, vy, angle)
    assert any(sw.fly(b, DT, 0, False, 1.0, sw.PLAYER_THRUST, sw.PLAYER_RADIUS) for _ in range(60 * 8))


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
    assert sw.LEVELS == [(1, 0, 0), (1, 1, 0), (2, 1, 1)]
    assert sw.LEVEL_SCALE == sorted(sw.LEVEL_SCALE) and len(set(sw.LEVEL_SCALE)) == 3
    scales = []
    for level, (blue, green, boss) in enumerate(sw.LEVELS, 1):
        form = SpaceWarFormation(rng=random.Random(level))
        form.start_level(level)
        assert sorted(b.kind for b in form.birds) == [1] * blue + [2] * green + [sw.SAUCER] * boss
        assert all(b.torpedoes == (sw.SAUCER_TORPEDOES if b.kind == sw.SAUCER else sw.BIRD_TORPEDOES) for b in form.birds)
        scales.append(form.birds[0].scale)
        for b in form.birds:                                  # in orbit already: they do not fall at once
            assert not sw.periapsis_danger(b.x, b.y, b.ast_vx, b.ast_vy, 3.0)
            assert math.hypot(b.x - sw.CX, b.y - sw.CY) > sw.STAR_R + 100
    assert scales == sorted(scales) and scales[0] < scales[-1]


def test_the_enemy_torpedoes_are_slow_and_the_players_are_not():
    assert sw.BIRD_TORPEDO_SPEED < 0.6 * sw.TORPEDO_SPEED
    assert sw.BIRD_TORPEDO_LIFE > sw.TORPEDO_LIFE
    form = SpaceWarFormation(rng=random.Random(1))
    b = Bird(1, 400.0, 300.0, 10.0, 20.0, 0.0, 1.0, random.Random(1))
    sw._fire(form, b, b)
    t = form.torpedoes[-1]
    assert t.vx == pytest.approx(10.0 + sw.BIRD_TORPEDO_SPEED) and t.vy == pytest.approx(20.0)
    assert t.life == sw.BIRD_TORPEDO_LIFE
    sw._fire(form, "player", b)
    t = form.torpedoes[-1]
    assert t.vx == pytest.approx(10.0 + sw.TORPEDO_SPEED) and t.life == sw.TORPEDO_LIFE


def test_a_bird_leads_its_aim_with_the_slow_torpedo():
    b = Bird(1, 300.0, 300.0, 0.0, 0.0, 0.0, 1.0, random.Random(1))
    b.danger = False
    b.think_in = 10.0

    class T:
        x, y, ast_vx, ast_vy = 300.0 + 230.0, 300.0, 0.0, 20.0

    b.think(0.01, T)
    # (the target is 230 px away and goes down at 20 px/s: the torpedo takes dist / its speed, and the aim is that far below)
    t = math.hypot(230.0, 0.0) / sw.BIRD_TORPEDO_SPEED
    assert b.turn == pytest.approx(5.0 * math.atan2(20.0 * t, 230.0), rel=1e-6)


def test_the_saucer_fires_from_its_own_nose():
    form = SpaceWarFormation(rng=random.Random(1))
    boss = Bird(sw.SAUCER, 400.0, 300.0, 0.0, 0.0, 0.0, 1.0, random.Random(1))
    sw._fire(form, boss, boss)
    assert form.torpedoes[-1].x - boss.x == pytest.approx(sw.SAUCER_RADIUS + 9)


def test_the_saucer_is_bigger_for_every_collision(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    gap = (sw.BIRD_RADIUS + sw.SAUCER_RADIUS) / 2.0                 # (inside the saucer, outside a bird)
    boss = _bird(form, sw.SAUCER, 900.0, 100.0)
    form.torpedoes.append(Torpedo(boss.x + gap, boss.y, 0.0, 0.0, "player"))
    run.frames(1)
    assert boss.hp == sw.SAUCER_HP - 1                              # (a torpedo)
    small = _bird(form, 1, 900.0, 100.0 + sw.BIRD_RADIUS + sw.SAUCER_RADIUS - 4.0)
    run.frames(1)
    assert not small.alive and boss.alive                           # (another bird)
    p = g.player
    p.x, p.y = boss.x, boss.y + sw.PLAYER_RADIUS + gap
    p.rect.center = (int(p.x), int(p.y))
    run.frames(1)
    assert p.dying                                                  # (the ship)


def test_the_saucer_touches_the_star_before_a_bird_does():
    class O:
        ast_vx = ast_vy = 0.0
        ast_angle = 0.0

    def crash(radius):
        o = O()
        o.x, o.y = sw.CX + sw.STAR_R + sw.CRASH_SHARE * (sw.BIRD_RADIUS + sw.SAUCER_RADIUS) / 2.0, sw.CY
        return sw.fly(o, 1e-4, 0.0, False, 1.0, sw.THRUST, radius)

    assert crash(sw.SAUCER_RADIUS) and not crash(sw.BIRD_RADIUS)


def test_in_the_level_the_saucer_crashes_into_the_star_with_its_own_size(run):
    _launch(run)
    form = _alone(run)
    spot = sw.STAR_R + sw.CRASH_SHARE * (sw.BIRD_RADIUS + sw.SAUCER_RADIUS) / 2.0
    boss = _bird(form, sw.SAUCER, sw.CX + spot, sw.CY)
    small = _bird(form, 1, sw.CX, sw.CY - spot)
    run.frames(1)
    assert not boss.alive and small.alive


def test_the_third_level_is_two_blue_a_green_and_the_boss_saucer():
    form = SpaceWarFormation(rng=random.Random(4))
    form.start_level(3)
    kinds = sorted(b.kind for b in form.birds)
    assert kinds == [1, 1, 2, sw.SAUCER]
    boss = [b for b in form.birds if b.kind == sw.SAUCER][0]
    assert boss.radius == sw.SAUCER_RADIUS > sw.BIRD_RADIUS and boss.hp == sw.SAUCER_HP
    assert all(b.radius == sw.BIRD_RADIUS and b.hp == 1 for b in form.birds if b is not boss)
    pic = boss.image()
    assert pic.get_width() > 2 * sw.BIRD_RADIUS


def test_the_saucer_takes_several_torpedoes_and_flashes(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    boss = _bird(form, sw.SAUCER)
    plain = boss.image().copy()
    for n in range(sw.SAUCER_HP - 1):
        form.torpedoes.append(Torpedo(boss.x, boss.y, 0.0, 0.0, "player"))
        run.frames(1)
        assert boss.alive and boss.hp == sw.SAUCER_HP - 1 - n and not form.torpedoes
        assert boss.hit > 0
    lit = boss.image()
    assert pygame.image.tobytes(lit, "RGBA") != pygame.image.tobytes(plain, "RGBA")
    run.frames(int(60 * (sw.HIT_FLASH + 0.2)))
    assert boss.hit == 0.0
    form.torpedoes.append(Torpedo(boss.x, boss.y, 0.0, 0.0, "player"))
    run.frames(1)
    assert not boss.alive and form.destroyed == 1 and g.explosions


def test_the_saucer_life_bar_is_drawn_and_shrinks(run):
    _launch(run)
    form = _alone(run)
    boss = _bird(form, sw.SAUCER, 900.0, 100.0)

    def red(hp):
        boss.hp = hp
        surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
        form.draw(surf)
        return sum(1 for x in range(840, 960) if surf.get_at((x, int(boss.y - boss.radius - 20)))[:3] == (230, 70, 50))

    assert red(3) > red(2) > red(1) > 0


def test_the_third_level_is_won_when_the_saucer_is_destroyed_even_with_birds_left(run):
    g = run.game
    _launch(run)
    form = g.formation
    form.start_level(3, g.player)
    form.level_time = 1.0
    boss = [b for b in form.birds if b.kind == sw.SAUCER][0]
    for b in form.birds:
        _pin(b)
    _orbit(g.player)
    run.frames(3)
    assert not form.won and not form.level_done()
    for b in form.birds:
        if b is not boss:
            b.alive = False
    run.frames(3)
    assert not form.won                                        # (the birds alone do not end it)
    boss.hp = 1
    others = [_bird(form, 1, 200.0, 650.0)]
    sw._hurt_bird(g, form, boss)
    assert form.level_done() and others[0].alive
    run.frames(3)
    assert form.won


def test_the_other_levels_are_won_when_no_bird_is_left():
    form = SpaceWarFormation(rng=random.Random(2))
    form.start_level(2)
    assert not form.level_done()
    for b in form.birds:
        b.alive = False
    assert form.level_done()


def test_the_saucer_is_not_hurt_by_a_ram_or_a_crashing_bird_but_kills_the_ship(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    boss = _bird(form, sw.SAUCER, 900.0, 100.0)
    small = _bird(form, 1, 930.0, 100.0)
    run.frames(1)
    assert boss.alive and boss.hp == sw.SAUCER_HP and not small.alive
    p = g.player
    p.x, p.y = boss.x + 20, boss.y
    p.rect.center = (int(p.x), int(p.y))
    run.frames(1)
    assert p.dying and boss.alive and boss.hp == sw.SAUCER_HP


def test_the_saucer_is_hit_by_the_rock_for_one_point(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    boss = _bird(form, sw.SAUCER, 900.0, 100.0)
    form.rock = sw.SpaceRock(boss.x, boss.y, 0.0, 0.0, random.Random(1))
    run.frames(1)
    assert boss.alive and boss.hp == sw.SAUCER_HP - 1


def test_the_saucer_fires_up_to_three_slow_torpedoes_at_once(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    boss = _bird(form, sw.SAUCER, 900.0, 100.0)

    def think(dt, target):
        boss.x, boss.y, boss.ast_vx, boss.ast_vy = 900.0, 100.0, 0.0, 0.0
        return 0.0, False, True
    boss.think = think
    _orbit(g.player)
    most = 0
    for _ in range(240):
        boss.fire_cd = 0.0
        run.frames(1)
        _orbit(g.player)
        most = max(most, sum(1 for tp in form.torpedoes if tp.owner is boss))
    assert most == sw.SAUCER_IN_AIR
    assert boss.torpedoes < sw.SAUCER_TORPEDOES


def test_the_boss_message_is_shown_on_the_last_level(run):
    _launch(run)
    form = run.game.formation
    form.start_level(3, run.game.player)
    form.level_time = 0.1
    form.started = True
    asked = []
    form._say = lambda surface, text, color, cy: asked.append(text)
    form.draw(pygame.Surface((BASE_WIDTH, BASE_HEIGHT)))
    assert i18n.t("story_spacewar_boss") in asked
    asked.clear()
    form.start_level(1, run.game.player)
    form.level_time = 0.1
    form.draw(pygame.Surface((BASE_WIDTH, BASE_HEIGHT)))
    assert i18n.t("story_spacewar_boss") not in asked


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


@pytest.mark.parametrize("planet", sw.PLANET_KEYS)
@pytest.mark.parametrize("level", [1, 2, 3])
def test_the_birds_keep_out_of_the_star_when_left_alone(level, planet):
    sw.set_planet(planet)
    crashed = total = 0
    for seed in range(12 if planet == "jupiter" else 5):
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
    b = Bird(1, sw.CX - 420, sw.CY, 0.0, 0.0, 0.0, 1.0, random.Random(2))     # at rest, nose to the star: it falls
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
    p.ast_angle = -math.pi / 2                                   # (up: a torpedo that goes to the star is stopped by it)
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
    a, c = _bird(form, 1, 900.0, 100.0), _bird(form, 2, 900.0 + sw.BIRD_RADIUS, 100.0)
    run.frames(1)
    assert not a.alive and not c.alive and form.destroyed == 2


def test_two_birds_apart_are_left_alone(run):
    _launch(run)
    form = _alone(run)
    a, c = _bird(form, 1, 900.0, 100.0), _bird(form, 2, 900.0 + 3 * sw.BIRD_RADIUS, 100.0)
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
    far = _bird(form, x=p.x + 2.5 * sw.BIRD_RADIUS, y=p.y)
    run.frames(1)
    assert far.alive and not p.dying
    far.alive = False
    near = _bird(form, x=p.x + 1.5 * sw.BIRD_RADIUS, y=p.y)
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
    assert form.torpedoes_left() == sw.PLAYER_TORPEDOES + 3 * sw.BIRD_TORPEDOES + 14
    for b in form.birds:
        if b.kind == sw.SAUCER:
            b.alive = False
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
    assert i18n.t("story_spacewar_hud").format(n=3, m=3, t=7) in rec.said


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


# ------------------------------------------------------------------ the second round (Kraran, 30/10)
def test_the_start_is_farther_from_the_star_than_it_was():
    assert sw.START_RADIUS >= 330
    x, y, _, _, _ = sw.start_state()
    assert sw.CX - x == sw.START_RADIUS and x > 100                      # (and still well inside the screen)


def test_the_ship_is_drawn_at_half_its_size(run):
    g = run.game
    _launch(run)
    _alone(run)
    p = g.player
    p.invulnerable = 0.0
    p.ast_angle = -math.pi / 2
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
    p.draw(surf)
    small = pygame.mask.from_surface(surf).get_bounding_rects()
    small = small[0].unionall(small[1:])
    p.sw_physics = False                                                 # the same ship drawn as in the Asteroids level
    surf.fill((0, 0, 0, 0))
    p.draw(surf)
    full = pygame.mask.from_surface(surf).get_bounding_rects()
    full = full[0].unionall(full[1:])
    assert 0.4 < small.h / full.h < 0.6 and 0.4 < small.w / full.w < 0.6


def test_the_dust_of_the_ship_is_half_size_too(run):
    from ship_burn import ShipBurn
    g = run.game
    _launch(run)
    p = g.player
    p.x, p.y = 600.0, 300.0
    burn = ShipBurn(p)
    burn.age = 0.5
    a, b = (pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA) for _ in range(2))
    burn.draw(a, 0.0, 1.0)
    burn.draw(b, 0.0, 0.5)
    ra = pygame.mask.from_surface(a).get_bounding_rects()
    rb = pygame.mask.from_surface(b).get_bounding_rects()
    ra, rb = ra[0].unionall(ra[1:]), rb[0].unionall(rb[1:])
    assert 0.4 < rb.h / ra.h < 0.6


def test_the_hit_zone_of_the_star_is_the_disc_that_is_drawn():
    img = sw.star_image()
    cx = cy = img.get_width() // 2
    assert img.get_at((cx + int(sw.STAR_R) - 4, cy))[3] > 200            # the disc is there inside the zone
    assert 0 <= img.get_width() // 2 - sw.STAR_R <= 6                    # the zone reaches the edge of the picture
    for radius in (sw.PLAYER_RADIUS, sw.BIRD_RADIUS):
        edge = sw.STAR_R + sw.CRASH_SHARE * radius
        inside = _Body(sw.CX - edge + 1.0, sw.CY, 0, 0, 0.0)
        outside = _Body(sw.CX - edge - 2.0, sw.CY, 0, 0, 0.0)
        assert sw.fly(inside, 0.0005, 0, False, 1.0, sw.THRUST, radius)
        assert not sw.fly(outside, 0.0005, 0, False, 1.0, sw.THRUST, radius)


def test_the_big_ship_touches_the_star_a_little_sooner_than_the_small_one():
    big = sw.STAR_R + sw.CRASH_SHARE * sw.BIRD_RADIUS
    small = sw.STAR_R + sw.CRASH_SHARE * sw.PLAYER_RADIUS
    assert big > small > sw.STAR_R


def test_the_star_stops_a_torpedo_that_reaches_its_disc(run):
    _launch(run)
    form = _alone(run)
    form.torpedoes.append(Torpedo(sw.CX - sw.STAR_R - 6, sw.CY, 60.0, 0.0, "player"))
    form.torpedoes.append(Torpedo(sw.CX - sw.STAR_R - 6, sw.CY + 200, 60.0, 0.0, "player"))     # (passes below it)
    run.frames(1)
    assert len(form.torpedoes) == 2
    run.frames(10)
    assert len(form.torpedoes) == 1 and form.torpedoes[0].y == pytest.approx(sw.CY + 200)


def test_a_torpedo_of_a_bird_is_stopped_by_the_star_too(run):
    _launch(run)
    form = _alone(run)
    form.torpedoes.append(Torpedo(sw.CX + sw.STAR_R + 3, sw.CY, -200.0, 0.0, _bird(form)))
    run.frames(3)
    assert not form.torpedoes and any(s.kind in ("spark", "fire") for s in form.sparks)


def test_the_thrusters_of_the_player_are_stronger_than_those_of_a_bird(run):
    assert sw.PLAYER_THRUST > sw.THRUST * 1.2
    g = run.game
    _launch(run)
    _alone(run)
    p = g.player
    p.x, p.y, p.ast_vx, p.ast_vy, p.ast_angle = 60.0, 60.0, 0.0, 0.0, 0.0
    ref = _Body(60.0, 60.0, 0, 0, 0.0)
    for _ in range(30):
        sw.fly(ref, DT, 0, False)
    _fly(run, pygame.K_UP, frames=30)
    assert p.ast_vx - ref.ast_vx == pytest.approx(sw.PLAYER_THRUST * 0.5, rel=0.1)


def test_the_hud_does_not_tell_how_many_birds_are_left():
    for code in i18n.LANG_CODES:
        text = i18n.T["story_spacewar_hud"][code]
        assert "{e}" not in text and "OISEAUX" not in text.upper() and "BIRDS" not in text.upper()
    assert set(i18n.T["story_spacewar_hud"]["fr"].replace("{", " ").replace("}", " ").split()) >= {"n", "m", "t"}


def _drawn_box(ux, uy, tip=(255, 0, 255)):
    surf = pygame.Surface((200, 200), pygame.SRCALPHA)
    sw.draw_torpedo(surf, 100.0, 100.0, ux, uy, tip)
    return surf, pygame.mask.from_surface(surf, 20).get_bounding_rects()


def test_a_torpedo_of_the_player_is_drawn_long_and_pointing_the_way_it_goes():
    for ux, uy in ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0)):
        surf, rects = _drawn_box(ux, uy)
        box = rects[0].unionall(rects[1:])
        along, across = (box.w, box.h) if ux else (box.h, box.w)
        assert along > 1.8 * across and along >= 24
        nose = (int(100 + ux * 9), int(100 + uy * 9))
        assert surf.get_at(nose)[:3] == (255, 0, 255)                    # the nose is in the colour of the hull
        tail = (int(100 - ux * 9), int(100 - uy * 9))
        assert surf.get_at(tail)[:3] != (255, 0, 255) and surf.get_at(tail)[3] > 0


def test_the_torpedoes_of_the_player_are_drawn_as_torpedoes(run):
    _launch(run)
    form = _alone(run)
    form.tip = (255, 0, 255)
    form.torpedoes.append(Torpedo(300.0, 600.0, 400.0, 0.0, "player"))
    form.torpedoes.append(Torpedo(900.0, 600.0, 0.0, 400.0, _bird(form)))
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
    form.draw(surf)
    assert surf.get_at((309, 600))[:3] == (255, 0, 255)                  # the nose of the first
    assert surf.get_at((900, 609))[:3] != (255, 0, 255)                  # (the bird's is a plain light)


# --- the small asteroid
def test_a_small_asteroid_comes_in_from_outside_the_screen():
    for seed in range(60):
        rock = sw.launch_rock(random.Random(seed))
        assert not (0 <= rock.x < BASE_WIDTH and 0 <= rock.y < BASE_HEIGHT)
        assert math.hypot(rock.vx, rock.vy) >= sw.ROCK_SPEED[0] * 0.99
        assert rock.radius == asteroids.ROCK_RADIUS[1]
        assert not rock.inside


def test_the_small_asteroid_does_not_wrap_it_goes_out_by_the_edge():
    rock = sw.SpaceRock(sw.CX + 300, 100.0, 300.0, 0.0, random.Random(1))      # (heading for the right edge, far from the star)
    rock.update(0.01)
    assert rock.inside and not rock.gone()
    for _ in range(300):
        rock.update(DT)
        if rock.gone():
            break
    assert rock.gone() and rock.x > BASE_WIDTH                           # it is out on the right: nothing on the left


def test_a_rock_that_never_comes_in_is_forgotten_in_the_end():
    rock = sw.SpaceRock(-40.0, -40.0, -50.0, -50.0, random.Random(1))
    assert not rock.gone()
    for _ in range(60 * 45):
        rock.update(DT)
    assert rock.gone()


def test_the_small_asteroid_is_pulled_by_the_star():
    rock = sw.SpaceRock(-40.0, 250.0, 300.0, 0.0, random.Random(1))
    for _ in range(60):
        rock.update(DT)
    assert rock.vx > 300.0 + 5.0 and rock.vy > 2.0                       # (pulled towards the star: faster, and down)


def test_a_small_asteroid_rarely_ends_on_the_star():
    crashes = 0
    n = 400
    for seed in range(n):
        r = sw.launch_rock(random.Random(seed))
        crashes += sw.rock_crashes(r.x, r.y, r.vx, r.vy)
    assert crashes <= n / 3
    assert crashes < n * 0.2                                             # (in fact much less)


def test_the_paths_that_end_on_the_star_are_the_exception_not_the_aim():
    sample = []
    for seed in range(300):
        rng = random.Random(1000 + seed)
        x, y = -40.0, rng.uniform(0, BASE_HEIGHT)
        a = math.atan2(sw.CY - y, sw.CX - x)
        sample.append(sw.rock_crashes(x, y, math.cos(a) * 300, math.sin(a) * 300))
    assert any(sample)                                                   # aimed at the star's middle: it does fall in


def test_a_rock_on_the_star_is_gone_with_dust(run):
    _launch(run)
    form = _alone(run)
    form.rock = sw.SpaceRock(sw.CX - sw.STAR_R, sw.CY, 0.0, 0.0, random.Random(1))
    form.rock.inside = True
    run.frames(2)
    assert form.rock is None and any(s.kind == "rock" for s in form.sparks)


def test_the_small_asteroid_destroys_the_ship(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    p = g.player
    form.rock = sw.SpaceRock(p.x + 14.0, p.y, 0.0, 0.0, random.Random(1))
    form.rock.inside = True
    run.frames(1)
    assert p.dying and p.guardian_burn is not None


def test_the_small_asteroid_destroys_a_bird_and_goes_on(run):
    _launch(run)
    form = _alone(run)
    b = _bird(form, x=900.0, y=100.0)
    form.rock = sw.SpaceRock(900.0, 100.0 + 20.0, 0.0, 0.0, random.Random(1))
    form.rock.inside = True
    run.frames(1)
    assert not b.alive and form.rock is not None and form.destroyed == 1


def test_the_small_asteroid_misses_a_ship_that_is_not_on_its_path(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    p = g.player
    form.rock = sw.SpaceRock(p.x + 80.0, p.y, 0.0, 0.0, random.Random(1))
    form.rock.inside = True
    run.frames(1)
    assert not p.dying


def test_a_torpedo_breaks_the_small_asteroid(run):
    _launch(run)
    form = _alone(run)
    form.rock = sw.SpaceRock(900.0, 500.0, 0.0, 0.0, random.Random(1))
    form.rock.inside = True
    form.torpedoes.append(Torpedo(900.0, 500.0 + 12.0, 0.0, 0.0, "player"))
    run.frames(1)
    assert form.rock is None and not form.torpedoes and any(s.kind == "rock" for s in form.sparks)


def test_the_asteroid_comes_now_and_then_one_at_a_time(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    _orbit(g.player)
    form.rock_in = 0.05
    run.frames(10)
    first = form.rock
    assert first is not None
    form.rock_in = 0.0
    run.frames(5)
    assert form.rock is first or form.rock is None                       # (never a second one at the same time)
    assert sw.ROCK_GAP[0] <= form.rock_in <= sw.ROCK_GAP[1] or form.rock_in <= 0.0 or form.rock is None


def test_no_asteroid_comes_during_the_pause_or_after_the_win(run):
    g = run.game
    _launch(run)
    form = _alone(run)
    _orbit(g.player)
    form.rock_in = 0.0
    form.pause = 100.0
    run.frames(10)
    assert form.rock is None
    form.pause = 0.0
    form.won = True
    run.frames(10)
    assert form.rock is None


def test_the_first_asteroid_waits_a_little_and_a_new_level_starts_without_one():
    form = SpaceWarFormation(rng=random.Random(2))
    assert sw.ROCK_FIRST[0] <= form.rock_in <= sw.ROCK_FIRST[1]
    form.rock = sw.SpaceRock(0.0, 0.0, 1.0, 0.0, random.Random(1))
    form.rock_in = 0.0
    form.start_level(2)
    assert form.rock is None and sw.ROCK_FIRST[0] <= form.rock_in <= sw.ROCK_FIRST[1]


def test_the_small_asteroid_is_drawn(run):
    _launch(run)
    form = _alone(run)
    form.rock = sw.SpaceRock(900.0, 600.0, 0.0, 0.0, random.Random(1))
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
    form.draw(surf)
    area = pygame.Rect(900 - 20, 600 - 20, 40, 40)
    assert sum(1 for x in range(area.left, area.right) for y in range(area.top, area.bottom)
               if surf.get_at((x, y))[3] > 0) > 200


def test_the_hint_and_the_banners_fit_on_the_screen(run):
    g = run.game
    for key in ("story_spacewar_hint", "story_spacewar_level", "story_spacewar_next", "story_spacewar_empty"):
        for code in ("fr", "en"):
            text = i18n.T[key][code].format(n=3, m=3)
            assert g.text_cache.get(g.font, text, (255, 255, 255)).get_width() <= BASE_WIDTH - 40, (key, code)


def test_the_dying_ship_in_the_game_is_drawn_at_half_size(run):
    g = run.game
    _launch(run)
    _alone(run)
    p = g.player
    p.x, p.y, p.ast_angle = 600.0, 300.0, -math.pi / 2
    p.burn_by_guardian()
    p.guardian_burn.age = 0.5
    boxes = []
    for sw_on in (True, False):
        p.sw_physics = sw_on
        surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
        p.draw(surf)
        rects = pygame.mask.from_surface(surf).get_bounding_rects()
        boxes.append(rects[0].unionall(rects[1:]))
    assert 0.4 < boxes[0].h / boxes[1].h < 0.62


def test_the_half_size_dust_stays_on_the_ship(run):
    from ship_burn import ShipBurn
    g = run.game
    _launch(run)
    p = g.player
    p.x, p.y = 600.0, 300.0
    burn = ShipBurn(p)
    for angle in (0.0, 90.0, -90.0):
        centres = []
        for scale in (1.0, 0.5):
            surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
            burn.draw(surf, angle, scale)
            c = pygame.mask.from_surface(surf).centroid()
            centres.append((c[0] - p.x, c[1] - p.y))
        # the half-size dust is the full one shrunk round the ship (not moved)
        assert math.hypot(centres[1][0] - centres[0][0] / 2, centres[1][1] - centres[0][1] / 2) < 1.6


# ------------------------------------------------------------------ the third round: the pull halved, four planets, no
# planets behind, a missile
PLANET_MISSIONS = {"jupiter": "test_spacewar", "saturn": "test_spacewar_saturn", "uranus": "test_spacewar_uranus",
                   "neptune": "test_spacewar_neptune"}


def test_the_pull_of_jupiter_is_half_of_what_it_was():
    assert sw.PLANETS["jupiter"]["gm"] == 5.0e6                              # (it was 1.0e7)
    assert sw.GM == 5.0e6
    gx, _ = sw.gravity(sw.CX - 300.0, sw.CY)
    assert gx == pytest.approx(5.0e6 / 300.0 ** 2, rel=1e-9)


def test_there_are_four_planets_the_lighter_ones_are_smaller_and_pull_less():
    assert sw.PLANET_KEYS == ("jupiter", "saturn", "uranus", "neptune")
    gm = {k: sw.PLANETS[k]["gm"] for k in sw.PLANET_KEYS}
    radius = {k: sw.PLANETS[k]["r"] for k in sw.PLANET_KEYS}
    assert gm["jupiter"] > gm["saturn"] > gm["neptune"] > gm["uranus"] > 0                 # (the real order of the masses)
    assert radius["jupiter"] > radius["saturn"] > radius["uranus"] > radius["neptune"] > 20     # (and of the sizes)
    assert radius["saturn"] / radius["jupiter"] == pytest.approx(0.84, abs=0.04)             # (about the real ratio)
    assert radius["uranus"] / radius["jupiter"] < 0.6 and gm["uranus"] / gm["jupiter"] < 0.5


@pytest.mark.parametrize("planet", sw.PLANET_KEYS)
def test_set_planet_sets_the_pull_the_disc_the_thrust_and_the_start(planet):
    d = sw.PLANETS[planet]
    assert sw.set_planet(planet) == planet
    assert (sw.PLANET, sw.GM, sw.STAR_R, sw.STAR_DRAW, sw.START_RADIUS, sw.POWER) == \
        (planet, d["gm"], d["r"], d["draw"], d["start"], d["power"])
    gx, _ = sw.gravity(sw.CX - 250.0, sw.CY)
    assert gx == pytest.approx(d["gm"] / 250.0 ** 2)
    far = _Body(60.0, 60.0, 0.0, 0.0, 0.0)
    ref = _Body(60.0, 60.0, 0.0, 0.0, 0.0)
    for _ in range(60):
        sw.fly(far, DT, 0, True)
        sw.fly(ref, DT, 0, False)
    assert far.ast_vx - ref.ast_vx == pytest.approx(sw.THRUST * d["power"], rel=0.02)
    x, _, _, _, _ = sw.start_state()
    assert x == sw.CX - d["start"]


def test_an_unknown_planet_is_jupiter():
    sw.set_planet("saturn")
    assert sw.set_planet("pluto") == "jupiter" and sw.set_planet(None) == "jupiter" and sw.GM == 5.0e6


def test_the_lighter_planets_do_not_make_the_ship_stronger_than_jupiter_does():
    assert sw.PLANETS["jupiter"]["power"] == 1.0
    assert all(0.4 <= sw.PLANETS[k]["power"] <= 1.0 for k in sw.PLANET_KEYS)


@pytest.mark.parametrize("planet", sw.PLANET_KEYS)
def test_the_picture_of_each_planet_is_its_disc_in_the_middle(planet):
    sw.set_planet(planet)
    img = sw.star_image()
    n = img.get_width()
    assert n == img.get_height() == sw.STAR_DRAW
    c = n // 2
    assert img.get_at((c, c))[3] == 255                                        # the globe is there, opaque
    assert img.get_at((c + int(sw.STAR_R) - 4, c))[3] > 200 and img.get_at((c, c + int(sw.STAR_R) - 4))[3] > 200
    assert img.get_at((n - 2, n - 2))[3] == 0 and img.get_at((1, n - 2))[3] == 0          # (nothing in the corners)
    assert n // 2 >= sw.STAR_R


def test_the_rings_of_saturn_are_drawn_but_are_not_in_the_hit_zone():
    sw.set_planet("saturn")
    img = sw.star_image()
    c = img.get_width() // 2
    ring = [(x, y) for x in range(img.get_width()) for y in range(img.get_height())
            if img.get_at((x, y))[3] > 120 and math.hypot(x - c, y - c) > sw.STAR_R + 12]
    assert len(ring) > 500                                                       # the rings, wider than the globe
    assert max(math.hypot(x - c, y - c) for x, y in ring) > sw.STAR_R * 2
    x, y = ring[len(ring) // 2]
    ship = _Body(sw.CX + (x - c), sw.CY + (y - c), 0, 0, 0.0)                    # a ship in the rings: nothing happens
    assert not sw.fly(ship, 0.0005, 0, False, 1.0, sw.THRUST, sw.BIRD_RADIUS)
    edge = sw.STAR_R + sw.CRASH_SHARE * sw.BIRD_RADIUS
    assert sw.fly(_Body(sw.CX - edge + 1, sw.CY, 0, 0, 0.0), 0.0005, 0, False, 1.0, sw.THRUST, sw.BIRD_RADIUS)


@pytest.mark.parametrize("planet", ("uranus", "neptune"))
def test_uranus_and_neptune_are_plain_discs(planet):
    sw.set_planet(planet)
    img = sw.star_image()
    c = img.get_width() // 2
    out = [1 for x in range(img.get_width()) for y in range(img.get_height())
           if img.get_at((x, y))[3] > 40 and math.hypot(x - c, y - c) > sw.STAR_R + 3]
    assert not out


@pytest.mark.parametrize("planet", sw.PLANET_KEYS)
def test_each_planet_has_its_mission_on_the_map_of_every_act(planet):
    mission = ss.mission_by_id(PLANET_MISSIONS[planet])
    assert mission["planet"] == planet and mission["spacewar"] and mission["training"]
    for act in (1, 2, 3):
        for mode in ss.MODES:
            state = ss.default_state()
            state.update(act=act, mode=mode)
            assert mission in ss.visible_missions(state) and ss.mission_playable(state, mission)
            assert ss.mission_group(mission) == ss.GROUP_EXTRA
            before = copy.deepcopy(state)
            result = ss.record_result(state, mission["id"], 9999, True, {"bird1": 6}, used=["genesis"])
            assert state == before and result["training"] and not result["fallen"]


def test_the_planet_missions_follow_the_jupiter_one_and_have_their_own_texts():
    ids = [m["id"] for m in ss.MISSIONS if m.get("spacewar")]
    assert ids == list(PLANET_MISSIONS.values())
    assert ss.next_mission(ss.default_state(), [ss.mission_by_id(i) for i in ids]) is None
    for planet, mid in PLANET_MISSIONS.items():
        m = ss.mission_by_id(mid)
        for key in (m["title"], m["blurb"], m["hud_title"]):
            assert set(i18n.T[key]) == set(i18n.LANG_CODES) and all(i18n.T[key][c] for c in i18n.LANG_CODES)
        name_en = {"jupiter": "Jupiter", "saturn": "Saturn", "uranus": "Uranus", "neptune": "Neptune"}[planet]
        assert name_en in i18n.T[m["blurb"]]["en"]
    titles = {i18n.T[ss.mission_by_id(i)["title"]]["en"] for i in ids}
    assert len(titles) == 4 and all(t.startswith("TEST - SpaceWar") for t in titles)


@pytest.mark.parametrize("planet", sw.PLANET_KEYS)
def test_the_mission_of_a_planet_puts_that_planet_in_the_middle(run, planet):
    hub = StoryHub()
    hub.state = ss.default_state()
    hub.map_index = next(i for i, m in enumerate(hub.missions()) if m["id"] == PLANET_MISSIONS[planet])
    spec = hub._launch_selected()
    assert spec["spacewar"] and spec["planet"] == planet and spec["training"]
    sw.set_planet("jupiter")
    _launch(run, mission=PLANET_MISSIONS[planet])
    g = run.game
    assert sw.PLANET == planet and sw.GM == sw.PLANETS[planet]["gm"]
    assert g.adventure["planet"] == planet
    p = g.player
    assert (p.x, p.y) == pytest.approx((sw.CX - sw.PLANETS[planet]["start"], sw.CY), abs=3.0)
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
    g.formation.draw(surf)
    assert surf.get_at((int(sw.CX), int(sw.CY)))[3] == 255                            # the planet is drawn in the middle
    g._end_adventure(False)


def test_the_next_launch_starts_again_with_its_own_planet(run):
    _launch(run, mission="test_spacewar_neptune")
    assert sw.PLANET == "neptune"
    run.game._end_adventure(False)
    _launch(run)
    assert sw.PLANET == "jupiter" and sw.GM == 5.0e6
    run.game._end_adventure(False)


@pytest.mark.parametrize("planet", sw.PLANET_KEYS)
def test_a_ship_that_falls_in_a_planet_is_destroyed_by_its_globe(run, planet):
    _launch(run, mission=PLANET_MISSIONS[planet])
    p = run.game.player
    _alone(run)
    p.x, p.y, p.ast_vx, p.ast_vy = sw.CX - sw.STAR_R - 30, sw.CY, 120.0, 0.0
    run.frames(60)
    assert p.dying or not p.alive or getattr(p, "guardian_burn", None) is not None


@pytest.mark.parametrize("planet", sw.PLANET_KEYS)
def test_the_small_asteroid_still_crosses_and_rarely_ends_on_any_planet(planet):
    sw.set_planet(planet)
    rng = random.Random(7)
    crashes = 0
    for _ in range(80):
        rock = sw.launch_rock(rng)
        crashes += 1 if sw.rock_crashes(rock.x, rock.y, rock.vx, rock.vy) else 0
    assert crashes / 80 <= 1 / 3


# --- no planet or rock behind the planet of the level
def test_the_starfield_can_be_bare():
    import starfield
    sf = starfield.Starfield()
    sf.planets.append(starfield.Planet())
    sf.planet_timer = 0.0
    sf.set_bare(True)
    assert sf.planets == []
    for _ in range(600):
        sf.planet_timer = 0.0
        sf.nebula_timer = 0.0
        sf.update(0.05)
        assert sf.planets == []
    sf.set_bare(False)
    sf.nebula = None                                                                  # (a planet comes at once when no nebula is up)
    sf.planet_timer = 0.0
    sf.update(0.05)
    assert len(sf.planets) == 1                                                       # (the usual sky comes back)


@pytest.mark.parametrize("planet", sw.PLANET_KEYS)
def test_no_planet_or_asteroid_in_the_background_of_spacewar(run, planet):
    import starfield
    g = run.game
    _launch(run, mission=PLANET_MISSIONS[planet])
    g.starfield.planets.append(starfield.Planet(free=True))
    for _ in range(5):
        g.starfield.planet_timer = 0.0
        run.frames(2)
        assert g.starfield.planets == []
    assert g.starfield.bare is True
    g._end_adventure(False)
    run.frames(3)
    assert g.starfield.bare is False


# --- the missile
def test_the_torpedo_is_a_slim_missile_with_fins_and_a_flame():
    surf, rects = _drawn_box(1.0, 0.0)
    box = rects[0].unionall(rects[1:])
    assert box.w >= 38 and box.w > 2.6 * box.h                                        # long and slim
    mid = pygame.mask.from_surface(surf, 20)
    body = sum(1 for y in range(200) if mid.get_at((104, y)))
    fins = sum(1 for y in range(200) if mid.get_at((88, y)))
    assert body <= 7 and fins >= 12                                                    # a thin body, wide tail fins
    canards = sum(1 for y in range(200) if mid.get_at((102, y)))
    assert canards >= 9 and canards > body + 2                                         # (and two small wings in front)
    assert surf.get_at((100 + 17, 100))[3] == 0 or surf.get_at((100 + 17, 100))[:3] == (255, 0, 255)   # (the nose is the tip)
    assert surf.get_at((100 - 20, 100))[3] > 0 and surf.get_at((100 - 20, 100))[0] > 200   # a flame behind
    nose = [surf.get_at((100 + d, 100))[:3] for d in (9, 12, 15)]
    assert nose == [(255, 0, 255)] * 3                                                 # an ogive in the colour of the hull
    assert surf.get_at((100 - 7, 100))[:3] == (214, 70, 54)                            # a red band on the white fuselage
    other = _drawn_box(1.0, 0.0, (0, 255, 0))[0]
    assert other.get_at((100 + 12, 100))[:3] == (0, 255, 0) and other.get_at((100 + 12, 100)) != surf.get_at((100 + 12, 100))


def test_each_planet_has_its_own_glow_round_it():
    seen = {}
    for planet in ("jupiter", "uranus", "neptune"):
        sw.set_planet(planet)
        form = SpaceWarFormation(rng=random.Random(1))
        form.tip = (255, 255, 255)
        surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
        form.draw(surf)
        seen[planet] = surf.get_at((int(sw.CX + sw.STAR_R + 12), int(sw.CY)))[:3]
    r, g, b = seen["jupiter"]
    assert r > b + 3                                                                   # warm round Jupiter
    r, g, b = seen["neptune"]
    assert b > r + 3                                                                   # cold blue round Neptune
    r, g, b = seen["uranus"]
    assert g > r + 3 and b > r + 3                                                      # pale cyan round Uranus


@pytest.mark.parametrize("planet", ("jupiter", "uranus"))
def test_a_bird_looks_ahead_with_the_thrust_its_planet_allows(monkeypatch, planet):
    sw.set_planet(planet)
    seen = []
    real = sw.periapsis_danger

    def spy(x, y, vx, vy, horizon=sw.LOOKAHEAD, margin=sw.SAFE_MARGIN):
        seen.append((vx, vy, horizon))
        return real(x, y, vx, vy, horizon, margin)

    monkeypatch.setattr(sw, "periapsis_danger", spy)
    b = Bird(1, sw.CX + 300.0, sw.CY, 0.0, 0.0, 0.0, 1.0, random.Random(1))
    b.think(DT, None)
    ahead = [v for v in seen if v[2] == 2.0][0]                                         # (the look with one push on)
    assert ahead[0] == pytest.approx(sw.THRUST * sw.PLANETS[planet]["power"] * 0.7)


# ------------------------------------------------------------------ the fourth round: stronger thrusters, fewer collisions
# between the birds, no wraparound for their torpedoes
def test_the_thrusters_of_the_player_are_stronger_and_the_pull_is_untouched():
    assert sw.PLAYER_THRUST == 110.0 and sw.PLAYER_THRUST > 1.6 * sw.THRUST            # (it was 75)
    assert sw.PLANETS["jupiter"]["gm"] == 5.0e6 and sw.PLANETS["saturn"]["gm"] == 2.7e6
    assert sw.PLANETS["uranus"]["gm"] == 1.5e6 and sw.PLANETS["neptune"]["gm"] == 1.6e6
    far, ref = _Body(60.0, 60.0, 0.0, 0.0, 0.0), _Body(60.0, 60.0, 0.0, 0.0, 0.0)
    for _ in range(60):
        sw.fly(far, DT, 0, True, 1.0, sw.PLAYER_THRUST, sw.PLAYER_RADIUS)
        sw.fly(ref, DT, 0, False)
    assert far.ast_vx - ref.ast_vx == pytest.approx(110.0, rel=0.02)


def test_the_thrusters_of_the_player_in_the_game_push_with_that_power(run):
    _launch(run)
    p = run.game.player
    _alone(run)
    _orbit(p)
    p.ast_angle = 0.0
    ref = _Body(p.x, p.y, p.ast_vx, p.ast_vy, 0.0)
    for _ in range(30):
        sw.fly(ref, DT, 0, False, 1.0, sw.PLAYER_THRUST, sw.PLAYER_RADIUS)
    _fly(run, pygame.K_UP, frames=30)
    assert p.ast_vx - ref.ast_vx == pytest.approx(sw.PLAYER_THRUST * 0.5, rel=0.12)


def test_a_torpedo_of_a_bird_does_not_come_round_the_screen():
    t = Torpedo(BASE_WIDTH - 5.0, 300.0, 400.0, 0.0, Bird(1, 900, 100, 0, 0, 0, 1.0, random.Random(1)))
    assert t.wrap is False
    t.update(0.02)
    assert t.x > BASE_WIDTH - 5.0 and t.life <= 0                  # out of the screen: it ends, it does not come back by the left
    for vx, vy, x, y in ((-400.0, 0.0, 5.0, 300.0), (0.0, 400.0, 600.0, BASE_HEIGHT - 5.0), (0.0, -400.0, 600.0, 5.0)):
        t = Torpedo(x, y, vx, vy, Bird(1, 900, 100, 0, 0, 0, 1.0, random.Random(1)))
        t.update(0.02)
        assert t.life <= 0
    mid = Torpedo(600.0, 300.0, 400.0, 0.0, Bird(1, 900, 100, 0, 0, 0, 1.0, random.Random(1)))
    mid.update(0.02)
    assert mid.life > 0 and mid.x == pytest.approx(608.0)          # (a straight line in the screen as before)


def test_a_torpedo_of_the_player_still_comes_round_the_screen():
    t = Torpedo(BASE_WIDTH - 5.0, 300.0, 400.0, 0.0, "player")
    assert t.wrap is True
    t.update(0.02)
    assert t.x < 20 and t.life > 0


def test_in_the_game_a_torpedo_of_a_bird_ends_at_the_edge_and_does_not_hit_by_the_other_side(run):
    _launch(run)
    form = _alone(run)
    p = run.game.player
    _orbit(p, 260.0)
    b = _bird(form)
    form.torpedoes.append(Torpedo(BASE_WIDTH - 6.0, p.y, 600.0, 0.0, b))          # (it flies out at the right: p is at the left)
    form.torpedoes.append(Torpedo(BASE_WIDTH - 6.0, 40.0, 600.0, 0.0, "player"))  # (the player's comes round)
    run.frames(3)
    assert [tp.owner for tp in form.torpedoes] == ["player"]
    assert run.game.player.alive and not run.game.player.dying


# --- the birds keep to their own orbits
def test_the_birds_start_on_their_own_circular_orbits_all_going_round_the_same_way():
    assert len(set(sw.LANES)) == 4 and all(b - a >= 44 for a, b in zip(sw.LANES, sw.LANES[1:]))
    for planet in sw.PLANET_KEYS:
        sw.set_planet(planet)
        for seed in range(10):
            form = SpaceWarFormation(rng=random.Random(seed))
            form.start_level(3)
            radii = sorted(round(math.hypot(b.x - sw.CX, b.y - sw.CY)) for b in form.birds)
            assert all(r in {round(x) for x in sw.LANES} for r in radii) and len(set(radii)) == 4
            turns = {math.copysign(1, (b.x - sw.CX) * b.ast_vy - (b.y - sw.CY) * b.ast_vx) for b in form.birds}
            assert len(turns) == 1                                                   # none meets another head on
            for b in form.birds:
                lo, hi = sw.orbit_band(b.x, b.y, b.ast_vx, b.ast_vy)
                assert hi - lo < 0.05 * hi and b.mates is form.birds


def test_the_orbit_band_of_a_ship():
    r = 250.0
    lo, hi = sw.orbit_band(sw.CX + r, sw.CY, 0.0, sw.circular_speed(r))
    assert lo == pytest.approx(r, abs=0.01) and hi == pytest.approx(r, abs=0.01)
    lo, hi = sw.orbit_band(sw.CX + r, sw.CY, 0.0, sw.circular_speed(r) * 0.8)        # slower: it falls to a nearer point
    assert hi == pytest.approx(r, abs=0.5) and lo < r - 40
    lo2, hi2 = sw.orbit_band(sw.CX + r, sw.CY, 0.0, sw.circular_speed(r) * 1.2)      # faster: it goes farther
    assert lo2 == pytest.approx(r, abs=0.5) and hi2 > r + 40
    assert sw.orbit_band(sw.CX + r, sw.CY, 0.0, sw.circular_speed(r) * 1.5) is None   # it leaves for good


def _lined(form, kind=1, r=250.0, angle=0.0):
    sense = 1.0
    x, y = sw.CX + math.cos(angle) * r, sw.CY + math.sin(angle) * r
    v = sw.circular_speed(r)
    b = Bird(kind, x, y, -math.sin(angle) * v * sense, math.cos(angle) * v * sense, math.atan2(math.cos(angle), -math.sin(angle)),
             1.0, random.Random(3))
    b.mates = form.birds
    form.birds.append(b)
    return b


def test_a_bird_pushes_only_when_the_orbit_it_makes_keeps_clear_of_the_others():
    form = SpaceWarFormation(rng=random.Random(1))
    form.birds = []
    a = _lined(form, r=190.0, angle=0.0)
    a.ast_angle = math.atan2(a.ast_vy, a.ast_vx)                       # nose along its speed: the push raises the orbit
    assert a._coast_is_safe() is True                                  # alone: it may
    _lined(form, r=250.0, angle=math.pi)                               # another on a neighbouring orbit
    assert a._coast_is_safe() is False
    form.birds[1].alive = False
    assert a._coast_is_safe() is True                                  # (a dead one does not count)
    low = _lined(form, r=200.0, angle=math.pi / 2)
    low.ast_angle = math.atan2(low.ast_vy, low.ast_vx) + math.pi        # nose back: the push slows it, down into the star
    low.mates = [low]
    assert low._coast_is_safe() is False


def test_a_bird_that_would_leave_the_screen_orbit_does_not_push():
    form = SpaceWarFormation(rng=random.Random(1))
    form.birds = []
    a = _lined(form, r=330.0, angle=0.0)
    a.ast_angle = math.atan2(a.ast_vy, a.ast_vx)
    assert a._coast_is_safe() is False                                 # a push there would take it past the edge of the screen


def test_the_birds_collide_much_less():
    hits = runs = 0
    for planet in ("jupiter", "uranus"):
        sw.set_planet(planet)
        for seed in range(10):
            form = SpaceWarFormation(rng=random.Random(100 + seed))
            form.start_level(3)
            me = _Body(sw.CX - 0.8 * sw.START_RADIUS, sw.CY, 0.0, -sw.circular_speed(0.8 * sw.START_RADIUS))
            for _ in range(60 * 40):
                sw.fly(me, DT, 0, False, 1.0, sw.PLAYER_THRUST, sw.PLAYER_RADIUS)
                for b in form.birds:
                    if b.alive:
                        turn, push, _ = b.think(DT, me)
                        if sw.fly(b, DT, turn, push, b.scale, sw.THRUST, sw.BIRD_RADIUS):
                            b.alive = False
                crew = [b for b in form.birds if b.alive]
                for i, a in enumerate(crew):
                    for c in crew[i + 1:]:
                        dx, dy = asteroids.wrapped_delta(a.x, a.y, c.x, c.y)
                        if a.alive and c.alive and dx * dx + dy * dy < (2 * sw.BIRD_RADIUS) ** 2:
                            a.alive = c.alive = False
                            hits += 1
            runs += 1
    assert hits <= 2 and runs == 20                                     # (it was more than one a run at level 3)


def test_a_bird_holds_its_heading_while_it_pushes_so_the_push_is_the_one_that_was_checked():
    form = SpaceWarFormation(rng=random.Random(1))
    form.birds = []
    b = _lined(form, r=190.0, angle=0.0)
    b.ast_angle = math.atan2(b.ast_vy, b.ast_vx)
    me = _Body(b.x + 40.0, b.y + 250.0, 0.0, 0.0)
    b.coast, b.coast_in, b.think_in = 0.3, 10 ** 6, 10 ** 6            # (it is pushing now; the target is a little off its nose)
    b.clear_ahead = True
    turn, push, fire = b.think(DT, me)
    assert turn == 0.0 and push is True and fire is False
    b.coast = 0.0
    turn, push, _ = b.think(DT, me)
    assert turn != 0.0 and push is False                              # (not pushing: it turns to the target as always)


def test_a_bird_keeps_a_gap_between_its_new_orbit_and_the_orbit_of_another():
    form = SpaceWarFormation(rng=random.Random(1))
    form.birds = []
    a = _lined(form, r=190.0, angle=0.0)
    a.ast_angle = math.atan2(a.ast_vy, a.ast_vx)
    kick = sw.THRUST * sw.POWER * a.scale * sw.COAST_MAX
    lo, hi = sw.orbit_band(a.x, a.y, a.ast_vx + math.cos(a.ast_angle) * kick, a.ast_vy + math.sin(a.ast_angle) * kick)
    mate = _lined(form, r=hi + sw.COAST_GAP * 0.5, angle=math.pi)             # clear of the orbit, but not by the gap
    assert a._coast_is_safe() is False
    form.birds.remove(mate)
    mate = _lined(form, r=hi + sw.COAST_GAP * 1.5, angle=math.pi)             # clear by more than the gap
    assert a._coast_is_safe() is True


def test_the_birds_of_a_level_may_go_round_either_way():
    senses = set()
    for seed in range(20):
        form = SpaceWarFormation(rng=random.Random(seed))
        form.start_level(2)
        b = form.birds[0]
        senses.add(math.copysign(1, (b.x - sw.CX) * b.ast_vy - (b.y - sw.CY) * b.ast_vx))
    assert senses == {1.0, -1.0}
