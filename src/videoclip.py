"""Small videos played in the game: looping clips behind the screens (6 to 10 seconds) and the boot intro. No sound
in the video itself (the intro's music is a separate file the game starts at the same time).

ffmpeg runs as a separate process that decodes, scales and crops the video, so the game only copies one finished
picture per frame (and darkens it with one multiply). The process loops the file by itself (`-stream_loop`) and
runs at a low priority; a thread reads its frames into a short queue (the process waits when the queue is full),
and `pump()` shows each frame when its time comes, at CLIP_FPS. The queue also hides the short pause ffmpeg makes
at each loop point. Every clip is encoded at CLIP_FPS by tools/encode_clip.py.

ffmpeg comes from, in this order: the `bin` folder of the game (or of the user data), the `imageio-ffmpeg`
package (listed in requirements.txt and packed into the exe by build_exe.bat), then the PATH.
Without ffmpeg, or if it fails, `ClipPlayer.surface` stays None and the screens show their still picture.

A decoder that does not start, or stops before its first picture (on a Windows that was just installed, the antivirus
holds a new ffmpeg.exe for a few seconds while it scans it), is started again a few times (RETRY_WAITS) before the
still takes over for good; what ffmpeg said is written to errors.log.
"""
import atexit
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque

import pygame

from errlog import log_exc, log_note

CLIP_FPS = 24.0         # pace of every clip (the encoder tool converts to it)
QUEUE_FRAMES = 6        # decoded frames kept ahead: a quarter of a second
RETRY_WAITS = (0.5, 1.5, 3.0)   # a decoder that gave no picture is started again after these waits (then: the still)

_exe_cache = []          # [path or None] once looked up


def _roots():
    roots = []
    try:
        from settings import project_root
        roots.append(os.path.join(project_root(), "bin"))
    except Exception:
        log_exc("videoclip._roots")
    roots.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin"))
    try:
        from settings import user_data_dir
        roots.append(os.path.join(user_data_dir(), "bin"))
    except Exception:
        log_exc("videoclip._roots")
    return roots


def find_ffmpeg(refresh=False):
    """Path of an ffmpeg executable, or None. Looked up once."""
    if _exe_cache and not refresh:
        return _exe_cache[0]
    found = None
    for root in _roots():
        for name in ("ffmpeg.exe", "ffmpeg"):
            fp = os.path.join(root, name)
            if os.path.isfile(fp):
                found = fp
                break
        if found:
            break
    if not found:
        try:
            import imageio_ffmpeg
            fp = imageio_ffmpeg.get_ffmpeg_exe()
            if fp and os.path.isfile(fp):
                found = fp
        except Exception:
            pass                                   # the package is simply not installed
    if not found:
        found = shutil.which("ffmpeg")
    _exe_cache[:] = [found]
    return found


def video_filter(size, mode="cover"):
    """ffmpeg filter that gives the picture the shape of `size`.

    "cover": scaled up to fill it, the overflow cropped. "exact": stretched to it (the caller made `size` the
    picture's own shape). "pad": the whole picture inside it, black bars where it does not fit."""
    w, h = size
    if mode == "exact":
        return "scale=%d:%d:flags=bicubic" % (w, h)
    if mode == "pad":
        return ("scale=%d:%d:force_original_aspect_ratio=decrease:flags=bicubic,"
                "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:black" % (w, h, w, h))
    return "scale=%d:%d:force_original_aspect_ratio=increase:flags=bicubic,crop=%d:%d" % (w, h, w, h)


def command(exe, path, size, loop=True, mode="cover"):
    """The ffmpeg command line: raw 32-bit frames (B, G, R, unused) on stdout, for ever when `loop`."""
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-nostdin"]
    if loop:
        cmd += ["-stream_loop", "-1"]
    return cmd + ["-threads", "2", "-i", path, "-an", "-sn", "-filter_threads", "2",
                  "-vf", video_filter(size, mode), "-f", "rawvideo", "-pix_fmt", "bgr0", "-"]


def mp4_info(path):
    """{"duration": seconds, "width": px, "height": px} read from the header of an mp4 (no process, no decoding),
    or None when the file is not one we can read. Width and height are those of the first video track."""
    import struct

    def boxes(f, start, end):
        pos = start
        while pos + 8 <= end:
            f.seek(pos)
            head = f.read(8)
            if len(head) < 8:
                return
            size, kind = struct.unpack(">I4s", head)
            body = pos + 8
            if size == 1:
                size = struct.unpack(">Q", f.read(8))[0]
                body += 8
            elif size == 0:
                size = end - pos
            if size < 8:
                return
            yield kind, body, min(end, pos + size)
            pos += size

    try:
        info = {}
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            total = f.tell()
            for kind, body, stop in boxes(f, 0, total):
                if kind != b"moov":
                    continue
                for kind2, body2, stop2 in boxes(f, body, stop):
                    if kind2 == b"mvhd":
                        f.seek(body2)
                        version = f.read(1)[0]
                        f.seek(body2 + 4 + (16 if version == 1 else 8))
                        scale = struct.unpack(">I", f.read(4))[0]
                        length = struct.unpack(">Q" if version == 1 else ">I", f.read(8 if version == 1 else 4))[0]
                        if scale:
                            info["duration"] = length / float(scale)
                    elif kind2 == b"trak" and "width" not in info:
                        for kind3, body3, stop3 in boxes(f, body2, stop2):
                            if kind3 != b"tkhd":
                                continue
                            f.seek(stop3 - 8)
                            w, h = struct.unpack(">II", f.read(8))
                            if w >> 16 and h >> 16:
                                info["width"], info["height"] = w >> 16, h >> 16
                break
        return info if "duration" in info else None
    except Exception:
        return None


def fitted_size(source, box):
    """The largest size with the shape of `source` that fits in `box`."""
    scale = min(box[0] / float(source[0]), box[1] / float(source[1]))
    return max(1, int(source[0] * scale)), max(1, int(source[1] * scale))


def make_shade(size, boxes):
    """Grey picture that darkens a frame when multiplied into it (BLEND_RGB_MULT), like black boxes would.

    `boxes` is [(x, width, alpha 0..255)] over the full height, in that order: where two boxes overlap the
    darkening adds up the way two translucent black layers do. Multiplying is a lot cheaper than blending
    (0.4 ms against 1.2 ms for a 1280x720 picture), and far cheaper than asking ffmpeg to draw the boxes."""
    w, h = int(size[0]), int(size[1])
    keep = [1.0] * w
    for x, bw, alpha in boxes:
        f = 1.0 - max(0, min(255, int(alpha))) / 255.0
        for i in range(max(0, int(x)), min(w, int(x) + int(bw))):
            keep[i] *= f
    shade = pygame.Surface((w, h))
    start = 0
    for i in range(1, w + 1):
        if i == w or int(round(255 * keep[i])) != int(round(255 * keep[start])):
            v = int(round(255 * keep[start]))
            shade.fill((v, v, v), pygame.Rect(start, 0, i - start, h))
            start = i
    return shade


def _tail(err, limit=300):
    """The last words ffmpeg wrote on its error output (a temporary file), closed after reading."""
    if err is None:
        return ""
    try:
        err.seek(0)
        text = err.read().decode("utf-8", "replace").strip()
        return " ".join(text.split())[-limit:]
    except Exception:
        return ""
    finally:
        try:
            err.close()
        except Exception:
            pass


_players = []


@atexit.register
def _close_all():
    for p in list(_players):
        p.close()


class ClipPlayer:
    """One video playing: `pump()` once per drawn frame, then blit `surface` when it is not None."""

    def __init__(self, path, size, shade=None, exe=None, fps=CLIP_FPS, loop=True, fit="cover", hard_clock=False):
        """`size` is the box to fill. fit="cover" fills it (the overflow is cropped); fit="contain" shrinks the
        picture to the box and `size` becomes the picture's own size: centre `surface` yourself. A clip that
        does not `loop` plays once and then `ended` is true. With `hard_clock` a late decoder never makes the
        picture wait (frames are skipped to keep the time): for pictures that go with a sound."""
        self.path = path
        self.loop = bool(loop)
        self.hard_clock = bool(hard_clock)
        self.info = mp4_info(path)
        self.duration = self.info["duration"] if self.info else None
        self.mode = "cover"
        size = (int(size[0]), int(size[1]))
        self.box = size                            # the box asked for (the picture may be smaller: fit="contain")
        if fit == "contain":
            self.mode = "pad"
            if self.info and "width" in self.info:
                size, self.mode = fitted_size((self.info["width"], self.info["height"]), size), "exact"
        self.size = size
        self.shade = shade                         # grey picture multiplied into every frame (make_shade)
        self.exe = exe if exe is not None else find_ffmpeg()
        self.fps = float(fps)
        self.surface = None                        # the picture of the moment (None until the first frame)
        self.failed = self.exe is None             # no decoder, or it stopped: the still takes over
        self.finished = False                      # a clip that does not loop: its last frame has been read
        self._got = False
        self._bytes = self.size[0] * self.size[1] * 4
        self._cond = threading.Condition()
        self._queue = deque()                      # decoded frames not shown yet
        self._shown = 0                            # frames shown so far
        self._t0 = None                            # when frame 0 was due
        self._proc = None
        self._err_file = None
        self._alive = True
        self._thread = None
        if not self.failed:
            self._thread = threading.Thread(target=self._read, name="clip-reader", daemon=True)
            self._thread.start()
            _players.append(self)

    def _spawn(self):
        err = self._err_file                       # (a temporary file for what ffmpeg says, or None)
        flags = 0
        if sys.platform.startswith("win"):
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
        return subprocess.Popen(command(self.exe, self.path, self.size, self.loop, self.mode), stdout=subprocess.PIPE,
                                stderr=err if err is not None else subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                creationflags=flags)

    def _read(self):
        """Read the frames of ffmpeg. A run that gives no picture (it could not start, or stopped at once) is tried again
        after RETRY_WAITS; a looping clip whose decoder stops later is started again the same way."""
        tries = 0
        while self._alive:
            outcome, why = self._run_once()
            if not self._alive or outcome == "done":
                return
            if tries >= len(RETRY_WAITS):
                log_note("videoclip: %s gave up after %d tries (%s)" % (os.path.basename(self.path), tries + 1, why))
                self.failed = True                  # the still takes over for good
                return
            log_note("videoclip: %s: %s, trying again" % (os.path.basename(self.path), why))
            end = time.monotonic() + RETRY_WAITS[tries]
            tries += 1
            while self._alive and time.monotonic() < end:
                time.sleep(0.05)

    def _run_once(self):
        """One run of ffmpeg: ("done", "") when it ended as it should (a clip played once to its end), else ("retry",
        what went wrong)."""
        proc = None
        err = None
        got = False
        why = "no picture"
        try:
            err = tempfile.TemporaryFile()
        except Exception:
            err = None
        try:
            self._err_file = err
            proc = self._proc = self._spawn()
            if not self._alive:
                return "done", ""                   # closed while the process was starting (finally kills it)
            out = proc.stdout
            while self._alive:
                data = out.read(self._bytes)
                if len(data) < self._bytes:
                    break                           # ffmpeg stopped (unreadable file, killed...)
                got = self._got = True
                with self._cond:
                    while self._alive and len(self._queue) >= QUEUE_FRAMES:
                        self._cond.wait(0.1)        # ffmpeg waits for the game to catch up
                    if not self._alive:
                        break
                    self._queue.append(data)
        except Exception as exc:
            why = "%s: %s" % (type(exc).__name__, exc)
            if self._alive:
                log_exc("videoclip._read")
        finally:
            if proc is not None:
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=2)
                except Exception:
                    pass
            said = _tail(err)
            if said:
                why += " — ffmpeg: " + said
        if not self._alive:
            return "done", ""
        if got and not self.loop:
            self.finished = True                    # the end of a clip that plays once
            return "done", ""
        if got:
            why = "the decoder stopped"
        return "retry", why

    def pump(self, now=None):
        """Show the frame whose time has come. True when `surface` changed. Frames that came due together
        are skipped but the last; when none is ready the clock waits instead of skipping."""
        now = time.monotonic() if now is None else now
        data = None
        with self._cond:
            if self._t0 is None:
                if not self._queue:
                    return False
                self._t0 = now                      # the first frame starts the clock
            while self._queue and self._t0 + self._shown / self.fps <= now:
                data = self._queue.popleft()
                self._shown += 1
            if data is not None:
                self._cond.notify()                 # room for the reader
            elif not self._queue and not self.hard_clock:
                self._t0 = max(self._t0, now - self._shown / self.fps)   # starved: the clock waits
        if data is None:
            return False
        try:
            if self.surface is None:
                self.surface = pygame.Surface(self.size)         # 32 bits: bytes B, G, R, unused
            buf = self.surface.get_buffer()
            buf.write(data)
            del buf
            if self.shade is not None:
                self.surface.blit(self.shade, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        except Exception:
            log_exc("videoclip.pump")
            self.failed = True
            self.surface = None
            return False
        return True

    @property
    def playing(self):
        return self.surface is not None and not self.failed

    @property
    def ready(self):
        """A frame is waiting (or one is already on show): the picture can start together with its sound."""
        return self.surface is not None or bool(self._queue)

    @property
    def ended(self):
        """A clip that plays once has shown its last frame."""
        with self._cond:
            return self.finished and not self._queue

    def close(self):
        self._alive = False
        with self._cond:
            self._cond.notify_all()
        proc = self._proc
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        if self in _players:
            _players.remove(self)
