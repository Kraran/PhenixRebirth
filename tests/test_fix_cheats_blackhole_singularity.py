"""Three fixes: the codes typed on the high-score screen (AZERTY digits, the codes of the Adventure), no black hole behind the
missions of the Adventure, and the Singularity Core that falls in its BONUS mission."""
import random

import pygame
import pytest

import main_menu
import starfield
import story_items as si
import story_state as ss
from cheat_keys import cheat_char
from test_smoke import run  # noqa: F401  (fixture)


# ---------------------------------------------------------------- the black hole
def _nebulae(adventure, n=400):
    kinds = set()
    for _ in range(n):
        kinds.add(starfield.Nebula(adventure=adventure).kind)
    return kinds


def test_no_black_hole_behind_a_mission_of_the_adventure(run):
    random.seed(3)
    assert "galaxy_blackhole.png" not in _nebulae(True)
    assert len(_nebulae(True)) == len(starfield.NEBULA_FILES) - 1      # (all the others are still there)


def test_the_arcade_game_still_has_it(run):
    random.seed(3)
    assert "galaxy_blackhole.png" in _nebulae(False)


def test_the_starfield_of_a_mission_never_spawns_it_and_drops_the_one_in_the_sky(run):
    random.seed(5)
    sf = starfield.Starfield()
    sf.nebula = starfield.Nebula(filename="galaxy_blackhole.png")
    sf.set_adventure(True)
    assert sf.nebula is None                                           # the one of the menu leaves at once
    for _ in range(300):
        sf.nebula = None
        sf.nebula_timer = 0.0
        sf.planets = []
        sf.update(1.0, 0.0)
        if sf.nebula is not None:
            assert sf.nebula.kind != "galaxy_blackhole.png"


# ---------------------------------------------------------------- the Singularity Core
def _singularity_slot():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["act"] = 3
    st.setdefault("flags", {}).update({"ch3_speed": True})
    ss.save_state(ss.story_path(1), st)
    return st


def _launch_singularity(run):
    g = run.game
    _singularity_slot()
    g.story.open_slot(1)
    rows = g.story.missions()
    g.story.map_index = [m["id"] for m in rows].index("bonus_singularity")
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    return spec


def test_the_launch_carries_the_item_of_the_mission(run):
    spec = _launch_singularity(run)
    assert spec["drop"] == "singularity"
    plan = run.game.adventure["loot_plan"]
    assert plan and plan["id"] == "singularity" and plan["last_wave"]


def test_the_singularity_core_falls_and_can_be_caught(run):
    g = run.game
    _launch_singularity(run)
    g.player.infinite_lives = True
    for _ in range(900):
        if g.stage_transition is None:
            break
        run.frames(1)
    g.adventure["loot_clock"] = 999.0                                  # its time has come
    run.frames(3)
    assert g.loot is not None and g.loot.item == "singularity"
    g.player.x, g.player.y = g.loot.x, g.loot.y
    run.frames(2)
    assert g.adventure["loot"] == "singularity"


# ---------------------------------------------------------------- the codes
def test_the_digits_come_from_the_physical_key():
    azerty = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_AMPERSAND, unicode="&", mod=0, scancode=30)
    e_acute = pygame.event.Event(pygame.KEYDOWN, key=233, unicode="é", mod=0, scancode=31)
    zero = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_0, unicode="à", mod=0, scancode=39)
    keypad = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_KP2, unicode="2", mod=0, scancode=90)
    letter = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l, unicode="l", mod=0, scancode=15)
    assert [cheat_char(e) for e in (azerty, e_acute, zero, keypad, letter)] == ["1", "2", "0", "2", "l"]
    assert cheat_char(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LSHIFT, unicode="", mod=0, scancode=225)) == ""


def _scores(run):
    g = run.game
    g.started, g.game_over, g.used_cheat = False, False, False
    g.cheat_live = g.phenix_cheat = False
    g.cheat_buffer = ""
    g.story_cheats = []
    g.menu_screen = "highscores"
    g.input_grace = 0.0
    return g


def _type(run, text, azerty=False):
    digits = {"0": 39, "1": 30, "2": 31, "3": 32, "4": 33, "5": 34, "6": 35, "7": 36, "8": 37, "9": 38}
    for ch in text:
        if azerty and ch.isdigit():
            ev = pygame.event.Event(pygame.KEYDOWN, key=233, unicode="é", mod=0, scancode=digits[ch])
        else:
            ev = pygame.event.Event(pygame.KEYDOWN, key=ord(ch.lower()), unicode=ch, mod=0, scancode=0)
        pygame.event.post(ev)
        run.frames(1)


def test_a_stage_code_works_on_an_azerty_keyboard(run):
    g = _scores(run)
    _type(run, "LV07", azerty=True)
    assert g.started and g.stage == 7


@pytest.mark.parametrize("code", ["UNLK", "2222", "3333", "NIX2", "FINE"])
def test_the_codes_of_the_adventure_are_taken_on_the_scores(run, code):
    g = _scores(run)
    _type(run, code, azerty=True)
    assert g.story_cheats == [code] and g.menu_screen == "highscores"


def _open_pilot(run):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    g.menu_screen = "main"
    g.menu_index = main_menu.main_index("story")
    g._menu_confirm()
    story = g.story
    story.sel, story.col = 0, 0
    g.input_grace = 0.0
    g._menu_confirm()
    return story


def test_unlk_typed_on_the_scores_opens_every_mission(run):
    g = _scores(run)
    _type(run, "UNLK")
    story = _open_pilot(run)
    assert story.cheat_unlock and story.cheating and g.story_cheats == []


def test_2222_on_the_scores_goes_to_act_2(run):
    g = _scores(run)
    _type(run, "2222")
    story = _open_pilot(run)
    assert story.state["act"] == 2 and story.cheating


def test_3333_on_the_scores_starts_the_attack_on_phobos(run):
    g = _scores(run)
    _type(run, "3333")
    story = _open_pilot(run)
    assert story.cheating and story.scene_id == ss.ACT3_ATTACK


def test_nix2_on_the_scores_gives_the_phenix(run):
    g = _scores(run)
    _type(run, "NIX2")
    story = _open_pilot(run)
    assert story.cheating and ss.flag(story.state, "phenix_s1")


def test_fine_on_the_scores_starts_the_ending(run):
    g = _scores(run)
    _type(run, "FINE")
    story = _open_pilot(run)
    assert story.cheating and story.ending and story.scene_id == ss.ENDING_MISSION


def test_without_a_code_the_pilot_opens_normally(run):
    g = _scores(run)
    story = _open_pilot(run)
    assert not story.cheating and story.state["act"] == 1
