"""Dessin direct sur l'écran (chemin SCALED) : mêmes pixels, canevas toujours restauré."""
import random

import pygame
import pytest

from game import Game

FLAGS = pygame.DOUBLEBUF | pygame.HWSURFACE


def _scaled_game(seed=3):
    random.seed(seed)
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
    return g


def _screen(g):
    return pygame.image.tobytes(g.screen, "RGB")


def _frames(direct, n=25):
    g = _scaled_game()
    if not direct:
        g._direct_draw_ok = lambda: False
    used = []
    orig = g._draw_canvas

    def spy():
        used.append(g.game_surface is g.screen)
        return orig()

    g._draw_canvas = spy
    out = []
    for _ in range(n):
        g.draw()
        out.append(_screen(g))
    return out, used


def test_memes_pixels_que_la_copie():
    # un seul affichage par processus : les deux parties se jouent l'une après l'autre
    direct, used_d = _frames(True)
    copie, used_c = _frames(False)
    # 1re image : la mise en page n'est pas encore faite, on passe par la copie (prudence)
    assert used_d[0] is False and all(used_d[1:]), "le dessin direct n'a pas été utilisé"
    assert not any(used_c)
    for i, (x, y) in enumerate(zip(direct, copie)):
        assert x == y, "image %d différente" % i


def test_canevas_restaure_et_secousse_sans_direct():
    g = _scaled_game()
    canvas = g.game_surface
    seen = []
    orig = g._draw_canvas

    def spy():
        seen.append(g.game_surface is g.screen)
        return orig()

    g._draw_canvas = spy
    g.draw()
    g.draw()
    assert g.game_surface is canvas and g._direct_restore is None
    g.started = True
    g.shake_amount = 5
    g.draw()
    assert seen == [False, True, False]  # secousse : on passe par le canevas et la copie décalée
    assert g.game_surface is canvas


def test_canevas_restaure_meme_si_le_dessin_plante():
    g = _scaled_game()
    canvas = g.game_surface
    g.draw()  # 1re image : mise en page

    def boom():
        raise RuntimeError("boom")

    g._draw_canvas = boom
    with pytest.raises(RuntimeError):
        g.draw()
    assert g._direct_draw_ok()  # c'était bien un dessin direct qui a planté
    assert g.game_surface is canvas and g._direct_restore is None


def test_lignes_de_balayage_pas_reconstruites():
    g = _scaled_game()
    g.scanlines = 2
    g.draw()
    overlay = g._scanline_surf
    assert overlay is not None
    g.draw()
    g.started = True
    g.shake_amount = 5
    g.draw()           # image avec secousse (chemin canevas)
    g.shake_amount = 0
    g.draw()           # retour au dessin direct
    assert g._scanline_surf is overlay


def test_echec_du_flip_direct_recopie_ecran(monkeypatch):
    g = _scaled_game()
    g.draw()
    monkeypatch.setattr(g._gpu, "present_direct", lambda: False)
    g.game_surface.fill((1, 2, 3))   # canevas périmé
    g.screen.fill((200, 100, 50))
    g._flip_frame(0, 0, True)
    assert g.game_surface.get_at((5, 5))[:3] == (200, 100, 50)
