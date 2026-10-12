"""Make the pictures of the engine flames: assets/sprites/engines/KIND_COLOUR.png (FRAMES cells side by side).

    python tools/make_engine_flames.py

The look of the jets is in src/engine_flame.py (temperature field, colour ramps, sizes): change it there, run this
again and commit the pictures. Needs only numpy and pygame (like the game).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

import engine_flame as ef  # noqa: E402

# which colours go with which kind of jet
SETS = {
    "phoenix": ("argent", "blue", "gold"),
    "shield": ("red", "green", "violet"),
    "phenix": ("phenix_red", "phenix_blue"),
}


def main():
    pygame.init()
    os.makedirs(os.path.dirname(ef.strip_path("phoenix", "argent")), exist_ok=True)
    for kind, keys in SETS.items():
        for key in keys:
            strip = ef.render_strip(kind, key)
            path = ef.strip_path(kind, key)
            pygame.image.save(strip, path)
            print(os.path.relpath(path, ROOT), strip.get_size(), os.path.getsize(path) // 1024, "KB")


if __name__ == "__main__":
    main()
