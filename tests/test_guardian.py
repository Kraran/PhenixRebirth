"""Always-available simulation, deterministic warning and dodgeable laser bolts."""
import copy
from collections import Counter

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
    while not any(isinstance(b, gd.FireLaser) for b in form.bullets) and elapsed < 4:
        form.update(dt, 640)
        elapsed += dt
    assert gd.SHOT_GAP + gd.CHARGE_SECONDS - 1e-8 <= elapsed <= gd.SHOT_GAP + gd.CHARGE_SECONDS + 3 * dt
    bolt = next(b for b in form.bullets if isinstance(b, gd.FireLaser))
    start = bolt.y
    for _ in range(fps):
        bolt.update(dt)
    assert bolt.y - start == pytest.approx(gd.LASER_SPEED)


def test_charge_stops_aiming_and_killing_the_shooter_cancels_it(display):
    form = gd.GuardianFormation()
    shooter = form.enemies[0]
    shooter.shot_wait = 0
    form.update(0.01, 640)
    assert shooter.charge > 0
    origin = shooter.x
    form.update(0.2, 50)
    assert shooter.x == origin
    while shooter.charge:
        form.update(1 / 120, 50)
    while shooter.laser_attached:
        form.update(1 / 120, 50)
    assert abs(shooter.x - origin) < 1  # no teleport when movement resumes
    form.bullets.clear()
    shooter.shot_wait = 0
    form.update(0.01, 640)
    shooter.kill()
    form.update(1.0, 50)
    assert not any(b.owner_id == shooter.owner_id for b in form.bullets)
    assert shooter.charge == 0


@pytest.mark.parametrize("fps", [30, 60, 120, 144])
def test_shooter_stays_fixed_until_its_own_laser_detaches(display, fps):
    form = gd.GuardianFormation()
    shooter = form.enemies[0]
    shooter.shot_wait = 0
    dt = 1 / fps
    while shooter.emission is None:
        form.update(dt, 640, 625)
    origin = shooter.x, shooter.y
    bolt = shooter.emission
    other = form.enemies[2]
    other_origin = other.x, other.y
    shooter.dive_wait = 0  # an overdue dive must also wait for detachment
    for _ in range(fps):
        was_attached = shooter.laser_attached
        form.update(dt, 1100, 625)
        if shooter.laser_attached:
            assert (shooter.x, shooter.y) == origin
            assert shooter.state == "patrol"
            assert bolt.x == shooter.x and bolt.origin_y == shooter.y + 16
        elif was_attached:
            break
    assert not shooter.laser_attached and bolt.alive  # still travelling on screen
    assert (other.x, other.y) != other_origin
    assert shooter.state == "windup"  # deferred dive starts immediately
    assert (shooter.x, shooter.y) != origin


def test_removed_laser_releases_the_shooter_without_waiting_for_a_timer(display):
    form = gd.GuardianFormation()
    shooter = form.enemies[0]
    shooter.emission = gd.FireLaser(shooter.x, shooter.y + 16, shooter.owner_id)
    form.bullets.append(shooter.emission)
    assert shooter.laser_attached
    shooter.start_dive(640, 625)
    assert shooter.state == "patrol"
    origin = shooter.x, shooter.y
    shooter.emission.alive = False
    form.update(1 / 120, 1100, 625)
    assert not shooter.laser_attached and (shooter.x, shooter.y) != origin


@pytest.mark.parametrize("fps", [30, 60, 120, 144])
def test_one_laser_per_guardian_with_overlapping_but_staggered_shots(display, fps):
    form = gd.GuardianFormation()
    max_active = 0
    fired_at = []
    for _ in range(30 * fps):
        previous = {id(b) for b in form.bullets if isinstance(b, gd.FireLaser)}
        form.update(1 / fps, 640)
        lasers = [b for b in form.bullets if isinstance(b, gd.FireLaser)]
        max_active = max(max_active, len(lasers))
        assert all(count <= 1 for count in Counter(b.owner_id for b in lasers).values())
        assert len(lasers) <= gd.PER_WAVE
        for b in lasers:
            if id(b) not in previous:
                fired_at.append(form.clock)
    assert 3 <= max_active <= 5
    assert len(fired_at) >= 9
    assert all(b - a >= gd.FIRE_STAGGER - 1e-8 for a, b in zip(fired_at, fired_at[1:]))
    # Even the starting Shield can clear the beam's lane during the warning alone.
    assert 480 * 0.4 * gd.CHARGE_SECONDS > gd.LASER_WIDTH + 48


def test_laser_hitbox_covers_the_swept_path_and_tail():
    bolt = gd.FireLaser(500, 200)
    bolt.update(0.5)
    assert bolt.get_hitbox().collidepoint(500, 450)
    bolt.update(1 / 6)
    box = bolt.get_hitbox()
    assert box.top <= 590 - gd.LASER_LENGTH and box.bottom >= 720
    assert not box.collidepoint(530, 600)


def test_wing_tips_have_transparent_margins_in_every_animation_cell(display):
    for row in gd.art()[0]:
        for frame in row:
            bounds = pygame.mask.from_surface(frame, 0).get_bounding_rects()
            combined = bounds[0].unionall(bounds[1:])
            assert combined.left >= 6 and combined.top >= 6
            assert combined.right <= 154 and combined.bottom <= 154


@pytest.mark.parametrize("fps", [30, 60, 120, 144])
def test_dive_locks_player_position_crosses_it_and_returns_from_above(display, fps):
    bird = gd.Guardian(320, 150, 0)
    target = (720, 560)
    bird.start_dive(*target)
    origin = (bird.x, bird.y)
    dt = 1 / fps
    for _ in range(int(gd.DIVE_WARNING * fps) - 1):
        bird.update(dt, 100, 660)
        assert (bird.x, bird.y) == origin
        assert not bird.diving
    passed_target = False
    seen_dive = False
    seen_wrap = False
    last = origin
    last_state = bird.state
    for _ in range(10 * fps):
        bird.update(dt, 100, 660)  # moving the player must not bend a locked dive
        assert bird.target == target
        distance = ((bird.x-last[0])**2 + (bird.y-last[1])**2)**0.5
        if last_state == "dive" and bird.state == "recover":
            assert last[1] + bird.vy * dt > gd.BASE_HEIGHT + 85
            assert bird.y == -85
            seen_wrap = True
        else:
            assert distance <= max(gd.DIVE_SPEED, gd.RETURN_SPEED) * dt + 1e-6
            if bird.state == "recover":
                assert bird.y >= last[1]  # re-enters downwards from the top
        if bird.diving:
            seen_dive = True
            # Swept contact with the original target, even at 30 FPS.
            swept = pygame.Rect(round(last[0]-24), round(last[1]-19), 48, 58).union(bird.get_hitbox())
            passed_target |= swept.collidepoint(*target)
        last = (bird.x, bird.y)
        last_state = bird.state
        if seen_dive and bird.state == "patrol":
            break
    assert seen_dive and passed_target and seen_wrap and bird.state == "patrol"


def test_dive_preparation_does_not_show_markers_or_trajectory(display):
    bird = gd.Guardian(320, 150, 0)
    plain = pygame.Surface((1280, 720))
    plain.fill((10, 20, 30))
    bird.draw(plain)
    bird.start_dive(700, 625)
    preparing = pygame.Surface((1280, 720))
    preparing.fill((10, 20, 30))
    bird.draw(preparing)
    assert pygame.image.tobytes(plain, "RGB") == pygame.image.tobytes(preparing, "RGB")


def test_patrol_pursues_the_player_and_can_schedule_a_dive(display):
    form = gd.GuardianFormation()
    bird = form.enemies[0]
    original_x = bird.x
    for _ in range(30):
        form.update(1 / 60, 1100, 600)
    assert bird.x > original_x
    bird.dive_wait = 0
    form.update(1 / 60, 1000, 610)
    assert bird.state == "windup" and bird.target == (1000, 610)


def test_encounter_waits_for_remaining_birds_deaths_and_projectiles(display):
    form = gd.GuardianFormation()
    for guardian in form.guardians:
        guardian.kill()
    form.update(0.1, 640)
    assert len(form.get_alive_enemies()) == 10
    assert not form.all_dead()
    for bird in form.birds:
        bird.kill()
    assert not form.all_dead()  # ordinary death animations still visible
    bolt = gd.FireLaser(640, 200)
    form.bullets = [bolt]
    form.update(0.5, 640)
    assert not form.all_dead()  # no enemies, but the laser remains
    form.update(4, 640)
    assert form.all_dead() and form.destroyed == 15



def test_drawing_reuses_loaded_art(display, monkeypatch):
    form = gd.GuardianFormation()
    canvas = pygame.Surface((1280, 720))
    form.draw(canvas)
    monkeypatch.setattr(pygame.image, "load", lambda *a: pytest.fail("Loaded sprites during draw"))
    form.enemies[0].shot_wait = 0
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
    bolt.update(1.7 / 3)
    game.formation.bullets = [bolt]
    lives = game.player.lives
    update_play.enemy_attacks_vs_players(game)
    assert game.player.lives == lives - 1 and bolt.alive and game.player.dying
    from ship_blast import DURATION
    game.player.update(DURATION + 0.01, {})
    assert game.player.alive and not game.player.dying
    game.formation.bullets.clear()  # manual ship-only animation step above
    game.player.invulnerable = 0
    diver = game.formation.enemies[0]
    diver.state = "dive"
    diver.x, diver.y = game.player.x, game.player.y
    lives = game.player.lives
    update_play.enemy_attacks_vs_players(game)
    assert game.player.lives == lives - 1 and not diver.alive
    game.dt = 1 / 60
    game.draw()
    game._bank_adventure(False)
    assert game.story.state == before
    # Finish the encounter and exercise the actual victory -> map transition.
    game._begin_adventure(spec)
    game.stage_transition = None
    for bird in game.formation.enemies:
        bird.kill(flash=False)
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
    game.player.lives = 1
    game.player.phenix_timer = 2.0
    assert game.player.burn_by_guardian()
    game.dt = 1 / 60
    game.update()
    assert game.started and game.player.dying  # final-life flames finish first
    game.player.update(DURATION + 0.01, {})
    game.update()
    assert not game.started and game.menu_screen == "story_hub"
    assert game.story.state == before
    game._setup_stage(3)
    assert isinstance(game.formation, EnemyFormation)
    game.running = False

def test_roster_has_five_guardians_and_five_birds_of_each_colour(display):
    form = gd.GuardianFormation()
    assert len(form.guardians) == 5
    assert Counter(b.stage for b in form.birds) == {1: 5, 2: 5}
    assert form.total == len(form.enemies) == 15
    assert form.waves == 1
    assert len({b.owner_id for b in form.enemies}) == 15
    assert all(b.frames is form.birds[0].frames for b in form.birds[:5])


@pytest.mark.parametrize("fps", [15, 30, 60, 120, 144])
def test_laser_burns_both_colours_once_and_keeps_travelling(display, fps):
    form = gd.GuardianFormation()
    targets = [form.birds[0], form.birds[5]]
    for enemy in form.enemies:
        if enemy not in targets:
            enemy.kill(flash=False)
    for bird, y in zip(targets, (260, 345)):
        bird.x = bird.start_x = 500
        bird.y = bird.start_y = y
        bird.attack_wait = bird.shot_wait = float("inf")
    bolt = gd.FireLaser(500, 170, 0)
    form.bullets = [bolt]
    for _ in range(fps):
        form.update(1 / fps, 640)
    assert form.burned == 2
    assert all(not bird.alive and not bird.dying for bird in targets)
    assert not form.get_hittable_enemies()
    assert len(form.effects) == 2
    assert not form.all_dead()  # ash still visible
    for _ in range(2 * fps):
        form.update(1 / fps, 640)
    assert form.burned == 2 and form.all_dead()


def test_ordinary_shots_do_not_burn_birds_or_guardians(display):
    from enemy import EnemyBullet
    form = gd.GuardianFormation()
    bird = form.birds[0]
    bolt = EnemyBullet(bird.x, bird.y - 10)
    bolt.update(0.05)
    form.bullets = [bolt]
    previous = {b: b.get_hitbox() for b in form.birds}
    form._burn_birds(previous)
    assert form.burned == 0 and bird.alive and not form.effects
    guardian = form.guardians[0]
    laser = gd.FireLaser(guardian.x, guardian.y - 60)
    laser.update(0.1)
    form.bullets = [laser]
    form._burn_birds(previous)
    assert guardian.alive


def test_dead_and_dying_birds_cannot_be_ignited(display):
    form = gd.GuardianFormation()
    bird = form.birds[0]
    bird.kill()
    laser = gd.FireLaser(bird.x, bird.y - 60)
    laser.update(0.1)
    form.bullets = [laser]
    form._burn_birds({})
    assert form.burned == 0 and not form.effects


def test_final_offscreen_laser_step_still_burns_a_bird(display):
    form = gd.GuardianFormation()
    bird = form.birds[0]
    bird.x = bird.start_x = 500
    bird.y = bird.start_y = 500
    bird.attack_wait = bird.shot_wait = float("inf")
    bolt = gd.FireLaser(500, 180, 0)
    form.bullets = [bolt]
    form.update(1.0, 640)
    assert not bolt.alive and not bird.alive and form.burned >= 1


def test_bird_wrapping_above_does_not_sweep_across_the_playfield(display):
    form = gd.GuardianFormation()
    bird = form.birds[0]
    bird.x = bird.start_x = 500
    bird.y = 775
    bird.state = "diving"
    bird.dive_lane = 500
    laser = gd.FireLaser(500, 200, 0)
    form.bullets = [laser]
    form.update(1 / 60, 640)
    assert bird.state == "returning" and bird.y == -40 and bird.alive


@pytest.mark.parametrize("stage", [1, 2])
def test_burning_frames_show_fire_then_ash_and_are_cached(display, stage, monkeypatch):
    form = gd.GuardianFormation()
    bird = next(b for b in form.birds if b.stage == stage)
    frames = gd.burning_frames(stage, bird.frames[0])
    assert len(frames) == gd.BURN_FRAME_COUNT
    assert frames is gd.burning_frames(stage, bird.frames[0])
    assert pygame.mask.from_surface(frames[0], 0).count() > 0
    assert pygame.mask.from_surface(frames[-1], 0).count() == 0
    fire = frames[5]
    assert any(c.r > 200 and c.g > 50 and c.b < 60 and c.a
               for y in range(fire.get_height()) for x in range(fire.get_width())
               for c in [fire.get_at((x, y))])
    ash = frames[19]
    assert any(c.a and abs(c.r - c.g) < 10 and abs(c.g - c.b) < 10
               for y in range(ash.get_height()) for x in range(ash.get_width())
               for c in [ash.get_at((x, y))])
    effect = gd.BurningBird(bird)
    canvas = pygame.Surface((1280, 720), pygame.SRCALPHA)
    monkeypatch.setattr(pygame.transform, "scale", lambda *a: pytest.fail("Scaled during burn draw"))
    monkeypatch.setattr(pygame.image, "load", lambda *a: pytest.fail("Loaded during burn draw"))
    for _ in range(100):
        effect.update(1 / 60)
        effect.draw(canvas)
    assert not effect.alive


def test_swept_bird_collision_requires_contact_at_the_same_time():
    laser = gd.FireLaser(500, 100)
    laser.update(0.5)  # tip moves from 100 to 490
    assert laser.hits_moving_rect(pygame.Rect(490, 300, 20, 20),
                                 pygame.Rect(490, 300, 20, 20))
    assert not laser.hits_moving_rect(pygame.Rect(520, 300, 20, 20),
                                     pygame.Rect(520, 300, 20, 20))
    # Bird crosses the lane early, well before the tip reaches its height.
    assert not laser.hits_moving_rect(pygame.Rect(490, 400, 20, 20),
                                     pygame.Rect(800, 400, 20, 20))
    # A growing tail never burns above its emission point.
    assert not laser.hits_moving_rect(pygame.Rect(490, 50, 20, 20),
                                     pygame.Rect(490, 50, 20, 20))


def test_escort_creation_does_not_change_arcade_random_state(display):
    import random
    before = random.getstate()
    gd.GuardianFormation()
    assert random.getstate() == before
