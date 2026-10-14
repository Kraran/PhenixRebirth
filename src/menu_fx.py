"""
Menu transitions: when an input changes the screen, the new screen slides in from the side it comes from and fades in
(0.22 s). Going on (Enter, A) it comes from the right, going back (Esc, B) from the left; Left / Right, Tab, LB / RB
between tabs (scores / achievements / jukebox, the option tabs, the Adventure's panes) follow the arrow pressed, the
help pages too.

Only the screen moves: the starfield behind keeps flowing, and the help bar stays where it is (hint_bar holds its
drawing while the screen is painted on the sliding layer, then it is drawn in place). Outside a transition the menus are
drawn exactly as before (no layer, no cost). No transition in a game, in the pause, under the story scenes, when a
fade to black is on (the ship select), or when a menu changes by itself (idle help, end of a fade).

Nothing here uses `random`: the reference replays are untouched.
"""
import pygame

SLIDE_SEC = 0.22          # length of a transition
SLIDE_PX = 90             # how far the new screen starts from its place

_LEFT_KEYS = (pygame.K_LEFT, pygame.K_a, pygame.K_q, pygame.K_PAGEUP)
_RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d, pygame.K_PAGEDOWN)
_UP_KEYS = (pygame.K_UP, pygame.K_w, pygame.K_z)
_DOWN_KEYS = (pygame.K_DOWN, pygame.K_s)

_layer = {}


def screen_key(game):
    """What counts as "another screen": the menu screen, the Adventure's screen and pane, the options tab, the help page."""
    g = game
    screen = getattr(g, "menu_screen", "")
    key = [screen]
    if screen == "story_hub":
        st = getattr(g, "story", None)
        if st is not None:
            key += [getattr(st, "screen", ""), getattr(st, "pane", ""), bool(getattr(st, "paint_mode", False))]
    elif screen == "options":
        key.append(int(getattr(g, "opt_tab", 0) or 0))
    elif screen == "help":
        key.append(int(getattr(g, "help_page", 0) or 0))
    return tuple(key)


def _story_scene(game):
    st = getattr(game, "story", None)
    return getattr(game, "menu_screen", "") == "story_hub" and st is not None and getattr(st, "screen", "") == "intro"


def direction(kind, event):
    """+1: the new screen comes from the right; -1: from the left."""
    if kind == "back":
        return -1
    if kind == "confirm":
        return 1
    et = event.type
    if et == pygame.KEYDOWN:
        if event.key == pygame.K_TAB:
            return -1 if getattr(event, "mod", 0) & pygame.KMOD_SHIFT else 1
        if event.key in _LEFT_KEYS or event.key in _UP_KEYS:
            return -1
        return 1
    if et == pygame.JOYBUTTONDOWN:
        return -1 if event.button == 4 else 1
    if et == pygame.JOYHATMOTION:
        hx, hy = event.value
        return -1 if (hx < 0 or (hx == 0 and hy > 0)) else 1
    if et == pygame.JOYAXISMOTION:
        return -1 if event.value < 0 else 1
    return 1


def note(game, before_key, before_started, kind, event):
    """After an input: start a transition if it changed the screen."""
    if before_key is None or kind is None or before_started:
        return
    if getattr(game, "started", False) or getattr(game, "fade_phase", None) or getattr(game, "attract_mode", False):
        return
    if _story_scene(game) or (len(before_key) > 1 and before_key[0] == "story_hub" and before_key[1] == "intro"):
        return
    after_key = screen_key(game)
    if after_key == before_key:
        return
    game._menu_slide = [direction(kind, event), 0.0]


def active(game):
    return bool(getattr(game, "_menu_slide", None))


def _ease(p):
    p = max(0.0, min(1.0, p))
    return 1.0 - (1.0 - p) ** 3                      # fast at first, settling softly


def draw_sliding(game, paint):
    """Paint the menu (`paint()` draws it on game.game_surface) on a see-through layer, then put that layer on screen
    shifted and faded by the transition; the help bar is drawn last, in place."""
    slide = game._menu_slide
    slide[1] += float(getattr(game, "dt", 0.0) or 0.0)
    p = _ease(slide[1] / SLIDE_SEC)
    real = game.game_surface
    size = real.get_size()
    layer = _layer.get(size)
    if layer is None:
        layer = _layer[size] = pygame.Surface(size, pygame.SRCALPHA)
    layer.fill((0, 0, 0, 0))
    held = []
    game.game_surface = layer
    game._bar_hold = held
    try:
        paint()
    finally:
        game.game_surface = real
        game._bar_hold = None
    layer.set_alpha(int(255 * min(1.0, 0.15 + p)))
    real.blit(layer, (int(slide[0] * (1.0 - p) * SLIDE_PX), 0))
    layer.set_alpha(255)                             # (not None: on a per-pixel alpha layer it would drop that alpha)
    import hint_bar
    for items, right, lit in held:
        hint_bar.draw(game, real, items, right=right, lit=lit)
    if slide[1] >= SLIDE_SEC:
        game._menu_slide = None
