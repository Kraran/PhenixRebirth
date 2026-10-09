"""The adventure has four save slots; a mission never announces the next level when it ends."""
import os

import pygame
import pytest

import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def clean_slots():
    def wipe():
        for i in range(1, 6):
            for suffix in ("", ".corrupt"):
                try:
                    os.remove(ss.story_path(i) + suffix)
                except OSError:
                    pass
    wipe()
    yield
    wipe()


# ------------------------------------------------------------------ four save slots
def test_there_are_four_slots_with_their_own_files():
    assert ss.SLOT_COUNT == 4
    assert [s["slot"] for s in ss.all_summaries()] == [1, 2, 3, 4]
    assert len({ss.story_path(i) for i in range(1, 5)}) == 4
    assert ss.story_path(4).endswith("story_4.json")


def test_the_fourth_slot_is_created_saved_reloaded_and_deleted():
    st = ss.create_slot(4, "QUATRE", "veteran")
    assert st["name"] == "QUATRE"
    info = ss.slot_summary(4)
    assert (info["slot"], info["status"], info["name"], info["mode"]) == (4, "ok", "QUATRE", "veteran")
    assert [s["status"] for s in ss.all_summaries()] == ["missing", "missing", "missing", "ok"]
    hub = StoryHub()
    hub.open_slot(4)
    assert hub.slot_no == 4 and hub.state["name"] == "QUATRE"
    assert ss.delete_slot(4) is True and ss.slot_summary(4)["status"] == "missing"


def test_a_slot_does_not_touch_the_others():
    ss.create_slot(1, "UN", "normal")
    ss.create_slot(4, "QUATRE", "normal")
    hub = StoryHub()
    hub.open_slot(4)
    hub.state["credits"] = 777
    hub.save()
    assert ss.load_state(ss.story_path(1))["credits"] != 777
    again = StoryHub()
    again.open_slot(4)
    assert again.state["credits"] == 777


def test_the_cursor_reaches_the_fourth_slot_and_stops_there():
    hub = StoryHub()
    hub.open_slots()
    for _ in range(10):
        hub.nav_v(1)
    assert hub.sel == 3
    for _ in range(10):
        hub.nav_v(-1)
    assert hub.sel == 0


def test_a_new_adventure_can_start_in_the_fourth_slot():
    hub = StoryHub()
    hub.open_slots()
    hub.sel = 3
    hub.confirm()
    assert hub.screen == "name"
    for ch in "DERNIER":
        hub.entry.type_char(ch)
    hub._submit_name()
    hub.confirm()                                                   # normal mode
    assert hub.slot_no == 4 and hub.state["name"] == "DERNIER"
    assert ss.slot_summary(4)["status"] == "ok" and ss.slot_summary(1)["status"] == "missing"


def test_an_old_three_slot_player_keeps_the_saves(tmp_path):
    for i in (1, 2, 3):
        ss.create_slot(i, "S%d" % i, "normal")
    assert [s["name"] for s in ss.all_summaries()] == ["S1", "S2", "S3", ""]


def test_the_four_cards_and_the_hint_fit_on_the_screen(run):
    import story
    for i in (1, 4):
        ss.create_slot(i, "PILOTE%d" % i, "normal")
    hub = StoryHub()
    hub.open_slots()
    hub.sel = 3
    g = run.game
    seen = []
    real = story._fill
    story._fill = lambda surface, color, rect, radius=0: (seen.append(pygame.Rect(rect)), real(surface, color, rect, radius))[1]
    try:
        surf = pygame.Surface((1280, 720))
        hub.draw(surf, g.font, g.medium_font, g.font)
    finally:
        story._fill = real
    cards = [r for r in seen if r.w > 800]
    assert len(cards) == 4
    assert all(a.bottom < b.top for a, b in zip(cards, cards[1:]))              # no overlap
    assert cards[-1].bottom <= 720 - 40                                          # the hint line stays free


# ------------------------------------------------------------------ no next-level announcement in a mission
class _Sounds:
    def __init__(self, real):
        self._real = real
        self.vo = []

    def play_vo(self, name, *a, **k):
        self.vo.append(name)

    def __getattr__(self, name):
        return getattr(self._real, name)


def _boss_outro(g, adventure):
    import update_play
    g.sounds = _Sounds(g.sounds)
    g.stage = 5
    g.adventure = {"id": "best_boss", "waves": [5]} if adventure else None
    g.stage_transition = "boss_outro"
    g.transition_timer = 5.0
    update_play.tick_boss_outro(g)
    return g.sounds.vo


def test_the_end_of_a_boss_mission_does_not_say_the_next_level(run):
    assert _boss_outro(run.game, adventure=True) == []
    assert run.game.stage_transition == "fly_up"


def test_the_arcade_still_announces_the_next_level_after_a_boss(run):
    assert _boss_outro(run.game, adventure=False) == ["level6"]
    assert run.game.stage_transition == "fly_up"
