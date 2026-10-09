"""The hangar drawn like the ship select screen, the ship that flies the missions, the ACT2 cheat."""
from types import SimpleNamespace

import pygame
import pytest

import story
import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

HUNTS = ["ch1_sortie", "best_s2", "best_s3", "best_s4"]
PHENIX = ["phenix_1", "phenix_2", "phenix_3", "phenix_4", "phenix_5"]
PAINT = ["paint_1", "paint_2", "paint_3"]


def _state(phenix=True, selected=0):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    if phenix:
        st["slots"][1]["owned"] = True
    st["selected_slot"] = selected
    return st


def _hub(st):
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


def _type(hub, text):
    return [hub.type_key(SimpleNamespace(key=ord(c.lower()), unicode=c)) for c in text]


def _file():
    with open(ss.story_path(1), "rb") as f:
        return f.read()


def _ids(missions):
    return [m["id"] for m in missions]


# ------------------------------------------------------------------ the hangar drawing
def _markers(hub):
    """Plain coloured blocks instead of the real portraits: easy to find on the picture."""
    hub._ensure_art()
    for key, rgb in (("shield_red", (4, 5, 6)), ("shield_green", (7, 8, 9)), ("shield_violet", (10, 11, 12)),
                     ("phoenix", (13, 14, 15))):
        big = pygame.Surface((60, 60))
        big.fill(rgb)
        hub._portraits[key] = big
        dim = pygame.Surface((60, 60))
        dim.fill((rgb[0] + 100, rgb[1] + 100, rgb[2] + 100))
        hub._greyed[key] = dim


def _draw(hub, run):
    surf = pygame.Surface((1280, 720))
    g = run.game
    hub.draw(surf, g.font, g.medium_font, g.font)
    return surf


def _px(surf, x, y):
    return tuple(surf.get_at((x, y)))[:3]


LEFT = (400, 110)      # the middle of the first hull frame (above its name)
RIGHT = (880, 110)     # the middle of the second one


def test_the_chosen_hull_is_lit_and_the_other_one_dimmed(run):
    hub = _hub(_state(selected=0))
    hub.pane = "hangar"
    _markers(hub)
    hub.anim_t = 0.0
    surf = _draw(hub, run)
    assert _px(surf, *LEFT) == (4, 5, 6) and _px(surf, *RIGHT) == (113, 114, 115)
    hub.state["selected_slot"] = 1
    surf = _draw(hub, run)
    assert _px(surf, *LEFT) == (104, 105, 106) and _px(surf, *RIGHT) == (13, 14, 15)


def test_the_chosen_frame_is_gold_and_the_other_one_is_plain(run):
    hub = _hub(_state(selected=1))
    hub.pane = "hangar"
    _markers(hub)
    surf = _draw(hub, run)
    assert _px(surf, 180, 54 + 80) == (70, 70, 90)                 # the left frame, not chosen
    assert _px(surf, 1099, 54 + 80) == (255, 210, 90)         # the right frame, chosen


def test_the_chosen_hull_keeps_the_gold_frame_whatever_the_cursor(run):
    hub = _hub(_state(selected=0))
    hub.pane = "hangar"
    _markers(hub)
    gold = []
    for zone in ("slots", "shop"):
        hub.zone = zone
        gold.append(_px(_draw(hub, run), 180, 54 + 80))
    assert gold == [(255, 210, 90)] * 2


def test_a_hull_not_owned_yet_shows_nothing_about_itself(run):
    from i18n import t
    hub = _hub(_state(phenix=False))
    hub.pane = "hangar"
    _markers(hub)
    surf = _draw(hub, run)
    assert _px(surf, *RIGHT) != (13, 14, 15) and _px(surf, *RIGHT) != (113, 114, 115)
    assert _px(surf, 1099, 54 + 80) == (70, 70, 90)           # a plain frame
    # the picture of the Phenix is not even on screen
    seen = []
    real = story._text
    story._text = lambda s, f, text, *a, **k: (seen.append(str(text)), real(s, f, text, *a, **k))[1]
    try:
        _draw(hub, run)
    finally:
        story._text = real
    assert t("story_hull_empty") in seen


def test_only_the_chosen_hull_moves_and_nothing_animates(run):
    hub = _hub(_state(selected=0))
    hub.pane = "hangar"
    _markers(hub)
    hub.anim_t = 0.0
    a = _draw(hub, run)
    hub.anim_t = 0.5                                                   # a quarter of the bob period
    b = _draw(hub, run)
    other = pygame.Rect(660, 54, 440, 176)
    assert pygame.image.tobytes(a.subsurface(other), "RGB") == pygame.image.tobytes(b.subsurface(other), "RGB")
    assert pygame.image.tobytes(a.subsurface((180, 54, 440, 120)), "RGB") != \
        pygame.image.tobytes(b.subsurface((180, 54, 440, 120)), "RGB")        # a gentle bob only


def test_the_real_portraits_use_the_ship_select_size_and_dimming(run):
    hub = _hub(_state())
    hub._ensure_art()
    assert hub._portraits["shield_red"].get_height() == story.PORTRAIT_H
    assert story.GREY_MULT == (80, 80, 90, 160)                        # the dimming of the ship select screen
    pic, dim = hub._portraits["shield_red"], hub._greyed["shield_red"]
    for x in range(pic.get_width()):
        for y in range(pic.get_height()):
            r, g, b, a = pic.get_at((x, y))
            if a > 200 and r > 120:
                r2, g2, b2, a2 = dim.get_at((x, y))
                assert r2 <= r * 80 // 255 + 1 and a2 <= a * 160 // 255 + 1
                return
    pytest.fail("no bright pixel found")


def test_the_painted_shield_shows_its_colour(run):
    st = _state(selected=0)
    st["slots"][0]["tint"] = "violet"
    hub = _hub(st)
    hub.pane = "hangar"
    _markers(hub)
    assert _px(_draw(hub, run), *LEFT) == (10, 11, 12)


def test_the_stats_follow_the_chosen_hull(run):
    from i18n import t
    hub = _hub(_state(selected=1))
    hub.pane = "hangar"
    seen = []
    real = story._text
    story._text = lambda s, f, text, *a, **k: (seen.append(str(text)), real(s, f, text, *a, **k))[1]
    try:
        _draw(hub, run)
    finally:
        story._text = real
    assert t("story_stat_phenix") in seen and t("story_stat_dome") not in seen


# ------------------------------------------------------------------ the ship that flies
def test_the_missions_fly_the_chosen_hull(run):
    g = run.game
    st = _state(selected=1)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = 0
    spec = g.story._launch_selected()
    assert "ship" not in spec
    g._begin_adventure(spec)
    assert g.player.ship_id == "phoenix"
    st["selected_slot"] = 0
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g._begin_adventure(g.story._launch_selected())
    assert g.player.ship_id == "shield"


def test_a_mission_can_impose_its_hull(run, monkeypatch):
    g = run.game
    st = _state(selected=1)                                           # the Phenix is chosen...
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    monkeypatch.setitem(ss.mission_by_id("ch1_sortie"), "ship", "shield")
    g.story.map_index = 0
    spec = g.story._launch_selected()
    assert spec["ship"] == "shield" and spec["dome"] is False
    g._begin_adventure(spec)
    assert g.player.ship_id == "shield"                                # ...but this mission flies the Shield


def test_an_imposed_hull_that_is_not_owned_falls_back():
    st = _state(phenix=False)
    assert ss.loadout(st, "phoenix")["ship_id"] == "shield"
    assert ss.loadout(st, "shield")["ship_id"] == "shield"
    assert ss.loadout(st, "nope")["ship_id"] == "shield"
    st = _state(selected=1)
    assert ss.loadout(st)["ship_id"] == "phoenix" and ss.loadout(st, "shield")["ship_id"] == "shield"
    assert ss.loadout(st, "phoenix")["ship_id"] == "phoenix"


def test_the_map_says_which_ship_flies(run):
    from i18n import t
    for selected, name in ((0, t("ship_shield")), (1, t("ship_phoenix"))):
        hub = _hub(_state(selected=selected))
        hub.pane = "map"
        seen = []
        real = story._text
        story._text = lambda s, f, text, *a, **k: (seen.append(str(text)), real(s, f, text, *a, **k))[1]
        try:
            _draw(hub, run)
        finally:
            story._text = real
        assert t("story_ship_label").format(name=name) in seen


# ------------------------------------------------------------------ ACT2
def test_the_jump_gives_the_save_of_a_pilot_who_finished_act_1():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.jump_to_act2(st)
    assert st["act"] == 2 and ss.flag(st, "act2") and ss.flag(st, "dome_online") and ss.flag(st, "ch1_speed")
    assert "act2_gate" in st["cleared"] and "ch2_tease" not in st["cleared"]
    assert _ids(ss.visible_missions(st)) == HUNTS + ["best_boss"] + PHENIX + PAINT
    assert ss.mission_playable(st, ss.mission_by_id("phenix_1")) and not ss.mission_playable(st, ss.mission_by_id("phenix_2"))
    assert ss.mission_playable(st, ss.mission_by_id("paint_1"))
    assert all(ss.mission_playable(st, ss.mission_by_id(m)) for m in HUNTS)
    assert st["log"] == [] and st["credits"] == 0 and not st["slots"][1]["owned"]


def test_the_jump_can_be_done_twice():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.jump_to_act2(st)
    first = dict(st, cleared=list(st["cleared"]))
    ss.jump_to_act2(st)
    assert st["cleared"] == first["cleared"] and st["act"] == 2


def test_act2_typed_on_the_map_goes_to_act_2_and_saves_nothing():
    hub = _hub(_state(phenix=False))
    hub.pane = "map"
    before = _file()
    assert _type(hub, "2222") == [False, False, False, False]          # the keys still work as menu keys
    assert hub.cheat_act2 and hub.cheating and not hub.cheat_unlock
    assert hub.state["act"] == 2 and hub.map_index == 0
    assert _ids(hub.missions()) == HUNTS + ["best_boss"] + PHENIX + PAINT
    from i18n import t
    assert hub.toast == t("story_cheat_act2")
    hub.apply_result("phenix_1", 300, True)
    hub.save()
    assert _file() == before                                           # not a byte written
    assert hub.state["credits"] == 300                                 # but the cheated game goes on in memory


def test_nothing_is_saved_whatever_happens_after_act2():
    hub = _hub(_state())
    hub.pane = "map"
    before = _file()
    _type(hub, "2222")
    hub.state["credits"] = 5000
    hub.pane = "hangar"
    hub.zone = "shop"
    hub.shop_index = 0
    hub.confirm()
    hub.apply_result("ch1_sortie", 10, False)
    hub.apply_result("ch1_sortie", 10, True)
    assert _file() == before


def test_loading_the_save_again_clears_the_cheat():
    hub = _hub(_state(phenix=False))
    hub.pane = "map"
    _type(hub, "2222")
    hub.open_slot(1)
    assert not hub.cheat_act2 and not hub.cheating and hub.state["act"] == 1
    assert _ids(hub.missions())[-1] == "ch2_tease"


def test_act2_typed_elsewhere_does_nothing():
    hub = _hub(_state(phenix=False))
    for pane in ("hangar", "log", "bestiary"):
        hub.pane = pane
        _type(hub, "2222")
        assert not hub.cheat_act2 and hub.state["act"] == 1, pane


def test_a_pilot_already_in_act_2_keeps_his_progress():
    st = _state(phenix=False)
    st["act"] = 2
    st["flags"].update(act2=True)
    st["cleared"] = ["phenix_1"]
    hub = _hub(st)
    hub.pane = "map"
    _type(hub, "2222")
    assert hub.cheat_act2 and hub.state["cleared"] == ["phenix_1"]     # nothing is reset or added


def test_act2_then_unlk_lists_everything_and_keeps_the_focus():
    hub = _hub(_state(phenix=False))
    hub.pane = "map"
    _type(hub, "2222")
    hub.map_index = _ids(hub.missions()).index("phenix_1")
    _type(hub, "UNLK")
    assert hub.cheat_unlock and hub.cheat_act2 and hub._mission()["id"] == "phenix_1"


def test_digits_and_letters_still_reach_the_menu_keys():
    hub = _hub(_state())
    hub.pane = "map"
    assert _type(hub, "A2") == [False, False]
    assert not hub.cheat_act2


def test_the_banner_shows_for_act2_too(run):
    from i18n import t
    hub = _hub(_state(phenix=False))
    hub.pane = "map"
    _type(hub, "2222")
    hub.toast = ""
    seen = []
    real = story._text_fit
    story._text_fit = lambda s, f, text, *a, **k: (seen.append(str(text)), real(s, f, text, *a, **k))[1]
    try:
        _draw(hub, run)
    finally:
        story._text_fit = real
    assert t("story_cheat_banner") in seen


def test_the_act_2_map_title_shows_after_the_cheat(run):
    from i18n import t
    hub = _hub(_state(phenix=False))
    hub.pane = "map"
    _type(hub, "2222")
    seen = []
    real = story._text
    story._text = lambda s, f, text, *a, **k: (seen.append(str(text)), real(s, f, text, *a, **k))[1]
    try:
        _draw(hub, run)
    finally:
        story._text = real
    assert t("story_ch2") in seen
