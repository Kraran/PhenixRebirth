"""
Sonde d'affichage Phenix Rebirth : compare le coût de la copie du canevas vers
l'écran (blit) et du flip pour plusieurs façons d'ouvrir l'affichage.

N'utilise PAS le jeu : seulement pygame. Chaque variante tourne dans un
processus séparé (le pilote de rendu SDL ne peut pas changer en cours de route).
L'écran clignote quelques secondes, c'est normal.

    python tools\\probe_present.py            (environ 40 secondes)
    python tools\\probe_present.py --quick    (vérification du script)

Résultat affiché et écrit dans probe_result.txt (à la racine du projet).
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
    """Tourne dans un sous-processus : ouvre l'affichage demandé et mesure."""
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
        # même dessin que le jeu : le canevas est copié en (0, 0)
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
    # vitesse brute de la mémoire : copie de 5 Mo en Python
    src = bytearray(CANVAS[0] * CANVAS[1] * 4)
    t0 = pc()
    for _ in range(50):
        dst = bytes(src)
    mem_ms = (pc() - t0) / 50 * 1000
    print("RESULT " + json.dumps({
        "name": spec["name"],
        "screen": list(screen.get_size()),
        "driver": pygame.display.get_driver(),
        "renderer": os.environ.get("SDL_RENDER_DRIVER", "(auto)"),
        "same_format": same_format,
        "bitsize": screen.get_bitsize(),
        "blit": _stats(blit), "flip": _stats(flip),
        "fill_screen": _stats(fill_s), "fill_canvas": _stats(fill_c),
        "mem_copy_ms": mem_ms,
    }))
    pygame.quit()


def variants(quick):
    sc = ["SCALED", "DOUBLEBUF", "FULLSCREEN"]
    out = [
        {"name": "actuel : SCALED plein écran 1707x720", "size": CANVAS, "flags": sc},
        {"name": "SCALED plein écran, rendu direct3d11", "size": CANVAS, "flags": sc,
         "env": {"SDL_RENDER_DRIVER": "direct3d11"}},
        {"name": "SCALED plein écran, rendu direct3d (9)", "size": CANVAS, "flags": sc,
         "env": {"SDL_RENDER_DRIVER": "direct3d"}},
        {"name": "SCALED plein écran, rendu opengl", "size": CANVAS, "flags": sc,
         "env": {"SDL_RENDER_DRIVER": "opengl"}},
        {"name": "SCALED plein écran, rendu logiciel", "size": CANVAS, "flags": sc,
         "env": {"SDL_RENDER_DRIVER": "software"}},
        {"name": "SCALED fenêtre 1707x720", "size": CANVAS, "flags": ["SCALED", "DOUBLEBUF"]},
        {"name": "SCALED plein écran 1280x720 (canevas 16:9)", "size": (1280, 720), "flags": sc},
        {"name": "plein écran natif sans SCALED (bureau)", "size": (0, 0),
         "flags": ["FULLSCREEN", "DOUBLEBUF", "HWSURFACE"]},
        {"name": "SCALED plein écran, vsync demandé", "size": CANVAS, "flags": sc, "vsync": True},
    ]
    if quick:
        out = out[:2]
        for v in out:
            v["frames"] = 20
    return out


def run_all(quick):
    lines = []
    results = []
    for spec in variants(quick):
        cmd = [sys.executable, os.path.abspath(__file__), "--worker", json.dumps(spec)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=ROOT)
        except subprocess.TimeoutExpired:
            results.append((spec["name"], None, "trop long"))
            continue
        res = None
        for ln in p.stdout.splitlines():
            if ln.startswith("RESULT "):
                res = json.loads(ln[7:])
        if res is None:
            err = (p.stderr.strip().splitlines() or ["(pas de message)"])[-1]
            results.append((spec["name"], None, err[:90]))
        else:
            results.append((spec["name"], res, ""))

    lines.append("Phenix Rebirth - sonde d'affichage")
    lines.append("Date    : " + time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("Système : " + platform.platform())
    lines.append("CPU     : " + platform.processor())
    lines.append("Python  : " + sys.version.split()[0])
    lines.append("")
    lines.append("%-46s | %-12s | blit moy p99 | flip moy p99 | fill écran | fill canevas" % ("Variante", "écran"))
    lines.append("-" * 120)
    for name, r, err in results:
        if r is None:
            lines.append("%-46s | ECHEC : %s" % (name, err))
            continue
        lines.append("%-46s | %-12s | %5.2f %5.2f | %5.2f %5.2f | %5.2f      | %5.2f" % (
            name, "x".join(str(x) for x in r["screen"]),
            r["blit"]["mean"], r["blit"]["p99"], r["flip"]["mean"], r["flip"]["p99"],
            r["fill_screen"]["mean"], r["fill_canvas"]["mean"]))
    lines.append("")
    first = next((r for _n, r, _e in results if r), None)
    if first:
        lines.append("pilote vidéo : %s   format canevas = écran : %s (%d bits)   copie mémoire 5 Mo : %.2f ms" % (
            first["driver"], first["same_format"], first["bitsize"], first["mem_copy_ms"]))
    lines.append("Durées en millisecondes. Budget : 144 Hz = 6,94 ms   120 Hz = 8,33 ms.")
    text = "\n".join(lines)
    print(text)
    try:
        with open(os.path.join(ROOT, "probe_result.txt"), "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("\nRésultat enregistré dans : " + os.path.join(ROOT, "probe_result.txt"))
    except OSError as e:
        print("(écriture de probe_result.txt impossible : %s)" % e)


def main():
    ap = argparse.ArgumentParser(description="Sonde d'affichage Phenix Rebirth")
    ap.add_argument("--worker", help=argparse.SUPPRESS)
    ap.add_argument("--quick", action="store_true", help="test très court (vérification du script)")
    a = ap.parse_args()
    if a.worker:
        worker(json.loads(a.worker))
        return
    print("Sonde d'affichage : l'écran va clignoter plusieurs fois, ne touche à rien (~40 s)...")
    run_all(a.quick)


if __name__ == "__main__":
    main()
