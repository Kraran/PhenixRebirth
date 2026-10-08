"""Dome series (Act 1): four chained missions of three waves each, flown once."""
import pytest

import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

DOME = ("dome_1", "dome_2", "dome_3", "dome_4")
WAVES = {"dome_1": [1, 6, 11], "dome_2": [2, 7, 12], "dome_3": [3, 8, 13], "dome_4": [4, 9, 14]}
COUNTS = {"dome_1": 13, "dome_2": 22, "dome_3": 7, "dome_4": 10}


def _open(**flags):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["flags"].update(flags)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


# ------------------------------------------------------------------ the data
def test_the_series_is_four_chained_missions_after_the_bestiary():
    ids = [m["id"] for m in ss.MISSIONS]
    assert ids[ids.index("best_s4") + 1:ids.index("best_s4") + 5] == list(DOME)
    chain = [ss.mission_by_id(i) for i in DOME]
    assert chain[0]["need"] == "bestiary_s4"
    for prev, nxt in zip(chain, chain[1:]):
        assert nxt["need"] in prev["unlock"], nxt["id"]       # each one opens the next
    for m in chain:
        assert m["once"] and ss.mission_waves(m) == WAVES[m["id"]]
        assert m["content"] == (m["waves"][0] - 1) % 5 + 1
    assert [ss.mission_by_id(i).get("once") for i in ("ch1_sortie", "best_s2", "best_s3", "best_s4")] == [None] * 4


def test_each_wave_list_is_the_same_wave_one_level_up_each_time():
    from settings import stage_content, stage_speed_mult
    for mid, waves in WAVES.items():
        assert {stage_content(w) for w in waves} == {ss.mission_by_id(mid)["content"]}
        assert [stage_speed_mult(w) for w in waves] == pytest.approx([1.0, 1.1, 1.2])


def test_mission_waves_ignores_damaged_data():
    assert ss.mission_waves(None) == [] and ss.mission_waves({}) == []
    assert ss.mission_waves({"waves": "x"}) == []
    assert ss.mission_waves({"waves": [0, "3", None]}) == [1, 3, 1]


def test_the_old_gate_mission_is_gone_and_the_teaser_waits_for_act_two():
    assert ss.mission_by_id("ch1_gate") is None
    assert ss.mission_by_id("ch2_tease")["need"] == "act2"


# ------------------------------------------------------------------ the rules
def test_a_dome_mission_is_locked_until_the_previous_one_is_cleared():
    st = ss.default_state()
    for flag in ("bestiary_s2", "bestiary_s3"):
        st["flags"][flag] = True
    assert not ss.mission_playable(st, ss.mission_by_id("dome_1"))
    st["flags"]["bestiary_s4"] = True
    assert ss.mission_playable(st, ss.mission_by_id("dome_1"))
    assert not ss.mission_open(st, ss.mission_by_id("dome_2"))
    ss.record_result(st, "dome_1", 100, True)
    assert ss.mission_open(st, ss.mission_by_id("dome_2"))
    assert ss.mission_playable(st, ss.mission_by_id("dome_2"))
    assert not ss.mission_open(st, ss.mission_by_id("dome_3"))


def test_a_cleared_dome_mission_cannot_be_flown_again():
    st = ss.default_state()
    st["flags"]["bestiary_s4"] = True
    m = ss.mission_by_id("dome_1")
    assert ss.mission_playable(st, m)
    ss.record_result(st, "dome_1", 100, True)
    assert not ss.mission_playable(st, m)
    assert ss.mission_open(st, m)                               # still open, just done
    assert ss.mission_playable(st, m, cheat=True)               # UNLK plays everything


def test_a_failed_try_can_be_flown_again_and_the_hunts_stay_replayable():
    st = ss.default_state()
    st["flags"]["bestiary_s4"] = True
    m = ss.mission_by_id("dome_1")
    ss.record_result(st, "dome_1", 0, False)
    assert ss.mission_playable(st, m) and st["cleared"] == []
    for hunt in ("ch1_sortie", "best_s2", "best_s3", "best_s4"):
        st["flags"]["bestiary_s2"] = st["flags"]["bestiary_s3"] = True
        ss.record_result(st, hunt, 10, True)
        assert ss.mission_playable(st, ss.mission_by_id(hunt)), hunt


def test_the_whole_series_in_order_gives_one_journal_line_each():
    st = ss.create_slot(1, "NOVA", "normal")
    for mid in ("ch1_sortie", "best_s2", "best_s3", "best_s4") + DOME:
        assert ss.mission_playable(st, ss.mission_by_id(mid)), mid
        ss.record_result(st, mid, 50, True)
    assert [e["key"] for e in st["log"]][-4:] == ["story_log_dome1", "story_log_dome2", "story_log_dome3", "story_log_dome4"]
    assert not any(ss.mission_playable(st, ss.mission_by_id(m)) for m in DOME)
    assert ss.flag(st, "dome_s4")


def test_the_launch_spec_carries_the_waves():
    hub = _open(bestiary_s4=True, dome_s1=True)
    hub.map_index = [m["id"] for m in ss.MISSIONS].index("dome_2")
    spec = hub._launch_selected()
    assert spec["waves"] == [2, 7, 12] and spec["id"] == "dome_2"
    hub.map_index = 0
    assert "waves" not in hub._launch_selected()                 # a one-wave mission has none


def test_the_map_shows_a_cleared_dome_mission_as_done(run):
    import pygame, story
    from i18n import t
    hub = _open(bestiary_s4=True)
    hub.apply_result("dome_1", 100, True)
    hub.pane = "map"
    seen = []
    real = story._text

    def spy(surface, font, text, *a, **k):
        seen.append(str(text))
        return real(surface, font, text, *a, **k)

    story._text = spy
    try:
        g = run.game
        hub.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
    finally:
        story._text = real
    assert t("story_cleared") in seen
    assert any(t("story_m_dome2") in s for s in seen)


# ------------------------------------------------------------------ in the game
def _launch(g, mission_id):
    hub = _open(bestiary_s4=True, dome_s1=True, dome_s2=True, dome_s3=True)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in ss.MISSIONS].index(mission_id)
    spec = g.story._launch_selected()
    assert spec, mission_id
    g._begin_adventure(spec)
    return g


def _kill_all(g):
    for e in g.formation.enemies:
        e.kill(flash=False)


def _fly_to_next_wave(run, g, wave_i):
    """Kill the wave, then let the game fly up and set the next one up."""
    for _ in range(600):
        _kill_all(g)
        run.frames(1)
        if g.adventure is None or g.adventure.get("wave_i", 0) > wave_i:
            return
    raise AssertionError("the next wave never came")


@pytest.mark.parametrize("mission_id", DOME)
def test_the_three_waves_follow_each_other_at_their_speed(run, mission_id):
    g = _launch(run.game, mission_id)
    speeds = []
    for wave_i, number in enumerate(WAVES[mission_id]):
        assert g.adventure.get("wave_i", 0) == wave_i
        assert g.stage == number
        assert len(g.formation.enemies) == COUNTS[mission_id], (mission_id, wave_i)
        assert {e.stage for e in g.formation.enemies} == {ss.mission_by_id(mission_id)["content"]}
        speeds.append(g.formation.enemies[0].speed_mult)
        if wave_i < 2:
            _fly_to_next_wave(run, g, wave_i)
    assert speeds[1] / speeds[0] == pytest.approx(1.1) and speeds[2] / speeds[0] == pytest.approx(1.2)


def test_clearing_the_third_wave_ends_the_mission_and_unlocks_the_next(run):
    g = _launch(run.game, "dome_1")
    for wave_i in range(3):
        _fly_to_next_wave(run, g, wave_i)
    assert g.adventure is None and g.menu_screen == "story_hub"
    st = g.story.state
    assert "dome_1" in st["cleared"] and ss.flag(st, "dome_s1")
    assert not ss.mission_playable(st, ss.mission_by_id("dome_1"))
    assert ss.mission_playable(st, ss.mission_by_id("dome_2"))


def test_the_score_of_every_wave_is_banked_once_at_the_end(run):
    g = _launch(run.game, "dome_1")
    g.score = 400
    _fly_to_next_wave(run, g, 0)
    assert g.score == 400 and g.adventure is not None          # nothing is banked between waves
    g.score = 900
    _fly_to_next_wave(run, g, 1)
    _fly_to_next_wave(run, g, 2)
    assert g.story.state["credits"] == 900


def test_dying_in_a_later_wave_fails_the_whole_mission(run):
    g = _launch(run.game, "dome_1")
    g.story.state["credits"] = 1000
    _fly_to_next_wave(run, g, 0)
    g.adventure["kills"] = {"bird1": 7}
    g._end_adventure(False)
    st = g.story.state
    assert "dome_1" not in st["cleared"] and st["credits"] == 950      # -5 %
    assert ss.mission_playable(st, ss.mission_by_id("dome_1"))        # it can be tried again
    assert ss.encounters(st, "bird1") == 7


def test_the_kills_of_every_wave_count_for_the_bestiary(run):
    g = _launch(run.game, "dome_1")
    class Foe:
        stage = 1
    for _ in range(5):
        g._enemy_kill_points(Foe())
    _fly_to_next_wave(run, g, 0)
    for _ in range(4):
        g._enemy_kill_points(Foe())
    assert g.adventure["kills"] == {"bird1": 9}


def test_one_wave_missions_and_the_arcade_game_are_unchanged(run):
    g = run.game
    hub = _open()
    g.story.open_slot(1)
    g.story.map_index = 0
    g._begin_adventure(g.story._launch_selected())
    assert "waves" not in g.adventure and g.stage == 1 and len(g.formation.enemies) == 13
    _fly_to_next_wave(run, g, 0)
    assert g.adventure is None
