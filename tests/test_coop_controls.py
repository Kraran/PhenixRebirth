"""Coop: the device of each player (auto by default, or chosen in the options)."""
import itertools

import pygame
import pytest

import controls
import menu_actions
import user_settings
from controls import AUTO, KB_ARROWS, KB_LEFT, resolve_coop
from i18n import t
from test_controls import Keys, bench  # noqa: F401  (fixtures and helpers)
from test_smoke import run  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def _own_settings_file(tmp_path, monkeypatch):
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))


# ------------------------------------------------------------------ the rule
def test_auto_is_two_pads_or_a_pad_and_the_arrows_or_the_split_keyboard():
    assert resolve_coop(AUTO, AUTO, 0) == (KB_LEFT, KB_ARROWS)
    assert resolve_coop(AUTO, AUTO, 1) == ("pad1", KB_ARROWS)
    assert resolve_coop(AUTO, AUTO, 2) == ("pad1", "pad2")
    assert resolve_coop(AUTO, AUTO, 4) == ("pad1", "pad2")


def test_a_choice_is_kept_and_the_other_player_takes_what_is_left():
    assert resolve_coop(KB_LEFT, AUTO, 2) == (KB_LEFT, "pad1")
    assert resolve_coop(AUTO, KB_ARROWS, 1) == ("pad1", KB_ARROWS)
    assert resolve_coop("pad2", AUTO, 2) == ("pad2", "pad1")
    assert resolve_coop(AUTO, "pad1", 2) == ("pad2", "pad1")
    assert resolve_coop(KB_ARROWS, AUTO, 0) == (KB_ARROWS, KB_LEFT)
    assert resolve_coop(AUTO, KB_LEFT, 0) == (KB_ARROWS, KB_LEFT)
    assert resolve_coop("pad2", "pad1", 2) == ("pad2", "pad1")
    assert resolve_coop(KB_ARROWS, KB_LEFT, 2) == (KB_ARROWS, KB_LEFT)


def test_a_pad_that_is_not_plugged_in_counts_as_auto():
    assert resolve_coop("pad2", AUTO, 1) == ("pad1", KB_ARROWS)
    assert resolve_coop(AUTO, "pad3", 2) == ("pad1", "pad2")
    assert resolve_coop("pad1", AUTO, 0) == (KB_LEFT, KB_ARROWS)


def test_two_players_never_get_the_same_device():
    choices = [AUTO, KB_LEFT, KB_ARROWS, "pad1", "pad2", "pad3", "junk"]
    for p1, p2, n in itertools.product(choices, choices, range(4)):
        d1, d2 = resolve_coop(p1, p2, n)
        assert d1 != d2 and controls.available(d1, n) and controls.available(d2, n), (p1, p2, n)


def test_the_options_cycle_leaves_out_what_the_other_player_took():
    assert controls.coop_choices(0, AUTO) == [AUTO, KB_LEFT, KB_ARROWS]
    assert controls.coop_choices(2, AUTO) == [AUTO, KB_LEFT, KB_ARROWS, "pad1", "pad2"]
    assert controls.coop_choices(2, "pad1") == [AUTO, KB_LEFT, KB_ARROWS, "pad2"]
    assert controls.coop_choices(1, KB_LEFT) == [AUTO, KB_ARROWS, "pad1"]


def test_choices_are_checked_and_turned_into_input_schemes():
    for ok in (AUTO, KB_LEFT, KB_ARROWS, "pad1", "pad12"):
        assert controls.valid_choice(ok) and controls.clean_choice(ok) == ok
    for bad in (None, "", "pad", "pad0", "padX", "joystick", 3):
        assert not controls.valid_choice(bad) and controls.clean_choice(bad) == AUTO
    assert [controls.scheme_of(d) for d in (KB_LEFT, KB_ARROWS, "pad1")] == ["kb1", "kb2", "pad"]


# ------------------------------------------------------------------ the game
def test_the_bindings_follow_the_choices(run, bench):                                    # noqa: F811
    a, b = bench.plug(), bench.plug()
    g = run.game
    g.coop_pref = [KB_LEFT, AUTO]
    (s1, j1), (s2, j2) = g._coop_bindings()
    assert (s1, j1) == ("kb1", None) and s2 == "pad" and controls.pad_id(j2) == a
    g.coop_pref = ["pad2", AUTO]
    (s1, j1), (s2, j2) = g._coop_bindings()
    assert s1 == s2 == "pad" and controls.pad_id(j1) == b and controls.pad_id(j2) == a
    g.coop_pref = [AUTO, AUTO]
    (s1, j1), (s2, j2) = g._coop_bindings()
    assert controls.pad_id(j1) == a and controls.pad_id(j2) == b


def _coop(run, p1, p2):
    g = run.game
    g.coop_pref = [p1, p2]
    g.ship_id, g.ship_id_p2 = "phoenix", "shield"
    g.play_mode = "coop"
    g._begin_run()
    run.frames(5)
    g.paused = False
    return g


def test_two_players_on_one_keyboard_even_with_a_pad_plugged_in(run, bench):             # noqa: F811
    bench.plug()
    g = _coop(run, KB_LEFT, KB_ARROWS)
    assert (g.player.input_scheme, g.player2.input_scheme) == ("kb1", "kb2")
    assert g.player._joy is None and g.player2._joy is None


def test_the_player_on_the_arrows_can_be_player_one(run):
    g = _coop(run, KB_ARROWS, KB_LEFT)
    assert (g.player.input_scheme, g.player2.input_scheme) == ("kb2", "kb1")
    p1, p2 = g.player, g.player2
    for ship, keys, sign in ((p1, Keys(pygame.K_RIGHT), 1), (p2, Keys(pygame.K_d), 1), (p2, Keys(pygame.K_a), -1),
                             (p2, Keys(pygame.K_q), -1), (p1, Keys(pygame.K_LEFT), -1)):
        ship.x = 600.0
        ship.update(1 / 60, keys, "keyboard", None)
        assert (ship.x - 600.0) * sign > 0
    p1.x = p2.x = 600.0
    p1.update(1 / 60, Keys(pygame.K_d, pygame.K_a), "keyboard", None)          # the left-hand keys do nothing for P1
    p2.update(1 / 60, Keys(pygame.K_LEFT, pygame.K_RIGHT), "keyboard", None)   # nor the arrows for P2
    assert p1.x == 600.0 and p2.x == 600.0


def _shift(game, key):
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0))
    game.handle_events()


def test_the_shift_keys_start_the_form_of_the_player_on_that_keyboard(run, monkeypatch):
    g = _coop(run, KB_ARROWS, KB_LEFT)
    hit = []
    monkeypatch.setattr(g, "_activate_phenix_from_input", lambda ship: hit.append(ship))
    g._special_keys = set()
    _shift(g, pygame.K_RSHIFT)
    assert hit == [g.player]                                  # the arrows are player 1's
    g._special_keys = set()
    _shift(g, pygame.K_LSHIFT)
    assert hit == [g.player, g.player2]


def test_the_usual_coop_shift_keys_are_unchanged(run, monkeypatch):
    g = _coop(run, AUTO, AUTO)                               # no pad: left keyboard + arrows
    hit = []
    monkeypatch.setattr(g, "_activate_phenix_from_input", lambda ship: hit.append(ship))
    g._special_keys = set()
    _shift(g, pygame.K_LSHIFT)
    g._special_keys = set()
    _shift(g, pygame.K_RSHIFT)
    assert hit == [g.player, g.player2]


def test_a_shift_key_with_nobody_on_that_keyboard_does_nothing(run, bench, monkeypatch):   # noqa: F811
    bench.plug()
    bench.plug()
    g = _coop(run, AUTO, AUTO)                               # two pads: nobody on the keyboard
    hit = []
    monkeypatch.setattr(g, "_activate_phenix_from_input", lambda ship: hit.append(ship))
    g._special_keys = set()
    _shift(g, pygame.K_RSHIFT)
    g._special_keys = set()
    _shift(g, pygame.K_LSHIFT)
    assert hit == []


# ------------------------------------------------------------------ the options
def _focus(g, key):
    g.menu_screen = "options"
    g.opt_tab = 0
    g.menu_index = g._options_spec().index(key)


def test_the_two_rows_are_in_the_game_tab_after_the_control(run):
    g = run.game
    _focus(g, "coop_p1")
    spec = g._options_spec()
    assert spec[:3] == ["control", "coop_p1", "coop_p2"]
    for key in ("coop_p1", "coop_p2"):
        assert t("opt_help_" + key) != "opt_help_" + key and g._option_label(key) != key


def test_the_row_cycles_through_the_devices_and_skips_the_other_players(run, bench):          # noqa: F811
    bench.plug()
    bench.plug()
    g = run.game
    g._poll_gamepad()
    _focus(g, "coop_p1")
    seen = [g.coop_pref[0]]
    for _ in range(5):
        menu_actions.menu_adjust(g, 1)
        seen.append(g.coop_pref[0])
    assert seen == [AUTO, KB_LEFT, KB_ARROWS, "pad1", "pad2", AUTO]
    menu_actions.menu_adjust(g, -1)
    assert g.coop_pref[0] == "pad2"
    _focus(g, "coop_p2")                                     # player 2 cannot take what player 1 has
    seen = []
    for _ in range(5):
        menu_actions.menu_adjust(g, 1)
        seen.append(g.coop_pref[1])
    assert seen == [KB_LEFT, KB_ARROWS, "pad1", AUTO, KB_LEFT]


def test_the_rows_show_the_device_in_use(run, bench):                                       # noqa: F811
    g = run.game
    assert g._option_value("coop_p1") == f"{t('ctrl_auto')} ({t('ctrl_kb_left')})"
    assert g._option_value("coop_p2") == f"{t('ctrl_auto')} ({t('ctrl_kb_arrows')})"
    bench.plug()
    g._poll_gamepad()
    assert g._option_value("coop_p1") == f"{t('ctrl_auto')} ({t('ctrl_pad_n').format(n=1)})"
    g.coop_pref = [KB_ARROWS, AUTO]
    assert g._option_value("coop_p1") == t("ctrl_kb_arrows")
    assert g._option_value("coop_p2") == f"{t('ctrl_auto')} ({t('ctrl_pad_n').format(n=1)})"
    g.coop_pref = ["pad2", AUTO]                             # a pad that is not there: shown as auto
    assert g._option_value("coop_p1").startswith(t("ctrl_auto"))


def test_the_options_screen_draws_with_the_new_rows(run, bench):                            # noqa: F811
    bench.plug()
    g = run.game
    g._poll_gamepad()
    g.coop_pref = [KB_ARROWS, "pad1"]
    _focus(g, "coop_p2")
    run.frames(5)
    g.opt_tab = 0
    g.menu_index = 0
    run.frames(3)


def test_the_choices_are_saved_and_loaded_again(run, bench):                                 # noqa: F811
    bench.plug()
    g = run.game
    g._poll_gamepad()
    _focus(g, "coop_p1")
    menu_actions.menu_adjust(g, 1)
    menu_actions.menu_adjust(g, 1)
    assert g.coop_pref[0] == KB_ARROWS
    _focus(g, "coop_p2")
    menu_actions.menu_adjust(g, 1)                           # player 2: the left keyboard (the arrows are taken)
    assert g.coop_pref == [KB_ARROWS, KB_LEFT]
    saved = user_settings.load_user_settings()
    assert (saved["coop_p1"], saved["coop_p2"]) == (KB_ARROWS, KB_LEFT)
    from game import Game
    g2 = Game()
    g2._intro_done = True
    try:
        assert g2.coop_pref == [KB_ARROWS, KB_LEFT]
    finally:
        g2.running = False


def test_a_bad_saved_choice_means_auto(tmp_path, monkeypatch):
    import json
    (tmp_path / "settings.json").write_text(json.dumps({"coop_p1": "pad", "coop_p2": 7}), encoding="utf-8")
    from game import Game
    g = Game()
    g._intro_done = True
    try:
        assert g.coop_pref == [AUTO, AUTO]
    finally:
        g.running = False


def test_the_defaults_are_auto():
    saved = user_settings.load_user_settings()
    assert (saved["coop_p1"], saved["coop_p2"]) == (AUTO, AUTO)


def test_the_longest_value_of_the_coop_rows_fits_the_options_box_in_every_language(run):
    import i18n
    g = run.game
    left_margin, right_margin, arrows = 28, 28, 48               # as draw_options places them (box 600 wide)
    try:
        for code in i18n.LANG_CODES:
            i18n.set_lang(code)
            label = g.font.size(g._option_label("coop_p1"))[0]
            values = [f"{t('ctrl_auto')} ({t(k)})" for k in ("ctrl_kb_left", "ctrl_kb_arrows")]
            values.append(f"{t('ctrl_auto')} ({t('ctrl_pad_n').format(n=2)})")
            value = max(g.menu_font.size(v)[0] for v in values)
            assert left_margin + label + value + arrows + right_margin <= 600, code
    finally:
        i18n.set_lang("fr")


def test_the_coop_rows_are_drawn_with_the_small_font(run, monkeypatch):
    import draw_frame
    g = run.game
    seen = {}
    real = draw_frame._value_with_arrows

    def spy(game, surf, font, value, *a, **k):
        seen[value] = font
        return real(game, surf, font, value, *a, **k)

    monkeypatch.setattr(draw_frame, "_value_with_arrows", spy)
    g.menu_screen, g.opt_tab, g.menu_index = "options", 0, 1
    run.frames(2)
    assert seen[g._option_value("coop_p1")] is g.menu_font and seen[g._option_value("coop_p2")] is g.menu_font
    assert seen[g._option_value("autofire")] is g.font
