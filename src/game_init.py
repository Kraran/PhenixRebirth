"""
Game construction, in phases: display, run state, fonts/logo, effects, input/menu,
user settings, audio and final layout.

Extracted from game.py (Game.__init__). Functions take the Game object as `game`
and run in the same order as before; `soft` is True on a soft restart (the
window, sounds and several settings are kept).
"""
import os

import pygame

from enemy import EnemyFormation
from gpu_present import GpuPresenter
from i18n import LANG_CODES, set_lang
from ingame_music import normalize as ingame_normalize
from highscores import load_highscores
from achievements import load_achievements
from player import Player
from settings import BASE_HEIGHT, BASE_WIDTH, asset_path
from sounds import SoundManager
from starfield import Starfield
from story import StoryHub
from text_cache import TextCache
from user_settings import load_user_settings
from errlog import log_exc


def init_display(game):
    """First start only: read display prefs, open the window, create the canvas."""
    pygame.init()
    # Load display prefs early so the FIRST (and only) window is correct
    try:
        early = load_user_settings()
        game.monitor_index = int(early.get("monitor_index", 0) or 0)
        if game.monitor_index < 0:
            game.monitor_index = 0
        game.display_mode = early.get("display_mode", "fullscreen") or "fullscreen"
        if game.display_mode not in ("window", "fullscreen", "borderless"):
            game.display_mode = "fullscreen"
        game.bezel_style = early.get("bezel_style", "phoenix") or "phoenix"
        game.gpu_present = bool(early.get("gpu_present", True))
        game.gpu_bezels = bool(early.get("gpu_bezels", False))
        game.vsync_mode = early.get("vsync_mode", "adaptive") or "adaptive"
        if game.vsync_mode not in ("on", "adaptive", "off"):
            game.vsync_mode = "adaptive"
        try:
            game.fps_cap = int(early.get("fps_cap", 120) or 120)
        except Exception:
            game.fps_cap = 120
        if game.fps_cap not in (60, 75, 120, 144):
            game.fps_cap = 120
    except Exception:
        game.monitor_index = 0
        game.display_mode = "fullscreen"
        game.bezel_style = "phoenix"
        game.gpu_present = True
        game.gpu_bezels = False
        game.vsync_mode = "adaptive"
        game.fps_cap = 120
    game.clock = pygame.time.Clock()
    game.view_rect = pygame.Rect(0, 0, BASE_WIDTH, BASE_HEIGHT)
    game.bezel_active = False
    game._bezel_stars = []
    game.bezel_left_img = None
    game.bezel_right_img = None
    game._bezel_blit_left = None
    game._bezel_blit_right = None
    game._bezel_cache_key = None
    game._present_size = None
    game._scaled_game_buf = None
    # ONE set_mode only — double set_mode crashes some Intel/SDL multi-monitor setups
    game._prepare_monitor_env()
    game._open_display()
    game._gpu = GpuPresenter()
    game._gpu_backend = "scaled"
    game._display_ready = True
    try:
        # 32-bit matches SDL2 textures — Texture.update skips a convert
        game.game_surface = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), 0, 32)
        try:
            game.game_surface = game.game_surface.convert()
        except Exception:
            log_exc("game_init.init_display")
    except Exception:
        try:
            game.game_surface = pygame.Surface((BASE_WIDTH, BASE_HEIGHT)).convert()
        except Exception:
            game.game_surface = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    import settings as _settings
    game.fps_target = int(getattr(game, 'fps_cap', 120) or 120)
    _settings.FPS_TARGET = game.fps_target
    try:
        pygame.display.set_caption(f"Phenix Rebirth  [{game.fps_target} Hz]")
    except Exception:
        log_exc("game_init.init_display")


def init_run_state(game):
    """Player, formation, scores, high scores, achievements, pause/hot-seat/help/credits state."""
    game.player = Player(BASE_WIDTH // 2, BASE_HEIGHT - 95)
    game.formation = EnemyFormation()
    game.explosions = []
    # old explosion.py has no delay_frames — wrap once
    game.tesla_fx = None
    game.starfield = Starfield()

    game.running = True
    game.dt = 0.0
    game.score = 0
    game.game_over = False
    game.started = False
    game.stage = 1
    game.DEBUG_LIGHT_BG = False
    game.stage_transition = None  # None | "fly_up" | "arrive"
    game.transition_timer = 0.0
    game.boss_saucer = None
    game.boss_bird_timer = 0.0
    game._boss_angry_queue = []
    game._boss_cry_quiet = 0.0
    game.bosses_defeated = 0
    game.life_flash_timer = 0.0
    game.life_flash_index = -1
    game.life_thresholds = [(1337, False), (8086, False)]

    # High score flow: None | "enter" | "table"
    game.hs_phase = None
    game.hs_entries = load_highscores()
    game.ach_data = load_achievements()
    game._ach_icon_cache = {}
    game.ach_scroll = 0.0
    game.ach_speed = 0.0
    game.ach_hold = 0.0
    game.ach_hold_dir = 0
    game._listen = {"menu": 0.0, "gameover": 0.0, "credits": 0.0}
    game._listen_key = None
    game._listen_pos = 0
    game.credits_from_start = False
    game.juke_index = 0
    game.juke_paused = False
    # ingame_music loaded from settings.json below
    game.juke_video = False
    game.juke_clip = None
    game._eq_n = 40
    game._eq_bands = [0.04] * 40
    game._eq_peaks = [0.04] * 40
    game._eq_seq = {}
    game.stage_life_lost = False
    game.stage_touched_edge = False
    game.hs_name = ["A", "A", "A"]
    game.hs_char_index = 0
    game.hs_submitted = False
    game.hs_just_added = []
    game._hs_joy_cooldown = 0.0
    game.cheat_buffer = ""
    game.cheat_msg_timer = 0.0
    game.cheat_msg = ""
    game.cheat_kind = ""
    game.used_cheat = False
    game.phenix_cheat = False
    game.cheat_live = False
    game.paused = False
    game.pause_index = 0  # Reprendre
    game.pause_options = False  # options opened from pause
    game.quit_confirm = False
    game.quit_index = 1  # default Non
    game.menu_idle = 0.0
    game.help_timer = 0.0
    game.help_page = 0  # 0 = scenario/points, 1 = PHENIX
    game.help_scroll = 0.0  # transition offset in pixels
    game.help_transitioning = False
    game.HELP_PAGE_SEC = 13.0
    game.HELP_SCROLL_SEC = 0.42
    game.help_first_shown = False  # first attract uses longer delay
    game.attract_mode = False
    game.attract_timer = 0.0
    game.AUDIO_MIXES = ["sfx", "sfx_music", "music", "off"]
    # Hot-seat 2P: each player has a fully independent run (stage/score/lives/world)
    game.hotseat = False
    game.play_mode = getattr(game, "play_mode", "solo")  # solo | hotseat | coop
    game.PLAY_MODES = ["solo", "hotseat", "coop"]
    game.player2 = None
    game.joysticks = []
    game.lives_shared = 5
    game.current_p = 0
    game.slots = [None, None]
    game.hotseat_wait = False
    game.hotseat_next = 0
    game.hotseat_hold = 0.0
    game.hotseat_pending = None  # None | "switch" | "eliminated" | "gameover"
    game.HOTSEAT_HOLD_LIFE = 1.25   # mid-life explosion
    game.HOTSEAT_HOLD_FINAL = 1.95  # last life / game over (covers Tesla climb)
    game.hs_queue = []
    game.hs_slot_label = 1
    game.next_is_attract = True  # after first help, alternate attract/help
    game.ai_move_smooth = 0.0
    game.ai_dir_locked = 0
    game.ai_dir_timer = 0.0
    game.help_anim_t = 0.0
    # Built after display ready — icons filled in _build_help_icons
    game.help_icons = {}
    game.credits_scroll = 0.0
    game.credits_speed = 42.0
    game.credits_x = 0.0
    game.credits_xv = 0.0


def init_fonts_and_logo(game):
    """Fonts, text caches and the animated title logo."""
    # Fonts with broad Unicode coverage (Cyrillic, accents, etc.)
    _font_names = "dejavusans,segoe ui,arial,consolas,notosans"
    game.font = pygame.font.SysFont(_font_names, 28, bold=True)
    game.menu_font = pygame.font.SysFont(_font_names, 22, bold=True)
    game.big_font = pygame.font.SysFont(_font_names, 64, bold=True)
    game.medium_font = pygame.font.SysFont(_font_names, 32, bold=True)
    game.text_cache = TextCache()
    game._opt_help_cache = {}
    game._credits_layout_cache = None
    game._menu_overlay = None
    game._gp_poll = 0.0
    game._fps_display = 0
    game._fps_timer = 0.0

    # Animated title logo (frame sequence from LogoPhenix.mp4)
    game.logo_frames = []
    game.logo_timer = 0.0
    game.logo_index = 0
    game.logo_fps = 12.0
    logo_dir = asset_path("logo")
    if os.path.isdir(logo_dir):
        for name in sorted(os.listdir(logo_dir)):
            if name.endswith(".png"):
                fp = os.path.join(logo_dir, name)
                try:
                    img = pygame.image.load(fp).convert_alpha()
                    # Fit width ~720 max for menu
                    # Menu-friendly size (~560px wide)
                    max_w = 560
                    if img.get_width() != max_w:
                        scale = max_w / img.get_width()
                        img = pygame.transform.smoothscale(
                            img, (max_w, max(1, int(img.get_height() * scale)))
                        )
                    game.logo_frames.append(img)
                except Exception:
                    log_exc("game_init.init_fonts_and_logo")


def init_effects_state(game):
    """Shake, fades, ship previews."""
    game.shake_amount = 0.0
    game.hitstop = 0.0
    game.phenix_flash = 0
    game.fade_t = 0.0
    game.fade_phase = None
    game.fade_action = None
    game.FADE_SEC = 5.0 / 60.0
    game.title_timer = 0.0

    game._load_ship_previews()
    game.ship_anim_t = 0.0


def init_input_menu(game):
    """Gamepad detection, menu state, story hub, difficulty."""
    # --- Input / menu ---
    pygame.joystick.init()
    game.joystick = None
    game.gamepad_detected = False
    if pygame.joystick.get_count() > 0:
        game.joystick = pygame.joystick.Joystick(0)
        game.joystick.init()
        game.gamepad_detected = True

    # Menu state: "main" | "options" | "story_hub"
    game.menu_screen = "main"
    game.story = StoryHub()
    game.menu_index = 0
    # Difficulty is session-only (not in settings.json) but must survive soft resets
    if not hasattr(game, "difficulty"):
        game.difficulty = "normal"  # novice | normal | veteran
    game.DIFFICULTIES = ["novice", "normal", "veteran"]
    game.DIFF_LABELS = {"novice": "Novice", "normal": "Normal", "veteran": "Veteran"}


def init_settings(game, soft):
    """Load settings.json (kept in memory on a soft restart), bezels, GPU binding."""
    # Load persistent settings (or keep in-memory on soft restart)
    user = load_user_settings()
    if not hasattr(game, "input_mode"):
        if user["input_mode"] in ("keyboard", "gamepad"):
            game.input_mode = user["input_mode"]
            if game.input_mode == "gamepad" and not game.gamepad_detected:
                game.input_mode = "keyboard"
        else:
            game.input_mode = "gamepad" if game.gamepad_detected else "keyboard"
    if not hasattr(game, "display_mode"):
        game.display_mode = user.get("display_mode", "fullscreen")
    if not hasattr(game, "sfx_volume"):
        game.sfx_volume = float(user.get("sfx_volume", 0.8))
    if not hasattr(game, "music_volume"):
        game.music_volume = float(user.get("music_volume", 0.4))
    if not hasattr(game, "audio_mix"):
        mix = str(user.get("audio_mix", "sfx") or "sfx")
        game.audio_mix = mix if mix in getattr(game, "AUDIO_MIXES", ["sfx"]) else "sfx"
    if not hasattr(game, "ingame_music"):
        game.ingame_music = ingame_normalize(user.get("ingame_music", "none"))
    game.season_force = game._read_season_force(user)
    game.april_gag = "idle"
    game.april_t = 0.0
    game.april_ox = game.april_oy = game.april_rot = 0.0
    if not hasattr(game, "rumble_level"):
        try:
            game.rumble_level = int(user.get("rumble_level", 3))
        except Exception:
            game.rumble_level = 3
        game.rumble_level = max(0, min(5, game.rumble_level))
    if not hasattr(game, "autofire"):
        game.autofire = bool(user.get("autofire", True))
    if not hasattr(game, "ship_id"):
        game.ship_id = "phoenix"
    if not hasattr(game, "ship_id_p2"):
        game.ship_id_p2 = "phoenix"
    if not hasattr(game, "shield_tint"):
        game.shield_tint = "red"
    if not hasattr(game, "shield_tint_p2"):
        game.shield_tint_p2 = "green"
    if not hasattr(game, "phoenix_tint"):
        game.phoenix_tint = "argent"
    if not hasattr(game, "phoenix_tint_p2"):
        game.phoenix_tint_p2 = "blue"
    game.ship_select_slot = 1
    game.ship_select_index = 0 if getattr(game, "ship_id", "phoenix") != "shield" else 1
    game.shield_slide = 1.0
    game.shield_slide_dir = -1
    game.shield_slide_from = "red"
    game._rebuild_life_icon()
    if not hasattr(game, "language"):
        game.language = user.get("language", "fr")
        if game.language not in LANG_CODES:
            game.language = "fr"
        set_lang(game.language)
    if not hasattr(game, "show_fps"):
        game.show_fps = bool(user.get("show_fps", False))  # default off
    if not hasattr(game, "scanlines"):
        raw = user.get("scanlines", 0)
        # Migrate old bool settings
        if isinstance(raw, bool):
            game.scanlines = 1 if raw else 0
        else:
            try:
                game.scanlines = max(0, min(3, int(raw)))
            except Exception:
                game.scanlines = 0
    game._scanline_surf = None
    game._scanline_level_cached = None
    if not hasattr(game, "bezel_style"):
        game.bezel_style = user.get("bezel_style", "phoenix")
    if not hasattr(game, "gpu_present"):
        game.gpu_present = bool(user.get("gpu_present", True))
    if not hasattr(game, "_gpu"):
        game._gpu = GpuPresenter()
    if not hasattr(game, "_gpu_backend"):
        game._gpu_backend = "scaled"
    if not hasattr(game, "monitor_index"):
        game.monitor_index = int(user.get("monitor_index", 0) or 0)
    # Registry of available bezels (id → i18n key)
    game.BEZEL_STYLES = [
        ("off", "bezel_off"),
        ("phoenix", "bezel_phoenix"),
        ("tesla", "bezel_tesla"),
        ("blue", "bezel_blue"),
        ("fire", "bezel_fire"),
    ]
    valid = {s[0] for s in game.BEZEL_STYLES}
    if getattr(game, "bezel_style", "phoenix") not in valid:
        game.bezel_style = "phoenix"
    if not soft:
        game._bind_gpu()


def init_audio_and_layout(game, soft):
    """Input cooldowns, sounds, help icons, bezel images, viewport layout."""
    # Joystick menu navigation cooldown (anti spam)
    game._joy_menu_cooldown = 0.0
    game.input_grace = 0.0
    game._joy_axis_latch_x = 0
    game._joy_axis_latch_y = 0
    game._hat_latch = (0, 0)
    try:
        pygame.key.set_repeat(220, 45)
    except Exception:
        log_exc("game_init.init_audio_and_layout")

    if not soft or not getattr(game, "sounds", None):
        game.sounds = SoundManager()
    game.sounds.set_master_volume(game.sfx_volume)
    game.sounds.set_music_volume(game.music_volume)
    game._apply_audio_mix()
    if not soft or not getattr(game, "help_icons", None):
        game._build_help_icons()
    if not soft or not getattr(game, "bezel_left_img", None):
        game._load_bezel_images()
    game.player.sounds = game.sounds
    game.formation.sounds = game.sounds

    # Display already opened once in boot (_open_display). Only layout/bezel finalize.
    if not soft:
        try:
            game._layout_viewport()
            if getattr(game, "bezel_active", False):
                game._ensure_bezel_cache()
        except Exception as e:
            print("post-boot layout failed:", e)
