"""Défense de Phobos: three mandatory missions, one per act, the swarm of TEST - Sacha with Sacha as wingman."""
import story_state as ss
from enemy import EnemyFormation
from i18n import t
from test_smoke import run  # noqa: F401  (fixture: the display)

SERIES = ("phobos_1", "phobos_2", "phobos_3")
KINDS = [[1], [1, 2], [1, 2, 3], [1, 2, 3, 4]]


def _counts(mission, wave):
    boost = (mission.get("swarm_boost") or {}).get(wave)
    return EnemyFormation.swarm_counts(KINDS[wave - 1], mission.get("swarm_screens"), mission.get("swarm_crowd"), boost)


def test_the_three_missions_sit_in_the_story_of_each_act():
    p1, p2, p3 = (ss.mission_by_id(m) for m in SERIES)
    assert (p1["acts"], p2["acts"], p3["acts"]) == ((1,), (2,), (3,))
    assert (p1["need"], p2["need"], p3["need"]) == ("dome_s5", "phenix_s2", "guardians_s3")
    assert ss.mission_by_id("act2_gate")["need"] == "phobos_s1"
    assert ss.mission_by_id("phenix_3")["need"] == "phobos_s2"
    assert ss.mission_by_id("final_1")["need"] == "phobos_s3"
    for n, m in enumerate((p1, p2, p3), 1):
        assert m["wingman"] == "sacha" and m["swarm"] and m["swarm_kinds"] == KINDS and m["once"]
        assert m["unlock"] == ["phobos_s%d" % n] and ss.mission_group(m) == ss.GROUP_STORY
        assert not m.get("training") and not m.get("test")
    assert (p1["waves"], p2["waves"], p3["waves"]) == ([11] * 4, [16] * 4, [21] * 4)


def test_no_guardians_in_act_1_more_dark_gargoyles_instead():
    p1 = ss.mission_by_id("phobos_1")
    assert not p1.get("guardians_wave") and not p1.get("guardians_at")
    test = {"swarm_screens": 1.0}
    screen, total = _counts(p1, 4)
    base_screen, base_total = _counts(test, 4)
    assert screen[4] > base_screen[4] and total[4] > base_total[4]
    assert {k: v for k, v in screen.items() if k != 4} == {k: v for k, v in base_screen.items() if k != 4}
    for wave in (1, 2, 3):
        assert _counts(p1, wave) == _counts(test, wave)              # the first three waves: TEST - Sacha
    assert ss.mission_by_id("phobos_2")["guardians_wave"] == {4: 3}
    assert ss.mission_by_id("phobos_3")["guardians_wave"] == {4: 3}


def test_more_enemies_at_once_and_in_all():
    test = {"swarm_screens": 1.0}
    for mission_id, at_once, in_all in (("phobos_2", 1.3, 1.5), ("phobos_3", 1.5, 2.0)):
        m = ss.mission_by_id(mission_id)
        screen, total = _counts(m, 4)
        base_screen, base_total = _counts(test, 4)
        assert sum(screen.values()) == round(sum(base_screen.values()) * at_once)
        assert sum(total.values()) == round(sum(base_total.values()) * in_all)


def test_a_swarm_with_a_crowd_keeps_that_many_on_screen(run):
    form = EnemyFormation()
    form.spawn_swarm(kinds=(1, 2, 3, 4), screens=1.5, crowd=1.3)
    screen, total = EnemyFormation.swarm_counts((1, 2, 3, 4), 1.5, 1.3)
    assert len([e for e in form.enemies if e.alive]) == sum(screen.values())
    assert form.swarm_remaining() == sum(total.values())
    plain = EnemyFormation()
    plain.spawn_swarm(kinds=(1, 2, 3, 4), screens=1.0)
    assert plain.swarm["screen"] == {k: EnemyFormation.swarm_on_screen(k) for k in (1, 2, 3, 4)}


def test_the_scenes_and_the_journal():
    for n, mission_id in enumerate(SERIES, 1):
        assert ss.SCENES[mission_id]["slides"] == [("defense_phobos_%d" % n, "story_scene_phobos%d" % n)]
        assert mission_id in ss.SCENE_ORDER
    assert ss.mission_by_id("phobos_1")["win_scene"] == ss.SACHA_SCENE
    assert ss.SACHA_SCENE in ss.STORY_SCENES and ss.SACHA_SCENE in ss.SCENE_ORDER
    order = ss.SCENE_ORDER
    assert order.index("phobos_1") < order.index(ss.SACHA_SCENE) < order.index("phobos_2") < order.index("phobos_3")
    assert "Sacha" not in t("story_scene_phobos1")                     # the surprise of Act 1
    assert "Sacha" in t("story_scene_sacha") and "Sacha" in t("story_scene_phobos2")
    for key in ("story_m_phobos1", "story_m_phobos2", "story_m_phobos3", "story_log_phobos1", "story_scene_sacha_t"):
        assert t(key) != key


def test_the_first_victory_of_act_1_tells_who_sacha_is():
    st = ss.default_state()
    st["flags"]["dome_s5"] = True
    assert ss.mission_playable(st, ss.mission_by_id("phobos_1"))
    assert not ss.mission_playable(st, ss.mission_by_id("act2_gate"))
    res = ss.record_result(st, "phobos_1", 500, True)
    assert res["first"] and res["win_scene"] == ss.SACHA_SCENE
    assert ss.mission_playable(st, ss.mission_by_id("act2_gate"))
    assert not ss.mission_playable(st, ss.mission_by_id("phobos_1"))  # once


def test_an_older_save_past_a_defence_is_not_held():
    st = ss.default_state()
    st["flags"].update(dome_s5=True, act2=True, phenix_s2=True, phenix_s3=True, guardians_s3=True)
    st["cleared"] = ["act2_gate", "phenix_3", "final_1"]
    st["act"] = 3
    migrated = ss.migrate_state(st)
    assert all(ss.flag(migrated, "phobos_s%d" % n) for n in (1, 2, 3))
    young = ss.default_state()
    young["flags"]["dome_s5"] = True
    assert not ss.flag(ss.migrate_state(young), "phobos_s1")          # still to fly


def _launch(run, mission_id, act, **flags):
    import story_state as ss2
    g = run.game
    st = ss2.create_slot(1, "NOVA", "normal")
    ss2.mark_intro_seen(st)
    if act >= 2:
        ss2.jump_to_act2(st)
    st["flags"].update(flags)
    ss2.save_state(ss2.story_path(1), st)
    g.story.open_slot(1)
    g.story.pane = "map"
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mission_id)
    spec = g.story._launch_selected()
    assert spec, mission_id
    g._begin_adventure(spec)
    return g, spec


def test_defence_ii_flies_with_sacha_and_a_bigger_swarm(run):
    g, spec = _launch(run, "phobos_2", 2, phenix_s1=True, phenix_s2=True)
    assert spec["wingman"] == "sacha" and spec["swarm_crowd"] == 1.3 and spec["swarm_screens"] == 1.5
    assert spec["guardians_wave"] == {4: 3} and g.wingman is not None
    assert g.formation.swarm["screen"] == EnemyFormation.swarm_counts((1,), 1.5, 1.3)[0]


def test_defence_i_has_more_dark_gargoyles_in_its_last_wave(run):
    g, spec = _launch(run, "phobos_1", 1, dome_s5=True)
    assert spec["swarm_boost"] == {4: {4: 1.5}} and not spec.get("guardians_wave") and g.wingman is not None
    g.adventure["wave_i"] = 3
    g._setup_stage(11)
    assert g.formation.swarm["screen"] == EnemyFormation.swarm_counts((1, 2, 3, 4), 1.0, None, {4: 1.5})[0]
    assert g.formation.swarm["screen"][4] == 5
