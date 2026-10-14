"""Menu sounds (src/menu_sfx.py): every input that moves a menu makes the right sound, the game does not."""
import os

import pygame
import pytest

import menu_sfx
from settings import asset_path


class Runner:
    def __init__(self, game):
        self.game = game
        self.played = []
        real = game.sounds.play

        def spy(name, *a, **k):
            self.played.append(name)
            return real(name, *a, **k)

        game.sounds.play = spy

    def frames(self, n=1, dt=1 / 60):
        g = self.game
        for _ in range(n):
            g.dt = dt
            g.handle_events()
            g.update()
            g.draw()

    def key(self, key, frames=2):
        self.played.clear()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0, scancode=0))
        self.frames(frames)
        return [n for n in self.played if n.startswith("menu_")]

    def button(self, button, frames=2):
        self.played.clear()
        pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, button=button, joy=0, instance_id=0))
        self.frames(frames)
        return [n for n in self.played if n.startswith("menu_")]


@pytest.fixture
def run():
    from game import Game

    game = Game()
    game._intro_done = True
    game.fade_phase = None
    game.input_grace = 0.0
    r = Runner(game)
    r.frames(3)
    yield r
    game.running = False


def test_the_four_sounds_exist():
    for name in (menu_sfx.MOVE, menu_sfx.CONFIRM, menu_sfx.BACK, menu_sfx.DENY):
        path = asset_path("sounds", name + ".wav")
        assert os.path.exists(path), path
        assert os.path.getsize(path) > 4000


def test_moving_the_cursor_ticks(run):
    assert run.key(pygame.K_DOWN) == [menu_sfx.MOVE]
    assert run.game.menu_index == 1
    assert run.key(pygame.K_UP) == [menu_sfx.MOVE]


def test_changing_a_value_ticks(run):
    g = run.game
    g.menu_index = 3                                 # MODE
    before = g.play_mode
    assert run.key(pygame.K_RIGHT) == [menu_sfx.MOVE]
    assert g.play_mode != before


def test_opening_and_leaving_a_screen(run):
    g = run.game
    g.menu_index = 5                                 # OPTIONS
    assert run.key(pygame.K_RETURN) == [menu_sfx.CONFIRM]
    assert g.menu_screen == "options"
    assert run.key(pygame.K_ESCAPE) == [menu_sfx.BACK]
    assert g.menu_screen == "main"


def test_pad_buttons(run):
    g = run.game
    g.menu_index = 5
    assert run.button(0) == [menu_sfx.CONFIRM]
    assert g.menu_screen == "options"
    g.input_grace = 0.0
    assert run.button(1) == [menu_sfx.BACK]
    assert g.menu_screen == "main"


def test_greyed_addon_is_refused(run, monkeypatch):
    import addon
    monkeypatch.setattr(addon, "addon_ready", lambda: False)
    run.game.menu_index = 2
    assert run.key(pygame.K_RETURN) == [menu_sfx.DENY]
    assert run.game.menu_screen == "main"


def test_a_row_set_with_left_right_is_refused(run):
    run.game.menu_index = 4                          # DIFFICULTE: Enter does nothing
    assert run.key(pygame.K_RETURN) == [menu_sfx.DENY]


def test_quit_question(run):
    g = run.game
    assert run.key(pygame.K_ESCAPE) == [menu_sfx.BACK]
    assert g.quit_confirm
    assert run.key(pygame.K_UP) == [menu_sfx.MOVE]
    assert run.key(pygame.K_ESCAPE) == [menu_sfx.BACK]
    assert not g.quit_confirm


def test_switching_score_screens_ticks(run):
    g = run.game
    g.menu_index = 6
    assert run.key(pygame.K_RETURN) == [menu_sfx.CONFIRM]
    assert g.menu_screen == "highscores"
    assert run.key(pygame.K_RIGHT) == [menu_sfx.MOVE]
    assert g.menu_screen != "highscores"


def test_nothing_while_playing_then_pause_sounds(run):
    g = run.game
    g.play_mode = "solo"
    g._begin_run()
    run.frames(30)
    assert g.started
    assert run.key(pygame.K_LEFT) == []
    assert run.key(pygame.K_SPACE) == []
    assert run.key(pygame.K_ESCAPE) == [menu_sfx.CONFIRM]
    assert g.paused
    assert run.key(pygame.K_DOWN) == [menu_sfx.MOVE]
    assert run.key(pygame.K_ESCAPE) == [menu_sfx.BACK]
    assert not g.paused


def test_a_menu_that_changes_by_itself_is_silent(run):
    g = run.game
    run.played.clear()
    g.menu_screen = "help"                           # what the idle timer does
    run.frames(5)
    assert [n for n in run.played if n.startswith("menu_")] == []


def test_attract_demo_is_silent():
    class G:
        attract_mode = True
    assert not menu_sfx.watching(G())


def test_choose_rules():
    def snap(**kw):
        base = {"screen": (False, False, False, "main", False, False, False, None),
                "cursor": (0,), "story": None, "options": None}
        base.update(kw)
        return base

    class G:
        menu_screen = "jukebox"
        menu_index = 0

    a = snap()
    assert menu_sfx.choose(G(), a, snap(cursor=(1,)), "nav") == menu_sfx.MOVE
    assert menu_sfx.choose(G(), a, snap(screen=(False, False, False, "options", False, False, False, None)),
                           "confirm") == menu_sfx.CONFIRM
    assert menu_sfx.choose(G(), a, a, "nav") is None
    assert menu_sfx.choose(G(), a, a, "confirm") is None          # the jukebox: the music itself answers
    started = snap(screen=(True, False, False, "main", False, False, False, None))
    assert menu_sfx.choose(G(), a, started, "confirm") is None    # a game starts: its own sounds


def test_adventure_menus_tick_too(run):
    g = run.game
    g.menu_index = 1                                 # AVENTURE
    assert run.key(pygame.K_RETURN) == [menu_sfx.CONFIRM]
    assert g.menu_screen == "story_hub" and g.story.screen == "slots"
    assert run.key(pygame.K_DOWN) == [menu_sfx.MOVE]
    assert run.key(pygame.K_ESCAPE) == [menu_sfx.BACK]          # the "leave the Adventure?" question
    assert g.story.screen == "leave"
    assert run.key(pygame.K_ESCAPE) == [menu_sfx.BACK]
    assert g.story.screen == "slots"


def test_story_scene_is_silent():
    class Story:
        screen = "intro"

    class G:
        attract_mode = False
        anchor_fx = None
        started = False
        menu_screen = "story_hub"
        story = Story()

    assert not menu_sfx.watching(G())


def test_effects_volume_plays_only_its_preview(run):
    g = run.game
    g.menu_index = 5
    run.key(pygame.K_RETURN)
    assert g.menu_screen == "options"
    g.menu_index = g._options_spec().index("sfx")
    run.played.clear()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT, unicode="", mod=0, scancode=0))
    run.frames(2)
    assert "shoot" in run.played and not [n for n in run.played if n.startswith("menu_")]
    g.menu_index = g._options_spec().index("music")
    assert run.key(pygame.K_LEFT) == [menu_sfx.MOVE]
