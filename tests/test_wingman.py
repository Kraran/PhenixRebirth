"""Sacha, the wingman flown by the computer (src/wingman.py), in Défense de Phobos I, II and III: the swarm in four
waves, his EDF-17 C, his damage, his retreat, his voice, his skill growing from one mission to the next."""
import numpy as np
import pygame
import pytest

import guardian
import story_state as ss
import wingman
from enemy import EnemyBullet, EnemyFormation
from settings import BASE_HEIGHT, BASE_WIDTH
from test_smoke import run  # noqa: F401  (fixture)

ID = "phobos_1"                   # Défense de Phobos I (Act 1); II in Act 2


def _launch(run, phenix=False, act=1, mode="normal"):
    g = run.game
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    st["flags"]["dome_s5"] = True                # (Défense de Phobos I is open)
    mission = ID
    if act >= 2:
        ss.jump_to_act2(st)
        st["flags"].update(phenix_s1=True, phenix_s2=True)      # (Défense de Phobos II is open)
        mission = "phobos_2"
    if phenix:
        st["flags"]["phenix_owned"] = True
        st["slots"][1]["owned"] = True
        st["selected_slot"] = 1
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.pane = "map"
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mission)
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    g.player.infinite_lives = True              # (these tests watch Sacha: the pilot is never lost)
    g.player.lives = 99
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
def test_the_test_mission_is_gone():
    """TEST - Sacha has served: Sacha flies in the three Défense de Phobos missions (and BONUS FINAL - Nuée)."""
    assert ss.mission_by_id("test_sacha") is None
    import i18n
    assert "story_m_sacha_test" not in i18n.T
    assert [m["id"] for m in ss.MISSIONS if m.get("wingman")] == ["phobos_1", "phobos_2", "phobos_3"]


def test_his_skill_grows_from_one_mission_to_the_next():
    skills = [ss.mission_by_id("phobos_%d" % n)["wingman_skill"] for n in (1, 2, 3)]
    assert skills == [1, 2, 3]
    lv = [wingman.SKILLS[n] for n in skills] + [wingman.ACE]
    for a, b in zip(lv, lv[1:]):          # each one sees sooner, further, keeps more room, chases the birds less
        assert b["reaction"] < a["reaction"] and b["horizon"] > a["horizon"]
        assert b["safe"] > a["safe"] and b["aim"] < a["aim"]
    assert wingman.SKILLS[1] == {"reaction": wingman.REACTION, "horizon": wingman.HORIZON, "safe": wingman.SAFE,
                                 "aim": wingman.AIM}


def test_the_mission_gives_him_his_skill(run):
    spec = _launch(run, act=2)
    w = run.game.wingman
    assert spec["wingman_skill"] == 2 and w.skill == 2
    assert (w.reaction, w.horizon, w.safe, w.aim) == tuple(wingman.SKILLS[2][k] for k in ("reaction", "horizon",
                                                                                          "safe", "aim"))


def test_the_launch(run):
    spec = _launch(run)
    assert not spec.get("training") and spec["wingman"] == "sacha" and spec["wingman_skill"] == 1
    assert spec["swarm"] and spec["stage"] == 11 and spec["waves"] == [11, 11, 11, 11]
    assert spec["swarm_kinds"] == [[1], [1, 2], [1, 2, 3], [1, 2, 3, 4]]
    assert not spec.get("guardians_wave")                     # (no Guardians in Act 1)
    g = run.game
    assert isinstance(g.wingman, wingman.Wingman) and g.wingman.skill == 1
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
def test_each_wave_adds_a_kind_and_act_1_has_no_guardians(run):
    _launch(run)
    g = run.game
    seen = []
    for wave in range(4):
        _arrived(run)
        assert int(g.adventure.get("wave_i", 0)) == wave
        assert g.stage == 11
        seen.append(_kinds(g.formation))
        sq = guardian.squad(g)
        assert sq is None                                        # (Défense de Phobos I: more dark gargoyles instead)
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


# ------------------------------------------------------------------ his voice on the radio
def test_each_line_has_its_voice_on_the_radio():
    import os
    import i18n
    import sounds
    from settings import asset_path
    for key in sounds.RADIO_LINES:
        assert i18n.t(key) != key                                           # (the words of the same line)
        path = asset_path("sounds", "sacha", f"{key}.ogg")
        assert os.path.getsize(path) > 5000
        snd = pygame.mixer.Sound(path) if pygame.mixer.get_init() else None
        if snd is not None:
            assert 1.0 < snd.get_length() < wingman.RADIO_TIME + 0.5        # (heard while its words are on screen)


def test_he_speaks_when_his_words_show(run, monkeypatch):
    _no_stray_harm(monkeypatch)
    g = run.game
    heard = []
    monkeypatch.setattr(g.sounds, "play_radio", lambda key, volume=None: heard.append(key))
    _launch(run)
    _with_sacha(run)
    w = g.wingman
    assert heard == ["wingman_hello"]
    for n in (1, 2, 3):
        w.ship.invulnerable = 0.0
        w.damage(g)
    assert heard == ["wingman_hello", "wingman_hit_1", "wingman_hit_2", "wingman_hit_3"]


def test_his_voice_holds_while_the_game_is_paused(run, monkeypatch):
    g = run.game
    held = []
    monkeypatch.setattr(g.sounds, "hold_radio", lambda paused: held.append(paused))
    _launch(run)
    _with_sacha(run)
    w = g.wingman
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    g.paused = True
    w.banner(surf, g)
    w.banner(surf, g)
    g.paused = False
    w.banner(surf, g)
    assert held == [True, False]


def test_the_radio_plays_on_its_own_channel():
    import sounds
    assert sounds.SoundManager.RADIO_CHANNEL == 1                           # (0 is the announcer's)
    if pygame.mixer.get_init():
        assert pygame.mixer.get_num_channels() >= 2


def test_the_ash_of_the_mission_is_made_behind_the_loading_bar(run):
    """The Guardians of the last wave burn gargoyles: their ash (both wings, or one) and the ash of the small birds are made
    before the mission, so that a burning bird never holds the game."""
    from game import Game
    spec = _launch(run, act=2)                                  # (Défense de Phobos II: Guardians in the last wave)
    assert Game.guardians_meet_gargoyles(spec)
    assert not Game.guardians_meet_gargoyles({"swarm": True, "waves": [11, 11], "swarm_kinds": [[1], [1, 2]],
                                              "guardians_wave": {2: 3}})
    guardian._BURN_ART.clear()
    guardian.warm_gargoyle_ash()
    for stage in (3, 4):
        for wings in ((True, True), (True, False), (False, True)):
            assert ("garg", stage) + wings in guardian._BURN_ART
    assert 1 in guardian._BURN_ART and 2 in guardian._BURN_ART
