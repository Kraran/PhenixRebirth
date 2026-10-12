"""The small asteroid of the background (Dinkinesh) is a short film: its moon turns around it, very slowly."""
import random

import pygame
import pytest

import starfield
from starfield import ANIMATED, Planet, Starfield
from test_smoke import run  # noqa: F401  (fixture)

DINK = "asteroid_dinkinesh.png"


@pytest.fixture
def only(monkeypatch):
    """Planets that can only be this rock (and no cache left from another test)."""
    def pick(filename):
        monkeypatch.setattr(starfield, "PLANET_FILES", [filename])
        monkeypatch.setattr(Planet, "_cache", {})
        return Planet()
    return pick


def test_the_film_file_holds_exactly_the_announced_cells(run):
    info = ANIMATED[DINK]
    Planet._cache.clear()
    Planet._load_film(DINK)
    strip = Planet._load_image(info["strip"])
    assert strip.get_width() % info["frames"] == 0
    assert strip.get_width() // info["frames"] >= 40 and strip.get_height() >= 40


def test_a_dinkinesh_rock_has_its_film_and_keeps_the_size_of_the_still(run, only):
    for _ in range(20):
        p = only(DINK)
        assert p.film is not None and len(p.film) == ANIMATED[DINK]["frames"]
        # the still scaled to 28..72 px; the cell is a little bigger (it holds the path of the moon)
        assert 28 * 1.5 <= p.h <= 72 * 1.8
        assert (p.w, p.h) == p._cell().get_size()


def test_the_cells_have_a_transparent_background_and_a_rock(run, only):
    p = only(DINK)
    for i in (0, 36, 72, 108):
        cell = p.film[i]
        assert cell.get_at((0, 0)).a == 0
        opaque = sum(1 for x in range(0, cell.get_width(), 3) for y in range(0, cell.get_height(), 3)
                     if cell.get_at((x, y)).a == 255)
        assert opaque > 100


def test_one_turn_is_slow_and_comes_back_to_where_it_began(run, only):
    info = ANIMATED[DINK]
    p = only(DINK)
    start = p._cell()
    step = info["period"] / info["frames"]
    assert info["period"] >= 30 and step >= 0.25                       # much slower than the 6 s video
    p.t = 0.0
    seen = []
    t = 0.0
    while t < info["period"] - 1e-6:
        p.t = t
        seen.append(id(p._cell()))
        t += step / 2
    assert len(set(seen)) == info["frames"]                          # every cell is shown, none twice in a row
    p.t = info["period"]
    assert p._cell() is start                                         # back to the first picture


def test_the_picture_changes_only_a_few_times_a_second(run, only):
    p = only(DINK)
    changes, last = 0, id(p._cell())
    for _ in range(60 * 10):                                          # ten seconds at 60 fps
        p.update(1 / 60)
        p.y = -500                                                   # stay alive and out of the way
        now = id(p._cell())
        changes += now != last
        last = now
    assert 20 <= changes <= 40                                       # 3 cells a second at the most


def test_a_cell_is_scaled_once_and_then_kept(run, only):
    p = only(DINK)
    p.t = 5.0
    assert p._cell() is p._cell()


def test_two_rocks_do_not_turn_in_step(run, only):
    firsts = set()
    for _ in range(12):
        p = only(DINK)
        firsts.add(p.first_cell)
    assert len(firsts) > 3


def test_turning_and_drawing_do_not_touch_the_random_numbers(run, only):
    p = only(DINK)
    state = random.getstate()
    surf = pygame.Surface((1280, 720))
    for _ in range(300):
        p.update(1 / 30)
        p.y = 300
        p.draw(surf)
    assert random.getstate() == state


def test_the_flipped_rock_flips_every_cell(run, only):
    for _ in range(40):
        p = only(DINK)
        if p.flipped:
            break
    else:
        pytest.skip("no flipped rock in 40 draws")
    p.t = 10.0
    cell = p._cell()
    plain = pygame.transform.smoothscale(p.film[(p.first_cell + int(10.0 / ANIMATED[DINK]["period"] * len(p.film))) % len(p.film)], (p.w, p.h))
    assert pygame.image.tobytes(cell, "RGBA") == pygame.image.tobytes(pygame.transform.flip(plain, True, False), "RGBA")


def test_the_other_rocks_stay_still_pictures(run, only):
    for name in ("asteroid_pallas.png", "mars.png"):
        p = only(name)
        assert p.film is None
        p.t = 20.0
        assert p._cell() is p.image


def test_a_missing_film_file_falls_back_to_the_still(run, only, monkeypatch):
    monkeypatch.setitem(ANIMATED, DINK, dict(ANIMATED[DINK], strip="nothing_here.png"))
    p = only(DINK)
    assert p.film is None and p._cell() is p.image


def test_the_whole_starfield_still_updates_and_draws(run):
    sf = Starfield()
    surf = pygame.Surface((1280, 720))
    for _ in range(120):
        sf.update(1 / 60, 640)
        sf.draw(surf)
