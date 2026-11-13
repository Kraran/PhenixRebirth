"""Sacha, the wingman (TEST - Sacha, story_state.py; the final version will take place in Act 2, he comes back in Act 3).

A young pilot of Phobos station joins the ship for the fight, at the controls of his own ship: an EDF-17 C, an
interceptor of the generation before the Shield that old Wallems put back in flight (straight wings, tip tanks, twin
engines; assets/sprites/sacha/, three pictures: intact, after one hit, after two). The computer flies him, and flies
him well, as a defender first:

  the pilot   every 1/DECIDE_HZ s he weighs the places of the line he could reach (CANDIDATE_STEP px apart): what would hit
              him on the way there and once there (the shots of the birds and their time to come down, the lasers of the
              Guardians and those still charging, the birds diving at their speed), then, far behind, the edges of the
              screen, the pilot's own place (he never flies under him) and a bird above to shoot at. He goes to the
              best one. A good pilot, not a perfect one: he notices a threat REACTION s late, thinks DECIDE_HZ times a
              second and likes to be under a bird, so now and then he is hit. His old ship has no dome and no Phenix
              form: he can only dodge.
  his shots   one at a time like the ship, when a bird is in his column; they hit like the pilot's, the points are his
              (not in the pilot's score)
  his entry  he is not there at the start: ENTER_DELAY s into the first wave he comes in from below, engines boosted
              like the ships between two waves (he arrives where it is safest), and says hello on the radio
  the harm    he cannot die, his ship never blows up: a shot or a laser DAMAGES it, it takes HITS of them; a collision with
              an enemy (a diver, a bird, the hull of a boss) takes it straight to its last level of damage. It blinks
              HIT_GRACE s after a hit, its picture shows the damage, and its two jets (engine_flame "edf17") smoke more
              and more: a grey trail after one hit, a thick one and a coughing engine after two, black smoke after three.
  his retreat LEAVE_DELAY s after the last level of damage he goes back to Phobos: his ship takes off (it climbs, engines
              full), turns about in a half circle toward the side with room, and dives off the bottom of the screen
              (no more shots, nothing touches him). The pilot goes on alone.
  the radio   a line at the top of the screen when he arrives, at each wave and at each hit (RADIO_TIME s), and his
              voice with it through a small radio (assets/sounds/sacha/, sounds.play_radio: a channel of its own)

Between the waves he flies up and comes back with the ship. The state of a mission is `game.wingman` (a Wingman, or None).
"""
import math
import random

import numpy as np
import pygame

import engine_flame
import fonts
import guardian
from enemy import EnemyBullet
from errlog import log_exc
from i18n import t
from player import Player
from settings import BASE_HEIGHT, BASE_WIDTH, ENEMY_BULLET_SPEED, PLAYER_SPEED, asset_path

HITS = 3                         # shots his ship takes; after the last one he goes home (a collision: at once)
HIT_GRACE = 1.6                  # s of blinking after a hit (no shot harms him then; a collision still does)
ENTER_DELAY = 3.0                # s after the start of the first wave, he comes in from below
LEAVE_DELAY = 0.8                # s between the last hit and his retreat to Phobos
TAKEOFF = 0.55                   # the retreat: he climbs, engines full (s)...
TAKEOFF_SPEED = (80.0, 280.0)    # ... from this speed to this one (px / s)
TURN = 0.95                      # ... turns about in a half circle (s) toward the side with room...
DIVE_ACCEL = 700.0               # ... and dives off the bottom of the screen, faster and faster (px / s / s)...
DIVE_TOP_SPEED = 620.0           # ... up to this
START_GAP = 170                  # px: his place at the start, to the right of the pilot (to his left near the right edge)
LINE_Y = BASE_HEIGHT - 95        # the line of the ships
FLY_UP = 420.0                   # px / s: the flight up between two waves (update_play.tick_fly_up)
ARRIVE = 380.0                   # ... and the arrival from below (update_play.tick_arrive)
RADIO_TIME = 3.2                 # s a line of the radio stays on screen
SPRITES = ("edf17c.png", "edf17c_degats1.png", "edf17c_degats2.png")     # assets/sprites/sacha/: intact, 1 hit, 2 hits
JETS = "edf17"                   # his jets (engine_flame.NOZZLES), orange
TURN_SHEET = (120, 280)          # px: the sheet his ship is drawn on to be turned (its middle is the middle of the ship)

# the pilot (the computer)
# (a good pilot, not a perfect one: he sees a shot REACTION s after it is fired, he thinks DECIDE_HZ times a second,
# looks HORIZON s ahead, keeps little margin and likes to be under a bird to shoot it: now and then he is hit)
DECIDE_HZ = 20.0                 # decisions a second
REACTION = 0.85                  # s before he notices a new shot or a Guardian charging (a diver: at once)
HORIZON = 0.7                    # s: what comes later than that is not weighed yet
CANDIDATE_STEP = 14              # px between two places weighed on the line
EDGE = 60                        # px: the places weighed stay this far from the sides
SAFE = 0.0                       # px of margin around his hitbox
NEAR = 12.0                      # px: a near miss still costs a little (he likes room)
HIT_COST = 10.0
BODY_ROOM = 26.0                 # px more room he keeps from an enemy's body (a collision ends his fight at once)...
BODY_COST = 4.0                  # ... and how much more he fears it than a shot
AIM = 1.4                        # how much he wants a bird above him (to shoot it)
# (smooth, like a person at the stick: he keeps to his plan unless the new one is clearly better or he is in danger,
# does not bother with a hop of less than MIN_HOP px, and his ship speeds up and slows down instead of jerking)
SWITCH_GAIN = 0.35               # how much better a new place must be to change his mind (when nothing threatens him)
MIN_HOP = 30.0                   # px: a move this short is not worth it (when nothing threatens him)
HOLD = 0.45                      # s he keeps to a new plan before he thinks of another (when nothing threatens him)
ACCEL = 2600.0                   # px / s / s: how fast his ship speeds up and slows down
EASE = 7.0                       # 1 / s: he eases in as he nears his place (speed = distance x EASE, at most his speed)
PILOT_ROOM = 170.0               # px: he does not fly under (or over) the pilot
SHOOT_COLUMN = 24                # px: a bird this close to his column is shot at
# BONUS FINAL - Nuée (src/swarm_bonus.py): the ace (a sharper eye than in the story missions) and the way back
ACE = {"reaction": 0.55, "horizon": 0.9, "safe": 3.0, "aim": 1.15}
COMEBACK = 20.0                  # s after his retreat to Phobos, he comes back repaired (BONUS FINAL - Nuée, the computer)


_PICTURES = []


def pictures():
    """The three pictures of his ship (intact, after one hit, after two), loaded once."""
    if not _PICTURES:
        for name in SPRITES:
            img = pygame.image.load(asset_path("sprites", "sacha", name))
            try:
                img = img.convert_alpha()
            except pygame.error:
                pass
            _PICTURES.append(img)
    return _PICTURES


def dress_edf17(s, game=None):
    """Give a ship (a Player) the look and the build of the EDF-17 C: its picture, its orange jets, no dome, no Phenix
    form, the speed of the arcade ship, immune to the walls."""
    s.image = pictures()[0]
    s._white_image = None
    s.palette = "gold"               # (the orange of his jets, the tip of his shots)
    s._engine_plan = lambda: (JETS, list(zip(engine_flame.NOZZLES[JETS]["xs"], engine_flame.NOZZLES[JETS]["ys"])), 1.0)
    engine_flame.prepare(JETS, "gold")
    s.sounds = getattr(game, "sounds", None)
    s.speed = PLAYER_SPEED           # Wallems has his old ship in fine order: the speed of the arcade ship
    s.infinite_lives = False
    s.electric_immune = True         # (he never flies into the walls; if he did, they would not stop him)
    s.adventure_dome = False         # (no dome, no Phenix form)
    s.phenix_gauge = 0
    s.phenix_cooldown = 9999.0
    s.no_gauge = True                # (the HUD shows no gauge for it)
    s.vertical_range = None
    s.engine_intensity = 1.0
    return s


class Wingman:
    def __init__(self, game, name="sacha", control="ai", look="edf17", ace=False, comeback=False, ship=None,
                 loadout=None, binding=None, tag=None):
        """`control`: "ai" (the computer), "human" (a second player, `binding` = (scheme, pad)) or "skin" (`ship` is the
        pilot's own ship, flown by the player: only its damage, its pictures and its smoke are handled here). `look`:
        "edf17" (Sacha's EDF-17 C, three hits) or "hull" (the pilot's own hull from the workshop, `loadout`, flown by the
        computer: its lives are its hits). `ace`: the sharper computer of BONUS FINAL - Nuée; `comeback`: after his retreat
        he comes back repaired (COMEBACK s). `tag`: the name under the ship (default his)."""
        self.name = name
        self.control = control
        self.look = look
        self.comeback = bool(comeback)
        self.back_in = COMEBACK
        self.binding = binding or ("kb2", None)
        self.tag_text = tag
        params = ACE if ace else {"reaction": REACTION, "horizon": HORIZON, "safe": SAFE, "aim": AIM}
        self.reaction, self.horizon, self.safe, self.aim = (params["reaction"], params["horizon"], params["safe"],
                                                             params["aim"])
        self.max_hits = HITS
        self.pictures = pictures()
        pilot = game.player
        x = pilot.x + START_GAP
        if x > BASE_WIDTH - EDGE - 40:
            x = pilot.x - START_GAP
        if ship is not None:
            self.ship = ship                 # (the pilot's own ship: "skin")
        elif look == "hull":
            lo = loadout or {}
            self.ship = Player(x, BASE_HEIGHT + 140, ship_id=lo.get("ship_id") or "shield", tint=lo.get("tint") or "red")
            self.ship.speed = PLAYER_SPEED * (int(lo.get("speed_pct") or 40) / 100.0)
            self.ship.sounds = getattr(game, "sounds", None)
            self.ship.infinite_lives = False
            self.ship.electric_immune = True
            self.ship.adventure_dome = False
            self.ship.phenix_gauge = 0
            self.ship.phenix_cooldown = 9999.0
            self.max_hits = max(1, int(lo.get("lives") or 1))
        else:
            # (a Player for the flight, the hitbox and the shots; the look is his own: the picture and the jets of the
            # EDF-17)
            self.ship = dress_edf17(Player(x, BASE_HEIGHT + 140, ship_id="phoenix", tint="gold"), game)
        s = self.ship
        if control != "skin":
            s.pid = 2
            s.wingman = True                 # (game._add_score: his points are his)
            s.score = 0
            s.lives = 99                     # (never used: his ship is only damaged, see damage)
            s.autofire = True
            s.rumble_level = 0               # (the pad is the pilot's)
        self.hits = 0
        # "wait" (not there yet), "enter" (coming in from below), "fight", "hurt" (at the last level of damage),
        # "leave" (the retreat to Phobos), "gone"
        self.state = "wait"
        self.enter_in = ENTER_DELAY
        self.leave_in = 0.0
        self.leave_t = 0.0
        self.leave_speed = 0.0
        self.turn_dir = 1.0              # +1: the half turn to the left (counterclockwise), -1: to the right
        self.angle = 0.0                 # degrees, counterclockwise: 0 the nose up, 180 the nose down (the retreat)
        self.noticed = {}                # id(threat) -> the time he first saw it (REACTION)
        self.clock = 0.0
        self.last_transition = None
        self.greeted = False
        self.target_x = s.x
        self.decide_in = 0.0
        self.vel = 0.0                   # px / s: his speed along the line (eased, see ACCEL / EASE)
        self.hold = 0.0                  # s left before a new plan is allowed (HOLD)
        self.danger = False              # something would hit him where he goes
        self.cough = 0.0                 # s left of a cough of a damaged engine (the jets die down)
        self.cough_in = 1.0
        self.seen = {}                   # id(enemy) -> (x, y, time) when he last looked: the speed of the divers
        self.smoke = []                  # [x, y, vx, vy, age, life, size, grey]
        self.sparks = []                 # [x, y, vx, vy, age]
        self.smoke_t = 0.0
        self.radio = None                # (text key, time left)
        self.radio_held = False          # his voice is held (the game is paused)
        if control in ("human", "skin") or look == "hull":
            self.enter_in = 0.0              # (a player's ship, or the pilot's: there from the start)
        if control == "skin":
            self.state = "fight"

    # --- what he is ----------------------------------------------------------------------------------------------
    def flying(self):
        return self.state in ("fight", "hurt")

    def in_play(self):
        """Still in the fight, or still to come (not destroyed, not gone for good)."""
        return self.state not in ("gone", "dead")

    def talks(self):
        """Sacha flown by the computer speaks on the radio (a player, or the pilot's ship, does not)."""
        return self.control == "ai" and self.look == "edf17"

    def targetable(self, game):
        s = self.ship
        return (self.flying() and s.alive and not s.dying and game.stage_transition is None
                and s.y <= LINE_Y + 40)

    def say(self, key):
        """A line on the radio: its words at the top of the screen, his voice through the radio (sounds.play_radio)."""
        if not self.talks():
            return
        self.radio = (key, RADIO_TIME)
        snd = getattr(self.ship, "sounds", None)
        if snd is not None:
            try:
                snd.play_radio(key)
            except Exception:
                log_exc("wingman.say")

    # --- every frame ---------------------------------------------------------------------------------------------
    def update(self, game, dt):
        self._puffs(dt)
        if self.radio is not None:
            key, left = self.radio
            self.radio = (key, left - dt) if left - dt > 0 else None
        s = self.ship
        self.clock += dt
        if self.control == "skin":
            self._skin(dt)
            return
        tr = game.stage_transition
        if self.state == "gone" and self.comeback:
            if tr is None:
                self.back_in -= dt
            if self.back_in <= 0:
                self._repair()                                    # he comes back, his ship repaired
            return
        if self.state in ("gone", "dead"):
            return
        if self.state == "wait":
            self._wait(game, dt, tr)
            return
        if self.state == "enter":
            if self._enter(game, dt, tr):
                return
        if self.look == "edf17":
            self._smoke_more(dt)
        if self.state == "leave":
            self._fly_home(dt)
            return
        if self.state == "hurt":
            self.leave_in -= dt
            if self.leave_in <= 0:
                self.state = "leave"
                self.leave_t = 0.0
                self.leave_speed = TAKEOFF_SPEED[0]
                self.turn_dir = -1.0 if s.x < BASE_WIDTH / 2 else 1.0     # (the half turn goes where there is room)
                s.shots.clear()
                s.invulnerable = 0.0
                return
        if tr == "fly_up":
            s.shots.clear()
            s.y -= FLY_UP * dt
            s.engine_intensity = 1.0
            s.boost_engines(dt, True)
            self.last_transition = tr
            return
        if tr == "arrive":
            if self.last_transition != "arrive":
                s.y = BASE_HEIGHT + 60              # (the ships have just left the top: they come back from below)
                s.shots.clear()
                if s.is_phenix:
                    s.end_phenix()
            was = s.y
            s.y = max(LINE_Y, s.y - ARRIVE * dt)
            if was > LINE_Y >= s.y:
                self._dust(game)                     # (he has arrived with the ships: the dust, like theirs)
                self.vel = 0.0
                self.target_x = float(s.x)
            s.engine_intensity = 1.0
            s.boost_engines(dt, False)
            s.rect.center = (int(s.x), int(s.y))
            self.last_transition = tr
            return
        if self.last_transition == "arrive":
            wave = int((getattr(game, "adventure", None) or {}).get("wave_i", 0) or 0)
            if wave > 0 and self.state == "fight" and (self.radio is None or self.radio[0] == "wingman_wave"):
                self.say("wingman_wave")
        self.last_transition = tr
        if tr is not None:
            return                                   # (the outro of a boss...: he waits)
        if s.y > LINE_Y:
            s.y = max(LINE_Y, s.y - ARRIVE * dt)
        try:
            keys = pygame.key.get_pressed()
        except Exception:
            keys = None
        if self.control == "human":
            scheme, joy = self.binding
            s.input_scheme = scheme
            s.pad_slot = 0
            pads = getattr(game, "pads", None)
            if joy is not None and pads is not None:
                try:
                    s.pad_slot = max(0, pads.index_of(joy))
                except Exception:
                    s.pad_slot = 0
            s.rumble_level = int(getattr(game, "rumble_level", 3))
            s.autofire = bool(getattr(game, "autofire", True))
            s.update(dt, keys, "gamepad" if scheme == "pad" else "keyboard", joy,
                     allow_shoot=float(getattr(game, "input_grace", 0.0) or 0.0) <= 0)
            if s.y > LINE_Y and s.vertical_range is None:
                s.y = LINE_Y
        else:
            move, shoot = self._pilot(game, dt)
            s.update(dt, keys, "keyboard", None, allow_shoot=True, ai_move=move, ai_shoot=shoot)
        s.phenix_gauge = 0                           # (his old ship has no Phenix form)
        s.phenix_cooldown = 9999.0
        if self.look == "edf17":
            self._engines(dt)

    def _wait(self, game, dt, tr):
        """Not there yet: ENTER_DELAY s into the first wave he comes in (or with the ships, if the wave was over first)."""
        s = self.ship
        s.y = BASE_HEIGHT + 140
        if tr is None:
            self.enter_in -= dt
        wave = int((getattr(game, "adventure", None) or {}).get("wave_i", 0) or 0)
        if (tr == "arrive" and wave > 0) or (tr is None and self.enter_in <= 0):
            try:
                s.y = LINE_Y
                if self.control == "ai":
                    self._decide(game, dt, everything=True)          # he comes in where it is safest
                    s.x = max(EDGE, min(BASE_WIDTH - EDGE, self.target_x))
            except Exception:
                log_exc("wingman._wait")
            s.y = BASE_HEIGHT + 60
            s.engine_burst = 1.0
            self.state = "enter"
        self.last_transition = tr

    def _enter(self, game, dt, tr):
        """Coming in from below, engines boosted (like the ships between two waves). True while he is on his way."""
        s = self.ship
        if tr == "fly_up":
            self.state = "fight"                                 # (the wave is over already: he flies up with the ships)
            return False
        s.y = max(LINE_Y, s.y - ARRIVE * dt)
        s.engine_intensity = 1.0
        s.boost_engines(dt, s.y > LINE_Y + 40)
        s.engine_time += dt
        s.rect.center = (int(s.x), int(s.y))
        self.last_transition = tr
        if s.y <= LINE_Y:
            self.state = "fight"
            self.target_x = float(s.x)
            self.vel = 0.0
            self._dust(game)
            if not self.greeted:
                self.greeted = True
                self.say("wingman_hello")
            return False
        return True

    def _dust(self, game):
        """The landing puff of the ships at the end of their arrival (update_play.tick_arrive), under his ship."""
        s = self.ship
        try:
            feet = s.y + float(getattr(s, "height", 90) or 90) * 0.48
            game.explosions.append(game._boom(s.x - 18, feet, kind="dust"))
            game.explosions.append(game._boom(s.x + 18, feet, kind="dust"))
        except Exception:
            log_exc("wingman._dust")

    def _fly_home(self, dt):
        """The retreat to Phobos: he takes off (climbs, engines full), turns about in a half circle, dives off the bottom."""
        s = self.ship
        self.leave_t += dt
        t = self.leave_t
        if t < TAKEOFF:
            k = t / TAKEOFF
            self.leave_speed = TAKEOFF_SPEED[0] + (TAKEOFF_SPEED[1] - TAKEOFF_SPEED[0]) * k
            self.angle = 0.0
            s.boost_engines(dt, True)
        elif t < TAKEOFF + TURN:
            self.leave_speed = TAKEOFF_SPEED[1]
            self.angle = self.turn_dir * 180.0 * (t - TAKEOFF) / TURN
            s.boost_engines(dt, False)
        else:
            self.angle = self.turn_dir * 180.0
            self.leave_speed = min(DIVE_TOP_SPEED, self.leave_speed + DIVE_ACCEL * dt)
            s.boost_engines(dt, True)
        hx, hy = self._heading()
        s.x += hx * self.leave_speed * dt
        s.y += hy * self.leave_speed * dt
        s.engine_intensity = 1.0
        s.engine_time += dt
        self._engines(dt)
        s.invulnerable = 0.0
        s.rect.center = (int(s.x), int(s.y))
        if t > TAKEOFF + TURN and s.y > BASE_HEIGHT + 140:
            self.state = "gone"

    def _heading(self):
        """Where his nose points (a unit vector on the screen)."""
        a = math.radians(self.angle)
        return -math.sin(a), -math.cos(a)

    def _turned(self, x, y):
        """A point of the ship (from its middle, nose up) on the screen, the ship turned by self.angle."""
        a = math.radians(self.angle)
        return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)

    # --- the harm ------------------------------------------------------------------------------------------------
    def damage(self, game, why="shot"):
        """A hit on his ship (`why`: "shot", "laser", "crash", "hull"). True when it counted. A collision ("crash", "hull")
        takes his ship straight to its last level of damage, even while it blinks."""
        s = self.ship
        if self.control != "ai" or self.look == "hull":
            return self._hit(game, why)              # (a player's EDF-17 C, or the pilot's ship flown by the computer)
        crash = why in ("crash", "hull")
        if not self.flying() or self.hits >= HITS or (s.invulnerable > 0 and not crash):
            return False
        self.hits = HITS if crash else self.hits + 1
        s.invulnerable = HIT_GRACE
        s.shield_flash = 1
        for _ in range(16):
            self._spark(s.x + random.uniform(-14, 14), s.y + random.uniform(-10, 10))
        try:
            game.explosions.append(game._boom(s.x + random.uniform(-10, 10), s.y - 4, kind="enemy"))
            game.sounds.play("explosion", volume=0.55, x=s.x)
            game.shake_amount = max(float(getattr(game, "shake_amount", 0.0) or 0.0), 6.0)
        except Exception:
            log_exc("wingman.damage")
        s.image = self.pictures[min(self.hits, len(self.pictures) - 1)]
        s._white_image = None
        self.say("wingman_hit_%d" % min(self.hits, HITS))
        if self.hits >= HITS:
            self.state = "hurt"
            self.leave_in = LEAVE_DELAY
        return True

    def _hit(self, game, why):
        """A hit on a ship that can be destroyed (BONUS FINAL - Nuée): a player's EDF-17 C takes three, the pilot's ship
        flown by the computer as many as its lives; a collision is one hit like a shot; the last one destroys it."""
        s = self.ship
        if not self.flying() or self.hits >= self.max_hits or s.invulnerable > 0:
            return False
        self.hits += 1
        s.invulnerable = HIT_GRACE
        s.shield_flash = 1
        last = self.hits >= self.max_hits
        try:
            if last:
                game._ship_boom(s, "gameover")
                game.sounds.play("explosion_big", x=s.x)
                game.shake_amount = max(float(getattr(game, "shake_amount", 0.0) or 0.0), 18.0)
            else:
                game.explosions.append(game._boom(s.x + random.uniform(-10, 10), s.y - 4, kind="enemy"))
                game.sounds.play("explosion", volume=0.55, x=s.x)
                game.shake_amount = max(float(getattr(game, "shake_amount", 0.0) or 0.0), 6.0)
        except Exception:
            log_exc("wingman._hit")
        if self.look == "edf17":
            for _ in range(16):
                self._spark(s.x + random.uniform(-14, 14), s.y + random.uniform(-10, 10))
            s.image = self.pictures[min(self.hits, len(self.pictures) - 1)]
            s._white_image = None
        if last:
            self.state = "dead"
            s.alive = False
            s.shots.clear()
        return True

    def _repair(self):
        """BONUS FINAL - Nuée: back from Phobos, his ship repaired; he comes in from below again."""
        s = self.ship
        self.hits = 0
        s.image = self.pictures[0]
        s._white_image = None
        s.alive = True
        s.dying = False
        s.invulnerable = 0.0
        s.shots.clear()
        self.angle = 0.0
        self.state = "wait"
        self.enter_in = 0.0
        self.back_in = COMEBACK
        self.greeted = False
        self.cough = 0.0
        self.target_x = float(s.x)
        self.vel = 0.0

    def _skin(self, dt):
        """The pilot's ship is the EDF-17 C (BONUS FINAL - Nuée, Sacha's ship flown by the player): its picture follows its
        damage (its lives: three), its jets smoke more and more, its engines cough."""
        s = self.ship
        if s.alive and not s.dying:
            hits = max(0, min(HITS - 1, HITS - int(s.lives)))
        else:
            hits = HITS
        if hits != self.hits:
            self.hits = hits
            s.image = self.pictures[min(hits, len(self.pictures) - 1)]
            s._white_image = None
        s.phenix_gauge = 0
        s.phenix_cooldown = 9999.0
        if s.alive and not s.dying:
            self._smoke_more(dt)
            self._engines(dt)

    # --- the computer at the controls ----------------------------------------------------------------------------
    def _speed(self):
        s = self.ship
        mult = 1.0
        if s.slowdown_timer > 0:
            mult *= s.SLOWDOWN_FACTOR
        return float(s.speed) * mult

    def _threats(self, game, dt, react=True):
        """What may hit him in the next HORIZON s: [(x, vx, t0, t1, half width, kind)], kind "shot", "laser", "body"."""
        s = self.ship
        box = s.get_hitbox()
        top, bottom = box.top, box.bottom
        out = []

        now = self.clock
        noticed = {}

        def seen_long_enough(key):
            """He notices a threat REACTION s after it shows up."""
            first = self.noticed.get(key, now)
            noticed[key] = first
            return not react or now - first >= self.reaction

        def falling(rect, vy, vx, kind, extra=0.0):
            if vy <= 1:
                return
            t0 = (top - rect.bottom) / vy
            t1 = (bottom - rect.top) / vy + extra
            if t1 < 0 or t0 > self.horizon:
                return
            out.append((float(rect.centerx), float(vx), max(0.0, t0), t1, rect.width / 2.0, kind))

        shots = list(getattr(game.formation, "bullets", None) or [])
        boss = getattr(game, "boss_saucer", None)
        if boss is not None and getattr(boss, "alive", False):
            shots += list(getattr(boss, "bullets", None) or [])
        for b in shots:
            if not getattr(b, "alive", False) or not seen_long_enough(id(b)):
                continue
            try:
                r = b.get_hitbox()
            except Exception:
                continue
            if isinstance(b, guardian.FireLaser):
                falling(r, guardian.LASER_SPEED, 0.0, "laser", guardian.LASER_LENGTH / guardian.LASER_SPEED)
            else:
                vy = float(getattr(b, "vy", ENEMY_BULLET_SPEED if isinstance(b, EnemyBullet) else ENEMY_BULLET_SPEED))
                falling(r, vy, float(getattr(b, "vx", 0.0) or 0.0), "shot")
        sq = guardian.squad(game)
        if sq is not None:                                  # a Guardian charging: its laser is coming down there
            for g in sq.guardians:
                if not g.alive or getattr(g, "dying", False) or not getattr(g, "charge", 0):
                    continue
                if not seen_long_enough(("charge", id(g))):
                    continue
                wait = max(0.0, guardian.CHARGE_SECONDS - float(g.charge))
                t0 = wait + max(0.0, top - g.y) / guardian.LASER_SPEED
                if t0 > self.horizon:
                    continue
                t1 = t0 + (guardian.LASER_LENGTH + box.height) / guardian.LASER_SPEED + 0.15
                scale = float(getattr(g, "scale", 1.0) or 1.0)
                for p in g.charge_points():
                    out.append((float(g.x) + (p - 80) * scale, 0.0, t0, t1, guardian.LASER_WIDTH / 2.0 + 4.0, "laser"))
        seen = {}
        for e in guardian.targets(game):
            try:
                r = e.get_hitbox()
            except Exception:
                continue
            key = id(e)
            seen[key] = (float(e.x), float(e.y), now)
            last = self.seen.get(key)
            if last is not None and now - last[2] > 1e-4:          # (its speed since he last looked at it)
                vx, vy = (e.x - last[0]) / (now - last[2]), (e.y - last[1]) / (now - last[2])
            else:
                vx, vy = 0.0, 0.0
            if getattr(e, "diving", False) and vy > 40:
                falling(r, vy, vx, "body")                   # (a diver he sees at once: it is big, and it hurts)
                if out and out[-1][5] == "body":
                    x, vx_, t0, t1, hw, kind = out[-1]
                    out[-1] = (x, vx_, t0, t1, hw + BODY_ROOM, kind)     # (a diver may turn: more room)
            elif r.bottom > top - 90:
                out.append((float(r.centerx), float(vx), 0.0, 0.8, r.width / 2.0 + BODY_ROOM, "body"))   # low: keep away
        self.seen = seen
        self.noticed = noticed
        return out

    def _decide(self, game, dt, everything=False):
        """Pick the place to go (self.target_x). `everything`: every threat at once, no reaction time (his entry)."""
        s = self.ship
        px = float(s.x)
        half = s.get_hitbox().width / 2.0
        xs = np.arange(EDGE, BASE_WIDTH - EDGE + 1, CANDIDATE_STEP, dtype=np.float64)
        xs = np.append(xs, px)
        v = self._speed()
        d = xs - px
        ad = np.abs(d)
        sgn = np.sign(d)

        def pos(tt):
            return px + sgn * np.minimum(ad, v * tt)

        hit = np.zeros_like(xs)
        for x, vx, t0, t1, hw, kind in self._threats(game, dt, react=not everything):
            a, b = pos(t0), pos(t1)
            lo, hi = np.minimum(a, b), np.maximum(a, b)
            tx0, tx1 = x + vx * t0, x + vx * t1
            tlo, thi = min(tx0, tx1), max(tx0, tx1)
            gap = np.maximum(0.0, np.maximum(lo - thi, tlo - hi))
            reach = hw + half + self.safe
            weight = 1.0 / (0.25 + t0)
            hits = gap < reach
            near = (~hits) & (gap < reach + NEAR)
            hit += np.where(hits, HIT_COST * weight * (BODY_COST if kind == "body" else 1.0), 0.0)
            hit += np.where(near, 0.6 * (1.0 - (gap - reach) / NEAR) * weight, 0.0)
        cost = hit + 0.0012 * ad
        room = np.minimum(xs - EDGE, BASE_WIDTH - EDGE - xs)
        cost += np.where(room < 50, (50 - room) / 50.0, 0.0)          # the walls are not for him
        pilot = getattr(game, "player", None)
        if pilot is not None and pilot.alive and not pilot.dying:
            gap = np.abs(xs - float(pilot.x))
            cost += np.where(gap < PILOT_ROOM, 0.9 * (1.0 - gap / PILOT_ROOM), 0.0)
        cols = [float(e.x) for e in guardian.targets(game) if float(e.y) < LINE_Y - 90]
        if cols:
            aim = np.min(np.abs(xs[:, None] - np.array(cols)[None, :]), axis=1)
            cost += self.aim * np.minimum(aim, 260.0) / 260.0            # a bird above, to shoot at
        best = int(np.argmin(cost))
        here = int(np.argmin(np.abs(xs - self.target_x)))             # (his plan as it stands)
        self.danger = bool(hit[here] >= HIT_COST * 0.5)
        if not everything and not self.danger:
            if (self.hold > 0 or cost[here] - cost[best] < SWITCH_GAIN
                    or abs(float(xs[best]) - self.target_x) < MIN_HOP):
                return                                                  # he keeps to his plan
        if abs(float(xs[best]) - self.target_x) >= 1.0:
            self.hold = HOLD
        self.target_x = float(xs[best])

    def _pilot(self, game, dt):
        """(move, shoot) for this frame."""
        s = self.ship
        self.hold = max(0.0, self.hold - dt)
        self.decide_in -= dt
        if self.decide_in <= 0:
            self.decide_in = 1.0 / DECIDE_HZ
            try:
                self._decide(game, dt)
            except Exception:
                log_exc("wingman._pilot")
                self.target_x = float(s.x)
        v = self._speed()
        err = self.target_x - float(s.x)
        move = 0.0
        if v > 0:
            want = max(-v, min(v, err * EASE))                      # eases in as he nears his place
            if abs(err) < 1.0:
                want = 0.0
            step = ACCEL * max(dt, 1e-3) * (1.6 if self.danger else 1.0)   # (a bit sharper when he must dodge)
            self.vel += max(-step, min(step, want - self.vel))
            if abs(err) < 1.0 and abs(self.vel) < 25.0:
                self.vel = 0.0
            move = max(-1.0, min(1.0, self.vel / v))
        else:
            self.vel = 0.0
        shoot = False
        if self.state == "fight" and not s.own_shots():
            for e in guardian.targets(game):
                if abs(float(e.x) - float(s.x)) < SHOOT_COLUMN and float(e.y) < s.y - 60:
                    shoot = True
                    break
        return move, shoot

    # --- smoke and sparks ----------------------------------------------------------------------------------------
    def _spark(self, x, y):
        a = random.uniform(0, 2 * math.pi)
        sp = random.uniform(80, 240)
        self.sparks.append([x, y, math.cos(a) * sp, math.sin(a) * sp, 0.0])

    def _engines(self, dt):
        """A damaged engine coughs: after two hits (and more after three) the jets die down now and then, for a moment."""
        s = self.ship
        if self.cough > 0:
            self.cough -= dt
            s.engine_intensity = min(s.engine_intensity, 0.25)
            return
        if self.hits < 2:
            return
        self.cough_in -= dt
        if self.cough_in <= 0:
            bad = self.hits >= 3
            self.cough = random.uniform(0.06, 0.16 if bad else 0.11)
            self.cough_in = random.uniform(0.35, 0.9) if bad else random.uniform(0.9, 2.2)
            if not (-60 < s.y < BASE_HEIGHT + 40):
                return
            for _ in range(3 if bad else 2):                      # a puff of black smoke and a spark with it
                self._puff_at(*random.choice(self._nozzles()), dark=True)
            if random.random() < 0.6:
                x, y = random.choice(self._nozzles())
                self._spark(x, y)

    def _nozzles(self):
        """Where his two jets come out, on the screen."""
        s = self.ship
        spec = engine_flame.NOZZLES[JETS]
        out = []
        for nx, ny in zip(spec["xs"], spec["ys"]):
            tx, ty = self._turned(nx, ny)
            out.append((s.x + tx, s.y + ty))
        return out

    def _puff_at(self, x, y, dark=False):
        hits = max(1, min(3, self.hits))
        grey = 55 if dark else {1: 165, 2: 110}.get(hits, 60)
        size = {1: 3.2, 2: 4.6}.get(hits, 6.0) * (1.25 if dark else 1.0)
        thrust = max(0.3, float(self.ship.engine_intensity or 0.0))
        back = 70.0 + 90.0 * thrust                                # blown back by the jet
        if self.state == "leave":
            back = 40.0
        ex, ey = self._turned(0.0, 1.0)                            # the way the jets blow
        off = 6 + 10 * thrust + random.uniform(0, 4)
        side = random.uniform(-9, 9)
        self.smoke.append([x + random.uniform(-1.5, 1.5) + ex * off, y + ey * off,
                           ex * back - ey * side, ey * back + ex * side + random.uniform(-15, 15) * ey, 0.0,
                           random.uniform(0.5, 0.8) + 0.18 * hits, size * random.uniform(0.8, 1.2), grey + random.randint(-12, 12)])

    def _smoke_more(self, dt):
        """The jets of the damaged ship smoke, more and more: a thin grey trail after one hit, a thick one after two,
        black smoke after three (and while he goes home)."""
        if self.hits <= 0:
            return
        s = self.ship
        if s.y > BASE_HEIGHT + 60 or s.y < -60:
            return
        every = {1: 0.09, 2: 0.045}.get(self.hits, 0.022)
        self.smoke_t -= dt
        while self.smoke_t <= 0:
            self.smoke_t += every
            for x, y in self._nozzles():
                if self.hits == 1 and random.random() < 0.5:
                    continue                                       # (one hit: a thin trail, now one jet, now the other)
                self._puff_at(x, y)
            if self.hits >= 3 and random.random() < 0.15:
                self._spark(s.x + random.uniform(-14, 14), s.y + random.uniform(-6, 10))

    def _puffs(self, dt):
        for p in self.smoke:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] += dt
        self.smoke = [p for p in self.smoke if p[4] < p[5]]
        for sp in self.sparks:
            sp[0] += sp[2] * dt
            sp[1] += sp[3] * dt
            sp[4] += dt
        self.sparks = [sp for sp in self.sparks if sp[4] < 0.28]

    # --- drawing -------------------------------------------------------------------------------------------------
    def draw(self, surface, game):
        for p in self.smoke:
            k = p[4] / p[5]
            r = max(2, int(p[6] * (1 + 1.6 * k)))
            surface.blit(_puff(r, int(p[7]), int(170 * (1 - k)) // 17 * 17), (int(p[0] - r - 1), int(p[1] - r - 1)))
        for sp in self.sparks:
            k = sp[4] / 0.28
            colour = (255, 240, 170) if k < 0.5 else (255, 160, 60)
            pygame.draw.line(surface, colour, (int(sp[0]), int(sp[1])),
                             (int(sp[0] - sp[2] * 0.02), int(sp[1] - sp[3] * 0.02)), 1)
        if self.state in ("gone", "dead") or self.control == "skin":
            return                                       # (the pilot's own ship is drawn by the game)
        s = self.ship
        if s.y < -120 or s.y > BASE_HEIGHT + 120 or self.state == "wait":
            return
        if self.state == "leave":
            self._draw_turned(surface)
            return
        s.draw(surface)
        if self.flying() and game.stage_transition is None:
            tag = _tag(game, self.tag_text)
            if tag is not None and not (s.invulnerable > 0 and int(s.invulnerable * 12) % 2 == 0):
                surface.blit(tag, (int(s.x - tag.get_width() / 2), int(s.y + s.height / 2 + 2)))

    def _draw_turned(self, surface):
        """The retreat: his ship and its jets, turned by self.angle (drawn upright on a sheet, then turned)."""
        s = self.ship
        sheet = pygame.Surface((TURN_SHEET[0], TURN_SHEET[1]), pygame.SRCALPHA)
        cx, cy = TURN_SHEET[0] // 2, TURN_SHEET[1] // 2
        spec = engine_flame.NOZZLES[JETS]
        thrust = max(engine_flame.SHOW_FROM, float(s.engine_intensity or 0.0))
        for i, (nx, ny) in enumerate(zip(spec["xs"], spec["ys"])):
            engine_flame.draw(sheet, JETS, "gold", cx + nx, cy + ny, thrust, s.engine_time, engine=i,
                              burst=s.engine_burst)
        sheet.blit(s.image, (cx - s.image.get_width() // 2, cy - s.image.get_height() // 2))
        if abs(self.angle) > 0.5:
            sheet = pygame.transform.rotozoom(sheet, self.angle, 1.0)
        surface.blit(sheet, (int(s.x - sheet.get_width() / 2), int(s.y - sheet.get_height() / 2)))

    def banner(self, surface, game):
        paused = bool(getattr(game, "paused", False))
        if paused != self.radio_held:                    # (his voice holds while the game is paused)
            self.radio_held = paused
            snd = getattr(self.ship, "sounds", None)
            if snd is not None:
                try:
                    snd.hold_radio(paused)
                except Exception:
                    log_exc("wingman.banner")
        if self.radio is None:
            return
        key, left = self.radio
        try:
            img = _radio_plate(game.text_cache.get(game.font, t(key), (150, 235, 170)))
        except Exception:
            log_exc("wingman.banner")
            return
        alpha = max(0, min(255, int(255 * min(1.0, left / 0.5))))
        if alpha < 255:
            img = img.copy()
            img.set_alpha(alpha)
        surface.blit(img, (BASE_WIDTH // 2 - img.get_width() // 2, 136))


_PUFFS = {}
_TAG = {}
_PLATES = {}


def _puff(r, grey, alpha):
    key = (r, grey, alpha)
    img = _PUFFS.get(key)
    if img is None:
        if len(_PUFFS) > 600:
            _PUFFS.clear()
        img = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(img, (grey, grey, min(255, grey + 8), alpha), (r + 1, r + 1), r)
        _PUFFS[key] = img
    return img


def _radio_plate(text):
    """The line of the radio on a dark translucent band (it stays readable over the birds), made once per line."""
    img = _PLATES.get(text)
    if img is None:
        if len(_PLATES) > 32:
            _PLATES.clear()
        w, h = text.get_width() + 32, text.get_height() + 10
        img = pygame.Surface((w, h), pygame.SRCALPHA)
        img.fill((6, 12, 18, 170))
        pygame.draw.rect(img, (90, 170, 110, 200), img.get_rect(), 1)
        img.blit(text, (16, 5))
        _PLATES[text] = img
    return img


def _tag(game, text=None):
    """His name under his ship (small); `text`: another name (the pilot's, on the ship the computer flies)."""
    try:
        from i18n import get_lang
        key = (get_lang(), text)
        img = _TAG.get(key)
        if img is None:
            font = fonts.text(16)
            img = _TAG[key] = font.render(text or t("wingman_name"), True, (150, 235, 170))
            img.set_alpha(190)
        return img
    except Exception:
        log_exc("wingman._tag")
        return None


# --- the mission ----------------------------------------------------------------------------------------------------
def start(game, spec):
    """At the start of a mission: Sacha when the mission has him (spec "wingman")."""
    game.wingman = None
    try:
        if getattr(game, "sounds", None) is not None:
            game.sounds.stop_radio(0)            # (a line of a mission before must not go on in this one)
    except Exception:
        log_exc("wingman.start")
    if not (spec or {}).get("wingman") or getattr(game, "play_mode", "solo") == "coop":
        return
    try:
        game.wingman = Wingman(game, spec.get("wingman"))
    except Exception:
        log_exc("wingman.start")
        game.wingman = None


def active(game):
    w = getattr(game, "wingman", None)
    return w if w is not None and getattr(game, "adventure", None) and getattr(game, "started", False) else None


def tick(game):
    w = active(game)
    if w is not None:
        try:
            w.update(game, float(game.dt or 0.0))
        except Exception:
            log_exc("wingman.tick")


def shooters(game):
    """His ship, for the shots against the enemies (update_play.player_bullets_vs_enemies), while he fights."""
    w = active(game)
    if w is None or not w.flying() or not w.ship.shots:
        return []
    return [w.ship]


def attacks(game):
    """The enemies against Sacha: the shots, the lasers, the divers and the hull of a boss damage his ship (see
    Wingman.damage); his dome takes the shots and the divers, his Phenix form too (not the lasers)."""
    w = active(game)
    if w is None or w.control == "skin" or not w.targetable(game):
        return
    try:
        _attacks(game, w)
    except Exception:
        log_exc("wingman.attacks")


def _attacks(game, w):
    s = w.ship
    box = s.get_hitbox()
    dome = s.uses_shield and s.is_phenix
    boss = getattr(game, "boss_saucer", None)
    if boss is not None and getattr(boss, "alive", False):
        hull = boss.get_hull_hitbox()
        if hull.width > 0 and box.colliderect(hull):
            w.damage(game, "hull")
        for b in boss.bullets:
            if b.alive and b.get_hitbox().colliderect(box):
                b.alive = False
                if dome:
                    game._shield_absorb(s, *b.get_hitbox().center)
                elif not s.is_phenix:
                    w.damage(game, "shot")
    for b in game.formation.bullets:
        if not b.alive or not b.get_hitbox().colliderect(box):
            continue
        if isinstance(b, guardian.FireLaser):
            w.damage(game, "laser")                     # (it goes through, as it goes through the birds)
            continue
        b.alive = False
        if dome:
            game._shield_absorb(s, *b.get_hitbox().center)
        elif not s.is_phenix:
            w.damage(game, "shot")
    for e in guardian.targets(game):
        if e.get_hitbox().colliderect(box):                # any enemy flying into him (a diver, most of the time)
            try:
                e.kill(flash=False)                     # the bird goes down, worth nothing
            except TypeError:
                e.kill()
                e.alive = False
                e.dying = False
            game.explosions.append(game._boom(e.x, e.y, kind="collision"))
            game.sounds.play("enemy_explosion", x=e.x)
            w.damage(game, "crash")                     # straight to the last level of damage
            break


def draw(game, surface):
    w = active(game)
    if w is not None:
        w.draw(surface, game)


def banner(game, surface):
    w = active(game)
    if w is not None:
        w.banner(surface, game)
