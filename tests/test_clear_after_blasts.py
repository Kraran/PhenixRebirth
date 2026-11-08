"""The end of a level: the ship flies up only once the explosions of the last enemies have finished (not while they
still play on the screen)."""

import pytest

import highscores
import update_play
import user_settings
from explosion import Explosion


@pytest.fixture
def game(tmp_path, monkeypatch):
    from game import Game
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(highscores, "HS_FILE", str(tmp_path / "hs.json"))
    g = Game()
    g.play_mode = "solo"
    g.adventure = None
    g._begin_run()
    g.stage_transition = None
    g.dt = 1 / 60
    yield g
    g.running = False


def _last_bird_down(game, kind="enemy"):
    e = game.formation.enemies[0]
    for other in game.formation.enemies:
        other.alive = other.dying = False
    game.formation.bullets.clear()
    game.explosions = [game._boom(e.x, e.y, kind=kind)]
    return game.explosions[0]


@pytest.mark.parametrize("kind", ["enemy", "gameover", "collision"])
def test_the_ship_waits_for_the_last_explosion(game, kind):
    blast = _last_bird_down(game, kind)
    frames = 0
    while game.stage_transition is None and frames < 400:
        game.update()
        frames += 1
        if game.stage_transition is None and frames < int(blast.max_life * 60) - 2:
            assert not blast.is_finished()                               # (still on the screen: the ship waits)
    assert game.stage_transition == "fly_up"
    assert blast.is_finished()                                           # (it played to its end)
    assert int(blast.max_life * 60) - 2 <= frames <= int(blast.max_life * 60) + 3


def test_without_an_explosion_the_ship_flies_up_at_once(game):
    _last_bird_down(game)
    game.explosions = []
    game.update()
    assert game.stage_transition == "fly_up"


def test_the_shield_ripple_and_the_landing_puff_do_not_hold_it(game):
    _last_bird_down(game)
    game.explosions = [Explosion(640, 600, kind="shield"), Explosion(600, 680, kind="dust")]
    assert not update_play.blasts_running(game)
    game.update()
    assert game.stage_transition == "fly_up"


# ------------------------------------------------------------------ the Guardians
def _with_squad(game, n=1):
    import guardian
    sq = guardian.GuardianSquad(n, game.sounds)
    for g in sq.guardians:
        g.entry = 0.0
        g.y, g.state = 150.0, "patrol"
    game.guardian_squad = sq
    return sq


def _frames_to_fly_up(game, limit=600):
    frames = 0
    while game.stage_transition is None and frames < limit:
        game.update()
        frames += 1
    return frames


def test_the_ship_waits_for_the_debris_of_the_last_guardian(game):
    _last_bird_down(game)
    game.explosions = []
    sq = _with_squad(game)
    sq.guardians[0].kill()                                               # (shot down: chips, embers, smoke, wings)
    assert sq.clear() and sq.guardians[0].fx_active()
    assert update_play.blasts_running(game)
    frames = _frames_to_fly_up(game)
    assert game.stage_transition == "fly_up" and frames > 10
    assert not sq.guardians[0].fx_active()                               # (they had all played to their end)


def test_the_ship_waits_for_a_burned_bird_to_fall_to_ash(game):
    import guardian
    e = game.formation.enemies[0]
    _last_bird_down(game)
    game.explosions = []
    sq = _with_squad(game, 0)
    burning = guardian.BurningBird(e)
    sq.effects.append(burning)
    frames = _frames_to_fly_up(game)
    assert game.stage_transition == "fly_up" and not burning.alive
    assert frames >= int(guardian.BURN_SECONDS * 60) - 2


def test_a_guardian_still_flying_is_not_a_blast(game):
    _last_bird_down(game)
    game.explosions = []
    _with_squad(game)
    assert not update_play.guardian_blasts_running(game)                 # (alive: it holds the end by itself, squad_clear)
