"""
Phenix Rebirth — main game controller.

Owns the window, delta-time loop, menus, combat, stage progression,
pause/options, high scores, attract-mode help, and credits.

Play modes: solo, hot-seat (alternating), coop (simultaneous). Options cover
controls, autofire, volumes, session audio mix, rumble, display, GPU present,
VSync, refresh cap, bezels, FPS counter, CRT scanlines and language.
Cheats on the high-score menu: LV02–LV99, LIVE, PHEN, VNOV.
v1.5.0 — Adventure (beta): Acts 1-3, rebindable controls, music, announcer to level 31.
v1.4.5 — 144 Hz option, smoother fullscreen, safer saves, errors.log.
v1.4.4 — Adventure chapter 1 (Shield, broken dome, bestiary, hangar credits).
Arcade loop is unchanged. Seasonal title, April gag, comet stay.

Architecture notes:
- Logical resolution BASE_WIDTH x BASE_HEIGHT (see settings.py).
- GPU path: pygame.SCALED. Ultrawide bezels use a wider logical canvas
  (same aspect as the monitor); SDL GPU-scales the composed frame.
- Display rebuild (GPU/bezel/mode) covers the desktop then refocuses the pad.
- State flags: started, game_over, paused, stage_transition, menu_screen, hs_phase.
- Stages cycle content 1–5 forever with rising speed (stage_speed_mult).
- Cheats on the menu high-score screen: LV02–LV99 (a stage), LIVE, PHEN (stackable), VNOV (every visual novel scene).
- hs_phase "card" = GAME OVER hold (voice + fading rumble) before scores / hot-seat.

This file is intentionally large; split only if a future refactor needs it.
"""
import pygame
import math
import re
import sys
import time
import random
import os
import json
import subprocess
import threading
from datetime import datetime
from settings import *
from settings import stage_content, stage_speed_mult, level_points_bonus
from player import Player, recolor_phenix_frames
from enemy import EnemyFormation, BigBird, Enemy
import invaders
from invaders import InvaderFormation
import crt
import announce
import bindings
import controls
import asteroids
import escort
import galaga
from guardian import GuardianFormation
from galaga import GalagaFormation
from boss import BossSaucer
from explosion import Explosion, TeslaCoilFx
from starfield import Starfield
from sounds import SoundManager
from pheq import load_pheq, resolve_path as pheq_resolve, sample as pheq_sample, tick as pheq_tick, draw as pheq_draw, clock_y as pheq_clock_y, draw_seek as pheq_draw_seek
import custom_music
from ingame_music import cycle as ingame_cycle, label as ingame_label, normalize as ingame_normalize
from mp3_title import title_from_path, title_for_key
from i18n import set_lang, get_lang, t, t_help, t_list, get_credits_lines, LANGS, LANG_CODES
from story import StoryHub
import story_state
import story_items
import addon as mame_addon
from highscores import load_highscores, is_highscore, insert_score, reset_highscores
from achievements import (
    CATALOG, CATALOG_ADV, PAGES as ACH_PAGES, load_achievements, unlock_achievement, unlocked_count,
    add_scalable, set_scalable_at_least, scalable_tier, scalable_progress,
    scalable_thresholds,
)
from gpu_present import GpuPresenter
from desktop_cover import show_cover, hide_cover
from intro import play_intro
import help_screen
import achievements_screen
import story_feats
import ship_select_screen
import highscores_screen
import credits_screen
import fonts
import update_idle
import anchor_fx
import update_play
import input_events
import menu_sfx
import menu_fx
import hint_bar
import menu_ui
import main_menu
import draw_frame
import ach_helpers
import addon_launch
import april_gag
import attract_ai
import display_open
import game_init
import hud_gauge
import menu_actions

from settings import user_data_dir, asset_path, project_root
from user_settings import SETTINGS_FILE, load_user_settings, save_user_settings
from text_cache import TextCache
from pacing import FramePacer
from errlog import log_exc
import videoclip


class _AddonClip:
    """Loop a snap mp4 in the addon frame. ffmpeg raw frames, main thread blit."""

    def __init__(self, path, size):
        self.path = path
        self.w, self.h = size
        self.surface = None
        self._proc = None
        self._buf = b""
        self._frame = self.w * self.h * 3
        self._lock = threading.Lock()
        self._raw = None
        self._fps = 12.0
        self._alive = True
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _spawn(self):
        exe = _ffmpeg_exe()
        cmd = [
            exe, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-i", self.path, "-an",
            "-vf", "scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2" % (self.w, self.h, self.w, self.h),
            "-r", "12", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ]
        flags = 0
        if sys.platform.startswith("win"):
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=flags)

    def _read(self):
        interval = 1.0 / self._fps
        while self._alive:
            try:
                self._proc = self._spawn()
            except Exception:
                return
            out = self._proc.stdout
            next_t = time.perf_counter()
            while self._alive and out is not None:
                chunk = out.read(self._frame)
                if not chunk or len(chunk) < self._frame:
                    break
                # Hold the frame until the display has taken it, then wait the frame slot.
                while self._alive:
                    with self._lock:
                        pending = self._raw is not None
                    if not pending:
                        break
                    time.sleep(0.004)
                if not self._alive:
                    break
                with self._lock:
                    self._raw = chunk
                next_t += interval
                delay = next_t - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_t = time.perf_counter()
            try:
                self._proc.kill()
            except Exception:
                log_exc("game._read")
            if not self._alive:
                break

    def pump(self):
        raw = None
        with self._lock:
            raw = self._raw
            self._raw = None
        if not raw:
            return
        try:
            self.surface = pygame.image.frombuffer(raw, (self.w, self.h), "RGB").convert()
        except Exception:
            self.surface = None

    def close(self):
        self._alive = False
        proc = self._proc
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                log_exc("game.close")


def _ffmpeg_exe():
    """The decoder shipped with the game (see videoclip.find_ffmpeg), else the bare name for the PATH."""
    return videoclip.find_ffmpeg() or ("ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg")


CHEAT_MIN_STAGE, CHEAT_MAX_STAGE = 2, 99      # the stages the cheat code LVxx (typed on the high-score screen) can start at
LAST_ANNOUNCED_LEVEL = 31          # the announcer has recorded the stages 1 to 31 (assets/sounds/level<n>.wav); past it, silence


class Game:
    """
    Top-level application object.

    Lifecycle: __init__ (load settings, build systems) → run() event/update/draw loop.
    Soft restart after a run re-enters __init__ while preserving user settings.
    """

    # Vrai canevas pendant un dessin direct (voir draw()), sinon None.
    _direct_restore = None
    def __init__(self, soft=False):
        """soft=True: reset session state without recreating the window (no desktop flash)."""
        if not soft:
            game_init.init_display(self)

        game_init.init_run_state(self)
        game_init.init_fonts_and_logo(self)
        game_init.init_effects_state(self)
        game_init.init_input_menu(self)
        game_init.init_settings(self, soft)
        game_init.init_audio_and_layout(self, soft)

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
            self._play_ingame_track(want)
        except Exception:
            log_exc("game._tick_ingame_music")

    def _play_ingame_track(self, want):
        """Start the track chosen in the Options: a theme of the game, or a file of the player's folder `musique_perso`."""
        if custom_music.is_custom(want):
            path = custom_music.path_of(want)
            if path is None:
                return
            self.sounds.register_music(want, path)
        self.sounds.play_music(want)

    def _update_music(self):
        """Menu / attract / optional in-game menu theme. Off silences everything."""
        mix = getattr(self, "audio_mix", "sfx")
        scene = self._story_scene_music()
        if scene is None:
            self.sounds.set_music_level(1.0, 2.0)       # (after a scene read over it, the music comes back to full)
        if mix == "off":
            self.sounds.stop_music()
            return
        if getattr(self, "menu_screen", "") == "jukebox":
            return
        story = getattr(self, "story", None)
        if (getattr(self, "menu_screen", "") == "story_hub" and not self.started and story is not None
                and story.film_playing()):
            return                                       # a film of the Adventure plays its own sound
        if scene is not None and not self.started:
            # a story scene with its own theme (the Phobos bar): the menu theme fades out quickly, the new one comes in
            # slowly and stays low under the text; it goes on in the Add-On menu, where it comes back to normal
            key, level = scene
            self.sounds.play_music(key, fade_ms=600, fade_in_ms=3000)
            self.sounds.set_music_level(level, 2.5)
        elif self.game_over and self.hs_phase in ("card", "enter", "table"):
            self.sounds.play_music("gameover")
        elif not self.started:
            if self.menu_screen in ("highscores", "achievements"):
                self.sounds.play_music("gameover")
            elif self.menu_screen == "credits":
                self.sounds.play_music("credits")
            elif self.menu_screen == "addon":
                self.sounds.play_music("nostalgie_elise")
            else:
                self.sounds.play_music("menu")
        elif getattr(self, "attract_mode", False):
            self.sounds.play_music("menu")
        else:
            # In-game picker wins (any of the 5 themes). Mix Off stays silent.
            want = ingame_normalize(getattr(self, "ingame_music", "none"))
            if want != "none":
                self._play_ingame_track(want)
            elif mix in ("sfx_music", "music"):
                self.sounds.play_music("menu")
            else:
                self.sounds.stop_music()

    def _story_scene_music(self):
        """(theme, level) of the music of the story scene on screen, or None."""
        story = getattr(self, "story", None)
        if story is None or getattr(self, "menu_screen", "") != "story_hub" or getattr(self, "started", False):
            return None
        return story.scene_music()

    def _juke_catalog(self):
        return (
            ("menu", "juke_eternal", "music"),
            ("gameover", "juke_gameover", "music"),
            ("credits", "juke_lastcoin", "music"),
            ("nostalgie_start", "juke_nostalgie_start", "music"),
            ("nostalgie_elise", "juke_nostalgie_elise", "music"),
            ("lyra_eternal_dawn", "juke_lyra_eternal_dawn", "music"),       # Lyra Voss: her concert in the Adventure
            ("lyra_what_we_lost", "juke_lyra_what_we_lost", "music"),
            ("lyra_no_mercy_left", "juke_lyra_no_mercy_left", "music"),
            ("lyra_oldest_fear", "juke_lyra_oldest_fear", "music"),
            ("intro", "juke_intro", "video"),
        )

    JUKE_ROWS = 6                   # the tracks shown at once (the list scrolls), above the clock and the LED rack

    def _open_jukebox(self):
        self.menu_screen = "jukebox"
        self.juke_index = int(getattr(self, "juke_index", 0) or 0)
        self.juke_paused = False
        self.juke_video = False
        self.juke_clip = None
        self._juke_audio_wait = False
        try:
            self.sounds.stop_music()
        except Exception:
            log_exc("game._open_jukebox")

    def _leave_jukebox_audio(self):
        self._juke_stop_video()
        try:
            self.sounds.stop_music()
        except Exception:
            log_exc("game._leave_jukebox_audio")
        self.juke_paused = False

    def _close_jukebox(self):
        """Esc / B from the jukebox: up to the main menu, on HIGH SCORES (the three screens of that entry are
        side by side; Left / Right go from one to the other, Esc leaves them). A video playing is only stopped."""
        if getattr(self, "juke_video", False):
            self._juke_play_or_pause()
            return
        self._leave_jukebox_audio()
        self._back_to_extras("jukebox")

    def _extra_enter(self, screen):
        """HS ↔ Hauts faits ↔ Jukebox."""
        if getattr(self, "menu_screen", "") == "jukebox" and screen != "jukebox":
            self._leave_jukebox_audio()
        if screen == "achievements":
            self.ach_data = load_achievements()
            self.menu_screen = "achievements"
            if int(getattr(self, "ach_page", 0) or 0) != 0:
                self.ach_page, self.ach_index = 0, 0       # from the main menu it opens on ARCADE (the Adventure: below)
            try:
                achievements_screen.warm(self)             # the cards of both pages, before the first frame
            except Exception:
                log_exc("game._extra_enter")
        elif screen == "jukebox":
            self._open_jukebox()
        else:
            self.hs_entries = load_highscores()
            self.menu_screen = "highscores"

    # --- Options, Achievements, Jukebox and Credits opened from the Adventure ---
    DOOR_SCREENS = {"options": ("options", "reset_confirm"), "achievements": ("achievements",), "jukebox": ("jukebox",),
                    "credits": ("credits",), "addon": ("addon",)}

    def _open_story_door(self, door):
        """The screen of the main menu that a paragraph of the Extras tab of the Adventure stands for. It looks and works
        as from the main menu; B / Esc (or whatever else would go on to another menu screen) brings the Adventure back
        on that paragraph."""
        if door not in self.DOOR_SCREENS:
            return
        self.story_door = door
        self.menu_index = 0
        self.menu_idle = 0.0
        self.input_grace = 0.45          # the same press / key repeat must not act in the screen just opened
        if door == "options":
            self._open_options()
            self.menu_index = 0
        elif door == "credits":
            self.menu_screen = "credits"
            self.credits_scroll = float(BASE_HEIGHT)
            self.credits_from_start = True
        elif door == "addon":
            self.menu_screen = "addon"            # the games of the Add-On: the bar of the Phobos station
        elif door == "achievements":
            self._extra_enter("achievements")
            self.ach_page = next(i for i, (_, cat) in enumerate(ACH_PAGES) if cat is CATALOG_ADV)   # the Adventure page
            self.ach_index = 0
        else:
            self._open_jukebox()

    def _story_scene_door(self, door):
        """The scene that ends in a screen of the main menu (the Phobos bar) has been read: fade to black, then open it
        (see _apply_fade_action), and the screen comes up from black."""
        self._scene_door = door
        self.FADE_SEC = 0.9
        self._fade_to("story_scene_door")

    def _finish_story_scene_door(self):
        door = getattr(self, "_scene_door", None)
        self._scene_door = None
        story = getattr(self, "story", None)
        if story is None or not door:
            return
        story.finish_scene(door)
        self.menu_screen = "story_hub"
        self._open_story_door(door)

    def _story_door_tick(self):
        """Every frame: when the screen opened from the Adventure has been left for another one, the Adventure is
        back on the Extras tab, on the paragraph it was opened from."""
        story = getattr(self, "story", None)
        if (story is not None and getattr(self, "menu_screen", "") == "story_hub"
                and not getattr(self, "started", False) and not getattr(self, "fade_phase", None)):
            req = story.take_door_request()
            if req:
                self._story_scene_door(req["door"])      # (B / Esc on the Phobos bar scene)
                return
        door = getattr(self, "story_door", None)
        if not door:
            return
        if (getattr(self, "started", False) or getattr(self, "attract_mode", False) or story is None
                or getattr(self, "menu_screen", "") == "story_hub"):
            self.story_door = None
            return
        if self.menu_screen in self.DOOR_SCREENS[door]:
            return
        self.story_door = None
        if getattr(self, "menu_screen", "") == "jukebox":
            self._leave_jukebox_audio()
        story.pane = "extras"
        doors = story.doors()
        story.extras_index = doors.index(door) if door in doors else 0
        story.screen = "hub"
        self.menu_screen = "story_hub"
        self.menu_index = 1
        self.menu_idle = 0.0
        self.input_grace = 0.25

    def _extra_step(self, direction):
        if getattr(self, "story_door", None):
            return                      # opened from the Adventure: Left / Right are not for going to the scores
        order = ("highscores", "achievements", "jukebox")
        cur = getattr(self, "menu_screen", "")
        if cur not in order:
            return
        nxt = order[(order.index(cur) + int(direction)) % 3]
        self._extra_enter(nxt)

    def _juke_stop_video(self):
        clip = getattr(self, "juke_clip", None)
        self.juke_video = False
        self.juke_clip = None
        self._juke_audio_wait = False
        if clip is not None:
            clip.close()

    def _juke_play_or_pause(self):
        cat = self._juke_catalog()
        i = int(getattr(self, "juke_index", 0) or 0) % len(cat)
        key, _title, kind = cat[i]
        if getattr(self, "juke_video", False):
            self._juke_stop_video()
            try:
                self.sounds.stop_music()
            except Exception:
                log_exc("game._juke_play_or_pause")
            return
        if kind == "video":
            from intro import open_clip
            clip = open_clip((BASE_WIDTH, BASE_HEIGHT - 80))
            if clip is None or clip.failed:
                if clip is not None:
                    clip.close()
                return                                  # no intro file, or no ffmpeg: nothing to show
            self.juke_clip = clip
            self.juke_video = True
            self.juke_paused = False
            self._juke_audio_wait = True                # the music starts with the first picture (see _update_jukebox)
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
        """The LED rack of the jukebox (pheq.draw), from the bands of the .pheq file."""
        pheq_draw(
            surface, pygame,
            getattr(self, "_eq_bands", []),
            getattr(self, "_eq_peaks", []),
            BASE_WIDTH, BASE_HEIGHT,
        )

    def _update_jukebox(self):
        if getattr(self, "juke_video", False):
            clip = getattr(self, "juke_clip", None)
            if clip is None or clip.failed:
                self._juke_stop_video()
                return
            if getattr(self, "_juke_audio_wait", False):
                if not clip.ready:
                    return
                self._juke_audio_wait = False           # picture and music start together
                from intro import start_audio
                if start_audio(self.sounds.music_volume):
                    self.sounds._current_music = "intro"
            if self.juke_paused:
                return
            clip.pump()
            if clip.failed or clip.ended:
                self._juke_stop_video()
                try:
                    self.sounds.stop_music()
                except Exception:
                    log_exc("game._update_jukebox")
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

    def _juke_scroll(self, index, n):
        """The first track shown: the list moves only when the cursor leaves the JUKE_ROWS tracks on screen."""
        top = int(getattr(self, "_juke_top", 0) or 0)
        if index < top:
            top = index
        elif index >= top + self.JUKE_ROWS:
            top = index - self.JUKE_ROWS + 1
        top = max(0, min(top, n - self.JUKE_ROWS))
        self._juke_top = top
        return top

    def _juke_arrows(self, surface, box, up, down):
        """Small amber arrows on the edges of the list when there are more tracks above or below."""
        cx = box.centerx
        for show, y, way in ((up, box.top, -1), (down, box.bottom - 1, 1)):
            if show:
                tip = y + way * 7
                pygame.draw.polygon(surface, (255, 200, 120), [(cx - 9, y - way * 3), (cx + 9, y - way * 3), (cx, tip)])

    def _juke_title(self, key, path=None):
        if key == "intro" or key.startswith("lyra_"):
            return t("juke_" + key)         # translated: "(Aventure)", "(Adventure)"... (the .ogg files have no tag)
        if path:
            tit = title_from_path(path)
            if tit:
                return tit
        return title_for_key(asset_path, key)


    def _draw_jukebox(self, surface):
        hdr = self._txt(self.medium_font, t("jukebox"), menu_ui.TITLE)
        surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 28))
        if getattr(self, "juke_video", False):
            clip = getattr(self, "juke_clip", None)
            img = clip.surface if clip is not None else None
            if img is not None:
                surface.blit(img, ((BASE_WIDTH - img.get_width()) // 2, 70 + (BASE_HEIGHT - 80 - img.get_height()) // 2))
            hint_bar.draw_for(self, surface)
            return
        cat = self._juke_catalog()
        cur = None
        try:
            cur = self.sounds.current_music_key()
        except Exception:
            cur = None
        y0 = 100
        labels = []
        for i, (key, title_k, kind) in enumerate(cat):
            playing = (cur == key and kind == "music" and self.sounds.music_busy()) or (
                cur == key and kind == "music" and self.juke_paused
            )
            extra = "  ||" if playing and self.juke_paused else ("  >" if playing else "")
            labels.append(self._juke_title(key) + extra)
        rows_font = fonts.text(32)                  # the tracks: a list to read, in Play (the titles are Audiowide)
        row_h = rows_font.get_linesize()
        index = int(getattr(self, "juke_index", 0) or 0) % max(1, len(cat))
        top = self._juke_scroll(index, len(cat))
        shown = labels[top:top + self.JUKE_ROWS]
        width = max(self._txt(rows_font, label, menu_ui.row_colour(False)).get_width() for label in labels)
        box = menu_ui.draw_rows(self, surface, rows_font, shown, y0, 46, index - top,
                                pad_y=max(1, (46 - row_h) // 2), panel_pad=(24, 12), min_width=width)
        self._juke_arrows(surface, box, top > 0, top + self.JUKE_ROWS < len(cat))
        # The LED rack, the seek bar and the clock of the track playing (or paused), wherever the cursor is in the
        # list: they follow the next track only once it is played.
        music = {k for k, _tk, kind in cat if kind == "music"}
        if cur in music:
            key = cur
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
                pheq_draw_seek(surface, pygame, pos, dur, BASE_WIDTH, BASE_HEIGHT)
                clock = self._txt(
                    self.font,
                    f"{int(pos)//60}:{int(pos)%60:02d} / {int(dur)//60}:{int(dur)%60:02d}",
                    (255, 200, 120),
                )
                surface.blit(clock, (BASE_WIDTH // 2 - clock.get_width() // 2, pheq_clock_y(BASE_HEIGHT)))
        hint_bar.draw_for(self, surface)

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
                if not getattr(s, "uses_shield", False):
                    self.phenix_flash = 1
                if getattr(s, "uses_shield", False):
                    self._note_scalable("iron_curtain")
                else:
                    self._note_scalable("phenix_wake")
                return


    def _draw_cheat_message(self):
        """Centered banner (1UP, achievement, cheat code, pad, screenshot): the colour and the size come from the
        table of announce.py, by kind (the kind is language-agnostic)."""
        if self.cheat_msg_timer <= 0 or not self.cheat_msg:
            return
        pulse = 0.55 + 0.45 * abs(math.sin(self.cheat_msg_timer * 5.0))
        kind = getattr(self, "cheat_kind", "")
        ctype, level = announce.style_of(kind)
        base = announce.color_of(ctype)
        if kind == "1up":                                           # the extra life blinks
            blink = int(self.cheat_msg_timer * 5) % 2 == 0
            col = announce.mix(base, (255, 255, 255), 0.6) if blink else base
        elif ctype in ("reward", "special", "danger"):               # these breathe softly
            col = announce.shade(base, 0.8 + 0.2 * pulse)
        else:
            col = base
        glow = pulse if ctype in ("gain", "reward", "special", "danger") else 0.0
        announce.draw(self, self.game_surface, self.cheat_msg, ctype, level,
                      (BASE_WIDTH // 2, BASE_HEIGHT // 2), color=col, glow=glow)

    def _add_score(self, ship, pts):
        pts = int(pts)
        if ship is not None:
            ship.score = getattr(ship, "score", 0) + pts
        if getattr(self, "play_mode", "solo") == "coop":
            self.score = sum(getattr(s, "score", 0) for s in self._ships())
        else:
            self.score += pts
        if getattr(self, "difficulty", "normal") != "novice":
            self._note_scalable("marathon", int(self.score), absolute=True)



    def _shield_absorb(self, ship, ix=None, iy=None):
        """One ripple + tick when a shot dies on an active Shield."""
        if not ship or not getattr(ship, "uses_shield", False) or not getattr(ship, "is_phenix", False):
            return
        cd = float(getattr(ship, "shield_ripple_cd", 0.0) or 0.0)
        if cd > 0:
            return
        ship.shield_ripple_cd = 0.08
        px, py = float(ship.x), float(ship.y)
        if ix is None:
            ix, iy = px, py
        else:
            ix, iy = float(ix), float(iy if iy is not None else py)
        # Snap spark onto the dome rim (ellipse) facing the shot
        a = max(8.0, getattr(ship, "shield_dome_w", 96) * 0.42)
        b = max(8.0, getattr(ship, "shield_dome_h", 128) * 0.40)
        dx, dy = ix - px, iy - py
        if abs(dx) + abs(dy) < 1.0:
            dx, dy = 0.0, -b
        tnorm = math.sqrt((dx / a) ** 2 + (dy / b) ** 2) or 1.0
        ix = px + dx / tnorm
        iy = py + dy / tnorm
        self.explosions.append(self._boom(ix, iy, kind="shield"))
        ship.shield_flash = 1
        ship.shield_punch = 0.10
        self.shake_amount = max(self.shake_amount, 2.0)
        try:
            self.sounds.play("shield_zap", volume=0.28, x=ship.x)
        except Exception:
            log_exc("game._shield_absorb")
        try:
            if getattr(ship, "_joy", None) is None and getattr(self, "joystick", None):
                ship._joy = self.joystick
            ship.rumble_level = int(getattr(self, "rumble_level", 3))
            ship.rumble(0.40, 0.70, 140)
        except Exception:
            log_exc("game._shield_absorb")


    def _hitstop(self, sec=0.032):
        """Freeze sim ~2 frames @ 60 Hz on a body kill. Wings stay live."""
        if getattr(self, "attract_mode", False):
            return
        self.hitstop = max(float(getattr(self, "hitstop", 0.0) or 0.0), float(sec))

    def _note_scalable(self, aid, amount=1, absolute=False):
        """Progress a scalable haut-fait. Toast only on unlock / tier up."""
        if getattr(self, "attract_mode", False) or getattr(self, "used_cheat", False) or getattr(self, "adventure", None):
            return
        data = getattr(self, "ach_data", None)
        if absolute:
            changed, tier = set_scalable_at_least(aid, amount, data)
        else:
            changed, tier = add_scalable(aid, amount, data)
        self.ach_data = load_achievements()
        if not changed or not tier:
            return
        title = t("ach_" + aid)
        extra = ""
        if tier == "bronze":
            extra = " — " + t("ach_tier_bronze")
        elif tier == "silver":
            extra = " — " + t("ach_tier_silver")
        elif tier == "gold":
            extra = " — " + t("ach_tier_gold")
        self.cheat_msg = f"{t('ach_unlocked')} — {title}{extra}"
        self.cheat_kind = "ach"
        self.cheat_msg_timer = 3.2
        self._say_achievement()

    def _say_achievement(self):
        """The announcer says "Achievement!" each time a haut-fait is unlocked (arcade, menus, Adventure page)."""
        try:
            self.sounds.play_achievement()
        except Exception:
            log_exc("game._say_achievement")

    def _note_bird_kill(self):
        self._note_scalable("first_blood", 1)

    def _on_stage_cleared(self):
        """Hauts faits tied to finishing the current wave."""
        if not getattr(self, "stage_life_lost", False):
            self._note_scalable("survivor")
        st = int(getattr(self, "stage", 1) or 1)
        if (st - 1) % 5 == 0 and not getattr(self, "stage_touched_edge", False):
            self._note_scalable("no_edge")
        if getattr(self, "play_mode", "solo") == "coop":
            ships = [s for s in self._ships() if getattr(s, "ship_id", None)]
            ids = {getattr(s, "ship_id", "phoenix") for s in ships}
            if len(ids) >= 2:
                self._unlock_ach("mixed_squad")

    def _unlock_ach(self, aid):
        """Unlock a haut-fait unless attract / cheat run."""
        if getattr(self, "attract_mode", False) or getattr(self, "used_cheat", False) or getattr(self, "adventure", None):
            return False
        data = getattr(self, "ach_data", None)
        if unlock_achievement(aid, data):
            self.ach_data = load_achievements()
            if getattr(self, "cheat_kind", "") != "1up" or self.cheat_msg_timer <= 0:
                title = t("ach_" + aid)
                self.cheat_msg = f"{t('ach_unlocked')} — {title}"
                self.cheat_kind = "ach"
                self.cheat_msg_timer = 3.0
            self._say_achievement()
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
            self._say_achievement()
            return True
        return False

    def _tick_story_feats(self):
        """The achievements of the Adventure page (src/story_feats.py): one banner after the other, in the menus."""
        if getattr(self, "started", False) or getattr(self, "attract_mode", False):
            return
        queue = self.__dict__.setdefault("_feat_queue", [])
        queue.extend(story_feats.take_news())
        story = getattr(self, "story", None)
        if (getattr(self, "menu_screen", "") == "story_hub" and story is not None
                and getattr(story, "screen", "") in ("intro", "choice", "film", "vn")):
            return                                        # not over a scene of the story, nor over the choice of the hull
        if not queue or self.cheat_msg_timer > 0:
            return
        aid, tier = queue.pop(0)
        extra = " — " + t("ach_tier_" + tier) if tier in ("bronze", "silver", "gold") else ""
        self.cheat_msg = f"{t('ach_unlocked')} — {t('ach_' + aid)}{extra}"
        self.cheat_kind = "ach"
        self.cheat_msg_timer = 3.2
        self._say_achievement()

    def _tick_listen_achs(self):
        """Unlock when the current theme finishes a full play (loop wrap).

        Screen changes that keep the same track do not reset the counter.
        Only a real track change, volume off, or attract resets it.
        """
        return ach_helpers.tick_listen_achs(self)

    def _try_music_collector(self):
        """Third meta: all five listen hauts-faits."""
        from achievements import is_unlocked
        need = (
            "listen_menu", "listen_hs", "listen_credits",
            "listen_nostalgie_start", "listen_nostalgie_elise",
        )
        data = getattr(self, "ach_data", None)
        if all(is_unlocked(a, data) for a in need):
            self._unlock_ach_meta("listen_music_all")

    def _ach_icon(self, kind, unlocked):
        """32px catalog icon, color or grey."""
        return ach_helpers.ach_icon(self, kind, unlocked)

    def _ach_move(self, dx, dy):
        """The cursor of the achievements grid (see achievements_screen.move)."""
        achievements_screen.move(self, dx, dy)

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
        """Hauts faits: a grid of icons and the panel of the one under the cursor."""
        try:
            self._draw_achievements_inner(surface)
        except Exception as e:
            print("achievements draw failed:", e)

    def _draw_achievements_inner(self, surface):
        return achievements_screen.draw_achievements_inner(self, surface)


    def _boom(self, x, y, kind="enemy", delay_frames=0):
        try:
            return Explosion(x, y, kind=kind, delay_frames=delay_frames)
        except TypeError:
            return Explosion(x, y, kind=kind)

    def _drain_detach_pops(self):
        """Wing-pop explosions after a gargoyle body kill."""
        form = getattr(self, "formation", None)
        if form is None:
            return
        for enemy in list(getattr(form, "enemies", []) or []):
            pops = getattr(enemy, "detach_pops", None)
            if not pops:
                continue
            for x, y in list(pops):
                self.explosions.append(self._boom(x, y, kind="enemy"))
            enemy.detach_pops.clear()

    def _draw_phenix_gauge(self, ship=None, gx=18, gy=100, align="left"):
        """HUD: 10-segment Phenix gauge + fire around label from level 3."""
        return hud_gauge.draw_phenix_gauge(self, ship, gx, gy, align)





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
                log_exc("game._coop_icon_surf")
            th = 16
            tw = max(10, int(raw.get_width() * th / max(1, raw.get_height())))
            icon = pygame.transform.smoothscale(raw, (tw, th))
            self._coop_icon = icon
        return icon

    def _vet_icon_surf(self):
        icon = getattr(self, "_vet_icon", None)
        if icon is None:
            path = asset_path("sprites", "icon_veteran.png")
            try:
                raw = pygame.image.load(path).convert_alpha()
            except Exception:
                raw = pygame.Surface((14, 16), pygame.SRCALPHA)
                pygame.draw.circle(raw, (220, 180, 50), (7, 10), 6)
            try:
                r = raw.get_bounding_rect(min_alpha=24)
                if r.width > 1 and r.height > 1:
                    raw = raw.subsurface(r).copy()
            except Exception:
                log_exc("game._vet_icon_surf")
            th = 16
            tw = max(10, int(raw.get_width() * th / max(1, raw.get_height())))
            icon = pygame.transform.smoothscale(raw, (tw, th))
            self._vet_icon = icon
        return icon

    def _draw_vet_mark(self, surface, x, y):
        icon = self._vet_icon_surf()
        iy = y + (self.font.get_height() - icon.get_height()) // 2
        surface.blit(icon, (x, iy))
        return icon.get_width()

    def _draw_coop_mark(self, surface, x, y, col=(170, 185, 210)):
        """Two-player mark. y is the top of the row text."""
        icon = self._coop_icon_surf()
        iy = y + (self.font.get_height() - icon.get_height()) // 2
        surface.blit(icon, (x, iy))

    def _hs_ship_icon(self, sid, tint=None):
        """Tiny hull for the high-score table — same visual height after crop."""
        return highscores_screen.hs_ship_icon(self, sid, tint)

    def _draw_hs_row(self, surface, y, rank, name, score, col, score_right_x=None, coop=False, ship=None, ship2=None, veteran=False, tint=None):
        """Draw one high-score line: rank aligned on '.', score right-aligned."""
        return highscores_screen.draw_hs_row(self, surface, y, rank, name, score, col, score_right_x, coop, ship, ship2, veteran, tint)

    def difficulty_speed_mult(self):

        if self.difficulty == "novice":
            return 0.8
        if self.difficulty == "veteran":
            return 1.2
        return 1.0

    def _level_points_bonus(self):
        """What every enemy is worth on top of its price at the level being played (+10 per 5-level round)."""
        form = getattr(self, "formation", None)
        if isinstance(form, InvaderFormation):
            level = form.level                               # the paint missions count their own levels
        else:
            level = getattr(self, "stage", 1)
        return level_points_bonus(level)

    def _enemy_points(self, content_stage, mastered=False):
        """Points for killing a bird by content stage (1-4), plus the bonus of the level being played.

        Veteran difficulty adds ENEMY_VETERAN_BONUS; so does an Adventure enemy the pilot has
        already destroyed 20 times (`mastered`). The bonus is never counted twice.
        """
        base = {1: 10, 2: 20, 3: 30, 4: 40}.get(content_stage, 10) + self._level_points_bonus()
        if self.difficulty == "veteran" or mastered:
            return base + ENEMY_VETERAN_BONUS
        return base

    def _enemy_kill_points(self, enemy):
        """Points for one enemy destroyed. In the Adventure it also counts for the Bestiary."""
        stage = getattr(enemy, "stage", 1)
        adv = getattr(self, "adventure", None)
        story = getattr(self, "story", None)
        if not adv or story is None:
            return self._enemy_points(stage)
        kind = story_state.enemy_kind(stage)
        kills = adv.setdefault("kills", {})
        kills[kind] = kills.get(kind, 0) + 1
        mastered = story_state.kill_bonus(story.state, kind, kills[kind]) > 0
        return self._enemy_points(stage, mastered)

    def _boss_kill_points(self):
        """Points for the boss saucer destroyed. In the Adventure it also counts for the Bestiary
        (and pays its mastery bonus once the last tier is reached)."""
        pts = self._boss_points()
        adv = getattr(self, "adventure", None)
        story = getattr(self, "story", None)
        if not adv or story is None:
            return pts
        kills = adv.setdefault("kills", {})
        kills["boss"] = kills.get("boss", 0) + 1
        return pts + story_state.kill_bonus(story.state, "boss", kills["boss"])

    def _boss_points(self):
        return (1000 if self.difficulty == "veteran" else 500) + self._level_points_bonus()

    def _deco_points(self):
        """A destroyed top decoration of the boss saucer (its armor bricks stay at 1 point)."""
        return 50 + self._level_points_bonus()

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
        if getattr(self, "cheat_live", False):
            self.player.infinite_lives = True
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
        tint = None
        pl = getattr(self, "player", None)
        if pl is not None:
            sid = getattr(pl, "ship_id", sid)
            tint = getattr(pl, "palette", None)
        if tint is None:
            tint = self._tint_of(sid, int(getattr(pl, "pid", 1) or 1)) if hasattr(self, "_tint_of") else None
        try:
            self.life_icon = self._hs_ship_icon(sid, tint)
        except Exception:
            path = asset_path("sprites", "player_ship.png")
            ship_full = pygame.image.load(path).convert_alpha()
            self.life_icon = pygame.transform.smoothscale(ship_full, (16, 22)).convert_alpha()

    def _load_ship_previews(self):
        """Menu portraits + focus animations (Phenix flap / Shield loop)."""
        return ship_select_screen.load_ship_previews(self)

    def _ship_for_pid(self, pid):
        if int(pid) == 2:
            return getattr(self, "ship_id_p2", "phoenix")
        return getattr(self, "ship_id", "phoenix")

    def _tint_of(self, sid, pid=1):
        """Tint for a hull type, independent of the last confirmed ship."""
        two = int(pid) == 2
        if sid == "shield":
            t = getattr(self, "shield_tint_p2" if two else "shield_tint", "red")
            return t if t in ("red", "green", "violet") else "red"
        t = getattr(self, "phoenix_tint_p2" if two else "phoenix_tint", "argent")
        return t if t in ("argent", "blue", "gold") else "argent"

    def _tint_for_pid(self, pid):
        return self._tint_of(self._ship_for_pid(pid), pid)

    def _palette_score_color(self, pal, bright=True):
        """HUD score tint matching hull palette."""
        base = {
            "blue": (120, 180, 255),
            "gold": (255, 210, 90),
            "red": (255, 130, 110),
            "green": (110, 230, 140),
            "violet": (210, 140, 255),
            "argent": (210, 220, 235),
        }.get(str(pal or "argent"), (210, 220, 235))
        if bright:
            return base
        return tuple(max(50, c * 145 // 255) for c in base)

    def _loadout(self, pid):
        sid = self._ship_for_pid(pid)
        return (sid, self._tint_of(sid, pid))

    def _available_tints(self, sid, pid):
        order = ("red", "green", "violet") if sid == "shield" else ("argent", "blue", "gold")
        if int(pid) != 2 or getattr(self, "play_mode", "solo") == "solo":
            return list(order)
        taken = self._loadout(1)
        return [t for t in order if (sid, t) != taken]

    def _set_tint(self, sid, pid, tint):
        two = int(pid) == 2
        if sid == "shield":
            setattr(self, "shield_tint_p2" if two else "shield_tint", tint)
        else:
            setattr(self, "phoenix_tint_p2" if two else "phoenix_tint", tint)

    def _ensure_p2_free(self):
        """Snap P2 tints off P1's exact loadout."""
        if getattr(self, "play_mode", "solo") == "solo":
            return
        for sid in ("phoenix", "shield"):
            av = self._available_tints(sid, 2)
            if not av:
                continue
            cur = self._tint_of(sid, 2)
            if cur not in av:
                self._set_tint(sid, 2, av[0])

    def _play_ship_welcome(self):
        """English announcer VO for the highlighted hull (reserved mixer channel)."""
        idx = int(getattr(self, "ship_select_index", 0) or 0) % 2
        key = "welcome_shield" if idx == 1 else "welcome_phoenix"
        if hasattr(self, "sounds"):
            try:
                self.sounds.play_vo(key, volume=0.90)
            except Exception:
                log_exc("game._play_ship_welcome")


    def _quit_app(self):
        """Fade to black + music, then leave the process."""
        if getattr(self, "fade_action", None) == "exit":
            self.running = False
            return
        try:
            pygame.mixer.music.fadeout(400)
        except Exception:
            log_exc("game._quit_app")
        self.FADE_SEC = 0.32
        self._fade_to("exit")

    def _fade_to(self, action):
        """Black fade (~5 frames @ 60 Hz) then run action at full black."""
        self.fade_action = action
        self.fade_phase = "out"
        # keep current fade_t if already mid-out

    def _tick_fade(self):
        ph = getattr(self, "fade_phase", None)
        if not ph:
            return
        step = float(self.dt or 0.016) / max(0.016, float(getattr(self, "FADE_SEC", 5.0 / 60.0)))
        if ph == "out":
            self.fade_t = min(1.0, float(getattr(self, "fade_t", 0.0)) + step)
            if self.fade_t >= 1.0:
                self._apply_fade_action()
                self.fade_phase = "in"
        elif ph == "in":
            self.fade_t = max(0.0, float(getattr(self, "fade_t", 1.0)) - step)
            if self.fade_t <= 0.0:
                self.fade_phase = None
                self.fade_action = None
                self.FADE_SEC = 5.0 / 60.0

    def _apply_fade_action(self):
        a = getattr(self, "fade_action", None)
        self.fade_action = None
        if a == "open_select":
            self._open_ship_select(1)
        elif a == "open_select_p2":
            self._open_ship_select(2)
        elif a == "begin":
            self._begin_run()
        elif a == "hotseat_p2":
            self._apply_hotseat_p2_ship()
        elif a == "story_scene_door":
            self._finish_story_scene_door()
        elif a == "exit":
            self.running = False

    def _draw_screen_fade(self):
        t = float(getattr(self, "fade_t", 0.0) or 0.0)
        if t <= 0.01:
            return
        surf = getattr(self, "_fade_surf", None)
        if surf is None or surf.get_size() != (BASE_WIDTH, BASE_HEIGHT):
            surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
            surf.fill((0, 0, 0))
            self._fade_surf = surf
        surf.set_alpha(int(255 * min(1.0, t)))
        self.game_surface.blit(surf, (0, 0))

    def _open_ship_select(self, slot=1):
        self.menu_screen = "ship_select"
        self.ship_select_locked = False
        self._pending_after_welcome = None
        self.ship_select_slot = 1 if int(slot) != 2 else 2
        self.ship_select_index = 0  # always start on Phenix
        if self.ship_select_slot == 1:
            self.phoenix_tint = "argent"
            self.shield_tint = "red"
        else:
            ph = self._available_tints("phoenix", 2)
            sh = self._available_tints("shield", 2)
            self.phoenix_tint_p2 = "argent" if "argent" in ph else (ph[0] if ph else "blue")
            self.shield_tint_p2 = "red" if "red" in sh else (sh[0] if sh else "green")
            if not ph and sh:
                self.ship_select_index = 1
        self.ship_anim_t = 0.0
        self.ship_cycle_phase = "idle"
        self.ship_cycle_t = 0.0
        self.ship_cycle_first = True
        self.ship_cycle_focus = int(getattr(self, "ship_select_index", 0) or 0)
        self.input_grace = 0.20

    def _preview_cycle_frame(self, pack, idle, loop):
        """idle hold → morph in → special hold → morph out → idle."""
        return ship_select_screen.preview_cycle_frame(self, pack, idle, loop)

    def _tick_preview_cycle(self, dt):
        ph = getattr(self, "ship_cycle_phase", "idle")
        tt = float(getattr(self, "ship_cycle_t", 0.0)) + dt
        focus = int(getattr(self, "ship_select_index", 0) or 0) % 2
        if focus != int(getattr(self, "ship_cycle_focus", focus)):
            self.ship_cycle_focus = focus
            self.ship_cycle_phase = "idle"
            self.ship_cycle_t = 0.0
            self.ship_cycle_first = True
            return
        sid = "shield" if focus == 1 else "phoenix"
        pack = (getattr(self, "preview_ships", {}) or {}).get(sid) or {}
        on_fr = pack.get("on") or []
        off_fr = pack.get("off") or []
        fps = 10.0
        if ph == "idle":
            need = 0.40 if getattr(self, "ship_cycle_first", True) else 1.25
            if tt >= need:
                self.ship_cycle_first = False
                self.ship_cycle_phase = "to_special"
                self.ship_cycle_t = 0.0
            else:
                self.ship_cycle_t = tt
        elif ph == "to_special":
            need = (pack.get("on_sec") or len(on_fr) / fps) if on_fr else 0.08
            need = max(0.08, need)
            if tt >= need:
                self.ship_cycle_phase = "special"
                self.ship_cycle_t = 0.0
            else:
                self.ship_cycle_t = tt
        elif ph == "special":
            if tt >= 1.45:
                self.ship_cycle_phase = "to_idle"
                self.ship_cycle_t = 0.0
            else:
                self.ship_cycle_t = tt
        elif ph == "to_idle":
            need = (pack.get("off_sec") or len(off_fr) / fps) if off_fr else 0.08
            need = max(0.08, need)
            if tt >= need:
                self.ship_cycle_phase = "idle"
                self.ship_cycle_t = 0.0
            else:
                self.ship_cycle_t = tt
        else:
            self.ship_cycle_phase = "idle"
            self.ship_cycle_t = 0.0

    def _draw_ship_select(self, surface):
        return ship_select_screen.draw_ship_select(self, surface)

    def _apply_ship_choice(self):
        for ship in self._ships():
            if not hasattr(ship, "set_ship"):
                continue
            pid = int(getattr(ship, "pid", 1) or 1)
            sid = self._ship_for_pid(pid)
            ship.set_ship(sid, tint=self._tint_for_pid(pid))
            # Real hull PNGs — no live hue shift.
        self._rebuild_life_icon()


    def _play_level_vo(self, stage):
        """English stage callout (level1.wav … level31.wav; level31 is "To boldly go where no one has gone before").
        Stages >31 stay silent."""
        n = int(stage or 0)
        if n < 1 or n > LAST_ANNOUNCED_LEVEL or not hasattr(self, "sounds"):
            return
        try:
            self.sounds.play_vo(f"level{n}", volume=0.88)
        except Exception:
            log_exc("game._play_level_vo")

    def _start_arrive_intro(self):
        """New run: fly in from below (same speed as stage transitions) and play stage VO."""
        if (getattr(self, "adventure", None) or {}).get("asteroids"):
            # the Asteroids mission: no flight in from below, the ship is in the middle of the field, nose up
            self.player.x, self.player.y = BASE_WIDTH / 2.0, BASE_HEIGHT / 2.0
            self.player.ast_angle = -math.pi / 2
            self.player.invulnerable = max(self.player.invulnerable, 1.5)
            self.stage_transition = None
            self.input_grace = 0.5
            self._play_level_vo(self._announced_level())
            return
        xs = [BASE_WIDTH // 2 - 70, BASE_WIDTH // 2 + 70] if getattr(self, "play_mode", "solo") == "coop" else [BASE_WIDTH // 2]
        ships = self._ships()
        for i, ship in enumerate(ships):
            if not ship:
                continue
            ship.y = BASE_HEIGHT + 60
            ship.x = xs[min(i, len(xs) - 1)]
            ship.engine_intensity = 1.0
        self.stage_transition = "arrive"
        self.transition_timer = 0.0
        self.input_grace = 0.5
        self._play_level_vo(self._announced_level())


    def _announced_level(self):
        """The level the announcer says at the start: the arcade stage, or, in a paint mission (Space Invaders, whose
        stage is always 1), the level of the mission (1, 2, 3 in the first pass, 4, 5, 6 in the next...)."""
        adv = getattr(self, "adventure", None) or {}
        if adv.get("invaders"):
            return int(adv.get("level") or 1)
        return int(getattr(self, "stage", 1) or 1)


    def _queue_after_welcome(self, action):
        """Launch only after Welcome aboard… has finished."""
        self._pending_after_welcome = action
        self.ship_select_locked = True
        try:
            self._play_ship_welcome()
        except Exception:
            log_exc("game._queue_after_welcome")
        if not (hasattr(self, "sounds") and self.sounds.vo_is_busy()):
            self._flush_after_welcome()

    def _flush_after_welcome(self):
        action = getattr(self, "_pending_after_welcome", None)
        if not action:
            return
        self._pending_after_welcome = None
        self.ship_select_locked = False
        if action == "hotseat_p2":
            self._fade_to("hotseat_p2")
        elif action == "open_select_p2":
            self._fade_to("open_select_p2")
        else:
            self._fade_to("begin")

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
            self._start_arrive_intro()
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
            "intro_done": False,
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
                log_exc("game._apply_slot")

    def _save_current_slot(self):
        if not self.hotseat:
            return
        cap = self._capture_slot()
        if self.slots[self.current_p]:
            cap["eliminated"] = self.slots[self.current_p].get("eliminated", False)
            cap["intro_done"] = self.slots[self.current_p].get("intro_done", False)
        self.slots[self.current_p] = cap

    def _init_hotseat_slots(self):
        """Build two independent stage-1 runs (same difficulty / cheat flags)."""
        self.slots = []
        for i in range(2):
            self.player = Player(BASE_WIDTH // 2, BASE_HEIGHT - 95, ship_id=self._ship_for_pid(i + 1), tint=self._tint_for_pid(i + 1))
            self.player.sounds = self.sounds
            self.player.pid = i + 1
            pass
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
            p.set_ship(sid, tint=self._tint_for_pid(2))
            p.pid = 2
            pass
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
        sl = self.slots[self.current_p] if self.slots else None
        first = sl is None or not sl.get("intro_done")
        if sl is not None:
            sl["intro_done"] = True
        # Extra lives on stage 1 respawn on the pad (same as solo). Intro once per player.
        if first and int(getattr(self, "stage", 1) or 1) == 1:
            self._start_arrive_intro()

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
            other = self._other_p()
            still = self._slot_still_playing(other)
            label = int(getattr(self, "current_p", 0) or 0) + 1
            self._start_gameover_card(after="switch" if still else "hs", player_label=label)
        elif pending == "gameover":
            self._start_gameover_card(after="hs", player_label=None)
        elif pending == "adventure_over":
            self._start_gameover_card(after="adventure", player_label=None)

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
            self._start_gameover_card()

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
        """The device of each coop player, from the two choices of the options (auto by default: two pads, or a pad and
        the arrows, or the keyboard split in two; see controls.resolve_coop)."""
        try:
            controls.sync_game(self)
        except Exception:
            log_exc("game._coop_bindings")
        joys = list(getattr(self, "joysticks", None) or [])      # in the order they were plugged in
        pref = list(getattr(self, "coop_pref", None) or [controls.AUTO, controls.AUTO])
        devices = controls.resolve_coop(pref[0], pref[1], len(joys))
        out = []
        for dev in devices:
            scheme = controls.scheme_of(dev)
            out.append((scheme, joys[int(dev[3:]) - 1] if scheme == "pad" else None))
        return out[0], out[1]

    def _start_coop(self):
        self.play_mode = "coop"
        self.hotseat = False
        self.player2 = Player(BASE_WIDTH // 2 + 70, BASE_HEIGHT - 95, ship_id=self._ship_for_pid(2), tint=self._tint_for_pid(2))
        self.player = Player(BASE_WIDTH // 2 - 70, BASE_HEIGHT - 95, ship_id=self._ship_for_pid(1), tint=self._tint_for_pid(1))
        self.player.pid = 1
        self.player2.pid = 2
        self.player.sounds = self.sounds
        self.player2.sounds = self.sounds
        pass
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
        self._start_arrive_intro()
        try:
            pygame.key.set_repeat(0)
        except Exception:
            log_exc("game._start_coop")

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
        if getattr(self, "adventure", None):
            return

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
                            self._note_scalable("one_up_1337")
                        elif threshold == 8086:
                            self._note_scalable("elite_8086")
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
                        self._note_scalable("one_up_1337")
                    elif threshold == 8086:
                        self._note_scalable("elite_8086")

    # --- Stage setup (content cycle + speed tier) ---
    def _play_boss_cry(self, name, volume=0.9, x=None):
        """Play a boss vocal and reset the idle-yell quiet timer."""
        self.sounds.play(name, volume=volume, x=x)
        self._boss_cry_quiet = 0.0

    def _request_adventure(self, spec):
        """UI launch path: read the first-sortie controls before starting combat."""
        if (not spec.get("first_help_read") and getattr(self, "story", None)
                and story_state.first_sortie(self.story.state, spec.get("id"))):
            self.story.show_first_help(spec)
            return
        self._begin_adventure(spec)

    def _begin_adventure(self, spec):
        """Launch a story mission. Arcade ship select and high scores stay out."""
        self.adventure = dict(spec)
        self.adventure.pop("first_help_read", None)
        self.hotseat = False
        self.player2 = None
        self.play_mode = "solo"
        self.attract_mode = False
        self.started = True
        self.game_over = False
        self.hs_phase = None
        self.paused = False
        self.quit_confirm = False
        self.menu_screen = "main"
        self.stage = 1
        self.score = 0
        self.explosions = []
        self.boss_saucer = None
        self.formation = EnemyFormation()
        self.stage_transition = None
        self.life_thresholds = []
        loadout = self.story.loadout(spec.get("ship")) if getattr(self, "story", None) else {}
        sid = loadout.get("ship_id") or "shield"
        tint = loadout.get("tint") or "red"
        self.ship_id = sid
        self.player = Player(BASE_WIDTH // 2, BASE_HEIGHT - 95, ship_id=sid, tint=tint)
        self.player.sounds = self.sounds
        self.player.pid = 1
        self.player.lives = int(loadout.get("lives") or 1)
        if spec.get("training"):
            self.player.lives = max(3, self.player.lives)
        self.player.infinite_lives = False
        pct = int(loadout.get("speed_pct") or 40)
        self.player.speed = PLAYER_SPEED * (pct / 100.0)
        dome = bool(loadout.get("dome"))
        self.player.adventure_dome = dome
        if sid == "phoenix":
            # the Phenix form lasts a share of the arcade one: 60 % at first, more after the workshop
            self.player.phenix_sec_per_point *= max(0.1, int(loadout.get("phenix_pct") or 60) / 100.0)
        self.player.adventure_wall = loadout.get("wall") or "instant"
        if spec.get("training"):
            self.player.adventure_wall = "immune"
        if loadout.get("vertical"):
            # the two-dimensional impulse reactor (BONUS mission): up and down in the lower third, for the rest of the Adventure
            self.player.vertical_range = (PLAYER_VERTICAL_TOP, PLAYER_VERTICAL_BOTTOM)
        if spec.get("asteroids"):
            # the Asteroids mission (src/asteroids.py): the ship turns and pushes, free on the whole screen
            self.player.asteroid_mode = True
            self.player.vertical_range = None
            self._ast_px, self._ast_py = self.player.x, self.player.y
            self._ast_last_x = self._ast_last_y = None
        self.adventure["dome"] = dome
        # the loot items bought in the hangar for this mission (they are used up when it ends, see _end_adventure)
        items = [] if spec.get("training") else list(spec.get("items") or [])
        fx = story_items.effects(items)
        self.adventure["items"] = items
        self.player.lives += fx["extra_lives"]
        self.player.speed *= fx["speed_mult"]
        self.player.bullet_speed_mult = fx["fire_mult"]
        self.player.electric_immune = fx["electric_immune"]
        # and the one that may fall during it (rare, see story_items.plan_drop). The paint missions (Space Invaders)
        # never carry one, and do not count in the gap between two drops; the items bought still work in them.
        story = getattr(self, "story", None)
        can_loot = (story is not None and not spec.get("invaders") and not spec.get("asteroids")
                    and not spec.get("training"))
        if can_loot and spec.get("reactor"):
            # a BONUS mission: the reactor of its hull falls once, whenever in the waves (the random loot is off)
            self.adventure["loot_plan"] = story_items.reactor_plan(story.state, spec["reactor"], random)
        elif can_loot and spec.get("drop"):
            # an Act 3 BONUS mission: its item falls once, whenever in the waves (the random loot is off)
            self.adventure["loot_plan"] = story_items.item_plan(story.state, spec["drop"], random)
        else:
            self.adventure["loot_plan"] = story_items.plan_drop(story.state, random) if can_loot else None
        self.adventure["loot_clock"] = 0.0
        self.adventure["loot"] = None
        self.loot = None
        self.loot_note = None
        if sid == "shield":
            self.player.SHIELD_DURATION = max(0.4, float(loadout.get("dome_dur") or 1.0))
            self.player.SHIELD_COOLDOWN = max(1.5, float(loadout.get("dome_cd") or 5.0))
            if not dome:
                self.player.phenix_gauge = 0.0
                self.player.phenix_cooldown = 9999.0
        self.input_grace = 0.35
        self.shake_amount = 0.0
        self._setup_stage(1)
        self._rebuild_life_icon()
        self._start_arrive_intro()

    def _next_adventure_wave(self):
        """A won wave of a multi-wave mission: set up the next one. False when it was the last."""
        adv = getattr(self, "adventure", None) or {}
        waves = adv.get("waves") or []
        i = int(adv.get("wave_i", 0) or 0) + 1
        if i >= len(waves):
            return False
        adv["wave_i"] = i
        self._setup_stage(waves[i])
        return True

    def _anchor_snapshot(self):
        """The mission as it is on screen now, as a picture of its own (None if it cannot be drawn)."""
        canvas = self.game_surface
        snap = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
        self.game_surface = snap
        try:
            draw_frame.draw_background(self)
            draw_frame.draw_play(self)
        except Exception:
            log_exc("game._anchor_snapshot")
            return None
        finally:
            self.game_surface = canvas
        return snap

    def _start_anchor_return(self, snapshot):
        """The mission was lost: the quantum double of the ship appears again at the base (Normal mode). The picture of the
        mission is drawn into a whirlwind, a flash, and the map comes back (src/anchor_fx.py)."""
        title = self.medium_font.render(t("story_anchor_title"), True, (190, 235, 255))
        sub = self.font.render(t("story_anchor_sub"), True, (150, 200, 240))
        self.anchor_fx = anchor_fx.make(snapshot, title, sub)
        if self.anchor_fx is not None:
            self._anchor_phase = "swirl"
            try:
                self.sounds.play("anchor_return")
            except Exception:
                log_exc("game._start_anchor_return")

    def _tick_anchor_fx(self):
        """Every frame: the return to base goes on; the map must not act on keys until it is back in sight."""
        fx = getattr(self, "anchor_fx", None)
        if fx is None:
            return
        fx.update(self.dt)
        if fx.done:
            self.anchor_fx = None
            return
        if fx.phase == "fade" and getattr(self, "_anchor_phase", "") != "fade":
            self._anchor_phase = "fade"
            self.input_grace = max(float(self.input_grace or 0.0), 0.3)      # a key held down must not act on the map

    def _veteran_adventure(self):
        """True while a mission of a Veteran save is played (one death ends the save for good)."""
        story = getattr(self, "story", None)
        state = getattr(story, "state", None) or {}
        adv = getattr(self, "adventure", None) or {}
        return bool(adv) and not adv.get("training") and state.get("mode") == "veteran"

    def _bank_adventure(self, cleared):
        """Write the result of the mission into the save (once)."""
        spec = getattr(self, "adventure", None) or {}
        story = getattr(self, "story", None)
        if story is None or spec.get("banked"):
            return
        spec["banked"] = True
        try:
            story.apply_result(spec.get("id"), int(getattr(self, "score", 0) or 0), bool(cleared), spec.get("kills"),
                               loot=spec.get("loot"), used=spec.get("items"), flawless=not spec.get("life_lost"))
        except Exception:
            log_exc("game._end_adventure")

    def _end_adventure(self, cleared):
        """Bank the run into the hangar and return to the mission map."""
        spec = getattr(self, "adventure", None) or {}
        self.sounds.stop_sfx("saucer_pass", 150)
        banked = bool(spec.get("banked"))                       # a fallen Veteran was already written down at his death
        snapshot = None if (cleared or banked) else self._anchor_snapshot()
        story = getattr(self, "story", None)
        self._bank_adventure(cleared)
        self.adventure = None
        self.started = False
        self._stop_go_rumble()
        game_init.reset_run(self)   # a new ship, formation, score... : the next game must not inherit the dead mission
        self.menu_screen = "story_hub"
        self.input_grace = 0.4
        if snapshot is not None and story is not None and getattr(story, "screen", "") == "hub":
            self._start_anchor_return(snapshot)         # (a fallen Veteran has no anchor: the slot list comes at once)
        try:
            self.sounds.play_electric(False)
        except Exception:
            log_exc("game._end_adventure")
        try:
            self.sounds.play_music("menu", fade_ms=getattr(self.sounds, "MENU_RETURN_MS", 900))
        except Exception:
            log_exc("game._end_adventure")

    def _setup_stage(self, stage):
        """Load content for stage (1-5 cycle) with speed scaling + difficulty.

        Adventure forces the mission content (chapter 1 main = stage 1 only).
        """
        self.stage_life_lost = False
        self.stage_touched_edge = False
        adv = getattr(self, "adventure", None)
        waves = (adv or {}).get("waves")
        if adv and adv.get("guardians"):
            self.stage = 3
            from ship_burn import prepare as prepare_ship_burn
            prepare_ship_burn(self.player)
            self.formation = GuardianFormation()
            self.formation.sounds = self.sounds
            self.boss_saucer = None
            return
        if adv and waves:
            # a mission of several waves: each one plays like that stage of the arcade game
            number = int(waves[max(0, min(len(waves) - 1, int(adv.get("wave_i", 0) or 0)))])
            self.stage = number
            content = stage_content(number)
            mult = float(adv.get("speed") or 1.0) * stage_speed_mult(number) * self.difficulty_speed_mult()
        elif adv and adv.get("invaders"):
            # the paint missions: a Space Invaders grid whose level (1, 2, 3...) sets its pace
            self.stage = 1
            mult = float(adv.get("speed") or 1.0) * self.difficulty_speed_mult()
            self.formation = InvaderFormation(level=int(adv.get("level") or 1), speed_mult=mult)
            self.formation.sounds = self.sounds
            self.formation.font = self.font
            self.sounds.prepare_invader_sfx(invaders.STEP_PITCHES, invaders.STEP_PITCH_GAP, invaders.SAUCER_PASS)
            self.boss_saucer = None
            return
        elif adv and adv.get("galaga"):
            # the BONUS mission: four waves of birds in chains, like Galaga (src/galaga.py), at level 2
            number = int(adv.get("stage") or story_state.GALAGA_STAGE)
            self.stage = number
            mult = float(adv.get("speed") or 1.0) * stage_speed_mult(number) * self.difficulty_speed_mult()
            self.formation = GalagaFormation(speed_mult=mult, fire_mult=float(adv.get("fire_mult") or 1.0))
            self.formation.sounds = self.sounds
            self.boss_saucer = None
            return
        elif adv and adv.get("asteroids"):
            # the Asteroids mission (src/asteroids.py): rocks that break, the miniature saucer, a ship that flies free
            self.stage = 1
            mult = float(adv.get("speed") or 1.0) * self.difficulty_speed_mult()
            self.formation = asteroids.AsteroidFormation(speed_mult=mult, target=int(adv.get("target") or asteroids.TARGET))
            self.formation.sounds = self.sounds
            self.formation.font = self.font
            self.sounds.prepare_invader_sfx(invaders.STEP_PITCHES, invaders.STEP_PITCH_GAP, invaders.SAUCER_PASS)
            self.boss_saucer = None
            return
        elif adv and adv.get("escort"):
            # the VIP rescue (src/escort.py): blue and khaki birds of one arcade level, for ever, and the cruise ship
            number = int(adv.get("stage") or 6)
            self.stage = number
            mult = float(adv.get("speed") or 1.0) * stage_speed_mult(number) * self.difficulty_speed_mult()
            self.formation = escort.EscortFormation(speed_mult=mult)
            self.formation.sounds = self.sounds
            self.boss_saucer = None
            return
        elif adv and adv.get("swarm"):
            # the swarm mission: all four enemies at once, at the speed of one arcade level
            number = int(adv.get("stage") or 11)
            self.stage = number
            content = 0
            mult = float(adv.get("speed") or 1.0) * stage_speed_mult(number) * self.difficulty_speed_mult()
        elif adv:
            content = int(adv.get("content") or 1)
            mult = float(adv.get("speed") or 1.0) * self.difficulty_speed_mult()
        else:
            content = stage_content(stage)
            mult = stage_speed_mult(stage) * self.difficulty_speed_mult()
        if isinstance(self.formation, (InvaderFormation, GalagaFormation, escort.EscortFormation,
                                       asteroids.AsteroidFormation, GuardianFormation)):
            self.formation = EnemyFormation()            # back to the ordinary grids
        self.formation.enemies = []
        self.formation.bullets = []
        self.formation.swarm = None
        self.boss_saucer = None
        if content == 0:
            self.formation.spawn_swarm(speed_mult=mult, screens=(adv or {}).get("swarm_screens"))
            self.formation.sounds = self.sounds
        elif content == 5:
            self.boss_saucer = BossSaucer()
            # Scale boss descend/shoot lightly with mult
            self.boss_saucer.descend_speed *= mult
            self.boss_saucer.speed *= mult
            self.boss_bird_timer = 1.2
            self._play_boss_cry("boss_ready", volume=0.92, x=BASE_WIDTH / 2)
        else:
            self.formation.spawn_stage(content, speed_mult=mult)
            self.formation.sounds = self.sounds

    # --- Cheats (high-score menu keyboard buffer) ---
    def _feed_cheat(self, ch):
        """Accumulate alnum from the high-score menu and fire known codes."""
        self.cheat_buffer = (self.cheat_buffer + ch.upper())[-10:]
        buf = self.cheat_buffer
        lv = re.search(r"LV(\d\d)$", buf)                  # LV02 ... LV99: straight into that stage (LV00 and LV01 do nothing)
        if lv and CHEAT_MIN_STAGE <= int(lv.group(1)) <= CHEAT_MAX_STAGE:
            self._start_at_stage(int(lv.group(1)))
        elif "LIVE" in buf:
            self.used_cheat = True
            self.cheat_live = True
            self.player.infinite_lives = True
            self.player.lives = 99
            self.cheat_buffer = ""
            self.cheat_msg = t("cheat_live")
            self.cheat_kind = "live"
            self.cheat_msg_timer = 5.0
        elif "VNOV" in buf:                                # the Adventure: every scene of the visual novel, nothing saved
            self.cheat_vn = not getattr(self, "cheat_vn", False)          # (typed again: back to normal)
            if getattr(self, "story", None) is not None:
                self.story.cheat_vn = self.cheat_vn
            self.cheat_buffer = ""
            self.cheat_msg = t("cheat_vn_on" if self.cheat_vn else "cheat_vn_off")
            self.cheat_kind = "vn"
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
        self.player = Player(BASE_WIDTH // 2, BASE_HEIGHT - 95, ship_id=self._ship_for_pid(1), tint=self._tint_for_pid(1))
        self.player.sounds = self.sounds
        self.player.pid = 1
        if getattr(self, "cheat_live", False):
            self.player.infinite_lives = True
            self.player.lives = 99
        if getattr(self, "phenix_cheat", False):
            self.player.phenix_auto_refill = True
            self.player.phenix_gauge = 10
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

    def _start_gameover_card(self, after="hs", player_label=None):
        """Hold the playfield with a GAME OVER title before high scores / hot-seat hand-off."""
        self.game_over = True
        self.hs_phase = "card"
        self.go_card_t = 0.0
        self.go_card_after = after
        self.go_card_player = player_label
        self.paused = False
        self.quit_confirm = False
        self.go_rumble_acc = 0.0
        self.go_rumble_on = True
        if hasattr(self, "sounds"):
            try:
                self.sounds.play_vo("gameover_vo", volume=0.92)
            except Exception:
                log_exc("game._start_gameover_card")

    def _tick_gameover_card(self):
        self.go_card_t = float(getattr(self, "go_card_t", 0.0)) + self.dt
        self._tick_stars(follow=False)
        for exp in self.explosions[:]:
            exp.update(self.dt)
            if exp.is_finished():
                self.explosions.remove(exp)
        if self.tesla_fx is not None:
            self.tesla_fx.update(self.dt)
            if self.tesla_fx.is_finished():
                self.tesla_fx = None
        if self.shake_amount > 0:
            self.shake_amount = max(0.0, self.shake_amount - 18.0 * self.dt)
        self._tick_gameover_rumble()
        if self.go_card_t >= 2.15:
            self._finish_gameover_card()

    def _tick_gameover_rumble(self):
        """Dying pad rumble: jolts that fade out before the card ends."""
        t = float(getattr(self, "go_card_t", 0.0))
        if t >= 1.65 or not getattr(self, "go_rumble_on", False):
            if getattr(self, "go_rumble_on", False):
                self.go_rumble_on = False
                self._stop_go_rumble()
            return
        self.go_rumble_acc = float(getattr(self, "go_rumble_acc", 0.0)) + self.dt
        # Envelope 1 → 0 over 1.65s, plus a 7 Hz stutter
        fade = max(0.0, 1.0 - t / 1.65)
        fade = fade * fade
        period = 0.11 + 0.08 * (1.0 - fade)
        if self.go_rumble_acc < period:
            return
        self.go_rumble_acc = 0.0
        # Occasional missed beat so it feels like a dying motor
        if int(t * 13) % 4 == 3 and fade < 0.7:
            return
        low = 0.55 * fade
        high = 0.95 * fade
        ms = int(70 + 50 * fade)
        if t < 0.14:
            low, high, ms = 1.0, 1.0, 220
        for ship in self._ships():
            if ship is None:
                continue
            if getattr(ship, "_joy", None) is None and getattr(self, "joystick", None):
                ship._joy = self.joystick
            ship.rumble_level = int(getattr(self, "rumble_level", 3))
            ship.rumble(low, high, ms)

    def _stop_go_rumble(self):
        for ship in self._ships():
            if ship is not None:
                try:
                    ship.stop_rumble()
                except Exception:
                    log_exc("game._stop_go_rumble")

    def _skip_gameover_card(self):
        if getattr(self, "go_card_t", 0.0) >= 1.0:
            self._finish_gameover_card()

    def _finish_gameover_card(self):
        self.go_rumble_on = False
        self._stop_go_rumble()
        after = getattr(self, "go_card_after", "hs")
        self.go_card_after = "hs"
        self.hs_phase = None
        if after == "adventure":                       # the Veteran's GAME OVER is over: back to the slot list (a memorial now)
            self.game_over = False
            self._end_adventure(False)
        elif after == "switch":
            self.game_over = False
            self._hotseat_player_eliminated()
        else:
            self.game_over = True
            if self.hotseat:
                self._save_current_slot()
                if self.slots[self.current_p]:
                    self.slots[self.current_p]["eliminated"] = True
            self._begin_highscore_flow()


    def _draw_gameover_card(self, surface):
        tcard = float(getattr(self, "go_card_t", 0.0))
        dur = 2.15
        fade_in, fade_out = 0.28, 0.40
        if tcard < fade_in:
            fade = max(0.0, tcard / fade_in)
        elif tcard > dur - fade_out:
            fade = max(0.0, (dur - tcard) / fade_out)
        else:
            fade = 1.0
        pulse = 0.45 + 0.55 * abs(math.sin(tcard * 4.2))
        veil = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
        veil.fill((90, 0, 0, int((70 + 50 * pulse) * fade)))
        surface.blit(veil, (0, 0))
        # One fast sweep (~0.85 s top → bottom)
        span = BASE_HEIGHT + 48
        y = int(tcard * 920) - 24
        if -20 <= y <= BASE_HEIGHT + 20:
            pygame.draw.rect(surface, (255, 80, 60), pygame.Rect(0, y, BASE_WIDTH, 3))
            pygame.draw.rect(surface, (180, 20, 20), pygame.Rect(0, y + 4, BASE_WIDTH, 1))
        msg = t("game_over")
        col = announce.mix(announce.DANGER, (255, 110, 90), 0.5 * pulse)
        centre = (BASE_WIDTH // 2, BASE_HEIGHT // 2)
        who = getattr(self, "go_card_player", None)
        if who:
            sub = self._txt(self.medium_font, t("player_n").format(n=int(who)), (255, 200, 120))
            if fade < 0.99:
                sub = sub.copy()
                sub.set_alpha(int(255 * fade))
            pad_y = announce.LEVELS["major"]["pad"][1]
            top = centre[1] - self.big_font.get_height() // 2 - pad_y        # above the plate of the title
            surface.blit(sub, (BASE_WIDTH // 2 - sub.get_width() // 2, top - sub.get_height() - 8))
        announce.draw(self, surface, msg, "danger", "major", centre, color=col, glow=pulse, alpha=int(255 * fade))

    def _begin_highscore_flow(self):

        self.hs_entries = load_highscores()
        self.hs_submitted = False
        self.hs_just_added = []
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
            self.hs_tint = getattr(self.player, "palette", None) or self._tint_for_pid(1)
            self.hs_phase = "enter"
        else:
            self.hs_phase = "table"

    def _hs_prepare_entry(self, slot_idx):
        sl = self.slots[slot_idx]
        self.score = sl["score"]
        self.hs_slot_label = slot_idx + 1
        p = sl.get("player")
        self.hs_ship = getattr(p, "ship_id", None) or self._ship_for_pid(slot_idx + 1)
        self.hs_tint = getattr(p, "palette", None) or self._tint_for_pid(slot_idx + 1)
        self.hs_name = ["A", "A", "A"]
        self.hs_char_index = 0
        self.hs_submitted = False
        self.hs_phase = "enter"

    def _hs_prepare_coop_entry(self, ship):
        self.score = int(getattr(ship, "score", 0) or 0)
        self.hs_slot_label = int(getattr(ship, "pid", 1) or 1)
        self.hs_ship = getattr(ship, "ship_id", "phoenix")
        self.hs_tint = getattr(ship, "palette", None) or self._tint_of(self.hs_ship, int(getattr(ship, "pid", 1) or 1))
        self.hs_name = ["A", "A", "A"]
        self.hs_char_index = 0
        self.hs_submitted = False
        self.hs_phase = "enter"

    def _submit_highscore(self):
        if self.hs_submitted:
            return
        name = "".join(self.hs_name)
        ship = getattr(self, "hs_ship", None) or getattr(self.player, "ship_id", None) or "phoenix"
        tint = getattr(self, "hs_tint", None) or getattr(self.player, "palette", None)
        self.hs_entries = insert_score(
            name, self.score,
            coop=(getattr(self, "play_mode", "solo") == "coop"),
            ship=ship, ship2=None,
            veteran=(getattr(self, "difficulty", "normal") == "veteran"),
            tint=tint,
        )
        self.hs_submitted = True
        added = getattr(self, "hs_just_added", None)
        if added is None:
            added = self.hs_just_added = []
        added.append({
            "name": name[:3].upper().ljust(3, "A"),
            "score": int(self.score),
            "pid": int(getattr(self, "hs_slot_label", 1) or 1),
        })
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

    def _flip_frame(self, shake_x=0, shake_y=0, direct=False):
        """Present game_surface: SCALED 1:1, or CPU blit + cached bezels.

        direct=True : l'image a déjà été dessinée sur l'écran (voir draw())."""
        mode = getattr(self, "display_mode", "window")
        scr_size = self.screen.get_size()
        if getattr(self, "_present_size", None) != scr_size:
            self._layout_viewport()
            self._invalidate_present_cache()
            # Stored AFTER the invalidation (which resets _present_size to None):
            # otherwise the layout and the borders were redone every frame.
            self._present_size = scr_size
        vr = getattr(self, "view_rect", pygame.Rect(0, 0, BASE_WIDTH, BASE_HEIGHT))
        gpu = getattr(self, "_gpu", None)
        if (
            gpu is not None and gpu.active
            and getattr(self, "_gpu_backend", "") == "scaled"
            and not self.bezel_active
        ):
            if direct:
                if gpu.present_direct():
                    return
                # rare failure: the canvas is stale, the picture of the screen is copied back onto it
                self.game_surface.blit(self.screen, (0, 0))
            elif gpu.present(self.game_surface, vr, None, None, None, (shake_x, shake_y)):
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
            if not self._present_overwrites_screen(shake_x, shake_y):
                self.screen.fill((0, 0, 0))
            if vr.width > 0 and vr.height > 0:
                self._present_game_scaled(vr, vr.x + shake_x, vr.y + shake_y)
        pygame.display.flip()

    def _present_overwrites_screen(self, shake_x, shake_y):
        """An opaque full-window presentation makes a preceding black fill redundant."""
        if shake_x or shake_y or self.bezel_active:
            return False
        scr, gs = self.screen, self.game_surface
        if scr is None or gs is None:
            return False
        if getattr(self, "_present_size", None) != scr.get_size():
            return False
        if gs.get_flags() & pygame.SRCALPHA or gs.get_colorkey() is not None or gs.get_alpha() not in (None, 255):
            return False
        gpu = getattr(self, "_gpu", None)
        if gpu is not None and gpu.active and getattr(self, "_gpu_backend", "") == "scaled":
            return scr.get_size() == gs.get_size()
        if getattr(self, "display_mode", "window") == "window" and scr.get_size() == (BASE_WIDTH, BASE_HEIGHT):
            return True
        return getattr(self, "view_rect", None) == scr.get_rect()

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
                        log_exc("game._query_monitors_raw._cb")
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
            log_exc("game._reset_video")
        try:
            pygame.display.quit()
        except Exception:
            log_exc("game._reset_video")
        try:
            pygame.display.init()
        except Exception:
            log_exc("game._reset_video")

    def _open_display(self):
        """Create the display surface once (or recreate on Options change)."""
        return display_open.open_display(self)

    def _refocus_game_window(self):
        """Put the new SDL window back in front so the pad keeps sending events."""
        try:
            pygame.event.pump()
        except Exception:
            log_exc("game._refocus_game_window")
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
            log_exc("game._rebind_joystick")
        self.joystick = None
        self.joysticks = []
        try:
            controls.sync_game(self, rebuild=True)             # the old objects died with the window: open fresh ones
            if self.pads.pads:
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
            log_exc("game._rebind_joystick")

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
            log_exc("game._update_caption")

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
            log_exc("game.apply_display_mode")

        self._scaled_cache = None
        self._scaled_cache_size = None
        self._scaled_game_buf = None
        self._present_size = None
        try:
            self._invalidate_present_cache()
        except Exception:
            log_exc("game.apply_display_mode")
        try:
            self._layout_viewport()
        except Exception as e:
            print("layout failed:", e)
        try:
            if getattr(self, "game_surface", None) is not None:
                self.game_surface = self.game_surface.convert()
        except Exception:
            log_exc("game.apply_display_mode")
        try:
            if getattr(self, "bezel_active", False):
                self._ensure_bezel_cache()
        except Exception as e:
            print("bezel rebuild failed:", e)
        self._bezel_stars = []

    def _apply_control_pref(self):
        """The control setting (auto / keyboard / gamepad) turned into the control in use now (`input_mode`):
        keyboard = the keys; gamepad = the pad if one is plugged in; auto = whichever device was used last, and the
        pad at once when it is plugged in and nothing was used yet."""
        pref = getattr(self, "control_pref", "auto")
        have = bool(getattr(self, "pads", None) is not None and self.pads.pads)
        if pref == "keyboard" or not have:
            self.input_mode = "keyboard"
        elif pref == "gamepad":
            self.input_mode = "gamepad"
        else:
            last = getattr(self, "last_input_pad", None)
            self.input_mode = "gamepad" if (last is None or last) else "keyboard"

    def _auto_input(self):
        """A key pressed gives the control back to the keys, a button or a stick pushed gives it to the pad (control
        "auto"; a forced choice stays as it is). Only when a pad is plugged in: without one, the keys are the only choice."""
        if getattr(self, "pads", None) is None or not self.pads.pads:
            return
        self._apply_control_pref()

    def _use_pad_of(self, event):
        """Solo / hot-seat with several pads: the pad that was just used is the one that flies the ship."""
        if getattr(self, "play_mode", "solo") == "coop" and self.started:
            return
        inst = getattr(event, "instance_id", None)
        if inst is None or getattr(self, "pads", None) is None:
            return
        for pad in self.pads.pads:
            if controls.pad_id(pad) == inst:
                self.joystick = pad
                return

    def _poll_gamepad(self):
        """Hot-plug detection while on menus (and soft recovery in-game): a pad that appears or goes away."""
        was = bool(self.gamepad_detected or self.joystick)
        try:
            added, removed = controls.sync_game(self)
        except Exception:
            log_exc("game._poll_gamepad")
            added, removed = [], []
        in_run = (
            bool(getattr(self, "started", False))
            and not getattr(self, "game_over", False)
            and not getattr(self, "attract_mode", False)
        )
        if self.pads.pads:
            # A pad plugged in (on a menu, or while playing alone): it takes the control, unless the keys were forced
            if added and not was and not self.game_over and getattr(self, "play_mode", "solo") != "coop":
                self.last_input_pad = True
            self._apply_control_pref()
            if in_run and getattr(self, "play_mode", "solo") == "coop":
                self._coop_pads_changed()
            return
        lost = was or bool(removed)
        if getattr(self, "play_mode", "") == "coop":
            self._coop_drop_pads()
        if lost and in_run:
            if not getattr(self, "paused", False):
                self.paused = True
                self.pause_index = 0
                self.pause_options = False
                self.pause_help = False
                self.pause_abandon = False
                self.quit_confirm = False
            try:
                self.cheat_msg = t("pad_unplugged")
            except Exception:
                self.cheat_msg = "PAD"
            self.cheat_kind = "pad"
            self.cheat_msg_timer = 3.5
        self.last_input_pad = False
        self._apply_control_pref()

    def _coop_drop_pads(self):
        """Coop: every pad is gone, the ships that were on a pad hold no pad any more."""
        for ship in self._ships():
            if getattr(ship, "input_scheme", "") == "pad":
                ship._joy = None

    def _coop_pads_changed(self):
        """Coop, a pad came or went while playing: a ship whose pad is unplugged stops (the keys of the other player
        never move it) and the game pauses, saying which player; a pad plugged in again goes to the ship without one."""
        ships = [s for s in self._ships() if getattr(s, "input_scheme", "") == "pad"]
        lost = []
        for ship in ships:
            if getattr(ship, "_joy", None) is not None and not self.pads.has(ship._joy):
                ship._joy = None
                lost.append(ship)
        free = [p for p in self.pads.pads if not any(getattr(s, "_joy", None) is not None
                                                     and controls.pad_id(s._joy) == controls.pad_id(p) for s in ships)]
        for ship in ships:
            if getattr(ship, "_joy", None) is None and free:
                ship._joy = free.pop(0)
                if ship in lost:
                    lost.remove(ship)
        if lost and not self.paused:
            self.paused = True
            self.pause_index = 0
            self.pause_options = False
            self.pause_help = False
            self.pause_abandon = False
            self.quit_confirm = False
            n = int(getattr(lost[0], "pid", 1) or 1)
            self.cheat_msg = t("pad_unplugged_n").format(n=n)
            self.cheat_kind = "pad"
            self.cheat_msg_timer = 3.5

    def save_settings(self):

        save_user_settings({
            "control_pref": getattr(self, "control_pref", "auto"),
            "coop_p1": (getattr(self, "coop_pref", None) or ["auto", "auto"])[0],
            "coop_p2": (getattr(self, "coop_pref", None) or ["auto", "auto"])[1],
            "bindings": bindings.current.to_dict(),
            "display_mode": self.display_mode,
            "bezel_style": getattr(self, "bezel_style", "phoenix"),
            "monitor_index": int(getattr(self, "monitor_index", 0) or 0),
            "sfx_volume": self.sfx_volume,
            "music_volume": self.music_volume,
            "audio_mix": getattr(self, "audio_mix", "sfx"),
            "ingame_music": ingame_normalize(getattr(self, "ingame_music", "none")),
            "rumble_level": int(getattr(self, "rumble_level", 3)),
            "autofire": bool(getattr(self, "autofire", True)),
            "language": self.language,
            "show_fps": self.show_fps,
            "scanlines": int(getattr(self, "scanlines", 0) or 0),
            "gpu_present": bool(getattr(self, "gpu_present", True)),
            "vsync_mode": getattr(self, "vsync_mode", "adaptive"),
            "fps_cap": int(getattr(self, "fps_cap", 120) or 120),
            "season_force": str(getattr(self, "season_force", "") or ""),
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
            if getattr(self, "ship_select_locked", False):
                return
            focus = int(getattr(self, "ship_select_index", 0)) % 2
            slot = int(getattr(self, "ship_select_slot", 1) or 1)
            sid = "shield" if focus == 1 else "phoenix"
            order = self._available_tints(sid, slot)
            if order:
                cur = self._tint_of(sid, slot)
                if cur not in order:
                    cur = order[0]
                nxt = order[(order.index(cur) + (1 if direction > 0 else -1)) % len(order)]
                self.shield_slide_from = cur
                self._set_tint(sid, slot, nxt)
                self.shield_slide = 0.0
                self.shield_slide_dir = -1 if direction < 0 else 1
                return
            self.ship_select_index = (focus + direction) % 2
            self.ship_cycle_phase = "idle"
            self.ship_cycle_t = 0.0
            self.ship_cycle_first = True
            self.ship_cycle_focus = self.ship_select_index
            return
        if self.menu_screen == "jukebox":
            n = len(self._juke_catalog())
            self.juke_index = (int(getattr(self, "juke_index", 0) or 0) + direction) % n
            return
        if self.menu_screen == "story_hub":
            if getattr(self, "story", None):
                self.story.nav_v(1 if direction > 0 else -1)
            return
        if self.menu_screen == "addon":
            n = max(1, len(mame_addon.available_sets()))
            self.menu_index = (self.menu_index + direction) % n
            return
        if self.menu_screen == "main":
            n = len(main_menu.MAIN)
        elif self.menu_screen == "arcade":
            n = len(main_menu.ARCADE)
        elif self.menu_screen == "extras":
            n = len(main_menu.EXTRAS)
        elif self.menu_screen == "reset_confirm":
            n = 2  # Oui, Non
        else:
            # the options: the row of tabs (-1) then the rows of the open tab, round and round
            n = len(self._options_spec())
            self.menu_index = (self.menu_index + 1 + direction) % (n + 1) - 1
            return
        self.menu_index = (self.menu_index + direction) % n


    def _credits_scroll_axis(self):
        """-1 down (faster forward), +1 up (reverse), 0 idle."""
        down = up = False
        try:
            keys = pygame.key.get_pressed()
            down = bool(keys[pygame.K_DOWN] or keys[pygame.K_s])
            up = bool(keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_z])
        except Exception:
            log_exc("game._credits_scroll_axis")
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
                log_exc("game._credits_scroll_axis")
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
            log_exc("game._credits_x_axis")
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
                log_exc("game._credits_x_axis")
        return max(-1.0, min(1.0, v))

    def _focus_option(self, name):
        """Put the cursor on the option `name`, in its tab."""
        self.opt_tab = main_menu.tab_of(name)
        spec = self._options_spec()
        self.menu_index = spec.index(name) if name in spec else 0

    def _open_options(self, pause=False):
        """The options, on their first tab, the cursor on its first row (in the menus or from the pause)."""
        self.opt_tab = 0
        self.menu_index = 0
        self.menu_screen = "options"
        if pause:
            self.pause_options = True

    def _options_tab_step(self, direction):
        """Next / previous tab (Tab, Page Up / Down, LB / RB, or Left / Right on the row of tabs)."""
        n = len(main_menu.OPTION_TABS)
        self.opt_tab = (int(getattr(self, "opt_tab", 0) or 0) + (1 if direction > 0 else -1)) % n
        if self.menu_index >= 0:
            self.menu_index = 0

    def _open_extra(self, name):
        """A screen of EXTRAS. B / Esc brings EXTRAS back on that paragraph (see _back_to_extras)."""
        self.extras_index = main_menu.extras_index(name)
        self.menu_idle = 0.0
        if name == "highscores":
            self.hs_entries = load_highscores()
            self.menu_screen = "highscores"
            self.menu_index = 0
        elif name in ("achievements", "jukebox"):
            self._extra_enter(name)
        elif name == "credits":
            self.menu_screen = "credits"
            self.credits_scroll = float(BASE_HEIGHT)
            self.credits_from_start = True
            self.menu_index = 0
        elif name == "help":
            self.menu_screen = "help"
            self.help_manual = True                  # opened by hand: no timer, the arrows turn the page
            self.help_timer = 0.0
            self.help_page = 0
            self.help_scroll = 0.0
            self.help_transitioning = False
        elif name == "addon":
            if mame_addon.available_sets(fresh=True):
                self.menu_screen = "addon"
                self.menu_index = 0
                self.input_grace = 0.45              # the same press / key repeat must not launch the first ROM

    def _pause_confirm(self):
        """Enter / A on a row of the pause menu. True when the run was left (the caller must stop there)."""
        name = main_menu.PAUSE[self.pause_index % len(main_menu.PAUSE)]
        if name == "resume":
            self.paused = False
        elif name == "options":
            self._open_options(pause=True)
        elif name == "help":
            self._open_pause_help()
        elif getattr(self, "adventure", None):
            self.pause_abandon = True                # leaving a mission asks first (NO is lit)
            self.abandon_index = 1
        else:
            self._quit_to_menu()
            return True
        return False

    def _abandon_toggle(self):
        """Up / Down / Left / Right in the question: the other answer."""
        self.abandon_index = 1 - int(getattr(self, "abandon_index", 1) or 0)

    def _abandon_answer(self, yes):
        """Answer the question "abandon the mission?". True when the mission was left (the caller must stop there)."""
        self.pause_abandon = False
        if yes:
            self._quit_to_menu()
            return True
        return False

    def _open_pause_help(self):
        """The help (two pages), over the paused game. Left / Right turn the page, B / Esc / Enter come back."""
        self.pause_help = True
        self.help_manual = True
        self.help_timer = 0.0
        self.help_page = 0
        self.help_scroll = 0.0
        self.help_transitioning = False

    def _help_turn(self, direction):
        """The help opened from EXTRAS: Right / Down shows page 2, Left / Up page 1."""
        page = 1 if direction > 0 else 0
        if page != int(getattr(self, "help_page", 0) or 0):
            self.help_page = page
            self.help_transitioning = False
            self.help_scroll = 0.0
            self.help_timer = 0.0

    def _back_to_extras(self, name=None):
        """Back to EXTRAS, on the paragraph of `name` (or the one it was left on)."""
        if name in main_menu.EXTRAS:
            self.extras_index = main_menu.extras_index(name)
        self.menu_screen = "extras"
        self.menu_index = int(getattr(self, "extras_index", 0) or 0) % len(main_menu.EXTRAS)
        self.menu_idle = 0.0
        self.cheat_buffer = ""



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
            "control", "coop_p1", "coop_p2", "keybinds", "autofire", "sfx", "music", "audio_mix", "ingame_music", "rumble", "display",
            "bezel", "fps", "scanlines", "gpu", "vsync", "hz",
            "language", "reset_hs", "back",
        ):
            return
        x, y, w, h = box
        if key == "ingame_music":
            # its help is long (folder of the player's music) and the chosen title comes under it: the panel grows to hold both
            bf = getattr(self, "body_font", None) or self.font
            n_body = len(self._wrap_ui(t("opt_help_ingame_music"), bf, w - 36))
            h = max(h, 58 + (n_body + 3) * (bf.get_linesize() + 4) + 12 + 18)
        cache = getattr(self, "_opt_help_cache", None)
        if cache is None:
            cache = self._opt_help_cache = {}
        ckey = (key, get_lang(), w, h)
        hit = cache.get(ckey)
        if hit is None:
            panel = pygame.Surface((w, h), pygame.SRCALPHA)
            menu_ui.panel(panel, panel.get_rect())                   # the same panel as the option list
            title = t({
                "control": "opt_control", "coop_p1": "opt_coop_p1", "coop_p2": "opt_coop_p2", "keybinds": "opt_keybinds",
                "autofire": "opt_autofire", "sfx": "opt_sfx",
                "music": "opt_music", "audio_mix": "opt_audio", "ingame_music": "opt_ingame", "rumble": "opt_rumble",
                "display": "opt_display",
                "bezel": "opt_bezel", "fps": "opt_fps", "scanlines": "opt_scanlines",
                "gpu": "opt_gpu", "vsync": "opt_vsync", "hz": "opt_hz",
                "language": "opt_language", "reset_hs": "opt_reset_hs", "back": "opt_back",
            }.get(key, "options"))
            hdr = self._txt(self.font, title, (255, 210, 140))
            panel.blit(hdr, (18, 14))
            body = t("opt_help_" + key)
            yy = 58
            body_font = getattr(self, "body_font", None) or self.font
            for line in self._wrap_ui(body, body_font, w - 36):
                surf = self._txt(body_font, line, (200, 200, 230))
                panel.blit(surf, (18, yy))
                yy += body_font.get_linesize() + 4
            hit = cache[ckey] = (panel, yy)
        panel, yy = hit
        self.game_surface.blit(panel, (x, y))
        if key == "ingame_music":
            # the row shows a long title cut short: the whole title of the chosen track is read here
            body_font = getattr(self, "body_font", None) or self.font
            yy += 12
            self.game_surface.blit(self._txt(body_font, t("ingame_now"), (255, 210, 140)), (x + 18, y + yy))
            yy += body_font.get_linesize() + 4
            for line in self._wrap_ui(self._option_value("ingame_music"), body_font, w - 36)[:2]:
                _f, line = draw_frame.fit_text((body_font,), line, w - 36)
                self.game_surface.blit(self._txt(body_font, line, (235, 235, 250)), (x + 18, y + yy))
                yy += body_font.get_linesize() + 4

    OPTION_LABELS = {
        "control": "opt_control", "coop_p1": "opt_coop_p1", "coop_p2": "opt_coop_p2", "keybinds": "opt_keybinds",
        "autofire": "opt_autofire", "sfx": "opt_sfx", "music": "opt_music",
        "audio_mix": "opt_audio", "ingame_music": "opt_ingame", "rumble": "opt_rumble", "display": "opt_display",
        "bezel": "opt_bezel", "fps": "opt_fps", "scanlines": "opt_scanlines", "gpu": "opt_gpu", "vsync": "opt_vsync",
        "hz": "opt_hz", "language": "opt_language", "reset_hs": "opt_reset_hs",
    }

    def _option_label(self, key):
        return t(self.OPTION_LABELS.get(key, key))

    def _option_greyed(self, key):
        """True for a row that does nothing now (the bezels outside fullscreen)."""
        return key == "bezel" and getattr(self, "display_mode", "fullscreen") != "fullscreen"

    def _option_value(self, key):
        """The value shown for the option `key` ("" for the rows that are actions)."""
        if key == "control":
            now = t("ctrl_pad") if self.input_mode == "gamepad" else t("ctrl_kb")
            if getattr(self, "control_pref", "auto") == "auto":
                return f"{t('ctrl_auto')} ({now})"
            return now
        if key in ("coop_p1", "coop_p2"):
            return self._coop_label(0 if key == "coop_p1" else 1)
        if key == "autofire":
            return t("yes") if getattr(self, "autofire", True) else t("no")
        if key == "sfx":
            return f"{int(round(self.sfx_volume * 100))}%"
        if key == "music":
            return f"{int(round(self.music_volume * 100))}%"
        if key == "audio_mix":
            return t("audio_" + getattr(self, "audio_mix", "sfx"))
        if key == "ingame_music":
            return ingame_label(getattr(self, "ingame_music", "none"), t, asset_path)
        if key == "rumble":
            return f"{int(getattr(self, 'rumble_level', 3))} / 5"
        if key == "display":
            return {"window": t("disp_window"), "fullscreen": t("disp_fullscreen"),
                    "borderless": t("disp_borderless")}.get(self.display_mode, self.display_mode)
        if key == "bezel":
            if self._option_greyed("bezel"):
                return t("bezel_fullscreen_only")
            styles = getattr(self, "BEZEL_STYLES", [("off", "bezel_off"), ("phoenix", "bezel_phoenix")])
            return t({k: v for k, v in styles}.get(getattr(self, "bezel_style", "phoenix"), "bezel_phoenix"))
        if key == "fps":
            return t("yes") if self.show_fps else t("no")
        if key == "scanlines":
            sl = int(getattr(self, "scanlines", 0) or 0)
            return "OFF" if sl <= 0 else str(sl)
        if key == "gpu":
            return t("yes") if getattr(self, "gpu_present", True) else t("no")
        if key == "vsync":
            return t("vsync_" + getattr(self, "vsync_mode", "adaptive"))
        if key == "hz":
            return f"{int(getattr(self, 'fps_cap', 120))} Hz"
        if key == "language":
            return next((n for c, n in LANGS if c == self.language), self.language)
        return ""

    def _device_label(self, device):
        if device == controls.KB_LEFT:
            return t("ctrl_kb_left")
        if device == controls.KB_ARROWS:
            return t("ctrl_kb_arrows")
        return t("ctrl_pad_n").format(n=int(device[3:]))

    def _coop_label(self, i):
        """What the coop option of player i+1 shows: the device it will use, "Auto (...)" when it is not fixed."""
        pref = list(getattr(self, "coop_pref", None) or [controls.AUTO, controls.AUTO])
        devices = controls.resolve_coop(pref[0], pref[1], len(self.pads.pads))
        label = self._device_label(devices[i])
        if pref[i] == devices[i]:
            return label
        return f"{t('ctrl_auto')} ({label})"

    def _option_fill(self, key):
        """0..1 for the rows drawn as a gauge (volumes, vibrations), else None."""
        if key == "sfx":
            return float(self.sfx_volume)
        if key == "music":
            return float(self.music_volume)
        if key == "rumble":
            return int(getattr(self, "rumble_level", 3)) / 5.0
        return None

    def _options_labels(self):
        """One text per row of the open tab ("label :  <  value  >", or the label alone for an action)."""
        out = []
        for key in self._options_spec():
            value = self._option_value(key)
            out.append(f"{self._option_label(key)} :  <  {value}  >" if value else self._option_label(key))
        return out

    def _options_spec(self):
        """The option ids of the open tab (src/main_menu.py, OPTION_TABS)."""
        return main_menu.tab_rows(getattr(self, "opt_tab", 0) or 0)

    def _menu_adjust(self, direction):
        """direction: -1 left, +1 right — change current option value"""
        return menu_actions.menu_adjust(self, direction)

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
        return credits_screen.credits_layout(self)

    def _tick_stars(self, follow=False):
        """Starfield step with comet rules (cycle / menu)."""
        px = py = None
        free = bool((getattr(self, "adventure", None) or {}).get("asteroids")) and bool(getattr(self, "started", False))
        if follow and getattr(self, "player", None) is not None:
            px = self.player.x
            py = self.player.y if free else None
            if free and getattr(self.player, "asteroid_mode", False):
                # the ship wraps around the screen: the background follows its real movement (x and y), not the jump
                # of the wrap
                lx = getattr(self, "_ast_last_x", None)
                ly = getattr(self, "_ast_last_y", None)
                if lx is not None and ly is not None:
                    self._ast_px = getattr(self, "_ast_px", px) + ((px - lx + BASE_WIDTH / 2) % BASE_WIDTH - BASE_WIDTH / 2)
                    self._ast_py = getattr(self, "_ast_py", py) + ((py - ly + BASE_HEIGHT / 2) % BASE_HEIGHT - BASE_HEIGHT / 2)
                else:
                    self._ast_px, self._ast_py = px, py
                self._ast_last_x, self._ast_last_y = px, py
                px, py = self._ast_px, self._ast_py
        self.starfield.set_free(free)             # the Asteroids mission: the background only follows the ship
        menu = not bool(getattr(self, "started", False))
        stage = int(getattr(self, "stage", 1) or 1) if not menu else 0
        self.starfield.update(self.dt, px, stage=stage, menu=menu, player_y=py)

    def _addon_snap(self, set_name):
        cache = getattr(self, "_addon_snaps", None)
        if cache is None:
            self._addon_snaps = cache = {}
        if set_name in cache:
            return cache[set_name]
        img = None
        fp = mame_addon.snap_path(set_name)
        if fp:
            try:
                raw = pygame.image.load(fp).convert()
                box = (400, 280)
                scale = min(box[0] / max(1, raw.get_width()), box[1] / max(1, raw.get_height()))
                nw = max(1, int(raw.get_width() * scale))
                nh = max(1, int(raw.get_height() * scale))
                img = pygame.transform.smoothscale(raw, (nw, nh))
            except Exception:
                img = None
        cache[set_name] = img
        return img

    def _tick_addon_clip(self, dt):
        sets = mame_addon.available_sets()
        sid = ""
        if sets:
            i = int(getattr(self, "menu_index", 0) or 0) % len(sets)
            sid = sets[i][0]
        if sid != getattr(self, "_addon_clip_sid", ""):
            self._addon_clip_stop()
            self._addon_clip_sid = sid
            self._addon_clip_t = 0.0
            self._addon_clip_path = mame_addon.video_path(sid) if sid else None
        self._addon_clip_t = float(getattr(self, "_addon_clip_t", 0.0)) + dt
        if self._addon_clip_t >= 1.0 and getattr(self, "_addon_clip_path", None):
            self._addon_clip_start()
        clip = getattr(self, "_addon_clip", None)
        if clip is not None:
            clip.pump()

    def _addon_clip_start(self):
        if getattr(self, "_addon_clip", None) is not None:
            return
        path = getattr(self, "_addon_clip_path", None)
        if not path:
            return
        self._addon_clip = _AddonClip(path, (400, 280))

    def _addon_clip_stop(self):
        clip = getattr(self, "_addon_clip", None)
        self._addon_clip = None
        if clip is not None:
            clip.close()

    def _addon_clip_frame(self):
        clip = getattr(self, "_addon_clip", None)
        if clip is None:
            return None
        return clip.surface

    def _draw_addon_menu(self, surface):
        hdr = self._txt(self.medium_font, t("addon"), menu_ui.TITLE)
        surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 40))
        sets = mame_addon.available_sets()
        if not sets:
            # nothing installed: the message alone, in a panel (no empty preview frame)
            empty = self._txt(self.font, t("addon_missing"), (190, 190, 210))
            box = pygame.Rect(0, 0, empty.get_width() + 80, empty.get_height() + 50)
            box.center = (BASE_WIDTH // 2, BASE_HEIGHT // 2 - 20)
            menu_ui.panel(surface, box)
            surface.blit(empty, (box.centerx - empty.get_width() // 2, box.centery - empty.get_height() // 2))
        else:
            # the list and the preview side by side, same top, same height, the pair centred on the screen
            fams = [mame_addon.family_of(sid) for sid, _label in sets]
            gaps = sum(1 for a, b in zip(fams, fams[1:]) if a != b)
            list_w, prev_w, gap, top = 650, 480, 28, 110
            height = max(380, len(sets) * 32 + gaps * 16 + 40)
            x0 = (BASE_WIDTH - (list_w + gap + prev_w)) // 2
            box = menu_ui.panel(surface, pygame.Rect(x0, top, list_w, height))
            frame = menu_ui.panel(surface, pygame.Rect(box.right + gap, top, prev_w, height))
            list_x = box.x + 30
            y = box.y + 20
            focus = None
            prev_fam = None
            for i, (sid, label) in enumerate(sets):
                fam = mame_addon.family_of(sid)
                if prev_fam is not None and fam != prev_fam:
                    y += 16
                prev_fam = fam
                selected = (i == self.menu_index)
                if selected:
                    focus = sid
                    menu_ui.highlight(surface, pygame.Rect(box.x + 12, y, box.w - 24, 32))
                surf = self._txt(self.font, label, menu_ui.row_colour(selected))
                surface.blit(surf, (list_x, y + 16 - surf.get_height() // 2))
                y += 32
            if focus:
                snap = self._addon_clip_frame()
                if snap is None:
                    snap = self._addon_snap(focus)
                if snap is not None:
                    surface.blit(snap, (frame.centerx - snap.get_width() // 2,
                                       frame.centery - snap.get_height() // 2))
        hint_bar.draw_for(self, surface)

    def _draw_logo(self, surface, center_x, top_y, ox=0.0, oy=0.0, angle=0.0):
        """Draw current animated logo frame centered horizontally."""
        if not self.logo_frames:
            return False
        img = self.logo_frames[self.logo_index % len(self.logo_frames)]
        if angle:
            img = pygame.transform.rotozoom(img, angle, 1.0)
        surface.blit(img, (int(center_x + ox - img.get_width() // 2),
                           int(top_y + oy)))
        return True

    def _april_fool_ok(self):
        """1 April, or season.txt = april / poisson (test)."""
        force = self._read_season_force()
        if force in ("april", "poisson", "1avril", "avril"):
            return True
        now = datetime.now()
        return now.month == 4 and now.day == 1

    def _update_april_gag(self, dt):
        """Boot-only title logo gag. Runs once."""
        return april_gag.update_april_gag(self, dt)

    def _read_season_force(self, user=None):
        """season.txt wins, then settings.json. Not wiped by empty defaults."""
        for flag in (
            os.path.join(project_root(), "season.txt"),
            os.path.join(user_data_dir(), "season.txt"),
        ):
            try:
                if os.path.isfile(flag):
                    val = open(flag, encoding="utf-8").read().strip().lower()
                    if val:
                        return val
            except Exception:
                log_exc("game._read_season_force")
        if user and user.get("season_force"):
            return str(user.get("season_force") or "").lower()
        return str(getattr(self, "season_force", "") or "").lower()

    def _season_id(self):
        """Title-screen only. season.txt / season_force / calendar."""
        force = self._read_season_force()
        if force in ("xmas", "christmas", "noel"):
            return "xmas"
        if force in ("halloween", "hallo"):
            return "halloween"
        now = datetime.now()
        if (now.month == 10 and now.day >= 24) or (now.month == 11 and now.day == 1):
            return "halloween"
        if now.month == 12 or (now.month == 1 and now.day <= 6):
            return "xmas"
        return None

    def _ensure_season_bits(self, theme):
        if getattr(self, "_season_theme", None) == theme and getattr(self, "_season_bits", None) is not None:
            return
        self._season_theme = theme
        bits = []
        if theme == "xmas":
            for i in range(70):
                bits.append({
                    "k": "snow",
                    "x": random.uniform(0, BASE_WIDTH),
                    "y": random.uniform(0, BASE_HEIGHT),
                    "s": random.choice((1, 1, 2, 2, 3)),
                    "vy": random.uniform(18, 48),
                    "vx": random.uniform(-8, 8),
                })
        self._season_bits = bits

    def _update_season(self, dt):
        theme = self._season_id()
        if not theme:
            self._season_bits = []
            self._season_theme = None
            return
        self._ensure_season_bits(theme)
        for b in self._season_bits:
            if b["k"] == "snow":
                b["y"] += b["vy"] * dt
                b["x"] += b["vx"] * dt + math.sin(b["y"] * 0.04) * 8 * dt
                if b["y"] > BASE_HEIGHT:
                    b["y"] = -4
                    b["x"] = random.uniform(0, BASE_WIDTH)

    def _season_load_corners(self, prefix):
        cache = f"_{prefix}_corners"
        corners = getattr(self, cache, None)
        if corners is None:
            corners = {}
            for key in ("tl", "tr", "bl", "br"):
                fp = asset_path("sprites", "season", f"{prefix}_{key}.png")
                if os.path.isfile(fp):
                    try:
                        corners[key] = pygame.image.load(fp).convert_alpha()
                    except Exception:
                        log_exc("game._season_load_corners")
            setattr(self, cache, corners)
        return corners

    def _season_load_png(self, attr, filename):
        img = getattr(self, attr, None)
        if img is False:
            return None
        if img is None:
            fp = asset_path("sprites", "season", filename)
            if os.path.isfile(fp):
                try:
                    img = pygame.image.load(fp).convert_alpha()
                except Exception:
                    img = False
            else:
                img = False
            setattr(self, attr, img)
        return img if img else None

    def _season_blit_corners(self, surface, corners):
        if "tl" in corners:
            surface.blit(corners["tl"], (0, 0))
        if "tr" in corners:
            img = corners["tr"]
            surface.blit(img, (BASE_WIDTH - img.get_width(), 0))
        if "bl" in corners:
            img = corners["bl"]
            surface.blit(img, (0, BASE_HEIGHT - img.get_height()))
        if "br" in corners:
            img = corners["br"]
            surface.blit(img, (BASE_WIDTH - img.get_width(), BASE_HEIGHT - img.get_height()))

    def _draw_season_title(self, surface):
        """Corner overlay on the main menu only."""
        theme = getattr(self, "_season_theme", None) or self._season_id()
        if theme:
            self._season_theme = theme
            self._ensure_season_bits(theme)
        if not theme:
            return
        if theme == "xmas":
            sack = self._season_load_png("_xmas_sack", "xmas_sack.png")
            if sack:
                surface.blit(sack, (148, BASE_HEIGHT - sack.get_height() - 10))
            self._season_blit_corners(surface, self._season_load_corners("xmas"))
            for b in self._season_bits:
                if b["k"] == "snow":
                    pygame.draw.circle(surface, (230, 238, 255), (int(b["x"]), int(b["y"])), int(b["s"]))
        elif theme == "halloween":
            bat = self._season_load_png("_hallo_bat", "hallo_bat.png")
            if bat:
                surface.blit(bat, (108, 72))
            self._season_blit_corners(surface, self._season_load_corners("hallo"))

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
        return help_screen.build_help_icons(self)


    def _draw_help_page(self, surface, page, y_off):
        """Draw help page 0 (scenario/points) or 1 (PHENIX). y_off shifts content."""
        return help_screen.draw_help_page(self, surface, page, y_off)

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
        return attract_ai.attract_ai(self)


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
        tint = "red" if sid == "shield" else "argent"
        if sid == "shield":
            self.shield_tint = "red"
        else:
            self.phoenix_tint = "argent"
        self.player = Player(BASE_WIDTH // 2, BASE_HEIGHT - 95, ship_id=sid, tint=tint)
        self.player.sounds = self.sounds
        self.player.lives = 5
        self.ship_id = sid
        self.ship_id_p1 = sid
        if hasattr(self, "_rebuild_life_icon"):
            try:
                self._rebuild_life_icon()
            except Exception:
                log_exc("game._start_attract")
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
            if getattr(self, "help_manual", False):
                self.help_manual = False
                self._back_to_extras("help")         # opened from EXTRAS: back there
            else:
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
        self.pause_help = False
        self.pause_abandon = False
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
            log_exc("game._paint_menu_frame")

    def _quit_to_menu(self):
        """Leave current run, return to main menu (keep settings)."""
        self.sounds.stop_sfx("saucer_pass", 150)
        back_story = False
        toast = ""
        toast_kind = "info"
        story_slot = None
        story_pane = "map"
        if getattr(self, "adventure", None) and getattr(self, "story", None):
            story_slot = self.story.slot_no
            try:
                if self.stage_transition == "fly_up":
                    # the mission was already won: bank it
                    self.story.apply_result(self.adventure.get("id"), int(self.score), True,
                                            self.adventure.get("kills"), loot=self.adventure.get("loot"),
                                            used=self.adventure.get("items"),
                                            flawless=not self.adventure.get("life_lost"))
                    toast = self.story.toast
                    toast_kind = self.story.toast_kind
                else:
                    # leaving a mission by choice: nothing gained, nothing lost, back to the hangar
                    story_pane = "hangar"
            except Exception:
                log_exc("game._quit_to_menu")
            self.adventure = None
            back_story = True
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
        self.pause_help = False
        self.pause_abandon = False
        if back_story:
            self.menu_screen = "story_hub"
            self.menu_index = 1
            if getattr(self, "story", None):
                if story_slot:
                    # the new Game forgot the open slot; the result is already saved
                    self.story.resume(story_slot, toast, story_pane, toast_kind)
                else:
                    self.story.pane = story_pane
                    self.story.toast = toast
                    self.story.toast_kind = toast_kind
        else:
            self.menu_screen = "main"
            self.menu_index = 0
        self.input_grace = 0.35  # absorb the confirm key/button that quit the run
        self.player.infinite_lives = False
        self.cheat_live = False
        self.phenix_cheat = False
        self.used_cheat = False
        try:
            self.sounds.play_music("menu", fade_ms=getattr(self.sounds, "MENU_RETURN_MS", 900))
        except Exception:
            log_exc("game._quit_to_menu")
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

    def _wait_mame_pad_idle(self, ms=1500):
        """Do not refocus while Guide/Start/Select is still down (Windows window-switch)."""
        import pygame
        t = 0
        while t < ms:
            try:
                if mame_addon.xinput_pad_idle():
                    break
            except Exception:
                break
            pygame.time.wait(50)
            t += 50

    def _wait_mame_quit(self, proc, set_name=""):
        """Wait for MAME. XInput poll for quit + Spectrum Pheenix keys."""
        import pygame
        spec = None
        while proc.poll() is None:
            pygame.event.pump()
            if set_name == "spectrum_pheenix":
                try:
                    spec = mame_addon.spectrum_input_tick(spec)
                except Exception:
                    log_exc("game._wait_mame_quit")
            try:
                if mame_addon.xinput_quit_combo():
                    try:
                        show_cover()
                    except Exception:
                        log_exc("game._wait_mame_quit")
                    try:
                        proc.terminate()
                    except Exception:
                        log_exc("game._wait_mame_quit")
                    pygame.time.wait(250)
                    if proc.poll() is None:
                        try:
                            proc.kill()
                        except Exception:
                            log_exc("game._wait_mame_quit")
                    self._wait_mame_pad_idle()
                    break
            except Exception:
                log_exc("game._wait_mame_quit")
            pygame.time.wait(32)

    def _release_joystick_for_mame(self):
        """Drop SDL joystick so MAME can open XInput/DInput."""
        for attr in ("joystick",):
            js = getattr(self, attr, None)
            if js is not None:
                try:
                    js.quit()
                except Exception:
                    log_exc("game._release_joystick_for_mame")
            setattr(self, attr, None)
        extra = getattr(self, "joysticks", None) or []
        for js in extra:
            try:
                js.quit()
            except Exception:
                log_exc("game._release_joystick_for_mame")
        self.joysticks = []
        if getattr(self, "pads", None) is not None:
            self.pads.clear()

    def _launch_addon(self):
        """Run local MAME on the focused ROM, hide the console, wait, come back."""
        return addon_launch.launch_addon(self)

    def _menu_back(self):

        """B / Esc — return to previous menu screen."""
        if self.menu_screen == "main":
            return
        if self.menu_screen == "reset_confirm":
            self.menu_screen = "options"
            self._focus_option("reset_hs")
        elif self.menu_screen == "ship_select":
            if getattr(self, "ship_select_locked", False):
                self.ship_select_locked = False
                self._pending_after_welcome = None
                return
            if int(getattr(self, "ship_select_slot", 1) or 1) == 2:
                self._open_ship_select(1)
            else:
                self.menu_screen = "arcade"            # back to the mode and the difficulty
                self.menu_index = len(main_menu.ARCADE) - 1
        elif self.menu_screen == "story_hub":
            if getattr(self, "story", None) and self.story.back():
                spec = self.story.take_launch_request()
                if isinstance(spec, dict) and spec.get("launch"):
                    self._request_adventure(spec)    # the first sortie gets its controls briefing before takeoff
                return              # one step back inside the Adventure (hangar -> slot list ...)
            self.menu_screen = "main"
            self.menu_index = main_menu.main_index("story")
        elif self.menu_screen == "addon":
            self._back_to_extras("addon")
        elif self.menu_screen == "options":
            self.menu_screen = "main"
            self.menu_index = main_menu.main_index("options")
        elif self.menu_screen == "arcade":
            self.menu_screen = "main"
            self.menu_index = main_menu.main_index("play")
        elif self.menu_screen == "extras":
            self.menu_screen = "main"
            self.menu_index = main_menu.main_index("extras")
        elif self.menu_screen in ("highscores", "achievements"):
            if self.menu_screen == "achievements":
                self.ach_data = load_achievements()
            self._back_to_extras(self.menu_screen)   # back on its paragraph of EXTRAS
        elif self.menu_screen == "jukebox":
            self._close_jukebox()
        elif self.menu_screen == "credits":
            self._back_to_extras("credits")
        elif self.menu_screen == "help":
            self._reset_menu_idle()
        else:
            self.menu_screen = "main"
            self.menu_index = 0

    def _menu_confirm(self):
        return menu_actions.menu_confirm(self)

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
            self.cheat_msg = "SCREENSHOT"
            self.cheat_kind = "system"
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
                log_exc("game.handle_events")
            events = []
        for event in events:
            if event.type == pygame.QUIT:
                self._quit_app()
            elif event.type in (getattr(pygame, "JOYDEVICEADDED", -1), getattr(pygame, "JOYDEVICEREMOVED", -2)):
                self._poll_gamepad()
            elif getattr(self, "fade_phase", None) and event.type not in (
                pygame.QUIT,
                getattr(pygame, "JOYDEVICEADDED", -1),
                getattr(pygame, "JOYDEVICEREMOVED", -2),
            ):
                if event.type == pygame.KEYDOWN and event.key == pygame.K_F12:
                    self.take_screenshot()
                continue
            elif self._anchor_blocks(event):
                continue
            elif event.type == pygame.KEYUP:
                input_events.on_keyup(self, event)
            elif event.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION, pygame.JOYAXISMOTION):
                # the help bar shows the buttons of the device used last (a stick that drifts back to rest is not a choice)
                if event.type == pygame.KEYDOWN:
                    self.last_input_pad = False
                    self._auto_input()
                elif not (event.type == pygame.JOYAXISMOTION and abs(getattr(event, "value", 0.0)) < 0.5):
                    self.last_input_pad = True
                    self._use_pad_of(event)
                    self._auto_input()
                before = menu_sfx.safe_snapshot(self) if menu_sfx.watching(self, event) else None
                screen_before = menu_fx.screen_key(self) if before is not None else None
                started_before = bool(self.started)
                if event.type == pygame.KEYDOWN:
                    input_events.on_keydown(self, event)
                elif event.type == pygame.JOYBUTTONDOWN:
                    input_events.on_joy_button(self, event)
                elif event.type == pygame.JOYHATMOTION:
                    input_events.on_joy_hat(self, event)
                else:
                    input_events.on_joy_axis(self, event)
                if before is not None:
                    kind = menu_sfx.kind_of(self, event)
                    menu_sfx.react(self, before, menu_sfx.safe_snapshot(self), kind)
                    try:
                        menu_fx.note(self, screen_before, started_before, kind, event)   # the screen slides in
                    except Exception:
                        log_exc("game.handle_events")

    def _anchor_blocks(self, event):
        """While the vortex and the flash are on screen the map is not in sight: keys do nothing, except that a confirm /
        back key or a pad button skips to the end of the flash (and F12 still takes a screenshot)."""
        fx = getattr(self, "anchor_fx", None)
        if fx is None or fx.phase not in ("swirl", "flash"):
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F12:
                self.take_screenshot()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_ESCAPE):
                fx.skip()
        elif event.type == pygame.JOYBUTTONDOWN:
            fx.skip()
        return event.type in (pygame.KEYDOWN, pygame.KEYUP, pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION,
                              pygame.JOYAXISMOTION)

    # --- Simulation step ---
    def _sync_invader_voices(self):
        """The saucer sound belongs to the saucer on screen: it follows it (stereo), waits while the game is
        paused and stops when the saucer is gone or the game is no longer running the invasion."""
        f = getattr(self, "formation", None)
        m = getattr(f, "mothership", None)
        running = (bool(getattr(self, "adventure", None)) and self.started and not self.game_over
                   and self.stage_transition is None)
        here = m is not None and m.alive and not m.dying and running
        self.sounds.follow_voice("saucer_pass", x=getattr(m, "x", None), alive=here, paused=bool(self.paused))

    def update(self):
        update_idle.tick_housekeeping(self)
        self._sync_invader_voices()
        
        if self.game_over and getattr(self, "hs_phase", None) == "card":
            self.sounds.play_electric(False)
            self._tick_gameover_card()
            return

        if not self.started or self.game_over:
            update_idle.tick_menu_or_gameover(self)
            return
        
        if self.paused:
            self._tick_stars(follow=False)
            self.sounds.play_electric(False)
            if getattr(self, "pause_help", False):
                self.help_anim_t += self.dt            # the ships of the help page move
            return

        if getattr(self, "hotseat_pick_p2", False):
            update_idle.tick_hotseat_pick_p2(self)
            return
        if self.hotseat_wait:
            self._tick_stars(follow=False)
            self.sounds.play_electric(False)
            return

        if self.hotseat_hold > 0:
            update_idle.tick_hotseat_hold(self)
            return
            
        hs = float(getattr(self, "hitstop", 0.0) or 0.0)
        if hs > 0 and self.stage_transition is None:
            self.hitstop = max(0.0, hs - self.dt)
            return

        update_play.tick_ships(self)
        
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
            elif not any(p.alive for p in self._ships()) or escort.failed(self):
                if getattr(self, "adventure", None):
                    if self._veteran_adventure():
                        # a fallen Veteran gets the real GAME OVER of the game (explosion, card, voice), then the slot list.
                        # The fall is written down at once: closing the game during the card does not save him.
                        self._bank_adventure(False)
                        self._hotseat_arm_hold("adventure_over", self.HOTSEAT_HOLD_FINAL)
                        return
                    self._end_adventure(False)
                    return
                if self.hotseat:
                    self._hotseat_arm_hold("eliminated", self.HOTSEAT_HOLD_FINAL)
                else:
                    self._hotseat_arm_hold("gameover", self.HOTSEAT_HOLD_FINAL)
                return
        
        # Starfield with parallax based on player movement
        self._tick_stars(follow=True)
        neb = getattr(self.starfield, "nebula", None)
        if neb is not None and "pleiades" in str(getattr(neb, "kind", "")):
            nid = id(neb)
            if nid != getattr(self, "_pleiades_seen_id", None):
                self._pleiades_seen_id = nid
                self._note_scalable("pleiades")
        if getattr(self, "play_mode", "") == "coop":
            ships = [s for s in self._ships() if s and s.alive]
            both = len(ships) >= 2 and all(getattr(s, "is_phenix", False) for s in ships)
            if both and not getattr(self, "_duo_latched", False):
                self._duo_latched = True
                self._note_scalable("duo_fire")
            elif not both:
                self._duo_latched = False
        
        # Stage transition: ship flies off top
        if self.stage_transition == "fly_up":
            update_play.tick_fly_up(self)
            return
        
        if self.stage_transition == "arrive":
            update_play.tick_arrive(self)
            return
        
        if isinstance(self.formation, GuardianFormation):
            self.formation.update(self.dt, self.player.x, self.player.y)
        else:
            self.formation.update(self.dt, self.player.x)
        escort.tick(self)                         # the VIP rescue: the cruise ship (nothing in any other mission)
        asteroids.tick(self)                      # the Asteroids mission: rocks, saucer, shots (nothing elsewhere)
        update_play.tick_loot(self)
        self._drain_detach_pops()
        self._check_extra_lives()
        if self.life_flash_timer > 0:
            self.life_flash_timer = max(0.0, self.life_flash_timer - self.dt)
        
        # --- Stage 5 boss ---
        if self.boss_saucer is not None and self.boss_saucer.alive:
            update_play.tick_boss_saucer(self)
        
        # Stage clear → fly to next stage (non-boss content)
        content = stage_content(self.stage)
        if (self.stage_transition is None and content != 5
                and self.formation.all_dead()
                and not any(s.dying for s in self._ships())
                and not update_play.loot_holds_the_clear(self)     # the reactor of a BONUS mission falls before the end
                and self.boss_saucer is None):
            update_play.begin_stage_clear(self)
            return
        
        # Boss killed → cataclysmic saucer explosion, kill all birds, then fly up
        if (self.boss_saucer is not None and not self.boss_saucer.alive
                and self.stage_transition is None and not self.game_over):
            update_play.boss_cataclysm(self)
        
        if self.stage_transition == "boss_outro":
            update_play.tick_boss_outro(self)
            return
        
        # Player bullet(s) vs Enemies / Boss
        update_play.player_bullets_vs_mothership(self)
        update_play.player_bullets_vs_enemies(self)

        # Unbroken saucer brick hits the bottom of the screen → game over
        update_play.boss_floor_check(self)

        # Enemy attacks vs Player(s) — ships do not collide with each other
        update_play.enemy_attacks_vs_players(self)

        update_play.tick_effects_and_hotseat(self)

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
        """The CRT scanline layers of the current level (src/crt.py), built once for the canvas they go on; returns
        the multiply overlay (None at level 0). `_scanline_layers` keeps the rest (the glow of levels 2 and 3)."""
        level = int(getattr(self, "scanlines", 0) or 0)
        if level <= 0:
            return None
        gs = getattr(self, "_direct_restore", None)  # vrai canevas pendant un dessin direct
        if gs is None:
            gs = getattr(self, "game_surface", None)
        key = (level, BASE_WIDTH, BASE_HEIGHT, id(gs) if gs is not None else 0)
        if self._scanline_surf is not None and getattr(self, "_scanline_key", None) == key:
            return self._scanline_surf
        layers = crt.build(level, (BASE_WIDTH, BASE_HEIGHT), gs)
        self._scanline_layers = layers
        self._scanline_surf = layers["mask"] if layers else None
        self._scanline_key = key
        self._scanline_level_cached = level
        return self._scanline_surf

    def draw(self):
        # Dessin direct : quand la copie du canevas vers l'écran recouvrirait tout
        # l'écran (chemin SCALED, sans bordures ni secousse, même taille et même
        # format), on dessine tout de suite sur l'écran et on évite cette copie
        # (~5 Mo par image). Même image, mêmes pixels.
        shaking = bool(self.shake_amount > 0 and self.started
                       and (not self.game_over or self.hs_phase == "card"))
        direct = (not shaking) and self._direct_draw_ok()
        if direct:
            canvas = self.game_surface
            self._direct_restore = canvas
            self.game_surface = self.screen
        try:
            shake_x, shake_y = self._draw_canvas()
        finally:
            if direct:
                self.game_surface = canvas
                self._direct_restore = None
        # Present — GPU upscale when bound, else CPU scale
        self._flip_frame(shake_x, shake_y, direct)

    def _direct_draw_ok(self):
        gpu = getattr(self, "_gpu", None)
        if gpu is None or not gpu.active or getattr(self, "_gpu_backend", "") != "scaled":
            return False
        if not self._present_overwrites_screen(0, 0):
            return False
        scr, gs = self.screen, self.game_surface
        if scr is gs or pygame.display.get_surface() is not scr:
            return False
        if scr.get_masks() != gs.get_masks() or scr.get_bitsize() != gs.get_bitsize():
            return False
        if scr.get_flags() & pygame.SRCALPHA or scr.get_colorkey() is not None:
            return False
        return True

    def _paint_menus(self):
        draw_frame.draw_menu_title(self)
        draw_frame.draw_menu_screens(self)
        draw_frame.draw_menu_footer(self)

    def _draw_canvas(self):
        self._announce_done = False
        story = getattr(self, "story", None)
        if not (not self.started and self.menu_screen == "story_hub" and story is not None
                and story.covers_screen()):
            draw_frame.draw_background(self)       # (a full-screen slide paints over it anyway)
        
        shake_x = shake_y = 0
        if self.shake_amount > 0 and self.started and (not self.game_over or self.hs_phase == "card"):
            shake_x = random.randint(-int(self.shake_amount), int(self.shake_amount))
            shake_y = random.randint(-int(self.shake_amount), int(self.shake_amount))
        
        if self.started and (not self.game_over or self.hs_phase == "card"):
            draw_frame.draw_play(self)
        
        # Title / Menu Screen
        if not self.started:
            if menu_fx.active(self) and not self.quit_confirm:
                menu_fx.draw_sliding(self, self._paint_menus)      # a new screen slides in (src/menu_fx.py)
            else:
                self._paint_menus()
        
        # High score / Game Over screens
        if self.game_over and self.hs_phase == "card":
            self._draw_gameover_card(self.game_surface)
        elif self.game_over and self.hs_phase:
            overlay = self._dim_overlay(180)
            self.game_surface.blit(overlay, (0, 0))
            
            if self.hs_phase == "enter":
                draw_frame.draw_hs_enter(self)
            
            elif self.hs_phase == "table":
                draw_frame.draw_hs_table(self)

        draw_frame.draw_hotseat_overlays(self)
        
        if not self._present_overwrites_screen(shake_x, shake_y):
            self.screen.fill((0, 0, 0))

        # Pause overlay
        if self.paused and self.started and not self.game_over:
            draw_frame.draw_pause(self)
        
        # Quit game confirm (menus)
        if self.quit_confirm and not self.started:
            draw_frame.draw_quit_confirm(self)

        # FPS counter (top-right) — refresh text ~4 Hz to avoid constant render
        if self.show_fps and not (self.started and (not self.game_over or self.hs_phase == "card")):
            draw_frame.draw_fps_counter(self)

        fx = getattr(self, "anchor_fx", None)
        if fx is not None and not self.started:
            fx.draw(self.game_surface)             # the return to base: over the map, before the CRT effects

        draw_frame.draw_post_effects(self)

        # Toast last so menus / credits / hauts faits can show unlocks (in a run, it is a layer of the scene already)
        if not self._announce_done:
            self._draw_cheat_message()
        
        self._draw_screen_fade()
        return shake_x, shake_y

    # --- Main loop ---
    def run(self):
        if not getattr(self, "_intro_done", False):
            play_intro(self)
            self._intro_done = True
            self.input_grace = 0.45
            self.menu_idle = 0.0
            self.fade_t = 1.0
            self.fade_phase = "in"
            self.fade_action = None
            self.FADE_SEC = 0.50
        self._pacer = FramePacer()
        while self.running:
            cap = int(getattr(self, "fps_cap", getattr(self, "fps_target", 60)) or 60)
            panel = int(getattr(self, "panel_hz", 60) or 60)
            # VSync On: never present faster than the panel (60 Hz screen + 120 cap = 60).
            if getattr(self, "vsync_mode", "adaptive") == "on":
                cap = min(cap, panel)
            # Limiteur exact (Clock.tick(n) attend un nombre entier de ms : 144 -> ~166 i/s).
            # clock.tick() sans limite sert seulement à tenir à jour le compteur d'images/s.
            real = self._pacer.wait(cap)
            ticked = self.clock.tick() / 1000.0
            self.dt = ticked if real is None else real
            # Safety clamp (spiral of death protection)
            self.dt = min(self.dt, 0.05)
            
            try:
                self.handle_events()
                self.update()
                self.draw()
            except Exception:
                import traceback
                tb = traceback.format_exc()
                print(tb)
                try:
                    log = os.path.join(user_data_dir(), "crash.log")
                    with open(log, "a", encoding="utf-8") as fh:
                        fh.write(tb + "\n")
                except Exception:
                    log_exc("game.run")
                self.running = False

        pygame.quit()
        sys.exit(0)
