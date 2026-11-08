"""BONUS - Asteroids (story_state "bonus_ast_endless", src/asteroids.py `endless`): pure Asteroids, level after level until
the ship is lost; every big rock of a level from its start (4, 6, 8, 10, then 11), the next level once no rock is left,
the saucer 10 % faster each level, the announcer saying each level; it ends with the GAME OVER of the ship, its points
paid, never a penalty nor a fall (leaving it gains and loses nothing); the best score of the save is kept and shown at
the top of the screen (not in the high scores)."""
import pygame
import pytest

import asteroids as ast
import highscores
import story_state as ss
from asteroids import AsteroidFormation
from test_smoke import run  # noqa: F401  (fixture)

DT = 1 / 60
MID = "bonus_ast_endless"


def _state(mode="normal", credits=1000, ending=True):
    st = ss.create_slot(1, "NOVA", mode)
    ss.mark_intro_seen(st)
    st["act"] = 3
    st["credits"] = credits
    if ending:
        st["flags"][ss.ENDING_DONE] = True
    return st


def _launch(run, **kw):
    g = run.game
    ss.save_state(ss.story_path(1), _state(**kw))
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(MID)
    spec = g.story._launch_selected()
    g._begin_adventure(spec)
    g.input_grace = 0.0
    g.player.infinite_lives = False
    return spec


# ------------------------------------------------------------------ the mission
def test_secret_until_the_game_is_finished_then_a_bonus_of_every_act():
    m = ss.mission_by_id(MID)
    assert ss.mission_group(m) == ss.GROUP_EXTRA and m["acts"] == (1, 2, 3)
    assert not ss.mission_open(_state(ending=False), m)
    assert ss.mission_open(_state(), m)


@pytest.mark.parametrize("level, rocks", [(1, 4), (2, 6), (3, 8), (4, 10), (5, 11), (9, 11)])
def test_the_big_rocks_of_each_level(level, rocks):
    form = AsteroidFormation(endless=True)
    form.level = level
    form.new_wave()
    assert form.rocks_for_level() == rocks and len(form.rocks) == rocks and all(r.size == 3 for r in form.rocks)
    assert not any(r.entering for r in form.rocks)                     # (all there, none coming in from outside)


def test_the_saucer_fires_10_percent_faster_each_level():
    form = AsteroidFormation(endless=True)
    gaps = []
    for level in (1, 2, 3, 6):
        form.level = level
        gaps.append(form.saucer_fire_gap())
    assert gaps[0] == ast.SAUCER_FIRE_GAP
    for level, gap in zip((2, 3, 6), gaps[1:]):
        assert ast.SAUCER_FIRE_GAP / gap == pytest.approx(1 + 0.1 * (level - 1))
    assert AsteroidFormation().saucer_fire_gap() == ast.SAUCER_FIRE_GAP  # (the belts: as before)


def test_never_won_and_nothing_comes_in(run):
    _launch(run)
    g = run.game
    form = g.formation
    assert isinstance(form, AsteroidFormation) and form.endless and g.adventure.get("level") == 1
    run.frames(2)
    assert len(form.rocks) == 4
    form.destroyed = 10 ** 6                                             # (no target: never "reached")
    assert not form.reached and not form.all_dead()
    for _ in range(3):                                                   # (the field is not topped up)
        form.rocks.pop()
    run.frames(240)
    assert len(form.rocks) == 1 and g.adventure is not None


def test_a_rock_hit_breaks_and_the_level_ends_when_no_rock_is_left(run):
    _launch(run)
    g = run.game
    said = []
    g._play_level_vo = lambda n: said.append(n)
    form = g.formation
    run.frames(2)
    g.player.invulnerable = 1e9
    big = form.rocks[0]
    form.rocks[:] = [big]
    form.break_rock(g, big)
    assert len(form.rocks) == 2 and all(r.size == 2 for r in form.rocks)   # (it still breaks in two)
    form.rocks.clear()
    run.frames(int(ast.LEVEL_PAUSE * 60) - 5)
    assert form.level == 1 and not form.rocks                          # (a short pause first)
    run.frames(10)
    assert form.level == 2 and len(form.rocks) == 6 and g.adventure["level"] == 2 and form.banner > 0
    assert g.adventure is not None and said == [2]                     # (the announcer: "Level 2")
    form.rocks.clear()
    run.frames(int(ast.LEVEL_PAUSE * 60) + 5)
    assert form.level == 3 and said == [2, 3]


def _lose_the_ship(run, g):
    g.player.lives = 1
    g.player.alive = False
    g.player.dying = False
    run.frames(3)


def _until_back(run, g, limit=60 * 15):
    for _ in range(limit):
        if g.adventure is None:
            return
        run.frames(1)


def test_the_loss_of_the_ship_shows_game_over_pays_the_points_and_keeps_the_best(run):
    _launch(run, mode="normal", credits=1000)
    g = run.game
    run.frames(2)
    g.score = 4321
    _lose_the_ship(run, g)
    st = ss.load_state(ss.story_path(1))                               # (written at once, before the card)
    assert st["credits"] == 1000 + 4321 and ss.endless_best(st, MID) == 4321
    seen = False
    for _ in range(60 * 15):
        seen = seen or (g.game_over and g.hs_phase == "card")
        if g.adventure is None:
            break
        run.frames(1)
    assert seen and g.adventure is None                                # (the GAME OVER card, then the map)
    assert g.menu_screen == "story_hub"
    assert g.story.toast.startswith(__import__("i18n").t("story_ast_end").format(pts=4321)[:8])
    assert all(e.get("score") != 4321 for e in highscores.load_highscores())


def test_a_veteran_does_not_fall_in_it(run):
    _launch(run, mode="veteran", credits=500)
    g = run.game
    run.frames(2)
    g.score = 100
    _lose_the_ship(run, g)
    _until_back(run, g)
    st = ss.load_state(ss.story_path(1))
    assert g.adventure is None and not st.get("fallen") and st["credits"] == 600


def test_leaving_it_gains_and_loses_nothing(run):
    _launch(run, credits=300)
    g = run.game
    run.frames(2)
    g.score = 250
    g._quit_to_menu()
    st = ss.load_state(ss.story_path(1))
    assert st["credits"] == 300 and ss.endless_best(st, MID) == 0


def test_a_lower_score_keeps_the_record():
    st = _state()
    ss.record_result(st, MID, 900, False)
    res = ss.record_result(st, MID, 300, False)
    assert res["cleared"] and not res["best"] and res["lost"] == 0 and ss.endless_best(st, MID) == 900
    assert ss.record_result(st, MID, 1200, False)["best"] and ss.endless_best(st, MID) == 1200
    assert ss.endless_best(ss.migrate_state(st), MID) == 1200          # (kept in the save)
    bad = dict(st, **{ss.ENDLESS_BEST: {"nope": 5, MID: "x"}})
    assert ss.migrate_state(bad).get(ss.ENDLESS_BEST, {}) .get("nope") is None


def test_the_record_is_shown_at_the_top(run):
    import draw_frame
    _launch(run)
    g = run.game
    st = g.story.state
    st[ss.ENDLESS_BEST] = {MID: 5000}
    g.score = 1200
    assert draw_frame.endless_record(g, g.adventure) == 5000
    g.score = 7000
    assert draw_frame.endless_record(g, g.adventure) == 7000          # (beaten: the run's)
    run.frames(5)                                                      # (the HUD draws: the record, the rocks, the level)
