"""The keys of the ship as the player sets them: the settings (src/bindings.py), the ship that obeys them, and the screen
"Keys and buttons" (src/keybind_screen.py) opened from Options > Game."""
import json

import pygame
import pytest

import bindings
import controls
import game_init
import keybind_screen as ks
import user_settings
from bindings import KB1, KB2, Bindings
from i18n import LANG_CODES, set_lang, t
from test_controls import Keys, bench  # noqa: F401  (fixtures and helpers)


@pytest.fixture(autouse=True)
def _own_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    bindings.load(None)
    yield
    bindings.load(None)
    set_lang("fr")


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

    def keyup(self, key, frames=1):
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key, mod=0, scancode=0))
        self.frames(frames)

    def button(self, button, frames=2, joy=0, instance_id=0):
        self.game.input_grace = 0.0
        pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=button, joy=joy, instance_id=instance_id))
        self.frames(frames)


@pytest.fixture
def run():
    from game import Game

    game = Game()
    game._intro_done = True
    game.fade_phase = None
    game.input_grace = 0.0
    set_lang("fr")
    r = Runner(game)
    r.frames(2)
    yield r
    game.running = False


def settled(run):
    """Let the grace time after an Enter / a choice run out and the key go up (a real player does not press twice in 0.3 s)."""
    run.game.keybind.grace = 0.0
    run.game.keybind.ignore = None                  # (and the key was released)


def open_from_options(run):
    g = run.game
    g._open_options()
    g.opt_tab = 0
    g.menu_index = g._options_spec().index("keybinds")
    run.key(pygame.K_RETURN)
    assert ks.is_open(g)
    settled(run)
    return g.keybind


def row_of(action):
    return ks.ROWS.index(action)


def go(run, st, action, col=0):
    """Put the cursor on a key of the list (moving by the keys, as the player would)."""
    assert st.mode == "list"
    for _ in range(len(ks.ROWS)):
        if st.row == row_of(action):
            break
        run.key(pygame.K_DOWN, frames=1)
    assert st.row == row_of(action)
    if action in ks.ACTION_ROWS and st.col != col:
        run.key(pygame.K_RIGHT, frames=1)
    assert action not in ks.ACTION_ROWS or st.col == col


def set_by_screen(run, st, action, col, key):
    settled(run)
    go(run, st, action, col)
    run.key(pygame.K_RETURN, frames=1)
    assert st.mode == "wait"
    settled(run)
    run.key(key, frames=1)


# ================================================================================================ the settings
def test_the_defaults_are_the_keys_the_game_always_had():
    b = Bindings()
    assert b.keys(KB1, "left") == (pygame.K_q, pygame.K_a) and b.keys(KB1, "up") == (pygame.K_z, pygame.K_w)
    assert b.keys(KB1, "right") == (pygame.K_d,) and b.keys(KB1, "down") == (pygame.K_s,)
    assert b.keys(KB1, "fire") == (pygame.K_LCTRL,) and b.keys(KB1, "phenix") == (pygame.K_LSHIFT,)
    assert b.keys(KB2, "left") == (pygame.K_LEFT,) and b.keys(KB2, "fire") == (pygame.K_SPACE, pygame.K_RCTRL)
    assert b.keys(KB2, "phenix") == (pygame.K_RSHIFT,)
    assert b.pad_buttons(0, "fire") == (0, 2, 3, 5) and b.pad_buttons(0, "phenix") == (1,)
    assert b.pad_buttons(0, "pause") == (7, 9, 6)
    assert b.to_dict() == {}


def test_the_default_keys_never_collide_between_the_two_keyboards():
    seen = {}
    for profile in bindings.KEY_PROFILES:
        for action in bindings.KEY_ACTIONS:
            for key in bindings.DEFAULT_KEYS[profile][action]:
                if key:
                    assert key not in seen, (profile, action)
                    seen[key] = (profile, action)


def test_a_free_key_is_set_and_the_old_one_is_gone():
    b = Bindings()
    assert b.set_key(KB2, "fire", 0, pygame.K_x)
    assert b.slots(KB2, "fire") == [pygame.K_x, pygame.K_RCTRL] and b.is_modified(KB2, "fire")
    assert not b.is_modified(KB2, "left")


def test_a_key_in_use_is_refused_unless_it_is_swapped():
    b = Bindings()
    assert not b.set_key(KB2, "fire", 0, pygame.K_d)                          # D is "right" of the other keyboard
    assert b.slots(KB2, "fire") == [pygame.K_SPACE, pygame.K_RCTRL]           # nothing moved
    assert b.set_key(KB2, "fire", 0, pygame.K_d, swap=True)
    assert b.slots(KB2, "fire")[0] == pygame.K_d
    assert b.slots(KB1, "right") == [pygame.K_SPACE, None]                    # it got what the slot had
    assert b.find_key(pygame.K_d) == (KB2, "fire", 0)


def test_a_swap_gives_the_other_action_what_the_slot_had_or_nothing():
    b = Bindings()
    assert b.set_key(KB1, "up", 0, pygame.K_q, swap=True)                     # Q was "left": it gets Z
    assert b.slots(KB1, "left") == [pygame.K_z, pygame.K_a] and b.slots(KB1, "up") == [pygame.K_q, pygame.K_w]
    b = Bindings()
    assert b.set_key(KB1, "right", 1, pygame.K_a, swap=True)                  # an empty slot: "left" just loses A
    assert b.slots(KB1, "left") == [pygame.K_q, None] and b.slots(KB1, "right") == [pygame.K_d, pygame.K_a]


def test_a_swap_that_would_leave_the_other_action_empty_is_refused():
    b = Bindings()
    before = b.to_dict()
    assert not b.set_key(KB1, "fire", 1, pygame.K_d, swap=True)               # D is the only key of "right"
    assert b.to_dict() == before and b.slots(KB1, "fire") == [pygame.K_LCTRL, None]


def test_an_action_always_keeps_one_key():
    b = Bindings()
    assert not b.set_key(KB1, "right", 0, None)                               # D is the only key of "right"
    assert b.keys(KB1, "right") == (pygame.K_d,)
    assert b.set_key(KB1, "left", 1, None) and b.keys(KB1, "left") == (pygame.K_q,)
    assert not b.set_key(KB1, "left", 0, None)
    assert b.set_key(KB1, "right", 1, pygame.K_t)
    assert b.set_key(KB1, "right", 0, None) and b.keys(KB1, "right") == (pygame.K_t,)


def test_the_reserved_keys_cannot_be_given_to_the_ship():
    b = Bindings()
    for key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB, pygame.K_BACKSPACE, pygame.K_DELETE,
                pygame.K_F1, pygame.K_F12, pygame.K_PAUSE, pygame.K_CAPSLOCK, pygame.K_LGUI):
        assert not bindings.bindable(key)
        assert not b.set_key(KB2, "fire", 1, key, swap=True)
    assert b.to_dict() == {}
    for key in (pygame.K_a, pygame.K_SPACE, pygame.K_LCTRL, pygame.K_RSHIFT, pygame.K_UP, pygame.K_KP0, pygame.K_COMMA):
        assert bindings.bindable(key)
    assert not bindings.bindable(0) and not bindings.bindable(None) and not bindings.bindable("x")


def test_the_same_key_twice_in_one_action_leaves_one():
    b = Bindings()
    assert b.set_key(KB2, "fire", 1, pygame.K_x)
    assert b.set_key(KB2, "fire", 0, pygame.K_x, swap=True)
    assert b.slots(KB2, "fire").count(pygame.K_x) == 1


def test_a_reset_forgets_only_that_keyboard():
    b = Bindings()
    b.set_key(KB1, "fire", 0, pygame.K_x)
    b.set_key(KB2, "fire", 0, pygame.K_c)
    b.reset_keys(KB1)
    assert b.keys(KB1, "fire") == (pygame.K_LCTRL,) and b.slots(KB2, "fire")[0] == pygame.K_c
    b.reset_all()
    assert b.to_dict() == {}


def test_only_the_differences_are_written_and_they_come_back():
    b = Bindings()
    b.set_key(KB2, "fire", 0, pygame.K_x)
    b.set_key(KB1, "left", 1, None)
    b.set_pad_buttons(0, "fire", [0, 8])
    b.set_shared(False)
    d = b.to_dict()
    json.dumps(d)                                                             # (it is plain data)
    assert set(d) == {KB1, KB2, "pad", "pad_shared"}
    assert d[KB2] == {"fire": ["x", "right ctrl"]} and d[KB1] == {"left": ["q", None]}
    c = Bindings.from_dict(json.loads(json.dumps(d)))
    assert c.kb == b.kb and c.pads == b.pads and c.pad_shared is False


def test_a_default_that_changes_later_reaches_whoever_did_not_touch_it():
    d = Bindings().to_dict()
    assert d == {}                                                            # nothing is stored for the untouched keys


@pytest.mark.parametrize("data", [
    None, 3, "x", [], {"kb1": 5}, {"kb1": {"left": "q"}}, {"kb1": {"left": []}}, {"kb1": {"left": [None, None]}},
    {"kb1": {"left": ["nonsense key"]}}, {"kb1": {"left": ["q", "a", "z"]}}, {"kb1": {"nothing": ["q"]}},
    {"kb1": {"left": ["escape"]}}, {"pad": 3}, {"pad": [5, 6]}, {"pad": [{"fire": "x"}]}, {"pad": [{"fire": []}]},
    {"pad": [{"fire": [1, 2, 3, 4, 5]}]}, {"pad": [{"fire": [True]}]}, {"pad": [{"fire": [-1]}]},
    {"pad": [{"pause": [1000]}]}, {"pad_shared": "yes"},
])
def test_damaged_settings_never_break_and_never_leave_an_action_empty(data):
    b = Bindings.from_dict(data)
    for profile in bindings.KEY_PROFILES:
        for action in bindings.KEY_ACTIONS:
            assert b.keys(profile, action), (profile, action)
    for table in b.pads:
        for action in bindings.PAD_ACTIONS:
            assert table[action] and all(isinstance(x, int) and 0 <= x < 64 for x in table[action])
    assert b.pad_shared in (True, False)


def test_a_damaged_action_keeps_its_default_and_the_others_are_read():
    b = Bindings.from_dict({"kb2": {"fire": ["no such key"], "left": ["j"]}})
    assert b.keys(KB2, "fire") == (pygame.K_SPACE, pygame.K_RCTRL) and b.keys(KB2, "left") == (pygame.K_j,)


def test_a_key_bound_twice_in_one_file_is_read_without_a_double_in_one_action():
    b = Bindings.from_dict({"kb2": {"fire": ["x", "x"]}})
    assert b.slots(KB2, "fire") == [pygame.K_x, None]


# ------------------------------------------------------------------------------------------------ the pad tables
def test_the_pad_buttons_are_toggled_added_removed_or_taken():
    b = Bindings()
    b.set_pad_buttons(0, "fire", [0, 2])
    assert b.toggle_button(0, "fire", 8) == "added" and b.pad_buttons(0, "fire") == (0, 2, 8)
    assert b.toggle_button(0, "fire", 2) == "removed" and b.pad_buttons(0, "fire") == (0, 8)
    assert b.toggle_button(0, "fire", 9) == "taken"                           # R3 was one of the three pause buttons
    assert b.pad_buttons(0, "fire") == (0, 8, 9) and b.pad_buttons(0, "pause") == (7, 6)
    assert b.find_button(0, 9) == "fire" and b.find_button(0, 9, skip="fire") is None


def test_a_pad_action_never_ends_up_without_a_button():
    b = Bindings()
    assert b.toggle_button(0, "phenix", 1) == "refused"                       # the only one
    assert b.toggle_button(0, "fire", 1) == "refused"                         # would empty Phenix
    assert b.pad_buttons(0, "phenix") == (1,)
    assert not b.set_pad_buttons(0, "fire", [])
    assert not b.set_pad_buttons(0, "fire", [1])                              # it would empty Phenix again
    assert b.pad_buttons(0, "fire") == (0, 2, 3, 5)


def test_at_most_four_buttons_per_action():
    b = Bindings()
    assert b.toggle_button(0, "fire", 8) == "refused"                         # already four
    assert len(b.pad_buttons(0, "fire")) == 4
    assert b.set_pad_buttons(0, "fire", [0, 2, 3, 5, 8, 7])
    assert b.pad_buttons(0, "fire") == (0, 2, 3, 5)


def test_the_pause_button_cannot_be_one_that_runs_the_menus():
    b = Bindings()
    for button in bindings.PAUSE_FORBIDDEN:
        assert b.toggle_button(0, "pause", button) == "refused"
    assert not b.set_pad_buttons(0, "pause", [0])
    assert b.toggle_button(0, "pause", 8) == "added"


def test_one_table_serves_every_pad_while_they_are_shared():
    b = Bindings()
    assert b.pad_shared and b.pad_table(0) == b.pad_table(1) == b.pad_table(3) == 0
    b.set_pad_buttons(1, "fire", [8])
    assert b.pad_buttons(0, "fire") == (8,)


def test_with_a_table_by_place_the_second_pad_starts_from_a_copy_and_goes_its_own_way():
    b = Bindings()
    b.set_pad_buttons(0, "fire", [0, 2])
    b.set_shared(False)
    assert b.pad_table(0) == 0 and b.pad_table(1) == 1 and b.pad_table(2) == 1
    assert b.pad_buttons(1, "fire") == (0, 2)
    b.set_pad_buttons(1, "fire", [3])
    assert b.pad_buttons(0, "fire") == (0, 2) and b.pad_buttons(1, "fire") == (3,)
    assert b.pad_is_modified(1, "fire") and not b.pad_is_modified(1, "pause")
    b.copy_pad(0, 1)
    assert b.pad_buttons(1, "fire") == (0, 2)
    b.set_shared(True)
    assert b.pad_table(1) == 0


def test_the_reset_of_a_pad_only_touches_its_own_table():
    b = Bindings()
    b.set_shared(False)
    b.set_pad_buttons(0, "fire", [0])
    b.set_pad_buttons(1, "fire", [2])
    b.reset_pad(1)
    assert b.pad_buttons(1, "fire") == (0, 2, 3, 5) and b.pad_buttons(0, "fire") == (0,)
    b.reset_pad()
    assert b.pad_buttons(0, "fire") == (0, 2, 3, 5)


def test_the_names_on_screen():
    assert bindings.key_label(pygame.K_LEFT, t) == "←" and bindings.key_label(pygame.K_UP, t) == "↑"
    assert bindings.key_label(pygame.K_q, t) == "Q" and bindings.key_label(pygame.K_5, t) == "5"
    assert bindings.key_label(None, t) == "—"
    assert bindings.key_label(pygame.K_SPACE, t) == t("key_space")
    assert bindings.key_label(pygame.K_LCTRL, t) == t("key_lctrl")
    assert [bindings.pad_label(i) for i in (0, 1, 2, 3, 7)] == ["A", "B", "X", "Y", "Start"]
    assert bindings.pad_label(12) == "#12"


# ================================================================================================ the settings file
def test_the_choices_are_saved_and_read_back(run):
    g = run.game
    bindings.current.set_key(KB2, "fire", 0, pygame.K_x)
    g.save_settings()
    data = json.load(open(user_settings.SETTINGS_FILE))
    assert data["bindings"] == {KB2: {"fire": ["x", "right ctrl"]}}
    bindings.load(None)
    assert bindings.current.keys(KB2, "fire") == (pygame.K_SPACE, pygame.K_RCTRL)
    game_init.init_settings(g, False)
    assert bindings.current.keys(KB2, "fire") == (pygame.K_x, pygame.K_RCTRL)


def test_nothing_is_written_when_nothing_changed(run):
    run.game.save_settings()
    assert json.load(open(user_settings.SETTINGS_FILE))["bindings"] == {}


def test_a_damaged_file_still_starts_the_game(run):
    json.dump({"bindings": {"kb1": 7, "pad": "oops"}}, open(user_settings.SETTINGS_FILE, "w"))
    game_init.init_settings(run.game, False)
    assert bindings.current.keys(KB1, "left") == (pygame.K_q, pygame.K_a)


# ================================================================================================ the ship obeys
def ship_on(run, scheme):
    g = run.game
    g.play_mode = "solo"
    g._begin_run()
    run.frames(5)
    g.paused = False
    ship = g.player
    ship.input_scheme = scheme
    ship.vertical_range = (100, 600)
    ship.invulnerable = 0
    return ship


def move(ship, *down):
    ship.x, ship.y = 600.0, 400.0
    ship.update(1 / 60, Keys(*down), "keyboard", None)
    return ship.x - 600.0, ship.y - 400.0


def test_the_ship_reads_the_keys_the_player_chose(run):
    ship = ship_on(run, "kb2")
    bindings.current.set_key(KB2, "left", 0, pygame.K_j)
    bindings.current.set_key(KB2, "up", 0, pygame.K_i)
    assert move(ship, pygame.K_j)[0] < 0
    assert move(ship, pygame.K_i)[1] < 0
    assert move(ship, pygame.K_LEFT) == (0.0, 0.0)                            # the old key does nothing any more
    assert move(ship, pygame.K_RIGHT)[0] > 0


def test_the_second_key_of_an_action_works_too(run):
    ship = ship_on(run, "kb2")
    bindings.current.set_key(KB2, "right", 1, pygame.K_k)
    assert move(ship, pygame.K_k)[0] > 0 and move(ship, pygame.K_RIGHT)[0] > 0


def test_each_keyboard_has_its_own_keys(run):
    ship = ship_on(run, "kb1")
    bindings.current.set_key(KB1, "right", 1, pygame.K_t)
    assert move(ship, pygame.K_t)[0] > 0
    ship.input_scheme = "kb2"
    assert move(ship, pygame.K_t) == (0.0, 0.0)                               # that was the left keyboard's
    ship.input_scheme = "solo"
    assert move(ship, pygame.K_RIGHT)[0] > 0                                  # solo uses the arrows keyboard
    bindings.current.set_key(KB2, "right", 0, pygame.K_l)
    assert move(ship, pygame.K_l)[0] > 0 and move(ship, pygame.K_RIGHT) == (0.0, 0.0)


def test_the_fire_key_is_the_one_chosen(run):
    ship = ship_on(run, "kb2")
    ship.autofire = False
    bindings.current.set_key(KB2, "fire", 0, pygame.K_x)
    bindings.current.set_key(KB2, "fire", 1, None)
    for key, fires in ((pygame.K_SPACE, False), (pygame.K_RCTRL, False), (pygame.K_x, True)):
        ship.shots = []
        ship._shoot_held = False
        ship.update(1 / 60, Keys(key), "keyboard", None)
        assert bool(ship.shots) is fires, key


def _phenix_calls(run, monkeypatch):
    hit = []
    monkeypatch.setattr(run.game, "_activate_phenix_from_input", lambda ship: hit.append(ship))
    run.game._special_keys = set()
    return hit


def test_the_phenix_key_is_the_one_chosen(run, monkeypatch):
    g = run.game
    ship_on(run, "kb2")
    hit = _phenix_calls(run, monkeypatch)
    bindings.current.set_key(KB2, "phenix", 1, pygame.K_p)
    run.key(pygame.K_RSHIFT, frames=1)
    run.keyup(pygame.K_RSHIFT)
    run.key(pygame.K_p, frames=1)
    assert hit == [g.player, g.player]
    bindings.current.set_key(KB2, "phenix", 0, None)
    run.keyup(pygame.K_p)
    run.key(pygame.K_RSHIFT, frames=1)
    assert len(hit) == 2                                                      # no longer a Phenix key


def test_a_held_phenix_key_does_not_repeat(run, monkeypatch):
    ship_on(run, "kb2")
    hit = _phenix_calls(run, monkeypatch)
    bindings.current.set_key(KB2, "phenix", 0, pygame.K_p)
    run.key(pygame.K_p, frames=1)
    run.key(pygame.K_p, frames=1)                                             # the key repeat of the system
    assert len(hit) == 1
    run.keyup(pygame.K_p)
    run.key(pygame.K_p, frames=1)
    assert len(hit) == 2


def test_the_left_keyboard_phenix_key_goes_to_the_coop_ship_on_it(run, monkeypatch):
    g = run.game
    g.coop_pref = [controls.KB_LEFT, controls.KB_ARROWS]
    g.ship_id, g.ship_id_p2 = "phoenix", "shield"
    g.play_mode = "coop"
    g._begin_run()
    run.frames(5)
    g.paused = False
    hit = _phenix_calls(run, monkeypatch)
    bindings.current.set_key(KB1, "phenix", 0, pygame.K_t)
    run.key(pygame.K_t, frames=1)
    run.key(pygame.K_RSHIFT, frames=1)
    assert hit == [g.player, g.player2]
    run.key(pygame.K_LSHIFT, frames=1)
    assert len(hit) == 2                                                      # the old key is free now


def test_a_solo_game_ignores_the_left_keyboard_phenix_key(run, monkeypatch):
    ship_on(run, "solo")
    hit = _phenix_calls(run, monkeypatch)
    run.key(pygame.K_LSHIFT, frames=1)
    assert hit == []


# ------------------------------------------------------------------------------------------------ the pads
def pad_fires(ship, joy, slot, button):
    joy.buttons = [i == button for i in range(len(joy.buttons))]
    ship.shots = []
    ship._shoot_held = False
    ship.pad_slot = slot
    ship.update(1 / 60, Keys(), "gamepad", joy)
    return bool(ship.shots)


def test_the_fire_buttons_of_the_pad_are_the_ones_chosen(run):
    from test_controls import FakeJoy
    ship = ship_on(run, "pad")
    ship.autofire = False
    joy = FakeJoy(10)
    assert [pad_fires(ship, joy, 0, b) for b in range(8)] == [True, False, True, True, False, True, False, False]
    bindings.current.set_pad_buttons(0, "fire", [6])
    assert [pad_fires(ship, joy, 0, b) for b in range(8)] == [False, False, False, False, False, False, True, False]


def test_each_place_has_its_own_fire_buttons_when_they_are_not_shared(run):
    from test_controls import FakeJoy
    ship = ship_on(run, "pad")
    ship.autofire = False
    joy = FakeJoy(10)
    bindings.current.set_shared(False)
    bindings.current.set_pad_buttons(1, "fire", [6])
    assert pad_fires(ship, joy, 0, 0) and not pad_fires(ship, joy, 0, 6)
    assert pad_fires(ship, joy, 1, 6) and not pad_fires(ship, joy, 1, 0)
    bindings.current.set_shared(True)
    assert pad_fires(ship, joy, 1, 0) and not pad_fires(ship, joy, 1, 6)


def test_the_ship_is_told_the_place_of_its_pad(run, bench):                  # noqa: F811
    a, b = bench.plug(), bench.plug()
    g = run.game
    controls.sync_game(g)
    g.coop_pref = ["pad2", "pad1"]
    g.ship_id, g.ship_id_p2 = "phoenix", "shield"
    g.play_mode = "coop"
    g._begin_run()
    run.frames(90)
    g.paused = False
    run.frames(2)
    assert controls.pad_id(g.player._joy) == b and controls.pad_id(g.player2._joy) == a
    assert (g.player.pad_slot, g.player2.pad_slot) == (1, 0)


def test_the_place_of_the_pad_that_was_pressed(run, bench):                  # noqa: F811
    a, b = bench.plug(), bench.plug()
    g = run.game
    controls.sync_game(g)

    def ev(**kw):
        return pygame.event.Event(pygame.JOYBUTTONDOWN, button=0, **kw)

    assert controls.slot_of(g, ev(instance_id=b, joy=0)) == 1                 # the instance wins over the index
    assert controls.slot_of(g, ev(instance_id=a, joy=1)) == 0
    assert controls.slot_of(g, ev(joy=1)) == 1
    assert controls.slot_of(g, ev(instance_id=999, joy=7)) == 0
    assert controls.slot_of(g, ev()) == 0


def pause_menu_setup(run):
    g = run.game
    g.play_mode = "solo"
    g._begin_run()
    run.frames(90)
    return g


def test_the_pause_button_is_the_one_chosen_in_a_game_and_start_in_the_menus(run):
    g = pause_menu_setup(run)
    g.paused = False
    bindings.current.set_pad_buttons(0, "pause", [8])
    run.button(8, frames=1)
    assert g.paused
    run.button(8, frames=1)
    assert not g.paused
    run.button(7, frames=1)                                                   # Start is not the pause button any more
    assert not g.paused


def test_a_pad_button_that_is_not_phenix_does_not_start_it(run, monkeypatch):
    g = pause_menu_setup(run)
    g.paused = False
    hit = _phenix_calls(run, monkeypatch)
    bindings.current.set_pad_buttons(0, "phenix", [8])
    run.button(1, frames=1)
    assert hit == []
    run.button(8, frames=1)
    assert hit == [g.player]


def test_the_main_menu_still_answers_to_start(run):
    g = run.game
    assert not g.started
    g.menu_screen = "options"
    bindings.current.set_pad_buttons(0, "pause", [8])
    run.button(7, frames=1)
    assert g.menu_screen != "options"                                         # Start goes back, whatever the setting


# ================================================================================================ the screen
def test_the_row_is_in_the_game_tab_and_opens_the_screen(run):
    g = run.game
    g._open_options()
    assert "keybinds" in g._options_spec() and g._option_label("keybinds") == t("opt_keybinds")
    st = open_from_options(run)
    assert st.mode == "list" and (st.tab, st.row, st.col) == (0, 0, 0)
    run.key(pygame.K_ESCAPE)
    assert not ks.is_open(g) and g.menu_screen == "options"                   # back on the options, not on the main menu


def test_it_opens_from_the_options_of_the_pause_too(run):
    g = pause_menu_setup(run)
    run.key(pygame.K_ESCAPE)
    run.key(pygame.K_DOWN)
    run.key(pygame.K_RETURN)
    assert g.pause_options
    g.opt_tab = 0
    g.menu_index = g._options_spec().index("keybinds")
    run.key(pygame.K_RETURN)
    assert ks.is_open(g)
    run.frames(3)                                                             # drawn over the paused game
    run.key(pygame.K_ESCAPE)
    assert not ks.is_open(g) and g.pause_options and g.paused


def test_the_enter_that_opens_the_screen_does_not_press_a_key_of_it(run):
    g = run.game
    g._open_options()
    g.menu_index = g._options_spec().index("keybinds")
    run.key(pygame.K_RETURN, frames=1)
    st = g.keybind
    assert st.mode == "list"
    run.key(pygame.K_RETURN, frames=1)                                        # still inside the grace time
    assert st.mode == "list"


def test_the_cursor_goes_round_the_rows_and_the_two_keys(run):
    st = open_from_options(run)
    run.key(pygame.K_UP, frames=1)
    assert st.row == len(ks.ROWS) - 1
    run.key(pygame.K_DOWN, frames=1)
    assert st.row == 0
    run.key(pygame.K_RIGHT, frames=1)
    assert st.col == 1
    run.key(pygame.K_LEFT, frames=1)
    run.key(pygame.K_LEFT, frames=1)
    assert st.col == 1
    go(run, st, "defaults")
    run.key(pygame.K_RIGHT, frames=1)
    assert st.col == 1                                                        # (nothing to choose on a button row)


def test_the_tabs_change_with_tab_and_the_page_keys(run):
    st = open_from_options(run)
    run.key(pygame.K_TAB, frames=1)
    assert st.tab == 1 and st.profile == KB2
    run.key(pygame.K_TAB, frames=1)
    assert st.tab == 2 and st.profile == bindings.PAD and st.is_pad            # the gamepad is the third tab
    run.key(pygame.K_TAB, frames=1)
    assert st.tab == 0
    run.key(pygame.K_TAB, frames=1, mod=pygame.KMOD_SHIFT)
    assert st.tab == 2
    run.key(pygame.K_PAGEUP, frames=1)
    assert st.tab == 1
    run.key(pygame.K_PAGEDOWN, frames=1)
    assert st.tab == 2


def test_a_key_is_chosen_with_enter_and_the_next_key_pressed(run):
    st = open_from_options(run)
    set_by_screen(run, st, "fire", 0, pygame.K_x)
    assert st.mode == "list" and bindings.current.slots(KB1, "fire") == [pygame.K_x, None]
    assert json.load(open(user_settings.SETTINGS_FILE))["bindings"][KB1]["fire"] == ["x", None]


def test_the_second_tab_changes_the_arrows_keyboard(run):
    st = open_from_options(run)
    run.key(pygame.K_TAB, frames=1)
    set_by_screen(run, st, "fire", 1, pygame.K_c)
    assert bindings.current.slots(KB2, "fire") == [pygame.K_SPACE, pygame.K_c]
    assert bindings.current.keys(KB1, "fire") == (pygame.K_LCTRL,)


def test_escape_while_waiting_changes_nothing_and_stays_on_the_screen(run):
    st = open_from_options(run)
    go(run, st, "fire")
    run.key(pygame.K_RETURN, frames=1)
    settled(run)
    run.key(pygame.K_ESCAPE, frames=1)
    assert st.mode == "list" and ks.is_open(run.game) and bindings.current.to_dict() == {}


def test_the_held_enter_is_not_taken_as_the_new_key(run):
    st = open_from_options(run)
    go(run, st, "fire")
    run.key(pygame.K_RETURN, frames=1)
    assert st.mode == "wait"
    run.key(pygame.K_RETURN, frames=1)                                        # (it is reserved anyway)
    assert st.mode == "wait"
    run.key(pygame.K_SPACE, frames=1)                                         # Space still held from the row: grace time
    assert st.mode == "wait"
    settled(run)
    run.key(pygame.K_SPACE, frames=1)
    assert st.mode in ("list", "conflict")


def test_a_reserved_key_is_refused_with_a_notice_and_the_wait_goes_on(run):
    st = open_from_options(run)
    go(run, st, "fire")
    run.key(pygame.K_RETURN, frames=1)
    settled(run)
    for key in (pygame.K_TAB, pygame.K_F5, pygame.K_CAPSLOCK):
        run.key(key, frames=1)
        assert st.mode == "wait" and st.flash and st.flash[0] == t("kb_flash_reserved")
        st.flash = None
    assert bindings.current.to_dict() == {}


def test_delete_clears_a_key_and_the_last_key_of_an_action_stays(run):
    st = open_from_options(run)
    go(run, st, "left", 1)
    run.key(pygame.K_DELETE, frames=1)
    assert bindings.current.slots(KB1, "left") == [pygame.K_q, None]
    go(run, st, "left", 0)
    run.key(pygame.K_DELETE, frames=1)
    assert bindings.current.slots(KB1, "left") == [pygame.K_q, None]
    assert st.flash and st.flash[0] == t("kb_flash_last")


def test_delete_while_waiting_clears_that_key(run):
    st = open_from_options(run)
    go(run, st, "up", 1)
    run.key(pygame.K_RETURN, frames=1)
    settled(run)
    run.key(pygame.K_DELETE, frames=1)
    assert st.mode == "list" and bindings.current.slots(KB1, "up") == [pygame.K_z, None]


def test_the_wait_gives_up_by_itself(run):
    st = open_from_options(run)
    go(run, st, "fire")
    run.key(pygame.K_RETURN, frames=1)
    ks.tick(run.game, ks.WAIT_SEC - 1)
    assert st.mode == "wait"
    ks.tick(run.game, 1.5)
    assert st.mode == "list" and bindings.current.to_dict() == {}


def test_the_flash_goes_out_by_itself(run):
    st = open_from_options(run)
    st.flash = ["x", 1.0]
    ks.tick(run.game, 1.5)
    assert st.flash is None


def test_a_key_in_use_asks_and_swapping_gives_the_other_action_the_old_key(run):
    st = open_from_options(run)
    set_by_screen(run, st, "fire", 0, pygame.K_d)                             # D is "right"
    assert st.mode == "conflict" and st.index == 0
    assert bindings.current.to_dict() == {}                                   # not done yet
    run.frames(2)
    settled(run)
    run.key(pygame.K_RETURN, frames=1)
    assert st.mode == "list"
    assert bindings.current.keys(KB1, "fire") == (pygame.K_d,)
    assert bindings.current.slots(KB1, "right") == [pygame.K_LCTRL, None]


def test_a_conflict_can_be_answered_no(run):
    st = open_from_options(run)
    set_by_screen(run, st, "fire", 0, pygame.K_d)
    run.key(pygame.K_DOWN, frames=1)
    assert st.index == 1
    settled(run)
    run.key(pygame.K_RETURN, frames=1)
    assert st.mode == "list" and bindings.current.to_dict() == {}
    set_by_screen(run, st, "fire", 0, pygame.K_d)
    run.key(pygame.K_ESCAPE, frames=1)
    assert st.mode == "list" and bindings.current.to_dict() == {}


def test_the_arrows_keyboard_keys_count_as_taken_when_setting_the_left_keyboard(run):
    st = open_from_options(run)
    set_by_screen(run, st, "fire", 0, pygame.K_LEFT)
    assert st.mode == "conflict" and st.conflict["other"][0] == KB2


def test_the_conflict_that_would_empty_an_action_is_refused_with_a_notice(run):
    st = open_from_options(run)
    set_by_screen(run, st, "fire", 1, pygame.K_d)                             # D: the only key of "right"... swap gives it
    settled(run)
    run.key(pygame.K_RETURN, frames=1)                                        # the empty slot goes to "right": it would be empty
    assert bindings.current.keys(KB1, "right") == (pygame.K_d,)
    assert st.flash and st.flash[0] == t("kb_flash_last")


def test_the_defaults_row_asks_and_the_chosen_answer_is_cancel(run):
    st = open_from_options(run)
    bindings.current.set_key(KB1, "fire", 0, pygame.K_x)
    bindings.current.set_key(KB2, "fire", 0, pygame.K_c)
    go(run, st, "defaults")
    run.key(pygame.K_RETURN, frames=1)
    assert st.mode == "reset" and st.index == 1
    settled(run)
    run.key(pygame.K_RETURN, frames=1)                                        # Enter at once: cancel
    assert st.mode == "list" and bindings.current.keys(KB1, "fire") == (pygame.K_x,)


def test_the_defaults_restore_only_the_keyboard_that_is_shown(run):
    st = open_from_options(run)
    bindings.current.set_key(KB1, "fire", 0, pygame.K_x)
    bindings.current.set_key(KB2, "fire", 0, pygame.K_c)
    go(run, st, "defaults")
    run.key(pygame.K_RETURN, frames=1)
    run.key(pygame.K_UP, frames=1)
    assert st.index == 0
    settled(run)
    run.key(pygame.K_RETURN, frames=1)
    assert bindings.current.keys(KB1, "fire") == (pygame.K_LCTRL,)
    assert bindings.current.slots(KB2, "fire")[0] == pygame.K_c               # the other keyboard keeps its changes
    assert json.load(open(user_settings.SETTINGS_FILE))["bindings"] == {KB2: {"fire": ["c", "right ctrl"]}}


def test_escape_on_the_list_goes_back_and_the_back_row_too(run):
    st = open_from_options(run)
    go(run, st, "back")
    run.key(pygame.K_RETURN, frames=1)
    assert not ks.is_open(run.game)


def test_the_hint_bar_follows_the_mode(run):
    import hint_bar
    st = open_from_options(run)
    assert ("del", "hint_clear") in hint_bar.menu_items(run.game)
    go(run, st, "defaults")
    assert ("del", "hint_clear") not in hint_bar.menu_items(run.game)
    st.mode = "wait"
    assert hint_bar.menu_items(run.game) == [("back", "hint_cancel"), ("del", "hint_clear")]
    st.mode = "reset"
    assert ("ud", "hint_choose") in hint_bar.menu_items(run.game)


# ------------------------------------------------------------------------------------------------ driven by a pad
def test_a_pad_drives_the_screen(run):
    st = open_from_options(run)
    run.button(5, frames=1)
    assert st.tab == 1
    run.button(4, frames=1)
    assert st.tab == 0
    pygame.event.post(pygame.event.Event(pygame.JOYHATMOTION, joy=0, instance_id=0, hat=0, value=(0, -1)))
    run.frames(1)
    assert st.row == 1
    pygame.event.post(pygame.event.Event(pygame.JOYHATMOTION, joy=0, instance_id=0, hat=0, value=(0, 0)))
    pygame.event.post(pygame.event.Event(pygame.JOYHATMOTION, joy=0, instance_id=0, hat=0, value=(1, 0)))
    run.frames(1)
    assert st.col == 1
    pygame.event.post(pygame.event.Event(pygame.JOYAXISMOTION, joy=0, instance_id=0, axis=1, value=0.9))
    run.frames(1)
    assert st.row == 2
    pygame.event.post(pygame.event.Event(pygame.JOYAXISMOTION, joy=0, instance_id=0, axis=1, value=0.95))
    run.frames(1)
    assert st.row == 2                                                        # a held stick counts once
    pygame.event.post(pygame.event.Event(pygame.JOYAXISMOTION, joy=0, instance_id=0, axis=1, value=0.0))
    run.frames(1)


def test_a_pad_sets_clears_and_goes_back(run):
    st = open_from_options(run)
    go(run, st, "fire", 1)
    run.button(0, frames=1)
    assert st.mode == "wait"
    run.button(0, frames=1)                                                   # A does not choose a key (only the keyboard does)
    assert st.mode == "wait"
    run.button(1, frames=1)                                                   # B cancels
    assert st.mode == "list"
    st.col = 0
    bindings.current.set_key(KB1, "left", 1, pygame.K_t)
    go(run, st, "left", 1)
    run.button(3, frames=1)                                                   # Y clears
    assert bindings.current.slots(KB1, "left") == [pygame.K_q, None]
    run.button(1, frames=1)
    assert not ks.is_open(run.game)


def test_while_the_screen_is_open_the_pad_does_not_pause_nor_start_phenix(run, monkeypatch):
    g = pause_menu_setup(run)
    g.paused = True
    g.pause_options = True
    g.menu_screen = "options"
    ks.open_screen(g)
    settled(run)
    hit = _phenix_calls(run, monkeypatch)
    run.button(1, frames=1)
    assert hit == [] and g.pause_options                                      # B closed the screen only
    assert not ks.is_open(g)


def test_while_the_screen_is_open_a_key_does_not_reach_the_game(run, monkeypatch):
    g = pause_menu_setup(run)
    hit = _phenix_calls(run, monkeypatch)
    g.paused = True
    g.pause_options = True
    g.menu_screen = "options"
    ks.open_screen(g)
    settled(run)
    run.key(pygame.K_RSHIFT, frames=1)
    assert hit == []


# ------------------------------------------------------------------------------------------------ drawing
@pytest.mark.parametrize("lang", LANG_CODES)
def test_every_mode_of_the_screen_draws_in_every_language(run, lang):
    g = run.game
    set_lang(lang)
    g.language = lang
    g._open_options()
    ks.open_screen(g)
    st = g.keybind
    bindings.current.set_key(KB1, "left", 1, None)
    bindings.current.set_key(KB2, "fire", 0, pygame.K_x)
    for tab in range(2):                                                      # (the keyboards: the gamepad has its own test)
        st.tab = tab
        for row in range(len(ks.ROWS)):
            for col in (0, 1):
                st.row, st.col = row, col
                for mode in ("list", "wait", "conflict", "reset"):
                    st.mode, st.index = mode, col
                    st.wait = (st.profile, ks.ACTION_ROWS[min(row, 5)], col)
                    st.conflict = {"key": pygame.K_d, "here": (st.profile, "fire", 0), "other": (KB1, "right", 0), "had": bool(col)}
                    st.flash = ["x" * 20, 1.0] if col else None
                    ks.draw(g)
                    top, bottom = st.layout
                    assert top <= bottom, (lang, tab, row, mode, st.layout)


def test_the_screen_is_drawn_by_the_game_loop_over_the_options_and_over_the_pause(run):
    open_from_options(run)
    run.frames(3)
    run.key(pygame.K_ESCAPE)
    g = pause_menu_setup(run)
    g.paused = True
    g.pause_options = True
    g.menu_screen = "options"
    ks.open_screen(g)
    run.frames(3)
    assert ks.is_open(g)


def test_every_text_of_the_screen_exists_in_all_languages():
    import i18n
    keys = [k for k in i18n.T if k.startswith(("kb_", "act_", "opt_keybinds", "opt_help_keybinds", "key_", "hint_key_",
                                              "hint_clear", "hint_done", "hint_pad_place"))]
    assert len(keys) >= 70
    for k in keys:
        for code in LANG_CODES:
            assert i18n.T[k].get(code), (k, code)
