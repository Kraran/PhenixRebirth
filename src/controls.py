"""Gamepads: which ones are plugged in, kept by their identifier (not by their index).

SDL numbers the pads by the order they were found (index 0, 1...), and that order changes when one of them is
unplugged and plugged again. Each pad also has an *instance id* that never changes while it stays plugged in, so
that is what the game follows. The registry keeps the pads in the order they were connected: the first one is the
first player's, the second one is the second player's (coop).

    registry.refresh()  -> (added, removed)     rescan after a JOYDEVICEADDED / JOYDEVICEREMOVED
    registry.pads                               the Joystick objects, in connection order
    sync_game(game)                             keeps game.pads, game.joysticks, game.joystick and
                                                game.gamepad_detected in line with the registry (the old names
                                                are still read all over the game)
"""
import pygame

from errlog import log_exc


def pad_id(joy):
    """The identifier of a pad: its instance id (pygame 2), else its index."""
    try:
        return joy.get_instance_id()
    except Exception:
        try:
            return joy.get_id()
        except Exception:
            return id(joy)


class PadRegistry:
    """The pads plugged in, in the order they were connected."""

    def __init__(self):
        self.pads = []

    def __len__(self):
        return len(self.pads)

    def clear(self):
        """Forget every pad (the window was rebuilt, or MAME takes the pads): the next refresh opens them again."""
        self.pads = []

    def ids(self):
        return [pad_id(p) for p in self.pads]

    def has(self, joy):
        """True when this pad is still plugged in."""
        if joy is None:
            return False
        pid = pad_id(joy)
        return any(pad_id(p) == pid for p in self.pads)

    def index_of(self, joy):
        """0 for the first pad, 1 for the second... or -1."""
        if joy is None:
            return -1
        pid = pad_id(joy)
        for i, p in enumerate(self.pads):
            if pad_id(p) == pid:
                return i
        return -1

    def refresh(self):
        """Rescan the pads. Returns (added, removed): the pads that appeared and the ones that are gone."""
        found = []
        try:
            pygame.joystick.init()
            for i in range(pygame.joystick.get_count()):
                try:
                    joy = pygame.joystick.Joystick(i)
                    joy.init()
                except Exception:
                    log_exc("controls.refresh")
                    continue
                found.append(joy)
        except Exception:
            log_exc("controls.refresh")
            found = []
        by_id = {}
        for joy in found:
            by_id.setdefault(pad_id(joy), joy)
        kept = []
        for old in self.pads:                       # the pads still there keep their place (and their object)
            pid = pad_id(old)
            if pid in by_id:
                kept.append(old)
                by_id.pop(pid)
        added = list(by_id.values())                # the new ones come after, in the order SDL lists them
        removed = [p for p in self.pads if not any(pad_id(p) == pad_id(k) for k in kept)]
        self.pads = kept + added
        return added, removed


def sync_game(game, rebuild=False):
    """Rescan the pads and keep the game's own names in line. `rebuild`: the old Joystick objects are dead (the
    window was recreated), open fresh ones. Returns (added, removed)."""
    reg = getattr(game, "pads", None)
    if reg is None:
        reg = game.pads = PadRegistry()
    if rebuild:
        reg.clear()
    added, removed = reg.refresh()
    game.joysticks = list(reg.pads)
    cur = getattr(game, "joystick", None)
    if cur is None or not reg.has(cur):
        game.joystick = reg.pads[0] if reg.pads else None   # the one in use is gone: the first one left takes over
    game.gamepad_detected = bool(reg.pads)
    return added, removed
