"""The "Adventure style" of the classic game (Options > GAMEPLAY): a solo arcade game that starts with some of the
equipment of the Adventure.

- "gameplay_style": "classic" (the game as it always was) or "adventure";
- "gp_modules": the two escort modules of the Adventure (src/gyro.py), one hit each;
- "gp_missiles": the antimatter missiles of the Adventure (src/antimatter.py), 0 to MISSILES_MAX for the whole game;
- "gp_reactor": the two-dimensional impulse reactor of the Adventure (its BONUS missions): the ship also flies up and
  down, in the lower third of the screen;
- "gp_guardians": the Guardians of BONUS FINAL - Gardiens (src/guardian.py GuardianSquad) come with every level, the
  boss levels too, in the same numbers (story_state.endless_guardians: one more each level up to five, then from level 6
  one Alpha Guardian more every five levels); Game._setup_guardian_squad makes them, as for the mission.

Only in a solo game (not the hot-seat, not the coop, not the demo); the choice is read when the game starts. The style
is not saved: the game always starts in the classic style (the settings of the Adventure style are saved). A game in
Adventure style never enters the high scores (Game._begin_highscore_flow: like a cheat, the table only)."""

import antimatter
import gyro
from errlog import log_exc
from settings import PLAYER_VERTICAL_BOTTOM, PLAYER_VERTICAL_TOP

STYLES = ("classic", "adventure")
MISSILES_MAX = 20
MODULES = {"count": 2, "armour": 1}      # the two modules of the Adventure, one hit each


def wanted(game):
    """True when the next solo game is in Adventure style (the options)."""
    return getattr(game, "gameplay_style", "classic") == "adventure"


def start(game):
    """A solo arcade game starts: its modules and its missiles, in Adventure style (nothing in the classic style)."""
    game.arcade_style = False
    game.arcade_guardians = False
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
    if getattr(game, "gp_reactor", True) and getattr(game, "player", None) is not None:
        game.player.vertical_range = (PLAYER_VERTICAL_TOP, PLAYER_VERTICAL_BOTTOM)
    if getattr(game, "gp_guardians", False):
        game.arcade_guardians = True
        _prepare_guardians(game)


def _prepare_guardians(game):
    """The Guardians of the first level (it is already set up), their flames and the ash of the gargoyles their lasers
    burn, made now behind the loading bar (about a second and a half, as behind the bar of BONUS FINAL - Gardiens), so
    the first ones do not hold the game."""
    import guardian
    import loading
    try:
        with loading.Loading(game, "arcade", delay=getattr(game, "LOADING_DELAY", 0.25)) as ld:
            if hasattr(game, "_setup_guardian_squad"):
                ld.step(0.6, game._setup_guardian_squad, 0.9)
            ld.step(0.4, guardian.warm_gargoyle_ash, 0.5)
    except Exception:
        log_exc("arcade_style.start")


def stop(game):
    """The game is over (or abandoned): nothing of it carries over."""
    game.arcade_style = False
    game.arcade_guardians = False
    game.gyro = None
    game.antimatter = None


def active(game):
    """True while a solo arcade game in Adventure style is being played."""
    return bool(getattr(game, "arcade_style", False)) and not getattr(game, "adventure", None)


def guardians(game):
    """True while a solo arcade game in Adventure style is played with its Guardians (Options > GAMEPLAY > Guardians)."""
    return (active(game) and bool(getattr(game, "arcade_guardians", False))
            and not getattr(game, "attract_mode", False) and getattr(game, "play_mode", "solo") == "solo")
