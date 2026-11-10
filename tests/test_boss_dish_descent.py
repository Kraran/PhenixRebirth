"""Destroying both dishes of the boss saucer halves its descent speed; it no longer stops."""
import pytest

from boss import BossSaucer
from settings import BASE_HEIGHT
from test_smoke import run  # noqa: F401  (fixture: pygame and the assets)


def _dishes(saucer):
    return [d for d in saucer.decorations if d.kind == "dish"]


def _kill(saucer, kind, n=None):
    items = [d for d in saucer.decorations if d.kind == kind]
    for d in items[: len(items) if n is None else n]:
        d.alive = False
    saucer._apply_pair_effects()


def _saucer(run):
    """A freshly built boss saucer (the run fixture has already opened pygame)."""
    assert run.game is not None
    return BossSaucer()


def test_the_saucer_has_two_dishes_and_starts_its_slow_descent(run):
    s = _saucer(run)
    dishes = _dishes(s)
    assert len(dishes) == 2 and all(d.alive for d in dishes)
    assert s.descend_speed == pytest.approx(2.8)
    assert s.offset_y == 0.0


def test_one_destroyed_dish_leaves_the_descent_speed_unchanged(run):
    s = _saucer(run)
    before = s.descend_speed
    _kill(s, "dish", 1)
    assert s.descend_speed == pytest.approx(before)
    assert "dish" not in s._pair_done
    s.update(1.0)
    assert s.offset_y == pytest.approx(before)


def test_both_destroyed_dishes_halve_the_descent_speed(run):
    s = _saucer(run)
    before = s.descend_speed
    _kill(s, "dish")
    assert s.descend_speed == pytest.approx(before * 0.5)
    assert "dish" in s._pair_done


def test_the_halving_is_applied_only_once(run):
    s = _saucer(run)
    _kill(s, "dish")
    halved = s.descend_speed
    s._apply_pair_effects()
    s._apply_pair_effects()
    assert s.descend_speed == pytest.approx(halved)


def test_a_scaled_descent_is_halved_too(run):
    """Levels 10, 15... and the difficulty already multiply descend_speed at spawn."""
    s = _saucer(run)
    s.descend_speed *= 1.2
    _kill(s, "dish")
    assert s.descend_speed == pytest.approx(2.8 * 1.2 * 0.5)


def test_descent_is_a_clean_game_time_step_and_does_not_jitter(run):
    """offset_y += descend_speed * dt: pause (dt=0) stands still, slow-mo and
    uneven frames cover the same distance as one big step."""
    s = _saucer(run)
    _kill(s, "dish")
    speed = s.descend_speed
    y0 = s.offset_y
    s.update(0.0)
    assert s.offset_y == pytest.approx(y0)

    s.update(1.0)
    assert s.offset_y == pytest.approx(y0 + speed)

    other = _saucer(run)
    _kill(other, "dish")
    for _ in range(120):
        other.update(1.0 / 120)
    assert other.offset_y == pytest.approx(speed, abs=1e-9)

    slow = _saucer(run)
    _kill(slow, "dish")
    for _ in range(200):
        slow.update(0.005)
    assert slow.offset_y == pytest.approx(speed, abs=1e-9)


def test_the_saucer_still_reaches_the_floor_after_both_dishes_are_down(run):
    s = _saucer(run)
    _kill(s, "dish")
    assert s.descend_speed > 0
    s._sync_positions()
    living = [c for c in s.cells if c.alive]
    assert living
    lowest = max(c.y + c.h / 2.0 for c in living)
    s.offset_y += (BASE_HEIGHT - 1.0) - lowest - 0.25
    s._sync_positions()
    assert not s.touches_floor(BASE_HEIGHT)
    s.update(1.0)
    assert s.touches_floor(BASE_HEIGHT)


def test_the_other_pair_effects_are_unchanged(run):
    s = _saucer(run)
    _kill(s, "dish")
    assert s.can_shoot is True
    assert s.bird_rate == pytest.approx(1.0)
    assert not getattr(s, "flag_ports_pair", False)
    assert all(c.alive for c in s.purple_cells)

    _kill(s, "cannon")
    assert s.can_shoot is False
    _kill(s, "port")
    assert s.bird_rate == pytest.approx(0.28)
    assert s.flag_ports_pair is True
    mid_before = sum(1 for c in s.purple_cells if c.alive)
    _kill(s, "gen")
    assert sum(1 for c in s.purple_cells if c.alive) < mid_before
