"""Boot intro clip — JPEG sequence + OGG, skippable."""
from __future__ import annotations

import os
import time

import pygame

from settings import BASE_HEIGHT, BASE_WIDTH, asset_path

INTRO_FPS = 24.0
FADE_SEC = 0.80
FRAME_DIR = asset_path("video", "intro_frames")
AUDIO_PATH = asset_path("video", "intro.ogg")


def _frame_list():
    if not os.path.isdir(FRAME_DIR):
        return []
    names = [
        os.path.join(FRAME_DIR, n)
        for n in sorted(os.listdir(FRAME_DIR))
        if n.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    return names


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
    """Play the boot cinematic on the logical canvas. Returns False if skipped
    the whole feature (no assets). QUIT sets game.running = False."""
    frames = _frame_list()
    if not frames:
        return False

    dest_w, dest_h = BASE_WIDTH, BASE_HEIGHT
    # Fit 46:25 plate into 16:9 without cropping
    src_w, src_h = 736, 400
    scale = min(dest_w / src_w, dest_h / src_h)
    tw, th = max(1, int(src_w * scale)), max(1, int(src_h * scale))
    ox, oy = (dest_w - tw) // 2, (dest_h - th) // 2

    cache = {}

    def _get(i):
        if i in cache:
            return cache[i]
        try:
            img = pygame.image.load(frames[i]).convert()
            if img.get_size() != (tw, th):
                img = pygame.transform.smoothscale(img, (tw, th))
        except Exception:
            img = None
        cache[i] = img
        if len(cache) > 6:
            oldest = min(k for k in cache if k < i)
            cache.pop(oldest, None)
        return img

    _get(0)

    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
    vol = float(getattr(game, "music_volume", 0.4) or 0.4)
    if os.path.isfile(AUDIO_PATH):
        try:
            pygame.mixer.music.load(AUDIO_PATH)
            pygame.mixer.music.set_volume(max(0.0, min(1.0, vol)))
            pygame.mixer.music.play(0)
        except Exception:
            pass

    n = len(frames)
    duration = n / INTRO_FPS
    t0 = time.perf_counter()
    last = -1
    skipped = False
    last_frame = None

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
                pass
        end = time.perf_counter() + seconds
        while game.running and time.perf_counter() < end:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    game.running = False
                    return
            _blit(frame)
            game.clock.tick(60)

    while game.running:
        now = time.perf_counter() - t0
        idx = int(now * INTRO_FPS)
        if idx >= n:
            break
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.running = False
                skipped = True
                break
            if event.type == pygame.JOYDEVICEADDED:
                try:
                    game.joystick = pygame.joystick.Joystick(event.device_index)
                    game.joystick.init()
                except Exception:
                    pass
            if _wants_skip(event):
                skipped = True
                break
        if skipped or not game.running:
            break
        remain = duration - now
        if remain < FADE_SEC:
            try:
                pygame.mixer.music.set_volume(max(0.0, vol * (remain / FADE_SEC)))
            except Exception:
                pass
        if idx != last:
            last = idx
            nxt = idx + 1
            if nxt < n and nxt not in cache:
                _get(nxt)
        last_frame = _get(idx)
        _blit(last_frame)
        game.clock.tick(60)

    if game.running:
        if skipped:
            _fade_hold(last_frame, 0.35)
        else:
            _fade_hold(last_frame, 0.18)
        _fade_to_black(last_frame, 0.45)

    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
    pygame.event.clear()
    return True
