"""The look of the pad buttons on screen, after the pad in use: Xbox (the default), PlayStation or Nintendo.

The buttons themselves are the same for every pad (src/pad_map.py gives a PlayStation or a Switch pad the numbers of
an Xbox pad: the bottom face button is 0, the right one 1...). Only what is drawn and written changes:

    Xbox          A B X Y (green, red, blue, yellow), LB RB, Back Start
    PlayStation   cross, circle, square, triangle (drawn, in the colours of the pad), L1 R1, Share Options
                  (Create Options on a DualSense)
    Nintendo      the bottom button carries the letter B, the right one A, the left one Y, the top one X (grey);
                  L R, − +

    family_for_name(name)     "xbox", "playstation", "playstation5" or "nintendo", from the name SDL gives the pad
    family_of(joy)            the same for a pad (kept once read)
    family_of_game(game)      the family of the pad in use (game.joystick)
    label(button, family)     the name of a button in a text ("A", "LB"; "Cross", "L1"...)
    face_surface(b, d, fam)   a face button as a disc of diameter d (None for a button that is not a face button)
"""
import pygame

from i18n import t

XBOX, PLAYSTATION, PLAYSTATION5, NINTENDO = "xbox", "playstation", "playstation5", "nintendo"
FAMILIES = (XBOX, PLAYSTATION, PLAYSTATION5, NINTENDO)

PLAYSTATION_HINTS = ("playstation", "dualshock", "dualsense", "ps3", "ps4", "ps5", "sony")
NINTENDO_HINTS = ("nintendo", "switch", "joy-con", "joycon")

FACE_BUTTONS = (0, 1, 2, 3)                     # bottom, right, left, top (the numbers of an Xbox pad)
XBOX_NAMES = {0: "A", 1: "B", 2: "X", 3: "Y", 4: "LB", 5: "RB", 6: "Back", 7: "Start", 8: "L3", 9: "R3"}
PLAYSTATION_NAMES = {4: "L1", 5: "R1", 6: "Share", 7: "Options", 8: "L3", 9: "R3"}
PLAYSTATION5_NAMES = {**PLAYSTATION_NAMES, 6: "Create"}
NINTENDO_NAMES = {0: "B", 1: "A", 2: "Y", 3: "X", 4: "L", 5: "R", 6: "−", 7: "+", 8: "L3", 9: "R3"}
PS_FACE_KEYS = {0: "pad_ps_cross", 1: "pad_ps_circle", 2: "pad_ps_square", 3: "pad_ps_triangle"}

XBOX_COLORS = {0: (70, 175, 95), 1: (205, 75, 75), 2: (74, 127, 208), 3: (217, 180, 65)}
# PlayStation: the symbols in their own colours (blue cross, red circle, pink square, green triangle) on a dark disc
PLAYSTATION_COLORS = {0: (130, 174, 240), 1: (238, 122, 114), 2: (223, 144, 208), 3: (79, 207, 166)}
PLAYSTATION_DISC = (28, 30, 44)
NINTENDO_COLOR = (150, 156, 170)

_by_pad = {}
current = XBOX          # the family of the pad in use (note_game), for the texts and the help bar


def note_game(game):
    """Remember the family of the pad in use (a pad was used, plugged in or unplugged)."""
    global current
    current = family_of_game(game)
    return current


def family_for_name(name):
    """The family of a pad from its name (unknown names: Xbox, the layout every pad is given)."""
    low = str(name or "").lower()
    for hint in PLAYSTATION_HINTS:
        if hint in low:
            return PLAYSTATION5 if ("dualsense" in low or "ps5" in low) else PLAYSTATION
    for hint in NINTENDO_HINTS:
        if hint in low:
            return NINTENDO
    return XBOX


def family_of(joy):
    """The family of a pad (its name is read once)."""
    if joy is None:
        return XBOX
    try:
        key = joy.get_instance_id()
    except Exception:
        key = id(joy)
    fam = _by_pad.get(key)
    if fam is None:
        try:
            fam = family_for_name(joy.get_name())
        except Exception:
            fam = XBOX
        _by_pad[key] = fam
    return fam


def forget():
    """The pads were opened again: read their names again."""
    _by_pad.clear()


def family_of_game(game):
    """The family of the pad in use."""
    return family_of(getattr(game, "joystick", None))


def is_playstation(family):
    return family in (PLAYSTATION, PLAYSTATION5)


def label(button, family=None):
    """The name of a pad button in a text, as the pad of this family writes it."""
    b = int(button)
    family = family or current
    if is_playstation(family):
        if b in PS_FACE_KEYS:
            return t(PS_FACE_KEYS[b])
        return (PLAYSTATION5_NAMES if family == PLAYSTATION5 else PLAYSTATION_NAMES).get(b, "#%d" % b)
    if family == NINTENDO:
        return NINTENDO_NAMES.get(b, "#%d" % b)
    return XBOX_NAMES.get(b, "#%d" % b)


def face_color(button, family=None):
    """The colour of a face button (the symbol's colour on a PlayStation pad)."""
    family = family or current
    if is_playstation(family):
        return PLAYSTATION_COLORS.get(button, (200, 200, 210))
    if family == NINTENDO:
        return NINTENDO_COLOR
    return XBOX_COLORS.get(button, (200, 200, 210))


def draw_symbol(surf, button, center, r, color, width):
    """The PlayStation symbol of a face button: cross, circle, square or triangle (no font has them)."""
    cx, cy = center
    if button == 0:
        pygame.draw.line(surf, color, (cx - r, cy - r), (cx + r, cy + r), width)
        pygame.draw.line(surf, color, (cx - r, cy + r), (cx + r, cy - r), width)
    elif button == 1:
        pygame.draw.circle(surf, color, (round(cx), round(cy)), round(r * 1.05), width)
    elif button == 2:
        pygame.draw.rect(surf, color, (round(cx - r), round(cy - r), round(2 * r), round(2 * r)), width)
    elif button == 3:
        pts = [(cx, cy - r * 1.1), (cx + r * 1.15, cy + r * 0.85), (cx - r * 1.15, cy + r * 0.85)]
        pygame.draw.polygon(surf, color, pts, width)


def face_surface(button, d, family=None, font=None, letter_color=(255, 255, 255), ring=True):
    """A face button as a disc of diameter `d`: the coloured disc and its letter (Xbox, Nintendo) or the symbol drawn
    in its colour on a dark disc (PlayStation). `font`: for the letter (pygame font). None for another button."""
    if button not in FACE_BUTTONS:
        return None
    family = family or current
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    c = d // 2
    if is_playstation(family):
        col = PLAYSTATION_COLORS[button]
        pygame.draw.circle(s, PLAYSTATION_DISC, (c, c), c)
        pygame.draw.circle(s, col, (c, c), c, 2)
        draw_symbol(s, button, (c - 0.5 if d % 2 == 0 else c, c), d * 0.2, col, max(2, d // 11))
        return s
    pygame.draw.circle(s, face_color(button, family), (c, c), c)
    if ring:
        pygame.draw.circle(s, (255, 255, 255, 90), (c, c), c, 2)
    if font is not None:
        img = font.render(label(button, family), True, letter_color)
        s.blit(img, ((d - img.get_width()) // 2, (d - img.get_height()) // 2))
    return s
