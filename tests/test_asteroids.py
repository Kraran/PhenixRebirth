"""The mission "Asteroids" (src/asteroids.py), the prelude of the main series of each act: a ship that flies free, rocks
that break, the miniature saucer."""
import math
import os

import pygame
import pytest

import asteroids as ast
import story_state as ss
from asteroids import AsteroidFormation, Rock, Shot
from settings import BASE_HEIGHT, BASE_WIDTH
from test_smoke import run  # noqa: F401  (fixture)

DT = 1 / 60


class _Keys:
    def __init__(self, *down):
        self.down = set(down)

    def __getitem__(self, k):
        return k in self.down


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


def _state(mode="normal", act=1, credits=0, hull="shield", dome=False, lives=None):
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    st["act"] = act
    st["credits"] = credits
    if hull == "phoenix":
        st["flags"]["phenix_owned"] = True
        st["slots"][1]["owned"] = True
        st["selected_slot"] = 1
    if dome:
        st["slots"][0]["dome"] = True
    if lives:
        st["slots"][0]["lives"] = lives
        st["slots"][1]["lives"] = lives
    return st


def _launch(run, mission="ast_1", **kw):
    g = run.game
    st = _state(**kw)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mission)
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    g.player.infinite_lives = False
    return spec


def _only(form, *rocks):
    form.rocks[:] = list(rocks)
    form.repop = False                                       # (a still field: nothing comes in)


def _rock(size, x, y, vx=0.0, vy=0.0, rng=None):
    import random
    return Rock(size, x, y, vx, vy, rng or random.Random(1))


# ------------------------------------------------------------------ on the map
@pytest.mark.parametrize("act,mid,target", ((1, "ast_1", 60), (2, "ast_2", 80), (3, "ast_3", 100)))
def test_the_launch_spec_says_asteroids_and_the_target_of_the_act(act, mid, target):
    from story import StoryHub
    hub = StoryHub()
    st = _state(act=act)
    if act == 2:
        st["flags"]["act2"] = True
    if act == 3:
        st["act3_ship"] = "shield"
        st["flags"]["ch3_ready"] = True
    ss.save_state(ss.story_path(1), st)
    hub.open_slot(1)
    hub.map_index = [m["id"] for m in hub.missions()].index(mid)
    spec = hub._launch_selected()
    assert spec["asteroids"] is True and spec["target"] == target and "test" not in spec


# ------------------------------------------------------------------ the start
def test_the_mission_starts_in_the_middle_with_four_big_rocks(run):
    g = run.game
    _launch(run)
    run.frames(3)
    p, form = g.player, g.formation
    assert isinstance(form, AsteroidFormation) and p.asteroid_mode
    assert g.stage_transition is None                        # no flight in from below
    assert (round(p.x), round(p.y)) == (BASE_WIDTH // 2, BASE_HEIGHT // 2)
    assert abs(p.ast_angle + math.pi / 2) < 1e-6              # nose up
    assert [r.size for r in form.rocks] == [3, 3, 3, 3]
    assert p.vertical_range is None


def test_no_loot_falls_in_this_mission(run):
    _launch(run)
    assert run.game.adventure["loot_plan"] is None


def test_the_ship_of_the_hangar_is_the_one_flown(run):
    for hull in ("shield", "phoenix"):
        _launch(run, hull=hull)
        run.frames(2)
        assert run.game.player.ship_id == ("shield" if hull == "shield" else "phoenix")
        run.game._end_adventure(False)


# ------------------------------------------------------------------ free flight
def _fly(run, *down, frames=1):
    """Hold keys for some frames (the game reads pygame.key.get_pressed)."""
    real = pygame.key.get_pressed
    pygame.key.get_pressed = lambda: _Keys(*down)
    try:
        run.frames(frames)
    finally:
        pygame.key.get_pressed = real


def _calm(run):
    form = run.game.formation
    form.rocks[:] = [_rock(3, 40, 40)]                       # one far rock: nothing happens
    form.saucer_in = 10 ** 6
    form.waves = 1
    form.repop = False


def test_left_and_right_turn_the_ship(run):
    _launch(run)
    _calm(run)
    p = run.game.player
    a0 = p.ast_angle
    _fly(run, pygame.K_RIGHT, frames=10)
    assert p.ast_angle - a0 == pytest.approx(ast.TURN_SPEED * 10 * DT, abs=0.02)
    a1 = p.ast_angle
    _fly(run, pygame.K_LEFT, frames=20)
    assert a1 - p.ast_angle == pytest.approx(ast.TURN_SPEED * 20 * DT, abs=0.02)


def test_up_pushes_the_ship_along_its_nose_and_it_keeps_its_speed(run):
    _launch(run)
    _calm(run)
    p = run.game.player
    _fly(run, pygame.K_UP, frames=30)
    assert p.ast_vy < -150 and abs(p.ast_vx) < 5            # nose up: it goes up
    assert p.y < BASE_HEIGHT / 2 - 30
    v = math.hypot(p.ast_vx, p.ast_vy)
    _fly(run, frames=30)                                     # nothing held: it keeps going, slowing only a little
    v2 = math.hypot(p.ast_vx, p.ast_vy)
    assert 0.5 * v < v2 < v


def test_the_push_follows_the_nose(run):
    _launch(run)
    _calm(run)
    p = run.game.player
    p.ast_angle = 0.0                                        # nose to the right
    _fly(run, pygame.K_UP, frames=20)
    assert p.ast_vx > 100 and abs(p.ast_vy) < 5


def test_the_speed_is_capped(run):
    _launch(run)
    _calm(run)
    p = run.game.player
    _fly(run, pygame.K_UP, frames=300)
    assert math.hypot(p.ast_vx, p.ast_vy) <= ast.MAX_SPEED * 1.21


def test_the_ship_comes_back_from_the_other_side(run):
    _launch(run)
    _calm(run)
    p = run.game.player
    p.x, p.y = BASE_WIDTH - 5.0, 300.0
    p.ast_vx, p.ast_vy = 200.0, 0.0
    run.frames(5)
    assert p.x < 100 and 0 <= p.x < BASE_WIDTH
    p.x, p.y = 300.0, 4.0
    p.ast_vx, p.ast_vy = 0.0, -300.0
    run.frames(5)
    assert p.y > BASE_HEIGHT - 100


def test_the_ship_is_drawn_turned_to_its_nose(run):
    _launch(run)
    _calm(run)
    g = run.game
    p = g.player
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
    p.invulnerable = 0.0
    p.ast_angle = -math.pi / 2
    p.draw(surf)
    up = pygame.mask.from_surface(surf).get_bounding_rects()[0]
    surf.fill((0, 0, 0, 0))
    p.ast_angle = 0.0
    p.draw(surf)
    right = pygame.mask.from_surface(surf).get_bounding_rects()[0]
    assert up.height > up.width and right.width > right.height           # the long ship turned a quarter of a turn
    assert abs(right.centery - p.y) < 40


def test_the_ship_is_drawn_again_on_the_other_side_at_the_edge(run):
    _launch(run)
    _calm(run)
    p = run.game.player
    p.invulnerable = 0.0
    p.x, p.y = 3.0, 300.0
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
    p.draw(surf)
    assert surf.get_at((BASE_WIDTH - 5, 300))[3] > 0 or surf.get_at((BASE_WIDTH - 10, 290))[3] > 0 or \
        any(surf.get_at((x, y))[3] for x in range(BASE_WIDTH - 20, BASE_WIDTH) for y in range(260, 340))


# ------------------------------------------------------------------ the shots
def test_fire_makes_a_shot_along_the_nose_with_the_speed_of_the_ship(run):
    _launch(run)
    _calm(run)
    g = run.game
    p = g.player
    p.ast_angle = 0.0
    p.ast_vx, p.ast_vy = 100.0, 0.0
    _hold_fire(run, 1)
    shots = [s for s in g.formation.shots if s.mine]
    assert len(shots) == 1
    s = shots[0]
    assert s.vx == pytest.approx(p.ast_vx + ast.SHOT_SPEED, abs=40) and abs(s.vy) < 5
    assert s.x > p.x                                             # it leaves from the nose


def _hold_fire(run, frames):
    """Hold the fire key of the solo keyboard for `frames` frames."""
    import bindings
    keys = bindings.current.keys(bindings.KB2, "fire")
    _fly(run, *[k for k in keys if k is not None], frames=frames)


def test_the_fire_key_makes_shots_but_no_more_than_four_at_once(run):
    _launch(run)
    _calm(run)
    g = run.game
    g.formation.rocks[:] = []
    g.formation.waves = 1
    g.formation.repop = False
    g.formation.target = 10 ** 6                                 # (no wave, no end in this test)
    g.autofire = True
    _hold_fire(run, 60)
    mine = [s for s in g.formation.shots if s.mine]
    assert 1 <= len(mine) <= ast.MAX_SHOTS
    assert len(mine) == ast.MAX_SHOTS                            # held: the four are out


def test_a_shot_dies_after_its_life_and_comes_back_by_the_other_side(run):
    _launch(run)
    _calm(run)
    form = run.game.formation
    form.shots.append(Shot(BASE_WIDTH - 5, 200, 600.0, 0.0, 1.0, True))
    run.frames(3)
    s = form.shots[0]
    assert s.x < 100                                             # wrapped
    run.frames(70)
    assert not any(x.mine for x in form.shots)


def test_without_autofire_a_held_key_makes_one_shot(run):
    _launch(run)
    _calm(run)
    g = run.game
    g.autofire = False
    _hold_fire(run, 30)
    assert sum(1 for s in g.formation.shots if s.mine) == 1


# ------------------------------------------------------------------ the rocks
def _hit(run, rock):
    """A shot that stands on `rock` for one frame, the other rocks being moved far away first."""
    form = run.game.formation
    for i, o in enumerate(form.rocks):
        if o is not rock:
            o.x, o.y, o.vx, o.vy = 60.0 + 200 * i, 80.0, 0.0, 0.0
    rock.vx = rock.vy = 0.0
    form.shots.append(Shot(rock.x, rock.y, 0, 0, 1, True))
    run.frames(1)


def test_a_big_rock_breaks_in_two_medium_ones_then_small_ones_then_nothing(run):
    _launch(run)
    g = run.game
    form = g.formation
    _only(form, _rock(3, 640, 500))
    form.waves = 1
    form.repop = False
    form.saucer_in = 10 ** 6
    _hit(run, form.rocks[0])
    assert sorted(r.size for r in form.rocks) == [2, 2] and form.destroyed == 1
    _hit(run, form.rocks[0])
    assert sorted(x.size for x in form.rocks) == [1, 1, 2] and form.destroyed == 2
    _hit(run, next(x for x in form.rocks if x.size == 1))
    assert sorted(x.size for x in form.rocks) == [1, 2] and form.destroyed == 3


def test_the_points_of_the_rocks_and_of_the_saucer(run):
    _launch(run)
    g = run.game
    form = g.formation
    form.waves = 1
    form.repop = False
    score = g.score
    for size in (3, 2, 1):
        r = _rock(size, 400, 300)
        form.rocks.append(r)
        form.break_rock(g, r)
    assert g.score - score == ast.ROCK_POINTS[3] + ast.ROCK_POINTS[2] + ast.ROCK_POINTS[1] == 70
    form.saucer = ast.Saucer(True, form.rng)
    form.blow_saucer(g)
    assert g.score - score == 70 + ast.SAUCER_POINTS and form.saucer is None


def test_every_piece_counts_for_the_target(run):
    _launch(run)
    g = run.game
    form = g.formation
    form.waves = 1
    form.repop = False
    _only(form, _rock(3, 300, 300))
    score = g.score
    while form.rocks:                                            # one big rock, broken down to nothing
        form.break_rock(g, form.rocks[0])
    assert form.destroyed == 1 + 2 + 4
    assert g.score - score == 10 + 2 * 20 + 4 * 40


def test_the_rocks_wrap_around_the_screen(run):
    _launch(run)
    form = run.game.formation
    r = _rock(2, BASE_WIDTH - 2, 300, 120.0, 0.0)
    _only(form, r)
    form.waves = 1
    form.repop = False
    run.frames(5)
    assert r.x < 50
    r.x, r.y, r.vx, r.vy = 300.0, 2.0, 0.0, -120.0
    run.frames(5)
    assert r.y > BASE_HEIGHT - 50


def test_rocks_come_in_from_outside_when_the_field_gets_thin(run):
    _launch(run)
    g = run.game
    form = g.formation
    p = g.player
    p.invulnerable = 100.0
    run.frames(2)
    form.rocks[:] = []
    seen = []
    for _ in range(60 * 4):
        run.frames(1)
        seen += [r for r in form.rocks if r.entering and r not in seen]
    assert seen, "nothing came in"
    assert all(r.size == 3 for r in seen)
    assert form.field_mass() >= ast.MASS_LOW - 4                 # the field is topped up again


def test_a_rock_that_comes_in_starts_beyond_an_edge_and_slides_in_without_wrapping(run):
    _launch(run)
    g = run.game
    form = g.formation
    for _ in range(300):                                          # (whatever the edge it is drawn at)
        form.rocks[:] = []
        form.spawn_rock(g.player)
        r = form.rocks[0]
        assert r.entering
        outside = r.x < -r.radius or r.x > BASE_WIDTH + r.radius or r.y < -r.radius or r.y > BASE_HEIGHT + r.radius
        assert outside                                           # wholly out of the screen
        lane = ast.ROCK_RADIUS[3] + 40                            # ... and clear of the corners, so that it does come in
        if r.x < 0 or r.x > BASE_WIDTH:
            assert lane <= r.y <= BASE_HEIGHT - lane
        else:
            assert lane <= r.x <= BASE_WIDTH - lane
        for _step in range(60 * 30):
            x0, y0 = r.x, r.y
            r.update(DT)
            assert abs(r.x - x0) < 5 and abs(r.y - y0) < 5       # it never jumps to the other side
            if not r.entering:
                break
        assert not r.entering and r.radius <= r.x <= BASE_WIDTH - r.radius and r.radius <= r.y <= BASE_HEIGHT - r.radius


def test_a_rock_coming_in_is_drawn_only_where_it_is(run):
    _launch(run)
    g = run.game
    form = g.formation
    form.rocks[:] = []
    r = _rock(3, -20.0, 300.0)                                   # half in on the left
    r.entering = True
    form.rocks.append(r)
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    form.draw(surf)
    left = any(surf.get_at((x, y))[:3] != (0, 0, 0) for x in range(0, 40) for y in range(250, 350))
    right = any(surf.get_at((x, y))[:3] != (0, 0, 0) for x in range(BASE_WIDTH - 60, BASE_WIDTH) for y in range(240, 360))
    assert left and not right                                    # no ghost on the other side
    r.entering = False                                           # once in, the usual wrap
    surf.fill((0, 0, 0))
    form.draw(surf)
    assert any(surf.get_at((x, y))[:3] != (0, 0, 0) for x in range(BASE_WIDTH - 60, BASE_WIDTH) for y in range(240, 360))


def test_a_rock_that_is_not_yet_in_cannot_hit_the_ship_on_the_other_side(run):
    _launch(run, lives=3)
    _calm(run)
    g = run.game
    p = g.player
    p.lives = 3
    p.invulnerable = 0.0
    p.x, p.y = BASE_WIDTH - 10.0, 300.0
    r = _rock(3, -40.0, 300.0)
    r.entering = True
    g.formation.rocks.append(r)
    run.frames(1)
    assert p.lives == 3


def test_rocks_do_not_come_in_while_the_field_is_full(run):
    _launch(run)
    g = run.game
    form = g.formation
    g.player.invulnerable = 100.0
    run.frames(60 * 3)
    assert form.field_mass() >= ast.MASS_LOW and not any(r.entering for r in form.rocks)


def test_one_rock_at_a_time_with_a_pause_between(run):
    _launch(run)
    g = run.game
    form = g.formation
    g.player.invulnerable = 100.0
    run.frames(2)
    form.rocks[:] = []
    run.frames(int(ast.REPOP_GAP[0] * 60) // 2)
    assert form.rocks == []                                      # not the very next frame
    n = []
    for _ in range(60 * 3):
        run.frames(1)
        n.append(len(form.rocks))
    assert max(n) >= 1 and all(b - a <= 1 for a, b in zip(n, n[1:]) if b >= a)


def test_no_rock_comes_in_once_the_target_is_reached(run):
    _launch(run)
    g = run.game
    form = g.formation
    run.frames(2)
    form.destroyed = form.target
    form.rocks[:] = [_rock(2, 40, 40)]                           # (one left: the end has not come yet)
    g.player.invulnerable = 100.0
    run.frames(int((ast.REPOP_GAP[1] + 0.5) * 60))
    assert len(form.rocks) == 1 and form.waves == 1              # a thin field, but the target is reached: nothing comes


def test_after_the_target_a_rock_that_is_hit_is_just_gone(run):
    _launch(run)
    g = run.game
    form = g.formation
    run.frames(2)
    form.destroyed = form.target
    big = _rock(3, 300, 300)
    _only(form, big)
    form.break_rock(g, big)
    assert form.rocks == []
    assert form.destroyed == form.target + 1


def test_the_hit_that_reaches_the_target_does_not_break_the_rock_either(run):
    _launch(run)
    g = run.game
    form = g.formation
    run.frames(2)
    form.destroyed = form.target - 1
    big = _rock(3, 300, 300)
    _only(form, big)
    form.break_rock(g, big)
    assert form.reached and form.rocks == []


def test_the_counter_is_the_target_then_what_is_left(run):
    from i18n import t
    _launch(run)
    g = run.game
    run.frames(3)
    form = g.formation
    assert form.remaining() == form.target
    form.destroyed = 12
    assert form.remaining() == form.target - 12
    form.destroyed = form.target
    form.rocks[:] = [_rock(2, 300, 300), _rock(1, 500, 300)]
    assert form.remaining() == 2
    run.frames(2)                                                # drawn with its text without a crash
    assert t("story_asteroids_hud").format(n=3, m=60) in ("ASTÉROÏDES : 3/60", "ASTEROIDS: 3/60")


# ------------------------------------------------------------------ hits on the ship
def _on_ship(run, size=2):
    g = run.game
    p = g.player
    p.invulnerable = 0.0
    r = _rock(size, p.x, p.y)
    _only(g.formation, r)
    g.formation.waves = 1
    g.formation.repop = False
    g.formation.saucer_in = 10 ** 6
    return r


def test_a_rock_on_the_ship_takes_a_life_and_the_ship_comes_back_to_the_middle(run):
    _launch(run, lives=3)
    g = run.game
    p = g.player
    p.lives = 3
    p.x, p.y = 200.0, 200.0
    p.ast_vx = 150.0
    _on_ship(run)
    run.frames(1)
    assert p.lives == 2 and p.invulnerable > 0 and not p.dying
    assert (round(p.x), round(p.y)) == (BASE_WIDTH // 2, BASE_HEIGHT // 2)
    assert p.ast_vx == 0 and p.ast_vy == 0 and abs(p.ast_angle + math.pi / 2) < 1e-6
    assert g.adventure["life_lost"] is True


def test_the_ship_is_safe_while_it_is_invulnerable(run):
    _launch(run, lives=3)
    g = run.game
    p = g.player
    p.lives = 3
    r = _on_ship(run)
    p.invulnerable = 1.0
    run.frames(1)
    assert p.lives == 3 and r in g.formation.rocks


def test_the_last_life_ends_the_mission(run):
    _launch(run)
    g = run.game
    p = g.player
    p.lives = 1
    _on_ship(run)
    run.frames(1)
    assert p.dying
    for _ in range(120):
        run.frames(1)
        if g.adventure is None:
            break
    assert g.adventure is None


def test_the_dome_of_the_shield_absorbs_the_rocks(run):
    _launch(run, dome=True)
    g = run.game
    p = g.player
    _calm(run)
    p.lives = 2
    p.phenix_gauge = 10.0
    assert p.try_activate_phenix()
    run.frames(30)
    assert p.is_phenix and p.uses_shield
    p.invulnerable = 0.0
    r = _rock(1, p.x + 20, p.y)
    g.formation.rocks.append(r)
    run.frames(1)
    assert p.lives == 2 and r not in g.formation.rocks         # the rock is gone, the ship is intact
    assert not p.dying
    assert p.shield_ripple_cd > 0                                # ... and the dome rippled where it was struck


def test_a_shot_of_the_saucer_takes_a_life(run):
    _launch(run, lives=3)
    g = run.game
    p = g.player
    p.lives = 3
    p.invulnerable = 0.0
    _calm(run)
    g.formation.shots.append(Shot(p.x, p.y, 0.0, 0.0, 1.0, False))
    run.frames(1)
    assert p.lives == 2


def test_my_shot_does_not_hurt_my_ship(run):
    _launch(run, lives=3)
    g = run.game
    p = g.player
    p.lives = 3
    p.invulnerable = 0.0
    _calm(run)
    g.formation.shots.append(Shot(p.x, p.y, 0.0, 0.0, 1.0, True))
    run.frames(1)
    assert p.lives == 3


# ------------------------------------------------------------------ the saucer
def test_the_saucer_comes_now_and_then_crosses_and_leaves(run):
    _launch(run)
    _calm(run)
    form = run.game.formation
    form.saucer_in = 0.01
    run.game.player.invulnerable = 1000.0
    run.frames(3)
    assert form.saucer is not None
    assert form.saucer_in >= ast.SAUCER_GAP[0] - 0.1                # the next one is far away
    for _ in range(60 * 14):
        run.frames(1)
        if form.saucer is None:
            break
    assert form.saucer is None


def test_the_saucer_comes_four_or_five_times_in_a_mission_of_a_minute_and_a_half(run):
    import invaders
    _launch(run)
    form = run.game.formation
    assert ast.SAUCER_FIRST[0] >= 8 and form.saucer_in >= ast.SAUCER_FIRST[0]      # not in the first seconds
    cross = invaders.SAUCER_PASS                                   # (the gap is counted once the last one has left)
    for gap, first in ((ast.SAUCER_GAP[0], ast.SAUCER_FIRST[0]), (ast.SAUCER_GAP[1], ast.SAUCER_FIRST[1]),
                       ((sum(ast.SAUCER_GAP)) / 2, sum(ast.SAUCER_FIRST) / 2)):
        t, n = first, 0
        while t < 90:
            n += 1
            t += cross + gap
        assert 4 <= n <= 6, (gap, first, n)
    assert sum(ast.SAUCER_GAP) / 2 < 18.0                           # a little more often than the first version (18 s)


def test_the_saucer_fires_at_the_ship(run):
    _launch(run)
    _calm(run)
    g = run.game
    form = g.formation
    form.saucer = ast.Saucer(True, form.rng)
    form.saucer.x, form.saucer.y = 300.0, 150.0
    form.saucer.fire_in = 0.0
    g.player.invulnerable = 5.0
    run.frames(2)
    foe = [s for s in form.shots if not s.mine]
    assert len(foe) == 1
    ship = (g.player.x - 300.0, g.player.y - 150.0)
    assert foe[0].vx * ship[0] + foe[0].vy * ship[1] > 0           # it goes more or less toward the ship


def test_a_shot_that_hits_the_saucer_blows_it_and_pays_a_hundred(run):
    _launch(run)
    _calm(run)
    g = run.game
    form = g.formation
    form.saucer = ast.Saucer(True, form.rng)
    form.saucer.x, form.saucer.y = 640.0, 200.0
    score = g.score
    form.shots.append(Shot(640.0, 200.0, 0, 0, 1, True))
    run.frames(1)
    assert form.saucer is None and g.score - score >= 100
    assert form.destroyed == 0                                    # (it does not count for the rocks)


def test_the_saucer_in_the_ship_takes_a_life_and_is_blown(run):
    _launch(run, lives=3)
    _calm(run)
    g = run.game
    p = g.player
    p.lives = 3
    p.invulnerable = 0.0
    form = g.formation
    form.saucer = ast.Saucer(True, form.rng)
    form.saucer.x, form.saucer.y = p.x, p.y
    run.frames(1)
    assert p.lives == 2 and form.saucer is None


def test_no_saucer_comes_once_the_target_is_reached(run):
    _launch(run)
    _calm(run)
    form = run.game.formation
    form.destroyed = form.target
    form.rocks[:] = [_rock(3, 40, 40)]
    form.saucer_in = 0.0
    run.frames(30)
    assert form.saucer is None


def test_the_end_waits_for_the_saucer_to_leave(run):
    _launch(run)
    _calm(run)
    form = run.game.formation
    form.destroyed = form.target
    form.rocks[:] = []
    form.saucer = ast.Saucer(True, form.rng)
    form.saucer.x = 300.0
    run.frames(5)
    run.frames(int(ast.END_DELAY * 60) + 10)
    assert not form.all_dead() and run.game.adventure is not None        # the saucer is still there: no end


# ------------------------------------------------------------------ the end
def _until_over(run, frames=60 * 25):
    g = run.game
    for _ in range(frames):
        run.frames(1)
        if g.adventure is None:
            return True
    return False


def test_the_mission_is_over_when_the_target_is_reached_and_the_screen_is_empty(run):
    from i18n import t
    _launch(run, credits=700)
    _calm(run)
    g = run.game
    form = g.formation
    form.destroyed = form.target - 1
    big = _rock(3, 800, 300)
    _only(form, big)
    form.break_rock(g, big)                                      # the last: the rock is gone, no more piece, no repop
    assert form.reached and form.rocks == []
    run.frames(10)
    assert form.rocks == [] and form.waves == 1 and g.adventure is not None      # the short pause, the last explosion
    assert _until_over(run, 60 * 3)
    st = g.story.state
    gained = st["credits"] - 700
    assert gained > 0 and g.story.toast == t("story_clear").format(pts=gained)       # the points are paid, like any mission
    assert "ast_1" in st["cleared"] and ss.flag(st, "ast_s1") and ss.mission_playable(st, ss.mission_by_id("dome_1"))


def test_the_rocks_left_must_be_cleared_before_the_end(run):
    _launch(run)
    _calm(run)
    g = run.game
    form = g.formation
    form.destroyed = form.target
    far = _rock(2, 40, 40)
    _only(form, far)
    run.frames(60 * 6)
    assert g.adventure is not None and not form.all_dead()       # a rock is still there: the mission goes on
    assert form.remaining() == 1
    form.break_rock(g, far)
    assert _until_over(run)


def test_the_mission_just_ends_no_flight_up_and_no_level_call(run):
    _launch(run)
    _calm(run)
    g = run.game
    p = g.player
    form = g.formation
    form.destroyed = form.target
    form.rocks[:] = []
    p.ast_angle, p.ast_vx, p.ast_vy = 0.3, 200.0, 100.0
    called = []
    orig_vo = g._play_level_vo
    g._play_level_vo = lambda *a, **k: called.append(a)
    seen = set()
    for _ in range(60 * 4):
        run.frames(1)
        seen.add(g.stage_transition)
        if g.adventure is None:
            break
    g._play_level_vo = orig_vo
    assert g.adventure is None and "fly_up" not in seen and not called
    assert g.menu_screen == "story_hub"


def test_the_ship_keeps_its_course_and_its_controls_until_the_end(run):
    _launch(run)
    _calm(run)
    g = run.game
    p = g.player
    form = g.formation
    form.destroyed = form.target
    form.rocks[:] = []
    p.ast_angle, p.ast_vx, p.ast_vy = 0.3, 200.0, 0.0
    run.frames(20)
    assert abs(p.ast_angle - 0.3) < 1e-6 and p.ast_vx > 150          # no automatic turn nose-up any more
    _fly(run, pygame.K_RIGHT, frames=5)
    assert p.ast_angle > 0.3 + 0.2


def test_a_lost_mission_in_normal_mode_costs_five_percent(run):
    from i18n import t
    _launch(run, credits=900)
    g = run.game
    p = g.player
    p.lives = 1
    _on_ship(run)
    run.frames(1)
    assert _until_over(run, 60 * 6)
    st = g.story.state
    assert st["credits"] == 855 and not st.get("fallen") and "ast_1" not in st["cleared"]
    assert g.story.toast == t("story_fail_pen").format(pts=45)


def test_a_veteran_falls_in_the_asteroid_belt(run):
    _launch(run, mode="veteran", credits=900)
    g = run.game
    p = g.player
    p.lives = 1
    _on_ship(run)
    run.frames(1)
    assert _until_over(run, 60 * 6)
    st = g.story.state
    assert st["credits"] == 900 and st.get("fallen")


# ------------------------------------------------------------------ the result
def test_the_result_of_the_mission_is_the_usual_one():
    for mode in ("normal", "novice", "veteran"):
        st = _state(mode=mode, credits=1000)
        res = ss.record_result(st, "ast_1", 700, True, kills={"drone": 3})
        assert res["cleared"] is True and res["first"] is True and res["score"] == 700 and res["lost"] == 0
        assert st["credits"] == 1700 and "ast_1" in st["cleared"] and ss.flag(st, "ast_s1")
        assert st["log"] == [{"key": "story_log_ast1"}]
        res = ss.record_result(st, "ast_1", 500, True)                  # again: paid again, nothing else
        assert res["first"] is False and st["credits"] == 2200 and st["cleared"].count("ast_1") == 1
        assert len(st["log"]) == 1


@pytest.mark.parametrize("mode,lost,fallen", (("normal", 50, False), ("novice", 20, False), ("veteran", 0, True)))
def test_a_lost_result_follows_the_rules_of_the_mode(mode, lost, fallen):
    st = _state(mode=mode, credits=1000)
    res = ss.record_result(st, "ast_1", 700, False)
    assert res["cleared"] is False and res["lost"] == lost and res["fallen"] is fallen
    assert st["credits"] == 1000 - lost and "ast_1" not in st["cleared"] and not ss.flag(st, "ast_s1")
    assert bool(st.get("fallen")) is fallen


def test_the_enemies_met_in_the_belt_still_go_into_the_bestiary():
    st = _state()
    kind = ss.BESTIARY[0]["id"]
    before = ss.encounters(st, kind)
    ss.record_result(st, "ast_1", 0, True, kills={kind: 2})
    assert ss.encounters(st, kind) == before + 2


def test_other_missions_keep_the_usual_result():
    st = _state(credits=100)
    res = ss.record_result(st, "m1", 400, True)
    assert res["cleared"] is True and st["credits"] == 500


# ------------------------------------------------------------------ the picture
def _hud_texts(run, frames=2):
    import text_cache as tc_mod
    seen = []
    orig = tc_mod.TextCache.get

    def spy(self, font, text, *a, **k):
        seen.append(str(text))
        return orig(self, font, text, *a, **k)

    tc_mod.TextCache.get = spy
    try:
        run.frames(frames)
    finally:
        tc_mod.TextCache.get = orig
    return seen


def test_the_counter_counts_up_to_the_target_then_tells_what_is_left(run):
    from i18n import t
    _launch(run)
    _calm(run)
    g = run.game
    run.frames(2)
    g.formation.destroyed = 7
    assert t("story_asteroids_hud").format(n=7, m=60) in _hud_texts(run)
    g.formation.destroyed = g.formation.target
    g.formation.rocks[:] = [_rock(2, 40, 40), _rock(1, 90, 40)]
    seen = _hud_texts(run)
    assert t("story_swarm_left").format(n=2) in seen
    assert not any(x.startswith(t("story_asteroids_hud").split("{")[0]) for x in seen)


def test_the_field_draws_rocks_the_saucer_and_the_shots(run):
    _launch(run)
    _calm(run)
    form = run.game.formation
    form.saucer = ast.Saucer(True, form.rng)
    form.saucer.x, form.saucer.y = 600.0, 300.0
    form.shots.append(Shot(300, 300, 0, 0, 1, True))
    form.shots.append(Shot(900, 300, 0, 0, 1, False))
    form.rocks.append(_rock(3, 1000, 500))
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    form.draw(surf)
    for x, y in ((600, 300), (300, 300), (900, 300), (1000, 500)):
        patch = [surf.get_at((x + dx, y + dy))[:3] for dx in range(-6, 7, 3) for dy in range(-6, 7, 3)]
        assert any(c != (0, 0, 0) for c in patch), (x, y)


def test_a_rock_is_drawn_on_both_sides_at_the_edge(run):
    _launch(run)
    _calm(run)
    form = run.game.formation
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    form.rocks[:] = [_rock(3, 3, 400)]
    form.draw(surf)
    right = any(surf.get_at((x, y))[:3] != (0, 0, 0) for x in range(BASE_WIDTH - 30, BASE_WIDTH) for y in range(370, 430))
    assert right


def test_the_stars_follow_the_real_movement_of_the_ship_through_the_wrap(run):
    _launch(run)
    _calm(run)
    g = run.game
    p = g.player
    run.frames(2)
    p.x, p.y = BASE_WIDTH - 40.0, 360.0
    p.ast_vx, p.ast_vy = 300.0, 0.0
    run.frames(1)
    seen = [g._ast_px]
    wrapped = False
    for _ in range(30):
        run.frames(1)
        wrapped = wrapped or p.x < 100
        seen.append(g._ast_px)
    assert wrapped and p.x < 200                                  # the ship came back by the left side
    steps = [b - a for a, b in zip(seen, seen[1:])]
    assert all(0 < d < 8 for d in steps) and seen[-1] > BASE_WIDTH   # ... the stars went on, no jump back across the screen


# ------------------------------------------------------------------ the sprites and their tool
def test_the_sprites_are_there_with_their_sizes():
    here = os.path.join(os.path.dirname(__file__), "..", "assets", "sprites", "asteroids")
    for size, cell in (("L", 132), ("M", 78), ("S", 44)):
        for v in (0, 1):
            img = pygame.image.load(os.path.join(here, f"rock_{size}_{v}.png"))
            assert img.get_size() == (cell * ast.ROCK_FRAMES, cell)


def test_every_rock_size_gives_its_frames():
    for size in (1, 2, 3):
        for v in range(ast.ROCK_VARIANTS):
            frames = ast.rock_frames(size, v)
            assert len(frames) == ast.ROCK_FRAMES and frames[0].get_width() == frames[0].get_height()


def test_the_generator_is_deterministic(tmp_path):
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
    import make_asteroids as mk
    a, b = tmp_path / "a", tmp_path / "b"
    mk.build(str(a), frames=3, variants=1)
    mk.build(str(b), frames=3, variants=1)
    names = sorted(os.listdir(a))
    assert names and names == sorted(os.listdir(b))
    for n in names:
        assert (a / n).read_bytes() == (b / n).read_bytes()


def test_the_texts_exist_in_french_and_english():
    from i18n import T
    for key in ("story_m_ast1", "story_m_ast2", "story_m_ast3", "story_m_ast_hud", "story_m_ast_b", "story_log_ast1",
                "story_log_ast2", "story_log_ast3", "story_asteroids_hud"):
        v = T[key]
        assert v["fr"] and v["en"] and v["fr"] != v["en"], key


# ------------------------------------------------------------------ across the edges of the screen
def test_a_rock_on_the_other_side_of_the_edge_hits_the_ship(run):
    _launch(run, lives=3)
    _calm(run)
    g = run.game
    p = g.player
    p.lives = 3
    p.invulnerable = 0.0
    p.x, p.y = 4.0, 300.0
    r = _rock(2, BASE_WIDTH - 8.0, 300.0)
    g.formation.rocks.append(r)
    run.frames(1)
    assert p.lives == 2


def test_a_rock_over_the_top_edge_is_hit_by_a_shot_from_the_bottom(run):
    _launch(run)
    _calm(run)
    g = run.game
    form = g.formation
    r = _rock(2, 500.0, 3.0)
    _only(form, r)
    form.shots.append(Shot(500.0, BASE_HEIGHT - 6.0, 0, 0, 1, True))
    run.frames(1)
    assert form.destroyed == 1


def test_a_rock_over_the_side_edge_is_hit_by_a_shot_from_the_other_side(run):
    _launch(run)
    _calm(run)
    g = run.game
    form = g.formation
    r = _rock(2, 3.0, 500.0)
    _only(form, r)
    form.shots.append(Shot(BASE_WIDTH - 6.0, 500.0, 0, 0, 1, True))
    run.frames(1)
    assert form.destroyed == 1


# ------------------------------------------------------------------ small things
def test_the_hit_box_of_the_saucer_is_a_flat_box_not_a_band(run):
    _launch(run)
    _calm(run)
    g = run.game
    form = g.formation
    form.saucer = ast.Saucer(True, form.rng)
    form.saucer.x, form.saucer.y = 640.0, 300.0
    form.saucer.vx = 0.0
    form.shots.append(Shot(640.0, 300.0 + ast.SAUCER_HALF[1] + 40, 0, 0, 1, True))      # far above / below it
    form.shots.append(Shot(640.0 + ast.SAUCER_HALF[0] + 40, 300.0, 0, 0, 1, True))     # far to the side
    run.frames(1)
    assert form.saucer is not None


def test_nothing_moves_in_the_field_during_the_flight_up(run):
    _launch(run)
    _calm(run)
    g = run.game
    form = g.formation
    r = form.rocks[0]
    r.vx = 100.0
    x0, t0 = r.x, form.time
    g.stage_transition = "fly_up"
    p = g.player
    p.lives = 3
    p.invulnerable = 0.0
    form.rocks.append(_rock(2, p.x, p.y))
    form.saucer_in = 0.0
    for _ in range(3):
        g.dt = DT
        ast.tick(g)
    assert form.time == t0 and r.x == x0 and p.lives == 3 and form.saucer is None


# ------------------------------------------------------------------ the field is topped up as it is destroyed
def _after(run, seconds):
    g = run.game
    g.player.invulnerable = 1000.0
    for _ in range(int(seconds * 60)):
        run.frames(1)


def test_a_field_with_little_left_gets_a_rock_and_a_full_one_does_not(run):
    _launch(run)
    g = run.game
    form = g.formation
    run.frames(2)
    form.saucer_in = 10 ** 6
    # 2 medium + 1 small = 5: thin
    form.rocks[:] = [_rock(2, 300, 200), _rock(2, 900, 200), _rock(1, 600, 500)]
    assert form.field_mass() == 5 < ast.MASS_LOW
    _after(run, ast.REPOP_GAP[1] + 0.5)
    assert any(r.size == 3 for r in form.rocks)
    # 2 big + 1 medium = 10: full enough
    form.rocks[:] = [_rock(3, 300, 200), _rock(3, 900, 200), _rock(2, 600, 500)]
    for r in form.rocks:
        r.vx = r.vy = 0.0
    assert form.field_mass() >= ast.MASS_LOW
    _after(run, ast.REPOP_GAP[1] + 1.0)
    assert len(form.rocks) == 3


def test_each_new_rock_waits_for_its_pause(run):
    _launch(run)
    g = run.game
    form = g.formation
    run.frames(2)
    form.saucer_in = 10 ** 6
    form.rocks[:] = []
    form.spawn_in = None
    _after(run, ast.REPOP_GAP[0] * 0.9)
    assert form.rocks == []                                      # the first one is not instant
    # step by step until the first one comes: it must be there before the longest pause is over, and alone
    # (a second pause starts only then, so waiting a fixed time would let a second rock in at random)
    g.player.invulnerable = 1000.0
    for _ in range(int((ast.REPOP_GAP[1] - ast.REPOP_GAP[0] * 0.9 + 0.2) * 60)):
        run.frames(1)
        if form.rocks:
            break
    assert len(form.rocks) == 1


def test_the_target_is_sixty_everywhere():
    assert ast.TARGET == 60 == ss.mission_by_id("ast_1")["target"]


def test_the_formation_of_the_mission_has_the_target_of_the_map(run):
    _launch(run)
    assert run.game.formation.target == 60


def test_a_full_field_forgets_the_pause_and_the_next_thinning_starts_a_new_one(run):
    _launch(run)
    g = run.game
    form = g.formation
    run.frames(2)
    form.saucer_in = 10 ** 6
    form.spawn_in = 0.05                                         # a stale count-down from an earlier thin moment
    run.frames(2)                                                # the field is full: it is forgotten
    assert form.spawn_in is None
    for r in form.rocks:
        r.vx = r.vy = 0.0
    form.rocks[:] = []
    _after(run, ast.REPOP_GAP[0] * 0.9)
    assert form.rocks == []
