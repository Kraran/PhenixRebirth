"""
Black topmost cover during display rebuild. No Python WndProc (that
crashes CPython 3.13 on Win64).
"""
from __future__ import annotations

import os

_hwnd = None
_brush = None
_registered = False
_CLASS = "PhenixRebirthCover2"


def _virtual_screen():
    import ctypes
    u = ctypes.windll.user32
    x = int(u.GetSystemMetrics(76) or 0)
    y = int(u.GetSystemMetrics(77) or 0)
    w = int(u.GetSystemMetrics(78) or 0)
    h = int(u.GetSystemMetrics(79) or 0)
    if w <= 0 or h <= 0:
        w = int(u.GetSystemMetrics(0) or 1920)
        h = int(u.GetSystemMetrics(1) or 1080)
        x = y = 0
    return x, y, w, h


def show_cover():
    global _hwnd, _brush, _registered
    if os.name != "nt":
        return
    try:
        hide_cover()
    except Exception:
        pass
    try:
        import ctypes

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", ctypes.c_uint),
                ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p),
                ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", ctypes.c_wchar_p),
                ("lpszClassName", ctypes.c_wchar_p),
            ]

        user32.DefWindowProcW.restype = ctypes.c_ssize_t
        user32.DefWindowProcW.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t
        ]

        if _brush is None:
            _brush = gdi32.CreateSolidBrush(0)
        wc = WNDCLASSW()
        wc.style = 0x0003
        wc.lpfnWndProc = ctypes.cast(user32.DefWindowProcW, ctypes.c_void_p)
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = None
        wc.hIcon = None
        wc.hCursor = None
        wc.hbrBackground = _brush
        wc.lpszMenuName = None
        wc.lpszClassName = _CLASS
        if not _registered:
            user32.RegisterClassW(ctypes.byref(wc))
            _registered = True

        x, y, w, h = _virtual_screen()
        WS_POPUP = 0x80000000
        WS_VISIBLE = 0x10000000
        WS_EX_TOPMOST = 0x00000008
        WS_EX_TOOLWINDOW = 0x00000080
        hwnd = user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
            _CLASS,
            "",
            WS_POPUP | WS_VISIBLE,
            int(x), int(y), int(w), int(h),
            None, None, None, None,
        )
        if not hwnd:
            print("desktop cover CreateWindow failed:", ctypes.GetLastError())
            return
        _hwnd = hwnd
        user32.SetWindowPos(hwnd, -1, int(x), int(y), int(w), int(h), 0x0040)
        user32.ShowWindow(hwnd, 5)
        user32.UpdateWindow(hwnd)
    except Exception as e:
        print("desktop cover failed:", e)
        _hwnd = None


def hide_cover():
    global _hwnd
    if os.name != "nt":
        return
    try:
        import ctypes
        if _hwnd:
            ctypes.windll.user32.DestroyWindow(_hwnd)
    except Exception:
        pass
    _hwnd = None
