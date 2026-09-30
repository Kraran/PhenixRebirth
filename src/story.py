"""
Story / Adventure hub — Hangar, Mission map, Mission log.

Arcade loop never imports combat rules from here. This module only
owns the pre-run screens and the story.json stub.
"""
import json
import os
import pygame
from settings import BASE_WIDTH, BASE_HEIGHT, asset_path, user_data_dir
from i18n import t


PANES = ("log", "hangar", "map")

SHOP = [
    # id, i18n label, cost, locked_until_flag or None
    ("speed_80", "story_shop_speed80", 400, "ch1_speed_80"),
    ("lives_2", "story_shop_lives2", 600, "ch1_life_2"),
    ("dome_dur", "story_shop_dome", 800, "dome_online"),
]


def _story_path():
    return os.path.join(user_data_dir(), "story.json")


def default_state():
    return {
        "version": 1,
        "chapter": 1,
        "credits": 0,
        "flags": {"bestiary_s1": True},
        "cleared": [],
        "slots": [
            {
                "id": "shield", "owned": True, "tint": "red",
                "lives": 1, "speed": 60, "dome": False,
                "dome_dur": 60, "dome_cd": 200, "wall": "instant",
            },
            {
                "id": "phoenix", "owned": False, "tint": "argent",
                "lives": 1, "speed": 60, "phenix": False,
                "phenix_cap": 60, "wall": "instant",
            },
        ],
        "selected_slot": 0,
        "log": [],
    }


class StoryHub:
    """Three-pane hub. Left = log, center = hangar, right = map."""

    def __init__(self):
        self.state = default_state()
        self.load()
        self.pane = "hangar"
        self.zone = "slots"   # slots | shop
        self.shop_index = 0
        self._ships = {}
        self._loaded_img = False

    def load(self):
        path = _story_path()
        if not os.path.isfile(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                base = default_state()
                base.update({k: data.get(k, base[k]) for k in base})
                if isinstance(data.get("slots"), list) and data["slots"]:
                    base["slots"] = data["slots"]
                self.state = base
        except Exception:
            pass

    def save(self):
        try:
            with open(_story_path(), "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception:
            pass

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
                img = pygame.transform.smoothscale(img, (220, 132))
                self._ships[key] = img
            except Exception:
                self._ships[key] = None

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
            # edge of slots → change pane
        idx = PANES.index(self.pane)
        self.pane = PANES[max(0, min(len(PANES) - 1, idx + direction))]
        self.zone = "slots"

    def nav_v(self, direction):
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
        if self.pane != "hangar" or self.zone != "shop":
            return False
        sid, _label, cost, need = SHOP[self.shop_index]
        flags = self.state.get("flags") or {}
        if need and not flags.get(need):
            return False
        if int(self.state.get("credits", 0)) < cost:
            return False
        slot = self._slot()
        if slot is None:
            return False
        if sid == "speed_80" and int(slot.get("speed", 60)) < 80:
            slot["speed"] = 80
        elif sid == "lives_2" and int(slot.get("lives", 1)) < 2:
            slot["lives"] = 2
        elif sid == "dome_dur" and not slot.get("dome"):
            return False
        else:
            return False
        self.state["credits"] = int(self.state.get("credits", 0)) - cost
        self.save()
        return True

    def _slot(self):
        slots = self.state.get("slots") or []
        i = int(self.state.get("selected_slot", 0))
        if 0 <= i < len(slots):
            return slots[i]
        return None

    def flag(self, name):
        return bool((self.state.get("flags") or {}).get(name))

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
            self._draw_placeholder(surface, font, t("story_map_empty"))
        else:
            self._draw_log(surface, font, small)

        hint = small.render(t("story_hint"), True, (140, 140, 170))
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

    def _draw_placeholder(self, surface, font, msg):
        box = pygame.Rect(80, 90, BASE_WIDTH - 160, BASE_HEIGHT - 180)
        pygame.draw.rect(surface, (18, 20, 32), box, border_radius=10)
        pygame.draw.rect(surface, (70, 90, 130), box, 2, border_radius=10)
        s = font.render(msg, True, (160, 170, 200))
        surface.blit(s, (box.centerx - s.get_width() // 2, box.centery - s.get_height() // 2))

    def _draw_log(self, surface, font, small):
        box = pygame.Rect(80, 90, BASE_WIDTH - 160, BASE_HEIGHT - 180)
        pygame.draw.rect(surface, (18, 20, 32), box, border_radius=10)
        pygame.draw.rect(surface, (70, 90, 130), box, 2, border_radius=10)
        log = self.state.get("log") or []
        if not log:
            s = font.render(t("story_log_empty"), True, (160, 170, 200))
            surface.blit(s, (box.centerx - s.get_width() // 2, box.centery - s.get_height() // 2))
            return
        y = box.y + 20
        for line in log[-12:]:
            s = small.render(str(line), True, (200, 200, 220))
            surface.blit(s, (box.x + 24, y))
            y += 28

    def _draw_hangar(self, surface, font, medium, small):
        slots = self.state.get("slots") or []
        sel = int(self.state.get("selected_slot", 0))
        slot_w, slot_h = 520, 200
        gap = 24
        x0 = (BASE_WIDTH - (slot_w * 2 + gap)) // 2
        y0 = 70
        for i, sl in enumerate(slots[:2]):
            r = pygame.Rect(x0 + i * (slot_w + gap), y0, slot_w, slot_h)
            owned = bool(sl.get("owned"))
            focus = self.pane == "hangar" and self.zone == "slots" and i == sel
            border = (80, 220, 255) if focus else ((70, 80, 100) if not owned else (180, 120, 60))
            pygame.draw.rect(surface, (16, 18, 28), r, border_radius=12)
            pygame.draw.rect(surface, border, r, 3 if focus else 2, border_radius=12)
            label = t("ship_shield") if sl.get("id") == "shield" else t("ship_phoenix")
            cap = small.render(f"SLOT {i + 1}  {label}", True, border)
            surface.blit(cap, (r.x + 16, r.y + 10))
            img = self._ships.get(sl.get("id"))
            if owned and img is not None:
                surface.blit(img, (r.centerx - img.get_width() // 2, r.y + 44))
            else:
                lock = medium.render("[X]", True, (140, 140, 150))
                surface.blit(lock, (r.centerx - lock.get_width() // 2, r.centery - 10))
                dim = small.render(t("story_locked"), True, (140, 140, 160))
                surface.blit(dim, (r.centerx - dim.get_width() // 2, r.bottom - 28))

        sl = slots[sel] if 0 <= sel < len(slots) else slots[0]
        self._draw_stats(surface, sl, small, y0 + slot_h + 16)
        self._draw_shop(surface, medium, small)
        pts = medium.render(f"{int(self.state.get('credits', 0))} PTS", True, (255, 210, 80))
        surface.blit(pts, (BASE_WIDTH // 2 - pts.get_width() // 2, BASE_HEIGHT - 92))

    def _draw_stats(self, surface, sl, small, y):
        owned = bool(sl.get("owned"))
        dome = bool(sl.get("dome"))
        cells = [
            (t("story_stat_lives"), f"{sl.get('lives', 1)}/3"),
            (t("story_stat_speed"), f"{sl.get('speed', 60)}%"),
            (t("story_stat_dome"), t("story_online") if dome else t("story_offline")),
            (t("story_stat_wall"), t("story_wall_" + str(sl.get("wall", "instant")))),
        ]
        w = 200
        x = (BASE_WIDTH - (w * 4 + 18 * 3)) // 2
        for i, (lab, val) in enumerate(cells):
            r = pygame.Rect(x + i * (w + 18), y, w, 72)
            pygame.draw.rect(surface, (16, 18, 28), r, border_radius=8)
            pygame.draw.rect(surface, (60, 70, 90), r, 1, border_radius=8)
            a = small.render(lab, True, (150, 155, 175))
            col = (255, 90, 80) if (i == 2 and not dome) else (220, 220, 235)
            if not owned:
                val = "—"
            b = small.render(val, True, col)
            surface.blit(a, (r.centerx - a.get_width() // 2, r.y + 10))
            surface.blit(b, (r.centerx - b.get_width() // 2, r.y + 36))

    def _draw_shop(self, surface, medium, small):
        box = pygame.Rect(BASE_WIDTH - 420, 70, 380, 200)
        # shop sits under stats on the right if 720p cramped — place under stats full width
        box = pygame.Rect(80, 380, BASE_WIDTH - 160, 210)
        pygame.draw.rect(surface, (16, 18, 28), box, border_radius=10)
        pygame.draw.rect(surface, (180, 120, 50), box, 2, border_radius=10)
        cap = small.render(t("story_workshop"), True, (255, 160, 70))
        surface.blit(cap, (box.x + 16, box.y + 8))
        flags = self.state.get("flags") or {}
        y = box.y + 36
        for i, (sid, label, cost, need) in enumerate(SHOP):
            locked = bool(need) and not flags.get(need)
            focus = self.zone == "shop" and i == self.shop_index
            row = pygame.Rect(box.x + 12, y, box.w - 24, 48)
            if focus:
                pygame.draw.rect(surface, (40, 36, 20), row, border_radius=6)
                pygame.draw.rect(surface, (255, 210, 80), row, 2, border_radius=6)
            col = (100, 100, 110) if locked else ((255, 230, 140) if focus else (200, 200, 210))
            mark = "> " if focus else "  "
            extra = t("story_locked") if locked else f"{cost} PTS"
            line = f"{mark}{t(label)}     {extra}"
            surface.blit(medium.render(line, True, col), (row.x + 8, row.y + 8))
            y += 52
