"""Adventure Bestiary: enemies met, what each tier shows (1/50/100/150/200), the bonus, hunt missions, saving."""
import pygame
import pytest

import bestiary_art
import story_state as ss
import update_play
from settings import ENEMY_VETERAN_BONUS
from story import StoryHub, PANES
from test_smoke import run  # noqa: F401  (fixture)


def _state(**counts):
    st = ss.default_state()
    st["bestiary"] = dict(counts)
    return st


# ------------------------------------------------------------------ rules
def test_enemy_kind_follows_the_content_stage():
    assert [ss.enemy_kind(s) for s in (1, 2, 3, 4)] == ["bird1", "bird2", "garg3", "garg4"]
    assert ss.enemy_kind(9) == "garg4" and ss.enemy_kind(0) == "bird1" and ss.enemy_kind("x") == "bird1"
    assert {e["stage"]: e["id"] for e in ss.BESTIARY} == {1: "bird1", 2: "bird2", 3: "garg3", 4: "garg4"}


def _shown(n, boss=False):
    return [k for k, v in ss.best_tiers(n, boss).items() if v]


def test_common_tiers_open_at_1_50_100_150_and_200():
    assert ss.BEST_TIERS_COMMON == (1, 50, 100, 150, 200)
    assert _shown(0) == []
    assert _shown(1) == _shown(49) == ["seen"]
    assert _shown(50) == _shown(99) == ["seen", "zoom"]
    assert _shown(100) == _shown(149) == ["seen", "zoom", "anim"]
    assert _shown(150) == _shown(199) == ["seen", "zoom", "anim", "text"]
    assert _shown(200) == _shown(5000) == ["seen", "zoom", "anim", "text", "bonus"]
    assert ss.best_tiers(None) == ss.best_tiers(0) and ss.best_tiers("x") == ss.best_tiers(0)


def test_boss_tiers_open_at_1_2_3_5_and_10():
    assert ss.BEST_TIERS_BOSS == (1, 2, 3, 5, 10)
    assert _shown(0, True) == []
    assert _shown(1, True) == ["seen"]
    assert _shown(2, True) == ["seen", "zoom"]
    assert _shown(3, True) == _shown(4, True) == ["seen", "zoom", "anim"]
    assert _shown(5, True) == _shown(9, True) == ["seen", "zoom", "anim", "text"]
    assert _shown(10, True) == _shown(99, True) == ["seen", "zoom", "anim", "text", "bonus"]


def test_only_enemies_already_destroyed_are_listed():
    assert ss.bestiary_entries(_state()) == []
    got = ss.bestiary_entries(_state(garg3=2, bird1=7))
    assert [(e["id"], n) for e, n in got] == [("bird1", 7), ("garg3", 2)]     # listing order, not kill order


def test_kills_are_added_and_never_lost():
    st = ss.default_state()
    ss.record_kills(st, {"bird1": 4})
    ss.record_kills(st, {"bird1": 3, "garg4": 1})
    assert st["bestiary"] == {"bird1": 7, "garg4": 1}
    ss.record_kills(st, {"dragon": 5, "bird2": -4, "garg3": "x"})                # unknown, negative, damaged
    ss.record_kills(st, None)
    ss.record_kills(st, "nope")
    assert st["bestiary"] == {"bird1": 7, "garg4": 1, "bird2": 0, "garg3": 0}
    assert ss.encounters(st, "bird1") == 7 and ss.encounters(st, "ghost") == 0


def test_the_bonus_starts_with_the_200th_enemy():
    st = _state(bird1=198)
    assert ss.kill_bonus(st, "bird1", 1) == 0           # 199th
    assert ss.kill_bonus(st, "bird1", 2) == ss.BESTIARY_BONUS      # 200th
    assert ss.kill_bonus(st, "bird1", 9) == ss.BESTIARY_BONUS
    assert ss.kill_bonus(st, "bird2", 5) == 0            # another enemy: not mastered
    assert ss.kill_bonus(_state(bird1=500), "bird1", 0) == ss.BESTIARY_BONUS
    assert ss.kill_bonus(_state(bird1=20), "bird1", 0) == 0     # the old threshold pays nothing
    assert ss.kill_bonus(st, "ghost", 500) == 0


def test_a_boss_pays_a_thousand_more_from_its_10th_defeat(monkeypatch):
    boss = {"id": "boss_x", "stage": 5, "name": "story_b_bird1", "text": "story_b_bird1_t", "boss": True}
    monkeypatch.setattr(ss, "BESTIARY", ss.BESTIARY + [boss])
    assert ss.is_boss("boss_x") and not ss.is_boss("bird1")
    assert ss.BOSS_BONUS == 1000 and ss.bestiary_bonus("boss_x") == 1000
    assert ss.bestiary_bonus("bird1") == ss.BESTIARY_BONUS
    st = _state(boss_x=8)
    assert ss.kill_bonus(st, "boss_x", 1) == 0           # 9th
    assert ss.kill_bonus(st, "boss_x", 2) == 1000        # 10th
    ss.record_kills(st, {"boss_x": 2})
    assert ss.encounters(st, "boss_x") == 10
    assert [e["id"] for e, n in ss.bestiary_entries(st)] == ["boss_x"]


def test_the_bonus_is_the_veteran_bonus_of_the_arcade_game():
    assert ss.BESTIARY_BONUS == ENEMY_VETERAN_BONUS == 10


def test_a_result_adds_the_kills_whatever_the_outcome():
    for cleared, mode in ((True, "normal"), (False, "normal"), (False, "veteran")):
        st = ss.default_state()
        st["mode"] = mode
        ss.record_result(st, "ch1_sortie", 100, cleared, {"bird1": 9})
        assert st["bestiary"] == {"bird1": 9}, (cleared, mode)


def test_a_result_without_kills_changes_nothing_in_the_bestiary():
    st = ss.default_state()
    ss.record_result(st, "ch1_sortie", 100, True)
    assert st["bestiary"] == {}
    credits = st["credits"]
    ss.record_result(st, "ch1_sortie", 50, True, {"bird1": 3})
    assert st["credits"] == credits + 50                  # kills never change the credits themselves


def test_old_saves_get_an_empty_bestiary_and_new_ones_keep_theirs():
    old = ss.migrate_state({"version": 4, "credits": 12})
    assert old["bestiary"] == {}
    st = _state(bird1=12, garg4=3)
    again = ss.migrate_state(__import__("json").loads(__import__("json").dumps(st)))
    assert again["bestiary"] == {"bird1": 12, "garg4": 3}
    bad = ss.migrate_state({"version": 4, "bestiary": {"bird1": "lots", "x": 4, "bird2": 2.9}})
    assert bad["bestiary"] == {"bird1": 0, "bird2": 2}
    assert ss.migrate_state({"version": 4, "bestiary": [1, 2]})["bestiary"] == {}


def test_the_bestiary_is_saved_in_the_slot_file(tmp_path):
    path = str(tmp_path / "story_1.json")
    st = _state(bird2=6)
    ss.save_state(path, st)
    assert ss.load_state(path)["bestiary"] == {"bird2": 6}


# ------------------------------------------------------------------ the game
class _Foe:
    def __init__(self, stage):
        self.stage = stage


def _start(g, stage_mission=0, **counts):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["bestiary"] = dict(counts)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = stage_mission
    g._begin_adventure(g.story._launch_selected())
    return g


def test_destroyed_enemies_are_counted_during_the_mission(run):
    g = _start(run.game)
    assert g._enemy_kill_points(_Foe(1)) == 20          # 10 + the +10 of level 1
    assert g._enemy_kill_points(_Foe(1)) == 20
    assert g._enemy_kill_points(_Foe(3)) == 40
    assert g.adventure["kills"] == {"bird1": 2, "garg3": 1}


def test_the_200th_enemy_of_a_kind_pays_ten_more_points(run):
    g = _start(run.game, bird1=198)
    assert g._enemy_kill_points(_Foe(1)) == 20           # 199th
    assert g._enemy_kill_points(_Foe(1)) == 30           # 200th: 20 + bonus
    assert g._enemy_kill_points(_Foe(1)) == 30
    assert g._enemy_kill_points(_Foe(2)) == 30           # another enemy, not mastered: its own price
    assert g._enemy_kill_points(_Foe(4)) == 50


def test_the_bonus_is_not_counted_twice_on_veteran_difficulty(run):
    g = _start(run.game, bird1=250)
    g.difficulty = "veteran"
    assert g._enemy_kill_points(_Foe(1)) == 30           # 20 + 10, not 20 + 10 + 10


def test_the_arcade_game_is_untouched(run):
    g = run.game
    g.adventure = None
    g.difficulty = "normal"
    assert g._enemy_kill_points(_Foe(1)) == 20 and g._enemy_kill_points(_Foe(4)) == 50
    g.difficulty = "veteran"
    assert g._enemy_kill_points(_Foe(2)) == 40
    assert g.adventure is None                            # nothing recorded outside the Adventure


def test_a_real_shot_counts_for_the_bestiary(run):
    g = _start(run.game)
    run.frames(5)
    foe = next(e for e in g.formation.get_hittable_enemies())
    g.player.shots = [{"x": foe.x, "y": foe.y, "resolved": False, "flame": False, "prev_y": foe.y}]
    update_play.player_bullets_vs_enemies(g)
    assert g.adventure["kills"].get("bird1") == 1
    assert g.score >= 10


def test_the_mission_end_saves_the_kills_and_returns_to_the_map(run):
    g = _start(run.game)
    g.adventure["kills"] = {"bird1": 13}
    g.score = 130
    g._end_adventure(True)
    assert g.story.state["bestiary"] == {"bird1": 13}
    again = StoryHub()
    again.open_slot(1)
    assert again.state["bestiary"] == {"bird1": 13}


def test_dying_keeps_the_kills_too(run):
    g = _start(run.game)
    g.adventure["kills"] = {"bird1": 6}
    g._end_adventure(False)
    assert g.story.state["bestiary"] == {"bird1": 6}


def test_leaving_a_mission_by_choice_records_nothing(run):
    g = _start(run.game, bird1=2)
    run.frames(5)
    g.adventure["kills"] = {"bird1": 9}
    g._quit_to_menu()
    assert g.story.state["bestiary"] == {"bird1": 2}


def test_leaving_after_the_win_keeps_the_kills(run):
    g = _start(run.game)
    run.frames(5)
    g.adventure["kills"] = {"bird1": 13}
    g.score = 130
    g.stage_transition = "fly_up"
    g._quit_to_menu()
    assert g.story.state["bestiary"] == {"bird1": 13}


# ------------------------------------------------------------------ the screen
def _hub(**counts):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["bestiary"] = dict(counts)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


def test_the_bestiary_is_left_of_the_journal():
    assert PANES.index("bestiary") + 1 == PANES.index("log")
    hub = _hub()
    hub.pane = "log"
    hub.nav_h(-1)
    assert hub.pane == "bestiary"
    hub.nav_h(-1)
    assert hub.pane == "bestiary"                        # first screen: it stops there
    hub.nav_h(1)
    assert hub.pane == "log"


def test_the_cursor_stays_inside_the_list():
    hub = _hub(bird1=3, garg3=1)
    hub.pane = "bestiary"
    hub.nav_v(-1)
    assert hub.best_index == 0
    for _ in range(9):
        hub.nav_v(1)
    assert hub.best_index == 1
    empty = _hub()
    empty.pane = "bestiary"
    empty.nav_v(1)
    assert empty.best_index == 0


def test_the_picture_is_small_then_twice_as_big_then_animated(run):
    hub = _hub()
    base = bestiary_art.still("bird1").get_size()
    big = (base[0] * 2, base[1] * 2)
    assert hub.bestiary_picture("bird1", 1).get_size() == base
    assert hub.bestiary_picture("bird1", 49).get_size() == base
    assert hub.bestiary_picture("bird1", 50).get_size() == big
    assert hub.bestiary_picture("bird1", 99).get_size() == big
    # animation from the 100th: the picture changes with time, still twice as big
    seen = set()
    for i in range(40):
        hub.anim_t = i * 0.05
        img = hub.bestiary_picture("bird1", 100)
        assert img.get_size() == big
        seen.add(pygame.image.tostring(img, "RGBA"))
    assert len(seen) >= 2
    still = set()
    for i in range(40):
        hub.anim_t = i * 0.05
        still.add(pygame.image.tostring(hub.bestiary_picture("bird1", 99), "RGBA"))
    assert len(still) == 1                               # before the 100th it does not move


def test_a_boss_picture_follows_the_boss_table(run, monkeypatch):
    boss = {"id": "bird1", "stage": 1, "name": "story_b_bird1", "text": "story_b_bird1_t", "boss": True}
    monkeypatch.setattr(ss, "BESTIARY", [boss])
    hub = _hub()
    base = bestiary_art.still("bird1").get_size()
    assert hub.bestiary_picture("bird1", 1).get_size() == base
    assert hub.bestiary_picture("bird1", 2).get_size() == (base[0] * 2, base[1] * 2)


def test_gargoyles_beat_their_wings(run):
    hub = _hub()
    frames = {pygame.image.tostring(bestiary_art.animated("garg3", i * 0.03), "RGBA") for i in range(60)}
    assert len(frames) == 2


def test_every_enemy_has_a_picture_of_a_sensible_size(run):
    for kind in bestiary_art.known_kinds():
        w, h = bestiary_art.still(kind).get_size()
        assert 30 <= w <= 200 and 30 <= h <= 100, (kind, w, h)


def _drawn_texts(hub, run):
    import story
    texts = []
    real = story._text

    real_fit = story._text_fit

    def spy(surface, font, text, *a, **k):
        texts.append(str(text))
        return real(surface, font, text, *a, **k)

    def spy_fit(surface, font, text, *a, **k):
        texts.append(str(text))
        return real_fit(surface, font, text, *a, **k)

    story._text = spy
    story._text_fit = spy_fit
    try:
        g = run.game
        surf = pygame.Surface((1280, 720))
        hub.draw(surf, g.font, g.medium_font, g.font)
    finally:
        story._text = real
        story._text_fit = real_fit
    return " | ".join(texts)


def test_the_text_comes_with_the_150th_enemy_and_the_bonus_with_the_200th(run):
    from i18n import t
    first_words = t("story_b_bird1_t").split()[0:4]
    probe = " ".join(first_words)
    for n, has_text, has_bonus in ((1, False, False), (149, False, False), (150, True, False),
                                   (199, True, False), (200, True, True)):
        hub = _hub(bird1=n)
        hub.pane = "bestiary"
        shown = _drawn_texts(hub, run)
        assert (first_words[0] in shown and first_words[1] in shown) == has_text, (n, shown)
        assert (t("story_best_bonus").split("{")[0] in shown) == has_bonus, n
        assert t("story_best_count").format(n=n) in shown


def test_an_enemy_not_met_yet_is_not_shown(run):
    from i18n import t
    hub = _hub(bird1=4)
    hub.pane = "bestiary"
    shown = _drawn_texts(hub, run)
    assert t("story_b_bird1") in shown
    for other in ("story_b_bird2", "story_b_garg3", "story_b_garg4"):
        assert t(other) not in shown


def test_the_empty_bestiary_says_so(run):
    from i18n import t
    hub = _hub()
    hub.pane = "bestiary"
    assert t("story_best_empty") in _drawn_texts(hub, run)


def test_every_tier_of_every_enemy_draws(run):
    g = run.game
    for kind in bestiary_art.known_kinds():
        for n in (1, 50, 100, 150, 200):
            hub = _hub(**{kind: n})
            hub.pane = "bestiary"
            hub.anim_t = 0.4
            surf = pygame.Surface((1280, 720))
            hub.draw(surf, g.font, g.medium_font, g.font)


def test_the_bestiary_texts_exist_in_every_language():
    from i18n import T, LANG_CODES, t
    keys = ["story_best", "story_tab_best", "story_hint_best", "story_best_empty",
            "story_best_count", "story_best_bonus", "story_best_bonus_boss", "story_replay",
            "story_log_kills", "story_log_kill_1"]
    for e in ss.BESTIARY:
        keys += [e["name"], e["text"]]
    for key in keys:
        assert set(T[key]) == set(LANG_CODES) and t(key), key


# ------------------------------------------------------------------ names fit the list
def test_every_name_fits_inside_its_row(run):
    """The names were too big (the longest one went out of its frame)."""
    import story
    from i18n import t, LANG_CODES, set_lang
    g = run.game
    list_w = 400
    for code in LANG_CODES:
        set_lang(code)
        try:
            for e in ss.BESTIARY:
                img = story._text_fit(pygame.Surface((1280, 720)), g.font, "> " + t(e["name"]),
                                      (255, 255, 255), 40, 0, list_w - 20, scale=0.8)
                assert img.get_width() <= list_w - 20, (code, e["id"])
        finally:
            set_lang("fr")


def test_the_longest_name_is_drawn_smaller_than_before(run):
    import story
    g = run.game
    surf = pygame.Surface((1280, 720))
    full = g.font.size("> GARGOUILLE SOMBRE")[0]
    img = story._text_fit(surf, g.font, "> GARGOUILLE SOMBRE", (255, 255, 255), 40, 0, 380, scale=0.8)
    assert img.get_width() < full * 0.85 and img.get_width() <= 380
    # a text that already fits is only reduced by the scale, never enlarged
    tiny = story._text_fit(surf, g.font, "A", (255, 255, 255), 40, 0, 380, scale=1.0)
    assert tiny.get_size() == g.font.render("A", True, (255, 255, 255)).get_size()


# ------------------------------------------------------------------ hunt missions
HUNTS = ("ch1_sortie", "best_s2", "best_s3", "best_s4")


def test_the_four_bestiary_missions_are_hunts_each_with_its_enemy():
    hunts = [m for m in ss.MISSIONS if ss.is_hunt(m)]
    assert [m["id"] for m in hunts] == list(HUNTS)
    assert [ss.enemy_kind(m["content"]) for m in hunts] == ["bird1", "bird2", "garg3", "garg4"]
    assert not ss.is_hunt(ss.mission_by_id("dome_1")) and not ss.is_hunt(ss.mission_by_id("ch2_tease"))
    assert not ss.is_hunt(None) and not ss.is_hunt(ss.mission_by_id("nope"))


def test_a_hunt_can_be_flown_again_and_again():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    for run_no in range(4):
        assert ss.mission_playable(st, ss.mission_by_id("ch1_sortie"))
        res = ss.record_result(st, "ch1_sortie", 100, True, {"bird1": 10})
        assert res["first"] == (run_no == 0)
    assert st["credits"] == 400 and st["cleared"] == ["ch1_sortie"]
    assert len(st["log"]) == 1                            # the first-clear line is written once
    assert ss.mission_playable(st, ss.mission_by_id("ch1_sortie"))


def test_the_total_of_kills_adds_up_over_all_the_runs_win_or_lose():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.record_result(st, "ch1_sortie", 100, True, {"bird1": 13})
    ss.record_result(st, "ch1_sortie", 0, False, {"bird1": 5})
    ss.record_result(st, "ch1_sortie", 90, True, {"bird1": 12})
    assert ss.mission_total_kills(st, "ch1_sortie") == 30
    assert ss.mission_total_kills(st, "best_s2") == 0
    assert ss.encounters(st, "bird1") == 30


def test_each_hunt_keeps_its_own_total():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.record_result(st, "ch1_sortie", 100, True, {"bird1": 13})
    ss.record_result(st, "best_s2", 100, True, {"bird2": 22})
    ss.record_result(st, "ch1_sortie", 100, True, {"bird1": 7})
    assert st["mission_kills"] == {"ch1_sortie": 20, "best_s2": 22}


def test_only_hunts_keep_a_total_and_odd_kills_are_ignored():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.record_result(st, "dome_1", 100, True, {"bird1": 13})
    assert st["mission_kills"] == {}                      # not a hunt
    assert ss.encounters(st, "bird1") == 13               # the Bestiary still counts them
    ss.record_result(st, "ch1_sortie", 0, False, {"bird1": -3, "dragon": 9, "bird2": "x"})
    ss.record_result(st, "ch1_sortie", 0, False, None)
    ss.record_mission_kills(st, "ch1_sortie", "nope")
    assert st["mission_kills"] == {}
    assert ss.mission_total_kills({"mission_kills": "damaged"}, "ch1_sortie") == 0


def test_the_journal_shows_the_total_under_the_mission_line():
    from i18n import t
    st = ss.create_slot(1, "NOVA", "normal")
    assert ss.journal_entries(st) == [{"intro": True}]
    ss.record_result(st, "ch1_sortie", 100, True, {"bird1": 13})
    ss.record_result(st, "best_s2", 100, True, {"bird2": 22})
    ss.record_result(st, "ch1_sortie", 100, True, {"bird1": 7})
    entries = ss.journal_entries(st)
    assert [ss.log_text(e, t) for e in entries[1:]] == [
        t("story_log_sortie"), t("story_log_level").format(n=3), t("story_log_kills").format(n=20),
        t("story_log_best2"), t("story_log_level").format(n=2), t("story_log_kills").format(n=22)]
    assert "20" in ss.log_text(entries[3], t)
    assert st["log"] == [{"key": "story_log_sortie"}, {"key": "story_log_best2"}]   # saved lines unchanged


def test_the_journal_says_one_enemy_in_the_singular():
    from i18n import t
    st = ss.create_slot(1, "NOVA", "normal")
    ss.record_result(st, "ch1_sortie", 100, True, {"bird1": 1})
    assert ss.log_text(ss.journal_entries(st)[3], t) == t("story_log_kill_1").format(n=1)


def test_no_kills_no_total_line_and_the_gate_has_none():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.record_result(st, "ch1_sortie", 100, True, {})
    assert len(ss.journal_entries(st)) == 3               # intro, the line, the level (no kills line)
    ss.record_result(st, "best_s2", 100, True, {"bird2": 4})
    ss.record_result(st, "best_s3", 100, True, {"garg3": 2})
    ss.record_result(st, "best_s4", 100, True, {"garg4": 1})
    ss.record_result(st, "dome_1", 100, True, {"bird1": 9})
    kills = [e for e in ss.journal_entries(st) if isinstance(e, dict) and "kills" in e]
    assert [(e["mission"], e["kills"]) for e in kills] == [("best_s2", 4), ("best_s3", 2), ("best_s4", 1)]


def test_the_totals_survive_save_and_load_and_old_saves_start_at_zero(tmp_path):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.record_result(st, "ch1_sortie", 100, True, {"bird1": 13})
    path = str(tmp_path / "s.json")
    ss.save_state(path, st)
    assert ss.load_state(path)["mission_kills"] == {"ch1_sortie": 13}
    old = ss.migrate_state({"version": 4, "name": "OLD", "cleared": ["ch1_sortie"],
                            "log": [{"key": "story_log_sortie"}], "bestiary": {"bird1": 40}})
    assert old["mission_kills"] == {} and ss.journal_entries(old)[1:] == [{"key": "story_log_sortie"},
                                                                          {"level": 2, "mission": "ch1_sortie"}]
    odd = ss.migrate_state({"version": 4, "mission_kills": {"ch1_sortie": "x", "dome_1": 5, "ghost": 3, 7: 1}})
    assert odd["mission_kills"] == {"ch1_sortie": 0}


def test_a_played_hunt_writes_its_total_in_the_journal(run):
    from i18n import t
    g = _start(run.game)
    g.adventure["kills"] = {"bird1": 13}
    g.score = 130
    g._end_adventure(True)
    g.story.state["log"]                                  # the first clear wrote its line
    g._begin_adventure(g.story._launch_selected())        # the same mission again
    g.adventure["kills"] = {"bird1": 9}
    g._end_adventure(False)
    hub = g.story
    text = [ss.log_text(e, t) for e in hub.log_entries()]
    assert t("story_log_kills").format(n=22) in text
    hub.pane = "log"
    assert t("story_log_kills").format(n=22) in _drawn_texts(hub, run)


def test_the_map_calls_a_hunt_replayable(run):
    from i18n import t
    g = _start(run.game)
    g.adventure["kills"] = {"bird1": 3}
    g.score = 30
    g._end_adventure(True)
    hub = g.story
    hub.pane = "map"
    shown = _drawn_texts(hub, run)
    assert t("story_replay") in shown
