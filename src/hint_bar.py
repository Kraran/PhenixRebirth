"""
The help bar at the bottom of the menus: the same place, the same look on every screen.

Each screen gives a short list of (button, label) pairs and the bar draws them centred on a translucent band:
the keys of the keyboard as small keycaps (ENTRÉE, ÉCHAP, arrows), or the buttons of the pad (a green A, a red B,
a D-pad with the arms that count lit), depending on the device that was used last (Game.last_input_pad, set by
Game.handle_events). Nothing to set in the options.

Buttons:  "ud" up / down   "lr" left / right   "l" left   "r" right   "all" the four arrows
          "sh" the tab keys (TAB on the keyboard, LB / RB on the pad)
          "ok" confirm   "back" back   None: a plain label

The Adventure uses the same bar: StoryHub.help_items() gives its pairs (draw_frame draws them).

The pad is not shown as a permanent line any more: a small notice says "Gamepad connected / unplugged" for a few
seconds at the right end of the bar when it happens (and once at launch when a pad is there).
"""
import pygame

from i18n import t
import i18n
import fonts
import main_menu
from settings import BASE_WIDTH, BASE_HEIGHT

BAND_H = 46                       # height of the band at the bottom of the screen
BAND_Y = BASE_HEIGHT - BAND_H
BAND_ALPHA = 168                  # the band lets the stars show through a little, like the Adventure panels
BAND_COLOR = (10, 10, 22)
LINE_COLOR = (70, 70, 110)
LABEL_COLOR = (190, 190, 220)
LIT_COLOR = (255, 220, 120)
CAP_FILL = (36, 36, 56)
CAP_EDGE = (130, 130, 175)
CAP_TEXT = (240, 240, 250)
PAD_A = (70, 175, 95)
PAD_B = (205, 75, 75)
DPAD_OFF = (52, 52, 74)
DPAD_ON = (235, 235, 250)
GAP_GLYPH = 8                     # between a button and its label
GAP_ITEM = 30                     # between two pairs
NOTICE_SEC = 3.0                  # how long "gamepad connected" stays

_fonts = {}
_cache = {}
_band = None


def _font(size):
    f = _fonts.get(size)
    if f is None:
        if not pygame.font.get_init():
            pygame.font.init()
        f = _fonts[size] = fonts.text(size)
    return f


def device_is_pad(game):
    """True when the bar should show pad buttons: the pad was used last (and is still plugged)."""
    if not getattr(game, "gamepad_detected", False):
        return False
    last = getattr(game, "last_input_pad", None)
    if last is None:
        return getattr(game, "input_mode", "keyboard") == "gamepad"
    return bool(last)


# --- the buttons -------------------------------------------------------------------------------------------------
def _keycap(text, size=15):
    f = _font(size)
    img = f.render(text, True, CAP_TEXT)
    w = max(26, img.get_width() + 14)
    h = 26
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, CAP_FILL, s.get_rect(), border_radius=5)
    pygame.draw.rect(s, CAP_EDGE, s.get_rect(), width=2, border_radius=5)
    pygame.draw.line(s, (60, 60, 88), (4, h - 4), (w - 5, h - 4), 2)       # the edge of a key, seen from the front
    s.blit(img, ((w - img.get_width()) // 2, (h - 3 - img.get_height()) // 2))
    return s


def _round_button(letter, color):
    d = 26
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    pygame.draw.circle(s, color, (d // 2, d // 2), d // 2)
    pygame.draw.circle(s, (255, 255, 255, 90), (d // 2, d // 2), d // 2, 2)
    img = _font(16).render(letter, True, (255, 255, 255))
    s.blit(img, ((d - img.get_width()) // 2, (d - img.get_height()) // 2))
    return s


def _dpad(lit):
    """A small cross; `lit` names the arms that matter: a string of u d l r."""
    d, arm = 26, 8
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    c = d // 2
    arms = {"u": pygame.Rect(c - arm // 2, 0, arm, c), "d": pygame.Rect(c - arm // 2, c, arm, c),
            "l": pygame.Rect(0, c - arm // 2, c, arm), "r": pygame.Rect(c, c - arm // 2, c, arm)}
    for k, r in arms.items():
        pygame.draw.rect(s, DPAD_ON if k in lit else DPAD_OFF, r, border_radius=2)
    pygame.draw.rect(s, DPAD_OFF, pygame.Rect(c - arm // 2, c - arm // 2, arm, arm))
    return s


def _shoulders():
    """LB and RB, the two shoulder buttons of the pad."""
    f = _font(13)
    caps = [f.render(x, True, CAP_TEXT) for x in ("LB", "RB")]
    w = sum(c.get_width() + 12 for c in caps) + 4
    s = pygame.Surface((w, 26), pygame.SRCALPHA)
    x = 0
    for c in caps:
        r = pygame.Rect(x, 4, c.get_width() + 12, 18)
        pygame.draw.rect(s, CAP_FILL, r, border_radius=9)
        pygame.draw.rect(s, CAP_EDGE, r, 2, border_radius=9)
        s.blit(c, (r.centerx - c.get_width() // 2, r.centery - c.get_height() // 2))
        x = r.right + 4
    return s


def glyph(kind, pad):
    """The picture of one button, for the keyboard or the pad (None for a plain label)."""
    if kind is None:
        return None
    if kind == "sh":
        return _shoulders() if pad else _keycap("TAB")
    if pad:
        if kind == "ok":
            return _round_button("A", PAD_A)
        if kind == "back":
            return _round_button("B", PAD_B)
        return _dpad({"ud": "ud", "lr": "lr", "l": "l", "r": "r", "all": "udlr"}.get(kind, "udlr"))
    if kind == "ok":
        return _keycap(t("hint_key_enter"))
    if kind == "back":
        return _keycap(t("hint_key_esc"))
    return _keycap({"ud": "↑↓", "lr": "←→", "l": "←", "r": "→", "all": "←↑↓→"}.get(kind, "?"), size=18)


# --- the bar -----------------------------------------------------------------------------------------------------
def render(items, pad, lit=None):
    """The bar's content (without the band), cached by its pairs, the device and the language.
    `lit`: index of a pair whose label is drawn gold (the Adventure's "the text is over, press A")."""
    key = (tuple(items), bool(pad), getattr(i18n, "_lang", ""), lit)
    img = _cache.get(key)
    if img is not None:
        return img
    parts = []
    for i, (kind, label) in enumerate(items):
        g = glyph(kind, pad)
        txt = _font(20).render(t(label), True, LIT_COLOR if i == lit else LABEL_COLOR)
        parts.append((g, txt))
    widths = [(g.get_width() + GAP_GLYPH if g is not None else 0) + txt.get_width() for g, txt in parts]
    w = sum(widths) + GAP_ITEM * max(0, len(parts) - 1)
    h = 28
    img = pygame.Surface((max(1, w), h), pygame.SRCALPHA)
    x = 0
    for (g, txt), pw in zip(parts, widths):
        if g is not None:
            img.blit(g, (x, (h - g.get_height()) // 2))
            x += g.get_width() + GAP_GLYPH
        img.blit(txt, (x, (h - txt.get_height()) // 2))
        x += txt.get_width() + GAP_ITEM
    if len(_cache) > 64:
        _cache.clear()
    _cache[key] = img
    return img


def band():
    global _band
    if _band is None:
        _band = pygame.Surface((BASE_WIDTH, BAND_H), pygame.SRCALPHA)
        _band.fill(BAND_COLOR + (BAND_ALPHA,))
        pygame.draw.line(_band, LINE_COLOR + (255,), (0, 0), (BASE_WIDTH, 0), 1)
    return _band


def draw(game, surface, items, right=None, lit=None):
    """The band and its pairs at the bottom of `surface`. `right`: a small picture shown at the right end."""
    hold = getattr(game, "_bar_hold", None)
    if hold is not None:
        hold.append((items, right, lit))         # a screen is sliding in: the bar is drawn in place afterwards
        return
    surface.blit(band(), (0, BAND_Y))
    img = render(items, device_is_pad(game), lit)
    surface.blit(img, ((BASE_WIDTH - img.get_width()) // 2, BAND_Y + (BAND_H - img.get_height()) // 2))
    right_w = 0
    if right is not None:
        surface.blit(right, (BASE_WIDTH - right.get_width() - 14, BAND_Y + (BAND_H - right.get_height()) // 2))
        right_w = right.get_width() + 10
    draw_pad_notice(game, surface, right_w)


# --- the gamepad notice ------------------------------------------------------------------------------------------
def note_pad(game):
    """Called on each frame a menu is drawn: starts the notice when the pad appears or goes away."""
    now = bool(getattr(game, "gamepad_detected", False))
    seen = getattr(game, "_hint_pad_seen", None)
    if seen is None:
        game._hint_pad_seen = now
        if now:
            game._hint_pad_notice = ["pad_notice_found", NOTICE_SEC]
        return
    if now != seen:
        game._hint_pad_seen = now
        game._hint_pad_notice = ["pad_notice_on" if now else "pad_notice_off", NOTICE_SEC]


def draw_pad_notice(game, surface, right_w=0):
    """The notice at the right end of the bar, clear of the screen above it (the Adventure's tabs...). Its time runs
    with the game's frame time, like everything on screen. `right_w`: room taken at the right end already."""
    note_pad(game)
    notice = getattr(game, "_hint_pad_notice", None)
    if not notice:
        return
    key, left = notice
    notice[1] = left - float(getattr(game, "dt", 0.0) or 0.0)
    if left <= 0:
        game._hint_pad_notice = None
        return
    alpha = 255 if left > 0.5 else int(255 * left / 0.5)
    on = key != "pad_notice_off"
    ck = ("notice", key, getattr(i18n, "_lang", ""))
    img = _cache.get(ck)
    if img is None:
        txt = _font(18).render(t(key), True, (150, 230, 170) if on else (230, 170, 150))
        icon = _dpad("udlr" if on else "")
        w, h = icon.get_width() + 10 + txt.get_width() + 28, BAND_H - 12
        img = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(img, (14, 14, 28, 220), img.get_rect(), border_radius=h // 2)
        pygame.draw.rect(img, (110, 160, 125) if on else (170, 110, 100), img.get_rect(), width=2, border_radius=h // 2)
        img.blit(icon, (14, (h - icon.get_height()) // 2))
        img.blit(txt, (14 + icon.get_width() + 10, (h - txt.get_height()) // 2))
        _cache[ck] = img
    img.set_alpha(alpha)
    surface.blit(img, (BASE_WIDTH - 14 - right_w - img.get_width(), BAND_Y + (BAND_H - img.get_height()) // 2))


# --- what each screen shows --------------------------------------------------------------------------------------
NAV, CHOOSE = ("ud", "hint_nav"), ("ud", "hint_choose")
OK, BACK = ("ok", "hint_ok"), ("back", "hint_back")
QUESTION = [CHOOSE, OK, ("back", "hint_cancel")]


def _options_items(game):
    if game.menu_index < 0:                                  # the row of tabs has the focus
        return [("lr", "hint_tab"), NAV, BACK]
    spec = game._options_spec()
    key = spec[game.menu_index] if 0 <= game.menu_index < len(spec) else ""
    tabs = ("sh", "hint_tab")
    if key == "reset_hs":
        return [NAV, OK, tabs, BACK]
    if game._option_greyed(key):
        return [NAV, tabs, BACK]
    return [NAV, ("lr", "hint_set"), tabs, BACK]


def _ship_colours(game):
    """True when Up / Down change the colour of the ship under the cursor (more than one colour to choose from)."""
    try:
        sid = "shield" if int(getattr(game, "ship_select_index", 0)) % 2 == 1 else "phoenix"
        slot = int(getattr(game, "ship_select_slot", 1) or 1)
        return len(game._available_tints(sid, slot)) > 1
    except Exception:
        return False


def _addon_ready():
    try:
        import addon
        return bool(addon.addon_ready())
    except Exception:
        return False


def menu_items(game):
    """The pairs of the help bar for the screen on display (None: no bar on this screen)."""
    g = game
    if g.started:
        if getattr(g, "game_over", False):
            phase = getattr(g, "hs_phase", None)
            if phase == "enter":
                return [("ud", "hint_letter"), ("lr", "hint_position"), OK]
            if phase == "table":
                return [("ok", "hint_menu")]
            return None
        if not getattr(g, "paused", False):
            return None
        if getattr(g, "pause_options", False):
            return QUESTION if g.menu_screen == "reset_confirm" else _options_items(g)
        return [NAV, OK, ("back", "hint_resume")]
    if getattr(g, "quit_confirm", False):
        return QUESTION
    screen = g.menu_screen
    if screen == "main":
        return [NAV, OK, ("back", "hint_quit")]
    if screen == "arcade":
        if g.menu_index < len(main_menu.ARCADE) - 1:
            return [NAV, ("lr", "hint_change"), ("ok", "hint_hull"), BACK]
        return [NAV, ("ok", "hint_hull"), BACK]
    if screen == "extras":
        name = main_menu.EXTRAS[g.menu_index % len(main_menu.EXTRAS)]
        if name == "addon" and not _addon_ready():
            return [CHOOSE, BACK]
        return [CHOOSE, ("ok", "hint_open"), BACK]
    if screen == "options":
        return _options_items(g)
    if screen == "reset_confirm":
        return QUESTION
    if screen == "help":
        if getattr(g, "help_manual", False):
            return [("lr", "hint_page"), BACK]
        return [(None, "hint_any_key")]
    if screen == "ship_select":
        return [("lr", "hint_choose"), ("ud", "hint_colour"), OK, BACK] if _ship_colours(g) else [("lr", "hint_choose"), OK, BACK]
    if screen == "highscores":
        return [("l", "hint_jukebox"), ("r", "hint_feats"), BACK]
    if screen == "achievements":
        tabs = [] if getattr(g, "story_door", None) else [("sh", "hint_scores_jukebox")]
        return [("all", "hint_choose")] + tabs + [BACK]
    if screen == "jukebox":
        if getattr(g, "juke_video", False):
            return [("ok", "hint_stop")]
        tabs = [] if getattr(g, "story_door", None) else [("l", "hint_feats"), ("r", "hint_scores")]
        return [CHOOSE, ("ok", "hint_play")] + tabs + [BACK]
    if screen == "addon":
        return [CHOOSE, ("ok", "hint_launch"), BACK] if _addon_ready() else [BACK]
    if screen == "story_hub" and getattr(g, "story", None) is not None:
        return g.story.help_items(device_is_pad(g))[0]
    return None


def draw_for(game, surface, right=None):
    """The bar of the screen on display, if it has one."""
    lit = None
    if (not game.started and not getattr(game, "quit_confirm", False) and game.menu_screen == "story_hub"
            and getattr(game, "story", None) is not None):
        items, lit = game.story.help_items(device_is_pad(game))
    else:
        items = menu_items(game)
    if items:
        draw(game, surface, items, right=right, lit=lit)
