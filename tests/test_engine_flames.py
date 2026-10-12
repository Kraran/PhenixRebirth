"""The jets of the engines (src/engine_flame.py): a straight, dense jet of burning gas out of each nozzle, behind the hull,
in the colours of each ship, wider and longer for the Phenix, stretched by the thrust."""
import math
import os
import random

import numpy as np
import pygame
import pytest

import engine_flame as ef
from player import Player
from test_smoke import run  # noqa: F401  (fixture)

ALL = [("phoenix", "argent"), ("phoenix", "blue"), ("phoenix", "gold"),
       ("shield", "red"), ("shield", "green"), ("shield", "violet"),
       ("phenix", "phenix_red"), ("phenix", "phenix_blue")]


def _alpha_rows(arr):
    return arr[..., 3].astype(float)


# --- the pictures ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind,key", ALL)
def test_every_jet_has_its_picture_file_of_the_right_size(kind, key):
    path = ef.strip_path(kind, key)
    assert os.path.isfile(path), path
    img = pygame.image.load(path)
    cw, ch = ef.cell_size(kind)
    assert img.get_size() == (cw * ef.FRAMES, ch)


def test_the_files_are_what_the_code_makes(run):
    """If this fails, the look was changed in src/engine_flame.py: run tools/make_engine_flames.py and commit the pictures."""
    for kind, key in (("phoenix", "argent"), ("shield", "violet"), ("phenix", "phenix_blue")):
        made = pygame.surfarray.array3d(ef.render_strip(kind, key)).astype(int)
        saved = pygame.surfarray.array3d(pygame.image.load(ef.strip_path(kind, key))).astype(int)
        made_a = pygame.surfarray.array_alpha(ef.render_strip(kind, key)).astype(int)
        saved_a = pygame.surfarray.array_alpha(pygame.image.load(ef.strip_path(kind, key))).astype(int)
        assert np.abs(made_a - saved_a).max() <= 6, (kind, key)
        solid = saved_a > 40
        assert np.abs(made - saved)[solid].max() <= 8, (kind, key)


def test_a_missing_or_wrong_file_makes_the_film_instead(run, monkeypatch, tmp_path):
    ef._films.clear()
    monkeypatch.setattr(ef, "strip_path", lambda kind, key: str(tmp_path / "nothing.png"))
    pics = ef.film("phoenix", "argent")
    assert pics is not None and len(pics) == ef.FRAMES and pics[0].get_size() == ef.cell_size("phoenix")
    bad = tmp_path / "bad.png"
    pygame.image.save(pygame.Surface((10, 10)), str(bad))
    ef._films.clear()
    monkeypatch.setattr(ef, "strip_path", lambda kind, key: str(bad))
    pics = ef.film("shield", "red")
    assert pics is not None and len(pics) == ef.FRAMES                # the file does not fit: the film is made
    ef._films.clear()


def test_the_colours_follow_the_code_of_each_ship():
    assert [ef.ramp_key("phoenix", t) for t in ("argent", "blue", "gold")] == ["argent", "blue", "gold"]
    assert [ef.ramp_key("shield", t) for t in ("red", "green", "violet")] == ["red", "green", "violet"]
    assert ef.ramp_key("phenix", "blue") == "phenix_blue"
    assert ef.ramp_key("phenix", "argent") == ef.ramp_key("phenix", "gold") == "phenix_red"     # as before: fire unless blue
    assert ef.ramp_key("phoenix", "nonsense") == "argent" and ef.ramp_key("shield", "nonsense") == "red"


@pytest.mark.parametrize("kind,key,ok", [
    ("phoenix", "argent", lambda r, g, b: b > r + 40 and b > g),
    ("phoenix", "blue", lambda r, g, b: b > r + 40 and b > g),
    ("phoenix", "gold", lambda r, g, b: r > b + 60 and r >= g),
    ("shield", "red", lambda r, g, b: r > g + 40 and r > b + 60),
    ("shield", "green", lambda r, g, b: g > r + 30 and g > b + 30),
    ("shield", "violet", lambda r, g, b: b > g + 30 and r > g + 20),
    ("phenix", "phenix_red", lambda r, g, b: r > b + 60 and r >= g),
    ("phenix", "phenix_blue", lambda r, g, b: b > r + 30),
])
def test_the_body_of_each_jet_has_the_colour_of_its_ship(kind, key, ok):
    spec = ef.NOZZLES[kind]
    arr = ef._frame(key, spec["half"], spec["length"], 0.3)
    h = arr.shape[0]
    body = arr[int(h * 0.2):int(h * 0.55)]
    solid = body[..., 3] > 200
    r, g, b = [float(body[..., c][solid].mean()) for c in range(3)]
    assert ok(r, g, b), (r, g, b)


@pytest.mark.parametrize("kind,key", ALL)
def test_the_head_of_the_jet_is_white_hot(kind, key):
    spec = ef.NOZZLES[kind]
    arr = ef._frame(key, spec["half"], spec["length"], 0.0)
    w = arr.shape[1]
    head = arr[2:5, w // 2 - 1:w // 2 + 2, :3].astype(int)
    tail = arr[int(arr.shape[0] * 0.7), w // 2, :3].astype(int)
    assert head.mean() > 190                                          # near white
    assert head.mean() > tail.mean() + 40


# --- the shape: straight, dense, no flicker of the position ------------------------------------------------------------

@pytest.mark.parametrize("kind,key", [("phoenix", "argent"), ("shield", "red"), ("phenix", "phenix_red")])
def test_the_jet_is_straight_it_does_not_sway(kind, key):
    spec = ef.NOZZLES[kind]
    for t in (0.0, 0.25, 0.5, 0.75):
        a = _alpha_rows(ef._frame(key, spec["half"], spec["length"], t))
        h, w = a.shape
        xs = np.arange(w)
        for frac in (0.1, 0.3, 0.5, 0.7):
            row = a[int(h * frac)]
            centre = float((row * xs).sum() / row.sum())
            assert abs(centre - (w - 1) / 2.0) < 0.6, (t, frac, centre)


@pytest.mark.parametrize("kind,key", [("phoenix", "argent"), ("shield", "red"), ("phenix", "phenix_red")])
def test_the_jet_keeps_most_of_its_width_then_fades_instead_of_ending_in_a_point(kind, key):
    spec = ef.NOZZLES[kind]
    a = _alpha_rows(ef._frame(key, spec["half"], spec["length"], 0.4))
    h = a.shape[0]

    def width(frac):
        return float((a[int(h * frac)] > 100).sum())

    assert width(0.1) >= 2 * spec["half"] * 0.9                          # as wide as the nozzle, at least
    assert width(0.6) >= 0.4 * width(0.1)                                # it narrows but does not close to a point
    assert width(0.1) <= 2 * spec["half"] * 1.4                          # a jet, not a cloud
    assert a[int(h * 0.1), a.shape[1] // 2] > a[int(h * 0.75), a.shape[1] // 2] > 0 and a[int(h * 0.75), a.shape[1] // 2] < 200   # it fades


def test_the_loop_has_no_jump():
    spec = ef.NOZZLES["phoenix"]
    a = ef._frame("argent", spec["half"], spec["length"], 0.0).astype(int)
    b = ef._frame("argent", spec["half"], spec["length"], ef.LOOP_SEC).astype(int)
    assert np.abs(a - b).max() <= 3                                       # after a loop the turbulence is where it began
    c = ef._frame("argent", spec["half"], spec["length"], ef.LOOP_SEC / ef.FRAMES).astype(int)
    assert np.abs(a - c).max() > 10                                       # and in between it moves


def test_the_phenix_is_wider_and_longer_than_the_ships_and_the_ships_stay_in_their_place():
    phoenix, shield, phenix = (ef.NOZZLES[k] for k in ("phoenix", "shield", "phenix"))
    assert phenix["half"] > 1.5 * phoenix["half"] * 0.99 and phenix["length"] > phoenix["length"]
    assert phenix["half"] >= 9.0 and phoenix["half"] >= 5.4 and shield["half"] >= 4.6        # as validated on the examples
    assert shield["half"] < phoenix["half"] < phenix["half"]
    # two jets of the same ship do not overlap (the Phenix ones almost touch: one mass of fire)
    for spec in (phoenix, shield, phenix):
        gaps = [b - a - 2 * spec["half"] * 1.16 for a, b in zip(spec["xs"], spec["xs"][1:])]
        assert min(gaps) > -3.5, gaps


# --- the place: out of the nozzles, read on the hull pictures --------------------------------------------------------------

@pytest.mark.parametrize("ship,tint", [("phoenix", "argent"), ("phoenix", "blue"), ("phoenix", "gold"),
                                       ("shield", "red"), ("shield", "green"), ("shield", "violet")])
def test_the_jets_start_inside_the_nozzles_of_the_hull_and_have_room_under_them(run, ship, tint):
    p = Player(100, 100, ship, tint)
    kind = "shield" if ship == "shield" else "phoenix"
    spec = ef.NOZZLES[kind]
    alpha = pygame.surfarray.array_alpha(p.image)
    w, h = p.image.get_size()
    for x, y in zip(spec["xs"], spec["ys"]):
        col, row = int(round(w // 2 + x)), int(round(h // 2 + y))
        assert alpha[col, row - 2] > 100, (x, y)                         # the root of the jet is hidden in the nozzle
        assert alpha[col, min(h - 1, row + 4)] < 30, (x, y)              # and under it there is open space
        assert alpha[col, min(h - 1, row + 2)] < 130, (x, y)             # the nozzle is at the edge of the hull, not up inside it
    # the nozzles are where the engine lights are on the picture: the jet is centred on its barrel
    for x in spec["xs"]:
        col = int(round(w // 2 + x))
        assert alpha[col - 1:col + 2, int(h // 2 + spec["ys"][0]) - 6].min() > 100


def test_the_phenix_jets_come_out_of_the_two_barrels_of_the_flight_pictures(run):
    p = Player(100, 100, "phoenix", "argent")
    spec = ef.NOZZLES["phenix"]
    for frame in p.phenix_frames:
        alpha = pygame.surfarray.array_alpha(frame)
        w, h = frame.get_size()
        for x, y in zip(spec["xs"], spec["ys"]):
            col, row = int(round(w // 2 + x)), int(round(h // 2 + y))
            assert alpha[col, row - 6] > 100, (x, y)


# --- drawing -----------------------------------------------------------------------------------------------------------------

def _lit(surf):
    arr = pygame.surfarray.array3d(surf).astype(int)
    return arr.sum(axis=2) > 90


def test_draw_puts_the_jet_under_the_nozzle_and_centred(run):
    surf = pygame.Surface((200, 200))
    surf.fill((0, 0, 0))
    assert ef.draw(surf, "phoenix", "argent", 100, 60, 1.0, 0.3)
    lit = _lit(surf)
    xs, ys = np.nonzero(lit)
    assert ys.min() >= 58 and ys.max() > 60 + 25                         # starts at the nozzle, goes down
    assert abs((xs.min() + xs.max()) / 2.0 - 100) <= 1.5               # centred on x
    assert xs.max() - xs.min() + 1 >= 8


def test_an_idling_jet_is_a_little_narrower_than_a_pushing_one(run, monkeypatch):
    sizes = []
    real = pygame.transform.smoothscale
    monkeypatch.setattr(pygame.transform, "smoothscale", lambda pic, size, *a: sizes.append(size) or real(pic, size, *a))
    cw = ef.cell_size("phoenix")[0]
    surf = pygame.Surface((200, 200))
    ef.draw(surf, "phoenix", "argent", 100, 60, ef.SHOW_FROM, 0.3, flicker=False)
    assert 0.75 * cw <= sizes[-1][0] <= 0.9 * cw, (sizes, cw)            # MIN_WIDTH: narrower at idle, but still a jet
    del sizes[:]
    ef.draw(surf, "phoenix", "argent", 100, 60, 1.0, 0.3, flicker=False)
    assert all(w == cw for w, h in sizes)                                # at full thrust the width is the picture's own


def test_the_thrust_stretches_the_jet(run):
    sizes = {}
    for thrust in (0.1, 0.25, 0.6, 1.0):
        surf = pygame.Surface((200, 200))
        surf.fill((0, 0, 0))
        ef.draw(surf, "phoenix", "argent", 100, 60, thrust, 0.3, flicker=False)
        xs, ys = np.nonzero(_lit(surf))
        sizes[thrust] = (int(ys.max() - ys.min()), int(xs.max() - xs.min()))
    lengths = [sizes[t][0] for t in (0.1, 0.25, 0.6, 1.0)]
    assert lengths == sorted(lengths) and len(set(lengths)) == 4, sizes
    assert sizes[1.0][1] >= sizes[0.25][1]
    assert sizes[1.0][0] > 2.0 * sizes[0.1][0]                           # idle is short, full thrust is long


def test_no_jet_when_the_engines_are_off(run):
    surf = pygame.Surface((200, 200))
    surf.fill((0, 0, 0))
    assert ef.draw(surf, "phoenix", "argent", 100, 60, 0.0, 0.3) is False
    assert ef.draw(surf, "phoenix", "argent", 100, 60, ef.SHOW_FROM - 0.01, 0.3) is False
    assert not _lit(surf).any()


def test_two_nozzles_do_not_show_the_same_picture_and_time_moves_the_jet(run):
    def shot(clock, engine):
        surf = pygame.Surface((200, 200))
        surf.fill((0, 0, 0))
        ef.draw(surf, "phoenix", "argent", 100, 60, 1.0, clock, engine=engine, flicker=False)
        return pygame.surfarray.array3d(surf).astype(int)

    assert np.abs(shot(0.3, 0) - shot(0.3, 1)).sum() > 500
    assert np.abs(shot(0.30, 0) - shot(0.34, 0)).sum() > 500
    assert (shot(0.3, 0) == shot(0.3 + ef.LOOP_SEC, 0)).all()           # a loop is a loop


def test_drawing_a_jet_is_cheap_and_does_not_touch_the_random_numbers(run):
    import time
    surf = pygame.Surface((300, 300))
    state = random.getstate()
    t0 = time.perf_counter()
    for i in range(300):
        for e in range(3):
            ef.draw(surf, "shield", "red", 100 + 20 * e, 60, 0.4 + (i % 7) / 12.0, i / 60.0, engine=e)
    per = (time.perf_counter() - t0) / 300
    assert random.getstate() == state
    assert per < 0.004, per                                              # three jets in a few milliseconds, on a slow machine


# --- in the game: Player -----------------------------------------------------------------------------------------------------

def _ship_picture(p, thrust, size=(200, 240), at=(100, 90)):
    p.x, p.y = at
    p.engine_time = 0.3
    p.engine_intensity = thrust
    surf = pygame.Surface(size)
    surf.fill((0, 0, 0))
    p.draw(surf)
    return surf


@pytest.mark.parametrize("ship,tint", [("phoenix", "argent"), ("phoenix", "blue"), ("phoenix", "gold"),
                                       ("shield", "red"), ("shield", "green"), ("shield", "violet")])
def test_the_jets_are_behind_the_hull(run, ship, tint):
    p = Player(100, 90, ship, tint)
    off, on = _ship_picture(p, 0.0), _ship_picture(p, 1.0)
    hull_alpha = pygame.surfarray.array_alpha(p.image)
    w, h = p.image.get_size()
    x0, y0 = 100 - w // 2, 90 - h // 2
    a, b = pygame.surfarray.array3d(off).astype(int), pygame.surfarray.array3d(on).astype(int)
    solid = np.zeros(a.shape[:2], bool)
    solid[x0:x0 + w, y0:y0 + h] = hull_alpha == 255
    assert (a[solid] == b[solid]).all()                                  # where the hull is solid, the jets change nothing
    assert np.abs(a - b).sum() > 2000                                    # but they are there


@pytest.mark.parametrize("ship,tint,ok", [
    ("phoenix", "argent", lambda r, g, b: b > r + 30),
    ("phoenix", "blue", lambda r, g, b: b > r + 30),
    ("phoenix", "gold", lambda r, g, b: r > b + 40),
    ("shield", "red", lambda r, g, b: r > b + 40),
    ("shield", "green", lambda r, g, b: g > b + 20 and g > r),
    ("shield", "violet", lambda r, g, b: b > g + 20),
])
def test_the_jets_of_each_ship_keep_its_colour(run, ship, tint, ok):
    p = Player(100, 90, ship, tint)
    off, on = pygame.surfarray.array3d(_ship_picture(p, 0.0)).astype(int), pygame.surfarray.array3d(_ship_picture(p, 1.0)).astype(int)
    added = np.abs(on - off).sum(axis=2) > 60
    assert added.sum() > 300
    r, g, b = [float(on[..., c][added].mean()) for c in range(3)]
    assert ok(r, g, b), (r, g, b)


def test_the_phenix_burns_wider_and_longer_than_the_ship(run):
    ship = Player(100, 90, "phoenix", "argent")
    phenix = Player(100, 90, "phoenix", "argent")
    phenix.phenix_timer = 5.0
    phenix.morph_dir = 0
    off_s, on_s = pygame.surfarray.array3d(_ship_picture(ship, 1.0)).astype(int), pygame.surfarray.array3d(_ship_picture(ship, 0.0)).astype(int)
    off_p, on_p = pygame.surfarray.array3d(_ship_picture(phenix, 0.0)).astype(int), pygame.surfarray.array3d(_ship_picture(phenix, 1.0)).astype(int)
    xs_s, ys_s = np.nonzero(np.abs(off_s - on_s).sum(axis=2) > 60)
    xs_p, ys_p = np.nonzero(np.abs(off_p - on_p).sum(axis=2) > 60)
    assert ys_p.max() - 90 > ys_s.max() - 90                             # lower: longer
    below = lambda xs, ys, y0: xs[ys > y0]
    assert (below(xs_p, ys_p, 150).max() - below(xs_p, ys_p, 150).min()) > (below(xs_s, ys_s, 150).max() - below(xs_s, ys_s, 150).min())


def test_the_phenix_jets_are_off_with_the_engines_and_on_when_the_ship_pushes(run):
    p = Player(100, 90, "phoenix", "blue")
    p.phenix_timer = 5.0
    p.morph_dir = 0
    off, idle = _ship_picture(p, 0.0), _ship_picture(p, 0.25)
    assert (pygame.surfarray.array3d(off) != pygame.surfarray.array3d(idle)).any()     # at idle it burns hard (0.85 at least)
    idle_a, push = pygame.surfarray.array3d(idle).astype(int), pygame.surfarray.array3d(_ship_picture(p, 1.0)).astype(int)
    assert np.abs(idle_a - push).sum() < 0.5 * np.abs(pygame.surfarray.array3d(off).astype(int) - push).sum()   # the Phenix always burns


def test_the_shield_dome_has_no_jets(run):
    p = Player(100, 90, "shield", "red")
    p.phenix_gauge = 10.0
    assert p.try_activate_phenix()
    p.engine_intensity = 1.0
    assert p._engine_plan() is None
    p.morph_dir = 0
    p.phenix_timer = 2.0
    assert p._engine_plan() is None


def test_the_jets_move_from_the_hull_to_the_phenix_during_the_change(run):
    p = Player(100, 90, "phoenix", "argent")
    hull, phenix = ef.NOZZLES["phoenix"], ef.NOZZLES["phenix"]
    p.phenix_gauge = 10.0
    assert p.try_activate_phenix()
    assert p.morph_dir > 0
    p.morph_timer = 0.0
    kind, nozzles, size = p._engine_plan()
    assert kind == "phenix" and size == pytest.approx(hull["half"] / phenix["half"])
    assert nozzles[0] == pytest.approx((hull["xs"][0], hull["ys"][0])) and nozzles[1] == pytest.approx((hull["xs"][1], hull["ys"][1]))
    p.morph_timer = p.morph_duration * 0.5
    _, mid, size_mid = p._engine_plan()
    assert hull["xs"][0] < mid[0][0] + 1e-9 or mid[0][0] < hull["xs"][0]
    assert mid[0][1] > hull["ys"][0] and mid[0][1] < phenix["ys"][0]
    assert hull["half"] / phenix["half"] < size_mid < 1.0
    p.morph_timer = p.morph_duration
    _, last, size_last = p._engine_plan()
    assert last[0] == pytest.approx((phenix["xs"][0], phenix["ys"][0])) and size_last == pytest.approx(1.0)
    p.morph_dir = 0
    p.phenix_timer = 5.0
    assert p._engine_plan()[0] == "phenix"
    p.phenix_timer = 0.0
    assert p._engine_plan()[0] == "phoenix"


def test_the_jets_go_back_from_the_phenix_to_the_hull_when_it_ends(run):
    p = Player(100, 90, "phoenix", "argent")
    hull, phenix = ef.NOZZLES["phoenix"], ef.NOZZLES["phenix"]
    p.phenix_timer = 5.0
    p.morph_dir = -1
    p.morph_duration = 1.0
    p.morph_timer = 0.0
    kind, nozzles, size = p._engine_plan()
    assert nozzles[0] == pytest.approx((phenix["xs"][0], phenix["ys"][0])) and size == pytest.approx(1.0)   # begins as the Phenix
    p.morph_timer = 1.0
    _, last, size_last = p._engine_plan()
    assert last[0] == pytest.approx((hull["xs"][0], hull["ys"][0])) and size_last == pytest.approx(hull["half"] / phenix["half"])
    p.morph_timer = 0.5
    _, mid, size_mid = p._engine_plan()
    assert hull["ys"][0] < mid[0][1] < phenix["ys"][0] and hull["half"] / phenix["half"] < size_mid < 1.0


def test_the_sputter_jets_follow_the_ship_as_it_swells_while_dying(run):
    p = Player(100, 90, "phoenix", "argent")
    p.dying = True
    p.death_flash = False
    p.death_timer = 0.3 * p.DEATH_DURATION
    calls = []
    real = ef.draw
    ef.draw = lambda surface, kind, palette, x, y, thrust, clock, engine=0, size=1.0, flicker=True: calls.append((x, y, size)) or True
    try:
        p.draw(pygame.Surface((200, 240)))
    finally:
        ef.draw = real
    spec = ef.NOZZLES["phoenix"]
    assert len(calls) == 2
    scale = calls[0][2]
    assert 1.05 < scale < 1.5                                            # the ship swells while it dies...
    for (x, y, size), nx, ny in zip(calls, spec["xs"], spec["ys"]):
        assert x == pytest.approx(p.x + nx * scale) and y == pytest.approx(p.y + ny * scale)   # ...and its nozzles with it
        assert size == pytest.approx(scale)


def test_a_dying_ship_sputters_for_the_first_half_of_its_death_then_nothing(run):
    p = Player(100, 90, "phoenix", "argent")
    p.dying = True
    p.engine_intensity = 0.0
    seen = []
    real = ef.draw

    def spy(*a, **k):
        seen.append(a[5])                                                # the thrust asked for
        return real(*a, **k)

    def jets(t):
        p.death_timer = t * p.DEATH_DURATION
        p.death_flash = False
        surf = pygame.Surface((200, 240))
        surf.fill((0, 0, 0))
        del seen[:]
        ef.draw = spy
        try:
            p.draw(surf)
        finally:
            ef.draw = real
        hull_only = pygame.Surface((200, 240))
        hull_only.fill((0, 0, 0))
        ef.draw = lambda *a, **k: False
        try:
            p.draw(hull_only)
        finally:
            ef.draw = real
        diff = int(np.abs(pygame.surfarray.array3d(surf).astype(int) - pygame.surfarray.array3d(hull_only).astype(int)).sum())
        return diff, max(seen) if seen else 0.0

    d1, t1 = jets(0.1)
    d3, t3 = jets(0.3)
    d45, t45 = jets(0.45)
    d6, t6 = jets(0.6)
    d9, t9 = jets(0.9)
    assert d1 > 500 and d3 > 100
    assert t1 > t3 > t45 > 0                                             # dying down
    assert d6 == 0 and d9 == 0 and t6 == 0.0 and t9 == 0.0


def test_the_films_are_made_before_the_mission_not_during_it(run):
    ef._films.clear()
    Player(100, 90, "phoenix", "gold")
    assert ("phoenix", "gold") in ef._films and ("phenix", "phenix_red") in ef._films
    Player(100, 90, "shield", "violet")
    assert ("shield", "violet") in ef._films
    ef._films.clear()
