"""The visual novel of the Adventure: after the concert of Lyra Voss, a scene between the story missions.

A scene is a picture, a speaker, a text and a list of answers. Each answer is worth hidden points (never shown to the
player); the total of the points the pilot has earned will decide which ending the visual novel tells. The answer of
a scene is final: it is kept in the save (`state["vn"]["picks"]`, scene id -> index of the answer, 0 based), the
points are always worked out from it, so a change of the table below changes them in every save.

This module knows nothing of the screen (story.py draws it) nor of the other save fields (story_state.py keeps the
films and the journal). Texts are keys of i18n.T.
"""

# id -> scene. "film": the film (story_state.FILMS) shown right before it; "image": assets/story/<image>.jpg, the
# support of the text and of the menu; "answers": [(text key, hidden points)].
VN_SCENES = {
    "vn_1": {
        "film": "vn_1", "image": "vn_1_bar", "title": "story_vn1_t", "speaker": "story_vn_lyra",
        "text": "story_vn1_q",
        "answers": [("story_vn1_a1", 1), ("story_vn1_a2", 2), ("story_vn1_a3", 3), ("story_vn1_a4", 4)],
    },
}
VN_ORDER = ["vn_1"]                    # the scenes in the order of the story


def clean(data):
    """The `vn` field of a save, cleaned: {"picks": {scene id: answer index}}. Unknown scenes and answers that do not
    exist are dropped (a damaged save never breaks the screen)."""
    picks = {}
    raw = data.get("picks") if isinstance(data, dict) else None
    if isinstance(raw, dict):
        for sid, idx in raw.items():
            scene = VN_SCENES.get(sid)
            if scene is None or isinstance(idx, bool) or not isinstance(idx, int):
                continue
            if 0 <= idx < len(scene["answers"]):
                picks[sid] = idx
    return {"picks": picks}


def scene(scene_id):
    return VN_SCENES.get(scene_id)


def scene_of_film(film_id):
    """The scene that follows this film, or None."""
    for sid in VN_ORDER:
        if VN_SCENES[sid]["film"] == film_id:
            return sid
    return None


def pick(state, scene_id):
    """Index of the answer given in this scene, or None while it is not answered."""
    return clean((state or {}).get("vn"))["picks"].get(scene_id)


def answered(state, scene_id):
    return pick(state, scene_id) is not None


def choose(state, scene_id, index):
    """Give the answer `index` to a scene. Final: False (nothing changes) when the scene is already answered, unknown,
    or the answer does not exist."""
    sc = VN_SCENES.get(scene_id)
    if sc is None or isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(sc["answers"]):
        return False
    vn = clean(state.get("vn"))
    if scene_id in vn["picks"]:
        return False
    vn["picks"][scene_id] = index
    state["vn"] = vn
    return True


def points(state):
    """The hidden total of the points of every answer given so far."""
    total = 0
    for sid, idx in clean((state or {}).get("vn"))["picks"].items():
        total += VN_SCENES[sid]["answers"][idx][1]
    return total
