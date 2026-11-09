"""The four TEST missions taken out of the Adventure (story_state.REMOVED_MISSIONS): the tests still use them to fly the
Guardians, the Lunar Lander, the Scramble and the escort modules alone, with nothing won nor lost (conftest: the fixture
`training_missions`)."""

TRAINING = [
    {
        "id": "test_guardians", "training": True, "test": True, "guardians": True,
        "title": "story_m_guardians_test", "blurb": "story_m_guardians_test_b",
        "need": None, "content": 3, "speed": 1.0,
    },
    # TEST: Lunar Lander (src/lander.py), a remake of Atari's 1979 arcade game: the ship lands by its thruster on the ice of
    # Titan or the rock of an asteroid (drawn at random). A training mission: the score is shown, nothing won, nothing lost.
    {
        "id": "test_lander", "acts": (1, 2, 3), "training": True, "test": True, "lander": True,
        "title": "story_m_lander", "hud_title": "story_m_lander_hud", "blurb": "story_m_lander_b",
        "need": None, "content": 1, "speed": 1.0,
    },
    # TEST: Scramble (src/scramble.py), a remake of Konami's 1981 arcade game: a side-scrolling shoot'em up through the rock of
    # one of the five settings of the Lunar Lander (chosen in a menu), to the enemy base. A training mission: the score is shown,
    # nothing won, nothing lost.
    {
        "id": "test_scramble", "acts": (1, 2, 3), "training": True, "test": True, "scramble": True,
        "title": "story_m_scramble", "hud_title": "story_m_scramble_hud", "blurb": "story_m_scramble_b",
        "need": None, "content": 1, "speed": 1.0,
    },
    # TEST: the escort modules (src/gyro.py): a run of the arcade levels 6 to 11 with the gyroscope satellites on each side
    # of the ship (how many, how tough: a menu first). A training mission: the score is shown, nothing won, nothing lost.
    {
        "id": "test_modules", "acts": (1, 2, 3), "training": True, "test": True, "modules": True,
        "title": "story_m_modules", "hud_title": "story_m_modules_hud", "blurb": "story_m_modules_b",
        "need": None, "content": 6, "waves": [6, 7, 8, 9, 10, 11], "speed": 1.0,
    },
]
