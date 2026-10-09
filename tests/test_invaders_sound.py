"""The sounds of the Space Invaders missions: the steps (higher when faster) and the waved saucer."""
import os

import pytest

import invaders as inv
import sfx_synth as syn
from settings import asset_path
from test_smoke import run  # noqa: F401  (fixture)
from test_invaders import _formation, _playing

STEP = asset_path("sounds", "invader_step.wav")
SAUCER = asset_path("sounds", "saucer.wav")


# ------------------------------------------------------------------ the synth
def test_the_two_sounds_are_in_the_game():
    for path in (STEP, SAUCER):
        data, rate = syn.read_wav(path)
        assert len(data) > 100 and rate == 11025 and max(abs(v) for v in data) > 0.3


def test_a_higher_pitch_is_shorter_and_the_pitch_one_is_the_original():
    data, rate = syn.read_wav(STEP)
    plain = syn.resample(data, rate, rate, 1.0)
    assert plain == pytest.approx(data)
    up = syn.resample(data, rate, rate, 1.25)
    assert len(up) == pytest.approx(len(data) / 1.25, abs=2)
    assert syn.resample([], 100, 100) == []


def test_the_resampling_keeps_the_shape_of_the_sound():
    data, rate = syn.read_wav(STEP)
    big = syn.resample(data, rate, 44100, 1.0)
    assert len(big) == pytest.approx(len(data) * 4, abs=5)
    assert max(big) == pytest.approx(max(data), abs=0.05)


def test_the_saucer_sound_lasts_exactly_the_passage():
    data, rate = syn.read_wav(SAUCER)
    assert len(data) / rate < inv.SAUCER_PASS / 2                       # the original is much shorter
    for seconds in (3.0, inv.SAUCER_PASS):
        out = syn.undulating(data, rate, 22050, seconds)
        assert len(out) == int(seconds * 22050)


def test_the_saucer_sound_swells_and_never_clicks():
    data, rate = syn.read_wav(SAUCER)
    out = syn.undulating(data, rate, 22050, 6.0)
    assert abs(out[0]) < 0.05 and abs(out[-1]) < 0.01                    # soft start and end
    jump = max(abs(b - a) for a, b in zip(out, out[1:]))
    source_jump = max(abs(b - a) for a, b in zip(data, data[1:])) * (rate / 22050 + 0.2)
    assert jump <= source_jump + 0.15                                      # the loop point adds no click
    assert max(abs(v) for v in out) <= 1.0
    # it undulates: the volume is not flat
    blocks = [max(abs(v) for v in out[i:i + 2205]) for i in range(0, len(out) - 2205, 2205)]
    assert max(blocks[5:-5]) - min(blocks[5:-5]) > 0.05


def test_the_loop_fades_its_end_into_its_beginning():
    body = syn.looped([1.0] * 10 + [0.0] * 10, 5)
    assert len(body) == 15 and body[0] == pytest.approx(0.0) and body[4] == pytest.approx(0.8)
    assert body[5:] == [1.0] * 5 + [0.0] * 5
    assert body[0] == pytest.approx(0.0)                                  # starts on the end of the sound


def test_pcm_is_16_bit_and_clipped():
    raw = syn.to_pcm([0.0, 2.0, -2.0], channels=2)
    assert len(raw) == 3 * 2 * 2
    from array import array
    vals = array("h", raw)
    assert list(vals) == [0, 0, 32767, 32767, -32767, -32767]


# ------------------------------------------------------------------ the pitch of the steps
def test_the_first_pace_is_the_plain_sound_and_a_faster_march_is_a_little_higher():
    first = inv.step_pitch_index(inv.BASE_INTERVAL)
    assert first == 0
    idx = [inv.step_pitch_index(inv.BASE_INTERVAL / s) for s in (1, 2, 3, 5, 8, 20, 1000)]
    assert idx == sorted(idx) and idx[-1] == inv.STEP_PITCHES - 1 and idx[1] <= 2
    assert inv.step_pitch_index(5.0) == 0 and inv.step_pitch_index(0) == inv.STEP_PITCHES - 1
    top = 1.0 + inv.STEP_PITCH_GAP * (inv.STEP_PITCHES - 1)
    assert top <= 1.3                                                       # always "very slightly" higher


def test_the_pitch_follows_the_march_of_the_formation(run):
    f = _formation(run)
    played = []

    class Spy:
        def play(self, name, **k):
            played.append(name)

        def stop_sfx(self, *a, **k):
            played.append("stop")

    f.sounds = Spy()
    f._step()
    for e in f.enemies[1:]:
        e.alive = False
    f._step()
    assert played[0] == "invader_step_0"
    assert int(played[1].rsplit("_", 1)[1]) > 0


def test_every_step_plays_its_sound(run):
    f = _formation(run)
    played = []

    class Spy:
        def play(self, name, **k):
            played.append(name)

    f.sounds = Spy()
    for _ in range(5):
        f._step()
    assert len(played) == 5


# ------------------------------------------------------------------ in the game
def test_the_game_builds_the_sounds_when_an_invasion_starts(run):
    g, f = _playing(run)
    if not g.sounds.enabled:
        pytest.skip("no mixer")
    for i in range(inv.STEP_PITCHES):
        assert "invader_step_%d" % i in g.sounds.sounds
    length = g.sounds.sounds["saucer_pass"].get_length()
    assert length == pytest.approx(inv.SAUCER_PASS, abs=0.1)
    higher = g.sounds.sounds["invader_step_%d" % (inv.STEP_PITCHES - 1)].get_length()
    assert higher < g.sounds.sounds["invader_step_0"].get_length()


def test_the_saucer_passage_plays_the_sound_once_and_a_hit_cuts_it(run):
    g, f = _playing(run)
    played = []

    class Spy:
        def play(self, name, **k):
            played.append(name)

        def play_voice(self, name, **k):
            played.append(name)

        def stop_sfx(self, name, *a, **k):
            played.append("stop:" + name)

    f.sounds = Spy()
    f.saucer_timer = 0.0
    f.update(1 / 60, 640)
    assert played.count("saucer_pass") == 1
    f.mothership_hit(f.mothership.x)
    assert played[-1] == "stop:saucer_pass"
    f.mothership_hit(0)                                                      # nothing to hit now
    assert played.count("stop:saucer_pass") == 1


def test_the_sound_is_cut_when_the_mission_ends(run):
    g, f = _playing(run)
    calls = []
    real = g.sounds.stop_sfx
    g.sounds.stop_sfx = lambda name, *a, **k: calls.append(name)
    g._end_adventure(False)
    assert "saucer_pass" in calls


def test_the_sound_is_built_once(run):
    g, f = _playing(run)
    if not g.sounds.enabled:
        pytest.skip("no mixer")
    first = g.sounds.sounds["saucer_pass"]
    g.sounds.prepare_invader_sfx(inv.STEP_PITCHES, inv.STEP_PITCH_GAP, inv.SAUCER_PASS)
    assert g.sounds.sounds["saucer_pass"] is first


def test_repeating_a_sound_does_not_click_at_the_join():
    ramp = [i / 4000.0 for i in range(4000)]                                # a saw: the worst join
    out = syn.undulating(ramp, 4000, 4000, 6.0, wobble=0.0, tremolo=0.0, fade_in=0.01, fade_out=0.01)
    assert max(abs(b - a) for a, b in zip(out, out[1:])) < 0.2


# ------------------------------------------------------------------ stereo
class FakeSound:
    def __init__(self):
        self.faded = []

    def fadeout(self, ms):
        self.faded.append(ms)


class FakeChannel:
    def __init__(self, snd):
        self.snd, self.busy, self.paused, self.vols = snd, True, False, []

    def get_busy(self):
        return self.busy

    def get_sound(self):
        return self.snd

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False

    def set_volume(self, left, right):
        self.vols.append((left, right))


def _voice(run):
    snd = run.game.sounds
    fake = FakeSound()
    snd.sounds["saucer_pass"] = fake
    ch = FakeChannel(fake)
    snd._voices["saucer_pass"] = ch
    return snd, fake, ch


def test_the_steps_are_panned_on_the_centre_of_the_group(run):
    f = _formation(run)
    heard = []

    class Spy:
        def play(self, name, x=None, **k):
            heard.append(x)

    f.sounds = Spy()
    f._step()
    assert heard[-1] == pytest.approx((min(e.x - e.width / 2 for e in f.enemies)
                                       + max(e.x + e.width / 2 for e in f.enemies)) / 2)
    assert abs(heard[-1] - 640) < 30                                         # the grid starts in the middle
    for e in f.enemies:
        if e.col >= 3:
            e.alive = False                                                  # only the left of the grid is left
    f._step()
    assert heard[-1] < 450
    for _ in range(8):
        f._step()
    assert len(heard) == 10 and heard[-1] > heard[1]                          # the group moved right: so does the sound


def test_the_saucer_sound_follows_the_saucer_from_left_to_right(run):
    snd, fake, ch = _voice(run)
    pans = []
    for x in (0, 320, 640, 960, 1280):
        snd.follow_voice("saucer_pass", x=x)
        pans.append(ch.vols[-1])
    lefts = [l for l, r in pans]
    rights = [r for l, r in pans]
    assert lefts == sorted(lefts, reverse=True) and rights == sorted(rights)
    assert lefts[0] > rights[0] and rights[-1] > lefts[-1]
    assert pans[2][0] == pytest.approx(pans[2][1], rel=0.05)                 # centred in the middle
    assert not ch.paused and not fake.faded


def test_the_saucer_voice_waits_while_paused_and_goes_on_after(run):
    snd, fake, ch = _voice(run)
    snd.follow_voice("saucer_pass", x=500, paused=True)
    assert ch.paused
    snd.follow_voice("saucer_pass", x=500, paused=False)
    assert not ch.paused


def test_the_saucer_voice_is_cut_when_its_source_is_gone(run):
    snd, fake, ch = _voice(run)
    assert snd.follow_voice("saucer_pass", x=500, alive=False) is False
    assert fake.faded and "saucer_pass" not in snd._voices
    assert snd.follow_voice("saucer_pass", x=500) is False                    # nothing left to follow


def test_a_voice_that_finished_is_forgotten_not_cut(run):
    snd, fake, ch = _voice(run)
    ch.busy = False
    assert snd.follow_voice("saucer_pass", x=500) is False and not fake.faded
    assert "saucer_pass" not in snd._voices


def test_a_channel_reused_for_another_sound_is_not_touched(run):
    snd, fake, ch = _voice(run)
    ch.snd = FakeSound()                                                    # the channel plays something else now
    assert snd.follow_voice("saucer_pass", x=500, alive=False) is False
    assert not fake.faded and not ch.snd.faded


# ------------------------------------------------------------------ never a saucer sound without a saucer
def _sounding(run):
    g, f = _playing(run)
    snd, fake, ch = _voice(run)
    f.mothership = inv.Mothership(1)
    f.mothership.x = 300
    return g, f, snd, fake, ch


def test_the_sound_goes_on_while_the_saucer_is_there(run):
    g, f, snd, fake, ch = _sounding(run)
    g._sync_invader_voices()
    assert not fake.faded and not ch.paused and ch.vols
    f.mothership.x = 1000
    g._sync_invader_voices()
    assert ch.vols[-1][1] > ch.vols[-1][0]                                  # now on the right


@pytest.mark.parametrize("what", ["gone", "dying", "transition", "game_over", "menu"])
def test_the_sound_stops_as_soon_as_the_saucer_is_not_there(run, what):
    g, f, snd, fake, ch = _sounding(run)
    if what == "gone":
        f.mothership = None
    elif what == "dying":
        f.mothership.kill()
    elif what == "transition":
        g.stage_transition = "fly_up"
    elif what == "game_over":
        g.game_over = True
    else:
        g.started = False
    g._sync_invader_voices()
    assert fake.faded


def test_pausing_the_game_pauses_the_sound(run):
    g, f, snd, fake, ch = _sounding(run)
    g.paused = True
    g._sync_invader_voices()
    assert ch.paused and not fake.faded
    g.paused = False
    g._sync_invader_voices()
    assert not ch.paused


def test_the_sync_runs_every_frame_even_when_paused_or_in_a_menu(run):
    g, f, snd, fake, ch = _sounding(run)
    g.paused = True
    run.frames(2)
    assert ch.paused
    g.paused = False
    g.started = False
    run.frames(2)
    assert fake.faded


def test_a_mission_with_no_invasion_has_no_voice_to_follow(run):
    g = run.game
    g.sounds.follow_voice("saucer_pass", x=None, alive=False)               # nothing playing: nothing happens
    run.frames(3)


# ------------------------------------------------------------------ both ways, sound included
@pytest.mark.parametrize("d", [1, -1])
def test_the_saucer_and_its_sound_cross_the_screen_both_ways(run, d, monkeypatch):
    g, f = _playing(run)
    snd, fake, ch = _voice(run)
    started = []

    def play_voice(name, x=None):
        started.append(x)
        snd._voices[name] = ch

    monkeypatch.setattr(snd, "play_voice", play_voice)
    monkeypatch.setattr(inv.random, "choice", lambda seq: d)
    f.saucer_timer = 0.0
    f.update(1 / 60, 640)
    m = f.mothership
    assert m is not None and m.direction == d and len(started) == 1
    assert started[0] == m.x and (m.x < 0 if d > 0 else m.x > 1280)             # it comes from the side it goes away from
    pans = []
    for _ in range(60 * 10):
        g._sync_invader_voices()
        if f.mothership is None:
            break
        if 0 <= m.x <= 1280:
            l, r = ch.vols[-1]
            pans.append(r - l)
        f.update(1 / 60, 640)
        f.step_timer = -999.0
    assert f.mothership is None                                                   # it left on the other side
    g._sync_invader_voices()
    assert fake.faded                                                             # and the sound went with it
    assert pans == sorted(pans) if d > 0 else pans == sorted(pans, reverse=True)
    assert (pans[0] < 0 < pans[-1]) if d > 0 else (pans[0] > 0 > pans[-1])        # the sound goes the same way


def test_both_ways_do_happen(run):
    sides = set()
    for _ in range(60):
        f = _formation(run)
        f.saucer_timer = 0.0
        f.step_timer = -999.0
        f.update(1 / 60, 640)
        sides.add(f.mothership.direction)
    assert sides == {1, -1}
