"""Guardians: 3 HP with a life bar, wings that are shot off and regrow (the gargoyles' 3.2 s), visible wounds."""
import random

import pygame
import pytest

import guardian as gd
from guardian_rig import Rig
import guardian_parts as gp


@pytest.fixture
def display():
    pygame.display.init()
    pygame.display.set_mode((1280, 720))


def bird():
    return gd.Guardian(400, 200, 0)


def test_three_hit_points_and_the_last_one_kills(display):
    b = bird()
    assert b.hp == 3 and b.max_hp == 3 and b.level == 0
    assert not b.hit() and b.hp == 2 and b.alive and b.level == 1
    assert not b.hit() and b.hp == 1 and b.alive and b.level == 2
    assert b.hit() and b.hp == 0 and not b.alive
    assert not b.hit()                       # a dead bird takes no more damage


def test_kill_is_still_instant_for_rams_and_antimatter(display):
    b = bird()
    b.kill()
    assert not b.alive and b.hp == 0


def test_a_hit_flashes_and_blinks_the_lost_segment_then_calms_down(display):
    b = bird()
    b.hit()
    assert b.hurt > 0 and b.bar_flash > 0 and abs(b.kick_y) > 1
    for _ in range(40):
        b.update(1 / 60, 400)
    assert b.hurt == 0 and b.bar_flash == 0 and abs(b.kick_y) < 0.1


def test_wing_boxes_beside_the_body_and_empty_when_gone(display):
    b = bird()
    left, right, body = b.get_left_wing_hitbox(), b.get_right_wing_hitbox(), b.get_hitbox()
    assert left.right <= body.left + 6 and right.left >= body.right - 6
    assert left.width > 40 and right.width > 40
    assert b.hit_wing("left")
    assert b.get_left_wing_hitbox().size == (0, 0) and b.get_right_wing_hitbox().size != (0, 0)
    assert not b.hit_wing("left")            # already gone
    assert b.hp == 3                         # a wing never costs health


def test_wing_regrows_after_the_gargoyle_delay_with_an_animation(display):
    b = bird()
    b.hit_wing("right")
    assert b.WING_REGEN == 3.2
    assert b.wing_grow("right") == 0.0 and b.wing_grow("left") == 1.0
    for _ in range(int(2.3 * 60)):
        b.update(1 / 60, 400)
    assert not b.wing_right and b.wing_grow("right") == 0.0     # still a stump
    for _ in range(int(0.5 * 60)):
        b.update(1 / 60, 400)
    assert not b.wing_right and 0.0 < b.wing_grow("right") < 1.0  # unfolding
    for _ in range(60):
        b.update(1 / 60, 400)
    assert b.wing_right and b.wing_grow("right") == 1.0


@pytest.mark.parametrize("fps", [30, 60, 144])
def test_regrowth_time_does_not_depend_on_the_frame_rate(display, fps):
    b = bird()
    b.hit_wing("left")
    t = 0.0
    while not b.wing_left:
        b.update(1 / fps, 400)
        t += 1 / fps
    assert 3.2 <= t <= 3.2 + 1 / fps + 1e-9


def test_no_wing_no_shot_and_no_dive_like_the_gargoyles(display):
    b = bird()
    assert b.can_shoot() and b.has_both_wings
    b.hit_wing("left")
    assert b.can_shoot() and not b.has_both_wings
    b.start_dive(400, 600)
    assert b.state == "patrol"               # a dive needs both wings
    b.hit_wing("right")
    assert not b.can_shoot()


def test_formation_cancels_a_charge_when_the_last_wing_goes(display):
    form = Rig()
    b = form.guardians[0]
    b.charge = 0.3
    b.hit_wing("left")
    b.hit_wing("right")
    form.update(1 / 60, 640)
    assert b.charge == 0.0
    b.shot_wait = 0
    for _ in range(120):
        form.update(1 / 60, 640)
        b.shot_wait = 0
        assert b.charge == 0.0               # and it never starts another one


def test_wingless_bird_does_not_block_the_others_dives(display):
    form = Rig()
    b = form.guardians[0]
    b.hit_wing("left")
    b.dive_wait = 0
    form.update(1 / 60, 640)
    assert b.state == "patrol"
    assert not any(g.dive_wait == 0 and g.state == "patrol" and g is not b and g.has_both_wings
                   and not any(o.state in ("windup", "dive") for o in form.guardians) for g in form.guardians[1:])


def test_pieces_make_the_original_cell_exactly(display):
    parts = gd.parts()
    for row in range(2):
        for frame in range(4):
            sheet = gd.art()[0][row][frame]
            rebuilt = pygame.Surface((160, 160), pygame.SRCALPHA)
            for side in gp.SIDES:
                p = parts.wing[row][frame][side][0]
                rebuilt.blit(p.surf, (p.ox, p.oy))
            p = parts.body[row][frame][0]
            rebuilt.blit(p.surf, (p.ox, p.oy))
            diff = sum(1 for x in range(160) for y in range(160)
                       if tuple(rebuilt.get_at((x, y))) != tuple(sheet.get_at((x, y))))
            assert diff == 0


def test_wounds_change_the_picture_at_two_and_at_one_hp(display):
    parts = gd.parts()
    def raw(level):
        s = pygame.Surface((160, 160), pygame.SRCALPHA)
        for side in gp.SIDES:
            p = parts.wing[0][1][side][level]
            s.blit(p.surf, (p.ox, p.oy))
        p = parts.body[0][1][level]
        s.blit(p.surf, (p.ox, p.oy))
        return pygame.image.tostring(s, "RGBA")
    a, b, c = raw(0), raw(1), raw(2)
    assert a != b and b != c and a != c
    def glow(img):                         # orange crack pixels
        return sum(1 for i in range(0, len(img), 4) if img[i] > 240 and 90 < img[i + 1] < 200 and img[i + 2] < 60 and img[i + 3] > 200)
    assert glow(a) < glow(b) < glow(c)


def test_wounded_birds_smoke_and_a_nearly_dead_one_burns(display):
    b = bird()
    for _ in range(120):
        b.update(1 / 60, 400)
    assert not b.fx
    b.hit()
    b.fx.clear()
    for _ in range(180):
        b.update(1 / 60, 400)
    smoke2 = sum(1 for p in b.fx if p[6] == "smoke")
    assert smoke2 >= 1
    b.hit()
    b.fx.clear()
    kinds = set()
    for _ in range(120):
        b.update(1 / 60, 400)
        kinds |= {p[6] for p in b.fx}
    assert {"smoke", "flame", "ember", "spark"} <= kinds
    assert len(b.fx) <= gd.FX_LIMIT


def test_effects_never_touch_the_arcade_random_state(display):
    random.seed(5)
    before = random.getstate()
    b = bird()
    b.hit(); b.hit_wing("left"); b.hit_wing("right")
    for _ in range(300):
        b.update(1 / 60, 400)
    b.canvas = pygame.Surface((1280, 720))
    b.draw(b.canvas)
    b.kill()
    assert random.getstate() == before


def test_death_sheds_the_wings_and_the_encounter_waits_for_the_fall(display):
    form = Rig(birds=(1, 2))
    for g in form.guardians:
        g.kill()
    for e in form.birds:
        e.kill(flash=False)
    assert all(len(g.fragments) == 2 for g in form.guardians)
    assert not form.all_dead()
    form.update(0.2, 640)
    assert not form.all_dead()
    form.update(3, 640)
    assert form.all_dead()


def test_silent_kill_leaves_no_effects(display):
    b = bird()
    b.kill(flash=False)
    assert not b.fx and not b.fragments


def test_drawing_every_state_works_and_loads_nothing(display, monkeypatch):
    canvas = pygame.Surface((1280, 720))
    b = bird()
    monkeypatch.setattr(pygame.image, "load", lambda *a: pytest.fail("Loaded sprites during draw"))
    for step in range(900):
        if step == 30:
            b.hit_wing("left")
        if step == 120:
            b.hit()
        if step == 200:
            b.hit_wing("right")
        if step == 300:
            b.hit()
        if step == 600:
            b.charge = 0.4
        b.update(1 / 60, 400)
        b.draw(canvas)
    b.kill()
    for _ in range(90):
        b.tick_fx(1 / 60)
        b.draw(canvas)


def test_bar_is_drawn_above_a_living_bird_with_one_segment_per_hp(display):
    canvas = pygame.Surface((300, 300))
    b = gd.Guardian(150, 150, 0)
    seen = []
    for hp in (3, 2, 1):
        b.hp = hp
        canvas.fill((0, 0, 0))
        b._draw_bar(canvas, 150, 150)
        seen.append(sum(1 for seg in range(3) if canvas.get_at((150 - 22 + 2 + seg * 14 + 6, 150 - 58 + 4))[:3] != (40, 24, 24)))
    assert seen == [3, 2, 1]


def test_bullets_in_game_wing_first_then_three_body_hits(display):
    import update_play

    class Ship:
        def __init__(self): self.shots = []; self.log = []
        def destroy_bullet(self, result=None, index=None): self.log.append(result)

    class Game:
        def __init__(self, form):
            self.formation = form; self.explosions = []; self.shake_amount = 0; self.sounds = type("S", (), {"play": lambda *a, **k: None})()
            self.kills = 0; self.stops = 0
        def _boom(self, *a, **k): return object()
        def _hitstop(self, *a): self.stops += 1
        def _add_score(self, *a): self.kills += 1
        def _enemy_kill_points(self, e): return 1
        def _note_bird_kill(self): pass
        def _note_scalable(self, *a, **k): pass
    form = Rig()
    g = form.guardians[2]
    game, ship = Game(form), Ship()
    left = g.get_left_wing_hitbox()
    assert update_play._shot_at_guardian(game, ship, 0, pygame.Rect(left.centerx, left.centery, 6, 12), g)
    assert not g.wing_left and g.hp == 3 and ship.log[-1] == "neutral"
    assert not update_play._shot_at_guardian(game, ship, 0, pygame.Rect(left.centerx, left.centery, 6, 12), g)
    body = g.get_hitbox()
    for hp in (2, 1):
        assert update_play._shot_at_guardian(game, ship, 0, pygame.Rect(body.centerx, body.centery, 6, 12), g)
        assert g.hp == hp and g.alive and game.kills == 0
    assert update_play._shot_at_guardian(game, ship, 0, pygame.Rect(body.centerx, body.centery, 6, 12), g)
    assert not g.alive and game.kills == 1 and ship.log[-1] == "valid"


def test_at_one_hp_the_eyes_are_no_longer_the_healthy_yellow(display):
    parts = gd.parts()
    def yellow(level):
        p = parts.body[0][1][level]
        return sum(1 for x in range(p.surf.get_width()) for y in range(p.surf.get_height())
                   if (c := p.surf.get_at((x, y))).a > 120 and 150 < c.r < 235 and c.g > 170 and c.b < 110)
    assert yellow(0) >= 4 and yellow(1) >= 4 and yellow(2) == 0
