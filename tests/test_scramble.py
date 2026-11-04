"""The test level "Scramble" (src/scramble.py, src/scramble_view.py): a side-scrolling shoot'em up through the rock of one of
the five settings of the Lunar Lander, the ship nose to the right, a passage always wide enough, the lives of the workshop."""
import math
import random

import numpy as np
import pygame
import pytest

import lander
import scramble as sc
import scramble_view as sv
import story_state as ss
from test_smoke import run  # noqa: F401,F811  (fixture)
from test_spacewar import _Keys, _launch


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


def _course(style="rock", seed=7):
    return sc.Course(style, seed)


def _form(style="rock", seed=7):
    return sc.ScrambleFormation(style=style, seed=seed, rng=random.Random(1))


def _hold(run, frames, *names):
    """Hold the keys of these actions (bindings, keyboard of a solo player) for some frames."""
    import bindings
    keys = []
    for name in names:
        keys += list(bindings.current.keys(bindings.KB2, name))
    real = pygame.key.get_pressed
    pygame.key.get_pressed = lambda: _Keys(*keys)
    try:
        run.frames(frames)
    finally:
        pygame.key.get_pressed = real


def _launch_scramble(run, body=None, **kw):
    spec = _launch(run, "test_scramble", **kw) if body is None else None
    if body is not None:
        g = run.game
        from test_spacewar import _state
        ss.save_state(ss.story_path(1), _state(**kw))
        g.story.open_slot(1)
        g.story.map_index = [m["id"] for m in g.story.missions()].index("test_scramble")
        g.story.lander_index = list(lander.MENU_ORDER).index(body)
        g.story.screen = "lander_pick"
        g.story.pick_for = "scramble"
        spec = g.story.confirm()
        g._begin_adventure(spec)
        g.input_grace = 0.0
        g.player.infinite_lives = False
        run.frames(2)
    return spec


# ------------------------------------------------------------------ the mission
def test_the_mission_is_a_training_test_in_the_list_of_every_act():
    m = ss.mission_by_id("test_scramble")
    assert m and m["training"] and m["test"] and m["scramble"]
    assert tuple(m["acts"]) == (1, 2, 3)


def test_the_mission_opens_the_menu_of_the_setting_then_flies_it(run):
    g = run.game
    from test_spacewar import _state
    ss.save_state(ss.story_path(1), _state())
    g.story.open_slot(1)
    g.story.pane = "map"
    g.story.map_index = [m["id"] for m in g.story.missions()].index("test_scramble")
    g.story.screen = "hub"
    assert g.story.confirm() is None                    # A on the mission: the choice of the setting first
    assert g.story.screen == "lander_pick" and g.story.pick_for == "scramble"
    g.story.nav_h(1)
    spec = g.story.confirm()
    assert spec and spec["scramble"] and spec["training"] and spec["body"] == lander.MENU_ORDER[1]
    assert g.story.screen == "hub"


def test_the_lander_menu_still_opens_for_the_lander(run):
    g = run.game
    from test_spacewar import _state
    ss.save_state(ss.story_path(1), _state())
    g.story.open_slot(1)
    g.story.pane = "map"
    g.story.screen = "hub"
    g.story.pick_for = "scramble"
    g.story.map_index = [m["id"] for m in g.story.missions()].index("test_lander")
    g.story.confirm()
    assert g.story.screen == "lander_pick" and g.story.pick_for == "lander"


@pytest.mark.parametrize("body", lander.MENU_ORDER)
def test_a_flight_starts_nose_right_in_the_passage_and_scrolls(run, body):
    _launch_scramble(run, body=body)
    g = run.game
    form = g.formation
    assert isinstance(form, sc.ScrambleFormation) and form.style == body
    p = g.player
    assert p.asteroid_mode and p.scramble is form and p.ast_angle == 0.0
    assert abs(p.x - sc.START_X) < 1.0
    up, down = form.rock_overlap(p)
    assert up == 0 and down == 0                        # the ship starts clear of the rock
    cam = form.cam
    run.frames(60)
    assert abs(form.cam - cam - sc.SCROLL) < 1.0       # one second: SCROLL px
    assert p.alive and not p.dying


def test_the_lives_are_those_of_the_workshop(run):
    _launch_scramble(run)
    g = run.game
    loadout = g.story.loadout(None)
    assert g.player.lives == int(loadout.get("lives") or 1)


def test_the_scroll_is_the_same_at_60_and_at_144_hz():
    a, b = _form(), _form()
    for _ in range(60 * 30):
        a.advance(1 / 60)
    for _ in range(144 * 30):
        b.advance(1 / 144)
    assert abs(a.cam - b.cam) < 0.01
    assert abs(a.cam - 30 * sc.SCROLL) < 0.01
    # and through the braking, to the stop
    for _ in range(60 * 200):
        a.advance(1 / 60)
    for _ in range(144 * 200):
        b.advance(1 / 144)
    assert a.cam == b.cam == a.course.stop
    assert a.speed == 0.0


def test_the_braking_is_smooth_and_lasts_twice_its_distance_at_full_speed():
    f = _form()
    f.cam = f.course.brake_from
    t, last = 0.0, sc.SCROLL
    while f.cam < f.course.stop and t < 100:
        f.advance(1 / 120)
        t += 1 / 120
        assert f.speed <= last + 1e-9                   # it only slows down
        last = f.speed
    assert abs(t - 2 * sc.BRAKE / sc.SCROLL) < 0.1


def test_the_whole_course_lasts_about_two_and_a_half_minutes():
    c = _course()
    seconds = c.brake_from / sc.SCROLL + 2 * sc.BRAKE / sc.SCROLL
    assert 140 <= seconds <= 180


# ------------------------------------------------------------------ the rock
@pytest.mark.parametrize("style", lander.MENU_ORDER)
@pytest.mark.parametrize("seed", range(8))
def test_a_passage_three_ships_high_always_runs_through(style, seed):
    c = _course(style, seed)
    half = int(math.ceil(sc.GAP_WINDOW / 2 / sc.STEP))
    for i in range(c.n):
        a, b = max(0, i - half), min(c.n, i + half + 1)
        assert c.floor[a:b].min() - c.ceil[a:b].max() >= sc.GAP_MIN - 0.01, (style, seed, i * sc.STEP)
    assert sc.GAP_MIN >= 3 * sc.SHIP_SPAN


@pytest.mark.parametrize("seed", range(6))
def test_there_is_always_rock_at_the_top_and_at_the_bottom_and_no_upright_wall(seed):
    c = _course("ice", seed)
    assert c.ceil.min() >= sc.BAND_MIN - 1e-6
    assert (sc.H - c.floor).min() >= sc.BAND_MIN - 1e-6
    assert np.abs(np.diff(c.floor)).max() / sc.STEP <= sc.SLOPE_MAX + 1e-6
    assert np.abs(np.diff(c.ceil)).max() / sc.STEP <= sc.SLOPE_MAX + 1e-6


def test_the_sections_come_in_order_and_the_arena_is_open():
    c = _course()
    names = [c.section_at(x) for x in np.arange(0, c.stop, 500.0)]
    order = [n for i, n in enumerate(names) if i == 0 or names[i - 1] != n]
    assert order == list(sc.SECTION_KEYS)
    xs = np.arange(c.stop, c.stop + sc.W, 16.0)
    assert np.allclose(c.ceiling(xs), sc.ARENA_BAND[0], atol=1.0)
    assert np.allclose(c.ground(xs), sc.H - sc.ARENA_BAND[1], atol=1.0)


def test_a_seed_gives_the_same_course():
    a, b = _course("triton", 42), _course("triton", 42)
    assert np.array_equal(a.floor, b.floor) and np.array_equal(a.ceil, b.ceil)
    assert not np.array_equal(a.floor, _course("triton", 43).floor)


def test_the_cavern_has_a_ceiling_and_the_hills_hardly_any():
    c = _course("rock", 3)
    hills = np.arange(c.starts[0] + 2000, c.starts[1] - 400, 8.0)
    cavern = np.arange(c.starts[1] + 400, c.starts[2] - 400, 8.0)
    assert c.ceiling(hills).mean() < 50
    assert c.ceiling(cavern).mean() > 100


# ------------------------------------------------------------------ the ship and the rock
class _Ship:
    def __init__(self, x=sc.START_X, y=360.0):
        self.x, self.y = x, y
        self.ast_angle = 0.0
        self.ast_vx = self.ast_vy = 0.0
        self.invulnerable = 0.0
        self.is_phenix = False


def test_the_ship_stays_in_its_part_of_the_screen():
    f = _form()
    s = _Ship()
    for _ in range(300):
        f.fly(s, 1 / 60, 1.0, -1.0, 400.0)
    assert s.x == sc.X_MAX and s.y == 30.0
    for _ in range(300):
        f.fly(s, 1 / 60, -1.0, 1.0, 400.0)
    assert s.x == sc.X_MIN and s.y == sc.H - 30.0
    assert s.ast_angle == 0.0


def test_a_diagonal_is_no_faster_than_a_straight_line():
    f = _form()
    a, b = _Ship(300, 300), _Ship(300, 300)
    f.fly(a, 0.1, 1.0, 0.0, 300.0)
    f.fly(b, 0.1, 1.0, 1.0, 300.0)
    assert abs(math.hypot(b.x - 300, b.y - 300) - (a.x - 300)) < 1e-6


def test_the_rock_is_felt_at_the_edges_of_the_hull():
    f = _form()
    s = _Ship()
    f.recentre(s)
    assert f.rock_overlap(s) == (0.0, 0.0)
    ground = f.course.ground(f.cam + s.x)
    s.y = ground - 10                                   # the belly in the ground
    up, down = f.rock_overlap(s)
    assert up == 0 and down > 0
    s.y = f.course.ceiling(f.cam + s.x) + 5             # the back in the ceiling
    up, down = f.rock_overlap(s)
    assert up > 0 and down == 0


def test_the_rock_pushes_out_what_it_cannot_hurt():
    f = _form()
    s = _Ship()
    s.y = f.course.ground(f.cam + s.x) - 12
    f.push_out(s)
    assert f.rock_overlap(s) == (0.0, 0.0)


def _into_the_ground(g):
    form = g.formation
    p = g.player
    p.y = form.course.ground(form.cam + p.x) - 5


def test_touching_the_rock_costs_a_life_and_the_ship_goes_on_from_there(run):
    _launch_scramble(run)
    g = run.game
    p, form = g.player, g.formation
    p.lives = 3
    p.invulnerable = 0.0
    x = p.x
    _into_the_ground(g)
    run.frames(1)
    assert p.lives == 2 and form.deaths == 1
    assert abs(p.x - x) < 1.0                           # where it was ...
    assert form.rock_overlap(p) == (0.0, 0.0)           # ... in the middle of the passage
    assert p.invulnerable > 0
    # blinking: the rock no longer hurts, it pushes out
    _into_the_ground(g)
    run.frames(1)
    assert p.lives == 2 and form.rock_overlap(p) == (0.0, 0.0)


def test_the_last_life_ends_the_mission_with_nothing_lost(run):
    _launch_scramble(run)
    g = run.game
    p = g.player
    p.lives = 1
    p.invulnerable = 0.0
    _into_the_ground(g)
    run.frames(1)
    assert p.dying
    run.frames(60 * 8)
    assert not g.adventure


def test_the_phenix_form_is_not_hurt_by_the_rock(run, monkeypatch):
    _launch_scramble(run)
    g = run.game
    p, form = g.player, g.formation
    p.lives = 3
    p.invulnerable = 0.0
    monkeypatch.setattr(type(p), "is_phenix", property(lambda self: True))
    _into_the_ground(g)
    run.frames(1)
    assert p.lives == 3 and form.rock_overlap(p) == (0.0, 0.0)


# ------------------------------------------------------------------ the controls, the shots
def test_the_keys_move_the_ship_in_four_directions(run):
    _launch_scramble(run)
    g = run.game
    p = g.player
    p.invulnerable = 5.0
    x, y = p.x, p.y
    _hold(run, 20, "right")
    assert p.x > x + 20 and abs(p.y - y) < 40
    x = p.x
    _hold(run, 20, "left")
    assert p.x < x - 20
    form = g.formation
    form.recentre(p)
    y = p.y
    _hold(run, 8, "down")
    assert p.y > y + 15
    form.recentre(p)
    y = p.y
    _hold(run, 8, "up")
    assert p.y < y - 15


def test_the_ship_fires_to_the_right_and_the_shots_die_out_of_the_screen(run):
    _launch_scramble(run)
    g = run.game
    form, p = g.formation, g.player
    p.invulnerable = 30.0
    form.recentre(p)
    _hold(run, 2, "fire")
    assert form.shots and all(s.vx > 0 for s in form.shots)
    first = form.shots[0]
    assert abs(first.y - p.y) < 1.0 and first.x > form.cam + p.x
    _hold(run, 30, "fire")
    assert len(form.shots) <= sc.MAX_SHOTS
    run.frames(90)
    assert not form.shots


def test_a_shot_dies_in_the_rock_with_sparks():
    f = _form()
    s = sc.Shot(f.cam + 300, f.course.ground(f.cam + 300) - 2, 500.0, 0.0)
    s.y = f.course.ground(f.cam + 300) + 3
    f.shots.append(s)

    class _G:
        pass

    g = _G()
    g.formation = f
    g.stage_transition = None
    g.dt = 1 / 60
    g.player = _Ship()
    g.player.alive, g.player.dying, g.player.ast_fire = True, False, False
    g.player.invulnerable = 9.0
    g.sounds = None
    sc.tick(g)
    assert not f.shots and f.sparks


# ------------------------------------------------------------------ the end
def test_reaching_the_arena_wins_the_mission(run):
    _launch_scramble(run)
    g = run.game
    form, p = g.formation, g.player
    p.invulnerable = 1e9
    form.cam = form.course.stop - 2.0
    run.frames(int(60 * (sc.ARENA_WAIT + 1)))
    assert not g.adventure                              # over, and won (a training: nothing won either)
    assert g.story.toast == __import__("i18n").t("story_scramble_clear")


# ------------------------------------------------------------------ the picture
@pytest.mark.parametrize("style", lander.MENU_ORDER)
def test_the_view_draws_the_rock_where_the_course_says(style):
    f = _form(style, 4)
    view = sv.View(style, f.course)
    f.cam = f.course.starts[1] + 700.0
    surf = pygame.Surface((sc.W, sc.H))
    view.draw(surf, f)
    # the middle of the passage shows the sky, deep in the ground shows the rock (it is not the sky there)
    for sx in (100, 640, 1100):
        wx = f.cam + sx
        mid, gap = f.course.passage(wx)
        deep = int(min(sc.H - 3, f.course.ground(wx) + 12))
        sky = surf.get_at((sx, int(mid)))[:3]
        rock = surf.get_at((sx, deep))[:3]
        assert rock != sky


def test_the_chunks_behind_the_screen_are_let_go():
    f = _form()
    view = sv.View("rock", f.course)
    surf = pygame.Surface((sc.W, sc.H))
    for _ in range(40):
        f.cam += 200.0
        view.draw(surf, f)
    assert len(view.chunks) <= sc.W // sv.CHUNK + 4


def test_a_chunk_is_made_once():
    f = _form()
    view = sv.View("rock", f.course)
    a = view.make_chunk(3)
    assert view.make_chunk(3) is a


@pytest.mark.parametrize("style", lander.MENU_ORDER)
def test_the_menu_has_a_picture_of_each_setting(style):
    pic = sv.preview(style)
    assert pic.get_size() == sv.PREVIEW_SIZE


def test_the_texts_are_there_in_french_and_english():
    import i18n
    keys = ["story_m_scramble", "story_m_scramble_hud", "story_m_scramble_b", "scramble_pick_title", "scramble_arena",
            "story_scramble_clear", "story_scramble_retry"]
    keys += ["scramble_info_" + k for k in lander.MENU_ORDER] + ["scramble_sec_" + k for k in sc.SECTION_KEYS]
    for code in ("fr", "en"):
        i18n.set_lang(code)
        for k in keys:
            assert i18n.t(k) != k
    i18n.set_lang("fr")


# ------------------------------------------------------------------ the missile stations (step 2)
@pytest.mark.parametrize("seed", range(6))
def test_the_stations_stand_on_flat_rock_where_the_passage_stays_wide(seed):
    f = _form("rock", seed)
    c = f.course
    assert len(f.stations) >= 30
    assert [s.x for s in f.stations] == sorted(s.x for s in f.stations)
    for st in f.stations:
        assert sc.STATION_FIRST <= st.x < c.brake_from
        assert c.section_at(st.x) != "comets"
        xs = np.linspace(st.x - sc.STATION_W / 2, st.x + sc.STATION_W / 2, 7)
        edge = c.ground(xs) if st.side == "floor" else c.ceiling(xs)
        # it stands on its pad: no rock comes into it, and the rock is never far from its foot
        if st.side == "floor":
            assert edge.min() >= st.base - 1e-6 and edge.max() - st.base <= 8.0
        else:
            assert edge.max() <= st.base + 1e-6 and st.base - edge.min() <= 8.0
        # with the station standing out of the rock, the ship still fits
        span = np.linspace(st.x - sc.GAP_WINDOW, st.x + sc.GAP_WINDOW, 13)
        assert np.min(c.ground(span)) - np.max(c.ceiling(span)) >= sc.GAP_MIN + sc.STATION_H


def test_there_are_stations_on_the_ground_and_on_the_ceiling():
    sides = set()
    for seed in range(4):
        sides |= {s.side for s in _form("ice", seed).stations}
    assert sides == {"floor", "ceil"}


def test_the_stations_are_the_same_for_a_seed():
    a, b = _form("rock", 11), _form("rock", 11)
    assert [(s.x, s.side) for s in a.stations] == [(s.x, s.side) for s in b.stations]


def test_rise_time_matches_a_flight():
    m = sc.Missile(0.0, 0.0, -1)
    t = 0.0
    while -m.y < 300.0:
        m.speed = min(sc.MISSILE_SPEED[1], m.speed + sc.MISSILE_ACCEL * 1e-3)
        m.y -= m.speed * 1e-3
        t += 1e-3
    assert abs(t - sc.rise_time(300.0)) < 0.01


class _Game:
    """Just what scramble.tick asks of the game."""

    def __init__(self, form, ship):
        self.formation = form
        self.player = ship
        self.stage_transition = None
        self.dt = 1 / 60
        self.sounds = None
        self.explosions = []
        self.score = 0
        self.shake_amount = 0.0

    def _add_score(self, ship, pts):
        self.score += pts

    def _enemy_points(self, stage):
        return {1: 10, 2: 20}[stage]

    def _enemy_kill_points(self, enemy):
        return self._enemy_points(enemy.stage)

    def _boom(self, x, y, kind="enemy"):
        class _B:
            pass
        b = _B()
        b.x, b.y = x, y
        return b

    def _shield_absorb(self, *a):
        pass

    def _ship_boom(self, *a):
        pass


class _Pilot(_Ship):
    def __init__(self, *a):
        super().__init__(*a)
        self.alive, self.dying, self.ast_fire = True, False, False
        self.uses_shield = False
        self.lives = 3
        self.just_lost_life = False

    def hit(self):
        if self.is_phenix or self.invulnerable > 0:
            return False
        self.lives -= 1
        self.just_lost_life = True
        self.invulnerable = 1.8
        return False


def _station_ahead(f, side="floor", ahead=600.0):
    """The camera put so that the first station of that side is `ahead` px in front of a ship at START_X."""
    st = next(s for s in f.stations if s.side == side)
    f.stations = [st]
    f.cam = st.x - sc.START_X - ahead
    return st


def test_a_station_fires_straight_at_the_height_of_the_ship_as_it_comes():
    f = _form("rock", 2)
    st = _station_ahead(f, "floor", 1000.0)
    ship = _Pilot()
    f.recentre(ship)
    g = _Game(f, ship)
    fired_at = None
    for i in range(60 * 8):
        f.recentre(ship)
        sc.tick(g)
        if f.missiles:
            fired_at = st.x - f.cam - ship.x
            break
    assert fired_at is not None and sc.STATION_RANGE[0] <= fired_at <= sc.STATION_RANGE[1]
    m = f.missiles[0]
    assert m.dir == -1 and abs(m.x - st.x) < 3.0 and st.missiles == sc.STATION_MISSILES - 1 and not st.loaded
    # its timing: it crosses the height of the ship about when the ship gets to it
    expected = fired_at / sc.SCROLL
    assert abs(expected - (sc.rise_time(abs(ship.y - st.mouth()[1])) + st.lead)) < 0.1
    y0 = m.y
    sc.tick(g)
    assert m.y < y0                                    # up, faster and faster
    s1 = m.speed
    sc.tick(g)
    assert m.speed > s1


def test_a_station_of_the_ceiling_fires_down():
    f = _form("rock", 2)
    st = _station_ahead(f, "ceil", 900.0)
    ship = _Pilot()
    g = _Game(f, ship)
    for _ in range(60 * 8):
        f.recentre(ship)
        sc.tick(g)
        if f.missiles:
            break
    assert f.missiles and f.missiles[0].dir == 1


def test_a_station_fires_its_missiles_one_by_one_then_none():
    f = _form("rock", 2)
    st = _station_ahead(f, "floor", 300.0)
    st.lead = 99.0                                     # (it fires as soon as it may)
    ship = _Pilot()
    ship.invulnerable = 1e9
    g = _Game(f, ship)
    launches = 0
    for _ in range(60 * 12):
        n = len(f.missiles)
        f.cam = st.x - sc.START_X - 300.0              # (held in front of the ship)
        f.recentre(ship)
        sc.tick(g)
        launches += max(0, len(f.missiles) - n)
    assert launches == sc.STATION_MISSILES and st.missiles == 0


def test_a_missile_bursts_on_the_rock_over_it():
    f = _form("rock", 2)
    x = f.course.starts[1] + 900.0                     # (the cavern: a ceiling)
    f.cam = x - 600
    ceil = f.course.ceiling(x)
    f.stations = []
    f.missiles = [sc.Missile(x, ceil + 40, -1)]
    f.missiles[0].age = 1.0
    ship = _Pilot()
    ship.invulnerable = 1e9
    g = _Game(f, ship)
    for _ in range(30):
        sc.tick(g)
    assert not f.missiles and g.explosions


def test_a_shot_destroys_a_missile_for_10_points_even_a_fast_one():
    f = _form("rock", 2)
    f.stations = []
    ship = _Pilot()
    f.recentre(ship)
    m = sc.Missile(f.cam + ship.x + 300, ship.y, -1)
    m.speed = 0.0
    f.missiles = [m]
    g = _Game(f, ship)
    g.dt = 1 / 20                                       # (a shot moves ~60 px a frame: more than a missile is wide)
    shot = sc.Shot(f.cam + ship.x + 290 - 8, ship.y, 1200.0, 0.0)
    f.shots = [shot]
    sc.tick(g)
    assert not f.missiles and not f.shots
    assert g.score == sc.MISSILE_POINTS and f.kills["missile"] == 1


def test_a_shot_destroys_a_station_for_the_points_of_a_green_bird():
    f = _form("rock", 2)
    st = _station_ahead(f, "floor", 400.0)
    st.lead = -99.0                                    # (it does not fire)
    st.loaded = False                                  # (no missile on it)
    ship = _Pilot()
    l, t, r, b = st.box()
    f.shots = [sc.Shot(l - 10, (t + b) / 2, 1200.0, 0.0)]
    g = _Game(f, ship)
    sc.tick(g)
    assert not st.alive and g.score == 20 and f.kills["station"] == 1
    assert g.explosions and g.explosions[0] in f.booms


def test_a_dead_station_fires_no_more():
    f = _form("rock", 2)
    st = _station_ahead(f, "floor", 300.0)
    st.alive = False
    st.lead = 99.0
    ship = _Pilot()
    g = _Game(f, ship)
    for _ in range(120):
        sc.tick(g)
    assert not f.missiles


def test_an_explosion_on_the_rock_scrolls_with_it():
    f = _form("rock", 2)
    f.stations = []
    ship = _Pilot()
    ship.invulnerable = 1e9
    g = _Game(f, ship)
    sc._blast(g, f, f.cam + 900.0, 300.0, small=False)
    boom = g.explosions[0]
    x0 = boom.x
    for _ in range(60):
        sc.tick(g)
    assert abs((x0 - boom.x) - sc.SCROLL) < 1.0


def test_a_missile_on_the_ship_costs_a_life():
    f = _form("rock", 2)
    f.stations = []
    ship = _Pilot()
    f.recentre(ship)
    f.missiles = [sc.Missile(f.cam + ship.x, ship.y + 10, -1)]
    g = _Game(f, ship)
    sc.tick(g)
    assert ship.lives == 2 and not f.missiles


def test_the_phenix_form_burns_the_missiles_and_the_dome_takes_them(monkeypatch):
    f = _form("rock", 2)
    f.stations = []
    ship = _Pilot()
    ship.is_phenix = True
    f.recentre(ship)
    f.missiles = [sc.Missile(f.cam + ship.x, ship.y + 10, -1)]
    g = _Game(f, ship)
    sc.tick(g)
    assert ship.lives == 3 and not f.missiles and g.score == sc.MISSILE_POINTS       # the Phenix: burnt, paid
    ship.uses_shield = True
    f.missiles = [sc.Missile(f.cam + ship.x, ship.y + 10, -1)]
    sc.tick(g)
    assert ship.lives == 3 and not f.missiles and g.score == sc.MISSILE_POINTS       # the dome: taken, not paid


def test_running_into_a_station_costs_a_life():
    f = _form("rock", 2)
    st = _station_ahead(f, "floor", 0.0)
    st.lead = -99.0
    ship = _Pilot()
    l, t, r, b = st.box()
    ship.y = t - sc.SHIP_BOX[1] + 4
    f.cam = st.x - ship.x
    g = _Game(f, ship)
    g.dt = 1e-4
    sc.tick(g)
    assert ship.lives == 2


def test_the_flight_pays_the_stations_and_the_missiles_in_the_real_game(run):
    _launch_scramble(run)
    g = run.game
    form, p = g.formation, g.player
    st = _station_ahead(form, "floor", 400.0)
    st.lead = -99.0
    st.loaded = False
    l, t, r, b = st.box()
    form.shots = [sc.Shot(l - 5, (t + b) / 2, 1200.0, 0.0)]
    p.invulnerable = 30.0
    score = g.score
    run.frames(1)
    assert not st.alive and g.score - score == g._enemy_points(sc.STATION_KIND)


def test_the_stations_and_the_missiles_are_drawn():
    f = _form("rock", 2)
    st = _station_ahead(f, "floor", 400.0)
    f.missiles = [sc.Missile(st.x + 200, 300, -1)]
    surf = pygame.Surface((sc.W, sc.H))
    surf.fill((0, 0, 0))
    sv.draw_items(surf, f)
    l, t, r, b = st.box()
    assert surf.get_bounding_rect().w > 0
    x = int((l + r) / 2 - f.cam)
    assert any(surf.get_at((x, y))[:3] != (0, 0, 0) for y in range(int(t), int(b)))
    for name in ("station", "missile"):
        up, down = sv.sprite(name, False), sv.sprite(name, True)
        assert up.get_size() == down.get_size()


# ------------------------------------------------------------------ more stations, homing missiles
@pytest.mark.parametrize("seed", range(4))
def test_the_pads_cut_under_the_stations_keep_the_rock_rules(seed):
    c = _form("rock", seed).course
    half = int(math.ceil(sc.GAP_WINDOW / 2 / sc.STEP))
    for i in range(c.n):
        a, b = max(0, i - half), min(c.n, i + half + 1)
        assert c.floor[a:b].min() - c.ceil[a:b].max() >= sc.GAP_MIN - 0.01
    assert np.abs(np.diff(c.floor)).max() / sc.STEP <= sc.SLOPE_MAX + 1e-6
    assert np.abs(np.diff(c.ceil)).max() / sc.STEP <= sc.SLOPE_MAX + 1e-6


def test_a_pad_only_takes_rock_away():
    a = _course("rock", 5)
    b = _course("rock", 5)
    x = a.starts[1] + 1200.0
    b.cut_pad(x, "floor", float(b.ground(x)) + 20.0)
    b.cut_pad(x, "ceil", float(b.ceiling(x)) - 20.0)
    assert np.all(b.floor >= a.floor) and np.all(b.ceil <= a.ceil)
    assert abs(b.ground(x) - (a.ground(x) + 20.0)) < 1e-6


def _homing_run(ship_y, dx):
    """A missile fired from the ground `dx` px ahead of a still ship (in the world): its x when it reaches the ship's
    height, or None."""
    f = _form("rock", 2)
    f.stations = []
    ship = _Pilot()
    ship.y = ship_y
    ship.invulnerable = 1e9
    wx = f.cam + ship.x
    m = sc.Missile(wx + dx, float(f.course.ground(wx + dx)) - 30.0, -1)
    f.course.ceil[:] = 0.0                                # (an open sky: it flies until it is over the ship)
    f.missiles = [m]
    g = _Game(f, ship)
    f.speed = 0.0
    for _ in range(240):
        sc._missiles(g, f, 1 / 60, ship)
        if m.y <= ship_y:
            return m.x - wx, m
    return None, m


def test_a_missile_slides_towards_the_ship_but_only_a_little():
    off, m = _homing_run(300.0, 160.0)
    assert off is not None and 0 < off < 160.0            # it came nearer ...
    assert abs(m.vx) <= sc.HOMING_VX + 1e-6               # ... no faster sideways than HOMING_VX
    far, _ = _homing_run(300.0, 600.0)
    assert far > 600.0 - sc.HOMING_VX * sc.HOMING_TIME - 1.0   # a station far away cannot catch it


def test_a_missile_goes_straight_on_once_past_the_ship():
    f = _form("rock", 2)
    f.stations = []
    ship = _Pilot()
    ship.y = 500.0
    m = sc.Missile(f.cam + ship.x + 100, 400.0, -1)       # already over the ship
    f.missiles = [m]
    g = _Game(f, ship)
    sc._missiles(g, f, 1 / 60, ship)
    assert m.vx == 0.0 and not m.homing


def test_a_leaning_missile_is_drawn_leaning():
    a = sv._tilted(False, 0.0)
    b = sv._tilted(False, 0.3)
    assert a is sv.sprite("missile", False) and b.get_width() > a.get_width()
    assert sv._tilted(False, 0.3) is b                     # (made once)


# ------------------------------------------------------------------ the birds and the comets (step 3)
import scramble_birds as sb  # noqa: E402


class _BirdGame(_Game):
    """The fake game, with the points and the Bestiary of the birds."""

    def __init__(self, form, ship):
        super().__init__(form, ship)
        self.kills = {}

    def _enemy_kill_points(self, enemy):
        kind = "bird2" if enemy.stage == 2 else "bird1"
        self.kills[kind] = self.kills.get(kind, 0) + 1
        return {1: 10, 2: 20}[enemy.stage]


def _sky_form(section="cavern", into=900.0):
    f = _form("rock", 2)
    f.stations = []
    f.cam = f.course.starts[sc.SECTION_KEYS.index(section)] + into
    return f


@pytest.mark.parametrize("pattern", ("snake", "vee", "swoop"))
@pytest.mark.parametrize("stage", (1, 2))
def test_a_wave_comes_in_from_the_right_keeps_to_the_passage_and_leaves_on_the_left(pattern, stage):
    f = _sky_form()
    ship = _Pilot()
    ship.invulnerable = 1e9
    f.recentre(ship)
    g = _BirdGame(f, ship)
    f.sky.wave_in = 1e9                                  # (no other wave)
    f.sky.send_wave(pattern=pattern, stage=stage)
    birds = list(f.sky.birds)
    assert len(birds) >= 4 and all(b.stage == stage and b.x > sc.W for b in birds)
    seen = False
    for _ in range(60 * 20):
        f.recentre(ship)
        sc.tick(g)
        for b in f.sky.birds:
            if not b.waiting and 0 < b.x < sc.W:
                seen = True
                wx = f.cam + b.x
                assert f.course.ceiling(wx) + sb.BIRD_MARGIN - 1e-6 <= b.y <= f.course.ground(wx) - sb.BIRD_MARGIN + 1e-6
        if not f.sky.birds:
            break
    assert seen and not f.sky.birds                        # they crossed and are gone (or dead on the ship)


def test_the_birds_of_a_vee_dive_at_the_ship_one_after_the_other():
    f = _sky_form()
    ship = _Pilot()
    ship.invulnerable = 1e9
    g = _BirdGame(f, ship)
    f.sky.wave_in = 1e9
    f.sky.send_wave(pattern="vee", stage=1)
    starts = {}
    for i in range(60 * 6):
        f.recentre(ship)
        sc.tick(g)
        for b in f.sky.birds:
            if b.state == "dive" and id(b) not in starts:
                starts[id(b)] = i
    times = sorted(starts.values())
    assert len(times) == 5 and all(b - a >= int(sb.VEE_GAP * 60) - 1 for a, b in zip(times, times[1:]))


def test_a_shot_kills_a_bird_for_its_points_and_the_bestiary():
    f = _sky_form()
    ship = _Pilot()
    f.recentre(ship)
    g = _BirdGame(f, ship)
    b = sb.Bird(2, "snake", ship.x + 300, ship.y)
    b.base_y = b.y
    f.sky.birds = [b]
    f.sky.wave_in = 1e9
    f.shots = [sc.Shot(f.cam + ship.x + 240, ship.y, 1200.0, 0.0)]
    g.dt = 1 / 20
    sc.tick(g)
    assert not b.alive and g.score == 20 and g.kills == {"bird2": 1} and f.kills["bird2"] == 1
    assert g.explosions


def test_the_real_game_counts_a_bird_for_the_bestiary(run):
    _launch_scramble(run)
    g = run.game
    form, p = g.formation, g.player
    p.invulnerable = 30.0
    b = sb.Bird(1, "snake", p.x + 300, p.y)
    b.base_y = b.y
    form.sky.birds = [b]
    form.shots = [sc.Shot(form.cam + p.x + 250, p.y, 1200.0, 0.0)]
    run.frames(2)
    assert not b.alive and g.adventure["kills"].get("bird1") == 1


def test_the_birds_fire_at_the_ship_while_they_are_in_front_of_it():
    f = _sky_form()
    ship = _Pilot()
    ship.invulnerable = 1e9
    f.recentre(ship)
    g = _BirdGame(f, ship)
    b = sb.Bird(2, "vee", ship.x + 500, ship.y - 80)
    b.hold_x, b.base_y, b.dive_at = b.x, b.y, 1e9
    b.shot_in = 0.0
    f.sky.birds = [b]
    f.sky.wave_in = 1e9
    sc.tick(g)
    assert f.sky.shots
    s = f.sky.shots[0]
    assert s.vx < 0 and s.vy > 0                         # towards the ship (to the left, and down to it)
    assert abs(math.hypot(s.vx, s.vy) - sb.BIRD_SHOT_SPEED) < 1e-6
    b.x = b.hold_x = ship.x + 100                        # (now too close: no more)
    b.shot_in = 0.0
    f.sky.shots = []
    sc.tick(g)
    assert not f.sky.shots


def test_a_bird_or_its_shot_on_the_ship_costs_a_life():
    f = _sky_form()
    ship = _Pilot()
    f.recentre(ship)
    g = _BirdGame(f, ship)
    f.sky.wave_in = 1e9
    f.sky.birds = [sb.Bird(1, "snake", ship.x + 10, ship.y)]
    f.sky.birds[0].base_y = ship.y
    sc.tick(g)
    assert ship.lives == 2 and not any(b.alive for b in f.sky.birds)
    ship.invulnerable = 0.0
    f.sky.shots = [sb.BirdShot(ship.x + 5, ship.y, -300.0, 0.0)]
    sc.tick(g)
    assert ship.lives == 1 and not f.sky.shots


def test_the_phenix_form_burns_the_birds_and_the_dome_takes_their_shots():
    f = _sky_form()
    ship = _Pilot()
    ship.is_phenix = True
    f.recentre(ship)
    g = _BirdGame(f, ship)
    f.sky.wave_in = 1e9
    b = sb.Bird(2, "snake", ship.x + 10, ship.y)
    b.base_y = ship.y
    f.sky.birds = [b]
    sc.tick(g)
    assert ship.lives == 3 and not b.alive and g.score == 20
    ship.uses_shield = True
    f.sky.shots = [sb.BirdShot(ship.x + 5, ship.y, -300.0, 0.0)]
    sc.tick(g)
    assert ship.lives == 3 and not f.sky.shots


def test_no_wave_in_the_comets_section_nor_at_the_start_nor_at_the_braking():
    f = _sky_form("comets", 600.0)
    assert not f.sky.can_send_wave()
    f.cam = 0.0
    assert not f.sky.can_send_wave()
    f.cam = f.course.brake_from
    assert not f.sky.can_send_wave()
    f.cam = f.course.starts[1] + 900.0
    assert f.sky.can_send_wave()


def test_waves_keep_coming_through_the_course():
    f = _sky_form("hills", 1400.0)
    ship = _Pilot()
    ship.invulnerable = 1e9
    g = _BirdGame(f, ship)
    for _ in range(60 * 60):
        f.recentre(ship)
        sc.tick(g)
    assert f.sky.waves >= 5


def test_the_comets_come_in_the_comets_section_and_nothing_destroys_them():
    f = _sky_form("comets", 400.0)
    ship = _Pilot()
    ship.invulnerable = 1e9
    ship.y = 60.0                                       # (out of their way)
    g = _BirdGame(f, ship)
    met = 0
    for _ in range(60 * 6):
        met = max(met, len(f.sky.comets))
        sc.tick(g)
        ship.y = 60.0
    assert met >= 1
    c = sb.Comet(700.0, 400.0, 500.0, True)
    f.sky.comets = [c]
    f.shots = [sc.Shot(f.cam + 640.0, 400.0, 1200.0, 0.0)]
    g.dt = 1 / 20
    score = g.score
    sc.tick(g)
    assert not f.shots and c.alive and g.score == score  # the shot died on it, nothing paid
    assert c.vx < 0 and c.vy > 0


def test_a_comet_on_the_ship_costs_a_life_but_not_through_the_dome():
    f = _sky_form("comets", 400.0)
    ship = _Pilot()
    f.recentre(ship)
    g = _BirdGame(f, ship)
    f.sky.comet_in = 1e9
    f.sky.comets = [sb.Comet(ship.x + 5, ship.y, 500.0, True)]
    sc.tick(g)
    assert ship.lives == 2
    ship.invulnerable = 0.0
    ship.is_phenix = ship.uses_shield = True
    f.sky.comets = [sb.Comet(ship.x + 5, ship.y, 500.0, True)]
    sc.tick(g)
    assert ship.lives == 2 and not f.sky.comets


def test_no_comet_outside_the_comets_section():
    f = _sky_form("cavern", 900.0)
    assert not f.sky.comets_due()
    f.cam = f.course.starts[sc.SECTION_KEYS.index("comets")] + 400.0
    assert f.sky.comets_due()


def test_the_birds_the_shots_and_the_comets_are_drawn():
    f = _sky_form("comets", 400.0)
    b = sb.Bird(1, "snake", 600, 300)
    f.sky.birds = [b]
    f.sky.shots = [sb.BirdShot(400, 200, -300, 0)]
    f.sky.comets = [sb.Comet(900, 400, 500, False)]
    surf = pygame.Surface((sc.W, sc.H))
    surf.fill((0, 0, 0))
    sv.draw_items(surf, f)
    assert surf.get_at((600, 300))[:3] != (0, 0, 0) or surf.get_at((598, 300))[:3] != (0, 0, 0)
    assert surf.get_at((400, 200))[:3] != (0, 0, 0)
    assert surf.get_at((900, 400))[:3] != (0, 0, 0)
    for stage in (1, 2):
        pic = sv.bird_frames(stage)[0]
        assert pic.get_width() >= pic.get_height() - 2      # (turned to face the left: wider than... at least as wide)


# ------------------------------------------------------------------ step 4: the missile on its rail, the comets
@pytest.mark.parametrize("side", ("floor", "ceil"))
def test_a_shot_on_the_missile_standing_on_a_station_blows_up_both(side):
    f = _form("rock", 2)
    st = _station_ahead(f, side, 400.0)
    st.lead = -99.0
    assert st.loaded
    mx, my = st.mouth()
    l, t, r, b = st.box()
    assert not (t <= my <= b)                            # (the height of the missile only: above or below the station)
    ship = _Pilot()
    f.shots = [sc.Shot(mx - 40, my, 1200.0, 0.0)]
    g = _Game(f, ship)
    sc.tick(g)
    assert not st.alive and not st.loaded
    assert g.score == 20 + sc.MISSILE_POINTS and f.kills == dict(f.kills, station=1, missile=1)


def test_an_empty_station_is_only_its_box():
    f = _form("rock", 2)
    st = _station_ahead(f, "floor", 400.0)
    st.loaded = False
    assert st.full_box() == st.box()
    st.loaded = True
    l, t, r, b = st.full_box()
    assert t < st.box()[1]                               # (the missile stands above a station of the ground)


def test_twice_as_many_comets():
    assert sb.COMET_GAP == (0.375, 0.675)
    f = _sky_form("comets", 400.0)
    ship = _Pilot()
    ship.invulnerable = 1e9
    ship.y = 60.0
    g = _BirdGame(f, ship)
    counts = []
    for _ in range(60 * 8):
        sc.tick(g)
        ship.y = 60.0
        counts.append(len(f.sky.comets))
    assert max(counts) >= 3
