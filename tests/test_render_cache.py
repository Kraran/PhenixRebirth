"""Rendering is cheap: text lines, slide backdrops and the saucer are prepared once, not every frame.

Each speed-up has to give exactly the same picture as before, so these tests compare the pixels with the
slow way of drawing it as well as checking that the work really is not repeated."""
import pygame
import pytest

import invaders as inv
import story
import story_state as ss
from settings import BASE_HEIGHT, BASE_WIDTH
from story import INTRO_END_Y, INTRO_TEXT_W, StoryHub
from test_smoke import run  # noqa: F401  (fixture)


def _hub_on_intro():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.start_intro()
    return hub


def _font():
    pygame.font.init()
    return pygame.font.Font(None, 28)


# --- text lines ---
def test_a_line_is_rendered_once_and_drawn_again_for_free(monkeypatch):
    font = _font()
    calls = []
    real = font.render

    class Spy:
        def __getattr__(self, n):
            return getattr(font, n)

        def render(self, *a):
            calls.append(a)
            return real(*a)

    spy = Spy()
    surf = pygame.Surface((300, 60))
    story._TEXTS.clear()
    for _ in range(5):
        story._text(surf, spy, "CACHE ME", (200, 100, 50), 30, left=4)
    assert len(calls) == 1


def test_a_new_text_or_colour_is_rendered_again():
    font = _font()
    surf = pygame.Surface((300, 60))
    story._TEXTS.clear()
    a = story._text(surf, font, "ONE", (255, 0, 0), 30, left=0)
    b = story._text(surf, font, "TWO", (255, 0, 0), 30, left=0)
    c = story._text(surf, font, "ONE", (0, 255, 0), 30, left=0)
    assert a is not b and a is not c
    row = [c.get_at((x, y))[:3] for x in range(c.get_width()) for y in range(c.get_height())]
    assert (0, 255, 0) in row and (255, 0, 0) not in row         # the green line is not the cached red one


def test_a_cached_line_looks_exactly_like_a_fresh_one():
    font = _font()
    story._TEXTS.clear()
    a, b = pygame.Surface((300, 60)), pygame.Surface((300, 60))
    story._text(pygame.Surface((300, 60)), font, "Same pixels", (230, 232, 244), 30, centerx=150)   # fills the cache
    story._text(a, font, "Same pixels", (230, 232, 244), 30, centerx=150)       # this one comes from the cache
    fresh = font.render("Same pixels", True, (230, 232, 244))
    b.blit(fresh, (150 - fresh.get_width() // 2, story._cap_top(font, 30)))
    assert pygame.image.tostring(a, "RGB") == pygame.image.tostring(b, "RGB")


def test_a_fitted_line_does_not_spoil_the_cached_one():
    font = _font()
    surf = pygame.Surface((400, 60))
    story._TEXTS.clear()
    story._text_fit(surf, font, "A LONG LINE THAT HAS TO BE SHRUNK", (255, 255, 255), 30, 0, 80)
    full = story._text(surf, font, "A LONG LINE THAT HAS TO BE SHRUNK", (255, 255, 255), 30, left=0)
    assert full.get_width() == font.size("A LONG LINE THAT HAS TO BE SHRUNK")[0]     # still the full-size picture


# --- slide screens ---
def _reference_intro_text(surface, block, top, x):
    """The way the scrolling text used to be drawn: a full transparent window, masked, then blitted."""
    view = pygame.Surface((INTRO_TEXT_W, BASE_HEIGHT), pygame.SRCALPHA)
    view.blit(block, (0, top))
    mask = pygame.Surface((INTRO_TEXT_W, BASE_HEIGHT), pygame.SRCALPHA)
    for y in range(BASE_HEIGHT):
        a = y / 90.0 if y < 90 else (max(0.0, 1.0 - (y - INTRO_END_Y) / 52.0) if y > INTRO_END_Y else 1.0)
        pygame.draw.line(mask, (255, 255, 255, int(255 * a)), (0, y), (INTRO_TEXT_W, y))
    view.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(view, (x, 0))


@pytest.mark.parametrize("top", [-900, -300, -40, 0, 40, 200, 380, 560, 620, 700, 719])
def test_the_scrolling_text_looks_the_same_as_the_slow_way(run, top):
    hub = _hub_on_intro()
    block, _h = hub._intro_block(run.game.font)
    x = (BASE_WIDTH - INTRO_TEXT_W) // 2
    back = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    back.fill((40, 60, 110))
    fast, slow = back.copy(), back.copy()
    hub._draw_intro_text(fast, block, top, x)
    _reference_intro_text(slow, block, top, x)
    a, b = pygame.image.tostring(fast, "RGB"), pygame.image.tostring(slow, "RGB")
    assert max(abs(p - q) for p, q in zip(a, b)) <= 1


def test_the_scrolling_text_keeps_the_clip_of_the_screen(run):
    hub = _hub_on_intro()
    block, _h = hub._intro_block(run.game.font)
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    clip = pygame.Rect(10, 20, 500, 400)
    surf.set_clip(clip)
    hub._draw_intro_text(surf, block, 100, 210)
    assert surf.get_clip() == clip


def test_the_dark_band_is_baked_into_the_backdrop_once(run):
    hub = _hub_on_intro()
    pic = hub.intro_slides[0][0]
    back = hub._intro_backdrop(pic)
    assert hub._intro_backdrop(pic) is back
    plain = hub._intro_picture(pic)
    inside = (BASE_WIDTH // 2, 300)
    outside = (20, 300)
    assert back.get_at(outside)[:3] == plain.get_at(outside)[:3]              # the band stops short of the sides
    a = 120 / 255.0
    for got, was in zip(back.get_at(inside)[:3], plain.get_at(inside)[:3]):
        assert abs(got - was * (1 - a)) <= 2
    assert hub._intro_picture(pic).get_at(inside) == plain.get_at(inside)      # and the picture itself is untouched


def test_an_intro_frame_allocates_no_new_picture(run, monkeypatch):
    g = run.game
    hub = _hub_on_intro()
    screen = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    hub.intro_t = 0.3                                                    # still fading in from black
    hub.draw(screen, g.font, g.medium_font, g.font)                      # first frame builds the caches
    made = []
    real = pygame.Surface

    class Counting(real):
        def __init__(self, *a, **k):
            made.append(a)
            super().__init__(*a, **k)

    monkeypatch.setattr(story.pygame, "Surface", Counting)
    for t in (0.35, 0.4, 0.5):
        hub.intro_t = t
        hub.draw(screen, g.font, g.medium_font, g.font)
    big = [a for a in made if a and a[0][0] * a[0][1] > 20000]
    assert big == []                                                     # nothing big is built per frame


def test_the_slide_covers_the_screen_but_the_hub_does_not():
    hub = _hub_on_intro()
    assert hub.covers_screen() is True
    hub.screen = "hub"
    assert hub.covers_screen() is False
    hub.screen = "slots"
    assert hub.covers_screen() is False


def test_the_starfield_is_not_drawn_under_a_slide(run, monkeypatch):
    import draw_frame
    g = run.game
    g.menu_screen, g.started = "story_hub", False
    g.story.open_slots()
    calls = []
    real = draw_frame.draw_background
    monkeypatch.setattr(draw_frame, "draw_background", lambda game: (calls.append(1), real(game))[1])
    g.story.screen = "hub"
    g._draw_canvas()
    assert calls == [1]                                                  # menus still show the stars through
    g.story.screen = "intro"
    g.story.intro_slides = [("epave_shield", "story_scene_dome_1")]
    g.story.intro_index = 0
    g._draw_canvas()
    assert calls == [1]                                                  # the slide paints over them: skipped


def test_a_slide_frame_has_the_same_pixels_without_the_starfield(run, monkeypatch):
    """Skipping the starfield changes nothing on screen: the picture covers every pixel."""
    import draw_frame
    g = run.game
    g.menu_screen, g.started = "story_hub", False
    g.story.open_slots()
    g.story.start_intro()
    g.story.intro_pos, g.story.intro_t = 300, 5.0
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: 0)
    g._draw_canvas()
    quick = pygame.image.tostring(g.game_surface, "RGB")
    g.game_surface.fill((255, 0, 255))                                   # whatever was behind
    g.story.draw(g.game_surface, g.font, g.medium_font, g.font)
    assert pygame.image.tostring(g.game_surface, "RGB") == quick


# --- the saucer ---
def test_the_saucer_is_painted_when_the_mission_starts_not_when_it_appears(monkeypatch):
    inv._CACHE.pop("saucer", None)
    built = []
    real = inv._saucer_frame
    monkeypatch.setattr(inv, "_saucer_frame", lambda level: (built.append(level), real(level))[1])
    inv.InvaderFormation(1)
    assert len(built) == inv.SAUCER_PULSE_FRAMES
    inv.Mothership(1)
    inv.saucer_image(3)
    assert len(built) == inv.SAUCER_PULSE_FRAMES                         # nothing more to paint when it flies in


def test_a_second_mission_does_not_paint_the_saucer_again(monkeypatch):
    inv.InvaderFormation(1)
    monkeypatch.setattr(inv, "_saucer_frame", lambda level: pytest.fail("painted again"))
    inv.InvaderFormation(2)


def test_the_text_cache_tells_fonts_apart_even_when_one_is_freed():
    """Keyed by the font object, not its id(): a new font can never get an old font's pictures."""
    import gc
    from text_cache import TextCache
    pygame.font.init()
    cache = TextCache()
    small = pygame.font.Font(None, 20)
    first = cache.get(small, "SAME", (255, 255, 255))
    assert any(k[0] is small for k in cache._data)
    del small
    gc.collect()
    heights = set()
    for size in (20, 24, 28, 32, 36, 40, 48, 60):         # new fonts may land on the freed font's memory
        font = pygame.font.Font(None, size)
        got = cache.get(font, "SAME", (255, 255, 255))
        assert got.get_height() == font.render("SAME", True, (255, 255, 255)).get_height()
        heights.add(got.get_height())
    assert len(heights) > 1 and first.get_height() in heights | {first.get_height()}
