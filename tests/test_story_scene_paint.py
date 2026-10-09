"""Second story scene: Wallems' workshop, told the first time the first paint mission is launched."""
import os

import pygame

import story_state as ss
from i18n import t
from settings import asset_path
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

ID = "paint_1"


def _hub(seen_dome=False, seen_paint=False, log=()):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["log"] = list(log)
    if seen_dome:
        ss.mark_scene_seen(st, "dome_1")
    if seen_paint:
        ss.mark_scene_seen(st, ID)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.cheat_unlock = True
    hub.pane = "map"
    hub.map_index = [m["id"] for m in hub.missions()].index(ID)
    return hub


def _wait(hub, seconds=1.0):
    for _ in range(int(seconds / 0.25) + 1):
        hub.update(0.25)


# ------------------------------------------------------------------ the scene itself
def test_the_first_paint_mission_has_a_scene_with_its_picture_and_text():
    scene = ss.scene_of(ID)
    assert scene and len(scene["slides"]) == 1
    pic, key = scene["slides"][0]
    assert pic == "atelier_wallems" and os.path.exists(asset_path("story", pic + ".jpg"))
    text = t(key)
    assert text.startswith("L’atelier clandestin du vieux Wallems, creusé dans le flanc de l’astéroïde 434-Hungaria, tourne encore.")
    assert text.endswith("Non, je n'irai pas, ça serait du délire...")
    assert text.count("\n\n") == 2                                 # three paragraphs, with a pause between
    assert "Wallems" in text and "Avioïdes" in text and "trompettes flamboyantes…" in text
    assert ss.scene_of("paint_2") is None and ss.scene_of("paint_3") is None


def test_the_text_is_exactly_the_one_given():
    paragraphs = t("story_scene_paint_1").split("\n\n")
    assert paragraphs[1] == ("Je ne suis pas assez fou pour tenter de franchir les hordes d’Avioïdes qui quadrillent "
                             "le secteur, rang après rang, rien que pour faire repeindre mon vaisseau. Non. Je ne le suis pas.")
    assert paragraphs[0].endswith("des masques penchés sur le métal...")
    assert paragraphs[2].startswith("Et pourtant la rumeur tient. Wallems prend encore les commandes, choisit ses teintes uniques à l’œil,")


def test_the_title_and_text_are_in_every_language_table():
    from i18n import T, LANG_CODES
    for key in ("story_scene_paint_1", "story_scene_paint_1_t"):
        assert set(T[key]) == set(LANG_CODES) and t(key)
    assert t("story_scene_paint_1_t") == "Peinture I : l'atelier de Wallems"


def test_the_picture_is_the_one_given():
    img = pygame.image.load(asset_path("story", "atelier_wallems.jpg"))
    assert img.get_size() == (1792, 1008)


def test_the_two_scenes_are_independent():
    assert list(ss.SCENES) == ["dome_1", ID]
    st = ss.create_slot(1, "A", "normal")
    ss.mark_scene_seen(st, ID)
    assert ss.scene_seen(st, ID) and not ss.scene_seen(st, "dome_1")
    assert ss.scenes_seen(st) == [ID]


# ------------------------------------------------------------------ the first launch
def test_the_first_launch_shows_the_scene_instead_of_flying():
    hub = _hub()
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
    assert hub.screen == "hub" and hub.scene_id is None
    assert ss.scene_seen(hub.state, ID) and not ss.scene_seen(hub.state, "dome_1")
    again = hub.confirm()                                           # the second time: straight to the mission
    assert isinstance(again, dict) and again["id"] == ID and hub.screen == "hub"


def test_skipping_the_scene_counts_as_seen_and_comes_back_to_the_map():
    hub = _hub()
    hub.confirm()
    assert hub.back() is True
    assert hub.screen == "hub" and hub.pane == "map" and ss.scene_seen(hub.state, ID)
    spec = hub.confirm()
    assert isinstance(spec, dict) and spec["id"] == ID


def test_the_scene_is_saved_with_the_slot():
    hub = _hub()
    hub.confirm()
    hub.back()
    hub.cheat_unlock = False                                        # a cheated adventure is never written
    hub.save()
    again = StoryHub()
    again.open_slot(1)
    assert ss.scene_seen(again.state, ID)


def test_the_dome_scene_does_not_stand_in_for_this_one():
    hub = _hub(seen_dome=True)
    hub.confirm()
    assert hub.screen == "intro" and hub.scene_id == ID


def test_a_mission_that_cannot_be_flown_shows_no_scene():
    hub = _hub()
    hub.cheat_unlock = False
    assert not hub.mission_playable(hub._mission())
    assert hub.confirm() is None and hub.screen == "hub"


def test_the_other_paint_missions_fly_straight_away():
    hub = _hub()
    hub.map_index = [m["id"] for m in hub.missions()].index("paint_2")
    spec = hub.confirm()
    assert isinstance(spec, dict) and spec["id"] == "paint_2" and hub.screen == "hub"


# ------------------------------------------------------------------ the journal
def test_the_journal_has_no_line_before_the_scene_is_seen():
    hub = _hub()
    hub.pane = "log"
    assert hub.log_entries() == [{"intro": True}]


def test_the_replay_lines_follow_the_order_of_the_scenes():
    hub = _hub(seen_dome=True, seen_paint=True, log=[{"key": "story_log_sortie"}])
    entries = hub.log_entries()
    assert entries[:4] == [{"intro": True}, {"scene": "dome_1"}, {"scene": ID}, {"key": "story_log_sortie"}]
    assert ss.log_text(entries[2], t) == "Revoir : Peinture I : l'atelier de Wallems"
    only = _hub(seen_paint=True).log_entries()
    assert only[:2] == [{"intro": True}, {"scene": ID}]


def test_the_journal_replays_the_scene_and_never_launches_the_mission():
    hub = _hub(seen_paint=True)
    hub.pane = "log"
    hub.nav_v(1)
    assert hub.confirm() is None
    assert hub.screen == "intro" and hub.scene_id == ID and not hub.scene_launch
    _wait(hub)
    assert hub.confirm() is None                                    # closes the replay: no take-off
    assert hub.screen == "hub" and hub.pane == "log"


def test_skipping_a_replayed_scene_returns_to_the_journal():
    hub = _hub(seen_paint=True)
    hub.pane = "log"
    hub.nav_v(1)
    hub.confirm()
    assert hub.back() and hub.screen == "hub" and hub.pane == "log"


# ------------------------------------------------------------------ drawing
def test_the_scene_draws_its_own_text_and_hints(run):
    hub = _hub()
    hub.confirm()
    hub.intro_t = 500.0
    hub.intro_pos = 99999.0
    hub.update(0.01)
    seen = []
    import story
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
    assert t("story_scene_last") in seen
    assert len({tuple(surf.get_at((x, y))) for x in range(0, 1280, 40) for y in range(0, 720, 40)}) > 20   # the picture is there
