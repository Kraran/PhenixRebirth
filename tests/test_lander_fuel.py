"""Starting fuel of the five landings and of BONUS FINAL - Lunar Lander, and the texts that mention it."""
import lander
import story_state as ss
from i18n import LANG_CODES, T

TANKS = {
    "lander_deimos": 90,
    "lander_rock": 80,
    "lander_europa": 70,
    "lander_titan": 70,
    "lander_triton": 60,
    "bonus_lander": 90,
}

BLURBS = {
    "lander_deimos": ("story_m_land1_b", "story_scene_land1"),
    "lander_rock": ("story_m_land2_b", "story_scene_land2"),
    "lander_europa": ("story_m_land3_b", "story_scene_land3"),
    "lander_titan": ("story_m_land4_b", "story_scene_land4"),
    "lander_triton": ("story_m_land5_b", "story_scene_land5"),
    "bonus_lander": ("story_m_lander_bonus_b",),
}

STALE = ("150", "120", "plein à ras bord", "full to the brim")


def test_each_landing_and_the_bonus_start_with_their_own_tank():
    assert lander.FUEL_START == 90.0
    for mid, fuel in TANKS.items():
        m = ss.mission_by_id(mid)
        assert m["lander"] and m["fuel"] == fuel


def test_the_blurbs_and_the_scenes_mention_the_right_numbers_in_every_language():
    for mid, keys in BLURBS.items():
        fuel = str(TANKS[mid])
        for key in keys:
            assert set(T[key]) == set(LANG_CODES) and T[key]["fr"] != T[key]["en"]
            for code in LANG_CODES:
                text = T[key][code]
                assert fuel in text, (key, code, text)
                for word in STALE:
                    assert word not in text, (key, code, word, text)


def test_a_refuel_of_the_endless_level_is_not_capped_by_the_starting_tank():
    f = lander.LanderFormation("rock", 1, fuel=90, endless=True)
    assert f.fuel == f.fuel_max == 90.0
    f.fuel = 80.0
    f.fuel += lander.REFUEL["perfect"]
    assert f.fuel == 130.0 and f.fuel > f.fuel_max
    f.fuel = 40.0
    f.fuel += lander.REFUEL["rough"]
    assert f.fuel == 65.0
