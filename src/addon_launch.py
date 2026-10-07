"""
Launching the MAME addon.

Extracted from game.py (Game._launch_addon). The function takes the Game object as
`game` and behaves exactly as before.
"""
import pygame

import addon as mame_addon
from desktop_cover import hide_cover, show_cover
from errlog import log_exc


def launch_addon(game):
    """Run local MAME on the focused ROM, hide the console, wait, come back."""
    if getattr(game, "input_grace", 0) > 0:
        return
    sets = mame_addon.available_sets(fresh=True)
    idx = int(getattr(game, "menu_index", 0) or 0)
    if not sets or idx < 0 or idx >= len(sets):
        return
    sid, _label = sets[idx]
    mon_i, mon_w, mon_h = 0, 0, 0
    try:
        mon = game._pick_monitor()
        mon_i, mon_w, mon_h = int(mon[0]), int(mon[1]), int(mon[2])
    except Exception:
        mon_i = int(getattr(game, "monitor_index", 0) or 0)
    try:
        pygame.mixer.music.stop()
        pygame.mixer.stop()
    except Exception:
        log_exc("addon_launch.launch_addon")
    try:
        game.sounds._current_music = None
        game.sounds._fading_out = False
        game.sounds._pending_music = None
    except Exception:
        log_exc("addon_launch.launch_addon")
    try:
        game._release_joystick_for_mame()
    except Exception:
        log_exc("addon_launch.launch_addon")
    try:
        show_cover()
    except Exception:
        log_exc("addon_launch.launch_addon")
    proc = None
    try:
        proc = mame_addon.launch(sid, wait=False, monitor_index=mon_i, width=mon_w, height=mon_h)
    except Exception:
        proc = None
    try:
        pygame.time.wait(700)
    except Exception:
        log_exc("addon_launch.launch_addon")
    try:
        hide_cover()
    except Exception:
        log_exc("addon_launch.launch_addon")
    if proc is not None:
        try:
            game._wait_mame_quit(proc, sid)
        except Exception:
            try:
                proc.wait()
            except Exception:
                log_exc("addon_launch.launch_addon")
        try:
            getattr(proc, "_phenix_log", None) and proc._phenix_log.close()
        except Exception:
            log_exc("addon_launch.launch_addon")
    try:
        show_cover()
    except Exception:
        log_exc("addon_launch.launch_addon")
    try:
        game._wait_mame_pad_idle()
    except Exception:
        log_exc("addon_launch.launch_addon")
    pygame.event.clear()
    try:
        mame_addon.focus_pygame_window()
    except Exception:
        log_exc("addon_launch.launch_addon")
    try:
        pygame.display.flip()
    except Exception:
        log_exc("addon_launch.launch_addon")
    try:
        pygame.time.wait(180)
    except Exception:
        log_exc("addon_launch.launch_addon")
    try:
        hide_cover()
    except Exception:
        log_exc("addon_launch.launch_addon")
    try:
        if getattr(game, "menu_screen", "") == "addon":
            game.sounds.play_music("nostalgie_elise")
        else:
            game.sounds.play_music("menu")
    except Exception:
        log_exc("addon_launch.launch_addon")
    try:
        game._rebind_joystick()
    except Exception:
        log_exc("addon_launch.launch_addon")
    game.input_grace = 0.4
