"""Performance paths preserve every pixel and retain bounded caches."""
from types import SimpleNamespace

import pygame
import pytest

import announce
from game import Game


@pytest.fixture
def display(monkeypatch):
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    monkeypatch.setattr(pygame.display, "flip", lambda: None)


@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (2560, 1440)])
@pytest.mark.parametrize("shake", [(0, 0), (3, -2)])
@pytest.mark.parametrize("alpha", [False, True])
def test_cpu_present_matches_clear_then_scale(display, size, shake, alpha):
    game = Game.__new__(Game)
    game.screen = pygame.Surface(size)
    game.game_surface = pygame.Surface((1280, 720), pygame.SRCALPHA if alpha else 0)
    game.game_surface.fill((35, 90, 170, 140) if alpha else (35, 90, 170))
    pygame.draw.rect(game.game_surface, (220, 40, 70), (100, 80, 120, 240))
    game.screen.fill((255, 0, 255))
    game.display_mode = "fullscreen"
    game._gpu = SimpleNamespace(active=False)
    game._gpu_backend = ""
    game.bezel_active = False
    game.view_rect = pygame.Rect((0, 0), size)
    game._present_size = size
    game._scaled_game_buf = None
    expected = pygame.Surface(size)
    expected.fill((0, 0, 0))
    if size == (1280, 720):
        expected.blit(game.game_surface, shake)
    else:
        scaled = pygame.Surface(size, 0, game.screen)
        pygame.transform.scale(game.game_surface, size, scaled)
        expected.blit(scaled, shake)
    assert not game._direct_draw_ok()
    assert game._present_overwrites_screen(*shake) == (not alpha and shake == (0, 0))
    game._flip_frame(*shake)
    assert pygame.image.tobytes(game.screen, "RGB") == pygame.image.tobytes(expected, "RGB")


def test_letterbox_still_requires_black_borders(display):
    game = Game.__new__(Game)
    game.screen = pygame.Surface((1920, 1200))
    game.game_surface = pygame.Surface((1280, 720))
    game._present_size = game.screen.get_size()
    game.view_rect = pygame.Rect(0, 60, 1920, 1080)
    game._gpu = SimpleNamespace(active=False)
    game._gpu_backend = ""
    game.bezel_active = False
    game.display_mode = "fullscreen"
    assert not game._present_overwrites_screen(0, 0)


def test_announcement_opacity_is_cached_without_mutating_the_source():
    source = pygame.Surface((120, 40), pygame.SRCALPHA)
    source.fill((70, 100, 200, 190))
    original = pygame.image.tobytes(source, "RGBA"), source.get_alpha()
    one = announce._with_alpha(source, 235)
    two = announce._with_alpha(source, 235)
    assert one is two and one is not source
    assert one.get_alpha() == 235
    assert (pygame.image.tobytes(source, "RGBA"), source.get_alpha()) == original
    assert announce._with_alpha(source, 120) is not one


def test_announcement_cache_stays_within_its_memory_limit():
    for i in range(150):
        source = pygame.Surface((256, 64), pygame.SRCALPHA)
        source.fill((i % 255, 70, 110, 220))
        announce._with_alpha(source, 235)
    assert len(announce._alpha_images) <= announce._ALPHA_MAX_ITEMS
    assert announce._alpha_bytes <= announce._ALPHA_MAX_BYTES
    assert announce._alpha_bytes == sum(s.get_pitch() * s.get_height()
                                       for s in announce._alpha_images.values())
