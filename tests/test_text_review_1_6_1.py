"""The review of the texts of the Adventure (1.6.1): Veteran variants of the scenes that count on the quantum anchor, "Acte" and not
"chapitre", the old gate texts, the NX01 on Phobos, the khaki skin, the Guardians and the Lander speaking to "tu", the paint shop
of the hull kept, Dôme I, Alcyone, and the small fixes of spelling."""
import json
import re

import pytest

import i18n
import story_state as ss
from story import StoryHub

SCENES_WITH_ANCHOR = {"ch1_sortie": "story_scene_sortie", "best_s3": "story_scene_best3", "best_s4": "story_scene_best4",
                      "best_boss": "story_scene_bestboss"}


def _say(key, lang):
    before = i18n.get_lang()
    i18n.set_lang(lang)
    try:
        return i18n.t(key)
    finally:
        i18n.set_lang(before)


# ------------------------------------------------------------------ Veteran: no anchor, Kamarasov is dead
@pytest.mark.parametrize("lang", ["fr", "en"])
@pytest.mark.parametrize("scene,key", sorted(SCENES_WITH_ANCHOR.items()))
def test_in_veteran_the_scenes_no_longer_count_on_the_anchor(scene, key, lang):
    slides = ss.scene_slides(scene, "veteran")
    assert slides and slides[0][1] == key + "_v"
    veteran, normal = _say(key + "_v", lang), _say(key, lang)
    assert not re.search(r"Kamarasov (a promis|promised)|ancrage quantique (fait|tient)|quantum anchor (does|keeps|holds)", veteran)
    assert re.search(r"Kamarasov (a promis|promised)|ancrage quantique (fait|tient)|quantum anchor (does|keeps|holds)", normal)
    assert ss.scene_slides(scene, "normal")[0][1] == key and ss.scene_slides(scene, "novice")[0][1] == key
    # only the paragraph that counts on the anchor is told differently
    assert veteran.split("\n\n")[:-1] == normal.split("\n\n")[:-1] and veteran != normal


def test_every_veteran_scene_has_its_text_in_each_language_that_has_the_normal_one():
    for lang in i18n.LANG_CODES:
        for key in SCENES_WITH_ANCHOR.values():
            if _say(key, lang) != key:
                assert _say(key + "_v", lang) != key + "_v", (lang, key)


def test_the_veteran_pilot_is_told_there_is_no_anchor():
    assert "pas d’ancrage" in _say("story_scene_sortie_v", "fr") and "Kamarasov est mort" in _say("story_scene_sortie_v", "fr")
    assert "no anchor" in _say("story_scene_sortie_v", "en")


# ------------------------------------------------------------------ Act, not chapter
def test_no_text_of_the_game_says_chapter_any_more():
    for key, entry in i18n.T.items():
        for lang in ("fr", "en"):
            text = entry.get(lang) or ""
            assert not re.search(r"chapitre|chapter", text, re.I), (key, lang)
    assert _say("story_ch1", "fr") == "ACTE 1 — SECTEUR OISEAUX" and _say("story_ch1", "en") == "ACT 1 — BIRD SECTOR"
    assert _say("story_log_sortie", "fr").startswith("Acte 1") and _say("story_phoenix_locked", "fr") == "Fin de l'acte 2"
    assert _say("story_m_ch2_b", "fr") == "Pas encore. Le Phenix se débloque en fin d'acte 2."


def test_the_old_gate_mission_has_no_text_about_the_dome_any_more():
    assert "story_m_gate" not in i18n.T and "story_m_gate_b" not in i18n.T
    for lang in ("fr", "en"):
        assert not re.search(r"dôme|dome", _say("story_log_gate", lang), re.I)


# ------------------------------------------------------------------ the scenes
def test_the_nx01_sleeps_in_orbit_of_mars_on_phobos():
    assert "là-bas" not in _say("story_scene_sortie", "fr") and "en orbite de Mars, sur Phobos, somnole le NX01" in _say("story_scene_sortie", "fr")
    assert "down there" not in _say("story_scene_sortie", "en") and "on Phobos, the NX01 lies dozing" in _say("story_scene_sortie", "en")


def test_the_khaki_birds_have_a_metallic_skin_not_plumage():
    for lang in ("fr", "en"):
        assert not re.search(r"plumage", _say("story_b_bird2_t", lang) + _say("ach_adv_kaki", lang), re.I)
    assert "peau métallique kaki" in _say("story_b_bird2_t", "fr") and "khaki metallic skin" in _say("story_b_bird2_t", "en")
    assert _say("ach_adv_kaki", "fr") == "Peau kaki" and _say("ach_adv_kaki", "en") == "Khaki Skin"


def test_kakis_and_bleus_are_written_the_same_way_everywhere():
    pat = re.compile(r"\b(?:les|Les|the|The) (kakis|bleus|khakis|blues)\b")
    for key, entry in i18n.T.items():
        for lang in ("fr", "en"):
            assert not pat.search(entry.get(lang) or ""), (key, lang)
    for lang in ("fr", "en"):
        for key in ("story_scene_best2", "story_scene_best3"):
            assert not pat.search(_say(key, lang)), (key, lang)
    assert "les Kakis arrivent en grappes" in _say("story_scene_best3", "fr") and "the Khakis come in clusters" in _say("story_scene_best3", "en")
    assert "oiseaux kaki" in _say("story_m_best2", "fr")                  # (the adjective stays as it is)


def test_the_vip_thanks_for_what_was_done_near_phobos():
    assert "à proximité de Phobos" in _say("story_vn5_r1", "fr") and "sur Phobos" not in _say("story_vn5_r1", "fr")
    assert "near Phobos" in _say("story_vn5_r1", "en")


def test_the_end_scene_is_more_than_two_years_after_the_silence():
    assert "plus de deux ans après le silence" in _say("story_scene_fin", "fr")
    assert "more than two years after the silence" in _say("story_scene_fin", "en")


def test_alcyone_is_440_light_years_away():
    for lang in ("fr", "en"):
        text = _say("story_scene_act4", lang)
        assert "440" in text and "409" not in text


def test_sentinelle_one_and_paint_one_read_well():
    assert "là où plus aucune construction humaine n’a survécu à la guerre" in _say("story_scene_sent1", "fr").replace("\n", " ")
    paint = _say("story_scene_paint_1", "fr")
    assert "coques magnifiques, le tout" in paint and "ce serait du délire" in paint and "ça serait" not in paint


def test_dome_one_has_the_name_of_its_scene():
    for lang in ("fr", "en"):
        assert _say("story_m_dome1", lang) == _say("story_scene_dome_1_t", lang)
    assert _say("story_m_dome1", "fr") == "Dôme I : l'épave du Shield"


def test_the_guardians_hint_says_phenix_without_an_accent():
    assert "Phénix" not in _say("story_guardians_hint", "fr") and "Phenix" in _say("story_guardians_hint", "fr")


# ------------------------------------------------------------------ "tu"
def test_the_guardians_and_the_lander_speak_to_tu():
    for key in ("story_guardians_clear", "story_guardians_retry", "story_lander_clear", "story_lander_retry"):
        text = _say(key, "fr")
        assert not re.search(r"\b[Vv]ous\b|\bvotre\b", text), key
        assert re.search(r"\b[Tt]u peux\b", text), key
    assert _say("story_lander_clear", "fr") == "Atterrissage réussi ! Tu peux recommencer à volonté."


# ------------------------------------------------------------------ the paint shop names the hull it works on
def _poor_hub(hull):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    st["credits"] = 0
    st["paint"] = {"step": 0, "runs": 0, "token": True}
    if hull == "phoenix":
        for sl in st["slots"]:
            if sl["id"] == "phoenix":
                sl["owned"] = True
        st["act3_ship"] = "phoenix"
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


@pytest.mark.parametrize("hull,name", [("shield", "Shield"), ("phoenix", "Phenix")])
@pytest.mark.parametrize("lang", ["fr", "en"])
def test_the_paint_shop_says_which_hull_costs_too_much(hull, name, lang):
    hub = _poor_hub(hull)
    assert (ss.paint_target(hub.state) or {}).get("id") == hull
    before = i18n.get_lang()
    i18n.set_lang(lang)
    try:
        hub._open_paint()
        assert name in hub.toast and "{" not in hub.toast and str(ss.paint_cost(hub.state)) in hub.toast
        other = "Shield" if hull == "phoenix" else "Phenix"
        assert other not in hub.toast
    finally:
        i18n.set_lang(before)


def test_the_other_languages_follow_the_paint_line_and_lose_the_old_gate_line():
    for code in i18n.LANG_CODES:
        if code in ("fr", "en"):
            continue
        with open(__import__("settings").asset_path("lang", code + ".json"), encoding="utf-8") as f:
            data = json.load(f)
        assert "story_log_gate" not in data
        if "story_paint_poor" in data:
            assert "{pts}" in data["story_paint_poor"]
            assert "{ship}" in data["story_paint_poor"] or code in ("pl", "tr")
