"""The escort modules (src/gyro.py), step 1: on screen. The gyroscope pictures, the way they follow the ship, the dome and
the Phenix form, the electric wall, and the TEST - Modules mission with its menu."""
import pygame
import pytest

import gyro
import i18n
import story_state as ss
from settings import BASE_WIDTH
from test_smoke import run  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


class _Ship:
    def __init__(self, x=640.0, y=600.0):
        self.x, self.y = x, y
        self.alive, self.dying = True, False
        self.is_phenix = False
        self.morph_dir = 0
        self.invulnerable = 0.0
        self.blast_hide = 0


class _Game:
    def __init__(self):
        self.explosions = []
        self.played = []
        self.sounds = self

    def play(self, name, **kw):
        self.played.append(name)

    def _boom(self, x, y, kind="enemy"):
        return ("boom", x, y, kind)


def _settle(g, game, ship, seconds=2.0, dt=1 / 120):
    for _ in range(int(seconds / dt)):
        g.update(game, ship, dt)


# ------------------------------------------------------------------ the pictures
def test_the_pictures_of_the_two_hulls():
    for hull in ("phoenix", "shield"):
        pics = gyro.frames(hull)
        assert len(pics) == gyro.FRAMES and all(p.get_size() == (gyro.SIZE, gyro.SIZE) for p in pics)
        assert gyro.frames(hull) is pics                                        # (made once)
        assert pics[0].get_at((gyro.SIZE // 2, gyro.SIZE // 2)).a > 200          # the sphere in the middle
        assert pics[0].get_at((0, 0)).a == 0                                     # (round: the corners are empty)
    a = gyro.frames("phoenix")[0].get_at((gyro.SIZE // 2, gyro.SIZE // 2 + 6))
    b = gyro.frames("shield")[0].get_at((gyro.SIZE // 2, gyro.SIZE // 2 + 6))
    assert a.b > a.r and b.r > b.b                                               # silver-blue, copper-red
    assert pygame.image.tostring(gyro.frames("shield")[0], "RGBA") != pygame.image.tostring(
        gyro.frames("shield")[gyro.FRAMES // 3], "RGBA")                         # the ring turns


# ------------------------------------------------------------------ placing
def test_one_module_on_the_left_two_on_both_sides():
    ship = _Ship()
    assert [m.side for m in gyro.Gyro("shield", 1, 1, ship).modules] == [-1]
    assert [m.side for m in gyro.Gyro("shield", 2, 2, ship).modules] == [-1, 1]
    assert all(m.hp == 2 for m in gyro.Gyro("shield", 2, 2, ship).modules)


def test_they_follow_the_ship_a_little_late():
    ship, game = _Ship(), _Game()
    g = gyro.Gyro("phoenix", 2, 1, ship)
    _settle(g, game, ship)
    left, right = g.modules
    assert (left.x, left.y) == pytest.approx((ship.x - gyro.ANCHOR[0], ship.y + gyro.ANCHOR[1]), abs=0.5)
    assert right.x == pytest.approx(ship.x + gyro.ANCHOR[0], abs=0.5)
    ship.x += 100
    g.update(game, ship, 1 / 60)
    assert ship.x - 100 - gyro.ANCHOR[0] < left.x < ship.x - gyro.ANCHOR[0]       # on its way, not there yet
    _settle(g, game, ship, 1.0)
    assert left.x == pytest.approx(ship.x - gyro.ANCHOR[0], abs=0.5)


@pytest.mark.parametrize("how", ("dome", "morph"))
def test_in_the_dome_or_the_phenix_form_they_move_out_and_down(how):
    ship, game = _Ship(), _Game()
    g = gyro.Gyro("shield", 2, 1, ship)
    _settle(g, game, ship)
    if how == "dome":
        ship.is_phenix = True
    else:
        ship.morph_dir = 1                                                       # (already while it changes)
    g.update(game, ship, gyro.WIDE_TIME / 2)
    assert 0.4 < g.wide < 0.6                                                    # it takes WIDE_TIME
    _settle(g, game, ship)
    left, right = g.modules
    assert left.x == pytest.approx(ship.x - gyro.WIDE[0], abs=0.5) and right.y == pytest.approx(ship.y + gyro.WIDE[1], abs=0.5)
    ship.is_phenix, ship.morph_dir = False, 0
    _settle(g, game, ship)
    assert g.wide == 0 and left.x == pytest.approx(ship.x - gyro.ANCHOR[0], abs=0.5)


# ------------------------------------------------------------------ the wall
def test_the_electric_wall_destroys_a_module():
    ship, game = _Ship(x=400), _Game()
    g = gyro.Gyro("shield", 2, 2, ship)
    _settle(g, game, ship)
    ship.x = 50                                                                  # (the left module goes into the wall)
    for _ in range(40):
        g.update(game, ship, 1 / 120)
        if g.modules[0].struck > 0:
            break
    left, right = g.modules
    assert left.struck > 0 and left.alive and left not in g.alive()             # in the lightning: it does no more
    assert "electric" in game.played
    _settle(g, game, ship, gyro.STRUCK + 0.05)
    assert not left.alive and g.lost == ["wall"] and game.explosions             # it blows up, whatever its armour
    assert right.alive and right in g.alive()
    surf = pygame.Surface((BASE_WIDTH, 720), pygame.SRCALPHA)
    g.draw(surf, ship)                                                           # (only the right one is drawn)


def test_the_wall_needs_the_module_against_it():
    ship, game = _Ship(x=gyro.WALL_X + gyro.SIZE * 0.42 + gyro.ANCHOR[0] + 6), _Game()
    g = gyro.Gyro("phoenix", 2, 1, ship)
    _settle(g, game, ship)
    assert all(m.struck == 0 and m.alive for m in g.modules)


# ------------------------------------------------------------------ drawn with the ship
def test_they_blink_with_the_ship_and_vanish_with_it():
    ship, game = _Ship(), _Game()
    g = gyro.Gyro("shield", 2, 1, ship)
    _settle(g, game, ship)

    def drawn():
        surf = pygame.Surface((BASE_WIDTH, 720), pygame.SRCALPHA)
        g.draw(surf, ship)
        m = g.modules[0]
        return surf.get_at((int(m.x), int(m.y))).a > 0
    assert drawn()
    ship.invulnerable = 1.0 / 12 * 2 + 0.01                                     # int(x * 12) even: the ship is hidden
    assert not drawn()
    ship.invulnerable = 1.0 / 12 + 0.01
    assert drawn()
    ship.invulnerable = 0
    ship.blast_hide = 0.2
    assert not drawn()
    ship.blast_hide, ship.dying = 0, True
    assert not drawn()


# ------------------------------------------------------------------ the mission and its menu
def _hub(run, hull="shield"):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    if hull == "phoenix":
        st["slots"][1]["owned"] = True
        st["selected_slot"] = 1
    ss.save_state(ss.story_path(1), st)
    g.menu_screen = "story_hub"
    g.story.open_slot(1)
    g.story.screen, g.story.pane = "hub", "map"
    g.story.map_index = [m["id"] for m in g.story.missions()].index("test_modules")
    return g


def test_the_mission_is_a_test_on_the_maps_of_the_three_acts():
    m = ss.mission_by_id("test_modules")
    assert m["acts"] == (1, 2, 3) and m["training"] and m["test"]
    assert ss.mission_waves(m) == [6, 7, 8, 9, 10, 11]                           # a run of the levels 6 to 11
    for act in (1, 2, 3):
        ids = [x["id"] for x in ss.MISSIONS if act in tuple(x.get("acts", ()))]
        assert ids.index("test_modules") == ids.index("test_scramble") + 1
    for lang in ("fr", "en"):
        i18n.set_lang(lang)
        for key in ("story_m_modules", "story_m_modules_hud", "story_m_modules_b", "modules_pick_title",
                    "modules_pick_count_1", "modules_pick_count_2", "modules_pick_armour_1", "modules_pick_armour_2"):
            assert i18n.t(key) != key
        for armour in (1, 2):
            assert "{" not in i18n.t("modules_pick_info_%d" % armour).format(shots=3)
    i18n.set_lang("fr")


def test_the_menu_chooses_how_many_and_how_tough(run):
    g = _hub(run)
    hub = g.story
    assert hub.confirm() is None and hub.screen == "lander_pick" and hub._pick_modules()
    import story
    assert story.MODULE_PICKS[hub.lander_index] == (2, 1)                        # (two, normal: the first choice lit)
    surf = pygame.Surface((1280, 720))
    hub._draw_gate(surf, g.font, g.medium_font, g.font)                          # (the menu draws)
    picks = []
    for _ in range(len(story.MODULE_PICKS)):
        picks.append(story.MODULE_PICKS[hub.lander_index])
        hub.nav_v(1)
    assert sorted(picks) == [(1, 1), (1, 2), (2, 1), (2, 2)]
    while story.MODULE_PICKS[hub.lander_index] != (1, 2):
        hub.nav_v(1)
    spec = hub.confirm()
    assert spec["id"] == "test_modules" and spec["modules"] == {"count": 1, "armour": 2}
    assert spec["training"] and spec["waves"] == [6, 7, 8, 9, 10, 11] and hub.screen == "hub"


def test_back_leaves_the_menu_without_launching(run):
    g = _hub(run)
    g.story.confirm()
    g.story.back()
    assert g.story.screen == "hub" and not g.started


@pytest.mark.parametrize("hull", ("shield", "phoenix"))
def test_the_mission_flies_with_its_modules(run, hull):
    g = _hub(run, hull)
    g.story.confirm()
    spec = g.story.confirm()
    g._request_adventure(dict(spec, first_help_read=True))
    assert g.started and g.gyro is not None
    assert g.gyro.hull == ("phoenix" if hull == "phoenix" else "shield") and len(g.gyro.modules) == 2
    if hull == "shield":
        assert g.player.adventure_dome                                           # (the test: the dome, to see them move out)
    run.frames(30)
    left = g.gyro.modules[0]
    assert left.x == pytest.approx(g.player.x - gyro.ANCHOR[0], abs=20)
    run.frames(2)


def test_no_modules_without_them_nor_once_the_mission_is_over(run):
    g = run.game
    g.adventure = {"id": "x"}
    gyro.start(g, {"launch": True})
    assert g.gyro is None
    gyro.start(g, {"modules": {"count": 2, "armour": 1}, "lander": True})
    assert g.gyro is None                                                        # (not in the Lander, Scramble... for now)
    gyro.start(g, {"modules": {"count": 2, "armour": 1}})
    assert g.gyro is not None
    g.adventure = None
    assert gyro._on(g) is None                                                   # an arcade game never shows them


# ------------------------------------------------------------------ step 2: grazing, the shots
@pytest.mark.parametrize("wide", (False, True))
def test_a_module_grazes_the_ship_never_touches_it(wide):
    ship, game = _Ship(x=640), _Game()
    ship.is_phenix = wide
    g = gyro.Gyro("shield", 2, 1, ship)
    _settle(g, game, ship)
    ax = (gyro.WIDE if wide else gyro.ANCHOR)[0]
    closest = 1e9
    for direction in (1, -1, 1, -1):                       # the ship darts left and right, at 4 times its speed
        for _ in range(30):                                 # (from 640 to 1015 and back: clear of the walls)
            ship.x += direction * 1500 / 120
            g.update(game, ship, 1 / 120)
            for m in g.modules:
                closest = min(closest, m.side * (m.x - ship.x))
    assert closest == pytest.approx(ax - gyro.GRAZE, abs=0.01)       # it came in as close as allowed, no closer
    assert ax - gyro.GRAZE - gyro.SIZE * 0.385 > 30                  # (the ring stays clear of the hull, 30 px each side)


def _flying(run, count=2, hull="shield"):
    g = _hub(run, hull)
    g.story.confirm()
    import story
    while story.MODULE_PICKS[g.story.lander_index] != (count, 1):
        g.story.nav_v(1)
    spec = g.story.confirm()
    g._request_adventure(dict(spec, first_help_read=True))
    g.input_grace = 0.0
    g.player.infinite_lives = True
    run.frames(40)
    return g


@pytest.mark.parametrize("count", (1, 2))
def test_each_module_adds_a_shot_to_the_salvo(run, count):
    g = _flying(run, count)
    p = g.player
    p.shots = []
    p.shoot()
    own = [s for s in p.shots if not s.get("module")]
    mods = [s for s in p.shots if s.get("module")]
    assert len(own) == 1 and len(mods) == count                       # x2, x3
    for s, m in zip(sorted(mods, key=lambda s: s["x"]), sorted(g.gyro.modules, key=lambda m: m.x)):
        assert s["x"] == pytest.approx(m.x) and s["y"] == pytest.approx(m.y - gyro.SIZE * 0.48)   # from its cannon
    surf = pygame.Surface((1280, 720))
    p.draw(surf)
    s = mods[0]
    tip = surf.get_at((int(s["x"]) - 2, int(s["y"]) + 1))[:3]
    assert tip == gyro.SHOT_COLOURS["shield"][0]                      # in the light of the modules of the Shield


def test_in_the_phenix_form_the_wings_and_the_modules_fire(run):
    g = _flying(run, 2, "phoenix")
    p = g.player
    p.phenix_gauge = 10
    p.try_activate_phenix()
    p.morph_dir = 0
    p.shots = []
    p.shoot()
    assert sum(1 for s in p.shots if s.get("flame")) == 2 and sum(1 for s in p.shots if s.get("module")) == 2
    assert gyro.SHOT_COLOURS["phoenix"] == p.gun_colours


def test_the_shots_of_the_modules_never_hold_back_the_ship(run):
    g = _flying(run, 2)
    p = g.player
    p.shots = []
    p.shoot()
    for i in reversed(range(len(p.shots))):
        if not p.shots[i].get("module"):
            p.destroy_bullet("valid", i)                              # the ship's shot hit something close
    assert len(p.shots) == 2 and not p.own_shots()
    p.shoot()                                                         # the ship fires again at once...
    assert len(p.own_shots()) == 1
    assert sum(1 for s in p.shots if s.get("module")) == 2            # ... and the modules, still in flight, do not


def test_a_missed_shot_of_a_module_costs_nothing(run):
    g = _flying(run, 2, "phoenix")                                    # (the gauge of the Phenix: the Shield's is its dome)
    p = g.player
    p.phenix_gauge = 5.0
    p.combo_streak = 3
    p.shots = [{"x": 300, "y": -25, "resolved": False, "flame": False, "module": -1}]
    run.frames(3)
    assert p.phenix_gauge == 5.0 and p.combo_streak == 3 and not p.shots
    p.shots = [{"x": 300, "y": -25, "resolved": False, "flame": False}]
    run.frames(3)
    assert p.phenix_gauge == 4.0                                      # (the ship's own miss costs one, as always)


def test_a_shot_of_a_module_that_hits_charges_the_gauge(run):
    g = _flying(run, 2, "phoenix")
    p = g.player
    p.phenix_gauge = 4.0
    p.shots = [{"x": 300, "y": 300, "resolved": False, "flame": False, "module": 1}]
    p.destroy_bullet("valid", 0)
    assert p.phenix_gauge > 4.0


def test_no_shot_from_a_module_struck_or_lost(run):
    g = _flying(run, 2)
    p = g.player
    left, right = g.gyro.modules
    left.struck = 0.1
    right.alive = False
    p.shots = []
    p.shoot()
    assert not [s for s in p.shots if s.get("module")]


def test_a_module_s_shot_brings_a_bird_down(run):
    """In the mission itself: a bird in front of the left module, and nothing in front of the ship, falls to it."""
    g = _flying(run, 2)
    p = g.player
    birds = [e for e in g.formation.get_hittable_enemies() if not getattr(e, "diving", False)]
    assert birds
    bird = birds[0]
    for e in g.formation.get_hittable_enemies():                      # (only this bird can be hit)
        if e is not bird:
            e.alive = False
    p.x = bird.x + gyro.ANCHOR[0]
    for m in g.gyro.modules:
        m.x, m.y = g.gyro.target(p, m.side)
    before = g.score if hasattr(g, "score") else None
    p.shots = []
    p.shoot()
    for _ in range(90):
        run.frames(1)
        if not bird.alive or getattr(bird, "dying", False):
            break
    assert not bird.alive or bird.dying


def test_holding_fire_the_ship_fires_again_while_the_modules_shots_still_fly(run):
    g = _flying(run, 2)
    p = g.player
    p.shots = [{"x": 300, "y": 400, "resolved": False, "flame": False, "module": -1},
               {"x": 400, "y": 400, "resolved": False, "flame": False, "module": 1}]
    p.autofire = True
    p.update(1 / 120, None, ai_move=0.0, ai_shoot=True)         # (the fire held, as the game reads it each frame)
    assert len(p.own_shots()) == 1 and len(p.shots) == 3


# ------------------------------------------------------------------ step 3: the harm done to the modules
def test_a_shot_destroys_a_normal_module():
    ship, game = _Ship(), _Game()
    g = gyro.Gyro("shield", 2, 1, ship)
    left = g.modules[0]
    assert g.hit(game, left, "shot") and not left.alive and g.lost == ["shot"]
    assert game.explosions and "explosion" in game.played


def test_a_reinforced_module_takes_two_shots_and_smokes_after_the_first():
    ship, game = _Ship(), _Game()
    g = gyro.Gyro("phoenix", 2, 2, ship)
    left = g.modules[0]
    assert not g.hit(game, left, "shot")
    assert left.alive and left.hp == 1 and left.damaged and left.flash > 0 and "shield_zap" in game.played
    _settle(g, game, ship, 0.5)
    assert g.smoke and left.flash == 0                                       # it smokes once damaged
    surf = pygame.Surface((BASE_WIDTH, 720), pygame.SRCALPHA)
    g.draw(surf, ship)
    assert g.hit(game, left, "shot") and not left.alive
    assert not g.modules[1].damaged and g.modules[1].alive


def test_a_collision_always_destroys_at_once():
    ship, game = _Ship(), _Game()
    g = gyro.Gyro("shield", 2, 2, ship)
    assert g.hit(game, g.modules[0], "crash") and g.lost == ["crash"]


def test_sheltered_in_the_dome_or_the_phenix_form_nothing_touches_them():
    ship, game = _Ship(), _Game()
    g = gyro.Gyro("shield", 2, 1, ship)
    assert g.targets() == g.modules
    ship.is_phenix = True
    _settle(g, game, ship, 0.5)
    assert g.sheltered() and g.targets() == []


class _Bullet:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.alive = True

    def get_hitbox(self):
        return pygame.Rect(int(self.x) - 3, int(self.y) - 6, 6, 12)


def test_in_the_mission_an_enemy_shot_hits_the_module_not_the_ship(run):
    g = _flying(run, 2)
    p = g.player
    p.infinite_lives = False
    lives = p.lives
    left = g.gyro.modules[0]
    b = _Bullet(left.x, left.y)
    g.formation.bullets.append(b)
    import update_play
    update_play.enemy_attacks_vs_players(g)
    assert not b.alive and not left.alive and g.gyro.lost == ["shot"]
    assert p.lives == lives and not p.dying                                  # (the module stood in the way)


def test_a_diving_bird_and_the_module_go_down_together_for_no_points(run):
    g = _flying(run, 2)
    bird = next(e for e in g.formation.get_hittable_enemies())
    right = g.gyro.modules[1]
    bird.state = "diving"                                               # (a bird in its dive)
    bird.x, bird.y = right.x, right.y
    score = g.score if hasattr(g, "score") else g.player.score
    import update_play
    update_play.enemy_attacks_vs_players(g)
    assert not right.alive and g.gyro.lost == ["crash"]
    assert not bird.alive or bird.dying
    assert (g.score if hasattr(g, "score") else g.player.score) == score       # no points


def test_the_laser_of_a_guardian_destroys_a_reinforced_module(run):
    from guardian import FireLaser
    g = _flying(run, 2)
    g.gyro.modules[0].hp = g.gyro.modules[0].armour = 2
    left = g.gyro.modules[0]
    laser = FireLaser.__new__(FireLaser)
    laser.alive = True
    laser.get_hitbox = lambda: left.rect().inflate(4, 40)
    g.formation.bullets.append(laser)
    import update_play
    update_play.enemy_attacks_vs_players(g)
    assert not left.alive and g.gyro.lost == ["crash"] and laser.alive       # (it goes through)


class _Boss:
    def __init__(self, hull):
        self.alive = True
        self.bullets = []
        self._hull = hull

    def get_hull_hitbox(self):
        return self._hull

    def draw_shots(self, surface):
        pass


def test_the_boss_its_shots_take_a_point_its_hull_destroys(run):
    g = _flying(run, 2)
    left, right = g.gyro.modules
    left.hp = left.armour = 2
    boss = _Boss(pygame.Rect(0, 0, 0, 0))
    shot = _Bullet(left.x, left.y)
    boss.bullets.append(shot)
    g.boss_saucer = boss
    gyro.attacks(g)
    assert not shot.alive and left.alive and left.hp == 1
    boss._hull = right.rect().inflate(10, 10)
    gyro.attacks(g)
    assert not right.alive and "crash" in g.gyro.lost
    g.boss_saucer = None


def test_nothing_hits_them_while_sheltered_in_the_mission(run):
    g = _flying(run, 2)
    p = g.player
    p.try_activate_phenix()                                                  # (the dome of the test)
    run.frames(30)
    left = g.gyro.modules[0]
    b = _Bullet(left.x, left.y)
    g.formation.bullets.append(b)
    gyro.attacks(g)
    assert left.alive and b.alive
