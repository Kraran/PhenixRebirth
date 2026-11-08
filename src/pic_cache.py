"""Pictures worked out from other pictures (the fire of the Phenix recoloured, the transformation's pictures between)
are kept the first time, keyed on what they are made of: a second ship of the same tint, a new game, the ship select
screen opened again (and every test that builds a Game) get copies of them instead of working them out again."""

import hashlib

import pygame

_KEPT = {}


def key_of(surf):
    """What a picture is made of: its size and its pixels."""
    if surf is None:
        return None
    return surf.get_size(), hashlib.blake2b(pygame.image.tobytes(surf, "RGBA"), digest_size=16).digest()


def kept(key, make):
    """The pictures `make()` returns for `key`, worked out once; each call gets its own copies (a picture or a list)."""
    out = _KEPT.get(key)
    if out is None:
        out = _KEPT[key] = make()
    if isinstance(out, list):
        return [p.copy() if p is not None else None for p in out]
    return out.copy() if out is not None else None
