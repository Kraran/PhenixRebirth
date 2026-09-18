"""
Local high-score persistence (JSON).

Stores the top 15 scores with 3-letter initials.
Optional "coop" flag marks scores set in 2-player simultaneous mode.
Default board is seeded with KRA / FFC / GRK for first launch.
"""
# Phenix Rebirth - High scores (top 15)

import json
import os

from settings import user_data_dir
HS_FILE = os.path.join(user_data_dir(), "highscores.json")
MAX_ENTRIES = 15

DEFAULT_SCORES = [
    {"name": "KRA", "score": 10000},
    {"name": "FFC", "score": 9000},
    {"name": "GRK", "score": 5000},
]

def default_highscores():
    return [dict(e) for e in DEFAULT_SCORES]

def load_highscores():
    try:
        with open(HS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and len(data) > 0:
            cleaned = []
            for e in data:
                if isinstance(e, dict) and "name" in e and "score" in e:
                    cleaned.append({
                        "name": str(e["name"])[:3].upper().ljust(3, "A"),
                        "score": int(e["score"]),
                        "coop": bool(e.get("coop", False)),
                    })
            if cleaned:
                cleaned.sort(key=lambda x: x["score"], reverse=True)
                return cleaned[:MAX_ENTRIES]
    except Exception:
        pass
    # First launch or empty/invalid file
    scores = default_highscores()
    save_highscores(scores)
    return scores

def save_highscores(entries):
    entries = sorted(entries, key=lambda x: x["score"], reverse=True)[:MAX_ENTRIES]
    try:
        with open(HS_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
    except Exception as e:
        print("Could not save highscores:", e)
    return entries

def reset_highscores():
    return save_highscores(default_highscores())

def is_highscore(score, entries=None):
    if score <= 0:
        return False
    if entries is None:
        entries = load_highscores()
    if len(entries) < MAX_ENTRIES:
        return True
    return score > entries[-1]["score"]

def insert_score(name, score, entries=None, coop=False):
    if entries is None:
        entries = load_highscores()
    entries.append({
        "name": name[:3].upper().ljust(3, "A"),
        "score": int(score),
        "coop": bool(coop),
    })
    return save_highscores(entries)
