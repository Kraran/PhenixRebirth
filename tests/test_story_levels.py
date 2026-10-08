"""Hunt missions (the Bestiary ones) go up one level after each victory: 1, 2, 3...

Level n plays the arcade stage `content + 5 * (n - 1)`: level 2 of the blues is the sixth screen of the arcade
game (speed x1.1), level 3 the eleventh (x1.2). The player only ever sees 1, 2, 3, never 1, 6, 11.
"""
import pygame
import pytest

import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

HUNTS = ("ch1_sortie", "best_s2", "best_s3", "best_s4")


def _state():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    return st


def _win(st, mission_id="ch1_sortie", kills=None):
    ss.record_result(st, mission_id, 100, True, kills if kills is not None else {"bird1": 1})


# ------------------------------------------------------------------ rules
def test_a_new_hunt_is_level_one_and_each_victory_adds_one():
    st = _state()
    for mission_id in HUNTS:
        assert ss.hunt_level(st, mission_id) == 1
    for expected in (2, 3, 4, 5):
        _win(st)
        assert ss.hunt_level(st, "ch1_sortie") == expected
    assert ss.hunt_level(st, "best_s2") == 1                     # the others do not follow


def test_a_lost_run_does_not_raise_the_level():
    st = _state()
    ss.record_result(st, "ch1_sortie", 50, False, {"bird1": 4})
    assert ss.hunt_level(st, "ch1_sortie") == 1
    _win(st)
    ss.record_result(st, "ch1_sortie", 50, False, {"bird1": 4})
    assert ss.hunt_level(st, "ch1_sortie") == 2


def test_the_level_plays_the_arcade_stage_five_levels_up():
    for mission in ss.MISSIONS:
        if mission["id"] in HUNTS:
            c = mission["content"]
            assert [ss.hunt_stage(mission, n) for n in (1, 2, 3, 4)] == [c, c + 5, c + 10, c + 15]
    assert ss.hunt_stage(None, 1) == 1 and ss.hunt_stage({"content": "x"}, "y") == 1


def test_only_the_hunts_have_a_level():
    st = _state()
    for mission_id in ("dome_1", "dome_5", "act2_gate"):
        ss.record_result(st, mission_id, 10, True, {"bird1": 3})
    assert st["mission_clears"] == {}


def test_an_old_save_counts_a_cleared_hunt_as_won_once():
    old = ss.migrate_state({"version": 4, "name": "OLD", "cleared": ["ch1_sortie", "best_s2", "dome_1"]})
    assert old["mission_clears"] == {}
    assert ss.hunt_level(old, "ch1_sortie") == ss.hunt_level(old, "best_s2") == 2
    assert ss.hunt_level(old, "best_s3") == 1
    _win(old, "ch1_sortie")                                      # the next win goes to 3, not 2 again
    assert ss.hunt_level(old, "ch1_sortie") == 3


def test_the_levels_survive_save_and_load_and_junk_is_ignored(tmp_path):
    st = _state()
    _win(st)
    _win(st)
    _win(st, "best_s3", {"garg3": 1})
    path = str(tmp_path / "s.json")
    ss.save_state(path, st)
    back = ss.load_state(path)
    assert back["mission_clears"] == {"ch1_sortie": 2, "best_s3": 1}
    assert ss.hunt_level(back, "ch1_sortie") == 3
    odd = ss.migrate_state({"version": 4, "mission_clears": {"ch1_sortie": "x", "best_s2": -4, "dome_1": 5,
                                                              "ghost": 2, "best_s3": 2}})
    assert odd["mission_clears"] == {"ch1_sortie": 0, "best_s2": 0, "best_s3": 2}
    assert ss.hunt_level({"mission_clears": "broken"}, "ch1_sortie") == 1


def test_a_new_slot_starts_without_any_level():
    assert ss.default_state()["mission_clears"] == {}
    assert ss.create_slot(2, "A", "normal")["mission_clears"] == {}


# ------------------------------------------------------------------ the journal
def test_the_journal_shows_the_level_under_each_played_hunt():
    from i18n import t
    st = _state()
    _win(st)
    _win(st)
    _win(st, "best_s2", {"bird2": 3})
    lines = [ss.log_text(e, t) for e in ss.journal_entries(st)[1:]]
    assert lines == [t("story_log_sortie"), t("story_log_level").format(n=3), t("story_log_kills").format(n=2),
                     t("story_log_best2"), t("story_log_level").format(n=2), t("story_log_kills").format(n=3)]
    assert "6" not in lines[1] and "11" not in lines[1]            # 1, 2, 3... never the arcade stage


def test_the_level_line_is_a_comment_and_not_selectable(run):
    import story
    st = _state()
    _win(st)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "log"
    entries = hub.log_entries()
    assert {"level": 2, "mission": "ch1_sortie"} in entries
    drawn = []
    real = story.pygame.draw.rect

    def spy(surface, color, rect, *a, **k):
        if tuple(color)[:3] == (255, 210, 80):
            drawn.append(pygame.Rect(rect).y)
        return real(surface, color, rect, *a, **k)

    story.pygame.draw.rect = spy
    try:
        g = run.game
        for steps in (0, 1, 2, 3):
            drawn.clear()
            for _ in range(steps):
                hub.nav_v(1)
            hub.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
            assert len(drawn) == 1                                # the cursor stays on the intro line
    finally:
        story.pygame.draw.rect = real


# ------------------------------------------------------------------ the map and the game
def _texts(hub, run):
    import story
    seen = []
    real, real_fit = story._text, story._text_fit

    def spy(surface, font, text, *a, **k):
        seen.append(str(text))
        return real(surface, font, text, *a, **k)

    def spy_fit(surface, font, text, *a, **k):
        seen.append(str(text))
        return real_fit(surface, font, text, *a, **k)

    story._text, story._text_fit = spy, spy_fit
    try:
        g = run.game
        hub.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
    finally:
        story._text, story._text_fit = real, real_fit
    return seen


def _hub(st):
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "map"
    return hub


def test_the_map_writes_the_level_next_to_each_open_hunt(run):
    from i18n import t
    st = _state()
    _win(st)
    _win(st)
    texts = _texts(_hub(st), run)
    assert any(x.endswith(t("story_level").format(n=3)) for x in texts)       # the first sortie, now level 3
    assert not any("LEVEL 6" in x or "NIVEAU 6" in x or "NIVEAU 11" in x for x in texts)


def test_a_fresh_map_says_level_one(run):
    from i18n import t
    texts = _texts(_hub(_state()), run)
    assert any(x.endswith(t("story_level").format(n=1)) for x in texts)


def _launch(g, st, mission_id):
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.cheat_unlock = True                                  # the order of the missions is not the point here
    g.story.map_index = [m["id"] for m in ss.MISSIONS].index(mission_id)
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    return spec


def test_level_one_plays_the_plain_mission(run):
    g = run.game
    spec = _launch(g, _state(), "ch1_sortie")
    assert spec["level"] == 1 and "waves" not in spec
    assert g.stage == 1 and {e.stage for e in g.formation.enemies} == {1}
    assert len(g.formation.enemies) == 13


@pytest.mark.parametrize("wins,stage,content,speed", [(1, 6, 1, 1.1), (2, 11, 1, 1.2), (3, 16, 1, 1.3)])
def test_higher_levels_play_the_same_enemies_faster(run, wins, stage, content, speed):
    g = run.game
    st = _state()
    for _ in range(wins):
        _win(st)
    spec = _launch(g, st, "ch1_sortie")
    assert spec["level"] == wins + 1 and spec["waves"] == [stage]
    assert g.stage == stage                                       # the arcade stage behind the level
    assert {e.stage for e in g.formation.enemies} == {content}
    assert len(g.formation.enemies) == 13
    base = {round(e.speed_mult, 6) for e in g.formation.enemies}
    assert base == {round(speed * g.difficulty_speed_mult() * float(spec.get("speed") or 1.0), 6)}


def test_each_hunt_keeps_its_own_enemy_at_every_level(run):
    g = run.game
    for mission_id, kind in (("best_s2", 2), ("best_s3", 3), ("best_s4", 4)):
        st = _state()
        _win(st, mission_id, {})
        _win(st, mission_id, {})
        _launch(g, st, mission_id)
        assert {e.stage for e in g.formation.enemies} == {kind}, mission_id
        assert g.stage == kind + 10


def test_winning_a_higher_level_goes_up_again_through_the_game(run):
    g = run.game
    st = _state()
    _win(st)
    _launch(g, st, "ch1_sortie")
    assert g.adventure["level"] == 2
    g.adventure["kills"] = {"bird1": 13}
    g.score = 130
    g._end_adventure(True)
    assert ss.hunt_level(g.story.state, "ch1_sortie") == 3
    assert g.story.state["mission_clears"]["ch1_sortie"] == 2


def test_a_death_at_level_two_keeps_level_two(run):
    g = run.game
    st = _state()
    _win(st)
    _launch(g, st, "ch1_sortie")
    g.adventure["kills"] = {"bird1": 5}
    g._end_adventure(False)
    assert ss.hunt_level(g.story.state, "ch1_sortie") == 2


def test_the_hud_shows_the_level_as_1_2_3(run):
    from i18n import t
    g = run.game
    st = _state()
    _win(st)
    _win(st)
    _launch(g, st, "ch1_sortie")
    seen = []
    import text_cache as tc_mod
    orig = tc_mod.TextCache.get

    def spy(self, font, text, *a, **k):
        seen.append(str(text))
        return orig(self, font, text, *a, **k)

    tc_mod.TextCache.get = spy
    try:
        run.frames(2, 1 / 60)
    finally:
        tc_mod.TextCache.get = orig
    level = t("story_level").format(n=3)
    assert any(level in x for x in seen), seen[:20]
    assert not any("11" in x and level in x for x in seen)
