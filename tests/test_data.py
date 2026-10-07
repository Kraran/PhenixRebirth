"""Fast checks on game data: translations, high scores, stage rules.
No window and no Game object needed."""
import glob
import os
import re

import pytest

import i18n
import highscores
import settings

SRC = os.path.join(os.path.dirname(__file__), "..", "src")


def test_every_text_exists_in_all_languages():
    missing = [
        (key, code)
        for key, entry in i18n.T.items()
        for code in i18n.LANG_CODES
        if not str(entry.get(code, "")).strip()
    ]
    assert not missing, f"missing translations (key, lang): {missing[:10]}"


def test_help_and_credits_cover_all_languages():
    for name in ("HELP", "CREDITS"):
        table = getattr(i18n, name)
        for key, entry in table.items():
            if isinstance(entry, dict):
                absent = [c for c in i18n.LANG_CODES if c not in entry]
                assert not absent, f"{name}[{key}] lacks {absent}"


def test_texts_used_in_code_exist():
    """t("some_key") in the code must exist, else the player sees the raw key."""
    pattern = re.compile(r'(?<![\w.])t\(\s*["\']([A-Za-z0-9_]+)["\']\s*\)')
    unknown = {}
    for path in glob.glob(os.path.join(SRC, "*.py")):
        if path.endswith("i18n.py"):
            continue
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                for key in pattern.findall(line):
                    if key not in i18n.T:
                        unknown[key] = f"{os.path.basename(path)}:{lineno}"
    assert not unknown, f"unknown translation keys: {unknown}"


def test_set_lang_falls_back_to_french():
    i18n.set_lang("xx")
    assert i18n.get_lang() == "fr"
    i18n.set_lang("en")
    assert i18n.get_lang() == "en"


@pytest.fixture
def hs_file(tmp_path, monkeypatch):
    monkeypatch.setattr(highscores, "HS_FILE", str(tmp_path / "highscores.json"))
    return tmp_path / "highscores.json"


def test_highscores_first_launch_creates_defaults(hs_file):
    entries = highscores.load_highscores()
    assert entries and hs_file.exists()
    assert entries == sorted(entries, key=lambda e: e["score"], reverse=True)


def test_highscores_insert_sorts_and_caps(hs_file):
    entries = highscores.load_highscores()
    for i in range(30):
        entries = highscores.insert_score("ab", 100 * (i + 1), entries)
    assert len(entries) == highscores.MAX_ENTRIES
    assert entries[0]["score"] == 10000  # default KRA score is still the best
    assert [e["score"] for e in entries] == sorted((e["score"] for e in entries), reverse=True)
    assert all(len(e["name"]) == 3 for e in entries)


def test_highscores_corrupt_file_is_replaced(hs_file):
    hs_file.write_text("not json", encoding="utf-8")
    assert highscores.load_highscores()


def test_highscores_rejects_zero_score(hs_file):
    assert highscores.is_highscore(0) is False


def test_stage_cycle_and_speed():
    assert [settings.stage_content(s) for s in range(1, 12)] == [1, 2, 3, 4, 5, 1, 2, 3, 4, 5, 1]
    assert settings.stage_speed_mult(1) == 1.0
    assert settings.stage_speed_mult(5) == 1.0
    assert settings.stage_speed_mult(6) == pytest.approx(1.1)
    assert settings.stage_speed_mult(11) == pytest.approx(1.2)
