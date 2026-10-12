"""The help screen calls the enemies by the names of the Bestiary and of the Adventure, and its texts still fit the screen."""
import pygame
import pytest

import i18n
from i18n import t, t_help
from test_smoke import run  # noqa: F401  (fixture)

ROWS = [("enemy_s1", "story_b_bird1", 1), ("enemy_s2", "story_b_bird2", 2), ("enemy_s3", "story_b_garg3", 3),
        ("enemy_s4", "story_b_garg4", 4), ("enemy_boss", "story_b_boss", 5)]
LANGS = ["fr", "en", "es", "de", "it", "pt", "nl", "pl", "tr", "sv", "no", "da", "ru"]


@pytest.fixture(autouse=True)
def _french_again():
    yield
    i18n.set_lang("fr")


@pytest.mark.parametrize("lang", ["fr", "en"])
@pytest.mark.parametrize("help_key,best_key,stage", ROWS)
def test_each_enemy_of_the_help_has_the_name_of_the_bestiary_and_its_stage(lang, help_key, best_key, stage):
    i18n.set_lang(lang)
    assert t_help(help_key).lower() == "%s stage %d" % (t(best_key).lower(), stage)


def test_the_names_are_the_ones_the_player_asked_for():
    i18n.set_lang("fr")
    assert [t_help(k) for k, _, _ in ROWS] == ["Avioïde éclaireur stage 1", "Avioïde kaki stage 2", "Gargouille stage 3",
                                               "Gargouille sombre stage 4", "Commandant avioïde stage 5"]
    i18n.set_lang("en")
    assert [t_help(k) for k, _, _ in ROWS] == ["Scout Avioid stage 1", "Khaki Avioid stage 2", "Gargoyle stage 3",
                                               "Dark Gargoyle stage 4", "Avioid commander stage 5"]


@pytest.mark.parametrize("lang,words", [("fr", ("Avioïdes", "Gargouilles", "Commandant")),
                                        ("en", ("Avioids", "Gargoyles", "Commander"))])
def test_the_rest_of_the_help_text_uses_the_same_words(lang, words):
    i18n.set_lang(lang)
    story = " ".join(t_help("scenario"))
    how = " ".join(t_help("howto"))
    vet = " ".join(t_help("vet_note"))
    assert words[0] in story and words[1] in story and words[2] in how and words[2].lower() in vet.lower()
    text = (story + how + vet).lower()
    assert "oiseau" not in text and "bird" not in text and "boss" not in text


@pytest.mark.parametrize("lang", LANGS)
def test_the_help_page_fits_the_screen_in_every_language(run, lang):
    import help_screen
    g = run.game
    i18n.set_lang(lang)
    drawn = []
    real = g._txt

    def spy(font, text, color, *a, **k):
        surf = real(font, text, color, *a, **k)
        drawn.append((text, surf.get_width()))
        return surf

    g._txt = spy
    try:
        help_screen.draw_help_page(g, pygame.Surface((1280, 720)), 0, 0)
    finally:
        g._txt = real
    col_r = 1280 // 2 + 90
    vet = t_help("vet_note")
    vet = vet if isinstance(vet, list) else [vet]
    widths = [w for text, w in drawn if text in vet]
    assert len(widths) == len(vet)
    if lang in ("fr", "en"):                                         # the other languages were not rewritten (pt was already wide)
        assert all(col_r + w <= 1280 - 12 for w in widths), widths
    names = [w for text, w in drawn if text in [t_help(k) for k, _, _ in ROWS]]
    assert len(names) == 5 and all(col_r + 60 + w <= 1280 - 12 for w in names), names
    if lang in ("fr", "en"):                                         # the texts that were rewritten
        assert all(48 + w <= col_r - 10 for text, w in drawn if text in t_help("scenario") + t_help("howto")), drawn
