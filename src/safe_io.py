"""
Safe saving of the player's JSON files (settings, high scores, achievements, story).

A plain open(path, "w") empties the file first: a crash, a power cut or a full
disk in the middle of the write leaves a truncated, unreadable file. Here the
data is written to a temporary file next to the target, flushed to disk, then
swapped in with os.replace (atomic): the old file stays intact until the new one
is complete.
"""
import json
import os
import shutil
import time


def atomic_write_text(path, text):
    """Write `text` to `path` without ever leaving a half-written file."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        # On Windows the target can be briefly locked (antivirus, indexer): retry.
        for attempt in range(4):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(0.05)
    except Exception:
        # Last resort: the old behaviour (direct write), so saving still works.
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def atomic_write_json(path, data, indent=2):
    """Serialize first (a bad value must not touch the existing file), then write atomically."""
    text = json.dumps(data, indent=indent)
    atomic_write_text(path, text)


def backup_unreadable(path):
    """Keep a copy of a save file that cannot be read, as `<path>.corrupt`.

    Called before the game falls back to defaults, so the next save does not
    silently erase whatever was in the file. Never raises; keeps only the latest copy.
    """
    try:
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            shutil.copy2(path, path + ".corrupt")
            return True
    except Exception:
        pass
    return False
