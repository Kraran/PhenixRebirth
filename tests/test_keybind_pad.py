"""The "Gamepad" tab of the screen "Keys and buttons" (src/keybind_pad.py): the drawn pad, the cards, the switch "same
buttons for every gamepad", the copy, the defaults, and the buttons pressed to set an action."""
import json

import pygame
import pytest

import bindings
import controls
import keybind_pad as kp
import keybind_screen as ks
import user_settings
from i18n import LANG_CODES, set_lang, t
from test_controls import bench  # noqa: F401  (fixture)
from test_keybinds import _own_settings, run, settled  # noqa: F401  (fixtures and helper)


def open_pad_tab(run):
    g = run.game
    g._open_options()
    ks.open_screen(g)
    st = g.keybind
    st.grace = 0.0
    st.tab = 2
    st.row = st.col = 0
    run.frames(2)
    return st


def pads(run, bench, count=2):                                               # noqa: F811
    ids = [bench.plug() for _ in range(count)]
    controls.sync_game(run.game)                                              # the game finds them
    run.frames(2)
    assert len(run.game.pads.pads) == count
    return ids


def to_row(run, st, name):
    for _ in range(len(kp.rows())):
        if kp.rows()[st.row] == name:
            return
        run.key(pygame.K_DOWN, frames=1)
    assert kp.rows()[st.row] == name


def begin(run, st, action, bench_ready=True):
    to_row(run, st, action)
    run.key(pygame.K_RETURN, frames=1)
    settled(run)


# ------------------------------------------------------------------------------------------------ the tab
def test_the_third_tab_is_the_gamepad_and_the_rows_follow_the_switch(run):
    st = open_pad_tab(run)
    assert ks.TABS[2] == bindings.PAD and st.is_pad
    assert kp.rows() == ("fire", "phenix", "missile", "pause", "shared", "defaults", "back")       # no copy while they share
    bindings.current.set_shared(False)
    assert kp.rows() == ("fire", "phenix", "missile", "pause", "shared", "copy", "defaults", "back")


def test_entering_and_leaving_the_gamepad_tab_starts_on_its_first_row(run):
    st = ks.open_screen(run.game) or run.game.keybind
    settled(run)
    st.row, st.col = 4, 1
    run.key(pygame.K_TAB, frames=1)
    run.key(pygame.K_TAB, frames=1)
    assert st.is_pad and (st.row, st.col) == (0, 0)
    st.row = 5
    run.key(pygame.K_TAB, frames=1)
    assert not st.is_pad and st.row == 0


def test_the_cursor_goes_round_the_rows(run):
    st = open_pad_tab(run)
    names = kp.rows()
    run.key(pygame.K_UP, frames=1)
    assert kp.rows()[st.row] == names[-1]
    run.key(pygame.K_DOWN, frames=1)
    assert st.row == 0


def test_the_switch_is_turned_with_enter_and_the_side_keys_and_is_saved(run):
    st = open_pad_tab(run)
    to_row(run, st, "shared")
    run.key(pygame.K_RETURN, frames=1)
    assert bindings.current.pad_shared is False
    assert json.load(open(user_settings.SETTINGS_FILE))["bindings"]["pad_shared"] is False
    settled(run)
    run.key(pygame.K_RIGHT, frames=1)
    assert bindings.current.pad_shared is True
    run.key(pygame.K_LEFT, frames=1)
    assert bindings.current.pad_shared is False
    assert "pad_shared" in json.load(open(user_settings.SETTINGS_FILE))["bindings"]


def test_turning_the_switch_off_gives_the_second_pad_a_copy_and_on_shows_the_first_place(run):
    st = open_pad_tab(run)
    bindings.current.set_pad_buttons(0, "fire", [0, 8])
    to_row(run, st, "shared")
    run.key(pygame.K_RETURN, frames=1)
    assert bindings.current.pad_buttons(1, "fire") == (0, 8)
    st.place = 1
    settled(run)
    run.key(pygame.K_RETURN, frames=1)
    assert bindings.current.pad_shared and st.place == 0


def test_left_and_right_choose_the_pad_only_when_they_do_not_share(run):
    st = open_pad_tab(run)
    run.key(pygame.K_RIGHT, frames=1)
    assert st.place == 0
    bindings.current.set_shared(False)
    run.key(pygame.K_RIGHT, frames=1)
    assert st.place == 1
    run.key(pygame.K_LEFT, frames=1)
    assert st.place == 0


def test_a_button_of_a_pad_lights_up_its_own_place(run, bench):                # noqa: F811
    a, b = pads(run, bench)
    st = open_pad_tab(run)
    bindings.current.set_shared(False)
    run.button(7, frames=1, joy=1, instance_id=b)
    assert st.place == 1
    run.button(7, frames=1, joy=0, instance_id=a)
    assert st.place == 0


def test_nothing_lights_up_while_the_pads_share_their_buttons(run, bench):    # noqa: F811
    a, b = pads(run, bench)
    st = open_pad_tab(run)
    run.button(7, frames=1, joy=1, instance_id=b)
    assert st.place == 0


# ------------------------------------------------------------------------------------------------ setting an action
def test_without_a_pad_the_action_cannot_be_set_and_says_so(run):
    st = open_pad_tab(run)
    run.key(pygame.K_RETURN, frames=1)
    assert st.mode == "list" and st.flash and st.flash[0] == t("kb_flash_no_pad")


def test_the_buttons_pressed_are_added_and_removed(run, bench):               # noqa: F811
    pads(run, bench)
    st = open_pad_tab(run)
    bindings.current.set_pad_buttons(0, "fire", [0, 2])
    begin(run, st, "fire")
    assert st.mode == "wait" and st.wait == (bindings.PAD, "fire", 0)
    run.button(8, frames=1)
    assert bindings.current.pad_buttons(0, "fire") == (0, 2, 8)
    run.button(2, frames=1)
    assert bindings.current.pad_buttons(0, "fire") == (0, 8)
    assert st.mode == "wait"                                                   # it goes on until it is ended
    assert json.load(open(user_settings.SETTINGS_FILE))["bindings"]["pad"][0]["fire"] == [0, 8]


def test_every_button_is_for_the_action_even_a_b_and_start(run, bench):       # noqa: F811
    pads(run, bench)
    st = open_pad_tab(run)
    begin(run, st, "pause")
    run.button(8, frames=1)                                                    # L3
    assert bindings.current.pad_buttons(0, "pause") == (7, 9, 6, 8)
    assert st.mode == "wait" and ks.is_open(run.game)                          # (it did not pause nor close anything)
    run.button(7, frames=1)                                                    # Start: removed from the three
    assert bindings.current.pad_buttons(0, "pause") == (9, 6, 8)


def test_a_button_of_another_action_is_taken_with_a_notice(run, bench):       # noqa: F811
    pads(run, bench)
    st = open_pad_tab(run)
    begin(run, st, "fire")
    bindings.current.set_pad_buttons(0, "fire", [0, 2])
    run.button(9, frames=1)                                                    # R3: one of the three pause buttons
    assert bindings.current.pad_buttons(0, "fire") == (0, 2, 9) and bindings.current.pad_buttons(0, "pause") == (7, 6)
    assert st.flash and st.flash[0] == t("kb_flash_pad_taken").format(action=t("act_pause"))


def test_what_would_empty_an_action_or_overfill_it_is_refused(run, bench):    # noqa: F811
    pads(run, bench)
    st = open_pad_tab(run)
    begin(run, st, "fire")
    run.button(1, frames=1)                                                    # B is the only Phénix button
    assert bindings.current.pad_buttons(0, "phenix") == (1,) and 1 not in bindings.current.pad_buttons(0, "fire")
    assert st.flash and st.flash[0] == t("kb_flash_pad_refused")
    run.button(8, frames=1)                                                    # fire already has four
    assert bindings.current.pad_buttons(0, "fire") == (0, 2, 3, 5)


def test_the_pause_button_cannot_be_one_that_runs_the_menus_on_the_screen(run, bench):   # noqa: F811
    pads(run, bench)
    st = open_pad_tab(run)
    begin(run, st, "pause")
    for button in bindings.PAUSE_FORBIDDEN:
        st.flash = None
        run.button(button, frames=1)
        assert st.flash and st.flash[0] == t("kb_flash_pad_pause")
    assert bindings.current.pad_buttons(0, "pause") == (7, 9, 6)


def test_the_capture_goes_to_the_pad_that_is_shown(run, bench):               # noqa: F811
    a, b = pads(run, bench)
    st = open_pad_tab(run)
    bindings.current.set_shared(False)
    st.place = 1
    begin(run, st, "fire")
    assert st.wait == (bindings.PAD, "fire", 1)
    run.button(8, frames=1, joy=1, instance_id=b)
    assert bindings.current.pad_buttons(1, "fire") == (0, 2, 3, 5)             # four already: refused
    bindings.current.set_pad_buttons(1, "fire", [0])
    run.button(8, frames=1, joy=1, instance_id=b)
    assert bindings.current.pad_buttons(1, "fire") == (0, 8) and bindings.current.pad_buttons(0, "fire") == (0, 2, 3, 5)


def test_the_capture_ends_with_the_dpad_the_stick_enter_or_escape_and_keeps_the_buttons(run, bench):   # noqa: F811
    pads(run, bench)
    st = open_pad_tab(run)
    bindings.current.set_pad_buttons(0, "fire", [0, 2])
    for how in ("hat", "axis", "enter", "escape", "arrow"):
        begin(run, st, "fire")
        assert st.mode == "wait", how
        run.button(8, frames=1) if 8 not in bindings.current.pad_buttons(0, "fire") else None
        if how == "hat":
            pygame.event.post(pygame.event.Event(pygame.JOYHATMOTION, joy=0, instance_id=0, hat=0, value=(0, 1)))
            run.frames(1)
            pygame.event.post(pygame.event.Event(pygame.JOYHATMOTION, joy=0, instance_id=0, hat=0, value=(0, 0)))
            run.frames(1)
        elif how == "axis":
            pygame.event.post(pygame.event.Event(pygame.JOYAXISMOTION, joy=0, instance_id=0, axis=0, value=0.95))
            run.frames(1)
            pygame.event.post(pygame.event.Event(pygame.JOYAXISMOTION, joy=0, instance_id=0, axis=0, value=0.0))
            run.frames(1)
        elif how == "enter":
            run.key(pygame.K_RETURN, frames=1)
        elif how == "escape":
            run.key(pygame.K_ESCAPE, frames=1)
        else:
            run.key(pygame.K_LEFT, frames=1)
        assert st.mode == "list" and ks.is_open(run.game), how
        assert 8 in bindings.current.pad_buttons(0, "fire"), how
        settled(run)


def test_the_enter_that_started_the_capture_does_not_end_it(run, bench):      # noqa: F811
    pads(run, bench)
    st = open_pad_tab(run)
    run.key(pygame.K_RETURN, frames=1)
    assert st.mode == "wait"
    run.key(pygame.K_RETURN, frames=1)                                         # the key repeat of the same press
    assert st.mode == "wait"


def test_other_keys_do_nothing_during_the_capture(run, bench):                 # noqa: F811
    pads(run, bench)
    st = open_pad_tab(run)
    begin(run, st, "fire")
    for key in (pygame.K_x, pygame.K_SPACE, pygame.K_DELETE, pygame.K_TAB):
        run.key(key, frames=1)
    assert st.mode == "wait" and bindings.current.to_dict() == {}


def test_the_capture_gives_up_after_a_silence_and_every_press_restarts_the_clock(run, bench):   # noqa: F811
    pads(run, bench)
    st = open_pad_tab(run)
    bindings.current.set_pad_buttons(0, "fire", [0, 2])
    begin(run, st, "fire")
    ks.tick(run.game, kp.PAD_WAIT_SEC - 1)
    run.button(8, frames=1)
    assert st.wait_left > kp.PAD_WAIT_SEC - 0.5                                # (the press started the clock again)
    ks.tick(run.game, kp.PAD_WAIT_SEC - 1)
    assert st.mode == "wait"
    ks.tick(run.game, 2)
    assert st.mode == "list" and 8 in bindings.current.pad_buttons(0, "fire")


def test_a_pad_does_not_pause_nor_start_phenix_while_the_screen_is_open(run, bench, monkeypatch):   # noqa: F811
    pads(run, bench)
    st = open_pad_tab(run)
    hit = []
    monkeypatch.setattr(run.game, "_activate_phenix_from_input", lambda ship: hit.append(ship))
    begin(run, st, "phenix")
    run.button(1, frames=1)
    run.button(7, frames=1)
    assert hit == [] and ks.is_open(run.game)


# ------------------------------------------------------------------------------------------------ the dialogs
def test_the_defaults_row_restores_the_shown_table_and_the_answer_chosen_is_cancel(run):
    st = open_pad_tab(run)
    bindings.current.set_pad_buttons(0, "fire", [0])
    to_row(run, st, "defaults")
    run.key(pygame.K_RETURN, frames=1)
    assert st.mode == "reset" and st.index == 1 and st.reset_kind == "defaults"
    settled(run)
    run.key(pygame.K_RETURN, frames=1)
    assert st.mode == "list" and bindings.current.pad_buttons(0, "fire") == (0,)
    settled(run)
    to_row(run, st, "defaults")
    run.key(pygame.K_RETURN, frames=1)
    run.key(pygame.K_UP, frames=1)
    settled(run)
    run.key(pygame.K_RETURN, frames=1)
    assert bindings.current.pad_buttons(0, "fire") == (0, 2, 3, 5)


def test_the_defaults_of_a_pad_do_not_touch_the_other_one_nor_the_keyboards(run):
    st = open_pad_tab(run)
    bindings.current.set_shared(False)
    bindings.current.set_pad_buttons(0, "fire", [0])
    bindings.current.set_pad_buttons(1, "fire", [2])
    bindings.current.set_key(bindings.KB2, "fire", 0, pygame.K_x)
    st.place = 1
    to_row(run, st, "defaults")
    run.key(pygame.K_RETURN, frames=1)
    run.key(pygame.K_UP, frames=1)
    settled(run)
    run.key(pygame.K_RETURN, frames=1)
    assert bindings.current.pad_buttons(1, "fire") == (0, 2, 3, 5)
    assert bindings.current.pad_buttons(0, "fire") == (0,) and bindings.current.keys(bindings.KB2, "fire")[0] == pygame.K_x


def test_the_defaults_of_a_shared_pad_table_restore_it_for_all(run):
    st = open_pad_tab(run)
    bindings.current.set_pad_buttons(0, "fire", [0])
    to_row(run, st, "defaults")
    run.key(pygame.K_RETURN, frames=1)
    assert kp.what(st) == t("kb_pad_all")
    run.key(pygame.K_UP, frames=1)
    settled(run)
    run.key(pygame.K_RETURN, frames=1)
    assert bindings.current.pad_buttons(1, "fire") == (0, 2, 3, 5)


def test_the_copy_button_replaces_the_shown_pad_by_the_other_one(run):
    st = open_pad_tab(run)
    bindings.current.set_shared(False)
    bindings.current.set_pad_buttons(0, "fire", [0, 8])
    bindings.current.set_pad_buttons(1, "fire", [2])
    st.place = 1
    to_row(run, st, "copy")
    run.key(pygame.K_RETURN, frames=1)
    assert st.mode == "reset" and st.reset_kind == "copy" and st.index == 1       # cancel is chosen
    settled(run)
    run.key(pygame.K_RETURN, frames=1)
    assert bindings.current.pad_buttons(1, "fire") == (2,)
    settled(run)
    to_row(run, st, "copy")
    run.key(pygame.K_RETURN, frames=1)
    run.key(pygame.K_UP, frames=1)
    settled(run)
    run.key(pygame.K_RETURN, frames=1)
    assert bindings.current.pad_buttons(1, "fire") == (0, 8) and bindings.current.pad_buttons(0, "fire") == (0, 8)
    st.place = 0
    bindings.current.set_pad_buttons(1, "fire", [3])
    settled(run)
    to_row(run, st, "copy")
    run.key(pygame.K_RETURN, frames=1)
    run.key(pygame.K_UP, frames=1)
    settled(run)
    run.key(pygame.K_RETURN, frames=1)
    assert bindings.current.pad_buttons(0, "fire") == (3,)                        # the other way round


def test_the_back_row_and_b_close_the_screen_and_y_does_nothing(run):
    st = open_pad_tab(run)
    run.button(3, frames=1)
    assert ks.is_open(run.game)
    to_row(run, st, "back")
    run.key(pygame.K_RETURN, frames=1)
    assert not ks.is_open(run.game)
    st = open_pad_tab(run)
    run.button(1, frames=1)
    assert not ks.is_open(run.game)


def test_the_hint_bar_of_the_tab(run):
    import hint_bar
    st = open_pad_tab(run)
    items = hint_bar.menu_items(run.game)
    assert ("ud", "hint_choose") in items and ("ok", "hint_change") in items and ("lr", "hint_pad_place") not in items
    bindings.current.set_shared(False)
    assert ("lr", "hint_pad_place") in hint_bar.menu_items(run.game)
    to_row(run, st, "defaults")
    assert ("ok", "hint_ok") in hint_bar.menu_items(run.game)
    st.mode, st.wait = "wait", (bindings.PAD, "fire", 0)
    assert hint_bar.menu_items(run.game) == [("ud", "hint_done")]


# ------------------------------------------------------------------------------------------------ what the game does with it
def test_the_game_reads_what_the_screen_set(run, bench):                       # noqa: F811
    pads(run, bench)
    st = open_pad_tab(run)
    begin(run, st, "phenix")
    run.button(8, frames=1)                                                    # L3 joins B
    assert bindings.current.pad_buttons(0, "phenix") == (1, 8)
    bindings.load(json.load(open(user_settings.SETTINGS_FILE))["bindings"])    # read back from the file
    assert bindings.current.pad_buttons(0, "phenix") == (1, 8)


# ------------------------------------------------------------------------------------------------ drawing
@pytest.mark.parametrize("lang", LANG_CODES)
def test_every_state_of_the_tab_draws_in_every_language(run, bench, lang):    # noqa: F811
    pads(run, bench, count=1)
    g = run.game
    set_lang(lang)
    g.language = lang
    st = open_pad_tab(run)
    for shared in (True, False):
        bindings.current.set_shared(shared)
        bindings.current.set_pad_buttons(0, "fire", [0, 2, 3, 5])
        bindings.current.set_pad_buttons(0, "pause", [7, 9, 6, 8])
        for place in (0, 1):
            st.place = place
            for row in range(len(kp.rows())):
                st.row = row
                st.mode, st.wait, st.flash = "list", None, None
                ks.draw(g)
                st.flash = ["x" * 40, 1.0]
                ks.draw(g)
            for action in kp.ACTIONS:
                st.row = kp.rows().index(action)
                st.mode, st.wait, st.wait_left, st.wait_total = "wait", (bindings.PAD, action, place), 3.0, 6.0
                ks.draw(g)
                st.flash = ["y" * 60, 1.0]
                ks.draw(g)
            st.flash = None
            for kind in ("defaults", "copy"):
                st.mode, st.reset_kind, st.index, st.wait = "reset", kind, place, None
                ks.draw(g)
    st.mode = "list"
    run.frames(2)


def test_buttons_without_a_place_on_the_drawing_do_not_break_it(run, bench):  # noqa: F811
    pads(run, bench, count=1)
    st = open_pad_tab(run)
    bindings.current.set_pad_buttons(0, "fire", [12, 15, 30, 63])
    ks.draw(run.game)
    st.row = 0
    ks.draw(run.game)
    assert kp._spot(30) is None and kp._spot(0) is not None
