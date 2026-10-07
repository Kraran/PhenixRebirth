"""
Safe saving of the player's JSON files (settings, high scores, achievements, story).

A plain open(path, "w") empties the file first: a crash, a power cut or a full
disk in the middle of the write leaves a truncated, unreadable file. Here the
data is written to a temporary file next to the target, flushed to disk, then
swapped in with os.replace (atomic): the old file stays intact until the new one
is complete.
"""
import atexit
import json
import os
import shutil
import threading
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


# --- Écriture différée -------------------------------------------------------
# Certains fichiers sont sauvegardés PENDANT la partie (hauts faits : à chaque
# oiseau abattu). Un fsync peut alors bloquer le jeu 10 à 50 ms sous Windows, ce
# qui se voit comme un à-coup. Ces fichiers sont donc écrits par un fil
# d'arrière-plan, avec exactement la même méthode sûre (fichier temporaire,
# fsync, os.replace). Garanties :
#   - read_text_latest() renvoie toujours la DERNIÈRE version, même pas encore
#     sur le disque : une relecture juste après une sauvegarde ne perd rien ;
#   - plusieurs sauvegardes rapprochées d'un même fichier sont fusionnées ;
#   - flush() (appelé aussi à la fermeture du jeu) attend que tout soit écrit.
COALESCE_SEC = 0.3

_cv = threading.Condition()
_pending = {}      # chemin -> texte à écrire
_inflight = {}     # chemin -> texte en cours d'écriture
_flush_requested = False
_thread = None


def _worker():
    while True:
        with _cv:
            while not _pending:
                _cv.wait()
            # laisse les sauvegardes rapprochées se regrouper (sauf flush demandé)
            _cv.wait_for(lambda: _flush_requested, timeout=COALESCE_SEC)
            batch = dict(_pending)
            _pending.clear()
            _inflight.update(batch)
        for path, text in batch.items():
            try:
                atomic_write_text(path, text)
            except Exception:
                try:
                    from errlog import log_exc
                    log_exc("safe_io.write_behind")
                except Exception:
                    pass
            with _cv:
                if _inflight.get(path) is text:
                    del _inflight[path]
                _cv.notify_all()


def write_behind(path, text):
    """Comme atomic_write_text, mais sans faire attendre l'appelant."""
    global _thread
    with _cv:
        _pending[path] = text
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_worker, name="phenix-save", daemon=True)
            _thread.start()
        _cv.notify_all()


def write_behind_json(path, data, indent=2):
    """Sérialise tout de suite (une valeur invalide n'abîme rien), écrit en arrière-plan."""
    write_behind(path, json.dumps(data, indent=indent))


def read_text_latest(path):
    """Contenu du fichier, ou de sa dernière version encore en attente d'écriture."""
    with _cv:
        if path in _pending:
            return _pending[path]
        if path in _inflight:
            return _inflight[path]
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def flush(timeout=10.0):
    """Attend que toutes les écritures différées soient sur le disque."""
    global _flush_requested
    with _cv:
        if not _pending and not _inflight:
            return True
        _flush_requested = True
        _cv.notify_all()
        ok = _cv.wait_for(lambda: not _pending and not _inflight, timeout=timeout)
        _flush_requested = False
        leftovers = {} if ok else dict(_pending)
    if not ok and (_thread is None or not _thread.is_alive()):
        # le fil est mort : on écrit nous-mêmes ce qui reste
        for path, text in leftovers.items():
            try:
                atomic_write_text(path, text)
                with _cv:
                    if _pending.get(path) is text:
                        del _pending[path]
            except Exception:
                pass
        ok = True
    return ok


atexit.register(flush)
