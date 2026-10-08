"""
Adventure rules and save data (no drawing, no window).

Everything the adventure *decides* lives here so it can be tested without a
screen: the default hangar, the mission list, the workshop upgrades, what a
mission result changes, and how a save slot is read, migrated and written.
`story.py` only draws these things and handles the menu input.

Save file: one JSON per slot (story_1.json ... story_3.json), version 4.
Durations (dome time and recharge) are stored in SECONDS, so they do not
depend on the frame rate. Version 2 files stored them in frames at 60 Hz.
Version 4 is the Act 1 hangar: the Shield starts at 40 % speed with one life,
no dome and deadly walls (see ACT_CAPS and UPGRADES).
"""
import json
import os
import time
import unicodedata

from safe_io import atomic_write_json, backup_unreadable
from settings import user_data_dir, ENEMY_VETERAN_BONUS

SAVE_VERSION = 4
SLOT_COUNT = 3
MODES = ("normal", "veteran")
NAME_MAX = 12
# A failed mission (Normal mode) gains nothing and costs this share of the credits held.
# Veteran: a failure is a permanent death.
PENALTY_RATE = 0.05
NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- "

# Speed steps (% of the arcade ship) and what each act allows the workshop to reach.
SPEED_START = 40
ACT_CAPS = {
    1: {"speed": 80, "lives": 2},      # Act 1: about 80 % of the arcade ship, no dome
    2: {"speed": 80, "lives": 2},      # Act 2: the same, and the Phenix joins the hangar
}

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
        "hunt": True,
        "title": "story_m_sortie",
        "blurb": "story_m_sortie_b",
        "need": None,
        "content": 1,
        "speed": 1.0,
        "unlock": ["ch1_sortie", "ch1_speed"],
        "log": "story_log_sortie",
    },
    {
        "id": "best_s2",
        "hunt": True,
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
        "hunt": True,
        "title": "story_m_best3",
        "blurb": "story_m_best3_b",
        "need": "bestiary_s2",
        "content": 3,
        "speed": 1.0,
        "unlock": ["bestiary_s3", "ch1_wall"],
        "log": "story_log_best3",
    },
    {
        "id": "best_s4",
        "hunt": True,
        "title": "story_m_best4",
        "blurb": "story_m_best4_b",
        "need": "bestiary_s3",
        "content": 4,
        "speed": 1.0,
        "unlock": ["bestiary_s4"],
        "log": "story_log_best4",
    },
    # The dome series: each mission opens the next one and can be flown only once.
    # `waves` are arcade stage numbers (1, 6, 11 = the same wave at 1.0x, 1.1x, 1.2x speed).
    {
        "id": "dome_1",
        "acts": (1,),
        "title": "story_m_dome1",
        "blurb": "story_m_dome1_b",
        "need": "bestiary_s4",
        "content": 1,
        "waves": [1, 6, 11],
        "speed": 1.0,
        "once": True,
        "unlock": ["dome_s1"],
        "log": "story_log_dome1",
    },
    {
        "id": "dome_2",
        "acts": (1,),
        "title": "story_m_dome2",
        "blurb": "story_m_dome2_b",
        "need": "dome_s1",
        "content": 2,
        "waves": [2, 7, 12],
        "speed": 1.0,
        "once": True,
        "unlock": ["dome_s2"],
        "log": "story_log_dome2",
    },
    {
        "id": "dome_3",
        "acts": (1,),
        "title": "story_m_dome3",
        "blurb": "story_m_dome3_b",
        "need": "dome_s2",
        "content": 3,
        "waves": [3, 8, 13],
        "speed": 1.0,
        "once": True,
        "unlock": ["dome_s3"],
        "log": "story_log_dome3",
    },
    {
        "id": "dome_4",
        "acts": (1,),
        "title": "story_m_dome4",
        "blurb": "story_m_dome4_b",
        "need": "dome_s3",
        "content": 4,
        "waves": [4, 9, 14],
        "speed": 1.0,
        "once": True,
        "unlock": ["dome_s4"],
        "log": "story_log_dome4",
    },
    {
        # all four enemies at once (levels 11 to 14), replaced as they fall; opens the dome
        "id": "dome_5",
        "acts": (1,),
        "title": "story_m_dome5",
        "blurb": "story_m_dome5_b",
        "need": "dome_s4",
        "content": 1,
        "swarm": True,
        "stage": 11,
        "speed": 1.0,
        "once": True,
        "unlock": ["dome_s5", "dome_online"],
        "log": "story_log_dome5",
    },
    {
        # a full run of the arcade levels 11 to 15; the death of the boss starts Act 2
        "id": "act2_gate",
        "acts": (1,),
        "title": "story_m_gate2",
        "blurb": "story_m_gate2_b",
        "need": "dome_s5",
        "content": 1,
        "waves": [11, 12, 13, 14, 15],
        "speed": 1.0,
        "once": True,
        "unlock": ["act2"],
        "act": 2,
        "log": "story_log_gate2",
    },
    {
        "id": "ch2_tease",
        "acts": (1,),
        "title": "story_m_ch2",
        "blurb": "story_m_ch2_b",
        "need": "act2",
        "content": 0,
        "speed": 1.0,
        "unlock": [],
        "log": "",
        "playable": False,
    },
    # Act 2: the Phenix series. Five chained missions, flown once each (arcade levels 16 and up,
    # x1.3 speed). The last one hands over the Phenix and opens its workshop.
    {
        "id": "phenix_1",
        "acts": (2,),
        "title": "story_m_ph1",
        "blurb": "story_m_ph1_b",
        "need": "act2",
        "content": 1,
        "waves": [16, 17],
        "speed": 1.0,
        "once": True,
        "unlock": ["phenix_s1"],
        "log": "story_log_ph1",
    },
    {
        "id": "phenix_2",
        "acts": (2,),
        "title": "story_m_ph2",
        "blurb": "story_m_ph2_b",
        "need": "phenix_s1",
        "content": 1,
        "swarm": True,
        "stage": 16,
        "speed": 1.0,
        "once": True,
        "unlock": ["phenix_s2"],
        "log": "story_log_ph2",
    },
    {
        "id": "phenix_3",
        "acts": (2,),
        "title": "story_m_ph3",
        "blurb": "story_m_ph3_b",
        "need": "phenix_s2",
        "content": 3,
        "waves": [18, 19],
        "speed": 1.0,
        "once": True,
        "unlock": ["phenix_s3"],
        "log": "story_log_ph3",
    },
    {
        "id": "phenix_4",
        "acts": (2,),
        "title": "story_m_ph4",
        "blurb": "story_m_ph4_b",
        "need": "phenix_s3",
        "content": 1,
        "waves": [16, 17, 18, 19],
        "speed": 1.0,
        "once": True,
        "unlock": ["phenix_s4"],
        "log": "story_log_ph4",
    },
    {
        # a full run of the arcade levels 16 to 20: the boss guards the Phenix
        "id": "phenix_5",
        "acts": (2,),
        "title": "story_m_ph5",
        "blurb": "story_m_ph5_b",
        "need": "phenix_s4",
        "content": 1,
        "waves": [16, 17, 18, 19, 20],
        "speed": 1.0,
        "once": True,
        "unlock": ["phenix_s5", "phenix_owned"],
        "grant_hull": "phoenix",
        "log": "story_log_ph5",
    },

    # Act 2: the paint series. Three optional missions, flown in order; when the third is won the
    # paint shop opens for ONE change of colour. The whole series can be flown again (harder each
    # time, like the Bestiary sorties) to earn another change. `waves` are the level-1 stages.
    {
        "id": "paint_1",
        "acts": (2,),
        "paint": 1,
        "title": "story_m_pt1",
        "blurb": "story_m_pt1_b",
        "need": "act2",
        "content": 1,
        "waves": [6, 7],
        "speed": 1.0,
        "unlock": [],
        "log": "story_log_pt1",
    },
    {
        "id": "paint_2",
        "acts": (2,),
        "paint": 2,
        "title": "story_m_pt2",
        "blurb": "story_m_pt2_b",
        "need": "act2",
        "content": 3,
        "waves": [8, 9],
        "speed": 1.0,
        "unlock": [],
        "log": "story_log_pt2",
    },
    {
        "id": "paint_3",
        "acts": (2,),
        "paint": 3,
        "title": "story_m_pt3",
        "blurb": "story_m_pt3_b",
        "need": "act2",
        "content": 1,
        "waves": [6, 7, 8, 9],
        "speed": 1.0,
        "unlock": [],
        "log": "story_log_pt3",
    },
]


# ---------------------------------------------------------------- bestiary
# The enemies of the Adventure, in the order they are listed. `stage` is the content stage
# that spawns them. An entry shows up in the Bestiary once the pilot has destroyed one.
BESTIARY = [
    {"id": "bird1", "stage": 1, "name": "story_b_bird1", "text": "story_b_bird1_t"},
    {"id": "bird2", "stage": 2, "name": "story_b_bird2", "text": "story_b_bird2_t"},
    {"id": "garg3", "stage": 3, "name": "story_b_garg3", "text": "story_b_garg3_t"},
    {"id": "garg4", "stage": 4, "name": "story_b_garg4", "text": "story_b_garg4_t"},
]
# What each tier shows, by number of enemies of that kind destroyed:
# (picture, picture twice as big, animation, presentation text, bonus points).
BEST_TIERS_COMMON = (1, 50, 100, 150, 200)
BEST_TIERS_BOSS = (1, 2, 3, 5, 10)
BEST_SEEN = 1                          # first tier of both tables
BESTIARY_BONUS = ENEMY_VETERAN_BONUS   # common enemy: same bonus as Veteran difficulty
BOSS_BONUS = 1000                      # boss: extra points per boss destroyed


def enemy_kind(stage):
    """Bestiary id of an enemy spawned by content stage `stage`."""
    stage = int(_num(stage, 1))
    if stage >= 4:
        return "garg4"
    if stage == 3:
        return "garg3"
    return "bird2" if stage == 2 else "bird1"


def encounters(state, kind):
    """How many enemies of this kind the pilot has destroyed so far (saved total)."""
    data = state.get("bestiary")
    if not isinstance(data, dict):
        return 0
    return max(0, int(_num(data.get(kind), 0)))


def _entry(kind):
    return next((e for e in BESTIARY if e["id"] == kind), None)


def is_boss(kind):
    entry = _entry(kind)
    return bool(entry and entry.get("boss"))


def bestiary_bonus(kind):
    """Extra points per enemy of this kind once its last tier is reached."""
    return BOSS_BONUS if is_boss(kind) else BESTIARY_BONUS


def best_tiers(count, boss=False):
    """What an entry shows after `count` enemies destroyed (boss: the short table)."""
    count = int(_num(count, 0))
    seen, zoom, anim, text, bonus = BEST_TIERS_BOSS if boss else BEST_TIERS_COMMON
    return {
        "seen": count >= seen,
        "zoom": count >= zoom,
        "anim": count >= anim,
        "text": count >= text,
        "bonus": count >= bonus,
    }


def bestiary_entries(state):
    """The entries the pilot has unlocked, as (entry, count), in listing order."""
    out = []
    for entry in BESTIARY:
        n = encounters(state, entry["id"])
        if n >= BEST_SEEN:
            out.append((entry, n))
    return out


def kill_bonus(state, kind, run_kills):
    """Extra points for a kill once the last tier is reached (saved total + this run)."""
    entry = _entry(kind)
    if entry is None:
        return 0
    total = encounters(state, kind) + max(0, int(_num(run_kills, 0)))
    return bestiary_bonus(kind) if best_tiers(total, bool(entry.get("boss")))["bonus"] else 0


def record_kills(state, kills):
    """Add the enemies destroyed during a mission ({kind: n}) to the Bestiary."""
    if not isinstance(kills, dict):
        return
    data = state.get("bestiary")
    if not isinstance(data, dict):
        data = state["bestiary"] = {}
    known = {e["id"] for e in BESTIARY}
    for kind, n in kills.items():
        if kind in known:
            data[kind] = encounters(state, kind) + max(0, int(_num(n, 0)))


# ---------------------------------------------------------------- hunt missions
# The four Act 1 sorties that each face one kind of enemy ("hunt" missions) can be flown again
# as often as the pilot likes. The journal keeps the total of enemies destroyed in all their runs.
def mission_by_id(mission_id):
    return next((m for m in MISSIONS if m["id"] == mission_id), None)


def is_hunt(mission):
    return bool(mission and mission.get("hunt"))


def mission_total_kills(state, mission_id):
    """Enemies destroyed in every run of this mission so far (all outcomes)."""
    data = state.get("mission_kills")
    if not isinstance(data, dict):
        return 0
    return max(0, int(_num(data.get(mission_id), 0)))


def hunt_level(state, mission_id):
    """Level of a hunt mission: 1 at first, one more after each victory (1, 2, 3...).

    A save from before levels existed counts a cleared mission as won at least once.
    """
    data = state.get("mission_clears")
    won = max(0, int(_num(data.get(mission_id), 0))) if isinstance(data, dict) else 0
    if mission_id in (state.get("cleared") or []):
        won = max(won, 1)
    return 1 + won


def hunt_stage(mission, level):
    """Arcade stage a hunt mission plays at `level`: level 2 is the same wave as at stage +5 (x1.1 speed)."""
    return max(1, int(_num((mission or {}).get("content"), 1))) + 5 * (max(1, int(_num(level, 1))) - 1)


# ---------------------------------------------------------------- paint series
# Three optional missions of Act 2. The third one opens the paint shop for ONE change of colour of the
# Shield. The series can be flown again, as a whole only, to earn another change; each pass is harder.
PAINT_TINTS = ("red", "green", "violet")
PAINT_STEPS = 3


def paint_state(state):
    """The paint series of a save, cleaned: {"step": 0..2 missions won in this pass, "runs": passes
    finished, "token": a colour change is waiting}."""
    data = state.get("paint")
    if not isinstance(data, dict):
        data = {}
    return {
        "step": max(0, min(PAINT_STEPS - 1, int(_num(data.get("step"), 0)))),
        "runs": max(0, int(_num(data.get("runs"), 0))),
        "token": bool(data.get("token")),
    }


def is_paint(mission):
    return bool(mission and mission.get("paint"))


def paint_level(state):
    """Level of the paint series: 1 at first, one more after each full pass (1, 2, 3...)."""
    return 1 + paint_state(state)["runs"]


def paint_waves(mission, level):
    """Arcade stages of a paint mission at `level`: every wave comes 5 stages later per level."""
    shift = 5 * (max(1, int(_num(level, 1))) - 1)
    return [w + shift for w in mission_waves(mission)]


def mission_level(state, mission):
    """The level shown for a mission (hunts and the paint series), or None for the others."""
    if is_hunt(mission):
        return hunt_level(state, mission["id"])
    if is_paint(mission):
        return paint_level(state)
    return None


def mission_done(state, mission):
    """Has the mission been won (for a paint mission: in the pass under way)?"""
    if is_paint(mission):
        return paint_state(state)["step"] >= int(mission["paint"])
    return bool(mission) and mission.get("id") in (state.get("cleared") or [])


def paint_change(state, tint):
    """Spend the waiting colour change on the Shield. False when there is none, the colour is not
    one of the three, or it is the colour the Shield already wears (nothing is spent then)."""
    shield = next((sl for sl in state.get("slots") or [] if sl.get("id") == "shield"), None)
    if shield is None or tint not in PAINT_TINTS or not paint_state(state)["token"]:
        return False
    if (shield.get("tint") or "red") == tint:
        return False
    shield["tint"] = tint
    state["paint"] = dict(paint_state(state), token=False)
    return True


def record_mission_kills(state, mission_id, kills):
    """Add the enemies destroyed during one run to the total of a hunt mission."""
    if not is_hunt(mission_by_id(mission_id)) or not isinstance(kills, dict):
        return
    known = {e["id"] for e in BESTIARY}
    added = sum(max(0, int(_num(n, 0))) for kind, n in kills.items() if kind in known)
    if added <= 0:
        return
    data = state.get("mission_kills")
    if not isinstance(data, dict):
        data = state["mission_kills"] = {}
    data[mission_id] = mission_total_kills(state, mission_id) + added


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
                "lives": 1, "speed": SPEED_START, "dome": False,
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
        "bestiary": {},          # enemies destroyed so far, by kind
        "mission_kills": {},     # enemies destroyed in all the runs of a hunt mission, by mission id
        "mission_clears": {},    # how many times a hunt mission was won (its level is one more)
        "paint": {"step": 0, "runs": 0, "token": False},   # the Act 2 paint series (see paint_state)
    }


def _num(value, default):
    """A number from a save file; a damaged value falls back to `default`."""
    try:
        if isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_act1_hangar(sl):
    """Version 3 -> 4 for one saved hull: the speed ladder moved down one step
    (60/80/100 became 40/60/80), lives stop at 2, the dome is not part of Act 1 and
    the "slow" wall (harmless) becomes the arcade rule."""
    speed = int(_num(sl.get("speed"), 60))
    if "speed" in sl:
        sl["speed"] = {60: 40, 80: 60, 100: 80}.get(speed, max(SPEED_START, min(80, speed)))
    if "lives" in sl:
        sl["lives"] = max(1, min(2, int(_num(sl.get("lives"), 1))))
    if sl.get("id") == "shield":
        sl["dome"] = False
        sl["dome_dur"] = DOME_DUR_START
        sl["dome_cd"] = DOME_CD_START
        if sl.get("wall") == "immune":
            sl["wall"] = "slow"


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
    if isinstance(data.get("bestiary"), dict):
        record_kills(base, {k: v for k, v in data["bestiary"].items()})
    if isinstance(data.get("mission_clears"), dict):
        for mid, n in data["mission_clears"].items():
            if isinstance(mid, str) and is_hunt(mission_by_id(mid)):
                base["mission_clears"][mid] = max(0, int(_num(n, 0)))
    if isinstance(data.get("paint"), dict):
        base["paint"] = paint_state(data)
    if isinstance(data.get("mission_kills"), dict):
        for mid, n in data["mission_kills"].items():
            if isinstance(mid, str) and is_hunt(mission_by_id(mid)):
                base["mission_kills"][mid] = max(0, int(_num(n, 0)))
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
                if old_version < 4:
                    _to_act1_hangar(sl)
                proto.update(sl)
            merged.append(proto)
        base["slots"] = merged
    if old_version < 4:
        flags = base["flags"]
        if flags.pop("ch1_speed_80", False):
            flags["ch1_speed"] = True
        if flags.get("bestiary_s3"):
            flags["ch1_wall"] = True
        flags.pop("dome_online", None)
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


# ------------------------------------------------------------------- intro
# The story told before the first mission: (picture in assets/story, text key).
# The first three slides are the same for everybody. The last one depends on the mode:
# in Veteran mode Professor Kamarasov died before finishing the quantum anchor.
INTRO_SLIDES = [
    ("huygens", "story_intro_1"),
    ("huygens_destroyed", "story_intro_2"),
    ("phobos", "story_intro_3"),
]
INTRO_LAST = {
    "normal": ("kamarasov", "story_intro_4"),
    "veteran": ("kamarasov_veteran", "story_intro_4v"),
}
INTRO_FLAG = "intro_seen"


def intro_slides(mode):
    """The slides to show for `mode`: a list of (picture name, text key)."""
    return INTRO_SLIDES + [INTRO_LAST.get(mode, INTRO_LAST["normal"])]


def intro_lines(translate, key, name):
    """Text of one slide as a list of lines ("" = a pause). {name} becomes the pilot's name."""
    text = str(translate(key)).replace("{name}", clean_name(name) or "?")
    return text.split("\n")


def intro_seen(state):
    return flag(state, INTRO_FLAG)


def mark_intro_seen(state):
    state.setdefault("flags", {})[INTRO_FLAG] = True


PHENIX_CAP_START = 60
PHENIX_CAP_MAX = 100


def phenix_cap(slot):
    """Share (%) of the arcade Phenix form the pilot gets: 60 at first, 80 after the workshop, 100 in Act 3."""
    return max(PHENIX_CAP_START, min(PHENIX_CAP_MAX, int(_num((slot or {}).get("phenix_cap"), PHENIX_CAP_START))))


def selected_slot(state):
    slots = state.get("slots") or []
    i = int(state.get("selected_slot", 0))
    if 0 <= i < len(slots):
        return slots[i]
    return None


def _hull_tint(sid, tint):
    """Colour a hull flies with: the Shield wears red / green / violet, the Phenix argent."""
    if sid == "shield":
        return tint if tint in PAINT_TINTS else "red"
    return tint if tint in ("argent", "blue", "gold") else "argent"


def loadout(state):
    """Hull the mission actually launches. Locked Phoenix falls back to Shield."""
    slot = selected_slot(state) or {}
    if not slot.get("owned"):
        slots = state.get("slots") or []
        slot = next((s for s in slots if s.get("owned")), slot)
    sid = slot.get("id") if slot.get("id") in ("shield", "phoenix") else "shield"
    fallback_speed = SPEED_START if sid == "shield" else 60
    return {
        "ship_id": sid,
        "tint": _hull_tint(sid, slot.get("tint")),
        "lives": max(1, int(_num(slot.get("lives"), 1) or 1)),
        "speed_pct": max(SPEED_START, min(100, int(_num(slot.get("speed"), fallback_speed) or fallback_speed))),
        "dome": bool(slot.get("dome")),
        "dome_dur": _num(slot.get("dome_dur"), DOME_DUR_START) or DOME_DUR_START,
        "dome_cd": _num(slot.get("dome_cd"), DOME_CD_START) or DOME_CD_START,
        "wall": slot.get("wall") or "instant",
        "phenix_pct": phenix_cap(slot),
    }


def mission_waves(mission):
    """Arcade stage numbers a mission flies one after the other (empty: one wave of `content`)."""
    waves = (mission or {}).get("waves")
    if not isinstance(waves, (list, tuple)):
        return []
    return [max(1, int(_num(w, 1))) for w in waves]


def mission_in_act(mission, act):
    """Is this mission on the map of act `act`? Missions without `acts` (the hunts) are on every map."""
    acts = (mission or {}).get("acts")
    return not acts or int(_num(act, 1)) in acts


def visible_missions(state, cheat=False):
    """The missions the map lists: those of the current act. The UNLK cheat lists every mission."""
    if cheat:
        return list(MISSIONS)
    act = int(_num(state.get("act"), 1))
    return [m for m in MISSIONS if mission_in_act(m, act)]


def mission_open(state, mission):
    if not mission:
        return False
    need = mission.get("need")
    if need and not flag(state, need):
        return False
    if is_paint(mission) and paint_state(state)["step"] < int(mission["paint"]) - 1:
        return False                       # the paint series is flown in order
    return True


def mission_playable(state, mission, cheat=False):
    """Can this mission be launched? `cheat` (the UNLK code) skips every unlock rule."""
    if not mission:
        return False
    if mission.get("playable") is False or int(mission.get("content") or 0) <= 0:
        return False
    if cheat:
        return True
    if not mission_open(state, mission):
        return False
    if mission.get("once") and mission.get("id") in (state.get("cleared") or []):
        return False                       # a story mission is flown once; hunts stay replayable
    if is_paint(mission) and paint_state(state)["step"] != int(mission["paint"]) - 1:
        return False                       # only the next mission of the pass; a won one waits for the next pass
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


def _up_speed_60(slot):
    return _step_to(slot, "speed", SPEED_START, _NO_MIN, 60)


def _up_speed_80(slot):
    return _step_to(slot, "speed", SPEED_START, 60, 80)


def _up_speed_100(slot):
    return _step_to(slot, "speed", SPEED_START, 80, 100)


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


def _up_dome_on(slot):
    """The first dome upgrade: the Shield gets its dome (1 s, the shortest one)."""
    if slot.get("dome") or slot.get("id") == "phoenix":
        return False                          # the dome is the Shield's
    slot["dome"] = True
    slot["dome_dur"] = DOME_DUR_START
    slot["dome_cd"] = _num(slot.get("dome_cd"), DOME_CD_START) or DOME_CD_START
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
    """Walls: touching the edge kills at once -> the arcade rule (slowdown, then death)."""
    if slot.get("wall") != "instant":
        return False
    slot["wall"] = "slow"
    return True


def _up_wall_immune(slot):
    if slot.get("wall") != "slow":
        return False
    slot["wall"] = "immune"
    return True


def _up_cap_80(slot):
    """Phenix only: the Phenix form lasts 80 % of the arcade one (60 % at first)."""
    if slot.get("id") != "phoenix" or phenix_cap(slot) >= 80:
        return False
    slot["phenix_cap"] = 80
    return True


def _st_cap_80(slot):
    return "owned" if phenix_cap(slot) >= 80 else None


def _speed(slot):
    return int(_num(slot.get("speed"), SPEED_START))


def _lives(slot):
    return int(_num(slot.get("lives"), 1))


def _st_speed_60(slot):
    return "owned" if _speed(slot) >= 60 else None


def _st_speed_80(slot):
    if _speed(slot) >= 80:
        return "owned"
    if _speed(slot) < 60:
        return "need_prev"
    return None


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


def _st_dome_on(slot):
    return "owned" if slot.get("dome") else None


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
    return "owned" if slot.get("wall") in ("slow", "immune") else None


def _st_wall_immune(slot):
    if slot.get("wall") == "immune":
        return "owned"
    if slot.get("wall") != "slow":
        return "need_prev"
    return None


# id, i18n label, cost, flag required, apply(slot) -> bool, status(slot) -> str|None, act
# `act` is the act whose workshop sells it. Only Act 1 is built so far: the dome comes with
# its own series of quests (nothing sets "dome_online" yet), the rest is for Acts 2 and 3.
UPGRADES = [
    ("speed_60", "story_shop_speed60", 300, "ch1_speed", _up_speed_60, _st_speed_60, 1),
    ("speed_80", "story_shop_speed80", 800, "ch1_speed", _up_speed_80, _st_speed_80, 1),
    ("lives_2", "story_shop_lives2", 2000, "ch1_life_2", _up_lives_2, _st_lives_2, 1),
    ("wall_slow", "story_shop_wall_slow", 1000, "ch1_wall", _up_wall_slow, _st_wall_slow, 1),
    ("dome_on", "story_shop_dome_on", 800, "dome_online", _up_dome_on, _st_dome_on, 1),
    ("phenix_cap_80", "story_shop_phenix80", 1000, "phenix_owned", _up_cap_80, _st_cap_80, 2),
    ("speed_100", "story_shop_speed100", 1000, "ch3_open", _up_speed_100, _st_speed_100, 3),
    ("lives_3", "story_shop_lives3", 900, "ch3_open", _up_lives_3, _st_lives_3, 3),
    ("dome_dur", "story_shop_dome", 800, "dome_online", _up_dome_dur, _st_dome_dur, 2),
    ("dome_lat", "story_shop_latency", 800, "dome_online", _up_dome_lat, _st_dome_lat, 2),
    ("wall_immune", "story_shop_wall_immune", 1400, "ch3_open", _up_wall_immune, _st_wall_immune, 3),
]

# What the workshop shows in Act 1: id, i18n label, cost, flag required before it is buyable
SHOP = [(u[0], u[1], u[2], u[3]) for u in UPGRADES if u[6] == 1]


# What the workshop sells for the Phenix (Act 2): the same hull upgrades, no dome, plus its own gauge.
PAINT_ROW = ("paint", "story_shop_paint", 0, None)
PHENIX_SHOP_IDS = ("speed_80", "lives_2", "wall_slow", "phenix_cap_80")


def shop_for(state):
    """Workshop rows of the selected hull: (id, label, cost, flag required)."""
    slot = selected_slot(state) or {}
    if slot.get("id") == "phoenix":
        return [(u[0], u[1], u[2], u[3]) for sid in PHENIX_SHOP_IDS for u in UPGRADES if u[0] == sid]
    rows = list(SHOP)
    if int(_num(state.get("act"), 1)) >= 2:
        rows.append(PAINT_ROW)                 # the paint shop: free, but one change per finished series
    return rows


def act_caps(state):
    """Highest speed and lives the workshop of the current act allows."""
    return ACT_CAPS.get(int(_num(state.get("act"), 1)), ACT_CAPS[1])

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


def record_result(state, mission_id, score, cleared, kills=None):
    """Apply the end of a mission.

    Cleared: the score is banked as hangar credits, unlock flags and journal line.
    Failed, Normal mode: nothing is gained and 5 % of the credits held are lost.
    Failed, Veteran mode: the pilot falls, the save becomes a memorial.
    `kills` ({kind: n}, the enemies destroyed) always goes into the Bestiary, win or lose.

    Returns {"score", "cleared", "first", "lost", "fallen"}. The journal stores a
    text KEY, not the translated text, so it follows the player's language.
    """
    score = max(0, int(score or 0))
    res = {"score": score, "cleared": bool(cleared), "first": False, "lost": 0, "fallen": False, "act": 0}
    record_kills(state, kills)            # the enemies met count whatever the outcome
    record_mission_kills(state, mission_id, kills)
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
    if is_paint(mission):
        paint = paint_state(state)
        if paint["step"] == int(mission["paint"]) - 1:        # in order only (the cheat can fly any)
            paint["step"] += 1
            if paint["step"] >= PAINT_STEPS:                  # the pass is done: one colour change, a harder series
                paint.update(step=0, runs=paint["runs"] + 1, token=True)
                res["paint"] = True
            state["paint"] = paint
    if is_hunt(mission):
        state["mission_clears"] = dict(state.get("mission_clears") or {})
        # the level before this win is also the number of wins after it
        state["mission_clears"][mission_id] = hunt_level(state, mission_id)
    if mission:
        flags = state.setdefault("flags", {})
        for name in mission.get("unlock") or []:
            flags[name] = True
        if mission.get("grant_hull"):
            for sl in state.get("slots") or []:
                if sl.get("id") == mission["grant_hull"] and not sl.get("owned"):
                    sl["owned"] = True
                    res["hull"] = mission["grant_hull"]
        act = int(_num(mission.get("act"), 0))
        if act > int(_num(state.get("act"), 1)):
            state["act"] = act                       # the end of an act starts the next one
            res["act"] = act
        cleared_ids = state.setdefault("cleared", [])
        res["first"] = mission_id not in cleared_ids
        if res["first"]:
            cleared_ids.append(mission_id)
            state.setdefault("log", []).append({"key": mission.get("log") or "story_log_clear"})
    return res


def journal_entries(state):
    """The journal as a list: the story intro first (always there), then what happened.

    Right under the first-clear line of a hunt mission comes a line with the total of
    enemies destroyed in all the runs of that mission (only once there is something to count).
    """
    out = [{"intro": True}]
    hunts = {m["log"]: m["id"] for m in MISSIONS if (is_hunt(m) or is_paint(m)) and m.get("log")}
    for entry in state.get("log") or []:
        out.append(entry)
        key = entry.get("key") if isinstance(entry, dict) else None
        mission_id = hunts.get(key)
        if mission_id:
            out.append({"level": mission_level(state, mission_by_id(mission_id)), "mission": mission_id})
        if mission_id and mission_total_kills(state, mission_id) > 0:
            out.append({"kills": mission_total_kills(state, mission_id), "mission": mission_id})
    return out


def log_text(entry, translate):
    """Text of one journal line (new entries are {"key": ...}, old ones plain text)."""
    if isinstance(entry, dict):
        if "level" in entry:
            return translate("story_log_level").format(n=max(1, int(_num(entry.get("level"), 1))))
        if "kills" in entry:
            n = max(0, int(_num(entry.get("kills"), 0)))
            return translate("story_log_kill_1" if n == 1 else "story_log_kills").format(n=n)
        return translate(str(entry.get("key") or "story_log_clear"))
    return str(entry)
