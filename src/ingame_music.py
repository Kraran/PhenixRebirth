"""In-game soundtrack picker (Options > Audio > In-game music).

The choices, in the order of the arrows: None, the five themes of the jukebox, the four songs of Lyra Voss, then the
files the player dropped in the folder `musique_perso` (src/custom_music.py). Labels = the ID3 title of the track, as in
the jukebox; the songs of Lyra Voss carry the translated titles of the jukebox (their files have no tag).
"""

import custom_music
from mp3_title import title_for_key

THEMES = (
    "none",
    "menu",
    "gameover",
    "credits",
    "nostalgie_start",
    "nostalgie_elise",
)
LYRA = (
    "lyra_eternal_dawn",
    "lyra_what_we_lost",
    "lyra_no_mercy_left",
    "lyra_oldest_fear",
)
CYCLE = THEMES + LYRA           # the tracks of the game; the files of the player come after (see choices())


def choices():
    """Every choice now: the tracks of the game, then the files of the folder `musique_perso`."""
    return CYCLE + custom_music.keys()


def normalize(value):
    v = value or "none"
    if v in CYCLE or custom_music.exists(v):
        return v
    return "none"


def cycle(value, direction):
    cur = normalize(value)
    allc = choices()
    i = allc.index(cur)
    return allc[(i + int(direction)) % len(allc)]


def is_custom(value):
    return custom_music.is_custom(value)


def label(value, t, asset_path_fn=None):
    key = normalize(value)
    if key == "none":
        try:
            return t("no")
        except Exception:
            return "Off"
    if custom_music.is_custom(key):
        return custom_music.label(key)
    if key in LYRA:
        try:
            return t("juke_" + key)
        except Exception:
            pass
    if asset_path_fn is not None:
        return title_for_key(asset_path_fn, key)
    return key
