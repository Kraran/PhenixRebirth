"""The boot intro and the jukebox video: one silent clip (assets/video/intro.mp4) played by videoclip.py,
its music (intro.ogg) started separately and together with the first picture."""
import os
import re
import subprocess
import threading
import time

import pygame
import pytest

import intro
import videoclip
from settings import BASE_HEIGHT, BASE_WIDTH
from test_smoke import run  # noqa: F401  (fixture)

FFMPEG = videoclip.find_ffmpeg()
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="no ffmpeg on this machine")
COLOURS = [(200, 30, 30), (30, 200, 30), (30, 30, 200), (200, 200, 30)]


class FakeClip:
    """Stands for a ClipPlayer: ready after `ready_after` seconds, then one coloured frame every `step` seconds."""

    def __init__(self, frames=6, step=0.05, ready_after=0.0, duration=None, failed=False, size=(40, 20)):
        self.size, self.box, self.fps = size, size, 24.0
        self.frames, self.step, self.ready_after, self.duration = frames, step, ready_after, duration
        self.failed, self.closed, self.surface, self.loop = failed, False, None, False
        self.born, self.t0, self.ready_at, self.pumps = time.perf_counter(), None, None, 0

    @property
    def ready(self):
        ok = (not self.failed) and time.perf_counter() - self.born >= self.ready_after
        if ok and self.ready_at is None:
            self.ready_at = time.perf_counter()
        return ok

    def pump(self, now=None):
        self.pumps += 1
        if not self.ready:
            return False
        if self.t0 is None:
            self.t0 = time.perf_counter()
        i = min(self.frames - 1, int((time.perf_counter() - self.t0) / self.step))
        if self.surface is None:
            self.surface = pygame.Surface(self.size)
        self.surface.fill(COLOURS[i % len(COLOURS)])
        return True

    @property
    def ended(self):
        return self.t0 is not None and time.perf_counter() - self.t0 >= self.frames * self.step

    @property
    def playing(self):
        return self.surface is not None and not self.failed

    def close(self):
        self.closed = True


class Mixer:
    """Stands for pygame.mixer.music: remembers what the intro asked of it, in order."""

    def __init__(self):
        self.calls, self.volumes = [], []

    def stop(self):
        self.calls.append("stop")

    def load(self, path):
        self.calls.append("load")
        self.path = path

    def play(self, loops=0):
        self.calls.append("play")
        self.played_at = time.perf_counter()

    def set_volume(self, v):
        self.volumes.append(v)

    def fadeout(self, ms):
        self.calls.append("fadeout")

    def get_busy(self):
        return False


@pytest.fixture
def mixer(monkeypatch):
    m = Mixer()
    monkeypatch.setattr(pygame.mixer, "music", m)
    return m


@pytest.fixture
def screen(run, monkeypatch):
    """The real game, with what the intro draws recorded instead of shown."""
    g = run.game
    seen = []
    ox = (BASE_WIDTH - 40) // 2
    oy = (BASE_HEIGHT - 20) // 2

    def flip(*a, **k):
        gs = g.game_surface
        seen.append((tuple(gs.get_at((ox + 1, oy + 1)))[:3], tuple(gs.get_at((3, 3)))[:3]))

    monkeypatch.setattr(g, "_flip_frame", flip)
    g.seen = seen
    return g


def _use(monkeypatch, clip):
    monkeypatch.setattr(intro, "open_clip", lambda box=(BASE_WIDTH, BASE_HEIGHT): clip)
    return clip


def _key_after(seconds):
    t = threading.Timer(seconds, lambda: pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)))
    t.start()
    return t


# ------------------------------------------------------------------ the files
def test_the_intro_is_one_silent_clip_and_its_music():
    assert os.path.isfile(intro.VIDEO_PATH) and os.path.isfile(intro.AUDIO_PATH)
    assert intro.VIDEO_PATH.endswith("intro.mp4") and intro.AUDIO_PATH.endswith("intro.ogg")
    assert not os.path.exists(os.path.join(os.path.dirname(intro.VIDEO_PATH), "intro_frames"))     # no loose frames
    assert os.path.getsize(intro.VIDEO_PATH) < 8 * 1024 * 1024                                       # was 16 MB of JPEG
    assert intro.INTRO_FPS == videoclip.CLIP_FPS == 24.0


def test_the_header_of_the_intro_says_what_the_picture_is():
    info = videoclip.mp4_info(intro.VIDEO_PATH)
    assert (info["width"], info["height"]) == (736, 400) and abs(info["duration"] - 18.04) < 0.05


@needs_ffmpeg
def test_the_intro_clip_is_h264_without_sound_at_24_fps_in_bt709():
    text = subprocess.run([FFMPEG, "-hide_banner", "-i", intro.VIDEO_PATH], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stderr
    assert "Video: h264" in text and "Audio:" not in text and re.search(r"\b24 fps\b", text)
    assert "bt709" in text                                                      # colours as the source video shows them
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", text)
    seconds = int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3))
    assert abs(seconds - videoclip.mp4_info(intro.VIDEO_PATH)["duration"]) < 0.05


def test_the_music_and_the_picture_have_about_the_same_length():
    pygame.mixer.init() if not pygame.mixer.get_init() else None
    if not pygame.mixer.get_init():
        pytest.skip("no audio device")
    length = pygame.mixer.Sound(intro.AUDIO_PATH).get_length()
    assert abs(length - videoclip.mp4_info(intro.VIDEO_PATH)["duration"]) < 0.5


# ------------------------------------------------------------------ opening and warming up
def test_open_clip_plays_the_intro_once_shrunk_to_the_box_with_a_hard_clock(monkeypatch):
    made = []

    class Rec:
        def __init__(self, path, size, **k):
            self.path, self.box, self.k, self.failed, self.closed = path, tuple(size), k, False, False
            made.append(self)

        def close(self):
            self.closed = True

    monkeypatch.setattr(videoclip, "ClipPlayer", Rec)
    monkeypatch.setattr(intro, "_warm", [])
    c = intro.open_clip((1280, 640))
    assert c.path == intro.VIDEO_PATH and c.box == (1280, 640)
    assert c.k == {"fit": "contain", "loop": False, "hard_clock": True}


def test_without_the_intro_file_there_is_no_clip(monkeypatch, tmp_path):
    monkeypatch.setattr(intro, "VIDEO_PATH", str(tmp_path / "missing.mp4"))
    monkeypatch.setattr(intro, "_warm", [])
    assert intro.open_clip() is None


def test_a_warmed_up_clip_is_the_one_the_intro_gets(monkeypatch):
    made = []

    class Rec:
        def __init__(self, path, size, **k):
            self.box, self.failed, self.closed = tuple(size), False, False
            made.append(self)

        def close(self):
            self.closed = True

    monkeypatch.setattr(videoclip, "ClipPlayer", Rec)
    monkeypatch.setattr(intro, "_warm", [])
    intro.prewarm()
    intro.prewarm()                                                      # twice: still one process
    assert len(made) == 1 and intro._warm == [made[0]]
    got = intro.open_clip((BASE_WIDTH, BASE_HEIGHT))
    assert got is made[0] and intro._warm == [] and not got.closed
    again = intro.open_clip((BASE_WIDTH, BASE_HEIGHT))                   # used up: a fresh one
    assert again is not got and len(made) == 2


def test_a_warmed_up_clip_of_another_shape_or_a_failed_one_is_given_up(monkeypatch):
    made = []

    class Rec:
        def __init__(self, path, size, **k):
            self.box, self.failed, self.closed = tuple(size), False, False
            made.append(self)

        def close(self):
            self.closed = True

    monkeypatch.setattr(videoclip, "ClipPlayer", Rec)
    monkeypatch.setattr(intro, "_warm", [])
    intro.prewarm((100, 50))
    got = intro.open_clip((BASE_WIDTH, BASE_HEIGHT))
    assert made[0].closed and got is made[1] and got.box == (BASE_WIDTH, BASE_HEIGHT)
    intro.prewarm()
    made[-1].failed = True
    got = intro.open_clip()
    assert made[2].closed and got is made[3]


def test_main_warms_the_intro_up_before_the_game_loads():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")).read()
    assert src.index("intro.prewarm()") < src.index("from game import Game")


# ------------------------------------------------------------------ the boot intro
def test_no_intro_file_no_intro(screen, mixer, monkeypatch, tmp_path):
    monkeypatch.setattr(intro, "VIDEO_PATH", str(tmp_path / "missing.mp4"))
    monkeypatch.setattr(intro, "_warm", [])
    assert intro.play_intro(screen) is False and "play" not in mixer.calls


def test_without_ffmpeg_the_intro_is_left_out_quietly(screen, mixer, monkeypatch):
    clip = _use(monkeypatch, FakeClip(failed=True))
    assert intro.play_intro(screen) is False
    assert clip.closed and "play" not in mixer.calls and screen.seen == []


def test_a_picture_that_never_comes_gives_the_intro_up(screen, mixer, monkeypatch):
    monkeypatch.setattr(intro, "READY_TIMEOUT", 0.3)
    clip = _use(monkeypatch, FakeClip(ready_after=60.0))
    t = time.perf_counter()
    assert intro.play_intro(screen) is False
    assert time.perf_counter() - t < 2.0 and clip.closed and "play" not in mixer.calls


def test_the_music_starts_with_the_first_picture_not_before(screen, mixer, monkeypatch):
    clip = _use(monkeypatch, FakeClip(ready_after=0.4, frames=3))
    assert intro.play_intro(screen) is True
    assert mixer.calls.count("play") == 1 and mixer.path == intro.AUDIO_PATH
    assert mixer.played_at >= clip.ready_at                                  # never ahead of the picture
    assert mixer.played_at - clip.ready_at < 0.2                             # and right after it
    assert all(c == (0, 0, 0) for _f, c in screen.seen)                      # the corners stay black


def test_the_intro_shows_every_frame_centred_then_ends_and_cleans_up(screen, mixer, monkeypatch):
    clip = _use(monkeypatch, FakeClip(frames=4, step=0.08))
    assert intro.play_intro(screen) is True
    frames = [f for f, _c in screen.seen if f != (0, 0, 0)]
    assert set(frames) >= set(COLOURS[:4])                                    # all four pictures, drawn at the centre
    assert clip.closed and mixer.calls[-1] == "stop" and "fadeout" in mixer.calls
    assert screen.seen[-1] == ((0, 0, 0), (0, 0, 0))                          # ends on black for the menu to fade in


def test_a_key_skips_the_intro_with_a_short_fade(screen, mixer, monkeypatch):
    clip = _use(monkeypatch, FakeClip(frames=400, step=0.05))                 # a 20 second intro
    timer = _key_after(0.5)
    t = time.perf_counter()
    assert intro.play_intro(screen) is True
    timer.cancel()
    assert time.perf_counter() - t < 3.0 and clip.closed and "fadeout" in mixer.calls and mixer.calls[-1] == "stop"


def test_a_key_during_the_wait_skips_without_any_music(screen, mixer, monkeypatch):
    clip = _use(monkeypatch, FakeClip(ready_after=60.0))
    timer = _key_after(0.2)
    assert intro.play_intro(screen) is True
    timer.cancel()
    assert clip.closed and "play" not in mixer.calls


def test_closing_the_window_stops_the_intro_and_the_game(screen, mixer, monkeypatch):
    clip = _use(monkeypatch, FakeClip(frames=400))
    timer = threading.Timer(0.3, lambda: pygame.event.post(pygame.event.Event(pygame.QUIT)))
    timer.start()
    intro.play_intro(screen)
    timer.cancel()
    assert screen.running is False and clip.closed


def test_the_music_fades_out_over_the_end_of_the_picture(screen, mixer, monkeypatch):
    clip = _use(monkeypatch, FakeClip(frames=20, step=0.05, duration=1.0))    # a one second picture
    screen.music_volume = 0.5
    intro.play_intro(screen)
    ramp = mixer.volumes
    assert ramp[0] == 0.5                                                      # starts at the user's volume
    tail = [v for v in ramp if v < 0.5]
    assert tail and tail == sorted(tail, reverse=True) and min(tail) < 0.2     # then goes down to nearly nothing


def test_the_player_is_closed_even_if_the_screen_fails(screen, mixer, monkeypatch):
    clip = _use(monkeypatch, FakeClip(frames=50))

    def boom(*a, **k):
        raise RuntimeError("display lost")

    monkeypatch.setattr(screen, "_flip_frame", boom)
    with pytest.raises(RuntimeError):
        intro.play_intro(screen)
    assert clip.closed and mixer.calls[-1] == "stop"


def test_a_decoder_that_dies_in_the_middle_ends_the_intro(screen, mixer, monkeypatch):
    clip = _use(monkeypatch, FakeClip(frames=400))
    real = clip.pump

    def pump(now=None):
        r = real(now)
        if clip.pumps > 8:
            clip.failed = True
        return r

    clip.pump = pump
    assert intro.play_intro(screen) is True
    assert clip.closed and mixer.calls[-1] == "stop"


@needs_ffmpeg
def test_the_real_intro_starts_with_its_music_and_can_be_skipped(screen, mixer, monkeypatch):
    monkeypatch.setattr(intro, "_warm", [])
    timer = _key_after(1.5)
    t = time.perf_counter()
    assert intro.play_intro(screen) is True
    timer.cancel()
    assert 1.0 < time.perf_counter() - t < 6.0
    assert mixer.calls.count("play") == 1
    assert len(screen.seen) > 20 and any(f != (0, 0, 0) for f, _c in screen.seen)      # real pictures were drawn
    assert all(c == (0, 0, 0) for _f, c in screen.seen)                               # inside the 16:9 bars


@needs_ffmpeg
def test_the_real_intro_clip_gives_all_its_frames_and_ends():
    p = intro.open_clip((BASE_WIDTH, BASE_HEIGHT))
    assert p.size == (1280, 695) and p.mode == "exact" and not p.loop and abs(p.duration - 18.04) < 0.05
    p.fps = 3000.0
    n, end = 0, time.time() + 90
    while not p.ended and time.time() < end:
        if p._queue and p.pump(now=n / 3000.0 + 1e-6):                      # the time of the next frame, exactly
            n += 1
        elif not p._queue:
            time.sleep(0.002)
    assert n == 433 and p.finished and not p.failed                            # 18.04 s at 24 fps, every frame
    p.close()


@needs_ffmpeg
def test_warming_up_makes_the_first_picture_ready_at_once(monkeypatch):
    monkeypatch.setattr(intro, "_warm", [])
    intro.prewarm()
    warm = intro._warm[0]
    end = time.time() + 5
    while not warm.ready and time.time() < end:
        time.sleep(0.01)
    got = intro.open_clip()
    assert got is warm and got.ready and not got.failed
    got.close()


# ------------------------------------------------------------------ the jukebox
def _juke(g, monkeypatch, clip):
    g.juke_index = [i for i, c in enumerate(g._juke_catalog()) if c[2] == "video"][0]
    g._open_jukebox()
    monkeypatch.setattr(intro, "open_clip", lambda box=(BASE_WIDTH, BASE_HEIGHT): clip)
    return g


def test_the_jukebox_plays_the_intro_with_the_music_of_the_first_picture(run, mixer, monkeypatch):
    g = run.game
    clip = FakeClip(ready_after=0.3, frames=200, size=(1000, 560))
    _juke(g, monkeypatch, clip)
    g._juke_play_or_pause()
    assert g.juke_video and g.juke_clip is clip and "play" not in mixer.calls
    g._update_jukebox()
    assert "play" not in mixer.calls and g.juke_video                          # the picture is not there yet
    time.sleep(0.35)
    g._update_jukebox()
    assert mixer.calls.count("play") == 1 and g.sounds._current_music == "intro"
    g._update_jukebox()
    assert mixer.calls.count("play") == 1                                       # started once
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    g._draw_jukebox(surf)
    x, y = (BASE_WIDTH - 1000) // 2, 70 + (BASE_HEIGHT - 80 - 560) // 2
    assert tuple(surf.get_at((x + 5, y + 5)))[:3] in COLOURS and tuple(surf.get_at((x - 3, y + 5)))[:3] not in COLOURS


def test_the_jukebox_stops_when_the_intro_ends(run, mixer, monkeypatch):
    g = run.game
    clip = FakeClip(frames=3, step=0.03)
    _juke(g, monkeypatch, clip)
    g._juke_play_or_pause()
    end = time.time() + 3
    while g.juke_video and time.time() < end:
        g._update_jukebox()
        time.sleep(0.01)
    assert not g.juke_video and g.juke_clip is None and clip.closed
    assert mixer.calls[-1] in ("stop", "fadeout")                              # the music is stopped with the picture


def test_the_jukebox_button_stops_the_video_and_closes_the_player(run, mixer, monkeypatch):
    g = run.game
    clip = FakeClip(frames=500)
    _juke(g, monkeypatch, clip)
    g._juke_play_or_pause()
    g._update_jukebox()
    g._juke_play_or_pause()                                                     # the same button again
    assert not g.juke_video and g.juke_clip is None and clip.closed


def test_leaving_the_jukebox_closes_the_player(run, mixer, monkeypatch):
    g = run.game
    clip = FakeClip(frames=500)
    _juke(g, monkeypatch, clip)
    g._juke_play_or_pause()
    g._leave_jukebox_audio()
    assert clip.closed and not g.juke_video and g.juke_clip is None


def test_the_jukebox_shows_nothing_without_ffmpeg_or_the_file(run, mixer, monkeypatch):
    g = run.game
    clip = FakeClip(failed=True)
    _juke(g, monkeypatch, clip)
    g._juke_play_or_pause()
    assert not g.juke_video and g.juke_clip is None and clip.closed and "play" not in mixer.calls
    monkeypatch.setattr(intro, "open_clip", lambda box=None: None)
    g._juke_play_or_pause()
    assert not g.juke_video


def test_a_decoder_that_stops_stops_the_jukebox_video(run, mixer, monkeypatch):
    g = run.game
    clip = FakeClip(frames=500)
    _juke(g, monkeypatch, clip)
    g._juke_play_or_pause()
    g._update_jukebox()
    clip.failed = True
    g._update_jukebox()
    assert not g.juke_video and clip.closed


def test_the_jukebox_fits_the_picture_under_its_title(run, monkeypatch):
    g = run.game
    seen = []
    _juke(g, monkeypatch, None)
    monkeypatch.setattr(intro, "open_clip", lambda box=None: seen.append(tuple(box)) or FakeClip(failed=True))
    g._juke_play_or_pause()
    assert seen == [(BASE_WIDTH, BASE_HEIGHT - 80)]
