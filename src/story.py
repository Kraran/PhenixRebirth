"""
Story / Adventure hub — Hangar, Mission map, Mission log.

Arcade loop never imports combat rules from here. This module draws the
pre-run screens and handles their input; the rules and the save data
(hangar, shop, missions, story_N.json) live in story_state.py, which has no
drawing code and is tested on its own. Points earned in a mission are
hangar credits.
"""
import pygame
from settings import BASE_WIDTH, BASE_HEIGHT, asset_path
from i18n import t
from errlog import log_exc
import story_state as ss
from story_state import MISSIONS, SHOP, log_text


PANES = ("log", "hangar", "map")


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


class StoryHub:
    """Three-pane hub. Left = log, center = hangar, right = map."""

    def __init__(self):
        self.slot_no = None            # save slot (1..3) being played; None before one is opened
        self.state = ss.default_state()
        self.screen = "slots"          # slots | delete | name | mode | hub
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
        self.map_index = 0
        self.toast = ""
        self._ships = {}
        self._loaded_img = False

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
        self.screen = "hub"
        self.pane = "hangar"
        self.zone = "slots"
        self.shop_index = 0
        self.map_index = 0
        self.toast = ""

    def save(self):
        if self.slot_no is None:
            return
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
            "phoenix": "sprites/player_ship.png",
        }
        for key, rel in mapping.items():
            fp = asset_path(*rel.split("/"))
            try:
                img = pygame.image.load(fp).convert_alpha()
                img = pygame.transform.smoothscale(img, (150, 90))
                self._ships[key] = img
            except Exception:
                self._ships[key] = None

    def flag(self, name):
        return ss.flag(self.state, name)

    def _slot(self):
        return ss.selected_slot(self.state)

    def loadout(self):
        """Hull the mission actually launches. Locked Phoenix falls back to Shield."""
        return ss.loadout(self.state)

    def _mission(self, index=None):
        i = self.map_index if index is None else index
        if 0 <= i < len(MISSIONS):
            return MISSIONS[i]
        return None

    def mission_open(self, mission):
        return ss.mission_open(self.state, mission)

    def mission_playable(self, mission):
        return ss.mission_playable(self.state, mission)

    # --- input: every screen answers to the same four calls ---
    def text_input_active(self):
        return self.screen == "name"

    def type_key(self, event):
        """Real keyboard while typing a name. True when the key was used."""
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
        return None

    def back(self):
        """B / Esc. True when handled here; False on the slot list (leave the Adventure)."""
        if self.screen == "hub":
            self.open_slots()
        elif self.screen in ("delete", "name"):
            self.screen = "slots"
            self.msg = ""
        elif self.screen == "mode":
            self.screen = "name"
        else:
            return False
        return True

    # --- hub input ---
    def _hub_nav_h(self, direction):
        """Left / right. Slots when hangar+slots, else change pane."""
        if self.pane == "hangar" and self.zone == "slots":
            slots = self.state["slots"]
            cur = int(self.state.get("selected_slot", 0))
            nxt = max(0, min(len(slots) - 1, cur + direction))
            if nxt != cur:
                self.state["selected_slot"] = nxt
                return
        idx = PANES.index(self.pane)
        self.pane = PANES[max(0, min(len(PANES) - 1, idx + direction))]
        self.zone = "slots"
        self.toast = ""

    def _hub_nav_v(self, direction):
        if self.pane == "map":
            self.map_index = max(0, min(len(MISSIONS) - 1, self.map_index + direction))
            self.toast = ""
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
            self.shop_index = max(0, min(len(SHOP) - 1, self.shop_index + direction))

    def _hub_confirm(self):
        """Shop buy, or a launch spec dict when a map node is confirmed."""
        if self.pane == "map":
            return self._launch_selected()
        if self.pane != "hangar" or self.zone != "shop":
            return None
        self._buy(SHOP[self.shop_index])
        return None

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
            "dome": bool(self.loadout().get("dome")),
        }
        return spec

    def apply_result(self, mission_id, score, cleared, target=0):
        """End of a mission: credits, penalty or fall (see story_state.record_result)."""
        res = ss.record_result(self.state, mission_id, score, cleared, target)
        if res["cleared"]:
            self.toast = t("story_clear").format(pts=res["score"])
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

    def resume(self, slot_no, toast=""):
        """Back from a mission in a new Game object: reload the slot from disk."""
        self.open_slot(slot_no)
        if self.state.get("fallen"):
            self.toast = toast
            self._show_fall()
        else:
            self.pane = "map"
            self.toast = toast

    def _buy(self, row):
        if not ss.buy(self.state, row[0]):
            return False
        self.save()
        return True

    def _shop_extra(self, sid, cost, locked):
        key = ss.upgrade_note(self.state, sid)
        if key:
            return t(key)
        return f"{cost} PTS"

    # --- draw ---
    def draw(self, surface, font, medium, small):
        self._ensure_art()
        if self.screen != "hub":
            self._draw_gate(surface, font, medium, small)
            return
        title = {
            "hangar": t("story_hangar"),
            "map": t("story_map"),
            "log": t("story_log"),
        }[self.pane]
        ts = medium.render(title, True, (255, 150, 70))
        surface.blit(ts, (BASE_WIDTH // 2 - ts.get_width() // 2, 18))

        if self.state.get("name"):
            mode = t("story_mode_" + str(self.state.get("mode", "normal")))
            _text(surface, small, f"{self.state['name']}  -  {mode}", (170, 175, 195), 36, left=80)
        if self.pane == "hangar":
            self._draw_hangar(surface, font, medium, small)
        elif self.pane == "map":
            self._draw_map(surface, font, medium, small)
        else:
            self._draw_log(surface, font, small)

        hint_key = {
            "hangar": "story_hint",
            "map": "story_hint_map",
            "log": "story_hint_log",
        }[self.pane]
        cx = BASE_WIDTH // 2
        tabs = "  ".join(
            ("> " if p == self.pane else "  ") + t({
                "log": "story_tab_log",
                "hangar": "story_tab_hangar",
                "map": "story_tab_map",
            }[p])
            for p in PANES
        )
        _text(surface, small, tabs, (160, 170, 200), BASE_HEIGHT - 62, centerx=cx)
        _text(surface, small, t(hint_key), (140, 140, 170), BASE_HEIGHT - 24, centerx=cx)

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
        log = self.state.get("log") or []
        if not log:
            _text(surface, font, t("story_log_empty"), (160, 170, 200), box.centery, centerx=box.centerx)
            return
        cy = box.y + 34
        for line in log[-14:]:
            _text(surface, small, log_text(line, t), (200, 200, 220), cy, left=box.x + 24)
            cy += 36

    def _draw_map(self, surface, font, medium, small):
        box = pygame.Rect(70, 78, BASE_WIDTH - 140, BASE_HEIGHT - 168)
        pygame.draw.rect(surface, (16, 18, 28), box, border_radius=10)
        pygame.draw.rect(surface, (70, 90, 130), box, 2, border_radius=10)
        _text(surface, small, t("story_ch1"), (255, 170, 80), box.y + 28, left=box.x + 16)
        y = box.y + 52
        for i, mission in enumerate(MISSIONS):
            open_ = self.mission_open(mission)
            playable = self.mission_playable(mission)
            done = mission["id"] in (self.state.get("cleared") or [])
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
                state = t("story_cleared")
            elif playable:
                col = (255, 230, 140) if focus else (210, 210, 220)
                mark = "> " if focus else "  "
                state = t("story_ready")
            else:
                col = (180, 180, 140) if focus else (150, 150, 160)
                mark = "> " if focus else "  "
                state = t("story_soon")
            cy = row.y + 20
            _text(surface, small, f"{mark}{t(mission['title'])}", col, cy, left=row.x + 10)
            _text(surface, small, state, col, cy, right=row.right - 14)
            if focus:
                _text(surface, small, t(mission["blurb"]), (170, 175, 195), cy + 34, left=row.x + 28)
            y += row.h + 4
        if self.toast:
            _text(surface, small, self.toast, (255, 220, 120), box.bottom - 30, centerx=box.centerx)

    def _draw_hangar(self, surface, font, medium, small):
        slots = self.state.get("slots") or []
        sel = int(self.state.get("selected_slot", 0))
        slot_w, slot_h = 460, 150
        gap = 24
        x0 = (BASE_WIDTH - (slot_w * 2 + gap)) // 2
        y0 = 58
        for i, sl in enumerate(slots[:2]):
            r = pygame.Rect(x0 + i * (slot_w + gap), y0, slot_w, slot_h)
            owned = bool(sl.get("owned"))
            focus = self.zone == "slots" and i == sel
            border = (80, 220, 255) if focus else ((70, 80, 100) if not owned else (180, 120, 60))
            pygame.draw.rect(surface, (16, 18, 28), r, border_radius=12)
            pygame.draw.rect(surface, border, r, 3 if focus else 2, border_radius=12)
            label = t("ship_shield") if sl.get("id") == "shield" else t("ship_phoenix")
            _text(surface, small, f"SLOT {i + 1}  {label}", border, r.y + 26, left=r.x + 16)
            img = self._ships.get(sl.get("id"))
            if owned and img is not None:
                surface.blit(img, (r.centerx - img.get_width() // 2, r.y + 48))
            else:
                _text(surface, medium, "[X]", (140, 140, 150), r.y + 78, centerx=r.centerx)
                _text(surface, small, t("story_phoenix_locked"), (140, 140, 160), r.bottom - 26, centerx=r.centerx)

        sl = slots[sel] if 0 <= sel < len(slots) else (slots[0] if slots else {})
        self._draw_stats(surface, sl, small, y0 + slot_h + 8)
        self._draw_shop(surface, small)
        pts = medium.render(f"{int(self.state.get('credits', 0))} PTS", True, (255, 210, 80))
        surface.blit(pts, (BASE_WIDTH - 80 - pts.get_width(), 18))

    def _draw_stats(self, surface, sl, small, y):
        owned = bool(sl.get("owned"))
        dome = bool(sl.get("dome"))
        dur = float(sl.get("dome_dur") or 0)
        cd = float(sl.get("dome_cd") or 5.0)
        dome_val = t("story_offline")
        if dome:
            dome_val = f"{dur:.1f}s / {cd:.0f}s"
        cells = [
            (t("story_stat_lives"), f"{sl.get('lives', 1)}/3"),
            (t("story_stat_speed"), f"{sl.get('speed', 60)}%"),
            (t("story_stat_dome"), dome_val),
            (t("story_stat_wall"), t("story_wall_" + str(sl.get("wall", "instant")))),
        ]
        w = 220
        x = (BASE_WIDTH - (w * 4 + 16 * 3)) // 2
        for i, (lab, val) in enumerate(cells):
            r = pygame.Rect(x + i * (w + 16), y, w, 76)
            pygame.draw.rect(surface, (16, 18, 28), r, border_radius=8)
            pygame.draw.rect(surface, (60, 70, 90), r, 1, border_radius=8)
            col = (255, 90, 80) if (i == 2 and not dome) else (220, 220, 235)
            if not owned:
                val = "—"
            _text(surface, small, lab, (150, 155, 175), r.y + 22, centerx=r.centerx)
            _text(surface, small, str(val), col, r.y + 54, centerx=r.centerx)

    def _draw_shop(self, surface, small):
        box = pygame.Rect(70, 300, BASE_WIDTH - 140, 336)
        pygame.draw.rect(surface, (16, 18, 28), box, border_radius=10)
        pygame.draw.rect(surface, (180, 120, 50), box, 2, border_radius=10)
        _text(surface, small, t("story_workshop"), (255, 160, 70), box.y + 26, left=box.x + 16)
        flags = self.state.get("flags") or {}
        window = 7
        start = max(0, min(self.shop_index - 3, len(SHOP) - window))
        y = box.y + 46
        for i in range(start, min(len(SHOP), start + window)):
            sid, label, cost, need = SHOP[i]
            locked = bool(need) and not flags.get(need)
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
