"""Makes the pictures of the central planets of the SpaceWar test levels (assets/sprites/spacewar/), from the photos of
assets/sprites/planets/: saturn.png (the rings are kept: they are NOT part of the zone of the planet), uranus.png and
neptune.png (the disc, cut in a circle with a soft edge).  Each planet is scaled so that its disc has the radius of
`spacewar.PLANETS[key]["r"]` and sits in the middle of a square picture of `["draw"]` px.  Run from the root of the project:
    python tools/make_spacewar_planets.py
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC = os.path.join("assets", "sprites", "planets")
DST = os.path.join("assets", "sprites", "spacewar")
# key: (photo, centre of the disc in the photo, radius of the disc in the photo, final disc radius, picture size)
PLANETS = {
    "saturn": ("saturn.jpg", (587, 360), (222, 205), 64.0, 320),
    "uranus": ("uranus.jpg", (386, 562), (211, 211), 40.0, 100),
    "neptune": ("neptune.jpg", (362, 540), (276, 276), 38.0, 100),
}
OVER = 4


def make(key):
    name, (cx, cy), (rx, ry), radius, size = PLANETS[key]
    photo = Image.open(os.path.join(SRC, name)).convert("RGB")
    k = radius / ((rx + ry) / 2.0)                        # photo px -> final px
    big = size * OVER
    s = k * OVER                                          # photo px -> oversampled px
    scaled = photo.resize((max(1, int(photo.width * s)), max(1, int(photo.height * s))), Image.LANCZOS)
    canvas = Image.new("RGB", (big, big), (0, 0, 0))
    canvas.paste(scaled, (int(big / 2 - cx * s), int(big / 2 - cy * s)))
    # the disc: opaque inside, a soft edge
    disc = Image.new("L", (big, big), 0)
    ex, ey = rx * s, ry * s
    ImageDraw.Draw(disc).ellipse((big / 2 - ex + 3, big / 2 - ey + 3, big / 2 + ex - 3, big / 2 + ey - 3), fill=255)
    disc = disc.filter(ImageFilter.GaussianBlur(OVER * 1.2))
    if key == "saturn":
        # the rings: the black of the photo is the sky, so the light of a pixel is its opacity
        lum = np.asarray(canvas).max(axis=2).astype(np.float32)
        rings = np.clip((lum - 8.0) / 60.0, 0.0, 1.0) * 255.0
        alpha = np.maximum(rings, np.asarray(disc, np.float32))
        alpha = Image.fromarray(alpha.astype(np.uint8), "L")
    else:
        alpha = disc
    canvas.putalpha(alpha)
    out = canvas.resize((size, size), Image.LANCZOS)
    os.makedirs(DST, exist_ok=True)
    out.save(os.path.join(DST, key + ".png"), optimize=True)


def main():
    for key in PLANETS:
        make(key)


if __name__ == "__main__":
    main()
