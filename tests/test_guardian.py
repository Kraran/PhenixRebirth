"""Always-available simulation, deterministic warning and dodgeable laser bolts."""
import copy

import pygame
import pytest

import guardian as gd
import story_state as ss
from story import StoryHub


@pytest.fixture
def display():
    pygame.display.init()
    pygame.display.set_mode((1280, 720))


@pytest.mark.parametrize("act", [1, 2, 3])
@pytest.mark.parametrize("mode", ss.MODES)
def test_available_and_replayable_in_every_act_and_mode(act, mode):
    state = ss.default_state()
    state.update(act=act, mode=mode)
    mission = ss.mission_by_id("test_guardians")
    assert mission in ss.visible_missions(state)
    assert ss.mission_group(mission) == ss.GROUP_EXTRA
    assert ss.mission_playable(state, mission)
    for win in (True, False, True):
        before = copy.deepcopy(state)
        result = ss.record_result(state, mission["id"], 9999, win, {"garg3": 6},
                                  loot="reactor_shield", used=["genesis"])
        assert state == before
        assert result["training"] and result["score"] == 0 and not result["fallen"]
        assert ss.mission_playable(state, mission)


def test_training_is_not_the_next_story_mission():
    state = ss.default_state()
    assert ss.next_mission(state, ss.visible_missions(state))["id"] == "ch1_sortie"
    assert ss.next_mission(state, [ss.mission_by_id("test_guardians")]) is None


def test_hub_launch_and_result_do_not_consume_or_save_progress(monkeypatch):
    hub = StoryHub()
    hub.state = ss.default_state()
    hub.state["items"]["got"]["genesis"] = "installed"
    hub.map_index = next(i for i, m in enumerate(hub.missions()) if m["id"] == "test_guardians")
    spec = hub._launch_selected()
    assert spec["training"] and spec["guardians"] and spec["items"] == []
    before = copy.deepcopy(hub.state)
    monkeypatch.setattr(hub, "save", lambda: pytest.fail("Simulation must not save progression"))
    hub.apply_result(spec["id"], 500, True, flawless=True)
    assert hub.state == before and hub.pane == "map"
    assert hub.missions()[hub.map_index]["id"] == "test_guardians"


@pytest.mark.parametrize("fps", [30, 60, 120, 144])
def test_charge_and_bolt_speed_do_not_depend_on_framerate(display, fps):
    form = gd.GuardianFormation()
    dt = 1 / fps
    elapsed = 0
    while not form.bullets and elapsed < 4:
        form.update(dt, 640)
        elapsed += dt
    assert gd.SHOT_GAP + gd.CHARGE_SECONDS - 1e-8 <= elapsed <= gd.SHOT_GAP + gd.CHARGE_SECONDS + 3 * dt
    bolt = form.bullets[0]
    start = bolt.y
    for _ in range(fps):
        bolt.update(dt)
    assert bolt.y - start == pytest.approx(gd.LASER_SPEED)


def test_charge_stops_aiming_and_killing_the_shooter_cancels_it(display):
    form = gd.GuardianFormation()
    form.shot_wait = 0
    form.update(0.01, 640)
    shooter = form.shooter
    assert shooter is not None
    origin = shooter.x
    form.update(0.2, 50)
    assert shooter.x == origin
    while form.shooter is not None:
        form.update(1 / 120, 50)
    form.update(1 / 120, 50)
    assert abs(shooter.x - origin) < 1  # no teleport when movement resumes
    form.bullets.clear()
    form.shot_wait = 0
    form.update(0.01, 640)
    shooter = form.shooter
    shooter.kill()
    form.update(1.0, 50)
    assert not form.bullets and form.shooter is None


def test_one_active_laser_at_a_time_and_safe_dodge_window(display):
    form = gd.GuardianFormation()
    for _ in range(1800):
        form.update(1 / 60, 640)
        assert len(form.bullets) <= 1
        assert sum(b.charge > 0 for b in form.get_alive_enemies()) <= 1
    # Even the starting Shield can clear the beam's lane during the warning alone.
    assert 480 * 0.4 * gd.CHARGE_SECONDS > gd.LASER_WIDTH + 48


def test_laser_hitbox_covers_the_swept_path_and_tail():
    bolt = gd.FireLaser(500, 200)
    bolt.update(1.5)
    assert bolt.get_hitbox().collidepoint(500, 450)
    bolt.update(0.5)
    box = bolt.get_hitbox()
    assert box.top <= 590 - gd.LASER_LENGTH and box.bottom >= 720
    assert not box.collidepoint(530, 600)


def test_last_wave_waits_for_remaining_projectiles(display):
    form = gd.GuardianFormation()
    for b in form.enemies:
        b.kill()
    form.update(1.6, 640)
    assert form.wave == 2 and len(form.get_alive_enemies()) == 3
    form.bullets.append(gd.FireLaser(640, 200))
    for b in form.enemies:
        b.kill()
    assert not form.all_dead()
    form.update(4, 640)
    assert form.all_dead() and form.destroyed == 6


def test_drawing_reuses_loaded_art(display, monkeypatch):
    form = gd.GuardianFormation()
    canvas = pygame.Surface((1280, 720))
    form.draw(canvas)
    monkeypatch.setattr(pygame.image, "load", lambda *a: pytest.fail("Loaded sprites during draw"))
    form.shot_wait = 0
    for _ in range(240):
        form.update(1 / 60, 640)
        form.draw(canvas)


def test_game_launch_collision_and_return_to_arcade(tmp_path, monkeypatch):
    import user_settings
    from game import Game
    from enemy import EnemyFormation
    import update_play

    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    game = Game()
    game.story.state = ss.default_state()
    game.story.state["mode"] = "veteran"
    game.story.state["items"]["got"]["genesis"] = "installed"
    game.story.map_index = next(i for i, m in enumerate(game.story.missions()) if m["id"] == "test_guardians")
    spec = game.story._launch_selected()
    before = copy.deepcopy(game.story.state)
    game._begin_adventure(spec)
    game.stage_transition = None
    assert isinstance(game.formation, gd.GuardianFormation)
    assert game.player.lives >= 3 and game.player.adventure_wall == "immune"
    assert not game._veteran_adventure() and game.adventure["loot_plan"] is None
    game.player.y = 625
    game.player.invulnerable = 0
    game.player.phenix_timer = 0
    game.player.morph_dir = 0
    bolt = gd.FireLaser(game.player.x, 200)
    bolt.update(1.7)
    game.formation.bullets = [bolt]
    lives = game.player.lives
    update_play.enemy_attacks_vs_players(game)
    assert game.player.lives == lives - 1 and not bolt.alive
    game.dt = 1 / 60
    game.draw()
    game._bank_adventure(False)
    assert game.story.state == before
    # Finish both waves and exercise the actual victory -> map transition.
    game._begin_adventure(spec)
    game.stage_transition = None
    for bird in game.formation.enemies:
        bird.kill()
    game.formation.update(1.6, 640)
    for bird in game.formation.enemies:
        bird.kill()
    game.formation.bullets.clear()
    game.update()
    assert game.stage_transition == "fly_up"
    game.player.y = -100
    game.update()
    assert not game.started and game.menu_screen == "story_hub"
    assert game.story.state == before
    # A lost Veteran test also returns to the map with the same save.
    game._begin_adventure(spec)
    game.stage_transition = None
    game.player.alive = False
    game.player.dying = False
    game.player.lives = 0
    game.update()
    assert not game.started and game.menu_screen == "story_hub"
    assert game.story.state == before
    game._setup_stage(3)
    assert isinstance(game.formation, EnemyFormation)
    game.running = False
