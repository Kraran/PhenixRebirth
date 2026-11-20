"""The flags of the languages in the options (src/lang_flags.py) and the language of the system at the very first start
(src/sys_lang.py): the game starts in it when it has it, else in English."""
import json

import pygame
import pytest

import i18n
import lang_flags
import sys_lang
import user_settings as us
from test_smoke import run  # noqa: F401  (fixture)

detect = sys_lang.real_detect          # (tests/conftest.py makes every other test start on a French system)


# ------------------------------------------------------------------ the flags
def test_every_language_has_its_flag():
    for code in i18n.LANG_CODES:
        img = lang_flags.flag(code)
        assert img is not None and img.get_size() == (33, 22), code
    assert lang_flags.flag("xx") is None


def test_the_flags_are_made_once_and_are_not_all_alike():
    assert lang_flags.flag("fr") is lang_flags.flag("fr")
    looks = {pygame.image.tobytes(lang_flags.flag(c), "RGB") for c in i18n.LANG_CODES}
    assert len(looks) == len(i18n.LANG_CODES)


def test_the_french_flag_is_blue_white_red():
    img = lang_flags.flag("fr", 30)
    left, middle, right = (img.get_at((x, 15))[:3] for x in (6, 22, 38))
    assert left[2] > 120 and left[0] < 60
    assert min(middle) > 230
    assert right[0] > 200 and right[2] < 90


def test_the_options_draw_the_flag_before_the_language(run, monkeypatch):
    import draw_frame
    import main_menu
    g = run.game
    drawn = []
    real = lang_flags.flag
    monkeypatch.setattr(lang_flags, "flag", lambda code, h=22: drawn.append(code) or real(code, h))
    g.language = "de"
    g.opt_tab = next(i for i, (_n, rows) in enumerate(main_menu.OPTION_TABS) if "language" in rows)
    g.menu_index = g._options_spec().index("language")
    draw_frame.draw_options(g, 40)
    assert "de" in drawn


# ------------------------------------------------------------------ the language of the system
@pytest.mark.parametrize("name,code", [
    ("fr_FR.UTF-8", "fr"), ("de_DE", "de"), ("es-ES", "es"), ("pt_BR.utf8", "pt"), ("nb_NO", "no"), ("nn_NO", "no"),
    ("sv_SE", "sv"), ("da_DK", "da"), ("ru_RU.UTF-8", "ru"), ("en_GB", "en"), ("tr_TR", "tr"),
    ("French_France", "fr"), ("German_Germany", "de"), ("Norwegian Bokmål_Norway", "no"),
    ("ja_JP", None), ("C", None), ("POSIX", None), ("", None), (None, None),
])
def test_the_names_of_the_system(name, code):
    assert sys_lang.code_of(name) == code


@pytest.mark.parametrize("env,code", [
    ({"LANG": "de_DE.UTF-8"}, "de"),
    ({"LANGUAGE": "ja:it:en", "LANG": "ja_JP"}, "it"),
    ({"LC_ALL": "pl_PL.UTF-8", "LANG": "fr_FR"}, "pl"),
    ({"LANG": "ja_JP.UTF-8"}, "en"),
    ({"LANG": "C.UTF-8"}, "en"),
    ({}, "en"),
])
def test_detect_reads_the_system_or_falls_back_to_english(monkeypatch, env, code):
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(sys_lang.sys, "platform", "linux")
    monkeypatch.setattr(sys_lang.locale, "getlocale", lambda *a: (None, None))
    monkeypatch.setattr(sys_lang.locale, "setlocale", lambda *a: "C")
    assert detect() == code


def test_on_windows_the_language_of_the_interface_comes_first(monkeypatch):
    monkeypatch.setattr(sys_lang.sys, "platform", "win32")
    monkeypatch.setattr(sys_lang, "_windows", lambda: "it_IT")
    monkeypatch.setenv("LANG", "de_DE")
    assert detect() == "it"
    monkeypatch.setattr(sys_lang, "_windows", lambda: None)
    assert detect() == "de"


def test_detect_never_fails(monkeypatch):
    def boom():
        raise RuntimeError("no")
    monkeypatch.setattr(sys_lang.sys, "platform", "linux")
    monkeypatch.setattr(sys_lang, "_environment", boom)
    assert detect() == "en"


# ------------------------------------------------------------------ the first start
def test_the_first_start_takes_the_system_language_then_keeps_the_choice(tmp_path, monkeypatch):
    p = tmp_path / "settings.json"
    monkeypatch.setattr(us, "SETTINGS_FILE", str(p))
    monkeypatch.setattr(sys_lang, "detect", lambda: "es")
    assert us.load_user_settings()["language"] == "es"                 # no settings.json: the system's
    p.write_text(json.dumps({"fps_cap": 60}), encoding="utf-8")
    assert us.load_user_settings()["language"] == "es"                 # a file without a language: the system's
    us.save_user_settings({"language": "pl"})
    assert us.load_user_settings()["language"] == "pl"                 # a language chosen: kept, whatever the system
    p.write_text(json.dumps({"language": "xx"}), encoding="utf-8")
    assert us.load_user_settings()["language"] == "es"


def test_a_system_in_a_language_the_game_has_not_starts_it_in_english(tmp_path, monkeypatch):
    monkeypatch.setattr(us, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(sys_lang, "detect", sys_lang.real_detect)
    monkeypatch.setattr(sys_lang.sys, "platform", "linux")
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LANG", "ja_JP.UTF-8")
    monkeypatch.setattr(sys_lang.locale, "getlocale", lambda *a: ("ja_JP", "UTF-8"))
    monkeypatch.setattr(sys_lang.locale, "setlocale", lambda *a: "ja_JP.UTF-8")
    assert us.load_user_settings()["language"] == "en"
