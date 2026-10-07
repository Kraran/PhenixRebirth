"""
April 1st gag logic.

Extracted from game.py (Game._update_april_gag). The function takes the Game object as
`game` and behaves exactly as before.
"""
import math

from explosion import Explosion
from settings import BASE_HEIGHT, BASE_WIDTH
from errlog import log_exc


def update_april_gag(game, dt):
    """Boot-only title logo gag. Runs once."""
    st = getattr(game, "april_gag", None)
    if st in (None, "skip", "done"):
        return
    if st == "idle":
        if game.menu_screen != "main" or not game._april_fool_ok():
            game.april_gag = "skip"
            return
        game.april_gag = "wait"
        game.april_t = 0.0
        game.april_ox = game.april_oy = game.april_rot = 0.0
    game.april_t = float(getattr(game, "april_t", 0.0)) + dt
    t = game.april_t
    if st == "wait":
        game.april_ox = game.april_oy = game.april_rot = 0.0
        if t >= 0.45:
            game.april_gag = "left"
            game.april_t = 0.0
    elif st == "left":
        k = min(1.0, t / 0.90)
        e = k * k * (3 - 2 * k)
        game.april_ox = -95.0 * e
        game.april_oy = 6.0 * e
        game.april_rot = 16.0 * e
        if t >= 0.90:
            game.april_gag = "right"
            game.april_t = 0.0
    elif st == "right":
        k = min(1.0, t / 0.95)
        e = k * k * (3 - 2 * k)
        game.april_ox = -95.0 + 205.0 * e
        game.april_oy = 6.0 + 10.0 * e
        game.april_rot = 16.0 - 40.0 * e
        if t >= 0.95:
            game.april_gag = "sway"
            game.april_t = 0.0
    elif st == "sway":
        # Slow hang before the drop
        w = t * 3.2
        damp = max(0.35, 1.0 - t / 1.35)
        game.april_ox = 110.0 + math.sin(w) * 22.0 * damp
        game.april_oy = 16.0 + abs(math.sin(w)) * 4.0 * damp
        game.april_rot = -24.0 + math.sin(w) * 11.0 * damp
        if t >= 1.25:
            game.april_gag = "fall"
            game.april_t = 0.0
    elif st == "fall":
        k = min(1.0, t / 0.55)
        e = k * k
        game.april_ox = 110.0 + 20.0 * k
        game.april_oy = 16.0 + (BASE_HEIGHT - 100) * e
        game.april_rot = -24.0 + 70.0 * e
        if t >= 0.55:
            game.april_gag = "boom"
            game.april_t = 0.0
            lx = BASE_WIDTH // 2 + game.april_ox
            ly = 8 + game.april_oy + 40
            try:
                game.explosions.append(game._boom(lx, ly, kind="collision"))
            except Exception:
                game.explosions.append(Explosion(lx, ly, kind="collision"))
            try:
                game.sounds.play("explosion", x=lx)
            except Exception:
                try:
                    game.sounds.play("explosion")
                except Exception:
                    log_exc("april_gag.update_april_gag")
    elif st == "boom":
        game.april_ox = 9999
        alive = False
        for exp in game.explosions[:]:
            exp.update(dt)
            if getattr(exp, "life", 0) > 0:
                alive = True
            else:
                game.explosions.remove(exp)
        if (not alive and t >= 0.35) or t >= 1.4:
            game.explosions.clear()
            game.april_gag = "done"
            game.april_ox = game.april_oy = game.april_rot = 0.0
        return
    for exp in game.explosions[:]:
        exp.update(dt)
        if getattr(exp, "life", 1) <= 0:
            game.explosions.remove(exp)
