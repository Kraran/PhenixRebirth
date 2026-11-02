"""The missile in the workshop: a launcher (permanent, 5000) and missiles (consumable, 500) bought in the list. A missile that is
not fired stays for the next mission."""
import antimatter as am
import story_state as ss
from story import StoryHub
from test_antimatter import _launch  # noqa: F401
from test_smoke import run  # noqa: F401  (fixture)


def _hub(unlocked=True, credits=0, launcher=False, missiles=0):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    st["credits"] = credits
    st["flags"][ss.ANTIMATTER_FLAG] = unlocked
    if launcher:
        st["flags"][ss.LAUNCHER_FLAG] = True
    st["missiles"] = missiles
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    return hub


def _ids(state):
    return [r[0] for r in ss.shop_for(state)]


def test_no_missile_rows_before_the_missile_is_unlocked():
    hub = _hub(unlocked=False, credits=99999)
    assert "missile_launcher" not in _ids(hub.state) and "missile_ammo" not in _ids(hub.state)
    assert not ss.buy(hub.state, "missile_launcher")


def test_the_launcher_and_the_missile_are_in_the_list_once_unlocked():
    hub = _hub()
    rows = {r[0]: r for r in ss.shop_for(hub.state)}
    assert rows["missile_launcher"][2] == 5000 and rows["missile_ammo"][2] == 500


def test_the_launcher_costs_5000_and_is_bought_once():
    hub = _hub(credits=4999)
    assert not ss.buy(hub.state, "missile_launcher") and not ss.has_launcher(hub.state)
    hub.state["credits"] = 5600
    assert ss.buy(hub.state, "missile_launcher")
    assert ss.has_launcher(hub.state) and hub.state["credits"] == 600
    assert not ss.buy(hub.state, "missile_launcher") and hub.state["credits"] == 600
    assert ss.upgrade_note(hub.state, "missile_launcher") == "story_owned"
    assert _ids(hub.state)[-1] == "missile_launcher"                 # (a finished row goes last)


def test_a_missile_needs_the_launcher_and_costs_500():
    hub = _hub(credits=2000)
    assert not ss.buy(hub.state, "missile_ammo") and ss.missile_stock(hub.state) == 0
    assert ss.upgrade_note(hub.state, "missile_ammo") == "story_need_launcher"
    hub.state["flags"][ss.LAUNCHER_FLAG] = True
    assert ss.buy(hub.state, "missile_ammo") and ss.buy(hub.state, "missile_ammo")
    assert ss.missile_stock(hub.state) == 2 and hub.state["credits"] == 1000
    hub.state["credits"] = 499
    assert not ss.buy(hub.state, "missile_ammo")


def test_the_stock_has_a_ceiling():
    hub = _hub(credits=99999, launcher=True, missiles=ss.MISSILE_MAX - 1)
    assert ss.buy(hub.state, "missile_ammo")
    assert not ss.buy(hub.state, "missile_ammo") and ss.missile_stock(hub.state) == ss.MISSILE_MAX
    assert ss.upgrade_note(hub.state, "missile_ammo") == "story_missile_full"


def test_a_save_keeps_the_stock_and_cleans_it():
    hub = _hub(launcher=True, missiles=4)
    assert ss.load_state(ss.story_path(1))["missiles"] == 4


def test_a_mission_carries_a_missile_only_with_the_launcher_and_a_missile():
    for launcher, stock, expected in ((False, 3, False), (True, 0, False), (True, 2, True)):
        hub = _hub(launcher=launcher, missiles=stock)
        hub.map_index = 0
        spec = hub._launch_selected()
        assert bool(spec.get("antimatter")) is expected, (launcher, stock)


def test_firing_uses_one_missile_and_it_is_written_at_once(run):
    g, spec = _launch(run, "ch1_sortie")
    assert spec["antimatter"] and ss.missile_stock(g.story.state) == 3
    assert am.fire(g, g.player)
    assert ss.missile_stock(g.story.state) == 2
    assert ss.load_state(ss.story_path(1))["missiles"] == 2


def test_a_missile_not_fired_stays_for_the_next_mission(run):
    g, spec = _launch(run, "ch1_sortie")
    g._end_adventure(False)
    assert ss.missile_stock(g.story.state) == 3
    assert ss.load_state(ss.story_path(1))["missiles"] == 3


def test_the_hangar_shows_four_stats_and_the_missile_rows(run, monkeypatch):
    import story
    g = run.game
    _hub(credits=0)
    g.story.open_slot(1)
    g.story.pane = "hangar"
    seen = []
    real = story._text
    monkeypatch.setattr(story, "_text", lambda surface, font, text, *a, **k: (seen.append(str(text)), real(surface, font, text, *a, **k))[1])
    g.story.draw(g.game_surface, g.font, g.medium_font, g.font)
    import i18n
    assert i18n.t("story_stat_lives") in seen and i18n.t("story_shop_launcher") in seen
