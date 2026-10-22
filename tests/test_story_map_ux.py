"""Adventure ergonomics: the map opens after the intro, ordered by kind, with its cursor on the next mission, hints on
locked missions and workshop rows; the HUD dome reminder; the workshop (MAX rows last, scroll arrows)."""
from types import SimpleNamespace

import pygame
import pytest

import draw_frame
import i18n
import story
import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)


def _fresh(phenix=False, intro_seen=True):
    st = ss.create_slot(1, "NOVA", "normal")
    if intro_seen:
        ss.mark_intro_seen(st)
    if phenix:
        st["slots"][1]["owned"] = True
    return st


def _hub(st):
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


def _ids(missions):
    return [m["id"] for m in missions]


# ------------------------------------------------------------------ landing
def test_intro_lands_on_the_map_with_the_cursor_on_the_first_sortie(run):
    st = _fresh(intro_seen=False)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub._maybe_intro()
    assert hub.screen == "intro"
    hub._end_intro()
    assert hub.screen == "hub" and hub.pane == "map"
    assert hub.missions()[hub.map_index]["id"] == "ch1_sortie"


def test_cursor_follows_the_next_mission_after_a_win(run):
    st = _fresh()
    first = ss.mission_by_id("ch1_sortie")
    st["cleared"] = ["ch1_sortie"]
    for f in first["unlock"]:
        st["flags"][f] = True
    hub = _hub(st)
    rows = hub.missions()
    nxt = ss.next_mission(hub.state, rows)
    assert nxt["id"] == "best_s2"                      # the hunt just won is replayable, but it is not "next"
    assert rows[hub.map_index]["id"] == "best_s2"


# ------------------------------------------------------------------ order
def test_act1_hunts_first_then_the_story_in_table_order():
    st = _fresh()
    rows = ss.visible_missions(st)
    groups = [ss.mission_group(m) for m in rows]
    assert groups == sorted(groups, key=lambda g: ss.GROUP_ORDER[1].index(g))     # grouped, no interleaving
    assert groups[0] == ss.GROUP_HUNT
    story_ids = [m["id"] for m in rows if ss.mission_group(m) == ss.GROUP_STORY]
    table = [m["id"] for m in ss.MISSIONS if m["id"] in story_ids]
    assert story_ids == table                         # inside a group the table order is kept


def test_act2_story_comes_before_the_hunts():
    st = _fresh(phenix=True)
    st["act"] = 2
    groups = [ss.mission_group(m) for m in ss.visible_missions(st)]
    assert ss.GROUP_STORY in groups and ss.GROUP_HUNT in groups
    assert groups.index(ss.GROUP_STORY) < groups.index(ss.GROUP_HUNT)


def test_cheat_unlock_keeps_the_table_order():
    st = _fresh()
    cheat = ss.visible_missions(st, cheat=True)
    table = [m["id"] for m in ss.MISSIONS if m["id"] in set(_ids(cheat))]
    assert _ids(cheat) == table


def test_next_mission_is_the_first_playable_not_won_one():
    st = _fresh()
    rows = ss.visible_missions(st)
    nxt = ss.next_mission(st, rows)
    assert nxt is not None and ss.mission_playable(st, nxt) and not ss.mission_done(st, nxt)
    assert not nxt.get("test")
    before = rows[: rows.index(nxt)]
    assert not any(ss.mission_playable(st, m) and not ss.mission_done(st, m) and not m.get("test") for m in before)


def test_next_mission_is_none_when_nothing_is_left():
    assert ss.next_mission(_fresh(), []) is None


# ------------------------------------------------------------------ hints
def test_locked_mission_names_what_opens_it():
    st = _fresh()
    locked = [m for m in ss.visible_missions(st) if not ss.mission_open(st, m)]
    assert locked
    for m in locked:
        hint = ss.unlock_hint(st, m)
        assert hint is not None, m["id"]
        assert hint["id"] != m["id"]


def test_open_mission_has_no_hint():
    st = _fresh()
    first = ss.visible_missions(st)[0]
    assert ss.mission_open(st, first)
    assert ss.unlock_hint(st, first) is None
    assert ss.unlock_hint(st, None) is None


def test_paint_mission_asks_for_the_previous_paint_mission():
    st = _fresh(phenix=True)
    st["act"] = 2
    p2 = ss.mission_by_id("paint_2")
    if ss.mission_open(st, p2):
        pytest.skip("paint_2 already open")
    assert ss.unlock_hint(st, p2)["id"] == "paint_1"


def test_map_draws_group_heads_and_the_hint(run, monkeypatch):
    hub = _hub(_fresh())
    seen = []
    real = story._text_fit

    def spy(surface, font, text, *a, **k):
        seen.append(text)
        return real(surface, font, text, *a, **k)

    monkeypatch.setattr(story, "_text_fit", spy)
    surf = pygame.Surface((1280, 720))
    small = pygame.font.Font(None, 24)
    rows = hub.missions()
    for i, m in enumerate(rows):
        hub.map_index = i
        seen.clear()
        hub._draw_map(surf, small, small, small)
        hint = ss.unlock_hint(hub.state, m)
        want = i18n.t("story_unlock_after").format(name=i18n.t(hint["title"])) if hint else None
        assert (want in seen) if want else not any(x.startswith(i18n.t("story_unlock_after")[:8]) for x in seen), m["id"]
    seen.clear()
    hub.map_index = 0
    hub._draw_map(surf, small, small, small)
    assert i18n.t("story_grp_hunt") in seen and i18n.t("story_grp_story") in seen


@pytest.mark.parametrize("code", i18n.LANG_CODES)
def test_new_map_texts_exist_in_every_language(code):
    old = i18n.get_lang()
    i18n.set_lang(code)
    try:
        for key in ("story_grp_story", "story_grp_hunt", "story_grp_extra", "story_next"):
            assert i18n.t(key) and i18n.t(key) != key
        assert "{name}" in i18n.t("story_unlock_after")
    finally:
        i18n.set_lang(old)


# ------------------------------------------------------------------ HUD dome
def _g(dome, ship):
    return SimpleNamespace(adventure={"dome": dome}, ship_id=ship)


def test_dome_reminder_only_for_a_shield_without_dome():
    assert draw_frame.dome_offline(_g(False, "shield"))
    assert not draw_frame.dome_offline(_g(True, "shield"))
    assert not draw_frame.dome_offline(_g(False, "phoenix"))       # the Phenix never had a dome
    assert not draw_frame.dome_offline(SimpleNamespace(adventure=None, ship_id="shield"))
    assert not draw_frame.dome_offline(SimpleNamespace(ship_id="shield"))     # arcade: no adventure


def test_dome_reminder_is_not_glued_to_the_title():
    assert draw_frame.DOME_HUD_Y >= 16 + 30


# ------------------------------------------------------------------ workshop
def test_maxed_rows_go_last():
    st = _fresh()
    for f in ("ch1_speed", "ch1_life_2", "ch1_wall", "dome_online"):
        st["flags"][f] = True
    st["credits"] = 100000
    assert ss.buy(st, "speed_60")
    rows = ss.shop_for(st)
    notes = [ss.upgrade_note(st, r[0]) == "story_owned" for r in rows]
    assert any(notes)
    assert notes == sorted(notes)                      # False... then True...: the finished rows are at the bottom
    assert rows[0][0] != "speed_60"


def test_locked_row_names_its_mission(run):
    hub = _hub(_fresh())
    locked = [r for r in hub.shop_rows() if ss.upgrade_note(hub.state, r[0]) == "story_locked"]
    assert locked
    for sid, label, cost, need in locked:
        src = ss.shop_after(hub.state, sid)
        assert src is not None, sid
        text = hub._shop_extra(sid, cost, True)
        assert text == i18n.t("story_unlock_after").format(name=i18n.t(src["title"]))


def test_open_row_has_no_after():
    st = _fresh()
    st["flags"]["ch1_speed"] = True
    assert ss.shop_after(st, "speed_60") is None
    assert ss.shop_after(st, "nope") is None


@pytest.mark.parametrize("act", [1, 3])
def test_shop_arrows_are_drawn_only_when_rows_are_hidden(run, act):
    st = _fresh()
    st["act"] = act
    hub = _hub(st)
    hub.pane = "hangar"
    hub.zone = "shop"
    surf = pygame.Surface((1280, 720))
    small = pygame.font.Font(None, 24)
    rows = hub.shop_rows()
    ARROW = (255, 190, 110)

    def arrows():
        box = pygame.Rect(70, 308, 1280 - 140, 328)
        ax = box.right - 14
        up = surf.get_at((ax, box.y + 33))[:3] == ARROW
        dn = surf.get_at((ax, box.y + 46 + story.SHOP_WINDOW * 40 + 8))[:3] == ARROW
        return up, dn

    hub.shop_index = 0
    surf.fill((0, 0, 0))
    hub._draw_shop(surf, small)
    up, dn = arrows()
    assert (len(rows) > story.SHOP_WINDOW) == (act == 3)
    if len(rows) > story.SHOP_WINDOW:
        assert dn and not up
        hub.shop_index = len(rows) - 1
        surf.fill((0, 0, 0))
        hub._draw_shop(surf, small)
        up, dn = arrows()
        assert up and not dn
    else:
        assert not up and not dn


# ------------------------------------------------------------------ after a mission
def _after_first_sortie():
    st = _fresh()
    st["cleared"] = ["ch1_sortie"]
    for f in ss.mission_by_id("ch1_sortie")["unlock"]:
        st["flags"][f] = True
    return _hub(st)


def test_cursor_leaves_a_won_story_mission_for_the_next_one(run):
    hub = _after_first_sortie()
    rows = hub.missions()
    hub.map_index = _ids(rows).index("dome_1")
    hub.apply_result("dome_1", 2000, True, {"bird1": 10})
    rows = hub.missions()
    nxt = ss.next_mission(hub.state, rows)
    assert nxt is not None and nxt["id"] != "dome_1"
    assert rows[hub.map_index]["id"] == nxt["id"]


def test_cursor_stays_on_a_replayable_hunt(run):
    hub = _after_first_sortie()
    rows = hub.missions()
    hub.map_index = _ids(rows).index("ch1_sortie")
    hub.apply_result("ch1_sortie", 1500, True, {"bird1": 10})
    assert hub.missions()[hub.map_index]["id"] == "ch1_sortie"


def test_shield_wall_immune_label_is_spelled_out_in_french():
    old = i18n.get_lang()
    i18n.set_lang("fr")
    try:
        assert i18n.t("story_wall_immune") == "IMMUNISÉ"
    finally:
        i18n.set_lang(old)
