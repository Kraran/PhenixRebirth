"""The pause menu has a fourth row, "Help / Controls", that opens the two help pages over the paused run."""
import pygame
import pytest

import help_screen
import hint_bar
import i18n
import main_menu
from i18n import LANG_CODES, set_lang, t
from test_smoke import run  # noqa: F401  (fixture)

RESUME, OPTIONS, HELP, QUIT = 0, 1, 2, 3


@pytest.fixture(autouse=True)
def _french_again():
    yield
    set_lang("fr")


def _key(run, key, frames=2):
    g = run.game
    g.input_grace = 0.0
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0, scancode=0))
    run.frames(frames)


def _button(run, button, frames=2):
    run.game.input_grace = 0.0
    pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=button, joy=0, instance_id=0))
    run.frames(frames)


def _hat(run, value):
    run.game.input_grace = 0.0
    pygame.event.post(pygame.event.Event(pygame.JOYHATMOTION, joy=0, instance_id=0, hat=0, value=value))
    run.frames(2)
    pygame.event.post(pygame.event.Event(pygame.JOYHATMOTION, joy=0, instance_id=0, hat=0, value=(0, 0)))
    run.frames(2)


@pytest.fixture
def paused(run):
    g = run.game
    g.play_mode = "solo"
    g._begin_run()
    run.frames(30)
    g.stage_transition = None
    g.input_grace = 0.0
    _key(run, pygame.K_ESCAPE)
    assert g.paused and g.pause_index == 0 and not g.pause_help
    return run


def test_the_pause_menu_has_four_rows_with_the_help_third():
    assert main_menu.PAUSE == ("resume", "options", "help", "quit")
    assert [main_menu.PAUSE_TITLES[n] for n in main_menu.PAUSE] == ["resume", "options", "pause_help", "quit_run"]
    assert t("pause_help") == "AIDE / COMMANDES"
    set_lang("en")
    assert t("pause_help") == "HELP / CONTROLS"


def test_the_rows_are_drawn(paused):
    g = paused.game
    seen = []
    real = g._txt

    def spy(font, text, color, *a, **k):
        seen.append(text)
        return real(font, text, color, *a, **k)

    g._txt = spy
    try:
        paused.frames(1)
    finally:
        g._txt = real
    for key in ("resume", "options", "pause_help", "quit_run"):
        assert t(key) in seen, key


def test_the_cursor_goes_round_the_four_rows(paused):
    g = paused.game
    _key(paused, pygame.K_UP)
    assert g.pause_index == QUIT
    _key(paused, pygame.K_DOWN)
    assert g.pause_index == RESUME
    for expected in (OPTIONS, HELP, QUIT, RESUME):
        _key(paused, pygame.K_DOWN)
        assert g.pause_index == expected


def test_enter_on_help_opens_the_help_and_esc_comes_back_to_the_pause_menu(paused):
    g = paused.game
    g.pause_index = HELP
    _key(paused, pygame.K_RETURN)
    assert g.paused and g.pause_help and g.help_page == 0
    paused.frames(3)
    _key(paused, pygame.K_ESCAPE)
    assert g.paused and not g.pause_help and g.pause_index == HELP        # the pause menu, on the same row
    _key(paused, pygame.K_ESCAPE)
    assert not g.paused                                                   # a second Esc resumes the game


def test_the_arrows_turn_the_pages_and_enter_comes_back(paused):
    g = paused.game
    g.pause_index = HELP
    _key(paused, pygame.K_RETURN)
    _key(paused, pygame.K_RIGHT)
    assert g.help_page == 1
    _key(paused, pygame.K_LEFT)
    assert g.help_page == 0
    _key(paused, pygame.K_DOWN)
    assert g.help_page == 1
    _key(paused, pygame.K_UP)
    assert g.help_page == 0
    _key(paused, pygame.K_RETURN)
    assert g.paused and not g.pause_help


def test_the_help_page_is_drawn_over_the_paused_game_with_its_page_label(paused):
    g = paused.game
    g.pause_index = HELP
    _key(paused, pygame.K_RETURN)
    seen = []
    real = g._txt

    def spy(font, text, color, *a, **k):
        seen.append(text)
        return real(font, text, color, *a, **k)

    g._txt = spy
    try:
        paused.frames(1)
        page_one = list(seen)
        seen.clear()
        _key(paused, pygame.K_RIGHT, frames=1)
    finally:
        g._txt = real
    assert i18n.t_help("scenario_h") in page_one and i18n.t_help("controls_h") in page_one      # page 1 of the help
    assert help_screen.help_tip() in seen and i18n.t_help("scenario_h") not in seen              # page 2 of the help
    seen.extend(page_one)
    assert "%s 1/2" % i18n.t_help("help_page") in seen and "%s 2/2" % i18n.t_help("help_page") in seen
    assert hint_bar.menu_items(g) == [("lr", "hint_page"), hint_bar.BACK]


def test_the_other_rows_still_work(paused):
    g = paused.game
    g.pause_index = OPTIONS
    _key(paused, pygame.K_RETURN)
    assert g.pause_options and not g.pause_help
    _key(paused, pygame.K_ESCAPE)
    assert g.paused and not g.pause_options
    g.pause_index = RESUME
    _key(paused, pygame.K_RETURN)
    assert not g.paused


def test_the_last_row_still_quits_the_run(paused):
    g = paused.game
    g.pause_index = QUIT
    _key(paused, pygame.K_RETURN)
    assert not g.started and not g.paused and not g.pause_help


def test_the_pad_opens_the_help_turns_pages_and_comes_back(paused):
    g = paused.game
    _hat(paused, (0, -1))                      # down
    _hat(paused, (0, -1))
    assert g.pause_index == HELP
    _button(paused, 0)                         # A
    assert g.pause_help
    _hat(paused, (1, 0))
    assert g.help_page == 1
    _button(paused, 4)                         # LB: the other page
    assert g.help_page == 0
    _button(paused, 5)
    assert g.help_page == 1
    _button(paused, 1)                         # B
    assert g.paused and not g.pause_help


def test_the_stick_turns_the_pages(paused):
    g = paused.game
    g.pause_index = HELP
    _key(paused, pygame.K_RETURN)
    g._joy_menu_cooldown = 0.0
    g.input_grace = 0.0
    pygame.event.post(pygame.event.Event(pygame.JOYAXISMOTION, joy=0, instance_id=0, axis=0, value=0.9))
    paused.frames(2)
    assert g.help_page == 1
    pygame.event.post(pygame.event.Event(pygame.JOYAXISMOTION, joy=0, instance_id=0, axis=0, value=0.0))
    paused.frames(2)
    g._joy_menu_cooldown = 0.0
    pygame.event.post(pygame.event.Event(pygame.JOYAXISMOTION, joy=0, instance_id=0, axis=0, value=-0.9))
    paused.frames(2)
    assert g.help_page == 0


def test_pausing_again_never_starts_on_the_help(paused):
    g = paused.game
    g.pause_index = HELP
    _key(paused, pygame.K_RETURN)
    g._toggle_pause()                           # the pause button (Start) while the help is open: resume
    assert not g.paused and not g.pause_help
    g._toggle_pause()
    assert g.paused and not g.pause_help and g.pause_index == 0


def test_the_help_keeps_its_ships_moving_while_paused(paused):
    g = paused.game
    g.pause_index = HELP
    _key(paused, pygame.K_RETURN)
    before = g.help_anim_t
    paused.frames(10)
    assert g.help_anim_t > before


@pytest.mark.parametrize("lang", LANG_CODES)
def test_the_row_and_the_help_draw_in_every_language(paused, lang):
    g = paused.game
    set_lang(lang)
    g.text_cache.clear()
    label = t("pause_help")
    assert label and label != "pause_help"
    paused.frames(2)
    assert g.medium_font.size(label)[0] < 640
    g.pause_index = HELP
    _key(paused, pygame.K_RETURN)
    paused.frames(2)
    _key(paused, pygame.K_RIGHT)
    paused.frames(2)
    assert g.pause_help
