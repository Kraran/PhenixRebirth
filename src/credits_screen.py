"""
Credits screen: layout (line kinds and heights) and the scrolling drawing.

Extracted from game.py (Game._credits_layout and the "credits" branch of
Game.draw). Functions take the Game object as `game` and behave exactly as
before; Game keeps thin methods with the old names.
"""
from settings import BASE_HEIGHT, BASE_WIDTH
from i18n import get_credits_lines, get_lang


def credits_layout(game):
    """Cached credits lines + row heights (language / logo size)."""
    logo_h = game.logo_frames[0].get_height() if game.logo_frames else 56
    lang = get_lang()
    pack = getattr(game, "_credits_layout_cache", None)
    if pack and pack[0] == lang and pack[1] == logo_h:
        return pack[2], pack[3], pack[4]
    lines = get_credits_lines()
    heights = []
    for kind, _ in lines:
        if kind == "title":
            heights.append(logo_h + 28)
        elif kind == "header":
            heights.append(46)
        elif kind == "blank":
            heights.append(40)
        elif kind == "sub":
            heights.append(36)
        else:
            heights.append(34)
    total = sum(heights)
    game._credits_layout_cache = (lang, logo_h, lines, heights, total)
    return lines, heights, total


def draw_credits(game):
    """Scrolling credits: logo, headers and lines, with wrap-around and the credits_watch achievement."""
    credits_lines, heights, total_h = game._credits_layout()
    y0 = game.credits_scroll
    if y0 < -total_h:
        if getattr(game, "credits_from_start", False):
            game._unlock_ach_meta("credits_watch")
        game.credits_scroll = float(BASE_HEIGHT)
        game.credits_from_start = True
        y0 = game.credits_scroll
    elif y0 > BASE_HEIGHT + 40:
        game.credits_scroll = float(-total_h)
        game.credits_from_start = False
        y0 = game.credits_scroll
    y = y0
    mid = BASE_WIDTH // 2 + int(round(getattr(game, "credits_x", 0.0)))
    logo_h = game.logo_frames[0].get_height() if game.logo_frames else 56
    for i, (kind, line) in enumerate(credits_lines):
        h = heights[i]
        if -logo_h < y < BASE_HEIGHT + 20 and kind != "blank":
            if kind == "title":
                if game.logo_frames:
                    img = game.logo_frames[game.logo_index % len(game.logo_frames)]
                    game.game_surface.blit(
                        img, (mid - img.get_width() // 2, int(y))
                    )
                else:
                    surf = game._txt(game.big_font, line, (255, 120, 255))
                    game.game_surface.blit(
                        surf, (mid - surf.get_width() // 2, int(y))
                    )
            elif kind == "header":
                surf = game._txt(game.medium_font, line, (255, 200, 120))
                game.game_surface.blit(surf, (mid - surf.get_width() // 2, int(y)))
            elif kind == "sub":
                surf = game._txt(game.font, line, (180, 160, 220))
                game.game_surface.blit(surf, (mid - surf.get_width() // 2, int(y)))
            else:
                surf = game._txt(game.font, line, (200, 200, 230))
                game.game_surface.blit(surf, (mid - surf.get_width() // 2, int(y)))
        y += h
