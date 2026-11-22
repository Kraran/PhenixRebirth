"""The reflective coating is bought at the workshop: Gardiens III won (the Alpha down) opens a row "Reflective coating",
2000 PTS, bought once for both hulls; until it is laid the lasers go through the dome and the Phenix form. The hangar
shows the coated hull (a golden edge and a gleam)."""
import pygame
import pytest

import story_state as ss
from story import StoryHub

DT = 1 / 60


def _state(credits=5000, act=3, won=True):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["act"] = act
    st["credits"] = credits
    if won:
        st["flags"][ss.REFLECT_FLAG] = True
    return st


def _ids(st):
    return [r[0] for r in ss.shop_for(st)]


def test_the_row_shows_only_once_gardiens_iii_is_won():
    assert ss.COATING_ROW not in _ids(_state(won=False))
    st = _state()
    rows = ss.shop_for(st)
    row = next(r for r in rows if r[0] == ss.COATING_ROW)
    assert row[1] == "story_shop_coating" and row[2] == 2000 and row[3] is None
    assert ss.upgrade_note(st, ss.COATING_ROW) is None and ss.coating_buyable(st)


def test_buying_it_lays_it_for_good_on_both_hulls():
    st = _state(credits=2500)
    assert not ss.has_coating(st)
    assert ss.buy(st, ss.COATING_ROW)
    assert st["credits"] == 500 and ss.has_coating(st)
    assert ss.upgrade_note(st, ss.COATING_ROW) == "story_owned"
    assert not ss.coating_buyable(st) and not ss.buy(st, ss.COATING_ROW) and st["credits"] == 500     # once only
    assert _ids(st).count(ss.COATING_ROW) == 1                       # still listed, as bought (with the rows at MAX)
    ss.grant_phenix(st)
    for i, sl in enumerate(st["slots"]):                 # whichever hull is chosen: the coating is on it
        if sl.get("owned"):
            st["selected_slot"] = i
            assert ss.has_coating(st) and ss.upgrade_note(st, ss.COATING_ROW) == "story_owned"


def test_not_enough_credits_or_not_won_it_cannot_be_bought():
    st = _state(credits=1999)
    assert not ss.coating_buyable(st) and not ss.buy(st, ss.COATING_ROW) and st["credits"] == 1999
    st = _state(won=False)
    assert not ss.buy(st, ss.COATING_ROW) and not ss.has_coating(st)
    st["flags"][ss.COATING_FLAG] = True                  # (a flag alone, without the film of the Alpha: nothing)
    assert not ss.has_coating(st)


def test_the_missions_reflect_only_once_it_is_laid(tmp_path, monkeypatch):
    import user_settings
    from game import Game
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    g = Game()
    m = ss.mission_by_id("guardians_1")
    for laid in (False, True):
        st = _state(act=2)
        st["flags"][m["need"]] = True
        if laid:
            assert ss.buy(st, ss.COATING_ROW)
        ss.mark_scene_seen(st, "guardians_1")
        g.story.state = st
        g.story.map_index = next(i for i, x in enumerate(g.story.missions()) if x["id"] == "guardians_1")
        spec = g.story._launch_selected()
        assert bool(spec.get("reflect")) is laid
    g.running = False


def test_the_workshop_draws_the_row_and_the_coated_hull(tmp_path, monkeypatch):
    import user_settings
    from game import Game
    from settings import BASE_WIDTH, BASE_HEIGHT
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    g = Game()
    st = _state()
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.screen, hub.pane, hub.zone = "hub", "hangar", "shop"
    rows = hub.shop_rows()
    hub.shop_index = [r[0] for r in rows].index(ss.COATING_ROW)
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    hub.draw(surf, g.font, g.medium_font, g.font)               # the row, its icon, its line under the list
    assert not hasattr(hub, "_coat_cache") or not hub._coat_cache        # not laid: no gleam on the hull
    assert hub._buy(rows[hub.shop_index]) and ss.has_coating(hub.state)
    for t_ in (0.3, 0.6, 2.5):                                  # the gleam crosses, then rests: the golden edge stays
        hub.anim_t = t_
        hub.draw(surf, g.font, g.medium_font, g.font)
    assert hub._coat_cache
    g.running = False


def test_an_old_save_with_the_film_ready_buys_it_like_the_others():
    st = _state()                                         # Gardiens III won before this version: the row is there
    assert ss.COATING_ROW in _ids(st) and not ss.has_coating(st)
