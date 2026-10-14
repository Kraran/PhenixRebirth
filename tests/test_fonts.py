"""The fonts shipped with the game (src/fonts.py, assets/fonts): Audiowide for the titles, Play for the rest, DejaVu
for what they lack."""
import os

import pygame
import pytest

import fonts
from test_smoke import run  # noqa: F401  (fixture)
import i18n
from settings import asset_path


@pytest.fixture(autouse=True)
def _font_init():
    if not pygame.font.get_init():
        pygame.font.init()
    yield


def _all_texts():
    for table in (i18n.T,):
        for entry in table.values():
            if isinstance(entry, dict):
                for s in entry.values():
                    if isinstance(s, str):
                        yield s


def test_the_files_and_their_licences_are_shipped():
    for name in (fonts.TITLE_FILE, fonts.BOLD_FILE, fonts.REGULAR_FILE, fonts.SPARE_FILE):
        assert os.path.isfile(asset_path("fonts", name)), name
    for lic in ("Audiowide-OFL.txt", "Play-OFL.txt", "DejaVu-LICENSE.txt"):
        assert os.path.getsize(asset_path("fonts", lic)) > 1000, lic


def test_the_cmap_reader_knows_what_each_font_draws():
    play = fonts.codepoints(asset_path("fonts", fonts.BOLD_FILE))
    title = fonts.codepoints(asset_path("fonts", fonts.TITLE_FILE))
    spare = fonts.codepoints(asset_path("fonts", fonts.SPARE_FILE))
    assert {ord(c) for c in "Aé ŚşĞıЖжё‹›…"} <= play
    assert {ord(c) for c in "AéŚşĞıÇ"} <= title
    assert ord("Ж") not in title and ord("←") not in title and ord("←") not in play
    assert {ord(c) for c in "←↑→↓↔∞≈"} <= spare


def test_every_character_of_every_language_can_be_drawn():
    play = fonts.codepoints(asset_path("fonts", fonts.BOLD_FILE))
    spare = fonts.codepoints(asset_path("fonts", fonts.SPARE_FILE))
    missing = {ch for s in _all_texts() for ch in s if ch not in "\n\r\t" and ord(ch) not in play | spare}
    assert not missing, sorted(missing)


@pytest.mark.parametrize("size", (16, 20, 22, 28, 32, 64))
def test_capitals_as_tall_as_the_old_font(size):
    """The layouts were made for the old font: the new ones keep its capital height (within a pixel or two)."""
    old = fonts.get("spare", size).metrics("H")[0][3]
    for f in (fonts.title(size), fonts.text(size), fonts.body(size)):
        assert abs(f.metrics("H")[0][3] - old) <= max(1, size // 20), (size, f)


def test_a_title_in_cyrillic_is_written_whole_in_play():
    title, bold = fonts.title(32), fonts.text(32)
    word = "ДОСТИЖЕНИЯ"
    assert title.size(word)[0] == bold.size(word)[0]
    img = title.render(word, True, (255, 255, 255))
    assert img.get_height() == title.get_height()
    assert img.get_bounding_rect(min_alpha=1).w > 100            # drawn, not empty boxes
    # a Latin title stays in Audiowide (wider than Play)
    assert title.size("ACHIEVEMENTS")[0] > bold.size("ACHIEVEMENTS")[0]


def test_a_missing_symbol_comes_from_dejavu_the_rest_stays():
    f, spare = fonts.text(20), fonts.get("spare", 20)
    arrows = "↑↓"
    assert f.size(arrows)[0] == spare.size(arrows)[0]
    line = "Naviguer ↑↓"
    assert f.size(line)[0] == fonts.text(20).size("Naviguer ")[0] + spare.size(arrows)[0]
    img = f.render(line, True, (255, 255, 255))
    assert img.get_width() == f.size(line)[0] and img.get_height() == f.get_height()
    # the arrows are real arrows: the same pixels as DejaVu's
    alone = f.render(arrows, True, (255, 255, 255))
    assert alone.get_bounding_rect(min_alpha=1).w == spare.render(arrows, True, (255, 255, 255)).get_bounding_rect(
        min_alpha=1).w


def test_italic_reaches_the_spare_font():
    f = fonts.text(28)
    f.set_italic(True)
    try:
        f.render("A ←", True, (255, 255, 255))
        assert fonts.get("spare", 28).get_italic()
    finally:
        f.set_italic(False)
        f.render("A ←", True, (255, 255, 255))


def test_a_broken_file_falls_back_to_the_system_fonts(monkeypatch):
    monkeypatch.setattr(fonts, "_fonts", {})
    monkeypatch.setattr(fonts, "TITLE_FILE", "missing.ttf")
    f = fonts.title(32)
    assert isinstance(f, pygame.font.Font) and not isinstance(f, fonts.GameFont)
    assert f.render("OPTIONS", True, (255, 255, 255)).get_width() > 0


def test_the_game_uses_the_shipped_fonts(run):
    g = run.game
    for attr in ("font", "menu_font", "big_font", "medium_font", "body_font", "read_font", "help_small"):
        assert isinstance(getattr(g, attr), fonts.GameFont), attr
    assert g.medium_font is fonts.title(32) and g.font is fonts.text(28) and g.body_font is fonts.body(22)
    import hint_bar
    assert hint_bar._font(16) is fonts.text(16)


def test_story_reads_in_the_regular_font(run):
    """The Adventure's story and its descriptions are drawn with the reading font when the game gives one."""
    from story import StoryHub
    g = run.game
    hub = StoryHub()
    surf = pygame.Surface((1280, 720))
    hub.draw(surf, g.font, g.medium_font, g.font, body=g.read_font)
    assert hub._body is g.read_font
    hub.draw(surf, g.font, g.medium_font, g.font)
    assert hub._body is g.font


def test_the_cmap_reader_agrees_with_fonttools():
    ttlib = pytest.importorskip("fontTools.ttLib")
    for name in (fonts.TITLE_FILE, fonts.BOLD_FILE, fonts.REGULAR_FILE, fonts.SPARE_FILE):
        path = asset_path("fonts", name)
        assert fonts.codepoints(path) == set(ttlib.TTFont(path).getBestCmap()), name
