"""The bar of the Phobos station: a scene told the first time the Add-On is available, and a fourth paragraph in the
Extras tab (the Add-On menu) from then on.

The scene has its picture and its video, the theme "Nostalgie pour Elise" under the text (low, then back to normal in the
Add-On menu), *Phoenix* in italics, and it ends straight in the Add-On menu (through a fade to black). It stays in the
journal, where it can be watched again."""
import os

import pygame
import pytest

import story as story_mod
import story_state as ss
from i18n import t
from settings import asset_path, BASE_WIDTH, BASE_HEIGHT
from story import DOORS, StoryHub, _italic_runs, _wrap_marked
from test_smoke import run  # noqa: F401  (fixture)

ID = ss.BAR_SCENE


def _hub(addon=True, seen=False, intro=True):
    st = ss.create_slot(1, "NOVA", "normal")
    if intro:
        ss.mark_intro_seen(st)
    if seen:
        ss.mark_scene_seen(st, ID)
    ss.save_state(ss.story_path(1), st)
    hub = StoryHub()
    hub.addon_ready = lambda: addon
    hub.open_slot(1)
    return hub


def _open_bar(hub):
    """A on the Phobos bar paragraph of the Extras tab."""
    hub.screen = "hub"
    hub.pane = "extras"
    hub.extras_index = len(DOORS)
    return hub.confirm()


def _wait(hub, seconds=1.0):
    for _ in range(int(seconds / 0.25) + 1):
        hub.update(0.25)


def _draw(hub, run):
    surf = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    hub.draw(surf, run.game.font, run.game.medium_font, run.game.font)
    return surf


# ------------------------------------------------------------------ the scene itself
def test_the_scene_has_a_picture_a_clip_a_title_and_the_text():
    scene = ss.scene_of(ID)
    assert scene and scene["slides"] == [("bar_phobos", "story_scene_bar")]
    assert os.path.exists(asset_path("story", "bar_phobos.jpg")) and ss.clip_path("bar_phobos")
    assert os.path.getsize(ss.clip_path("bar_phobos")) > 50000
    assert scene["door"] == "addon" and scene["music"] == "nostalgie_elise"
    assert t(scene["title"]) == "Bar de la station Phobos"
    assert t("story_door_addon_t") == "BAR DE LA STATION PHOBOS" == t("story_door_addon_t").upper()    # like OPTIONS, JUKEBOX...
    text = t("story_scene_bar")
    assert text.startswith("La porte du sas siffle en s’ouvrant")
    assert text.endswith("Et la partie commence…")
    assert text.count("\n\n") == 7                                   # eight paragraphs, with a pause between
    assert "FREE PLAY. APPUYEZ SUR SELECT(5) POUR METTRE UN CRÉDIT PUIS SUR START(1) POUR JOUER." in text.split("\n")
    assert "du jeu *Phoenix* de Taito" in text and text.count("*") == 2
    assert "..." not in text


def test_the_scene_is_not_a_mission_scene_and_is_in_every_language_table():
    from i18n import T, LANG_CODES
    assert ID not in ss.SCENES and ss.scene_of("dome_1") and ss.scene_of("nothing") is None
    for key in ("story_scene_bar", "story_scene_bar_t", "story_door_addon", "story_door_addon_t", "story_scene_door"):
        assert set(T[key]) == set(LANG_CODES) and t(key), key


def test_the_scene_is_due_only_with_the_addon_and_once_per_save():
    st = ss.create_slot(1, "NOVA", "normal")
    assert ss.bar_due(st, True) and not ss.bar_due(st, False)
    ss.mark_scene_seen(st, ID)
    assert not ss.bar_due(st, True)


# ------------------------------------------------------------------ the Extras tab
def test_the_extras_tab_has_the_bar_as_a_fifth_paragraph_only_with_the_addon():
    assert DOORS == ("achievements", "jukebox", "credits", "options")
    assert _hub(addon=False).doors() == DOORS
    hub = _hub(addon=True)
    assert hub.doors() == DOORS + ("addon",)
    hub.pane = "extras"
    hub.extras_index = 3
    hub.nav_v(1)
    assert hub.extras_index == 4
    hub.nav_v(1)
    assert hub.extras_index == 4                                      # the last one
    ss.mark_scene_seen(hub.state, ID)                                 # (the first time its scene comes first)
    assert hub.confirm() == {"door": "addon"}


def test_without_the_addon_the_tab_goes_no_further_than_the_options():
    hub = _hub(addon=False)
    hub.pane = "extras"
    hub.extras_index = 3
    hub.nav_v(1)
    assert hub.extras_index == 3 and hub.confirm() == {"door": "options"}


def test_the_addon_going_away_does_not_leave_the_cursor_on_nothing():
    hub = _hub(addon=True)
    hub.pane = "extras"
    hub.extras_index = 4
    hub.addon_ready = lambda: False
    assert hub.confirm() == {"door": "options"}


def test_the_bar_is_the_concert_scene_picture_and_loop():
    """The bar with the stage of the future concert of Lyra Voss (the Phoenix cabinet in the middle, the stage and the old
    computers on the right): the poster is 1792 x 1008, the clip (no sound) is about 9.5 s and starts over without a cut."""
    import subprocess
    pic = pygame.image.load(asset_path("story", "bar_phobos.jpg"))
    assert pic.get_size() == (1792, 1008)
    clip = ss.clip_path("bar_phobos")
    assert os.path.getsize(clip) > 100000
    import videoclip
    exe = videoclip.find_ffmpeg()
    if not exe:
        pytest.skip("no ffmpeg to read the clip")
    info = subprocess.run([exe, "-hide_banner", "-i", clip], capture_output=True, text=True).stderr
    assert "752x416" in info and "Audio:" not in info
    import re
    h, m, sec = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info).groups()
    length = int(h) * 3600 + int(m) * 60 + float(sec)
    assert 9.0 < length < 10.0                                      # (the old bar clip lasted 5.5 s)
    # the poster is the first picture of the clip: the same scene, so the same colours on a coarse grid
    out = subprocess.run([exe, "-v", "error", "-i", clip, "-frames:v", "1", "-vf", "scale=8:4", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    small = pygame.transform.smoothscale(pic, (8, 4))
    ref = pygame.image.tobytes(small, "RGB")
    assert len(out) == len(ref) == 96
    assert sum(abs(a - b) for a, b in zip(out, ref)) / 96 < 25


def test_the_tab_draws_five_paragraphs_with_the_bar_title(run):
    hub = _hub(addon=True)
    hub.pane = "extras"
    hub.extras_index = 4
    texts = []
    real = story_mod._text

    def spy(surface, font, text, *a, **k):
        texts.append(text)
        return real(surface, font, text, *a, **k)
    story_mod._text = spy
    try:
        _draw(hub, run)
    finally:
        story_mod._text = real
    assert any(x == "BAR DE LA STATION PHOBOS" for x in texts)
    for door in DOORS:
        assert any(t(door) in x for x in texts), door
    assert any(t("story_door_addon").split()[0] in x for x in texts)


def test_the_five_paragraphs_fit_between_the_title_and_the_tabs(run):
    """The boxes are drawn smaller with five of them: the last one ends above the row of tabs."""
    hub = _hub(addon=True)
    hub.pane = "extras"
    boxes = []
    real = story_mod.menu_ui.panel                  # the paragraphs are menu panels (the chosen one lit)

    def spy(surface, rect, *a, **k):
        boxes.append(pygame.Rect(rect))
        return real(surface, rect, *a, **k)
    story_mod.menu_ui.panel = spy
    try:
        _draw(hub, run)
    finally:
        story_mod.menu_ui.panel = real
    paragraphs = [b for b in boxes if b.width == 860]
    assert len(paragraphs) == 5 and paragraphs[-1].bottom < BASE_HEIGHT - 90
    assert paragraphs[0].top > 70                                                   # below the title
    assert all(a.bottom < b.top for a, b in zip(paragraphs, paragraphs[1:]))        # they do not touch
    assert all(b.height >= 95 for b in paragraphs)


# ------------------------------------------------------------------ when it is told
def test_opening_a_save_or_a_new_pilot_never_tells_the_scene_by_itself(run):
    hub = _hub(addon=True)
    assert hub.screen == "hub" and hub.scene_id is None and hub.bar_due()      # nothing started on its own
    st = ss.create_slot(2, "ACE", "normal")
    ss.save_state(ss.story_path(2), st)
    hub.open_slots()
    hub.sel, hub.col = 1, 0
    hub.confirm()
    assert hub.screen == "intro" and hub.scene_id is None                       # the story introduction, as always
    _wait(hub)
    for _ in range(len(hub.intro_slides)):
        hub.confirm()
        _wait(hub)
    assert hub.screen == "hub" and hub.scene_id is None                         # and then the hangar, not the bar


def test_the_first_a_on_the_bar_paragraph_tells_the_scene(run):
    hub = _hub(addon=True)
    assert _open_bar(hub) is None
    assert hub.screen == "intro" and hub.scene_id == ID and hub.scene_door == "addon" and not hub.scene_launch
    assert hub.intro_slides == ss.scene_of(ID)["slides"] and hub.extras_index == 4
    assert hub.intro_return == "extras"
    _draw(hub, run)


def test_the_other_paragraphs_never_tell_it():
    hub = _hub(addon=True)
    for i, door in enumerate(DOORS):
        hub.pane, hub.extras_index = "extras", i
        assert hub.confirm() == {"door": door} and hub.screen == "hub"


def test_once_seen_a_on_the_bar_paragraph_opens_the_addon_menu_at_once():
    hub = _hub(addon=True, seen=True)
    assert _open_bar(hub) == {"door": "addon"} and hub.screen == "hub"


def test_it_is_told_again_in_a_save_that_has_not_seen_it():
    seen = _hub(addon=True, seen=True)
    assert _open_bar(seen) == {"door": "addon"}
    fresh = _hub(addon=True)
    assert _open_bar(fresh) is None and fresh.scene_id == ID


def test_without_the_addon_the_cursor_cannot_reach_a_bar_and_no_scene_is_told():
    hub = _hub(addon=False)
    hub.pane, hub.extras_index = "extras", 5
    assert hub.confirm() == {"door": "options"} and hub.screen == "hub" and hub.scene_id is None


def test_the_intro_replayed_from_the_journal_does_not_tell_the_bar():
    hub = _hub(addon=True)
    hub.start_intro(back_to="log")
    hub.back()
    assert hub.screen == "hub" and hub.pane == "log" and hub.scene_id is None


# ------------------------------------------------------------------ how it ends
def test_the_last_press_asks_for_the_addon_menu_and_locks_the_scene():
    hub = _hub()
    _open_bar(hub)
    assert hub.confirm() is None                                       # a press at the very start is ignored
    _wait(hub)
    spec = hub.confirm()
    assert spec == {"door": "addon", "scene": True} and hub.scene_closing
    assert hub.screen == "intro"                                       # still on the picture: the game fades to black
    assert not ss.scene_seen(hub.state, ID)
    assert hub.confirm() is None and hub.screen == "intro"             # a second press does nothing
    hub.back()
    assert hub.screen == "intro"                                       # nor does escape


def test_finishing_the_scene_remembers_it_and_puts_the_tab_on_the_addon():
    hub = _hub()
    _open_bar(hub)
    _wait(hub)
    hub.confirm()
    hub.finish_scene("addon")
    assert hub.screen == "hub" and hub.pane == "extras" and hub.extras_index == 4
    assert ss.scene_seen(hub.state, ID) and not hub.scene_closing and hub.scene_door is None
    assert ss.load_state(ss.story_path(1))["flags"][ss.scene_flag(ID)] is True      # saved
    assert not hub.bar_due() and _open_bar(hub) == {"door": "addon"}


def test_finishing_a_scene_with_a_door_always_lands_on_that_paragraph_of_the_extras_tab():
    hub = _hub()
    hub.start_scene(ID, back_to="log", door="addon")                   # (whatever the scene was started from)
    hub.extras_index = 0
    hub.finish_scene("addon")
    assert hub.pane == "extras" and hub.extras_index == 4 and hub.screen == "hub"


def test_skipping_the_scene_asks_for_the_addon_menu_like_its_end():
    hub = _hub()
    _open_bar(hub)
    assert hub.take_door_request() is None
    hub.back()
    assert hub.scene_closing and hub.screen == "intro"                  # still on the picture: the game fades to black
    assert hub.take_door_request() == {"door": "addon", "scene": True}
    assert hub.take_door_request() is None                              # asked once
    hub.back()
    assert hub.take_door_request() is None                              # a second Esc does not ask again
    hub.finish_scene("addon")
    assert hub.screen == "hub" and hub.pane == "extras" and hub.extras_index == 4
    assert ss.scene_seen(hub.state, ID) and hub.scene_door is None


def test_the_last_slide_says_where_it_leads(run):
    hub = _hub()
    _open_bar(hub)
    texts = []
    real = story_mod._text

    def spy(surface, font, text, *a, **k):
        texts.append(text)
        return real(surface, font, text, *a, **k)
    story_mod._text = spy
    try:
        _draw(hub, run)
    finally:
        story_mod._text = real
    assert hub.help_items()[0][0] == ("ok", "hint_play_addon")        # the help bar says where it leads


# ------------------------------------------------------------------ the journal
def test_the_scene_is_in_the_journal_and_can_be_watched_again_without_the_door():
    hub = _hub(seen=True)
    entries = hub.log_entries()
    assert {"scene": ID} in entries
    assert ss.log_text({"scene": ID}, t) == "Revoir : Bar de la station Phobos"
    hub.pane = "log"
    hub.log_cursor = [e for e in hub.replay_entries()].index({"scene": ID})
    assert hub.confirm() is None
    assert hub.screen == "intro" and hub.scene_id == ID and hub.scene_door is None and hub.intro_return == "log"
    _wait(hub)
    assert hub.confirm() is None                                       # no fade, no Add-On: back to the journal
    assert hub.screen == "hub" and hub.pane == "log"


def test_the_journal_lists_the_mission_scenes_before_the_bar():
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_scene_seen(st, ID)
    ss.mark_scene_seen(st, "dome_1")
    assert ss.scenes_seen(st) == ["dome_1", ID]


# ------------------------------------------------------------------ the music
def test_the_scene_asks_for_its_theme_low_and_back_to_normal_when_closed():
    hub = _hub()
    assert hub.scene_music() is None
    _open_bar(hub)
    assert hub.scene_music() == ("nostalgie_elise", ss.BAR_MUSIC_LEVEL) and ss.BAR_MUSIC_LEVEL < 0.5
    _wait(hub)
    hub.confirm()
    assert hub.scene_music() == ("nostalgie_elise", 1.0)
    hub.finish_scene("addon")
    assert hub.scene_music() is None
    hub.start_scene("dome_1", back_to="map")
    assert hub.scene_music() is None                                   # the scenes of the missions have no theme of their own


@pytest.fixture
def snd(run):
    s = run.game.sounds
    s.set_music_volume(0.8)
    s.play_music("menu", fade_ms=0)
    for _ in range(3):
        s.update(0.016)
    return s


def test_the_music_level_moves_smoothly_and_comes_back(snd):
    base = snd._music_out()
    assert snd.music_level() == 1.0 and base > 0.1
    snd.set_music_level(0.3, 2.0)
    seen = []
    for _ in range(int(2.6 * 60)):
        snd.update(1 / 60)
        seen.append(snd._music_out())
    assert abs(seen[-1] - base * 0.3) < 0.002 and snd._level_spec is None
    assert all(a >= b - 1e-9 for a, b in zip(seen, seen[1:]))          # steadily down, never up
    steepest = 1.5 * (base * 0.7) / (2.0 * 60)
    assert max(abs(a - b) for a, b in zip(seen, seen[1:])) < steepest * 1.05      # no jump
    assert abs(seen[60] - (base * 0.3 + base * 0.7 * 0.5)) < 0.01     # halfway after one second...
    assert abs(seen[30] - base * (1.0 - 0.7 * 0.15625)) < 0.005       # ...and a soft start (smoothstep at a quarter: 0.156)
    snd.set_music_level(1.0, 1.0)
    for _ in range(90):
        snd.update(1 / 60)
    assert abs(snd._music_out() - base) < 0.002


def test_asking_for_the_same_level_again_does_not_restart_the_move(snd):
    snd.set_music_level(0.3, 2.0)
    for _ in range(60):
        snd.update(1 / 60)
    mid = snd._level
    for _ in range(10):
        snd.set_music_level(0.3, 2.0)                                  # (the game asks every frame)
        snd.update(1 / 60)
    assert snd._level < mid


def test_the_level_applies_to_the_music_of_any_theme_and_to_a_new_one(snd):
    snd.set_music_level(0.0, 0.0)
    assert snd._music_out() == 0.0
    snd.set_music_level(1.0, 0.0)
    assert snd._music_out() > 0.1


def test_a_theme_can_fade_out_quickly_and_the_next_come_in_slowly(snd):
    snd.play_music("nostalgie_elise", fade_ms=600, fade_in_ms=3000)
    assert snd._fading_out and snd._pending_music == "nostalgie_elise"
    assert snd._pending_fade_ms == 3000 and abs(snd._fade_timer - 0.6) < 1e-6


# ------------------------------------------------------------------ italics
def test_stars_make_italics_and_are_not_shown():
    plain, mask = _italic_runs("du jeu *Phoenix* de Taito")
    assert plain == "du jeu Phoenix de Taito"
    assert [plain[i] for i, m in enumerate(mask) if m] == list("Phoenix")
    assert _italic_runs("no stars") == ("no stars", None)
    assert _italic_runs("one * star")[1] is None and _italic_runs("a *b* c *d")[1] is None   # unpaired: left as written


def test_the_wrapped_runs_keep_the_title_in_italics_and_lose_nothing(run):
    font = run.game.font
    plain, mask = _italic_runs("Je m’approche d’une borne d’arcade du jeu *Phoenix* de Taito, dans le coin le plus sombre.")
    lines = _wrap_marked(font, plain, mask, 300)
    assert len(lines) > 1
    assert " ".join("".join(txt for _it, txt in runs) for runs in lines) == plain
    assert all(font.size("".join(txt for _it, txt in runs))[0] <= 300 for runs in lines)
    italic = "".join(txt for runs in lines for it, txt in runs if it)
    assert italic == "Phoenix"


def test_a_title_made_of_two_words_stays_in_italics_across_the_space(run):
    plain, mask = _italic_runs("le jeu *Space Invaders* de Taito")
    lines = _wrap_marked(run.game.font, plain, mask, 2000)
    assert lines == [((False, "le jeu "), (True, "Space Invaders"), (False, " de Taito"))]


def test_the_font_is_upright_again_after_the_text_is_drawn(run):
    hub = _hub()
    _open_bar(hub)
    font = run.game.font
    block, height = hub._intro_block(font)
    assert not font.get_italic() and height > 0
    pygame.image.tostring(block, "RGBA")


def test_the_italic_word_is_drawn_in_italics_in_the_text(run):
    """The slanted word is wider than the upright one, so the picture of the line differs from a plain render."""
    font = run.game.font
    story_mod._render_runs(font, ((False, "du jeu "), (True, "Phoenix")), (255, 255, 255))
    assert not font.get_italic()
    slanted = story_mod._render_runs(font, ((True, "Phoenix"),), (255, 255, 255))
    upright = story_mod._render_runs(font, ((False, "Phoenix"),), (255, 255, 255))
    assert pygame.image.tostring(slanted, "RGBA") != pygame.image.tostring(upright, "RGBA")


# ------------------------------------------------------------------ in the game: the Add-On menu from the Adventure
@pytest.fixture
def game(run):
    g = run.game
    st = ss.create_slot(1, "NOVA", "normal")
    ss.mark_intro_seen(st)
    ss.save_state(ss.story_path(1), st)
    g.menu_screen = "story_hub"
    g.story.addon_ready = lambda: True
    g.story.open_slot(1)
    g.input_grace = 0
    run.frames(2)
    return g


def _game_open_bar(g):
    """A on the Phobos bar paragraph (the game's own confirm, as the player does it)."""
    g.story.pane = "extras"
    g.story.extras_index = 4
    g.story.screen = "hub"
    return g.story.confirm() is None and g.story.screen == "intro"


def _key(run, key, frames=2):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0, scancode=0))
    run.frames(frames)


def test_a_on_the_bar_paragraph_opens_the_addon_menu_and_escape_brings_the_tab_back(game, run):
    g = game
    ss.mark_scene_seen(g.story.state, ID)                              # (the first time the scene comes first, see below)
    g.story.pane = "extras"
    g.story.extras_index = 4
    _key(run, pygame.K_RETURN)
    g.input_grace = 0
    run.frames(2)
    assert g.menu_screen == "addon" and g.story_door == "addon"
    run.frames(10)
    assert g.menu_screen == "addon"
    _key(run, pygame.K_ESCAPE, frames=3)
    assert g.menu_screen == "story_hub" and g.story.pane == "extras" and g.story.screen == "hub"
    assert g.story.extras_index == 4 and g.story_door is None


def test_the_scene_ends_with_a_fade_to_black_then_the_addon_menu(game, run):
    g = game
    assert _game_open_bar(g)
    run.frames(3)
    g.story.intro_t = 5.0
    g.input_grace = 0
    _key(run, pygame.K_RETURN, frames=1)
    assert g.story.scene_closing and g.fade_action == "story_scene_door" and g.fade_phase == "out"
    assert g.FADE_SEC >= 0.7                                          # a slow fade, not the quick one of the menus
    assert g.menu_screen == "story_hub" and g.story.screen == "intro"        # the picture stays until it is black
    run.frames(int(g.FADE_SEC * 60) + 5)
    assert g.menu_screen == "addon" and g.story_door == "addon"          # at full black the screen is changed...
    assert ss.scene_seen(g.story.state, ID) and g.story.screen == "hub" and g.story.pane == "extras"
    assert g.fade_phase == "in" and g.fade_t > 0.0                       # ...and it comes up from black
    run.frames(int(g.FADE_SEC * 60) + 30)
    assert g.fade_phase is None and g.fade_t <= 0.0                   # and it came back up from black
    assert g.FADE_SEC < 0.5                                           # the quick fade of the menus is back
    _key(run, pygame.K_ESCAPE, frames=3)
    assert g.menu_screen == "story_hub" and g.story.extras_index == 4 and g.story.pane == "extras"


def test_the_scene_music_is_low_and_comes_back_to_normal_in_the_addon_menu(game, run):
    g = game
    snd = g.sounds
    _game_open_bar(g)
    run.frames(240)
    assert snd.current_music_key() == "nostalgie_elise"
    assert snd.music_level() < 0.5
    g.story.intro_t = 5.0
    g.input_grace = 0
    _key(run, pygame.K_RETURN, frames=1)
    run.frames(int(g.FADE_SEC * 60) + 400)
    assert g.menu_screen == "addon" and snd.current_music_key() == "nostalgie_elise"       # the same theme goes on
    assert snd.music_level() == 1.0


def test_the_theme_goes_back_to_the_menu_one_when_the_scene_is_watched_again_and_closed(game, run):
    g = game
    snd = g.sounds
    g.story.state["flags"][ss.scene_flag(ID)] = True
    g.story.pane = "log"
    g.story.log_cursor = g.story.replay_entries().index({"scene": ID})
    _key(run, pygame.K_RETURN)
    run.frames(240)
    assert g.story.screen == "intro" and snd.current_music_key() == "nostalgie_elise" and snd.music_level() < 0.5
    g.story.intro_t = 5.0
    _key(run, pygame.K_RETURN, frames=1)
    assert g.story.screen == "hub" and g.story.pane == "log" and g.menu_screen == "story_hub"
    run.frames(400)
    assert snd.current_music_key() == "menu" and snd.music_level() == 1.0


def test_the_scene_theme_comes_in_slowly_after_a_quick_fade_of_the_menu_one(game, run):
    g = game
    calls = []
    real = g.sounds.play_music

    def spy(key, *a, **k):
        calls.append((key, k))
        return real(key, *a, **k)
    g.sounds.play_music = spy
    try:
        _game_open_bar(g)
        run.frames(5)
    finally:
        g.sounds.play_music = real
    scene = [k for key, k in calls if key == "nostalgie_elise"]
    assert scene and scene[0]["fade_in_ms"] >= 2000 and scene[0]["fade_ms"] <= 1000


def test_the_first_a_on_the_bar_paragraph_of_the_game_shows_the_scene_not_the_menu(game, run):
    g = game
    g.story.pane = "extras"
    g.story.extras_index = 4
    _key(run, pygame.K_RETURN)
    assert g.menu_screen == "story_hub" and g.story.screen == "intro" and g.story.scene_id == ID
    assert getattr(g, "story_door", None) is None
    run.frames(30)
    assert g.menu_screen == "story_hub" and g.story.screen == "intro"


def test_escape_on_the_scene_also_fades_to_black_then_opens_the_addon_menu(game, run):
    g = game
    g.story.pane = "extras"
    g.story.extras_index = 4
    _key(run, pygame.K_RETURN)
    run.frames(3)
    _key(run, pygame.K_ESCAPE, frames=2)
    assert g.story.scene_closing and g.fade_action == "story_scene_door" or g.fade_phase == "out"
    assert g.story.screen == "intro"
    run.frames(int(g.FADE_SEC * 60) + 5)
    assert g.menu_screen == "addon" and g.story_door == "addon" and ss.scene_seen(g.story.state, ID)
    run.frames(int(g.FADE_SEC * 60) + 30)
    _key(run, pygame.K_ESCAPE, frames=3)
    assert g.menu_screen == "story_hub" and g.story.pane == "extras" and g.story.extras_index == 4
    g.input_grace = 0
    _key(run, pygame.K_RETURN)
    g.input_grace = 0
    run.frames(2)
    assert g.menu_screen == "addon"                                    # the second time: no scene
