"""
settings.json: load (with defaults) and save.

Moved out of game.py so that other modules can read the user settings without
importing the whole Game class.
"""
import json
import os

from safe_io import atomic_write_json, backup_unreadable
from settings import user_data_dir

SETTINGS_FILE = os.path.join(user_data_dir(), "settings.json")

def load_user_settings():
    defaults = {
        "input_mode": None,  # None = auto
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
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        defaults.update({k: data[k] for k in defaults if k in data})
    except FileNotFoundError:
        pass
    except Exception:
        backup_unreadable(SETTINGS_FILE)
    return defaults

def save_user_settings(data):
    try:
        atomic_write_json(SETTINGS_FILE, data)
    except Exception as e:
        print("Could not save settings:", e)
