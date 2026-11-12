"""TEST - Sacha: the swarm in four waves and Sacha, the wingman flown by the computer (src/wingman.py)."""
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
def test_sacha_flies_his_old_edf17_whatever_the_pilot_flies(run, phenix):
    _launch(run, phenix=phenix, act=2 if phenix else 1)
    g = run.game
    s = g.wingman.ship
    assert s.image is wingman.pictures()[0] and s.image.get_size() == (60, 90)
    assert s._engine_plan()[0] == "edf17" and len(s._engine_plan()[1]) == 2
    _arrived(run)
    for _ in range(120):
        s.phenix_gauge = 99                    # (even a full gauge: no Phenix form, no dome)
        run.frames(1)
    assert not s.is_phenix and s.phenix_gauge == 0


def test_the_damage_shows_on_his_ship_and_his_jets_smoke_more_and_more(run):
    _launch(run)
    g = run.game
    _arrived(run)
    w = g.wingman
    s = w.ship
    pics = wingman.pictures()
    smoke = []
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
    noz = w._nozzles()
    assert all(any(abs(p[0] - x) < 12 for x, _ in noz) for p in w.smoke)       # from the jets
    assert sum(p[7] for p in w.smoke) / len(w.smoke) < 140                       # darker smoke after two hits


def test_a_damaged_engine_coughs(run):
    _launch(run)
    g = run.game
    _arrived(run)
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
    _launch(run)
    g = run.game
    _arrived(run)
    w = g.wingman
    s = w.ship
    for n in (1, 2, 3):
        s.invulnerable = 0.0
        g.formation.bullets.append(_bullet_on(s))
        wingman.attacks(g)
        assert w.hits == n
        assert s.alive and not s.dying                          # never destroyed
    assert w.state == "hurt"
    s.invulnerable = 0.0
    g.formation.bullets.append(_bullet_on(s))
    wingman.attacks(g)
    assert w.hits == 3                                        # nothing more counts
    g.player.infinite_lives = True
    for _ in range(int(60 * (wingman.LEAVE_DELAY + 0.2))):
        run.frames(1)
    assert w.state in ("leave", "gone")
    assert wingman.shooters(g) == []
    for _ in range(240):
        run.frames(1)
    assert w.state == "gone" and s.y < 0
    assert g.adventure is not None and g.started             # the pilot goes on alone


def test_a_hit_gives_a_moment_of_grace(run):
    _launch(run)
    g = run.game
    _arrived(run)
    w = g.wingman
    g.formation.bullets.append(_bullet_on(w.ship))
    wingman.attacks(g)
    g.formation.bullets.append(_bullet_on(w.ship))
    wingman.attacks(g)
    assert w.hits == 1 and w.ship.invulnerable > 0


def test_his_points_are_not_the_pilots(run):
    _launch(run)
    g = run.game
    before = g.score
    g._add_score(g.wingman.ship, 500)
    assert g.score == before and g.wingman.ship.score == 500


def test_he_dodges_a_shot_coming_at_him(run):
    _launch(run)
    g = run.game
    _arrived(run)
    w = g.wingman
    g.formation.enemies = []
    g.formation.swarm["reserve"] = {k: 10 for k in (1, 2, 3, 4)}       # (the wave does not end)
    g.formation.swarm["wait"] = {k: 1e9 for k in (1, 2, 3, 4)}
    x0 = w.ship.x
    b = EnemyBullet(x0, w.ship.y - 300)
    g.formation.bullets = [b]
    for _ in range(90):
        run.frames(1)
    assert w.hits == 0
    assert abs(w.ship.x - x0) > 15


def test_he_survives_a_long_fight_much_better_than_three_hits(run):
    """The defender: a full minute of the third wave (the gargoyles) with an untouchable pilot."""
    _launch(run)
    g = run.game
    g.adventure["wave_i"] = 2
    g._setup_stage(11)
    _arrived(run)
    g.player.infinite_lives = True
    hits_at = []
    for i in range(60 * 60):
        g.player.invulnerable = 5.0
        before = g.wingman.hits
        run.frames(1)
        if g.wingman.hits != before:
            hits_at.append(i / 60.0)
        if g.stage_transition is not None:
            break
    assert len(hits_at) <= 2, hits_at


def test_the_whole_mission_draws(run):
    _launch(run)
    g = run.game
    g.player.infinite_lives = True
    run.frames(600)
    assert g.started
