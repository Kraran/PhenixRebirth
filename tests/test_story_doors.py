"""Options, Jukebox and Credits are reached from the Adventure, in the Extras tab at the far left (left of the Bestiary).

The tab has three paragraphs, one for each screen: Up / Down choose, A opens the screen of the main menu, as it works from
the main menu, and leaving it (B / Esc, or the screen's own way out) brings the Adventure back on the same paragraph.
"""
import pygame
import pytest

import story_state as ss
from story import DOORS, PANES, StoryHub
from test_smoke import run  # noqa: F401  (fixture)


def _key(run, key, frames=2):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0, scancode=0))
    run.frames(frames)


@pytest.fixture
def hub(run):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    g.menu_screen = "story_hub"
    g.story.open_slot(1)
    g.input_grace = 0
    run.frames(2)
    return g


def _open(run, g, door):
    g.story.pane = "extras"
    g.story.extras_index = DOORS.index(door)
    g.input_grace = 0
    _key(run, pygame.K_RETURN)
    g.input_grace = 0
    run.frames(2)


# --- where they are -----------------------------------------------------------------------------------------------

def test_one_extras_tab_is_the_first_and_holds_the_three_screens_in_this_order():
    assert DOORS == ("options", "jukebox", "credits")
    assert PANES == ("extras", "bestiary", "log", "hangar", "map")


def test_left_from_the_bestiary_goes_to_extras_and_stops():
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "bestiary"
    seen = []
    for _ in range(3):
        hub.nav_h(-1)
        seen.append(hub.pane)
    assert seen == ["extras"] * 3
    hub.nav_h(1)
    assert hub.pane == "bestiary"


def test_up_and_down_choose_the_paragraph_and_stop_at_the_ends():
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "extras"
    assert hub.extras_index == 0
    hub.nav_v(-1)
    assert hub.extras_index == 0
    seen = []
    for _ in range(4):
        hub.nav_v(1)
        seen.append(hub.extras_index)
    assert seen == [1, 2, 2, 2]
    hub.nav_v(-1)
    assert hub.extras_index == 1


def test_a_gives_the_screen_of_the_chosen_paragraph():
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "extras"
    got = []
    for i in range(3):
        hub.extras_index = i
        got.append(hub.confirm())
    assert got == [{"door": "options"}, {"door": "jukebox"}, {"door": "credits"}]


def test_the_tab_row_and_the_tab_draw(hub, run):
    for pane in PANES:
        hub.story.pane = pane
        run.frames(3)
    hub.story.pane = "extras"
    for i in range(3):
        hub.story.extras_index = i
        run.frames(3)


def test_the_three_paragraphs_and_the_chosen_one_are_drawn(hub):
    import story
    from i18n import t
    texts = []
    real = story._text

    def spy(surface, font, text, *a, **k):
        texts.append(text)
        return real(surface, font, text, *a, **k)
    story._text = spy
    try:
        hub.story.pane = "extras"
        hub.story.extras_index = 1
        hub.draw()
    finally:
        story._text = real
    for door in DOORS:
        assert any(t(door) in x for x in texts), door
        assert any(t("story_door_" + door).split()[0] in x for x in texts), door
    assert any(x.startswith("> ") and t("jukebox") in x for x in texts)
    assert not any(x.startswith("> ") and (t("options") in x or t("credits") in x) for x in texts)
    row = [x for x in texts if t("story_extras") in x and t("story_tab_best") in x]
    assert row and row[0].index(t("story_extras")) < row[0].index(t("story_tab_best"))


# --- opening and coming back ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("door", DOORS)
def test_a_opens_the_screen_and_escape_brings_the_tab_back(hub, run, door):
    g = hub
    _open(run, g, door)
    assert g.menu_screen == door and g.story_door == door
    run.frames(10)
    assert g.menu_screen == door                          # it stays: nothing sends it away
    _key(run, pygame.K_ESCAPE, frames=3)
    assert g.menu_screen == "story_hub" and g.story.pane == "extras" and g.story.screen == "hub"
    assert g.story.extras_index == DOORS.index(door)      # on the paragraph it was opened from
    assert g.story_door is None and g.started is False
    assert g.story.slot_no == 1                           # the same adventure, nothing was reloaded


def test_the_press_that_opens_a_screen_does_not_act_in_it(hub, run):
    g = hub
    g.story.pane = "extras"
    g.story.extras_index = DOORS.index("credits")
    g.input_grace = 0
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0, scancode=0))
    run.frames(1)
    assert g.menu_screen == "credits"
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0, scancode=0))   # key repeat
    run.frames(2)
    assert g.menu_screen == "credits"                     # still there: the repeat was ignored
    g.input_grace = 0
    _key(run, pygame.K_RETURN, frames=3)                  # a real press leaves it, as from the main menu
    assert g.menu_screen == "story_hub" and g.story.pane == "extras" and g.story.extras_index == 2


def test_options_work_from_the_adventure_and_changes_are_kept(hub, run):
    g = hub
    _open(run, g, "options")
    g.sfx_volume = 0.5
    g.menu_index = g._options_spec().index("sfx")
    _key(run, pygame.K_RIGHT)
    assert g.menu_screen == "options" and g.story.pane == "extras"       # Left / Right change a value, not the tab
    assert g.sfx_volume > 0.5
    _key(run, pygame.K_ESCAPE, frames=3)
    assert g.menu_screen == "story_hub" and g.story.pane == "extras" and g.story.extras_index == 0


def test_the_reset_screen_of_the_options_stays_inside_the_door(hub, run):
    g = hub
    _open(run, g, "options")
    g.menu_screen = "reset_confirm"
    g.menu_index = 1
    run.frames(5)
    assert g.menu_screen == "reset_confirm" and g.story_door == "options"
    _key(run, pygame.K_ESCAPE, frames=2)                  # back to the options, not out of them
    assert g.menu_screen == "options"
    _key(run, pygame.K_ESCAPE, frames=3)
    assert g.menu_screen == "story_hub"


def test_the_options_back_line_returns_to_the_adventure(hub, run):
    g = hub
    _open(run, g, "options")
    spec = g._options_spec()
    g.menu_index = spec.index("back")
    g.input_grace = 0
    _key(run, pygame.K_RETURN, frames=3)
    assert g.menu_screen == "story_hub" and g.story.pane == "extras" and g.story.extras_index == 0


def test_the_jukebox_plays_and_left_right_do_not_go_to_the_scores(hub, run):
    g = hub
    _open(run, g, "jukebox")
    assert g.menu_screen == "jukebox"
    for key in (pygame.K_RIGHT, pygame.K_LEFT):
        _key(run, key)
        assert g.menu_screen == "jukebox"
    _key(run, pygame.K_ESCAPE, frames=3)
    assert g.menu_screen == "story_hub" and g.story.pane == "extras" and g.story.extras_index == 1


def test_the_jukebox_stops_its_music_when_it_is_left(hub, run, monkeypatch):
    g = hub
    stopped = []
    monkeypatch.setattr(g, "_leave_jukebox_audio", lambda: stopped.append(1))
    _open(run, g, "jukebox")
    _key(run, pygame.K_ESCAPE, frames=3)
    assert stopped and g.menu_screen == "story_hub"


def test_a_gamepad_b_button_also_brings_the_tab_back(hub, run):
    g = hub
    for door in DOORS:
        _open(run, g, door)
        assert g.menu_screen == door
        g.input_grace = 0
        pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=1, instance_id=0, joy=0))
        run.frames(3)
        assert g.menu_screen == "story_hub" and g.story.pane == "extras" and g.story.extras_index == DOORS.index(door), door


def test_the_screens_of_the_main_menu_are_as_they_were(run):
    """From the main menu they still go back to the main menu, and Left / Right still go through the scores."""
    g = run.game
    g.menu_screen = "options"
    g.menu_index = 0
    run.frames(3)
    _key(run, pygame.K_ESCAPE, frames=3)
    assert g.menu_screen == "main" and g.menu_index == 5 and not getattr(g, "story_door", None)
    g.menu_screen = "highscores"
    run.frames(2)
    g.input_grace = 0
    _key(run, pygame.K_RIGHT)
    assert g.menu_screen == "achievements"


def test_a_door_forgotten_is_dropped_when_a_run_starts(hub, run):
    g = hub
    _open(run, g, "options")
    g._begin_run()
    run.frames(5)
    assert g.started and g.menu_screen != "story_hub" and g.story_door is None


def test_the_hub_keeps_its_own_tabs_working(hub, run):
    g = hub
    g.story.pane = "map"
    for _ in range(3):
        _key(run, pygame.K_LEFT)
    assert g.story.pane == "bestiary"
    _key(run, pygame.K_LEFT)
    assert g.story.pane == "extras"
    g.story.pane = "hangar"
    _key(run, pygame.K_RIGHT)
    assert g.story.pane == "map"


def test_the_paragraph_comes_from_the_screen_that_was_opened_not_from_the_cursor(hub, run):
    g = hub
    _open(run, g, "credits")
    g.story.extras_index = 0                              # whatever the cursor says, the way back goes by the screen
    _key(run, pygame.K_ESCAPE, frames=3)
    assert g.menu_screen == "story_hub" and g.story.extras_index == DOORS.index("credits")
