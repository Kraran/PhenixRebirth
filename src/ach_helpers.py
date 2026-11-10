"""
The listen-achievements tick (the achievements won by hearing a track to its end).

Extracted from game.py (Game._tick_listen_achs). The functions take the Game object as `game`.
"""

import pygame



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
