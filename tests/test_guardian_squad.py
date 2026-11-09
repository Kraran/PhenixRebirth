"""The Guardians in the waves of the Adventure (step 1 of the Guardians plan): a squad that comes with a wave, whatever
the formation, goes into the targets, the attacks, the end of the wave and the drawing."""

import pygame
import pytest

import guardian as gd
import story_state as ss
import update_play

pytestmark = pytest.mark.usefixtures("training_missions")   # (the TEST missions, out of the Adventure)

PLANS = {"phenix_3": {19: 2}, "act3_gate": {23: 2, 24: 2, 25: 3}, "up_shield_4": {20: 2}, "up_phenix_3": {20: 2},
         "final_1": {22: 1}, "final_2": {21: 2}, "final_3": {21: 2}, "final_4": {25: 3}, "final_5": {30: 4}}
DT = 1 / 60


@pytest.fixture
def display():
    pygame.display.init()
    pygame.display.set_mode((1280, 720))


@pytest.fixture
def game(tmp_path, monkeypatch):
    import user_settings
    from game import Game
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    g = Game()
    g.story.state = ss.default_state()
    yield g
    g.running = False


def _fly(game, mission_id, wave_i=0):
    """The mission, its wave `wave_i` in play."""
    m = ss.mission_by_id(mission_id)
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["act"] = m["acts"][0]
    st["flags"][m["need"]] = True
    ss.mark_scene_seen(st, mission_id)
    game.story.state = st
    game.story.map_index = next(i for i, x in enumerate(game.story.missions()) if x["id"] == mission_id)
    spec = game.story._launch_selected()
    game._begin_adventure(spec)
    if wave_i:
        game.adventure["wave_i"] = wave_i
        game._setup_stage(game.stage)
    game.stage_transition = None
    game.dt = DT
    return spec


def _arrive(sq, seconds=6.0):
    """The squad flies in (no birds, the ship in the middle)."""
    for _ in range(int(seconds / DT)):
        sq.tick(DT, 640, 625, [], [])


# ---------------------------------------------------------------- the missions
def test_the_nine_missions_and_their_guardians():
    have = {m["id"]: m["guardians_at"] for m in ss.MISSIONS if m.get("guardians_at")
            and not m["id"].startswith("guardians_")}                       # (the series: tests/test_guardians_series.py)
    assert have == PLANS
    for mid, plan in PLANS.items():
        m = ss.mission_by_id(mid)
        waves = m.get("waves") or [m.get("stage")]
        assert set(plan) <= set(waves), mid                     # (a wave the mission plays)
    for mid in ("bonus_vip", "test_guardians", "dome_1", "paint_1", "phenix_1", "lander_deimos", "raid_deimos",
                "sentinelle_1", "ast_2"):
        assert "guardians_at" not in ss.mission_by_id(mid), mid


def test_the_spec_carries_the_plan_and_only_its_wave_gets_the_squad(game):
    spec = _fly(game, "phenix_3")
    assert spec["guardians_at"] == {19: 2}
    assert game.stage == 18 and game.guardian_squad is None              # the first wave: no Guardian
    game.adventure["wave_i"] = 1
    game._setup_stage(19)
    assert game.stage == 19 and isinstance(game.guardian_squad, gd.GuardianSquad)
    assert len(game.guardian_squad.guardians) == 2
    game.adventure["wave_i"] = 0
    game._setup_stage(18)                                                 # (back to the first wave: none again)
    assert game.stage == 18 and game.guardian_squad is None


def test_no_squad_in_the_arcade_game(game):
    game.adventure = None
    for stage in (19, 20, 25):
        game._setup_stage(stage)
        assert game.guardian_squad is None


# ---------------------------------------------------------------- the squad
def test_they_come_down_from_the_top_one_after_the_other(display):
    sq = gd.GuardianSquad(3)
    assert not sq.targets() and all(g.y < 0 for g in sq.guardians)
    seen = []
    for _ in range(int(6 / DT)):
        sq.tick(DT, 640, 625, [], [])
        seen.append(len(sq.targets()))
    assert seen[0] == 0 and seen[-1] == 3 and seen == sorted(seen)
    assert all(abs(g.y - gd.SQUAD_Y) < 30 and g.state == "patrol" for g in sq.guardians)
    xs = sorted(g.home_x for g in sq.guardians)
    assert xs[0] < 640 < xs[-1]


def test_they_fire_lasers_into_the_shots_of_the_formation_and_burn_its_birds(display):
    from enemy import Enemy
    sq = gd.GuardianSquad(1)
    _arrive(sq)
    g = sq.guardians[0]
    g.dive_wait = 1e9                                                       # (it fires, it does not dive)
    shots = []
    bird = Enemy(g.x, g.y + 140, stage=1)
    bird.state = "formation"
    for _ in range(int(8 / DT)):
        for b in shots:
            b.update(DT)
        shots[:] = [b for b in shots if b.alive]
        sq.tick(DT, g.x, 625, shots, [bird] if bird.alive else [])
        bird.x = g.x
        if not bird.alive:
            break
    assert any(isinstance(b, gd.FireLaser) for b in shots) or sq.burned
    assert not bird.alive and sq.burned == 1 and sq.effects                  # it burns (no points)


def test_a_bird_with_no_picture_explodes_instead(display):
    class Garg:
        alive, dying, x, y = True, False, 640.0, 300.0

        def get_hitbox(self):
            return pygame.Rect(620, 280, 40, 40)

        def kill(self, flash=True):
            self.alive = False

    bolt = gd.FireLaser(640, 240)
    bolt.update(0.1)                                                        # (its tip goes past the gargoyle)
    owner = type("O", (), {"bullets": [bolt], "effects": [], "sounds": None})()
    garg = Garg()
    assert gd.burn_birds(owner, [garg], {}) == 1 and not garg.alive and not owner.effects


def test_a_laser_dropped_from_the_shots_lets_its_guardian_go(display):
    sq = gd.GuardianSquad(1)
    _arrive(sq)
    g = sq.guardians[0]
    g.emission = gd.FireLaser(g.x, g.y + 16)
    assert g.laser_attached
    sq.tick(DT, 640, 625, [], [])                                           # (the shots were cleared)
    assert g.emission is None and not g.laser_attached


def test_the_squad_is_cleared_when_all_are_down(display):
    sq = gd.GuardianSquad(2)
    _arrive(sq)
    assert not sq.clear()
    sq.guardians[0].kill()
    assert not sq.clear() and len(sq.alive()) == 1
    sq.kill_all()
    assert sq.clear()


# ---------------------------------------------------------------- in the game
def test_the_shots_hit_the_guardians_of_the_wave(game):
    _fly(game, "phenix_3", wave_i=1)
    game.formation.enemies = []                                             # (no bird in the way of the shot)
    sq = game.guardian_squad
    _arrive(sq)
    g = sq.guardians[0]
    assert g in gd.targets(game)
    hp = g.hp
    ship = game.player
    rect = pygame.Rect(0, 0, 6, 6)
    rect.center = g.get_hitbox().center                                    # (the body, not a wing)
    ship.get_bullet_rects = lambda: [(0, rect.copy())]
    ship.destroy_bullet = lambda *a, **k: None
    update_play.player_bullets_vs_enemies(game)
    assert g.hp == hp - 1


def test_the_wave_does_not_end_while_a_guardian_flies(game):
    _fly(game, "phenix_3", wave_i=1)
    sq = game.guardian_squad
    for e in game.formation.enemies:
        e.alive = False
        e.dying = False
    game.formation.bullets.clear()
    game.update()
    assert game.stage_transition is None                                  # the birds are down, not the Guardians
    sq.kill_all()
    for _ in range(60 * 4):                                               # (and their debris have fallen)
        if game.stage_transition is not None:
            break
        game.update()
    assert game.stage_transition == "fly_up" and not any(g.fx_active() for g in sq.guardians)


def test_their_laser_burns_the_ship_in_any_wave(game):
    _fly(game, "phenix_3", wave_i=1)
    p = game.player
    p.y, p.invulnerable, p.phenix_timer, p.morph_dir = 625, 0, 0, 0
    bolt = gd.FireLaser(p.x, 200)
    bolt.update(1.7 / 3)
    game.formation.bullets = [bolt]
    lives = p.lives
    update_play.enemy_attacks_vs_players(game)
    assert p.lives == lives - 1 and bolt.alive                              # (it goes on, through the ship)


def test_a_diving_guardian_of_the_wave_hits_the_ship(game):
    _fly(game, "phenix_3", wave_i=1)
    sq = game.guardian_squad
    _arrive(sq)
    p = game.player
    p.invulnerable = 0
    g = sq.guardians[0]
    g.state = "dive"
    g.x, g.y = p.x, p.y
    lives = p.lives
    update_play.enemy_attacks_vs_players(game)
    assert p.lives == lives - 1 and not g.alive


def test_the_boss_takes_its_guardians_with_it(game):
    _fly(game, "final_5", wave_i=4)
    assert game.stage == 30 and game.boss_saucer is not None and len(game.guardian_squad.guardians) == 4
    assert all(g.home_y == gd.SQUAD_BOSS_Y for g in game.guardian_squad.guardians)      # below the saucer
    hull = game.boss_saucer.get_hull_hitbox()
    assert gd.SQUAD_BOSS_Y - 40 > hull.bottom and gd.SQUAD_BOSS_Y < game.player.y - 120
    update_play.boss_cataclysm(game)
    assert game.guardian_squad.clear()


@pytest.mark.parametrize("mid", ["final_2", "final_3"])
def test_the_swarm_and_the_galaga_chains_get_their_guardians(game, mid):
    _fly(game, mid)
    sq = game.guardian_squad
    assert sq is not None and len(sq.guardians) == 2
    for _ in range(int(5 / DT)):
        game.update()
        if not game.started:
            break
    assert sq.targets()                                                   # (flown in, in play)
    game.draw()


def test_the_game_draws_the_squad(game, monkeypatch):
    _fly(game, "phenix_3", wave_i=1)
    seen = []
    monkeypatch.setattr(game.guardian_squad, "draw", lambda surface: seen.append(surface))
    game.draw()
    assert seen
