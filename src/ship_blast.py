"""The big explosion of the ship of the player in the SpaceWar level (src/spacewar.py): the hull breaks into glowing shards
that fly apart and turn, a flash and a fireball swell round it, two shock rings run out, sparks streak away, embers drift
and smoke rises. It has the interface of ship_burn.ShipBurn (update, finished, draw) so that Player can hold either.

Everything is drawn live from a few dozen particles (no pre-made frames): the shards are cut from the picture of the hull
that the player was flying (the same layers as ship_burn), in its own turn and size.
"""
import math
import random

import pygame

import asteroids
from ship_burn import _source

DURATION = 2.4
SHARDS = 14
SPARKS = 48
EMBERS = 28
PUFFS = 12
RINGS = ((0.0, 250.0), (0.14, 170.0))                 # (delay s, final radius px) of the shock rings
RING_TIME = 0.75
FLASH_TIME = 0.22
SCALE_UP = 1.5                                        # the shards are this much bigger than the (half sized) ship
EFFECT_SIZE = 2.2                                     # the size of the lights, rings and sparks (the blast is big)
SHARD_DRAG = 1.4


def _lerp(a, b, k):
    return a + (b - a) * k


def _mix(c1, c2, k):
    return tuple(int(_lerp(c1[i], c2[i], k)) for i in range(3))


def _scaled(color, k):
    """`color` at the brightness k (0..1), quantised so that the glow pictures made for it are few."""
    k = max(0.0, min(1.0, k))
    k = round(k * 10) / 10.0
    return (int(color[0] * k), int(color[1] * k), int(color[2] * k))


class _Shard:
    def __init__(self, imgs, x, y, vx, vy, spin, angle):
        self.imgs = imgs                                # (as it was, red hot, charred)
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.spin, self.angle = spin, angle


class ShipBlast:
    def __init__(self, ship, angle=None, scale=1.0, rng=None):
        self.rng = rng if rng is not None else random.Random()
        self.x, self.y = float(ship.x), float(ship.y)
        self.vx = float(getattr(ship, "ast_vx", 0.0) or 0.0) * 0.4          # (the wreck keeps some of the speed)
        self.vy = float(getattr(ship, "ast_vy", 0.0) or 0.0) * 0.4
        self.size = EFFECT_SIZE
        self.shard_k = SCALE_UP
        self.age = 0.0
        img = _source(ship, ship.is_phenix)
        if angle is not None or scale != 1.0:
            img = pygame.transform.rotozoom(img, angle or 0.0, scale)
        self.shards = self._cut(img)
        rng = self.rng
        self.sparks = []
        for _ in range(SPARKS):
            a = rng.uniform(0, math.tau)
            sp = rng.uniform(110.0, 520.0) * self.size ** 0.5
            self.sparks.append([math.cos(a), math.sin(a), sp, rng.uniform(0.45, 1.3), rng.choice((1, 2, 2))])
        self.embers = []
        for _ in range(EMBERS):
            a = rng.uniform(0, math.tau)
            sp = rng.uniform(15.0, 150.0) * self.size ** 0.5
            self.embers.append([math.cos(a) * sp, math.sin(a) * sp, rng.uniform(0.9, 2.2), rng.uniform(0, 6.28)])
        self.puffs = []
        for _ in range(PUFFS):
            a = rng.uniform(0, math.tau)
            sp = rng.uniform(10.0, 70.0) * self.size ** 0.5
            self.puffs.append([math.cos(a) * sp, math.sin(a) * sp, rng.uniform(0.08, 0.5), rng.uniform(26.0, 52.0) * self.size ** 0.5,
                               rng.uniform(1.2, 2.0)])

    # ---------------------------------------------------------------- the hull in pieces
    def _cut(self, img):
        w, h = img.get_size()
        cx, cy = w / 2.0, h / 2.0
        rng = self.rng
        pix = [(x, y, img.get_at((x, y))) for y in range(h) for x in range(w) if img.get_at((x, y)).a > 24]
        if not pix:
            return []
        n = min(SHARDS, len(pix))
        seeds = [(p[0], p[1]) for p in rng.sample(pix, n)]
        groups = [[] for _ in seeds]
        for x, y, c in pix:
            best = min(range(n), key=lambda i: (x - seeds[i][0]) ** 2 + (y - seeds[i][1]) ** 2)
            groups[best].append((x, y, c))
        shards = []
        for g in groups:
            if not g:
                continue
            x0, x1 = min(p[0] for p in g), max(p[0] for p in g)
            y0, y1 = min(p[1] for p in g), max(p[1] for p in g)
            surf = pygame.Surface((x1 - x0 + 1, y1 - y0 + 1), pygame.SRCALPHA)
            for x, y, c in g:
                surf.set_at((x - x0, y - y0), c)
            big = pygame.transform.scale(surf, (max(1, int(surf.get_width() * self.shard_k)), max(1, int(surf.get_height() * self.shard_k))))
            hot = big.copy()
            hot.fill((190, 90, 10, 0), special_flags=pygame.BLEND_RGB_ADD)
            dark = big.copy()
            dark.fill((70, 62, 58, 255), special_flags=pygame.BLEND_RGB_MULT)
            mx = sum(p[0] for p in g) / len(g) - cx
            my = sum(p[1] for p in g) / len(g) - cy
            d = math.hypot(mx, my)
            if d < 0.5:
                a = rng.uniform(0, math.tau)
                ux, uy = math.cos(a), math.sin(a)
            else:
                ux, uy = mx / d, my / d
            speed = rng.uniform(70.0, 230.0) * self.size ** 0.5
            shards.append(_Shard((big, hot, dark), self.x + mx * self.shard_k, self.y + my * self.shard_k,
                                 ux * speed + rng.uniform(-30, 30) + self.vx, uy * speed + rng.uniform(-30, 30) + self.vy,
                                 rng.uniform(-9.0, 9.0), rng.uniform(0.0, 360.0)))
        return shards

    # ---------------------------------------------------------------- the life of it
    @property
    def finished(self):
        return self.age >= DURATION

    def update(self, dt):
        self.age += dt
        damp = math.exp(-SHARD_DRAG * dt)
        for s in self.shards:
            s.x += s.vx * dt
            s.y += s.vy * dt
            s.vx *= damp
            s.vy *= damp
            s.angle += s.spin * 57.3 * dt

    def draw(self, surface, angle=None, scale=1.0):
        """(`angle` and `scale` are those of ShipBurn.draw: the blast was made in the turn and size of the ship.)"""
        if self.finished:
            return
        t = self.age
        x, y = self.x, self.y
        # smoke, behind everything
        for dx, dy, t0, radius, life in self.puffs:
            u = (t - t0) / life
            if 0.0 <= u < 1.0:
                r = max(2, int(radius * (0.35 + 0.65 * math.sqrt(u))))
                shade = int(_lerp(95, 30, u))
                pic = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(pic, (shade, shade - 6, shade - 10, int(120 * (1.0 - u) ** 1.5)), (r, r), r)
                surface.blit(pic, (int(x + dx * u * life - r), int(y + dy * u * life - r)))
        # the fireball: layered lights that swell fast and cool
        grow = 1.0 - math.exp(-t * 6.0)
        heat = max(0.0, 1.0 - t / 1.1)
        if heat > 0.0:
            asteroids._add_glow(surface, _scaled((255, 70, 20), heat), (x, y), (60 + 230 * grow) * self.size)
            asteroids._add_glow(surface, _scaled((255, 150, 50), heat), (x, y), (40 + 150 * grow) * self.size)
            asteroids._add_glow(surface, _scaled((255, 230, 150), heat * heat), (x, y), (24 + 80 * grow) * self.size)
        # the hull in pieces, glowing and then charred, each with a spark of light behind it while it is hot
        for s in self.shards:
            if t < 0.9:
                asteroids._add_glow(surface, _scaled((255, 140, 40), 1.0 - t / 0.9), (s.x, s.y), 16 * self.size)
            if t < 0.14:
                img = s.imgs[0]
            elif t < 0.8:
                img = s.imgs[1]
            else:
                img = s.imgs[2]
            img = pygame.transform.rotate(img, s.angle)
            if t > 1.5:
                img.set_alpha(max(0, int(255 * (1.0 - (t - 1.5) / (DURATION - 1.5)))))
            surface.blit(img, img.get_rect(center=(round(s.x), round(s.y))))
        # the sparks: streaks that slow down and cool from white to red
        for ux, uy, speed, life, width in self.sparks:
            u = t / life
            if 0.0 <= u < 1.0:
                run = speed * (1.0 - math.exp(-2.2 * t)) / 2.2
                px, py = x + self.vx * t + ux * run, y + self.vy * t + uy * run
                tail = max(2.0, speed * math.exp(-2.2 * t) * 0.06)
                color = _mix((255, 250, 200), (255, 70, 15), min(1.0, u * 1.4))
                color = _scaled(color, 1.0 - u * u)
                pygame.draw.line(surface, color, (px, py), (px - ux * tail, py - uy * tail), width)
        # the embers that drift away and flicker
        for vx, vy, life, phase in self.embers:
            u = t / life
            if 0.0 <= u < 1.0:
                ex, ey = x + self.vx * t + vx * t * (1.0 - 0.3 * u), y + self.vy * t + vy * t * (1.0 - 0.3 * u)
                flicker = 0.65 + 0.35 * math.sin(t * 22.0 + phase)
                asteroids._add_glow(surface, _scaled((255, 130, 40), (1.0 - u) * flicker), (ex, ey), 9 * self.size)
        # the white flash at the start
        if t < FLASH_TIME:
            k = 1.0 - t / FLASH_TIME
            asteroids._add_glow(surface, _scaled((255, 255, 235), k), (x, y), (150 + 260 * (1.0 - k)) * self.size)
        # the shock rings
        for delay, reach in RINGS:
            u = (t - delay) / RING_TIME
            if 0.0 <= u < 1.0:
                radius = reach * self.size / EFFECT_SIZE * (1.0 - (1.0 - u) ** 2.2)
                d = int(radius * 2 + 10)
                ring = pygame.Surface((d, d))
                color = _scaled(_mix((255, 245, 215), (255, 120, 60), u), (1.0 - u) ** 1.3)
                pygame.draw.circle(ring, color, (d // 2, d // 2), max(1, int(radius)), 3 if u < 0.6 else 2)
                surface.blit(ring, (int(x - d / 2), int(y - d / 2)), special_flags=pygame.BLEND_RGB_ADD)
