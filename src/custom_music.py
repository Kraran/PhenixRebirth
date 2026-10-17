"""Your own music for the in-game soundtrack: the files dropped in the folder `musique_perso`, next to the game.

The folder is made (empty) when the game starts. Every sound file of a kind the mixer reads (mp3, wav, ogg, flac...)
shows up in Options > Audio > In-game music, after the tracks of the game. Nothing here is saved but the choice made:
the key `custom:<file name>` in settings.json. A file that is gone (or renamed) is no longer a choice, and the music
falls back to None.
"""
import os
import time

import settings
from errlog import log_exc

FOLDER_NAME = "musique_perso"
PREFIX = "custom:"
# What the mixer (SDL_mixer through pygame) reads on every machine: the usual formats and the tracker modules.
EXTENSIONS = (".mp3", ".wav", ".ogg", ".flac", ".opus", ".mod", ".xm", ".it", ".s3m")
RESCAN_SEC = 1.5                      # the folder is read again at most this often (a name is asked for every frame)

_cache = {"at": -1e9, "dir": None, "names": ()}


def folder():
    """The full path of the folder (next to settings.json, so next to the .exe once packaged)."""
    return os.path.join(settings.user_data_dir(), FOLDER_NAME)


def ensure_folder():
    """Make the folder when it does not exist yet. Never raises: no folder is just no custom music."""
    path = folder()
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        log_exc("custom_music.ensure_folder")
        return False
    return os.path.isdir(path)


def forget():
    """Read the folder again at the next question (a test, or the Options screen opening)."""
    _cache["at"] = -1e9


def files():
    """The names of the playable files of the folder, sorted without regard to case. Empty when there is no folder."""
    now = time.monotonic()
    path = folder()
    if _cache["dir"] == path and now - _cache["at"] < RESCAN_SEC:
        return _cache["names"]
    names = []
    try:
        for name in os.listdir(path):
            if name.lower().endswith(EXTENSIONS) and not name.startswith(".") and os.path.isfile(os.path.join(path, name)):
                names.append(name)
    except OSError:
        names = []                      # no folder (yet): nothing to offer
    names.sort(key=lambda n: (n.lower(), n))
    _cache.update(at=now, dir=path, names=tuple(names))
    return _cache["names"]


def key_for(name):
    return PREFIX + name


def is_custom(key):
    return isinstance(key, str) and key.startswith(PREFIX)


def keys():
    return tuple(key_for(n) for n in files())


def exists(key):
    """True when `key` names a file that is in the folder now."""
    return is_custom(key) and key[len(PREFIX):] in files()


def path_of(key):
    """The full path of the file of a key, or None (not a custom key, file gone). Only a name the folder lists is
    accepted, so a hand-edited settings.json cannot point outside the folder."""
    if not exists(key):
        return None
    return os.path.join(folder(), key[len(PREFIX):])


def label(key):
    """What the Options show: the title tag of the file when it has one (mp3), else its name without the extension."""
    path = path_of(key)
    if path is None:
        return key[len(PREFIX):] if is_custom(key) else str(key)
    try:
        from mp3_title import title_from_path
        title = title_from_path(path)
    except Exception:
        log_exc("custom_music.label")
        title = ""
    return title or os.path.splitext(os.path.basename(path))[0]
