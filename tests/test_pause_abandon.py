"""In an Adventure mission the last row of the pause menu is "ABANDON MISSION" and it asks before leaving
(NO is lit first). The arcade run keeps "QUIT RUN", without a question."""
import pygame
import pytest

import hint_bar
import main_menu
import story_state as ss
from i18n import LANG_CODES, set_lang, t
from test_smoke import run  # noqa: F401  (fixture)

RESUME, OPTIONS, HELP, QUIT = 0, 1, 2, 3
YES, NO = 0, 1


@pytest.fixture(autouse=True)
def _french_again():
    yield
    set_lang("fr")


def _key(run, key, frames=2):
    run.game.input_grace = 0.0
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


def _mission(run):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    st["credits"] = 1000
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = 0
    g._begin_adventure(g.story._launch_selected())
    run.frames(30)
    g.stage_transition = None
    g.input_grace = 0.0
    return run


@pytest.fixture
def adv_paused(run):
    _mission(run)
    g = run.game
    _key(run, pygame.K_ESCAPE)
    assert g.paused and g.adventure and not g.pause_abandon
    g.pause_index = QUIT
    return run


@pytest.fixture
def arcade_paused(run):
    g = run.game
    g.play_mode = "solo"
    g._begin_run()
    run.frames(30)
    g.stage_transition = None
    g.input_grace = 0.0
    _key(run, pygame.K_ESCAPE)
    assert g.paused and not getattr(g, "adventure", None)
    g.pause_index = QUIT
    return run


def test_the_row_is_named_by_the_mode():
    assert main_menu.pause_title("quit", adventure=True) == "pause_abandon"
    assert main_menu.pause_title("quit", adventure=False) == "quit_run"
    assert main_menu.pause_title("help", adventure=True) == "pause_help"        # only the last row changes
    assert t("pause_abandon") == "ABANDONNER LA MISSION"
    set_lang("en")
    assert t("pause_abandon") == "ABANDON MISSION"


def test_the_adventure_row_is_drawn(adv_paused):
    g = adv_paused.game
    seen = []
    real = g._txt

    def spy(font, text, color, *a, **k):
        seen.append(text)
        return real(font, text, color, *a, **k)

    g._txt = spy
    try:
        adv_paused.frames(1)
    finally:
        g._txt = real
    assert t("pause_abandon") in seen and t("quit_run") not in seen


def test_enter_on_the_row_asks_first_and_no_is_lit(adv_paused):
    g = adv_paused.game
    _key(adv_paused, pygame.K_RETURN)
    assert g.started and g.paused and g.pause_abandon and g.abandon_index == NO
    assert hint_bar.menu_items(g) == hint_bar.QUESTION


def test_enter_on_no_stays_in_the_mission(adv_paused):
    g = adv_paused.game
    _key(adv_paused, pygame.K_RETURN)
    _key(adv_paused, pygame.K_RETURN)                                  # NO
    assert g.started and g.paused and not g.pause_abandon and g.pause_index == QUIT and g.adventure


def test_esc_is_no_and_a_second_esc_resumes(adv_paused):
    g = adv_paused.game
    _key(adv_paused, pygame.K_RETURN)
    _key(adv_paused, pygame.K_ESCAPE)
    assert g.started and g.paused and not g.pause_abandon
    _key(adv_paused, pygame.K_ESCAPE)
    assert g.started and not g.paused


@pytest.mark.parametrize("move", [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT])
def test_the_arrows_switch_the_answer_and_yes_leaves(adv_paused, move):
    g = adv_paused.game
    _key(adv_paused, pygame.K_RETURN)
    _key(adv_paused, move)
    assert g.abandon_index == YES
    _key(adv_paused, move)
    assert g.abandon_index == NO
    _key(adv_paused, move)
    _key(adv_paused, pygame.K_RETURN)                                  # YES
    assert not g.started and not g.paused and not g.pause_abandon and not g.adventure
    assert g.menu_screen == "story_hub" and g.story.state["credits"] == 1000      # nothing gained, nothing lost


def test_the_question_is_drawn(adv_paused):
    g = adv_paused.game
    _key(adv_paused, pygame.K_RETURN)
    seen = []
    real = g._txt

    def spy(font, text, color, *a, **k):
        seen.append(text)
        return real(font, text, color, *a, **k)

    g._txt = spy
    try:
        adv_paused.frames(1)
    finally:
        g._txt = real
    assert t("abandon_title") in seen and t("abandon_q") in seen and t("yes_u") in seen and t("no_u") in seen


def test_the_pad_answers(adv_paused):
    g = adv_paused.game
    _button(adv_paused, 0)                                             # A on the row
    assert g.pause_abandon and g.abandon_index == NO
    _button(adv_paused, 1)                                             # B: NO
    assert g.started and g.paused and not g.pause_abandon
    _button(adv_paused, 0)
    _hat(adv_paused, (0, 1))                                           # D-pad: the other answer
    assert g.abandon_index == YES
    _button(adv_paused, 0)                                             # A on YES
    assert not g.started and not g.adventure


def test_the_stick_switches_the_answer(adv_paused):
    g = adv_paused.game
    _key(adv_paused, pygame.K_RETURN)
    g._joy_menu_cooldown = 0.0
    pygame.event.post(pygame.event.Event(pygame.JOYAXISMOTION, joy=0, instance_id=0, axis=1, value=-0.9))
    adv_paused.frames(2)
    assert g.abandon_index == YES


def test_the_pause_button_resumes_and_the_question_does_not_come_back(adv_paused):
    g = adv_paused.game
    _key(adv_paused, pygame.K_RETURN)
    g._toggle_pause()
    assert not g.paused and not g.pause_abandon
    g._toggle_pause()
    assert g.paused and not g.pause_abandon


def test_the_arcade_run_still_quits_at_once(arcade_paused):
    g = arcade_paused.game
    _key(arcade_paused, pygame.K_RETURN)
    assert not g.started and not g.paused and not g.pause_abandon


@pytest.mark.parametrize("lang", LANG_CODES)
def test_the_texts_exist_in_every_language(adv_paused, lang):
    g = adv_paused.game
    set_lang(lang)
    for key in ("pause_abandon", "abandon_title", "abandon_q"):
        assert t(key) and t(key) != key
    adv_paused.frames(1)
    _key(adv_paused, pygame.K_RETURN)
    adv_paused.frames(1)
    assert g.pause_abandon
