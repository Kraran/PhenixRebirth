"""available_sets() : le menu l'appelle à chaque image, le résultat est gardé quelques secondes."""
import addon


def _reset(monkeypatch, sets):
    calls = {"n": 0}

    def fake_scan():
        calls["n"] += 1
        return list(sets["value"])

    monkeypatch.setattr(addon, "_scan_sets", fake_scan)
    monkeypatch.setattr(addon, "_sets_cache", None)
    return calls


def test_cache_evite_de_relire_le_disque(monkeypatch):
    sets = {"value": [("phoenix", "Phoenix")]}
    calls = _reset(monkeypatch, sets)
    for _ in range(100):
        assert addon.available_sets() == [("phoenix", "Phoenix")]
        assert addon.addon_ready() is True
    assert calls["n"] == 1


def test_fresh_relit_toujours(monkeypatch):
    sets = {"value": [("phoenix", "Phoenix")]}
    calls = _reset(monkeypatch, sets)
    addon.available_sets()
    sets["value"] = []
    assert addon.available_sets() == [("phoenix", "Phoenix")]      # encore le cache
    assert addon.available_sets(fresh=True) == []                  # relu à neuf
    assert addon.available_sets() == []                            # et le cache est à jour
    assert calls["n"] == 2


def test_cache_expire(monkeypatch):
    sets = {"value": [("phoenix", "Phoenix")]}
    calls = _reset(monkeypatch, sets)
    t = {"now": 1000.0}
    monkeypatch.setattr(addon.time, "monotonic", lambda: t["now"])
    addon.available_sets()
    sets["value"] = [("phoenix", "Phoenix"), ("pleiads", "Pleiads")]
    t["now"] += addon._SETS_TTL - 0.5
    assert len(addon.available_sets()) == 1
    t["now"] += 1.0
    assert len(addon.available_sets()) == 2
    assert calls["n"] == 2


def test_liste_rendue_est_une_copie(monkeypatch):
    sets = {"value": [("phoenix", "Phoenix")]}
    _reset(monkeypatch, sets)
    first = addon.available_sets()
    first.append(("x", "X"))
    assert addon.available_sets() == [("phoenix", "Phoenix")]


def test_sans_mame_liste_vide(monkeypatch):
    monkeypatch.setattr(addon, "_sets_cache", None)
    monkeypatch.setattr(addon, "mame_exe", lambda: None)
    assert addon.available_sets(fresh=True) == []
    assert addon.addon_ready() is False
