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
import story
from story import StoryHub

SCENE = "vn_1"
REAL_ORDER = story_vn.order
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


@pytest.fixture(autouse=True)
def _natural_order(monkeypatch):
    """The answers of scene 1 come in a random order: here in the order of the list, so that the tests can count on it
    (the random order has its own tests, with REAL_ORDER)."""
    monkeypatch.setattr(story_vn, "order", lambda scene_id, shuffled=True: list(range(len((story_vn.scene(scene_id) or {"answers": []})["answers"]))))


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
    """A through the pages of the text, until the last one is complete (the answers are there)."""
    for _ in range(20):
        hub.vn_t = hub.VN_FADE + 999.0
        if hub.vn_ready():
            return
        hub.confirm()
    raise AssertionError("the text never ends")


def _finish(hub):
    """A through the reaction of Lyra, until the scene is closed."""
    for _ in range(20):
        if hub.screen != "vn":
            return
        hub.vn_t = hub.VN_FADE + 999.0
        hub.confirm()
    raise AssertionError("the scene never ends")


def _answer(hub, index=0):
    """Choose the answer `index` (the list is in its natural order here) and watch the reaction to the end."""
    _ready(hub)
    hub.vn_index = index
    hub.confirm()
    _finish(hub)


def _draw(hub):
    font = pygame.font.Font(None, 28)
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    hub.draw(surf, font, font, font)
    return surf


# ------------------------------------------------------------------ the scene and its hidden points
def test_scene_one_is_the_bar_of_phobos_with_four_answers_worth_2_3_4_3():
    sc = story_vn.scene(SCENE)
    assert sc["image"] == "vn_1_bar" and sc["film"] == "vn_1" and sc["speaker"] == "story_vn_lyra"
    assert [a[1] for a in sc["answers"]] == [2, 3, 4, 3]
    assert [a[0] for a in sc["answers"]] == ["story_vn1_a1", "story_vn1_a2", "story_vn1_a3", "story_vn1_a4"]
    assert [a[2] for a in sc["answers"]] == ["story_vn1_r1", "story_vn1_r2", "story_vn1_r3", "story_vn1_r4"]
    assert sc["shuffle"] is True
    assert story_vn.VN_ORDER == [SCENE, "vn_2"]


@pytest.mark.parametrize("index,expected", [(0, 2), (1, 3), (2, 4), (3, 3)])
def test_each_answer_gives_its_own_points(index, expected):
    st = {}
    assert story_vn.points(st) == 0
    assert story_vn.choose(st, SCENE, index)
    assert story_vn.pick(st, SCENE) == index and story_vn.points(st) == expected


def test_an_answer_is_final():
    st = {}
    assert story_vn.choose(st, SCENE, 1)
    assert not story_vn.choose(st, SCENE, 2)
    assert story_vn.pick(st, SCENE) == 1 and story_vn.points(st) == 3


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
    assert story_vn.points({"vn": {"picks": {SCENE: 2}}}) == 4


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
    assert back["vn"] == {"picks": {SCENE: 2}, "marks": {SCENE: 0}} and story_vn.points(back) == 4


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
    first = story_vn.page_length(story_vn.pages(i18n.t("story_vn1_q"))[0])
    assert hub.vn_typed() == 0 and not hub.vn_ready() and not hub.vn_page_done()
    hub.vn_t = hub.VN_FADE + 1.0
    assert 0 < hub.vn_typed() < first and not hub.vn_page_done()
    hub.nav_v(1)
    assert hub.vn_index == 0                      # nothing to choose yet
    hub.vn_t = hub.VN_FADE + 999.0
    assert hub.vn_page_done() and not hub.vn_ready()          # (the first of three pages)
    _ready(hub)
    assert hub.vn_page == 2 and hub.vn_last_page()


def test_the_text_is_cut_in_three_pages_in_scene_one(french):
    hub = _hub()
    assert len(hub.vn_pages()) == 3 and hub.vn_page == 0
    assert [len(p) for p in hub.vn_pages()] == [3, 3, 1]


def test_a_shows_the_whole_page_then_the_next_page_then_the_answers():
    hub = _hub()
    hub.confirm()                                                # the page is shown at once
    assert hub.vn_page == 0 and hub.vn_page_done() and not hub.vn_ready()
    hub.confirm()                                                # the next page begins, typed from the start
    assert hub.vn_page == 1 and hub.vn_typed() == 0 and hub.vn_t == hub.VN_FADE
    hub.confirm()
    hub.confirm()
    assert hub.vn_page == 2 and hub.vn_typed() == 0
    hub.confirm()
    assert hub.vn_ready() and hub.screen == "vn" and not story_vn.answered(hub.state, SCENE)


def test_b_shows_the_text_page_after_page_but_never_skips_the_answer():
    hub = _hub()
    for _ in range(10):
        if hub.vn_ready():
            break
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
def test_choosing_an_answer_keeps_it_then_lyra_answers_and_the_map_comes_back(index):
    hub = _hub()
    _ready(hub)
    for _ in range(index):
        hub.nav_v(1)
    hub.confirm()
    assert hub.screen == "vn" and hub.vn_phase == "react"
    assert story_vn.pick(hub.state, SCENE) == index and story_vn.points(hub.state) == [2, 3, 4, 3][index]
    saved = ss.load_state(ss.story_path(1))
    assert story_vn.pick(saved, SCENE) == index                 # written to the save at once
    _finish(hub)
    assert hub.screen == "hub" and hub.pane == "map" and hub.vn_id is None


def test_lyra_answers_with_the_text_of_the_answer_given(french):
    for index in range(4):
        hub = _hub()
        _ready(hub)
        hub.vn_index = index
        hub.confirm()
        assert hub.vn_phase == "react" and hub.vn_page == 0 and hub.vn_typed() == 0
        assert hub.vn_pages() == story_vn.pages(i18n.t("story_vn1_r%d" % (index + 1)))
        assert hub.vn_pages()[0][0][0] is True                  # (the first line of each is narration)


def test_the_reaction_is_typed_then_a_shows_it_whole_then_closes():
    hub = _hub()
    _ready(hub)
    hub.confirm()
    hub.vn_t = hub.VN_FADE + 0.5
    assert 0 < hub.vn_typed() < story_vn.page_length(hub.vn_pages()[0]) and not hub.vn_page_done()
    hub.nav_v(1)
    assert hub.vn_phase == "react"
    hub.confirm()
    assert hub.vn_page_done() and hub.screen == "vn"
    for _ in range(5):
        if hub.screen != "vn":
            break
        hub.confirm()
    assert hub.screen == "hub" and hub.pane == "map"


def test_b_goes_through_the_reaction_too():
    hub = _hub()
    _ready(hub)
    hub.confirm()
    for _ in range(6):
        if hub.screen != "vn":
            break
        assert hub.back() is True
    assert hub.screen == "hub" and story_vn.answered(hub.state, SCENE)


def test_the_moving_cursor_does_nothing_during_the_reaction():
    hub = _hub()
    _ready(hub)
    hub.confirm()
    _ready(hub)
    before = hub.vn_index
    hub.nav_v(1)
    assert hub.vn_index == before


def test_the_scene_watched_again_shows_the_answer_then_the_reaction_and_changes_nothing():
    hub = _hub()
    _answer(hub, 2)
    assert story_vn.points(hub.state) == 4
    hub.start_vn(SCENE, back_to="log")
    assert hub.vn_review and hub.vn_index == 2 and hub.screen == "vn" and hub.vn_phase == "ask"
    _ready(hub)
    hub.nav_v(1)
    assert hub.vn_index == 2                                    # no moving: the answer is given
    hub.nav_v(-1)
    assert hub.vn_index == 2
    hub.confirm()
    assert hub.screen == "vn" and hub.vn_phase == "react"       # Lyra's words come again
    assert hub.vn_pages() == story_vn.pages(i18n.t("story_vn1_r3"))
    _finish(hub)
    assert hub.screen == "hub" and hub.pane == "log"
    assert story_vn.pick(hub.state, SCENE) == 2 and story_vn.points(hub.state) == 4


def test_b_closes_a_scene_watched_again():
    hub = _hub()
    _answer(hub)
    hub.start_vn(SCENE, back_to="log")
    assert hub.back() is True
    assert hub.screen == "hub" and hub.pane == "log"


def test_the_scene_is_watched_again_from_the_journal(french):
    hub = _hub()
    _answer(hub)
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
    hub.confirm()                                                # Lyra answers: typed, then complete
    assert hub.help_items() == ([("ok", "hint_next")], None)
    hub.vn_t = hub.VN_FADE + 999.0
    assert hub.vn_ready() and hub.help_items() == ([("ok", "hint_close")], None)
    _finish(hub)
    hub.start_vn(SCENE)                                          # watched again: the reaction follows, then it closes
    assert hub.help_items() == ([("ok", "hint_next")], None)
    _ready(hub)
    assert hub.help_items() == ([("ok", "hint_next")], None)
    hub.confirm()
    _ready(hub)
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
        "« Ah. Mon sauveur est vivant. C’est plutôt rassurant. »\n"
        "*Elle désigne la chaise en face d’elle.\n"
        "« Assieds-toi, si tu as le temps. Je t’offre un verre. Enfin… avec les restrictions actuelles, ce sera "
        "probablement un truc synthétique qui prétend être du whisky. »\n\n"
        "*Un bref sourire.\n"
        "« Je voulais te remercier. Pour de vrai, cette fois. Pas avec un communiqué de presse ou une photo "
        "officielle. »\n"
        "*Elle joue avec son verre.\n\n"
        "« Alors, dis-moi… tu savais qui j’étais, quand tu m’as sortie de là-bas ? »")
    assert [i18n.t(a[0]) for a in story_vn.scene(SCENE)["answers"]] == [
        "« Oui. Tu es Lyra Voss, la chanteuse. Mais j’avais des gens à sauver. Je n’allais pas te laisser mourir. »",
        "« Bien sûr que je te connaissais. Même dans une base militaire, il faudrait vivre dans un caisson pour "
        "ne jamais avoir entendu parler de toi. »",
        "« Je savais qui tu étais. Mais à ce moment-là, tu n’étais pas une star. Tu étais quelqu’un qui allait se "
        "faire tuer. »",
        "« Je ne savais pas qui tu étais. J’ai compris après. Tu m’aurais vu agir exactement de la même façon si "
        "tu avais été n’importe qui d’autre. »"]


def test_the_french_reactions_of_lyra_are_the_ones_asked_for(french):
    r = [i18n.t("story_vn1_r%d" % k) for k in (1, 2, 3, 4)]
    assert r[0].split("\n") == [
        "*Lyra paraît sincèrement surprise.",
        "« C’est tout ? Pas de demande d’autographe ? Pas de déclaration sur la façon dont ma musique a changé ta vie ? »",
        "*Elle rit doucement.",
        "« Je plaisante. Enfin, à moitié. C’est agréable, pour une fois, de ne pas avoir l’impression que quelqu’un "
        "attend quelque chose de moi. »"]
    assert r[1].split("\n")[0] == "*Elle relève le menton avec un air faussement majestueux."
    assert r[1].endswith("« Mais sérieusement… merci. Je suis contente que tu sois venu t’asseoir avec moi. »")
    assert r[2].split("\n")[:2] == ["*Lyra cesse de jouer avec son verre.", "« Quelqu’un. »"]
    assert r[2].endswith("« Je ne sais pas trop quoi te dire. Ce n’est pas habituel pour moi. »")
    assert "Tu m’aurais" not in r[3] and r[3].split("\n")[0] == "*Lyra semble réfléchir à ta réponse."
    assert r[3].endswith("*Elle lève son verre.\n« À cette rencontre improbable, alors. »")


def test_the_english_text_is_there_and_the_other_languages_show_it():
    keys = ["story_vn1_q", "story_vn_lyra", "story_film_vn1_t", "story_vn1_t"]
    keys += [k for a in story_vn.scene(SCENE)["answers"] for k in (a[0], a[2])]
    for key in keys:
        assert i18n.T[key]["en"] and i18n.T[key]["fr"]
        for code in i18n.LANG_CODES:
            assert i18n.T[key].get(code)
    assert i18n.T["story_vn1_a1"]["en"].startswith("“Yes. You’re Lyra Voss, the singer.")


def test_the_french_and_the_english_texts_have_the_same_shape():
    for key in ["story_vn1_q", "story_vn1_r1", "story_vn1_r2", "story_vn1_r3", "story_vn1_r4"]:
        fr, en = (story_vn.pages(i18n.T[key][code]) for code in ("fr", "en"))
        assert [[n for n, _w in page] for page in fr] == [[n for n, _w in page] for page in en], key


def test_no_text_of_the_scene_shows_the_points():
    for key in ("story_vn1_q", "story_vn1_a1", "story_vn1_a2", "story_vn1_a3", "story_vn1_a4",
                "story_vn1_r1", "story_vn1_r2", "story_vn1_r3", "story_vn1_r4"):
        for code in ("fr", "en"):
            assert "→" not in i18n.T[key][code] and "pts" not in i18n.T[key][code].lower()


def test_the_reaction_begins_without_a_new_fade_and_no_answers_are_drawn_over_it(monkeypatch):
    shown, colors = [], []
    real_wrap = story._wrap_nb
    real_text = story._text
    monkeypatch.setattr(story, "_wrap_nb", lambda font, text, width: shown.append(text) or real_wrap(font, text, width))
    monkeypatch.setattr(story, "_text", lambda surface, font, text, color, *a, **k: colors.append((text, color)) or real_text(surface, font, text, color, *a, **k))
    hub = _hub()
    _ready(hub)
    hub.confirm()
    assert hub.vn_phase == "react" and hub.vn_t == hub.VN_FADE
    assert _draw(hub).get_at((900, 300))[:3] != (0, 0, 0)            # (the picture stays: no black coming back)
    hub.vn_t = hub.VN_FADE + 999.0
    shown.clear()
    colors.clear()
    _draw(hub)
    assert hub.vn_ready() and not any(x[:3] in ("1. ", "2. ", "3. ", "4. ") for x in shown)
    lines = dict(colors)
    assert lines["Lyra paraît sincèrement surprise."] == story.StoryHub.VN_NARRATION      # the narration: its own color
    speech = [c for text, c in colors if text.startswith("« C’est tout")]
    assert speech and speech[0] != story.StoryHub.VN_NARRATION


def test_a_page_shown_at_once_is_complete_whatever_its_length(monkeypatch):
    hub = _hub()
    for length in range(1, 1500):
        monkeypatch.setattr(story_vn, "page_length", lambda page, n=length: n)
        hub.vn_t = 0.0
        hub.confirm()
        assert hub.vn_page_done(), length


def test_watched_again_in_a_scene_without_reaction_the_last_a_closes():
    hub = _hub_after_scene1()
    story_vn.choose(hub.state, SCENE2, 1, 1)
    hub.start_vn(SCENE2, back_to="log")
    assert hub.help_items() == ([("ok", "hint_next")], None)          # (still typing)
    _ready(hub)
    assert hub.help_items() == ([("ok", "hint_close")], None)         # (no reaction to come: it closes)
    hub.confirm()
    assert hub.screen == "hub" and hub.pane == "log"


# ------------------------------------------------------------------ the pages of a text, the reactions, the random order
def test_a_text_is_cut_in_pages_and_the_stars_mark_the_narration():
    text = "« A. »\n*She smiles.\n\n\n  « B   c. »  \n\n"
    assert story_vn.pages(text) == [[(False, "«\u00a0A.\u00a0»"), (True, "She smiles.")],
                                    [(False, "«\u00a0B c.\u00a0»")]]
    assert story_vn.pages("") == [] and story_vn.pages("\n \n") == []
    assert story_vn.pages("*") == []                                  # (a star alone is nothing)


def test_the_length_of_a_page_counts_each_paragraph_and_its_end():
    assert story_vn.page_length([(False, "abc"), (True, "de")]) == 4 + 3
    assert story_vn.page_length([]) == 0


def test_the_spaces_inside_the_french_quotes_do_not_break():
    nb = story_vn.NBSP
    assert story_vn.tidy("« a ? »") == "«" + nb + "a" + nb + "?" + nb + "»"
    assert story_vn.tidy("a !  b : c ; d") == "a" + nb + "! b" + nb + ": c" + nb + "; d"
    assert story_vn.tidy("plain text") == "plain text"


def test_a_wrapped_line_never_begins_with_a_closing_quote():
    font = pygame.font.Font(None, 28)
    text = story_vn.tidy("« " + "mot " * 12 + "dernier ? »")
    for width in range(150, 400, 7):
        lines = story._wrap_nb(font, text, width)
        assert lines and all(not line.startswith("»") and not line.startswith("?") for line in lines), width
        assert story_vn.NBSP not in "".join(lines)                                 # (drawn as plain spaces)
        assert " ".join(lines).split() == text.replace(story_vn.NBSP, " ").split()


def test_every_answer_of_scene_one_has_a_reaction_and_scene_two_has_none():
    for k, ans in enumerate(story_vn.scene(SCENE)["answers"]):
        assert story_vn.reaction(SCENE, k) == ans[2] and story_vn.pages(i18n.T[ans[2]]["en"])
    assert [story_vn.reaction(SCENE2, k) for k in range(4)] == [None] * 4
    for scene, index in (("nope", 0), (SCENE, -1), (SCENE, 4), (SCENE, True), (SCENE, None), (SCENE, "1")):
        assert story_vn.reaction(scene, index) is None


def test_the_answers_of_scene_one_come_in_a_random_order():
    seen = set()
    for _ in range(200):
        order = REAL_ORDER(SCENE)
        assert sorted(order) == [0, 1, 2, 3]
        seen.add(tuple(order))
    assert len(seen) > 12                                             # (24 are possible)
    assert REAL_ORDER(SCENE, shuffled=False) == [0, 1, 2, 3]          # (watched again: the list as it is)
    assert all(REAL_ORDER(SCENE2) == [0, 1, 2, 3] for _ in range(20))   # (scene two keeps its order)
    assert REAL_ORDER("nope") == []


def test_the_screen_asks_for_a_new_random_order_each_time(monkeypatch):
    monkeypatch.setattr(story_vn, "order", REAL_ORDER)
    hub = _hub()
    orders = set()
    for _ in range(40):
        hub.start_vn(SCENE)
        assert sorted(hub.vn_order) == [0, 1, 2, 3] and hub.vn_index == hub.vn_order[0]
        orders.add(tuple(hub.vn_order))
    assert len(orders) > 3


def test_the_cursor_follows_the_order_shown_and_the_pick_is_the_answer_of_the_list(monkeypatch):
    monkeypatch.setattr(story_vn, "order", lambda scene_id, shuffled=True: [2, 0, 3, 1])
    hub = _hub()
    assert hub.vn_order == [2, 0, 3, 1] and hub.vn_index == 2
    _ready(hub)
    hub.nav_v(-1)
    assert hub.vn_index == 2                                          # the top of the list
    for want in (0, 3, 1, 1):
        hub.nav_v(1)
        assert hub.vn_index == want
    hub.nav_v(-1)
    assert hub.vn_index == 3
    hub.confirm()
    assert story_vn.pick(hub.state, SCENE) == 3 and story_vn.points(hub.state) == 3       # (the answer 4 of the list)
    _finish(hub)


def test_the_first_answer_shown_is_the_one_under_the_cursor(monkeypatch):
    monkeypatch.setattr(story_vn, "order", lambda scene_id, shuffled=True: [1, 3, 2, 0])
    hub = _hub()
    _ready(hub)
    hub.confirm()                                                     # A at once: the answer on top
    assert story_vn.pick(hub.state, SCENE) == 1
    _finish(hub)


def test_watched_again_the_answers_are_in_the_order_of_the_list(monkeypatch):
    monkeypatch.setattr(story_vn, "order", REAL_ORDER)
    hub = _hub()
    hub.start_vn(SCENE)
    hub.vn_index = hub.vn_order[0]
    _ready(hub)
    given = hub.vn_index
    hub.confirm()
    _finish(hub)
    for _ in range(10):
        hub.start_vn(SCENE)
        assert hub.vn_review and hub.vn_order == [0, 1, 2, 3] and hub.vn_index == given


def test_the_numbers_of_the_answers_are_the_places_on_screen(monkeypatch, french):
    monkeypatch.setattr(story_vn, "order", lambda scene_id, shuffled=True: [3, 2, 1, 0])
    shown = []
    real = story._wrap_nb
    monkeypatch.setattr(story, "_wrap_nb", lambda font, text, width: shown.append(text) or real(font, text, width))
    hub = _hub()
    _ready(hub)
    _draw(hub)
    texts = [x for x in shown if x[:2] in ("1.", "2.", "3.", "4.")]
    assert [x[:2] for x in texts[:4]] == ["1.", "2.", "3.", "4."]
    assert texts[0].split(". ", 1)[1] == story_vn.tidy(i18n.t("story_vn1_a4"))
    assert texts[3].split(". ", 1)[1] == story_vn.tidy(i18n.t("story_vn1_a1"))


def _draw_real(hub):
    """Drawn with the fonts of the game (the test font is smaller: the long answers would fit in the usual panel)."""
    import fonts
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    hub.draw(surf, fonts.body(28), fonts.title(32), fonts.body(28), body=fonts.body(28))
    return surf


def _panel_span(surf, y):
    """The first and the last column where the edge of the panel is drawn on this row."""
    xs = [x for x in range(BASE_WIDTH) if surf.get_at((x, y))[:3] == (70, 90, 130)]
    return (xs[0], xs[-1]) if xs else None


def test_the_page_of_the_answers_is_wide_and_the_text_pages_are_not():
    hub = _hub()
    hub.vn_t = hub.VN_FADE + 999.0
    first = _panel_span(_draw_real(hub), 120)
    assert first is not None and first[1] - first[0] < 720             # (the usual panel: 700 wide)
    _ready(hub)
    last = _panel_span(_draw_real(hub), 300)
    assert last is not None and last[1] - last[0] > 800                # (long answers: wider, and higher)


def test_the_panel_of_every_page_stays_on_the_screen():
    for lang in ("fr", "en"):
        i18n.set_lang(lang)
        for index in range(4):
            hub = _hub()
            for phase in ("ask", "react"):
                if phase == "react":
                    _ready(hub)
                    hub.vn_index = index
                    hub.confirm()
                for _ in range(4):
                    hub.vn_t = hub.VN_FADE + 999.0
                    surf = _draw_real(hub)
                    assert surf.get_at((BASE_WIDTH // 2, BASE_HEIGHT - 2))[:3] != (70, 90, 130)
                    assert surf.get_at((BASE_WIDTH // 2, BASE_HEIGHT - 20))[:3] != (70, 90, 130)
                    if hub.vn_ready():
                        break
                    hub.confirm()
    i18n.set_lang("fr")


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
    assert [a[0] for a in sc["answers"]] == ["story_vn2_a1", "story_vn2_a2", "story_vn2_a3", "story_vn2_a4"]
    assert [a[1] for a in sc["answers"]] == [1, 2, 3, 4]
    assert not sc.get("shuffle") and all(len(a) == 2 for a in sc["answers"])


def test_the_picture_of_scene_two_is_in_the_game_folder():
    assert os.path.isfile(asset_path("story", "vn_2_hangar.jpg"))


def test_the_points_of_the_scenes_add_up():
    st = {}
    story_vn.choose(st, SCENE, 2)
    story_vn.choose(st, SCENE2, 1)
    assert story_vn.points(st) == 4 + 2
    st = {}
    story_vn.choose(st, SCENE, 0)
    story_vn.choose(st, SCENE2, 2)
    assert story_vn.points(st) == 2 + 3


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
    assert story_vn.points(hub.state) == 3 + 3                    # (scene 1: answer 2 of the list, 3 points)
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
    assert [i18n.t(a[0]) for a in story_vn.scene(SCENE2)["answers"]] == [
        "« Non. C’est mon métier. »", "« Un peu. Comme toujours. »", "« Oui. Et je pensais à toi. »",
        "« Oui. J’avais surtout peur de ne pas te revoir. »"]
    assert i18n.t("story_vn2_t") == "Scène 2 : le hangar"


def test_the_english_text_of_scene_two_is_there():
    keys = ["story_vn2_q", "story_vn2_t", "story_vn2_j"] + [a[0] for a in story_vn.scene(SCENE2)["answers"]]
    for key in keys:
        assert i18n.T[key]["en"] and i18n.T[key]["fr"]
        for code in i18n.LANG_CODES:
            assert i18n.T[key].get(code)
    assert i18n.T["story_vn2_a3"]["en"] == "“Yes. And I was thinking of you.”"


# ================================================================== the code VNOV (typed on the HIGH SCORES screen)
import menu_actions                                      # noqa: E402
import main_menu                                         # noqa: E402
from test_smoke import run                               # noqa: E402,F401  (fixture: a game)


def _type_code(g, text):
    for ch in text:
        g._feed_cheat(ch)


def _highscores(run):
    g = run.game
    g.started, g.game_over, g.used_cheat = False, False, False
    g.cheat_buffer, g.cheat_vn = "", False
    g.menu_screen = "highscores"
    return g


def test_vnov_turns_the_cheat_on_and_off(run, french):
    g = _highscores(run)
    _type_code(g, "VNOV")
    assert g.cheat_vn is True and g.cheat_buffer == ""
    assert g.cheat_msg == "VISUAL NOVEL : TOUTES LES SCÈNES" and g.cheat_kind == "vn" and g.cheat_msg_timer > 0
    assert g.used_cheat is False                                      # (the arcade high scores are not concerned)
    _type_code(g, "VNOV")
    assert g.cheat_vn is False and g.cheat_msg == "VISUAL NOVEL : NORMAL"


def test_vnov_is_typed_among_other_letters_and_leaves_the_other_codes_alone(run):
    g = _highscores(run)
    _type_code(g, "XXVNOV")
    assert g.cheat_vn is True
    g.player.infinite_lives = False
    _type_code(g, "LIVE")
    assert g.cheat_live and g.cheat_vn
    _type_code(g, "VNO")
    assert g.cheat_vn is True                                         # (an unfinished code does nothing)


def test_the_keys_of_the_high_score_screen_reach_vnov(run):
    g = _highscores(run)
    g.input_grace = 0.0
    for ch in "vnov":
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=ord(ch), unicode=ch, mod=0, scancode=0))
        run.frames(1)
    assert g.cheat_vn is True


def test_the_banner_of_the_code_has_a_style():
    from announce import KIND_STYLE
    assert KIND_STYLE["vn"] == ("special", "standard")


def test_vnov_reaches_the_adventure_already_open_and_the_one_opened_after(run):
    g = _highscores(run)
    from story import StoryHub
    g.story = StoryHub()
    _type_code(g, "VNOV")
    assert g.story.cheat_vn is True
    _type_code(g, "VNOV")
    assert g.story.cheat_vn is False
    _type_code(g, "VNOV")
    g.story = None
    g.menu_screen, g.menu_index = "main", main_menu.MAIN.index("story")
    menu_actions.menu_confirm(g)                                      # the Adventure is created, with the cheat
    assert g.story is not None and g.story.cheat_vn is True and g.menu_screen == "story_hub"
    g.cheat_vn = False
    g.menu_screen, g.menu_index = "main", main_menu.MAIN.index("story")
    menu_actions.menu_confirm(g)
    assert g.story.cheat_vn is False


def test_the_cheat_is_off_by_default_and_is_a_cheat_for_the_saves():
    hub = _hub()
    assert hub.cheat_vn is False and not hub.cheating
    hub.cheat_vn = True
    assert hub.cheating


def test_the_journal_lists_every_scene_under_the_cheat_even_with_nothing_seen():
    st = _state(concert=False)
    plain = ss.journal_entries(st)
    assert {"film": "vn_1"} not in plain and {"vn": SCENE2} not in plain
    entries = ss.journal_entries(st, cheat_vn=True)
    assert {"film": "vn_1"} in entries and {"vn": SCENE2} in entries
    assert entries.index({"film": "vn_1"}) < entries.index({"vn": SCENE2})
    assert entries.count({"film": "vn_1"}) == 1 and entries.count({"vn": SCENE2}) == 1
    assert plain == [e for e in entries if e not in ({"film": "vn_1"}, {"vn": SCENE2})]       # (nothing else changes)


def test_the_journal_does_not_list_a_scene_twice_when_it_is_already_there():
    st = _state()
    ss.mark_film_seen(st, "vn_1")
    story_vn.choose(st, SCENE2, 0, 0)
    entries = ss.journal_entries(st, cheat_vn=True)
    assert entries == ss.journal_entries(st)


def test_the_scenes_of_the_cheat_are_replay_lines_of_the_journal():
    hub = _hub(concert=False)
    hub.cheat_vn = True
    entries = hub.replay_entries()
    assert {"film": "vn_1"} in entries and {"vn": SCENE2} in entries
    assert {"vn": SCENE2} not in hub.story_entries()


def test_a_scene_that_was_not_unlocked_is_told_from_the_journal_under_the_cheat():
    hub = _hub(concert=False)
    hub.cheat_vn = True
    hub.pane = "log"
    hub.log_cursor = hub.replay_entries().index({"vn": SCENE2})
    hub._hub_confirm()
    assert hub.screen == "vn" and hub.vn_id == SCENE2 and hub.vn_return == "log" and not hub.vn_review
    assert hub.vn_pick is None


def test_the_film_of_scene_one_leads_to_the_scene_under_the_cheat():
    hub = _hub(concert=False)
    hub.cheat_vn = True
    hub.pane = "log"
    hub.log_cursor = hub.replay_entries().index({"film": "vn_1"})
    hub._hub_confirm()                                             # (no film file here: the scene comes at once)
    assert hub.screen == "vn" and hub.vn_id == SCENE and not hub.vn_review


def test_under_the_cheat_the_answer_is_not_kept_and_nothing_is_saved():
    hub = _hub(concert=False)
    before = open(ss.story_path(1), "rb").read()
    hub.cheat_vn = True
    hub.start_vn(SCENE, back_to="log")
    _ready(hub)
    hub.vn_index = 2
    hub.confirm()
    assert hub.vn_phase == "react" and hub.vn_pick == 2
    assert hub.vn_pages() == story_vn.pages(i18n.t("story_vn1_r3"))          # (Lyra answers this answer)
    _finish(hub)
    assert hub.screen == "hub" and hub.pane == "log"
    assert not story_vn.answered(hub.state, SCENE) and story_vn.points(hub.state) == 0
    assert open(ss.story_path(1), "rb").read() == before


def test_under_the_cheat_a_scene_already_answered_is_told_afresh_and_can_be_answered_again():
    hub = _hub()
    _answer(hub, 1)
    assert story_vn.pick(hub.state, SCENE) == 1
    hub.cheat_vn = True
    hub.start_vn(SCENE, back_to="log")
    assert not hub.vn_review and hub.vn_pick is None
    _ready(hub)
    hub.vn_index = 3
    hub.confirm()
    _finish(hub)
    assert story_vn.pick(hub.state, SCENE) == 1                         # (the real answer is untouched)


def test_under_the_cheat_the_answers_of_scene_one_still_come_in_a_random_order(monkeypatch):
    monkeypatch.setattr(story_vn, "order", REAL_ORDER)
    hub = _hub()
    hub.cheat_vn = True
    orders = set()
    for _ in range(40):
        hub.start_vn(SCENE)
        orders.add(tuple(hub.vn_order))
    assert len(orders) > 3


def test_the_scenes_do_not_come_by_themselves_under_the_cheat():
    hub = _hub(concert=False)
    hub.cheat_vn = True
    for fid in ("lyra_1", "lyra_2", "lyra_3"):
        ss.mark_film_seen(hub.state, fid)
    hub.update(1 / 60)
    assert hub.screen == "hub"


def test_the_cheat_stays_when_a_slot_is_opened_again_and_shows_the_banner():
    hub = _hub(concert=False)
    hub.cheat_vn = True
    hub.open_slot(1)
    assert hub.cheat_vn is True and hub.cheating
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    font = pygame.font.Font(None, 28)
    hub.screen, hub.pane = "hub", "map"
    plain = _draw_hub_pixels(hub, surf, font, cheat=False)
    cheated = _draw_hub_pixels(hub, surf, font, cheat=True)
    assert plain != cheated                                              # (the "CHEAT - NOT SAVED" banner)


def _draw_hub_pixels(hub, surf, font, cheat):
    hub.cheat_vn = cheat
    hub.draw(surf, font, font, font)
    return pygame.image.tostring(surf, "RGB")
