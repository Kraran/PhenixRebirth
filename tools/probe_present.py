"""
Phenix Rebirth display probe: compares the cost of copying the canvas to the
screen (blit) and of the flip for several ways of opening the display.

Does NOT use the game: only pygame. Every variant runs in a separate
process (the SDL render driver cannot change on the way).
The screen flickers for a few seconds, this is normal.

    python tools\\probe_present.py            (about 2 minutes)
    python tools\\probe_present.py --quick    (to check the script)

Result shown and written to probe_result.txt (at the root of the project).
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRAMES = 300
CANVAS = (1707, 720)


def _stats(values):
    v = sorted(values)
    n = len(v)
    return {
        "mean": sum(v) / n,
        "p95": v[min(n - 1, int(n * 0.95))],
        "p99": v[min(n - 1, int(n * 0.99))],
    }


def worker(spec):
    """Runs in a subprocess: opens the display asked for and measures."""
    for k, val in spec.get("env", {}).items():
        os.environ[k] = val
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    os.environ["SDL_RENDER_VSYNC"] = "1" if spec.get("vsync") else "0"
    import pygame

    pygame.init()
    flags = 0
    for name in spec["flags"]:
        flags |= getattr(pygame, name)
    size = tuple(spec["size"])
    if size == (0, 0):
        size = pygame.display.get_desktop_sizes()[0]
    if spec.get("vsync"):
        screen = pygame.display.set_mode(size, flags, vsync=1)
    else:
        screen = pygame.display.set_mode(size, flags)
    canvas = pygame.Surface(CANVAS, 0, 32).convert()
    same_format = canvas.get_masks() == screen.get_masks() and canvas.get_bitsize() == screen.get_bitsize()
    frames = spec.get("frames", FRAMES)
    blit, flip, fill_s, fill_c = [], [], [], []
    pc = time.perf_counter
    for i in range(frames + 30):
        t0 = pc()
        canvas.fill((i % 50, 20, 40))
        t1 = pc()
        screen.fill((0, 0, 0))
        t2 = pc()
        # same drawing as the game: the canvas is copied at (0, 0)
        screen.blit(canvas, (0, 0))
        t3 = pc()
        pygame.display.flip()
        t4 = pc()
        pygame.event.pump()
        if i >= 30:
            fill_c.append((t1 - t0) * 1000)
            fill_s.append((t2 - t1) * 1000)
            blit.append((t3 - t2) * 1000)
            flip.append((t4 - t3) * 1000)
    print("RESULT " + json.dumps({
        "name": spec["name"],
        "screen": list(screen.get_size()),
        "driver": pygame.display.get_driver(),
        "renderer": os.environ.get("SDL_RENDER_DRIVER", "(auto)"),
        "same_format": same_format,
        "bitsize": screen.get_bitsize(),
        "blit": _stats(blit), "flip": _stats(flip),
        "fill_screen": _stats(fill_s), "fill_canvas": _stats(fill_c),
    }))
    pygame.quit()


def variants(quick):
    sc = ["SCALED", "DOUBLEBUF", "FULLSCREEN"]
    out = [
        {"name": "current: SCALED fullscreen 1707x720", "size": CANVAS, "flags": sc},
        {"name": "SCALED fullscreen, direct3d11 renderer", "size": CANVAS, "flags": sc,
         "env": {"SDL_RENDER_DRIVER": "direct3d11"}},
        {"name": "SCALED fullscreen, direct3d (9) renderer", "size": CANVAS, "flags": sc,
         "env": {"SDL_RENDER_DRIVER": "direct3d"}},
        {"name": "SCALED fullscreen, software renderer", "size": CANVAS, "flags": sc,
         "env": {"SDL_RENDER_DRIVER": "software"}},
        {"name": "SCALED window 1707x720", "size": CANVAS, "flags": ["SCALED", "DOUBLEBUF"]},
        {"name": "SCALED fullscreen 1280x720 (16:9 canvas)", "size": (1280, 720), "flags": sc},
        {"name": "native fullscreen without SCALED (desktop)", "size": (0, 0),
         "flags": ["FULLSCREEN", "DOUBLEBUF", "HWSURFACE"]},
        {"name": "SCALED fullscreen, vsync asked for", "size": CANVAS, "flags": sc, "vsync": True},
    ]
    if quick:
        out = out[:2]
        for v in out:
            v["frames"] = 20
    return out


def _median(v):
    v = sorted(v)
    return v[len(v) // 2]


def run_all(quick):
    import machine_check

    rounds = 1 if quick else 3
    specs = variants(quick)
    runs = {sp["name"]: [] for sp in specs}
    errors = {}
    mach_before = machine_check.measure()
    for _round in range(rounds):          # interleaved passes: a one-off noise hits every variant
        for spec in specs:
            cmd = [sys.executable, os.path.abspath(__file__), "--worker", json.dumps(spec)]
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=40, cwd=ROOT)
            except subprocess.TimeoutExpired:
                errors[spec["name"]] = "too long (variant given up)"
                continue
            res = None
            for ln in p.stdout.splitlines():
                if ln.startswith("RESULT "):
                    res = json.loads(ln[7:])
            if res is None:
                err = (p.stderr.strip().splitlines() or ["(pas de message)"])[-1]
                errors[spec["name"]] = err[:90]
            else:
                runs[spec["name"]].append(res)
    mach_after = machine_check.measure()

    lines = []
    lines.append("Phenix Rebirth - display probe")
    lines.append("Date    : " + time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("System  : " + platform.platform())
    lines.append("CPU     : " + platform.processor())
    lines.append("Python  : " + sys.version.split()[0])
    lines.append("Power plan : " + (machine_check.power_plan() or "?"))
    lines.append(machine_check.describe("PC before", mach_before))
    lines.append(machine_check.describe("PC after", mach_after))
    warn = machine_check.drift_warning(mach_before, mach_after)
    if warn:
        lines.append(warn)
    lines.append("")
    lines.append("Values = median of %d passes (mean per pass), p99 = worst of the passes." % rounds)
    lines.append("%-46s | %-10s | blit mean p99 | flip mean p99 | fill screen | fill canvas" % ("Variant", "screen"))
    lines.append("-" * 118)
    first = None
    for spec in specs:
        name = spec["name"]
        rs = runs[name]
        if not rs:
            lines.append("%-46s | ECHEC : %s" % (name, errors.get(name, "?")))
            continue
        first = first or rs[0]

        def med(k, f="mean"):
            return _median([r[k][f] for r in rs])

        def worst(k):
            return max(r[k]["p99"] for r in rs)

        lines.append("%-46s | %-10s | %6.2f %6.2f | %6.2f %6.2f | %6.2f     | %6.2f" % (
            name, "x".join(str(x) for x in rs[0]["screen"]),
            med("blit"), worst("blit"), med("flip"), worst("flip"),
            med("fill_screen"), med("fill_canvas")))
    lines.append("")
    if first:
        lines.append("video driver: %s   canvas format = screen: %s (%d bits)" % (
            first["driver"], first["same_format"], first["bitsize"]))
    lines.append("Times in milliseconds. Budget: 144 Hz = 6.94 ms   120 Hz = 8.33 ms.")
    text = "\n".join(lines)
    print(text)
    try:
        with open(os.path.join(ROOT, "probe_result.txt"), "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("\nResult saved in: " + os.path.join(ROOT, "probe_result.txt"))
    except OSError as e:
        print("(could not write probe_result.txt: %s)" % e)


def main():
    ap = argparse.ArgumentParser(description="Sonde d'affichage Phenix Rebirth")
    ap.add_argument("--worker", help=argparse.SUPPRESS)
    ap.add_argument("--quick", action="store_true", help="a very short test (to check the script)")
    a = ap.parse_args()
    if a.worker:
        worker(json.loads(a.worker))
        return
    print("Display probe: the screen will flicker several times, do not touch anything (~2 minutes)...")
    run_all(a.quick)


if __name__ == "__main__":
    main()
