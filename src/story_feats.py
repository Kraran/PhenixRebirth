"""
The achievements of the Adventure (second page of the achievements screen, achievements.CATALOG_ADV).

Most of them are read from the save: `check(state)` looks at what a pilot has done (missions won and how many
times, the act, the credits, the Bestiary, the scenes watched, the paint, the reactors) and unlocks or raises
what it can. It is called each time the Adventure writes its save, and when a save is opened (a pilot who played
before this page existed gets what he has earned). Three of them count events that a save does not keep: the
workshop upgrades bought (`note_upgrade`), the missions won without losing a life (`note_flawless`) and the last
mission won without losing a life (`note_untouchable`).

The achievements are the player's, not a save's: the counters keep the best of all the saves (set_scalable_at_least),
the events add up. A cheated Adventure (story.StoryHub.cheating) counts nothing.

What was unlocked or raised waits in a list (`take_news`) that the game shows as a banner once it is back in the
menus: the StoryHub that saw it may already be gone by then (a new one is made when a mission ends).
"""
import weakref

import achievements as ach
import story_items
import story_state as ss
from errlog import log_exc

HUNTS = {"adv_sortie": "ch1_sortie", "adv_kaki": "best_s2", "adv_garg": "best_s3", "adv_shadow": "best_s4",
         "adv_commander": "best_boss"}
DOMES = ("dome_1", "dome_2", "dome_3", "dome_4", "dome_5")
PHENIX = ("phenix_1", "phenix_2", "phenix_3", "phenix_4", "phenix_5")
FINAL = ("final_1", "final_2", "final_3", "final_4", "final_5")
WRECKS = ("bonus_wreck_phenix", "bonus_wreck_shield")

_game = None                 # weak reference to the Game: its achievements data is the one to write into
_news = []                   # (achievement id, tier or None) not shown yet


def use_game(game):
    """The Game keeps the achievements data in memory and writes it whole: the Adventure page must change THAT
    copy, or the next arcade unlock would write the old one back over it."""
    global _game
    _game = weakref.ref(game)


def _data():
    game = _game() if _game is not None else None
    data = getattr(game, "ach_data", None)
    if isinstance(data, dict):
        return data
    return ach.load_achievements()


def counts(state):
    """What the save says, for the achievements that count something: {id: number}."""
    state = state or {}
    cleared = set(state.get("cleared") or [])
    out = {aid: ss.hunt_level(state, mid) - 1 for aid, mid in HUNTS.items()}
    out["adv_domes"] = sum(1 for m in DOMES if m in cleared)
    out["adv_phenix"] = sum(1 for m in PHENIX if m in cleared)
    out["adv_paint"] = ss.paint_state(state)["runs"]
    out["adv_saver"] = max(0, int(ss._num(state.get("credits"), 0)))
    entries = ss.bestiary_entries(state)
    out["adv_bestiary"] = len(entries)
    out["adv_hunter"] = sum(1 for entry, n in entries if ss.best_tiers(n, bool(entry.get("boss")))["bonus"])
    out["adv_cinema"] = sum(1 for mid in ss.SCENES if ss.scene_seen(state, mid))
    out["adv_riposte"] = sum(1 for m in FINAL if m in cleared)
    return out


def at_full(state):
    """Is the hull kept in Act 3 at 100 %, like the arcade ship (everything the Act 3 workshop sells is bought)?"""
    hull = ss.kept_hull(state)
    sl = next((s for s in (state or {}).get("slots") or [] if s.get("id") == hull and s.get("owned")), None)
    if sl is None:
        return False
    if int(ss._num(sl.get("speed"), 0)) < 100 or int(ss._num(sl.get("lives"), 1)) < ss.lives_base(sl) + 2:
        return False
    if hull == "shield":
        return sl.get("wall") == "immune" and bool(sl.get("dome")) and \
            (ss._num(sl.get("dome_dur"), 0.0) or 0.0) >= ss.DOME_DUR_MAX - 1e-6
    return ss.phenix_cap(sl) >= 100


def done(state):
    """The achievements a save has earned once and for all (no counter)."""
    state = state or {}
    act = int(ss._num(state.get("act"), 1))
    got = story_items.clean(state.get("items"))["got"]
    shield = next((sl for sl in state.get("slots") or [] if sl.get("id") == "shield"), {})
    out = set()
    if state.get("name"):
        out.add("adv_pilot")
    if any(got.get(item) for item in story_items.REACTOR_IDS):
        out.add("adv_reactor")
    if act >= 2:
        out.add("adv_act2")
        if state.get("mode") == "veteran":
            out.add("adv_veteran")
    if (shield.get("tint") or "red") in ss.PAINT_TINTS and shield.get("tint") != "red":
        out.add("adv_colour")
    phenix = next((sl for sl in state.get("slots") or [] if sl.get("id") == "phoenix"), {})
    if phenix.get("owned") and phenix.get("tint") in ("blue", "gold"):
        out.add("adv_colour")                        # the Phenix painted in Act 3
    if ss.scene_seen(state, ss.BAR_SCENE):
        out.add("adv_bar")
    # Act 3
    cleared = set(state.get("cleared") or [])
    if "act3_gate" in cleared:
        out.add("adv_raid")
    hull = ss.kept_hull(state)
    if hull:
        out.add("adv_anchor")
    if at_full(state):
        out.add("adv_full")
    if cleared & set(WRECKS):
        out.add("adv_wreck")
    items = story_items.clean(state.get("items"))
    if "bonus_singularity" in cleared and items["act"] >= 3 and items["got"].get("singularity"):
        out.add("adv_convoy")
    if ss.flag(state, ss.GAME_WON):
        out.add("adv_triton")
        if hull == "shield":
            out.add("adv_win_shield")
        elif hull == "phoenix":
            out.add("adv_win_phenix")
        if state.get("mode") == "veteran":
            out.add("adv_legend")
    if hull == "phoenix" and phenix.get("owned") and phenix.get("tint") == "gold":
        out.add("adv_gilded")
    return out


def _raise(aid, value, data, news):
    changed, tier = ach.set_scalable_at_least(aid, value, data)
    if changed and tier:
        news.append((aid, tier))


def _add(aid, data, news):
    changed, tier = ach.add_scalable(aid, 1, data)
    if changed and tier:
        news.append((aid, tier))


def check(state):
    """Unlock / raise what the save `state` has earned. Returns the news (also kept for take_news)."""
    news = []
    try:
        data = _data()
        for aid, value in counts(state).items():
            if value > 0:
                _raise(aid, value, data, news)
        for aid in sorted(done(state), key=ach.ADV_IDS.index):
            if ach.unlock_achievement(aid, data):
                news.append((aid, None))
    except Exception:
        log_exc("story_feats.check")
    _news.extend(news)
    return news


def note_upgrade():
    """A workshop upgrade was bought."""
    news = []
    try:
        _add("adv_mechanic", _data(), news)
    except Exception:
        log_exc("story_feats.note_upgrade")
    _news.extend(news)
    return news


def note_flawless():
    """A mission was won without losing a life."""
    news = []
    try:
        _add("adv_flawless", _data(), news)
    except Exception:
        log_exc("story_feats.note_flawless")
    _news.extend(news)
    return news


def note_untouchable():
    """The last mission of the Adventure was won without losing a life."""
    news = []
    try:
        if ach.unlock_achievement("adv_untouchable", _data()):
            news.append(("adv_untouchable", None))
    except Exception:
        log_exc("story_feats.note_untouchable")
    _news.extend(news)
    return news


def take_news():
    """What was unlocked or raised since the last call, then forgotten."""
    out = list(_news)
    del _news[:]
    return out
