"""
Achievements ("hauts faits") screen: a grid of the 32 icons on the left, and on the right a panel that tells
everything about the one under the cursor (how to get it, its tiers, how far along the player is, the date).

The secret ones (achievements.SECRETS) show a "?" and no name until they are unlocked.

The grid and the panel are drawn on layers that are kept until something changes (the save, the language, the
cursor): a frame only puts them on screen, with the cursor's frame on top.
"""
import pygame

import fonts
import hint_bar
import i18n
import menu_ui

from settings import BASE_WIDTH
from i18n import t
from achievements import (
    CATALOG,
    SECRETS,
    TIER_ORDER,
    is_hidden,
    load_achievements,
    scalable_progress,
    scalable_thresholds,
    scalable_tier,
    unlocked_count,
)

COLS = 8
ROWS = (len(CATALOG) + COLS - 1) // COLS
CELL, GAP = 80, 12
GRID_X, GRID_Y = 52, 96
GRID_W = COLS * CELL + (COLS - 1) * GAP
GRID_H = ROWS * CELL + (ROWS - 1) * GAP
SUMMARY_Y = GRID_H + 22                       # below the grid, in the grid's layer
LAYER_H = SUMMARY_Y + 80
DETAIL = pygame.Rect(GRID_X + GRID_W + 36, 86, BASE_WIDTH - (GRID_X + GRID_W + 36) - 40, 500)

TIER_EDGE = {"bronze": (196, 120, 56), "silver": (200, 205, 215), "gold": (255, 210, 48)}
DONE = (150, 220, 160)                        # unlocked, first step (no metal yet)
EDGE_ON, EDGE_OFF = (110, 130, 170), (48, 52, 70)
FILL_ON, FILL_OFF = (30, 32, 48), (18, 19, 28)
BAR_BACK, BAR_FILL = (40, 42, 60), (120, 200, 255)
STEP_OFF = (85, 88, 110)
TITLE_ON, TITLE_OFF = (255, 230, 160), (200, 200, 220)
TEXT, TEXT_DIM = (200, 205, 228), (150, 150, 175)

_LAYERS = {}


def _keep(key, img):
    if len(_LAYERS) > 96:
        _LAYERS.clear()
    _LAYERS[key] = img
    return img


# --- the cursor ----------------------------------------------------------------------------------------------------
def selected(game):
    i = int(getattr(game, "ach_index", 0) or 0)
    return max(0, min(len(CATALOG) - 1, i))


def move(game, dx, dy):
    """Left / Right: the previous / next one (row after row). Up / Down: the same column, one row up / down."""
    n = len(CATALOG)
    i = selected(game)
    if dx:
        i = (i + int(dx)) % n
    if dy:
        r, c = divmod(i, COLS)
        rows = ROWS
        for _ in range(rows):                 # (a last row that is not full: skip its holes)
            r = (r + int(dy)) % rows
            if r * COLS + c < n:
                break
        i = r * COLS + c
    game.ach_index = i


def cell_rect(i):
    r, c = divmod(i, COLS)
    return pygame.Rect(GRID_X + c * (CELL + GAP), GRID_Y + r * (CELL + GAP), CELL, CELL)


# --- what the panel says ---------------------------------------------------------------------------------------------
_THOUSANDS = {"en": ",", "de": ".", "es": ".", "it": ".", "pt": ".", "nl": ".", "tr": ".", "da": "."}


def fmt_num(n):
    """1 266 / 1,266 / 1.266, as each language writes it."""
    return f"{int(n):,}".replace(",", _THOUSANDS.get(i18n.get_lang(), " "))


def _tier_name(name):
    return t("ach_done") if name == "normal" else t("ach_tier_" + name)


def steps_of(aid):
    """The tiers worth showing: [(tier, threshold)...], or [] (one step only, or not a scalable one)."""
    steps = scalable_thresholds(aid)
    if not steps or len(set(steps)) < 2:
        return []
    return list(zip(TIER_ORDER, steps))


def progress_line(aid, data):
    """"You are at 734. Next tier: Gold, 1 266 to go." (None when there is nothing to count)."""
    steps = scalable_thresholds(aid)
    if not steps:
        return None
    prog = scalable_progress(aid, data)
    unlocked = aid in (data.get("unlocked") or {})
    if len(set(steps)) < 2:                   # a single step ("To boldly go"): only while it is not reached
        return None if unlocked else t("ach_progress_unlock").format(n=fmt_num(prog), goal=fmt_num(steps[0]))
    nxt = next(((name, th) for name, th in zip(TIER_ORDER, steps) if prog < th), None)
    if nxt is None:
        return t("ach_progress_done").format(n=fmt_num(prog))
    if nxt[0] == "normal":
        return t("ach_progress_unlock").format(n=fmt_num(prog), goal=fmt_num(nxt[1]))
    return t("ach_progress_next").format(n=fmt_num(prog), tier=_tier_name(nxt[0]), left=fmt_num(nxt[1] - prog))


def detail_texts(game, aid, data):
    """The panel's texts for one achievement (also what the tests read)."""
    unlocked = data.get("unlocked") or {}
    if is_hidden(aid, data):
        return {"hidden": True, "title": t("ach_secret"), "status": t("ach_secret_status"),
                "how": t("ach_secret_d"), "progress": None, "steps": []}
    on = aid in unlocked
    if on:
        tier = scalable_tier(aid, data) or "normal"
        status = f"{_tier_name(tier)} · {game._fmt_ach_date(unlocked.get(aid))}"
    else:
        status = t("ach_locked")
    return {"hidden": False, "title": t("ach_" + aid), "status": status, "how": t("ach_" + aid + "_d"),
            "progress": progress_line(aid, data), "steps": steps_of(aid)}


# --- drawing ---------------------------------------------------------------------------------------------------------
def _icon(game, kind, on, scale):
    key = ("icon", kind, bool(on), scale)
    img = _LAYERS.get(key)
    if img is None:
        raw = game._ach_icon(kind, on)
        w, h = raw.get_size()
        img = pygame.transform.scale(raw, (max(1, int(w * scale)), max(1, int(h * scale))))
        if not on:
            img = img.copy()
            img.set_alpha(170)
        _keep(key, img)
    return img


def _question(size, colour):
    key = ("q", size, colour)
    img = _LAYERS.get(key)
    if img is None:
        img = _keep(key, fonts.title(size).render("?", True, colour))
    return img


def _frame_colour(on, tier):
    if not on:
        return EDGE_OFF
    return TIER_EDGE.get(tier, EDGE_ON)


def _cell(game, surface, rect, aid, kind, data):
    on = aid in (data.get("unlocked") or {})
    tier = scalable_tier(aid, data) if on else None
    pygame.draw.rect(surface, FILL_ON if on else FILL_OFF, rect, border_radius=10)
    pygame.draw.rect(surface, _frame_colour(on, tier), rect, 3 if tier in TIER_EDGE else 2, border_radius=10)
    if is_hidden(aid, data):
        q = _question(34, (90, 92, 115))
        surface.blit(q, q.get_rect(center=rect.center))
        return
    ic = _icon(game, kind, on, 1.5)
    surface.blit(ic, ic.get_rect(center=rect.center))
    # a thin line under the icon: the way to the next tier
    steps = scalable_thresholds(aid)
    if steps:
        prog = scalable_progress(aid, data)
        nxt = next((th for th in steps if prog < th), None)
        if nxt and prog > 0:
            prev = max([0] + [th for th in steps if th <= prog])
            f = (prog - prev) / max(1, nxt - prev)
            bar = pygame.Rect(rect.x + 10, rect.bottom - 10, rect.w - 20, 4)
            pygame.draw.rect(surface, BAR_BACK, bar, border_radius=2)
            pygame.draw.rect(surface, BAR_FILL, (bar.x, bar.y, max(2, int(bar.w * f)), bar.h), border_radius=2)


def _summary(game, surface, y, data):
    n, total = unlocked_count(data), len(CATALOG)
    count = game.font.render(f"{n} / {total}", True, (220, 220, 240))
    surface.blit(count, (0, y))
    bar = pygame.Rect(count.get_width() + 18, y + count.get_height() // 2 - 5, GRID_W - count.get_width() - 18, 10)
    pygame.draw.rect(surface, BAR_BACK, bar, border_radius=5)
    if n:
        pygame.draw.rect(surface, menu_ui.SEL_EDGE, (bar.x, bar.y, max(4, int(bar.w * n / total)), bar.h),
                         border_radius=5)
    tiers = data.get("tiers") or {}
    unlocked = data.get("unlocked") or {}
    counts = {k: sum(1 for aid, v in tiers.items() if v == k and aid in unlocked) for k in TIER_EDGE}
    secrets = sum(1 for aid in SECRETS if aid not in unlocked)
    sep = " : " if i18n.get_lang() == "fr" else ": "
    for font, gap in ((game.body_font, 30), (game.body_font, 18), (fonts.body(19), 16), (fonts.body(17), 12)):
        parts = [(TIER_EDGE[k], font.render(f"{t('ach_tier_' + k)}{sep}{counts[k]}", True, (190, 195, 220)))
                 for k in ("gold", "silver", "bronze")]
        sec = font.render(t("ach_secrets_left").format(n=secrets), True, TEXT_DIM)
        if sum(26 + img.get_width() + gap for _c, img in parts) + sec.get_width() <= GRID_W - 8:
            break
    x = 0
    y2 = y + count.get_height() + 12
    for colour, img in parts:
        pygame.draw.circle(surface, colour, (x + 9, y2 + img.get_height() // 2), 9)
        surface.blit(img, (x + 26, y2))
        x += 26 + img.get_width() + gap
    surface.blit(sec, (x, y2))


def _signature(data):
    return (i18n.get_lang(), tuple(sorted((data.get("unlocked") or {}).items())),
            tuple(sorted((data.get("progress") or {}).items())), tuple(sorted((data.get("tiers") or {}).items())))


def _grid_layer(game, data):
    key = ("grid", _signature(data))
    img = _LAYERS.get(key)
    if img is None:
        img = pygame.Surface((GRID_W, LAYER_H), pygame.SRCALPHA)
        for i, (aid, kind) in enumerate(CATALOG):
            r = cell_rect(i).move(-GRID_X, -GRID_Y)
            _cell(game, img, r, aid, kind, data)
        _summary(game, img, SUMMARY_Y, data)
        for k in [k for k in _LAYERS if k[0] == "grid"]:
            del _LAYERS[k]
        _keep(key, img)
    return img


def _fit(text, sizes, width, kind="text"):
    """The largest of `sizes` that holds `text` on one line (else the smallest)."""
    for size in sizes:
        font = fonts.get(kind, size) if kind != "text" else fonts.text(size)
        if font.size(text)[0] <= width:
            return font
    return font


def _steps(surface, x, y, w, aid, data):
    """The tiers on a line: a dot each (lit when reached), its name and its count under it."""
    steps = steps_of(aid)
    prog = scalable_progress(aid, data)
    bar = pygame.Rect(x + 8, y + 10, w - 16, 10)
    pygame.draw.rect(surface, BAR_BACK, bar, border_radius=5)
    pos = [bar.x + int((bar.w - 26) * (i + 1) / len(steps)) for i in range(len(steps))]
    pts, px = [0] + [th for _n, th in steps], [bar.x] + pos
    fill_x = bar.x
    for i in range(len(steps)):
        a, b = pts[i], pts[i + 1]
        if prog >= b:
            fill_x = px[i + 1]
        else:
            if prog > a:
                fill_x = px[i] + int((px[i + 1] - px[i]) * (prog - a) / max(1, b - a))
            break
    if fill_x > bar.x:
        pygame.draw.rect(surface, BAR_FILL, (bar.x, bar.y, fill_x - bar.x, bar.h), border_radius=5)
    small = fonts.body(17)
    for i, (name, th) in enumerate(steps):
        reached = prog >= th
        colour = (TIER_EDGE.get(name, DONE) if reached else STEP_OFF)
        pygame.draw.circle(surface, colour, (pos[i], bar.centery), 9)
        pygame.draw.circle(surface, menu_ui.PANEL_FILL, (pos[i], bar.centery), 9, 2)
        label = small.render(t("ach_step_first") if name == "normal" else t("ach_tier_" + name), True, colour)
        num = small.render(fmt_num(th), True, colour)
        surface.blit(label, (pos[i] - label.get_width() // 2, bar.bottom + 12))
        surface.blit(num, (pos[i] - num.get_width() // 2, bar.bottom + 32))
    return bar.bottom + 64


def _detail_layer(game, aid, kind, data):
    unlocked = data.get("unlocked") or {}
    key = ("detail", aid, i18n.get_lang(), unlocked.get(aid), scalable_progress(aid, data),
           scalable_tier(aid, data))
    img = _LAYERS.get(key)
    if img is not None:
        return img
    for k in [k for k in _LAYERS if k[0] == "detail"]:
        del _LAYERS[k]
    img = pygame.Surface(DETAIL.size, pygame.SRCALPHA)
    info = detail_texts(game, aid, data)
    on = aid in unlocked
    tier = scalable_tier(aid, data) if on else None
    x, y, w = 24, 22, DETAIL.w - 48
    box = pygame.Rect(x, y, 84, 84)
    pygame.draw.rect(img, FILL_ON if on else FILL_OFF, box, border_radius=12)
    pygame.draw.rect(img, TIER_EDGE.get(tier, EDGE_ON) if on else (60, 64, 84), box, 3, border_radius=12)
    if info["hidden"]:
        q = _question(52, (110, 112, 140))
        img.blit(q, q.get_rect(center=box.center))
    else:
        ic = _icon(game, kind, on, 2.0)
        img.blit(ic, ic.get_rect(center=box.center))
    # the name (smaller, or on two lines, when it is long) and the state under it
    tx = box.right + 18
    tw = DETAIL.w - tx - 16
    tfont = _fit(info["title"], (28, 24, 21), tw)
    lines = [info["title"]] if tfont.size(info["title"])[0] <= tw else game._wrap_ui(info["title"], tfont, tw)[:2]
    ty = y + (4 if len(lines) == 1 else -4)
    for line in lines:
        s = tfont.render(line, True, TITLE_ON if on else TITLE_OFF)
        img.blit(s, (tx, ty))
        ty += s.get_height() - 2
    if on:
        scol = TIER_EDGE.get(tier, DONE)
    else:
        scol = (140, 140, 165)
    sfont = game.body_font if game.body_font.size(info["status"])[0] <= tw else fonts.body(18)
    img.blit(sfont.render(info["status"], True, scol), (tx, max(ty + 4, y + 46)))
    # how to get it
    y = box.bottom + 22
    head = fonts.text(18)
    img.blit(head.render(t("ach_how"), True, menu_ui.TITLE), (x, y))
    y += 28
    body = game.body_font
    colour = TEXT_DIM if info["hidden"] else TEXT
    for line in game._wrap_ui(info["how"], body, w):
        img.blit(body.render(line, True, colour), (x, y))
        y += 28
    # its tiers and how far along the player is
    if info["steps"]:
        y += 18
        img.blit(head.render(t("ach_steps"), True, menu_ui.TITLE), (x, y))
        y = _steps(img, x, y + 34, w, aid, data)
    elif info["progress"]:
        y += 12
    if info["progress"]:
        for line in game._wrap_ui(info["progress"], body, w):
            img.blit(body.render(line, True, (190, 195, 220)), (x, y))
            y += 28
    return _keep(key, img)


def draw_achievements_inner(game, surface):
    data = getattr(game, "ach_data", None)
    if not data:
        data = game.ach_data = load_achievements()
    tc = getattr(game, "text_cache", None)
    hdr = (tc.get(game.medium_font, t("achievements"), menu_ui.TITLE)
           if tc else game._txt(game.medium_font, t("achievements"), menu_ui.TITLE))
    surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 18))

    surface.blit(_grid_layer(game, data), (GRID_X, GRID_Y))
    i = selected(game)
    pygame.draw.rect(surface, menu_ui.SEL_EDGE, cell_rect(i).inflate(10, 10), 3, border_radius=13)

    menu_ui.panel(surface, DETAIL)
    aid, kind = CATALOG[i]
    surface.blit(_detail_layer(game, aid, kind, data), DETAIL.topleft)

    hint_bar.draw_for(game, surface)
