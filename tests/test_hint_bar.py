"""Help bar (src/hint_bar.py), lit frame and panels (src/menu_ui.py), French texts of the classic menus."""
import pygame
import pytest

import hint_bar
import i18n
import menu_ui
from settings import BASE_HEIGHT, BASE_WIDTH


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


@pytest.fixture
def run():
    from game import Game

    game = Game()
    game._intro_done = True
    game.fade_phase = None
    i18n.set_lang("fr")
    yield Runner(game)
    game.running = False
    i18n.set_lang("fr")


SCREENS = ["main", "options", "help", "ship_select", "highscores", "achievements", "jukebox", "addon", "reset_confirm"]


@pytest.mark.parametrize("screen", SCREENS)
def test_every_classic_menu_has_a_bar(run, screen):
    g = run.game
    g.menu_screen = screen
    g.menu_index = 0
    items = hint_bar.menu_items(g)
    assert items, screen
    for kind, label in items:
        assert kind in (None, "ud", "lr", "l", "r", "ok", "back")
        assert i18n.t(label) != label, label                  # a real text, not a raw key
    drawn = []
    real = hint_bar.draw

    def spy(game, surface, its, right=None, lit=None):
        drawn.append(list(its))
        return real(game, surface, its, right=right, lit=lit)

    hint_bar.draw = spy
    try:
        run.frames(3)
    finally:
        hint_bar.draw = real
    assert drawn and drawn[-1] == items, screen


def test_the_bar_is_at_the_bottom_on_every_screen(run):
    g = run.game
    run.frames(3)
    band = g.screen.get_at((5, BASE_HEIGHT - 2))
    line = g.screen.get_at((5, hint_bar.BAND_Y))
    assert line[:3] != band[:3]                                # the thin line on top of the band
    assert hint_bar.BAND_Y == BASE_HEIGHT - hint_bar.BAND_H


def test_main_menu_items_follow_the_cursor(run, monkeypatch):
    import addon
    g = run.game
    g.menu_screen = "main"
    g.menu_index = 0
    assert ("ok", "hint_ok") in hint_bar.menu_items(g)
    g.menu_index = 3                                           # MODE: set with Left / Right
    assert ("lr", "hint_change") in hint_bar.menu_items(g)
    assert ("ok", "hint_ok") not in hint_bar.menu_items(g)
    monkeypatch.setattr(addon, "addon_ready", lambda: False)
    g.menu_index = 2                                           # greyed ADD-ON: nothing to validate
    assert ("ok", "hint_ok") not in hint_bar.menu_items(g)
    assert hint_bar.menu_items(g)[-1] == ("back", "hint_quit")


def test_pause_and_questions(run):
    g = run.game
    g.quit_confirm = True
    assert hint_bar.menu_items(g) == hint_bar.QUESTION
    g.quit_confirm = False
    g.play_mode = "solo"
    g._begin_run()
    run.frames(10)
    assert hint_bar.menu_items(g) is None                     # no bar while playing
    g.paused = True
    assert hint_bar.menu_items(g)[-1] == ("back", "hint_resume")


def test_jukebox_from_the_adventure_has_no_tabs(run):
    g = run.game
    g.menu_screen = "jukebox"
    assert any(k == "l" for k, _ in hint_bar.menu_items(g))
    g.story_door = "jukebox"
    assert not any(k in ("l", "r") for k, _ in hint_bar.menu_items(g))


def test_buttons_follow_the_last_device(run):
    g = run.game
    g.gamepad_detected = True
    g.last_input_pad = False
    assert not hint_bar.device_is_pad(g)
    pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=5, joy=0, instance_id=0))
    run.frames(1)
    g.gamepad_detected = True
    assert g.last_input_pad and hint_bar.device_is_pad(g)
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11, unicode="", mod=0, scancode=0))
    run.frames(1)
    assert not g.last_input_pad and not hint_bar.device_is_pad(g)
    g.last_input_pad = True
    g.gamepad_detected = False                                 # unplugged: back to the keys
    assert not hint_bar.device_is_pad(g)


def test_a_resting_stick_does_not_switch_to_the_pad(run):
    g = run.game
    g.last_input_pad = False
    pygame.event.post(pygame.event.Event(pygame.JOYAXISMOTION, axis=0, value=0.05, joy=0, instance_id=0))
    run.frames(1)
    assert g.last_input_pad is False


def test_keyboard_and_pad_bars_differ():
    pygame.init()
    items = [("ud", "hint_nav"), ("ok", "hint_ok"), ("back", "hint_back")]
    kb = hint_bar.render(items, pad=False)
    pad = hint_bar.render(items, pad=True)
    assert kb.get_width() != pad.get_width()                    # ENTRÉE / ÉCHAP keycaps are wider than A / B


def test_pad_notice_when_plugged_and_unplugged(run):
    g = run.game
    g.gamepad_detected = False
    run.frames(2)
    assert not getattr(g, "_hint_pad_notice", None)
    g.gamepad_detected = True
    hint_bar.note_pad(g)
    assert g._hint_pad_notice[0] == "pad_notice_on"
    g.gamepad_detected = False
    hint_bar.note_pad(g)
    assert g._hint_pad_notice[0] == "pad_notice_off"
    for _ in range(int(hint_bar.NOTICE_SEC * 60) + 5):
        g.dt = 1 / 60
        hint_bar.draw_pad_notice(g, pygame.Surface((BASE_WIDTH, BASE_HEIGHT)))
    assert g._hint_pad_notice is None                         # it goes away by itself


def test_no_gamepad_line_on_the_main_menu_any_more(run):
    g = run.game
    seen = []
    real = g._txt

    def spy(font, text, color, *a, **k):
        seen.append(text)
        return real(font, text, color, *a, **k)

    g._txt = spy
    run.frames(2)
    g._txt = real
    assert i18n.t("gamepad_none") not in seen and i18n.t("press_confirm") not in seen


def test_the_chosen_row_does_not_move(run):
    """No '> ' in front of the chosen row: only the lit frame moves."""
    g = run.game
    labels = {}
    real = g._txt
    for idx in range(9):
        g.menu_index = idx
        seen = []

        def spy(font, text, color, *a, **k):
            seen.append(text)
            return real(font, text, color, *a, **k)

        g._txt = spy
        run.frames(1)
        g._txt = real
        assert not any(str(s).startswith("> ") for s in seen), seen
        labels[idx] = [s for s in seen if s in (i18n.t("play"), i18n.t("options"))]
    assert all(v == labels[0] for v in labels.values())


def test_draw_rows_keeps_one_width_and_returns_the_panel():
    pygame.init()
    font = pygame.font.SysFont("dejavusans", 22, bold=True)

    class G:
        def _txt(self, f, text, col):
            return f.render(text, True, col)

    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    box = menu_ui.draw_rows(G(), surf, font, ["A", "LONGER LINE"], 100, 30, 0)
    assert box.width > font.size("LONGER LINE")[0]
    assert box.top < 100 and box.bottom > 130
    lit = surf.get_at((box.centerx, 100 + 2))
    assert lit[:3] != surf.get_at((box.centerx, 130 + 2))[:3]     # the frame is on the first row only


def test_french_menu_texts_have_their_accents():
    i18n.set_lang("fr")
    try:
        assert i18n.t("difficulty") == "DIFFICULTÉ"
        assert i18n.t("credits") == "CRÉDITS"
        assert i18n.t("opt_control") == "Contrôle"
        assert i18n.t("subtitle") != i18n.T["subtitle"]["en"]          # the subtitle is French in French
        assert "défaut" in i18n.t("opt_help_control")
        assert i18n.t_help("controls_h") == "CONTRÔLES"
        for key in ("ach_locked", "disp_window", "diff_veteran", "juke_intro"):
            assert any(c in i18n.t(key) for c in "éèêà"), key
    finally:
        i18n.set_lang("fr")


def test_hint_texts_in_every_language():
    for key, texts in i18n._MENU_HINTS.items():
        assert len(texts) == len(i18n.LANG_CODES), key
        assert all(str(x).strip() for x in texts), key
