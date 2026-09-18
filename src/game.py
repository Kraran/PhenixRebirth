"""
Phenix Rebirth — main game controller.

Owns the window, delta-time loop, menus, combat, stage progression,
pause/options, high scores, attract-mode help, and credits.

Play modes: solo, hot-seat (alternating), coop (simultaneous). Options cover
controls, autofire, volumes, session audio mix, rumble, display, GPU present,
VSync, refresh cap, bezels, FPS counter, CRT scanlines and language.
Cheats on the high-score menu: LVL2–LVL5, LIVE, PHEN.
v1.2.1 — looping music, animated help/boss, difficulty HUD, input swallows.

Architecture notes:
- Logical resolution BASE_WIDTH x BASE_HEIGHT (see settings.py).
- GPU path: pygame.SCALED. Ultrawide bezels use a wider logical canvas
  (same aspect as the monitor); SDL GPU-scales the composed frame.
- Display rebuild (GPU/bezel/mode) covers the desktop then refocuses the pad.
- State flags: started, game_over, paused, stage_transition, menu_screen, hs_phase.
- Stages cycle content 1–5 forever with rising speed (stage_speed_mult).
- Cheats on the menu high-score screen: LVL2–LVL5, LIVE, PHEN.

This file is intentionally large; split only if a future refactor needs it.
"""
import pygame
import math
import sys
import random
import os
import json
from datetime import datetime
from settings import *
from settings import stage_content, stage_speed_mult
from player import Player
from enemy import EnemyFormation, BigBird, Enemy
from boss import BossSaucer
from explosion import Explosion, TeslaCoilFx
from starfield import Starfield
from sounds import SoundManager
from pheq import load_pheq, resolve_path as pheq_resolve, sample as pheq_sample, tick as pheq_tick, draw as pheq_draw, clock_y as pheq_clock_y
from ingame_music import cycle as ingame_cycle, label as ingame_label, normalize as ingame_normalize
from mp3_title import title_from_path, title_for_key
from i18n import set_lang, get_lang, t, t_help, t_list, get_credits_lines, LANGS, LANG_CODES
from highscores import load_highscores, is_highscore, insert_score, reset_highscores
from achievements import (
    CATALOG, load_achievements, unlock_achievement, unlocked_count,
)
from gpu_present import GpuPresenter
from desktop_cover import show_cover, hide_cover
from intro import play_intro

from settings import user_data_dir, asset_path
SETTINGS_FILE = os.path.join(user_data_dir(), "settings.json")

def load_user_settings():
    defaults = {
        "input_mode": None,  # None = auto
        "display_mode": "fullscreen",
        "sfx_volume": 0.8,
        "music_volume": 0.4,
        "rumble_level": 3,  # 0=off … 3=normal … 5=max
        "autofire": True,  # hold fire key to shoot again when the shot leaves
        "language": "fr",
        "show_fps": False,
        "scanlines": 0,  # 0=off, 1/2/3 intensity
        "bezel_style": "phoenix",  # off | phoenix | (future styles)
        "monitor_index": 0,
        "gpu_present": True,  # SDL2 GPU upscale (falls back to CPU)
        "vsync_mode": "adaptive",  # on | adaptive | off
        "fps_cap": 120,  # 60 | 75 | 120
        "ship_id": "phoenix",  # P1 / solo
        "ship_id_p2": "phoenix",
    }
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        defaults.update({k: data[k] for k in defaults if k in data})
    except Exception:
        pass
    return defaults

def save_user_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("Could not save settings:", e)

class TextCache:
    """Cache font.render results — rebuild only when (font, text, color) changes."""
    __slots__ = ("_data",)

    def __init__(self):
        self._data = {}

    def get(self, font, text, color):
        key = (id(font), text, color)
        surf = self._data.get(key)
        if surf is None:
            if len(self._data) > 1200:
                # Drop oldest half — a full clear hitch-spikes menus/credits
                for k in list(self._data)[:600]:
                    self._data.pop(k, None)
            surf = font.render(str(text), True, color)
            self._data[key] = surf
        return surf

    def clear(self):
        self._data.clear()


class Game:
    """
    Top-level application object.

    Lifecycle: __init__ (load settings, build systems) → run() event/update/draw loop.
    Soft restart after a run re-enters __init__ while preserving user settings.
    """
    def __init__(self, soft=False):
        """soft=True: reset session state without recreating the window (no desktop flash)."""
        if not soft:
            pygame.init()
            # Load display prefs early so the FIRST (and only) window is correct
            try:
                early = load_user_settings()
                self.monitor_index = int(early.get("monitor_index", 0) or 0)
                if self.monitor_index < 0:
                    self.monitor_index = 0
                self.display_mode = early.get("display_mode", "fullscreen") or "fullscreen"
                if self.display_mode not in ("window", "fullscreen", "borderless"):
                    self.display_mode = "fullscreen"
                self.bezel_style = early.get("bezel_style", "phoenix") or "phoenix"
                self.gpu_present = bool(early.get("gpu_present", True))
                self.gpu_bezels = bool(early.get("gpu_bezels", False))
                self.vsync_mode = early.get("vsync_mode", "adaptive") or "adaptive"
                if self.vsync_mode not in ("on", "adaptive", "off"):
                    self.vsync_mode = "adaptive"
                try:
                    self.fps_cap = int(early.get("fps_cap", 120) or 120)
                except Exception:
                    self.fps_cap = 120
                if self.fps_cap not in (60, 75, 120):
                    self.fps_cap = 120
            except Exception:
                self.monitor_index = 0
                self.display_mode = "fullscreen"
                self.bezel_style = "phoenix"
                self.gpu_present = True
                self.gpu_bezels = False
                self.vsync_mode = "adaptive"
                self.fps_cap = 120
            self.clock = pygame.time.Clock()
            self.view_rect = pygame.Rect(0, 0, BASE_WIDTH, BASE_HEIGHT)
            self.bezel_active = False
            self._bezel_stars = []
            self.bezel_left_img = None
            self.bezel_right_img = None
            self._bezel_blit_left = None
            self._bezel_blit_right = None
            self._bezel_cache_key = None
            self._present_size = None
            self._scaled_game_buf = None
            # ONE set_mode only — double set_mode crashes some Intel/SDL multi-monitor setups
            self._prepare_monitor_env()
            self._open_display()
            self._gpu = GpuPresenter()
            self._gpu_backend = "scaled"
            self._display_ready = True
            try:
                # 32-bit matches SDL2 textures — Texture.update skips a convert
                self.game_surface = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), 0, 32)
                try:
                    self.game_surface = self.game_surface.convert()
                except Exception:
                    pass
            except Exception:
                try:
                    self.game_surface = pygame.Surface((BASE_WIDTH, BASE_HEIGHT)).convert()
                except Exception:
                    self.game_surface = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
            import settings as _settings
            self.fps_target = int(getattr(self, 'fps_cap', 120) or 120)
            _settings.FPS_TARGET = self.fps_target
            try:
                pygame.display.set_caption(f"Phenix Rebirth  [{self.fps_target} Hz]")
            except Exception:
                pass
        
        self.player = Player(BASE_WIDTH // 2, BASE_HEIGHT - 95)
        self.formation = EnemyFormation()
        self.explosions = []
        self.tesla_fx = None
        self.starfield = Starfield()
        
        self.running = True
        self.dt = 0.0
        self.score = 0
        self.game_over = False
        self.started = False
        self.stage = 1
        self.stage_transition = None  # None | "fly_up" | "arrive"
        self.transition_timer = 0.0
        self.boss_saucer = None
        self.boss_bird_timer = 0.0
        self.bosses_defeated = 0
        self.life_flash_timer = 0.0
        self.life_flash_index = -1
        self.life_thresholds = [(1337, False), (8086, False)]
        
        # High score flow: None | "enter" | "table"
        self.hs_phase = None
        self.hs_entries = load_highscores()
        self.ach_data = load_achievements()
        self._ach_icon_cache = {}
        self.ach_scroll = 0.0
        self.ach_speed = 0.0
        self.ach_hold = 0.0
        self.ach_hold_dir = 0
        self._listen = {"menu": 0.0, "gameover": 0.0, "credits": 0.0}
        self._listen_key = None
        self._listen_pos = 0
        self.credits_from_start = False
        self.juke_index = 0
        self.juke_paused = False
        self.ingame_music = getattr(self, "ingame_music", "none")
        self.juke_video = False
        self._eq_n = 40
        self._eq_bands = [0.04] * 40
        self._eq_peaks = [0.04] * 40
        self._eq_seq = {}
        self.stage_life_lost = False
        self.stage_touched_edge = False
        self.hs_name = ["A", "A", "A"]
        self.hs_char_index = 0
        self.hs_submitted = False
        self._hs_joy_cooldown = 0.0
        self.cheat_buffer = ""
        self.cheat_msg_timer = 0.0
        self.cheat_msg = ""
        self.cheat_kind = ""
        self.used_cheat = False
        self.phenix_cheat = False
        self.paused = False
        self.pause_index = 0  # Reprendre
        self.pause_options = False  # options opened from pause
        self.quit_confirm = False
        self.quit_index = 1  # default Non
        self.menu_idle = 0.0
        self.help_timer = 0.0
        self.help_page = 0  # 0 = scenario/points, 1 = PHENIX
        self.help_scroll = 0.0  # transition offset in pixels
        self.help_transitioning = False
        self.HELP_PAGE_SEC = 13.0
        self.HELP_SCROLL_SEC = 0.42
        self.help_first_shown = False  # first attract uses longer delay
        self.attract_mode = False
        self.attract_timer = 0.0
        # Session-only in-game audio mix (not saved). Default: SFX, no music.
        if not hasattr(self, "audio_mix"):
            self.audio_mix = "sfx"
        self.AUDIO_MIXES = ["sfx", "sfx_music", "music", "off"]
        self._apply_audio_mix()
        # Hot-seat 2P: each player has a fully independent run (stage/score/lives/world)
        self.hotseat = False
        self.play_mode = getattr(self, "play_mode", "solo")  # solo | hotseat | coop
        self.PLAY_MODES = ["solo", "hotseat", "coop"]
        self.player2 = None
        self.joysticks = []
        self.lives_shared = 5
        self.current_p = 0
        self.slots = [None, None]
        self.hotseat_wait = False
        self.hotseat_next = 0
        self.hotseat_hold = 0.0
        self.hotseat_pending = None  # None | "switch" | "eliminated" | "gameover"
        self.HOTSEAT_HOLD_LIFE = 1.25   # mid-life explosion
        self.HOTSEAT_HOLD_FINAL = 1.95  # last life / game over (covers Tesla climb)
        self.hs_queue = []
        self.hs_slot_label = 1
        self.next_is_attract = True  # after first help, alternate attract/help
        self.ai_move_smooth = 0.0
        self.ai_dir_locked = 0
        self.ai_dir_timer = 0.0
        self.help_anim_t = 0.0
        # Built after display ready — icons filled in _build_help_icons
        self.help_icons = {}
        self.credits_scroll = 0.0
        self.credits_speed = 42.0
        self.credits_x = 0.0
        self.credits_xv = 0.0
        
        # Fonts with broad Unicode coverage (Cyrillic, accents, etc.)
        _font_names = "dejavusans,segoe ui,arial,consolas,notosans"
        self.font = pygame.font.SysFont(_font_names, 28, bold=True)
        self.big_font = pygame.font.SysFont(_font_names, 64, bold=True)
        self.medium_font = pygame.font.SysFont(_font_names, 32, bold=True)
        self.text_cache = TextCache()
        self._opt_help_cache = {}
        self._credits_layout_cache = None
        self._menu_overlay = None
        self._gp_poll = 0.0
        self._fps_display = 0
        self._fps_timer = 0.0

        # Animated title logo (frame sequence from LogoPhenix.mp4)
        self.logo_frames = []
        self.logo_timer = 0.0
        self.logo_index = 0
        self.logo_fps = 12.0
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
                        self.logo_frames.append(img)
                    except Exception:
                        pass

        self.shake_amount = 0.0
        self.title_timer = 0.0
        
        self._load_ship_previews()
        self.ship_anim_t = 0.0
        
        # --- Input / menu ---
        pygame.joystick.init()
        self.joystick = None
        self.gamepad_detected = False
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            self.gamepad_detected = True
        
        # Menu state: "main" | "options"
        self.menu_screen = "main"
        self.menu_index = 0
        # Difficulty is session-only (not in settings.json) but must survive soft resets
        if not hasattr(self, "difficulty"):
            self.difficulty = "normal"  # novice | normal | veteran
        self.DIFFICULTIES = ["novice", "normal", "veteran"]
        self.DIFF_LABELS = {"novice": "Novice", "normal": "Normal", "veteran": "Veteran"}
        
        # Load persistent settings (or keep in-memory on soft restart)
        user = load_user_settings()
        if not hasattr(self, "input_mode"):
            if user["input_mode"] in ("keyboard", "gamepad"):
                self.input_mode = user["input_mode"]
                if self.input_mode == "gamepad" and not self.gamepad_detected:
                    self.input_mode = "keyboard"
            else:
                self.input_mode = "gamepad" if self.gamepad_detected else "keyboard"
        if not hasattr(self, "display_mode"):
            self.display_mode = user.get("display_mode", "fullscreen")
        if not hasattr(self, "sfx_volume"):
            self.sfx_volume = float(user.get("sfx_volume", 0.8))
        if not hasattr(self, "music_volume"):
            self.music_volume = float(user.get("music_volume", 0.4))
        if not hasattr(self, "rumble_level"):
            try:
                self.rumble_level = int(user.get("rumble_level", 3))
            except Exception:
                self.rumble_level = 3
            self.rumble_level = max(0, min(5, self.rumble_level))
        if not hasattr(self, "autofire"):
            self.autofire = bool(user.get("autofire", True))
        if not hasattr(self, "ship_id"):
            sid = user.get("ship_id", "phoenix")
            self.ship_id = sid if sid in ("phoenix", "shield") else "phoenix"
        if not hasattr(self, "ship_id_p2"):
            sid2 = user.get("ship_id_p2", user.get("ship_id", "phoenix"))
            self.ship_id_p2 = sid2 if sid2 in ("phoenix", "shield") else "phoenix"
        self.ship_select_slot = 1
        self.ship_select_index = 0 if getattr(self, "ship_id", "phoenix") != "shield" else 1
        self._rebuild_life_icon()
        if not hasattr(self, "language"):
            self.language = user.get("language", "fr")
            if self.language not in LANG_CODES:
                self.language = "fr"
            set_lang(self.language)
        if not hasattr(self, "show_fps"):
            self.show_fps = bool(user.get("show_fps", False))  # default off
        if not hasattr(self, "scanlines"):
            raw = user.get("scanlines", 0)
            # Migrate old bool settings
            if isinstance(raw, bool):
                self.scanlines = 1 if raw else 0
            else:
                try:
                    self.scanlines = max(0, min(3, int(raw)))
                except Exception:
                    self.scanlines = 0
        self._scanline_surf = None
        self._scanline_level_cached = None
        if not hasattr(self, "bezel_style"):
            self.bezel_style = user.get("bezel_style", "phoenix")
        if not hasattr(self, "gpu_present"):
            self.gpu_present = bool(user.get("gpu_present", True))
        if not hasattr(self, "_gpu"):
            self._gpu = GpuPresenter()
        if not hasattr(self, "_gpu_backend"):
            self._gpu_backend = "scaled"
        if not hasattr(self, "monitor_index"):
            self.monitor_index = int(user.get("monitor_index", 0) or 0)
        # Registry of available bezels (id → i18n key)
        self.BEZEL_STYLES = [
            ("off", "bezel_off"),
            ("phoenix", "bezel_phoenix"),
            ("tesla", "bezel_tesla"),
            ("blue", "bezel_blue"),
            ("fire", "bezel_fire"),
        ]
        valid = {s[0] for s in self.BEZEL_STYLES}
        if getattr(self, "bezel_style", "phoenix") not in valid:
            self.bezel_style = "phoenix"
        if not soft:
            self._bind_gpu()
        
        # Joystick menu navigation cooldown (anti spam)
        self._joy_menu_cooldown = 0.0
        self.input_grace = 0.0
        self._joy_axis_latch_x = 0
        self._joy_axis_latch_y = 0
        self._hat_latch = (0, 0)
        try:
            pygame.key.set_repeat(220, 45)
        except Exception:
            pass
        
        if not soft or not getattr(self, "sounds", None):
            self.sounds = SoundManager()
        self.sounds.set_master_volume(self.sfx_volume)
        self.sounds.set_music_volume(self.music_volume)
        self._apply_audio_mix()
        if not soft or not getattr(self, "help_icons", None):
            self._build_help_icons()
        if not soft or not getattr(self, "bezel_left_img", None):
            self._load_bezel_images()
        self.player.sounds = self.sounds
        self.formation.sounds = self.sounds
        
        # Display already opened once in boot (_open_display). Only layout/bezel finalize.
        if not soft:
            try:
                self._layout_viewport()
                if getattr(self, "bezel_active", False):
                    self._ensure_bezel_cache()
            except Exception as e:
                print("post-boot layout failed:", e)

    # --- Audio state machine (menu / game-over / in-game silence) ---
    def _apply_audio_mix(self):
        """Mute SFX when mix is music-only or off. Does not persist."""
        mix = getattr(self, "audio_mix", "sfx")
        if getattr(self, "sounds", None):
            self.sounds.sfx_muted = mix in ("music", "off")
            if mix in ("music", "off"):
                self.sounds.play_electric(False)


    def _tick_ingame_music(self):
        """Play the Options in-game track during a run (Off + 5 jukebox themes)."""
        if not getattr(self, "started", False) or getattr(self, "game_over", False):
            return
        if getattr(self, "attract_mode", False):
            return
        if getattr(self, "menu_screen", "") == "jukebox":
            return
        want = ingame_normalize(getattr(self, "ingame_music", "none"))
        if want == "none":
            return
        try:
            self.sounds.play_music(want)
        except Exception:
            pass

    def _update_music(self):
        """Menu / attract / optional in-game menu theme. Off silences everything."""
        mix = getattr(self, "audio_mix", "sfx")
        if mix == "off":
            self.sounds.stop_music()
            return
        if getattr(self, "menu_screen", "") == "jukebox":
            return
        if self.game_over and self.hs_phase in ("enter", "table"):
            self.sounds.play_music("gameover")
        elif not self.started:
            if self.menu_screen in ("highscores", "achievements"):
                self.sounds.play_music("gameover")
            elif self.menu_screen == "credits":
                self.sounds.play_music("credits")
            else:
                self.sounds.play_music("menu")
        elif getattr(self, "attract_mode", False):
            self.sounds.play_music("menu")
        elif mix in ("sfx_music", "music"):
            self.sounds.play_music("menu")
        else:
            self.sounds.stop_music()

    def _juke_catalog(self):
        return (
            ("menu", "juke_eternal", "music"),
            ("gameover", "juke_gameover", "music"),
            ("credits", "juke_lastcoin", "music"),
            ("nostalgie_start", "juke_nostalgie_start", "music"),
            ("nostalgie_elise", "juke_nostalgie_elise", "music"),
            ("intro", "juke_intro", "video"),
        )

    def _open_jukebox(self):
        self.menu_screen = "jukebox"
        self.juke_index = int(getattr(self, "juke_index", 0) or 0)
        self.juke_paused = False
        self.juke_video = False
        self.juke_video_i = 0
        self.juke_video_acc = 0.0
        self.juke_frames = None
        try:
            self.sounds.stop_music()
        except Exception:
            pass

    def _leave_jukebox_audio(self):
        self._juke_stop_video()
        try:
            self.sounds.stop_music()
        except Exception:
            pass
        self.juke_paused = False

    def _close_jukebox(self):
        """Esc / B from jukebox → high scores (same drawer)."""
        self._leave_jukebox_audio()
        self.menu_screen = "highscores"

    def _extra_enter(self, screen):
        """HS ↔ Hauts faits ↔ Jukebox."""
        if getattr(self, "menu_screen", "") == "jukebox" and screen != "jukebox":
            self._leave_jukebox_audio()
        if screen == "achievements":
            self.ach_data = load_achievements()
            self.ach_scroll = 0.0
            self.ach_speed = 0.0
            self.ach_hold = 0.0
            self.menu_screen = "achievements"
            try:
                for _aid, kind in CATALOG:
                    self._ach_icon(kind, True)
                    self._ach_icon(kind, False)
            except Exception:
                pass
        elif screen == "jukebox":
            self._open_jukebox()
        else:
            self.hs_entries = load_highscores()
            self.menu_screen = "highscores"

    def _extra_step(self, direction):
        order = ("highscores", "achievements", "jukebox")
        cur = getattr(self, "menu_screen", "")
        if cur not in order:
            return
        nxt = order[(order.index(cur) + int(direction)) % 3]
        self._extra_enter(nxt)

    def _juke_stop_video(self):
        self.juke_video = False
        self.juke_frames = None
        self.juke_video_i = 0
        self.juke_video_acc = 0.0

    def _juke_play_or_pause(self):
        cat = self._juke_catalog()
        i = int(getattr(self, "juke_index", 0) or 0) % len(cat)
        key, _title, kind = cat[i]
        if getattr(self, "juke_video", False):
            self._juke_stop_video()
            try:
                self.sounds.stop_music()
            except Exception:
                pass
            return
        if kind == "video":
            from intro import _frame_list, AUDIO_PATH, INTRO_FPS
            frames = _frame_list()
            self.juke_frames = frames
            self.juke_video = True
            self.juke_video_i = 0
            self.juke_video_acc = 0.0
            self.juke_paused = False
            self._juke_intro_fps = float(INTRO_FPS)
            try:
                if AUDIO_PATH and os.path.exists(AUDIO_PATH):
                    pygame.mixer.music.stop()
                    pygame.mixer.music.load(AUDIO_PATH)
                    pygame.mixer.music.set_volume(self.sounds.music_volume)
                    pygame.mixer.music.play(0)
                    self.sounds._current_music = "intro"
            except Exception as e:
                print("Jukebox intro audio:", e)
            return
        cur = None
        try:
            cur = self.sounds.current_music_key()
        except Exception:
            cur = None
        busy = False
        try:
            busy = self.sounds.music_busy()
        except Exception:
            busy = False
        if cur == key and (busy or self.juke_paused):
            self.juke_paused = not self.juke_paused
            self.sounds.pause_music(self.juke_paused)
            return
        self.juke_paused = False
        self.sounds.play_direct(key, loops=0)
        self._eq_ensure(key)







    def _eq_ensure(self, key):
        """Load original PHEQ1 file from assets/music/ (not music/eq remakes)."""
        seqs = getattr(self, "_eq_seq", None)
        if seqs is None:
            self._eq_seq = seqs = {}
        if key in seqs:
            return
        path = pheq_resolve(asset_path, key)
        seqs[key] = load_pheq(path) if path else None

    def _eq_tick(self, key, pos, playing, dt):
        self._eq_ensure(key)
        seq = (getattr(self, "_eq_seq", {}) or {}).get(key)
        n = int(seq["n"]) if seq else 40
        if len(getattr(self, "_eq_bands", [])) != n:
            self._eq_n = n
            self._eq_bands = [0.0] * n
            self._eq_peaks = [0.0] * n
        target = pheq_sample(seq, pos) if (playing and seq) else [0.0] * n
        pheq_tick(self._eq_bands, self._eq_peaks, target, playing and bool(seq), dt)

    def _draw_eq(self, surface):
        """Original neon bars from .pheq — no frame, no panel."""
        pheq_draw(
            surface, pygame,
            getattr(self, "_eq_bands", []),
            getattr(self, "_eq_peaks", []),
            BASE_WIDTH, BASE_HEIGHT,
        )

    def _update_jukebox(self):
        if getattr(self, "juke_video", False):
            if self.juke_paused:
                return
            fps = float(getattr(self, "_juke_intro_fps", 24.0) or 24.0)
            self.juke_video_acc = float(getattr(self, "juke_video_acc", 0.0)) + self.dt
            step = 1.0 / max(1.0, fps)
            frames = getattr(self, "juke_frames", None) or []
            while self.juke_video_acc >= step and frames:
                self.juke_video_acc -= step
                self.juke_video_i += 1
                if self.juke_video_i >= len(frames):
                    self._juke_stop_video()
                    try:
                        self.sounds.stop_music()
                    except Exception:
                        pass
                    break
            return
        if self.juke_paused:
            return
        key = None
        try:
            key = self.sounds.current_music_key()
        except Exception:
            key = None
        cat = self._juke_catalog()
        i = int(getattr(self, "juke_index", 0) or 0) % len(cat)
        want = cat[i][0]
        if key == want and not self.sounds.music_busy():
            # Track finished — stay selected, ready to replay
            pass

    def _juke_title(self, key, path=None):
        if key == "intro":
            return t("juke_intro")
        if path:
            tit = title_from_path(path)
            if tit:
                return tit
        return title_for_key(asset_path, key)


    def _draw_jukebox(self, surface):
        hdr = self._txt(self.medium_font, t("jukebox"), (255, 180, 90))
        surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 28))
        if getattr(self, "juke_video", False):
            frames = getattr(self, "juke_frames", None) or []
            i = int(getattr(self, "juke_video_i", 0) or 0)
            img = getattr(self, "_juke_frame_surf", None)
            if frames and 0 <= i < len(frames) and getattr(self, "_juke_frame_i", -1) != i:
                try:
                    raw = pygame.image.load(frames[i]).convert()
                    src_w, src_h = raw.get_size()
                    scale = min(BASE_WIDTH / max(1, src_w), (BASE_HEIGHT - 80) / max(1, src_h))
                    tw, th = max(1, int(src_w * scale)), max(1, int(src_h * scale))
                    img = pygame.transform.smoothscale(raw, (tw, th)) if raw.get_size() != (tw, th) else raw
                    self._juke_frame_surf = img
                    self._juke_frame_i = i
                except Exception:
                    img = None
            if img is not None:
                surface.blit(img, ((BASE_WIDTH - img.get_width()) // 2, 70 + (BASE_HEIGHT - 80 - img.get_height()) // 2))
            hint = self._txt(self.font, t("juke_hint_video"), (255, 220, 100))
            surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 40))
            return
        cat = self._juke_catalog()
        cur = None
        try:
            cur = self.sounds.current_music_key()
        except Exception:
            cur = None
        y0 = 100
        for i, (key, title_k, kind) in enumerate(cat):
            selected = i == int(getattr(self, "juke_index", 0) or 0)
            playing = (cur == key and kind == "music" and self.sounds.music_busy()) or (
                cur == key and kind == "music" and self.juke_paused
            )
            col = (255, 230, 120) if selected else (160, 160, 190)
            mark = "> " if selected else "  "
            extra = "  ||" if playing and self.juke_paused else ("  >" if playing else "")
            label = mark + self._juke_title(key) + extra
            surf = self._txt(self.medium_font, label, col)
            surface.blit(surf, (BASE_WIDTH // 2 - surf.get_width() // 2, y0 + i * 46))
        # Spectrum + progress of current audio
        i = int(getattr(self, "juke_index", 0) or 0) % len(cat)
        key, _tk, kind = cat[i]
        if kind == "music" and cur == key:
            if key not in getattr(self, "_eq_seq", {}):
                self._eq_ensure(key)
            pos = self.sounds.music_pos_sec() if not self.juke_paused else getattr(self, "_juke_hold_pos", 0.0)
            playing = bool(self.sounds.music_busy()) and not self.juke_paused
            if not getattr(self, "juke_paused", False):
                self._eq_tick(key, pos, playing, float(self.dt or 0.016))
            self._draw_eq(surface)
            dur = 0.0
            try:
                dur = float(self.sounds.music_duration(key) or 0.0)
            except Exception:
                dur = 0.0
            if not self.juke_paused:
                self._juke_hold_pos = pos
            if dur > 1.0:
                bx, by, bw, bh = 220, BASE_HEIGHT - 88, BASE_WIDTH - 440, 10
                pygame.draw.rect(surface, (40, 40, 55), (bx, by, bw, bh), border_radius=3)
                fill = max(0.0, min(1.0, pos / dur))
                pygame.draw.rect(surface, (255, 180, 80), (bx, by, int(bw * fill), bh), border_radius=3)
                clock = self._txt(
                    self.font,
                    f"{int(pos)//60}:{int(pos)%60:02d} / {int(dur)//60}:{int(dur)%60:02d}",
                    (180, 180, 210),
                )
                surface.blit(clock, (BASE_WIDTH // 2 - clock.get_width() // 2, pheq_clock_y(BASE_HEIGHT)))
        hint = self._txt(self.font, t("juke_hint"), (255, 220, 100))
        surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 40))

    # --- Difficulty & scoring helpers ---


    def _activate_phenix_from_input(self, ship=None):
        """Toggle Phenix: activate if ready, or cancel early (keep remaining gauge)."""
        if not self.started or self.paused or self.game_over or self.attract_mode:
            return
        if self.stage_transition is not None:
            return
        ships = [ship] if ship is not None else self._ships()
        for s in ships:
            if not s or not s.alive:
                continue
            if s.is_phenix:
                if s.cancel_phenix():
                    self.shake_amount = max(self.shake_amount, 3.0)
                return
            if s.try_activate_phenix():
                self.shake_amount = max(self.shake_amount, 4.0)
                if getattr(s, "uses_shield", False):
                    self._unlock_ach("iron_curtain")
                else:
                    self._unlock_ach("phenix_wake")
                return


    def _draw_cheat_message(self):
        """Centered, large, readable cheat / stage / 1UP banner."""
        if self.cheat_msg_timer <= 0 or not self.cheat_msg:
            return
        pulse = 0.55 + 0.45 * abs(math.sin(self.cheat_msg_timer * 5.0))
        msg = self.cheat_msg
        # Color by type (kind is language-agnostic)
        kind = getattr(self, "cheat_kind", "")
        if kind == "1up" or "1UP" in msg.upper():
            blink = int(self.cheat_msg_timer * 5) % 2 == 0
            col = (255, 255, 180) if blink else (255, 200, 60)
        elif kind == "phen" or "PHENIX" in msg.upper():
            col = (255, int(140 + 80 * pulse), 40)
        elif kind == "live":
            col = (120, 255, 160)
        elif kind == "stage":
            col = (180, 200, 255)
        elif kind == "ach":
            col = (255, int(180 + 50 * pulse), 80)
        else:
            col = (255, 220, 100)

        cm = self._txt(self.big_font, msg, col)
        cx = BASE_WIDTH // 2
        cy = BASE_HEIGHT // 2
        # Dark plate behind for readability
        pad_x, pad_y = 28, 16
        plate = pygame.Surface((cm.get_width() + pad_x * 2, cm.get_height() + pad_y * 2), pygame.SRCALPHA)
        pygame.draw.rect(plate, (0, 0, 0, 160), plate.get_rect(), border_radius=8)
        self.game_surface.blit(plate, (cx - plate.get_width() // 2, cy - plate.get_height() // 2))
        # Glow
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1)):
            g = self._txt(self.big_font, msg, col)
            g.set_alpha(int(50 + 60 * pulse))
            self.game_surface.blit(g, (cx - cm.get_width() // 2 + ox, cy - cm.get_height() // 2 + oy))
        self.game_surface.blit(cm, (cx - cm.get_width() // 2, cy - cm.get_height() // 2))

    def _add_score(self, ship, pts):
        pts = int(pts)
        if ship is not None:
            ship.score = getattr(ship, "score", 0) + pts
        if getattr(self, "play_mode", "solo") == "coop":
            self.score = sum(getattr(s, "score", 0) for s in self._ships())
        else:
            self.score += pts
        if pts >= 10:
            self._unlock_ach("first_blood")

    def _on_stage_cleared(self):
        """Hauts faits tied to finishing the current wave."""
        if not getattr(self, "stage_life_lost", False):
            self._unlock_ach("survivor")
        if int(getattr(self, "stage", 1) or 1) == 1 and not getattr(self, "stage_touched_edge", False):
            self._unlock_ach("no_edge")
        if getattr(self, "play_mode", "solo") == "coop":
            ships = [s for s in self._ships() if getattr(s, "ship_id", None)]
            ids = {getattr(s, "ship_id", "phoenix") for s in ships}
            if len(ids) >= 2:
                self._unlock_ach("mixed_squad")

    def _unlock_ach(self, aid):
        """Unlock a haut-fait unless attract / cheat run."""
        if getattr(self, "attract_mode", False) or getattr(self, "used_cheat", False):
            return False
        data = getattr(self, "ach_data", None)
        if unlock_achievement(aid, data):
            self.ach_data = load_achievements()
            if getattr(self, "cheat_kind", "") != "1up" or self.cheat_msg_timer <= 0:
                title = t("ach_" + aid)
                self.cheat_msg = f"{t('ach_unlocked')} — {title}"
                self.cheat_kind = "ach"
                self.cheat_msg_timer = 3.0
            return True
        return False

    def _unlock_ach_meta(self, aid):
        """Menu meta (listen / credits). Attract blocks; last-run cheat does not."""
        if getattr(self, "attract_mode", False):
            return False
        data = getattr(self, "ach_data", None)
        if unlock_achievement(aid, data):
            self.ach_data = load_achievements()
            if getattr(self, "cheat_kind", "") != "1up" or self.cheat_msg_timer <= 0:
                title = t("ach_" + aid)
                self.cheat_msg = f"{t('ach_unlocked')} — {title}"
                self.cheat_kind = "ach"
                self.cheat_msg_timer = 4.0
            return True
        return False

    def _tick_listen_achs(self):
        """Unlock when the current theme finishes a full play (loop wrap).

        Screen changes that keep the same track do not reset the counter.
        Only a real track change, volume off, or attract resets it.
        """
        if getattr(self, "menu_screen", "") == "jukebox":
            return
        listen = getattr(self, "_listen", None)
        if listen is None:
            listen = self._listen = {"menu": 0.0, "gameover": 0.0, "credits": 0.0}
        if getattr(self, "attract_mode", False):
            listen["menu"] = listen["gameover"] = listen["credits"] = 0.0
            self._listen_key = None
            self._listen_pos = 0
            return
        mix = getattr(self, "audio_mix", "sfx")
        vol = float(getattr(self.sounds, "music_volume", 0.0) or 0.0)
        if mix == "off" or vol < 0.02:
            listen["menu"] = listen["gameover"] = listen["credits"] = 0.0
            self._listen_key = None
            self._listen_pos = 0
            return
        key = None
        try:
            key = self.sounds.current_music_key()
        except Exception:
            key = None
        if key not in ("menu", "gameover", "credits"):
            # Fade / silence: keep counters, wait for the same track to resume.
            return
        if self._listen_key != key:
            for k in list(listen.keys()):
                if k != key:
                    listen[k] = 0.0
            self._listen_key = key
            self._listen_pos = 0
        listen[key] = float(listen.get(key, 0.0)) + float(self.dt)

        pos_ms = -1
        try:
            pos_ms = int(pygame.mixer.music.get_pos())
        except Exception:
            pos_ms = -1
        wrapped = False
        last = int(getattr(self, "_listen_pos", 0) or 0)
        if pos_ms >= 0:
            if last > 2500 and pos_ms + 800 < last:
                wrapped = True
            self._listen_pos = pos_ms
        need = 0.0
        try:
            need = float(self.sounds.music_duration(key) or 0.0)
        except Exception:
            need = 0.0
        near_end = False
        if need >= 8.0 and pos_ms >= 0:
            near_end = (pos_ms / 1000.0) >= (need - 0.45)
        elif need >= 8.0:
            near_end = listen[key] >= (need - 0.45)
        if not (wrapped or near_end):
            return
        aid = {"menu": "listen_menu", "gameover": "listen_hs", "credits": "listen_credits"}.get(key)
        done = getattr(self, "_listen_done", None)
        if done is None:
            done = self._listen_done = set()
        if not aid or aid in done:
            listen[key] = 0.0
            return
        done.add(aid)
        self._unlock_ach_meta(aid)
        listen[key] = 0.0
        self._listen_pos = 0

    def _ach_icon(self, kind, unlocked):
        """32px catalog icon, color or grey."""
        cache = getattr(self, "_ach_icon_cache", None)
        if cache is None:
            cache = self._ach_icon_cache = {}
        key = (kind, bool(unlocked))
        if key in cache:
            return cache[key]

        def _load(*parts):
            path = asset_path("sprites", *parts)
            try:
                return pygame.image.load(path).convert_alpha()
            except Exception:
                return None

        raw = None
        if kind == "bird1":
            raw = _load("bird1_flap0.png")
        elif kind == "bird2":
            raw = _load("bird2_flap0.png")
        elif kind == "boss":
            raw = _load("boss_core_00.png") or _load("boss_core.png")
        elif kind == "phenix":
            pdir = asset_path("sprites", "phenix")
            if os.path.isdir(pdir):
                names = sorted(n for n in os.listdir(pdir) if n.startswith("phenix_") and n.endswith(".png"))
                if names:
                    raw = _load("phenix", names[0])
        elif kind == "shield":
            sdir = asset_path("sprites", "shield")
            if os.path.isdir(sdir):
                for name in ("loop_00.png", "morph_03.png"):
                    raw = _load("shield", name)
                    if raw is not None:
                        break
            if raw is None:
                raw = _load("player_ship_shield.png")
        elif kind == "coop":
            raw = _load("icon_coop.png")
        elif kind == "flag":
            raw = pygame.Surface((28, 28), pygame.SRCALPHA)
            pygame.draw.rect(raw, (180, 40, 50), (8, 4, 16, 10))
            pygame.draw.line(raw, (200, 200, 210), (8, 4), (8, 26), 2)
        elif kind == "edge":
            raw = pygame.Surface((28, 28), pygame.SRCALPHA)
            pygame.draw.line(raw, (120, 220, 255), (6, 26), (10, 8), 2)
            pygame.draw.line(raw, (180, 240, 255), (10, 8), (16, 20), 2)
            pygame.draw.line(raw, (80, 180, 255), (16, 20), (22, 4), 2)
        elif kind == "music":
            raw = pygame.Surface((28, 28), pygame.SRCALPHA)
            pygame.draw.circle(raw, (230, 200, 90), (10, 22), 5)
            pygame.draw.circle(raw, (230, 200, 90), (22, 18), 4)
            pygame.draw.line(raw, (230, 200, 90), (14, 22), (14, 6), 3)
            pygame.draw.line(raw, (230, 200, 90), (25, 18), (25, 4), 3)
            pygame.draw.line(raw, (230, 200, 90), (14, 6), (25, 4), 3)
        elif kind == "scroll":
            raw = pygame.Surface((28, 28), pygame.SRCALPHA)
            pygame.draw.rect(raw, (200, 180, 120), (6, 4, 16, 20), 2, border_radius=2)
            pygame.draw.line(raw, (200, 180, 120), (10, 10), (18, 10), 2)
            pygame.draw.line(raw, (200, 180, 120), (10, 15), (18, 15), 2)
            pygame.draw.line(raw, (200, 180, 120), (10, 20), (16, 20), 2)
        else:
            raw = _load("player_ship.png")
        if raw is None:
            raw = pygame.Surface((28, 28), pygame.SRCALPHA)
            pygame.draw.circle(raw, (180, 180, 200), (14, 14), 12)
        try:
            r = raw.get_bounding_rect(min_alpha=24)
            if r.width > 1 and r.height > 1:
                raw = raw.subsurface(r).copy()
        except Exception:
            pass
        # Cap source size — a full-res morph frame would hitch the GPU path
        if raw.get_width() > 96 or raw.get_height() > 96:
            s = 96.0 / max(raw.get_width(), raw.get_height())
            raw = pygame.transform.scale(
                raw, (max(8, int(raw.get_width() * s)), max(8, int(raw.get_height() * s)))
            )
        h = 36
        w = max(8, int(raw.get_width() * h / max(1, raw.get_height())))
        try:
            icon = pygame.transform.smoothscale(raw, (w, h))
        except Exception:
            icon = pygame.transform.scale(raw, (w, h))
        if not unlocked:
            grey = icon.copy()
            grey.fill((70, 72, 82, 255), special_flags=pygame.BLEND_RGBA_MULT)
            icon = grey
        cache[key] = icon
        return icon

    def _ach_view(self):
        """List metrics: row height, clip top/bottom, max pixel scroll."""
        row_h = 112
        top, bottom = 88, BASE_HEIGHT - 56
        view_h = max(1, bottom - top)
        max_s = max(0.0, len(CATALOG) * row_h - view_h)
        return row_h, top, bottom, max_s

    def _update_ach_scroll(self):
        """Smooth scroll; hold time ramps speed (credits-style inertia)."""
        row_h, top, bottom, max_s = self._ach_view()
        axis = self._credits_scroll_axis()
        hold = float(getattr(self, "ach_hold", 0.0))
        last = int(getattr(self, "ach_hold_dir", 0))
        if axis == 0:
            hold = 0.0
            last = 0
            target = 0.0
        else:
            if axis != last:
                hold = 0.0
            hold += self.dt
            last = axis
            # 0.0s → 140 px/s, ~1.1s → 560 px/s (quadratic ease-in)
            t = min(1.0, hold / 1.10)
            mag = 140.0 + 420.0 * (t * t)
            target = mag if axis < 0 else -mag
        self.ach_hold = hold
        self.ach_hold_dir = last
        k = min(1.0, 9.0 * self.dt)
        self.ach_speed = float(getattr(self, "ach_speed", 0.0))
        self.ach_speed += (target - self.ach_speed) * k
        dt = min(0.05, max(0.0, float(self.dt or 0.0)))
        y = float(getattr(self, "ach_scroll", 0.0)) + self.ach_speed * dt
        if y < 0.0:
            y = 0.0
            self.ach_speed = 0.0
            self.ach_hold = 0.0
        elif y > max_s:
            y = max_s
            self.ach_speed = 0.0
            self.ach_hold = 0.0
        self.ach_scroll = y

    def _fmt_ach_date(self, raw):
        """ISO stamp → JJ/MM/AAAA."""
        if not raw:
            return ""
        s = str(raw).strip()
        try:
            if "T" in s:
                s = s.split("T", 1)[0]
            y, m, d = s[:10].split("-")
            return f"{d}/{m}/{y}"
        except Exception:
            return s[:10]

    def _draw_achievements(self, surface):
        """Single-column hauts faits, scrollable, date when unlocked."""
        try:
            self._draw_achievements_inner(surface)
        except Exception as e:
            print("achievements draw failed:", e)

    def _draw_achievements_inner(self, surface):
        data = getattr(self, "ach_data", None)
        if not data:
            data = self.ach_data = load_achievements()
        unlocked = data.get("unlocked") or {}
        tc = getattr(self, "text_cache", None)
        hdr = (tc.get(self.medium_font, t("achievements"), (255, 180, 90))
               if tc else self._txt(self.medium_font, t("achievements"), (255, 180, 90)))
        surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 18))
        count_txt = f"{unlocked_count(data)} / {len(CATALOG)}"
        count = (tc.get(self.font, count_txt, (180, 180, 210))
                 if tc else self._txt(self.font, count_txt, (180, 180, 210)))
        surface.blit(count, (BASE_WIDTH // 2 - count.get_width() // 2, 52))

        row_h, top, bottom, max_s = self._ach_view()
        x = 90
        col_w = BASE_WIDTH - 180
        body = getattr(self, "help_small", None) or self.font
        n = len(CATALOG)
        scroll = float(getattr(self, "ach_scroll", 0.0) or 0.0)
        scroll = max(0.0, min(max_s, scroll))
        self.ach_scroll = scroll

        # No surface.set_clip — SCALED/GPU present can freeze on clip changes.
        for i, (aid, kind) in enumerate(CATALOG):
            y = int(top + i * row_h - scroll)
            if y + row_h < top or y > bottom:
                continue
            on = aid in unlocked
            icon = self._ach_icon(kind, on)
            iy = y + (row_h - icon.get_height()) // 2 - 6
            if iy < bottom and iy + icon.get_height() > top:
                surface.blit(icon, (x, iy))
            tx = x + 52
            if on:
                title = t("ach_" + aid)
                desc = t("ach_" + aid + "_d")
                tcol, dcol = (255, 230, 160), (190, 195, 220)
                date_s = self._fmt_ach_date(unlocked.get(aid))
            else:
                title = t("ach_locked")
                desc = "—"
                tcol, dcol = (90, 90, 110), (70, 70, 85)
                date_s = ""
            ts = tc.get(self.font, title, tcol) if tc else self._txt(self.font, title, tcol)
            if y + 10 + ts.get_height() > top:
                surface.blit(ts, (tx, y + 10))
            if date_s:
                ds_date = (tc.get(body, date_s, (160, 170, 200))
                           if tc else body.render(date_s, True, (160, 170, 200)))
                surface.blit(ds_date, (x + col_w - ds_date.get_width(), y + 14))
            dy = y + 10 + ts.get_height() + 8
            for piece in self._wrap_ui(desc, body, col_w - 60)[:2]:
                if dy > bottom:
                    break
                dsurf = (tc.get(body, piece, dcol) if tc else body.render(piece, True, dcol))
                if dy + dsurf.get_height() > top:
                    surface.blit(dsurf, (tx, dy))
                dy += dsurf.get_height() + 4

        if max_s > 1:
            bar_x = BASE_WIDTH - 36
            bar_y, bar_h = top + 8, bottom - top - 16
            pygame.draw.rect(surface, (40, 40, 55), (bar_x, bar_y, 6, bar_h), border_radius=3)
            view_h = float(bottom - top)
            thumb_h = max(18, int(bar_h * view_h / max(view_h, n * row_h)))
            thumb_y = bar_y + int((bar_h - thumb_h) * scroll / max_s)
            pygame.draw.rect(surface, (200, 180, 120), (bar_x, thumb_y, 6, thumb_h), border_radius=3)

        hint = (tc.get(self.font, t("ach_hint_back"), (255, 220, 100))
                if tc else self._txt(self.font, t("ach_hint_back"), (255, 220, 100)))
        surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 42))

    def _draw_phenix_gauge(self, ship=None, gx=18, gy=100, align="left"):
        """HUD: 10-segment Phenix gauge + fire around label from level 3."""
        if ship is None:
            ship = getattr(self, "player", None)
        if ship is None:
            return
        gauge = float(getattr(ship, "phenix_gauge", 0))
        level = int(gauge)  # for label threshold
        blue = getattr(ship, "palette", "red") == "blue"
        shield_ship = bool(getattr(ship, "uses_shield", False) or getattr(ship, "ship_id", "") == "shield")
        seg_w, seg_h, gap = 14, 10, 3
        total_h = 10 * (seg_h + gap)
        pygame.draw.rect(self.game_surface, (20, 20, 35), (gx - 3, gy - 3, seg_w + 6, total_h + 3), border_radius=3)
        active = getattr(ship, "is_phenix", False)
        for i in range(10):
            y = gy + (9 - i) * (seg_h + gap)
            # How much of this segment is filled (supports fractional drain)
            seg_fill = max(0.0, min(1.0, gauge - i))
            if seg_fill > 0:
                t = (i + 1) / 10.0
                if blue or shield_ship:
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
                    self.game_surface, col,
                    (gx, y + (seg_h - fh), seg_w, fh),
                    border_radius=2,
                )
            else:
                pygame.draw.rect(self.game_surface, (40, 40, 55), (gx, y, seg_w, seg_h), border_radius=2)

        lab_y = gy + total_h + 6
        tc = self.text_cache
        right = align == "right" or gx > BASE_WIDTH // 2
        shield_ship = bool(getattr(ship, "uses_shield", False) or getattr(ship, "ship_id", "") == "shield")
        tag = "SHIELD" if shield_ship else "PHENIX"
        if shield_ship or level >= 3:
            ticks = pygame.time.get_ticks() * 0.001
            pulse = 0.75 + 0.25 * abs(math.sin(ticks * 4.0))
            power = gauge / 10.0 if shield_ship else (level - 3) / 7.0
            if blue or shield_ship:
                g_q = int((180 + 50 * power * pulse) // 8) * 8
                lab = tc.get(self.font, tag, (140, g_q, 255))
                glow = tc.get(self.font, tag, (80, 180, 255))
            else:
                g_q = int((140 + 80 * power * pulse) // 8) * 8
                b_q = int((40 + 40 * power) // 8) * 8
                lab = tc.get(self.font, tag, (255, g_q, b_q))
                glow_g = int((100 + 60 * power) // 8) * 8
                glow = tc.get(self.font, tag, (255, glow_g, 20))
            lab_x = (gx + seg_w - lab.get_width()) if right else (gx - 2)
            alpha = int(50 + 40 * power * pulse)
            glow.set_alpha(alpha)
            for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self.game_surface.blit(glow, (lab_x + ox, lab_y + oy))
            self.game_surface.blit(lab, (lab_x, lab_y))
        else:
            lab = tc.get(self.font, tag, (100, 140, 180) if blue else (120, 110, 100))
            lab_x = (gx + seg_w - lab.get_width()) if right else (gx - 2)
            self.game_surface.blit(lab, (lab_x, lab_y))

        num_col = ((180, 230, 255) if blue else (255, 220, 160)) if level >= 3 or active else (140, 140, 150)
        num = tc.get(self.font, str(int(round(gauge))), num_col)
        self.game_surface.blit(num, (gx + seg_w // 2 - num.get_width() // 2, gy - 18))





    @staticmethod
    def format_score(n):
        """Thousand-separated score for display (spaces)."""
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = 0
        s = f"{n:,}".replace(",", " ")
        return s

    def _coop_icon_surf(self):
        """Lazy-load a compact two-player pictogram (fits a HS row)."""
        icon = getattr(self, "_coop_icon", None)
        if icon is None:
            path = asset_path("sprites", "icon_coop.png")
            try:
                raw = pygame.image.load(path).convert_alpha()
            except Exception:
                raw = pygame.Surface((18, 16), pygame.SRCALPHA)
                pygame.draw.circle(raw, (180, 195, 220), (6, 5), 4)
                pygame.draw.circle(raw, (180, 195, 220), (12, 5), 4)
            try:
                r = raw.get_bounding_rect(min_alpha=24)
                if r.width > 1 and r.height > 1:
                    raw = raw.subsurface(r).copy()
            except Exception:
                pass
            th = 16
            tw = max(10, int(raw.get_width() * th / max(1, raw.get_height())))
            icon = pygame.transform.smoothscale(raw, (tw, th))
            self._coop_icon = icon
        return icon

    def _draw_coop_mark(self, surface, x, y, col=(170, 185, 210)):
        """Two-player mark. y is the top of the row text."""
        icon = self._coop_icon_surf()
        iy = y + (self.font.get_height() - icon.get_height()) // 2
        surface.blit(icon, (x, iy))

    def _hs_ship_icon(self, sid):
        """Tiny hull for the high-score table — same visual height after crop."""
        cache = getattr(self, "_hs_ship_icons", None)
        if cache is None:
            cache = self._hs_ship_icons = {}
        key = "shield" if sid == "shield" else "phoenix"
        if key in cache:
            return cache[key]
        path = asset_path("sprites", "player_ship_shield.png" if key == "shield" else "player_ship.png")
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
            pass
        h = 22
        w = max(8, int(raw.get_width() * h / max(1, raw.get_height())))
        cache[key] = pygame.transform.smoothscale(raw, (w, h))
        return cache[key]

    def _draw_hs_row(self, surface, y, rank, name, score, col, score_right_x=None, coop=False, ship=None, ship2=None):
        """Draw one high-score line: rank aligned on '.', score right-aligned."""
        if score_right_x is None:
            score_right_x = BASE_WIDTH // 2 + 160
        # Rank + dot (right-align rank digits against the dot)
        rank_s = f"{rank:>2}"
        dot = "."
        rank_surf = self._txt(self.font, rank_s, col)
        dot_surf = self._txt(self.font, dot, col)
        # Fixed column for the '.' so all ranks align
        dot_x = BASE_WIDTH // 2 - 120
        surface.blit(rank_surf, (dot_x - rank_surf.get_width(), y))
        surface.blit(dot_surf, (dot_x, y))
        # Name
        name_s = name if name else "---"
        name_surf = self._txt(self.font, f" {name_s}", col)
        surface.blit(name_surf, (dot_x + dot_surf.get_width() + 6, y))
        # Score right-aligned (or dashes)
        if score is None:
            sc_s = "—"
        else:
            sc_s = self.format_score(score)
        sc_surf = self._txt(self.font, sc_s, col)
        surface.blit(sc_surf, (score_right_x - sc_surf.get_width(), y))
        ix = score_right_x + 10
        if score is not None:
            ids = []
            if ship in ("phoenix", "shield"):
                ids.append(ship)
            elif not coop:
                ids = ["phoenix"]
            line_h = self.font.get_height()
            for sid in ids:
                icon = self._hs_ship_icon(sid)
                iy = y + (line_h - icon.get_height()) // 2
                surface.blit(icon, (ix, iy))
                ix += icon.get_width() + 3
        if coop:
            self._draw_coop_mark(surface, ix + 4, y)

    def difficulty_speed_mult(self):

        if self.difficulty == "novice":
            return 0.8
        if self.difficulty == "veteran":
            return 1.2
        return 1.0

    def _enemy_points(self, content_stage):
        """Points for killing a bird by content stage (1-4)."""
        base = {1: 10, 2: 20, 3: 30, 4: 40}.get(content_stage, 10)
        if self.difficulty == "veteran":
            return base + 10
        return base

    def _boss_points(self):
        return 300 if self.difficulty == "veteran" else 200

    def _apply_difficulty_start(self):
        """Lives and stage 1 setup when pressing JOUER."""
        if getattr(self.player, "uses_shield", False):
            self.player.phenix_sec_per_point = 0.6
            self.player.phenix_min_gauge = 0
            if float(getattr(self.player, "phenix_cooldown", 0) or 0) <= 0 and not self.player.is_phenix:
                self.player.phenix_gauge = 10.0
        elif self.difficulty == "novice":
            self.player.phenix_sec_per_point = 1.0
            self.player.phenix_min_gauge = 1
            self.player.phenix_gauge = 1
        else:
            self.player.phenix_sec_per_point = 0.6
            self.player.phenix_min_gauge = 0
        if self.phenix_cheat:
            self.player.phenix_auto_refill = True
            self.player.phenix_gauge = 10
        if self.player.infinite_lives:
            self.player.lives = 99
        elif self.difficulty == "novice":
            self.player.lives = 5
        else:
            self.player.lives = 3
        # Any active cheat (LVL / LIVE / PHEN) blocks high scores + shows banner
        self.used_cheat = bool(
            self.phenix_cheat
            or getattr(self.player, "infinite_lives", False)
            or getattr(self.player, "phenix_auto_refill", False)
        )
        self.bosses_defeated = 0
        self.life_flash_timer = 0.0
        self.life_flash_index = -1
        self.stage = 1
        self._setup_stage(1)

    def _rebuild_life_icon(self):
        sid = getattr(self, "ship_id", "phoenix")
        pl = getattr(self, "player", None)
        if pl is not None:
            sid = getattr(pl, "ship_id", sid)
        path = asset_path("sprites", "player_ship_shield.png") if sid == "shield" else asset_path("sprites", "player_ship.png")
        try:
            ship_full = pygame.image.load(path).convert_alpha()
        except Exception:
            ship_full = pygame.image.load(asset_path("sprites", "player_ship.png")).convert_alpha()
        mini_h = 22
        scale = mini_h / max(1, ship_full.get_height())
        mini_w = max(1, int(ship_full.get_width() * scale))
        self.life_icon = pygame.transform.smoothscale(ship_full, (mini_w, mini_h)).convert_alpha()

    def _load_ship_previews(self):
        """Menu portraits + focus animations (Phenix flap / Shield loop)."""
        self.preview_ships = {}
        def _load(path):
            try:
                return pygame.image.load(path).convert_alpha()
            except Exception:
                return None
        idle_p = _load(asset_path("sprites", "player_ship.png"))
        anim_p = []
        pdir = asset_path("sprites", "phenix")
        if os.path.isdir(pdir):
            for name in sorted(os.listdir(pdir)):
                if name.startswith("phenix_") and name.endswith(".png"):
                    fr = _load(os.path.join(pdir, name))
                    if fr is not None:
                        anim_p.append(fr)
        self.preview_ships["phoenix"] = {"idle": idle_p, "anim": anim_p or ([idle_p] if idle_p else [])}
        idle_s = _load(asset_path("sprites", "player_ship_shield.png"))
        anim_s = []
        sdir = asset_path("sprites", "shield")
        if os.path.isdir(sdir):
            for name in sorted(os.listdir(sdir)):
                if name.startswith("loop_") and name.endswith(".png"):
                    fr = _load(os.path.join(sdir, name))
                    if fr is not None:
                        anim_s.append(fr)
        self.preview_ships["shield"] = {"idle": idle_s, "anim": anim_s or ([idle_s] if idle_s else [])}

    def _ship_for_pid(self, pid):
        if int(pid) == 2:
            return getattr(self, "ship_id_p2", "phoenix")
        return getattr(self, "ship_id", "phoenix")

    def _p2_needs_blue(self):
        """P2 is tinted blue only when both players fly the same hull."""
        return self._ship_for_pid(1) == self._ship_for_pid(2)

    def _open_ship_select(self, slot=1):
        self.menu_screen = "ship_select"
        self.ship_select_slot = 1 if int(slot) != 2 else 2
        sid = self._ship_for_pid(self.ship_select_slot)
        self.ship_select_index = 0 if sid != "shield" else 1
        self.ship_anim_t = 0.0
        self.input_grace = 0.20

    def _draw_ship_select(self, surface):
        slot = int(getattr(self, "ship_select_slot", 1) or 1)
        two_p = getattr(self, "play_mode", "solo") in ("hotseat", "coop")
        if two_p:
            heading = t("choose_ship_p").replace("{n}", str(slot))
        else:
            heading = t("choose_ship")
        title = self._txt(self.medium_font, heading, (255, 230, 140))
        surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 72))
        ids = ("phoenix", "shield")
        labels = (t("ship_phoenix"), t("ship_shield"))
        focus = int(getattr(self, "ship_select_index", 0)) % 2
        anim_t = getattr(self, "ship_anim_t", 0.0)
        previews = getattr(self, "preview_ships", {})
        slots = (BASE_WIDTH // 2 - 220, BASE_WIDTH // 2 + 220)
        for i, sid in enumerate(ids):
            cx = slots[i]
            cy = 360
            pack = previews.get(sid) or {}
            idle = pack.get("idle")
            frames = pack.get("anim") or []
            img = idle
            if i == focus and frames:
                idx = int(anim_t * 8.0) % len(frames)
                img = frames[idx]
            if img is None:
                continue
            # Focused ship a bit larger
            target_h = 200 if i == focus else 150
            scale = target_h / max(1, img.get_height())
            tw = max(1, int(img.get_width() * scale))
            th = max(1, int(img.get_height() * scale))
            spr = pygame.transform.smoothscale(img, (tw, th))
            if i == focus:
                bob = int(math.sin(anim_t * 3.2) * 4)
            else:
                bob = 0
            rx = cx - tw // 2
            ry = cy - th // 2 + bob
            if i == focus:
                pad = 18
                box = pygame.Rect(rx - pad, ry - pad, tw + pad * 2, th + pad * 2)
                pygame.draw.rect(surface, (255, 210, 90), box, 2, border_radius=10)
            surface.blit(spr, (rx, ry))
            col = (255, 230, 120) if i == focus else (150, 150, 175)
            name = self._txt(self.font, labels[i], col)
            surface.blit(name, (cx - name.get_width() // 2, cy + 130))
        hint = self._txt(self.font, t("ship_hint"), (160, 160, 190))
        surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 56))

    def _apply_ship_choice(self):
        for ship in self._ships():
            if not hasattr(ship, "set_ship"):
                continue
            pid = int(getattr(ship, "pid", 1) or 1)
            ship.set_ship(self._ship_for_pid(pid))
            if pid == 2 and self._p2_needs_blue() and hasattr(ship, "apply_blue_palette"):
                ship.apply_blue_palette()
        self._rebuild_life_icon()

    def _begin_run(self):
        """Start the chosen play mode after ship select."""
        mode = getattr(self, "play_mode", "solo")
        if mode == "hotseat":
            self.hotseat = True
            self.current_p = 0
            self._init_hotseat_slots()
            self._apply_slot(self.slots[0])
            self.started = True
            self.hotseat_wait = True
            self.hotseat_next = 0
            self.input_grace = 0.35
        elif mode == "coop":
            self._start_coop()
        else:
            self.hotseat = False
            self.player2 = None
            self._apply_ship_choice()
            self._apply_difficulty_start()
            self.started = True
            self.input_grace = 0.35
        self._rebuild_life_icon()
        self.menu_screen = "main"

    def _capture_slot(self):
        """Snapshot the active run so another player can take over."""
        return {
            "player": self.player,
            "formation": self.formation,
            "boss_saucer": self.boss_saucer,
            "score": self.score,
            "stage": self.stage,
            "bosses_defeated": self.bosses_defeated,
            "life_thresholds": list(self.life_thresholds),
            "boss_bird_timer": getattr(self, "boss_bird_timer", 0.0),
            "eliminated": bool(getattr(self.player, "alive", True) is False),
        }

    def _apply_slot(self, slot):
        """Restore a player's independent world."""
        if not slot:
            return
        self.player = slot["player"]
        self.formation = slot["formation"]
        self.boss_saucer = slot["boss_saucer"]
        self.score = slot["score"]
        self.stage = slot["stage"]
        self.bosses_defeated = slot["bosses_defeated"]
        self.life_thresholds = list(slot["life_thresholds"])
        self.boss_bird_timer = slot.get("boss_bird_timer", 1.2)
        self.stage_transition = None
        self.transition_timer = 0.0
        self.explosions = []
        self.shake_amount = 0.0
        # Fresh ship placement; keep gauge / lives / phenix flags on the Player object
        self.player.x = BASE_WIDTH // 2
        self.player.y = BASE_HEIGHT - 95
        self.player.destroy_bullet()
        self.player.dying = False
        if self.player.lives > 0 or getattr(self.player, "infinite_lives", False):
            self.player.alive = True
        self.player.invulnerable = 1.1
        self._rebuild_life_icon()
        self.player.just_lost_life = False
        self.player.clear_wall_status()
        self.tesla_fx = None
        self.sounds.play_electric(False)
        if getattr(self.player, "is_phenix", False):
            try:
                self.player.end_phenix(grant_invuln=True, keep_gauge=True)
            except Exception:
                pass

    def _save_current_slot(self):
        if not self.hotseat:
            return
        cap = self._capture_slot()
        if self.slots[self.current_p]:
            cap["eliminated"] = self.slots[self.current_p].get("eliminated", False)
        self.slots[self.current_p] = cap

    def _init_hotseat_slots(self):
        """Build two independent stage-1 runs (same difficulty / cheat flags)."""
        self.slots = []
        for i in range(2):
            self.player = Player(BASE_WIDTH // 2, BASE_HEIGHT - 95, ship_id=self._ship_for_pid(i + 1))
            self.player.sounds = self.sounds
            self.player.pid = i + 1
            if i == 1 and self._p2_needs_blue():
                self.player.apply_blue_palette()
            self.formation = EnemyFormation()
            self.boss_saucer = None
            self.score = 0
            self.stage = 1
            self.explosions = []
            self.life_thresholds = [(1337, False), (8086, False)]
            self._apply_difficulty_start()
            slot = self._capture_slot()
            slot["eliminated"] = False
            self.slots.append(slot)
        self.hotseat_p2_picked = False
        self.hotseat_pick_p2 = False

    def _apply_hotseat_p2_ship(self):
        """P2 just chose a hull — stamp it on their slot then show the turn banner."""
        sid = getattr(self, "ship_id_p2", "phoenix")
        if self.slots and len(self.slots) > 1 and self.slots[1].get("player"):
            p = self.slots[1]["player"]
            p.set_ship(sid)
            p.pid = 2
            if self._p2_needs_blue():
                p.apply_blue_palette()
            if getattr(p, "uses_shield", False):
                p.phenix_gauge = 10.0
                p.phenix_cooldown = 0.0
        self.hotseat_p2_picked = True
        self.hotseat_pick_p2 = False
        self.menu_screen = "main"
        self._hotseat_begin_wait(1)

    def _other_p(self):
        return 1 - self.current_p

    def _slot_still_playing(self, idx):
        sl = self.slots[idx] if 0 <= idx < 2 else None
        if not sl or sl.get("eliminated"):
            return False
        p = sl.get("player")
        if p is None:
            return False
        return bool(getattr(p, "infinite_lives", False) or getattr(p, "lives", 0) > 0 or p.alive)

    def _hotseat_begin_wait(self, next_idx):
        """Interstitial: wait for any key before loading the other player's world."""
        if int(next_idx) == 1 and not getattr(self, "hotseat_p2_picked", False):
            self._save_current_slot()
            if self.player:
                self.player.clear_wall_status()
            self.hotseat_next = 1
            self.hotseat_wait = False
            self.hotseat_pick_p2 = True
            self._open_ship_select(2)
            return
        if int(getattr(self, "current_p", 0) or 0) == 1:
            self._unlock_ach("hotseat")
        self._save_current_slot()
        if self.player:
            self.player.clear_wall_status()
        outgoing = self.slots[self.current_p] if self.slots[self.current_p] else None
        if outgoing and outgoing.get("player"):
            outgoing["player"].clear_wall_status()
        self.hotseat_wait = True
        self.hotseat_next = next_idx
        self.input_grace = 0.28
        self.paused = False
        self.tesla_fx = None
        self.sounds.play_electric(False)

    def _hotseat_resume(self):
        if not self.hotseat_wait:
            return
        self.hotseat_wait = False
        self.current_p = self.hotseat_next
        self._apply_slot(self.slots[self.current_p])
        self.input_grace = 0.35
        self.game_over = False

    def _hotseat_arm_hold(self, pending, duration):
        """Wait so the ship explosion is visible before overlay / game over."""
        if self.hotseat_hold > 0:
            return
        self.hotseat_hold = duration
        self.hotseat_pending = pending
        if self.player:
            self.player.just_lost_life = False

    def _hotseat_finish_hold(self):
        pending = self.hotseat_pending
        self.hotseat_pending = None
        self.hotseat_hold = 0.0
        if pending == "switch":
            self._hotseat_try_switch()
        elif pending == "eliminated":
            self._hotseat_player_eliminated()
        elif pending == "gameover":
            self.game_over = True
            self._begin_highscore_flow()

    def _hotseat_try_switch(self):
        """After a lost life (ship still has lives): other player takes their own run."""
        other = self._other_p()
        if self._slot_still_playing(other):
            self._hotseat_begin_wait(other)
        # else keep playing — opponent already eliminated

    def _hotseat_player_eliminated(self):
        """Current player has no lives left."""
        if int(getattr(self, "current_p", 0) or 0) == 1:
            self._unlock_ach("hotseat")
        self._save_current_slot()
        if self.slots[self.current_p]:
            self.slots[self.current_p]["eliminated"] = True
        other = self._other_p()
        if self._slot_still_playing(other):
            self._hotseat_begin_wait(other)
        else:
            self.game_over = True
            self._begin_highscore_flow()

    def _ships(self):
        """Active ships this frame (1 in solo/hotseat, 2 in coop)."""
        out = []
        if self.player:
            out.append(self.player)
        if getattr(self, "play_mode", "solo") == "coop" and getattr(self, "player2", None):
            out.append(self.player2)
        return out


    def _sfx_electric_x(self):
        """Pan tesla/edge crackle to the wall or the sparking ship."""
        fx = getattr(self, "tesla_fx", None)
        if fx is not None:
            return getattr(fx, "x", 0)
        for ship in self._ships():
            if getattr(ship, "edge_flash", 0) > 0.08:
                return ship.x
        return None

    def _living_ships(self):
        return [p for p in self._ships() if p.alive and not p.dying]

    def _coop_bindings(self):
        """Assign kb/pad for coop: 2 pads, or kb+pad, or split keyboard."""
        joys = []
        try:
            pygame.joystick.init()
            for i in range(pygame.joystick.get_count()):
                j = pygame.joystick.Joystick(i)
                j.init()
                joys.append(j)
        except Exception:
            joys = []
        self.joysticks = joys
        if len(joys) >= 2:
            return ("pad", joys[0]), ("pad", joys[1])
        if len(joys) == 1:
            # P1 pad, P2 same keyboard layout as 1-player
            return ("pad", joys[0]), ("solo", None)
        return ("kb1", None), ("kb2", None)

    def _start_coop(self):
        self.play_mode = "coop"
        self.hotseat = False
        self.player2 = Player(BASE_WIDTH // 2 + 70, BASE_HEIGHT - 95, ship_id=self._ship_for_pid(2))
        self.player = Player(BASE_WIDTH // 2 - 70, BASE_HEIGHT - 95, ship_id=self._ship_for_pid(1))
        self.player.pid = 1
        self.player2.pid = 2
        self.player.sounds = self.sounds
        self.player2.sounds = self.sounds
        if self._p2_needs_blue():
            self.player2.apply_blue_palette()
        self.player.use_shared_lives = True
        self.player2.use_shared_lives = True
        b1, b2 = self._coop_bindings()
        self.player.input_scheme = b1[0]
        self.player2.input_scheme = b2[0]
        self.player._joy = b1[1]
        self.player2._joy = b2[1]
        if b1[0] == "pad":
            self.joystick = b1[1]
        elif b2[0] == "pad":
            self.joystick = b2[1]
        self.lives_shared = 5
        self._apply_difficulty_start()
        # Shared pool overrides per-difficulty lives
        self.lives_shared = 5
        self.player.lives = 5
        self.player2.lives = 5
        self.player.use_shared_lives = True
        self.player2.use_shared_lives = True
        self.player2.phenix_sec_per_point = self.player.phenix_sec_per_point
        self.player2.phenix_min_gauge = self.player.phenix_min_gauge
        self.player.score = 0
        self.player2.score = 0
        self.player.life_flags = [False, False]
        self.player2.life_flags = [False, False]
        self.player2.sounds = self.sounds
        self._sync_special_gauges()
        self.started = True
        self.input_grace = 0.35
        try:
            pygame.key.set_repeat(0)
        except Exception:
            pass

    def _sync_special_gauges(self):
        """Both coop/hot-seat ships share the chosen hull rules."""
        for s in self._ships():
            if not s:
                continue
            if getattr(s, "uses_shield", False):
                s.phenix_min_gauge = 0
                if not s.is_phenix and float(getattr(s, "phenix_cooldown", 0) or 0) <= 0:
                    s.phenix_gauge = 10.0
                s.SHIELD_DURATION = 2.0
                s.SHIELD_COOLDOWN = 5.0
            else:
                s.phenix_sec_per_point = getattr(self.player, "phenix_sec_per_point", 0.6)
                s.phenix_min_gauge = getattr(self.player, "phenix_min_gauge", 0)
                if self.difficulty == "novice" and not s.is_phenix:
                    s.phenix_gauge = max(float(s.phenix_gauge), 1.0)

    def _on_coop_life_lost(self, ship):
        if getattr(self, "play_mode", "") != "coop":
            return
        self.lives_shared = max(0, self.lives_shared - 1)
        for p in self._ships():
            p.lives = self.lives_shared
        if self.lives_shared <= 0 and not ship.dying:
            ship.lives = 0
            ship.dying = True
            ship.death_timer = 0.0
            ship.invulnerable = 0.0
            ship.rumble(1.0, 1.0, 640)

    def _check_extra_lives(self):

        """Award a life when crossing score thresholds (once each)."""
        if self.play_mode == "coop":
            for ship in self._ships():
                flags = getattr(ship, "life_flags", None)
                if not flags or len(flags) < len(self.life_thresholds):
                    ship.life_flags = [False] * len(self.life_thresholds)
                    flags = ship.life_flags
                for i, (threshold, _) in enumerate(self.life_thresholds):
                    if not flags[i] and getattr(ship, "score", 0) >= threshold:
                        flags[i] = True
                        self.lives_shared += 1
                        for s in self._ships():
                            s.lives = self.lives_shared
                        self.sounds.play("1up")
                        self.cheat_msg = t("one_up")
                        self.cheat_kind = "1up"
                        self.cheat_msg_timer = 5.0
                        self.life_flash_timer = 4.0
                        self.life_flash_index = max(0, self.lives_shared - 1)
                        if threshold == 1337:
                            self._unlock_ach("one_up_1337")
                        elif threshold == 8086:
                            self._unlock_ach("elite_8086")
            return
        for i, (threshold, awarded) in enumerate(self.life_thresholds):
            if not awarded and self.score >= threshold:
                self.life_thresholds[i] = (threshold, True)
                if self.player.alive:
                    self.player.lives += 1
                    self.sounds.play("1up")
                    self.cheat_msg = t("one_up")
                    self.cheat_kind = "1up"
                    self.cheat_msg_timer = 5.0
                    self.life_flash_timer = 4.0
                    self.life_flash_index = max(0, self.player.lives - 1)
                    if threshold == 1337:
                        self._unlock_ach("one_up_1337")
                    elif threshold == 8086:
                        self._unlock_ach("elite_8086")

    # --- Stage setup (content cycle + speed tier) ---
    def _setup_stage(self, stage):
        """Load content for stage (1-5 cycle) with speed scaling + difficulty."""
        self.stage_life_lost = False
        self.stage_touched_edge = False
        content = stage_content(stage)
        mult = stage_speed_mult(stage) * self.difficulty_speed_mult()
        self.formation.enemies = []
        self.formation.bullets = []
        self.boss_saucer = None
        if content == 5:
            self.boss_saucer = BossSaucer()
            # Scale boss descend/shoot lightly with mult
            self.boss_saucer.descend_speed *= mult
            self.boss_saucer.speed *= mult
            self.boss_bird_timer = 1.2
        else:
            self.formation.spawn_stage(content, speed_mult=mult)
            self.formation.sounds = self.sounds

    # --- Cheats (high-score menu keyboard buffer) ---
    def _feed_cheat(self, ch):
        """Accumulate alnum from the high-score menu and fire known codes."""
        self.cheat_buffer = (self.cheat_buffer + ch.upper())[-10:]
        buf = self.cheat_buffer
        if "LVL5" in buf:
            self._start_at_stage(5)
        elif "LVL4" in buf:
            self._start_at_stage(4)
        elif "LVL3" in buf:
            self._start_at_stage(3)
        elif "LVL2" in buf:
            self._start_at_stage(2)
        elif "LIVE" in buf:
            self.used_cheat = True
            self.player.infinite_lives = True
            self.player.lives = 99
            self.cheat_buffer = ""
            self.cheat_msg = t("cheat_live")
            self.cheat_kind = "live"
            self.cheat_msg_timer = 5.0
        elif "PHEN" in buf:
            self.used_cheat = True
            self.phenix_cheat = True
            self.player.phenix_auto_refill = True
            self.player.phenix_gauge = 10
            self.cheat_buffer = ""
            self.cheat_msg = t("cheat_phen")
            self.cheat_kind = "phen"
            self.cheat_msg_timer = 5.0

    def _start_at_stage(self, stage):

        """Cheat: jump straight into a stage from the menu."""
        self.started = True
        self.game_over = False
        self.hs_phase = None
        self.menu_screen = "main"
        self.stage = stage
        self.stage_transition = None
        self.player = Player(BASE_WIDTH // 2, BASE_HEIGHT - 95)
        self.player.sounds = self.sounds
        self.score = 0
        self.explosions = []
        self.life_thresholds = [(1337, False), (8086, False)]
        self.input_grace = 0.4
        self.cheat_buffer = ""
        self.cheat_msg = t("cheat_stage").format(n=stage)
        self.cheat_kind = "stage"
        self.cheat_msg_timer = 5.0
        self.used_cheat = True
        self.bosses_defeated = max(0, (stage - 1) // 5)
        self._setup_stage(stage)

    # --- High-score entry / table ---
    def _begin_highscore_flow(self):

        self.hs_entries = load_highscores()
        self.hs_submitted = False
        self.hs_name = ["A", "A", "A"]
        self.hs_char_index = 0
        self.shake_amount = 0.0
        self.explosions.clear()  # remove explosion remnants from HS screen
        self.hs_queue = []
        self.hs_slot_label = 1
        block = (self.difficulty == "novice"
                 or getattr(self, "used_cheat", False)
                 or getattr(self, "phenix_cheat", False))
        if self.hotseat and self.slots[0] and self.slots[1]:
            # Show last player's score as default; queue every qualifying run
            self.score = max(self.slots[0]["score"], self.slots[1]["score"])
            if not block:
                for i, sl in enumerate(self.slots):
                    if sl and is_highscore(sl["score"], self.hs_entries):
                        self.hs_queue.append(i)
            if self.hs_queue:
                self._hs_prepare_entry(self.hs_queue.pop(0))
            else:
                self.hs_phase = "table"
            return
        if getattr(self, "play_mode", "solo") == "coop":
            # One entry per player — ship icon matches that score only
            ranked = sorted(self._ships(), key=lambda s: getattr(s, "score", 0), reverse=True)
            if ranked:
                self.score = getattr(ranked[0], "score", 0)
            self.hs_coop_queue = []
            if not block:
                for p in ranked:
                    if is_highscore(getattr(p, "score", 0), self.hs_entries):
                        self.hs_coop_queue.append(p)
            if self.hs_coop_queue:
                self._hs_prepare_coop_entry(self.hs_coop_queue.pop(0))
            else:
                self.hs_phase = "table"
            return
        # Novice / cheat: view table only, no name entry
        if block:
            self.hs_phase = "table"
        elif is_highscore(self.score, self.hs_entries):
            self.hs_ship = getattr(self.player, "ship_id", "phoenix")
            self.hs_phase = "enter"
        else:
            self.hs_phase = "table"

    def _hs_prepare_entry(self, slot_idx):
        sl = self.slots[slot_idx]
        self.score = sl["score"]
        self.hs_slot_label = slot_idx + 1
        p = sl.get("player")
        self.hs_ship = getattr(p, "ship_id", None) or self._ship_for_pid(slot_idx + 1)
        self.hs_name = ["A", "A", "A"]
        self.hs_char_index = 0
        self.hs_submitted = False
        self.hs_phase = "enter"

    def _hs_prepare_coop_entry(self, ship):
        self.score = int(getattr(ship, "score", 0) or 0)
        self.hs_slot_label = int(getattr(ship, "pid", 1) or 1)
        self.hs_ship = getattr(ship, "ship_id", "phoenix")
        self.hs_name = ["A", "A", "A"]
        self.hs_char_index = 0
        self.hs_submitted = False
        self.hs_phase = "enter"

    def _submit_highscore(self):
        if self.hs_submitted:
            return
        name = "".join(self.hs_name)
        ship = getattr(self, "hs_ship", None) or getattr(self.player, "ship_id", None) or "phoenix"
        self.hs_entries = insert_score(
            name, self.score,
            coop=(getattr(self, "play_mode", "solo") == "coop"),
            ship=ship, ship2=None,
        )
        self.hs_submitted = True
        if self.hs_queue:
            self._hs_prepare_entry(self.hs_queue.pop(0))
        elif getattr(self, "hs_coop_queue", None):
            self._hs_prepare_coop_entry(self.hs_coop_queue.pop(0))
        else:
            self.hs_phase = "table"

    def _hs_cycle_letter(self, direction):
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        cur = self.hs_name[self.hs_char_index]
        idx = alphabet.find(cur)
        if idx < 0:
            idx = 0
        idx = (idx + direction) % len(alphabet)
        self.hs_name[self.hs_char_index] = alphabet[idx]



    def _bezel_asset_names(self, style=None):
        """Return (left_file, right_file) for a bezel style id."""
        style = style if style is not None else getattr(self, "bezel_style", "phoenix")
        mapping = {
            "phoenix": ("bezel_left.png", "bezel_right.png"),
            "tesla": ("bezel_tesla_left.png", "bezel_tesla_right.png"),
            "blue": ("bezel_blue_left.png", "bezel_blue_right.png"),
            "fire": ("bezel_fire_left.png", "bezel_fire_right.png"),
        }
        return mapping.get(style, (None, None))

    def _load_bezel_images(self):
        """Load left/right arcade bezel artwork for the current style."""
        self.bezel_left_img = None
        self.bezel_right_img = None
        style = getattr(self, "bezel_style", "phoenix")
        if style in (None, "", "off"):
            self._invalidate_present_cache()
            return
        left_name, right_name = self._bezel_asset_names(style)
        try:
            if left_name:
                lp = asset_path("sprites", left_name)
                if os.path.exists(lp):
                    self.bezel_left_img = pygame.image.load(lp).convert()
            if right_name:
                rp = asset_path("sprites", right_name)
                if os.path.exists(rp):
                    self.bezel_right_img = pygame.image.load(rp).convert()
            self._invalidate_present_cache()
        except Exception as e:
            print("Bezel images not loaded:", e)

    def _layout_viewport(self):
        """Center the 16:9 game area in the real window.

        Bezel art only in fullscreen on displays wider than 16:9.
        Windowed and borderless: never bezel (letterbox black only if needed).
        """
        if not getattr(self, "screen", None):
            return
        mode = getattr(self, "display_mode", "window")
        sw, sh = self.screen.get_size()
        # SCALED 16:9 canvas → no side band. Wider logical canvas → bezels fit.
        if getattr(self, "_gpu_backend", "") == "scaled" and sw <= BASE_WIDTH + 8:
            self.view_rect = pygame.Rect(0, 0, BASE_WIDTH, BASE_HEIGHT)
            self.bezel_active = False
            return
        if mode == "window" or sh <= 0 or sw <= 0:
            self.view_rect = pygame.Rect(0, 0, BASE_WIDTH, BASE_HEIGHT)
            self.bezel_active = False
            return

        scale = min(sw / float(BASE_WIDTH), sh / float(BASE_HEIGHT))
        gw = max(1, int(BASE_WIDTH * scale))
        gh = max(1, int(BASE_HEIGHT * scale))
        target_aspect = BASE_WIDTH / float(BASE_HEIGHT)
        if gw / float(max(1, gh)) > target_aspect:
            gw = max(1, int(gh * target_aspect))
        else:
            gh = max(1, int(gw / target_aspect))
        gx = max(0, (sw - gw) // 2)
        gy = max(0, (sh - gh) // 2)
        self.view_rect = pygame.Rect(gx, gy, gw, gh)

        aspect = sw / float(sh)
        style = getattr(self, "bezel_style", "phoenix")
        self.bezel_active = (
            mode == "fullscreen"
            and style not in (None, "", "off")
            and aspect > (16.0 / 9.0 + 0.02)
            and gx >= 40
        )

    def _init_bezel_stars(self):
        """Starfield particles for left/right bezel panels."""
        import random as _r
        self._bezel_stars = []
        if not getattr(self, "screen", None):
            return
        sw, sh = self.screen.get_size()
        for _ in range(120):
            self._bezel_stars.append({
                "x": _r.uniform(0, sw),
                "y": _r.uniform(0, sh),
                "s": _r.uniform(0.4, 2.2),
                "v": _r.uniform(12, 55),
                "a": _r.randint(80, 220),
            })

    def _update_bezel_stars(self, dt):
        if not self._bezel_stars:
            return
        sh = self.screen.get_height()
        for st in self._bezel_stars:
            st["y"] += st["v"] * dt
            if st["y"] > sh:
                st["y"] = -2
                st["x"] = __import__("random").uniform(0, self.screen.get_width())

    def _invalidate_present_cache(self):
        """Call when display mode / bezel style / window size changes."""
        self._bezel_blit_left = None
        self._bezel_blit_right = None
        self._bezel_cache_key = None
        self._present_size = None

    def _ensure_bezel_cache(self):
        """Scale bezel art once per panel size (not every frame)."""
        if not self.bezel_active:
            self._bezel_blit_left = None
            self._bezel_blit_right = None
            self._bezel_cache_key = None
            return
        sw, sh = self.screen.get_size()
        vr = self.view_rect
        left_w = max(0, vr.x)
        right_w = max(0, sw - vr.right)
        key = (left_w, right_w, sh, getattr(self, "bezel_style", "phoenix"), int(getattr(self, "monitor_index", 0) or 0))
        if key == getattr(self, "_bezel_cache_key", None):
            return
        self._bezel_cache_key = key
        self._bezel_blit_left = None
        self._bezel_blit_right = None

        def cover(img, panel_w, panel_h, align_right):
            if img is None or panel_w < 8 or panel_h < 8:
                return None
            iw, ih = img.get_width(), img.get_height()
            scale = max(panel_w / float(iw), panel_h / float(ih))
            tw = max(1, int(iw * scale))
            th = max(1, int(ih * scale))
            # Fast scale once; convert for faster blit
            scaled = pygame.transform.scale(img, (tw, th)).convert()
            # Same pixel format as the display → blit without conversion
            try:
                if getattr(self, "screen", None) is not None:
                    surf = pygame.Surface((panel_w, panel_h), 0, self.screen)
                else:
                    surf = pygame.Surface((panel_w, panel_h)).convert()
            except Exception:
                surf = pygame.Surface((panel_w, panel_h))
            if align_right:
                x = panel_w - tw
            else:
                x = 0
            y = (panel_h - th) // 2
            surf.blit(scaled, (x, y))
            return surf

        self._bezel_blit_left = cover(
            getattr(self, "bezel_left_img", None), left_w, sh, True
        )
        self._bezel_blit_right = cover(
            getattr(self, "bezel_right_img", None), right_w, sh, False
        )

    def _draw_arcade_bezels(self):
        """Blit cached left/right bezel panels (no per-frame scaling)."""
        if not self.bezel_active:
            return
        self._ensure_bezel_cache()
        vr = self.view_rect
        if self._bezel_blit_left is not None:
            self.screen.blit(self._bezel_blit_left, (0, 0))
        if self._bezel_blit_right is not None:
            self.screen.blit(self._bezel_blit_right, (vr.right, 0))

    def _flip_frame(self, shake_x=0, shake_y=0):
        """Present game_surface: SCALED 1:1, or CPU blit + cached bezels."""
        mode = getattr(self, "display_mode", "window")
        scr_size = self.screen.get_size()
        if getattr(self, "_present_size", None) != scr_size:
            self._present_size = scr_size
            self._layout_viewport()
            self._invalidate_present_cache()
        vr = getattr(self, "view_rect", pygame.Rect(0, 0, BASE_WIDTH, BASE_HEIGHT))
        gpu = getattr(self, "_gpu", None)
        if (
            gpu is not None and gpu.active
            and getattr(self, "_gpu_backend", "") == "scaled"
            and not self.bezel_active
        ):
            if gpu.present(self.game_surface, vr, None, None, None, (shake_x, shake_y)):
                return
        # CPU fallback (previous path)
        if mode == "window" and scr_size == (BASE_WIDTH, BASE_HEIGHT):
            self.screen.blit(self.game_surface, (shake_x, shake_y))
        elif self.bezel_active and vr.width > 0 and vr.height > 0:
            self._ensure_bezel_cache()
            if self._bezel_blit_left is not None:
                self.screen.blit(self._bezel_blit_left, (0, 0))
            if self._bezel_blit_right is not None:
                self.screen.blit(self._bezel_blit_right, (vr.right, 0))
            dest_x, dest_y = vr.x + shake_x, vr.y + shake_y
            if shake_x == 0 and shake_y == 0 and vr.width > 0:
                try:
                    dest = self.screen.subsurface(vr)
                    if vr.width == BASE_WIDTH and vr.height == BASE_HEIGHT:
                        dest.blit(self.game_surface, (0, 0))
                    else:
                        pygame.transform.scale(self.game_surface, (vr.width, vr.height), dest)
                except Exception:
                    self._present_game_scaled(vr, dest_x, dest_y)
            else:
                self.screen.fill((0, 0, 0), vr)
                self._present_game_scaled(vr, dest_x, dest_y)
        else:
            self.screen.fill((0, 0, 0))
            if vr.width > 0 and vr.height > 0:
                self._present_game_scaled(vr, vr.x + shake_x, vr.y + shake_y)
        pygame.display.flip()

    def _present_game_scaled(self, vr, dest_x, dest_y):
        """Scale logical canvas into the window game band."""
        if vr.width == BASE_WIDTH and vr.height == BASE_HEIGHT:
            self.screen.blit(self.game_surface, (dest_x, dest_y))
            return
        key = (vr.width, vr.height)
        buf = getattr(self, "_scaled_game_buf", None)
        if buf is None or buf.get_size() != key:
            try:
                if self.screen is not None:
                    self._scaled_game_buf = pygame.Surface(key, 0, self.screen)
                else:
                    self._scaled_game_buf = pygame.Surface(key).convert()
            except Exception:
                self._scaled_game_buf = pygame.Surface(key)
            buf = self._scaled_game_buf
        pygame.transform.scale(self.game_surface, key, buf)
        self.screen.blit(buf, (dest_x, dest_y))

    def _prepare_monitor_env(self):
        """Set SDL window position for the selected monitor before set_mode."""
        try:
            import os
            mons = self._list_monitors()
            idx = int(getattr(self, "monitor_index", 0) or 0)
            if idx < 0 or idx >= len(mons):
                idx = 0
            m = mons[idx]
            mon_w, mon_h = int(m[1]), int(m[2])
            mon_x = int(m[3]) if len(m) >= 5 else 0
            mon_y = int(m[4]) if len(m) >= 5 else 0
            mode = getattr(self, "display_mode", "fullscreen")
            if mode == "window":
                x = mon_x + max(0, (mon_w - BASE_WIDTH) // 2)
                y = mon_y + max(0, (mon_h - BASE_HEIGHT) // 2)
            else:
                x, y = mon_x, mon_y
            os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x},{y}"
            os.environ["SDL_VIDEO_CENTERED"] = "0"
        except Exception as e:
            print("prepare monitor env:", e)

    def _list_monitors(self):
        """List monitors as (index, w, h, x, y).

        Index 0 is always the primary monitor (Windows) / first desktop size.
        User-facing "Moniteur 1" = index 0.
        """
        raw = self._query_monitors_raw()
        if not raw:
            info = pygame.display.Info()
            w = int(getattr(info, "current_w", BASE_WIDTH) or BASE_WIDTH)
            h = int(getattr(info, "current_h", BASE_HEIGHT) or BASE_HEIGHT)
            raw = [(max(BASE_WIDTH, w), max(BASE_HEIGHT, h), 0, 0, True)]
        # Primary first, then left-to-right
        raw.sort(key=lambda m: (0 if m[4] else 1, m[2], m[3]))
        out = []
        for i, (w, h, x, y, _prim) in enumerate(raw):
            out.append((i, int(w), int(h), int(x), int(y)))
        return out

    def _query_monitors_raw(self):
        """Return list of (w, h, x, y, is_primary)."""
        # Prefer Win32 for accurate primary + origins
        try:
            import sys
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes

                class RECT(ctypes.Structure):
                    _fields_ = [
                        ("left", wintypes.LONG),
                        ("top", wintypes.LONG),
                        ("right", wintypes.LONG),
                        ("bottom", wintypes.LONG),
                    ]

                class MONITORINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.DWORD),
                        ("rcMonitor", RECT),
                        ("rcWork", RECT),
                        ("dwFlags", wintypes.DWORD),
                    ]

                MONITORINFOF_PRIMARY = 1
                rects = []
                MONITORENUMPROC = ctypes.WINFUNCTYPE(
                    ctypes.c_int,
                    wintypes.HMONITOR,
                    wintypes.HDC,
                    ctypes.POINTER(RECT),
                    wintypes.LPARAM,
                )

                def _cb(hmon, hdc, lprect, lparam):
                    try:
                        mi = MONITORINFO()
                        mi.cbSize = ctypes.sizeof(MONITORINFO)
                        if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                            r = mi.rcMonitor
                            w = int(r.right - r.left)
                            h = int(r.bottom - r.top)
                            x, y = int(r.left), int(r.top)
                            prim = bool(mi.dwFlags & MONITORINFOF_PRIMARY)
                            rects.append((w, h, x, y, prim))
                    except Exception:
                        pass
                    return 1

                cb = MONITORENUMPROC(_cb)
                self._mon_enum_cb = cb
                ctypes.windll.user32.EnumDisplayMonitors(None, None, cb, 0)
                if rects:
                    return rects
        except Exception as e:
            print("Win32 monitor query:", e)

        # Fallback: pygame sizes only (primary = index 0)
        try:
            sizes = list(pygame.display.get_desktop_sizes())
        except Exception:
            sizes = []
        out = []
        for i, (w, h) in enumerate(sizes):
            out.append((int(w), int(h), 0, 0, i == 0))
        return out

    def _monitor_origins(self, count):
        """Compat helper — origins from _list_monitors order."""
        mons = self._list_monitors()
        origins = [(m[3], m[4]) for m in mons]
        while len(origins) < count:
            origins.append((0, 0))
        return origins[:count]

    def _pick_monitor(self):
        """Return (index, width, height, x, y). Default = monitor 1 (index 0, primary)."""
        mons = self._list_monitors()
        idx = int(getattr(self, "monitor_index", 0) or 0)
        if idx < 0 or idx >= len(mons):
            self.monitor_index = 0
            return mons[0]
        return mons[idx]

    def _pick_monitor_size(self):
        m = self._pick_monitor()
        return m[1], m[2]

    def _reset_video(self):
        """Drop the SDL window so the next set_mode can create a fresh renderer."""
        self.screen = None
        self._present_size = None
        self._scaled_game_buf = None
        try:
            self._invalidate_present_cache()
        except Exception:
            pass
        try:
            pygame.display.quit()
        except Exception:
            pass
        try:
            pygame.display.init()
        except Exception:
            pass

    def _open_display(self):
        """Create the display surface once (or recreate on Options change)."""
        recreating = bool(getattr(self, "_display_ready", False))
        if recreating:
            try:
                if getattr(self, "screen", None) is not None:
                    self.screen.fill((0, 0, 0))
                    pygame.display.flip()
            except Exception:
                pass
            show_cover()
            self._reset_video()
        try:
            mon = self._pick_monitor()
            mon_i = int(mon[0])
            mon_w, mon_h = int(mon[1]), int(mon[2])
            mon_x = int(mon[3]) if len(mon) >= 5 else 0
            mon_y = int(mon[4]) if len(mon) >= 5 else 0
        except Exception as e:
            print("pick monitor failed:", e)
            mon_i, mon_w, mon_h, mon_x, mon_y = 0, BASE_WIDTH, BASE_HEIGHT, 0, 0

        base_flags = pygame.DOUBLEBUF | pygame.HWSURFACE
        mode = getattr(self, "display_mode", "fullscreen")

        def _set(size, flags, display=None):
            # SCALED must not keep display= after a CPU fullscreen: SDL then
            # fails with "failed to create renderer" and stays stuck on CPU.
            last = None
            if display is not None and not (flags & getattr(pygame, "SCALED", 0)):
                try:
                    return pygame.display.set_mode(size, flags, display=int(display))
                except TypeError:
                    pass
                except pygame.error as e:
                    last = e
                    print("set_mode(display=) failed:", e)
            want_vs = 1 if getattr(self, "vsync_mode", "adaptive") == "on" else 0
            try:
                import os
                os.environ["SDL_RENDER_VSYNC"] = "1" if want_vs else "0"
            except Exception:
                pass
            import warnings
            def _mode(vs):
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=".*vsync.*")
                    try:
                        return pygame.display.set_mode(size, flags, vsync=vs)
                    except TypeError:
                        return pygame.display.set_mode(size, flags)
            try:
                return _mode(want_vs)
            except pygame.error as e:
                last = e
                print("set_mode failed:", e)
            self._reset_video()
            try:
                return _mode(0)
            except pygame.error:
                return pygame.display.set_mode(size, flags)

        # Position hint for the next window
        try:
            import os
            if mode == "window":
                px = mon_x + max(0, (mon_w - BASE_WIDTH) // 2)
                py = mon_y + max(0, (mon_h - BASE_HEIGHT) // 2)
            else:
                px, py = mon_x, mon_y
            os.environ["SDL_VIDEO_WINDOW_POS"] = f"{px},{py}"
            os.environ["SDL_VIDEO_CENTERED"] = "0"
        except Exception:
            pass

        want_bezel = (
            mode == "fullscreen"
            and getattr(self, "bezel_style", "phoenix") not in (None, "", "off")
            and mon_h > 0
            and (mon_w / float(mon_h)) > (16.0 / 9.0 + 0.02)
        )
        # SCALED with bezels: logical size matches monitor aspect (e.g. 1707x720
        # on 2560x1080). Game 1:1 in the center, panels on the sides, SDL GPU
        # stretches the whole frame. No OpenGL.
        use_gpu = (
            bool(getattr(self, "gpu_present", True))
            and hasattr(pygame, "SCALED")
        )
        self._gpu_backend = "cpu"
        try:
            opened = False
            if use_gpu:
                sc = pygame.SCALED | pygame.DOUBLEBUF
                if mode == "fullscreen":
                    sc |= pygame.FULLSCREEN
                elif mode == "borderless":
                    sc |= pygame.NOFRAME
                try:
                    # Small logical canvas. SDL SCALED GPU-stretches it.
                    # Native 2560x1080 + SCALED was slower than CPU (40 vs 60).
                    if want_bezel and mode == "fullscreen" and mon_h > 0:
                        lw = max(BASE_WIDTH, int(round(BASE_HEIGHT * mon_w / float(mon_h))))
                        gpu_size = (lw, BASE_HEIGHT)
                    else:
                        gpu_size = (BASE_WIDTH, BASE_HEIGHT)
                    self.screen = _set(gpu_size, sc, mon_i)
                    self._gpu_backend = "scaled"
                    opened = True
                except pygame.error:
                    print("SCALED set_mode failed, CPU path")
                    use_gpu = False
            if not opened:
              if mode == "window":
                self.screen = _set((BASE_WIDTH, BASE_HEIGHT), base_flags, mon_i)
              elif mode == "borderless":
                self.screen = _set((mon_w, mon_h), base_flags | pygame.NOFRAME, mon_i)
              else:
                try:
                    self.screen = _set(
                        (mon_w, mon_h), base_flags | pygame.FULLSCREEN, mon_i
                    )
                except pygame.error:
                    try:
                        self.screen = _set(
                            (0, 0), base_flags | pygame.FULLSCREEN, mon_i
                        )
                    except pygame.error:
                        self.display_mode = "window"
                        self.screen = _set((BASE_WIDTH, BASE_HEIGHT), base_flags, mon_i)
        except Exception as e:
            print("open display failed, windowed fallback:", e)
            import traceback
            traceback.print_exc()
            self.display_mode = "window"
            self.screen = pygame.display.set_mode(
                (BASE_WIDTH, BASE_HEIGHT), base_flags
            )

        try:
            pygame.mouse.set_visible(self.display_mode == "window")
        except Exception:
            pass
        try:
            if getattr(self, "game_surface", None) is not None:
                self.game_surface = self.game_surface.convert()
        except Exception:
            pass
        self._bind_gpu()
        self._update_caption()
        try:
            if getattr(self, "screen", None) is not None:
                self.screen.fill((0, 0, 0))
                pygame.display.flip()
        except Exception:
            pass
        hide_cover()
        try:
            pygame.event.clear()
            pygame.event.pump()
        except Exception:
            pass
        self._refocus_game_window()
        self._rebind_joystick()
        try:
            self.panel_hz = int(detect_refresh_rate() or 60)
            self.fps_target = int(getattr(self, "fps_cap", 120) or 120)
            import settings as _settings
            _settings.FPS_TARGET = self.fps_target
            print("panel:", self.panel_hz, "Hz  cap:", self.fps_target, "Hz  vsync:", getattr(self, "vsync_mode", "?"))
        except Exception:
            pass
        try:
            pygame.event.clear()
        except Exception:
            pass

    def _refocus_game_window(self):
        """Put the new SDL window back in front so the pad keeps sending events."""
        try:
            pygame.event.pump()
        except Exception:
            pass
        if os.name != "nt":
            return
        try:
            import ctypes
            info = pygame.display.get_wm_info() or {}
            hwnd = info.get("window")
            if not hwnd:
                return
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
            pygame.event.pump()
        except Exception as e:
            print("refocus window:", e)

    def _rebind_joystick(self):
        """Joystick instance dies with the old SDL window — reopen it."""
        keep_pad = getattr(self, "input_mode", "keyboard") == "gamepad"
        # Do NOT joystick.quit() — that poisons event.get() with KeyError: 0
        try:
            pygame.joystick.init()
        except Exception:
            pass
        self.joystick = None
        self.joysticks = []
        try:
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                self.gamepad_detected = True
                if keep_pad:
                    self.input_mode = "gamepad"
            elif keep_pad:
                # device still there next pump; don't flip to keyboard
                self.gamepad_detected = True
        except Exception as e:
            print("rebind joystick:", e)
        try:
            if getattr(self, "play_mode", "") == "coop" and getattr(self, "player2", None):
                b1, b2 = self._coop_bindings()
                self.player.input_scheme = b1[0]
                self.player2.input_scheme = b2[0]
                self.player._joy = b1[1]
                self.player2._joy = b2[1]
                if b1[0] == "pad":
                    self.joystick = b1[1]
            elif getattr(self, "player", None) is not None:
                self.player._joy = self.joystick
        except Exception:
            pass

    def _bind_gpu(self):
        """(Re)bind the SDL2 GPU presenter to the current window."""
        gpu = getattr(self, "_gpu", None)
        if gpu is None:
            return
        want = (
            bool(getattr(self, "gpu_present", True))
            and getattr(self, "_gpu_backend", "") == "scaled"
        )
        gpu.bind(want)

    def _update_caption(self):
        try:
            gpu = getattr(self, "_gpu", None)
            backend = getattr(self, "_gpu_backend", "")
            if backend == "gl":
                tag = "GPU-GL"
            elif backend == "scaled" or (gpu is not None and gpu.active):
                tag = "GPU"
            else:
                tag = "CPU"
            title = f"Phenix Rebirth  [{getattr(self, 'fps_target', FPS_TARGET)} Hz · {tag}]"
            pygame.display.set_caption(title)
            if gpu is not None:
                gpu.set_title(title)
        except Exception:
            pass

    def apply_display_mode(self):
        """Apply window/fullscreen/borderless from Options (safe recreate)."""
        try:
            self._prepare_monitor_env()
            self._open_display()
        except Exception as e:
            print("apply_display_mode failed:", e)
            import traceback
            traceback.print_exc()
            try:
                self.display_mode = "window"
                self.screen = pygame.display.set_mode(
                    (BASE_WIDTH, BASE_HEIGHT), pygame.DOUBLEBUF | pygame.HWSURFACE
                )
            except Exception as e2:
                print("windowed fallback failed:", e2)
                return

        try:
            pygame.display.set_caption(f"Phenix Rebirth  [{getattr(self, 'fps_target', 60)} Hz]")
            pygame.mouse.set_visible(self.display_mode == "window")
        except Exception:
            pass

        self._scaled_cache = None
        self._scaled_cache_size = None
        self._scaled_game_buf = None
        self._present_size = None
        try:
            self._invalidate_present_cache()
        except Exception:
            pass
        try:
            self._layout_viewport()
        except Exception as e:
            print("layout failed:", e)
        try:
            if getattr(self, "game_surface", None) is not None:
                self.game_surface = self.game_surface.convert()
        except Exception:
            pass
        try:
            if getattr(self, "bezel_active", False):
                self._ensure_bezel_cache()
        except Exception as e:
            print("bezel rebuild failed:", e)
        self._bezel_stars = []

    def _poll_gamepad(self):
        """Hot-plug detection while on menus (and soft recovery in-game)."""
        count = pygame.joystick.get_count()
        if count > 0:
            if self.joystick is None:
                try:
                    self.joystick = pygame.joystick.Joystick(0)
                    self.joystick.init()
                    self.gamepad_detected = True
                    # First detection on menus → default to gamepad if still on auto feel
                    if not self.started and not self.game_over:
                        # Newly plugged on menu → switch to gamepad
                        self.input_mode = "gamepad"
                        self.save_settings()
                except Exception:
                    self.joystick = None
                    self.gamepad_detected = False
            else:
                self.gamepad_detected = True
        else:
            self.joystick = None
            if self.gamepad_detected:
                self.gamepad_detected = False
                if self.input_mode == "gamepad":
                    self.input_mode = "keyboard"

    def save_settings(self):

        save_user_settings({
            "input_mode": self.input_mode,
            "display_mode": self.display_mode,
            "bezel_style": getattr(self, "bezel_style", "phoenix"),
            "monitor_index": int(getattr(self, "monitor_index", 0) or 0),
            "sfx_volume": self.sfx_volume,
            "music_volume": self.music_volume,
            "rumble_level": int(getattr(self, "rumble_level", 3)),
            "autofire": bool(getattr(self, "autofire", True)),
            "language": self.language,
            "show_fps": self.show_fps,
            "scanlines": int(getattr(self, "scanlines", 0) or 0),
            "gpu_present": bool(getattr(self, "gpu_present", True)),
            "vsync_mode": getattr(self, "vsync_mode", "adaptive"),
            "fps_cap": int(getattr(self, "fps_cap", 120) or 120),
            "ship_id": getattr(self, "ship_id", "phoenix"),
            "ship_id_p2": getattr(self, "ship_id_p2", "phoenix"),
        })

    # --- Menu navigation ---
    def _is_menu_up(self, key):
        # W = QWERTY, Z = AZERTY (ZQSD)
        return key in (pygame.K_UP, pygame.K_w, pygame.K_z)

    def _is_menu_down(self, key):
        return key in (pygame.K_DOWN, pygame.K_s)

    def _is_menu_confirm(self, key):
        # Enter, Space and fire keys all validate
        return key in (
            pygame.K_RETURN, pygame.K_KP_ENTER,
            pygame.K_SPACE, pygame.K_LCTRL, pygame.K_RCTRL,
        )

    def _menu_nav(self, direction):
        """direction: -1 up, +1 down"""
        if self.menu_screen == "ship_select":
            self.ship_select_index = (int(getattr(self, "ship_select_index", 0)) + direction) % 2
            return
        if self.menu_screen == "jukebox":
            n = len(self._juke_catalog())
            self.juke_index = (int(getattr(self, "juke_index", 0) or 0) + direction) % n
            return
        if self.menu_screen == "main":
            n = 7  # Jouer, mode, diff, Options, HS, Credits, Quitter
        elif self.menu_screen == "reset_confirm":
            n = 2  # Oui, Non
        else:
            n = len(self._options_spec())
        self.menu_index = (self.menu_index + direction) % n


    def _credits_scroll_axis(self):
        """-1 down (faster forward), +1 up (reverse), 0 idle."""
        down = up = False
        try:
            keys = pygame.key.get_pressed()
            down = bool(keys[pygame.K_DOWN] or keys[pygame.K_s])
            up = bool(keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_z])
        except Exception:
            pass
        joy = getattr(self, "joystick", None)
        if joy is not None:
            try:
                if joy.get_numhats() > 0:
                    hat = joy.get_hat(0)
                    if hat[1] < 0:
                        down = True
                    elif hat[1] > 0:
                        up = True
                if joy.get_numaxes() > 1:
                    ay = joy.get_axis(1)
                    if ay > 0.45:
                        down = True
                    elif ay < -0.45:
                        up = True
            except Exception:
                pass
        if up and not down:
            return 1
        if down and not up:
            return -1
        return 0

    def _credits_x_axis(self):
        """-1 left, +1 right, 0 idle. Analog stick is proportional."""
        v = 0.0
        try:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT] or keys[pygame.K_a] or keys[pygame.K_q]:
                v -= 1.0
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                v += 1.0
        except Exception:
            pass
        joy = getattr(self, "joystick", None)
        if joy is not None:
            try:
                if joy.get_numhats() > 0:
                    hat = joy.get_hat(0)
                    if hat[0] < 0:
                        v -= 1.0
                    elif hat[0] > 0:
                        v += 1.0
                if joy.get_numaxes() > 0:
                    raw = float(joy.get_axis(0))
                    if abs(raw) > 0.18:
                        v += max(-1.0, min(1.0, raw))
            except Exception:
                pass
        return max(-1.0, min(1.0, v))

    def _focus_option(self, name):
        spec = self._options_spec()
        self.menu_index = spec.index(name) if name in spec else 0



    def _wrap_ui(self, text, font, max_w):
        words = (text or "").split()
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if font.size(trial)[0] <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines or [""]

    def _draw_option_help(self, key, box=(700, 148, 520, 420)):
        """Right-hand hint panel for the focused option."""
        if not key or key not in (
            "control", "autofire", "sfx", "music", "audio_mix", "ingame_music", "rumble", "display",
            "bezel", "fps", "scanlines", "gpu", "vsync", "hz",
            "language", "reset_hs", "back",
        ):
            return
        x, y, w, h = box
        cache = getattr(self, "_opt_help_cache", None)
        if cache is None:
            cache = self._opt_help_cache = {}
        ckey = (key, get_lang(), w, h)
        panel = cache.get(ckey)
        if panel is None:
            panel = pygame.Surface((w, h), pygame.SRCALPHA)
            panel.fill((8, 8, 22, 170))
            pygame.draw.rect(panel, (180, 140, 255), panel.get_rect(), 2, border_radius=10)
            title = t({
                "control": "opt_control", "autofire": "opt_autofire", "sfx": "opt_sfx",
                "music": "opt_music", "audio_mix": "opt_audio", "rumble": "opt_rumble", "display": "opt_display",
                "bezel": "opt_bezel", "fps": "opt_fps", "scanlines": "opt_scanlines",
                "gpu": "opt_gpu", "vsync": "opt_vsync", "hz": "opt_hz",
                "language": "opt_language", "reset_hs": "opt_reset_hs", "back": "opt_back",
            }.get(key, "options"))
            hdr = self._txt(self.font, title, (255, 210, 140))
            panel.blit(hdr, (18, 14))
            body = t("opt_help_" + key)
            yy = 52
            for line in self._wrap_ui(body, self.font, w - 36):
                surf = self._txt(self.font, line, (200, 200, 230))
                panel.blit(surf, (18, yy))
                yy += 26
            cache[ckey] = panel
        self.game_surface.blit(panel, (x, y))

    def _options_labels(self):
        """Human-readable option rows matching _options_spec order."""
        mode_labels = {
            "window": t("disp_window"),
            "fullscreen": t("disp_fullscreen"),
            "borderless": t("disp_borderless"),
        }
        ctrl = t("ctrl_pad") if self.input_mode == "gamepad" else t("ctrl_kb")
        vol_pct = int(round(self.sfx_volume * 100))
        mus_pct = int(round(self.music_volume * 100))
        disp = mode_labels.get(self.display_mode, self.display_mode)
        fps_label = t("yes") if self.show_fps else t("no")
        sl = int(getattr(self, "scanlines", 0) or 0)
        scan_label = t("no") if sl <= 0 else f"{t('opt_scanlines')} {sl}"
        lang_label = next((n for c, n in LANGS if c == self.language), self.language)
        bezel_keys = {s[0]: s[1] for s in getattr(self, "BEZEL_STYLES", [("off", "bezel_off"), ("phoenix", "bezel_phoenix")])}
        bezel_label = t(bezel_keys.get(getattr(self, "bezel_style", "phoenix"), "bezel_phoenix"))
        mapping = {
            "control": f"{t('opt_control')} :  <  {ctrl}  >",
            "autofire": f"{t('opt_autofire')} :  <  {t('yes') if getattr(self, 'autofire', True) else t('no')}  >",
            "sfx": f"{t('opt_sfx')} :  <  {vol_pct}%  >",
            "music": f"{t('opt_music')} :  <  {mus_pct}%  >",
            "audio_mix": f"{t('opt_audio')} :  <  {t('audio_' + getattr(self, 'audio_mix', 'sfx'))}  >",
            "ingame_music": f"{t('opt_ingame_music') if False else 'Musique en jeu'} :  <  {ingame_label(getattr(self, 'ingame_music', 'none'), t, asset_path)}  >",
            "rumble": f"{t('opt_rumble')} :  <  {int(getattr(self, 'rumble_level', 3))} / 5  >",
            "display": f"{t('opt_display')} :  <  {disp}  >",
            "bezel": f"{t('opt_bezel')} :  <  {bezel_label}  >",
            "fps": f"{t('opt_fps')} :  <  {fps_label}  >",
            "scanlines": f"{t('opt_scanlines')} :  <  {('OFF' if sl <= 0 else str(sl))}  >",
            "gpu": f"{t('opt_gpu')} :  <  {t('yes') if getattr(self, 'gpu_present', True) else t('no')}  >",
            "vsync": f"{t('opt_vsync')} :  <  {t('vsync_' + getattr(self, 'vsync_mode', 'adaptive'))}  >",
            "hz": f"{t('opt_hz')} :  <  {int(getattr(self, 'fps_cap', 120))} Hz  >",
            "language": f"{t('opt_language')} :  <  {lang_label}  >",
            "reset_hs": t("opt_reset_hs"),
            "back": t("opt_back"),
        }
        return [mapping[k] for k in self._options_spec() if k in mapping]

    def _options_spec(self):
        """Ordered option ids (bezel / monitor only when relevant)."""
        items = ["control", "autofire", "sfx", "music", "audio_mix", "ingame_music", "rumble", "display"]
        mode = getattr(self, "display_mode", "fullscreen")
        if mode == "fullscreen":
            items.append("bezel")
        items.extend(["fps", "scanlines", "gpu", "vsync", "hz", "language", "reset_hs", "back"])
        return items

    def _menu_adjust(self, direction):
        """direction: -1 left, +1 right — change current option value"""
        if self.menu_screen == "ship_select":
            self.ship_select_index = (int(getattr(self, "ship_select_index", 0)) + direction) % 2
            return
        if self.menu_screen == "main":
            if self.menu_index == 1:
                modes = getattr(self, "PLAY_MODES", ["solo", "hotseat", "coop"])
                cur = getattr(self, "play_mode", "solo")
                idx = modes.index(cur) if cur in modes else 0
                self.play_mode = modes[(idx + direction) % len(modes)]
            elif self.menu_index == 2:
                idx = self.DIFFICULTIES.index(self.difficulty)
                self.difficulty = self.DIFFICULTIES[(idx + direction) % len(self.DIFFICULTIES)]
            return
        if self.menu_screen != "options":
            return
        spec = self._options_spec()
        if self.menu_index < 0 or self.menu_index >= len(spec):
            return
        key = spec[self.menu_index]
        if key == "control":
            self.input_mode = "keyboard" if self.input_mode == "gamepad" else "gamepad"
            if self.input_mode == "gamepad" and not self.gamepad_detected:
                self.input_mode = "keyboard"
            self.save_settings()
        elif key == "autofire":
            self.autofire = not bool(getattr(self, "autofire", True))
            self.save_settings()
        elif key == "sfx":
            self.sfx_volume = max(0.0, min(1.0, self.sfx_volume + direction * 0.1))
            self.sounds.set_master_volume(self.sfx_volume)
            self.sounds.play("shoot")
            self.save_settings()
        elif key == "music":
            self.music_volume = max(0.0, min(1.0, self.music_volume + direction * 0.1))
            self.sounds.set_music_volume(self.music_volume)
            self.save_settings()
        elif key == "audio_mix":
            modes = getattr(self, "AUDIO_MIXES", ["sfx", "sfx_music", "music", "off"])
            cur = getattr(self, "audio_mix", "sfx")
            i = modes.index(cur) if cur in modes else 0
            self.audio_mix = modes[(i + direction) % len(modes)]
            self._apply_audio_mix()

        elif key == "ingame_music":
            self.ingame_music = ingame_cycle(getattr(self, "ingame_music", "none"), direction)

        elif key == "rumble":
            self.rumble_level = max(0, min(5, int(getattr(self, "rumble_level", 3)) + direction))
            if self.player:
                self.player.rumble_level = self.rumble_level
                self.player._joy = self.joystick
                self.player._rumble_enabled = True
                if self.rumble_level > 0:
                    self.player.rumble(0.35, 0.55, 180)
            self.save_settings()
        elif key == "display":
            modes = ["window", "fullscreen", "borderless"]
            idx = modes.index(self.display_mode) if self.display_mode in modes else 0
            self.display_mode = modes[(idx + direction) % len(modes)]
            self.apply_display_mode()
            self.menu_index = min(self.menu_index, len(self._options_spec()) - 1)
            self.save_settings()
        elif key == "bezel":
            styles = [s[0] for s in getattr(self, "BEZEL_STYLES", [("off", ""), ("phoenix", "")])]
            cur = getattr(self, "bezel_style", "phoenix")
            idx = styles.index(cur) if cur in styles else 0
            self.bezel_style = styles[(idx + direction) % len(styles)]
            self.save_settings()
            self._load_bezel_images()
            self._open_display()
            self._invalidate_present_cache()
            self._layout_viewport()
            if self.bezel_active:
                self._ensure_bezel_cache()
            self._update_caption()
        elif key == "fps":
            self.show_fps = not self.show_fps
            self.save_settings()
        elif key == "scanlines":
            cur = int(getattr(self, "scanlines", 0) or 0)
            self.scanlines = (cur + direction) % 4  # 0..3
            self._scanline_surf = None  # rebuild overlay
            self._scanline_level_cached = None
            self.save_settings()
        elif key == "gpu":
            self.gpu_present = not bool(getattr(self, "gpu_present", True))
            self.save_settings()
            self._open_display()
        elif key == "vsync":
            modes = ["on", "adaptive", "off"]
            cur = getattr(self, "vsync_mode", "adaptive")
            i = modes.index(cur) if cur in modes else 1
            self.vsync_mode = modes[(i + direction) % len(modes)]
            self.save_settings()
            self._open_display()
        elif key == "hz":
            caps = [60, 75, 120]
            cur = int(getattr(self, "fps_cap", 120) or 120)
            i = caps.index(cur) if cur in caps else 2
            self.fps_cap = caps[(i + direction) % len(caps)]
            self.fps_target = self.fps_cap
            self.save_settings()
            self._update_caption()
            self._invalidate_present_cache()
            self._layout_viewport()
            self._update_caption()
        elif key == "language":
            idx = LANG_CODES.index(self.language) if self.language in LANG_CODES else 0
            self.language = LANG_CODES[(idx + direction) % len(LANG_CODES)]
            set_lang(self.language)
            self.text_cache.clear()
            self._opt_help_cache = {}
            self._credits_layout_cache = None
            self.save_settings()

    def _txt(self, font, text, color):
        """Cached SysFont raster — menus used to re-render every frame."""
        return self.text_cache.get(font, text, color)

    def _dim_overlay(self, alpha=180):
        """Reuse a full-screen dim layer (avoid 1280×720 alloc every frame)."""
        cache = getattr(self, "_dim_overlays", None)
        if cache is None:
            cache = self._dim_overlays = {}
        surf = cache.get(alpha)
        if surf is None:
            surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
            surf.fill((0, 0, 0, int(alpha)))
            cache[alpha] = surf
        return surf

    def _credits_layout(self):
        """Cached credits lines + row heights (language / logo size)."""
        logo_h = self.logo_frames[0].get_height() if self.logo_frames else 56
        lang = get_lang()
        pack = getattr(self, "_credits_layout_cache", None)
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
        self._credits_layout_cache = (lang, logo_h, lines, heights, total)
        return lines, heights, total

    def _draw_logo(self, surface, center_x, top_y):
        """Draw current animated logo frame centered horizontally."""
        if not self.logo_frames:
            return False
        img = self.logo_frames[self.logo_index % len(self.logo_frames)]
        surface.blit(img, (center_x - img.get_width() // 2, top_y))
        return True

    def _draw_boss_flag(self, surface, x, y, big=False):

        """Victory flag next to stage number. big=True at 10+ bosses."""
        if big:
            pygame.draw.line(surface, (220, 220, 230), (x, y + 28), (x, y), 3)
            pygame.draw.polygon(surface, (220, 40, 50), [
                (x + 2, y), (x + 24, y + 8), (x + 2, y + 16)
            ])
            pygame.draw.polygon(surface, (255, 140, 100), [
                (x + 2, y + 2), (x + 18, y + 8), (x + 2, y + 12)
            ])
            # star mark
            pygame.draw.circle(surface, (255, 220, 80), (x + 8, y + 8), 3)
        else:
            pygame.draw.line(surface, (200, 200, 210), (x, y + 14), (x, y), 2)
            pygame.draw.polygon(surface, (220, 50, 60), [
                (x + 1, y), (x + 12, y + 4), (x + 1, y + 8)
            ])
            pygame.draw.polygon(surface, (255, 120, 100), [
                (x + 1, y + 1), (x + 9, y + 4), (x + 1, y + 6)
            ])

    # --- Help attract-mode icons ---
    def _build_help_icons(self):

        """Sprites for the help screen score table."""
        from enemy import Enemy, BigBird
        e1 = Enemy(0, 0, stage=1)
        e2 = Enemy(0, 0, stage=2)
        g3 = BigBird(0, 0, stage=3)
        g4 = BigBird(0, 0, stage=4)
        self.help_icons = {
            "bird1": e1,
            "bird2": e2,
            "garg3": g3,
            "garg4": g4,
        }
        boss_frames = []
        ch = 36
        for i in range(4):
            path = asset_path("sprites", f"boss_core_{i:02d}.png")
            if not os.path.isfile(path):
                continue
            try:
                core_img = pygame.image.load(path).convert_alpha()
                scale = ch / max(1, core_img.get_height())
                cw = max(1, int(core_img.get_width() * scale))
                boss_frames.append(pygame.transform.smoothscale(core_img, (cw, ch)))
            except Exception:
                pass
        if not boss_frames:
            try:
                core_img = pygame.image.load(asset_path("sprites", "boss_core.png")).convert_alpha()
                scale = ch / max(1, core_img.get_height())
                cw = max(1, int(core_img.get_width() * scale))
                boss_frames.append(pygame.transform.smoothscale(core_img, (cw, ch)))
            except Exception:
                core = pygame.Surface((36, 40), pygame.SRCALPHA)
                pygame.draw.ellipse(core, (40, 90, 70), (4, 4, 28, 32))
                boss_frames.append(core)
        self.help_icons["boss_frames"] = boss_frames
        self.help_icons["boss"] = boss_frames[0]
        # Ship + Phenix form for help page 2
        try:
            ship = pygame.image.load(asset_path("sprites", "player_ship.png")).convert_alpha()
            sh = 72
            scale = sh / max(1, ship.get_height())
            sw = max(1, int(ship.get_width() * scale))
            self.help_icons["ship"] = pygame.transform.smoothscale(ship, (sw, sh))
        except Exception:
            self.help_icons["ship"] = None
        phenix_dir = asset_path("sprites", "phenix")
        frames = []
        for i in range(8):
            path = os.path.join(phenix_dir, f"phenix_{i:02d}.png")
            if not os.path.isfile(path):
                continue
            try:
                img = pygame.image.load(path).convert_alpha()
            except Exception:
                continue
            ph = 80
            scale = ph / max(1, img.get_height())
            pw = max(1, int(img.get_width() * scale))
            frames.append(pygame.transform.smoothscale(img, (pw, ph)))
        if not frames:
            for name in ("phenix_04.png", "morph_03.png", "phenix_00.png"):
                path = os.path.join(phenix_dir, name)
                if os.path.isfile(path):
                    try:
                        img = pygame.image.load(path).convert_alpha()
                        ph = 80
                        scale = ph / max(1, img.get_height())
                        pw = max(1, int(img.get_width() * scale))
                        frames.append(pygame.transform.smoothscale(img, (pw, ph)))
                        break
                    except Exception:
                        pass
        self.help_icons["phenix_frames"] = frames
        self.help_icons["phenix"] = frames[0] if frames else None
        try:
            shs = pygame.image.load(asset_path("sprites", "player_ship_shield.png")).convert_alpha()
            hh = 72
            sc = hh / max(1, shs.get_height())
            self.help_icons["ship_shield"] = pygame.transform.smoothscale(
                shs, (max(1, int(shs.get_width() * sc)), hh)
            )
        except Exception:
            self.help_icons["ship_shield"] = None
        sframes = []
        sdir = asset_path("sprites", "shield")
        if os.path.isdir(sdir):
            for name in ("loop_00.png", "loop_01.png", "loop_02.png", "loop_03.png"):
                path = os.path.join(sdir, name)
                if not os.path.isfile(path):
                    continue
                try:
                    img = pygame.image.load(path).convert_alpha()
                except Exception:
                    continue
                ph = 80
                sc = ph / max(1, img.get_height())
                sframes.append(pygame.transform.smoothscale(
                    img, (max(1, int(img.get_width() * sc)), ph)
                ))
        self.help_icons["shield_frames"] = sframes
        self.help_icons["shield"] = sframes[0] if sframes else None


    def _draw_help_page(self, surface, page, y_off):
        """Draw help page 0 (scenario/points) or 1 (PHENIX). y_off shifts content."""
        def yy(y):
            return int(y + y_off)

        title = self._txt(self.big_font, "PHENIX REBIRTH", (255, 120, 255))
        surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, yy(28)))
        sub = self._txt(self.font, t("subtitle"), (180, 160, 220))
        surface.blit(sub, (BASE_WIDTH // 2 - sub.get_width() // 2, yy(82)))

        if page <= 0:
            col_l = 48
            y = 120

            def hdr(txt, y):
                s = self._txt(self.medium_font, txt, (255, 200, 120))
                surface.blit(s, (col_l, yy(y)))
                return y + 34

            def body(txt, y):
                s = self._txt(self.font, txt, (200, 200, 230))
                surface.blit(s, (col_l, yy(y)))
                return y + 24

            y = hdr(t_help("scenario_h"), y)
            for line in t_list("scenario"):
                y = body(line, y)
            y += 10
            y = hdr(t_help("howto_h"), y)
            for line in t_list("howto"):
                y = body(line, y)
            y += 10
            y = hdr(t_help("controls_h"), y)
            for line in t_list("controls"):
                y = body(line, y)

            col_r = BASE_WIDTH // 2 + 90
            y = 120
            s = self._txt(self.medium_font, t_help("points_h"), (255, 200, 120))
            surface.blit(s, (col_r, yy(y)))
            y += 40
            score_rows = [
                ("bird1", t_help("enemy_s1"), "10"),
                ("bird2", t_help("enemy_s2"), "20"),
                ("garg3", t_help("enemy_s3"), "30"),
                ("garg4", t_help("enemy_s4"), "40"),
                ("boss", t_help("enemy_boss"), "200"),
            ]
            for key, label, pts in score_rows:
                ix, iy = col_r + 28, yy(y + 14)
                if key == "bird1" and "bird1" in self.help_icons:
                    self._draw_help_bird(surface, self.help_icons["bird1"], ix, iy, phase=0.0)
                elif key == "bird2" and "bird2" in self.help_icons:
                    self._draw_help_bird(surface, self.help_icons["bird2"], ix, iy, phase=1.7)
                elif key == "garg3" and "garg3" in self.help_icons:
                    self._draw_help_gargoyle(surface, self.help_icons["garg3"], ix, iy, 0.5)
                elif key == "garg4" and "garg4" in self.help_icons:
                    self._draw_help_gargoyle(surface, self.help_icons["garg4"], ix, iy, 0.5)
                elif key == "boss":
                    bframes = self.help_icons.get("boss_frames") or []
                    img = None
                    if bframes:
                        idx = int(getattr(self, "help_anim_t", 0.0) * 8.0) % len(bframes)
                        img = bframes[idx]
                    else:
                        img = self.help_icons.get("boss")
                    if img is not None:
                        surface.blit(img, (ix - img.get_width() // 2, iy - img.get_height() // 2))
                ls = self._txt(self.font, label, (200, 200, 230))
                surface.blit(ls, (col_r + 60, yy(y + 4)))
                ps = self._txt(self.font, pts + " " + t_help("pts"), (110, 255, 150))
                surface.blit(ps, (col_r + 60, yy(y + 26)))
                y += 54
            note = self._txt(self.font, t_help("vet_note"), (180, 160, 200))
            surface.blit(note, (col_r, yy(y + 2)))
            y += 26
            note2 = self._txt(self.font, t_help("bonus_lives"), (180, 160, 220))
            surface.blit(note2, (col_r, yy(y)))
        else:
            # Page 2 — Phenix (left) + Shield (right), same ship size
            def _fit(surf, box_h=90):
                if surf is None:
                    return None
                try:
                    r = surf.get_bounding_rect(min_alpha=24)
                except Exception:
                    r = surf.get_rect()
                if r.width < 2 or r.height < 2:
                    src = surf
                else:
                    src = surf.subsurface(r).copy()
                sc = box_h / max(1, src.get_height())
                return pygame.transform.smoothscale(
                    src, (max(1, int(src.get_width() * sc)), box_h)
                )

            body_font = getattr(self, "help_small", None)
            if body_font is None:
                try:
                    body_font = pygame.font.SysFont(
                        ("segoeui", "tahoma", "verdana", "arial"), 20, bold=True
                    )
                except Exception:
                    body_font = self.font
                self.help_small = body_font

            def _text_col(header, lines, hx, col_w, hcol, y0):
                s = self._txt(self.medium_font, header, hcol)
                surface.blit(s, (hx + (col_w - s.get_width()) // 2, yy(y0)))
                y = y0 + 36
                for line in lines:
                    for piece in self._wrap_ui(line, body_font, col_w):
                        ls = self._txt(body_font, piece, (210, 210, 235))
                        surface.blit(ls, (hx, yy(y)))
                        y += 20
                y += 8
                tip = self._txt(body_font, "Shift / X  ·  B", (255, 220, 120))
                surface.blit(tip, (hx + (col_w - tip.get_width()) // 2, yy(y)))
                return y + 22

            def _art_row(hx, col_w, art_left, art_right, hcol, art_y):
                left = _fit(art_left)
                right = _fit(art_right)
                arrow = self._txt(self.medium_font, ">>>", hcol)
                total = arrow.get_width() + 20
                if left is not None:
                    total += left.get_width()
                if right is not None:
                    total += right.get_width()
                x0 = hx + max(0, (col_w - total) // 2)
                if left is not None:
                    surface.blit(left, (x0, yy(art_y)))
                    x0 += left.get_width() + 10
                surface.blit(arrow, (x0, yy(art_y + 32)))
                x0 += arrow.get_width() + 10
                if right is not None:
                    surface.blit(right, (x0, yy(art_y)))

            tnow = float(getattr(self, "help_anim_t", 0.0))
            pframes = self.help_icons.get("phenix_frames") or []
            phenix = pframes[int(tnow * 10.0) % len(pframes)] if pframes else self.help_icons.get("phenix")
            sframes = self.help_icons.get("shield_frames") or []
            bubble = sframes[int(tnow * 8.0) % len(sframes)] if sframes else self.help_icons.get("shield")
            gap = 36
            col_w = (BASE_WIDTH - 64 - gap) // 2
            lx, rx = 32, 32 + col_w + gap
            y_l = _text_col("PHENIX", t_list("phenix"), lx, col_w, (255, 160, 80), 146)
            y_r = _text_col("SHIELD", t_list("shield"), rx, col_w, (120, 200, 255), 146)
            art_y = max(y_l, y_r) + 16
            _art_row(lx, col_w, self.help_icons.get("ship"), phenix, (255, 160, 80), art_y)
            _art_row(rx, col_w, self.help_icons.get("ship_shield"), bubble, (120, 200, 255), art_y)

    def _draw_help_bird(self, surface, bird, x, y, phase=0.0):
        """Stage 1–2 bird: flap + eye glow, desynced by phase."""
        frames = getattr(bird, "frames", None) or [getattr(bird, "image", None)]
        frames = [f for f in frames if f is not None]
        if not frames:
            return
        t = float(getattr(self, "help_anim_t", 0.0)) + phase
        flap = int(t * 5.2) % 2
        glow = (t % 2.2) < 0.38
        idx = flap
        if glow and len(frames) >= 4:
            idx = flap + 2
        img = frames[idx % len(frames)]
        surface.blit(img, (int(x - img.get_width() // 2), int(y - img.get_height() // 2)))

    def _draw_help_gargoyle(self, surface, bird, x, y, scale=0.55):
        """Draw animated gargoyle icon centered at (x, y)."""
        wing_up = math.sin(self.help_anim_t * 10.0) > 0
        wing_src = bird.wing_up if wing_up else bird.wing_down
        flap_y = -2 if wing_up else 2
        body = pygame.transform.smoothscale(
            bird.body_img,
            (max(8, int(bird.body_img.get_width() * scale)),
             max(8, int(bird.body_img.get_height() * scale)))
        )
        wing = pygame.transform.smoothscale(
            wing_src,
            (max(8, int(wing_src.get_width() * scale)),
             max(8, int(wing_src.get_height() * scale)))
        )
        bw, bh = body.get_size()
        ww, wh = wing.get_size()
        surface.blit(wing, (int(x - ww - bw * 0.15), int(y - wh * 0.3 + flap_y)))
        surface.blit(pygame.transform.flip(wing, True, False),
                     (int(x + bw * 0.15), int(y - wh * 0.3 + flap_y)))
        surface.blit(body, (int(x - bw / 2), int(y - bh / 2)))



    def _attract_ai(self):
        """Reactive pilot with smoothed steering (avoids left/right jitter)."""
        px, py = self.player.x, self.player.y
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

        for b in getattr(self.formation, "bullets", []) or []:
            if isinstance(b, (list, tuple)):
                add_threat(b[0], b[1], 1.3)
            elif getattr(b, "alive", True):
                add_threat(getattr(b, "x", 0), getattr(b, "y", 0), 1.3)

        if self.boss_saucer is not None:
            for b in getattr(self.boss_saucer, "bullets", []) or []:
                if isinstance(b, (list, tuple)):
                    add_threat(b[0], b[1], 1.5)
                elif getattr(b, "alive", True):
                    add_threat(getattr(b, "x", 0), getattr(b, "y", 0), 1.5)

        # Desired aim X — prefer targets nearly above the ship (easier kills)
        aim_x = None
        best = 1e9
        for e in getattr(self.formation, "enemies", []) or []:
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

        if self.boss_saucer is not None and not getattr(self.boss_saucer, "dead", False):
            core = getattr(self.boss_saucer, "core", None)
            if core is not None and getattr(core, "alive", True):
                aim_x = getattr(core, "x", self.boss_saucer.x)
            else:
                cells = [c for c in (getattr(self.boss_saucer, "cells", []) or []) if getattr(c, "alive", True)]
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
        alpha = min(1.0, 6.0 * self.dt)
        self.ai_move_smooth += (desired - self.ai_move_smooth) * alpha

        # Hold direction at least ~0.12s when committed (hysteresis)
        self.ai_dir_timer = max(0.0, self.ai_dir_timer - self.dt)
        raw = self.ai_move_smooth
        if abs(raw) < 0.22:
            discrete = 0
        elif raw > 0:
            discrete = 1
        else:
            discrete = -1

        if discrete != 0 and discrete != self.ai_dir_locked:
            if self.ai_dir_timer <= 0:
                self.ai_dir_locked = discrete
                self.ai_dir_timer = 0.14
            else:
                discrete = self.ai_dir_locked
        elif discrete == 0 and abs(raw) < 0.12:
            self.ai_dir_locked = 0

        move = self.ai_dir_locked if self.ai_dir_timer > 0 and self.ai_dir_locked != 0 else discrete

        # Aggressive fire: shoot whenever a target is roughly in our column
        shots_ready = len(getattr(self.player, "shots", []) or []) == 0
        if shots_ready:
            # 1) Primary aim target in wide lane
            if aim_x is not None and abs(aim_x - px) < 70:
                shoot = True
            else:
                # 2) Any living enemy roughly above us
                for e in getattr(self.formation, "enemies", []) or []:
                    if not getattr(e, "alive", True) or getattr(e, "dying", False):
                        continue
                    if abs(getattr(e, "x", 0) - px) < 55 and getattr(e, "y", 0) < py - 30:
                        shoot = True
                        break
            # 3) Boss cells / core
            if not shoot and self.boss_saucer is not None and not getattr(self.boss_saucer, "dead", False):
                if aim_x is not None and abs(aim_x - px) < 80:
                    shoot = True
            # 4) Still fire occasionally while hunting (keeps pressure)
            if not shoot and aim_x is not None and random.random() < 0.08:
                shoot = True

        # Special: Phenix when charged, Shield when a volley is incoming
        if (not self.player.is_phenix) and self.player.can_activate_phenix():
            threat_sum = danger_l + danger_r
            want = False
            if getattr(self.player, "uses_shield", False):
                close_dive = False
                for e in getattr(self.formation, "enemies", []) or []:
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
                elif self.stage % 5 == 0 and self.player.phenix_gauge >= 3:
                    want = random.random() < 0.06
                elif aim_x is not None and abs(aim_x - px) < 70:
                    want = random.random() < 0.03
            if want:
                self.player.try_activate_phenix()

        return move, shoot


    def _start_attract(self):
        """Demo play — random stage 1–5, 30s, no high score."""
        self.attract_mode = True
        self.attract_timer = 30.0
        self.started = True
        self.game_over = False
        self.paused = False
        self.quit_confirm = False
        self.hs_phase = None
        self.stage_transition = None
        self.menu_screen = "main"
        self.stage = random.randint(1, 5)
        self.score = 0
        self.explosions = []
        self.life_thresholds = [(1337, False), (8086, False)]
        self.bosses_defeated = max(0, (self.stage - 1) // 5)
        self.used_cheat = True  # never write high score
        sid = random.choice(("phoenix", "shield"))
        self.player = Player(BASE_WIDTH // 2, BASE_HEIGHT - 95, ship_id=sid)
        self.player.sounds = self.sounds
        self.player.lives = 5
        self.ship_id = sid
        self.ship_id_p1 = sid
        if hasattr(self, "_rebuild_life_icon"):
            try:
                self._rebuild_life_icon()
            except Exception:
                pass
        # Phoenix: pre-fill gauge on stages 2–5. Shield starts ready.
        if sid != "shield" and self.stage != 1:
            roll = random.random()
            if roll < 0.55:
                self.player.phenix_gauge = random.randint(4, 8)
            elif roll < 0.80:
                self.player.phenix_gauge = random.randint(3, 5)
        self.input_grace = 0.25
        self.shake_amount = 0.0
        self._setup_stage(self.stage)
        self.cheat_msg = ""
        self.cheat_msg_timer = 0.0
        self.ai_move_smooth = 0.0
        self.ai_dir_locked = 0
        self.ai_dir_timer = 0.0

    def _end_attract(self):
        """Return to main menu from attract mode."""
        saved = (self.input_mode, self.display_mode, self.sfx_volume, self.music_volume,
                 self.fps_target, self.show_fps, self.difficulty, self.language,
                 getattr(self, "bezel_style", "phoenix"), int(getattr(self, "monitor_index", 0) or 0))
        first = self.help_first_shown
        nxt = self.next_is_attract
        self.__init__(soft=True)
        (self.input_mode, self.display_mode, self.sfx_volume, self.music_volume,
         self.fps_target, self.show_fps, self.difficulty, self.language,
         self.bezel_style, self.monitor_index) = saved
        set_lang(self.language)
        self.sounds.set_music_volume(self.music_volume)
        self.sounds.set_master_volume(self.sfx_volume)
        # Do NOT re-call apply_display_mode — avoids desktop flash
        self.help_first_shown = first
        self.next_is_attract = nxt
        self.attract_mode = False
        self.started = False
        self.menu_idle = 0.0
        self.input_grace = 0.45  # swallow the key/button that cancelled the demo
        self._paint_menu_frame()

    def _reset_menu_idle(self):
        self.menu_idle = 0.0
        if self.menu_screen == "help":
            self.menu_screen = "main"
            self.menu_index = 0
            self.help_timer = 0.0

    # --- Pause / quit-to-menu / app quit confirm ---
    def _toggle_pause(self):

        if not self.started or self.game_over or self.stage_transition is not None:
            return
        self.paused = not self.paused
        self.pause_index = 0
        self.pause_options = False
        if self.paused:
            self.sounds.play_electric(False)

    def _paint_menu_frame(self):
        """Immediate frame so soft reset never shows the desktop."""
        try:
            self.game_surface.fill((0, 0, 0))
            if getattr(self, "starfield", None):
                self.starfield.draw(self.game_surface)
            self._flip_frame(0, 0)
        except Exception:
            pass

    def _quit_to_menu(self):
        """Leave current run, return to main menu (keep settings)."""
        saved = (self.input_mode, self.display_mode, self.sfx_volume, self.music_volume,
                 self.fps_target, self.show_fps, self.difficulty, self.language,
                 getattr(self, "bezel_style", "phoenix"), int(getattr(self, "monitor_index", 0) or 0))
        self.__init__(soft=True)
        (self.input_mode, self.display_mode, self.sfx_volume, self.music_volume,
         self.fps_target, self.show_fps, self.difficulty, self.language,
         self.bezel_style, self.monitor_index) = saved
        set_lang(self.language)
        self.sounds.set_music_volume(self.music_volume)
        self.sounds.set_master_volume(self.sfx_volume)
        # Keep existing window — no set_mode flash
        self.paused = False
        self.quit_confirm = False
        self.pause_options = False
        self.menu_screen = "main"
        self.menu_index = 0
        self.input_grace = 0.35  # absorb the confirm key/button that quit the run
        self.player.infinite_lives = False
        self._paint_menu_frame()

    def _return_from_gameover(self):
        """High-score table → title. Swallow the key that closed the table."""
        saved = (self.input_mode, self.display_mode, self.sfx_volume, self.music_volume,
                 self.fps_target, self.show_fps, self.difficulty, self.language,
                 getattr(self, "bezel_style", "phoenix"), int(getattr(self, "monitor_index", 0) or 0))
        self.__init__(soft=True)
        (self.input_mode, self.display_mode, self.sfx_volume, self.music_volume,
         self.fps_target, self.show_fps, self.difficulty, self.language,
         self.bezel_style, self.monitor_index) = saved
        set_lang(self.language)
        self.sounds.set_music_volume(self.music_volume)
        self.sounds.set_master_volume(self.sfx_volume)
        self._paint_menu_frame()
        self.input_grace = 0.45

    def _menu_back(self):

        """B / Esc — return to previous menu screen."""
        if self.menu_screen == "main":
            return
        if self.menu_screen == "reset_confirm":
            self.menu_screen = "options"
            self._focus_option("reset_hs")
        elif self.menu_screen == "ship_select":
            if int(getattr(self, "ship_select_slot", 1) or 1) == 2:
                self._open_ship_select(1)
            else:
                self.menu_screen = "main"
                self.menu_index = 0
        elif self.menu_screen == "options":
            self.menu_screen = "main"
            self.menu_index = 3  # OPTIONS
        elif self.menu_screen == "highscores":
            self.menu_screen = "main"
            self.menu_index = 4
        elif self.menu_screen == "achievements":
            self.ach_data = load_achievements()
            self.menu_screen = "highscores"
        elif self.menu_screen == "jukebox":
            self._close_jukebox()
        elif self.menu_screen == "credits":
            self.menu_screen = "main"
            self.menu_index = 5
        else:
            self.menu_screen = "main"
            self.menu_index = 0

    def _menu_confirm(self):

        if self.menu_screen == "main":
            if self.menu_index == 0:
                self._open_ship_select(1)
            elif self.menu_index == 1:
                pass  # Mode: Left/Right only
            elif self.menu_index == 2:
                # Difficulty changes only with Left/Right — Enter does not cycle
                pass
            elif self.menu_index == 3:
                self.menu_screen = "options"
                self.menu_index = 0
            elif self.menu_index == 4:
                self.hs_entries = load_highscores()
                self.menu_screen = "highscores"
                self.menu_index = 0
            elif self.menu_index == 5:
                self.menu_screen = "credits"
                self.credits_scroll = float(BASE_HEIGHT)
                self.credits_from_start = True
                self.menu_index = 0
            elif self.menu_index == 6:
                self.running = False
        elif self.menu_screen == "jukebox":
            self._juke_play_or_pause()
        elif self.menu_screen == "ship_select":
            ids = ("phoenix", "shield")
            chosen = ids[int(getattr(self, "ship_select_index", 0)) % 2]
            slot = int(getattr(self, "ship_select_slot", 1) or 1)
            two_p = getattr(self, "play_mode", "solo") in ("hotseat", "coop")
            if slot == 2:
                self.ship_id_p2 = chosen
            else:
                self.ship_id = chosen
            try:
                self.save_settings()
            except Exception:
                pass
            if two_p and slot == 1 and getattr(self, "play_mode", "solo") == "coop":
                self._open_ship_select(2)
            elif getattr(self, "hotseat_pick_p2", False):
                self._apply_hotseat_p2_ship()
            else:
                self._begin_run()
        elif self.menu_screen == "reset_confirm":
            if self.menu_index == 0:  # Oui
                self.hs_entries = reset_highscores()
            self.menu_screen = "options"
            spec = self._options_spec()
            self.menu_index = spec.index("reset_hs") if "reset_hs" in spec else 0
        elif self.menu_screen == "options":
            spec = self._options_spec()
            key = spec[self.menu_index] if 0 <= self.menu_index < len(spec) else ""
            if key == "reset_hs":
                self.menu_screen = "reset_confirm"
                self.menu_index = 1
            elif key == "back":
                if self.pause_options:
                    self.pause_options = False
                    self.menu_index = 0
                else:
                    self.menu_screen = "main"
                    self.menu_index = 3

    # --- Input ---

    def take_screenshot(self):
        """Save a PNG of the current display (fullscreen includes bezel)."""
        try:
            folder = os.path.join(user_data_dir(), "screenshots")
            os.makedirs(folder, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(folder, f"phenix_{stamp}.png")
            # Capture the real window surface (bezels + game)
            pygame.image.save(self.screen, path)
            self.cheat_msg = f"SCREENSHOT"
            self.cheat_msg_timer = 2.0
            print("Screenshot saved:", path)
            return path
        except Exception as e:
            print("Screenshot failed:", e)
            return None

    def handle_events(self):
        try:
            events = pygame.event.get()
        except Exception:
            try:
                pygame.event.clear()
            except Exception:
                pass
            events = []
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type in (getattr(pygame, "JOYDEVICEADDED", -1), getattr(pygame, "JOYDEVICEREMOVED", -2)):
                self._poll_gamepad()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F12:
                    self.take_screenshot()
                    continue
                if self.attract_mode:
                    self._end_attract()
                    continue
                if getattr(self, "hotseat_pick_p2", False) and self.menu_screen == "ship_select":
                    if self._is_menu_confirm(event.key) or event.key in (
                        pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_ESCAPE,
                    ):
                        self._menu_confirm()
                    elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
                        self._menu_adjust(-1)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self._menu_adjust(1)
                    continue
                if self.hotseat_wait and self.started and not self.game_over:
                    if getattr(self, "input_grace", 0) <= 0:
                        self._hotseat_resume()
                    continue
                # Phenix / Shield — edge only (set_repeat must not retrigger)
                if self.started and not self.paused and not self.game_over:
                    held = getattr(self, "_special_keys", None)
                    if held is None:
                        held = self._special_keys = set()
                    shift_repeat = event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT) and event.key in held
                    if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT) and not shift_repeat:
                        held.add(event.key)
                    if shift_repeat:
                        pass
                    elif event.key == pygame.K_LSHIFT:
                        # Coop split-keyboard P1 only
                        if self.play_mode == "coop" and getattr(self.player, "input_scheme", "") == "kb1":
                            self._activate_phenix_from_input(self.player)
                    elif event.key == pygame.K_RSHIFT:
                        if self.play_mode == "coop":
                            # P2 keyboard (or 1P-style layout)
                            target = self.player2
                            if getattr(self.player, "input_scheme", "") == "solo":
                                target = self.player2
                            self._activate_phenix_from_input(target)
                        else:
                            self._activate_phenix_from_input(self.player)
                if event.key == pygame.K_ESCAPE:
                    if self.started and not self.game_over:
                        if self.pause_options:
                            if self.menu_screen == "reset_confirm":
                                self.menu_screen = "options"
                                self._focus_option("reset_hs")
                            else:
                                self.pause_options = False
                                self.menu_index = 0
                        elif self.paused:
                            self.paused = False
                            self.pause_options = False
                        else:
                            self._toggle_pause()
                        continue
                    elif not self.started:
                        if self.menu_screen == "help":
                            self._reset_menu_idle()
                        elif self.quit_confirm:
                            self.quit_confirm = False
                        elif self.menu_screen in ("options", "credits", "reset_confirm", "ship_select", "jukebox"):
                            self._menu_back()
                        else:
                            self.quit_confirm = True
                            self.quit_index = 1
                        continue
                # Pause menu (in-game)
                if self.paused and self.started and not self.game_over:
                    if self.pause_options:
                        if self._is_menu_up(event.key):
                            self._menu_nav(-1)
                        elif self._is_menu_down(event.key):
                            self._menu_nav(1)
                        elif event.key in (pygame.K_LEFT, pygame.K_a):
                            self._menu_adjust(-1)
                        elif event.key in (pygame.K_RIGHT, pygame.K_d):
                            self._menu_adjust(1)
                        elif self._is_menu_confirm(event.key):
                            if self.menu_screen == "reset_confirm":
                                if self.menu_index == 0:
                                    self.hs_entries = reset_highscores()
                                self.menu_screen = "options"
                                self._focus_option("reset_hs")
                            else:
                                spec = self._options_spec()
                                key = spec[self.menu_index] if 0 <= self.menu_index < len(spec) else ""
                                if key == "back":
                                    self.pause_options = False
                                    self.menu_index = 0
                                elif key == "reset_hs":
                                    self.menu_screen = "reset_confirm"
                                    self.menu_index = 1
                        elif event.key == pygame.K_ESCAPE:
                            if self.menu_screen == "reset_confirm":
                                self.menu_screen = "options"
                                self._focus_option("reset_hs")
                            else:
                                self.pause_options = False
                                self.menu_index = 0
                    else:
                        if self._is_menu_up(event.key):
                            self.pause_index = (self.pause_index - 1) % 3
                        elif self._is_menu_down(event.key):
                            self.pause_index = (self.pause_index + 1) % 3
                        elif self._is_menu_confirm(event.key):
                            if self.pause_index == 0:  # Reprendre
                                self.paused = False
                            elif self.pause_index == 1:  # Options
                                self.pause_options = True
                                self.menu_screen = "options"
                                self.menu_index = 0
                            else:  # Quitter la partie
                                self._quit_to_menu()
                                continue  # don't also confirm main-menu with same Enter
                        elif event.key == pygame.K_ESCAPE:
                            self.paused = False
                            self.pause_options = False
                            continue
                # Quit game confirm (menus) — ESC already toggled above
                elif self.quit_confirm and not self.started:
                    if self._is_menu_up(event.key):
                        self.quit_index = (self.quit_index - 1) % 2
                    elif self._is_menu_down(event.key):
                        self.quit_index = (self.quit_index + 1) % 2
                    elif self._is_menu_confirm(event.key):
                        if self.quit_index == 0:
                            self.running = False
                        else:
                            self.quit_confirm = False
                            self.input_grace = 0.30
                        continue

                
                if not self.started and not self.game_over and not self.quit_confirm:
                    arrow = self._is_menu_up(event.key) or self._is_menu_down(event.key) or event.key in (
                        pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_q, pygame.K_d,
                    )
                    if not arrow and getattr(self, "input_grace", 0) > 0:
                        continue
                    if self.menu_screen == "help":
                        self._reset_menu_idle()
                    elif self.menu_screen == "credits":
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
                        ) or self._is_menu_confirm(event.key):
                            self.menu_screen = "main"
                            self.menu_index = 6
                    elif self.menu_screen == "achievements":
                        if event.key in (
                            pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s, pygame.K_z,
                        ) or self._is_menu_up(event.key) or self._is_menu_down(event.key):
                            pass
                        elif event.key in (pygame.K_RIGHT, pygame.K_d):
                            self._extra_step(1)
                        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
                            self._extra_step(-1)
                        elif event.key in (
                            pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
                            pygame.K_ESCAPE, pygame.K_BACKSPACE,
                        ):
                            self.ach_data = load_achievements()
                            self.menu_screen = "highscores"
                    elif self.menu_screen == "jukebox":
                        if getattr(self, "juke_video", False):
                            if event.key in (
                                pygame.K_ESCAPE, pygame.K_BACKSPACE,
                                pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
                            ) or self._is_menu_confirm(event.key):
                                self._juke_play_or_pause()
                        elif self._is_menu_up(event.key):
                            self._menu_nav(-1)
                        elif self._is_menu_down(event.key):
                            self._menu_nav(1)
                        elif event.key in (pygame.K_RIGHT, pygame.K_d):
                            self._extra_step(1)
                        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
                            self._extra_step(-1)
                        elif self._is_menu_confirm(event.key):
                            self._juke_play_or_pause()
                    elif self.menu_screen == "highscores":
                        # Invisible cheats on this screen. Empty unicode (numlock,
                        # dead keys) must NOT kick back to the title.
                        ch = (event.unicode or "")
                        if event.key in (pygame.K_RIGHT, pygame.K_d):
                            self._extra_step(1)
                        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
                            self._extra_step(-1)
                        elif ch.isalnum():
                            self._feed_cheat(ch)
                        elif event.key in (
                            pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
                            pygame.K_ESCAPE, pygame.K_BACKSPACE,
                        ):
                            self.menu_screen = "main"
                            self.menu_index = 4
                            self.cheat_buffer = ""
                    elif self._is_menu_up(event.key):
                        self._reset_menu_idle()
                        self._menu_nav(-1)
                    elif self._is_menu_down(event.key):
                        self._reset_menu_idle()
                        self._menu_nav(1)
                    elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
                        self._reset_menu_idle()
                        self._menu_adjust(-1)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self._reset_menu_idle()
                        self._menu_adjust(1)
                    elif self._is_menu_confirm(event.key):
                        self._reset_menu_idle()
                        self._menu_confirm()
                
                if self.game_over:
                    if self.hs_phase == "enter":
                        if event.key == pygame.K_LEFT:
                            self.hs_char_index = (self.hs_char_index - 1) % 3
                        elif event.key == pygame.K_RIGHT:
                            self.hs_char_index = (self.hs_char_index + 1) % 3
                        elif self._is_menu_up(event.key):
                            self._hs_cycle_letter(1)
                        elif self._is_menu_down(event.key):
                            self._hs_cycle_letter(-1)
                        elif event.key == pygame.K_BACKSPACE:
                            self.hs_char_index = max(0, self.hs_char_index - 1)
                        elif self._is_menu_confirm(event.key):
                            self._submit_highscore()
                            self.input_grace = 0.40
                            continue
                        elif event.unicode and event.unicode.isalnum():
                            self.hs_name[self.hs_char_index] = event.unicode.upper()
                            self.hs_char_index = min(2, self.hs_char_index + 1)
                    elif self.hs_phase == "table" and self._is_menu_confirm(event.key):
                        self._return_from_gameover()
                        continue

            elif event.type == pygame.KEYUP:
                held = getattr(self, "_special_keys", None)
                if held and event.key in held:
                    held.discard(event.key)
            
            elif event.type == pygame.JOYBUTTONDOWN:
                if self.attract_mode:
                    self._end_attract()
                    continue
                if getattr(self, "hotseat_pick_p2", False) and self.menu_screen == "ship_select":
                    if event.button in (0, 1, 2, 3):
                        self._menu_confirm()
                    continue
                if self.hotseat_wait and self.started and not self.game_over:
                    if getattr(self, "input_grace", 0) <= 0:
                        self._hotseat_resume()
                    continue
                # B = Phenix while playing (menus still use B as back elsewhere)
                if (event.button == 1 and self.started and not self.paused
                        and not self.game_over and not self.quit_confirm):
                    target = self.player
                    if self.play_mode == "coop":
                        inst = getattr(event, "instance_id", getattr(event, "joy", None))
                        for s in self._ships():
                            joy = getattr(s, "_joy", None)
                            if joy is None:
                                continue
                            jid = getattr(joy, "get_instance_id", lambda: joy.get_id())()
                            if jid == inst or joy.get_id() == getattr(event, "joy", -1):
                                target = s
                                break
                    self._activate_phenix_from_input(target)
                # Start button (7 Xbox / 9 some pads) — pause or quit confirm
                if event.button in (7, 9, 6):
                    if self.started and not self.game_over:
                        self._toggle_pause()
                    elif not self.started:
                        if self.menu_screen == "help":
                            self._reset_menu_idle()
                        elif self.quit_confirm:
                            self.quit_confirm = False
                        elif self.menu_screen in ("options", "credits", "reset_confirm", "ship_select", "jukebox"):
                            self._menu_back()
                        else:
                            self.quit_confirm = True
                            self.quit_index = 1
                elif self.paused and self.started and not self.game_over:
                    if self.pause_options:
                        if event.button == 0:
                            if self.menu_screen == "reset_confirm":
                                if self.menu_index == 0:
                                    self.hs_entries = reset_highscores()
                                self.menu_screen = "options"
                                self._focus_option("reset_hs")
                            else:
                                spec = self._options_spec()
                                key = spec[self.menu_index] if 0 <= self.menu_index < len(spec) else ""
                                if key == "back":
                                    self.pause_options = False
                                    self.menu_index = 0
                                elif key == "reset_hs":
                                    self.menu_screen = "reset_confirm"
                                    self.menu_index = 1
                        elif event.button == 1:
                            if self.menu_screen == "reset_confirm":
                                self.menu_screen = "options"
                                self._focus_option("reset_hs")
                            else:
                                self.pause_options = False
                                self.menu_index = 0
                    else:
                        if event.button == 0:
                            if self.pause_index == 0:
                                self.paused = False
                            elif self.pause_index == 1:
                                self.pause_options = True
                                self.menu_screen = "options"
                                self.menu_index = 0
                            else:
                                self._quit_to_menu()
                                continue  # same A must not confirm main menu
                        elif event.button == 1:
                            self.paused = False
                            self.pause_options = False
                            continue
                elif self.quit_confirm and not self.started:
                    if event.button == 0:
                        if self.quit_index == 0:
                            self.running = False
                        else:
                            self.quit_confirm = False
                            self.input_grace = 0.30
                        continue
                    elif event.button == 1:
                        self.quit_confirm = False
                        self.input_grace = 0.30
                        continue
                elif not self.started and not self.game_over and not self.quit_confirm and getattr(self, "input_grace", 0) <= 0:
                    if self.menu_screen == "help":
                        self._reset_menu_idle()
                    elif event.button == 0:  # A — confirm / enter
                        self._reset_menu_idle()
                        if self.menu_screen in ("highscores", "credits", "achievements"):
                            self._menu_back()
                        else:
                            self._menu_confirm()
                    elif event.button == 1:  # B — back
                        self._reset_menu_idle()
                        self._menu_back()
                elif self.game_over and self.hs_phase == "enter":
                    if event.button in (0, 1):
                        self._submit_highscore()
                        self.input_grace = 0.40
                        continue
                elif self.game_over and self.hs_phase == "table":
                    if event.button in (0, 1):
                        self._return_from_gameover()
                        continue
            elif event.type == pygame.JOYHATMOTION:
                hx, hy = event.value
                if hx == 0 and hy == 0:
                    self._hat_latch = (0, 0)
                elif getattr(self, "_hat_latch", (0, 0)) != (hx, hy):
                    self._hat_latch = (hx, hy)
                    if getattr(self, "hotseat_pick_p2", False) and self.menu_screen == "ship_select":
                        if hx != 0:
                            self._menu_adjust(1 if hx > 0 else -1)
                    elif self.paused and self.started and not self.game_over and not self.pause_options:
                        if hy > 0:
                            self.pause_index = (self.pause_index - 1) % 3
                        elif hy < 0:
                            self.pause_index = (self.pause_index + 1) % 3
                    elif not self.started and not self.game_over:
                        if self.menu_screen == "help":
                            self._reset_menu_idle()
                        elif self.menu_screen == "credits":
                            pass
                        elif self.menu_screen == "jukebox":
                            if getattr(self, "juke_video", False):
                                pass
                            else:
                                if hy > 0:
                                    self._menu_nav(-1)
                                elif hy < 0:
                                    self._menu_nav(1)
                            if hx > 0:
                                self._extra_step(1)
                            elif hx < 0:
                                self._extra_step(-1)
                        elif self.menu_screen in ("highscores", "achievements"):
                            if hx > 0:
                                self._extra_step(1)
                            elif hx < 0:
                                self._extra_step(-1)
                        else:
                            self._reset_menu_idle()
                            if hy > 0:
                                self._menu_nav(-1)
                            elif hy < 0:
                                self._menu_nav(1)
                            if hx != 0:
                                self._menu_adjust(1 if hx > 0 else -1)
                elif self.game_over and self.hs_phase == "enter":
                    if hx < 0:
                        self.hs_char_index = (self.hs_char_index - 1) % 3
                    elif hx > 0:
                        self.hs_char_index = (self.hs_char_index + 1) % 3
                    if hy > 0:
                        self._hs_cycle_letter(1)
                    elif hy < 0:
                        self._hs_cycle_letter(-1)
            elif event.type == pygame.JOYAXISMOTION:
                DEAD = 0.72
                if getattr(self, "hotseat_pick_p2", False) and self.menu_screen == "ship_select":
                    if event.axis == 0:
                        if abs(event.value) < 0.40:
                            self._joy_axis_latch_x = 0
                        elif self._joy_menu_cooldown <= 0:
                            if event.value < -DEAD and self._joy_axis_latch_x != -1:
                                self._menu_adjust(-1)
                                self._joy_axis_latch_x = -1
                                self._joy_menu_cooldown = 0.28
                            elif event.value > DEAD and self._joy_axis_latch_x != 1:
                                self._menu_adjust(1)
                                self._joy_axis_latch_x = 1
                                self._joy_menu_cooldown = 0.28
                elif self.paused and self.started and not self.game_over:
                    if self.pause_options:
                        if event.axis == 1:
                            if abs(event.value) < 0.40:
                                self._joy_axis_latch_y = 0
                            elif self._joy_menu_cooldown <= 0:
                                if event.value < -DEAD and self._joy_axis_latch_y != -1:
                                    self._menu_nav(-1)
                                    self._joy_axis_latch_y = -1
                                    self._joy_menu_cooldown = 0.28
                                elif event.value > DEAD and self._joy_axis_latch_y != 1:
                                    self._menu_nav(1)
                                    self._joy_axis_latch_y = 1
                                    self._joy_menu_cooldown = 0.28
                        elif event.axis == 0:
                            if abs(event.value) < 0.40:
                                self._joy_axis_latch_x = 0
                            elif self._joy_menu_cooldown <= 0:
                                if event.value < -DEAD and self._joy_axis_latch_x != -1:
                                    self._menu_adjust(-1)
                                    self._joy_axis_latch_x = -1
                                    self._joy_menu_cooldown = 0.28
                                elif event.value > DEAD and self._joy_axis_latch_x != 1:
                                    self._menu_adjust(1)
                                    self._joy_axis_latch_x = 1
                                    self._joy_menu_cooldown = 0.28
                    elif event.axis == 1:
                        if abs(event.value) < 0.40:
                            self._joy_axis_latch_y = 0
                        elif self._joy_menu_cooldown <= 0:
                            if event.value < -DEAD and self._joy_axis_latch_y != -1:
                                self.pause_index = (self.pause_index - 1) % 3
                                self._joy_axis_latch_y = -1
                                self._joy_menu_cooldown = 0.28
                            elif event.value > DEAD and self._joy_axis_latch_y != 1:
                                self.pause_index = (self.pause_index + 1) % 3
                                self._joy_axis_latch_y = 1
                                self._joy_menu_cooldown = 0.28
                elif self.quit_confirm and not self.started:
                    if event.axis == 1:
                        if abs(event.value) < 0.40:
                            self._joy_axis_latch_y = 0
                        elif self._joy_menu_cooldown <= 0:
                            if event.value < -DEAD and self._joy_axis_latch_y != -1:
                                self.quit_index = (self.quit_index - 1) % 2
                                self._joy_axis_latch_y = -1
                                self._joy_menu_cooldown = 0.28
                            elif event.value > DEAD and self._joy_axis_latch_y != 1:
                                self.quit_index = (self.quit_index + 1) % 2
                                self._joy_axis_latch_y = 1
                                self._joy_menu_cooldown = 0.28
                elif not self.started and not self.game_over:
                    if self.menu_screen == "achievements" and event.axis == 1:
                        pass
                    elif self.menu_screen == "jukebox" and event.axis == 1:
                        if getattr(self, "juke_video", False):
                            pass
                        elif abs(event.value) < 0.40:
                            self._joy_axis_latch_y = 0
                        elif self._joy_menu_cooldown <= 0:
                            if event.value < -DEAD and self._joy_axis_latch_y != -1:
                                self._menu_nav(-1)
                                self._joy_axis_latch_y = -1
                                self._joy_menu_cooldown = 0.22
                            elif event.value > DEAD and self._joy_axis_latch_y != 1:
                                self._menu_nav(1)
                                self._joy_axis_latch_y = 1
                                self._joy_menu_cooldown = 0.22
                    elif self.menu_screen in ("highscores", "achievements", "jukebox") and event.axis == 0:
                        if abs(event.value) < 0.40:
                            self._joy_axis_latch_x = 0
                        elif self._joy_menu_cooldown <= 0:
                            if event.value > DEAD and self._joy_axis_latch_x != 1:
                                self._joy_axis_latch_x = 1
                                self._joy_menu_cooldown = 0.28
                                self._extra_step(1)
                            elif event.value < -DEAD and self._joy_axis_latch_x != -1:
                                self._joy_axis_latch_x = -1
                                self._joy_menu_cooldown = 0.28
                                self._extra_step(-1)
                    elif self.menu_screen == "credits":
                        pass  # analog stick steers the roll in update()
                    elif self.menu_screen == "help":
                        if abs(event.value) > 0.55:
                            self._reset_menu_idle()
                    elif event.axis == 1:
                        if abs(event.value) < 0.40:
                            self._joy_axis_latch_y = 0
                        elif self._joy_menu_cooldown <= 0:
                            if event.value < -DEAD and self._joy_axis_latch_y != -1:
                                self._reset_menu_idle()
                                self._menu_nav(-1)
                                self._joy_axis_latch_y = -1
                                self._joy_menu_cooldown = 0.28
                            elif event.value > DEAD and self._joy_axis_latch_y != 1:
                                self._reset_menu_idle()
                                self._menu_nav(1)
                                self._joy_axis_latch_y = 1
                                self._joy_menu_cooldown = 0.28
                    elif event.axis == 0:
                        if abs(event.value) < 0.40:
                            self._joy_axis_latch_x = 0
                        elif self._joy_menu_cooldown <= 0:
                            if event.value < -DEAD and self._joy_axis_latch_x != -1:
                                self._reset_menu_idle()
                                self._menu_adjust(-1)
                                self._joy_axis_latch_x = -1
                                self._joy_menu_cooldown = 0.28
                            elif event.value > DEAD and self._joy_axis_latch_x != 1:
                                self._reset_menu_idle()
                                self._menu_adjust(1)
                                self._joy_axis_latch_x = 1
                                self._joy_menu_cooldown = 0.28

    # --- Simulation step ---
    def update(self):
        self.title_timer += self.dt
        self._update_music(); self._tick_ingame_music()
        self._tick_listen_achs()
        self.sounds.update(self.dt)
        # Detect controller plugged after launch (especially on menus)
        if not self.started or self.game_over:
            self._gp_poll = float(getattr(self, "_gp_poll", 0.0)) + self.dt
            if self._gp_poll >= 0.45:
                self._gp_poll = 0.0
                self._poll_gamepad()
        if self._joy_menu_cooldown > 0:
            self._joy_menu_cooldown = max(0.0, self._joy_menu_cooldown - self.dt)
        if self.input_grace > 0:
            self.input_grace = max(0.0, self.input_grace - self.dt)
        # Menus need key repeat; in-game it would retrigger Shield / Phenix.
        want_repeat = not (self.started and not self.game_over)
        if want_repeat != getattr(self, "_key_repeat_on", True):
            self._key_repeat_on = want_repeat
            try:
                pygame.key.set_repeat(220, 45) if want_repeat else pygame.key.set_repeat(0)
            except Exception:
                pass
        if self.cheat_msg_timer > 0:
            self.cheat_msg_timer = max(0.0, self.cheat_msg_timer - self.dt)
        if self._hs_joy_cooldown > 0:
            self._hs_joy_cooldown = max(0.0, self._hs_joy_cooldown - self.dt)
        
        # Analog stick for initials entry
        if self.game_over and self.hs_phase == "enter" and self.joystick and self._hs_joy_cooldown <= 0:
            try:
                ax = self.joystick.get_axis(0) if self.joystick.get_numaxes() > 0 else 0
                ay = self.joystick.get_axis(1) if self.joystick.get_numaxes() > 1 else 0
                if abs(ax) > 0.7:
                    self.hs_char_index = (self.hs_char_index + (1 if ax > 0 else -1)) % 3
                    self._hs_joy_cooldown = 0.28
                elif abs(ay) > 0.7:
                    self._hs_cycle_letter(-1 if ay > 0 else 1)
                    self._hs_joy_cooldown = 0.22
            except Exception:
                pass
        
        if not self.started or self.game_over:
            # Still scroll stars on title/game over (no parallax)
            self.starfield.update(self.dt)
            self.sounds.play_electric(False)
            if self.logo_frames:
                self.logo_timer += self.dt
                if self.logo_timer >= 1.0 / self.logo_fps:
                    self.logo_timer -= 1.0 / self.logo_fps
                    self.logo_index = (self.logo_index + 1) % len(self.logo_frames)
            if not self.started and self.menu_screen == "jukebox":
                self._update_jukebox()
            if not self.started and self.menu_screen == "achievements":
                self._update_ach_scroll()
            if not self.started and self.menu_screen == "credits":
                axis = self._credits_scroll_axis()
                # signed px/s: negative = normal (text rises)
                if axis > 0:
                    target = 140.0
                elif axis < 0:
                    target = -150.0
                else:
                    target = -42.0
                k = min(1.0, 8.0 * self.dt)
                self.credits_speed = getattr(self, "credits_speed", -42.0)
                self.credits_speed += (target - self.credits_speed) * k
                self.credits_scroll += self.credits_speed * self.dt
                ax = self._credits_x_axis()
                target = ax * 58.0
                # Spring + damper: resistance while held, ease back when released
                k_s, k_d = 14.0, 7.5
                self.credits_x = float(getattr(self, "credits_x", 0.0))
                self.credits_xv = float(getattr(self, "credits_xv", 0.0))
                acc = (target - self.credits_x) * k_s - self.credits_xv * k_d
                self.credits_xv += acc * self.dt
                self.credits_x += self.credits_xv * self.dt
                if abs(self.credits_x) < 0.15 and ax == 0:
                    self.credits_x = 0.0
                    self.credits_xv = 0.0
            if not self.started and self.menu_screen == "ship_select":
                self.ship_anim_t = getattr(self, "ship_anim_t", 0.0) + self.dt
            # Attract / help screen from main menu idle
            if not self.started and not self.quit_confirm:
                if self.menu_screen == "main":
                    self.menu_idle += self.dt
                    # First idle after launch: 10s help; then alternate help / attract every 5s
                    idle_need = 10.0 if not self.help_first_shown else 5.0
                    if self.menu_idle >= idle_need:
                        self.menu_idle = 0.0
                        if not self.help_first_shown:
                            self.help_first_shown = True
                            self.menu_screen = "help"
                            self.help_timer = 0.0
                            self.help_page = 0
                            self.help_scroll = 0.0
                            self.help_transitioning = False
                            self.next_is_attract = True
                        elif self.next_is_attract:
                            self.next_is_attract = False
                            self._start_attract()
                        else:
                            self.next_is_attract = True
                            self.menu_screen = "help"
                            self.help_timer = 0.0
                            self.help_page = 0
                            self.help_scroll = 0.0
                            self.help_transitioning = False
                elif self.menu_screen == "help":
                    self.help_anim_t += self.dt
                    if self.help_transitioning:
                        # Smooth vertical slide page 0 → page 1
                        self.help_scroll += self.dt / max(0.05, self.HELP_SCROLL_SEC) * BASE_HEIGHT
                        if self.help_scroll >= BASE_HEIGHT:
                            self.help_scroll = 0.0
                            self.help_transitioning = False
                            self.help_page = 1
                            self.help_timer = 0.0
                    else:
                        self.help_timer += self.dt
                        if self.help_timer >= self.HELP_PAGE_SEC:
                            if self.help_page <= 0:
                                self.help_transitioning = True
                                self.help_scroll = 0.0
                            else:
                                self.menu_screen = "main"
                                self.menu_index = 0
                                self.menu_idle = 0.0
                                self.help_timer = 0.0
                                self.help_page = 0
                else:
                    self.menu_idle = 0.0
            return
        
        if self.paused:
            self.starfield.update(self.dt)
            self.sounds.play_electric(False)
            return

        if getattr(self, "hotseat_pick_p2", False):
            self.starfield.update(self.dt)
            self.ship_anim_t = getattr(self, "ship_anim_t", 0.0) + self.dt
            self.sounds.play_electric(False)
            return
        if self.hotseat_wait:
            self.starfield.update(self.dt)
            self.sounds.play_electric(False)
            return

        if self.hotseat_hold > 0:
            self.hotseat_hold = max(0.0, self.hotseat_hold - self.dt)
            self.starfield.update(self.dt, self.player.x if self.player else BASE_WIDTH / 2)
            for exp in self.explosions[:]:
                exp.update(self.dt)
                if exp.is_finished():
                    self.explosions.remove(exp)
            tesla_on = False
            if self.tesla_fx is not None:
                self.tesla_fx.update(self.dt)
                tesla_on = not self.tesla_fx.is_finished()
                if not tesla_on:
                    self.tesla_fx = None
            self.sounds.play_electric(tesla_on, x=self._sfx_electric_x())
            if self.shake_amount > 0:
                self.shake_amount = max(0.0, self.shake_amount - SCREEN_SHAKE_DECAY * self.dt)
            if self.hotseat_hold <= 0:
                self._hotseat_finish_hold()
            return
            
        keys = pygame.key.get_pressed()
        
        edge_killed_any = False
        if self.stage_transition is None:
            ai_move = ai_shoot = None
            if self.attract_mode:
                ai_move, ai_shoot = self._attract_ai()
            for ship in self._ships():
                ship.rumble_level = int(getattr(self, "rumble_level", 3))
                ship.autofire = True if self.attract_mode else bool(getattr(self, "autofire", True))
                if getattr(self, "play_mode", "solo") != "coop":
                    mode = self.input_mode
                    joy = self.joystick
                    ship.input_scheme = "solo"
                else:
                    scheme = getattr(ship, "input_scheme", "solo")
                    joy = getattr(ship, "_joy", None)
                    mode = "gamepad" if scheme == "pad" else "keyboard"
                if self.attract_mode and ship is self.player:
                    edge_killed = ship.update(
                        self.dt, keys, mode, joy,
                        allow_shoot=(self.input_grace <= 0),
                        ai_move=ai_move, ai_shoot=ai_shoot,
                    )
                else:
                    edge_killed = ship.update(
                        self.dt, keys, mode, joy,
                        allow_shoot=(self.input_grace <= 0),
                    )
                if edge_killed:
                    edge_killed_any = True
                    kind = "gameover" if ship.dying else "edge"
                    self.explosions.append(Explosion(ship.x, ship.y, kind=kind))
                    self.shake_amount = 22.0 if ship.dying else 14.0
                    self.sounds.play("explosion_big" if ship.dying else "explosion", x=ship.x)
                    side = getattr(ship, "last_edge_side", 0) or getattr(ship, "edge_side", -1)
                    self.tesla_fx = TeslaCoilFx(side, ship.y)
                    self.sounds.play_electric(True, x=ship.x)
                    if getattr(ship, "just_lost_life", False):
                        self.stage_life_lost = True
                    if getattr(ship, "edge_contact", False) and getattr(ship, "edge_flash", 0) > 0:
                        self.stage_touched_edge = True
                    if getattr(ship, "flag_gauge_max", False):
                        ship.flag_gauge_max = False
                        if not getattr(ship, "phenix_auto_refill", False):
                            self._unlock_ach("gauge_max")
                    if getattr(self, "play_mode", "") == "coop" and getattr(ship, "just_lost_life", False):
                        self._on_coop_life_lost(ship)
        else:
            edge_killed_any = False
        tesla_on = self.tesla_fx is not None and not self.tesla_fx.is_finished()
        flash_on = any(p.edge_flash > 0.08 and not p.dying for p in self._ships())
        self.sounds.play_electric(tesla_on or flash_on, x=self._sfx_electric_x())
        
        # Attract mode: 30s demo or death → back to menu (no high score)
        if self.attract_mode:
            self.attract_timer -= self.dt
            if self.attract_timer <= 0 or not self.player.alive:
                self._end_attract()
                return

        # Game over / hot-seat hand-off after death disappearance or a lost life
        if not self.attract_mode and not self.game_over and self.hotseat_hold <= 0:
            if (self.hotseat and getattr(self.player, "just_lost_life", False)
                    and self.player.alive and not self.player.dying
                    and self.stage_transition is None):
                self._hotseat_arm_hold("switch", self.HOTSEAT_HOLD_LIFE)
                if self.hotseat_hold > 0:
                    return
            elif not any(p.alive for p in self._ships()):
                if self.hotseat:
                    self._hotseat_arm_hold("eliminated", self.HOTSEAT_HOLD_FINAL)
                else:
                    self._hotseat_arm_hold("gameover", self.HOTSEAT_HOLD_FINAL)
                return
        
        # Starfield with parallax based on player movement
        self.starfield.update(self.dt, self.player.x)
        
        # Stage transition: ship flies off top
        if self.stage_transition == "fly_up":
            for ship in self._ships():
                if ship.alive or ship.dying:
                    ship.y -= 420 * self.dt
                    ship.engine_intensity = 1.0
            self.starfield.update(self.dt, self.player.x)
            if all((not s.alive) or s.y < -80 for s in self._ships()):
                self.stage += 1
                if self.stage == 2:
                    self._unlock_ach("stage2")
                elif self.stage == 6:
                    self._unlock_ach("loop")
                self._setup_stage(self.stage)
                xs = [BASE_WIDTH // 2 - 70, BASE_WIDTH // 2 + 70] if self.play_mode == "coop" else [BASE_WIDTH // 2]
                for i, ship in enumerate(self._ships()):
                    ship.y = BASE_HEIGHT + 60
                    ship.x = xs[min(i, len(xs) - 1)]
                self.stage_transition = "arrive"
                self.transition_timer = 0.0
            # still draw explosions etc lightly
            for exp in self.explosions[:]:
                exp.update(self.dt)
                if exp.is_finished():
                    self.explosions.remove(exp)
            return
        
        if self.stage_transition == "arrive":
            # Ship enters from bottom
            target_y = BASE_HEIGHT - 95
            for ship in self._ships():
                if ship.alive:
                    ship.y -= 380 * self.dt
                    ship.engine_intensity = 1.0
            self.starfield.update(self.dt, self.player.x)
            self.formation.update(self.dt, self.player.x)
            if all((not s.alive) or s.y <= target_y for s in self._ships()):
                for ship in self._ships():
                    if ship.alive:
                        ship.y = target_y
                self.stage_transition = None
                self.input_grace = 0.4
            for exp in self.explosions[:]:
                exp.update(self.dt)
                if exp.is_finished():
                    self.explosions.remove(exp)
            return
        
        self.formation.update(self.dt, self.player.x)
        self._check_extra_lives()
        if self.life_flash_timer > 0:
            self.life_flash_timer = max(0.0, self.life_flash_timer - self.dt)
        
        # --- Stage 5 boss ---
        if self.boss_saucer is not None and self.boss_saucer.alive:
            self.boss_saucer.update(self.dt, self.player.x)
            # Spawn birds more often — stage1 2x more likely than stage2, max 10
            self.boss_bird_timer -= self.dt
            if self.boss_bird_timer <= 0:
                self.boss_bird_timer = random.uniform(0.9, 1.8)
                alive_birds = len(self.formation.get_alive_enemies())
                if alive_birds < 6:
                    x = random.uniform(60, BASE_WIDTH - 60)
                    st = 1 if random.random() < 0.67 else 2
                    bird = Enemy(x, -30, formation_index=alive_birds + random.randint(0, 6), stage=st)
                    bird.speed_mult = stage_speed_mult(self.stage) * self.difficulty_speed_mult()
                    bird.state = "formation"
                    bird.start_dive(x)  # dive in their spawn lane, not a shared player X
                    self.formation.enemies.append(bird)
        
        # Stage clear → fly to next stage (non-boss content)
        content = stage_content(self.stage)
        if (self.stage_transition is None and content != 5
                and self.formation.all_dead()
                and not any(s.dying for s in self._ships())
                and self.boss_saucer is None):
            self._clear_enemy_fire()
            self._on_stage_cleared()
            self.stage_transition = "fly_up"
            for ship in self._ships():
                ship.destroy_bullet()
        
        # Boss killed → cataclysmic saucer explosion, kill all birds, then fly up
        if (self.boss_saucer is not None and not self.boss_saucer.alive
                and self.stage_transition is None and not self.game_over):
            # Cataclysm: explode many cells + boss area
            import random as _r
            living = [c for c in self.boss_saucer.cells if c.alive]
            for c in living:
                c.alive = False
                if _r.random() < 0.35:
                    self.explosions.append(Explosion(c.x, c.y, kind="enemy"))
            for d in self.boss_saucer.decorations:
                if d.alive:
                    d.alive = False
                    self.explosions.append(Explosion(d.x, d.y, kind="enemy"))
            bx = self.boss_saucer.boss.x
            by = self.boss_saucer.boss.y
            for _ in range(8):
                self.explosions.append(Explosion(
                    bx + _r.uniform(-120, 120),
                    by + _r.uniform(-40, 80),
                    kind="gameover" if _ < 3 else "collision"
                ))
            self.shake_amount = 30.0
            self.sounds.play("explosion_big", x=bx)
            for e in self.formation.get_alive_enemies():
                e.kill()
            self.boss_saucer = None
            self.bosses_defeated += 1
            self._unlock_ach("boss_down")
            if self.difficulty == "veteran":
                self._unlock_ach("veteran_clear")
            if self.bosses_defeated >= 10:
                self._unlock_ach("ten_flags")
            self._clear_enemy_fire()
            self.stage_transition = "boss_outro"
            self.transition_timer = 0.0
        
        if self.stage_transition == "boss_outro":
            self.transition_timer += self.dt
            self.starfield.update(self.dt, self.player.x)
            for exp in self.explosions[:]:
                exp.update(self.dt)
                if exp.is_finished():
                    self.explosions.remove(exp)
            # After spectacle, ship flies to next stage
            if self.transition_timer > 1.8:
                self._clear_enemy_fire()
                self._on_stage_cleared()
                self.stage_transition = "fly_up"
                for ship in self._ships():
                    ship.destroy_bullet()
            return
        
        # Player bullet(s) vs Enemies / Boss
        for ship in self._ships():
          for shot_i, bullet_rect in ship.get_bullet_rects():
            hit_something = False
            # Boss saucer armor / core
            if self.boss_saucer is not None and self.boss_saucer.alive:
                result = self.boss_saucer.hit_bullet(bullet_rect)
                if result is not None:
                    kind, target = result
                    if kind == "cell":
                        ship.destroy_bullet("neutral", index=shot_i)
                        self.explosions.append(Explosion(target.x, target.y, kind="enemy"))
                        self.shake_amount = 3.5
                        self.sounds.play("enemy_explosion", volume=0.4, x=target.x)
                        self._add_score(ship, 1)
                    elif kind == "deco":
                        ship.destroy_bullet("neutral", index=shot_i)
                        self.explosions.append(Explosion(target.x, target.y, kind="enemy"))
                        self.shake_amount = 5.0
                        self.sounds.play("enemy_explosion", x=enemy.x)
                        self._add_score(ship, 50)
                    elif kind == "boss":
                        ship.destroy_bullet("valid", index=shot_i)
                        target.kill()
                        self._add_score(ship, self._boss_points())
                        self.explosions.append(Explosion(target.x, target.y, kind="gameover"))
                        self.shake_amount = 20.0
                        self.sounds.play("explosion_big", x=ship.x)
                    hit_something = True
            if hit_something:
                break  # indices shifted; next frame continues

            for enemy in self.formation.get_hittable_enemies():
                if isinstance(enemy, BigBird):
                    if bullet_rect.colliderect(enemy.get_left_wing_hitbox()):
                        if enemy.hit_wing("left"):
                            ship.destroy_bullet("neutral", index=shot_i)
                            self.explosions.append(Explosion(enemy.x - 35, enemy.y, kind="enemy"))
                            self.shake_amount = 3.0
                            self.sounds.play("enemy_explosion", volume=0.5, x=enemy.x)
                        else:
                            ship.destroy_bullet("neutral", index=shot_i)
                        hit_something = True
                        break
                    if bullet_rect.colliderect(enemy.get_right_wing_hitbox()):
                        if enemy.hit_wing("right"):
                            ship.destroy_bullet("neutral", index=shot_i)
                            self.explosions.append(Explosion(enemy.x + 35, enemy.y, kind="enemy"))
                            self.shake_amount = 3.0
                            self.sounds.play("enemy_explosion", volume=0.5, x=enemy.x)
                        else:
                            ship.destroy_bullet("neutral", index=shot_i)
                        hit_something = True
                        break
                    if bullet_rect.colliderect(enemy.get_body_hitbox()):
                        enemy.kill()
                        ship.destroy_bullet("valid", index=shot_i)
                        self._add_score(ship, self._enemy_points(getattr(enemy, "stage", 3)))
                        self.explosions.append(Explosion(enemy.x, enemy.y, kind="enemy"))
                        self.shake_amount = 7.0
                        self.sounds.play("enemy_explosion", x=enemy.x)
                        hit_something = True
                        break
                    # Catch-all: silhouette overlap that slipped between wing/body boxes
                    if bullet_rect.colliderect(enemy.get_hitbox()):
                        enemy.kill()
                        ship.destroy_bullet("valid", index=shot_i)
                        self._add_score(ship, self._enemy_points(getattr(enemy, "stage", 3)))
                        self.explosions.append(Explosion(enemy.x, enemy.y, kind="enemy"))
                        self.shake_amount = 7.0
                        self.sounds.play("enemy_explosion", x=enemy.x)
                        hit_something = True
                        break
                else:
                    if bullet_rect.colliderect(enemy.get_hitbox()):
                        enemy.kill()
                        ship.destroy_bullet("valid", index=shot_i)
                        self._add_score(ship, self._enemy_points(getattr(enemy, "stage", 1)))
                        self.explosions.append(Explosion(enemy.x, enemy.y, kind="enemy"))
                        self.shake_amount = 5.5
                        self.sounds.play("enemy_explosion", x=enemy.x)
                        hit_something = True
                        break
            if hit_something:
                break

        # Enemy attacks vs Player(s) — ships do not collide with each other
        for ship in self._ships():
            if not ship.alive or ship.dying:
                continue
            player_hitbox = ship.get_hitbox()
            if self.boss_saucer is not None and self.boss_saucer.alive:
                hull = self.boss_saucer.get_hull_hitbox()
                if hull.width > 0 and player_hitbox.colliderect(hull):
                    if ship.infinite_lives:
                        ship.hit()
                        self.explosions.append(Explosion(ship.x, ship.y, kind="bullet"))
                        self.shake_amount = 14.0
                        self.sounds.play("explosion", x=ship.x)
                        ship.y = min(BASE_HEIGHT - 80, ship.y + 40)
                    else:
                        if self.play_mode == "coop":
                            ship.hit()
                            self._on_coop_life_lost(ship)
                        else:
                            ship.lives = 0
                            ship.dying = True
                            ship.death_timer = 0.0
                            ship.invulnerable = 0.0
                            ship.rumble(1.0, 1.0, 640)
                        ship.phenix_gauge = float(getattr(ship, "phenix_min_gauge", 0))
                        ship.combo_streak = 0
                        ship.phenix_timer = 0.0
                        self.explosions.append(Explosion(ship.x, ship.y, kind="gameover"))
                        self.shake_amount = 24.0
                        self.sounds.play("explosion_big", x=ship.x)
                for b in self.boss_saucer.bullets[:]:
                    if b.alive and b.get_hitbox().colliderect(player_hitbox):
                        b.alive = False
                        if (not ship.is_phenix) and ship.invulnerable <= 0 and ship.alive and not ship.dying:
                            ship.hit()
                            if self.play_mode == "coop":
                                self._on_coop_life_lost(ship)
                            kind = "gameover" if ship.dying else "bullet"
                            self.explosions.append(Explosion(ship.x, ship.y, kind=kind))
                            self.shake_amount = 22.0 if ship.dying else 12.0
                            self.sounds.play("explosion_big" if ship.dying else "explosion", x=ship.x)
                        break
            for bullet in self.formation.bullets[:]:
                if bullet.alive and bullet.get_hitbox().colliderect(player_hitbox):
                    bullet.alive = False
                    if (not ship.is_phenix) and ship.invulnerable <= 0 and ship.alive and not ship.dying:
                        ship.hit()
                        if self.play_mode == "coop":
                            self._on_coop_life_lost(ship)
                        kind = "gameover" if ship.dying else "bullet"
                        self.explosions.append(Explosion(ship.x, ship.y, kind=kind))
                        self.shake_amount = 22.0 if ship.dying else 12.0
                        self.sounds.play("explosion_big" if ship.dying else "explosion", x=ship.x)
                    break
            for enemy in self.formation.get_hittable_enemies():
                if enemy.diving and enemy.get_hitbox().colliderect(player_hitbox):
                    enemy.kill()
                    self.explosions.append(Explosion(enemy.x, enemy.y, kind="collision"))
                    self.sounds.play("enemy_explosion", x=enemy.x)
                    if ship.is_phenix:
                        self.shake_amount = max(self.shake_amount, 8.0)
                    else:
                        ship.hit()
                        if self.play_mode == "coop":
                            self._on_coop_life_lost(ship)
                        pkind = "gameover" if ship.dying else "collision"
                        self.explosions.append(Explosion(ship.x, ship.y, kind=pkind))
                        self.shake_amount = 26.0 if ship.dying else 18.0
                        self.sounds.play("explosion_big", x=ship.x)
                    break

        if any(getattr(s, "just_lost_life", False) for s in self._ships()):
            self.stage_life_lost = True
        for s in self._ships():
            if getattr(s, "flag_gauge_max", False):
                s.flag_gauge_max = False
                if not getattr(s, "phenix_auto_refill", False):
                    self._unlock_ach("gauge_max")

        for exp in self.explosions[:]:
            exp.update(self.dt)
            if exp.is_finished():
                self.explosions.remove(exp)
        if self.tesla_fx is not None:
            self.tesla_fx.update(self.dt)
            if self.tesla_fx.is_finished():
                self.tesla_fx = None
                self.sounds.play_electric(False)
        
        # Soft performance cap: keep newest explosions only
        if len(self.explosions) > 24:
            self.explosions = self.explosions[-24:]
        
        if self.shake_amount > 0:
            self.shake_amount = max(0.0, self.shake_amount - SCREEN_SHAKE_DECAY * self.dt)

        # Life lost mid-frame (enemy bullet / dive) — hold, then hand off
        if (self.hotseat and not self.attract_mode and not self.game_over
                and not self.hotseat_wait and self.hotseat_hold <= 0
                and self.stage_transition is None
                and getattr(self.player, "just_lost_life", False)
                and self.player.alive and not self.player.dying):
            self._hotseat_arm_hold("switch", self.HOTSEAT_HOLD_LIFE)

    def _clear_enemy_fire(self):
        """Drop leftover enemy / boss shots before the ship flies up."""
        form = getattr(self, "formation", None)
        if form is not None:
            form.bullets = []
            for e in getattr(form, "enemies", []) or []:
                if hasattr(e, "active_shots"):
                    e.active_shots = 0
        boss = getattr(self, "boss_saucer", None)
        if boss is not None and hasattr(boss, "bullets"):
            boss.bullets = []

    # --- Render (logical canvas, then present) ---
    def _ensure_scanline_surf(self):
        """Cached CRT multiply overlay. Period-4 rows (2 dark / 2 clear).

        1px-on/1px-off at 720p moirés when SDL scales to 1080p (1.5×).
        A 4-pixel period becomes 3+3 at 1080p and 4+4 at 1440p — even bars,
        no crawling. Soft cool tint, not prison-bar grey.

        Built once as an opaque RGB map; hot path is a single BLEND_RGB_MULT
        (no per-pixel alpha). Same format as game_surface.
        """
        level = int(getattr(self, "scanlines", 0) or 0)
        if level <= 0:
            return None
        gs = getattr(self, "game_surface", None)
        key = (level, BASE_WIDTH, BASE_HEIGHT, id(gs) if gs is not None else 0)
        if self._scanline_surf is not None and getattr(self, "_scanline_key", None) == key:
            return self._scanline_surf

        w, h = BASE_WIDTH, BASE_HEIGHT
        try:
            if gs is not None:
                surf = pygame.Surface((w, h), 0, gs)
            else:
                surf = pygame.Surface((w, h)).convert()
        except Exception:
            surf = pygame.Surface((w, h))

        # (dark_pair, clear_pair) — RGB multiply factors as 0–255
        # Cool CRT phosphor, never pure black.
        palettes = {
            1: ((236, 238, 242), (255, 255, 255)),
            2: ((214, 218, 228), (250, 252, 255)),
            3: ((188, 194, 208), (244, 246, 250)),
        }
        dark, clear = palettes.get(level, palettes[1])
        try:
            tile = pygame.Surface((w, 4), 0, surf)
        except Exception:
            tile = pygame.Surface((w, 4))
        tile.fill(dark, (0, 0, w, 2))
        tile.fill(clear, (0, 2, w, 2))
        for y in range(0, h, 4):
            surf.blit(tile, (0, y))

        self._scanline_surf = surf
        self._scanline_key = key
        self._scanline_level_cached = level
        return surf


    def draw(self):
        self.game_surface.fill(COLOR_BG)
        
        # Starfield first (background)
        self.starfield.draw(self.game_surface)
        
        shake_x = shake_y = 0
        if self.shake_amount > 0 and self.started and not self.game_over:
            shake_x = random.randint(-int(self.shake_amount), int(self.shake_amount))
            shake_y = random.randint(-int(self.shake_amount), int(self.shake_amount))
        
        if self.started and not self.game_over:
            if self.boss_saucer:
                self.boss_saucer.draw(self.game_surface)
            self.formation.draw(self.game_surface)
            
            for exp in self.explosions:
                exp.draw(self.game_surface)
            if self.tesla_fx is not None:
                self.tesla_fx.draw(self.game_surface)
            
            for ship in self._ships():
                ship.draw(self.game_surface)
            
            # UI (cached text — re-render only when string/color changes)
            tc = self.text_cache
            if self.play_mode == "coop" and self.player2:
                p1s = tc.get(self.font, f"P1 {self.format_score(getattr(self.player, 'score', 0))}", (110, 255, 150))
                p2s = tc.get(self.font, f"P2 {self.format_score(getattr(self.player2, 'score', 0))}", (120, 180, 255))
                self.game_surface.blit(p1s, (16, 16))
                self.game_surface.blit(p2s, (BASE_WIDTH - 16 - p2s.get_width(), 16))
                self._draw_phenix_gauge(self.player, 18, 100)
                self._draw_phenix_gauge(self.player2, BASE_WIDTH - 18 - 14, 100, align="right")
            else:
                score_surf = tc.get(self.font, self.format_score(self.score), (110, 255, 150))
                self.game_surface.blit(score_surf, (BASE_WIDTH // 2 - score_surf.get_width() // 2, 16))
                if self.hotseat and self.slots[0] and self.slots[1]:
                    s0 = self.slots[0]["score"] if self.current_p != 0 else self.score
                    s1 = self.slots[1]["score"] if self.current_p != 1 else self.score
                    c0 = (255, 230, 120) if self.current_p == 0 else (140, 140, 170)
                    c1 = (255, 230, 120) if self.current_p == 1 else (140, 140, 170)
                    hp1 = tc.get(self.font, f"P1 {self.format_score(s0)}", c0)
                    hp2 = tc.get(self.font, f"P2 {self.format_score(s1)}", c1)
                    self.game_surface.blit(hp1, (16, 44))
                    self.game_surface.blit(hp2, (BASE_WIDTH - 16 - hp2.get_width(), 44))
                if self.hotseat and self.current_p == 1:
                    self._draw_phenix_gauge(self.player, BASE_WIDTH - 18 - 14, 100, align="right")
                else:
                    self._draw_phenix_gauge(self.player, 18, 100)
            if self.attract_mode:
                demo = tc.get(self.medium_font, t("demo"), (255, 180, 80))
                self.game_surface.blit(demo, (BASE_WIDTH // 2 - demo.get_width() // 2, 72))
                hint = tc.get(self.font, t("press_any"), (180, 180, 200))
                self.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 36))
            if getattr(self, "used_cheat", False) and not self.attract_mode:
                ch = tc.get(self.font, t("cheat_active"), (255, 60, 60))
                self.game_surface.blit(ch, (BASE_WIDTH // 2 - ch.get_width() // 2, 74))
            
            stage_surf = tc.get(self.font, f"{t('stage')} {self.stage}", (180, 180, 220))
            stage_x = BASE_WIDTH // 2 - stage_surf.get_width() // 2 if self.play_mode == "coop" else 16
            self.game_surface.blit(stage_surf, (stage_x, 16))
            if self.difficulty in ("novice", "veteran") and not self.attract_mode:
                dkey = "diff_novice" if self.difficulty == "novice" else "diff_veteran"
                dcol = (120, 210, 255) if self.difficulty == "novice" else (255, 150, 80)
                dsurf = tc.get(self.font, t(dkey), dcol)
                if self.play_mode in ("coop", "hotseat") or getattr(self, "hotseat", False):
                    dx = BASE_WIDTH // 2 - dsurf.get_width() // 2
                    dy = 70
                else:
                    dx = BASE_WIDTH - 16 - dsurf.get_width()
                    dy = 16
                self.game_surface.blit(dsurf, (dx, dy))
            # Flags for each boss defeated — at 10+, one big flag only
            if self.bosses_defeated >= 10:
                fx = stage_x + stage_surf.get_width() + 12
                self._draw_boss_flag(self.game_surface, fx, 12, big=True)
            elif self.bosses_defeated > 0:
                fx = stage_x + stage_surf.get_width() + 10
                fy = 18
                for i in range(self.bosses_defeated):
                    self._draw_boss_flag(self.game_surface, fx + i * 18, fy, big=False)
            
            self._draw_cheat_message()
            
            # Lives as mini ships
            if self.player.infinite_lives:
                inf = self.text_cache.get(self.font, t("lives_inf"), (110, 255, 150))
                self.game_surface.blit(inf, (BASE_WIDTH // 2 - inf.get_width() // 2, 44))
            n_lives = max(0, self.player.lives)
            if n_lives > 0 and not self.player.infinite_lives:
                gap = 6
                iw = self.life_icon.get_width()
                ih = self.life_icon.get_height()
                total_w = n_lives * iw + (n_lives - 1) * gap
                start_x = BASE_WIDTH // 2 - total_w // 2
                for i in range(n_lives):
                    lx = start_x + i * (iw + gap)
                    ly = 44
                    # Extra life flash/shine on the new icon
                    if self.life_flash_timer > 0 and i == self.life_flash_index:
                        blink = int(self.life_flash_timer * 8) % 2 == 0
                        if blink:
                            # bright glow under ship
                            glow = pygame.Surface((iw + 10, ih + 10), pygame.SRCALPHA)
                            pygame.draw.ellipse(glow, (255, 255, 120, 90), glow.get_rect())
                            self.game_surface.blit(glow, (lx - 5, ly - 5))
                            # white flash version
                            white = self.life_icon.copy()
                            white.fill((255, 255, 200, 0), special_flags=pygame.BLEND_RGBA_ADD)
                            self.game_surface.blit(white, (lx, ly))
                            self.game_surface.blit(self.life_icon, (lx, ly))
                    else:
                        self.game_surface.blit(self.life_icon, (lx, ly))
        
        # Title / Menu Screen
        if not self.started:
            if self.menu_screen in ("main",):
                # Animated fiery logo (fallback to text if frames missing)
                if not self._draw_logo(self.game_surface, BASE_WIDTH // 2, 8):
                    title = self._txt(self.big_font, "PHENIX REBIRTH", (255, 120, 255))
                    self.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 80))
                
                # Subtitle below logo
                logo_h = self.logo_frames[0].get_height() if self.logo_frames else 100
                sub = self._txt(self.font, t("subtitle"), (180, 160, 220))
                self.game_surface.blit(sub, (BASE_WIDTH // 2 - sub.get_width() // 2, 8 + logo_h - 4))
            
            if self.menu_screen == "help":
                # Two pages with optional vertical scroll transition
                if self.help_transitioning:
                    off = int(self.help_scroll)
                    self._draw_help_page(self.game_surface, 0, -off)
                    self._draw_help_page(self.game_surface, 1, BASE_HEIGHT - off)
                else:
                    self._draw_help_page(self.game_surface, self.help_page, 0)
                hint = self._txt(self.font, t("help_return"), (255, 220, 100))
                self.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 36))
                page_lbl = self._txt(
                    self.font,
                    f"{t_help('help_page')} {int(self.help_page) + 1}/2",
                    (140, 140, 180),
                )
                self.game_surface.blit(page_lbl, (BASE_WIDTH - page_lbl.get_width() - 20, BASE_HEIGHT - 36))

            elif self.menu_screen == "ship_select":
                self._draw_ship_select(self.game_surface)
            elif self.menu_screen == "jukebox":
                self._draw_jukebox(self.game_surface)
            elif self.menu_screen == "main":
                diff_key = {"novice": "diff_novice", "normal": "diff_normal", "veteran": "diff_veteran"}.get(self.difficulty, "diff_normal")
                diff = t(diff_key)
                mode = getattr(self, "play_mode", "solo")
                mode_key = {"solo": "mode_solo", "hotseat": "mode_hotseat", "coop": "mode_coop"}.get(mode, "mode_solo")
                options = [
                    t("play"),
                    f"{t('mode')} :  <  {t(mode_key)}  >",
                    f"{t('difficulty')} :  <  {diff}  >",
                    t("options"),
                    t("high_scores"),
                    t("credits"),
                    t("quit"),
                ]
                # Under logo + subtitle, no overlap
                logo_h = self.logo_frames[0].get_height() if self.logo_frames else 100
                base_y = max(300, 12 + logo_h + 48)
                spacing = 34 if base_y + 6 * 34 < BASE_HEIGHT - 100 else 30
                for i, label in enumerate(options):
                    selected = (i == self.menu_index)
                    col = (255, 230, 120) if selected else (160, 160, 190)
                    prefix = "> " if selected else "  "
                    surf = self._txt(self.medium_font, prefix + label, col)
                    self.game_surface.blit(surf, (BASE_WIDTH // 2 - surf.get_width() // 2, base_y + i * spacing))
                
                if self.gamepad_detected:
                    status = self._txt(self.font, t("gamepad_detected"), (100, 200, 140))
                else:
                    status = self._txt(self.font, t("gamepad_none"), (180, 140, 120))
                status_y = min(BASE_HEIGHT - 100, base_y + len(options) * spacing + 10)
                self.game_surface.blit(status, (BASE_WIDTH // 2 - status.get_width() // 2, status_y))
            
            elif self.menu_screen == "highscores":
                hdr = self._txt(self.big_font, t("high_scores"), (255, 120, 255))
                self.game_surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 50))
                entries = self.hs_entries if self.hs_entries else load_highscores()
                base_y = 140
                score_right = BASE_WIDTH // 2 + 170
                for i in range(15):
                    rank = i + 1
                    if i < len(entries):
                        self._draw_hs_row(
                            self.game_surface, base_y + i * 28, rank,
                            entries[i]["name"], entries[i]["score"],
                            (200, 200, 230), score_right,
                            coop=bool(entries[i].get("coop")),
                            ship=entries[i].get("ship"),
                            ship2=entries[i].get("ship2"),
                        )
                    else:
                        self._draw_hs_row(
                            self.game_surface, base_y + i * 28, rank,
                            "---", None, (100, 100, 120), score_right,
                        )
                back = self._txt(self.font, t("ach_hint_hs"), (255, 220, 100))
                self.game_surface.blit(back, (BASE_WIDTH // 2 - back.get_width() // 2, BASE_HEIGHT - 60))
                self._draw_cheat_message()

            elif self.menu_screen == "achievements":
                self._draw_achievements(self.game_surface)
            
            elif self.menu_screen == "credits":
                credits_lines, heights, total_h = self._credits_layout()
                y0 = self.credits_scroll
                if y0 < -total_h:
                    if getattr(self, "credits_from_start", False):
                        self._unlock_ach_meta("credits_watch")
                    self.credits_scroll = float(BASE_HEIGHT)
                    self.credits_from_start = True
                    y0 = self.credits_scroll
                elif y0 > BASE_HEIGHT + 40:
                    self.credits_scroll = float(-total_h)
                    self.credits_from_start = False
                    y0 = self.credits_scroll
                y = y0
                mid = BASE_WIDTH // 2 + int(round(getattr(self, "credits_x", 0.0)))
                logo_h = self.logo_frames[0].get_height() if self.logo_frames else 56
                for i, (kind, line) in enumerate(credits_lines):
                    h = heights[i]
                    if -logo_h < y < BASE_HEIGHT + 20 and kind != "blank":
                        if kind == "title":
                            if self.logo_frames:
                                img = self.logo_frames[self.logo_index % len(self.logo_frames)]
                                self.game_surface.blit(
                                    img, (mid - img.get_width() // 2, int(y))
                                )
                            else:
                                surf = self._txt(self.big_font, line, (255, 120, 255))
                                self.game_surface.blit(
                                    surf, (mid - surf.get_width() // 2, int(y))
                                )
                        elif kind == "header":
                            surf = self._txt(self.medium_font, line, (255, 200, 120))
                            self.game_surface.blit(surf, (mid - surf.get_width() // 2, int(y)))
                        elif kind == "sub":
                            surf = self._txt(self.font, line, (180, 160, 220))
                            self.game_surface.blit(surf, (mid - surf.get_width() // 2, int(y)))
                        else:
                            surf = self._txt(self.font, line, (200, 200, 230))
                            self.game_surface.blit(surf, (mid - surf.get_width() // 2, int(y)))
                    y += h
            
            elif self.menu_screen == "reset_confirm":
                hdr = self._txt(self.medium_font, t("reset_hs_title"), (255, 120, 100))
                self.game_surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 280))
                warn = self._txt(self.font, t("reset_hs_warn"), (180, 160, 160))
                self.game_surface.blit(warn, (BASE_WIDTH // 2 - warn.get_width() // 2, 340))
                for i, label in enumerate([t("yes_u"), t("no_u")]):
                    selected = (i == self.menu_index)
                    col = (255, 230, 120) if selected else (160, 160, 190)
                    prefix = "> " if selected else "  "
                    surf = self._txt(self.medium_font, prefix + label, col)
                    self.game_surface.blit(surf, (BASE_WIDTH // 2 - surf.get_width() // 2, 400 + i * 50))
            
            elif self.menu_screen == "options":
                # OPTIONS screen
                hdr = self._txt(self.medium_font, t("options"), (255, 180, 255))
                self.game_surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 48))
                
                mode_labels = {
                    "window": t("disp_window"),
                    "fullscreen": t("disp_fullscreen"),
                    "borderless": t("disp_borderless"),
                }
                ctrl = t("ctrl_pad") if self.input_mode == "gamepad" else t("ctrl_kb")
                vol_pct = int(round(self.sfx_volume * 100))
                disp = mode_labels.get(self.display_mode, self.display_mode)
                
                fps_label = t("yes") if self.show_fps else t("no")
                mus_pct = int(round(self.music_volume * 100))
                lang_label = next((n for c, n in LANGS if c == self.language), self.language)
                lines = self._options_labels()
                n = max(1, len(lines))
                top = 128
                reserved = 96
                spacing = min(34, max(24, (BASE_HEIGHT - reserved - top) // n))
                left_x = 48
                for i, label in enumerate(lines):
                    selected = (i == self.menu_index)
                    col = (255, 230, 120) if selected else (160, 160, 190)
                    prefix = "> " if selected else "  "
                    surf = self._txt(self.font, prefix + label, col)
                    self.game_surface.blit(surf, (left_x, top + i * spacing))
                spec = self._options_spec()
                if 0 <= self.menu_index < len(spec):
                    self._draw_option_help(spec[self.menu_index])
                hint = self._txt(self.font, t("opt_hint"), (120, 120, 150))
                self.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 78))
            
            if self.menu_screen == "main":
                if int(self.title_timer * 2.5) % 2 == 0:
                    press = self._txt(self.font, t("press_confirm"), (255, 220, 100))
                    self.game_surface.blit(press, (BASE_WIDTH // 2 - press.get_width() // 2, BASE_HEIGHT - 70))
                
                if self.input_mode == "gamepad":
                    controls = self._txt(self.font, t("controls_pad"), (140, 140, 180))
                else:
                    controls = self._txt(self.font, t("controls_kb"), (140, 140, 180))
                self.game_surface.blit(controls, (BASE_WIDTH // 2 - controls.get_width() // 2, BASE_HEIGHT - 40))
            elif self.menu_screen == "options":
                if self.input_mode == "gamepad":
                    controls = self._txt(self.font, t("controls_pad"), (140, 140, 180))
                else:
                    controls = self._txt(self.font, t("controls_kb"), (140, 140, 180))
                self.game_surface.blit(controls, (BASE_WIDTH // 2 - controls.get_width() // 2, BASE_HEIGHT - 40))
        
        # High score / Game Over screens
        if self.game_over and self.hs_phase:
            overlay = self._dim_overlay(180)
            self.game_surface.blit(overlay, (0, 0))
            
            if self.hs_phase == "enter":
                title = self._txt(self.big_font, t("new_record"), (255, 220, 100))
                self.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 100))
                if self.hotseat:
                    who = self._txt(self.font, t("player_n").format(n=self.hs_slot_label), (255, 200, 120))
                    self.game_surface.blit(who, (BASE_WIDTH // 2 - who.get_width() // 2, 72))
                
                sc = self._txt(self.font, f"{t('score_label')} : {self.format_score(self.score)}", (200, 255, 180))
                self.game_surface.blit(sc, (BASE_WIDTH // 2 - sc.get_width() // 2, 180))
                
                hint = self._txt(self.font, t("enter_initials_hint"), (180, 180, 220))
                self.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, 240))
                
                # Three letters
                letter_spacing = 70
                start_x = BASE_WIDTH // 2 - letter_spacing
                for i, ch in enumerate(self.hs_name):
                    col = (255, 255, 120) if i == self.hs_char_index else (220, 220, 255)
                    letter = self._txt(self.big_font, ch, col)
                    lx = start_x + i * letter_spacing - letter.get_width() // 2
                    self.game_surface.blit(letter, (lx, 320))
                    if i == self.hs_char_index:
                        pygame.draw.line(
                            self.game_surface, (255, 220, 100),
                            (lx, 400), (lx + letter.get_width(), 400), 3
                        )
                
                controls = self._txt(self.font, t("hs_entry_controls"), (140, 140, 180))
                self.game_surface.blit(controls, (BASE_WIDTH // 2 - controls.get_width() // 2, 480))
                ok = self._txt(self.font, t("press_confirm"), (255, 220, 100))
                self.game_surface.blit(ok, (BASE_WIDTH // 2 - ok.get_width() // 2, 540))
            
            elif self.hs_phase == "table":
                title = self._txt(self.big_font, t("high_scores"), (255, 120, 255))
                self.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 40))
                
                sc = self._txt(self.font, f"{t('your_score')} : {self.format_score(self.score)}", (200, 255, 180))
                self.game_surface.blit(sc, (BASE_WIDTH // 2 - sc.get_width() // 2, 110))
                
                entries = self.hs_entries if self.hs_entries else []
                base_y = 160
                score_right = BASE_WIDTH // 2 + 170
                for i in range(15):
                    rank = i + 1
                    if i < len(entries):
                        name = entries[i]["name"]
                        score = entries[i]["score"]
                        highlight = (self.hs_submitted and score == self.score and name == "".join(self.hs_name))
                        col = (255, 230, 120) if highlight else (200, 200, 230)
                        self._draw_hs_row(
                            self.game_surface, base_y + i * 28, rank,
                            name, score, col, score_right,
                            coop=bool(entries[i].get("coop")),
                            ship=entries[i].get("ship"),
                            ship2=entries[i].get("ship2"),
                        )
                    else:
                        self._draw_hs_row(
                            self.game_surface, base_y + i * 28, rank,
                            "---", None, (100, 100, 120), score_right,
                        )
                
                restart = self._txt(self.font, t("back_to_menu"), (255, 220, 100))
                self.game_surface.blit(restart, (BASE_WIDTH // 2 - restart.get_width() // 2, BASE_HEIGHT - 50))

        if getattr(self, "hotseat_pick_p2", False) and self.menu_screen == "ship_select":
            overlay = self._dim_overlay(150)
            self.game_surface.blit(overlay, (0, 0))
            self._draw_ship_select(self.game_surface)
        if self.hotseat_wait and self.started and not self.game_over:
            overlay = self._dim_overlay(170)
            self.game_surface.blit(overlay, (0, 0))
            who = t("player_n").format(n=self.hotseat_next + 1)
            title = self._txt(self.big_font, who, (255, 200, 80))
            self.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, BASE_HEIGHT // 2 - 50))
            hint = self._txt(self.font, t("hotseat_press"), (220, 220, 240))
            self.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT // 2 + 24))
        
        self.screen.fill((0, 0, 0))

        # Pause overlay
        if self.paused and self.started and not self.game_over:
            overlay = self._dim_overlay(160)
            self.game_surface.blit(overlay, (0, 0))
            if self.pause_options:
                hdr = self._txt(self.medium_font, t("options"), (255, 180, 255))
                self.game_surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 36))
                if self.menu_screen == "reset_confirm":
                    rh = self._txt(self.medium_font, t("reset_hs_title"), (255, 120, 100))
                    self.game_surface.blit(rh, (BASE_WIDTH // 2 - rh.get_width() // 2, 280))
                    for i, label in enumerate([t("yes_u"), t("no_u")]):
                        selected = (i == self.menu_index)
                        col = (255, 230, 120) if selected else (160, 160, 190)
                        prefix = "> " if selected else "  "
                        surf = self._txt(self.medium_font, prefix + label, col)
                        self.game_surface.blit(surf, (BASE_WIDTH // 2 - surf.get_width() // 2, 360 + i * 50))
                else:
                    lines = self._options_labels()
                    n = max(1, len(lines))
                    top = 92
                    reserved = 48
                    spacing = min(32, max(22, (BASE_HEIGHT - reserved - top) // n))
                    left_x = 48
                    for i, label in enumerate(lines):
                        selected = (i == self.menu_index)
                        col = (255, 230, 120) if selected else (160, 160, 190)
                        prefix = "> " if selected else "  "
                        surf = self._txt(self.font, prefix + label, col)
                        self.game_surface.blit(surf, (left_x, top + i * spacing))
                    spec = self._options_spec()
                    if 0 <= self.menu_index < len(spec):
                        self._draw_option_help(spec[self.menu_index], box=(700, 100, 520, 460))
            else:
                title = self._txt(self.big_font, t("pause"), (255, 220, 100))
                self.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 200))
                for i, label in enumerate([t("resume"), t("options"), t("quit_run")]):
                    selected = (i == self.pause_index)
                    col = (255, 230, 120) if selected else (160, 160, 190)
                    prefix = "> " if selected else "  "
                    surf = self._txt(self.medium_font, prefix + label, col)
                    self.game_surface.blit(surf, (BASE_WIDTH // 2 - surf.get_width() // 2, 300 + i * 55))
        
        # Quit game confirm (menus)
        if self.quit_confirm and not self.started:
            overlay = self._dim_overlay(180)
            self.game_surface.blit(overlay, (0, 0))
            title = self._txt(self.big_font, t("quit_game"), (255, 120, 100))
            self.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 220))
            q = self._txt(self.medium_font, t("quit_game_q"), (220, 220, 240))
            self.game_surface.blit(q, (BASE_WIDTH // 2 - q.get_width() // 2, 300))
            for i, label in enumerate([t("yes_u"), t("no_u")]):
                selected = (i == self.quit_index)
                col = (255, 230, 120) if selected else (160, 160, 190)
                prefix = "> " if selected else "  "
                surf = self._txt(self.medium_font, prefix + label, col)
                self.game_surface.blit(surf, (BASE_WIDTH // 2 - surf.get_width() // 2, 360 + i * 50))

        # FPS counter (top-right) — refresh text ~4 Hz to avoid constant render
        if self.show_fps:
            self._fps_timer = getattr(self, "_fps_timer", 0.0) + getattr(self, "dt", 0.016)
            if self._fps_timer >= 0.25:
                self._fps_timer = 0.0
                self._fps_display = int(round(self.clock.get_fps()))
            fps_surf = self.text_cache.get(
                self.font, f"{getattr(self, '_fps_display', 0)} FPS", (120, 220, 120)
            )
            self.game_surface.blit(fps_surf, (BASE_WIDTH - fps_surf.get_width() - 130, 12))

        # CRT scanlines — multiply, same format as game_surface (no alpha blit)
        if int(getattr(self, "scanlines", 0) or 0) > 0:
            sc = self._ensure_scanline_surf()
            if sc is not None:
                self.game_surface.blit(sc, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        # Toast last so menus / credits / hauts faits can show unlocks
        self._draw_cheat_message()
        
        # Present — GPU upscale when bound, else CPU scale
        self._flip_frame(shake_x, shake_y)

    # --- Main loop ---
    def run(self):
        if not getattr(self, "_intro_done", False):
            play_intro(self)
            self._intro_done = True
            self.input_grace = 0.45
            self.menu_idle = 0.0
        while self.running:
            cap = int(getattr(self, "fps_cap", getattr(self, "fps_target", 60)) or 60)
            panel = int(getattr(self, "panel_hz", 60) or 60)
            # VSync On: never present faster than the panel (60 Hz screen + 120 cap = 60).
            if getattr(self, "vsync_mode", "adaptive") == "on":
                cap = min(cap, panel)
            self.dt = self.clock.tick(cap) / 1000.0
            # Safety clamp (spiral of death protection)
            self.dt = min(self.dt, 0.05)
            
            self.handle_events()
            self.update()
            self.draw()
            
        pygame.quit()
        sys.exit(0)
