"""
The look of the menus of the classic game, taken from the Adventure screens so that both read as one game:

- `panel`: a rounded panel that lets a little of the starfield through, with a thin blue-grey edge
  (the Adventure's MENU_ALPHA, fill and edge colours, see story.py);
- `draw_rows`: a list of choices. The chosen row gets the Adventure's lit frame (a warm fill and a gold edge) behind
  it; the text itself never moves (no "> " in front of it any more), and the frame has the same width on every row,
  so moving the cursor only moves the frame.

Every layer is cached by its size: drawing a menu costs a few blits.
"""
import pygame

MENU_ALPHA = 195                  # the same see-through as the Adventure panels (story.MENU_ALPHA)
PANEL_FILL = (16, 18, 28)
PANEL_EDGE = (70, 90, 130)
SEL_FILL = (40, 36, 20)
SEL_EDGE = (255, 210, 80)
TITLE = (255, 170, 80)            # the title of every menu screen, classic game and Adventure alike
DANGER = (235, 110, 100)          # red is kept for what destroys something (erase the scores, delete a save)
TEXT = (160, 160, 190)
TEXT_SEL = (255, 230, 120)
TEXT_OFF = (90, 90, 105)          # a greyed entry
TEXT_OFF_SEL = (190, 175, 120)    # a greyed entry under the cursor

_layers = {}


def _layer(w, h, fill, alpha, radius, edge, edge_w):
    key = (w, h, fill, alpha, radius, edge, edge_w)
    img = _layers.get(key)
    if img is None:
        img = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
        pygame.draw.rect(img, fill + (alpha,), img.get_rect(), border_radius=radius)
        if edge is not None and edge_w > 0:
            pygame.draw.rect(img, edge + (255,), img.get_rect(), edge_w, border_radius=radius)
        if len(_layers) > 160:
            _layers.clear()
        _layers[key] = img
    return img


def panel(surface, rect, radius=12, edge=PANEL_EDGE, alpha=MENU_ALPHA, fill=PANEL_FILL, edge_w=2):
    """A see-through rounded panel (the background of a list, a question, a table)."""
    r = pygame.Rect(rect)
    surface.blit(_layer(r.w, r.h, tuple(fill), int(alpha), radius, tuple(edge) if edge else None, edge_w), r.topleft)
    return r


def highlight(surface, rect, radius=6):
    """The lit frame behind the chosen row."""
    return panel(surface, rect, radius=radius, edge=SEL_EDGE, alpha=MENU_ALPHA, fill=SEL_FILL, edge_w=2)


def row_colour(selected, disabled=False):
    if disabled:
        return TEXT_OFF_SEL if selected else TEXT_OFF
    return TEXT_SEL if selected else TEXT


def draw_rows(game, surface, font, labels, top, spacing, index, x=None, left=None,
              disabled=(), pad_x=22, pad_y=3, min_width=0, back_panel=True, panel_pad=(26, 14)):
    """A list of choices, centred on `x` (default: the middle of the screen) or aligned on `left`.

    Returns the rect of the whole list (with its panel margin). The rows are `spacing` px apart starting at `top`;
    `index` is the chosen row; `disabled` holds the indexes drawn greyed."""
    imgs = [game._txt(font, str(label), row_colour(i == index, i in disabled)) for i, label in enumerate(labels)]
    if not imgs:
        return pygame.Rect(0, top, 0, 0)
    row_h = max(i.get_height() for i in imgs)
    inner_w = max(min_width, max(i.get_width() for i in imgs)) + pad_x * 2
    if left is None:
        cx = surface.get_width() // 2 if x is None else int(x)
        bar_x = cx - inner_w // 2
    else:
        bar_x = int(left) - pad_x
    n = len(imgs)
    box = pygame.Rect(bar_x, top - pad_y, inner_w, spacing * (n - 1) + row_h + pad_y * 2)
    outer = box.inflate(panel_pad[0] * 2, panel_pad[1] * 2)
    if back_panel:
        panel(surface, outer)
    if 0 <= index < n:
        highlight(surface, pygame.Rect(bar_x, top + index * spacing - pad_y, inner_w, row_h + pad_y * 2))
    for i, img in enumerate(imgs):
        y = top + i * spacing + (row_h - img.get_height()) // 2
        if left is None:
            surface.blit(img, (cx - img.get_width() // 2, y))
        else:
            surface.blit(img, (int(left), y))
    return outer
