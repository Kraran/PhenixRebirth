"""
Small sound helpers (pure Python, no numpy): read a short wav, change its pitch, stretch it with undulations.

Used by the Space Invaders missions: the step of the invaders (the same sound, a little higher the faster
they march) and the passage of the saucer (a short sound prolonged with waves to last as long as the saucer
takes to cross the screen).
"""
import math
import wave
from array import array


def read_wav(path):
    """(samples in -1..1, sample rate) of the first channel of a 8 or 16 bit wav."""
    with wave.open(path, "rb") as w:
        n, width, chans, rate = w.getnframes(), w.getsampwidth(), w.getnchannels(), w.getframerate()
        raw = w.readframes(n)
    if width == 1:
        data = [(b - 128) / 128.0 for b in raw]
    elif width == 2:
        data = [v / 32768.0 for v in array("h", raw)]
    else:
        raise ValueError("unsupported wav width")
    return data[::chans], rate


def resample(samples, rate_in, rate_out, pitch=1.0):
    """The sound at another speed: pitch 1.1 is 10 % higher (and 10 % shorter). Linear interpolation."""
    if not samples:
        return []
    step = rate_in * float(pitch) / rate_out
    n = int((len(samples) - 1) / step) + 1
    out = []
    last = len(samples) - 1
    for i in range(n):
        p = i * step
        k = int(p)
        f = p - k
        a = samples[k]
        b = samples[k + 1] if k < last else a
        out.append(a + (b - a) * f)
    return out


def looped(samples, fade):
    """The sound made able to repeat without a click: its end melts into its beginning over `fade` samples."""
    fade = max(1, min(int(fade), len(samples) // 2))
    body = list(samples[:len(samples) - fade])
    for i in range(fade):
        k = i / fade
        body[i] = body[i] * k + samples[len(samples) - fade + i] * (1.0 - k)
    return body


def undulating(samples, rate_in, rate_out, seconds, wobble=0.07, wobble_hz=2.4, tremolo=0.18, tremolo_hz=5.5,
               fade_in=0.08, fade_out=0.5):
    """`samples` repeated and waved (pitch and volume swell) for exactly `seconds`, with a soft start and end."""
    base = looped(samples, int(rate_in * 0.25))
    n_out = int(seconds * rate_out)
    out = []
    pos = 0.0
    nb = len(base)
    ratio = rate_in / rate_out
    fi = max(1, int(fade_in * rate_out))
    fo = max(1, int(fade_out * rate_out))
    for i in range(n_out):
        t = i / rate_out
        pos += ratio * (1.0 + wobble * math.sin(2 * math.pi * wobble_hz * t))
        k = int(pos)
        f = pos - k
        a = base[k % nb]
        b = base[(k + 1) % nb]
        v = a + (b - a) * f
        v *= 1.0 - tremolo * 0.5 * (1.0 + math.sin(2 * math.pi * tremolo_hz * t))
        if i < fi:
            v *= i / fi
        elif i >= n_out - fo:
            v *= (n_out - 1 - i) / fo
        out.append(v)
    return out


def to_pcm(samples, channels=2, gain=1.0):
    """16 bit interleaved bytes for the mixer."""
    pcm = array("h")
    for v in samples:
        x = int(max(-1.0, min(1.0, v * gain)) * 32767)
        for _ in range(channels):
            pcm.append(x)
    return pcm.tobytes()
