"""The cards of the achievements: one picture each (assets/achievements, made by tools/make_achievement_art.py),
a frame whose metal is the tier, grey when locked, a "?" for a secret not found yet."""
import importlib.util
import os

import pygame
import pytest

import achievement_cards as ac
import achievements as ach
from settings import asset_path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def screen():
    pygame.display.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((8, 8))
    ac._CACHE.clear()
    yield
    ac._CACHE.clear()


@pytest.mark.parametrize("aid", ach.ALL_IDS)
def test_every_achievement_has_its_picture(aid):
    path = asset_path("achievements", aid + ".png")
    assert os.path.isfile(path), aid
    assert pygame.image.load(path).get_size() == (ac.BASE, ac.BASE)


def test_the_pictures_are_all_different():
    seen = {}
    for aid in ach.ALL_IDS:
        raw = pygame.image.tobytes(pygame.image.load(asset_path("achievements", aid + ".png")), "RGB")
        assert raw not in seen, (aid, seen.get(raw))
        seen[raw] = aid


def test_the_tool_knows_every_achievement():
    spec = importlib.util.spec_from_file_location("make_achievement_art",
                                                  os.path.join(ROOT, "tools", "make_achievement_art.py"))
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    assert set(tool.SCENES) == set(ach.ALL_IDS)


def _px(img, x, y):
    return tuple(img.get_at((x, y)))[:3]


def test_the_frame_tells_the_tier():
    edge = {state: _px(ac.card("first_blood", state, 128), 3, 64) for state in ac.STATES}
    assert len({edge[s] for s in ("locked", "normal", "bronze", "silver", "gold")}) == 5
    gold = ac.card("first_blood", "gold", 128)
    assert gold.get_at((0, 0))[3] == 0                                  # rounded corners
    assert gold.get_at((64, 64))[3] == 255


def test_a_locked_card_is_grey_and_a_secret_hides_its_picture():
    r, g, b = _px(ac.card("phenix_wake", "locked", 128), 64, 64)
    assert max(abs(r - g), abs(g - b)) < 30                             # no colour left
    a = pygame.image.tobytes(ac.card("pleiades", "hidden", 64), "RGBA")
    b2 = pygame.image.tobytes(ac.card("boldly_go", "hidden", 64), "RGBA")
    assert a == b2                                                      # nothing tells one secret from another


def test_a_missing_picture_still_makes_a_card(monkeypatch):
    monkeypatch.setattr(ac, "picture_path", lambda aid: "/nowhere/" + aid + ".png")
    img = ac.card("first_blood", "gold", 80)
    assert img.get_size() == (80, 80)


def test_the_sizes_are_kept():
    a = ac.card("razor", "silver", 80)
    assert ac.card("razor", "silver", 80) is a
    assert ac.card("razor", "silver", 96).get_size() == (96, 96)
