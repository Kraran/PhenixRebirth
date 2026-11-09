"""
Shared test setup: run the game without a screen, sound card or user files.

- SDL "dummy" drivers: no window, no audio device (works on CI and on any PC).
- user_data_dir() is redirected to a temp folder BEFORE any game module is
  imported, so tests never read or overwrite your real settings.json,
  highscores.json, achievements.json or story.json.
"""
import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

_USER_DIR = tempfile.mkdtemp(prefix="phenix_test_")

import settings  # noqa: E402  (must come first, see docstring)

settings.user_data_dir = lambda: _USER_DIR

import lander_view  # noqa: E402

lander_view.WARM_UP = False          # (the menu of the Lunar Lander would make its pictures in a thread: not in the tests)

import scramble_view  # noqa: E402

scramble_view.BACKGROUND = False     # (the rock of the Scramble ahead of the screen would be made in a thread: not in the tests)


import pygame  # noqa: E402

_load = pygame.image.load
_LOADED = {}


def _load_kept(file, *args, **kwargs):
    """The tests build a Game hundreds of times: each picture file is read from the disk once, then copied."""
    if args or kwargs or not isinstance(file, (str, os.PathLike)):
        return _load(file, *args, **kwargs)
    try:
        st = os.stat(file)
    except OSError:
        return _load(file)
    key = (os.path.abspath(file), st.st_mtime_ns, st.st_size)
    pic = _LOADED.get(key)
    if pic is None:
        pic = _LOADED[key] = _load(file)
    return pic.copy()


pygame.image.load = _load_kept


_FAILURES = []


def pytest_runtest_logreport(report):
    if report.failed:
        crash = getattr(report.longrepr, "reprcrash", None)
        _FAILURES.append((report.nodeid, crash.message if crash else str(report.longrepr)[-600:]))


def pytest_terminal_summary(terminalreporter):
    """On GitHub Actions, show each failure as an annotation (visible on the pull request)."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    for nodeid, text in _FAILURES:
        text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")[:1000]
        terminalreporter.write_line(f"::error title=Test failed {nodeid}::{text}")


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _spacewar_test_missions(request, monkeypatch):
    """The SpaceWar engine tests fly the old training missions (tests/sw_missions.py); the game itself no longer lists them."""
    if getattr(request.module, "NEEDS_SW_MISSIONS", False):
        import story_state
        from sw_missions import TEST_MISSIONS
        monkeypatch.setattr(story_state, "MISSIONS", story_state.MISSIONS + TEST_MISSIONS)
    yield


import pytest  # noqa: E402


@pytest.fixture
def training_missions():
    """The four TEST missions taken out of the Adventure, put back for a test that flies one of them (tests/training_missions.py),
    where they stood: just before the BONUS FINAL - Scramble."""
    import story_state as ss
    from training_missions import TRAINING
    at = next(i for i, m in enumerate(ss.MISSIONS) if m["id"] == "bonus_scramble")
    added = [dict(m) for m in TRAINING]
    ss.MISSIONS[at:at] = added
    try:
        yield added
    finally:
        for m in added:
            ss.MISSIONS.remove(m)
