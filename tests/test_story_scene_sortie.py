"""Story scene of the very first sortie: the blue birds over Mars, told the first time it is launched."""
import os

import pygame

import story_state as ss
from i18n import t
from settings import asset_path
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

ID = "ch1_sortie"


def _hub(seen=False, seen_others=(), log=()):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["log"] = list(log)
    if seen:
        ss.mark_scene_seen(st, ID)
    for other in seen_others:
        ss.mark_scene_seen(st, other)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "map"
    hub.map_index = [m["id"] for m in hub.missions()].index(ID)
    return hub


def _wait(hub, seconds=1.0):
    for _ in range(int(seconds / 0.25) + 1):
        hub.update(0.25)


# ------------------------------------------------------------------ the scene itself
def test_the_first_sortie_has_a_scene_with_its_picture_and_text():
    scene = ss.scene_of(ID)
    assert scene and len(scene["slides"]) == 1
    pic, key = scene["slides"][0]
    assert pic == "oiseaux_bleus" and os.path.exists(asset_path("story", pic + ".jpg"))
    text = t(key)
    assert text.startswith("Mars brûle de son éternel rouge ; là-bas somnole le NX01.")
    assert text.endswith("Sinon… eh bien, je n’aurai plus à m’en soucier.")
    assert text.count("\n\n") == 2                                 # three paragraphs, with a pause between
    for word in ("Phobos", "Avioïdes", "oiseaux bleus", "armes à plasma", "Kamarasov", "premier jeu de données"):
        assert word in text


def test_the_text_is_exactly_the_one_given():
    paragraphs = t("story_scene_sortie").split("\n\n")
    assert paragraphs[0].endswith("et de ces lueurs rouges qui couvent dans leurs yeux et dans leur poitrine.")
    assert paragraphs[1] == ("Personne ne sait ce qu’ils cherchent. Ils ne communiquent pas, ils n’exigent rien. "
                             "Ils patrouillent, ils plongent, ils déchirent. Avec leurs ailes de cuir tendu, leurs serres "
                             "incandescentes et leurs armes à plasma, ils ont mis en pièces plus de Shields que je n’ai "
                             "d’heures de vol. Ce sont les éclaireurs de la horde, les plus rapides, les plus nombreux, "
                             "et c’est toujours par eux que tout commence.")
    assert paragraphs[2].startswith("Alors tant pis si le NX01 tient à peine en l’air. Il faut bien commencer par quelque part.")


def test_the_title_and_text_are_in_every_language_table():
    from i18n import T, LANG_CODES
    for key in ("story_scene_sortie", "story_scene_sortie_t"):
        assert set(T[key]) == set(LANG_CODES) and t(key)
    assert t("story_scene_sortie_t") == "Première sortie : les oiseaux bleus"


def test_the_picture_is_the_one_given():
    img = pygame.image.load(asset_path("story", "oiseaux_bleus.jpg"))
    assert img.get_size() == (1792, 1008)


def test_the_scenes_come_in_the_order_of_the_story():
    assert list(ss.SCENES) == [ID, "dome_1", "paint_1"]
    st = ss.create_slot(1, "A", "normal")
    ss.mark_scene_seen(st, "paint_1")
    ss.mark_scene_seen(st, ID)
    assert ss.scenes_seen(st) == [ID, "paint_1"] and not ss.scene_seen(st, "dome_1")


# ------------------------------------------------------------------ the first launch
def test_the_very_first_launch_shows_the_scene_without_any_cheat():
    hub = _hub()
    assert not hub.cheat_unlock and hub.mission_playable(hub._mission())
    assert hub.confirm() is None
    assert hub.screen == "intro" and hub.scene_id == ID and hub.scene_launch
    assert hub.intro_slides == ss.scene_of(ID)["slides"]
    assert not ss.scene_seen(hub.state, ID)


def test_the_end_of_the_scene_flies_the_mission_and_remembers_it():
    hub = _hub()
    hub.confirm()
    _wait(hub)
    spec = hub.confirm()
    assert isinstance(spec, dict) and spec["launch"] and spec["id"] == ID and spec["level"] == 1
    assert hub.screen == "hub" and hub.scene_id is None
    assert ss.scene_seen(hub.state, ID)
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
    hub.save()
    again = StoryHub()
    again.open_slot(1)
    assert ss.scene_seen(again.state, ID)


def test_a_replayed_sortie_does_not_show_the_scene_again():
    hub = _hub(seen=True)
    spec = hub.confirm()
    assert isinstance(spec, dict) and spec["id"] == ID and hub.screen == "hub"


def test_the_other_scenes_do_not_stand_in_for_this_one():
    hub = _hub(seen_others=("dome_1", "paint_1"))
    hub.confirm()
    assert hub.screen == "intro" and hub.scene_id == ID


def test_the_other_bestiary_missions_fly_straight_away():
    hub = _hub()
    hub.cheat_unlock = True
    hub.map_index = [m["id"] for m in hub.missions()].index("best_s2")
    spec = hub.confirm()
    assert isinstance(spec, dict) and spec["id"] == "best_s2" and hub.screen == "hub"


# ------------------------------------------------------------------ the journal
def test_the_journal_has_no_line_before_the_scene_is_seen():
    hub = _hub()
    hub.pane = "log"
    assert hub.log_entries() == [{"intro": True}]


def test_the_replay_line_comes_first_after_the_intro():
    hub = _hub(seen=True, seen_others=("dome_1", "paint_1"), log=[{"key": "story_log_sortie"}])
    entries = hub.log_entries()
    assert entries[:5] == [{"intro": True}, {"scene": ID}, {"scene": "dome_1"}, {"scene": "paint_1"},
                           {"key": "story_log_sortie"}]
    assert ss.log_text(entries[1], t) == "Revoir : Première sortie : les oiseaux bleus"


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
    assert t("story_scene_last") in seen
    assert len({tuple(surf.get_at((x, y))) for x in range(0, 1280, 40) for y in range(0, 720, 40)}) > 20
