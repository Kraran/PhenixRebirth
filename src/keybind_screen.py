"""The screen "Keys and buttons" (Options > Game): the keys of each keyboard, one action per row, two keys per action.

It opens over the options (from the menu or from the pause) and takes every key and every pad button while it is open
(`game.keybind` is its state, None when it is closed). Each change is saved at once (settings.json). The settings
themselves live in bindings.py; this file is the screen, its dialogs and its input.

Rows: the six actions, then "Default settings" and "Back". Left / Right choose the key of the row, Enter waits for the
new key, Delete clears it, Tab / Page Up / Page Down change the keyboard tab, Escape goes back.
Dialogs (over the screen): waiting for a key (Escape cancels, Delete clears, it gives up by itself after a few
seconds), a key already used elsewhere (swap, or take it), restoring the defaults (the answer "cancel" is chosen).
A pad drives it too: the D-pad / stick move, A confirms, B goes back, Y clears, LB / RB change the tab.
"""
import sys

import pygame

import bindings
import controls
import fonts
import keybind_pad
import menu_ui
from i18n import t
from settings import BASE_HEIGHT, BASE_WIDTH

TABS = (bindings.KB1, bindings.KB2, bindings.PAD)      # two keyboards, then the gamepads
ACTION_ROWS = bindings.KEY_ACTIONS
ROWS = ACTION_ROWS + ("defaults", "back")
WAIT_SEC = 8.0                   # a key that is waited for: it gives up after this
GRACE_SEC = 0.35                 # after opening / a choice: the Enter or Space still held down is not taken as a new press
FLASH_SEC = 2.6
DEAD = 0.72                      # stick: how far it must be pushed to count as a press (the menus' value)

UP_KEYS = (pygame.K_UP, pygame.K_w, pygame.K_z)
DOWN_KEYS = (pygame.K_DOWN, pygame.K_s)
LEFT_KEYS = (pygame.K_LEFT, pygame.K_a, pygame.K_q)
RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d)
OK_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_LCTRL, pygame.K_RCTRL)
CLEAR_KEYS = (pygame.K_DELETE, pygame.K_BACKSPACE)

CAP_FILL, CAP_EDGE = (31, 32, 51), (90, 90, 130)
CAP_ON_FILL = (58, 52, 24)
CAP_EMPTY_EDGE = (60, 60, 85)
ORANGE = (255, 170, 80)
HEAD = (255, 210, 140)
BODY = (200, 200, 230)
DIM = (110, 110, 144)


class State:
    def __init__(self):
        self.tab = 0
        self.row = 0
        self.col = 0
        self.mode = "list"            # list | wait | conflict | reset
        self.wait = None              # (profile, action, slot) of the key that is waited for ("pad": the place of the pad)
        self.wait_left = 0.0
        self.wait_total = WAIT_SEC
        self.place = 0                # gamepad tab: the pad shown (0 = the first one plugged in)
        self.reset_kind = "keys"      # the dialog of "reset": keys | pad | copy
        self.conflict = None          # {"key", "here", "other", "had"}
        self.index = 0                # the answer chosen in a dialog
        self.flash = None             # [text, seconds left]
        self.grace = GRACE_SEC
        self.ignore = None            # a key that must not count until it is released (it started the dialog)
        self.latch = [0, 0]           # the stick: x and y already counted
        self.hat = (0, 0)
        self.layout = (0, 0)

    @property
    def profile(self):
        return TABS[self.tab % len(TABS)]

    @property
    def is_pad(self):
        return self.profile == bindings.PAD


# ------------------------------------------------------------------------------------------------ open / close
def is_open(game):
    return getattr(game, "keybind", None) is not None


def open_screen(game):
    game.keybind = State()


def close(game):
    game.keybind = None
    try:
        game.save_settings()
    except Exception:
        pass


def _flash(st, key):
    st.flash = [t(key), FLASH_SEC]


def _save(game):
    try:
        game.save_settings()
    except Exception:
        pass


def tick(game, dt):
    """Run the clocks of the screen (the wait for a key, the notice, the pause after an Enter)."""
    st = game.keybind
    if st is None:
        return
    st.grace = max(0.0, st.grace - dt)
    if st.flash:
        st.flash[1] -= dt
        if st.flash[1] <= 0:
            st.flash = None
    if st.mode == "wait":
        st.wait_left -= dt
        if st.wait_left <= 0:
            st.mode, st.wait = "list", None             # nobody pressed anything: back to the list, nothing changed


# ------------------------------------------------------------------------------------------------ the actions
def _what(st):
    """What the defaults dialog restores, as a name: "Keyboard 1"."""
    if st.is_pad:
        return keybind_pad.what(st)
    return t("kb_tab").format(n=TABS.index(st.profile) + 1).title()


def _begin_wait(st):
    st.wait = (st.profile, ACTION_ROWS[st.row], st.col)
    st.wait_left = WAIT_SEC
    st.mode = "wait"
    st.grace = GRACE_SEC


def _clear_slot(game, st):
    profile, action = st.profile, ACTION_ROWS[st.row]
    if bindings.current.slots(profile, action)[st.col] is None:
        return
    if bindings.current.set_key(profile, action, st.col, None):
        _save(game)
    else:
        _flash(st, "kb_flash_last")


def _assign(game, st, key):
    """The key pressed while waiting. Taken elsewhere: a question; else it is set."""
    profile, action, slot = st.wait
    b = bindings.current
    st.mode, st.wait = "list", None
    st.grace = GRACE_SEC
    st.ignore = key
    other = b.find_key(key, skip=(profile, action, slot))
    if other is not None:
        st.conflict = {"key": key, "here": (profile, action, slot), "other": other,
                       "had": b.slots(profile, action)[slot] is not None}
        st.mode, st.index = "conflict", 0
        return
    if b.set_key(profile, action, slot, key):
        _save(game)
    else:
        _flash(st, "kb_flash_last")


def _resolve_conflict(game, st, accept):
    c, st.conflict = st.conflict, None
    st.mode = "list"
    st.grace = GRACE_SEC
    if accept and c:
        profile, action, slot = c["here"]
        if bindings.current.set_key(profile, action, slot, c["key"], swap=True):
            _save(game)
        else:
            _flash(st, "kb_flash_last")


def _do_reset(game, st, accept):
    st.mode = "list"
    st.grace = GRACE_SEC
    if st.is_pad:
        keybind_pad.do_reset(game, st, st.reset_kind, accept)
    elif accept:
        bindings.current.reset_keys(st.profile)
        _save(game)


# ------------------------------------------------------------------------------------------------ input
def _command(game, st, cmd):
    """One abstract press (up down left right ok back clear tab-prev tab-next) on the screen in the mode it is in."""
    if st.mode in ("conflict", "reset"):
        if cmd in ("up", "down"):
            st.index = 1 - st.index
        elif cmd == "ok":
            if st.mode == "conflict":
                _resolve_conflict(game, st, st.index == 0)
            else:
                _do_reset(game, st, st.index == 0)
        elif cmd == "back":
            if st.mode == "conflict":
                _resolve_conflict(game, st, False)
            else:
                _do_reset(game, st, False)
        return
    if st.mode == "wait":
        if st.wait[0] == bindings.PAD:                        # the buttons of a pad action: the D-pad or Enter / Esc end it
            if cmd in ("back", "ok", "up", "down", "left", "right"):
                keybind_pad.end_wait(st, GRACE_SEC)
            return
        if cmd == "back":
            st.mode, st.wait = "list", None
        elif cmd == "clear":
            profile, action, slot = st.wait
            st.mode, st.wait = "list", None
            st.col, st.row = slot, ACTION_ROWS.index(action)
            _clear_slot(game, st)
        return
    if cmd in ("tab-prev", "tab-next"):
        was_pad = st.is_pad
        st.tab = (st.tab + (1 if cmd == "tab-next" else -1)) % len(TABS)
        if st.is_pad != was_pad:
            st.row, st.col = 0, 0
            st.place = 0 if bindings.current.pad_shared else st.place
        return
    if st.is_pad:
        if keybind_pad.list_command(game, st, cmd):
            close(game)
        return
    if cmd == "up":
        st.row = (st.row - 1) % len(ROWS)
    elif cmd == "down":
        st.row = (st.row + 1) % len(ROWS)
    elif cmd in ("left", "right") and st.row < len(ACTION_ROWS):
        st.col = (st.col + (1 if cmd == "right" else -1)) % bindings.SLOTS
    elif cmd == "ok":
        name = ROWS[st.row]
        if name == "defaults":
            st.mode, st.index, st.reset_kind = "reset", 1, "keys"   # the safe answer (cancel) is the one chosen
        elif name == "back":
            close(game)
        else:
            _begin_wait(st)
    elif cmd == "clear" and st.row < len(ACTION_ROWS):
        _clear_slot(game, st)
    elif cmd == "back":
        close(game)


def on_key(game, event):
    """A key pressed while the screen is open (always taken)."""
    st = game.keybind
    key = event.key
    if st.ignore is not None and key != st.ignore:
        st.ignore = None
    if key == pygame.K_F12:
        game.take_screenshot()
        return
    if st.mode == "wait" and st.wait[0] == bindings.PAD:
        if key == st.ignore or (st.grace > 0 and key in OK_KEYS):
            return
        if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT,
                   pygame.K_RIGHT):
            _command(game, st, "back")
        return
    if st.mode == "wait":
        if key in (pygame.K_ESCAPE,):
            _command(game, st, "back")
        elif key in CLEAR_KEYS:
            _command(game, st, "clear")
        elif st.grace > 0 and key in OK_KEYS:
            return                                           # the Enter / Space that opened the wait, still held
        elif key == st.ignore:
            return
        elif bindings.bindable(key):
            _assign(game, st, key)
        else:
            _flash(st, "kb_flash_reserved")
        return
    if key == st.ignore or (st.grace > 0 and key in OK_KEYS):
        return
    shift = bool(getattr(event, "mod", 0) & pygame.KMOD_SHIFT)
    if key == pygame.K_ESCAPE:
        cmd = "back"
    elif key in UP_KEYS:
        cmd = "up"
    elif key in DOWN_KEYS:
        cmd = "down"
    elif key in LEFT_KEYS:
        cmd = "left"
    elif key in RIGHT_KEYS:
        cmd = "right"
    elif key in OK_KEYS:
        cmd = "ok"
        st.ignore = key
    elif key in CLEAR_KEYS:
        cmd = "clear"
    elif key == pygame.K_PAGEUP or (key == pygame.K_TAB and shift):
        cmd = "tab-prev"
    elif key in (pygame.K_PAGEDOWN, pygame.K_TAB):
        cmd = "tab-next"
    else:
        return
    _command(game, st, cmd)


def on_keyup(game, event):
    st = game.keybind
    if st is not None and st.ignore == event.key:
        st.ignore = None


def on_joy_button(game, event):
    st = game.keybind
    b = event.button
    if st.is_pad and st.mode == "list" and not bindings.current.pad_shared:
        slot = controls.slot_of(game, event)           # a button of a pad lights up its own place
        if slot in (0, 1):
            st.place = slot
    if st.mode == "wait":
        if st.wait[0] == bindings.PAD:
            keybind_pad.press(game, st, b)                 # every button is for the action (the D-pad ends it)
            return
        if b == 1:
            _command(game, st, "back")
        return
    if b == 0:
        _command(game, st, "ok")
    elif b == 1:
        _command(game, st, "back")
    elif b == 3:
        _command(game, st, "clear")
    elif b in (4, 5):
        _command(game, st, "tab-prev" if b == 4 else "tab-next")


def on_joy_hat(game, event):
    st = game.keybind
    hx, hy = event.value
    if (hx, hy) == (0, 0):
        st.hat = (0, 0)
        return
    if st.hat == (hx, hy):
        return
    st.hat = (hx, hy)
    if hy:
        _command(game, st, "up" if hy > 0 else "down")
    if hx:
        _command(game, st, "right" if hx > 0 else "left")


def on_joy_axis(game, event):
    st = game.keybind
    if event.axis not in (0, 1):
        return
    i = event.axis
    v = event.value
    if abs(v) < 0.40:
        st.latch[i] = 0
        return
    way = 1 if v > DEAD else (-1 if v < -DEAD else 0)
    if not way or st.latch[i] == way:
        return
    st.latch[i] = way
    if i == 0:
        _command(game, st, "right" if way > 0 else "left")
    else:
        _command(game, st, "down" if way > 0 else "up")


# ------------------------------------------------------------------------------------------------ the help bar
def help_items(game):
    st = game.keybind
    if st.is_pad:
        return keybind_pad.help_items(st) if st.mode in ("list", "wait") else [("ud", "hint_choose"), ("ok", "hint_ok"), ("back", "hint_cancel")]
    if st.mode == "wait":
        return [("back", "hint_cancel"), ("del", "hint_clear")]
    if st.mode in ("conflict", "reset"):
        return [("ud", "hint_choose"), ("ok", "hint_ok"), ("back", "hint_cancel")]
    items = [("ud", "hint_choose")]
    if st.row < len(ACTION_ROWS):
        items += [("lr", "hint_key_slot"), ("ok", "hint_change"), ("del", "hint_clear")]
    else:
        items += [("ok", "hint_ok")]
    return items + [("sh", "hint_tab"), ("back", "hint_back")]


# ------------------------------------------------------------------------------------------------ drawing
LEFT = pygame.Rect(60, 168, 700, 476)
RIGHT = pygame.Rect(790, 168, 430, 476)
ROW_H, ROW_STEP = 46, 50
SLOT_W, SLOT_GAP = 128, 12


def _small(size):
    return fonts.text(size)


def _fit(game, text, col, width):
    """The text in the largest of three sizes that fits `width`."""
    img = None
    for font in (game.menu_font, _small(18), _small(15)):
        img = game._txt(font, text, col)
        if img.get_width() <= width:
            break
    return img


def _cap(surf, rect, img, kind, modified=False):
    """A key on screen: kind is "on" (the key that has the cursor), "norm" or "empty"."""
    if kind == "on":
        menu_ui.panel(surf, rect, radius=8, edge=menu_ui.SEL_EDGE, fill=CAP_ON_FILL, alpha=255, edge_w=2)
    elif kind == "norm":
        menu_ui.panel(surf, rect, radius=8, edge=CAP_EDGE, fill=CAP_FILL, alpha=255, edge_w=1)
    else:
        menu_ui.panel(surf, rect, radius=8, edge=CAP_EMPTY_EDGE, fill=(20, 21, 32), alpha=120, edge_w=1)
    surf.blit(img, (rect.centerx - img.get_width() // 2, rect.centery - img.get_height() // 2))
    if modified:
        pygame.draw.circle(surf, ORANGE, (rect.right - 3, rect.top + 3), 6)
        pygame.draw.circle(surf, (40, 24, 8), (rect.right - 3, rect.top + 3), 6, 1)


def _slot_rects(row_rect):
    right = row_rect.right - 18
    s2 = pygame.Rect(right - SLOT_W, row_rect.centery - 18, SLOT_W, 36)
    s1 = pygame.Rect(s2.x - SLOT_GAP - SLOT_W, s2.y, SLOT_W, 36)
    return s1, s2


def _label(game, key):
    return bindings.key_label(key, t)


def draw(game):
    """The screen, and over it the dialog of the mode it is in."""
    import draw_frame                      # (it imports this module: loaded here, when the screen is drawn)
    st = game.keybind
    tick(game, float(getattr(game, "dt", 0.0) or 0.0))
    surf = game.game_surface
    hdr = game._txt(game.medium_font, t("opt_keybinds").upper(), menu_ui.TITLE)
    surf.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 40))
    labels = [t("kb_tab").format(n=i + 1) for i in range(len(TABS) - 1)] + [t("kb_tab_pad")]
    draw_frame.draw_tab_strip(game, labels, st.tab, 108, focused=False)
    note = None
    for size in (17, 15, 13):             # who uses this keyboard: one line under the tabs, in the largest size that fits
        note = game._txt(_small(size), t("kb_note_pad" if st.is_pad else "kb_note_%d" % (TABS.index(st.profile) + 1)), (138, 138, 168))
        if note.get_width() <= 1160:
            break
    surf.blit(note, (BASE_WIDTH // 2 - note.get_width() // 2, 148))
    if st.is_pad:
        keybind_pad.draw(game, st)
    else:
        _draw_list(game, st)
        _draw_help(game, st)
    if st.flash and not (st.mode == "wait" and st.is_pad):
        img = game._txt(game.menu_font, st.flash[0], ORANGE)
        surf.blit(img, (BASE_WIDTH // 2 - img.get_width() // 2, LEFT.bottom + 6))
    if st.mode == "wait":
        if st.wait[0] == bindings.PAD:
            keybind_pad.draw_wait(game, st, sys.modules[__name__])
        else:
            _draw_wait(game, st)
    elif st.mode == "conflict":
        _draw_conflict(game, st)
    elif st.mode == "reset":
        _draw_reset(game, st)


def _draw_list(game, st):
    surf = game.game_surface
    b = bindings.current
    menu_ui.panel(surf, LEFT)
    small = _small(16)
    head_y = LEFT.y + 16
    surf.blit(game._txt(small, t("kb_col_action"), DIM), (LEFT.x + 28, head_y))
    s1, s2 = _slot_rects(pygame.Rect(LEFT.x + 10, LEFT.y + 40, LEFT.w - 20, ROW_H))
    for n, rect in ((1, s1), (2, s2)):
        img = game._txt(small, t("kb_col_key").format(n=n), DIM)
        surf.blit(img, (rect.centerx - img.get_width() // 2, head_y))
    y0 = LEFT.y + 40
    profile = st.profile
    for i, name in enumerate(ROWS):
        if name == "defaults":
            y = y0 + len(ACTION_ROWS) * ROW_STEP + 22
        elif name == "back":
            y = y0 + len(ACTION_ROWS) * ROW_STEP + 22 + ROW_STEP
        else:
            y = y0 + i * ROW_STEP
        row = pygame.Rect(LEFT.x + 10, y, LEFT.w - 20, ROW_H)
        chosen = i == st.row
        if chosen:
            menu_ui.highlight(surf, row)
        col = menu_ui.TEXT_SEL if chosen else menu_ui.TEXT
        if name in ACTION_ROWS:
            lab = game._txt(game.font, t("act_" + name), col)
            surf.blit(lab, (row.x + 18, row.centery - lab.get_height() // 2))
            slots, defaults = b.slots(profile, name), b.default_slots(profile, name)
            rects = _slot_rects(row)
            for k in range(bindings.SLOTS):
                key = slots[k]
                kind = "empty" if key is None else ("on" if chosen and st.col == k else "norm")
                if key is None and chosen and st.col == k:
                    kind = "on"
                img = _fit(game, _label(game, key), (255, 230, 120) if kind == "on" else (240, 240, 250), SLOT_W - 14)
                _cap(surf, rects[k], img, kind, modified=slots[k] != defaults[k])
        else:
            text = t("kb_defaults") if name == "defaults" else t("hint_back")
            lab = game._txt(game.font, text, col)
            surf.blit(lab, (row.x + 18, row.centery - lab.get_height() // 2))
            if name == "defaults":
                pygame.draw.line(surf, (46, 51, 80), (LEFT.x + 28, y - 10), (LEFT.right - 28, y - 10), 1)


def _caps_line(game, surf, x, y, keys, maxw=None):
    """Small keys side by side; returns the x after the last one."""
    for key in keys:
        img = game._txt(_small(17), _label(game, key), (240, 240, 250))
        w = max(40, img.get_width() + 20)
        r = pygame.Rect(x, y, w, 30)
        _cap(surf, r, img, "norm")
        x = r.right + 8
    return x


def _draw_help(game, st):
    surf = game.game_surface
    menu_ui.panel(surf, RIGHT)
    name = ROWS[st.row]
    profile = st.profile
    b = bindings.current
    x = RIGHT.x + 22
    w = RIGHT.w - 44
    if name in ACTION_ROWS:
        title, body = t("act_" + name), t("kb_help_" + name)
    elif name == "defaults":
        title, body = t("kb_defaults"), t("kb_help_defaults")
    else:
        title, body = t("hint_back"), ""
    surf.blit(game._txt(game.font, title, HEAD), (x, RIGHT.y + 16))
    body_font = getattr(game, "body_font", None) or game.font
    y = RIGHT.y + 60
    paragraphs = [body] if body else []
    if profile == bindings.KB1 and name in ("left", "up"):
        paragraphs.append(t("kb_azerty"))
    for para in paragraphs:
        for line in game._wrap_ui(para, body_font, w):
            surf.blit(game._txt(body_font, line, BODY), (x, y))
            y += body_font.get_linesize() + 2
        y += 8
    if name in ACTION_ROWS:
        y += 4
        pygame.draw.line(surf, (46, 51, 80), (x, y), (RIGHT.right - 22, y), 1)
        y += 14
        cur, dflt = b.keys(profile, name), b.default_slots(profile, name)
        for label, keys in ((t("kb_default_lbl"), [k for k in dflt if k]), (t("kb_now_lbl"), list(cur))):
            surf.blit(game._txt(_small(15), label, DIM), (x, y + 6))
            _caps_line(game, surf, x + 150, y, keys)
            y += 42
        if not b.is_modified(profile, name):
            surf.blit(game._txt(_small(16), t("kb_unchanged"), DIM), (x + 150, y - 6))
            y += 22
    top_end = y
    # at the bottom: the note of the tab, the legend of the orange dot, and what never changes
    small = _small(17)
    lines = []
    for text in (t("kb_pause_fixed"),):
        lines.append(game._wrap_ui(text, small, w))
    yb = RIGHT.bottom - 16
    for wrapped in lines:
        for line in reversed(wrapped):
            img = game._txt(small, line, (138, 138, 168))
            yb -= img.get_height() + 1
            surf.blit(img, (x, yb))
        yb -= 8
    img = game._txt(small, t("kb_legend"), (138, 138, 168))
    yb -= img.get_height()
    pygame.draw.circle(surf, ORANGE, (x + 6, yb + img.get_height() // 2), 6)
    surf.blit(img, (x + 20, yb))
    st.layout = (top_end, yb)              # what the top and the bottom of the panel took (a test checks they never meet)


def _dialog(game, w, h, edge=menu_ui.PANEL_EDGE):
    surf = game.game_surface
    surf.blit(game._dim_overlay(170), (0, 0))
    r = pygame.Rect(0, 0, w, h)
    r.center = (BASE_WIDTH // 2, BASE_HEIGHT // 2 - 20)
    menu_ui.panel(surf, r, radius=14, alpha=240, edge=edge)
    return r


def _centered(game, surf, font, text, col, cx, y):
    img = game._txt(font, text, col)
    surf.blit(img, (cx - img.get_width() // 2, y))
    return y + img.get_height()


def _answers(game, r, y, labels, colours=None):
    """Answer rows at the bottom of a dialog, the chosen one framed (like the options)."""
    surf = game.game_surface
    st = game.keybind
    for i, text in enumerate(labels):
        row = pygame.Rect(r.x + 20, y + i * 52, r.w - 40, 46)
        chosen = i == st.index
        if chosen:
            menu_ui.highlight(surf, row)
        col = (colours[i] if colours and colours[i] and not chosen else None) or (
            menu_ui.TEXT_SEL if chosen else menu_ui.TEXT)
        img = game._txt(game.font, text, col)
        surf.blit(img, (row.x + 18, row.centery - img.get_height() // 2))


def _draw_wait(game, st):
    surf = game.game_surface
    profile, action, slot = st.wait
    r = _dialog(game, 460, 330, edge=menu_ui.SEL_EDGE)
    y = r.y + 22
    y = _centered(game, surf, game.font, t("act_" + action), HEAD, r.centerx, y) + 12
    body_font = getattr(game, "body_font", None) or game.font
    y = _centered(game, surf, body_font, t("kb_wait_text"), BODY, r.centerx, y) + 22
    box = pygame.Rect(0, 0, 160, 72)
    box.midtop = (r.centerx, y)
    menu_ui.panel(surf, box, radius=12, edge=menu_ui.SEL_EDGE, fill=CAP_ON_FILL, alpha=255, edge_w=2)
    dots = "." * (1 + int(st.wait_left * 3) % 3)
    dots = dots.replace(".", "·")
    img = game._txt(game.font, dots, menu_ui.TEXT_SEL)
    surf.blit(img, (box.centerx - img.get_width() // 2, box.centery - img.get_height() // 2))
    y = box.bottom + 30
    bar = pygame.Rect(r.x + 30, y, r.w - 60, 6)
    pygame.draw.rect(surf, (36, 36, 56), bar, border_radius=3)
    fill = bar.copy()
    fill.w = int(bar.w * max(0.0, min(1.0, st.wait_left / WAIT_SEC)))
    pygame.draw.rect(surf, menu_ui.SEL_EDGE, fill, border_radius=3)
    left = max(1, int(st.wait_left + 0.999))
    _centered(game, surf, game.menu_font, t("kb_wait_timeout").format(n=left), DIM, r.centerx, y + 16)


def _draw_conflict(game, st):
    c = st.conflict
    profile, action, _slot = c["other"]
    where = t("kb_tab").format(n=TABS.index(profile) + 1).title()
    key = _label(game, c["key"])
    r = _dialog(game, 560, 330)
    surf = game.game_surface
    y = r.y + 22
    y = _centered(game, surf, game.font, t("kb_conflict_title").format(key=key), HEAD, r.centerx, y) + 14
    text = t("kb_conflict_swap" if c["had"] else "kb_conflict_take").format(key=key, action=t("act_" + action), where=where)
    body_font = getattr(game, "body_font", None) or game.font
    for line in game._wrap_ui(text, body_font, r.w - 60):
        y = _centered(game, surf, body_font, line, BODY, r.centerx, y)
    _answers(game, r, r.bottom - 124, [t("kb_swap" if c["had"] else "kb_take"), t("hint_cancel")])


def _draw_reset(game, st):
    r = _dialog(game, 600, 350)
    surf = game.game_surface
    copy = st.is_pad and st.reset_kind == "copy"
    title = t("kb_copy_title" if copy else "kb_reset_title")
    if copy:
        text = t("kb_copy_text").format(to=t("ctrl_pad_n").format(n=st.place + 1), src=t("ctrl_pad_n").format(n=2 - st.place))
    elif st.is_pad:
        text = t("kb_reset_text_pad").format(what=_what(st))
    else:
        text = t("kb_reset_text").format(what=_what(st))
    y = r.y + 22
    for line in game._wrap_ui(title, game.font, r.w - 60):
        y = _centered(game, surf, game.font, line, HEAD, r.centerx, y)
    y += 14
    body_font = getattr(game, "body_font", None) or game.font
    for line in game._wrap_ui(text, body_font, r.w - 60):
        y = _centered(game, surf, body_font, line, BODY, r.centerx, y)
    _answers(game, r, r.bottom - 124, [t("kb_copy_ok" if copy else "kb_reset_ok"), t("hint_cancel")],
             colours=[None if copy else menu_ui.DANGER, None])
