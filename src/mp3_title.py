"""ID3v2 TIT2 titles for jukebox + Options. Read the file; known tags as fallback."""
from __future__ import annotations

import os

# Exact TIT2 currently in the soundtrack MP3s (read 2026-09-18).
KNOWN_TIT2 = {
    "menu": "Phenix - Eternal Dawn I (Opening)",
    "gameover": "Phenix - Eternal Dawn II (Game Over)",
    "credits": "Phenix - Last Coin (Credits)",
    "nostalgie_start": "Phoenix - Nostalgie interdite (Start)",
    "nostalgie_elise": "Phoenix - Nostalgie pour Elise (Final)",
}

KEY_FILES = {
    "menu": ("Phenix-EternalDawn.mp3",),
    "gameover": ("Phenix-EternalDawn-Game-Over.mp3",),
    "credits": ("Phenix-LastCoin-Credits.mp3",),
    "nostalgie_start": (
        "Phenix-Nostalgie-Interdite.mp3",
        "Phoenix - Nostalgie interdite (Start).mp3",
    ),
    "nostalgie_elise": (
        "Phenix-Nostalgie-Elise.mp3",
        "Phoenix - Nostalgie pour Elise (Final).mp3",
    ),
}

_cache = {}


def _decode_id3_text(raw):
    if not raw:
        return ""
    enc = raw[0]
    data = raw[1:]
    try:
        if enc == 0:
            return data.split(b"\x00", 1)[0].decode("latin-1", "replace").strip()
        if enc == 1:
            return data.decode("utf-16", "replace").replace("\x00", "").strip()
        if enc == 2:
            return data.decode("utf-16-be", "replace").replace("\x00", "").strip()
        if enc == 3:
            return data.split(b"\x00", 1)[0].decode("utf-8", "replace").strip()
    except Exception:
        pass
    return data.decode("latin-1", "replace").replace("\x00", "").strip()


def title_from_path(path):
    if not path or not os.path.isfile(path):
        return ""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0
    hit = _cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    title = ""
    try:
        with open(path, "rb") as f:
            head = f.read(10)
            if len(head) >= 10 and head[:3] == b"ID3":
                size = (
                    (head[6] & 0x7F) << 21
                    | (head[7] & 0x7F) << 14
                    | (head[8] & 0x7F) << 7
                    | (head[9] & 0x7F)
                )
                tag = f.read(min(size, 256 * 1024))
                i = 0
                while i + 10 <= len(tag):
                    fid = tag[i:i + 4]
                    if fid == b"\x00\x00\x00\x00" or not fid.strip(b"\x00"):
                        break
                    flen = int.from_bytes(tag[i + 4:i + 8], "big")
                    if flen <= 0 or i + 10 + flen > len(tag):
                        break
                    if fid == b"TIT2":
                        title = _decode_id3_text(tag[i + 10:i + 10 + flen])
                        break
                    i += 10 + flen
    except OSError:
        title = ""
    base = os.path.splitext(os.path.basename(path or ""))[0]
    for key, names in KEY_FILES.items():
        stems = [os.path.splitext(n)[0] for n in names]
        if base in stems or (path and os.path.basename(path) in names):
            title = title or KNOWN_TIT2.get(key, "")
            break
    if not title:
        title = base
    _cache[path] = (mtime, title)
    return title


def title_for_key(asset_path_fn, key):
    if asset_path_fn is not None:
        for name in KEY_FILES.get(key, (key + ".mp3",)):
            try:
                path = asset_path_fn("music", name)
            except TypeError:
                path = None
            if path and os.path.isfile(path):
                got = title_from_path(path)
                if got:
                    return got
    return KNOWN_TIT2.get(key, key)
