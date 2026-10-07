"""Chemin SCALED : le remplissage noir de l'écran n'est évité que s'il est inutile."""
import random

import pygame

from game import Game

FLAGS = pygame.DOUBLEBUF | pygame.HWSURFACE


def _scaled_game():
    random.seed(3)
    g = Game()
    g._intro_done = True
    g.fade_phase = None
    size = g.game_surface.get_size()
    pygame.display.set_mode(size, FLAGS)  # le pilote factice ramène la 1re fenêtre à 1024x768
    g.screen = pygame.display.set_mode(size, FLAGS)
    g.display_mode = "fullscreen"
    g._gpu.bind(True)
    g._gpu_backend = "scaled"
    g._present_size = None
    g._invalidate_present_cache()
    g._layout_viewport()
    g._present_size = g.screen.get_size()
    return g


def test_conditions():
    g = _scaled_game()
    assert g._present_overwrites_screen(0, 0) is True
    assert g._present_overwrites_screen(2, 0) is False          # secousse : bords noirs nécessaires
    assert g._present_overwrites_screen(0, -1) is False
    g.bezel_active = True
    assert g._present_overwrites_screen(0, 0) is False          # bordures : chemin CPU
    g.bezel_active = False
    g._gpu_backend = ""
    assert g._present_overwrites_screen(0, 0) is False          # pas SCALED
    g._gpu_backend = "scaled"
    g._present_size = None
    assert g._present_overwrites_screen(0, 0) is False          # mise en page pas à jour
    g._present_size = g.screen.get_size()
    g.game_surface = pygame.Surface((g.screen.get_width() - 1, g.screen.get_height()))
    assert g._present_overwrites_screen(0, 0) is False          # tailles différentes
    g.game_surface = pygame.Surface(g.screen.get_size(), pygame.SRCALPHA)
    assert g._present_overwrites_screen(0, 0) is False          # canevas avec alpha


def test_ecran_entierement_recouvert():
    g = _scaled_game()
    g.screen.fill((255, 0, 0))  # reste d'une image précédente
    g.draw()
    w, h = g.screen.get_size()
    reds = sum(1 for x in range(0, w, 7) for y in range(0, h, 7) if g.screen.get_at((x, y))[:3] == (255, 0, 0))
    assert reds == 0


def test_secousse_garde_des_bords_noirs():
    g = _scaled_game()
    g.screen.fill((255, 0, 0))
    g.started = True
    g.shake_amount = 6
    random.seed(11)
    g.draw()
    w, h = g.screen.get_size()
    corners = [g.screen.get_at(p)[:3] for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    assert (255, 0, 0) not in corners  # aucun reste rouge : le noir a bien été posé
