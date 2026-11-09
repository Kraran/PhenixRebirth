"""The loading bar (src/loading.py): at the start of the game and at the launch of a mission of the Adventure."""
import threading
import time

import pygame
import pytest

import loading
import story_state as ss
from test_smoke import run  # noqa: F401  (fixture)

pytestmark = pytest.mark.usefixtures("training_missions")   # (the TEST missions, out of the Adventure)


class _Game:
    """Stands for the game: a canvas and a flip that counts."""

    def __init__(self):
        self.game_surface = pygame.Surface((1280, 720))
        self.flips = 0

    def _flip_frame(self, *a):
        self.flips += 1


@pytest.fixture(autouse=True)
def _screen():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


def test_report_costs_nothing_without_a_loading():
    assert loading.active() is None
    loading.report()                                            # (no error, nothing drawn)


def test_the_bar_goes_forward_step_by_step_and_ends_full():
    g = _Game()
    seen = []
    with loading.Loading(g, "arcade") as ld:
        assert loading.active() is ld
        for share in (0.3, 0.7):
            def work():
                for _ in range(5):
                    time.sleep(0.04)
                    loading.report()
                    seen.append(ld.shown)
            ld.step(share, work, 0.2)
        assert ld.done == pytest.approx(1.0)
    assert loading.active() is None
    assert seen == sorted(seen) and 0 < seen[0] < 0.3 < seen[-1] <= 1.0      # never back, never past its step
    assert all(v <= 0.3 for v in seen[:5])
    assert g.flips >= 4


def test_a_quick_loading_shows_nothing():
    g = _Game()
    with loading.Loading(g, "adventure", title="X", delay=10.0) as ld:
        ld.step(1.0, lambda: [loading.report() for _ in range(20)])
    assert g.flips == 0


def test_only_the_main_thread_draws():
    g = _Game()
    with loading.Loading(g, "arcade"):
        before = g.flips
        th = threading.Thread(target=lambda: [loading.report() for _ in range(5)])
        th.start()
        th.join()
        assert g.flips == before                              # (the warm-ups of the Lander and Scramble report too)


def test_the_keys_pressed_while_it_loads_are_dropped_but_not_closing_the_window():
    g = _Game()
    with loading.Loading(g, "arcade") as ld:
        ld.step(1.0, lambda: None)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r"))
        pygame.event.post(pygame.event.Event(pygame.QUIT))
    kinds = [e.type for e in pygame.event.get()]
    assert pygame.QUIT in kinds and pygame.KEYDOWN not in kinds


@pytest.mark.parametrize("style", ("arcade", "adventure"))
def test_both_pictures_draw(style):
    g = _Game()
    g.logo_frames = [pygame.Surface((600, 300))]
    ld = loading.Loading(g, style, title="BONUS - Scramble")
    ld.draw(0.5)
    assert g.game_surface.get_at((640, loading._bar_rect().y + 8))[:3] != (0, 0, 0)


def test_the_game_starts_behind_the_bar(run):
    g = run.game
    assert loading.active() is None                           # (it was closed once the game was ready)
    assert getattr(g, "sounds", None) is not None and g.logo_frames is not None


def _spec(g, mid):
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    g.story.open_slot(1)
    m = ss.mission_by_id(mid)
    g.story._mission = lambda: m
    g.story.mission_playable = lambda mm: True
    g.story.lander_index = 0
    return g.story._launch_selected()


@pytest.mark.parametrize("mid", ("ch1_sortie", "test_guardians", "test_scramble", "test_lander"))
def test_a_mission_starts_behind_the_bar(run, mid, monkeypatch):
    g = run.game
    spec = _spec(g, mid)
    made = []
    real = loading.Loading.__init__

    def spy(self, *a, **k):
        real(self, *a, **k)
        made.append(self)
    monkeypatch.setattr(loading.Loading, "__init__", spy)
    monkeypatch.setattr(type(g), "LOADING_DELAY", 0.0)
    # as at the first launch of a run: nothing made yet by an earlier test (the flames, the textures)
    import guardian, lander_view, scramble_view, ship_burn
    saved = [(c, dict(c)) for c in (guardian._BURN_ART, ship_burn._CACHE, lander_view._CACHE, scramble_view._TEX)]
    for c, _old in saved:
        c.clear()
    try:
        g._request_adventure(dict(spec, first_help_read=True))
    finally:
        for c, old in saved:
            for k, v in old.items():
                c.setdefault(k, v)
    assert g.started and g.adventure and g.adventure["id"] == mid
    assert len(made) == 1 and made[0].style == "adventure" and made[0].title
    assert made[0].done == pytest.approx(1.0)
    # the heavy ones (flames of the Guardians, textures of the Lander and Scramble) keep the bar moving while they work
    assert made[0].drawn >= (6 if mid != "ch1_sortie" else 2), made[0].drawn
    run.frames(2)                                             # (and it plays on)


def test_a_quick_mission_shows_no_bar(run, monkeypatch):
    g = run.game
    spec = _spec(g, "ch1_sortie")
    flips = []
    monkeypatch.setattr(loading.Loading, "draw", lambda self, p: flips.append(p))
    monkeypatch.setattr(type(g), "LOADING_DELAY", 30.0)
    g._request_adventure(dict(spec, first_help_read=True))
    assert g.started and not flips


def test_the_warm_ups_are_waited_for_not_raced(run):
    """A warm-up of the Lander holding its lock: the launch waits for it while the bar moves on, then goes."""
    import lander_view
    g = run.game
    spec = _spec(g, "test_lander")
    taken = threading.Event()

    def warm_up():                                           # (another thread holds the lock for 0.3 s)
        with lander_view._LOCK:
            taken.set()
            time.sleep(0.3)
    th = threading.Thread(target=warm_up)
    th.start()
    taken.wait()
    t0 = time.perf_counter()
    g._request_adventure(dict(spec, first_help_read=True))
    th.join()
    assert time.perf_counter() - t0 >= 0.25 and g.started
