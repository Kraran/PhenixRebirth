"""Every secret code of the game, typed the way the player types it (real key events), one test each."""
from types import SimpleNamespace

import pygame
import pytest

import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)


def _scores_screen(run):
    g = run.game
    g.started, g.game_over, g.used_cheat = False, False, False
    g.cheat_live = g.phenix_cheat = False
    g.cheat_buffer = ""
    g.menu_screen = "highscores"
    g.input_grace = 0.0
    return g


def _keys(run, text):
    for ch in text:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=ord(ch.lower()), unicode=ch, mod=0, scancode=0))
        run.frames(1)


@pytest.mark.parametrize("n", [2, 3, 5, 10, 15, 20, 31, 50, 75, 99])
def test_lvxx_starts_the_stages_from_02_to_99(run, n):
    g = _scores_screen(run)
    _keys(run, "LV%02d" % n)
    assert g.started and g.stage == n and g.used_cheat
    g.player.infinite_lives = True
    run.frames(3)


@pytest.mark.parametrize("code", ["LV00", "LV01"])
def test_lv00_and_lv01_do_nothing(run, code):
    g = _scores_screen(run)
    _keys(run, code)
    assert not g.started


def test_live(run):
    g = _scores_screen(run)
    _keys(run, "LIVE")
    assert g.cheat_live and g.player.infinite_lives and g.player.lives == 99 and g.used_cheat


def test_phen(run):
    g = _scores_screen(run)
    _keys(run, "PHEN")
    assert g.phenix_cheat and g.player.phenix_auto_refill and g.player.phenix_gauge == 10 and g.used_cheat


def test_vnov_toggles(run):
    g = _scores_screen(run)
    g.cheat_vn = False
    _keys(run, "VNOV")
    assert g.cheat_vn is True
    _keys(run, "VNOV")
    assert g.cheat_vn is False


def test_codes_stack(run):
    g = _scores_screen(run)
    _keys(run, "LIVEPHENLV07")
    assert g.stage == 7 and g.player.infinite_lives and g.player.phenix_auto_refill


def _ev(ch):
    return SimpleNamespace(key=ord(ch.lower()), unicode=ch)


def _hub(pane):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = pane
    return hub


def _type(hub, text):
    for c in text:
        hub.type_key(_ev(c))


def test_unlk_on_the_map():
    hub = _hub("map")
    _type(hub, "UNLK")
    assert hub.cheat_unlock and hub.cheating


def test_2222_on_the_map_goes_to_act_2():
    hub = _hub("map")
    _type(hub, "2222")
    assert hub.state["act"] == 2 and hub.cheating


def test_3333_on_the_map_plays_the_phobos_attack_then_act_3():
    hub = _hub("map")
    _type(hub, "3333")
    assert hub.cheating and hub.screen == "intro" and hub.scene_id == ss.ACT3_ATTACK
    hub._end_intro()
    hub.nav_h(0)
    hub.confirm()
    hub.nav_h(1)
    hub.confirm()
    assert hub.state["act"] == 3


def test_nix2_in_the_hangar():
    hub = _hub("hangar")
    _type(hub, "NIX2")
    assert hub.cheating and ss.flag(hub.state, "phenix_s1")


@pytest.mark.parametrize("code,pane", [("UNLK", "hangar"), ("2222", "hangar"), ("3333", "hangar"), ("NIX2", "map")])
def test_story_codes_only_work_on_their_own_pane(code, pane):
    hub = _hub(pane)
    _type(hub, code)
    assert not hub.cheating and hub.state["act"] == 1 and hub.screen != "intro"
