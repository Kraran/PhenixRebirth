"""
Global constants and stage progression helpers.

Also exposes project_root() / user_data_dir() for assets and save files,
compatible with PyInstaller frozen builds.

Resolution is fixed at an internal 1280x720 logical canvas, then scaled
to the window / fullscreen display. Movement and combat use delta-time
so the game feels the same at 60 Hz or 120 Hz.
"""
# Phenix Rebirth - Settings
# Ultra-responsive action game settings

import os
import sys


def project_root():
    """Read-only game data root (assets). Inside PyInstaller one-folder/onefile extract dir."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def user_data_dir():
    """Writable directory for settings.json / highscores.json (next to the .exe when frozen)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return project_root()


def asset_path(*parts):
    """Join path under project_root/assets/..."""
    return os.path.join(project_root(), "assets", *parts)

# Display
BASE_WIDTH = 1280
BASE_HEIGHT = 720

# Frame rate: 60 or 120 (144 later)
# Will be set at runtime by detect_refresh_rate()
FPS_TARGET = 120
VSYNC = True

# Colors
COLOR_BG = (8, 8, 16)
COLOR_PURPLE_FLOOR = (120, 40, 160)
COLOR_UI = (220, 220, 255)

# Player
PLAYER_SPEED = 480.0
PLAYER_WIDTH = 48
PLAYER_HEIGHT = 36
BULLET_SPEED = 980.0
PLAYER_MAX_LIVES = 3
PLAYER_INVULN_TIME = 1.8          # seconds of invulnerability after hit

# Enemy Stage 1
ENEMY_SPEED = 85.0
ENEMY_DIVE_SPEED = 280.0
ENEMY_BULLET_SPEED = 320.0
ENEMY_SHOOT_CHANCE = 0.0035
ENEMY_DIVE_CHANCE = 0.0018

# Game feel
SCREEN_SHAKE_DECAY = 14.0

# Performance
MAX_PARTICLES_SOFT = 120          # soft cap for simultaneous explosion particles
STAR_FAR_COUNT = 55
STAR_MID_COUNT = 35
STAR_NEAR_COUNT = 20


def detect_refresh_rate():
    """Hz of the *current* window. Do not take max() of other monitors."""
    import pygame
    rate = 0
    try:
        if hasattr(pygame.display, "get_current_refresh_rate"):
            cur = int(pygame.display.get_current_refresh_rate() or 0)
            if cur >= 50:
                rate = cur
        if rate < 50 and hasattr(pygame.display, "get_desktop_refresh_rates"):
            rates = [int(r) for r in (pygame.display.get_desktop_refresh_rates() or []) if r]
            if rates:
                # First desktop is the primary — not max (other screens may be 120).
                rate = rates[0]
        print("refresh probe:", rate)
    except Exception as e:
        print("refresh probe failed:", e)
        rate = 60
    if rate >= 130:
        return 144
    if rate >= 100:
        return 120
    if rate >= 70:
        return 75
    return 60


def stage_content(stage):
    """Map infinite stage index to content template 1–5 (boss every 5th)."""
    """Map infinite stage number to content 1-5."""
    return ((int(stage) - 1) % 5) + 1


def stage_speed_mult(stage):
    """+10% enemy speed every full 5-stage cycle (stages 6–10 → 1.1×, …)."""
    """+10% speed every 5 stages: 1-5 → 1.0, 6-10 → 1.1, 11-15 → 1.2, ..."""
    tier = max(0, (int(stage) - 1) // 5)
    return 1.0 + 0.1 * tier
