"""Main menu with five entries, the arcade game screen, EXTRAS, and the options in four tabs (src/main_menu.py)."""
import pygame
import pytest

import hint_bar
import i18n
import main_menu


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

    def key(self, key, frames=2, mod=0):
        self.game.input_grace = 0.0
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=mod, scancode=0))
        self.frames(frames)

    def button(self, button, frames=2):
        self.game.input_grace = 0.0
        pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=button, joy=0, instance_id=0))
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


def _go(run, name):
    """Move the cursor of the main menu to `name` with the arrows."""
    g = run.game
    while g.menu_index != main_menu.main_index(name):
        run.key(pygame.K_DOWN)


# --- the main menu -------------------------------------------------------------------------------------------------
def test_five_entries_drawn_without_mode_or_difficulty(run):
    g = run.game
    seen = []
    real = g._txt

    def spy(font, text, color, *a, **k):
        seen.append(text)
        return real(font, text, color, *a, **k)

    g._txt = spy
    run.frames(1)
    g._txt = real
    titles = [i18n.t(main_menu.MAIN_TITLES[n]) for n in main_menu.MAIN]
    assert all(x in seen for x in titles)
    assert not any(i18n.t("difficulty") in str(x) or i18n.t("mode") + " :" in str(x) for x in seen)
    assert len(main_menu.MAIN) == 5


def test_the_cursor_wraps_over_five_entries(run):
    g = run.game
    for _ in range(5):
        run.key(pygame.K_DOWN)
    assert g.menu_index == 0
    run.key(pygame.K_UP)
    assert g.menu_index == main_menu.main_index("quit")


# --- PLAY: the arcade game screen ----------------------------------------------------------------------------------
def test_play_opens_the_arcade_screen_then_the_ship_select(run):
    g = run.game
    run.key(pygame.K_RETURN)
    assert g.menu_screen == "arcade" and g.menu_index == 0
    before = g.play_mode
    run.key(pygame.K_RIGHT)
    assert g.play_mode != before
    run.key(pygame.K_DOWN)
    d = g.difficulty
    run.key(pygame.K_LEFT)
    assert g.difficulty != d
    run.key(pygame.K_RETURN, frames=30)                       # any row: on to the ship select (after the fade)
    assert g.menu_screen == "ship_select"
    run.key(pygame.K_ESCAPE)
    assert g.menu_screen == "arcade"                           # the ship select goes back to the arcade screen
    run.key(pygame.K_ESCAPE)
    assert g.menu_screen == "main" and g.menu_index == main_menu.main_index("play")


def test_arcade_screen_explains_the_choices(run):
    g = run.game
    g.menu_screen = "arcade"
    g.difficulty = "veteran"
    seen = []
    real = g._txt

    def spy(font, text, color, *a, **k):
        seen.append(str(text))
        return real(font, text, color, *a, **k)

    g._txt = spy
    run.frames(1)
    g._txt = real
    joined = " ".join(seen)
    assert i18n.t("diff_veteran_d").split()[0] in joined and "Commandant" in joined


# --- EXTRAS ----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["highscores", "achievements", "jukebox", "credits", "help"])
def test_each_extra_opens_and_esc_comes_back_on_its_paragraph(run, name):
    g = run.game
    _go(run, "extras")
    run.key(pygame.K_RETURN)
    assert g.menu_screen == "extras"
    while main_menu.EXTRAS[g.menu_index] != name:
        run.key(pygame.K_DOWN)
    run.key(pygame.K_RETURN)
    assert g.menu_screen == name
    run.key(pygame.K_ESCAPE)
    assert g.menu_screen == "extras" and main_menu.EXTRAS[g.menu_index] == name
    run.key(pygame.K_ESCAPE)
    assert g.menu_screen == "main" and g.menu_index == main_menu.main_index("extras")


def test_pad_b_also_comes_back_to_extras(run):
    g = run.game
    g._open_extra("credits")
    run.button(1)
    assert g.menu_screen == "extras" and main_menu.EXTRAS[g.menu_index] == "credits"


def test_greyed_addon_does_not_open(run, monkeypatch):
    import addon
    monkeypatch.setattr(addon, "addon_ready", lambda: False)
    monkeypatch.setattr(addon, "available_sets", lambda fresh=False: [])
    g = run.game
    g.menu_screen = "extras"
    g.menu_index = main_menu.extras_index("addon")
    assert ("ok", "hint_open") not in hint_bar.menu_items(g)
    run.key(pygame.K_RETURN)
    assert g.menu_screen == "extras"


def test_help_opened_by_hand_stays_and_turns_its_pages(run):
    g = run.game
    g._open_extra("help")
    assert g.help_manual
    run.frames(int(g.HELP_PAGE_SEC * 60) + 30)               # longer than the page timer of the idle help
    assert g.menu_screen == "help" and g.help_page == 0
    run.key(pygame.K_RIGHT)
    assert g.help_page == 1 and g.menu_screen == "help"
    run.key(pygame.K_LEFT)
    assert g.help_page == 0
    assert hint_bar.menu_items(g)[0] == ("lr", "hint_page")
    run.key(pygame.K_RETURN)
    assert g.menu_screen == "extras" and not g.help_manual


def test_scores_left_right_still_go_round_and_esc_returns_to_extras(run):
    g = run.game
    g._open_extra("highscores")
    run.key(pygame.K_RIGHT)
    assert g.menu_screen == "achievements"
    run.key(pygame.K_ESCAPE)
    assert g.menu_screen == "extras" and main_menu.EXTRAS[g.menu_index] == "achievements"


# --- the options in four tabs ----------------------------------------------------------------------------------------
def test_every_option_is_in_exactly_one_tab():
    keys = [k for _n, rows in main_menu.OPTION_TABS for k in rows]
    assert len(keys) == len(set(keys)) == 18
    assert [n for n, _r in main_menu.OPTION_TABS] == ["game", "audio", "display", "advanced"]
    assert main_menu.tab_rows(3)[-1] == "reset_hs"
    for name in main_menu.TAB_TITLES.values():
        assert i18n.T[name]["fr"] and i18n.T[name]["ru"]


def test_tab_keys_and_shoulders_change_the_tab(run):
    g = run.game
    _go(run, "options")
    run.key(pygame.K_RETURN)
    assert g.menu_screen == "options" and g.opt_tab == 0
    run.key(pygame.K_TAB)
    assert g.opt_tab == 1 and g._options_spec() == main_menu.tab_rows(1)
    run.key(pygame.K_TAB, mod=pygame.KMOD_SHIFT)
    assert g.opt_tab == 0
    run.key(pygame.K_PAGEDOWN)
    run.key(pygame.K_PAGEDOWN)
    assert g.opt_tab == 2
    run.button(5)
    assert g.opt_tab == 3
    run.button(4)
    assert g.opt_tab == 2


def test_the_row_of_tabs_takes_the_focus_above_the_first_row(run):
    g = run.game
    g._open_options()
    run.key(pygame.K_UP)
    assert g.menu_index == -1
    assert hint_bar.menu_items(g)[0] == ("lr", "hint_tab")
    run.key(pygame.K_RIGHT)
    assert g.opt_tab == 1 and g.menu_index == -1               # Left / Right change the tab there
    run.key(pygame.K_DOWN)
    assert g.menu_index == 0
    vol = g.sfx_volume
    run.key(pygame.K_LEFT)                                     # and set the value on a row
    assert g.sfx_volume < vol and g.opt_tab == 1


def test_reset_scores_question_comes_back_on_its_row(run):
    g = run.game
    g._open_options()
    g._focus_option("reset_hs")
    assert g.opt_tab == 3
    run.key(pygame.K_RETURN)
    assert g.menu_screen == "reset_confirm"
    run.key(pygame.K_ESCAPE)
    assert g.menu_screen == "options" and g.opt_tab == 3 and g._options_spec()[g.menu_index] == "reset_hs"


def test_bezel_is_greyed_outside_fullscreen(run):
    g = run.game
    g._open_options()
    g._focus_option("bezel")
    g.display_mode = "window"
    style = g.bezel_style
    assert g._option_greyed("bezel") and g._option_value("bezel") == i18n.t("bezel_fullscreen_only")
    run.key(pygame.K_RIGHT)
    assert g.bezel_style == style                              # nothing changes
    assert ("lr", "hint_set") not in hint_bar.menu_items(g)


def test_pause_options_have_the_tabs_too(run):
    g = run.game
    g.play_mode = "solo"
    g._begin_run()
    run.frames(90)                                             # (no pause while the ship flies in)
    run.key(pygame.K_ESCAPE)
    assert g.paused
    run.key(pygame.K_DOWN)
    run.key(pygame.K_RETURN)
    assert g.pause_options and g.menu_screen == "options" and g.opt_tab == 0
    run.key(pygame.K_TAB)
    assert g.opt_tab == 1
    run.key(pygame.K_ESCAPE)
    assert g.paused and not g.pause_options


def test_options_draw_a_gauge_for_the_volumes(run):
    g = run.game
    g._open_options()
    g.opt_tab = 1
    assert g._option_fill("sfx") == pytest.approx(g.sfx_volume)
    assert g._option_fill("audio_mix") is None
    run.frames(2)                                               # draws without error
