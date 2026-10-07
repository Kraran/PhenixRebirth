"""
Story / Adventure hub — Hangar, Mission map, Mission log.

Arcade loop never imports combat rules from here. This module owns the
pre-run screens, story.json, chapter-1 mission list and hangar shop.
Points earned in a mission are hangar credits.
"""
import json
import os
import pygame
from safe_io import atomic_write_json, backup_unreadable
from settings import BASE_WIDTH, BASE_HEIGHT, asset_path, user_data_dir
from i18n import t


PANES = ("log", "hangar", "map")

# id, i18n, cost, flag required before the row is buyable
SHOP = [
    ("speed_80", "story_shop_speed80", 400, "ch1_speed_80"),
    ("speed_100", "story_shop_speed100", 700, "ch1_speed_80"),
    ("lives_2", "story_shop_lives2", 600, "ch1_life_2"),
    ("lives_3", "story_shop_lives3", 900, "ch1_life_2"),
    ("dome_dur", "story_shop_dome", 800, "dome_online"),
    ("dome_lat", "story_shop_latency", 800, "dome_online"),
    ("wall_slow", "story_shop_wall_slow", 1000, "dome_online"),
    ("wall_immune", "story_shop_wall_immune", 1400, "dome_online"),
]

# Chapter 1: main sorties are stage-1 birds only.
# Other hulls are met (and unlocked) in Bestiary nodes.
# Phoenix hull is not granted here — end of chapter 2.
MISSIONS = [
    {
        "id": "ch1_sortie",
        "title": "story_m_sortie",
        "blurb": "story_m_sortie_b",
        "need": None,
        "content": 1,
        "speed": 1.0,
        "unlock": ["ch1_sortie", "ch1_speed_80"],
        "log": "story_log_sortie",
    },
    {
        "id": "best_s2",
        "title": "story_m_best2",
        "blurb": "story_m_best2_b",
        "need": "ch1_sortie",
        "content": 2,
        "speed": 1.0,
        "unlock": ["bestiary_s2", "ch1_life_2"],
        "log": "story_log_best2",
    },
    {
        "id": "best_s3",
        "title": "story_m_best3",
        "blurb": "story_m_best3_b",
        "need": "bestiary_s2",
        "content": 3,
        "speed": 1.0,
        "unlock": ["bestiary_s3"],
        "log": "story_log_best3",
    },
    {
        "id": "best_s4",
        "title": "story_m_best4",
        "blurb": "story_m_best4_b",
        "need": "bestiary_s3",
        "content": 4,
        "speed": 1.0,
        "unlock": ["bestiary_s4"],
        "log": "story_log_best4",
    },
    {
        "id": "ch1_gate",
        "title": "story_m_gate",
        "blurb": "story_m_gate_b",
        "need": "bestiary_s4",
        "content": 1,
        "speed": 1.15,
        "unlock": ["ch1_clear", "dome_online"],
        "log": "story_log_gate",
    },
    {
        "id": "ch2_tease",
        "title": "story_m_ch2",
        "blurb": "story_m_ch2_b",
        "need": "ch1_clear",
        "content": 0,
        "speed": 1.0,
        "unlock": [],
        "log": "",
        "playable": False,
    },
]


def _story_path():
    return os.path.join(user_data_dir(), "story.json")


def default_state():
    return {
        "version": 2,
        "chapter": 1,
        "credits": 0,
        "flags": {"bestiary_s1": True},
        "cleared": [],
        "slots": [
            {
                "id": "shield", "owned": True, "tint": "red",
                "lives": 1, "speed": 60, "dome": False,
                "dome_dur": 60, "dome_cd": 300, "wall": "instant",
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
        self.map_index = 0
        self.toast = ""
        self._ships = {}
        self._loaded_img = False

    def load(self):
        path = _story_path()
        if not os.path.isfile(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            base = default_state()
            for key in ("version", "chapter", "credits", "selected_slot"):
                if key in data:
                    base[key] = data[key]
            flags = dict(base["flags"])
            if isinstance(data.get("flags"), dict):
                flags.update(data["flags"])
            base["flags"] = flags
            if isinstance(data.get("cleared"), list):
                base["cleared"] = list(data["cleared"])
            if isinstance(data.get("log"), list):
                base["log"] = list(data["log"])
            if isinstance(data.get("slots"), list) and data["slots"]:
                merged = []
                for i, sl in enumerate(data["slots"][:2]):
                    proto = dict(base["slots"][i] if i < len(base["slots"]) else {})
                    if isinstance(sl, dict):
                        proto.update(sl)
                    merged.append(proto)
                base["slots"] = merged
            self.state = base
        except Exception:
            backup_unreadable(path)

    def save(self):
        try:
            atomic_write_json(_story_path(), self.state)
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
                img = pygame.transform.smoothscale(img, (150, 90))
                self._ships[key] = img
            except Exception:
                self._ships[key] = None

    def flag(self, name):
        return bool((self.state.get("flags") or {}).get(name))

    def _slot(self):
        slots = self.state.get("slots") or []
        i = int(self.state.get("selected_slot", 0))
        if 0 <= i < len(slots):
            return slots[i]
        return None

    def loadout(self):
        """Hull the mission actually launches. Locked Phoenix falls back to Shield."""
        slot = self._slot() or {}
        if not slot.get("owned"):
            slots = self.state.get("slots") or []
            slot = next((s for s in slots if s.get("owned")), slot)
        sid = slot.get("id") if slot.get("id") in ("shield", "phoenix") else "shield"
        return {
            "ship_id": sid,
            "tint": slot.get("tint") or ("red" if sid == "shield" else "argent"),
            "lives": max(1, int(slot.get("lives") or 1)),
            "speed_pct": max(40, min(100, int(slot.get("speed") or 60))),
            "dome": bool(slot.get("dome")),
            "dome_dur": int(slot.get("dome_dur") or 60),
            "dome_cd": int(slot.get("dome_cd") or 300),
            "wall": slot.get("wall") or "instant",
        }

    def _mission(self, index=None):
        i = self.map_index if index is None else index
        if 0 <= i < len(MISSIONS):
            return MISSIONS[i]
        return None

    def mission_open(self, mission):
        if not mission:
            return False
        need = mission.get("need")
        if need and not self.flag(need):
            return False
        return True

    def mission_playable(self, mission):
        if not self.mission_open(mission):
            return False
        if mission.get("playable") is False or int(mission.get("content") or 0) <= 0:
            return False
        return True

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
        score = max(0, int(score or 0))
        self.state["credits"] = int(self.state.get("credits", 0)) + score
        mission = next((m for m in MISSIONS if m["id"] == mission_id), None)
        if cleared and mission:
            flags = self.state.setdefault("flags", {})
            for name in mission.get("unlock") or []:
                flags[name] = True
            cleared_ids = self.state.setdefault("cleared", [])
            first = mission_id not in cleared_ids
            if first:
                cleared_ids.append(mission_id)
                line = t(mission.get("log") or "story_log_clear")
                self.state.setdefault("log", []).append(line)
            self.toast = t("story_clear").format(pts=score)
        else:
            self.toast = t("story_fail").format(pts=score)
        self.pane = "map"
        self.save()

    def _buy(self, row):
        sid, _label, cost, need = row
        flags = self.state.get("flags") or {}
        if need and not flags.get(need):
            return False
        slot = self._slot()
        if slot is None or not slot.get("owned"):
            return False
        if int(self.state.get("credits", 0)) < cost:
            return False
        if not self._apply_upgrade(slot, sid):
            return False
        self.state["credits"] = int(self.state.get("credits", 0)) - cost
        self.save()
        return True

    def _apply_upgrade(self, slot, sid):
        speed = int(slot.get("speed", 60))
        lives = int(slot.get("lives", 1))
        if sid == "speed_80":
            if speed >= 80:
                return False
            slot["speed"] = 80
            return True
        if sid == "speed_100":
            if speed < 80 or speed >= 100:
                return False
            slot["speed"] = 100
            return True
        if sid == "lives_2":
            if lives >= 2:
                return False
            slot["lives"] = 2
            return True
        if sid == "lives_3":
            if lives < 2 or lives >= 3:
                return False
            slot["lives"] = 3
            return True
        if sid == "dome_dur":
            if not slot.get("dome"):
                slot["dome"] = True
                slot["dome_dur"] = 60
                slot["dome_cd"] = int(slot.get("dome_cd") or 300)
                return True
            dur = int(slot.get("dome_dur") or 60)
            if dur >= 120:
                return False
            slot["dome_dur"] = min(120, dur + 30)
            return True
        if sid == "dome_lat":
            if not slot.get("dome"):
                return False
            cd = int(slot.get("dome_cd") or 300)
            if cd <= 180:
                return False
            slot["dome_cd"] = max(180, cd - 60)
            return True
        if sid == "wall_slow":
            if not slot.get("dome") or slot.get("wall") != "instant":
                return False
            slot["wall"] = "slow"
            return True
        if sid == "wall_immune":
            if not slot.get("dome") or slot.get("wall") != "slow":
                return False
            slot["wall"] = "immune"
            return True
        return False

    def _shop_extra(self, sid, cost, locked):
        if locked:
            return t("story_locked")
        slot = self._slot() or {}
        if sid == "speed_80" and int(slot.get("speed", 60)) >= 80:
            return t("story_owned")
        if sid == "speed_100" and int(slot.get("speed", 60)) >= 100:
            return t("story_owned")
        if sid == "speed_100" and int(slot.get("speed", 60)) < 80:
            return t("story_need_prev")
        if sid == "lives_2" and int(slot.get("lives", 1)) >= 2:
            return t("story_owned")
        if sid == "lives_3" and int(slot.get("lives", 1)) >= 3:
            return t("story_owned")
        if sid == "lives_3" and int(slot.get("lives", 1)) < 2:
            return t("story_need_prev")
        if sid == "dome_dur" and slot.get("dome") and int(slot.get("dome_dur") or 0) >= 120:
            return t("story_owned")
        if sid == "dome_lat" and not slot.get("dome"):
            return t("story_need_dome")
        if sid == "dome_lat" and int(slot.get("dome_cd") or 300) <= 180:
            return t("story_owned")
        if sid == "wall_slow" and slot.get("wall") in ("slow", "immune"):
            return t("story_owned")
        if sid == "wall_slow" and not slot.get("dome"):
            return t("story_need_dome")
        if sid == "wall_immune" and slot.get("wall") == "immune":
            return t("story_owned")
        if sid == "wall_immune" and slot.get("wall") != "slow":
            return t("story_need_prev")
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
            s = small.render(str(line), True, (200, 200, 220))
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
