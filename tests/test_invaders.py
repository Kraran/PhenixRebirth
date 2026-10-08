"""Paint missions as a Space Invaders clone: the grid, its march, the shots, the saucer, the invasion."""
import random

import pytest

import invaders as inv
import story_state as ss
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


def test_the_saucer_is_the_size_of_a_bird(run):
    img = inv.saucer_image()
    assert 40 <= img.get_width() <= 60 and 28 <= img.get_height() <= 44


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
    assert got == {3: 10, 2: 20, 1: 30, 0: 40}


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
