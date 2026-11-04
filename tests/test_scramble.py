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
