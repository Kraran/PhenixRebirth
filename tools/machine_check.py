"""
Quick measure of the state of the PC (memory copy, calculation, power plan),
to spot a test spoiled by a busy or throttled PC.
Used by bench.py and probe_present.py; can also be run alone.
"""
import subprocess
import sys
import time


def measure():
    """(5 MB memory copy in ms, calculation loop in ms): the best of several tries."""
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
    return "%s: 5 MB memory copy %.2f ms   calculation loop %.1f ms" % (label, m[0], m[1])


def drift_warning(before, after):
    """A warning text if the PC changed state during the test, else ''."""
    worst = max(after[0] / max(before[0], 1e-6), after[1] / max(before[1], 1e-6),
                before[0] / max(after[0], 1e-6), before[1] / max(after[1], 1e-6))
    if worst > 1.4:
        return ("WARNING: the PC did not run at the same speed before and after the test "
                "(gap x%.1f): unreliable results. Close the other programs and try again." % worst)
    return ""


if __name__ == "__main__":
    print(describe("Machine", measure()))
    print("Power plan:", power_plan() or "(unknown)")
