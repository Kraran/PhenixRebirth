"""A Guardian's laser (or a half of it split on the reflective coating) burns a gargoyle like a bird: it catches fire,
chars and falls to ash (guardian.BurningBird), with the wings it still has. The ash of the gargoyles is made behind the
loading bar of the missions whose Guardians can meet them."""
import random

import pygame
import pytest

import guardian as gd
from enemy import BigBird


@pytest.fixture(autouse=True)
def _screen():
    pygame.display.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 64))


class _Owner:
    def __init__(self):
        self.effects = []
        self.sounds = None


@pytest.mark.parametrize("stage", [3, 4])
def test_a_burned_gargoyle_falls_to_ash(stage):
    random.seed(1)
    bird = BigBird(400, 300, 0, stage)
    owner = _Owner()
    gd.burn_bird(owner, bird)
    assert not bird.alive and not bird.dying                            # (gone at once, no wings flying away)
    assert len(owner.effects) == 1 and isinstance(owner.effects[0], gd.BurningBird)
    fx = owner.effects[0]
    assert (fx.x, fx.y) == (400, 300) and len(fx.frames) == gd.BURN_FRAME_COUNT
    surf = pygame.Surface((800, 600), pygame.SRCALPHA)
    drawn = []
    for t in (0.0, gd.BURN_SECONDS * 0.5, gd.BURN_SECONDS * 0.95):
        fx.age = t
        surf.fill((0, 0, 0, 0))
        fx.draw(surf)
        drawn.append(pygame.mask.from_surface(surf).count())
    assert drawn[0] > 0 and drawn[1] > 0                                # (fire, then ash, on the screen)
    fx.age = gd.BURN_SECONDS
    assert not fx.alive


def test_the_wings_it_lost_do_not_burn():
    random.seed(2)
    whole = BigBird(0, 0, 0, 3)
    torn = BigBird(0, 0, 0, 3)
    torn.wing_left = False
    full = pygame.mask.from_surface(gd.gargoyle_picture(whole)).count()
    half = pygame.mask.from_surface(gd.gargoyle_picture(torn, False, True)).count()
    assert half < full
    assert gd.gargoyle_burning_frames(torn) is not gd.gargoyle_burning_frames(whole)
    assert gd.gargoyle_burning_frames(BigBird(0, 0, 0, 3)) is gd.gargoyle_burning_frames(whole)   # (made once)


def test_the_picture_leaves_the_gargoyle_as_it_was():
    random.seed(3)
    bird = BigBird(123, 456, 0, 4)
    bird.wing_right = False
    before = (bird.x, bird.y, bird.flap, bird.wing_left, bird.wing_right, bird.dying)
    gd.gargoyle_picture(bird, True, True)
    assert (bird.x, bird.y, bird.flap, bird.wing_left, bird.wing_right, bird.dying) == before


def test_the_ash_is_made_beforehand_without_touching_the_draws(monkeypatch):
    gd._BURN_ART.pop(("garg", 3, True, True), None)
    gd._BURN_ART.pop(("garg", 4, True, True), None)
    random.seed(7)
    expected = random.random()
    random.seed(7)
    gd.warm_gargoyle_ash()
    assert random.random() == expected
    assert ("garg", 3, True, True) in gd._BURN_ART and ("garg", 4, True, True) in gd._BURN_ART


@pytest.mark.parametrize("spec, yes", [({"endless_guardians": True}, True), ({"guardians_each": 2}, True),
                                       ({"guardians_at": {23: 2}}, True), ({"guardians_at": {22: 1}}, False),
                                       ({"guardians_at": {21: 2}}, False), ({}, False)])
def test_which_missions_make_the_ash_behind_the_loading_bar(spec, yes):
    from game import Game
    assert Game.guardians_meet_gargoyles(spec) is yes


def test_a_squad_laser_burns_a_gargoyle_of_the_wave():
    random.seed(4)
    bird = BigBird(640, 300, 0, 3)
    bird.state = "roam"
    sq = gd.GuardianSquad(0)
    bolt = gd.FireLaser(640, 200)
    bolt.y = 420
    sq.bullets = [bolt]
    before = {bird: bird.get_hitbox()}
    assert gd.burn_birds(sq, [bird], before) == 1
    assert not bird.alive and isinstance(sq.effects[0], gd.BurningBird)
