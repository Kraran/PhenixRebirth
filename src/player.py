"""
Player ship: movement, single-shot (optional autofire), edge lightning /
kill timer, thruster animation, Phenix transform, and death sequences.

Input: keyboard (QWERTY + AZERTY ZQSD) and gamepad. Coop uses input_scheme
kb1 / kb2 / pad. Wall slowdown and tesla FX are cleared on life loss so
they never leak to the next life or the other hot-seat player.
"""
import pygame
import os
import math
import random
from settings import *

from settings import asset_path
SHIP_PATH = asset_path("sprites", "player_ship.png")
SHIP_SHIELD_PATH = asset_path("sprites", "player_ship_shield.png")

class Player:
    def __init__(self, x, y, ship_id="phoenix"):
        self.x = float(x)
        self.y = float(y)
        self.ship_id = "phoenix"
        self.image = pygame.image.load(SHIP_PATH).convert_alpha()
        self.width = self.image.get_width()
        self.height = self.image.get_height()
        self.speed = PLAYER_SPEED

        # Phenix form: flight loop + morph sequence (ship ↔ firebird)
        self.phenix_frames = []
        self.morph_frames = []  # 1→4 becoming Phenix
        self.phenix_anim_time = 0.0
        self.PHENIX_ANIM_FPS = 10.0
        self.morph_timer = 0.0
        self.morph_duration = 0.0
        self.morph_dir = 0  # +1 to phenix, -1 to ship, 0 idle
        self.MORPH_IN_SEC = 0.45
        self.MORPH_OUT_SEC = 0.40
        phenix_dir = asset_path("sprites", "phenix")
        if os.path.isdir(phenix_dir):
            for name in sorted(os.listdir(phenix_dir)):
                path = os.path.join(phenix_dir, name)
                try:
                    fr = pygame.image.load(path).convert_alpha()
                except Exception as e:
                    print("phenix asset skip:", name, e)
                    continue
                if name.startswith("phenix_") and name.endswith(".png"):
                    self.phenix_frames.append(fr)
                elif name.startswith("morph_") and name.endswith(".png"):
                    self.morph_frames.append(fr)

        # Active shots: list of {x, y, resolved, flame}
        # Normal: max 1. Phenix: max 2 (pair from rear wings), one volley on screen.
        self.shots = []
        
        # Phenix gauge (0–10). Each valid kill +1, each miss -1 (no combo required).
        self.phenix_gauge = 0
        self.combo_streak = 0  # kept for compatibility; no longer used for fill
        self.phenix_timer = 0.0  # remaining transform time (seconds)
        self.phenix_duration = 0.0  # total duration at activation
        self.phenix_start_level = 0  # gauge level spent at activation
        self.PHENIX_SPEED_MULT = 1.35
        self.PHENIX_END_INVULN = 0.45
        self.phenix_sec_per_point = 0.6  # duration per gauge level
        self.phenix_min_gauge = 0  # novice keeps at least 1
        self.phenix_auto_refill = False  # PHEN cheat
        self.PHENIX_REFILL_TIME = 3.0  # seconds 0→10
        self.phenix_cooldown = 0.0
        self.PHENIX_COOLDOWN_SEC = 1.25
        
        self.lives = PLAYER_MAX_LIVES
        self.infinite_lives = False
        self.use_shared_lives = False
        self.input_scheme = "solo"  # solo | kb1 | kb2 | pad
        self.palette = "red"  # red | blue
        self.pid = 0
        self.score = 0
        self.life_flags = [False, False]
        self.just_lost_life = False
        self._shoot_held = False
        self.autofire = True
        self._joy = None
        self._rumble_enabled = True
        self.invulnerable = 0.0
        self.alive = True
        
        self.rect = self.image.get_rect(center=(self.x, self.y))
        
        # Hitbox covers fuselage + wings (shots must not pass through wings)
        self.hitbox_w = max(28, int(self.width * 0.78))
        self.hitbox_h = max(32, int(self.height * 0.52))
        # Twin engines spacing (px from center each side)
        self.engine_offset = 8
        self.engine_offsets = (-8, 8)
        self.engine_ys = (0, 0)
        self.engine_width_scale = 1.0
        
        # Engine animation
        self.moving = False
        self.engine_time = 0.0
        self.engine_intensity = 0.0
        
        # Edge collision / lightning
        self.edge_contact = False
        self.edge_side = 0
        self.edge_timer = 0.0
        self.EDGE_KILL_TIME = 0.50
        self.edge_flash = 0.0
        self.last_edge_side = 0
        self.edge_death = False
        self.slowdown_timer = 0.0
        self.SLOWDOWN_DURATION = 1.7
        self.SLOWDOWN_FACTOR = 0.35
        
        # Death disappearance
        self.dying = False
        self.death_timer = 0.0
        self.DEATH_DURATION = 0.70
        self.death_flash = False
        self._white_image = None
        # Apply hull last so engine count / shield frames are not overwritten
        # by the defaults above (coop / hot-seat construct with ship_id).
        if ship_id and ship_id != "phoenix":
            self.set_ship(ship_id)

    def apply_blue_palette(self):
        """Dark-blue ship + icy Phenix / Shield (P2 coop / hot-seat)."""
        self.palette = "blue"
        def _tint(surf, rgb):
            if surf is None:
                return surf
            out = surf.copy()
            overlay = pygame.Surface(out.get_size(), pygame.SRCALPHA)
            overlay.fill((*rgb, 255))
            out.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            return out
        shield = getattr(self, "uses_shield", False)
        hull = (150, 200, 255) if shield else (70, 120, 255)
        ice = (210, 240, 255) if shield else (170, 220, 255)
        self.image = _tint(self.image, hull)
        self._white_image = None
        self.phenix_frames = [_tint(fr, ice) for fr in (self.phenix_frames or [])]
        self.morph_frames = [_tint(fr, ice) for fr in (self.morph_frames or [])]
        if getattr(self, "uses_shield", False):
            self.shield_on_frames = [_tint(fr, ice) for fr in (getattr(self, "shield_on_frames", None) or [])]
            self.shield_loop_frames = [_tint(fr, ice) for fr in (getattr(self, "shield_loop_frames", None) or [])]
            self.shield_off_frames = [_tint(fr, ice) for fr in (getattr(self, "shield_off_frames", None) or [])]
            self.morph_frames = list(self.shield_on_frames)
            self.phenix_frames = list(self.shield_loop_frames)
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def set_ship(self, ship_id):
        """Swap hull art. Combat rules (Phenix vs Shield) hook here later."""
        sid = "shield" if ship_id == "shield" else "phoenix"
        self.ship_id = sid
        self.palette = "red"
        path = SHIP_SHIELD_PATH if sid == "shield" else SHIP_PATH
        try:
            self.image = pygame.image.load(path).convert_alpha()
        except Exception as e:
            print("set_ship load failed:", e)
            return
        self.width = self.image.get_width()
        self.height = self.image.get_height()
        self._white_image = None
        self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))
        self._load_shield_frames()
        if sid == "shield":
            self.engine_offsets = (-12, 0, 12)
            self.engine_ys = (0, 6, 0)
            self.engine_width_scale = 0.58
            self.engine_offset = 12
            self.phenix_gauge = 10.0
            self.phenix_min_gauge = 0
            self.phenix_cooldown = 0.0
            self.SHIELD_DURATION = 2.0
            self.SHIELD_COOLDOWN = 5.0
            self.MORPH_IN_SEC = 0.22
            self.MORPH_OUT_SEC = 0.26
        else:
            self.engine_offsets = (-8, 8)
            self.engine_ys = (0, 0)
            self.engine_width_scale = 1.0
            self.engine_offset = 8

    @property
    def uses_shield(self):
        return getattr(self, "ship_id", "phoenix") == "shield"

    def _load_shield_frames(self):
        self.shield_on_frames = []
        self.shield_loop_frames = []
        self.shield_off_frames = []
        sdir = asset_path("sprites", "shield")
        if not os.path.isdir(sdir):
            return
        for name in sorted(os.listdir(sdir)):
            path = os.path.join(sdir, name)
            try:
                fr = pygame.image.load(path).convert_alpha()
            except Exception:
                continue
            if name.startswith("morph_"):
                self.shield_on_frames.append(fr)
            elif name.startswith("loop_"):
                self.shield_loop_frames.append(fr)
            elif name.startswith("off_"):
                self.shield_off_frames.append(fr)
        if self.uses_shield:
            self.morph_frames = list(self.shield_on_frames)
            self.phenix_frames = list(self.shield_loop_frames)

    def update(self, dt, keys, input_mode="keyboard", joystick=None, allow_shoot=True, ai_move=None, ai_shoot=None):
        if not self.alive:
            return False
        
        # Death animation — no control
        if self.dying:
            self.death_timer += dt
            self.death_flash = (int(self.death_timer * 18) % 2) == 0
            self.engine_intensity = max(0.0, self.engine_intensity - dt * 2.0)
            if self.death_timer >= self.DEATH_DURATION:
                self.alive = False
                self.dying = False
            return False
            
        if self.invulnerable > 0:
            self.invulnerable = max(0.0, self.invulnerable - dt)
        if getattr(self, "phenix_cooldown", 0) > 0:
            self.phenix_cooldown = max(0.0, self.phenix_cooldown - dt)
        if getattr(self, "_special_lock", 0) > 0:
            self._special_lock = max(0.0, self._special_lock - dt)

        # Morph ship ↔ Phenix (must advance every frame)
        if getattr(self, "morph_dir", 0) != 0:
            self.morph_timer += dt
            if self.morph_timer >= self.morph_duration:
                if self.morph_dir < 0:
                    # Morph-out done → normal ship
                    self.morph_dir = 0
                    self.morph_timer = 0.0
                    self.phenix_timer = 0.0
                    self.phenix_duration = 0.0
                    self.phenix_start_level = 0
                    if getattr(self, "phenix_saved_gauge", None) is not None:
                        self.phenix_gauge = max(
                            float(self.phenix_min_gauge),
                            min(10.0, float(self.phenix_saved_gauge)),
                        )
                        self.phenix_saved_gauge = None
                    else:
                        self.phenix_gauge = float(self.phenix_min_gauge)
                    if self.uses_shield:
                        self.phenix_cooldown = float(getattr(self, "SHIELD_COOLDOWN", 5.0))
                        self.phenix_gauge = 0.0
                    else:
                        self.phenix_cooldown = float(getattr(self, "PHENIX_COOLDOWN_SEC", 1.25))
                else:
                    # Morph-in done → full Phenix flight loop
                    self.morph_dir = 0
                    self.morph_timer = 0.0

        # Phenix / Shield form countdown — only while fully transformed (not during morph)
        if self.phenix_timer > 0 and getattr(self, "morph_dir", 0) == 0:
            self.phenix_timer = max(0.0, self.phenix_timer - dt)
            if not hasattr(self, "phenix_anim_time"):
                self.phenix_anim_time = 0.0
            self.phenix_anim_time += dt
            if self.phenix_duration > 0:
                self.phenix_gauge = self.phenix_start_level * (self.phenix_timer / self.phenix_duration)
            if self.phenix_timer <= 0:
                self.end_phenix(grant_invuln=True)
            elif not self.uses_shield:
                self._purr_cd = getattr(self, "_purr_cd", 0.0) - dt
                if self._purr_cd <= 0:
                    self._purr_cd = 0.32
                    self.rumble(0.16, 0.28, 300)
        elif self.uses_shield and getattr(self, "morph_dir", 0) == 0:
            cd = float(getattr(self, "phenix_cooldown", 0) or 0)
            total = float(getattr(self, "SHIELD_COOLDOWN", 5.0))
            if cd > 0:
                self.phenix_gauge = 10.0 * (1.0 - min(1.0, cd / max(0.05, total)))
            else:
                self.phenix_gauge = 10.0
        elif self.phenix_auto_refill and self.alive and not self.dying and getattr(self, "morph_dir", 0) == 0:
            rate = 10.0 / max(0.1, self.PHENIX_REFILL_TIME)
            if self.phenix_gauge < 10.0:
                self.phenix_gauge = min(10.0, self.phenix_gauge + rate * dt)
        
        dx = 0.0
        shoot_pressed = False

        self._joy = joystick
        self._rumble_enabled = ai_move is None
        # Attract-mode AI overrides human input when provided
        if ai_move is not None:
            # Same units as keyboard: -1 / 0 / +1 (speed applied later)
            dx = float(ai_move)
            shoot_pressed = bool(ai_shoot) if allow_shoot else False
            _ai = True
        else:
            _ai = False
        
        if not _ai and input_mode == "gamepad" and joystick is not None:
            try:
                axis = joystick.get_axis(0)
                if abs(axis) > 0.25:
                    dx = 1.0 if axis > 0 else -1.0
                # D-pad hat
                if joystick.get_numhats() > 0:
                    hat = joystick.get_hat(0)
                    if hat[0] < 0:
                        dx = -1.0
                    elif hat[0] > 0:
                        dx = 1.0
                # Face buttons: 0=A, 1=B, 2=X, 3=Y — also shoulder
                # B (1) reserved for Phenix activation (edge-triggered in Game)
                for b in (0, 2, 3, 5):
                    if joystick.get_numbuttons() > b and joystick.get_button(b):
                        shoot_pressed = True
                        break
            except Exception:
                pass
        elif not _ai:
            scheme = getattr(self, "input_scheme", "solo")
            if scheme == "kb1":
                # Coop P1 keyboard: Q+A / D, Left Ctrl shoot
                if keys[pygame.K_q] or keys[pygame.K_a]:
                    dx -= 1.0
                if keys[pygame.K_d]:
                    dx += 1.0
                shoot_pressed = keys[pygame.K_LCTRL]
            elif scheme == "kb2":
                # Coop P2 keyboard (same as 1P kb): arrows, Space / Right Ctrl
                if keys[pygame.K_LEFT]:
                    dx -= 1.0
                if keys[pygame.K_RIGHT]:
                    dx += 1.0
                shoot_pressed = keys[pygame.K_SPACE] or keys[pygame.K_RCTRL]
            else:
                # 1P / hot-seat keyboard: arrows, Space or Right Ctrl
                if keys[pygame.K_LEFT]:
                    dx -= 1.0
                if keys[pygame.K_RIGHT]:
                    dx += 1.0
                shoot_pressed = keys[pygame.K_SPACE] or keys[pygame.K_RCTRL]
        
        if self.uses_shield and self.is_phenix:
            dx = 0.0
        self.moving = dx != 0.0
        
        if self.slowdown_timer > 0:
            self.slowdown_timer = max(0.0, self.slowdown_timer - dt)
            speed_mult = self.SLOWDOWN_FACTOR
        else:
            speed_mult = 1.0
        if self.is_phenix and not self.uses_shield:
            speed_mult *= self.PHENIX_SPEED_MULT
            
        self.x += dx * self.speed * speed_mult * dt
        
        margin = 36
        left_limit = margin
        right_limit = BASE_WIDTH - margin
        
        self.edge_contact = False
        self.edge_side = 0
        
        if self.x <= left_limit:
            self.x = left_limit
            if dx < 0:
                self.edge_contact = True
                self.edge_side = -1
                self.last_edge_side = -1
        elif self.x >= right_limit:
            self.x = right_limit
            if dx > 0:
                self.edge_contact = True
                self.edge_side = 1
                self.last_edge_side = 1
        
        if self.edge_contact and self.invulnerable <= 0:
            # Any edge spark empties Phenix gauge (and ends form if active)
            if self.is_phenix and not self.uses_shield:
                self.end_phenix(grant_invuln=True)
                self.edge_timer = 0.0
                self.edge_flash = 0.35
                self.slowdown_timer = max(self.slowdown_timer, 0.5)
            elif self.is_phenix and self.uses_shield:
                self.edge_contact = False
                self.edge_timer = 0.0
            else:
                if self.phenix_gauge > self.phenix_min_gauge or self.combo_streak > 0:
                    self.phenix_gauge = float(self.phenix_min_gauge)
                    self.combo_streak = 0
                self.edge_timer += dt
                self.edge_flash = min(1.0, self.edge_timer / 0.25)
                self.edge_flash = 1.0
                if self.slowdown_timer <= 0:
                    self.slowdown_timer = self.SLOWDOWN_DURATION
                    self.rumble(0.38, 0.62, int(self.SLOWDOWN_DURATION * 1000))
                else:
                    self.slowdown_timer = max(self.slowdown_timer, 0.35)
        else:
            self.edge_timer = max(0.0, self.edge_timer - dt * 2.5)
            # Lightning lasts as long as the slowdown
            if self.slowdown_timer > 0:
                frac = self.slowdown_timer / max(0.05, self.SLOWDOWN_DURATION)
                self.edge_flash = max(0.28, min(1.0, frac))
            else:
                self.edge_flash = max(0.0, self.edge_flash - dt * 4.0)
        
        self.rect.center = (int(self.x), int(self.y))
        
        self.engine_time += dt
        target = 1.0 if self.moving else 0.25
        self.engine_intensity += (target - self.engine_intensity) * min(1.0, 8.0 * dt)
        if self.uses_shield and self.is_phenix:
            self.engine_intensity = 0.0
        
        # Update shots
        for shot in self.shots[:]:
            shot["prev_y"] = shot["y"]
            shot["y"] -= BULLET_SPEED * dt
            if shot["y"] < -30:
                if not shot.get("resolved"):
                    self.register_miss()
                self.shots.remove(shot)
        
        fire = bool(allow_shoot and shoot_pressed and not self.shots)
        if fire:
            if getattr(self, "autofire", True) or not getattr(self, "_shoot_held", False):
                self.shoot()
        self._shoot_held = bool(shoot_pressed)
        
        return self._check_edge_kill()

    def _check_edge_kill(self):
        if self.edge_timer >= self.EDGE_KILL_TIME and self.alive and not self.dying:
            if self.invulnerable <= 0 and not self.is_phenix:
                self.hit()
                self.edge_timer = 0.0
                self.slowdown_timer = 0.0
                self.last_edge_side = self.last_edge_side or self.edge_side or -1
                if self.dying:
                    # Tesla + ship arcs only for this edge-death animation
                    self.edge_death = True
                    self.edge_flash = 1.0
                else:
                    self.edge_death = False
                    self.edge_flash = 0.0
                return True  # damage applied
        return False

    def shoot(self):
        if self.dying or self.shots:
            return
        by = self.y - self.height // 2 - 4
        if self.is_phenix and not self.uses_shield:
            # Dual fire from rear wings
            wing = max(12, int(self.width * 0.28))
            self.shots = [
                {"x": self.x - wing, "y": by + 4, "resolved": False, "flame": True},
                {"x": self.x + wing, "y": by + 4, "resolved": False, "flame": True},
            ]
        else:
            self.shots = [
                {"x": self.x, "y": by, "resolved": False, "flame": False},
            ]
        if getattr(self, "sounds", None):
            self.sounds.play("shoot", volume=0.45, x=self.x)

    def rumble(self, low, high, duration_ms):
        """Gamepad vibration if a pad is present. Silent no-op otherwise.
        Intensity 0–5 (3 = default)."""
        if not getattr(self, "_rumble_enabled", True):
            return
        level = int(getattr(self, "rumble_level", 3) or 0)
        if level <= 0:
            return
        joy = getattr(self, "_joy", None)
        if joy is None:
            return
        scale = level / 3.0
        low = max(0.0, min(1.0, float(low) * scale))
        high = max(0.0, min(1.0, float(high) * scale))
        try:
            if hasattr(joy, "rumble"):
                joy.rumble(low, high, int(duration_ms))
        except Exception:
            pass

    def stop_rumble(self):
        joy = getattr(self, "_joy", None)
        if joy is None:
            return
        try:
            if hasattr(joy, "stop_rumble"):
                joy.stop_rumble()
        except Exception:
            pass

    def destroy_bullet(self, result=None, index=None):
        """Remove one shot (index) or all. result: 'valid' | 'neutral' | None."""
        if not self.shots:
            return
        if index is None:
            # Clear all (stage transition, etc.) — no miss penalty
            for s in self.shots:
                s["resolved"] = True
            self.shots.clear()
            return
        if index < 0 or index >= len(self.shots):
            return
        shot = self.shots[index]
        if result == "valid":
            self.register_valid_hit()
            shot["resolved"] = True
        elif result == "neutral":
            shot["resolved"] = True
        self.shots.pop(index)

    def _clamp_phenix_gauge(self):
        """Respect difficulty floor (novice: never below 1)."""
        self.phenix_gauge = max(float(self.phenix_min_gauge), float(self.phenix_gauge))
        if self.phenix_gauge > 10:
            self.phenix_gauge = 10.0

    def register_miss(self):
        """Shot left the screen with no valid/neutral contact — -1 gauge."""
        if self.is_phenix or self.uses_shield:
            return  # no gauge change during form
        self.combo_streak = 0
        self.phenix_gauge = max(float(self.phenix_min_gauge), float(self.phenix_gauge) - 1.0)

    @property
    def is_phenix(self):
        if not self.alive or self.dying:
            return False
        if getattr(self, "morph_dir", 0) != 0:
            return True
        return self.phenix_timer > 0

    def can_activate_phenix(self):
        if not self.alive or self.dying or self.is_phenix:
            return False
        if getattr(self, "phenix_cooldown", 0) > 0:
            return False
        if self.uses_shield:
            return True
        return self.phenix_gauge >= 3

    def try_activate_phenix(self):
        """Phenix: spend gauge. Shield: 2s bubble, then 5s cooldown."""
        if not self.can_activate_phenix():
            return False
        if self.uses_shield:
            self.phenix_start_level = 10
            self.phenix_duration = 2.0
            self.phenix_timer = 2.0
            self.SHIELD_DURATION = 2.0
            self.phenix_gauge = 10.0
            self.combo_streak = 0
            self.phenix_anim_time = 0.0
            self.morph_frames = list(getattr(self, "shield_on_frames", None) or [])
            self.phenix_frames = list(getattr(self, "shield_loop_frames", None) or [])
            self.morph_dir = 1 if self.morph_frames else 0
            self.morph_timer = 0.0
            self.morph_duration = 0.22 if self.morph_frames else 0.0
            self._special_lock = 0.40
            if getattr(self, "sounds", None):
                try:
                    self.sounds.play("phenix_activate", x=self.x)
                except Exception:
                    pass
            return True
        level = int(self.phenix_gauge)
        self.phenix_start_level = level
        self.phenix_duration = self.phenix_sec_per_point * level
        self.phenix_timer = self.phenix_duration
        # Keep gauge full at start; update() drains it toward 0
        self.phenix_gauge = float(level)
        self.combo_streak = 0
        self.phenix_anim_time = 0.0
        self.morph_dir = 1
        self.morph_timer = 0.0
        self.morph_duration = self.MORPH_IN_SEC if self.morph_frames else 0.0
        self._special_lock = 0.40
        if getattr(self, "sounds", None):
            self.sounds.play("phenix_activate", x=self.x)
        return True

    def end_phenix(self, grant_invuln=False, keep_gauge=False):
        """End Phenix form — reverse morph 4→1.

        keep_gauge=True: player cancelled early — conserve remaining gauge.
        """
        # Already morphing out
        if getattr(self, "morph_dir", 0) < 0:
            return

        was_active = (
            self.phenix_timer > 0 or self.phenix_duration > 0
            or getattr(self, "morph_dir", 0) > 0
        )
        if not was_active:
            return

        # Snapshot remaining gauge before clearing timers
        if keep_gauge:
            # Prefer live gauge (already tracks remaining time); fallback to timer ratio
            remaining = float(self.phenix_gauge)
            if remaining <= 0 and self.phenix_duration > 0 and self.phenix_timer > 0:
                remaining = self.phenix_start_level * (self.phenix_timer / self.phenix_duration)
            self.phenix_saved_gauge = max(
                float(self.phenix_min_gauge), min(10.0, remaining)
            )
        else:
            self.phenix_saved_gauge = None

        if self.uses_shield and getattr(self, "shield_off_frames", None):
            self.morph_frames = list(self.shield_off_frames)
        if getattr(self, "morph_frames", None):
            self.morph_dir = -1
            self.morph_timer = 0.0
            self.morph_duration = 0.26 if self.uses_shield else self.MORPH_OUT_SEC
            self.phenix_timer = 0.0
            if getattr(self, "sounds", None):
                self.sounds.play("phenix_end", x=self.x)
            if grant_invuln and self.alive and not self.dying:
                self.invulnerable = max(self.invulnerable, self.PHENIX_END_INVULN)
            return

        # No morph frames — instant end
        self.morph_dir = 0
        self.morph_timer = 0.0
        self.phenix_timer = 0.0
        self.phenix_duration = 0.0
        self.phenix_start_level = 0
        if self.phenix_saved_gauge is not None:
            self.phenix_gauge = self.phenix_saved_gauge
            self.phenix_saved_gauge = None
        else:
            self.phenix_gauge = float(self.phenix_min_gauge)
        if self.uses_shield:
            self.phenix_cooldown = float(getattr(self, "SHIELD_COOLDOWN", 5.0))
            self.phenix_gauge = 0.0
        else:
            self.phenix_cooldown = float(getattr(self, "PHENIX_COOLDOWN_SEC", 1.25))
        if getattr(self, "sounds", None):
            self.sounds.play("phenix_end", x=self.x)
        if grant_invuln and self.alive and not self.dying:
            self.invulnerable = max(self.invulnerable, self.PHENIX_END_INVULN)

    def cancel_phenix(self):
        """Manual early exit (B again) — keep remaining gauge."""
        if not self.is_phenix:
            return False
        if getattr(self, "_special_lock", 0) > 0:
            return False  # same key hold / key-repeat must not cut the form
        if getattr(self, "morph_dir", 0) < 0:
            return False  # already exiting
        self.end_phenix(grant_invuln=True, keep_gauge=True)
        return True


    def register_valid_hit(self):
        """Body/core kill — +1 gauge (capped at 10). No combo required."""
        if self.is_phenix or self.uses_shield:
            return  # no refill during form
        before = float(self.phenix_gauge)
        self.phenix_gauge = min(10.0, before + 1.0)
        self.combo_streak = 0
        if before < 10.0 and self.phenix_gauge >= 10.0 and not self.uses_shield:
            self.flag_gauge_max = True

    def hit(self):
        """Apply damage. Returns True if this hit started the death sequence."""
        # Phenix: immune to normal hits (bullets / dives). Hull/edge handled separately.
        if self.is_phenix:
            return False
        if self.invulnerable > 0 or not self.alive or self.dying:
            return False
        # Never carry wall slowdown / lightning into the next life
        self.clear_wall_status()
            
        if not self.infinite_lives:
            if not self.use_shared_lives:
                self.lives -= 1
            self.just_lost_life = True
        self.invulnerable = PLAYER_INVULN_TIME
        # Any life loss clears Phenix gauge / combo (novice keeps floor)
        self.phenix_gauge = float(self.phenix_min_gauge)
        self.combo_streak = 0
        self.phenix_timer = 0.0
        
        if self.lives <= 0 and not getattr(self, 'infinite_lives', False):
            self.lives = 0
            self.dying = True
            self.death_timer = 0.0
            self.invulnerable = 0.0
            self.rumble(1.0, 1.0, 640)
            return True
        self.rumble(0.85, 1.0, 360)
        return False

    def clear_wall_status(self):
        """Drop leftover edge lightning / slowdown so it cannot leak to next life or hot-seat swap."""
        self.slowdown_timer = 0.0
        self.edge_timer = 0.0
        self.edge_flash = 0.0
        self.edge_contact = False
        self.edge_death = False
        self.edge_side = 0

    def _get_white_image(self):
        if self._white_image is None:
            white = self.image.copy()
            white.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGB_MAX)
            self._white_image = white
        return self._white_image

    def _draw_engine_flame(self, surface, cx, cy, intensity):
        if intensity < 0.05:
            return
        
        phenix = self.is_phenix
        # Boost size when transformed
        if phenix:
            intensity = max(intensity, 0.85) * 1.55
        
        flicker = 0.85 + 0.15 * math.sin(self.engine_time * 28.0 + cx * 0.1)
        length = intensity * flicker * (18.0 + 4.0 * math.sin(self.engine_time * 19.0 + cx))
        width = (5 + intensity * 3) * float(getattr(self, "engine_width_scale", 1.0))
        if phenix:
            length *= 1.35
            width *= 1.45
        
        for i in range(3, 0, -1):
            h = length * (0.5 + 0.5 * (i / 3.0))
            w = width * (1.4 - 0.2 * i)
            if phenix:
                if getattr(self, "palette", "red") == "blue":
                    color = (
                        (80, 180, 255),
                        (140, 220, 255),
                        (200, 245, 255),
                    )[min(2, 3 - i)]
                else:
                    color = (
                        (160, 20, 5),
                        (220, 50, 10),
                        (255, 110, 25),
                    )[min(2, 3 - i)]
            else:
                if getattr(self, "palette", "red") == "blue":
                    color = (20, 60 + i * 20, 200)
                else:
                    color = (40, 160 + i * 30, 255)
            points = [
                (cx - w, cy),
                (cx + w, cy),
                (cx + w * 0.3, cy + h),
                (cx - w * 0.3, cy + h),
            ]
            pygame.draw.polygon(surface, color, points)
        
        core_h = length * 0.7
        core_w = width * 0.45
        if phenix:
            if getattr(self, "palette", "red") == "blue":
                pygame.draw.polygon(surface, (210, 245, 255), [
                    (cx - core_w, cy),
                    (cx + core_w, cy),
                    (cx + core_w * 0.2, cy + core_h),
                    (cx - core_w * 0.2, cy + core_h),
                ])
                pygame.draw.circle(surface, (255, 255, 255), (int(cx), int(cy + core_h * 0.85)), 3)
            else:
                pygame.draw.polygon(surface, (255, 200, 60), [
                    (cx - core_w, cy),
                    (cx + core_w, cy),
                    (cx + core_w * 0.2, cy + core_h),
                    (cx - core_w * 0.2, cy + core_h),
                ])
                pygame.draw.circle(surface, (255, 245, 180), (int(cx), int(cy + core_h * 0.85)), 3)
        else:
            pygame.draw.polygon(surface, (180, 255, 255), [
                (cx - core_w, cy),
                (cx + core_w, cy),
                (cx + core_w * 0.2, cy + core_h),
                (cx - core_w * 0.2, cy + core_h),
            ])
            pygame.draw.circle(surface, (220, 255, 255), (int(cx), int(cy + core_h * 0.85)), 2)

    def _draw_edge_lightning(self, surface):
        if self.edge_flash < 0.05 and not (self.dying and self.edge_death):
            return
        if self.dying and not self.edge_death:
            return
        
        intensity = max(self.edge_flash, 0.85 if (self.dying and self.edge_death) else 0.0)
        side = self.edge_side or self.last_edge_side
        cx, cy = self.x, self.y
        num_arcs = 3 + int(intensity * 5)
        
        for i in range(num_arcs):
            angle = random.uniform(0, math.pi * 2)
            dist = random.uniform(18, 38 + intensity * 20)
            x1 = cx + math.cos(angle) * 12
            y1 = cy + math.sin(angle) * 10
            x2 = cx + math.cos(angle) * dist
            y2 = cy + math.sin(angle) * dist * 0.7
            
            points = [(x1, y1)]
            steps = random.randint(3, 5)
            for s in range(1, steps):
                t = s / steps
                mx = x1 + (x2 - x1) * t + random.uniform(-8, 8)
                my = y1 + (y2 - y1) * t + random.uniform(-6, 6)
                points.append((mx, my))
            points.append((x2, y2))
            
            if random.random() > intensity * 0.7:
                continue
            
            color = (200, 230, 255) if random.random() < 0.4 else (80, 160, 255)
            width = 2 if color[0] > 150 else 1
            pygame.draw.lines(surface, color, False, points, width)
        
        if random.random() < intensity * 0.35:
            r = int(22 + intensity * 18 + random.uniform(-4, 4))
            pygame.draw.circle(surface, (120, 190, 255), (int(cx), int(cy)), r, 1)
        
        if side != 0:
            wall_x = 8 if side < 0 else BASE_WIDTH - 8
            for _ in range(2):
                y_off = random.uniform(-25, 25)
                points = [
                    (cx + side * 15, cy + y_off * 0.3),
                    (cx + side * 25 + random.uniform(-5, 5), cy + y_off * 0.6),
                    (wall_x, cy + y_off + random.uniform(-8, 8)),
                ]
                pygame.draw.lines(surface, (150, 210, 255), False, points, 1)

    def draw(self, surface):
        if not self.alive:
            return
        
        # Death disappearance
        if self.dying:
            t = self.death_timer / self.DEATH_DURATION
            alpha = max(0, int(255 * (1.0 - t)))
            scale = 1.0 + 0.45 * t
            
            img = self._get_white_image() if (self.death_flash and t < 0.55) else self.image
            w = max(1, int(self.width * scale))
            h = max(1, int(self.height * scale))
            scaled = pygame.transform.smoothscale(img, (w, h))
            scaled.set_alpha(alpha)
            surface.blit(scaled, (int(self.x - w // 2), int(self.y - h // 2)))
            
            # Dying engine sputter
            if t < 0.5:
                ship_bottom = self.y + h // 2 - 4
                offs = getattr(self, "engine_offsets", (-8, 8))
                yos = getattr(self, "engine_ys", (0,) * len(offs))
                for i, off in enumerate(offs):
                    self._draw_engine_flame(
                        surface, self.x + off, ship_bottom + yos[i] if i < len(yos) else ship_bottom,
                        0.6 * (1.0 - t),
                    )
            if self.edge_death:
                self._draw_edge_lightning(surface)
            return
        
        # Blink when invulnerable
        if self.invulnerable > 0 and int(self.invulnerable * 12) % 2 == 0:
            return
        
        morph_frames = getattr(self, "morph_frames", None) or []
        morph_dir = getattr(self, "morph_dir", 0)
        if morph_dir != 0 and morph_frames:
            n = len(morph_frames)
            prog = 0.0 if self.morph_duration <= 0 else min(1.0, self.morph_timer / self.morph_duration)
            if morph_dir > 0:
                # 1→4 (indices 0..n-1)
                idx = int(prog * (n - 1) + 1e-6)
            else:
                # 4→1
                idx = int((1.0 - prog) * (n - 1) + 1e-6)
            idx = max(0, min(n - 1, idx))
            img = morph_frames[idx]
            iw, ih = img.get_width(), img.get_height()
            surface.blit(img, (int(self.x - iw // 2), int(self.y - ih // 2)))
            ship_bottom = self.y + ih // 2 - 6
        elif self.is_phenix and getattr(self, "phenix_frames", None):
            n = len(self.phenix_frames)
            idx = int(self.phenix_anim_time * self.PHENIX_ANIM_FPS) % n
            img = self.phenix_frames[idx]
            iw, ih = img.get_width(), img.get_height()
            surface.blit(img, (int(self.x - iw // 2), int(self.y - ih // 2)))
            ship_bottom = self.y + ih // 2 - 6
        else:
            draw_x = int(self.x - self.width // 2)
            draw_y = int(self.y - self.height // 2)
            surface.blit(self.image, (draw_x, draw_y))
            ship_bottom = self.y + self.height // 2 - 2

        if not (self.uses_shield and self.is_phenix):
            offs = getattr(self, "engine_offsets", (-8, 8))
            yos = getattr(self, "engine_ys", (0,) * len(offs))
            for i, off in enumerate(offs):
                self._draw_engine_flame(
                    surface, self.x + off,
                    ship_bottom + (yos[i] if i < len(yos) else 0),
                    self.engine_intensity,
                )
        
        self._draw_edge_lightning(surface)
        
        for shot in self.shots:
            bx, by = int(shot["x"]), int(shot["y"])
            if shot.get("flame"):
                # Orange-red flame bolt, bright yellow-orange core
                pygame.draw.rect(surface, (180, 40, 10), (bx - 5, by, 10, 15))
                pygame.draw.rect(surface, (255, 100, 20), (bx - 4, by, 8, 14))
                pygame.draw.rect(surface, (255, 180, 50), (bx - 2, by, 4, 13))
                pygame.draw.rect(surface, (255, 240, 160), (bx - 1, by, 2, 10))
                pygame.draw.circle(surface, (255, 220, 120), (bx, by), 3)
            else:
                if getattr(self, "palette", "red") == "blue":
                    # P2: cyan shifted toward violet
                    pygame.draw.rect(surface, (170, 120, 255), (bx - 3, by, 6, 16))
                    pygame.draw.rect(surface, (230, 210, 255), (bx - 1, by, 2, 16))
                else:
                    pygame.draw.rect(surface, (140, 255, 255), (bx - 3, by, 6, 16))
                    pygame.draw.rect(surface, (255, 255, 255), (bx - 1, by, 2, 16))

    def get_bullet_rects(self):
        """List of (index, rect) for active shots."""
        if self.dying:
            return []
        out = []
        for i, shot in enumerate(self.shots):
            bx, by = shot["x"], shot["y"]
            prev = shot.get("prev_y", by)
            top = min(float(prev), float(by))
            h = max(16.0, abs(float(prev) - float(by)) + 16.0)
            pad = 5 if shot.get("flame") else 4
            out.append((i, pygame.Rect(int(bx) - pad, int(top), pad * 2, int(h))))
        return out

    def get_bullet_rect(self):
        """Primary shot rect (compat)."""
        rects = self.get_bullet_rects()
        return rects[0][1] if rects else None

    @property
    def bullet(self):
        """Compat: truthy if any shot on screen (attract AI, etc.)."""
        return self.shots[0] if self.shots else None

    def get_hitbox(self):
        if self.dying or not self.alive:
            return pygame.Rect(0, 0, 0, 0)
        return pygame.Rect(
            self.x - self.hitbox_w // 2,
            self.y - self.hitbox_h // 2,
            self.hitbox_w,
            self.hitbox_h
        )
