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


def pytest_runtest_logreport(report):
    """On GitHub Actions, show each failure as an annotation (visible on the pull request)."""
    if not (report.failed and os.environ.get("GITHUB_ACTIONS")):
        return
    crash = getattr(report.longrepr, "reprcrash", None)
    text = crash.message if crash else str(report.longrepr)[-600:]
    text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")[:1000]
    print(f"::error title=Test failed {report.nodeid}::{text}")
