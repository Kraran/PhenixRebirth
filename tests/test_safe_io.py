"""Safe saving: a failed or interrupted save must never destroy the existing file."""
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import achievements  # noqa: E402
import highscores  # noqa: E402
import safe_io  # noqa: E402
import user_settings  # noqa: E402


def test_atomic_write_creates_and_replaces(tmp_path):
    p = tmp_path / "a.json"
    safe_io.atomic_write_json(str(p), {"x": 1})
    assert json.loads(p.read_text(encoding="utf-8")) == {"x": 1}
    safe_io.atomic_write_json(str(p), {"x": 2})
    assert json.loads(p.read_text(encoding="utf-8")) == {"x": 2}
    assert not (tmp_path / "a.json.tmp").exists()


def test_bad_value_keeps_old_file(tmp_path):
    p = tmp_path / "a.json"
    safe_io.atomic_write_json(str(p), {"x": 1})
    with pytest.raises(TypeError):
        safe_io.atomic_write_json(str(p), {"x": object()})
    assert json.loads(p.read_text(encoding="utf-8")) == {"x": 1}
    assert not (tmp_path / "a.json.tmp").exists()


def test_crash_during_write_keeps_old_file(tmp_path, monkeypatch):
    """Power cut simulated between writing the temp file and swapping it in."""
    p = tmp_path / "a.json"
    safe_io.atomic_write_json(str(p), {"x": 1})

    def boom(src, dst):
        raise KeyboardInterrupt  # not an Exception: no fallback runs, like a real crash

    monkeypatch.setattr(safe_io.os, "replace", boom)
    with pytest.raises(KeyboardInterrupt):
        safe_io.atomic_write_json(str(p), {"x": 2})
    assert json.loads(p.read_text(encoding="utf-8")) == {"x": 1}


def test_locked_target_falls_back_to_direct_write(tmp_path, monkeypatch):
    p = tmp_path / "a.json"
    monkeypatch.setattr(safe_io.os, "replace", lambda s, d: (_ for _ in ()).throw(PermissionError("locked")))
    monkeypatch.setattr(safe_io.time, "sleep", lambda s: None)
    safe_io.atomic_write_json(str(p), {"x": 3})
    assert json.loads(p.read_text(encoding="utf-8")) == {"x": 3}
    assert not (tmp_path / "a.json.tmp").exists()


def test_backup_unreadable(tmp_path):
    p = tmp_path / "a.json"
    assert safe_io.backup_unreadable(str(p)) is False  # missing file
    p.write_text("", encoding="utf-8")
    assert safe_io.backup_unreadable(str(p)) is False  # empty file
    p.write_text("{broken", encoding="utf-8")
    assert safe_io.backup_unreadable(str(p)) is True
    assert (tmp_path / "a.json.corrupt").read_text(encoding="utf-8") == "{broken"


def test_corrupt_highscores_are_kept_aside(tmp_path, monkeypatch):
    p = tmp_path / "highscores.json"
    monkeypatch.setattr(highscores, "HS_FILE", str(p))
    p.write_text('[{"name": "ABC", "score": 99999', encoding="utf-8")  # truncated
    entries = highscores.load_highscores()
    assert entries and json.loads(p.read_text(encoding="utf-8"))  # defaults written
    assert (tmp_path / "highscores.json.corrupt").read_text(encoding="utf-8").startswith('[{"name": "ABC"')


def test_corrupt_achievements_are_kept_aside(tmp_path, monkeypatch):
    p = tmp_path / "achievements.json"
    monkeypatch.setattr(achievements, "ACH_FILE", str(p))
    p.write_text("{oops", encoding="utf-8")
    assert achievements.load_achievements() == {"unlocked": {}, "progress": {}, "tiers": {}}
    assert (tmp_path / "achievements.json.corrupt").exists()


def test_corrupt_settings_are_kept_aside(tmp_path, monkeypatch):
    p = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(p))
    p.write_text("not json", encoding="utf-8")
    assert user_settings.load_user_settings()["language"] == "fr"
    assert (tmp_path / "settings.json.corrupt").exists()


def test_settings_roundtrip_and_no_backup_when_missing(tmp_path, monkeypatch):
    p = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(p))
    assert user_settings.load_user_settings()["language"] == "fr"
    assert not (tmp_path / "settings.json.corrupt").exists()
    user_settings.save_user_settings({"language": "en", "fps_cap": 60})
    got = user_settings.load_user_settings()
    assert got["language"] == "en" and got["fps_cap"] == 60


def test_achievements_save_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(achievements, "ACH_FILE", str(tmp_path / "achievements.json"))
    achievements.save_achievements({"unlocked": {}, "progress": {"marathon": 7}, "tiers": {}})
    assert achievements.load_achievements()["progress"] == {"marathon": 7}


# --- écriture différée (hauts faits sauvegardés pendant la partie) -----------

def test_write_behind_visible_tout_de_suite_et_sur_disque_apres_flush(tmp_path, monkeypatch):
    p = str(tmp_path / "wb.json")
    monkeypatch.setattr(safe_io, "COALESCE_SEC", 0.05)
    safe_io.write_behind(p, '{"a": 1}')
    assert safe_io.read_text_latest(p) == '{"a": 1}'     # même si pas encore écrit
    assert safe_io.flush() is True
    assert (tmp_path / "wb.json").read_text(encoding="utf-8") == '{"a": 1}'
    assert not (tmp_path / "wb.json.tmp").exists()
    assert safe_io.read_text_latest(p) == '{"a": 1}'     # relu depuis le disque


def test_write_behind_ne_fait_pas_attendre_et_fusionne(tmp_path, monkeypatch):
    p = str(tmp_path / "wb2.json")
    calls = []
    real = safe_io.atomic_write_text

    def slow(path, text):
        calls.append(text)
        time.sleep(0.15)
        real(path, text)

    monkeypatch.setattr(safe_io, "atomic_write_text", slow)
    monkeypatch.setattr(safe_io, "COALESCE_SEC", 0.05)
    t0 = time.perf_counter()
    for i in range(50):
        safe_io.write_behind(p, '{"n": %d}' % i)
    assert time.perf_counter() - t0 < 0.1               # l'appelant n'attend pas le disque
    assert safe_io.read_text_latest(p) == '{"n": 49}'
    assert safe_io.flush() is True
    assert (tmp_path / "wb2.json").read_text(encoding="utf-8") == '{"n": 49}'
    assert len(calls) <= 3                              # 50 sauvegardes -> quelques écritures
    assert calls[-1] == '{"n": 49}'


def test_write_behind_erreur_n_arrete_pas_le_fil(tmp_path, monkeypatch):
    bad = str(tmp_path / "no_such_dir" / "x.json")
    good = str(tmp_path / "ok.json")
    monkeypatch.setattr(safe_io, "COALESCE_SEC", 0.01)
    safe_io.write_behind(bad, "{}")
    safe_io.flush()
    safe_io.write_behind(good, '{"ok": true}')
    assert safe_io.flush() is True
    assert (tmp_path / "ok.json").read_text(encoding="utf-8") == '{"ok": true}'


def test_hauts_faits_relus_apres_chaque_sauvegarde(tmp_path, monkeypatch):
    p = tmp_path / "achievements.json"
    monkeypatch.setattr(achievements, "ACH_FILE", str(p))
    monkeypatch.setattr(safe_io, "COALESCE_SEC", 0.05)
    # comme Game._note_scalable : ajout + relecture à chaque oiseau abattu
    data = achievements.load_achievements()
    for _ in range(120):
        achievements.add_scalable("first_blood", 1, data)
        data = achievements.load_achievements()
    assert data["progress"]["first_blood"] == 120
    safe_io.flush()
    assert json.loads(p.read_text(encoding="utf-8"))["progress"]["first_blood"] == 120
