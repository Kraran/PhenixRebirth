"""Slide transitions between menu screens (src/menu_fx.py), one title colour, the add-on frames, the achievements
list kept inside its panel."""
import pygame
import pytest

import hint_bar
import i18n
import main_menu
import menu_fx
import menu_ui


class Runner:
    def __init__(self, game):
        self.game = game

    def frames(self, n=1, dt=1 / 60):
        g = self.game
        for _ in range(n):
            g.dt = dt
            g.handle_events()
            g.update()
            g.draw()

    def key(self, key, frames=1, mod=0):
        self.game.input_grace = 0.0
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=mod, scancode=0))
        self.frames(frames)


@pytest.fixture
def run():
    from game import Game

    game = Game()
    game._intro_done = True
    game.fade_phase = None
    game.input_grace = 0.0
    i18n.set_lang("fr")
    r = Runner(game)
    r.frames(2)
    yield r
    game.running = False


def test_going_on_slides_from_the_right_and_back_from_the_left(run):
    g = run.game
    run.key(pygame.K_RETURN)                                   # PLAY: the arcade game screen
    assert g.menu_screen == "arcade" and g._menu_slide and g._menu_slide[0] == 1
    run.frames(int(menu_fx.SLIDE_SEC * 60) + 3)
    assert not g._menu_slide                                   # it ends by itself
    run.key(pygame.K_ESCAPE)
    assert g.menu_screen == "main" and g._menu_slide[0] == -1


def test_moving_in_a_list_does_not_slide(run):
    g = run.game
    run.key(pygame.K_DOWN)
    assert not g._menu_slide


@pytest.mark.parametrize("key,mod,want", [(pygame.K_RIGHT, 0, 1), (pygame.K_LEFT, 0, -1)])
def test_tabs_slide_the_way_of_the_arrow(run, key, mod, want):
    g = run.game
    g._open_extra("highscores")
    run.frames(20)
    run.key(key, mod=mod)
    assert g.menu_screen != "highscores" and g._menu_slide[0] == want


def test_option_tabs_slide(run):
    g = run.game
    g._open_options()
    run.frames(20)
    run.key(pygame.K_TAB)
    assert g.opt_tab == 1 and g._menu_slide[0] == 1
    run.frames(20)
    run.key(pygame.K_TAB, mod=pygame.KMOD_SHIFT)
    assert g.opt_tab == 0 and g._menu_slide[0] == -1


def test_no_slide_in_a_game_or_under_a_fade(run):
    g = run.game
    g.menu_screen = "arcade"
    g.menu_index = 0
    run.frames(20)
    run.key(pygame.K_RETURN)                                   # on to the ship select: a fade, no slide
    assert g.fade_phase and not g._menu_slide
    g.fade_phase = None
    g.play_mode = "solo"
    g._begin_run()
    run.frames(90)
    run.key(pygame.K_ESCAPE)                                   # the pause
    assert g.paused and not g._menu_slide


def test_the_new_screen_moves_and_the_bar_stays(run):
    g = run.game
    g.starfield.draw = lambda surface: None                    # the stars flow behind the see-through bar
    run.key(pygame.K_RETURN)
    first = pygame.Surface.copy(g.screen)
    run.frames(int(menu_fx.SLIDE_SEC * 60) + 3)
    last = pygame.Surface.copy(g.screen)
    band_y = hint_bar.BAND_Y + hint_bar.BAND_H // 2
    row = lambda surf, y: [surf.get_at((x, y))[:3] for x in range(0, 1280, 4)]
    assert row(first, band_y) == row(last, band_y)              # the help bar did not move
    title_y = 60
    assert row(first, title_y) != row(last, title_y)            # the title did


def test_the_sliding_layer_keeps_its_alpha(run):
    """A frame in the middle of a slide shows the new screen (an earlier version lost the layer's alpha)."""
    g = run.game
    run.key(pygame.K_RETURN, frames=4)
    seen = sum(1 for x in range(400, 900, 5) if max(g.screen.get_at((x, 60))[:3]) > 120)
    assert seen > 5


# --- point 11: colours -------------------------------------------------------------------------------------------
def test_one_title_colour_everywhere(run):
    g = run.game
    colours = {}
    real = g._txt

    def spy(font, text, color, *a, **k):
        colours[str(text)] = tuple(color[:3])
        return real(font, text, color, *a, **k)

    g._txt = spy
    try:
        for screen, key in (("options", "options"), ("extras", "extras_title"), ("arcade", "arcade_title"),
                            ("jukebox", "jukebox"), ("highscores", "high_scores")):
            g.menu_screen = screen
            g.menu_index = 0
            run.frames(1)
            assert colours.get(i18n.t(key)) == menu_ui.TITLE, (screen, colours.get(i18n.t(key)))
    finally:
        g._txt = real


def test_red_is_kept_for_what_destroys(run):
    g = run.game
    g._open_options()
    g._focus_option("reset_hs")
    run.key(pygame.K_RETURN)
    colours = {}
    real = g._txt

    def spy(font, text, color, *a, **k):
        colours[str(text)] = tuple(color[:3])
        return real(font, text, color, *a, **k)

    g._txt = spy
    run.frames(1)
    g.menu_screen = "main"
    g.quit_confirm = True
    run.frames(1)
    g._txt = real
    assert colours[i18n.t("reset_hs_title")] == menu_ui.DANGER
    assert colours[i18n.t("quit_game")] == menu_ui.TITLE        # quitting destroys nothing


# --- the add-on frames and the achievements list -----------------------------------------------------------------
def test_addon_list_and_preview_line_up(run, monkeypatch):
    import addon
    monkeypatch.setattr(addon, "available_sets", lambda fresh=False: [("a1", "Game A"), ("b1", "Game B")])
    monkeypatch.setattr(addon, "family_of", lambda sid: sid[0])
    monkeypatch.setattr(addon, "addon_ready", lambda: True)
    g = run.game
    g.menu_screen = "addon"
    g.menu_index = 0
    panels = []
    real = menu_ui.panel

    def spy(surface, rect, *a, **k):
        panels.append(pygame.Rect(rect))
        return real(surface, rect, *a, **k)

    monkeypatch.setattr(menu_ui, "panel", spy)
    g._draw_addon_menu(pygame.Surface((1280, 720)))
    big = [r for r in panels if r.h >= 300]
    assert len(big) == 2
    left, right = sorted(big, key=lambda r: r.x)
    assert left.top == right.top and left.h == right.h            # same top, same height
    assert abs((left.left - 0) - (1280 - right.right)) <= 1       # the pair is centred


def test_achievements_rows_stay_inside_the_panel(run):
    g = run.game
    g.menu_screen = "achievements"
    row_h, top, bottom, max_s = g._ach_view()
    for scroll in (0.0, row_h * 0.5, max_s / 2, max_s):
        g.ach_scroll = scroll
        surf = pygame.Surface((1280, 720))
        surf.fill((1, 2, 3))
        import achievements_screen
        achievements_screen.draw_achievements_inner(g, surf)
        # just above the panel, between the counter and the panel's top edge, nothing from the rows
        for x in list(range(80, 520, 7)) + list(range(760, 1100, 7)):     # (the counter sits in the middle)
            assert surf.get_at((x, top - 4))[:3] == (1, 2, 3), (scroll, x)
