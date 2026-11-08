"""The sound of the saucer in the Asteroids missions lasts as long as a saucer is on the screen: the saucer of the
Space Invaders missions (Game._sync_invader_voices) no longer cuts it, and it starts again if a saucer outlives it."""
import pytest

import story_state as ss
from test_smoke import run  # noqa: F401  (fixture)


def _launch(run, mission="ast_1"):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    g.story.map_index = [m["id"] for m in g.story.missions()].index(mission)
    g._begin_adventure(g.story._launch_selected())
    g.input_grace = 0.0
    g.player.invulnerable = 1e9
    return g


def _sounding(g):
    snd = g.sounds.sounds.get("saucer_pass")
    return snd is not None and snd.get_num_channels() > 0 and g.sounds.follow_voice(
        "saucer_pass", x=640, paused=False)


def test_the_saucer_sounds_all_the_way_across(run):
    g = _launch(run)
    if not g.sounds.enabled or g.sounds.sounds.get("saucer_pass") is None:
        pytest.skip("no sound here")
    form = g.formation
    form.saucer_in = 0.0
    run.frames(2)
    assert form.saucers
    for _ in range(60 * 3):                                            # (3 s later, still crossing: still heard)
        run.frames(1)
        if not form.saucers:
            break
    assert form.saucers and _sounding(g)


def test_a_saucer_that_outlives_its_sound_is_heard_again(run):
    g = _launch(run)
    if not g.sounds.enabled or g.sounds.sounds.get("saucer_pass") is None:
        pytest.skip("no sound here")
    form = g.formation
    form.saucer_in = 0.0
    run.frames(2)
    g.sounds.sounds["saucer_pass"].stop()                              # (its sound is over, the saucer still flies)
    run.frames(2)
    assert form.saucers and _sounding(g)
