"""
Menu actions: change the highlighted option (left/right) and confirm it.

Extracted from game.py (Game._menu_adjust, Game._menu_confirm). Functions take
the Game object as `game` and behave exactly as before.
"""
import addon as mame_addon
from highscores import load_highscores, reset_highscores
from i18n import LANG_CODES, set_lang
from ingame_music import cycle as ingame_cycle
from settings import BASE_HEIGHT
from errlog import log_exc
import main_menu


def menu_adjust(game, direction):
    """direction: -1 left, +1 right — change current option value"""
    if game.menu_screen == "ship_select":
        if getattr(game, "ship_select_locked", False):
            return
        game.ship_select_index = (int(getattr(game, "ship_select_index", 0)) + direction) % 2
        game.ship_cycle_phase = "idle"
        game.ship_cycle_t = 0.0
        game.ship_cycle_first = True
        game.ship_cycle_focus = game.ship_select_index
        return
    if game.menu_screen == "story_hub":
        if getattr(game, "story", None):
            game.story.nav_h(1 if direction > 0 else -1)
        return
    if game.menu_screen == "arcade":
        row = main_menu.ARCADE[game.menu_index] if 0 <= game.menu_index < len(main_menu.ARCADE) else ""
        if row == "mode":
            modes = getattr(game, "PLAY_MODES", ["solo", "hotseat", "coop"])
            cur = getattr(game, "play_mode", "solo")
            idx = modes.index(cur) if cur in modes else 0
            game.play_mode = modes[(idx + direction) % len(modes)]
        elif row == "difficulty":
            idx = game.DIFFICULTIES.index(game.difficulty)
            game.difficulty = game.DIFFICULTIES[(idx + direction) % len(game.DIFFICULTIES)]
        return
    if game.menu_screen != "options":
        return
    if game.menu_index < 0:
        game._options_tab_step(direction)        # the row of tabs has the focus: Left / Right change the tab
        return
    spec = game._options_spec()
    if game.menu_index < 0 or game.menu_index >= len(spec):
        return
    key = spec[game.menu_index]
    if key == "control":
        order = ["auto", "keyboard"] + (["gamepad"] if game.gamepad_detected else [])
        cur = getattr(game, "control_pref", "auto")
        idx = order.index(cur) if cur in order else 0
        game.control_pref = order[(idx + (1 if direction >= 0 else -1)) % len(order)]
        game._apply_control_pref()
        game.save_settings()
    elif key == "autofire":
        game.autofire = not bool(getattr(game, "autofire", True))
        game.save_settings()
    elif key == "sfx":
        game.sfx_volume = max(0.0, min(1.0, game.sfx_volume + direction * 0.1))
        game.sounds.set_master_volume(game.sfx_volume)
        game.sounds.play("shoot")
        game.save_settings()
    elif key == "music":
        game.music_volume = max(0.0, min(1.0, game.music_volume + direction * 0.1))
        game.sounds.set_music_volume(game.music_volume)
        game.save_settings()
    elif key == "audio_mix":
        modes = getattr(game, "AUDIO_MIXES", ["sfx", "sfx_music", "music", "off"])
        cur = getattr(game, "audio_mix", "sfx")
        i = modes.index(cur) if cur in modes else 0
        game.audio_mix = modes[(i + direction) % len(modes)]
        game._apply_audio_mix()
        game.save_settings()

    elif key == "ingame_music":
        game.ingame_music = ingame_cycle(getattr(game, "ingame_music", "none"), direction)
        game.save_settings()

    elif key == "rumble":
        game.rumble_level = max(0, min(5, int(getattr(game, "rumble_level", 3)) + direction))
        if game.player:
            game.player.rumble_level = game.rumble_level
            game.player._joy = game.joystick
            game.player._rumble_enabled = True
            if game.rumble_level > 0:
                game.player.rumble(0.35, 0.55, 180)
        game.save_settings()
    elif key == "display":
        modes = ["window", "fullscreen", "borderless"]
        idx = modes.index(game.display_mode) if game.display_mode in modes else 0
        game.display_mode = modes[(idx + direction) % len(modes)]
        game.apply_display_mode()
        game.save_settings()
    elif key == "bezel":
        if getattr(game, "display_mode", "fullscreen") != "fullscreen":
            return                               # the bezels only show in fullscreen: the row is greyed
        styles = [s[0] for s in getattr(game, "BEZEL_STYLES", [("off", ""), ("phoenix", "")])]
        cur = getattr(game, "bezel_style", "phoenix")
        idx = styles.index(cur) if cur in styles else 0
        game.bezel_style = styles[(idx + direction) % len(styles)]
        game.save_settings()
        game._load_bezel_images()
        game._open_display()
        game._invalidate_present_cache()
        game._layout_viewport()
        if game.bezel_active:
            game._ensure_bezel_cache()
        game._update_caption()
    elif key == "fps":
        game.show_fps = not game.show_fps
        game.save_settings()
    elif key == "scanlines":
        cur = int(getattr(game, "scanlines", 0) or 0)
        game.scanlines = (cur + direction) % 4  # 0..3
        game._scanline_surf = None  # rebuild overlay
        game._scanline_level_cached = None
        game.save_settings()
    elif key == "gpu":
        game.gpu_present = not bool(getattr(game, "gpu_present", True))
        game.save_settings()
        game._open_display()
    elif key == "vsync":
        modes = ["on", "adaptive", "off"]
        cur = getattr(game, "vsync_mode", "adaptive")
        i = modes.index(cur) if cur in modes else 1
        game.vsync_mode = modes[(i + direction) % len(modes)]
        game.save_settings()
        game._open_display()
    elif key == "hz":
        caps = [60, 75, 120, 144]
        cur = int(getattr(game, "fps_cap", 120) or 120)
        i = caps.index(cur) if cur in caps else 2
        game.fps_cap = caps[(i + direction) % len(caps)]
        game.fps_target = game.fps_cap
        game.save_settings()
        game._update_caption()
        game._invalidate_present_cache()
        game._layout_viewport()
        game._update_caption()
    elif key == "language":
        idx = LANG_CODES.index(game.language) if game.language in LANG_CODES else 0
        game.language = LANG_CODES[(idx + direction) % len(LANG_CODES)]
        set_lang(game.language)
        game.text_cache.clear()
        game._opt_help_cache = {}
        game._credits_layout_cache = None
        game.save_settings()


def menu_confirm(game):

    if game.menu_screen == "main":
        entry = main_menu.MAIN[game.menu_index] if 0 <= game.menu_index < len(main_menu.MAIN) else ""
        if entry == "play":
            game.menu_screen = "arcade"              # mode and difficulty, then the ship select
            game.menu_index = 0
        elif entry == "story":
            if not getattr(game, "story", None):
                from story import StoryHub
                game.story = StoryHub()
                game.story.sounds = getattr(game, "sounds", None)
            game.story.open_slots()
            game.menu_screen = "story_hub"
            game.menu_idle = 0.0
        elif entry == "extras":
            game.menu_screen = "extras"
            game.menu_index = int(getattr(game, "extras_index", 0) or 0) % len(main_menu.EXTRAS)
        elif entry == "options":
            game._open_options()
        elif entry == "quit":
            game._quit_app()
    elif game.menu_screen == "arcade":
        game._fade_to("open_select")                 # whichever row: Enter goes on to the ship select
    elif game.menu_screen == "extras":
        game._open_extra(main_menu.EXTRAS[game.menu_index % len(main_menu.EXTRAS)])
    elif game.menu_screen == "story_hub":
        spec = None
        if getattr(game, "story", None):
            spec = game.story.confirm()
            for name in game.story.take_sounds():
                game.sounds.play(name)
        if isinstance(spec, dict) and spec.get("launch"):
            game._begin_adventure(spec)
        elif isinstance(spec, dict) and spec.get("leave"):
            game.menu_screen = "main"                    # the Adventure is left (confirmed): back to the normal game
            game.menu_index = 1
        elif isinstance(spec, dict) and spec.get("door"):
            if spec.get("scene"):
                game._story_scene_door(spec["door"])     # a scene that ends in a screen: black fade, then the screen
            else:
                game._open_story_door(spec["door"])
    elif game.menu_screen == "addon":
        game._launch_addon()
    elif game.menu_screen == "jukebox":
        game._juke_play_or_pause()
    elif game.menu_screen == "ship_select":
        if getattr(game, "ship_select_locked", False) or getattr(game, "_pending_after_welcome", None):
            return
        ids = ("phoenix", "shield")
        chosen = ids[int(getattr(game, "ship_select_index", 0)) % 2]
        slot = int(getattr(game, "ship_select_slot", 1) or 1)
        if slot == 2:
            av = game._available_tints(chosen, 2)
            if av and game._tint_of(chosen, 2) not in av:
                game._set_tint(chosen, 2, av[0])
        two_p = getattr(game, "play_mode", "solo") in ("hotseat", "coop")
        if slot == 2:
            game.ship_id_p2 = chosen
        else:
            game.ship_id = chosen
        try:
            game.save_settings()
        except Exception:
            log_exc("menu_actions.menu_confirm")
        if two_p and slot == 1 and getattr(game, "play_mode", "solo") == "coop":
            try:
                game._play_ship_welcome()
            except Exception:
                log_exc("menu_actions.menu_confirm")
            game._fade_to("open_select_p2")
        else:
            game._queue_after_welcome(
                "hotseat_p2" if getattr(game, "hotseat_pick_p2", False) else "begin"
            )
    elif game.menu_screen == "reset_confirm":
        if game.menu_index == 0:  # Oui
            game.hs_entries = reset_highscores()
        game.menu_screen = "options"
        game._focus_option("reset_hs")
    elif game.menu_screen == "options":
        spec = game._options_spec()
        key = spec[game.menu_index] if 0 <= game.menu_index < len(spec) else ""
        if key == "reset_hs":
            game.menu_screen = "reset_confirm"
            game.menu_index = 1
