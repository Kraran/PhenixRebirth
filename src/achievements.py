"""
Local achievements (hauts faits).

Persisted next to highscores.json. Cheats / attract mode must not unlock.

Each catalog row: id + icon key. Titles live in i18n (ach_<id>, ach_<id>_d).

Scalable entries (SCALABLE) store a counter in progress[] and a tier
normal / bronze / silver / gold. Thresholds are 4-tuples.
"boldly_go" uses (21,21,21,21) so the first unlock is gold.
Old binary saves migrate to progress = first threshold, tier normal.
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
    ("listen_nostalgie_start", "music"),
    ("listen_nostalgie_elise", "music"),
    ("listen_music_all", "music"),
    ("clean_shot", "bird1"),
    ("razor", "edge"),
    ("butcher", "bird2"),
    ("wrecker", "boss"),
    ("cutter", "flag"),
    ("duo_fire", "coop"),
    ("marathon", "ship"),
    ("pleiades", "scroll"),
    ("port_pair", "boss"),
    ("boldly_go", "flag"),
]

CATALOG_IDS = [aid for aid, _ in CATALOG]

# aid -> (normal, bronze, silver, gold) thresholds
SCALABLE = {
    "first_blood": (1, 100, 500, 2000),
    "stage2": (2, 5, 10, 20),
    "boss_down": (1, 3, 5, 10),
    "loop": (1, 3, 5, 10),
    "ten_flags": (1, 5, 10, 15),
    "phenix_wake": (1, 10, 25, 50),
    "iron_curtain": (1, 10, 25, 50),
    "survivor": (1, 5, 10, 20),
    "no_edge": (1, 5, 10, 20),
    "gauge_max": (1, 5, 15, 30),
    "veteran_clear": (1, 3, 5, 10),
    "one_up_1337": (1, 3, 5, 10),
    "elite_8086": (1, 2, 4, 8),
    "clean_shot": (10, 25, 50, 100),
    "razor": (1, 5, 15, 30),
    "butcher": (5, 20, 50, 100),
    "wrecker": (20, 80, 200, 500),
    "cutter": (2, 10, 25, 50),
    "duo_fire": (1, 3, 8, 15),
    "marathon": (5000, 20000, 50000, 100000),
    "pleiades": (1, 5, 15, 30),
    "port_pair": (1, 3, 5, 10),
    "boldly_go": (21, 21, 21, 21),
}
TIER_ORDER = ("normal", "bronze", "silver", "gold")


def _empty():
    return {"unlocked": {}, "progress": {}, "tiers": {}}


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
        prog = data.get("progress") or {}
        tiers = data.get("tiers") or {}
        progress, tier_map = {}, {}
        if isinstance(prog, dict):
            for k, v in prog.items():
                try:
                    progress[str(k)] = max(0, int(v))
                except Exception:
                    pass
        if isinstance(tiers, dict):
            for k, v in tiers.items():
                if v in TIER_ORDER:
                    tier_map[str(k)] = v
        # Migrate old binary unlocks into scalable normal (1st threshold)
        for aid, steps in SCALABLE.items():
            if aid in cleaned and progress.get(aid, 0) < steps[0]:
                progress[aid] = steps[0]
                tier_map.setdefault(aid, "normal")
        return {"unlocked": cleaned, "progress": progress, "tiers": tier_map}
    except Exception:
        return _empty()


def save_achievements(data):
    try:
        payload = {
            "unlocked": dict((data or {}).get("unlocked") or {}),
            "progress": dict((data or {}).get("progress") or {}),
            "tiers": dict((data or {}).get("tiers") or {}),
        }
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


def scalable_thresholds(aid):
    return SCALABLE.get(aid)


def scalable_progress(aid, data=None):
    if data is None:
        data = load_achievements()
    return int((data.get("progress") or {}).get(aid, 0) or 0)


def scalable_tier(aid, data=None):
    if data is None:
        data = load_achievements()
    return (data.get("tiers") or {}).get(aid)


def add_scalable(aid, amount=1, data=None):
    """Add progress. Returns (newly_unlocked_or_upgraded, tier_or_None)."""
    if aid not in SCALABLE:
        return False, None
    if data is None:
        data = load_achievements()
    steps = SCALABLE[aid]
    prog = data.setdefault("progress", {})
    tiers = data.setdefault("tiers", {})
    unlocked = data.setdefault("unlocked", {})
    prev = int(prog.get(aid, 0) or 0)
    now = prev + max(0, int(amount))
    prog[aid] = now
    new_tier = None
    for name, th in zip(TIER_ORDER, steps):
        if now >= th:
            new_tier = name
    old_tier = tiers.get(aid)
    changed = False
    if new_tier and aid not in unlocked:
        from datetime import datetime, timezone
        unlocked[aid] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        changed = True
    if new_tier and new_tier != old_tier:
        tiers[aid] = new_tier
        changed = True
    if changed or now != prev:
        save_achievements(data)
    return changed, new_tier


def set_scalable_at_least(aid, value, data=None):
    """Set progress to max(current, value). Returns (changed, tier)."""
    if aid not in SCALABLE:
        return False, None
    if data is None:
        data = load_achievements()
    prev = int((data.get("progress") or {}).get(aid, 0) or 0)
    value = int(value)
    if value <= prev:
        return False, (data.get("tiers") or {}).get(aid)
    return add_scalable(aid, value - prev, data)
