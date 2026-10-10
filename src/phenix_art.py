"""The Phenix frames (assets/sprites/phenix/phenix_NN.png) are drawn on a canvas larger than the ship.

The artwork used to be cut by the edge of its canvas: the tips of both wings were missing. The missing parts were
added (tools/extend_wings.py) in a margin of WING_PAD_X pixels on each side and WING_PAD_Y pixels above AND below
the ship. The margin is the same on both sides of an axis, so the centre of the canvas is still the centre of the
ship, and nothing the ship already showed moved by one pixel.

The size of the ship is the size of the canvas WITHOUT that margin. Whoever scales a frame to a wanted size must
scale by `ship_size`, never by the size of the canvas, or the ship shrinks by the margin it was given.

The transformation (ship -> Phenix, and back) is drawn from a few pictures that were made by hand. `morph_sequence`
puts pictures between them (cross-dissolves), so that the change is smooth at the pace of the screen and starts
and ends on exactly the pictures that come before and after it.
"""
import pygame

try:                         # the pictures between the drawn ones need numpy; without it the drawn ones are used as they are
    import numpy as np
except ImportError:          # pragma: no cover - exercised by a test that hides numpy
    np = None

WING_PAD_X = 16
WING_PAD_Y = 12

LEAD_STEPS = 3               # pictures that fade the flight picture on show into the way back
MORPH_STEPS = 4              # pictures added between two drawn pictures: 6 drawn ones make 26 in all
PHENIX_MORPH_IN_SEC = 0.45   # ship -> Phenix
PHENIX_MORPH_OUT_SEC = 0.40  # Phenix -> ship


def ship_size(frame):
    """(width, height) of the ship in a Phenix frame, the margin left out. `frame` is a pygame Surface."""
    return frame.get_width() - 2 * WING_PAD_X, frame.get_height() - 2 * WING_PAD_Y


def _on_canvas(frame, size):
    """(premultiplied colour, alpha) arrays of `frame` on a canvas of `size`, where the game puts it when it draws a
    picture centred: the picture's left edge is at centre - width // 2, so the offset here is size // 2 - width // 2."""
    cw, ch = size
    w, h = frame.get_size()
    ox, oy = cw // 2 - w // 2, ch // 2 - h // 2
    rgb = np.zeros((cw, ch, 3), np.float32)
    alpha = np.zeros((cw, ch), np.float32)
    rgb[ox: ox + w, oy: oy + h] = pygame.surfarray.array3d(frame)
    alpha[ox: ox + w, oy: oy + h] = pygame.surfarray.array_alpha(frame)
    return rgb, alpha


def _surface(rgb, alpha):
    cw, ch = alpha.shape
    px = np.zeros((cw, ch, 4), np.uint8)
    px[..., :3] = np.clip(np.rint(rgb), 0, 255)
    px[..., 3] = np.clip(np.rint(alpha), 0, 255)
    return pygame.image.frombuffer(px.transpose(1, 0, 2).tobytes(), (cw, ch), "RGBA").convert_alpha()


def _mix(a, b, t):
    """The picture t of the way from a to b (each a pair from _on_canvas), as a Surface."""
    rgb_a, alpha_a = a
    rgb_b, alpha_b = b
    pre_a, pre_b = rgb_a * (alpha_a / 255.0)[..., None], rgb_b * (alpha_b / 255.0)[..., None]
    alpha = (1.0 - t) * alpha_a + t * alpha_b
    pre = (1.0 - t) * pre_a + t * pre_b
    rgb = np.where(alpha[..., None] > 0.5, pre * 255.0 / np.maximum(alpha, 1e-3)[..., None], 0.0)
    return _surface(rgb, alpha)


def morph_sequence(ship, drawn, flight, steps=MORPH_STEPS):
    """The pictures of the transformation, ship first and the first picture of the flight last: `ship`, then the
    `drawn` pictures, then `flight`, with `steps` cross-dissolves between each two.

    All the pictures have the size of the biggest and sit in it the way the game draws them centred, so each picture
    drawn centred at (x, y) puts every pixel of the original where it was. The drawn pictures themselves are not
    altered. Where a picture is transparent and the next is not, the pixel fades in (the colour is mixed
    premultiplied by the alpha, so a half-transparent pixel is not darkened). Empty when there is nothing drawn, or
    when numpy is missing (the caller then uses the drawn pictures)."""
    if np is None:
        return []
    keys = [ship] + list(drawn) + [flight]
    if not drawn or any(k is None for k in keys):
        return []
    size = (max(k.get_width() for k in keys), max(k.get_height() for k in keys))
    arrays = [_on_canvas(k, size) for k in keys]
    out = []
    for i, a in enumerate(arrays):
        out.append(_surface(*a))
        if i == len(arrays) - 1:
            break
        for j in range(1, steps + 1):
            out.append(_mix(a, arrays[i + 1], j / float(steps + 1)))
    return out


def lead_in(start, end, steps=LEAD_STEPS):
    """`steps` pictures that fade `start` into `end`, neither of them included: they join the flight picture on show
    to the first picture of the way back, which is another one of the flight. Empty when numpy is missing."""
    if np is None:
        return []
    size = (max(start.get_width(), end.get_width()), max(start.get_height(), end.get_height()))
    a, b = _on_canvas(start, size), _on_canvas(end, size)
    return [_mix(a, b, j / float(steps + 1)) for j in range(1, steps + 1)]
