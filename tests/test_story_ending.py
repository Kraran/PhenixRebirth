"""Act IV - No Mercy Left: the open ending (scene -> film "theend" that waits for a key -> credits -> the workshop)."""
import os

import pygame
import pytest

import story as story_mod
import story_state as ss
from i18n import set_lang, t
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)


class FakeClip:
    """Stands for the ffmpeg player: a few frames, then it has ended."""
    def __init__(self, *a, **k):
        self.surface = pygame.Surface((8, 8))
        self.failed = False
        self.ready = True
        self.n = 0
        self.closed = False

    def pump(self):
        self.n += 1

    @property
    def ended(self):
        return self.n >= 3

    def close(self):
        self.closed = True


@pytest.fixture
def fake_clip(monkeypatch):
    monkeypatch.setattr(story_mod.videoclip, "ClipPlayer", FakeClip)
    monkeypatch.setattr(ss, "film_files", lambda fid: ("a.mp4", "a.ogg"))


def _hub(won=True, act=3):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["act"] = act
    if won:
        st.setdefault("flags", {}).update({ss.GAME_WON: True, "final_s4": True, "final_s5": True})
        st.setdefault("cleared", []).extend(["ch1_sortie", "final_5"])
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "map"
    return hub


def _ids(hub):
    return [m["id"] for m in hub.missions()]


def _to_film(hub):
    hub.start_ending()
    assert hub.screen == "intro" and hub.scene_id == ss.ENDING_MISSION
    hub.intro_t = 99
    while hub.screen == "intro":
        hub.intro_t = 99
        hub.confirm()
    assert hub.screen == "film" and hub.film_id == ss.ENDING_FILM
    assert hub._film_sound is None                               # no sound of its own: the music goes on
    for _ in range(6):
        hub.update(0.1)
    assert hub.film_wait


def test_assets_exist():
    for name in ("story/fin.jpg", "video/theend.mp4"):
        assert os.path.isfile(ss.asset_path(*name.split("/"))), name
    assert ss.film_files(ss.ENDING_FILM) is not None          # (no .ogg needed: the music of the ending plays over it)


def test_act4_is_on_the_map_only_once_triton_is_won():
    assert ss.ENDING_MISSION not in _ids(_hub(won=False))
    hub = _hub(won=True)
    ids = _ids(hub)
    assert ss.ENDING_MISSION in ids and "final_5" in ids          # next to Act 3
    assert ss.shown_acts(hub.state) == [3, 4]
    assert hub.mission_playable(ss.mission_by_id(ss.ENDING_MISSION))
    assert not ss.mission_playable(_hub(won=False).state, ss.mission_by_id(ss.ENDING_MISSION))


def test_text_has_the_pilot_name_and_the_title():
    set_lang("fr")
    text = t("story_scene_act4")
    assert "{name}" in text and "440 années-lumière" in text and text.rstrip().endswith("Le saut a commencé…")
    assert t("story_ch4") == "ACTE 4 — NO MERCY LEFT" and t("story_m_act4") == "Alcyone - Le Grand Saut"
    set_lang("en")
    assert "440 light-years" in t("story_scene_act4") and t("story_m_act4") != "story_m_act4"
    set_lang("fr")
    assert ss.scene_slides(ss.ENDING_MISSION) == [("fin", "story_scene_act4")]
    assert ss.STORY_SCENES[ss.ENDING_MISSION]["music"] == "lyra_no_mercy_left"


def test_the_mission_starts_the_ending_not_a_sortie(fake_clip):
    hub = _hub()
    hub.map_index = _ids(hub).index(ss.ENDING_MISSION)
    assert hub.confirm() is None
    assert hub.ending and hub.screen == "intro" and hub.scene_id == ss.ENDING_MISSION


def test_the_film_waits_for_a_press_then_the_credits(fake_clip):
    hub = _hub()
    _to_film(hub)
    assert hub.screen == "film" and hub._film is not None          # the last picture stays: no loop, no end
    for _ in range(20):
        hub.update(0.1)
    assert hub.screen == "film" and hub.take_door_request() is None
    hub.film_wait_t = 0.0
    assert not hub.film_waiting() and not hub.press()                # (a press right at the end is ignored)
    hub.film_wait_t = 5.0
    assert hub.film_waiting()
    assert hub.press()
    assert hub.take_door_request() == {"door": "credits", "scene": True}
    assert hub.screen == "film"                                    # the fade runs over the last picture
    hub.finish_scene("credits")
    assert hub.ending_credits and hub.pane == "hangar" and hub._film is None
    assert ss.ending_done(hub.state) and ss.ENDING_MISSION in hub.state["cleared"]
    hub.finish_ending()
    assert not hub.ending and hub.screen == "hub" and hub.pane == "hangar"


def test_b_skips_the_film_to_the_credits_too(fake_clip):
    hub = _hub()
    hub.start_ending()
    hub.intro_t = 99
    while hub.screen == "intro":
        hub.intro_t = 99
        hub.confirm()
    hub.back()                                                      # B / Esc during the film
    assert hub.take_door_request() == {"door": "credits", "scene": True}


def test_without_the_video_the_credits_come_at_once():
    hub = _hub()
    hub.start_ending()
    hub.intro_t = 99
    orig = ss.film_files
    try:
        ss.film_files = lambda fid: None
        while hub.screen == "intro":
            hub.intro_t = 99
            hub.confirm()
    finally:
        ss.film_files = orig
    assert hub.take_door_request() == {"door": "credits", "scene": True}


def test_after_the_ending_all_acts_and_missions_are_there(fake_clip):
    hub = _hub()
    before = [m["id"] for m in ss.MISSIONS if m.get("once") and m.get("acts") and not m.get("test")]
    _to_film(hub)
    hub.film_wait_t = 5.0
    hub.press()
    hub.finish_scene("credits")
    hub.finish_ending()
    state = hub.state
    assert ss.shown_acts(state) == [1, 2, 3, 4]
    ids = _ids(hub)
    assert ss.ENDING_MISSION in ids and "ch1_sortie" in ids and "final_5" in ids
    acts = {a for m in hub.missions() if (a := ss.map_act(state, m))}
    assert acts == {1, 2, 3, 4}
    for mid in ("ch1_sortie", "final_5", ss.ENDING_MISSION):
        assert mid in state["cleared"] and ss.mission_playable(state, ss.mission_by_id(mid)), mid
    # the intro is kept in the journal
    entries = ss.journal_entries(state)
    assert {"scene": ss.ENDING_MISSION} in entries and {"film": ss.ENDING_FILM} in entries
    assert before                                                   # (there were once-only missions to open up)


def test_nothing_is_replayable_before_the_ending():
    hub = _hub()
    assert not ss.mission_playable(hub.state, ss.mission_by_id("final_5"))


def test_fine_cheat_starts_the_ending_and_saves_nothing(fake_clip):
    hub = _hub(won=False, act=1)
    for c in "FINE":
        hub.feed_cheat(c)
    assert hub.cheating and hub.ending and hub.screen == "intro" and hub.scene_id == ss.ENDING_MISSION
    hub.intro_t = 99
    while hub.screen == "intro":
        hub.intro_t = 99
        hub.confirm()
    for _ in range(6):
        hub.update(0.1)
    hub.film_wait_t = 5.0
    hub.press()
    hub.finish_scene("credits")
    hub.finish_ending()
    assert not ss.ending_done(hub.state)                            # (in memory only)
    on_disk = ss.load_state(ss.story_path(1))
    assert not ss.ending_done(on_disk) and not ss.flag(on_disk, ss.scene_flag(ss.ENDING_MISSION))


def test_fine_only_works_on_the_map():
    hub = _hub(won=False, act=1)
    hub.pane = "hangar"
    for c in "FINE":
        hub.feed_cheat(c)
    assert not hub.ending and not hub.cheating


def test_the_whole_ending_in_the_game(run, fake_clip):
    """Scene, film, fade, credits (with the music of the ending), B: back to the workshop."""
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["act"] = 3
    st.setdefault("flags", {})[ss.GAME_WON] = True
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.pane = "map"
    g.menu_screen = "story_hub"
    g.started = False
    g.input_grace = 0.0
    g.fade_phase = None
    played = []
    real = g.sounds.play_music
    g.sounds.play_music = lambda key, *a, **k: (played.append(key), real(key, *a, **k))[1]
    story = g.story
    story.start_ending()
    story.intro_t = 99
    run.frames(2)
    assert ss.ENDING_MUSIC in played
    while story.screen == "intro":
        story.intro_t = 99
        story.confirm()
    for _ in range(8):
        run.frames(4)
        story.update(0.1)
    assert story.film_wait
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x, unicode="x", mod=0, scancode=0))
    story.film_wait_t = 5.0
    run.frames(1)
    for _ in range(200):
        run.frames(1)
        if g.menu_screen == "credits":
            break
    assert g.menu_screen == "credits" and story.ending_credits
    played.clear()
    run.frames(5)
    assert set(played) <= {ss.ENDING_MUSIC}
    g.input_grace = 0.0
    g._menu_back()
    run.frames(3)
    assert g.menu_screen == "story_hub" and story.pane == "hangar" and not story.ending
    assert ss.ending_done(story.state)
