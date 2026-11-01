"""Make the four sounds of the Lunar Lander level: assets/sounds/lander_thrust.wav, lander_beep.wav, lander_land.wav,
lander_rough.wav

    python tools/make_lander_sounds.py            # needs only numpy

- lander_thrust : the engine, a soft rumble of filtered noise (~0.28 s, played again every 0.2 s so the pieces overlap)
- lander_beep   : the warning when the fuel runs low (a short high double tone, ~0.12 s)
- lander_land   : a gentle landing (a low thud, then two rising notes)
- lander_rough  : a hard landing (a heavy thud with a short rattle of metal)
Mono turned stereo, 44.1 kHz, 16 bits. The noise uses a fixed seed: the files are the same each time.
"""
import os
import wave

import numpy as np

RATE = 44100
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sounds")


def _t(seconds):
    return np.arange(int(seconds * RATE)) / RATE


def _fade(sig, a=0.01, b=0.03):
    n = len(sig)
    na, nb = min(n, int(a * RATE)), min(n, int(b * RATE))
    sig = sig.copy()
    if na:
        sig[:na] *= np.linspace(0.0, 1.0, na)
    if nb:
        sig[-nb:] *= np.linspace(1.0, 0.0, nb)
    return sig


def _lowpass(sig, k):
    out = np.zeros_like(sig)
    acc = 0.0
    for i, v in enumerate(sig):
        acc += (v - acc) * k
        out[i] = acc
    return out


def thrust():
    rng = np.random.default_rng(11)
    t = _t(0.28)
    noise = _lowpass(rng.uniform(-1, 1, len(t)), 0.08) * 3.0
    rumble = np.sin(2 * np.pi * 52 * t) * 0.5 + np.sin(2 * np.pi * 78 * t) * 0.3
    return _fade((noise * 0.8 + rumble) * 0.55, 0.03, 0.06)


def beep():
    t = _t(0.12)
    sig = np.sign(np.sin(2 * np.pi * 1320 * t)) * 0.35 + np.sin(2 * np.pi * 1760 * t) * 0.25
    return _fade(sig * 0.7, 0.004, 0.02)


def _thud(seconds, f0, f1, level):
    t = _t(seconds)
    freq = f1 + (f0 - f1) * np.exp(-t / 0.05)
    return np.sin(2 * np.pi * np.cumsum(freq) / RATE) * np.exp(-t / (seconds / 4)) * level


def land():
    thud = _thud(0.35, 120, 50, 0.8)
    t = _t(0.5)
    notes = np.zeros(int(0.5 * RATE))
    for start, f in ((0.12, 660.0), (0.26, 880.0)):
        i = int(start * RATE)
        tt = _t(0.2)
        notes[i:i + len(tt)] += np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.07) * 0.35
    out = np.zeros(len(t))
    out[:len(thud)] += thud
    return _fade(out + notes, 0.002, 0.05)


def rough():
    rng = np.random.default_rng(23)
    thud = _thud(0.5, 150, 38, 1.0)
    t = _t(0.5)
    rattle = _lowpass(rng.uniform(-1, 1, len(t)), 0.5) * np.exp(-t / 0.08) * 0.8
    metal = np.sin(2 * np.pi * 310 * t) * np.exp(-t / 0.06) * 0.3
    out = thud + rattle + metal
    return _fade(out / max(1.0, np.abs(out).max() / 0.95), 0.001, 0.08)


def save(name, sig):
    sig = np.clip(sig, -1.0, 1.0)
    data = (sig * 32000).astype("<i2")
    stereo = np.repeat(data[:, None], 2, axis=1)
    os.makedirs(OUT_DIR, exist_ok=True)
    with wave.open(os.path.join(OUT_DIR, name + ".wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(stereo.tobytes())


if __name__ == "__main__":
    for n, f in (("lander_thrust", thrust), ("lander_beep", beep), ("lander_land", land), ("lander_rough", rough)):
        save(n, f())
        print("made", n)
