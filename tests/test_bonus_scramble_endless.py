"""BONUS FINAL - Scramble (scramble.py `endless`): the base blown up, the course starts again from its beginning with 10 %
more enemies (birds, missiles, comets), and so on until the last life (the GAME OVER); its points pay, leaving it gains
nothing, one record for all the settings at the top of the screen."""
import pytest

import scramble as sc
import story_state as ss
from test_smoke import run  # noqa: F401  (fixture)

MID = "bonus_scramble"


def _state(credits=1000):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    st["credits"] = credits
    ss.complete_ending(st)
    return st


def _launch(run, body="rock", credits=1000):
    g = run.game
    ss.save_state(ss.story_path(1), _state(credits))
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(MID)
    spec = g.story._launch_selected(body)
    g._begin_adventure(spec)
    g.input_grace = 0.0
    g.stage_transition = None
    return spec


# ------------------------------------------------------------------ 10 % more enemies each course
@pytest.mark.parametrize("loop", [2, 3, 6])
def test_each_course_has_ten_percent_more_enemies(loop):
    base = sc.Tune(sc.LEVEL_MAX)
    more = sc.Tune(sc.LEVEL_MAX, 1.0 + sc.BOOST_STEP * (loop - 1))
    k = 1.0 + 0.1 * (loop - 1)
    assert more.stations == pytest.approx(base.stations * k) and more.comets == pytest.approx(base.comets * k)
    assert more.reload == pytest.approx(base.reload / k)
    assert more.wave_gap == pytest.approx(tuple(g / k for g in base.wave_gap))
    assert more.boss_hp == base.boss_hp and more.scroll == base.scroll         # (the rest: the same)


def test_more_missile_stations_on_a_boosted_course():
    import random
    one = sc.ScrambleFormation(style="rock", seed=11, rng=random.Random(1))
    four = sc.ScrambleFormation(style="rock", seed=11, rng=random.Random(1), endless=True, loop=4)
    assert four.tune.boost == pytest.approx(1.3) and len(four.stations) > len(one.stations)


# ------------------------------------------------------------------ in the game
def test_the_launch_is_endless(run):
    spec = _launch(run, body="europa")
    g = run.game
    assert spec["scramble"] and spec["endless"] and spec["body"] == "europa"
    assert g.formation.endless and g.formation.loop == 1 and g.adventure["level"] == 1


def test_the_base_blown_up_starts_the_course_again_harder(run):
    _launch(run)
    g = run.game
    said = []
    g._play_level_vo = lambda n: said.append(n)
    run.frames(2)
    form = g.formation
    g.player.invulnerable = 1e9                                          # (nothing of the course may cost a life here)
    lives = g.player.lives
    form.cam = form.course.stop
    form.speed = 0.0
    run.frames(2)
    assert form.phase == "arena"
    form.base.done = True
    run.frames(2)
    assert form.phase == "won" and not form.won and not form.all_dead()  # (never won: the mission goes on)
    run.frames(int(sc.LOOP_PAUSE * 60) + 3)
    new = g.formation
    assert new is not form and isinstance(new, sc.ScrambleFormation)
    assert new.loop == 2 and new.cam == pytest.approx(0.0, abs=20) and new.phase == "flying"
    assert new.style == form.style and new.tune.boost == pytest.approx(1.1)
    assert g.player.scramble is new and g.player.lives == lives and g.adventure is not None      # (its lives go on)
    assert g.adventure["level"] == 2 and said == [2]


def test_the_last_life_lost_shows_game_over_pays_and_keeps_one_record(run):
    _launch(run, body="ice", credits=1000)
    g = run.game
    run.frames(2)
    g.score = 6400
    g.player.lives = 1
    g.player.alive = False
    g.player.dying = False
    seen = False
    for _ in range(60 * 15):
        run.frames(1)
        seen = seen or (g.game_over and g.hs_phase == "card")
        if g.adventure is None:
            break
    st = ss.load_state(ss.story_path(1))
    assert seen and g.adventure is None and not st.get("fallen")
    assert st["credits"] == 1000 + 6400 and ss.endless_best(st, MID) == 6400   # (one record, whatever the setting)


def test_leaving_it_gains_nothing(run):
    _launch(run, credits=300)
    g = run.game
    run.frames(2)
    g.score = 900
    g._quit_to_menu()
    st = ss.load_state(ss.story_path(1))
    assert st["credits"] == 300 and ss.endless_best(st, MID) == 0


def test_the_record_is_shown_under_the_bar_of_the_course(run, monkeypatch):
    import draw_frame
    import i18n
    _launch(run, body="deimos")
    g = run.game
    g.story.state[ss.ENDLESS_BEST] = {MID: 15000}
    assert g.endless_key() == MID and draw_frame.endless_record(g, g.adventure) == 15000
    asked = []
    real = i18n.t
    monkeypatch.setattr("draw_frame.t", lambda k, *a, **kw: (asked.append(k), real(k, *a, **kw))[1])
    run.frames(2)
    assert "story_ast_record" in asked


def test_a_raid_is_still_won_by_its_base():
    import random
    f = sc.ScrambleFormation(style="rock", seed=3, rng=random.Random(2), level=3)
    assert not f.endless and f.loop == 1 and f.tune.boost == 1.0
