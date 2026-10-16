"""The equalizer of the jukebox: a hi-fi LED rack of the 80s (src/pheq.py), 32 columns of 12 diodes green -> amber ->
red, faint unlit diodes, a white peak diode, a glow; the seek bar under it."""
import pygame
import pytest

import pheq

W, H = 1280, 720


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


def _drawn(bands, peaks):
    surf = pygame.Surface((W, H)).convert()
    surf.fill((0, 0, 0))
    pheq.draw(surf, pygame, bands, peaks, W, H)
    return surf


def _diode(col, seg):
    """Centre of diode `seg` of column `col`."""
    x0, x1, y_bot, _h, _p = pheq._geometry(W, H)
    cw = (x1 - x0) / pheq.COLS
    x = int(x0 + col * cw) + 2 + (int(cw) - 4) // 2
    y = y_bot - (seg + 1) * (pheq.SEG_H + pheq.SEG_GAP) + pheq.SEG_H // 2
    return x, y


def test_the_colours_go_from_green_to_amber_to_red():
    assert pheq.seg_colour(0) == pheq.GREEN and pheq.seg_colour(pheq.SEGS - 1) == pheq.RED
    assert pheq.AMBER in [pheq.seg_colour(s) for s in range(pheq.SEGS)]


def test_forty_bands_fold_into_32_columns():
    vals = pheq._column_values([i / 39 for i in range(40)])
    assert len(vals) == pheq.COLS and vals[0] < vals[-1] and max(vals) <= 1.0


def test_a_loud_band_lights_its_column_and_a_silent_one_only_shows_faint_diodes():
    bands = [1.0] * 20 + [0.0] * 20
    surf = _drawn(bands, [0.0] * 40)
    lit = surf.get_at(_diode(0, 0))
    top = surf.get_at(_diode(0, pheq.SEGS - 1))
    off = surf.get_at(_diode(pheq.COLS - 1, 0))
    assert lit.g > 200 and lit.r < 150                     # a green diode, lit
    assert top.r > 200 and top.g < 150                     # the top one is red
    assert off.g < 60                                      # unlit: only the faint diode (and a little glow)


def test_the_peak_is_a_white_diode_above_the_lit_ones():
    bands = [0.25] * 40
    surf = _drawn(bands, [0.8] * 40)
    seg = int(0.8 * pheq.SEGS)
    c = surf.get_at(_diode(5, seg))
    assert min(c.r, c.g, c.b) > 200                       # white
    assert surf.get_at(_diode(5, seg - 2)).g < 120          # dark between the bar and its peak


def test_the_seek_bar_and_the_clock_sit_around_the_rack():
    _x0, _x1, _y, _h, panel = pheq._geometry(W, H)
    assert pheq.clock_y(H) + 30 <= panel[1]                 # the time above the box
    surf = pygame.Surface((W, H)).convert()
    surf.fill((0, 0, 0))
    pheq.draw_seek(surf, pygame, 30.0, 120.0, W, H)
    y = H - pheq.SEEK_FROM_BOTTOM + 3
    quarter = panel[0] + panel[2] // 4
    assert surf.get_at((panel[0] + 20, y))[:3] == pheq.SEEK_COL          # played
    assert surf.get_at((quarter + 60, y))[:3] == (36, 38, 56)          # still to play
    assert panel[1] + panel[3] < y - 3 < H - 40                        # under the box, above the help bar


def test_nothing_without_bands():
    surf = pygame.Surface((W, H)).convert()
    surf.fill((1, 2, 3))
    pheq.draw(surf, pygame, [], [], W, H)
    assert surf.get_at((W // 2, H - 150))[:3] == (1, 2, 3)
