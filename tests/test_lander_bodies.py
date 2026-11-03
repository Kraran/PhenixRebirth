"""The five settings of the Lunar Lander test (src/lander.py BODIES, src/lander_view.py, the menu of the choice in story.py): the
asteroid, Titan, Europa, Deimos and Triton, each with its ground, its sky and its mother planet (Saturn, Jupiter, Mars, Neptune;
other asteroids for the asteroid)."""
import random

import numpy as np
import pygame
import pytest

import i18n
import lander as ld
import lander_view as lv
import story_state as ss
from settings import BASE_HEIGHT, BASE_WIDTH
from story import StoryHub
from test_smoke import run  # noqa: F401,F811  (fixture)
from test_spacewar import _launch

NEW = ("europa", "deimos", "triton")
PLANETS = {"ice": "saturn", "europa": "jupiter", "deimos": "mars", "triton": "neptune", "rock": "asteroids"}


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((64, 64))
    yield


def _form(style, seed=7):
    return ld.LanderFormation(style=style, seed=seed, rng=random.Random(1))


# ------------------------------------------------------------------ the bodies
def test_there_are_five_bodies_and_the_menu_lists_them_all_once():
    assert set(ld.BODIES) == {"ice", "rock", "europa", "deimos", "triton"}
    assert sorted(ld.MENU_ORDER) == sorted(ld.BODIES) and len(set(ld.MENU_ORDER)) == 5
    assert ld.MENU_ORDER[0] == "rock"


def test_each_body_has_its_mother_planet():
    assert {k: v["planet"] for k, v in ld.BODIES.items()} == PLANETS


def test_the_gravity_follows_the_real_ones_deimos_hardly_pulls():
    g = {k: v["gravity"] for k, v in ld.BODIES.items()}
    assert g["ice"] > g["europa"] > g["triton"] > g["rock"] > g["deimos"] > 0
    assert g["deimos"] < 15 and g["europa"] > 50


def test_titan_and_the_asteroid_keep_their_ground_exactly():
    a = ld.Terrain("ice", 3)
    assert round(float(np.abs(a.h).sum()), 3) == 278642.841 and len(a.boulders) == 153
    b = ld.Terrain("rock", 5)
    assert round(float(np.abs(b.h).sum()), 3) == 313482.665 and len(b.boulders) == 151


@pytest.mark.parametrize("style", NEW)
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_ground_has_one_to_three_flat_zones_and_loops(style, seed):
    t = ld.Terrain(style, seed)
    assert 1 <= len(t.pads) <= 3
    for p in t.pads:
        xs = np.linspace(p["x"] - p["w"] / 2, p["x"] + p["w"] / 2, 20)
        assert np.ptp(t.ground(xs)) < 1.0
    assert abs(t.ground(0.0) - t.ground(float(ld.WORLD))) < 1e-6
    assert (ld.Terrain(style, seed).h == t.h).all()


def test_the_new_grounds_are_gentler_than_titan():
    rough = {s: float(np.abs(np.diff(ld.Terrain(s, 4).h)).mean()) for s in ("ice", "europa", "deimos", "triton")}
    assert rough["europa"] < rough["ice"] and rough["deimos"] < rough["ice"] and rough["triton"] < rough["ice"]


@pytest.mark.parametrize("style", sorted(ld.BODIES))
def test_a_formation_of_each_body_uses_its_gravity(style):
    f = _form(style)
    assert f.style == style and f.gravity == ld.BODIES[style]["gravity"]


# ------------------------------------------------------------------ the pictures
def _sky_only(style, cam_x=3000.0):
    """The view with the ground far under the screen: the sky and what is in it."""
    f = _form(style)
    f.x, f.y, f.zoom = cam_x, -2000.0, 0.25
    view = lv.View(style)
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    view.draw(surf, f)
    return surf


@pytest.mark.parametrize("style", sorted(ld.BODIES))
def test_the_view_draws_each_body_at_the_three_zooms(style):
    f = _form(style)
    view = lv.View(style)
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    for alt, z in ((-1500.0, 0.25), (-500.0, 0.5), (-120.0, 1.0)):
        f.y, f.zoom = alt, z
        f.x = f.terrain.pads[0]["x"]
        view.draw(surf, f)
        assert surf.get_at((5, BASE_HEIGHT - 5))[:3] != (0, 0, 0)               # (the ground is not black)


@pytest.mark.parametrize("style,spot,min_light", [("europa", (330, 190), 60), ("deimos", (930, 210), 60),
                                                  ("triton", (320, 200), 40), ("ice", (900, 200), 90)])
def test_the_mother_planet_shines_in_the_sky(style, spot, min_light):
    sky = _sky_only(style)
    px = sky.get_at(spot)[:3]
    assert max(px) >= min_light, (style, px)
    empty = sky.get_at((640, 700))[:3]                         # far from it
    assert max(px) > max(empty)


def test_the_colour_of_each_mother_planet_is_the_right_one():
    r, g, b = _sky_only("triton").get_at((320, 200))[:3]
    assert b > r and b > g                                      # Neptune is blue
    r, g, b = _sky_only("deimos").get_at((930, 210))[:3]
    assert r > b                                                # Mars is red-orange
    r, g, b = _sky_only("ice").get_at((900, 200))[:3]
    assert r > b                                                # Saturn in the orange haze


def test_the_other_asteroids_float_in_the_sky_of_the_asteroid():
    a = lv.assets("rock")
    assert a["planet"] is None and len(a["rocks"]) >= 6
    near = _sky_only("rock")
    ys, xs = np.nonzero(pygame.surfarray.array3d(near).max(axis=2).T > 60)
    assert len(xs) > 2000                                       # (rocks, not only stars)


def _mother_only(style, cam_x, cam_y=-1000.0):
    """Only the mother planet (and the other asteroids) of the view, on black."""
    view = lv.View(style)
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    view._mother(surf, cam_x, cam_y)
    return pygame.image.tostring(surf, "RGB")


@pytest.mark.parametrize("style", ["europa", "rock"])
def test_the_mother_planet_slides_a_little_when_the_ship_moves_and_comes_round_with_the_world(style):
    assert _mother_only(style, 1500.0) != _mother_only(style, 4500.0)
    assert _mother_only(style, 0.0) == _mother_only(style, float(ld.WORLD))               # (nothing jumps when the ground comes round)
    assert _mother_only(style, 3000.0, -1700.0) != _mother_only(style, 3000.0, -100.0)     # (and it rises as the ship comes down)


def test_the_textures_of_the_grounds_differ_from_one_body_to_the_next():
    means = {}
    for style in sorted(ld.BODIES):
        tile = lv.assets(style)["tiles"][0]
        means[style] = tuple(int(v) for v in pygame.transform.average_color(tile)[:3])
    assert len(set(means.values())) == 5
    assert min(means["europa"]) > 150                           # Europa is bright
    assert max(means["deimos"]) < 140                           # Deimos is dark
    r, g, b = means["triton"]
    assert r > g + 10 and r > 150                            # Triton is pinkish


def test_the_tiles_of_each_body_loop_on_their_sides():
    for style in NEW:
        for tile in lv.assets(style)["tiles"]:
            left = pygame.surfarray.array3d(tile)[0].astype(int)
            right = pygame.surfarray.array3d(tile)[-1].astype(int)
            assert np.abs(left - right).mean() < 22, style     # (neighbouring columns across the seam look alike)


def test_the_lit_edge_and_the_boulders_have_the_colours_of_their_body():
    assert lv.LOOKS["europa"]["lip"][2] > 240 and lv.LOOKS["deimos"]["plain"][0] < 100
    assert set(lv.LOOKS) == set(ld.BODIES)


# ------------------------------------------------------------------ the menu of the choice
def _hub():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.screen, hub.pane = "hub", "map"
    hub.map_index = [m["id"] for m in hub.missions()].index("test_lander")
    return hub


def test_launching_the_test_opens_the_menu_of_the_settings_first():
    hub = _hub()
    assert hub.confirm() is None
    assert hub.screen == "lander_pick" and hub.lander_index == 0


def test_the_cursor_moves_with_up_down_and_left_right_and_wraps():
    hub = _hub()
    hub.confirm()
    hub.nav_v(1)
    assert hub.lander_index == 1
    hub.nav_h(1)
    assert hub.lander_index == 2
    hub.nav_v(-1)
    hub.nav_v(-1)
    hub.nav_v(-1)
    assert hub.lander_index == 4                                # (0 -> last)
    hub.nav_v(1)
    assert hub.lander_index == 0


@pytest.mark.parametrize("index", range(5))
def test_the_setting_chosen_is_the_one_launched(index):
    hub = _hub()
    hub.confirm()
    hub.lander_index = index
    spec = hub.confirm()
    assert spec and spec["lander"] and spec["training"] and spec["body"] == ld.MENU_ORDER[index]
    assert hub.screen == "hub"


def test_back_leaves_the_menu_without_launching():
    hub = _hub()
    hub.confirm()
    hub.back()
    assert hub.screen == "hub" and hub.pane == "map"
    assert hub.confirm() is None and hub.screen == "lander_pick"          # (it opens again)


def test_a_launch_without_a_choice_still_draws_a_setting_at_random(run):
    spec = _launch(run, "test_lander")
    assert "body" not in spec
    assert run.game.formation.style in ld.BODIES


@pytest.mark.parametrize("style", sorted(ld.BODIES))
def test_the_game_flies_the_setting_of_the_spec(run, style):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index("test_lander")
    spec = g.story._launch_selected(body=style)
    assert spec["body"] == style
    g._begin_adventure(spec)
    g.input_grace = 0.0
    run.frames(3)
    form = g.formation
    assert form.style == style and form.gravity == ld.BODIES[style]["gravity"]
    assert form.view is not None and form.view.style == style


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_the_menu_is_drawn_for_every_setting_and_the_text_fits(lang):
    before = i18n.get_lang()
    i18n.set_lang(lang)
    try:
        hub = _hub()
        hub.confirm()
        font = pygame.font.Font(None, 28)
        for k in range(5):
            hub.lander_index = k
            surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
            hub.draw(surf, font, font, font)
            assert surf.get_at((900, 300))[:3] != (0, 0, 0)       # the picture is there
            key = ld.MENU_ORDER[k]
            for name in ("lander_body_", "lander_planet_", "lander_info_"):
                assert i18n.t(name + key) and not i18n.t(name + key).startswith(name)
    finally:
        i18n.set_lang(before)


def test_the_picture_of_a_setting_is_made_once():
    a = lv.preview("triton")
    assert a.get_size() == lv.PREVIEW_SIZE and lv.preview("triton") is a


def test_the_help_bar_of_the_menu():
    hub = _hub()
    hub.confirm()
    pairs, _lit = hub.help_items()
    assert ("ok", "hint_takeoff") in pairs and ("back", "hint_back") in pairs


def test_the_texts_of_the_settings_exist_in_french_and_english():
    for lang in ("fr", "en"):
        for key in ld.BODIES:
            for name in ("lander_body_", "lander_planet_", "lander_info_"):
                assert i18n.T[name + key][lang]
    assert i18n.T["lander_pick_title"]["fr"] != i18n.T["lander_pick_title"]["en"]
    for style in ld.BODIES:
        assert "..." not in i18n.T["lander_info_" + style]["fr"] and "..." not in i18n.T["lander_info_" + style]["en"]
