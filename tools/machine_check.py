"""
Mesure rapide de l'état du PC (copie mémoire, calcul, plan d'alimentation),
pour repérer un test faussé par un PC occupé ou bridé.
Utilisé par bench.py et probe_present.py ; peut aussi se lancer seul.
"""
import subprocess
import sys
import time


def measure():
    """(copie mémoire de 5 Mo en ms, boucle de calcul en ms) : meilleur de plusieurs essais."""
    size = 5_000_000
    src = memoryview(bytearray(size))
    dst = memoryview(bytearray(size))
    best_copy = 1e9
    for _ in range(40):
        t0 = time.perf_counter()
        dst[:] = src
        best_copy = min(best_copy, (time.perf_counter() - t0) * 1000)
    best_cpu = 1e9
    for _ in range(8):
        t0 = time.perf_counter()
        sum(i * i for i in range(150_000))
        best_cpu = min(best_cpu, (time.perf_counter() - t0) * 1000)
    return best_copy, best_cpu


def power_plan():
    if not sys.platform.startswith("win"):
        return ""
    try:
        out = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=5).stdout
        return out.strip().split(":", 1)[-1].strip()
    except Exception:
        return ""


def describe(label, m):
    return "%s : copie mémoire 5 Mo %.2f ms   boucle de calcul %.1f ms" % (label, m[0], m[1])


def drift_warning(before, after):
    """Texte d'avertissement si le PC a changé d'état pendant le test, sinon ''."""
    worst = max(after[0] / max(before[0], 1e-6), after[1] / max(before[1], 1e-6),
                before[0] / max(after[0], 1e-6), before[1] / max(after[1], 1e-6))
    if worst > 1.4:
        return ("ATTENTION : le PC n'a pas eu la même vitesse avant et après le test "
                "(écart x%.1f) : résultats peu fiables. Ferme les autres programmes et recommence." % worst)
    return ""


if __name__ == "__main__":
    print(describe("Machine", measure()))
    print("Plan d'alimentation :", power_plan() or "(inconnu)")
