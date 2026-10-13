"""Loot items in a mission of the Adventure: what the installed items do to the ship, the item that falls from the top of
the screen, the catch, and what the end of the mission (or leaving it) records."""
import random

import pygame
import pytest

import loot
import menu_actions
import story_items as si
import story_state as ss
import update_play
from player import Player
from settings import BASE_HEIGHT, BASE_WIDTH, BULLET_SPEED, PLAYER_SPEED
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

DT = 1 / 60


class _Keys:
    def __init__(self, *down):
        self.down = set(down)

    def __getitem__(self, k):
        return k in self.down


def _slot(credits=0, found=(), buy=(), mode="normal"):
    """A saved pilot with some items found and some bought."""
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    st["credits"] = credits
    for item in found:
        si.find(st, item)
    for item in buy:
        assert si.buy(st, item)
    ss.save_state(ss.story_path(1), st)
    return st


def _launch(run, **kw):
    g = run.game
    _slot(**kw)
    g.story.open_slot(1)
    g.story.map_index = 0
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    return spec


def _in_play(run, limit=900):
    """Wait until the ship has arrived (the item only falls once the mission is on)."""
    g = run.game
    g.player.infinite_lives = True
    for _ in range(limit):
        if g.stage_transition is None:
            return
        run.frames(1)
    raise AssertionError("the mission never started")


def _picture(g):
    """The mission as drawn now, on a surface of its own."""
    import draw_frame
    canvas = g.game_surface
    snap = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    g.game_surface = snap
    try:
        draw_frame.draw_background(g)
        draw_frame.draw_play(g)
    finally:
        g.game_surface = canvas
    return snap


def _fall(run, g, item="tesla", t=0.0):
    g.adventure["loot_plan"] = {"id": item, "t": t}
    g.adventure["loot_clock"] = 0.0


# ---------------------------------------------------------------- the pictures
@pytest.mark.parametrize("item", si.RANDOM_IDS)
def test_every_item_has_its_animated_sprite_the_size_of_a_bird(run, item):
    cells = loot.frames(item)
    assert len(cells) == loot.FRAMES
    w, h = cells[0].get_size()
    assert all(c.get_size() == (w, h) for c in cells)
    assert 30 <= max(w, h) <= 50 and min(w, h) >= 20          # the birds of the stages 1 and 2 are 38 x 36
    assert any(c.get_bounding_rect().w > 10 for c in cells)


@pytest.mark.parametrize("item", si.RANDOM_IDS)
def test_the_sprite_has_a_transparent_background_and_really_moves(run, item):
    cells = loot.frames(item)
    corner = [c.get_at((0, 0)).a for c in cells]
    assert max(corner) < 30                                   # no background box around the item
    mid = cells[0].get_at((cells[0].get_width() // 2, cells[0].get_height() // 2))
    assert mid.a > 200
    data = {pygame.image.tobytes(c, "RGBA") for c in cells}
    assert len(data) > loot.FRAMES // 2                       # animated, not one picture repeated


@pytest.mark.parametrize("item", si.RANDOM_IDS)
def test_every_item_has_an_icon_for_the_shop(run, item):
    pic = loot.icon(item, 30, 40)
    assert pic is not None and pic.get_height() <= 30 and pic.get_width() <= 40 and max(pic.get_size()) >= 26
    assert max(loot.icon(item).get_size()) >= 90


# ---------------------------------------------------------------- what the items do
def test_no_item_no_effect(run):
    _launch(run)
    p = run.game.player
    assert p.lives == 1 and p.bullet_speed_mult == 1.0 and not p.electric_immune
    assert p.speed == pytest.approx(PLAYER_SPEED * 0.4)
    assert run.game.adventure["items"] == []


def test_the_launch_carries_the_installed_items(run):
    spec = _launch(run, credits=20000, found=("tesla", "genesis", "hyperion"), buy=("tesla", "hyperion"))
    assert spec["items"] == ["hyperion", "tesla"]
    assert run.game.adventure["items"] == ["hyperion", "tesla"]


def test_the_item_found_but_not_bought_does_not_work(run):
    spec = _launch(run, credits=20000, found=("tesla", "genesis"))
    assert spec["items"] == []
    assert run.game.player.lives == 1 and not run.game.player.electric_immune


def test_singularity_core_doubles_the_rate_of_fire(run):
    def travelled(g):
        p = g.player
        p.shots = [{"x": p.x, "y": 500.0, "resolved": False, "flame": False}]
        p.update(DT, _Keys())
        return 500.0 - p.shots[0]["y"]

    _launch(run)
    plain = travelled(run.game)
    assert plain == pytest.approx(BULLET_SPEED * DT)
    _launch(run, credits=6000, found=("singularity",), buy=("singularity",))
    assert travelled(run.game) == pytest.approx(2 * plain)


def test_singularity_core_makes_a_ship_that_hits_fire_twice_as_often(run):
    """A target 400 px ahead: the shot lands, the next one can leave. Twice as many shots in the same time."""
    def shots_in(g, seconds):
        p = g.player
        p.shots = []
        fired = 0
        for _ in range(int(seconds / DT)):
            for s in p.shots:
                if s["y"] < p.y - 400:
                    p.shots.remove(s)                            # it hit something 400 px away
            before = not p.shots
            p.update(DT, _Keys(pygame.K_SPACE), allow_shoot=True)
            if before and p.shots:
                fired += 1
        return fired

    _launch(run)
    plain = shots_in(run.game, 4.0)
    _launch(run, credits=6000, found=("singularity",), buy=("singularity",))
    boosted = shots_in(run.game, 4.0)
    assert plain >= 8 and boosted >= 1.7 * plain            # (whole frames: not exactly twice)


def test_noyau_genesis_is_one_more_life(run):
    _launch(run, credits=6000, found=("genesis",), buy=("genesis",))
    assert run.game.player.lives == 2
    assert not run.game.player.infinite_lives


def test_noyau_genesis_lets_the_ship_be_reborn_once(run):
    _launch(run, credits=6000, found=("genesis",), buy=("genesis",))
    g = run.game
    _in_play(run)
    p = g.player
    p.infinite_lives = False
    p.invulnerable = 0.0
    p.hit()
    assert p.lives == 1 and p.alive and not p.dying           # reborn
    p.invulnerable = 0.0
    p.hit()
    assert p.lives == 0 and p.dying                           # and only once


def test_reacteur_hyperion_is_forty_percent_faster(run):
    _launch(run)
    plain = run.game.player.speed
    _launch(run, credits=4000, found=("hyperion",), buy=("hyperion",))
    p = run.game.player
    assert p.speed == pytest.approx(plain * 1.4)
    x0 = p.x
    p.update(DT, _Keys(pygame.K_LEFT))
    q = Player(x0, p.y, ship_id=p.ship_id, tint="red")
    q.speed = plain
    q.update(DT, _Keys(pygame.K_LEFT))
    assert (x0 - p.x) == pytest.approx(1.4 * (x0 - q.x), rel=0.02)


def test_the_speed_bonus_rides_on_the_speed_of_the_workshop(run):
    st = _slot(credits=4000, found=("hyperion",), buy=("hyperion",))
    for sl in st["slots"]:
        sl["speed"] = 80
    ss.save_state(ss.story_path(1), st)
    g = run.game
    g.story.open_slot(1)
    g.story.map_index = 0
    g._begin_adventure(g.story._launch_selected())
    assert g.player.speed == pytest.approx(PLAYER_SPEED * 0.8 * 1.4)


def _push_into_the_wall(p, frames=120):
    for _ in range(frames):
        p.update(DT, _Keys(pygame.K_LEFT))
        if p.dying or p.just_lost_life:
            return True
    return False


def test_tesla_seal_protects_from_the_electric_wall(run):
    _launch(run)
    p = run.game.player
    p.x, p.invulnerable = 37, 0.0
    assert _push_into_the_wall(p)                             # the wall of Act 1 kills at once
    _launch(run, credits=2000, found=("tesla",), buy=("tesla",))
    p = run.game.player
    p.x, p.invulnerable = 37, 0.0
    assert not _push_into_the_wall(p, 300)
    assert p.lives == 1 and not p.dying and p.edge_timer == 0.0


def _phenix_hull(run, immune):
    p = Player(BASE_WIDTH // 2, BASE_HEIGHT - 95, ship_id="phoenix", tint="argent")
    p.sounds = run.game.sounds
    p.lives, p.infinite_lives, p.invulnerable = 1, False, 0.0
    p.electric_immune = immune
    p.phenix_gauge = 10.0
    assert p.try_activate_phenix()                            # the Phenix form is on
    p.x = 37
    return p


def test_the_electric_wall_ends_the_phenix_form_without_the_seal(run):
    p = _phenix_hull(run, immune=False)
    assert p.is_phenix
    for _ in range(10):
        p.update(DT, _Keys(pygame.K_LEFT))
    assert not p.is_phenix and p.invulnerable > 0              # the wall threw it back to the ship


def test_tesla_seal_protects_the_phenix_form_too(run):
    p = _phenix_hull(run, immune=True)
    for _ in range(60):
        p.update(DT, _Keys(pygame.K_LEFT))
    assert p.is_phenix and p.lives == 1 and not p.dying       # the wall does not end the Phenix form


# ---------------------------------------------------------------- the item that falls
def test_nothing_falls_without_a_plan(run, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.99)
    _launch(run)
    assert run.game.adventure["loot_plan"] is None
    _in_play(run)
    run.frames(120)
    assert run.game.loot is None


def test_a_lucky_mission_plans_an_item(run, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    _launch(run)
    plan = run.game.adventure["loot_plan"]
    assert plan and plan["id"] in si.RANDOM_IDS and si.DROP_DELAY[0] <= plan["t"] <= si.DROP_DELAY[1]


def test_the_planned_item_is_not_one_held(run, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    _launch(run, found=("singularity", "genesis", "hyperion"))
    assert run.game.adventure["loot_plan"]["id"] == "tesla"


def test_no_plan_when_everything_is_held(run, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    _launch(run, found=si.RANDOM_IDS)
    assert run.game.adventure["loot_plan"] is None


def test_the_gap_between_two_missions_with_an_item(run, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    g = run.game
    _launch(run)
    assert g.adventure["loot_plan"]
    for _ in range(si.MIN_GAP):                               # the next two missions carry nothing
        g._begin_adventure(g.story._launch_selected())
        assert g.adventure["loot_plan"] is None
    g._begin_adventure(g.story._launch_selected())
    assert g.adventure["loot_plan"]


def test_the_item_waits_for_its_time(run):
    _launch(run)
    _in_play(run)
    g = run.game
    _fall(run, g, "tesla", t=30.0)
    run.frames(120)
    assert g.loot is None
    g.adventure["loot_clock"] = 29.9
    run.frames(30)
    assert g.loot is not None and g.loot.item == "tesla"


def test_the_item_falls_from_the_top_to_the_bottom(run):
    _launch(run)
    _in_play(run)
    g = run.game
    _fall(run, g)
    run.frames(2)
    item = g.loot
    assert item is not None and item.y < 20                  # it comes in at the top
    ys = []
    for _ in range(60):
        run.frames(1)
        ys.append(item.y)
    assert all(b > a for a, b in zip(ys, ys[1:]))
    assert ys[-1] - ys[0] == pytest.approx(loot.FALL_SPEED * 59 / 60, rel=0.1)
    g.player.x = 40 if item.x > BASE_WIDTH / 2 else BASE_WIDTH - 40          # out of its way
    for _ in range(600):
        run.frames(1)
        if g.loot is None:
            break
    assert g.loot is None and g.adventure["loot"] is None      # it fell off the bottom: lost


def test_a_missed_item_is_not_recorded_and_stays_lootable(run):
    _launch(run)
    _in_play(run)
    g = run.game
    _fall(run, g)
    run.frames(2)
    g.player.x = 40 if g.loot.x > BASE_WIDTH / 2 else BASE_WIDTH - 40
    run.frames(500)
    g.player.infinite_lives = False
    g.player.lives = 1
    g.player.invulnerable = 0.0
    g.player.hit()
    for _ in range(600):
        run.frames(1)
        if g.adventure is None:
            break
    assert g.adventure is None
    assert si.status(g.story.state, "tesla") is None


def test_the_item_never_falls_where_the_ship_cannot_reach(run):
    for px in (40, 300, 640, 1000, 1240):
        for _ in range(50):
            x = loot.FallingItem.pick_x(px, PLAYER_SPEED * 0.4, 625)
            reach = PLAYER_SPEED * 0.4 * 0.75 * (625 - loot.START_Y) / loot.FALL_SPEED
            assert loot.MARGIN <= x <= BASE_WIDTH - loot.MARGIN
            assert abs(x - px) <= reach + loot.MARGIN


def test_touching_the_item_catches_it(run):
    _launch(run)
    _in_play(run)
    g = run.game
    _fall(run, g, "hyperion")
    run.frames(2)
    g.sounds.stop_sfx("1up", 0)
    for _ in range(700):
        g.player.x = max(40, min(BASE_WIDTH - 40, g.loot.x)) if g.loot else g.player.x
        run.frames(1)
        if g.loot is None:
            break
    assert g.adventure["loot"] == "hyperion"
    note = g.loot_note
    assert note and "Réacteur Hyperion" in note["text"] or "Hyperion" in note["text"]
    run.frames(1)                                              # the line is drawn without trouble
    run.frames(int(update_play.LOOT_NOTE_TIME * 60) + 10)
    assert g.loot_note is None


def test_the_item_is_not_caught_by_a_ship_that_is_dying(run):
    _launch(run)
    _in_play(run)
    g = run.game
    _fall(run, g)
    run.frames(2)
    g.player.dying = True
    g.loot.y = g.player.y
    g.loot.x = g.player.x
    update_play.tick_loot(g)
    assert g.adventure["loot"] is None


def test_the_end_of_the_mission_puts_the_caught_item_on_sale(run):
    _launch(run)
    _in_play(run)
    g = run.game
    g.adventure["loot"] = "genesis"
    g._end_adventure(True)
    assert si.status(g.story.state, "genesis") == "found"
    assert ss.shop_for(g.story.state)[-1][0] == "item:genesis"
    assert "Noyau Genesis" in g.story.toast
    saved = ss.load_state(ss.story_path(1))
    assert si.status(saved, "genesis") == "found"             # and it is in the save file


def test_a_lost_mission_keeps_the_caught_item_too(run):
    _launch(run)
    _in_play(run)
    g = run.game
    g.adventure["loot"] = "tesla"
    g.player.infinite_lives = False
    g.player.lives = 1
    g.player.invulnerable = 0.0
    g.player.hit()
    for _ in range(600):
        run.frames(1)
        if g.adventure is None:
            break
    assert si.status(g.story.state, "tesla") == "found"


def test_the_mission_uses_up_the_installed_items(run):
    _launch(run, credits=20000, found=("tesla", "hyperion"), buy=("tesla",))
    _in_play(run)
    g = run.game
    g._end_adventure(True)
    assert si.status(g.story.state, "tesla") == "used"
    assert si.status(g.story.state, "hyperion") == "found"    # not bought: still on the shelf
    assert si.shop(g.story.state) == ["hyperion"]
    saved = ss.load_state(ss.story_path(1))
    assert si.status(saved, "tesla") == "used"


def test_the_next_mission_has_no_installed_item_left(run):
    _launch(run, credits=2000, found=("tesla",), buy=("tesla",))
    g = run.game
    _in_play(run)
    g._end_adventure(False)
    run.frames(5)
    g.story.map_index = 0
    spec = g.story._launch_selected()
    assert spec["items"] == []
    g._begin_adventure(spec)
    assert not g.player.electric_immune


def test_leaving_a_mission_by_choice_records_nothing(run):
    """Like the points: nothing gained, nothing lost. The item bought is still installed for the next try."""
    _launch(run, credits=2000, found=("tesla",), buy=("tesla",))
    g = run.game
    _in_play(run)
    g.adventure["loot"] = "genesis"
    g._quit_to_menu()
    st = ss.load_state(ss.story_path(1))
    assert si.status(st, "tesla") == "installed"
    assert si.status(st, "genesis") is None
    assert g.story.state["items"]["got"] == {"tesla": "installed"}


def test_a_won_mission_left_during_the_fly_up_still_banks_its_loot(run):
    _launch(run, credits=2000, found=("tesla",), buy=("tesla",))
    g = run.game
    _in_play(run)
    g.adventure["loot"] = "genesis"
    g.stage_transition = "fly_up"
    g._quit_to_menu()
    st = ss.load_state(ss.story_path(1))
    assert si.status(st, "genesis") == "found" and si.status(st, "tesla") == "used"


def test_the_item_in_flight_does_not_follow_into_the_next_game(run):
    _launch(run)
    _in_play(run)
    g = run.game
    _fall(run, g)
    run.frames(3)
    assert g.loot is not None
    g._end_adventure(True)
    assert g.loot is None and g.loot_note is None
    g.menu_screen = "main"
    g.play_mode = "solo"
    g._begin_run()
    run.frames(10)
    assert g.loot is None


def test_the_installed_items_are_shown_during_the_mission(run):
    _launch(run, credits=20000, found=("tesla", "singularity"), buy=("tesla", "singularity"))
    g = run.game
    _in_play(run)
    area = pygame.Rect(BASE_WIDTH - 120, 70, 110, 40)
    g.adventure["items"] = []
    plain = pygame.image.tobytes(_picture(g).subsurface(area), "RGB")
    g.adventure["items"] = ["singularity", "tesla"]
    shown = pygame.image.tobytes(_picture(g).subsurface(area), "RGB")
    assert plain != shown


def test_the_item_and_the_line_that_tells_it_was_caught_are_drawn(run):
    _launch(run)
    _in_play(run)
    g = run.game
    g.loot_note = None
    plain = _picture(g)
    g.loot = loot.FallingItem("singularity", 300)
    g.loot.y = 300
    with_item = _picture(g)
    box = g.loot.rect().inflate(4, 4)
    assert pygame.image.tobytes(plain.subsurface(box), "RGB") != pygame.image.tobytes(with_item.subsurface(box), "RGB")
    g.loot = None
    g.loot_note = {"text": "OBJET RÉCUPÉRÉ : TEST", "t": 2.0}
    with_note = _picture(g)
    line = pygame.Rect(BASE_WIDTH // 2 - 250, 105, 500, 40)
    assert pygame.image.tobytes(plain.subsurface(line), "RGB") != pygame.image.tobytes(with_note.subsurface(line), "RGB")


# ---------------------------------------------------------------- the hangar
def _hangar(found=(), credits=0, buy=()):
    _slot(credits=credits, found=found, buy=buy)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "hangar"
    hub.zone = "shop"
    return hub


def _focus(hub, sid):
    hub.shop_index = [r[0] for r in hub.shop_rows()].index(sid)


def test_the_hangar_lists_nothing_of_items_not_caught():
    hub = _hangar()
    assert all(not r[0].startswith("item:") for r in hub.shop_rows())


def test_the_hangar_sells_a_caught_item_once():
    hub = _hangar(found=("hyperion",), credits=4500)
    _focus(hub, "item:hyperion")
    assert hub.confirm() is None
    assert hub.state["credits"] == 500
    assert si.status(hub.state, "hyperion") == "installed"
    assert hub.take_sounds() == ["1up"]
    hub.confirm()                                              # a second press buys nothing more
    assert hub.state["credits"] == 500 and hub.take_sounds() == []
    assert si.status(ss.load_state(ss.story_path(1)), "hyperion") == "installed"     # saved


def test_the_hangar_refuses_an_item_that_is_too_dear():
    hub = _hangar(found=("singularity",), credits=5999)
    _focus(hub, "item:singularity")
    hub.confirm()
    assert hub.state["credits"] == 5999 and si.status(hub.state, "singularity") == "found"
    assert hub.take_sounds() == []


def test_an_installed_item_shows_installed_instead_of_its_price():
    hub = _hangar(found=("tesla",), credits=2000, buy=("tesla",))
    assert hub._shop_extra("item:tesla", 2000, False) == "INSTALLÉ" or hub._shop_extra("item:tesla", 2000, False) == "INSTALLED"
    hub2 = _hangar(found=("tesla",), credits=0)
    assert hub2._shop_extra("item:tesla", 2000, False) == "2000 PTS"


@pytest.mark.parametrize("credits", [0, 9000])
@pytest.mark.parametrize("focus", ["speed_60", "item:genesis", "item:tesla"])
def test_the_hangar_draws_the_items(run, credits, focus):
    g = run.game
    hub = _hangar(found=("singularity", "genesis", "hyperion", "tesla"), credits=credits)
    g.story = hub
    g.menu_screen = "story_hub"
    _focus(hub, focus)
    run.frames(3)
    assert hub.shop_index == [r[0] for r in hub.shop_rows()].index(focus)


def _hub_picture(g, hub):
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    hub.draw(surf, g.font, g.medium_font, g.font)
    return surf


def test_the_shop_row_of_an_item_shows_its_picture_and_the_description_under_the_list(run):
    g = run.game
    hub = _hangar(found=("tesla",), credits=2000)
    _focus(hub, "item:tesla")
    box = pygame.Rect(70, 308, BASE_WIDTH - 140, 328)
    focused = _hub_picture(g, hub)
    desc = pygame.Rect(box.x + 20, box.bottom - 34, box.w - 40, 24)             # the line under the rows
    hub.zone = "slots"                                                         # the cursor leaves the shop
    away = _hub_picture(g, hub)
    assert pygame.image.tobytes(focused.subsurface(desc), "RGB") != pygame.image.tobytes(away.subsurface(desc), "RGB")
    # the picture of the item is in its row: the area left of the name, in the last row listed
    rows = hub.shop_rows()
    y = box.y + 46 + 40 * (len(rows) - 1)
    icon_area = pygame.Rect(box.x + 12 + 30, y, 40, 38)
    colours = {tuple(away.get_at((x, yy))[:3]) for x in range(icon_area.left, icon_area.right)
               for yy in range(icon_area.top, icon_area.bottom)}
    assert len(colours) > 8                                   # a picture, not the plain panel


def test_a_workshop_row_that_is_not_an_item_has_no_description(run):
    g = run.game
    hub = _hangar(found=("tesla",), credits=2000)
    box = pygame.Rect(70, 308, BASE_WIDTH - 140, 328)
    desc = pygame.Rect(box.x + 20, box.bottom - 34, box.w - 40, 24)
    _focus(hub, "speed_60")
    plain = _hub_picture(g, hub)
    colours = {tuple(plain.get_at((x, y))[:3]) for x in range(desc.left, desc.right, 3)
               for y in range(desc.top, desc.bottom, 3)}
    assert len(colours) == 1                                  # the plain panel, no text


def test_every_row_of_a_long_list_can_be_reached_and_drawn(run):
    g = run.game
    hub = _hangar(found=si.RANDOM_IDS, credits=0)
    g.story = hub
    g.menu_screen = "story_hub"
    rows = hub.shop_rows()
    assert len(rows) > 6
    for i in range(len(rows)):
        hub.shop_index = i
        run.frames(2)


def test_the_item_news_is_on_the_map_after_the_mission(run):
    g = run.game
    _launch(run)
    _in_play(run)
    g.adventure["loot"] = "tesla"
    g._end_adventure(True)
    assert "Tesla Seal" in g.story.toast and g.story.toast.count("PTS") >= 1


def test_the_texts_exist_in_french_and_english():
    from i18n import T
    for item in si.RANDOM_IDS:
        for part in ("name", "effect", "desc"):
            entry = T["item_%s_%s" % (item, part)]
            assert entry["fr"] and entry["en"]
    assert T["item_singularity_desc"]["fr"] == "Libère la puissance destructrice des armes du vaisseau."
    assert T["item_genesis_desc"]["fr"] == "Permet au vaisseau de renaître une fois après sa destruction."
    assert T["item_hyperion_desc"]["fr"] == "Déchaîne une poussée énergétique qui propulse le vaisseau à une vitesse extrême."
    assert T["item_tesla_desc"]["fr"] == "Protège intégralement le vaisseau contre les décharges électriques."
    assert T["item_singularity_effect"]["fr"] == "Cadence de tir ×2"
    assert T["item_genesis_effect"]["fr"] == "Vie supplémentaire"
    assert T["item_hyperion_effect"]["fr"] == "Vitesse +40 %"
    assert T["item_tesla_effect"]["fr"] == "Immunité électrique"
    assert [T["item_%s_name" % i]["fr"] for i in si.RANDOM_IDS] == [
        "Singularity Core", "Noyau Genesis", "Réacteur Hyperion", "Tesla Seal"]


# ---------------------------------------------------------------- the paint missions
def _launch_paint(run, **kw):
    g = run.game
    _slot(**kw)
    g.story.open_slot(1)
    g.story.cheat_unlock = True                                # any mission can be flown
    g.story.map_index = [m["id"] for m in g.story.missions()].index("paint_1")
    spec = g.story._launch_selected()
    assert spec and spec.get("invaders")
    g._begin_adventure(spec)
    g.input_grace = 0.0
    return spec


def test_a_paint_mission_never_carries_an_item(run, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)         # the luckiest dice
    _launch_paint(run)
    assert run.game.adventure["loot_plan"] is None
    _in_play(run)
    run.frames(120)
    assert run.game.loot is None


def test_a_paint_mission_does_not_count_in_the_gap_between_drops(run, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    g = run.game
    _launch(run)
    assert g.adventure["loot_plan"]                            # a mission with an item...
    before = dict(g.story.state["items"])
    for _ in range(5):
        g._begin_adventure(_launch_paint_spec(g))
    assert g.story.state["items"]["since"] == before["since"]   # ...the paint missions do not use up the gap


def _launch_paint_spec(g):
    g.story.cheat_unlock = True
    g.story.map_index = [m["id"] for m in g.story.missions()].index("paint_1")
    return g.story._launch_selected()


def test_the_other_missions_still_carry_items_after_a_paint_one(run, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    g = run.game
    _launch_paint(run)
    g.story.cheat_unlock = False
    g.story.map_index = 0
    g._begin_adventure(g.story._launch_selected())
    assert g.adventure["loot_plan"]


@pytest.mark.parametrize("item", si.RANDOM_IDS)
def test_an_item_installed_works_in_a_paint_mission(run, item):
    spec = _launch_paint(run, credits=20000, found=(item,), buy=(item,))
    g = run.game
    assert spec["items"] == [item] and g.adventure["items"] == [item]
    fx = si.effects([item])
    p = g.player
    assert p.bullet_speed_mult == fx["fire_mult"] and p.electric_immune == fx["electric_immune"]
    assert p.lives == 1 + fx["extra_lives"]
    assert p.speed == pytest.approx(PLAYER_SPEED * 0.4 * fx["speed_mult"])


def test_a_paint_mission_uses_the_installed_items_up(run):
    _launch_paint(run, credits=20000, found=("tesla", "hyperion"), buy=("tesla",))
    g = run.game
    _in_play(run)
    g._end_adventure(True)
    assert si.status(g.story.state, "tesla") == "used"
    assert si.status(g.story.state, "hyperion") == "found"
