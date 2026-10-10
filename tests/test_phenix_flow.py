"""The pictures between the drawn ones of the transformation are made by moving the details along a flow, not only
by fading one picture into the other: the hull no longer shows through the wings as a ghost.

The flow (assets/sprites/morph_flow.npz) is calculated once by tools/bake_morph_flow.py; the game only applies it, with
numpy. Without the file, with a different canvas or without numpy, the pictures are plain cross-dissolves.
"""
import numpy as np
import pygame
import pytest

import phenix_art as pa
from phenix_art import MORPH_STEPS, dissolve, morph_flow, morph_sequence
from player import Player, recolor_phenix_frames
from test_smoke import run  # noqa: F401  (fixture)


@pytest.fixture
def game(run):
    return run.game


def _square(x, w=40, h=30, size=8):
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    surf.fill((255, 255, 255, 255), pygame.Rect(x, 11, size, size))
    return surf.convert_alpha()


def _flow_of(shift, pairs=1, size=(40, 30)):
    """The flow of a picture whose details all go `shift` pixels to the right."""
    fab = np.zeros(size + (2,), np.float32)
    fab[..., 0] = shift
    fba = -fab
    return size, [fab] * pairs, [fba] * pairs


def _alpha(surf):
    return pygame.surfarray.array_alpha(surf).astype(float)


# --- the move -----------------------------------------------------------------------------------------------------

def test_warp_with_no_flow_changes_nothing():
    img = np.random.RandomState(1).rand(9, 7, 4).astype(np.float32)
    assert np.allclose(pa._warp(img, np.zeros((9, 7, 2), np.float32), 0.7), img)


def test_warp_moves_by_whole_pixels_and_zero_outside():
    img = np.zeros((10, 6, 1), np.float32)
    img[7, 3, 0] = 5.0
    flow = np.zeros((10, 6, 2), np.float32)
    flow[..., 0] = 2.0                     # samples two pixels to the right: the detail appears two to the left
    out = pa._warp(img, flow, 1.0)
    assert out[5, 3, 0] == pytest.approx(5.0) and out.sum() == pytest.approx(5.0)
    flow[..., 0] = -4.0                    # samples out of the picture on the left: nothing there
    assert pa._warp(img, flow, 1.0)[0:4].sum() == 0.0


def test_warp_between_pixels_is_bilinear_and_keeps_the_sum():
    img = np.zeros((10, 6, 1), np.float32)
    img[4, 3, 0] = 8.0
    flow = np.zeros((10, 6, 2), np.float32)
    flow[..., 0] = 0.25
    out = pa._warp(img, flow, 1.0)
    assert out[4, 3, 0] == pytest.approx(6.0) and out[3, 3, 0] == pytest.approx(2.0)
    assert out.sum() == pytest.approx(8.0)


def test_warp_works_the_same_way_up_and_down():
    img = np.zeros((6, 10, 1), np.float32)
    img[3, 7, 0] = 8.0
    flow = np.zeros((6, 10, 2), np.float32)
    flow[..., 1] = 3.0
    out = pa._warp(img, flow, 1.0)
    assert out[3, 4, 0] == pytest.approx(8.0) and out.sum() == pytest.approx(8.0)
    flow[..., 1] = 0.25
    out = pa._warp(img, flow, 1.0)
    assert out[3, 7, 0] == pytest.approx(6.0) and out[3, 6, 0] == pytest.approx(2.0)


def test_warp_fades_a_detail_at_the_edge_into_nothing_not_into_a_copy_of_the_edge():
    img = np.zeros((6, 6, 1), np.float32)
    img[5, :, 0] = 8.0                      # the last column
    img[:, 5, 0] = 8.0                      # and the last row
    img[0, :, 0] = 8.0                      # and the first column
    flow = np.zeros((6, 6, 2), np.float32)
    flow[..., 0] = 0.5
    assert pa._warp(img, flow, 1.0)[5, 2, 0] == pytest.approx(4.0)       # half of it is outside: zero
    flow[...] = 0.0
    flow[..., 1] = 0.5
    assert pa._warp(img, flow, 1.0)[2, 5, 0] == pytest.approx(4.0)
    flow[...] = 0.0
    flow[..., 0] = -0.5
    assert pa._warp(img, flow, 1.0)[0, 2, 0] == pytest.approx(4.0)       # first column: nothing to the left


def test_a_detail_that_moves_is_one_solid_detail_in_the_middle_not_two_faded_ones(game):
    a, b = _square(4), _square(24)         # 20 pixels apart
    plain = dissolve([a, b], 1)[1]
    moved = dissolve([a, b], 1, _flow_of(20))[1]
    assert _alpha(plain).max() < 140                      # a cross-dissolve: two squares at half strength
    am = _alpha(moved)
    assert am[14:22, 11:19].min() == 255                  # the square halfway, whole and solid
    assert am[:12].sum() == 0 and am[24:].sum() == 0      # and nothing left behind or ahead of it


def test_the_ends_of_a_moved_pair_are_the_pictures_themselves(game):
    a, b = _square(4), _square(24)
    seq = dissolve([a, b], MORPH_STEPS, _flow_of(20))
    assert len(seq) == MORPH_STEPS + 2
    assert (pygame.surfarray.array_alpha(seq[0]) == pygame.surfarray.array_alpha(a)).all()
    assert (pygame.surfarray.array_alpha(seq[-1]) == pygame.surfarray.array_alpha(b)).all()


def test_the_square_goes_the_same_way_all_the_way(game):
    a, b = _square(4), _square(24)
    seq = dissolve([a, b], MORPH_STEPS, _flow_of(20))
    left = [int(np.argmax(_alpha(s).sum(1) > 0)) for s in seq]
    assert left == sorted(left) and left[0] == 4 and left[-1] == 24
    assert len(set(left)) == len(left)
    for j, pic in enumerate(seq):           # every picture has the whole square, solid, wherever it is
        x = left[j]
        assert _alpha(pic)[x + 1: x + 7, 12:18].min() == 255, j


def test_the_colour_of_a_half_transparent_detail_is_kept_when_it_moves(game):
    def picture(x):
        surf = pygame.Surface((40, 30), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        surf.fill((200, 100, 50, 128), pygame.Rect(x, 11, 8, 8))
        return surf.convert_alpha()
    pic = dissolve([picture(4), picture(24)], 1, _flow_of(20))[1]
    rgb, alpha = pygame.surfarray.array3d(pic), pygame.surfarray.array_alpha(pic)
    assert alpha[17, 14] == 128
    assert all(abs(int(v) - w) <= 2 for v, w in zip(rgb[17, 14], (200, 100, 50)))


def test_a_flow_that_does_not_fit_is_not_used(game):
    a, b, c = _square(4), _square(24), _square(4)
    plain = dissolve([a, b, c], 2)
    wrong_pairs = dissolve([a, b, c], 2, _flow_of(20, pairs=1))      # one flow for two pairs
    wrong_size = dissolve([a, b, c], 2, _flow_of(20, pairs=2, size=(41, 30)))
    for seq in (wrong_pairs, wrong_size):
        assert all((pygame.surfarray.array_alpha(x) == pygame.surfarray.array_alpha(y)).all()
                   for x, y in zip(seq, plain))


# --- the file ---------------------------------------------------------------------------------------------------

def test_the_flow_of_the_game_fits_its_pictures(game):
    flow = morph_flow()
    assert flow is not None
    size, fab, fba = flow
    assert size == (105, 134) and len(fab) == len(fba) == 5
    for f in fab + fba:
        assert f.shape == (105, 134, 2) and np.isfinite(f).all() and np.abs(f).max() < 30


def test_the_flow_of_the_game_goes_the_right_way(game):
    """fab: B at x + fab(x) looks like A at x; fba: A at x + fba(x) looks like B at x. The wrong way is not better than
    standing still (this also catches the two lists being swapped in the file or when it is read)."""
    p = Player(300, 300)
    keys = [p.image] + list(p._morph_src) + [p.phenix_frames[0]]
    size, fab, fba = morph_flow()
    arrays = []
    for k in keys:
        rgb, alpha = pa._on_canvas(k, size)
        arrays.append(np.dstack([rgb * (alpha / 255.0)[..., None], alpha]))
    for i in range(5):
        a, b = arrays[i], arrays[i + 1]
        for src, dst, right, wrong in ((b, a, fab[i], fba[i]), (a, b, fba[i], fab[i])):
            err = lambda img: float(np.abs(img - dst).mean())
            assert err(pa._warp(src, right, 1.0)) < err(src), i
            assert err(pa._warp(src, right, 1.0)) < err(pa._warp(src, wrong, 1.0)), i


def test_a_missing_or_damaged_file_gives_none_and_the_game_still_has_its_pictures(tmp_path, game):
    assert morph_flow(str(tmp_path / "nope.npz")) is None
    bad = tmp_path / "bad.npz"
    bad.write_bytes(b"not an archive")
    assert morph_flow(str(bad)) is None
    ship, flight = _square(4), _square(24)
    assert morph_sequence(ship, [_square(8)], flight, use_flow=False)


def test_the_player_gets_the_same_number_of_pictures_and_the_same_ends_as_before(game):
    p = Player(300, 300)
    keys = [p.image] + list(p._morph_src) + [p.phenix_frames[0]]
    plain = morph_sequence(p.image, p._morph_src, p.phenix_frames[0], flash=True, use_flow=False)
    assert len(p.morph_frames) == len(plain) == (len(keys) - 1) * (MORPH_STEPS + 1) + 1
    assert {f.get_size() for f in p.morph_frames} == {plain[0].get_size()}
    assert any((pygame.surfarray.array3d(x) != pygame.surfarray.array3d(y)).any()
               for x, y in zip(p.morph_frames, plain)), "the flow is not used"
    # the pictures at the drawn ones are the drawn ones, as with the plain pictures (the flash is the same)
    for i in range(0, len(plain), MORPH_STEPS + 1):
        assert (pygame.surfarray.array3d(p.morph_frames[i]) == pygame.surfarray.array3d(plain[i])).all(), i


def test_the_three_colours_use_the_flow(game):
    for tint in ("argent", "gold", "blue"):
        p = Player(300, 300, tint=tint)
        plain = morph_sequence(p.image, recolor_phenix_frames(p._morph_src, tint),
                               p.phenix_frames[0], flash=True, use_flow=False)
        assert len(p.morph_frames) == len(plain)
        assert any((pygame.surfarray.array3d(x) != pygame.surfarray.array3d(y)).any()
                   for x, y in zip(p.morph_frames, plain)), tint


def test_without_numpy_nothing_is_asked_of_the_flow(monkeypatch):
    monkeypatch.setattr(pa, "np", None)
    assert morph_flow() is None
    assert morph_sequence(None, [], None) == []
