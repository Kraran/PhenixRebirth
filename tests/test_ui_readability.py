"""Preflight controls, deliberate VN answers, and readable combat layering."""
from types import SimpleNamespace

import pygame
import pytest

import announce
import draw_frame
from story import StoryHub
import story_state as ss
import story_vn


@pytest.mark.parametrize("fps", [30, 60, 120, 144])
def test_repeated_confirms_cannot_skip_the_vn_answer_delay(monkeypatch, fps):
    hub = StoryHub()
    hub.state = ss.default_state()
    hub.start_vn("vn_1")
    monkeypatch.setattr(hub, "vn_pages", lambda: [[(False, "Choose deliberately.")]])
    saved = []
    monkeypatch.setattr(hub, "save", lambda: saved.append(True))
    hub.confirm()  # reveal last page immediately
    assert hub.vn_ready()
    for _ in range(30):
        hub.confirm()
    assert not story_vn.answered(hub.state, "vn_1") and not saved
    hub.nav_v(1)  # navigation is available during the guard
    choice = hub.vn_index
    elapsed = 0
    dt = 1 / fps
    while elapsed + dt < hub.VN_CHOICE_DELAY - 1e-8:
        hub.update(dt)
        elapsed += dt
        hub.confirm()
        assert not saved
    hub.update(hub.VN_CHOICE_DELAY - elapsed + 1e-6)
    hub.confirm()
    assert story_vn.pick(hub.state, "vn_1") == choice and saved == [True]


def test_natural_typing_also_waits_after_the_answers_appear(monkeypatch):
    hub = StoryHub()
    hub.state = ss.default_state()
    hub.start_vn("vn_1")
    monkeypatch.setattr(hub, "vn_pages", lambda: [[(False, "Hi")]])
    while not hub.vn_ready():
        hub.update(0.01)
    assert hub.vn_choice_wait == hub.VN_CHOICE_DELAY
    assert hub.help_items() == ([("ud", "hint_choose")], None)
    hub.confirm()
    assert not story_vn.answered(hub.state, "vn_1")
    hub.start_vn("vn_2")  # every new scene resets the guard
    assert hub.vn_choice_wait == hub.VN_CHOICE_DELAY


def test_combat_layers_put_enemies_and_shots_above_hud_and_announcements_and_the_saucer_body_under_them(monkeypatch):
    surface = pygame.Surface((1280, 720))
    events = []
    rect = pygame.Rect(15, 15, 40, 40)

    def paint(name, colour):
        def draw(target):
            events.append(name)
            target.fill(colour, rect)
        return draw

    hud = paint("hud", (80, 120, 240))
    monkeypatch.setattr(draw_frame, "draw_hud", lambda game: hud(game.game_surface))
    monkeypatch.setattr(draw_frame.escort, "draw", lambda *a: None)
    game = SimpleNamespace(
        game_surface=surface, game_over=False, paused=False, hotseat_wait=False,
        _draw_cheat_message=lambda: paint("announcement", (20, 20, 20))(surface),
        boss_saucer=SimpleNamespace(draw_body=paint("boss body", (90, 160, 50)),
                                    draw_shots=paint("boss shots", (200, 200, 30))),
        formation=SimpleNamespace(draw=paint("birds and shots", (240, 60, 20))),
        loot=None, explosions=[], tesla_fx=None, _ships=lambda: [],
    )
    draw_frame.draw_play(game)
    assert events == ["boss body", "hud", "announcement", "boss shots", "birds and shots"]
    assert game._announce_done
    assert tuple(surface.get_at((25, 25)))[:3] == (240, 60, 20)


def test_all_announcement_sizes_are_more_transparent_without_mutating_cached_text():
    pygame.font.init()
    font = pygame.font.Font(None, 32)
    images = {}

    def text(_font, words, colour):
        key = words, colour
        if key not in images:
            images[key] = font.render(words, True, colour)
        return images[key]

    game = SimpleNamespace(font=font, medium_font=font, big_font=font, menu_font=font, _txt=text)
    surface = pygame.Surface((1280, 720))
    for level, old_alpha in (("major", 185), ("standard", 140), ("discreet", 100)):
        shared = text(font, "NOTICE", announce.INFO)
        before = shared.get_alpha()
        img = announce.draw(game, surface, "NOTICE", "info", level, (640, 360))
        assert announce.LEVELS[level]["plate"] < old_alpha
        assert img.get_alpha() == round(255 * 0.92)
        assert shared.get_alpha() == before


def test_preflight_confirmation_is_separate_from_the_launch_click():
    hub = StoryHub()
    hub.state = ss.default_state()
    hub.show_first_help({"launch": True, "id": "ch1_sortie"})
    for _ in range(20):
        assert hub.confirm() is None
    hub.update(0.25)
    hub.update(0.25)
    spec = hub.confirm()
    assert spec == {"launch": True, "id": "ch1_sortie", "first_help_read": True}
    assert hub.screen == "hub" and hub.first_help_spec is None


def test_preflight_can_be_cancelled_without_launching():
    hub = StoryHub()
    hub.state = ss.default_state()
    hub.show_first_help({"launch": True, "id": "ch1_sortie"})
    assert hub.back()
    assert hub.screen == "hub" and hub.pane == "map"
    assert hub.first_help_spec is None


def test_preflight_draws_controls_without_any_combat(monkeypatch):
    import help_screen
    import story
    pygame.font.init()
    font = pygame.font.Font(None, 28)
    hub = StoryHub()
    hub.show_first_help({"launch": True, "id": "ch1_sortie"})
    monkeypatch.setattr(hub, "_ensure_art", lambda: None)
    seen = []
    real = story._text

    def text(surface, font, words, *args, **kwargs):
        seen.append(words)
        return real(surface, font, words, *args, **kwargs)

    monkeypatch.setattr(story, "_text", text)
    hub.draw(pygame.Surface((1280, 720)), font, font, font)
    assert hub.covers_screen()
    for line in help_screen.help_lines("story_first_help"):
        assert " ".join(line.split()) in " ".join(" ".join(seen).split())
