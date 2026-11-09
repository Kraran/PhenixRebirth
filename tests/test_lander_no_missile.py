"""The Lunar Lander missions (the landings, BONUS FINAL - Lunar Lander): no antimatter missile, so no reminder of it over
the HUD of the Lander."""
import story_state as ss
from test_smoke import run  # noqa: F401  (fixture)


def _state():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    ss.complete_ending(st)
    st["flags"][ss.ANTIMATTER_FLAG] = True
    st["flags"][ss.LAUNCHER_FLAG] = True
    st["missiles"] = 1
    return st


def _spec(run, mid, body="rock"):
    g = run.game
    st = _state()
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mid)
    return g, g.story._launch_selected(body)


def test_no_missile_in_a_lander_mission_but_in_the_others(run, monkeypatch):
    g, spec = _spec(run, "bonus_lander")
    assert ss.missile_ready(g.story.state) and not spec.get("antimatter")
    g2, other = _spec(run, "bonus_ast_endless")
    assert other.get("antimatter")


def test_the_reminder_is_never_drawn_in_the_lander(run, monkeypatch):
    import antimatter
    import i18n
    g, spec = _spec(run, "bonus_lander")
    spec["antimatter"] = True                                            # (even if one came along)
    g._begin_adventure(spec)
    g.stage_transition = None
    asked = []
    real = i18n.t
    monkeypatch.setattr(antimatter, "t", lambda k, *a, **kw: (asked.append(k), real(k, *a, **kw))[1])
    antimatter.draw_hud(g)
    assert "antimatter_hud" not in asked and "antimatter_hud_n" not in asked
