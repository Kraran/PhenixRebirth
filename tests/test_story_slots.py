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
    assert hub.screen == "hub" and hub.slot_no == 1
    assert hub.state["name"] == "AB" and hub.state["mode"] == "veteran"
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
    assert hub.screen == "hub"
    assert hub.back() and hub.screen == "slots"                               # hangar -> slot list
    assert hub.summaries[0]["name"] == "NOVA"                                 # list refreshed


def test_resume_delete_and_refusals():
    ss.create_slot(1, "NOVA", "normal")
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
    assert g.story.screen == "hub" and g.story.state["mode"] == "veteran"
    assert ss.slot_summary(1)["name"] == "WASDZQ"


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
    assert g.story.slot_no == 2 and g.story.screen == "hub" and g.story.pane == "map"
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
