"""
Per-frame simulation steps that run *before* the play logic of Game.update():
housekeeping, title/menu/game-over idle, and the hot-seat hand-off screens.

Extracted from game.py (Game.update). Functions take the Game object as `game`
and behave exactly as before; Game.update() calls them in the same order.
"""
import pygame

from settings import BASE_HEIGHT, SCREEN_SHAKE_DECAY
from errlog import log_exc


def tick_housekeeping(game):
    """Music, fades, gamepad hot-plug, timers (runs every frame)."""
    game._tick_fade()
    game.title_timer += game.dt
    game._update_music()
    game._tick_listen_achs()
    if getattr(game, "sounds", None):
        game.sounds.pause_duck = bool(
            getattr(game, "paused", False)
            and getattr(game, "started", False)
            and not getattr(game, "game_over", False)
        )
    game.sounds.update(game.dt)
    # Hot-plug on menus and mid-run (wireless drop).
    game._gp_poll = float(getattr(game, "_gp_poll", 0.0)) + game.dt
    if game._gp_poll >= 0.45:
        game._gp_poll = 0.0
        game._poll_gamepad()
    if game._joy_menu_cooldown > 0:
        game._joy_menu_cooldown = max(0.0, game._joy_menu_cooldown - game.dt)
    if game.input_grace > 0:
        game.input_grace = max(0.0, game.input_grace - game.dt)
    # Menus need key repeat; in-game it would retrigger Shield / Phenix.
    want_repeat = not (game.started and not game.game_over)
    if want_repeat != getattr(game, "_key_repeat_on", True):
        game._key_repeat_on = want_repeat
        try:
            pygame.key.set_repeat(220, 45) if want_repeat else pygame.key.set_repeat(0)
        except Exception:
            log_exc("update_idle.tick_housekeeping")
    if game.cheat_msg_timer > 0:
        game.cheat_msg_timer = max(0.0, game.cheat_msg_timer - game.dt)
    if game._hs_joy_cooldown > 0:
        game._hs_joy_cooldown = max(0.0, game._hs_joy_cooldown - game.dt)

    # Analog stick for initials entry
    if game.game_over and game.hs_phase == "enter" and game.joystick and game._hs_joy_cooldown <= 0:
        try:
            ax = game.joystick.get_axis(0) if game.joystick.get_numaxes() > 0 else 0
            ay = game.joystick.get_axis(1) if game.joystick.get_numaxes() > 1 else 0
            if abs(ax) > 0.7:
                game.hs_char_index = (game.hs_char_index + (1 if ax > 0 else -1)) % 3
                game._hs_joy_cooldown = 0.28
            elif abs(ay) > 0.7:
                game._hs_cycle_letter(-1 if ay > 0 else 1)
                game._hs_joy_cooldown = 0.22
        except Exception:
            log_exc("update_idle.tick_housekeeping")


def tick_menu_or_gameover(game):
    """Title / menu / game-over frame (stars, logo, attract/help idle, credits...)."""
    # Still scroll stars on title/game over (no parallax)
    game._tick_stars(follow=False)
    game.sounds.play_electric(False)
    if game.logo_frames:
        game.logo_timer += game.dt
        if game.logo_timer >= 1.0 / game.logo_fps:
            game.logo_timer -= 1.0 / game.logo_fps
            game.logo_index = (game.logo_index + 1) % len(game.logo_frames)
    if not game.started and game.menu_screen == "main":
        game._update_season(game.dt)
        game._update_april_gag(game.dt)
    else:
        game._season_theme = None
    if not game.started and game.menu_screen == "jukebox":
        game._update_jukebox()
    if not game.started and game.menu_screen == "achievements":
        game._update_ach_scroll()
    if not game.started and game.menu_screen == "credits":
        axis = game._credits_scroll_axis()
        # signed px/s: negative = normal (text rises)
        if axis > 0:
            target = 140.0
        elif axis < 0:
            target = -150.0
        else:
            target = -42.0
        k = min(1.0, 8.0 * game.dt)
        game.credits_speed = getattr(game, "credits_speed", -42.0)
        game.credits_speed += (target - game.credits_speed) * k
        game.credits_scroll += game.credits_speed * game.dt
        ax = game._credits_x_axis()
        target = ax * 58.0
        # Spring + damper: resistance while held, ease back when released
        k_s, k_d = 14.0, 7.5
        game.credits_x = float(getattr(game, "credits_x", 0.0))
        game.credits_xv = float(getattr(game, "credits_xv", 0.0))
        acc = (target - game.credits_x) * k_s - game.credits_xv * k_d
        game.credits_xv += acc * game.dt
        game.credits_x += game.credits_xv * game.dt
        if abs(game.credits_x) < 0.15 and ax == 0:
            game.credits_x = 0.0
            game.credits_xv = 0.0
    if not game.started and game.menu_screen == "ship_select":
        game.ship_anim_t = getattr(game, "ship_anim_t", 0.0) + game.dt
        game._tick_preview_cycle(game.dt)
        sl = float(getattr(game, "shield_slide", 1.0))
        if sl < 1.0:
            game.shield_slide = min(1.0, sl + game.dt / 0.28)
        if getattr(game, "_pending_after_welcome", None):
            if not (hasattr(game, "sounds") and game.sounds.vo_is_busy()):
                game._flush_after_welcome()
    # Attract / help screen from main menu idle
    if not game.started and not game.quit_confirm:
        if game.menu_screen != "addon" and getattr(game, "_addon_clip", None):
            game._addon_clip_stop()
        if game.menu_screen == "main":
            if getattr(game, "april_gag", "done") not in ("idle", "wait", "left", "right", "sway", "fall", "boom"):
                game.menu_idle += game.dt
            # First idle after launch: 10s help; then alternate help / attract every 5s
            idle_need = 10.0 if not game.help_first_shown else 5.0
            if game.menu_idle >= idle_need:
                game.menu_idle = 0.0
                if not game.help_first_shown:
                    game.help_first_shown = True
                    game.menu_screen = "help"
                    game.help_timer = 0.0
                    game.help_page = 0
                    game.help_scroll = 0.0
                    game.help_transitioning = False
                    game.next_is_attract = True
                elif game.next_is_attract:
                    game.next_is_attract = False
                    game._start_attract()
                else:
                    game.next_is_attract = True
                    game.menu_screen = "help"
                    game.help_timer = 0.0
                    game.help_page = 0
                    game.help_scroll = 0.0
                    game.help_transitioning = False
        elif game.menu_screen == "addon":
            game._tick_addon_clip(game.dt)
        elif game.menu_screen == "help":
            game.help_anim_t += game.dt
            if game.help_transitioning:
                # Smooth vertical slide page 0 → page 1
                game.help_scroll += game.dt / max(0.05, game.HELP_SCROLL_SEC) * BASE_HEIGHT
                if game.help_scroll >= BASE_HEIGHT:
                    game.help_scroll = 0.0
                    game.help_transitioning = False
                    game.help_page = 1
                    game.help_timer = 0.0
            else:
                game.help_timer += game.dt
                if game.help_timer >= game.HELP_PAGE_SEC:
                    if game.help_page <= 0:
                        game.help_transitioning = True
                        game.help_scroll = 0.0
                    else:
                        game.menu_screen = "main"
                        game.menu_index = 0
                        game.menu_idle = 0.0
                        game.help_timer = 0.0
                        game.help_page = 0
        else:
            game.menu_idle = 0.0


def tick_hotseat_pick_p2(game):
    """Hot-seat: player 2 ship selection frame."""
    game._tick_stars(follow=False)
    game.ship_anim_t = getattr(game, "ship_anim_t", 0.0) + game.dt
    game._tick_preview_cycle(game.dt)
    sl = float(getattr(game, "shield_slide", 1.0))
    if sl < 1.0:
        game.shield_slide = min(1.0, sl + game.dt / 0.28)
    game.sounds.play_electric(False)
    if getattr(game, "_pending_after_welcome", None):
        if not (hasattr(game, "sounds") and game.sounds.vo_is_busy()):
            game._flush_after_welcome()


def tick_hotseat_hold(game):
    """Hot-seat hand-off pause (explosions settle, then switch)."""
    game.hotseat_hold = max(0.0, game.hotseat_hold - game.dt)
    game._tick_stars(follow=True)
    for exp in game.explosions[:]:
        exp.update(game.dt)
        if exp.is_finished():
            game.explosions.remove(exp)
    form = getattr(game, "formation", None)
    if form is not None:
        for enemy in list(getattr(form, "enemies", []) or []):
            if getattr(enemy, "dying", False) or getattr(enemy, "hit_flash_frames", 0):
                enemy.update(game.dt, getattr(form, "offset_x", 0.0), 0.0)
        game._drain_detach_pops()
    tesla_on = False
    if game.tesla_fx is not None:
        game.tesla_fx.update(game.dt)
        tesla_on = not game.tesla_fx.is_finished()
        if not tesla_on:
            game.tesla_fx = None
    game.sounds.play_electric(tesla_on, x=game._sfx_electric_x())
    if game.shake_amount > 0:
        game.shake_amount = max(0.0, game.shake_amount - SCREEN_SHAKE_DECAY * game.dt)
    if game.hotseat_hold <= 0:
        game._hotseat_finish_hold()
