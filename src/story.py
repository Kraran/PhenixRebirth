"""
Story / Adventure hub — Hangar, Mission map, Mission log.

Arcade loop never imports combat rules from here. This module draws the
pre-run screens and handles their input; the rules and the save data
(hangar, shop, missions, story_N.json) live in story_state.py, which has no
drawing code and is tested on its own. Points earned in a mission are
hangar credits.
"""
import math
import os
import random
import re

import pygame
from settings import BASE_WIDTH, BASE_HEIGHT, asset_path
from i18n import t, get_lang
from errlog import log_exc
import announce
import story_feats
import story_items
import story_state as ss
import loot
from text_cache import TextCache
import bestiary_art
import videoclip
import addon as mame_addon
import menu_ui
from story_state import MISSIONS, SHOP, log_text   # noqa: F401  (re-exported for the tests)


# The Extras tab, at the far left, holds four screens of the main menu (Achievements, Jukebox, Credits, Options) as
# paragraphs: Up / Down choose, A opens the real screen, B / Esc comes back to the same paragraph. (Left / Right change
# values in those screens, so they could not also change tab.) The order is the one of EXTRAS in the main menu
# (main_menu.EXTRAS: scores, achievements, jukebox, credits, help, add-on), Options where the help is there.
DOORS = ("achievements", "jukebox", "credits", "options")
BAR_DOOR = "addon"             # the fifth paragraph, there only when the Add-On is available: the Phobos station bar
DOOR_TITLES = {BAR_DOOR: "story_door_addon_t"}      # the paragraphs whose title is not the name of the screen
PANES = ("extras", "bestiary", "log", "hangar", "map")
CHEAT_UNLOCK = "UNLK"          # typed on the mission map: play any mission, save nothing
PORTRAIT_H = 124                 # height of a hull portrait in the hangar (the ship select screen uses 168)
GREY_MULT = (80, 80, 90, 160)    # the dimming of the ship select screen for the hull that is not chosen
CHEAT_NIX = "NIX2"             # typed in the hangar: all the Phenix missions won, the Phenix is yours, nothing saved
CHEAT_ACT2 = "2222"            # typed on the mission map: go straight to Act 2, save nothing
CHEAT_ACT3 = "3333"            # typed on the mission map: Acts 1 and 2 won, the attack on Phobos and the choice, save nothing
LOG_REPLAY_ROWS = 4            # journal: scenes to watch again, shown at once (the cursor moves in them)
LOG_STORY_ROWS = 6             # journal: lines of what happened, shown at once (they scroll)
MODE_COLORS = {"novice": (120, 200, 255), "normal": (140, 220, 160), "veteran": (255, 110, 100)}   # title of each mode card
MAP_HEAD_H = 26                # a group heading of the map (story, hunts, BONUS)
SHOP_WINDOW = 6                # workshop rows shown at once (the line under them describes a loot item)


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


def _italic_runs(line):
    """`a *Phoenix* b` -> (`a Phoenix b`, [False, ..., True, ..., False]) : the text without the stars and, for each of
    its characters, whether it is in italics (the title of a work). A line whose stars do not pair up is left as it is."""
    parts = str(line).split("*")
    if len(parts) < 3 or len(parts) % 2 == 0:
        return str(line), None
    plain, mask = "", []
    for i, part in enumerate(parts):
        plain += part
        mask.extend([i % 2 == 1] * len(part))
    return plain, mask


def _wrap_marked(font, plain, mask, width):
    """Like _wrap, for a line with italics: a list of lines, each a tuple of (italic, text) runs."""
    words = [(m.start(), m.end()) for m in re.finditer(r"\S+", plain)]
    lines, cur = [], []
    for w in words:
        trial = cur + [w]
        text = " ".join(plain[a:b] for a, b in trial)
        if cur and font.size(text)[0] > width:
            lines.append(cur)
            cur = [w]
        else:
            cur = trial
    if cur:
        lines.append(cur)
    out = []
    for line in lines:
        chars = []                                   # (character, italic)
        for k, (a, b) in enumerate(line):
            if k:
                chars.append((" ", mask[a - 1] and mask[a]))     # the space between two words of one title
            chars.extend((plain[i], mask[i]) for i in range(a, b))
        runs = []
        for ch, it in chars:
            if runs and runs[-1][0] == it:
                runs[-1] = (it, runs[-1][1] + ch)
            else:
                runs.append((it, ch))
        out.append(tuple(runs))
    return out


def _render_runs(font, runs, color):
    """One text line made of (italic, text) runs, side by side. A slanted run is wider than the same text upright
    (the slant overhangs on the right); the next run takes that back so the space after a title is a normal one."""
    pieces = []                                       # (picture, shift of the next run)
    try:
        for italic, text in runs:
            font.set_italic(False)
            upright = font.size(text)[0]
            font.set_italic(bool(italic))
            img = font.render(text, True, color)
            pieces.append((img, -(img.get_width() - upright) if italic else 0))
    finally:
        font.set_italic(False)
    width = sum(p.get_width() + d for p, d in pieces)
    img = pygame.Surface((max(1, width), max(p.get_height() for p, _d in pieces)), pygame.SRCALPHA)
    x = 0
    for p, d in pieces:
        img.blit(p, (x, 0))
        x += p.get_width() + d
    return img


MENU_ALPHA = 195                # the panels of the adventure menus let a little of the background through (0..255)
_FILLS = {}


def _fill(surface, color, rect, radius=0, alpha=None):
    """Fill a rounded rectangle slightly see-through (the menu backgrounds)."""
    rect = pygame.Rect(rect)
    a = MENU_ALPHA if alpha is None else int(alpha)
    key = (rect.w, rect.h, tuple(color[:3]), radius, a)
    layer = _FILLS.get(key)
    if layer is None:
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(layer, (*tuple(color[:3]), a), layer.get_rect(), border_radius=radius)
        if len(_FILLS) > 200:
            _FILLS.clear()
        _FILLS[key] = layer
    surface.blit(layer, rect.topleft)


_TEXTS = TextCache()        # rendered lines: a line is drawn again every frame, rendered once


def _render(font, text, color):
    return _TEXTS.get(font, text, tuple(color[:3]))


def _night_sky():
    """The slide of a scene whose picture is still to come: a dark blue sky with stars (its own random generator:
    the game's one is not touched)."""
    img = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
    for y in range(BASE_HEIGHT):
        f = y / (BASE_HEIGHT - 1)
        img.fill((int(10 * (1 - f) + 3 * f), int(14 * (1 - f) + 4 * f), int(34 * (1 - f) + 10 * f)), (0, y, BASE_WIDTH, 1))
    rnd = random.Random(1969)
    for _ in range(260):
        b = rnd.randrange(80, 220)
        img.set_at((rnd.randrange(BASE_WIDTH), rnd.randrange(BASE_HEIGHT)), (b, b, min(255, b + 25)))
    return img


def _text(surface, font, text, color, cy, left=None, right=None, centerx=None):
    """Draw one line, vertically centred on `cy`, anchored left, right or centre."""
    img = _render(font, text, color)
    if left is not None:
        x = left
    elif right is not None:
        x = right - img.get_width()
    else:
        x = centerx - img.get_width() // 2
    surface.blit(img, (x, _cap_top(font, cy)))
    return img


def mission_blurb(mission):
    """The one line the map shows under a mission; a mission with a `target` (the Asteroids prelude) gives it as {n}."""
    text = t(mission["blurb"])
    return text.format(n=int(mission["target"])) if mission.get("target") else text


def _is_replay(entry):
    """Is this journal line one that replays a scene (the intro, a scene seen, a film seen)?"""
    return isinstance(entry, dict) and bool(entry.get("intro") or entry.get("scene") or entry.get("film"))


def _text_fit(surface, font, text, color, cy, left, max_w, scale=1.0):
    """A line anchored left, shrunk (never grown) to `scale` and to fit in `max_w` pixels."""
    img = _render(font, text, color)
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
# When the intro is read aloud (see story_state.intro_voice) the text follows the voice: the line being said is kept near
# VOICE_READ_Y, the text first rises into place while the voice has not started.
VOICE_DELAY = 1.6           # seconds after the slide appears before the voice starts
VOICE_LEAD = 3.2            # seconds the text takes to rise into place
VOICE_READ_Y = 380          # where on the screen the line being said is kept at the start...
VOICE_READ_END_Y = 500      # ...and at the end of the voice (it comes down slowly, so the last lines end in the lower half)
VOICE_CATCH = 0.25          # seconds in which the text catches up with the voice after the keys moved it
VOICE_MAX_SPEED = 220.0     # px/s, the fastest the text goes to catch up
VOICE_VOLUME = 0.92


class StoryHub:
    """Three-pane hub. Left = log, center = hangar, right = map."""

    def __init__(self, sounds=None):
        self.slot_no = None            # save slot (1..4) being played; None before one is opened
        self.sound_events = []         # sounds the hub asks for (the game plays them, see take_sounds)
        self.state = ss.default_state()
        self.screen = "slots"          # slots | delete | leave | name | mode | intro | hub
        self.sel = 0                   # slot cursor on the slot list (0..2)
        self.col = 0                   # 0 = the slot, 1 = its DELETE button
        self.del_yes = False            # the lit button of the YES / NO questions (delete a slot, leave the Adventure)
        self.mode_index = ss.MODES.index(ss.DEFAULT_MODE)    # 0 novice, 1 normal, 2 veteran
        self.entry = None              # NameEntry while typing a pilot name
        self.new_name = ""
        self.msg = ""
        self.summaries = []
        self.pane = "hangar"
        self.zone = "slots"   # slots | shop
        self.shop_index = 0
        self.paint_mode = False        # the paint shop is open (choosing a colour)
        self.choice_index = 0          # Act 3: the hull that keeps the anchor (0 Shield, 1 Phenix, ss.HULLS)
        self.choice_ask = False        # its question "keep it? the other one will be lost" is on screen
        self.paint_choice = 0
        self.map_index = 0
        self.toast = ""
        self.toast_kind = "info"       # its colour type (announce.TOAST_COLOR)
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
        self.log_scroll = 0            # first journal line shown (only the replay lines are selectable)
        self.log_cursor = 0            # which replay line (the intro, then the scenes seen) is selected
        self.scene_id = None           # mission whose scene is being shown (None: the story intro)
        self.scene_launch = False      # the scene came before a launch: A on the last slide flies the mission
        self.scene_door = None         # the scene is told for the first time and ends in this screen of the main menu
        self.scene_closing = False     # A was pressed on its last slide: the game fades out and opens that screen
        self._door_request = None      # B / Esc on such a scene: the same request, taken by take_door_request
        self._launch_request = None    # B / Esc on the scene of a launch: the mission flies at once (take_launch_request)
        self.addon_ready = mame_addon.addon_ready      # (replaced in the tests) is the Add-On available?
        self.cheat_buf = ""            # last letters typed on the mission map
        self.cheat_unlock = False      # UNLK: every mission can be played, nothing is saved any more
        self.cheat_act2 = False        # ACT2: the save jumped to Act 2, nothing is saved any more
        self.best_index = 0            # cursor in the Bestiary list
        self.extras_index = 0          # which paragraph of the Extras tab is chosen
        self.anim_t = 0.0              # seconds, drives the Bestiary animation
        self._intro_bg = {}
        self._clip = None              # videoclip.ClipPlayer of the slide on screen, if it is a video
        self.film_id = None            # the film on screen (screen "film", story_state.FILMS)
        self.film_return = "map"       # pane to go back to when it is over
        self._film = None              # its videoclip.ClipPlayer
        self._film_sound = None        # path of its sound, until the sound has started
        self.film_t = 0.0              # seconds since it started
        self._clip_name = None
        self._clip_shade = None
        self._clip_paths = {}          # picture name -> its clip file (None: a still)
        self._intro_blocks = {}
        self._intro_mask = None
        self._intro_edges = {}
        self._intro_black = None
        self._intro_limit = None
        self.sounds = sounds           # the SoundManager: the intro is read aloud (None: no voice)
        self._intro_spans = {}         # text key -> (y0, y1) of each line of the text, in the tall picture
        self._voice = None             # the voice of the slide on screen (story_state.intro_voice), once it is playing
        self._voice_t = 0.0            # seconds the voice has been speaking
        self._voice_curve = None       # [(second, y in the text)] of the voice of the slide on screen (made when drawn)
        self._voice_given_up = False   # the voice could not start on this slide: the text goes at its own speed
        self._intro_key = None         # key of the tall text picture last asked for
        self._voice_found = {}         # (text key, language) -> its voice, or None

    # --- intro ---
    def start_intro(self, back_to="hangar"):
        """Show the story slides (new adventure, a save that never saw them, or a replay)."""
        self.intro_slides = ss.intro_slides(self.state.get("mode"))
        self.intro_index = 0
        self._reset_slide()
        self.intro_return = back_to
        self.scene_id = None
        self.scene_launch = False
        self.screen = "intro"

    def start_scene(self, mission_id, back_to="map", launch=False, door=None):
        """Show the scene of a mission (the first time it is launched, or from the journal). `door`: the screen of the
        main menu to open when it is over (the scene of the Phobos bar, told for the first time)."""
        scene = ss.scene_of(mission_id)
        if not scene:
            return False
        self.intro_slides = ss.scene_slides(mission_id, self.state.get("mode"))
        self.intro_index = 0
        self._reset_slide()
        self.intro_return = back_to
        self.scene_id = mission_id
        self.scene_launch = bool(launch)
        self.scene_door = door
        self.scene_closing = False
        self.screen = "intro"
        return True

    # --- the Extras tab: the screens of the main menu, and the bar of Phobos once the Add-On is there ---
    def doors(self):
        """The paragraphs of the Extras tab: Achievements, Jukebox, Credits, Options, and the Phobos bar (the Add-On menu)
        when the Add-On is available."""
        return DOORS + ((BAR_DOOR,) if self._addon_available() else ())

    def _addon_available(self):
        try:
            return bool(self.addon_ready())
        except Exception:
            log_exc("story._addon_available")
            return False

    def bar_due(self):
        """True when the scene of the Phobos bar has to be told now (Add-On available, not seen in this save)."""
        return ss.bar_due(self.state, self._addon_available())

    def take_door_request(self):
        """The game asks every frame: has the player skipped the scene that ends in a screen of the main menu? (Then
        the same fade to black and the same screen as at the end of the scene.) Returns the request once, or None."""
        req, self._door_request = self._door_request, None
        return req

    def take_launch_request(self):
        """The game asks after every B / Esc: was it a scene read before a launch, skipped? Then the mission flies at
        once, like at the end of the scene (nobody has to press again). Returns the launch spec once, or None."""
        req, self._launch_request = self._launch_request, None
        return req

    def scene_music(self):
        """(theme, level) of the music kept under the scene being read, or None. The level is a share of the normal
        volume: low while the text goes by, back to normal when the scene is closed."""
        if self.screen != "intro" or not self.scene_id:
            return None
        key = (ss.scene_of(self.scene_id) or {}).get("music")
        if not key:
            return None
        return key, (1.0 if self.scene_closing else ss.BAR_MUSIC_LEVEL)

    def _reset_slide(self):
        self._stop_clip()                 # a video starts over with its slide
        self._stop_voice()                # and so does the voice
        self.intro_t = 0.0
        self.intro_pos = 0.0
        self.intro_speed = 0.0

    def _maybe_intro(self):
        if not ss.intro_seen(self.state):
            self.start_intro(back_to="map")          # the story first, then the map: the first sortie waits there

    def _intro_next(self):
        """A on a slide: the next one; after the last, the story goes on (a scene before a launch flies the
        mission: the launch spec is returned)."""
        if self.intro_t < INTRO_LOCK or self.scene_closing:
            return None
        if self.intro_index + 1 < len(self.intro_slides):
            self.intro_index += 1
            self._reset_slide()
            return None
        if self.scene_door:
            # the player has read it: the game fades to black, then calls finish_scene() and opens the screen
            self.scene_closing = True
            return {"door": self.scene_door, "scene": True}
        launch = self.scene_launch
        self._end_intro()
        if launch:
            return self._launch_selected()
        return None

    def _end_intro(self):
        """Last slide done, or skipped: remember it and go back (the hangar, the map or the journal). After the attack
        on Phobos, the choice of the hull comes next (it cannot be skipped)."""
        self._stop_clip()
        self._stop_voice()
        choose = self.scene_id == ss.ACT3_ATTACK and ss.act3_pending(self.state)
        film = ss.film_after(self.scene_id) if self.scene_id else None
        if film and ss.film_seen(self.state, film):
            film = None                            # (watched again from the journal: the scene alone)
        if self.scene_id:
            ss.mark_scene_seen(self.state, self.scene_id)
        else:
            ss.mark_intro_seen(self.state)
        self.save()
        self.scene_id = None
        self.scene_launch = False
        self.scene_door = None
        self.scene_closing = False
        self.screen = "hub"
        self.pane = self.intro_return
        self.zone = "slots"
        self.intro_return = "hangar"
        if choose:
            self.open_choice()
        elif film:
            self.start_film(film, back_to=self.pane)    # the concert right after the scene of the VIP rescue

    # --- films: a video with its sound, full screen (story_state.FILMS) ---
    def start_film(self, film_id, back_to="map"):
        """Show a film. False (and nothing on screen) when its files are missing or there is no ffmpeg; it then
        counts as seen, so the journal still lists it once the files are there."""
        files = ss.film_files(film_id)
        clip = None
        if files is not None:
            try:
                clip = videoclip.ClipPlayer(files[0], (BASE_WIDTH, BASE_HEIGHT), fit="contain", loop=False,
                                            hard_clock=True)
            except Exception:
                log_exc("story.start_film")
                clip = None
        if clip is None or clip.failed:
            if clip is not None:
                clip.close()
            ss.mark_film_seen(self.state, film_id)
            self.save()
            return False
        self._stop_film()
        self.film_id = film_id
        self.film_return = back_to
        self._film = clip
        self._film_sound = files[1]                # it starts with the first picture (see _tick_film)
        self.film_t = 0.0
        self.screen = "film"
        return True

    def film_playing(self):
        """A film is on screen: the game leaves the music to it."""
        return self.screen == "film"

    def _tick_film(self, dt):
        clip = self._film
        if clip is None or clip.failed:
            self._end_film()
            return
        if self._film_sound is not None:
            if not clip.ready:
                return                             # picture and sound start together
            self._start_film_sound(self._film_sound)
            self._film_sound = None
        self.film_t += dt
        clip.pump()
        if clip.ended:
            self._end_film()

    def _start_film_sound(self, path):
        snd = self.sounds
        volume = float(getattr(snd, "music_volume", 0.4) or 0.0) if snd is not None else 0.4
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
            pygame.mixer.music.play(0)
            if snd is not None:
                snd._current_music = "film"        # the menu theme must not come back over it
        except Exception:
            log_exc("story._start_film_sound")

    def _stop_film(self):
        if self._film is not None:
            self._film.close()
        self._film = None
        self._film_sound = None

    def _end_film(self):
        """The film is over, or skipped: it counts as seen, the journal keeps it, the music of the menus comes back. The
        first time, the film that follows it comes next (the songs of the concert); B / Esc skips one song."""
        film = self.film_id
        self._stop_film()
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            log_exc("story._end_film")
        if self.sounds is not None and getattr(self.sounds, "_current_music", None) == "film":
            self.sounds._current_music = None      # the game starts the menu theme again
        nxt = ss.film_after(film) if film else None
        if film:
            first = not ss.film_seen(self.state, film)
            ss.mark_film_seen(self.state, film)
            self.save()
            if not first or (nxt and ss.film_seen(self.state, nxt)):
                nxt = None                         # (watched again from the journal: that film alone)
        self.film_id = None
        self.screen = "hub"
        self.pane = self.film_return
        self.zone = "slots"
        if nxt:
            self.start_film(nxt, back_to=self.film_return)     # the next song of the concert

    # --- Act 3: the choice of the hull that keeps the quantum anchor ---
    def _maybe_act3(self):
        """Act 2 is won and the hull is not chosen yet: the attack on Phobos is told (again), then the choice."""
        if self.state is not None and ss.act3_pending(self.state) and self.screen != "intro":
            self.start_scene(ss.ACT3_ATTACK, back_to="map")

    def open_choice(self):
        slots = self.state.get("slots") or []
        cur = slots[int(ss._num(self.state.get("selected_slot"), 0))] if slots else {}
        self.choice_index = ss.HULLS.index(cur.get("id")) if cur.get("id") in ss.HULLS else 0
        self.choice_ask = False
        self.del_yes = False
        self.screen = "choice"

    def _choice_confirm(self):
        if not self.choice_ask:
            self.choice_ask = True                       # "Keep the Shield? The Phenix will be lost." NO is lit
            self.del_yes = False
            return
        self.choice_ask = False
        if not self.del_yes:
            return
        hull = ss.HULLS[self.choice_index % len(ss.HULLS)]
        if ss.choose_act3_ship(self.state, hull):
            self.save()
            self.map_index = 0
            self.toast = t("story_act3_start")
            self.toast_kind = "info"
            self.start_scene(ss.loss_scene(hull), back_to="map")      # the other one is lost: told now

    def finish_scene(self, door=None):
        """The fade to black is done: the scene is over and the Adventure is back on its Extras paragraph."""
        self._end_intro()
        self.pane = "extras"
        if door in self.doors():
            self.extras_index = self.doors().index(door)

    def update(self, dt, scroll=0):
        """Time passes. `scroll` is the speed control of the intro: +1 faster (Down), -1 back (Up)."""
        self.anim_t += max(0.0, min(0.25, float(dt)))
        if self.screen == "film":
            self._tick_film(max(0.0, min(0.25, float(dt))))
            return
        if self._film is not None:
            self._stop_film()
        if self.screen != "intro":
            if self._clip is not None:
                self._stop_clip()
            self._stop_voice()
            return
        dt = max(0.0, min(0.25, float(dt)))
        self.intro_t += dt
        self._tick_voice(dt)
        if scroll > 0:
            target = INTRO_FAST
        elif scroll < 0:
            target = -INTRO_BACK
        elif self._voice is not None or self._voice_expected():
            target = self._voice_scroll()    # the text follows the voice (before it starts, the text rises into place)
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
        if self._voice is not None:
            limit = None                  # the voice leads: the text goes up as far as the last line it says
        if limit is not None and self.intro_pos > limit:
            self.intro_pos = limit
            self.intro_speed = min(0.0, self.intro_speed)

    # --- the voice of the intro (story_state.intro_voice): the text is kept in step with it ---
    def _slide_voice(self):
        """The voice of the slide on screen, or None (no recording, another language, or no sound)."""
        if self.sounds is None or not getattr(self.sounds, "enabled", False) or getattr(self.sounds, "sfx_muted", False):
            return None
        try:
            key = (self.intro_slides[self.intro_index][1], get_lang())
        except (IndexError, TypeError):
            return None
        if key not in self._voice_found:
            self._voice_found[key] = ss.intro_voice(*key)
        return self._voice_found[key]

    def _voice_expected(self):
        """True from the moment the slide appears until its voice has started or has been given up."""
        return self._voice is None and not self._voice_given_up and self._slide_voice() is not None

    def _tick_voice(self, dt):
        if self._voice is not None:
            self._voice_t += dt
            if not self.sounds.narration_busy():
                self._voice_t = max(self._voice_t, self._voice["length"])
            return
        if self.intro_t < VOICE_DELAY or self._voice_given_up:
            return
        voice = self._slide_voice()
        if voice is None or not self.sounds.play_narration(voice["path"], VOICE_VOLUME):
            self._voice_given_up = True                    # no voice: the text goes at its own speed
            return
        self._voice = voice
        self._voice_t = self.intro_t - VOICE_DELAY          # (the frame that started it may be late)
        self._voice_curve = None

    def _stop_voice(self):
        if self.sounds is not None and self._voice is not None:
            try:
                self.sounds.stop_narration()
            except Exception:
                log_exc("story._stop_voice")
        self._voice = None
        self._voice_t = 0.0
        self._voice_curve = None
        self._voice_given_up = False

    def _voice_target(self, t, v):
        """Where the text should be (intro_pos, in px) `t` seconds after the slide appeared, the voice having spoken for `v`
        seconds (negative: it has not started)."""
        curve = self._voice_curve
        if curve:
            if v <= curve[0][0]:
                y = curve[0][1]
            elif v >= curve[-1][0]:
                y = curve[-1][1]
            else:
                y = curve[-1][1]
                for (t0, y0), (t1, y1) in zip(curve, curve[1:]):
                    if t0 <= v <= t1:
                        y = y0 + (y1 - y0) * ((v - t0) / (t1 - t0) if t1 > t0 else 1.0)
                        break
        else:
            y = 0.0
        x = max(0.0, min(1.0, t / VOICE_LEAD))
        length = self._voice["length"] if self._voice is not None else 1.0
        read_y = VOICE_READ_Y + (VOICE_READ_END_Y - VOICE_READ_Y) * max(0.0, min(1.0, v / max(1.0, length)))
        lead = (BASE_HEIGHT - read_y) * (1.0 - x * x * (3.0 - 2.0 * x))           # the text rises into place
        return max(0.0, BASE_HEIGHT - read_y + y - lead)

    def _voice_scroll(self):
        """The rising speed (px/s) that brings the text to where the voice is, a moment ahead."""
        v = (self._voice_t if self._voice is not None else self.intro_t - VOICE_DELAY) + VOICE_CATCH
        want = self._voice_target(self.intro_t + VOICE_CATCH, v)
        speed = (want - self.intro_pos) / VOICE_CATCH
        return max(-VOICE_MAX_SPEED, min(VOICE_MAX_SPEED, speed))

    def _make_voice_curve(self, key, spans, height):
        """[(second, y)]: the line being said, as a place in the tall text, from the marks of the recording."""
        voice = self._voice
        curve = []
        for line, start, end in voice["marks"]:
            span = spans.get(line)
            if span is None:
                continue
            curve.append((start, float(span[0])))
            curve.append((end, float(span[1])))
        if curve and curve[0][0] > 0.0:
            curve.insert(0, (0.0, curve[0][1]))
        return curve

    # --- save slots ---
    def open_slots(self):
        """Entry point of the Adventure menu: the list of the 4 save slots."""
        self.screen = "slots"
        self.col = 0
        self.msg = ""
        self.summaries = ss.all_summaries()
        self.sel = max(0, min(ss.SLOT_COUNT - 1, self.sel))

    def open_slot(self, slot_no):
        """Load slot 1..4 and go to its hangar (a missing file starts a fresh one)."""
        state = ss.load_state(ss.story_path(slot_no))
        self.state = state if state is not None else ss.default_state()
        self.slot_no = int(slot_no)
        self.cheat_unlock = False                 # loading a save always starts clean
        self.cheat_act2 = False
        self.cheat_buf = ""
        self.log_scroll = 0
        self.log_cursor = 0
        self.scene_id = None
        self.scene_launch = False
        slots = self.state.get("slots") or []
        cur = int(ss._num(self.state.get("selected_slot"), 0))
        if not (0 <= cur < len(slots) and slots[cur].get("owned")):
            self.state["selected_slot"] = 0       # never rest on a hull the pilot does not own yet
        self.screen = "hub"
        self.pane = "hangar"
        self.zone = "slots"
        self.paint_mode = False
        self.shop_index = 0
        self.focus_next()                         # the map opens on the mission to fly next
        self.toast = ""
        story_feats.check(self.state)             # a save made before the Adventure page gets what it has earned
        self._maybe_act3()                        # Act 2 won and no hull chosen yet: the attack on Phobos

    def save(self):
        if self.slot_no is None or self.cheating:
            return                                # a cheated adventure is never written (and earns nothing)
        try:
            ss.save_state(ss.story_path(self.slot_no), self.state)
        except Exception:
            log_exc("story.save")
        story_feats.check(self.state)             # the achievements of the Adventure page

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
            "phoenix_argent": "sprites/player_ship.png",
            "phoenix_blue": "sprites/player_ship_blue.png",
            "phoenix_gold": "sprites/player_ship_gold.png",
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

    def focus_next(self):
        """Put the map cursor on the mission the map suggests (the first one that can be flown and is not won yet),
        or on the first row when there is none."""
        rows = self.missions()
        nxt = ss.next_mission(self.state, rows)
        self.map_index = next((i for i, m in enumerate(rows) if nxt is not None and m["id"] == nxt["id"]), 0)

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
        if self.screen == "hub" and self.pane in ("map", "hangar"):
            ch = getattr(event, "unicode", "") or ""
            if getattr(self, "_cheat_pane", None) != self.pane:
                self._cheat_pane = self.pane
                self.cheat_buf = ""               # a code is typed on one screen, not across two
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
        self.cheat_buf = (self.cheat_buf + str(ch).upper())[-max(len(CHEAT_UNLOCK), len(CHEAT_ACT2), len(CHEAT_NIX)):]
        if self.cheat_buf == CHEAT_ACT3 and self.pane == "map":
            self.cheat_buf = ""
            if int(ss._num(self.state.get("act"), 1)) < 3:
                ss.jump_to_act3(self.state)
            self.cheat_act2 = True                # nothing is saved any more
            self.map_index = 0
            self.toast = t("story_cheat_act3")
            self.toast_kind = "special"
            self._maybe_act3()                    # the attack on Phobos is told now
            return True
        if self.cheat_buf == CHEAT_NIX and self.pane == "hangar":
            self.cheat_buf = ""
            ss.grant_phenix(self.state)
            self.cheat_act2 = True                # nothing is saved any more
            self.map_index = 0
            self.toast = t("story_cheat_nix")
            self.toast_kind = "special"
            return True
        if self.cheat_buf == CHEAT_ACT2 and self.pane == "map":
            self.cheat_buf = ""
            if int(ss._num(self.state.get("act"), 1)) < 2:
                ss.jump_to_act2(self.state)
            self.cheat_act2 = True
            self.map_index = 0                    # the Act 2 map is a different list
            self.toast = t("story_cheat_act2")
            self.toast_kind = "special"
            return True
        if self.cheat_buf == CHEAT_UNLOCK and not self.cheat_unlock and self.pane == "map":
            here = self._mission()
            self.cheat_unlock = True
            self.cheat_buf = ""
            if here is not None:                  # the list now holds every mission: stay on the same one
                ids = [m["id"] for m in self.missions()]
                self.map_index = ids.index(here["id"]) if here["id"] in ids else 0
            self.toast = t("story_cheat_on")
            self.toast_kind = "special"
            return True
        return False

    def _submit_name(self):
        if not self.entry.name:
            self.msg = t("story_name_empty")
            return
        self.new_name = self.entry.name
        self.mode_index = ss.MODES.index(ss.DEFAULT_MODE)       # Normal is lit first
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
        elif self.screen in ("delete", "leave"):
            self.del_yes = direction > 0
        elif self.screen == "choice":
            if self.choice_ask:
                self.del_yes = direction > 0
            else:
                self.choice_index = max(0, min(len(ss.HULLS) - 1, self.choice_index + (1 if direction > 0 else -1)))
        elif self.screen == "name":
            self.entry.move(1 if direction > 0 else -1, 0)
            self.msg = ""
        elif self.screen == "mode":
            self.mode_index = max(0, min(len(ss.MODES) - 1, self.mode_index + (1 if direction > 0 else -1)))

    def nav_v(self, direction):
        if self.screen == "hub":
            return self._hub_nav_v(direction)
        if self.screen == "slots":
            self.msg = ""
            self.sel = max(0, min(ss.SLOT_COUNT - 1, self.sel + direction))
            if self._summary().get("status") == "missing":
                self.col = 0
        elif self.screen in ("delete", "leave"):
            self.del_yes = direction > 0
        elif self.screen == "name":
            self.entry.move(0, 1 if direction > 0 else -1)
        elif self.screen == "mode":
            self.mode_index = max(0, min(len(ss.MODES) - 1, self.mode_index + (1 if direction > 0 else -1)))

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
            return self._intro_next()
        elif self.screen == "choice":
            self._choice_confirm()
        elif self.screen == "delete":
            if self.del_yes:
                ss.delete_slot(self.sel + 1)
                self.open_slots()
            else:
                self.screen = "slots"
        elif self.screen == "leave":
            self.screen = "slots"                        # whatever the answer, the slot list is what is left behind
            if self.del_yes:
                self.del_yes = False
                return {"leave": True}                   # the game goes back to its main menu
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
            self.start_intro(back_to="map")
        return None

    def back(self):
        """B / Esc. Always handled here: on the slot list it asks whether to leave the Adventure (the answer comes
        back from confirm() as {"leave": True}); B / Esc on that question cancels it."""
        if self.screen == "slots":
            self.screen = "leave"
            self.del_yes = False                         # NO is lit: a second B / Esc does not leave by accident
            self.msg = ""
        elif self.screen == "hub":
            if self.paint_mode:
                self.paint_mode = False                  # B closes the paint shop, nothing is spent
                return True
            self.open_slots()
        elif self.screen in ("delete", "leave", "name"):
            self.screen = "slots"
            self.msg = ""
        elif self.screen == "mode":
            self.screen = "name"
        elif self.screen == "choice":
            self.choice_ask = False                      # the choice itself cannot be skipped
        elif self.screen == "film":
            self._end_film()                             # B / Esc: the film is skipped (A does nothing: no accident)
        elif self.screen == "intro":
            if self.scene_door:
                if not self.scene_closing:       # skipped: the same way out as at the end (the scene counts as seen)
                    self.scene_closing = True
                    self._door_request = {"door": self.scene_door, "scene": True}
            else:
                launch = self.scene_launch
                self._end_intro()
                if launch:
                    self._launch_request = self._launch_selected()      # skipping the scene is not cancelling the sortie
        else:
            return False
        return True

    # --- hub input ---
    def _hub_nav_h(self, direction):
        """Left / right. Slots when hangar+slots, else change pane."""
        if self.paint_mode:
            n = len(ss.paint_tints(self.state))
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

    def replay_entries(self):
        """The journal lines that replay a story scene: the intro first, then each scene seen."""
        return [e for e in self.log_entries() if _is_replay(e)]

    def story_entries(self):
        """The journal lines that tell what happened (the replay lines are shown apart, above them)."""
        return [e for e in self.log_entries() if not _is_replay(e)]

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
            # only the replay lines at the top (the intro, then the scenes seen) can be selected: Down goes
            # through them, then scrolls the rest; Up scrolls back first, then goes up through them
            top = max(0, len(self.story_entries()) - LOG_STORY_ROWS)
            last = len(self.replay_entries()) - 1
            if direction > 0 and self.log_cursor < last:
                self.log_cursor += 1
            elif direction < 0 and self.log_scroll == 0 and self.log_cursor > 0:
                self.log_cursor -= 1
            else:
                self.log_scroll = max(0, min(top, self.log_scroll + direction))
            return
        if self.pane == "extras":
            self.extras_index = max(0, min(len(self.doors()) - 1, self.extras_index + direction))
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
            mission = self._mission()
            if (self.mission_playable(mission) and ss.scene_of(mission["id"])
                    and not ss.scene_seen(self.state, mission["id"])):
                self.start_scene(mission["id"], back_to="map", launch=True)       # the story comes first
                return None
            return self._launch_selected()
        if self.pane == "extras":
            doors = self.doors()
            door = doors[max(0, min(len(doors) - 1, self.extras_index))]
            if door == BAR_DOOR and self.bar_due():
                # the first time the Phobos bar is opened (it is only there with the Add-On) its scene is told first
                self.start_scene(ss.BAR_SCENE, back_to="extras", door=BAR_DOOR)
                return None
            return {"door": door}   # the game opens the screen and brings us back here
        if self.pane == "log":
            replay = self.replay_entries()
            entry = replay[max(0, min(len(replay) - 1, self.log_cursor))]
            if entry.get("scene"):
                self.start_scene(entry["scene"], back_to="log")       # watch a scene again
            elif entry.get("film"):
                self.start_film(entry["film"], back_to="log")         # a film again (the concert)
            else:
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

    def take_sounds(self):
        """The sounds asked for since the last call (names known to the Sounds object), then forgotten."""
        out, self.sound_events = self.sound_events, []
        return out

    def _open_paint(self):
        """The paint shop row: opens the colour choice when a change is waiting."""
        if not ss.paint_state(self.state)["token"]:
            self.toast = t("story_paint_locked")
            self.toast_kind = "danger"
            return
        if not ss.paint_affordable(self.state):
            self.toast = t("story_paint_poor").format(pts=ss.PAINT_COST)
            self.toast_kind = "danger"
            return
        tints = ss.paint_tints(self.state)
        self.paint_choice = tints.index(ss.worn_tint(self.state))
        self.paint_mode = True
        self.toast = ""

    def _paint_confirm(self):
        """A on the colour choice: wear it (spends the change) or, if it is the current colour, just close."""
        tints = ss.paint_tints(self.state)
        tint = tints[self.paint_choice % len(tints)]
        if ss.paint_change(self.state, tint):
            self.save()
            self.toast = t("story_paint_done")
            self.toast_kind = "reward"
            self.sound_events.append("paint_fanfare")            # trumpets for the new colour
        self.paint_mode = False

    def _launch_selected(self):
        mission = self._mission()
        if not self.mission_playable(mission):
            return None
        ship = mission.get("ship")
        if mission.get("needs_reactor"):
            ship = ss.reactor_hull(self.state)        # the VIP rescue: a hull with its two-dimensional reactor
        spec = {
            "launch": True,
            "id": mission["id"],
            "title": mission["title"],
            "content": int(mission["content"]),
            "speed": float(mission.get("speed") or 1.0),
            "dome": bool(self.loadout(ship).get("dome")),
            "items": story_items.installed(self.state),       # bought in the hangar: they work in this mission only
        }
        if ship:
            spec["ship"] = ship                       # a mission that imposes its hull
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
        if mission.get("hud_title"):
            spec["hud_title"] = mission["hud_title"]          # a shorter name for the top of the screen
        if mission.get("galaga"):
            spec["galaga"] = True                 # waves in chains like Namco's Galaga (src/galaga.py)
            spec["stage"] = int(mission.get("stage") or ss.GALAGA_STAGE)
            if mission.get("fire_mult"):
                spec["fire_mult"] = float(mission["fire_mult"])    # the birds shoot more (the Phenix version)
        if mission.get("reactor"):
            spec["reactor"] = mission["reactor"]      # the hull whose reactor falls in this mission, once
        if mission.get("asteroids"):
            spec["asteroids"] = True                  # the Asteroids level (src/asteroids.py)
            spec["target"] = int(mission.get("target") or 40)
        if mission.get("escort"):
            spec["escort"] = True                 # the VIP rescue: the cruise ship to bring across (src/escort.py)
            spec["stage"] = int(mission.get("stage") or 6)
        if mission.get("swarm"):
            spec["swarm"] = True                  # the four enemies together, replaced as they fall
            spec["stage"] = int(mission.get("stage") or 11)
            if mission.get("swarm_screens") is not None:
                spec["swarm_screens"] = float(mission["swarm_screens"])    # a smaller swarm
        return spec

    def apply_result(self, mission_id, score, cleared, kills=None, loot=None, used=None, flawless=False):
        """End of a mission: credits, penalty or fall (see story_state.record_result). `loot` is the item caught
        during the mission, `used` the items that were installed for it; `flawless`: no life was lost."""
        res = ss.record_result(self.state, mission_id, score, cleared, kills, loot=loot, used=used)
        if res["cleared"] and flawless and not self.cheating:
            story_feats.note_flawless()
            if mission_id == "final_5":
                story_feats.note_untouchable()          # Triton, not a scratch
        if res["cleared"]:
            self.toast = t("story_clear").format(pts=res["score"])
            self.toast_kind = "success"
            fought = ss.mission_by_id(mission_id) or {}
            if not fought.get("hunt"):
                self.focus_next()                    # a story mission is won once: the cursor goes on to the next one
            if res.get("act"):
                self.focus_next()                    # a new act has a new map
                self.toast = t("story_act_start").format(n=res["act"])
                self.toast_kind = "info"
            if res.get("paint"):
                self.toast = t("story_paint_done_series")
                self.toast_kind = "reward"
            if res.get("hull") == "phoenix":
                self.toast = t("story_phenix_gift")
                self.toast_kind = "reward"
            if res.get("opened"):
                gift = self.toast if res.get("hull") == "phoenix" else ""     # the Phenix comes with its own BONUS mission
                self.toast = (gift + "   " if gift else "") + t("story_bonus_open")
                self.toast_kind = "reward"
            if res.get("reward"):
                self.toast = t("story_reward").format(pts=res["reward"])     # the parts salvaged from the wreck
                self.toast_kind = "gain"
        elif res.get("no_item"):
            self.toast = t("story_item_missed").format(name=t("item_%s_name" % res["no_item"]))
            self.toast_kind = "info"                 # the BONUS item was not caught: no gain, no loss
        elif res["fallen"]:
            self.toast = t("story_fell_msg").format(name=self.state.get("name") or "")
            self.toast_kind = "danger"
        elif res["lost"]:
            self.toast = t("story_fail_pen").format(pts=res["lost"])
            self.toast_kind = "danger"
        else:
            self.toast = t("story_fail_none")
            self.toast_kind = "danger"
        if res.get("reactor_lost") and not res["fallen"]:
            self.toast += "   " + t("story_reactor_lost")
        if res.get("loot") and not res["fallen"]:
            self.toast += "   " + t("story_item_found").format(name=t("item_%s_name" % res["loot"]))
            if self.toast_kind != "danger":
                self.toast_kind = "gain"
        self.pane = "map"
        self.save()
        if res["fallen"]:
            self._show_fall()
        elif res.get("act3"):
            self._maybe_act3()                       # Phobos is attacked: the scene, then the choice of the hull
        elif res.get("epilogue") and res.get("first"):
            self.start_scene(ss.EPILOGUE, back_to="map")       # the end of the Adventure
        elif res.get("win_scene") and res.get("first"):
            self.start_scene(res["win_scene"], back_to="map")  # who was on board (the VIP rescue)

    def _show_fall(self):
        """A fallen Veteran goes back to the slot list, where the save is now a memorial."""
        msg = self.toast
        self.open_slots()
        self.msg = msg

    def resume(self, slot_no, toast="", pane="map", toast_kind="info"):
        """Back from a mission in a new Game object: reload the slot from disk."""
        self.open_slot(slot_no)
        if self.state.get("fallen"):
            self.toast = toast
            self.toast_kind = toast_kind
            self._show_fall()
        else:
            self.pane = pane
            self.toast = toast
            self.toast_kind = toast_kind

    def _buy(self, row):
        hidden = [m for m in ss.MISSIONS if m.get("secret") and not ss.mission_open(self.state, m)]
        if not ss.buy(self.state, row[0]):
            return False
        if any(ss.mission_open(self.state, m) and ss.mission_in_act(m, self.state.get("act")) for m in hidden):
            self.toast = t("story_bonus_open")               # a reactor installed opens the VIP rescue
            self.toast_kind = "reward"
        if ss.item_of(row[0]):
            self.sound_events.append("1up")                  # a loot item is installed for the next mission
        elif not self.cheating:
            story_feats.note_upgrade()                       # a workshop upgrade (achievement "Mécano")
        self.save()
        return True

    def _shop_extra(self, sid, cost, locked):
        if sid == "paint":
            if not ss.paint_state(self.state)["token"]:
                return t("story_locked")
            return t("story_paint_ready").format(pts=ss.PAINT_COST)
        key = ss.upgrade_note(self.state, sid)
        if key == "story_locked":
            src = ss.shop_after(self.state, sid)
            if src is not None:
                return t("story_unlock_after").format(name=t(src["title"]))     # what to win to open this row
        if key:
            return t(key)
        return f"{cost} PTS"

    def covers_screen(self):
        """True when the current screen paints every pixel itself (the slide pictures), so the
        starfield underneath need not be drawn."""
        return self.screen in ("intro", "film")

    # --- draw ---
    def draw(self, surface, font, medium, small, body=None):
        """`body`: the font of what is read at length (the story, the descriptions); `font` when not given."""
        self._ensure_art()
        self._body = body or small
        if self.screen == "intro":
            self._draw_intro(surface, body or font, small)
            return
        if self.screen == "film":
            self._draw_film(surface, medium)
            return
        if self.screen != "hub":
            self._draw_gate(surface, font, medium, small)
            return
        title = {
            "hangar": t("story_hangar"),
            "map": t("story_map"),
            "log": t("story_log"),
            "bestiary": t("story_best"),
            "extras": t("story_extras"),
        }[self.pane]
        ts = medium.render(title, True, menu_ui.TITLE)
        surface.blit(ts, (BASE_WIDTH // 2 - ts.get_width() // 2, 18))

        if self.cheating:
            # small, top left above the pilot name: the title, the credits and the FPS counter own the rest
            _text_fit(surface, small, t("story_cheat_banner"), announce.SPECIAL, 11, 80, 330, scale=0.7)
        if self.state.get("name"):
            mode = t("story_mode_" + str(self.state.get("mode", "normal")))
            _text(surface, small, f"{self.state['name']}  -  {mode}", (170, 175, 195), 36, left=80)
        if self.pane == "hangar":
            self._draw_hangar(surface, font, medium, small)
        elif self.pane == "map":
            self._draw_map(surface, font, medium, small)
        elif self.pane == "bestiary":
            self._draw_bestiary(surface, font, medium, small)
        elif self.pane == "extras":
            self._draw_extras(surface, medium, small)
        else:
            self._draw_log(surface, font, small)

        self._draw_tabs(surface)

    FILM_TITLE_SEC = 5.0           # the title of a film shows over its first seconds

    def _draw_film(self, surface, medium):
        surface.fill((0, 0, 0))
        clip = self._film
        img = clip.surface if clip is not None else None
        if img is not None:
            surface.blit(img, ((BASE_WIDTH - img.get_width()) // 2, (BASE_HEIGHT - img.get_height()) // 2))
        film = ss.FILMS.get(self.film_id) or {}
        if film.get("title") and self.film_t < self.FILM_TITLE_SEC:
            fade = min(1.0, self.film_t / 0.6, (self.FILM_TITLE_SEC - self.film_t) / 0.8)
            title = _render(medium, t(film["title"]), (255, 225, 140)).copy()      # (the cached one stays opaque)
            band = pygame.Surface((BASE_WIDTH, title.get_height() + 24), pygame.SRCALPHA)
            band.fill((0, 0, 0, int(150 * fade)))
            title.set_alpha(int(255 * fade))
            surface.blit(band, (0, 24))
            surface.blit(title, (BASE_WIDTH // 2 - title.get_width() // 2, 36))

    TAB_KEYS = {"bestiary": "story_tab_best", "log": "story_tab_log", "hangar": "story_tab_hangar",
                "map": "story_tab_map", "extras": "story_extras"}
    TAB_Y = 652                    # centre of the tab strip, just above the help bar

    def _draw_tabs(self, surface):
        """The five tabs as small plates over the help bar; the open one wears the lit frame of the menus."""
        import hint_bar
        font = hint_bar._font(20)
        imgs = [(p, _render(font, t(self.TAB_KEYS[p]), menu_ui.TEXT_SEL if p == self.pane else menu_ui.TEXT))
                for p in PANES]
        pad, gap, h = 16, 10, 28
        total = sum(img.get_width() + pad * 2 for _p, img in imgs) + gap * (len(imgs) - 1)
        x = BASE_WIDTH // 2 - total // 2
        for p, img in imgs:
            r = pygame.Rect(x, self.TAB_Y - h // 2, img.get_width() + pad * 2, h)
            if p == self.pane:
                menu_ui.highlight(surface, r)
            else:
                menu_ui.panel(surface, r, radius=6, edge_w=1)
            surface.blit(img, (r.centerx - img.get_width() // 2, r.centery - img.get_height() // 2))
            x = r.right + gap

    def help_items(self, pad=False):
        """(pairs, lit) of the help bar for the screen on display (see hint_bar). `lit`: the pair drawn gold."""
        back, choose = ("back", "hint_back"), ("ud", "hint_choose")
        tab = ("lr", "hint_tab")
        if self.screen == "intro":
            last = self.intro_index + 1 >= len(self.intro_slides)
            if last:
                ok = "hint_takeoff" if self.scene_launch else (
                    "hint_play_addon" if self.scene_door else ("hint_close" if self.scene_id else "hint_start"))
                if self.scene_id == ss.ACT3_ATTACK and ss.act3_pending(self.state):
                    ok = "hint_choose"                   # the choice of the hull comes next
            else:
                ok = "hint_next"
            lit = 0 if getattr(self, "_intro_done", False) and (pygame.time.get_ticks() // 500) % 2 == 0 else None
            return [("ok", ok), ("ud", "hint_speed"), ("back", "hint_skip")], lit
        if self.screen == "film":
            # with the title only: after that the bar would hide the words of the song (the bottom of the picture)
            return ([("back", "hint_skip")] if self.film_t < self.FILM_TITLE_SEC else []), None
        if self.screen == "slots":
            if self.col == 1:
                return [choose, ("ok", "hint_delete"), ("l", "hint_back"), back], None
            items = [choose, ("ok", "hint_open")]
            if self._summary().get("status") != "missing":
                items.append(("r", "hint_delete"))
            return items + [back], None
        if self.screen in ("delete", "leave") or (self.screen == "choice" and self.choice_ask):
            return [("lr", "hint_choose"), ("ok", "hint_ok"), ("back", "hint_cancel")], None
        if self.screen == "choice":
            return [("lr", "hint_hull"), ("ok", "hint_ok")], None
        if self.screen == "name":
            items = [("all", "hint_letters"), ("ok", "hint_ok"), ("back", "hint_cancel")]
            return (items if pad else [(None, "hint_type_name")] + items), None
        if self.screen == "mode":
            return [("lr", "hint_choose"), ("ok", "hint_start"), back], None
        if self.paint_mode:
            return [("lr", "hint_colour"), ("ok", "hint_paint"), ("back", "hint_cancel")], None
        if self.pane == "hangar":
            if self.zone == "shop":
                return [choose, ("ok", "hint_buy"), tab, back], None
            owned = sum(1 for sl in (self.state.get("slots") or []) if sl.get("owned"))
            return [("lr", "hint_hull" if owned > 1 else "hint_tab"), ("ud", "hint_workshop"), back], None
        if self.pane == "map":
            return [choose, ("ok", "hint_launch"), tab, back], None
        if self.pane == "log":
            return [choose, ("ok", "hint_replay"), tab, back], None
        if self.pane == "extras":
            return [choose, ("ok", "hint_open"), tab, back], None
        return [choose, tab, back], None

    # --- intro ---
    def _intro_picture(self, name):
        img = self._intro_bg.get(name)
        if img is None:
            img = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
            path = asset_path("story", name + ".jpg")
            if not os.path.isfile(path):
                img = _night_sky()                # a picture still to come: a dark sky behind the text
                self._intro_bg[name] = img
                return img
            try:
                raw = pygame.image.load(path).convert()
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
        _pic, text_key = self.intro_slides[self.intro_index]
        key = (text_key, get_lang(), self.state.get("name"), id(font))
        self._intro_key = key
        hit = self._intro_blocks.get(key)
        if hit is not None:
            return hit
        rows = []                                  # (text, height); text None = a pause
        spans = {}                                 # line number -> (top, bottom) in the tall picture
        pitch = font.get_linesize() + 12
        y_line = 0
        for number, line in enumerate(ss.intro_lines(t, text_key, self.state.get("name"))):
            first = len(rows)
            if not line:
                rows.append((None, pitch // 2))
            else:
                plain, mask = _italic_runs(line)
                if mask is None:
                    rows.extend((piece, pitch) for piece in _wrap(font, line, INTRO_TEXT_W))
                else:        # a title in italics (*Phoenix*): the text goes by runs, a little narrower for the slant
                    rows.extend((runs, pitch) for runs in _wrap_marked(font, plain, mask, INTRO_TEXT_W - 24))
            h_line = sum(h for _txt, h in rows[first:])
            if line:
                spans[number] = (y_line, y_line + h_line - 12)
            y_line += h_line
        self._intro_spans[key] = spans
        height = sum(h for _txt, h in rows)
        block = pygame.Surface((INTRO_TEXT_W, max(1, height)), pygame.SRCALPHA)
        y = 0
        for txt, h in rows:
            if txt:
                if isinstance(txt, tuple):
                    shadow = _render_runs(font, txt, (0, 0, 0))
                    img = _render_runs(font, txt, (230, 232, 244))
                else:
                    shadow = font.render(txt, True, (0, 0, 0))
                    img = font.render(txt, True, (230, 232, 244))
                x = (INTRO_TEXT_W - img.get_width()) // 2
                block.blit(shadow, (x + 2, y + 2))
                block.blit(img, (x, y))
            y += h
        if len(self._intro_blocks) > 16:
            self._intro_blocks.clear()
            self._intro_spans.clear()
            self._intro_spans[key] = spans
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
        """True once the text has risen to its resting place (with a voice: once the voice has said it all)."""
        if self._voice is not None:
            return self._voice_t >= self._voice["length"] - 0.5
        return self._intro_top(text_height) <= self._intro_rest(text_height)

    @staticmethod
    def _intro_rest(text_height):
        return min((BASE_HEIGHT - text_height) // 2, INTRO_END_Y - text_height)

    def _intro_top(self, text_height):
        if self._voice is not None:
            return BASE_HEIGHT - self.intro_pos          # (the text goes on rising while the voice says it)
        return max(self._intro_rest(text_height), BASE_HEIGHT - self.intro_pos)

    # --- video clip as a slide background (see story_state.clip_path and videoclip.py) ---
    def _stop_clip(self):
        if self._clip is not None:
            self._clip.close()
        self._clip = None
        self._clip_name = None

    def _clip_file(self, name):
        if name not in self._clip_paths:
            self._clip_paths[name] = ss.clip_path(name)
        return self._clip_paths[name]

    def _clip_backdrop(self, name):
        """The video frame of the moment, darkened like the still picture, or None while the video starts
        and whenever it cannot play (then the still shows)."""
        path = self._clip_file(name)
        if not path:
            return None
        if self._clip_name != name:
            self._stop_clip()
            if self._clip_shade is None:
                band = INTRO_TEXT_W + 120                          # the same shade and reading band as a still
                self._clip_shade = videoclip.make_shade(
                    (BASE_WIDTH, BASE_HEIGHT), [(0, BASE_WIDTH, 70), ((BASE_WIDTH - band) // 2, band, 120)])
            self._clip = videoclip.ClipPlayer(path, (BASE_WIDTH, BASE_HEIGHT), self._clip_shade)
            self._clip_name = name
        self._clip.pump()
        return self._clip.surface if self._clip.playing else None

    def _intro_backdrop(self, name):
        """The slide picture with the dark reading band already baked in (cached, opaque)."""
        if self._clip_file(name):
            moving = self._clip_backdrop(name)
            if moving is not None:
                return moving
        key = ("band", name)
        img = self._intro_bg.get(key)
        if img is None:
            img = self._intro_picture(name).copy()
            band = pygame.Surface((INTRO_TEXT_W + 120, BASE_HEIGHT), pygame.SRCALPHA)
            band.fill((0, 0, 0, 120))
            img.blit(band, ((BASE_WIDTH - band.get_width()) // 2, 0))
            self._intro_bg[key] = img
        return img

    def _intro_edge(self, which):
        """Scratch picture and fade strip for the top or bottom edge of the text window (cached)."""
        hit = self._intro_edges.get(which)
        if hit is None:
            y0, y1 = (0, 90) if which == "top" else (INTRO_END_Y, BASE_HEIGHT)
            strip = pygame.Surface((INTRO_TEXT_W, y1 - y0), pygame.SRCALPHA)
            hit = (y0, y1, strip)
            self._intro_edges[which] = hit
        return hit

    def _draw_intro_text(self, surface, block, top, x):
        """The scrolling text, faded softly at the top and bottom edges of its window.

        Between the two fade zones the fade is fully opaque, so the text is drawn straight onto the
        picture; only the two thin edge strips go through the mask."""
        mask = self._intro_fade_mask()
        y_top = self._intro_edge("top")[1]
        y_bot = self._intro_edge("bottom")[0]
        keep = surface.get_clip()
        surface.set_clip(pygame.Rect(x, y_top, INTRO_TEXT_W, y_bot - y_top).clip(keep))
        surface.blit(block, (x, top))
        surface.set_clip(keep)
        for which in ("top", "bottom"):
            y0, y1, strip = self._intro_edge(which)
            strip.fill((0, 0, 0, 0))
            strip.blit(block, (0, top - y0))
            strip.blit(mask, (0, 0), area=pygame.Rect(0, y0, INTRO_TEXT_W, y1 - y0),
                       special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(strip, (x, y0))

    def _draw_intro(self, surface, font, small):
        pic, _key = self.intro_slides[self.intro_index]
        surface.blit(self._intro_backdrop(pic), (0, 0))
        cx = BASE_WIDTH // 2

        block, height = self._intro_block(font)
        self._intro_limit = BASE_HEIGHT - self._intro_rest(height)     # the text cannot rise past this
        if self._voice is not None and self._voice_curve is None:
            self._voice_curve = self._make_voice_curve(self._intro_key, self._intro_spans.get(self._intro_key) or {},
                                                       height)
        top = self._intro_top(height)
        self._draw_intro_text(surface, block, top, cx - INTRO_TEXT_W // 2)

        # the help bar (hint_bar, drawn by the game) lights "A" when the text is over
        self._intro_done = self.intro_finished_scrolling(height)
        if len(self.intro_slides) > 1:
            _text(surface, small, f"{self.intro_index + 1} / {len(self.intro_slides)}", (140, 145, 170),
                  28, right=BASE_WIDTH - 40)

        fade = 1.0 - min(1.0, self.intro_t / INTRO_FADE)
        if fade > 0:
            if self._intro_black is None:
                self._intro_black = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
            self._intro_black.set_alpha(int(255 * fade))
            surface.blit(self._intro_black, (0, 0))

    # --- slot list, name, mode, delete ---
    def _draw_gate(self, surface, font, medium, small):
        cx = BASE_WIDTH // 2
        titles = {"slots": "story_gate_title", "delete": "story_delete_title", "leave": "story_leave_title",
                  "name": "story_name_title", "mode": "story_mode_title", "choice": "story_choice_title"}
        ts = medium.render(t(titles[self.screen]), True, menu_ui.TITLE)
        surface.blit(ts, (cx - ts.get_width() // 2, 18))
        getattr(self, "_draw_gate_" + self.screen)(surface, font, medium, small)

    def _draw_gate_slots(self, surface, font, medium, small):
        card_w = min(BASE_WIDTH - 240, 1100)
        x = (BASE_WIDTH - card_w) // 2
        h, gap, y = 120, 16, 90
        for i, info in enumerate(self.summaries[:ss.SLOT_COUNT]):
            r = pygame.Rect(x, y, card_w, h)
            status = info.get("status")
            focus = i == self.sel
            on_card = focus and self.col == 0
            border = menu_ui.SEL_EDGE if on_card else menu_ui.PANEL_EDGE
            _fill(surface, menu_ui.SEL_FILL if on_card else menu_ui.PANEL_FILL, r, 12)
            pygame.draw.rect(surface, border, r, 3 if on_card else 2, border_radius=12)
            _text(surface, medium, str(i + 1), border if (on_card or status == "missing") else (180, 150, 110),
                  r.centery, left=r.x + 28)
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
                _fill(surface, menu_ui.SEL_FILL if bf else (22, 24, 36), b, 8)
                pygame.draw.rect(surface, menu_ui.SEL_EDGE if bf else menu_ui.PANEL_EDGE, b, 2, border_radius=8)
                _text(surface, small, t("story_slot_delete"), (255, 230, 140) if bf else (150, 155, 175),
                      b.centery, centerx=b.centerx)
            y += h + gap
        if self.msg:
            _text(surface, small, self.msg, (255, 220, 120), y + 20, centerx=BASE_WIDTH // 2)

    def _draw_gate_delete(self, surface, font, medium, small):
        cx = BASE_WIDTH // 2
        info = self._summary()
        _text(surface, medium, info.get("name") or t("story_slot_damaged"), (255, 230, 140), 200, centerx=cx)
        _text(surface, small, t("story_delete_warn"), menu_ui.DANGER, 270, centerx=cx)
        self._draw_yes_no(surface, small, cx, danger=True)

    def _draw_gate_leave(self, surface, font, medium, small):
        cx = BASE_WIDTH // 2
        _text(surface, medium, t("story_leave_ask"), (255, 230, 140), 200, centerx=cx)
        _text(surface, small, t("story_leave_warn"), (170, 175, 195), 270, centerx=cx)
        self._draw_yes_no(surface, small, cx, danger=False)

    def _draw_gate_choice(self, surface, font, medium, small):
        """Act 3: which hull keeps the quantum anchor (Veteran: which one the pilot flies). The two hulls side by
        side, as in the hangar; then the question, with NO lit first: the other hull will be lost."""
        cx = BASE_WIDTH // 2
        veteran = self.state.get("mode") == "veteran"
        self._ensure_art()
        if self.choice_ask:
            hull = ss.HULLS[self.choice_index % len(ss.HULLS)]
            other = ss.HULLS[(self.choice_index + 1) % len(ss.HULLS)]
            _text(surface, medium, t("story_choice_ask").format(ship=t("ship_" + hull)), (255, 230, 140), 200,
                  centerx=cx)
            _text(surface, small, t("story_choice_warn").format(ship=t("ship_" + other)), menu_ui.DANGER, 270,
                  centerx=cx)
            self._draw_yes_no(surface, small, cx, danger=True)
            return
        _text(surface, small, t("story_choice_q_v" if veteran else "story_choice_q"), (220, 220, 235), 84,
              centerx=cx)
        w, h, gap = 440, 400, 40
        x0 = cx - (w * 2 + gap) // 2
        body = getattr(self, "_body", None) or small
        for k, hull in enumerate(ss.HULLS):
            r = pygame.Rect(x0 + k * (w + gap), 116, w, h)
            focus = k == self.choice_index
            _fill(surface, menu_ui.SEL_FILL if focus else menu_ui.PANEL_FILL, r, 12)
            pygame.draw.rect(surface, menu_ui.SEL_EDGE if focus else menu_ui.PANEL_EDGE, r, 3 if focus else 2,
                             border_radius=12)
            sl = next((s for s in self.state.get("slots") or [] if s.get("id") == hull), {})
            img = (self._portraits if focus else self._greyed).get(self._hull_key(sl))
            if img is not None:
                bob = int(math.sin(self.anim_t * 3.2) * 4) if focus else 0
                surface.blit(img, (r.centerx - img.get_width() // 2, r.y + 18 + bob))
            _text(surface, medium, t("ship_" + hull), (255, 230, 140) if focus else (160, 160, 180),
                  r.y + 196, centerx=r.centerx)
            for li, line in enumerate(_wrap(body, t("story_choice_%s_d" % hull), r.w - 56)[:5]):
                _text(surface, body, line, (200, 200, 215) if focus else (130, 135, 155), r.y + 246 + li * 30,
                      centerx=r.centerx)
        _text(surface, small, t("story_choice_note"), (170, 175, 195), 116 + h + 34, centerx=cx)

    def _draw_yes_no(self, surface, small, cx, danger):
        """The NO / YES buttons of a question (NO on the left); `del_yes` tells which one is lit. YES is red when
        the answer destroys something (the delete question)."""
        for k, (label, yes) in enumerate(((t("story_no"), False), (t("story_yes"), True))):
            b = pygame.Rect(cx - 230 + k * 260, 340, 200, 60)
            focus = self.del_yes == yes
            _fill(surface, menu_ui.SEL_FILL if focus else (22, 24, 36), b, 10)
            pygame.draw.rect(surface, (menu_ui.DANGER if yes and danger else menu_ui.SEL_EDGE) if focus else menu_ui.PANEL_EDGE,
                             b, 3 if focus else 2, border_radius=10)
            _text(surface, small, label, (255, 230, 140) if focus else (150, 155, 175), b.centery, centerx=b.centerx)

    def _draw_gate_name(self, surface, font, medium, small):
        cx = BASE_WIDTH // 2
        box = pygame.Rect(cx - 280, 90, 560, 70)
        _fill(surface, menu_ui.SEL_FILL, box, 10)
        pygame.draw.rect(surface, menu_ui.SEL_EDGE, box, 2, border_radius=10)
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
                _fill(surface, menu_ui.SEL_FILL if focus else menu_ui.PANEL_FILL, r, 8)
                pygame.draw.rect(surface, menu_ui.SEL_EDGE if focus else tint, r, 3 if focus else 2, border_radius=8)
                _text(surface, small, labels.get(tok, tok), (255, 230, 140) if focus else (200, 200, 215),
                      r.centery, centerx=r.centerx)
        if self.msg:
            _text(surface, small, self.msg, (255, 220, 120), gy + 4 * (ch + cg) + 24, centerx=cx)

    @staticmethod
    def mode_card_rects():
        """The cards of the mode screen (novice, normal, veteran), side by side and centred."""
        w, h, gap = 376, 270, 24
        x0 = BASE_WIDTH // 2 - (w * len(ss.MODES) + gap * (len(ss.MODES) - 1)) // 2
        return [pygame.Rect(x0 + k * (w + gap), 140, w, h) for k in range(len(ss.MODES))]

    def _draw_gate_mode(self, surface, font, medium, small):
        cx = BASE_WIDTH // 2
        _text(surface, small, f"{t('story_pilot')} : {self.new_name}", (170, 175, 195), 100, centerx=cx)
        for k, (key, r) in enumerate(zip(ss.MODES, self.mode_card_rects())):
            focus = k == self.mode_index
            _fill(surface, menu_ui.SEL_FILL if focus else menu_ui.PANEL_FILL, r, 12)
            pygame.draw.rect(surface, menu_ui.SEL_EDGE if focus else menu_ui.PANEL_EDGE, r, 3 if focus else 2,
                             border_radius=12)
            col = MODE_COLORS[key]
            _text(surface, medium, t("story_mode_" + key), col if focus else (150, 155, 175), r.y + 46, centerx=r.centerx)
            body = getattr(self, "_body", None) or small
            for li, line in enumerate(_wrap(body, t("story_mode_%s_d" % key), r.w - 40)):
                _text(surface, body, line, (200, 200, 215) if focus else (130, 135, 155), r.y + 112 + li * 36, centerx=r.centerx)

    def _draw_log(self, surface, font, small):
        """The journal in two zones: the scenes to watch again (the cursor is there) and what happened (it scrolls),
        under a line that says what to do next."""
        box = pygame.Rect(80, 78, BASE_WIDTH - 160, BASE_HEIGHT - 168)
        _fill(surface, menu_ui.PANEL_FILL, box, 10)
        pygame.draw.rect(surface, menu_ui.PANEL_EDGE, box, 2, border_radius=10)
        head_col = (120, 160, 210)
        arrow_col = (255, 190, 110)
        ax = box.right - 22
        nxt = ss.next_mission(self.state, self.missions())
        if nxt is not None:
            _text_fit(surface, small, t("story_log_goal").format(name=t(nxt["title"])), (255, 230, 140), box.y + 30,
                      box.x + 24, box.w - 48)
        # zone 1: the scenes to watch again
        _text_fit(surface, small, t("story_log_head_scenes"), head_col, box.y + 72, box.x + 24, 400, scale=0.8)
        replay = self.replay_entries()
        step = 34
        first = max(0, min(self.log_cursor - 1, len(replay) - LOG_REPLAY_ROWS))
        y = box.y + 104
        for i in range(first, min(len(replay), first + LOG_REPLAY_ROWS)):
            entry = replay[i]
            focus = i == self.log_cursor
            if focus:
                menu_ui.highlight(surface, pygame.Rect(box.x + 12, y - step // 2 + 2, box.w - 24, step - 4))
            text = t("story_log_intro") if entry.get("intro") else log_text(entry, t)
            _text_fit(surface, small, text, (255, 230, 140) if focus else (255, 190, 90), y, box.x + 24, box.w - 80)
            y += step
        zone2 = box.y + 104 + LOG_REPLAY_ROWS * step
        if first > 0:
            pygame.draw.polygon(surface, arrow_col, [(ax - 7, box.y + 100), (ax + 7, box.y + 100), (ax, box.y + 90)])
        if first + LOG_REPLAY_ROWS < len(replay):
            pygame.draw.polygon(surface, arrow_col, [(ax - 7, zone2 - 18), (ax + 7, zone2 - 18), (ax, zone2 - 8)])
        # zone 2: what happened
        pygame.draw.line(surface, menu_ui.PANEL_EDGE, (box.x + 20, zone2 + 2), (box.right - 20, zone2 + 2), 1)
        _text_fit(surface, small, t("story_log_head_log"), head_col, zone2 + 26, box.x + 24, 400, scale=0.8)
        entries = self.story_entries()
        rows, step = LOG_STORY_ROWS, 36
        start = self.log_scroll = max(0, min(self.log_scroll, len(entries) - rows))
        y = zone2 + 62
        if not entries:
            _text(surface, small, t("story_log_empty"), (160, 170, 200), y, left=box.x + 24)
        for i in range(start, min(len(entries), start + rows)):
            entry = entries[i]
            indent = 0
            if isinstance(entry, dict) and ("kills" in entry or "level" in entry):
                text = log_text(entry, t)
                col = (190, 175, 130)
                indent = 56                                   # sits under its mission line
            else:
                text = log_text(entry, t)
                col = (200, 200, 220)
            _text_fit(surface, small, text, col, y, box.x + 24 + indent, box.w - 80 - indent)
            y += step
        if start > 0:
            pygame.draw.polygon(surface, arrow_col, [(ax - 7, zone2 + 46), (ax + 7, zone2 + 46), (ax, zone2 + 36)])
        if start + rows < len(entries):
            low = zone2 + 62 + rows * step - 16
            pygame.draw.polygon(surface, arrow_col, [(ax - 7, low), (ax + 7, low), (ax, low + 10)])

    def bestiary_picture(self, kind, count):
        """The picture of an enemy met `count` times: small, then 2x, then animated (also 2x)."""
        tiers = ss.best_tiers(count, ss.is_boss(kind))
        img = bestiary_art.animated(kind, self.anim_t) if tiers["anim"] else bestiary_art.still(kind)
        if tiers["zoom"]:
            img = pygame.transform.scale(img, (img.get_width() * 2, img.get_height() * 2))
        return img

    # the layout of the Extras tab for 3, 4 and 5 paragraphs: top, step, gap between boxes, title / text offsets,
    # text line height
    EXTRAS_LAYOUT = {3: (124, 150, 24, 30, 68, 30), 4: (124, 122, 14, 26, 60, 27), 5: (84, 108, 10, 22, 55, 24)}

    def _draw_extras(self, surface, medium, small):
        """One paragraph for each screen of the main menu (Achievements, Jukebox, Credits, Options, and the Add-On when
        it is there, as the bar of Phobos); the chosen one has a frame. The more paragraphs, the smaller they are."""
        cx = BASE_WIDTH // 2
        doors = self.doors()
        width = 860
        top, step, gap, head_dy, body_dy, line_h = self.EXTRAS_LAYOUT[max(3, min(5, len(doors)))]
        for i, door in enumerate(doors):
            chosen = i == self.extras_index
            y = top + i * step
            box = pygame.Rect(cx - width // 2, y, width, step - gap)
            if chosen:
                menu_ui.highlight(surface, box, radius=10)
            else:
                menu_ui.panel(surface, box, radius=10, edge_w=1)
            head = t(DOOR_TITLES.get(door, door))
            _text(surface, medium, head, (255, 230, 120) if chosen else (170, 175, 200), y + head_dy, left=box.x + 28)
            body = getattr(self, "_body", None) or small
            for j, line in enumerate(_wrap(body, t("story_door_" + door), width - 60)[:2]):
                _text(surface, body, line, (205, 208, 228) if chosen else (140, 145, 170),
                      y + body_dy + j * line_h, left=box.x + 28)

    def _draw_bestiary(self, surface, font, medium, small):
        """Left: the enemies met so far. Right: what the pilot has learned about the selected one."""
        box = pygame.Rect(70, 78, BASE_WIDTH - 140, BASE_HEIGHT - 168)
        _fill(surface, menu_ui.PANEL_FILL, box, 10)
        pygame.draw.rect(surface, menu_ui.PANEL_EDGE, box, 2, border_radius=10)
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
                menu_ui.highlight(surface, row)
            col = (255, 230, 140) if focus else (200, 200, 215)
            _text_fit(surface, small, t(entry["name"]), col, y, row.x + 16, list_w - 26, scale=0.8)
            y += 56
        pygame.draw.line(surface, (60, 70, 100), (box.x + list_w + 24, box.y + 16),
                         (box.x + list_w + 24, box.bottom - 16), 1)

        entry, count = entries[self.best_index]
        tiers = ss.best_tiers(count, bool(entry.get("boss")))
        panel = pygame.Rect(box.x + list_w + 44, box.y + 16, box.w - list_w - 64, box.h - 32)
        cx = panel.centerx

        # picture: 1 kill = small, 3 = twice as big, 5 = animated
        frame = pygame.Rect(panel.x, panel.y, panel.w, 210)
        _fill(surface, (8, 10, 18), frame, 8)
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
            body = getattr(self, "_body", None) or small
            for line in _wrap(body, t(entry["text"]), panel.w - 40):
                _text(surface, body, line, (215, 218, 232), line_y, centerx=cx)
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
        _fill(surface, menu_ui.PANEL_FILL, box, 10)
        pygame.draw.rect(surface, menu_ui.PANEL_EDGE, box, 2, border_radius=10)
        act = int(self.state.get("act") or 1)
        chapter = "story_ch1" if self.cheat_unlock or act < 2 else ("story_ch2" if act == 2 else "story_ch3")
        _text(surface, small, t(chapter), (255, 170, 80), box.y + 28, left=box.x + 16)
        y = box.y + 52
        # the list scrolls: entries from `first` on, so that the focused row (taller) always fits. The entries are
        # the missions and, between two groups (story, hunts, BONUS), a small heading
        low = box.bottom - (62 if self._toast_level() == "standard" else 44)      # the rows stop above the toast
        room = low - y
        missions = self.missions()
        focus_i = max(0, min(len(missions) - 1, self.map_index))
        entries, last = [], None
        for i, mission in enumerate(missions):
            group = None if self.cheat_unlock else ss.mission_group(mission)
            if group is not None and group != last:
                entries.append(("head", group))
                last = group
            entries.append(("row", i))
        height = lambda e: MAP_HEAD_H if e[0] == "head" else 40
        focus_e = entries.index(("row", focus_i)) if missions else 0
        first = 0
        while first < focus_e and sum(height(e) + 4 for e in entries[first:focus_e]) + 76 + 4 > room:
            first += 1
        if first > 0:
            _text(surface, small, "^", (180, 180, 200), box.y + 28, right=box.right - 20)
        nxt = ss.next_mission(self.state, missions)
        for kind, ref in entries[first:]:
            if kind == "head":
                if y + MAP_HEAD_H > low:
                    _text(surface, small, "v", (180, 180, 200), low - 12, right=box.right - 20)
                    break
                _text_fit(surface, small, t("story_grp_" + ref), (120, 160, 210), y + MAP_HEAD_H // 2 + 2, box.x + 16,
                          400, scale=0.8)
                y += MAP_HEAD_H + 4
                continue
            i, mission = ref, missions[ref]
            if y + (76 if i == focus_i else 40) > low:
                _text(surface, small, "v", (180, 180, 200), low - 12, right=box.right - 20)
                break
            open_ = self.mission_open(mission)
            playable = self.mission_playable(mission)
            done = ss.mission_done(self.state, mission)
            focus = i == self.map_index
            # the focused row is taller: title line + one line for the blurb
            row = pygame.Rect(box.x + 12, y, box.w - 24, 76 if focus else 40)
            if focus:
                menu_ui.highlight(surface, row)
            if not open_:
                col = (110, 110, 120)
                state = t("story_locked")
            elif done:
                col = (140, 220, 160) if not focus else (190, 255, 190)
                state = t("story_replay") if mission.get("hunt") else t("story_cleared")
            elif playable:
                col = (255, 230, 140) if focus else (210, 210, 220)
                state = t("story_next") if mission is nxt else t("story_ready")
                if mission is nxt and not focus:
                    col = (255, 215, 120)                  # the suggested mission stands out in the list
            else:
                col = (180, 180, 140) if focus else (150, 150, 160)
                state = t("story_soon")
            cy = row.y + 20
            name = t(mission["title"])
            level = ss.mission_level(self.state, mission)
            if open_ and level is not None:
                name += "   " + t("story_level").format(n=level)
            _text(surface, small, name, col, cy, left=row.x + 16)
            _text(surface, small, state, col, cy, right=row.right - 14)
            if focus:
                before = None if open_ else ss.unlock_hint(self.state, mission)
                if before is not None:
                    _text_fit(surface, small, t("story_unlock_after").format(name=t(before["title"])), (225, 185, 120),
                              cy + 34, row.x + 28, row.w - 40)       # what opens it, in place of its blurb
                else:
                    _text_fit(surface, small, mission_blurb(mission), (170, 175, 195), cy + 34, row.x + 28, row.w - 40)
            y += row.h + 4
        if self.toast:
            self._draw_toast(surface, medium, small, box)

    def _toast_level(self):
        """'standard' for the result of a mission (won / failed), 'discreet' for the rest; '' without a toast."""
        if not self.toast:
            return ""
        return announce.TOAST_LEVEL.get(self.toast_kind, "discreet")

    def _draw_toast(self, surface, medium, small, box):
        """The message under the list of missions, in the colour of its type (see announce)."""
        ctype = announce.TOAST_COLOR.get(self.toast_kind, "info")
        level = self._toast_level()
        font = medium if level == "standard" else small
        col = announce.color_of(ctype)
        room = box.w - 40
        img = _render(font, self.toast, col)
        if font is medium and img.get_width() > room:      # too long for the big size: the small one first
            font, level = small, "discreet"
            img = _render(font, self.toast, col)
        if img.get_width() > room:                       # a long line (result + item found) shrinks to fit
            k = room / img.get_width()
            img = pygame.transform.smoothscale(img, (room, max(1, int(img.get_height() * k))))
        spec = announce.LEVELS[level]
        pad_x, pad_y = spec["pad"][0], 3 if level == "standard" else spec["pad"][1]
        cx, cy = box.centerx, box.bottom - 28
        plate = announce.plate(img.get_width() + 2 * pad_x, img.get_height() + 2 * pad_y, level, col)
        surface.blit(plate, (cx - plate.get_width() // 2, cy - plate.get_height() // 2))
        surface.blit(img, (cx - img.get_width() // 2, cy - img.get_height() // 2))

    def _hull_key(self, sl):
        """Picture key of a hull: the Shield wears the colour chosen in the paint shop."""
        key = sl.get("id")
        if key == "shield" and sl.get("tint") in ss.PAINT_TINTS:
            key = "shield_" + sl["tint"]
        elif key == "phoenix" and sl.get("tint") in ("blue", "gold"):
            key = "phoenix_" + sl["tint"]                 # the Phenix painted in Act 3
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
                border = menu_ui.SEL_EDGE                       # the lit frame of the menus
            else:
                border = menu_ui.PANEL_EDGE
            _fill(surface, menu_ui.PANEL_FILL, r, 10)
            pygame.draw.rect(surface, border, r, 2, border_radius=10)
            key = self._hull_key(sl)
            img = (self._portraits if chosen else self._greyed).get(key)
            if owned and img is not None:
                bob = int(math.sin(self.anim_t * 3.2) * 4) if chosen else 0
                surface.blit(img, (r.centerx - img.get_width() // 2, r.y + 12 + bob))
                label = t("ship_shield") if sl.get("id") == "shield" else t("ship_phoenix")
                col = (255, 230, 120) if chosen else (150, 150, 175)
                _text(surface, small, label, col, r.bottom - 22, centerx=r.centerx)
            elif sl.get("destroyed"):
                # Act 3: the hull lost in the attack on Phobos, dimmed and crossed out
                dim = self._greyed.get(key)
                if dim is not None:
                    dim = dim.copy()
                    dim.set_alpha(110)
                    surface.blit(dim, (r.centerx - dim.get_width() // 2, r.y + 12))
                pygame.draw.line(surface, menu_ui.DANGER, (r.x + 40, r.y + 24), (r.right - 40, r.bottom - 44), 3)
                pygame.draw.line(surface, menu_ui.DANGER, (r.right - 40, r.y + 24), (r.x + 40, r.bottom - 44), 3)
                label = t("ship_shield") if sl.get("id") == "shield" else t("ship_phoenix")
                _text(surface, small, label + " — " + t("story_hull_lost"), menu_ui.DANGER, r.bottom - 22,
                      centerx=r.centerx)
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
            _fill(surface, menu_ui.PANEL_FILL, r, 8)
            pygame.draw.rect(surface, menu_ui.PANEL_EDGE, r, 1, border_radius=8)
            col = (110, 115, 135) if (i == 2 and not dome and not phenix) else (220, 220, 235)
            if not owned:
                val = "—"
            _text(surface, small, lab, (150, 155, 175), r.y + 18, centerx=r.centerx)
            _text(surface, small, str(val), col, r.y + 46, centerx=r.centerx)

    def _draw_paint(self, surface, small, box):
        """The paint shop: the three colours of the hull it works on (the Shield, or the hull kept in Act 3)."""
        hull = (ss.paint_target(self.state) or {}).get("id") or "shield"
        title = "story_paint_title" if hull == "shield" else "story_paint_title_phenix"
        _text(surface, small, t(title).format(pts=ss.PAINT_COST), (255, 160, 70), box.y + 26, left=box.x + 16)
        tints = ss.paint_tints(self.state)
        current = ss.worn_tint(self.state)
        cell_w = 300
        x0 = box.centerx - (cell_w * 3 + 20 * 2) // 2
        for i, tint in enumerate(tints):
            r = pygame.Rect(x0 + i * (cell_w + 20), box.y + 52, cell_w, 190)
            focus = i == self.paint_choice
            _fill(surface, menu_ui.SEL_FILL if focus else (22, 24, 36), r, 8)
            pygame.draw.rect(surface, menu_ui.SEL_EDGE if focus else menu_ui.PANEL_EDGE, r, 3 if focus else 1,
                             border_radius=8)
            img = self._ships.get(hull + "_" + tint)
            if img is not None:
                surface.blit(img, (r.centerx - img.get_width() // 2, r.y + 24))
            label = t("story_paint_" + tint) + ("  (" + t("story_paint_worn") + ")" if tint == current else "")
            _text(surface, small, label, (255, 230, 140) if focus else (200, 200, 210), r.bottom - 28, centerx=r.centerx)

    def _draw_shop(self, surface, small):
        box = pygame.Rect(70, 308, BASE_WIDTH - 140, 328)
        _fill(surface, menu_ui.PANEL_FILL, box, 10)
        pygame.draw.rect(surface, menu_ui.PANEL_EDGE, box, 2, border_radius=10)
        if self.paint_mode:
            self._draw_paint(surface, small, box)
            return
        _text(surface, small, t("story_workshop"), (255, 160, 70), box.y + 26, left=box.x + 16)
        flags = self.state.get("flags") or {}
        window = SHOP_WINDOW
        rows = self.shop_rows()
        start = max(0, min(self.shop_index - 3, len(rows) - window))
        y = box.y + 46
        for i in range(start, min(len(rows), start + window)):
            sid, label, cost, need = rows[i]
            item = ss.item_of(sid)
            locked = bool(need) and not flags.get(need)
            if sid == "paint":
                locked = not ss.paint_state(self.state)["token"] or not ss.paint_affordable(self.state)
            if item:
                locked = story_items.status(self.state, item) != story_items.INSTALLED and not story_items.affordable(self.state, item)
            focus = self.zone == "shop" and i == self.shop_index
            row = pygame.Rect(box.x + 12, y, box.w - 24, 38)
            if focus:
                menu_ui.highlight(surface, row)
            col = (100, 100, 110) if locked else ((255, 230, 140) if focus else (200, 200, 210))
            extra = self._shop_extra(sid, cost, locked)
            if item:
                pic = loot.shop_frame(item, self.anim_t, 34)          # it turns, like when it falls in a mission
                if pic is not None:
                    surface.blit(pic, (row.x + 30 + (40 - pic.get_width()) // 2, row.centery - pic.get_height() // 2))
                _text(surface, small, t(label), col, row.centery, left=row.x + 80)
                _text(surface, small, t("item_%s_effect" % item), col if locked else (150, 195, 235),
                      row.centery, left=row.x + 400)
                perm = story_items.permanent(item)
                _text(surface, small, t("story_item_permanent" if perm else "story_item_single"),
                      col if locked else ((130, 220, 150) if perm else (235, 175, 110)),
                      row.centery, right=row.right - 180)
            else:
                _text(surface, small, t(label), col, row.centery, left=row.x + 16)
            _text(surface, small, extra, col, row.centery, right=row.right - 12)
            y += 40
        # there are more rows than the window shows: an arrow on the right edge says where
        ax = box.right - 14
        if start > 0:
            pygame.draw.polygon(surface, (255, 190, 110), [(ax - 7, box.y + 36), (ax + 7, box.y + 36), (ax, box.y + 26)])
        if start + window < len(rows):
            ay = box.y + 46 + window * 40 + 2
            pygame.draw.polygon(surface, (255, 190, 110), [(ax - 7, ay), (ax + 7, ay), (ax, ay + 10)])
        if 0 <= self.shop_index < len(rows):
            item = ss.item_of(rows[self.shop_index][0])
            if item and self.zone == "shop":
                _text_fit(surface, small, t("item_%s_desc" % item), (190, 200, 220), box.bottom - 22,
                          box.x + 20, box.w - 40)
