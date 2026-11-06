"""The scenes of the landings and the raids (step 4d of the escort modules): one briefing per mission, told before its first
flight, kept in the journal in the order of the story."""

import pytest

import story_state as ss
from i18n import LANG_CODES, T, t
from story import StoryHub

MISSIONS = ("lander_deimos", "raid_deimos", "lander_rock", "raid_rock", "lander_europa", "raid_europa",
            "lander_titan", "raid_titan", "lander_triton", "raid_triton")


def test_each_landing_and_raid_has_its_scene_with_its_own_picture():
    pics = set()
    for mid in MISSIONS:
        scene = ss.scene_of(mid)
        assert scene and scene["title"] == ss.mission_by_id(mid)["title"]
        (pic, key), = scene["slides"]
        assert pic.startswith("atterrissage_" if mid.startswith("lander_") else "raid_")
        assert key.startswith("story_scene_land" if mid.startswith("lander_") else "story_scene_raid")
        pics.add(pic)
    assert len(pics) == 10


@pytest.mark.parametrize("lang", LANG_CODES)
def test_the_texts_exist_in_every_language(lang):
    for mid in MISSIONS:
        key = ss.scene_of(mid)["slides"][0][1]
        assert T[key][lang] and len(T[key][lang]) > 200, (key, lang)
        assert T[key]["fr"] != T[key]["en"]
        assert "..." not in T[key]["fr"]                      # (the ellipsis is always one sign: …)


def test_the_scenes_come_in_the_order_of_the_story():
    order = ss.SCENE_ORDER
    assert set(ss.SCENES) <= set(order) and all(order.count(m) == 1 for m in MISSIONS)
    for mid in MISSIONS[0::2]:
        assert order.index(mid) + 1 == order.index("raid_" + mid[len("lander_"):])     # the landing, then its raid
    assert order.index("dome_1") < order.index("lander_deimos") < order.index("lander_rock") < order.index("ast_2")
    assert order.index(ss.VIP_SCENE) < order.index("lander_europa") < order.index("lander_titan") < order.index(ss.ACT3_ATTACK)
    assert order.index("up_phenix_1") < order.index("lander_triton") < order.index("final_1")
    assert order.index("paint_1") + 1 == order.index(ss.VIP_SCENE)


@pytest.mark.parametrize("mid", ["lander_deimos", "raid_deimos"])
def test_the_scene_is_told_before_the_first_flight_and_not_again(mid):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["flags"]["dome_s2"] = True
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "map"
    hub.map_index = [m["id"] for m in hub.missions()].index(mid)
    assert hub._hub_confirm() is None and hub.screen == "intro" and hub.scene_id == mid and hub.scene_launch
    assert hub.intro_slides == list(ss.scene_of(mid)["slides"])
    ss.mark_scene_seen(hub.state, mid)
    hub.screen = "hub"
    assert hub._hub_confirm()["id"] == mid


def test_the_journal_lists_them_once_seen():
    st = ss.create_slot(1, "NOVA", "normal")
    for mid in ("raid_deimos", "lander_deimos", "dome_1"):
        ss.mark_scene_seen(st, mid)
    entries = ss.journal_entries(st)
    i = entries.index({"scene": "dome_1"})
    assert entries[i + 1] == {"scene": "lander_deimos"} and entries[i + 2] == {"scene": "raid_deimos"}
    assert t("story_log_scene").format(title=t("story_m_raid1")) in [ss.log_text(e, t) for e in entries]


def test_the_ten_pictures_are_there_and_widescreen():
    import os

    import pygame
    from settings import asset_path
    for mid in MISSIONS:
        pic = ss.scene_of(mid)["slides"][0][0]
        path = asset_path("story", pic + ".jpg")
        assert os.path.isfile(path), pic
        w, h = pygame.image.load(path).get_size()
        assert w >= 1280 and abs(w / h - 16 / 9) < 0.01, pic
