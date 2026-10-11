"""Turn the recorded voices of the Adventure intro into game files, and find when each line of the text is said.

    python tools/make_intro_voice.py story_intro_1=take1.mp3 story_intro_2=take2.mp3 ... [--out-dir assets/story/voice]

For every `text key = recording` pair it writes `OUT/<text key>.ogg` (mono Vorbis, the level evened out, the silence at
both ends cut) and adds the key to `OUT/marks.json`: for every non-empty line of the text (the lines of
`story_state.intro_lines`, as the game shows them) the second where the voice starts it and the second where it stops. The
intro scrolls the text with that (`story.StoryHub`, `story_state.intro_voice`), so the line being said is the line on screen.

How the times are found: the pauses of the recording are detected; the line changes are matched to the pauses by dynamic
programming (the time each line should start is estimated from its number of characters), a pause that is too short to be
heard stays inside its line. The result is printed: read it with the recording, and run the tool again if a time is wrong.
Needs numpy, scipy and ffmpeg (found like in the game).
"""
import argparse
import json
import os
import subprocess
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import numpy as np  # noqa: E402

from videoclip import find_ffmpeg  # noqa: E402

RATE = 44100
HOP = 441                      # 10 ms
TARGET_DB = -20.0              # level of the speech (RMS), the same for every recording
PEAK_MAX = 0.89
LEAD, TAIL = 0.15, 0.35        # silence kept before the first word and after the last one
MIN_PAUSE = 0.18               # a pause shorter than that is just a breath


def decode(exe, path):
    """The recording as float samples, mono, RATE Hz."""
    import tempfile
    from scipy.io import wavfile
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "in.wav")
        subprocess.run([exe, "-loglevel", "error", "-y", "-i", path, "-ac", "1", "-ar", str(RATE), wav], check=True)
        sr, data = wavfile.read(wav)
    x = data.astype(np.float32)
    if data.dtype == np.int16:
        x /= 32768.0
    return x


def envelope_db(x):
    n = len(x) // HOP
    rms = np.sqrt((x[:n * HOP].reshape(n, HOP) ** 2).mean(axis=1) + 1e-12)
    return 20.0 * np.log10(rms)


def pauses(db):
    """[(start, end)] seconds of the stretches where nobody speaks (leading and trailing ones included)."""
    floor = float(np.percentile(db, 4))
    loud = float(np.percentile(db, 90))
    thr = max(floor + 10.0, loud - 34.0)
    quiet = db < thr
    out, i, n = [], 0, len(db)
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            out.append((i * HOP / RATE, j * HOP / RATE))
            i = j
        else:
            i += 1
    return out, thr


def spoken_lines(text_key, name=""):
    """The non-empty lines of the text as (index in the shown lines, characters that are said)."""
    import i18n
    import story_state as ss
    # the voice does not say the name of the pilot ("moi, {name}, j'en suis certain" is read "moi, j'en suis certain")
    lines = ss.intro_lines(lambda key: i18n.t(key).replace(" {name},", ""), text_key, name)
    return [(i, line.strip()) for i, line in enumerate(lines) if line.strip()]


def match(lines, pause_list, t_start, t_end):
    """Time at which each line starts: the line changes are put on the pauses that fit best (DP), by the length of the lines.
    Returns [(start, end)] for every line."""
    chars = np.array([len(s) for _i, s in lines], float)
    n = len(lines)
    breaks = [p for p in pause_list if t_start + 0.4 < p[0] and p[1] < t_end - 0.4 and p[1] - p[0] >= MIN_PAUSE]
    # model of the time: each character takes `rate` seconds and each line change costs about the mean pause
    total_gap = sum(b - a for a, b in breaks[: max(0, n - 1)]) or 0.0
    gap = (total_gap / max(1, min(len(breaks), n - 1))) if breaks else 0.6
    gap = min(1.2, max(0.3, gap))
    rate = max(0.01, ((t_end - t_start) - gap * (n - 1)) / chars.sum())
    est = []
    clock = t_start
    for k in range(n):
        est.append(clock)
        clock += chars[k] * rate + gap
    # cost of putting the change before line k on pause i: distance to the estimate (a long pause is a better bet);
    # no pause at all costs VIRTUAL. The best choice for all the changes, in order, by recursion with a memory.
    VIRTUAL = 3.5
    m = len(breaks)
    memo = {}

    def cost(k, i):
        if i < 0:
            return VIRTUAL
        a, b = breaks[i]
        return abs(b - est[k]) - 2.5 * min(1.0, (b - a) / 0.5)

    def best(k, first):
        """(cost, [pause index or -1 for each change k..n-1]) with the pauses used from `first` on."""
        if k >= n:
            return 0.0, []
        key = (k, first)
        if key not in memo:
            options = [(cost(k, -1) + best(k + 1, first)[0], [-1] + best(k + 1, first)[1])]
            for i in range(first, m):
                rest = best(k + 1, i + 1)
                options.append((cost(k, i) + rest[0], [i] + rest[1]))
            memo[key] = min(options, key=lambda o: o[0])
        return memo[key]

    chosen = [None] + best(1, 0)[1]
    starts = [t_start]
    ends = []
    for k in range(1, n):
        if chosen[k] == -1:
            starts.append(est[k])                          # no pause to stand on: the estimate
            ends.append(est[k] - min(gap, 0.5))
        else:
            a, b = breaks[chosen[k]]
            starts.append(b)
            ends.append(a)
    ends.append(t_end)
    # the times must go forward
    for k in range(1, n):
        starts[k] = max(starts[k], starts[k - 1] + 0.3)
    return list(zip(starts, ends))


def process(exe, key, path, out_dir):
    from scipy.io import wavfile
    x = decode(exe, path)
    db = envelope_db(x)
    quiet, thr = pauses(db)
    dur = len(x) / RATE
    t_start = quiet[0][1] if quiet and quiet[0][0] < 0.05 else 0.0
    t_end = quiet[-1][0] if quiet and quiet[-1][1] > dur - 0.05 else dur
    cut0 = max(0.0, t_start - LEAD)
    cut1 = min(dur, t_end + TAIL)
    lines = spoken_lines(key)
    pairs = match(lines, quiet, t_start, t_end)
    # the same level for every recording
    seg = x[int(t_start * RATE):int(t_end * RATE)]
    loud = seg[np.abs(seg) > 0.02]
    rms_db = 20 * np.log10(float(np.sqrt((loud ** 2).mean())) + 1e-9)
    gain = 10 ** ((TARGET_DB - rms_db) / 20.0)
    y = x[int(cut0 * RATE):int(cut1 * RATE)] * gain
    peak = float(np.abs(y).max())
    if peak * 1.0 > PEAK_MAX:
        y *= PEAK_MAX / peak
    os.makedirs(out_dir, exist_ok=True)
    wav = os.path.join(out_dir, key + ".tmp.wav")
    wavfile.write(wav, RATE, (np.clip(y, -1, 1) * 32767).astype(np.int16))
    ogg = os.path.join(out_dir, key + ".ogg")
    subprocess.run([exe, "-loglevel", "error", "-y", "-i", wav, "-c:a", "libvorbis", "-q:a", "3", "-ac", "1", ogg],
                   check=True)
    os.remove(wav)
    length = len(y) / RATE
    marks = [{"line": idx, "start": round(a - cut0, 2), "end": round(max(a - cut0 + 0.2, b - cut0), 2)}
             for (idx, _s), (a, b) in zip(lines, pairs)]
    print("%s: %.1f s (kept %.1f s), gain %+.1f dB, pauses found %d" % (key, dur, length, 20 * np.log10(gain), len(quiet)))
    for (idx, said), mk in zip(lines, marks):
        print("   %5.1f -> %5.1f  [%d] %s" % (mk["start"], mk["end"], idx, said[:70]))
    return {"file": key + ".ogg", "length": round(length, 2), "marks": marks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="+", help="text_key=recording")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "assets", "story", "voice"))
    args = ap.parse_args()
    exe = find_ffmpeg()
    if not exe:
        raise SystemExit("no ffmpeg found")
    path = os.path.join(args.out_dir, "marks.json")
    table = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            table = json.load(f)
    for pair in args.pairs:
        key, _, src = pair.partition("=")
        table[key] = process(exe, key, src, args.out_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=1, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
