"""CRT scanlines (src/crt.py): 240 soft lines (one every 3 rows), a vignette, and at levels 2 and 3 the glow of the
bright parts that spill into the dark gaps."""
import pygame
import pytest

import crt
from settings import BASE_HEIGHT, BASE_WIDTH

SIZE = (BASE_WIDTH, BASE_HEIGHT)
MID = BASE_WIDTH // 2


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


def _picture(value):
    surf = pygame.Surface(SIZE).convert()
    surf.fill((value, value, value))
    return surf


def test_no_layers_at_level_0():
    assert crt.build(0, SIZE) is None


@pytest.mark.parametrize("level", [1, 2, 3])
def test_a_line_every_three_rows_with_a_soft_profile(level):
    layers = crt.build(level, SIZE, _picture(0))
    mask = layers["mask"]
    y0 = BASE_HEIGHT // 2 - (BASE_HEIGHT // 2) % 3           # the start of a line, in the middle of the screen
    near, centre, gap = (mask.get_at((MID, y0 + i))[0] for i in range(3))
    assert gap < near < centre and centre >= 250                     # the beam, then the dark gap
    assert mask.get_at((MID, y0 + 3))[0] == near                     # it repeats every 3 rows (240 lines)
    assert mask.get_at((5, 5))[0] < mask.get_at((MID, BASE_HEIGHT // 2 + 1))[0]       # darker corners
    assert layers["glow"] == (level >= 2)                             # the glow: levels 2 and 3


def test_stronger_levels_have_darker_gaps():
    gaps = [crt.build(lv, SIZE, _picture(0))["mask"].get_at((MID, 362))[0] for lv in (1, 2, 3)]
    assert gaps[0] > gaps[1] > gaps[2]


def _gap_row():
    y = BASE_HEIGHT // 2
    return y - y % 3 + 2


def test_the_dark_shows_the_lines():
    for level in (1, 2, 3):
        pic = _picture(80)
        crt.apply(pic, crt.build(level, SIZE, pic))
        assert pic.get_at((MID, _gap_row()))[0] < pic.get_at((MID, _gap_row() - 1))[0] - 15


def test_the_bright_parts_glow_into_the_gaps_at_levels_2_and_3():
    for level in (2, 3):
        pic = _picture(255)
        layers = crt.build(level, SIZE, pic)
        without = layers["mask"].get_at((MID, _gap_row()))[0]           # the gap without the glow
        crt.apply(pic, layers)
        lit = pic.get_at((MID, _gap_row()))[0]
        assert lit >= 255 - crt.GLOW_DROP and lit > without + 30      # the white stays nearly white in the gaps
        dim = _picture(60)
        crt.apply(dim, layers)
        assert dim.get_at((MID, _gap_row()))[0] < 45                    # the dark keeps its lines


def test_nothing_when_there_are_no_layers():
    pic = _picture(100)
    crt.apply(pic, None)
    assert pic.get_at((MID, _gap_row()))[0] == 100


def test_in_the_game_the_picture_gets_its_lines(run):
    g = run.game
    g.scanlines = 2
    g._scanline_surf = None
    run.frames(2)
    assert g._scanline_layers is not None and g._scanline_layers["glow"]
    g.scanlines = 1
    g._scanline_surf = None
    run.frames(2)
    assert not g._scanline_layers["glow"]


from test_smoke import run  # noqa: E402,F401  (fixture)
