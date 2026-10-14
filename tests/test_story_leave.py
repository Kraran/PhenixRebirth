"""Leaving the Adventure for the normal game asks for a confirmation (B / Esc on the slot list)."""
import os

import pygame
import pytest

import story_state as ss
from i18n import t
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def clean_slots():
    def wipe():
        for i in range(1, ss.SLOT_COUNT + 1):
            for suffix in ("", ".corrupt"):
                try:
                    os.remove(ss.story_path(i) + suffix)
                except OSError:
                    pass
    wipe()
    yield
    wipe()


def _key(key, ch=""):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=ch, mod=0, scancode=0))


def _open_adventure(g):
    g.menu_screen = "main"
    g.menu_index = 1
    g.input_grace = 0
    g._menu_confirm()
    assert g.menu_screen == "story_hub" and g.story.screen == "slots"


# ------------------------------------------------------------------ the question
def test_back_on_the_slot_list_asks_before_leaving():
    hub = StoryHub()
    hub.open_slots()
    assert hub.back() is True and hub.screen == "leave"
    assert hub.del_yes is False                                      # NO is lit first


def test_back_on_the_question_cancels_it():
    hub = StoryHub()
    hub.open_slots()
    hub.back()
    assert hub.back() is True and hub.screen == "slots"
    hub.back()
    assert hub.back() is True and hub.screen == "slots"              # twice B in a row never leaves


def test_no_stays_in_the_adventure():
    hub = StoryHub()
    hub.open_slots()
    hub.back()
    assert hub.confirm() is None and hub.screen == "slots"


def test_yes_asks_the_game_to_leave():
    hub = StoryHub()
    hub.open_slots()
    hub.back()
    hub.nav_h(1)
    assert hub.del_yes is True
    assert hub.confirm() == {"leave": True}
    assert hub.screen == "slots" and hub.del_yes is False           # the next visit starts on the slot list


def test_the_buttons_move_in_both_directions_like_the_delete_question():
    hub = StoryHub()
    hub.open_slots()
    hub.back()
    hub.nav_h(1); assert hub.del_yes is True
    hub.nav_h(-1); assert hub.del_yes is False
    hub.nav_v(1); assert hub.del_yes is True
    hub.nav_v(-1); assert hub.del_yes is False


def test_the_question_comes_back_with_no_lit_each_time():
    hub = StoryHub()
    hub.open_slots()
    hub.back(); hub.nav_h(1); hub.back()                            # cancelled with YES lit
    hub.back()
    assert hub.screen == "leave" and hub.del_yes is False


def test_the_hangar_and_the_other_screens_still_walk_up_one_step_without_asking():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    assert hub.back() is True and hub.screen == "slots"             # hangar -> slot list: no question yet


def test_the_delete_question_is_not_changed():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slots()
    hub.col = 1
    hub.confirm()
    assert hub.screen == "delete" and hub.del_yes is False
    hub.nav_h(1)
    assert hub.del_yes is True
    hub.confirm()
    assert ss.slot_summary(1)["status"] == "missing" and hub.screen == "slots"


def test_the_texts_exist():
    assert t("story_leave_title") == "QUITTER L'AVENTURE ?"
    assert t("story_leave_ask") == "Retourner au jeu normal ?"
    assert "sauvegardes" in t("story_leave_warn")


# ------------------------------------------------------------------ the real game
def test_escape_asks_and_the_game_stays_in_the_adventure(run):
    g = run.game
    _open_adventure(g)
    _key(pygame.K_ESCAPE); run.frames(2)
    assert g.menu_screen == "story_hub" and g.story.screen == "leave"
    _key(pygame.K_ESCAPE); run.frames(2)                             # cancel
    assert g.menu_screen == "story_hub" and g.story.screen == "slots"
    _key(pygame.K_ESCAPE); run.frames(2)
    _key(pygame.K_RETURN, "\r"); run.frames(2)                       # NO is lit: Enter stays
    assert g.menu_screen == "story_hub" and g.story.screen == "slots"


def test_yes_goes_back_to_the_main_menu_on_the_adventure_line(run):
    g = run.game
    _open_adventure(g)
    _key(pygame.K_ESCAPE); run.frames(2)
    _key(pygame.K_RIGHT); run.frames(2)
    _key(pygame.K_RETURN, "\r"); run.frames(2)
    assert g.menu_screen == "main" and g.menu_index == 1


def test_the_question_is_drawn(run):
    import story
    g = run.game
    _open_adventure(g)
    g.story.back()
    seen = []
    real, real_fit = story._text, story._text_fit

    def spy(surface, font, text, *a, **k):
        seen.append(str(text))
        return real(surface, font, text, *a, **k)

    story._text = spy
    try:
        surf = pygame.Surface((1280, 720))
        g.story.draw(surf, g.font, g.medium_font, g.font)
    finally:
        story._text = real
    assert t("story_leave_ask") in seen and t("story_leave_warn") in seen
    assert t("story_no") in seen and t("story_yes") in seen
    assert t("story_delete_warn") not in seen
