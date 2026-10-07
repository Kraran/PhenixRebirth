"""
HUD Phenix gauge.

Extracted from game.py (Game._draw_phenix_gauge). The function takes the Game
object as `game` and behaves exactly as before.
"""
import math

import pygame

from settings import BASE_WIDTH


def draw_phenix_gauge(game, ship=None, gx=18, gy=100, align="left"):
    """HUD: 10-segment Phenix gauge + fire around label from level 3."""
    if ship is None:
        ship = getattr(game, "player", None)
    if ship is None:
        return
    gauge = float(getattr(ship, "phenix_gauge", 0))
    level = int(gauge)  # for label threshold
    pal = getattr(ship, "palette", "argent")
    blue = pal == "blue"
    gold = pal == "gold"
    shield_ship = bool(getattr(ship, "uses_shield", False) or getattr(ship, "ship_id", "") == "shield")
    seg_w, seg_h, gap = 14, 10, 3
    total_h = 10 * (seg_h + gap)
    pygame.draw.rect(game.game_surface, (20, 20, 35), (gx - 3, gy - 3, seg_w + 6, total_h + 3), border_radius=3)
    active = getattr(ship, "is_phenix", False)
    for i in range(10):
        y = gy + (9 - i) * (seg_h + gap)
        # How much of this segment is filled (supports fractional drain)
        seg_fill = max(0.0, min(1.0, gauge - i))
        if seg_fill > 0:
            t = (i + 1) / 10.0
            if shield_ship:
                # Bottom = ship color, top ≈ white
                pal = getattr(ship, "palette", "red")
                if pal == "green":
                    base = (40, 170, 55) if not active else (50, 210, 70)
                elif pal == "violet":
                    base = (140, 50, 180) if not active else (190, 80, 230)
                else:
                    base = (210, 70, 70) if not active else (255, 90, 90)
                col = (
                    int(base[0] + (255 - base[0]) * t),
                    int(base[1] + (255 - base[1]) * t),
                    int(base[2] + (255 - base[2]) * t),
                )
            elif gold:
                if active:
                    col = (255, int(190 + 50 * t), int(40 + 80 * t))
                else:
                    col = (
                        int(180 + 75 * t),
                        int(130 + 90 * t),
                        int(30 + 40 * t),
                    )
            elif blue:
                if active:
                    col = (int(40 + 20 * t), int(140 + 80 * t), 255)
                else:
                    col = (
                        int(40 * (1.0 - t)),
                        int(80 + 100 * t),
                        int(255 * min(1.0, 0.5 + t * 0.5)),
                    )
            elif active:
                col = (255, int(140 + 80 * t), int(30 + 20 * t))
            else:
                col = (
                    int(255 * min(1.0, 0.5 + t * 0.5)),
                    int(80 + 100 * t),
                    int(40 * (1.0 - t)),
                )
            fh = max(1, int(seg_h * seg_fill))
            pygame.draw.rect(
                game.game_surface, col,
                (gx, y + (seg_h - fh), seg_w, fh),
                border_radius=2,
            )
        else:
            pygame.draw.rect(game.game_surface, (40, 40, 55), (gx, y, seg_w, seg_h), border_radius=2)

    lab_y = gy + total_h + 6
    tc = game.text_cache
    right = align == "right" or gx > BASE_WIDTH // 2
    shield_ship = bool(getattr(ship, "uses_shield", False) or getattr(ship, "ship_id", "") == "shield")
    tag = "SHIELD" if shield_ship else "PHENIX"
    if shield_ship or level >= 3:
        ticks = pygame.time.get_ticks() * 0.001
        pulse = 0.75 + 0.25 * abs(math.sin(ticks * 4.0))
        power = gauge / 10.0 if shield_ship else (level - 3) / 7.0
        if shield_ship:
            pal = getattr(ship, "palette", "red")
            if pal == "green":
                lab = tc.get(game.font, tag, (120, 200, 140))
                glow = tc.get(game.font, tag, (70, 160, 90))
            elif pal == "violet":
                lab = tc.get(game.font, tag, (200, 150, 230))
                glow = tc.get(game.font, tag, (160, 80, 200))
            else:
                lab = tc.get(game.font, tag, (230, 140, 140))
                glow = tc.get(game.font, tag, (200, 80, 80))
        elif gold:
            g_q = int((190 + 50 * power * pulse) // 8) * 8
            lab = tc.get(game.font, tag, (255, g_q, 80))
            glow = tc.get(game.font, tag, (220, 160, 40))
        elif blue:
            g_q = int((180 + 50 * power * pulse) // 8) * 8
            lab = tc.get(game.font, tag, (140, g_q, 255))
            glow = tc.get(game.font, tag, (80, 180, 255))
        else:
            g_q = int((140 + 80 * power * pulse) // 8) * 8
            b_q = int((40 + 40 * power) // 8) * 8
            lab = tc.get(game.font, tag, (255, g_q, b_q))
            glow_g = int((100 + 60 * power) // 8) * 8
            glow = tc.get(game.font, tag, (255, glow_g, 20))
        lab_x = (gx + seg_w - lab.get_width()) if right else (gx - 2)
        alpha = int(50 + 40 * power * pulse)
        glow.set_alpha(alpha)
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            game.game_surface.blit(glow, (lab_x + ox, lab_y + oy))
        game.game_surface.blit(lab, (lab_x, lab_y))
    else:
        if shield_ship:
            pal = getattr(ship, "palette", "red")
            if pal == "green":
                idle = (90, 160, 110)
            elif pal == "violet":
                idle = (150, 110, 180)
            else:
                idle = (190, 120, 120)
        elif gold:
            idle = (160, 130, 70)
        elif blue:
            idle = (100, 140, 180)
        else:
            idle = (120, 110, 100)
        lab = tc.get(game.font, tag, idle)
        lab_x = (gx + seg_w - lab.get_width()) if right else (gx - 2)
        game.game_surface.blit(lab, (lab_x, lab_y))

    if shield_ship:
        pal = getattr(ship, "palette", "red")
        if pal == "green":
            num_col = (130, 210, 150) if (level >= 3 or active) else (100, 150, 115)
        elif pal == "violet":
            num_col = (210, 170, 240) if (level >= 3 or active) else (150, 120, 180)
        else:
            num_col = (230, 150, 150) if (level >= 3 or active) else (180, 120, 120)
    else:
        if level >= 3 or active:
            num_col = (255, 230, 140) if gold else ((180, 230, 255) if blue else (255, 220, 160))
        else:
            num_col = (140, 140, 150)
    num = tc.get(game.font, str(int(round(gauge))), num_col)
    game.game_surface.blit(num, (gx + seg_w // 2 - num.get_width() // 2, gy - 18))
