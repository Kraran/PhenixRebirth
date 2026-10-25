"""
settings.json: load (with defaults) and save.

Moved out of game.py so that other modules can read the user settings without
importing the whole Game class.
"""
import json
import math
import os

from safe_io import atomic_write_json, backup_unreadable
from settings import user_data_dir
from i18n import LANG_CODES

SETTINGS_FILE = os.path.join(user_data_dir(), "settings.json")

def clean_user_settings(data):
    """Validate each setting independently, preserving valid preferences."""
    defaults = {
        "coop_p1": "auto",  # coop: the device of player 1 and 2: auto | kb_left | kb_arrows | pad1, pad2...
        "coop_p2": "auto",
        "control_pref": "auto",  # auto (the last device used) | keyboard | gamepad
        "bindings": {},  # the keys and buttons the player changed (src/bindings.py); {} = all the defaults
        "display_mode": "fullscreen",
        "sfx_volume": 0.8,
        "music_volume": 0.4,
        "rumble_level": 3,  # 0=off … 3=normal … 5=max
        "autofire": True,  # hold fire key to shoot again when the shot leaves
        "language": "fr",
        "show_fps": False,
        "scanlines": 0,  # 0=off, 1/2/3 intensity
        "bezel_style": "phoenix",  # off | phoenix | (future styles)
        "monitor_index": 0,
        "gpu_present": True,  # SDL2 GPU upscale (falls back to CPU)
        "vsync_mode": "adaptive",  # on | adaptive | off
        "fps_cap": 120,  # 60 | 75 | 120 | 144
        "audio_mix": "sfx",
        "ingame_music": "none",
        "season_force": "",  # "" | xmas | halloween — title overlay test
    }
    if not isinstance(data, dict):
        return defaults
    enums = {
        "control_pref": ("auto", "keyboard", "gamepad"),
        "display_mode": ("fullscreen", "window", "borderless"),
        "language": LANG_CODES,
        "bezel_style": ("off", "phoenix", "tesla", "blue", "fire"),
        "vsync_mode": ("on", "adaptive", "off"),
        "audio_mix": ("sfx", "sfx_music", "music", "off"),
        "season_force": ("", "xmas", "halloween"),
    }
    for key, default in defaults.items():
        value = data.get(key, default)
        if key in enums:
            if isinstance(value, str) and value in enums[key]:
                defaults[key] = value
        elif isinstance(default, bool):
            if isinstance(value, bool):
                defaults[key] = value
        elif key in ("sfx_volume", "music_volume", "rumble_level", "scanlines", "monitor_index", "fps_cap"):
            if key == "scanlines" and isinstance(value, bool):
                value = int(value)  # old settings stored scanlines as a boolean
            try:
                number = float(value) if not isinstance(value, bool) else float("nan")
                if not math.isfinite(number):
                    continue
                if key in ("sfx_volume", "music_volume"):
                    defaults[key] = max(0.0, min(1.0, number))
                elif number.is_integer():
                    number = int(number)
                    if key == "fps_cap":
                        if number in (60, 75, 120, 144):
                            defaults[key] = number
                    elif key == "monitor_index":
                        if 0 <= number <= 2**31 - 1:
                            defaults[key] = number
                    else:
                        defaults[key] = max(0, min(5 if key == "rumble_level" else 3, number))
            except (TypeError, ValueError, OverflowError):
                pass
        elif isinstance(value, type(default)):
            # Bindings have their own nested validation in bindings.load().
            defaults[key] = value
    for key in ("coop_p1", "coop_p2"):
        value = defaults[key]
        if value not in ("auto", "kb_left", "kb_arrows") and not (
                value.startswith("pad") and value[3:].isascii() and value[3:].isdigit()
                and len(value[3:]) <= 9 and int(value[3:]) >= 1):
            defaults[key] = "auto"
    return defaults


def load_user_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Settings must be a JSON object")
    except FileNotFoundError:
        data = None
    except Exception:
        backup_unreadable(SETTINGS_FILE)
        data = None
    return clean_user_settings(data)

def save_user_settings(data):
    try:
        atomic_write_json(SETTINGS_FILE, data)
    except Exception as e:
        print("Could not save settings:", e)
