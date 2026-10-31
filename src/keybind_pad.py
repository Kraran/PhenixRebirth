"""The "Gamepad" tab of the screen "Keys and buttons" (src/keybind_screen.py): a drawn pad with a card for each action
(Fire, Phoenix, Pause) tied to the buttons it uses by a line, the movement and the menus shown locked, the switch "same
buttons for every gamepad" and, when it is off, one table per place (the first and the second pad plugged in) with a
button to copy one to the other.

An action is set by Enter (or A on the pad) and then the buttons are pressed: each press adds the button to the action,
or removes it when the action already has it. The D-pad (or Enter / Esc) ends it, so does a few seconds of silence.
The settings themselves live in bindings.py.
"""
import pygame

import bindings
import fonts
import menu_ui
from i18n import t

ACTIONS = bindings.PAD_ACTIONS
ROWS_ALL = ("fire", "phenix", "missile", "pause", "shared", "copy", "defaults", "back")
PAD_WAIT_SEC = 6.0                       # silence after which the capture ends by itself
ORANGE = (255, 170, 80)
HEAD = (255, 210, 140)
DIM = (110, 110, 144)
SOFT = (138, 138, 168)
GREEN = (143, 224, 168)
LINE = (90, 106, 160)

ORIGIN = (400, 250)                      # where the drawn pad starts on the screen
# where each button of an Xbox-like pad is, in the coordinates of the drawing (480 x 300)
BTN_POS = {0: (330, 132), 1: (352, 110), 2: (308, 110), 3: (330, 88), 4: (140, 37), 5: (340, 37), 6: (235, 105),
           7: (265, 105), 8: (150, 110), 9: (290, 175)}
FACE = {0: (70, 175, 95), 1: (205, 75, 75), 2: (74, 127, 208), 3: (217, 180, 65)}
CARDS = {"fire": pygame.Rect(890, 232, 300, 100), "phenix": pygame.Rect(890, 470, 300, 100),
         "missile": pygame.Rect(890, 351, 300, 100),
         "pause": pygame.Rect(490, 218, 300, 48)}
MOVE_CARD = pygame.Rect(90, 232, 300, 100)
MENUS_CARD = pygame.Rect(90, 470, 300, 100)
PANEL = pygame.Rect(60, 168, 1160, 476)


def rows():
    """The rows of the tab, in the order of the cursor: the copy button only exists with a table per pad."""
    if bindings.current.pad_shared:
        return tuple(r for r in ROWS_ALL if r != "copy")
    return ROWS_ALL


def _f(size):
    return fonts.text(size)


def _pads(game):
    return list(getattr(getattr(game, "pads", None), "pads", None) or [])


def _save(game):
    try:
        game.save_settings()
    except Exception:
        pass


def _flash(st, text):
    st.flash = [text, 2.6]


# ------------------------------------------------------------------------------------------------ the actions
def what(st):
    """What the defaults dialog restores: "Manette 2", or all of them while they share one table."""
    if bindings.current.pad_shared:
        return t("kb_pad_all")
    return t("ctrl_pad_n").format(n=st.place + 1)


def toggle_shared(game, st):
    b = bindings.current
    b.set_shared(not b.pad_shared)
    if b.pad_shared:
        st.place = 0
    _save(game)


def begin_wait(game, st, action):
    if not _pads(game):
        _flash(st, t("kb_flash_no_pad"))
        return
    st.wait = (bindings.PAD, action, st.place)
    st.mode = "wait"
    st.wait_left = st.wait_total = PAD_WAIT_SEC


def end_wait(st, grace):
    st.mode, st.wait = "list", None
    st.grace = grace


def press(game, st, button):
    """A pad button pressed while an action is being set."""
    _p, action, _place = st.wait
    b = bindings.current
    st.wait_left = st.wait_total
    if action == "pause" and button in bindings.PAUSE_FORBIDDEN:
        _flash(st, t("kb_flash_pad_pause"))
        return
    owner = b.find_button(st.place, button, skip=action)
    res = b.toggle_button(st.place, action, button)
    if res == "refused":
        _flash(st, t("kb_flash_pad_refused"))
        return
    if res == "taken" and owner:
        _flash(st, t("kb_flash_pad_taken").format(action=t("act_" + owner)))
    _save(game)


def do_reset(game, st, kind, accept):
    if not accept:
        return
    b = bindings.current
    if kind == "copy":
        b.copy_pad(1 - st.place, st.place)
    else:
        b.reset_pad(st.place)
    _save(game)


def list_command(game, st, cmd):
    """One abstract press on the list of the tab. True when the screen must close."""
    names = rows()
    st.row = max(0, min(st.row, len(names) - 1))
    name = names[st.row]
    b = bindings.current
    if cmd == "up":
        st.row = (st.row - 1) % len(names)
    elif cmd == "down":
        st.row = (st.row + 1) % len(names)
    elif cmd in ("left", "right"):
        if name == "shared":
            toggle_shared(game, st)
        elif name in ACTIONS and not b.pad_shared:
            st.place = 1 - st.place
    elif cmd == "ok":
        if name in ACTIONS:
            begin_wait(game, st, name)
        elif name == "shared":
            toggle_shared(game, st)
        elif name in ("copy", "defaults"):
            st.mode, st.index, st.reset_kind = "reset", 1, name       # the safe answer (cancel) is the one chosen
        else:
            return True
    elif cmd == "back":
        return True
    return False


def help_items(st):
    """The hint bar: (glyph, label key) pairs."""
    if st.mode == "wait":
        return [("ud", "hint_done")]
    names = rows()
    name = names[max(0, min(st.row, len(names) - 1))]
    items = [("ud", "hint_choose")]
    if name in ACTIONS:
        if not bindings.current.pad_shared:
            items.append(("lr", "hint_pad_place"))
        items.append(("ok", "hint_change"))
    elif name == "shared":
        items.append(("ok", "hint_change"))
    else:
        items.append(("ok", "hint_ok"))
    return items + [("sh", "hint_tab"), ("back", "hint_back")]


# ------------------------------------------------------------------------------------------------ the drawn pad
def _bez(p0, p1, p2, p3, n=14):
    pts = []
    for i in range(1, n + 1):
        u = i / n
        a, b, c, d = (1 - u) ** 3, 3 * u * (1 - u) ** 2, 3 * u * u * (1 - u), u ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


_BODY = ([(90, 90)] + _bez((90, 90), (90, 60), (130, 50), (170, 50)) + [(310, 50)]
         + _bez((310, 50), (350, 50), (390, 60), (390, 90)) + [(440, 220)]
         + _bez((440, 220), (450, 250), (420, 270), (390, 262)) + _bez((390, 262), (360, 255), (345, 230), (320, 215))
         + [(160, 215)] + _bez((160, 215), (135, 230), (120, 255), (90, 262)) + _bez((90, 262), (60, 270), (30, 250), (40, 220)))
_DPAD = [(181, 153), (199, 153), (199, 166), (212, 166), (212, 184), (199, 184), (199, 197), (181, 197), (181, 184),
         (168, 184), (168, 166), (181, 166)]
_cache = {}


def _pad_surface():
    """The pad without any ring (drawn once)."""
    surf = _cache.get("pad")
    if surf is not None:
        return surf
    surf = pygame.Surface((480, 300), pygame.SRCALPHA)
    edge, fill = (130, 130, 175), (36, 36, 56)
    pygame.draw.polygon(surf, (20, 22, 38), _BODY)
    pygame.draw.polygon(surf, LINE, _BODY, 2)
    for x in (100, 300):
        pygame.draw.rect(surf, fill, (x, 28, 80, 18), border_radius=9)
        pygame.draw.rect(surf, edge, (x, 28, 80, 18), 2, border_radius=9)
    pygame.draw.circle(surf, (16, 18, 28), (150, 110), 28)
    pygame.draw.circle(surf, edge, (150, 110), 28, 2)
    pygame.draw.circle(surf, fill, (150, 110), 16)
    pygame.draw.polygon(surf, fill, _DPAD)
    pygame.draw.polygon(surf, edge, _DPAD, 2)
    pygame.draw.circle(surf, (16, 18, 28), (290, 175), 24)
    pygame.draw.circle(surf, (60, 60, 85), (290, 175), 24, 2)
    pygame.draw.circle(surf, (26, 27, 44), (290, 175), 13)
    for pos in ((235, 105), (265, 105)):
        pygame.draw.circle(surf, fill, pos, 7)
        pygame.draw.circle(surf, edge, pos, 7, 2)
    font = _f(15)
    for b, col in FACE.items():
        pos = BTN_POS[b]
        pygame.draw.circle(surf, col, pos, 13)
        img = font.render(bindings.pad_label(b), True, (10, 10, 22))
        surf.blit(img, (pos[0] - img.get_width() // 2, pos[1] - img.get_height() // 2))
    _cache["pad"] = surf
    return surf


def _spot(b):
    """Where a button is on the screen (None when the drawing has no such button)."""
    pos = BTN_POS.get(int(b))
    return None if pos is None else (ORIGIN[0] + pos[0], ORIGIN[1] + pos[1])


def _ring(surf, b, col):
    p = _spot(b)
    if p is None:
        return
    if b in (4, 5):
        r = pygame.Rect(0, 0, 92, 30)
        r.center = p
        pygame.draw.rect(surf, col, r, 3, border_radius=15)
    else:
        radius = {8: 36, 9: 32, 6: 12, 7: 12}.get(b, 19)
        pygame.draw.circle(surf, col, p, radius, 3)


def _chip_images(game, buttons, h):
    """The pictures of buttons as chips: a coloured disc for the four face buttons, a pill with the name for the others."""
    font = _f(max(12, h // 2 + 1))
    out = []
    for b in buttons:
        label = bindings.pad_label(b)
        if b in FACE:
            s = pygame.Surface((h, h), pygame.SRCALPHA)
            pygame.draw.circle(s, FACE[b], (h // 2, h // 2), h // 2)
            img = font.render(label, True, (10, 10, 22))
            s.blit(img, (h // 2 - img.get_width() // 2, h // 2 - img.get_height() // 2))
        else:
            img = font.render(label, True, (240, 240, 250))
            s = pygame.Surface((img.get_width() + 24, h), pygame.SRCALPHA)
            pygame.draw.rect(s, (36, 36, 56), s.get_rect(), border_radius=h // 2)
            pygame.draw.rect(s, (130, 130, 175), s.get_rect(), 1, border_radius=h // 2)
            s.blit(img, (s.get_width() // 2 - img.get_width() // 2, h // 2 - img.get_height() // 2))
        out.append(s)
    return out


def chips(game, surf, x, y, buttons, maxw, h=30, right=False):
    """A row of button chips, shrunk until it fits `maxw`. Returns the x after the last one."""
    gap = 6
    imgs = _chip_images(game, buttons, h)
    while h > 20 and sum(i.get_width() for i in imgs) + gap * (len(imgs) - 1) > maxw:
        h -= 2
        imgs = _chip_images(game, buttons, h)
    if right:
        x -= sum(i.get_width() for i in imgs) + gap * (len(imgs) - 1)
    for img in imgs:
        surf.blit(img, (x, y + (30 - h) // 2 if h < 30 else y))
        x += img.get_width() + gap
    return x


def _lock(surf, cx, cy, col):
    pygame.draw.rect(surf, col, (cx - 7, cy - 1, 14, 10), 2, border_radius=2)
    pygame.draw.arc(surf, col, (cx - 5, cy - 9, 10, 14), 0, 3.1416, 2)


# ------------------------------------------------------------------------------------------------ the cards
def _card(game, surf, name, focused):
    b = bindings.current
    slot = 0 if b.pad_shared else game.keybind.place
    rect = CARDS[name]
    if focused:
        menu_ui.panel(surf, rect, radius=10, edge=menu_ui.SEL_EDGE, fill=menu_ui.SEL_FILL, alpha=255, edge_w=2)
    else:
        menu_ui.panel(surf, rect, radius=10, alpha=230, edge_w=1)
    buttons = list(b.pad_buttons(slot, name))
    title = game._txt(_f(22 if name != "pause" else 21), t("act_" + name), menu_ui.TEXT_SEL if focused else menu_ui.TEXT)
    pad = 16
    surf.blit(title, (rect.x + pad, rect.y + (rect.h - title.get_height()) // 2 if name == "pause" else rect.y + 10))
    if b.pad_is_modified(slot, name):
        dot = (rect.x + pad + title.get_width() + 12, (rect.y + rect.h // 2) if name == "pause" else rect.y + 10 + title.get_height() // 2)
        pygame.draw.circle(surf, ORANGE, dot, 6)
    if name == "pause":
        chips(game, surf, rect.right - pad, rect.y + (rect.h - 28) // 2, buttons, rect.w - pad * 2 - title.get_width() - 30,
              h=28, right=True)
        return
    if focused:
        dflt = " ".join(bindings.pad_label(x) for x in b.default_pad_buttons(name))
        d = game._txt(_f(15), t("kb_default_short").format(keys=dflt), SOFT)
        if d.get_width() > rect.w - pad * 2 - title.get_width() - 10:
            d = game._txt(_f(13), t("kb_default_short").format(keys=dflt), SOFT)
        surf.blit(d, (rect.right - pad - d.get_width(), rect.y + 14))
    chips(game, surf, rect.x + pad, rect.bottom - 12 - 30, buttons, rect.w - pad * 2)


def _fixed_card(game, surf, rect, title, kind):
    menu_ui.panel(surf, rect, radius=10, edge=(60, 60, 85), fill=(16, 18, 28), alpha=150, edge_w=1)
    img = game._txt(_f(22), title, DIM)
    surf.blit(img, (rect.x + 16, rect.y + 10))
    _lock(surf, rect.right - 26, rect.y + 24, DIM)
    y = rect.bottom - 12 - 30
    if kind == "move":
        x = rect.x + 16
        for key in ("kb_pad_stick", "kb_pad_dpad"):
            txt = game._txt(_f(15), t(key), (200, 200, 230))
            r = pygame.Rect(x, y, txt.get_width() + 26, 30)
            pygame.draw.rect(surf, (36, 36, 56), r, border_radius=15)
            pygame.draw.rect(surf, (90, 90, 130), r, 1, border_radius=15)
            surf.blit(txt, (r.centerx - txt.get_width() // 2, r.centery - txt.get_height() // 2))
            x = r.right + 8
        return
    # menus: A confirms, B goes back, LB / RB change tabs
    for size in (16, 14, 12):
        font = _f(size)
        ok, back = game._txt(font, t("hint_ok"), DIM), game._txt(font, t("hint_back"), DIM)
        if 26 + ok.get_width() + 26 + back.get_width() + 70 + 36 <= rect.w - 24:
            break
    x = rect.x + 16
    for letter, col, label in (("A", (44, 90, 58), ok), ("B", (90, 44, 44), back)):
        pygame.draw.circle(surf, col, (x + 13, y + 15), 13)
        let = _f(14).render(letter, True, (200, 220, 205))
        surf.blit(let, (x + 13 - let.get_width() // 2, y + 15 - let.get_height() // 2))
        surf.blit(label, (x + 32, y + 15 - label.get_height() // 2))
        x += 32 + label.get_width() + 12
    txt = _f(13).render("LB RB", True, (160, 160, 190))
    r = pygame.Rect(x, y + 3, txt.get_width() + 18, 24)
    pygame.draw.rect(surf, (36, 36, 56), r, border_radius=12)
    surf.blit(txt, (r.centerx - txt.get_width() // 2, r.centery - txt.get_height() // 2))


def _lines(game, surf, focus):
    b = bindings.current
    slot = 0 if b.pad_shared else game.keybind.place
    anchors = {"fire": (890, 282), "phenix": (890, 520), "missile": (890, 401), "pause": (640, 266)}
    for name in ACTIONS:
        sel = name == focus
        col = menu_ui.SEL_EDGE if sel else LINE
        for btn in b.pad_buttons(slot, name):
            p = _spot(btn)
            if p is not None:
                pygame.draw.line(surf, col, anchors[name], p, 2 if sel else 1)
                pygame.draw.circle(surf, col, p, 4 if sel else 3)
    for p in ((550, 360), (590, 425)):
        pygame.draw.line(surf, (60, 66, 100), (390, 282), p, 1)
        pygame.draw.circle(surf, (60, 66, 100), p, 3)


# ------------------------------------------------------------------------------------------------ the tab
def _pill(game, surf, x, y, text, plugged, chosen):
    img = game._txt(_f(17), text, (255, 230, 120) if chosen else (GREEN if plugged else SOFT))
    r = pygame.Rect(x, y, img.get_width() + 52, 34)
    if chosen:
        pygame.draw.rect(surf, (58, 52, 24), r, border_radius=17)
        pygame.draw.rect(surf, menu_ui.SEL_EDGE, r, 2, border_radius=17)
    else:
        pygame.draw.rect(surf, (46, 65, 61) if plugged else (28, 29, 44), r, border_radius=17)
        pygame.draw.rect(surf, (95, 191, 127) if plugged else (70, 70, 100), r, 1, border_radius=17)
    pygame.draw.circle(surf, (255, 230, 120) if chosen else (GREEN if plugged else SOFT), (r.x + 20, r.centery), 5)
    surf.blit(img, (r.x + 34, r.centery - img.get_height() // 2))
    return r


def _switch(game, surf, focused):
    shared = bindings.current.pad_shared
    label = game._txt(_f(17), t("kb_shared_lbl"), menu_ui.TEXT_SEL if focused else (160, 160, 190))
    word = game._txt(_f(15), t("yes_u" if shared else "no_u"), GREEN if shared else SOFT)
    right = 1190
    word_x = right - word.get_width()
    track = pygame.Rect(word_x - 12 - 46, 0, 46, 24)
    track.centery = 197
    label_x = track.x - 14 - label.get_width()
    if focused:
        menu_ui.highlight(surf, pygame.Rect(label_x - 12, 178, right + 12 - (label_x - 12), 38), radius=8)
    surf.blit(label, (label_x, track.centery - label.get_height() // 2))
    pygame.draw.rect(surf, (46, 65, 61) if shared else (36, 36, 56), track, border_radius=12)
    pygame.draw.rect(surf, (95, 191, 127) if shared else (130, 130, 175), track, 1, border_radius=12)
    pygame.draw.circle(surf, GREEN if shared else (138, 138, 168), (track.right - 12 if shared else track.x + 12, track.centery), 8)
    surf.blit(word, (word_x, track.centery - word.get_height() // 2))


def _buttons_row(game, surf, st):
    names = [n for n in rows() if n in ("defaults", "copy", "back")]
    place = st.place
    labels = {"defaults": t("kb_defaults"), "copy": t("kb_copy").format(n=(1 - place) + 1), "back": t("hint_back")}
    for size in (23, 20, 17):
        imgs = {n: game._txt(_f(size), labels[n], menu_ui.TEXT) for n in names}
        widths = {n: imgs[n].get_width() + (80 if n == "back" else 52) for n in names}
        if sum(widths.values()) + 24 * (len(names) - 1) <= PANEL.w - 40:
            break
    total = sum(widths.values()) + 24 * (len(names) - 1)
    x = PANEL.centerx - total // 2
    for n in names:
        r = pygame.Rect(x, 586, widths[n], 46)
        focused = rows()[max(0, min(st.row, len(rows()) - 1))] == n
        if focused:
            menu_ui.highlight(surf, r, radius=10)
        else:
            menu_ui.panel(surf, r, radius=10, alpha=230, edge_w=1)
        img = game._txt(_f(size), labels[n], menu_ui.TEXT_SEL if focused else menu_ui.TEXT)
        surf.blit(img, (r.centerx - img.get_width() // 2, r.centery - img.get_height() // 2))
        x = r.right + 24


def draw(game, st):
    """The body of the tab (the title, the tab strip and the note under them are drawn by the screen)."""
    surf = game.game_surface
    b = bindings.current
    names = rows()
    name = names[max(0, min(st.row, len(names) - 1))]
    menu_ui.panel(surf, PANEL)
    pads = _pads(game)
    # who is shown: one pill while the pads share their buttons, a pill for each place otherwise
    if b.pad_shared:
        n = len(pads)
        text = t("gamepad_none") if n == 0 else (t("gamepad_detected") if n == 1 else t("kb_pad_found_n").format(n=n))
        _pill(game, surf, 90, 180, text, n > 0, False)
    else:
        x = 90
        for i in range(2):
            r = _pill(game, surf, x, 180, t("ctrl_pad_n").format(n=i + 1), len(pads) > i, st.place == i)
            x = r.right + 10
    _switch(game, surf, name == "shared")
    surf.blit(_pad_surface(), ORIGIN)
    _lines(game, surf, name if name in ACTIONS else None)
    focus = name if name in ACTIONS else None
    if focus:
        for btn in b.pad_buttons(0 if b.pad_shared else st.place, focus):
            _ring(surf, btn, menu_ui.SEL_EDGE)
    for action in ACTIONS:
        _card(game, surf, action, action == focus)
    _fixed_card(game, surf, MOVE_CARD, t("act_move"), "move")
    _fixed_card(game, surf, MENUS_CARD, t("act_menus"), "menus")
    _buttons_row(game, surf, st)
    if not st.flash:
        key = "kb_pad_hint" if focus else ("kb_pad_footer_shared" if b.pad_shared else "kb_pad_footer")
        for size in (16, 14, 12):
            img = game._txt(_f(size), t(key), DIM)
            if img.get_width() <= PANEL.w:
                break
        surf.blit(img, (PANEL.centerx - img.get_width() // 2, PANEL.bottom + 6))
    st.layout = (0, 0)


def draw_wait(game, st, ks):
    """The dialog while the buttons of an action are being pressed."""
    surf = game.game_surface
    _p, action, _place = st.wait
    r = ks._dialog(game, 560, 380, edge=menu_ui.SEL_EDGE)
    y = r.y + 22
    y = ks._centered(game, surf, game.font, t("act_" + action), HEAD, r.centerx, y) + 12
    body_font = getattr(game, "body_font", None) or game.font
    for line in game._wrap_ui(t("kb_pad_wait_text"), body_font, r.w - 60):
        y = ks._centered(game, surf, body_font, line, ks.BODY, r.centerx, y)
    y += 16
    box = pygame.Rect(0, 0, r.w - 60, 62)
    box.midtop = (r.centerx, y)
    menu_ui.panel(surf, box, radius=12, edge=menu_ui.SEL_EDGE, fill=ks.CAP_ON_FILL, alpha=255, edge_w=2)
    slot = 0 if bindings.current.pad_shared else st.place
    chips(game, surf, box.x + 20, box.y + 16, list(bindings.current.pad_buttons(slot, action)), box.w - 40, h=30)
    y = box.bottom + 14
    if st.flash:
        for line in game._wrap_ui(st.flash[0], game.menu_font, r.w - 60)[:2]:
            y = ks._centered(game, surf, game.menu_font, line, ORANGE, r.centerx, y)
    y = max(y, box.bottom + 14) + 10
    bar = pygame.Rect(r.x + 30, r.bottom - 92, r.w - 60, 6)
    pygame.draw.rect(surf, (36, 36, 56), bar, border_radius=3)
    fill = bar.copy()
    fill.w = int(bar.w * max(0.0, min(1.0, st.wait_left / max(0.1, st.wait_total))))
    pygame.draw.rect(surf, menu_ui.SEL_EDGE, fill, border_radius=3)
    left = max(1, int(st.wait_left + 0.999))
    ks._centered(game, surf, game.menu_font, t("kb_pad_wait_timeout").format(n=left), DIM, r.centerx, bar.bottom + 8)
    ks._centered(game, surf, _f(15), t("kb_pad_wait_done"), SOFT, r.centerx, bar.bottom + 38)
