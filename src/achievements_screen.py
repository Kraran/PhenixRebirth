"""
Achievements ("hauts faits") list drawing.

Extracted from game.py (Game._draw_achievements_inner). Takes the Game object
as `game`; behaviour is unchanged. Game keeps a thin method with the old name.
"""
import pygame

from settings import BASE_WIDTH, BASE_HEIGHT
from i18n import t
from achievements import (
    CATALOG,
    load_achievements,
    scalable_progress,
    scalable_thresholds,
    scalable_tier,
    unlocked_count,
)


def draw_achievements_inner(game, surface):
    data = getattr(game, "ach_data", None)
    if not data:
        data = game.ach_data = load_achievements()
    unlocked = data.get("unlocked") or {}
    tc = getattr(game, "text_cache", None)
    hdr = (tc.get(game.medium_font, t("achievements"), (255, 180, 90))
           if tc else game._txt(game.medium_font, t("achievements"), (255, 180, 90)))
    surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 18))
    count_txt = f"{unlocked_count(data)} / {len(CATALOG)}"
    count = (tc.get(game.font, count_txt, (180, 180, 210))
             if tc else game._txt(game.font, count_txt, (180, 180, 210)))
    surface.blit(count, (BASE_WIDTH // 2 - count.get_width() // 2, 52))

    row_h, top, bottom, max_s = game._ach_view()
    x = 72
    col_w = BASE_WIDTH - 180
    body = getattr(game, "help_small", None) or game.font
    n_items = len(CATALOG)
    scroll = float(getattr(game, "ach_scroll", 0.0) or 0.0)
    scroll = max(0.0, min(max_s, scroll))
    game.ach_scroll = scroll

    # No surface.set_clip — SCALED/GPU present can freeze on clip changes.
    for i, (aid, kind) in enumerate(CATALOG):
        y = int(top + i * row_h - scroll)
        if y + row_h < top or y > bottom:
            continue
        on = aid in unlocked
        icon = game._ach_icon(kind, on)
        box = 52  # same frame for every haut-fait
        fy = y + (row_h - box) // 2 - 6
        ix = x + (box - icon.get_width()) // 2
        iy = fy + (box - icon.get_height()) // 2
        if fy < bottom and fy + box > top:
            surface.blit(icon, (ix, iy))
            tier = scalable_tier(aid, data) if on else None
            frame = {
                "bronze": (150, 88, 32),
                "silver": (196, 200, 210),
                "gold": (255, 210, 48),
            }.get(tier)
            if frame:
                pygame.draw.rect(surface, frame, pygame.Rect(x, fy, box, box), 3, border_radius=10)
        tx = x + 68
        if on:
            title = t("ach_" + aid)
            desc = t("ach_" + aid + "_d")
            tcol, dcol = (255, 230, 160), (190, 195, 220)
            date_s = game._fmt_ach_date(unlocked.get(aid))
            steps = scalable_thresholds(aid)
            if steps:
                prog = scalable_progress(aid, data)
                nxt = None
                for th in steps:
                    if prog < th:
                        nxt = th
                        break
                if nxt:
                    desc = f"{desc}  ({prog}/{nxt})"
                else:
                    desc = f"{desc}  ({prog})"
        else:
            title = t("ach_locked")
            desc = "—"
            tcol, dcol = (90, 90, 110), (70, 70, 85)
            date_s = ""
        ts = tc.get(game.font, title, tcol) if tc else game._txt(game.font, title, tcol)
        if y + 10 + ts.get_height() > top:
            surface.blit(ts, (tx, y + 10))
        if date_s:
            ds_date = (tc.get(body, date_s, (160, 170, 200))
                       if tc else body.render(date_s, True, (160, 170, 200)))
            surface.blit(ds_date, (x + col_w - ds_date.get_width(), y + 14))
        dy = y + 10 + ts.get_height() + 8
        for piece in game._wrap_ui(desc, body, col_w - 60)[:2]:
            if dy > bottom:
                break
            dsurf = (tc.get(body, piece, dcol) if tc else body.render(piece, True, dcol))
            if dy + dsurf.get_height() > top:
                surface.blit(dsurf, (tx, dy))
            dy += dsurf.get_height() + 4

    if max_s > 1:
        bar_x = BASE_WIDTH - 36
        bar_y, bar_h = top + 8, bottom - top - 16
        pygame.draw.rect(surface, (40, 40, 55), (bar_x, bar_y, 6, bar_h), border_radius=3)
        view_h = float(bottom - top)
        content_h = float(n_items * row_h)
        thumb_h = max(18, int(bar_h * view_h / max(view_h, content_h)))
        thumb_y = bar_y + int((bar_h - thumb_h) * scroll / max_s)
        pygame.draw.rect(surface, (200, 180, 120), (bar_x, thumb_y, 6, thumb_h), border_radius=3)

    hint = (tc.get(game.font, t("ach_hint_back"), (255, 220, 100))
            if tc else game._txt(game.font, t("ach_hint_back"), (255, 220, 100)))
    surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 42))
