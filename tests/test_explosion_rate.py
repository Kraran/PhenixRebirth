"""Explosions : identiques à 60 Hz, même étalement à 120 / 144 Hz."""
import copy
import random

import pytest

from explosion import Explosion

KINDS = ["enemy", "bullet", "collision", "edge", "flame", "dust", "shield", "electric", "gameover"]


def _old_update(e, dt):
    """Copie de l'ancien Explosion.update (décélérations « par image »)."""
    if int(getattr(e, "delay_frames", 0) or 0) > 0:
        e.delay_frames -= 1
        return
    e.life -= dt
    for p in e.particles:
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["vy"] += 140 * dt
        p["vx"] *= p["drag"]
        p["vy"] *= p["drag"]
    for d in e.debris:
        d["x"] += d["vx"] * dt
        d["y"] += d["vy"] * dt
        d["vy"] += 300 * dt
        d["vx"] *= 0.975
        d["rot"] += d["rot_spd"] * dt
    for s in e.sparks:
        s["x"] += s["vx"] * dt
        s["y"] += s["vy"] * dt
        s["vx"] *= 0.94
        s["vy"] *= 0.94
        s["life"] -= dt
    for f in e.flashes:
        f["life"] -= dt * 2.8
    for r in e.rings:
        r["r"] += (r["max_r"] - r["r"]) * min(1.0, 3.2 * dt)
    for tng in getattr(e, "tongues", ()):
        tng["x"] += tng["vx"] * dt
        tng["y"] += tng["vy"] * dt
        tng["vy"] -= 30 * dt
        if tng["kind"] == "fire":
            tng["h"] += 18 * dt
            tng["w"] = max(4, tng["w"] - 6 * dt)
        else:
            tng["w"] += 22 * dt
            tng["h"] += 14 * dt


def _state(e):
    return (e.life, e.delay_frames, e.particles, e.debris, e.sparks, e.flashes, e.rings, e.tongues)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("delay", [0, 1])
def test_60hz_identique_a_avant(kind, delay):
    random.seed(7)
    new = Explosion(100, 200, kind=kind, delay_frames=delay)
    old = copy.deepcopy(new)
    dt = 1 / 60
    for i in range(140):
        new.update(dt)
        _old_update(old, dt)
        assert _state(new) == _state(old), "image %d" % i
        assert (new.delay_frames > 0.05) == (int(old.delay_frames) > 0)


def _simulate(kind, fps, seconds=1.0):
    random.seed(11)
    e = Explosion(0, 0, kind=kind)
    for _ in range(int(round(seconds * fps))):
        e.update(1.0 / fps)
    return e


@pytest.mark.parametrize("kind", ["enemy", "bullet", "collision", "gameover", "dust", "shield"])
def test_meme_etalement_a_toutes_les_cadences(kind):
    ref = _simulate(kind, 60)
    for fps in (120, 144, 75):
        e = _simulate(kind, fps)
        # la vitesse horizontale ne subit que la décélération : elle doit être la même
        for a, b in zip(ref.particles, e.particles):
            assert b["vx"] == pytest.approx(a["vx"], rel=1e-9, abs=1e-9)
        for a, b in zip(ref.debris, e.debris):
            assert b["vx"] == pytest.approx(a["vx"], rel=1e-9, abs=1e-9)
        for a, b in zip(ref.sparks, e.sparks):
            assert b["vx"] == pytest.approx(a["vx"], rel=1e-9, abs=1e-9)
            assert b["vy"] == pytest.approx(a["vy"], rel=1e-9, abs=1e-9)
        for a, b in zip(ref.rings, e.rings):
            assert b["r"] == pytest.approx(a["r"], rel=1e-9)
        assert e.life == pytest.approx(ref.life, abs=1e-9)
        # et la position, qui dépend aussi de l'intégration image par image : à quelques % près
        for a, b in zip(ref.particles, e.particles):
            assert b["x"] == pytest.approx(a["x"], rel=0.06, abs=1.5)


def test_delai_en_temps_reel():
    random.seed(1)
    for fps in (60, 120, 144):
        e = Explosion(0, 0, kind="enemy", delay_frames=1)
        updates = 0
        while e.life == e.max_life and updates < 20:
            e.update(1.0 / fps)
            updates += 1
        # l'explosion démarre à l'image qui suit le délai : ~1/60 s plus tard, pas 1 image
        started_after = (updates - 1) / fps
        assert 1 / 60 - 1e-6 <= started_after <= 1 / 60 + 1 / fps, (fps, started_after)


def test_ancien_comportement_dependait_de_la_cadence():
    # ce que ce changement corrige : l'ancienne version, simulée 0,5 s
    def run(fps):
        random.seed(11)
        e = Explosion(0, 0, kind="gameover")
        for _ in range(int(0.5 * fps)):
            _old_update(e, 1.0 / fps)
        return e.sparks[0]["vx"]

    assert run(144) < 0.2 * run(60)       # à 144 Hz les étincelles freinaient bien plus vite
