"""Page up / Page down (LB / RB on the pad) on the mission map and in the journal: a page of the list at once, and the very
end when there is less than a page."""
import pygame
import pytest

import story as story_mod
import story_state as ss
from test_smoke import run  # noqa: F401  (fixture)


def _open(run, act=2, pane="map"):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["act"] = act
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.pane = pane
    g.menu_screen = "story_hub"
    g.started = False
    g.input_grace = 0.0
    g.fade_phase = None
    return g, g.story


def _key(run, key):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0, scancode=0))
    run.frames(1)


def _pad(run, button):
    pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=button, joy=0, instance_id=0))
    run.frames(1)


def test_map_page_down_and_up_jump_by_the_rows_shown(run):
    g, hub = _open(run)
    run.frames(2)                                           # drawn once: the page size is known
    n = len(hub.missions())
    assert 3 <= hub.map_page < n
    hub.map_index = 0
    for key, sign in [(pygame.K_PAGEDOWN, 1), (pygame.K_PAGEDOWN, 1), (pygame.K_PAGEUP, -1), (pygame.K_PAGEUP, -1)]:
        before, page = hub.map_index, hub.map_page
        _key(run, key)
        assert hub.map_index == max(0, min(n - 1, before + sign * page))
        assert hub.map_index != before
    for _ in range(6):
        _key(run, pygame.K_PAGEUP)
    assert hub.map_index == 0


def test_map_ends_at_the_last_row_and_the_first(run):
    g, hub = _open(run)
    run.frames(2)
    n = len(hub.missions())
    hub.map_index = n - 2
    _key(run, pygame.K_PAGEDOWN)
    assert hub.map_index == n - 1
    _key(run, pygame.K_PAGEDOWN)
    assert hub.map_index == n - 1
    hub.map_index = 1
    _key(run, pygame.K_PAGEUP)
    assert hub.map_index == 0


def test_a_short_list_goes_straight_to_the_end(run):
    g, hub = _open(run, act=1)
    run.frames(2)
    hub.missions = lambda: hub.__class__.missions(hub)[:2]          # fewer rows than a page
    hub.map_page = 7
    hub.map_index = 0
    hub.page_v(1)
    assert hub.map_index == 1
    hub.page_v(-1)
    assert hub.map_index == 0


def test_lb_and_rb_do_the_same_on_the_pad(run):
    g, hub = _open(run)
    run.frames(2)
    page = hub.map_page
    hub.map_index = 0
    _pad(run, 5)
    assert hub.map_index == page
    _pad(run, 4)
    assert hub.map_index == 0


def test_page_keys_do_nothing_on_the_other_panes_and_screens(run):
    g, hub = _open(run, pane="hangar")
    run.frames(2)
    before = (hub.map_index, hub.log_cursor, hub.log_scroll, hub.pane)
    _key(run, pygame.K_PAGEDOWN)
    _pad(run, 5)
    assert (hub.map_index, hub.log_cursor, hub.log_scroll, hub.pane) == before
    hub.pane = "map"
    hub.screen = "slots"
    hub.map_index = 0
    hub.page_v(1)
    assert hub.map_index == 0


def test_the_journal_scrolls_by_a_page(run, monkeypatch):
    g, hub = _open(run, pane="log")
    replay = [{"intro": True}] + [{"scene": "s%d" % i} for i in range(9)]
    story = [{"text": "line %d" % i} for i in range(40)]
    monkeypatch.setattr(hub, "replay_entries", lambda: replay)
    monkeypatch.setattr(hub, "story_entries", lambda: story)
    hub.log_cursor = hub.log_scroll = 0
    hub.page_v(1)
    assert hub.log_cursor == story_mod.LOG_REPLAY_ROWS and hub.log_scroll == 0
    hub.page_v(1)
    assert hub.log_cursor == 8
    hub.page_v(1)
    assert hub.log_cursor == 9 and hub.log_scroll == 0
    hub.page_v(1)
    assert hub.log_scroll == story_mod.LOG_STORY_ROWS
    for _ in range(10):
        hub.page_v(1)
    assert hub.log_scroll == len(story) - story_mod.LOG_STORY_ROWS            # the very end
    hub.page_v(-1)
    assert hub.log_scroll == len(story) - 2 * story_mod.LOG_STORY_ROWS
    for _ in range(10):
        hub.page_v(-1)
    assert hub.log_scroll == 0 and hub.log_cursor == 0


def test_a_short_journal_goes_to_the_end_and_back(run, monkeypatch):
    g, hub = _open(run, pane="log")
    monkeypatch.setattr(hub, "replay_entries", lambda: [{"intro": True}, {"scene": "a"}])
    monkeypatch.setattr(hub, "story_entries", lambda: [{"text": "x"}] * 3)
    hub.log_cursor = hub.log_scroll = 0
    hub.page_v(1)
    assert hub.log_cursor == 1 and hub.log_scroll == 0
    hub.page_v(1)
    assert hub.log_scroll == 0                                   # nothing to scroll: already at the bottom
    hub.page_v(-1)
    assert hub.log_cursor == 0


def test_the_journal_answers_to_the_keys_and_the_pad(run, monkeypatch):
    g, hub = _open(run, pane="log")
    monkeypatch.setattr(hub, "replay_entries", lambda: [{"intro": True}] + [{"scene": "s%d" % i} for i in range(9)])
    monkeypatch.setattr(hub, "story_entries", lambda: [{"text": "line %d" % i} for i in range(40)])
    hub.log_cursor = hub.log_scroll = 0
    _key(run, pygame.K_PAGEDOWN)
    assert hub.log_cursor == story_mod.LOG_REPLAY_ROWS
    _pad(run, 4)
    assert hub.log_cursor == 0
