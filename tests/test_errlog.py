"""errors.log: ignored errors are recorded, repeats are counted, and logging never breaks the game."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import errlog  # noqa: E402
import settings  # noqa: E402


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "user_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(errlog, "_seen", {})
    monkeypatch.setattr(errlog, "_started", False)
    return tmp_path


def _boom(msg="bad"):
    try:
        raise ValueError(msg)
    except Exception:
        errlog.log_exc("mod.func")


def test_first_error_is_written_with_traceback(log_dir):
    _boom("first")
    text = (log_dir / "errors.log").read_text(encoding="utf-8")
    assert "[mod.func]" in text and "ValueError: first" in text and "Traceback" in text


def test_repeats_are_counted_not_rewritten(log_dir):
    for _ in range(5):
        _boom()
    text = (log_dir / "errors.log").read_text(encoding="utf-8")
    assert text.count("ValueError: bad") == 1
    assert errlog._seen[("mod.func", "ValueError")] == 5
    errlog._summary()
    assert "mod.func ValueError x5" in (log_dir / "errors.log").read_text(encoding="utf-8")


def test_different_places_are_logged_separately(log_dir):
    try:
        raise KeyError("k")
    except Exception:
        errlog.log_exc("a.b")
        errlog.log_exc("c.d")
    text = (log_dir / "errors.log").read_text(encoding="utf-8")
    assert "[a.b]" in text and "[c.d]" in text


def test_no_exception_no_entry(log_dir):
    errlog.log_exc("x.y")
    assert not (log_dir / "errors.log").exists()


def test_never_raises_when_folder_is_unwritable(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "user_data_dir", lambda: str(tmp_path / "missing" / "dir"))
    monkeypatch.setattr(errlog, "_seen", {})
    monkeypatch.setattr(errlog, "_started", False)
    _boom()  # must not raise


def test_big_log_is_rotated(log_dir):
    p = log_dir / "errors.log"
    p.write_bytes(b"x" * (errlog.MAX_BYTES + 10))
    _boom()
    assert (log_dir / "errors.log.old").exists()
    assert "ValueError" in p.read_text(encoding="utf-8")
    assert p.stat().st_size < errlog.MAX_BYTES
