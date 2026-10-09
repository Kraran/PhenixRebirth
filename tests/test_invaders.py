"""Paint missions as a Space Invaders clone: the grid, its march, the shots, the saucer, the invasion."""
import random

import pygame
import pytest

import invaders as inv
import story_state as ss
from settings import asset_path
from enemy import EnemyBullet
from test_smoke import run  # noqa: F401  (fixture)

PAINT = ["paint_1", "paint_2", "paint_3"]


# ------------------------------------------------------------------ helpers
def _formation(run, level=1, mult=1.0):
    f = inv.InvaderFormation(level=level, speed_mult=mult)
    f.delay = 0.0
    f.saucer_timer = 999.0
    f.shot_timer = 999.0
    return f


def _act2():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["flags"].update(act2=True, dome_online=True, ch1_speed=True)
    st["act"] = 2
    return st


def _launch(g, mission_id="paint_1", st=None):
    st = st or _act2()
    for earlier in PAINT[:PAINT.index(mission_id)]:
        ss.record_result(st, earlier, 100, True, {})
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mission_id)
    spec = g.story._launch_selected()
    assert spec, mission_id
    g._begin_adventure(spec)
    return spec


def _playing(run, mission_id="paint_1", st=None):
    """The mission is launched, the ship has arrived, the invaders wait for orders (no random shot or saucer)."""
    g = run.game
    _launch(g, mission_id, st)
    g.autofire = False
    run.frames(70)
    assert g.stage_transition is None
    f = g.formation
    f.delay = 0.0
    f.saucer_timer = 999.0
    f.shot_timer = 999.0
    f.step_timer = -999.0                       # no step during the test unless asked for
    return g, f


def _shoot_at(g, x, y):
    g.player.shots.append({"x": x, "y": y, "resolved": False})


# ------------------------------------------------------------------ the grid
def test_the_grid_is_four_rows_of_eleven_enemies(run):
    f = _formation(run)
    assert len(f.enemies) == 44 == f.total
    rows = {}
    for e in f.enemies:
        rows.setdefault(e.row, []).append(e)
    assert sorted(rows) == [0, 1, 2, 3] and all(len(r) == 11 for r in rows.values())
    for r in rows.values():
        xs = sorted(e.x for e in r)
        assert [round(b - a) for a, b in zip(xs, xs[1:])] == [inv.SPACING_X] * 10
        assert len({e.y for e in r}) == 1
    ys = [rows[i][0].y for i in range(4)]
    assert [round(b - a) for a, b in zip(ys, ys[1:])] == [inv.SPACING_Y] * 3
    assert (min(e.x for e in f.enemies) + max(e.x for e in f.enemies)) / 2 == 640      # centred


def test_the_rows_are_blue_khaki_gargoyle_dark_gargoyle_from_the_bottom(run):
    f = _formation(run)
    kinds = {}
    for e in f.enemies:
        kinds.setdefault(e.row, set()).add(e.stage)
    assert [kinds[r] for r in (3, 2, 1, 0)] == [{1}, {2}, {3}, {4}]       # bottom to top


def test_every_enemy_has_about_the_size_of_a_bird(run):
    f = _formation(run)
    sizes = {}
    for e in f.enemies:
        for fr in e.frames:
            sizes.setdefault(e.stage, set()).add(fr.get_size())
    for kind, found in sizes.items():
        assert len(found) == 1, kind                                      # the two frames match
        w, h = next(iter(found))
        assert 36 <= w <= 58 and 20 <= h <= 40, (kind, w, h)
    assert sizes[1] == sizes[2]                                           # blue and khaki are the same bird
    assert sizes[3] == sizes[4]                                           # both gargoyles are the same size


def test_the_gargoyles_are_miniatures_of_the_real_ones(run):
    from enemy import BigBird
    big = BigBird(300, 300, stage=3)
    mini = inv.frames_for(3)[0]
    assert mini.get_width() < big.body_img.get_width()
    assert inv.frames_for(3)[0] is not inv.frames_for(4)[0]               # the dark ones have their own colours


def test_the_enemies_stay_the_same_kind_for_the_arcade_scoring(run):
    f = _formation(run)
    assert {e.stage for e in f.enemies} == {1, 2, 3, 4}
    assert all(e.diving is False for e in f.enemies)


# ------------------------------------------------------------------ the march
def test_the_whole_grid_steps_together_and_animates_together(run):
    f = _formation(run)
    before = [(e.x, e.y) for e in f.enemies]
    f._step()
    after = [(e.x, e.y) for e in f.enemies]
    assert {round(a[0] - b[0]) for a, b in zip(after, before)} == {inv.STEP_PX}
    assert {a[1] - b[1] for a, b in zip(after, before)} == {0}

def test_the_wings_flap_together_at_a_steady_pace_whatever_the_march(run):
    f = _formation(run)
    f.step_timer = -999.0
    seen = []
    for _ in range(int(2.0 / (1 / 60))):
        f.update(1 / 60, 640)
        f.step_timer = -999.0
        assert len({id(e.image) for e in f.enemies if e.stage == 3}) == 1      # one wing position for all
        assert all(e.image is e.frames[f.frame] for e in f.enemies)
        if not seen or seen[-1] != f.frame:
            seen.append(f.frame)
    assert len(seen) in (6, 7)                                                # 2 s at one change per 0.3 s
    fast = _formation(run)
    for e in fast.enemies[1:]:
        e.alive = False
    flips = 0
    last = fast.frame
    for _ in range(120):
        fast.update(1 / 60, 640)
        flips += fast.frame != last
        last = fast.frame
    assert flips <= 7                                                         # the last enemy does not flicker


def test_the_two_wing_positions_of_a_gargoyle_look_clearly_different(run):
    import pygame
    for kind in (3, 4):
        a, b = inv.frames_for(kind)
        diff = sum(1 for x in range(a.get_width()) for y in range(a.get_height())
                   if abs(a.get_at((x, y)).a - b.get_at((x, y)).a) > 60)
        assert diff > 400, kind


def test_a_wall_drops_the_grid_one_line_and_turns_it_back(run):
    f = _formation(run)
    for _ in range(200):
        y0 = f.enemies[0].y
        f._step()
        if f.enemies[0].y != y0:
            break
    assert f.direction == -1
    assert {round(e.y - (inv.START_Y + e.row * inv.SPACING_Y)) for e in f.enemies} == {inv.DROP_PX}
    hi = max(e.x + e.width / 2 for e in f.enemies)
    assert hi <= inv.WALL_RIGHT and hi + inv.STEP_PX > inv.WALL_RIGHT       # it was the wall that stopped it
    x0 = f.enemies[0].x
    f._step()
    assert f.enemies[0].x == x0 - inv.STEP_PX and f.direction == -1         # now it goes back
    for _ in range(200):
        y1 = f.enemies[0].y
        f._step()
        if f.enemies[0].y != y1:
            break
    assert f.direction == 1 and f.enemies[0].y == y1 + inv.DROP_PX          # the left wall: down again, turn again


def test_the_dropping_step_does_not_slide_sideways(run):
    f = _formation(run)
    while True:
        x0 = [e.x for e in f.enemies]
        y0 = f.enemies[0].y
        f._step()
        if f.enemies[0].y != y0:
            assert [e.x for e in f.enemies] == x0
            break


def test_the_walls_are_the_limits_of_the_enemies_still_alive(run):
    f = _formation(run)
    for e in f.enemies:
        if e.col >= 8:
            e.alive = False                                                # the three right columns are gone
    moved = 0
    while True:
        y0 = f.enemies[0].y
        f._step()
        if f.enemies[0].y != y0:
            break
        moved += 1
    g = _formation(run)
    plain = 0
    while True:
        y0 = g.enemies[0].y
        g._step()
        if g.enemies[0].y != y0:
            break
        plain += 1
    assert moved > plain + 8


def test_the_march_speeds_up_as_the_grid_empties(run):
    f = _formation(run)
    gaps = [f.interval()]
    for k in range(43):
        f.enemies[k].alive = False
        gaps.append(f.interval())
    assert all(b < a for a, b in zip(gaps, gaps[1:]))
    assert gaps[0] == pytest.approx(inv.level_interval(1))
    assert gaps[-1] < gaps[0] / 5


def test_nothing_moves_before_the_start_delay(run):
    f = inv.InvaderFormation(level=1)
    f.shot_timer = 0.0
    x0 = f.enemies[0].x
    for _ in range(60):
        f.update(1 / 60, 640)
    assert f.enemies[0].x == x0 and not f.bullets and f.steps == 0
    for _ in range(120):
        f.update(1 / 60, 640)
    assert f.steps > 0


def test_the_march_follows_the_clock(run):
    f = _formation(run)
    for _ in range(300):
        f.update(1 / 60, 640)
    assert 13 <= f.steps <= 16                                           # 5 s at one step per 0.34 s


def test_the_difficulty_speed_makes_the_march_faster(run):
    assert _formation(run, mult=1.3).interval() < _formation(run, mult=1.0).interval()


# ------------------------------------------------------------------ the levels
def test_a_higher_level_marches_faster_and_starts_lower(run):
    ivs = [inv.level_interval(n) for n in range(1, 9)]
    assert all(b <= a for a, b in zip(ivs, ivs[1:])) and ivs[1] < ivs[0] and ivs[-1] >= inv.MIN_INTERVAL
    ys = [inv.level_start_y(n) for n in range(1, 8)]
    # the 2nd mission starts one line (a row of the grid) lower, the 3rd two lines lower; the next pass starts again
    assert ys == [130, 130 + 46, 130 + 92, 130, 130 + 46, 130 + 92, 130]
    assert _formation(run, level=4).enemies[0].y == inv.level_start_y(4)
    assert inv.level_start_y(0) == inv.START_Y                            # a damaged level counts as 1


def test_a_higher_level_shoots_more(run):
    shots = [inv.level_max_bullets(n) for n in range(1, 12)]
    assert shots[0] == 2 and all(b >= a for a, b in zip(shots, shots[1:])) and shots[-1] == 5
    gaps = [inv.level_shot_gap(n)[0] for n in range(1, 12)]
    assert all(b <= a for a, b in zip(gaps, gaps[1:])) and gaps[-1] >= inv.BULLET_PAUSE_MIN - 1e-9


def test_the_levels_stay_playable(run):
    f = _formation(run, level=60)
    assert f.enemies[0].y < inv.INVASION_Y - 3 * inv.SPACING_Y - 100 and f.enemies[0].y <= 130 + 2 * 46


# ------------------------------------------------------------------ the shots of the enemies
def test_only_the_front_of_each_column_shoots(run):
    f = _formation(run)
    for e in f.enemies:
        if e.col == 0 and e.row == 3:
            e.alive = False
    front = f._front_row()
    assert len(front) == 11 and front[0].row == 2 and all(front[c].row == 3 for c in range(1, 11))
    random.seed(4)
    for _ in range(60):
        f.bullets = []
        f._shoot(640)
        b = f.bullets[0]
        owner = [e for e in f.enemies if id(e) == b.owner_id][0]
        assert owner is front[owner.col] and b.y > owner.y


def test_some_shots_aim_at_the_ship(run):
    f = _formation(run)
    nearest = min(f._front_row().values(), key=lambda e: abs(e.x - 100)).col
    cols = []
    random.seed(9)
    for _ in range(300):
        f.bullets = []
        f._shoot(100)
        owner = [e for e in f.enemies if id(e) == f.bullets[0].owner_id][0]
        cols.append(owner.col)
    share = cols.count(nearest) / len(cols)
    assert 0.3 < share < 0.6                                              # more often than one in eleven


def test_the_screen_never_holds_more_shots_than_the_level_allows(run):
    for level in (1, 5, 9):
        f = _formation(run, level=level)
        random.seed(level)
        for _ in range(3000):
            f.shot_timer = 0.0
            f.update(1 / 60, 640)
            f.step_timer = -999.0
            for b in f.bullets:
                b.y = 0                                                    # none ever falls away
            assert len([b for b in f.bullets if b.alive]) <= inv.level_max_bullets(level)
        assert len(f.bullets) == inv.level_max_bullets(level)


# ------------------------------------------------------------------ the miniature saucer
def test_the_saucer_pays_500_to_1000_by_how_centred_the_shot_is():
    assert inv.saucer_points(300, 300) == 1000
    half = inv.SAUCER_HIT_W / 2
    assert inv.saucer_points(300 + half, 300) == 500 and inv.saucer_points(300 - half, 300) == 500
    assert inv.saucer_points(300 + half / 2, 300) == 750 == inv.saucer_points(300 - half / 2, 300)
    assert inv.saucer_points(300 + 3 * half, 300) == 500                   # never under 500
    mids = [inv.saucer_points(300 + d, 300) for d in range(0, 23)]
    assert mids == sorted(mids, reverse=True) and mids[0] == 1000 and mids[-1] >= 500


def test_the_saucer_crosses_the_top_in_a_straight_line_and_leaves(run):
    for d in (1, -1):
        f = _formation(run)
        f.mothership = inv.Mothership(d)
        m = f.mothership
        assert m.y == inv.SAUCER_Y and m.y < f.enemies[0].y - 30            # above the grid
        assert m.x < 0 if d > 0 else m.x > 1280
        xs = []
        for _ in range(60 * 12):
            f.update(1 / 60, 640)
            f.step_timer = -999.0
            if f.mothership is None:
                break
            xs.append(f.mothership.x)
        assert f.mothership is None
        steps = [b - a for a, b in zip(xs, xs[1:])]
        assert {round(s, 2) for s in steps} == {round(d * inv.SAUCER_SPEED / 60, 2)}


def test_the_saucer_is_a_small_miniature_of_the_given_picture(run):
    src = pygame.image.load(asset_path("sprites", "saucer_mini.png"))
    assert abs(inv.SAUCER_W / inv.SAUCER_H - src.get_width() / src.get_height()) < 0.12          # same proportions
    assert 56 <= inv.SAUCER_W <= 80 and 24 <= inv.SAUCER_H <= 36                                 # about a bird's size
    img = inv.saucer_image()
    assert img.get_size() == (inv.SAUCER_W + 2 * inv.SAUCER_GLOW, inv.SAUCER_H + 2 * inv.SAUCER_GLOW)
    m = inv.Mothership(1)
    assert (m.width, m.height) == (inv.SAUCER_W, inv.SAUCER_H)
    box = m.get_hitbox
    m.x = 300
    assert box().height == inv.SAUCER_H and box().width == inv.SAUCER_HIT_W
    assert inv.SAUCER_HIT_W <= inv.SAUCER_W


def test_the_saucer_comes_now_and_then_but_not_for_the_last_enemy(run):
    f = _formation(run)
    f.saucer_timer = 0.0
    f.step_timer = -999.0
    f.update(1 / 60, 640)
    assert f.mothership is not None and f.saucer_timer >= inv.SAUCER_GAP[0] - 1
    g = _formation(run)
    for e in g.enemies[1:]:
        e.alive = False
    g.saucer_timer = 0.0
    g.update(1 / 60, 640)
    assert g.mothership is None


def test_a_shot_through_the_middle_of_the_saucer_gives_1000(run):
    g, f = _playing(run)
    f.mothership = inv.Mothership(1)
    f.mothership.direction = 0                  # holding still above the shot
    f.mothership.x = 500
    f.mothership.y = 300
    g.score = 0
    _shoot_at(g, 500, 330)
    run.frames(3)
    assert g.score == 1000 and (f.mothership is None or f.mothership.dying)


def test_a_shot_near_the_edge_of_the_saucer_gives_less(run):
    g, f = _playing(run)
    f.mothership = inv.Mothership(1)
    f.mothership.direction = 0                  # holding still above the shot
    f.mothership.x = 500
    f.mothership.y = 300
    g.score = 0
    _shoot_at(g, 500 + 18, 330)
    run.frames(3)
    assert 500 < g.score < 700


def test_the_points_of_the_saucer_are_shown_where_it_fell(run):
    g, f = _playing(run)
    f.mothership = inv.Mothership(1)
    f.mothership.direction = 0                  # holding still above the shot
    f.mothership.x = 500
    f.mothership.y = 300
    _shoot_at(g, 500, 330)
    run.frames(2)
    assert f.popups and f.popups[0][2] == "1000"
    run.frames(90)
    assert not f.popups


def test_the_saucer_does_not_have_to_be_killed_to_win(run):
    g, f = _playing(run)
    f.mothership = inv.Mothership(1)
    for e in f.enemies:
        e.alive = False
    assert f.all_dead()


# ------------------------------------------------------------------ in the game
def test_a_shot_destroys_an_enemy_and_pays_by_row(run):
    g, f = _playing(run)
    got = {}
    for row in (3, 2, 1, 0):
        target = next(e for e in f.enemies if e.row == row and e.col == 5)
        g.score = 0
        _shoot_at(g, target.x, target.y + 12)
        for _ in range(12):
            run.frames(1)
            if target.dying or not target.alive:
                break
        got[row] = g.score
        assert target.dying or not target.alive, row
    assert got == {3: 20, 2: 30, 1: 40, 0: 50}          # 10, 20, 30, 40 + the +10 of level 1


def test_the_kills_of_the_invasion_count_for_the_bestiary(run):
    g, f = _playing(run)
    target = next(e for e in f.enemies if e.row == 0 and e.col == 5)
    _shoot_at(g, target.x, target.y + 12)
    run.frames(2)
    assert g.adventure["kills"].get("garg4") == 1


def test_the_remaining_enemies_are_counted_on_screen(run):
    from i18n import t
    import text_cache as tc_mod
    g, f = _playing(run)
    for e in f.enemies[:5]:
        e.alive = False
    seen = []
    orig = tc_mod.TextCache.get

    def spy(self, font, text, *a, **k):
        seen.append(str(text))
        return orig(self, font, text, *a, **k)

    tc_mod.TextCache.get = spy
    try:
        run.frames(2)
    finally:
        tc_mod.TextCache.get = orig
    assert t("story_swarm_left").format(n=39) in seen


def test_the_enemy_shots_hurt_the_ship(run):
    g, f = _playing(run)
    lives = g.player.lives
    g.player.invulnerable = 0.0
    f.bullets.append(EnemyBullet(g.player.x, g.player.y - 20, stage=1))
    run.frames(3)
    assert g.player.lives < lives or g.player.dying


def test_an_enemy_reaching_the_line_of_the_ship_ends_the_run(run):
    g, f = _playing(run)
    for e in f.enemies:
        e.y += 330
    f.step_timer = 999.0
    run.frames(2)
    assert f.invaded
    assert g.player.lives == 0 and (g.player.dying or not g.player.alive)


def test_the_line_is_above_the_ship_and_far_below_the_start(run):
    f = _formation(run)
    assert inv.INVASION_Y < 625 - 40
    assert max(e.y for e in f.enemies) + 20 < inv.INVASION_Y - 100


def test_an_invader_far_from_the_line_does_not_end_the_run(run):
    g, f = _playing(run)
    f.step_timer = 999.0
    run.frames(20)
    assert not f.invaded and g.player.lives > 0 and g.player.alive


def test_destroying_the_whole_grid_wins_the_mission_and_saves_the_progress(run):
    g, f = _playing(run, "paint_1")
    g.score = 700
    for _ in range(900):
        if g.adventure is None:
            break
        for e in g.formation.enemies:
            e.alive = False
        run.frames(1)
    assert g.adventure is None
    st = g.story.state
    assert ss.paint_state(st)["step"] == 1
    assert st["credits"] == 700


def test_losing_the_invasion_fails_the_mission(run):
    g, f = _playing(run)
    g.story.state["credits"] = 400
    g._end_adventure(False)
    assert ss.paint_state(g.story.state)["step"] == 0 and g.story.state["credits"] == 380


def test_the_third_mission_of_a_pass_opens_the_paint_shop(run):
    g, f = _playing(run, "paint_3")
    for _ in range(900):
        if g.adventure is None:
            break
        for e in g.formation.enemies:
            e.alive = False
        run.frames(1)
    assert g.adventure is None and ss.paint_state(g.story.state)["token"]


def test_the_title_shows_the_level_of_each_mission(run):
    from i18n import t
    import text_cache as tc_mod
    seen = []
    orig = tc_mod.TextCache.get

    def spy(self, font, text, *a, **k):
        seen.append(str(text))
        return orig(self, font, text, *a, **k)

    tc_mod.TextCache.get = spy
    try:
        st = _act2()
        ss.record_result(st, "paint_1", 10, True, {})
        ss.record_result(st, "paint_2", 10, True, {})
        ss.record_result(st, "paint_3", 10, True, {})
        g, f = _playing(run, "paint_2", st)
    finally:
        tc_mod.TextCache.get = orig
    assert any(t("story_level").format(n=5) in x for x in seen)


def test_the_grid_is_drawn_whole(run):
    import pygame
    g, f = _playing(run)
    surf = pygame.Surface((1280, 720))
    f.draw(surf)
    for e in f.enemies:
        box = pygame.Rect(int(e.x - e.width / 2), int(e.y - e.height / 2), e.width, e.height)
        assert any(surf.get_at(p)[:3] != (0, 0, 0) for p in ((x, y) for x in range(box.left, box.right, 3)
                                                              for y in range(box.top, box.bottom, 3))), (e.row, e.col)
    f.mothership = inv.Mothership(1)
    f.mothership.x = 100
    surf.fill((0, 0, 0))
    f.draw(surf)
    assert surf.get_at((100, inv.SAUCER_Y))[:3] != (0, 0, 0)


# ------------------------------------------------------------------ the saucer must be seen
PEAK = inv.SAUCER_PULSE_FRAMES // 2


def _red_parts():
    """Where the picture is red (frame coordinates), as the game found them."""
    _img, redness = inv._saucer_source()
    return [(x + inv.SAUCER_GLOW, y + inv.SAUCER_GLOW) for (x, y), red in redness.items() if red > 0.5]


def _mean_red(frame):
    img = inv.saucer_image(frame)
    pts = _red_parts()
    return sum(img.get_at(p)[0] for p in pts) / len(pts)


def test_the_miniature_has_the_shape_of_the_given_picture(run):
    src = pygame.image.load(asset_path("sprites", "saucer_mini.png"))
    flat = pygame.transform.smoothscale(src, (inv.SAUCER_W, inv.SAUCER_H))
    want = pygame.mask.from_surface(flat, 128).count()
    img = inv.saucer_image(PEAK)
    got = pygame.mask.from_surface(img, 200).count()                    # the body, without the soft halo
    assert abs(got - want) <= 0.1 * want and want > 1000
    # the dome window, the dishes and the red band are where they are in the picture: the silhouettes agree
    a = pygame.mask.from_surface(flat, 128)
    b = pygame.mask.from_surface(img.subsurface((inv.SAUCER_GLOW, inv.SAUCER_GLOW, inv.SAUCER_W, inv.SAUCER_H)), 128)
    assert a.overlap_area(b, (0, 0)) > 0.9 * want


def test_there_are_red_parts_and_they_pulse(run):
    red = _red_parts()
    assert len(red) >= 40                                               # the band, the two lights, the tip
    dim, peak = _mean_red(0), _mean_red(PEAK)
    assert peak - dim > 60 and peak > 200 and dim < 160
    levels = [_mean_red(i) for i in range(inv.SAUCER_PULSE_FRAMES)]
    assert levels.index(min(levels)) == 0 and levels.index(max(levels)) == PEAK
    rises = [b - a for a, b in zip(levels[:PEAK], levels[1:PEAK + 1])]
    assert all(r > 0 for r in rises) and max(rises) < 0.4 * (peak - dim)    # a smooth swell, not a flash
    falls = [a - b for a, b in zip(levels[PEAK:], levels[PEAK + 1:] + levels[:1])]
    assert all(f > 0 for f in falls)                                    # and it comes back down to the start


def test_the_hull_does_not_pulse_only_the_red_parts(run):
    red = _red_parts()
    a, b = inv.saucer_image(0), inv.saucer_image(PEAK)
    g = inv.SAUCER_GLOW
    redness = inv._saucer_source()[1]
    grey = [(x, y) for x in range(g, g + inv.SAUCER_W) for y in range(g, g + inv.SAUCER_H)
            if a.get_at((x, y))[3] >= 251 and (x - g, y - g) not in redness
            and all(abs(x - rx) > 5 or abs(y - ry) > 5 for rx, ry in red)]     # away from the red light
    assert len(grey) > 300
    # (the body is a hair see-through: the halo behind it shows by a few levels at most)
    assert all(max(abs(u - v) for u, v in zip(a.get_at(p)[:3], b.get_at(p)[:3])) <= 8 for p in grey)
    near = [p for p in red if a.get_at(p)[:3] != b.get_at(p)[:3]]
    assert len(near) > 0.8 * len(red)                                    # while the red parts all change


def test_the_grey_hull_is_lightened_to_show_against_the_sky(run):
    g = inv.SAUCER_GLOW
    img = inv.saucer_image(0)
    redness = inv._saucer_source()[1]
    vals = [max(img.get_at((x + g, y + g))[:3]) for x in range(inv.SAUCER_W) for y in range(inv.SAUCER_H)
            if img.get_at((x + g, y + g))[3] > 200 and (x, y) not in redness]
    assert sum(vals) / len(vals) > 75


def _halo(frame):
    """How much red light spills outside the body of the saucer (sum of the alpha around it)."""
    img = inv.saucer_image(frame)
    g = inv.SAUCER_GLOW
    body = pygame.mask.from_surface(inv._saucer_source()[0], 1)           # every pixel the picture itself covers
    total = 0
    for x in range(img.get_width()):
        for y in range(img.get_height()):
            inside = 0 <= x - g < inv.SAUCER_W and 0 <= y - g < inv.SAUCER_H and body.get_at((x - g, y - g))
            if not inside:
                total += img.get_at((x, y))[3]
    return total


def test_a_red_halo_swells_with_the_red_parts(run):
    dim, peak = _halo(0), _halo(PEAK)
    assert peak > 20 * max(1, dim) and peak > 400
    img = inv.saucer_image(PEAK)
    g = inv.SAUCER_GLOW
    spill = [img.get_at((x, y)) for x in range(img.get_width()) for y in range(img.get_height())
             if img.get_at((x, y))[3] > 40 and not (0 <= x - g < inv.SAUCER_W and 0 <= y - g < inv.SAUCER_H
                                                    and inv._saucer_source()[0].get_at((x - g, y - g))[3] > 0)]
    assert spill and all(p[0] > 3 * p[1] and p[0] > 3 * p[2] for p in spill)                 # the halo is red, not white or grey


def test_the_pulse_follows_the_age_of_the_saucer(run):
    n, T = inv.SAUCER_PULSE_FRAMES, inv.SAUCER_PULSE
    assert inv.saucer_frame_at(0) == 0 and inv.saucer_frame_at(T / 2) == n // 2
    assert inv.saucer_frame_at(T) == 0 and inv.saucer_frame_at(7 * T + T / 2) == n // 2
    assert [inv.saucer_frame_at(T * i / n) for i in range(n)] == list(range(n))
    m = inv.Mothership(1)
    m.x = 640
    shots = []
    for age in (0.0, T / 2, T):
        m.age = age
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        m.draw(surf)
        shots.append(pygame.image.tobytes(surf, "RGBA"))
    assert shots[0] != shots[1] and shots[0] == shots[2]


def test_a_saucer_pulses_as_it_flies(run):
    f = _formation(run)
    f.mothership = inv.Mothership(1)
    m = f.mothership
    m.x = 100
    seen = set()
    for _ in range(int(inv.SAUCER_PULSE * 60)):
        m.update(1 / 60)
        seen.add(inv.saucer_frame_at(m.age))
    assert len(seen) >= inv.SAUCER_PULSE_FRAMES - 2


def test_the_saucer_is_drawn_visibly_on_the_real_screen(run):
    g, f = _playing(run)
    f.mothership = inv.Mothership(1)
    f.mothership.x = 900
    f.mothership.direction = 0
    f.mothership.age = inv.SAUCER_PULSE / 2                              # the red parts at their brightest
    g.shake_amount = 0
    g._draw_canvas()
    box = pygame.Rect(900 - 40, inv.SAUCER_Y - 22, 80, 44)
    px = [g.game_surface.get_at((x, y))[:3] for x in range(box.left, box.right) for y in range(box.top, box.bottom)]
    assert sum(1 for p in px if max(p) >= 90) > 400                       # the hull stands out of the night
    assert sum(1 for p in px if p[0] >= 200 and p[1] < 170) >= 40         # and so do the red parts


def test_a_dying_saucer_never_spoils_the_picture_of_the_next_ones(run):
    """The fade-out used to be set on the one shared picture: after the first kill every saucer stayed
    nearly see-through (a sound with no saucer to be seen)."""
    reference = [pygame.image.tobytes(inv.saucer_image(i), "RGBA") for i in range(inv.SAUCER_PULSE_FRAMES)]
    for age in (0.0, 0.04, 0.08, 0.12, 0.2, 0.29):
        m = inv.Mothership(1)
        m.x = 300
        m.age = 0.37
        m.kill()
        m.death_timer = age
        m.draw(pygame.Surface((1280, 720), pygame.SRCALPHA))
        assert all(inv.saucer_image(i).get_alpha() in (None, 255) for i in range(inv.SAUCER_PULSE_FRAMES))
        assert [pygame.image.tobytes(inv.saucer_image(i), "RGBA") for i in range(inv.SAUCER_PULSE_FRAMES)] == reference
    fresh = pygame.Surface((1280, 720), pygame.SRCALPHA)
    n = inv.Mothership(-1)
    n.x = 640
    n.draw(fresh)
    ref = pygame.Surface((1280, 720), pygame.SRCALPHA)
    ref.blit(inv.saucer_image(0), (int(640 - inv.SAUCER_W / 2) - inv.SAUCER_GLOW,
                                   int(inv.SAUCER_Y - inv.SAUCER_H / 2) - inv.SAUCER_GLOW))
    assert pygame.image.tobytes(fresh, "RGBA") == pygame.image.tobytes(ref, "RGBA")


@pytest.mark.parametrize("d, x, hit", [(1, -26.0, False), (1, -1.0, False), (1, 0.0, True), (1, 640.0, True),
                                       (-1, 1280.0, True), (-1, 1281.0, False), (-1, 1306.0, False)])
def test_the_saucer_cannot_be_hit_before_it_is_on_the_screen(run, d, x, hit):
    m = inv.Mothership(d)
    m.x = x
    assert (m.get_hitbox().width > 0) is hit and m.on_screen() is hit


def test_a_shot_at_the_edge_does_not_kill_a_saucer_still_outside(run):
    g, f = _playing(run)
    f.mothership = inv.Mothership(1)
    f.mothership.direction = 0
    f.mothership.x = -10.0                                           # its hit box would reach x = 12
    g.score = 0
    _shoot_at(g, 8, f.mothership.y + 30)
    run.frames(30)
    assert f.mothership is not None and f.mothership.alive and not f.mothership.dying and g.score == 0
