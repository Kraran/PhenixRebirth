"""
Frame drawing of Game.draw(): one function per scene or overlay, drawn onto
game.game_surface in the same order as before.

Extracted from game.py (Game.draw). Functions take the Game object as `game`
and behave exactly as before; Game.draw() calls them in the same order.
"""
import pygame

import addon as mame_addon
import announce
import credits_screen
import crt
import escort
import fonts
import highscores_screen
import hint_bar
import keybind_screen
import menu_ui
import main_menu
import story_state
import loot
from i18n import t, t_help
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


def _draw_loot_hud(game):
    """Adventure: the items installed for this mission (small pictures, top right) and the line that tells an item
    was caught."""
    adv = getattr(game, "adventure", None)
    if not adv or game.play_mode == "coop":
        return
    x = BASE_WIDTH - 16
    for item in reversed(adv.get("items") or []):
        pic = loot.icon(item, 28)
        if pic is not None:
            x -= pic.get_width()
            game.game_surface.blit(pic, (x, 74))
            x -= 8
    note = getattr(game, "loot_note", None)
    if note:
        img = game.text_cache.get(game.medium_font, note["text"], (150, 220, 255))
        alpha = max(0, min(255, int(255 * min(1.0, note["t"] / 0.6))))
        if alpha < 255:
            img = img.copy()
            img.set_alpha(alpha)
        game.game_surface.blit(img, (BASE_WIDTH // 2 - img.get_width() // 2, 110))


def scene_overlaid(game):
    """True while something is laid over the scene of the run (pause, game over, hot-seat hand-off): the banner then
    keeps being drawn last, over it, so that an unlock is still seen."""
    return bool(game.game_over or game.paused or game.hotseat_wait)


def announce_layer(game):
    """One translucent banner beneath enemies during play; menus retain their overlay."""
    if scene_overlaid(game):
        game._draw_cheat_message()
        return
    game._draw_cheat_message()
    game._announce_done = True


DOME_HUD_Y = 52                                     # under the mission title (y 16), clear of the Phenix gauge (y 100)


def dome_offline(game):
    """True when the HUD must say "dome offline": an Adventure mission flown with a Shield that has no dome yet."""
    adv = getattr(game, "adventure", None)
    if not adv or adv.get("dome"):
        return False
    return getattr(game, "ship_id", None) != "phoenix"


def draw_play(game):
    """HUD and announcements under the complete enemy layer, drawn exactly once."""
    draw_hud(game)
    announce_layer(game)
    if game.boss_saucer:
        game.boss_saucer.draw(game.game_surface)
    escort.draw(game, game.game_surface)            # the VIP's cruise ship, under the birds (that mission only)
    game.formation.draw(game.game_surface)
    if getattr(game, "loot", None) is not None:
        game.loot.draw(game.game_surface)

    for exp in game.explosions:
        exp.draw(game.game_surface)
    if game.tesla_fx is not None:
        game.tesla_fx.draw(game.game_surface)

    for ship in game._ships():
        ship.draw(game.game_surface)


def draw_hud(game):
    """Scores, gauges, mission counters, loot notices and lives under enemies."""
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
        demo = tc.get(game.medium_font, t("demo"), announce.INFO)
        game.game_surface.blit(demo, (BASE_WIDTH // 2 - demo.get_width() // 2, 72))
        hint = tc.get(game.font, t("press_any"), announce.NEUTRAL)
        game.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 36))
    if getattr(game, "used_cheat", False) and not game.attract_mode:
        ch = tc.get(game.font, t("cheat_active"), announce.SPECIAL)
        game.game_surface.blit(ch, (BASE_WIDTH // 2 - ch.get_width() // 2, 74))

    mission_name = ""
    if getattr(game, "adventure", None):
        mission_name = t(game.adventure.get("hud_title") or game.adventure.get("title") or "story")
        if game.adventure.get("level"):
            mission_name += "  " + t("story_level").format(n=int(game.adventure["level"]))
    stage_surf = tc.get(
        game.font,
        mission_name if getattr(game, "adventure", None) else f"{t('stage')} {game.stage}",
        announce.INFO,
    )
    stage_x = BASE_WIDTH // 2 - stage_surf.get_width() // 2 if game.play_mode == "coop" else 16
    game.game_surface.blit(stage_surf, (stage_x, 16))
    adv = getattr(game, "adventure", None)
    if adv and adv.get("swarm") and game.play_mode != "coop":
        left = tc.get(game.font, t("story_swarm_left").format(n=game.formation.swarm_remaining()), announce.INFO)
        game.game_surface.blit(left, (BASE_WIDTH - 16 - left.get_width(), 44))
    elif adv and adv.get("guardians"):
        form = game.formation
        label = t("story_guardians_hud").format(n=form.destroyed, total=form.total)
        text = tc.get(game.font, label, (255, 190, 110))
        game.game_surface.blit(text, (BASE_WIDTH - 16 - text.get_width(), 52))
        hint = tc.get(game.font, t("story_guardians_hint"), (255, 190, 110))
        game.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 34))
    elif adv and adv.get("escort") and game.play_mode != "coop" and hasattr(game.formation, "cruise"):
        pct = int(game.formation.cruise.progress() * 100)
        left = tc.get(game.font, t("story_vip_hud").format(p=pct), announce.INFO)
        game.game_surface.blit(left, (BASE_WIDTH - 16 - left.get_width(), 44))
    elif adv and adv.get("asteroids") and game.play_mode != "coop":
        form = game.formation
        if getattr(form, "reached", False):
            text = t("story_swarm_left").format(n=form.remaining())                  # the target is reached: empty the screen
        else:
            text = t("story_asteroids_hud").format(n=int(getattr(form, "destroyed", 0)), m=int(getattr(form, "target", 0)))
        left = tc.get(game.font, text, announce.INFO)
        game.game_surface.blit(left, (BASE_WIDTH - 16 - left.get_width(), 44))
    elif adv and adv.get("galaga") and game.play_mode != "coop":
        form = game.formation
        left = tc.get(game.font, t("story_galaga_hud").format(n=max(1, int(getattr(form, "wave", 1))),
                                                              m=int(getattr(form, "waves", 4)),
                                                              left=form.remaining()), announce.INFO)
        game.game_surface.blit(left, (BASE_WIDTH - 16 - left.get_width(), 44))
    elif adv and adv.get("invaders") and game.play_mode != "coop":
        left = tc.get(game.font, t("story_swarm_left").format(n=game.formation.remaining()), announce.INFO)
        game.game_surface.blit(left, (BASE_WIDTH - 16 - left.get_width(), 44))
    elif adv and len(adv.get("waves") or []) > 1 and game.play_mode != "coop":
        wave = tc.get(game.font, t("story_wave_n").format(n=int(adv.get("wave_i", 0)) + 1, m=len(adv["waves"])),
                      announce.INFO)
        game.game_surface.blit(wave, (BASE_WIDTH - 16 - wave.get_width(), 44))
    if dome_offline(game):
        # a quiet reminder under the mission title (the Shield only: the Phenix never had a dome)
        off = tc.get(game.font, t("story_dome_broken"), announce.NEUTRAL)
        game.game_surface.blit(off, (16, DOME_HUD_Y))
    _draw_loot_hud(game)
    escort.banner(game, game.game_surface)
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
    if game.show_fps:
        draw_fps_counter(game)


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
        page_lbl = game._txt(
            getattr(game, "menu_font", None) or game.font,
            f"{t_help('help_page')} {int(game.help_page) + 1}/2",
            (140, 140, 180),
        )
        hint_bar.draw_for(game, game.game_surface, right=page_lbl)

    elif game.menu_screen == "ship_select":
        game._draw_ship_select(game.game_surface)
    elif game.menu_screen == "story_hub":
        if getattr(game, "story", None):
            game.story.draw(game.game_surface, game.font, game.medium_font, game.font,
                            body=getattr(game, "read_font", None))
            if not game.quit_confirm:
                hint_bar.draw_for(game, game.game_surface)        # the same help bar as the classic menus
    elif game.menu_screen == "addon":
        game._draw_addon_menu(game.game_surface)
    elif game.menu_screen == "jukebox":
        game._draw_jukebox(game.game_surface)
    elif game.menu_screen == "main":
        # five entries, in the large font: PLAY, ADVENTURE, EXTRAS, OPTIONS, QUIT
        labels = [t(main_menu.MAIN_TITLES[name]) for name in main_menu.MAIN]
        sub_y = int(getattr(game, "_title_sub_y", 200))
        font = game.medium_font
        row_h = font.get_linesize()
        base_y = sub_y + 33 + 30
        room = hint_bar.BAND_Y - 30 - base_y                 # down to the help bar, panel margin kept
        spacing = max(row_h, min(54, room // len(labels)))
        menu_ui.draw_rows(game, game.game_surface, font, labels, base_y, spacing, game.menu_index,
                          pad_y=max(1, (spacing - row_h) // 2 - 2), min_width=330, panel_pad=(34, 12))

    elif game.menu_screen == "arcade":
        draw_arcade(game)

    elif game.menu_screen == "extras":
        draw_extras(game)

    elif game.menu_screen == "highscores":
        highscores_screen.draw_highscores(game)

    elif game.menu_screen == "achievements":
        game._draw_achievements(game.game_surface)

    elif game.menu_screen == "credits":
        credits_screen.draw_credits(game)

    elif game.menu_screen == "reset_confirm":
        draw_question(game, game.medium_font, t("reset_hs_title"), t("reset_hs_warn"), game.menu_index,
                      title_col=menu_ui.DANGER)
        hint_bar.draw_for(game, game.game_surface)

    elif game.menu_screen == "options":
        if getattr(game, "keybind", None) is not None:
            keybind_screen.draw(game)                      # the screen "Keys and buttons", over the options
        else:
            hdr = game._txt(game.medium_font, t("options"), menu_ui.TITLE)
            game.game_surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 40))
            draw_options(game, top=108)


TITLE_COLOR = menu_ui.TITLE          # the titles of the menu screens (one colour for all of them)


def _title(game, key, y=40):
    hdr = game._txt(game.medium_font, t(key), TITLE_COLOR)
    game.game_surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, y))


def _value_with_arrows(game, surf, font, text, right, cy, chosen, col):
    """A value right-aligned on `right`; on the chosen row it sits between ‹ and › (Left / Right change it)."""
    img = game._txt(font, text, col)
    x = right - img.get_width()
    if chosen:
        arrow_r = game._txt(font, "›", menu_ui.SEL_EDGE)
        arrow_l = game._txt(font, "‹", menu_ui.SEL_EDGE)
        surf.blit(arrow_r, (right - arrow_r.get_width(), cy - arrow_r.get_height() // 2))
        x = right - arrow_r.get_width() - 12 - img.get_width()
        surf.blit(arrow_l, (x - 12 - arrow_l.get_width(), cy - arrow_l.get_height() // 2))
        surf.blit(img, (x, cy - img.get_height() // 2))
        return x - 12 - arrow_l.get_width()                 # the left edge of what was drawn
    surf.blit(img, (x, cy - img.get_height() // 2))
    return x


ARROW_ROOM = 72           # what the arrows of the chosen row take on both sides of a value (‹ ... ›)


def fit_text(fonts, text, max_w):
    """(font, text) that fit in `max_w` px: the first font of `fonts` the whole text fits in; else the last (smallest)
    font with the MIDDLE of the text cut out and "..." put in its place, so the end of the title stays readable
    ("Phoenix - N...e (Final)" and "Phoenix - N...e (Start)" are told apart). The Play font has no ellipsis sign."""
    for font in fonts:
        if font.size(text)[0] <= max_w:
            return font, text
    font = fonts[-1]
    tail = text[-min(9, max(1, len(text) // 3)):].lstrip()
    head = text[:len(text) - len(tail)]
    while font.size(head.rstrip() + "..." + tail)[0] > max_w and (len(head) > 1 or tail):
        if len(head) > 1:
            head = head[:-1]
        else:
            tail = tail[1:]                       # (almost no room: the end goes too, never the whole text)
    return font, head.rstrip() + "..." + tail


def _gauge(surf, right, cy, fill, steps, chosen):
    """A row of small segments (volume, vibrations), right-aligned on `right`."""
    seg_w, seg_h, gap = 12, 16, 4
    width = steps * seg_w + (steps - 1) * gap
    x0 = right - width
    lit = int(round(max(0.0, min(1.0, fill)) * steps))
    on = menu_ui.SEL_EDGE if chosen else (170, 175, 205)
    for i in range(steps):
        r = pygame.Rect(x0 + i * (seg_w + gap), cy - seg_h // 2, seg_w, seg_h)
        pygame.draw.rect(surf, on if i < lit else (50, 52, 72), r, border_radius=3)
    return x0


def draw_tab_strip(game, labels, active, y, focused, font=None):
    """A row of tabs centred on the screen; the open one is lit (gold frame when the row has the focus)."""
    surf = game.game_surface
    font = font or getattr(game, "menu_font", None) or game.font
    imgs = [game._txt(font, lab, menu_ui.TEXT_SEL if i == active else menu_ui.TEXT) for i, lab in enumerate(labels)]
    pad, gap, h = 22, 12, 36
    total = sum(img.get_width() + pad * 2 for img in imgs) + gap * (len(imgs) - 1)
    x = BASE_WIDTH // 2 - total // 2
    rects = []
    for i, img in enumerate(imgs):
        r = pygame.Rect(x, y, img.get_width() + pad * 2, h)
        if i == active and focused:
            menu_ui.highlight(surf, r, radius=8)
        elif i == active:
            menu_ui.panel(surf, r, radius=8, edge=menu_ui.SEL_EDGE, edge_w=1)
        else:
            menu_ui.panel(surf, r, radius=8, edge_w=1)
        surf.blit(img, (r.centerx - img.get_width() // 2, r.centery - img.get_height() // 2))
        rects.append(r)
        x = r.right + gap
    return rects


def draw_options(game, top):
    """The options (menu and pause): the four tabs, the rows of the open tab (label on the left, value in a column
    on the right, gauges for the volumes), and the help of the chosen row on the right."""
    surf = game.game_surface
    tab = int(getattr(game, "opt_tab", 0) or 0) % len(main_menu.OPTION_TABS)
    labels = [t(main_menu.TAB_TITLES[name]) for name, _rows in main_menu.OPTION_TABS]
    draw_tab_strip(game, labels, tab, top, focused=game.menu_index < 0)
    keys = game._options_spec()
    font = game.font
    row_h = 56
    box = pygame.Rect(60, top + 60, 600, len(keys) * row_h + 24)
    menu_ui.panel(surf, box)
    for i, key in enumerate(keys):
        cy = box.y + 12 + i * row_h + row_h // 2
        chosen = i == game.menu_index
        greyed = game._option_greyed(key)
        if chosen:
            menu_ui.highlight(surf, pygame.Rect(box.x + 10, cy - row_h // 2 + 3, box.w - 20, row_h - 6))
        if key == "reset_hs":
            col = (255, 150, 130) if chosen else menu_ui.DANGER       # it erases something: red
        elif greyed:
            col = menu_ui.TEXT_OFF_SEL if chosen else menu_ui.TEXT_OFF
        else:
            col = menu_ui.TEXT_SEL if chosen else menu_ui.TEXT
        lab = game._txt(font, game._option_label(key), col)
        surf.blit(lab, (box.x + 28, cy - lab.get_height() // 2))
        value = game._option_value(key)
        if not value:
            continue
        right = box.right - 28
        small = getattr(game, "menu_font", None) or font
        # a long value (the title of a track, "Fullscreen only"...) must never run over the label: smaller, then cut
        room = right - (box.x + 28 + lab.get_width()) - 24 - ARROW_ROOM
        if game._option_fill(key) is None:
            first = small if (greyed or key in ("coop_p1", "coop_p2")) else font
            vfont, value = fit_text((first, small) if first is not small else (small,), value, room)
        else:
            vfont = font
        if greyed:
            img = game._txt(vfont, value, menu_ui.TEXT_OFF)
            surf.blit(img, (right - img.get_width(), cy - img.get_height() // 2))
            continue
        fill = game._option_fill(key)
        vcol = menu_ui.TEXT_SEL if chosen else (205, 205, 230)
        if fill is not None:
            steps = 5 if key == "rumble" else 10
            x = _value_with_arrows(game, surf, small, value, right, cy, chosen, vcol)
            _gauge(surf, x - 16, cy, fill, steps, chosen)
        else:
            # the two coop rows have a long value ("Auto (Touches ZQSD/WASD)"): the smaller font keeps it in the box
            _value_with_arrows(game, surf, vfont, value, right, cy, chosen, vcol)
    if 0 <= game.menu_index < len(keys):
        game._draw_option_help(keys[game.menu_index], box=(700, box.y, 520, box.h))


ARCADE_VALUES = {
    "mode": ("play_mode", {"solo": "mode_solo", "hotseat": "mode_hotseat", "coop": "mode_coop"}),
    "difficulty": ("difficulty", {"novice": "diff_novice", "normal": "diff_normal", "veteran": "diff_veteran"}),
}


def draw_arcade(game):
    """PLAY: the mode and the difficulty of the arcade game, then the ship select (Enter on any row goes on)."""
    surf = game.game_surface
    _title(game, "arcade_title")
    font = game.font
    row_h = 66
    box = pygame.Rect(BASE_WIDTH // 2 - 380, 120, 760, len(main_menu.ARCADE) * row_h + 28)
    menu_ui.panel(surf, box)
    descs = []
    for i, row in enumerate(main_menu.ARCADE):
        cy = box.y + 14 + i * row_h + row_h // 2
        chosen = i == game.menu_index
        if chosen:
            menu_ui.highlight(surf, pygame.Rect(box.x + 12, cy - row_h // 2 + 4, box.w - 24, row_h - 8))
        col = menu_ui.TEXT_SEL if chosen else menu_ui.TEXT
        if row == "ship":
            img = game._txt(game.medium_font, t("arcade_ship") + "  ›", col)
            surf.blit(img, (box.centerx - img.get_width() // 2, cy - img.get_height() // 2))
            continue
        lab = game._txt(font, t(row), col)
        surf.blit(lab, (box.x + 32, cy - lab.get_height() // 2))
        attr, keys = ARCADE_VALUES[row]
        cur = getattr(game, attr, "") or ""
        key = keys.get(cur, next(iter(keys.values())))
        _value_with_arrows(game, surf, font, t(key), box.right - 32, cy, chosen,
                           menu_ui.TEXT_SEL if chosen else (205, 205, 230))
        descs.append((t(key), t(key + "_d"), chosen))
    # what the chosen mode and difficulty mean
    small = getattr(game, "body_font", None) or font
    info = pygame.Rect(box.x, box.bottom + 24, box.w, 0)
    lines = []
    for name, text, chosen in descs:
        for j, line in enumerate(game._wrap_ui(f"{name} : {text}", small, info.w - 56)):
            lines.append((line, chosen, j == 0))
    info.h = len(lines) * (small.get_linesize() + 4) + 40
    menu_ui.panel(surf, info)
    y = info.y + 20
    for line, chosen, first in lines:
        img = game._txt(small, line, (225, 225, 240) if chosen else (160, 162, 190))
        surf.blit(img, (info.x + 28, y))
        y += small.get_linesize() + 4


def draw_extras(game):
    """EXTRAS: one paragraph for each screen (scores, achievements, jukebox, credits, help, add-on), like the
    Extras tab of the Adventure; the chosen one is lit."""
    surf = game.game_surface
    _title(game, "extras_title")
    small = getattr(game, "body_font", None) or game.font
    width, top, step, h = 860, 96, 94, 82
    ready = mame_addon.addon_ready()
    for i, name in enumerate(main_menu.EXTRAS):
        chosen = i == game.menu_index
        box = pygame.Rect(BASE_WIDTH // 2 - width // 2, top + i * step, width, h)
        if chosen:
            menu_ui.highlight(surf, box, radius=10)
        else:
            menu_ui.panel(surf, box, radius=10, edge_w=1)
        off = name == "addon" and not ready
        if off:
            col = menu_ui.TEXT_OFF_SEL if chosen else menu_ui.TEXT_OFF
        else:
            col = menu_ui.TEXT_SEL if chosen else (170, 175, 200)
        head = game._txt(game.medium_font, t(main_menu.EXTRAS_TITLES[name]), col)
        surf.blit(head, (box.x + 28, box.y + 8))
        text = t("addon_missing") if off else t("extras_%s_d" % name)
        line = game._wrap_ui(text, small, width - 56)[0]
        desc = game._txt(small, line, (205, 208, 228) if chosen and not off else (140, 145, 170))
        surf.blit(desc, (box.x + 28, box.y + 48))


def draw_menu_footer(game):
    """Press-confirm blink, version, controls hint and season decor."""
    bar = not game.quit_confirm                  # the quit question draws its own bar, over the dimmed menu
    if game.menu_screen == "main":
        ver = getattr(game, "_ver_surf", None)
        if ver is None:
            vf = fonts.text(13)
            ver = vf.render("v1.5.0", True, (110, 110, 130))
            game._ver_surf = ver
        if bar:
            hint_bar.draw_for(game, game.game_surface, right=ver)
        game._draw_season_title(game.game_surface)
    elif game.menu_screen in ("options", "arcade", "extras") and bar:
        hint_bar.draw_for(game, game.game_surface)


def draw_hs_enter(game):
    """High-score entry: three initials."""
    cy = 100 + game.big_font.get_height() // 2
    img = announce.draw(game, game.game_surface, t("new_record"), "reward", "major", (BASE_WIDTH // 2, cy))
    if game.hotseat or getattr(game, "play_mode", "solo") == "coop":
        who = game._txt(game.font, t("player_n").format(n=game.hs_slot_label), (255, 200, 120))
        game.game_surface.blit(who, (BASE_WIDTH // 2 - who.get_width() // 2, 44))

    # everything below hangs from the bottom of the plate (its height follows the font that fits the text)
    plate_bottom = cy + img.get_height() // 2 + announce.LEVELS["major"]["pad"][1]
    score_y = max(180, plate_bottom + 14)
    shift = score_y - 180

    sc = game._txt(game.font, f"{t('score_label')} : {game.format_score(game.score)}", (200, 255, 180))
    game.game_surface.blit(sc, (BASE_WIDTH // 2 - sc.get_width() // 2, score_y))

    hint = game._txt(game.font, t("enter_initials_hint"), (180, 180, 220))
    game.game_surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, 240 + shift))

    # Three letters
    letter_spacing = 70
    start_x = BASE_WIDTH // 2 - letter_spacing
    for i, ch in enumerate(game.hs_name):
        col = (255, 255, 120) if i == game.hs_char_index else (220, 220, 255)
        letter = game._txt(game.big_font, ch, col)
        lx = start_x + i * letter_spacing - letter.get_width() // 2
        game.game_surface.blit(letter, (lx, 320 + shift))
        if i == game.hs_char_index:
            pygame.draw.line(
                game.game_surface, (255, 220, 100),
                (lx, 400 + shift), (lx + letter.get_width(), 400 + shift), 3
            )

    hint_bar.draw_for(game, game.game_surface)


def draw_hs_table(game):
    """High-score table after a game."""
    title = game._txt(game.big_font, t("high_scores"), menu_ui.TITLE)
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
    menu_ui.panel(game.game_surface, pygame.Rect(BASE_WIDTH // 2 - 260, base_y - 14, 520, 15 * 28 + 30))
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

    hint_bar.draw_for(game, game.game_surface)


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
    page_lbl = None
    if getattr(game, "pause_abandon", False):
        game.game_surface.blit(game._dim_overlay(180), (0, 0))
        draw_question(game, game.big_font, t("abandon_title"), t("abandon_q"), game.abandon_index)
        hint_bar.draw_for(game, game.game_surface)
        return
    if getattr(game, "pause_help", False):
        game.game_surface.blit(game._dim_overlay(225), (0, 0))      # darker: the help is text
        game._draw_help_page(game.game_surface, game.help_page, 0)
        page_lbl = game._txt(getattr(game, "menu_font", None) or game.font,
                             f"{t_help('help_page')} {int(game.help_page) + 1}/2", (140, 140, 180))
        hint_bar.draw_for(game, game.game_surface, right=page_lbl)
        return
    overlay = game._dim_overlay(160)
    game.game_surface.blit(overlay, (0, 0))
    if game.pause_options and getattr(game, "keybind", None) is not None:
        keybind_screen.draw(game)
    elif game.pause_options:
        hdr = game._txt(game.medium_font, t("options"), menu_ui.TITLE)
        game.game_surface.blit(hdr, (BASE_WIDTH // 2 - hdr.get_width() // 2, 36))
        if game.menu_screen == "reset_confirm":
            draw_question(game, game.medium_font, t("reset_hs_title"), t("reset_hs_warn"), game.menu_index,
                      title_col=menu_ui.DANGER)
        else:
            draw_options(game, top=92)
    else:
        title = game._txt(game.big_font, t("pause"), menu_ui.TITLE)
        game.game_surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 200))
        row_h = game.medium_font.get_linesize()
        menu_ui.draw_rows(game, game.game_surface, game.medium_font,
                          [t(main_menu.pause_title(name, bool(getattr(game, "adventure", None)))) for name in main_menu.PAUSE], 300, 55, game.pause_index,
                          pad_y=(55 - row_h) // 2 - 3, min_width=360, panel_pad=(26, 16))
    hint_bar.draw_for(game, game.game_surface)


def draw_quit_confirm(game):
    """Quit-the-game confirmation (menus)."""
    overlay = game._dim_overlay(180)
    game.game_surface.blit(overlay, (0, 0))
    draw_question(game, game.big_font, t("quit_game"), t("quit_game_q"), game.quit_index)
    hint_bar.draw_for(game, game.game_surface)


def draw_question(game, title_font, title, question, index, title_col=menu_ui.TITLE):
    """A YES / NO question in its own panel, in the middle of the screen (quit the game, erase the scores).
    YES is the first row, NO the second, as before."""
    surf = game.game_surface
    head = game._txt(title_font, title, title_col)
    ask = game._txt(game.font, question, (220, 220, 240))
    font = game.medium_font
    row_h = font.get_linesize()
    spacing = row_h + 14
    w = max(520, head.get_width() + 80, ask.get_width() + 80)
    h = head.get_height() + ask.get_height() + spacing * 2 + 84
    box = pygame.Rect(0, 0, w, h)
    box.center = (BASE_WIDTH // 2, BASE_HEIGHT // 2 - 20)
    menu_ui.panel(surf, box, radius=14, alpha=230)
    y = box.top + 22
    surf.blit(head, (BASE_WIDTH // 2 - head.get_width() // 2, y))
    y += head.get_height() + 6
    surf.blit(ask, (BASE_WIDTH // 2 - ask.get_width() // 2, y))
    y += ask.get_height() + 24
    menu_ui.draw_rows(game, surf, font, [t("yes_u"), t("no_u")], y, spacing, index,
                      pad_y=6, min_width=160, back_panel=False)


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

    # CRT scanlines (src/crt.py): 240 soft lines and a vignette; the glow of the bright parts at levels 2 and 3
    if int(getattr(game, "scanlines", 0) or 0) > 0:
        if game._ensure_scanline_surf() is not None:
            crt.apply(game.game_surface, getattr(game, "_scanline_layers", None))
