"""Edge (wall) rules of the Shield in the adventure hangar.

instant : touching the edge kills at once (start of Act 1)
slow    : the arcade rule - slowdown, then death if you stay too long (Act 1 upgrade)
immune  : harmless sparks (later acts)
The arcade Shield (no adventure wall at all) must stay immune, as before.
"""
import pygame
import pytest

from settings import BASE_WIDTH, BASE_HEIGHT
from player import Player
from test_smoke import run  # noqa: F401  (fixture)

DT = 1 / 60


class _Keys:
    def __init__(self, *down):
        self.down = set(down)

    def __getitem__(self, k):
        return k in self.down


def _ship(run, wall, lives=1):
    p = Player(BASE_WIDTH // 2, BASE_HEIGHT - 95, ship_id="shield", tint="red")
    p.sounds = run.game.sounds
    p.pid = 1
    p.lives = lives
    p.infinite_lives = False
    p.invulnerable = 0.0
    if wall is not None:
        p.adventure_wall = wall
    return p


def _push_left(p, frames):
    """Hold LEFT against the wall; returns the frame index of the first death or None."""
    keys = _Keys(pygame.K_LEFT)
    for i in range(frames):
        p.update(DT, keys)
        if p.dying or p.lives <= 0 or p.just_lost_life:
            return i
    return None


def test_instant_wall_kills_on_the_first_touch(run):
    p = _ship(run, "instant", lives=1)
    p.x = 36 + 1
    hit_frame = _push_left(p, 120)
    assert hit_frame is not None and hit_frame <= 1
    assert p.dying and p.lives == 0


def test_instant_wall_costs_a_life_when_there_are_two(run):
    p = _ship(run, "instant", lives=2)
    p.x = 37
    assert _push_left(p, 120) is not None
    assert p.lives == 1 and not p.dying


def test_instant_wall_does_not_kill_without_touching(run):
    p = _ship(run, "instant")
    p.x = BASE_WIDTH // 2
    keys = _Keys(pygame.K_LEFT)
    for _ in range(10):          # 10 frames of left movement stay far from the edge
        p.update(DT, keys)
    assert p.lives == 1 and not p.dying


def test_slow_wall_slows_down_then_kills_after_half_a_second(run):
    p = _ship(run, "slow", lives=1)
    p.x = 37
    first = None
    slowed = False
    keys = _Keys(pygame.K_LEFT)
    for i in range(120):
        p.update(DT, keys)
        slowed = slowed or p.slowdown_timer > 0
        if p.dying:
            first = i
            break
    assert slowed, "the slowdown must start on contact"
    assert first is not None
    # EDGE_KILL_TIME = 0.5 s -> about 30 frames, clearly not instant
    assert 25 <= first <= 35, first


def test_slow_wall_lets_the_pilot_escape(run):
    p = _ship(run, "slow", lives=1)
    p.x = 37
    keys_left = _Keys(pygame.K_LEFT)
    for _ in range(15):          # 0.25 s against the wall
        p.update(DT, keys_left)
    assert not p.dying
    for _ in range(60):          # then away from it
        p.update(DT, _Keys(pygame.K_RIGHT))
    assert not p.dying and p.lives == 1


def test_immune_wall_never_kills(run):
    p = _ship(run, "immune", lives=1)
    p.x = 37
    assert _push_left(p, 300) is None
    assert not p.dying and p.lives == 1


def test_arcade_shield_is_still_immune(run):
    p = _ship(run, None, lives=3)          # no adventure wall = arcade game
    p.x = 37
    assert _push_left(p, 300) is None
    assert not p.dying and p.lives == 3


# ---------------------------------------------------------------- in the game
def _start_act1(g):
    import story_state as ss
    g.story.state = ss.default_state()
    g.story.map_index = 0
    spec = g.story._launch_selected()
    assert spec
    g._begin_adventure(spec)
    return g.player


def test_act1_mission_starts_with_the_weak_shield(run):
    from settings import PLAYER_SPEED
    p = _start_act1(run.game)
    assert p.ship_id == "shield"
    assert p.lives == 1
    assert p.speed == pytest.approx(PLAYER_SPEED * 0.40)
    assert p.adventure_dome is False and p.adventure_wall == "instant"


def test_act1_mission_after_the_workshop(run):
    import story_state as ss
    from settings import PLAYER_SPEED
    g = run.game
    st = ss.default_state()
    st["credits"] = 99999
    st["flags"].update(ch1_speed=True, ch1_life_2=True, ch1_wall=True, dome_online=True)
    for sid, *_ in ss.SHOP:
        assert ss.buy(st, sid)
    g.story.state = st
    g.story.map_index = 0
    g._begin_adventure(g.story._launch_selected())
    p = g.player
    assert (p.lives, p.adventure_wall, p.adventure_dome) == (2, "slow", True)   # the workshop now sells the dome
    assert p.speed == pytest.approx(PLAYER_SPEED * 0.80)


def test_touching_the_edge_in_a_real_mission_ends_the_run(run):
    g = run.game
    p = _start_act1(g)
    run.frames(5)
    p.x = 37
    keys = _Keys(pygame.K_LEFT)
    for _ in range(3):
        p.update(DT, keys)
    assert p.dying or p.lives == 0
