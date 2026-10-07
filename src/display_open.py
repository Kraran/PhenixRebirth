"""
Opening / recreating the display surface.

Extracted from game.py (Game._open_display). The function takes the Game object as
`game` and behaves exactly as before.
"""
import pygame

from desktop_cover import hide_cover, show_cover
from settings import BASE_HEIGHT, BASE_WIDTH, detect_refresh_rate


def open_display(game):
    """Create the display surface once (or recreate on Options change)."""
    recreating = bool(getattr(game, "_display_ready", False))
    if recreating:
        try:
            if getattr(game, "screen", None) is not None:
                game.screen.fill((0, 0, 0))
                pygame.display.flip()
        except Exception:
            pass
        show_cover()
        game._reset_video()
    try:
        mon = game._pick_monitor()
        mon_i = int(mon[0])
        mon_w, mon_h = int(mon[1]), int(mon[2])
        mon_x = int(mon[3]) if len(mon) >= 5 else 0
        mon_y = int(mon[4]) if len(mon) >= 5 else 0
    except Exception as e:
        print("pick monitor failed:", e)
        mon_i, mon_w, mon_h, mon_x, mon_y = 0, BASE_WIDTH, BASE_HEIGHT, 0, 0

    base_flags = pygame.DOUBLEBUF | pygame.HWSURFACE
    mode = getattr(game, "display_mode", "fullscreen")

    def _set(size, flags, display=None):
        # SCALED must not keep display= after a CPU fullscreen: SDL then
        # fails with "failed to create renderer" and stays stuck on CPU.
        last = None
        if display is not None and not (flags & getattr(pygame, "SCALED", 0)):
            try:
                return pygame.display.set_mode(size, flags, display=int(display))
            except TypeError:
                pass
            except pygame.error as e:
                last = e
                print("set_mode(display=) failed:", e)
        want_vs = 1 if getattr(game, "vsync_mode", "adaptive") == "on" else 0
        try:
            import os
            os.environ["SDL_RENDER_VSYNC"] = "1" if want_vs else "0"
        except Exception:
            pass
        import warnings
        def _mode(vs):
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*vsync.*")
                try:
                    return pygame.display.set_mode(size, flags, vsync=vs)
                except TypeError:
                    return pygame.display.set_mode(size, flags)
        try:
            return _mode(want_vs)
        except pygame.error as e:
            last = e
            print("set_mode failed:", e)
        game._reset_video()
        try:
            return _mode(0)
        except pygame.error:
            return pygame.display.set_mode(size, flags)

    # Position hint for the next window
    try:
        import os
        if mode == "window":
            px = mon_x + max(0, (mon_w - BASE_WIDTH) // 2)
            py = mon_y + max(0, (mon_h - BASE_HEIGHT) // 2)
        else:
            px, py = mon_x, mon_y
        os.environ["SDL_VIDEO_WINDOW_POS"] = f"{px},{py}"
        os.environ["SDL_VIDEO_CENTERED"] = "0"
    except Exception:
        pass

    want_bezel = (
        mode == "fullscreen"
        and getattr(game, "bezel_style", "phoenix") not in (None, "", "off")
        and mon_h > 0
        and (mon_w / float(mon_h)) > (16.0 / 9.0 + 0.02)
    )
    # SCALED with bezels: logical size matches monitor aspect (e.g. 1707x720
    # on 2560x1080). Game 1:1 in the center, panels on the sides, SDL GPU
    # stretches the whole frame. No OpenGL.
    use_gpu = (
        bool(getattr(game, "gpu_present", True))
        and hasattr(pygame, "SCALED")
    )
    game._gpu_backend = "cpu"
    try:
        opened = False
        if use_gpu:
            sc = pygame.SCALED | pygame.DOUBLEBUF
            if mode == "fullscreen":
                sc |= pygame.FULLSCREEN
            elif mode == "borderless":
                sc |= pygame.NOFRAME
            try:
                # Small logical canvas. SDL SCALED GPU-stretches it.
                # Native 2560x1080 + SCALED was slower than CPU (40 vs 60).
                if want_bezel and mode == "fullscreen" and mon_h > 0:
                    lw = max(BASE_WIDTH, int(round(BASE_HEIGHT * mon_w / float(mon_h))))
                    gpu_size = (lw, BASE_HEIGHT)
                else:
                    gpu_size = (BASE_WIDTH, BASE_HEIGHT)
                game.screen = _set(gpu_size, sc, mon_i)
                game._gpu_backend = "scaled"
                opened = True
            except pygame.error:
                print("SCALED set_mode failed, CPU path")
                use_gpu = False
        if not opened:
          if mode == "window":
            game.screen = _set((BASE_WIDTH, BASE_HEIGHT), base_flags, mon_i)
          elif mode == "borderless":
            game.screen = _set((mon_w, mon_h), base_flags | pygame.NOFRAME, mon_i)
          else:
            try:
                game.screen = _set(
                    (mon_w, mon_h), base_flags | pygame.FULLSCREEN, mon_i
                )
            except pygame.error:
                try:
                    game.screen = _set(
                        (0, 0), base_flags | pygame.FULLSCREEN, mon_i
                    )
                except pygame.error:
                    game.display_mode = "window"
                    game.screen = _set((BASE_WIDTH, BASE_HEIGHT), base_flags, mon_i)
    except Exception as e:
        print("open display failed, windowed fallback:", e)
        import traceback
        traceback.print_exc()
        game.display_mode = "window"
        game.screen = pygame.display.set_mode(
            (BASE_WIDTH, BASE_HEIGHT), base_flags
        )

    try:
        pygame.mouse.set_visible(game.display_mode == "window")
    except Exception:
        pass
    try:
        if getattr(game, "game_surface", None) is not None:
            game.game_surface = game.game_surface.convert()
    except Exception:
        pass
    game._bind_gpu()
    game._update_caption()
    try:
        if getattr(game, "screen", None) is not None:
            game.screen.fill((0, 0, 0))
            pygame.display.flip()
    except Exception:
        pass
    hide_cover()
    try:
        pygame.event.clear()
        pygame.event.pump()
    except Exception:
        pass
    game._refocus_game_window()
    game._rebind_joystick()
    try:
        game.panel_hz = int(detect_refresh_rate() or 60)
        game.fps_target = int(getattr(game, "fps_cap", 120) or 120)
        import settings as _settings
        _settings.FPS_TARGET = game.fps_target
        print("panel:", game.panel_hz, "Hz  cap:", game.fps_target, "Hz  vsync:", getattr(game, "vsync_mode", "?"))
    except Exception:
        pass
    try:
        pygame.event.clear()
    except Exception:
        pass
