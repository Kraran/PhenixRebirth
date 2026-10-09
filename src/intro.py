"""Boot intro: one silent H.264 clip (intro.mp4, played by videoclip.py) and its music (intro.ogg), skippable.

The picture and the music start together: ffmpeg is started first and the music only when its first frame is
ready, so a slow start of ffmpeg never leaves the picture behind the sound. main.py calls `prewarm()` before the
game loads, so that ffmpeg starts while the game is still busy loading. The jukebox plays the same intro
through `open_clip` and `start_audio`."""
from __future__ import annotations

import os
import time

import pygame

import videoclip
from settings import BASE_HEIGHT, BASE_WIDTH, asset_path
from errlog import log_exc

INTRO_FPS = videoclip.CLIP_FPS
FADE_SEC = 0.80                      # the music fades out over the end of the picture
READY_TIMEOUT = 4.0                  # seconds to wait for the first picture before giving the intro up
VIDEO_PATH = asset_path("video", "intro.mp4")
AUDIO_PATH = asset_path("video", "intro.ogg")

_warm = []                           # the player started by prewarm(), until play_intro takes it


def open_clip(box=(BASE_WIDTH, BASE_HEIGHT)):
    """A player of the intro picture shrunk to fit `box`, playing once with a hard clock (it goes with a sound).
    None when there is no intro file; the player is `failed` right away when there is no ffmpeg."""
    if not os.path.isfile(VIDEO_PATH):
        return None
    box = (int(box[0]), int(box[1]))
    if _warm:
        warm = _warm.pop()
        if warm.box == box and not warm.failed:
            return warm
        warm.close()
    return videoclip.ClipPlayer(VIDEO_PATH, box, fit="contain", loop=False, hard_clock=True)


def prewarm(box=(BASE_WIDTH, BASE_HEIGHT)):
    """Start decoding the intro now, to have its first pictures ready when the intro begins."""
    if _warm:
        return
    clip = open_clip(box)
    if clip is not None:
        _warm.append(clip)


def start_audio(volume):
    """Start the intro music. True when it plays."""
    if not os.path.isfile(AUDIO_PATH):
        return False
    try:
        pygame.mixer.music.stop()
        pygame.mixer.music.load(AUDIO_PATH)
        pygame.mixer.music.set_volume(max(0.0, min(1.0, float(volume))))
        pygame.mixer.music.play(0)
        return True
    except Exception:
        log_exc("intro.start_audio")
        return False


def _wants_skip(event):
    if event.type == pygame.KEYDOWN:
        return True
    if event.type == pygame.JOYBUTTONDOWN:
        return True
    if event.type == pygame.MOUSEBUTTONDOWN:
        return True
    if event.type == pygame.JOYHATMOTION:
        try:
            hx, hy = event.value
            return hx != 0 or hy != 0
        except Exception:
            return False
    return False


def play_intro(game):
    """Play the boot cinematic on the logical canvas. Returns False when there is nothing to play (no file,
    no ffmpeg, a video that does not start). QUIT sets game.running = False."""
    clip = open_clip((BASE_WIDTH, BASE_HEIGHT))
    if clip is None:
        return False
    try:
        return _play(game, clip)
    finally:
        clip.close()
        try:
            pygame.mixer.music.stop()
        except Exception:
            log_exc("intro.play_intro")
        pygame.event.clear()


def _play(game, clip):
    if clip.failed:
        return False
    ox, oy = (BASE_WIDTH - clip.size[0]) // 2, (BASE_HEIGHT - clip.size[1]) // 2
    vol = float(getattr(game, "music_volume", 0.4) or 0.4)
    state = {"skipped": False}

    def _events():
        """True when the intro must stop now (skip, or the window was closed)."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.running = False
                state["skipped"] = True
                return True
            if event.type == pygame.JOYDEVICEADDED:
                try:
                    game.joystick = pygame.joystick.Joystick(event.device_index)
                    game.joystick.init()
                except Exception:
                    log_exc("intro.play_intro")
            if _wants_skip(event):
                state["skipped"] = True
                return True
        return not game.running

    def _blit(frame):
        gs = game.game_surface
        gs.fill((0, 0, 0))
        if frame is not None:
            gs.blit(frame, (ox, oy))
        game._flip_frame(0, 0)

    def _fade_to_black(frame, seconds):
        """Last frame → black. Menu then fades in on the other side."""
        seconds = max(0.05, float(seconds))
        t0b = time.perf_counter()
        black = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
        black.fill((0, 0, 0))
        while game.running and time.perf_counter() - t0b < seconds:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    game.running = False
                    return
            k = min(1.0, (time.perf_counter() - t0b) / seconds)
            gs = game.game_surface
            gs.fill((0, 0, 0))
            if frame is not None:
                gs.blit(frame, (ox, oy))
            black.set_alpha(int(255 * k))
            gs.blit(black, (0, 0))
            game._flip_frame(0, 0)
            game.clock.tick(60)
        gs = game.game_surface
        gs.fill((0, 0, 0))
        game._flip_frame(0, 0)

    def _fade_hold(frame, seconds):
        """Keep last picture while music volume goes to 0."""
        try:
            pygame.mixer.music.fadeout(max(1, int(seconds * 1000)))
        except Exception:
            try:
                pygame.mixer.music.stop()
            except Exception:
                log_exc("intro.play_intro._fade_hold")
        end = time.perf_counter() + seconds
        while game.running and time.perf_counter() < end:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    game.running = False
                    return
            _blit(frame)
            game.clock.tick(60)

    try:
        pygame.mixer.music.stop()
    except Exception:
        log_exc("intro.play_intro")

    # the first picture is ready before anything starts: picture and music then run together
    wait = time.perf_counter()
    while game.running and not clip.ready and not clip.failed and time.perf_counter() - wait < READY_TIMEOUT:
        if _events():
            break
        _blit(None)
        game.clock.tick(60)
    if state["skipped"] or not game.running:
        return True
    if clip.failed or not clip.ready:
        return False

    start_audio(vol)
    t0 = time.perf_counter()
    last_frame = None
    while game.running:
        if _events():
            break
        clip.pump()
        if clip.surface is not None:
            last_frame = clip.surface
        if clip.failed or clip.ended:
            break                                 # the end of the picture (or the decoder stopped: end the intro)
        if clip.duration:
            remain = clip.duration - (time.perf_counter() - t0)
            if remain < FADE_SEC:
                try:
                    pygame.mixer.music.set_volume(max(0.0, vol * (remain / FADE_SEC)))
                except Exception:
                    log_exc("intro.play_intro")
        _blit(last_frame)
        game.clock.tick(60)

    if game.running:
        _fade_hold(last_frame, 0.35 if state["skipped"] else 0.18)
        _fade_to_black(last_frame, 0.45)
    return True
