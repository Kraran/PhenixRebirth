"""UNLK: typed on the mission map, opens every mission and stops all saving until the slot is reloaded."""
import os
from types import SimpleNamespace

import pygame

import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)


def _ev(ch):
    return SimpleNamespace(key=ord(ch.lower()), unicode=ch)


def _type(hub, text):
    return [hub.type_key(_ev(c)) for c in text]


def _hub(pane="map", **flags):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["flags"].update(flags)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = pane
    return hub


def _file():
    with open(ss.story_path(1), "rb") as f:
        return f.read()


def _mission_index(mission_id):
    return [m["id"] for m in ss.MISSIONS].index(mission_id)


# ------------------------------------------------------------------ the code
def test_typing_unlk_on_the_map_turns_the_cheat_on():
    hub = _hub()
    assert not hub.cheat_unlock
    _type(hub, "UNLK")
    assert hub.cheat_unlock and hub.toast


def test_the_letters_are_not_swallowed_so_the_menu_keys_still_work():
    hub = _hub()
    assert _type(hub, "UNLK") == [False, False, False, False]
    assert _type(hub, "adqwsz") == [False] * 6


def test_lower_case_and_earlier_letters_do_not_matter():
    hub = _hub()
    _type(hub, "xxunlk")
    assert hub.cheat_unlock
    other = _hub()
    _type(other, "UNL")
    _type(other, "UNK")
    assert not other.cheat_unlock
    _type(other, "KNLU")
    assert not other.cheat_unlock


def test_the_code_only_works_on_the_mission_map():
    for pane in ("hangar", "log", "bestiary"):
        hub = _hub(pane)
        _type(hub, "UNLK")
        assert not hub.cheat_unlock, pane
    hub = _hub("hangar")
    _type(hub, "UNL")
    hub.pane = "map"
    _type(hub, "K")
    assert not hub.cheat_unlock                      # letters typed elsewhere do not count


def test_the_code_is_ignored_while_typing_a_name():
    hub = StoryHub()
    hub.screen = "slots"
    _type(hub, "UNLK")
    assert not hub.cheat_unlock


# ------------------------------------------------------------------ missions
def test_without_the_code_a_locked_mission_cannot_be_launched():
    hub = _hub()
    hub.map_index = _mission_index("best_s3")
    assert not hub.mission_playable(hub._mission())
    assert hub._launch_selected() is None


def test_with_the_code_every_playable_mission_can_be_launched():
    hub = _hub()
    _type(hub, "UNLK")
    for i, m in enumerate(ss.MISSIONS):
        hub.map_index = i
        want = m.get("playable") is not False and int(m.get("content") or 0) > 0
        assert hub.mission_playable(m) == want, m["id"]
        assert hub.mission_open(m)
        assert (hub._launch_selected() is not None) == want, m["id"]
    assert hub.mission_playable(None) is False


def test_the_state_rule_function_knows_the_cheat_too():
    st = ss.default_state()
    locked = ss.mission_by_id("best_s3")
    assert not ss.mission_playable(st, locked)
    assert ss.mission_playable(st, locked, cheat=True)
    assert not ss.mission_playable(st, ss.mission_by_id("ch2_tease"), cheat=True)


# ------------------------------------------------------------------ saving
def test_nothing_is_saved_while_the_cheat_is_on():
    hub = _hub(ch1_speed=True)
    before = _file()
    _type(hub, "UNLK")
    hub.state["credits"] = 99999
    hub.save()
    hub.apply_result("ch1_sortie", 500, True, {"bird1": 9})
    hub.state["credits"] = 5000
    assert hub._buy(next(r for r in __import__("story").SHOP if r[0] == "speed_60"))
    assert _file() == before
    assert hub.state["credits"] == 5000 - 300            # the game still plays in memory


def test_without_the_cheat_the_same_actions_are_saved():
    hub = _hub()
    before = _file()
    hub.apply_result("ch1_sortie", 500, True, {"bird1": 9})
    assert _file() != before
    assert ss.load_state(ss.story_path(1))["credits"] == 500


def test_reloading_the_slot_starts_clean_and_saving_works_again():
    hub = _hub()
    _type(hub, "UNLK")
    hub.apply_result("ch1_sortie", 500, True)
    assert hub.cheat_unlock
    hub.open_slot(1)                                     # reload the save
    assert not hub.cheat_unlock and hub.cheat_buf == ""
    assert hub.state["credits"] == 0                     # the cheated progress is gone
    hub.apply_result("ch1_sortie", 70, True)
    assert ss.load_state(ss.story_path(1))["credits"] == 70


def test_the_cheat_does_not_follow_to_another_slot():
    hub = _hub()
    _type(hub, "UNLK")
    ss.create_slot(2, "TWO", "normal")
    hub.open_slot(2)
    assert not hub.cheat_unlock


def test_a_red_banner_shows_while_the_cheat_is_on(run):
    import story
    from i18n import t
    seen = []
    real = story._text

    def spy(surface, font, text, *a, **k):
        seen.append(str(text))
        return real(surface, font, text, *a, **k)

    hub = _hub()
    g = run.game
    story._text = spy
    try:
        hub.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
        assert t("story_cheat_banner") not in seen
        _type(hub, "UNLK")
        hub.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
        assert t("story_cheat_banner") in seen
    finally:
        story._text = real


# ------------------------------------------------------------------ through the real keyboard
def test_the_real_keyboard_path_reaches_the_code(run):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    g.menu_screen = "story_hub"
    g.story.open_slot(1)
    g.story.pane = "map"
    g.input_grace = 0
    for ch in "unlk":
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=ord(ch), unicode=ch, mod=0, scancode=0))
        run.frames(2)
    assert g.story.cheat_unlock
    assert g.menu_screen == "story_hub"
