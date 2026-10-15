"""
Achievements ("hauts faits") screen, in two pages (achievements.PAGES): ARCADE and AVENTURE, chosen by the tabs
under the title. Each page is a grid of cards on the left (src/achievement_cards.py: the picture of the achievement
in a frame whose metal is the tier) and, on the right, a panel that tells everything about the one under the
cursor (how to get it, its tiers, how far along the player is, the date).

The cursor goes from one page to the other across the edges of the grid (Left on the first column, Right on the
last one). The secret ones (achievements.SECRETS) show a "?" and no name until they are unlocked.

The grid and the panel are drawn on layers that are kept until something changes (the save, the language, the
cursor): a frame only puts them on screen, with the cursor's frame on top.
"""
import pygame

import achievement_cards
import fonts
import hint_bar
import i18n
import menu_ui

from settings import BASE_WIDTH
from i18n import t
from achievements import (
    PAGES,
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
ROWS = 4                                      # the most a page has (a page with fewer cards leaves room below)
CELL, GAP = 80, 12
GRID_X, GRID_Y = 52, 98
GRID_W = COLS * CELL + (COLS - 1) * GAP
GRID_H = ROWS * CELL + (ROWS - 1) * GAP
SUMMARY_Y = GRID_H + 20                       # below the grid, in the grid's layer
LAYER_H = SUMMARY_Y + 80
DETAIL = pygame.Rect(GRID_X + GRID_W + 36, 88, BASE_WIDTH - (GRID_X + GRID_W + 36) - 40, 500)
TABS_Y = 60                                   # the tabs ARCADE / AVENTURE, under the title
BIG = 96                                      # the card in the panel

TIER_EDGE = {"bronze": (196, 120, 56), "silver": (200, 205, 215), "gold": (255, 210, 48)}
DONE = (150, 220, 160)                        # unlocked, first step (no metal yet)
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


# --- the pages and the cursor ----------------------------------------------------------------------------------------
def page(game):
    return max(0, min(len(PAGES) - 1, int(getattr(game, "ach_page", 0) or 0)))


def catalog(game):
    """The (id, icon) of the page on screen."""
    return PAGES[page(game)][1]


def _rows(n):
    return (n + COLS - 1) // COLS


def selected(game):
    i = int(getattr(game, "ach_index", 0) or 0)
    return max(0, min(len(catalog(game)) - 1, i))


def _enter(game, new_page, row, last):
    """Put the cursor on page `new_page`, row `row` (or the last one there is), first or last card of that row."""
    game.ach_page = new_page % len(PAGES)
    n = len(catalog(game))
    row = max(0, min(_rows(n) - 1, row))
    in_row = min(COLS, n - row * COLS)
    game.ach_index = row * COLS + (in_row - 1 if last else 0)


def move(game, dx, dy):
    """Left / Right: the card before / after in the row; past the edge of the grid, the page before / after
    (the pages go round). Up / Down: the same column, one row up / down (the grid goes round)."""
    n = len(catalog(game))
    i = selected(game)
    r, c = divmod(i, COLS)
    if dx:
        in_row = min(COLS, n - r * COLS)
        if dx < 0 and c == 0:
            _enter(game, page(game) - 1, r, last=True)
            return
        if dx > 0 and c >= in_row - 1:
            _enter(game, page(game) + 1, r, last=False)
            return
        i += 1 if dx > 0 else -1
    if dy:
        rows = _rows(n)
        for _ in range(rows):                 # (a last row that is not full: skip its holes)
            r = (r + int(dy)) % rows
            if r * COLS + c < n:
                break
        i = r * COLS + c
        if i >= n:
            i = n - 1
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
def card_state(aid, data):
    """locked / hidden (a secret not found yet) / normal / bronze / silver / gold."""
    if is_hidden(aid, data):
        return "hidden"
    if aid not in (data.get("unlocked") or {}):
        return "locked"
    tier = scalable_tier(aid, data)
    return tier if tier in TIER_EDGE else "normal"


def _cell(game, surface, rect, aid, kind, data):
    state = card_state(aid, data)
    surface.blit(achievement_cards.card(aid, state, rect.w), rect)
    if state == "hidden":
        return
    # a thin line at the bottom of the card: the way to the next tier
    steps = scalable_thresholds(aid)
    if steps:
        prog = scalable_progress(aid, data)
        nxt = next((th for th in steps if prog < th), None)
        if nxt and prog > 0:
            prev = max([0] + [th for th in steps if th <= prog])
            f = (prog - prev) / max(1, nxt - prev)
            bar = pygame.Rect(rect.x + 12, rect.bottom - 13, rect.w - 24, 5)
            pygame.draw.rect(surface, (10, 12, 20), bar.inflate(4, 4), border_radius=3)
            pygame.draw.rect(surface, BAR_BACK, bar, border_radius=2)
            pygame.draw.rect(surface, BAR_FILL, (bar.x, bar.y, max(2, int(bar.w * f)), bar.h), border_radius=2)


def _summary(game, surface, y, data, cat):
    """Under the grid, for the page on screen: unlocked / all, the tiers, the secrets still to find."""
    ids = [aid for aid, _kind in cat]
    n, total = unlocked_count(data, ids), len(ids)
    count = game.font.render(f"{n} / {total}", True, (220, 220, 240))
    surface.blit(count, (0, y))
    bar = pygame.Rect(count.get_width() + 18, y + count.get_height() // 2 - 5, GRID_W - count.get_width() - 18, 10)
    pygame.draw.rect(surface, BAR_BACK, bar, border_radius=5)
    if n:
        pygame.draw.rect(surface, menu_ui.SEL_EDGE, (bar.x, bar.y, max(4, int(bar.w * n / total)), bar.h),
                         border_radius=5)
    tiers = data.get("tiers") or {}
    unlocked = data.get("unlocked") or {}
    counts = {k: sum(1 for aid in ids if tiers.get(aid) == k and aid in unlocked) for k in TIER_EDGE}
    secrets = sum(1 for aid in ids if aid in SECRETS and aid not in unlocked)
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


def _grid_layer(game, data, pg=None):
    pg = page(game) if pg is None else pg
    cat = PAGES[pg][1]
    key = ("grid", pg, _signature(data))
    img = _LAYERS.get(key)
    if img is None:
        img = pygame.Surface((GRID_W, LAYER_H), pygame.SRCALPHA)
        for i, (aid, kind) in enumerate(cat):
            r = cell_rect(i).move(-GRID_X, -GRID_Y)
            _cell(game, img, r, aid, kind, data)
        _summary(game, img, SUMMARY_Y, data, cat)
        for k in [k for k in _LAYERS if k[0] == "grid" and k[1] == pg]:
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
    box = pygame.Rect(x, y, BIG, BIG)
    img.blit(achievement_cards.card(aid, card_state(aid, data), BIG), box)
    # the name (smaller, or on two lines, when it is long) and the state under it
    tx = box.right + 18
    tw = DETAIL.w - tx - 16
    tfont = _fit(info["title"], (28, 24, 21), tw)
    lines = [info["title"]] if tfont.size(info["title"])[0] <= tw else game._wrap_ui(info["title"], tfont, tw)[:2]
    ty = y + (12 if len(lines) == 1 else 2)
    for line in lines:
        s = tfont.render(line, True, TITLE_ON if on else TITLE_OFF)
        img.blit(s, (tx, ty))
        ty += s.get_height() - 2
    if on:
        scol = TIER_EDGE.get(tier, DONE)
    else:
        scol = (140, 140, 165)
    sfont = game.body_font if game.body_font.size(info["status"])[0] <= tw else fonts.body(18)
    img.blit(sfont.render(info["status"], True, scol), (tx, max(ty + 4, y + 54)))
    # how to get it
    y = box.bottom + 18
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


def _tabs(game, surface):
    """ARCADE / AVENTURE under the title, the page on screen lit, each with its count."""
    data = game.ach_data or {}
    f = fonts.text(20)
    small = fonts.body(17)
    parts = []
    for i, (key, cat) in enumerate(PAGES):
        on = i == page(game)
        label = f.render(t(key), True, menu_ui.TEXT_SEL if on else menu_ui.TEXT)
        count = small.render(f"{unlocked_count(data, [a for a, _k in cat])}/{len(cat)}", True,
                             (220, 200, 140) if on else (120, 120, 145))
        parts.append((on, label, count))
    gap, inner = 46, 10
    total = sum(lab.get_width() + inner + cnt.get_width() for _on, lab, cnt in parts) + gap * (len(parts) - 1)
    x = BASE_WIDTH // 2 - total // 2
    # small arrows at both ends: the pages turn at the edges of the grid
    cy = TABS_Y + 12
    for ax, way in ((x - 30, -1), (x + total + 30, 1)):
        pygame.draw.polygon(surface, (150, 150, 180), [(ax + 5 * way, cy), (ax - 4 * way, cy - 7), (ax - 4 * way, cy + 7)])
    for on, label, count in parts:
        w = label.get_width() + inner + count.get_width()
        if on:
            menu_ui.highlight(surface, pygame.Rect(x - 12, TABS_Y - 3, w + 24, 30))
        surface.blit(label, (x, TABS_Y))
        surface.blit(count, (x + label.get_width() + inner, TABS_Y + label.get_height() - count.get_height() - 1))
        x += w + gap


def warm(game):
    """Draw the layers of both pages now (called when the screen opens: the first frame is not slowed down)."""
    data = getattr(game, "ach_data", None) or load_achievements()
    for pg in range(len(PAGES)):
        _grid_layer(game, data, pg)


def draw_achievements_inner(game, surface):
    data = getattr(game, "ach_data", None)
    if not data:
        data = game.ach_data = load_achievements()
    tc = getattr(game, "text_cache", None)
    hdr = (tc.get(game.medium_font, t("achievements"), menu_ui.TITLE)
           if tc else game._txt(game.medium_font, t("achievements"), menu_ui.TITLE))
    surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 14))
    _tabs(game, surface)

    surface.blit(_grid_layer(game, data), (GRID_X, GRID_Y))
    i = selected(game)
    pygame.draw.rect(surface, menu_ui.SEL_EDGE, cell_rect(i).inflate(10, 10), 3, border_radius=13)

    menu_ui.panel(surface, DETAIL)
    aid, kind = catalog(game)[i]
    surface.blit(_detail_layer(game, aid, kind, data), DETAIL.topleft)

    hint_bar.draw_for(game, surface)
