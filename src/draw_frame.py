"""
Frame drawing of Game.draw(): one function per scene or overlay, drawn onto
game.game_surface in the same order as before.

Extracted from game.py (Game.draw). Functions take the Game object as `game`
and behave exactly as before; Game.draw() calls them in the same order.
"""
import pygame

import addon as mame_addon
import credits_screen
import highscores_screen
from i18n import LANGS, t, t_help
from settings import BASE_HEIGHT, BASE_WIDTH, COLOR_BG


def draw_background(game):
    """Clear the canvas and draw the starfield."""
    # TEMP debug: True = pale backdrop to spot opaque leaks. Set False after.
    if getattr(game, "DEBUG_LIGHT_BG", False):
        game.game_surface.fill((198, 202, 210))
    else:
        game.game_surface.fill(COLOR_BG)

    # Starfield first (background)
    game.starfield.draw(game.game_surface)


def draw_play(game):
    """In-run scene: boss, birds, explosions, ships, score, lives and HUD."""
    if game.boss_saucer:
        game.boss_saucer.draw(game.game_surface)
    game.formation.draw(game.game_surface)

    for exp in game.explosions:
        exp.draw(game.game_surface)
    if game.tesla_fx is not None:
        game.tesla_fx.draw(game.game_surface)

    for ship in game._ships():
        ship.draw(game.game_surface)

    # UI (cached text — re-render only when string/color changes)
    tc = game.text_cache
    if game.play_mode == "coop" and game.player2:
        c1 = game._palette_score_color(getattr(game.player, "palette", "argent"))
        c2 = game._palette_score_color(getattr(game.player2, "palette", "blue"))
        p1s = tc.get(game.font, f"P1 {game.format_score(getattr(game.player, 'score', 0))}", c1)
        p2s = tc.get(game.font, f"P2 {game.format_score(getattr(game.player2, 'score', 0))}", c2)
        game.game_surface.blit(p1s, (16, 16))
        game.game_surface.blit(p2s, (BASE_WIDTH - 16 - p2s.get_width(), 16))
        game._draw_phenix_gauge(game.player, 18, 100)
        game._draw_phenix_gauge(game.player2, BASE_WIDTH - 18 - 14, 100, align="right")
    else:
        score_surf = tc.get(game.font, game.format_score(game.score), game._palette_score_color(getattr(game.player, "palette", "argent")))
        game.game_surface.blit(score_surf, (BASE_WIDTH // 2 - score_surf.get_width() // 2, 16))
        if game.hotseat and game.slots[0] and game.slots[1]:
            s0 = game.slots[0]["score"] if game.current_p != 0 else game.score
            s1 = game.slots[1]["score"] if game.current_p != 1 else game.score
            p0 = game.slots[0].get("player")
            p1p = game.slots[1].get("player")
            pal0 = getattr(p0, "palette", None) or game._tint_for_pid(1)
            pal1 = getattr(p1p, "palette", None) or game._tint_for_pid(2)
            c0 = game._palette_score_color(pal0, bright=(game.current_p == 0))
            c1 = game._palette_score_color(pal1, bright=(game.current_p == 1))
            hp1 = tc.get(game.font, f"P1 {game.format_score(s0)}", c0)
            hp2 = tc.get(game.font, f"P2 {game.format_score(s1)}", c1)
            game.game_surface.blit(hp1, (16, 44))
            game.game_surface.blit(hp2, (BASE_WIDTH - 16 - hp2.get_width(), 44))
        if game.hotseat and game.current_p == 1:
            game._draw_phenix_gauge(game.player, BASE_WIDTH - 18 - 14, 100, align="right")
        else:
            game._draw_phenix_gauge(game.player, 18, 100)
    if game.attract_mode:
        demo = tc.get(game.medium_font, t("demo"), (255, 180, 80))
        game.game_surface.blit(demo, (BASE_WIDTH // 2 - demo.get_width() // 2, 72))
        hint = tc.get(game.font, t("press_any"), (180, 180, 200))
        game.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 36))
    if getattr(game, "used_cheat", False) and not game.attract_mode:
        ch = tc.get(game.font, t("cheat_active"), (255, 60, 60))
        game.game_surface.blit(ch, (BASE_WIDTH // 2 - ch.get_width() // 2, 74))

    stage_surf = tc.get(
        game.font,
        t(game.adventure.get("title") or "story") if getattr(game, "adventure", None) else f"{t('stage')} {game.stage}",
        (255, 170, 80) if getattr(game, "adventure", None) else (180, 180, 220),
    )
    stage_x = BASE_WIDTH // 2 - stage_surf.get_width() // 2 if game.play_mode == "coop" else 16
    game.game_surface.blit(stage_surf, (stage_x, 16))
    if getattr(game, "adventure", None) and not game.adventure.get("dome"):
        off = tc.get(game.font, t("story_dome_broken"), (255, 90, 80))
        game.game_surface.blit(off, (16, 40))
    if game.difficulty in ("novice", "veteran") and not game.attract_mode:
        dkey = "diff_novice" if game.difficulty == "novice" else "diff_veteran"
        dcol = (120, 210, 255) if game.difficulty == "novice" else (255, 150, 80)
        dsurf = tc.get(game.font, t(dkey), dcol)
        if game.play_mode in ("coop", "hotseat") or getattr(game, "hotseat", False):
            dx = BASE_WIDTH // 2 - dsurf.get_width() // 2
            dy = 70
        else:
            dx = BASE_WIDTH - 16 - dsurf.get_width()
            dy = 16
        game.game_surface.blit(dsurf, (dx, dy))
    # Flags for each boss defeated — at 10+, one big flag only
    if game.bosses_defeated >= 10:
        fx = stage_x + stage_surf.get_width() + 12
        game._draw_boss_flag(game.game_surface, fx, 12, big=True)
    elif game.bosses_defeated > 0:
        fx = stage_x + stage_surf.get_width() + 10
        fy = 18
        for i in range(game.bosses_defeated):
            game._draw_boss_flag(game.game_surface, fx + i * 18, fy, big=False)

    game._draw_cheat_message()

    # Lives as mini ships
    if game.player.infinite_lives:
        inf = game.text_cache.get(game.font, t("lives_inf"), (110, 255, 150))
        game.game_surface.blit(inf, (BASE_WIDTH // 2 - inf.get_width() // 2, 44))
    n_lives = max(0, game.player.lives)
    if n_lives > 0 and not game.player.infinite_lives:
        gap = 6
        iw = game.life_icon.get_width()
        ih = game.life_icon.get_height()
        total_w = n_lives * iw + (n_lives - 1) * gap
        start_x = BASE_WIDTH // 2 - total_w // 2
        for i in range(n_lives):
            lx = start_x + i * (iw + gap)
            ly = 44
            # Extra life flash/shine on the new icon
            if game.life_flash_timer > 0 and i == game.life_flash_index:
                blink = int(game.life_flash_timer * 8) % 2 == 0
                if blink:
                    # bright glow under ship
                    glow = pygame.Surface((iw + 10, ih + 10), pygame.SRCALPHA)
                    pygame.draw.ellipse(glow, (255, 255, 120, 90), glow.get_rect())
                    game.game_surface.blit(glow, (lx - 5, ly - 5))
                    # white flash version
                    white = game.life_icon.copy()
                    white.fill((255, 255, 200, 0), special_flags=pygame.BLEND_RGBA_ADD)
                    game.game_surface.blit(white, (lx, ly))
                    game.game_surface.blit(game.life_icon, (lx, ly))
            else:
                game.game_surface.blit(game.life_icon, (lx, ly))


def draw_menu_title(game):
    """Title screen: animated logo and subtitle."""
    if game.menu_screen in ("main",):
        # Animated fiery logo (fallback to text if frames missing)
        hide = getattr(game, "april_gag", "") == "boom"
        if not hide:
            ok = game._draw_logo(
                game.game_surface, BASE_WIDTH // 2, 8,
                ox=float(getattr(game, "april_ox", 0.0)),
                oy=float(getattr(game, "april_oy", 0.0)),
                angle=float(getattr(game, "april_rot", 0.0)),
            )
            if not ok:
                title = game._txt(game.big_font, "PHENIX REBIRTH", (255, 120, 255))
                game.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 80))
        for exp in getattr(game, "explosions", []) or []:
            if not game.started:
                exp.draw(game.game_surface)

        # Subtitle glued under the logo bitmap (not over the menu)
        logo_h = game.logo_frames[0].get_height() if game.logo_frames else 100
        sub = game._txt(game.font, t("subtitle"), (180, 160, 220))
        game._title_sub_y = 8 + logo_h + 2
        game.game_surface.blit(sub, (BASE_WIDTH // 2 - sub.get_width() // 2, game._title_sub_y))


def draw_menu_screens(game):
    """The menu screen itself: help, ship select, story, add-on, jukebox, main list, scores, options..."""
    if game.menu_screen == "help":
        # Two pages with optional vertical scroll transition
        if game.help_transitioning:
            off = int(game.help_scroll)
            game._draw_help_page(game.game_surface, 0, -off)
            game._draw_help_page(game.game_surface, 1, BASE_HEIGHT - off)
        else:
            game._draw_help_page(game.game_surface, game.help_page, 0)
        hint = game._txt(game.font, t("help_return"), (255, 220, 100))
        game.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 36))
        page_lbl = game._txt(
            game.font,
            f"{t_help('help_page')} {int(game.help_page) + 1}/2",
            (140, 140, 180),
        )
        game.game_surface.blit(page_lbl, (BASE_WIDTH - page_lbl.get_width() - 20, BASE_HEIGHT - 36))

    elif game.menu_screen == "ship_select":
        game._draw_ship_select(game.game_surface)
    elif game.menu_screen == "story_hub":
        if getattr(game, "story", None):
            game.story.draw(game.game_surface, game.font, game.medium_font, game.font)
    elif game.menu_screen == "addon":
        game._draw_addon_menu(game.game_surface)
    elif game.menu_screen == "jukebox":
        game._draw_jukebox(game.game_surface)
    elif game.menu_screen == "main":
        diff_key = {"novice": "diff_novice", "normal": "diff_normal", "veteran": "diff_veteran"}.get(game.difficulty, "diff_normal")
        diff = t(diff_key)
        mode = getattr(game, "play_mode", "solo")
        mode_key = {"solo": "mode_solo", "hotseat": "mode_hotseat", "coop": "mode_coop"}.get(mode, "mode_solo")
        options = [
            t("play"),
            t("story"),
            t("addon"),
            f"{t('mode')} :  <  {t(mode_key)}  >",
            f"{t('difficulty')} :  <  {diff}  >",
            t("options"),
            t("high_scores"),
            t("credits"),
            t("quit"),
        ]
        sub_y = int(getattr(game, "_title_sub_y", 200))
        sub_h = 22
        base_y = sub_y + sub_h + 28
        foot = 80
        room = max(160, BASE_HEIGHT - foot - base_y)
        spacing = max(18, min(24, room // max(1, len(options))))
        menu_font = getattr(game, "menu_font", None) or game.font
        for i, label in enumerate(options):
            selected = (i == game.menu_index)
            disabled = (i == 2) and not mame_addon.addon_ready()
            if disabled:
                col = (255, 230, 120) if selected else (90, 90, 105)
            else:
                col = (255, 230, 120) if selected else (160, 160, 190)
            prefix = "> " if selected else "  "
            surf = game._txt(menu_font, prefix + label, col)
            game.game_surface.blit(surf, (BASE_WIDTH // 2 - surf.get_width() // 2, base_y + i * spacing))

        if game.gamepad_detected:
            status = game._txt(game.font, t("gamepad_detected"), (100, 200, 140))
        else:
            status = game._txt(game.font, t("gamepad_none"), (180, 140, 120))
        status_y = min(BASE_HEIGHT - 64, base_y + len(options) * spacing + 6)
        game.game_surface.blit(status, (BASE_WIDTH // 2 - status.get_width() // 2, status_y))

    elif game.menu_screen == "highscores":
        highscores_screen.draw_highscores(game)

    elif game.menu_screen == "achievements":
        game._draw_achievements(game.game_surface)

    elif game.menu_screen == "credits":
        credits_screen.draw_credits(game)

    elif game.menu_screen == "reset_confirm":
        hdr = game._txt(game.medium_font, t("reset_hs_title"), (255, 120, 100))
        game.game_surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 280))
        warn = game._txt(game.font, t("reset_hs_warn"), (180, 160, 160))
        game.game_surface.blit(warn, (BASE_WIDTH // 2 - warn.get_width() // 2, 340))
        for i, label in enumerate([t("yes_u"), t("no_u")]):
            selected = (i == game.menu_index)
            col = (255, 230, 120) if selected else (160, 160, 190)
            prefix = "> " if selected else "  "
            surf = game._txt(game.medium_font, prefix + label, col)
            game.game_surface.blit(surf, (BASE_WIDTH // 2 - surf.get_width() // 2, 400 + i * 50))

    elif game.menu_screen == "options":
        # OPTIONS screen
        hdr = game._txt(game.medium_font, t("options"), (255, 180, 255))
        game.game_surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 48))

        mode_labels = {
            "window": t("disp_window"),
            "fullscreen": t("disp_fullscreen"),
            "borderless": t("disp_borderless"),
        }
        ctrl = t("ctrl_pad") if game.input_mode == "gamepad" else t("ctrl_kb")
        vol_pct = int(round(game.sfx_volume * 100))
        disp = mode_labels.get(game.display_mode, game.display_mode)

        fps_label = t("yes") if game.show_fps else t("no")
        mus_pct = int(round(game.music_volume * 100))
        lang_label = next((n for c, n in LANGS if c == game.language), game.language)
        lines = game._options_labels()
        n = max(1, len(lines))
        top = 128
        reserved = 96
        spacing = min(34, max(24, (BASE_HEIGHT - reserved - top) // n))
        left_x = 48
        for i, label in enumerate(lines):
            selected = (i == game.menu_index)
            col = (255, 230, 120) if selected else (160, 160, 190)
            prefix = "> " if selected else "  "
            surf = game._txt(game.font, prefix + label, col)
            game.game_surface.blit(surf, (left_x, top + i * spacing))
        spec = game._options_spec()
        if 0 <= game.menu_index < len(spec):
            game._draw_option_help(spec[game.menu_index])
        hint = game._txt(game.font, t("opt_hint"), (120, 120, 150))
        game.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 78))


def draw_menu_footer(game):
    """Press-confirm blink, version, controls hint and season decor."""
    if game.menu_screen == "main":
        if int(game.title_timer * 2.5) % 2 == 0:
            press = game._txt(game.font, t("press_confirm"), (255, 220, 100))
            game.game_surface.blit(press, (BASE_WIDTH // 2 - press.get_width() // 2, BASE_HEIGHT - 70))
        ver = getattr(game, "_ver_surf", None)
        if ver is None:
            vf = pygame.font.SysFont(pygame.font.get_default_font(), 16)
            ver = vf.render("v1.4.4", True, (110, 110, 130))
            game._ver_surf = ver
        game.game_surface.blit(ver, (BASE_WIDTH - ver.get_width() - 10, BASE_HEIGHT - ver.get_height() - 8))

        if game.input_mode == "gamepad":
            controls = game._txt(game.font, t("controls_pad"), (140, 140, 180))
        else:
            controls = game._txt(game.font, t("controls_kb"), (140, 140, 180))
        game.game_surface.blit(controls, (BASE_WIDTH // 2 - controls.get_width() // 2, BASE_HEIGHT - 40))
        game._draw_season_title(game.game_surface)
    elif game.menu_screen == "options":
        if game.input_mode == "gamepad":
            controls = game._txt(game.font, t("controls_pad"), (140, 140, 180))
        else:
            controls = game._txt(game.font, t("controls_kb"), (140, 140, 180))
        game.game_surface.blit(controls, (BASE_WIDTH // 2 - controls.get_width() // 2, BASE_HEIGHT - 40))


def draw_hs_enter(game):
    """High-score entry: three initials."""
    title = game._txt(game.big_font, t("new_record"), (255, 220, 100))
    game.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 100))
    if game.hotseat or getattr(game, "play_mode", "solo") == "coop":
        who = game._txt(game.font, t("player_n").format(n=game.hs_slot_label), (255, 200, 120))
        game.game_surface.blit(who, (BASE_WIDTH // 2 - who.get_width() // 2, 72))

    sc = game._txt(game.font, f"{t('score_label')} : {game.format_score(game.score)}", (200, 255, 180))
    game.game_surface.blit(sc, (BASE_WIDTH // 2 - sc.get_width() // 2, 180))

    hint = game._txt(game.font, t("enter_initials_hint"), (180, 180, 220))
    game.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, 240))

    # Three letters
    letter_spacing = 70
    start_x = BASE_WIDTH // 2 - letter_spacing
    for i, ch in enumerate(game.hs_name):
        col = (255, 255, 120) if i == game.hs_char_index else (220, 220, 255)
        letter = game._txt(game.big_font, ch, col)
        lx = start_x + i * letter_spacing - letter.get_width() // 2
        game.game_surface.blit(letter, (lx, 320))
        if i == game.hs_char_index:
            pygame.draw.line(
                game.game_surface, (255, 220, 100),
                (lx, 400), (lx + letter.get_width(), 400), 3
            )

    controls = game._txt(game.font, t("hs_entry_controls"), (140, 140, 180))
    game.game_surface.blit(controls, (BASE_WIDTH // 2 - controls.get_width() // 2, 480))
    ok = game._txt(game.font, t("press_confirm"), (255, 220, 100))
    game.game_surface.blit(ok, (BASE_WIDTH // 2 - ok.get_width() // 2, 540))


def draw_hs_table(game):
    """High-score table after a game."""
    title = game._txt(game.big_font, t("high_scores"), (255, 120, 255))
    game.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 40))

    added = getattr(game, "hs_just_added", None) or []
    if len(added) >= 2:
        parts = [f"P{e['pid']} {game.format_score(e['score'])}" for e in sorted(added, key=lambda e: e['pid'])]
        sc = game._txt(game.font, f"{t('your_scores')} : " + "  —  ".join(parts), (200, 255, 180))
    else:
        sc = game._txt(game.font, f"{t('your_score')} : {game.format_score(game.score)}", (200, 255, 180))
    game.game_surface.blit(sc, (BASE_WIDTH // 2 - sc.get_width() // 2, 110))

    entries = game.hs_entries if game.hs_entries else []
    base_y = 160
    score_right = BASE_WIDTH // 2 + 170
    for i in range(15):
        rank = i + 1
        if i < len(entries):
            name = entries[i]["name"]
            score = entries[i]["score"]
            added = getattr(game, "hs_just_added", None) or []
            highlight = any(e.get("score") == score and e.get("name") == name for e in added)
            if not highlight:
                highlight = (game.hs_submitted and score == game.score and name == "".join(game.hs_name))
            col = (255, 230, 120) if highlight else (200, 200, 230)
            game._draw_hs_row(
                game.game_surface, base_y + i * 28, rank,
                name, score, col, score_right,
                coop=bool(entries[i].get("coop")),
                ship=entries[i].get("ship"),
                ship2=entries[i].get("ship2"),
                veteran=bool(entries[i].get("veteran")),
                tint=entries[i].get("tint"),
            )
        else:
            game._draw_hs_row(
                game.game_surface, base_y + i * 28, rank,
                "---", None, (100, 100, 120), score_right,
            )

    restart = game._txt(game.font, t("back_to_menu"), (255, 220, 100))
    game.game_surface.blit(restart, (BASE_WIDTH // 2 - restart.get_width() // 2, BASE_HEIGHT - 50))


def draw_hotseat_overlays(game):
    """Hot-seat: player 2 ship pick and 'press a key' hand-off overlays."""
    if getattr(game, "hotseat_pick_p2", False) and game.menu_screen == "ship_select":
        overlay = game._dim_overlay(150)
        game.game_surface.blit(overlay, (0, 0))
        game._draw_ship_select(game.game_surface)
    if game.hotseat_wait and game.started and not game.game_over:
        overlay = game._dim_overlay(170)
        game.game_surface.blit(overlay, (0, 0))
        who = t("player_n").format(n=game.hotseat_next + 1)
        title = game._txt(game.big_font, who, (255, 200, 80))
        game.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, BASE_HEIGHT // 2 - 50))
        hint = game._txt(game.font, t("hotseat_press"), (220, 220, 240))
        game.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT // 2 + 24))


def draw_pause(game):
    """Pause menu and pause options."""
    overlay = game._dim_overlay(160)
    game.game_surface.blit(overlay, (0, 0))
    if game.pause_options:
        hdr = game._txt(game.medium_font, t("options"), (255, 180, 255))
        game.game_surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 36))
        if game.menu_screen == "reset_confirm":
            rh = game._txt(game.medium_font, t("reset_hs_title"), (255, 120, 100))
            game.game_surface.blit(rh, (BASE_WIDTH // 2 - rh.get_width() // 2, 280))
            for i, label in enumerate([t("yes_u"), t("no_u")]):
                selected = (i == game.menu_index)
                col = (255, 230, 120) if selected else (160, 160, 190)
                prefix = "> " if selected else "  "
                surf = game._txt(game.medium_font, prefix + label, col)
                game.game_surface.blit(surf, (BASE_WIDTH // 2 - surf.get_width() // 2, 360 + i * 50))
        else:
            lines = game._options_labels()
            n = max(1, len(lines))
            top = 92
            reserved = 48
            spacing = min(32, max(22, (BASE_HEIGHT - reserved - top) // n))
            left_x = 48
            for i, label in enumerate(lines):
                selected = (i == game.menu_index)
                col = (255, 230, 120) if selected else (160, 160, 190)
                prefix = "> " if selected else "  "
                surf = game._txt(game.font, prefix + label, col)
                game.game_surface.blit(surf, (left_x, top + i * spacing))
            spec = game._options_spec()
            if 0 <= game.menu_index < len(spec):
                game._draw_option_help(spec[game.menu_index], box=(700, 100, 520, 460))
    else:
        title = game._txt(game.big_font, t("pause"), (255, 220, 100))
        game.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 200))
        for i, label in enumerate([t("resume"), t("options"), t("quit_run")]):
            selected = (i == game.pause_index)
            col = (255, 230, 120) if selected else (160, 160, 190)
            prefix = "> " if selected else "  "
            surf = game._txt(game.medium_font, prefix + label, col)
            game.game_surface.blit(surf, (BASE_WIDTH // 2 - surf.get_width() // 2, 300 + i * 55))


def draw_quit_confirm(game):
    """Quit-the-game confirmation (menus)."""
    overlay = game._dim_overlay(180)
    game.game_surface.blit(overlay, (0, 0))
    title = game._txt(game.big_font, t("quit_game"), (255, 120, 100))
    game.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 220))
    q = game._txt(game.medium_font, t("quit_game_q"), (220, 220, 240))
    game.game_surface.blit(q, (BASE_WIDTH // 2 - q.get_width() // 2, 300))
    for i, label in enumerate([t("yes_u"), t("no_u")]):
        selected = (i == game.quit_index)
        col = (255, 230, 120) if selected else (160, 160, 190)
        prefix = "> " if selected else "  "
        surf = game._txt(game.medium_font, prefix + label, col)
        game.game_surface.blit(surf, (BASE_WIDTH // 2 - surf.get_width() // 2, 360 + i * 50))


def draw_fps_counter(game):
    """FPS counter, top right."""
    game._fps_timer = getattr(game, "_fps_timer", 0.0) + getattr(game, "dt", 0.016)
    if game._fps_timer >= 0.25:
        game._fps_timer = 0.0
        game._fps_display = int(round(game.clock.get_fps()))
    fps_surf = game.text_cache.get(
        game.font, f"{getattr(game, '_fps_display', 0)} FPS", (120, 220, 120)
    )
    game.game_surface.blit(fps_surf, (BASE_WIDTH - fps_surf.get_width() - 130, 12))


def draw_post_effects(game):
    """Phenix white flash, then CRT scanlines."""
    if int(getattr(game, "phenix_flash", 0) or 0) > 0:
        flash = getattr(game, "_phenix_flash_surf", None)
        if flash is None or flash.get_size() != (BASE_WIDTH, BASE_HEIGHT):
            flash = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
            flash.fill((255, 210, 140))
            game._phenix_flash_surf = flash
        game.game_surface.blit(flash, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        game.phenix_flash = 0

    # CRT scanlines — multiply, same format as game_surface (no alpha blit)
    if int(getattr(game, "scanlines", 0) or 0) > 0:
        sc = game._ensure_scanline_surf()
        if sc is not None:
            game.game_surface.blit(sc, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
