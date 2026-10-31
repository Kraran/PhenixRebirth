"""Guardian lasers ignore all defences; normal shots keep their protections."""
from types import SimpleNamespace

import pygame
import pytest

import guardian as gd
import ship_blast as sbl
import ship_burn as sb
from player import Player
import update_play


@pytest.fixture
def display():
    pygame.display.init()
    pygame.display.set_mode((1280, 720))


def _ship(hull, active=False):
    ship = Player(640, 625, ship_id=hull)
    ship.lives = 3
    ship.phenix_timer = 5.0 if active else 0.0
    sb.prepare(ship)
    return ship


def _game(ship, bolt, guardians=True):
    form = gd.GuardianFormation()
    form.bullets = [bolt]
    sounds = SimpleNamespace(play=lambda *a, **kw: None)
    return SimpleNamespace(
        _ships=lambda: [ship], player=ship, formation=form,
        adventure={"guardians": guardians}, boss_saucer=None, play_mode="solo",
        sounds=sounds, shake_amount=0.0, stage_life_lost=False, explosions=[],
        _shield_absorb=lambda *a: pytest.fail("Guardian laser was absorbed"),
        _add_score=lambda *a: pytest.fail("Guardian laser awarded score"),
    )


@pytest.mark.parametrize("hull", ["shield", "phoenix"])
@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("protection", ["none", "blink", "infinite", "morph_in", "morph_out"])
def test_guardian_laser_destroys_every_form_and_ignores_protection(display, hull, active, protection):
    ship = _ship(hull, active)
    ship.invulnerable = 8 if protection == "blink" else 0
    ship.infinite_lives = protection == "infinite"
    if protection.startswith("morph"):
        ship.morph_dir = 1 if protection == "morph_in" else -1
        ship.morph_duration = 1.0
    was_active = ship.is_phenix
    bolt = gd.FireLaser(ship.x, ship.y - 100, 0)
    bolt.update(0.15)
    game = _game(ship, bolt)
    update_play.enemy_attacks_vs_players(game)
    assert ship.lives == 2 and ship.alive and ship.dying
    assert ship.guardian_burn.active_form == was_active
    assert isinstance(ship.guardian_burn, sbl.ShipBlast)       # (the big blast, as in every death of the ship)
    assert not ship.is_phenix and ship.morph_dir == 0
    assert ship.invulnerable == 0 and ship.just_lost_life
    assert game.stage_life_lost and game.adventure["life_lost"]
    assert bolt.alive  # continues through the ship
    update_play.enemy_attacks_vs_players(game)
    assert ship.lives == 2  # no second life lost during the same destruction


@pytest.mark.parametrize("hull", ["shield", "phoenix"])
@pytest.mark.parametrize("fps", [15, 30, 60, 120, 144])
@pytest.mark.parametrize("last_life", [False, True])
def test_full_animation_then_respawn_or_death(display, hull, fps, last_life):
    ship = _ship(hull, True)
    ship.lives = 1 if last_life else 3
    ship.shots = [{"x": 640, "y": 500}]
    assert ship.burn_by_guardian()
    origin = ship.x, ship.y
    canvas = pygame.Surface((1280, 720), pygame.SRCALPHA)
    elapsed = 0.0
    dt = 1 / fps
    while elapsed + dt < sbl.DURATION - 1e-8:
        ship.update(dt, {})
        elapsed += dt
        ship.draw(canvas)
        assert ship.alive and ship.dying and ship.guardian_burn is not None
        assert (ship.x, ship.y) == origin and not ship.shots
        assert not ship.get_bullet_rects() and ship.get_hitbox().width == 0
    ship.update(sbl.DURATION - elapsed + 1e-6, {})
    assert ship.guardian_burn is None and not ship.dying
    assert ship.alive == (not last_life)
    assert ship.lives == (0 if last_life else 2)
    if not last_life:
        assert (ship.x, ship.y) == (640, 625)
        assert not ship.is_phenix and ship.invulnerable > 0
        # Respawn blink does not protect against a fresh Guardian laser.
        assert ship.burn_by_guardian() and ship.lives == 1


@pytest.mark.parametrize("hull", ["shield", "phoenix"])
def test_normal_damage_still_respects_form_and_invulnerability(display, hull):
    ship = _ship(hull, True)
    assert not ship.hit() and ship.lives == 3 and ship.guardian_burn is None
    ship.phenix_timer = 0
    ship.invulnerable = 2
    assert not ship.hit() and ship.lives == 3 and ship.guardian_burn is None


def test_special_rule_requires_guardian_mission(display):
    ship = _ship("phoenix", True)
    laser = gd.FireLaser(ship.x, ship.y - 100)
    laser.update(0.15)
    game = _game(ship, laser, guardians=False)
    update_play.enemy_attacks_vs_players(game)
    assert ship.lives == 3 and ship.guardian_burn is None


@pytest.mark.parametrize("hull", ["shield", "phoenix"])
def test_burning_draw_loads_and_smoothscales_nothing(display, hull, monkeypatch):
    ship = _ship(hull, True)
    normal, active = sb.frames(ship, False), sb.frames(ship, True)
    assert normal is not active
    assert pygame.image.tobytes(normal[0], "RGBA") != pygame.image.tobytes(active[0], "RGBA")
    assert pygame.mask.from_surface(normal[-1], 0).count() == 0
    assert pygame.mask.from_surface(active[-1], 0).count() == 0
    monkeypatch.setattr(pygame.image, "load", lambda *a: pytest.fail("Loaded art during impact/draw"))
    monkeypatch.setattr(pygame.transform, "smoothscale", lambda *a: pytest.fail("Scaled art during burn"))
    assert ship.burn_by_guardian()
    canvas = pygame.Surface((1280, 720), pygame.SRCALPHA)
    for _ in range(40):
        ship.update(1 / 60, {})
        ship.draw(canvas)


def test_normal_bird_bullet_does_not_use_the_guardian_rule(display):
    from enemy import EnemyBullet
    ship = _ship("phoenix", True)
    bolt = EnemyBullet(ship.x, ship.y)
    game = _game(ship, bolt)
    update_play.enemy_attacks_vs_players(game)
    assert ship.lives == 3 and ship.guardian_burn is None and not bolt.alive


@pytest.mark.parametrize("hull", ["shield", "phoenix"])
@pytest.mark.parametrize("active", [False, True])
def test_destruction_is_idempotent_and_does_not_change_normal_death_duration(display, hull, active):
    ship = _ship(hull, active)
    duration = ship.DEATH_DURATION
    assert ship.burn_by_guardian()
    effect = ship.guardian_burn
    assert not ship.burn_by_guardian()
    assert ship.lives == 2 and ship.guardian_burn is effect
    assert ship.DEATH_DURATION == duration
    ship.update(sbl.DURATION + 0.01, {})
    ship.invulnerable = 0
    assert not ship.hit() and ship.lives == 1
    assert ship.guardian_burn is None  # ordinary damage keeps its ordinary path
