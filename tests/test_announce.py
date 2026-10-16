"""The announcements of the game: one colour per type, three sizes, and the ship HUD left alone."""
import math

import pygame
import pytest

import announce
import story_state as ss
from i18n import t
from story import StoryHub
from test_smoke import run  # noqa: F401  (fixture)


# ------------------------------------------------------------------ colour helpers (CIELAB)
def _lab(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = map(f, c[:3])
    x = (r * .4124 + g * .3576 + b * .1805) / .95047
    y = r * .2126 + g * .7152 + b * .0722
    z = (r * .0193 + g * .1192 + b * .9505) / 1.08883
    h = lambda v: v ** (1 / 3) if v > 0.008856 else 7.787 * v + 16 / 116
    fx, fy, fz = h(x), h(y), h(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _de(a, b):
    return math.dist(_lab(a), _lab(b))


# the colours of the ship HUD (hud_gauge.py and Game._palette_score_color): they tell the hull and the player apart
SHIP_HUD = {
    "score red": (255, 130, 110), "score green": (110, 230, 140), "score violet": (210, 140, 255),
    "score argent": (210, 220, 235), "score blue": (120, 180, 255), "score gold": (255, 210, 90),
    "gauge red": (230, 140, 140), "gauge green": (120, 200, 140), "gauge violet": (200, 150, 230),
    "gauge gold": (255, 230, 80), "gauge blue": (140, 230, 255), "gauge orange": (255, 220, 40),
    "number gold": (255, 230, 140), "number blue": (180, 230, 255), "number orange": (255, 220, 160),
}


# ------------------------------------------------------------------ the table
def test_the_table_has_seven_types_with_the_agreed_colours():
    assert announce.COLORS == {
        "gain": (25, 255, 236), "success": (70, 255, 0), "reward": (255, 25, 148), "info": (90, 120, 255),
        "danger": (255, 20, 10), "special": (255, 132, 0), "neutral": (140, 145, 170),
    }
    assert len(set(announce.COLORS.values())) == 7


def test_the_types_are_told_apart_from_each_other():
    names = list(announce.COLORS)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert _de(announce.COLORS[a], announce.COLORS[b]) > 30, (a, b)


def test_the_colours_stay_clear_of_the_ship_hud_colours():
    for name, col in announce.COLORS.items():
        for hud, hc in SHIP_HUD.items():
            assert _de(col, hc) >= 25, (name, hud)


def test_the_palette_colours_of_the_score_are_the_ones_measured(run):
    g = run.game
    for pal in ("blue", "gold", "red", "green", "violet", "argent"):
        assert g._palette_score_color(pal) == {k: v for k, v in SHIP_HUD.items() if k.startswith("score ")}["score " + pal]


# ------------------------------------------------------------------ the three levels
def test_three_levels_big_to_small_and_a_stronger_plate_for_the_bigger(run):
    g = run.game
    L = announce.LEVELS
    assert (g.big_font.get_height() > g.medium_font.get_height() > g.font.get_height())
    assert [getattr(g, L[k]["font"]) for k in ("major", "standard", "discreet")] == [g.big_font, g.medium_font, g.font]
    assert L["major"]["plate"] > L["standard"]["plate"] > L["discreet"]["plate"]
    assert L["major"]["pad"][0] > L["standard"]["pad"][0] > L["discreet"]["pad"][0]


def test_each_banner_kind_has_one_colour_type_and_one_level():
    expect = {
        "1up": ("gain", "standard"), "ach": ("reward", "standard"), "live": ("special", "standard"),
        "phen": ("special", "standard"), "stage": ("special", "standard"),
        "pad": ("danger", "discreet"), "system": ("neutral", "discreet"),
    }
    for kind, style in expect.items():
        assert announce.style_of(kind) == style
    assert announce.style_of("") == announce.style_of("what") == ("neutral", "discreet")
    for ctype, level in announce.KIND_STYLE.values():
        assert ctype in announce.COLORS and level in announce.LEVELS


def test_a_text_too_wide_steps_down_a_size(run):
    g = run.game
    assert announce.fit_font(g, "major", "GO") is g.big_font
    wide = "X" * 80
    font = announce.fit_font(g, "major", wide, pad_x=32)
    assert font is not g.big_font and font.size(wide)[0] + 64 <= announce.MAX_WIDTH or font is g.menu_font
    assert announce.fit_font(g, "standard", "1UP") is g.medium_font
    assert announce.fit_font(g, "discreet", "PAD") is g.font


def _spy_draw(game):
    calls = []
    real = announce.draw

    def spy(g, surface, text, ctype, level, center, **kw):
        calls.append({"text": text, "ctype": ctype, "level": level, "center": center, **kw})
        return real(g, surface, text, ctype, level, center, **kw)

    announce.draw = spy
    return calls, real


def _banner(run, msg, kind):
    g = run.game
    g.cheat_msg, g.cheat_kind, g.cheat_msg_timer = msg, kind, 2.0
    calls, real = _spy_draw(g)
    try:
        g._draw_cheat_message()
    finally:
        announce.draw = real
    return calls


def test_the_banners_take_their_colour_and_size_from_their_kind(run):
    for kind, (ctype, level) in announce.KIND_STYLE.items():
        calls = _banner(run, "TEXTE", kind)
        assert len(calls) == 1 and calls[0]["ctype"] == ctype and calls[0]["level"] == level, kind


def test_the_one_up_blinks_and_the_others_do_not_blink_to_white(run):
    g = run.game
    seen = set()
    for i in range(12):
        g.cheat_msg, g.cheat_kind, g.cheat_msg_timer = "1UP", "1up", 2.0 - i * 0.05
        calls, real = _spy_draw(g)
        try:
            g._draw_cheat_message()
        finally:
            announce.draw = real
        seen.add(calls[0]["color"])
    assert announce.GAIN in seen and len(seen) == 2
    g.cheat_msg, g.cheat_kind, g.cheat_msg_timer = "CODE", "live", 2.0
    calls, real = _spy_draw(g)
    try:
        g._draw_cheat_message()
    finally:
        announce.draw = real
    col = calls[0]["color"]
    assert all(c <= b for c, b in zip(col, announce.SPECIAL))        # it breathes darker, never whiter


def test_the_banner_is_drawn_in_the_colour_of_its_type_and_the_shared_text_is_untouched(run):
    g = run.game
    surf = pygame.Surface((1280, 720))
    surf.fill((0, 0, 0))
    g._txt(g.medium_font, "UNIQUE-BANNER", announce.GAIN)
    shared = g._txt(g.medium_font, "UNIQUE-BANNER", announce.GAIN)
    before = shared.get_alpha()
    announce.draw(g, surf, "UNIQUE-BANNER", "gain", "standard", (640, 360), glow=1.0, alpha=120)
    assert g._txt(g.medium_font, "UNIQUE-BANNER", announce.GAIN).get_alpha() == before
    cyan = sum(1 for x in range(0, 1280, 2) for y in range(300, 420, 2)
               if surf.get_at((x, y))[1] > 150 and surf.get_at((x, y))[2] > 150 and surf.get_at((x, y))[0] < 90)
    assert cyan > 20


def test_a_text_banner_is_opaque_and_its_plate_darkens_the_background(run):
    g = run.game
    surf = pygame.Surface((1280, 720))
    surf.fill((200, 200, 200))
    announce.draw(g, surf, "OK", "success", "major", (640, 360))
    assert surf.get_at((640 - 80, 360))[0] < 150                              # the margin of the plate is dark
    assert tuple(surf.get_at((5, 5)))[:3] == (200, 200, 200)                  # and only there


def test_a_plate_gets_darker_with_the_level(run):
    g = run.game
    lum = {}
    for level in ("discreet", "standard", "major"):
        surf = pygame.Surface((400, 200))
        surf.fill((255, 255, 255))
        img = announce.draw(g, surf, "IIII", "neutral", level, (200, 100))
        pad_y = announce.LEVELS[level]["pad"][1]
        lum[level] = surf.get_at((200, 100 - img.get_height() // 2 - pad_y // 2))[0]     # the margin above the text
    assert lum["major"] < lum["standard"] < lum["discreet"] < 255


# ------------------------------------------------------------------ the events
def test_the_pad_message_and_the_screenshot_have_their_own_kind(run):
    import inspect
    import game as game_mod
    src = inspect.getsource(game_mod.Game)
    assert 'self.cheat_kind = "pad"' in src and 'self.cheat_kind = "system"' in src


def test_game_over_is_a_major_danger_announcement(run):
    g = run.game
    import inspect
    src = inspect.getsource(type(g)._draw_gameover_card)
    assert '"danger", "major"' in src


def test_the_new_record_title_is_a_major_reward_announcement():
    import inspect
    import draw_frame
    src = inspect.getsource(draw_frame.draw_hs_enter)
    assert '"new_record"' in src and '"reward", "major"' in src


def test_the_vip_banner_is_major_green_when_saved_and_red_when_lost(run):
    import escort
    g = run.game
    form = escort.EscortFormation.__new__(escort.EscortFormation)
    cruise = type("C", (), {"destroyed": True})()
    form.cruise, form.won = cruise, False
    g.formation = form
    calls, real = _spy_draw(g)
    try:
        escort.banner(g, pygame.Surface((1280, 720)))
        cruise.destroyed, form.won = False, True
        escort.banner(g, pygame.Surface((1280, 720)))
        form.won = False
        escort.banner(g, pygame.Surface((1280, 720)))
    finally:
        announce.draw = real
    assert [(c["ctype"], c["level"]) for c in calls] == [("danger", "major"), ("success", "major")]
    assert calls[0]["text"] == t("story_vip_lost") and calls[1]["text"] == t("story_vip_safe")


# ------------------------------------------------------------------ the adventure toast
def _hub():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.pane = "map"
    return hub


def test_a_won_mission_is_a_standard_green_toast_and_a_lost_one_a_red_one():
    hub = _hub()
    hub.apply_result("ch1_sortie", 1200, True, {"bird1": 10})
    assert hub.toast_kind == "success" and hub._toast_level() == "standard"
    hub = _hub()
    hub.apply_result("ch1_sortie", 0, False)
    assert hub.toast_kind == "danger" and hub._toast_level() == "standard"


def test_a_fallen_veteran_gets_a_red_message_on_the_slot_list():
    st = ss.create_slot(1, "NOVA", "veteran")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.open_slot(1)
    hub.apply_result("ch1_sortie", 0, False)
    assert hub.state.get("fallen") and hub.toast_kind == "danger"


def test_the_kind_of_the_toast_survives_the_return_from_a_mission(run):
    from test_loot_in_mission import _launch, _in_play
    _launch(run)
    g = run.game
    _in_play(run)
    g.stage_transition = "fly_up"                      # the mission was won: banked on the way out
    g._quit_to_menu()
    assert g.story.toast and g.story.toast_kind == "success"
    _launch(run)
    g = run.game
    _in_play(run)
    g.adventure["loot"] = "genesis"
    g.stage_transition = "fly_up"
    g._quit_to_menu()
    assert g.story.toast_kind == "gain"                # an item found is a gain


def test_the_toast_kinds_of_the_hub():
    hub = _hub()
    assert hub._toast_level() == ""                     # no toast, no level
    hub.toast, hub.toast_kind = "x", "success"
    assert hub._toast_level() == "standard"
    for kind in ("reward", "gain", "special", "info"):
        hub.toast_kind = kind
        assert hub._toast_level() == "discreet"
    assert set(announce.TOAST_COLOR.values()) <= set(announce.COLORS)


def test_the_cheat_toast_is_orange():
    from types import SimpleNamespace
    hub = _hub()
    for c in "UNLK":
        hub.type_key(SimpleNamespace(key=ord(c.lower()), unicode=c))
    assert hub.toast == t("story_cheat_on") and hub.toast_kind == "special"
    assert announce.color_of(announce.TOAST_COLOR[hub.toast_kind]) == announce.SPECIAL


def test_the_toast_kind_follows_the_slot_when_the_game_is_rebuilt():
    hub = _hub()
    hub.resume(1, "message", "map", "danger")
    assert hub.toast == "message" and hub.toast_kind == "danger"
    hub.resume(1, "message")                           # the old call: the neutral type
    assert hub.toast_kind == "info"


def test_the_toast_is_drawn_in_its_colour_with_its_plate(run):
    g = run.game
    hub = _hub()
    hub.toast, hub.toast_kind = "MISSION REUSSIE", "success"
    surf = pygame.Surface((1280, 720))
    hub.draw(surf, g.font, g.medium_font, g.font)
    green = 0
    for x in range(300, 980):
        for y in range(600, 660):
            r, gg, b = surf.get_at((x, y))[:3]
            if gg > 200 and r < 120 and b < 80:
                green += 1
    assert green > 30


def test_a_long_toast_shrinks_to_the_box_instead_of_overflowing(run):
    g = run.game
    hub = _hub()
    hub.toast, hub.toast_kind = "MISSION REUSSIE " * 12, "success"
    surf = pygame.Surface((1280, 720))
    hub.draw(surf, g.font, g.medium_font, g.font)
    for y in range(600, 660):
        for x in (0, 1, 2, 3, 1276, 1277, 1278, 1279):
            r, gg, b = surf.get_at((x, y))[:3]
            assert not (gg > 200 and r < 120 and b < 80)


def test_the_invaders_points_are_cyan():
    import inspect
    import invaders
    assert "announce.GAIN" in inspect.getsource(invaders)
