"""The old "TEST - SpaceWar" missions, kept for the tests of the SpaceWar engine only (they are no longer on the map of the
game: the Sentinelles missions use the engine now). A test module that needs them sets ``NEEDS_SW_MISSIONS = True`` and
tests/conftest.py puts them in story_state.MISSIONS for the length of each of its tests."""


def _mission(planet, suffix, blurb_suffix):
    return {
        "id": "test_spacewar" + suffix, "acts": (1, 2, 3), "extra": True, "spacewar": True,
        "planet": planet,
        "title": "story_m_sent_hud", "hud_title": "story_m_sent_hud", "blurb": "story_m_sent_hud",
        "need": None, "content": 1, "speed": 1.0,
    }


TEST_MISSIONS = [
    _mission("jupiter", "", ""),
    _mission("saturn", "_saturn", "_saturn"),
    _mission("uranus", "_uranus", "_uranus"),
    _mission("neptune", "_neptune", "_neptune"),
]
