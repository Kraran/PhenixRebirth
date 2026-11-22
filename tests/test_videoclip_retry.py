"""A decoder that gives no picture (on a Windows just installed, the antivirus holds the new ffmpeg.exe for a few
seconds) is started again (videoclip.RETRY_WAITS) before the still takes over; what went wrong goes to errors.log."""
import io
import time

import pytest

import errlog
import videoclip

W, H = 8, 4
FRAME = b"\x10\x20\x30\x00" * (W * H)


class FakeProc:
    def __init__(self, frames):
        self.stdout = io.BytesIO(FRAME * frames)

    def kill(self):
        pass

    def wait(self, timeout=None):
        return 0


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(videoclip, "RETRY_WAITS", (0.01, 0.01, 0.01))
    notes = []
    monkeypatch.setattr(videoclip, "log_note", notes.append)
    return notes


def _player(monkeypatch, runs, loop=False, path=None):
    """A player whose ffmpeg runs give, one after the other, `runs` (a number of frames, or an exception)."""
    calls = []

    def spawn(self):
        r = runs[min(len(calls), len(runs) - 1)]
        calls.append(r)
        if isinstance(r, Exception):
            if self._err_file is not None:
                self._err_file.write(b"Permission denied")
            raise r
        return FakeProc(r)
    monkeypatch.setattr(videoclip.ClipPlayer, "_spawn", spawn)
    monkeypatch.setattr(videoclip, "mp4_info", lambda p: None)
    p = videoclip.ClipPlayer(path or "clip.mp4", (W, H), exe="ffmpeg", loop=loop)
    return p, calls


def _drain(p, until, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end and not until():
        p.pump(time.monotonic() + 100)
        time.sleep(0.005)
    return until()


def test_a_decoder_that_could_not_start_is_started_again(monkeypatch, fast):
    p, calls = _player(monkeypatch, [PermissionError(13, "Access is denied"), 0, 5])
    assert _drain(p, lambda: p.ended)
    assert len(calls) == 3 and not p.failed and p.surface is not None
    assert any("trying again" in n and "PermissionError" in n and "ffmpeg: Permission denied" in n for n in fast)
    p.close()


def test_after_the_last_try_the_still_takes_over(monkeypatch, fast):
    p, calls = _player(monkeypatch, [0])
    assert _drain(p, lambda: p.failed)
    assert len(calls) == 1 + len(videoclip.RETRY_WAITS) and p.surface is None and not p.playing
    assert any("gave up" in n for n in fast)
    p.close()


def test_a_clip_played_once_to_its_end_is_not_started_again(monkeypatch, fast):
    p, calls = _player(monkeypatch, [4])
    assert _drain(p, lambda: p.ended)
    assert len(calls) == 1 and not p.failed and fast == []
    p.close()


def test_a_looping_clip_whose_decoder_stops_is_started_again(monkeypatch, fast):
    p, calls = _player(monkeypatch, [3, 3, 3, 3], loop=True)
    assert _drain(p, lambda: p.failed)
    assert len(calls) == 4 and p.surface is not None
    p.close()


def test_a_closed_player_is_not_started_again(monkeypatch, fast):
    p, calls = _player(monkeypatch, [0])
    p.close()
    time.sleep(0.1)
    assert len(calls) <= 1 and not p.failed


def test_what_ffmpeg_said_is_kept():
    import tempfile
    f = tempfile.TemporaryFile()
    f.write(b"  oiseaux_kaki.mp4:\n   Permission denied  ")
    assert videoclip._tail(f) == "oiseaux_kaki.mp4: Permission denied"
    assert videoclip._tail(None) == ""
