"""
Local achievements (hauts faits).

Persisted next to highscores.json. Cheats / attract mode must not unlock.
Each entry: id + icon key. Titles/descriptions live in i18n.
"""
import json
import os
from datetime import datetime, timezone

from settings import user_data_dir

ACH_FILE = os.path.join(user_data_dir(), "achievements.json")

# icon: sprite hint used by Game._ach_icon
CATALOG = [
    ("first_blood", "bird1"),
    ("stage2", "bird2"),
    ("boss_down", "boss"),
    ("loop", "flag"),
    ("one_up_1337", "ship"),
    ("elite_8086", "ship"),
    ("phenix_wake", "phenix"),
    ("iron_curtain", "shield"),
    ("mixed_squad", "coop"),
    ("survivor", "ship"),
    ("ten_flags", "flag"),
    ("veteran_clear", "boss"),
    ("no_edge", "edge"),
    ("hotseat", "coop"),
    ("gauge_max", "phenix"),
    ("credits_watch", "scroll"),
    ("listen_menu", "music"),
    ("listen_hs", "music"),
    ("listen_credits", "music"),
]

CATALOG_IDS = [aid for aid, _ in CATALOG]


def _empty():
    return {"unlocked": {}}


def load_achievements():
    try:
        with open(ACH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _empty()
        raw = data.get("unlocked") or {}
        cleaned = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if k in CATALOG_IDS:
                    cleaned[str(k)] = v
        return {"unlocked": cleaned}
    except Exception:
        return _empty()


def save_achievements(data):
    try:
        payload = {"unlocked": dict((data or {}).get("unlocked") or {})}
        with open(ACH_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        print("Could not save achievements:", e)
    return data


def is_unlocked(aid, data=None):
    if data is None:
        data = load_achievements()
    return aid in (data.get("unlocked") or {})


def unlock_achievement(aid, data=None):
    """Unlock once. Returns True if this call newly unlocked it."""
    if aid not in CATALOG_IDS:
        return False
    if data is None:
        data = load_achievements()
    unlocked = data.setdefault("unlocked", {})
    if aid in unlocked:
        return False
    unlocked[aid] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_achievements(data)
    return True


def unlocked_count(data=None):
    if data is None:
        data = load_achievements()
    return len(data.get("unlocked") or {})
