"""The announcements are beneath every enemy, including the boss, and its shots.

In a plain run the banner is drawn once before the enemies; under an overlay
(pause, game over, hot-seat hand-off) and in the menus it is still drawn last, over everything."""
import pygame

import draw_frame
from settings import BASE_HEIGHT, BASE_WIDTH
from test_smoke import run  # noqa: F401  (fixture)

CENTER = (BASE_WIDTH // 2, BASE_HEIGHT // 2)
BLUE, RED = (20, 60, 220), (220, 20, 20)


class Painter:
    """Stands for the saucer, or for the formation: draws a plate of one colour on the middle of the screen."""

    def __init__(self, events, name, colour, size=(520, 140)):
        self.events, self.name, self.colour, self.size = events, name, colour, size

    def draw(self, surface):
        self.events.append(self.name)
        r = pygame.Rect((0, 0), self.size)
        r.center = CENTER
        surface.fill(self.colour, r)


def _play(run):
    g = run.game
    g.play_mode = "solo"
    g._begin_run()
    run.frames(3)
    g.scanlines = 0
    g.cheat_msg, g.cheat_kind, g.cheat_msg_timer = "1UP !", "1up", 3.0
    return g


def _spy(g, formation=True):
    """Replaces the saucer, the formation and the banner by recorders; returns the list of events."""
    events = []
    g.boss_saucer = Painter(events, "saucer", BLUE)
    if formation:
        g.formation.draw = Painter(events, "aliens", RED, size=(40, 40)).draw
    g._draw_cheat_message = lambda: events.append("banner")
    return events


def test_the_banner_is_under_the_saucer_and_the_aliens(run):
    g = _play(run)
    events = _spy(g)
    g._draw_canvas()
    assert events.count("banner") == 1                      # a single translucent copy, under every enemy
    assert events[0] == "banner"
    assert events.index("aliens") > max(i for i, e in enumerate(events) if e == "banner")
    assert events == ["banner", "saucer", "aliens"]


def test_birds_and_saucer_are_seen_in_front_of_the_banner(run):
    g = _play(run)
    events = []
    g.boss_saucer = Painter(events, "saucer", BLUE)
    g.formation.draw = Painter(events, "aliens", RED, size=(40, 40)).draw
    g._draw_canvas()
    surf = g.game_surface
    assert tuple(surf.get_at(CENTER))[:3] == RED            # the alien, in front of the text of the banner
    with_banner = [tuple(surf.get_at((CENTER[0] + dx, CENTER[1])))[:3] for dx in range(-60, 61, 6)
                   if abs(dx) > 25]
    g.cheat_msg_timer = 0.0
    g._draw_canvas()
    assert tuple(surf.get_at(CENTER))[:3] == RED
    without = [tuple(surf.get_at((CENTER[0] + dx, CENTER[1])))[:3] for dx in range(-60, 61, 6) if abs(dx) > 25]
    assert all(c == BLUE for c in without)                  # no banner: the saucer plate alone
    assert with_banner == without                           # the saucer is now above the banner too


def test_under_an_overlay_the_banner_stays_on_top(run):
    g = _play(run)
    events = _spy(g)
    g._draw_canvas()                                        # a plain frame first (the flag is set...)
    g.hs_phase = "card"                                     # (game over with its card: the scene is drawn under it)
    for state in ("paused", "game_over", "hotseat_wait"):
        setattr(g, state, True)
        if state == "paused":
            g.pause_index = 0
        events.clear()
        try:
            g._draw_canvas()
        finally:
            setattr(g, state, False)
        assert events[-1] == "banner", state                # ...and it must not hide the toast of the next one
        assert events.count("banner") == 2, state           # one under the overlay, one over: as before


def test_in_the_menus_the_banner_is_drawn_once_and_last(run):
    g = run.game
    g.cheat_msg, g.cheat_kind, g.cheat_msg_timer = "CODE", "live", 3.0
    events = []
    g._draw_cheat_message = lambda: events.append("banner")
    g._draw_canvas()
    assert events == ["banner"]


def test_scene_overlaid(run):
    g = run.game
    g.game_over = g.paused = g.hotseat_wait = False
    assert not draw_frame.scene_overlaid(g)
    for state in ("paused", "game_over", "hotseat_wait"):
        setattr(g, state, True)
        assert draw_frame.scene_overlaid(g), state
        setattr(g, state, False)
