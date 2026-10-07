"""
Achievement icon drawing and the listen-achievements tick.

Extracted from game.py (Game._ach_icon, Game._tick_listen_achs). Functions take
the Game object as `game` and behave exactly as before.
"""
import os

import pygame

from settings import asset_path


def ach_icon(game, kind, unlocked):
    """32px catalog icon, color or grey."""
    cache = getattr(game, "_ach_icon_cache", None)
    if cache is None:
        cache = game._ach_icon_cache = {}
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


def tick_listen_achs(game):
    """Unlock when the current theme finishes a full play (loop wrap).

    Screen changes that keep the same track do not reset the counter.
    Only a real track change, volume off, or attract resets it.
    """
    listen = getattr(game, "_listen", None)
    if listen is None:
        listen = game._listen = {
            "menu": 0.0, "gameover": 0.0, "credits": 0.0,
            "nostalgie_start": 0.0, "nostalgie_elise": 0.0,
        }
    if getattr(game, "attract_mode", False):
        listen["menu"] = listen["gameover"] = listen["credits"] = 0.0
        game._listen_key = None
        game._listen_pos = 0
        return
    mix = getattr(game, "audio_mix", "sfx")
    vol = float(getattr(game.sounds, "music_volume", 0.0) or 0.0)
    if mix == "off" or vol < 0.02:
        listen["menu"] = listen["gameover"] = listen["credits"] = 0.0
        game._listen_key = None
        game._listen_pos = 0
        game._try_music_collector()
        return
    key = None
    try:
        key = game.sounds.current_music_key()
    except Exception:
        key = None
    if key not in ("menu", "gameover", "credits", "nostalgie_start", "nostalgie_elise"):
        # Fade / silence / other theme: keep counters.
        return
    if game._listen_key != key:
        for k in list(listen.keys()):
            if k != key:
                listen[k] = 0.0
        game._listen_key = key
        game._listen_pos = 0
    listen[key] = float(listen.get(key, 0.0)) + float(game.dt)

    pos_ms = -1
    try:
        pos_ms = int(pygame.mixer.music.get_pos())
    except Exception:
        pos_ms = -1
    wrapped = False
    last = int(getattr(game, "_listen_pos", 0) or 0)
    if pos_ms >= 0:
        if last > 2500 and pos_ms + 800 < last:
            wrapped = True
        game._listen_pos = pos_ms
    need = 0.0
    try:
        need = float(game.sounds.music_duration(key) or 0.0)
    except Exception:
        need = 0.0
    near_end = False
    if need >= 8.0 and pos_ms >= 0:
        near_end = (pos_ms / 1000.0) >= (need - 0.45)
    elif need >= 8.0:
        near_end = listen[key] >= (need - 0.45)
    if not (wrapped or near_end):
        return
    aid = {
        "menu": "listen_menu", "gameover": "listen_hs", "credits": "listen_credits",
        "nostalgie_start": "listen_nostalgie_start",
        "nostalgie_elise": "listen_nostalgie_elise",
    }.get(key)
    done = getattr(game, "_listen_done", None)
    if done is None:
        done = game._listen_done = set()
    if not aid or aid in done:
        listen[key] = 0.0
        return
    done.add(aid)
    game._unlock_ach_meta(aid)
    listen[key] = 0.0
    game._listen_pos = 0
    game._try_music_collector()
