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


# ------------------------------------------------------------------ the hangar
def test_a_holo_card_has_cut_corners_and_a_gold_edge_when_chosen():
    a, b = _surf(), _surf()
    phobos_ui.holo(a, pygame.Rect(20, 20, 200, 100), True)
    phobos_ui.holo(b, pygame.Rect(20, 20, 200, 100), False)
    assert a.get_at((120, 20))[:3] == phobos_ui.LIT_EDGE and b.get_at((120, 20))[:3] == phobos_ui.HOLO_EDGE
    assert a.get_at((20, 20))[:3] == (0, 0, 0)                          # the corner is cut: nothing drawn there
    inside = b.get_at((120, 70))[:3]
    assert inside[2] > inside[0]                                         # blue glass


def test_a_meter_lights_the_first_cells():
    s = _surf()
    r = phobos_ui.meter(s, 10, 10, 2, 5)
    assert r.w == 5 * 16 + 4 * 3 and r.h == 5
    lit = [s.get_at((10 + i * 19 + 8, 12))[:3] == phobos_ui.CRT for i in range(5)]
    assert lit == [True, True, False, False, False]
    phobos_ui.meter(s, 10, 30, 9, 5)                                     # more than the total: all lit, no error
    assert all(s.get_at((10 + i * 19 + 8, 32))[:3] == phobos_ui.CRT for i in range(5))


def _hangar_pixels(g, hub):
    s = g.game_surface
    s.fill((0, 0, 0))
    hub.draw(s, g.font, g.medium_font, g.font, body=g.read_font)
    return s


def test_the_hangar_cards_sit_below_the_badges_and_the_chosen_one_is_gold(run):
    g = run.game
    hub = _hub(g, "hangar")
    hub.state["slots"][0]["owned"] = True
    hub.state["selected_slot"] = 0
    s = _hangar_pixels(g, hub)
    assert s.get_at((400, 64))[:3] == phobos_ui.LIT_EDGE                 # the chosen hull: gold edge on its top line
    assert s.get_at((880, 64))[:3] == phobos_ui.HOLO_EDGE                # the other one: blue glass
    badge = phobos_ui.badge(pygame.Surface((1280, 100)), g.font, "NOVA  -  NORMAL", (200, 200, 200), 40, left=56, max_w=330)
    assert badge.bottom < 64                                             # nothing under the pilot badge now


def test_the_workshop_stats_show_the_levels_as_cells(run):
    g = run.game
    hub = _hub(g, "hangar")
    sl = hub.state["slots"][0]
    sl.update(owned=True, lives=2, speed=60)
    hub.state["selected_slot"] = 0
    s = _hangar_pixels(g, hub)
    cells = lambda x0, n: [s.get_at((x0 + i * 19 + 8, 238 + 64 - 9 + 2))[:3] == phobos_ui.CRT for i in range(n)]
    lives_x = (1280 - (196 * 4 + 12 * 3)) // 2 + 98 - (2 * 16 + 3) // 2
    speed_x = lives_x + 208 - (5 * 16 + 4 * 3) // 2 + (2 * 16 + 3) // 2
    assert cells(lives_x, 2) == [True, True]                             # 2 lives of 2
    assert cells(speed_x, 5) == [True, True, True, False, False]         # 60 % = three cells of five
    sl["owned"] = False
    s = _hangar_pixels(g, hub)
    assert not any(s.get_at((x, 238 + 64 - 7))[:3] == phobos_ui.CRT for x in range(180, 1100))   # no hull, no levels


def test_the_points_are_on_a_steel_badge_at_the_right(run):
    g = run.game
    hub = _hub(g, "hangar")
    s = _hangar_pixels(g, hub)
    assert s.get_at((BASE_WIDTH - 56 - 1, 40))[:3] == phobos_ui.STEEL_EDGE      # the right end of the badge
    assert any(s.get_at((x, 40))[:3] == phobos_ui.GOLD for x in range(1000, 1224))   # gold digits


# ------------------------------------------------------------------ the bestiary
def test_a_crt_has_dark_green_glass_scan_lines_and_a_steel_bezel():
    s = _surf()
    phobos_ui.crt(s, pygame.Rect(20, 20, 300, 120))
    assert s.get_at((20, 70))[:3] == phobos_ui.STEEL_EDGE                    # the bezel
    glass = {s.get_at((170, y))[:3] for y in range(40, 100)}
    assert len(glass) == 2                                                    # scan lines: a darker row every third one
    dark, light = sorted(glass)
    assert dark[1] < light[1] and light[1] > light[0] and max(light) < 60         # dark green glass


def _bestiary_hub(g, kills=None):
    hub = _hub(g, "bestiary")
    if kills:
        ss.record_result(hub.state, "ch1_sortie", 100, True, kills)
    hub.best_index = 0
    return hub


def test_the_bestiary_list_is_a_terminal_with_the_chosen_entry_in_negative(run):
    g = run.game
    hub = _bestiary_hub(g, {"bird1": 160, "bird2": 55})
    s = _hangar_pixels(g, hub)
    lit = lambda y: sum(s.get_at((300, yy))[:3][1] > 200 for yy in range(y - 2, y + 3))
    assert lit(100) >= 2                                                     # the chosen row: phosphor
    assert lit(170) == 0                                                     # the other one: not lit
    row = {s.get_at((x, y))[:3] for x in range(100, 300) for y in range(104, 132)}
    assert min(sum(c) for c in row) < 70 and any(c[1] > 200 for c in row)    # dark letters on the lit row
    hub.best_index = 1
    s = _hangar_pixels(g, hub)
    assert lit(170) >= 2 and lit(100) == 0


def test_the_sheet_is_read_on_a_second_terminal(run):
    g = run.game
    hub = _bestiary_hub(g, {"bird1": 160})
    s = _hangar_pixels(g, hub)
    assert s.get_at((516, 300))[:3] == phobos_ui.STEEL_EDGE                  # the bezel of the right terminal
    assert any(s.get_at((x, 430))[:3] == phobos_ui.CRT_TEXT for x in range(540, 1180)) or \
        any(s.get_at((x, y))[:3] == phobos_ui.CRT_TEXT for x in range(540, 1180) for y in range(420, 560))


def test_the_empty_bestiary_is_one_terminal_with_its_line(run):
    g = run.game
    hub = _bestiary_hub(g)
    s = _hangar_pixels(g, hub)
    assert s.get_at((70 + 12, 300))[:3] == phobos_ui.STEEL_EDGE              # the bezel
    assert any(s.get_at((x, y))[:3] == phobos_ui.CRT_TEXT for x in range(400, 880) for y in range(330, 380))
