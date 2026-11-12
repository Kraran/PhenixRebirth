"""TEST - Sacha: the swarm in four waves and Sacha, the wingman flown by the computer (src/wingman.py)."""
import numpy as np
import pygame
import pytest

import guardian
import story_state as ss
import wingman
from enemy import EnemyBullet, EnemyFormation
from settings import BASE_HEIGHT, BASE_WIDTH
from test_smoke import run  # noqa: F401  (fixture)

ID = "test_sacha"
NEEDS_TEST_MISSIONS = True        # (conftest: the TEST missions are kept for this module)


def _launch(run, phenix=False, act=1, mode="normal"):
    g = run.game
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    if act >= 2:
        ss.jump_to_act2(st)
    if phenix:
        st["flags"]["phenix_owned"] = True
        st["slots"][1]["owned"] = True
        st["selected_slot"] = 1
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.pane = "map"
    g.story.map_index = [m["id"] for m in g.story.missions()].index(ID)
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    return spec


def _arrived(run, limit=600):
    for _ in range(limit):
        if run.game.stage_transition is None:
            return
        run.frames(1)
    raise AssertionError("the ships never arrived")


def _with_sacha(run, limit=600):
    """The ships have arrived and Sacha has come in (ENTER_DELAY s into the first wave)."""
    _arrived(run)
    g = run.game
    for _ in range(limit):
        if g.wingman.state == "fight":
            return
        g.player.invulnerable = max(g.player.invulnerable, 1.0)
        run.frames(1)
    raise AssertionError("Sacha never came in")


def _no_stray_harm(monkeypatch):
    """The enemies of the swarm leave him alone (a test that counts his hits gives them itself)."""
    real = wingman.attacks
    monkeypatch.setattr(wingman, "attacks", lambda game: None)
    return real


def _kinds(form):
    return sorted({e.stage for e in form.enemies if e.alive and not e.dying})


# ------------------------------------------------------------------ the mission
def test_a_training_mission_on_the_map_of_every_act_from_the_start():
    m = ss.mission_by_id(ID)
    assert m["training"] and m["test"] and m["wingman"] == "sacha"
    assert m["acts"] == (1, 2, 3) and m["need"] is None
    assert ss.mission_group(m) == ss.GROUP_EXTRA
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    assert ID in [x["id"] for x in ss.visible_missions(st)]
    assert (ss.next_mission(st, ss.visible_missions(st)) or {}).get("id") != ID      # never suggested


def test_nothing_won_nothing_lost():
    st = ss.create_slot(1, "NOVA", "veteran")
    credits = st.get("credits")
    res = ss.record_result(st, ID, 12345, False, {"bird1": 3})
    assert res["training"] and not res["fallen"] and not res["lost"]
    assert not st.get("fallen") and st.get("credits") == credits
    res = ss.record_result(st, ID, 12345, True)
    assert res["training"] and res["score"] == 0 and ID not in (st.get("cleared") or [])


def test_the_launch(run):
    spec = _launch(run)
    assert spec["training"] and spec["items"] == [] and spec["wingman"] == "sacha"
    assert spec["swarm"] and spec["stage"] == 11 and spec["waves"] == [11, 11, 11, 11]
    assert spec["swarm_kinds"] == [[1], [1, 2], [1, 2, 3], [1, 2, 3, 4]]
    assert spec["guardians_wave"] == {4: 3}
    g = run.game
    assert g.player.lives >= 3
    assert isinstance(g.wingman, wingman.Wingman)
    assert g.wingman.ship.image is wingman.pictures()[0]       # his own ship: the EDF-17 C


@pytest.mark.parametrize("phenix", [False, True])
def test_sacha_flies_his_old_edf17_whatever_the_pilot_flies(run, phenix, monkeypatch):
    _no_stray_harm(monkeypatch)
    _launch(run, phenix=phenix, act=2 if phenix else 1)
    g = run.game
    s = g.wingman.ship
    assert s.image is wingman.pictures()[0] and s.image.get_size() == (60, 90)
    assert s._engine_plan()[0] == "edf17" and len(s._engine_plan()[1]) == 2
    _with_sacha(run)
    for _ in range(120):
        s.phenix_gauge = 99                    # (even a full gauge: no Phenix form, no dome)
        run.frames(1)
    assert not s.is_phenix and s.phenix_gauge == 0


def test_the_damage_shows_on_his_ship_and_his_jets_smoke_more_and_more(run, monkeypatch):
    _no_stray_harm(monkeypatch)
    _launch(run)
    g = run.game
    _with_sacha(run)
    w = g.wingman
    s = w.ship
    pics = wingman.pictures()
    smoke = []
    born = []                                                   # (where a puff was born, the jets at that moment)
    puff = w._puff_at
    w._puff_at = lambda x, y, dark=False: (born.append((x, y, w._nozzles())), puff(x, y, dark))
    run.frames(60)
    smoke.append(len(w.smoke))
    for n in (1, 2):
        s.invulnerable = 0.0
        w.damage(g)
        assert s.image is pics[n]
        w.smoke.clear()
        run.frames(60)
        smoke.append(len(w.smoke))
    assert smoke[0] == 0 < smoke[1] < smoke[2]
    assert born and all((x, y) in noz for x, y, noz in born)                   # out of the jets
    assert sum(p[7] for p in w.smoke) / len(w.smoke) < 140                       # darker smoke after two hits


def test_a_damaged_engine_coughs(run, monkeypatch):
    _no_stray_harm(monkeypatch)
    _launch(run)
    g = run.game
    _with_sacha(run)
    w = g.wingman
    for _ in range(2):
        w.ship.invulnerable = 0.0
        w.damage(g)
    low = 0
    for _ in range(60 * 6):
        run.frames(1)
        low += w.ship.engine_intensity <= 0.25
    assert low > 0


# ------------------------------------------------------------------ the four waves
def test_each_wave_adds_a_kind_and_the_last_one_brings_three_guardians(run):
    _launch(run)
    g = run.game
    seen = []
    for wave in range(4):
        _arrived(run)
        assert int(g.adventure.get("wave_i", 0)) == wave
        assert g.stage == 11
        seen.append(_kinds(g.formation))
        sq = guardian.squad(g)
        assert (len(sq.guardians) if sq is not None else 0) == (3 if wave == 3 else 0)
        if wave < 3:
            for e in g.formation.enemies:
                e.alive = e.dying = False
            g.formation.swarm["reserve"] = {k: 0 for k in (1, 2, 3, 4)}
            for _ in range(600):
                run.frames(1)
                if g.stage_transition == "arrive":
                    break
    assert seen == [[1], [1, 2], [1, 2, 3], [1, 2, 3, 4]]


def test_a_swarm_of_some_kinds_only():
    form = EnemyFormation()
    form.spawn_swarm(speed_mult=1.0, screens=1.0, kinds=(1, 3))
    assert _kinds(form) == [1, 3]
    assert form.swarm["reserve"][2] == form.swarm["reserve"][4] == 0
    assert form.swarm_remaining() == 13 + 7
    form = EnemyFormation()
    form.spawn_swarm(speed_mult=1.0, screens=1.0, kinds=(3, 4))
    assert form.swarm["slots"] == [] and _kinds(form) == [3, 4]


# ------------------------------------------------------------------ Sacha
def _bullet_on(ship):
    b = EnemyBullet(ship.x, ship.y - 4)
    return b


def test_three_shots_and_he_goes_home_without_exploding(run, monkeypatch):
    attack = _no_stray_harm(monkeypatch)
    _launch(run)
    g = run.game
    _with_sacha(run)
    w = g.wingman
    s = w.ship
    for n in (1, 2, 3):
        s.invulnerable = 0.0
        g.formation.bullets.append(_bullet_on(s))
        attack(g)
        assert w.hits == n
        assert s.alive and not s.dying                          # never destroyed
    assert w.state == "hurt"
    s.invulnerable = 0.0
    g.formation.bullets.append(_bullet_on(s))
    attack(g)
    assert w.hits == 3                                        # nothing more counts
    g.player.infinite_lives = True
    for _ in range(int(60 * (wingman.LEAVE_DELAY + 0.2))):
        run.frames(1)
    assert w.state in ("leave", "gone")
    assert wingman.shooters(g) == []
    for _ in range(240):
        run.frames(1)
    assert w.state == "gone" and s.y > BASE_HEIGHT        # out by the bottom of the screen
    assert g.adventure is not None and g.started             # the pilot goes on alone


def test_a_hit_gives_a_moment_of_grace(run, monkeypatch):
    attack = _no_stray_harm(monkeypatch)
    _launch(run)
    g = run.game
    _with_sacha(run)
    w = g.wingman
    g.formation.bullets.append(_bullet_on(w.ship))
    attack(g)
    g.formation.bullets.append(_bullet_on(w.ship))
    attack(g)
    assert w.hits == 1 and w.ship.invulnerable > 0


def test_his_points_are_not_the_pilots(run, monkeypatch):
    _no_stray_harm(monkeypatch)
    _launch(run)
    g = run.game
    before = g.score
    g._add_score(g.wingman.ship, 500)
    assert g.score == before and g.wingman.ship.score == 500


def test_he_dodges_a_shot_coming_at_him(run, monkeypatch):
    _no_stray_harm(monkeypatch)
    _launch(run)
    g = run.game
    _with_sacha(run)
    w = g.wingman
    g.formation.enemies = []
    g.formation.swarm["reserve"] = {k: 10 for k in (1, 2, 3, 4)}       # (the wave does not end)
    g.formation.swarm["wait"] = {k: 1e9 for k in (1, 2, 3, 4)}
    x0 = w.ship.x
    b = EnemyBullet(x0, 40)                                    # (high enough for him to notice it in time)
    g.formation.bullets = [b]
    for _ in range(150):
        run.frames(1)
    assert w.hits == 0
    assert abs(w.ship.x - x0) > 15


def _fight(run, wave, seconds, seed):
    """How many times he is damaged (a shot, a laser, a collision: one each) in a fight of `seconds` s."""
    import random
    random.seed(seed)
    np.random.seed(seed)
    _launch(run)
    g = run.game
    if wave:
        g.adventure["wave_i"] = wave
        g._setup_stage(11)
    _with_sacha(run)
    g.player.infinite_lives = True
    w = g.wingman
    events = []
    damage = w.damage
    w.damage = lambda game, why="shot": events.append(why) if damage(game, why) else False
    for _ in range(int(60 * seconds)):
        g.player.invulnerable = 5.0
        run.frames(1)
        if w.state != "fight" or g.stage_transition is not None:
            break
    return len(events)


def test_a_good_pilot_not_a_perfect_one(run):
    """He dodges well (the first wave hardly touches him) but the last one, now and then, hits him: he smokes."""
    assert sum(_fight(run, 0, 30, seed) for seed in range(3)) <= 3
    assert sum(_fight(run, 3, 60, seed) for seed in range(3)) >= 1


def test_the_whole_mission_draws(run):
    _launch(run)
    g = run.game
    g.player.infinite_lives = True
    run.frames(600)
    assert g.started


# ------------------------------------------------------------------ his entry, a collision, his retreat
def test_he_comes_in_from_below_three_seconds_into_the_first_wave(run):
    _launch(run)
    g = run.game
    w = g.wingman
    assert w.state == "wait" and not w.targetable(g) and wingman.shooters(g) == []
    _arrived(run)                                          # the ship arrives alone
    assert w.state == "wait" and w.ship.y > BASE_HEIGHT
    waited = 0
    while w.state == "wait":
        g.player.invulnerable = 5.0
        run.frames(1)
        waited += 1
        assert waited < 60 * 5
    assert abs(waited / 60.0 - wingman.ENTER_DELAY) < 0.1
    assert w.state == "enter" and w.ship.y > wingman.LINE_Y and w.ship.engine_burst > 0     # from below, engines boosted
    ys = []
    while w.state == "enter":
        g.player.invulnerable = 5.0
        run.frames(1)
        ys.append(w.ship.y)
    assert ys == sorted(ys, reverse=True) and w.ship.y == wingman.LINE_Y
    assert w.state == "fight" and w.radio[0] == "wingman_hello"


def test_a_collision_takes_his_ship_straight_to_its_last_level_of_damage(run):
    _launch(run)
    g = run.game
    _with_sacha(run)
    w = g.wingman
    s = w.ship
    s.invulnerable = 1.0                                   # (even while it blinks)
    e = next(e for e in g.formation.enemies if e.alive and not e.dying)
    e.x, e.y = s.x, s.y
    wingman.attacks(g)
    assert w.hits == wingman.HITS and w.state == "hurt"
    assert s.image is wingman.pictures()[-1]
    assert s.alive and not s.dying                         # he cannot die


@pytest.mark.parametrize("side", ["left", "right"])
def test_his_retreat_takes_off_turns_about_and_leaves_by_the_bottom(run, side, monkeypatch):
    _no_stray_harm(monkeypatch)
    _launch(run)
    g = run.game
    _with_sacha(run)
    w = g.wingman
    s = w.ship
    s.x = 300 if side == "left" else BASE_WIDTH - 300
    w.target_x = s.x
    s.invulnerable = 0.0
    g.formation.bullets.append(EnemyBullet(s.x, s.y - 4))
    for _ in range(3):
        s.invulnerable = 0.0
        w.damage(g)
    y0, x0 = s.y, s.x
    angles, ys, xs = [], [], []
    for _ in range(60 * 6):
        g.player.invulnerable = 5.0
        run.frames(1)
        angles.append(w.angle)
        ys.append(s.y)
        xs.append(s.x)
        if w.state == "gone":
            break
    assert w.state == "gone" and s.y > BASE_HEIGHT and s.alive
    assert min(ys) < y0 - 60                               # it took off first
    assert abs(angles[-1]) == 180.0                        # turned about: nose down
    k = next(i for i, a in enumerate(angles) if a != 0)
    assert ys[k] < y0                                       # (the turn starts up there)
    turned_to = max(xs) - x0 if side == "left" else x0 - min(xs)
    assert turned_to > 60                                  # the half circle goes toward the middle (the room)
    assert wingman.shooters(g) == [] and not w.targetable(g)


def _dust_count(g):
    return sum(1 for e in g.explosions if getattr(e, "kind", None) == "dust")


def test_the_dust_when_he_arrives_like_the_ships(run):
    _launch(run)
    g = run.game
    _arrived(run)
    w = g.wingman
    while w.state in ("wait", "enter"):
        g.player.invulnerable = 5.0
        before = _dust_count(g)
        run.frames(1)
    assert _dust_count(g) == before + 2                    # two puffs under his ship, as for the ships of the player
    feet = [e for e in g.explosions if getattr(e, "kind", None) == "dust"][-2:]
    assert all(abs(e.x - w.ship.x) <= 20 and e.y > w.ship.y for e in feet)


def test_he_flies_smoothly_like_a_person(run):
    """No jerks nor little hops: few changes of direction, his speed changes gradually."""
    _launch(run)
    g = run.game
    g.adventure["wave_i"] = 2
    g._setup_stage(11)
    _with_sacha(run)
    g.player.infinite_lives = True
    w = g.wingman
    xs, ts = [], []
    for _ in range(60 * 20):
        g.player.invulnerable = 5.0
        run.frames(1)
        if w.state != "fight" or g.stage_transition is not None:
            break
        if ts and w.clock == ts[-1]:
            continue                                       # (a frame the game froze: the hit stop of a kill)
        xs.append(w.ship.x)
        ts.append(w.clock)
    v = np.diff(np.array(xs)) / np.diff(np.array(ts))
    moving = np.abs(v) > 5
    sgn = np.sign(v[moving])
    reversals = int(np.sum(sgn[1:] != sgn[:-1]))
    assert reversals / (len(xs) / 60) < 0.7
    dt = 1 / 60
    assert np.max(np.abs(np.diff(v))) <= wingman.ACCEL * 1.6 * dt * 1.05 + 1.0     # (never a jump in speed)
