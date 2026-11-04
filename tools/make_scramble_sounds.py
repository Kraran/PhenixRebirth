"""Make the five sounds of the Scramble level: assets/sounds/scramble_launch.wav, scramble_comet.wav, scramble_brick.wav,
scramble_alarm.wav, scramble_shield.wav

    python tools/make_scramble_sounds.py          # needs only numpy

- scramble_launch : a missile leaves its station or its turret (a low thump, then a rising hiss of fire, ~0.5 s)
- scramble_comet  : a comet streaks by (a hiss that swells and fades while its pitch falls, ~0.75 s)
- scramble_brick  : a brick of the base breaks (a short ringing clank of metal, ~0.15 s)
- scramble_alarm  : the base wakes up when the scroll stops (a two-tone siren, three times, ~1.3 s)
- scramble_shield : a shot sparks off the shields of the base (a short high ping that falls, ~0.25 s)
Mono turned stereo, 44.1 kHz, 16 bits. The noise uses fixed seeds: the files are the same each time.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_lander_sounds import RATE, _fade, _lowpass, _t, _thud, save  # noqa: E402


def _band(noise, k_low, k_high):
    """A band of the noise: what one low-pass lets through minus what a lower one does."""
    return _lowpass(noise, k_high) - _lowpass(noise, k_low)


def launch():
    rng = np.random.default_rng(31)
    t = _t(0.5)
    hiss = _band(rng.uniform(-1, 1, len(t)), 0.02, 0.35) * 2.2
    swell = np.clip(t / 0.08, 0, 1) * np.exp(-np.clip(t - 0.12, 0, None) / 0.18)
    tone = np.sin(2 * np.pi * np.cumsum(180 + 900 * t) / RATE) * 0.18 * swell
    out = hiss * swell * 0.7 + tone
    thud = _thud(0.2, 140, 60, 0.6)
    out[:len(thud)] += thud
    return _fade(out / max(1.0, np.abs(out).max() / 0.9), 0.002, 0.06)


def comet():
    rng = np.random.default_rng(37)
    t = _t(0.75)
    noise = rng.uniform(-1, 1, len(t))
    # a low-pass whose cut falls as the comet passes: bright, then dull
    k = 0.45 * np.exp(-t / 0.35) + 0.04
    out = np.zeros(len(t))
    acc = 0.0
    for i, v in enumerate(noise):
        acc += (v - acc) * k[i]
        out[i] = acc
    env = np.sin(np.pi * np.clip(t / 0.75, 0, 1)) ** 1.5
    tone = np.sin(2 * np.pi * np.cumsum(520 - 260 * t / 0.75) / RATE) * 0.12
    out = (out * 2.4 + tone) * env
    return _fade(out / max(1e-6, np.abs(out).max()) * 0.85, 0.02, 0.08)


def brick():
    rng = np.random.default_rng(41)
    t = _t(0.15)
    ring = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((1240.0, 0.5), (1870.0, 0.35), (2630.0, 0.25), (3410.0, 0.15)))
    click = _lowpass(rng.uniform(-1, 1, len(t)), 0.6) * np.exp(-t / 0.008)
    out = ring * np.exp(-t / 0.035) * 0.6 + click * 0.7
    return _fade(out, 0.0005, 0.03)


def alarm():
    t = _t(1.3)
    out = np.zeros(len(t))
    for k in range(6):                                  # high, low, high, low, high, low
        i0 = int(k * 0.2 * RATE)
        tt = _t(0.19)
        f = 950.0 if k % 2 == 0 else 700.0
        wave = np.tanh(np.sin(2 * np.pi * f * tt) * 2.5) * 0.4 + np.sin(2 * np.pi * f * 2 * tt) * 0.08
        out[i0:i0 + len(tt)] += _fade(wave, 0.005, 0.02)
    return _fade(out * 0.85, 0.005, 0.1)


def shield():
    t = _t(0.25)
    freq = 1600 + 1000 * np.exp(-t / 0.04)
    ping = np.sin(2 * np.pi * np.cumsum(freq) / RATE) * np.exp(-t / 0.06)
    shimmer = np.sin(2 * np.pi * np.cumsum(freq * 1.5) / RATE) * np.exp(-t / 0.03) * 0.3
    return _fade((ping + shimmer) * 0.55, 0.001, 0.04)


SOUNDS = (("scramble_launch", launch), ("scramble_comet", comet), ("scramble_brick", brick), ("scramble_alarm", alarm),
          ("scramble_shield", shield))


if __name__ == "__main__":
    for n, f in SOUNDS:
        save(n, f())
        print("made", n)
