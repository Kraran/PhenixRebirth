"""
Story / Adventure hub — Hangar, Mission map, Mission log.

Arcade loop never imports combat rules from here. This module draws the
pre-run screens and handles their input; the rules and the save data
(hangar, shop, missions, story_N.json) live in story_state.py, which has no
drawing code and is tested on its own. Points earned in a mission are
hangar credits.
"""
import math

import pygame
from settings import BASE_WIDTH, BASE_HEIGHT, asset_path
from i18n import t, get_lang
from errlog import log_exc
import story_state as ss
import bestiary_art
from story_state import MISSIONS, SHOP, log_text   # noqa: F401  (re-exported for the tests)


PANES = ("bestiary", "log", "hangar", "map")
CHEAT_UNLOCK = "UNLK"          # typed on the mission map: play any mission, save nothing
PORTRAIT_H = 124                 # height of a hull portrait in the hangar (the ship select screen uses 168)
GREY_MULT = (80, 80, 90, 160)    # the dimming of the ship select screen for the hull that is not chosen
CHEAT_ACT2 = "2222"            # typed on the mission map: go straight to Act 2, save nothing
LOG_ROWS = 12                  # journal lines shown at once


def _cap_top(font, cy):
    """Top y at which to blit text so its capital letters are centred on `cy`.

    A text surface is taller than its letters (room for accents and descenders),
    so centring the surface makes the letters look too high or too low. This
    centres the capitals instead, the same way for every string of that font.
    """
    try:
        cap = font.metrics("H")[0][3]
    except Exception:
        cap = int(font.get_height() * 0.7)
    return int(round(cy - (font.get_ascent() - cap / 2.0)))


def _wrap(font, text, width):
    """Split text into lines that fit `width` pixels."""
    lines, cur = [], ""
    for word in str(text).split():
        trial = (cur + " " + word).strip()
        if cur and font.size(trial)[0] > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _text(surface, font, text, color, cy, left=None, right=None, centerx=None):
    """Draw one line, vertically centred on `cy`, anchored left, right or centre."""
    img = font.render(text, True, color)
    if left is not None:
        x = left
    elif right is not None:
        x = right - img.get_width()
    else:
        x = centerx - img.get_width() // 2
    surface.blit(img, (x, _cap_top(font, cy)))
    return img


def _text_fit(surface, font, text, color, cy, left, max_w, scale=1.0):
    """A line anchored left, shrunk (never grown) to `scale` and to fit in `max_w` pixels."""
    img = font.render(text, True, color)
    k = min(scale, max_w / img.get_width()) if img.get_width() else 1.0
    k = min(1.0, k)
    if k < 1.0:
        img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k))))
    surface.blit(img, (left, int(cy - (cy - _cap_top(font, cy)) * k)))
    return img


# Intro slides (credits-style scroll over a picture)
INTRO_TEXT_W = 860          # width of the scrolling text
INTRO_SPEED = 46.0          # px per second (about the speed of the credits)
INTRO_FAST = 150.0          # Down held: the text rises faster (same feel as the credits)
INTRO_BACK = 140.0          # Up held: the text goes back down
INTRO_EASE = 8.0            # how quickly the speed follows the keys (soft start and stop)
INTRO_DELAY = 0.8           # the picture shows alone for a moment before the text rises
INTRO_FADE = 0.7            # fade in from black at each slide
INTRO_LOCK = 0.4            # a key pressed right at the start of a slide does not skip it
INTRO_END_Y = BASE_HEIGHT - 96    # where the last line comes to rest


class StoryHub:
    """Three-pane hub. Left = log, center = hangar, right = map."""

    def __init__(self):
        self.slot_no = None            # save slot (1..3) being played; None before one is opened
        self.state = ss.default_state()
        self.screen = "slots"          # slots | delete | name | mode | intro | hub
        self.sel = 0                   # slot cursor on the slot list (0..2)
        self.col = 0                   # 0 = the slot, 1 = its DELETE button
        self.del_yes = False
        self.mode_index = 0            # 0 normal, 1 veteran
        self.entry = None              # NameEntry while typing a pilot name
        self.new_name = ""
        self.msg = ""
        self.summaries = []
        self.pane = "hangar"
        self.zone = "slots"   # slots | shop
        self.shop_index = 0
        self.paint_mode = False        # the paint shop is open (choosing a colour)
        self.paint_choice = 0
        self.map_index = 0
        self.toast = ""
        self._ships = {}               # small pictures (the paint shop)
        self._portraits = {}           # the hangar portraits, as on the ship select screen
        self._greyed = {}              # the same, dimmed (the hull that is not selected)
        self._loaded_img = False
        self.intro_slides = []         # [(picture, text key)] of the intro being shown
        self.intro_index = 0
        self.intro_t = 0.0             # seconds since the current slide appeared
        self.intro_pos = 0.0           # how far the text has risen (px)
        self.intro_speed = 0.0         # current rising speed (px/s), eased
        self.intro_return = "hangar"   # pane to go back to when the intro ends
        self.log_scroll = 0            # first journal line shown (only "watch the intro again" is selectable)
        self.cheat_buf = ""            # last letters typed on the mission map
        self.cheat_unlock = False      # UNLK: every mission can be played, nothing is saved any more
        self.cheat_act2 = False        # ACT2: the save jumped to Act 2, nothing is saved any more
        self.best_index = 0            # cursor in the Bestiary list
        self.anim_t = 0.0              # seconds, drives the Bestiary animation
        self._intro_bg = {}
        self._intro_blocks = {}
        self._intro_mask = None
        self._intro_limit = None

    # --- intro ---
    def start_intro(self, back_to="hangar"):
        """Show the story slides (new adventure, a save that never saw them, or a replay)."""
        self.intro_slides = ss.intro_slides(self.state.get("mode"))
        self.intro_index = 0
        self._reset_slide()
        self.intro_return = back_to
        self.screen = "intro"

    def _reset_slide(self):
        self.intro_t = 0.0
        self.intro_pos = 0.0
        self.intro_speed = 0.0

    def _maybe_intro(self):
        if not ss.intro_seen(self.state):
            self.start_intro()

    def _intro_next(self):
        if self.intro_t < INTRO_LOCK:
            return
        if self.intro_index + 1 < len(self.intro_slides):
            self.intro_index += 1
            self._reset_slide()
        else:
            self._end_intro()

    def _end_intro(self):
        """Last slide done, or skipped: remember it and go to the hangar."""
        ss.mark_intro_seen(self.state)
        self.save()
        self.screen = "hub"
        self.pane = self.intro_return
        self.zone = "slots"
        self.intro_return = "hangar"

    def update(self, dt, scroll=0):
        """Time passes. `scroll` is the speed control of the intro: +1 faster (Down), -1 back (Up)."""
        self.anim_t += max(0.0, min(0.25, float(dt)))
        if self.screen != "intro":
            return
        dt = max(0.0, min(0.25, float(dt)))
        self.intro_t += dt
        if scroll > 0:
            target = INTRO_FAST
        elif scroll < 0:
            target = -INTRO_BACK
        elif self.intro_t >= INTRO_DELAY:
            target = INTRO_SPEED
        else:
            target = 0.0                  # the picture shows alone for a moment
        self.intro_speed += (target - self.intro_speed) * min(1.0, INTRO_EASE * dt)
        self.intro_pos += self.intro_speed * dt
        if self.intro_pos < 0.0:
            self.intro_pos = 0.0
            self.intro_speed = max(0.0, self.intro_speed)
        limit = getattr(self, "_intro_limit", None)
        if limit is not None and self.intro_pos > limit:
            self.intro_pos = limit
            self.intro_speed = min(0.0, self.intro_speed)

    # --- save slots ---
    def open_slots(self):
        """Entry point of the Adventure menu: the list of the 3 save slots."""
        self.screen = "slots"
        self.col = 0
        self.msg = ""
        self.summaries = ss.all_summaries()
        self.sel = max(0, min(ss.SLOT_COUNT - 1, self.sel))

    def open_slot(self, slot_no):
        """Load slot 1..3 and go to its hangar (a missing file starts a fresh one)."""
        state = ss.load_state(ss.story_path(slot_no))
        self.state = state if state is not None else ss.default_state()
        self.slot_no = int(slot_no)
        self.cheat_unlock = False                 # loading a save always starts clean
        self.cheat_act2 = False
        self.cheat_buf = ""
        self.log_scroll = 0
        slots = self.state.get("slots") or []
        cur = int(ss._num(self.state.get("selected_slot"), 0))
        if not (0 <= cur < len(slots) and slots[cur].get("owned")):
            self.state["selected_slot"] = 0       # never rest on a hull the pilot does not own yet
        self.screen = "hub"
        self.pane = "hangar"
        self.zone = "slots"
        self.paint_mode = False
        self.shop_index = 0
        self.map_index = 0
        self.toast = ""

    def save(self):
        if self.slot_no is None or self.cheating:
            return                                # a cheated adventure is never written
        try:
            ss.save_state(ss.story_path(self.slot_no), self.state)
        except Exception:
            log_exc("story.save")

    def _ensure_art(self):
        if self._loaded_img:
            return
        self._loaded_img = True
        mapping = {
            "shield": "sprites/player_ship_shield.png",
            "shield_red": "sprites/player_ship_shield.png",
            "shield_green": "sprites/player_ship_shield_green.png",
            "shield_violet": "sprites/player_ship_shield_violet.png",
            "phoenix": "sprites/player_ship.png",
        }
        for key, rel in mapping.items():
            fp = asset_path(*rel.split("/"))
            try:
                raw = pygame.image.load(fp).convert_alpha()
                self._ships[key] = pygame.transform.smoothscale(raw, (150, 90))
                scale = PORTRAIT_H / max(1, raw.get_height())
                big = pygame.transform.smoothscale(
                    raw, (max(1, int(raw.get_width() * scale)), PORTRAIT_H))
                self._portraits[key] = big
                dim = big.copy()
                dim.fill(GREY_MULT, special_flags=pygame.BLEND_RGBA_MULT)     # same dimming as the ship select
                self._greyed[key] = dim
            except Exception:
                self._ships[key] = None

    def flag(self, name):
        return ss.flag(self.state, name)

    def _slot(self):
        return ss.selected_slot(self.state)

    def loadout(self, force_ship=None):
        """Hull the mission actually launches: the selected one (or the one the mission imposes)."""
        return ss.loadout(self.state, force_ship)

    @property
    def cheating(self):
        """A cheat code is on: nothing is written to the save until it is loaded again."""
        return bool(self.cheat_unlock or self.cheat_act2)

    def missions(self):
        """The missions of the map: those of the current act (every one under the UNLK cheat)."""
        return ss.visible_missions(self.state, self.cheat_unlock)

    def shop_rows(self):
        """Workshop rows of the selected hull."""
        return ss.shop_for(self.state)

    def _mission(self, index=None):
        i = self.map_index if index is None else index
        rows = self.missions()
        if 0 <= i < len(rows):
            return rows[i]
        return None

    def mission_open(self, mission):
        if self.cheat_unlock:
            return bool(mission)
        return ss.mission_open(self.state, mission)

    def mission_playable(self, mission):
        return ss.mission_playable(self.state, mission, cheat=self.cheat_unlock)

    # --- input: every screen answers to the same four calls ---
    def text_input_active(self):
        return self.screen == "name"

    def type_key(self, event):
        """Real keyboard while typing a name. True when the key was used."""
        if self.screen == "hub" and self.pane == "map":
            ch = getattr(event, "unicode", "") or ""
            if ch.isalnum():
                self.feed_cheat(ch)               # the letters still work as menu keys
            return False
        if self.screen != "name" or self.entry is None:
            return False
        if event.key == pygame.K_BACKSPACE:
            self.entry.backspace()
            self.msg = ""
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._submit_name()      # Enter on the real keyboard means "OK"
            return True
        ch = getattr(event, "unicode", "")
        if ch and ch.isprintable():
            self.entry.type_char(ch)
            self.msg = ""
            return True
        return False

    def feed_cheat(self, ch):
        """Secret code typed on the mission map. Returns True when UNLK was just completed."""
        self.cheat_buf = (self.cheat_buf + str(ch).upper())[-max(len(CHEAT_UNLOCK), len(CHEAT_ACT2)):]
        if self.cheat_buf == CHEAT_ACT2:
            self.cheat_buf = ""
            if int(ss._num(self.state.get("act"), 1)) < 2:
                ss.jump_to_act2(self.state)
            self.cheat_act2 = True
            self.map_index = 0                    # the Act 2 map is a different list
            self.toast = t("story_cheat_act2")
            return True
        if self.cheat_buf == CHEAT_UNLOCK and not self.cheat_unlock:
            here = self._mission()
            self.cheat_unlock = True
            self.cheat_buf = ""
            if here is not None:                  # the list now holds every mission: stay on the same one
                ids = [m["id"] for m in self.missions()]
                self.map_index = ids.index(here["id"]) if here["id"] in ids else 0
            self.toast = t("story_cheat_on")
            return True
        return False

    def _submit_name(self):
        if not self.entry.name:
            self.msg = t("story_name_empty")
            return
        self.new_name = self.entry.name
        self.mode_index = 0
        self.screen = "mode"
        self.msg = ""

    def key_delete(self):
        """Delete key on the slot list: ask to delete the slot under the cursor."""
        if self.screen == "slots" and self._summary().get("status") != "missing":
            self.col = 1
            self.confirm()

    def _summary(self):
        if 0 <= self.sel < len(self.summaries):
            return self.summaries[self.sel]
        return {"status": "missing"}

    def nav_h(self, direction):
        if self.screen == "hub":
            return self._hub_nav_h(direction)
        if self.screen == "slots":
            self.msg = ""
            self.col = max(0, min(1, self.col + direction)) if self._summary().get("status") != "missing" else 0
        elif self.screen == "delete":
            self.del_yes = direction > 0
        elif self.screen == "name":
            self.entry.move(1 if direction > 0 else -1, 0)
            self.msg = ""
        elif self.screen == "mode":
            self.mode_index = 1 if direction > 0 else 0

    def nav_v(self, direction):
        if self.screen == "hub":
            return self._hub_nav_v(direction)
        if self.screen == "slots":
            self.msg = ""
            self.sel = max(0, min(ss.SLOT_COUNT - 1, self.sel + direction))
            if self._summary().get("status") == "missing":
                self.col = 0
        elif self.screen == "delete":
            self.del_yes = direction > 0
        elif self.screen == "name":
            self.entry.move(0, 1 if direction > 0 else -1)
        elif self.screen == "mode":
            self.mode_index = 1 if direction > 0 else 0

    def confirm(self):
        """Hub: shop buy, or a launch spec when a map node is confirmed. Other screens: None."""
        if self.screen == "hub":
            if self.paint_mode:
                self._paint_confirm()
                return None
            return self._hub_confirm()
        if self.screen == "slots":
            info = self._summary()
            if self.col == 1 and info.get("status") != "missing":
                self.screen = "delete"
                self.del_yes = False
            elif info.get("status") == "missing":
                self.entry = ss.NameEntry()
                self.screen = "name"
                self.msg = ""
            elif info.get("status") == "damaged":
                self.msg = t("story_slot_damaged_msg")
            elif info.get("fallen"):
                self.msg = t("story_slot_fallen_msg")
            else:
                self.open_slot(self.sel + 1)
                self._maybe_intro()
        elif self.screen == "intro":
            self._intro_next()
        elif self.screen == "delete":
            if self.del_yes:
                ss.delete_slot(self.sel + 1)
                self.open_slots()
            else:
                self.screen = "slots"
        elif self.screen == "name":
            res = self.entry.press()
            if res == "ok":
                self._submit_name()
            elif res == "empty":
                self.msg = t("story_name_empty")
            else:
                self.msg = ""
        elif self.screen == "mode":
            slot = self.sel + 1
            ss.create_slot(slot, self.new_name, ss.MODES[self.mode_index])
            self.open_slot(slot)
            self.start_intro()
        return None

    def back(self):
        """B / Esc. True when handled here; False on the slot list (leave the Adventure)."""
        if self.screen == "hub":
            if self.paint_mode:
                self.paint_mode = False                  # B closes the paint shop, nothing is spent
                return True
            self.open_slots()
        elif self.screen in ("delete", "name"):
            self.screen = "slots"
            self.msg = ""
        elif self.screen == "mode":
            self.screen = "name"
        elif self.screen == "intro":
            self._end_intro()
        else:
            return False
        return True

    # --- hub input ---
    def _hub_nav_h(self, direction):
        """Left / right. Slots when hangar+slots, else change pane."""
        if self.paint_mode:
            n = len(ss.PAINT_TINTS)
            self.paint_choice = (self.paint_choice + direction) % n
            return
        if self.pane == "hangar" and self.zone == "slots":
            slots = self.state["slots"]
            cur = int(self.state.get("selected_slot", 0))
            nxt = max(0, min(len(slots) - 1, cur + direction))
            if nxt != cur and slots[nxt].get("owned"):
                self.state["selected_slot"] = nxt
                return
        idx = PANES.index(self.pane)
        self.paint_mode = False
        self.pane = PANES[max(0, min(len(PANES) - 1, idx + direction))]
        self.zone = "slots"
        self.toast = ""

    def log_entries(self):
        """The journal as a list: first the story intro (always there), then what happened."""
        return ss.journal_entries(self.state)

    def _hub_nav_v(self, direction):
        if self.paint_mode:
            return
        if self.pane == "map":
            self.map_index = max(0, min(len(self.missions()) - 1, self.map_index + direction))
            self.toast = ""
            return
        if self.pane == "log":
            # only the first line (watch the intro again) can be selected: Up / Down scroll the rest
            top = max(0, len(self.log_entries()) - LOG_ROWS)
            self.log_scroll = max(0, min(top, self.log_scroll + direction))
            return
        if self.pane == "bestiary":
            n = len(ss.bestiary_entries(self.state))
            self.best_index = max(0, min(max(0, n - 1), self.best_index + direction))
            return
        if self.pane != "hangar":
            return
        if self.zone == "slots" and direction > 0:
            self.zone = "shop"
            self.shop_index = 0
            return
        if self.zone == "shop" and direction < 0 and self.shop_index == 0:
            self.zone = "slots"
            return
        if self.zone == "shop":
            self.shop_index = max(0, min(len(self.shop_rows()) - 1, self.shop_index + direction))

    def _hub_confirm(self):
        """Shop buy, or a launch spec dict when a map node is confirmed."""
        if self.pane == "map":
            return self._launch_selected()
        if self.pane == "log":
            self.start_intro(back_to="log")          # watch the introduction again
            return None
        if self.pane != "hangar" or self.zone != "shop":
            return None
        rows = self.shop_rows()
        row = rows[max(0, min(len(rows) - 1, self.shop_index))]
        if row[0] == "paint":
            self._open_paint()
            return None
        self._buy(row)
        return None

    def _open_paint(self):
        """The paint shop row: opens the colour choice when a change is waiting."""
        if not ss.paint_state(self.state)["token"]:
            self.toast = t("story_paint_locked")
            return
        shield = next((sl for sl in self.state.get("slots") or [] if sl.get("id") == "shield"), {})
        tint = shield.get("tint") if shield.get("tint") in ss.PAINT_TINTS else "red"
        self.paint_choice = ss.PAINT_TINTS.index(tint)
        self.paint_mode = True
        self.toast = ""

    def _paint_confirm(self):
        """A on the colour choice: wear it (spends the change) or, if it is the current colour, just close."""
        tint = ss.PAINT_TINTS[self.paint_choice % len(ss.PAINT_TINTS)]
        if ss.paint_change(self.state, tint):
            self.save()
            self.toast = t("story_paint_done")
        self.paint_mode = False

    def _launch_selected(self):
        mission = self._mission()
        if not self.mission_playable(mission):
            return None
        spec = {
            "launch": True,
            "id": mission["id"],
            "title": mission["title"],
            "content": int(mission["content"]),
            "speed": float(mission.get("speed") or 1.0),
            "dome": bool(self.loadout(mission.get("ship")).get("dome")),
        }
        if mission.get("ship"):
            spec["ship"] = mission["ship"]            # a mission that imposes its hull
        waves = ss.mission_waves(mission)
        if waves:
            spec["waves"] = waves                 # several waves in a row, at the speed of their level
        if mission.get("hunt"):
            level = ss.hunt_level(self.state, mission["id"])
            spec["level"] = level
            if level > 1:                         # a won sortie comes back faster, like the next arcade cycle
                spec["waves"] = [ss.hunt_stage(mission, level)]
        if ss.is_paint(mission):
            spec["level"] = ss.invader_level(self.state, mission)
            spec["invaders"] = True               # a Space Invaders grid, three levels harder each pass
        if mission.get("swarm"):
            spec["swarm"] = True                  # the four enemies together, replaced as they fall
            spec["stage"] = int(mission.get("stage") or 11)
        return spec

    def apply_result(self, mission_id, score, cleared, kills=None):
        """End of a mission: credits, penalty or fall (see story_state.record_result)."""
        res = ss.record_result(self.state, mission_id, score, cleared, kills)
        if res["cleared"]:
            self.toast = t("story_clear").format(pts=res["score"])
            if res.get("act"):
                self.map_index = 0                   # a new act has a new map
                self.toast = t("story_act_start").format(n=res["act"])
            if res.get("paint"):
                self.toast = t("story_paint_done_series")
            if res.get("hull") == "phoenix":
                self.toast = t("story_phenix_gift")
        elif res["fallen"]:
            self.toast = t("story_fell_msg").format(name=self.state.get("name") or "")
        elif res["lost"]:
            self.toast = t("story_fail_pen").format(pts=res["lost"])
        else:
            self.toast = t("story_fail_none")
        self.pane = "map"
        self.save()
        if res["fallen"]:
            self._show_fall()

    def _show_fall(self):
        """A fallen Veteran goes back to the slot list, where the save is now a memorial."""
        msg = self.toast
        self.open_slots()
        self.msg = msg

    def resume(self, slot_no, toast="", pane="map"):
        """Back from a mission in a new Game object: reload the slot from disk."""
        self.open_slot(slot_no)
        if self.state.get("fallen"):
            self.toast = toast
            self._show_fall()
        else:
            self.pane = pane
            self.toast = toast

    def _buy(self, row):
        if not ss.buy(self.state, row[0]):
            return False
        self.save()
        return True

    def _shop_extra(self, sid, cost, locked):
        if sid == "paint":
            return t("story_paint_ready") if ss.paint_state(self.state)["token"] else t("story_locked")
        key = ss.upgrade_note(self.state, sid)
        if key:
            return t(key)
        return f"{cost} PTS"

    # --- draw ---
    def draw(self, surface, font, medium, small):
        self._ensure_art()
        if self.screen == "intro":
            self._draw_intro(surface, font, small)
            return
        if self.screen != "hub":
            self._draw_gate(surface, font, medium, small)
            return
        title = {
            "hangar": t("story_hangar"),
            "map": t("story_map"),
            "log": t("story_log"),
            "bestiary": t("story_best"),
        }[self.pane]
        ts = medium.render(title, True, (255, 150, 70))
        surface.blit(ts, (BASE_WIDTH // 2 - ts.get_width() // 2, 18))

        if self.cheating:
            # small, top left above the pilot name: the title, the credits and the FPS counter own the rest
            _text_fit(surface, small, t("story_cheat_banner"), (255, 70, 70), 11, 80, 330, scale=0.7)
        if self.state.get("name"):
            mode = t("story_mode_" + str(self.state.get("mode", "normal")))
            _text(surface, small, f"{self.state['name']}  -  {mode}", (170, 175, 195), 36, left=80)
        if self.pane == "hangar":
            self._draw_hangar(surface, font, medium, small)
        elif self.pane == "map":
            self._draw_map(surface, font, medium, small)
        elif self.pane == "bestiary":
            self._draw_bestiary(surface, font, medium, small)
        else:
            self._draw_log(surface, font, small)

        hint_key = {
            "hangar": "story_hint",
            "map": "story_hint_map",
            "log": "story_hint_log",
            "bestiary": "story_hint_best",
        }[self.pane]
        if self.paint_mode:
            hint_key = "story_hint_paint"
        cx = BASE_WIDTH // 2
        tabs = "  ".join(
            ("> " if p == self.pane else "  ") + t({
                "bestiary": "story_tab_best",
                "log": "story_tab_log",
                "hangar": "story_tab_hangar",
                "map": "story_tab_map",
            }[p])
            for p in PANES
        )
        _text(surface, small, tabs, (160, 170, 200), BASE_HEIGHT - 62, centerx=cx)
        _text(surface, small, t(hint_key), (140, 140, 170), BASE_HEIGHT - 24, centerx=cx)

    # --- intro ---
    def _intro_picture(self, name):
        img = self._intro_bg.get(name)
        if img is None:
            img = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
            try:
                raw = pygame.image.load(asset_path("story", name + ".jpg")).convert()
                scale = max(BASE_WIDTH / raw.get_width(), BASE_HEIGHT / raw.get_height())
                size = (int(round(raw.get_width() * scale)), int(round(raw.get_height() * scale)))
                big = pygame.transform.smoothscale(raw, size)
                img.blit(big, ((BASE_WIDTH - size[0]) // 2, (BASE_HEIGHT - size[1]) // 2))
                shade = pygame.Surface(img.get_size())
                shade.set_alpha(70)
                img.blit(shade, (0, 0))          # a little darker so the text reads
            except Exception:
                log_exc("story._intro_picture")
            self._intro_bg[name] = img
        return img

    def _intro_block(self, font):
        """The whole text of the current slide as one tall transparent picture (cached)."""
        key = (self.intro_index, get_lang(), self.state.get("name"), self.state.get("mode"), id(font))
        hit = self._intro_blocks.get(key)
        if hit is not None:
            return hit
        _pic, text_key = self.intro_slides[self.intro_index]
        rows = []                                  # (text, height); text None = a pause
        pitch = font.get_linesize() + 12
        for line in ss.intro_lines(t, text_key, self.state.get("name")):
            if not line:
                rows.append((None, pitch // 2))
            else:
                rows.extend((piece, pitch) for piece in _wrap(font, line, INTRO_TEXT_W))
        height = sum(h for _txt, h in rows)
        block = pygame.Surface((INTRO_TEXT_W, max(1, height)), pygame.SRCALPHA)
        y = 0
        for txt, h in rows:
            if txt:
                shadow = font.render(txt, True, (0, 0, 0))
                img = font.render(txt, True, (230, 232, 244))
                x = (INTRO_TEXT_W - img.get_width()) // 2
                block.blit(shadow, (x + 2, y + 2))
                block.blit(img, (x, y))
            y += h
        if len(self._intro_blocks) > 16:
            self._intro_blocks.clear()
        self._intro_blocks[key] = (block, height)
        return block, height

    def _intro_fade_mask(self):
        """White picture whose alpha fades at the top and bottom edges (text slides in and out softly)."""
        if self._intro_mask is None:
            mask = pygame.Surface((INTRO_TEXT_W, BASE_HEIGHT), pygame.SRCALPHA)
            for y in range(BASE_HEIGHT):
                if y < 90:
                    a = y / 90.0
                elif y > INTRO_END_Y:
                    a = max(0.0, 1.0 - (y - INTRO_END_Y) / 52.0)
                else:
                    a = 1.0
                pygame.draw.line(mask, (255, 255, 255, int(255 * a)), (0, y), (INTRO_TEXT_W, y))
            self._intro_mask = mask
        return self._intro_mask

    def intro_finished_scrolling(self, text_height):
        """True once the text has risen to its resting place."""
        return self._intro_top(text_height) <= self._intro_rest(text_height)

    @staticmethod
    def _intro_rest(text_height):
        return min((BASE_HEIGHT - text_height) // 2, INTRO_END_Y - text_height)

    def _intro_top(self, text_height):
        return max(self._intro_rest(text_height), BASE_HEIGHT - self.intro_pos)

    def _draw_intro(self, surface, font, small):
        pic, _key = self.intro_slides[self.intro_index]
        surface.blit(self._intro_picture(pic), (0, 0))
        cx = BASE_WIDTH // 2
        band = pygame.Surface((INTRO_TEXT_W + 120, BASE_HEIGHT), pygame.SRCALPHA)
        band.fill((0, 0, 0, 120))
        surface.blit(band, (cx - band.get_width() // 2, 0))

        block, height = self._intro_block(font)
        self._intro_limit = BASE_HEIGHT - self._intro_rest(height)     # the text cannot rise past this
        top = self._intro_top(height)
        view = pygame.Surface((INTRO_TEXT_W, BASE_HEIGHT), pygame.SRCALPHA)
        view.blit(block, (0, top))
        view.blit(self._intro_fade_mask(), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(view, (cx - INTRO_TEXT_W // 2, 0))

        done = self.intro_finished_scrolling(height)
        last = self.intro_index + 1 >= len(self.intro_slides)
        blink = done and (pygame.time.get_ticks() // 500) % 2 == 0
        col = (255, 220, 120) if blink else ((235, 235, 245) if done else (140, 145, 170))
        _text(surface, small, t("story_intro_last" if last else "story_intro_hint"), col,
              BASE_HEIGHT - 24, centerx=cx)
        _text(surface, small, f"{self.intro_index + 1} / {len(self.intro_slides)}", (140, 145, 170),
              28, right=BASE_WIDTH - 40)

        fade = 1.0 - min(1.0, self.intro_t / INTRO_FADE)
        if fade > 0:
            black = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
            black.set_alpha(int(255 * fade))
            surface.blit(black, (0, 0))

    # --- slot list, name, mode, delete ---
    def _draw_gate(self, surface, font, medium, small):
        cx = BASE_WIDTH // 2
        titles = {"slots": "story_gate_title", "delete": "story_delete_title",
                  "name": "story_name_title", "mode": "story_mode_title"}
        hints = {"slots": "story_gate_hint", "delete": "story_delete_hint",
                 "name": "story_name_hint", "mode": "story_mode_hint"}
        ts = medium.render(t(titles[self.screen]), True, (255, 150, 70))
        surface.blit(ts, (cx - ts.get_width() // 2, 18))
        getattr(self, "_draw_gate_" + self.screen)(surface, font, medium, small)
        _text(surface, small, t(hints[self.screen]), (140, 140, 170), BASE_HEIGHT - 24, centerx=cx)

    def _draw_gate_slots(self, surface, font, medium, small):
        card_w = min(BASE_WIDTH - 240, 1100)
        x = (BASE_WIDTH - card_w) // 2
        h, gap, y = 120, 16, 90
        for i, info in enumerate(self.summaries[:ss.SLOT_COUNT]):
            r = pygame.Rect(x, y, card_w, h)
            status = info.get("status")
            focus = i == self.sel
            on_card = focus and self.col == 0
            border = (80, 220, 255) if on_card else ((70, 80, 100) if status == "missing" else (180, 120, 60))
            pygame.draw.rect(surface, (16, 18, 28), r, border_radius=12)
            pygame.draw.rect(surface, border, r, 3 if on_card else 2, border_radius=12)
            _text(surface, medium, str(i + 1), border, r.centery, left=r.x + 28)
            tx = r.x + 84
            if status == "missing":
                _text(surface, small, t("story_slot_empty"), (140, 140, 160), r.centery, left=tx)
            elif status == "damaged":
                _text(surface, small, t("story_slot_damaged"), (255, 90, 80), r.centery, left=tx)
            else:
                _text(surface, medium, info.get("name") or "-", (255, 230, 140) if on_card else (220, 220, 235),
                      r.y + 40, left=tx)
                if info.get("fallen"):
                    line = t("story_slot_fallen")
                    col = (255, 90, 80)
                else:
                    line = "   ".join(p for p in (t("story_slot_act").format(n=info.get("act", 1)),
                                                   info.get("date") or "",
                                                   t("story_mode_" + str(info.get("mode", "normal")))) if p)
                    col = (170, 175, 195)
                _text(surface, small, line, col, r.y + 86, left=tx)
            if status != "missing":
                b = pygame.Rect(r.right - 230, r.centery - 26, 206, 52)
                bf = focus and self.col == 1
                pygame.draw.rect(surface, (40, 36, 20) if bf else (22, 24, 36), b, border_radius=8)
                pygame.draw.rect(surface, (255, 210, 80) if bf else (80, 85, 105), b, 2, border_radius=8)
                _text(surface, small, t("story_slot_delete"), (255, 230, 140) if bf else (150, 155, 175),
                      b.centery, centerx=b.centerx)
            y += h + gap
        if self.msg:
            _text(surface, small, self.msg, (255, 220, 120), y + 20, centerx=BASE_WIDTH // 2)

    def _draw_gate_delete(self, surface, font, medium, small):
        cx = BASE_WIDTH // 2
        info = self._summary()
        _text(surface, medium, info.get("name") or t("story_slot_damaged"), (255, 230, 140), 200, centerx=cx)
        _text(surface, small, t("story_delete_warn"), (255, 120, 100), 270, centerx=cx)
        for k, (label, yes) in enumerate(((t("story_no"), False), (t("story_yes"), True))):
            b = pygame.Rect(cx - 230 + k * 260, 340, 200, 60)
            focus = self.del_yes == yes
            pygame.draw.rect(surface, (40, 36, 20) if focus else (22, 24, 36), b, border_radius=10)
            pygame.draw.rect(surface, ((255, 90, 80) if yes else (255, 210, 80)) if focus else (80, 85, 105),
                             b, 3 if focus else 2, border_radius=10)
            _text(surface, small, label, (255, 230, 140) if focus else (150, 155, 175), b.centery, centerx=b.centerx)

    def _draw_gate_name(self, surface, font, medium, small):
        cx = BASE_WIDTH // 2
        box = pygame.Rect(cx - 280, 90, 560, 70)
        pygame.draw.rect(surface, (16, 18, 28), box, border_radius=10)
        pygame.draw.rect(surface, (80, 220, 255), box, 2, border_radius=10)
        text = self.entry.text
        shown = text + ("_" if (pygame.time.get_ticks() // 450) % 2 == 0 and len(text) < ss.NAME_MAX else " ")
        _text(surface, medium, shown, (255, 230, 140), box.centery, left=box.x + 22)
        _text(surface, small, f"{len(text)}/{ss.NAME_MAX}", (120, 125, 150), box.centery, right=box.right - 16)
        cw, ch, cg = 72, 56, 8
        gx = (BASE_WIDTH - (10 * cw + 9 * cg)) // 2
        gy = 190
        labels = {"SPACE": "SPC", "DEL": "DEL", "OK": "OK"}
        for ri, row in enumerate(ss.KEY_ROWS):
            for ci, tok in enumerate(row):
                r = pygame.Rect(gx + ci * (cw + cg), gy + ri * (ch + cg), cw, ch)
                focus = ri == self.entry.row and ci == self.entry.col
                tint = (60, 150, 90) if tok == "OK" else ((170, 80, 70) if tok == "DEL" else (80, 85, 105))
                pygame.draw.rect(surface, (40, 36, 20) if focus else (16, 18, 28), r, border_radius=8)
                pygame.draw.rect(surface, (255, 210, 80) if focus else tint, r, 3 if focus else 2, border_radius=8)
                _text(surface, small, labels.get(tok, tok), (255, 230, 140) if focus else (200, 200, 215),
                      r.centery, centerx=r.centerx)
        if self.msg:
            _text(surface, small, self.msg, (255, 220, 120), gy + 4 * (ch + cg) + 24, centerx=cx)

    def _draw_gate_mode(self, surface, font, medium, small):
        cx = BASE_WIDTH // 2
        _text(surface, small, f"{t('story_pilot')} : {self.new_name}", (170, 175, 195), 100, centerx=cx)
        w, h, gap = 460, 270, 40
        x0 = cx - (w * 2 + gap) // 2
        for k, key in enumerate(ss.MODES):
            r = pygame.Rect(x0 + k * (w + gap), 140, w, h)
            focus = k == self.mode_index
            vet = key == "veteran"
            pygame.draw.rect(surface, (30, 28, 22) if focus else (16, 18, 28), r, border_radius=12)
            pygame.draw.rect(surface, (255, 210, 80) if focus else (70, 80, 100), r, 3 if focus else 2, border_radius=12)
            col = (255, 110, 100) if vet else (140, 220, 160)
            _text(surface, medium, t("story_mode_" + key), col if focus else (150, 155, 175), r.y + 46, centerx=r.centerx)
            for li, line in enumerate(_wrap(small, t("story_mode_%s_d" % key), r.w - 48)):
                _text(surface, small, line, (200, 200, 215) if focus else (130, 135, 155), r.y + 112 + li * 36, centerx=r.centerx)

    def _draw_log(self, surface, font, small):
        box = pygame.Rect(80, 78, BASE_WIDTH - 160, BASE_HEIGHT - 168)
        pygame.draw.rect(surface, (18, 20, 32), box, border_radius=10)
        pygame.draw.rect(surface, (70, 90, 130), box, 2, border_radius=10)
        entries = self.log_entries()
        rows, step = LOG_ROWS, 40
        start = self.log_scroll = max(0, min(self.log_scroll, len(entries) - rows))
        y = box.y + 28
        for i in range(start, min(len(entries), start + rows)):
            entry = entries[i]
            focus = isinstance(entry, dict) and bool(entry.get("intro"))   # the only selectable line
            indent = 0
            row = pygame.Rect(box.x + 12, y - step // 2 + 2, box.w - 24, step - 4)
            if focus:
                pygame.draw.rect(surface, (40, 36, 20), row, border_radius=6)
                pygame.draw.rect(surface, (255, 210, 80), row, 2, border_radius=6)
            if isinstance(entry, dict) and entry.get("intro"):
                text = t("story_log_intro")
                col = (255, 230, 140) if focus else (255, 190, 90)
            elif isinstance(entry, dict) and ("kills" in entry or "level" in entry):
                text = log_text(entry, t)
                col = (255, 215, 130) if focus else (190, 175, 130)
                indent = 56                                   # sits under its mission line
            else:
                text = log_text(entry, t)
                col = (235, 235, 245) if focus else (200, 200, 220)
            if indent:
                _text(surface, small, ">" if focus else " ", col, y, left=box.x + 24)
            _text_fit(surface, small, text if indent else ("> " if focus else "  ") + text, col, y,
                      box.x + 24 + indent, row.w - 24 - indent)
            y += step

    def bestiary_picture(self, kind, count):
        """The picture of an enemy met `count` times: small, then 2x, then animated (also 2x)."""
        tiers = ss.best_tiers(count, ss.is_boss(kind))
        img = bestiary_art.animated(kind, self.anim_t) if tiers["anim"] else bestiary_art.still(kind)
        if tiers["zoom"]:
            img = pygame.transform.scale(img, (img.get_width() * 2, img.get_height() * 2))
        return img

    def _draw_bestiary(self, surface, font, medium, small):
        """Left: the enemies met so far. Right: what the pilot has learned about the selected one."""
        box = pygame.Rect(70, 78, BASE_WIDTH - 140, BASE_HEIGHT - 168)
        pygame.draw.rect(surface, (16, 18, 28), box, border_radius=10)
        pygame.draw.rect(surface, (70, 90, 130), box, 2, border_radius=10)
        entries = ss.bestiary_entries(self.state)
        if not entries:
            _text(surface, font, t("story_best_empty"), (160, 170, 200), box.centery, centerx=box.centerx)
            return
        self.best_index = max(0, min(len(entries) - 1, self.best_index))

        list_w = 400
        y = box.y + 30
        for i, (entry, count) in enumerate(entries):
            focus = i == self.best_index
            row = pygame.Rect(box.x + 12, y - 24, list_w, 48)
            if focus:
                pygame.draw.rect(surface, (40, 36, 20), row, border_radius=6)
                pygame.draw.rect(surface, (255, 210, 80), row, 2, border_radius=6)
            col = (255, 230, 140) if focus else (200, 200, 215)
            _text_fit(surface, small, ("> " if focus else "  ") + t(entry["name"]), col, y, row.x + 10,
                      list_w - 20, scale=0.8)
            y += 56
        pygame.draw.line(surface, (60, 70, 100), (box.x + list_w + 24, box.y + 16),
                         (box.x + list_w + 24, box.bottom - 16), 1)

        entry, count = entries[self.best_index]
        tiers = ss.best_tiers(count, bool(entry.get("boss")))
        panel = pygame.Rect(box.x + list_w + 44, box.y + 16, box.w - list_w - 64, box.h - 32)
        cx = panel.centerx

        # picture: 1 kill = small, 3 = twice as big, 5 = animated
        frame = pygame.Rect(panel.x, panel.y, panel.w, 210)
        pygame.draw.rect(surface, (8, 10, 18), frame, border_radius=8)
        pygame.draw.rect(surface, (50, 60, 90), frame, 1, border_radius=8)
        img = self.bestiary_picture(entry["id"], count)
        surface.blit(img, (frame.centerx - img.get_width() // 2, frame.centery - img.get_height() // 2))

        name_w = medium.size(t(entry["name"]))[0]
        if name_w <= panel.w - 20:
            _text(surface, medium, t(entry["name"]), (255, 170, 80), frame.bottom + 36, centerx=cx)
        else:                                   # a long translated name is shrunk to fit
            _text_fit(surface, medium, t(entry["name"]), (255, 170, 80), frame.bottom + 36,
                      panel.x + 10, panel.w - 20)
        _text(surface, small, t("story_best_count").format(n=count), (150, 155, 180), frame.bottom + 76, centerx=cx)
        line_y = frame.bottom + 116
        if tiers["text"]:
            for line in _wrap(small, t(entry["text"]), panel.w - 40):
                _text(surface, small, line, (215, 218, 232), line_y, centerx=cx)
                line_y += 36
        if tiers["bonus"]:
            _text(surface, small, t("story_best_bonus_boss" if entry.get("boss") else "story_best_bonus").format(
                      pts=ss.bestiary_bonus(entry["id"])), (255, 215, 90),
                  panel.bottom - 14, centerx=cx)

    def _ship_name(self):
        slot = ss.selected_slot(self.state) or {}
        if not slot.get("owned"):
            slot = next((sl for sl in self.state.get("slots") or [] if sl.get("owned")), slot)
        return t("ship_shield") if slot.get("id") != "phoenix" else t("ship_phoenix")

    def _draw_map(self, surface, font, medium, small):
        # the missions are flown with the hull chosen in the hangar
        _text(surface, small, t("story_ship_label").format(name=self._ship_name()), (170, 175, 195), 36,
              right=BASE_WIDTH - 80)
        box = pygame.Rect(70, 78, BASE_WIDTH - 140, BASE_HEIGHT - 168)
        pygame.draw.rect(surface, (16, 18, 28), box, border_radius=10)
        pygame.draw.rect(surface, (70, 90, 130), box, 2, border_radius=10)
        act = int(self.state.get("act") or 1)
        _text(surface, small, t("story_ch2") if act >= 2 and not self.cheat_unlock else t("story_ch1"),
              (255, 170, 80), box.y + 28, left=box.x + 16)
        y = box.y + 52
        # the list scrolls: rows from `first` on, so that the focused one (taller) always fits
        room = box.bottom - 44 - y
        missions = self.missions()
        focus_i = max(0, min(len(missions) - 1, self.map_index))
        first = 0
        while first < focus_i and sum(40 + 4 for _ in range(first, focus_i)) + 76 + 4 > room:
            first += 1
        if first > 0:
            _text(surface, small, "^", (180, 180, 200), box.y + 28, right=box.right - 20)
        for i, mission in enumerate(missions):
            if i < first:
                continue
            if y + (76 if i == focus_i else 40) > box.bottom - 44:
                _text(surface, small, "v", (180, 180, 200), box.bottom - 56, right=box.right - 20)
                break
            open_ = self.mission_open(mission)
            playable = self.mission_playable(mission)
            done = ss.mission_done(self.state, mission)
            focus = i == self.map_index
            # the focused row is taller: title line + one line for the blurb
            row = pygame.Rect(box.x + 12, y, box.w - 24, 76 if focus else 40)
            if focus:
                pygame.draw.rect(surface, (36, 32, 22), row, border_radius=6)
                pygame.draw.rect(surface, (255, 210, 80), row, 2, border_radius=6)
            if not open_:
                col = (110, 110, 120)
                mark = "  "
                state = t("story_locked")
            elif done:
                col = (140, 220, 160) if not focus else (190, 255, 190)
                mark = "> " if focus else "  "
                state = t("story_replay") if mission.get("hunt") else t("story_cleared")
            elif playable:
                col = (255, 230, 140) if focus else (210, 210, 220)
                mark = "> " if focus else "  "
                state = t("story_ready")
            else:
                col = (180, 180, 140) if focus else (150, 150, 160)
                mark = "> " if focus else "  "
                state = t("story_soon")
            cy = row.y + 20
            name = t(mission["title"])
            level = ss.mission_level(self.state, mission)
            if open_ and level is not None:
                name += "   " + t("story_level").format(n=level)
            _text(surface, small, f"{mark}{name}", col, cy, left=row.x + 10)
            _text(surface, small, state, col, cy, right=row.right - 14)
            if focus:
                _text_fit(surface, small, t(mission["blurb"]), (170, 175, 195), cy + 34, row.x + 28, row.w - 40)
            y += row.h + 4
        if self.toast:
            _text(surface, small, self.toast, (255, 220, 120), box.bottom - 30, centerx=box.centerx)

    def _hull_key(self, sl):
        """Picture key of a hull: the Shield wears the colour chosen in the paint shop."""
        key = sl.get("id")
        if key == "shield" and sl.get("tint") in ss.PAINT_TINTS:
            key = "shield_" + sl["tint"]
        return key

    def _draw_hangar(self, surface, font, medium, small):
        """The two hulls, drawn like the ship select screen (portrait in a frame, the chosen one lit, the
        other one dimmed), without the Phenix / dome animations. The chosen hull flies the missions."""
        slots = self.state.get("slots") or []
        sel = int(self.state.get("selected_slot", 0))
        slot_w, slot_h = 440, 176
        gap = 40
        x0 = (BASE_WIDTH - (slot_w * 2 + gap)) // 2
        y0 = 54
        for i, sl in enumerate(slots[:2]):
            r = pygame.Rect(x0 + i * (slot_w + gap), y0, slot_w, slot_h)
            owned = bool(sl.get("owned"))
            chosen = i == sel
            if owned and chosen:
                border = (255, 210, 90)                         # the lit frame of the ship select screen
            else:
                border = (70, 70, 90)
            pygame.draw.rect(surface, (16, 18, 28), r, border_radius=10)
            pygame.draw.rect(surface, border, r, 2, border_radius=10)
            key = self._hull_key(sl)
            img = (self._portraits if chosen else self._greyed).get(key)
            if owned and img is not None:
                bob = int(math.sin(self.anim_t * 3.2) * 4) if chosen else 0
                surface.blit(img, (r.centerx - img.get_width() // 2, r.y + 12 + bob))
                label = t("ship_shield") if sl.get("id") == "shield" else t("ship_phoenix")
                col = (255, 230, 120) if chosen else (150, 150, 175)
                _text(surface, small, label, col, r.bottom - 22, centerx=r.centerx)
            else:
                # a hull that is not owned yet shows nothing about itself (no spoiler)
                _text(surface, medium, t("story_hull_empty"), (110, 115, 135), r.centery, centerx=r.centerx)

        sl = slots[sel] if 0 <= sel < len(slots) else (slots[0] if slots else {})
        self._draw_stats(surface, sl, small, y0 + slot_h + 6)
        self._draw_shop(surface, small)
        pts = medium.render(f"{int(self.state.get('credits', 0))} PTS", True, (255, 210, 80))
        surface.blit(pts, (BASE_WIDTH - 80 - pts.get_width(), 18))

    def _draw_stats(self, surface, sl, small, y):
        owned = bool(sl.get("owned"))
        dome = bool(sl.get("dome"))
        dur = float(sl.get("dome_dur") or 0)
        cd = float(sl.get("dome_cd") or 5.0)
        dome_val = t("story_locked")
        if dome:
            dome_val = f"{dur:.1f}s / {cd:.0f}s"
        phenix = sl.get("id") == "phoenix"
        if phenix:
            dome_val = f"{ss.phenix_cap(sl)}%"
        cells = [
            (t("story_stat_lives"), f"{sl.get('lives', 1)}/{ss.act_caps(self.state)['lives']}"),
            (t("story_stat_speed"), f"{sl.get('speed', ss.SPEED_START)}%"),
            (t("story_stat_phenix") if phenix else t("story_stat_dome"), dome_val),
            (t("story_stat_wall"), t("story_wall_" + str(sl.get("wall", "instant")))),
        ]
        w = 220
        x = (BASE_WIDTH - (w * 4 + 16 * 3)) // 2
        for i, (lab, val) in enumerate(cells):
            r = pygame.Rect(x + i * (w + 16), y, w, 64)
            pygame.draw.rect(surface, (16, 18, 28), r, border_radius=8)
            pygame.draw.rect(surface, (60, 70, 90), r, 1, border_radius=8)
            col = (110, 115, 135) if (i == 2 and not dome and not phenix) else (220, 220, 235)
            if not owned:
                val = "—"
            _text(surface, small, lab, (150, 155, 175), r.y + 18, centerx=r.centerx)
            _text(surface, small, str(val), col, r.y + 46, centerx=r.centerx)

    def _draw_paint(self, surface, small, box):
        """The paint shop: the three colours of the Shield side by side."""
        _text(surface, small, t("story_paint_title"), (255, 160, 70), box.y + 26, left=box.x + 16)
        names = {"red": t("story_paint_red"), "green": t("story_paint_green"), "violet": t("story_paint_violet")}
        shield = next((sl for sl in self.state.get("slots") or [] if sl.get("id") == "shield"), {})
        current = shield.get("tint") if shield.get("tint") in ss.PAINT_TINTS else "red"
        cell_w = 300
        x0 = box.centerx - (cell_w * 3 + 20 * 2) // 2
        for i, tint in enumerate(ss.PAINT_TINTS):
            r = pygame.Rect(x0 + i * (cell_w + 20), box.y + 52, cell_w, 190)
            focus = i == self.paint_choice
            pygame.draw.rect(surface, (40, 36, 20) if focus else (22, 24, 36), r, border_radius=8)
            pygame.draw.rect(surface, (255, 210, 80) if focus else (70, 80, 100), r, 3 if focus else 1, border_radius=8)
            img = self._ships.get("shield_" + tint)
            if img is not None:
                surface.blit(img, (r.centerx - img.get_width() // 2, r.y + 24))
            label = names[tint] + ("  (" + t("story_paint_worn") + ")" if tint == current else "")
            _text(surface, small, label, (255, 230, 140) if focus else (200, 200, 210), r.bottom - 28, centerx=r.centerx)

    def _draw_shop(self, surface, small):
        box = pygame.Rect(70, 308, BASE_WIDTH - 140, 328)
        pygame.draw.rect(surface, (16, 18, 28), box, border_radius=10)
        pygame.draw.rect(surface, (180, 120, 50), box, 2, border_radius=10)
        if self.paint_mode:
            self._draw_paint(surface, small, box)
            return
        _text(surface, small, t("story_workshop"), (255, 160, 70), box.y + 26, left=box.x + 16)
        flags = self.state.get("flags") or {}
        window = 7
        rows = self.shop_rows()
        start = max(0, min(self.shop_index - 3, len(rows) - window))
        y = box.y + 46
        for i in range(start, min(len(rows), start + window)):
            sid, label, cost, need = rows[i]
            locked = bool(need) and not flags.get(need)
            if sid == "paint":
                locked = not ss.paint_state(self.state)["token"]
            focus = self.zone == "shop" and i == self.shop_index
            row = pygame.Rect(box.x + 12, y, box.w - 24, 38)
            if focus:
                pygame.draw.rect(surface, (40, 36, 20), row, border_radius=6)
                pygame.draw.rect(surface, (255, 210, 80), row, 2, border_radius=6)
            col = (100, 100, 110) if locked else ((255, 230, 140) if focus else (200, 200, 210))
            mark = "> " if focus else "  "
            extra = self._shop_extra(sid, cost, locked)
            _text(surface, small, f"{mark}{t(label)}", col, row.centery, left=row.x + 8)
            _text(surface, small, extra, col, row.centery, right=row.right - 12)
            y += 40
