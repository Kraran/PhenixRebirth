"""The Guardians: deterministic warning and dodgeable laser bolts (on tests/guardian_rig.py: the squad of the Adventure)."""
from collections import Counter

import pygame
import pytest

import guardian as gd
from guardian_rig import Rig


@pytest.fixture
def display():
    pygame.display.init()
    pygame.display.set_mode((1280, 720))


@pytest.mark.parametrize("fps", [30, 60, 120, 144])
def test_charge_and_bolt_speed_do_not_depend_on_framerate(display, fps):
    form = Rig()
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
    form = Rig()
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
    form = Rig()
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
    form = Rig()
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
    form = Rig()
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
    form = Rig()
    bird = form.enemies[0]
    original_x = bird.x
    for _ in range(30):
        form.update(1 / 60, 1100, 600)
    assert bird.x > original_x
    bird.dive_wait = 0
    form.update(1 / 60, 1000, 610)
    assert bird.state == "windup" and bird.target == (1000, 610)


def test_drawing_reuses_loaded_art(display, monkeypatch):
    form = Rig()
    canvas = pygame.Surface((1280, 720))
    form.draw(canvas)
    monkeypatch.setattr(pygame.image, "load", lambda *a: pytest.fail("Loaded sprites during draw"))
    form.enemies[0].shot_wait = 0
    for _ in range(240):
        form.update(1 / 60, 640)
        form.draw(canvas)


@pytest.mark.parametrize("fps", [15, 30, 60, 120, 144])
def test_laser_burns_both_colours_once_and_keeps_travelling(display, fps):
    form = Rig(birds=(1, 2))
    targets = form.birds
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
    form = Rig(birds=(1,))
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
    form = Rig(birds=(1,))
    bird = form.birds[0]
    bird.kill()
    laser = gd.FireLaser(bird.x, bird.y - 60)
    laser.update(0.1)
    form.bullets = [laser]
    form._burn_birds({})
    assert form.burned == 0 and not form.effects


def test_final_offscreen_laser_step_still_burns_a_bird(display):
    form = Rig(birds=(1,))
    bird = form.birds[0]
    bird.x = bird.start_x = 500
    bird.y = bird.start_y = 500
    bird.attack_wait = bird.shot_wait = float("inf")
    bolt = gd.FireLaser(500, 180, 0)
    form.bullets = [bolt]
    form.update(1.0, 640)
    assert not bolt.alive and not bird.alive and form.burned >= 1


@pytest.mark.parametrize("stage", [1, 2])
def test_burning_frames_show_fire_then_ash_and_are_cached(display, stage, monkeypatch):
    form = Rig(birds=(1, 2))
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


def test_fire_bolt_is_ten_percent_longer_than_the_old_one():
    assert gd.LASER_LENGTH == 158  # 144 + 10 %


def test_fire_bolt_art_matches_its_length_and_has_distinct_animation_frames(display):
    frames = gd.art()[1]
    assert len(frames) == gd.LASER_FRAMES == 3
    assert all(f.get_height() == gd.LASER_LENGTH for f in frames)
    raw = [pygame.image.tostring(f, "RGBA") for f in frames]
    assert len(set(raw)) == 3
    for f in frames:  # the glowing head sits at the bottom, wider than the hitbox
        bounds = pygame.mask.from_surface(f, 8).get_bounding_rects()
        box = bounds[0].unionall(bounds[1:])
        assert box.bottom >= gd.LASER_LENGTH - 6 and box.width >= gd.LASER_WIDTH


def test_fire_bolt_draws_animated_frames_cropped_to_its_visible_length(display):
    def render(age, travelled):
        bolt = gd.FireLaser(100, 50)
        bolt.y = 50 + travelled
        bolt.age = age
        surface = pygame.Surface((200, 400), pygame.SRCALPHA)
        bolt.draw(surface)
        return surface, pygame.mask.from_surface(surface, 8).get_bounding_rects()

    a, _ = render(0.0, 100)
    b, _ = render(1.0 / gd.LASER_FPS, 100)
    assert pygame.image.tostring(a, "RGBA") != pygame.image.tostring(b, "RGBA")
    assert pygame.image.tostring(a, "RGBA") == pygame.image.tostring(
        render(gd.LASER_FRAMES / gd.LASER_FPS, 100)[0], "RGBA")  # the cycle loops
    _, short = render(0.0, 40)
    _, full = render(0.0, 300)
    top_short = min(r.top for r in short)
    assert top_short >= 50 and max(r.bottom for r in short) <= 90 + 1
    assert max(r.bottom for r in full) - min(r.top for r in full) >= gd.LASER_LENGTH - 8


def test_fire_bolt_age_advances_with_updates():
    bolt = gd.FireLaser(0, 0)
    bolt.update(0.25)
    bolt.update(0.25)
    assert bolt.age == pytest.approx(0.5)


def test_fire_bolt_shows_its_head_first_when_only_part_is_visible(display):
    frame = gd.art()[1][0]
    bolt = gd.FireLaser(100, 50)
    bolt.y = 50 + 40
    surface = pygame.Surface((200, 400), pygame.SRCALPHA)
    bolt.draw(surface)
    x0 = round(100 - frame.get_width() / 2)
    drawn = surface.subsurface((x0, 50, frame.get_width(), 40))
    head = frame.subsurface((0, gd.LASER_LENGTH - 40, frame.get_width(), 40))
    assert pygame.image.tostring(drawn, "RGBA") == pygame.image.tostring(head, "RGBA")
