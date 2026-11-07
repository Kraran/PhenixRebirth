"""The Guardians series (step 2 of the Guardians plan): Gardiens I (after the second belt, before Phenix I), Gardiens II
(the wall of lasers, before the great raid), Gardiens III (the Alpha, before Riposte I), Bestiary VI (the hunt of the
Guardians), their two entries of the Bestiary, and the saves made before the series."""

import pygame
import pytest

import bestiary_art
import guardian as gd
import story_state as ss
from i18n import T, t

DT = 1 / 60
SERIES = ("guardians_1", "guardians_2", "guardians_3")


@pytest.fixture
def display():
    pygame.display.init()
    pygame.display.set_mode((1280, 720))


@pytest.fixture
def game(tmp_path, monkeypatch):
    import user_settings
    from game import Game
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    g = Game()
    g.story.state = ss.default_state()
    yield g
    g.running = False


def _fly(game, mission_id, wave_i=0, level_wins=0):
    """The mission, its wave `wave_i` in play (a hunt: won `level_wins` times before)."""
    m = ss.mission_by_id(mission_id)
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["act"] = m["acts"][0]
    st["flags"][m["need"]] = True
    if level_wins:
        st["mission_clears"] = {mission_id: level_wins}
    ss.mark_scene_seen(st, mission_id)
    game.story.state = st
    game.story.map_index = next(i for i, x in enumerate(game.story.missions()) if x["id"] == mission_id)
    spec = game.story._launch_selected()
    game._begin_adventure(spec)
    if wave_i:
        game.adventure["wave_i"] = wave_i
        game._setup_stage(game.stage)
    game.stage_transition = None
    game.dt = DT
    return spec


def _arrive(sq, seconds=6.0):
    for _ in range(int(seconds / DT)):
        sq.tick(DT, 640, 625, [], [])


def _win(st, mission_id):
    return ss.record_result(st, mission_id, 100, True, {})


# ---------------------------------------------------------------- the missions
def test_the_three_missions_of_the_series():
    g1, g2, g3 = (ss.mission_by_id(m) for m in SERIES)
    assert g1["acts"] == (2,) and g1["need"] == "ast_s2" and g1["unlock"] == ["guardians_s1"]
    assert g1["waves"] == [16, 17] and g1["guardians_at"] == {16: 1, 17: 3}
    assert g2["acts"] == (2,) and g2["need"] == "phenix_owned" and g2["unlock"] == ["guardians_s2"]
    assert g2["waves"] == [21, 22] and g2["guardians_at"] == {21: 3, 22: 5} and g2["volley"] and g2["birds_keep"] == 3
    assert g3["acts"] == (3,) and g3["need"] == "ast_s3" and g3["unlock"] == ["guardians_s3", ss.REFLECT_FLAG]
    assert g3["waves"] == [23, 24] and g3["guardians_at"] == {23: 2, 24: 4} and g3["alpha_at"] == 24
    for m in (g1, g2, g3):
        assert m["once"] and ss.mission_group(m) == ss.GROUP_STORY and not m.get("hunt")      # mandatory, once
        assert set(m["guardians_at"]) == set(m["waves"])
    # each one is waited for by the next mission of the story
    assert ss.mission_by_id("phenix_1")["need"] == "guardians_s1"
    assert ss.mission_by_id("act3_gate")["need"] == "guardians_s2"
    assert ss.mission_by_id("final_1")["need"] == "guardians_s3"


def test_gardiens_i_comes_between_the_belt_and_phenix_i():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.jump_to_act2(st)
    g1, ph1 = ss.mission_by_id("guardians_1"), ss.mission_by_id("phenix_1")
    assert not ss.mission_playable(st, g1) and not ss.mission_playable(st, ph1)
    _win(st, "ast_2")
    assert ss.mission_playable(st, g1) and not ss.mission_playable(st, ph1)
    assert ss.unlock_hint(st, ph1) is g1
    _win(st, "guardians_1")
    assert ss.mission_playable(st, ph1) and not ss.mission_playable(st, g1)                  # once
    assert "story_log_gd1" in [e.get("key") for e in st["log"]]


def test_gardiens_ii_comes_between_the_phenix_and_the_great_raid():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.jump_to_act2(st)
    g2, gate = ss.mission_by_id("guardians_2"), ss.mission_by_id("act3_gate")
    assert not ss.mission_playable(st, g2)
    ss.grant_phenix(st)                                         # (Phenix V is won)
    assert ss.mission_playable(st, g2) and not ss.mission_playable(st, gate)
    _win(st, "guardians_2")
    assert ss.mission_playable(st, gate)
    ids = [m["id"] for m in ss.visible_missions(st)]
    assert ids.index("phenix_5") + 1 == ids.index("guardians_2") == ids.index("act3_gate") - 1


def test_gardiens_iii_comes_between_the_belt_and_riposte_i_and_gives_the_coating():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.grant_phenix(st)
    _win(st, "guardians_2")
    _win(st, "act3_gate")
    assert ss.choose_act3_ship(st, "shield")
    st["flags"]["ch3_ready"] = True
    _win(st, "ast_3")
    g3, f1 = ss.mission_by_id("guardians_3"), ss.mission_by_id("final_1")
    assert ss.mission_playable(st, g3) and not ss.mission_playable(st, f1)
    assert not ss.flag(st, ss.REFLECT_FLAG)
    _win(st, "guardians_3")
    assert ss.mission_playable(st, f1) and ss.flag(st, ss.REFLECT_FLAG)


def test_the_act_3_cheat_counts_the_act_2_missions_as_won():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.jump_to_act3(st)
    assert {"guardians_1", "guardians_2"} <= set(st["cleared"]) and "guardians_3" not in st["cleared"]


def test_the_texts_exist_in_both_languages():
    for m in list(SERIES) + ["best_guardians"]:
        mission = ss.mission_by_id(m)
        for key in (mission["title"], mission["blurb"], mission["log"]):
            assert key in T and T[key]["fr"] and T[key]["en"] and T[key]["fr"] != T[key]["en"], key
    for entry in ("guardian", "alpha"):
        e = next(x for x in ss.BESTIARY if x["id"] == entry)
        assert T[e["name"]]["fr"] and T[e["text"]]["en"]
    assert t("story_m_gd3") in (T["story_m_gd3"]["fr"], T["story_m_gd3"]["en"])


# ---------------------------------------------------------------- in the game
def test_gardiens_i_one_guardian_then_three(game):
    spec = _fly(game, "guardians_1")
    assert spec["guardians_at"] == {16: 1, 17: 3} and "volley" not in spec and "alpha_at" not in spec
    assert game.stage == 16 and len(game.guardian_squad.guardians) == 1 and not game.guardian_squad.volley
    game.adventure["wave_i"] = 1
    game._setup_stage(17)
    assert len(game.guardian_squad.guardians) == 3
    assert not any(isinstance(g, gd.AlphaGuardian) for g in game.guardian_squad.guardians)


def test_gardiens_ii_few_birds_and_a_squad_that_fires_together(game):
    game.adventure = {"waves": [21]}
    game._setup_formation(21)
    full = len(game.formation.enemies)
    spec = _fly(game, "guardians_2")
    assert spec["volley"] and spec["birds_keep"] == 3
    assert game.stage == 21 and game.guardian_squad.volley and len(game.guardian_squad.guardians) == 3
    assert len(game.formation.enemies) == (full + 2) // 3 < full                    # one bird in three
    game.adventure["wave_i"] = 1
    game._setup_stage(22)
    assert len(game.guardian_squad.guardians) == 5


def _most_lasers_in_one_tick(sq, seconds=5.0):
    shots, most = [], 0
    for g in sq.guardians:
        g.dive_wait = 1e9                                                 # (they fire, they do not dive)
    for _ in range(int(seconds / DT)):
        before = len(shots)
        sq.tick(DT, 640, 625, shots, [])
        most = max(most, len(shots) - before)
    return most


def test_the_volley_is_a_wall_of_five_lasers(display):
    sq = gd.GuardianSquad(5, volley=True)
    _arrive(sq)
    assert _most_lasers_in_one_tick(sq) == 5
    alone = gd.GuardianSquad(5)                                           # (the other missions: one after the other)
    _arrive(alone)
    assert _most_lasers_in_one_tick(alone) == 1


def test_gardiens_iii_the_alpha_comes_with_the_last_wave(game):
    spec = _fly(game, "guardians_3")
    assert spec["alpha_at"] == 24
    assert game.stage == 23 and len(game.guardian_squad.guardians) == 2
    assert not any(isinstance(g, gd.AlphaGuardian) for g in game.guardian_squad.guardians)
    game.adventure["wave_i"] = 1
    game._setup_stage(24)
    squad = game.guardian_squad.guardians
    assert len(squad) == 5 and [isinstance(g, gd.AlphaGuardian) for g in squad] == [False, False, True, False, False]
    alpha = squad[2]
    assert alpha.hp == alpha.max_hp == gd.ALPHA_HP == 6 and alpha.home_y > squad[0].home_y
    _arrive(game.guardian_squad)
    game.draw()


def test_the_alpha_is_bigger_and_fires_two_lasers(display):
    small, alpha = gd.Guardian(400, 200, 0), gd.AlphaGuardian(800, 200, 1)
    assert alpha.get_hitbox().w > small.get_hitbox().w and alpha.get_hitbox().h > small.get_hitbox().h
    assert alpha.get_left_wing_hitbox().w > small.get_left_wing_hitbox().w
    one, two = small.fire_lasers(), alpha.fire_lasers()
    assert len(one) == 1 and len(two) == 2 and two[0].x < alpha.x < two[1].x
    levels = []
    for _ in range(5):
        levels.append(alpha.level)
        assert not alpha.hit()
    assert levels == [0, 0, 1, 1, 2] and alpha.hit() and not alpha.alive          # six hits, three looks
    surf = pygame.Surface((1280, 720))
    beaten = gd.AlphaGuardian(640, 300, 0)
    beaten.charge = 0.5
    beaten.draw(surf)


def test_the_alpha_fires_its_two_lasers_in_the_squad(display):
    sq = gd.GuardianSquad(0, alpha=True)
    alpha = sq.guardians[0]
    assert isinstance(alpha, gd.AlphaGuardian)
    _arrive(sq)
    alpha.dive_wait = 1e9
    shots = []
    for _ in range(int(5 / DT)):
        sq.tick(DT, 640, 625, shots, [])
        if shots:
            break
    assert len(shots) == 2 and all(isinstance(b, gd.FireLaser) for b in shots)
    assert alpha.emission is shots[0] and alpha.laser_attached


def test_their_kills_go_into_their_own_entries_of_the_bestiary(game):
    _fly(game, "guardians_3", wave_i=1)
    alpha = next(g for g in game.guardian_squad.guardians if isinstance(g, gd.AlphaGuardian))
    other = next(g for g in game.guardian_squad.guardians if not isinstance(g, gd.AlphaGuardian))
    pts = game._enemy_kill_points(other)
    big = game._enemy_kill_points(alpha)
    assert game.adventure["kills"] == {"guardian": 1, "alpha": 1}
    assert big == pts * gd.ALPHA_POINTS
    st = game.story.state
    ss.record_kills(st, game.adventure["kills"])
    assert [e["id"] for e, _n in ss.bestiary_entries(st)] == ["guardian", "alpha"]
    assert ss.is_boss("alpha") and not ss.is_boss("guardian")


def test_their_pictures_in_the_bestiary(display):
    small, big = bestiary_art.still("guardian"), bestiary_art.still("alpha")
    assert big.get_width() > small.get_width()
    assert bestiary_art.animated("guardian", 0.0) is not bestiary_art.animated("guardian", 1 / bestiary_art.GUARDIAN_FPS)


# ---------------------------------------------------------------- Bestiary VI
def test_bestiary_vi_is_a_hunt_after_phenix_iii():
    m = ss.mission_by_id("best_guardians")
    assert ss.is_hunt(m) and m["need"] == "phenix_s3" and m["acts"] == (2, 3) and not m.get("once")
    assert [ss.hunt_guardians(n) for n in (1, 2, 3, 4, 5, 9)] == [2, 3, 4, 5, 5, 5]
    st = ss.create_slot(1, "NOVA", "normal")
    ss.jump_to_act2(st)
    assert not ss.mission_playable(st, m)
    st["flags"]["phenix_s3"] = True
    assert ss.mission_playable(st, m)
    for _ in range(2):
        _win(st, "best_guardians")
        assert ss.mission_playable(st, m)                                      # replayable


def test_bestiary_vi_guardians_come_with_the_wave_and_grow_with_the_level(game):
    spec = _fly(game, "best_guardians")
    assert spec["guardians_each"] == 2 and spec["level"] == 1
    assert len(game.guardian_squad.guardians) == 2
    spec = _fly(game, "best_guardians", level_wins=2)
    assert spec["level"] == 3 and spec["guardians_each"] == 4 and spec["waves"] == [12]
    assert game.stage == 12 and len(game.guardian_squad.guardians) == 4


# ---------------------------------------------------------------- the saves made before the series
def test_a_save_past_a_guardians_mission_keeps_its_way_open():
    data = ss.default_state()
    data["act"] = 3
    data["cleared"] = ["ast_2", "phenix_1", "act3_gate", "ast_3", "final_1"]
    st = ss.migrate_state(data)
    assert all(ss.flag(st, "guardians_s%d" % n) for n in (1, 2, 3))
    assert not any(m in st["cleared"] for m in SERIES)                       # not won: they can still be flown ...
    assert not ss.flag(st, ss.REFLECT_FLAG)                                  # ... the Alpha for its coating
    again = ss.migrate_state(st)
    assert again["flags"] == st["flags"] and again["cleared"] == st["cleared"]


def test_a_save_before_the_great_raid_has_to_fly_gardiens_ii():
    data = ss.default_state()
    data["act"] = 2
    data["flags"] = {"act2": True, "ast_s2": True, "phenix_s5": True, "phenix_owned": True}
    data["cleared"] = ["ast_2", "phenix_1", "phenix_2", "phenix_3", "phenix_4", "phenix_5"]
    st = ss.migrate_state(data)
    assert ss.flag(st, "guardians_s1") and not ss.flag(st, "guardians_s2")
    assert not ss.mission_playable(st, ss.mission_by_id("act3_gate"))
    assert ss.mission_playable(st, ss.mission_by_id("guardians_2"))


def test_an_old_save_with_phenix_i_won_still_skips_the_belt():
    data = ss.default_state()
    data["act"] = 2
    data["cleared"] = ["dome_1", "phenix_1"]
    st = ss.migrate_state(data)
    assert "ast_2" in st["cleared"] and ss.flag(st, "ast_s2") and ss.flag(st, "guardians_s1")
