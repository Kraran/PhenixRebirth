"""
The VIP rescue (Act 2 BONUS mission "bonus_vip", story_state.py): a small luxury cruise ship crosses the bottom of the
screen, slowly, from left to right, and the blue and khaki avioids of level 3 throw themselves at it.

- The cruise ship rides the ship's line. Shots go through it (the birds' and the player's), but the player's ship is
  solid against it: it cannot go through, it bumps into it without damage, and while it is in front of the cruise ship
  the cruise ship waits. The two-dimensional reactor (needed to fly this mission) lets the ship pass above it.
- A bird that touches the cruise ship destroys it: the mission is lost (`EscortFormation.failed`, a little after the
  explosion, so it is seen).
- The birds are replaced as they fall, for ever: the mission is won only when the cruise ship has passed the right edge
  completely. Then the birds flee off the top and the ship flies up as after any wave.

`EscortFormation` is the EnemyFormation of the mission (birds from the swarm machinery, kinds 1 and 2, an endless
reserve); `tick(game)` moves the cruise ship and settles the bumps every frame, `draw(game)` draws it and its messages.
"""
import math
import random

import pygame

from enemy import EnemyFormation
from settings import BASE_HEIGHT, BASE_WIDTH

ON_SCREEN = {1: 7, 2: 11}          # birds in the formation at once: blue, khaki (about half a screen of each)
ENDLESS = 10 ** 9                  # the reserve: they never run out
MAX_DIVERS = 2                     # birds diving at the cruise ship at the same time
DIVE_GAP = 1.3                     # seconds between two birds starting their dive
AIM_SPREAD = 60                    # a diver goes for a point up to this far from the centre of the cruise ship
AIM_LEAD = 30                      # ... a little ahead of it, it is moving
CRUISE_SPEED = 22.0                # px / s: about a minute across the screen when nothing stops it
CRUISE_W, CRUISE_H = 156, 64       # the picture
CRUISE_Y = BASE_HEIGHT - 95        # its centre: on the line of the ship (story missions start the ship there)
HULL = (146, 44)                   # what is solid / what a bird must touch (inside the picture)
LOST_DELAY = 2.2                   # seconds between the explosion and the end of the mission
DIVE_FROM_X = 40                   # the birds wait until the centre of the cruise ship is that far in


def ship_body(ship):
    """The part of a player's ship that is solid against the cruise ship (its hull, not the glow of a dome)."""
    w = int(getattr(ship, "hitbox_w", 46) or 46)
    h = int(max(getattr(ship, "hitbox_h", 46) or 46, (getattr(ship, "height", 90) or 90) * 0.6))
    return pygame.Rect(int(ship.x - w / 2), int(ship.y - h / 2), w, h)


class CruiseShip:
    """The VIP's ship. `x` is its centre; it starts out of the screen on the left."""

    def __init__(self, speed=CRUISE_SPEED):
        self.speed = float(speed)
        self.x = -CRUISE_W / 2 - 4.0
        self.y = float(CRUISE_Y)
        self.blocked = False             # held up by the player's ship this frame
        self.destroyed = False
        self.time = 0.0

    def hull(self, x=None):
        cx = self.x if x is None else x
        return pygame.Rect(int(cx - HULL[0] / 2), int(self.y - HULL[1] / 2), HULL[0], HULL[1])

    @property
    def through(self):
        """Gone past the right edge, all of it."""
        return self.x - CRUISE_W / 2 >= BASE_WIDTH

    def progress(self):
        """0.0 (not in yet) to 1.0 (through)."""
        start, end = -CRUISE_W / 2, BASE_WIDTH + CRUISE_W / 2
        return max(0.0, min(1.0, (self.x - start) / (end - start)))

    def advance(self, dt, bodies):
        """Move on, unless a ship stands in the way (it waits, it does not push)."""
        self.time += dt
        if self.destroyed or self.through:
            return
        nxt = self.x + self.speed * dt
        ahead = self.hull(nxt)
        self.blocked = any(ahead.colliderect(b) for b in bodies)
        if not self.blocked:
            self.x = nxt


def bump(ship, cruise):
    """The player's ship cannot go through the cruise ship: push it out the shortest way (left, right or up; there is
    no room under it). True when it was pushed."""
    body, hull = ship_body(ship), cruise.hull()
    if not body.colliderect(hull):
        return False
    left = body.right - hull.left            # how far to move it left to get it out
    right = hull.right - body.left
    up = body.bottom - hull.top
    move = min(left, right, up)
    if move == up:
        ship.y -= up
    elif move == left:
        ship.x -= left
    else:
        ship.x += right
    return True


class EscortFormation(EnemyFormation):
    """Blue and khaki birds in formation, replaced for ever, that dive at the cruise ship."""

    def __init__(self, speed_mult=1.0, cruise_speed=CRUISE_SPEED):
        super().__init__(stage=1)
        self.cruise = CruiseShip(cruise_speed)
        self.won = False                 # the cruise ship is through: the birds flee
        self.fleeing = False
        self.dive_wait = 0.0             # until the next bird may dive
        self.lost_timer = None           # seconds since the cruise ship blew up
        self.failed = False              # the mission is lost (set LOST_DELAY after the explosion)
        self.spawn_escort(speed_mult)

    # the swarm machinery, with two kinds and their own counts
    @staticmethod
    def swarm_on_screen(kind):
        return ON_SCREEN.get(kind, 0)

    def spawn_escort(self, speed_mult=1.0):
        self.spawn_swarm(speed_mult=speed_mult, screens=0)
        self.enemies = [e for e in self.enemies if e.stage in (1, 2)]       # (the swarm adds gargoyles: none here)
        self.swarm["reserve"] = {1: ENDLESS, 2: ENDLESS, 3: 0, 4: 0}
        for e in self.enemies:
            self._hook(e)

    def _swarm_add_bird(self, slot_i, kind, arriving):
        return self._hook(super()._swarm_add_bird(slot_i, kind, arriving))

    def _swarm_add_gargoyle(self, kind, arriving):
        return None                      # no gargoyles in this mission

    def _hook(self, bird):
        bird.dive_aim = self._aim
        bird.dive_gate = self._may_dive
        bird.aim_offset = random.uniform(-AIM_SPREAD, AIM_SPREAD)
        return bird

    def _aim(self):
        return self.cruise.x + AIM_LEAD

    def divers(self):
        return sum(1 for e in self.enemies if e.alive and not e.dying and e.state == "diving")

    def _may_dive(self):
        """Up to MAX_DIVERS at a time, once the cruise ship is well in sight, never after it is through or lost."""
        cruise = self.cruise
        if self.won or cruise.destroyed or cruise.x < DIVE_FROM_X or self.dive_wait > 0:
            return False
        if self.divers() >= MAX_DIVERS:
            return False
        self.dive_wait = DIVE_GAP        # this one goes: the next one waits
        return True

    def update(self, dt, player_x):
        self.dive_wait = max(0.0, self.dive_wait - dt)
        if self.won and not self.fleeing:
            self.fleeing = True
            self.swarm["reserve"] = {1: 0, 2: 0, 3: 0, 4: 0}       # nobody comes in any more
            for e in self.enemies:
                if e.alive and not e.dying:
                    e.state = "returning"                         # back up to a seat... above the screen
                    e.start_y = -200.0
        super().update(dt, self.cruise.x)
        if self.fleeing:
            for e in self.enemies:
                if e.alive and not e.dying and e.y < -60:
                    e.alive = False
        if self.lost_timer is not None:
            self.lost_timer += dt
            if self.lost_timer >= LOST_DELAY:
                self.failed = True

    def all_dead(self):
        """The wave is over when the cruise ship is through and the birds are gone (never while it is on its way)."""
        if not self.won:
            return False
        return not any(e.alive and not e.dying for e in self.enemies)

    def remaining(self):
        return 0


def tick(game):
    """Every frame of the VIP rescue: the cruise ship goes on (or waits), bumps against the player's ship, birds that
    reach it. Returns "lost" the frame it is destroyed, "won" the frame it is through, else None."""
    form = getattr(game, "formation", None)
    if not isinstance(form, EscortFormation) or getattr(game, "stage_transition", None) is not None:
        return None
    cruise = form.cruise
    if cruise.destroyed or form.won:
        return None
    ships = [s for s in game._ships() if s.alive and not s.dying]
    cruise.advance(game.dt, [ship_body(s) for s in ships])
    for ship in ships:
        bump(ship, cruise)
    if cruise.through:
        form.won = True
        form.bullets = []
        try:
            game.sounds.play("1up", x=BASE_WIDTH - 40)
        except Exception:
            pass
        return "won"
    hull = cruise.hull()
    for e in form.get_hittable_enemies():
        if e.get_hitbox().colliderect(hull):
            cruise.destroyed = True
            form.lost_timer = 0.0
            e.kill(flash=False)
            game.explosions.append(game._boom(e.x, e.y, kind="collision"))
            for dx in (-48, 0, 48):
                game.explosions.append(game._boom(cruise.x + dx, cruise.y + random.uniform(-8, 8), kind="gameover"))
            game.shake_amount = max(getattr(game, "shake_amount", 0.0), 24.0)
            try:
                game.sounds.play("explosion_big", x=cruise.x)
            except Exception:
                pass
            return "lost"
    return None


def failed(game):
    """The cruise ship blew up a little while ago: the mission is lost."""
    form = getattr(game, "formation", None)
    return isinstance(form, EscortFormation) and form.failed


# ------------------------------------------------------------------------------------------------------------------
# The picture: a small personal space yacht seen from the side, its nose to the right: a pearl white hull with a gold
# line, a long deck of lit windows, a glass bridge at the front, the engine pod at the back. Drawn once, three times
# bigger then scaled down, so the edges are smooth.
_PICTURE = []


def _drop(w, h, x0, x1, top, bottom, cy, sharp=0.35):
    """Points of a long drop shape from x0 (round back) to x1 (pointed nose) around the line cy."""
    pts_top, pts_bot = [], []
    n = 48
    for i in range(n + 1):
        u = i / n
        x = x0 + (x1 - x0) * u
        back = math.sqrt(max(0.0, 1 - (1 - min(1.0, u / 0.18)) ** 2))       # round at the back
        nose = (1 - max(0.0, (u - 0.62) / 0.38)) ** (1 + sharp)             # tapering to the nose
        f = back * nose
        pts_top.append((x, cy - top * f))
        pts_bot.append((x, cy + bottom * f))
    return pts_top + pts_bot[::-1]


def picture():
    if _PICTURE:
        return _PICTURE[0]
    k = 3
    w, h = CRUISE_W * k, CRUISE_H * k
    big = pygame.Surface((w, h), pygame.SRCALPHA)
    gold, gold_hi = (214, 176, 70), (255, 228, 150)
    pearl, pearl_dark, edge = (232, 234, 242), (150, 156, 182), (96, 100, 128)
    cy = h * 0.66
    # the superstructure (a long cabin on the deck), behind the hull
    deck = _drop(w, h, w * 0.18, w * 0.80, h * 0.50, h * 0.05, cy - h * 0.02, sharp=1.2)
    pygame.draw.polygon(big, (210, 214, 228), deck)
    pygame.draw.polygon(big, edge, deck, 3)
    # two rows of warm windows along the cabin
    for row, (yy, n, x0, step) in enumerate(((cy - h * 0.30, 9, w * 0.25, w * 0.052),
                                             (cy - h * 0.16, 11, w * 0.22, w * 0.050))):
        for i in range(n):
            r = pygame.Rect(int(x0 + i * step), int(yy), int(w * 0.034), int(h * 0.075))
            pygame.draw.rect(big, (255, 210, 130), r, border_radius=int(h * 0.03))
            pygame.draw.rect(big, (255, 240, 200), r.inflate(-r.w * 0.5, -r.h * 0.5).move(-r.w * 0.1, -r.h * 0.12),
                             border_radius=int(h * 0.02))
    # the glass bridge at the front of the cabin
    bridge = [(w * 0.66, cy - h * 0.38), (w * 0.74, cy - h * 0.38), (w * 0.84, cy - h * 0.10), (w * 0.66, cy - h * 0.10)]
    pygame.draw.polygon(big, (30, 52, 98), bridge)
    pygame.draw.polygon(big, (120, 170, 235), [(w * 0.70, cy - h * 0.35), (w * 0.735, cy - h * 0.35),
                                               (w * 0.77, cy - h * 0.24), (w * 0.70, cy - h * 0.24)])
    pygame.draw.polygon(big, gold, bridge, 4)
    # the hull, in front of everything
    hull = _drop(w, h, w * 0.06, w * 0.99, h * 0.13, h * 0.26, cy, sharp=0.6)
    pygame.draw.polygon(big, pearl, hull)
    shade = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(int(cy), h):
        a = max(0, int(min(150, (y - cy) * 2.6)))
        pygame.draw.line(shade, pearl_dark + (a,), (0, y), (w, y))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), hull)
    shade.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    big.blit(shade, (0, 0))
    pygame.draw.polygon(big, edge, hull, 3)
    # the gold line along the hull, and a thin light one above it
    pygame.draw.line(big, gold, (w * 0.08, cy + h * 0.02), (w * 0.95, cy + h * 0.005), 8)
    pygame.draw.line(big, gold_hi, (w * 0.08, cy - h * 0.005), (w * 0.95, cy - h * 0.02), 3)
    # portholes along the hull
    for i in range(6):
        c = (int(w * (0.30 + i * 0.08)), int(cy + h * 0.12))
        pygame.draw.circle(big, (40, 60, 100), c, int(h * 0.035))
        pygame.draw.circle(big, (170, 210, 250), (c[0] - 2, c[1] - 2), int(h * 0.015))
    # a gold fin at the back, the engine pod at the very back
    pygame.draw.polygon(big, gold, [(w * 0.14, cy - h * 0.10), (w * 0.26, cy - h * 0.12), (w * 0.12, cy - h * 0.50)])
    pygame.draw.polygon(big, gold_hi, [(w * 0.14, cy - h * 0.14), (w * 0.17, cy - h * 0.15), (w * 0.13, cy - h * 0.40)])
    eng = pygame.Rect(int(w * 0.02), int(cy - h * 0.14), int(w * 0.12), int(h * 0.30))
    pygame.draw.ellipse(big, (84, 90, 116), eng)
    pygame.draw.ellipse(big, (140, 146, 170), eng.inflate(-eng.w * 0.25, -eng.h * 0.35).move(eng.w * 0.08, -eng.h * 0.06))
    pygame.draw.ellipse(big, (170, 225, 255), pygame.Rect(eng.x, eng.y + eng.h * 0.22, eng.w * 0.30, eng.h * 0.56))
    small = pygame.transform.smoothscale(big, (CRUISE_W, CRUISE_H))
    _PICTURE.append(small)
    return small


def _flame(surface, x, y, t, blocked):
    """The jet behind the engine, flickering; short while the cruise ship waits."""
    n = 0.7 + 0.3 * math.sin(t * 31.0) * math.sin(t * 17.0 + 1.3)
    length = (8 if blocked else 22) * n + 6
    glow = pygame.Surface((int(length) + 16, 22), pygame.SRCALPHA)
    gw = glow.get_width()
    pygame.draw.ellipse(glow, (90, 170, 255, 90), pygame.Rect(0, 3, gw, 16))
    pygame.draw.ellipse(glow, (190, 230, 255, 200), pygame.Rect(gw * 0.35, 7, gw * 0.65, 8))
    surface.blit(glow, (int(x - gw + 4), int(y - 11)))


def draw(game, surface):
    form = getattr(game, "formation", None)
    if not isinstance(form, EscortFormation):
        return
    cruise = form.cruise
    if not cruise.destroyed and not cruise.through:
        img = picture()
        left = int(cruise.x - CRUISE_W / 2)
        top = int(cruise.y - CRUISE_H * 0.59)          # the cabin and the hull around the centre line
        _flame(surface, left + 6, top + CRUISE_H * 0.66, cruise.time, cruise.blocked)
        surface.blit(img, (left, top))


def banner(game, surface):
    """The cruise ship blew up / is through: one line in the middle of the screen (over everything)."""
    from i18n import t
    form = getattr(game, "formation", None)
    if not isinstance(form, EscortFormation):
        return
    cruise = form.cruise
    if cruise.destroyed:
        key, col = "story_vip_lost", (255, 90, 80)
    elif form.won:
        key, col = "story_vip_safe", (255, 220, 120)
    else:
        return
    font = getattr(game, "medium_font", None) or game.font
    tc = getattr(game, "text_cache", None)
    img = tc.get(font, t(key), col) if tc is not None else font.render(t(key), True, col)
    surface.blit(img, (BASE_WIDTH // 2 - img.get_width() // 2, BASE_HEIGHT // 2 - 60))
