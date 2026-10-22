"""The journal in two zones: the scenes to watch again (the cursor) above what happened (it scrolls), under a line
that says what to do next."""
import pygame
import pytest

import i18n
import story
import story_state as ss
from i18n import LANG_CODES, set_lang, t
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)

BOX = pygame.Rect(80, 78, 1280 - 160, 720 - 168)
AX = BOX.right - 22
ZONE2 = BOX.y + 104 + story.LOG_REPLAY_ROWS * 34
ARROW = (255, 190, 110)


@pytest.fixture(autouse=True)
def _french_again():
    yield
    set_lang("fr")


def _hub(scenes=True, log=20):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    if scenes:
        for mid in ss.SCENES:
            ss.mark_scene_seen(st, mid)
    st["log"] = ["Ligne %d" % i for i in range(log)]
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "log"
    return hub


def _draw(hub, spy=True):
    seen = []
    real = story._text_fit
    real_text = story._text

    def fit(surface, font, text, *a, **k):
        seen.append(text)
        return real(surface, font, text, *a, **k)

    def txt(surface, font, text, *a, **k):
        seen.append(text)
        return real_text(surface, font, text, *a, **k)

    story._text_fit, story._text = fit, txt
    pygame.font.init()
    surf = pygame.Surface((1280, 720))
    try:
        hub._draw_log(surf, pygame.font.Font(None, 30), pygame.font.Font(None, 30))
    finally:
        story._text_fit, story._text = real, real_text
    return seen, surf


def test_story_entries_are_the_journal_without_the_replay_lines():
    hub = _hub()
    replay, story_lines = hub.replay_entries(), hub.story_entries()
    assert replay and story_lines
    assert len(replay) + len(story_lines) == len(hub.log_entries())
    assert all(story._is_replay(e) for e in replay) and not any(story._is_replay(e) for e in story_lines)
    assert story_lines == ["Ligne %d" % i for i in range(20)]


def test_a_fresh_journal_has_only_the_intro_replay_line():
    hub = _hub(scenes=False, log=0)
    assert hub.replay_entries() == [{"intro": True}] and hub.story_entries() == []


def test_the_two_zones_and_the_goal_are_drawn():
    hub = _hub()
    seen, _ = _draw(hub)
    nxt = ss.next_mission(hub.state, hub.missions())
    assert nxt is not None
    assert t("story_log_goal").format(name=t(nxt["title"])) in seen
    assert t("story_log_head_scenes") in seen and t("story_log_head_log") in seen


def test_no_goal_line_when_there_is_nothing_left_to_do(monkeypatch):
    hub = _hub()
    monkeypatch.setattr(ss, "next_mission", lambda *a, **k: None)
    seen, _ = _draw(hub)
    assert not any(x.startswith("OBJECTIF") for x in seen)


def test_only_a_window_of_each_zone_is_drawn():
    hub = _hub()
    seen, _ = _draw(hub)
    replays = [x for x in seen if x.startswith("Revoir")]
    logs = [x for x in seen if x.startswith("Ligne ")]
    assert len(replays) == story.LOG_REPLAY_ROWS and len(logs) == story.LOG_STORY_ROWS


def test_the_replay_window_follows_the_cursor():
    hub = _hub()
    replay = hub.replay_entries()
    for i in (0, 5, len(replay) - 1):
        hub.log_cursor = i
        seen, _ = _draw(hub)
        label = t("story_log_intro") if replay[i].get("intro") else ss.log_text(replay[i], t)
        assert label in seen, i


def test_an_empty_log_says_so():
    hub = _hub(scenes=False, log=0)
    seen, _ = _draw(hub)
    assert t("story_log_empty") in seen


def _lit(surf, x, y):
    return tuple(surf.get_at((x, y)))[:3] == ARROW


def test_arrows_tell_where_more_lines_are():
    hub = _hub()
    n = len(hub.replay_entries())
    hub.log_cursor, hub.log_scroll = 0, 0
    _, surf = _draw(hub)
    assert not _lit(surf, AX, BOX.y + 97) and _lit(surf, AX, ZONE2 - 16)                 # scenes: more below
    assert not _lit(surf, AX, ZONE2 + 43) and _lit(surf, AX, ZONE2 + 65 + 6 * 36 - 18 + 0)   # log: more below
    hub.log_cursor = n - 1
    hub.log_scroll = len(hub.story_entries()) - story.LOG_STORY_ROWS
    _, surf = _draw(hub)
    assert _lit(surf, AX, BOX.y + 97) and not _lit(surf, AX, ZONE2 - 16)
    assert _lit(surf, AX, ZONE2 + 43) and not _lit(surf, AX, ZONE2 + 65 + 6 * 36 - 18)


def test_no_arrow_when_everything_fits():
    hub = _hub(scenes=False, log=2)
    _, surf = _draw(hub)
    for y in (BOX.y + 97, ZONE2 - 16, ZONE2 + 43, ZONE2 + 65 + 6 * 36 - 18):
        assert not _lit(surf, AX, y)


@pytest.mark.parametrize("lang", LANG_CODES)
def test_every_language_draws_the_journal(lang):
    set_lang(lang)
    hub = _hub()
    seen, _ = _draw(hub)
    for key in ("story_log_head_scenes", "story_log_head_log"):
        assert t(key) in seen and t(key) != key
    assert any(x.startswith(t("story_log_goal").split("{")[0]) for x in seen)


def test_the_layout_is_four_scenes_and_six_lines_and_fits_in_the_box():
    assert (story.LOG_REPLAY_ROWS, story.LOG_STORY_ROWS) == (4, 6)
    assert ZONE2 + 62 + story.LOG_STORY_ROWS * 36 - 18 <= BOX.bottom


def test_the_scene_just_above_the_cursor_stays_in_view():
    hub = _hub()
    replay = hub.replay_entries()
    hub.log_cursor = 6
    seen, _ = _draw(hub)
    assert ss.log_text(replay[5], t) in seen and ss.log_text(replay[6], t) in seen
    assert ss.log_text(replay[4], t) not in seen


def test_a_scroll_too_far_is_brought_back_to_the_last_lines():
    hub = _hub()
    hub.log_scroll = 999
    seen, _ = _draw(hub)
    assert hub.log_scroll == len(hub.story_entries()) - story.LOG_STORY_ROWS
    assert "Ligne 19" in seen and "Ligne 13" not in seen


def test_the_empty_message_is_only_for_an_empty_log():
    hub = _hub(log=3)
    seen, _ = _draw(hub)
    assert t("story_log_empty") not in seen and "Ligne 0" in seen


def test_a_film_seen_is_a_replay_line_and_a_story_line_is_not():
    hub = _hub(scenes=False, log=0)
    film = next(iter(ss.FILMS))
    ss.mark_film_seen(hub.state, film)
    hub.state["log"] = [{"key": "story_log_clear"}]
    assert {"film": film} in hub.replay_entries() and {"film": film} not in hub.story_entries()
    assert hub.story_entries() == [{"key": "story_log_clear"}]
    assert {"key": "story_log_clear"} not in hub.replay_entries()
