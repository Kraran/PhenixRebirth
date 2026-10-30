"""Makes assets/sprites/spacewar/jupiter.png (the star of the SpaceWar test level) from the photo of Jupiter:
the disc is cut out in a circle with a soft edge, 160 x 160 px.  Run from the root of the project:
    python tools/make_spacewar_jupiter.py
"""
import os

from PIL import Image, ImageDraw, ImageFilter

SRC = os.path.join("assets", "sprites", "planets", "jupiter.jpg")
DST = os.path.join("assets", "sprites", "spacewar", "jupiter.png")
CENTER = (394, 558)        # the disc in the photo
RADIUS = 296
SIZE = 160


def main():
    photo = Image.open(SRC).convert("RGB")
    box = (CENTER[0] - RADIUS, CENTER[1] - RADIUS, CENTER[0] + RADIUS, CENTER[1] + RADIUS)
    disc = photo.crop(box).resize((SIZE * 4, SIZE * 4), Image.LANCZOS)
    mask = Image.new("L", disc.size, 0)
    ImageDraw.Draw(mask).ellipse((6, 6, disc.size[0] - 7, disc.size[1] - 7), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(5))
    disc.putalpha(mask)
    disc = disc.resize((SIZE, SIZE), Image.LANCZOS)
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    disc.save(DST, optimize=True)


if __name__ == "__main__":
    main()
