"""Esc leaves High Scores / Achievements / Jukebox for the main menu; the ship select bar shows the colour;
the Adventure uses the same help bar, tabs and lit frames as the classic menus."""
import pygame
import pytest

import hint_bar
import i18n
import story_state as ss


class Runner:
    def __init__(self, game):
        self.game = game

    def frames(self, n=1, dt=1 / 60):
        g = self.game
        for _ in range(n):
            g.dt = dt
            g.handle_events()
            g.update()
            g.draw()

    def key(self, key, frames=2):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0, scancode=0))
        self.frames(frames)

    def button(self, button, frames=2):
        self.game.input_grace = 0.0
        pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=button, joy=0, instance_id=0))
        self.frames(frames)


@pytest.fixture
def run():
    from game import Game

    game = Game()
    game._intro_done = True
    game.fade_phase = None
    game.input_grace = 0.0
    i18n.set_lang("fr")
    r = Runner(game)
    r.frames(2)
    yield r
    game.running = False


def _open_scores(run):
    import main_menu
    g = run.game
    g.menu_index = main_menu.main_index("extras")
    run.key(pygame.K_RETURN)
    assert g.menu_screen == "extras"
    g.menu_index = main_menu.extras_index("highscores")
    run.key(pygame.K_RETURN)
    assert g.menu_screen == "highscores"


def _on_extras(g, name):
    import main_menu
    return g.menu_screen == "extras" and main_menu.EXTRAS[g.menu_index] == name


@pytest.mark.parametrize("steps", [0, 1, -1])            # High Scores, Achievements (right), Jukebox (left)
@pytest.mark.parametrize("how", ["esc", "pad_b"])
def test_esc_goes_back_up_to_extras(run, steps, how):
    """(Since the main menu has five entries, these three screens are behind EXTRAS: Esc goes back there.)"""
    g = run.game
    _open_scores(run)
    if steps:
        run.key(pygame.K_RIGHT if steps > 0 else pygame.K_LEFT)
        assert g.menu_screen == ("achievements" if steps > 0 else "jukebox")
    if how == "esc":
        run.key(pygame.K_ESCAPE)
    else:
        run.button(1)
    assert not g.quit_confirm, "the quit question must not open"
    assert _on_extras(g, ("highscores", "achievements", "jukebox")[steps])


def test_enter_also_leaves_the_achievements(run):
    g = run.game
    _open_scores(run)
    run.key(pygame.K_RIGHT)
    assert g.menu_screen == "achievements"
    run.key(pygame.K_RETURN)
    assert _on_extras(g, "achievements")


def test_esc_on_the_main_menu_still_asks_to_quit(run):
    run.key(pygame.K_ESCAPE)
    assert run.game.quit_confirm


def test_esc_during_the_jukebox_video_only_stops_it(run):
    g = run.game
    g._open_jukebox()
    g.juke_video = True
    g.juke_clip = None
    run.key(pygame.K_ESCAPE)
    assert g.menu_screen == "jukebox" and not g.juke_video


def test_ship_select_bar_shows_the_colour(run):
    g = run.game
    g.menu_screen = "ship_select"
    g.ship_select_index = 1
    items = hint_bar.menu_items(g)
    assert ("ud", "hint_colour") in items
    assert i18n.t("hint_colour") == "Couleur"


# --- the Adventure -------------------------------------------------------------------------------------------------
@pytest.fixture
def hub(run):
    from story import StoryHub
    g = run.game
    g.story = StoryHub()
    g.story.sounds = g.sounds
    ss.create_slot(1, "KRARAN", "normal")
    g.story.open_slots()
    g.menu_screen = "story_hub"
    return run


def _drawn_bar(run):
    seen = []
    real = hint_bar.draw

    def spy(game, surface, items, right=None, lit=None):
        seen.append(list(items))
        return real(game, surface, items, right=right, lit=lit)

    hint_bar.draw = spy
    try:
        run.frames(2)
    finally:
        hint_bar.draw = real
    return seen[-1] if seen else None


def test_adventure_screens_use_the_help_bar(hub):
    g = hub.game
    st = g.story
    cases = {"slots": ("ok", "hint_open"), "leave": ("ok", "hint_ok"), "mode": ("ok", "hint_start")}
    for screen, pair in cases.items():
        st.screen = screen
        st.new_name = "KRA"
        bar = _drawn_bar(hub)
        assert bar and pair in bar, (screen, bar)
    st.screen = "name"
    st.entry = ss.NameEntry("K")
    g.last_input_pad = False
    assert (None, "hint_type_name") in _drawn_bar(hub)
    g.gamepad_detected, g.last_input_pad = True, True
    bar = st.help_items(pad=True)[0]
    assert (None, "hint_type_name") not in bar and ("all", "hint_letters") in bar
    st.open_slot(1)
    st.screen = "hub"
    for pane, pair in (("map", ("ok", "hint_launch")), ("log", ("ok", "hint_replay")),
                       ("extras", ("ok", "hint_open")), ("bestiary", ("lr", "hint_tab"))):
        st.pane = pane
        bar = _drawn_bar(hub)
        assert pair in bar, (pane, bar)
    st.pane, st.zone = "hangar", "shop"
    assert ("ok", "hint_buy") in _drawn_bar(hub)
    st.zone = "slots"
    assert ("ud", "hint_workshop") in _drawn_bar(hub)
    st.paint_mode = True
    assert ("ok", "hint_paint") in _drawn_bar(hub)


def test_adventure_texts_lose_their_old_hint_lines(hub):
    g = hub.game
    st = g.story
    seen = []
    import story
    real = story._render

    def spy(font, text, color):
        seen.append(text)
        return real(font, text, color)

    story._render = spy
    try:
        st.open_slot(1)
        st.screen = "hub"
        for pane in ("map", "hangar", "log", "bestiary", "extras"):
            st.pane = pane
            hub.frames(1)
    finally:
        story._render = real
    old = {i18n.t(k) for k in ("story_hint", "story_hint_map", "story_hint_log", "story_hint_best",
                                "story_hint_extras")}
    assert not old & set(seen)
    assert not any(str(x).startswith("> ") for x in seen)
    assert i18n.t("story_tab_map") in seen                     # the tabs are still there, as plates


def test_intro_lights_a_when_the_text_is_over(hub):
    st = hub.game.story
    st.open_slot(1)
    st.start_intro()
    items, lit = st.help_items()
    assert items[0] == ("ok", "hint_next") and items[-1] == ("back", "hint_skip")
    st._intro_done = True
    lits = set()
    for ms in (0, 600):
        orig = pygame.time.get_ticks
        pygame.time.get_ticks = lambda ms=ms: ms
        try:
            lits.add(st.help_items()[1])
        finally:
            pygame.time.get_ticks = orig
    assert lits == {0, None}                                  # it blinks


def test_adventure_french_texts_have_their_accents():
    i18n.set_lang("fr")
    assert i18n.t("story_ready") == "PRÊT"
    assert i18n.t("story_locked") == "VERROUILLÉ"
    assert i18n.t("story_mode_veteran") == "VÉTÉRAN"
    assert i18n.t("story_fail_pen").startswith("Échec")


def test_drawing_the_slide_tells_when_its_text_is_over(hub):
    g = hub.game
    st = g.story
    st.open_slot(1)
    st._clip_file = lambda name: None
    st.start_intro()
    st.intro_t, st.intro_pos = 0.1, 0.0
    st.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
    assert not st._intro_done                                 # the text is still rising
    st.intro_t, st.intro_pos = 500.0, 99999.0
    st.draw(pygame.Surface((1280, 720)), g.font, g.medium_font, g.font)
    assert st._intro_done
