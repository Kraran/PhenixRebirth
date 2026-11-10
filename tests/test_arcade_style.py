"""Options > GAMEPLAY: the Adventure style of a solo arcade game (src/arcade_style.py): two escort modules (one hit each)
and 0 to 20 antimatter missiles; never saved (the game always starts in the classic style), never a high score."""

import pygame
import pytest

import antimatter
import arcade_style
import highscores
import main_menu
import menu_actions
import user_settings


@pytest.fixture
def game(tmp_path, monkeypatch):
    from game import Game
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(highscores, "HS_FILE", str(tmp_path / "hs.json"))
    g = Game()
    yield g
    g.running = False


def _solo(game, style="adventure", modules=True, missiles=5):
    game.gameplay_style, game.gp_modules, game.gp_missiles = style, modules, missiles
    game.play_mode = "solo"
    game.adventure = None
    game._begin_run()
    game.dt = 1 / 60


# ---------------------------------------------------------------- the options
def test_the_gameplay_tab_and_its_rows():
    names = [name for name, _rows in main_menu.OPTION_TABS]
    assert names == ["game", "gameplay", "audio", "display", "advanced"]
    assert main_menu.tab_rows(names.index("gameplay")) == ["gp_style", "gp_modules", "gp_missiles", "gp_reactor",
                                                         "gp_guardians"]
    assert main_menu.TAB_TITLES["gameplay"] == "opt_tab_gameplay"


def test_the_settings_are_kept_and_cleaned():
    d = user_settings.clean_user_settings({})
    assert "gameplay_style" not in d and d["gp_modules"] is True and d["gp_missiles"] == 5      # (the style: never saved)
    d = user_settings.clean_user_settings({"gameplay_style": "adventure", "gp_modules": False, "gp_missiles": 17})
    assert "gameplay_style" not in d and d["gp_modules"] is False and d["gp_missiles"] == 17
    d = user_settings.clean_user_settings({"gp_modules": "yes", "gp_missiles": 99})
    assert d["gp_modules"] is True and d["gp_missiles"] == 20
    assert user_settings.clean_user_settings({"gp_missiles": True})["gp_missiles"] == 5
    assert user_settings.clean_user_settings({"gp_missiles": -3})["gp_missiles"] == 0


def test_the_game_always_starts_in_the_classic_style(tmp_path, monkeypatch):
    from game import Game
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "s.json"))
    user_settings.save_user_settings({"gameplay_style": "adventure", "gp_modules": False, "gp_missiles": 9})
    g = Game()
    try:
        assert g.gameplay_style == "classic" and g.gp_modules is False and g.gp_missiles == 9
        g.gameplay_style = "adventure"
        g.save_settings()
        assert "gameplay_style" not in user_settings.load_user_settings()
    finally:
        g.running = False


def test_the_rows_change_and_are_greyed_in_the_classic_style(game):
    game.menu_screen = "options"
    game.opt_tab = [n for n, _r in main_menu.OPTION_TABS].index("gameplay")
    game.gameplay_style, game.gp_modules, game.gp_missiles = "classic", True, 5
    spec = game._options_spec()
    assert spec[:5] == ["gp_style", "gp_modules", "gp_missiles", "gp_reactor", "gp_guardians"]
    assert game._option_greyed("gp_modules") and game._option_greyed("gp_missiles") and not game._option_greyed("gp_style")
    game.menu_index = 1
    menu_actions.menu_adjust(game, 1)
    assert game.gp_modules is True                                        # (greyed: nothing changes)
    game.menu_index = 0
    menu_actions.menu_adjust(game, 1)
    assert game.gameplay_style == "adventure" and not game._option_greyed("gp_missiles")
    game.menu_index = 1
    menu_actions.menu_adjust(game, 1)
    assert game.gp_modules is False and game._option_value("gp_modules") == __import__("i18n").t("no")
    game.menu_index = 2
    for want in (6, 7):
        menu_actions.menu_adjust(game, 1)
        assert game.gp_missiles == want and game._option_value("gp_missiles") == str(want)
    game.gp_missiles = 20
    menu_actions.menu_adjust(game, 1)
    assert game.gp_missiles == 0 and game._option_value("gp_missiles") == __import__("i18n").t("no")
    menu_actions.menu_adjust(game, -1)
    assert game.gp_missiles == 20
    saved = user_settings.load_user_settings()
    assert "gameplay_style" not in saved and saved["gp_modules"] is False and saved["gp_missiles"] == 20


def test_the_options_screen_draws_the_tab(game):
    game.menu_screen = "options"
    game.opt_tab = 1
    game.menu_index = 0
    game.gameplay_style = "adventure"
    for i in range(5):
        game.menu_index = i
        game.draw()


# ---------------------------------------------------------------- the game
def test_a_classic_game_has_nothing(game):
    _solo(game, "classic")
    assert not game.arcade_style and game.gyro is None and antimatter._armory(game) is None


def test_an_adventure_style_game_has_its_modules_and_missiles(game):
    _solo(game, "adventure", True, 7)
    assert game.arcade_style
    assert game.gyro is not None and len(game.gyro.modules) == 2 and all(m.hp == 1 for m in game.gyro.modules)
    arm = antimatter._armory(game)
    assert arm is not None and arm.count == 7 and arm.ready
    assert game.player.gun_points is not None                                  # (the modules fire with the ship)
    import gyro
    assert gyro._on(game) is game.gyro                                         # (live: they follow, fire, take hits)
    for _ in range(30):
        game.update()
    assert game.gyro.modules[0].alive and game.gyro.modules[0].x < game.player.x < game.gyro.modules[1].x


def test_the_missiles_go_one_by_one_and_the_hud_counts_them(game):
    _solo(game, "adventure", False, 2)
    assert game.gyro is None
    assert not antimatter.fire(game, game.player)                             # (not while the ship flies in)
    game.stage_transition = None
    p = game.player
    p.y = 625
    labels = []
    game.text_cache = type("TC", (), {"get": staticmethod(lambda font, text, col: labels.append(text)
                                                     or pygame.Surface((10, 10)))})()
    antimatter.draw_hud(game)
    assert labels[-1].startswith("MISSILES ×2")
    assert antimatter.fire(game, p) and game.antimatter.count == 1 and game.antimatter.ready
    assert antimatter.fire(game, p) and game.antimatter.count == 0 and not game.antimatter.ready
    assert not antimatter.fire(game, p)
    antimatter.draw_hud(game)
    assert labels[-1].startswith("MISSILES ×0")


def test_no_missile_and_no_module_when_set_to_none(game):
    _solo(game, "adventure", False, 0)
    assert game.arcade_style and game.gyro is None and antimatter._armory(game) is None


def test_not_in_coop_nor_in_the_demo(game):
    game.gameplay_style, game.play_mode = "adventure", "coop"
    arcade_style.start(game)
    assert not game.arcade_style and game.gyro is None
    game.play_mode, game.attract_mode = "solo", True
    arcade_style.start(game)
    assert not game.arcade_style
    game.attract_mode = False


def test_the_adventure_keeps_its_own_missile(game):
    arm = antimatter.Armory(True)
    assert arm.count == 1 and arm.ready
    assert antimatter.Armory(False).count == 0 and not antimatter.Armory(False).ready


def test_nothing_carries_over_to_the_next_game(game):
    _solo(game, "adventure", True, 3)
    import game_init
    game_init.reset_run(game)
    assert not game.arcade_style and game.gyro is None and game.antimatter is None
    _solo(game, "classic")
    assert not game.arcade_style and game.gyro is None


# ---------------------------------------------------------------- the high scores
def _game_over(game, score):
    game.score = score
    game.player.score = score
    game._begin_highscore_flow()


def test_no_high_score_in_adventure_style(game):
    _solo(game, "adventure", True, 3)
    _game_over(game, 9_999_999)
    assert game.hs_phase == "table"                                           # the table only, no name to enter


def test_the_classic_style_still_enters_its_high_score(game):
    _solo(game, "classic")
    _game_over(game, 9_999_999)
    assert game.hs_phase == "enter"
