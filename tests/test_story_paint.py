"""Act 2 paint series: three optional missions, one colour change for the Shield, a harder series each time."""
import pygame
import pytest

import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

PAINT = ["paint_1", "paint_2", "paint_3"]


def _act2():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["flags"].update(act2=True, dome_online=True, ch1_speed=True)
    st["act"] = 2
    st["credits"] = 2000                                              # painting costs 500
    return st


def _win(st, mission_id):
    return ss.record_result(st, mission_id, 100, True, {})


def _pass(st):
    for mid in PAINT:
        _win(st, mid)


def _mission(mid):
    return ss.mission_by_id(mid)


# ------------------------------------------------------------------ the series
def test_the_series_is_flown_in_order():
    st = _act2()
    assert [ss.mission_playable(st, _mission(m)) for m in PAINT] == [True, False, False]
    _win(st, "paint_1")
    assert [ss.mission_playable(st, _mission(m)) for m in PAINT] == [False, True, False]
    _win(st, "paint_2")
    assert [ss.mission_playable(st, _mission(m)) for m in PAINT] == [False, False, True]


def test_the_series_is_optional_and_only_on_the_act_2_map():
    assert all(_mission(m)["acts"] == (2,) and not _mission(m).get("once") for m in PAINT)
    st = _act2()
    ids = [m["id"] for m in ss.visible_missions(st)]
    assert ids[-3:] == PAINT and "phenix_5" in ids                 # beside the Phenix series, not inside it
    assert not ss.mission_open(ss.create_slot(1, "A", "normal"), _mission("paint_1"))


def test_a_won_mission_waits_for_the_next_pass():
    st = _act2()
    _win(st, "paint_1")
    assert ss.mission_done(st, _mission("paint_1")) and not ss.mission_done(st, _mission("paint_2"))
    assert not ss.mission_playable(st, _mission("paint_1"))          # not on its own


def test_the_third_win_ends_the_pass_and_gives_one_change():
    st = _act2()
    assert not ss.paint_state(st)["token"]
    _win(st, "paint_1")
    _win(st, "paint_2")
    assert not ss.paint_state(st)["token"]
    res = _win(st, "paint_3")
    assert res["paint"] and ss.paint_state(st) == {"step": 0, "runs": 1, "token": True}
    assert [ss.mission_playable(st, _mission(m)) for m in PAINT] == [True, False, False]   # renewable, from the start


def test_a_lost_run_changes_nothing_in_the_series():
    st = _act2()
    _win(st, "paint_1")
    st["credits"] = 200
    res = ss.record_result(st, "paint_2", 100, False, {})
    assert res["lost"] == 10 and ss.paint_state(st)["step"] == 1 and ss.mission_playable(st, _mission("paint_2"))


def test_the_cheat_cannot_skip_a_mission_of_the_series():
    st = _act2()
    _win(st, "paint_3")                                               # flown out of order with UNLK
    assert ss.paint_state(st) == {"step": 0, "runs": 0, "token": False}
    assert ss.mission_playable(st, _mission("paint_3"), cheat=True)


def test_the_level_goes_up_with_each_finished_pass():
    st = _act2()
    assert ss.paint_level(st) == 1
    for expected in (2, 3, 4):
        _pass(st)
        assert ss.paint_level(st) == expected
    _win(st, "paint_1")
    assert ss.paint_level(st) == 4                                    # a part of a pass does not count


def test_the_levels_of_the_series_are_1_2_3_then_4_5_6():
    st = _act2()
    levels = []
    for _ in range(3):
        levels.append([ss.invader_level(st, _mission(m)) for m in PAINT])
        _pass(st)
    assert levels == [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    assert [ss.mission_level(st, _mission(m)) for m in PAINT] == [10, 11, 12]
    assert ss.invader_level(st, None) == 1 + 3 * 3                    # a damaged call does not crash


def test_the_paint_missions_are_invasions_not_arcade_waves():
    for m in PAINT:
        mission = _mission(m)
        assert mission["invaders"] is True and ss.mission_waves(mission) == [] and not mission.get("swarm")


def test_only_hunts_and_paint_show_a_level():
    st = _act2()
    assert ss.mission_level(st, _mission("ch1_sortie")) == 1 and ss.mission_level(st, _mission("paint_1")) == 1
    assert ss.mission_level(st, _mission("phenix_1")) is None and ss.mission_level(st, None) is None


# ------------------------------------------------------------------ save data
def test_a_new_slot_has_no_paint_and_junk_is_cleaned(tmp_path):
    assert ss.default_state()["paint"] == {"step": 0, "runs": 0, "token": False}
    assert ss.paint_state({"paint": "broken"}) == {"step": 0, "runs": 0, "token": False}
    assert ss.paint_state({"paint": {"step": 9, "runs": -3, "token": 1}}) == {"step": 2, "runs": 0, "token": True}
    assert ss.paint_state({"paint": {"step": "x", "runs": True}}) == {"step": 0, "runs": 0, "token": False}
    old = ss.migrate_state({"version": 4, "name": "OLD", "cleared": ["ch1_sortie"]})
    assert old["paint"] == {"step": 0, "runs": 0, "token": False}


def test_the_paint_survives_a_save(tmp_path):
    st = _act2()
    _pass(st)
    _win(st, "paint_1")
    path = str(tmp_path / "s.json")
    ss.save_state(path, st)
    back = ss.load_state(path)
    assert ss.paint_state(back) == {"step": 1, "runs": 1, "token": True}


# ------------------------------------------------------------------ the paint shop
def test_the_paint_shop_row_comes_with_act_2_only():
    assert "paint" not in [r[0] for r in ss.shop_for(ss.create_slot(1, "A", "normal"))]
    assert [r[0] for r in ss.shop_for(_act2())][-1] == "paint"


def test_the_phenix_has_no_paint_shop_row():
    st = _act2()
    st["slots"][1]["owned"] = True
    st["selected_slot"] = 1
    assert "paint" not in [r[0] for r in ss.shop_for(st)]


def test_one_change_for_one_pass():
    st = _act2()
    assert not ss.paint_change(st, "green")                           # nothing earned yet
    _pass(st)
    assert not ss.paint_change(st, "red")                             # the colour already worn spends nothing
    assert ss.paint_state(st)["token"]
    assert not ss.paint_change(st, "pink")
    assert ss.paint_change(st, "green")
    assert st["slots"][0]["tint"] == "green" and not ss.paint_state(st)["token"]
    assert not ss.paint_change(st, "violet")                          # spent
    _pass(st)                                                         # a new pass earns another change
    assert ss.paint_change(st, "violet") and st["slots"][0]["tint"] == "violet"
    assert ss.paint_state(st)["runs"] == 2


def test_the_changes_do_not_pile_up():
    st = _act2()
    _pass(st)
    _pass(st)
    assert ss.paint_change(st, "green") and not ss.paint_change(st, "violet")


def test_the_loadout_wears_the_chosen_colour():
    st = _act2()
    assert ss.loadout(st)["tint"] == "red"
    _pass(st)
    ss.paint_change(st, "violet")
    assert ss.loadout(st)["tint"] == "violet"
    st["slots"][0]["tint"] = "rainbow"
    assert ss.loadout(st)["tint"] == "red"                            # a damaged value falls back


# ------------------------------------------------------------------ journal
def test_the_journal_follows_the_series_with_its_level():
    from i18n import t
    st = _act2()
    _pass(st)
    lines = [ss.log_text(e, t) for e in ss.journal_entries(st)[1:]]
    assert lines == [t("story_log_pt1"), t("story_log_level").format(n=4),
                     t("story_log_pt2"), t("story_log_level").format(n=5),
                     t("story_log_pt3"), t("story_log_level").format(n=6)]


# ------------------------------------------------------------------ hub and game
def _ready():
    from i18n import t
    return t("story_paint_ready").format(pts=ss.PAINT_COST)


def _hub(st):
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


def _texts(hub, run):
    import story
    seen = []
    real, real_fit = story._text, story._text_fit

    def spy(surface, font, text, *a, **k):
        seen.append(str(text))
        return real(surface, font, text, *a, **k)

    def spy_fit(surface, font, text, *a, **k):
        seen.append(str(text))
        return real_fit(surface, font, text, *a, **k)

    story._text, story._text_fit = spy, spy_fit
    try:
        g = run.game
        hub.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
    finally:
        story._text, story._text_fit = real, real_fit
    return seen


def _go_to_paint_row(hub):
    hub.pane = "hangar"
    hub.zone = "slots"
    hub.nav_v(1)
    for _ in range(10):
        hub.nav_v(1)
    assert hub.shop_rows()[hub.shop_index][0] == "paint"


def test_the_map_shows_the_series_with_its_level(run):
    from i18n import t
    st = _act2()
    _pass(st)
    hub = _hub(st)
    hub.pane = "map"
    ids = [m["id"] for m in hub.missions()]
    hub.map_index = ids.index("paint_1")
    shown = _texts(hub, run)
    row = [x for x in shown if t("story_m_pt1") in x]
    assert row and row[0].endswith(t("story_level").format(n=4))
    hub.map_index = ids.index("paint_3")
    shown = _texts(hub, run)
    row = [x for x in shown if t("story_m_pt3") in x]
    assert row and t("story_level").format(n=6) not in row[0]         # a locked mission shows no level yet
    assert t("story_locked") in shown                                    # the next missions wait their turn


def test_without_a_change_the_row_is_locked_and_opens_nothing(run):
    from i18n import t
    hub = _hub(_act2())
    _go_to_paint_row(hub)
    shown = _texts(hub, run)
    assert any(t("story_shop_paint") in x for x in shown) and _ready() not in shown
    hub.confirm()
    assert not hub.paint_mode and hub.toast == t("story_paint_locked")


def test_the_paint_shop_changes_the_colour_once_and_saves(run):
    from i18n import t
    st = _act2()
    _pass(st)
    hub = _hub(st)
    _go_to_paint_row(hub)
    assert _ready() in _texts(hub, run)
    hub.confirm()
    assert hub.paint_mode and hub.paint_choice == 0
    shown = _texts(hub, run)
    assert t("story_paint_title").format(pts=500) in shown and any(t("story_paint_green") in x for x in shown)
    hub.nav_h(1)
    assert hub.paint_choice == 1 and hub.pane == "hangar"             # the arrows choose the colour here
    hub.confirm()
    assert not hub.paint_mode and hub.state["slots"][0]["tint"] == "green" and hub.toast == t("story_paint_done")
    again = StoryHub()
    again.open_slot(1)
    assert again.state["slots"][0]["tint"] == "green" and not ss.paint_state(again.state)["token"]
    _go_to_paint_row(again)
    again.confirm()
    assert not again.paint_mode                                       # spent: the row is locked again


def test_the_colour_wraps_and_the_same_colour_spends_nothing():
    st = _act2()
    _pass(st)
    hub = _hub(st)
    _go_to_paint_row(hub)
    hub.confirm()
    hub.nav_h(-1)
    assert hub.paint_choice == 2
    hub.nav_h(1)
    assert hub.paint_choice == 0
    hub.confirm()                                                     # red again
    assert not hub.paint_mode and ss.paint_state(hub.state)["token"] and hub.state["slots"][0]["tint"] == "red"


def test_back_closes_the_paint_shop_without_spending_or_leaving():
    st = _act2()
    _pass(st)
    hub = _hub(st)
    _go_to_paint_row(hub)
    hub.confirm()
    hub.nav_h(1)
    assert hub.back() is True
    assert not hub.paint_mode and hub.screen == "hub" and ss.paint_state(hub.state)["token"]
    assert hub.state["slots"][0]["tint"] == "red"


def test_up_down_do_nothing_while_choosing_a_colour():
    st = _act2()
    _pass(st)
    hub = _hub(st)
    _go_to_paint_row(hub)
    index = hub.shop_index
    hub.confirm()
    hub.nav_v(-1)
    hub.nav_v(1)
    assert hub.paint_mode and hub.shop_index == index


def test_finishing_the_series_tells_the_player(run):
    from i18n import t
    st = _act2()
    _win(st, "paint_1")
    _win(st, "paint_2")
    hub = _hub(st)
    hub.apply_result("paint_3", 100, True)
    assert hub.toast == t("story_paint_done_series") and ss.paint_state(hub.state)["token"]


def test_the_hangar_draws_the_shield_in_its_colour(run):
    st = _act2()
    _pass(st)
    ss.paint_change(st, "violet")
    hub = _hub(st)
    hub.pane = "hangar"
    hub._ensure_art()
    for key, rgb in (("shield_red", (4, 5, 6)), ("shield_violet", (1, 2, 3)), ("shield_green", (7, 8, 9))):
        marker = pygame.Surface((60, 60))
        marker.fill(rgb)
        hub._portraits[key] = marker                                     # a plain block per colour: easy to find
    surf = pygame.Surface((1280, 720))
    g = run.game
    hub.draw(surf, g.font, g.medium_font, g.font)
    assert tuple(surf.get_at((400, 110)))[:3] == (1, 2, 3)           # the middle of the first hull


def _launch(g, st, mission_id):
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mission_id)
    spec = g.story._launch_selected()
    assert spec, mission_id
    g._begin_adventure(spec)
    return spec


def test_the_first_pass_flies_invaders_of_level_1_2_3(run):
    from invaders import InvaderFormation
    g = run.game
    st = _act2()
    for mid, level in (("paint_1", 1), ("paint_2", 2), ("paint_3", 3)):
        spec = _launch(g, st, mid)
        _win(st, mid)
        assert spec["level"] == level and spec["invaders"] is True and "waves" not in spec
        assert isinstance(g.formation, InvaderFormation) and g.formation.level == level
        assert len(g.formation.enemies) == 44


def test_the_second_pass_flies_levels_4_5_6(run):
    g = run.game
    st = _act2()
    _pass(st)
    for mid, level in (("paint_1", 4), ("paint_2", 5), ("paint_3", 6)):
        spec = _launch(g, st, mid)
        _win(st, mid)
        assert spec["level"] == level and g.formation.level == level


def test_a_hunt_after_a_paint_mission_gets_the_ordinary_grid_back(run):
    from enemy import EnemyFormation
    from invaders import InvaderFormation
    g = run.game
    st = _act2()
    _launch(g, st, "paint_1")
    assert isinstance(g.formation, InvaderFormation)
    g._end_adventure(False)
    _launch(g, st, "ch1_sortie")
    assert type(g.formation) is EnemyFormation and g.formation.enemies


def test_an_arcade_game_after_an_invasion_does_not_keep_the_invaders(run):
    from enemy import EnemyFormation
    g = run.game
    _launch(g, _act2(), "paint_1")
    g._end_adventure(False)
    assert g.adventure is None
    g._setup_stage(1)                                  # what a new arcade game does first
    assert type(g.formation) is EnemyFormation and g.formation.enemies


def test_the_hud_shows_the_level_of_the_series(run):
    from i18n import t
    import text_cache as tc_mod
    g = run.game
    st = _act2()
    _pass(st)
    _pass(st)
    _win(st, "paint_1")
    _win(st, "paint_2")
    _launch(g, st, "paint_3")
    seen = []
    orig = tc_mod.TextCache.get

    def spy(self, font, text, *a, **k):
        seen.append(str(text))
        return orig(self, font, text, *a, **k)

    tc_mod.TextCache.get = spy
    try:
        run.frames(2, 1 / 60)
    finally:
        tc_mod.TextCache.get = orig
    assert any(t("story_level").format(n=9) in x for x in seen)


def test_a_won_pass_in_the_game_opens_the_paint_shop(run):
    g = run.game
    st = _act2()
    _win(st, "paint_1")
    _win(st, "paint_2")
    _launch(g, st, "paint_3")
    g.score = 300
    g._end_adventure(True)
    assert ss.paint_state(g.story.state)["token"] and ss.paint_level(g.story.state) == 2


def test_the_ship_flies_in_its_new_colour(run):
    g = run.game
    st = _act2()
    _pass(st)
    ss.paint_change(st, "green")
    _launch(g, st, "ch1_sortie")
    assert g.player.ship_id == "shield" and g.player.shield_tint == "green"


def test_the_next_missions_of_the_series_show_as_locked_until_their_turn():
    st = _act2()
    assert [ss.mission_open(st, _mission(m)) for m in PAINT] == [True, False, False]
    _win(st, "paint_1")
    assert [ss.mission_open(st, _mission(m)) for m in PAINT] == [True, True, False]
    _pass(st)
    assert [ss.mission_open(st, _mission(m)) for m in PAINT] == [True, False, False]     # a new pass


# ------------------------------------------------------------------ the paint costs 500
def test_the_paint_costs_500_points():
    assert ss.PAINT_COST == 500
    assert [r for r in ss.shop_for(_act2()) if r[0] == "paint"][0][2] == 500


def test_painting_takes_the_credits_and_a_refused_change_takes_nothing():
    st = _act2()
    _pass(st)
    before = st["credits"]
    assert ss.paint_change(st, "green") and st["credits"] == before - 500
    st2 = _act2()
    _pass(st2)
    kept = st2["credits"]
    assert not ss.paint_change(st2, "red") and st2["credits"] == kept          # the same colour: free of charge
    assert not ss.paint_change(st2, "pink") and st2["credits"] == kept


@pytest.mark.parametrize("credits, ok", [(499, False), (500, True), (501, True)])
def test_the_change_needs_exactly_the_price(credits, ok):
    st = _act2()
    _pass(st)
    st["credits"] = credits
    assert ss.paint_change(st, "violet") is ok
    assert st["credits"] == (credits - 500 if ok else credits)
    assert ss.paint_state(st)["token"] is (not ok)                            # nothing spent, the change waits


def test_too_poor_to_paint_the_shop_does_not_open_and_says_so(run):
    from i18n import t
    st = _act2()
    _pass(st)
    st["credits"] = 120
    hub = _hub(st)
    _go_to_paint_row(hub)
    hub.confirm()
    assert not hub.paint_mode and hub.toast == t("story_paint_poor").format(pts=500)
    assert ss.paint_state(hub.state)["token"] and hub.state["credits"] == 120
    shown = _texts(hub, run)
    assert _ready() in shown                                                  # the price is on the row


def test_the_paint_shop_charges_when_the_colour_is_worn_and_saves_it(run):
    st = _act2()
    _pass(st)
    credits = st["credits"]
    hub = _hub(st)
    _go_to_paint_row(hub)
    hub.confirm()
    hub.nav_h(1)
    hub.confirm()
    assert hub.state["credits"] == credits - 500
    again = StoryHub()
    again.open_slot(1)
    assert again.state["credits"] == credits - 500 and again.state["slots"][0]["tint"] == "green"


def test_leaving_the_paint_shop_or_keeping_the_colour_costs_nothing():
    st = _act2()
    _pass(st)
    credits = st["credits"]
    hub = _hub(st)
    _go_to_paint_row(hub)
    hub.confirm()
    hub.back()
    hub.confirm()
    hub.confirm()                                                             # red again
    assert hub.state["credits"] == credits and ss.paint_state(hub.state)["token"]
