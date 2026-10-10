"""
errors.log: a quiet record of errors the game catches and ignores.

Many `try / except Exception` blocks keep the game running when something
optional fails (a sound, a bezel image, a monitor query...). Until now those
errors vanished without a trace. log_exc() writes them to errors.log, next to
the game (same folder as settings.json), so a problem can be diagnosed later.

Design rules:
- it must never raise or slow the game down: every step is wrapped, and a
  repeated error (same place, same exception type) is only counted, not
  formatted again, so an error that happens every frame costs almost nothing;
- the first occurrence of each error is written with its full traceback;
  a summary of the repeat counts is added when the game exits;
- the file is capped (256 KB, previous one kept as errors.log.old).
"""
import atexit
import os
import sys
import time
import traceback

import settings

MAX_BYTES = 256 * 1024
MAX_DISTINCT = 200  # distinct errors written per session

_seen = {}  # (where, exception type) -> repeat count
_started = False


def _path():
    return os.path.join(settings.user_data_dir(), "errors.log")


def _append(text):
    path = _path()
    global _started
    if not _started:
        _started = True
        try:
            if os.path.getsize(path) > MAX_BYTES:
                os.replace(path, path + ".old")
        except OSError:
            pass
        text = "=== %s ===\n%s" % (time.strftime("%Y-%m-%d %H:%M:%S"), text)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)


def log_exc(where):
    """Record the exception being handled (call it from inside an `except` block)."""
    try:
        etype, evalue, etb = sys.exc_info()
        if etype is None:
            return
        key = (where, etype.__name__)
        if key in _seen:
            _seen[key] += 1
            return
        if len(_seen) >= MAX_DISTINCT:
            return
        _seen[key] = 1
        tb = "".join(traceback.format_exception(etype, evalue, etb)).rstrip()
        _append("[%s] %s\n" % (where, tb))
    except Exception:
        pass


def log_note(text):
    """Record a line of text (no exception): the same line is only written once per session."""
    try:
        key = ("note", text)
        if key in _seen:
            _seen[key] += 1
            return
        if len(_seen) >= MAX_DISTINCT:
            return
        _seen[key] = 1
        _append("[note] %s\n" % text)
    except Exception:
        pass


def _summary():
    try:
        repeats = [(k, n) for k, n in _seen.items() if n > 1]
        if repeats:
            lines = ["repeated errors:"]
            for (where, name), n in sorted(repeats, key=lambda kv: -kv[1]):
                lines.append("  %s %s x%d" % (where, name, n))
            _append("\n".join(lines) + "\n")
    except Exception:
        pass


atexit.register(_summary)
