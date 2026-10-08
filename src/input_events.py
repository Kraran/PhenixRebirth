"""
Input handling of Game.handle_events(): one function per event type.

Extracted from game.py (Game.handle_events). Functions take the Game object as
`game` and the pygame event, and behave exactly as before. In the original
loop `continue` meant "done with this event": here it is `return`.
"""
import pygame

from highscores import reset_highscores
from achievements import load_achievements


def on_keydown(game, event):
    """Keyboard press: attract exit, Phenix/Shield, pause, menus, quit confirm, high-score entry."""
    if event.key == pygame.K_F12:
        game.take_screenshot()
        return
    if game.attract_mode:
        game._end_attract()
        return
    if getattr(game, "hotseat_pick_p2", False) and game.menu_screen == "ship_select":
        if game._is_menu_confirm(event.key) or event.key in (
            pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
        ):
            game._menu_confirm()
        elif game._is_menu_up(event.key):
            game._menu_nav(-1)
        elif game._is_menu_down(event.key):
            game._menu_nav(1)
        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
            game._menu_adjust(-1)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            game._menu_adjust(1)
        return
    if game.hotseat_wait and game.started and not game.game_over:
        if getattr(game, "input_grace", 0) <= 0:
            game._hotseat_resume()
        return
    # Phenix / Shield — edge only (set_repeat must not retrigger)
    if game.started and not game.paused and not game.game_over:
        held = getattr(game, "_special_keys", None)
        if held is None:
            held = game._special_keys = set()
        shift_repeat = event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT) and event.key in held
        if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT) and not shift_repeat:
            held.add(event.key)
        if shift_repeat:
            pass
        elif event.key == pygame.K_LSHIFT:
            # Coop split-keyboard P1 only
            if game.play_mode == "coop" and getattr(game.player, "input_scheme", "") == "kb1":
                game._activate_phenix_from_input(game.player)
        elif event.key == pygame.K_RSHIFT:
            if game.play_mode == "coop":
                # P2 keyboard (or 1P-style layout)
                target = game.player2
                if getattr(game.player, "input_scheme", "") == "solo":
                    target = game.player2
                game._activate_phenix_from_input(target)
            else:
                game._activate_phenix_from_input(game.player)
    if event.key == pygame.K_ESCAPE:
        if game.started and not game.game_over:
            if game.pause_options:
                if game.menu_screen == "reset_confirm":
                    game.menu_screen = "options"
                    game._focus_option("reset_hs")
                else:
                    game.pause_options = False
                    game.menu_index = 0
            elif game.paused:
                game.paused = False
                game.pause_options = False
            else:
                game._toggle_pause()
            return
        elif not game.started:
            if game.menu_screen == "help":
                game._reset_menu_idle()
            elif game.quit_confirm:
                game.quit_confirm = False
            elif game.menu_screen in ("options", "credits", "reset_confirm", "ship_select", "jukebox", "story_hub", "addon"):
                game._menu_back()
            else:
                game.quit_confirm = True
                game.quit_index = 1
            return
    # Pause menu (in-game)
    if game.paused and game.started and not game.game_over:
        if game.pause_options:
            if game._is_menu_up(event.key):
                game._menu_nav(-1)
            elif game._is_menu_down(event.key):
                game._menu_nav(1)
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                game._menu_adjust(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                game._menu_adjust(1)
            elif game._is_menu_confirm(event.key):
                if game.menu_screen == "reset_confirm":
                    if game.menu_index == 0:
                        game.hs_entries = reset_highscores()
                    game.menu_screen = "options"
                    game._focus_option("reset_hs")
                else:
                    spec = game._options_spec()
                    key = spec[game.menu_index] if 0 <= game.menu_index < len(spec) else ""
                    if key == "back":
                        game.pause_options = False
                        game.menu_index = 0
                    elif key == "reset_hs":
                        game.menu_screen = "reset_confirm"
                        game.menu_index = 1
            elif event.key == pygame.K_ESCAPE:
                if game.menu_screen == "reset_confirm":
                    game.menu_screen = "options"
                    game._focus_option("reset_hs")
                else:
                    game.pause_options = False
                    game.menu_index = 0
        else:
            if game._is_menu_up(event.key):
                game.pause_index = (game.pause_index - 1) % 3
            elif game._is_menu_down(event.key):
                game.pause_index = (game.pause_index + 1) % 3
            elif game._is_menu_confirm(event.key):
                if game.pause_index == 0:  # Reprendre
                    game.paused = False
                elif game.pause_index == 1:  # Options
                    game.pause_options = True
                    game.menu_screen = "options"
                    game.menu_index = 0
                else:  # Quitter la partie
                    game._quit_to_menu()
                    return  # don't also confirm main-menu with same Enter
            elif event.key == pygame.K_ESCAPE:
                game.paused = False
                game.pause_options = False
                return
    # Quit game confirm (menus) — ESC already toggled above
    elif game.quit_confirm and not game.started:
        if game._is_menu_up(event.key):
            game.quit_index = (game.quit_index - 1) % 2
        elif game._is_menu_down(event.key):
            game.quit_index = (game.quit_index + 1) % 2
        elif game._is_menu_confirm(event.key):
            if game.quit_index == 0:
                game._quit_app()
            else:
                game.quit_confirm = False
                game.input_grace = 0.30
            return


    if not game.started and not game.game_over and not game.quit_confirm:
        arrow = game._is_menu_up(event.key) or game._is_menu_down(event.key) or event.key in (
            pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_q, pygame.K_d,
        )
        if not arrow and getattr(game, "input_grace", 0) > 0:
            return
        story = getattr(game, "story", None)
        if game.menu_screen == "story_hub" and story is not None:
            # Adventure name entry: typed letters must not act as menu keys (W A S D Z Q ...)
            if story.type_key(event):
                game._reset_menu_idle()
                return
            if event.key == pygame.K_DELETE:
                story.key_delete()
                return
        if game.menu_screen == "help":
            game._reset_menu_idle()
        elif game.menu_screen == "credits":
            # Arrows / WASD / ZQSD drive the scroll — do not leave.
            if event.key in (
                pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT,
                pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_z, pygame.K_q,
                pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_CAPSLOCK,
            ):
                pass
            elif event.key in (
                pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
                pygame.K_ESCAPE, pygame.K_BACKSPACE,
            ) or game._is_menu_confirm(event.key):
                game.menu_screen = "main"
                game.menu_index = 6
        elif game.menu_screen == "achievements":
            if event.key in (
                pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s, pygame.K_z,
            ) or game._is_menu_up(event.key) or game._is_menu_down(event.key):
                pass
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                game._extra_step(1)
            elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
                game._extra_step(-1)
            elif event.key in (
                pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
                pygame.K_ESCAPE, pygame.K_BACKSPACE,
            ):
                game.ach_data = load_achievements()
                game.menu_screen = "highscores"
        elif game.menu_screen == "jukebox":
            if getattr(game, "juke_video", False):
                if event.key in (
                    pygame.K_ESCAPE, pygame.K_BACKSPACE,
                    pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
                ) or game._is_menu_confirm(event.key):
                    game._juke_play_or_pause()
            elif game._is_menu_up(event.key):
                game._menu_nav(-1)
            elif game._is_menu_down(event.key):
                game._menu_nav(1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                game._extra_step(1)
            elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
                game._extra_step(-1)
            elif game._is_menu_confirm(event.key):
                game._juke_play_or_pause()
        elif game.menu_screen == "highscores":
            # Invisible cheats on this screen. Empty unicode (numlock,
            # dead keys) must NOT kick back to the title.
            ch = (event.unicode or "")
            if event.key in (pygame.K_RIGHT, pygame.K_d):
                game._extra_step(1)
            elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
                game._extra_step(-1)
            elif ch.isalnum():
                game._feed_cheat(ch)
            elif event.key in (
                pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
                pygame.K_ESCAPE, pygame.K_BACKSPACE,
            ):
                game.menu_screen = "main"
                game.menu_index = 4
                game.cheat_buffer = ""
        elif game._is_menu_up(event.key):
            game._reset_menu_idle()
            game._menu_nav(-1)
        elif game._is_menu_down(event.key):
            game._reset_menu_idle()
            game._menu_nav(1)
        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
            game._reset_menu_idle()
            game._menu_adjust(-1)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            game._reset_menu_idle()
            game._menu_adjust(1)
        elif game._is_menu_confirm(event.key):
            game._reset_menu_idle()
            game._menu_confirm()

    if game.game_over:
        if game.hs_phase == "card":
            if game._is_menu_confirm(event.key):
                game._skip_gameover_card()
            return
        if game.hs_phase == "enter":
            if event.key == pygame.K_LEFT:
                game.hs_char_index = (game.hs_char_index - 1) % 3
            elif event.key == pygame.K_RIGHT:
                game.hs_char_index = (game.hs_char_index + 1) % 3
            elif game._is_menu_up(event.key):
                game._hs_cycle_letter(1)
            elif game._is_menu_down(event.key):
                game._hs_cycle_letter(-1)
            elif event.key == pygame.K_BACKSPACE:
                game.hs_char_index = max(0, game.hs_char_index - 1)
            elif game._is_menu_confirm(event.key):
                game._submit_highscore()
                game.input_grace = 0.40
                return
            elif event.unicode and event.unicode.isalnum():
                game.hs_name[game.hs_char_index] = event.unicode.upper()
                game.hs_char_index = min(2, game.hs_char_index + 1)
        elif game.hs_phase == "table" and game._is_menu_confirm(event.key):
            game._return_from_gameover()
            return


def on_keyup(game, event):
    """Keyboard release: forget the held Shift keys."""
    held = getattr(game, "_special_keys", None)
    if held and event.key in held:
        held.discard(event.key)


def on_joy_button(game, event):
    """Gamepad button: attract exit, Phenix, pause, menus, high-score entry."""
    if game.attract_mode:
        game._end_attract()
        return
    if getattr(game, "hotseat_pick_p2", False) and game.menu_screen == "ship_select":
        if event.button == 0:
            game._menu_confirm()
        return
    if game.hotseat_wait and game.started and not game.game_over:
        if getattr(game, "input_grace", 0) <= 0:
            game._hotseat_resume()
        return
    # B = Phenix while playing (menus still use B as back elsewhere)
    if (event.button == 1 and game.started and not game.paused
            and not game.game_over and not game.quit_confirm):
        target = game.player
        if game.play_mode == "coop":
            inst = getattr(event, "instance_id", getattr(event, "joy", None))
            for s in game._ships():
                joy = getattr(s, "_joy", None)
                if joy is None:
                    continue
                jid = getattr(joy, "get_instance_id", lambda: joy.get_id())()
                if jid == inst or joy.get_id() == getattr(event, "joy", -1):
                    target = s
                    break
        game._activate_phenix_from_input(target)
    # Start button (7 Xbox / 9 some pads) — pause or quit confirm
    if event.button in (7, 9, 6):
        if game.started and not game.game_over:
            game._toggle_pause()
        elif not game.started:
            if game.menu_screen == "help":
                game._reset_menu_idle()
            elif game.quit_confirm:
                game.quit_confirm = False
            elif game.menu_screen in ("options", "credits", "reset_confirm", "ship_select", "jukebox", "story_hub", "addon"):
                game._menu_back()
            else:
                game.quit_confirm = True
                game.quit_index = 1
    elif game.paused and game.started and not game.game_over:
        if game.pause_options:
            if event.button == 0:
                if game.menu_screen == "reset_confirm":
                    if game.menu_index == 0:
                        game.hs_entries = reset_highscores()
                    game.menu_screen = "options"
                    game._focus_option("reset_hs")
                else:
                    spec = game._options_spec()
                    key = spec[game.menu_index] if 0 <= game.menu_index < len(spec) else ""
                    if key == "back":
                        game.pause_options = False
                        game.menu_index = 0
                    elif key == "reset_hs":
                        game.menu_screen = "reset_confirm"
                        game.menu_index = 1
            elif event.button == 1:
                if game.menu_screen == "reset_confirm":
                    game.menu_screen = "options"
                    game._focus_option("reset_hs")
                else:
                    game.pause_options = False
                    game.menu_index = 0
        else:
            if event.button == 0:
                if game.pause_index == 0:
                    game.paused = False
                elif game.pause_index == 1:
                    game.pause_options = True
                    game.menu_screen = "options"
                    game.menu_index = 0
                else:
                    game._quit_to_menu()
                    return  # same A must not confirm main menu
            elif event.button == 1:
                game.paused = False
                game.pause_options = False
                return
    elif game.quit_confirm and not game.started:
        if event.button == 0:
            if game.quit_index == 0:
                game._quit_app()
            else:
                game.quit_confirm = False
                game.input_grace = 0.30
            return
        elif event.button == 1:
            game.quit_confirm = False
            game.input_grace = 0.30
            return
    elif not game.started and not game.game_over and not game.quit_confirm and getattr(game, "input_grace", 0) <= 0:
        if game.menu_screen == "help":
            game._reset_menu_idle()
        elif event.button == 0:  # A — confirm / enter
            game._reset_menu_idle()
            if game.menu_screen in ("highscores", "credits", "achievements"):
                game._menu_back()
            else:
                game._menu_confirm()
        elif event.button == 1:  # B — back
            game._reset_menu_idle()
            game._menu_back()
    elif game.game_over and game.hs_phase == "enter":
        if event.button in (0, 1):
            game._submit_highscore()
            game.input_grace = 0.40
            return
    elif game.game_over and game.hs_phase == "card":
        game._skip_gameover_card()
    elif game.game_over and game.hs_phase == "table":
        if event.button in (0, 1):
            game._return_from_gameover()
            return


def on_joy_hat(game, event):
    """Gamepad D-pad (hat) in menus, pause, hot-seat pick and high-score entry."""
    hx, hy = event.value
    if hx == 0 and hy == 0:
        game._hat_latch = (0, 0)
    elif getattr(game, "_hat_latch", (0, 0)) != (hx, hy):
        game._hat_latch = (hx, hy)
        if getattr(game, "hotseat_pick_p2", False) and game.menu_screen == "ship_select":
            if hx != 0:
                game._menu_adjust(1 if hx > 0 else -1)
            if hy > 0:
                game._menu_nav(-1)
            elif hy < 0:
                game._menu_nav(1)
        elif game.paused and game.started and not game.game_over and not game.pause_options:
            if hy > 0:
                game.pause_index = (game.pause_index - 1) % 3
            elif hy < 0:
                game.pause_index = (game.pause_index + 1) % 3
        elif not game.started and not game.game_over:
            if game.menu_screen == "help":
                game._reset_menu_idle()
            elif game.menu_screen == "credits":
                pass
            elif game.menu_screen == "jukebox":
                if getattr(game, "juke_video", False):
                    pass
                else:
                    if hy > 0:
                        game._menu_nav(-1)
                    elif hy < 0:
                        game._menu_nav(1)
                if hx > 0:
                    game._extra_step(1)
                elif hx < 0:
                    game._extra_step(-1)
            elif game.menu_screen in ("highscores", "achievements"):
                if hx > 0:
                    game._extra_step(1)
                elif hx < 0:
                    game._extra_step(-1)
            else:
                game._reset_menu_idle()
                if hy > 0:
                    game._menu_nav(-1)
                elif hy < 0:
                    game._menu_nav(1)
                if hx != 0:
                    game._menu_adjust(1 if hx > 0 else -1)
    elif game.game_over and game.hs_phase == "enter":
        if hx < 0:
            game.hs_char_index = (game.hs_char_index - 1) % 3
        elif hx > 0:
            game.hs_char_index = (game.hs_char_index + 1) % 3
        if hy > 0:
            game._hs_cycle_letter(1)
        elif hy < 0:
            game._hs_cycle_letter(-1)


def on_joy_axis(game, event):
    """Gamepad stick in menus, pause, quit confirm, hot-seat pick."""
    DEAD = 0.72
    if getattr(game, "hotseat_pick_p2", False) and game.menu_screen == "ship_select":
        if event.axis == 0:
            if abs(event.value) < 0.40:
                game._joy_axis_latch_x = 0
            elif game._joy_menu_cooldown <= 0:
                if event.value < -DEAD and game._joy_axis_latch_x != -1:
                    game._menu_adjust(-1)
                    game._joy_axis_latch_x = -1
                    game._joy_menu_cooldown = 0.28
                elif event.value > DEAD and game._joy_axis_latch_x != 1:
                    game._menu_adjust(1)
                    game._joy_axis_latch_x = 1
                    game._joy_menu_cooldown = 0.28
        elif event.axis == 1:
            if abs(event.value) < 0.40:
                game._joy_axis_latch_y = 0
            elif game._joy_menu_cooldown <= 0:
                if event.value < -DEAD and game._joy_axis_latch_y != -1:
                    game._menu_nav(-1)
                    game._joy_axis_latch_y = -1
                    game._joy_menu_cooldown = 0.28
                elif event.value > DEAD and game._joy_axis_latch_y != 1:
                    game._menu_nav(1)
                    game._joy_axis_latch_y = 1
                    game._joy_menu_cooldown = 0.28
    elif game.paused and game.started and not game.game_over:
        if game.pause_options:
            if event.axis == 1:
                if abs(event.value) < 0.40:
                    game._joy_axis_latch_y = 0
                elif game._joy_menu_cooldown <= 0:
                    if event.value < -DEAD and game._joy_axis_latch_y != -1:
                        game._menu_nav(-1)
                        game._joy_axis_latch_y = -1
                        game._joy_menu_cooldown = 0.28
                    elif event.value > DEAD and game._joy_axis_latch_y != 1:
                        game._menu_nav(1)
                        game._joy_axis_latch_y = 1
                        game._joy_menu_cooldown = 0.28
            elif event.axis == 0:
                if abs(event.value) < 0.40:
                    game._joy_axis_latch_x = 0
                elif game._joy_menu_cooldown <= 0:
                    if event.value < -DEAD and game._joy_axis_latch_x != -1:
                        game._menu_adjust(-1)
                        game._joy_axis_latch_x = -1
                        game._joy_menu_cooldown = 0.28
                    elif event.value > DEAD and game._joy_axis_latch_x != 1:
                        game._menu_adjust(1)
                        game._joy_axis_latch_x = 1
                        game._joy_menu_cooldown = 0.28
        elif event.axis == 1:
            if abs(event.value) < 0.40:
                game._joy_axis_latch_y = 0
            elif game._joy_menu_cooldown <= 0:
                if event.value < -DEAD and game._joy_axis_latch_y != -1:
                    game.pause_index = (game.pause_index - 1) % 3
                    game._joy_axis_latch_y = -1
                    game._joy_menu_cooldown = 0.28
                elif event.value > DEAD and game._joy_axis_latch_y != 1:
                    game.pause_index = (game.pause_index + 1) % 3
                    game._joy_axis_latch_y = 1
                    game._joy_menu_cooldown = 0.28
    elif game.quit_confirm and not game.started:
        if event.axis == 1:
            if abs(event.value) < 0.40:
                game._joy_axis_latch_y = 0
            elif game._joy_menu_cooldown <= 0:
                if event.value < -DEAD and game._joy_axis_latch_y != -1:
                    game.quit_index = (game.quit_index - 1) % 2
                    game._joy_axis_latch_y = -1
                    game._joy_menu_cooldown = 0.28
                elif event.value > DEAD and game._joy_axis_latch_y != 1:
                    game.quit_index = (game.quit_index + 1) % 2
                    game._joy_axis_latch_y = 1
                    game._joy_menu_cooldown = 0.28
    elif not game.started and not game.game_over:
        if game.menu_screen == "achievements" and event.axis == 1:
            pass
        elif game.menu_screen == "jukebox" and event.axis == 1:
            if getattr(game, "juke_video", False):
                pass
            elif abs(event.value) < 0.40:
                game._joy_axis_latch_y = 0
            elif game._joy_menu_cooldown <= 0:
                if event.value < -DEAD and game._joy_axis_latch_y != -1:
                    game._menu_nav(-1)
                    game._joy_axis_latch_y = -1
                    game._joy_menu_cooldown = 0.22
                elif event.value > DEAD and game._joy_axis_latch_y != 1:
                    game._menu_nav(1)
                    game._joy_axis_latch_y = 1
                    game._joy_menu_cooldown = 0.22
        elif game.menu_screen in ("highscores", "achievements", "jukebox") and event.axis == 0:
            if abs(event.value) < 0.40:
                game._joy_axis_latch_x = 0
            elif game._joy_menu_cooldown <= 0:
                if event.value > DEAD and game._joy_axis_latch_x != 1:
                    game._joy_axis_latch_x = 1
                    game._joy_menu_cooldown = 0.28
                    game._extra_step(1)
                elif event.value < -DEAD and game._joy_axis_latch_x != -1:
                    game._joy_axis_latch_x = -1
                    game._joy_menu_cooldown = 0.28
                    game._extra_step(-1)
        elif game.menu_screen == "credits":
            pass  # analog stick steers the roll in update()
        elif game.menu_screen == "help":
            if abs(event.value) > 0.55:
                game._reset_menu_idle()
        elif event.axis == 1:
            if abs(event.value) < 0.40:
                game._joy_axis_latch_y = 0
            elif game._joy_menu_cooldown <= 0:
                if event.value < -DEAD and game._joy_axis_latch_y != -1:
                    game._reset_menu_idle()
                    game._menu_nav(-1)
                    game._joy_axis_latch_y = -1
                    game._joy_menu_cooldown = 0.28
                elif event.value > DEAD and game._joy_axis_latch_y != 1:
                    game._reset_menu_idle()
                    game._menu_nav(1)
                    game._joy_axis_latch_y = 1
                    game._joy_menu_cooldown = 0.28
        elif event.axis == 0:
            if abs(event.value) < 0.40:
                game._joy_axis_latch_x = 0
            elif game._joy_menu_cooldown <= 0:
                if event.value < -DEAD and game._joy_axis_latch_x != -1:
                    game._reset_menu_idle()
                    game._menu_adjust(-1)
                    game._joy_axis_latch_x = -1
                    game._joy_menu_cooldown = 0.28
                elif event.value > DEAD and game._joy_axis_latch_x != 1:
                    game._reset_menu_idle()
                    game._menu_adjust(1)
                    game._joy_axis_latch_x = 1
                    game._joy_menu_cooldown = 0.28
