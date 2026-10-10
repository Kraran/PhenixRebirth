"""
Ship select screen: portrait loading, focus animation frames and drawing.

Extracted from game.py (Game._load_ship_previews, Game._preview_cycle_frame,
Game._draw_ship_select). The functions take the Game object as `game` and
behave exactly as before; Game keeps thin methods with the old names.
"""
import math
import os

import pygame

from settings import BASE_HEIGHT, BASE_WIDTH, asset_path
from i18n import t
from player import recolor_phenix_frames
from phenix_art import PREVIEW_FLASH_RADIUS, PREVIEW_MORPH_IN_SEC, PREVIEW_MORPH_OUT_SEC, morph_sequence


def load_ship_previews(game):
    """Menu portraits + focus animations (Phenix flap / Shield loop)."""
    game.preview_ships = {}
    def _load(path):
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception:
            return None
    idle_p = _load(asset_path("sprites", "player_ship.png"))
    anim_p = []
    pdir = asset_path("sprites", "phenix")
    if os.path.isdir(pdir):
        for name in sorted(os.listdir(pdir)):
            if name.startswith("phenix_") and name.endswith(".png"):
                fr = _load(os.path.join(pdir, name))
                if fr is not None:
                    anim_p.append(fr)
    morph_p = []
    if os.path.isdir(pdir):
        for name in sorted(os.listdir(pdir)):
            if name.startswith("morph_") and name.endswith(".png"):
                fr = _load(os.path.join(pdir, name))
                if fr is not None:
                    morph_p.append(fr)
    pack_p = {
        "anim": anim_p or ([idle_p] if idle_p else []),
        "on": morph_p or [],
        "off": list(reversed(morph_p)) if morph_p else [],
    }
    for key, path in (
        ("argent", asset_path("sprites", "player_ship.png")),
        ("blue", asset_path("sprites", "player_ship_blue.png")),
        ("gold", asset_path("sprites", "player_ship_gold.png")),
    ):
        idle_t = _load(path) or idle_p
        anim_t = recolor_phenix_frames(pack_p["anim"], key)
        drawn_t = recolor_phenix_frames(pack_p["on"], key)
        # same transformation as in the game: the drawn pictures with pictures between them, ship to flight
        change = morph_sequence(idle_t, drawn_t, anim_t[0] if anim_t else None, flash=True, flash_radius=PREVIEW_FLASH_RADIUS)
        game.preview_ships["phoenix_" + key] = {
            "idle": idle_t,
            "anim": anim_t,
            "on": change or drawn_t,
            "off": list(reversed(change)) if change else recolor_phenix_frames(pack_p["off"], key),
        }
        if change:
            # the panel is sized by the pictures without the halo, which may go a little beyond it
            game.preview_ships["phoenix_" + key]["core_size"] = (
                max(f.get_width() for f in [idle_t] + drawn_t + anim_t[:1]),
                max(f.get_height() for f in [idle_t] + drawn_t + anim_t[:1]))
            game.preview_ships["phoenix_" + key]["on_sec"] = PREVIEW_MORPH_IN_SEC
            game.preview_ships["phoenix_" + key]["off_sec"] = PREVIEW_MORPH_OUT_SEC
    game.preview_ships["phoenix"] = game.preview_ships["phoenix_argent"]
    idle_s = _load(asset_path("sprites", "player_ship_shield.png"))
    anim_s, on_s, off_s = [], [], []
    sdir = asset_path("sprites", "shield")
    if os.path.isdir(sdir):
        for name in sorted(os.listdir(sdir)):
            if not name.endswith(".png"):
                continue
            fr = _load(os.path.join(sdir, name))
            if fr is None:
                continue
            if name.startswith("loop_"):
                anim_s.append(fr)
            elif name.startswith("morph_"):
                on_s.append(fr)
            elif name.startswith("off_"):
                off_s.append(fr)
    game.preview_ships["shield"] = {
        "idle": idle_s,
        "anim": anim_s or ([idle_s] if idle_s else []),
        "on": on_s,
        "off": off_s or list(reversed(on_s)),
    }
    pack_fx = {
        "anim": anim_s or [],
        "on": on_s,
        "off": off_s or list(reversed(on_s)),
    }
    def _comp(hull, fx):
        if hull is None:
            return fx
        if fx is None:
            return hull
        cw, ch = max(hull.get_width(), fx.get_width()), max(hull.get_height(), fx.get_height())
        canvas = pygame.Surface((cw, ch), pygame.SRCALPHA)
        canvas.blit(hull, ((cw - hull.get_width()) // 2, (ch - hull.get_height()) // 2))
        canvas.blit(fx, ((cw - fx.get_width()) // 2, (ch - fx.get_height()) // 2))
        return canvas
    tint_files = {
        "red": asset_path("sprites", "player_ship_shield.png"),
        "green": asset_path("sprites", "player_ship_shield_green.png"),
        "violet": asset_path("sprites", "player_ship_shield_violet.png"),
    }
    for tint, path in tint_files.items():
        idle_t = _load(path) or idle_s
        game.preview_ships["shield_" + tint] = {
            "idle": idle_t,
            "anim": [_comp(idle_t, fr) for fr in pack_fx["anim"]] or [idle_t],
            "on": [_comp(idle_t, fr) for fr in pack_fx["on"]],
            "off": [_comp(idle_t, fr) for fr in pack_fx["off"]],
        }
    game.preview_ships["shield"] = game.preview_ships["shield_red"]


def preview_cycle_frame(game, pack, idle, loop):
    """idle hold → morph in → special hold → morph out → idle."""
    ph = getattr(game, "ship_cycle_phase", "idle")
    tt = float(getattr(game, "ship_cycle_t", 0.0))
    fps = 10.0
    on_fr = pack.get("on") or []
    off_fr = pack.get("off") or list(reversed(on_fr))
    on_sec, off_sec = pack.get("on_sec"), pack.get("off_sec")      # set when the pictures are the whole change
    if ph == "to_special" and on_fr:
        idx = min(len(on_fr) - 1, int(tt * (len(on_fr) / on_sec if on_sec else fps)))
        return on_fr[idx]
    if ph == "special" and loop:
        return loop[int(tt * 8.0) % len(loop)]
    if ph == "to_idle" and off_fr:
        idx = min(len(off_fr) - 1, int(tt * (len(off_fr) / off_sec if off_sec else fps)))
        return off_fr[idx]
    return idle or (loop[0] if loop else None)


def preview_extent(pack):
    """(width, height, scale) of the panel of a ship preview: the idle picture at 168 px high, and room for every
    picture of the ship (the halo of the flash is left out: it may go a little beyond the panel)."""
    idle = pack.get("idle")
    if idle is None:
        return 168, 168, 1.0
    scale = 168 / max(1, idle.get_height())
    mw = mh = 1
    for key in ("idle", "anim", "on", "off"):
        frs = pack.get(key)
        if frs is None:
            continue
        if not isinstance(frs, (list, tuple)):
            frs = [frs]
        core = pack.get("core_size") if key in ("on", "off") else None
        if core:
            mw = max(mw, int(core[0] * scale))
            mh = max(mh, int(core[1] * scale))
            continue
        for fr in frs:
            if fr is None:
                continue
            mw = max(mw, int(fr.get_width() * scale))
            mh = max(mh, int(fr.get_height() * scale))
    return mw, mh, scale


def draw_ship_select(game, surface):
    slot = int(getattr(game, "ship_select_slot", 1) or 1)
    two_p = getattr(game, "play_mode", "solo") in ("hotseat", "coop")
    if two_p:
        heading = t("choose_ship_p").replace("{n}", str(slot))
    else:
        heading = t("choose_ship")
    title = game._txt(game.medium_font, heading, (255, 230, 140))
    surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 72))
    ids = ("phoenix", "shield")
    labels = (t("ship_phoenix"), t("ship_shield"))
    focus = int(getattr(game, "ship_select_index", 0)) % 2
    locked = getattr(game, "ship_select_locked", False)
    chosen = ids[focus]
    # Coop final lock: two different hulls → both stay lit + timer under each
    both_lit = (
        locked
        and getattr(game, "play_mode", "solo") == "coop"
        and int(getattr(game, "ship_select_slot", 1) or 1) == 2
        and getattr(game, "ship_id", "phoenix") != chosen
    )
    anim_t = getattr(game, "ship_anim_t", 0.0)
    previews = getattr(game, "preview_ships", {})
    slots = (BASE_WIDTH // 2 - 220, BASE_WIDTH // 2 + 220)
    cy = 292
    pad = 18
    def _pack_for(sid):
        pack = previews.get(sid) or {}
        tint = game._tint_of(sid, slot)
        pack = previews.get(sid + "_" + tint) or pack
        return pack
    box_w = box_h = 1
    scales = {}
    for sid in ids:
        mw, mh, sc = preview_extent(_pack_for(sid))
        scales[sid] = sc
        box_w = max(box_w, mw)
        box_h = max(box_h, mh)
    for i, sid in enumerate(ids):
        cx = slots[i]
        pack = _pack_for(sid)
        idle = pack.get("idle")
        frames = pack.get("anim") or []
        img = idle
        active = (i == focus) or both_lit
        if active:
            img = game._preview_cycle_frame(pack, idle, frames)
        if img is None:
            continue
        scale = scales.get(sid, 168 / max(1, (idle or img).get_height()))
        tw = max(1, int(img.get_width() * scale))
        th = max(1, int(img.get_height() * scale))
        spr = pygame.transform.smoothscale(img, (tw, th))
        max_w, max_h = box_w, box_h
        if locked and (not active):
            spr = spr.copy()
            spr.fill((80, 80, 90, 160), special_flags=pygame.BLEND_RGBA_MULT)
        if active:
            bob = int(math.sin(anim_t * (5.0 if locked else 3.2)) * 4)
        else:
            bob = 0
        rx = cx - tw // 2
        ry = cy - th // 2 + bob
        box = pygame.Rect(
            cx - box_w // 2 - pad,
            cy - box_h // 2 - pad,
            box_w + pad * 2,
            box_h + pad * 2,
        )
        if active:
            col_box = (255, 240, 120) if locked else (255, 210, 90)
            pygame.draw.rect(surface, col_box, box, 3 if locked else 2, border_radius=10)
        else:
            pygame.draw.rect(surface, (70, 70, 90), box, 2, border_radius=10)
        solo_slide = (
            i == focus
            and float(getattr(game, "shield_slide", 1.0)) < 0.999
            and not locked
        )
        if solo_slide:
            tslide = min(1.0, max(0.0, float(game.shield_slide)))
            sdir = int(getattr(game, "shield_slide_dir", -1) or -1)
            pad_in = 6
            clip = pygame.Rect(rx - 12 + pad_in, ry - 12 + pad_in, tw + 24 - pad_in * 2, th + 24 - pad_in * 2)
            if active:
                clip = pygame.Rect(box.x + 5, box.y + 5, box.w - 10, box.h - 10)
            other_key = getattr(game, "shield_slide_from", "red")
            other_pack = previews.get(sid + "_" + str(other_key)) or pack
            other_img = other_pack.get("idle")
            ofr = other_pack.get("anim") or []
            if active and ofr:
                other_img = ofr[int(anim_t * 8.0) % len(ofr)]
            if other_img is not None:
                oscale = scale
                ow = max(1, int(other_img.get_width() * oscale))
                oh = max(1, int(other_img.get_height() * oscale))
                other_spr = pygame.transform.smoothscale(other_img, (ow, oh))
            else:
                other_spr = spr
                ow, oh = tw, th
            travel = clip.h
            old_oy = int(sdir * tslide * travel)
            new_oy = int(-sdir * (1.0 - tslide) * travel)
            surface.set_clip(clip)
            surface.blit(other_spr, (cx - ow // 2, ry + old_oy))
            surface.blit(spr, (rx, ry + new_oy))
            surface.set_clip(None)
        else:
            surface.blit(spr, (rx, ry))
        if locked and active:
            blink = int(anim_t * 6) % 2 == 0
            col = (255, 255, 200) if blink else (255, 170, 60)
        elif i == focus:
            col = (255, 230, 120)
        else:
            col = (90, 90, 105) if locked else (150, 150, 175)
        name = game._txt(game.font, labels[i], col)
        surface.blit(name, (cx - name.get_width() // 2, box.bottom + 10))
        # color label omitted — slide animation carries the tint
        if locked and hasattr(game, "sounds") and game.sounds.vo_is_busy() and active:
            pbar = game.sounds.vo_progress()
            bw, bh = 120, 6
            bx = cx - bw // 2
            by = box.bottom + 48
            pygame.draw.rect(surface, (40, 40, 50), pygame.Rect(bx, by, bw, bh), border_radius=3)
            pygame.draw.rect(surface, (255, 200, 80), pygame.Rect(bx, by, max(2, int(bw * pbar)), bh), border_radius=3)
    hint = game._txt(game.font, t("ship_hint"), (160, 160, 190))
    surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 42))
