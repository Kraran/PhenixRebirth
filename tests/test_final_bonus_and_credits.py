"""The credits of the workshop stop at 99 999 (what is won beyond is lost); the three final BONUS missions (Scramble,
Lunar Lander, Asteroids) close Act IV under their own heading, END BONUS; the menu of the setting of the Lunar Lander
and of Scramble is made behind a loading bar."""
import pytest

import i18n
import story_state as ss
import story_vn
from story import StoryHub

FINALS = ("bonus_scramble", "bonus_lander", "bonus_ast_endless")


def _state(credits=0, ending=True):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    st["credits"] = credits
    if ending:
        ss.complete_ending(st)
    return st


# ------------------------------------------------------------------ the credits
def test_the_credits_stop_at_99999_and_the_rest_is_lost():
    st = _state(credits=99000)
    res = ss.record_result(st, "best_s2", 5000, True)
    assert st["credits"] == ss.CREDITS_MAX == 99999 and res["score"] == 5000
    assert ss.add_credits(st, 10) == 0 and st["credits"] == 99999
    st["credits"] = 99990
    assert ss.add_credits(st, 50) == 9 and st["credits"] == 99999
    st["credits"] = 100
    assert ss.add_credits(st, 50) == 50 and st["credits"] == 150


def test_an_old_save_over_the_cap_is_brought_down():
    st = _state()
    st["credits"] = 250000
    assert ss.migrate_state(st)["credits"] == 99999


def test_the_gift_of_an_ending_and_a_reward_stay_under_the_cap(monkeypatch):
    st = _state(credits=99950)
    monkeypatch.setattr(story_vn, "ending_id", lambda s: "amitie")
    monkeypatch.setattr(story_vn, "ending_told", lambda s: False)
    monkeypatch.setattr(story_vn, "ending_gift", lambda s: 5000)
    story_vn.tell_ending(st)
    assert st["credits"] == 99999


# ------------------------------------------------------------------ the final BONUS
@pytest.mark.parametrize("mid", FINALS)
def test_the_final_bonus_missions_are_in_act_4_under_end_bonus(mid):
    m = ss.mission_by_id(mid)
    assert m["acts"] == (ss.ENDING_ACT,) and ss.mission_group(m) == ss.GROUP_FINAL and m["secret"]
    assert not ss.mission_open(_state(ending=False), m) and ss.mission_open(_state(), m)
    assert ss.next_mission(_state(), [m]) is None                         # (never what the map suggests)
    for lang, start in (("fr", "BONUS FINAL - "), ("en", "FINAL BONUS - ")):
        before = i18n.get_lang()
        i18n.set_lang(lang)
        try:
            assert i18n.t(m["title"]).startswith(start)
        finally:
            i18n.set_lang(before)


def test_they_close_the_map_after_the_ending_of_act_4():
    st = _state()
    shown = ss.visible_missions(st)
    ids = [m["id"] for m in shown]
    assert ids[-3:] == list(FINALS)                                       # (the very end of the map)
    act4 = [m["id"] for m in shown if ss.map_act(st, m) == ss.ENDING_ACT]
    assert act4 == [ss.ENDING_MISSION] + list(FINALS)
    assert i18n.T["story_grp_final"]["fr"] == "BONUS DE FIN" and i18n.T["story_grp_final"]["en"] == "END BONUS"


def test_the_map_draws_the_end_bonus_heading(tmp_path, monkeypatch):
    import pygame
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 64))
    st = _state()
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.screen, hub.pane = "hub", "map"
    hub.map_index = [m["id"] for m in hub.missions()].index("bonus_ast_endless")
    asked = []
    real = i18n.t
    monkeypatch.setattr("story.t", lambda key, *a, **k: (asked.append(key), real(key, *a, **k))[1])
    font = pygame.font.Font(None, 24)
    hub.draw(pygame.Surface((1280, 720)), font, font, font)
    assert "story_grp_final" in asked


# ------------------------------------------------------------------ the loading bar of the menu of the setting
@pytest.mark.parametrize("mid, kind", [("bonus_lander", "lander"), ("bonus_scramble", "scramble")])
def test_the_menu_of_the_setting_is_made_behind_a_loading_bar(mid, kind, monkeypatch):
    from game import Game
    import lander
    import lander_view
    import loading
    import menu_actions
    import scramble_view
    g = Game()
    try:
        g._intro_done, g.fade_phase = True, None
        ss.save_state(ss.story_path(1), _state())
        g.story.open_slot(1)
        g.story.screen, g.story.pane = "hub", "map"
        g.menu_screen = "story_hub"
        g.story.map_index = [m["id"] for m in g.story.missions()].index(mid)
        view = scramble_view if kind == "scramble" else lander_view
        made, bars, warmed = [], [], []
        monkeypatch.setattr(view, "preview", lambda key: made.append((key, loading.active() is not None)))
        monkeypatch.setattr(view, "warm", lambda order: warmed.append(list(order)))
        real = loading.Loading.__init__

        def spy(self, game, style="arcade", title=None, delay=0.0, lang=None):
            bars.append((style, title))
            real(self, game, style, title, delay, lang)
        monkeypatch.setattr(loading.Loading, "__init__", spy)
        menu_actions.menu_confirm(g)
        assert g.story.screen == "lander_pick"
        assert bars == [("adventure", i18n.t(ss.mission_by_id(mid)["title"]))]
        assert made == [(lander.MENU_ORDER[0], True)]                     # (the first picture, behind the bar)
        assert warmed == [list(lander.MENU_ORDER)]                        # (then the others, in the background)
    finally:
        g.running = False


@pytest.mark.parametrize("mid, key", [("bonus_lander", "lander_pick_title_final"),
                                      ("bonus_scramble", "scramble_pick_title_final")])
def test_the_menu_of_the_setting_of_a_final_bonus_says_so(mid, key, monkeypatch):
    import pygame
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 64))
    ss.save_state(ss.story_path(1), _state())
    hub = StoryHub()
    hub.open_slot(1)
    hub.screen, hub.pane = "hub", "map"
    hub.map_index = [m["id"] for m in hub.missions()].index(mid)
    hub.confirm()
    assert hub.screen == "lander_pick"
    asked = []
    real = i18n.t
    monkeypatch.setattr("story.t", lambda k, *a, **kw: (asked.append(k), real(k, *a, **kw))[1])
    font = pygame.font.Font(None, 24)
    hub.draw(pygame.Surface((1280, 720)), font, font, font)
    assert key in asked and i18n.T[key]["fr"].startswith("BONUS FINAL - ")
