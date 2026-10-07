"""Les bordures de l'écran ultra-large ne sont recalculées que si l'écran change."""
import random

import pygame

from game import Game


def _set_mode(size):
    """Le pilote factice ramène la 1re fenêtre à 1024x768 : on la redimensionne."""
    flags = pygame.DOUBLEBUF | pygame.HWSURFACE
    pygame.display.set_mode(size, flags)
    return pygame.display.set_mode(size, flags)


def _game(size, style="blue"):
    random.seed(1)
    g = Game()
    g._intro_done = True
    g.fade_phase = None
    g.display_mode = "fullscreen"
    g.bezel_style = style
    g._gpu_backend = ""
    g.screen = _set_mode(size)
    g._present_size = None
    g._scaled_game_buf = None
    g._load_bezel_images()
    g._invalidate_present_cache()
    g._layout_viewport()
    return g


def test_bordures_construites_une_seule_fois():
    g = _game((2560, 1080))
    assert g.bezel_active
    builds = {"n": 0}
    orig = g._ensure_bezel_cache

    def counted():
        before = g._bezel_cache_key
        orig()
        if g._bezel_cache_key != before:
            builds["n"] += 1

    g._ensure_bezel_cache = counted
    for _ in range(20):
        g.draw()
    assert builds["n"] == 1


def test_changement_de_taille_reconstruit():
    g = _game((2560, 1080))
    g.draw()
    key = g._bezel_cache_key
    g.screen = _set_mode((3440, 1440))
    g.draw()
    assert g._bezel_cache_key != key
    assert g._present_size == (3440, 1440)
