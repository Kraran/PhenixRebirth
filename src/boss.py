"""
Stage 5 boss: Phoenix-style mothership saucer.

- Destructible armor cells (1 pt) and top decorations (50 pts)
- Central core alien (200 / 300 pts on Veteran) once a firing lane is open
- Slow horizontal drift + continuous descent (contact is fatal)
- Up to 5 saucer bullets on screen; spawns stage-1/2 birds via Game

Purple band cells scroll horizontally to complicate core shots.
"""
import pygame
import math
import os
import random
from settings import *
from settings import asset_path

class ArmorCell:
    def __init__(self, x, y, w, h, color, color_dark, tile=None):
        self.base_x = float(x)
        self.base_y = float(y)
        self.x = float(x)
        self.y = float(y)
        self.w = w
        self.h = h
        self.alive = True
        self.color = color
        self.color_dark = color_dark
        self.tile = tile  # optional subsurface of the photo hull

    def get_hitbox(self):
        if not self.alive:
            return pygame.Rect(0, 0, 0, 0)
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h / 2), self.w, self.h)

    def draw(self, surface):
        if not self.alive:
            return
        r = self.get_hitbox()
        if self.tile is not None:
            surface.blit(self.tile, r.topleft)
            return
        pygame.draw.rect(surface, self.color, r)
        pygame.draw.rect(surface, self.color_dark, r, 1)
        pygame.draw.circle(surface, self.color_dark, (r.centerx, r.centery), 2)



class SaucerDecoration:
    """Destructible top decorations: dish, cannon, turret — 50 pts."""
    KINDS = ("dish", "cannon", "turret", "radar", "port", "gen")
    _dish_l = None
    _dish_r = None
    _port_glow_frames = None

    @classmethod
    def load_dish_frames(cls):
        if cls._dish_l:
            return
        frames = []
        folder = asset_path("sprites", "dish_anim")
        for i in range(1, 11):
            fp = os.path.join(folder, f"dish_{i:02d}.png")
            if not os.path.isfile(fp):
                continue
            try:
                frames.append(pygame.image.load(fp).convert_alpha())
            except Exception:
                pass
        cls._dish_l = frames
        cls._dish_r = [pygame.transform.flip(f, True, False) for f in frames]

    def __init__(self, x, y, kind="dish", image=None, w=None, h=None, mirror=False):
        self.base_x = float(x)
        self.base_y = float(y)
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.alive = True
        self.image = image
        if image is not None:
            self.w = image.get_width()
            self.h = image.get_height()
        else:
            self.w = 28 if w is None else w
            self.h = 24 if h is None else h
        self.frames = []
        self.anim_i = 0.0
        self.anim_phase = "idle"
        self.anim_target = 0
        self.anim_wait = random.uniform(3.0, 8.0)
        self.anim_fps = 5.2
        self.glow_t = random.uniform(0, 6.0)
        self.glow_ox = 0.0
        self.glow_oy = 0.0
        if image is not None and kind == "port":
            try:
                arr = pygame.surfarray.array3d(image)
                # (w,h,3)
                best = 0
                bx = by = image.get_width() // 2, image.get_height() // 2
                w, h = image.get_width(), image.get_height()
                step = 2
                for x in range(0, w, step):
                    for y in range(0, h, step):
                        r, g, b = int(arr[x, y, 0]), int(arr[x, y, 1]), int(arr[x, y, 2])
                        score = r - g - b
                        if r > 140 and score > best:
                            best = score
                            bx, by = x, y
                self.glow_ox = bx - w / 2.0
                self.glow_oy = by - h / 2.0
            except Exception:
                self.glow_ox, self.glow_oy = (-self.w * 0.28, 0.0)
        if kind == "dish":
            self.load_dish_frames()
            src = self._dish_r if mirror else self._dish_l
            if src:
                tw, th = self.w, self.h
                self.frames = [
                    pygame.transform.smoothscale(f, (tw, th)) if (f.get_width() != tw or f.get_height() != th) else f
                    for f in src
                ]
                self.anim_ox = 0.0
                self.anim_oy = 0.0
                if self.frames:
                    fr = self.frames[0]
                    try:
                        arr = pygame.surfarray.array_alpha(fr)
                        # array_alpha is (w, h)
                        total = sx = sy = 0
                        w, h = fr.get_width(), fr.get_height()
                        step = 2
                        for x in range(0, w, step):
                            col = arr[x]
                            for y in range(0, h, step):
                                if col[y] > 30:
                                    total += 1
                                    sx += x
                                    sy += y
                        if total:
                            self.anim_ox = sx / total - w / 2.0
                            self.anim_oy = sy / total - h / 2.0
                    except Exception:
                        self.anim_ox = self.anim_oy = 0.0

    def get_hitbox(self):
        if not self.alive:
            return pygame.Rect(0, 0, 0, 0)
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h / 2), self.w, self.h)

    def _draw_port_glow(self, surface):
        phase = (id(self) % 7) * 0.9
        t = pygame.time.get_ticks() * 0.001 + phase
        wave = 0.5 + 0.5 * math.sin(t * 4.6)
        pulse = 0.00 + 0.90 * wave
        gx = int(self.x + getattr(self, "glow_ox", 0.0))
        gy = int(self.y + getattr(self, "glow_oy", 0.0))
        frames = SaucerDecoration._port_glow_frames
        if not frames:
            frames = []
            for i in range(9):
                pu = i / 8.0
                g = pygame.Surface((56, 56), pygame.SRCALPHA)
                pygame.draw.circle(g, (160, 12, 8, int(70 * pu)), (28, 28), int(14 + 6 * pu))
                pygame.draw.circle(g, (255, 30, 16, int(110 * pu)), (28, 28), int(8 + 3 * pu))
                pygame.draw.circle(g, (255, 80, 30, int(160 * pu)), (28, 28), 5)
                pygame.draw.circle(g, (255, 230, 190, int(220 * pu)), (28, 28), 2)
                frames.append(g)
            SaucerDecoration._port_glow_frames = frames
        idx = max(0, min(8, int(round(pulse * 8))))
        surface.blit(frames[idx], (gx - 28, gy - 28), special_flags=pygame.BLEND_ADD)

    def tick(self, dt):
        self.glow_t = getattr(self, "glow_t", 0.0) + dt
        if not self.alive or not self.frames:
            return
        n = len(self.frames)
        if self.anim_phase == "idle":
            self.anim_wait -= dt
            if self.anim_wait <= 0:
                last = min(n - 1, 9)  # frame 10 max — later frames leave the mount
                pct = random.uniform(0.30, 1.00)
                self.anim_target = max(1, int(round(pct * last)))
                self.anim_phase = "fwd"
        elif self.anim_phase == "fwd":
            self.anim_i += self.anim_fps * dt
            if self.anim_i >= self.anim_target:
                self.anim_i = float(self.anim_target)
                self.anim_phase = "back"
        elif self.anim_phase == "back":
            self.anim_i -= self.anim_fps * dt
            if self.anim_i <= 0:
                self.anim_i = 0.0
                self.anim_phase = "idle"
                self.anim_wait = random.uniform(8.0, 16.0)

    def draw(self, surface):
        if not self.alive:
            return
        if self.frames:
            idx = int(self.anim_i) % len(self.frames)
            img = self.frames[idx]
            ox = getattr(self, "anim_ox", 0.0)
            oy = getattr(self, "anim_oy", 0.0)
            surface.blit(
                img,
                (int(self.x - img.get_width() / 2 - ox),
                 int(self.y - img.get_height() / 2 - oy)),
            )
            return
        if self.image is not None:
            surface.blit(
                self.image,
                (int(self.x - self.w / 2), int(self.y - self.h / 2)),
            )
            if self.kind == "port":
                self._draw_port_glow(surface)
            return
        cx, cy = int(self.x), int(self.y)
        if self.kind == "dish":
            # Parabolic antenna
            pygame.draw.circle(surface, (180, 180, 200), (cx, cy), 12, 2)
            pygame.draw.arc(surface, (220, 220, 240), (cx - 14, cy - 10, 28, 20), 0.2, 2.9, 2)
            pygame.draw.line(surface, (140, 140, 160), (cx, cy + 4), (cx, cy + 14), 2)
            pygame.draw.circle(surface, (255, 200, 80), (cx, cy - 2), 3)
        elif self.kind == "cannon":
            # Twin barrel cannon pointing down-ish / up
            pygame.draw.rect(surface, (90, 90, 110), (cx - 10, cy - 4, 20, 12))
            pygame.draw.rect(surface, (60, 60, 80), (cx - 12, cy - 2, 6, 10))
            pygame.draw.rect(surface, (60, 60, 80), (cx + 6, cy - 2, 6, 10))
            pygame.draw.circle(surface, (200, 60, 60), (cx - 9, cy - 4), 2)
            pygame.draw.circle(surface, (200, 60, 60), (cx + 9, cy - 4), 2)
        elif self.kind == "turret":
            pygame.draw.circle(surface, (100, 110, 90), (cx, cy + 2), 10)
            pygame.draw.rect(surface, (70, 80, 60), (cx - 3, cy - 12, 6, 14))
            pygame.draw.circle(surface, (255, 80, 40), (cx, cy - 12), 3)
        else:  # radar
            pygame.draw.line(surface, (160, 200, 255), (cx, cy + 8), (cx, cy - 10), 2)
            pygame.draw.circle(surface, (100, 180, 255), (cx, cy - 10), 6, 1)
            pygame.draw.line(surface, (200, 230, 255), (cx, cy - 10), (cx + 8, cy - 14), 1)
            pygame.draw.circle(surface, (255, 255, 100), (cx + 8, cy - 14), 2)


class BossBullet:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.alive = True
        self.speed = 280.0

    def update(self, dt):
        self.y += self.speed * dt
        if self.y > BASE_HEIGHT + 20:
            self.alive = False

    def get_hitbox(self):
        return pygame.Rect(int(self.x) - 3, int(self.y), 7, 14)

    def draw(self, surface):
        if not self.alive:
            return
        pygame.draw.rect(surface, (255, 80, 200), (int(self.x) - 3, int(self.y), 7, 14))
        pygame.draw.rect(surface, (255, 180, 255), (int(self.x) - 1, int(self.y), 3, 14))


class BossCore:
    """Cthulhu-esque alien core in the saucer center — 200 / 300 pts."""
    _image = None
    _image_white = None
    _frames = None
    _frames_white = None
    ANIM_FPS = 8.0

    @classmethod
    def _whiten(cls, src):
        w, h = src.get_size()
        white = pygame.Surface((w, h), pygame.SRCALPHA)
        for yy in range(h):
            for xx in range(w):
                r, g, b, a = src.get_at((xx, yy))
                if a > 20:
                    white.set_at((xx, yy), (255, 255, 255, a))
        return white

    @classmethod
    def _load_images(cls):
        if cls._frames:
            return
        frames = []
        for i in range(8):
            path = asset_path("sprites", f"boss_core_{i:02d}.png")
            try:
                if not os.path.isfile(path):
                    continue
                frames.append(pygame.image.load(path).convert_alpha())
            except Exception:
                pass
        if not frames:
            path = asset_path("sprites", "boss_core.png")
            try:
                frames = [pygame.image.load(path).convert_alpha()]
            except Exception as e:
                print("boss_core load failed:", e)
                cls._image = None
                cls._frames = []
                return
        cls._frames = frames
        cls._image = frames[0]
        cls._frames_white = [cls._whiten(f) for f in frames]
        cls._image_white = cls._frames_white[0] if cls._frames_white else None

    def __init__(self, x, y, fit=None):
        BossCore._load_images()
        self.base_x = float(x)
        self.base_y = float(y)
        self.x = float(x)
        self.y = float(y)
        self.alive = True
        self.dying = False
        self.death_timer = 0.0
        self.DEATH_DURATION = 1.2
        self.time = 0.0
        self.hit_flash = 0.0
        self._draw_frames = None
        src = None
        if BossCore._frames:
            src = BossCore._frames[0]
        elif BossCore._image is not None:
            src = BossCore._image
        if src is not None:
            self.w = src.get_width()
            self.h = src.get_height()
        else:
            self.w, self.h = 28, 32
        if fit and self.w > 0 and self.h > 0:
            tw, th = fit
            scale = min(tw / self.w, th / self.h)
            if scale > 0:
                self.w = max(16, int(self.w * scale))
                self.h = max(16, int(self.h * scale))
                srcs = BossCore._frames or ([BossCore._image] if BossCore._image else [])
                self._draw_frames = [
                    pygame.transform.smoothscale(f, (self.w, self.h)) for f in srcs
                ]
                if BossCore._frames_white:
                    self._draw_frames_white = [
                        pygame.transform.smoothscale(f, (self.w, self.h))
                        for f in BossCore._frames_white
                    ]
                else:
                    self._draw_frames_white = []

    def update(self, dt):
        self.time += dt
        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.dying:
            self.death_timer += dt
            if self.death_timer >= self.DEATH_DURATION:
                self.alive = False

    def kill(self):
        if self.dying or not self.alive:
            return
        self.dying = True
        self.death_timer = 0.0

    def get_hitbox(self):
        if not self.alive or self.dying:
            return pygame.Rect(0, 0, 0, 0)
        hw = max(28, int(self.w * 0.88))
        hh = max(28, int(self.h * 0.88))
        return pygame.Rect(int(self.x - hw // 2), int(self.y - hh // 2), hw, hh)

    def draw(self, surface):
        if not self.alive:
            return
        bob = self.y + math.sin(self.time * 3.0) * 2

        if self.dying:
            alpha_t = 1.0 - self.death_timer / self.DEATH_DURATION
            for i in range(5, 0, -1):
                r = int(22 + self.death_timer * 90 * i / 5)
                c = int(255 * alpha_t * (0.4 + 0.1 * i))
                pygame.draw.circle(surface, (c, c // 3, c // 2), (int(self.x), int(bob)), r, 2)
            return

        flash = self.hit_flash > 0 and int(self.hit_flash * 20) % 2 == 0
        frames = self._draw_frames or BossCore._frames or (
            [BossCore._image] if BossCore._image else []
        )
        img = None
        if frames:
            idx = int(self.time * BossCore.ANIM_FPS) % len(frames)
            img = frames[idx]
            whites = getattr(self, "_draw_frames_white", None) or BossCore._frames_white
            if flash and whites:
                img = whites[idx % len(whites)]
        if img is None:
            # Fallback procedural
            cx, cy = int(self.x), int(bob)
            col = (255, 255, 255) if flash else (40, 90, 70)
            pygame.draw.ellipse(surface, col, (cx - 14, cy - 16, 28, 32))
            return
        surface.blit(img, (int(self.x - img.get_width() // 2), int(bob - img.get_height() // 2)))


class BossSaucer:
    """
    Phoenix-style mothership:
    - ~3/4 screen width, thick oval hull
    - slowly descends
    - destructible armor cells
    - shoots up to 5 bullets on screen
    - boss core in the center
    """
    def __init__(self):
        self.cells = []
        self.decorations = []
        self.boss = None
        self.bullets = []
        self.time = 0.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.direction = 1
        self.speed = 32.0
        self.descend_speed = 2.8  # slow downward drift
        self.alive = True
        self.shoot_timer = 1.0
        self.pink_scroll = 0.0
        self._flick_t = 0.0
        self._flick_dur = random.uniform(1.2, 2.0)
        self._band_levels = None
        self._band_src_levels = []
        self._band_comp_sig = None
        self.can_shoot = True
        self.bird_rate = 1.0
        self._pair_done = set()
        self._build()

    _hull_img = None
    _hull_meta = None

    @classmethod
    def _load_hull(cls):
        if cls._hull_img is not None:
            return cls._hull_img, cls._hull_meta
        path = asset_path("sprites", "boss_saucer.png")
        meta_path = asset_path("sprites", "boss_saucer_meta.json")
        try:
            img = pygame.image.load(path).convert_alpha()
            meta = {"w": img.get_width(), "h": img.get_height(),
                    "hangar": [0, 0, 0, 0], "red": [0, 0]}
            try:
                import json
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta.update(json.load(f))
            except Exception:
                pass
            cls._hull_img = img
            cls._hull_meta = meta
            return img, meta
        except Exception as e:
            print("boss_saucer load failed:", e)
            cls._hull_img = False
            return None, None

    def _build(self):
        self.use_art = False
        self.hull_surf = None
        self.band_tile = None
        if self._build_art():
            return
        self._build_legacy()

    def _build_legacy(self):
        saucer_w = int(BASE_WIDTH * 0.75)
        cx = BASE_WIDTH // 2
        top_y = 70

        c_yellow = (230, 200, 50)
        c_yellow_d = (180, 140, 20)
        c_purple = (160, 60, 180)
        c_purple_d = (100, 30, 120)
        c_green = (140, 200, 60)
        c_green_d = (80, 140, 30)
        c_lime = (180, 230, 80)
        c_lime_d = (120, 170, 40)

        cell_w, cell_h = 26, 14

        # Yellow hull saucer silhouette: narrow bottom → wide middle →
        # slightly undercut under purple so side flanks stay open.
        hull_rows = [
            # y_off, half_count
            (0, 6, c_yellow, c_yellow_d),     # bottom tip
            (-14, 10, c_yellow, c_yellow_d),
            (-28, 13, c_yellow, c_yellow_d),
            (-42, 15, c_yellow, c_yellow_d),  # widest (saucer disk)
            (-56, 14, c_yellow, c_yellow_d),
            (-70, 11, c_yellow, c_yellow_d),  # under purple, sides open (purple is 14)
        ]
        for y_off, half, col, cold in hull_rows:
            for i in range(-half, half + 1):
                x = cx + i * (cell_w - 2)
                y = top_y + 120 + y_off
                self.cells.append(ArmorCell(x, y, cell_w - 2, cell_h - 2, col, cold))

        # Purple band (wider than upper yellow → exposed side flanks)
        for row in (0, -14):
            for i in range(-14, 15):
                x = cx + i * (cell_w - 2)
                y = top_y + 48 + row
                self.cells.append(ArmorCell(x, y, cell_w - 2, cell_h - 2, c_purple, c_purple_d))

        # Green upper dome (oval stepped)
        green_rows = [
            (32, 11, c_green, c_green_d),
            (18, 10, c_green, c_green_d),
            (4, 8, c_lime, c_lime_d),
            (-10, 6, c_lime, c_lime_d),
            (-24, 4, c_lime, c_lime_d),
            (-38, 2, c_lime, c_lime_d),
        ]
        for y_off, half, col, cold in green_rows:
            for i in range(-half, half + 1):
                x = cx + i * (cell_w - 2)
                y = top_y + y_off
                self.cells.append(ArmorCell(x, y, cell_w - 2, cell_h - 2, col, cold))

        # Two shorter bottom lines protecting the center (under the hull)
        bottom_y = top_y + 120 + 8  # just below main yellow hull bottom
        for row_i, half in enumerate((7, 5)):  # shorter than full width
            for i in range(-half, half + 1):
                x = cx + i * (cell_w - 2)
                y = bottom_y + row_i * 14
                cell = ArmorCell(x, y, cell_w - 2, cell_h - 2, c_yellow, c_yellow_d)
                cell.protect_center = True
                self.cells.append(cell)

        # Tag purple band cells for scrolling
        self.purple_cells = []
        for c in self.cells:
            if c.color == c_purple:
                c.is_purple = True
                c.scroll_base_x = c.base_x
                self.purple_cells.append(c)

        # Decorations flush on top of uppermost bricks — no gap
        # Use actual placed cells; skip center (boss); spread across width
        deco_dx_kinds = [
            (-380, "dish"),
            (-320, "radar"),
            (-265, "cannon"),
            (-200, "turret"),
            (-145, "dish"),
            (-85, "radar"),
            (60, "cannon"),
            (110, "dish"),
            (165, "radar"),
            (220, "turret"),
            (280, "cannon"),
            (340, "dish"),
            (400, "radar"),
        ]
        deco_h = 24
        for dx, kind in deco_dx_kinds:
            target_x = cx + dx
            # Topmost cell near this x (within half a cell width)
            candidates = [c for c in self.cells if abs(c.base_x - target_x) <= (cell_w - 2)]
            if not candidates:
                candidates = sorted(self.cells, key=lambda c: abs(c.base_x - target_x))[:5]
            top = min(candidates, key=lambda c: c.base_y - c.h / 2)
            brick_top = top.base_y - top.h / 2
            y = brick_top - deco_h / 2  # flush: deco bottom == brick top
            self.decorations.append(SaucerDecoration(top.base_x, y, kind))

        self.boss = BossCore(cx, top_y + 18)
        self.base_cx = cx
        self.top_y = top_y
        self.cell_w = cell_w - 2

        # No armor cells over the core hitbox (leave a clear window on the monster)
        core_r = self.boss.get_hitbox().inflate(10, 14)
        kept = []
        for c in self.cells:
            cr = pygame.Rect(
                int(c.base_x - c.w / 2), int(c.base_y - c.h / 2), c.w, c.h
            )
            if cr.colliderect(core_r):
                continue
            kept.append(c)
        self.cells = kept
        # Rebuild purple scroll list after filtering
        self.purple_cells = []
        for c in self.cells:
            if c.color == c_purple:
                c.is_purple = True
                c.scroll_base_x = c.base_x
                self.purple_cells.append(c)

    def _build_art(self):
        """C hull + dash ring + 6 decos. Brick grid is hitboxes that punch holes."""
        path = asset_path("sprites", "boss_saucer_c.png")
        band_path = asset_path("sprites", "boss_band_dash.png")
        if not os.path.isfile(path):
            return False
        try:
            raw = pygame.image.load(path).convert_alpha()
        except Exception as e:
            print("boss_saucer_c load failed:", e)
            return False
        src_w, src_h = raw.get_width(), raw.get_height()
        game_w = 840
        game_h = max(8, int(src_h * game_w / src_w))
        hull = pygame.transform.smoothscale(raw, (game_w, game_h))
        sx = game_w / src_w
        sy = game_h / src_h
        cx = BASE_WIDTH // 2
        origin_x = cx - game_w // 2
        origin_y = 18

        hangar_s = (457, 45, 653, 193)
        hangar = pygame.Rect(
            int(origin_x + hangar_s[0] * sx),
            int(origin_y + hangar_s[1] * sy),
            int((hangar_s[2] - hangar_s[0]) * sx),
            int((hangar_s[3] - hangar_s[1]) * sy),
        )
        band_y0 = origin_y + 249 * sy
        band_y1 = origin_y + 314 * sy
        # Keep the pointed rims solid so the belt does not cut the silhouette
        inset = 72
        band_x0 = origin_x + inset
        band_x1 = origin_x + game_w - inset

        cell_w = max(16, int(40 * sx))
        cell_h = max(10, int(20 * sy))
        c_hull, c_hull_d = (80, 80, 88), (30, 30, 36)
        c_band, c_band_d = (200, 40, 40), (100, 10, 10)
        self.cells = []
        cols = game_w // cell_w
        rows = game_h // cell_h
        for row in range(rows):
            for col in range(cols):
                px = col * cell_w
                py = row * cell_h
                if px + cell_w > game_w or py + cell_h > game_h:
                    continue
                wx = origin_x + px + cell_w / 2
                wy = origin_y + py + cell_h / 2
                if hangar.inflate(-8, -8).collidepoint(wx, wy):
                    continue
                opaque = 0
                step = 4
                for iy in range(0, cell_h, step):
                    for ix in range(0, cell_w, step):
                        if hull.get_at((min(game_w - 1, px + ix), min(game_h - 1, py + iy)))[3] > 40:
                            opaque += 1
                if opaque < 6:
                    continue
                in_band = (
                    (band_y0 - 4) <= wy <= (band_y1 + 4)
                    and band_x0 + 4 <= wx <= band_x1 - 4
                )
                colc, cold = (c_band, c_band_d) if in_band else (c_hull, c_hull_d)
                cell = ArmorCell(wx, wy, cell_w, cell_h, colc, cold)
                if in_band:
                    cell.is_purple = True
                    cell.scroll_base_x = cell.base_x
                self.cells.append(cell)
        self.purple_cells = [c for c in self.cells if getattr(c, "is_purple", False)]
        # Shield = exactly 2 brick rows. Drop extra hitboxes in the belt.
        if self.purple_cells:
            mid = (band_y0 + band_y1) / 2.0
            keys = sorted({int(round(c.base_y / max(1, cell_h))) for c in self.purple_cells})
            if len(keys) <= 2:
                keep_keys = set(keys)
            else:
                pair = min(
                    ((keys[i], keys[i + 1]) for i in range(len(keys) - 1)),
                    key=lambda pr: abs((pr[0] + pr[1]) * 0.5 * cell_h - mid),
                )
                keep_keys = {pair[0], pair[1]}
            kept_p = []
            kept_all = []
            for c in self.cells:
                k = int(round(c.base_y / max(1, cell_h)))
                in_belt = (band_y0 - 6) <= c.base_y <= (band_y1 + 6)
                if getattr(c, "is_purple", False):
                    if k in keep_keys:
                        kept_p.append(c)
                        kept_all.append(c)
                    # else drop ghost band cell
                elif in_belt:
                    # hull cell sitting in the belt → invisible brick, drop
                    continue
                else:
                    kept_all.append(c)
            self.cells = kept_all
            self.purple_cells = kept_p
            if kept_p:
                band_y0 = min(c.base_y - c.h / 2 for c in kept_p)
                band_y1 = max(c.base_y + c.h / 2 for c in kept_p)
                # Neon strip must not extend past the actual bricks
                # (leftover slivers at both caps were not hittable)
                band_x0 = min(c.base_x - c.w / 2 for c in kept_p)
                band_x1 = max(c.base_x + c.w / 2 for c in kept_p)

        # Destructible keel nav light (1 pt, like a brick)
        beacon_x = origin_x + game_w / 2.0
        beacon_y = origin_y + game_h - 6
        beacon = ArmorCell(beacon_x, beacon_y, 18, 14, (180, 30, 20), (80, 10, 8))
        beacon.is_beacon = True
        self.cells.append(beacon)
        self._beacon_cell = beacon

        self.decorations = []
        deco_boxes = [
            (28, 148, 155, 230, "port_l"),
            (125, 88, 235, 168, "cannon_l"),
            (168, 8, 295, 128, "dish_l"),
            (818, 8, 948, 128, "dish_r"),
            (868, 88, 990, 170, "cannon_r"),
            (955, 145, 1090, 235, "port_r"),
        ]
        for x0, y0, x1, y1, name in deco_boxes:
            if name.startswith("dish"):
                kind = "dish"
            elif name.startswith("cannon"):
                kind = "cannon"
            elif name.startswith("port"):
                kind = "port"
            else:
                kind = "turret"
            img = None
            p = asset_path("sprites", f"saucer_deco_{name}.png")
            if os.path.isfile(p):
                try:
                    img = pygame.image.load(p).convert_alpha()
                    dw = max(8, int(img.get_width() * sx))
                    dh = max(8, int(img.get_height() * sy))
                    img = pygame.transform.smoothscale(img, (dw, dh))
                except Exception:
                    img = None
            gx = origin_x + ((x0 + x1) / 2) * sx
            gy = origin_y + ((y0 + y1) / 2) * sy
            self.decorations.append(
                SaucerDecoration(gx, gy, kind, image=img, mirror=name.endswith("_r"))
            )

        band_h = max(12.0, band_y1 - band_y0)
        band_cy = (band_y0 + band_y1) / 2.0
        for name, at_right in (("gen_r", True), ("gen_l", False)):
            p = asset_path("sprites", f"saucer_deco_{name}.png")
            if not os.path.isfile(p):
                continue
            try:
                img = pygame.image.load(p).convert_alpha()
            except Exception:
                continue
            target_h = int(band_h * 1.35)
            target_w = int(img.get_width() * target_h / max(1, img.get_height()))
            target_w = max(24, min(130, target_w))
            img = pygame.transform.smoothscale(img, (target_w, target_h))
            if at_right:
                gx = band_x1 + target_w / 2.0 - 6
            else:
                gx = band_x0 - target_w / 2.0 + 6
            self.decorations.append(
                SaucerDecoration(gx, band_cy, "gen", image=img)
            )

        self.boss = BossCore(
            hangar.centerx,
            hangar.centery,
            fit=(int(hangar.w * 0.92), int(hangar.h * 0.92)),
        )
        self.base_cx = cx
        self.top_y = origin_y
        self.cell_w = cell_w
        self.hull_surf = hull
        under = hull.copy()
        under.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self._hull_under = under
        self.hull_origin = (origin_x, origin_y)
        self.hangar_rect = hangar
        self.band_window = (band_x0, band_y0, band_x1, band_y1)
        # Hide photo dishes — only the animated frames should show
        for d in self.decorations:
            if d.kind != "dish":
                continue
            rx = int(d.base_x - d.w / 2 - origin_x) + 6
            ry = int(d.base_y - d.h / 2 - origin_y) + 6
            rw = max(8, int(d.w) - 12)
            rh = max(8, int(d.h) - 12)
            self.hull_surf.fill((0, 0, 0, 0), pygame.Rect(rx, ry, rw, rh))
        under = self.hull_surf.copy()
        under.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self._hull_under = under
        self._hull_cache = None
        self._hull_sig = None
        # Strip the baked photo belt — only the rotating bricks should sit there
        ly0 = max(0, int(band_y0 - origin_y) - 2)
        ly1 = min(hull.get_height(), int(band_y1 - origin_y) + 2)
        lx0 = max(0, int(band_x0 - origin_x))
        lx1 = min(hull.get_width(), int(band_x1 - origin_x))
        if ly1 > ly0 and lx1 > lx0:
            self.hull_surf.fill((0, 0, 0, 0), pygame.Rect(lx0, ly0, lx1 - lx0, ly1 - ly0))
        self._fill_tip_metal(ly0, ly1, lx0, hull.get_width() - lx1)
        self._scrub_belt_neon(ly0, ly1)
        # Rebuild under from final hull, then pack interior keel cells
        under = self.hull_surf.copy()
        under.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        ox0, oy0 = origin_x, origin_y
        lower = [c for c in self.cells
                 if c.base_y >= band_y1 - 2 and not getattr(c, "is_purple", False)]
        by_row = {}
        for c in lower:
            key = int(round(c.base_y / max(1, cell_h)))
            by_row.setdefault(key, []).append(c)
        for row in by_row.values():
            xs = sorted(row, key=lambda c: c.base_x)
            if len(xs) <= 2:
                continue
            for c in xs[1:-1]:
                rx = int(c.base_x - c.w / 2 - ox0)
                ry = int(c.base_y - c.h / 2 - oy0)
                under.fill((0, 0, 0, 255), pygame.Rect(rx, ry, int(c.w), int(c.h)))
        self._hull_under = under
        try:
            bt = pygame.image.load(band_path).convert_alpha()
            bt = pygame.transform.smoothscale(
                bt, (max(16, int(bt.get_width() * sx)), max(8, int(band_y1 - band_y0)))
            )
            solid = pygame.Surface(bt.get_size(), pygame.SRCALPHA)
            solid.fill((0, 0, 0, 255))
            solid.blit(bt, (0, 0))
            self.band_tile = solid
        except Exception as e:
            print("band tile load failed:", e)
            self.band_tile = None
        self.use_art = True
        return True

    def _scrub_belt_neon(self, ly0, ly1):
        """Kill leftover photo neon in / under the belt (not a brick)."""
        hull = self.hull_surf
        hw, hh = hull.get_width(), hull.get_height()
        y0 = max(0, int(ly0) - 8)
        y1 = hh  # keel + anything under the belt
        for y in range(y0, y1):
            for x in range(hw):
                p = hull.get_at((x, y))
                if p[3] < 12:
                    continue
                r, g, b = p[0], p[1], p[2]
                if r >= 90 and r > g + 22 and r > b + 16:
                    hull.set_at((x, y), (0, 0, 0, 0))

    def _fill_tip_metal(self, ly0, ly1, cap_l, cap_r):
        """Replace baked red stubs at both rims with neighboring hull metal."""
        hull = self.hull_surf
        hw, hh = hull.get_width(), hull.get_height()
        cap_l = max(8, int(cap_l) + 6)
        cap_r = max(8, int(cap_r) + 6)
        src_y = max(0, int(ly0) - 12)
        zones = [range(0, min(cap_l, hw)), range(max(0, hw - cap_r), hw)]

        def is_neon(p):
            return p[3] >= 40 and p[0] > 140 and p[0] > p[1] + 35

        def metal_at(x, y0):
            for yy in range(y0, max(-1, y0 - 28), -1):
                p = hull.get_at((x, yy))
                if p[3] >= 60 and not is_neon(p):
                    return p
            for yy in range(min(hh - 1, int(ly1) + 8), min(hh, int(ly1) + 28)):
                p = hull.get_at((x, yy))
                if p[3] >= 60 and not is_neon(p):
                    return p
            return None

        for xs in zones:
            for x in xs:
                sample = metal_at(x, src_y)
                if sample is None:
                    continue
                for y in range(max(0, int(ly0) - 4), min(hh, int(ly1) + 4)):
                    dst = hull.get_at((x, y))
                    if dst[3] < 18:
                        continue
                    hull.set_at((x, y), sample)

    def _sync_positions(self):
        for c in self.cells:
            if not c.alive and not getattr(c, "is_purple", False):
                continue
            c.x = c.base_x + self.offset_x
            c.y = c.base_y + self.offset_y
        for d in self.decorations:
            d.x = d.base_x + self.offset_x
            d.y = d.base_y + self.offset_y
        self.boss.x = self.boss.base_x + self.offset_x
        self.boss.y = self.boss.base_y + self.offset_y

    def update(self, dt, player_x=0.0):
        self.time += dt
        # Horizontal drift
        self.offset_x += self.direction * self.speed * dt
        if self.offset_x > 50:
            self.direction = -1
        elif self.offset_x < -50:
            self.direction = 1

        # Slow descent
        self.offset_y += self.descend_speed * dt

        # Pink/purple band scrolls horizontally on itself
        self.pink_scroll += 28.0 * dt
        self._flick_t += dt
        if self._flick_t >= self._flick_dur:
            self._flick_t = 0.0
            self._flick_dur = random.uniform(1.2, 2.0)
        band_width = 29 * self.cell_w  # approx purple span

        self._sync_positions()
        for d in self.decorations:
            d.tick(dt)
        # Rotating shield: living AND dead band bricks travel together
        if self.purple_cells:
            if getattr(self, "use_art", False) and getattr(self, "band_window", None):
                min_x = self.band_window[0]
                span = max(self.cell_w, self.band_window[2] - self.band_window[0])
            else:
                xs = [c.scroll_base_x for c in self.purple_cells]
                min_x, max_x = min(xs), max(xs)
                span = max_x - min_x + self.cell_w
            for c in self.purple_cells:
                local = (c.scroll_base_x - min_x + self.pink_scroll) % span
                c.x = min_x + local + self.offset_x
                c.y = c.base_y + self.offset_y

        self.boss.update(dt)

        # Bullets
        for b in self.bullets[:]:
            b.update(dt)
            if not b.alive:
                self.bullets.remove(b)

        # Shoot up to 5 on screen
        self.shoot_timer -= dt
        if self.can_shoot and self.shoot_timer <= 0 and self.boss.alive and not self.boss.dying:
            alive_shots = sum(1 for b in self.bullets if b.alive)
            if alive_shots < 5:
                # Fire from random points along the purple band underside
                bx = self.boss.x + random.uniform(-180, 180)
                by = self.boss.y + 70 + self.offset_y * 0  # relative already in boss.y
                # Use lower hull y
                by = min(c.y for c in self.cells if c.alive) if any(c.alive for c in self.cells) else self.boss.y + 80
                # Actually fire from bottom of living cells near player
                candidates = [c for c in self.cells if c.alive and c.y > self.boss.y + 40]
                if candidates:
                    # Prefer near player x
                    candidates.sort(key=lambda c: abs(c.x - player_x))
                    src = candidates[random.randint(0, min(4, len(candidates) - 1))]
                    self.bullets.append(BossBullet(src.x, src.y + src.h / 2))
                else:
                    self.bullets.append(BossBullet(self.boss.x, self.boss.y + 40))
            self.shoot_timer = random.uniform(0.35, 0.75)

        if not self.boss.alive:
            self.alive = False

    def get_hull_hitbox(self):
        """Approximate bounding box of living armor for player collision."""
        living = [c for c in self.cells if c.alive]
        if not living:
            if self.boss.alive:
                return self.boss.get_hitbox()
            return pygame.Rect(0, 0, 0, 0)
        min_x = min(c.x - c.w / 2 for c in living)
        max_x = max(c.x + c.w / 2 for c in living)
        min_y = min(c.y - c.h / 2 for c in living)
        max_y = max(c.y + c.h / 2 for c in living)
        return pygame.Rect(int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y))


    def _pair_dead(self, kind):
        items = [d for d in self.decorations if d.kind == kind]
        return len(items) >= 2 and all(not d.alive for d in items)

    def _apply_pair_effects(self):
        """Both decos of a type down → saucer system drops out."""
        done = self._pair_done
        if "gen" not in done and self._pair_dead("gen"):
            done.add("gen")
            bw = getattr(self, "band_window", None)
            mid = (bw[1] + bw[3]) / 2.0 if bw else (
                min(c.base_y for c in self.purple_cells) +
                max(c.base_y for c in self.purple_cells)
            ) / 2.0 if self.purple_cells else 0
            for c in self.purple_cells:
                if c.base_y >= mid - 2:
                    c.alive = False
        if "port" not in done and self._pair_dead("port"):
            done.add("port")
            self.bird_rate = 0.28
        if "cannon" not in done and self._pair_dead("cannon"):
            done.add("cannon")
            self.can_shoot = False
        if "dish" not in done and self._pair_dead("dish"):
            done.add("dish")
            self.descend_speed = 0.0

    def _invalidate_cells(self):
        self._hit_order = None
        self._band_comp_sig = None
        self._hull_sig = None

    def _living_hit_order(self):
        order = getattr(self, "_hit_order", None)
        if order is None:
            order = [c for c in self.cells if c.alive]
            order.sort(key=lambda c: -c.y)
            self._hit_order = order
        return order

    def hit_bullet(self, bullet_rect):
        for deco in self.decorations:
            if deco.alive and bullet_rect.colliderect(deco.get_hitbox()):
                zone = deco.get_hitbox().inflate(
                    max(16, deco.w // 3), max(12, deco.h // 3)
                )
                deco.alive = False
                for cell in self.cells:
                    if not cell.alive or getattr(cell, "is_purple", False):
                        continue
                    if cell.get_hitbox().colliderect(zone):
                        cell.alive = False
                self._apply_pair_effects()
                self._invalidate_cells()
                return ("deco", deco)

        for cell in self._living_hit_order():
            if cell.alive and bullet_rect.colliderect(cell.get_hitbox()):
                cell.alive = False
                self._invalidate_cells()
                return ("cell", cell)

        if self.boss.alive and not self.boss.dying:
            if bullet_rect.colliderect(self.boss.get_hitbox()):
                return ("boss", self.boss)
        return None

    def living_cells(self):
        return sum(1 for c in self.cells if c.alive)

    def draw(self, surface):
        if getattr(self, "use_art", False) and self.hull_surf is not None:
            self._draw_art(surface)
        else:
            for cell in self.cells:
                cell.draw(surface)
            for d in self.decorations:
                d.draw(surface)
        self.boss.draw(surface)
        for b in self.bullets:
            b.draw(surface)

    def _ensure_hull_cache(self):
        dead_c = tuple(i for i, c in enumerate(self.cells)
                       if not c.alive and not getattr(c, "is_purple", False))
        dead_d = tuple(i for i, d in enumerate(self.decorations) if not d.alive)
        sig = (dead_c, dead_d)
        if sig == getattr(self, "_hull_sig", None) and getattr(self, "_hull_cache", None):
            return self._hull_cache
        ox0, oy0 = self.hull_origin
        hull = pygame.Surface(self.hull_surf.get_size(), pygame.SRCALPHA)
        # Black only where the photo is opaque — keeps the oval rim clean
        under = getattr(self, "_hull_under", None)
        if under is not None:
            hull.blit(under, (0, 0))
        hull.blit(self.hull_surf, (0, 0))
        for i in dead_c:
            c = self.cells[i]
            rx = int(c.base_x - c.w / 2 - ox0) - 2
            ry = int(c.base_y - c.h / 2 - oy0) - 2
            hull.fill((0, 0, 0, 0), pygame.Rect(rx, ry, int(c.w) + 4, int(c.h) + 4))
        for i in dead_d:
            d = self.decorations[i]
            rx = int(d.base_x - d.w / 2 - ox0)
            ry = int(d.base_y - d.h / 2 - oy0)
            hull.fill((0, 0, 0, 0), pygame.Rect(rx, ry, int(d.w), int(d.h)))
        try:
            hull = hull.convert_alpha()
        except Exception:
            pass
        self._hull_cache = hull
        self._hull_sig = sig
        return hull


    def _flick_bright(self):
        keys = (
            (0.00, 1.00), (0.12, 0.92), (0.18, 0.40), (0.22, 0.55),
            (0.28, 0.38), (0.40, 0.70), (0.52, 1.00), (0.68, 0.95),
            (0.74, 0.48), (0.82, 0.88), (1.00, 1.00),
        )
        dur = max(0.2, float(getattr(self, "_flick_dur", 1.5)))
        t = max(0.0, min(1.0, float(getattr(self, "_flick_t", 0.0)) / dur))
        for i in range(len(keys) - 1):
            t0, v0 = keys[i]
            t1, v1 = keys[i + 1]
            if t0 <= t <= t1:
                u = (t - t0) / max(1e-6, t1 - t0)
                u = u * u * (3 - 2 * u)
                return v0 + (v1 - v0) * u
        return 1.0

    def _band_tile_lit(self):
        if not self.band_tile:
            return None
        if not self._band_levels:
            levels = []
            for i in range(9):
                b = 0.32 + 0.68 * (i / 8.0)
                s = self.band_tile.copy()
                s.fill(
                    (int(255 * b), int(255 * b), int(255 * b), 255),
                    special_flags=pygame.BLEND_RGBA_MULT,
                )
                levels.append(s)
            self._band_levels = levels
        b = self._flick_bright()
        idx = int(round((b - 0.32) / 0.68 * 8))
        idx = max(0, min(8, idx))
        return self._band_levels[idx]

    def _ensure_band_src(self, bw, th, tw):
        key = (bw, th, tw)
        if getattr(self, "_band_src_key", None) == key and self._band_src_levels:
            return
        self._band_tile_lit()  # build 9 tile shades
        self._band_src_levels = []
        for tile in (self._band_levels or [self.band_tile]):
            src = pygame.Surface((bw + tw, th), pygame.SRCALPHA)
            src.fill((0, 0, 0, 255))
            x = 0
            while x < bw + tw:
                src.blit(tile, (x, 0))
                x += tw
            try:
                src = src.convert_alpha()
            except Exception:
                pass
            self._band_src_levels.append(src)
        self._band_layer = pygame.Surface((bw, th), pygame.SRCALPHA)
        self._band_src_key = key
        self._band_comp_sig = None

    def _draw_keel_beacon(self, surface):
        """Tiny blinking red nav light under the saucer."""
        if not self.alive:
            return
        t = pygame.time.get_ticks() * 0.001
        on = (t % 1.15) < 0.62
        pulse = (0.55 + 0.45 * math.sin(t * 14.0)) if on else 0.0
        if pulse <= 0.02:
            return
        ox = int(self.hull_origin[0] + self.offset_x)
        oy = int(self.hull_origin[1] + self.offset_y)
        cell = getattr(self, "_beacon_cell", None)
        if cell is None or not cell.alive:
            return
        hx = int(cell.x)
        hy = int(cell.y)
        frames = getattr(BossSaucer, "_beacon_frames", None)
        if not frames:
            frames = []
            for i in range(9):
                pu = i / 8.0
                g = pygame.Surface((28, 28), pygame.SRCALPHA)
                pygame.draw.circle(g, (160, 10, 8, int(80 * pu)), (14, 14), 8)
                pygame.draw.circle(g, (255, 40, 20, int(140 * pu)), (14, 14), 4)
                pygame.draw.circle(g, (255, 200, 160, int(200 * pu)), (14, 14), 2)
                frames.append(g)
            BossSaucer._beacon_frames = frames
        idx = max(0, min(8, int(round(pulse * 8))))
        surface.blit(frames[idx], (hx - 14, hy - 14), special_flags=pygame.BLEND_ADD)

    def _draw_art(self, surface):
        ox = int(self.hull_origin[0] + self.offset_x)
        oy = int(self.hull_origin[1] + self.offset_y)
        surface.blit(self._ensure_hull_cache(), (ox, oy))
        living_band = any(c.alive for c in self.purple_cells)
        if self.band_tile is not None and living_band:
            bx0, by0, bx1, by1 = self.band_window
            tw = max(1, self.band_tile.get_width())
            th = max(1, int(by1 - by0))
            bw = max(1, int(bx1 - bx0))
            self._ensure_band_src(bw, th, tw)
            shift = int(self.pink_scroll) % tw
            b = self._flick_bright()
            fidx = max(0, min(8, int(round((b - 0.32) / 0.68 * 8))))
            dead = tuple(i for i, c in enumerate(self.purple_cells) if not c.alive)
            sig = (shift, fidx, dead)
            layer = self._band_layer
            if sig != getattr(self, "_band_comp_sig", None):
                srcs = self._band_src_levels or []
                src = srcs[fidx] if fidx < len(srcs) else (srcs[0] if srcs else None)
                layer.fill((0, 0, 0, 255))
                if src is not None:
                    layer.blit(src, (-shift, 0))
                layer_origin_x = bx0 + self.offset_x
                layer_origin_y = by0 + self.offset_y
                for c in self.purple_cells:
                    if c.alive:
                        continue
                    hx = pygame.Rect(
                        int(c.x - c.w / 2 - layer_origin_x) - 3,
                        int(c.y - c.h / 2 - layer_origin_y) - 2,
                        int(c.w) + 6, int(c.h) + 4,
                    )
                    clip = hx.clip(pygame.Rect(0, 0, bw, th))
                    if clip.width > 0 and clip.height > 0:
                        layer.fill((0, 0, 0, 0), clip)
                    if hx.right > bw and hx.left < bw:
                        wrap = pygame.Rect(hx.x - bw, hx.y, hx.w, hx.h).clip(
                            pygame.Rect(0, 0, bw, th)
                        )
                        if wrap.width > 0 and wrap.height > 0:
                            layer.fill((0, 0, 0, 0), wrap)
                    if hx.left < 0:
                        wrap = pygame.Rect(hx.x + bw, hx.y, hx.w, hx.h).clip(
                            pygame.Rect(0, 0, bw, th)
                        )
                        if wrap.width > 0 and wrap.height > 0:
                            layer.fill((0, 0, 0, 0), wrap)
                self._band_comp_sig = sig
            surface.blit(layer, (int(bx0 + self.offset_x), int(by0 + self.offset_y)))
        self._draw_keel_beacon(surface)
        for d in self.decorations:
            if d.alive:
                d.draw(surface)
