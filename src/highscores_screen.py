"""
High-score screen: ship icons, table rows and the 15-row list.

Extracted from game.py (Game._hs_ship_icon, Game._draw_hs_row and the
"highscores" branch of Game.draw). Functions take the Game object as `game`
and behave exactly as before; Game keeps thin methods with the old names.
"""
import pygame

from settings import BASE_HEIGHT, BASE_WIDTH, asset_path
from i18n import t
from highscores import load_highscores
from errlog import log_exc


def hs_ship_icon(game, sid, tint=None):
    """Tiny hull for the high-score table — same visual height after crop."""
    cache = getattr(game, "_hs_ship_icons", None)
    if cache is None:
        cache = game._hs_ship_icons = {}
    key_sid = "shield" if sid == "shield" else "phoenix"
    if key_sid == "shield":
        tn = tint if tint in ("red", "green", "violet") else "red"
        files = {
            "red": "player_ship_shield.png",
            "green": "player_ship_shield_green.png",
            "violet": "player_ship_shield_violet.png",
        }
    else:
        tn = tint if tint in ("argent", "blue", "gold") else "argent"
        files = {
            "argent": "player_ship.png",
            "blue": "player_ship_blue.png",
            "gold": "player_ship_gold.png",
        }
    key = key_sid + "_" + tn
    if key in cache:
        return cache[key]
    path = asset_path("sprites", files[tn])
    try:
        raw = pygame.image.load(path).convert_alpha()
    except Exception:
        raw = pygame.Surface((12, 18), pygame.SRCALPHA)
        pygame.draw.polygon(raw, (200, 200, 220), [(6, 0), (12, 18), (0, 18)])
    try:
        r = raw.get_bounding_rect(min_alpha=24)
        if r.width > 1 and r.height > 1:
            raw = raw.subsurface(r).copy()
    except Exception:
        log_exc("highscores_screen.hs_ship_icon")
    h = 22
    w = max(8, int(raw.get_width() * h / max(1, raw.get_height())))
    cache[key] = pygame.transform.smoothscale(raw, (w, h))
    return cache[key]


def draw_hs_row(game, surface, y, rank, name, score, col, score_right_x=None, coop=False, ship=None, ship2=None, veteran=False, tint=None):
    """Draw one high-score line: rank aligned on '.', score right-aligned."""
    if score_right_x is None:
        score_right_x = BASE_WIDTH // 2 + 160
    # Rank + dot (right-align rank digits against the dot)
    rank_s = f"{rank:>2}"
    dot = "."
    rank_surf = game._txt(game.font, rank_s, col)
    dot_surf = game._txt(game.font, dot, col)
    # Fixed column for the '.' so all ranks align
    dot_x = BASE_WIDTH // 2 - 120
    surface.blit(rank_surf, (dot_x - rank_surf.get_width(), y))
    surface.blit(dot_surf, (dot_x, y))
    # Name
    name_s = name if name else "---"
    name_surf = game._txt(game.font, f" {name_s}", col)
    surface.blit(name_surf, (dot_x + dot_surf.get_width() + 6, y))
    # Score right-aligned (or dashes)
    if score is None:
        sc_s = "—"
    else:
        sc_s = game.format_score(score)
    sc_surf = game._txt(game.font, sc_s, col)
    surface.blit(sc_surf, (score_right_x - sc_surf.get_width(), y))
    ix = score_right_x + 10
    if score is not None:
        ids = []
        if ship in ("phoenix", "shield"):
            ids.append(ship)
        elif not coop:
            ids = ["phoenix"]
        line_h = game.font.get_height()
        for sid in ids:
            icon = game._hs_ship_icon(sid, tint)
            iy = y + (line_h - icon.get_height()) // 2
            surface.blit(icon, (ix, iy))
            ix += icon.get_width() + 3
    if coop:
        game._draw_coop_mark(surface, ix + 4, y)
        ix += 22
    if veteran:
        game._draw_vet_mark(surface, ix + 4, y)


def draw_highscores(game):
    """High-score table (15 rows) drawn on the game surface."""
    hdr = game._txt(game.big_font, t("high_scores"), (255, 120, 255))
    game.game_surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 50))
    entries = game.hs_entries if game.hs_entries else load_highscores()
    base_y = 140
    score_right = BASE_WIDTH // 2 + 170
    for i in range(15):
        rank = i + 1
        if i < len(entries):
            game._draw_hs_row(
                game.game_surface, base_y + i * 28, rank,
                entries[i]["name"], entries[i]["score"],
                (200, 200, 230), score_right,
                coop=bool(entries[i].get("coop")),
                ship=entries[i].get("ship"),
                ship2=entries[i].get("ship2"),
                veteran=bool(entries[i].get("veteran")),
                tint=entries[i].get("tint"),
            )
        else:
            game._draw_hs_row(
                game.game_surface, base_y + i * 28, rank,
                "---", None, (100, 100, 120), score_right,
            )
    back = game._txt(game.font, t("ach_hint_hs"), (255, 220, 100))
    game.game_surface.blit(back, (BASE_WIDTH // 2 - back.get_width() // 2, BASE_HEIGHT - 60))
    game._draw_cheat_message()
