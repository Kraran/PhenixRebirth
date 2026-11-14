"""The achievement banners wait in a queue: never two at once, none lost, and one taken over by another banner (1UP,
a code, the pad) comes back after it. The results of a mission read « Échec · … », not two spaces."""
import json
import os

import pytest

import i18n
from test_smoke import run  # noqa: F401  (fixture)

ROOT = os.path.join(os.path.dirname(__file__), "..")


@pytest.fixture
def g(run, monkeypatch):
    game = run.game
    game.started, game.attract_mode = False, False
    game.menu_screen = "main"
    game.cheat_msg, game.cheat_kind, game.cheat_msg_timer = "", "", 0.0
    game._ach_queue = []
    game._ach_on = None
    monkeypatch.setattr(game.sounds, "play_achievement", lambda: None)
    return game


def _end_banner(g):
    g.cheat_msg_timer = 0.0
    g._tick_banners()


def test_a_second_achievement_waits_for_the_first(g):
    g._show_ach("HAUT FAIT — A", 3.0)
    g._show_ach("HAUT FAIT — B", 3.0)
    assert g.cheat_msg == "HAUT FAIT — A" and g.cheat_kind == "ach"
    for _ in range(5):
        g._tick_banners()
    assert g.cheat_msg == "HAUT FAIT — A"                               # (the first one keeps its time)
    _end_banner(g)
    assert g.cheat_msg == "HAUT FAIT — B" and g.cheat_msg_timer == pytest.approx(3.0)
    _end_banner(g)
    assert not g._ach_queue


def test_the_same_achievement_is_not_queued_twice(g):
    g._show_ach("HAUT FAIT — A", 3.0)
    g._show_ach("HAUT FAIT — A", 3.0)
    g._show_ach("HAUT FAIT — B", 3.0)
    g._show_ach("HAUT FAIT — B", 3.0)
    assert [q[0] for q in g._ach_queue] == ["HAUT FAIT — B"]


def test_an_achievement_waits_for_a_one_up(g):
    g.cheat_msg, g.cheat_kind, g.cheat_msg_timer = "1UP", "1up", 3.0
    g._show_ach("HAUT FAIT — A", 3.0)
    assert g.cheat_kind == "1up"
    _end_banner(g)
    assert g.cheat_msg == "HAUT FAIT — A" and g.cheat_kind == "ach"


def test_an_achievement_taken_over_comes_back_after(g):
    g._show_ach("HAUT FAIT — A", 3.0)
    g._tick_banners()
    g.cheat_msg, g.cheat_kind, g.cheat_msg_timer = "1UP", "1up", 5.0        # (the 1UP takes the banner at once)
    g._tick_banners()
    assert g.cheat_kind == "1up"
    _end_banner(g)
    assert g.cheat_msg == "HAUT FAIT — A" and g.cheat_msg_timer == pytest.approx(3.0)


def test_the_adventure_news_go_through_the_same_queue(g):
    import story_feats
    i18n.set_lang("fr")
    g._show_ach("HAUT FAIT — A", 3.0)
    story_feats._news[:] = [("adv_pilot", None)]
    g._tick_story_feats()
    assert g.cheat_msg == "HAUT FAIT — A"
    _end_banner(g)
    assert g.cheat_msg == "HAUT FAIT — Matricule"


def test_the_results_of_a_mission_use_a_middle_dot():
    for code in ("fr", "en"):
        i18n.set_lang(code)
        for key in ("story_fail_none", "story_fail_pen", "story_clear", "story_test_clear", "story_test_retry",
                    "story_ast_end"):
            text = i18n.t(key)
            assert " · " in text and "  " not in text, (code, key)
    i18n.set_lang("fr")
    assert i18n.t("story_fail_none") == "Échec · aucune perte"
    for name in os.listdir(os.path.join(ROOT, "assets", "lang")):
        with open(os.path.join(ROOT, "assets", "lang", name), encoding="utf-8") as f:
            data = json.load(f)
        for key in ("story_fail_none", "story_fail_pen"):
            if key in data:
                assert " · " in data[key] and "  " not in data[key], (name, key)
