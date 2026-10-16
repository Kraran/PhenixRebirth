"""
The structure of the classic game's menus, in one place (the drawing, the input and the sounds all read it):

- MAIN: the five entries of the main menu.
- ARCADE: the rows of the "arcade game" screen opened by PLAY (mode, difficulty, then the ship select).
- EXTRAS: the screens gathered behind EXTRAS (scores, achievements, jukebox, credits, help, add-on).
- OPTION_TABS: the four tabs of the options and the rows of each one.

Use the names, never the numbers: `main_index("options")`, `extras_index("credits")`.
"""

MAIN = ("play", "story", "extras", "options", "quit")

ARCADE = ("mode", "difficulty", "ship")

EXTRAS = ("highscores", "achievements", "jukebox", "credits", "help", "addon")

OPTION_TABS = (
    ("game", ("control", "coop_p1", "coop_p2", "keybinds", "autofire", "rumble", "language")),
    ("audio", ("sfx", "music", "audio_mix", "ingame_music")),
    ("display", ("display", "bezel", "scanlines", "fps")),
    ("advanced", ("gpu", "vsync", "hz", "reset_hs")),
)

# title of each entry / tab (i18n keys)
MAIN_TITLES = {"play": "play", "story": "story", "extras": "extras_title", "options": "options", "quit": "quit"}
EXTRAS_TITLES = {"highscores": "high_scores", "achievements": "achievements", "jukebox": "jukebox",
                 "credits": "credits", "help": "extras_help", "addon": "addon"}
TAB_TITLES = {"game": "opt_tab_game", "audio": "opt_tab_audio", "display": "opt_tab_display",
              "advanced": "opt_tab_advanced"}


def main_index(name):
    return MAIN.index(name)


def extras_index(name):
    return EXTRAS.index(name)


def tab_rows(tab):
    """The option rows of tab number `tab` (wraps around)."""
    return list(OPTION_TABS[int(tab) % len(OPTION_TABS)][1])


def tab_of(key):
    """The tab number that holds the option `key` (0 if none)."""
    for i, (_name, rows) in enumerate(OPTION_TABS):
        if key in rows:
            return i
    return 0
