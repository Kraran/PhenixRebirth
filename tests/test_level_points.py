"""Every enemy is worth +10 per 5-level round: a blue bird is 20 at level 1, 30 at level 6, 40 at level 11.
That goes for the birds, the boss and the decorations of its saucer; its armor bricks stay at 1 point."""
from types import SimpleNamespace

import pygame
import pytest

import invaders as inv
from settings import level_points_bonus
from test_smoke import run  # noqa: F401  (fixture)
from test_story_swarm import _launch


class Foe:
    def __init__(self, stage):
        self.stage = stage


# --- the rule itself ---
@pytest.mark.parametrize("level,bonus", [(1, 10), (2, 10), (5, 10), (6, 20), (10, 20), (11, 30), (15, 30),
                                         (16, 40), (51, 110)])
def test_the_bonus_grows_by_ten_every_five_levels(level, bonus):
    assert level_points_bonus(level) == bonus


def test_a_nonsense_level_counts_as_level_one():
    assert level_points_bonus(0) == level_points_bonus(-3) == level_points_bonus(1)


# --- birds ---
def test_a_blue_bird_is_worth_20_then_30_then_40(run):
    g = run.game
    g.adventure = None
    g.difficulty = "normal"
    got = []
    for stage in (1, 6, 11):
        g.stage = stage
        got.append(g._enemy_kill_points(Foe(1)))
    assert got == [20, 30, 40]


def test_every_kind_of_enemy_gets_the_bonus_of_its_level(run):
    g = run.game
    g.adventure = None
    g.difficulty = "normal"
    for stage, bonus in ((1, 10), (5, 10), (6, 20), (12, 30)):
        g.stage = stage
        for kind, base in ((1, 10), (2, 20), (3, 30), (4, 40)):
            assert g._enemy_kill_points(Foe(kind)) == base + bonus, (stage, kind)


def test_the_whole_round_pays_the_same_then_the_next_round_pays_more(run):
    g = run.game
    g.adventure = None
    g.difficulty = "normal"
    prices = []
    for stage in range(1, 12):
        g.stage = stage
        prices.append(g._enemy_kill_points(Foe(2)))
    assert prices == [30] * 5 + [40] * 5 + [50]


def test_the_veteran_bonus_comes_on_top(run):
    g = run.game
    g.adventure = None
    g.difficulty = "veteran"
    g.stage = 6
    assert g._enemy_kill_points(Foe(1)) == 10 + 20 + 10


# --- boss and saucer ---
def test_the_boss_is_worth_its_price_plus_the_level_bonus(run):
    g = run.game
    g.difficulty = "normal"
    got = []
    for stage in (5, 10, 15):
        g.stage = stage
        got.append(g._boss_points())
    assert got == [510, 520, 530]
    g.difficulty = "veteran"
    g.stage = 5
    assert g._boss_points() == 1010


def test_a_saucer_decoration_is_worth_50_plus_the_level_bonus(run):
    g = run.game
    got = []
    for stage in (1, 6, 11):
        g.stage = stage
        got.append(g._deco_points())
    assert got == [60, 70, 80]


def _shoot_boss(g, kind, stage):
    """One player shot hitting a part of the boss saucer; returns the points it gave."""
    g.stage = stage
    g.score = 0
    ship = g.player
    ship.score = 0
    ship.get_bullet_rects = lambda: [(0, pygame.Rect(600, 300, 6, 14))]
    ship.destroy_bullet = lambda *a, **k: None
    target = SimpleNamespace(x=600, y=300, is_purple=False, kill=lambda: None)
    g.boss_saucer = SimpleNamespace(alive=True, hit_bullet=lambda rect: (kind, target), flag_ports_pair=False)
    import update_play
    update_play.player_bullets_vs_enemies(g)
    g.boss_saucer = None
    return g.score


def test_shooting_the_saucer_gives_the_new_points_in_the_game(run):
    g = run.game
    g.difficulty = "normal"
    assert _shoot_boss(g, "deco", 1) == 60
    assert _shoot_boss(g, "deco", 6) == 70
    assert _shoot_boss(g, "boss", 5) == 510
    assert _shoot_boss(g, "boss", 10) == 520


def test_the_armor_bricks_always_stay_at_one_point(run):
    g = run.game
    g.difficulty = "normal"
    for stage in (5, 10, 15, 50):
        assert _shoot_boss(g, "cell", stage) == 1


# --- the Adventure and the Space Invaders missions ---
def test_the_adventure_waves_pay_by_their_arcade_stage(run):
    g = _launch(run.game, "dome_5")                    # the swarm plays at stage 11: +30
    assert g.stage == 11
    assert g._enemy_kill_points(Foe(1)) == 10 + 30


def test_the_first_adventure_mission_pays_the_level_one_bonus(run):
    g = _launch(run.game, "dome_1")
    assert g.stage == 1
    assert g._enemy_kill_points(Foe(1)) == 20


def test_invader_missions_count_their_own_levels(run):
    g = run.game
    g.adventure = None
    g.difficulty = "normal"
    g.stage = 1
    g.formation = inv.InvaderFormation(level=1)
    assert g._enemy_kill_points(Foe(1)) == 20
    g.formation = inv.InvaderFormation(level=7)
    assert g._enemy_kill_points(Foe(1)) == 30


def test_the_miniature_saucer_keeps_its_own_500_to_1000(run):
    assert inv.saucer_points(300, 300) == 1000
    assert inv.saucer_points(300 + inv.SAUCER_HIT_W, 300) == 500
