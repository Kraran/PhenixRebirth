"""Make the pictures behind the panes of the Adventure hub: assets/story/ui_<pane>.jpg (1280x720, darkened, light vignette).

    python tools/make_ui_backdrops.py map=SRC hangar=SRC bestiary=SRC log=SRC extras=SRC [--dir OUT]

SRC is any picture (it is cropped to 16:9 around its centre, then darkened so the panels and the text read on it).
The look is in this file (BRIGHTNESS, VIGNETTE): change it, run it again and commit the pictures. Needs numpy and pygame.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np  # noqa: E402
import pygame  # noqa: E402

W, H = 1280, 720
BRIGHTNESS = {"map": 0.58, "hangar": 0.62, "bestiary": 0.52, "log": 0.62, "extras": 0.68}
VIGNETTE = 0.55            # how dark the corners get (0 = none)


def bake(src, name):
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    raw = pygame.image.load(src).convert()
    k = max(W / raw.get_width(), H / raw.get_height())
    size = (int(round(raw.get_width() * k)), int(round(raw.get_height() * k)))
    big = pygame.transform.smoothscale(raw, size)
    img = pygame.Surface((W, H))
    img.blit(big, ((W - size[0]) // 2, (H - size[1]) // 2))
    px = pygame.surfarray.array3d(img).astype(np.float32)               # (W, H, 3)
    x = (np.arange(W, dtype=np.float32) - W / 2) / (W / 2)
    y = (np.arange(H, dtype=np.float32) - H / 2) / (H / 2)
    d = np.sqrt(x[:, None] ** 2 * 0.6 + y[None, :] ** 2 * 0.9)
    shade = BRIGHTNESS[name] * (1.0 - VIGNETTE * np.clip(d - 0.35, 0, 1) ** 1.5)
    out = np.clip(px * shade[:, :, None], 0, 255).astype(np.uint8)
    return pygame.surfarray.make_surface(out)


def main(argv):
    out_dir = os.path.join(ROOT, "assets", "story")
    pairs = []
    i = 0
    while i < len(argv):
        if argv[i] == "--dir":
            out_dir = argv[i + 1]
            i += 2
            continue
        name, _eq, src = argv[i].partition("=")
        pairs.append((name, src))
        i += 1
    for name, src in pairs:
        if name not in BRIGHTNESS:
            raise SystemExit("unknown pane: " + name)
        path = os.path.join(out_dir, "ui_" + name + ".jpg")
        pygame.image.save(bake(src, name), path)
        print(path, os.path.getsize(path) // 1024, "KB")


if __name__ == "__main__":
    main(sys.argv[1:])
