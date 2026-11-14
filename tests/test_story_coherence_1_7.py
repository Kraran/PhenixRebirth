"""The incoherences found in the full Adventure playthrough of version 1.7: the Silent Sentinels come before la Riposte on
the map, the map never suggests an optional mission (the paint series, a BONUS), and the texts that said otherwise."""
import json
import os

import i18n
import story_state as ss

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _act3(**flags):
    st = ss.create_slot(1, "NOVA", "normal")
    st["act"] = 3
    st["flags"].update({"act2": True, "phobos_s3": True}, **flags)
    return st


def test_neptune_comes_before_triton_on_the_map():
    st = _act3(sentinelle_3=True)
    rows = ss.visible_missions(st)
    ids = [m["id"] for m in rows]
    assert ids.index("sentinelle_4") < ids.index("final_1")
    assert ss.next_mission(st, rows)["id"] == "sentinelle_4"


def test_the_sentinels_stay_optional_for_la_riposte():
    st = _act3()
    final_1 = ss.mission_by_id("final_1")
    assert ss.mission_playable(st, final_1)
    assert ss.next_mission(st, ss.visible_missions(st))["id"] in ("sentinelle_1", "final_1")


def test_the_paint_series_is_never_suggested():
    st = _act3()
    paint = ss.mission_by_id("paint_1")
    assert ss.mission_playable(st, paint) and not ss.mission_done(st, paint)
    assert ss.next_mission(st, [paint]) is None


def test_no_optional_or_final_bonus_mission_is_ever_suggested():
    for m in ss.MISSIONS:
        if ss.mission_group(m) in (ss.GROUP_EXTRA, ss.GROUP_FINAL):
            st = ss.create_slot(1, "NOVA", "normal")
            st["flags"] = {name: True for name in ([m.get("need")] if m.get("need") else [])}
            assert ss.next_mission(st, [m]) is None, m["id"]


def test_the_last_sentinel_still_makes_sense_after_the_nest_is_destroyed():
    for code in ("fr", "en"):
        text = i18n.T["story_scene_sent4"][code]
        assert "d’où viennent" not in text and "finally know where" not in text
        assert "Neptune" in text


def test_the_commander_text_names_the_birds_that_really_come():
    fr = i18n.T["story_scene_bestboss"]["fr"]
    assert "vertes" not in fr and "Les Bleus et les Kakis" in fr
    for name in os.listdir(os.path.join(ROOT, "assets", "lang")):
        with open(os.path.join(ROOT, "assets", "lang", name), encoding="utf-8") as f:
            data = json.load(f)
        for key in ("story_scene_bestboss", "story_scene_bestboss_v"):
            assert key in data, (name, key)
            assert "green" not in data[key].lower(), (name, key)


def test_the_act4_text_has_typographic_apostrophes():
    fr = i18n.T["story_scene_act4"]["fr"]
    assert "'" not in fr and "porte-aéronefs" in fr
    assert "n’irai pas" in i18n.T["story_scene_paint_1"]["fr"]
