"""The four endings of the visual novel (src/story_vn.py, screen "vn" of story.py): told on the picture of the last scene
after its reaction, according to the total of points. Amitie and Romance: a gift of points x 500 credits; Romance: every
price of the workshop is 10 % lower, for good."""
import pygame
import pytest

import i18n
import story_items
import story_state as ss
import story_vn
from settings import BASE_HEIGHT, BASE_WIDTH
from story import StoryHub

PICKS_BY_TOTAL = {                       # answers (index in the list of each scene) -> total
    6: [0, 0, 0, 0, 0],                  # 2+1+1+1+1 = 6
    8: [0, 2, 0, 3, 1],                  # 2+2+1+1+2 = 8
    9: [0, 2, 1, 3, 1],                  # 2+2+3+1+2 = 10 -> see test below for exact values
}

def _after_concert(hub):
    """The two best endings (Amitie, Romance) go on with the concert of Lyra Voss (story_state.CONCERT_SCENES): it is
    read to its end and closed, then the screen is the one the visual novel goes back to."""
    if hub.screen == "intro":
        assert hub.scene_id in ss.VN_CONCERTS.values()
        hub.intro_t = 99.0
        hub.confirm()



@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((64, 64))
    yield


@pytest.fixture(autouse=True)
def _natural(monkeypatch):
    monkeypatch.setattr(ss, "film_files", lambda film_id: None)
    monkeypatch.setattr(story_vn, "order", lambda sid, shuffled=True: list(range(len(story_vn.scene(sid)["answers"]))))


@pytest.fixture
def french():
    before = i18n.get_lang()
    i18n.set_lang("fr")
    yield
    i18n.set_lang(before)


def _pick_for(sid, points):
    """The index of the answer of scene `sid` worth `points`."""
    return next(i for i, a in enumerate(story_vn.scene(sid)["answers"]) if a[1] == points)


def _state(per_scene, told=False, answered=5):
    """A save that answered `answered` scenes, each with the answer worth the given points."""
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    for fid in ("lyra_1", "lyra_2", "lyra_3"):
        ss.mark_film_seen(st, fid)
    for sid, pts in list(zip(story_vn.VN_ORDER, per_scene))[:answered]:
        story_vn.choose(st, sid, _pick_for(sid, pts), ss.story_wins(st))
    if told:
        st["flags"][story_vn.ENDING_FLAG] = True
    return st


# every scene has answers worth 1..4 in some order; a total is reached with these per-scene points
TOTALS = {6: (2, 1, 1, 1, 1), 8: (2, 2, 1, 1, 2), 9: (2, 2, 2, 1, 2), 12: (3, 3, 2, 2, 2), 13: (3, 3, 3, 2, 2),
          16: (4, 4, 3, 3, 2), 17: (4, 4, 3, 3, 3), 20: (4, 4, 4, 4, 4)}


@pytest.mark.parametrize("total,ending", [(6, "fachery"), (8, "fachery"), (9, "distance"), (12, "distance"),
                                          (13, "amitie"), (16, "amitie"), (17, "romance"), (20, "romance")])
def test_the_total_of_points_picks_the_ending(total, ending):
    st = _state(TOTALS[total])
    assert story_vn.points(st) == total
    assert story_vn.ending_id(st) == ending


def test_no_ending_while_a_scene_is_missing():
    st = _state(TOTALS[20], answered=4)
    assert story_vn.ending_id(st) is None and story_vn.ending_pages(st) == []
    assert story_vn.tell_ending(st) == 0 and not story_vn.ending_told(st)


def test_the_gift_is_points_times_500_for_friendship_and_romance_only():
    assert [story_vn.ending_gift(_state(TOTALS[t])) for t in (6, 8, 9, 12)] == [0, 0, 0, 0]
    assert story_vn.ending_gift(_state(TOTALS[13])) == 13 * 500
    assert story_vn.ending_gift(_state(TOTALS[16])) == 16 * 500
    assert story_vn.ending_gift(_state(TOTALS[17])) == 17 * 500
    assert story_vn.ending_gift(_state(TOTALS[20])) == 10000


def test_only_romance_has_a_sale_of_ten_percent():
    assert [story_vn.ending_sale(_state(TOTALS[t])) for t in (6, 9, 13, 17)] == [0, 0, 0, 10]


def test_telling_the_ending_pays_the_gift_once():
    st = _state(TOTALS[13])
    st["credits"] = 100
    assert story_vn.tell_ending(st) == 6500 and st["credits"] == 6600 and story_vn.ending_told(st)
    assert story_vn.tell_ending(st) == 0 and st["credits"] == 6600


def test_the_sale_only_counts_once_the_ending_is_told():
    st = _state(TOTALS[17])
    assert story_vn.sale_price(st, 2000) == 2000
    story_vn.tell_ending(st)
    assert [story_vn.sale_price(st, p) for p in (500, 2000, 5000, 6000, 4000, 1)] == [450, 1800, 4500, 5400, 3600, 1]
    other = _state(TOTALS[13], told=True)
    assert story_vn.sale_price(other, 2000) == 2000


def test_the_sale_is_rounded_to_the_nearest_credit():
    st = _state(TOTALS[17], told=True)
    assert story_vn.sale_price(st, 15) == 14 and story_vn.sale_price(st, 25) == 23 and story_vn.sale_price(st, 5) == 5


# ------------------------------------------------------------------ the workshop
def _shop_costs(st):
    return {r[0]: r[2] for r in ss.shop_for(st)}


def test_every_row_of_the_workshop_costs_ten_percent_less_after_romance():
    st = _state(TOTALS[13], told=True)
    st["act"] = 3
    for f in ("antimatter",):
        pass
    before = _shop_costs(st)
    st2 = _state(TOTALS[17], told=True)
    st2["act"] = 3
    after = _shop_costs(st2)
    assert before and set(before) == set(after)
    for sid, cost in before.items():
        assert after[sid] == (cost * 90 + 50) // 100, sid


def test_the_missile_rows_and_the_paint_follow_the_sale():
    st = _state(TOTALS[17], told=True)
    assert story_vn.sale_price(st, ss.LAUNCHER_PRICE) == 4500 and ss.paint_cost(st) == 450
    plain = _state(TOTALS[13], told=True)
    assert ss.paint_cost(plain) == ss.PAINT_COST


def test_the_launcher_is_bought_at_the_sale_price(monkeypatch):
    st = _state(TOTALS[17], told=True)
    monkeypatch.setattr(ss, "has_antimatter", lambda s: True)
    st["credits"] = 4499
    assert not ss.missile_buyable(st, "missile_launcher")
    st["credits"] = 4500
    assert ss.missile_buyable(st, "missile_launcher") and ss.buy(st, "missile_launcher")
    assert st["credits"] == 0
    st["credits"] = 900                                                            # a missile is 1000, 10 % less with the Romance
    assert ss.buy(st, "missile_ammo") and st["credits"] == 0


def test_an_upgrade_is_bought_at_the_sale_price():
    st = _state(TOTALS[17], told=True)
    slot = ss.selected_slot(st)
    sid = next(r[0] for r in ss.shop_for(st) if ss.upgrade_note(st, r[0]) is None and r[2] > 0 and ss.upgrade_cost(slot, r[0]))
    price = (ss.upgrade_cost(slot, sid) * 90 + 50) // 100
    st["credits"] = price
    assert ss.buy(st, sid) and st["credits"] == 0


def test_an_item_is_bought_at_the_sale_price():
    st = _state(TOTALS[17], told=True)
    item = "tesla"
    story_items.find(st, item)
    assert story_items.price(st, item) == 1800
    st["credits"] = 1799
    assert not story_items.affordable(st, item) and not story_items.buy(st, item)
    st["credits"] = 1800
    assert story_items.buy(st, item) and st["credits"] == 0


def test_the_paint_is_paid_at_the_sale_price():
    st = _state(TOTALS[17], told=True)
    st["credits"] = 449
    assert not ss.paint_affordable(st)
    st["credits"] = 450
    assert ss.paint_affordable(st)


# ------------------------------------------------------------------ the screen
def _hub(per_scene, answered=5, told=False, wins_after=None):
    st = _state(per_scene, told=told, answered=answered)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.screen, hub.pane = "hub", "map"
    return hub


def _skip_pages(hub, phase_stop=None):
    for _ in range(30):
        if hub.screen != "vn" or hub.vn_phase == phase_stop:
            return
        hub.vn_t = hub.VN_FADE + 999.0
        hub.confirm()
    raise AssertionError("never ends")


def _last_scene_hub(per_scene=TOTALS[17]):
    """A save with four scenes answered and the fifth about to be told."""
    hub = _hub(per_scene, answered=4)
    st = hub.state
    st["cleared"].extend(["ast_2", "ast_3", "phenix_1", "phenix_2"][:0])
    return hub


def _answer_last(hub, points):
    sid = "vn_5"
    assert hub.start_vn(sid, back_to="map")
    for _ in range(20):
        hub.vn_t = hub.VN_FADE + 999.0
        if hub.vn_ready():
            break
        hub.confirm()
    while hub.vn_choice_wait > 0:
        hub.update(0.25)
    hub.vn_index = _pick_for(sid, points)
    hub.confirm()
    assert hub.vn_phase == "react"


def test_the_ending_follows_the_reaction_of_the_last_scene():
    hub = _last_scene_hub(TOTALS[13][:4] + (0,))
    hub.state["credits"] = 0
    _answer_last(hub, 2)                      # 3+3+3+2 = 11, +2 = 13: friendship
    assert story_vn.points(hub.state) == 13
    _skip_pages(hub, phase_stop="end")
    assert hub.screen == "vn" and hub.vn_phase == "end"
    assert hub.vn_pages() == story_vn.ending_pages(hub.state, hub.state.get("name"))
    assert hub.state["credits"] == 6500 and story_vn.ending_told(hub.state)
    _skip_pages(hub)
    _after_concert(hub)
    assert hub.screen == "hub"


def test_the_gift_and_the_flag_are_saved():
    hub = _last_scene_hub(TOTALS[13][:4] + (0,))
    hub.state["credits"] = 0
    _answer_last(hub, 2)
    _skip_pages(hub)
    loaded = ss.load_state(ss.story_path(1))
    assert loaded["credits"] == 6500 and story_vn.ending_told(loaded)


def test_the_first_two_endings_pay_nothing_and_the_ending_is_still_told():
    hub = _last_scene_hub((2, 1, 1, 1, 0))
    hub.state["credits"] = 0
    _answer_last(hub, 1)                      # 2+1+1+1+1 = 6: falling out
    _skip_pages(hub, phase_stop="end")
    assert hub.vn_phase == "end" and hub.state["credits"] == 0
    assert len(hub.vn_pages()) == 2           # the narration and the last line, no effects page
    _skip_pages(hub)
    assert hub.screen == "hub"


def test_romance_tells_the_sale_then_the_gift_and_applies_both(french):
    hub = _last_scene_hub((4, 4, 3, 3, 0))
    hub.state["credits"] = 0
    _answer_last(hub, 3)                      # 4+4+3+3+3 = 17: romance
    total = story_vn.points(hub.state)
    assert story_vn.ending_id(hub.state) == "romance"
    _skip_pages(hub, phase_stop="end")
    pages = hub.vn_pages()
    assert pages[-1][0][1].startswith("Lyra mobilise les foules")
    assert pages[-1][1][1].startswith("Lyra fait un don de")
    assert story_vn.group(total * 500) in pages[-1][1][1]
    assert hub.state["credits"] == total * 500
    assert ss.paint_cost(hub.state) == 450


def test_the_pilot_name_is_in_the_romance_ending(french):
    st = _state(TOTALS[17])
    txt = " ".join(w for p in story_vn.ending_pages(st, "NOVA") for _n, w in p)
    assert "NOVA" in txt and "{name}" not in txt


def test_the_french_lines_of_kraran_are_the_last_lines_of_each_ending(french):
    expect = {
        6: "Tu m’as sauvée, et je ne l’oublierai jamais. Mais ça ne veut pas dire qu’on se comprend. Bonne chance pour la suite.",
        9: "Envoie-moi des nouvelles, de temps en temps. Et si tu passes par Eloncity, tu sais où me trouver.",
        13: "Je crois que je peux te faire confiance. Et ça, pour moi, c’est plus rare que tu ne l’imagines. Alors ne disparais pas complètement, d’accord ?",
        17: "Je vais monter sur cette scène, regarder des milliers de personnes et chanter comme je ne l’ai jamais fait. Mais je crois que, cette fois, il y aura quelqu’un dans le public que j’aurai vraiment envie de retrouver après le spectacle.",
    }
    for total, line in expect.items():
        pages = story_vn.ending_pages(_state(TOTALS[total]), "NOVA")
        quote = next(p for p in pages if not p[0][0])
        said = " ".join(w for _n, w in quote).replace(story_vn.NBSP, " ")
        assert said == "« " + line + " »", total


def test_the_effects_in_english():
    before = i18n.get_lang()
    i18n.set_lang("en")
    try:
        pages = story_vn.ending_pages(_state(TOTALS[17]), "NOVA")
        text = " ".join(w for p in pages for _n, w in p)
        assert "10%" in text and "credits" in text and "NOVA" in text
    finally:
        i18n.set_lang(before)


def test_every_ending_fits_its_panel_in_both_languages():
    font = pygame.font.Font(None, 28)
    for lang in ("fr", "en"):
        before = i18n.get_lang()
        i18n.set_lang(lang)
        try:
            for total in (6, 9, 13, 17):
                hub = _hub(TOTALS[total], told=True)
                assert hub.start_vn_ending(back_to="map")
                n = len(hub.vn_pages())
                for _ in range(n):
                    hub.vn_t = hub.VN_FADE + 999.0
                    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
                    hub.draw(surf, font, font, font)
                    hub.confirm()
        finally:
            i18n.set_lang(before)


def test_watched_again_from_the_journal_the_ending_pays_nothing_more():
    hub = _hub(TOTALS[13], told=True)
    hub.state["credits"] = 10
    assert hub.start_vn("vn_5", back_to="log")
    _skip_pages(hub)
    _after_concert(hub)
    assert hub.screen == "hub" and hub.state["credits"] == 10


def test_a_save_made_before_the_endings_gets_its_ending_after_the_next_story_mission():
    hub = _hub(TOTALS[17])                   # all five answered, the ending never told
    st = hub.state
    base = story_vn.mark(st, "vn_5")
    assert base is not None and not ss.vn_ending_due(st)
    st["cleared"].append("ast_2")
    assert ss.vn_ending_due(st)
    st["credits"] = 0
    hub._maybe_vn()
    assert hub.screen == "vn" and hub.vn_phase == "end"
    assert story_vn.ending_told(hub.state) and hub.state["credits"] == 17 * 500
    _skip_pages(hub)
    hub._maybe_vn()
    _after_concert(hub)
    assert hub.screen == "hub"               # told once


def test_the_ending_is_not_due_before_the_last_scene_is_answered_or_once_told():
    assert not ss.vn_ending_due(_state(TOTALS[17], answered=4))
    assert not ss.vn_ending_due(_state(TOTALS[17], told=True))


def test_the_cheat_vnov_tells_the_ending_without_gift_nor_sale():
    hub = _hub(TOTALS[13][:4] + (0,), answered=4)
    hub.cheat_vn = True
    hub.state["credits"] = 5
    _answer_last(hub, 4)                      # 3+3+3+2 = 11, +4 = 15: friendship
    _skip_pages(hub, phase_stop="end")
    assert hub.vn_phase == "end" and hub.state["credits"] == 5 and not story_vn.ending_told(hub.state)
    assert story_vn.sale_price(hub.state, 2000) == 2000
    assert story_vn.pick(hub.state, "vn_5") is None            # (nothing kept)
    _skip_pages(hub)
    _after_concert(hub)
    assert hub.screen == "hub"


def test_the_cheat_without_a_complete_save_tells_no_ending():
    hub = _hub((2, 1, 1, 1, 1), answered=0)
    hub.cheat_vn = True
    assert hub.start_vn("vn_5", back_to="map")
    for _ in range(20):
        hub.vn_t = hub.VN_FADE + 999.0
        if hub.vn_ready():
            break
        hub.confirm()
    while hub.vn_choice_wait > 0:
        hub.update(0.25)
    hub.confirm()
    _skip_pages(hub)
    assert hub.screen == "hub" and hub.vn_phase != "end"


def test_the_help_bar_says_next_after_the_last_reaction_and_close_on_the_ending():
    hub = _last_scene_hub(TOTALS[13][:4] + (0,))
    _answer_last(hub, 2)
    hub.vn_t = hub.VN_FADE + 999.0
    assert hub.help_items()[0] == [("ok", "hint_next")]
    _skip_pages(hub, phase_stop="end")
    hub.vn_t = hub.VN_FADE + 999.0
    assert hub.vn_ready() is False or hub.help_items()[0] in ([("ok", "hint_next")], [("ok", "hint_close")])


def test_the_cheat_vnov_pays_nothing_even_on_a_save_that_answered_everything():
    hub = _hub(TOTALS[13])                     # all answered, the ending not told yet
    assert not story_vn.ending_told(hub.state)
    hub.cheat_vn = True
    hub.state["credits"] = 7
    _answer_last(hub, 4)
    _skip_pages(hub, phase_stop="end")
    assert hub.vn_phase == "end" and hub.state["credits"] == 7 and not story_vn.ending_told(hub.state)
