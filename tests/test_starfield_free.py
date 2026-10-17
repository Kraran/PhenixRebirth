"""The free background of the Asteroids mission (starfield.Starfield.set_free): no top-to-bottom scrolling, the sky
only moves with the ship, in every direction; the two rocks of the planet list never appear."""
import math

import pygame
import pytest

import starfield as sf
from settings import BASE_HEIGHT, BASE_WIDTH
from test_smoke import run  # noqa: F401  (fixture)

DT = 1 / 60


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


def _sky(free=True):
    s = sf.Starfield()
    s.planets, s.galaxies, s.nebula = [], [], None
    s.planet_timer = s.galaxy_timer = s.nebula_timer = 10 ** 6
    s.set_free(free)
    return s


def _positions(s):
    return [(st.x, st.y) for st in s.stars]


def _ship(s, dx, dy, frames=1):
    """Move the ship by (dx, dy) per frame (the game tells the sky where the ship is, not how far it went)."""
    x, y = s.last_player_x, s.last_player_y
    for _ in range(frames):
        x += dx
        y += dy
        s.update(DT, x, stage=1, menu=False, player_y=y)


def test_the_sky_stands_still_when_the_ship_does():
    s = _sky()
    s.update(DT, 640.0, stage=1, menu=False, player_y=360.0)
    before = _positions(s)
    for _ in range(120):
        s.update(DT, 640.0, stage=1, menu=False, player_y=360.0)
    assert _positions(s) == before                                   # nothing falls from the top any more


def test_the_normal_sky_still_falls_from_the_top():
    s = _sky(False)
    before = [st.y for st in s.stars]
    for _ in range(10):
        s.update(DT, 640.0, stage=1, menu=False)
    assert sum(1 for b, st in zip(before, s.stars) if st.y > b) > len(before) * 0.8


@pytest.mark.parametrize("dx,dy", [(4.0, 0.0), (-4.0, 0.0), (0.0, 4.0), (0.0, -4.0), (3.0, -3.0), (-3.0, 3.0)])
def test_the_stars_go_the_opposite_way_to_the_ship(dx, dy):
    s = _sky()
    s.update(DT, 640.0, stage=1, menu=False, player_y=360.0)
    near = s.stars_near[0]
    near.x, near.y = 600.0, 300.0
    x0, y0 = near.x, near.y
    _ship(s, dx, dy, 10)
    assert near.x - x0 == pytest.approx(-dx * 10 * near.fpar, abs=1e-6)
    assert near.y - y0 == pytest.approx(-dy * 10 * near.fpar, abs=1e-6)


def test_the_nearer_the_star_the_more_it_moves():
    s = _sky()
    s.update(DT, 640.0, stage=1, menu=False, player_y=360.0)
    for layer in (s.stars_far, s.stars_mid, s.stars_near):
        layer[0].x, layer[0].y = 600.0, 300.0
    _ship(s, 5.0, 3.0, 10)
    moves = [abs(600.0 - layer[0].x) for layer in (s.stars_far, s.stars_mid, s.stars_near)]
    assert moves[0] < moves[1] < moves[2]
    movesy = [abs(300.0 - layer[0].y) for layer in (s.stars_far, s.stars_mid, s.stars_near)]
    assert movesy[0] < movesy[1] < movesy[2]


def test_the_stars_come_back_by_the_opposite_side_in_both_directions():
    s = _sky()
    s.update(DT, 640.0, stage=1, menu=False, player_y=360.0)
    st = s.stars_near[0]
    st.x, st.y = 3.0, 5.0
    _ship(s, 20.0, 20.0, 5)                                          # the ship goes right and down: the stars go left and up
    assert st.x > BASE_WIDTH - 60 and st.y > BASE_HEIGHT - 60
    st.x, st.y = BASE_WIDTH - 3.0, BASE_HEIGHT - 5.0
    _ship(s, -20.0, -20.0, 5)
    assert st.x < 60 and st.y < 60


def test_the_first_frame_in_the_free_mode_does_not_jump():
    s = _sky(False)                                                  # the sky remembers the ship at the old centre ...
    s.set_free(True)
    before = _positions(s)
    s.update(DT, 1000.0, stage=1, menu=False, player_y=100.0)       # ... and the ship is elsewhere on the first frame
    flat = lambda pos: [c for xy in pos for c in xy]
    assert flat(_positions(s)) == pytest.approx(flat(before), abs=1e-6)
    s.update(DT, 1010.0, stage=1, menu=False, player_y=100.0)       # then it follows
    assert flat(_positions(s)) != pytest.approx(flat(before), abs=1e-6)


def test_the_two_rocks_never_come_in_the_free_mode():
    names = set()
    for _ in range(80):
        names.add(sf.Planet(free=True).filename)
    assert not names & set(sf.FREE_EXCLUDED) and len(names) >= 5


def test_the_normal_sky_may_still_have_them():
    names = {sf.Planet().filename for _ in range(120)}
    assert set(sf.FREE_EXCLUDED) & names


def test_turning_the_free_mode_on_takes_away_the_two_rocks_already_there():
    s = _sky(False)
    for name in sf.FREE_EXCLUDED:
        p = sf.Planet()
        p.filename = name
        s.planets.append(p)
    keep = sf.Planet()
    keep.filename = "earth.png"
    s.planets.append(keep)
    s.set_free(True)
    assert [p.filename for p in s.planets] == ["earth.png"]


def test_the_sky_decorations_come_in_from_outside_and_drift_in_any_direction():
    dirs = set()
    for _ in range(60):
        p = sf.Planet(free=True)
        outside = p.x + p.w / 2 < 0 or p.x - p.w / 2 > BASE_WIDTH or p.y + p.h / 2 < 0 or p.y - p.h / 2 > BASE_HEIGHT
        assert outside
        assert math.hypot(p.vx, p.vy) < 15.0                          # slowly
        dirs.add((p.vx > 0, p.vy > 0))
    assert len(dirs) == 4                                            # not always from the top
    for cls in (sf.Galaxy, sf.Nebula):
        o = cls(free=True)
        assert o.x + o.w / 2 < 0 or o.x - o.w / 2 > BASE_WIDTH or o.y + o.h / 2 < 0 or o.y - o.h / 2 > BASE_HEIGHT


def test_a_decoration_moves_with_the_ship_and_goes_when_it_has_left():
    s = _sky()
    p = sf.Planet(free=True)
    p.x, p.y, p.vx, p.vy = 640.0, 360.0, 0.0, 0.0
    s.planets.append(p)
    s.update(DT, 640.0, stage=1, menu=False, player_y=360.0)
    _ship(s, 6.0, 0.0, 10)
    assert p.x == pytest.approx(640.0 - 6.0 * 10 * sf.FREE_PARALLAX["planet"], abs=1e-6) and p.y == pytest.approx(360.0)
    _ship(s, 0.0, 6.0, 10)                                          # the ship goes down: the planet goes up
    assert p.y == pytest.approx(360.0 - 6.0 * 10 * sf.FREE_PARALLAX["planet"], abs=1e-6)
    p.x, p.y = 100.0, 100.0
    s.update(DT, s.last_player_x, stage=1, menu=False, player_y=s.last_player_y)
    p.x = -p.w                                                       # it has been seen and it is gone
    s.update(DT, s.last_player_x, stage=1, menu=False, player_y=s.last_player_y)
    assert p not in s.planets


def test_nothing_is_spawned_at_the_top_in_the_free_mode():
    s = _sky()
    s.planet_timer = s.galaxy_timer = s.nebula_timer = 0.0
    s.update(DT, 640.0, stage=1, menu=False, player_y=360.0)
    for o in s.planets + s.galaxies + ([s.nebula] if s.nebula else []):
        assert not (-o.h - 100 < o.y < 0 and 0 < o.x < BASE_WIDTH and abs(o.vx) < 1e-9)


# ------------------------------------------------------------------ in the game
def _launch(run):
    import story_state as ss
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index("bonus_asteroids")
    g._begin_adventure(g.story._launch_selected())
    g.input_grace = 0.0
    g.player.infinite_lives = False
    f = g.formation
    f.rocks[:] = []
    f.repop = False
    f.waves = 1
    f.saucer_in = 10 ** 6
    return g


class _Keys:
    def __init__(self, *down):
        self.down = set(down)

    def __getitem__(self, k):
        return k in self.down


def _fly(run, *down, frames=1):
    real = pygame.key.get_pressed
    pygame.key.get_pressed = lambda: _Keys(*down)
    try:
        run.frames(frames)
    finally:
        pygame.key.get_pressed = real


def test_in_the_mission_the_sky_is_free_and_still_while_the_ship_is(run):
    g = _launch(run)
    run.frames(3)
    assert g.starfield.free
    assert not any(p.filename in sf.FREE_EXCLUDED for p in g.starfield.planets)
    before = _positions(g.starfield)
    run.frames(30)
    assert _positions(g.starfield) == before


def test_in_the_mission_the_stars_follow_the_ship_in_every_direction(run):
    g = _launch(run)
    run.frames(3)
    p = g.player
    near = g.starfield.stars_near[0]
    near.x, near.y = 400.0, 300.0
    p.ast_angle = -math.pi / 2                                       # nose up
    _fly(run, pygame.K_UP, frames=20)
    assert p.ast_vy < 0 and near.y > 300.0 and abs(near.x - 400.0) < 1e-6      # the sky goes down when the ship goes up
    near.x, near.y = 400.0, 300.0
    p.ast_angle, p.ast_vx, p.ast_vy = 0.0, 0.0, 0.0                  # nose to the right
    _fly(run, pygame.K_UP, frames=20)
    assert near.x < 400.0 and abs(near.y - 300.0) < 1e-6              # ... and to the left when it goes right


def test_the_sky_goes_back_to_normal_when_the_mission_is_over(run):
    g = _launch(run)
    run.frames(3)
    assert g.starfield.free
    g._end_adventure(False)
    run.frames(3)
    assert not g.starfield.free
    y0 = [st.y for st in g.starfield.stars]
    run.frames(20)
    assert sum(1 for b, st in zip(y0, g.starfield.stars) if st.y > b) > len(y0) * 0.7     # falls from the top again


def test_the_sky_keeps_still_in_the_pause(run):
    g = _launch(run)
    run.frames(3)
    g.paused = True
    run.frames(3)
    assert g.starfield.free


def test_the_sky_does_not_jump_when_the_ship_wraps_from_bottom_to_top(run):
    g = _launch(run)
    run.frames(3)
    p = g.player
    p.x, p.y = 640.0, BASE_HEIGHT - 30.0
    p.ast_vx, p.ast_vy = 0.0, 300.0
    p.invulnerable = 100.0
    run.frames(1)
    near = g.starfield.stars_near[0]
    seen, wrapped = [], False
    for _ in range(30):
        y0 = near.y
        run.frames(1)
        wrapped = wrapped or p.y < 100
        d = (near.y - y0 + 360) % (BASE_HEIGHT + 20) - 360          # (the star itself wraps in its own band)
        seen.append(d)
    assert wrapped
    assert all(-3.0 < d < 0 for d in seen)                           # always a small step up, never a jump
