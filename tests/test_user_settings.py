"""Damaged settings must not stop startup or discard other valid preferences."""
import json
from types import SimpleNamespace

import pytest

import user_settings as us


@pytest.mark.parametrize("value", [None, "oops", [], {}, True, float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("key", ["sfx_volume", "music_volume", "rumble_level", "monitor_index", "fps_cap"])
def test_invalid_numbers_fall_back_independently(tmp_path, monkeypatch, key, value):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({key: value, "language": "en"}), encoding="utf-8")
    monkeypatch.setattr(us, "SETTINGS_FILE", str(path))
    result = us.load_user_settings()
    assert result[key] == us.clean_user_settings(None)[key]
    assert result["language"] == "en"


@pytest.mark.parametrize("data", [[], ["sfx_volume"], "music_volume", None, 7])
def test_non_object_settings_are_backed_up(tmp_path, monkeypatch, data):
    path = tmp_path / "settings.json"
    text = json.dumps(data)
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(us, "SETTINGS_FILE", str(path))
    assert us.load_user_settings() == us.clean_user_settings(None)
    assert (tmp_path / "settings.json.corrupt").read_text(encoding="utf-8") == text


def test_numeric_bounds_and_legacy_scanlines():
    settings = us.clean_user_settings({"sfx_volume": -2, "music_volume": 9, "rumble_level": 20,
                                       "scanlines": True, "monitor_index": -1, "fps_cap": 999})
    assert (settings["sfx_volume"], settings["music_volume"], settings["rumble_level"], settings["scanlines"]) == (0, 1, 5, 1)
    assert settings["monitor_index"] == 0 and settings["fps_cap"] == 120
    assert us.clean_user_settings({"scanlines": False})["scanlines"] == 0
    assert us.clean_user_settings({"scanlines": "oops"})["scanlines"] == 0


def test_invalid_enums_booleans_and_types_keep_defaults():
    defaults = us.clean_user_settings(None)
    for value in (None, [], {}, 123, "invalid"):
        for key in defaults:
            if key in ("sfx_volume", "music_volume", "rumble_level", "scanlines", "monitor_index", "fps_cap"):
                continue
            settings = us.clean_user_settings({key: value})
            if key == "ingame_music" and isinstance(value, str):
                # Track names (including custom ones) are resolved by ingame_music.normalize().
                continue
            if key == "bindings" and isinstance(value, dict):
                continue
            assert settings[key] == defaults[key], (key, value)


def test_valid_preferences_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(us, "SETTINGS_FILE", str(path))
    data = {"language": "en", "sfx_volume": 0.25, "music_volume": 0.75, "display_mode": "window",
            "rumble_level": 5, "monitor_index": 2, "fps_cap": 144, "scanlines": 3,
            "coop_p1": "pad2", "coop_p2": "kb_arrows", "bezel_style": "tesla", "audio_mix": "sfx_music",
            "autofire": False, "show_fps": True, "gpu_present": False, "vsync_mode": "off",
            "bindings": {"kb2": {"fire": ["x", None]}}, "ingame_music": "custom:my-song.mp3"}
    us.save_user_settings(data)
    result = us.load_user_settings()
    assert all(result[k] == v for k, v in data.items())


def test_settings_initialization_with_damaged_file(tmp_path, monkeypatch):
    import game_init

    path = tmp_path / "settings.json"
    defaults = us.clean_user_settings(None)
    path.write_text(json.dumps({key: {"invalid": True} for key in defaults}), encoding="utf-8")
    monkeypatch.setattr(us, "SETTINGS_FILE", str(path))
    game = SimpleNamespace(_apply_control_pref=lambda: None, _rebuild_life_icon=lambda: None,
                           _read_season_force=lambda user: user["season_force"], _gpu=None,
                           _bind_gpu=lambda: None)
    game_init.init_settings(game, soft=False)
    assert game.sfx_volume == 0.8 and game.music_volume == 0.4
    assert game.monitor_index == 0 and game.language == "fr"
