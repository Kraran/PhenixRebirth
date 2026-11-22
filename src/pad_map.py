"""Every pad speaks Xbox: a PlayStation or a Nintendo pad is given the button numbers of an Xbox pad.

The game reads the pads as SDL "joysticks", whose numbers depend on the pad: an Xbox pad gives A = 0, B = 1, X = 2,
Y = 3, LB = 4, RB = 5, Back = 6, Start = 7 and its cross as a hat; a DualShock 4 or a DualSense gives L1 = 9,
R1 = 10, Options = 6 and its cross as four buttons (11 to 14); a Switch Pro pad has its own order too. SDL knows, for
each pad it recognises, which of its numbers is "the bottom button", "the left shoulder", "the cross up"... (its game
controller mapping). This module reads that mapping once per pad and puts every pad in the Xbox order:

    - the events (`translate`): a button gets its Xbox number, a cross made of buttons moves a hat, the axes of the
      left stick are 0 and 1;
    - what the ship reads every frame (`wrap`): get_button(n), get_hat(0) and get_axis(n) of the Xbox pad.

The face buttons go by their place, not by their letter: the bottom one confirms on every pad (on a Switch pad the
one marked B, as SDL_GAMECONTROLLER_USE_BUTTON_LABELS = 0 asks; `setup_hints` before pygame.init). An Xbox pad, or a
pad SDL does not know, is left as it is.
"""
import os

import pygame

from errlog import log_exc

XBOX_BUTTONS = {"a": 0, "b": 1, "x": 2, "y": 3, "leftshoulder": 4, "rightshoulder": 5, "back": 6, "start": 7,
                "leftstick": 8, "rightstick": 9, "guide": 10}
XBOX_AXES = {"leftx": 0, "lefty": 1, "rightx": 2, "righty": 3, "lefttrigger": 4, "righttrigger": 5}
DPAD = {"dpup": (0, 1), "dpdown": (0, -1), "dpleft": (-1, 0), "dpright": (1, 0)}
UNMAPPED = 32          # a button the Xbox pad does not have (touchpad, capture...) is given 32 + its number: no action


def setup_hints():
    """Before pygame.init: the face buttons by their place on a Nintendo pad (bottom = confirm, as on the others)."""
    os.environ.setdefault("SDL_GAMECONTROLLER_USE_BUTTON_LABELS", "0")


def _parse(value):
    """'b9' -> ("b", 9, False); 'h0.4' -> ("h", (0, 4), False); 'a1~' / '-a1' / '+a1' -> ("a", 1, inverted)."""
    v = str(value or "").strip()
    inv = v.endswith("~")
    v = v.rstrip("~").lstrip("+-")
    if len(v) < 2 or v[0] not in "bha":
        return None
    try:
        if v[0] == "h":
            hat, mask = v[1:].split(".")
            return "h", (int(hat), int(mask)), inv
        return v[0], int(v[1:]), inv
    except ValueError:
        return None


class PadMap:
    """The Xbox order of one pad, from its SDL mapping {"a": "b0", "leftshoulder": "b9", "dpup": "b11"...}."""

    def __init__(self, mapping):
        self.buttons = {}          # raw button -> Xbox button
        self.raw_of = {}           # Xbox button -> raw button
        self.dpad_buttons = {}     # raw button -> (dx, dy) of the cross
        self.axes = {}             # raw axis -> (Xbox axis, inverted)
        self.raw_axis = {}         # Xbox axis -> (raw axis, inverted)
        for name, value in (mapping or {}).items():
            p = _parse(value)
            if p is None:
                continue
            kind, n, inv = p
            if name in XBOX_BUTTONS and kind == "b":
                self.buttons[n] = XBOX_BUTTONS[name]
                self.raw_of[XBOX_BUTTONS[name]] = n
            elif name in DPAD and kind == "b":
                self.dpad_buttons[n] = DPAD[name]
            elif name in XBOX_AXES and kind == "a":
                self.axes[n] = (XBOX_AXES[name], inv)
                self.raw_axis[XBOX_AXES[name]] = (n, inv)
        self.identity = (all(raw == x for raw, x in self.buttons.items()) and not self.dpad_buttons
                         and all(raw == x and not inv for raw, (x, inv) in self.axes.items()))

    def button(self, raw):
        """The Xbox number of a raw button (UNMAPPED + raw for a button the Xbox pad does not have)."""
        return self.buttons.get(raw, UNMAPPED + raw)

    def axis(self, raw):
        """(Xbox axis, inverted) of a raw axis (8 + raw for an axis the Xbox pad does not have)."""
        return self.axes.get(raw, (8 + raw, False))


def mapping_of(joy):
    """The SDL game controller mapping of a pad, or None (not a pad SDL knows, or no controller module)."""
    try:
        from pygame._sdl2 import controller
        if not controller.get_init():
            controller.init()
            controller.set_eventstate(False)  # (the game reads the joystick events: no second copy of each press)
        inst = joy.get_instance_id()
        for i in range(pygame.joystick.get_count()):
            if pygame.joystick.Joystick(i).get_instance_id() != inst:
                continue
            if not controller.is_controller(i):
                return None
            c = controller.Controller(i)
            mapping = c.get_mapping()
            _keep.append(c)                  # (kept open: closing it could close the pad the game reads)
            return mapping
    except Exception:
        log_exc("pad_map.mapping_of")
    return None


_keep = []


class Pad:
    """A pad read in the Xbox order (everything it does not change goes to the real pad)."""

    def __init__(self, joy, pmap):
        self._joy = joy
        self.map = pmap
        self.held = set()          # the raw buttons of the cross held down (from the events)

    def __getattr__(self, name):
        return getattr(self._joy, name)

    def get_numbuttons(self):
        return max(len(XBOX_BUTTONS), self._joy.get_numbuttons())

    def get_button(self, n):
        raw = self.map.raw_of.get(int(n))
        return bool(raw is not None and raw < self._joy.get_numbuttons() and self._joy.get_button(raw))

    def get_numhats(self):
        return 1 if self.map.dpad_buttons else self._joy.get_numhats()

    def get_hat(self, n):
        if not self.map.dpad_buttons:
            return self._joy.get_hat(n)
        if n != 0:
            return (0, 0)
        return dpad_value(self.map, lambda raw: self._joy.get_button(raw))

    def get_numaxes(self):
        return max(6, self._joy.get_numaxes()) if self.map.raw_axis else self._joy.get_numaxes()

    def get_axis(self, n):
        raw = self.map.raw_axis.get(int(n))
        if raw is None:
            return self._joy.get_axis(n) if not self.map.raw_axis and n < self._joy.get_numaxes() else 0.0
        v = self._joy.get_axis(raw[0])
        return -v if raw[1] else v


def dpad_value(pmap, pressed):
    """The hat (x, y) of a cross made of buttons; `pressed(raw)` tells whether a raw button is held."""
    x = y = 0
    for raw, (dx, dy) in pmap.dpad_buttons.items():
        try:
            if pressed(raw):
                x += dx
                y += dy
        except Exception:
            pass
    return (max(-1, min(1, x)), max(-1, min(1, y)))


def wrap(joy):
    """The pad itself when it already speaks Xbox (or SDL does not know it), else a Pad in the Xbox order."""
    if joy is None or isinstance(joy, Pad):
        return joy
    mapping = mapping_of(joy)
    if not mapping:
        return joy
    pmap = PadMap(mapping)
    if pmap.identity or not pmap.buttons:
        return joy
    return Pad(joy, pmap)


def translate(events, pads):
    """The events of the pads in the Xbox order. `pads`: the pads of the game (controls.PadRegistry.pads)."""
    maps = {}
    for p in pads or ():
        if isinstance(p, Pad):
            try:
                maps[p.get_instance_id()] = p
            except Exception:
                pass
    if not maps:
        return events
    out = []
    for e in events:
        pad = maps.get(getattr(e, "instance_id", None)) if e.type in _PAD_EVENTS else None
        if pad is None:
            out.append(e)
            continue
        pmap = pad.map
        if e.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
            if e.button in pmap.dpad_buttons:
                down = e.type == pygame.JOYBUTTONDOWN
                (pad.held.add if down else pad.held.discard)(e.button)
                value = dpad_value(pmap, lambda raw: raw in pad.held)
                out.append(pygame.event.Event(pygame.JOYHATMOTION, {
                    "instance_id": e.instance_id, "joy": getattr(e, "joy", 0), "hat": 0, "value": value}))
            else:
                out.append(pygame.event.Event(e.type, dict(e.dict, button=pmap.button(e.button))))
        elif e.type == pygame.JOYAXISMOTION and pmap.axes:
            axis, inv = pmap.axis(e.axis)
            out.append(pygame.event.Event(e.type, dict(e.dict, axis=axis, value=-e.value if inv else e.value)))
        else:
            out.append(e)
    return out


_PAD_EVENTS = (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYAXISMOTION, pygame.JOYHATMOTION)
