"""
Autopilot of the demo (attract) mode.

Extracted from game.py (Game._attract_ai). The function takes the Game object as
`game` and behaves exactly as before.
"""
import random

from settings import BASE_WIDTH


def attract_ai(game):
    """Reactive pilot with smoothed steering (avoids left/right jitter)."""
    px, py = game.player.x, game.player.y
    shoot = False

    danger_l = 0.0
    danger_r = 0.0

    def add_threat(bx, by, weight=1.0):
        nonlocal danger_l, danger_r
        if by < py - 520 or by > py + 30:
            return
        dx = bx - px
        if abs(dx) > 140:
            return
        dist_y = max(40.0, abs(by - py))
        w = weight * (220.0 / dist_y)
        if dx < -12:
            danger_l += w
        elif dx > 12:
            danger_r += w
        else:
            # Head-on: pick side with more room
            if px < BASE_WIDTH * 0.5:
                danger_l += w * 0.8
            else:
                danger_r += w * 0.8

    for b in getattr(game.formation, "bullets", []) or []:
        if isinstance(b, (list, tuple)):
            add_threat(b[0], b[1], 1.3)
        elif getattr(b, "alive", True):
            add_threat(getattr(b, "x", 0), getattr(b, "y", 0), 1.3)

    if game.boss_saucer is not None:
        for b in getattr(game.boss_saucer, "bullets", []) or []:
            if isinstance(b, (list, tuple)):
                add_threat(b[0], b[1], 1.5)
            elif getattr(b, "alive", True):
                add_threat(getattr(b, "x", 0), getattr(b, "y", 0), 1.5)

    # Desired aim X — prefer targets nearly above the ship (easier kills)
    aim_x = None
    best = 1e9
    for e in getattr(game.formation, "enemies", []) or []:
        if not getattr(e, "alive", True) or getattr(e, "dying", False):
            continue
        ex = getattr(e, "x", 0)
        ey = getattr(e, "y", 0)
        if ey > py - 40:
            if ex < px:
                danger_l += 2.0
            else:
                danger_r += 2.0
        # Weight: strongly favor enemies in a vertical corridor above us
        d = abs(ex - px) * 1.6 + max(0.0, py - ey) * 0.15
        if ey >= py - 20:
            d += 200  # behind / below — ignore for aim
        if d < best:
            best = d
            aim_x = ex

    if game.boss_saucer is not None and not getattr(game.boss_saucer, "dead", False):
        core = getattr(game.boss_saucer, "core", None)
        if core is not None and getattr(core, "alive", True):
            aim_x = getattr(core, "x", game.boss_saucer.x)
        else:
            cells = [c for c in (getattr(game.boss_saucer, "cells", []) or []) if getattr(c, "alive", True)]
            if cells:
                cells.sort(key=lambda c: abs(c.x - px))
                aim_x = cells[0].x

    # Desired continuous steering in [-1, 1]
    desired = 0.0
    threat = danger_r - danger_l  # positive → dodge left
    if abs(threat) > 0.35:
        desired = -1.0 if threat > 0 else 1.0
    elif aim_x is not None:
        err = aim_x - px
        # Proportional aim, deadzone to stop micro-jitter
        if abs(err) > 12:
            desired = max(-1.0, min(1.0, err / 70.0))
        else:
            desired = 0.0

    # Edge soft push
    if px < 100:
        desired = max(desired, (100 - px) / 80.0)
    elif px > BASE_WIDTH - 100:
        desired = min(desired, -(px - (BASE_WIDTH - 100)) / 80.0)

    # Low-pass filter on steering (frame-rate independent-ish)
    # Higher alpha = more responsive; lower = smoother
    alpha = min(1.0, 6.0 * game.dt)
    game.ai_move_smooth += (desired - game.ai_move_smooth) * alpha

    # Hold direction at least ~0.12s when committed (hysteresis)
    game.ai_dir_timer = max(0.0, game.ai_dir_timer - game.dt)
    raw = game.ai_move_smooth
    if abs(raw) < 0.22:
        discrete = 0
    elif raw > 0:
        discrete = 1
    else:
        discrete = -1

    if discrete != 0 and discrete != game.ai_dir_locked:
        if game.ai_dir_timer <= 0:
            game.ai_dir_locked = discrete
            game.ai_dir_timer = 0.14
        else:
            discrete = game.ai_dir_locked
    elif discrete == 0 and abs(raw) < 0.12:
        game.ai_dir_locked = 0

    move = game.ai_dir_locked if game.ai_dir_timer > 0 and game.ai_dir_locked != 0 else discrete

    # Aggressive fire: shoot whenever a target is roughly in our column
    shots_ready = len(getattr(game.player, "shots", []) or []) == 0
    if shots_ready:
        # 1) Primary aim target in wide lane
        if aim_x is not None and abs(aim_x - px) < 70:
            shoot = True
        else:
            # 2) Any living enemy roughly above us
            for e in getattr(game.formation, "enemies", []) or []:
                if not getattr(e, "alive", True) or getattr(e, "dying", False):
                    continue
                if abs(getattr(e, "x", 0) - px) < 55 and getattr(e, "y", 0) < py - 30:
                    shoot = True
                    break
        # 3) Boss cells / core
        if not shoot and game.boss_saucer is not None and not getattr(game.boss_saucer, "dead", False):
            if aim_x is not None and abs(aim_x - px) < 80:
                shoot = True
        # 4) Still fire occasionally while hunting (keeps pressure)
        if not shoot and aim_x is not None and random.random() < 0.08:
            shoot = True

    # Special: Phenix when charged, Shield when a volley is incoming
    if (not game.player.is_phenix) and game.player.can_activate_phenix():
        threat_sum = danger_l + danger_r
        want = False
        if getattr(game.player, "uses_shield", False):
            close_dive = False
            for e in getattr(game.formation, "enemies", []) or []:
                if not getattr(e, "alive", True):
                    continue
                if abs(getattr(e, "x", 0) - px) < 55 and 0 < (py - getattr(e, "y", 0)) < 160:
                    close_dive = True
                    break
            if threat_sum > 1.1 or close_dive:
                want = True
            elif threat_sum > 0.35 and random.random() < 0.12:
                want = True
        else:
            if threat_sum > 0.8:
                want = True
            elif game.stage % 5 == 0 and game.player.phenix_gauge >= 3:
                want = random.random() < 0.06
            elif aim_x is not None and abs(aim_x - px) < 70:
                want = random.random() < 0.03
        if want:
            game.player.try_activate_phenix()

    return move, shoot
