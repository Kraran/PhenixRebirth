"""Leaving an adventure mission must not leave explosions behind on the menu."""
import story_state as ss
from test_smoke import run  # noqa: F401  (fixture)


def _launch(g):
    g.story.map_index = 0
    spec = g.story._launch_selected()
    assert spec
    g._begin_adventure(spec)
    return spec


def test_end_of_mission_clears_explosions(run):
    g = run.game
    _launch(g)
    run.frames(30)
    g.explosions.append(g._boom(400, 300, kind="enemy"))
    g.explosions.append(g._boom(600, 200, kind="gameover"))
    assert g.explosions
    g._end_adventure(True)
    assert g.explosions == []
    assert g.started is False and g.menu_screen == "story_hub"
    run.frames(5)
    assert g.explosions == []


def test_failed_mission_clears_explosions_too(run):
    g = run.game
    _launch(g)
    run.frames(10)
    g.explosions.append(g._boom(300, 300, kind="enemy"))
    g._end_adventure(False)
    assert g.explosions == []
