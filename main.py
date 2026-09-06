#!/usr/bin/env python3
"""Phenix Rebirth — entry point."""
import sys
import os

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _root = sys._MEIPASS
else:
    _root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_root, "src"))
sys.path.insert(0, _root)

os.environ.setdefault("SDL_HINT_RENDER_SCALE_QUALITY", "linear")
os.environ.setdefault("SDL_RENDER_VSYNC", "0")
os.environ.setdefault("SDL_HINT_RENDER_VSYNC", "0")

LOG = os.path.join(_root, "boot.log")

def _log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass
    print(msg, flush=True)


if __name__ == "__main__":
    try:
        with open(LOG, "w", encoding="utf-8") as f:
            f.write("boot start\n")
        _log("python " + sys.version.replace("\n", " "))
        _log("import pygame...")
        import pygame
        _log("pygame " + pygame.version.ver)
        _log("import Game...")
        from game import Game
        _log("Game imported")
        game = Game()
        _log("Game() ok, run()")
        game.run()
        _log("run() returned")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception:
        import traceback
        tb = traceback.format_exc()
        _log(tb)
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        if os.name == "nt":
            try:
                input("\n[ERREUR] voir boot.log — Entree pour fermer...")
            except Exception:
                pass
        sys.exit(1)
