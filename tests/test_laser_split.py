"""The reflective coating: a Guardian's laser splits on the film of the dome / the Phenix form, more of it on the side it
touched, slice after slice (a ship moving under it changes the shares), the halves fall and burn the birds they cross,
the modules move further out while they run (src/laser_split.py)."""

import pygame
import pytest

import guardian as gd
import gyro
import laser_split as ls
import story_state as ss
import update_play

DT = 1 / 60


@pytest.fixture
def game(tmp_path, monkeypatch):
    import user_settings
    from game import Game
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    g = Game()
    m = ss.mission_by_id("guardians_1")
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["act"] = 2
    st["flags"][m["need"]] = True
    st["flags"][ss.REFLECT_FLAG] = True
    ss.mark_scene_seen(st, "guardians_1")
    g.story.state = st
    g.story.map_index = next(i for i, x in enumerate(g.story.missions()) if x["id"] == "guardians_1")
    g._begin_adventure(g.story._launch_selected())
    g.stage_transition = None
    g.dt = DT
    g.guardian_squad = None
    p = g.player
    p.x, p.y, p.invulnerable, p.morph_dir, p.phenix_timer = 640, 625, 0, 0, 50.0
    yield g
    g.running = False


def _laser(game, dx=0.0, y=330.0):
    bolt = gd.FireLaser(game.player.x + dx, y)
    game.formation.bullets = [bolt]
    return bolt


def _step(game, n=1, move=0.0):
    for _ in range(n):
        for b in game.formation.bullets:
            b.update(DT)
        game.formation.bullets = [b for b in game.formation.bullets if b.alive]
        game.player.x += move * DT
        ls.tick(game)
        update_play.enemy_attacks_vs_players(game)


def _shares(game, side):
    return [s.w for s in game.laser_slices if s.side == side]


def test_in_the_middle_half_and_half(game):
    lives = game.player.lives
    bolt = _laser(game)
    _step(game, 32)
    assert not bolt.alive and game.player.lives == lives and not game.player.dying
    right, left = _shares(game, 1), _shares(game, -1)
    assert len(right) == len(left) == gd.LASER_LENGTH // ls.SPACING       # (all of it, in slices of 2 px)
    assert all(abs(w - 0.5) < 0.02 for w in right + left)


@pytest.mark.parametrize("dx", [-30, 30])
def test_more_laser_on_the_side_it_touched(game, dx):
    lives = game.player.lives
    _laser(game, dx)
    _step(game, 25)
    near, far = (1, -1) if dx > 0 else (-1, 1)
    assert min(_shares(game, near)) > 0.75 and max(_shares(game, far)) < 0.25
    assert game.player.lives == lives


def test_at_the_edge_almost_all_of_it_and_a_thread_on_the_other_side(game):
    p = game.player
    _laser(game, ls.reach(p) - 0.5)
    _step(game, 25)
    assert min(_shares(game, 1)) >= 1 - ls.SHARE_MIN - 0.02 and 0 < max(_shares(game, -1)) <= ls.SHARE_MIN + 0.02


def test_beside_the_ship_the_laser_does_not_split(game):
    bolt = _laser(game, ls.reach(game.player) + 2)
    _step(game, 40)
    assert not getattr(game, "laser_slices", None) and bolt.eaten == 0


def test_a_ship_moving_under_the_laser_shares_each_slice_where_it_touches(game):
    game.player.ship_id = "phoenix"
    hw = ls.reach(game.player)
    game.player.x = 640 - 0.7 * hw
    bolt = _laser(game, 0.7 * hw, y=545.0)                           # (a laser at x=640, its tip at the film)
    for _ in range(60):                                              # (the ship slides right under a laser at x=640)
        _step(game, 1, move=160.0)
        if not bolt.alive:
            break
    right = [s.w for s in game.laser_slices if s.side == 1 and s.stream[0] == id(bolt)]
    assert len(right) > 10
    assert right[0] > 0.65 and right[-1] < right[0] - 0.2         # (first on the right of it, then towards its left)


def test_a_laser_the_ship_leaves_keeps_the_rest_of_it(game):
    bolt = _laser(game)
    _step(game, 22)                                                  # (its tip touches the film)
    assert 0 < bolt.eaten < gd.LASER_LENGTH
    game.player.x += 200                                             # (the ship darts away)
    eaten = bolt.eaten
    _step(game, 3)
    assert bolt.alive and bolt.eaten == eaten
    box = bolt.get_hitbox()
    assert box.bottom == pytest.approx(bolt.y - bolt.eaten, abs=1.5)  # (what is left of it goes on, shorter)


def test_the_bare_hull_or_no_coating_no_split(game):
    game.player.phenix_timer = 0.0
    game.player.lives = 3
    bolt = _laser(game)
    _step(game, 30)
    assert not getattr(game, "laser_slices", None) and bolt.eaten == 0 and game.player.lives == 2


def test_the_halves_fall_and_burn_the_birds_below(game):
    from enemy import Enemy
    _laser(game)
    _step(game, 22)
    a, b, cx, cy = ls.film(game.player)
    bird = Enemy(int(cx + a + 6), int(cy + 70), 1)
    bird.state = "formation"
    game.formation.enemies = [bird]
    _step(game, 30)
    assert not bird.alive or bird.dying


def test_the_modules_move_further_out_while_the_halves_run(game):
    p = game.player
    game.gyro = gyro.Gyro("shield", 2, 1, p)
    for _ in range(30):
        game.gyro.update(game, p, DT)
    before = game.gyro.target(p, 1)[0] - p.x
    _laser(game)
    for _ in range(30):
        _step(game)
        game.gyro.update(game, p, DT)
    assert game.gyro.split > 0.9 and game.gyro.target(p, 1)[0] - p.x == pytest.approx(before + ls.SPREAD[0], abs=0.5)
    for _ in range(90):
        _step(game)
        game.gyro.update(game, p, DT)
    assert game.gyro.split == 0.0                                    # (back once the halves are gone)


def test_the_halves_are_drawn_and_leave_the_screen(game):
    _laser(game, -12)
    surface = pygame.Surface((1280, 720))
    for _ in range(25):
        _step(game)
        ls.draw(game, surface)
        game.formation.bullets and game.formation.bullets[0].draw(surface)
    assert game.laser_slices and game.laser_glows
    _step(game, 120)
    assert not game.laser_slices and not game.laser_glows


def test_a_new_mission_starts_without_halves(game):
    _laser(game)
    _step(game, 25)
    assert game.laser_slices
    game._begin_adventure(game.story._launch_selected())
    assert game.laser_slices == [] and game.laser_glows == {}
