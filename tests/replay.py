"""
Deterministic replay of scripted games, used to prove that a refactoring of
game.py did not change the gameplay.

A scenario starts a run, then feeds fixed "key presses" frame by frame
(always dt = 1/60) and, every few frames, computes a short fingerprint of the
whole game state (ships, enemies, bullets, boss, score, stage...) and of the
random-number generator. If the logic changes in any way - even one random()
call more or less - the fingerprints no longer match the saved ones.

Run `python tests/replay.py tests/golden_replay.json` to (re)create the saved
fingerprints. Only do this when a gameplay change is intended.
"""
import json
import os
import random
import sys
import zlib

import pygame

SAMPLE_EVERY = 10  # frames between two fingerprints
DT = 1 / 60


class _Keys:
    """Stand-in for pygame.key.get_pressed()."""

    def __init__(self, pressed=()):
        self.pressed = set(pressed)

    def __getitem__(self, key):
        return key in self.pressed


def _r(v):
    try:
        return round(float(v), 3)
    except Exception:
        return 0.0


def _ship_state(s):
    return (
        _r(getattr(s, "x", 0)), _r(getattr(s, "y", 0)),
        int(getattr(s, "lives", 0) or 0), bool(getattr(s, "alive", True)),
        _r(getattr(s, "phenix_gauge", 0)), len(getattr(s, "shots", []) or []),
        _r(getattr(s, "phenix_timer", 0)), _r(getattr(s, "phenix_cooldown", 0)),
        int(getattr(s, "shield_flash", 0) or 0),
    )


def fingerprint(g):
    parts = [
        int(g.score), int(g.stage), bool(g.game_over), bool(g.started),
        str(g.stage_transition), len(g.explosions), _r(g.shake_amount),
        bool(getattr(g, "paused", False)), str(g.menu_screen),
        [_ship_state(s) for s in g._ships()],
    ]
    f = g.formation
    enemies = getattr(f, "enemies", []) or []
    parts.append([(_r(e.x), _r(e.y), bool(getattr(e, "alive", True))) for e in enemies])
    parts.append([(_r(b.x), _r(b.y)) for b in getattr(f, "bullets", []) or []])
    b = g.boss_saucer
    if b is None:
        parts.append(None)
    else:
        cells = getattr(b, "cells", []) or []
        parts.append((bool(b.alive), len(cells), sum(1 for c in cells if getattr(c, "alive", True))))
    parts.append(zlib.crc32(repr(random.getstate()).encode()))
    return "%08x" % (zlib.crc32(repr(parts).encode()) & 0xFFFFFFFF)


def _target_x(g):
    """x to aim at: nearest living enemy, else the boss armour, else centre."""
    b = g.boss_saucer
    if b is not None and getattr(b, "alive", False):
        xs = [c.x for c in getattr(b, "cells", []) or [] if getattr(c, "alive", True)]
        if xs:
            return sum(xs) / len(xs) + float(getattr(b, "offset_x", 0.0) or 0.0)
    enemies = [e for e in getattr(g.formation, "enemies", []) or [] if getattr(e, "alive", True)]
    if enemies:
        return max(enemies, key=lambda e: e.y).x
    return 640.0


def _pressed(g, frame):
    """Scripted input: autopilot for P1 (arrows + space), sweep for P2 (A/D + ctrl)."""
    pressed = set()
    ships = g._ships()
    if ships:
        dx = _target_x(g) - float(getattr(ships[0], "x", 640))
        if dx < -12:
            pressed.add(pygame.K_LEFT)
        elif dx > 12:
            pressed.add(pygame.K_RIGHT)
        if (frame // 5) % 4 != 3:
            pressed.add(pygame.K_SPACE)
    phase = (frame // 50) % 4
    if phase == 0:
        pressed.add(pygame.K_a)
    elif phase == 2:
        pressed.add(pygame.K_d)
    if (frame // 6) % 3 != 2:
        pressed.add(pygame.K_LCTRL)
    return pressed


def _press(key):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0))


def _release(key):
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key, mod=0))


def _new_game(seed):
    from game import Game

    random.seed(seed)
    g = Game()
    g._intro_done = True
    g.fade_phase = None
    return g


def run_scenario(name, frames, setup, events=None, stage_jumps=None, god=False):
    """Return the list of fingerprints for one scripted game."""
    g = _new_game(hash_seed(name))
    clock = {"frame": 0}
    real_ticks, real_pressed = pygame.time.get_ticks, pygame.key.get_pressed
    pygame.time.get_ticks = lambda: int(clock["frame"] * 1000 * DT)
    current = {"keys": _Keys()}
    pygame.key.get_pressed = lambda: current["keys"]
    out = []
    try:
        setup(g)
        for f in range(frames):
            if god:
                for ship in g._ships():
                    ship.infinite_lives = True
            clock["frame"] = f
            current["keys"] = _Keys(_pressed(g, f))
            if stage_jumps and f in stage_jumps:
                s = stage_jumps[f]
                g.stage = s
                g._setup_stage(s)
                g.stage_transition = None
            if events and f in events:
                for ship in g._ships():
                    ship.phenix_gauge = 10.0   # make the special move available
                _press(events[f])
            if events and (f - 3) in events:
                _release(events[f - 3])   # the game ignores a key it thinks is still held
            g.dt = DT
            g.handle_events()
            g.update()
            g.draw()
            if f % SAMPLE_EVERY == 0:
                out.append(fingerprint(g))
    finally:
        pygame.time.get_ticks, pygame.key.get_pressed = real_ticks, real_pressed
        g.running = False
    return out


def hash_seed(name):
    return zlib.crc32(name.encode()) & 0xFFFF


def _solo(ship):
    def setup(g):
        g.ship_id = ship
        g.play_mode = "solo"
        g._begin_run()
    return setup


def _coop(g):
    g.ship_id = "phoenix"
    g.ship_id_p2 = "shield"
    g.play_mode = "coop"
    g._begin_run()


def _hotseat(g):
    g.ship_id = "phoenix"
    g.ship_id_p2 = "shield"
    g.play_mode = "hotseat"
    g._begin_run()


def _adventure(g):
    import story

    spec = None
    for i in range(len(story.MISSIONS)):
        g.story.map_index = i
        spec = g.story._launch_selected()
        if spec:
            break
    g._begin_adventure(spec)


SCENARIOS = {
    "solo_phoenix_stages": dict(
        frames=3300, setup=_solo("phoenix"), god=True,
        stage_jumps={500: 2, 1000: 3, 1500: 4, 2000: 5},
        events={400: pygame.K_RSHIFT, 1200: pygame.K_RSHIFT, 1600: pygame.K_RSHIFT, 2300: pygame.K_RSHIFT},
    ),
    "solo_phoenix_deaths": dict(frames=1500, setup=_solo("phoenix")),
    "solo_shield_stages": dict(
        frames=2400, setup=_solo("shield"), god=True,
        stage_jumps={500: 3, 1000: 6, 1500: 10},
        events={300: pygame.K_RSHIFT, 800: pygame.K_RSHIFT, 1700: pygame.K_RSHIFT},
    ),
    "boss_fight": dict(
        frames=2400, setup=_solo("phoenix"), god=True,
        stage_jumps={5: 5},
        events={200: pygame.K_RSHIFT, 900: pygame.K_RSHIFT, 1500: pygame.K_RSHIFT},
    ),
    "coop": dict(
        frames=1800, setup=_coop, god=True, stage_jumps={700: 2},
        events={300: pygame.K_LSHIFT, 500: pygame.K_RSHIFT},
    ),
    "hotseat": dict(frames=2000, setup=_hotseat, stage_jumps={900: 2},
                    events={40: pygame.K_RETURN}),
    "adventure": dict(frames=1500, setup=_adventure, god=True),
}


def run_all():
    return {name: run_scenario(name, **cfg) for name, cfg in SCENARIOS.items()}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    import conftest  # noqa: F401  (headless setup, temp user dir)

    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "golden_replay.json")
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(run_all(), fh, indent=0)
    print("written:", target)
