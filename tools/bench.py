#!/usr/bin/env python3
"""
Benchmark de fluidité : mesure ce que coûte une image du jeu sur CE PC.

    python tools\\bench.py                  (plein écran, vsync coupé)
    python tools\\bench.py --mode window    (fenêtre)
    python tools\\bench.py --vsync on       (comme en jeu normal)

Le script joue tout seul (pilote automatique, vaisseau invincible) : un moment
sur le menu, puis les niveaux 1 à 6 dont le boss du niveau 5. Pour chaque
partie il mesure, image par image :
  - logique   : événements + mise à jour du jeu
  - dessin    : tout le dessin, sans l'affichage final
  - affichage : l'envoi de l'image à l'écran (flip)
  - total     : la somme, soit ce que coûte vraiment une image

Le jeu avance à pas fixe de 1/144 s par image et SANS limiteur : le total
moyen donne donc directement le nombre d'images par seconde que le PC peut
tenir. Pour du 144 Hz, il faut que presque toutes les images coûtent moins de
6,94 ms.

Rien n'est lu ni écrit dans tes fichiers de jeu (réglages, scores, succès) :
tout se passe dans un dossier temporaire. Le résultat est écrit dans
bench_result.txt (à côté du jeu). Ne touche pas au clavier pendant le test.
"""
import argparse
import gc
import json
import os
import platform
import shutil
import statistics
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

STEP = 1 / 144          # game time simulated per frame
BUDGETS = ((144, 1000 / 144), (120, 1000 / 120), (60, 1000 / 60))


def parse_args():
    ap = argparse.ArgumentParser(description="Benchmark de fluidité Phenix Rebirth")
    ap.add_argument("--mode", choices=("fullscreen", "borderless", "window"), default="fullscreen")
    ap.add_argument("--vsync", choices=("off", "adaptive", "on"), default="off")
    ap.add_argument("--monitor", type=int, default=0, help="numéro de l'écran (0 = principal)")
    ap.add_argument("--mute", action="store_true", help="sans son (carte son factice)")
    ap.add_argument("--quick", action="store_true", help="test très court (vérification du script)")
    return ap.parse_args()


def pct(values, p):
    s = sorted(values)
    return s[min(len(s) - 1, int(len(s) * p))] if s else 0.0


def main():
    args = parse_args()
    if args.mute:
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    # Private user folder, set up BEFORE any game module is imported.
    user_dir = tempfile.mkdtemp(prefix="phenix_bench_")
    import settings

    settings.user_data_dir = lambda: user_dir
    with open(os.path.join(user_dir, "settings.json"), "w", encoding="utf-8") as f:
        json.dump({
            "display_mode": args.mode, "vsync_mode": args.vsync,
            "monitor_index": args.monitor, "fps_cap": 120, "show_fps": False,
            "language": "fr", "input_mode": "keyboard",
        }, f)

    import pygame
    import replay
    import game as game_module

    # time spent presenting the frame (flip) is measured apart from the drawing
    flip_ms = [0.0]
    real_flip = game_module.Game._flip_frame

    def timed_flip(self, *a, **k):
        t = time.perf_counter()
        try:
            return real_flip(self, *a, **k)
        finally:
            flip_ms[0] += (time.perf_counter() - t) * 1000

    game_module.Game._flip_frame = timed_flip

    g = replay._new_game(12345)
    keys = {"cur": replay._Keys()}
    pygame.key.get_pressed = lambda: keys["cur"]

    n = 300 if args.quick else 1200
    menu_n = 120 if args.quick else 600
    segments = [("Menu titre", menu_n, None)]
    for stage in (1, 2, 3, 4, 5, 6):
        label = "Niveau %d%s" % (stage, " (boss)" if stage % 5 == 0 else "")
        segments.append((label, n, stage))

    results = []
    frame = 0
    print("Test en cours (%s frames environ), ne touche à rien..." % sum(s[1] for s in segments))
    gc.collect()
    for label, count, stage in segments:
        if stage == 1:
            replay._solo("phoenix")(g)
        elif stage:
            g.stage = stage
            g._setup_stage(stage)
            g.stage_transition = None
        rec = {"logic": [], "draw": [], "flip": [], "total": []}
        for i in range(count):
            if stage:
                for ship in g._ships():
                    ship.infinite_lives = True
                if i == count // 2:
                    for ship in g._ships():
                        ship.phenix_gauge = 10.0
                    replay._press(pygame.K_RSHIFT)
                if i == count // 2 + 3:
                    replay._release(pygame.K_RSHIFT)
                keys["cur"] = replay._Keys(replay._pressed(g, frame))
            else:
                keys["cur"] = replay._Keys(replay._menu_pressed(g, frame))
            g.dt = STEP
            flip_ms[0] = 0.0
            t0 = time.perf_counter()
            g.handle_events()
            g.update()
            t1 = time.perf_counter()
            g.draw()
            t2 = time.perf_counter()
            if not g.running:
                print("Le jeu s'est fermé pendant le test.")
                break
            logic = (t1 - t0) * 1000
            draw_all = (t2 - t1) * 1000
            rec["logic"].append(logic)
            rec["draw"].append(draw_all - flip_ms[0])
            rec["flip"].append(flip_ms[0])
            rec["total"].append(logic + draw_all)
            frame += 1
        results.append((label, rec))

    info = [
        "Phenix Rebirth - benchmark de fluidité",
        "Date        : %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
        "Système     : %s" % platform.platform(),
        "Processeur  : %s" % (platform.processor() or "?"),
        "Python      : %s   pygame %s   SDL %s" % (
            platform.python_version(), pygame.version.ver, ".".join(map(str, pygame.get_sdl_version()))),
        "Pilote vidéo: %s" % pygame.display.get_driver(),
        "Affichage   : %s  fenêtre/écran %s  vsync=%s  moniteur=%d  panneau détecté %s Hz  mode %s" % (
            args.mode, g.screen.get_size(), args.vsync, args.monitor,
            getattr(g, "panel_hz", "?"), getattr(g, "_gpu_backend", "?")),
        "Son         : %s" % ("coupé" if args.mute else "actif"),
        "",
    ]
    lines = list(info)
    head = "%-18s %6s | %6s %6s | %6s %6s %6s | %6s %6s | %7s %7s %7s %7s %6s | %6s" % (
        "Partie", "images", "logiq.", "p99", "dessin", "p99", "max", "affich", "p99",
        "total", "p95", "p99", "max", "i/s", ">6,9ms")
    lines += [head, "-" * len(head)]
    all_total = []
    for label, rec in results:
        t = rec["total"]
        if not t:
            continue
        all_total += t
        over = 100.0 * sum(1 for x in t if x > BUDGETS[0][1]) / len(t)
        lines.append("%-18s %6d | %6.2f %6.2f | %6.2f %6.2f %6.2f | %6.2f %6.2f | %7.2f %7.2f %7.2f %7.2f %6.0f | %5.1f%%" % (
            label, len(t),
            statistics.mean(rec["logic"]), pct(rec["logic"], .99),
            statistics.mean(rec["draw"]), pct(rec["draw"], .99), max(rec["draw"]),
            statistics.mean(rec["flip"]), pct(rec["flip"], .99),
            statistics.mean(t), pct(t, .95), pct(t, .99), max(t),
            1000.0 / statistics.mean(t), over))
    lines.append("")
    lines.append("Durées en millisecondes. i/s = images par seconde que le PC peut tenir (1000 / total moyen).")
    lines.append("Budget par image : 144 Hz = 6,94 ms   120 Hz = 8,33 ms   60 Hz = 16,67 ms.")
    if all_total:
        lines.append("")
        lines.append("Bilan sur toutes les parties (%d images) :" % len(all_total))
        for hz, budget in BUDGETS:
            ok = 100.0 * sum(1 for x in all_total if x <= budget) / len(all_total)
            lines.append("  %3d Hz : %5.1f %% des images tiennent dans le budget (%.2f ms)" % (hz, ok, budget))
        p99 = pct(all_total, .99)
        mean = statistics.mean(all_total)
        lines.append("  moyenne %.2f ms  /  99%% des images sous %.2f ms  /  pire image %.2f ms" % (mean, p99, max(all_total)))
        if p99 <= BUDGETS[0][1]:
            verdict = "144 Hz : OK, ce PC a de la marge."
        elif mean <= BUDGETS[0][1]:
            verdict = "144 Hz : limite. La moyenne tient, mais certaines images (explosions, boss) dépassent le budget."
        elif mean <= BUDGETS[1][1]:
            verdict = "144 Hz : non, 120 Hz : oui. Il faut gagner du temps par image pour viser le 144."
        else:
            verdict = "144 Hz : non pour l'instant."
        lines.append("  >>> " + verdict)

    text = "\n".join(lines)
    print()
    print(text)
    out = os.path.join(ROOT, "bench_result.txt")
    try:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("\nRésultat enregistré dans : %s" % out)
    except OSError as e:
        print("\n(Impossible d'écrire bench_result.txt : %s)" % e)

    g.running = False
    pygame.quit()
    shutil.rmtree(user_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
