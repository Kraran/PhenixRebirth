"""The VIP rescue (Act 2 BONUS, src/escort.py): a cruise ship to bring across the bottom of the screen while the level 3
birds throw themselves at it. Open with a two-dimensional reactor installed, flown by such a hull only, once. Won, it
tells who was on board (Lyra Voss) and opens her concert in the Phobos bar."""
import os

import pygame
import pytest

import escort
import story_items as si
import story_state as ss
from escort import CruiseShip, EscortFormation
from player import Player
from settings import BASE_HEIGHT, BASE_WIDTH, PLAYER_VERTICAL_TOP, asset_path
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

DT = 1 / 60
ID = "bonus_vip"
SHIELD_ON = {"reactor_shield": si.INSTALLED}
PHENIX_ON = {"reactor_phenix": si.INSTALLED}


@pytest.fixture(scope="module", autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


@pytest.fixture
def french():
    from i18n import get_lang, set_lang
    before = get_lang()
    set_lang("fr")
    yield
    set_lang(before)


def _state(got=None, phenix=False, act2=True):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    if act2:
        ss.jump_to_act2(st)
    if phenix:
        st["flags"]["phenix_owned"] = True
        st["slots"][1]["owned"] = True
    st["items"]["got"].update(got or {})
    return st


def _select(st, hull):
    st["selected_slot"] = [sl.get("id") for sl in st["slots"]].index(hull)


def _ids(st):
    return [m["id"] for m in ss.visible_missions(st)]


def _launch(run, got=SHIELD_ON, phenix=False, select=None):
    g = run.game
    st = _state(got, phenix=phenix)
    if select:
        _select(st, select)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.pane = "map"
    g.story.map_index = [m["id"] for m in g.story.missions()].index(ID)
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    g.player.infinite_lives = True
    return spec


def _arrived(run, limit=600):
    for _ in range(limit):
        if run.game.stage_transition is None:
            return
        run.frames(1)
    raise AssertionError("the ship never arrived")


# ------------------------------------------------------------------ the mission on the map
def test_the_mission_is_an_act_2_bonus_flown_once():
    m = ss.mission_by_id(ID)
    assert m["acts"] == (2, 3) and m["once"] and m["secret"] and m["needs_reactor"] and m["escort"]
    assert m["stage"] == 11                                        # the birds of level 3
    assert ss.LYRA_FLAG in m["unlock"] and m["win_scene"] == ss.VIP_SCENE


def test_hidden_until_a_reactor_is_installed():
    assert ID not in _ids(_state())
    assert ID not in _ids(_state({"reactor_shield": si.FOUND}))   # caught, on sale: not yet
    assert ID in _ids(_state(SHIELD_ON))
    assert ID in _ids(_state(PHENIX_ON, phenix=True))
    assert ID not in _ids(_state(SHIELD_ON, act2=False))          # an Act 2 mission (the reactor can come in Act 1)


def test_a_reactor_on_a_lost_hull_does_not_count():
    st = _state(SHIELD_ON, phenix=True)
    st["slots"][0]["destroyed"] = True
    st["slots"][0]["owned"] = False
    assert ss.reactor_hulls(st) == [] and not ss.mission_open(st, ss.mission_by_id(ID))


def test_flown_once_and_still_on_the_map_of_act_3_until_it_is_won():
    st = _state(SHIELD_ON)
    m = ss.mission_by_id(ID)
    assert ss.mission_playable(st, m)
    st["act"] = 3
    assert ID in _ids(st)
    st["cleared"].append(ID)
    assert ID not in _ids(st)                                      # won: Act 3 does not list it any more
    st["act"] = 2
    assert ID in _ids(st) and not ss.mission_playable(st, m)      # its own act shows it, done


def test_the_hull_flown_is_one_with_its_reactor():
    st = _state(PHENIX_ON, phenix=True)
    _select(st, "shield")
    assert ss.reactor_hull(st) == "phoenix"                        # the Shield has none: the Phenix flies it
    st["items"]["got"].update(SHIELD_ON)
    assert ss.reactor_hull(st) == "shield"                         # both have one: the hull selected
    _select(st, "phoenix")
    assert ss.reactor_hull(st) == "phoenix"


def test_the_launch(run):
    spec = _launch(run, got=PHENIX_ON, phenix=True, select="shield")
    assert spec["escort"] and spec["ship"] == "phoenix" and spec["stage"] == 11
    g = run.game
    assert g.ship_id == "phoenix" and g.player.vertical_range is not None
    assert isinstance(g.formation, EscortFormation)


def test_installing_a_reactor_announces_the_new_bonus(run, french):
    st = _state({"reactor_shield": si.FOUND})
    st["credits"] = 5000
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    assert hub._buy(("item:reactor_shield",)) and si.reactor_on(hub.state, "shield")
    assert hub.toast == "Nouvelle mission BONUS sur la carte !"


# ------------------------------------------------------------------ the birds
def test_blue_and_khaki_birds_only_and_they_never_run_out_but_come_back_slowly():
    form = EscortFormation()
    kinds = sorted(e.stage for e in form.enemies)
    assert kinds == [1] * escort.ON_SCREEN[1] + [2] * escort.ON_SCREEN[2]
    assert all(isinstance(e, escort.EscortBird) for e in form.enemies)
    for e in form.enemies:
        e.alive = False
    for _ in range(int(escort.REFILL_DELAY * 2.5 / DT)):
        form.update(DT, 0)
    back = [e for e in form.enemies if e.alive]
    assert 2 * 2 <= len(back) <= 2 * 3                              # one of each kind every REFILL_DELAY seconds
    assert escort.REFILL_DELAY >= 2.5 > EscortFormation.__mro__[1].REFILL_DELAY
    for _ in range(int(escort.REFILL_DELAY * (max(escort.ON_SCREEN.values()) + 1) / DT)):
        form.update(DT, 0)
    alive = [e for e in form.enemies if e.alive]
    assert len(alive) == escort.ON_SCREEN[1] + escort.ON_SCREEN[2]          # all replaced, for ever
    assert not form.all_dead() and form.remaining() == 0


def test_no_bird_dives_before_the_cruise_ship_is_in_sight_then_a_few_at_a_time():
    form = EscortFormation()
    for _ in range(int(3 / DT)):
        form.update(DT, 0)
    assert form.divers() == 0 and form.cruise.x < escort.DIVE_FROM_X
    form.cruise.x = 400
    most = 0
    for _ in range(int(20 / DT)):
        form.update(DT, 0)
        most = max(most, form.divers())
    assert 1 <= most <= escort.MAX_DIVERS


def _swirling_bird(form, x=200.0):
    bird = next(e for e in form.enemies if e.state == "formation")
    bird.x, bird.y = x, 200.0
    form.dive_wait = 0.0
    bird.start_dive(0)
    return bird


def test_a_bird_swirls_before_it_strikes():
    form = EscortFormation()
    form.cruise.x = 640
    bird = _swirling_bird(form, x=640.0)
    assert bird.state == "swirl" and bird.diving                  # (a swirling bird hits the ship it meets)
    ys, xs, t = [], [], 0.0
    while bird.state == "swirl":
        bird.update(DT, form.offset_x, 0)
        ys.append(bird.y)
        xs.append(bird.x)
        t += DT
        assert t < escort.SWIRL_TIME[1] + 0.1
    assert t >= escort.SWIRL_TIME[0] - 0.1
    ups = sum(1 for a, b in zip(ys, ys[1:]) if b < a)
    assert ups > 10                                                # it goes up again in its loops, not only down
    assert max(xs) - min(xs) > 2 * escort.SWIRL_RADIUS[0] - 10     # round loops
    assert max(ys) <= escort.SWIRL_FLOOR + escort.SWIRL_RADIUS[1] < form.cruise.hull().top - 40    # well above it
    assert bird.state == "diving"


def test_then_it_dives_at_the_cruise_ship_steeply():
    form = EscortFormation()
    form.cruise.x = 900
    bird = _swirling_bird(form)
    bird.aim_offset = 0.0
    while bird.state == "swirl":
        bird.update(DT, form.offset_x, 0)
    start = bird.x
    for _ in range(int(1.0 / DT)):
        x, y = bird.x, bird.y
        bird.update(DT, form.offset_x, 0)
        assert abs(bird.x - x) <= (bird.y - y) * escort.STRIKE_SLANT + 1     # more down than sideways: no swoop
    assert start > 300 and bird.x > start + 100                    # the loops drifted towards it, the dive goes on


def test_a_bird_that_misses_goes_back_to_its_seat():
    form = EscortFormation()
    bird = _swirling_bird(form)
    bird.state = "diving"
    bird.y = BASE_HEIGHT + 60
    bird.update(DT, form.offset_x, 0)
    assert bird.state == "returning" and bird.y < 0


# ------------------------------------------------------------------ the cruise ship and the player's ship
def test_the_cruise_ship_rides_the_line_of_the_ship_and_crosses_slowly():
    c = CruiseShip()
    assert c.y == BASE_HEIGHT - 95 and c.x < 0 and c.progress() == 0.0
    for _ in range(int(10 / DT)):
        c.advance(DT, [])
    assert 120 < c.x < 160 and not c.through                       # 220 px in ten seconds


def test_a_ship_in_front_stops_it_and_a_ship_above_does_not():
    c = CruiseShip()
    c.x = 400
    p = Player(400 + escort.HULL[0] / 2 + 20, c.y, ship_id="shield")
    c.advance(DT, [escort.ship_body(p)])
    assert c.blocked and c.x == 400                                # it waits
    p.y = PLAYER_VERTICAL_TOP
    c.advance(DT, [escort.ship_body(p)])
    assert not c.blocked and c.x > 400                             # the reactor lets the ship fly over it


def test_the_ship_bumps_into_it_without_going_through():
    c = CruiseShip()
    c.x = 600
    p = Player(600 + escort.HULL[0] / 2 + 10, c.y, ship_id="shield")     # driven into its nose
    assert escort.bump(p, c)
    assert escort.ship_body(p).left >= c.hull().right and p.y == c.y     # pushed back out, sideways
    p = Player(600 - escort.HULL[0] / 2 - 10, c.y, ship_id="shield")     # into its back
    assert escort.bump(p, c) and escort.ship_body(p).right <= c.hull().left
    p = Player(600, c.y - escort.HULL[1] / 2 - 20, ship_id="shield")     # coming down on its roof
    assert escort.bump(p, c) and escort.ship_body(p).bottom <= c.hull().top and p.x == 600
    p = Player(1000, c.y, ship_id="shield")
    assert not escort.bump(p, c)


def test_in_the_game_the_ship_is_held_out_and_lives_are_safe(run):
    _launch(run)
    _arrived(run)
    g = run.game
    form = g.formation
    for e in form.enemies:
        e.alive = False                                            # (no bird in the way of this test)
    form.swarm["reserve"] = {1: 0, 2: 0, 3: 0, 4: 0}
    form.cruise.x = g.player.x - 40
    lives = g.player.lives
    run.frames(3)
    body, hull = escort.ship_body(g.player), form.cruise.hull()
    assert not body.colliderect(hull) and g.player.lives == lives and g.player.alive


# ------------------------------------------------------------------ lost and won
def test_a_bird_on_the_cruise_ship_loses_the_mission(run, french):
    _launch(run)
    _arrived(run)
    g = run.game
    form = g.formation
    g.player.x = 1100
    bird = next(e for e in form.enemies if e.alive)
    form.cruise.x = 500
    bird.state = "diving"
    bird.x, bird.y = 500.0, form.cruise.y
    bird.rect.center = (500, int(form.cruise.y))
    run.frames(1)
    assert form.cruise.destroyed and not form.failed and g.started          # the explosion is seen first
    run.frames(int(escort.LOST_DELAY / DT) + 5)
    assert not g.started and g.menu_screen == "story_hub"
    assert ID not in (g.story.state.get("cleared") or [])
    assert g.story.toast.startswith("Échec")


def test_shots_go_through_the_cruise_ship(run):
    _launch(run)
    _arrived(run)
    g = run.game
    form = g.formation
    for e in form.enemies:
        e.alive = False
    form.swarm["reserve"] = {1: 0, 2: 0, 3: 0, 4: 0}
    form.cruise.x = 300
    g.player.x = 900
    from enemy import EnemyBullet
    form.bullets.append(EnemyBullet(300, form.cruise.y - 10, stage=1))
    run.frames(2)
    assert not form.cruise.destroyed


def test_through_the_right_edge_the_mission_is_won_and_lyra_voss_was_on_board(run, french):
    _launch(run)
    _arrived(run)
    g = run.game
    form = g.formation
    g.player.x = 200
    form.cruise.x = BASE_WIDTH + escort.HULL_W / 2 - escort.FLAME_AT[0] - 1
    for _ in range(600):
        run.frames(1)
        if not g.started:
            break
    assert form.won and not g.started and g.menu_screen == "story_hub"
    hub = g.story
    assert ID in hub.state["cleared"] and ss.flag(hub.state, ss.LYRA_FLAG)
    assert hub.screen == "intro" and hub.scene_id == ss.VIP_SCENE                 # who was on board
    assert hub.intro_slides == [("lyra_voss", "story_scene_vip")]
    assert {"key": "story_log_vip"} in hub.state["log"]


def test_the_birds_flee_when_it_is_through():
    form = EscortFormation()
    form.won = True
    for _ in range(int(3 / DT)):
        form.update(DT, 0)
    assert form.all_dead() and not any(e.alive for e in form.enemies)


# ------------------------------------------------------------------ the scene and the texts
def test_the_scene_is_in_the_journal_after_the_paint_and_has_its_picture(french):
    assert ss.VIP_SCENE in ss.SCENE_ORDER
    assert ss.SCENE_ORDER.index(ss.VIP_SCENE) == ss.SCENE_ORDER.index("paint_1") + 1
    assert os.path.isfile(asset_path("story", "lyra_voss.jpg"))
    from i18n import t
    text = t("story_scene_vip")
    assert text.startswith("Vous ne devinerez jamais qui était à bord du vaisseau qu’on a sauvé…")
    assert "Lyra Voss ! La plus grande star du système solaire !" in text
    assert text.endswith("Bon sang, aujourd’hui j’ai une raison de plus d’adorer mon boulot de pilote.")


def test_the_hud_shows_how_far_the_cruise_ship_is(run, french, monkeypatch):
    _launch(run)
    _arrived(run)
    g = run.game
    c = g.formation.cruise
    c.x = -escort.HULL_W / 2 + (BASE_WIDTH + escort.HULL_W - escort.FLAME_AT[0]) / 2
    texts = []
    real = type(g.text_cache).get

    def spy(self, font, text, *a, **k):
        texts.append(text)
        return real(self, font, text, *a, **k)
    monkeypatch.setattr(type(g.text_cache), "get", spy)
    run.frames(1)
    assert any(x.startswith("VIP : 5") for x in texts)


def test_the_pictures_of_the_yacht():
    img = escort.picture()
    assert img.get_size() == (escort.HULL_W, escort.HULL_H)
    assert img.get_at((escort.HULL_W // 2, escort.HULL_H // 2))[3] >= 250      # the hull is solid (windows too)
    assert img.get_at((1, 1))[3] == 0 and img.get_at((escort.HULL_W - 2, escort.HULL_H - 2))[3] == 0
    sheet = pygame.image.load(asset_path("sprites", "vip_yacht_flame.png"))
    rows = -(-escort.FLAME_FRAMES // escort.FLAME_COLS)
    assert sheet.get_size() == (escort.FLAME_W * escort.FLAME_COLS, escort.FLAME_H * rows)
    a, b = escort.flame_frame(0.0), escort.flame_frame(0.5)
    assert a.get_size() == (escort.FLAME_W, escort.FLAME_H)
    assert pygame.image.tobytes(a, "RGB") != pygame.image.tobytes(b, "RGB")    # it moves


def test_the_flame_is_not_part_of_the_hit_box():
    c = CruiseShip()
    c.x = 500
    pic, hull = c.picture_rect(), c.hull()
    assert pic.contains(hull) and hull.left >= pic.left
    flame = pygame.Rect(pic.x + escort.FLAME_AT[0], pic.y + escort.FLAME_AT[1], escort.FLAME_W - 4, escort.FLAME_H)
    assert not flame.colliderect(hull)
    form = EscortFormation()
    form.cruise.x = 500
    bird = next(e for e in form.enemies)
    bird.x, bird.y = float(flame.centerx), float(flame.centery)
    bird.rect.center = flame.center
    assert not bird.get_hitbox().colliderect(form.cruise.hull())


def test_it_is_through_only_when_its_flame_is_gone_too():
    c = CruiseShip()
    c.x = BASE_WIDTH + escort.HULL_W / 2 + 10                      # the hull is out, the flame still shows
    assert not c.through and c.progress() < 1.0
    c.x = BASE_WIDTH + escort.HULL_W / 2 - escort.FLAME_AT[0]
    assert c.through and c.progress() == 1.0
