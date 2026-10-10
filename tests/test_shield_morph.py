"""The dome of the Shield forms and goes away smoothly, and goes away in the right order.

The way out used to play the drawn pictures backwards: the dome vanished at once, came back to half its size, then
vanished again. Now the picture on show fades into the first picture of the way out, which then goes on to the one that
is nearly gone. Pictures are added between the drawn ones (cross-dissolves), as for the Phenix.
"""
import numpy as np
import pygame
import pytest

from phenix_art import (SHIELD_IN_SEC, SHIELD_IN_STEPS, SHIELD_OUT_SEC, SHIELD_OUT_STEPS, dissolve, lead_in)
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
    canvas = pygame.Surface(size)
    canvas.fill((0, 0, 0))
    canvas.blit(surf, (size[0] // 2 - surf.get_width() // 2, size[1] // 2 - surf.get_height() // 2))
    return pygame.surfarray.array3d(canvas).astype(int)


def _shield():
    from player import Player

    p = Player(250, 200, ship_id="shield")
    p.engine_intensity = 0.0
    return p


def _render(p):
    surf = pygame.Surface((500, 400))
    surf.fill((0, 0, 0))
    p.draw(surf)
    return pygame.surfarray.array3d(surf).astype(int)


def _start(p):
    p.phenix_gauge, p.phenix_cooldown = 10.0, 0.0
    assert p.try_activate_phenix()
    return p


def _play(p, ticks_in=None, hold=10):
    """Dome-only amounts (the picture minus the bare ship) and pictures: in, then `hold` ticks of the loop, then out."""
    bare = _render(_shield())
    dome = lambda: int(np.abs(_render(p) - bare).sum())          # noqa: E731
    ins, loop, out, out_pics, in_pics = [], [], [], [], []
    for _ in range(200):
        if p.morph_dir <= 0:
            break
        ins.append(dome()), in_pics.append(_render(p))
        p.update(1 / 60, Keys())
    for _ in range(hold):
        loop.append(dome())
        p.update(1 / 60, Keys())
    loop_pic = _render(p)
    p.end_phenix(grant_invuln=False, keep_gauge=True)
    for _ in range(200):
        if p.morph_dir >= 0:
            break
        out.append(dome()), out_pics.append(_render(p))
        p.update(1 / 60, Keys())
    return ins, loop, out, in_pics, out_pics, loop_pic, dome()


def _steps(pics):
    return [int(np.abs(pics[i] - pics[i - 1]).sum()) for i in range(1, len(pics))]


def _distinct(pics):
    return 1 + sum(int((pics[i] != pics[i - 1]).any()) for i in range(1, len(pics)))


# --- the pictures between -----------------------------------------------------------------------------------------

def test_dissolve_keeps_every_picture_and_puts_pictures_between(game):
    pics = [_picture(10, 14, (255, 0, 0, 255)), _picture(12, 16, (0, 255, 0, 255)), _picture(11, 15, (0, 0, 255, 255))]
    for steps in (0, 1, 3):
        seq = dissolve(pics, steps)
        assert len(seq) == (len(pics) - 1) * (steps + 1) + 1
        assert len({s.get_size() for s in seq}) == 1 and seq[0].get_size() == (12, 16)
        for i, pic in enumerate(pics):
            assert (_centred(seq[i * (steps + 1)]) == _centred(pic)).all(), (steps, i)


def test_dissolve_of_nothing_or_with_a_missing_picture_is_empty(game, monkeypatch):
    assert dissolve([]) == [] and dissolve([_picture(4, 4, (1, 2, 3, 255)), None]) == []
    import phenix_art

    monkeypatch.setattr(phenix_art, "np", None)
    assert dissolve([_picture(4, 4, (1, 2, 3, 255))]) == []


def test_the_dome_has_pictures_between_the_drawn_ones(game):
    p = _shield()
    assert len(p.shield_in_seq) == (len(p.shield_on_frames) - 1) * (SHIELD_IN_STEPS + 1) + 1
    assert len(p.shield_out_seq) == (len(p.shield_off_frames) - 1) * (SHIELD_OUT_STEPS + 1) + 1
    for seq, drawn, steps in ((p.shield_in_seq, p.shield_on_frames, SHIELD_IN_STEPS),
                              (p.shield_out_seq, p.shield_off_frames, SHIELD_OUT_STEPS)):
        for i, pic in enumerate(drawn):
            assert (_centred(seq[i * (steps + 1)], (96, 128)) == _centred(pic, (96, 128))).all()


def test_the_durations_and_the_game_timing_of_the_bubble_are_what_they_were(game):
    p = _shield()
    assert (p.MORPH_IN_SEC, p.MORPH_OUT_SEC) == (SHIELD_IN_SEC, SHIELD_OUT_SEC) == (0.22, 0.26)
    _start(p)
    assert p.morph_duration == 0.22 and p.phenix_duration == 2.0
    assert p.SHIELD_COOLDOWN == 5.0
    # the bubble lasts 2 s once the dome has formed, and the cooldown starts when the dome has gone: the whole is
    # 0.22 + 2 + 0.26 s from the key to the start of the cooldown (the way the game was before the smoother dome)
    ticks = 0
    while p.phenix_cooldown <= 0.0 and ticks < 1000:
        p.update(1 / 60, Keys())
        ticks += 1
    assert abs(ticks / 60.0 - (0.22 + 2.0 + 0.26)) < 0.08
    assert p.phenix_cooldown == pytest.approx(5.0, abs=0.05)


# --- the dome forming ---------------------------------------------------------------------------------------------

def test_the_dome_forms_with_a_new_picture_almost_every_screen_frame(game):
    p = _start(_shield())
    ins, _loop, _out, in_pics, _op, _lp, _after = _play(p)
    assert len(ins) in (13, 14)                                           # 0.22 s at 60 Hz
    assert _distinct(in_pics) >= len(ins) - 1                             # a new picture at every screen frame (it was 6 of 14)
    assert ins[0] < 0.01 * max(ins)                                       # it starts with no dome
    assert ins == sorted(ins)                                             # and it only grows


def test_the_dome_forming_ends_on_the_first_picture_of_the_loop(game):
    p = _start(_shield())
    _ins, _loop, _out, in_pics, _op, _lp, _after = _play(p)
    loop0 = _render(_start(_shield()))                                    # (the same scene, dome not yet shown)
    p2 = _shield()
    p2.morph_dir = 0
    p2.phenix_timer, p2.phenix_duration = 2.0, 2.0
    p2.phenix_frames = list(p2.shield_loop_frames)
    p2.phenix_anim_time = 0.0
    assert int(np.abs(_render(p2) - in_pics[-1]).sum()) < 0.2 * int(np.abs(_render(p2) - loop0).sum())


def test_no_step_of_the_forming_is_as_big_as_the_biggest_one_it_had(game):
    ins, _l, _o, in_pics, _op, _lp, _a = _play(_start(_shield()))
    assert max(_steps(in_pics)) < 0.7 * 1_548_000                         # it was 1.55 M: pictures 2 and 3 of 8 jumped


# --- the dome going away ------------------------------------------------------------------------------------------

def test_the_dome_goes_away_and_never_comes_back(game):
    _i, loop, out, _ip, out_pics, _lp, after = _play(_start(_shield()))
    assert len(out) in (15, 16)                                           # 0.26 s at 60 Hz
    assert _distinct(out_pics) >= len(out) - 1                            # a new picture at every screen frame (it was 6 of 16)
    assert max(out) <= max(loop) * 1.02                                   # never bigger than the dome that was on show
    assert all(out[i] <= out[i - 1] * 1.03 + 2000 for i in range(1, len(out)))     # it only shrinks and fades
    assert out[-1] < 0.05 * out[0] and after == 0                         # and it is gone at the end


def test_the_way_out_starts_from_the_dome_that_was_on_show(game):
    _i, _l, _o, _ip, out_pics, loop_pic, _a = _play(_start(_shield()))
    first_step = int(np.abs(out_pics[0] - loop_pic).sum())
    others = _steps(out_pics)
    assert first_step <= 1.5 * max(others)                                # no jump: the old way out began from nothing


def test_cancelling_while_the_dome_forms_goes_away_from_the_picture_on_show(game):
    p = _start(_shield())
    for _ in range(6):
        p.update(1 / 60, Keys())
    assert p.morph_dir > 0
    before = _render(p)
    p.end_phenix(grant_invuln=False, keep_gauge=True)
    after = _render(p)
    assert p.morph_dir < 0
    full = int(np.abs(_render(_shield()) - before).sum())
    assert int(np.abs(after - before).sum()) < 0.25 * full               # not a jump to the dome of the loop
    p.update(1 / 60, Keys())
    assert p.morph_dir < 0


# --- other cases ----------------------------------------------------------------------------------------------------

def test_without_numpy_the_dome_uses_the_drawn_pictures_and_still_works(game, monkeypatch):
    import phenix_art

    monkeypatch.setattr(phenix_art, "np", None)
    p = _shield()
    assert len(p.shield_in_seq) == len(p.shield_on_frames) and len(p.shield_out_seq) == len(p.shield_off_frames)
    ins, _l, out, _ip, _op, _lp, after = _play(_start(p))
    assert ins and out and after == 0 and p.morph_dir == 0


def test_the_phenix_is_not_changed_by_the_dome_work(game):
    from player import Player

    p = Player(250, 200)
    assert (p.MORPH_IN_SEC, p.MORPH_OUT_SEC) == (0.45, 0.40)
    assert not hasattr(p, "shield_in_seq") or not p.shield_in_seq


def test_lead_in_still_joins_two_pictures(game):
    a, b = _picture(10, 10, (255, 0, 0, 255)), _picture(10, 10, (0, 0, 255, 255))
    assert len(lead_in(a, b)) == 3


def test_the_way_out_is_joined_to_the_loop_picture_that_was_on_show(game):
    from phenix_art import lead_in as make_lead

    for frame in (0, 3):
        p = _start(_shield())
        for _ in range(40):
            p.update(1 / 60, Keys())
        assert p.morph_dir == 0
        p.phenix_anim_time = frame / float(p.PHENIX_ANIM_FPS) + 0.001          # the picture `frame` of the loop
        shown = p.shield_loop_frames[frame]
        p.end_phenix(grant_invuln=False, keep_gauge=True)
        want = make_lead(shown, p.morph_frames[-1])
        assert len(p._morph_lead) == len(want)
        for got, exp in zip(p._morph_lead, want):
            assert (pygame.surfarray.array3d(got) == pygame.surfarray.array3d(exp)).all()
    assert int(np.abs(pygame.surfarray.array3d(make_lead(p.shield_loop_frames[0], p.morph_frames[-1])[0]).astype(int)
                      - pygame.surfarray.array3d(p._morph_lead[0]).astype(int)).sum()) > 0   # frame 0 and 3 differ
