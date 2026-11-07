"""The "Adventure style" of the classic game (Options > GAMEPLAY): a solo arcade game that starts with some of the
equipment of the Adventure.

- "gameplay_style": "classic" (the game as it always was) or "adventure";
- "gp_modules": the two escort modules of the Adventure (src/gyro.py), one hit each;
- "gp_missiles": the antimatter missiles of the Adventure (src/antimatter.py), 0 to MISSILES_MAX for the whole game.

Only in a solo game (not the hot-seat, not the coop, not the demo); the choice is read when the game starts. A score made
in Adventure style carries a mark in the table of high scores (highscores.insert_score adventure=True)."""

import antimatter
import gyro

STYLES = ("classic", "adventure")
MISSILES_MAX = 20
MODULES = {"count": 2, "armour": 1}      # the two modules of the Adventure, one hit each


def wanted(game):
    """True when the next solo game is in Adventure style (the options)."""
    return getattr(game, "gameplay_style", "classic") == "adventure"


def start(game):
    """A solo arcade game starts: its modules and its missiles, in Adventure style (nothing in the classic style)."""
    game.arcade_style = False
    game.gyro = None
    game.antimatter = None
    if not wanted(game) or getattr(game, "adventure", None) or getattr(game, "attract_mode", False):
        return
    if getattr(game, "play_mode", "solo") != "solo":
        return
    game.arcade_style = True
    if getattr(game, "gp_modules", True):
        gyro.start(game, {"modules": dict(MODULES)})
    n = max(0, min(MISSILES_MAX, int(getattr(game, "gp_missiles", 0) or 0)))
    if n:
        game.antimatter = antimatter.Armory(True, count=n)


def stop(game):
    """The game is over (or abandoned): nothing of it carries over."""
    game.arcade_style = False
    game.gyro = None
    game.antimatter = None


def active(game):
    """True while a solo arcade game in Adventure style is being played."""
    return bool(getattr(game, "arcade_style", False)) and not getattr(game, "adventure", None)
