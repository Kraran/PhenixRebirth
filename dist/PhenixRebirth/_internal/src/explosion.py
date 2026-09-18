"""
Particle explosions for combat feedback.

Kinds: bullet hit, enemy death, collision, edge death, game-over blast.
Object lifetime is short; Game caps concurrent instances for performance.
"""
import pygame
import math
import random

class Explosion:
    """
    kind:
      - "enemy"      : enemy death
      - "bullet"     : player hit by bullet (hull tear)
      - "collision"  : player rammed by diving enemy
      - "edge"       : killed by screen edge
      - "gameover"   : final death — maximum spectacle
    """
    def __init__(self, x, y, kind="enemy"):
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.particles = []
        self.debris = []
        self.flashes = []
        self.rings = []
        self.sparks = []
        
        if kind == "enemy":
            self.life = 0.55
            self.max_life = 0.55
            self._spawn_particles(22, 70, 260, [
                (255, 200, 80), (255, 120, 40), (255, 80, 180), (200, 60, 255), (255, 255, 200)
            ])
            self._spawn_flash(14, (255, 220, 150))
            self._spawn_ring(16, (255, 160, 60))
            
        elif kind == "bullet":
            self.life = 1.10
            self.max_life = 1.10
            self._spawn_hull_tear(heavy=False)
            self._spawn_particles(42, 90, 340, [
                (255, 220, 100), (255, 160, 50), (255, 90, 40),
                (200, 200, 220), (160, 180, 200), (255, 255, 200)
            ])
            self._spawn_sparks(18, (255, 200, 80))
            self._spawn_flash(28, (255, 240, 200))
            self._spawn_flash(16, (255, 160, 60))
            self._spawn_ring(30, (255, 180, 80))
            self._spawn_ring(18, (255, 220, 150))
            
        elif kind == "collision":
            self.life = 1.50
            self.max_life = 1.50
            self._spawn_hull_tear(heavy=True)
            self._spawn_particles(80, 140, 520, [
                (255, 240, 120), (255, 180, 60), (255, 100, 30),
                (255, 60, 20), (200, 220, 255), (255, 255, 255),
                (180, 100, 255), (100, 200, 255)
            ])
            self._spawn_sparks(35, (255, 220, 100))
            self._spawn_flash(48, (255, 250, 220))
            self._spawn_flash(30, (120, 180, 255))
            self._spawn_flash(18, (255, 100, 40))
            self._spawn_ring(55, (255, 200, 80))
            self._spawn_ring(38, (100, 180, 255))
            self._spawn_ring(22, (255, 255, 200))
            
        elif kind == "edge":
            self.life = 1.20
            self.max_life = 1.20
            self._spawn_hull_tear(heavy=False)
            self._spawn_particles(48, 100, 380, [
                (100, 180, 255), (150, 210, 255), (80, 140, 255),
                (200, 230, 255), (255, 255, 255), (180, 220, 255)
            ])
            self._spawn_particles(16, 50, 180, [
                (255, 220, 100), (255, 160, 50), (200, 200, 220)
            ])
            self._spawn_sparks(22, (150, 210, 255))
            self._spawn_flash(32, (160, 210, 255))
            self._spawn_flash(18, (255, 255, 255))
            self._spawn_ring(36, (100, 170, 255))
            self._spawn_ring(24, (200, 230, 255))
            
        else:  # gameover — spectacular
            self.life = 2.10
            self.max_life = 2.10
            self._spawn_hull_tear(heavy=True)
            self._spawn_hull_tear(heavy=True)  # double debris
            self._spawn_particles(120, 160, 620, [
                (255, 250, 180), (255, 200, 80), (255, 120, 40),
                (255, 60, 20), (255, 255, 255), (180, 220, 255),
                (120, 160, 255), (255, 100, 200), (200, 100, 255)
            ])
            self._spawn_sparks(55, (255, 240, 150))
            self._spawn_sparks(25, (150, 200, 255))
            self._spawn_flash(70, (255, 255, 240))
            self._spawn_flash(45, (255, 180, 80))
            self._spawn_flash(28, (120, 180, 255))
            self._spawn_ring(70, (255, 220, 100))
            self._spawn_ring(50, (255, 140, 50))
            self._spawn_ring(35, (150, 200, 255))
            self._spawn_ring(20, (255, 255, 255))

    def _spawn_particles(self, count, min_spd, max_spd, colors):
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(min_spd, max_spd)
            self.particles.append({
                "x": random.uniform(-10, 10),
                "y": random.uniform(-10, 10),
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "size": random.uniform(2.5, 8.0),
                "color": random.choice(colors),
                "drag": random.uniform(0.93, 0.98),
            })

    def _spawn_sparks(self, count, color):
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(180, 480)
            self.sparks.append({
                "x": 0.0,
                "y": 0.0,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": random.uniform(0.15, 0.45),
                "max_life": 0.45,
                "color": color,
            })

    def _spawn_hull_tear(self, heavy=False):
        count = 18 if heavy else 10
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(70, 280 if heavy else 190)
            w = random.uniform(5, 14)
            h = random.uniform(2.5, 8)
            self.debris.append({
                "x": random.uniform(-10, 10),
                "y": random.uniform(-10, 10),
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed - random.uniform(30, 100),
                "w": w,
                "h": h,
                "rot": random.uniform(0, 360),
                "rot_spd": random.uniform(-520, 520),
                "color": random.choice([
                    (200, 200, 210), (180, 185, 195), (160, 165, 175),
                    (220, 220, 230), (140, 150, 160), (100, 110, 120)
                ]),
            })

    def _spawn_flash(self, radius, color):
        self.flashes.append({
            "r": radius,
            "color": color,
            "life": 1.0,
        })

    def _spawn_ring(self, radius, color):
        self.rings.append({
            "r": float(radius),
            "max_r": radius * 4.2,
            "color": color,
            "width": 3 if radius < 40 else 4,
        })

    def update(self, dt):
        self.life -= dt
        
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 140 * dt
            p["vx"] *= p["drag"]
            p["vy"] *= p["drag"]
        
        for d in self.debris:
            d["x"] += d["vx"] * dt
            d["y"] += d["vy"] * dt
            d["vy"] += 300 * dt
            d["vx"] *= 0.975
            d["rot"] += d["rot_spd"] * dt
        
        for s in self.sparks:
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["vx"] *= 0.94
            s["vy"] *= 0.94
            s["life"] -= dt
        
        for f in self.flashes:
            f["life"] -= dt * 2.8
        
        for r in self.rings:
            r["r"] += (r["max_r"] - r["r"]) * min(1.0, 3.2 * dt)

    def is_finished(self):
        return self.life <= 0

    def draw(self, surface):
        if self.life <= 0:
            return
        
        alpha = max(0.0, self.life / self.max_life)
        
        for r in self.rings:
            if r["r"] >= r["max_r"] * 0.96:
                continue
            ring_alpha = alpha * (1.0 - r["r"] / r["max_r"])
            c = r["color"]
            col = (int(c[0] * ring_alpha), int(c[1] * ring_alpha), int(c[2] * ring_alpha))
            if col[0] + col[1] + col[2] > 25:
                pygame.draw.circle(surface, col, (int(self.x), int(self.y)), int(r["r"]), max(1, r["width"]))
        
        for f in self.flashes:
            if f["life"] <= 0:
                continue
            fa = max(0.0, min(1.0, f["life"]))
            c = f["color"]
            rad = int(f["r"] * (0.5 + 0.5 * fa))
            col = (int(c[0] * fa), int(c[1] * fa), int(c[2] * fa))
            pygame.draw.circle(surface, col, (int(self.x), int(self.y)), rad)
        
        for p in self.particles:
            size = p["size"] * alpha
            if size < 0.6:
                continue
            px = int(self.x + p["x"])
            py = int(self.y + p["y"])
            c = p["color"]
            col = (int(c[0] * alpha), int(c[1] * alpha), int(c[2] * alpha))
            r = max(1, int(size))
            if r <= 2:
                surface.fill(col, (px - r, py - r, r * 2, r * 2))
            else:
                pygame.draw.circle(surface, col, (px, py), r)
        
        for s in self.sparks:
            if s["life"] <= 0:
                continue
            sa = max(0.0, s["life"] / s["max_life"])
            c = s["color"]
            col = (int(c[0] * sa), int(c[1] * sa), int(c[2] * sa))
            x1, y1 = int(self.x + s["x"]), int(self.y + s["y"])
            x2 = int(self.x + s["x"] - s["vx"] * 0.02)
            y2 = int(self.y + s["y"] - s["vy"] * 0.02)
            pygame.draw.line(surface, col, (x1, y1), (x2, y2), 2)
        
        for d in self.debris:
            if alpha < 0.06:
                continue
            px = self.x + d["x"]
            py = self.y + d["y"]
            c = d["color"]
            col = (int(c[0] * alpha), int(c[1] * alpha), int(c[2] * alpha))
            hw, hh = d["w"] / 2, d["h"] / 2
            rad = math.radians(d["rot"])
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            points = []
            for cx, cy in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]:
                rx = cx * cos_a - cy * sin_a
                ry = cx * sin_a + cy * cos_a
                points.append((px + rx, py + ry))
            pygame.draw.polygon(surface, col, points)


class TeslaCoilFx:
    """Lightning climbing a screen edge after an edge-kill (Tesla coil look)."""

    def __init__(self, side, origin_y):
        from settings import BASE_WIDTH, BASE_HEIGHT
        self.side = -1 if side < 0 else 1
        self.origin_y = float(origin_y)
        self.t = 0.0
        self.duration = 1.85
        self.w = BASE_WIDTH
        self.h = BASE_HEIGHT
        self.x = 7 if self.side < 0 else BASE_WIDTH - 7
        self._glow = None

    def update(self, dt):
        self.t += dt

    def is_finished(self):
        return self.t >= self.duration

    def _bolt(self, y0, y1, fork=True):
        pts = []
        n = max(5, int(abs(y1 - y0) / 28))
        for i in range(n + 1):
            tt = i / max(1, n)
            y = y0 + (y1 - y0) * tt
            jag = random.uniform(-7, 7) + math.sin(tt * 9 + self.t * 18) * 3
            pts.append((self.x + jag, y))
        return pts

    def draw(self, surface):
        if self.is_finished():
            return
        life = 1.0 - self.t / self.duration
        climb = min(1.0, self.t / 0.72)
        top = self.h * (1.0 - climb) - 20
        top = max(-10, top)
        fade = life * life

        # Glow column (reuse surface — no alloc each frame)
        glow_w = int(18 + 22 * fade)
        gw, gh = glow_w * 2, self.h
        glow = self._glow
        if glow is None or glow.get_size()[1] != gh or glow.get_width() < gw:
            glow = pygame.Surface((max(gw, 80), gh), pygame.SRCALPHA)
            self._glow = glow
        glow.fill((0, 0, 0, 0))
        col_a = int(70 * fade)
        pygame.draw.rect(glow, (80, 170, 255, col_a), (glow_w - 6, int(top), 12, int(self.h - top + 8)))
        pygame.draw.rect(glow, (180, 230, 255, int(40 * fade)), (glow_w - 3, int(top), 6, int(self.h - top + 8)))
        surface.blit(glow, (self.x - glow_w, 0), special_flags=pygame.BLEND_ADD)

        # Main rising bolt + satellites
        bolts = 4 if climb < 1 else 3
        for b in range(bolts):
            y0 = self.h + 8
            y1 = top + random.uniform(-12, 18)
            pts = self._bolt(y0, y1)
            if len(pts) < 2:
                continue
            core = (220, 245, 255) if b == 0 else (90, 170, 255)
            pygame.draw.lines(surface, core, False, pts, 3 if b == 0 else 1)
            if b == 0:
                pygame.draw.lines(surface, (255, 255, 255), False, pts, 1)
            # Side forks near the climbing tip
            if random.random() < 0.55:
                mid = pts[len(pts) // 2]
                fx = mid[0] + self.side * random.uniform(12, 42)
                fy = mid[1] + random.uniform(-18, 8)
                pygame.draw.line(surface, (160, 210, 255), mid, (fx, fy), 1)

        # Bright tip spark climbing
        tip_y = top
        pygame.draw.circle(surface, (255, 255, 255), (int(self.x), int(tip_y)), int(5 + 4 * fade))
        pygame.draw.circle(surface, (140, 200, 255), (int(self.x), int(tip_y)), int(10 + 6 * fade), 1)

        # Residual crackles at ship height
        for _ in range(3):
            y = self.origin_y + random.uniform(-30, 30)
            x2 = self.x + self.side * random.uniform(8, 36)
            pygame.draw.line(
                surface, (180, 230, 255),
                (self.x + random.uniform(-4, 4), y),
                (x2, y + random.uniform(-16, 16)), 1,
            )
