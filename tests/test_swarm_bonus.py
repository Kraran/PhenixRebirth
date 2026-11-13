"""BONUS FINAL - Nuée (story_state "bonus_swarm", src/swarm_bonus.py): the last wave of Défense de Phobos II without an
end, five versions (who flies), a record per version, 10 % of the score paid at the GAME OVER (5 % of the two at two),
leaving gains nothing."""
import pytest

import story_state as ss
import swarm_bonus as sb
import wingman
from enemy import EnemyFormation
from test_smoke import run  # noqa: F401  (fixture)

MID = "bonus_swarm"


def _state(credits=1000, ending=True):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    st["credits"] = credits
    if ending:
        ss.complete_ending(st)
    return st


def _launch(run, variant, credits=1000):
    g = run.game
    ss.save_state(ss.story_path(1), _state(credits))
    g.story.open_slot(1)
    g.story.pane = "map"
    g.story.map_index = [m["id"] for m in g.story.missions()].index(MID)
    assert g.story._hub_confirm() is None
    assert g.story.screen == "lander_pick" and g.story.pick_for == "swarm"
    g.story.__dict__.pop("pick_load", None)
    g.story.lander_index = sb.VARIANTS.index(variant)
    spec = g.story.confirm()
    assert spec and spec["variant"] == variant
    g._begin_adventure(spec)
    g.input_grace = 0.0
    return g, spec


def _alive(form):
    return {k: sum(1 for e in form.enemies if e.alive and not e.dying and e.stage == k) for k in (1, 2, 3, 4)}


# ------------------------------------------------------------------ the mission
def test_a_final_bonus_of_act_4_secret_until_the_end():
    m = ss.mission_by_id(MID)
    assert m["acts"] == (ss.ENDING_ACT,) and ss.mission_group(m) == ss.GROUP_FINAL and m["endless"]
    assert m["stage"] == 16 and m["swarm_kinds"] == [[1, 2, 3, 4]] and m["swarm_crowd"] == 1.3     # Défense de Phobos II
    assert not ss.mission_open(_state(ending=False), m) and ss.mission_open(_state(), m)
    import i18n
    assert i18n.T[m["title"]]["fr"] == "BONUS FINAL - Nuée"
    for v in sb.VARIANTS:
        for key in ("swarm_variant_", "swarm_variant_sub_", "swarm_info_"):
            assert i18n.t(key + v) != key + v


def test_the_swarm_ramps_up_and_never_ends(run):
    form = EnemyFormation()
    form.spawn_swarm(kinds=(1, 2, 3, 4), screens=1.0, crowd=1.3, ramp=sb.RAMP)
    full = form.swarm["screen"]
    assert _alive(form) == {1: 1, 2: 0, 3: 0, 4: 0}                   # a single blue bird to start with
    seen = []
    for step in range(int(70 / 0.1)):
        form._refill_swarm(0.1)
        if step % 100 == 99:
            seen.append(_alive(form))
    assert seen[0][2] == 0 and seen[0][1] > 1                          # 10 s: the blue birds only
    assert seen[2][4] == 0 and seen[2][3] >= 1                         # 30 s: the grey gargoyles, not the dark ones
    assert _alive(form) == full                                        # a minute: the full screen
    for e in form.enemies:
        e.alive = False
    assert not form.all_dead()                                         # the fallen always come back
    form._refill_swarm(1.0)
    assert sum(_alive(form).values()) > 0


def test_the_guardians_come_once_the_swarm_is_full_and_again(run):
    g, _ = _launch(run, "solo")
    assert g.guardian_squad is None
    st = g.swarm_bonus
    g.stage_transition = None
    g.dt = 1.0
    for _ in range(int(sb.GUARDIANS_FROM) - 1):
        sb.tick(g)
    assert g.guardian_squad is None
    sb.tick(g)
    sb.tick(g)
    assert g.guardian_squad is not None and len(g.guardian_squad.guardians) == sb.GUARDIANS
    for gd in g.guardian_squad.guardians:
        gd.alive = False
    first = g.guardian_squad
    for _ in range(int(sb.GUARDIANS_AGAIN) + 1):
        sb.tick(g)
    assert g.guardian_squad is not first and len(g.guardian_squad.alive()) == sb.GUARDIANS
    assert st["clock"] > sb.GUARDIANS_FROM


# ------------------------------------------------------------------ who flies
def test_solo_the_pilots_ship_alone(run):
    g, spec = _launch(run, "solo")
    assert g.wingman is None and g.swarm_bonus["skin"] is None and not getattr(g.player, "no_gauge", False)
    assert g.formation.swarm and g.formation.swarm.get("ramp") and spec["endless"]


def test_with_sacha_the_sharper_computer_and_his_way_back(run):
    g, _ = _launch(run, "sacha_ai")
    w = g.wingman
    assert w.control == "ai" and w.look == "edf17" and w.comeback
    assert (w.reaction, w.horizon) == (wingman.ACE["reaction"], wingman.ACE["horizon"])
    assert w.reaction < wingman.REACTION and w.horizon > wingman.HORIZON
    w.state = "fight"
    w.ship.y = wingman.LINE_Y
    for _ in range(wingman.HITS):
        w.ship.invulnerable = 0.0
        assert w.damage(g, "shot")
    assert w.state == "hurt"
    w.state = "gone"
    g.stage_transition = None
    w.update(g, wingman.COMEBACK + 0.1)
    assert w.state == "wait" and w.hits == 0 and w.ship.image is w.pictures[0]


def test_two_players_the_run_goes_on_while_one_flies(run):
    g, _ = _launch(run, "duo")
    w = g.wingman
    assert w.control == "human" and w.look == "edf17" and not w.talks()
    run.frames(60)
    assert w.state == "fight"
    g.player.lives = 0
    g.player.alive = False
    g.player.dying = False
    run.frames(10)
    assert g.adventure is not None and not g.game_over                # Sacha flies on
    g.score = 4000
    w.ship.score = 6000
    for _ in range(wingman.HITS):
        w.ship.invulnerable = 0.0
        assert w.damage(g, "crash")                                    # (a collision: one hit, like a shot)
    assert w.state == "dead" and not sb.holds(g)
    run.frames(3)
    st = ss.load_state(ss.story_path(1))
    assert st["credits"] == 1000 + int((4000 + 6000) * sb.PAY_DUO + 0.5)
    assert ss.endless_best(st, MID + ":duo") == 4000 and ss.endless_best(st, MID + ":duo_sacha") == 6000


def test_sacha_alone_the_player_flies_the_edf17(run):
    g, spec = _launch(run, "sacha")
    p = g.player
    assert g.wingman is None and spec["items"] == [] and not spec.get("antimatter") and not spec.get("modules")
    assert p.lives == wingman.HITS and p.image is wingman.pictures()[0] and p.no_gauge and p.electric_immune
    skin = g.swarm_bonus["skin"]
    assert skin.control == "skin" and skin.ship is p
    p.lives = 1
    skin.update(g, 0.016)
    assert p.image is wingman.pictures()[2] and skin.hits == 2           # the picture follows the damage


def test_sacha_leads_the_computer_flies_the_pilots_ship(run):
    g, _ = _launch(run, "sacha_lead")
    w = g.wingman
    assert w.control == "ai" and w.look == "hull" and not w.talks() and w.tag_text == "NOVA"
    assert g.player.image is wingman.pictures()[0]
    lives = w.max_hits
    w.state = "fight"
    for _ in range(lives):
        w.ship.invulnerable = 0.0
        assert w.damage(g, "shot")
    assert w.state == "dead" and not sb.holds(g)                       # (the run ends with the EDF-17 C only)


# ------------------------------------------------------------------ the end
@pytest.mark.parametrize("variant", ["solo", "sacha"])
def test_the_game_over_pays_ten_percent_and_keeps_the_record_of_the_version(run, variant):
    g, _ = _launch(run, variant, credits=500)
    run.frames(2)
    g.score = 12345
    g.player.infinite_lives = False
    g.player.lives = 0
    g.player.alive = False
    g.player.dying = False
    run.frames(3)
    st = ss.load_state(ss.story_path(1))
    assert st["credits"] == 500 + int(12345 * sb.PAY + 0.5)
    assert ss.endless_best(st, MID + ":" + variant) == 12345
    others = [v for v in sb.VARIANTS if v != variant]
    assert all(ss.endless_best(st, MID + ":" + v) == 0 for v in others)   # each version its own record


def test_leaving_it_gains_nothing(run):
    g, _ = _launch(run, "sacha_ai", credits=300)
    run.frames(2)
    g.score = 900
    g._quit_to_menu()
    st = ss.load_state(ss.story_path(1))
    assert st["credits"] == 300 and ss.endless_best(st, MID + ":sacha_ai") == 0


def test_the_menu_shows_the_records(run):
    st = _state()
    st[ss.ENDLESS_BEST] = {MID + ":solo": 4200, MID + ":duo": 10, MID + ":duo_sacha": 20}
    assert "4 200" in sb.records_text(st, "solo")
    duo = sb.records_text(st, "duo")
    assert "10" in duo and "20" in duo
    pic = sb.preview("duo", {"ship_id": "shield", "tint": "red"})
    assert pic.get_size() == sb.PREVIEW_SIZE


@pytest.mark.parametrize("variant", ["solo", "sacha"])
def test_what_the_guardians_need_is_made_at_the_start(run, variant, monkeypatch):
    """The burning ship of a laser takes more than a second to make: it is made with the mission, behind the loading
    bar, not when the Guardians first come (a freeze in the middle of the fight)."""
    import ship_burn
    made = []
    real = ship_burn.prepare
    monkeypatch.setattr(ship_burn, "prepare", lambda ship: (made.append(ship), real(ship)))
    g, _ = _launch(run, variant)
    assert made and made[-1] is g.player
    made.clear()
    g.stage_transition = None
    g.dt = 1.0
    for _ in range(int(sb.GUARDIANS_FROM) + 2):
        sb.tick(g)
    assert g.guardian_squad is not None
    assert all(ship_burn.frames(g.player, False) is ship_burn.frames(g.player, False) for _ in range(2))
