"""Step 3 of the Guardians plan: the reflective coating (Gardiens III won: the dome of the Shield and the Phenix form stop
the lasers of the Guardians) and the scenes of the series (Gardiens I, II, III, Bestiary VI, and the coating after the
first victory of Gardiens III)."""

import pytest

import guardian as gd
import story_state as ss
import update_play
from i18n import T, t
from story import StoryHub

pytestmark = pytest.mark.usefixtures("training_missions")   # (the TEST missions, out of the Adventure)

DT = 1 / 60
SCENED = ("guardians_1", "best_guardians", "guardians_2", "guardians_3")


@pytest.fixture
def game(tmp_path, monkeypatch):
    import user_settings
    from game import Game
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    g = Game()
    g.story.state = ss.default_state()
    yield g
    g.running = False


def _fly(game, mission_id, coated):
    m = ss.mission_by_id(mission_id)
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["act"] = (m.get("acts") or (2,))[0]
    if m.get("need"):
        st["flags"][m["need"]] = True
    if coated:
        st["flags"][ss.REFLECT_FLAG] = True
    ss.mark_scene_seen(st, mission_id)
    game.story.state = st
    game.story.map_index = next(i for i, x in enumerate(game.story.missions()) if x["id"] == mission_id)
    spec = game.story._launch_selected()
    game._begin_adventure(spec)
    game.stage_transition = None
    game.dt = DT
    return spec


def _laser_on_the_ship(game, hull="shield", special=True):
    """A Guardian's laser across the ship (its form on or off); returns (lives lost, the bolt)."""
    p = game.player
    p.ship_id = hull
    p.y, p.invulnerable, p.morph_dir = 625, 0, 0
    p.phenix_timer = 5.0 if special else 0.0
    bolt = gd.FireLaser(p.x, 200)
    bolt.update(1.7 / 3)
    owner = gd.Guardian(p.x, 120, 0)
    owner.emission = bolt
    owner.entry = 0.0
    owner.state = "patrol"
    sq = gd.GuardianSquad(0)
    sq.guardians = [owner]
    game.guardian_squad = sq
    game.formation.bullets = [bolt]
    lives = p.lives
    update_play.enemy_attacks_vs_players(game)
    return lives - p.lives, bolt, owner


# ---------------------------------------------------------------- the coating
def test_the_launch_carries_the_coating_once_gardiens_iii_is_won(game):
    assert "reflect" not in _fly(game, "guardians_1", coated=False)
    assert _fly(game, "guardians_1", coated=True)["reflect"] is True
    assert "reflect" not in _fly(game, "test_guardians", coated=True)                  # (the TEST: the bare ship)


@pytest.mark.parametrize("hull", ["shield", "phoenix"])
def test_the_dome_and_the_phenix_form_stop_the_laser(game, hull):
    _fly(game, "guardians_1", coated=True)
    lost, bolt, owner = _laser_on_the_ship(game, hull)
    for _ in range(20):                                              # (it splits on the film, slice after slice)
        bolt.update(DT)
        update_play.enemy_attacks_vs_players(game)
    assert lost == 0 and not game.player.dying and not bolt.alive                 # (all of it split: nothing left to burn the ship)
    assert owner.emission is None                                    # (its Guardian is free again)
    assert game.laser_slices                                         # (its two halves run around the ship)


def test_the_bare_hull_still_burns(game):
    _fly(game, "guardians_1", coated=True)
    lost, bolt, _owner = _laser_on_the_ship(game, special=False)
    assert lost == 1 and bolt.alive


@pytest.mark.parametrize("hull", ["shield", "phoenix"])
def test_without_the_coating_the_laser_goes_through_the_form(game, hull):
    _fly(game, "guardians_1", coated=False)
    lost, bolt, _owner = _laser_on_the_ship(game, hull)
    assert lost == 1 and bolt.alive


def test_the_coating_stops_lasers_only(game):
    _fly(game, "guardians_1", coated=True)
    from enemy import EnemyBullet
    p = game.player
    p.ship_id, p.y, p.invulnerable, p.morph_dir, p.phenix_timer = "shield", 625, 0, 0, 0.0
    bullet = EnemyBullet(p.x, p.y)
    game.formation.bullets = [bullet]
    lives = p.lives
    update_play.enemy_attacks_vs_players(game)
    assert p.lives == lives - 1                                     # (a bird's shot on a bare hull: as always)


# ---------------------------------------------------------------- the scenes
def test_each_mission_of_the_series_has_its_scene_and_its_picture():
    pics = set()
    for mid in SCENED:
        scene = ss.scene_of(mid)
        assert scene and scene["title"] == ss.mission_by_id(mid)["title"]
        (pic, key), = scene["slides"]
        pics.add(pic)
    coat = ss.scene_of(ss.COAT_SCENE)
    (pic, key), = coat["slides"]
    pics.add(pic)
    assert len(pics) == 5 and coat["title"] == "story_scene_coat_t"
    assert ss.mission_by_id("guardians_3")["win_scene"] == ss.COAT_SCENE


def test_the_texts_exist_in_french_and_english():
    keys = [ss.scene_of(m)["slides"][0][1] for m in SCENED + (ss.COAT_SCENE,)]
    for key in keys:
        fr, en = T[key]["fr"], T[key]["en"]
        assert len(fr) > 300 and len(en) > 300 and fr != en, key
        assert "..." not in fr and "..." not in en
    assert "hybride" in T["story_scene_gd2"]["fr"] and "hybrids" in T["story_scene_gd2"]["en"]     # the revelation
    assert "revêtement réfléchissant" in T["story_m_gd3_b"]["fr"]
    assert t("story_scene_coat_t")


def test_the_scenes_come_in_the_order_of_the_story():
    order = ss.SCENE_ORDER
    assert all(order.count(s) == 1 for s in SCENED + (ss.COAT_SCENE,))
    assert order.index("ast_2") < order.index("guardians_1") < order.index("paint_1")
    assert order.index("raid_titan") < order.index("best_guardians") < order.index("guardians_2") < order.index(ss.ACT3_ATTACK)
    assert order.index("ast_3") < order.index("guardians_3") < order.index(ss.COAT_SCENE) < order.index("final_1")


def test_the_scene_of_gardiens_ii_is_told_before_its_first_flight():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    ss.grant_phenix(st)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "map"
    hub.map_index = [m["id"] for m in hub.missions()].index("guardians_2")
    assert hub._hub_confirm() is None and hub.screen == "intro" and hub.scene_id == "guardians_2"
    assert hub.intro_slides == list(ss.scene_of("guardians_2")["slides"])


def test_the_first_victory_of_gardiens_iii_tells_the_coating():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["act"] = 3
    st["flags"].update(act3=True, ast_s3=True)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.apply_result("guardians_3", 500, True, {})
    assert hub.screen == "intro" and hub.scene_id == ss.COAT_SCENE
    assert ss.flag(hub.state, ss.REFLECT_FLAG)
