"""Back from MAME, the game window must really get the focus: the steps are checked with a fake Windows."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import errlog  # noqa: E402
import window_focus  # noqa: E402
from window_focus import SW_RESTORE, SW_SHOW, bring_to_front  # noqa: E402

GAME, OTHER = 100, 200


class FakeWindows:
    """Windows' rule: SetForegroundWindow works only if the caller is attached to the input of the window in front
    (or after the Alt tap). `refuse` makes it refuse that many calls whatever happens."""

    def __init__(self, front=OTHER, need_attach=True, refuse=0, iconic=False):
        self.front, self.need_attach, self.refuse, self.iconic = front, need_attach, refuse, iconic
        self.attached, self.alt_tapped, self.log = False, False, []

    def get_foreground(self):
        return self.front

    def thread_of(self, hwnd):
        return 7 if hwnd == OTHER else 5

    def current_thread(self):
        return 5

    def attach(self, tid, to_tid, on):
        self.log.append(("attach", on))
        self.attached = on
        return True

    def is_iconic(self, hwnd):
        return self.iconic

    def show(self, hwnd, cmd):
        self.log.append(("show", cmd))

    def set_topmost(self, hwnd, on):
        self.log.append(("topmost", on))

    def bring_to_top(self, hwnd):
        self.log.append(("top",))

    def set_foreground(self, hwnd):
        self.log.append(("foreground",))
        if self.refuse > 0:
            self.refuse -= 1
            return
        if self.attached or self.alt_tapped or not self.need_attach:
            self.front = hwnd

    def set_active(self, hwnd):
        self.log.append(("active",))

    def set_focus(self, hwnd):
        self.log.append(("focus",))

    def alt_tap(self):
        self.log.append(("alt",))
        self.alt_tapped = True


def _run(api, **kw):
    sleeps = []
    ok = bring_to_front(GAME, api=api, sleep=sleeps.append, **kw)
    return ok, sleeps


def test_a_plain_call_is_not_enough_when_another_window_is_in_front():
    api = FakeWindows()
    api.need_attach = True
    ok, _ = _run(api)
    assert ok and api.front == GAME
    assert ("attach", True) in api.log                        # it got the input of the window in front first


def test_the_input_is_detached_again_even_when_a_call_fails():
    api = FakeWindows()
    api.set_focus = lambda hwnd: (_ for _ in ()).throw(RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        _run(api)
    assert api.attached is False                              # never left attached to the other window


def test_nothing_is_done_when_the_game_is_already_in_front():
    api = FakeWindows(front=GAME)
    ok, sleeps = _run(api)
    assert ok and api.log == [] and sleeps == []


def test_it_tries_again_when_windows_refuses_at_first():
    api = FakeWindows(refuse=2)
    ok, sleeps = _run(api)
    assert ok and len(sleeps) == 2                            # waited between the tries, then it worked


def test_it_gives_up_after_the_tries_and_says_so():
    api = FakeWindows(refuse=99)
    ok, sleeps = _run(api, tries=4)
    assert ok is False and len(sleeps) == 4
    assert sum(1 for c in api.log if c == ("foreground",)) == 4


def test_the_alt_tap_is_the_last_resort_not_the_first_move():
    api = FakeWindows(refuse=1)
    _run(api)
    assert ("alt",) not in api.log                            # the second try worked without it
    api = FakeWindows(need_attach=True, refuse=2)
    api.attach = lambda *a: False                             # attaching fails: only the Alt tap is left
    ok, _ = _run(api)
    assert ok and ("alt",) in api.log
    first_alt = api.log.index(("alt",))
    assert [c for c in api.log[:first_alt] if c == ("foreground",)].__len__() >= 2


def test_a_minimised_window_is_restored_and_a_normal_one_is_not():
    api = FakeWindows(iconic=True)
    _run(api)
    assert ("show", SW_RESTORE) in api.log and ("show", SW_SHOW) not in api.log
    api = FakeWindows()
    _run(api)
    assert ("show", SW_SHOW) in api.log and ("show", SW_RESTORE) not in api.log


def test_the_window_gets_the_whole_set_of_calls():
    api = FakeWindows()
    _run(api)
    names = [c[0] for c in api.log]
    for needed in ("topmost", "top", "foreground", "active", "focus"):
        assert needed in names
    tops = [c for c in api.log if c[0] == "topmost"]
    assert tops == [("topmost", True), ("topmost", False)]    # in front for a moment, then an ordinary window again


def test_nothing_in_front_at_all_does_not_attach():
    api = FakeWindows(front=0, need_attach=False)
    ok, _ = _run(api)
    assert ok and ("attach", True) not in api.log


# --- the way the game uses it ---------------------------------------------------------------------------------

def test_focus_pygame_window_reports_a_failure_in_the_log(tmp_path, monkeypatch):
    import addon
    import pygame

    monkeypatch.setattr(errlog.settings, "user_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(errlog, "_seen", {})
    monkeypatch.setattr(errlog, "_started", False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(pygame.display, "get_wm_info", lambda: {"window": GAME})
    monkeypatch.setattr(window_focus, "bring_to_front", lambda hwnd, **kw: False)
    assert addon.focus_pygame_window() is False
    assert "could not be put in front" in (tmp_path / "errors.log").read_text(encoding="utf-8")
    monkeypatch.setattr(window_focus, "bring_to_front", lambda hwnd, **kw: hwnd == GAME)
    assert addon.focus_pygame_window() is True


def test_focus_pygame_window_is_a_no_op_outside_windows(monkeypatch):
    import addon

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(window_focus, "bring_to_front", lambda *a, **k: pytest.fail("must not be called"))
    assert addon.focus_pygame_window() is True


def test_log_note_writes_a_line_once(tmp_path, monkeypatch):
    monkeypatch.setattr(errlog.settings, "user_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(errlog, "_seen", {})
    monkeypatch.setattr(errlog, "_started", False)
    errlog.log_note("hello")
    errlog.log_note("hello")
    assert (tmp_path / "errors.log").read_text(encoding="utf-8").count("[note] hello") == 1


def test_the_game_takes_the_focus_again_after_the_black_cover_is_gone(monkeypatch):
    import addon_launch

    calls = []

    class Proc:
        def poll(self):
            return 0

    class Sounds:
        def play_music(self, name):
            pass

    class FakeGame:
        input_grace = 0
        menu_index = 0
        menu_screen = "addon"
        monitor_index = 0
        sounds = Sounds()

        def _pick_monitor(self):
            return (0, 1920, 1080)

        def _release_joystick_for_mame(self):
            pass

        def _wait_mame_quit(self, proc, sid):
            pass

        def _wait_mame_pad_idle(self):
            pass

        def _rebind_joystick(self):
            pass

    monkeypatch.setattr(addon_launch.mame_addon, "available_sets", lambda fresh=False: [("x", "X")])
    monkeypatch.setattr(addon_launch.mame_addon, "launch", lambda *a, **k: Proc())
    monkeypatch.setattr(addon_launch.mame_addon, "focus_pygame_window", lambda: calls.append("focus"))
    monkeypatch.setattr(addon_launch, "show_cover", lambda: calls.append("show"))
    monkeypatch.setattr(addon_launch, "hide_cover", lambda: calls.append("hide"))
    monkeypatch.setattr(addon_launch.pygame.time, "wait", lambda ms: None)
    monkeypatch.setattr(addon_launch.pygame.event, "clear", lambda *a: None)
    monkeypatch.setattr(addon_launch.pygame.display, "flip", lambda: None)
    monkeypatch.setattr(addon_launch.pygame.mixer, "music", type("M", (), {"stop": staticmethod(lambda: None)}))
    addon_launch.launch_addon(FakeGame())
    assert calls[-3:] == ["focus", "hide", "focus"]           # focus while covered, and again once uncovered
