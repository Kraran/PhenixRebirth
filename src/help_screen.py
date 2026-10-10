"""
Help screen (2 pages: scenario / points, then Phenix & Shield).

Extracted from game.py (Game._build_help_icons, Game._draw_help_page).
The functions take the Game object as `game` and behave exactly as before;
Game keeps thin methods with the old names that call them.
"""
import pygame
import os

from settings import BASE_WIDTH, asset_path
from i18n import t, t_help, t_list
from errlog import log_exc
from phenix_art import ship_size

HELP_PHENIX_SHIP_H = 80          # height of the Phenix itself in the help icons (not of its canvas)


def fit_art(surf, box_h=90, ship_h=None):
    """`surf` shrunk so that its content is `box_h` high.

    By default the content is what the picture shows (its picture is cropped to it first). With `ship_h`, the
    height of the ship inside `surf` (the margin around it left out), the whole picture is scaled by the ship and
    not cropped: the ship keeps its size and its place however far its wings go."""
    if surf is None:
        return None
    if ship_h:
        sc = box_h / float(max(1, ship_h))
        return pygame.transform.smoothscale(
            surf, (max(1, int(surf.get_width() * sc)), max(1, int(surf.get_height() * sc))))
    try:
        r = surf.get_bounding_rect(min_alpha=24)
    except Exception:
        r = surf.get_rect()
    if r.width < 2 or r.height < 2:
        src = surf
    else:
        src = surf.subsurface(r).copy()
    sc = box_h / max(1, src.get_height())
    return pygame.transform.smoothscale(
        src, (max(1, int(src.get_width() * sc)), box_h)
    )


def build_help_icons(game):

    """Sprites for the help screen score table."""
    from enemy import Enemy, BigBird
    e1 = Enemy(0, 0, stage=1)
    e2 = Enemy(0, 0, stage=2)
    g3 = BigBird(0, 0, stage=3)
    g4 = BigBird(0, 0, stage=4)
    game.help_icons = {
        "bird1": e1,
        "bird2": e2,
        "garg3": g3,
        "garg4": g4,
    }
    boss_frames = []
    ch = 36
    for i in range(4):
        path = asset_path("sprites", f"boss_core_{i:02d}.png")
        if not os.path.isfile(path):
            continue
        try:
            core_img = pygame.image.load(path).convert_alpha()
            scale = ch / max(1, core_img.get_height())
            cw = max(1, int(core_img.get_width() * scale))
            boss_frames.append(pygame.transform.smoothscale(core_img, (cw, ch)))
        except Exception:
            log_exc("help_screen.build_help_icons")
    if not boss_frames:
        try:
            core_img = pygame.image.load(asset_path("sprites", "boss_core.png")).convert_alpha()
            scale = ch / max(1, core_img.get_height())
            cw = max(1, int(core_img.get_width() * scale))
            boss_frames.append(pygame.transform.smoothscale(core_img, (cw, ch)))
        except Exception:
            core = pygame.Surface((36, 40), pygame.SRCALPHA)
            pygame.draw.ellipse(core, (40, 90, 70), (4, 4, 28, 32))
            boss_frames.append(core)
    game.help_icons["boss_frames"] = boss_frames
    game.help_icons["boss"] = boss_frames[0]
    # Ship + Phenix form for help page 2
    try:
        ship = pygame.image.load(asset_path("sprites", "player_ship.png")).convert_alpha()
        sh = 72
        scale = sh / max(1, ship.get_height())
        sw = max(1, int(ship.get_width() * scale))
        game.help_icons["ship"] = pygame.transform.smoothscale(ship, (sw, sh))
    except Exception:
        game.help_icons["ship"] = None
    phenix_dir = asset_path("sprites", "phenix")
    frames = []
    for i in range(8):
        path = os.path.join(phenix_dir, f"phenix_{i:02d}.png")
        if not os.path.isfile(path):
            continue
        try:
            img = pygame.image.load(path).convert_alpha()
        except Exception:
            continue
        # the scale comes from the ship, not from its canvas: the canvas has a margin around the ship
        scale = HELP_PHENIX_SHIP_H / max(1, ship_size(img)[1])
        frames.append(pygame.transform.smoothscale(
            img, (max(1, int(img.get_width() * scale)), max(1, int(img.get_height() * scale)))))
    game.help_icons["phenix_ship_h"] = HELP_PHENIX_SHIP_H if frames else None
    if not frames:
        for name in ("phenix_04.png", "morph_03.png", "phenix_00.png"):
            path = os.path.join(phenix_dir, name)
            if os.path.isfile(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    padded = name.startswith("phenix_")           # morph frames have no margin
                    scale = HELP_PHENIX_SHIP_H / max(1, ship_size(img)[1] if padded else img.get_height())
                    frames.append(pygame.transform.smoothscale(
                        img, (max(1, int(img.get_width() * scale)), max(1, int(img.get_height() * scale)))))
                    game.help_icons["phenix_ship_h"] = HELP_PHENIX_SHIP_H if padded else None
                    break
                except Exception:
                    log_exc("help_screen.build_help_icons")
    game.help_icons["phenix_frames"] = frames
    game.help_icons["phenix"] = frames[0] if frames else None
    try:
        shs = pygame.image.load(asset_path("sprites", "player_ship_shield.png")).convert_alpha()
        hh = 72
        sc = hh / max(1, shs.get_height())
        game.help_icons["ship_shield"] = pygame.transform.smoothscale(
            shs, (max(1, int(shs.get_width() * sc)), hh)
        )
    except Exception:
        game.help_icons["ship_shield"] = None
    sframes = []
    sdir = asset_path("sprites", "shield")
    if os.path.isdir(sdir):
        for name in ("loop_00.png", "loop_01.png", "loop_02.png", "loop_03.png"):
            path = os.path.join(sdir, name)
            if not os.path.isfile(path):
                continue
            try:
                sframes.append(pygame.image.load(path).convert_alpha())
            except Exception:
                continue
    game.help_icons["shield_fx"] = sframes
    game.help_icons["shield_frames"] = sframes
    game.help_icons["shield"] = sframes[0] if sframes else game.help_icons.get("ship_shield")


def draw_help_page(game, surface, page, y_off):
    """Draw help page 0 (scenario/points) or 1 (PHENIX). y_off shifts content."""
    def yy(y):
        return int(y + y_off)

    title = game._txt(game.big_font, "PHENIX REBIRTH", (255, 120, 255))
    surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, yy(28)))
    sub = game._txt(game.font, t("subtitle"), (180, 160, 220))
    surface.blit(sub, (BASE_WIDTH // 2 - sub.get_width() // 2, yy(82)))

    if page <= 0:
        col_l = 48
        y = 120

        def hdr(txt, y):
            s = game._txt(game.medium_font, txt, (255, 200, 120))
            surface.blit(s, (col_l, yy(y)))
            return y + 34

        def body(txt, y):
            s = game._txt(game.font, txt, (200, 200, 230))
            surface.blit(s, (col_l, yy(y)))
            return y + 24

        y = hdr(t_help("scenario_h"), y)
        for line in t_list("scenario"):
            y = body(line, y)
        y += 10
        y = hdr(t_help("howto_h"), y)
        for line in t_list("howto"):
            y = body(line, y)
        y += 10
        y = hdr(t_help("controls_h"), y)
        for line in t_list("controls"):
            y = body(line, y)

        col_r = BASE_WIDTH // 2 + 90
        y = 120
        s = game._txt(game.medium_font, t_help("points_h"), (255, 200, 120))
        surface.blit(s, (col_r, yy(y)))
        y += 40
        score_rows = [
            ("bird1", t_help("enemy_s1"), "10"),
            ("bird2", t_help("enemy_s2"), "20"),
            ("garg3", t_help("enemy_s3"), "30"),
            ("garg4", t_help("enemy_s4"), "40"),
            ("boss", t_help("enemy_boss"), "500"),
        ]
        for key, label, pts in score_rows:
            ix, iy = col_r + 28, yy(y + 14)
            if key == "bird1" and "bird1" in game.help_icons:
                game._draw_help_bird(surface, game.help_icons["bird1"], ix, iy, phase=0.0)
            elif key == "bird2" and "bird2" in game.help_icons:
                game._draw_help_bird(surface, game.help_icons["bird2"], ix, iy, phase=1.7)
            elif key == "garg3" and "garg3" in game.help_icons:
                game._draw_help_gargoyle(surface, game.help_icons["garg3"], ix, iy, 0.5)
            elif key == "garg4" and "garg4" in game.help_icons:
                game._draw_help_gargoyle(surface, game.help_icons["garg4"], ix, iy, 0.5)
            elif key == "boss":
                bframes = game.help_icons.get("boss_frames") or []
                img = None
                if bframes:
                    idx = int(getattr(game, "help_anim_t", 0.0) * 8.0) % len(bframes)
                    img = bframes[idx]
                else:
                    img = game.help_icons.get("boss")
                if img is not None:
                    surface.blit(img, (ix - img.get_width() // 2, iy - img.get_height() // 2))
            ls = game._txt(game.font, label, (200, 200, 230))
            surface.blit(ls, (col_r + 60, yy(y + 4)))
            ps = game._txt(game.font, pts + " " + t_help("pts"), (110, 255, 150))
            surface.blit(ps, (col_r + 60, yy(y + 26)))
            y += 54
        note = game._txt(game.font, t_help("vet_note"), (180, 160, 200))
        surface.blit(note, (col_r, yy(y + 2)))
        y += 26
        note2 = game._txt(game.font, t_help("bonus_lives"), (180, 160, 220))
        surface.blit(note2, (col_r, yy(y)))
    else:
        # Page 2 — Phenix (left) + Shield (right), same ship size
        def _fit(surf, box_h=90, ship_h=None):
            return fit_art(surf, box_h, ship_h)

        body_font = getattr(game, "help_small", None)
        if body_font is None:
            try:
                body_font = pygame.font.SysFont(
                    ("segoeui", "tahoma", "verdana", "arial"), 20, bold=True
                )
            except Exception:
                body_font = game.font
            game.help_small = body_font

        def _text_col(header, lines, hx, col_w, hcol, y0):
            s = game._txt(game.medium_font, header, hcol)
            surface.blit(s, (hx + (col_w - s.get_width()) // 2, yy(y0)))
            y = y0 + 36
            for line in lines:
                for piece in game._wrap_ui(line, body_font, col_w):
                    ls = game._txt(body_font, piece, (210, 210, 235))
                    surface.blit(ls, (hx, yy(y)))
                    y += 20
            y += 8
            tip = game._txt(body_font, "Shift / X  ·  B", (255, 220, 120))
            surface.blit(tip, (hx + (col_w - tip.get_width()) // 2, yy(y)))
            return y + 22

        def _fit_shield(hull, fx, hull_h=90):
            """Same hull size as idle; dome may overflow the box."""
            if hull is None:
                return _fit(fx, hull_h)
            try:
                r = hull.get_bounding_rect(min_alpha=24)
                hsrc = hull.subsurface(r).copy() if r.width > 1 else hull
            except Exception:
                hsrc = hull
            sc = hull_h / max(1, hsrc.get_height())
            hs = pygame.transform.smoothscale(
                hsrc, (max(1, int(hsrc.get_width() * sc)), hull_h)
            )
            if fx is None:
                return hs
            fs = pygame.transform.smoothscale(
                fx, (max(1, int(fx.get_width() * sc)), max(1, int(fx.get_height() * sc)))
            )
            cw = max(hs.get_width(), fs.get_width())
            ch = max(hs.get_height(), fs.get_height())
            canvas = pygame.Surface((cw, ch), pygame.SRCALPHA)
            canvas.blit(hs, ((cw - hs.get_width()) // 2, (ch - hs.get_height()) // 2))
            canvas.blit(fs, ((cw - fs.get_width()) // 2, (ch - fs.get_height()) // 2))
            return canvas

        def _art_row(hx, col_w, art_left, art_right, hcol, art_y, right_is_shield=False, hull_h=90, right_ship_h=None):
            left = _fit(art_left, hull_h)
            right = _fit_shield(art_left, art_right, hull_h) if right_is_shield else _fit(art_right, hull_h, right_ship_h)
            arrow = game._txt(game.medium_font, ">>>", hcol)
            total = arrow.get_width() + 20
            if left is not None:
                total += left.get_width()
            if right is not None:
                total += right.get_width()
            x0 = hx + max(0, (col_w - total) // 2)
            cy = art_y + hull_h // 2  # common hull midline
            if left is not None:
                surface.blit(left, (x0, yy(cy - left.get_height() // 2)))
                x0 += left.get_width() + 10
            surface.blit(arrow, (x0, yy(cy - arrow.get_height() // 2)))
            x0 += arrow.get_width() + 10
            if right is not None:
                surface.blit(right, (x0, yy(cy - right.get_height() // 2)))

        tnow = float(getattr(game, "help_anim_t", 0.0))
        pframes = game.help_icons.get("phenix_frames") or []
        phenix = pframes[int(tnow * 10.0) % len(pframes)] if pframes else game.help_icons.get("phenix")
        sframes = game.help_icons.get("shield_frames") or []
        bubble = sframes[int(tnow * 8.0) % len(sframes)] if sframes else game.help_icons.get("shield")
        gap = 36
        col_w = (BASE_WIDTH - 64 - gap) // 2
        lx, rx = 32, 32 + col_w + gap
        y_l = _text_col("PHENIX", t_list("phenix"), lx, col_w, (255, 160, 80), 146)
        y_r = _text_col("SHIELD", t_list("shield"), rx, col_w, (120, 200, 255), 146)
        art_y = max(y_l, y_r) + 16
        _art_row(lx, col_w, game.help_icons.get("ship"), phenix, (255, 160, 80), art_y,
                 right_ship_h=game.help_icons.get("phenix_ship_h"))
        _art_row(rx, col_w, game.help_icons.get("ship_shield"), bubble, (120, 200, 255), art_y, right_is_shield=True)
