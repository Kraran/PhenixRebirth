"""In-game soundtrack picker. Labels = ID3 Title tags, same as jukebox."""

from mp3_title import title_for_key

CYCLE = (
    "none",
    "menu",
    "gameover",
    "credits",
    "nostalgie_start",
    "nostalgie_elise",
)


def normalize(value):
    v = value or "none"
    return v if v in CYCLE else "none"


def cycle(value, direction):
    cur = normalize(value)
    i = CYCLE.index(cur)
    return CYCLE[(i + int(direction)) % len(CYCLE)]


def label(value, t, asset_path_fn=None):
    key = normalize(value)
    if key == "none":
        try:
            return t("no")
        except Exception:
            return "Off"
    if asset_path_fn is not None:
        return title_for_key(asset_path_fn, key)
    return key
