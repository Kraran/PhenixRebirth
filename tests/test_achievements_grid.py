"""The achievements screen: a grid of icons, a panel that says how to get the one under the cursor, the secret ones
hidden until they are unlocked, Tab / LB / RB to go to the scores and the jukebox."""
import pygame
import pytest

import achievements
import achievements_screen as scr
import hint_bar
import i18n
from achievements import CATALOG, SCALABLE, SECRETS


class Runner:
    def __init__(self, game):
        self.game = game

    def frames(self, n=1):
        g = self.game
        for _ in range(n):
            g.dt = 1 / 60
            g.handle_events()
            g.update()
            g.draw()

    def key(self, key, mod=0, frames=2):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=mod, scancode=0))
        self.frames(frames)

    def button(self, button, frames=2):
        self.game.input_grace = 0.0
        pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=button, joy=0, instance_id=0))
        self.frames(frames)

    def hat(self, value, frames=2):
        self.game.input_grace = 0.0
        self.game._hat_latch = (0, 0)
        pygame.event.post(pygame.event.Event(pygame.JOYHATMOTION, value=value, joy=0, instance_id=0, hat=0))
        self.frames(frames)


def _data():
    data = {"unlocked": {}, "progress": {}, "tiers": {}}
    for aid, prog, tier in (("first_blood", 734, "silver"), ("iron_curtain", 52, "gold"), ("loop", 3, "bronze"),
                            ("razor", 3, "normal")):
        data["unlocked"][aid] = "2026-09-02T20:00:00Z"
        data["progress"][aid] = prog
        data["tiers"][aid] = tier
    data["unlocked"]["credits_watch"] = "2026-10-01T10:00:00Z"
    data["progress"]["marathon"] = 3200
    return data


@pytest.fixture
def run():
    from game import Game

    game = Game()
    game._intro_done = True
    game.fade_phase = None
    game.input_grace = 0.0
    i18n.set_lang("fr")
    r = Runner(game)
    r.frames(2)
    game._open_extra("achievements")
    game.ach_data = _data()
    game.ach_index = 0
    r.frames(2)
    yield r
    game.running = False
    i18n.set_lang("fr")


# --- the cursor ------------------------------------------------------------------------------------------------------
def test_the_arrows_move_in_the_grid(run):
    g = run.game
    run.key(pygame.K_RIGHT)
    assert g.ach_index == 1 and g.menu_screen == "achievements"
    run.key(pygame.K_DOWN)
    assert g.ach_index == 1 + scr.COLS
    run.key(pygame.K_LEFT)
    assert g.ach_index == scr.COLS
    run.key(pygame.K_UP)
    run.key(pygame.K_UP)
    assert g.ach_index == len(CATALOG) - scr.COLS          # Up from the first row: the last row, same column
    assert g.ach_page == 0


def test_the_edges_of_the_grid_turn_the_page(run):
    g = run.game
    g.ach_index = scr.COLS - 1                              # last card of the first row
    run.key(pygame.K_RIGHT)
    assert (g.ach_page, g.ach_index) == (1, 0)              # AVENTURE, first card of the first row
    run.key(pygame.K_LEFT)
    assert (g.ach_page, g.ach_index) == (0, scr.COLS - 1)   # back on ARCADE, where it was
    g.ach_index = 3 * scr.COLS                              # ARCADE, fourth row: AVENTURE has three rows only
    run.key(pygame.K_LEFT)
    n = len(achievements.CATALOG_ADV)
    assert g.ach_page == 1 and g.ach_index == n - 1         # the last card of its last row
    run.key(pygame.K_RIGHT)
    assert (g.ach_page, g.ach_index) == (0, 2 * scr.COLS)   # the pages go round: ARCADE, third row


def test_a_page_change_slides_and_ticks(run):
    import menu_fx
    import menu_sfx
    g = run.game
    before_key, before = menu_fx.screen_key(g), menu_sfx.snapshot(g)
    g.ach_index = scr.COLS - 1
    g._ach_move(1, 0)
    assert menu_fx.screen_key(g) != before_key
    assert menu_sfx.choose(g, before, menu_sfx.snapshot(g), "nav") == menu_sfx.MOVE


@pytest.mark.parametrize("key", [pygame.K_z, pygame.K_w, pygame.K_s, pygame.K_q, pygame.K_a, pygame.K_d])
def test_zqsd_and_wasd_move_too(run, key):
    g = run.game
    g.ach_index = 9
    run.key(key)
    assert g.ach_index != 9 and g.menu_screen == "achievements"


def test_the_d_pad_moves_in_the_grid(run):
    g = run.game
    run.hat((1, 0))
    assert g.ach_index == 1
    run.hat((0, -1))
    assert g.ach_index == 1 + scr.COLS
    run.hat((0, 1))
    run.hat((-1, 0))
    assert g.ach_index == 0 and g.menu_screen == "achievements"


def test_move_skips_the_holes_of_a_last_row():
    class G:
        ach_index = 6
        ach_page = 1                                                # AVENTURE: 8 + 8 + 4
    g = G()
    scr.move(g, 0, -1)
    assert g.ach_index == 14                                        # the third row has no 7th card
    scr.move(g, 0, 1)
    assert g.ach_index == 6


@pytest.mark.parametrize("key,mod,where", [(pygame.K_TAB, 0, "jukebox"), (pygame.K_TAB, pygame.KMOD_SHIFT, "highscores"),
                                           (pygame.K_PAGEDOWN, 0, "jukebox"), (pygame.K_PAGEUP, 0, "highscores")])
def test_tab_goes_to_the_scores_and_the_jukebox(run, key, mod, where):
    run.key(key, mod=mod)
    assert run.game.menu_screen == where


@pytest.mark.parametrize("button,where", [(4, "highscores"), (5, "jukebox")])
def test_lb_rb_go_to_the_scores_and_the_jukebox(run, button, where):
    run.button(button)
    assert run.game.menu_screen == where


def test_tab_and_lb_rb_also_work_on_the_scores(run):
    g = run.game
    g._open_extra("highscores")
    run.frames(2)
    run.key(pygame.K_TAB)
    assert g.menu_screen == "achievements"
    run.button(4)
    assert g.menu_screen == "highscores"


def test_enter_and_a_stay_on_the_grid(run):
    g = run.game
    run.key(pygame.K_RIGHT)
    run.key(pygame.K_RETURN)
    assert g.menu_screen == "achievements" and g.ach_index == 1
    run.button(0)
    assert g.menu_screen == "achievements" and g.ach_index == 1


def test_the_cursor_is_kept_from_one_visit_to_the_next(run):
    g = run.game
    g.ach_index = 13
    run.key(pygame.K_ESCAPE)
    assert g.menu_screen == "extras"
    g._open_extra("achievements")
    run.frames(2)
    assert g.ach_index == 13


def test_a_move_ticks(run):
    import menu_sfx
    g = run.game
    before = menu_sfx.snapshot(g)
    g._ach_move(1, 0)
    assert menu_sfx.choose(g, before, menu_sfx.snapshot(g), "nav") == menu_sfx.MOVE


# --- what the panel says ---------------------------------------------------------------------------------------------
def test_a_locked_one_says_how_to_get_it(run):
    info = scr.detail_texts(run.game, "no_edge", run.game.ach_data)
    assert info["title"] == i18n.t("ach_no_edge")
    assert info["how"] == i18n.t("ach_no_edge_d") and "murs" in info["how"]
    assert info["status"] == "Verrouillé"


def test_a_secret_is_hidden_until_it_is_unlocked(run):
    g = run.game
    info = scr.detail_texts(g, "pleiades", g.ach_data)
    assert info["hidden"] and info["title"] == "Haut fait secret"
    assert i18n.t("ach_pleiades") not in str(info) and i18n.t("ach_pleiades_d") not in str(info)
    assert info["progress"] is None and info["steps"] == []
    shown = scr.detail_texts(g, "razor", g.ach_data)              # a secret already found
    assert not shown["hidden"] and shown["title"] == i18n.t("ach_razor")


def test_the_secrets_are_real_achievements():
    assert SECRETS <= set(achievements.ALL_IDS)
    assert achievements.is_hidden("pleiades", {"unlocked": {}})
    assert not achievements.is_hidden("pleiades", {"unlocked": {"pleiades": "x"}})
    assert not achievements.is_hidden("first_blood", {"unlocked": {}})


def test_the_tiers_and_the_way_to_the_next_one(run):
    g = run.game
    info = scr.detail_texts(g, "first_blood", g.ach_data)
    assert info["status"] == "Argent · 02/09/2026"
    assert [n for n, _th in info["steps"]] == ["normal", "bronze", "silver", "gold"]
    assert info["progress"] == "Tu en es à 734. Prochain palier : Or, encore 1 266."
    gold = scr.detail_texts(g, "iron_curtain", g.ach_data)
    assert gold["progress"] == "Tu en es à 52. Tous les paliers sont atteints !"
    locked = scr.detail_texts(g, "marathon", g.ach_data)
    assert locked["progress"] == "Tu en es à 3 200 sur 5 000 pour le débloquer."
    plain = scr.detail_texts(g, "credits_watch", g.ach_data)
    assert plain["status"] == "Débloqué · 01/10/2026" and plain["progress"] is None and plain["steps"] == []


def test_a_single_step_shows_no_tiers(run):
    g = run.game
    data = {"unlocked": {"boldly_go": "2026-01-01T00:00:00Z"}, "progress": {"boldly_go": 21},
            "tiers": {"boldly_go": "gold"}}
    info = scr.detail_texts(g, "boldly_go", data)
    assert info["steps"] == [] and info["progress"] is None and info["status"].startswith("Or ·")


def test_numbers_are_written_as_each_language_does():
    for lang, text in (("fr", "1 266"), ("en", "1,266"), ("de", "1.266")):
        i18n.set_lang(lang)
        assert scr.fmt_num(1266) == text
    i18n.set_lang("fr")


def test_no_description_repeats_the_tiers():
    """The tiers are on the panel's line now: the descriptions only say what to do."""
    for aid in SCALABLE:
        for lang in i18n.LANG_CODES:
            text = i18n.T["ach_" + aid + "_d"][lang]
            assert i18n.T["ach_tier_gold"][lang] not in text, (aid, lang)


def test_every_language_has_the_panel_texts():
    for key in ("ach_how", "ach_steps", "ach_step_first", "ach_done", "ach_secret", "ach_secret_status",
                "ach_secret_d", "ach_progress_unlock", "ach_progress_next", "ach_progress_done", "ach_secrets_left",
                "hint_scores_jukebox"):
        for lang in i18n.LANG_CODES:
            assert i18n.T[key].get(lang), (key, lang)


# --- drawing -----------------------------------------------------------------------------------------------------------
def _ink(img, rect):
    """Is anything drawn in `rect` of a see-through layer?"""
    return pygame.mask.from_surface(img.subsurface(rect), 40).count() > 0


@pytest.mark.parametrize("lang", i18n.LANG_CODES)
def test_every_text_fits_in_the_panel_and_under_the_grid(run, lang):
    g = run.game
    i18n.set_lang(lang)
    full = {"unlocked": {aid: "2026-09-02T20:00:00Z" for aid in achievements.ALL_IDS},
            "progress": {aid: steps[-1] for aid, steps in SCALABLE.items()},
            "tiers": {aid: "gold" for aid in SCALABLE}}
    w, h = scr.DETAIL.size
    for data in (g.ach_data, full, {"unlocked": {}, "progress": {"marathon": 99999}, "tiers": {}}):
        for aid, kind in CATALOG + achievements.CATALOG_ADV:
            img = scr._detail_layer(g, aid, kind, data)
            assert not _ink(img, pygame.Rect(w - 10, 0, 10, h)), (lang, aid, "right edge")
            assert not _ink(img, pygame.Rect(0, h - 40, w, 40)), (lang, aid, "bottom")
        for pg in range(len(achievements.PAGES)):
            grid = scr._grid_layer(g, data, pg)
            below = pygame.Rect(scr.GRID_W - 6, scr.SUMMARY_Y + 34, 6, scr.LAYER_H - scr.SUMMARY_Y - 34)
            assert not _ink(grid, below), (lang, pg, "summary")
    # the tabs: both fit between the screen's edges, under the title
    surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
    scr._tabs(g, surf)
    box = pygame.mask.from_surface(surf, 40).get_bounding_rects()[0]
    assert box.left > scr.GRID_X and box.right < scr.DETAIL.right, lang


def test_the_screen_draws_and_the_cursor_is_framed(run):
    g = run.game
    g.ach_index = 10
    surf = pygame.Surface((1280, 720))
    surf.fill((1, 2, 3))
    scr.draw_achievements_inner(g, surf)
    r = scr.cell_rect(10).inflate(10, 10)
    import menu_ui
    assert surf.get_at((r.centerx, r.top + 1))[:3] == menu_ui.SEL_EDGE
    # the grid stays left of the panel, both above the help bar
    assert scr.cell_rect(scr.COLS - 1).right < scr.DETAIL.left
    assert scr.GRID_Y + scr.LAYER_H < hint_bar.BAND_Y and scr.DETAIL.bottom < hint_bar.BAND_Y
    assert scr.TABS_Y + 30 < scr.GRID_Y - 5                                  # the tabs above the cursor's frame


def test_the_second_page_draws(run):
    g = run.game
    g.ach_page, g.ach_index = 1, 5
    surf = pygame.Surface((1280, 720))
    surf.fill((1, 2, 3))
    scr.draw_achievements_inner(g, surf)
    r = scr.cell_rect(5).inflate(10, 10)
    import menu_ui
    assert surf.get_at((r.centerx, r.top + 1))[:3] == menu_ui.SEL_EDGE
    assert scr.catalog(g) is achievements.CATALOG_ADV
    # the room kept for Act 3: nothing drawn after the twentieth card
    empty = scr.cell_rect(len(achievements.CATALOG_ADV)).inflate(-4, -4)
    assert surf.get_at(empty.center)[:3] == (1, 2, 3)


def test_each_page_counts_its_own(run):
    g = run.game
    data = {"unlocked": {"first_blood": "x", "adv_pilot": "x", "adv_act2": "x"}, "progress": {}, "tiers": {}}
    assert achievements.unlocked_count(data, achievements.CATALOG_IDS) == 1
    assert achievements.unlocked_count(data, achievements.ADV_IDS) == 2
    assert achievements.unlocked_count(data) == 3


def test_the_layers_are_kept_between_frames(run):
    g = run.game
    a = scr._grid_layer(g, g.ach_data)
    assert scr._grid_layer(g, g.ach_data) is a
    d = scr._detail_layer(g, "first_blood", "bird1", g.ach_data)
    assert scr._detail_layer(g, "first_blood", "bird1", g.ach_data) is d
    g.ach_data["progress"]["first_blood"] = 735                     # a new kill: drawn again
    assert scr._detail_layer(g, "first_blood", "bird1", g.ach_data) is not d
    assert scr._grid_layer(g, g.ach_data) is not a


def test_the_bar_says_choose_and_tab(run):
    g = run.game
    items = hint_bar.menu_items(g)
    assert ("all", "hint_choose") in items and ("sh", "hint_scores_jukebox") in items
    g.story_door = "achievements"                                    # opened from the Adventure: no tabs
    try:
        assert ("sh", "hint_scores_jukebox") not in hint_bar.menu_items(g)
    finally:
        g.story_door = None
