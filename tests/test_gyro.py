"""The escort modules (src/gyro.py), step 1: on screen. The gyroscope pictures, the way they follow the ship, the dome and
the Phenix form, the electric wall, and the TEST - Modules mission with its menu."""
import pygame
import pytest

import gyro
import i18n
import story_state as ss
from settings import BASE_WIDTH
from test_smoke import run  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


class _Ship:
    def __init__(self, x=640.0, y=600.0):
        self.x, self.y = x, y
        self.alive, self.dying = True, False
        self.is_phenix = False
        self.morph_dir = 0
        self.invulnerable = 0.0
        self.blast_hide = 0


class _Game:
    def __init__(self):
        self.explosions = []
        self.played = []
        self.sounds = self

    def play(self, name, **kw):
        self.played.append(name)

    def _boom(self, x, y, kind="enemy"):
        return ("boom", x, y, kind)


def _settle(g, game, ship, seconds=2.0, dt=1 / 120):
    for _ in range(int(seconds / dt)):
        g.update(game, ship, dt)


# ------------------------------------------------------------------ the pictures
def test_the_pictures_of_the_two_hulls():
    for hull in ("phoenix", "shield"):
        pics = gyro.frames(hull)
        assert len(pics) == gyro.FRAMES and all(p.get_size() == (gyro.SIZE, gyro.SIZE) for p in pics)
        assert gyro.frames(hull) is pics                                        # (made once)
        assert pics[0].get_at((gyro.SIZE // 2, gyro.SIZE // 2)).a > 200          # the sphere in the middle
        assert pics[0].get_at((0, 0)).a == 0                                     # (round: the corners are empty)
    a = gyro.frames("phoenix")[0].get_at((gyro.SIZE // 2, gyro.SIZE // 2 + 6))
    b = gyro.frames("shield")[0].get_at((gyro.SIZE // 2, gyro.SIZE // 2 + 6))
    assert a.b > a.r and b.r > b.b                                               # silver-blue, copper-red
    assert pygame.image.tostring(gyro.frames("shield")[0], "RGBA") != pygame.image.tostring(
        gyro.frames("shield")[gyro.FRAMES // 3], "RGBA")                         # the ring turns


# ------------------------------------------------------------------ placing
def test_one_module_on_the_left_two_on_both_sides():
    ship = _Ship()
    assert [m.side for m in gyro.Gyro("shield", 1, 1, ship).modules] == [-1]
    assert [m.side for m in gyro.Gyro("shield", 2, 2, ship).modules] == [-1, 1]
    assert all(m.hp == 2 for m in gyro.Gyro("shield", 2, 2, ship).modules)


def test_they_follow_the_ship_a_little_late():
    ship, game = _Ship(), _Game()
    g = gyro.Gyro("phoenix", 2, 1, ship)
    _settle(g, game, ship)
    left, right = g.modules
    assert (left.x, left.y) == pytest.approx((ship.x - gyro.ANCHOR[0], ship.y + gyro.ANCHOR[1]), abs=0.5)
    assert right.x == pytest.approx(ship.x + gyro.ANCHOR[0], abs=0.5)
    ship.x += 100
    g.update(game, ship, 1 / 60)
    assert ship.x - 100 - gyro.ANCHOR[0] < left.x < ship.x - gyro.ANCHOR[0]       # on its way, not there yet
    _settle(g, game, ship, 1.0)
    assert left.x == pytest.approx(ship.x - gyro.ANCHOR[0], abs=0.5)


@pytest.mark.parametrize("how", ("dome", "morph"))
def test_in_the_dome_or_the_phenix_form_they_move_out_and_down(how):
    ship, game = _Ship(), _Game()
    g = gyro.Gyro("shield", 2, 1, ship)
    _settle(g, game, ship)
    if how == "dome":
        ship.is_phenix = True
    else:
        ship.morph_dir = 1                                                       # (already while it changes)
    g.update(game, ship, gyro.WIDE_TIME / 2)
    assert 0.4 < g.wide < 0.6                                                    # it takes WIDE_TIME
    _settle(g, game, ship)
    left, right = g.modules
    assert left.x == pytest.approx(ship.x - gyro.WIDE[0], abs=0.5) and right.y == pytest.approx(ship.y + gyro.WIDE[1], abs=0.5)
    ship.is_phenix, ship.morph_dir = False, 0
    _settle(g, game, ship)
    assert g.wide == 0 and left.x == pytest.approx(ship.x - gyro.ANCHOR[0], abs=0.5)


# ------------------------------------------------------------------ the wall
def test_the_electric_wall_destroys_a_module():
    ship, game = _Ship(x=400), _Game()
    g = gyro.Gyro("shield", 2, 2, ship)
    _settle(g, game, ship)
    ship.x = 50                                                                  # (the left module goes into the wall)
    for _ in range(40):
        g.update(game, ship, 1 / 120)
        if g.modules[0].struck > 0:
            break
    left, right = g.modules
    assert left.struck > 0 and left.alive and left not in g.alive()             # in the lightning: it does no more
    assert "electric" in game.played
    _settle(g, game, ship, gyro.STRUCK + 0.05)
    assert not left.alive and g.lost == ["wall"] and game.explosions             # it blows up, whatever its armour
    assert right.alive and right in g.alive()
    surf = pygame.Surface((BASE_WIDTH, 720), pygame.SRCALPHA)
    g.draw(surf, ship)                                                           # (only the right one is drawn)


def test_the_wall_needs_the_module_against_it():
    ship, game = _Ship(x=gyro.WALL_X + gyro.SIZE * 0.42 + gyro.ANCHOR[0] + 6), _Game()
    g = gyro.Gyro("phoenix", 2, 1, ship)
    _settle(g, game, ship)
    assert all(m.struck == 0 and m.alive for m in g.modules)


# ------------------------------------------------------------------ drawn with the ship
def test_they_blink_with_the_ship_and_vanish_with_it():
    ship, game = _Ship(), _Game()
    g = gyro.Gyro("shield", 2, 1, ship)
    _settle(g, game, ship)

    def drawn():
        surf = pygame.Surface((BASE_WIDTH, 720), pygame.SRCALPHA)
        g.draw(surf, ship)
        m = g.modules[0]
        return surf.get_at((int(m.x), int(m.y))).a > 0
    assert drawn()
    ship.invulnerable = 1.0 / 12 * 2 + 0.01                                     # int(x * 12) even: the ship is hidden
    assert not drawn()
    ship.invulnerable = 1.0 / 12 + 0.01
    assert drawn()
    ship.invulnerable = 0
    ship.blast_hide = 0.2
    assert not drawn()
    ship.blast_hide, ship.dying = 0, True
    assert not drawn()


# ------------------------------------------------------------------ the mission and its menu
def _hub(run, hull="shield"):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    if hull == "phoenix":
        st["slots"][1]["owned"] = True
        st["selected_slot"] = 1
    ss.save_state(ss.story_path(1), st)
    g.menu_screen = "story_hub"
    g.story.open_slot(1)
    g.story.screen, g.story.pane = "hub", "map"
    g.story.map_index = [m["id"] for m in g.story.missions()].index("test_modules")
    return g


def test_the_mission_is_a_test_on_the_maps_of_the_three_acts():
    m = ss.mission_by_id("test_modules")
    assert m["acts"] == (1, 2, 3) and m["training"] and m["test"]
    assert ss.mission_waves(m) == [6, 7, 8, 9, 10, 11]                           # a run of the levels 6 to 11
    for act in (1, 2, 3):
        ids = [x["id"] for x in ss.MISSIONS if act in tuple(x.get("acts", ()))]
        assert ids.index("test_modules") == ids.index("test_scramble") + 1
    for lang in ("fr", "en"):
        i18n.set_lang(lang)
        for key in ("story_m_modules", "story_m_modules_hud", "story_m_modules_b", "modules_pick_title",
                    "modules_pick_count_1", "modules_pick_count_2", "modules_pick_armour_1", "modules_pick_armour_2"):
            assert i18n.t(key) != key
        for armour in (1, 2):
            assert "{" not in i18n.t("modules_pick_info_%d" % armour).format(shots=3)
    i18n.set_lang("fr")


def test_the_menu_chooses_how_many_and_how_tough(run):
    g = _hub(run)
    hub = g.story
    assert hub.confirm() is None and hub.screen == "lander_pick" and hub._pick_modules()
    import story
    assert story.MODULE_PICKS[hub.lander_index] == (2, 1)                        # (two, normal: the first choice lit)
    surf = pygame.Surface((1280, 720))
    hub._draw_gate(surf, g.font, g.medium_font, g.font)                          # (the menu draws)
    picks = []
    for _ in range(len(story.MODULE_PICKS)):
        picks.append(story.MODULE_PICKS[hub.lander_index])
        hub.nav_v(1)
    assert sorted(picks) == [(1, 1), (1, 2), (2, 1), (2, 2)]
    while story.MODULE_PICKS[hub.lander_index] != (1, 2):
        hub.nav_v(1)
    spec = hub.confirm()
    assert spec["id"] == "test_modules" and spec["modules"] == {"count": 1, "armour": 2}
    assert spec["training"] and spec["waves"] == [6, 7, 8, 9, 10, 11] and hub.screen == "hub"


def test_back_leaves_the_menu_without_launching(run):
    g = _hub(run)
    g.story.confirm()
    g.story.back()
    assert g.story.screen == "hub" and not g.started


@pytest.mark.parametrize("hull", ("shield", "phoenix"))
def test_the_mission_flies_with_its_modules(run, hull):
    g = _hub(run, hull)
    g.story.confirm()
    spec = g.story.confirm()
    g._request_adventure(dict(spec, first_help_read=True))
    assert g.started and g.gyro is not None
    assert g.gyro.hull == ("phoenix" if hull == "phoenix" else "shield") and len(g.gyro.modules) == 2
    if hull == "shield":
        assert g.player.adventure_dome                                           # (the test: the dome, to see them move out)
    run.frames(30)
    left = g.gyro.modules[0]
    assert left.x == pytest.approx(g.player.x - gyro.ANCHOR[0], abs=20)
    run.frames(2)


def test_no_modules_without_them_nor_once_the_mission_is_over(run):
    g = run.game
    g.adventure = {"id": "x"}
    gyro.start(g, {"launch": True})
    assert g.gyro is None
    gyro.start(g, {"modules": {"count": 2, "armour": 1}, "lander": True})
    assert g.gyro is None                                                        # (not in the Lander, Scramble... for now)
    gyro.start(g, {"modules": {"count": 2, "armour": 1}})
    assert g.gyro is not None
    g.adventure = None
    assert gyro._on(g) is None                                                   # an arcade game never shows them
