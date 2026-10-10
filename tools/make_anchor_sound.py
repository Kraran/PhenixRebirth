"""Make the sound of the return to base by the quantum anchor: assets/sounds/anchor_return.wav

    python tools/make_anchor_sound.py            # needs only numpy

It follows src/anchor_fx.py second by second: a whoosh that rises and turns from one speaker to the other while the screen
is drawn into the vortex (0 - 1.6 s), a short silence-and-swell as the vortex closes, a shimmer of bells and a low thump at
the flash (1.9 s), then it fades while the map comes back. Stereo, 44.1 kHz, 16 bits, about 3.3 s.
Change the numbers here (and the ones of src/anchor_fx.py if the timing changes) and run it again.
"""
import os
import sys
import wave

import numpy as np

RATE = 44100
SWIRL, FLASH, FADE = 1.6, 0.30, 0.90          # the same as src/anchor_fx.py
TOTAL = SWIRL + FLASH + FADE + 0.4            # a little tail after the picture is back
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sounds", "anchor_return.wav")


def swept_noise(n, rng, f0, f1, width=0.5):
    """Noise through a band that goes from f0 to f1 (Hz) exponentially: a one-pole band made of two low-pass filters."""
    x = rng.standard_normal(n).astype(np.float64)
    t = np.linspace(0.0, 1.0, n)
    fc = f0 * (f1 / f0) ** t
    a_hi = 1.0 - np.exp(-2.0 * np.pi * fc / RATE)                   # the upper edge of the band
    a_lo = 1.0 - np.exp(-2.0 * np.pi * fc * width / RATE)           # the lower edge
    y1 = y2 = 0.0
    out = np.empty(n)
    for i in range(n):
        y1 += a_hi[i] * (x[i] - y1)
        y2 += a_lo[i] * (x[i] - y2)
        out[i] = y1 - y2
    return out


def main():
    rng = np.random.default_rng(7)
    n = int(TOTAL * RATE)
    t = np.arange(n) / RATE
    left = np.zeros(n)
    right = np.zeros(n)

    # the whoosh: noise swept up while the screen turns, louder and louder
    ns = int(SWIRL * RATE)
    p = np.linspace(0.0, 1.0, ns)
    whoosh = swept_noise(ns, rng, 150.0, 2600.0)
    whoosh /= np.max(np.abs(whoosh)) + 1e-9
    env = p ** 1.6 * (1.0 - 0.15 * p)
    # it goes round: from one speaker to the other, faster and faster
    pan = 0.5 + 0.45 * np.sin(2.0 * np.pi * (1.2 * p + 3.0 * p ** 2))
    left[:ns] += whoosh * env * np.cos(pan * np.pi / 2)
    right[:ns] += whoosh * env * np.sin(pan * np.pi / 2)

    # a tone that spirals up with it (a slow tremolo, a little detuned in each ear)
    freq = 110.0 * (14.0 ** (p ** 1.3))
    phase = 2.0 * np.pi * np.cumsum(freq) / RATE
    trem = 0.75 + 0.25 * np.sin(2.0 * np.pi * (5.0 + 10.0 * p) * p)
    tone = np.sin(phase) * env * trem * 0.28
    left[:ns] += tone
    right[:ns] += np.sin(phase * 1.004) * env * trem * 0.28

    # the vortex closes: a breath of air pulled in, then nothing for a moment
    close = int(FLASH * RATE)
    q = np.linspace(0.0, 1.0, close)
    pull = swept_noise(close, rng, 3000.0, 700.0)
    pull = pull / (np.max(np.abs(pull)) + 1e-9) * (1.0 - q) * 0.35
    left[ns:ns + close] += pull
    right[ns:ns + close] += pull

    # the flash: a shimmer of bells, a low thump
    t0 = int((SWIRL + FLASH * 0.55) * RATE)
    tt = np.arange(n - t0) / RATE
    shimmer = np.zeros(n - t0)
    for k, (f, g, d) in enumerate(((880.0, 0.30, 1.3), (1318.5, 0.24, 1.1), (1760.0, 0.20, 0.95), (2637.0, 0.12, 0.75),
                                   (3520.0, 0.07, 0.55))):
        shimmer += g * np.sin(2.0 * np.pi * f * tt + 0.7 * k) * np.exp(-tt / d)
    attack = np.minimum(1.0, tt / 0.012)
    shimmer *= attack
    thump = np.sin(2.0 * np.pi * (58.0 - 18.0 * np.minimum(tt, 0.5)) * tt) * np.exp(-tt / 0.22) * 0.75 * attack
    left[t0:] += shimmer * 0.9 + thump
    right[t0:] += shimmer * 1.0 + thump

    # soft start and end
    fade = np.minimum(1.0, t / 0.04) * np.minimum(1.0, (TOTAL - t) / 0.6)
    left *= fade
    right *= fade
    peak = max(np.max(np.abs(left)), np.max(np.abs(right)))
    gain = 0.9 / peak
    pcm = np.empty((n, 2), np.int16)
    pcm[:, 0] = np.clip(left * gain * 32767, -32767, 32767)
    pcm[:, 1] = np.clip(right * gain * 32767, -32767, 32767)
    out = sys.argv[1] if len(sys.argv) > 1 else OUT
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    print("written", out, os.path.getsize(out), "bytes,", round(TOTAL, 2), "s")


if __name__ == "__main__":
    main()
