"""Skipping the scene read before a launch (B / Esc) flies the mission at once; the very first sortie shows a controls
reminder for a few seconds."""
import pygame
import pytest

import draw_frame
import help_screen
import i18n
import story_state as ss
from i18n import LANG_CODES, set_lang, t
from test_smoke import run  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def _french_again():
    yield
    set_lang("fr")


def _slot(cleared=()):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["cleared"] = list(cleared)
    for mission_id in cleared:
        for flag in ss.mission_by_id(mission_id).get("unlock") or []:
            st["flags"][flag] = True                       # what winning it opened
    ss.save_state(ss.story_path(1), st)
    return st


def _on_map(g, mission="ch1_sortie"):
    g.story.open_slot(1)
    g.story.pane = "map"
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mission)
    g.menu_screen = "story_hub"
    g.input_grace = 0.0


def _esc(run, key=pygame.K_ESCAPE):
    run.game.input_grace = 0.0
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0, scancode=0))
    run.frames(3)


def _scene_before_launch(run):
    g = run.game
    _slot()
    _on_map(g)
    g.story.confirm()                                   # the scene of the first sortie opens, a launch waits behind it
    assert g.story.screen == "intro" and g.story.scene_launch and g.story.scene_id == "ch1_sortie"
    return g


# ------------------------------------------------------------------ B / Esc on the scene
def test_esc_on_the_scene_flies_the_mission_at_once(run):
    g = _scene_before_launch(run)
    _esc(run)
    assert g.started and g.adventure and g.adventure["id"] == "ch1_sortie"
    assert ss.scene_seen(g.story.state, "ch1_sortie")           # skipped = seen: it does not come back


def test_the_pad_b_on_the_scene_flies_the_mission_too(run):
    g = _scene_before_launch(run)
    g.input_grace = 0.0
    pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=1, joy=0, instance_id=0))
    run.frames(3)
    assert g.started and g.adventure and g.adventure["id"] == "ch1_sortie"


def test_a_scene_replayed_from_the_journal_does_not_launch(run):
    g = run.game
    _slot()
    _on_map(g)
    g.story.start_scene("ch1_sortie", back_to="log", launch=False)
    _esc(run)
    assert not g.started and g.story.screen == "hub" and g.story.pane == "log"


def test_skipping_the_story_intro_does_not_launch(run):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.start_intro(back_to="map")
    g.menu_screen = "story_hub"
    _esc(run)
    assert not g.started and g.story.screen == "hub" and g.story.pane == "map"


def test_a_launch_request_is_given_only_once(run):
    g = _scene_before_launch(run)
    assert g.story.back() is True
    spec = g.story.take_launch_request()
    assert spec and spec["id"] == "ch1_sortie" and g.story.take_launch_request() is None


def test_a_launch_that_is_not_playable_gives_nothing(run):
    g = _scene_before_launch(run)
    g.story.map_index = [m["id"] for m in g.story.missions()].index("best_s3")      # locked: not playable
    assert g.story.back() is True
    assert g.story.take_launch_request() is None


# ------------------------------------------------------------------ the reminder of the first sortie
def test_only_the_first_sortie_of_a_new_pilot_is_due():
    new = ss.create_slot(1, "A", "normal")
    assert ss.first_sortie(new, "ch1_sortie")
    assert not ss.first_sortie(new, "best_s2")
    assert not ss.first_sortie(dict(new, cleared=["ch1_sortie"]), "ch1_sortie")       # already won once
    assert not ss.first_sortie(dict(new, cleared=["dome_1"]), "ch1_sortie")           # a pilot who has won something
    assert ss.first_sortie({}, "ch1_sortie")                                          # (a save without the list: nothing won)


def test_the_first_mission_starts_with_the_reminder_and_the_second_does_not(run):
    g = run.game
    _slot()
    _on_map(g)
    g._begin_adventure(g.story._launch_selected())
    assert g.adventure["tip_t"] == ss.FIRST_HELP_SECONDS
    g._end_adventure(False)
    _slot(cleared=["ch1_sortie"])
    _on_map(g, "best_s2")
    g._begin_adventure(g.story._launch_selected())
    assert not g.adventure.get("tip_t")


def _first(run):
    g = run.game
    _slot()
    _on_map(g)
    g._begin_adventure(g.story._launch_selected())
    return g


def test_the_clock_runs_only_once_the_ship_is_in_play(run):
    g = _first(run)
    assert g.stage_transition is not None                          # the ship is arriving
    run.frames(5)
    assert g.adventure["tip_t"] == ss.FIRST_HELP_SECONDS
    assert draw_frame.first_help_alpha(g) == 0
    g.stage_transition = None
    run.frames(30)
    assert 0 < g.adventure["tip_t"] < ss.FIRST_HELP_SECONDS
    assert draw_frame.first_help_alpha(g) > 0


def test_the_reminder_fades_in_stays_and_fades_out(run):
    g = _first(run)
    g.stage_transition = None
    full = ss.FIRST_HELP_SECONDS
    g.adventure["tip_t"] = full - 0.05
    start = draw_frame.first_help_alpha(g)
    g.adventure["tip_t"] = full / 2
    middle = draw_frame.first_help_alpha(g)
    g.adventure["tip_t"] = 0.1
    end = draw_frame.first_help_alpha(g)
    g.adventure["tip_t"] = 0.0
    gone = draw_frame.first_help_alpha(g)
    assert middle == 255 and 0 < start < 255 and 0 < end < 255 and gone == 0


def test_the_pause_stops_the_clock(run):
    g = _first(run)
    g.stage_transition = None
    run.frames(10)
    g.paused = True
    before = g.adventure["tip_t"]
    run.frames(30)
    assert g.adventure["tip_t"] == before


def test_it_goes_away_at_the_end_of_its_time(run):
    g = _first(run)
    g.stage_transition = None
    g.adventure["tip_t"] = 0.2
    run.frames(30)
    assert g.adventure is not None and g.adventure["tip_t"] == 0
    assert draw_frame.first_help_alpha(g) == 0


def test_the_reminder_is_drawn_with_the_real_keys(run):
    g = _first(run)
    g.stage_transition = None
    run.frames(20)
    seen = []
    real = g._txt

    def spy(font, text, color, *a, **k):
        seen.append(text)
        return real(font, text, color, *a, **k)

    g._txt = spy
    try:
        run.frames(1)
    finally:
        g._txt = real
    for line in help_screen.help_lines("story_first_help"):
        assert line in seen and "{" not in line


@pytest.mark.parametrize("lang", LANG_CODES)
def test_the_reminder_exists_in_every_language(lang):
    set_lang(lang)
    lines = help_screen.help_lines("story_first_help")
    assert len(lines) == 2 and all(lines) and not any("{" in line for line in lines)
    assert "Esc" in lines[0] or "Échap" in lines[0]


def test_the_clock_waits_while_a_transition_runs(run):
    import update_play
    g = _first(run)
    g.dt = 0.5
    g.stage_transition = "arrive"
    update_play.tick_effects_and_hotseat(g)
    assert g.adventure["tip_t"] == ss.FIRST_HELP_SECONDS
    g.stage_transition = None
    update_play.tick_effects_and_hotseat(g)
    assert g.adventure["tip_t"] == ss.FIRST_HELP_SECONDS - 0.5


def test_the_reminder_is_hidden_during_a_transition_even_when_due(run):
    g = _first(run)
    g.adventure["tip_t"] = ss.FIRST_HELP_SECONDS / 2
    g.stage_transition = "arrive"
    assert draw_frame.first_help_alpha(g) == 0
    g.stage_transition = None
    assert draw_frame.first_help_alpha(g) == 255


def test_the_plate_is_translucent_while_it_fades(run):
    g = _first(run)
    g.stage_transition = None
    probe = (640, draw_frame.FIRST_HELP_Y + 2)                  # on the top edge of the plate (its blue frame)

    def edge(left):
        g.adventure["tip_t"] = left
        g.game_surface.fill((0, 0, 0))
        draw_frame.draw_first_help(g)
        return sum(g.game_surface.get_at(probe)[:3])

    assert edge(ss.FIRST_HELP_SECONDS / 2) > edge(0.15) > 0
