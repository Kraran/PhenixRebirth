"""Make the four menu sounds: assets/sounds/menu_move.wav, menu_confirm.wav, menu_back.wav, menu_deny.wav

    python tools/make_menu_sounds.py            # needs only numpy

Short retro blips in the spirit of the arcade (soft square waves, no reverb):
- menu_move    : the cursor moves or a value changes (a tiny tick, ~50 ms)
- menu_confirm : a choice is validated (two notes going up, ~150 ms)
- menu_back    : back / cancel (two notes going down, softer, ~130 ms)
- menu_deny    : refused (a short low double buzz, ~190 ms)
Stereo (the same in both ears), 44.1 kHz, 16 bits. Change the numbers here and run it again.
"""
import os
import wave

import numpy as np

RATE = 44100
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sounds")


def soft_square(freq, seconds, harmonics=7):
    """A square wave with only its first odd harmonics: the 8-bit colour without the harsh top."""
    t = np.arange(int(seconds * RATE)) / RATE
    out = np.zeros_like(t)
    for k in range(1, 2 * harmonics, 2):
        out += np.sin(2.0 * np.pi * freq * k * t) / k
    return out * (4.0 / np.pi) * 0.5


def envelope(n, attack=0.003, decay=None):
    """A fast attack then an exponential fall (decay = time constant in seconds, default: the length / 4)."""
    t = np.arange(n) / RATE
    if decay is None:
        decay = max(0.004, n / RATE / 4.0)
    env = np.minimum(1.0, t / max(1e-6, attack)) * np.exp(-t / decay)
    tail = min(n, int(0.004 * RATE))                       # end on zero: no click
    if tail > 0:
        env[-tail:] *= np.linspace(1.0, 0.0, tail)
    return env


def note(freq, seconds, gain, decay=None, harmonics=7):
    wav = soft_square(freq, seconds, harmonics)
    return wav * envelope(len(wav), decay=decay) * gain


def join(*parts, gap=0.0):
    pad = np.zeros(int(gap * RATE))
    out = []
    for i, p in enumerate(parts):
        if i:
            out.append(pad)
        out.append(p)
    return np.concatenate(out)


def move():
    return note(1320.0, 0.050, 0.55, decay=0.012, harmonics=4)


def confirm():
    return join(note(880.0, 0.060, 0.55, decay=0.030), note(1318.5, 0.095, 0.60, decay=0.040))


def back():
    return join(note(987.8, 0.055, 0.42, decay=0.025, harmonics=5), note(659.3, 0.080, 0.42, decay=0.035, harmonics=5))


def deny():
    a = note(146.8, 0.075, 0.70, decay=0.060, harmonics=9)
    return join(a, a * 0.85, gap=0.035)


def write(name, mono):
    peak = float(np.max(np.abs(mono))) or 1.0
    mono = mono / max(1.0, peak / 0.89)                    # never clip
    pcm = (mono * 32767.0).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    path = os.path.join(OUT_DIR, name + ".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(stereo.tobytes())
    print(f"{path}  {len(mono) / RATE:.3f} s")


def main():
    write("menu_move", move())
    write("menu_confirm", confirm())
    write("menu_back", back())
    write("menu_deny", deny())


if __name__ == "__main__":
    main()
