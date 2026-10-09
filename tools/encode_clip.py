"""Turn a video into a game clip: no sound, H.264 tuned for size, and a loop without a visible seam.

    python tools/encode_clip.py SOURCE.mp4 NAME [--fade 0.5] [--crf 27] [--no-loop] [--max-width 1280]
                                [--no-poster] [--out-dir assets/video]

Writes assets/story/NAME.mp4 (and the poster assets/story/NAME.jpg when there is none yet). The game plays
the clip behind the text of the scene whose picture is NAME (see videoclip.py and story_state.clip_path).

The loop: the last `--fade` seconds are dissolved into the first ones, and the clip starts after them,
so when the file starts over there is no cut. Cost: the clip is `--fade` seconds shorter than the source.

ffmpeg is found like in the game (bin folder, imageio-ffmpeg package, PATH).
"""
import argparse
import os
import re
import subprocess
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "src")
sys.path.insert(0, SRC)

from videoclip import CLIP_FPS, find_ffmpeg  # noqa: E402

STORY = os.path.join(os.path.dirname(HERE), "assets", "story")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(exe, path):
    """(frames at CLIP_FPS, source fps, width, height) of the first video stream, decoding it once to count
    the frames the game will see."""
    info = run([exe, "-hide_banner", "-i", path]).stderr
    m = re.search(r"Stream #\d+:\d+.*?Video:.*?, (\d{2,5})x(\d{2,5})", info)
    f = re.search(r"([\d.]+) fps", info)
    if not m or not f:
        raise SystemExit("no video stream in " + path)
    out = run([exe, "-hide_banner", "-i", path, "-map", "0:v:0", "-vf", "fps=%g" % CLIP_FPS, "-f", "null", "-"]).stderr
    frames = re.findall(r"frame=\s*(\d+)", out)
    if not frames:
        raise SystemExit("cannot count the frames of " + path)
    return int(frames[-1]), float(f.group(1)), int(m.group(1)), int(m.group(2))


def loop_graph(frames, fade_frames, scale):
    """Filter graph: frames F..N-F, then the last F frames dissolved into the first F ones."""
    n, f = frames, fade_frames
    return (
        "[0:v:0]%ssplit=3[a][b][c];"
        "[a]trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS[mid];"
        "[b]trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS[tail];"
        "[c]trim=start_frame=0:end_frame=%d,setpts=PTS-STARTPTS[head];"
        "[tail][head]blend=all_expr='A*(1-(N+1)/(%d+1))+B*((N+1)/(%d+1))'[mix];"
        "[mid][mix]concat=n=2:v=1:a=0[v]" % (scale, f, n - f, n - f, n, f, f, f))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("name", help="picture name of the scene (letters, digits, underscore)")
    ap.add_argument("--fade", type=float, default=0.5, help="seconds of dissolve at the loop point (default 0.5)")
    ap.add_argument("--crf", type=int, default=27, help="quality, higher is smaller (default 27)")
    ap.add_argument("--max-width", type=int, default=1280)
    ap.add_argument("--no-loop", action="store_true", help="plain re-encode, no dissolve at the loop point")
    ap.add_argument("--no-poster", action="store_true", help="do not make the NAME.jpg poster")
    ap.add_argument("--out-dir", default=STORY)
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_]+", args.name):
        raise SystemExit("the name must be letters, digits and underscores")
    exe = find_ffmpeg()
    if not exe:
        raise SystemExit("ffmpeg not found: pip install imageio-ffmpeg")
    frames, fps, w, h = probe(exe, args.source)
    fade = 0 if args.no_loop else int(round(args.fade * CLIP_FPS))
    if fade and frames < 6 * fade:
        raise SystemExit("clip too short for a %.1f s dissolve (%d frames)" % (args.fade, frames))
    scale = "fps=%g," % CLIP_FPS                   # every clip runs at the pace of the game player
    if w > args.max_width:
        scale += "scale=%d:-2:flags=lanczos," % args.max_width
    os.makedirs(args.out_dir, exist_ok=True)
    dest = os.path.join(args.out_dir, args.name + ".mp4")
    enc = ["-an", "-sn", "-c:v", "libx264", "-preset", "veryslow", "-crf", str(args.crf), "-profile:v", "high",
           "-pix_fmt", "yuv420p", "-r", "%g" % CLIP_FPS, "-movflags", "+faststart", "-map_metadata", "-1", "-y", dest]
    if fade:
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-i", args.source, "-filter_complex",
               loop_graph(frames, fade, scale), "-map", "[v]"] + enc
    else:
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-i", args.source, "-map", "0:v:0"]
        cmd += ["-vf", scale.rstrip(",")]
        cmd += enc
    res = run(cmd)
    if res.returncode:
        raise SystemExit("ffmpeg failed:\n" + res.stderr)
    out_frames, _fps, ow, oh = probe(exe, dest)
    print("%s: %d frames %dx%d (source at %g fps) -> %d frames at %g fps, %.2f MB" %
          (dest, frames, w, h, fps, out_frames, CLIP_FPS, os.path.getsize(dest) / 1048576.0))
    poster = os.path.join(args.out_dir, args.name + ".jpg")
    if not args.no_poster and not os.path.exists(poster):
        res = run([exe, "-hide_banner", "-loglevel", "error", "-i", dest, "-frames:v", "1", "-q:v", "3",
                   "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720", "-y", poster])
        print("poster:", poster if not res.returncode else "failed: " + res.stderr)


if __name__ == "__main__":
    main()
