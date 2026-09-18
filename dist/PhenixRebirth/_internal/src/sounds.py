"""
SFX and music manager (SDL_mixer via pygame).

SFX are WAV samples under assets/sounds/.
Music tracks are MP3 under assets/music/ with short cross-fades between
menu theme, game-over theme, credits theme, and in-game silence.

Loop behaviour:
- Tracks loop natively (play(-1)) so we never reload an MP3 mid-session.
- Theme changes still cross-fade. Credits keeps a long end-fade only when
  leaving that screen, not a disk reload every loop.
"""
import pygame
import os

from settings import asset_path
SOUND_DIR = asset_path("sounds")
MUSIC_DIR = asset_path("music")


class SoundManager:
    FADE_MS = 350          # crossfade when switching themes
    LOOP_GAP_SEC = 1.5     # silence before re-looping any track
    # Soft end-fade length (seconds before track end). Credits gets a longer one.
    END_FADE_DEFAULT = 2.5
    END_FADE_CREDITS = 12.0  # long soft landing — track ends hard otherwise

    def __init__(self):
        self.enabled = False
        self.sfx_muted = False
        self.sounds = {}
        self._electric_channel = None
        self.master_volume = 0.8
        self.music_volume = 0.4
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
            ]:
                self._load(name, f"{name}.wav", vol)
            self.enabled = len(self.sounds) > 0
            self._apply_master()
            self._music_paths = {
                "menu": os.path.join(MUSIC_DIR, "Phenix-EternalDawn.mp3"),
                "gameover": os.path.join(MUSIC_DIR, "Phenix-EternalDawn-Game-Over.mp3"),
                "credits": os.path.join(MUSIC_DIR, "Phenix-LastCoin-Credits.mp3"),
            }
            # Known lengths (seconds) when probe is unavailable
            self._music_durations = {
                "credits": 480.0,  # Phenix-LastCoin-Credits (ffprobe)
            }
            for k, path in self._music_paths.items():
                probed = self._probe_duration(path)
                if probed:
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
        try:
            size = os.path.getsize(path)
            est = size / 20000.0
            if est > 5.0:
                return est
        except Exception:
            pass
        return None

    def _load(self, name, filename, volume=0.55):
        path = os.path.join(SOUND_DIR, filename)
        if os.path.exists(path):
            snd = pygame.mixer.Sound(path)
            self.sounds[name] = snd
            self._base_volumes[name] = volume

    def _apply_master(self):
        for name, snd in self.sounds.items():
            base = self._base_volumes.get(name, 0.5)
            snd.set_volume(base * self.master_volume)

    def set_master_volume(self, vol):
        self.master_volume = max(0.0, min(1.0, vol))
        self._apply_master()

    def set_music_volume(self, vol):
        self.music_volume = max(0.0, min(1.0, vol))
        if not self._end_fading and not self._fading_out:
            try:
                pygame.mixer.music.set_volume(self.music_volume)
            except Exception:
                pass

    def play(self, name, volume=None):
        """Play SFX. Optional volume (0..1) overrides the sample base * master for this shot."""
        if not self.enabled or getattr(self, "sfx_muted", False):
            return
        snd = self.sounds.get(name)
        if not snd:
            return
        if volume is not None:
            base = self._base_volumes.get(name, 0.5)
            # volume arg is a relative level; still respect master
            snd.set_volume(max(0.0, min(1.0, float(volume))) * self.master_volume)
            snd.play()
            # restore base * master for subsequent default plays
            snd.set_volume(base * self.master_volume)
        else:
            snd.play()

    def play_electric(self, active):
        """Loop electric crackle while edge shock is active."""
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
        if active:
            if self._electric_channel is None or not self._electric_channel.get_busy():
                self._electric_channel = snd.play(loops=-1)
        else:
            if self._electric_channel is not None:
                self._electric_channel.stop()
                self._electric_channel = None

    def play_music(self, key, loops=-1):
        """Request a theme. Cross-fades from the current one if needed."""
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
            self._start_track(path, key)
            return

        if self._current_music == key:
            return

        self._pending_music = key
        if not self._fading_out:
            self._fading_out = True
            self._end_fading = False
            self._fade_timer = self.FADE_MS / 1000.0
            try:
                pygame.mixer.music.fadeout(self.FADE_MS)
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

    def _start_track(self, path, key):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.music_volume)
            # Native loop: no mid-track reload (that was the rare hitch)
            pygame.mixer.music.play(-1, fade_ms=self.FADE_MS)
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
        self._pending_music = None
        if pending:
            path = self._music_paths.get(pending)
            if path and os.path.exists(path):
                self._start_track(path, pending)

    def _end_fade_seconds(self, key):
        if key == "credits":
            return self.END_FADE_CREDITS
        return self.END_FADE_DEFAULT

    def update(self, dt):
        """Call each frame: finish a theme crossfade. Loops are native (no reload)."""
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
