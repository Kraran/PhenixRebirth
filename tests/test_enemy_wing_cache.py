"""Pixel regressions against the uncached renderer, on the same SDL build."""
import copy
import math

import pygame
import pytest

from enemy import BigBird, _whiten_surf


@pytest.fixture
def bird_factory(monkeypatch):
    pygame.display.init()
    pygame.display.set_mode((320, 240))

    def make(stage, fallback=False):
        if fallback:
            monkeypatch.setattr(BigBird, "_load_garg_sprites", lambda self, stage: False)
        return BigBird(160, 120, stage=stage)

    return make


# Previous renderer kept as a reference: compare pixels without platform-specific goldens.
def _reference_draw(self, surface):
    if not self.alive:
        return

    wing_up = math.sin(self.flap) > 0
    wing_src = self.wing_up if wing_up else self.wing_down
    flap_y = -5 if wing_up else 5
    bw = self.body_img.get_width()
    bh = self.body_img.get_height()
    ww = wing_src.get_width()
    wh = wing_src.get_height()
    bx = int(self.x - bw // 2)
    by = int(self.y - bh // 2)
    # Attach wings just outside the body so destroying a wing
    # never looks like carving the torso
    wing_y = int(self.y - wh // 2 + flap_y)
    left_x = int(self.x - bw // 2 - ww + 6)
    right_x = int(self.x + bw // 2 - 6)

    if self.dying:
        if int(getattr(self, "hit_flash_frames", 0) or 0) > 0:
            body_w = getattr(self, "_white_body", None)
            if body_w is None:
                self._white_body = body_w = _whiten_surf(self.body_img)
            wing_w = getattr(self, "_white_wing", None)
            if wing_w is None:
                self._white_wing = wing_w = _whiten_surf(wing_src)
            if self.wing_left:
                surface.blit(wing_w, (left_x, wing_y))
            if self.wing_right:
                surface.blit(pygame.transform.flip(wing_w, True, False), (right_x, wing_y))
            surface.blit(body_w, (bx, by))
            return
        for w in self.detach_wings:
            if not w.get("alive"):
                continue
            img = w["img"]
            rot = w.get("rot", 0.0)
            if abs(rot) > 0.4:
                img = pygame.transform.rotate(img, rot)
            surface.blit(img, (int(w["x"] - img.get_width() / 2),
                               int(w["y"] - img.get_height() / 2)))
        return

    # Wings behind body
    if self.wing_left:
        surface.blit(wing_src, (left_x, wing_y))
    if self.wing_right:
        surface.blit(pygame.transform.flip(wing_src, True, False), (right_x, wing_y))

    surface.blit(self.body_img, (bx, by))

    # Tiny shoulder stubs when a wing is missing (reads as torn, not floating tips)
    if not self.wing_left or not self.wing_right:
        stub = getattr(self, "_wing_stub", None)
        if stub is None:
            stub = pygame.Surface((10, 12), pygame.SRCALPHA)
            pygame.draw.ellipse(stub, (90, 95, 105, 220), (0, 2, 9, 9))
            pygame.draw.polygon(stub, (130, 135, 145, 230), [(2, 4), (9, 1), (8, 10)])
            self._wing_stub = stub
        sy = int(self.y - 4)
        if not self.wing_left:
            surface.blit(stub, (int(self.x - bw // 2 - 4), sy))
        if not self.wing_right:
            surface.blit(pygame.transform.flip(stub, True, False),
                         (int(self.x + bw // 2 - 6), sy))

@pytest.mark.parametrize("stage", [3, 4])
@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("flap", [-1.0, 1.0])
@pytest.mark.parametrize("wings", [(True, True), (True, False), (False, True), (False, False)])
@pytest.mark.parametrize("state", ["flying", "flash", "detached", "rotated"])
def test_pixels_match_previous_renderer(bird_factory, stage, fallback, flap, wings, state):
    bird = bird_factory(stage, fallback)
    bird.flap = flap
    bird.wing_left, bird.wing_right = wings
    if state != "flying":
        bird.kill()
        bird.hit_flash_frames = int(state == "flash")
        for wing in bird.detach_wings:
            wing["rot"] = 23.0 if state == "rotated" else 0.0
    before = copy.copy(bird)
    actual = pygame.Surface((320, 240))
    actual.fill((17, 31, 53))
    expected = actual.copy()
    sources = [bird.wing_up, bird.wing_down, bird.wing_up_right, bird.wing_down_right]
    pixels = [pygame.image.tobytes(img, "RGBA") for img in sources]
    bird.draw(actual)
    _reference_draw(before, expected)
    assert pygame.image.tobytes(actual, "RGB") == pygame.image.tobytes(expected, "RGB")
    assert [pygame.image.tobytes(img, "RGBA") for img in sources] == pixels


@pytest.mark.parametrize("stage", [3, 4])
def test_warmed_draw_and_detachment_do_not_flip_again(bird_factory, monkeypatch, stage):
    bird = bird_factory(stage)
    canvas = pygame.Surface((320, 240))
    bird.wing_right = False
    bird.draw(canvas)  # the first missing wing prepares its pair of stubs
    bird.wing_right = True
    bird.kill()
    bird.draw(canvas)  # the first flash prepares its white wing pair

    def unexpected_flip(*args, **kwargs):
        pytest.fail("A cached sprite was flipped again")

    monkeypatch.setattr(pygame.transform, "flip", unexpected_flip)
    for flap in (-1.0, 1.0):
        bird.flap = flap
        for left, right in ((True, True), (False, True), (True, False), (False, False)):
            bird.wing_left, bird.wing_right = left, right
            bird.dying = False
            bird.draw(canvas)
            bird.dying = True
            bird.hit_flash_frames = 1
            bird.draw(canvas)
        bird.wing_left = bird.wing_right = True
        bird.detach_wings = []
        bird._spawn_detach_wings()
        right = bird.detach_wings[1]["img"]
        assert right is (bird.wing_up_right if math.sin(flap) > 0 else bird.wing_down_right)
        bird.hit_flash_frames = 0
        for wing in bird.detach_wings:
            wing["rot"] = 25
        bird.draw(canvas)


def test_regrown_wings_keep_the_same_pixels(bird_factory):
    bird = bird_factory(3)
    assert bird.hit_wing("left") and bird.hit_wing("right")
    bird.update(bird.WING_REGEN + 0.1)
    assert bird.wing_left and bird.wing_right
    actual = pygame.Surface((320, 240))
    actual.fill((17, 31, 53))
    expected = actual.copy()
    bird.draw(actual)
    _reference_draw(copy.copy(bird), expected)
    assert pygame.image.tobytes(actual, "RGB") == pygame.image.tobytes(expected, "RGB")

