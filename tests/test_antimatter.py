"""The antimatter missile (src/antimatter.py): the reward of Silent Sentinels IV for every mission of the Adventure. One per
mission, fired straight ahead with a key / a pad button, it destroys what is within a quarter of the screen of its impact
(two bricks round the impact on the armour of the boss saucer) and is lost when it touches nothing."""
import math

import pygame
import pytest

import antimatter as am
import asteroids
import bindings
import i18n
import spacewar as sw
import story_state as ss
from boss import BossSaucer
from enemy import Enemy
from settings import BASE_HEIGHT, BASE_WIDTH
from test_asteroids import _rock
from test_smoke import run  # noqa: F401  (fixture)
from test_spacewar import _alone, _bird, _orbit, _pin

DT = 1 / 60


def _settle(run):
    """The ship flies in at the start of a mission: wait for the end of it."""
    for _ in range(600):
        if run.game.stage_transition is None:
            break
        run.frames(1)
    assert run.game.stage_transition is None


def _launch(run, mission="ch1_sortie", antimatter=True, act=1):
    """A mission of the map, flown from a save that has (or has not) won Silent Sentinels IV."""
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    if act >= 2:
        ss.jump_to_act2(st)
    st["act"] = max(act, st["act"])
    if antimatter:
        st["flags"][ss.ANTIMATTER_FLAG] = True
    for m in ss.MISSIONS:
        if m["id"].startswith("sentinelle_"):
            st["flags"][m["id"]] = True
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mission)
    spec = g.story._launch_selected()
    assert spec
    g._begin_adventure(spec)
    g.input_grace = 0.0
    g.player.infinite_lives = False
    run.frames(2)
    _settle(run)
    return g, spec


def _still(g):
    """The formation does not move (the test places its birds)."""
    g.formation.update = lambda *a, **k: None
    g.formation.enemies = []
    g.formation.swarm = None


def _bird_at(g, x, y):
    e = Enemy(x, y, len(g.formation.enemies), 1)
    e.state = "formation"
    g.formation.enemies.append(e)
    return e


def _fly(g, frames=120):
    g.dt = DT
    for _ in range(frames):
        am.tick(g)
        if not g.antimatter.missiles:
            return


# ------------------------------------------------------------------ the keys and the buttons
def test_the_missile_has_a_key_and_a_button_of_its_own():
    assert "missile" in bindings.KEY_ACTIONS and "missile" in bindings.PAD_ACTIONS
    assert bindings.DEFAULT_KEYS[bindings.KB2]["missile"] == [pygame.K_m, None]
    assert bindings.DEFAULT_KEYS[bindings.KB1]["missile"] == [pygame.K_e, None]
    assert bindings.DEFAULT_PAD["missile"] == [4]


def test_no_default_key_or_button_is_used_twice():
    keys = [k for p in bindings.KEY_PROFILES for a in bindings.KEY_ACTIONS for k in bindings.DEFAULT_KEYS[p][a] if k]
    assert len(keys) == len(set(keys))
    buttons = [b for a in bindings.PAD_ACTIONS for b in bindings.DEFAULT_PAD[a]]
    assert len(buttons) == len(set(buttons))


def test_the_missile_key_and_button_can_be_changed_and_are_saved():
    b = bindings.Bindings()
    assert b.set_key(bindings.KB2, "missile", 0, pygame.K_n)
    assert b.set_pad_buttons(0, "missile", [8])
    again = bindings.Bindings.from_dict(b.to_dict())
    assert again.keys(bindings.KB2, "missile") == (pygame.K_n,) and again.pad_buttons(0, "missile") == (8,)
    assert bindings.Bindings().to_dict() == {}                       # nothing changed: nothing written
    assert again.keys(bindings.KB1, "missile") == (pygame.K_e,)


def test_the_help_values_name_the_missile_keys():
    v = bindings.help_values(i18n.t)
    assert v["kb_missile"] == "M" and v["pad_missile"] == "LB"


def test_the_texts_exist_in_every_language():
    for key in ("act_missile", "kb_help_missile", "story_stat_missile", "story_missile_ready", "antimatter_hud"):
        assert all(i18n.T[key][c] for c in i18n.LANG_CODES)
    assert "{key}" in i18n.T["antimatter_hud"]["fr"] and "{key}" in i18n.T["story_missile_unlocked"]["en"]


def test_the_keys_screens_have_a_row_for_the_missile(run):
    import keybind_pad
    import keybind_screen
    assert "missile" in keybind_screen.ACTION_ROWS and "missile" in keybind_pad.rows()
    assert keybind_pad.CARDS["missile"].colliderect(keybind_pad.CARDS["fire"]) is False
    assert keybind_pad.CARDS["missile"].colliderect(keybind_pad.CARDS["phenix"]) is False
    g = run.game
    g.menu_screen = "keybind"
    g.keybind = keybind_screen.State()
    for tab in range(3):
        g.keybind.tab = tab
        g.keybind.row = 0
        run.frames(2)
        g.keybind.row = 6 if tab < 2 else 2
        run.frames(2)
    last = keybind_screen.LEFT.y + 40 + len(keybind_screen.ACTION_ROWS) * keybind_screen.ROW_STEP + 22 + keybind_screen.ROW_STEP
    assert last + keybind_screen.ROW_H <= keybind_screen.LEFT.bottom                       # the rows still fit in the panel


# ------------------------------------------------------------------ the unlock
def test_winning_silent_sentinels_iv_unlocks_the_missile():
    st = ss.default_state()
    st["act"] = 3
    for mid in ("sentinelle_1", "sentinelle_2", "sentinelle_3"):
        ss.record_result(st, mid, 100, True)
    assert not ss.has_antimatter(st)
    ss.record_result(st, "sentinelle_4", 100, False)
    assert not ss.has_antimatter(st)                                  # lost: nothing
    ss.record_result(st, "sentinelle_4", 100, True)
    assert ss.has_antimatter(st) and ss.flag(st, ss.ANTIMATTER_FLAG)
    ss.record_result(st, "sentinelle_4", 100, True)                   # (flown again: still there)
    assert ss.has_antimatter(st)


def test_only_the_adventure_missions_with_the_flag_carry_the_missile(run):
    g, spec = _launch(run, "ch1_sortie")
    assert spec["antimatter"] is True and g.antimatter is not None and g.antimatter.ready
    g._end_adventure(False)
    g, spec = _launch(run, "ch1_sortie", antimatter=False)
    assert "antimatter" not in spec and g.antimatter is None
    g._end_adventure(False)
    g, spec = _launch(run, "test_spacewar")                           # a test is not a mission of the story
    assert "antimatter" not in spec and g.antimatter is None
    g._end_adventure(False)


def test_a_new_mission_has_its_missile_again(run):
    g, spec = _launch(run, "ch1_sortie")
    assert am.fire(g, g.player) and not g.antimatter.ready
    g._end_adventure(False)
    g, spec = _launch(run, "ch1_sortie")
    assert g.antimatter.ready and not g.antimatter.missiles


def test_winning_the_fourth_says_so(run):
    st = ss.default_state()
    st["act"] = 3
    g = run.game
    g.story.state = st
    for mid in ("sentinelle_1", "sentinelle_2", "sentinelle_3"):
        g.story.apply_result(mid, 100, True)
    g.story.apply_result("sentinelle_4", 100, True)
    assert g.story.toast == i18n.T["story_missile_unlocked"][i18n.get_lang()].format(key="M")
    assert g.story.toast_kind == "reward"


# ------------------------------------------------------------------ the shot
def test_the_key_fires_the_missile_once_up_the_screen(run):
    g, spec = _launch(run, "ch1_sortie")
    _still(g)
    p = g.player
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m, unicode="m", mod=0))
    g.dt = DT
    g.handle_events()
    arm = g.antimatter
    assert not arm.ready and len(arm.missiles) == 1
    m = arm.missiles[0]
    assert (m.ux, m.uy) == (0.0, -1.0) and m.x == p.x and m.y < p.y
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m, unicode="m", mod=0))
    g.handle_events()
    assert len(arm.missiles) == 1                                     # one per mission
    g._end_adventure(False)


def test_the_pad_button_fires_it_too(run):
    g, spec = _launch(run, "ch1_sortie")
    _still(g)
    pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=4, joy=0, instance_id=0))
    g.dt = DT
    g.handle_events()
    assert not g.antimatter.ready and len(g.antimatter.missiles) == 1
    g._end_adventure(False)


def test_it_does_not_fire_when_paused_dying_or_without_the_unlock(run):
    g, spec = _launch(run, "ch1_sortie")
    g.paused = True
    assert not am.fire(g, g.player) and g.antimatter.ready
    g.paused = False
    g.player.dying = True
    assert not am.fire(g, g.player) and g.antimatter.ready
    g.player.dying = False
    g.stage_transition = "fly_up"
    assert not am.fire(g, g.player) and g.antimatter.ready
    g.stage_transition = None
    g._end_adventure(False)
    g, spec = _launch(run, "ch1_sortie", antimatter=False)
    assert not am.fire(g, g.player)
    g._end_adventure(False)


def test_the_arcade_game_has_no_missile(run):
    g, spec = _launch(run, "ch1_sortie")
    g._end_adventure(False)
    assert g.adventure is None
    assert not am.fire(g, g.player)                                    # (the stock of the last mission is not for the arcade)
    am.draw_hud(g)
    am.draw(g, g.game_surface)


def test_it_flies_straight_and_is_lost_without_an_impact(run):
    g, spec = _launch(run, "ch1_sortie")
    _still(g)
    assert am.fire(g, g.player)
    m = g.antimatter.missiles[0]
    x0 = m.x
    _fly(g)
    assert not g.antimatter.missiles and not g.antimatter.ready        # gone out at the top: lost
    assert m.x == x0 and m.y < -20
    assert not [e for e in g.explosions if isinstance(e, am.Blast)]
    assert not am.fire(g, g.player)
    g._end_adventure(False)


def test_it_is_lost_with_the_wave(run):
    g, spec = _launch(run, "ch1_sortie")
    assert am.fire(g, g.player)
    g.stage_transition = "fly_up"
    am.tick(g)
    assert not g.antimatter.missiles and not g.antimatter.ready
    g.stage_transition = None
    g._end_adventure(False)


def test_it_blows_on_the_first_bird_and_destroys_what_is_within_the_radius(run):
    g, spec = _launch(run, "ch1_sortie")
    _still(g)
    p = g.player
    first = _bird_at(g, p.x, 300)
    near = _bird_at(g, p.x + 120, 260)                                  # (about 135 from the impact)
    far = _bird_at(g, p.x + 300, 300)                                   # (300 from it)
    g.score = 0
    assert am.fire(g, p)
    _fly(g)
    assert not first.alive or first.dying
    assert not near.alive or near.dying
    assert far.alive and not far.dying
    blasts = [e for e in g.explosions if isinstance(e, am.Blast)]
    assert len(blasts) == 1 and blasts[0].reach == am.BLAST_RADIUS == 180.0
    assert g.score == 2 * g._enemy_kill_points(first) > 0               # the usual points
    assert g.shake_amount >= 26.0
    g._end_adventure(False)


def test_the_radius_is_a_quarter_of_the_screen_height():
    assert am.BLAST_RADIUS == BASE_HEIGHT / 4
    assert am.SAUCER_BLAST == 52.0 and am.SIZE > 1.0


@pytest.mark.parametrize("dx,dead", [(100, True), (178, True), (230, False)])
def test_the_edge_of_the_blast(run, dx, dead):
    g, spec = _launch(run, "ch1_sortie")
    _still(g)
    e = _bird_at(g, 400 + dx, 300)
    am.blast(g, 400.0, 300.0)
    assert (not e.alive or e.dying) is dead
    g._end_adventure(False)


def test_a_missile_that_passes_between_the_birds_hits_the_next_one(run):
    g, spec = _launch(run, "ch1_sortie")
    _still(g)
    p = g.player
    aside = _bird_at(g, p.x + 120, 500)
    top = _bird_at(g, p.x, 100)
    assert am.fire(g, p)
    g.dt = DT
    for _ in range(8):
        am.tick(g)
    assert g.antimatter.missiles and top.alive                         # (it did not blow on the way)
    _fly(g)
    assert not top.alive or top.dying
    assert aside.alive and not aside.dying                             # (400 px from the impact: out of reach)
    g._end_adventure(False)


def test_it_touches_the_mothership_of_space_invaders(run):
    g, spec = _launch(run, "paint_1", act=2)
    form = g.formation
    import invaders
    mother = form.mothership = invaders.Mothership(1)
    mother.x = 600.0                                                  # (it is hit only on the screen)
    form.update = lambda *a, **k: None
    g.score = 0
    am.blast(g, mother.x, mother.y)
    assert g.score >= 500
    g._end_adventure(False)


# ------------------------------------------------------------------ the boss saucer
def _saucer(run):
    g, spec = _launch(run, "ch1_sortie")
    _still(g)
    boss = BossSaucer()
    boss.use_art = False
    g.boss_saucer = boss
    return g, boss


def _dist(rect, x, y):
    nx, ny = max(rect.left, min(x, rect.right)), max(rect.top, min(y, rect.bottom))
    return math.hypot(nx - x, ny - y)


def test_on_the_saucer_the_blast_is_two_bricks_wide(run):
    g, boss = _saucer(run)
    cell = [c for c in boss.cells if c.alive][len(boss.cells) // 2]
    x, y = cell.x, cell.y
    inside = {id(c) for c in boss.cells if c.alive and _dist(c.get_hitbox(), x, y) <= 52}
    outside = [c for c in boss.cells if c.alive and _dist(c.get_hitbox(), x, y) > 52]
    assert len(inside) > 4 and outside
    before = boss.living_cells()
    am.blast(g, x, y)
    assert not cell.alive
    for c in boss.cells:
        if id(c) in inside:
            assert not c.alive
    assert all(c.alive for c in outside)
    assert boss.living_cells() == before - len(inside) or boss.living_cells() < before
    g.boss_saucer = None
    g._end_adventure(False)


def test_the_blast_on_the_saucer_reaches_the_core_only_when_it_is_close(run):
    g, boss = _saucer(run)
    core = boss.boss
    am.blast(g, core.x, core.y - 400)
    assert core.alive and not core.dying
    am.blast(g, core.x, core.y)
    assert not core.alive or core.dying
    g.boss_saucer = None
    g._end_adventure(False)


def test_a_bird_far_from_the_saucer_dies_but_the_bricks_stay(run):
    g, boss = _saucer(run)
    e = _bird_at(g, 100, 600)
    x, y = 100.0, 600.0
    alive = boss.living_cells()
    am.blast(g, x, y)
    assert not e.alive or e.dying
    assert boss.living_cells() == alive                                # (nothing of the saucer within two bricks)
    g.boss_saucer = None
    g._end_adventure(False)


def test_the_missile_stops_on_the_armour(run):
    g, boss = _saucer(run)
    brick = [c for c in boss.cells if c.alive][0]
    m = am.Missile(brick.x, brick.y + 3, 0.0, -1.0)
    assert am._touch(g, m) == "hit"
    far = am.Missile(5.0, 5.0, 0.0, -1.0)
    assert am._touch(g, far) is None
    g.boss_saucer = None
    g._end_adventure(False)


# ------------------------------------------------------------------ SpaceWar
def _sentinelle(run, mid="sentinelle_2"):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st.update(act=3)
    for before in ("sentinelle_1", "sentinelle_2", "sentinelle_3"):
        if before != mid:
            st["flags"][before] = True
        if before == mid:
            break
    st["flags"][ss.ANTIMATTER_FLAG] = True
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mid)
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    g.player.infinite_lives = False
    run.frames(2)
    _settle(run)
    return g


def test_in_spacewar_it_flies_along_the_heading_of_the_ship(run):
    g = _sentinelle(run)
    form = _alone(run)
    p = g.player
    _orbit(p)
    p.ast_angle = 0.0
    p.ast_vx = p.ast_vy = 0.0
    assert am.fire(g, p)
    m = g.antimatter.missiles[0]
    assert (round(m.ux, 3), round(m.uy, 3)) == (1.0, 0.0) and m.x == p.x + am.START_AHEAD and m.vx == am.SPEED
    g._end_adventure(False)


def test_in_spacewar_the_blast_destroys_every_bird_in_reach_the_saucer_too(run):
    g = _sentinelle(run)
    form = _alone(run)
    x, y = 300.0, 150.0
    near = _bird(form, 1, x + 100, y)
    green = _bird(form, 2, x, y + 150)
    saucer = _bird(form, sw.SAUCER, x - 120, y)
    far = _bird(form, 1, x + 400, y + 300)
    for b in form.birds:
        _pin(b, b.x, b.y)
    g.score = 0
    am.blast(g, x, y)
    assert not near.alive and not green.alive and not saucer.alive and far.alive
    assert g.score >= 10 + 20 + 500                                   # (the Sentinelle missions pay the normal points)
    g._end_adventure(False)


def test_in_spacewar_it_blows_on_a_bird_in_its_way(run):
    g = _sentinelle(run)
    form = _alone(run)
    p = g.player
    p.x, p.y, p.ast_angle, p.ast_vx, p.ast_vy = 200.0, 400.0, 0.0, 0.0, 0.0
    target = _bird(form, 1, 600.0, 400.0)
    other = _bird(form, 2, 640.0, 520.0)
    for b in form.birds:
        _pin(b, b.x, b.y)
    assert am.fire(g, p)
    _fly(g)
    assert not target.alive and not other.alive
    assert not g.antimatter.missiles
    g._end_adventure(False)


def test_in_spacewar_the_star_stops_it_without_a_blast(run):
    g = _sentinelle(run)
    form = _alone(run)
    p = g.player
    p.x, p.y, p.ast_angle, p.ast_vx, p.ast_vy = 200.0, sw.CY, 0.0, 0.0, 0.0
    bystander = _bird(form, 1, sw.CX + 60, sw.CY + 150)
    _pin(bystander, bystander.x, bystander.y)
    assert am.fire(g, p)
    _fly(g)
    assert not g.antimatter.missiles and not g.antimatter.ready
    assert bystander.alive and not [e for e in g.explosions if isinstance(e, am.Blast)]
    g._end_adventure(False)


def test_in_spacewar_the_missile_does_not_come_round_the_screen(run):
    g = _sentinelle(run)
    form = _alone(run)
    p = g.player
    p.x, p.y, p.ast_angle, p.ast_vx, p.ast_vy = 200.0, 60.0, -math.pi / 2, 0.0, 0.0
    assert am.fire(g, p)
    _fly(g)
    assert not g.antimatter.missiles and not g.antimatter.ready
    g._end_adventure(False)


def test_the_blast_takes_the_small_rock_too(run):
    g = _sentinelle(run)
    form = _alone(run)
    form.rock = sw.launch_rock(form.rng)
    form.rock.x, form.rock.y = 500.0, 300.0
    am.blast(g, 480.0, 300.0)
    assert form.rock is None
    g._end_adventure(False)


# ------------------------------------------------------------------ Asteroids
def test_in_the_asteroids_mission_the_blast_breaks_every_rock_in_reach_and_the_pieces(run):
    from test_asteroids import _launch as launch_ast
    g = run.game
    spec = launch_ast(run, "ast_1")
    g.antimatter = am.Armory(True)
    g.adventure["antimatter"] = True
    run.frames(2)
    _settle(run)
    form = g.formation
    assert isinstance(form, asteroids.AsteroidFormation)
    form.rocks[:] = [_rock(3, 400, 300), _rock(2, 520, 380), _rock(3, 1000, 600)]
    form.repop = False
    far = form.rocks[2]
    am.blast(g, 420.0, 310.0)
    assert form.rocks == [far]                                         # the big one and its pieces are all gone
    assert form.destroyed >= 5
    g._end_adventure(False)


def test_in_the_asteroids_mission_it_flies_where_the_ship_looks_and_hits_a_rock(run):
    from test_asteroids import _launch as launch_ast
    g = run.game
    launch_ast(run, "ast_1")
    g.antimatter = am.Armory(True)
    g.adventure["antimatter"] = True
    run.frames(2)
    _settle(run)
    form = g.formation
    form.repop = False
    p = g.player
    p.x, p.y, p.ast_angle, p.ast_vx, p.ast_vy = 300.0, 300.0, 0.0, 0.0, 0.0
    form.rocks[:] = [_rock(1, 700, 300)]
    form.saucer = None
    assert am.fire(g, p)
    _fly(g)
    assert form.rocks == [] and not g.antimatter.missiles
    g._end_adventure(False)


def test_in_the_asteroids_mission_the_blast_takes_the_saucer(run):
    from test_asteroids import _launch as launch_ast
    g = run.game
    launch_ast(run, "ast_1")
    g.antimatter = am.Armory(True)
    g.adventure["antimatter"] = True
    run.frames(2)
    _settle(run)
    form = g.formation
    form.rocks[:] = []
    form.repop = False
    form.saucer = asteroids.Saucer(True, form.rng)
    form.saucer.x, form.saucer.y = 600.0, 300.0
    am.blast(g, 640.0, 300.0)
    assert form.saucer is None
    g._end_adventure(False)


# ------------------------------------------------------------------ what the player sees
def test_the_missile_is_the_torpedo_of_spacewar_a_little_bigger(run):
    g, spec = _launch(run, "ch1_sortie")
    small = pygame.Surface((200, 200), pygame.SRCALPHA)
    big = pygame.Surface((200, 200), pygame.SRCALPHA)
    sw.draw_torpedo(small, 100, 100, 0.0, -1.0, (210, 220, 235))
    sw.draw_torpedo(big, 100, 100, 0.0, -1.0, (210, 220, 235), am.SIZE)
    ys = lambda s: [y for y in range(200) for x in range(200) if s.get_at((x, y))[3] > 200]
    assert max(ys(big)) - min(ys(big)) > max(ys(small)) - min(ys(small))
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    g.antimatter.missiles.append(am.Missile(500, 400, 0.0, -1.0))
    am.draw(g, surf)
    assert any(surf.get_at((x, y))[:3] != (0, 0, 0) for x in range(480, 520) for y in range(370, 430))
    g._end_adventure(False)


def test_the_torpedo_of_spacewar_is_not_changed_at_the_default_size():
    a = pygame.Surface((120, 120), pygame.SRCALPHA)
    b = pygame.Surface((120, 120), pygame.SRCALPHA)
    sw.draw_torpedo(a, 60, 60, 1.0, 0.0, (180, 220, 255))
    sw.draw_torpedo(b, 60, 60, 1.0, 0.0, (180, 220, 255), 1.0)
    assert pygame.image.tobytes(a, "RGBA") == pygame.image.tobytes(b, "RGBA")


def test_the_explosion_is_drawn_and_ends(run):
    g, spec = _launch(run, "ch1_sortie")
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    blast = am.Blast(640, 360, am.BLAST_RADIUS)
    seen = set()
    for _ in range(int(am.BLAST_TIME / DT) + 5):
        blast.update(DT)
        surf.fill((0, 0, 0))
        blast.draw(surf)
        seen.add(sum(1 for x in range(0, BASE_WIDTH, 16) for y in range(0, BASE_HEIGHT, 16) if surf.get_at((x, y))[:3] != (0, 0, 0)))
        if blast.is_finished():
            break
    assert blast.is_finished() and max(seen) > 60                     # (it covers a good part of the screen)
    g._end_adventure(False)


def test_the_hud_shows_the_key_while_the_missile_is_ready(run):
    g, spec = _launch(run, "ch1_sortie")
    texts = []

    class _Cache:
        def __init__(self, real):
            self.real = real

        def get(self, font, text, color, *a, **k):
            texts.append((text, color))
            return self.real.get(font, text, color, *a, **k)
    g.text_cache = _Cache(g.text_cache)
    am.draw_hud(g)
    assert (i18n.t("antimatter_hud").format(key="M"), am.HUD_COLOR) in texts
    am.fire(g, g.player)
    texts.clear()
    am.draw_hud(g)
    assert texts[0][1] == am.DONE_COLOR                                # spent: dim
    g._end_adventure(False)


def test_the_workshop_says_whether_the_missile_is_there(run, monkeypatch):
    import story
    for unlocked in (False, True):
        g = run.game
        st = ss.create_slot(1, "NOVA", "normal")
        ss.mark_intro_seen(st)
        st["flags"][ss.ANTIMATTER_FLAG] = unlocked
        ss.save_state(ss.story_path(1), st)
        g.story.open_slot(1)
        g.story.pane = "hangar"
        seen = []
        real = story._text

        def spy(surface, font, text, *a, **k):
            seen.append(str(text))
            return real(surface, font, text, *a, **k)
        monkeypatch.setattr(story, "_text", spy)
        g.story.draw(g.game_surface, g.font, g.medium_font, g.font)
        monkeypatch.setattr(story, "_text", real)
        assert i18n.t("story_stat_missile") in seen
        assert (i18n.t("story_missile_ready") in seen) is unlocked


# ------------------------------------------------------------------ what the mutation checks asked for
def test_the_game_loop_flies_the_missile_and_draws_it_and_its_reminder(run, monkeypatch):
    g, spec = _launch(run, "ch1_sortie")
    _still(g)
    _bird_at(g, 100, 100)                                             # (a wave with a bird: it does not end)
    drawn, texts = [], []
    real_draw = am.draw
    monkeypatch.setattr(am, "draw", lambda game, surface: (drawn.append(len(game.antimatter.missiles)), real_draw(game, surface)))

    class _Cache:
        def __init__(self, real):
            self.real = real

        def get(self, font, text, color, *a, **k):
            texts.append(text)
            return self.real.get(font, text, color, *a, **k)
    g.text_cache = _Cache(g.text_cache)
    run.frames(1)
    assert i18n.t("antimatter_hud").format(key="M") in texts and drawn                # (the reminder, the draw call)
    assert am.fire(g, g.player)
    y0 = g.antimatter.missiles[0].y
    drawn.clear()
    run.frames(5)
    assert g.antimatter.missiles[0].y < y0 - 20                       # Game.update flies it
    assert 1 in drawn                                                 # Game.draw shows it
    g._end_adventure(False)


def test_a_missile_too_old_is_lost():
    m = am.Missile(500, 400, 0.0, -1.0)
    assert not m.gone()
    m.age = am.MAX_AGE + 0.1
    assert m.gone()
    assert am.Missile(-40, 100, 1.0, 0.0).gone() and am.Missile(500, BASE_HEIGHT + 40, 0.0, 1.0).gone()


def test_the_edges_of_what_a_missile_touches_in_spacewar(run):
    g = _sentinelle(run)
    form = _alone(run)
    b = _bird(form, 1, 300.0, 200.0)
    just_in = am.Missile(300.0 + b.radius + am.HIT_HALF - 1, 200.0, 1.0, 0.0)
    just_out = am.Missile(300.0 + b.radius + am.HIT_HALF + 2, 200.0, 1.0, 0.0)
    assert am._touch(g, just_in) == "hit" and am._touch(g, just_out) is None
    form.rock = sw.launch_rock(form.rng)
    form.rock.x, form.rock.y = 900.0, 200.0
    assert am._touch(g, am.Missile(900.0, 200.0 + form.rock.radius - 1, 0.0, -1.0)) == "hit"
    g._end_adventure(False)


def test_the_star_hides_what_is_behind_it(run):
    g = _sentinelle(run)
    form = _alone(run)
    p = g.player
    p.x, p.y, p.ast_angle, p.ast_vx, p.ast_vy = 120.0, sw.CY, 0.0, 0.0, 0.0
    behind = _bird(form, 1, sw.CX + sw.STAR_R + 60, sw.CY)
    _pin(behind, behind.x, behind.y)
    assert am.fire(g, p)
    _fly(g)
    assert behind.alive and not g.antimatter.missiles
    g._end_adventure(False)


def test_the_edge_of_the_blast_in_spacewar(run):
    g = _sentinelle(run)
    form = _alone(run)
    inside = _bird(form, 1)
    outside = _bird(form, 1)
    inside.x, inside.y = 300.0 + am.BLAST_RADIUS + inside.radius - 2, 200.0           # (its edge is just in the blast)
    outside.x, outside.y = 300.0, 200.0 + am.BLAST_RADIUS + outside.radius + 6        # (its edge is just out)
    am.blast(g, 300.0, 200.0)
    assert not inside.alive and outside.alive
    g._end_adventure(False)


def test_the_missile_touches_the_mothership(run):
    import invaders
    g, spec = _launch(run, "paint_1", act=2)
    mother = g.formation.mothership = invaders.Mothership(1)
    mother.x = 600.0
    g.formation.enemies = []
    assert am._touch(g, am.Missile(mother.x, mother.y, 0.0, -1.0)) == "hit"
    assert am._touch(g, am.Missile(mother.x, mother.y + 300, 0.0, -1.0)) is None
    g._end_adventure(False)


def test_the_blast_takes_the_decorations_of_the_saucer_in_reach(run):
    g, boss = _saucer(run)
    assert boss.decorations
    deco = boss.decorations[0]
    far = [d for d in boss.decorations if d is not deco and _dist(d.get_hitbox(), deco.x, deco.y) > 52]
    before = g.score
    am.blast(g, deco.x, deco.y)
    assert not deco.alive and all(d.alive for d in far)
    assert g.score >= before + g._deco_points()
    g.boss_saucer = None
    g._end_adventure(False)


def test_without_an_adventure_nothing_fires_nothing_shows(run):
    g, spec = _launch(run, "ch1_sortie")
    g.adventure = None                                                 # (the arcade game, the stock of the last mission is still there)
    assert g.antimatter is not None and g.antimatter.ready
    assert not am.fire(g, g.player) and g.antimatter.ready
    texts = []

    class _Cache:
        def get(self, font, text, color, *a, **k):
            texts.append(text)
            return pygame.Surface((1, 1))
    g.text_cache = _Cache()
    am.draw_hud(g)
    assert not texts
    g.antimatter.missiles.append(am.Missile(500, 400, 0.0, -1.0))
    am.tick(g)
    assert len(g.antimatter.missiles) == 1                            # (not flown either)


def test_the_unlock_is_announced_once(run):
    st = ss.default_state()
    st["act"] = 3
    g = run.game
    g.story.state = st
    for mid in ("sentinelle_1", "sentinelle_2", "sentinelle_3", "sentinelle_4"):
        g.story.apply_result(mid, 100, True)
    first = g.story.toast
    assert first == i18n.T["story_missile_unlocked"][i18n.get_lang()].format(key="M")
    g.story.apply_result("sentinelle_4", 100, True)                    # (flown again after the end of the series)
    assert g.story.toast != first
