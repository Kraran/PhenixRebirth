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
    def __init__(self, x, y, w, h, color, color_dark):
        self.base_x = float(x)
        self.base_y = float(y)
        self.x = float(x)
        self.y = float(y)
        self.w = w
        self.h = h
        self.alive = True
        self.color = color
        self.color_dark = color_dark

    def get_hitbox(self):
        if not self.alive:
            return pygame.Rect(0, 0, 0, 0)
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h / 2), self.w, self.h)

    def draw(self, surface):
        if not self.alive:
            return
        r = self.get_hitbox()
        pygame.draw.rect(surface, self.color, r)
        pygame.draw.rect(surface, self.color_dark, r, 1)
        pygame.draw.circle(surface, self.color_dark, (r.centerx, r.centery), 2)



class SaucerDecoration:
    """Destructible top decorations: dish, cannon, turret — 50 pts."""
    KINDS = ("dish", "cannon", "turret", "radar")

    def __init__(self, x, y, kind="dish"):
        self.base_x = float(x)
        self.base_y = float(y)
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.alive = True
        self.w = 28
        self.h = 24

    def get_hitbox(self):
        if not self.alive:
            return pygame.Rect(0, 0, 0, 0)
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h / 2), self.w, self.h)

    def draw(self, surface):
        if not self.alive:
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

    def __init__(self, x, y):
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
        hw = max(20, int(self.w * 0.55))
        hh = max(22, int(self.h * 0.55))
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
        frames = BossCore._frames or ([BossCore._image] if BossCore._image else [])
        img = None
        if frames:
            idx = int(self.time * BossCore.ANIM_FPS) % len(frames)
            img = frames[idx]
            if flash and BossCore._frames_white:
                img = BossCore._frames_white[idx % len(BossCore._frames_white)]
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
        self.descend_speed = 7.5  # slow downward drift
        self.alive = True
        self.shoot_timer = 1.0
        self.pink_scroll = 0.0
        self._build()

    def _build(self):
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

    def _sync_positions(self):
        for c in self.cells:
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
        band_width = 29 * self.cell_w  # approx purple span

        self._sync_positions()
        # Apply scroll only to purple band cells (wrap within band)
        if self.purple_cells:
            xs = [c.scroll_base_x for c in self.purple_cells]
            min_x, max_x = min(xs), max(xs)
            span = max_x - min_x + self.cell_w
            for c in self.purple_cells:
                if not c.alive:
                    continue
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
        if self.shoot_timer <= 0 and self.boss.alive and not self.boss.dying:
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

    def hit_bullet(self, bullet_rect):
        for cell in sorted(self.cells, key=lambda c: -c.y):
            if cell.alive and bullet_rect.colliderect(cell.get_hitbox()):
                cell.alive = False
                return ("cell", cell)

        for deco in self.decorations:
            if deco.alive and bullet_rect.colliderect(deco.get_hitbox()):
                deco.alive = False
                return ("deco", deco)

        if self.boss.alive and not self.boss.dying:
            if bullet_rect.colliderect(self.boss.get_hitbox()):
                return ("boss", self.boss)
        return None

    def living_cells(self):
        return sum(1 for c in self.cells if c.alive)

    def draw(self, surface):
        for cell in sorted(self.cells, key=lambda c: c.y):
            cell.draw(surface)
        for d in self.decorations:
            d.draw(surface)
        self.boss.draw(surface)
        for b in self.bullets:
            b.draw(surface)
