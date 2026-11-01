"""The help screen tells the keys and the buttons the player really set, not the default ones (src/bindings.help_values)."""
import re

import pygame
import pytest

import bindings
import help_screen
import i18n
from bindings import KB2
from i18n import LANG_CODES, set_lang, t, t_list
from test_smoke import run  # noqa: F401  (fixture)

SECTIONS = ("controls", "phenix", "shield")
PLACEHOLDERS = {"kb_move", "kb_fire", "kb_phenix", "pad_fire", "pad_pause", "pad_phenix"}


@pytest.fixture(autouse=True)
def _defaults_and_french(tmp_path, monkeypatch):
    import user_settings
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    bindings.load(None)
    set_lang("fr")
    yield
    bindings.load(None)
    set_lang("fr")


def test_the_default_help_says_the_default_keys_and_buttons():
    assert help_screen.help_lines("controls") == ["Clavier : ← → ↑ ↓ + Espace / Ctrl droit",
                                                  "Manette : stick + A  |  Start = Pause"]
    phenix = help_screen.help_lines("phenix")
    assert phenix[2] == "À partir de 3 : Maj droite ou bouton B active le mode."
    assert phenix[5] == "Rappuie sur B / Maj droite pour couper et garder la jauge."
    assert help_screen.help_lines("shield")[1] == "Jauge pleine = prêt. B / Maj droite = 2 s d'invulnérabilité."
    set_lang("en")
    assert help_screen.help_lines("controls")[0] == "Keyboard : ← → ↑ ↓ + Space / Right Ctrl"
    assert help_screen.help_lines("phenix")[2] == "From 3: Right Shift or button B activates the form."


def test_a_changed_key_or_button_is_what_the_help_tells():
    b = bindings.current
    b.set_key(KB2, "phenix", 0, pygame.K_x)
    b.set_key(KB2, "fire", 0, pygame.K_f)
    b.set_key(KB2, "left", 0, pygame.K_j)
    assert b.set_pad_buttons(0, "phenix", [3])
    assert b.set_pad_buttons(0, "fire", [0, 2])
    assert b.set_pad_buttons(0, "pause", [6])
    lines = help_screen.help_lines("controls")
    assert lines[0] == "Clavier : J → ↑ ↓ + F / Ctrl droit"
    assert lines[1] == "Manette : stick + A  |  Back = Pause"
    assert help_screen.help_lines("phenix")[2] == "À partir de 3 : X ou bouton Y active le mode."
    assert help_screen.help_lines("shield")[1].startswith("Jauge pleine = prêt. Y / X = ")


def test_several_buttons_and_an_empty_slot_are_told_properly():
    b = bindings.current
    assert b.set_pad_buttons(0, "phenix", [1, 8])                    # (LB is the missile's)
    assert help_screen.help_lines("phenix")[2] == "À partir de 3 : Maj droite ou bouton B / L3 active le mode."
    values = bindings.help_values(t)
    assert values["pad_phenix"] == "B / L3" and values["pad_fire"] == "A"


def test_the_help_reads_the_table_of_the_first_pad_when_the_pads_have_their_own():
    b = bindings.current
    b.set_shared(False)
    assert b.set_pad_buttons(0, "phenix", [3])
    assert b.set_pad_buttons(1, "phenix", [2])
    assert bindings.help_values(t)["pad_phenix"] == "Y"
    assert help_screen.help_tip() == "Maj droite  \u00b7  Y"


def test_the_placeholders_are_the_same_in_the_13_languages():
    for section in SECTIONS:
        reference = [set(re.findall(r"\{(\w+)\}", line)) for line in i18n.HELP[section]["en"]]
        for lang in LANG_CODES:
            lines = i18n.HELP[section][lang]
            assert len(lines) == len(reference), (section, lang)
            assert [set(re.findall(r"\{(\w+)\}", line)) for line in lines] == reference, (section, lang)
    used = {p for s in SECTIONS for line in i18n.HELP[s]["en"] for p in re.findall(r"\{(\w+)\}", line)}
    assert used == PLACEHOLDERS


@pytest.mark.parametrize("lang", LANG_CODES)
def test_no_default_key_name_is_left_in_the_text_and_no_brace_shows(lang):
    set_lang(lang)
    for section in SECTIONS:
        for raw, line in zip(t_list(section), help_screen.help_lines(section)):
            assert "{" not in line and "}" not in line, (lang, line)
            assert "Shift / X" not in raw and "B / Shift" not in raw, (lang, raw)


def test_a_stray_brace_or_unknown_name_does_not_break_a_line():
    assert bindings.fill("a {unknown} b", {"kb_move": "x"}) == "a {unknown} b"
    assert bindings.fill("oops {", {}) == "oops {"
    assert bindings.fill("{kb_move}", {"kb_move": "Q D Z S"}) == "Q D Z S"


@pytest.mark.parametrize("lang", ["fr", "en", "ru", "de"])
def test_the_help_pages_draw_the_real_keys(run, lang):
    g = run.game
    set_lang(lang)
    bindings.current.set_key(KB2, "phenix", 0, pygame.K_x)
    seen = []
    real = g._txt

    def spy(font, text, color, *a, **k):
        seen.append(text)
        return real(font, text, color, *a, **k)

    g._txt = spy
    try:
        for page in (0, 1):
            help_screen.draw_help_page(g, pygame.Surface((1280, 720)), page, 0)
    finally:
        g._txt = real
    for section in ("controls", "phenix", "shield"):
        for line in help_screen.help_lines(section):
            assert line in seen, (lang, line)
    phenix_line = help_screen.help_lines("phenix")[2]
    assert "X" in phenix_line.replace("{", "") and "{" not in phenix_line
    assert all("Shift / X" not in str(x) for x in seen)
    assert help_screen.help_tip() in seen and help_screen.help_tip().startswith("X")


def test_the_caption_under_the_columns_follows_the_keys():
    assert help_screen.help_tip() == "Maj droite  \u00b7  B"
    bindings.current.set_key(KB2, "phenix", 0, pygame.K_x)
    bindings.current.set_pad_buttons(0, "phenix", [3])
    assert help_screen.help_tip() == "X  \u00b7  Y"
