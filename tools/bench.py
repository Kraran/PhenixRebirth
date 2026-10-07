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
  - copie     : préparation de l'image avant l'envoi (bordures, copie du canevas)
  - flip      : l'envoi de l'image à l'écran (pygame.display.flip)
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
    ap.add_argument("--profile", action="store_true",
                    help="au lieu des mesures : liste les fonctions de dessin les plus coûteuses (menu, niveau 3, boss)")
    return ap.parse_args()


def pct(values, p):
    s = sorted(values)
    return s[min(len(s) - 1, int(len(s) * p))] if s else 0.0


def run_profile(args, g, run_frame, new_rec, settings, replay, root):
    """--profile: which drawing functions cost the most on this PC (menu, level 3, boss)."""
    import cProfile
    import io
    import pstats

    n = 120 if args.quick else 400
    out = ["Phenix Rebirth - profil du dessin (fonctions les plus coûteuses)",
           "Date : %s   écran/canevas : %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), g.screen.get_size()),
           "Le profileur ralentit le jeu : seuls les rangs et les proportions comptent.", ""]

    def section(title, playing):
        prof = cProfile.Profile()
        rec = new_rec()
        for i in range(n):
            run_frame(rec, playing, i, n, prof)
        buf = io.StringIO()
        stats = pstats.Stats(prof, stream=buf)
        stats.sort_stats("tottime").print_stats(14)
        txt = buf.getvalue().replace(root, "").replace("\\", "/")
        out.append("=== %s (%d images) ===" % (title, n))
        keep = [l[:150] for l in txt.split("\n") if l.strip()][1:]
        out.extend(keep)
        # qui appelle les 2 opérations les plus fréquentes (blit / fill) ?
        for op in ("'blit'", "'fill'"):
            for key, val in stats.stats.items():
                if key[2].startswith("<method " + op):
                    callers = sorted(val[4].items(), key=lambda kv: -kv[1][2])[:6]
                    out.append("  appelants de %s (appels / par image / temps) :" % op.strip("'"))
                    for (fn, line, name), (cc, nc, tt, ct) in callers:
                        out.append("    %6d %5.1f %7.3f s  %s:%d(%s)" % (
                            nc, nc / float(n), tt, os.path.basename(fn), line, name))
        out.append("")

    section("Menu titre", False)
    replay._solo("phoenix")(g)
    for stage, title in ((3, "Niveau 3"), (5, "Niveau 5 (boss)")):
        if g.stage < stage:
            g.stage = stage
            g._setup_stage(stage)
            g.stage_transition = None
            for ship in g._ships():
                ship.y = settings.BASE_HEIGHT - 95
        while g.stage_transition is not None:
            run_frame(new_rec(), True, 0, n)
        section(title, True)
    text = "\n".join(out)
    print(text)
    path = os.path.join(root, "bench_profile.txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("\nRésultat enregistré dans : %s" % path)
    except OSError as e:
        print("\n(Impossible d'écrire bench_profile.txt : %s)" % e)


def main():
    import machine_check
    mach_before = machine_check.measure()
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

    # Presentation is measured apart from the drawing, and split in two:
    #   flip = pygame.display.flip() alone, copy = the rest of Game._flip_frame
    present_ms = [0.0]   # whole Game._flip_frame
    flip_ms = [0.0]      # pygame.display.flip only
    real_present = game_module.Game._flip_frame
    real_display_flip = pygame.display.flip

    def timed_present(self, *a, **k):
        t = time.perf_counter()
        try:
            return real_present(self, *a, **k)
        finally:
            present_ms[0] += (time.perf_counter() - t) * 1000

    def timed_display_flip():
        t = time.perf_counter()
        try:
            return real_display_flip()
        finally:
            flip_ms[0] += (time.perf_counter() - t) * 1000

    game_module.Game._flip_frame = timed_present
    pygame.display.flip = timed_display_flip

    g = replay._new_game(12345)
    keys = {"cur": replay._Keys()}
    pygame.key.get_pressed = lambda: keys["cur"]

    n = 300 if args.quick else 1200
    menu_n = 120 if args.quick else 600
    results = []
    state = {"frame": 0}

    def run_frame(rec, playing, i, count, prof=None):
        """One frame of the game, timed and added to `rec`."""
        if playing:
            for ship in g._ships():
                ship.infinite_lives = True
            if i == count // 2:
                for ship in g._ships():
                    ship.phenix_gauge = 10.0
                replay._press(pygame.K_RSHIFT)
            if i == count // 2 + 3:
                replay._release(pygame.K_RSHIFT)
            keys["cur"] = replay._Keys(replay._pressed(g, state["frame"]))
        else:
            keys["cur"] = replay._Keys(replay._menu_pressed(g, state["frame"]))
        g.dt = STEP
        present_ms[0] = 0.0
        flip_ms[0] = 0.0
        t0 = time.perf_counter()
        g.handle_events()
        g.update()
        t1 = time.perf_counter()
        if prof is not None:
            prof.enable()
        g.draw()
        if prof is not None:
            prof.disable()
        t2 = time.perf_counter()
        logic = (t1 - t0) * 1000
        draw_all = (t2 - t1) * 1000
        rec["logic"].append(logic)
        rec["draw"].append(draw_all - present_ms[0])
        rec["copy"].append(present_ms[0] - flip_ms[0])
        rec["flip"].append(flip_ms[0])
        rec["total"].append(logic + draw_all)
        state["frame"] += 1

    def new_rec():
        return {"logic": [], "draw": [], "copy": [], "flip": [], "total": []}

    print("Test en cours (une minute environ), ne touche à rien...")
    gc.collect()

    if args.profile:
        run_profile(args, g, run_frame, new_rec, settings, replay, ROOT)
        g.running = False
        pygame.quit()
        shutil.rmtree(user_dir, ignore_errors=True)
        return

    # --- menu ---
    rec = new_rec()
    for i in range(menu_n):
        run_frame(rec, False, i, menu_n)
    results.append(("Menu titre", rec))

    # --- levels 1 to 6: the game's own level changes are never interrupted ---
    replay._solo("phoenix")(g)
    for stage in range(1, 7):
        if stage > 1 and g.stage < stage:
            g.stage = stage
            g._setup_stage(stage)
            g.stage_transition = None
            for ship in g._ships():            # back to the normal play height
                ship.y = settings.BASE_HEIGHT - 95
        rec = new_rec()
        label = "Niveau %d%s" % (g.stage, " (boss)" if settings.stage_content(g.stage) == 5 else "")
        for i in range(n):
            run_frame(rec, True, i, n)
        # let a level change in progress finish (ship flying up, next level arriving)
        extra = 0
        while g.stage_transition is not None and extra < 2000 and g.running:
            run_frame(rec, True, n, n)
            extra += 1
        results.append((label, rec))
        if not g.running:
            print("Le jeu s'est fermé pendant le test.")
            break

    mach_after = machine_check.measure()
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
        "Alimentation: %s" % (machine_check.power_plan() or "?"),
        machine_check.describe("PC avant   ", mach_before),
        machine_check.describe("PC après   ", mach_after),
        "",
    ]
    warn = machine_check.drift_warning(mach_before, mach_after)
    if warn:
        info.insert(-1, warn)
    lines = list(info)
    head = "%-17s %6s | %5s %5s | %5s %5s %5s | %5s | %5s %5s | %6s %6s %6s %6s %5s | %6s" % (
        "Partie", "images", "logiq", "p99", "dessin", "p99", "max", "copie", "flip", "p99",
        "total", "p95", "p99", "max", "i/s", ">6,9ms")
    lines += [head, "-" * len(head)]
    all_total = []
    for label, rec in results:
        t = rec["total"]
        if not t:
            continue
        all_total += t
        over = 100.0 * sum(1 for x in t if x > BUDGETS[0][1]) / len(t)
        lines.append("%-17s %6d | %5.2f %5.2f | %5.2f %5.2f %5.2f | %5.2f | %5.2f %5.2f | %6.2f %6.2f %6.2f %6.2f %5.0f | %5.1f%%" % (
            label, len(t),
            statistics.mean(rec["logic"]), pct(rec["logic"], .99),
            statistics.mean(rec["draw"]), pct(rec["draw"], .99), max(rec["draw"]),
            statistics.mean(rec["copy"]),
            statistics.mean(rec["flip"]), pct(rec["flip"], .99),
            statistics.mean(t), pct(t, .95), pct(t, .99), max(t),
            1000.0 / statistics.mean(t), over))
    lines.append("")
    lines.append("Durées en millisecondes. copie = bordures + copie du canevas avant le flip ; flip = pygame.display.flip().")
    lines.append("i/s = images par seconde que le PC peut tenir (1000 / total moyen).")
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
