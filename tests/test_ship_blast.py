"""The big explosion of the ship in the SpaceWar level (src/ship_blast.py)."""
import random

import pygame
import pytest

import ship_blast as sbl
import ship_burn as sb
from player import Player
from test_smoke import run  # noqa: F401  (fixture)


@pytest.fixture
def display():
    pygame.display.init()
    pygame.display.set_mode((1280, 720))


def _ship(hull="shield"):
    ship = Player(400, 300, ship_id=hull)
    ship.lives = 1
    ship.ast_vx, ship.ast_vy = 100.0, -50.0
    sb.prepare(ship)
    return ship


def _blast(hull="shield", angle=30.0, scale=0.5, seed=1):
    return sbl.ShipBlast(_ship(hull), angle, scale, random.Random(seed))


def _lit(blast, t, size=(1280, 720)):
    blast.age = 0.0
    step = 1 / 60
    while blast.age < t:
        blast.update(step)
    surf = pygame.Surface(size)
    blast.draw(surf)
    return surf


def _count(surf):
    return pygame.mask.from_threshold(surf, (0, 0, 0), (1, 1, 1)).count()


@pytest.mark.parametrize("hull", ["shield", "phoenix"])
def test_the_hull_breaks_into_shards_that_cover_the_ship(display, hull):
    b = _blast(hull, None, 1.0)
    assert 6 <= len(b.shards) <= sbl.SHARDS
    # (all the opaque pixels of the hull end in some shard)
    img = sb._source(_ship(hull), _ship(hull).is_phenix)
    solid = sum(1 for x in range(img.get_width()) for y in range(img.get_height()) if img.get_at((x, y)).a > 24)
    assert solid > 0
    area = sum(s.imgs[0].get_width() * s.imgs[0].get_height() for s in b.shards)
    assert area >= solid * b.shard_k ** 2 * 0.9


def test_the_shards_fly_apart_from_the_ship_and_slow_down(display):
    b = _blast()
    x0 = [(s.x, s.y) for s in b.shards]
    for _ in range(30):
        b.update(1 / 60)
    spread0 = sum(abs(x - 400) + abs(y - 300) for x, y in x0)
    spread1 = sum(abs(s.x - 400) + abs(s.y - 300) for s in b.shards)
    assert spread1 > spread0 + 50
    v1 = sum(abs(s.vx) + abs(s.vy) for s in b.shards)
    for _ in range(60):
        b.update(1 / 60)
    assert sum(abs(s.vx) + abs(s.vy) for s in b.shards) < v1


def test_the_shards_turn(display):
    b = _blast()
    a0 = [s.angle for s in b.shards]
    b.update(0.5)
    assert any(abs(s.angle - a) > 5 for s, a in zip(b.shards, a0))


def test_the_blast_lasts_more_than_two_seconds():
    assert 2.0 <= sbl.DURATION <= 3.0


def test_the_blast_lasts_and_then_is_finished_and_draws_nothing(display):
    b = _blast()
    assert not b.finished
    b.update(sbl.DURATION - 0.01)
    assert not b.finished
    b.update(0.02)
    assert b.finished
    surf = pygame.Surface((1280, 720))
    b.draw(surf)
    assert _count(surf) == 1280 * 720


def test_the_blast_starts_with_a_flash_then_the_fireball_then_dies_out(display):
    b = _blast()
    flash = _count(_lit(b, 0.05))
    mid = _count(_lit(_blast(), 0.5))
    late = _count(_lit(_blast(), 2.3))
    assert flash < 1280 * 720 * 0.99 and flash < 1280 * 720 - 3000   # (a lot of light around the ship)
    assert 1280 * 720 - mid > 3000
    assert (1280 * 720 - mid) > (1280 * 720 - late)


def test_the_flash_is_whiter_than_the_end(display):
    surf = _lit(_blast(), 0.04)
    centre = surf.get_at((400, 300))
    assert min(centre[:3]) > 150
    late = _lit(_blast(), 2.2)
    assert sum(late.get_at((400, 300))[:3]) < sum(centre[:3])


def test_the_shock_ring_runs_out_from_the_ship(display):
    def ring_radius(t):
        b = _blast()
        b.sparks, b.embers, b.puffs, b.shards = [], [], [], []      # (the rings alone)
        surf = _lit(b, t)
        best = 0
        for x in range(400, 1000):
            if sum(surf.get_at((x, 300))[:3]) > 60:
                best = x - 400
        return best

    assert ring_radius(0.5) > ring_radius(0.2) + 20


def _only(b, keep):
    """The blast with only some of its parts: 'shards', 'sparks', 'embers', 'puffs'."""
    for name in ("shards", "sparks", "embers", "puffs"):
        if name not in keep:
            setattr(b, name, [])
    return b


def _changed_far(a, b, centre=(400, 300), far=130):
    n = 0
    for y in range(0, 720):
        for x in range(0, 1280):
            if (x - centre[0]) ** 2 + (y - centre[1]) ** 2 > far * far and a.get_at((x, y)) != b.get_at((x, y)):
                n += 1
    return n


def test_sparks_are_drawn_far_from_the_ship(display, monkeypatch):
    monkeypatch.setattr(sbl, "RINGS", ())
    with_sparks = _lit(_only(_blast(), ("sparks",)), 0.35)
    without = _lit(_only(_blast(), ()), 0.35)
    assert _changed_far(with_sparks, without) > 20


def test_the_sparks_run_out_further_as_time_goes(display, monkeypatch):
    monkeypatch.setattr(sbl, "RINGS", ())

    def reach(t):
        a = _lit(_only(_blast(), ("sparks",)), t)
        base = _lit(_only(_blast(), ()), t)
        far = 0.0
        for y in range(0, 720, 2):
            for x in range(0, 1280, 2):
                if a.get_at((x, y)) != base.get_at((x, y)):
                    far = max(far, ((x - 400) ** 2 + (y - 300) ** 2) ** 0.5)
        return far

    assert reach(0.4) > reach(0.1) + 30


def test_the_fireball_is_bright_in_the_middle_and_fades(display, monkeypatch):
    monkeypatch.setattr(sbl, "RINGS", ())
    early = _lit(_only(_blast(), ()), 0.3).get_at((400, 300))
    late = _lit(_only(_blast(), ()), 1.5).get_at((400, 300))
    assert sum(early[:3]) > 300 and sum(late[:3]) < 60


def test_the_flash_lights_a_wide_disc_at_the_start(display, monkeypatch):
    def lit(flash):
        monkeypatch.setattr(sbl, "FLASH_TIME", flash)
        surf = _lit(_only(_blast(), ()), 0.04)
        return sum(sum(surf.get_at((400 + dx, 300))[:3]) for dx in range(100, 240, 10))

    assert lit(0.22) > lit(0.0) + 100


def test_the_shards_fly_in_x_and_in_y(display):
    b = _blast()
    spread = lambda: (sum(abs(s.x - 400) for s in b.shards), sum(abs(s.y - 300) for s in b.shards))
    x0, y0 = spread()
    for _ in range(30):
        b.update(1 / 60)
    x1, y1 = spread()
    assert x1 > x0 + 20 and y1 > y0 + 20


def test_the_blast_is_bigger_than_the_half_sized_ship_and_keeps_its_speed(display):
    b = _blast(scale=0.5)
    assert b.size == sbl.EFFECT_SIZE and b.shard_k == sbl.SCALE_UP
    assert (b.vx, b.vy) == pytest.approx((40.0, -20.0))
    b.update(0.5)
    assert b.shards  # (the pieces drift with the wreck)
    assert sum(s.x for s in b.shards) / len(b.shards) > 400


def test_two_blasts_with_the_same_seed_are_the_same_and_with_others_differ(display):
    a, b, c = _blast(seed=5), _blast(seed=5), _blast(seed=6)
    assert [round(s.vx, 3) for s in a.shards] == [round(s.vx, 3) for s in b.shards]
    assert [round(s.vx, 3) for s in a.shards] != [round(s.vx, 3) for s in c.shards]


def test_burn_by_guardian_with_blast_makes_a_blast_and_without_the_dust(display):
    p = _ship()
    assert p.burn_by_guardian(blast=True)
    assert isinstance(p.guardian_burn, sbl.ShipBlast) and p.dying and p.lives == 0
    q = _ship()
    assert q.burn_by_guardian()
    assert isinstance(q.guardian_burn, sb.ShipBurn)


def test_the_player_draws_and_updates_the_blast_and_drops_it_at_the_end(display):
    p = _ship()
    p.burn_by_guardian(blast=True)
    surf = pygame.Surface((1280, 720))
    p.draw(surf)
    burn = p.guardian_burn
    for _ in range(int(60 * (sbl.DURATION + 0.5))):
        burn.update(1 / 60)
    assert burn.finished


def test_the_level_kills_the_ship_with_the_blast_and_a_big_shake(run):
    import spacewar as sw
    from test_spacewar import _launch
    g = run.game
    _launch(run)
    form = sw.active(g)
    sw._kill_player(g, form)
    assert isinstance(g.player.guardian_burn, sbl.ShipBlast)
    assert g.shake_amount >= 30.0
