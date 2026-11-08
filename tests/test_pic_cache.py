"""The pictures worked out from other pictures are kept (src/pic_cache.py): the same pictures as worked out anew, and
each caller gets its own copies."""

import pygame
import pytest

import phenix_art
import pic_cache
import player


@pytest.fixture(autouse=True)
def _screen():
    pygame.display.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 64))


def _pic(colour):
    s = pygame.Surface((24, 20), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    pygame.draw.circle(s, colour, (12, 10), 8)
    return s


def _same(a, b):
    return a.get_size() == b.get_size() and pygame.image.tobytes(a, "RGBA") == pygame.image.tobytes(b, "RGBA")


def test_the_recoloured_fire_is_the_same_and_a_copy():
    src = _pic((255, 120, 30, 255))
    a = player.shift_fire_hsv(src, 0.52, 0.9, 1.08)
    b = player.shift_fire_hsv(src, 0.52, 0.9, 1.08)
    assert _same(a, player._shift_fire_hsv(src, 0.52, 0.9, 1.08)) and _same(a, b) and a is not b
    a.fill((1, 2, 3, 255))                                               # (one caller's change stays its own)
    assert _same(b, player.shift_fire_hsv(src, 0.52, 0.9, 1.08))
    assert not _same(b, player.shift_fire_hsv(src, 0.055, 1.12, 1.06))  # (another tint: another picture)


def test_the_pictures_of_the_change_are_the_same_and_copies():
    ship, drawn, flight = _pic((200, 200, 220, 255)), [_pic((255, 160, 40, 255))], _pic((255, 90, 20, 255))
    a = phenix_art.morph_sequence(ship, drawn, flight, steps=2, use_flow=False)
    b = phenix_art.morph_sequence(ship, drawn, flight, steps=2, use_flow=False)
    fresh = phenix_art._morph_sequence([ship] + drawn + [flight], 2, False, phenix_art.FLASH_RADIUS, False)
    assert a and len(a) == len(b) == len(fresh) and all(_same(x, y) for x, y in zip(a, fresh))
    assert all(x is not y for x, y in zip(a, b))
    other = phenix_art.morph_sequence(ship, drawn, _pic((20, 90, 255, 255)), steps=2, use_flow=False)
    assert not _same(other[-1], a[-1])                                   # (other pictures: worked out again)


def test_the_key_follows_the_pixels():
    a, b = _pic((255, 0, 0, 255)), _pic((255, 0, 0, 255))
    assert pic_cache.key_of(a) == pic_cache.key_of(b) and pic_cache.key_of(None) is None
    b.set_at((0, 0), (0, 0, 0, 255))
    assert pic_cache.key_of(a) != pic_cache.key_of(b)
