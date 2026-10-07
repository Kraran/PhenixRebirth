"""
Smoke tests: start the real game without a screen and walk through it.

They only check that nothing crashes (no exception while handling events,
updating or drawing). They do NOT judge how the game feels or looks, so a
quick manual playtest on a real PC is still needed after big changes.
Note: the game catches some errors on purpose (audio, gamepad, ...), so
those are not reported here.
"""
import pytest
import pygame

MENU_SCREENS = [
    "main", "options", "help", "achievements", "credits", "highscores",
    "jukebox", "ship_select", "story_hub", "reset_confirm", "addon",
]


class Runner:
    """Small helper that advances the game like Game.run() does, minus the
    safety net that hides exceptions."""

    def __init__(self, game):
        self.game = game

    def frames(self, n=1, dt=1 / 60):
        g = self.game
        for _ in range(n):
            g.dt = dt
            g.handle_events()
            g.update()
            g.draw()


@pytest.fixture
def run():
    from game import Game

    game = Game()
    game._intro_done = True   # skip the intro video
    game.fade_phase = None    # no fade-in blocking input
    yield Runner(game)
    game.running = False


def test_game_starts_on_main_menu(run):
    g = run.game
    assert g.menu_screen == "main"
    assert g.started is False
    run.frames(30)


@pytest.mark.parametrize("screen", MENU_SCREENS)
def test_menu_screen_draws(run, screen):
    g = run.game
    g.menu_screen = screen
    g.menu_index = 0
    run.frames(20)


def test_menu_keyboard_navigation(run):
    """Press down / enter / escape like a player would, on the main menu."""
    g = run.game
    run.frames(5)
    for key in (pygame.K_DOWN, pygame.K_DOWN, pygame.K_UP, pygame.K_ESCAPE):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0))
        run.frames(3)


def test_solo_run_plays(run):
    g = run.game
    g.play_mode = "solo"
    g._begin_run()
    run.frames(240)
    assert g.started is True
    assert g.player.alive


@pytest.mark.parametrize("stage", [1, 2, 3, 4, 5, 6, 10])
def test_every_stage_type_runs(run, stage):
    """Stages 1-4 are birds / gargoyles, stage 5 (and 10) is the boss."""
    g = run.game
    g.play_mode = "solo"
    g._begin_run()
    run.frames(5)
    g.stage = stage
    g._setup_stage(stage)
    g.stage_transition = None
    for i in range(120):
        g.player.x = 200 + (i * 7) % 880
        run.frames(1)
    if stage % 5 == 0:
        assert g.boss_saucer is not None


def test_pause_and_resume(run):
    g = run.game
    g.play_mode = "solo"
    g._begin_run()
    run.frames(60)
    g.paused = True
    run.frames(30)
    g.paused = False
    run.frames(10)


def test_coop_run_plays(run):
    g = run.game
    g.play_mode = "coop"
    g._begin_run()
    run.frames(200)
    assert g.player2 is not None


def test_hotseat_run_plays(run):
    g = run.game
    g.play_mode = "hotseat"
    g._begin_run()
    run.frames(200)
    assert g.hotseat is True


def test_game_over_card(run):
    g = run.game
    g.play_mode = "solo"
    g._begin_run()
    run.frames(30)
    for ship in g._ships():
        ship.lives = 0
    g._start_gameover_card()
    run.frames(300)
    assert g.game_over is True


def test_adventure_mission_plays(run):
    """Launch the first playable story mission from the hangar data."""
    import story

    g = run.game
    spec = None
    for i in range(len(story.MISSIONS)):
        g.story.map_index = i
        spec = g.story._launch_selected()
        if spec:
            break
    assert spec, "no playable adventure mission found"
    g._begin_adventure(spec)
    assert g.started is True
    run.frames(240)
    # An idle ship (1 life in chapter 1) may get hit: the mission then ends
    # and the game goes back to the mission map. Both outcomes are fine.
    assert g.started or g.menu_screen == "story_hub"
