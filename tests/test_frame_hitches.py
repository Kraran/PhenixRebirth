"""Regression checks for work that must stay outside combat frames."""
import random
import pygame
import pytest
import starfield
from text_cache import TextCache, MAX_ENTRIES


@pytest.fixture
def scenery(monkeypatch):
    pygame.display.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 64))
    monkeypatch.setattr(starfield.Planet, "_cache", {})
    monkeypatch.setattr(starfield.Nebula, "_cache", {})
    monkeypatch.setattr(starfield.Nebula, "_raw", {})
    monkeypatch.setattr(starfield.Comet, "_frames", None)
    return starfield


def test_prepare_preserves_random_state_and_nebula_first_spawn(scenery):
    state = random.getstate()
    try:
        scenery.prepare_assets()
        assert random.getstate() == state
        filename = scenery.NEBULA_FILES[0]
        assert filename not in scenery.Nebula._cache
        assert filename in scenery.Nebula._raw
        random.seed(98)
        prepared = scenery.Nebula(filename)
        after = random.getstate()
        pixels = pygame.image.tobytes(prepared.image, "RGBA")
        scenery.Nebula._cache.clear()
        random.seed(98)
        cold = scenery.Nebula(filename)
        assert random.getstate() == after
        assert pygame.image.tobytes(cold.image, "RGBA") == pixels
        assert filename not in scenery.Nebula._raw
    finally:
        random.setstate(state)


def test_prepared_scenery_never_decodes_again(scenery, monkeypatch):
    state = random.getstate()
    try:
        scenery.prepare_assets()
        def unexpected_load(*args, **kwargs):
            raise AssertionError("Scenery decoded during combat")
        monkeypatch.setattr(pygame.image, "load", unexpected_load)
        scenery.prepare_assets()
        for filename in scenery.NEBULA_FILES:
            scenery.Nebula(filename)
        for filename in scenery.PLANET_FILES:
            scenery.Planet._load_image(filename)
            scenery.Planet._load_film(filename)
    finally:
        random.setstate(state)


def test_text_cache_evicts_only_one_oldest_entry():
    class Font:
        def render(self, *args):
            return object()
    font = Font()
    cache = TextCache()
    color = (255, 255, 255)
    oldest = cache.get(font, "0", color)
    second = cache.get(font, "1", color)
    for i in range(2, MAX_ENTRIES):
        cache.get(font, str(i), color)
    assert cache.get(font, "0", color) is oldest
    cache.get(font, "next", color)
    assert len(cache._data) == MAX_ENTRIES
    assert (font, "0", color) not in cache._data
    assert cache.get(font, "1", color) is second
    cache.clear()
    assert not cache._data
