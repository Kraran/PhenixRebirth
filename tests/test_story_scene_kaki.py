"""Story scene of the second Bestiary hunt: the khaki birds over a moon of Jupiter, told the first time it is launched."""
import os

import pygame

import story_state as ss
from i18n import t
from settings import asset_path
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

ID = "best_s2"


def _hub(seen=False, seen_others=(), cheat=False):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.record_result(st, "ch1_sortie", 100, True, {"bird1": 10})    # the first sortie opens the second hunt
    if seen:
        ss.mark_scene_seen(st, ID)
    for other in seen_others:
        ss.mark_scene_seen(st, other)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.cheat_unlock = cheat
    hub.pane = "map"
    hub.map_index = [m["id"] for m in hub.missions()].index(ID)
    return hub


def _wait(hub, seconds=1.0):
    for _ in range(int(seconds / 0.25) + 1):
        hub.update(0.25)


# ------------------------------------------------------------------ the scene itself
def test_the_second_hunt_has_a_scene_with_a_picture_a_clip_and_a_text():
    scene = ss.scene_of(ID)
    assert scene and len(scene["slides"]) == 1
    pic, key = scene["slides"][0]
    assert pic == "oiseaux_kaki" and os.path.exists(asset_path("story", pic + ".jpg"))
    assert ss.clip_path(pic) and os.path.getsize(ss.clip_path(pic)) > 100000
    text = t(key)
    assert text.startswith("Les bleus ne sont pas les seuls.")
    assert text.count("\n\n") == 2                                 # three paragraphs, with a pause between
    for word in ("Avioïdes", "oiseaux kaki", "vert", "lune de Jupiter", "yeux orange", "Bestiaire"):
        assert word in text
    assert "..." not in text                                        # the sign is « … », never three dots


def test_the_picture_is_the_one_given():
    img = pygame.image.load(asset_path("story", "oiseaux_kaki.jpg"))
    assert img.get_size() == (1792, 1008)


def test_the_clip_is_a_silent_loop_at_the_pace_of_the_game():
    import videoclip
    exe = videoclip.find_ffmpeg()
    if not exe:
        return
    import subprocess
    info = subprocess.run([exe, "-hide_banner", "-i", ss.clip_path("oiseaux_kaki")], capture_output=True,
                          text=True).stderr
    assert "Audio:" not in info and "1280x" not in info and " 24 fps" in info


def test_the_title_and_text_are_in_every_language_table():
    from i18n import T, LANG_CODES
    for key in ("story_scene_best2", "story_scene_best2_t"):
        assert set(T[key]) == set(LANG_CODES) and t(key)
    assert t("story_scene_best2_t") == "Bestiaire II : les oiseaux kaki"


def test_the_scene_comes_right_after_the_first_sortie():
    assert list(ss.SCENES)[:3] == ["ch1_sortie", ID, "best_s3"]


# ------------------------------------------------------------------ the first launch
def test_the_first_launch_of_the_hunt_shows_the_scene():
    hub = _hub()
    assert hub.mission_playable(hub._mission())
    assert hub.confirm() is None
    assert hub.screen == "intro" and hub.scene_id == ID and hub.scene_launch
    assert hub.intro_slides == ss.scene_of(ID)["slides"]
    assert not ss.scene_seen(hub.state, ID)


def test_the_end_of_the_scene_flies_the_mission_and_remembers_it():
    hub = _hub()
    hub.confirm()
    _wait(hub)
    spec = hub.confirm()
    assert isinstance(spec, dict) and spec["launch"] and spec["id"] == ID
    assert hub.screen == "hub" and hub.scene_id is None and ss.scene_seen(hub.state, ID)
    again = hub.confirm()                                           # the second time: straight to the mission
    assert isinstance(again, dict) and again["id"] == ID and hub.screen == "hub"


def test_skipping_the_scene_counts_as_seen():
    hub = _hub()
    hub.confirm()
    assert hub.back() is True
    assert hub.screen == "hub" and hub.pane == "map" and ss.scene_seen(hub.state, ID)


def test_a_replayed_hunt_does_not_show_the_scene_again():
    hub = _hub(seen=True)
    spec = hub.confirm()
    assert isinstance(spec, dict) and spec["id"] == ID and hub.screen == "hub"


def test_the_scene_of_the_first_sortie_does_not_stand_in_for_this_one():
    hub = _hub(seen_others=("ch1_sortie", "dome_1", "paint_1"))
    hub.confirm()
    assert hub.screen == "intro" and hub.scene_id == ID


def test_the_other_hunts_do_not_show_this_scene():
    hub = _hub()
    hub.cheat_unlock = True
    hub.map_index = [m["id"] for m in hub.missions()].index("dome_2")
    spec = hub.confirm()
    assert isinstance(spec, dict) and spec["id"] == "dome_2" and hub.screen == "hub"


# ------------------------------------------------------------------ the journal
def test_the_replay_line_follows_the_first_sortie_scene():
    hub = _hub(seen=True, seen_others=("ch1_sortie", "dome_1", "paint_1"))
    entries = hub.log_entries()
    assert entries[:5] == [{"intro": True}, {"scene": "ch1_sortie"}, {"scene": ID}, {"scene": "dome_1"},
                           {"scene": "paint_1"}]          # (the gargoyle scene, not seen here, comes after the khaki one)
    assert ss.log_text(entries[2], t) == "Revoir : Bestiaire II : les oiseaux kaki"


def test_the_journal_replays_the_scene_and_never_launches_the_mission():
    hub = _hub(seen=True)
    hub.pane = "log"
    hub.nav_v(1)
    assert hub.confirm() is None
    assert hub.screen == "intro" and hub.scene_id == ID and not hub.scene_launch
    _wait(hub)
    assert hub.confirm() is None
    assert hub.screen == "hub" and hub.pane == "log"


# ------------------------------------------------------------------ drawing
def test_the_scene_draws_its_picture_and_its_hints(run):
    import story
    hub = _hub()
    hub.confirm()
    hub.intro_t = 500.0
    hub.intro_pos = 99999.0
    hub.update(0.01)
    seen = []
    real, real_fit = story._text, story._text_fit

    def spy(surface, font, text, *a, **k):
        seen.append(str(text))
        return real(surface, font, text, *a, **k)

    def spy_fit(surface, font, text, *a, **k):
        seen.append(str(text))
        return real_fit(surface, font, text, *a, **k)

    story._text, story._text_fit = spy, spy_fit
    try:
        g = run.game
        surf = pygame.Surface((1280, 720))
        hub.draw(surf, g.font, g.medium_font, g.font)
    finally:
        story._text, story._text_fit = real, real_fit
    assert hub.help_items()[0][0] == ("ok", "hint_takeoff")   # the help bar says "take off"
    assert len({tuple(surf.get_at((x, y))) for x in range(0, 1280, 40) for y in range(0, 720, 40)}) > 20
