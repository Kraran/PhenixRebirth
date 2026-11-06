"""The escort modules in the Adventure (step 4c): their pieces won by the landings and the raids, the bonuses of the asteroid,
the workshop rows (assemble, buy again), the save, and the pilot's modules flying with the ship and lost when destroyed."""

import pygame

import story_state as ss
from i18n import t
import story_vn
from test_smoke import run  # noqa: F401,F811  (fixture)

PIECES = {"lander_deimos": "m1_lander", "raid_deimos": "m1_raid", "lander_europa": "m2_lander",
          "raid_europa": "m2_raid", "lander_rock": "bonus_cheap", "raid_rock": "bonus_armour"}


def _st(parts=(), built=0, alive=0, credits=20000):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["module_parts"] = list(parts)
    st["modules_built"] = built
    st["modules"] = alive
    st["credits"] = credits
    return st


def _row(st, sid):
    return next((r for r in ss.shop_for(st) if r[0] == sid), None)


# ---------------------------------------------------------------- the pieces
def test_each_landing_and_raid_of_deimos_europa_and_the_asteroid_gives_its_piece_at_the_first_win():
    assert ss.MODULE_PARTS == PIECES
    for mid, part in PIECES.items():
        st = _st()
        st["flags"][ss.mission_by_id(mid)["need"]] = True
        res = ss.record_result(st, mid, 0, False)
        assert "part" not in res and ss.module_parts(st) == []          # (a failure gives nothing)
        res = ss.record_result(st, mid, 1500, True)
        assert res["part"] == part and ss.module_parts(st) == [part]
        st["flags"][ss.ENDING_DONE] = True
        res = ss.record_result(st, mid, 1500, True)
        assert "part" not in res and ss.module_parts(st) == [part]      # (once)
    for mid in ("lander_titan", "raid_titan", "lander_triton", "raid_triton"):
        st = _st()
        assert "part" not in ss.record_result(st, mid, 1500, True) and ss.module_parts(st) == []


def test_the_toast_says_what_was_won(run):
    g = run.game
    st = _st(credits=0)
    st["flags"]["dome_s2"] = True
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.apply_result("raid_rock", 2000, True)
    assert ss.module_parts(g.story.state) == ["bonus_armour"]
    assert g.story.toast.endswith(t("story_part_bonus_armour")) and g.story.toast_kind == "reward"
    assert ss.module_parts(ss.load_state(ss.story_path(1))) == ["bonus_armour"]        # (written)


# ---------------------------------------------------------------- the workshop
def test_the_row_of_a_module_appears_with_its_first_piece_and_opens_with_the_second():
    st = _st()
    assert ss.module_status(st, 1) == "hidden" and _row(st, "module_1") is None
    st["module_parts"] = ["m1_raid"]
    assert ss.module_status(st, 1) == "parts" and ss.upgrade_note(st, "module_1") == "story_module_parts"
    assert _row(st, "module_1")[1] == "story_shop_module1" and not ss.module_buyable(st, "module_1")
    assert not ss.buy(st, "module_1")
    st["module_parts"] = ["m1_raid", "m1_lander"]
    assert ss.module_status(st, 1) == "assemble" and ss.upgrade_note(st, "module_1") is None
    assert ss.module_buyable(st, "module_1")


def test_module_2_waits_for_module_1():
    st = _st(parts=("m2_lander", "m2_raid"))
    assert ss.module_status(st, 2) == "need_prev" and ss.upgrade_note(st, "module_2") == "story_need_prev"
    assert not ss.buy(st, "module_2") and _row(st, "module_1") is None
    st = _st(parts=("m1_lander", "m1_raid", "m2_lander", "m2_raid"), built=1, alive=1)
    assert ss.module_status(st, 2) == "assemble" and ss.buy(st, "module_2")
    assert ss.modules_built(st) == 2 and ss.modules_alive(st) == 2


def test_assembling_costs_3000_then_5000_and_a_module_destroyed_half():
    st = _st(parts=("m1_lander", "m1_raid", "m2_lander", "m2_raid"), credits=10000)
    assert ss.module_price(st, 1) == 3000 and ss.module_price(st, 2) == 5000
    assert _row(st, "module_1")[2] == 3000
    assert ss.buy(st, "module_1") and st["credits"] == 7000
    assert ss.buy(st, "module_2") and st["credits"] == 2000
    assert ss.module_status(st, 1) == ss.module_status(st, 2) == "ready"
    assert ss.upgrade_note(st, "module_1") == "story_module_ready"
    assert not ss.buy(st, "module_1")                                  # (in working order: nothing to buy)
    assert ss.lose_module(st) and ss.modules_alive(st) == 1
    assert ss.module_status(st, 2) == "rebuy" and ss.module_price(st, 2) == 2500
    assert _row(st, "module_2")[1] == "story_shop_module2_rebuy"
    assert not ss.buy(st, "module_2")                                  # (2000 credits: not enough)
    st["credits"] = 2500
    assert ss.buy(st, "module_2") and st["credits"] == 0 and ss.modules_alive(st) == 2


def test_both_destroyed_are_bought_again_in_order():
    st = _st(parts=("m1_lander", "m1_raid", "m2_lander", "m2_raid"), built=2, alive=0)
    assert ss.module_status(st, 1) == "rebuy" and ss.module_status(st, 2) == "need_prev"
    assert not ss.buy(st, "module_2") and ss.buy(st, "module_1") and st["credits"] == 20000 - 1500
    assert ss.module_status(st, 2) == "rebuy" and ss.buy(st, "module_2") and st["credits"] == 20000 - 1500 - 2500
    assert not ss.lose_module(_st())                                    # (none to lose)


def test_the_plans_take_40_percent_off_everything():
    st = _st(parts=("m1_lander", "m1_raid", "m2_lander", "m2_raid", "bonus_cheap"))
    assert ss.module_price(st, 1) == 1800 and ss.module_price(st, 2) == 3000
    st["modules_built"] = 2
    assert ss.module_price(st, 1) == 900 and ss.module_price(st, 2) == 1500


def test_the_romance_discount_applies_on_top():
    st = _st(parts=("m1_lander", "m1_raid", "bonus_cheap"))
    price = story_vn.sale_price(st, 1800)
    assert _row(st, "module_1")[2] == price
    assert ss.buy(st, "module_1") and st["credits"] == 20000 - price


def test_the_modules_in_service_go_to_the_end_of_the_workshop():
    st = _st(parts=("m1_lander", "m1_raid", "m2_raid"), built=1, alive=1)
    ids = [r[0] for r in ss.shop_for(st)]
    assert ids[-1] == "module_1" and ids.index("module_2") < ids.index("module_1")


def test_the_save_keeps_the_modules_and_cleans_bad_values(tmp_path):
    st = _st(parts=("m1_lander", "bonus_armour"), built=2, alive=1)
    path = tmp_path / "s.json"
    ss.save_state(str(path), st)
    back = ss.load_state(str(path))
    assert back["module_parts"] == ["m1_lander", "bonus_armour"] and back["modules_built"] == 2 and back["modules"] == 1
    bad = ss.migrate_state({"module_parts": ["m1_lander", "junk", 3, "m1_lander"], "modules_built": 9, "modules": 7})
    assert bad["module_parts"] == ["m1_lander"] and bad["modules_built"] == 2 and bad["modules"] == 2
    old = ss.migrate_state({"credits": 10})
    assert old["module_parts"] == [] and old["modules_built"] == 0 and old["modules"] == 0


def test_the_workshop_draws_the_rows_and_the_line_under_them(run):
    g = run.game
    st = _st(parts=("m1_lander", "m1_raid", "m2_raid", "bonus_armour", "bonus_cheap"), credits=500)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.pane = "hangar"
    g.story.zone = "shop"
    rows = g.story.shop_rows()
    g.story.shop_index = [r[0] for r in rows].index("module_2")
    assert g.story._shop_extra("module_2", rows[g.story.shop_index][2], True) == t("story_module_parts").format(n=1, of=2)
    desc = g.story._module_desc()
    assert t("story_desc_module_armour") in desc and t("story_desc_module_cheap") in desc
    surf = pygame.Surface((1280, 720))
    g.story._draw_shop(surf, g.font)
    g.story.shop_index = [r[0] for r in rows].index("module_1")
    g.story._draw_shop(surf, g.font)


# ---------------------------------------------------------------- in the missions
def test_the_modules_in_service_fly_in_the_missions_that_count():
    st = _st(parts=("bonus_armour",), built=2, alive=1)
    assert ss.module_spec(st, ss.mission_by_id("ch1_sortie")) == {"count": 1, "armour": 2, "owned": True}
    assert ss.module_spec(st, ss.mission_by_id("test_guardians")) is None          # (a test: nothing won, nothing lost)
    assert ss.module_spec(st, ss.mission_by_id("test_modules")) is None            # (its own, from its menu)
    assert ss.module_spec(_st(built=1, alive=0), ss.mission_by_id("ch1_sortie")) is None
    assert ss.module_spec(_st(built=2, alive=2), ss.mission_by_id("ch1_sortie"))["armour"] == 1


def _fly(run, mission_id, st):
    g = run.game
    ss.save_state(ss.story_path(1), st)
    g.menu_screen = "story_hub"
    g.story.open_slot(1)
    g.story.screen, g.story.pane = "hub", "map"
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mission_id)
    spec = g.story._launch_selected()
    g._request_adventure(dict(spec, first_help_read=True))
    return g, spec


def test_a_module_destroyed_in_a_mission_is_lost_at_once(run):
    g, spec = _fly(run, "ch1_sortie", _st(built=2, alive=2))
    assert spec["modules"] == {"count": 2, "armour": 1, "owned": True}
    assert g.started and g.gyro is not None and g.gyro.owned and len(g.gyro.modules) == 2
    run.frames(10)
    g.gyro.hit(g, g.gyro.modules[1], "crash")
    assert ss.modules_alive(g.story.state) == 1 and ss.modules_built(g.story.state) == 2
    assert ss.load_state(ss.story_path(1))["modules"] == 1                          # (written at once)
    run.frames(5)


def test_the_test_of_the_modules_never_touches_the_pilots_modules(run):
    g, spec = _fly(run, "test_modules", _st(built=2, alive=1))
    g.story.screen = "hub"
    assert spec["modules"] == {"count": 2, "armour": 1}
    assert g.gyro is not None and not g.gyro.owned
    run.frames(5)
    g.gyro.hit(g, g.gyro.modules[0], "crash")
    assert ss.modules_alive(g.story.state) == 1


def test_no_modules_in_the_lander_nor_the_scramble(run):
    st = _st(built=2, alive=2)
    st["flags"]["dome_s2"] = True
    g, spec = _fly(run, "lander_deimos", st)
    assert spec["modules"]["owned"] and g.gyro is None


# ---------------------------------------------------------------- the pictures of the workshop
def _hangar(run, parts=(), built=0, alive=0, launcher=False):
    g = run.game
    st = _st(parts=parts, built=built, alive=alive)
    if launcher:
        st["flags"][ss.ANTIMATTER_FLAG] = True
        st["flags"][ss.LAUNCHER_FLAG] = True
        st["missiles"] = 1
    ss.save_state(ss.story_path(1), st)
    hub = g.story
    hub.open_slot(1)
    hub.screen, hub.pane, hub.zone = "hub", "hangar", "shop"
    return g, hub


def _spy_icons(monkeypatch):
    import gyro
    calls = []
    real = gyro.draw_icon

    def spy(surface, hull, cx, cy, size, t, halves=(True, True), split=0.0, dim=False):
        calls.append({"hull": hull, "cx": cx, "cy": cy, "size": size, "halves": tuple(halves), "split": split, "dim": dim})
        return real(surface, hull, cx, cy, size, t, halves, split, dim)

    monkeypatch.setattr(gyro, "draw_icon", spy)
    return calls


def test_the_icon_draws_the_halves_asked_for():
    import gyro
    surf = pygame.Surface((100, 100), pygame.SRCALPHA)
    gyro.draw_icon(surf, "shield", 50, 50, 40, 0.0, halves=(True, False))
    assert any(surf.get_at((x, 50)).a for x in range(30, 50)) and not any(surf.get_at((x, y)).a for x in range(51, 100)
                                                                          for y in range(100))
    surf.fill((0, 0, 0, 0))
    gyro.draw_icon(surf, "shield", 50, 50, 40, 0.0, halves=(False, True), split=6)
    assert not any(surf.get_at((x, y)).a for x in range(0, 56) for y in range(100))
    assert gyro.frame_at(0.0) == 0 and gyro.frame_at(180.0 / gyro.SPIN * 0.5) == gyro.FRAMES // 2


def test_the_hangar_shows_the_modules_in_service_beside_the_hull(run, monkeypatch):
    for alive, want in ((0, 0), (1, 1), (2, 2)):
        g, hub = _hangar(run, built=2, alive=alive)
        hub._ensure_art()                                                 # (the portraits)
        calls = _spy_icons(monkeypatch)
        hub._draw_hangar(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
        ship = [c for c in calls if c["size"] > 40]
        assert len(ship) == want and all(c["halves"] == (True, True) and not c["dim"] for c in ship)
        if want:
            assert ship[0]["cx"] < 640 and (want == 1 or ship[1]["cx"] > ship[0]["cx"])        # the first one on the left


def test_the_rows_of_the_modules_show_their_pieces(run, monkeypatch):
    cases = [((("m1_lander",), 0, 0), (True, False), False, 4),
             ((("m1_raid",), 0, 0), (False, True), False, 4),
             ((("m1_lander", "m1_raid"), 0, 0), (True, True), False, 4),       # two halves, apart
             ((("m1_lander", "m1_raid"), 1, 1), (True, True), False, 0),       # assembled: whole
             ((("m1_lander", "m1_raid"), 1, 0), (True, True), True, 0)]        # destroyed: whole, dimmed
    for (parts, built, alive), halves, dim, split in cases:
        g, hub = _hangar(run, parts=parts, built=built, alive=alive)
        calls = _spy_icons(monkeypatch)
        hub._draw_shop(pygame.Surface((1280, 720)), g.font)
        row = [c for c in calls if c["size"] <= 40]
        assert len(row) == 1 and row[0]["halves"] == halves and row[0]["dim"] == dim and row[0]["split"] == split, parts


def test_the_row_of_the_missile_shows_the_missile(run, monkeypatch):
    import spacewar
    seen = []
    real = spacewar.draw_torpedo
    monkeypatch.setattr(spacewar, "draw_torpedo", lambda *a, **k: seen.append(a) or real(*a, **k))
    g, hub = _hangar(run)
    hub._draw_shop(pygame.Surface((1280, 720)), g.font)
    assert not seen                                                       # (no missile row before it is unlocked)
    g, hub = _hangar(run, launcher=True)
    hub._draw_shop(pygame.Surface((1280, 720)), g.font)
    assert len(seen) == 1 and seen[0][5] == (255, 120, 110)                # one picture, the nose in the red of the Shield
