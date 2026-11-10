"""BONUS FINAL - Space War (story_state "bonus_spacewar", src/spacewar.py `endless`): level after level around the
gas giant chosen in the menu, until the ship is lost or the player has no missile left. 20 torpedoes are refilled at
each level; its points pay, leaving it gains nothing, one record per planet at the top of the screen."""
import math
import random

import pytest

import antimatter
import i18n
import spacewar as sw
import story_state as ss
from test_smoke import run  # noqa: F401  (fixture)

MID = "bonus_spacewar"

WAVES = {
    1: (1, 0, 0), 2: (2, 0, 0), 3: (2, 1, 0), 4: (2, 2, 0), 5: (2, 2, 1),
    9: (2, 2, 0), 10: (2, 2, 1), 11: (2, 2, 0), 15: (2, 2, 1),
}


def _state(credits=1000):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    st["credits"] = credits
    ss.complete_ending(st)
    return st


def _launch(run, planet="jupiter", credits=1000):
    g = run.game
    ss.save_state(ss.story_path(1), _state(credits))
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(MID)
    spec = g.story._launch_selected(planet=planet)
    g._begin_adventure(spec)
    g.input_grace = 0.0
    g.stage_transition = None
    return spec


def _orbit(p, r=260.0):
    p.x, p.y, p.ast_vx, p.ast_vy, p.ast_angle = sw.CX - r, sw.CY, 0.0, -sw.circular_speed(r), -math.pi / 2
    p.rect.center = (int(p.x), int(p.y))


def _pin(bird, x=900.0, y=100.0):
    def think(dt, target):
        bird.x, bird.y, bird.ast_vx, bird.ast_vy = x, y, 0.0, 0.0
        return 0.0, False, False
    bird.x, bird.y, bird.ast_vx, bird.ast_vy = x, y, 0.0, 0.0
    bird.think = think


def _kinds(blue, green, boss):
    return [1] * blue + [2] * green + [sw.SAUCER] * boss


# ------------------------------------------------------------------ the waves
@pytest.mark.parametrize("level, wave", list(WAVES.items()))
def test_the_waves_of_the_bonus_follow_the_plan(level, wave):
    assert sw.endless_wave(level) == wave
    form = sw.SpaceWarFormation(endless=True, rng=random.Random(level))
    form.start_level(level)
    assert form.level == level and form.player_torpedoes == sw.PLAYER_TORPEDOES
    assert sorted(b.kind for b in form.birds) == sorted(_kinds(*wave))
    assert len(form.birds) == sum(wave)          # (level 5 and its kin: the fifth ship has its own orbit)


def test_the_new_texts_exist_in_every_language():
    keys = ("story_m_sw_bonus", "story_m_sw_bonus_hud", "story_m_sw_bonus_b", "spacewar_pick_title_final",
            "story_spacewar_hud_endless", "story_spacewar_level_endless")
    keys += tuple("spacewar_planet_" + k for k in sw.MENU_ORDER)
    keys += tuple("spacewar_planet_sub_" + k for k in sw.MENU_ORDER)
    keys += tuple("spacewar_info_" + k for k in sw.MENU_ORDER)
    for key in keys:
        assert set(i18n.T[key]) == set(i18n.LANG_CODES) and all(i18n.T[key][c] for c in i18n.LANG_CODES)
    assert i18n.T["story_m_sw_bonus"]["fr"].startswith("BONUS FINAL - ")
    assert i18n.T["story_m_sw_bonus"]["en"].startswith("FINAL BONUS - ")
    assert i18n.T["spacewar_pick_title_final"]["fr"].startswith("BONUS FINAL - ")
    assert "Saturne" in i18n.T["spacewar_planet_saturn"]["fr"]


def test_the_launch_is_endless_on_the_planet_chosen():
    from story import StoryHub
    ss.save_state(ss.story_path(1), _state())
    hub = StoryHub()
    hub.open_slot(1)
    hub.screen, hub.pane = "hub", "map"
    hub.map_index = [m["id"] for m in hub.missions()].index(MID)
    spec = hub._launch_selected(planet="neptune")
    assert spec["spacewar"] and spec["endless"] and spec["planet"] == "neptune" and spec["level"] == 1
    assert not spec.get("sw_levels")


# ------------------------------------------------------------------ in the game
def test_clearing_a_level_refills_the_torpedoes_and_the_announcer_says_the_next(run):
    _launch(run)
    g = run.game
    form = g.formation
    said = []
    g._play_level_vo = lambda n: said.append(n)
    run.frames(2)
    assert form.endless and form.level == 1 and sorted(b.kind for b in form.birds) == [1]
    form.player_torpedoes = 3
    form.level_time = 1.0
    for b in form.birds:
        b.alive = False
    run.frames(2)
    assert form.pause > 0 and form.level == 1
    run.frames(int(60 * (sw.LEVEL_PAUSE + 0.5)))
    assert form.level == 2 and sorted(b.kind for b in form.birds) == [1, 1]
    assert form.player_torpedoes == sw.PLAYER_TORPEDOES and not form.torpedoes
    assert g.adventure is not None and g.adventure["level"] == 2 and said == [2]


def test_a_death_ends_the_run_with_game_over_pays_and_keeps_the_best_of_the_planet(run):
    _launch(run, planet="saturn", credits=1000)
    g = run.game
    form = g.formation
    run.frames(2)
    g.score = 4200
    _orbit(g.player)
    sw._kill_player(g, form)
    seen = False
    for _ in range(60 * 20):
        run.frames(1)
        seen = seen or (g.game_over and g.hs_phase == "card")
        if g.adventure is None:
            break
    st = ss.load_state(ss.story_path(1))
    assert seen and g.adventure is None and not st.get("fallen")
    assert st["credits"] == 1000 + 4200
    assert ss.endless_best(st, MID + ":saturn") == 4200 and ss.endless_best(st, MID + ":jupiter") == 0


def test_leaving_it_gains_nothing(run):
    _launch(run, planet="uranus", credits=300)
    g = run.game
    run.frames(2)
    g.score = 900
    g._quit_to_menu()
    st = ss.load_state(ss.story_path(1))
    assert st["credits"] == 300 and ss.endless_best(st, MID + ":uranus") == 0


def test_the_record_of_the_planet_is_shown_at_the_top(run, monkeypatch):
    import draw_frame
    _launch(run, planet="neptune")
    g = run.game
    g.story.state[ss.ENDLESS_BEST] = {MID + ":neptune": 9000, MID + ":jupiter": 1}
    assert g.endless_key() == MID + ":neptune" and draw_frame.endless_record(g, g.adventure) == 9000
    asked = []
    real = i18n.t
    monkeypatch.setattr("draw_frame.t", lambda k, *a, **kw: (asked.append(k), real(k, *a, **kw))[1])
    run.frames(2)
    assert "story_ast_record" in asked


def test_the_records_of_the_planets_are_kept_in_the_save():
    st = _state()
    ss.record_result(st, MID, 700, True, best_key=MID + ":jupiter")
    ss.record_result(st, MID, 300, True, best_key=MID + ":jupiter")
    st[ss.ENDLESS_BEST]["nope:saturn"] = 5
    clean = ss.migrate_state(st)
    assert ss.endless_best(clean, MID + ":jupiter") == 700 and "nope:saturn" not in clean[ss.ENDLESS_BEST]


# ------------------------------------------------------------------ exhaustion (the player's missiles only)
def test_the_run_ends_when_the_player_is_out_of_missiles_while_enemies_remain(run):
    _launch(run, credits=500)
    g = run.game
    form = g.formation
    run.frames(2)
    g.score = 300
    g.antimatter = None
    form.player_torpedoes = 0
    _orbit(g.player)
    for b in form.birds:
        _pin(b)
        b.torpedoes = sw.BIRD_TORPEDOES          # (the birds still have ammo: that does not keep the bonus going)
    run.frames(5)
    assert form.exhausted and g.adventure
    run.frames(int(60 * (sw.EXHAUST_PAUSE + 0.5)))
    st = ss.load_state(ss.story_path(1))
    assert st["credits"] == 800 and ss.endless_best(st, MID + ":jupiter") == 300
    seen = False
    for _ in range(60 * 15):
        seen = seen or (g.game_over and g.hs_phase == "card")
        if g.adventure is None:
            break
        run.frames(1)
    assert seen and g.adventure is None and not st.get("fallen")


def test_a_last_torpedo_in_the_air_can_still_win_the_level(run):
    _launch(run)
    g = run.game
    form = g.formation
    run.frames(2)
    g.antimatter = None
    form.player_torpedoes = 0
    form.level_time = 1.0
    _orbit(g.player)
    bird = form.birds[0]
    _pin(bird, x=900.0, y=100.0)
    form.torpedoes.append(sw.Torpedo(bird.x, bird.y, 0.0, 0.0, "player"))
    run.frames(3)
    assert not form.exhausted and (form.pause > 0 or form.level == 2)
    run.frames(int(60 * (sw.LEVEL_PAUSE + 0.5)))
    assert form.level == 2 and form.player_torpedoes == sw.PLAYER_TORPEDOES and g.adventure is not None


def test_an_unused_workshop_missile_keeps_the_run_going(run):
    _launch(run)
    g = run.game
    form = g.formation
    run.frames(2)
    g.antimatter = antimatter.Armory(True)
    form.player_torpedoes = 0
    _orbit(g.player)
    for b in form.birds:
        _pin(b)
        b.torpedoes = 0
    run.frames(int(60 * (sw.EXHAUST_PAUSE + 1.0)))
    assert not form.exhausted and g.adventure is not None


def test_it_waits_for_the_workshop_missile_in_the_air_before_the_game_over(run):
    _launch(run, credits=400)
    g = run.game
    form = g.formation
    run.frames(2)
    g.score = 150
    arm = antimatter.Armory(True)
    arm.count, arm.ready = 0, False
    # a missile that stays in the air (it does not age out in one frame)
    arm.missiles = [antimatter.Missile(100.0, 100.0, 1.0, 0.0)]
    g.antimatter = arm
    form.player_torpedoes = 0
    _orbit(g.player)
    for b in form.birds:
        _pin(b)
        b.torpedoes = 0
    run.frames(5)
    assert not form.exhausted and g.adventure is not None
    arm.missiles = []
    run.frames(5)
    assert form.exhausted
    run.frames(int(60 * (sw.EXHAUST_PAUSE + 0.5)))
    st = ss.load_state(ss.story_path(1))
    assert st["credits"] == 550 and ss.endless_best(st, MID + ":jupiter") == 150
