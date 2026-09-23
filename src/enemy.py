"""
Enemy units and formation logic.

Stage 1–2: small birds in drifting formation (dive + shoot).
Stage 3–4: free-roaming BigBird gargoyles with destructible wings.
Stage loops reuse these templates with a speed multiplier.

Scoring is handled by the Game class (difficulty may add a veteran bonus).
"""
import pygame
import os
from settings import asset_path
import math
import random
from settings import *

class EnemyBullet:
    def __init__(self, x, y, stage=1):
        self.x = float(x)
        self.y = float(y)
        self.alive = True
        self.stage = stage
        self.owner_id = None

    def update(self, dt):
        self.prev_y = getattr(self, "prev_y", self.y)
        self.prev_y = self.y
        self.y += ENEMY_BULLET_SPEED * dt
        if self.y > BASE_HEIGHT + 20:
            self.alive = False

    def draw(self, surface):
        if not self.alive:
            return
        # Same pink as stage-1 birds, all stages / boss fodder
        pygame.draw.rect(surface, (255, 80, 200), (int(self.x) - 3, int(self.y), 6, 12))
        pygame.draw.rect(surface, (255, 180, 255), (int(self.x) - 1, int(self.y), 2, 12))

    def get_hitbox(self):
        prev = getattr(self, "prev_y", self.y)
        top = min(float(prev), float(self.y))
        h = max(12.0, abs(float(prev) - float(self.y)) + 12.0)
        return pygame.Rect(int(self.x) - 4, int(top), 8, int(h))


def _whiten_surf(src):
    """Opaque-white copy keeping source alpha. Cached by caller."""
    w, h = src.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.blit(src, (0, 0))
    out.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_ADD)
    # force RGB to white where alpha remains
    arr_ok = False
    try:
        out.fill((255, 255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
        arr_ok = True
    except Exception:
        pass
    if not arr_ok:
        out = src.copy()
        for y in range(h):
            for x in range(w):
                r, g, b, a = src.get_at((x, y))
                if a > 20:
                    out.set_at((x, y), (255, 255, 255, a))
    return out


class Enemy:
    def __init__(self, x, y, formation_index=0, stage=1):
        self.x = float(x)
        self.y = float(y)
        self.start_x = float(x)
        self.start_y = float(y)
        self.stage = stage
        
        self.width = 36
        self.height = 28
        self.alive = True
        
        self.formation_index = formation_index
        self.time = 0.0
        
        # States: "formation" | "diving" | "returning"
        self.state = "formation"
        self.dive_target_x = 0.0
        self.shoot_cooldown = 0.0
        
        # Death / disappearance animation
        self.dying = False
        self.death_timer = 0.0
        self.DEATH_DURATION = 0.38
        self.death_flash = False
        self._white_image = None
        
        self.anim_t = 0.0
        self.eye_glow = False
        self.frames = None  # stage-1 animated frames
        # Desync wing/eye anim slightly per bird
        self.anim_phase = random.random() * 10.0
        self.flap_rate = 5.2 + random.uniform(-0.9, 0.9)
        self.glow_period = 2.0 + random.uniform(-0.5, 0.7)
        self.glow_len = 0.35 + random.uniform(-0.08, 0.12)
        if stage in (1, 2):
            self.frames = self._load_bird_frames(stage)
            self.image = self.frames[0]
            self.width = self.image.get_width()
            self.height = self.image.get_height()
            self.hitbox_w = max(22, int(self.width * 0.78))
            self.hitbox_h = max(20, int(self.height * 0.78))
        else:
            self.image = self._create_bird_sprite(stage=stage)
            self.hitbox_w = 26
            self.hitbox_h = 20
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.active_shots = 0  # bullets currently on screen from this enemy


    def _load_bird_frames(self, stage=1):
        """Animated bird frames: stage1 blue-grey, stage2 green/khaki."""
        base = asset_path("sprites")
        prefix = "bird2" if stage >= 2 else "bird1"
        names = [
            f"{prefix}_flap0.png",
            f"{prefix}_flap1.png",
            f"{prefix}_flap0_glow.png",
            f"{prefix}_flap1_glow.png",
        ]
        frames = []
        for n in names:
            p = os.path.join(base, n)
            if os.path.exists(p):
                frames.append(pygame.image.load(p).convert_alpha())
        if not frames:
            self.width, self.height = 36, 28
            return [self._create_bird_sprite(stage=stage)]
        return frames

    def _create_bird_sprite(self, stage=1):
        surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        
        if stage >= 2:
            # Blue birds for stage 2
            c_body = (60, 120, 230)
            c_body_dark = (30, 70, 180)
            c_body_light = (120, 180, 255)
            c_wing = (50, 100, 210)
            c_wing_tip = (100, 220, 255)
            c_eye = (255, 255, 200)
            c_beak = (200, 220, 255)
        else:
            c_body = (170, 60, 220)
            c_body_dark = (110, 30, 160)
            c_body_light = (210, 110, 255)
            c_wing = (150, 45, 200)
            c_wing_tip = (255, 120, 255)
            c_eye = (255, 230, 80)
            c_beak = (255, 160, 40)
        
        cx = self.width // 2
        cy = self.height // 2
        
        pygame.draw.polygon(surf, c_wing, [
            (cx - 16, cy - 2), (cx - 4, cy - 8), (cx - 4, cy + 4)
        ])
        pygame.draw.polygon(surf, c_wing, [
            (cx + 16, cy - 2), (cx + 4, cy - 8), (cx + 4, cy + 4)
        ])
        
        pygame.draw.circle(surf, c_wing_tip, (cx - 15, cy - 1), 3)
        pygame.draw.circle(surf, c_wing_tip, (cx + 15, cy - 1), 3)
        
        pygame.draw.ellipse(surf, c_body, (cx - 9, cy - 9, 18, 18))
        pygame.draw.ellipse(surf, c_body_light, (cx - 6, cy - 7, 12, 10))
        pygame.draw.circle(surf, c_body, (cx, cy - 6), 7)
        
        pygame.draw.circle(surf, c_eye, (cx - 3, cy - 7), 2)
        pygame.draw.circle(surf, c_eye, (cx + 3, cy - 7), 2)
        
        pygame.draw.polygon(surf, c_beak, [
            (cx - 2, cy - 3), (cx + 2, cy - 3), (cx, cy + 1)
        ])
        
        pygame.draw.polygon(surf, c_body_dark, [
            (cx - 6, cy + 6), (cx, cy + 12), (cx + 6, cy + 6)
        ])
        
        return surf

    def update(self, dt, formation_offset_x=0.0, player_x=0.0):
        if not self.alive:
            return
        
        # Disappearance animation — no AI, just fade out
        if self.dying:
            if int(getattr(self, "hit_flash_frames", 0) or 0) > 0:
                self.hit_flash_frames -= 1
                return
            self.death_timer += dt
            self.death_flash = (int(self.death_timer * 20) % 2) == 0
            if self.death_timer >= self.DEATH_DURATION:
                self.alive = False
                self.dying = False
            return
            
        self.time += dt
        self.anim_t += dt
        self.shoot_cooldown = max(0.0, self.shoot_cooldown - dt)

        # Stage 1–2: wing flap + eye glow (desynchronized per bird)
        if self.frames and len(self.frames) >= 2:
            t = self.anim_t + self.anim_phase
            flap = int(t * self.flap_rate) % 2
            glow_phase = t % self.glow_period
            self.eye_glow = glow_phase < self.glow_len
            idx = flap
            if self.eye_glow and len(self.frames) >= 4:
                idx = flap + 2
            self.image = self.frames[idx]
        
        if self.state == "diving":
            sm = getattr(self, 'speed_mult', 1.0)
            self.y += ENEMY_DIVE_SPEED * sm * dt
            
            # Soft steer toward this bird's own lane — not a shared player X
            lane = getattr(self, "dive_lane", self.dive_target_x)
            dx = lane - self.x
            self.x += dx * 0.55 * dt
            self.x += math.sin(self.time * 5.5 + self.formation_index) * 36 * dt
            self.x = max(20, min(BASE_WIDTH - 20, self.x))
            
            if self.y > BASE_HEIGHT + 50:
                if random.random() < 0.18:
                    self.state = "returning"
                    self.y = -40
                else:
                    self.y = -40
                    # Keep a personal lane; slight wander, do not stack on player
                    jitter = random.uniform(-70, 70)
                    self.dive_lane = max(28, min(BASE_WIDTH - 28, lane + jitter))
                    self.dive_target_x = self.dive_lane
        
        elif self.state == "returning":
            target_x = self.start_x + formation_offset_x
            target_y = self.start_y
            
            dx = target_x - self.x
            dy = target_y - self.y
            dist = math.hypot(dx, dy)
            
            if dist < 12:
                self.state = "formation"
                self.x = target_x
                self.y = target_y
            else:
                speed = 320.0
                self.x += (dx / dist) * speed * dt
                self.y += (dy / dist) * speed * dt
        
        else:
            self.x = self.start_x + formation_offset_x
            self.y = self.start_y + math.sin(self.time * 2.5 + self.formation_index * 0.7) * 6
        
        self.rect.center = (int(self.x), int(self.y))

    def start_dive(self, player_x):
        if self.state != "formation" or not self.alive or self.dying:
            return
        self.state = "diving"
        slot = (self.formation_index % 7) - 3
        jitter = slot * 38 + random.uniform(-28, 28)
        self.dive_lane = max(28, min(BASE_WIDTH - 28, player_x + jitter))
        self.dive_target_x = self.dive_lane

    def kill(self, flash=True):
        """Start disappearance animation (idempotent)."""
        if not self.alive or self.dying:
            return
        self.dying = True
        self.death_timer = 0.0
        self.hit_flash_frames = 1 if flash else 0
        if not flash:
            self.alive = False
            self.dying = False

    @property
    def diving(self):
        return self.state == "diving" and not self.dying

    def can_shoot(self):
        return self.alive and not self.dying and self.shoot_cooldown <= 0.0

    def did_shoot(self):
        self.shoot_cooldown = 0.55

    def _get_white_image(self):
        if self._white_image is None:
            w, h = self.image.get_size()
            white = pygame.Surface((w, h), pygame.SRCALPHA)
            for y in range(h):
                for x in range(w):
                    r, g, b, a = self.image.get_at((x, y))
                    if a > 20:
                        white.set_at((x, y), (255, 255, 255, a))
            self._white_image = white
        return self._white_image

    def draw(self, surface):
        if not self.alive:
            return
        
        if self.dying:
            if int(getattr(self, "hit_flash_frames", 0) or 0) > 0:
                img = self._get_white_image()
                surface.blit(img, (int(self.x - self.width // 2), int(self.y - self.height // 2)))
                return
            t = self.death_timer / self.DEATH_DURATION
            alpha = max(0, int(255 * (1.0 - t)))
            scale = 1.0 + 0.28 * t
            
            img = self._get_white_image() if (self.death_flash and t < 0.5) else self.image
            w = max(1, int(self.width * scale))
            h = max(1, int(self.height * scale))
            scaled = pygame.transform.scale(img, (w, h))
            scaled.set_alpha(alpha)
            surface.blit(scaled, (int(self.x - w // 2), int(self.y - h // 2)))
        else:
            draw_x = int(self.x - self.width // 2)
            draw_y = int(self.y - self.height // 2)
            surface.blit(self.image, (draw_x, draw_y))

    def get_hitbox(self):
        if self.dying or not self.alive:
            return pygame.Rect(0, 0, 0, 0)
        return pygame.Rect(
            self.x - self.hitbox_w // 2,
            self.y - self.hitbox_h // 2,
            self.hitbox_w,
            self.hitbox_h
        )


class EnemyFormation:
    def __init__(self, stage=1):
        self.enemies = []
        self.bullets = []
        self.offset_x = 0.0
        self.direction = 1
        self.speed = ENEMY_SPEED
        self.time = 0.0
        self.stage = stage
        self.sounds = None  # set by Game
        self.spawn_stage(stage)

    def spawn_stage(self, stage, speed_mult=1.0):
        self.stage = stage
        self.speed_mult = speed_mult
        self.enemies = []
        self.bullets = []
        self.offset_x = 0.0
        self.direction = 1
        self.time = 0.0
        
        if stage >= 3:
            # Grand oiseaux libres — positions aleatoires
            self.speed = 0  # no formation drift for big birds
            self.offset_x = 0.0
            count = 10 if stage >= 4 else 7
            for idx in range(count):
                x = random.uniform(80, BASE_WIDTH - 80)
                y = random.uniform(80, 320)
                b = BigBird(x, y, formation_index=idx, stage=stage)
                b.speed_mult = speed_mult
                b.vx *= speed_mult
                b.vy *= speed_mult
                self.enemies.append(b)
            return
        elif stage >= 2:
            rows = [
                (5, 110),
                (6, 160),
                (6, 210),
                (5, 260),
            ]
            spacing = 88
            self.speed = ENEMY_SPEED * 1.15 * speed_mult
        else:
            rows = [
                (4, 130),
                (5, 185),
                (4, 240),
            ]
            spacing = 95
            self.speed = ENEMY_SPEED * speed_mult
        
        idx = 0
        for count, y in rows:
            total_width = (count - 1) * spacing
            start_x = (BASE_WIDTH - total_width) // 2
            for i in range(count):
                x = start_x + i * spacing
                e = Enemy(x, y, formation_index=idx, stage=stage)
                e.speed_mult = speed_mult
                self.enemies.append(e)
                idx += 1

    def update(self, dt, player_x):
        self.time += dt
        
        self.offset_x += self.direction * self.speed * dt
        if self.offset_x > 170:
            self.direction = -1
        elif self.offset_x < -170:
            self.direction = 1
        
        alive = self.get_alive_enemies()
        
        for enemy in alive:
            enemy.update(dt, self.offset_x, player_x)
            
            if enemy.dying:
                continue
            
            # Dive — rare for BigBird
            if isinstance(enemy, BigBird):
                if enemy.state == "roam" and random.random() < ENEMY_DIVE_CHANCE * 0.55:
                    enemy.start_dive(player_x)
            elif enemy.state == "formation":
                if random.random() < ENEMY_DIVE_CHANCE:
                    enemy.start_dive(player_x)
            
            if isinstance(enemy, BigBird):
                max_shots = 5 if self.stage >= 4 else 4
                chance = ENEMY_SHOOT_CHANCE * (4.5 if self.stage >= 4 else 4.0)
            elif self.stage >= 2:
                max_shots = 2
                chance = ENEMY_SHOOT_CHANCE * 1.5
            else:
                max_shots = 1
                chance = ENEMY_SHOOT_CHANCE
            
            if enemy.can_shoot() and enemy.state not in ("returning",):
                owned = sum(1 for b in self.bullets if b.alive and getattr(b, "owner_id", None) == id(enemy))
                if owned >= max_shots:
                    continue
                if enemy.state == "diving":
                    chance *= 1.8
                
                if random.random() < chance:
                    by = enemy.y + (20 if isinstance(enemy, BigBird) else 14)
                    bullet = EnemyBullet(enemy.x, by, stage=self.stage)
                    bullet.owner_id = id(enemy)
                    self.bullets.append(bullet)
                    enemy.did_shoot()
                    if self.sounds:
                        self.sounds.play("enemy_shoot", x=enemy.x)
        
        for bullet in self.bullets[:]:
            bullet.update(dt)
            if not bullet.alive:
                self.bullets.remove(bullet)
        # Drop finished corpses so later stages don't scan ghosts
        if any((not e.alive and not e.dying) for e in self.enemies):
            self.enemies = [e for e in self.enemies if e.alive or e.dying]

    def draw(self, surface):
        for enemy in self.enemies:
            if enemy.alive or enemy.dying:
                enemy.draw(surface)
        for bullet in self.bullets:
            if bullet.alive:
                bullet.draw(surface)

    def get_alive_enemies(self):
        return [e for e in self.enemies if e.alive]

    def get_hittable_enemies(self):
        return [e for e in self.enemies if e.alive and not e.dying]

    def all_dead(self):
        return not any(e.alive for e in self.enemies)




# ============================================================
# Stage 3 — Gargoyle space bird (horrific, free roam)
# ============================================================

class BigBird:
    """Large gargoyle-like predator. Layered transparent wings."""

    def __init__(self, x, y, formation_index=0, stage=3):
        self.x = float(x)
        self.y = float(y)
        self.start_x = float(x)
        self.start_y = float(y)
        self.formation_index = formation_index
        self.stage = stage

        self.width = 110
        self.height = 70
        self.alive = True
        self.dying = False
        self.death_timer = 0.0
        self.DEATH_DURATION = 0.50
        self.death_flash = False

        self.time = 0.0
        self.state = "roam"
        self.dive_target_x = 0.0
        self.shoot_cooldown = 0.0

        self.vx = random.choice([-1, 1]) * random.uniform(80, 140)
        self.vy = random.choice([-1, 1]) * random.uniform(50, 100)
        self.dir_timer = random.uniform(0.6, 1.8)

        self.wing_left = True
        self.wing_right = True
        self.wing_left_timer = 0.0
        self.wing_right_timer = 0.0
        self.WING_REGEN = 3.2

        self.flap = random.uniform(0, 6.28)
        self.flap_speed = random.uniform(10.0, 14.0)

        if stage in (3, 4) and self._load_garg_sprites(stage):
            pass
        else:
            self.body_img = self._build_body(stage)
            self.wing_up = self._build_wing(up=True, stage=stage)
            self.wing_down = self._build_wing(up=False, stage=stage)
        self.width = max(self.body_img.get_width() + self.wing_up.get_width(), 100)
        self.height = max(self.body_img.get_height(), self.wing_up.get_height(), 60)
        # Stage 4: slightly faster base roam
        if stage >= 4:
            self.vx *= 1.2
            self.vy *= 1.2


    def _load_garg_sprites(self, stage=3):
        """Load mechanical bat art — stage 3 grey, stage 4 violet/dark red."""
        base = asset_path("sprites")
        prefix = "garg4" if stage >= 4 else "garg3"
        try:
            self.body_img = pygame.image.load(os.path.join(base, f"{prefix}_body.png")).convert_alpha()
            self.wing_up = pygame.image.load(os.path.join(base, f"{prefix}_wing_up.png")).convert_alpha()
            self.wing_down = pygame.image.load(os.path.join(base, f"{prefix}_wing_down.png")).convert_alpha()
        except Exception:
            return False
        return True

    def _build_body(self, stage=3):
        w, h = 48, 58
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        if stage >= 4:
            # Toxic green / sickly yellow gargoyle
            stone = (40, 70, 35)
            stone_l = (70, 120, 55)
            stone_d = (20, 35, 18)
            blood = (180, 160, 20)
            bone = (200, 210, 120)
            eye_r = (255, 255, 40)
            eye_g = (180, 255, 60)
        else:
            # Stone / bone / blood palette
            stone = (55, 48, 58)
            stone_l = (90, 78, 88)
            stone_d = (28, 22, 30)
            blood = (140, 20, 30)
            bone = (180, 170, 160)
            eye_r = (255, 30, 30)
            eye_g = (255, 90, 40)
        cx, cy = w // 2, h // 2 + 2

        # Horns
        pygame.draw.polygon(surf, stone_d, [(cx - 10, cy - 20), (cx - 18, cy - 34), (cx - 6, cy - 18)])
        pygame.draw.polygon(surf, stone_d, [(cx + 10, cy - 20), (cx + 18, cy - 34), (cx + 6, cy - 18)])
        pygame.draw.polygon(surf, bone, [(cx - 10, cy - 20), (cx - 15, cy - 30), (cx - 7, cy - 18)])
        pygame.draw.polygon(surf, bone, [(cx + 10, cy - 20), (cx + 15, cy - 30), (cx + 7, cy - 18)])

        # Skull / head
        pygame.draw.ellipse(surf, stone, (cx - 14, cy - 20, 28, 26))
        pygame.draw.ellipse(surf, stone_l, (cx - 10, cy - 18, 20, 14))
        pygame.draw.ellipse(surf, stone_d, (cx - 12, cy - 8, 24, 16))

        # Hollow glowing eyes
        pygame.draw.ellipse(surf, (20, 0, 0), (cx - 11, cy - 14, 10, 8))
        pygame.draw.ellipse(surf, (20, 0, 0), (cx + 1, cy - 14, 10, 8))
        pygame.draw.circle(surf, eye_g, (cx - 6, cy - 10), 3)
        pygame.draw.circle(surf, eye_g, (cx + 6, cy - 10), 3)
        pygame.draw.circle(surf, eye_r, (cx - 6, cy - 10), 2)
        pygame.draw.circle(surf, eye_r, (cx + 6, cy - 10), 2)

        # Fanged maw
        pygame.draw.polygon(surf, blood, [
            (cx - 10, cy - 2), (cx + 10, cy - 2), (cx + 8, cy + 10), (cx - 8, cy + 10)
        ])
        pygame.draw.polygon(surf, (40, 5, 10), [
            (cx - 8, cy), (cx + 8, cy), (cx + 6, cy + 8), (cx - 6, cy + 8)
        ])
        # Teeth
        for tx in (-6, -2, 2, 6):
            pygame.draw.polygon(surf, bone, [
                (cx + tx - 2, cy), (cx + tx + 2, cy), (cx + tx, cy + 6)
            ])

        # Body torso
        pygame.draw.ellipse(surf, stone, (cx - 13, cy + 4, 26, 28))
        pygame.draw.ellipse(surf, stone_d, (cx - 10, cy + 10, 20, 20))
        # Rib lines
        for ry in (10, 16, 22):
            pygame.draw.arc(surf, stone_l, (cx - 10, cy + ry - 4, 20, 12), 0.3, 2.8, 1)

        # Clawed feet
        pygame.draw.polygon(surf, bone, [(cx - 8, cy + 28), (cx - 12, cy + 36), (cx - 4, cy + 30)])
        pygame.draw.polygon(surf, bone, [(cx + 8, cy + 28), (cx + 12, cy + 36), (cx + 4, cy + 30)])

        return surf

    def _build_wing(self, up=True, stage=3):
        """Single left wing (flip for right). Full alpha transparency."""
        w, h = 52, 40
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        if stage >= 4:
            membrane = (30, 70, 40, 220)
            membrane_l = (60, 120, 50, 200)
            bone = (180, 200, 100)
            claw = (220, 230, 140)
            edge = (100, 140, 30)
        else:
            membrane = (45, 30, 55, 220)
            membrane_l = (70, 45, 85, 200)
            bone = (160, 150, 145)
            claw = (200, 190, 180)
            edge = (100, 40, 60)

        if up:
            # Stretched upward membrane
            pygame.draw.polygon(surf, membrane, [
                (w - 2, h // 2 + 4), (4, 2), (2, 14), (8, 22), (18, h - 4), (w - 6, h // 2 + 10)
            ])
            pygame.draw.polygon(surf, membrane_l, [
                (w - 4, h // 2 + 2), (10, 6), (8, 14), (16, 18), (w - 8, h // 2 + 6)
            ])
            # Bone structure
            pygame.draw.line(surf, bone, (w - 4, h // 2 + 4), (6, 4), 2)
            pygame.draw.line(surf, bone, (w - 4, h // 2 + 4), (10, 20), 2)
            pygame.draw.line(surf, bone, (w - 4, h // 2 + 4), (20, h - 6), 2)
            # Claw tips
            for px, py in [(4, 2), (8, 20), (18, h - 4)]:
                pygame.draw.circle(surf, claw, (px, py), 3)
                pygame.draw.polygon(surf, edge, [(px, py - 4), (px - 3, py + 2), (px + 3, py + 2)])
        else:
            # Folded / down
            pygame.draw.polygon(surf, membrane, [
                (w - 2, h // 2 - 4), (6, h // 2 - 2), (2, h - 8), (14, h - 2), (w - 8, h // 2 + 8)
            ])
            pygame.draw.polygon(surf, membrane_l, [
                (w - 4, h // 2 - 2), (12, h // 2), (8, h - 10), (w - 10, h // 2 + 4)
            ])
            pygame.draw.line(surf, bone, (w - 4, h // 2), (8, h // 2), 2)
            pygame.draw.line(surf, bone, (w - 4, h // 2), (6, h - 6), 2)
            pygame.draw.line(surf, bone, (w - 4, h // 2), (16, h - 2), 2)
            for px, py in [(6, h // 2 - 2), (4, h - 6), (14, h - 2)]:
                pygame.draw.circle(surf, claw, (px, py), 3)

        return surf

    def update(self, dt, formation_offset_x=0.0, player_x=0.0):
        if not self.alive:
            return

        if self.dying:
            if int(getattr(self, "hit_flash_frames", 0) or 0) > 0:
                self.hit_flash_frames -= 1
                return
            self.death_timer += dt
            self.death_flash = (int(self.death_timer * 18) % 2) == 0
            if self.death_timer >= self.DEATH_DURATION:
                self.alive = False
                self.dying = False
            return

        self.time += dt
        self.flap += dt * self.flap_speed
        self.shoot_cooldown = max(0.0, self.shoot_cooldown - dt)

        if not self.wing_left:
            self.wing_left_timer += dt
            if self.wing_left_timer >= self.WING_REGEN:
                self.wing_left = True
                self.wing_left_timer = 0.0
        if not self.wing_right:
            self.wing_right_timer += dt
            if self.wing_right_timer >= self.WING_REGEN:
                self.wing_right = True
                self.wing_right_timer = 0.0

        if self.state == "diving":
            sm = getattr(self, 'speed_mult', 1.0)
            self.y += ENEMY_DIVE_SPEED * 0.95 * sm * dt
            lane = getattr(self, "dive_lane", self.dive_target_x)
            dx = lane - self.x
            self.x += dx * 0.5 * sm * dt
            self.x += math.sin(self.time * 4.0 + self.formation_index) * 30 * dt
            self.x = max(50, min(BASE_WIDTH - 50, self.x))
            # Sortie bas → réapparition fluide en haut (comme stage 1/2)
            if self.y > BASE_HEIGHT + 50:
                self.y = -60
                self.state = "roam"
                self.vx = random.choice([-1, 1]) * random.uniform(90, 150)
                self.vy = random.uniform(30, 80)  # descend un peu en entrant
                self.dir_timer = random.uniform(0.8, 1.6)
        else:
            self.dir_timer -= dt
            if self.dir_timer <= 0:
                self.dir_timer = random.uniform(0.45, 1.7)
                spd = (1.2 if self.stage >= 4 else 1.0) * getattr(self, 'speed_mult', 1.0)
                self.vx = random.uniform(-160, 160) * spd
                self.vy = random.uniform(-110, 110) * spd
                if abs(self.vx) < 50 * spd:
                    self.vx = 50 * spd * (1 if self.vx >= 0 else -1)
                if abs(self.vy) < 30 * spd:
                    self.vy = 30 * spd * (1 if random.random() < 0.5 else -1)

            self.x += self.vx * dt
            self.y += self.vy * dt

            margin_x, margin_y = 48, 36
            if self.x < margin_x:
                self.x = margin_x
                self.vx = abs(self.vx)
            elif self.x > BASE_WIDTH - margin_x:
                self.x = BASE_WIDTH - margin_x
                self.vx = -abs(self.vx)
            if self.y < margin_y + 40:
                self.y = margin_y + 40
                self.vy = abs(self.vy)
            elif self.y > BASE_HEIGHT - 160:
                self.y = BASE_HEIGHT - 160
                self.vy = -abs(self.vy)

    def start_dive(self, player_x):
        if self.state != "roam" or not self.alive or self.dying:
            return
        if not (self.wing_left and self.wing_right):
            return
        self.state = "diving"
        slot = (self.formation_index % 7) - 3
        jitter = slot * 42 + random.uniform(-30, 30)
        self.dive_lane = max(50, min(BASE_WIDTH - 50, player_x + jitter))
        self.dive_target_x = self.dive_lane

    def kill(self, flash=True):
        if not self.alive or self.dying:
            return
        self.dying = True
        self.death_timer = 0.0
        self.hit_flash_frames = 1 if flash else 0
        if not flash:
            self.alive = False
            self.dying = False

    def hit_wing(self, side):
        if side == "left" and self.wing_left:
            self.wing_left = False
            self.wing_left_timer = 0.0
            return True
        if side == "right" and self.wing_right:
            self.wing_right = False
            self.wing_right_timer = 0.0
            return True
        return False

    @property
    def diving(self):
        return self.state == "diving" and not self.dying

    def can_shoot(self):
        if not self.wing_left and not self.wing_right:
            return False
        return self.alive and not self.dying and self.shoot_cooldown <= 0.0

    def did_shoot(self):
        self.shoot_cooldown = 0.17

    def get_body_hitbox(self):
        """Torso hitbox — generous enough that shots can't slip past the silhouette."""
        if self.dying or not self.alive:
            return pygame.Rect(0, 0, 0, 0)
        bw = self.body_img.get_width()
        bh = self.body_img.get_height()
        return pygame.Rect(
            int(self.x - bw * 0.42),
            int(self.y - bh * 0.45),
            int(bw * 0.84),
            int(bh * 0.90),
        )

    def get_left_wing_hitbox(self):
        if not self.wing_left or self.dying or not self.alive:
            return pygame.Rect(0, 0, 0, 0)
        ww = self.wing_up.get_width()
        wh = self.wing_up.get_height()
        bw = self.body_img.get_width()
        # Overlap slightly into the body so no gap between wing and torso
        return pygame.Rect(
            int(self.x - bw // 2 - ww + 2),
            int(self.y - wh * 0.48),
            int(ww * 0.98),
            int(wh * 0.88),
        )

    def get_right_wing_hitbox(self):
        if not self.wing_right or self.dying or not self.alive:
            return pygame.Rect(0, 0, 0, 0)
        ww = self.wing_up.get_width()
        wh = self.wing_up.get_height()
        bw = self.body_img.get_width()
        return pygame.Rect(
            int(self.x + bw // 2 - ww * 0.05),
            int(self.y - wh * 0.48),
            int(ww * 0.98),
            int(wh * 0.88),
        )

    def get_hitbox(self):
        if self.dying or not self.alive:
            return pygame.Rect(0, 0, 0, 0)
        return pygame.Rect(int(self.x - self.width * 0.45), int(self.y - self.height * 0.4),
                           int(self.width * 0.9), int(self.height * 0.8))

    def draw(self, surface):
        if not self.alive:
            return

        wing_up = math.sin(self.flap) > 0
        wing_src = self.wing_up if wing_up else self.wing_down
        flap_y = -5 if wing_up else 5
        bw = self.body_img.get_width()
        bh = self.body_img.get_height()
        ww = wing_src.get_width()
        wh = wing_src.get_height()
        bx = int(self.x - bw // 2)
        by = int(self.y - bh // 2)
        # Attach wings just outside the body so destroying a wing
        # never looks like carving the torso
        wing_y = int(self.y - wh // 2 + flap_y)
        left_x = int(self.x - bw // 2 - ww + 6)
        right_x = int(self.x + bw // 2 - 6)

        if self.dying:
            if int(getattr(self, "hit_flash_frames", 0) or 0) > 0:
                body_w = getattr(self, "_white_body", None)
                if body_w is None:
                    self._white_body = body_w = _whiten_surf(self.body_img)
                wing_w = getattr(self, "_white_wing", None)
                if wing_w is None:
                    self._white_wing = wing_w = _whiten_surf(wing_src)
                if self.wing_left:
                    surface.blit(wing_w, (left_x, wing_y))
                if self.wing_right:
                    surface.blit(pygame.transform.flip(wing_w, True, False), (right_x, wing_y))
                surface.blit(body_w, (bx, by))
                return
            t = self.death_timer / self.DEATH_DURATION
            alpha = max(0, int(255 * (1.0 - t)))
            body = self.body_img.copy()
            body.set_alpha(alpha)
            surface.blit(body, (bx, by))
            return

        # Wings behind body
        if self.wing_left:
            surface.blit(wing_src, (left_x, wing_y))
        if self.wing_right:
            surface.blit(pygame.transform.flip(wing_src, True, False), (right_x, wing_y))

        surface.blit(self.body_img, (bx, by))

        # Tiny shoulder stubs when a wing is missing (reads as torn, not floating tips)
        if not self.wing_left or not self.wing_right:
            stub = getattr(self, "_wing_stub", None)
            if stub is None:
                stub = pygame.Surface((10, 12), pygame.SRCALPHA)
                pygame.draw.ellipse(stub, (90, 95, 105, 220), (0, 2, 9, 9))
                pygame.draw.polygon(stub, (130, 135, 145, 230), [(2, 4), (9, 1), (8, 10)])
                self._wing_stub = stub
            sy = int(self.y - 4)
            if not self.wing_left:
                surface.blit(stub, (int(self.x - bw // 2 - 4), sy))
            if not self.wing_right:
                surface.blit(pygame.transform.flip(stub, True, False),
                             (int(self.x + bw // 2 - 6), sy))
