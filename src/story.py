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


class StoryHub:
    """Three-pane hub. Left = log, center = hangar, right = map."""

    def __init__(self, slot=1):
        self.slot_no = int(slot)
        self.state = ss.default_state()
        self.load()
        self.pane = "hangar"
        self.zone = "slots"   # slots | shop
        self.shop_index = 0
        self.map_index = 0
        self.toast = ""
        self._ships = {}
        self._loaded_img = False

    def load(self):
        state = ss.load_state(ss.story_path(self.slot_no))
        if state is not None:
            self.state = state

    def save(self):
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

    # --- input ---
    def nav_h(self, direction):
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

    def nav_v(self, direction):
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

    def confirm(self):
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

    def apply_result(self, mission_id, score, cleared):
        """Bank points. Unlock flags and log only on a clear."""
        res = ss.record_result(self.state, mission_id, score, cleared)
        if res["cleared"] and any(m["id"] == mission_id for m in MISSIONS):
            self.toast = t("story_clear").format(pts=res["score"])
        else:
            self.toast = t("story_fail").format(pts=res["score"])
        self.pane = "map"
        self.save()

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
        title = {
            "hangar": t("story_hangar"),
            "map": t("story_map"),
            "log": t("story_log"),
        }[self.pane]
        ts = medium.render(title, True, (255, 150, 70))
        surface.blit(ts, (BASE_WIDTH // 2 - ts.get_width() // 2, 18))

        if self.pane == "hangar":
            self._draw_hangar(surface, font, medium, small)
        elif self.pane == "map":
            self._draw_map(surface, font, medium, small)
        else:
            self._draw_log(surface, font, small)

        if self.toast and self.pane == "map":
            toast = small.render(self.toast, True, (255, 220, 120))
            surface.blit(toast, (BASE_WIDTH // 2 - toast.get_width() // 2, 48))

        hint_key = {
            "hangar": "story_hint",
            "map": "story_hint_map",
            "log": "story_hint_log",
        }[self.pane]
        hint = small.render(t(hint_key), True, (140, 140, 170))
        surface.blit(hint, (BASE_WIDTH // 2 - hint.get_width() // 2, BASE_HEIGHT - 36))
        tabs = "  ".join(
            ("> " if p == self.pane else "  ") + t({
                "log": "story_tab_log",
                "hangar": "story_tab_hangar",
                "map": "story_tab_map",
            }[p])
            for p in PANES
        )
        tab = small.render(tabs, True, (160, 170, 200))
        surface.blit(tab, (BASE_WIDTH // 2 - tab.get_width() // 2, BASE_HEIGHT - 58))

    def _draw_log(self, surface, font, small):
        box = pygame.Rect(80, 78, BASE_WIDTH - 160, BASE_HEIGHT - 168)
        pygame.draw.rect(surface, (18, 20, 32), box, border_radius=10)
        pygame.draw.rect(surface, (70, 90, 130), box, 2, border_radius=10)
        log = self.state.get("log") or []
        if not log:
            s = font.render(t("story_log_empty"), True, (160, 170, 200))
            surface.blit(s, (box.centerx - s.get_width() // 2, box.centery - s.get_height() // 2))
            return
        y = box.y + 16
        for line in log[-14:]:
            s = small.render(log_text(line, t), True, (200, 200, 220))
            surface.blit(s, (box.x + 24, y))
            y += 26

    def _draw_map(self, surface, font, medium, small):
        box = pygame.Rect(70, 78, BASE_WIDTH - 140, BASE_HEIGHT - 168)
        pygame.draw.rect(surface, (16, 18, 28), box, border_radius=10)
        pygame.draw.rect(surface, (70, 90, 130), box, 2, border_radius=10)
        cap = small.render(t("story_ch1"), True, (255, 170, 80))
        surface.blit(cap, (box.x + 16, box.y + 10))
        y = box.y + 36
        for i, mission in enumerate(MISSIONS):
            open_ = self.mission_open(mission)
            playable = self.mission_playable(mission)
            done = mission["id"] in (self.state.get("cleared") or [])
            focus = i == self.map_index
            row = pygame.Rect(box.x + 12, y, box.w - 24, 52)
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
            line = f"{mark}{t(mission['title'])}"
            surface.blit(small.render(line, True, col), (row.x + 10, row.y + 6))
            surface.blit(small.render(state, True, col), (row.right - 160, row.y + 6))
            if focus:
                blurb = small.render(t(mission["blurb"]), True, (170, 175, 195))
                surface.blit(blurb, (row.x + 28, row.y + 28))
            y += 56

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
            cap = small.render(f"SLOT {i + 1}  {label}", True, border)
            surface.blit(cap, (r.x + 16, r.y + 8))
            img = self._ships.get(sl.get("id"))
            if owned and img is not None:
                surface.blit(img, (r.centerx - img.get_width() // 2, r.y + 36))
            else:
                lock = medium.render("[X]", True, (140, 140, 150))
                surface.blit(lock, (r.centerx - lock.get_width() // 2, r.centery - 8))
                dim = small.render(t("story_phoenix_locked"), True, (140, 140, 160))
                surface.blit(dim, (r.centerx - dim.get_width() // 2, r.bottom - 24))

        sl = slots[sel] if 0 <= sel < len(slots) else (slots[0] if slots else {})
        self._draw_stats(surface, sl, small, y0 + slot_h + 8)
        self._draw_shop(surface, small)
        pts = medium.render(f"{int(self.state.get('credits', 0))} PTS", True, (255, 210, 80))
        surface.blit(pts, (BASE_WIDTH - 80 - pts.get_width(), 18))

    def _draw_stats(self, surface, sl, small, y):
        owned = bool(sl.get("owned"))
        dome = bool(sl.get("dome"))
        dur = int(sl.get("dome_dur") or 0) / 60.0
        cd = int(sl.get("dome_cd") or 300) / 60.0
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
            r = pygame.Rect(x + i * (w + 16), y, w, 58)
            pygame.draw.rect(surface, (16, 18, 28), r, border_radius=8)
            pygame.draw.rect(surface, (60, 70, 90), r, 1, border_radius=8)
            a = small.render(lab, True, (150, 155, 175))
            col = (255, 90, 80) if (i == 2 and not dome) else (220, 220, 235)
            if not owned:
                val = "—"
            b = small.render(str(val), True, col)
            surface.blit(a, (r.centerx - a.get_width() // 2, r.y + 6))
            surface.blit(b, (r.centerx - b.get_width() // 2, r.y + 28))

    def _draw_shop(self, surface, small):
        box = pygame.Rect(70, 292, BASE_WIDTH - 140, 330)
        pygame.draw.rect(surface, (16, 18, 28), box, border_radius=10)
        pygame.draw.rect(surface, (180, 120, 50), box, 2, border_radius=10)
        cap = small.render(t("story_workshop"), True, (255, 160, 70))
        surface.blit(cap, (box.x + 16, box.y + 6))
        flags = self.state.get("flags") or {}
        window = 7
        start = max(0, min(self.shop_index - 3, len(SHOP) - window))
        y = box.y + 28
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
            line = f"{mark}{t(label)}"
            surface.blit(small.render(line, True, col), (row.x + 8, row.y + 8))
            extra_s = small.render(extra, True, col)
            surface.blit(extra_s, (row.right - extra_s.get_width() - 12, row.y + 8))
            y += 40
