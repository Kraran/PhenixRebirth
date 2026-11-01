"""The decisions of the birds (dive, shoot) are chances per SECOND, not per image: the AI is as aggressive at 30, 60, 120 or
144 images/s (enemy.happens, settings ENEMY_DIVE_RATE / ENEMY_SHOOT_RATE)."""
import math
import random

import pygame
import pytest

import enemy as en
import settings as st
from enemy import EnemyFormation, happens


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


def test_the_rates_are_the_old_chances_per_image_at_60_images_per_second():
    assert st.AI_TUNED_FPS == 60.0
    assert st.ENEMY_SHOOT_RATE == pytest.approx(st.ENEMY_SHOOT_CHANCE * 60)
    assert st.ENEMY_DIVE_RATE == pytest.approx(st.ENEMY_DIVE_CHANCE * 60)
    assert st.ENEMY_SHOOT_RATE == pytest.approx(0.21) and st.ENEMY_DIVE_RATE == pytest.approx(0.108)


def test_happens_never_fires_without_a_rate_or_time(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    assert not happens(0.0, 1.0) and not happens(-3.0, 1.0)
    assert not happens(5.0, 0.0) and not happens(5.0, -0.1)
    assert happens(5.0, 0.01)                         # (a roll of 0 fires as soon as there is a chance)


def test_the_chance_of_a_frame_is_one_minus_exp_of_rate_times_dt(monkeypatch):
    for rate, dt in ((0.21, 1 / 60), (0.9, 1 / 120), (4.0, 0.05), (30.0, 0.05)):
        p = 1.0 - math.exp(-rate * dt)
        monkeypatch.setattr(random, "random", lambda p=p: p - 1e-9)
        assert happens(rate, dt)
        monkeypatch.setattr(random, "random", lambda p=p: p + 1e-9)
        assert not happens(rate, dt)


def test_a_huge_rate_or_frame_is_almost_sure_but_never_above_one(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.999999)
    assert happens(1000.0, 0.05)
    monkeypatch.setattr(random, "random", lambda: 0.9999999999999999)    # (the biggest value random() gives)
    assert happens(1e9, 0.05)


@pytest.mark.parametrize("hz", [30, 60, 120, 144, 240])
def test_the_count_per_second_does_not_depend_on_the_frame_rate(hz):
    rng = random.Random(5)
    real = random.random
    random.random = rng.random
    try:
        dt = 1.0 / hz
        seconds = 4000
        n = sum(1 for _ in range(int(seconds * hz)) if happens(0.9, dt))
    finally:
        random.random = real
    assert n / seconds == pytest.approx(0.9, rel=0.06)


def _count(hz, seconds, monkeypatch, seed=11):
    """Dives started and shots fired by a normal screen of birds left alone for `seconds` seconds at `hz` images/s."""
    random.seed(seed)
    form = EnemyFormation()
    dives, shots = [0], [0]
    monkeypatch.setattr(en.Enemy, "start_dive", lambda self, px: dives.__setitem__(0, dives[0] + 1))
    real = en.EnemyBullet.__init__

    def counted(self, *a, **k):
        shots[0] += 1
        real(self, *a, **k)
    monkeypatch.setattr(en.EnemyBullet, "__init__", counted)
    dt = 1.0 / hz
    for _ in range(int(20 * hz)):                       # (the birds fly in first and cannot shoot yet)
        form.update(dt, 640.0)
    dives[0] = shots[0] = 0
    for _ in range(int(seconds * hz)):
        form.update(dt, 640.0)
        form.bullets.clear()                            # (the shots do not block the next ones: only the clock counts)
    return dives[0] / seconds, shots[0] / seconds


def test_the_birds_dive_and_shoot_as_often_at_120_and_144_as_at_60(monkeypatch):
    base = _count(60, 600, monkeypatch)
    assert base[0] > 0.5 and base[1] > 0.5                    # (a sane count to compare with)
    for hz in (30, 120, 144):
        d, s = _count(hz, 600, monkeypatch)
        assert d == pytest.approx(base[0], rel=0.15), (hz, d, base)
        assert s == pytest.approx(base[1], rel=0.15), (hz, s, base)


def _rates(form, state, stage, big=False, dt=1 / 120):
    """The rates `happens` is asked about for a lone bird in `state` of a formation at `stage`: (dive rates, shoot rates)."""
    form.stage = stage
    bird = en.BigBird(300, 200, stage=stage) if big else form.enemies[0]
    form.enemies = [bird]
    bird.update = lambda *a, **k: None
    bird.state = state
    bird.shoot_cooldown = 0.0
    bird.dying = False
    asked = []
    real = en.happens
    en.happens = lambda rate, d: asked.append((rate, d)) and False
    try:
        form.update(dt, 640.0)
    finally:
        en.happens = real
    return asked


def test_the_chances_are_asked_for_the_frame_that_is_running_and_scaled_by_the_kind_of_bird():
    dive, shoot = st.ENEMY_DIVE_RATE, st.ENEMY_SHOOT_RATE
    f = EnemyFormation()
    assert _rates(f, "formation", 1) == [(dive, 1 / 120), (shoot, 1 / 120)]           # a plain bird of the first screen
    assert _rates(f, "formation", 2)[1][0] == pytest.approx(shoot * 1.5)
    assert _rates(f, "formation", 3)[1][0] == pytest.approx(shoot * 1.5)
    assert _rates(f, "diving", 1) == [(shoot * 1.8, 1 / 120)]                          # a diving bird shoots more, does not dive again
    assert _rates(f, "diving", 2)[0][0] == pytest.approx(shoot * 1.5 * 1.8)
    assert _rates(f, "formation", 3, big=True, dt=1 / 144) == [(pytest.approx(shoot * 4.0), 1 / 144)]      # (a BigBird only dives from its roam)
    assert _rates(f, "formation", 4, big=True)[0][0] == pytest.approx(shoot * 4.5)
    assert _rates(f, "roam", 3, big=True) == [(dive * 0.55, 1 / 120), (shoot * 4.0, 1 / 120)]
    assert _rates(f, "returning", 1) == []                                              # nothing to decide
