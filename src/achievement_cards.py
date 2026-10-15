"""
The card of an achievement: its picture (assets/achievements/<id>.png, made by tools/make_achievement_art.py) in a
square frame with slightly rounded corners. The metal of the frame tells the tier: steel when unlocked, then
bronze, silver, gold; a locked achievement is a grey card in a dull frame, a secret one not found yet a "?".

Cards are drawn once at 128 px and scaled to the size asked; every size is kept (a few dozen small images).
"""
import os

import pygame

import fonts
from errlog import log_exc
from settings import asset_path

BASE = 128
RADIUS = 14                      # corners, at 128 px
STATES = ("locked", "normal", "bronze", "silver", "gold", "hidden")

# (base, dark, light) of each frame
METAL = {
    "locked": ((70, 74, 90), (40, 42, 54), (100, 104, 120)),
    "hidden": ((70, 74, 90), (40, 42, 54), (100, 104, 120)),
    "normal": ((120, 140, 180), (60, 70, 100), (200, 215, 240)),
    "bronze": ((190, 115, 55), (100, 55, 25), (250, 190, 130)),
    "silver": ((190, 196, 210), (100, 104, 120), (250, 252, 255)),
    "gold": ((235, 185, 50), (130, 85, 15), (255, 245, 170)),
}

_CACHE = {}


def picture_path(aid):
    return asset_path("achievements", aid + ".png")


def _picture(aid):
    """The scene of an achievement at 128 px (a dark sky when its file is missing)."""
    key = ("pic", aid)
    img = _CACHE.get(key)
    if img is None:
        img = None
        path = picture_path(aid)
        if os.path.isfile(path):
            try:
                img = pygame.image.load(path)
                img = img.convert() if pygame.display.get_surface() is not None else img
                if img.get_size() != (BASE, BASE):
                    img = pygame.transform.smoothscale(img, (BASE, BASE))
            except Exception:
                log_exc("achievement_cards._picture")
                img = None
        if img is None:
            img = pygame.Surface((BASE, BASE))
            for y in range(BASE):
                f = y / (BASE - 1)
                pygame.draw.line(img, (int(14 * (1 - f) + 4 * f), int(20 * (1 - f) + 5 * f), int(52 * (1 - f) + 14 * f)),
                                 (0, y), (BASE, y))
        _CACHE[key] = img
    return img


def _grey(img):
    """The picture of a locked achievement: grey and darker."""
    out = pygame.transform.grayscale(img)
    out.fill((150, 150, 165), special_flags=pygame.BLEND_RGB_MULT)
    return out


def _question():
    img = pygame.Surface((BASE, BASE))
    for y in range(BASE):
        f = y / (BASE - 1)
        pygame.draw.line(img, (int(24 - 12 * f), int(26 - 12 * f), int(40 - 18 * f)), (0, y), (BASE, y))
    q = fonts.title(64).render("?", True, (110, 112, 140))
    img.blit(q, q.get_rect(center=(BASE // 2, BASE // 2 + 2)))
    return img


def _make(aid, state):
    if state == "hidden":
        scene = _question()
    else:
        scene = _picture(aid)
        if state == "locked":
            scene = _grey(scene)
    out = pygame.Surface((BASE, BASE), pygame.SRCALPHA)
    mask = pygame.Surface((BASE, BASE), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, BASE, BASE), border_radius=RADIUS)
    pic = scene.convert_alpha() if pygame.display.get_surface() is not None else scene.copy()
    if pic.get_flags() & pygame.SRCALPHA == 0:
        tmp = pygame.Surface((BASE, BASE), pygame.SRCALPHA)
        tmp.blit(pic, (0, 0))
        pic = tmp
    pic.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    out.blit(pic, (0, 0))
    base, dark, light = METAL.get(state, METAL["normal"])
    pygame.draw.rect(out, dark, (0, 0, BASE, BASE), 7, border_radius=RADIUS)
    pygame.draw.rect(out, base, (1, 1, BASE - 2, BASE - 2), 4, border_radius=RADIUS - 1)
    pygame.draw.line(out, light, (RADIUS, 2), (BASE - RADIUS, 2), 2)            # light on the top edge
    if state in ("bronze", "silver", "gold"):
        corner = [(BASE - 24, BASE - 5), (BASE - 5, BASE - 24), (BASE - 5, BASE - 5)]
        pygame.draw.polygon(out, base, corner)
        pygame.draw.polygon(out, light, [(BASE - 24, BASE - 5), (BASE - 5, BASE - 24), (BASE - 12, BASE - 12)])
    return out


def card(aid, state, size):
    """The card of `aid` in `state` (one of STATES), `size` px wide."""
    size = int(size)
    key = ("card", aid, state, size)
    img = _CACHE.get(key)
    if img is None:
        big = _CACHE.get(("card", aid, state, BASE))
        if big is None:
            big = _CACHE[("card", aid, state, BASE)] = _make(aid, state)
        img = big if size == BASE else pygame.transform.smoothscale(big, (size, size))
        if len(_CACHE) > 600:
            _CACHE.clear()
        _CACHE[key] = img
    return img


def has_picture(aid):
    return os.path.isfile(picture_path(aid))
