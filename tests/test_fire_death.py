"""The death in the flames of the Guardians' fire bolt: blaze, charring and ash scattered by the wind (src/fire_death.py)."""
import math
import random

import pygame
import pytest

import fire_death as fd
import guardian as gd
import ship_burn as sb
from player import Player


@pytest.fixture
def display():
    pygame.display.init()
    pygame.display.set_mode((1280, 720))


@pytest.fixture(scope="module")
def ship_frames():
    pygame.display.init()
    pygame.display.set_mode((1280, 720))
    ship = Player(640, 625, ship_id="shield")
    return ship, sb.frames(ship, False)


@pytest.fixture(scope="module")
def bird_frames():
    pygame.display.init()
    pygame.display.set_mode((1280, 720))
    bird = gd.EscortBird(100, 100, 0, 1)
    return bird, gd.burning_frames(1, bird.frames[0])


def _box(pic):
    parts = pygame.mask.from_surface(pic, 8).get_bounding_rects()
    return parts[0].unionall(parts[1:]) if parts else None


def _centroid_x(pic):
    mask = pygame.mask.from_surface(pic, 8)
    return mask.centroid()[0] if mask.count() else None


def _colours(pic):
    return [pic.get_at((x, y)) for y in range(pic.get_height()) for x in range(pic.get_width())
            if pic.get_at((x, y)).a > 40]


@pytest.mark.parametrize("which", ["ship", "bird"])
def test_it_starts_whole_and_ends_with_nothing_left(which, ship_frames, bird_frames):
    frames = ship_frames[1] if which == "ship" else bird_frames[1]
    assert pygame.mask.from_surface(frames[0], 8).count() > 0
    assert pygame.mask.from_surface(frames[-1], 0).count() == 0
    # the flakes thin out to the end: the second to last picture has far less than the middle of the fire
    counts = [pygame.mask.from_surface(f, 8).count() for f in frames]
    assert counts[-2] < counts[len(counts) // 4] / 2


@pytest.mark.parametrize("which", ["ship", "bird"])
def test_fire_then_embers_then_grey_ash(which, ship_frames, bird_frames):
    frames = ship_frames[1] if which == "ship" else bird_frames[1]
    n = len(frames)
    fire = _colours(frames[n // 6])
    assert any(c.r > 220 and 90 < c.g < 235 and c.b < 110 for c in fire)             # flames: yellow / orange
    ash = _colours(frames[int(n * 0.8)])
    assert ash and any(abs(c.r - c.g) < 12 and abs(c.g - c.b) < 12 for c in ash)     # grey ash flakes
    assert not any(c.r > 240 and c.g > 240 and c.b > 240 for c in ash)               # no white blaze left


def test_the_ash_is_blown_to_the_side_by_the_wind(ship_frames, bird_frames):
    ship_late = ship_frames[1][int(len(ship_frames[1]) * 0.85)]
    assert _centroid_x(ship_late) > sb.HULL[0] + 20                      # the cloud has left the hull to the right
    bird_late = bird_frames[1][int(len(bird_frames[1]) * 0.85)]
    assert _centroid_x(bird_late) > bird_late.get_width() / 2 + 6


def test_the_fire_of_the_ship_towers_over_the_hull_and_the_ash_cloud_is_wide(ship_frames):
    ship, frames = ship_frames
    hull_top = sb.HULL[1] - ship.image.get_height() // 2
    tallest = min(_box(f).top for f in frames if _box(f))
    assert tallest <= hull_top - 70                          # the blaze rises far above the nose
    widest = max(_box(f).width for f in frames[len(frames) // 2:] if _box(f))
    assert widest >= 70                                      # a cloud of ash, not a few dots


def test_the_ship_dies_in_a_much_bigger_fire_than_a_bird(ship_frames, bird_frames):
    ship_peak = max(pygame.mask.from_surface(f, 8).count() for f in ship_frames[1])
    bird_peak = max(pygame.mask.from_surface(f, 8).count() for f in bird_frames[1])
    assert ship_peak > 3 * bird_peak
    assert sb.DURATION > gd.BURN_SECONDS


def test_the_flash_and_the_ring_of_heat_are_only_for_the_ship(ship_frames, bird_frames):
    ship_flash = _box(ship_frames[1][0])
    assert ship_flash.width >= 90 and ship_flash.height >= 90          # a flash round the hull at the touch
    assert _box(bird_frames[1][0]).width < 60
    ring = _box(ship_frames[1][int(len(ship_frames[1]) * 0.15)])
    assert ring.width >= 80                                             # the ring of heat runs out


def test_frames_are_identical_each_time_and_use_no_random_numbers(display, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: pytest.fail("random used"))
    monkeypatch.setattr(random, "uniform", lambda *a: pytest.fail("random used"))
    source = pygame.Surface((20, 20), pygame.SRCALPHA)
    source.fill((90, 120, 200, 255))
    one = fd.frames(source, 6, fd.BIRD, (90, 90), (35, 35))
    two = fd.frames(source, 6, fd.BIRD, (90, 90), (35, 35))
    assert [pygame.image.tobytes(f, "RGBA") for f in one] == [pygame.image.tobytes(f, "RGBA") for f in two]


def test_transparent_pixels_of_the_picture_do_not_burn(display):
    source = pygame.Surface((20, 20), pygame.SRCALPHA)
    pygame.draw.rect(source, (200, 60, 60, 255), (8, 8, 4, 4))
    box = _box(fd.render(source, 0.0, fd.BIRD, (60, 60), (20, 20)))
    assert box.width <= 6 and box.height <= 6


def test_flames_leave_the_burning_pixels_upwards(display):
    source = pygame.Surface((20, 20), pygame.SRCALPHA)
    source.fill((90, 120, 200, 255))
    pics = [fd.render(source, t, fd.BIRD, (120, 120), (50, 60)) for t in (0.15, 0.25, 0.35)]
    assert min(_box(p).top for p in pics) < 60 - 12                      # above the top of the picture (y = 60)
    assert max(_box(p).bottom for p in pics) <= 80 + 6                   # but not below its bottom (y = 80)


def test_shipburn_keeps_the_hull_where_the_ship_was_in_every_turn_and_size(display):
    ship = Player(500, 400, ship_id="shield")
    sb.prepare(ship)
    burn = sb.ShipBurn(ship)
    plain = pygame.Surface((1280, 720), pygame.SRCALPHA)
    burn.draw(plain)
    cx, cy = _box(plain).center
    assert abs(cx - 500) <= 4 and abs(cy - 400) <= 4
    for angle, scale in ((90.0, 0.5), (-135.0, 0.5), (30.0, 1.0)):
        turned = pygame.Surface((1280, 720), pygame.SRCALPHA)
        burn.draw(turned, angle, scale)
        cx, cy = _box(turned).center
        assert abs(cx - 500) <= 5 and abs(cy - 400) <= 5, (angle, scale, cx, cy)


def test_shipburn_lasts_longer_than_the_old_dust_and_is_drawn_from_cached_frames(display):
    ship = Player(500, 400, ship_id="shield")
    sb.prepare(ship)
    assert sb.DURATION == 2.4 and sb.FRAME_COUNT == 32
    burn = sb.ShipBurn(ship)
    assert burn.frames is sb.frames(ship, False)
    burn.update(sb.DURATION - 0.01)
    assert not burn.finished
    burn.update(0.02)
    assert burn.finished
    canvas = pygame.Surface((1280, 720), pygame.SRCALPHA)
    burn.draw(canvas)
    assert pygame.mask.from_surface(canvas, 0).count() == 0                 # nothing is drawn when it is over


def test_the_frame_shown_follows_the_age(display):
    ship = Player(500, 400, ship_id="shield")
    sb.prepare(ship)
    burn = sb.ShipBurn(ship)
    seen = set()
    for _ in range(int(sb.DURATION * 60)):
        canvas = pygame.Surface((1280, 720), pygame.SRCALPHA)
        burn.draw(canvas)
        seen.add(pygame.image.tobytes(canvas, "RGBA"))
        burn.update(1 / 60)
    assert len(seen) >= sb.FRAME_COUNT - 2


def test_blobs_are_cached_and_additive(display):
    glow = pygame.Surface((60, 60))
    glow.fill((0, 0, 0))
    fd.add_blob(glow, 30, 30, 8, 8, (255, 140, 30), 1.0)
    first = glow.get_at((30, 30))
    assert first.r > 0
    fd.add_blob(glow, 30, 30, 8, 8, (255, 140, 30), 1.0)
    assert glow.get_at((30, 30)).r > first.r
    assert fd._blob(8, 8, (255, 140, 30), 1.0) is fd._blob(8, 8, (255, 140, 30), 1.0)


def test_flame_colours_go_from_yellow_to_dark_red():
    young, old = fd.flame_colour(0.0), fd.flame_colour(1.0)
    assert young[0] > 240 and young[1] > 190
    assert old[0] < 130 and old[1] < 40
    assert math.isclose(sum(fd.flame_colour(-5)), sum(fd.flame_colour(0.0)))


def test_the_ring_of_heat_runs_out_round_the_hull(ship_frames):
    ship, frames = ship_frames
    i = 9
    t = i / (len(frames) - 1)
    radius = 20 + (t - 0.04) / 0.41 * 110
    assert frames[i].get_at((round(sb.HULL[0] + radius) - 2, sb.HULL[1])).a > 30      # on the ring ...
    assert frames[i].get_at((round(sb.HULL[0] + radius + 12), sb.HULL[1])).a < 12     # ... and not beyond it


def test_the_big_fire_of_the_ship_has_a_hot_yellow_core(ship_frames):
    hot = max(sum(1 for c in _colours(f) if c.r > 240 and c.g > 200) for f in ship_frames[1])
    assert hot >= 700


def test_embers_glow_orange_before_they_turn_to_grey_ash(display):
    source = pygame.Surface((24, 24), pygame.SRCALPHA)
    source.fill((90, 120, 200, 255))
    style = dict(fd.BIRD, ignite=0.1, burn=0.1, ash_life=0.5, ember_k=0.5)
    colours = _colours(fd.render(source, 0.3, style, (90, 90), (33, 33)))
    assert any(c.r > 240 and 120 < c.g < 185 and c.b < 80 and c.a > 200 for c in colours)


def test_the_burning_hull_glows_orange_then_chars(display):
    source = pygame.Surface((24, 24), pygame.SRCALPHA)
    source.fill((90, 120, 200, 255))
    style = dict(fd.BIRD, tongues=0, ember_k=0.0)
    colours = _colours(fd.render(source, 0.2, style, (90, 90), (33, 33)))
    assert any(c.r > 200 and 60 < c.g < 200 and c.b < 100 for c in colours)
    dark = _colours(fd.render(source, 0.38, style, (90, 90), (33, 33)))
    assert any(c.r < 80 and c.g < 60 and c.b < 60 for c in dark)                      # the charred silhouette


def test_flames_die_with_the_pixels_that_fed_them(display):
    source = pygame.Surface((24, 24), pygame.SRCALPHA)
    source.fill((90, 120, 200, 255))
    colours = _colours(fd.render(source, 0.7, fd.BIRD, (90, 90), (33, 33)))
    assert not any(c.r > 200 and c.g < 200 and c.b < 90 and c.a > 60 for c in colours)


def test_nearly_transparent_pixels_do_not_burn(display):
    source = pygame.Surface((24, 24), pygame.SRCALPHA)
    pygame.draw.rect(source, (200, 60, 60, 255), (10, 10, 4, 4))
    source.set_at((0, 0), (255, 255, 255, 20))
    box = _box(fd.render(source, 0.0, fd.BIRD, (60, 60), (18, 18)))
    assert box.width <= 6 and box.height <= 6


def test_the_blaze_of_the_ship_is_dense_and_wide(ship_frames):
    frames = ship_frames[1]
    solid = pygame.mask.from_surface(frames[8], 150).count()          # (the flames are thick at 0.25 of the death)
    assert solid > 6000
