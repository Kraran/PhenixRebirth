"""The loot items of the Adventure: four single-use objects that fall during a mission, and the two reactors.

The life of one item, in one Act:
    lootable   (nothing in the save)  -> it may fall during a mission;
    "found"    the pilot caught it    -> the hangar shop sells it, once, for its price;
    "installed" bought                -> it works in the next mission that ends, and in that one only;
    "used"     that mission is over   -> it is gone for the rest of the Act: it does not fall again.
A new Act gives every item back (the book is stamped with the Act it belongs to).
Only one copy of an item exists at a time: an item that is found, installed or used never falls again.

The two reactors (the two-dimensional impulse reactor of the BONUS missions, one for the Shield and one for the Phenix)
are the exception: they only fall in their own BONUS mission, once, never in the random loot; once installed they
are not used up (the hull flies up and down the lower third of the screen for good) and the new Act keeps them.
Each one is sold for its own hull only (the workshop lists the one of the hull selected).

No pygame here: the rules only read and write the save dict (see story_state.py).
"""

ITEMS = [
    # id, price (hangar points)
    ("singularity", 6000),     # fire rate x2
    ("genesis", 6000),         # one more life
    ("hyperion", 4000),        # speed +40 %
    ("tesla", 2000),           # electric immunity
    ("reactor_shield", 2000),  # two-dimensional impulse reactor for the Shield: flight in the lower third, for good
    ("reactor_phenix", 4000),  # the same for the Phenix
]
ITEM_IDS = tuple(i for i, _ in ITEMS)
PRICES = dict(ITEMS)

# The reactors: hull id (as in the save slots) -> item. They have no random drop and are never used up.
REACTORS = {"shield": "reactor_shield", "phoenix": "reactor_phenix"}
REACTOR_IDS = tuple(REACTORS.values())
RANDOM_IDS = tuple(i for i in ITEM_IDS if i not in REACTOR_IDS)     # what may fall in an ordinary mission
SPRITES = {"reactor_shield": "reactor", "reactor_phenix": "reactor"}   # items that share a picture (assets/items)

FOUND, INSTALLED, USED = "found", "installed", "used"
_STATES = (FOUND, INSTALLED, USED)

# Loot is rare: at most ONE mission in three may carry an item (a drop needs two missions without one before it),
# and then only DROP_CHANCE of the missions that may. The item falls some time into the mission.
MIN_GAP = 2                        # missions without an item between two that have one
DROP_CHANCE = 0.40
DROP_DELAY = (6.0, 30.0)           # seconds into the mission when the item appears
REACTOR_DELAY = (8.0, 45.0)        # the reactor of a BONUS mission falls somewhere in its four waves

FIRE_RATE_MULT = 2.0               # Singularity Core: the bullets fly twice as fast, so the ship fires twice as often
SPEED_MULT = 1.4                   # Réacteur Hyperion: +40 % speed
EXTRA_LIVES = 1                    # Noyau Genesis


def _num(value, default):
    try:
        if isinstance(value, bool):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _act(state):
    return max(1, _num((state or {}).get("act"), 1))


def clean(data):
    """A book from a save file: only known items, only known states, anything else dropped."""
    book = {"act": 1, "got": {}, "since": MIN_GAP}
    if not isinstance(data, dict):
        return book
    book["act"] = max(1, _num(data.get("act"), 1))
    book["since"] = max(0, min(99, _num(data.get("since"), MIN_GAP)))
    got = data.get("got")
    if isinstance(got, dict):
        for item, st in got.items():
            if item in ITEM_IDS and st in _STATES and not (item in REACTOR_IDS and st == USED):
                book["got"][item] = st
    return book


def book(state):
    """The item book of this save, for the current Act (a new Act starts with a fresh one; the count of missions
    since the last drop goes on, so the gap holds across two Acts)."""
    act = _act(state)
    current = clean(state.get("items"))
    if current["act"] != act:
        keep = {i: st for i, st in current["got"].items() if i in REACTOR_IDS}      # a reactor stays for good
        current = {"act": act, "got": keep, "since": current["since"]}
    state["items"] = current
    return current


def permanent(item):
    """True for the reactors (kept for good once installed), False for the four single-use items."""
    return item in REACTOR_IDS


def status(state, item):
    """None (lootable), "found", "installed" or "used"."""
    return book(state)["got"].get(item)


def lootable(state):
    """Items that may still fall in a mission of this Act."""
    got = book(state)["got"]
    return [i for i in RANDOM_IDS if i not in got]


def shop(state, hull=None):
    """What the hangar shop lists: the items found or installed, in the fixed order. A reactor is listed only for
    its own hull (`hull`: the id of the hull selected); with no hull given no reactor is listed."""
    got = book(state)["got"]
    return [i for i in ITEM_IDS if got.get(i) in (FOUND, INSTALLED) and (i not in REACTOR_IDS or REACTORS.get(hull) == i)]


def installed(state):
    """The single-use items installed for the next mission (a reactor is not one: it is never used up)."""
    got = book(state)["got"]
    return [i for i in RANDOM_IDS if got.get(i) == INSTALLED]


def reactor_status(state, hull):
    """None, "found" (caught, on sale) or "installed" for the reactor of `hull` ("shield" or "phoenix")."""
    item = REACTORS.get(hull)
    return book(state)["got"].get(item) if item else None


def reactor_on(state, hull):
    """Does this hull fly up and down the lower third of the screen?"""
    return reactor_status(state, hull) == INSTALLED


def reactor_plan(state, hull, rand):
    """A BONUS mission starts: the reactor of `hull` falls once, some time into the waves ("last_wave": at the latest
    when the last wave comes in, so a quick pilot still sees it). {"id", "t", "last_wave"} or None when there is
    nothing to drop (the pilot has it already)."""
    item = REACTORS.get(hull)
    if item is None or item in book(state)["got"]:
        return None
    return {"id": item, "t": float(rand.uniform(*REACTOR_DELAY)), "last_wave": True}


def find(state, item):
    """The pilot caught `item`: the hangar sells it now. False if it was not lootable (nothing changes)."""
    b = book(state)
    if item not in ITEM_IDS or item in b["got"]:
        return False
    b["got"][item] = FOUND
    return True


def affordable(state, item):
    return int((state or {}).get("credits", 0) or 0) >= PRICES.get(item, 10 ** 9)


def buy(state, item):
    """Pay for a found item: it is installed for the next mission. True when bought."""
    b = book(state)
    if b["got"].get(item) != FOUND or not affordable(state, item):
        return False
    state["credits"] = int(state.get("credits", 0)) - PRICES[item]
    b["got"][item] = INSTALLED
    return True


def consume(state, items):
    """The mission is over: every installed item among `items` is used up. Returns the ones consumed."""
    b = book(state)
    used = []
    for item in items or ():
        if b["got"].get(item) == INSTALLED and item not in REACTOR_IDS:
            b["got"][item] = USED
            used.append(item)
    return used


def plan_drop(state, rand):
    """A mission starts: does an item fall in it? Returns {"id", "t"} (seconds into the mission) or None.

    `rand` is the random module (or anything with random / choice / uniform). Missions count even when no item is
    left to find, so the gap between two drops never depends on what is lootable."""
    b = book(state)                      # (book() makes a new dict each time: only this one is changed below)
    b["since"] = min(99, b["since"] + 1)
    pool = [i for i in RANDOM_IDS if i not in b["got"]]
    if not pool or b["since"] <= MIN_GAP or rand.random() >= DROP_CHANCE:
        return None
    b["since"] = 0
    return {"id": rand.choice(pool), "t": float(rand.uniform(*DROP_DELAY))}


def effects(items):
    """What a set of installed items does to the ship."""
    items = set(items or ())
    return {
        "fire_mult": FIRE_RATE_MULT if "singularity" in items else 1.0,
        "extra_lives": EXTRA_LIVES if "genesis" in items else 0,
        "speed_mult": SPEED_MULT if "hyperion" in items else 1.0,
        "electric_immune": "tesla" in items,
    }
