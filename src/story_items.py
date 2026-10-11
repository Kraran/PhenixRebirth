"""The loot items of the Adventure: four single-use objects that fall during a mission.

The life of one item, in one Act:
    lootable   (nothing in the save)  -> it may fall during a mission;
    "found"    the pilot caught it    -> the hangar shop sells it, once, for its price;
    "installed" bought                -> it works in the next mission that ends, and in that one only;
    "used"     that mission is over   -> it is gone for the rest of the Act: it does not fall again.
A new Act gives every item back (the book is stamped with the Act it belongs to).
Only one copy of an item exists at a time: an item that is found, installed or used never falls again.

No pygame here: the rules only read and write the save dict (see story_state.py).
"""

ITEMS = [
    # id, price (hangar points)
    ("singularity", 6000),     # fire rate x2
    ("genesis", 6000),         # one more life
    ("hyperion", 4000),        # speed +40 %
    ("tesla", 2000),           # electric immunity
]
ITEM_IDS = tuple(i for i, _ in ITEMS)
PRICES = dict(ITEMS)

FOUND, INSTALLED, USED = "found", "installed", "used"
_STATES = (FOUND, INSTALLED, USED)

# Loot is rare: at most ONE mission in three may carry an item (a drop needs two missions without one before it),
# and then only DROP_CHANCE of the missions that may. The item falls some time into the mission.
MIN_GAP = 2                        # missions without an item between two that have one
DROP_CHANCE = 0.40
DROP_DELAY = (6.0, 30.0)           # seconds into the mission when the item appears

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
            if item in ITEM_IDS and st in _STATES:
                book["got"][item] = st
    return book


def book(state):
    """The item book of this save, for the current Act (a new Act starts with a fresh one; the count of missions
    since the last drop goes on, so the gap holds across two Acts)."""
    act = _act(state)
    current = clean(state.get("items"))
    if current["act"] != act:
        current = {"act": act, "got": {}, "since": current["since"]}
    state["items"] = current
    return current


def status(state, item):
    """None (lootable), "found", "installed" or "used"."""
    return book(state)["got"].get(item)


def lootable(state):
    """Items that may still fall in a mission of this Act."""
    got = book(state)["got"]
    return [i for i in ITEM_IDS if i not in got]


def shop(state):
    """What the hangar shop lists: the items found or installed, in the fixed order."""
    got = book(state)["got"]
    return [i for i in ITEM_IDS if got.get(i) in (FOUND, INSTALLED)]


def installed(state):
    got = book(state)["got"]
    return [i for i in ITEM_IDS if got.get(i) == INSTALLED]


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
        if b["got"].get(item) == INSTALLED:
            b["got"][item] = USED
            used.append(item)
    return used


def plan_drop(state, rand):
    """A mission starts: does an item fall in it? Returns {"id", "t"} (seconds into the mission) or None.

    `rand` is the random module (or anything with random / choice / uniform). Missions count even when no item is
    left to find, so the gap between two drops never depends on what is lootable."""
    b = book(state)                      # (book() makes a new dict each time: only this one is changed below)
    b["since"] = min(99, b["since"] + 1)
    pool = [i for i in ITEM_IDS if i not in b["got"]]
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
