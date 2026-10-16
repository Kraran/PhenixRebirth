"""Control "auto" in solo: the last device used (keys or pad) flies the ship; a plugged pad is taken at once."""
import json

import pygame
import pytest

import controls
import menu_actions
import update_play
import user_settings
from i18n import t
from test_controls import FakeJoy, Keys, bench  # noqa: F401  (fixtures and helpers)
from test_smoke import run  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def _own_settings_file(tmp_path, monkeypatch):
    """Every test starts from the default settings, and what it saves does not leak into the next one."""
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))


def _key(game, key=pygame.K_LEFT):
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0))
    game.handle_events()


def _button(game, iid, button=3):
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=button, instance_id=iid, joy=0))
    game.handle_events()


def _axis(game, iid, value):
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.JOYAXISMOTION, axis=0, value=value, instance_id=iid, joy=0))
    game.handle_events()


# ------------------------------------------------------------------ the choice at launch and the last device used
def test_the_default_is_auto_and_a_plugged_pad_is_taken_at_launch(bench):
    bench.plug()
    from game import Game
    g = Game()
    g._intro_done = True
    try:
        assert g.control_pref == "auto" and g.input_mode == "gamepad"
    finally:
        g.running = False


def test_without_a_pad_the_keys_are_used(run):
    g = run.game
    assert g.control_pref == "auto" and g.input_mode == "keyboard" and not g.gamepad_detected


def test_a_key_gives_the_control_to_the_keys_and_a_button_gives_it_back_to_the_pad(bench, run):    # noqa: F811
    a = bench.plug()
    g = run.game
    g._poll_gamepad()
    assert g.input_mode == "gamepad"
    _key(g)
    assert g.input_mode == "keyboard" and g.last_input_pad is False
    _button(g, a)
    assert g.input_mode == "gamepad" and g.last_input_pad is True
    _key(g)
    _axis(g, a, 0.9)
    assert g.input_mode == "gamepad"


def test_a_stick_that_only_drifts_does_not_take_the_control(bench, run):               # noqa: F811
    a = bench.plug()
    g = run.game
    g._poll_gamepad()
    _key(g)
    _axis(g, a, 0.2)
    assert g.input_mode == "keyboard"
    _axis(g, a, 0.0)
    assert g.input_mode == "keyboard"


def test_without_a_pad_a_pad_event_changes_nothing(run):
    g = run.game
    _button(g, 99)
    assert g.input_mode == "keyboard"


def test_the_pad_just_used_is_the_one_that_flies_the_ship(bench, run):                  # noqa: F811
    a, b = bench.plug(), bench.plug()
    g = run.game
    g._poll_gamepad()
    assert controls.pad_id(g.joystick) == a
    _button(g, b)
    assert controls.pad_id(g.joystick) == b
    _button(g, a)
    assert controls.pad_id(g.joystick) == a


# ------------------------------------------------------------------ forced choices
def test_keyboard_forced_ignores_the_pad(bench, run):                                    # noqa: F811
    a = bench.plug()
    g = run.game
    g.control_pref = "keyboard"
    g._poll_gamepad()
    _button(g, a)
    assert g.input_mode == "keyboard"


def test_gamepad_forced_ignores_the_keys_but_only_with_a_pad(bench, run):                # noqa: F811
    a = bench.plug()
    g = run.game
    g.control_pref = "gamepad"
    g._poll_gamepad()
    _key(g)
    assert g.input_mode == "gamepad"
    bench.unplug(a)
    g._poll_gamepad()
    assert g.input_mode == "keyboard"                  # nothing to hold: the keys, until a pad comes back
    bench.plug()
    g._poll_gamepad()
    assert g.input_mode == "gamepad"


# ------------------------------------------------------------------ the option
def _focus_control(g):
    g.menu_screen = "options"
    g.opt_tab = 0
    g.menu_index = g._options_spec().index("control")


def test_the_option_cycles_auto_keyboard_gamepad_when_a_pad_is_there(bench, run):         # noqa: F811
    bench.plug()
    g = run.game
    g._poll_gamepad()
    _focus_control(g)
    seen = [g.control_pref]
    for _ in range(3):
        menu_actions.menu_adjust(g, 1)
        seen.append(g.control_pref)
    assert seen == ["auto", "keyboard", "gamepad", "auto"]
    menu_actions.menu_adjust(g, -1)
    assert g.control_pref == "gamepad" and g.input_mode == "gamepad"


def test_the_option_without_a_pad_is_auto_or_keyboard(run):
    g = run.game
    _focus_control(g)
    seen = [g.control_pref]
    for _ in range(2):
        menu_actions.menu_adjust(g, 1)
        seen.append(g.control_pref)
    assert seen == ["auto", "keyboard", "auto"]


def test_the_option_shows_auto_and_the_device_in_use(bench, run):                        # noqa: F811
    bench.plug()
    g = run.game
    g._poll_gamepad()
    assert g._option_value("control") == f"{t('ctrl_auto')} ({t('ctrl_pad')})"
    _key(g)
    assert g._option_value("control") == f"{t('ctrl_auto')} ({t('ctrl_kb')})"
    g.control_pref = "keyboard"
    assert g._option_value("control") == t("ctrl_kb")


# ------------------------------------------------------------------ saved setting
def test_the_choice_is_saved_and_an_old_input_mode_is_forgotten(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(path))
    assert user_settings.load_user_settings()["control_pref"] == "auto"
    path.write_text(json.dumps({"input_mode": "keyboard"}), encoding="utf-8")        # an old file: it forced the keys
    assert user_settings.load_user_settings()["control_pref"] == "auto"
    path.write_text(json.dumps({"control_pref": "gamepad"}), encoding="utf-8")
    assert user_settings.load_user_settings()["control_pref"] == "gamepad"


def test_save_settings_writes_the_choice(run, monkeypatch):
    import game as game_mod
    saved = {}
    monkeypatch.setattr(game_mod, "save_user_settings", lambda d: saved.update(d))
    g = run.game
    g.control_pref = "keyboard"
    g.save_settings()
    assert saved["control_pref"] == "keyboard" and "input_mode" not in saved


def test_a_bad_saved_value_means_auto(bench, monkeypatch, tmp_path):                      # noqa: F811
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"control_pref": "joystick"}), encoding="utf-8")
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(path))
    from game import Game
    g = Game()
    g._intro_done = True
    try:
        assert g.control_pref == "auto"
    finally:
        g.running = False


def test_the_choice_survives_a_return_to_the_menu(run):
    g = run.game
    g.control_pref = "keyboard"
    g.play_mode = "solo"
    g._begin_run()
    run.frames(5)
    g._quit_to_menu()
    assert g.control_pref == "keyboard"


# ------------------------------------------------------------------ while playing
def _solo_run(run, pad):
    g = run.game
    g._poll_gamepad()
    g.play_mode = "solo"
    g._begin_run()
    run.frames(5)
    g.paused = False
    g.input_grace = 0.0
    g.stage_transition = None
    return g


def _fly(g, keys, frames=20):
    real = pygame.key.get_pressed
    pygame.key.get_pressed = lambda: keys
    try:
        for _ in range(frames):
            g.dt = 1 / 60
            update_play.tick_ships(g)
    finally:
        pygame.key.get_pressed = real


def test_in_auto_the_pad_flies_the_ship_until_a_key_is_pressed(bench, run):               # noqa: F811
    a = bench.plug()
    g = _solo_run(run, a)
    pad = g.joystick
    assert g.input_mode == "gamepad"
    pad.axes[0] = 1.0
    g.player.x = 600.0
    _fly(g, Keys())
    right = g.player.x
    assert right > 600.0                                    # the stick pushes the ship to the right
    pad.axes[0] = 0.0
    _key(g, pygame.K_SPACE)                                 # a key: the keys fly it now
    pad.axes[0] = 1.0                                       # (a stick still held does nothing any more)
    g.player.x = 600.0
    _fly(g, Keys())
    assert g.player.x == 600.0
    _fly(g, Keys(pygame.K_LEFT))
    assert g.player.x < 600.0
    _axis(g, a, 1.0)                                        # the stick again: the pad takes it back
    g.player.x = 600.0
    _fly(g, Keys())
    assert g.player.x > 600.0


def test_a_pad_plugged_in_while_playing_on_the_keys_takes_the_control(bench, run):          # noqa: F811
    g = _solo_run(run, None)
    assert g.input_mode == "keyboard"
    bench.plug()
    g._poll_gamepad()
    assert g.input_mode == "gamepad" and not g.paused


def test_a_pad_plugged_in_while_the_keys_are_forced_changes_nothing(bench, run):             # noqa: F811
    g = _solo_run(run, None)
    g.control_pref = "keyboard"
    bench.plug()
    g._poll_gamepad()
    assert g.input_mode == "keyboard"


def test_unplugging_the_pad_in_auto_gives_the_control_to_the_keys(bench, run):              # noqa: F811
    a = bench.plug()
    g = _solo_run(run, a)
    assert g.input_mode == "gamepad"
    bench.unplug(a)
    g._poll_gamepad()
    assert g.paused and g.input_mode == "keyboard" and g.last_input_pad is False


def test_hot_seat_follows_the_last_device_too(bench, run):                                 # noqa: F811
    a = bench.plug()
    g = run.game
    g._poll_gamepad()
    g.play_mode = "hotseat"
    assert g.input_mode == "gamepad"
    _key(g)
    assert g.input_mode == "keyboard"


def test_coop_is_not_touched_by_the_auto_choice(bench, run):                                # noqa: F811
    a, b = bench.plug(), bench.plug()
    g = run.game
    g._poll_gamepad()
    g.ship_id, g.ship_id_p2 = "phoenix", "shield"
    g.play_mode = "coop"
    g._begin_run()
    run.frames(5)
    first = g.player._joy
    _button(g, b)                                          # a button of the second pad: P1 keeps the first pad
    assert g.player._joy is first and g.player.input_scheme == "pad" and g.player2.input_scheme == "pad"
    assert controls.pad_id(g.joystick) == controls.pad_id(first)


def test_a_second_pad_plugged_in_does_not_take_the_control_from_the_keys(bench, run):       # noqa: F811
    bench.plug()
    g = run.game
    g._poll_gamepad()
    _key(g)
    assert g.input_mode == "keyboard"
    bench.plug()
    g._poll_gamepad()
    assert g.input_mode == "keyboard"


def test_without_any_pad_a_key_leaves_the_control_alone(run):
    g = run.game
    g.input_mode = "gamepad"                              # (set by hand, like the replays do)
    _key(g)
    assert g.input_mode == "gamepad"
