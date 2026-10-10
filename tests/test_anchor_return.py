"""Return to base by the quantum anchor: when a mission is lost (Normal mode) the last picture of the mission is drawn
into a whirlwind, a flash opens, and the mission map comes back under the fading flash (src/anchor_fx.py).

A fallen Veteran has no anchor (it was never finished): nothing of this for them.
"""
import math
import os
import wave

import numpy as np
import pygame
import pytest

import story_state as ss

import anchor_fx as ax
from anchor_fx import AnchorReturn, BLEND_SEC, FADE_SEC, FLASH_COLOUR, FLASH_SEC, SWIRL_SEC, TOTAL_SEC
from test_smoke import run  # noqa: F401  (fixture)

SIZE = (1280, 720)


def _snapshot(colour=(255, 255, 255), left=None):
    surf = pygame.Surface(SIZE)
    surf.fill(colour)
    if left is not None:
        surf.fill(left, pygame.Rect(0, 0, SIZE[0] // 2, SIZE[1]))
    return surf


@pytest.fixture
def display(run):
    return run


def _px(surf):
    return pygame.surfarray.array3d(surf).astype(int)


# --- the picture ----------------------------------------------------------------------------------------------------

def test_the_first_picture_is_the_mission_exactly(display):
    snap = _snapshot((10, 40, 90), left=(200, 30, 30))
    fx = AnchorReturn(snap)
    out = pygame.Surface(SIZE)
    out.fill((0, 0, 0))
    fx.draw(out)
    assert (_px(out) == _px(snap)).all()


def test_no_jump_when_the_real_picture_stops_showing_through(display):
    snap = _snapshot((90, 90, 120), left=(200, 120, 40))
    fx = AnchorReturn(snap)
    shots = []
    for t in (BLEND_SEC - 1 / 60, BLEND_SEC, BLEND_SEC + 1 / 60):
        fx.t = t
        out = pygame.Surface(SIZE)
        fx.draw(out)
        shots.append(_px(out))
    assert float(np.abs(shots[1] - shots[0]).mean()) < 12
    assert float(np.abs(shots[2] - shots[1]).mean()) < 12


def test_the_picture_shrinks_towards_the_middle(display):
    white, black = AnchorReturn(_snapshot((255, 255, 255))), AnchorReturn(_snapshot((0, 0, 0)))
    covered = []
    for p in (0.2, 0.4, 0.6, 0.8, 0.95):
        diff = np.abs(white.vortex(p).astype(int) - black.vortex(p).astype(int)).max(axis=2)
        covered.append(float((diff > 40).mean()))
    assert covered == sorted(covered, reverse=True) and len(set(covered)) == len(covered), covered
    assert covered[0] > 0.30 and covered[-1] < 0.05, covered


def test_the_middle_turns_more_than_the_outside(display):
    fx = AnchorReturn(_snapshot((0, 0, 255), left=(255, 0, 0)))

    def red_angle(p, radius):
        arr = fx.vortex(p).astype(int)
        angles = np.linspace(-math.pi, math.pi, 720, endpoint=False)
        xs = np.rint(fx.cx + radius * np.cos(angles)).astype(int)
        ys = np.rint(fx.cy + radius * np.sin(angles)).astype(int)
        px = arr[xs, ys]
        red = px[:, 0] > px[:, 2]
        assert red.sum() > 100, (p, radius)
        return math.atan2(np.sin(angles[red]).sum(), np.cos(angles[red]).sum())

    def turned(p, radius):
        d = red_angle(p, radius) - red_angle(0.0, radius)
        return (d + math.pi) % (2 * math.pi) - math.pi

    inner, outer = abs(turned(0.4, 15)), abs(turned(0.4, 45))
    assert inner > outer + 0.25, (inner, outer)
    assert 1.0 < inner < 2.3                                  # about the 1.6 radians the formula gives there


def test_the_turn_goes_on_the_same_way_all_the_swirl(display):
    fx = AnchorReturn(_snapshot((0, 0, 255), left=(255, 0, 0)))

    def red_angle(p):
        arr = fx.vortex(p).astype(int)
        angles = np.linspace(-math.pi, math.pi, 720, endpoint=False)
        px = arr[np.rint(fx.cx + 12 * np.cos(angles)).astype(int), np.rint(fx.cy + 12 * np.sin(angles)).astype(int)]
        red = px[:, 0] > px[:, 2]
        return math.atan2(np.sin(angles[red]).sum(), np.cos(angles[red]).sum())

    seen = [red_angle(p) for p in (0.0, 0.1, 0.2, 0.3)]
    steps = [((b - a) + math.pi) % (2 * math.pi) - math.pi for a, b in zip(seen, seen[1:])]
    assert all(s < 0 for s in steps) or all(s > 0 for s in steps), steps
    assert abs(steps[-1]) > abs(steps[0])                     # faster and faster


def test_the_flash_opens_from_the_middle_and_covers_everything(display):
    fx = AnchorReturn(_snapshot((120, 120, 120)))
    assert (fx.vortex(1.0, 0.0)[10, 10] != np.array(FLASH_COLOUR)).any()
    small = fx.vortex(1.0, 0.3)
    mid, corner = small[fx.rings.shape[0] // 4, 0], small[0, 0]
    assert abs(int(small[int(fx.cx), int(fx.cy)].astype(int).sum()) - sum(FLASH_COLOUR)) < 40     # the middle is lit first
    assert corner.astype(int).sum() < sum(FLASH_COLOUR) - 100                                         # the corner is not yet
    full = fx.vortex(1.0, 1.0)
    assert (full == np.array(FLASH_COLOUR, np.uint8)).all()


def test_the_map_comes_back_under_a_flash_that_fades(display):
    fx = AnchorReturn(_snapshot())
    means, first = [], None
    for k in range(0, 10):
        fx.t = SWIRL_SEC + FLASH_SEC + FADE_SEC * k / 10.0
        out = pygame.Surface(SIZE)
        out.fill((0, 0, 0))                                   # the map, here black
        fx.draw(out)
        means.append(float(_px(out).mean()))
        if k == 0:
            first = _px(out)
    assert (first == np.array(FLASH_COLOUR)).all()            # starts as a full flash: the swirl and flash end on it
    assert means == sorted(means, reverse=True) and means[-1] < means[0] * 0.15, means
    fx.t = TOTAL_SEC
    out = pygame.Surface(SIZE)
    out.fill((7, 8, 9))
    fx.draw(out)
    assert (_px(out) == np.array((7, 8, 9))).all()            # done: the map as it is


def test_phases_and_the_time_they_take(display):
    fx = AnchorReturn(_snapshot())
    assert fx.phase == "swirl" and not fx.done
    fx.t = SWIRL_SEC
    assert fx.phase == "flash"
    fx.t = SWIRL_SEC + FLASH_SEC
    assert fx.phase == "fade"
    fx.t = TOTAL_SEC
    assert fx.phase == "done" and fx.done
    assert TOTAL_SEC == pytest.approx(SWIRL_SEC + FLASH_SEC + FADE_SEC)
    assert 2.5 < TOTAL_SEC < 3.5                              # long enough to be seen, short enough not to be a wait


def test_update_moves_the_time_and_skip_goes_to_the_end_of_the_flash(display):
    fx = AnchorReturn(_snapshot())
    fx.update(0.5)
    fx.update(-3.0)                                           # time never goes back
    assert fx.t == pytest.approx(0.5)
    fx.skip()
    assert fx.t == pytest.approx(SWIRL_SEC + FLASH_SEC) and fx.phase == "fade"
    fx.t = TOTAL_SEC - 0.1
    fx.skip()
    assert fx.t == pytest.approx(TOTAL_SEC - 0.1)             # skip never goes back either


def test_the_legend_shows_in_the_second_half_of_the_swirl_and_goes_with_the_flash(display):
    title = pygame.Surface((300, 40))
    title.fill((255, 255, 255))
    snap = _snapshot((0, 0, 0))
    plain, with_legend = AnchorReturn(snap), AnchorReturn(snap, title=title)

    def diff(t):
        shots = []
        for fx in (plain, with_legend):
            fx.t = t
            out = pygame.Surface(SIZE)
            fx.draw(out)
            shots.append(_px(out))
        return int(np.abs(shots[0] - shots[1]).sum())

    assert diff(0.2) == 0                                     # not yet
    assert diff(SWIRL_SEC * 0.6) > 0
    assert diff(SWIRL_SEC * 0.6) > diff(SWIRL_SEC * 0.5)      # coming in
    assert diff(SWIRL_SEC + FLASH_SEC) == 0                   # gone with the flash


def test_without_numpy_or_a_picture_there_is_no_effect(monkeypatch, display):
    assert ax.make(None) is None
    monkeypatch.setattr(ax, "np", None)
    assert ax.make(_snapshot()) is None


def test_the_vortex_is_made_in_a_few_milliseconds(display):
    import time
    fx = AnchorReturn(_snapshot())
    fx.vortex(0.5)
    t0 = time.perf_counter()
    for _ in range(10):
        fx.vortex(0.5, 0.2)
    per = (time.perf_counter() - t0) / 10
    assert per < 0.06, per                                    # a loose guard: it is about 7 ms here, the frame is 16 ms


# --- the sound -------------------------------------------------------------------------------------------------------

def test_the_sound_is_there_and_follows_the_picture():
    path = os.path.join(os.path.dirname(__file__), "..", "assets", "sounds", "anchor_return.wav")
    with wave.open(path) as w:
        seconds = w.getnframes() / float(w.getframerate())
        assert w.getnchannels() == 2 and w.getsampwidth() == 2
    assert SWIRL_SEC + FLASH_SEC < seconds < TOTAL_SEC + 1.0


# --- in the game -----------------------------------------------------------------------------------------------------

def _launch(g, mode="normal"):
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    g.menu_screen = "story_hub"
    g.story.open_slot(1)
    g.story.map_index = 0
    spec = g.story._launch_selected()
    assert spec
    g._begin_adventure(spec)
    g.input_grace = 0
    return spec


def _lose(run):
    g = run.game
    _launch(g)
    run.frames(30)
    played = []
    real = g.sounds.play
    g.sounds.play = lambda name, *a, **k: (played.append(name), real(name, *a, **k))[1]
    g._end_adventure(False)
    return g, played


def test_a_lost_mission_goes_back_to_base_through_the_vortex(run):
    g, played = _lose(run)
    assert g.anchor_fx is not None and g.anchor_fx.phase == "swirl"
    assert g.started is False and g.menu_screen == "story_hub" and g.adventure is None
    assert "anchor_return" in played
    assert g.story.pane == "map" and g.story.toast                      # the result is banked at once: nothing is lost if the game closes
    frames = 0
    while g.anchor_fx is not None and frames < 600:
        run.frames(1)
        frames += 1
    assert g.anchor_fx is None
    assert abs(frames / 60.0 - TOTAL_SEC) < 0.25, frames
    assert g.menu_screen == "story_hub" and g.story.pane == "map"


def test_the_vortex_is_on_screen_and_the_map_after_it(run):
    g, _ = _lose(run)
    seen = {}
    for name, t in (("swirl", 0.9), ("flash_end", SWIRL_SEC + FLASH_SEC + 0.01), ("late", TOTAL_SEC - 0.2)):
        g.anchor_fx.t = t
        run.frames(1)
        seen[name] = _px(g.screen)
        g.anchor_fx.t = t
    assert float(seen["swirl"][..., 2].mean()) > float(seen["swirl"][..., 0].mean()) + 5     # the vortex is blue
    assert float(seen["flash_end"].mean()) > 200                                              # the flash
    assert float(seen["late"].mean()) < float(seen["flash_end"].mean()) * 0.6                 # then the map


def test_keys_do_nothing_during_the_vortex_but_confirm_skips_it(run):
    g, _ = _lose(run)
    for key in (pygame.K_RIGHT, pygame.K_LEFT, pygame.K_UP, pygame.K_DOWN, pygame.K_a):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0, scancode=0))
    run.frames(3)
    assert g.story.pane == "map" and g.anchor_fx.phase == "swirl"
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0, scancode=0))
    run.frames(1)
    assert g.anchor_fx is not None and g.anchor_fx.phase == "fade"
    assert g.started is False and g.adventure is None                    # the key that skipped did not launch a mission
    assert g.input_grace > 0.2


def test_a_key_held_down_does_not_act_on_the_map_when_the_flash_fades(run):
    g, _ = _lose(run)
    g.input_grace = 0                                                    # (the grace of the end of the mission is gone)
    g.anchor_fx.t = SWIRL_SEC + FLASH_SEC - 0.001
    run.frames(2)
    assert g.anchor_fx.phase == "fade" and g.input_grace > 0.2
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0, scancode=0))
    run.frames(1)
    assert g.started is False and g.adventure is None


def test_key_releases_and_pad_moves_are_swallowed_during_the_vortex_too(run, monkeypatch):
    import input_events
    seen = []
    for name in ("on_keyup", "on_joy_hat", "on_joy_axis", "on_joy_button"):
        monkeypatch.setattr(input_events, name, lambda game, event, name=name: seen.append(name))
    g, _ = _lose(run)
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_LEFT, mod=0, scancode=0))
    pygame.event.post(pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=(1, 0), instance_id=0, joy=0))
    pygame.event.post(pygame.event.Event(pygame.JOYAXISMOTION, axis=0, value=0.9, instance_id=0, joy=0))
    run.frames(2)
    assert seen == [] and g.anchor_fx.phase == "swirl"
    g.anchor_fx.t = SWIRL_SEC + FLASH_SEC + 0.01                         # once the map is back in sight, they work again
    run.frames(1)
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_LEFT, mod=0, scancode=0))
    run.frames(1)
    assert seen == ["on_keyup"]


def test_the_vortex_is_not_drawn_over_a_game_that_is_running(run):
    g, _ = _lose(run)
    drawn = []
    g.anchor_fx.draw = lambda surface: drawn.append(surface)
    run.frames(1)
    assert len(drawn) == 1
    g.started = True
    run.frames(1)
    assert len(drawn) == 1


def test_the_vortex_takes_the_picture_of_the_ships_and_the_caption_with_it(run):
    import draw_frame
    g = run.game
    _launch(g)
    run.frames(30)
    full = _px(g._anchor_snapshot())
    real = draw_frame.draw_play
    draw_frame.draw_play = lambda game: None
    try:
        background = _px(g._anchor_snapshot())
    finally:
        draw_frame.draw_play = real
    assert float(np.abs(full - background).mean()) > 0.2                 # the ship, the invaders, the score are in the picture
    g._end_adventure(False)
    assert g.anchor_fx.title is not None and g.anchor_fx.sub is not None
    assert g.anchor_fx.title.get_width() > 100


def test_a_pad_button_skips_it_too(run):
    g, _ = _lose(run)
    pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=0, instance_id=0, joy=0))
    run.frames(1)
    assert g.anchor_fx.phase == "fade" and g.started is False


def test_the_map_answers_again_when_it_is_back_in_sight(run):
    g, _ = _lose(run)
    g.anchor_fx.t = SWIRL_SEC + FLASH_SEC + 0.01
    run.frames(1)
    g.input_grace = 0
    before = g.story.map_index
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, unicode="", mod=0, scancode=0))
    run.frames(2)
    assert g.story.map_index != before or len(g.story.missions()) == 1


def test_a_won_mission_has_no_vortex(run):
    g = run.game
    _launch(g)
    run.frames(10)
    g._end_adventure(True)
    assert g.anchor_fx is None and g.menu_screen == "story_hub"


def test_a_fallen_veteran_has_no_anchor(run):
    g = run.game
    _launch(g, "veteran")
    run.frames(10)
    g._end_adventure(False)
    assert g.anchor_fx is None
    assert g.story.screen == "slots"                                      # as before: the memorial


def test_leaving_to_the_main_menu_drops_it(run):
    g, _ = _lose(run)
    g._quit_to_menu()
    assert g.anchor_fx is None


def test_it_is_not_made_without_numpy(run, monkeypatch):
    monkeypatch.setattr(ax, "np", None)
    g, _ = _lose(run)
    assert g.anchor_fx is None and g.menu_screen == "story_hub" and g.story.pane == "map"
