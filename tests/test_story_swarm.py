"""Dome V (the swarm), the gateway to Act 2 and the first dome upgrade."""
import random

import pytest

import enemy as enemy_mod
import story_state as ss
from enemy import (BigBird, Enemy, EnemyFormation, SWARM_NORMAL_COUNT, SWARM_REFILL_DELAY, SWARM_SCREENS)
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

KINDS = (1, 2, 3, 4)
ON_SCREEN = {1: 4, 2: 7, 3: 2, 4: 3}       # a third of the normal screens: 13, 22, 7, 10


@pytest.fixture(autouse=True)
def _screen(run):
    """Sprites need an initialised display: every test runs with a Game around."""
    yield run


def _kinds(form):
    out = {k: 0 for k in KINDS}
    for e in form.enemies:
        if e.alive and not e.dying:
            out[e.stage] += 1
    return out


def _swarm(mult=1.2):
    form = EnemyFormation()
    form.spawn_swarm(speed_mult=mult)
    return form


# ------------------------------------------------------------------ the formation
def test_the_swarm_shows_a_third_of_a_normal_screen_of_each_kind_and_the_rest_waits():
    form = _swarm()
    assert SWARM_NORMAL_COUNT == {1: 13, 2: 22, 3: 7, 4: 10}      # the counts of the normal screens
    assert _kinds(form) == ON_SCREEN == {k: round(n / 3) for k, n in SWARM_NORMAL_COUNT.items()}
    assert sum(_kinds(form).values()) == 16                       # three times fewer at once than before (48)
    assert form.swarm["reserve"] == {1: 35, 2: 59, 3: 19, 4: 27}  # still three times the normal count in all
    assert form.swarm_remaining() == 3 * (13 + 22 + 7 + 10) == 156
    assert all(isinstance(e, Enemy) for e in form.enemies if e.stage in (1, 2))
    assert all(isinstance(e, BigBird) for e in form.enemies if e.stage in (3, 4))
    assert {e.speed_mult for e in form.enemies} == {1.2}


def test_the_birds_sit_in_their_own_seats_inside_the_screen():
    form = _swarm()
    birds = [e for e in form.enemies if e.stage in (1, 2)]
    seats = {(e.start_x, e.start_y) for e in birds}
    assert len(seats) == len(birds) == 11                          # nobody shares a seat
    assert all(170 + 20 <= e.start_x <= 1280 - 170 - 20 for e in birds)   # the drift keeps them on screen
    xs = sorted({e.start_x for e in birds if e.start_y == birds[0].start_y})
    assert all(b - a >= 90 for a, b in zip(xs, xs[1:]))            # a bird is 38 px wide: no overlap
    blue = [e.formation_index for e in birds if e.stage == 1]
    assert sorted(blue) == blue
    rows = {}
    for e in birds:
        rows.setdefault(e.start_y, set()).add(e.stage)
    assert all(kinds == {1, 2} for kinds in rows.values())         # blue and khaki mixed in every row


def test_a_fallen_enemy_is_replaced_by_one_of_the_same_kind_coming_from_above():
    for kind in KINDS:
        form = _swarm()
        victim = next(e for e in form.enemies if e.stage == kind)
        victim.kill(flash=False)
        form.update(0.01, 640)
        assert _kinds(form)[kind] == ON_SCREEN[kind], kind
        assert form.swarm["reserve"][kind] == SWARM_SCREENS * SWARM_NORMAL_COUNT[kind] - ON_SCREEN[kind] - 1
        new = [e for e in form.enemies if e.stage == kind and e.alive][-1]
        assert new.y < 0, kind                                      # it comes in from the top
        assert new.state in ("returning", "enter")
        assert new.speed_mult == 1.2


def test_a_new_bird_takes_the_seat_that_was_freed():
    form = _swarm()
    victim = next(e for e in form.enemies if e.stage == 2)
    seat = (victim.start_x, victim.start_y)
    victim.kill(flash=False)
    form.update(0.01, 640)
    new = [e for e in form.enemies if e.stage == 2 and e.alive and e.y < 0][0]
    assert (new.start_x, new.start_y) == seat
    for _ in range(300):                                            # it flies to its seat and joins the formation
        form.update(1 / 60, 640)
    assert new.state in ("formation", "diving")


def test_arrivals_of_one_kind_are_spaced_out():
    form = _swarm()
    for e in [e for e in form.enemies if e.stage == 1][:3]:
        e.kill(flash=False)
    form.update(0.01, 640)
    assert _kinds(form)[1] == 4 - 3 + 1                             # one at a time
    form.update(0.01, 640)
    assert _kinds(form)[1] == 4 - 3 + 1                             # the next one has to wait its turn
    form.update(SWARM_REFILL_DELAY, 640)
    assert _kinds(form)[1] == 4 - 3 + 2


def test_a_gargoyle_glides_in_then_roams_and_does_not_shoot_while_entering(monkeypatch):
    form = _swarm()
    victim = next(e for e in form.enemies if e.stage == 3)
    victim.kill(flash=False)
    form.update(0.01, 640)
    new = [e for e in form.enemies if e.stage == 3 and e.alive and e.state == "enter"][0]
    monkeypatch.setattr(random, "random", lambda: 0.0)              # everyone wants to shoot
    form.bullets = []
    new.shoot_cooldown = 0.0
    before = sum(1 for b in form.bullets if b.owner_id == id(new))
    form.update(1 / 60, 640)
    assert sum(1 for b in form.bullets if b.owner_id == id(new)) == before
    monkeypatch.undo()
    for _ in range(200):
        new.update(1 / 60)
        if new.state == "roam":
            break
    assert new.state == "roam" and new.y >= 80


def test_every_kind_shoots_with_its_own_rules_inside_a_swarm(monkeypatch):
    form = _swarm()
    monkeypatch.setattr(random, "random", lambda: 0.0)
    form.update(1 / 60, 640)
    owners = {id(e): e for e in form.enemies}
    seen = {}
    for b in form.bullets:
        seen.setdefault(owners[b.owner_id].stage, set()).add(b.stage)
    assert seen and all(stages == {kind} for kind, stages in seen.items())    # a bullet carries its shooter's kind
    assert set(seen) >= {1, 2, 3, 4}


def test_the_swarm_is_won_when_every_enemy_ever_sent_is_down():
    form = _swarm()
    killed = {k: 0 for k in KINDS}
    for step in range(5000):
        for e in form.enemies:
            if e.alive and not e.dying:
                killed[e.stage] += 1
                e.kill(flash=False)
        if form.all_dead():
            break
        assert form.swarm_remaining() > 0
        form.update(0.2, 640)
        on_screen = _kinds(form)
        assert all(on_screen[k] <= SWARM_NORMAL_COUNT[k] for k in KINDS)
    assert form.all_dead() and form.swarm_remaining() == 0
    assert killed == {k: SWARM_SCREENS * n for k, n in SWARM_NORMAL_COUNT.items()}


def test_the_swarm_is_not_over_while_enemies_are_still_to_come():
    form = _swarm()
    for e in form.enemies:
        e.kill(flash=False)
    assert not form.all_dead()                                      # the reserve is still waiting
    form.swarm["reserve"] = {k: 0 for k in KINDS}
    form.enemies = []
    assert form.all_dead()


def test_a_normal_wave_is_not_a_swarm():
    form = EnemyFormation()
    assert form.swarm is None and form.swarm_remaining() == 0
    form.spawn_swarm(1.0)
    form.spawn_stage(2, speed_mult=1.0)
    assert form.swarm is None and len(form.enemies) == 22
    form.enemies[0].kill(flash=False)
    form.update(1.0, 640)
    assert len([e for e in form.enemies if e.alive]) == 21          # nobody comes to replace it


# ------------------------------------------------------------------ the missions
def test_dome_five_and_the_gateway_follow_the_series():
    m5, gate = ss.mission_by_id("dome_5"), ss.mission_by_id("act2_gate")
    assert m5["need"] == "dome_s4" and m5["swarm"] and m5["stage"] == 11 and m5["once"]
    assert set(m5["unlock"]) == {"dome_s5", "dome_online"}
    assert gate["need"] == "dome_s5" and ss.mission_waves(gate) == [11, 12, 13, 14, 15] and gate["once"]
    assert gate["act"] == 2 and gate["unlock"] == ["act2"]
    assert ss.mission_by_id("ch2_tease")["need"] == "act2"
    ids = [m["id"] for m in ss.MISSIONS]
    assert ids.index("dome_4") + 1 == ids.index("dome_5") and ids.index("dome_5") + 1 == ids.index("act2_gate")


def _open(**flags):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["flags"].update(flags)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


def test_the_launch_specs_of_the_new_missions():
    hub = _open(dome_s4=True, dome_s5=True)
    ids = [m["id"] for m in ss.MISSIONS]
    hub.map_index = ids.index("dome_5")
    spec = hub._launch_selected()
    assert spec["swarm"] and spec["stage"] == 11 and "waves" not in spec
    hub.map_index = ids.index("act2_gate")
    spec = hub._launch_selected()
    assert spec["waves"] == [11, 12, 13, 14, 15] and "swarm" not in spec


def test_clearing_the_swarm_brings_the_dome_online_and_the_gateway_opens():
    st = ss.default_state()
    st["flags"]["dome_s4"] = True
    assert not ss.flag(st, "dome_online")
    res = ss.record_result(st, "dome_5", 800, True)
    assert ss.flag(st, "dome_online") and ss.flag(st, "dome_s5") and res["act"] == 0
    assert st["act"] == 1
    assert ss.mission_playable(st, ss.mission_by_id("act2_gate"))
    assert not ss.mission_playable(st, ss.mission_by_id("dome_5"))


def test_the_gateway_starts_act_two_once():
    st = ss.default_state()
    st["flags"]["dome_s5"] = True
    res = ss.record_result(st, "act2_gate", 500, True)
    assert st["act"] == 2 and res["act"] == 2 and ss.flag(st, "act2")
    assert ss.mission_open(st, ss.mission_by_id("ch2_tease"))
    assert not ss.mission_playable(st, ss.mission_by_id("ch2_tease"))      # Act 2 itself comes later
    assert not ss.mission_playable(st, ss.mission_by_id("act2_gate"))
    res = ss.record_result(st, "act2_gate", 500, True)
    assert res["act"] == 0 and st["act"] == 2
    assert ss.act_caps(st) == ss.act_caps(ss.default_state())               # the workshop caps stay Act 1's


def test_a_failed_gateway_does_not_start_act_two():
    st = ss.default_state()
    st["flags"]["dome_s5"] = True
    ss.record_result(st, "act2_gate", 500, False)
    assert st["act"] == 1 and not ss.flag(st, "act2")


def test_the_act_survives_a_save_and_the_slot_list_shows_it(tmp_path):
    st = ss.create_slot(1, "NOVA", "normal")
    st["flags"]["dome_s5"] = True
    ss.record_result(st, "act2_gate", 500, True)
    ss.save_state(ss.story_path(1), st)
    assert ss.load_state(ss.story_path(1))["act"] == 2
    assert ss.slot_summary(1)["act"] == 2


# ------------------------------------------------------------------ the dome upgrade
def test_the_first_dome_upgrade_is_sold_in_the_act_one_workshop_once_the_dome_is_online():
    assert [r[0] for r in ss.SHOP] == ["speed_60", "speed_80", "lives_2", "wall_slow", "dome_on"]
    st = ss.default_state()
    st["credits"] = 5000
    assert not ss.buy(st, "dome_on")                                 # locked until the swarm is beaten
    ss.record_result(st, "dome_5", 0, True) if False else st["flags"].update({"dome_online": True})
    assert not ss.loadout(st)["dome"]
    assert ss.buy(st, "dome_on") and st["credits"] == 4200
    lo = ss.loadout(st)
    assert lo["dome"] and lo["dome_dur"] == ss.DOME_DUR_START and lo["dome_cd"] == ss.DOME_CD_START
    assert not ss.buy(st, "dome_on")                                 # only once
    assert ss.upgrade_status(st, "dome_on") == "owned" if hasattr(ss, "upgrade_status") else True


def test_the_dome_upgrade_comes_before_the_longer_dome_of_act_two():
    st = ss.default_state()
    st["credits"] = 9999
    st["flags"]["dome_online"] = True
    assert ss.buy(st, "dome_on")
    assert ss.buy(st, "dome_dur")                                    # the next step is still the old upgrade
    assert ss.loadout(st)["dome_dur"] == pytest.approx(ss.DOME_DUR_START + ss.DOME_DUR_STEP)


# ------------------------------------------------------------------ in the game
def _launch(g, mission_id, **flags):
    base = dict(bestiary_s4=True, dome_s1=True, dome_s2=True, dome_s3=True, dome_s4=True, dome_s5=True)
    base.update(flags)
    _open(**base)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in ss.MISSIONS].index(mission_id)
    spec = g.story._launch_selected()
    assert spec, mission_id
    g._begin_adventure(spec)
    return g


def _kill_all(g):
    for e in g.formation.enemies:
        e.kill(flash=False)


def test_the_swarm_mission_starts_at_level_eleven_with_a_third_of_the_screens(run):
    g = _launch(run.game, "dome_5")
    assert g.stage == 11 and g.formation.swarm is not None
    assert _kinds(g.formation) == ON_SCREEN
    assert {round(e.speed_mult, 6) for e in g.formation.enemies} == {round(1.2 * g.difficulty_speed_mult(), 6)}


def test_destroying_the_whole_swarm_wins_the_mission(run):
    g = _launch(run.game, "dome_5")
    g.score = 700
    for _ in range(4000):
        if g.adventure is None:
            break
        _kill_all(g)
        run.frames(1, dt=1 / 20)
    assert g.adventure is None, g.formation.swarm_remaining()
    st = g.story.state
    assert "dome_5" in st["cleared"] and ss.flag(st, "dome_online")
    assert st["credits"] == 700
    assert g.story.pane == "map"


def test_the_kills_of_the_swarm_go_to_the_bestiary(run):
    g = _launch(run.game, "dome_5")
    class Foe:
        pass
    for kind in (1, 2, 3, 4):
        foe = Foe()
        foe.stage = kind
        g._enemy_kill_points(foe)
    assert g.adventure["kills"] == {"bird1": 1, "bird2": 1, "garg3": 1, "garg4": 1}


def test_dying_in_the_swarm_fails_it(run):
    g = _launch(run.game, "dome_5")
    g.story.state["credits"] = 500
    g._end_adventure(False)
    assert "dome_5" not in g.story.state["cleared"] and g.story.state["credits"] == 475
    assert not ss.flag(g.story.state, "dome_online")


def test_the_gateway_flies_levels_eleven_to_fifteen_and_the_boss_starts_act_two(run):
    g = _launch(run.game, "act2_gate")
    expected_content = [1, 2, 3, 4]
    for wave_i, stage in enumerate((11, 12, 13, 14)):
        assert g.stage == stage and g.adventure.get("wave_i", 0) == wave_i
        assert {e.stage for e in g.formation.enemies} == {expected_content[wave_i]}
        for _ in range(900):
            _kill_all(g)
            run.frames(1)
            if g.adventure.get("wave_i", 0) > wave_i:
                break
    assert g.stage == 15 and g.boss_saucer is not None and g.adventure["wave_i"] == 4
    assert g.story.state["act"] == 1                                 # not yet: the boss is still up
    g.boss_saucer.alive = False
    for _ in range(900):
        run.frames(1)
        if g.adventure is None:
            break
    assert g.adventure is None
    st = g.story.state
    assert st["act"] == 2 and ss.flag(st, "act2") and "act2_gate" in st["cleared"]
    assert "2" in g.story.toast
    assert ss.mission_open(st, ss.mission_by_id("ch2_tease"))


def test_the_hud_counts_down_the_swarm(run):
    from i18n import t
    g = _launch(run.game, "dome_5")
    run.frames(3)
    seen = []
    cls = type(g.text_cache)
    real = cls.get

    def spy(self, font, text, color, *a, **k):
        seen.append(str(text))
        return real(self, font, text, color, *a, **k)

    cls.get = spy
    try:
        run.frames(2)
    finally:
        cls.get = real
    assert any(s.startswith(t("story_swarm_left").split("{")[0]) for s in seen), seen[:8]


# ------------------------------------------------------------------ the map scrolls
def test_the_mission_map_always_shows_the_selected_mission(run):
    import pygame, story
    from i18n import t
    hub = _open(bestiary_s4=True)
    hub.pane = "map"
    assert len(hub.missions()) >= 11
    seen = []
    real = story._text

    def spy(surface, font, text, *a, **k):
        seen.append(str(text))
        return real(surface, font, text, *a, **k)

    story._text = spy
    g = run.game
    try:
        for i, m in enumerate(hub.missions()):
            hub.map_index = i
            seen.clear()
            hub.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
            assert any(t(m["title"]) in s for s in seen), m["id"]
            if i == 0:
                assert "^" not in seen and "v" in seen        # more below
            if i == len(hub.missions()) - 1:
                assert "^" in seen and "v" not in seen        # more above
    finally:
        story._text = real


def test_the_selected_row_never_leaves_the_frame(run):
    import pygame, story
    hub = _open(bestiary_s4=True)
    hub.pane = "map"
    ys = []
    real = story._text_fit

    def spy(surface, font, text, color, cy, left, max_w, scale=1.0):
        ys.append(cy)
        return real(surface, font, text, color, cy, left, max_w, scale)

    story._text_fit = spy
    g = run.game
    try:
        for i in range(len(hub.missions())):
            hub.map_index = i
            ys.clear()
            hub.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
            assert ys and max(ys) < 78 + (720 - 168), (i, ys)   # the blurb of the selected row is inside the box
    finally:
        story._text_fit = real


def test_the_hud_shows_the_wave_number_of_a_multi_wave_mission(run):
    from i18n import t
    g = _launch(run.game, "dome_1")
    run.frames(3)
    seen = []
    cls = type(g.text_cache)
    real = cls.get

    def spy(self, font, text, color, *a, **k):
        seen.append(str(text))
        return real(self, font, text, color, *a, **k)

    cls.get = spy
    try:
        run.frames(2)
        assert t("story_wave_n").format(n=1, m=3) in seen
        g.adventure["wave_i"] = 2
        seen.clear()
        run.frames(2)
        assert t("story_wave_n").format(n=3, m=3) in seen
        g.adventure["swarm"] = True                        # a swarm counts enemies, not waves
        seen.clear()
        run.frames(2)
        assert not any(s.startswith("VAGUE") for s in seen)
    finally:
        cls.get = real
