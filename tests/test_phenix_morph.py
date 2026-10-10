"""The transformation ship -> Phenix and back is smooth: pictures between the drawn ones, at the pace of the screen.

It used to be 4 drawn pictures in 0.45 s (the last one never shown), starting on the second one, with the ship
and the flight popping in and out. Now it goes ship, the drawn pictures, first flight picture, with cross-dissolves
between each two, and starts and ends on exactly the pictures that come before and after it.
"""
import numpy as np
import pygame
import pytest

from phenix_art import LEAD_STEPS, MORPH_STEPS, PHENIX_MORPH_IN_SEC, PHENIX_MORPH_OUT_SEC, lead_in, morph_sequence
from test_smoke import run  # noqa: F401  (fixture)


@pytest.fixture
def game(run):
    return run.game


class Keys:
    def __getitem__(self, _):
        return False


def _picture(w, h, rgba, box=None):
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    surf.fill(rgba, box if box is not None else surf.get_rect())
    return surf.convert_alpha()


def _centred(surf, size=(60, 60)):
    """What the game shows when it draws `surf` centred on the middle of a canvas of `size`."""
    canvas = pygame.Surface(size)
    canvas.fill((0, 0, 0))
    canvas.blit(surf, (size[0] // 2 - surf.get_width() // 2, size[1] // 2 - surf.get_height() // 2))
    return pygame.surfarray.array3d(canvas).astype(int)


# --- the pictures between ---------------------------------------------------------------------------------------

def test_the_sequence_has_every_drawn_picture_and_pictures_between_them(game):
    ship, flight = _picture(10, 14, (200, 200, 200, 255)), _picture(31, 35, (255, 120, 0, 255))
    drawn = [_picture(20, 24, (255, 0, 0, 255)), _picture(21, 25, (0, 255, 0, 255))]
    seq = morph_sequence(ship, drawn, flight)
    keys = [ship] + drawn + [flight]
    assert len(seq) == (len(keys) - 1) * (MORPH_STEPS + 1) + 1
    assert len({s.get_size() for s in seq}) == 1 and seq[0].get_size() == (31, 35)
    for i, key in enumerate(keys):
        # each drawn picture is on screen exactly as the game draws it, whatever the canvas it sits in
        assert (_centred(seq[i * (MORPH_STEPS + 1)]) == _centred(key)).all(), i


def test_a_pixel_in_both_pictures_changes_colour_and_stays_solid(game):
    a, b = _picture(8, 8, (255, 0, 0, 255)), _picture(8, 8, (0, 0, 255, 255))
    seq = morph_sequence(a, [b], b)
    red = [int(pygame.surfarray.array3d(s)[4, 4][0]) for s in seq[: MORPH_STEPS + 2]]
    blue = [int(pygame.surfarray.array3d(s)[4, 4][2]) for s in seq[: MORPH_STEPS + 2]]
    alpha = [int(pygame.surfarray.array_alpha(s)[4, 4]) for s in seq[: MORPH_STEPS + 2]]
    assert red == sorted(red, reverse=True) and red[0] == 255 and red[-1] == 0
    assert blue == sorted(blue) and blue[0] == 0 and blue[-1] == 255
    assert all(x == 255 for x in alpha)                          # no dip in the middle


def test_a_pixel_only_in_one_picture_fades_out_or_in(game):
    a = _picture(8, 8, (255, 255, 255, 255), pygame.Rect(0, 0, 4, 8))      # left half
    b = _picture(8, 8, (255, 255, 255, 255), pygame.Rect(4, 0, 4, 8))      # right half
    seq = morph_sequence(a, [b], b)[: MORPH_STEPS + 2]
    left = [int(pygame.surfarray.array_alpha(s)[1, 4]) for s in seq]
    right = [int(pygame.surfarray.array_alpha(s)[6, 4]) for s in seq]
    assert left == sorted(left, reverse=True) and left[0] == 255 and left[-1] == 0
    assert right == sorted(right) and right[0] == 0 and right[-1] == 255
    assert len(set(left)) == len(left)                           # a new step each time


def test_a_half_transparent_pixel_is_not_darkened_by_the_mix(game):
    a = _picture(8, 8, (255, 40, 0, 128))
    b = _picture(8, 8, (0, 0, 0, 0))
    for s in morph_sequence(a, [b], b)[1: MORPH_STEPS + 1]:
        r, g, _bl = pygame.surfarray.array3d(s)[4, 4]
        assert r >= 250 and 35 <= g <= 45                        # the colour stays, only the alpha goes down


def test_nothing_drawn_gives_no_sequence(game):
    ship = _picture(10, 14, (200, 200, 200, 255))
    assert morph_sequence(ship, [], ship) == []
    assert morph_sequence(ship, [ship], None) == []


def test_lead_in_joins_two_pictures_without_showing_either(game):
    a = _picture(10, 10, (255, 255, 255, 255), pygame.Rect(0, 0, 5, 10))
    b = _picture(10, 10, (255, 255, 255, 255), pygame.Rect(5, 0, 5, 10))
    seq = lead_in(a, b)
    assert len(seq) == LEAD_STEPS
    left = [int(pygame.surfarray.array_alpha(s)[2, 5]) for s in seq]
    assert all(0 < x < 255 for x in left) and left == sorted(left, reverse=True)


# --- in the game --------------------------------------------------------------------------------------------------

def _render(player):
    surf = pygame.Surface((500, 400))
    surf.fill((0, 0, 0))
    player.engine_intensity = 0.0
    player.draw(surf)
    return pygame.surfarray.array3d(surf).astype(int)


def _flight(player, tint="argent", frames=0):
    player.phenix_gauge = 10.0
    player.phenix_cooldown = 0.0
    assert player.try_activate_phenix()
    return player


def _play(player, dt=1 / 60):
    """The pictures shown from the start of the change in, then 30 of flight, then the way back (from the last
    flight picture), then the ship again."""
    shown_in, shown_flight, shown_out = [], [], []
    for _ in range(200):
        if player.morph_dir <= 0:
            break
        shown_in.append(_render(player))
        player.update(dt, Keys())
    for _ in range(30):
        shown_flight.append(_render(player))
        player.update(dt, Keys())
    player.end_phenix(grant_invuln=False, keep_gauge=True)
    for _ in range(200):
        if player.morph_dir >= 0:
            break
        shown_out.append(_render(player))
        player.update(dt, Keys())
    return shown_in, shown_flight, shown_out, _render(player)


def _steps(seq):
    return [int(np.abs(seq[i] - seq[i - 1]).sum()) for i in range(1, len(seq))]


def _distinct(seq):
    return 1 + sum(int((seq[i] != seq[i - 1]).any()) for i in range(1, len(seq)))


@pytest.mark.parametrize("tint", ["argent", "gold", "blue"])
def test_the_change_is_one_picture_per_screen_frame_both_ways(game, tint):
    from player import Player

    p = Player(250, 200, tint=tint)
    assert len(p.morph_frames) == 5 * (MORPH_STEPS + 1) + 1
    shown_in, shown_flight, shown_out, ship_again = _play(_flight(p))
    assert _distinct(shown_in) >= 24 and _distinct(shown_out) >= 24       # it was 3 and 3
    ship_still = _render(Player(250, 200, tint=tint))
    assert (shown_in[0] == ship_still).all()                              # it starts on the ship as it was
    assert (ship_again == ship_still).all()                               # and the way back ends on it
    assert (shown_out[-1] != shown_flight[-1]).any()


def test_no_jump_in_the_change_is_bigger_than_the_flight_animation_makes_itself(game):
    from player import Player

    p = Player(250, 200)
    shown_in, shown_flight, shown_out, _ship = _play(_flight(p))
    biggest = max(_steps(shown_flight))
    assert max(_steps(shown_in + [shown_flight[0]])) <= biggest
    assert max(_steps([shown_flight[-1]] + shown_out)) <= biggest         # the start of the way back too


def test_the_change_in_ends_on_the_first_picture_of_the_flight(game):
    from player import Player

    p = Player(250, 200)
    shown_in, shown_flight, _out, _ship = _play(_flight(p))
    assert int(np.abs(shown_in[-1] - shown_flight[0]).sum()) == 0


def test_the_last_instant_of_the_way_back_shows_the_ship_itself(game):
    from player import Player

    p = Player(250, 200)
    _flight(p)
    p.morph_dir, p.morph_timer = 0, 0.0
    p.phenix_timer, p.phenix_duration = 5.0, 5.0
    p.end_phenix(grant_invuln=False, keep_gauge=True)
    assert p.morph_dir < 0
    p.morph_timer = p.morph_duration * 0.999
    assert (_render(p) == _render(Player(250, 200))).all()


def test_the_way_back_starts_from_the_flight_picture_on_show(game):
    from player import Player

    p = Player(250, 200)
    _flight(p)
    p.morph_dir, p.morph_timer = 0, 0.0
    p.phenix_timer, p.phenix_duration = 5.0, 5.0
    p.phenix_anim_time = 0.55                                             # the sixth flight picture
    shown = _render(p)
    p.phenix_anim_time = 0.0
    first = _render(p)
    p.phenix_anim_time = 0.55
    p.end_phenix(grant_invuln=False, keep_gauge=True)
    start = _render(p)                                                    # first picture of the way back
    assert int(np.abs(start - shown).sum()) < int(np.abs(first - shown).sum())   # closer to what was on show


def test_cancelling_in_the_middle_of_the_change_goes_back_from_where_it_was(game):
    from player import Player

    p = Player(250, 200)
    _flight(p)
    for _ in range(14):
        p.update(1 / 60, Keys())
    assert p.morph_dir > 0
    before = _render(p)
    p.end_phenix(grant_invuln=False, keep_gauge=True)
    after = _render(p)
    assert p.morph_dir < 0
    full_jump = int(np.abs(_render(Player(250, 200)) - before).sum())
    assert int(np.abs(after - before).sum()) < 0.5 * full_jump            # no jump back to the end of the change
    p.update(1 / 60, Keys())
    assert p.morph_dir < 0


def test_the_shield_change_is_left_as_it_was(game):
    from player import Player

    p = Player(250, 200, ship_id="shield")
    assert p.morph_frames and len(p.morph_frames) == len(p.shield_on_frames)
    assert all(a is b for a, b in zip(p.morph_frames, p.shield_on_frames))      # not the Phenix sequence
    p.phenix_gauge, p.phenix_cooldown = 10.0, 0.0
    assert p.try_activate_phenix()
    n = len(p.morph_frames)
    p.morph_timer = p.morph_duration * 0.5
    surf = pygame.Surface((500, 400))
    surf.fill((0, 0, 0))
    p.draw(surf)
    expected = pygame.Surface((500, 400))
    expected.fill((0, 0, 0))
    expected.blit(p.image, (int(p.x - p.image.get_width() // 2), int(p.y - p.image.get_height() // 2)))
    frame = p.morph_frames[int(0.5 * (n - 1) + 1e-6)]
    expected.blit(frame, (int(p.x - frame.get_width() // 2), int(p.y - frame.get_height() // 2)))
    assert (pygame.surfarray.array3d(surf) == pygame.surfarray.array3d(expected)).all()


# --- the menu preview ----------------------------------------------------------------------------------------------

def test_the_ship_select_preview_uses_the_same_change(game):
    pack = game.preview_ships["phoenix_argent"]
    assert len(pack["on"]) == len(pack["off"]) == 5 * (MORPH_STEPS + 1) + 1
    assert pack["on_sec"] == PHENIX_MORPH_IN_SEC and pack["off_sec"] == PHENIX_MORPH_OUT_SEC
    assert pack["off"][0] is pack["on"][-1]
    assert "on_sec" not in game.preview_ships["shield"]                   # the shield preview is as it was


def test_the_preview_picks_pictures_over_the_whole_time_of_the_change(game):
    from ship_select_screen import preview_cycle_frame

    pack = game.preview_ships["phoenix_argent"]
    game.ship_cycle_phase = "to_special"
    game.ship_cycle_t = 0.0
    assert preview_cycle_frame(game, pack, pack["idle"], pack["anim"]) is pack["on"][0]
    game.ship_cycle_t = PHENIX_MORPH_IN_SEC - 0.005
    assert preview_cycle_frame(game, pack, pack["idle"], pack["anim"]) is pack["on"][-1]
    game.ship_cycle_t = PHENIX_MORPH_IN_SEC / 2
    mid = preview_cycle_frame(game, pack, pack["idle"], pack["anim"])
    assert mid is pack["on"][len(pack["on"]) // 2]
    game.ship_cycle_phase = "to_idle"
    game.ship_cycle_t = 0.0
    assert preview_cycle_frame(game, pack, pack["idle"], pack["anim"]) is pack["off"][0]
    game.ship_cycle_t = PHENIX_MORPH_OUT_SEC - 0.005
    assert preview_cycle_frame(game, pack, pack["idle"], pack["anim"]) is pack["off"][-1]


def test_the_preview_changes_phase_when_the_change_is_over_not_before(game):
    game.ship_select_index = 0
    game.ship_cycle_focus = 0
    game.ship_cycle_phase = "to_special"
    game.ship_cycle_t = 0.0
    game._tick_preview_cycle(PHENIX_MORPH_IN_SEC - 0.05)
    assert game.ship_cycle_phase == "to_special"
    game._tick_preview_cycle(0.06)
    assert game.ship_cycle_phase == "special"
    game.ship_cycle_phase, game.ship_cycle_t = "to_idle", 0.0
    game._tick_preview_cycle(PHENIX_MORPH_OUT_SEC - 0.05)
    assert game.ship_cycle_phase == "to_idle"
    game._tick_preview_cycle(0.06)
    assert game.ship_cycle_phase == "idle"
