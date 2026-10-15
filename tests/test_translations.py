"""The translations: accents in every language, and the texts that were in French and English only (the Adventure,
its scenes, the descriptions of the arcade game screen and of EXTRAS) translated in assets/lang/<code>.json."""
import json
import os
import re

import pytest

import i18n
from settings import asset_path

OTHERS = [c for c in i18n.LANG_CODES if c not in ("fr", "en")]
LATIN = [c for c in OTHERS if c != "ru"]


def _fr_en_only_keys():
    return list(i18n._ADVENTURE_TEXTS) + list(i18n._MENU_DESCRIPTIONS)


def _load(code):
    with open(asset_path("lang", code + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.parametrize("code", OTHERS)
def test_every_language_has_every_text(code):
    data = _load(code)
    missing = [k for k in _fr_en_only_keys() if not data.get(k)]
    assert not missing, (code, missing[:10])
    unknown = [k for k in data if k not in i18n.T]
    assert not unknown, (code, unknown)


def test_english_has_the_scenes():
    data = _load("en")
    assert set(i18n._INTRO_FR) <= set(data)
    for key in i18n._INTRO_FR:
        assert i18n.T[key]["en"] == data[key] != i18n.T[key]["fr"]


def _placeholders(text):
    return sorted(re.findall(r"\{[a-z_]+\}", text))


def test_placeholders_and_italics_are_kept_everywhere():
    bad = []
    for key, entry in i18n.T.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("fr"), str):
            continue
        fr = entry["fr"]
        for code, text in entry.items():
            if not isinstance(text, str):
                continue
            if _placeholders(text) != _placeholders(fr):
                bad.append((key, code, "placeholders"))
            if text.count("*") != fr.count("*"):
                bad.append((key, code, "italics"))
    assert not bad, bad[:10]


def test_the_scenes_keep_their_lines():
    """Same number of lines (and pauses) as the French text, in every language."""
    for key, fr in i18n._INTRO_FR.items():
        for code in i18n.LANG_CODES:
            assert i18n.T[key][code].count("\n") == fr.count("\n"), (key, code)


def test_accents_are_back():
    T = i18n.T
    assert T["quit"]["pl"] == "WYJŚCIE"
    assert T["quit"]["tr"] == "ÇIKIŞ"
    assert T["achievements"]["pl"] == "OSIĄGNIĘCIA"
    assert T["achievements"]["tr"] == "BAŞARIMLAR"
    assert T["story_map_empty"]["es"].startswith("Aún")
    assert "Khakivögel" in T["story_m_best2"]["de"]
    assert "fåglar" in T["story_m_sortie_b"]["sv"]
    assert T["achievements"]["da"] == "PRÆSTATIONER"
    assert T["quit_game_q"]["es"] == "¿Cerrar el juego?"


@pytest.mark.parametrize("code", LATIN)
def test_no_language_is_written_without_its_letters(code):
    """Each Latin language uses its own letters in its longer texts (they had all been stripped)."""
    marks = {"es": "áéíóúñ¿¡", "de": "äöüß", "it": "àèéìòù", "pt": "áâãàçéêíóôõú", "nl": "éëïöü",
             "pl": "ąćęłńóśźż", "tr": "çğıöşüİ", "sv": "åäö", "no": "æøå", "da": "æøå"}[code]
    texts = [e[code] for e in i18n.T.values() if isinstance(e, dict) and isinstance(e.get(code), str)
             and len(e[code]) > 40 and e[code] != e.get("en")]      # (not the English shown until a translation)
    with_marks = sum(1 for s in texts if any(ch in s.lower() for ch in marks))
    floor = {"it": 0.35, "nl": 0.15}.get(code, 0.5)          # Italian and Dutch need fewer accents
    assert with_marks / len(texts) > floor, (code, with_marks, len(texts))


def test_a_broken_language_file_keeps_the_english(tmp_path, monkeypatch):
    import settings
    (tmp_path / "lang").mkdir()
    (tmp_path / "lang" / "de.json").write_text("{broken", encoding="utf-8")
    (tmp_path / "lang" / "it.json").write_text(json.dumps({"story_pilot": "PILOTA X", "nope": "x"}),
                                               encoding="utf-8")
    monkeypatch.setattr(settings, "asset_path", lambda *parts: os.path.join(str(tmp_path), *parts))
    saved = {k: dict(v) for k, v in i18n.T.items() if isinstance(v, dict)}
    try:
        for k in ("story_pilot", "story_best"):
            i18n.T[k]["de"] = i18n.T[k]["en"]
            i18n.T[k]["it"] = i18n.T[k]["en"]
        i18n._load_lang_files()
        assert i18n.T["story_pilot"]["it"] == "PILOTA X"
        assert i18n.T["story_best"]["it"] == i18n.T["story_best"]["en"]       # not in the file: English
        assert i18n.T["story_pilot"]["de"] == i18n.T["story_pilot"]["en"]     # broken file: English
        assert "nope" not in i18n.T
    finally:
        for k, v in saved.items():
            i18n.T[k] = v
