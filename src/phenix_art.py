"""The Phenix frames (assets/sprites/phenix/phenix_NN.png) are drawn on a canvas larger than the ship.

The artwork used to be cut by the edge of its canvas: the tips of both wings were missing. The missing parts were
added (tools/extend_wings.py) in a margin of WING_PAD_X pixels on each side and WING_PAD_Y pixels above AND below
the ship. The margin is the same on both sides of an axis, so the centre of the canvas is still the centre of the
ship, and nothing the ship already showed moved by one pixel.

The size of the ship is the size of the canvas WITHOUT that margin. Whoever scales a frame to a wanted size must
scale by `ship_size`, never by the size of the canvas, or the ship shrinks by the margin it was given.
"""

WING_PAD_X = 16
WING_PAD_Y = 12


def ship_size(frame):
    """(width, height) of the ship in a Phenix frame, the margin left out. `frame` is a pygame Surface."""
    return frame.get_width() - 2 * WING_PAD_X, frame.get_height() - 2 * WING_PAD_Y
