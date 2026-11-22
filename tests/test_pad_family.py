"""PlayStation and Nintendo pads: every pad in the Xbox order (src/pad_map.py) and the buttons drawn and named as the
pad in use shows them (src/pad_style.py)."""
import pygame
import pytest

import bindings
import hint_bar
import i18n
import keybind_pad
import pad_map
import pad_style
from pad_map import PadMap, Pad, UNMAPPED

# the SDL mapping of a DualShock 4 / DualSense (HIDAPI): the cross as four buttons, L1 = 9, Options = 6
PS_MAPPING = {"a": "b0", "b": "b1", "x": "b2", "y": "b3", "back": "b4", "guide": "b5", "start": "b6",
              "leftstick": "b7", "rightstick": "b8", "leftshoulder": "b9", "rightshoulder": "b10", "dpup": "b11",
              "dpdown": "b12", "dpleft": "b13", "dpright": "b14", "leftx": "a0", "lefty": "a1", "rightx": "a2",
              "righty": "a3", "lefttrigger": "a4", "righttrigger": "a5", "touchpad": "b15"}
# an Xbox pad (XInput): already in the order
XBOX_MAPPING = {"a": "b0", "b": "b1", "x": "b2", "y": "b3", "back": "b6", "guide": "b10", "start": "b7",
                "leftstick": "b8", "rightstick": "b9", "leftshoulder": "b4", "rightshoulder": "b5", "dpup": "h0.1",
                "dpdown": "h0.4", "dpleft": "h0.8", "dpright": "h0.2", "leftx": "a0", "lefty": "a1", "rightx": "a2",
                "righty": "a3", "lefttrigger": "a4", "righttrigger": "a5"}
# a Switch Pro pad, face buttons by their place (SDL_GAMECONTROLLER_USE_BUTTON_LABELS = 0), the cross as a hat
SWITCH_MAPPING = {"a": "b0", "b": "b1", "x": "b2", "y": "b3", "back": "b4", "guide": "b5", "start": "b6",
                  "leftstick": "b7", "rightstick": "b8", "leftshoulder": "b9", "rightshoulder": "b10",
                  "dpup": "h0.1", "dpdown": "h0.4", "dpleft": "h0.8", "dpright": "h0.2", "leftx": "a0",
                  "lefty": "a1~", "rightx": "a2", "righty": "a3"}


class FakeJoy:
    def __init__(self, name="Pad", inst=7, buttons=16, axes=6, hats=0):
        self.name, self.inst = name, inst
        self.down = set()
        self.axes = [0.0] * axes
        self.hats = [(0, 0)] * hats
        self.nb = buttons

    def get_instance_id(self):
        return self.inst

    def get_name(self):
        return self.name

    def get_numbuttons(self):
        return self.nb

    def get_button(self, i):
        return i in self.down

    def get_numaxes(self):
        return len(self.axes)

    def get_axis(self, i):
        return self.axes[i]

    def get_numhats(self):
        return len(self.hats)

    def get_hat(self, i):
        return self.hats[i]

    def rumble(self, *a):
        return True


@pytest.fixture(autouse=True)
def _xbox_after():
    yield
    pad_style.current = pad_style.XBOX
    pad_style.forget()
    hint_bar._cache.clear()
    keybind_pad._cache.clear()
    i18n.set_lang("fr")


# ------------------------------------------------------------------ which pad
@pytest.mark.parametrize("name,family", [
    ("PS4 Controller", "playstation"), ("Sony Interactive Entertainment Wireless Controller", "playstation"),
    ("DualShock 3", "playstation"), ("DualSense Wireless Controller", "playstation5"), ("PS5 Controller", "playstation5"),
    ("Nintendo Switch Pro Controller", "nintendo"), ("Joy-Con (L/R)", "nintendo"),
    ("Xbox Series X Controller", "xbox"), ("Controller (XBOX 360 For Windows)", "xbox"), ("", "xbox"), (None, "xbox"),
])
def test_the_family_of_a_pad_from_its_name(name, family):
    assert pad_style.family_for_name(name) == family


def test_the_family_of_the_pad_in_use():
    class G:
        joystick = FakeJoy("DualSense Wireless Controller", inst=1)
    assert pad_style.note_game(G()) == "playstation5" and pad_style.current == "playstation5"
    G.joystick = None
    assert pad_style.note_game(G()) == "xbox"


# ------------------------------------------------------------------ the Xbox order
def test_a_playstation_pad_gets_the_numbers_of_an_xbox_pad():
    m = PadMap(PS_MAPPING)
    assert not m.identity
    assert [m.button(r) for r in (0, 1, 2, 3, 9, 10, 4, 6, 7, 8, 5)] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert m.button(15) == UNMAPPED + 15                  # the touchpad: nothing
    assert m.dpad_buttons == {11: (0, 1), 12: (0, -1), 13: (-1, 0), 14: (1, 0)}


def test_an_xbox_pad_is_left_as_it_is(monkeypatch):
    assert PadMap(XBOX_MAPPING).identity
    joy = FakeJoy("Xbox Series X Controller")
    monkeypatch.setattr(pad_map, "mapping_of", lambda j: XBOX_MAPPING)
    assert pad_map.wrap(joy) is joy
    monkeypatch.setattr(pad_map, "mapping_of", lambda j: None)        # a pad SDL does not know: as it is
    assert pad_map.wrap(joy) is joy


def test_what_the_ship_reads_on_a_playstation_pad(monkeypatch):
    joy = FakeJoy("PS4 Controller")
    monkeypatch.setattr(pad_map, "mapping_of", lambda j: PS_MAPPING)
    pad = pad_map.wrap(joy)
    assert isinstance(pad, Pad) and pad.get_instance_id() == 7 and pad.get_name() == "PS4 Controller"
    joy.down = {9}                                         # L1
    assert pad.get_button(4) and not pad.get_button(0)     # = LB
    joy.down = {0, 6}                                      # cross + Options
    assert pad.get_button(0) and pad.get_button(7) and not pad.get_button(6)
    assert pad.get_numhats() == 1 and pad.get_hat(0) == (0, 0)
    joy.down = {11, 13}                                    # the cross: up + left
    assert pad.get_hat(0) == (-1, 1)
    joy.axes[0], joy.axes[1] = 0.8, -0.5
    assert (pad.get_axis(0), pad.get_axis(1)) == (0.8, -0.5)
    assert pad.rumble(0.5, 0.5, 100)                       # what it does not change goes to the real pad


def test_an_inverted_axis_is_put_right(monkeypatch):
    joy = FakeJoy("Nintendo Switch Pro Controller", hats=1)
    monkeypatch.setattr(pad_map, "mapping_of", lambda j: SWITCH_MAPPING)
    pad = pad_map.wrap(joy)
    joy.axes[1] = 0.6
    assert pad.get_axis(1) == -0.6
    joy.hats[0] = (1, 0)                                   # its cross is a hat: read as it is
    assert pad.get_hat(0) == (1, 0)
    joy.down = {10}
    assert pad.get_button(5)                               # R = RB


def _ev(kind, **kw):
    return pygame.event.Event(kind, dict(kw, instance_id=7, joy=0))


def test_the_events_of_a_playstation_pad(monkeypatch):
    monkeypatch.setattr(pad_map, "mapping_of", lambda j: PS_MAPPING)
    pad = pad_map.wrap(FakeJoy("PS4 Controller"))
    other = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_a})
    evs = pad_map.translate([
        _ev(pygame.JOYBUTTONDOWN, button=9), other, _ev(pygame.JOYBUTTONDOWN, button=6),
        _ev(pygame.JOYBUTTONDOWN, button=11), _ev(pygame.JOYBUTTONDOWN, button=14), _ev(pygame.JOYBUTTONUP, button=11),
        _ev(pygame.JOYBUTTONUP, button=14), _ev(pygame.JOYBUTTONDOWN, button=15), _ev(pygame.JOYAXISMOTION, axis=1, value=0.9),
    ], [pad])
    assert evs[0].type == pygame.JOYBUTTONDOWN and evs[0].button == 4 and evs[0].instance_id == 7     # L1 = LB
    assert evs[1] is other
    assert evs[2].button == 7                                                                          # Options = Start
    hats = [e.value for e in evs[3:7]]
    assert all(e.type == pygame.JOYHATMOTION and e.hat == 0 for e in evs[3:7])
    assert hats == [(0, 1), (1, 1), (1, 0), (0, 0)]
    assert evs[7].button == UNMAPPED + 15
    assert evs[8].axis == 1 and evs[8].value == 0.9


def test_the_events_of_an_xbox_pad_are_not_touched():
    joy = FakeJoy("Xbox")
    evs = [_ev(pygame.JOYBUTTONDOWN, button=4)]
    assert pad_map.translate(evs, [joy]) is evs


def test_the_registry_wraps_a_playstation_pad(monkeypatch):
    import controls
    joy = FakeJoy("PS4 Controller", inst=3)
    monkeypatch.setattr(pygame.joystick, "init", lambda: None)
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 1)
    joy.init = lambda: None
    monkeypatch.setattr(pygame.joystick, "Joystick", lambda i: joy)
    monkeypatch.setattr(pad_map, "mapping_of", lambda j: PS_MAPPING)
    reg = controls.PadRegistry()
    added, removed = reg.refresh()
    assert len(reg.pads) == 1 and isinstance(reg.pads[0], Pad) and added == reg.pads
    assert reg.refresh() == ([], []) and isinstance(reg.pads[0], Pad)     # kept, not wrapped twice


def test_setup_hints_asks_for_the_buttons_by_their_place(monkeypatch):
    monkeypatch.delenv("SDL_GAMECONTROLLER_USE_BUTTON_LABELS", raising=False)
    pad_map.setup_hints()
    import os
    assert os.environ["SDL_GAMECONTROLLER_USE_BUTTON_LABELS"] == "0"


# ------------------------------------------------------------------ what is drawn and written
def test_the_names_of_the_buttons():
    i18n.set_lang("fr")
    assert [pad_style.label(b, "xbox") for b in (0, 1, 4, 5, 6, 7)] == ["A", "B", "LB", "RB", "Back", "Start"]
    assert [pad_style.label(b, "playstation") for b in (0, 1, 2, 3, 4, 5, 6, 7)] == [
        "Croix", "Rond", "Carré", "Triangle", "L1", "R1", "Share", "Options"]
    assert pad_style.label(6, "playstation5") == "Create"
    assert [pad_style.label(b, "nintendo") for b in (0, 1, 2, 3, 4, 5, 6, 7)] == ["B", "A", "Y", "X", "L", "R", "−", "+"]
    i18n.set_lang("en")
    assert pad_style.label(0, "playstation") == "Cross"
    pad_style.current = "nintendo"
    assert bindings.pad_label(0) == "B" and bindings.pad_label(4, "xbox") == "LB"


def test_the_help_texts_name_the_buttons_of_the_pad_in_use():
    i18n.set_lang("en")
    pad_style.current = "playstation"
    vals = bindings.help_values(i18n.t, bindings.Bindings())
    assert "Cross" in vals["pad_fire"] and "Options" in vals["pad_pause"]


def test_the_face_buttons_are_drawn_for_each_pad():
    pygame.font.init()
    font = pygame.font.Font(None, 16)
    looks = {}
    for fam in pad_style.FAMILIES:
        for b in (0, 1, 2, 3):
            s = pad_style.face_surface(b, 26, fam, font)
            assert s.get_size() == (26, 26)
            looks[(fam, b)] = pygame.image.tobytes(s, "RGBA")
    assert pad_style.face_surface(4, 26, "xbox", font) is None
    assert len({looks[("playstation", b)] for b in range(4)}) == 4                 # four different symbols
    assert looks[("playstation", 0)] != looks[("xbox", 0)] != looks[("nintendo", 0)]
    ps_cross = pad_style.face_surface(0, 26, "playstation")
    assert ps_cross.get_at((13, 13))[:3] == pad_style.PLAYSTATION_COLORS[0]       # the centre of the cross


def test_the_help_bar_follows_the_pad_in_use():
    items = (("ok", "hint_ok"), ("back", "hint_back"), ("sh", "hint_ok"))
    pics = {}
    for fam in ("xbox", "playstation", "nintendo"):
        pad_style.current = fam
        pics[fam] = pygame.image.tobytes(hint_bar.render(items, True), "RGBA")
    assert len(set(pics.values())) == 3
    pad_style.current = "playstation"
    kb = hint_bar.render(items, False)
    pad_style.current = "xbox"
    assert hint_bar.render(items, False) is kb                                  # the keyboard does not change


def test_the_message_of_the_menu_buttons():
    i18n.set_lang("fr")
    pad_style.current = "playstation"
    assert keybind_pad.menu_buttons_text(i18n.t("kb_flash_pad_pause")) == (
        "Croix, Rond, L1 et R1 servent aux menus : choisis un autre bouton.")
    pad_style.current = "xbox"
    assert keybind_pad.menu_buttons_text(i18n.t("kb_flash_pad_pause")) == i18n.t("kb_flash_pad_pause")
    for lang in i18n.LANG_CODES:
        i18n.set_lang(lang)
        pad_style.current = "nintendo"
        assert keybind_pad.menu_buttons_text(i18n.t("kb_flash_pad_pause")).startswith("B, A, L ")


def test_the_pad_screen_draws_the_pad_in_use(run):
    pad_style.current = "playstation"
    ps = pygame.image.tobytes(keybind_pad._pad_surface(), "RGBA")
    pad_style.current = "xbox"
    assert pygame.image.tobytes(keybind_pad._pad_surface(), "RGBA") != ps
    assert keybind_pad._chip_images(run.game, [0, 4, 7], 30)


from test_smoke import run  # noqa: E402,F401  (fixture)
