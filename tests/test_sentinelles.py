"""EDF - Opération Sentinelles silencieuses I-IV: the SpaceWar level (src/spacewar.py) as four real missions of the
Adventure, one round each gas giant. Their own levels, the normal points, the normal penalties, the order in which they are
opened, and the replay of all four once the last one is won."""
import copy
import os
import random

import pygame
import pytest

import i18n
import spacewar as sw
import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)
from test_spacewar import _alone, _bird, _orbit, _pin

IDS = ["sentinelle_1", "sentinelle_2", "sentinelle_3", "sentinelle_4"]
PLANETS = ["jupiter", "saturn", "uranus", "neptune"]
LEVELS = {
    "sentinelle_1": [(1, 0, 0), (0, 0, 1)],
    "sentinelle_2": [(1, 0, 0), (0, 1, 0), (0, 0, 1)],
    "sentinelle_3": [(1, 0, 0), (1, 1, 0), (0, 1, 1)],
    "sentinelle_4": [(1, 0, 0), (1, 1, 0), (0, 2, 1)],
}
ACTS = {"sentinelle_1": (1, 2, 3), "sentinelle_2": (2, 3), "sentinelle_3": (2, 3), "sentinelle_4": (3,)}
PICTURES = ["sentinelle1_jupiter", "sentinelle2_saturne", "sentinelle3_uranus", "sentinelle4_neptune"]
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "story")


def _state(act=1, mode="normal", credits=1000, **flags):
    st = ss.default_state()
    st.update(act=act, mode=mode, credits=credits)
    st["flags"].update(flags)
    return st


def _won(state, *ids):
    for mid in ids:
        ss.record_result(state, mid, 100, True)


# ------------------------------------------------------------------ the table
def test_four_missions_one_per_planet_with_their_levels():
    found = [m for m in ss.MISSIONS if m["id"].startswith("sentinelle_")]
    assert [m["id"] for m in found] == IDS
    for m, planet in zip(found, PLANETS):
        assert m["spacewar"] and m["planet"] == planet and not m.get("training") and not m.get("test")
        assert [tuple(lv) for lv in m["sw_levels"]] == LEVELS[m["id"]]
        assert m["acts"] == ACTS[m["id"]] and m["once"] and m["replay"] == ss.SENTINELLE_DONE
        assert ss.mission_group(m) == ss.GROUP_STORY
        assert m["planet"] in sw.PLANETS


def test_the_four_missions_come_after_the_tests_and_are_not_tests():
    ids = [m["id"] for m in ss.MISSIONS]
    assert ids.index("sentinelle_1") > ids.index("test_spacewar_neptune")
    assert not [m for m in ss.MISSIONS if m["id"].startswith("sentinelle_") and m.get("training")]


@pytest.mark.parametrize("mid", IDS)
def test_texts_scene_and_pictures(mid):
    m = ss.mission_by_id(mid)
    for key in (m["title"], m["blurb"], m["hud_title"]):
        assert set(i18n.T[key]) == set(i18n.LANG_CODES) and all(i18n.T[key][c] for c in i18n.LANG_CODES)
    scene = ss.scene_of(mid)
    (pic, key), = scene["slides"]
    assert pic == PICTURES[IDS.index(mid)] and os.path.isfile(os.path.join(ASSETS, pic + ".jpg"))
    for lang in ("fr", "en", "de"):
        text = i18n.T[key][lang]
        assert "{name}" in text and "20" in text and text.startswith(("Commandement EDF", "EDF Command"))
    assert i18n.T[key]["fr"] != i18n.T[key]["en"]
    assert i18n.T[scene["title"]]["fr"]
    lines = ss.intro_lines(i18n.t, key, "NOVA")
    assert lines[-1].endswith("NOVA.") and "{name}" not in "\n".join(lines)


def test_the_two_clips_exist_and_loop_without_sound():
    for pic in ("sentinelle1_jupiter", "sentinelle4_neptune"):
        assert ss.clip_path(pic)
    assert not ss.clip_path("sentinelle2_saturne") and not ss.clip_path("sentinelle3_uranus")
    for pic in PICTURES:
        assert pygame.image.load(os.path.join(ASSETS, pic + ".jpg")).get_size() == (1280, 720)
        assert os.path.getsize(os.path.join(ASSETS, pic + ".jpg")) < 200_000


# ------------------------------------------------------------------ the order
def test_only_the_first_is_open_at_the_start_of_act_1():
    st = _state(act=1)
    assert ss.mission_playable(st, ss.mission_by_id("sentinelle_1"))
    assert ss.mission_by_id("sentinelle_1") in ss.visible_missions(st)
    for mid in IDS[1:]:
        assert ss.mission_by_id(mid) not in ss.visible_missions(st)
        assert not ss.mission_playable(st, ss.mission_by_id(mid))


@pytest.mark.parametrize("act", [2, 3])
def test_each_one_opens_when_the_one_before_is_won(act):
    st = _state(act=act)
    assert not ss.mission_playable(st, ss.mission_by_id("sentinelle_2"))
    _won(st, "sentinelle_1")
    assert ss.mission_playable(st, ss.mission_by_id("sentinelle_2"))
    assert not ss.mission_playable(st, ss.mission_by_id("sentinelle_3"))
    _won(st, "sentinelle_2")
    assert ss.mission_playable(st, ss.mission_by_id("sentinelle_3"))
    assert not ss.mission_playable(st, ss.mission_by_id("sentinelle_4"))
    assert ss.mission_by_id("sentinelle_3") in ss.visible_missions(st)


def test_the_fourth_is_in_act_3_only_and_opens_when_the_third_is_won():
    for act in (1, 2):
        st = _state(act=act, sentinelle_3=True)
        assert ss.mission_by_id("sentinelle_4") not in ss.visible_missions(st)
    st = _state(act=3)
    assert ss.mission_by_id("sentinelle_4") in ss.visible_missions(st)
    assert not ss.mission_playable(st, ss.mission_by_id("sentinelle_4"))
    _won(st, "sentinelle_1", "sentinelle_2", "sentinelle_3")
    assert ss.mission_playable(st, ss.mission_by_id("sentinelle_4"))


def test_a_won_one_is_flown_once_until_the_fourth_is_won_then_all_come_back():
    st = _state(act=3)
    _won(st, "sentinelle_1", "sentinelle_2", "sentinelle_3")
    for mid in IDS[:3]:
        assert not ss.mission_playable(st, ss.mission_by_id(mid))
    assert not ss.flag(st, ss.SENTINELLE_DONE)
    _won(st, "sentinelle_4")
    assert ss.flag(st, ss.SENTINELLE_DONE)
    for mid in IDS:
        assert ss.mission_playable(st, ss.mission_by_id(mid))
        assert ss.mission_by_id(mid) in ss.visible_missions(st)


def test_a_lost_one_can_be_tried_again_and_loses_the_normal_penalty():
    st = _state(act=1, credits=2000)
    res = ss.record_result(st, "sentinelle_1", 300, False)
    assert res["lost"] == ss.failure_penalty(2000) == 100 and st["credits"] == 1900
    assert not res.get("training") and not ss.flag(st, "sentinelle_1")
    assert ss.mission_playable(st, ss.mission_by_id("sentinelle_1"))


def test_a_failure_in_veteran_mode_makes_the_pilot_fall():
    st = _state(mode="veteran")
    res = ss.record_result(st, "sentinelle_1", 300, False)
    assert res["fallen"] and st["fallen"]


def test_the_points_are_paid_at_every_win_and_the_replays_are_normal():
    st = _state(act=3, credits=0)
    for mid in IDS:
        res = ss.record_result(st, mid, 250, True)
        assert res["cleared"] and res["score"] == 250 and not res.get("training")
    assert st["credits"] == 1000
    res = ss.record_result(st, "sentinelle_2", 400, True)
    assert st["credits"] == 1400 and not res["first"]
    res = ss.record_result(st, "sentinelle_2", 400, False)
    assert res["lost"] == ss.failure_penalty(1400) and st["credits"] == 1400 - res["lost"]


def test_the_flags_follow_the_chain():
    st = _state()
    for mid in IDS:
        ss.record_result(st, mid, 10, True)
    assert all(ss.flag(st, mid) for mid in IDS) and ss.flag(st, ss.SENTINELLE_DONE)
    st = _state()
    _won(st, "sentinelle_1", "sentinelle_2", "sentinelle_3")
    assert not ss.flag(st, ss.SENTINELLE_DONE)


# ------------------------------------------------------------------ the launch
@pytest.mark.parametrize("mid", IDS)
def test_the_launch_spec_is_a_real_mission(mid):
    hub = StoryHub()
    hub.state = _state(act=3, **{m: True for m in IDS[:3]})
    hub.state["items"]["got"]["genesis"] = "installed"
    hub.map_index = next(i for i, m in enumerate(hub.missions()) if m["id"] == mid)
    spec = hub._launch_selected()
    assert spec["spacewar"] and not spec.get("training") and spec["items"] == []
    assert [tuple(lv) for lv in spec["sw_levels"]] == LEVELS[mid]
    assert spec["planet"] == PLANETS[IDS.index(mid)]


def test_the_test_mission_keeps_its_three_levels_and_its_training():
    hub = StoryHub()
    hub.state = ss.default_state()
    hub.map_index = next(i for i, m in enumerate(hub.missions()) if m["id"] == "test_spacewar")
    spec = hub._launch_selected()
    assert spec["training"] and "sw_levels" not in spec


def test_a_won_mission_toasts_its_points(monkeypatch):
    hub = StoryHub()
    hub.state = _state()
    monkeypatch.setattr(hub, "save", lambda: None)
    hub.apply_result("sentinelle_1", 120, True)
    assert hub.toast == i18n.t("story_clear").format(pts=120)
    assert hub.state["credits"] == 1120


# ------------------------------------------------------------------ the formation
@pytest.mark.parametrize("mid", IDS)
def test_the_levels_have_the_birds_of_the_table(mid):
    form = sw.SpaceWarFormation(rng=random.Random(5), levels=LEVELS[mid])
    assert form.levels == LEVELS[mid]
    for n, (blue, green, boss) in enumerate(LEVELS[mid], 1):
        form.start_level(n)
        kinds = sorted(b.kind for b in form.birds)
        assert kinds == sorted([1] * blue + [2] * green + [sw.SAUCER] * boss)
        assert form.level == n


def test_without_levels_the_formation_has_the_three_of_the_test():
    form = sw.SpaceWarFormation(rng=random.Random(1))
    assert form.levels == sw.LEVELS and not form.points
    form.start_level(9)
    assert form.level == 3
    form = sw.SpaceWarFormation(rng=random.Random(1), levels=[(1, 0, 0), (0, 0, 1)])
    form.start_level(9)
    assert form.level == 2
    form.start_level(0)
    assert form.level == 1


def test_a_level_with_a_saucer_is_won_when_the_saucer_is_destroyed_whatever_is_left():
    form = sw.SpaceWarFormation(rng=random.Random(2), levels=LEVELS["sentinelle_4"])
    form.start_level(3)
    assert len(form.birds) == 3 and not form.level_done()
    boss = [b for b in form.birds if b.kind == sw.SAUCER][0]
    boss.alive = False
    assert form.level_done() and sum(b.alive for b in form.birds) == 2


# ------------------------------------------------------------------ in the game
def _mission(run, mid, credits=1000):
    """Launch `mid` from a save of act 3 where everything before it is won."""
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st.update(act=3, credits=credits)
    for before in IDS[:IDS.index(mid)] if mid in IDS else []:
        st["flags"][before] = True
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mid)
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    g.player.infinite_lives = False
    run.frames(2)
    return g, spec


def test_a_sentinelle_mission_runs_its_own_levels_with_its_planet(run, monkeypatch):
    import story_items
    monkeypatch.setattr(story_items, "plan_drop", lambda *a, **k: {"item": "genesis"})    # (a drop is always planned...)
    g, spec = _mission(run, "sentinelle_3")
    form = g.formation
    assert isinstance(form, sw.SpaceWarFormation) and form.points
    assert form.levels == LEVELS["sentinelle_3"] and sw.PLANET == "uranus"
    assert g.player.lives == 1 and not g.adventure.get("training")
    assert not g.adventure.get("loot_plan")
    g._end_adventure(False)


def test_the_test_mission_pays_nothing(run):
    g, spec = _mission(run, "test_spacewar")
    form = g.formation
    assert not form.points
    b = _bird(form, 1)
    sw._kill_bird(g, form, b)
    assert g.score == 0
    g._end_adventure(False)


def test_a_blue_bird_pays_10_a_green_20_and_the_saucer_its_boss_points(run):
    g, spec = _mission(run, "sentinelle_2")
    form = g.formation
    _alone(run)
    g.score = 0
    sw._kill_bird(g, form, _bird(form, 1))
    assert g.score == 10 == g.player.score
    sw._kill_bird(g, form, _bird(form, 2))
    assert g.score == 30
    sw._kill_bird(g, form, _bird(form, sw.SAUCER))
    assert g.score == 30 + 500 + g._level_points_bonus()
    assert g.adventure["kills"]["boss"] == 1 and g.adventure["kills"]["bird1"] == 1
    g._end_adventure(False)


def test_the_hud_counts_the_levels_of_the_mission(run, monkeypatch):
    import draw_frame
    texts = []

    class _Cache:
        def __init__(self, real):
            self.real = real

        def get(self, font, text, color, *a, **k):
            texts.append(text)
            return self.real.get(font, text, color, *a, **k)
    for mid, total in (("sentinelle_1", 2), ("sentinelle_4", 3)):
        g, spec = _mission(run, mid)
        monkeypatch.setattr(g, "text_cache", _Cache(g.text_cache))
        texts.clear()
        draw_frame.draw_hud(g)
        assert any(("1/%d" % total) in x and "20" in x for x in texts), texts
        g._end_adventure(False)


def test_the_whole_mission_won_pays_the_credits_and_opens_the_next(run):
    g, spec = _mission(run, "sentinelle_1")
    form = g.formation
    p = g.player
    # level 1: the blue bird falls
    for b in form.birds:
        _pin(b)
    _orbit(p)
    run.frames(3)
    form.level_time = 1.0
    for b in list(form.birds):
        sw._kill_bird(g, form, b)
    run.frames(3)
    assert form.pause > 0 and g.score == 10
    form.pause = 0.01
    run.frames(5)
    assert form.level == 2 and [b.kind for b in form.birds] == [sw.SAUCER]
    for b in form.birds:
        _pin(b)
    _orbit(p)
    form.level_time = 1.0
    boss = form.birds[0]
    boss.hp = 1
    sw._hurt_bird(g, form, boss)
    run.frames(3)
    assert form.won
    score = g.score
    assert score >= 510
    g._end_adventure(True)
    st = g.story.state
    assert st["credits"] >= score and ss.flag(st, "sentinelle_1")
    assert ss.mission_playable(st, ss.mission_by_id("sentinelle_2"))
    assert not ss.mission_playable(st, ss.mission_by_id("sentinelle_1"))


def test_dying_costs_the_normal_penalty(run):
    g, spec = _mission(run, "sentinelle_1")
    st = g.story.state
    st["credits"] = 2000
    g.story.state = st
    g._end_adventure(False)
    assert g.story.state["credits"] == 1900


def test_the_banner_of_a_level_counts_the_levels_of_the_mission():
    for mid, total in (("sentinelle_1", 2), ("sentinelle_3", 3)):
        form = sw.SpaceWarFormation(rng=random.Random(4), levels=LEVELS[mid])
        said = []
        form._say = lambda surface, text, color, cy, said=said: said.append(text)
        form.started = True
        form.start_level(1)
        form.level_time = 0.1
        form.draw(pygame.Surface((1280, 720)))
        assert any("1 / %d" % total in x for x in said), said
