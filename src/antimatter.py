"""The antimatter missile: the reward of Silent Sentinels IV, once it is won, for every mission of the Adventure.

One missile per mission (the stock is `game.antimatter`, made by `begin` when the mission starts and only if the
mission spec says `antimatter`). A key / a pad button (bindings action "missile") fires it straight ahead of the ship:
up in the missions that scroll, along the heading of the ship in the Asteroids and SpaceWar missions. It is the torpedo
of SpaceWar, a little bigger. It flies in a straight line until it touches an enemy: then a blast destroys every enemy
within BLAST_RADIUS (a quarter of the height of the screen), the usual points paid. On the armour of the boss saucer the
blast is a smaller one (SAUCER_BLAST: two bricks round the impact). A missile that touches nothing and leaves the
screen is lost (and so is the one the star of SpaceWar stops): there is no second one.

    antimatter.begin(game, spec)     the stock of a mission
    antimatter.fire(game, ship)      the key was pressed (True when a missile left)
    antimatter.tick(game)            every frame: flight, impact, blast
    antimatter.draw(game, surface)   the missiles in flight; draw_hud: the reminder of the key
"""
import math

import pygame

import asteroids
import bindings
import spacewar
from errlog import log_exc
from i18n import t
from settings import BASE_HEIGHT, BASE_WIDTH

BLAST_RADIUS = 180.0              # px: a quarter of the screen (720): what is within this distance of the impact is destroyed
SAUCER_BLAST = 52.0               # px: two bricks of the boss saucer (26 px each) round the impact
SPEED = 560.0                     # px/s, plus the speed of the ship in the free missions
SIZE = 1.35                       # the drawing of the SpaceWar torpedo, this much bigger
START_AHEAD = 34.0                # px from the middle of a ship that turns (the nose)
HIT_HALF = 9                      # the missile touches with a square this big (half side)
MAX_STEP = 8.0                    # px: a longer move is cut, so that nothing is crossed
MAX_AGE = 4.0                     # s: a missile in flight for so long is lost
HUD_COLOR = (255, 190, 90)
DONE_COLOR = (110, 110, 130)
BLAST_TIME = 1.5
FLASH_TIME = 0.2


class Missile:
    def __init__(self, x, y, ux, uy, vx=0.0, vy=0.0):
        self.x, self.y = float(x), float(y)
        self.ux, self.uy = float(ux), float(uy)               # the way it flies (unit vector)
        self.vx = self.ux * SPEED + float(vx)
        self.vy = self.uy * SPEED + float(vy)
        self.age = 0.0

    def step(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.age += dt

    def rect(self):
        return pygame.Rect(int(self.x) - HIT_HALF, int(self.y) - HIT_HALF, HIT_HALF * 2, HIT_HALF * 2)

    def gone(self):
        """Out of the screen (it does not come round), or too old."""
        return (self.age > MAX_AGE or self.x < -30 or self.x > BASE_WIDTH + 30 or self.y < -30 or self.y > BASE_HEIGHT + 30)


class Armory:
    """The missile of the mission: `ready` until it is fired; `missiles` the ones in flight."""

    def __init__(self, ready=True):
        self.ready = bool(ready)
        self.missiles = []


# ------------------------------------------------------------------------------------------------ the mission
def begin(game, spec):
    """The stock of a mission that starts (None when the mission has no missile)."""
    game.antimatter = Armory(True) if (spec or {}).get("antimatter") else None
    return game.antimatter


def _armory(game):
    """The stock of the mission being flown, or None (the arcade game, a mission without a missile)."""
    if not getattr(game, "adventure", None):
        return None
    return getattr(game, "antimatter", None)


def _free_mode(game):
    """The ship turns in this mission (Asteroids, SpaceWar): the missile flies along its heading."""
    return spacewar.active(game) is not None or asteroids.active(game) is not None


def fire(game, ship):
    arm = _armory(game)
    if arm is None or not arm.ready or ship is None:
        return False
    if (not getattr(game, "started", False) or getattr(game, "paused", False) or getattr(game, "game_over", False)
            or getattr(game, "stage_transition", None) is not None or not ship.alive or ship.dying):
        return False
    if _free_mode(game):
        a = float(getattr(ship, "ast_angle", -math.pi / 2))
        ux, uy = math.cos(a), math.sin(a)
        m = Missile(ship.x + ux * START_AHEAD, ship.y + uy * START_AHEAD, ux, uy,
                    getattr(ship, "ast_vx", 0.0) or 0.0, getattr(ship, "ast_vy", 0.0) or 0.0)
    else:
        m = Missile(ship.x, ship.y - ship.height // 2 - 6, 0.0, -1.0)
    arm.ready = False
    arm.missiles.append(m)
    try:
        game.sounds.play("shoot", volume=0.8, x=ship.x)
    except Exception:
        log_exc("antimatter.fire")
    return True


def tick(game):
    """Every frame of a mission with a missile: it flies, touches, blows up (or is lost)."""
    arm = _armory(game)
    if arm is None or not arm.missiles:
        return
    if getattr(game, "stage_transition", None) is not None or getattr(game, "game_over", False):
        arm.missiles.clear()                      # the wave is over: a missile still in the air is lost
        return
    dt = float(game.dt)
    for m in list(arm.missiles):
        steps = max(1, int(math.ceil(math.hypot(m.vx, m.vy) * dt / MAX_STEP)))
        for _ in range(steps):
            m.step(dt / steps)
            hit = _touch(game, m)
            if hit is not None:
                arm.missiles.remove(m)
                if hit != "star":
                    blast(game, m.x, m.y)
                break
            if m.gone():
                arm.missiles.remove(m)
                break


# ------------------------------------------------------------------------------------------------ the impact
def _saucer_touch(boss, rect):
    """Does the missile touch the body of the boss saucer (an armour brick, a decoration, the core)?"""
    for deco in boss.decorations:
        if deco.alive and rect.colliderect(deco.get_hitbox()):
            return True
    for cell in boss.cells:
        if cell.alive and rect.colliderect(cell.get_hitbox()):
            return True
    return bool(boss.boss.alive and not boss.boss.dying and rect.colliderect(boss.boss.get_hitbox()))


def _touch(game, m):
    """What the missile touches now: "hit" (an enemy), "star" (the star of SpaceWar: it is lost), or None."""
    x, y, rect = m.x, m.y, m.rect()
    sw = spacewar.active(game)
    if sw is not None:
        if math.hypot(x - spacewar.CX, y - spacewar.CY) < spacewar.STAR_R:
            return "star"
        for b in sw.birds:
            if b.alive and math.hypot(x - b.x, y - b.y) < b.radius + HIT_HALF:
                return "hit"
        rock = sw.rock
        if rock is not None and math.hypot(x - rock.x, y - rock.y) < rock.radius + HIT_HALF:
            return "hit"
        return None
    ast = asteroids.active(game)
    if ast is not None:
        for r in ast.rocks:
            dx, dy = r.delta_to(x, y)
            if dx * dx + dy * dy < (r.radius + HIT_HALF) ** 2:
                return "hit"
        s = ast.saucer
        if s is not None:
            dx, dy = asteroids.wrapped_delta(x, y, s.x, s.y)
            if abs(dx) < asteroids.SAUCER_HALF[0] + HIT_HALF and abs(dy) < asteroids.SAUCER_HALF[1] + HIT_HALF:
                return "hit"
        return None
    boss = getattr(game, "boss_saucer", None)
    if boss is not None and boss.alive and _saucer_touch(boss, rect):
        return "hit"
    form = game.formation
    for e in form.get_hittable_enemies():
        if rect.colliderect(e.get_hitbox()):
            return "hit"
    mother = getattr(form, "mothership", None)
    if mother is not None and mother.alive and not mother.dying and rect.colliderect(mother.get_hitbox()):
        return "hit"
    return None


# ------------------------------------------------------------------------------------------------ the blast
def _near_rect(rect, x, y, radius):
    """Is the rectangle within `radius` of the point (its nearest point counts)?"""
    nx = max(rect.left, min(x, rect.right))
    ny = max(rect.top, min(y, rect.bottom))
    return math.hypot(nx - x, ny - y) <= radius


def blast(game, x, y):
    """The impact at (x, y): everything within BLAST_RADIUS is destroyed (the armour of the boss saucer: SAUCER_BLAST)."""
    sw = spacewar.active(game)
    ast = asteroids.active(game)
    if sw is not None:
        _blast_spacewar(game, sw, x, y)
    elif ast is not None:
        _blast_asteroids(game, ast, x, y)
    else:
        _blast_waves(game, x, y)
    game.explosions.append(Blast(x, y, BLAST_RADIUS))
    game.shake_amount = max(game.shake_amount, 26.0)
    try:
        game.sounds.play("explosion_big", x=x)
    except Exception:
        log_exc("antimatter.blast")


def _kill_enemy(game, e):
    """A bird of the waves falls to the blast, like to a shot of the ship: its points, its explosion."""
    ship = game.player
    e.kill()
    game._add_score(ship, game._enemy_kill_points(e))
    game._note_bird_kill()
    game.explosions.append(game._boom(e.x, e.y, kind="enemy", delay_frames=1))
    game.sounds.play("enemy_explosion", x=e.x)


def _blast_waves(game, x, y):
    form = game.formation
    for e in list(form.get_hittable_enemies()):
        if _near_rect(e.get_hitbox(), x, y, BLAST_RADIUS):
            _kill_enemy(game, e)
    mother = getattr(form, "mothership", None)
    if mother is not None and mother.alive and not mother.dying and _near_rect(mother.get_hitbox(), x, y, BLAST_RADIUS):
        game._add_score(game.player, form.mothership_hit(mother.x))              # (Space Invaders: the miniature saucer)
        game.explosions.append(game._boom(mother.x, mother.y, kind="gameover"))
    boss = getattr(game, "boss_saucer", None)
    if boss is not None and boss.alive:
        _blast_saucer(game, boss, x, y)


def _blast_saucer(game, boss, x, y):
    """The boss saucer: what is within SAUCER_BLAST (two bricks) of the impact goes: bricks, decorations, and the core."""
    ship = game.player
    r = SAUCER_BLAST
    hit = False
    for deco in boss.decorations:
        if deco.alive and _near_rect(deco.get_hitbox(), x, y, r):
            deco.alive = False
            hit = True
            zone = deco.get_hitbox().inflate(max(16, deco.w // 3), max(12, deco.h // 3))
            for cell in boss.cells:
                if cell.alive and not getattr(cell, "is_purple", False) and cell.get_hitbox().colliderect(zone):
                    cell.alive = False
            game.explosions.append(game._boom(deco.x, deco.y, kind="flame"))
            game._add_score(ship, game._deco_points())
    for cell in boss.cells:
        if cell.alive and _near_rect(cell.get_hitbox(), x, y, r):
            cell.alive = False
            hit = True
            game.explosions.append(game._boom(cell.x, cell.y, kind="electric" if getattr(cell, "is_purple", False) else "enemy"))
            game._add_score(ship, 1)
    if hit:
        boss._apply_pair_effects()
        boss._invalidate_cells()
    core = boss.boss
    if core.alive and not core.dying and _near_rect(core.get_hitbox(), x, y, r):
        core.kill()
        game._add_score(ship, game._boss_kill_points())
        game.explosions.append(game._boom(core.x, core.y, kind="gameover"))
        game.shake_amount = max(game.shake_amount, 20.0)


def _blast_spacewar(game, form, x, y):
    for b in list(form.birds):
        if b.alive and math.hypot(x - b.x, y - b.y) <= BLAST_RADIUS + b.radius:
            # (the saucer of SpaceWar too: the antimatter takes all its points at once)
            spacewar._kill_bird(game, form, b)
    rock = form.rock
    if rock is not None and math.hypot(x - rock.x, y - rock.y) <= BLAST_RADIUS + rock.radius:
        form.debris(rock.x, rock.y, "rock", 14, 240, life=(0.5, 1.2), size=(2.0, 4.0))
        form.rock = None


def _blast_asteroids(game, form, x, y):
    for _ in range(64):                                    # (the pieces of a rock are still in the blast: they go too)
        near = [r for r in form.rocks if math.hypot(*r.delta_to(x, y)) <= BLAST_RADIUS + r.radius]
        if not near:
            break
        for r in near:
            form.break_rock(game, r)
    s = form.saucer
    if s is not None and math.hypot(*asteroids.wrapped_delta(x, y, s.x, s.y)) <= BLAST_RADIUS + max(asteroids.SAUCER_HALF):
        form.blow_saucer(game)


# ------------------------------------------------------------------------------------------------ the explosion
def _lerp(a, b, k):
    return a + (b - a) * k


class Blast:
    """The big explosion of the impact: a white flash, a fireball that swells to the reach of the blast, two shock rings
    and embers. It has the interface of the explosions of the game (update, is_finished, draw)."""

    def __init__(self, x, y, reach):
        self.x, self.y, self.reach = float(x), float(y), float(reach)
        self.age = 0.0
        a0 = (x * 12.9898 + y * 78.233) % 6.28
        self.embers = [(a0 + i * 0.52, 0.5 + 0.5 * ((i * 37) % 11) / 10.0) for i in range(12)]

    def update(self, dt):
        self.age += dt

    def is_finished(self):
        return self.age >= BLAST_TIME

    def draw(self, surface):
        if self.is_finished():
            return
        t0 = self.age
        u = t0 / BLAST_TIME
        grow = 1.0 - math.exp(-t0 * 7.0)
        heat = max(0.0, 1.0 - t0 / 1.1)
        d = self.reach * 2.0
        if heat > 0.0:
            for color, k in (((255, 70, 20), 1.0), ((255, 150, 50), 0.72), ((255, 235, 170), 0.4)):
                c = tuple(int(v * heat) for v in color)
                asteroids._add_glow(surface, c, (self.x, self.y), int(d * k * (0.25 + 0.75 * grow)))
        if t0 < FLASH_TIME:
            c = int(255 * (1.0 - t0 / FLASH_TIME))
            asteroids._add_glow(surface, (c, c, int(c * 0.9)), (self.x, self.y), int(d * 0.7))
        for delay, scale in ((0.0, 1.0), (0.12, 0.7)):
            v = (t0 - delay) / 0.8
            if 0.0 <= v < 1.0:
                radius = self.reach * scale * (1.0 - (1.0 - v) ** 2.2)
                size = int(radius * 2 + 10)
                ring = pygame.Surface((size, size))
                fade = (1.0 - v) ** 1.3
                color = tuple(int(_lerp(a, b, v) * fade) for a, b in zip((255, 245, 215), (255, 120, 60)))
                pygame.draw.circle(ring, color, (size // 2, size // 2), max(1, int(radius)), 4 if v < 0.6 else 2)
                surface.blit(ring, (int(self.x - size / 2), int(self.y - size / 2)), special_flags=pygame.BLEND_RGB_ADD)
        for a, sp in self.embers:
            run = self.reach * sp * (1.0 - math.exp(-t0 * 3.0))
            fade = max(0.0, 1.0 - u)
            asteroids._add_glow(surface, (int(255 * fade), int(140 * fade), int(40 * fade)),
                                (self.x + math.cos(a) * run, self.y + math.sin(a) * run), 14)


# ------------------------------------------------------------------------------------------------ on screen
def draw(game, surface):
    """The missile in flight: the torpedo of SpaceWar, a little bigger."""
    arm = _armory(game)
    if arm is None:
        return
    tip = asteroids.tip_color(game.player)
    for m in arm.missiles:
        spacewar.draw_torpedo(surface, m.x, m.y, m.ux, m.uy, tip, SIZE)


def key_text(t_=t):
    """The first key of the missile of the solo game (the arrows keyboard)."""
    keys = bindings.current.keys(bindings.KB2, "missile")
    return bindings.key_label(keys[0], t_) if keys else "—"


def draw_hud(game):
    """A reminder at the top right while the missile is ready (dim once it is gone)."""
    arm = _armory(game)
    if arm is None or getattr(game, "attract_mode", False):
        return
    ready = arm.ready
    text = game.text_cache.get(game.font, t("antimatter_hud").format(key=key_text()), HUD_COLOR if ready else DONE_COLOR)
    game.game_surface.blit(text, (BASE_WIDTH - 16 - text.get_width(), 78))
