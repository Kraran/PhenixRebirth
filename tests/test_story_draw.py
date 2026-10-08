"""Adventure screens: text must sit in the middle of its box."""
import pygame

import story


def _ink(surf):
    """Bounding boxes of the white text drawn on the black surface."""
    mask = pygame.mask.from_threshold(surf, (255, 255, 255), (100, 100, 100, 255))
    return mask.get_bounding_rects()


def _font(size=28):
    pygame.font.init()
    return pygame.font.SysFont("dejavusans,arial,sans", size, bold=True)


def test_capitals_are_centred_on_the_requested_line():
    for size in (22, 28, 32):
        font = _font(size)
        surf = pygame.Surface((300, 120))
        for cy in (30, 60):
            surf.fill((0, 0, 0))
            story._text(surf, font, "HEH", (255, 255, 255), cy, left=10)
            ink = _ink(surf)
            top = min(r.top for r in ink)
            bottom = max(r.bottom for r in ink)
            assert abs((top + bottom) / 2.0 - cy) <= 1.5, (size, cy, top, bottom)


def test_text_anchors():
    font = _font()
    surf = pygame.Surface((400, 100))
    img = story._text(surf, font, "ABC", (255, 255, 255), 50, right=380)
    w = img.get_width()
    ink = _ink(surf)
    assert max(r.right for r in ink) <= 380 and min(r.left for r in ink) >= 380 - w - 1
    surf.fill((0, 0, 0))
    story._text(surf, font, "ABC", (255, 255, 255), 50, centerx=200)
    ink = _ink(surf)
    mid = (min(r.left for r in ink) + max(r.right for r in ink)) / 2.0
    assert abs(mid - 200) <= 4
