"""Pads followed by their identifier, plugged and unplugged while playing, and the keyboards of the two players."""
import pygame
import pytest

import controls
from i18n import t
from test_smoke import run  # noqa: F401  (fixture)


class FakeJoy:
    """A pad as pygame shows it: a new object each time it is opened, the same instance id while it stays plugged."""

    def __init__(self, iid):
        self.iid = iid
        self.axes = [0.0, 0.0]
        self.buttons = [False] * 8

    def get_instance_id(self):
        return self.iid

    def get_id(self):
        return 0

    def init(self):
        pass

    def quit(self):
        pass

    def get_numaxes(self):
        return 2

    def get_axis(self, n):
        return self.axes[n]

    def get_numhats(self):
        return 0

    def get_numbuttons(self):
        return len(self.buttons)

    def get_button(self, n):
        return self.buttons[n]

    def rumble(self, *a):
        pass

    def stop_rumble(self):
        pass


class Bench:
    """The pads plugged in, in the order SDL lists them (the index)."""

    def __init__(self, monkeypatch):
        self.plugged = []
        self.next_id = 10
        monkeypatch.setattr(pygame.joystick, "get_count", lambda: len(self.plugged))
        monkeypatch.setattr(pygame.joystick, "Joystick", lambda i: FakeJoy(self.plugged[i]))

    def plug(self, at=None):
        iid = self.next_id
        self.next_id += 1
        if at is None:
            self.plugged.append(iid)
        else:
            self.plugged.insert(at, iid)
        return iid

    def unplug(self, iid):
        self.plugged.remove(iid)


@pytest.fixture
def bench(monkeypatch):
    return Bench(monkeypatch)


class Keys:
    """A keyboard state: only the keys listed are down."""

    def __init__(self, *down):
        self.down = set(down)

    def __getitem__(self, key):
        return key in self.down


# ------------------------------------------------------------------ the registry
def test_pads_are_followed_by_their_identifier_in_the_order_they_were_plugged(bench):
    a, b = bench.plug(), bench.plug()
    reg = controls.PadRegistry()
    added, removed = reg.refresh()
    assert reg.ids() == [a, b] and [controls.pad_id(p) for p in added] == [a, b] and removed == []
    first_b = reg.pads[1]
    bench.unplug(a)                                   # SDL now lists b at index 0
    added, removed = reg.refresh()
    assert reg.ids() == [b] and [controls.pad_id(p) for p in removed] == [a] and added == []
    assert reg.pads[0] is first_b                     # the same object: nothing was reopened
    c = bench.plug(at=0)                              # a new pad that SDL lists first
    reg.refresh()
    assert reg.ids() == [b, c]                        # but it comes after b: b is still the first player's


def test_a_refresh_with_nothing_new_changes_nothing(bench):
    bench.plug()
    reg = controls.PadRegistry()
    reg.refresh()
    before = list(reg.pads)
    added, removed = reg.refresh()
    assert added == [] and removed == [] and reg.pads == before


def test_has_and_index_of(bench):
    a, b = bench.plug(), bench.plug()
    reg = controls.PadRegistry()
    reg.refresh()
    assert reg.has(reg.pads[1]) and reg.index_of(reg.pads[1]) == 1 and reg.index_of(FakeJoy(a)) == 0
    assert not reg.has(None) and not reg.has(FakeJoy(999)) and reg.index_of(None) == -1


def test_clear_forgets_every_pad_and_the_next_refresh_opens_them_again(bench):
    bench.plug()
    reg = controls.PadRegistry()
    reg.refresh()
    old = reg.pads[0]
    reg.clear()
    assert reg.pads == []
    added, _ = reg.refresh()
    assert len(added) == 1 and added[0] is not old


def test_a_pad_that_cannot_be_opened_is_skipped(monkeypatch, bench):
    bench.plug()
    bench.plug()
    real = pygame.joystick.Joystick

    def flaky(i):
        if i == 0:
            raise pygame.error("busy")
        return real(i)

    monkeypatch.setattr(pygame.joystick, "Joystick", flaky)
    reg = controls.PadRegistry()
    reg.refresh()
    assert len(reg.pads) == 1


def test_sync_game_keeps_the_old_names_in_line(bench):
    a, b = bench.plug(), bench.plug()

    class G:
        pass

    g = G()
    controls.sync_game(g)
    assert g.joystick is g.pads.pads[0] and g.joysticks == g.pads.pads and g.gamepad_detected
    first = g.joystick
    bench.plug()
    controls.sync_game(g)
    assert g.joystick is first                        # a new pad does not take the first one's place
    bench.unplug(a)
    controls.sync_game(g)
    assert controls.pad_id(g.joystick) == b           # the one in use is gone: the next one takes over
    bench.unplug(b)
    bench.plugged.clear()
    controls.sync_game(g)
    assert g.joystick is None and g.joysticks == [] and not g.gamepad_detected


# ------------------------------------------------------------------ the coop bindings
def test_coop_gives_the_first_pad_to_player_one_and_the_second_to_player_two(run, bench):
    a, b = bench.plug(), bench.plug()
    g = run.game
    (s1, j1), (s2, j2) = g._coop_bindings()
    assert (s1, s2) == ("pad", "pad") and controls.pad_id(j1) == a and controls.pad_id(j2) == b


def test_coop_with_one_pad_or_none(run, bench):
    g = run.game
    (s1, _), (s2, j2) = g._coop_bindings()
    assert (s1, s2) == ("kb1", "kb2") and j2 is None
    bench.plug()
    (s1, j1), (s2, j2) = g._coop_bindings()
    assert s1 == "pad" and j1 is not None and s2 == "kb2" and j2 is None


def test_the_second_player_keeps_the_second_pad_when_the_first_one_is_replugged(run, bench):
    a, b = bench.plug(), bench.plug()
    g = run.game
    g._coop_bindings()
    bench.unplug(a)
    c = bench.plug()
    (s1, j1), (s2, j2) = g._coop_bindings()
    assert controls.pad_id(j1) == b and controls.pad_id(j2) == c          # b was first to stay, c came after


# ------------------------------------------------------------------ plugged and unplugged while playing
def _coop_run(run, bench, pads=2):
    ids = [bench.plug() for _ in range(pads)]
    g = run.game
    g.ship_id, g.ship_id_p2 = "phoenix", "shield"
    g.play_mode = "coop"
    g._begin_run()
    run.frames(5)
    g.paused = False
    return g, ids


def test_coop_unplugging_one_pad_stops_its_ship_and_pauses_saying_which_player(run, bench):
    g, (a, b) = _coop_run(run, bench)
    assert g.player._joy is not None and g.player2._joy is not None
    bench.unplug(b)
    g._poll_gamepad()
    assert g.paused and g.player2._joy is None and controls.pad_id(g.player._joy) == a
    assert g.cheat_msg == t("pad_unplugged_n").format(n=2) and g.cheat_kind == "pad"
    assert g.gamepad_detected                                  # the first player still has a pad


def test_coop_a_pad_plugged_in_again_goes_to_the_ship_without_one(run, bench):
    g, (a, b) = _coop_run(run, bench)
    bench.unplug(a)
    g._poll_gamepad()
    assert g.player._joy is None and g.paused and g.cheat_msg == t("pad_unplugged_n").format(n=1)
    c = bench.plug()
    g._poll_gamepad()
    assert controls.pad_id(g.player._joy) == c and controls.pad_id(g.player2._joy) == b


def test_coop_every_pad_unplugged_pauses_with_the_usual_message(run, bench):
    g, (a, b) = _coop_run(run, bench)
    bench.unplug(a)
    bench.unplug(b)
    g._poll_gamepad()
    assert g.paused and g.player._joy is None and g.player2._joy is None
    assert g.cheat_msg == t("pad_unplugged") and not g.gamepad_detected


def test_a_ship_on_an_unplugged_pad_is_not_moved_by_the_keys(run, bench, monkeypatch):
    import player as player_mod
    logged = []
    monkeypatch.setattr(player_mod, "log_exc", lambda *a, **k: logged.append(a))
    g, (a, b) = _coop_run(run, bench)
    bench.unplug(b)
    g._poll_gamepad()
    g.paused = False
    ship = g.player2
    x = ship.x
    keys = Keys(pygame.K_RIGHT, pygame.K_SPACE)
    for _ in range(30):
        ship.update(1 / 60, keys, "gamepad", None)
    assert ship.x == x and not ship.moving
    assert logged == []                                        # and nothing is written to errors.log every frame


def test_solo_with_its_only_pad_gone_falls_back_on_the_keys(run, bench):
    import update_play
    bench.plug()
    g = run.game
    g._poll_gamepad()
    g.play_mode = "solo"
    g._begin_run()
    run.frames(5)
    g.input_mode = "gamepad"
    bench.plugged.clear()
    g._poll_gamepad()
    g.paused = False
    g.input_grace = 0.0
    g.stage_transition = None
    x = g.player.x
    real = pygame.key.get_pressed
    pygame.key.get_pressed = lambda: Keys(pygame.K_RIGHT)
    try:
        for _ in range(20):
            g.dt = 1 / 60
            update_play.tick_ships(g)
    finally:
        pygame.key.get_pressed = real
    assert g.player.x > x


def test_solo_unplugging_the_only_pad_pauses(run, bench):
    a = bench.plug()
    g = run.game
    g._poll_gamepad()                                  # the pad is noticed on the menu
    g.play_mode = "solo"
    g._begin_run()
    run.frames(5)
    g.paused = False
    bench.unplug(a)
    g._poll_gamepad()
    assert g.paused and g.cheat_msg == t("pad_unplugged") and g.joystick is None


def test_solo_one_pad_of_two_gone_does_not_pause_and_the_other_takes_over(run, bench):
    a, b = bench.plug(), bench.plug()
    g = run.game
    g._poll_gamepad()
    g.play_mode = "solo"
    g._begin_run()
    run.frames(5)
    g.paused = False
    assert controls.pad_id(g.joystick) == a
    bench.unplug(a)
    g._poll_gamepad()
    assert not g.paused and controls.pad_id(g.joystick) == b


def test_a_pad_plugged_in_on_the_menu_becomes_the_control(run, bench):
    g = run.game
    g.input_mode = "keyboard"
    assert not g.started
    bench.plug()
    g._poll_gamepad()
    assert g.input_mode == "gamepad" and g.gamepad_detected
    bench.plugged.clear()
    g._poll_gamepad()
    assert g.input_mode == "keyboard" and not g.gamepad_detected


def test_rebinding_after_the_window_changed_opens_fresh_pads(run, bench):
    bench.plug()
    g = run.game
    controls.sync_game(g)
    old = g.joystick
    g._rebind_joystick()
    assert g.joystick is not None and g.joystick is not old and g.gamepad_detected


def test_releasing_the_pads_for_mame_forgets_them(run, bench):
    bench.plug()
    g = run.game
    controls.sync_game(g)
    g._release_joystick_for_mame()
    assert g.joystick is None and g.joysticks == [] and g.pads.pads == []


# ------------------------------------------------------------------ the keyboards: AZERTY and QWERTY alike
def _ship(run, scheme):
    ship = run.game.player
    ship.input_scheme = scheme
    ship.vertical_range = (100, 600)
    ship.invulnerable = 0
    return ship


def _move(ship, *down):
    keys = Keys(*down)
    ship.x, ship.y = 600.0, 400.0
    ship.update(1 / 60, keys, "keyboard", None)
    return ship.x - 600.0, ship.y - 400.0


def test_the_left_hand_keyboard_works_on_qwerty_and_on_azerty(run):
    """Left: A (QWERTY) or Q (AZERTY); up: W (QWERTY) or Z (AZERTY); right D; down S."""
    ship = _ship(run, "kb1")
    for left in (pygame.K_a, pygame.K_q):
        assert _move(ship, left)[0] < 0
    assert _move(ship, pygame.K_d)[0] > 0
    for up in (pygame.K_w, pygame.K_z):
        assert _move(ship, up)[1] < 0
    assert _move(ship, pygame.K_s)[1] > 0


def test_the_two_left_keys_do_the_same_thing(run):
    ship = _ship(run, "kb1")
    assert _move(ship, pygame.K_a) == _move(ship, pygame.K_q)
    assert _move(ship, pygame.K_w) == _move(ship, pygame.K_z)


def test_the_right_hand_keyboard_is_the_arrows(run):
    ship = _ship(run, "kb2")
    assert _move(ship, pygame.K_LEFT)[0] < 0 and _move(ship, pygame.K_RIGHT)[0] > 0
    assert _move(ship, pygame.K_UP)[1] < 0 and _move(ship, pygame.K_DOWN)[1] > 0
    assert _move(ship, pygame.K_a) == (0.0, 0.0)               # the left-hand keys do nothing for it


def test_the_left_hand_keyboard_ignores_the_arrows(run):
    ship = _ship(run, "kb1")
    assert _move(ship, pygame.K_LEFT, pygame.K_RIGHT) == (0.0, 0.0)
