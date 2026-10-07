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


SIDE_EFFECTS = {"quit": 0, "addon": 0}


def _frozen_datetime():
    """The game changes its decor on 1 April, Halloween and Christmas: freeze the date."""
    import datetime as _dt

    class FrozenDate(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 6, 15, 12, 0, 0)

    return FrozenDate


FUZZ_KEYS = [
    (pygame.K_UP, ""), (pygame.K_DOWN, ""), (pygame.K_LEFT, ""), (pygame.K_RIGHT, ""),
    (pygame.K_RETURN, ""), (pygame.K_ESCAPE, ""), (pygame.K_SPACE, " "), (pygame.K_BACKSPACE, ""),
    (pygame.K_a, "a"), (pygame.K_d, "d"), (pygame.K_q, "q"), (pygame.K_w, "w"), (pygame.K_s, "s"),
    (pygame.K_z, "z"), (pygame.K_x, "x"), (pygame.K_b, "b"), (pygame.K_n, "n"), (pygame.K_p, "p"),
    (pygame.K_LSHIFT, ""), (pygame.K_RSHIFT, ""), (pygame.K_KP_ENTER, ""), (pygame.K_CAPSLOCK, ""),
    (pygame.K_LCTRL, ""),
]


def _fuzz_events(rng, joy):
    """One random input event (keyboard, plus gamepad buttons / hat / sticks when joy)."""
    pick = rng.random()
    if not joy or pick < 0.55:
        key, uni = rng.choice(FUZZ_KEYS)
        return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=uni, mod=0)
    if pick < 0.72:
        return pygame.event.Event(pygame.JOYBUTTONDOWN, button=rng.choice([0, 1, 2, 3, 6, 7, 9]),
                                  instance_id=0, joy=0)
    if pick < 0.85:
        return pygame.event.Event(pygame.JOYHATMOTION, value=rng.choice(
            [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]), instance_id=0, joy=0, hat=0)
    return pygame.event.Event(pygame.JOYAXISMOTION, axis=rng.choice([0, 1]),
                              value=rng.choice([0.0, 0.3, 0.9, -0.9, 0.6, -0.6, 1.0, -1.0]),
                              instance_id=0, joy=0)


ALL_JUMPS = ["pause", "pause_options", "pause_reset", "quit_confirm", "options",
             "reset_confirm", "credits", "ship_select", "hotseat_pick", "go_card",
             "go_enter", "go_table", "hotseat_wait", "to_menu", "highscores",
             "achievements", "jukebox", "help", "attract"]


def _jump_state(g, rng, kinds=None):
    """Throw the game into a random menu / pause / game-over state (fuzz scenarios)."""
    k = rng.choice(kinds or ALL_JUMPS)
    if k in ("pause", "pause_options", "pause_reset", "hotseat_wait") and (not g.started or g.game_over):
        return k + "-skipped"
    if k == "pause":
        g.paused, g.pause_options, g.pause_index = True, False, rng.randrange(3)
    elif k == "pause_options":
        g.paused, g.pause_options, g.menu_screen, g.menu_index = True, True, "options", rng.randrange(6)
    elif k == "pause_reset":
        g.paused, g.pause_options, g.menu_screen, g.menu_index = True, True, "reset_confirm", rng.randrange(2)
    elif k == "hotseat_wait":
        g.hotseat_wait = True
    elif k == "quit_confirm" and not g.started:
        g.quit_confirm, g.quit_index = True, rng.randrange(2)
    elif k in ("options", "reset_confirm", "credits", "ship_select", "highscores",
               "achievements", "jukebox", "help") and not g.started:
        g.quit_confirm = False
        g.menu_screen = k
        g.menu_index = rng.randrange(6)
        if k == "ship_select":
            g.play_mode = rng.choice(["solo", "coop", "hotseat"])
    elif k == "hotseat_pick" and g.started and g.hotseat and not g.game_over:
        g.hotseat_pick_p2 = True
        g.menu_screen = "ship_select"
    elif k.startswith("go_"):
        g.game_over = True
        g.hs_phase = {"go_card": "card", "go_enter": "enter", "go_table": "table"}[k]
        g.hs_char_index = rng.randrange(3)
    elif k == "to_menu" and g.started:
        g._quit_to_menu()
    elif k == "attract" and not g.started and not g.game_over:
        g.menu_screen = "main"
        g.quit_confirm = False
        g._start_attract()
    return k


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
        # menus, idle / attract, help, credits, pause, hot-seat, high-score entry
        int(getattr(g, "menu_index", 0) or 0), _r(getattr(g, "menu_idle", 0)),
        bool(getattr(g, "attract_mode", False)), str(getattr(g, "hs_phase", None)),
        int(getattr(g, "help_page", 0) or 0), _r(getattr(g, "help_scroll", 0)),
        bool(getattr(g, "hotseat_wait", False)), _r(getattr(g, "hotseat_hold", 0)),
        _r(getattr(g, "credits_scroll", 0)), _r(getattr(g, "credits_x", 0)),
        int(getattr(g, "logo_index", 0) or 0), _r(getattr(g, "input_grace", 0)),
        _r(getattr(g, "ship_anim_t", 0)), _r(getattr(g, "shield_slide", 0)),
        _r(getattr(g, "ach_scroll", 0)), int(getattr(g, "juke_index", 0) or 0),
        # pause / quit menus, high-score entry, joystick latches, options, side effects
        int(getattr(g, "pause_index", 0) or 0), bool(getattr(g, "pause_options", False)),
        bool(getattr(g, "quit_confirm", False)), int(getattr(g, "quit_index", 0) or 0),
        int(getattr(g, "hs_char_index", 0) or 0), "".join(str(c) for c in getattr(g, "hs_name", [])),
        str(getattr(g, "play_mode", "")), str(getattr(g, "ship_id", "")),
        bool(getattr(g, "hotseat_pick_p2", False)),
        sorted(getattr(g, "_special_keys", None) or []), str(getattr(g, "_hat_latch", None)),
        int(getattr(g, "_joy_axis_latch_x", 0) or 0), int(getattr(g, "_joy_axis_latch_y", 0) or 0),
        _r(getattr(g, "_joy_menu_cooldown", 0)), SIDE_EFFECTS["quit"], SIDE_EFFECTS["addon"],
        [str(getattr(g, k, None)) for k in ("difficulty", "audio_mix", "autofire", "rumble_level",
                                             "scanlines", "input_mode", "lang", "cheat_buffer")],
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


def _menu_pressed(g, frame):
    """Scripted keys for menu scenarios: hold up / down / left / right in turn."""
    cycle = (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, None)
    key = cycle[(frame // 45) % len(cycle)]
    return {key} if key is not None else set()


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


def run_scenario(name, frames, setup, events=None, stage_jumps=None, god=False,
                 screens=None, menu_keys=False, fuzz=None):
    """Return the list of fingerprints for one scripted game.

    fuzz = dict(seed=, every=, joy=): every `every` frames a pseudo-random input
    event is posted (keyboard, and gamepad buttons / hat / sticks when joy=True).
    """
    import shutil

    import game as game_module
    import i18n
    import settings
    from game import Game

    # Every scenario starts from a clean profile (settings, high scores, achievements...):
    # the random-input scenarios change options, which must not leak into the next one.
    user_dir = settings.user_data_dir()
    for entry in os.listdir(user_dir):
        path = os.path.join(user_dir, entry)
        shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path) else os.remove(path)
    i18n.set_lang("fr")
    # Class-level image caches in starfield.py: the first use of an image draws a random
    # number, so a warm cache (left by an earlier scenario) would shift the generator.
    import starfield

    for cls in vars(starfield).values():
        if isinstance(cls, type):
            for attr in ("_cache", "_stamps"):
                if isinstance(vars(cls).get(attr), dict):
                    vars(cls)[attr].clear()

    real_dt = game_module.datetime
    game_module.datetime = _frozen_datetime()
    real_methods = (Game._quit_app, Game._launch_addon)
    SIDE_EFFECTS["quit"] = SIDE_EFFECTS["addon"] = 0
    Game._quit_app = lambda self: SIDE_EFFECTS.__setitem__("quit", SIDE_EFFECTS["quit"] + 1)
    Game._launch_addon = lambda self, *a, **k: SIDE_EFFECTS.__setitem__("addon", SIDE_EFFECTS["addon"] + 1)
    fuzz_rng = random.Random(fuzz["seed"]) if fuzz else None
    fuzz_release = []
    errors = []
    g = _new_game(hash_seed(name))
    clock = {"frame": 0}
    real_ticks, real_pressed = pygame.time.get_ticks, pygame.key.get_pressed
    # Audio runs in real time (even on the dummy driver): whether a voice-over or a
    # track is "still playing" would depend on the machine speed, not on the frame.
    from sounds import SoundManager
    real_audio = (SoundManager.vo_is_busy, SoundManager.music_busy, SoundManager.music_pos_sec)
    SoundManager.vo_is_busy = lambda self: False
    SoundManager.music_busy = lambda self: False
    SoundManager.music_pos_sec = lambda self: 0.0
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
            current["keys"] = _Keys((_menu_pressed if menu_keys else _pressed)(g, f))
            if stage_jumps and f in stage_jumps:
                s = stage_jumps[f]
                g.stage = s
                g._setup_stage(s)
                g.stage_transition = None
            if screens and f in screens:
                for attr, value in screens[f].items():
                    setattr(g, attr, value)
            if events and f in events:
                for ship in g._ships():
                    ship.phenix_gauge = 10.0   # make the special move available
                _press(events[f])
            if events and (f - 3) in events:
                _release(events[f - 3])   # the game ignores a key it thinks is still held
            if fuzz_rng is not None:
                for key, due in list(fuzz_release):
                    if f >= due:
                        _release(key)
                        fuzz_release.remove((key, due))
                if fuzz.get("jump_every") and f > 0 and f % fuzz["jump_every"] == 0:
                    _jump_state(g, fuzz_rng, fuzz.get("kinds"))
                if f % fuzz["every"] == 0:
                    ev = _fuzz_events(fuzz_rng, fuzz.get("joy", False))
                    pygame.event.post(ev)
                    if ev.type == pygame.KEYDOWN:
                        fuzz_release.append((ev.key, f + 2))
            g.dt = DT
            if fuzz_rng is not None:
                try:   # states forced at random may be inconsistent: record, do not stop
                    g.handle_events()
                    g.update()
                    g.draw()
                except Exception as exc:
                    errors.append((f, type(exc).__name__))
            else:
                g.handle_events()
                g.update()
                g.draw()
            if f % SAMPLE_EVERY == 0:
                out.append(fingerprint(g))
        if fuzz_rng is not None:
            out.append("errors:%s" % (errors,))
    finally:
        pygame.time.get_ticks, pygame.key.get_pressed = real_ticks, real_pressed
        SoundManager.vo_is_busy, SoundManager.music_busy, SoundManager.music_pos_sec = real_audio
        game_module.datetime = real_dt
        Game._quit_app, Game._launch_addon = real_methods
        g.running = False
    return out


def hash_seed(name):
    return zlib.crc32(name.encode()) & 0xFFFF


def _nothing(g):
    pass


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
    # main menu left alone: help pages, then attract mode (demo game)
    "menu_idle_attract": dict(frames=4800, setup=_nothing),
    # every menu screen with held direction keys (credits scroll, achievements...)
    "menu_screens": dict(
        frames=2400, setup=_nothing, menu_keys=True,
        screens={
            0: {"menu_screen": "credits"}, 400: {"menu_screen": "achievements"},
            800: {"menu_screen": "jukebox"}, 1000: {"menu_screen": "highscores"},
            1100: {"menu_screen": "options", "menu_index": 0},
            1300: {"menu_screen": "ship_select", "play_mode": "solo"},
            1600: {"menu_screen": "story_hub"}, 1900: {"menu_screen": "reset_confirm"},
            2100: {"menu_screen": "main"},
        },
    ),
    # pause / resume, then play until game over and walk through the end cards
    "pause_game_over": dict(
        frames=2600, setup=_solo("phoenix"),
        events={200: pygame.K_ESCAPE, 330: pygame.K_ESCAPE, 1700: pygame.K_RETURN,
                1760: pygame.K_RETURN, 1820: pygame.K_RETURN, 1880: pygame.K_RETURN,
                1940: pygame.K_RETURN, 2000: pygame.K_RETURN, 2060: pygame.K_RETURN},
    ),
    # random keyboard + gamepad events through menus, options, pause, game over
    "fuzz_menu": dict(frames=3600, setup=_nothing, fuzz=dict(seed=1, every=6, joy=True, jump_every=90)),
    "fuzz_solo": dict(frames=3600, setup=_solo("phoenix"), fuzz=dict(seed=2, every=9, joy=True, jump_every=110)),
    "fuzz_shield": dict(frames=3600, setup=_solo("shield"), fuzz=dict(seed=5, every=7, joy=True, jump_every=130)),
    "fuzz_coop": dict(frames=3000, setup=_coop, fuzz=dict(seed=3, every=8, joy=True, jump_every=100)),
    "fuzz_hotseat": dict(frames=3000, setup=_hotseat, fuzz=dict(seed=4, every=8, joy=True, jump_every=120)),
    "fuzz_gameover": dict(frames=3600, setup=_solo("phoenix"), fuzz=dict(seed=6, every=4, joy=True, jump_every=70)),
    "fuzz_hotseat_pick": dict(frames=2400, setup=_hotseat, fuzz=dict(
        seed=8, every=5, joy=True, jump_every=60, kinds=["hotseat_pick", "to_menu"])),
    "fuzz_pause_gameover": dict(frames=3000, setup=_solo("phoenix"), fuzz=dict(
        seed=9, every=3, joy=True, jump_every=45,
        kinds=["pause", "pause_options", "pause_reset", "go_card", "go_enter", "go_table"])),
    "fuzz_attract_menu": dict(frames=2400, setup=_nothing, fuzz=dict(
        seed=10, every=4, joy=True, jump_every=50, kinds=["attract", "quit_confirm", "help", "credits",
                                                          "achievements", "jukebox", "highscores", "options"])),
    "fuzz_keys_only": dict(frames=3000, setup=_nothing, fuzz=dict(seed=7, every=5, joy=False, jump_every=60)),
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
