"""
Menu sounds: a tick when the cursor moves, a chime when a choice is validated, a softer one going back, a buzz
when something is refused.

The menus have dozens of input paths (keyboard, D-pad, stick, buttons, one set per screen: see input_events.py).
Rather than add a sound to each of them, Game.handle_events takes a picture of the menu state before and after
each key / button / stick event (`snapshot`) and `react` plays what the difference means:
- a new screen (or a question opened / closed, the game paused or a fade started): confirm, or back if the key
  was a back key (Esc, Backspace, B, Start), or move for Left / Right switching between the score screens;
- the cursor or a value changed: move (confirm if it was a confirm key, back if it was a back key);
- a confirm key that changed nothing on a screen where it should do something (a greyed entry, a locked
  mission, a purchase that cannot be paid, a value row): deny.
Nothing is played in a game, in the attract demo, under the story scenes (they are read aloud), or when the
menu changes by itself (help screen after a wait, end of a fade): only an input can make a menu sound.

The sounds are made by tools/make_menu_sounds.py. Nothing here uses `random` (the reference replay is untouched).
"""
import pygame

import addon as mame_addon
from errlog import log_exc

MOVE, CONFIRM, BACK, DENY = "menu_move", "menu_confirm", "menu_back", "menu_deny"

_BACK_KEYS = (pygame.K_ESCAPE, pygame.K_BACKSPACE)
_CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
_PAD_CONFIRM, _PAD_BACK, _PAD_START = 0, 1, (6, 7, 9)

def kind_of(game, event):
    """'confirm', 'back' or 'nav' for an input event; None for the events that are not menu input."""
    et = event.type
    if et == pygame.KEYDOWN:
        if event.key in _BACK_KEYS:
            return "back"
        if event.key in _CONFIRM_KEYS:
            return "confirm"
        try:
            if game._is_menu_confirm(event.key):
                return "confirm"
        except Exception:
            pass
        return "nav"
    if et == pygame.JOYBUTTONDOWN:
        if event.button == _PAD_CONFIRM:
            return "confirm"
        if event.button == _PAD_BACK or event.button in _PAD_START:
            return "back"
        return None
    if et in (pygame.JOYHATMOTION, pygame.JOYAXISMOTION):
        return "nav"
    return None


def watching(game, event=None):
    """True when an input may move a menu: title menus, the pause menu, the high-score entry."""
    if getattr(game, "attract_mode", False):
        return False
    if getattr(game, "anchor_fx", None) is not None:
        return False
    if not getattr(game, "started", False):
        story = getattr(game, "story", None)
        if (getattr(game, "menu_screen", "") == "story_hub" and story is not None
                and getattr(story, "screen", "") == "intro"):
            return False                     # a story scene: the voice and the music are what matter
        if getattr(game, "menu_screen", "") == "jukebox" and getattr(game, "juke_video", False):
            return False
        return True
    if getattr(game, "game_over", False):
        return getattr(game, "hs_phase", None) in ("enter", "table")
    if getattr(game, "paused", False):
        return True                          # the pause menu
    # in a game: only the key / button that opens the pause (moving and shooting are not menu input)
    if event is None:
        return False
    if event.type == pygame.KEYDOWN:
        return event.key == pygame.K_ESCAPE
    if event.type == pygame.JOYBUTTONDOWN:
        return event.button in _PAD_START
    return False


def _story_part(game):
    story = getattr(game, "story", None)
    if story is None or getattr(game, "menu_screen", "") != "story_hub":
        return None
    entry = getattr(story, "entry", None)
    state = getattr(story, "state", None) or {}
    return {
        "screen": (story.screen, story.pane, getattr(story, "paint_mode", False)),
        "cursor": (story.sel, story.col, story.del_yes, story.mode_index, story.zone, story.shop_index,
                   story.paint_choice, story.map_index, story.log_scroll, story.log_cursor,
                   story.best_index, story.extras_index, state.get("selected_slot"),
                   (entry.row, entry.col, entry.text) if entry is not None else None),
        "progress": (state.get("credits"), getattr(story, "intro_index", 0)),
        "msg": (story.msg, story.toast),
    }


def snapshot(game):
    """What the menus show, as plain values that can be compared."""
    g = game
    snap = {
        "screen": (bool(g.started), bool(g.paused), bool(getattr(g, "pause_options", False)), g.menu_screen,
                   bool(g.quit_confirm), getattr(g, "fade_phase", None) is not None,
                   bool(g.game_over), getattr(g, "hs_phase", None)),
        "cursor": (g.menu_index, getattr(g, "pause_index", 0), getattr(g, "quit_index", 0),
                   getattr(g, "play_mode", ""), getattr(g, "difficulty", ""),
                   getattr(g, "ship_select_index", 0), getattr(g, "juke_index", 0),
                   getattr(g, "hs_char_index", 0), tuple(getattr(g, "hs_name", ()) or ())),
        "story": _story_part(g),
        "options": None,
    }
    if g.menu_screen == "options" and (not g.started or g.paused):
        try:
            snap["options"] = tuple(g._options_labels())
        except Exception:
            log_exc("menu_sfx.snapshot")
    return snap


def safe_snapshot(game):
    """`snapshot`, or None if it fails (a menu sound is never worth breaking the input)."""
    try:
        return snapshot(game)
    except Exception:
        log_exc("menu_sfx.safe_snapshot")
        return None


def _focused_option(game):
    try:
        spec = game._options_spec()
        return spec[game.menu_index] if 0 <= game.menu_index < len(spec) else ""
    except Exception:
        return ""


def _addon_greyed(game):
    if game.menu_screen != "main" or game.menu_index != 2:
        return False
    try:
        return not mame_addon.addon_ready()
    except Exception:
        return True


def choose(game, before, after, kind):
    """The sound name for one input (None: silence)."""
    if kind is None:
        return None
    sb, sa = before.get("story"), after.get("story")
    screen_changed = before["screen"] != after["screen"] or (
        sb is not None and sa is not None and sb["screen"] != sa["screen"])
    if screen_changed:
        b_started, b_paused = before["screen"][0], before["screen"][1]
        a_started, a_paused = after["screen"][0], after["screen"][1]
        if b_started and not b_paused and a_paused:
            return CONFIRM                   # the game is paused (Esc or Start)
        if not b_started and a_started:
            return None                      # a mission or a game starts: its own sounds take over
        if kind == "back":
            return BACK
        if kind == "nav":
            return MOVE                      # Left / Right between the scores, the feats and the jukebox
        return CONFIRM
    changed = (before["cursor"] != after["cursor"] or before["options"] != after["options"]
               or (sb is not None and sa is not None and (sb["cursor"] != sa["cursor"] or sb["progress"] != sa["progress"])))
    if changed:
        if before["options"] != after["options"] and _focused_option(game) == "sfx":
            return None                      # the effects volume already plays a shot at its new level
        if kind == "confirm":
            return CONFIRM
        if kind == "back":
            return BACK
        return MOVE
    if kind != "confirm" or after["screen"][0]:
        return None
    if _addon_greyed(game):
        return DENY
    if game.menu_screen in ("main", "options"):
        return DENY                          # a row that is set with Left / Right: nothing to open
    if sa is not None:
        story = game.story
        if sa["msg"] != sb["msg"] and any(sa["msg"]):
            return DENY                      # the hub answered with a message (empty name, damaged save, no paint...)
        if story.screen == "hub" and (story.pane == "map" or (story.pane == "hangar" and story.zone == "shop")):
            return DENY                      # a locked mission, a purchase out of reach
    return None


def react(game, before, after, kind):
    """Play the sound of one input (see `choose`)."""
    if before is None or after is None:
        return None
    try:
        name = choose(game, before, after, kind)
    except Exception:
        log_exc("menu_sfx.react")
        return None
    if name is None:
        return None
    sounds = getattr(game, "sounds", None)
    if sounds is not None:
        try:
            sounds.play(name)
        except Exception:
            log_exc("menu_sfx.react")
    return name
