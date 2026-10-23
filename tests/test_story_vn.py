"""The visual novel that begins after the concert of Lyra Voss (src/story_vn.py, the screen "vn" of story.py): the film of
the bar, then a scene with a text and four answers worth hidden points. The answer is final, kept in the save, and the
scene can be watched again from the journal."""
import os

import pygame
import pytest

import i18n
import story_state as ss
import story_vn
from settings import BASE_HEIGHT, BASE_WIDTH, asset_path
from story import StoryHub

SCENE = "vn_1"
EMPTY = {"picks": {}, "marks": {}}


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((64, 64))
    yield


@pytest.fixture
def french():
    before = i18n.get_lang()
    i18n.set_lang("fr")
    yield
    i18n.set_lang(before)


@pytest.fixture(autouse=True)
def _no_film_files(monkeypatch):
    """The films are not decoded in these tests: the scene comes straight away (the case of a missing file)."""
    monkeypatch.setattr(ss, "film_files", lambda film_id: None)


def _state(concert=True):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    if concert:
        for fid in ("lyra_1", "lyra_2", "lyra_3"):
            ss.mark_film_seen(st, fid)
    return st


def _hub(concert=True):
    st = _state(concert)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


def _ready(hub):
    hub.vn_t = hub.VN_FADE + 999.0
    assert hub.vn_ready()


def _draw(hub):
    font = pygame.font.Font(None, 28)
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    hub.draw(surf, font, font, font)
    return surf


# ------------------------------------------------------------------ the scene and its hidden points
def test_scene_one_is_the_bar_of_phobos_with_four_answers_worth_1_2_3_4():
    sc = story_vn.scene(SCENE)
    assert sc["image"] == "vn_1_bar" and sc["film"] == "vn_1" and sc["speaker"] == "story_vn_lyra"
    assert [pts for _k, pts in sc["answers"]] == [1, 2, 3, 4]
    assert [k for k, _p in sc["answers"]] == ["story_vn1_a1", "story_vn1_a2", "story_vn1_a3", "story_vn1_a4"]
    assert story_vn.VN_ORDER == [SCENE, "vn_2"]


@pytest.mark.parametrize("index,expected", [(0, 1), (1, 2), (2, 3), (3, 4)])
def test_each_answer_gives_its_own_points(index, expected):
    st = {}
    assert story_vn.points(st) == 0
    assert story_vn.choose(st, SCENE, index)
    assert story_vn.pick(st, SCENE) == index and story_vn.points(st) == expected


def test_an_answer_is_final():
    st = {}
    assert story_vn.choose(st, SCENE, 1)
    assert not story_vn.choose(st, SCENE, 3)
    assert story_vn.pick(st, SCENE) == 1 and story_vn.points(st) == 2


@pytest.mark.parametrize("scene,index", [("nope", 0), (SCENE, -1), (SCENE, 4), (SCENE, True), (SCENE, "1"), (SCENE, None)])
def test_a_wrong_answer_is_refused(scene, index):
    st = {}
    assert not story_vn.choose(st, scene, index)
    assert story_vn.points(st) == 0 and story_vn.pick(st, SCENE) is None and not story_vn.answered(st, SCENE)


@pytest.mark.parametrize("raw", [None, 3, "x", [], {}, {"picks": 5}, {"picks": {"nope": 1}}, {"picks": {SCENE: 9}},
                                 {"picks": {SCENE: -1}}, {"picks": {SCENE: 4}}, {"picks": {SCENE: True}}, {"picks": {SCENE: "2"}}])
def test_a_damaged_vn_field_is_cleaned(raw):
    assert story_vn.clean(raw) == EMPTY
    assert story_vn.points({"vn": raw}) == 0


def test_a_good_vn_field_is_kept():
    assert story_vn.clean({"picks": {SCENE: 2}, "extra": 1}) == {"picks": {SCENE: 2}, "marks": {}}
    assert story_vn.points({"vn": {"picks": {SCENE: 2}}}) == 3


def test_scene_of_film():
    assert story_vn.scene_of_film("vn_1") == SCENE
    assert story_vn.scene_of_film("lyra_3") is None and story_vn.scene_of_film("") is None
    assert story_vn.scene_of_film(None) is None          # (scene 2 has no film: None is not its film)


# ------------------------------------------------------------------ the save
def test_a_new_save_has_no_answers_and_a_save_keeps_them(tmp_path):
    assert ss.default_state()["vn"] == EMPTY
    st = _state()
    assert story_vn.choose(st, SCENE, 2)
    ss.save_state(ss.story_path(1), st)
    back = ss.load_state(ss.story_path(1))
    assert back["vn"] == {"picks": {SCENE: 2}, "marks": {SCENE: 0}} and story_vn.points(back) == 3


def test_an_old_save_without_the_field_gets_an_empty_one():
    st = ss.migrate_state({"version": 4, "act": 2, "flags": {}})
    assert st["vn"] == EMPTY


def test_a_damaged_field_in_a_save_is_cleaned_on_load():
    st = ss.migrate_state({"version": 4, "act": 2, "vn": {"picks": {SCENE: 77, "nope": 1}}})
    assert st["vn"] == EMPTY


# ------------------------------------------------------------------ the film and the journal
def test_the_film_of_the_bar_comes_after_the_third_song_of_the_concert():
    assert ss.film_after("lyra_3") == "vn_1"
    assert ss.film_chain(ss.VIP_SCENE) == ["lyra_1", "lyra_2", "lyra_3", "vn_1"]
    assert ss.FILMS["vn_1"]["video"] == "vn_1_bar" and ss.FILMS["vn_1"]["quiet"] and ss.FILMS["vn_1"]["vn"] == SCENE


def test_the_media_are_in_the_game_folders():
    assert os.path.isfile(asset_path("video", "vn_1_bar.mp4"))
    assert os.path.isfile(asset_path("video", "vn_1_bar.ogg"))
    assert os.path.isfile(asset_path("story", "vn_1_bar.jpg"))


def test_the_scene_is_due_once_the_concert_is_over_and_until_it_is_answered():
    assert ss.vn_due(_state(concert=False)) is None
    st = _state()
    assert ss.vn_due(st) == SCENE
    story_vn.choose(st, SCENE, 0, ss.story_wins(st))
    assert ss.vn_due(st) is None


def test_the_scene_is_due_after_the_third_song_only():
    st = _state(concert=False)
    for fid in ("lyra_1", "lyra_2"):
        ss.mark_film_seen(st, fid)
    assert ss.vn_due(st) is None
    ss.mark_film_seen(st, "lyra_3")
    assert ss.vn_due(st) == SCENE


def test_the_journal_lists_the_scene_once_its_film_was_watched(french):
    st = _state()
    assert {"film": "vn_1"} not in ss.journal_entries(st)
    ss.mark_film_seen(st, "vn_1")
    entries = ss.journal_entries(st)
    assert entries.index({"film": "lyra_3"}) + 1 == entries.index({"film": "vn_1"})
    assert ss.log_text({"film": "vn_1"}, i18n.t) == "Revoir : Visual novel - Scène 1 : le bar de Phobos"


# ------------------------------------------------------------------ the flow
def test_the_third_song_ends_on_the_film_of_the_bar_then_the_scene(monkeypatch):
    hub = _hub(concert=False)
    assert hub.screen == "hub"
    films = []
    real = hub.start_film

    def spy(film_id, back_to="map"):
        films.append(film_id)
        return real(film_id, back_to)

    monkeypatch.setattr(hub, "start_film", spy)
    hub.film_id, hub.film_return, hub.screen = "lyra_3", "map", "film"
    hub._end_film()
    assert films == ["vn_1"]                      # (no file here: the scene follows at once)
    assert hub.screen == "vn" and hub.vn_id == SCENE and not hub.vn_review
    assert ss.film_seen(hub.state, "lyra_3") and ss.film_seen(hub.state, "vn_1")


def test_the_end_of_the_film_of_the_bar_opens_the_scene():
    hub = _hub(concert=False)
    hub.film_id, hub.film_return, hub.screen = "vn_1", "map", "film"
    hub._end_film()
    assert hub.screen == "vn" and hub.vn_id == SCENE and hub.vn_return == "map"


def test_a_film_that_cannot_play_goes_on_to_the_scene():
    hub = _hub(concert=False)
    assert hub.start_film("vn_1", back_to="log") is False
    assert hub.screen == "vn" and hub.vn_return == "log"


def test_opening_a_save_after_the_concert_tells_the_scene():
    hub = _hub()
    assert hub.screen == "vn" and hub.vn_id == SCENE and hub.vn_return == "map"


def test_opening_a_save_before_the_concert_does_not():
    assert _hub(concert=False).screen == "hub"


def test_opening_an_answered_save_does_not_tell_the_scene_again():
    st = _state()
    story_vn.choose(st, SCENE, 1, ss.story_wins(st))
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    assert hub.screen == "hub"


# ------------------------------------------------------------------ the screen
def test_the_text_is_typed_and_the_answers_wait_for_it():
    hub = _hub()
    assert hub.vn_typed() == 0 and not hub.vn_ready()
    hub.vn_t = hub.VN_FADE + 1.0
    assert 0 < hub.vn_typed() < len(i18n.t("story_vn1_q")) and not hub.vn_ready()
    hub.nav_v(1)
    assert hub.vn_index == 0                      # nothing to choose yet
    _ready(hub)
    assert hub.vn_typed() >= len(i18n.t("story_vn1_q"))


def test_a_shows_the_whole_text_then_a_chooses():
    hub = _hub()
    hub.confirm()
    assert hub.vn_ready() and hub.screen == "vn" and not story_vn.answered(hub.state, SCENE)


def test_b_shows_the_whole_text_but_never_skips_the_answer():
    hub = _hub()
    assert hub.back() is True
    assert hub.vn_ready() and hub.screen == "vn"
    assert hub.back() is True
    assert hub.screen == "vn" and not story_vn.answered(hub.state, SCENE)


def test_up_and_down_move_between_the_four_answers_without_wrapping():
    hub = _hub()
    _ready(hub)
    hub.nav_v(-1)
    assert hub.vn_index == 0
    for want in (1, 2, 3, 3):
        hub.nav_v(1)
        assert hub.vn_index == want
    hub.nav_v(-1)
    assert hub.vn_index == 2


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_choosing_an_answer_keeps_it_and_leaves_for_the_map(index):
    hub = _hub()
    _ready(hub)
    for _ in range(index):
        hub.nav_v(1)
    hub.confirm()
    assert hub.screen == "hub" and hub.pane == "map" and hub.vn_id is None
    assert story_vn.pick(hub.state, SCENE) == index and story_vn.points(hub.state) == index + 1
    saved = ss.load_state(ss.story_path(1))
    assert story_vn.pick(saved, SCENE) == index                 # written to the save at once


def test_the_scene_watched_again_shows_the_answer_and_changes_nothing():
    hub = _hub()
    _ready(hub)
    hub.nav_v(1)
    hub.nav_v(1)
    hub.confirm()                                               # answer 3 (index 2)
    assert story_vn.points(hub.state) == 3
    hub.start_vn(SCENE, back_to="log")
    assert hub.vn_review and hub.vn_index == 2 and hub.screen == "vn"
    _ready(hub)
    hub.nav_v(1)
    assert hub.vn_index == 2                                    # no moving: the answer is given
    hub.nav_v(-1)
    assert hub.vn_index == 2
    hub.confirm()
    assert hub.screen == "hub" and hub.pane == "log"
    assert story_vn.pick(hub.state, SCENE) == 2 and story_vn.points(hub.state) == 3


def test_b_closes_a_scene_watched_again():
    hub = _hub()
    _ready(hub)
    hub.confirm()
    hub.start_vn(SCENE, back_to="log")
    assert hub.back() is True
    assert hub.screen == "hub" and hub.pane == "log"


def test_the_scene_is_watched_again_from_the_journal(french):
    hub = _hub()
    _ready(hub)
    hub.confirm()
    ss.mark_film_seen(hub.state, "vn_1")
    hub.pane = "log"
    entries = hub.replay_entries()
    idx = entries.index({"film": "vn_1"})
    hub.log_cursor = idx
    hub._hub_confirm()
    assert hub.screen == "vn" and hub.vn_review and hub.vn_return == "log"


def test_unknown_scene_is_refused():
    hub = _hub()
    hub.screen = "hub"
    assert hub.start_vn("nope") is False and hub.screen == "hub"


def test_the_scene_covers_the_screen_and_has_its_help_bar():
    hub = _hub()
    assert hub.covers_screen()
    assert hub.help_items() == ([("ok", "hint_next")], None)
    _ready(hub)
    assert hub.help_items() == ([("ud", "hint_choose"), ("ok", "hint_ok")], None)
    hub.confirm()
    hub.start_vn(SCENE)
    assert hub.help_items() == ([("ok", "hint_close")], None)


def test_the_film_of_the_bar_has_no_title_over_it():
    hub = _hub(concert=False)
    hub.film_id, hub.film_t, hub.screen = "vn_1", 1.0, "film"
    assert hub.help_items() == ([("back", "hint_skip")], None)
    hub.film_id = "lyra_1"
    hub.film_t = 9.0
    assert hub.help_items() == ([], None)


def test_no_title_is_drawn_over_the_film_of_the_bar_but_one_over_a_song():
    hub = _hub(concert=False)
    hub.film_id, hub.film_t, hub.screen = "vn_1", 1.0, "film"
    black = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    black.fill((0, 0, 0))
    font = pygame.font.Font(None, 40)
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    hub.draw(surf, font, font, font)
    assert pygame.image.tostring(surf, "RGB") == pygame.image.tostring(black, "RGB")
    hub.film_id = "lyra_1"
    hub.draw(surf, font, font, font)
    assert pygame.image.tostring(surf, "RGB") != pygame.image.tostring(black, "RGB")


def test_the_screen_draws_at_every_stage_in_both_languages():
    hub = _hub()
    for lang in ("fr", "en", "de"):
        i18n.set_lang(lang)
        hub.start_vn(SCENE)
        for t in (0.0, 0.5, 1.5, 3.0, 99.0):
            hub.vn_t = t
            _draw(hub)
    i18n.set_lang("fr")


def test_the_answers_and_the_lit_row_are_drawn_once_the_text_is_complete():
    hub = _hub()
    before = pygame.image.tostring(_draw(hub), "RGB")
    _ready(hub)
    ready = pygame.image.tostring(_draw(hub), "RGB")
    assert before != ready
    hub.nav_v(1)
    assert ready != pygame.image.tostring(_draw(hub), "RGB")        # the lit row moved


def test_the_screen_fades_in_from_black():
    hub = _hub()
    hub.vn_t = 0.0
    dark = _draw(hub)
    assert dark.get_at((900, 300))[:3] == (0, 0, 0)
    hub.vn_t = hub.VN_FADE + 1
    assert dark is not None and _draw(hub).get_at((900, 300))[:3] != (0, 0, 0)


def test_time_passes_on_the_scene():
    hub = _hub()
    hub.update(0.1)
    hub.update(0.1)
    assert abs(hub.vn_t - 0.2) < 1e-9
    hub.update(9.0)
    assert abs(hub.vn_t - 0.45) < 1e-9                              # (a long frame counts for 0.25 s at most)


# ------------------------------------------------------------------ the texts
def test_the_french_text_of_the_scene_is_the_one_asked_for(french):
    assert i18n.t("story_vn_lyra") == "LYRA VOSS"
    assert i18n.t("story_vn1_q") == (
        "Tu m’as sortie de ce vaisseau. Je ne sais toujours pas comment te remercier. "
        "Tu es venu juste pour vérifier que je tenais encore debout, ou tu veux vraiment boire un verre avec moi ?")
    assert [i18n.t(k) for k, _p in story_vn.scene(SCENE)["answers"]] == [
        "« C’était mon travail. Rien de plus. »", "« Un verre, pourquoi pas. »", "« Je voulais te revoir. »",
        "« Je voulais être sûr que tu allais bien. Et te revoir. »"]


def test_the_english_text_is_there_and_the_other_languages_show_it():
    keys = ["story_vn1_q", "story_vn_lyra", "story_film_vn1_t", "story_vn1_t"] + [k for k, _p in story_vn.scene(SCENE)["answers"]]
    for key in keys:
        assert i18n.T[key]["en"] and i18n.T[key]["fr"]
        for code in i18n.LANG_CODES:
            assert i18n.T[key].get(code)
    assert i18n.T["story_vn1_a3"]["en"] == "“I wanted to see you again.”"


def test_no_text_of_the_scene_shows_the_points():
    for key in ("story_vn1_q", "story_vn1_a1", "story_vn1_a2", "story_vn1_a3", "story_vn1_a4"):
        for code in ("fr", "en"):
            assert "→" not in i18n.T[key][code] and "pts" not in i18n.T[key][code].lower()


# ================================================================== scene 2: the hangar
SCENE2 = "vn_2"
EN2 = "story_vn2_q"


def _story_win(st, mission_id):
    """A story mission is won (the first time it is added to `cleared`)."""
    assert mission_id not in st["cleared"]
    st["cleared"].append(mission_id)


def _hub_after_scene1(wins_before=0):
    """A save where scene 1 was answered; `wins_before` story missions were already won when it was."""
    st = _state()
    for mid in ("phenix_1", "phenix_2", "phenix_3")[:wins_before]:
        _story_win(st, mid)
    story_vn.choose(st, SCENE, 1, ss.story_wins(st))
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.screen, hub.pane = "hub", "map"
    return hub


def test_scene_two_is_the_hangar_with_four_answers_worth_1_2_3_4():
    sc = story_vn.scene(SCENE2)
    assert sc["film"] is None and sc["after"] == SCENE and sc["wins"] == 1 and sc["panel"] == "right"
    assert sc["image"] == "vn_2_hangar" and sc["speaker"] == "story_vn_lyra" and sc["text"] == EN2
    assert sc["journal"] == "story_vn2_j" and sc["title"] == "story_vn2_t"
    assert [k for k, _p in sc["answers"]] == ["story_vn2_a1", "story_vn2_a2", "story_vn2_a3", "story_vn2_a4"]
    assert [pts for _k, pts in sc["answers"]] == [1, 2, 3, 4]


def test_the_picture_of_scene_two_is_in_the_game_folder():
    assert os.path.isfile(asset_path("story", "vn_2_hangar.jpg"))


def test_the_points_of_the_scenes_add_up():
    st = {}
    story_vn.choose(st, SCENE, 3)
    story_vn.choose(st, SCENE2, 1)
    assert story_vn.points(st) == 4 + 2
    st = {}
    story_vn.choose(st, SCENE, 0)
    story_vn.choose(st, SCENE2, 2)
    assert story_vn.points(st) == 1 + 3


def test_the_scenes_come_one_after_the_other():
    assert story_vn.next_scene({}) == SCENE
    st = {}
    story_vn.choose(st, SCENE2, 0)                       # (a scene two answered before one: the first is still to tell)
    assert story_vn.next_scene(st) == SCENE
    story_vn.choose(st, SCENE, 0)
    assert story_vn.next_scene(st) is None


def test_the_answer_remembers_how_many_story_missions_were_won():
    st = {}
    assert story_vn.choose(st, SCENE, 0, 5)
    assert story_vn.mark(st, SCENE) == 5 and story_vn.mark(st, SCENE2) is None
    assert story_vn.choose({}, SCENE, 0) and story_vn.mark({"vn": {"picks": {SCENE: 0}}}, SCENE) is None


@pytest.mark.parametrize("marks", [{SCENE: -1}, {SCENE: True}, {SCENE: "3"}, {SCENE: 2.5}, {SCENE2: 4}, {"nope": 1}, 7])
def test_a_damaged_mark_is_dropped(marks):
    assert story_vn.clean({"picks": {SCENE: 0}, "marks": marks}) == {"picks": {SCENE: 0}, "marks": {}}


def test_a_good_mark_is_kept():
    assert story_vn.clean({"picks": {SCENE: 0}, "marks": {SCENE: 3}})["marks"] == {SCENE: 3}


def test_a_save_without_marks_counts_from_now_on():
    st = {"vn": {"picks": {SCENE: 1}}}
    assert story_vn.ensure_marks(st, 4) is True
    assert story_vn.mark(st, SCENE) == 4
    assert story_vn.ensure_marks(st, 9) is False and story_vn.mark(st, SCENE) == 4
    assert story_vn.ensure_marks({}, 3) is False


def test_the_story_wins_count_series_and_belts_only():
    st = _state()
    st["cleared"] = []
    assert ss.story_wins(st) == 0
    for mid in ("ast_2", "phenix_1", "up_shield_1", "final_1"):
        st["cleared"].append(mid)
    assert ss.story_wins(st) == 4
    for mid in ("best_s2", "bonus_vip", "bonus_2d", "paint_1", "bonus_wreck_phenix", "bonus_singularity"):
        st["cleared"].append(mid)
    assert ss.story_wins(st) == 4                        # hunts, bonuses and paint do not count
    st["cleared"] += ["ast_2", "phenix_1", "unknown"]
    assert ss.story_wins(st) == 4                        # nor a mission twice, nor an unknown one
    assert ss.story_wins({}) == 0 and ss.story_wins(None) == 0


def test_scene_two_is_not_due_before_scene_one_is_answered():
    st = _state()
    _story_win(st, "phenix_1")
    assert ss.vn_due(st) == SCENE                        # (scene 1 first)
    st2 = _state(concert=False)
    _story_win(st2, "phenix_1")
    assert ss.vn_due(st2) is None


def test_scene_two_is_due_after_the_next_story_mission_won():
    st = _state()
    story_vn.choose(st, SCENE, 0, ss.story_wins(st))
    assert ss.vn_due(st) is None                         # nothing won since
    st["cleared"].append("best_s2")
    st["cleared"].append("bonus_vip")
    assert ss.vn_due(st) is None                         # a hunt and a bonus are not story missions
    st["cleared"].append("phenix_1")
    assert ss.vn_due(st) == SCENE2
    story_vn.choose(st, SCENE2, 0, ss.story_wins(st))
    assert ss.vn_due(st) is None


def test_a_belt_is_a_story_mission_for_the_scene():
    st = _state()
    story_vn.choose(st, SCENE, 0, ss.story_wins(st))
    st["cleared"].append("ast_2")
    assert ss.vn_due(st) == SCENE2


def test_missions_won_before_the_answer_do_not_count():
    st = _state()
    for mid in ("ast_2", "phenix_1"):
        st["cleared"].append(mid)
    story_vn.choose(st, SCENE, 0, ss.story_wins(st))
    assert ss.vn_due(st) is None
    st["cleared"].append("phenix_2")
    assert ss.vn_due(st) == SCENE2


def test_a_save_answered_before_the_marks_waits_for_the_next_mission():
    st = _state()
    st["vn"] = {"picks": {SCENE: 0}}
    wins = ss.story_wins(st)
    assert ss.vn_due(st) is None                         # no mark yet: never due by accident
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    assert hub.screen == "hub" and story_vn.mark(hub.state, SCENE) == wins
    assert story_vn.mark(ss.load_state(ss.story_path(1)), SCENE) == wins           # written to the save
    hub.update(1 / 60)
    assert hub.screen == "hub"                           # nothing won since
    hub.state["cleared"].append("phenix_1")
    hub.update(1 / 60)
    assert hub.screen == "vn" and hub.vn_id == SCENE2


def test_the_map_brings_scene_two_back_after_a_won_mission():
    hub = _hub_after_scene1()
    assert hub.screen == "hub"
    hub.update(1 / 60)
    assert hub.screen == "hub"                           # nothing won yet
    hub.state["cleared"].append("phenix_1")
    hub.update(1 / 60)
    assert hub.screen == "vn" and hub.vn_id == SCENE2 and hub.vn_return == "map" and not hub.vn_review


def test_a_hunt_won_does_not_bring_it():
    hub = _hub_after_scene1()
    hub.state["cleared"].append("best_s3")
    hub.update(1 / 60)
    assert hub.screen == "hub"


def test_the_scene_does_not_interrupt_the_paint_shop_nor_a_cheat():
    hub = _hub_after_scene1()
    hub.state["cleared"].append("phenix_1")
    hub.paint_mode = True
    hub.update(1 / 60)
    assert hub.screen == "hub"
    hub.paint_mode = False
    hub.cheat_unlock = True
    hub.update(1 / 60)
    assert hub.screen == "hub"
    hub.cheat_unlock = False
    hub.update(1 / 60)
    assert hub.screen == "vn"


def test_scene_two_is_told_on_the_map_not_over_another_screen():
    hub = _hub_after_scene1()
    hub.state["cleared"].append("phenix_1")
    for screen in ("slots", "intro", "film", "choice", "name"):
        hub.screen = screen
        hub._maybe_vn()
        assert hub.screen == screen


def test_choosing_in_scene_two_keeps_the_answer_and_counts_from_there():
    hub = _hub_after_scene1()
    hub.state["cleared"].append("phenix_1")
    hub.update(1 / 60)
    _ready(hub)
    hub.nav_v(1)
    hub.nav_v(1)
    hub.confirm()
    assert hub.screen == "hub" and story_vn.pick(hub.state, SCENE2) == 2
    assert story_vn.points(hub.state) == 2 + 3
    assert story_vn.mark(hub.state, SCENE2) == ss.story_wins(hub.state)
    saved = ss.load_state(ss.story_path(1))
    assert story_vn.pick(saved, SCENE2) == 2
    hub.update(1 / 60)
    assert hub.screen == "hub"                           # told once


def test_scene_two_is_in_the_journal_once_answered_and_watched_again_from_it(french):
    hub = _hub_after_scene1()
    assert {"vn": SCENE2} not in ss.journal_entries(hub.state)
    story_vn.choose(hub.state, SCENE2, 3, 1)
    entries = ss.journal_entries(hub.state)
    assert {"vn": SCENE2} in entries and {"vn": SCENE} not in entries      # (scene 1 is listed by its film)
    assert ss.log_text({"vn": SCENE2}, i18n.t) == "Revoir : Visual novel - Scène 2 : le hangar"
    hub.pane = "log"
    hub.log_cursor = hub.replay_entries().index({"vn": SCENE2})
    hub._hub_confirm()
    assert hub.screen == "vn" and hub.vn_id == SCENE2 and hub.vn_review and hub.vn_index == 3
    assert hub.vn_return == "log"
    _ready(hub)
    hub.confirm()
    assert hub.screen == "hub" and hub.pane == "log" and story_vn.pick(hub.state, SCENE2) == 3


def test_a_journal_line_that_replays_a_vn_scene_is_a_replay_line():
    from story import _is_replay
    assert _is_replay({"vn": SCENE2}) and not _is_replay({"vn": ""})


def test_scene_two_has_its_text_on_the_right_and_scene_one_on_the_left():
    hub = _hub_after_scene1()
    for sid, side in ((SCENE, "left"), (SCENE2, "right")):
        hub.start_vn(sid)
        hub.vn_t = hub.VN_FADE + 999.0
        surf = _draw(hub)
        # the panel edge colour is only where the panel is
        px = [x for x in range(0, BASE_WIDTH, 8) if surf.get_at((x, 300))[:3] == (70, 90, 130)]
        assert px, sid
        assert (px[0] < 400) == (side == "left"), sid


def test_the_french_text_of_scene_two_is_the_one_asked_for(french):
    assert i18n.t("story_vn2_q") == "Tu es rentré en un seul morceau. Bien. … Tu as eu peur, là-haut ?"
    assert [i18n.t(k) for k, _p in story_vn.scene(SCENE2)["answers"]] == [
        "« Non. C’est mon métier. »", "« Un peu. Comme toujours. »", "« Oui. Et je pensais à toi. »",
        "« Oui. J’avais surtout peur de ne pas te revoir. »"]
    assert i18n.t("story_vn2_t") == "Scène 2 : le hangar"


def test_the_english_text_of_scene_two_is_there():
    keys = ["story_vn2_q", "story_vn2_t", "story_vn2_j"] + [k for k, _p in story_vn.scene(SCENE2)["answers"]]
    for key in keys:
        assert i18n.T[key]["en"] and i18n.T[key]["fr"]
        for code in i18n.LANG_CODES:
            assert i18n.T[key].get(code)
    assert i18n.T["story_vn2_a3"]["en"] == "“Yes. And I was thinking of you.”"
