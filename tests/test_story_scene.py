"""Story scenes: a text with a picture, told the first time a mission is launched, replayable from the journal."""
import os

import pygame
import pytest

import story_state as ss
from i18n import t
from settings import asset_path
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)


def _hub(cheat=True, seen_scene=False, log=()):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["log"] = list(log)
    if seen_scene:
        ss.mark_scene_seen(st, "dome_1")
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.cheat_unlock = cheat                      # dome_1 is far down the story: open the map for the test
    hub.pane = "map"
    hub.map_index = [m["id"] for m in hub.missions()].index("dome_1")
    return hub


def _wait(hub, seconds=1.0):
    for _ in range(int(seconds / 0.25) + 1):
        hub.update(0.25)


# ------------------------------------------------------------------ the scene itself
def test_the_first_dome_mission_has_a_scene_with_its_picture_and_text():
    scene = ss.scene_of("dome_1")
    assert scene and len(scene["slides"]) == 1
    pic, key = scene["slides"][0]
    assert os.path.exists(asset_path("story", pic + ".jpg"))
    text = t(key)
    assert text.startswith("De rares survivants, échappés des colonies ravagées des lunes de Jupiter")
    assert text.endswith("la malédiction qui pèse sur la race humaine.")
    assert text.count("\n\n") == 2                                 # its three paragraphs, with a pause between
    assert "EDF42-Shield" in text and "Avioïdes" in text
    assert ss.scene_of("dome_2") is None and ss.scene_of("best_s2") is None


def test_the_scene_texts_are_in_every_language_table():
    from i18n import T, LANG_CODES
    for key in ("story_scene_dome_1", "story_scene_dome_1_t", "story_log_scene", "story_scene_last",
                "story_scene_end"):
        assert set(T[key]) == set(LANG_CODES) and t(key)


def test_the_picture_is_the_one_given():
    img = pygame.image.load(asset_path("story", "epave_shield.jpg"))
    assert img.get_size() == (1792, 1008)


# ------------------------------------------------------------------ the first launch
def test_the_first_launch_shows_the_scene_instead_of_flying():
    hub = _hub()
    assert hub.confirm() is None
    assert hub.screen == "intro" and hub.scene_id == "dome_1" and hub.scene_launch
    assert hub.intro_slides == ss.scene_of("dome_1")["slides"] and hub.intro_index == 0
    assert not ss.scene_seen(hub.state, "dome_1")                  # not told yet: only when it is over


def test_the_end_of_the_scene_flies_the_mission_and_remembers_it(tmp_path):
    hub = _hub()
    hub.confirm()
    assert hub.confirm() is None and hub.screen == "intro"          # too early: ignored
    _wait(hub)
    spec = hub.confirm()
    assert isinstance(spec, dict) and spec["launch"] and spec["id"] == "dome_1"
    assert hub.screen == "hub" and hub.scene_id is None and not hub.scene_launch
    assert ss.scene_seen(hub.state, "dome_1")
    assert not ss.intro_seen(ss.default_state())                    # the scene is not the intro
    again = hub.confirm()                                           # the second time: straight to the mission
    assert isinstance(again, dict) and again["id"] == "dome_1" and hub.screen == "hub"


def test_the_scene_is_saved_with_the_slot():
    hub = _hub(cheat=False)
    hub.state["cleared"] = ["ch1_sortie", "best_s2", "best_s3", "best_s4"]
    hub.state["flags"].update(ch1_speed=True)
    hub.cheat_unlock = True
    hub.confirm()
    _wait(hub)
    hub.confirm()
    hub.cheat_unlock = False
    hub.save()
    again = StoryHub()
    again.open_slot(1)
    assert ss.scene_seen(again.state, "dome_1")


def test_skipping_the_scene_counts_as_seen_and_comes_back_to_the_map():
    hub = _hub()
    hub.confirm()
    assert hub.back() is True
    assert hub.screen == "hub" and hub.pane == "map" and ss.scene_seen(hub.state, "dome_1")
    spec = hub.confirm()
    assert isinstance(spec, dict) and spec["id"] == "dome_1"        # the next A flies


def test_other_missions_fly_straight_away():
    hub = _hub()
    hub.map_index = [m["id"] for m in hub.missions()].index("best_s2")
    spec = hub.confirm()
    assert isinstance(spec, dict) and spec["id"] == "best_s2" and hub.screen == "hub"


def test_a_mission_that_cannot_be_flown_shows_no_scene():
    hub = _hub(cheat=False)
    assert not hub.mission_playable(hub._mission())
    assert hub.confirm() is None and hub.screen == "hub"


def test_each_slot_has_its_own_scene_memory():
    st = ss.create_slot(2, "OTHER", "normal")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(2), st)
    hub = _hub()
    hub.confirm()
    _wait(hub)
    hub.confirm()
    other = StoryHub()
    other.open_slot(2)
    assert not ss.scene_seen(other.state, "dome_1")


def test_the_launch_goes_through_the_game_menu(run):
    import menu_actions
    g = run.game
    hub = _hub()
    g.story = hub
    g.menu_screen = "story_hub"
    launched = []
    g._begin_adventure = lambda spec: launched.append(spec)
    menu_actions.menu_confirm(g)
    assert launched == [] and hub.screen == "intro"
    _wait(hub)
    menu_actions.menu_confirm(g)
    assert len(launched) == 1 and launched[0]["id"] == "dome_1"


# ------------------------------------------------------------------ the journal
def test_the_journal_has_no_scene_line_before_the_scene_is_seen():
    hub = _hub()
    hub.pane = "log"
    assert hub.log_entries() == [{"intro": True}]
    hub.nav_v(1)
    assert hub.log_cursor == 0


def test_a_seen_scene_has_a_replay_line_right_after_the_intro():
    hub = _hub(seen_scene=True, log=[{"key": "story_log_sortie"}])
    entries = hub.log_entries()
    assert entries[0] == {"intro": True} and entries[1] == {"scene": "dome_1"} and entries[2] == {"key": "story_log_sortie"}
    assert ss.log_text(entries[1], t) == t("story_log_scene").format(title=t("story_scene_dome_1_t"))
    assert ss.log_text(entries[1], t) == "Revoir : Dôme I : l'épave du Shield"
    assert hub.replay_entries() == entries[:2]


def test_down_and_up_go_through_the_replay_lines_before_scrolling():
    from story import LOG_ROWS
    hub = _hub(seen_scene=True, log=[{"key": "story_log_sortie"}] * 20)
    hub.pane = "log"
    assert hub.log_cursor == 0 and hub.log_scroll == 0
    hub.nav_v(1)
    assert hub.log_cursor == 1 and hub.log_scroll == 0
    hub.nav_v(1)
    assert hub.log_cursor == 1 and hub.log_scroll == 1                # past the replay lines: it scrolls
    for _ in range(60):
        hub.nav_v(1)
    assert hub.log_scroll == len(hub.log_entries()) - LOG_ROWS
    for _ in range(60):
        hub.nav_v(-1)
    assert hub.log_scroll == 0 and hub.log_cursor == 0                 # and back up again
    hub.nav_v(1)
    hub.nav_v(-1)
    assert hub.log_cursor == 0


def test_the_journal_replays_the_scene_and_returns_to_the_journal():
    hub = _hub(seen_scene=True)
    hub.pane = "log"
    hub.nav_v(1)
    assert hub.confirm() is None
    assert hub.screen == "intro" and hub.scene_id == "dome_1" and not hub.scene_launch
    _wait(hub)
    assert hub.confirm() is None                                      # a replay never flies the mission
    assert hub.screen == "hub" and hub.pane == "log" and hub.scene_id is None


def test_the_intro_line_still_replays_the_intro():
    hub = _hub(seen_scene=True)
    hub.pane = "log"
    hub.confirm()
    assert hub.screen == "intro" and hub.scene_id is None
    assert hub.intro_slides == ss.intro_slides("normal")
    assert hub.back() and hub.pane == "log" and ss.intro_seen(hub.state)


def test_skipping_a_replayed_scene_returns_to_the_journal():
    hub = _hub(seen_scene=True)
    hub.pane = "log"
    hub.nav_v(1)
    hub.confirm()
    assert hub.back() and hub.screen == "hub" and hub.pane == "log"


def test_watching_the_intro_does_not_mark_a_scene_and_the_reverse():
    hub = _hub()
    hub.pane = "log"
    hub.confirm()
    _wait(hub)
    for _ in range(len(hub.intro_slides)):
        _wait(hub)
        hub.confirm()
    assert not ss.scene_seen(hub.state, "dome_1")
    hub = _hub()
    hub.confirm()
    hub.back()
    assert ss.scene_seen(hub.state, "dome_1")


# ------------------------------------------------------------------ drawing
def _drawn(hub, run):
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
        surf = pygame.Surface((1280, 720))
        hub.draw(surf, g.font, g.medium_font, g.font)
    finally:
        story._text, story._text_fit = real, real_fit
    return seen, surf


def test_the_scene_draws_its_picture_and_its_own_hints(run):
    hub = _hub()
    hub.confirm()
    hub.intro_t = 500.0
    hub.intro_pos = 99999.0                                           # the text has risen to its resting place
    hub.update(0.01)
    shown, surf = _drawn(hub, run)
    assert t("story_scene_last") in shown                              # "take off": the mission follows
    assert not any("/" in s and s.strip()[0].isdigit() for s in shown)      # one slide: no "1 / 1" counter
    px = [surf.get_at((x, 120))[:3] for x in range(20, 140, 10)]
    assert any(max(p) > 30 for p in px)                                # the picture is there, not black


def test_a_replayed_scene_says_close_not_take_off(run):
    hub = _hub(seen_scene=True)
    hub.pane = "log"
    hub.nav_v(1)
    hub.confirm()
    hub.intro_t = 500.0
    shown, _ = _drawn(hub, run)
    assert t("story_scene_end") in shown and t("story_scene_last") not in shown


def test_the_scene_text_is_not_mixed_up_with_the_intro_text(run):
    """Both are slide 0 of their own list: the cached text must follow the slide, not its index."""
    g = run.game
    hub = _hub(seen_scene=True)
    hub.pane = "log"
    hub.confirm()                                                      # the intro, slide 0
    block_intro, h_intro = hub._intro_block(g.font)
    hub.back()
    hub.nav_v(1)
    hub.confirm()                                                      # the scene, slide 0
    block_scene, h_scene = hub._intro_block(g.font)
    assert h_scene != h_intro and block_scene is not block_intro
    assert h_scene > 1000                                              # the long text of the scene


def test_the_journal_draws_the_scene_line_with_one_cursor(run):
    import story
    hub = _hub(seen_scene=True)
    hub.pane = "log"
    gold = []
    real = story.pygame.draw.rect

    def spy(surface, color, rect, *a, **k):
        if tuple(color)[:3] == (255, 210, 80):
            gold.append(pygame.Rect(rect).y)
        return real(surface, color, rect, *a, **k)

    story.pygame.draw.rect = spy
    try:
        shown0, _ = _drawn(hub, run)
        y0 = list(gold)
        gold.clear()
        hub.nav_v(1)
        shown1, _ = _drawn(hub, run)
        y1 = list(gold)
    finally:
        story.pygame.draw.rect = real
    assert len(y0) == 1 and len(y1) == 1 and y1[0] > y0[0]             # the frame moved down one line
    assert any("Revoir : Dôme I" in s for s in shown0)
