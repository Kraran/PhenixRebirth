"""The Novice mode of the Adventure: three choices (Novice, Normal, Veteran). Everything is like Normal, except that the hulls
start with three lives (the workshop sells the fourth, like the second one in Normal) and a failed mission costs 2 % of the
points instead of 5 %."""
import pygame
import pytest

import i18n
import story
import story_items as si
import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)


def _novice(credits=0):
    st = ss.create_slot(1, "NOVA", "novice")
    ss.mark_intro_seen(st)
    st["credits"] = credits
    ss.save_state(ss.story_path(1), st)
    return st


def _rich(mode, credits=9000):
    st = ss.create_slot(1, "NOVA", mode)
    st["credits"] = credits
    st["flags"]["ch1_life_2"] = True
    return st


# ---------------------------------------------------------------- the rules
def test_three_modes_in_this_order():
    assert ss.MODES == ("novice", "normal", "veteran")
    assert ss.DEFAULT_MODE == "normal"


def test_a_novice_hull_starts_with_three_lives_and_a_normal_one_with_one():
    st = ss.create_slot(1, "NOVA", "novice")
    assert st["mode"] == "novice"
    assert [(s["lives"], s["lives_base"]) for s in st["slots"]] == [(3, 3), (3, 3)]
    for mode in ("normal", "veteran"):
        st = ss.create_slot(1, "NOVA", mode)
        assert [(s["lives"], s["lives_base"]) for s in st["slots"]] == [(1, 1), (1, 1)]


def test_an_unknown_mode_is_normal():
    assert ss.create_slot(1, "NOVA", "godlike")["mode"] == "normal"


def test_the_mission_launches_with_three_lives():
    st = _novice()
    assert ss.loadout(st)["lives"] == 3
    assert ss.loadout(ss.create_slot(1, "NOVA", "normal"))["lives"] == 1


def test_the_workshop_cap_is_four_lives_in_novice_and_two_in_normal():
    assert ss.act_caps(ss.create_slot(1, "NOVA", "novice"))["lives"] == 4
    assert ss.act_caps(ss.create_slot(1, "NOVA", "normal"))["lives"] == 2
    assert ss.act_caps(ss.create_slot(1, "NOVA", "veteran"))["lives"] == 2
    a, b = ss.act_caps(ss.create_slot(1, "NOVA", "novice")), ss.act_caps(ss.create_slot(1, "NOVA", "normal"))
    assert a["speed"] == b["speed"]                                    # nothing else changes


def test_the_workshop_sells_the_fourth_life_like_the_second_one_in_normal():
    st = _rich("novice")
    assert ss.upgrade_note(st, "lives_2") is None
    assert ss.buy(st, "lives_2") is True
    assert st["slots"][0]["lives"] == 4 and st["credits"] == 7000      # the same row, the same price
    assert ss.upgrade_note(st, "lives_2") == "story_owned"
    assert ss.buy(st, "lives_2") is False and st["slots"][0]["lives"] == 4 and st["credits"] == 7000
    normal = _rich("normal")
    assert ss.buy(normal, "lives_2") and normal["slots"][0]["lives"] == 2 and normal["credits"] == 7000


def test_the_fourth_life_needs_the_story_flag_like_the_second_one():
    st = _rich("novice")
    st["flags"]["ch1_life_2"] = False
    assert ss.buy(st, "lives_2") is False and st["slots"][0]["lives"] == 3


def test_the_phenix_hull_gets_the_same_ladder():
    st = _rich("novice")
    st["slots"][1]["owned"] = True
    st["selected_slot"] = 1
    assert ss.buy(st, "lives_2") and st["slots"][1]["lives"] == 4 and st["slots"][0]["lives"] == 3


def test_the_ladder_goes_on_from_the_starting_lives_in_act_3_too():
    for mode, base in (("novice", 3), ("normal", 1)):
        st = ss.create_slot(1, "NOVA", mode)
        sl = st["slots"][0]
        assert ss._st_lives_3(sl) == "need_prev"
        assert ss._up_lives_3(sl) is False                              # not before the step below
        assert ss._up_lives_2(sl) and sl["lives"] == base + 1
        assert ss._st_lives_3(sl) is None
        assert ss._up_lives_3(sl) and sl["lives"] == base + 2
        assert ss._st_lives_3(sl) == "owned" and ss._up_lives_3(sl) is False


@pytest.mark.parametrize("credits,lost", [(0, 0), (10, 0), (25, 1), (100, 2), (1000, 20), (1250, 25), (999, 20), (30000, 600)])
def test_a_failed_novice_mission_costs_two_percent(credits, lost):
    assert ss.failure_penalty(credits, "novice") == lost
    st = ss.create_slot(1, "NOVA", "novice")
    st["credits"] = credits
    res = ss.record_result(st, "ch1_sortie", 500, False, {})
    assert res["lost"] == lost and st["credits"] == credits - lost and not res["fallen"]


def test_normal_still_loses_five_percent_and_veteran_still_falls():
    assert ss.failure_penalty(1000) == 50 and ss.failure_penalty(1000, "normal") == 50
    assert ss.failure_penalty(1000, "veteran") == 50 and ss.failure_penalty(1000, None) == 50
    st = ss.create_slot(1, "NOVA", "normal")
    st["credits"] = 1000
    assert ss.record_result(st, "ch1_sortie", 0, False, {})["lost"] == 50
    vet = ss.create_slot(1, "NOVA", "veteran")
    vet["credits"] = 1000
    res = ss.record_result(vet, "ch1_sortie", 0, False, {})
    assert res["fallen"] and vet["credits"] == 1000


def test_a_won_novice_mission_pays_in_full_and_a_failure_gains_nothing():
    st = ss.create_slot(1, "NOVA", "novice")
    assert ss.record_result(st, "ch1_sortie", 700, True, {})["lost"] == 0 and st["credits"] == 700
    res = ss.record_result(st, "ch1_sortie", 9999, False, {})
    assert st["credits"] == 686 and res["lost"] == 14


def test_the_novice_has_the_same_intro_as_a_normal_pilot():
    assert ss.intro_slides("novice") == ss.intro_slides("normal")
    assert ss.intro_slides("novice") != ss.intro_slides("veteran")


def test_the_genesis_core_adds_to_the_three_lives():
    st = _novice(credits=7000)
    si.find(st, "genesis")
    si.buy(st, "genesis")
    assert ss.loadout(st)["lives"] == 3                                # (the game adds the item's life itself)
    assert si.effects(si.installed(st))["extra_lives"] == 1


# ---------------------------------------------------------------- the save
def test_a_novice_save_comes_back_as_it_was(tmp_path):
    st = _novice()
    path = str(tmp_path / "s.json")
    ss.save_state(path, st)
    back = ss.load_state(path)
    assert back["mode"] == "novice"
    assert [(s["lives"], s["lives_base"]) for s in back["slots"]] == [(3, 3), (3, 3)]
    assert ss.act_caps(back)["lives"] == 4
    assert ss.slot_summary(1)["mode"] == "novice"


def test_a_save_made_before_the_novice_mode_is_not_changed():
    st = ss.create_slot(1, "NOVA", "normal")
    for sl in st["slots"]:
        del sl["lives_base"]                                          # saves of the earlier versions have no such field
    st["slots"][0]["lives"] = 2
    st["flags"]["ch1_life_2"] = True
    back = ss.migrate_state(st)
    assert back["slots"][0]["lives"] == 2 and ss.lives_base(back["slots"][0]) == 1
    assert ss.upgrade_note(back, "lives_2") == "story_owned"
    assert ss.act_caps(back)["lives"] == 2 and back["mode"] == "normal"


@pytest.mark.parametrize("junk", [None, "x", -4, 0, 2.5, True])
def test_a_damaged_starting_lives_value_falls_back_to_one(junk):
    assert ss.lives_base({"lives_base": junk}) in (1, 2)
    assert ss.lives_base({"lives_base": junk}) >= 1
    assert ss.lives_base({}) == 1 and ss.lives_base(None) == 1


# ---------------------------------------------------------------- the choice screen
def _mode_screen(name="NOVA"):
    ss.delete_slot(1)
    hub = StoryHub()
    hub.open_slots()
    hub.confirm()
    for ch in name:
        hub.entry.type_char(ch)
    hub._submit_name()
    assert hub.screen == "mode"
    return hub


def test_the_choice_screen_offers_three_modes_and_lights_normal_first():
    hub = _mode_screen()
    assert ss.MODES[hub.mode_index] == "normal"


def test_left_and_right_walk_through_the_three_modes_and_stop_at_the_ends():
    hub = _mode_screen()
    seen = [ss.MODES[hub.mode_index]]
    hub.nav_h(-1); seen.append(ss.MODES[hub.mode_index])
    hub.nav_h(-1); seen.append(ss.MODES[hub.mode_index])             # already the first: stays
    hub.nav_h(1); hub.nav_h(1); seen.append(ss.MODES[hub.mode_index])
    hub.nav_h(1); seen.append(ss.MODES[hub.mode_index])               # already the last: stays
    assert seen == ["normal", "novice", "novice", "veteran", "veteran"]
    hub.nav_v(-1)                                                      # Up / Down move the same way
    assert ss.MODES[hub.mode_index] == "normal"
    hub.nav_v(-1)
    assert ss.MODES[hub.mode_index] == "novice"
    hub.nav_v(1)
    assert ss.MODES[hub.mode_index] == "normal"


@pytest.mark.parametrize("key,mode", [("left", "novice"), ("none", "normal"), ("right", "veteran")])
def test_the_choice_made_is_the_mode_of_the_adventure(key, mode):
    hub = _mode_screen()
    if key == "left":
        hub.nav_h(-1)
    elif key == "right":
        hub.nav_h(1)
    hub.confirm()
    assert hub.screen == "intro" and hub.state["mode"] == mode
    assert ss.load_state(ss.story_path(1))["mode"] == mode
    if mode == "novice":
        assert [s["lives"] for s in hub.state["slots"]] == [3, 3]


def test_back_from_the_choice_goes_to_the_name_and_comes_back_on_normal():
    hub = _mode_screen()
    hub.nav_h(-1)
    assert hub.back() is True and hub.screen == "name"
    hub._submit_name()
    assert ss.MODES[hub.mode_index] == "normal"


def test_the_three_cards_fit_on_the_screen_and_their_texts_fit_in_the_cards(run):
    g = run.game
    pygame.font.init()
    for lang in ("fr", "en"):
        i18n.set_lang(lang)
        try:
            hub = _mode_screen()
            for index in range(len(ss.MODES)):
                hub.mode_index = index
                surf = pygame.Surface((1280, 720))
                hub.draw(surf, g.font, g.medium_font, g.font)
            rects = StoryHub.mode_card_rects()
            assert len(rects) == 3
            assert rects[0].left >= 20 and rects[-1].right <= 1280 - 20
            assert all(a.right + 8 <= b.left for a, b in zip(rects, rects[1:]))      # a gap between the cards
            assert all(r.bottom <= 720 - 20 for r in rects)
            w = rects[0].w
            for key in ss.MODES:
                lines = story._wrap(g.font, i18n.t("story_mode_%s_d" % key), w - 40)
                assert 1 <= len(lines) <= 4, (lang, key, lines)           # 112 + 36 * 4 stays inside the 270 px card
                assert all(g.font.size(line)[0] <= w - 40 + 1 for line in lines)
        finally:
            i18n.set_lang("fr")


def test_each_card_draws_something_different(run):
    g = run.game
    hub = _mode_screen()
    shots = []
    for index in range(3):
        hub.mode_index = index
        surf = pygame.Surface((1280, 720))
        hub.draw(surf, g.font, g.medium_font, g.font)
        shots.append(pygame.image.tobytes(surf.subsurface((20, 130, 1240, 290)), "RGB"))
    assert len(set(shots)) == 3


def test_the_focused_card_title_wears_the_colour_of_its_mode(run):
    g = run.game
    hub = _mode_screen()
    for index, key in enumerate(ss.MODES):
        hub.mode_index = index
        surf = pygame.Surface((1280, 720))
        hub.draw(surf, g.font, g.medium_font, g.font)
        r = StoryHub.mode_card_rects()[index]
        band = surf.subsurface(pygame.Rect(r.x + 4, r.y + 20, r.w - 8, 56))
        colours = {tuple(band.get_at((x, y)))[:3] for x in range(band.get_width()) for y in range(band.get_height())}
        assert story.MODE_COLORS[key] in colours, key
    assert len(set(story.MODE_COLORS.values())) == 3


def test_the_texts_of_the_three_modes():
    for lang_index, lang in enumerate(("fr", "en")):
        names = [i18n.T["story_mode_" + m][lang] for m in ss.MODES]
        assert names == ["NOVICE", "NORMAL", "VETERAN"]
    novice = i18n.T["story_mode_novice_d"]["fr"]
    assert "3 vies" in novice and "2%" in novice
    assert "5%" in i18n.T["story_mode_normal_d"]["fr"]
    assert "3 lives" in i18n.T["story_mode_novice_d"]["en"] and "2%" in i18n.T["story_mode_novice_d"]["en"]


def test_the_slot_list_and_the_hangar_name_the_mode(run):
    g = run.game
    _novice()
    hub = StoryHub()
    hub.open_slots()
    surf = pygame.Surface((1280, 720))
    hub.draw(surf, g.font, g.medium_font, g.font)
    assert ss.slot_summary(1)["mode"] == "novice"
    hub.open_slot(1)
    hub.pane = "hangar"
    hub.draw(surf, g.font, g.medium_font, g.font)
    assert i18n.t("story_mode_" + hub.state["mode"]) == "NOVICE"


def test_the_hangar_shows_three_lives_out_of_four(run):
    g = run.game
    _novice()
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "hangar"
    seen = []
    real = story._text

    def spy(surface, font, text, *a, **k):
        seen.append(text)
        return real(surface, font, text, *a, **k)

    story._text = spy
    try:
        hub.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
    finally:
        story._text = real
    assert "3/4" in seen


# ---------------------------------------------------------------- in a mission
def _begin(g, mode="novice", credits=1000):
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    st["credits"] = credits
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = 0
    g._begin_adventure(g.story._launch_selected())
    g.input_grace = 0.0


def test_the_novice_ship_has_three_lives_in_the_mission(run):
    g = run.game
    _begin(g)
    assert g.player.lives == 3 and not g.player.infinite_lives
    _begin(g, "normal")
    assert g.player.lives == 1


def test_the_novice_survives_two_hits_and_falls_on_the_third(run):
    g = run.game
    _begin(g)
    p = g.player
    for expected in (2, 1):
        p.invulnerable = 0.0
        p.hit()
        assert p.lives == expected and p.alive and not p.dying
    p.invulnerable = 0.0
    p.hit()
    assert p.lives == 0 and p.dying


def test_the_wall_costs_the_novice_one_life_not_the_mission(run):
    g = run.game
    _begin(g)
    p = g.player
    p.x, p.invulnerable = 37, 0.0

    class Keys:
        def __getitem__(self, k):
            return k == pygame.K_LEFT

    for _ in range(5):
        p.update(1 / 60, Keys())
        if p.just_lost_life:
            break
    assert p.lives == 2 and not p.dying


def test_a_lost_novice_mission_takes_two_percent_and_goes_back_to_the_map(run):
    g = run.game
    _begin(g, credits=1000)
    g.score = 400
    g._end_adventure(False)
    assert g.story.state["credits"] == 980 and "20" in g.story.toast
    assert g.story.screen == "hub" and not g.story.state.get("fallen")
    again = StoryHub()
    again.open_slot(1)
    assert again.state["credits"] == 980 and again.state["mode"] == "novice"


def test_a_won_novice_mission_banks_the_score(run):
    g = run.game
    _begin(g, credits=1000)
    g.score = 400
    g._end_adventure(True)
    assert g.story.state["credits"] == 1400


def test_quitting_a_novice_mission_by_choice_changes_nothing(run):
    g = run.game
    _begin(g, credits=1000)
    g._quit_to_menu()
    assert ss.load_state(ss.story_path(1))["credits"] == 1000


def test_the_genesis_core_makes_it_four_lives_for_a_novice(run):
    g = run.game
    st = ss.create_slot(1, "NOVA", "novice")
    ss.mark_intro_seen(st)
    st["credits"] = 6000
    si.find(st, "genesis")
    si.buy(st, "genesis")
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = 0
    g._begin_adventure(g.story._launch_selected())
    assert g.player.lives == 4


def test_the_hangar_of_a_novice_sells_the_fourth_life_through_the_screen(run):
    g = run.game
    st = _novice(credits=2500)
    st["flags"]["ch1_life_2"] = True
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane, hub.zone = "hangar", "shop"
    hub.shop_index = [r[0] for r in hub.shop_rows()].index("lives_2")
    hub.confirm()
    assert hub.state["slots"][0]["lives"] == 4 and hub.state["credits"] == 500
    assert ss.load_state(ss.story_path(1))["slots"][0]["lives"] == 4
    hub.confirm()
    assert hub.state["credits"] == 500                                  # bought once


# ---------------------------------------------------------------- the workshop label: the lives you end up with
def _drawn_texts(g, hub):
    seen = []
    real = story._text

    def spy(surface, font, text, *a, **k):
        seen.append(text)
        return real(surface, font, text, *a, **k)

    story._text = spy
    try:
        hub.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
    finally:
        story._text = real
    return seen


def _hangar(mode, hull=None):
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    st["flags"]["ch1_life_2"] = True
    st["credits"] = 5000
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane, hub.zone = "hangar", "shop"
    return hub


def test_the_novice_workshop_sells_vies_4_where_normal_sells_vies_2(run):
    i18n.set_lang("fr")
    labels = lambda hub: {sid: i18n.t(lab) for sid, lab, _, _ in hub.shop_rows()}
    assert labels(_hangar("novice"))["lives_2"] == "Vies 4"
    assert labels(_hangar("normal"))["lives_2"] == "Vies 2"
    assert labels(_hangar("veteran"))["lives_2"] == "Vies 2"
    i18n.set_lang("en")
    assert labels(_hangar("novice"))["lives_2"] == "Lives 4"
    assert labels(_hangar("normal"))["lives_2"] == "Lives 2"
    i18n.set_lang("fr")


def test_the_novice_screen_draws_vies_4_and_the_price_is_unchanged(run):
    g = run.game
    i18n.set_lang("fr")
    hub = _hangar("novice")
    assert any(s.endswith("Vies 4") for s in _drawn_texts(g, hub) if isinstance(s, str))
    assert not any(s.endswith("Vies 2") for s in _drawn_texts(g, hub) if isinstance(s, str))
    rows = {sid: cost for sid, _, cost, _ in hub.shop_rows()}
    assert rows["lives_2"] == 2000
    hub = _hangar("normal")
    assert any(s.endswith("Vies 2") for s in _drawn_texts(g, hub) if isinstance(s, str))


def test_the_phenix_workshop_and_act_three_follow_the_same_rule(run):
    assert ss.NOVICE_LABELS == {"story_shop_lives2": "story_shop_lives4", "story_shop_lives3": "story_shop_lives5"}
    for lang in ("fr", "en", "es", "de", "ru"):
        i18n.set_lang(lang)
        assert "4" in i18n.t("story_shop_lives4") and "5" in i18n.t("story_shop_lives5")
    i18n.set_lang("fr")
    st = ss.create_slot(1, "NOVA", "novice")
    st["selected_slot"] = 1
    assert ss.selected_slot(st)["id"] == "phoenix"
    rows = {sid: lab for sid, lab, _, _ in ss.shop_for(st)}
    assert rows.get("lives_2") == "story_shop_lives4"               # the Phenix hull also starts with three lives
    st["mode"] = "normal"
    assert {sid: lab for sid, lab, _, _ in ss.shop_for(st)}.get("lives_2") == "story_shop_lives2"
