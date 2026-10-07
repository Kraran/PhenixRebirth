"""Limiteur d'images : intervalle exact, rien à attendre si l'image est déjà en retard."""
from pacing import FramePacer


class FakeTime:
    """Horloge simulée : chaque lecture coûte 10 µs, sleep() dort un peu plus que demandé."""

    def __init__(self, oversleep=0.0003):
        self.t = 100.0
        self.slept = []
        self.oversleep = oversleep

    def clock(self):
        self.t += 10e-6
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s + self.oversleep

    def work(self, s):
        self.t += s


def _run(cap, work, frames, oversleep=0.0003):
    ft = FakeTime(oversleep)
    p = FramePacer(clock=ft.clock, sleep=ft.sleep)
    assert p.wait(cap) is None            # 1er appel : rien à mesurer
    start = ft.t
    dts = []
    for _ in range(frames):
        ft.work(work)
        dts.append(p.wait(cap))
    return ft, dts, ft.t - start


def test_144_images_par_seconde_exactement():
    for cap in (60, 75, 120, 144):
        _ft, dts, elapsed = _run(cap, 0.002, cap)
        assert abs(elapsed - 1.0) < 0.02, (cap, elapsed)   # cap images en ~1 s
        assert all(abs(d - 1.0 / cap) < 0.0005 for d in dts), cap


def test_pygame_clock_tronque_a_la_milliseconde():
    # ce que le limiteur remplace : 1000 // 144 = 6 ms -> ~166 images/s au lieu de 144
    assert 1000 // 144 == 6 and 1000 // 120 == 8 and 1000 // 60 == 16


def test_image_en_retard_pas_d_attente_ni_rattrapage():
    ft = FakeTime()
    p = FramePacer(clock=ft.clock, sleep=ft.sleep)
    p.wait(144)
    ft.work(0.030)                       # image lente (30 ms)
    d = p.wait(144)
    assert 0.029 < d < 0.031 and ft.slept == []
    ft.work(0.001)
    d2 = p.wait(144)                     # la suivante repart normalement, sans rafale de rattrapage
    assert abs(d2 - 1 / 144) < 0.0005


def test_changement_de_cadence_et_reset():
    ft = FakeTime()
    p = FramePacer(clock=ft.clock, sleep=ft.sleep)
    p.wait(60)
    ft.work(0.001)
    assert abs(p.wait(60) - 1 / 60) < 0.0005
    ft.work(0.001)
    assert abs(p.wait(144) - 1 / 144) < 0.0005
    p.reset()
    assert p.wait(144) is None
