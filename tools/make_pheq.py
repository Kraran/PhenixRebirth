"""
The .pheq file of a track (the bands of the jukebox's LED rack, see src/pheq.py), made from its sound:

    python tools/make_pheq.py assets/music/Lyra-Voss-Oldest-Fear.mp3 [out.pheq]

(out: next to the sound, with the .pheq extension, by default). Any sound ffmpeg reads (mp3, ogg...).

The recipe is the one of the original files of the soundtrack, found by fitting it on them: all five come out again,
99.9 % of their values within 1 (out of 255), see tests/test_jukebox_lyra.py:
- the sound in mono at 22050 Hz;
- 24 frames a second, each one a 2048-sample Hann window starting at the frame's time;
- 40 bands spaced logarithmically from 40 Hz to 8 kHz, each one the mean magnitude of the FFT bins inside it (the
  bin nearest its middle when it is narrower than a bin), in dB;
- the loudest band of the whole track is 255, 48 dB under it is 0, and in between 255 * x ** 0.72.

Needs numpy and ffmpeg (the one the game finds, see src/videoclip.py).
"""
import os
import struct
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

SR = 22050
FPS = 24
NBAR = 40
N_FFT = 2048
F_MIN, F_MAX = 40.0, 8000.0
RANGE_DB = 48.0
GAMMA = 0.72


def decode(path, ffmpeg=None):
    """The sound of a file, mono float32 at SR."""
    if ffmpeg is None:
        import videoclip
        ffmpeg = videoclip.find_ffmpeg()
    if not ffmpeg:
        raise SystemExit("ffmpeg not found")
    raw = subprocess.run([ffmpeg, "-loglevel", "error", "-i", path, "-map", "0:a:0", "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def band_bins():
    """The FFT bins of each band."""
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / SR)
    edges = np.geomspace(F_MIN, F_MAX, NBAR + 1)
    bins = []
    for j in range(NBAR):
        inside = np.where((freqs >= edges[j]) & (freqs < edges[j + 1]))[0]
        if len(inside) == 0:
            inside = np.array([int(np.argmin(np.abs(freqs - (edges[j] + edges[j + 1]) / 2)))])
        bins.append(inside)
    return bins


def bands_db(samples):
    """(frames, NBAR) levels in dB."""
    hop = SR / FPS
    n = max(0, int((len(samples) - N_FFT) // hop) + 1)
    window = np.hanning(N_FFT).astype(np.float32)
    bins = band_bins()
    out = np.empty((n, NBAR), np.float32)
    starts = np.round(np.arange(n) * hop).astype(np.int64)
    for a in range(0, n, 1000):
        idx = starts[a:a + 1000, None] + np.arange(N_FFT)[None, :]
        mag = np.abs(np.fft.rfft(samples[idx] * window, axis=1))
        for j, b in enumerate(bins):
            out[a:a + 1000, j] = mag[:, b].mean(axis=1)
    return 20.0 * np.log10(out + 1e-9)


def to_bytes(db):
    top = float(db.max()) if db.size else 0.0
    x = np.clip((db - (top - RANGE_DB)) / RANGE_DB, 0.0, 1.0)
    return np.round(255.0 * x ** GAMMA).astype(np.uint8)


def make(samples):
    """The 0-255 bands of a sound, (frames, NBAR)."""
    return to_bytes(bands_db(samples))


def write(path, data):
    with open(path, "wb") as f:
        f.write(b"PHEQ1" + struct.pack("<HHfI", NBAR, FPS, float(SR), len(data)))
        f.write(np.ascontiguousarray(data, np.uint8).tobytes())


def main(src, out=None):
    out = out or os.path.splitext(src)[0] + ".pheq"
    data = make(decode(src))
    write(out, data)
    print("%s: %d frames (%.1f s)" % (out, len(data), len(data) / float(FPS)))


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
