# Development log — Phenix Rebirth 1.8.1

The detailed notes of the changes since 1.8.0. The short version is in the [ROADMAP](../ROADMAP.md) ("Done in 1.8.1").

- **Every pad in the Xbox order** (`src/pad_map.py`, PR #289). The game reads the pads as SDL joysticks, whose numbers
  depend on the pad: a DualShock 4 gives L1 = 9, Options = 6 and its D-pad as four buttons. `pad_map.wrap` reads the
  SDL game controller mapping of each pad once (`pygame._sdl2.controller`, `get_mapping`) and, when it is not already
  the Xbox order, wraps the pad (`Pad`: `get_button`, `get_hat`, `get_axis` in the Xbox order) in
  `controls.PadRegistry`; `pad_map.translate` gives the events of `game.handle_events` the Xbox numbers (a D-pad made
  of buttons moves hat 0). `SDL_GAMECONTROLLER_USE_BUTTON_LABELS = 0` is set before `pygame.init`: the face buttons go
  by their place, the bottom one confirms on a Switch pad too. An Xbox pad, or one SDL does not know, is left as it is.
  Tests: `tests/test_pad_family.py`.

- **The buttons of the pad in use** (`src/pad_style.py`, PR #289, #290). The family comes from the name of the pad
  (the list of Swarm Attack and Fluvial Strike): Xbox, PlayStation, PlayStation 5, Nintendo. `pad_style.label` names a
  button (Cross / Croix... in the 13 languages, L1, Options, Create; B A Y X, L R, − +), `face_surface` draws a face
  button (the PlayStation symbols drawn, in their colours). The help bar (`hint_bar`), the help texts
  (`bindings.help_values`) and the *Keys and buttons* screen (`keybind_pad`: the pad, the chips, the message of the
  menu buttons) follow `pad_style.current`, the family of the last pad used. A PlayStation pad is drawn with its D-pad
  above its left stick (`keybind_pad._stick_and_cross`; only the drawing).

- **The reflective coating at the workshop** (`src/story_state.py`, `src/story.py`, PR #291, #292). `REFLECT_FLAG`
  (Gardiens III won) now opens the row `COATING_ROW` (2000 PTS, `COATING_PRICE`); buying it sets `COATING_FLAG`.
  `has_coating` (both flags) decides the mission's `reflect`. The hangar draws the coated hull with a golden edge and a
  gleam every 3.2 s (`_draw_coating_sheen`), the row its golden scale (`_draw_coating_icon`), PERMANENT, then
  INSTALLED. The scene `story_scene_coat` (FR/EN) says the film waits at the workshop. Tests:
  `tests/test_coating_workshop.py`.

- **The clips started again** (`src/videoclip.py`, PR #293). A run of ffmpeg that gives no picture (it could not
  start, or stopped at once) is started again after 0.5, 1.5 and 3 s (`RETRY_WAITS`) before the still takes over; a
  looping clip whose decoder stops is started again the same way. What ffmpeg wrote on its error output (a temporary
  file) and each new try go to errors.log (`log_note`). Before, one failure left the scene on its still, silently.
  Tests: `tests/test_videoclip_retry.py`.
