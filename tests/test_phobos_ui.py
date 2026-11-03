"""The steel look of the Adventure menus (src/phobos_ui.py): plates, lit rows, title, tabs, help bar, pictures behind
the panes. The classic menus keep their look."""
import importlib.util
import os

import pygame
import pytest

import draw_frame
import hint_bar
import phobos_ui
import story_state as ss
from settings import BASE_HEIGHT, BASE_WIDTH, asset_path
from test_smoke import run  # noqa: F401  (fixture)

PANES = ("map", "hangar", "bestiary", "log", "extras")


@pytest.fixture(autouse=True)
def _fresh_caches():
    phobos_ui._layers.clear()
    phobos_ui._backdrops.clear()                  # (a picture is loaded on first use: it needs the display)
    yield
    phobos_ui._backdrops.clear()


def _surf(w=400, h=200):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((0, 0, 0, 255))
    return s


def _act2():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    st["credits"] = 4200
    return st


def _hub(g, pane="map"):
    hub = g.story
    hub.state = _act2()
    hub.screen = "hub"
    hub.pane = pane
    g.started = False
    g.menu_screen = "story_hub"
    return hub


# ------------------------------------------------------------------ the pieces
def test_a_plate_is_steel_with_rivets_and_the_hazard_strip():
    s = _surf()
    r = phobos_ui.plate(s, pygame.Rect(20, 20, 300, 120), hazard=True)
    assert r == pygame.Rect(20, 20, 300, 120)
    inside = s.get_at((160, 100))[:3]
    assert inside[2] > inside[0] and max(inside) < 60                 # dark blue-grey steel
    strip = {s.get_at((20 + x, 20 + 4))[:3] for x in range(4, 60)}
    assert phobos_ui.HAZARD in strip and phobos_ui.HAZARD_DARK in strip   # yellow and black stripes
    assert s.get_at((20 + 11, 20 + 120 - 12))[:3] != inside                  # (a rivet sits in the lower left corner)
    plain = _surf()
    phobos_ui.plate(plain, pygame.Rect(20, 20, 300, 120))
    assert plain.get_at((160, 24))[:3] != s.get_at((160, 24))[:3]      # no strip without `hazard`


def test_a_plate_is_drawn_once_per_size():
    phobos_ui._layers.clear()
    s = _surf()
    phobos_ui.plate(s, (0, 0, 120, 60))
    phobos_ui.plate(s, (50, 50, 120, 60))
    assert len([k for k in phobos_ui._layers if k[0] == "plate"]) == 1
    phobos_ui.plate(s, (0, 0, 130, 60))
    assert len([k for k in phobos_ui._layers if k[0] == "plate"]) == 2


def test_the_chosen_row_has_a_gold_edge_and_a_warm_fill():
    s = _surf()
    phobos_ui.lit(s, pygame.Rect(10, 10, 200, 40))
    assert s.get_at((100, 10))[:3] == phobos_ui.LIT_EDGE
    fill = s.get_at((100, 30))[:3]
    assert fill[0] > fill[2] + 20                                      # warm, not blue


def test_the_open_tab_is_lit_and_the_others_are_steel():
    a, b = _surf(), _surf()
    phobos_ui.tab(a, pygame.Rect(10, 10, 120, 28), True)
    phobos_ui.tab(b, pygame.Rect(10, 10, 120, 28), False)
    assert a.get_at((10, 20))[:3] == phobos_ui.LIT_EDGE
    assert b.get_at((10, 20))[:3] == phobos_ui.STEEL_EDGE


def test_the_title_sits_in_a_cartouche_centred_on_the_screen():
    pygame.font.init()
    font = pygame.font.Font(None, 40)
    s = _surf(BASE_WIDTH, 120)
    r = phobos_ui.title(s, font, "HANGAR", BASE_WIDTH // 2, 10)
    assert r.centerx == BASE_WIDTH // 2 and r.top == 10
    assert s.get_at((r.left + 1, r.centery))[:3] == phobos_ui.COPPER          # the copper edge
    assert any(s.get_at((x, r.centery))[:3] == phobos_ui.AMBER for x in range(r.left, r.right))   # the letters
    n = len(phobos_ui._layers)
    phobos_ui.title(s, font, "HANGAR", BASE_WIDTH // 2, 10)
    assert len(phobos_ui._layers) == n                                          # made once


def test_a_badge_hangs_on_the_left_or_the_right_and_shrinks_its_text():
    pygame.font.init()
    font = pygame.font.Font(None, 30)
    s = _surf(BASE_WIDTH, 80)
    left = phobos_ui.badge(s, font, "NOVA - NORMAL", (200, 200, 220), 40, left=56)
    right = phobos_ui.badge(s, font, "VAISSEAU : SHIELD", (200, 200, 220), 40, right=BASE_WIDTH - 56)
    assert left.left == 56 and right.right == BASE_WIDTH - 56 and left.centery == 40
    long = phobos_ui.badge(s, font, "A very very long name of a ship that does not fit", (200, 200, 220), 40,
                           right=BASE_WIDTH - 56, max_w=330)
    assert long.w <= 330


def test_the_help_band_is_steel_with_a_bevelled_edge():
    band = phobos_ui.band()
    assert band.get_size() == (BASE_WIDTH, hint_bar.BAND_H)
    assert band.get_at((5, 0))[:3] == phobos_ui.STEEL_EDGE and band.get_at((5, 2))[:3] == phobos_ui.STEEL_LIGHT
    assert band.get_at((5, 20))[:3] == phobos_ui.STEEL_DARK


# ------------------------------------------------------------------ the pictures behind the panes
@pytest.mark.parametrize("pane", PANES)
def test_every_pane_has_its_picture_made_for_the_screen(run, pane):
    img = phobos_ui.backdrop(pane)
    assert img is not None and img.get_size() == (BASE_WIDTH, BASE_HEIGHT)
    assert os.path.getsize(asset_path("story", phobos_ui.BACKDROPS[pane] + ".jpg")) < 200 * 1024     # light to load
    mean = pygame.transform.average_color(img)[:3]
    assert max(mean) < 120                                                     # dark: the text reads on it


def test_no_picture_for_an_unknown_pane_or_a_missing_file(monkeypatch, tmp_path):
    assert phobos_ui.backdrop("nope") is None
    monkeypatch.setattr(phobos_ui, "_backdrops", {})
    monkeypatch.setattr(phobos_ui, "asset_path", lambda *a: str(tmp_path / "missing.jpg"))
    assert phobos_ui.backdrop("map") is None


def test_a_broken_picture_is_not_fatal(monkeypatch, tmp_path):
    bad = tmp_path / "ui_map.jpg"
    bad.write_bytes(b"not a picture")
    monkeypatch.setattr(phobos_ui, "_backdrops", {})
    monkeypatch.setattr(phobos_ui, "asset_path", lambda *a: str(bad))
    assert phobos_ui.backdrop("map") is None


def test_the_tool_bakes_a_dark_16_9_picture(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "make_ui_backdrops", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools",
                                          "make_ui_backdrops.py"))
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    src = pygame.Surface((900, 900))
    src.fill((200, 180, 160))
    path = tmp_path / "src.png"
    pygame.image.save(src, str(path))
    out = tool.bake(str(path), "map")
    assert out.get_size() == (1280, 720)
    centre, corner = out.get_at((640, 360))[:3], out.get_at((3, 3))[:3]
    assert 80 < centre[0] < 140 and corner[0] < centre[0] * 0.7                 # darkened, darker in the corners


# ------------------------------------------------------------------ the hub
def test_the_help_bar_is_steel_only_in_the_adventure(run):
    g = run.game
    _hub(g)
    assert hint_bar.is_steel(g)
    g.menu_screen = "main"
    assert not hint_bar.is_steel(g)
    _hub(g)
    g.started = True
    assert not hint_bar.is_steel(g)


def test_the_steel_keys_differ_from_the_classic_ones():
    pygame.font.init()
    a = hint_bar._keycap("OK", steel=True)
    b = hint_bar._keycap("OK")
    assert a.get_at((0, 12))[:3] == hint_bar.STEEL_CAP_EDGE and b.get_at((0, 12))[:3] == hint_bar.CAP_EDGE
    assert hint_bar.render([("ok", "hint_launch")], False, None, True) is not hint_bar.render(
        [("ok", "hint_launch")], False, None, False)


@pytest.mark.parametrize("pane", PANES)
def test_each_pane_draws_its_picture_title_and_tabs(run, pane):
    g = run.game
    hub = _hub(g, pane)
    s = g.game_surface
    s.fill((255, 0, 255))
    hub.draw(s, g.font, g.medium_font, g.font, body=g.read_font)
    picture = phobos_ui.backdrop(pane)
    assert s.get_at((3, 400))[:3] == picture.get_at((3, 400))[:3]                # the picture, not the stars
    assert phobos_ui.COPPER in {s.get_at((x, 11))[:3] for x in range(400, 880)}        # the copper edge of the cartouche
    assert s.get_at((56, 38))[:3] == phobos_ui.STEEL_EDGE                        # the steel badge of the pilot
    assert any(s.get_at((x, hub.TAB_Y))[:3] == phobos_ui.LIT_EDGE for x in range(280, 1000))   # the open tab is lit


def test_the_bar_is_steel_in_the_hub_and_classic_elsewhere(run):
    g = run.game
    _hub(g)
    s = g.game_surface
    hint_bar.draw_for(g, s)
    assert s.get_at((5, hint_bar.BAND_Y))[:3] == phobos_ui.STEEL_EDGE
    g.menu_screen = "main"
    hint_bar.draw_for(g, s)
    assert s.get_at((5, hint_bar.BAND_Y))[:3] != phobos_ui.STEEL_EDGE


def test_the_starfield_is_not_drawn_under_a_pane_with_a_picture(run, monkeypatch):
    g = run.game
    hub = _hub(g, "map")
    assert hub.covers_screen()
    calls = []
    monkeypatch.setattr(draw_frame, "draw_background", lambda game: calls.append(1))
    g._draw_canvas()
    assert not calls
    monkeypatch.setattr(phobos_ui, "BACKDROPS", {})                              # no picture: the stars show again
    assert not hub.covers_screen()
    g._draw_canvas()
    assert calls


def test_the_screens_before_the_hub_keep_the_starfield(run):
    g = run.game
    hub = _hub(g, "map")
    hub.screen = "slots"
    assert not hub.covers_screen()


def test_the_map_wears_the_steel_plate_and_the_lit_row(run):
    g = run.game
    hub = _hub(g, "map")
    s = g.game_surface
    hub.draw(s, g.font, g.medium_font, g.font, body=g.read_font)
    strip = {s.get_at((90 + x, 78 + 4))[:3] for x in range(0, 40)}
    assert phobos_ui.HAZARD in strip                                             # the hazard strip on the list
    row_edge = [s.get_at((300, y))[:3] for y in range(150, 175)]
    assert phobos_ui.LIT_EDGE in row_edge                                        # the lit row of the next mission
