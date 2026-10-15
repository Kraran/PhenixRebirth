"""
The VIP rescue (Act 2 BONUS mission "bonus_vip", story_state.py): a small luxury cruise ship crosses the bottom of the
screen, slowly, from left to right, and the blue and khaki avioids of level 3 throw themselves at it.

- The cruise ship rides the ship's line. Shots go through it (the birds' and the player's), but the player's ship is
  solid against it: it cannot go through, it bumps into it without damage, and while it is in front of the cruise ship
  the cruise ship waits. The two-dimensional reactor (needed to fly this mission) lets the ship pass above it.
- A bird that touches the cruise ship destroys it: the mission is lost (`EscortFormation.failed`, a little after the
  explosion, so it is seen).
- The birds swirl before they strike: a bird that leaves the formation loops down for a moment (`EscortBird`, state
  "swirl"), drifting towards the cruise ship, then dives straight at it. A few at a time.
- The birds are replaced as they fall, for ever, but slowly (REFILL_DELAY): the mission is won only when the cruise ship
  has passed the right edge completely, its flame too. Then the birds flee off the top and the ship flies up as after
  any wave.

The yacht is Kraran's video cut in two by tools/make_vip_yacht.py: the hull (assets/sprites/vip_yacht.png, the only part
that counts for the collisions) and its reactor flame (vip_yacht_flame.png, every frame of the video, added on top).

`EscortFormation` is the EnemyFormation of the mission (birds from the swarm machinery, kinds 1 and 2, an endless
reserve); `tick(game)` moves the cruise ship and settles the bumps every frame, `draw(game)` draws it and its messages.
"""
import math
import random

import pygame

from enemy import Enemy, EnemyFormation
from errlog import log_exc
from settings import BASE_HEIGHT, BASE_WIDTH, ENEMY_DIVE_SPEED, asset_path

ON_SCREEN = {1: 7, 2: 11}          # birds in the formation at once: blue, khaki (about half a screen of each)
ENDLESS = 10 ** 9                  # the reserve: they never run out
REFILL_DELAY = 3.0                 # seconds between two newcomers of the same kind (the arcade swarm: 0.35)
MAX_DIVERS = 2                     # birds going for the cruise ship at the same time (swirling or diving)
DIVE_GAP = 1.3                     # seconds between two birds leaving the formation
AIM_SPREAD = 60                    # a diver goes for a point up to this far from the centre of the cruise ship
AIM_LEAD = 30                      # ... a little ahead of it, it is moving
SWIRL_TIME = (2.0, 3.2)            # how long a bird loops before it strikes (seconds, at random in between)
SWIRL_RADIUS = (60.0, 95.0)        # the size of its loops (px)
SWIRL_TURN = 2.0                   # seconds for one loop
SWIRL_SINK = 50.0                  # px / s: the loops go down...
SWIRL_DRIFT = 80.0                 # ... and towards the cruise ship
SWIRL_FLOOR = 230                  # ... but their centre stays this high: the strike starts well above the cruise ship
STRIKE_SPEED = 0.85                # the dive after the loops, a share of the arcade dive (one sees it coming)
STRIKE_SLANT = 0.55                # its sideways speed is at most this share of its speed down: a steep dive, no swoop
CRUISE_SPEED = 22.0                # px / s: about a minute across the screen when nothing stops it
HULL_W, HULL_H = 172, 49           # the picture of the hull (tools/make_vip_yacht.py)
HULL_BOX = (3, 6, 166, 40)         # in that picture: what is solid, what a bird must touch (not the thin roof, the flame)
FLAME_W, FLAME_H = 94, 49          # one frame of the flame, and where it sits from the left edge of the hull picture
FLAME_AT = (-92, 4)
FLAME_COLS, FLAME_FRAMES, FLAME_FPS = 16, 145, 24.0
HULL = HULL_BOX[2:]                # (width, height) of the solid part
CRUISE_Y = BASE_HEIGHT - 95        # its centre: on the line of the ship (story missions start the ship there)
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
        self.x = -HULL_W / 2 - 4.0
        self.y = float(CRUISE_Y)
        self.blocked = False             # held up by the player's ship this frame
        self.destroyed = False
        self.time = 0.0

    def picture_rect(self, x=None):
        """Where the picture of the hull is drawn (`x` is the centre of that picture)."""
        cx = self.x if x is None else x
        return pygame.Rect(int(cx - HULL_W / 2), int(self.y - HULL_H / 2), HULL_W, HULL_H)

    def hull(self, x=None):
        """The solid part: the hull without its thin roof, and never the flame."""
        pic = self.picture_rect(x)
        return pygame.Rect(pic.x + HULL_BOX[0], pic.y + HULL_BOX[1], HULL_BOX[2], HULL_BOX[3])

    @property
    def through(self):
        """Gone past the right edge, all of it, its flame too."""
        return self.x - HULL_W / 2 + FLAME_AT[0] >= BASE_WIDTH

    def progress(self):
        """0.0 (not in yet) to 1.0 (through)."""
        start, end = -HULL_W / 2, BASE_WIDTH + HULL_W / 2 - FLAME_AT[0]
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


class EscortBird(Enemy):
    """A blue or khaki bird of the escort: from its seat it swirls down in loops, drifting towards the cruise ship,
    then dives straight at it. `formation` gives what it aims at (`_aim`) and whether it may go now (`_may_dive`)."""

    def __init__(self, x, y, formation, formation_index=0, stage=1):
        super().__init__(x, y, formation_index=formation_index, stage=stage)
        self.formation = formation
        self.aim_offset = random.uniform(-AIM_SPREAD, AIM_SPREAD)
        self.swirl_t = 0.0
        self.swirl_time = 0.0
        self.swirl_r = 0.0
        self.spin = 0.0
        self.angle = 0.0
        self.centre = (0.0, 0.0)

    @property
    def diving(self):
        """Swirling counts: it hits the ship it meets, like a diver."""
        return self.state in ("swirl", "diving") and not self.dying

    def start_dive(self, player_x):
        if self.state != "formation" or not self.alive or self.dying or not self.formation._may_dive():
            return
        self.state = "swirl"
        self.swirl_t = 0.0
        self.swirl_time = random.uniform(*SWIRL_TIME)
        self.swirl_r = random.uniform(*SWIRL_RADIUS)
        side = 1 if self.formation._aim() >= self.x else -1        # it loops towards the cruise ship
        self.spin = side * 2 * math.pi / SWIRL_TURN
        self.angle = -math.pi / 2                                 # it starts at the top of its first loop
        self.centre = (self.x, self.y + self.swirl_r)
        self.aim_offset = random.uniform(-AIM_SPREAD, AIM_SPREAD)

    def update(self, dt, formation_offset_x=0.0, player_x=0.0):
        if not self.alive:
            return
        if self.dying or self.state not in ("swirl", "diving"):
            super().update(dt, formation_offset_x, player_x)
            return
        self._tick_wings(dt)
        sm = float(getattr(self, "speed_mult", 1.0) or 1.0)
        aim = self.formation._aim() + self.aim_offset
        if self.state == "swirl":
            self.swirl_t += dt
            cx, cy = self.centre
            step = SWIRL_DRIFT * sm * dt
            cx += max(-step, min(step, aim - cx))
            cx = max(self.swirl_r + 24, min(BASE_WIDTH - self.swirl_r - 24, cx))
            cy = min(SWIRL_FLOOR, cy + SWIRL_SINK * sm * dt)
            self.centre = (cx, cy)
            self.angle += self.spin * sm * dt
            self.x = cx + math.cos(self.angle) * self.swirl_r
            self.y = cy + math.sin(self.angle) * self.swirl_r
            if self.swirl_t >= self.swirl_time:
                self.state = "diving"                             # enough loops: it strikes
        else:
            down = ENEMY_DIVE_SPEED * STRIKE_SPEED * sm * dt
            self.y += down
            side = max(-down * STRIKE_SLANT, min(down * STRIKE_SLANT, (aim - self.x) * 1.8 * dt))
            self.x += side + math.sin(self.time * 5.5 + self.formation_index) * 20 * dt
            if self.y > BASE_HEIGHT + 50:
                self.state = "returning"                          # missed: back to its seat, from the top
                self.y = -40.0
        self.x = max(20.0, min(BASE_WIDTH - 20.0, self.x))
        self.rect.center = (int(self.x), int(self.y))


class EscortFormation(EnemyFormation):
    """Blue and khaki birds in formation, replaced for ever (slowly), that swirl then dive at the cruise ship."""

    REFILL_DELAY = REFILL_DELAY

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

    def _swarm_add_bird(self, slot_i, kind, arriving):
        """(EnemyFormation._swarm_add_bird, with an EscortBird.)"""
        x, y, _ = self.swarm["slots"][slot_i]
        e = EscortBird(x, y, self, formation_index=self._swarm_index(), stage=kind)
        e.speed_mult = self.swarm["mult"]
        e.swarm_slot = slot_i
        if arriving:                              # comes in from the top and flies to its seat
            e.state = "returning"
            e.x = x + self.offset_x
            e.y = -40.0
            e.rect.center = (int(e.x), int(e.y))
        self.enemies.append(e)
        return e

    def _swarm_add_gargoyle(self, kind, arriving):
        return None                      # no gargoyles in this mission

    def _aim(self):
        return self.cruise.x + AIM_LEAD

    def divers(self):
        """Birds going for the cruise ship: swirling or diving."""
        return sum(1 for e in self.enemies if e.alive and not e.dying and e.state in ("swirl", "diving"))

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
# The pictures (tools/make_vip_yacht.py): the hull with its transparency, the flame frames in a grid on black, added
# to what is behind them. Loaded once. Without the files, a plain pale hull and no flame.
_ART = {}


def picture():
    """The hull."""
    img = _ART.get("hull")
    if img is None:
        try:
            img = pygame.image.load(asset_path("sprites", "vip_yacht.png")).convert_alpha()
        except Exception:
            log_exc("escort.picture")
            img = pygame.Surface((HULL_W, HULL_H), pygame.SRCALPHA)
            pygame.draw.ellipse(img, (220, 222, 232), pygame.Rect(0, HULL_H // 4, HULL_W, HULL_H // 2))
        _ART["hull"] = img
    return img


def flame_frame(t):
    """The frame of the flame at time `t` (seconds), or None without the file."""
    sheet = _ART.get("flame", False)
    if sheet is False:
        try:
            sheet = pygame.image.load(asset_path("sprites", "vip_yacht_flame.png")).convert()
        except Exception:
            log_exc("escort.flame_frame")
            sheet = None
        _ART["flame"] = sheet
    if sheet is None:
        return None
    i = int(t * FLAME_FPS) % FLAME_FRAMES
    return sheet.subsurface(pygame.Rect((i % FLAME_COLS) * FLAME_W, (i // FLAME_COLS) * FLAME_H, FLAME_W, FLAME_H))


def draw(game, surface):
    form = getattr(game, "formation", None)
    if not isinstance(form, EscortFormation):
        return
    cruise = form.cruise
    if cruise.destroyed or cruise.through:
        return
    pic = cruise.picture_rect()
    frame = flame_frame(cruise.time)
    if frame is not None:
        x, y = pic.x + FLAME_AT[0], pic.y + FLAME_AT[1]
        if cruise.blocked:                       # held up: the reactor idles, a short and dim flame
            w = int(FLAME_W * 0.5)
            frame = pygame.transform.smoothscale(frame, (w, int(FLAME_H * 0.8)))
            frame.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_MULT)
            x, y = x + FLAME_W - w, y + int(FLAME_H * 0.1)
        surface.blit(frame, (x, y), special_flags=pygame.BLEND_RGB_ADD)
    surface.blit(picture(), pic.topleft)


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
