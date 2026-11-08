"""Options > GAMEPLAY, Adventure style: the 2D reactor (the ship of a solo arcade game also flies up and down in the
lower third of the screen, like after the BONUS missions of the Adventure)."""

import pygame
import pytest

import highscores
import menu_actions
import user_settings
from i18n import t
from settings import PLAYER_VERTICAL_BOTTOM, PLAYER_VERTICAL_TOP


@pytest.fixture
def game(tmp_path, monkeypatch):
    from game import Game
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(highscores, "HS_FILE", str(tmp_path / "hs.json"))
    g = Game()
    yield g
    g.running = False


def _solo(game, style="adventure", reactor=True):
    game.gameplay_style, game.gp_reactor = style, reactor
    game.play_mode = "solo"
    game.adventure = None
    game._begin_run()
    game.dt = 1 / 60


def test_the_setting_is_kept_and_cleaned():
    assert user_settings.clean_user_settings({})["gp_reactor"] is True
    assert user_settings.clean_user_settings({"gp_reactor": False})["gp_reactor"] is False
    assert user_settings.clean_user_settings({"gp_reactor": "no"})["gp_reactor"] is True


def test_the_row_toggles_only_in_the_adventure_style(game):
    import main_menu
    game.menu_screen = "options"
    game.opt_tab = [n for n, _r in main_menu.OPTION_TABS].index("gameplay")
    game.gameplay_style, game.gp_reactor = "classic", True
    game.menu_index = game._options_spec().index("gp_reactor")
    assert game._option_greyed("gp_reactor") and game._option_label("gp_reactor") == t("opt_gp_reactor")
    menu_actions.menu_adjust(game, 1)
    assert game.gp_reactor is True                                       # (greyed: nothing changes)
    game.gameplay_style = "adventure"
    menu_actions.menu_adjust(game, 1)
    assert game.gp_reactor is False and game._option_value("gp_reactor") == t("no")
    assert user_settings.load_user_settings()["gp_reactor"] is False
    menu_actions.menu_adjust(game, -1)
    assert game.gp_reactor is True and game._option_value("gp_reactor") == t("yes")
    game.draw()


@pytest.mark.parametrize("style, reactor, flies", [("adventure", True, True), ("adventure", False, False),
                                                   ("classic", True, False)])
def test_the_ship_flies_up_and_down_with_the_reactor(game, style, reactor, flies):
    _solo(game, style, reactor)
    p = game.player
    assert (p.vertical_range == (PLAYER_VERTICAL_TOP, PLAYER_VERTICAL_BOTTOM)) is flies
    if not flies:
        assert p.vertical_range is None
        return
    up = pygame.K_UP
    pressed = type("Keys", (), {"__getitem__": lambda self, k: k == up})()
    y = p.y
    for _ in range(120):
        p.update(1 / 60, pressed, "keyboard", None, False)
    assert p.y < y and p.y >= PLAYER_VERTICAL_TOP
