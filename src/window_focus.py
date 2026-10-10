"""Give the focus back to the game window after MAME has quit (Windows).

Windows does not let a program take the foreground just by asking: SetForegroundWindow from a process that is not
in front only makes the taskbar button blink. After MAME quits, the game is not the foreground process, so the
single call used to work or not depending on what Windows had put in front in the meantime.

`bring_to_front` does what is known to work, checks that the window really is in front, and tries again a few
times (the window of MAME may still be closing). The Windows calls are behind a small object (`_Win32`) so that the
steps can be tested with a fake one on any system.
"""
import ctypes
import time

SW_SHOW = 5
SW_RESTORE = 9


class _Win32:
    """The Windows calls `bring_to_front` needs."""

    def __init__(self):
        self.u = ctypes.windll.user32
        self.k = ctypes.windll.kernel32
        self.u.GetForegroundWindow.restype = ctypes.c_void_p
        for name in ("IsIconic", "BringWindowToTop", "SetForegroundWindow", "SetFocus", "SetActiveWindow"):
            getattr(self.u, name).argtypes = [ctypes.c_void_p]
        self.u.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.u.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 5
        self.u.AttachThreadInput.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_int]

    def get_foreground(self):
        return int(self.u.GetForegroundWindow() or 0)

    def thread_of(self, hwnd):
        return int(self.u.GetWindowThreadProcessId(hwnd, None))

    def current_thread(self):
        return int(self.k.GetCurrentThreadId())

    def attach(self, tid, to_tid, on):
        return bool(self.u.AttachThreadInput(tid, to_tid, 1 if on else 0))

    def is_iconic(self, hwnd):
        return bool(self.u.IsIconic(hwnd))

    def show(self, hwnd, cmd):
        self.u.ShowWindow(hwnd, cmd)

    def set_topmost(self, hwnd, on):
        # HWND_TOPMOST = -1, HWND_NOTOPMOST = -2; flags: no size, no move, no activate
        self.u.SetWindowPos(hwnd, -1 if on else -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

    def bring_to_top(self, hwnd):
        self.u.BringWindowToTop(hwnd)

    def set_foreground(self, hwnd):
        self.u.SetForegroundWindow(hwnd)

    def set_active(self, hwnd):
        self.u.SetActiveWindow(hwnd)

    def set_focus(self, hwnd):
        self.u.SetFocus(hwnd)

    def alt_tap(self):
        """A tap on Alt: Windows then lets the program that sent it take the foreground."""
        self.u.keybd_event(0x12, 0, 0, 0)
        self.u.keybd_event(0x12, 0, 2, 0)


def bring_to_front(hwnd, api=None, sleep=time.sleep, tries=6, delay=0.08):
    """Put the window `hwnd` in front, with the keyboard focus. True when it is the foreground window at the end."""
    api = api or _Win32()
    hwnd = int(hwnd)
    for attempt in range(tries):
        front = api.get_foreground()
        if front == hwnd:
            return True
        # Being attached to the input of the window in front is what lets the calls below take effect.
        me, other = api.current_thread(), (api.thread_of(front) if front else 0)
        attached = bool(other and other != me and api.attach(me, other, True))
        try:
            api.show(hwnd, SW_RESTORE if api.is_iconic(hwnd) else SW_SHOW)
            api.set_topmost(hwnd, True)
            api.set_topmost(hwnd, False)
            api.bring_to_top(hwnd)
            api.set_foreground(hwnd)
            api.set_active(hwnd)
            api.set_focus(hwnd)
        finally:
            if attached:
                api.attach(me, other, False)
        if api.get_foreground() == hwnd:
            return True
        if attempt == 1:
            api.alt_tap()                       # last resort, only after a first try failed
        sleep(delay)
    return api.get_foreground() == hwnd
