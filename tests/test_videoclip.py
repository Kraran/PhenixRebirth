"""videoclip.py: the small looping videos played behind the screens (ffmpeg in a separate process, no sound)."""
import os
import re
import subprocess
import sys
import threading
import time

import pygame
import pytest

import videoclip as vc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG = vc.find_ffmpeg()
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="no ffmpeg on this machine")


@pytest.fixture(autouse=True)
def _forget_the_lookup():
    """Tests that change where ffmpeg is looked for must not leave their answer behind."""
    yield
    vc._exe_cache[:] = []


def _frame(rgb, size=(4, 2)):
    """Raw bytes of one solid frame as ffmpeg's bgr0 gives them."""
    r, g, b = rgb
    return bytes([b, g, r, 0]) * (size[0] * size[1])


class FakeOut:
    """What ffmpeg writes on stdout: the same frames for ever, or until `frames` runs out."""

    def __init__(self, frames, endless=True):
        self.frames, self.endless, self.i, self.closed = list(frames), endless, 0, False
        self.reads = 0

    def read(self, n):
        if self.closed:
            return b""
        if self.i >= len(self.frames):
            if not self.endless:
                return b""
            self.i = 0
        self.reads += 1
        time.sleep(0.001)
        data = self.frames[self.i]
        self.i += 1
        return data


class FakeProc:
    def __init__(self, out):
        self.stdout, self.killed = out, False

    def kill(self):
        self.killed = True
        self.stdout.closed = True

    def wait(self, timeout=None):
        return 0


def _player(monkeypatch, frames=None, endless=True, size=(4, 2), shade=None):
    out = FakeOut(frames if frames is not None else [_frame((10, 20, 30), size)], endless)
    proc = FakeProc(out)
    monkeypatch.setattr(vc.ClipPlayer, "_spawn", lambda self: proc)
    p = vc.ClipPlayer("x.mp4", size, shade, exe="ffmpeg-for-tests")
    return p, out, proc


def _wait(cond, seconds=3.0):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.005)
    return False


# ------------------------------------------------------------------ finding ffmpeg
def test_ffmpeg_is_looked_up_in_the_game_folders_then_the_package_then_the_path(tmp_path, monkeypatch):
    folder = tmp_path / "bin"
    folder.mkdir()
    monkeypatch.setattr(vc, "_roots", lambda: [str(folder)])
    fake_mod = type(sys)("imageio_ffmpeg")
    pkg = tmp_path / "pkg-ffmpeg"
    pkg.write_text("x")
    fake_mod.get_ffmpeg_exe = lambda: str(pkg)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", fake_mod)
    monkeypatch.setattr(vc.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    assert vc.find_ffmpeg(refresh=True) == str(pkg)                    # no bin folder file: the package
    (folder / "ffmpeg").write_text("x")
    assert vc.find_ffmpeg(refresh=True) == str(folder / "ffmpeg")      # a file the player placed wins
    (folder / "ffmpeg").unlink()
    fake_mod.get_ffmpeg_exe = lambda: str(tmp_path / "missing")
    assert vc.find_ffmpeg(refresh=True) == "/usr/bin/ffmpeg"           # the package has nothing: the PATH
    monkeypatch.setattr(vc.shutil, "which", lambda name: None)
    assert vc.find_ffmpeg(refresh=True) is None
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)           # package not installed at all
    assert vc.find_ffmpeg(refresh=True) is None


def test_the_lookup_is_done_once(monkeypatch):
    calls = []
    monkeypatch.setattr(vc, "_roots", lambda: calls.append(1) or [])
    vc.find_ffmpeg(refresh=True)
    vc.find_ffmpeg()
    vc.find_ffmpeg()
    assert len(calls) == 1


def test_the_game_uses_the_same_lookup(monkeypatch):
    import game
    monkeypatch.setattr(vc, "find_ffmpeg", lambda refresh=False: "/somewhere/ffmpeg")
    assert game._ffmpeg_exe() == "/somewhere/ffmpeg"
    monkeypatch.setattr(vc, "find_ffmpeg", lambda refresh=False: None)
    assert game._ffmpeg_exe() in ("ffmpeg", "ffmpeg.exe")


def test_the_package_is_a_requirement_and_goes_into_the_exe():
    assert re.search(r"^imageio-ffmpeg", open(os.path.join(ROOT, "requirements.txt")).read(), re.M)
    assert "collect-all imageio_ffmpeg" in open(os.path.join(ROOT, "build_exe.bat")).read()
    spec = open(os.path.join(ROOT, "PhenixRebirth.spec")).read()
    assert "collect_all('imageio_ffmpeg')" in spec and "videoclip" in spec


# ------------------------------------------------------------------ the command
def test_the_command_decodes_forever_without_sound_into_one_raw_format():
    cmd = vc.command("ffmpeg", "a.mp4", (1280, 720))
    assert cmd[0] == "ffmpeg" and cmd[cmd.index("-i") + 1] == "a.mp4"
    assert cmd[cmd.index("-stream_loop") + 1] == "-1" and cmd.index("-stream_loop") < cmd.index("-i")
    assert "-an" in cmd and "-sn" in cmd                                # never a sound
    assert "-re" not in cmd                                             # the game paces the frames itself
    assert cmd[cmd.index("-pix_fmt") + 1] == "bgr0" and cmd[cmd.index("-f") + 1] == "rawvideo" and cmd[-1] == "-"
    vf = cmd[cmd.index("-vf") + 1]
    assert "scale=1280:720:force_original_aspect_ratio=increase" in vf and vf.endswith("crop=1280:720")
    assert "drawbox" not in vf                                          # the shade is a cheap multiply in the game


def test_a_frame_has_the_layout_of_a_pygame_surface():
    s = pygame.Surface((4, 2))
    assert s.get_bitsize() == 32 and s.get_pitch() == 16 and s.get_masks()[:3] == (0xFF0000, 0xFF00, 0xFF)


# ------------------------------------------------------------------ the shade
def test_the_shade_multiplies_like_black_layers_do():
    boxes = [(0, 1280, 70), (220, 840, 120)]
    shade = vc.make_shade((1280, 720), boxes)
    assert shade.get_size() == (1280, 720)
    out, inside = shade.get_at((10, 5))[:3], shade.get_at((640, 700))[:3]
    assert out == (185, 185, 185) and inside == (98, 98, 98)
    assert shade.get_at((219, 0))[:3] == out and shade.get_at((220, 0))[:3] == inside
    assert shade.get_at((1059, 0))[:3] == inside and shade.get_at((1060, 0))[:3] == out
    # the same result as the translucent layers the still pictures get
    for colour in ((250, 120, 40), (255, 255, 255), (10, 200, 90)):
        still = pygame.Surface((1280, 720))
        still.fill(colour)
        for x, w, a in boxes:
            layer = pygame.Surface((w, 720), pygame.SRCALPHA)
            layer.fill((0, 0, 0, a))
            still.blit(layer, (x, 0))
        mult = pygame.Surface((1280, 720))
        mult.fill(colour)
        mult.blit(shade, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        for x in (10, 640):
            a, b = still.get_at((x, 5)), mult.get_at((x, 5))
            assert max(abs(a[i] - b[i]) for i in range(3)) <= 3


def test_a_shade_without_boxes_does_not_darken():
    shade = vc.make_shade((8, 4), [])
    assert shade.get_at((3, 2))[:3] == (255, 255, 255)
    off = vc.make_shade((8, 4), [(-5, 7, 255), (6, 10, 128)])          # boxes sticking out of the picture
    assert off.get_at((0, 0))[:3] == (0, 0, 0) and off.get_at((1, 0))[:3] == (0, 0, 0)
    assert off.get_at((3, 0))[:3] == (255, 255, 255) and off.get_at((7, 0))[:3][0] in (127, 128)


# ------------------------------------------------------------------ playing frames
def test_the_frame_comes_in_the_right_colours(monkeypatch):
    p, _out, _proc = _player(monkeypatch, [_frame((30, 20, 10))])
    assert _wait(lambda: p._queue)
    assert p.pump(now=100.0) and p.playing
    assert p.surface.get_size() == (4, 2) and p.surface.get_at((1, 1))[:3] == (30, 20, 10)
    p.close()


def test_the_shade_is_applied_once_to_each_frame(monkeypatch):
    shade = pygame.Surface((4, 2))
    shade.fill((128, 128, 128))
    p, _out, _proc = _player(monkeypatch, [_frame((200, 100, 50))], shade=shade)
    assert _wait(lambda: len(p._queue) >= 3)
    p.pump(now=0.0)
    first = p.surface.get_at((0, 0))[:3]
    p.pump(now=1.0)
    second = p.surface.get_at((0, 0))[:3]
    assert first == second and abs(first[0] - 100) <= 2 and abs(first[2] - 25) <= 2      # darkened once, not twice
    p.close()


def test_each_frame_is_shown_when_its_time_comes(monkeypatch):
    frames = [_frame((10 * (i + 1), 0, 0)) for i in range(6)]
    p, _out, _proc = _player(monkeypatch, frames, endless=False)
    assert _wait(lambda: len(p._queue) == 6)
    red = lambda: p.surface.get_at((0, 0)).r
    assert p.pump(now=50.0) and red() == 10                  # the first frame starts the clock
    assert not p.pump(now=50.0 + 0.5 / 24)                   # not yet
    assert p.pump(now=50.0 + 1.0 / 24) and red() == 20
    assert p.pump(now=50.0 + 2.0 / 24 + 0.001) and red() == 30
    assert p.pump(now=50.0 + 5.0 / 24) and red() == 60       # frames 3 and 4 came due together: only the last shows
    p.close()


def test_a_slow_machine_skips_frames_but_never_runs_ahead(monkeypatch):
    frames = [_frame((i + 1, 0, 0)) for i in range(6)]
    p, _out, _proc = _player(monkeypatch, frames, endless=False)
    assert _wait(lambda: len(p._queue) == 6)
    p.pump(now=0.0)
    assert p.pump(now=10.0) and p.surface.get_at((0, 0)).r == 6          # long overdue: straight to the newest
    p.close()


def test_when_the_decoder_is_late_the_clock_waits_instead_of_skipping(monkeypatch):
    p, _out, proc = _player(monkeypatch, [_frame((7, 0, 0))])
    assert _wait(lambda: p._queue)
    p.pump(now=0.0)
    p._alive = False                                          # the reader stops: nothing new arrives
    time.sleep(0.2)
    p._queue.clear()
    assert not p.pump(now=100.0)                              # starved for a long time
    for i in (1, 2, 3):
        p._queue.append(_frame((i * 10, 0, 0)))
    assert p.pump(now=100.0) and p.surface.get_at((0, 0)).r == 10     # one frame as soon as it is there
    assert not p.pump(now=100.0 + 0.5 / 24)
    assert p.pump(now=100.0 + 1.0 / 24 + 0.001) and p.surface.get_at((0, 0)).r == 20   # then at the pace, not all at once
    p.close()


def test_ffmpeg_waits_when_the_game_does_not_take_frames(monkeypatch):
    p, out, _proc = _player(monkeypatch)
    assert _wait(lambda: len(p._queue) == vc.QUEUE_FRAMES)
    time.sleep(0.15)
    assert len(p._queue) == vc.QUEUE_FRAMES                  # a few frames ahead, not the whole video
    reads = out.reads
    time.sleep(0.15)
    assert out.reads <= reads + 1
    p.pump(now=0.0)
    p.pump(now=5.0)
    assert _wait(lambda: len(p._queue) == vc.QUEUE_FRAMES and out.reads > reads)       # and it goes on when room is made
    p.close()


def test_closing_kills_ffmpeg_and_ends_the_reader(monkeypatch):
    p, _out, proc = _player(monkeypatch)
    assert _wait(lambda: p._queue)
    assert p in vc._players
    p.close()
    assert proc.killed and p not in vc._players
    assert _wait(lambda: not p._thread.is_alive())
    assert not p.failed                                      # a normal end is not a failure


def test_closing_while_ffmpeg_is_still_starting_leaves_nothing_running(monkeypatch):
    gate = threading.Event()
    proc = FakeProc(FakeOut([_frame((1, 1, 1))]))

    def slow_spawn(self):
        gate.wait(2)
        return proc

    monkeypatch.setattr(vc.ClipPlayer, "_spawn", slow_spawn)
    p = vc.ClipPlayer("x.mp4", (4, 2), exe="ffmpeg-for-tests")
    p.close()
    gate.set()
    assert _wait(lambda: proc.killed and not p._thread.is_alive())


def test_if_ffmpeg_stops_the_clip_gives_up_quietly(monkeypatch):
    p, _out, proc = _player(monkeypatch, [_frame((9, 9, 9))], endless=False)
    assert _wait(lambda: p.failed)
    assert proc.killed
    p.pump(now=0.0)                                           # the one frame it did get may still be shown...
    assert not p.playing                                      # ...but the screens go back to their still picture
    p.surface = None
    assert not p.playing


def test_a_failing_start_is_a_failed_player(monkeypatch):
    def boom(self):
        raise OSError("no such executable")

    monkeypatch.setattr(vc.ClipPlayer, "_spawn", boom)
    p = vc.ClipPlayer("x.mp4", (4, 2), exe="nope")
    assert _wait(lambda: p.failed)
    assert not p.pump() and p.surface is None and not p.playing


def test_without_ffmpeg_nothing_starts(monkeypatch):
    monkeypatch.setattr(vc, "find_ffmpeg", lambda refresh=False: None)
    threads = threading.active_count()
    p = vc.ClipPlayer("x.mp4", (4, 2))
    assert p.failed and p._thread is None and p not in vc._players
    assert threading.active_count() == threads
    assert not p.pump() and p.surface is None and not p.playing
    p.close()


def test_a_player_never_blocks_the_game_when_nothing_has_arrived(monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(vc.ClipPlayer, "_spawn", lambda self: (gate.wait(1), FakeProc(FakeOut([_frame((1, 2, 3))])))[1])
    p = vc.ClipPlayer("x.mp4", (4, 2), exe="ffmpeg-for-tests")
    t = time.perf_counter()
    for _ in range(50):
        assert not p.pump()
    assert time.perf_counter() - t < 0.2 and p.surface is None
    gate.set()
    p.close()


# ------------------------------------------------------------------ with the real ffmpeg
def _collect(path, size, count):
    """The first `count` frames in order, as fast as ffmpeg gives them."""
    fps = 1000.0
    p = vc.ClipPlayer(path, size, fps=fps)
    frames = []
    end = time.time() + 60
    while len(frames) < count and time.time() < end:
        if p._queue and p.pump(now=len(frames) / fps + 1e-6):                # the time of the next frame, exactly
            frames.append(bytes(p.surface.get_buffer().raw))
        elif not p._queue:
            time.sleep(0.002)
        assert not p.failed
    p.close()
    return frames


def _diff(a, b):
    return sum(abs(x - y) for x, y in zip(a[::97], b[::97])) / len(a[::97])


@needs_ffmpeg
def test_the_shipped_clip_plays_and_loops_without_a_seam():
    path = os.path.join(ROOT, "assets", "story", "oiseaux_bleus.mp4")
    n = 229
    frames = _collect(path, (320, 180), n + 40)
    assert len(frames) == n + 40
    assert frames[n] == frames[0] and frames[n + 30] == frames[30]            # the second pass is the first again
    steps = sorted(_diff(frames[i], frames[i + 1]) for i in range(0, n - 1))
    seam = _diff(frames[n - 1], frames[n])
    assert seam <= steps[-1] * 1.5 + 0.5                                      # the loop point is no bigger a step than the clip's own
    assert len({f for f in frames}) > n // 2                                  # and the picture really moves


@needs_ffmpeg
def test_a_real_player_gives_its_first_frame_quickly_and_ends_cleanly():
    path = os.path.join(ROOT, "assets", "story", "oiseaux_bleus.mp4")
    p = vc.ClipPlayer(path, (1280, 720))
    t = time.time()
    assert _wait(lambda: p.pump(), 5.0)
    assert time.time() - t < 3.0 and p.playing and p.surface.get_size() == (1280, 720)
    proc = p._proc
    p.close()
    assert _wait(lambda: proc.poll() is not None, 3.0)                         # the process is gone
    assert not p.failed


@needs_ffmpeg
def test_a_missing_or_broken_file_fails_without_a_crash(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"this is not a video")
    for path in (str(bad), str(tmp_path / "missing.mp4")):
        p = vc.ClipPlayer(path, (64, 36))
        assert _wait(lambda: p.failed, 5.0)
        assert not p.pump() and not p.playing
        p.close()


# ------------------------------------------------------------------ the encoder tool
@needs_ffmpeg
def test_the_encoder_makes_a_silent_looping_clip(tmp_path):
    src = tmp_path / "source.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=320x180:rate=30:duration=4", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", "-y", str(src)], check=True)
    out = tmp_path / "out"
    res = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "encode_clip.py"), str(src), "demo_clip",
                          "--out-dir", str(out), "--fade", "0.5"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    mp4 = out / "demo_clip.mp4"
    assert mp4.exists() and (out / "demo_clip.jpg").exists()                 # the clip and its poster
    info = subprocess.run([FFMPEG, "-hide_banner", "-i", str(mp4)], capture_output=True, text=True).stderr
    assert "Video: h264" in info and "Audio:" not in info                    # never a sound
    assert re.search(r"\b24 fps\b", info) and "320x180" in info              # converted to the pace of the player
    counted = subprocess.run([FFMPEG, "-hide_banner", "-i", str(mp4), "-f", "null", "-"], capture_output=True,
                             text=True).stderr
    frames = int(re.findall(r"frame=\s*(\d+)", counted)[-1])
    assert frames == 4 * 24 - 12                                              # 4 s at 24 fps, minus the dissolve
    # the loop point is as smooth as any other step
    two = _collect(str(mp4), (160, 90), frames + 2)
    steps = sorted(_diff(two[i], two[i + 1]) for i in range(frames - 1))
    assert _diff(two[frames - 1], two[frames]) <= steps[-1] * 1.5 + 0.5


@needs_ffmpeg
def test_the_encoder_can_keep_a_plain_clip_without_the_dissolve(tmp_path):
    src = tmp_path / "source.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=640x360:rate=24:duration=2", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", "-y", str(src)], check=True)
    res = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "encode_clip.py"), str(src), "plain",
                          "--out-dir", str(tmp_path), "--no-loop", "--max-width", "320"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    info = subprocess.run([FFMPEG, "-hide_banner", "-i", str(tmp_path / "plain.mp4")], capture_output=True,
                          text=True).stderr
    assert "Audio:" not in info and "320x180" in info                         # silent, and cut down to the width asked
    counted = subprocess.run([FFMPEG, "-hide_banner", "-i", str(tmp_path / "plain.mp4"), "-f", "null", "-"],
                             capture_output=True, text=True).stderr
    assert int(re.findall(r"frame=\s*(\d+)", counted)[-1]) == 48            # every frame kept


@needs_ffmpeg
def test_the_encoder_refuses_names_and_clips_it_cannot_use(tmp_path):
    tool = os.path.join(ROOT, "tools", "encode_clip.py")
    res = subprocess.run([sys.executable, tool, "nothing.mp4", "bad name!", "--out-dir", str(tmp_path)],
                         capture_output=True, text=True)
    assert res.returncode != 0 and "name" in (res.stderr + res.stdout)
    short = tmp_path / "short.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=64x36:rate=24:duration=0.5", "-pix_fmt", "yuv420p", "-y", str(short)], check=True)
    res = subprocess.run([sys.executable, tool, str(short), "tiny", "--out-dir", str(tmp_path / "o")],
                         capture_output=True, text=True)
    assert res.returncode != 0 and "too short" in (res.stderr + res.stdout)


# ------------------------------------------------------------------ a clip that plays once, with a sound
def test_a_clip_that_plays_once_has_no_loop_flag_and_a_clip_that_loops_has_one():
    once = vc.command("ffmpeg", "a.mp4", (1280, 720), loop=False)
    assert "-stream_loop" not in once and "-i" in once
    assert "-stream_loop" in vc.command("ffmpeg", "a.mp4", (1280, 720), loop=True)
    assert vc.command("ffmpeg", "a.mp4", (1280, 720)) == vc.command("ffmpeg", "a.mp4", (1280, 720), True, "cover")


def test_the_three_ways_to_shape_a_picture():
    assert vc.video_filter((1280, 720), "cover").endswith("crop=1280:720") and "increase" in vc.video_filter((1280, 720))
    assert vc.video_filter((1280, 695), "exact") == "scale=1280:695:flags=bicubic"
    pad = vc.video_filter((1280, 640), "pad")
    assert "decrease" in pad and "pad=1280:640:(ow-iw)/2:(oh-ih)/2" in pad and "crop" not in pad


def test_the_largest_picture_of_its_shape_that_fits():
    assert vc.fitted_size((736, 400), (1280, 720)) == (1280, 695)
    assert vc.fitted_size((736, 400), (1280, 640)) == (1177, 640)
    assert vc.fitted_size((400, 736), (1280, 640)) == (347, 640)
    assert vc.fitted_size((10, 10), (1000, 1000)) == (1000, 1000)


def test_contain_shrinks_the_picture_to_its_own_shape_and_cover_fills_the_box(monkeypatch):
    info = {"duration": 18.0, "width": 736, "height": 400}
    monkeypatch.setattr(vc, "mp4_info", lambda path: info)
    monkeypatch.setattr(vc.ClipPlayer, "_spawn", lambda self: FakeProc(FakeOut([b""], endless=False)))
    p = vc.ClipPlayer("x.mp4", (1280, 720), exe="ffmpeg-for-tests", fit="contain", loop=False)
    assert p.size == (1280, 695) and p.box == (1280, 720) and p.mode == "exact" and p.duration == 18.0
    q = vc.ClipPlayer("x.mp4", (1280, 640), exe="ffmpeg-for-tests", fit="contain", loop=False)
    assert q.size == (1177, 640) and q.box == (1280, 640)
    c = vc.ClipPlayer("x.mp4", (1280, 720), exe="ffmpeg-for-tests")
    assert c.size == (1280, 720) and c.mode == "cover" and c.loop and not c.hard_clock
    for x in (p, q, c):
        x.close()


def test_contain_without_a_readable_header_pads_to_the_box(monkeypatch):
    monkeypatch.setattr(vc, "mp4_info", lambda path: None)
    monkeypatch.setattr(vc.ClipPlayer, "_spawn", lambda self: FakeProc(FakeOut([b""], endless=False)))
    p = vc.ClipPlayer("x.mp4", (1280, 640), exe="ffmpeg-for-tests", fit="contain", loop=False)
    assert p.size == (1280, 640) and p.mode == "pad" and p.duration is None
    p.close()


def test_a_clip_that_plays_once_finishes_instead_of_failing(monkeypatch):
    frames = [_frame((10 * (i + 1), 0, 0)) for i in range(3)]
    out = FakeOut(frames, endless=False)
    proc = FakeProc(out)
    monkeypatch.setattr(vc.ClipPlayer, "_spawn", lambda self: proc)
    p = vc.ClipPlayer("x.mp4", (4, 2), exe="ffmpeg-for-tests", loop=False)
    assert _wait(lambda: p.finished)
    assert not p.failed and not p.ended and len(p._queue) == 3                # the pictures are still to be shown
    shown = []
    for i in range(3):
        assert p.pump(now=100.0 + i / 24.0 + 1e-6)
        shown.append(p.surface.get_at((0, 0)).r)
    assert shown == [10, 20, 30]
    assert p.ended and p.ready and p.playing                                  # the last picture stays on show
    assert not p.pump(now=200.0) and p.surface.get_at((0, 0)).r == 30
    p.close()


def test_a_clip_that_plays_once_and_gives_nothing_has_failed(monkeypatch):
    out = FakeOut([], endless=False)
    monkeypatch.setattr(vc.ClipPlayer, "_spawn", lambda self: FakeProc(out))
    p = vc.ClipPlayer("x.mp4", (4, 2), exe="ffmpeg-for-tests", loop=False)
    assert _wait(lambda: p.failed)
    assert not p.finished and not p.ended and not p.ready
    p.close()


def test_a_clip_that_loops_never_finishes_by_itself(monkeypatch):
    p, _out, _proc = _player(monkeypatch, [_frame((1, 1, 1))], endless=False)
    assert _wait(lambda: p.failed)
    assert not p.finished                                                     # for a loop the end means trouble


def test_ready_means_a_picture_is_waiting_or_on_show(monkeypatch):
    gate = threading.Event()
    frame = _frame((5, 5, 5))

    class Slow(FakeOut):
        def read(self, n):
            gate.wait(2)
            return super().read(n)

    monkeypatch.setattr(vc.ClipPlayer, "_spawn", lambda self: FakeProc(Slow([frame])))
    p = vc.ClipPlayer("x.mp4", (4, 2), exe="ffmpeg-for-tests")
    assert not p.ready
    gate.set()
    assert _wait(lambda: p.ready)
    p.pump(now=0.0)
    p._queue.clear()
    assert p.ready                                                            # still on show
    p.close()


def test_a_hard_clock_never_waits_for_a_late_decoder_but_a_soft_one_does(monkeypatch):
    for hard in (False, True):
        out = FakeOut([_frame((9, 9, 9))])
        monkeypatch.setattr(vc.ClipPlayer, "_spawn", lambda self, o=out: FakeProc(o))
        p = vc.ClipPlayer("x.mp4", (4, 2), exe="ffmpeg-for-tests", hard_clock=hard)
        assert _wait(lambda: p._queue)
        p.pump(now=0.0)
        p._alive = False
        time.sleep(0.2)
        p._queue.clear()
        assert not p.pump(now=50.0)                                           # starved for a long time
        for i in (1, 2, 3):
            p._queue.append(_frame((i * 10, 0, 0)))
        assert p.pump(now=50.0 + 1e-6)
        red = p.surface.get_at((0, 0)).r
        # soft: the clock waited, so the frames come one by one; hard: it kept the time, so it skips ahead
        assert red == (10 if not hard else 30)
        p.close()


# ------------------------------------------------------------------ what the header of an mp4 says
@needs_ffmpeg
def test_the_header_of_a_clip_is_read_without_a_process(tmp_path):
    for flags, name in (([], "end.mp4"), (["-movflags", "+faststart"], "front.mp4")):          # moov last, moov first
        path = tmp_path / name
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=320x180:rate=24:duration=3", "-f", "lavfi", "-i", "sine=duration=3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"] + flags + ["-y", str(path)], check=True)
        info = vc.mp4_info(str(path))
        assert info and (info["width"], info["height"]) == (320, 180) and abs(info["duration"] - 3.0) < 0.1, name


def test_a_file_that_is_not_an_mp4_has_no_header(tmp_path):
    junk = tmp_path / "junk.mp4"
    junk.write_bytes(b"not a video at all" * 100)
    assert vc.mp4_info(str(junk)) is None
    assert vc.mp4_info(str(tmp_path / "missing.mp4")) is None
    assert vc.mp4_info(os.path.join(ROOT, "assets", "story", "oiseaux_bleus.jpg")) is None
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    assert vc.mp4_info(str(empty)) is None


def test_the_header_of_the_shipped_clips():
    info = vc.mp4_info(os.path.join(ROOT, "assets", "story", "oiseaux_bleus.mp4"))
    assert (info["width"], info["height"]) == (752, 416) and abs(info["duration"] - 9.54) < 0.05
    assert vc.mp4_info(os.path.join(ROOT, "assets", "story", "oiseaux_bleus.mp4").replace("oiseaux_bleus.mp4", "none")) is None
