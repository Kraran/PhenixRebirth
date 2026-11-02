"""The menus of the Adventure never show the black hole nor the fantasy ringed planet behind them (the other menus do)."""
import random

import starfield
import story_state as ss
from test_smoke import run  # noqa: F401  (fixture)


def _sky(g, kind, n=200):
    """Put the sky in a state with both things in it, tick it once the way the game does, and say what is left."""
    g.starfield.nebula = starfield.Nebula(filename="galaxy_blackhole.png")
    ring = starfield.Planet()
    ring.filename = "fantasy_rings.png"                  # (what the sky filters on)
    g.starfield.planets = [ring]
    g._tick_stars()
    return g.starfield


def test_the_menus_of_the_adventure_have_neither(run):
    g = run.game
    g.started = False
    g.menu_screen = "story_hub"
    sf = _sky(g, None)
    assert sf.nebula is None
    assert all(getattr(p, "filename", "") != "fantasy_rings.png" for p in sf.planets)
    random.seed(11)
    for _ in range(300):
        sf.nebula = None
        sf.planets = []
        sf.nebula_timer = sf.planet_timer = 0.0
        sf.update(1.0, 0.0)
        assert sf.nebula is None or sf.nebula.kind != "galaxy_blackhole.png"
        assert all(getattr(p, "filename", "") != "fantasy_rings.png" for p in sf.planets)


def test_a_screen_opened_from_the_adventure_too(run):
    g = run.game
    g.started = False
    g.menu_screen = "credits"
    g.story_door = "credits"
    sf = _sky(g, None)
    assert sf.nebula is None


def test_the_other_menus_keep_them(run):
    g = run.game
    g.started = False
    g.story_door = None
    g.menu_screen = "main"
    g.starfield.set_adventure(False)
    sf = _sky(g, None)
    assert sf.nebula is not None and sf.nebula.kind == "galaxy_blackhole.png"
    assert any(getattr(p, "filename", "") == "fantasy_rings.png" for p in sf.planets)
