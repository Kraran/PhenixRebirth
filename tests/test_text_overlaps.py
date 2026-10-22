"""Texts that used to touch: the score under the plate of the "new record" screen, the subtitle under the help's title."""
import pygame
import pytest

import draw_frame
import help_screen
import hint_bar
import i18n
from i18n import LANG_CODES, set_lang
from test_smoke import run  # noqa: F401  (fixture)


class RecSurface(pygame.Surface):
    """A surface that remembers what was blitted on it, and where."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.blits = []

    def blit(self, source, dest, *a, **k):
        pos = dest if isinstance(dest, tuple) else dest.topleft
        self.blits.append((source, pos))
        return super().blit(source, dest, *a, **k)


@pytest.fixture(autouse=True)
def _french_again():
    yield
    set_lang("fr")


def _visible(source, pos):
    """Where the pixels that show are (the picture's margins left out)."""
    r = source.get_bounding_rect(min_alpha=40)
    return pygame.Rect(pos[0] + r.x, pos[1] + r.y, r.w, r.h)


def _spy(g):
    labels = {}
    real = g._txt

    def spy(font, text, color, *a, **k):
        surf = real(font, text, color, *a, **k)
        labels[id(surf)] = text
        return surf

    g._txt = spy
    return labels, real


@pytest.mark.parametrize("lang", LANG_CODES)
@pytest.mark.parametrize("two_players", [False, True])
def test_the_score_of_a_new_record_clears_the_plate(run, lang, two_players):
    g = run.game
    set_lang(lang)
    g.hs_name = list("AAA")
    g.hs_char_index = 0
    g.score = 12345
    if two_players:
        g.hotseat = True
        g.hs_slot_label = "1"
    g.game_surface = RecSurface((1280, 720))
    labels, real = _spy(g)
    try:
        draw_frame.draw_hs_enter(g)
    finally:
        g._txt = real
    score_txt = "%s : %s" % (i18n.t("score_label"), g.format_score(12345))
    plate = [(s, p) for s, p in g.game_surface.blits if id(s) not in labels and s.get_height() > 80 and p[1] < 260]
    score = [(s, p) for s, p in g.game_surface.blits if labels.get(id(s)) == score_txt]
    hint = [(s, p) for s, p in g.game_surface.blits if labels.get(id(s)) == i18n.t("enter_initials_hint")]
    letters = [(s, p) for s, p in g.game_surface.blits if labels.get(id(s)) in ("A",)]
    assert len(plate) == 1 and len(score) == 1 and len(hint) == 1 and len(letters) == 3
    plate_rect = pygame.Rect(plate[0][1], plate[0][0].get_size())
    score_rect = _visible(*score[0])
    hint_rect = _visible(*hint[0])
    assert score_rect.top >= plate_rect.bottom + 6, (lang, plate_rect, score_rect)
    assert hint_rect.top >= score_rect.bottom + 6, (lang, score_rect, hint_rect)
    letters_rect = _visible(*letters[0])
    assert letters_rect.top >= hint_rect.bottom + 6, (lang, hint_rect, letters_rect)
    assert letters_rect.bottom + 30 <= hint_bar.BAND_Y, (lang, letters_rect)


@pytest.mark.parametrize("lang", LANG_CODES)
@pytest.mark.parametrize("page", [0, 1])
def test_the_help_subtitle_clears_the_title_and_the_content(run, lang, page):
    g = run.game
    set_lang(lang)
    surface = RecSurface((1280, 720))
    labels, real = _spy(g)
    try:
        help_screen.draw_help_page(g, surface, page, 0)
    finally:
        g._txt = real
    title = [(s, p) for s, p in surface.blits if labels.get(id(s)) == "PHENIX REBIRTH"]
    sub = [(s, p) for s, p in surface.blits if labels.get(id(s)) == i18n.t("subtitle")]
    assert len(title) == 1 and len(sub) == 1
    title_rect, sub_rect = _visible(*title[0]), _visible(*sub[0])
    assert sub_rect.top >= title_rect.bottom + 6, (lang, title_rect, sub_rect)
    below = [_visible(s, p) for s, p in surface.blits
             if labels.get(id(s)) and p[1] > sub[0][1][1] + 20 and id(s) != id(sub[0][0])]
    assert below and all(r.top >= sub_rect.bottom + 4 for r in below), (lang, sub_rect, min(r.top for r in below))


def test_the_title_and_subtitle_positions_are_the_ones_of_the_constants(run):
    assert help_screen.HELP_TITLE_Y < help_screen.HELP_SUB_Y
