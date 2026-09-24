"""
SFX and music manager (SDL_mixer via pygame).

SFX are WAV samples under assets/sounds/.
Announcer VO (level1–15, welcome_phoenix / welcome_shield) uses reserved mixer channel 0.
Music tracks are MP3 under assets/music/ with short cross-fades between
menu theme, game-over theme, credits theme, and in-game silence.

Loop behaviour:
- Tracks loop natively (play(-1)) so we never reload an MP3 mid-session.
- Theme changes still cross-fade. Credits keeps a long end-fade only when
  leaving that screen, not a disk reload every loop.
"""
import pygame
import os
import math

from settings import asset_path, BASE_WIDTH
SOUND_DIR = asset_path("sounds")
MUSIC_DIR = asset_path("music")


class SoundManager:
    FADE_MS = 350          # crossfade when switching themes
    MENU_RETURN_MS = 900   # quit run → title
    LOOP_GAP_SEC = 1.5     # silence before re-looping any track
    # Soft end-fade length (seconds before track end). Credits gets a longer one.
    END_FADE_DEFAULT = 2.5
    END_FADE_CREDITS = 12.0  # long soft landing — track ends hard otherwise

    def __init__(self):
        self.enabled = False
        self.sfx_muted = False
        self.sounds = {}
        self._electric_channel = None
        self._vo_channel = None
        self.master_volume = 0.8
        self.music_volume = 0.4
        self._duck = 1.0
        self.DUCK_LEVEL = 0.40   # -8 dB VO
        self.PAUSE_DUCK = 0.32   # ~-10 dB in-game pause
        self.DUCK_IN = 0.10
        self.DUCK_OUT = 0.16
        self.PAUSE_IN = 0.30
        self.PAUSE_OUT = 0.40
        self.pause_duck = False
        self._base_volumes = {}
        self._current_music = None  # "menu" | "gameover" | "credits" | None
        self._fading_out = False
        self._pending_music = None
        self._fade_timer = 0.0
        # Loop / end-fade state
        self._music_elapsed = 0.0
        self._music_duration = None  # seconds or None
        self._end_fading = False
        self._loop_wait = 0.0
        self._loop_key = None
        self._busy_cache = False
        self._busy_age = 1.0
        try:
            if not pygame.mixer.get_init():
                # 2048 samples ≈ 46 ms — fewer underruns than 1024, still tight for SFX
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            try:
                pygame.mixer.set_num_channels(24)
                pygame.mixer.set_reserved(1)
            except Exception:
                pass
            for name, vol in [
                ("shoot", 0.45),
                ("explosion", 0.65),
                ("explosion_big", 0.85),
                ("electric", 0.35),
                ("enemy_shoot", 0.40),
                ("enemy_explosion", 0.55),
                ("1up", 1.0),
                ("phenix_activate", 0.75),
                ("phenix_end", 0.65),
                ("shield_zap", 0.70),
                ("boss_ready", 0.90),
                ("boss_angry", 0.88),
                ("boss_yell", 0.86),
                ("level1", 0.88),
                ("level2", 0.88),
                ("level3", 0.88),
                ("level4", 0.88),
                ("level5", 0.88),
                ("level6", 0.88),
                ("level7", 0.88),
                ("level8", 0.88),
                ("level9", 0.88),
                ("level10", 0.88),
                ("level11", 0.88),
                ("level12", 0.88),
                ("level13", 0.88),
                ("level14", 0.88),
                ("level15", 0.88),
                ("level16", 0.88),
                ("level17", 0.88),
                ("level18", 0.88),
                ("level19", 0.88),
                ("level20", 0.88),
                ("level21", 0.88),
                ("welcome_phoenix", 0.90),
                ("gameover_vo", 0.92),
                ("welcome_shield", 0.90),
            ]:
                self._load(name, f"{name}.wav", vol)
            self.enabled = len(self.sounds) > 0
            self._apply_master()
            self._music_paths = {
                "menu": os.path.join(MUSIC_DIR, "Phenix-EternalDawn.mp3"),
                "gameover": os.path.join(MUSIC_DIR, "Phenix-EternalDawn-Game-Over.mp3"),
                "credits": os.path.join(MUSIC_DIR, "Phenix-LastCoin-Credits.mp3"),
            }
            self._register_extra_music()
            # Authoritative lengths (ffprobe). Size-estimate is wrong on CBR/VBR MP3.
            self._music_durations = {
                "menu": 288.720,
                "gameover": 328.248,
                "credits": 480.000,
                "nostalgie_start": 216.456,  # 3:36
                "nostalgie_elise": 199.656,  # 3:19
            }
            for k, path in self._music_paths.items():
                probed = self._probe_duration(path)
                if probed and abs(probed - self._music_durations.get(k, probed)) < 8.0:
                    self._music_durations[k] = probed
                elif probed and k not in self._music_durations:
                    self._music_durations[k] = probed
        except Exception as e:
            print("Sound disabled:", e)
            self.enabled = False
            self._music_paths = {}
            self._music_durations = {}

    def _probe_duration(self, path):
        """Best-effort MP3 length in seconds (ffprobe > mutagen > size estimate)."""
        if not path or not os.path.exists(path):
            return None
        try:
            import subprocess
            r = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0 and r.stdout.strip():
                length = float(r.stdout.strip())
                if length > 1.0:
                    return length
        except Exception:
            pass
        try:
            import mutagen
            info = mutagen.File(path)
            if info is not None and getattr(info, "info", None) is not None:
                length = float(info.info.length)
                if length > 1.0:
                    return length
        except Exception:
            pass
        return None

    def _register_extra_music(self):
        """Jukebox extras: Nostalgie tracks + intro audio if present."""
        try:
            names = os.listdir(MUSIC_DIR)
        except Exception:
            names = []
        lower = {n: n.lower() for n in names if n.lower().endswith(".mp3")}
        def pick(*needles):
            for orig, low in lower.items():
                if all(n in low for n in needles):
                    return os.path.join(MUSIC_DIR, orig)
            return None
        start = (
            pick("nostalgie", "interdite")
            or pick("nostalgie", "start")
            or pick("interdite")
        )
        elise = pick("elise") or pick("élise")
        if start:
            self._music_paths["nostalgie_start"] = start
        if elise:
            self._music_paths["nostalgie_elise"] = elise
        intro = None
        try:
            from intro import AUDIO_PATH
            if AUDIO_PATH and os.path.exists(AUDIO_PATH):
                intro = AUDIO_PATH
        except Exception:
            intro = None
        if intro is None:
            intro = pick("intro")
        if intro:
            self._music_paths["intro"] = intro

    def current_music_key(self):
        return self._current_music

    def music_busy(self):
        try:
            return bool(pygame.mixer.music.get_busy())
        except Exception:
            return False

    def music_duration(self, key):
        return self._music_durations.get(key)

    def music_pos_sec(self):
        try:
            ms = int(pygame.mixer.music.get_pos())
            if ms < 0:
                return 0.0
            return ms / 1000.0
        except Exception:
            return 0.0

    def pause_music(self, paused):
        try:
            if paused:
                pygame.mixer.music.pause()
            else:
                pygame.mixer.music.unpause()
        except Exception:
            pass

    def play_direct(self, key, loops=0):
        """Immediate play (jukebox): no crossfade, optional one-shot."""
        path = self._music_paths.get(key)
        if not path or not os.path.exists(path):
            print("play_direct missing:", key)
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self._fading_out = False
        self._pending_music = None
        self._end_fading = False
        self._loop_wait = 0.0
        self._loop_key = None
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self._music_out())
            pygame.mixer.music.play(int(loops))
            self._current_music = key
            self._music_elapsed = 0.0
            self._music_duration = self._music_durations.get(key)
        except Exception as e:
            print("play_direct failed:", e)
            self._current_music = None

    def _load(self, name, filename, volume=0.55):
        path = os.path.join(SOUND_DIR, filename)
        if os.path.exists(path):
            snd = pygame.mixer.Sound(path)
            snd.set_volume(1.0)  # gain + pan applied per Channel
            self.sounds[name] = snd
            self._base_volumes[name] = volume

    def _apply_master(self):
        # Gain is applied per-play on the Channel (stereo pan).
        pass

    def _pan_lr(self, x, gain):
        """Equal-power pan from on-screen x. None = centered."""
        gain = max(0.0, min(1.0, float(gain)))
        if x is None:
            return gain, gain
        try:
            t = float(x) / float(BASE_WIDTH)
        except Exception:
            t = 0.5
        t = max(0.0, min(1.0, t))
        t = 0.12 + 0.76 * t  # keep a whisper on the far speaker
        ang = t * math.pi * 0.5
        return gain * math.cos(ang), gain * math.sin(ang)

    def _play_on_channel(self, snd, gain, x=None):
        ch = snd.play()
        if ch is None:
            try:
                ch = pygame.mixer.find_channel(True)
            except Exception:
                ch = None
            if ch is not None:
                ch.play(snd)
        if ch is not None:
            left, right = self._pan_lr(x, gain)
            try:
                ch.set_volume(left, right)
            except Exception:
                ch.set_volume(gain)
        return ch

    def set_master_volume(self, vol):
        self.master_volume = max(0.0, min(1.0, vol))

    def _music_out(self):
        """OST is mastered hotter than SFX. Slider 1.0 ≈ 30% mixer, then VO duck."""
        duck = float(getattr(self, "_duck", 1.0) or 1.0)
        return max(0.0, min(1.0, float(self.music_volume) * 0.30 * duck))

    def set_music_volume(self, vol):
        self.music_volume = max(0.0, min(1.0, vol))
        if not self._end_fading and not self._fading_out:
            try:
                pygame.mixer.music.set_volume(self._music_out())
            except Exception:
                pass

    def play(self, name, volume=None, x=None):
        """Play SFX. Optional x (screen px) pans L/R; volume 0..1 overrides base."""
        if not self.enabled or getattr(self, "sfx_muted", False):
            return
        snd = self.sounds.get(name)
        if not snd:
            return
        if volume is not None:
            gain = max(0.0, min(1.0, float(volume))) * self.master_volume
        else:
            gain = self._base_volumes.get(name, 0.5) * self.master_volume
        self._play_on_channel(snd, gain, x=x)

    def play_vo(self, name, volume=None):
        """Announcer: reserved channel, never stolen by SFX."""
        if not self.enabled or getattr(self, "sfx_muted", False):
            return
        snd = self.sounds.get(name)
        if not snd:
            return
        gain = (float(volume) if volume is not None else self._base_volumes.get(name, 0.88))
        gain = max(0.0, min(1.0, gain)) * self.master_volume
        try:
            ch = pygame.mixer.Channel(0)
            self._vo_channel = ch
            ch.play(snd)
            ch.set_volume(gain, gain)
            self._vo_t0 = pygame.time.get_ticks() * 0.001
            try:
                self._vo_len = float(snd.get_length())
            except Exception:
                self._vo_len = 2.5
        except Exception:
            self._play_on_channel(snd, gain)

    def vo_progress(self):
        """0..1 how far the current announcer clip has played."""
        if not self.vo_is_busy():
            return 1.0
        t0 = float(getattr(self, "_vo_t0", 0.0) or 0.0)
        ln = float(getattr(self, "_vo_len", 0.0) or 0.0)
        if ln <= 0.05:
            return 1.0
        now = pygame.time.get_ticks() * 0.001
        return max(0.0, min(1.0, (now - t0) / ln))

    def vo_is_busy(self):
        """True while the reserved announcer channel is playing."""
        ch = getattr(self, "_vo_channel", None)
        if ch is None:
            return False
        try:
            return bool(ch.get_busy())
        except Exception:
            return False

    def play_electric(self, active, x=None):
        """Loop electric crackle while edge shock is active. x pans to the wall."""
        if not self.enabled or getattr(self, "sfx_muted", False):
            if not active and self._electric_channel is not None:
                try:
                    self._electric_channel.stop()
                except Exception:
                    pass
                self._electric_channel = None
            return
        snd = self.sounds.get("electric")
        if not snd:
            return
        gain = self._base_volumes.get("electric", 0.35) * self.master_volume
        if active:
            if self._electric_channel is None or not self._electric_channel.get_busy():
                self._electric_channel = snd.play(loops=-1)
            ch = self._electric_channel
            if ch is not None:
                left, right = self._pan_lr(x, gain)
                try:
                    ch.set_volume(left, right)
                except Exception:
                    ch.set_volume(gain)
        else:
            if self._electric_channel is not None:
                self._electric_channel.stop()
                self._electric_channel = None

    def play_music(self, key, loops=-1, fade_ms=None):
        """Request a theme. Cross-fades from the current one if needed."""
        fade = int(self.FADE_MS if fade_ms is None else fade_ms)
        if key not in self._music_paths:
            return
        path = self._music_paths.get(key)
        if not path:
            return
        # Already on this track — never touch the stream (avoids MP3 reload hitch)
        if self._current_music == key and not self._fading_out:
            return
        if self._pending_music == key and self._fading_out:
            return

        self._loop_wait = 0.0
        self._loop_key = None

        if self._current_music is None and not self._fading_out:
            self._start_track(path, key, fade_ms=fade)
            return

        if self._current_music == key:
            return

        self._pending_music = key
        self._pending_fade_ms = fade
        if not self._fading_out:
            self._fading_out = True
            self._end_fading = False
            self._fade_timer = fade / 1000.0
            try:
                pygame.mixer.music.fadeout(fade)
            except Exception:
                self._finish_fade()

    def stop_music(self):
        """Fade out to silence (e.g. entering gameplay)."""
        self._loop_wait = 0.0
        self._loop_key = None
        if self._current_music is None and not self._fading_out:
            return
        self._pending_music = None
        if not self._fading_out:
            self._fading_out = True
            self._end_fading = False
            self._fade_timer = self.FADE_MS / 1000.0
            try:
                pygame.mixer.music.fadeout(self.FADE_MS)
            except Exception:
                self._finish_fade()

    def _start_track(self, path, key, fade_ms=None):
        try:
            fade = int(self.FADE_MS if fade_ms is None else fade_ms)
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self._music_out())
            # Native loop: no mid-track reload (that was the rare hitch)
            pygame.mixer.music.play(-1, fade_ms=fade)
            self._current_music = key
            self._fading_out = False
            self._pending_music = None
            self._music_elapsed = 0.0
            self._music_duration = self._music_durations.get(key)
            self._end_fading = False
            self._loop_wait = 0.0
            self._loop_key = None
        except Exception as e:
            print("Music play failed:", e)
            self._current_music = None
            self._fading_out = False

    def _finish_fade(self):
        self._fading_out = False
        self._end_fading = False
        self._current_music = None
        self._music_elapsed = 0.0
        pending = self._pending_music
        fade = getattr(self, "_pending_fade_ms", None)
        self._pending_music = None
        self._pending_fade_ms = None
        if pending:
            path = self._music_paths.get(pending)
            if path and os.path.exists(path):
                self._start_track(path, pending, fade_ms=fade)

    def _end_fade_seconds(self, key):
        if key == "credits":
            return self.END_FADE_CREDITS
        return self.END_FADE_DEFAULT

    def _tick_duck(self, dt):
        """Ramp OST down for announcer VO and in-game pause."""
        target = 1.0
        speed_in, speed_out = self.DUCK_IN, self.DUCK_OUT
        if self.vo_is_busy():
            target = min(target, self.DUCK_LEVEL)
        if getattr(self, "pause_duck", False):
            target = min(target, self.PAUSE_DUCK)
            speed_in, speed_out = self.PAUSE_IN, self.PAUSE_OUT
        cur = float(getattr(self, "_duck", 1.0) or 1.0)
        speed = speed_in if target < cur else speed_out
        if speed <= 0:
            cur = target
        else:
            k = min(1.0, dt / speed)
            cur = cur + (target - cur) * k
        if abs(cur - target) < 0.01:
            cur = target
        if cur != getattr(self, "_duck", 1.0):
            self._duck = cur
            if not self._end_fading and not self._fading_out:
                try:
                    pygame.mixer.music.set_volume(self._music_out())
                except Exception:
                    pass
        else:
            self._duck = cur

    def update(self, dt):
        """Call each frame: VO duck + finish a theme crossfade."""
        try:
            self._tick_duck(dt)
        except Exception:
            pass
        if not self._fading_out:
            return
        self._fade_timer -= dt
        if self._fade_timer > 0:
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self._finish_fade()
