"""Options > GAMEPLAY, Adventure style: the Guardians (a solo arcade game where the Guardians of BONUS FINAL - Gardiens
come with every level, in the same numbers: story_state.endless_guardians, src/guardian.py GuardianSquad)."""

import pygame
import pytest

import arcade_style
import game_init
import highscores
import i18n
import main_menu
import menu_actions
import story_state
import user_settings
from guardian import SQUAD_BOSS_Y, SQUAD_Y, AlphaGuardian, Guardian
from i18n import t
from settings import BASE_HEIGHT


@pytest.fixture
def game(tmp_path, monkeypatch):
    from game import Game
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(highscores, "HS_FILE", str(tmp_path / "hs.json"))
    g = Game()
    yield g
    g.running = False


def _solo(game, style="adventure", guardians=True, mode="solo"):
    game.gameplay_style, game.gp_guardians = style, guardians
    game.play_mode = mode
    game.adventure = None
    game._begin_run()
    game.dt = 1 / 60


def _kinds(game):
    sq = game.guardian_squad
    birds = sq.guardians if sq is not None else []
    return (sum(type(g) is Guardian for g in birds), sum(type(g) is AlphaGuardian for g in birds))


# ---------------------------------------------------------------- the option
def test_the_setting_is_off_by_default_kept_and_cleaned():
    assert user_settings.clean_user_settings({})["gp_guardians"] is False
    assert user_settings.clean_user_settings({"gp_guardians": True})["gp_guardians"] is True
    assert user_settings.clean_user_settings({"gp_guardians": "yes"})["gp_guardians"] is False
    assert user_settings.clean_user_settings({"gp_guardians": 1})["gp_guardians"] is False


def test_the_setting_is_read_when_the_game_starts_and_the_style_is_still_classic(tmp_path, monkeypatch):
    from game import Game
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "s.json"))
    user_settings.save_user_settings({"gp_guardians": True})
    g = Game()
    try:
        assert g.gp_guardians is True and g.gameplay_style == "classic"
    finally:
        g.running = False


def test_the_row_is_the_last_of_the_gameplay_tab_and_toggles_only_in_the_adventure_style(game):
    game.menu_screen = "options"
    game.opt_tab = [n for n, _r in main_menu.OPTION_TABS].index("gameplay")
    game.gameplay_style, game.gp_guardians = "classic", False
    spec = game._options_spec()
    assert spec[-1] == "gp_guardians"
    game.menu_index = spec.index("gp_guardians")
    assert game._option_greyed("gp_guardians") and game._option_label("gp_guardians") == t("opt_gp_guardians")
    assert game._option_value("gp_guardians") == t("no")
    menu_actions.menu_adjust(game, 1)
    assert game.gp_guardians is False                                    # (greyed: nothing changes)
    game.gameplay_style = "adventure"
    assert not game._option_greyed("gp_guardians")
    menu_actions.menu_adjust(game, 1)
    assert game.gp_guardians is True and game._option_value("gp_guardians") == t("yes")
    assert user_settings.load_user_settings()["gp_guardians"] is True
    menu_actions.menu_adjust(game, -1)
    assert game.gp_guardians is False and user_settings.load_user_settings()["gp_guardians"] is False
    game.draw()


def test_the_texts_are_in_every_language_and_fit_the_options_screen(game):
    import draw_frame
    game.menu_screen = "options"
    game.opt_tab = [n for n, _r in main_menu.OPTION_TABS].index("gameplay")
    game.gameplay_style = "adventure"
    old = i18n.get_lang()
    try:
        for code in i18n.LANG_CODES:
            for key in ("opt_gp_guardians", "opt_help_gp_guardians"):
                assert i18n.T[key].get(code), (key, code)
                assert "{" not in i18n.T[key][code]                         # (no placeholder: plain texts)
            i18n.set_lang(code)
            game._opt_help_cache = {}
            label = game.font.size(t("opt_gp_guardians"))[0]
            value = max(game.font.size(t("yes"))[0], game.font.size(t("no"))[0])
            assert 28 + label + 24 + draw_frame.ARROW_ROOM + value + 28 <= 600, code      # (the row of the box)
            lines = game._wrap_ui(t("opt_help_gp_guardians"), game.body_font or game.font, 520 - 36)
            top = 60 + 60 + 120                                            # (the box under the tabs, generously)
            assert top + 58 + len(lines) * (game.body_font.get_linesize() + 4) + 14 <= BASE_HEIGHT, code
            game.menu_index = game._options_spec().index("gp_guardians")
            game.draw()
    finally:
        i18n.set_lang(old)


# ---------------------------------------------------------------- the game
def test_the_guardians_come_as_in_the_final_bonus(game):
    _solo(game)
    assert game.arcade_style and game.arcade_guardians and arcade_style.guardians(game)
    assert game.stage == 1 and _kinds(game) == story_state.endless_guardians(1) == (1, 0)
    assert game.guardian_squad.guardians[0].home_y == SQUAD_Y
    for stage in (2, 4, 5, 6, 10, 11, 16):
        game.stage = stage
        game._setup_stage(stage)
        assert _kinds(game) == story_state.endless_guardians(stage), stage
    game.stage = 5
    game._setup_stage(5)
    assert game.boss_saucer is not None                                  # a boss level: the Guardians below its saucer
    assert all(g.home_y == SQUAD_BOSS_Y for g in game.guardian_squad.guardians)


def test_the_guardians_fly_in_and_hold_the_end_of_the_level(game):
    _solo(game)
    game.player.infinite_lives = True
    for _ in range(240):
        game.update()
    sq = game.guardian_squad
    assert sq is not None and sq.targets()                               # (come down from the top: they can be shot)
    for e in game.formation.enemies:
        e.alive = False
    import update_play
    assert not update_play.squad_clear(game)                             # the level waits for the Guardians too
    sq.kill_all()
    assert update_play.squad_clear(game)


def test_the_next_level_brings_its_guardians(game):
    _solo(game)
    import update_play
    game.stage_transition = "fly_up"
    for ship in game._ships():
        ship.y = -200
    update_play.tick_fly_up(game)
    assert game.stage == 2 and _kinds(game) == (2, 0)


@pytest.mark.parametrize("style, on", [("classic", True), ("adventure", False)])
def test_no_guardian_without_the_option_or_in_the_classic_style(game, style, on):
    _solo(game, style, on)
    assert game.guardian_squad is None and not arcade_style.guardians(game)
    game.stage = 6
    game._setup_stage(6)
    assert game.guardian_squad is None


@pytest.mark.parametrize("mode", ["coop", "hotseat"])
def test_not_in_the_two_player_games(game, mode):
    _solo(game, "adventure", True, mode)
    assert not getattr(game, "arcade_guardians", False) and game.guardian_squad is None


def test_not_in_the_demo(game):
    game.gameplay_style, game.gp_guardians = "adventure", True
    game.play_mode, game.attract_mode = "solo", True
    arcade_style.start(game)
    assert not game.arcade_guardians
    game.attract_mode = False


def test_the_demo_after_a_game_has_no_guardian(game):
    _solo(game)
    game_init.reset_run(game)
    assert not game.arcade_guardians and game.guardian_squad is None
    game.attract_mode = True
    game._setup_stage(3)
    assert game.guardian_squad is None
    game.attract_mode = False


def test_the_adventure_keeps_its_own_guardians(game):
    _solo(game)
    game.adventure = {"guardians_at": {3: 2}}                            # (a mission: its plan, not the option's)
    game.stage = 3
    game._setup_stage(3)
    assert _kinds(game) == (2, 0)
    game.stage = 4
    game._setup_stage(4)
    assert game.guardian_squad is None


def test_no_high_score_with_the_guardians(game):
    _solo(game)
    game.score = game.player.score = 9_999_999
    game._begin_highscore_flow()
    assert game.hs_phase == "table"
