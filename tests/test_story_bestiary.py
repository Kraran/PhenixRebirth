"""Adventure Bestiary: enemies met, what each tier shows, the 20-kill bonus, saving."""
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


def test_tiers_open_at_1_3_5_10_and_20():
    def shown(n):
        return [k for k, v in ss.best_tiers(n).items() if v]
    assert shown(0) == []
    assert shown(1) == shown(2) == ["seen"]
    assert shown(3) == shown(4) == ["seen", "zoom"]
    assert shown(5) == shown(9) == ["seen", "zoom", "anim"]
    assert shown(10) == shown(19) == ["seen", "zoom", "anim", "text"]
    assert shown(20) == shown(500) == ["seen", "zoom", "anim", "text", "bonus"]
    assert ss.best_tiers(None) == ss.best_tiers(0) and ss.best_tiers("x") == ss.best_tiers(0)


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


def test_the_bonus_starts_with_the_20th_enemy():
    st = _state(bird1=18)
    assert ss.kill_bonus(st, "bird1", 1) == 0           # 19th
    assert ss.kill_bonus(st, "bird1", 2) == ss.BESTIARY_BONUS      # 20th
    assert ss.kill_bonus(st, "bird1", 9) == ss.BESTIARY_BONUS
    assert ss.kill_bonus(st, "bird2", 5) == 0            # another enemy: not mastered
    assert ss.kill_bonus(_state(bird1=50), "bird1", 0) == ss.BESTIARY_BONUS


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
    assert g._enemy_kill_points(_Foe(1)) == 10
    assert g._enemy_kill_points(_Foe(1)) == 10
    assert g._enemy_kill_points(_Foe(3)) == 30
    assert g.adventure["kills"] == {"bird1": 2, "garg3": 1}


def test_the_20th_enemy_of_a_kind_pays_ten_more_points(run):
    g = _start(run.game, bird1=18)
    assert g._enemy_kill_points(_Foe(1)) == 10           # 19th
    assert g._enemy_kill_points(_Foe(1)) == 20           # 20th: 10 + bonus
    assert g._enemy_kill_points(_Foe(1)) == 20
    assert g._enemy_kill_points(_Foe(2)) == 20           # another enemy, not mastered: its own price
    assert g._enemy_kill_points(_Foe(4)) == 40


def test_the_bonus_is_not_counted_twice_on_veteran_difficulty(run):
    g = _start(run.game, bird1=25)
    g.difficulty = "veteran"
    assert g._enemy_kill_points(_Foe(1)) == 20           # 10 + 10, not 10 + 10 + 10


def test_the_arcade_game_is_untouched(run):
    g = run.game
    g.adventure = None
    g.difficulty = "normal"
    assert g._enemy_kill_points(_Foe(1)) == 10 and g._enemy_kill_points(_Foe(4)) == 40
    g.difficulty = "veteran"
    assert g._enemy_kill_points(_Foe(2)) == 30
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
    assert hub.bestiary_picture("bird1", 1).get_size() == base
    assert hub.bestiary_picture("bird1", 2).get_size() == base
    assert hub.bestiary_picture("bird1", 3).get_size() == (base[0] * 2, base[1] * 2)
    assert hub.bestiary_picture("bird1", 4).get_size() == (base[0] * 2, base[1] * 2)
    # animation from the 5th: the picture changes with time, still twice as big
    seen = set()
    for i in range(40):
        hub.anim_t = i * 0.05
        img = hub.bestiary_picture("bird1", 5)
        assert img.get_size() == (base[0] * 2, base[1] * 2)
        seen.add(pygame.image.tostring(img, "RGBA"))
    assert len(seen) >= 2
    still = set()
    for i in range(40):
        hub.anim_t = i * 0.05
        still.add(pygame.image.tostring(hub.bestiary_picture("bird1", 4), "RGBA"))
    assert len(still) == 1                               # before the 5th it does not move


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

    def spy(surface, font, text, *a, **k):
        texts.append(str(text))
        return real(surface, font, text, *a, **k)

    story._text = spy
    try:
        g = run.game
        surf = pygame.Surface((1280, 720))
        hub.draw(surf, g.font, g.medium_font, g.font)
    finally:
        story._text = real
    return " | ".join(texts)


def test_the_text_comes_with_the_10th_enemy_and_the_bonus_with_the_20th(run):
    from i18n import t
    first_words = t("story_b_bird1_t").split()[0:4]
    probe = " ".join(first_words)
    for n, has_text, has_bonus in ((1, False, False), (9, False, False), (10, True, False),
                                   (19, True, False), (20, True, True)):
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
        for n in (1, 3, 5, 10, 20):
            hub = _hub(**{kind: n})
            hub.pane = "bestiary"
            hub.anim_t = 0.4
            surf = pygame.Surface((1280, 720))
            hub.draw(surf, g.font, g.medium_font, g.font)


def test_the_bestiary_texts_exist_in_every_language():
    from i18n import T, LANG_CODES, t
    keys = ["story_best", "story_tab_best", "story_hint_best", "story_best_empty",
            "story_best_count", "story_best_bonus"]
    for e in ss.BESTIARY:
        keys += [e["name"], e["text"]]
    for key in keys:
        assert set(T[key]) == set(LANG_CODES) and t(key), key
