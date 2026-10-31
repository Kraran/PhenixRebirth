"""Every explosion of the ship of the player is the big blast of the SpaceWar level (Game._ship_boom, src/ship_blast.py),
in the arcade game and in the Adventure; and the fantasy ringed planet never shows in a mission of the Adventure."""
import random

import pygame
import pytest

import ship_blast as sbl
import starfield as sf
import update_play
from explosion import Explosion
from test_smoke import run  # noqa: F401  (fixture)


class _NoKeys:
    def __getitem__(self, k):
        return False


def _blasts(g):
    return [e for e in g.explosions if isinstance(e, sbl.ShipBlast)]


def _game_started(run):
    g = run.game
    g._begin_run()
    run.frames(3)
    assert g.started
    g.stage_transition = None
    return g


def test_a_hit_that_costs_a_life_makes_the_blast_and_hides_the_hull_for_a_moment(run):
    g = _game_started(run)
    ship = g.player
    ship.invulnerable = 0
    g.explosions.clear()
    ship.hit()
    g._ship_boom(ship, "bullet")
    assert len(_blasts(g)) == 1 and not any(isinstance(e, Explosion) for e in g.explosions)
    assert ship.blast_hide == pytest.approx(0.55)
    surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
    ship.draw(surf)
    assert pygame.mask.from_surface(surf).count() == 0              # (hidden: the blast is drawn by the explosions)
    for _ in range(40):
        ship.update(1 / 60, _NoKeys())
    assert ship.blast_hide == 0.0
    ship.invulnerable = 0
    ship.draw(surf)
    assert pygame.mask.from_surface(surf).count() > 0               # (and it is back)


def test_the_last_life_hides_the_hull_for_the_whole_death(run):
    g = _game_started(run)
    ship = g.player
    ship.lives = 1
    ship.invulnerable = 0
    ship.hit()
    assert ship.dying
    g._ship_boom(ship, "gameover")
    assert ship.blast_hide >= ship.DEATH_DURATION


@pytest.mark.parametrize("site", ["bullet", "dive", "boss_hull", "edge"])
def test_every_kind_of_hit_in_the_game_makes_the_blast(run, site):
    g = _game_started(run)
    ship = g.player
    ship.invulnerable = 0
    ship.phenix_timer = 0.0
    ship.lives = 3
    g.explosions.clear()
    if site == "bullet":
        from enemy import EnemyBullet
        g.formation.bullets = [EnemyBullet(ship.x, ship.y)]
        update_play.enemy_attacks_vs_players(g)
    elif site == "dive":
        e = g.formation.enemies[0]
        e.state = "diving"
        e.x, e.y = ship.x, ship.y
        update_play.enemy_attacks_vs_players(g)
    elif site == "boss_hull":
        class Hull:
            alive = True
            bullets = []
            cells = []
            decorations = []

            def get_hull_hitbox(self):
                return pygame.Rect(ship.x - 40, ship.y - 40, 80, 80)

            def update(self, *a, **k):
                pass
        g.boss_saucer = Hull()
        update_play.enemy_attacks_vs_players(g)
        g.boss_saucer = None
    else:
        ship.edge_death = True
        g._ship_boom(ship, "edge")
    assert _blasts(g), site
    # (the old explosions of the ship are gone; the bird that rammed it has its own, of the kind "collision")
    assert not any(isinstance(e, Explosion) and e.kind in ("bullet", "edge") for e in g.explosions)
    if site != "dive":
        assert not any(isinstance(e, Explosion) and e.kind == "collision" for e in g.explosions)


def test_the_blast_has_the_pose_of_the_ship(run):
    g = _game_started(run)
    p = g.player
    p.asteroid_mode, p.ast_angle = True, 0.0
    g._ship_boom(p, "bullet")
    assert _blasts(g)[-1].pose == (-90.0, 1.0)
    p.asteroid_mode = False
    g._ship_boom(p, "bullet")
    assert _blasts(g)[-1].pose == (None, 1.0)


def test_the_boss_hull_and_the_boss_bullets_make_the_blast_with_or_without_infinite_lives(run):
    g = _game_started(run)
    ship = g.player
    ship.phenix_timer = 0.0

    class Shot:
        alive = True

        def get_hitbox(self):
            return pygame.Rect(ship.x - 5, ship.y - 5, 10, 10)

    class Boss:
        alive = True
        cells = decorations = ()

        def __init__(self, hull, shots):
            self.hull, self.bullets = hull, shots

        def get_hull_hitbox(self):
            return self.hull

    for infinite in (True, False):
        ship.infinite_lives = infinite
        for hull in (pygame.Rect(ship.x - 40, ship.y - 40, 80, 80), pygame.Rect(0, 0, 0, 0)):
            ship.alive, ship.dying, ship.invulnerable, ship.lives = True, False, 0.0, 3
            g.boss_saucer = Boss(hull, [] if hull.width else [Shot()])
            g.explosions.clear()
            update_play.enemy_attacks_vs_players(g)
            assert len(_blasts(g)) == 1, (infinite, hull)
            assert not any(isinstance(e, Explosion) and e.kind == "bullet" for e in g.explosions)
    ship.infinite_lives = False
    g.boss_saucer = None


def test_the_wall_and_the_invaders_floor_make_the_blast_too(run):
    g = _game_started(run)
    ship = g.player
    ship.phenix_timer = 0.0
    ship.invulnerable = 0.0
    ship.lives = 3
    ship.edge_timer = ship.EDGE_KILL_TIME + 0.1                       # (the edge of the screen: lightning)
    g.explosions.clear()
    g.input_grace = 0
    update_play.tick_ships(g)
    assert len(_blasts(g)) == 1 and not any(isinstance(e, Explosion) and e.kind == "edge" for e in g.explosions)
    ship.blast_hide = 0.0
    g.explosions.clear()
    g.formation.invaded = True                                         # (the invaders reach the ship: the end)
    g.stage_transition = None
    ship.alive, ship.dying, ship.lives, ship.invulnerable = True, False, 3, 0.0
    update_play.boss_floor_check(g)
    assert len(_blasts(g)) == 1 and ship.dying and ship.blast_hide >= ship.DEATH_DURATION
    g.formation.invaded = False


def test_the_blast_is_updated_drawn_and_removed_with_the_other_explosions(run):
    g = _game_started(run)
    g.explosions.clear()
    g._ship_boom(g.player, "bullet")
    blast = _blasts(g)[0]
    surf = pygame.Surface((1280, 720))
    blast.draw(surf)
    for _ in range(int(60 * (sbl.DURATION + 0.5))):
        run.frames(1)
        g.player.invulnerable = 5.0
    assert blast not in g.explosions


def test_the_blast_is_bigger_for_a_ship_at_full_size(display=None):
    pygame.display.init()
    pygame.display.set_mode((1280, 720))
    from player import Player
    p = Player(400, 300, ship_id="shield")
    small = sbl.ShipBlast(p, None, 0.5, random.Random(1))
    full = sbl.ShipBlast(p, None, 1.0, random.Random(1))
    assert full.size == pytest.approx(small.size * sbl.FULL_SHIP_GROW) and full.size > small.size


def test_the_asteroids_hit_makes_the_blast_at_the_place_of_the_hit(run):
    import asteroids
    g = run.game
    g.adventure = {"asteroids": True}
    p = g.player
    p.x, p.y, p.invulnerable = 300.0, 200.0, 0.0
    p.alive, p.dying, p.phenix_timer = True, False, 0.0
    p.lives = 3
    g.explosions.clear()
    asteroids._ship_hit(g, type("F", (), {"debris": lambda *a, **k: None})())
    blasts = _blasts(g)
    assert len(blasts) == 1 and (blasts[0].x, blasts[0].y) == (300.0, 200.0)


# ------------------------------------------------------------------ the fantasy ringed planet
@pytest.fixture
def screen():
    pygame.display.init()
    pygame.display.set_mode((1280, 720))
    yield


def test_the_ringed_fantasy_planet_never_comes_in_a_mission_but_still_in_the_arcade(screen):
    names = set()
    for seed in range(300):
        random.seed(seed)
        names.add(sf.Planet().filename)
    assert "fantasy_rings.png" in names                              # (the arcade game keeps it)
    s = sf.Starfield()
    s.set_adventure(True)
    assert s.no_rings
    names = set()
    for seed in range(300):
        random.seed(seed)
        names.add(sf.Planet(no_rings=s.no_rings).filename)
    assert "fantasy_rings.png" not in names and "saturn.png" in names
    s.set_adventure(False)
    assert not s.no_rings
    names = set()
    for seed in range(300):
        random.seed(seed)
        names.add(sf.Planet(no_rings=s.no_rings).filename)
    assert "fantasy_rings.png" in names


def test_the_sky_that_spawns_planets_in_a_mission_has_no_ringed_planet(screen):
    s = sf.Starfield()
    s.set_adventure(True)
    spawned = set()
    for seed in range(400):
        random.seed(seed)
        s.planets, s.nebula = [], None
        s.planet_timer = 0.0
        s.update(1 / 60, 640.0, stage=1, menu=False)
        spawned.update(p.filename for p in s.planets)
    assert spawned and "fantasy_rings.png" not in spawned
    assert len(spawned) > 3


def test_a_new_sky_has_the_ringed_planet_again_and_nothing_leaks_between_skies(screen):
    mission = sf.Starfield()
    mission.set_adventure(True)
    arcade = sf.Starfield()
    assert mission.no_rings and not arcade.no_rings                     # (a flag of the sky, not of the class)


def test_a_ringed_planet_already_in_the_sky_leaves_when_a_mission_starts(screen):
    s = sf.Starfield()
    ring = sf.Planet()
    other = sf.Planet()
    ring.filename, other.filename = "fantasy_rings.png", "mars.png"
    s.planets = [ring, other]
    s.set_adventure(True)
    assert s.planets == [other]
    s.set_adventure(True)                                            # (idempotent)
    assert s.planets == [other]


def test_the_game_tells_the_sky_about_the_adventure_every_frame(run):
    g = run.game
    g.started = True
    g.adventure = {"mission": "x"}
    ring = sf.Planet()
    ring.filename = "fantasy_rings.png"
    g.starfield.planets = [ring]
    g._tick_stars()
    assert g.starfield.no_rings and ring not in g.starfield.planets
    g.adventure = None
    g._tick_stars()
    assert not g.starfield.no_rings
