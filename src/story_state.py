"""
Adventure rules and save data (no drawing, no window).

Everything the adventure *decides* lives here so it can be tested without a
screen: the default hangar, the mission list, the workshop upgrades, what a
mission result changes, and how a save slot is read, migrated and written.
`story.py` only draws these things and handles the menu input.

Save file: one JSON per slot (story_1.json ... story_3.json), version 3.
Durations (dome time and recharge) are stored in SECONDS, so they do not
depend on the frame rate. Version 2 files stored them in frames at 60 Hz.
"""
import json
import os
import time
import unicodedata

from safe_io import atomic_write_json, backup_unreadable
from settings import user_data_dir

SAVE_VERSION = 3
SLOT_COUNT = 3
MODES = ("normal", "veteran")
NAME_MAX = 12
# A failed mission (Normal mode) gains nothing and costs this share of the credits held.
# Veteran: a failure is a permanent death.
PENALTY_RATE = 0.20
NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- "

# Dome (Shield bubble): seconds. 2.0 s / 5.0 s is the arcade Shield.
DOME_DUR_START = 1.0
DOME_DUR_STEP = 0.5
DOME_DUR_MAX = 2.0
DOME_CD_START = 5.0
DOME_CD_STEP = 1.0
DOME_CD_MIN = 3.0
_EPS = 1e-6

# Chapter 1: main sorties are stage-1 birds only.
# Other hulls are met (and unlocked) in Bestiary nodes.
# Phoenix hull is not granted here — end of chapter 2.
MISSIONS = [
    {
        "id": "ch1_sortie",
        "title": "story_m_sortie",
        "blurb": "story_m_sortie_b",
        "need": None,
        "content": 1,
        "speed": 1.0,
        "unlock": ["ch1_sortie", "ch1_speed_80"],
        "log": "story_log_sortie",
    },
    {
        "id": "best_s2",
        "title": "story_m_best2",
        "blurb": "story_m_best2_b",
        "need": "ch1_sortie",
        "content": 2,
        "speed": 1.0,
        "unlock": ["bestiary_s2", "ch1_life_2"],
        "log": "story_log_best2",
    },
    {
        "id": "best_s3",
        "title": "story_m_best3",
        "blurb": "story_m_best3_b",
        "need": "bestiary_s2",
        "content": 3,
        "speed": 1.0,
        "unlock": ["bestiary_s3"],
        "log": "story_log_best3",
    },
    {
        "id": "best_s4",
        "title": "story_m_best4",
        "blurb": "story_m_best4_b",
        "need": "bestiary_s3",
        "content": 4,
        "speed": 1.0,
        "unlock": ["bestiary_s4"],
        "log": "story_log_best4",
    },
    {
        "id": "ch1_gate",
        "title": "story_m_gate",
        "blurb": "story_m_gate_b",
        "need": "bestiary_s4",
        "content": 1,
        "speed": 1.15,
        "unlock": ["ch1_clear", "dome_online"],
        "log": "story_log_gate",
    },
    {
        "id": "ch2_tease",
        "title": "story_m_ch2",
        "blurb": "story_m_ch2_b",
        "need": "ch1_clear",
        "content": 0,
        "speed": 1.0,
        "unlock": [],
        "log": "",
        "playable": False,
    },
]


# ---------------------------------------------------------------- save data
def story_path(slot=1):
    return os.path.join(user_data_dir(), "story_%d.json" % int(slot))


def default_state():
    return {
        "version": SAVE_VERSION,
        "act": 1,
        "name": "",
        "mode": "normal",
        "fallen": False,
        "saved_at": "",
        "credits": 0,
        "flags": {"bestiary_s1": True},
        "cleared": [],
        "slots": [
            {
                "id": "shield", "owned": True, "tint": "red",
                "lives": 1, "speed": 60, "dome": False,
                "dome_dur": DOME_DUR_START, "dome_cd": DOME_CD_START,
                "wall": "instant",
            },
            {
                "id": "phoenix", "owned": False, "tint": "argent",
                "lives": 1, "speed": 60, "phenix": False,
                "phenix_cap": 60, "wall": "instant",
            },
        ],
        "selected_slot": 0,
        "log": [],
    }


def _num(value, default):
    """A number from a save file; a damaged value falls back to `default`."""
    try:
        if isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def migrate_state(data):
    """Turn any saved dict (version 2 or 3) into a complete version-3 state.

    Unknown or damaged fields fall back to the defaults. Returns None when
    `data` is not a dict at all.
    """
    if not isinstance(data, dict):
        return None
    base = default_state()
    old_version = int(_num(data.get("version"), 2))
    for key in ("credits", "selected_slot"):
        if key in data:
            base[key] = data[key]
    # chapter (v2) became act (v3)
    base["act"] = data.get("act", data.get("chapter", 1))
    if isinstance(data.get("name"), str):
        base["name"] = data["name"]
    if data.get("mode") in MODES:
        base["mode"] = data["mode"]
    base["fallen"] = bool(data.get("fallen"))
    if isinstance(data.get("saved_at"), str):
        base["saved_at"] = data["saved_at"]
    flags = dict(base["flags"])
    if isinstance(data.get("flags"), dict):
        flags.update(data["flags"])
    base["flags"] = flags
    if isinstance(data.get("cleared"), list):
        base["cleared"] = list(data["cleared"])
    if isinstance(data.get("log"), list):
        base["log"] = list(data["log"])
    if isinstance(data.get("slots"), list) and data["slots"]:
        merged = []
        for i, sl in enumerate(data["slots"][:2]):
            proto = dict(base["slots"][i] if i < len(base["slots"]) else {})
            if isinstance(sl, dict):
                sl = dict(sl)
                if old_version < 3:
                    # v2 stored the dome times in frames at 60 Hz
                    for key in ("dome_dur", "dome_cd"):
                        if key in sl:
                            sl[key] = _num(sl[key], 0.0) / 60.0
                proto.update(sl)
            merged.append(proto)
        base["slots"] = merged
    base["version"] = SAVE_VERSION
    return base


def read_state(path):
    """Read one slot file without touching it. Returns (state, status).

    status is "missing" (no file), "ok", or "damaged" (not readable; state is None).
    """
    if not os.path.isfile(path):
        return None, "missing"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        state = migrate_state(data)
    except Exception:
        return None, "damaged"
    if state is None:
        return None, "damaged"
    return state, "ok"


def load_state(path):
    """Read one slot. Returns a state, or None when missing or unreadable.

    An unreadable file is set aside (backup_unreadable) so it is never lost.
    """
    state, status = read_state(path)
    if status == "damaged":
        backup_unreadable(path)
    return state


def save_state(path, state):
    state["version"] = SAVE_VERSION
    state["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    atomic_write_json(path, state)


# -------------------------------------------------------------- save slots
def format_date(saved_at):
    """'2026-10-08T11:21:05' -> '08/10/2026' ('' when unknown)."""
    try:
        y, m, d = str(saved_at)[:10].split("-")
        return "%02d/%02d/%04d" % (int(d), int(m), int(y))
    except (ValueError, TypeError):
        return ""


def slot_summary(slot):
    """What the slot list shows for slot 1..SLOT_COUNT."""
    state, status = read_state(story_path(slot))
    info = {"slot": slot, "status": status, "name": "", "mode": "normal",
            "act": 1, "date": "", "fallen": False}
    if state is not None:
        info.update(name=state.get("name") or "", mode=state.get("mode", "normal"),
                    act=int(_num(state.get("act"), 1)), date=format_date(state.get("saved_at")),
                    fallen=bool(state.get("fallen")))
    return info


def all_summaries():
    return [slot_summary(i) for i in range(1, SLOT_COUNT + 1)]


def clean_char(ch):
    """One typed character -> an allowed upper-case character, or ''."""
    if not ch:
        return ""
    ch = unicodedata.normalize("NFKD", ch)
    ch = "".join(c for c in ch if not unicodedata.combining(c)).upper()
    return ch if len(ch) == 1 and ch in NAME_CHARS else ""


def clean_name(raw):
    """A pilot name as stored: allowed characters only, single spaces, at most NAME_MAX."""
    chars = "".join(clean_char(c) for c in str(raw or ""))
    return " ".join(chars.split())[:NAME_MAX].strip()


def create_slot(slot, name, mode):
    """Start a new adventure in `slot` and save it. Returns the new state."""
    state = default_state()
    state["name"] = clean_name(name)
    state["mode"] = mode if mode in MODES else "normal"
    save_state(story_path(slot), state)
    return state


def delete_slot(slot):
    """Remove the save file of `slot`. True when a file was removed."""
    try:
        os.remove(story_path(slot))
        return True
    except OSError:
        return False


# Name entry: an on-screen keyboard, so the pad can do everything the keyboard does.
KEY_ROWS = [
    list("ABCDEFGHIJ"),
    list("KLMNOPQRST"),
    list("UVWXYZ0123"),
    ["4", "5", "6", "7", "8", "9", "-", "SPACE", "DEL", "OK"],
]


class NameEntry:
    """Pilot name being typed: text, plus a cursor on the on-screen keyboard."""

    def __init__(self, text=""):
        self.text = clean_name(text)
        self.row = 0
        self.col = 0

    @property
    def token(self):
        return KEY_ROWS[self.row][self.col]

    @property
    def name(self):
        return clean_name(self.text)

    def move(self, dx, dy):
        self.row = (self.row + dy) % len(KEY_ROWS)
        self.col = (self.col + dx) % len(KEY_ROWS[self.row])

    def type_char(self, ch):
        """A character typed on the real keyboard. True when it was accepted."""
        c = clean_char(ch)
        if not c or len(self.text) >= NAME_MAX:
            return False
        if c == " " and (not self.text or self.text.endswith(" ")):
            return False
        self.text += c
        return True

    def backspace(self):
        self.text = self.text[:-1]

    def press(self):
        """Validate the key under the cursor. Returns "ok" when the name is final,
        "empty" when OK was pressed with no name, else None."""
        tok = self.token
        if tok == "OK":
            return "ok" if self.name else "empty"
        if tok == "DEL":
            self.backspace()
        elif tok == "SPACE":
            self.type_char(" ")
        else:
            self.type_char(tok)
        return None


# ------------------------------------------------------------------ queries
def flag(state, name):
    return bool((state.get("flags") or {}).get(name))


def selected_slot(state):
    slots = state.get("slots") or []
    i = int(state.get("selected_slot", 0))
    if 0 <= i < len(slots):
        return slots[i]
    return None


def loadout(state):
    """Hull the mission actually launches. Locked Phoenix falls back to Shield."""
    slot = selected_slot(state) or {}
    if not slot.get("owned"):
        slots = state.get("slots") or []
        slot = next((s for s in slots if s.get("owned")), slot)
    sid = slot.get("id") if slot.get("id") in ("shield", "phoenix") else "shield"
    return {
        "ship_id": sid,
        "tint": slot.get("tint") or ("red" if sid == "shield" else "argent"),
        "lives": max(1, int(_num(slot.get("lives"), 1) or 1)),
        "speed_pct": max(40, min(100, int(_num(slot.get("speed"), 60) or 60))),
        "dome": bool(slot.get("dome")),
        "dome_dur": _num(slot.get("dome_dur"), DOME_DUR_START) or DOME_DUR_START,
        "dome_cd": _num(slot.get("dome_cd"), DOME_CD_START) or DOME_CD_START,
        "wall": slot.get("wall") or "instant",
    }


def mission_open(state, mission):
    if not mission:
        return False
    need = mission.get("need")
    if need and not flag(state, need):
        return False
    return True


def mission_playable(state, mission):
    if not mission_open(state, mission):
        return False
    if mission.get("playable") is False or int(mission.get("content") or 0) <= 0:
        return False
    return True


# ---------------------------------------------------------------- workshop
_NO_MIN = float("-inf")


def _step_to(slot, field, default, minimum, target):
    """Set `field` to `target` if it is currently in [minimum, target)."""
    cur = int(_num(slot.get(field), default))
    if cur < minimum or cur >= target:
        return False
    slot[field] = target
    return True


def _up_speed_80(slot):
    return _step_to(slot, "speed", 60, _NO_MIN, 80)


def _up_speed_100(slot):
    return _step_to(slot, "speed", 60, 80, 100)


def _up_lives_2(slot):
    return _step_to(slot, "lives", 1, _NO_MIN, 2)


def _up_lives_3(slot):
    return _step_to(slot, "lives", 1, 2, 3)


def _up_dome_dur(slot):
    if not slot.get("dome"):
        slot["dome"] = True
        slot["dome_dur"] = DOME_DUR_START
        slot["dome_cd"] = _num(slot.get("dome_cd"), DOME_CD_START) or DOME_CD_START
        return True
    dur = _num(slot.get("dome_dur"), DOME_DUR_START) or DOME_DUR_START
    if dur >= DOME_DUR_MAX - _EPS:
        return False
    slot["dome_dur"] = min(DOME_DUR_MAX, dur + DOME_DUR_STEP)
    return True


def _up_dome_lat(slot):
    if not slot.get("dome"):
        return False
    cd = _num(slot.get("dome_cd"), DOME_CD_START) or DOME_CD_START
    if cd <= DOME_CD_MIN + _EPS:
        return False
    slot["dome_cd"] = max(DOME_CD_MIN, cd - DOME_CD_STEP)
    return True


def _up_wall_slow(slot):
    if not slot.get("dome") or slot.get("wall") != "instant":
        return False
    slot["wall"] = "slow"
    return True


def _up_wall_immune(slot):
    if not slot.get("dome") or slot.get("wall") != "slow":
        return False
    slot["wall"] = "immune"
    return True


def _speed(slot):
    return int(_num(slot.get("speed"), 60))


def _lives(slot):
    return int(_num(slot.get("lives"), 1))


def _st_speed_80(slot):
    return "owned" if _speed(slot) >= 80 else None


def _st_speed_100(slot):
    if _speed(slot) >= 100:
        return "owned"
    if _speed(slot) < 80:
        return "need_prev"
    return None


def _st_lives_2(slot):
    return "owned" if _lives(slot) >= 2 else None


def _st_lives_3(slot):
    if _lives(slot) >= 3:
        return "owned"
    if _lives(slot) < 2:
        return "need_prev"
    return None


def _st_dome_dur(slot):
    if slot.get("dome") and (_num(slot.get("dome_dur"), 0.0) or 0.0) >= DOME_DUR_MAX - _EPS:
        return "owned"
    return None


def _st_dome_lat(slot):
    if not slot.get("dome"):
        return "need_dome"
    cd = _num(slot.get("dome_cd"), DOME_CD_START) or DOME_CD_START
    if cd <= DOME_CD_MIN + _EPS:
        return "owned"
    return None


def _st_wall_slow(slot):
    if slot.get("wall") in ("slow", "immune"):
        return "owned"
    if not slot.get("dome"):
        return "need_dome"
    return None


def _st_wall_immune(slot):
    if slot.get("wall") == "immune":
        return "owned"
    if slot.get("wall") != "slow":
        return "need_prev"
    return None


# id, i18n label, cost, flag required, apply(slot) -> bool, status(slot) -> str|None
UPGRADES = [
    ("speed_80", "story_shop_speed80", 400, "ch1_speed_80", _up_speed_80, _st_speed_80),
    ("speed_100", "story_shop_speed100", 700, "ch1_speed_80", _up_speed_100, _st_speed_100),
    ("lives_2", "story_shop_lives2", 600, "ch1_life_2", _up_lives_2, _st_lives_2),
    ("lives_3", "story_shop_lives3", 900, "ch1_life_2", _up_lives_3, _st_lives_3),
    ("dome_dur", "story_shop_dome", 800, "dome_online", _up_dome_dur, _st_dome_dur),
    ("dome_lat", "story_shop_latency", 800, "dome_online", _up_dome_lat, _st_dome_lat),
    ("wall_slow", "story_shop_wall_slow", 1000, "dome_online", _up_wall_slow, _st_wall_slow),
    ("wall_immune", "story_shop_wall_immune", 1400, "dome_online", _up_wall_immune, _st_wall_immune),
]

# id, i18n label, cost, flag required before the row is buyable
SHOP = [(u[0], u[1], u[2], u[3]) for u in UPGRADES]

_STATUS_KEYS = {
    "owned": "story_owned",
    "need_prev": "story_need_prev",
    "need_dome": "story_need_dome",
}


def _upgrade(sid):
    return next((u for u in UPGRADES if u[0] == sid), None)


def upgrade_note(state, sid):
    """i18n key shown on a workshop row instead of its price, or None.

    "story_locked" when the story flag is missing, "story_owned" when already
    bought, "story_need_prev" / "story_need_dome" when a step is missing.
    """
    up = _upgrade(sid)
    if up is None:
        return None
    if up[3] and not flag(state, up[3]):
        return "story_locked"
    slot = selected_slot(state) or {}
    return _STATUS_KEYS.get(up[5](slot))


def buy(state, sid):
    """Buy one upgrade for the selected hull. True when it was bought."""
    up = _upgrade(sid)
    if up is None:
        return False
    if up[3] and not flag(state, up[3]):
        return False
    slot = selected_slot(state)
    if slot is None or not slot.get("owned"):
        return False
    if int(state.get("credits", 0)) < up[2]:
        return False
    if not up[4](slot):
        return False
    state["credits"] = int(state.get("credits", 0)) - up[2]
    return True


# ----------------------------------------------------------------- results
def failure_penalty(credits):
    """Points lost after a failed mission in Normal mode: PENALTY_RATE of the credits held."""
    credits = max(0, int(_num(credits, 0)))
    return int(credits * PENALTY_RATE + 0.5)


def record_result(state, mission_id, score, cleared):
    """Apply the end of a mission.

    Cleared: the score is banked as hangar credits, unlock flags and journal line.
    Failed, Normal mode: nothing is gained and 20 % of the credits held are lost.
    Failed, Veteran mode: the pilot falls, the save becomes a memorial.

    Returns {"score", "cleared", "first", "lost", "fallen"}. The journal stores a
    text KEY, not the translated text, so it follows the player's language.
    """
    score = max(0, int(score or 0))
    res = {"score": score, "cleared": bool(cleared), "first": False, "lost": 0, "fallen": False}
    if not cleared:
        if state.get("mode") == "veteran":
            state["fallen"] = True
            res["fallen"] = True
        else:
            credits = max(0, int(state.get("credits", 0)))
            res["lost"] = failure_penalty(credits)
            state["credits"] = credits - res["lost"]
        return res
    state["credits"] = int(state.get("credits", 0)) + score
    mission = next((m for m in MISSIONS if m["id"] == mission_id), None)
    if mission:
        flags = state.setdefault("flags", {})
        for name in mission.get("unlock") or []:
            flags[name] = True
        cleared_ids = state.setdefault("cleared", [])
        res["first"] = mission_id not in cleared_ids
        if res["first"]:
            cleared_ids.append(mission_id)
            state.setdefault("log", []).append({"key": mission.get("log") or "story_log_clear"})
    return res


def log_text(entry, translate):
    """Text of one journal line (new entries are {"key": ...}, old ones plain text)."""
    if isinstance(entry, dict):
        return translate(str(entry.get("key") or "story_log_clear"))
    return str(entry)
