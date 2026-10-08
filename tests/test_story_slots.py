"""Adventure save slots: slot list, pilot name, mode, delete (logic and real input)."""
import os

import pygame
import pytest

import story_state as ss
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def clean_slots():
    def wipe():
        for i in range(1, ss.SLOT_COUNT + 1):
            for suffix in ("", ".corrupt"):
                try:
                    os.remove(ss.story_path(i) + suffix)
                except OSError:
                    pass
    wipe()
    yield
    wipe()


# ------------------------------------------------------------------ name rules
def test_name_is_cleaned_like_an_arcade_name():
    assert ss.clean_name("  éric  le  roux ") == "ERIC LE ROUX"
    assert ss.clean_name("a" * 30) == "A" * ss.NAME_MAX
    assert ss.clean_name("n0va!?#") == "N0VA"
    assert ss.clean_name("") == "" and ss.clean_name(None) == ""
    assert ss.clean_name("JEAN-LUC") == "JEAN-LUC"


def test_name_entry_typing_limits_and_spaces():
    e = ss.NameEntry()
    assert not e.type_char(" ")                          # no leading space
    for c in "nova":
        assert e.type_char(c)
    assert e.type_char(" ") and not e.type_char(" ")     # one space at a time
    assert not e.type_char("é!") and e.type_char("é")    # accent becomes E
    assert e.text == "NOVA E"
    for _ in range(20):
        e.type_char("x")
    assert len(e.text) == ss.NAME_MAX
    e.backspace()
    assert len(e.text) == ss.NAME_MAX - 1


def test_name_entry_cursor_wraps_and_presses_keys():
    e = ss.NameEntry()
    e.move(-1, 0)
    assert e.token == "J"                                # wraps to the end of the row
    e.move(0, -1)
    assert e.token == "OK"                               # wraps to the last row
    assert e.press() == "empty"                          # OK with no name
    e.move(-1, 0)                                        # DEL, still nothing to delete
    e.press()
    e.row, e.col = 0, 0
    assert e.press() is None and e.text == "A"
    e.row, e.col = 3, 7
    assert e.token == "SPACE"
    e.press()
    assert e.text == "A "                                # a trailing space is kept while typing ...
    assert e.name == "A"                                 # ... and dropped from the final name
    e.row, e.col = 3, 8
    e.press()                                            # DEL
    e.press()
    assert e.text == ""
    e.type_char("z")
    e.row, e.col = 3, 9
    assert e.press() == "ok" and e.name == "Z"


# ------------------------------------------------------------------ save slots
def test_slot_files_summaries_create_delete():
    assert [s["status"] for s in ss.all_summaries()] == ["missing"] * 3
    st = ss.create_slot(2, "  nova ", "veteran")
    assert st["name"] == "NOVA" and st["mode"] == "veteran"
    info = ss.slot_summary(2)
    assert (info["status"], info["name"], info["mode"], info["act"]) == ("ok", "NOVA", "veteran", 1)
    assert len(info["date"]) == 10 and info["date"][2] == "/"
    assert ss.slot_summary(1)["status"] == "missing"
    assert ss.create_slot(3, "x", "godlike")["mode"] == "normal"      # unknown mode -> normal
    assert ss.delete_slot(2) is True and ss.delete_slot(2) is False
    assert ss.slot_summary(2)["status"] == "missing"


def test_damaged_and_fallen_slots():
    with open(ss.story_path(1), "w", encoding="utf-8") as f:
        f.write("{broken")
    assert ss.slot_summary(1)["status"] == "damaged"
    assert os.path.isfile(ss.story_path(1))                            # looking never touches the file
    assert not os.path.isfile(ss.story_path(1) + ".corrupt")
    st = ss.create_slot(2, "ZED", "veteran")
    st["fallen"] = True
    ss.save_state(ss.story_path(2), st)
    assert ss.slot_summary(2)["fallen"] is True
    assert ss.slot_summary(3)["fallen"] is False


def test_format_date():
    assert ss.format_date("2026-10-08T11:21:05") == "08/10/2026"
    assert ss.format_date("") == "" and ss.format_date("nonsense") == ""


# ------------------------------------------------------------- hub flow (no Game)
def _type(hub, text):
    for ch in text:
        hub.entry.type_char(ch)


def test_new_adventure_flow_with_the_pad_only():
    hub = StoryHub()
    hub.open_slots()
    assert hub.screen == "slots" and hub.sel == 0
    hub.confirm()                                        # empty slot -> name
    assert hub.screen == "name"
    hub.confirm()                                        # A on "A" key
    hub.nav_h(1); hub.confirm()                          # "B"
    assert hub.entry.text == "AB"
    hub.nav_v(-1)                                        # up from row 0 wraps to the last row
    hub.nav_h(-1)                                        # DEL
    hub.entry.row, hub.entry.col = 3, 9                  # OK
    hub.confirm()
    assert hub.screen == "mode" and hub.new_name == "AB"
    hub.nav_h(1)                                         # veteran
    hub.confirm()
    assert hub.screen == "intro" and hub.slot_no == 1    # the story comes first
    assert hub.state["name"] == "AB" and hub.state["mode"] == "veteran"
    for _ in range(len(hub.intro_slides)):               # A on every slide
        hub.update(0.25); hub.update(0.25)
        hub.confirm()
    assert hub.screen == "hub" and ss.intro_seen(hub.state)
    assert ss.slot_summary(1)["status"] == "ok"


def test_ok_with_no_name_stays_and_explains():
    hub = StoryHub()
    hub.open_slots()
    hub.confirm()
    hub.entry.row, hub.entry.col = 3, 9
    hub.confirm()
    assert hub.screen == "name" and hub.msg


def test_back_walks_up_one_screen_at_a_time():
    hub = StoryHub()
    hub.open_slots()
    hub.confirm(); _type(hub, "NOVA"); hub._submit_name()
    assert hub.screen == "mode"
    assert hub.back() and hub.screen == "name" and hub.entry.text == "NOVA"   # name is kept
    assert hub.back() and hub.screen == "slots"
    assert ss.slot_summary(1)["status"] == "missing"                          # nothing created
    assert hub.back() is False                                                # leave the Adventure
    hub.confirm(); _type(hub, "NOVA"); hub._submit_name(); hub.confirm()
    assert hub.screen == "intro"
    assert hub.back() and hub.screen == "hub"                                 # B skips the intro
    assert hub.back() and hub.screen == "slots"                               # hangar -> slot list
    assert hub.summaries[0]["name"] == "NOVA"                                 # list refreshed


def test_resume_delete_and_refusals():
    seen = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(seen)
    ss.save_state(ss.story_path(1), seen)
    done = ss.create_slot(2, "ZED", "veteran"); done["fallen"] = True
    ss.save_state(ss.story_path(2), done)
    with open(ss.story_path(3), "w", encoding="utf-8") as f:
        f.write("{broken")
    hub = StoryHub()
    hub.open_slots()
    hub.nav_v(1); hub.confirm()                          # fallen: cannot be opened
    assert hub.screen == "slots" and hub.msg
    hub.nav_v(1); hub.confirm()                          # damaged: cannot be opened
    assert hub.screen == "slots" and hub.msg
    hub.nav_v(-1); hub.nav_v(-1)
    hub.confirm()                                        # resume slot 1
    assert hub.screen == "hub" and hub.state["name"] == "NOVA" and hub.slot_no == 1
    hub.back()
    hub.nav_h(1); hub.confirm()                          # DELETE button -> confirmation
    assert hub.screen == "delete" and hub.del_yes is False
    hub.confirm()                                        # default answer is NO
    assert hub.screen == "slots" and ss.slot_summary(1)["status"] == "ok"
    hub.confirm(); hub.nav_h(1); hub.confirm()           # DELETE, YES
    assert hub.screen == "slots" and ss.slot_summary(1)["status"] == "missing"
    assert hub.summaries[0]["status"] == "missing"


def test_delete_button_is_only_on_filled_slots():
    hub = StoryHub()
    hub.open_slots()
    hub.nav_h(1)
    assert hub.col == 0                                  # empty slot: nothing to the right


def test_a_slot_is_saved_in_its_own_file():
    hub = StoryHub()
    hub.open_slots()
    hub.sel = 2
    hub.confirm(); _type(hub, "ONE"); hub._submit_name(); hub.confirm()
    hub.state["credits"] = 123
    hub.save()
    assert os.path.isfile(ss.story_path(3)) and not os.path.isfile(ss.story_path(1))
    other = StoryHub()
    other.open_slot(3)
    assert other.state["credits"] == 123 and other.state["name"] == "ONE"


def test_hub_without_a_slot_never_writes_a_file():
    hub = StoryHub()                                     # tests and replays drive it like this
    hub.state["credits"] = 5
    hub.save()
    assert all(not os.path.isfile(ss.story_path(i)) for i in range(1, 4))


# ------------------------------------------------------- real keyboard / pad events
def _key(key, ch=""):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=ch, mod=0, scancode=0))


def _open_adventure(g):
    g.menu_screen = "main"
    g.menu_index = 1
    g.input_grace = 0
    g._menu_confirm()
    assert g.menu_screen == "story_hub" and g.story.screen == "slots"


def test_keyboard_typing_does_not_trigger_menu_keys(run):
    g = run.game
    _open_adventure(g)
    _key(pygame.K_RETURN, "\r"); run.frames(2)
    assert g.story.screen == "name"
    for ch, k in (("w", pygame.K_w), ("a", pygame.K_a), ("s", pygame.K_s), ("d", pygame.K_d),
                  ("z", pygame.K_z), ("q", pygame.K_q), (" ", pygame.K_SPACE), ("é", pygame.K_e)):
        _key(k, ch)
    run.frames(3)
    assert g.story.entry.text == "WASDZQ E"               # every letter went into the name
    assert g.menu_screen == "story_hub" and g.story.screen == "name"
    _key(pygame.K_BACKSPACE); run.frames(2)
    assert g.story.entry.text == "WASDZQ "
    _key(pygame.K_RETURN, "\r"); run.frames(2)
    assert g.story.screen == "mode" and g.story.new_name == "WASDZQ"
    _key(pygame.K_RIGHT); run.frames(2)
    _key(pygame.K_RETURN, "\r"); run.frames(2)
    assert g.story.screen == "intro" and g.story.state["mode"] == "veteran"
    assert ss.slot_summary(1)["name"] == "WASDZQ"
    _key(pygame.K_ESCAPE); run.frames(2)                  # Esc skips the story
    assert g.story.screen == "hub" and g.menu_screen == "story_hub"


def test_escape_and_pad_back_leave_step_by_step(run):
    g = run.game
    _open_adventure(g)
    g._menu_confirm()                                    # pad A: name entry
    assert g.story.screen == "name"
    pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=1, instance_id=0, joy=0))
    run.frames(2)                                        # pad B
    assert g.story.screen == "slots" and g.menu_screen == "story_hub"
    _key(pygame.K_ESCAPE); run.frames(2)
    assert g.menu_screen == "main" and g.menu_index == 1


def test_pad_a_and_dpad_drive_the_name_screen(run):
    g = run.game
    _open_adventure(g)
    pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=0, instance_id=0, joy=0)); run.frames(2)
    assert g.story.screen == "name"
    g._menu_adjust(1); g._menu_confirm()                 # right, A  -> "B"
    g._menu_nav(1); g._menu_confirm()                    # down, A   -> "L"
    assert g.story.entry.text == "BL"


def test_delete_key_asks_before_deleting(run):
    ss.create_slot(1, "NOVA", "normal")
    g = run.game
    _open_adventure(g)
    _key(pygame.K_DELETE); run.frames(2)
    assert g.story.screen == "delete" and ss.slot_summary(1)["status"] == "ok"


def test_quitting_a_mission_keeps_the_open_slot(run):
    ss.create_slot(2, "NOVA", "normal")
    g = run.game
    _open_adventure(g)
    g.story.open_slot(2)
    g.story.pane = "map"
    g.story.map_index = 0
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    run.frames(10)
    g._quit_to_menu()
    assert g.menu_screen == "story_hub"
    assert g.story.slot_no == 2 and g.story.screen == "hub" and g.story.pane == "hangar"
    assert g.story.state["name"] == "NOVA"
    assert os.path.isfile(ss.story_path(2))


def test_mission_result_is_saved_in_the_open_slot(run):
    ss.create_slot(1, "NOVA", "normal")
    g = run.game
    g.story.open_slot(1)
    g.story.map_index = 0
    g._begin_adventure(g.story._launch_selected())
    run.frames(5)
    g.score = 777
    g._end_adventure(True)
    back = StoryHub()
    back.open_slot(1)
    assert back.state["credits"] == 777 and "ch1_sortie" in back.state["cleared"]


# ------------------------------------------------------------ failure rules in the game
def _start_mission(g, slot, name="NOVA", mode="normal", credits=0):
    st = ss.create_slot(slot, name, mode)
    st["credits"] = credits
    ss.save_state(ss.story_path(slot), st)
    g.story.open_slot(slot)
    g.story.map_index = 0
    g._begin_adventure(g.story._launch_selected())


def test_failed_mission_in_normal_mode_loses_a_fifth_of_the_credits(run):
    g = run.game
    _start_mission(g, 1, credits=1000)
    g.score = 130                                         # what you scored does not matter
    g._end_adventure(False)
    assert g.menu_screen == "story_hub" and g.story.screen == "hub" and g.story.pane == "map"
    assert g.story.state["credits"] == 800
    assert "200" in g.story.toast
    again = StoryHub()
    again.open_slot(1)
    assert again.state["credits"] == 800                  # saved in the slot


def test_failed_veteran_mission_ends_the_adventure(run):
    g = run.game
    _start_mission(g, 2, name="ZED", mode="veteran", credits=300)
    g._end_adventure(False)
    assert g.menu_screen == "story_hub" and g.story.screen == "slots"
    assert "ZED" in g.story.msg
    assert g.story.summaries[1]["fallen"] is True
    g.story.sel = 1
    g.story.confirm()                                     # a memorial cannot be reopened
    assert g.story.screen == "slots" and g.story.msg


def test_quitting_a_veteran_mission_changes_nothing(run):
    g = run.game
    _start_mission(g, 3, name="ZED", mode="veteran", credits=300)
    run.frames(10)
    g.score = 500
    g._quit_to_menu()
    assert g.menu_screen == "story_hub" and g.story.screen == "hub" and g.story.pane == "hangar"
    assert g.story.slot_no == 3 and g.story.state["credits"] == 300
    assert ss.slot_summary(3)["fallen"] is False
    assert g.story.state["cleared"] == []


def test_quitting_a_normal_mission_changes_nothing_and_returns_to_the_hangar(run):
    g = run.game
    _start_mission(g, 1, credits=1000)
    run.frames(10)
    g.score = 400                                         # points of the abandoned run are not kept
    g._quit_to_menu()
    assert g.story.screen == "hub" and g.story.pane == "hangar" and g.story.slot_no == 1
    assert g.story.state["credits"] == 1000
    assert g.story.state["cleared"] == [] and g.story.state["log"] == []
    again = StoryHub()
    again.open_slot(1)
    assert again.state["credits"] == 1000


def test_quitting_after_the_win_still_banks_the_mission(run):
    g = run.game
    _start_mission(g, 1, credits=10)
    run.frames(5)
    g.score = 150
    g.stage_transition = "fly_up"
    g._quit_to_menu()
    assert g.story.state["credits"] == 160 and "ch1_sortie" in g.story.state["cleared"]


def test_cleared_mission_still_banks_the_score(run):
    g = run.game
    _start_mission(g, 1, credits=10)
    g.score = 150
    g._end_adventure(True)
    assert g.story.state["credits"] == 160 and "ch1_sortie" in g.story.state["cleared"]


# ------------------------------------------------------------ hangar: the Phenix slot
def _hub_in_hangar(slot=1):
    ss.create_slot(slot, "NOVA", "normal")
    hub = StoryHub()
    hub.open_slot(slot)
    return hub


def test_the_second_hull_cannot_be_selected_in_act_1():
    hub = _hub_in_hangar()
    assert hub.pane == "hangar" and hub.zone == "slots"
    hub.nav_h(1)                                          # right: goes to the next screen, not slot 2
    assert hub.state["selected_slot"] == 0
    assert hub.pane == "map"


def test_a_bad_selected_slot_is_reset_when_the_hangar_opens():
    st = ss.create_slot(1, "NOVA", "normal")
    st["selected_slot"] = 1                               # hull not owned
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    assert hub.state["selected_slot"] == 0


def test_the_second_hull_can_be_selected_once_owned():
    st = ss.create_slot(1, "NOVA", "normal")
    st["slots"][1]["owned"] = True                        # what the later acts will do
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.nav_h(1)
    assert hub.state["selected_slot"] == 1 and hub.pane == "hangar"


def test_the_empty_second_hull_does_not_name_the_phenix():
    import pygame
    from i18n import t
    pygame.font.init()
    hub = _hub_in_hangar()
    texts = []

    def spy(surface, font, text, *a, **k):
        texts.append(str(text))
        return font.render(str(text), True, (255, 255, 255))

    import story
    real = story._text
    story._text = spy
    try:
        surf = pygame.Surface((1280, 720))
        font = pygame.font.SysFont("dejavusans,arial,sans", 24, bold=True)
        hub._draw_hangar(surf, font, font, font)
    finally:
        story._text = real
    shown = " ".join(texts).upper()
    assert "SLOT 2" in shown and t("story_hull_empty") in texts
    assert "PHENIX" not in shown and "PHOENIX" not in shown and "CHAPITRE" not in shown


# ------------------------------------------------------------ the story intro
def _new_hub(mode_index=0, name="NOVA"):
    ss.delete_slot(1)                                      # always start from an empty first slot
    hub = StoryHub()
    hub.open_slots()
    hub.confirm(); _type(hub, name); hub._submit_name()
    hub.mode_index = mode_index
    hub.confirm()
    assert hub.screen == "intro"
    return hub


def _wait(hub, seconds):
    for _ in range(int(seconds / 0.25) + 1):
        hub.update(0.25)


def test_intro_has_four_slides_and_veteran_changes_only_the_last():
    normal = ss.intro_slides("normal")
    veteran = ss.intro_slides("veteran")
    assert len(normal) == len(veteran) == 4
    assert normal[:3] == veteran[:3]
    assert normal[3] != veteran[3]
    assert normal[3] == ("kamarasov", "story_intro_4")
    assert veteran[3] == ("kamarasov_veteran", "story_intro_4v")
    assert ss.intro_slides("godlike") == normal            # unknown mode: the Normal story


def test_every_intro_picture_exists():
    import os
    from settings import asset_path
    for mode in ss.MODES:
        for pic, _key in ss.intro_slides(mode):
            assert os.path.isfile(asset_path("story", pic + ".jpg")), pic


def test_the_last_sentence_carries_the_pilot_name():
    from i18n import t
    for mode, must in (("normal", "j'en suis maintenant certain"), ("veteran", "j'en suis maintenant certain")):
        key = ss.INTRO_LAST[mode][1]
        lines = ss.intro_lines(t, key, "ZED")
        assert "{name}" not in " ".join(lines)
        assert lines[-1].endswith("moi, ZED, " + must + "."), lines[-1]


def test_the_veteran_story_tells_how_kamarasov_died_and_the_normal_one_does_not():
    from i18n import t
    vet = " ".join(ss.intro_lines(t, "story_intro_4v", "ZED"))
    nor = " ".join(ss.intro_lines(t, "story_intro_4", "ZED"))
    assert "drone espion" in vet and "peu d'espoir" in vet
    assert "drone" not in nor and "L'espoir renaît" in nor


def test_intro_runs_after_the_mode_choice_with_the_right_story():
    normal = _new_hub(0)
    assert normal.intro_slides[-1][0] == "kamarasov"
    vet = _new_hub(1, name="ZED")
    assert vet.intro_slides[-1][0] == "kamarasov_veteran"
    assert ss.intro_seen(vet.state) is False               # not seen until it is over


def test_a_key_right_at_the_start_does_not_skip_a_slide():
    hub = _new_hub()
    hub.confirm()                                          # the same press that left the mode screen
    assert hub.intro_index == 0
    _wait(hub, 0.5)
    hub.confirm()
    assert hub.intro_index == 1 and hub.intro_t == 0.0


def test_action_button_walks_the_slides_then_opens_the_hangar():
    hub = _new_hub()
    seen = []
    for _ in range(10):
        if hub.screen != "intro":
            break
        seen.append(hub.intro_index)
        _wait(hub, 0.5)
        hub.confirm()
    assert seen == [0, 1, 2, 3]
    assert hub.screen == "hub" and hub.pane == "hangar"
    assert ss.intro_seen(hub.state)
    assert ss.load_state(ss.story_path(1))["flags"]["intro_seen"] is True      # saved


def test_back_skips_the_whole_intro_at_once():
    hub = _new_hub()
    assert hub.back() is True and hub.screen == "hub" and ss.intro_seen(hub.state)


def test_the_intro_is_shown_once_per_adventure():
    hub = _new_hub()
    hub.back()
    hub.open_slots()
    hub.sel = 0
    hub.confirm()                                          # reopen the slot
    assert hub.screen == "hub"


def test_a_save_that_never_saw_the_intro_plays_it_when_opened():
    ss.create_slot(2, "OLD", "normal")                     # as if the game was closed during the intro
    hub = StoryHub()
    hub.open_slots()
    hub.sel = 1
    hub.confirm()
    assert hub.screen == "intro" and hub.slot_no == 2


def test_back_from_a_mission_does_not_replay_the_intro(run):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.save_state(ss.story_path(1), st)                    # intro not marked on purpose
    g.story.open_slot(1)
    g.story.map_index = 0
    g._begin_adventure(g.story._launch_selected())
    run.frames(5)
    g._quit_to_menu()
    assert g.story.screen == "hub"


def test_intro_scroll_rises_then_rests(run):
    hub = _new_hub()
    block_h = 900
    assert hub._intro_top(block_h) == 720                  # starts below the screen
    _wait(hub, 1.0)
    assert 600 < hub._intro_top(block_h) < 720             # now rising
    _wait(hub, 60)
    assert hub.intro_finished_scrolling(block_h)
    assert hub._intro_top(block_h) == 720 - 96 - block_h   # last line rests above the hint
    small = 200
    _wait(hub, 60)
    assert hub._intro_top(small) == (720 - small) // 2     # a short text rests in the middle


def test_every_slide_draws_in_both_modes(run):
    import pygame
    g = run.game
    font = g.font
    for mode_index in (0, 1):
        hub = _new_hub(mode_index)
        for i in range(len(hub.intro_slides)):
            hub.intro_index = i
            hub.intro_t = 0.0
            surf = pygame.Surface((1280, 720))
            hub.draw(surf, font, g.medium_font, font)       # fading in
            hub.intro_t = 500.0
            hub.draw(surf, font, g.medium_font, font)       # resting
            assert surf.get_at((640, 360)) != (0, 0, 0, 255) or surf.get_at((100, 100)) != (0, 0, 0, 255)


def test_the_text_comes_from_the_language_table():
    from i18n import t, T, LANG_CODES
    for key in ("story_intro_1", "story_intro_2", "story_intro_3", "story_intro_4", "story_intro_4v",
                "story_intro_hint", "story_intro_last"):
        assert set(T[key]) == set(LANG_CODES) and t(key)


def test_the_game_loop_advances_the_intro_clock(run):
    g = run.game
    _open_adventure(g)
    ss.delete_slot(1)
    g.story.open_slots()
    _key(pygame.K_RETURN, "\r"); run.frames(2)
    for ch, k in (("n", pygame.K_n), ("o", pygame.K_o)):
        _key(k, ch)
    run.frames(2)
    _key(pygame.K_RETURN, "\r"); run.frames(2)            # name -> mode
    _key(pygame.K_RETURN, "\r"); run.frames(2)            # mode -> intro
    assert g.story.screen == "intro"
    _key(pygame.K_RETURN, "\r"); run.frames(2)
    assert g.story.intro_index == 0                       # too early: the first press is ignored
    before = g.story.intro_t
    run.frames(60)
    assert g.story.intro_t > before                       # the game loop runs the clock
    _key(pygame.K_RETURN, "\r"); run.frames(2)
    assert g.story.intro_index == 1
