"""
Optional MAME add-on (Phoenix / Pleiads / Mega Phoenix / Atari 2600 Phoenix).

Looks for addon/mame/mame.exe and ROMs under addon/mame/roms.
ROMs are never shipped.
"""
import os
import subprocess
import sys
import ctypes
from ctypes import wintypes

from settings import project_root, user_data_dir

# XInput wButtons — shared read, does not steal the pad from MAME.
_XI_BACK = 0x0020
_XI_START = 0x0010
_XI_GUIDE = 0x0400


class _XiGamepad(ctypes.Structure):
    _fields_ = [
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", wintypes.BYTE),
        ("bRightTrigger", wintypes.BYTE),
        ("sThumbLX", wintypes.SHORT),
        ("sThumbLY", wintypes.SHORT),
        ("sThumbRX", wintypes.SHORT),
        ("sThumbRY", wintypes.SHORT),
    ]


class _XiState(ctypes.Structure):
    _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", _XiGamepad)]


_XI_DLL = None
_XI_GET = None
_XI_GETEX = None


def _xinput_bind():
    global _XI_DLL, _XI_GET, _XI_GETEX
    if _XI_GET is not None:
        return _XI_GET
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            dll = ctypes.WinDLL(name)
        except OSError:
            continue
        _XI_DLL = dll
        _XI_GET = dll.XInputGetState
        _XI_GET.argtypes = [wintypes.DWORD, ctypes.POINTER(_XiState)]
        _XI_GET.restype = wintypes.DWORD
        try:
            _XI_GETEX = ctypes.WINFUNCTYPE(
                wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_XiState)
            )(("XInputGetStateEx", dll))
        except Exception:
            try:
                _XI_GETEX = ctypes.WINFUNCTYPE(
                    wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_XiState)
                )((100, dll))
            except Exception:
                _XI_GETEX = None
        return _XI_GET
    _XI_GET = False
    return None


_XI_DPAD_LEFT = 0x0004
_XI_DPAD_RIGHT = 0x0008
_XI_A = 0x1000
_XI_B = 0x2000
_XI_STICK = 14000

_VK_LSHIFT = 0xA0
_VK_W = 0x57
_VK_SPACE = 0x20
_VK_RETURN = 0x0D
_VK_S = 0x53
_VK_K = 0x4B
_VK_1 = 0x31


def xinput_state():
    """(wButtons, thumbLX) for pad 0."""
    if not sys.platform.startswith("win"):
        return 0, 0
    get = _xinput_bind()
    if not get:
        return 0, 0
    st = _XiState()
    fn = _XI_GETEX or get
    try:
        if fn(0, ctypes.byref(st)) != 0:
            return 0, 0
    except Exception:
        return 0, 0
    return int(st.Gamepad.wButtons), int(st.Gamepad.sThumbLX)


def xinput_buttons():
    """Raw XInput wButtons for pad 0, or 0."""
    return xinput_state()[0]


def _key_set(vk, down):
    user32 = ctypes.windll.user32
    if down:
        user32.keybd_event(vk, 0, 0, 0)
    else:
        user32.keybd_event(vk, 0, 2, 0)


def _key_tap(vk):
    _key_set(vk, True)
    _key_set(vk, False)


def spectrum_input_tick(prev):
    """Pheenix: pad → LShift / W / Space / Enter. Start = S then K then 1."""
    import time
    now = time.monotonic()
    if prev is None:
        prev = {"held": set(), "start": False, "seq": []}
    b, lx = xinput_state()
    want = set()
    if (b & _XI_DPAD_LEFT) or lx <= -_XI_STICK:
        want.add(_VK_LSHIFT)
    if (b & _XI_DPAD_RIGHT) or lx >= _XI_STICK:
        want.add(_VK_W)
    if b & _XI_A:
        want.add(_VK_SPACE)
    if b & _XI_B:
        want.add(_VK_RETURN)
    seq = list(prev.get("seq") or [])
    start = bool(b & _XI_START) and not bool(b & _XI_BACK) and not bool(b & _XI_GUIDE)
    if start and not prev.get("start") and not seq:
        seq = [
            (_VK_S, now + 0.06, now + 0.18),
            (_VK_K, now + 0.34, now + 0.46),
            (_VK_1, now + 0.62, now + 0.74),
        ]
    extra = set()
    keep = []
    try:
        for vk, t0, t1 in seq:
            if now < t1:
                keep.append((vk, t0, t1))
            if t0 <= now < t1:
                extra.add(vk)
    except Exception:
        keep = seq
    target = set(want) | extra
    held = set(prev.get("held") or set())
    try:
        for vk in target - held:
            _key_set(vk, True)
        for vk in held - target:
            _key_set(vk, False)
    except Exception:
        pass
    return {"held": target, "start": start, "seq": keep}


def xinput_quit_combo():
    """True if Select+Start or Guide+Start is held on pad 0."""
    b = xinput_buttons()
    if not (b & _XI_START):
        return False
    return bool(b & _XI_BACK) or bool(b & _XI_GUIDE)


def xinput_pad_idle():
    """True when Select, Start and Guide are all released."""
    b = xinput_buttons()
    return not (b & (_XI_BACK | _XI_START | _XI_GUIDE))


# 0.289 pad tokens that actually parse (DPADUP is invalid and blanks the whole seq).
_JOY_UP = "KEYCODE_UP OR JOYCODE_1_HAT1UP OR JOYCODE_1_YAXIS_UP_SWITCH"
_JOY_DOWN = "KEYCODE_DOWN OR JOYCODE_1_HAT1DOWN OR JOYCODE_1_YAXIS_DOWN_SWITCH"
_JOY_LEFT = "KEYCODE_LEFT OR JOYCODE_1_HAT1LEFT OR JOYCODE_1_XAXIS_LEFT_SWITCH"
_JOY_RIGHT = "KEYCODE_RIGHT OR JOYCODE_1_HAT1RIGHT OR JOYCODE_1_XAXIS_RIGHT_SWITCH"
_JOY_FIRE = "KEYCODE_LCONTROL OR KEYCODE_SPACE OR JOYCODE_1_BUTTON1"
_JOY_FIRE2 = "KEYCODE_LALT OR JOYCODE_1_BUTTON2"
_JOY_FIRE_2600 = "KEYCODE_LCONTROL OR KEYCODE_SPACE OR JOYCODE_1_BUTTON1 OR JOYCODE_1_BUTTON2"
_JOY_START = "KEYCODE_1 OR JOYCODE_1_START"
_JOY_COIN = "KEYCODE_5 OR JOYCODE_1_SELECT"
_JOY_QUIT = (
    "KEYCODE_ESC OR JOYCODE_1_SELECT JOYCODE_1_START OR JOYCODE_1_BUTTON9 JOYCODE_1_START"
)


ROM_SETS = (
    ("phoenix", "Phoenix (Arcade, 1980)", ["phoenix"], ("phoenix.zip",)),
    ("pleiads", "Pleiads (Arcade, 1981)", ["pleiads"], ("pleiads.zip",)),
    ("megaphx", "Mega Phoenix (Arcade, 1991)", ["megaphx"], ("megaphx.zip",)),
    ("a2600_phoenix", "Phoenix (Atari 2600, 1982)",
     ["a2600", "phoenix", "-joyport1", "joy", "-joystick"],
     ("a2600/phoenix.zip", "a2600/phoenix.bin")),
    ("spectrum_pheenix", "Pheenix (ZX Spectrum, 1983)",
     ["spectrum", "-dump", "", "-ramsize", "16K", "-ui_active",
      "-natural", "-autoboot_delay", "2", "-autoboot_command", "sk1"],
     ()),
)


def _mame_roots():
    seen = []
    for base in (user_data_dir(), project_root()):
        path = os.path.join(base, "addon", "mame")
        if path not in seen:
            seen.append(path)
    return seen


def mame_exe():
    name = "mame.exe" if sys.platform.startswith("win") else "mame"
    for root in _mame_roots():
        exe = os.path.join(root, name)
        if os.path.isfile(exe):
            return exe
    return None


def _roms_dir():
    exe = mame_exe()
    if not exe:
        return None
    return os.path.join(os.path.dirname(exe), "roms")


def _spectrum_bios_ok():
    roms = _roms_dir()
    if not roms:
        return False
    for name in ("spectrum.zip", "spectrum.rom"):
        if os.path.isfile(os.path.join(roms, name)):
            return True
    return False


def find_spectrum_pheenix():
    """Loose .z80 — walk addon/mame (roms/, spectrum/, next to mame.exe)."""
    roots = []
    roms = _roms_dir()
    if roms:
        roots.append(roms)
        roots.append(os.path.join(roms, "spectrum"))
    exe = mame_exe()
    if exe:
        roots.append(os.path.dirname(exe))
        roots.append(os.path.join(os.path.dirname(exe), "spectrum"))
    found = []
    seen = set()
    for root in roots:
        if not root or not os.path.isdir(root) or root in seen:
            continue
        seen.add(root)
        try:
            names = os.listdir(root)
        except Exception:
            continue
        for name in names:
            low = name.lower()
            if not low.endswith(".z80"):
                continue
            if "pheenix" in low or "phoenix" in low:
                found.append(os.path.join(root, name))
        # one extra level (roms/spectrum/… already covered; also roms/<folder>/*.z80)
        for name in names:
            sub = os.path.join(root, name)
            if not os.path.isdir(sub) or sub in seen:
                continue
            try:
                for fn in os.listdir(sub):
                    low = fn.lower()
                    if low.endswith(".z80") and ("pheenix" in low or "phoenix" in low):
                        found.append(os.path.join(sub, fn))
            except Exception:
                pass
    if not found:
        return None
    for fp in found:
        low = os.path.basename(fp).lower()
        if "pheenix" in low:
            return fp
    return found[0]


def rom_path(set_name):
    roms = _roms_dir()
    if not roms:
        return None
    zip_path = os.path.join(roms, set_name + ".zip")
    if os.path.isfile(zip_path):
        return zip_path
    return None


def _set_ready(entry):
    sid, _label, _argv, files = entry
    if sid == "spectrum_pheenix":
        return find_spectrum_pheenix() is not None
    roms = _roms_dir()
    if not roms:
        return False
    for rel in files:
        if os.path.isfile(os.path.join(roms, rel.replace("/", os.sep))):
            return True
    return rom_path(sid) is not None


def available_sets():
    if not mame_exe():
        return []
    out = []
    for entry in ROM_SETS:
        if _set_ready(entry):
            out.append((entry[0], entry[1]))
    return out


def addon_ready():
    return bool(available_sets())


def mame_argv(set_name):
    roms = _roms_dir()
    for sid, _label, argv, files in ROM_SETS:
        if sid != set_name:
            continue
        out = list(argv)
        if sid == "spectrum_pheenix":
            z80 = find_spectrum_pheenix()
            if z80:
                # slot after -dump
                try:
                    i = out.index("-dump")
                    out[i + 1] = os.path.abspath(z80)
                except ValueError:
                    out += ["-dump", os.path.abspath(z80)]
            return out
        if roms and len(out) >= 3 and out[1] in ("-cart", "-cart1", "-flop"):
            for rel in files:
                fp = os.path.abspath(os.path.join(roms, rel.replace("/", os.sep)))
                if os.path.isfile(fp):
                    out[-1] = fp
                    break
        return out
    return [set_name]


def snap_path(set_name):
    names = [set_name + ".png", set_name + ".jpg"]
    if set_name == "a2600_phoenix":
        names = [
            os.path.join("a2600", "phoenix.png"),
            os.path.join("a2600", "phoenix.jpg"),
            "a2600_phoenix.png",
        ] + names
    if set_name == "spectrum_pheenix":
        names = [
            os.path.join("spectrum", "pheenix.png"),
            os.path.join("spectrum", "phoenix.png"),
            "pheenix.png",
            "spectrum_pheenix.png",
        ] + names
    roots = []
    exe = mame_exe()
    if exe:
        roots.append(os.path.join(os.path.dirname(exe), "snap"))
    for base in (user_data_dir(), project_root()):
        roots.append(os.path.join(base, "addon", "mame", "snap"))
    seen = []
    for root in roots:
        if root in seen:
            continue
        seen.append(root)
        for n in names:
            fp = os.path.join(root, n)
            if os.path.isfile(fp):
                return fp
    return None


def _write_cfg(path, system, extra_ports=""):
    xml = (
        '<?xml version="1.0"?>\n'
        '<mameconfig version="10">\n'
        '    <system name="%s">\n'
        "        <input>\n"
        '            <mapdevice device="XInput Player 1" controller="JOYCODE_1" />\n'
        '            <port type="P1_JOYSTICK_UP">\n'
        "                <newseq type=\"standard\">%s</newseq>\n"
        "            </port>\n"
        '            <port type="P1_JOYSTICK_DOWN">\n'
        "                <newseq type=\"standard\">%s</newseq>\n"
        "            </port>\n"
        '            <port type="P1_JOYSTICK_LEFT">\n'
        "                <newseq type=\"standard\">%s</newseq>\n"
        "            </port>\n"
        '            <port type="P1_JOYSTICK_RIGHT">\n'
        "                <newseq type=\"standard\">%s</newseq>\n"
        "            </port>\n"
        '            <port type="P1_BUTTON1">\n'
        "                <newseq type=\"standard\">%s</newseq>\n"
        "            </port>\n"
        '            <port type="P1_BUTTON2">\n'
        "                <newseq type=\"standard\">%s</newseq>\n"
        "            </port>\n"
        '            <port type="P1_START">\n'
        "                <newseq type=\"standard\">%s</newseq>\n"
        "            </port>\n"
        '            <port type="START1">\n'
        "                <newseq type=\"standard\">%s</newseq>\n"
        "            </port>\n"
        '            <port type="COIN1">\n'
        "                <newseq type=\"standard\">%s</newseq>\n"
        "            </port>\n"
        '            <port type="UI_CANCEL">\n'
        "                <newseq type=\"standard\">%s</newseq>\n"
        "            </port>\n"
        "%s"
        "        </input>\n"
        "    </system>\n"
        "</mameconfig>\n"
    ) % (
        system,
        _JOY_UP, _JOY_DOWN, _JOY_LEFT, _JOY_RIGHT, _JOY_FIRE, _JOY_FIRE2,
        _JOY_START, _JOY_START, _JOY_COIN, _JOY_QUIT,
        extra_ports,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)


def ensure_quit_ctrlr(mame_root):
    """Arcade + default: HAT1/analog, A=tir, B=bouton 2, Select=pièce."""
    folder = os.path.join(mame_root, "ctrlr")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        return None
    path = os.path.join(folder, "phenix.cfg")
    try:
        _write_cfg(path, "default")
        return folder
    except Exception:
        return None


def ensure_arcade_cfg(mame_root, set_name):
    """Per-system cfg so arcade games keep the pad even if a default.cfg exists."""
    folder = os.path.join(mame_root, "cfg")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        return None
    path = os.path.join(folder, set_name + ".cfg")
    try:
        _write_cfg(path, set_name)
        return folder
    except Exception:
        return None


def ensure_a2600_cfg(mame_root):
    """2600 pad: tagged joyport + Reset/Select."""
    folder = os.path.join(mame_root, "cfg")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        return None
    path = os.path.join(folder, "a2600.cfg")
    extra = (
        '            <port tag=":joyport1:joy:JOY" type="P1_JOYSTICK_UP" mask="1" defvalue="1">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        '            <port tag=":joyport1:joy:JOY" type="P1_JOYSTICK_DOWN" mask="2" defvalue="2">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        '            <port tag=":joyport1:joy:JOY" type="P1_JOYSTICK_LEFT" mask="4" defvalue="4">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        '            <port tag=":joyport1:joy:JOY" type="P1_JOYSTICK_RIGHT" mask="8" defvalue="8">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        '            <port tag=":joyport1:joy:JOY" type="P1_BUTTON1" mask="32" defvalue="32">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        '            <port tag=":SWB" type="OTHER" mask="1" defvalue="1">\n'
        '                <newseq type="standard">KEYCODE_2 OR JOYCODE_1_START</newseq>\n'
        "            </port>\n"
        '            <port tag=":SWB" type="OTHER" mask="2" defvalue="2">\n'
        '                <newseq type="standard">KEYCODE_1 OR JOYCODE_1_SELECT</newseq>\n'
        "            </port>\n"
    ) % (_JOY_UP, _JOY_DOWN, _JOY_LEFT, _JOY_RIGHT, _JOY_FIRE_2600)
    try:
        _write_cfg(path, "a2600", extra)
        return folder
    except Exception:
        return None


def ensure_spectrum_cfg(mame_root):
    """Pheenix keys on pad: Caps Shift / W / Space / Enter. Start = S."""
    folder = os.path.join(mame_root, "cfg")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        return None
    path = os.path.join(folder, "spectrum.cfg")
    left = "KEYCODE_LSHIFT OR JOYCODE_1_HAT1LEFT OR JOYCODE_1_XAXIS_LEFT_SWITCH"
    right = "KEYCODE_W OR JOYCODE_1_HAT1RIGHT OR JOYCODE_1_XAXIS_RIGHT_SWITCH"
    fire = "KEYCODE_SPACE OR JOYCODE_1_BUTTON1"
    barrier = "KEYCODE_ENTER OR JOYCODE_1_BUTTON2"
    start_s = "KEYCODE_S OR JOYCODE_1_START"
    key_k = "KEYCODE_K OR JOYCODE_1_START"
    key_1 = "KEYCODE_1 OR JOYCODE_1_START"
    xml = (
        '<?xml version="1.0"?>\n'
        '<mameconfig version="10">\n'
        '    <system name="spectrum">\n'
        "        <input>\n"
        '            <mapdevice device="XInput Player 1" controller="JOYCODE_1" />\n'
        '            <port tag=":LINE0" type="KEYBOARD" mask="1" defvalue="1">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        '            <port tag=":LINE2" type="KEYBOARD" mask="2" defvalue="2">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        '            <port tag=":LINE7" type="KEYBOARD" mask="1" defvalue="1">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        '            <port tag=":LINE6" type="KEYBOARD" mask="1" defvalue="1">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        '            <port tag=":LINE1" type="KEYBOARD" mask="2" defvalue="2">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        '            <port tag=":LINE6" type="KEYBOARD" mask="4" defvalue="4">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        '            <port tag=":LINE3" type="KEYBOARD" mask="1" defvalue="1">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        '            <port type="UI_CANCEL">\n'
        '                <newseq type="standard">%s</newseq>\n'
        "            </port>\n"
        "        </input>\n"
        "    </system>\n"
        "</mameconfig>\n"
    ) % (left, right, fire, barrier, start_s, key_k, key_1, _JOY_QUIT)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml)
        return folder
    except Exception:
        return None


def _monitor_device(index):
    """\\\\.\\DISPLAY n for MAME -screen (1-based)."""
    try:
        n = max(0, int(index or 0))
    except Exception:
        n = 0
    return r"\\.\DISPLAY%d" % (n + 1)


def launch(set_name, wait=True, monitor_index=0, width=0, height=0):
    exe = mame_exe()
    ready = any(sid == set_name for sid, _lab in available_sets())
    if not exe or not ready:
        return False
    root = os.path.dirname(exe)
    roms = os.path.join(root, "roms")
    art = os.path.join(root, "artwork")
    base = [exe] + mame_argv(set_name) + [
        "-rompath", roms,
        "-skip_gameinfo",
        "-noartwork_crop",
        "-joystick",
    ]
    if set_name == "a2600_phoenix":
        ensure_a2600_cfg(root)
    elif set_name == "spectrum_pheenix":
        ensure_spectrum_cfg(root)
    else:
        ensure_arcade_cfg(root, set_name)
        ctrlr = ensure_quit_ctrlr(root)
        if ctrlr:
            base += ["-ctrlrpath", ctrlr, "-ctrlr", "phenix"]
    hashdir = os.path.join(root, "hash")
    if os.path.isdir(hashdir):
        base += ["-hashpath", hashdir]
    if os.path.isdir(art):
        base += ["-artpath", art]
    screen = _monitor_device(monitor_index)
    if screen:
        base += ["-screen", screen]
    log_path = os.path.join(root, "last_launch.log")
    flags = 0
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        logf = open(log_path, "w", encoding="utf-8")
        try:
            logf.write(" ".join(base) + "\n")
            logf.flush()
        except Exception:
            pass
        proc = subprocess.Popen(
            base,
            cwd=root,
            stdout=logf,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        proc._phenix_log = logf
    except Exception:
        return False
    if wait:
        try:
            proc.wait()
        except Exception:
            pass
        try:
            logf.close()
        except Exception:
            pass
        return True
    return proc


def focus_pygame_window():
    if not sys.platform.startswith("win"):
        return
    try:
        import pygame
        wm = pygame.display.get_wm_info()
        hwnd = int(wm.get("window") or 0)
        if not hwnd:
            return
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
