"""The boss saucer joins the Bestiary once the pilot has destroyed it (the end of Act 1)."""
import pygame
import pytest

import bestiary_art
import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)


def _state(**counts):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["bestiary"] = dict(counts)
    ss.save_state(ss.story_path(1), st)
    return st


def _start(g, mission_id="act2_gate", **counts):
    _state(**counts)
    g.story.open_slot(1)
    g.story.cheat_unlock = True
    g.story.map_index = [m["id"] for m in ss.MISSIONS].index(mission_id)
    g._begin_adventure(g.story._launch_selected())
    return g


# --- the entry ---
def test_the_boss_is_a_boss_entry_listed_last():
    entry = ss.BESTIARY[-1]
    assert entry["id"] == "boss" and entry["boss"] is True and ss.is_boss("boss")
    assert ss.bestiary_bonus("boss") == ss.BOSS_BONUS == 1000
    assert not any(ss.is_boss(e["id"]) for e in ss.BESTIARY[:-1])


def test_the_boss_is_hidden_until_it_is_destroyed():
    st = _state(bird1=3)
    assert [e["id"] for e, n in ss.bestiary_entries(st)] == ["bird1"]
    st = _state(bird1=3, boss=1)
    assert [e["id"] for e, n in ss.bestiary_entries(st)] == ["bird1", "boss"]


def test_the_boss_follows_the_short_table():
    for n, shown in ((1, ["seen"]), (2, ["seen", "zoom"]), (3, ["seen", "zoom", "anim"]),
                     (5, ["seen", "zoom", "anim", "text"]), (10, ["seen", "zoom", "anim", "text", "bonus"])):
        assert [k for k, v in ss.best_tiers(n, ss.is_boss("boss")).items() if v] == shown


def test_the_boss_has_a_name_and_a_text_in_every_language():
    import i18n
    entry = ss.BESTIARY[-1]
    for lang in ("fr", "en", "es", "de"):
        old = i18n.get_lang()
        i18n.set_lang(lang)
        try:
            assert i18n.t(entry["name"]) not in ("", entry["name"])
            assert len(i18n.t(entry["text"])) > 60
        finally:
            i18n.set_lang(old)


# --- counting its destruction ---
def test_destroying_the_boss_in_a_mission_is_counted_for_the_bestiary(run):
    g = _start(run.game)
    g.stage = 15                                   # the boss of the gate mission: +20 for its level
    assert g._boss_kill_points() == 520
    assert g.adventure["kills"] == {"boss": 1}
    g._boss_kill_points()
    assert g.adventure["kills"] == {"boss": 2}


def test_the_boss_pays_a_thousand_more_from_its_10th_defeat(run):
    g = _start(run.game, boss=8)
    g.stage = 5
    assert g._boss_kill_points() == 500            # 9th
    assert g._boss_kill_points() == 1500           # 10th: 500 + 1000
    assert g._boss_kill_points() == 1500


def test_the_veteran_boss_bonus_adds_to_the_mastery_bonus(run):
    g = _start(run.game, boss=9)
    g.stage = 5
    g.difficulty = "veteran"
    assert g._boss_kill_points() == 1000 + 1000


def test_the_arcade_boss_is_untouched(run):
    g = run.game
    g.adventure = None
    g.difficulty = "normal"
    assert g._boss_kill_points() == 500
    g.difficulty = "veteran"
    assert g._boss_kill_points() == 1000
    assert g.adventure is None


def test_the_saved_bestiary_gets_the_boss_when_the_mission_ends(run):
    st = _state(bird1=5)
    ss.record_kills(st, {"boss": 1, "bird1": 2})
    assert ss.encounters(st, "boss") == 1 and ss.encounters(st, "bird1") == 7


def test_shooting_the_boss_core_registers_it_in_the_game(run):
    """The real shot path: a bullet that kills the core goes to the Bestiary."""
    from types import SimpleNamespace
    import update_play
    g = _start(run.game)
    g.stage = 5
    g.score = 0
    ship = g.player
    ship.get_bullet_rects = lambda: [(0, pygame.Rect(600, 300, 6, 14))]
    ship.destroy_bullet = lambda *a, **k: None
    core = SimpleNamespace(x=600, y=300, kill=lambda: None)
    g.boss_saucer = SimpleNamespace(alive=True, hit_bullet=lambda rect: ("boss", core), flag_ports_pair=False)
    update_play.player_bullets_vs_enemies(g)
    assert g.adventure["kills"] == {"boss": 1}
    assert g.score == 500


# --- the pictures ---
def test_the_boss_has_a_still_picture_and_a_loop(run):
    still = bestiary_art.still("boss")
    assert still.get_width() > 100
    frames = {pygame.image.tostring(bestiary_art.animated("boss", i / bestiary_art.BOSS_FPS), "RGBA")
              for i in range(bestiary_art.BOSS_FRAMES)}
    assert len(frames) > 4                            # the core flickers, the band scrolls
    assert (pygame.image.tostring(bestiary_art.animated("boss", 0.0), "RGBA")
            == pygame.image.tostring(bestiary_art.animated("boss", bestiary_art.BOSS_FRAMES / bestiary_art.BOSS_FPS), "RGBA"))


def test_the_twice_as_big_boss_is_drawn_at_that_size_not_stretched(run):
    hub = StoryHub()
    one = hub.bestiary_picture("boss", 1)
    two = hub.bestiary_picture("boss", 2)
    assert two.get_width() == one.get_width() * 2 and two.get_height() == one.get_height() * 2
    assert two is bestiary_art.big("boss")            # the real big picture, not a scaled copy
    small = pygame.transform.scale(one, two.get_size())
    assert pygame.image.tostring(two, "RGBA") != pygame.image.tostring(small, "RGBA")


def test_the_boss_picture_animates_from_its_third_defeat(run):
    hub = StoryHub()
    seen = set()
    for i in range(bestiary_art.BOSS_FRAMES):
        hub.anim_t = i / bestiary_art.BOSS_FPS
        seen.add(pygame.image.tostring(hub.bestiary_picture("boss", 2), "RGBA"))
    assert len(seen) == 1                             # still at 2
    for i in range(bestiary_art.BOSS_FRAMES):
        hub.anim_t = i / bestiary_art.BOSS_FPS
        seen.add(pygame.image.tostring(hub.bestiary_picture("boss", 3), "RGBA"))
    assert len(seen) > 4                              # alive at 3


def test_the_ordinary_enemies_keep_their_stretched_pictures(run):
    hub = StoryHub()
    one, two = hub.bestiary_picture("bird1", 1), hub.bestiary_picture("bird1", 50)
    assert two.get_size() == (one.get_width() * 2, one.get_height() * 2)
    assert bestiary_art.big("bird1") is None


def test_the_boss_screen_draws_with_text_and_bonus(run):
    g = run.game
    _state(boss=10)
    hub = g.story
    hub.open_slot(1)
    hub.pane = "bestiary"
    g.menu_screen, g.started = "story_hub", False
    g.draw()                                          # the full panel: picture, name, text, bonus


def test_the_boss_picture_fits_its_frame(run):
    hub = StoryHub()
    big = hub.bestiary_picture("boss", 10)
    assert big.get_width() <= 676 - 20 and big.get_height() <= 210 - 10


def test_a_won_gate_mission_unlocks_the_boss_in_the_bestiary(run):
    g = run.game
    _state(bird1=5)
    hub = g.story
    hub.open_slot(1)
    assert [e["id"] for e, n in ss.bestiary_entries(hub.state)] == ["bird1"]
    hub.apply_result("act2_gate", 1200, True, {"bird1": 40, "boss": 1})
    assert [e["id"] for e, n in ss.bestiary_entries(hub.state)] == ["bird1", "boss"]
    hub.open_slot(1)                                   # and it is saved
    assert ss.encounters(hub.state, "boss") == 1


def test_a_lost_gate_mission_after_the_boss_fell_still_counts(run):
    g = run.game
    _state()
    hub = g.story
    hub.open_slot(1)
    hub.apply_result("act2_gate", 0, False, {"boss": 1})
    assert ss.encounters(hub.state, "boss") == 1


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_every_presentation_text_fits_above_the_bonus_line(run, lang):
    """The text goes in a 636 px column, 36 px per line, and must stop before the bonus line."""
    import i18n
    from story import _wrap
    font = run.game.font
    old = i18n.get_lang()
    i18n.set_lang(lang)
    try:
        for entry in ss.BESTIARY:
            lines = _wrap(font, i18n.t(entry["text"]), 676 - 40)
            assert len(lines) <= 5, (entry["id"], lang, len(lines))
    finally:
        i18n.set_lang(old)
