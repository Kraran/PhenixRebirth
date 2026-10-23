"""The visual novel of the Adventure: after the concert of Lyra Voss, a scene between the story missions.

A scene is a picture, a speaker, a text and a list of answers. Each answer is worth hidden points (never shown to the
player); the total of the points the pilot has earned will decide which ending the visual novel tells. The answer of
a scene is final: it is kept in the save (`state["vn"]["picks"]`, scene id -> index of the answer, 0 based), the
points are always worked out from it, so a change of the table below changes them in every save.

This module knows nothing of the screen (story.py draws it) nor of the other save fields (story_state.py keeps the
films and the journal). Texts are keys of i18n.T.
"""
import random

# id -> scene. "film": the film (story_state.FILMS) shown right before it, or None; "image": assets/story/<image>.jpg, the
# support of the text and of the menu; "answers": [(text key, hidden points)]. A scene without a film comes after
# another one: "after": its id, "wins": how many story missions (the series and the asteroid belts, see
# story_state.story_wins) have to be won once that one is answered. "panel": the side of the picture the text sits on.
# "journal": the title of its line in the journal (a scene with a film is listed by its film).
# A text is a list of paragraphs, one per line: a line that begins with a star is narration ("*She smiles."), the others
# are the words of the speaker; an empty line cuts the text in pages (see `pages`). An answer may have a third item, the
# key of the reaction that follows it (same format as the text). "shuffle": the answers are shown in a random order
# (the points and the saved pick stay those of the order of the list below).
VN_SCENES = {
    "vn_1": {
        "film": "vn_1", "image": "vn_1_bar", "title": "story_vn1_t", "speaker": "story_vn_lyra",
        "text": "story_vn1_q", "shuffle": True,
        "answers": [("story_vn1_a1", 2, "story_vn1_r1"), ("story_vn1_a2", 3, "story_vn1_r2"),
                    ("story_vn1_a3", 4, "story_vn1_r3"), ("story_vn1_a4", 3, "story_vn1_r4")],
    },
    "vn_2": {
        "film": None, "after": "vn_1", "wins": 1, "panel": "right", "image": "vn_2_hangar", "title": "story_vn2_t",
        "journal": "story_vn2_j", "speaker": "story_vn_lyra", "text": "story_vn2_q", "shuffle": True,
        "answers": [("story_vn2_a1", 1, "story_vn2_r1"), ("story_vn2_a2", 3, "story_vn2_r2"),
                    ("story_vn2_a3", 2, "story_vn2_r3"), ("story_vn2_a4", 4, "story_vn2_r4")],
    },
    "vn_3": {
        "film": None, "after": "vn_2", "wins": 1, "panel": "right", "image": "vn_3_pont", "title": "story_vn3_t",
        "journal": "story_vn3_j", "speaker": "story_vn_lyra", "text": "story_vn3_q", "shuffle": True,
        "answers": [("story_vn3_a1", 1, "story_vn3_r1"), ("story_vn3_a2", 3, "story_vn3_r2"),
                    ("story_vn3_a3", 4, "story_vn3_r3"), ("story_vn3_a4", 2, "story_vn3_r4")],
    },
    "vn_4": {                                      # (Lyra is on the right of the picture: the text is on the left)
        "film": None, "after": "vn_3", "wins": 1, "image": "vn_4_refuge", "title": "story_vn4_t",
        "journal": "story_vn4_j", "speaker": "story_vn_lyra", "text": "story_vn4_q", "shuffle": True,
        "answers": [("story_vn4_a1", 2, "story_vn4_r1"), ("story_vn4_a2", 3, "story_vn4_r2"),
                    ("story_vn4_a3", 4, "story_vn4_r3"), ("story_vn4_a4", 1, "story_vn4_r4")],
    },
}
VN_ORDER = ["vn_1", "vn_2", "vn_3", "vn_4"]    # the scenes in the order of the story


def clean(data):
    """The `vn` field of a save, cleaned: {"picks": {scene id: answer index}, "marks": {scene id: story missions won
    when it was answered}}. Unknown scenes, answers that do not exist and marks of a scene not answered are dropped (a
    damaged save never breaks the screen)."""
    picks = {}
    raw = data.get("picks") if isinstance(data, dict) else None
    if isinstance(raw, dict):
        for sid, idx in raw.items():
            scene = VN_SCENES.get(sid)
            if scene is None or isinstance(idx, bool) or not isinstance(idx, int):
                continue
            if 0 <= idx < len(scene["answers"]):
                picks[sid] = idx
    marks = {}
    raw = data.get("marks") if isinstance(data, dict) else None
    if isinstance(raw, dict):
        for sid, n in raw.items():
            if sid in picks and isinstance(n, int) and not isinstance(n, bool) and n >= 0:
                marks[sid] = n
    return {"picks": picks, "marks": marks}


def scene(scene_id):
    return VN_SCENES.get(scene_id)


def scene_of_film(film_id):
    """The scene that follows this film, or None."""
    if not film_id:
        return None
    for sid in VN_ORDER:
        if VN_SCENES[sid]["film"] == film_id:
            return sid
    return None


NBSP = "\u00a0"


def tidy(text):
    """A text with its extra spaces dropped and the spaces inside the French quotes (and before a `?` `!` `:` `;`)
    made unbreakable, so that a line never begins with the closing quote (see story._wrap_nb)."""
    out = " ".join(str(text).split())
    for old, new in ((" »", NBSP + "»"), ("« ", "«" + NBSP), (" ?", NBSP + "?"), (" !", NBSP + "!"),
                     (" :", NBSP + ":"), (" ;", NBSP + ";")):
        out = out.replace(old, new)
    return out


def pages(text):
    """A text cut in pages: a list of pages, each a list of paragraphs (narration, words) -- `narration`: the line began
    with a star. Extra spaces are dropped and the empty lines only separate the pages (never an empty page)."""
    out, page = [], []
    for raw in str(text).split("\n"):
        line = raw.strip()
        if not line:
            if page:
                out.append(page)
                page = []
            continue
        narration = line.startswith("*")
        words = tidy(line.lstrip("*"))
        if words:
            page.append((narration, words))
    if page:
        out.append(page)
    return out


def page_length(page):
    """How many characters a page types (the line breaks of the wrapping count as the space they replace)."""
    return sum(len(words) + 1 for _narration, words in page)


def reaction(scene_id, index):
    """The key of the text that follows this answer, or None (a scene without reactions, an answer that does not exist)."""
    sc = VN_SCENES.get(scene_id)
    if sc is None or isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(sc["answers"]):
        return None
    ans = sc["answers"][index]
    return ans[2] if len(ans) > 2 else None


def order(scene_id, shuffled=True):
    """The order the answers are shown in: a list of the indexes of the answers. Random for a scene that asks for it
    (`shuffled`), otherwise the order of the list."""
    sc = VN_SCENES.get(scene_id) or {"answers": []}
    n = len(sc["answers"])
    return random.sample(range(n), n) if shuffled and sc.get("shuffle") else list(range(n))


def pick(state, scene_id):
    """Index of the answer given in this scene, or None while it is not answered."""
    return clean((state or {}).get("vn"))["picks"].get(scene_id)


def answered(state, scene_id):
    return pick(state, scene_id) is not None


def choose(state, scene_id, index, wins=0):
    """Give the answer `index` to a scene (`wins`: the story missions won so far, the next scene counts from there).
    Final: False (nothing changes) when the scene is already answered, unknown, or the answer does not exist."""
    sc = VN_SCENES.get(scene_id)
    if sc is None or isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(sc["answers"]):
        return False
    vn = clean(state.get("vn"))
    if scene_id in vn["picks"]:
        return False
    vn["picks"][scene_id] = index
    vn["marks"][scene_id] = max(0, int(wins))
    state["vn"] = vn
    return True


def mark(state, scene_id):
    """The story missions won when this scene was answered, or None (not answered, or answered before the count)."""
    return clean((state or {}).get("vn"))["marks"].get(scene_id)


def ensure_marks(state, wins):
    """An answered scene that has no mark (a save made before the next scenes existed) counts from now on. True when a
    mark was added."""
    vn = clean(state.get("vn"))
    added = False
    for sid in vn["picks"]:
        if sid not in vn["marks"]:
            vn["marks"][sid] = max(0, int(wins))
            added = True
    if added:
        state["vn"] = vn
    return added


def next_scene(state):
    """The first scene not answered yet (the scenes come one after the other), or None when all are."""
    return next((sid for sid in VN_ORDER if not answered(state, sid)), None)


def points(state):
    """The hidden total of the points of every answer given so far."""
    total = 0
    for sid, idx in clean((state or {}).get("vn"))["picks"].items():
        total += VN_SCENES[sid]["answers"][idx][1]
    return total
