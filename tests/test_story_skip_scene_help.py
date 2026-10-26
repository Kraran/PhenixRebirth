"""The first sortie shows its controls before takeoff, including after a skipped story scene."""
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
def test_esc_on_the_scene_opens_the_preflight_briefing(run):
    g = _scene_before_launch(run)
    _esc(run)
    assert not g.started and g.story.screen == "first_help" and g.story.first_help_spec["id"] == "ch1_sortie"
    assert ss.scene_seen(g.story.state, "ch1_sortie")           # skipped = seen: it does not come back


def test_the_pad_b_on_the_scene_opens_the_preflight_briefing_too(run):
    g = _scene_before_launch(run)
    g.input_grace = 0.0
    pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=1, joy=0, instance_id=0))
    run.frames(3)
    assert not g.started and g.story.screen == "first_help"
    assert g.story.first_help_spec["id"] == "ch1_sortie"


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


# ------------------------------------------------------------------ briefing before combat
def test_first_sortie_briefing_requires_confirmation_before_takeoff(run):
    g = run.game
    _slot()
    _on_map(g)
    spec = g.story._launch_selected()
    g._request_adventure(spec)
    assert not g.started and g.story.screen == "first_help"
    assert g.story.confirm() is None  # cannot reuse the click that closed the scene
    g.story.update(0.25)
    g.story.update(0.25)
    launch = g.story.confirm()
    assert launch["first_help_read"]
    g._request_adventure(launch)
    assert g.started and g.adventure["id"] == "ch1_sortie"
    assert "tip_t" not in g.adventure and "first_help_read" not in g.adventure


def test_cancelling_the_briefing_returns_to_the_map(run):
    g = run.game
    _slot()
    _on_map(g)
    g._request_adventure(g.story._launch_selected())
    assert g.story.back()
    assert not g.started and g.story.screen == "hub" and g.story.pane == "map"
    assert g.story.first_help_spec is None


def test_later_missions_launch_without_the_briefing(run):
    g = run.game
    _slot(cleared=["ch1_sortie"])
    _on_map(g, "best_s2")
    g._request_adventure(g.story._launch_selected())
    assert g.started and g.adventure["id"] == "best_s2" and "tip_t" not in g.adventure


def test_controls_are_drawn_before_the_mission_with_real_bindings(run):
    import story
    g = run.game
    _slot()
    _on_map(g)
    g._request_adventure(g.story._launch_selected())
    seen = []
    real = story._text

    def spy(surface, font, text, *args, **kwargs):
        seen.append(text)
        return real(surface, font, text, *args, **kwargs)

    story._text = spy
    try:
        g.story.draw(g.game_surface, g.font, g.medium_font, g.font)
    finally:
        story._text = real
    for line in help_screen.help_lines("story_first_help"):
        assert any(part in " ".join(seen) for part in line.split())
    assert not g.started and g.story.covers_screen()


@pytest.mark.parametrize("lang", LANG_CODES)
def test_the_reminder_exists_in_every_language(lang):
    set_lang(lang)
    lines = help_screen.help_lines("story_first_help")
    assert len(lines) == 2 and all(lines) and not any("{" in line for line in lines)
