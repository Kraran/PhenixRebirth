"""The Adventure intro is read aloud (French): the recorded voices, the times at which each line is said, and the text that
keeps in step with the voice (src/story.py, story_state.intro_voice, tools/make_intro_voice.py)."""
import json
import os
import sys

import numpy as np
import pygame
import pytest

import i18n
import story
import story_state as ss
from settings import asset_path
from sounds import SoundManager
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

KEYS = ("story_intro_1", "story_intro_2", "story_intro_3", "story_intro_4", "story_intro_4v")
SURF = (1280, 720)


class FakeSounds:
    """Stands for the SoundManager: records what the intro asks, plays nothing."""

    def __init__(self, ok=True):
        self.enabled, self.sfx_muted, self.ok = True, False, ok
        self.played, self.stopped, self.busy = [], 0, False

    def play_narration(self, path, volume=0.9):
        self.played.append(path)
        self.busy = self.ok
        return self.ok

    def narration_busy(self):
        return self.busy

    def stop_narration(self, fade_ms=250):
        self.stopped += 1
        self.busy = False


def _hub(mode="normal", sounds=True):
    st = ss.create_slot(1, "NOVA", mode)
    ss.save_state(ss.story_path(1), st)
    fake = FakeSounds() if sounds is True else sounds
    hub = StoryHub(sounds=fake)
    hub.open_slot(1)
    hub.start_intro()
    assert hub.screen == "intro"
    return hub, fake


def _frame(hub, run, dt=1 / 60):
    g = run.game
    hub.update(dt)
    hub.draw(pygame.Surface(SURF), g.font, g.medium_font, g.font)


def _wait(hub, run, seconds):
    for _ in range(int(seconds * 60)):
        _frame(hub, run)


# ------------------------------------------------------------------ the recordings and their marks
def test_every_slide_of_the_intro_has_a_voice_in_french():
    for mode in ("normal", "veteran"):
        for _pic, key in ss.intro_slides(mode):
            voice = ss.intro_voice(key, "fr")
            assert voice and os.path.isfile(voice["path"]) and voice["path"].endswith(key + ".ogg"), key
            assert 15.0 < voice["length"] < 60.0
    assert ss.intro_voice("story_intro_4", "fr")["path"] != ss.intro_voice("story_intro_4v", "fr")["path"]


def test_there_is_no_voice_in_the_other_languages_nor_for_other_texts():
    for lang in ("en", "de", "es", ""):
        assert ss.intro_voice("story_intro_1", lang) is None
    assert ss.intro_voice("story_scene_sortie", "fr") is None and ss.intro_voice("nothing", "fr") is None


@pytest.mark.parametrize("key", KEYS)
def test_the_marks_are_the_lines_of_the_text_in_order(key):
    voice = ss.intro_voice(key, "fr")
    lines = ss.intro_lines(i18n.t, key, "NOVA")
    last_end = 0.0
    for number, start, end in voice["marks"]:
        assert lines[number].strip(), (key, number)                 # a line with words, not a pause
        assert start >= last_end - 0.01 and end > start, (key, number)
        last_end = end
    assert [m[0] for m in voice["marks"]] == [i for i, line in enumerate(lines) if line.strip()]
    assert voice["marks"][0][1] < 1.0 and voice["marks"][-1][2] > voice["length"] - 2.0
    assert voice["marks"][-1][2] <= voice["length"] + 0.01


def test_a_damaged_table_gives_no_voice_rather_than_a_wrong_scroll(monkeypatch):
    good = {"file": "story_intro_1.ogg", "length": 20.0, "marks": [{"line": 0, "start": 0.1, "end": 2.0},
                                                                    {"line": 2, "start": 3.0, "end": 9.0}]}
    monkeypatch.setattr(ss, "_VOICE_TABLE", {"table": {"story_intro_1": good}})
    assert ss.intro_voice("story_intro_1", "fr")["marks"] == [(0, 0.1, 2.0), (2, 3.0, 9.0)]
    bad = [
        dict(good, marks=[{"line": 2, "start": 3.0, "end": 9.0}, {"line": 0, "start": 0.1, "end": 2.0}]),     # not in order
        dict(good, marks=[{"line": 0, "start": 0.1, "end": 2.0}, {"line": 2, "start": 1.0, "end": 9.0}]),     # goes back in time
        dict(good, marks=[{"line": 0, "start": 2.0, "end": 1.0}]),                                           # ends before it starts
        dict(good, marks=[]), dict(good, length=0), dict(good, file="no_such_file.ogg"),
        dict(good, marks=[{"line": 0, "start": 0.1, "end": 99.0}]),                                          # after the recording
        {"file": "story_intro_1.ogg"}, None, "x",
    ]
    for entry in bad:
        monkeypatch.setattr(ss, "_VOICE_TABLE", {"table": {"story_intro_1": entry}})
        assert ss.intro_voice("story_intro_1", "fr") is None, entry


def test_a_missing_or_broken_marks_file_gives_no_voice(monkeypatch, tmp_path):
    for content in (None, "not json at all {", json.dumps(["not", "a", "dict"])):
        path = tmp_path / "marks.json"
        if content is None:
            if path.exists():
                path.unlink()
        else:
            path.write_text(content, encoding="utf-8")
        monkeypatch.setattr(ss, "_VOICE_TABLE", {})
        monkeypatch.setattr(ss, "asset_path", lambda *parts, p=str(path): p)
        assert ss.intro_voice("story_intro_1", "fr") is None, content


@pytest.mark.parametrize("key", KEYS)
def test_the_recording_is_what_the_marks_say(run, key):
    """Each line is spoken in its interval (the middle of it is not silent) and the length is that of the file."""
    voice = ss.intro_voice(key, "fr")
    snd = pygame.mixer.Sound(voice["path"])
    assert abs(snd.get_length() - voice["length"]) < 0.1
    freq, _fmt, chans = pygame.mixer.get_init()
    x = pygame.sndarray.array(snd).astype(np.float32)
    x = np.abs(x if x.ndim == 1 else x.max(axis=1)) / 32768.0
    hop = int(freq * 0.05)
    env = np.array([x[i:i + hop].mean() for i in range(0, len(x) - hop, hop)])
    loud = float(np.percentile(env, 90))
    for number, start, end in voice["marks"]:
        margin = min(0.3, (end - start) / 4)                                       # (a line can be a very short one)
        mid = env[int((start + margin) / 0.05):max(int((end - margin) / 0.05), int((start + margin) / 0.05) + 1)]
        assert mid.size and float(np.mean(mid)) > 0.25 * loud, (key, number, start, end)
    assert float(env[:int(0.1 / 0.05)].mean()) < 0.3 * loud                       # no long silence at the start either
    assert abs(float(np.sqrt((x[x > 0.02] ** 2).mean()))) > 0.03                  # the recordings are not faint


def test_the_voices_have_the_same_level():
    levels = []
    for key in KEYS:
        voice = ss.intro_voice(key, "fr")
        snd = pygame.mixer.Sound(voice["path"])
        x = pygame.sndarray.array(snd).astype(np.float32) / 32768.0
        x = x if x.ndim == 1 else x.max(axis=1)
        levels.append(20 * np.log10(float(np.sqrt((x[np.abs(x) > 0.02] ** 2).mean()))))
    assert max(levels) - min(levels) < 2.0, levels


# ------------------------------------------------------------------ the sound manager
def test_the_sound_manager_plays_and_stops_a_narration(run):
    sounds = run.game.sounds
    path = ss.intro_voice("story_intro_1", "fr")["path"]
    assert sounds.play_narration(path) is True
    assert sounds.narration_busy() and sounds.vo_is_busy()                           # the music steps back, as for the announcer
    sounds.stop_narration(fade_ms=0)
    assert not sounds.narration_busy() and getattr(sounds, "_narration", None) is None
    sounds.stop_narration()                                                          # twice is harmless
    assert sounds.play_narration(os.path.join(os.path.dirname(path), "nothing.ogg")) is False
    assert sounds.play_narration("") is False and not sounds.narration_busy()
    sounds.sfx_muted = True
    assert sounds.play_narration(path) is False
    sounds.sfx_muted = False
    sounds.enabled = False
    assert sounds.play_narration(path) is False
    sounds.enabled = True


def test_another_sound_on_the_announcer_channel_is_not_taken_for_the_narration(run):
    sounds = run.game.sounds
    sounds.play_narration(ss.intro_voice("story_intro_1", "fr")["path"])
    sounds.play_vo("gameover_vo")                                                    # takes the channel over
    assert not sounds.narration_busy()
    sounds.stop_narration(fade_ms=0)
    sounds.stop_narration(fade_ms=0)


# ------------------------------------------------------------------ the intro with a voice
def test_the_voice_starts_after_a_moment_and_with_the_right_recording(run):
    hub, fake = _hub()
    _wait(hub, run, story.VOICE_DELAY - 0.2)
    assert fake.played == []
    _wait(hub, run, 0.4)
    assert fake.played == [ss.intro_voice("story_intro_1", "fr")["path"]]
    _wait(hub, run, 3.0)
    assert len(fake.played) == 1                                                     # once


def test_each_slide_has_its_voice_and_the_one_before_is_stopped(run):
    hub, fake = _hub()
    for key in KEYS[:4]:
        _wait(hub, run, story.VOICE_DELAY + 0.3)
        assert fake.played[-1] == ss.intro_voice(key, "fr")["path"]
        stopped = fake.stopped
        hub.intro_t = 60.0
        hub.confirm()
        if hub.screen == "intro":
            assert fake.stopped == stopped + 1
    assert hub.screen == "hub" and not fake.busy                                    # the story is over, the voice with it
    assert len(fake.played) == 4


def test_the_veteran_hears_the_death_of_kamarasov(run):
    hub, fake = _hub("veteran")
    for _ in range(3):
        _wait(hub, run, story.VOICE_DELAY + 0.3)
        hub.intro_t = 60.0
        hub.confirm()
    _wait(hub, run, story.VOICE_DELAY + 0.3)
    assert fake.played[-1] == ss.intro_voice("story_intro_4v", "fr")["path"]
    assert fake.played[2] == ss.intro_voice("story_intro_3", "fr")["path"]


def test_skipping_the_intro_stops_the_voice(run):
    hub, fake = _hub()
    _wait(hub, run, 3.0)
    assert fake.busy
    hub.intro_t = 60.0
    hub.back()
    assert hub.screen == "hub" and not fake.busy and hub._voice is None


def test_leaving_the_intro_in_any_other_way_stops_the_voice_too(run):
    hub, fake = _hub()
    _wait(hub, run, 3.0)
    hub.screen = "hub"
    hub.update(0.016)
    assert not fake.busy and hub._voice is None


def test_a_replayed_intro_is_read_again(run):
    hub, fake = _hub()
    _wait(hub, run, 3.0)
    hub.intro_t = 60.0
    hub.back()
    hub.start_intro(back_to="log")
    _wait(hub, run, story.VOICE_DELAY + 0.3)
    assert len(fake.played) == 2 and fake.played[0] == fake.played[1]


@pytest.mark.parametrize("why", ["no sounds", "no audio", "muted", "english", "refused"])
def test_without_a_voice_the_text_goes_at_its_own_speed(run, monkeypatch, why):
    fake = FakeSounds(ok=(why != "refused"))
    hub, _ = _hub(sounds=None if why == "no sounds" else fake)
    if why == "no audio":
        fake.enabled = False
    if why == "muted":
        fake.sfx_muted = True
    if why == "english":
        monkeypatch.setattr(story, "get_lang", lambda: "en")
    _wait(hub, run, 3.0)
    p0 = hub.intro_pos
    _wait(hub, run, 2.0)
    assert abs((hub.intro_pos - p0) / 2.0 - story.INTRO_SPEED) < 3.0, why
    if why != "refused":
        assert fake.played == []
    else:
        assert len(fake.played) == 1                                                 # asked once, not every frame
        assert hub._voice is None


def test_the_text_is_in_place_when_the_voice_starts_and_follows_it(run):
    hub, fake = _hub()
    _wait(hub, run, story.VOICE_DELAY)
    first = hub._intro_spans[hub._intro_key][0]
    top = story.BASE_HEIGHT - hub.intro_pos
    assert 400 < top + first[0] < 620, top                                          # the first line is on screen when it is said
    _wait(hub, run, 6.0)
    spans = hub._intro_spans[hub._intro_key]
    voice = ss.intro_voice("story_intro_1", "fr")
    t = hub._voice_t
    number = [n for n, s, e in voice["marks"] if s <= t <= e][0]
    on_screen = story.BASE_HEIGHT - hub.intro_pos + spans[number][0]
    assert abs(on_screen - story.VOICE_READ_Y) < 140, (t, number, on_screen)


@pytest.mark.parametrize("mode", ["normal", "veteran"])
def test_the_line_being_said_is_on_screen_all_through_every_slide(run, mode):
    """The whole intro, frame by frame: at every moment of a line, that line is in the window where the text shows."""
    hub, fake = _hub(mode)
    g = run.game
    surf = pygame.Surface(SURF)
    for _ in range(4):
        voice = ss.intro_voice(hub.intro_slides[hub.intro_index][1], "fr")
        checked = {}
        frames = 0
        while (hub._voice is None or hub._voice_t < voice["length"] - 0.3) and frames < 60 * 70:
            hub.update(1 / 30)
            hub.draw(surf, g.font, g.medium_font, g.font)
            frames += 1
            if hub._voice is None or hub._voice_curve is None:
                continue
            _block, height = hub._intro_block(g.font)
            top = hub._intro_top(height)
            spans = hub._intro_spans[hub._intro_key]
            for number, start, end in voice["marks"]:
                margin = min(0.4, (end - start) / 4)
                if start + margin <= hub._voice_t <= end - margin:
                    y0, y1 = top + spans[number][0], top + spans[number][1]
                    # visible window of the text: 90 .. INTRO_END_Y; the line must have at least some of its body in it
                    assert y1 > 100 and y0 < story.INTRO_END_Y - 10, (mode, number, hub._voice_t, y0, y1)
                    checked[number] = checked.get(number, 0) + 1
        assert set(checked) == {m[0] for m in voice["marks"]}, (mode, checked)
        hub.intro_t = 60.0
        hub.confirm()
    assert hub.screen == "hub"


@pytest.mark.parametrize("key,mode", [("story_intro_1", "normal"), ("story_intro_2", "normal"), ("story_intro_4v", "veteran")])
def test_the_point_being_said_stays_near_the_reading_line_and_the_text_rises_until_the_voice_ends(run, key, mode):
    hub, fake = _hub(mode)
    g = run.game
    surf = pygame.Surface(SURF)
    while hub.intro_slides[hub.intro_index][1] != key:
        hub.intro_t = 60.0
        hub.confirm()
    hub.intro_t = 0.0
    hub._reset_slide()
    voice = ss.intro_voice(key, "fr")
    worst, rising = 0.0, []
    for _ in range(int((voice["length"] + story.VOICE_DELAY) * 30)):
        hub.update(1 / 30)
        hub.draw(surf, g.font, g.medium_font, g.font)
        if hub._voice is None or hub._voice_t < story.VOICE_LEAD or hub._voice_t > voice["length"]:
            continue
        spot = hub._voice_target(hub.intro_t, hub._voice_t)                        # where the text should be
        worst = max(worst, abs(hub.intro_pos - spot))
        rising.append((hub._voice_t / voice["length"], hub.intro_pos))
    assert worst < 12.0, worst                                                       # in step with the voice, to a few pixels
    late = [p for f, p in rising if f > 0.7]
    assert late[-1] > late[0] + 30, (late[0], late[-1])                              # still rising in the last 30 % of the voice
    height = hub._intro_block(g.font)[1]
    assert hub._intro_top(height) == story.BASE_HEIGHT - hub.intro_pos               # drawn where it is, not held at a resting place
    end_top = hub._intro_top(height) + hub._intro_spans[hub._intro_key][max(hub._intro_spans[hub._intro_key])][1]
    assert 380 < end_top < 620, end_top                                              # the last line ends in the lower half


def test_the_text_does_not_say_it_is_finished_before_the_voice_is(run):
    hub, fake = _hub()
    for _ in range(int(10 * 60)):
        _frame(hub, run)
    assert hub._voice is not None and not hub.intro_finished_scrolling(hub._intro_block(run.game.font)[1])
    for _ in range(int(15 * 60)):
        _frame(hub, run)
    assert hub.intro_finished_scrolling(hub._intro_block(run.game.font)[1])


def test_finished_means_the_voice_has_said_it_all_wherever_the_text_is(run):
    hub, fake = _hub()
    _wait(hub, run, 4.0)
    height = hub._intro_block(run.game.font)[1]
    length = hub._voice["length"]
    hub.intro_pos = 5000.0                                                           # the text is far up: not a reason to be done
    hub._voice_t = length - 5.0
    assert not hub.intro_finished_scrolling(height)
    hub.intro_pos = 0.0                                                              # the text is still low, the voice is done
    hub._voice_t = length - 0.2
    assert hub.intro_finished_scrolling(height)
    hub._voice_t = length - 0.6
    assert not hub.intro_finished_scrolling(height)


def test_down_runs_the_text_ahead_and_it_comes_back_to_the_voice(run):
    hub, fake = _hub()
    _wait(hub, run, 8.0)
    on_curve = hub.intro_pos
    for _ in range(40):                                                              # Down held for 2/3 of a second
        hub.update(1 / 60, scroll=1)
        hub.draw(pygame.Surface(SURF), run.game.font, run.game.medium_font, run.game.font)
    assert hub.intro_pos > on_curve + 40
    _wait(hub, run, 3.0)
    want = hub._voice_target(hub.intro_t, hub._voice_t)
    assert abs(hub.intro_pos - want) < 15, (hub.intro_pos, want)


def test_when_the_recording_stops_the_text_goes_to_the_end_of_the_voice(run):
    hub, fake = _hub()
    _wait(hub, run, 4.0)
    fake.busy = False                                                                # the recording ended (or was cut off)
    hub.update(1 / 60)
    assert hub._voice_t >= hub._voice["length"]
    for _ in range(300):
        _frame(hub, run)
    assert hub.intro_finished_scrolling(hub._intro_block(run.game.font)[1])


# ------------------------------------------------------------------ the tool
def _tool():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
    import make_intro_voice
    return make_intro_voice


def test_the_tool_puts_the_line_changes_on_the_pauses():
    tool = _tool()
    lines = [(0, "a" * 50), (2, "b" * 100), (4, "c" * 50)]
    # 0.06 s a character: 3 s, 6 s, 3 s, with pauses of 0.8 s between: the voice starts at 0.1
    pauses = [(0.0, 0.1), (3.1, 3.9), (9.9, 10.7), (13.7, 13.9)]
    got = tool.match(lines, pauses, 0.1, 13.7)
    assert [round(a, 1) for a, _b in got] == [0.1, 3.9, 10.7]
    assert [round(b, 1) for _a, b in got] == [3.1, 9.9, 13.7]


def test_the_tool_ignores_a_pause_inside_a_line_and_keeps_the_order():
    tool = _tool()
    lines = [(0, "a" * 50), (2, "b" * 100)]
    pauses = [(0.0, 0.1), (1.0, 1.4), (3.2, 4.0), (8.0, 8.5), (10.0, 10.2)]       # two pauses inside the lines
    got = tool.match(lines, pauses, 0.1, 10.0)
    assert abs(got[1][0] - 4.0) < 0.01 and got[0][1] == 3.2


def test_the_tool_prefers_a_real_pause_to_a_breath_a_little_nearer_the_estimate():
    tool = _tool()
    lines = [(0, "a" * 50), (2, "b" * 100)]
    # the first line should end near 3.1: a breath of 0.2 s at 3.0, a real pause of 0.8 s at 4.0
    got = tool.match(lines, [(0.0, 0.1), (2.8, 3.0), (4.0, 4.8), (9.0, 9.2)], 0.1, 9.0)
    assert abs(got[1][0] - 4.8) < 0.01, got


def test_the_tool_has_a_time_for_a_line_change_without_an_audible_pause():
    tool = _tool()
    lines = [(0, "a" * 60), (2, "b" * 40), (3, "c" * 60)]
    got = tool.match(lines, [(0.0, 0.1), (5.0, 5.5)], 0.1, 10.0)                   # only one pause for two changes
    starts = [a for a, _b in got]
    assert starts == sorted(starts) and len(set(starts)) == 3
    assert any(abs(a - 5.5) < 0.01 for a in starts)


def test_the_tool_does_not_read_the_name_of_the_pilot():
    tool = _tool()
    lines = tool.spoken_lines("story_intro_4")
    shown = ss.intro_lines(i18n.t, "story_intro_4", "NOVA")
    assert [i for i, _s in lines] == [i for i, line in enumerate(shown) if line.strip()] and all(s for _i, s in lines)
    assert "{name}" not in lines[-1][1] and lines[-1][1].endswith("moi, j'en suis maintenant certain.")


# ------------------------------------------------------------------ the credit (the free plan of the voice service asks for it)
def test_the_credits_name_the_voice_service_in_every_language():
    before = i18n.get_lang()
    try:
        for code in i18n.LANG_CODES:
            i18n.set_lang(code)
            lines = i18n.get_credits_lines()
            at = [i for i, (_kind, text) in enumerate(lines) if "elevenlabs.io" in text]
            assert len(at) == 1 and lines[at[0] - 1][0] == "header", code          # a line under its own header
    finally:
        i18n.set_lang(before)
