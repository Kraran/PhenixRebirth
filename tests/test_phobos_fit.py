"""Every text of the Adventure menus fits in its plate in the 13 languages: nothing leaves the screen, two texts of one line
never touch, a long blurb is shrunk but stays readable, and the paragraphs that are cut to a few lines (Extras, hulls) do not
need more lines than they get."""
import pygame
import pytest

import i18n
import phobos_ui
import story
import story_state as ss
from settings import BASE_WIDTH
from test_smoke import run  # noqa: F401  (fixture)

MARGIN = 24                  # a text keeps this far from the edge of the screen
MIN_SHRINK = 0.70            # a line shrunk to fit is not read below this fraction of its size


@pytest.fixture(autouse=True)
def _fresh_caches():
    phobos_ui._layers.clear()
    phobos_ui._backdrops.clear()
    yield
    phobos_ui._backdrops.clear()


class Collector:
    """Records where each line of the hub is drawn (the real drawing goes on)."""

    def __init__(self, monkeypatch):
        self.rects = []
        self.shrunk = []
        real_text, real_fit = story._text, story._text_fit

        def text(surface, font, txt, color, cy, left=None, right=None, centerx=None):
            img = real_text(surface, font, txt, color, cy, left=left, right=right, centerx=centerx)
            x = left if left is not None else (right - img.get_width() if right is not None else centerx - img.get_width() // 2)
            self.rects.append((pygame.Rect(x, int(cy) - 2, img.get_width(), 4), str(txt)))
            return img

        def fit(surface, font, txt, color, cy, left, max_w, scale=1.0):
            img = real_fit(surface, font, txt, color, cy, left, max_w, scale)
            nat = story._render(font, txt, color).get_width()
            if nat and img.get_width() / nat < MIN_SHRINK:
                self.shrunk.append((round(img.get_width() / nat, 2), str(txt)[:50]))
            self.rects.append((pygame.Rect(left, int(cy) - 2, img.get_width(), 4), str(txt)))
            return img
        monkeypatch.setattr(story, "_text", text)
        monkeypatch.setattr(story, "_text_fit", fit)

    def problems(self):
        out = [("shrunk", s) for s in self.shrunk]
        for r, txt in self.rects:
            if r.x < MARGIN or r.right > BASE_WIDTH - MARGIN:
                out.append(("edge", txt, tuple(r)))
        for i, (a, ta) in enumerate(self.rects):
            for b, tb in self.rects[i + 1:]:
                if ta != tb and a.colliderect(b.inflate(-2, 10)):          # two texts on one line that touch
                    out.append(("touch", ta, tb))
        self.rects.clear()
        self.shrunk.clear()
        return out


def _hub(g):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.jump_to_act2(st)
    st["credits"] = 4200
    ss.record_kills(st, {e["id"]: 999 for e in ss.BESTIARY})             # every enemy met: the whole bestiary
    hub = g.story
    hub.state = st
    hub.screen, hub.pane = "hub", "map"
    g.started, g.menu_screen = False, "story_hub"
    return hub


def _draw(g, hub):
    hub.draw(g.game_surface, g.font, g.medium_font, g.font, body=g.read_font)


@pytest.fixture
def lang_restored():
    before = i18n.get_lang()
    yield
    i18n.set_lang(before)


@pytest.mark.parametrize("lang", i18n.LANG_CODES)
def test_the_panes_of_the_hub_fit_in_every_language(run, monkeypatch, lang, lang_restored):
    i18n.set_lang(lang)
    g = run.game
    hub = _hub(g)
    seen = Collector(monkeypatch)
    for i in range(len(hub.missions())):                                  # the blurb of each mission, under the cursor
        hub.pane, hub.map_index = "map", i
        _draw(g, hub)
        assert seen.problems() == [], ("map", i)
    hub.pane = "hangar"
    _draw(g, hub)
    assert seen.problems() == [], "hangar"
    for i in range(len(ss.bestiary_entries(hub.state))):                   # each sheet of the bestiary
        hub.pane, hub.best_index = "bestiary", i
        _draw(g, hub)
        assert seen.problems() == [], ("bestiary", i)
    for pane in ("log", "extras"):
        hub.pane = pane
        _draw(g, hub)
        assert seen.problems() == [], pane


@pytest.mark.parametrize("lang", i18n.LANG_CODES)
def test_the_screens_before_the_hub_fit_in_every_language(run, monkeypatch, lang, lang_restored):
    i18n.set_lang(lang)
    g = run.game
    hub = _hub(g)
    hub.summaries = ss.all_summaries()
    hub.new_name = "NOVA"
    hub.entry = ss.NameEntry()
    seen = Collector(monkeypatch)
    for screen in ("slots", "delete", "leave", "name", "mode", "choice", "lander_pick"):
        hub.screen, hub.choice_ask = screen, False
        _draw(g, hub)
        assert seen.problems() == [], screen
    hub.screen, hub.choice_ask = "choice", True
    _draw(g, hub)
    assert seen.problems() == [], "choice (the question)"


@pytest.mark.parametrize("lang", i18n.LANG_CODES)
def test_the_cut_paragraphs_have_the_lines_they_need(run, lang, lang_restored):
    i18n.set_lang(lang)
    t = i18n.t
    g = run.game
    hub = _hub(g)
    for door, count in (("achievements", 4), ("jukebox", 4), ("credits", 4), ("options", 4), ("addon", 5)):
        body = hub._extras_body(count)
        assert len(story._wrap(body, t("story_door_" + door), 860 - 100)) <= 2, door        # (Extras show two lines)
    body = hub._body = __import__("fonts").body(hub.AIRY_BODY)
    for hull in ss.HULLS:
        assert len(story._wrap(body, t("story_choice_%s_d" % hull), 440 - 96)) <= 5, hull   # (the hull cards show five)
    for key in ss.MODES:
        lines = story._wrap(body, t("story_mode_%s_d" % key), 376 - 80)
        assert 118 + (len(lines) - 1) * 34 <= 270 - 26, key                                 # (the mode cards are 270 high)


def test_the_collector_sees_a_text_that_is_too_long(run, monkeypatch, lang_restored):
    """(a check that checks: a locked mission with a huge label touches the name of the mission)"""
    i18n.set_lang("en")
    monkeypatch.setitem(i18n.T["story_locked"], "en", "LOCKED UNTIL SOMETHING VERY LONG HAPPENS IN THE STORY")
    g = run.game
    hub = _hub(g)
    seen = Collector(monkeypatch)
    hub.pane, hub.map_index = "map", 0
    _draw(g, hub)
    assert any(p[0] == "touch" for p in seen.problems())


@pytest.mark.parametrize("lang", i18n.LANG_CODES)
def test_no_note_of_the_map_is_cut(run, lang):
    """The blurb under the cursor is written whole: its lines, put end to end, give back all its words."""
    import story
    i18n.set_lang(lang)
    try:
        hub = _hub(run.game)
        for m in hub.missions():
            text = hub._map_note(m)[0]
            lines = hub._map_note_lines(text, 1040 - 32 - 72)
            assert " ".join(lines).split() == text.split(), (lang, m["id"], text)
            assert len(lines) <= story.MAP_NOTE_MAX
    finally:
        i18n.set_lang("fr")
