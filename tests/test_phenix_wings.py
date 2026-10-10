"""The Phenix frames carry their wing tips again, on a larger canvas, and the ship keeps its size and its place.

The frames used to be cut by the edge of their canvas (73x110). The wings now go on in a margin (src/phenix_art.py)
which is the same above and below, and on both sides, so the centre of the canvas stays the centre of the ship.
Whoever scales a frame must scale by the ship, never by the canvas.
"""
import os
import sys

import numpy as np
import pygame
import pytest

from phenix_art import WING_PAD_X, WING_PAD_Y, ship_size
from settings import asset_path
from test_smoke import run  # noqa: F401  (fixture)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))

PHENIX_DIR = asset_path("sprites", "phenix")
NAMES = ["phenix_%02d.png" % i for i in range(8)]


def _alpha(name):
    surf = pygame.image.load(os.path.join(PHENIX_DIR, name))
    return surf, pygame.surfarray.array_alpha(surf).T            # (rows, columns)


@pytest.fixture
def game(run):
    return run.game


# --- the frames --------------------------------------------------------------------------------------------

def test_the_ship_in_every_frame_is_the_size_it_always_was():
    """73 or 74 wide, 110 high, as before: only the margin was added."""
    for name in NAMES:
        surf = pygame.image.load(os.path.join(PHENIX_DIR, name))
        w, h = ship_size(surf)
        assert h == 110, name
        assert w in (73, 74), (name, w)


def test_the_margin_is_even_so_the_ship_stays_at_the_centre_of_its_canvas():
    """A frame is drawn centred: the ship is at the same place only if the margin is the same on both sides."""
    for name in NAMES:
        surf, alpha = _alpha(name)
        w, h = ship_size(surf)
        assert surf.get_width() // 2 - WING_PAD_X == w // 2, name
        assert surf.get_height() // 2 - WING_PAD_Y == h // 2, name
        assert alpha[-WING_PAD_Y:].max() == 0, name             # nothing was added below the ship


def test_the_wings_no_longer_touch_the_edge_of_the_canvas():
    for name in NAMES:
        _surf, alpha = _alpha(name)
        assert (alpha[:, 0] > 40).sum() == 0, name
        assert (alpha[:, -1] > 40).sum() == 0, name
        assert (alpha[0] > 40).sum() == 0, name


def test_the_wings_go_on_in_the_margin_on_both_sides():
    for name in NAMES:
        _surf, alpha = _alpha(name)
        left = (alpha[:, :WING_PAD_X] > 40).sum()
        right = (alpha[:, -WING_PAD_X:] > 40).sum()
        assert left > 100 and right > 100, (name, left, right)
        assert min(left, right) > 0.5 * max(left, right), (name, left, right)       # one wing each side


# --- in the game ---------------------------------------------------------------------------------------------

def _draw_phenix(player, frame):
    from player import Player  # noqa: F401
    player.phenix_frames = [frame]
    player.phenix_timer = 5.0
    player.phenix_anim_time = 0.0
    player.engine_intensity = 0.0
    surf = pygame.Surface((400, 400))
    surf.fill((0, 0, 0))
    player.draw(surf)
    return pygame.surfarray.array3d(surf).astype(int)


def test_the_ship_is_drawn_where_it_was_whatever_the_margin(game):
    """Draw the frame, and the frame without its margin (the ship as it was): every pixel of the ship that was
    there is on screen at the same place, the same colour. Only the wing tips are new."""
    from player import Player

    for name in NAMES:
        frame = pygame.image.load(os.path.join(PHENIX_DIR, name)).convert_alpha()
        w, h = ship_size(frame)
        bare = frame.subsurface(pygame.Rect(WING_PAD_X, WING_PAD_Y, w, h)).copy()
        with_margin = _draw_phenix(Player(200, 200), frame)
        as_before = _draw_phenix(Player(200, 200), bare)
        lit = as_before.sum(2) > 0
        assert lit.sum() > 3000
        assert (with_margin[lit] == as_before[lit]).all(), name
        assert (with_margin.sum(2) > 0).sum() > lit.sum() + 200, name       # and the wings came back


def test_help_icons_scale_the_ship_not_the_canvas(game):
    from help_screen import HELP_PHENIX_SHIP_H, build_help_icons

    build_help_icons(game)
    frames = game.help_icons["phenix_frames"]
    assert len(frames) == 8
    assert game.help_icons["phenix_ship_h"] == HELP_PHENIX_SHIP_H
    for frame in frames:
        # the canvas is taller than the ship by the margin: the ship inside is HELP_PHENIX_SHIP_H high
        ship_px = frame.get_height() * 110.0 / (110 + 2 * WING_PAD_Y)
        assert abs(ship_px - HELP_PHENIX_SHIP_H) < 1.0, frame.get_size()


def test_fit_art_by_the_ship_keeps_the_scale_the_wings_do_not_change():
    """Two canvases of the same ship, one with longer wings: by the ship they come out at the same scale; by what
    they show (the crop to the content) the one with longer wings would shrink."""
    from help_screen import fit_art

    short = pygame.Surface((100, 140), pygame.SRCALPHA)
    short.fill((255, 120, 0, 255), pygame.Rect(12, 20, 76, 100))     # the ship: 76 x 100
    wide = pygame.Surface((100, 140), pygame.SRCALPHA)
    wide.fill((255, 120, 0, 255), pygame.Rect(0, 0, 100, 140))       # wings out to the edge of the canvas
    a = fit_art(short, 50, ship_h=100)
    b = fit_art(wide, 50, ship_h=100)
    assert a.get_size() == b.get_size() == (50, 70)                   # 140 * 50 / 100: scaled by the ship
    c = fit_art(short, 50)
    d = fit_art(wide, 50)
    assert c.get_size() != d.get_size()                               # cropping to the content does not


def test_help_page_scales_the_phenix_by_its_ship_when_it_draws(game, monkeypatch):
    """The page asks fit_art to scale the Phenix by the height of the ship in it, not by what it shows."""
    import help_screen

    calls = []
    real = help_screen.fit_art

    def spy(surf, box_h=90, ship_h=None):
        calls.append((surf, box_h, ship_h))
        return real(surf, box_h, ship_h)

    monkeypatch.setattr(help_screen, "fit_art", spy)
    game.menu_screen = "help"
    game.help_page = 1
    game.dt = 1 / 60
    game.handle_events()
    game.update()
    game.draw()
    sizes = {f.get_size() for f in game.help_icons["phenix_frames"]}
    phenix = [c for c in calls if c[0] is not None and c[0].get_size() in sizes]
    assert phenix and all(c[2] == help_screen.HELP_PHENIX_SHIP_H for c in phenix)
    others = [c for c in calls if c not in phenix]
    assert others and all(c[2] is None for c in others)           # the ship and the shield are cropped as before


def test_help_page_draws_with_the_larger_frames(game):
    game.menu_screen = "help"
    game.help_page = 1
    for _ in range(3):
        game.dt = 1 / 60
        game.handle_events()
        game.update()
        game.draw()


def test_ship_select_draws_with_the_larger_frames(game):
    game.menu_screen = "ship_select"
    for _ in range(40):
        game.dt = 1 / 60
        game.handle_events()
        game.update()
        game.draw()


# --- the tool that made them -----------------------------------------------------------------------------------

def _wings(w=73, h=110):
    """Two wings climbing out to the edges, cut by them, and a body in the middle."""
    img = np.zeros((h, w, 4), np.float32)
    for y in range(8, 70):
        reach = int((y - 8) * 0.32) + 4                       # the wing gets wider downward
        for x in range(0, w):
            if abs(x - w // 2) > w // 2 - reach and y < 50 + (abs(x - w // 2) // 4):
                img[y, x] = (240, 110 + (x * 3) % 90, 20, 255)
    for y in range(20, 108):
        img[y, w // 2 - 4: w // 2 + 5] = (180, 60, 20, 255)
    return img


def test_the_tool_keeps_every_pixel_of_the_original_and_adds_a_margin():
    import extend_wings as tool

    src = _wings()
    out = tool.extend_frame(src)
    assert out.shape == (110 + 2 * WING_PAD_Y, 73 + 2 * WING_PAD_X, 4)
    inner = out[WING_PAD_Y: WING_PAD_Y + 110, WING_PAD_X: WING_PAD_X + 73]
    assert (inner == src).all()
    assert out[-WING_PAD_Y:, :, 3].max() == 0
    assert (out[:, :WING_PAD_X, 3] > 40).sum() > 60               # the left wing went on
    assert (out[:, -WING_PAD_X:, 3] > 40).sum() > 60              # and the right one


def test_the_tool_treats_both_wings_alike():
    import extend_wings as tool

    src = _wings()
    src = np.maximum(src, src[:, ::-1])                           # a symmetric ship
    out = tool.extend_frame(src)
    assert (out == out[:, ::-1]).all()


def test_the_tool_makes_the_wings_end_in_a_point():
    """Far out the margin is empty: the wing does not run to the edge of the new canvas."""
    import extend_wings as tool

    out = tool.extend_frame(_wings())
    assert (out[:, 0, 3] > 40).sum() == 0
    assert (out[:, -1, 3] > 40).sum() == 0
    near = (out[:, WING_PAD_X - 2, 3] > 40).sum()
    far = (out[:, 3, 3] > 40).sum()
    assert near > far


def test_the_tool_leaves_a_frame_without_wings_at_the_edge_alone():
    import extend_wings as tool

    src = np.zeros((110, 73, 4), np.float32)
    src[30:100, 25:48] = (200, 80, 20, 255)                       # only a body, nothing cut
    out = tool.extend_frame(src)
    assert (out[:, :WING_PAD_X, 3] > 0).sum() == 0
    assert (out[:, -WING_PAD_X:, 3] > 0).sum() == 0
    assert (out[:WING_PAD_Y, :, 3] > 0).sum() == 0


def test_the_tool_command_line_writes_every_frame(tmp_path):
    import extend_wings as tool

    src_dir, out_dir = tmp_path / "src", tmp_path / "out"
    src_dir.mkdir()
    for i in range(2):
        tool.save_rgba(_wings(), str(src_dir / ("phenix_%02d.png" % i)))
    sys.argv = ["extend_wings.py", str(src_dir), str(out_dir)]
    tool.main()
    for i in range(2):
        surf = pygame.image.load(str(out_dir / ("phenix_%02d.png" % i)))
        assert surf.get_size() == (73 + 2 * WING_PAD_X, 110 + 2 * WING_PAD_Y)
    with pytest.raises(SystemExit):
        sys.argv = ["extend_wings.py", str(out_dir / "nothing"), str(out_dir)]
        os.makedirs(str(out_dir / "nothing"))
        tool.main()


def _wings_cut_on_top():
    src = np.zeros((110, 73, 4), np.float32)
    for y in range(0, 60):                                        # two wings that run into the top edge
        src[y, 4 + y // 6: 16 + y // 6] = (250, 140, 30, 255)
        src[y, 57 - y // 6: 69 - y // 6] = (250, 140, 30, 255)
    src[20:100, 30:43] = (180, 70, 20, 255)
    return src


def test_the_tool_goes_on_upward_where_the_top_edge_cuts_a_wing():
    import extend_wings as tool

    out = tool.extend_frame(_wings_cut_on_top())
    assert (out[:WING_PAD_Y, :, 3] > 40).sum() > 80               # the wings went up past the old top edge
    assert (out[0, :, 3] > 40).sum() == 0                         # and end before the new one
    top = (out[WING_PAD_Y - 1, :, 3] > 40).sum()
    high = (out[2, :, 3] > 40).sum()
    assert top > high                                             # narrower the higher they go


def test_the_tool_cleans_specks_from_the_margin_and_only_there():
    import extend_wings as tool

    h, w = 110 + 2 * WING_PAD_Y, 73 + 2 * WING_PAD_X
    canvas = np.zeros((h, w, 4), np.float32)
    own = np.zeros((h, w), bool)
    own[WING_PAD_Y: WING_PAD_Y + 110, WING_PAD_X: WING_PAD_X + 73] = True
    canvas[WING_PAD_Y + 30, WING_PAD_X + 5] = (255, 0, 0, 10)     # a faint pixel of the original: untouched
    canvas[60, 3] = (255, 200, 0, 255)                            # a lone speck in the margin
    canvas[80, 2:6] = (255, 200, 0, 15)                           # too faint to be kept
    canvas[100:108, 0:12] = (255, 200, 0, 255)                    # a real piece of wing, joined to the ship
    canvas[100:108, 12:20] = (255, 200, 0, 255)
    canvas[3, 20:60] = (255, 200, 0, 255)                         # a thin line above the wings
    canvas[50:53, 2:5] = (255, 200, 0, 255)                       # a little island of 9 pixels, with neighbours
    canvas[20:31, 6:20] = (255, 200, 0, 255)                      # a piece of wing joined to the ship...
    canvas[28, 12] = (255, 200, 0, 15)                            # ...with a faint pixel inside it
    canvas[25, 0:6] = (255, 200, 0, 255)                          # ...and a one-pixel spur sticking out of it
    canvas[40, 20:60] = (255, 200, 0, 255)                        # a thin line in the side margin: left alone
    before = canvas.copy()
    out = tool.clean(canvas, own)
    assert out[WING_PAD_Y + 30, WING_PAD_X + 5, 3] == 10
    assert out[60, 3, 3] == 0
    assert out[80, 2:6, 3].max() == 0
    assert out[3, 20:60, 3].max() == 0
    assert out[40, 20:60, 3].min() == 255
    assert out[100:108, 0:12, 3].min() == 255
    assert out[50:53, 2:5, 3].max() == 0                          # the island is gone
    assert out[28, 12, 3] == 0                                    # the faint pixel too
    assert out[25, 0, 3] == 0 and out[25, 1, 3] == 0              # the spur lost its tip
    assert out[25, 3, 3] == 255 and out[20:31, 6:20, 3].sum() > 255 * 140   # the piece of wing is still there
    assert (canvas == before).all()                               # the input was not changed


def test_nothing_faint_is_left_in_the_margin_of_a_finished_frame():
    import extend_wings as tool

    for src in (_wings(), _wings_cut_on_top()):
        out = tool.extend_frame(src)
        own = np.zeros(out.shape[:2], bool)
        own[WING_PAD_Y: WING_PAD_Y + 110, WING_PAD_X: WING_PAD_X + 73] = True
        margin = out[..., 3][~own]
        assert margin.max() > 200
        assert ((margin > 0) & (margin < 28)).sum() == 0
