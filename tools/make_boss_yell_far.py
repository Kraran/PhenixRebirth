"""Make the far cry of the red commander, heard as the approach of its base comes in sight in Scramble:
assets/sounds/boss_yell_far.wav (from assets/sounds/boss_yell.wav, which stays as it is for the other cries)

    python tools/make_boss_yell_far.py            # the committed one ("forte")
    python tools/make_boss_yell_far.py --plus OUT # a wetter, longer variant ("très forte") written to OUT

The dry cry stays on top, clear; under it, a cavernous hall (a stereo reverb of decaying filtered noise, RT60 a few
seconds) and a distinct echo that repeats, ping-pong between the speakers, each repeat darker and quieter. The tail
fades out by itself; the peak is brought back to the one of the original cry. Same format: 44.1 kHz, stereo, 16 bits.
Needs numpy and scipy.
"""
import os
import sys
import wave

import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "sounds", "boss_yell.wav")
OUT = os.path.join(ROOT, "assets", "sounds", "boss_yell_far.wav")

PRESETS = {
    # rt60 s, pre-delay s, reverb wet, echo delay s, echo feedback, echo repeats, echo wet, tail after the cry s
    "forte": dict(rt60=3.6, pre=0.045, wet=0.85, delay=0.32, fb=0.60, taps=6, echo=0.75, tail=3.6),
    "plus": dict(rt60=5.0, pre=0.060, wet=1.15, delay=0.36, fb=0.70, taps=8, echo=0.90, tail=4.8),
}


def read(path):
    with wave.open(path) as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
    return rate, data.reshape(-1, ch), width


def lowpass(x, fc, rate, order=2):
    return sosfilt(butter(order, fc, "low", fs=rate, output="sos"), x, axis=0)


def highpass(x, fc, rate, order=2):
    return sosfilt(butter(order, fc, "high", fs=rate, output="sos"), x, axis=0)


def hall_ir(rate, rt60, pre, seed=11):
    """Stereo impulse response of a big hall: two decorrelated noises, decaying by 60 dB in rt60, darker as they fade."""
    rng = np.random.default_rng(seed)
    n = int((rt60 + pre) * rate)
    t = np.arange(n) / rate
    env = np.where(t < pre, 0.0, 10.0 ** (-3.0 * (t - pre) / rt60))
    env *= np.clip((t - pre) / 0.03, 0.0, 1.0)                     # (a soft onset after the pre-delay)
    noise = rng.standard_normal((n, 2))
    bright = lowpass(noise, 6000, rate)
    dark = lowpass(noise, 1500, rate)
    mixw = np.clip(t / rt60, 0.0, 1.0)[:, None]                    # the high end dies sooner, like in a real room
    ir = (bright * (1 - mixw) + dark * mixw) * env[:, None]
    ir = highpass(ir, 120, rate)
    return ir / np.sqrt(np.sum(ir ** 2, axis=0, keepdims=True))


def make(preset):
    p = PRESETS[preset]
    rate, dry, width = read(SRC)
    assert width == 2
    n = len(dry) + int(p["tail"] * rate)
    pad = np.zeros((n, 2))
    pad[:len(dry)] = dry
    # the hall
    ir = hall_ir(rate, p["rt60"], p["pre"])
    mono = pad.mean(axis=1)
    rev = np.stack([fftconvolve(mono, ir[:, c])[:n] for c in range(2)], axis=1)
    rev *= np.sqrt(np.mean(pad ** 2)) / max(1e-9, np.sqrt(np.mean(rev[:len(dry)] ** 2)))
    # the echo: repeats every `delay`, ping-pong, each darker and quieter, and each one into the hall too
    echo = np.zeros((n, 2))
    src = pad.copy()
    gain = 1.0
    for k in range(1, p["taps"] + 1):
        src = lowpass(src, max(1200.0, 5000.0 / k), rate)
        gain *= p["fb"]
        d = int(k * p["delay"] * rate)
        side = np.array([0.35, 1.0]) if k % 2 else np.array([1.0, 0.35])
        echo[d:] += src[:n - d].mean(axis=1, keepdims=True) * side * gain
    echo_rev = np.stack([fftconvolve(echo.mean(axis=1), ir[:, c])[:n] for c in range(2)], axis=1)
    echo_rev *= np.sqrt(np.mean(echo ** 2)) / max(1e-9, np.sqrt(np.mean(echo_rev ** 2)))
    out = pad + p["wet"] * rev + p["echo"] * (0.7 * echo + 0.3 * echo_rev)
    # the end fades by itself (no cut), then the peak goes back to the original one
    fade = int(min(1.2, p["tail"] * 0.45) * rate)
    out[-fade:] *= np.cos(np.linspace(0.0, np.pi / 2, fade))[:, None] ** 2
    out *= np.max(np.abs(dry)) / np.max(np.abs(out))
    return rate, out


def write(path, rate, out):
    pcm = np.clip(np.round(out * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def main(argv):
    if len(argv) >= 2 and argv[0] == "--plus":
        write(argv[1], *make("plus"))
        print("wrote", argv[1])
    else:
        write(OUT, *make("forte"))
        print("wrote", OUT)


if __name__ == "__main__":
    main(sys.argv[1:])
