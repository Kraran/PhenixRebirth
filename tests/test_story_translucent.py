"""The backgrounds of the adventure menus are slightly see-through: the starfield shows through a little."""
import pygame
import pytest

import story
import story_state as ss
from story import StoryHub, _fill
from test_smoke import run  # noqa: F401  (fixture)

BACK = (200, 60, 60)


def test_a_fill_lets_the_background_through_a_little():
    surf = pygame.Surface((100, 100))
    surf.fill(BACK)
    _fill(surf, (16, 18, 28), pygame.Rect(10, 10, 80, 80), 10)
    px = surf.get_at((50, 50))[:3]
    a = story.MENU_ALPHA / 255.0
    assert px != (16, 18, 28) and px != BACK
    for got, back, fill in zip(px, BACK, (16, 18, 28)):
        assert abs(got - (back * (1 - a) + fill * a)) <= 2
    assert surf.get_at((2, 2))[:3] == BACK and surf.get_at((11, 11))[:3] == BACK     # outside / rounded corner


def test_only_slightly_see_through():
    assert 150 <= story.MENU_ALPHA <= 230          # not a window, not opaque: the text stays easy to read


def test_the_same_fill_always_gives_the_same_picture_and_alpha_is_honoured():
    surf = pygame.Surface((60, 60))
    surf.fill((0, 0, 0))
    _fill(surf, (40, 36, 20), (5, 5, 50, 50), 6)
    once = surf.get_at((30, 30))[:3]
    surf.fill((0, 0, 0))
    _fill(surf, (40, 36, 20), (5, 5, 50, 50), 6)
    assert surf.get_at((30, 30))[:3] == once
    assert _fill(surf, (1, 2, 3), (0, 0, 4, 4), alpha=0) is None
    surf.fill(BACK)
    _fill(surf, (1, 2, 3), (0, 0, 4, 4), alpha=0)
    assert surf.get_at((2, 2))[:3] == BACK                          # alpha 0: nothing painted
    _fill(surf, (1, 2, 3), (0, 0, 4, 4), alpha=255)
    assert surf.get_at((2, 2))[:3] == (1, 2, 3)


def test_two_fills_of_the_same_size_keep_their_own_colour_and_alpha():
    a, b = pygame.Surface((40, 40)), pygame.Surface((40, 40))
    for surf in (a, b):
        surf.fill(BACK)
    _fill(a, (16, 18, 28), (0, 0, 40, 40), 4)
    _fill(b, (40, 36, 20), (0, 0, 40, 40), 4)
    assert a.get_at((20, 20)) != b.get_at((20, 20))
    c = pygame.Surface((40, 40))
    c.fill(BACK)
    _fill(c, (16, 18, 28), (0, 0, 40, 40), 4, alpha=100)
    assert c.get_at((20, 20)) != a.get_at((20, 20))
    d = pygame.Surface((40, 40))
    d.fill(BACK)
    _fill(d, (16, 18, 28), (0, 0, 40, 40), 14)
    assert d.get_at((1, 1))[:3] == BACK and a.get_at((1, 1))[:3] != BACK      # a bigger radius rounds more


def _hub():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["act"] = 2
    st["flags"].update(act2=True, dome_online=True)
    st["credits"] = 1200
    ss.record_result(st, "ch1_sortie", 100, True, {"bird1": 60})
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slots()
    return hub


def _screens(hub):
    """Every adventure screen with a panel background, as a list of (name, setup function)."""
    def slots():
        hub.open_slots()

    def delete():
        hub.open_slots()
        hub.screen = "delete"

    def name():
        hub.open_slots()
        hub.sel = 1
        hub.screen = "name"
        hub.entry = ss.NameEntry()

    def mode():
        hub.open_slots()
        hub.screen = "mode"

    def pane(p, zone="slots"):
        def go():
            hub.open_slot(1)
            hub.pane = p
            hub.zone = zone
        return go

    def paint():
        hub.open_slot(1)
        hub.pane, hub.zone = "hangar", "shop"
        hub.paint_mode = True

    return [("slots", slots), ("delete", delete), ("name", name), ("mode", mode), ("hangar", pane("hangar")),
            ("workshop", pane("hangar", "shop")), ("paint", paint), ("map", pane("map")), ("log", pane("log")),
            ("bestiary", pane("bestiary"))]


def test_no_menu_panel_is_painted_opaque(run):
    """Every filled panel goes through the see-through fill: no plain filled rectangle is drawn on the screen."""
    g = run.game
    hub = _hub()
    real = story.pygame.draw.rect
    solid = []

    def spy(surface, color, rect, width=0, *a, **k):
        if width == 0 and surface.get_size() == (1280, 720):
            solid.append(tuple(color)[:3])
        return real(surface, color, rect, width, *a, **k)

    story.pygame.draw.rect = spy
    try:
        for name, setup in _screens(hub):
            setup()
            solid.clear()
            hub.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
            assert solid == [], (name, solid)
    finally:
        story.pygame.draw.rect = real


@pytest.mark.parametrize("name, point", [("log", (640, 400)), ("workshop", (640, 610)), ("bestiary", (300, 500)),
                                         ("slots", (640, 150))])
def test_the_backdrop_shows_through_the_panels(run, name, point):
    g = run.game
    hub = _hub()
    dict(_screens(hub))[name]()
    surf = pygame.Surface((1280, 720))
    surf.fill(BACK)
    hub.draw(surf, g.font, g.medium_font, g.font)
    px = surf.get_at(point)[:3]
    assert px[0] > 45 and px != BACK                              # a bit of the backdrop, tinted by the panel
    assert px[0] < BACK[0]


def test_the_text_is_still_readable_over_a_bright_backdrop(run):
    """The panel stays dark enough: the light text keeps its contrast even over a pale backdrop."""
    g = run.game
    hub = _hub()
    hub.open_slot(1)
    hub.pane = "log"
    surf = pygame.Surface((1280, 720))
    surf.fill((230, 230, 235))
    hub.draw(surf, g.font, g.medium_font, g.font)
    panel = surf.get_at((900, 500))[:3]
    assert max(panel) < 130                                           # still a dark panel
