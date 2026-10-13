"""BONUS missions of the Adventure: the two-dimensional impulse reactor (waves of birds like Namco's Galaga; the reactor
falls once, goes on sale in the hangar for one hull and lets it fly up and down the lower third of the screen)."""
import math
import os

import pygame
import pytest

import galaga
import story_items as si
import story_state as ss
from galaga import GalagaBird, GalagaFormation, Path, path_for
from player import Player
from settings import BASE_HEIGHT, BASE_WIDTH, PLAYER_VERTICAL_BOTTOM, PLAYER_VERTICAL_TOP, PLAYER_SPEED
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

DT = 1 / 60


class _Keys:
    def __init__(self, *down):
        self.down = set(down)

    def __getitem__(self, k):
        return k in self.down


@pytest.fixture(scope="module", autouse=True)
def _screen():
    """Sprites need an initialised display (one for the whole file; the tests that need a Game ask for `run`)."""
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


def _state(got=None, **flags):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["flags"].update(flags)
    st["items"]["got"].update(got or {})
    return st


SHIELD_ON = {"reactor_shield": si.INSTALLED}
PHENIX_ON = {"reactor_phenix": si.INSTALLED}


def _launch(run, mission="bonus_2d", got=None, cheat=False, **flags):
    g = run.game
    st = _state(got, **flags)
    if mission == "bonus_2d_phenix":
        st["flags"]["phenix_owned"] = True
        st["slots"][1]["owned"] = True
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.cheat_unlock = cheat
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mission)
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


def _step(form, seconds, player_x=640.0):
    for _ in range(int(seconds / DT)):
        form.update(DT, player_x)


def _until(cond, form, step=DT, limit=120.0, player_x=640.0):
    """Advance the formation until `cond()` is true; fail (instead of hanging) after `limit` seconds."""
    t = 0.0
    while not cond():
        form.update(step, player_x)
        t += step
        assert t < limit, "the formation never got there"


def _alive(form):
    return [e for e in form.enemies if e.alive and not e.dying]


def _kill(form, birds):
    for b in birds:
        b.kill(flash=False)


# ------------------------------------------------------------------ the mission data
def test_the_bonus_mission_follows_the_last_hunt_and_waits_for_the_dark_gargoyles():
    m = ss.mission_by_id("bonus_2d")
    assert m["need"] == "bestiary_s4" and "bestiary_s4" in ss.mission_by_id("best_s4")["unlock"]
    assert m["secret"] and m["galaga"] and m["reactor"] == "shield" and m["ship"] == "shield"
    assert not m.get("once") and not m.get("unlock")           # nothing is given outright any more: the reactor falls
    assert not m.get("acts")                                 # on the map of every act until the reactor is caught
    assert ss.GALAGA_STAGE == 6 and (m["stage"] - 1) // 5 == 1      # level 2 (x1.1 speed)
    ids = [x["id"] for x in ss.MISSIONS]
    assert ids[ids.index("best_s4") + 1] == "bonus_2d"
    assert ids[ids.index("bonus_2d") + 1] == "bonus_2d_phenix"


def test_the_phenix_version_comes_with_the_phenix_and_the_birds_shoot_more():
    m = ss.mission_by_id("bonus_2d_phenix")
    assert m["need"] == "phenix_owned" and m["reactor"] == "phoenix" and m["ship"] == "phoenix"
    assert m["galaga"] and m["secret"] and m["stage"] == ss.GALAGA_STAGE
    assert m["fire_mult"] == ss.PHENIX_FIRE_MULT > 1.0
    assert not ss.mission_by_id("bonus_2d").get("fire_mult")
    assert ss.mission_by_id("phenix_5")["unlock"].count("phenix_owned") == 1
    assert ss.mission_by_id("bonus_2d_phenix")["title"] != ss.mission_by_id("bonus_2d")["title"]


def _ids(st, **kw):
    return [m["id"] for m in ss.visible_missions(st, **kw)]


def test_the_mission_is_hidden_until_it_is_unlocked_then_stays_through_the_acts():
    st = _state()
    assert "bonus_2d" not in _ids(st)
    st["flags"]["bestiary_s4"] = True
    assert "bonus_2d" in _ids(st)
    st["act"] = 2
    assert "bonus_2d" in _ids(st)                                                # it stays between the acts
    st["cleared"].append("bonus_2d")                                             # won, but the reactor was missed: still there
    assert "bonus_2d" in _ids(st)
    st["items"]["got"]["reactor_shield"] = si.FOUND                              # caught: no clutter in the later acts
    assert "bonus_2d" not in _ids(st)
    st["act"] = 1
    assert "bonus_2d" in _ids(st)                                                # (it stays listed as done in its own act)
    assert "bonus_2d" in _ids(_state(), cheat=True)                              # the UNLK cheat lists all


def test_the_phenix_mission_appears_with_the_phenix_and_goes_when_its_reactor_is_caught():
    st = _state(bestiary_s4=True)
    assert "bonus_2d_phenix" not in _ids(st)
    st["flags"]["phenix_owned"] = True
    st["act"] = 2
    assert "bonus_2d_phenix" in _ids(st) and "bonus_2d" in _ids(st)              # the two are independent
    st["items"]["got"]["reactor_phenix"] = si.FOUND
    assert "bonus_2d_phenix" in _ids(st)                                         # it is in its own act (2): listed as done
    st["act"] = 3
    assert "bonus_2d_phenix" not in _ids(st)


def test_the_act_2_cheat_leaves_the_bonus_missions_to_play():
    st = _state()
    ss.jump_to_act2(st)                                                          # "every mission of Act 1 is won"
    assert not ss.flag(st, "vertical_thrust") and ss.loadout(st)["vertical"] is False
    assert "bonus_2d" in _ids(st)                                                # no reactor yet: it is still to do
    assert ss.mission_playable(st, ss.mission_by_id("bonus_2d"))


def test_winning_the_last_hunt_opens_the_bonus_mission_once():
    st = _state(bestiary_s3=True)
    res = ss.record_result(st, "best_s4", 100, True)
    assert res["opened"] == ["bonus_2d"]
    assert ss.mission_playable(st, ss.mission_by_id("bonus_2d"))
    again = ss.record_result(st, "best_s4", 100, True)                          # the hunt is flown again: nothing new
    assert again["opened"] == []


def test_the_waves_alone_give_nothing_and_the_mission_is_offered_again():
    st = _state(bestiary_s4=True)
    m = ss.mission_by_id("bonus_2d")
    res = ss.record_result(st, "bonus_2d", 500, True)                           # the waves are beaten, the reactor missed
    assert res["loot"] is None and si.reactor_status(st, "shield") is None
    assert st["credits"] == 500 and "bonus_2d" in st["cleared"]
    assert not ss.flag(st, "vertical_thrust") and ss.loadout(st)["vertical"] is False
    assert ss.mission_playable(st, m) and not ss.mission_done(st, m)            # offered again
    assert ss.record_result(st, "bonus_2d", 400, True)["first"] is False


def test_catching_the_reactor_puts_it_on_sale_and_ends_the_offer():
    st = _state(bestiary_s4=True)
    m = ss.mission_by_id("bonus_2d")
    res = ss.record_result(st, "bonus_2d", 500, True, loot="reactor_shield")
    assert res["loot"] == "reactor_shield" and si.reactor_status(st, "shield") == si.FOUND
    assert {"key": "story_log_reactor_shield"} in st["log"]
    assert ss.loadout(st)["vertical"] is False                                  # on sale, not installed yet
    assert ss.mission_done(st, m) and not ss.mission_playable(st, m)
    assert "bonus_2d" in _ids(st)                                               # listed as done in Act 1
    assert ss.mission_playable(st, m, cheat=True)


def test_the_reactor_is_kept_even_when_the_mission_is_lost():
    st = _state(bestiary_s4=True)
    res = ss.record_result(st, "bonus_2d", 0, False, loot="reactor_shield")
    assert res["loot"] == "reactor_shield" and si.reactor_status(st, "shield") == si.FOUND


def test_a_lost_bonus_mission_gives_nothing_and_can_be_tried_again():
    st = _state(bestiary_s4=True)
    st["credits"] = 1000
    res = ss.record_result(st, "bonus_2d", 300, False)
    assert res["loot"] is None and ss.loadout(st)["vertical"] is False
    assert st["credits"] < 1000 and "bonus_2d" not in st["cleared"]
    assert ss.mission_playable(st, ss.mission_by_id("bonus_2d"))


def test_the_hangar_loadout_carries_the_reactor_of_the_hull_flown_only():
    assert ss.loadout(_state())["vertical"] is False
    assert ss.loadout(_state(got=SHIELD_ON))["vertical"] is True
    assert ss.loadout(_state(got={"reactor_shield": si.FOUND}))["vertical"] is False        # on sale is not installed
    st = _state(got=PHENIX_ON)                                                   # the Phenix reactor does not help the Shield
    assert ss.loadout(st)["vertical"] is False
    st["slots"][1]["owned"] = True
    st["selected_slot"] = 1
    assert ss.loadout(st)["ship_id"] == "phoenix" and ss.loadout(st)["vertical"] is True
    assert ss.loadout(_state(got=SHIELD_ON), force_ship="phoenix")["vertical"] is True     # (Phenix not owned: Shield)


def test_the_launch_spec_and_the_texts(run, french):
    spec = _launch(run, bestiary_s4=True)
    assert spec["galaga"] is True and spec["stage"] == 6 and spec["id"] == "bonus_2d"
    assert spec["hud_title"] == "story_m_bonus2d_hud" and spec["reactor"] == "shield" and spec["ship"] == "shield"
    assert "fire_mult" not in spec
    from i18n import set_lang, t
    for lang in ("fr", "en"):
        set_lang(lang)
        for key in ("story_m_bonus2d", "story_m_bonus2d_hud", "story_m_bonus2d_b", "story_log_bonus2d",
                    "story_m_bonus2dp", "story_m_bonus2dp_hud", "story_m_bonus2dp_b", "story_log_bonus2dp",
                    "story_log_reactor_shield", "story_log_reactor_phenix",
                    "item_reactor_shield_name", "item_reactor_shield_effect", "item_reactor_shield_desc",
                    "item_reactor_phenix_name", "item_reactor_phenix_effect", "item_reactor_phenix_desc",
                    "story_bonus_open", "story_galaga_hud"):
            assert t(key) != key, (lang, key)
    set_lang("fr")
    assert t("story_m_bonus2d") == "BONUS : le réacteur à impulsion bidimensionnelle (Shield)"
    assert t("story_m_bonus2dp") == "BONUS : le réacteur à impulsion bidimensionnelle (Phenix)"
    assert "Shield" in t("item_reactor_shield_name") and "Shield" in t("item_reactor_shield_desc")
    assert "Phenix" in t("item_reactor_phenix_name") and "Phenix" in t("item_reactor_phenix_desc")
    assert "Phenix" in t("story_m_bonus2dp_hud") and "Shield" in t("story_m_bonus2d_hud")
    set_lang("en")
    assert t("story_m_bonus2d") == "BONUS: the two-dimensional impulse reactor (Shield)"
    assert t("story_m_bonus2dp") == "BONUS: the two-dimensional impulse reactor (Phenix)"
    assert "Shield" in t("item_reactor_shield_name") and "Phenix" in t("item_reactor_phenix_name")


def test_the_phenix_launch_spec_flies_the_phenix_with_more_enemy_fire(run):
    spec = _launch(run, mission="bonus_2d_phenix", bestiary_s4=True)
    g = run.game
    assert spec["id"] == "bonus_2d_phenix" and spec["reactor"] == "phoenix" and spec["ship"] == "phoenix"
    assert spec["fire_mult"] == ss.PHENIX_FIRE_MULT and spec["galaga"] is True
    assert spec["hud_title"] == "story_m_bonus2dp_hud"
    assert g.ship_id == "phoenix" and g.formation.fire_mult == ss.PHENIX_FIRE_MULT
    assert g.adventure["loot_plan"]["id"] == "reactor_phenix"


def test_the_map_lists_the_mission_and_the_toasts_tell_what_happened(run):
    g = run.game
    st = _state(bestiary_s3=True)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    from i18n import t
    g.story.apply_result("best_s4", 100, True)
    assert g.story.toast == t("story_bonus_open")
    assert "bonus_2d" in [m["id"] for m in g.story.missions()]
    g.story.apply_result("bonus_2d", 100, True, loot="reactor_shield")
    assert t("item_reactor_shield_name") in g.story.toast
    g.story.map_index = [m["id"] for m in g.story.missions()].index("bonus_2d")
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    g.story._draw_map(surf, g.font, g.medium_font, g.font)                       # a long title must not break the map
    if os.environ.get("PHENIX_SHOT"):
        pygame.image.save(surf, os.environ["PHENIX_SHOT"])


# ------------------------------------------------------------------ the ship flies up and down
def _ship(vertical=True, speed_pct=None):
    p = Player(640, BASE_HEIGHT - 95, ship_id="shield")
    p.input_scheme = "solo"
    if vertical:
        p.vertical_range = (PLAYER_VERTICAL_TOP, PLAYER_VERTICAL_BOTTOM)
    return p


def test_the_vertical_range_is_the_lower_third_of_the_screen():
    assert PLAYER_VERTICAL_TOP > BASE_HEIGHT * 2 // 3
    assert PLAYER_VERTICAL_BOTTOM < BASE_HEIGHT
    assert PLAYER_VERTICAL_TOP < BASE_HEIGHT - 95 <= PLAYER_VERTICAL_BOTTOM      # the usual place is inside it


def test_without_the_reactor_the_ship_stays_on_its_line():
    p = _ship(vertical=False)
    y0 = p.y
    for _ in range(30):
        p.update(DT, _Keys(pygame.K_UP))
    assert p.y == y0


def test_the_long_jets_burn_while_the_reactor_climbs():
    """Going up with the reactor uses the long jets of the flight up a stage (`engine_burst`), and they die back after."""
    p = _ship()
    p.speed = 100.0                                                            # slow, so that the top of the range is far
    p.y = float(PLAYER_VERTICAL_BOTTOM)
    assert p.engine_burst == 0.0 and p.climbing is False
    for _ in range(6):
        p.update(DT, _Keys(pygame.K_UP))
    assert p.climbing is True and 0.3 < p.engine_burst <= 1.0
    for _ in range(14):
        p.update(DT, _Keys(pygame.K_UP))
    assert p.engine_burst == 1.0                                               # the full long jets
    p.update(DT, _Keys())                                                      # the key is let go: the jets come back
    assert p.climbing is False and 0.5 < p.engine_burst < 1.0
    for _ in range(60):
        p.update(DT, _Keys())
    assert p.engine_burst == 0.0


def test_the_long_jets_do_not_burn_going_down_or_across_or_without_the_reactor():
    p = _ship()
    p.y = PLAYER_VERTICAL_TOP + 40.0
    for _ in range(20):
        p.update(DT, _Keys(pygame.K_DOWN))
    assert p.engine_burst == 0.0 and p.climbing is False
    for _ in range(20):
        p.update(DT, _Keys(pygame.K_LEFT))
    assert p.engine_burst == 0.0
    q = _ship(vertical=False)
    for _ in range(20):
        q.update(DT, _Keys(pygame.K_UP))
    assert q.engine_burst == 0.0 and q.climbing is False                       # no reactor: the ship does not climb


def test_the_jets_do_not_burn_when_the_ship_is_stopped_at_the_top_of_its_range():
    p = _ship()
    p.y = float(PLAYER_VERTICAL_TOP)
    for _ in range(20):
        p.update(DT, _Keys(pygame.K_UP))
    assert p.y == PLAYER_VERTICAL_TOP and p.climbing is False and p.engine_burst == 0.0


def test_the_phenix_climbs_with_the_long_jets_too():
    p = Player(640, BASE_HEIGHT - 95, ship_id="phoenix")
    p.input_scheme = "solo"
    p.vertical_range = (PLAYER_VERTICAL_TOP, PLAYER_VERTICAL_BOTTOM)
    p.speed = 100.0
    p.y = float(PLAYER_VERTICAL_BOTTOM)
    for _ in range(20):
        p.update(DT, _Keys(pygame.K_UP))
    assert p.engine_burst == 1.0


def test_up_and_down_move_the_ship_inside_the_range():
    p = _ship()
    y0 = p.y
    p.update(DT, _Keys(pygame.K_UP))
    assert p.y == pytest.approx(y0 - p.speed * DT)
    for _ in range(300):
        p.update(DT, _Keys(pygame.K_UP))
    assert p.y == PLAYER_VERTICAL_TOP                                            # stops at the top of the range
    p.update(DT, _Keys(pygame.K_DOWN))
    assert p.y == pytest.approx(PLAYER_VERTICAL_TOP + p.speed * DT)
    for _ in range(300):
        p.update(DT, _Keys(pygame.K_DOWN))
    assert p.y == PLAYER_VERTICAL_BOTTOM                                         # and at the bottom
    assert p.rect.centery == PLAYER_VERTICAL_BOTTOM


def test_both_keys_cancel_out_and_a_diagonal_moves_in_both_ways():
    p = _ship()
    y0 = p.y
    p.update(DT, _Keys(pygame.K_UP, pygame.K_DOWN))
    assert p.y == y0
    x0 = p.x
    p.update(DT, _Keys(pygame.K_UP, pygame.K_LEFT))
    assert p.x < x0 and p.y < y0
    assert p.moving


def test_moving_only_vertically_counts_as_moving_for_the_engines():
    p = _ship()
    p.update(DT, _Keys(pygame.K_DOWN))
    assert p.moving is True
    p.update(DT, _Keys())
    assert p.moving is False


def test_the_vertical_speed_follows_the_hangar_speed():
    p = _ship()
    p.speed = PLAYER_SPEED * 0.4
    y0 = p.y
    p.update(DT, _Keys(pygame.K_UP))
    assert y0 - p.y == pytest.approx(PLAYER_SPEED * 0.4 * DT)


def test_the_gamepad_stick_and_dpad_fly_up_and_down():
    class Pad:
        def __init__(self, ax1=0.0, hat=(0, 0)):
            self.ax1, self.hat = ax1, hat

        def get_axis(self, i):
            return self.ax1 if i == 1 else 0.0

        def get_numhats(self):
            return 1

        def get_hat(self, i):
            return self.hat

        def get_numbuttons(self):
            return 0

        def get_button(self, i):
            return 0

    p = _ship()
    y0 = p.y
    p.update(DT, _Keys(), "gamepad", Pad(ax1=-1.0))
    assert p.y < y0
    y1 = p.y
    p.update(DT, _Keys(), "gamepad", Pad(ax1=1.0))
    assert p.y > y1
    y2 = p.y
    p.update(DT, _Keys(), "gamepad", Pad(hat=(0, 1)))                           # d-pad up
    assert p.y < y2
    y3 = p.y
    p.update(DT, _Keys(), "gamepad", Pad(hat=(0, -1)))                          # d-pad down
    assert p.y > y3
    q = _ship(vertical=False)
    yq = q.y
    q.update(DT, _Keys(), "gamepad", Pad(ax1=-1.0))
    assert q.y == yq


def test_the_coop_keyboards_have_their_own_vertical_keys():
    p = _ship()
    p.input_scheme = "kb1"
    y0 = p.y
    p.update(DT, _Keys(pygame.K_z))
    assert p.y < y0
    y1 = p.y
    p.update(DT, _Keys(pygame.K_s))
    assert p.y > y1
    p.input_scheme = "kb2"
    y2 = p.y
    p.update(DT, _Keys(pygame.K_UP))
    assert p.y < y2


def test_the_ship_of_a_mission_flies_up_and_down_only_once_the_reactor_is_installed(run):
    g = run.game
    _launch(run, bestiary_s4=True)
    assert g.player.vertical_range is None
    g._end_adventure(False)
    _launch(run, bestiary_s4=True, got={"reactor_shield": si.FOUND}, cheat=True)      # on sale: not yet
    assert g.player.vertical_range is None
    g._end_adventure(False)
    _launch(run, bestiary_s4=True, got=SHIELD_ON, cheat=True)
    assert g.player.vertical_range == (PLAYER_VERTICAL_TOP, PLAYER_VERTICAL_BOTTOM)
    _arrived(run)
    y0 = g.player.y
    pygame.key.set_mods(0)
    p = g.player
    p.update(DT, _Keys(pygame.K_UP))
    assert p.y < y0


def test_the_reactor_works_in_the_other_missions_too(run):
    g = run.game
    st = _state(SHIELD_ON)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index("ch1_sortie")
    g._begin_adventure(g.story._launch_selected())
    assert g.player.vertical_range == (PLAYER_VERTICAL_TOP, PLAYER_VERTICAL_BOTTOM)


def test_the_arcade_game_never_gets_the_reactor(run):
    g = run.game
    assert g.player.vertical_range is None


# ------------------------------------------------------------------ the paths
@pytest.mark.parametrize("variant", range(galaga.VARIANTS))
def test_a_path_comes_in_from_outside_and_leaves_outside(variant):
    p = path_for(variant, 1)
    x0, y0, _ = p.at(0)
    x1, y1, _ = p.at(p.length)
    assert x0 < 0 or y0 < 0 or x0 > BASE_WIDTH
    assert x1 < 0 or y1 < 0 or x1 > BASE_WIDTH
    assert p.length > 1500                                                      # long enough for loops
    ys = [y for _, y in p.pts]
    assert max(ys) < BASE_HEIGHT - 200                                         # the birds stay above the ship's zone


@pytest.mark.parametrize("variant", range(galaga.VARIANTS))
def test_the_other_side_is_the_mirror_image(variant):
    a, b = path_for(variant, 1), path_for(variant, -1)
    assert a.length == pytest.approx(b.length)
    for s in (0, a.length * 0.3, a.length * 0.6, a.length):
        xa, ya, _ = a.at(s)
        xb, yb, _ = b.at(s)
        assert xb == pytest.approx(BASE_WIDTH - xa) and yb == pytest.approx(ya)


@pytest.mark.parametrize("variant", range(galaga.VARIANTS))
def test_a_path_is_smooth_no_kinks(variant):
    """The heading never jumps between two points close together (loops are joined along their tangent)."""
    p = path_for(variant, 1)
    last = None
    worst = 0.0
    s = 0.0
    while s < p.length:
        _, _, h = p.at(s)
        if last is not None:
            d = abs((math.degrees(h - last) + 180.0) % 360.0 - 180.0)
            worst = max(worst, d)
        last = h
        s += 6.0
    assert worst < 25.0, worst


def test_at_goes_on_in_a_straight_line_before_the_start_and_after_the_end():
    p = Path([(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)])
    assert p.length == pytest.approx(200.0)
    assert p.at(50.0)[:2] == pytest.approx((50.0, 0.0))
    assert p.at(150.0)[:2] == pytest.approx((100.0, 50.0))
    assert p.at(-30.0)[:2] == pytest.approx((-30.0, 0.0))
    assert p.at(260.0)[:2] == pytest.approx((100.0, 160.0))
    assert p.at(50.0)[2] == pytest.approx(0.0) and p.at(150.0)[2] == pytest.approx(math.pi / 2)


# ------------------------------------------------------------------ the formation
def _form(mult=1.1, seed=3, fresh=galaga.FRESH):
    import random
    return GalagaFormation(speed_mult=mult, rng=random.Random(seed), fresh=fresh)


def test_the_formation_has_the_face_the_game_expects():
    f = _form()
    for name in ("enemies", "bullets", "update", "draw", "get_alive_enemies", "get_hittable_enemies", "all_dead",
                 "offset_x", "sounds", "swarm", "remaining", "wave", "waves"):
        assert hasattr(f, name), name
    assert f.swarm is None and f.waves == 4 and galaga.WAVES == 4
    assert f.remaining() == sum(galaga.FRESH) and not f.all_dead()


def test_nothing_comes_in_before_the_start_delay():
    f = _form()
    _step(f, galaga.START_DELAY - 0.2)
    assert f.enemies == [] and f.wave == 0
    _step(f, 0.4)
    assert f.wave == 1 and len(f.enemies) == galaga.FRESH[0]


def test_the_first_wave_mixes_blue_and_khaki_birds_in_two_chains_from_both_sides():
    f = _form()
    _step(f, galaga.START_DELAY + 0.1)
    assert {e.stage for e in f.enemies} == {1, 2}                                # blue and khaki
    assert all(isinstance(e, GalagaBird) for e in f.enemies)
    assert len(f.chains) == 2 and galaga.FRESH[0] > galaga.CHAIN_MAX             # eleven birds: two chains
    sides = {c.path.at(0)[0] < 0 for c in f.chains}
    assert sides == {True, False}                                                # one comes from each side
    small = _form(fresh=(6, 6, 8, 8))
    _step(small, galaga.START_DELAY + 0.1)
    assert len(small.chains) == 1                                                # six birds: one chain


def test_the_waves_are_almost_twice_as_big_as_the_first_version():
    assert sum(galaga.FRESH) >= 48 and len(galaga.FRESH) == galaga.WAVES == 4    # was 6 + 6 + 8 + 8 = 28
    assert list(galaga.FRESH) == sorted(galaga.FRESH)                            # never smaller than the one before


def test_the_birds_of_a_chain_follow_the_same_path_one_behind_the_other():
    f = _form(fresh=(6, 6, 8, 8))
    _step(f, galaga.START_DELAY + 1.5)
    chain = f.chains[0]
    first, second = chain.birds[0], chain.birds[1]
    assert first.x != second.x or first.y != second.y
    d = chain.run - 0
    x0, y0, _ = chain.path.at(d)
    assert (first.x, first.y) == pytest.approx((x0, y0), abs=1.0)
    x1, y1, _ = chain.path.at(d - galaga.CHAIN_GAP)
    assert (second.x, second.y) == pytest.approx((x1, y1), abs=1.0)
    assert first.state == "diving"                                               # a bird on its path rams like a diver


def test_a_wave_with_no_shots_fired_leaves_and_its_birds_wait_for_the_next_one():
    f = _form()
    f.fresh = (6, 6, 8, 8)
    _step(f, galaga.START_DELAY + 0.1)
    birds = list(f.enemies)
    _until(lambda: not f.chains, f, step=0.5)
    assert f.enemies == [] and sorted(map(id, f.carry)) == sorted(map(id, birds))     # nobody was lost on the way
    assert f.remaining() == 28 and not f.all_dead()


def test_the_survivors_join_the_next_wave_which_gets_bigger():
    f = _form()
    _step(f, galaga.START_DELAY + 0.1)
    assert len(f.enemies) == galaga.FRESH[0]
    _kill(f, f.enemies[:2])                                                      # two are shot down
    survivors = {id(e) for e in _alive(f)}
    assert len(survivors) == galaga.FRESH[0] - 2
    _until(lambda: f.wave == 2, f, step=0.25)
    assert f.wave == 2
    assert survivors <= {id(e) for e in f.enemies}                               # the same birds come back...
    assert len(_alive(f)) == galaga.FRESH[0] - 2 + galaga.FRESH[1]                               # ...with the new ones
    n2 = len(_alive(f))
    _kill(f, _alive(f)[:3])
    _until(lambda: f.wave == 3, f, step=0.25)
    assert len(_alive(f)) == n2 - 3 + galaga.FRESH[2]


def test_there_is_a_calm_between_the_end_of_a_wave_and_the_next_one():
    f = _form()
    _step(f, galaga.START_DELAY + 0.1)
    _until(lambda: not f.chains, f)
    assert f.wave == 1
    calm = 0.0
    while f.wave == 1:
        f.update(DT, 640.0)
        calm += DT
        assert calm < 5.0
    assert calm == pytest.approx(galaga.WAVE_PAUSE, abs=0.05)


def test_the_fourth_wave_comes_back_until_every_bird_is_destroyed():
    f = _form()
    seen_return = False
    for _ in range(40 * 60):
        f.update(DT, 640.0)
        if f.wave == 4 and not f.chains and f.carry:
            seen_return = True
            break
    assert f.wave == 4
    # let it fly on: the last wave leaves and comes again, nobody is created any more
    count = len(f.enemies) + len(f.carry)
    launches = 0
    prev = bool(f.chains)
    for _ in range(60 * 60):
        f.update(DT, 640.0)
        now = bool(f.chains)
        if now and not prev:
            launches += 1
        prev = now
        if launches >= 2:
            break
    assert launches >= 2                                                         # it keeps coming back
    assert f.wave == 4 and len(f.enemies) + len(f.carry) == count                # with the same birds
    assert not f.all_dead()
    # and the mission is won when they are all down
    _kill(f, list(f.enemies) + list(f.carry))
    f.carry = []
    f.update(DT, 640.0)
    assert f.all_dead() and f.remaining() == 0


def test_the_mission_is_not_won_while_a_bird_waits_out_of_the_screen_or_a_wave_is_to_come():
    f = _form()
    assert not f.all_dead()
    _step(f, galaga.START_DELAY + 0.1)
    _kill(f, list(f.enemies))
    f.update(DT, 640.0)
    assert not f.all_dead()                                                      # three waves are still to come
    f2 = _form()
    f2.wave = 4
    f2.carry = [GalagaBird(1)]
    assert not f2.all_dead()


def test_the_birds_fire_a_lot_but_only_when_they_are_in_the_screen():
    f = _form()
    f.fresh = (6, 6, 8, 8)
    _step(f, galaga.START_DELAY + 0.1)
    birds = list(f.enemies)
    # far out of the screen: nobody shoots
    for b in birds:
        b.fire_t = 0.0
    f.update(DT, 640.0)
    assert f.bullets == []
    _step(f, 4.0)
    assert len(f.bullets) + 0 >= 0
    shots = 0
    for _ in range(int(20 / DT)):
        before = len(f.bullets)
        f.update(DT, 640.0)
        shots += max(0, len(f.bullets) - before)
        if f.wave > 1:
            break
    assert shots >= 4                                                           # a chain fills the sky with bullets
    assert all(b.owner_id in {id(e) for e in birds} for b in f.bullets)


def test_the_later_waves_shoot_more():
    assert list(galaga.FIRE_MEAN) == sorted(galaga.FIRE_MEAN, reverse=True)      # shorter and shorter gaps
    assert galaga.FIRE_MEAN[0] > galaga.FIRE_MEAN[-1]
    means = []
    for wave in (0, 3):
        f = _form()
        f.wave = wave
        f.carry = [GalagaBird(1 + i % 2) for i in range(4)]
        f.update(DT, 640.0)
        f.pause = 0.0
        f.update(DT, 640.0)
        means.append(f._fire_mean)
    assert means[0] > means[1]                                                   # a later wave waits less between shots


def test_each_wave_flies_a_little_faster_and_the_level_speed_counts():
    speeds = []
    for wave in range(4):
        f = _form(mult=1.1)
        f.wave = wave
        f.carry = [GalagaBird(1)]
        f.update(DT, 640.0)
        f.pause = 0.0
        f.update(DT, 640.0)
        speeds.append(f._speed)
    assert speeds[0] == pytest.approx(galaga.BASE_SPEED * 1.1)                   # level 2: x1.1
    assert speeds == sorted(speeds) and speeds[3] == pytest.approx(speeds[0] * (1 + 3 * galaga.WAVE_SPEEDUP))
    slow = _form(mult=1.0)
    slow.carry = [GalagaBird(1)]
    slow.update(DT, 640.0)
    slow.pause = 0.0
    slow.update(DT, 640.0)
    assert slow._speed < speeds[0]


def test_the_number_of_bullets_in_the_sky_is_capped(monkeypatch):
    monkeypatch.setattr(galaga, "FIRE_MEAN", (0.1, 0.1, 0.1, 0.1))               # everybody shoots all the time
    f = _form()
    f.wave = 3
    f.carry = [GalagaBird(1 + i % 2) for i in range(26)]
    f.update(DT, 640.0)
    f.pause = 0.0
    top = 0
    for _ in range(int(20 / DT)):
        f.update(DT, 640.0)
        top = max(top, len(f.bullets))
        assert len(f.bullets) <= galaga.MAX_BULLETS
    assert top == galaga.MAX_BULLETS                                             # and the sky does fill up to it


def test_a_bird_above_the_ship_shoots_sooner():
    f = _form()
    _step(f, galaga.START_DELAY + 0.1)
    b = f.enemies[0]
    b.place(600.0, 200.0, math.pi / 2)
    b.fire_t = 5.0
    f._fire(b, 1.0, 600.0)
    near = b.fire_t
    b.fire_t = 5.0
    f._fire(b, 1.0, 1100.0)
    far = b.fire_t
    assert near < far


def test_a_dying_bird_stops_shooting_and_is_dropped():
    f = _form()
    _step(f, galaga.START_DELAY + 0.1)
    b = f.enemies[0]
    b.kill()                                                                     # starts the death animation
    assert b.dying
    _step(f, 0.6)
    assert b not in f.enemies


def test_the_formation_draws_birds_in_every_direction_without_failing():
    f = _form()
    f.sounds = None
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT), pygame.SRCALPHA)
    banks = set()
    for _ in range(60 * 30):
        f.update(DT, 640.0)
        f.draw(surf)
        banks |= {round(b.bank / 5.0) for b in f.enemies}
    assert len(banks) > 6                                                        # the birds lean one way, then the other
    assert min(banks) < 0 < max(banks)


def test_a_bird_leans_into_its_turns_and_is_straight_when_it_dives():
    b = GalagaBird(1)
    b.place(100, 100, math.pi / 2)                                               # straight down
    assert b.bank == pytest.approx(0.0)
    b.place(100, 100, 0.0)                                                       # to the right
    assert b.bank == pytest.approx(-54.0) or b.bank == pytest.approx(54.0) or abs(b.bank) > 30
    b.place(100, 100, -math.pi / 2)                                              # straight up
    assert abs(b.bank) == pytest.approx(galaga.BANK_MAX)
    right, left = GalagaBird(1), GalagaBird(1)
    right.place(0, 0, 0.3)
    left.place(0, 0, math.pi - 0.3)
    assert right.bank * left.bank < 0


# ------------------------------------------------------------------ in the game
def test_the_mission_runs_in_the_game_at_level_two(run):
    g = run.game
    spec = _launch(run, bestiary_s4=True)
    assert isinstance(g.formation, GalagaFormation)
    assert g.stage == 6
    assert g.formation.speed_mult == pytest.approx(1.1 * g.difficulty_speed_mult())
    _arrived(run)
    run.frames(int(galaga.START_DELAY * 60) + 60)
    assert len(g.formation.enemies) == galaga.FRESH[0]
    # birds are worth the level-2 points (+10) and count in the Bestiary
    blue = next(e for e in g.formation.enemies if e.stage == 1)
    g.stage = 1
    base = g._enemy_kill_points(blue)
    g.stage = 6
    assert g._enemy_kill_points(blue) == base + 10
    assert g.adventure["kills"]["bird1"] == 2
    run.frames(5)


def test_the_hud_shows_the_wave_and_the_birds_left(run, french):
    import text_cache as tc_mod
    from i18n import t
    g = run.game
    _launch(run, bestiary_s4=True)
    _arrived(run)
    run.frames(int(galaga.START_DELAY * 60) + 30)
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
    assert t("story_galaga_hud").format(n=1, m=4, left=sum(galaga.FRESH)) in seen
    assert t("story_m_bonus2d_hud") in seen                                      # a short name on the top left
    for e in g.formation.enemies[:2]:
        e.kill(flash=False)
    seen.clear()
    tc_mod.TextCache.get = spy
    try:
        run.frames(2)
    finally:
        tc_mod.TextCache.get = orig
    assert t("story_galaga_hud").format(n=1, m=4, left=sum(galaga.FRESH) - 2) in seen


def test_a_bird_shot_down_is_worth_points_and_a_ram_costs_a_life(run):
    g = run.game
    _launch(run, bestiary_s4=True)
    _arrived(run)
    g.player.infinite_lives = False
    g.player.lives = 3
    run.frames(int(galaga.START_DELAY * 60) + 20)
    bird = g.formation.enemies[0]
    g.player.invulnerable = 0.0
    bird.place(g.player.x, g.player.y, math.pi / 2)
    g.formation.bullets = []
    lives = g.player.lives
    update_play = __import__("update_play")
    update_play.enemy_attacks_vs_players(g)
    assert g.player.lives == lives - 1 or g.player.dying


def _win(run, catch):
    """Play the mission by killing every bird the moment it can be hit; `catch`: put the ship under the reactor."""
    g = run.game
    for _ in range(60 * 120):
        run.frames(1)
        if g.adventure is None:
            break
        if catch and g.loot is not None:
            g.player.x = g.loot.x
            g.player.y = g.loot.y
        for b in g.formation.get_hittable_enemies():
            b.kill(flash=False)
        g.formation.carry = [b for b in g.formation.carry if b.alive]
        for b in g.formation.carry:
            b.kill(flash=False)
        g.formation.carry = []
    assert g.adventure is None                                                   # the mission ended, back to the map
    return g.story.state


def test_winning_the_mission_and_catching_the_reactor_puts_it_on_sale(run):
    g = run.game
    _launch(run, bestiary_s4=True)
    _arrived(run)
    st = _win(run, catch=True)
    assert "bonus_2d" in st["cleared"] and si.reactor_status(st, "shield") == si.FOUND
    assert ss.loadout(st)["vertical"] is False                                   # to be bought in the hangar


def test_a_fast_win_still_sees_the_reactor_fall_and_a_missed_one_brings_the_mission_back(run):
    g = run.game
    _launch(run, bestiary_s4=True)
    _arrived(run)
    seen = []
    for _ in range(60 * 120):
        run.frames(1)
        if g.adventure is None:
            break
        if g.loot is not None:
            seen.append(g.loot.item)                                             # it falls, and the pilot lets it go by
            g.player.x = 60.0 if g.loot.x > BASE_WIDTH / 2 else BASE_WIDTH - 60.0     # (the far side: no catch by chance)
        for b in g.formation.get_hittable_enemies():
            b.kill(flash=False)
        g.formation.carry = []
    assert g.adventure is None
    st = g.story.state
    assert set(seen) == {"reactor_shield"}                                       # it did fall, once
    assert "bonus_2d" in st["cleared"] and si.reactor_status(st, "shield") is None
    assert ss.mission_playable(st, ss.mission_by_id("bonus_2d"))                 # offered again


def test_the_mission_plays_with_a_ship_that_flies_up_and_down(run):
    g = run.game
    _launch(run, bestiary_s4=True, got=SHIELD_ON, cheat=True)
    _arrived(run)
    run.frames(int(galaga.START_DELAY * 60) + 120)
    assert PLAYER_VERTICAL_TOP <= g.player.y <= PLAYER_VERTICAL_BOTTOM


# ------------------------------------------------------------------ the reactor in the hangar
def _hangar(got=(), credits=0, phenix=False, **flags):
    st = _state(**flags)
    st["credits"] = credits
    for item in got:
        assert si.find(st, item)
    if phenix:
        st["slots"][1]["owned"] = True
        st["selected_slot"] = 1
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "hangar"
    hub.zone = "shop"
    return hub


def _item_rows(hub):
    return [r for r in hub.shop_rows() if r[0].startswith("item:")]


def test_the_two_reactors_cost_2000_for_the_shield_and_4000_for_the_phenix():
    assert si.PRICES["reactor_shield"] == 2000 and si.PRICES["reactor_phenix"] == 4000
    assert si.REACTORS == {"shield": "reactor_shield", "phoenix": "reactor_phenix"}


def test_the_shield_shop_sells_the_shield_reactor_only():
    hub = _hangar(got=("reactor_shield", "reactor_phenix"), credits=9000)
    assert [(r[0], r[1], r[2]) for r in _item_rows(hub)] == [
        ("item:reactor_shield", "item_reactor_shield_name", 2000)]


def test_the_phenix_shop_sells_the_phenix_reactor_only():
    hub = _hangar(got=("reactor_shield", "reactor_phenix"), credits=9000, phenix=True)
    assert [(r[0], r[1], r[2]) for r in _item_rows(hub)] == [
        ("item:reactor_phenix", "item_reactor_phenix_name", 4000)]


def test_nothing_is_listed_before_the_reactor_is_caught():
    assert _item_rows(_hangar(credits=9000)) == []
    assert _item_rows(_hangar(credits=9000, phenix=True)) == []


def test_buying_the_shield_reactor_installs_it_for_good_and_saves():
    hub = _hangar(got=("reactor_shield",), credits=2500)
    hub.shop_index = [r[0] for r in hub.shop_rows()].index("item:reactor_shield")
    hub.confirm()
    assert hub.state["credits"] == 500 and si.reactor_on(hub.state, "shield")
    assert hub.take_sounds() == ["1up"]
    hub.confirm()                                                              # a second press buys nothing more
    assert hub.state["credits"] == 500
    saved = ss.load_state(ss.story_path(1))
    assert si.reactor_on(saved, "shield") and ss.loadout(saved)["vertical"] is True
    assert hub._shop_extra("item:reactor_shield", 2000, False) in ("INSTALLÉ", "INSTALLED")


def test_the_reactor_is_too_dear_with_too_few_points():
    hub = _hangar(got=("reactor_shield",), credits=1999)
    hub.shop_index = [r[0] for r in hub.shop_rows()].index("item:reactor_shield")
    hub.confirm()
    assert hub.state["credits"] == 1999 and si.reactor_status(hub.state, "shield") == si.FOUND


def test_the_phenix_reactor_costs_4000():
    hub = _hangar(got=("reactor_phenix",), credits=3999, phenix=True)
    hub.shop_index = [r[0] for r in hub.shop_rows()].index("item:reactor_phenix")
    hub.confirm()
    assert si.reactor_status(hub.state, "phoenix") == si.FOUND
    hub.state["credits"] = 4100
    hub.confirm()
    assert hub.state["credits"] == 100 and si.reactor_on(hub.state, "phoenix")


def test_a_reactor_cannot_be_bought_for_the_other_hull():
    st = _state(got={"reactor_phenix": si.FOUND})
    st["credits"] = 9000
    assert ss.buy(st, "item:reactor_phenix") is False                          # the Shield is selected
    assert st["credits"] == 9000 and si.reactor_status(st, "phoenix") == si.FOUND
    st["slots"][1]["owned"] = True
    st["selected_slot"] = 1
    assert ss.buy(st, "item:reactor_shield") is False                          # (not even found)
    st2 = _state(got={"reactor_shield": si.FOUND})
    st2["credits"] = 9000
    st2["slots"][1]["owned"] = True
    st2["selected_slot"] = 1
    assert ss.buy(st2, "item:reactor_shield") is False and st2["credits"] == 9000


def test_the_hangar_draws_the_reactor_rows(run):
    g = run.game
    for phenix in (False, True):
        hub = _hangar(got=("reactor_phenix" if phenix else "reactor_shield",), credits=9000, phenix=phenix)
        g.story = hub
        g.menu_screen = "story_hub"
        hub.shop_index = [r[0] for r in hub.shop_rows()].index(_item_rows(hub)[0][0])
        surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
        hub.draw(surf, g.font, g.medium_font, g.font)
        run.frames(2)


# ------------------------------------------------------------------ a reactor is not a single-use item
def test_a_reactor_is_never_used_up():
    st = _state(got=SHIELD_ON)
    assert si.installed(st) == []                                              # not among the items of a mission
    assert si.consume(st, ["reactor_shield"]) == []
    res = ss.record_result(st, "ch1_sortie", 100, True, used=["reactor_shield"])
    assert res["used"] == [] and si.reactor_on(st, "shield")


def test_the_reactor_is_kept_in_the_next_acts_while_the_single_use_items_start_again():
    st = _state(got={"reactor_shield": si.INSTALLED, "reactor_phenix": si.FOUND, "tesla": si.USED})
    st["act"] = 2
    assert si.reactor_on(st, "shield") and si.reactor_status(st, "phoenix") == si.FOUND
    assert si.status(st, "tesla") is None                                      # a new Act gives the items back
    st["act"] = 3
    assert si.reactor_on(st, "shield") and ss.loadout(st)["vertical"] is True


def test_a_reactor_never_falls_in_an_ordinary_mission_and_is_not_lootable():
    st = _state()
    assert si.lootable(st) == list(si.RANDOM_IDS) and not set(si.REACTOR_IDS) & set(si.lootable(st))
    import random
    rng = random.Random(1)
    seen = set()
    for _ in range(400):
        st["items"]["since"] = 9
        plan = si.plan_drop(st, rng)
        if plan:
            seen.add(plan["id"])
    assert seen and not seen & set(si.REACTOR_IDS)


def test_a_used_reactor_in_a_save_file_is_dropped():
    book = si.clean({"act": 1, "got": {"reactor_shield": "used", "reactor_phenix": "installed", "tesla": "used"}})
    assert book["got"] == {"reactor_phenix": "installed", "tesla": "used"}


# ------------------------------------------------------------------ the fall
def test_the_reactor_plan_falls_once_at_a_random_moment_and_only_if_it_is_not_owned():
    import random
    st = _state()
    times = set()
    for seed in range(40):
        plan = si.reactor_plan(st, "shield", random.Random(seed))
        assert plan["id"] == "reactor_shield" and plan["last_wave"] is True
        assert si.REACTOR_DELAY[0] <= plan["t"] <= si.REACTOR_DELAY[1]
        times.add(round(plan["t"], 3))
    assert len(times) > 30                                                     # not always the same moment
    assert si.reactor_plan(st, "phoenix", random.Random(1))["id"] == "reactor_phenix"
    assert si.reactor_plan(st, "nobody", random.Random(1)) is None
    st["items"]["got"]["reactor_shield"] = si.FOUND
    assert si.reactor_plan(st, "shield", random.Random(1)) is None             # caught already: it does not fall again
    assert si.reactor_plan(_state(got={"reactor_shield": si.INSTALLED}), "shield", random.Random(1)) is None
    assert si.reactor_plan(st, "phoenix", random.Random(1)) is not None        # the other hull's one is separate


def test_the_bonus_mission_plans_its_reactor_and_not_a_random_item(run):
    g = run.game
    _launch(run, bestiary_s4=True)
    plan = g.adventure["loot_plan"]
    assert plan["id"] == "reactor_shield"
    assert g.story.state["items"]["since"] == si.MIN_GAP                       # it does not count in the gap of ordinary loot


def test_nothing_falls_in_the_bonus_mission_when_the_reactor_is_owned(run):
    g = run.game
    _launch(run, bestiary_s4=True, got={"reactor_shield": si.FOUND}, cheat=True)
    assert g.adventure["loot_plan"] is None


def test_the_reactor_falls_at_the_latest_when_the_last_wave_comes_in(run):
    g = run.game
    _launch(run, bestiary_s4=True)
    _arrived(run)
    g.adventure["loot_plan"] = {"id": "reactor_shield", "t": 10 ** 6, "last_wave": True}
    run.frames(5)
    assert g.loot is None and g.formation.wave < g.formation.waves
    g.formation.wave = g.formation.waves
    run.frames(2)
    assert g.loot is not None and g.loot.item == "reactor_shield"
    assert g.adventure["loot_plan"] is None                                    # once


def test_the_reactor_falls_at_its_own_time_when_the_waves_are_not_over(run):
    g = run.game
    _launch(run, bestiary_s4=True)
    _arrived(run)
    g.adventure["loot_plan"] = {"id": "reactor_shield", "t": 0.0, "last_wave": True}
    run.frames(2)
    assert g.loot is not None and g.formation.wave < g.formation.waves


def test_catching_the_reactor_in_flight_is_remembered_for_the_end_of_the_mission(run):
    g = run.game
    _launch(run, bestiary_s4=True)
    _arrived(run)
    g.adventure["loot_plan"] = {"id": "reactor_phenix", "t": 0.0}
    run.frames(2)
    g.player.x, g.player.y = g.loot.x, g.loot.y
    run.frames(2)
    assert g.adventure["loot"] == "reactor_phenix" and g.loot is None


def test_both_reactors_share_the_picture_of_the_item(run):
    import loot
    a, b = loot.frames("reactor_shield"), loot.frames("reactor_phenix")
    assert len(a) == loot.FRAMES and len(b) == loot.FRAMES
    assert pygame.image.tobytes(a[7], "RGBA") == pygame.image.tobytes(b[7], "RGBA")       # the same picture
    assert len({pygame.image.tobytes(c, "RGBA") for c in a}) > loot.FRAMES // 2           # and it turns
    assert loot.icon("reactor_shield", 30, 40) is not None
    assert max(loot.icon("reactor_phenix").get_size()) >= 90


# ------------------------------------------------------------------ the old saves
def test_a_save_that_got_the_flight_outright_keeps_it_as_an_installed_reactor():
    st = _state(vertical_thrust=True)
    ss.save_state(ss.story_path(1), st)
    back = ss.load_state(ss.story_path(1))
    assert si.reactor_on(back, "shield") and ss.loadout(back)["vertical"] is True
    assert si.reactor_status(back, "phoenix") is None
    ss.save_state(ss.story_path(1), back)
    again = ss.load_state(ss.story_path(1))
    assert si.reactor_on(again, "shield")


def test_a_save_without_the_old_flag_has_no_reactor():
    st = _state()
    ss.save_state(ss.story_path(1), st)
    assert si.reactor_status(ss.load_state(ss.story_path(1)), "shield") is None


def test_an_old_save_that_was_in_act_2_keeps_the_reactor_too():
    st = _state(vertical_thrust=True)
    st["act"] = 2
    ss.save_state(ss.story_path(1), st)
    back = ss.load_state(ss.story_path(1))
    assert si.reactor_on(back, "shield")


# ------------------------------------------------------------------ the birds of the Phenix version
def test_the_birds_shoot_more_when_the_fire_is_multiplied():
    import random
    base = GalagaFormation(speed_mult=1.0, rng=random.Random(3))
    hot = GalagaFormation(speed_mult=1.0, rng=random.Random(3), fire_mult=ss.PHENIX_FIRE_MULT)
    assert base.fire_mult == 1.0 and hot.fire_mult == ss.PHENIX_FIRE_MULT
    assert hot.max_bullets == round(galaga.MAX_BULLETS * ss.PHENIX_FIRE_MULT) > base.max_bullets == galaga.MAX_BULLETS
    for form in (base, hot):
        _until(lambda f=form: f.wave >= 1 and f.chains, form)
    assert hot._fire_mean == pytest.approx(base._fire_mean / ss.PHENIX_FIRE_MULT)
    shots = []
    for form in (base, hot):
        n = 0
        for _ in range(int(40 / DT)):
            before = len(form.bullets)
            form.update(DT, 640.0)
            n += max(0, len(form.bullets) - before)
        shots.append(n)
    assert shots[1] > shots[0] * 1.2
