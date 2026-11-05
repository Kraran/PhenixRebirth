"""The loading bar: at the start of the game and at the launch of a mission of the Adventure.

Everything stays on the main thread. A loading is a list of steps, each with the share of the bar it fills (from what each one
costs, measured); the heavy loops of the game call `report()` now and then (fire_death.frames, the textures of the Lander, the
sounds...): while a loading is on, that redraws the bar (at most ~30 times a second) and keeps the window alive (the events are
pumped), else it costs nothing. Inside a step the bar moves on towards the end of the step, more and more slowly, so it never
stops while the work goes on and never jumps past it.

A mission that is ready at once shows nothing: the bar only appears after `delay` seconds.
"""
import math
import threading
import time

import pygame

from errlog import log_exc
from settings import BASE_HEIGHT, BASE_WIDTH

FRAME = 1.0 / 30.0             # the bar is redrawn at most this often
BAR_W, BAR_H = 560, 16
AMBER = (255, 190, 90)
AMBER_LIGHT = (255, 230, 170)

_active = None


def report():
    """Called from a heavy loop: the bar moves on (when a loading is on screen). From another thread (the warm-ups of the
    Lander and of Scramble): nothing, only the main thread draws."""
    if _active is not None and threading.current_thread() is threading.main_thread():
        _active.tick()


def active():
    return _active


class Loading:
    """`with Loading(game, style, title) as ld: ld.step(share, fn, expect)...` - see the module."""

    def __init__(self, game, style="arcade", title=None, delay=0.0, lang=None):
        self.game = game
        self.style = style                      # "arcade" (the start of the game) or "adventure" (a mission)
        self.title = title
        self.delay = float(delay)
        self.lang = lang
        self.start = time.perf_counter()
        self.done = 0.0                         # share of the bar of the steps finished
        self.span = (0.0, 0.0)                  # the step running: from, to
        self.step_t0 = self.start
        self.expect = 1.0
        self.shown = 0.0                        # what the bar shows (never goes back)
        self.last = 0.0
        self.drawn = 0

    def __enter__(self):
        global _active
        self._outer = _active
        _active = self
        return self

    def __exit__(self, *exc):
        global _active
        if exc[0] is None and self.drawn:
            self.span = (1.0, 1.0)
            self.done = 1.0
            self.tick(force=True)               # (the full bar, a last time)
        _active = self._outer
        if self.drawn:
            self._drop_inputs()
        return False

    def step(self, share, fn, expect=1.0):
        """Run `fn` while the bar goes from where it is to `share` further; `expect`: about how long it takes (seconds)."""
        a = self.done
        b = min(1.0, a + max(0.0, share))
        self.span = (a, b)
        self.step_t0 = time.perf_counter()
        self.expect = max(0.05, float(expect))
        self.tick(force=True)
        try:
            return fn()
        finally:
            self.done = b
            self.span = (b, b)
            self.tick()

    def progress(self):
        a, b = self.span
        k = 1.0 - math.exp(-(time.perf_counter() - self.step_t0) / self.expect)      # 0 -> 1, slower and slower
        self.shown = max(self.shown, min(b, a + (b - a) * 0.92 * k), self.done)
        return self.shown

    def tick(self, force=False):
        now = time.perf_counter()
        if now - self.start < self.delay:
            return
        if not force and now - self.last < FRAME:
            return
        self.last = now
        try:
            pygame.event.pump()                 # (the window stays alive)
            self.draw(self.progress())
            self.game._flip_frame(0, 0)
            self.drawn += 1
        except Exception:
            log_exc("loading.tick")

    def _drop_inputs(self):
        """The keys and buttons pressed while it loaded are not played afterwards (closing the window is kept)."""
        try:
            pygame.event.clear((pygame.KEYDOWN, pygame.KEYUP, pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP,
                                pygame.JOYHATMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP))
        except Exception:
            log_exc("loading._drop_inputs")

    # --- the picture
    def _label(self):
        import i18n
        if self.lang and i18n.get_lang() != self.lang:
            i18n.set_lang(self.lang)
        return i18n.t("loading")

    def draw(self, p):
        surface = self.game.game_surface
        if self.style == "adventure":
            draw_adventure(surface, self.title, self._label(), p, time.perf_counter() - self.start)
        else:
            frames = getattr(self.game, "logo_frames", None) or []
            t = time.perf_counter() - self.start
            logo = frames[int(t * 12) % len(frames)] if frames else None          # (the animated logo, once it is loaded)
            draw_arcade(surface, logo, self._label(), p, t)


def _bar_rect():
    return pygame.Rect((BASE_WIDTH - BAR_W) // 2, BASE_HEIGHT // 2 + 70, BAR_W, BAR_H)


def _fill(surface, rect, p, colour, light, t):
    fill = int(rect.w * max(0.0, min(1.0, p)))
    if fill <= 0:
        return
    pygame.draw.rect(surface, colour, (rect.x, rect.y, fill, rect.h), border_radius=rect.h // 2)
    # a light that runs along the filled part
    x = rect.x + int((t * 220) % max(1, fill))
    glow = pygame.Rect(x - 18, rect.y + 3, 36, rect.h - 6).clip(pygame.Rect(rect.x, rect.y, fill, rect.h))
    if glow.w > 0:
        pygame.draw.rect(surface, light, glow, border_radius=3)


def draw_arcade(surface, logo, label, p, t):
    """The start of the game: the logo, LOADING and the bar, on the dark of the menus."""
    import fonts
    import menu_ui
    surface.fill((6, 7, 14))
    cy = BASE_HEIGHT // 2
    if logo is not None:
        w = min(logo.get_width(), 520)
        img = logo if w == logo.get_width() else pygame.transform.smoothscale(
            logo, (w, int(logo.get_height() * w / logo.get_width())))
        surface.blit(img, ((BASE_WIDTH - img.get_width()) // 2, max(20, cy - 30 - img.get_height())))
    head = fonts.title(30).render(label, True, menu_ui.TITLE)
    surface.blit(head, ((BASE_WIDTH - head.get_width()) // 2, cy + 18))
    r = _bar_rect()
    pygame.draw.rect(surface, (14, 16, 28), r.inflate(10, 10), border_radius=(r.h + 10) // 2)
    pygame.draw.rect(surface, menu_ui.PANEL_EDGE, r.inflate(10, 10), 2, border_radius=(r.h + 10) // 2)
    _fill(surface, r, p, AMBER, AMBER_LIGHT, t)
    pct = fonts.text(20).render(f"{int(round(p * 100))} %", True, menu_ui.TEXT)
    surface.blit(pct, ((BASE_WIDTH - pct.get_width()) // 2, r.bottom + 16))


def draw_adventure(surface, title, label, p, t):
    """A mission of the Adventure: the hangar of the station, the name of the mission in its copper cartouche, the bar on a
    steel plate with its hazard strip, lit in the phosphor of the terminals."""
    import fonts
    import phobos_ui
    bg = phobos_ui.backdrop("hangar")
    if bg is not None:
        surface.blit(bg, (0, 0))
    else:
        surface.fill((10, 12, 16))
    cy = BASE_HEIGHT // 2
    plate = pygame.Rect((BASE_WIDTH - 760) // 2, cy - 110, 760, 270)
    phobos_ui.plate(surface, plate, hazard=True)
    if title:
        font = fonts.title(34)
        while font.size(title)[0] > plate.w - 120 and font.get_height() > 18:
            font = fonts.title(font.get_height() - 3)
        phobos_ui.title(surface, font, title, BASE_WIDTH // 2, plate.y + 40)
    head = fonts.title(24).render(label, True, phobos_ui.HOLO_TEXT)
    surface.blit(head, ((BASE_WIDTH - head.get_width()) // 2, cy + 18))
    r = _bar_rect()
    pygame.draw.rect(surface, phobos_ui.CRT_BG, r.inflate(10, 10), border_radius=4)
    pygame.draw.rect(surface, phobos_ui.STEEL_EDGE, r.inflate(10, 10), 3, border_radius=4)
    _fill(surface, r, p, phobos_ui.CRT, (200, 255, 246), t)
    pct = fonts.text(20).render(f"{int(round(p * 100))} %", True, phobos_ui.CRT_TEXT)
    surface.blit(pct, ((BASE_WIDTH - pct.get_width()) // 2, r.bottom + 16))
