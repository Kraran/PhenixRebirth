"""The keys and the buttons of the ship, as the player set them (Options > Game > Keys and buttons).

Three profiles, each one a table "action -> what triggers it":

    "kb1"   the left-hand keyboard of a coop game (default Q/A, D, Z/W, S, Left Ctrl, Left Shift)
    "kb2"   the arrows keyboard: the solo game, the hot-seat and the right-hand player of a coop game
    "pad"   the gamepads (by place: the first pad plugged in has its own table, the second one too; while
            `pad_shared` is on the first table serves every pad)

A keyboard action has two slots (Q and A are both "left": the game works the same on an AZERTY and a QWERTY
keyboard), a pad action holds up to four buttons. The menus keep their own keys (arrows, Enter, Escape...): only what
flies the ship is here.

Only what differs from the defaults is written to settings.json (`to_dict`), so a default that is changed later
reaches everyone who did not touch it, and "reset" is just "forget the differences".

    bindings.current.keys("kb1", "left")        -> the key codes of an action (what the ship reads every frame)
    bindings.current.pad_buttons(0, "fire")     -> the buttons of the first pad's table
"""
import copy

import pygame

KB1, KB2, PAD = "kb1", "kb2", "pad"
KEY_PROFILES = (KB1, KB2)
KEY_ACTIONS = ("left", "right", "up", "down", "fire", "phenix", "missile")
PAD_ACTIONS = ("fire", "phenix", "missile", "pause")
SLOTS = 2                    # keys per keyboard action
PAD_MAX = 4                  # buttons per pad action
PAD_TABLES = 2               # the first pad, the second one (the others use the second table)

DEFAULT_KEYS = {
    KB1: {"left": [pygame.K_q, pygame.K_a], "right": [pygame.K_d, None], "up": [pygame.K_z, pygame.K_w],
          "down": [pygame.K_s, None], "fire": [pygame.K_LCTRL, None], "phenix": [pygame.K_LSHIFT, None],
          "missile": [pygame.K_e, None]},
    KB2: {"left": [pygame.K_LEFT, None], "right": [pygame.K_RIGHT, None], "up": [pygame.K_UP, None],
          "down": [pygame.K_DOWN, None], "fire": [pygame.K_SPACE, pygame.K_RCTRL], "phenix": [pygame.K_RSHIFT, None],
          "missile": [pygame.K_m, None]},
}
DEFAULT_PAD = {"fire": [0, 2, 3, 5], "phenix": [1], "missile": [4], "pause": [7, 9, 6]}   # 7 / 9 / 6: where "Start" is, by pad model
PAUSE_FORBIDDEN = (0, 1, 4, 5)       # A, B, LB, RB run the pause menu and the options: they cannot be "pause" too

# keys that cannot be given to the ship: they keep their job in the menus and for the game itself
_RESERVED = {pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB, pygame.K_BACKSPACE, pygame.K_DELETE,
             pygame.K_PAUSE, pygame.K_PRINTSCREEN, pygame.K_NUMLOCK, pygame.K_CAPSLOCK, pygame.K_SCROLLOCK,
             pygame.K_LGUI, pygame.K_RGUI, pygame.K_MENU, pygame.K_MODE}
_RESERVED.update(getattr(pygame, "K_F%d" % n) for n in range(1, 16) if hasattr(pygame, "K_F%d" % n))


def bindable(key):
    """True when this key can be given to an action of the ship."""
    try:
        key = int(key)
    except (TypeError, ValueError):
        return False
    return key > 0 and key not in _RESERVED and bool(pygame.key.name(key))


def key_name(code):
    """The name stored in settings.json for a key (None for an empty slot)."""
    return pygame.key.name(code) if code else None


def key_from_name(name):
    """The key code for a stored name, or None when it is not a key that can be bound any more."""
    try:
        code = pygame.key.key_code(str(name))
    except (ValueError, TypeError):
        return None
    return code if bindable(code) else None


class Bindings:
    def __init__(self):
        self.reset_all()

    # ---------------------------------------------------------------- the tables
    def reset_all(self):
        self.kb = copy.deepcopy(DEFAULT_KEYS)
        self.pads = [copy.deepcopy(DEFAULT_PAD) for _ in range(PAD_TABLES)]
        self.pad_shared = True

    def reset_keys(self, profile):
        self.kb[profile] = copy.deepcopy(DEFAULT_KEYS[profile])

    def reset_pad(self, slot=None):
        """Defaults for the table of the pad at this place (every table: None)."""
        for i in range(PAD_TABLES) if slot is None else (self.pad_table(slot),):
            self.pads[i] = copy.deepcopy(DEFAULT_PAD)

    # ---------------------------------------------------------------- keyboards
    def slots(self, profile, action):
        """The two slots of an action, a key code or None each."""
        return list(self.kb[profile][action])

    def keys(self, profile, action):
        """The keys that trigger the action (what the ship reads every frame)."""
        return tuple(k for k in self.kb[profile][action] if k)

    def default_slots(self, profile, action):
        return list(DEFAULT_KEYS[profile][action])

    def is_modified(self, profile, action):
        return self.kb[profile][action] != DEFAULT_KEYS[profile][action]

    def find_key(self, key, skip=None):
        """Where a key is already used: (profile, action, slot) or None. `skip`: a (profile, action, slot) to ignore."""
        for profile in KEY_PROFILES:
            for action in KEY_ACTIONS:
                for slot, k in enumerate(self.kb[profile][action]):
                    if k == key and (profile, action, slot) != skip:
                        return profile, action, slot
        return None

    def set_key(self, profile, action, slot, key, swap=False):
        """Give `key` to a slot (None empties it). A key already used elsewhere is refused (False) unless `swap`:
        then the other action gets what this slot had (or nothing if it was empty). An action always keeps at least
        one key: what would leave one without any is refused. Returns True when it was done."""
        if key is not None and not bindable(key):
            return False
        here = (profile, action, slot)
        old = self.kb[profile][action][slot]
        tmp = copy.deepcopy(self.kb)
        if key is not None:
            other = self.find_key(key, skip=here)
            if other is not None:
                if not swap:
                    return False
                tmp[other[0]][other[1]][other[2]] = old
        tmp[profile][action][slot] = key
        for p, a in {(profile, action), *(((other[0], other[1]),) if key is not None and other is not None else ())}:
            if not any(tmp[p][a]):
                return False
        self.kb = tmp
        self._tidy_keys(profile, action)
        return True

    def _tidy_keys(self, profile, action):
        """Two slots of one action never hold the same key (the second one is emptied)."""
        a = self.kb[profile][action]
        if a[0] is not None and a[0] == a[1]:
            a[1] = None

    # ---------------------------------------------------------------- pads
    def pad_table(self, slot):
        """The table number (0 / 1) that serves the pad at this place (the first plugged in is place 0)."""
        if self.pad_shared:
            return 0
        return 0 if int(slot) <= 0 else 1

    def pad_buttons(self, slot, action):
        """The buttons that trigger the action on the pad at this place."""
        return tuple(self.pads[self.pad_table(slot)][action])

    def default_pad_buttons(self, action):
        return tuple(DEFAULT_PAD[action])

    def pad_is_modified(self, slot, action):
        return list(self.pads[self.pad_table(slot)][action]) != DEFAULT_PAD[action]

    def find_button(self, slot, button, skip=None):
        """The action of this pad table that already uses the button, or None."""
        table = self.pads[self.pad_table(slot)]
        for action in PAD_ACTIONS:
            if action != skip and button in table[action]:
                return action
        return None

    def toggle_button(self, slot, action, button):
        """Press a button while setting an action: a button the action has is removed, another is added (at most
        PAD_MAX). A button of another action is taken from it. Returns what happened: "added", "removed", "taken",
        or "refused" (it would leave an action without any button, or the list is full)."""
        table = self.pads[self.pad_table(slot)]
        cur = table[action]
        if action == "pause" and button in PAUSE_FORBIDDEN:
            return "refused"
        if button in cur:
            if len(cur) <= 1:
                return "refused"
            table[action] = [b for b in cur if b != button]
            return "removed"
        if len(cur) >= PAD_MAX:
            return "refused"
        owner = [o for o in PAD_ACTIONS if o != action and button in table[o]]
        if any(len(table[o]) <= 1 for o in owner):
            return "refused"
        for o in owner:
            table[o] = [b for b in table[o] if b != button]
        table[action] = cur + [button]
        return "taken" if owner else "added"

    def set_pad_buttons(self, slot, action, buttons):
        """Replace the buttons of an action: the other actions lose the ones they shared. An action never ends up
        without a button (False, nothing changed)."""
        buttons = [b for i, b in enumerate(buttons) if b not in buttons[:i]][:PAD_MAX]
        if not buttons or (action == "pause" and any(b in PAUSE_FORBIDDEN for b in buttons)):
            return False
        table = self.pads[self.pad_table(slot)]
        for o in PAD_ACTIONS:
            if o != action and not [b for b in table[o] if b not in buttons]:
                return False
        for o in PAD_ACTIONS:
            if o != action:
                table[o] = [b for b in table[o] if b not in buttons]
        table[action] = list(buttons)
        return True

    def set_shared(self, shared):
        """"Same buttons for every pad": turned off, the second pad starts from a copy of the first one's table."""
        shared = bool(shared)
        if shared == self.pad_shared:
            return
        self.pad_shared = shared
        if not shared:
            self.pads[1] = copy.deepcopy(self.pads[0])

    def copy_pad(self, src_slot, dst_slot):
        self.pads[self.pad_table(dst_slot)] = copy.deepcopy(self.pads[self.pad_table(src_slot)])

    # ---------------------------------------------------------------- settings.json
    def to_dict(self):
        """Only what is not the default (an empty dict when nothing was changed)."""
        out = {}
        for profile in KEY_PROFILES:
            diff = {a: [key_name(k) for k in self.kb[profile][a]] for a in KEY_ACTIONS
                    if self.kb[profile][a] != DEFAULT_KEYS[profile][a]}
            if diff:
                out[profile] = diff
        pads = []
        for table in self.pads:
            pads.append({a: list(table[a]) for a in PAD_ACTIONS if table[a] != DEFAULT_PAD[a]})
        if any(pads):
            out[PAD] = pads
        if not self.pad_shared:
            out["pad_shared"] = False
        return out

    @classmethod
    def from_dict(cls, data):
        """Read what to_dict wrote. Whatever is wrong (a key that does not exist, an action unknown, a key given twice)
        is dropped and the default stays: a damaged file never stops the game."""
        b = cls()
        if not isinstance(data, dict):
            return b
        for profile in KEY_PROFILES:
            section = data.get(profile)
            if not isinstance(section, dict):
                continue
            for action in KEY_ACTIONS:
                names = section.get(action)
                if not isinstance(names, list) or not 1 <= len(names) <= SLOTS:
                    continue
                codes = [key_from_name(n) if n else None for n in names]
                if any(n and c is None for n, c in zip(names, codes)):
                    continue                              # a key that does not exist: keep the default
                codes += [None] * (SLOTS - len(codes))
                if not any(codes):
                    continue
                b.kb[profile][action] = codes
                b._tidy_keys(profile, action)
        tables = data.get(PAD)
        if isinstance(tables, list):
            for i, section in enumerate(tables[:PAD_TABLES]):
                if not isinstance(section, dict):
                    continue
                for action in PAD_ACTIONS:
                    vals = section.get(action)
                    if (isinstance(vals, list) and 1 <= len(vals) <= PAD_MAX
                            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 64 for v in vals)):
                        b.pads[i][action] = [v for j, v in enumerate(vals) if v not in vals[:j]]
        b.pad_shared = data.get("pad_shared", True) is not False
        return b


current = Bindings()


def load(data):
    """Make the settings read from settings.json the ones in force."""
    global current
    current = Bindings.from_dict(data)
    return current


# ------------------------------------------------------------------------------------------------ names on screen
_KEY_TEXT = {"space": "key_space", "left ctrl": "key_lctrl", "right ctrl": "key_rctrl",
             "left shift": "key_lshift", "right shift": "key_rshift", "left alt": "key_lalt", "right alt": "key_ralt"}
_ARROWS = {"left": "←", "right": "→", "up": "↑", "down": "↓"}


def key_label(code, t):
    """How a key is written on screen (`t`: the translation function)."""
    if not code:
        return "—"
    name = pygame.key.name(code)
    if name in _ARROWS:
        return _ARROWS[name]
    if name in _KEY_TEXT:
        return t(_KEY_TEXT[name])
    return name.upper() if len(name) > 1 or name.isalnum() else name


_PAD_NAMES = {0: "A", 1: "B", 2: "X", 3: "Y", 4: "LB", 5: "RB", 6: "Back", 7: "Start", 8: "L3", 9: "R3"}


def pad_label(button):
    """A pad button as the Xbox pads write it (the numbers the pad gives are those of an Xbox pad)."""
    return _PAD_NAMES.get(int(button), "#%d" % int(button))


# ------------------------------------------------------------------------------------- the help screen's texts
def help_values(t, bindings=None):
    """What the placeholders of the help texts stand for, from the keys and buttons in force.

    The solo game flies with the arrows keyboard ("kb2") and the first pad's table. `{kb_move}` is the first key of
    each direction, `{kb_fire}` / `{kb_phenix}` every key of the action, `{pad_fire}` / `{pad_pause}` the first
    button, `{pad_phenix}` every button of the action. `t` is the translation function (the names of some keys)."""
    b = bindings or current

    def keys(action):
        return " / ".join(key_label(k, t) for k in b.keys(KB2, action)) or "—"

    def first_key(action):
        ks = b.keys(KB2, action)
        return key_label(ks[0], t) if ks else "—"

    def buttons(action, only_first=False):
        bs = b.pad_buttons(0, action)
        if only_first:
            bs = bs[:1]
        return " / ".join(pad_label(x) for x in bs) or "—"

    return {
        "kb_move": " ".join(first_key(a) for a in ("left", "right", "up", "down")),
        "kb_fire": keys("fire"),
        "kb_phenix": keys("phenix"),
        "kb_missile": keys("missile"),
        "pad_fire": buttons("fire", True),
        "pad_pause": buttons("pause", True),
        "pad_phenix": buttons("phenix"),
        "pad_missile": buttons("missile"),
    }


class _Keep(dict):
    """format_map table that leaves an unknown {name} as it is instead of failing."""

    def __missing__(self, key):
        return "{" + key + "}"


def fill(line, values):
    """A help line with its {placeholders} filled in (a stray brace never raises)."""
    try:
        return str(line).format_map(_Keep(values))
    except (ValueError, IndexError, KeyError, AttributeError):
        return str(line)

