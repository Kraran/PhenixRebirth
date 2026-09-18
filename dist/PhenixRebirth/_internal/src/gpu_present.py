"""
GPU present via pygame.SCALED (SDL2 hardware scale).

pygame 2.6 Texture.from_surface crashes on this Windows SDL build
("Surface doesn't have a colorkey"). SCALED avoids that API.

Ultrawide + bezel: logical canvas matches the monitor aspect
(e.g. 1707x720 on 2560x1080). Game is 1:1 in the center, bezels sit
on the sides, SDL stretches the whole frame on the GPU.
16:9 / window: logical 1280x720, no bezel band.
"""
from __future__ import annotations

import pygame

from settings import BASE_WIDTH, BASE_HEIGHT


class GpuPresenter:
    def __init__(self):
        self.enabled = False
        self.available = hasattr(pygame, "SCALED")
        self.renderer = None
        self.tex = None
        self.last_error = ""
        self.size = (BASE_WIDTH, BASE_HEIGHT)

    def close(self):
        self.enabled = False

    def open_window(self, title, size, mode, pos):
        return None

    def bind(self, enabled=True):
        self.enabled = bool(enabled) and self.available
        return self.enabled

    @property
    def active(self):
        return bool(self.enabled)

    def set_title(self, title):
        try:
            pygame.display.set_caption(title)
        except Exception:
            pass

    def present(self, game_surface, dest_rect, left_surf=None, right_surf=None,
                bezel_key=None, shake=(0, 0)):
        # 16:9 SCALED surface is 1280x720 — 1:1 blit, SDL upscales. Bezels use the CPU blit path on a wider logical canvas.
        if not self.active:
            return False
        try:
            screen = pygame.display.get_surface()
            if screen is None:
                return False
            screen.blit(game_surface, (int(shake[0]), int(shake[1])))
            pygame.display.flip()
            return True
        except Exception as e:
            self.last_error = str(e)
            print("GPU present frame failed:", e)
            self.enabled = False
            return False


def scaled_flags(mode):
    """Flags for set_mode when GPU/SCALED is on."""
    flags = pygame.SCALED | pygame.DOUBLEBUF
    if mode == "fullscreen":
        flags |= pygame.FULLSCREEN
    elif mode == "borderless":
        flags |= pygame.NOFRAME
    return flags


