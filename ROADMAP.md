# Roadmap — Phenix Rebirth
Current release: **v1.4.5**

## Unreleased (towards 1.5.0 — Adventure)

- Announcer: the stage callouts go up to **level 31** (`assets/sounds/level22.wav` … `level31.wav`, new recordings, plus a new `level21.wav`). "To boldly go where no one has gone before" moves from level 21 to **level 31**; levels 25 and 30 are the two longer "Warning" callouts. They are played like every other level callout (announcer channel, volume 0.88, at the start of the stage and when a stage is cleared, also in the Adventure's paint missions by their level). Past level 31 the announcer stays silent (`game.LAST_ANNOUNCED_LEVEL`). Tests: `tests/test_level_announcer.py`.
- In-game music, three additions (Options > Audio > In-game music; the tests are in `tests/test_ingame_music.py`). **1.** The four songs of Lyra Voss (Eternal Dawn, What We Lost, No Mercy Left, Oldest Fear) join the five themes of the jukebox in the choices, with their translated jukebox titles. **2.** Your own music: the game makes an empty folder **`musique_perso`** next to `settings.json` (so next to the game, in the root of `D:\PhenixRebirth`) at its first start; every mp3, wav, ogg, flac, opus or tracker file (mod, xm, it, s3m) dropped in it shows up after the game's tracks (its ID3 title when it has one, else its file name) and loops during the run. The choice is saved as `custom:<file name>`; a file that is gone (or renamed) falls back to None; a file the mixer cannot read is tried once, not every frame (`src/custom_music.py`, `SoundManager.register_music`). The folder is not tracked by git. **3.** The long title of a track no longer runs over the label of the row ("Musique en jeu" over "Phoenix - Nostalgie pour Elise (Final)"): any value of an option that is too wide is drawn smaller, then cut in the middle with "..." so its end stays readable (`draw_frame.fit_text`); the help panel on the right gives the whole title of the chosen track and its title is now the name of the option (it read "OPTIONS"). **Announcer:** the voice of the announcer says "Achievement!" (`assets/sounds/achievement.wav`) each time a haut-fait is unlocked or goes up a tier (arcade, menus, Adventure page), on the announcer channel (the music steps back) unless another announcement is speaking.
- Announcements in a fight: the banner (1UP, achievements, codes...) is now a layer of the scene, drawn **over the boss saucer and under every alien and its shots** (and the ship, the explosions, the items), so the action crosses the text instead of being hidden by it. Nothing else changes: same colours, sizes, plates and durations. In a plain run the banner is drawn once in the scene (twice over, as before: it had always been drawn twice, which is why its plate is a little denser) and no longer a last time over everything; under an overlay (pause, game over, hot-seat hand-off) and in the menus it is still drawn last, over everything, so an unlock is still seen (`draw_frame.announce_layer`). Tests: `tests/test_announce_layer.py`
- Controls, step 4b (keys and buttons, the gamepad part): third tab **Manette** in the screen "Touches et boutons" (`src/keybind_pad.py`). A drawn pad with one card per action: **Tir**, **Phénix**, **Pause**, each tied by a line to the buttons it uses (the chosen card lights its buttons); **Déplacer** (stick, D-pad) and **Menus** (A, B, LB / RB) are shown locked because they never change. Enter (or A) on a card, then press the buttons: each press adds the button to the action or removes it when it already has it (1 to 4 buttons per action); a button of another action is taken from it with a notice; what would leave an action without a button is refused. The D-pad, the stick, Enter or Esc end the capture, so do 6 seconds of silence (each press starts the clock again). A, B, LB and RB run the menus: they cannot be the pause button. Switch **"Mêmes boutons pour toutes les manettes"** (on by default): on, one table serves every pad; off, each place (the first and the second pad plugged in) has its own table, one pill per pad, Left / Right (or a button pressed on that pad) choose the one shown, "Copier la manette n" gives the shown pad the buttons of the other one (after a question), and turning the switch off starts the second pad from a copy of the first. "Valeurs par défaut" restores the pad that is shown (every pad while they share). Orange dot on a changed action, "par défaut" on the card that has the cursor. With no pad plugged in the buttons cannot be pressed and a notice says so. 28 new texts in the 13 languages; the help of the option no longer says "bientôt". Tests: `tests/test_keybind_pad.py`
- Controls, step 4a (keys and buttons, the keyboard part): new row "Touches et boutons" in the Options, "Game" tab (also from the pause menu), under the two coop rows. It opens a screen with one tab per keyboard: **Clavier 1** (the left-hand keys of a coop game: A or Q, D, W or Z, S, Left Ctrl, Left Shift) and **Clavier 2** (the arrows, Space or Right Ctrl, Right Shift: solo, hot-seat and the right-hand coop player). One row per action (left, right, up, down, fire, Phénix / Shield), two keys per action (so the game still works on AZERTY and QWERTY). Enter waits for the new key (Esc cancels, Delete clears, it gives up by itself after 8 s), Left / Right choose the key of the row, Tab / Page Up / Page Down change the keyboard. A key that another action already uses asks "swap" (the other action gets the old key) or "cancel"; a key the menus need (Esc, Enter, Tab, Backspace, Delete, F1-F15, Pause, Caps Lock, system keys) is refused with a notice; an action always keeps at least one key. A modified key shows an orange dot; the right panel shows the default and the current keys. "Valeurs par défaut" (answer "Annuler" chosen first) restores the keyboard that is shown only. A pad drives the screen too (D-pad / stick, A, B back, Y clear, LB / RB tabs). Each change is saved at once; settings.json (`bindings`) only holds what differs from the defaults, so a default changed later reaches whoever did not touch it, and a damaged file never stops the game. The ship, the Phénix key (edge-triggered, as before) and the pause button of a pad read the same tables (`src/bindings.py`); the pad tables (fire, Phénix, pause, one per place, with the "same buttons for every pad" switch) are in place and used by the game, their screen (the drawn pad) comes next. Replay fingerprints of the 6 fuzz scenarios renewed (the options have one more row; the 3 scripted games, which never open the options, are identical to the bit). Tests: `tests/test_keybinds.py` (settings, ship, Phénix, pads, the screen in every mode and in the 13 languages)
- Controls, step 3 (the control of each coop player): two new rows in the Options, "Game" tab, under "Contrôle": "Coop 1" and "Coop 2". Each one cycles Auto, "Touches ZQSD/WASD" (left-hand keyboard: A or Q, D, W or Z, S, Left Ctrl, Left Shift), "Flèches" (arrows, Space or Right Ctrl, Right Shift) and "Manette n" for each pad plugged in (n = the order they were plugged in); a device taken by the other player is left out. Auto (default): two pads -> pad 1 and pad 2; one pad -> pad 1 and the arrows; none -> both halves of the keyboard. So every case is possible: two pads, keyboard + pad (either way round), two players on one keyboard even with pads plugged in. A pad that is not plugged in counts as Auto. The choice applies to the next coop game and is saved (`coop_p1`, `coop_p2` in settings.json). The Phénix keys follow the keyboard: Left Shift for whoever plays on the left-hand keys, Right Shift for whoever plays on the arrows (even if that is player 1). The values of the two rows are drawn in the smaller font (they are long in some languages). Replay fingerprints of the 7 fuzz scenarios renewed (the options have two more rows). Tests: `tests/test_coop_controls.py`
- Controls, step 2 (automatic control in solo): the "Contrôle" option has three values: Auto (default), Clavier, Manette. In Auto the last device used flies the ship: a key gives the control to the keys, a button or a stick pushed (more than half way) gives it to the pad, at once, in a game or on a menu. A pad that is plugged in at launch, or the first one plugged in later, takes the control. With several pads, the one just used is the one that flies the ship (solo and hot-seat; coop keeps one pad per player). Unplugging the only pad pauses (as before) and gives the control to the keys. The old saved "input_mode" is forgotten (it used to be saved even when nothing was chosen, so a pad could stay ignored); the choice is now `control_pref` in settings.json. The option shows the device in use: "Auto (Manette)". Tests: `tests/test_control_auto.py`
- Controls, step 1 (foundation): the gamepads are followed by their identifier, in the order they were plugged in (`src/controls.py`, `PadRegistry`), instead of "index 0" all over the game. Plugging or unplugging a pad no longer mixes up the players: in coop the first pad stays the first player's. A coop ship whose pad is unplugged stops (the keys of the other player never move it), the game pauses and says which player ("Manette du joueur 2 débranchée"), and a pad plugged in again goes to the ship without one. No more error written to `errors.log` every frame for a dead pad. Solo with its only pad gone falls back on the keys. The left-hand keyboard (coop) works the same on AZERTY and QWERTY: A or Q = left, W or Z = up (tested). Next steps: automatic "last device used" in solo, then a screen to choose the control of each player (two pads, pad + keyboard, two players on one keyboard)
- Announcements: one colour per type and three sizes (`src/announce.py`, tests in `tests/test_announce.py`). Colours: GAIN cyan (1UP, points, items), RÉUSSITE green (mission won), RÉCOMPENSE pink (achievements, new record, new BONUS mission), INFORMATION blue (level, mission name, counters, act), DANGER red (failure, death, dome broken, pad unplugged, GAME OVER), SPÉCIAL orange (cheat codes and their banners), NEUTRE grey (system, hints). Sizes: major (64 px, strong plate: GAME OVER, mission won / VIP, new record), standard (32 px, medium plate: 1UP, achievements, codes, mission result toast), discreet (28 px, light plate: pad unplugged, screenshot, other toasts). The colours are kept far from those of the ship HUD (score, gauge, name), which are unchanged. Banner text is now fully opaque (the old one shared a cached picture and faded it). Menus and adventure menus are unchanged
- Adventure: leaving the Adventure for the normal game asks first. B / Esc (or pad B) on the slot list opens "QUITTER L'AVENTURE ?" ("Retourner au jeu normal ?", NO lit first, same buttons as the delete question); YES goes back to the main menu, NO or B / Esc stays on the slot list. Going up from the hangar to the slot list is unchanged (`StoryHub.back()` / `confirm()`, screen "leave")
- Adventure, Act 1: new mission "BONUS : le réacteur à impulsion bidimensionnelle (Shield)" (`src/galaga.py`). It appears on the map
  (in every act, until its reactor is caught) once the "Bestiaire : gargouilles sombres" hunt is won, and flies the Shield. It is four
  waves of blue and khaki avioids of level 2 (x1.1 speed, +10 points a bird) that come in like in Namco's Galaga: chains of birds follow
  curved paths, loop over the screen, bomb the ship (they shoot a lot, more and more) and leave. The birds still alive when their chain
  leaves join the next wave, which is bigger and deadlier; the fourth and last wave keeps coming back until every bird is destroyed or
  the ship is. Failure rules are the usual ones (Normal: 5 % lost, can be tried again; Veteran: the pilot falls)
- Adventure, BONUS mission: almost twice as many birds in the waves (11 / 11 / 14 / 14 new birds instead of 6 / 6 / 8 / 8, 50 in all; the survivors still come on top). Each bird shoots a little less often (4.0 / 3.5 / 3.0 / 2.6 s between two shots instead of 3.2 to 2.1) and up to 44 shots can be in the sky (34 before), so the sky is fuller without being twice as deadly
- Adventure: the two-dimensional impulse reactor is an item, not a gift. It falls ONCE, at a random moment of the waves (at the latest
  when the last wave comes in), like the other loot items (new picture from a video, `assets/items/reactor*.png`; the random loot is off in the BONUS missions and they do not
  count in the gap between two drops). Caught, it goes on sale in the hangar for its own hull only: **Réacteur 2D (Shield), 2000 points**,
  installed on the Shield only. Not caught (the waves won or lost without it), or caught but the ship is lost before the end of the mission: nothing is acquired and the mission is offered again, as often as needed. The reactor must be caught AND the mission finished (the map says "Réacteur perdu" after a lost mission). The four other loot items are still kept when the mission is lost
  Installed, it is permanent (never used up, kept in the next Acts): the hull flies up and down the lower third of the screen in every
  mission (arrow keys up / down, left stick or d-pad up / down; Z / S in coop keyboard 1). Saves made with the first version of the
  BONUS mission (`vertical_thrust` flag) keep the flight: the Shield reactor is installed for free. The arcade game does not change
- Adventure: second BONUS mission "BONUS : le réacteur à impulsion bidimensionnelle (Phenix)", offered once the Phenix is in the hangar
  (and until its reactor is caught, in the maps of Acts 2 and 3). Same four waves flown with the Phenix, but the avioids shoot one and
  a half times as often (`PHENIX_FIRE_MULT`; up to 66 shots in the sky). Its reactor, **Réacteur 2D (Phenix), 4000 points**, is sold
  with the Phenix hull selected and installed on the Phenix only. The two missions are independent. The title, the HUD title, the
  item name and its text say "(Shield)" or "(Phenix)"
- Tests: `tests/test_render_cache.py` no longer fails at random (a video clip that started on its own time replaced the still picture the two tests looked at; they now use a still picture)
- Adventure: the journal lines of the five Bestiary scenes carry the same numbers: "Revoir : Bestiaire I : les oiseaux bleus" (it was "Première sortie : les oiseaux bleus"), "Revoir : Bestiaire II : les oiseaux kaki", "III : les gargouilles", "IV : les gargouilles sombres", "V : le commandant avioïde" (English: "Watch again: Bestiary I: the blue birds"...)
- Adventure: the five Bestiary hunts now carry their number in Roman numerals, like "Dôme I" and "Phenix I": "Bestiaire I : Première sortie", "Bestiaire II : oiseaux kaki", "Bestiaire III : gargouilles", "Bestiaire IV : gargouilles sombres", "Bestiaire V : le commandant avioïde" (and the same in every language, e.g. "Bestiary III: gargoyles"). The accent of "Première" is back. The titles of the story scenes in the journal are unchanged
- Adventure, Act 2: new story scene for the fifth Bestiary hunt, "Bestiaire : le commandant avioïde" (`best_boss`, picture and video `assets/story/soucoupe_commandement.jpg/.mp4`: the black cracked command saucer in orbit of Neptune, with green and dark gargoyles around it). Three paragraphs written by Kraran (corrected by Claude) about the telepathic brain of the Avioids, told the first time the hunt is launched, then replayable from the journal ("Revoir : Bestiaire : le commandant avioïde", between the Dome I and Painting I lines). Same mechanism as the other scenes (`story_state.SCENES`); test `tests/test_story_scene_commandant.py`
- Adventure: new story scene for the fourth Bestiary hunt, "Bestiaire : les gargouilles sombres" (`best_s4`, picture and video `assets/story/gargouilles_sombres.jpg/.mp4`: three purple gargoyles in front of Uranus). Same mechanics as the other scenes: told the first time the hunt is launched, watched again from the journal right after the gargoyles' one. Text by Claude (adapted to the picture: purple, Uranus), to be read
- Adventure: new story scene for the third Bestiary hunt, "Bestiaire : les gargouilles" (`best_s3`, picture and video `assets/story/gargouilles.jpg/.mp4`: two gargoyles in front of Saturn). Three paragraphs told the first time the hunt is launched (A on the last slide flies the mission), watched again from the journal ("Revoir : Bestiaire : les gargouilles", right after the khaki birds). Text by Claude, to be read
- Adventure, Add-On: new scene "Bar de la station Phobos" (`story_state.ADDON_SCENES`, picture and video `assets/story/bar_phobos.jpg/.mp4`), and a fourth paragraph in the Extras tab, "BAR DE LA STATION PHOBOS" (in capitals like the others), that opens the Add-On menu (it comes back to the tab with B / Esc). The paragraph is there only when the Add-On is available (`addon.addon_ready()`); with four paragraphs the boxes are a little smaller. The first time that paragraph is opened in a save (A on it) the scene is told instead: the text goes up over the video, *Phoenix* is written in italics (a `*title*` markup of the scene texts), "Nostalgie pour Élise" fades in slowly under it at 34 % of the music volume (new `SoundManager.set_music_level`, and `play_music(..., fade_in_ms=)`); A on the last slide (or B / Esc, which skips it) fades to black (0.9 s) and the Add-On menu comes up from black, with the same theme which then goes back to normal volume. The next times A opens the Add-On menu at once. The scene is in the journal ("Revoir : Bar de la station Phobos"; watched again it ends back in the journal). No voice yet
- Adventure, reactor: while the ship climbs with the two-dimensional impulse reactor (key / stick up) the jets are the long ones of the flight up to the next stage (`Player.climbing`, `boost_engines`); they grow while it climbs and die back when it stops, goes down or across, or reaches the top of its range. Both hulls
- Adventure, hangar: the pictures of the loot items in the workshop rows now turn (the same animation as when they fall in a mission, `loot.shop_frame`, driven by the hub clock), and each row says in colour if the item is "USAGE UNIQUE" (the four loot items: used up by the next mission) or "PERMANENT" (the two reactors)
- Adventure, quantum anchor return (after a lost mission in Normal / Novice): for the first 0.8 s of the vortex (`SKIP_LOCK_SEC`) the confirm keys (Enter, Space, Esc) and the pad buttons no longer skip it, so the fire button still being hit as the ship dies does not cut the animation short. After that they skip it as before
- Adventure, Veteran: when the ship dies, the normal GAME OVER of the game is played (explosion, GAME OVER card, announcer voice,
  pad rumble) before the slot list where the save is now a memorial. The fall is written into the save at the moment of death,
  so closing the game during the card does not save the pilot. Normal and Novice are unchanged (quantum anchor return)
- Adventure, paint missions (Space Invaders): the announcer now says the real level of the mission (Level 1, 2, 3 in the first pass,
  4, 5, 6 in the next one...) instead of always "Level 1" (`Game._announced_level`). Past level 21 (no recording) it stays silent, like elsewhere
- Help screen: the enemies carry the names of the Bestiary and of the Adventure, with their stage (French: Avioïde éclaireur stage 1,
  Avioïde kaki stage 2, Gargouille stage 3, Gargouille sombre stage 4, Commandant avioïde stage 5; English: Scout Avioid, Khaki Avioid,
  Gargoyle, Dark Gargoyle, Avioid commander). The story, "how to play" and Veteran lines use the same words (the Veteran note is now two
  lines). Other languages keep their own translations
- Adventure, Novice mode: the workshop sells "Vies 4" (the lives you end up with) where Normal sells "Vies 2"; Act 3 will read "Vies 5"
- Adventure: Dome I is now open from the start of Act 1, like "Bestiaire : Premiere sortie" (it no longer waits for the
  4th Bestiary hunt). The rest of the dome series is unchanged: each mission opens the next one and is flown once
- Ships: new engine jets (`src/engine_flame.py`). Each nozzle now gives a straight, dense jet of burning gas (white-hot
  at the nozzle, then yellow / orange, fading at the end, no point), drawn behind the hull. Colours are kept (Phoenix
  argent / blue / gold, Shield red / green / violet, Phenix red / blue). Nozzle places are read on the hull pictures;
  the Phenix jets are wider and longer, and the jets follow the morph in both directions. The jets lengthen with the
  thrust and sputter out when the ship dies. Pictures are pre-rendered in `assets/sprites/engines/` by
  `tools/make_engine_flames.py` (made on the fly if a file is missing); no random numbers are used.
  While the ships fly up to the next stage the jets are twice as long and a very little wider (`BURST_LENGTH`, `BURST_WIDTH`),
  and come back to normal as they arrive
- Background: the small asteroid Dinkinesh now comes from a video: its little moon circles the rock. One turn takes 48 s
  (the video lasts 6 s), 144 cells in `assets/sprites/planets/asteroid_dinkinesh_anim.png` made by
  `tools/make_planet_strip.py`. The rock keeps its size, two asteroids do not turn in step, other planets are unchanged
- Adventure code reorganised, nothing changes on screen: rules and save data now live in
  `story_state.py` (tested without a window), `story.py` only draws the menus
- Adventure save is now one file per slot (`story_1.json` … `story_3.json`, version 4).
  The old draft `story.json` is no longer read; start a new adventure
- Dome time and recharge are saved in seconds (no longer tied to 60 Hz)
- The adventure journal follows the language chosen in Options
- Adventure menus: texts are now centred inside their boxes (hangar, workshop, mission map, journal)
- No more frozen explosion pieces on the menu after an adventure mission
- Adventure start: slot list (3 saves with pilot name, act, date and mode), pilot name entry, Novice / Normal / Veteran choice
- Adventure failure rules: a failed mission (death) gives no points and costs 5 % of your points; Veteran mode has permanent death. Quitting a mission by choice changes nothing
- Adventure, Novice mode: the mode choice now has three cards (Novice, Normal, Veteran; Normal is lit first). A Novice pilot
  starts with 3 lives (the workshop sells a 4th the way it sells the 2nd in Normal) and loses only 2 % of the points on a failed
  mission instead of 5 %. Everything else is identical to Normal. The slot keeps its starting lives in `lives_base` (saves made
  before the mode have none and behave as Normal). Normal's text now reads "5%" so the sign is not split across two lines
- Act 1 hangar: the Shield starts slow (40 % speed), with one life, no dome, and dies the moment
  it touches the screen edge. The workshop sells speed 60 % then 80 %, a second life, and the arcade
  edge rule (slowdown, then death if you stay too long). The dome becomes a series of quests (Act 2).
  Prices: 300 / 800 / 2000 / 1000. The Phenix slot shows as empty and cannot be selected in Act 1.
  Saves from the earlier draft are converted (speed steps move down, dome back offline)
- Adventure intro: after the name and the mode, 4 slides (Huygens, its destruction, Phobos, Kamarasov)
  scroll like the credits over a picture. Action button = next slide, B / Esc = skip. Shown once per
  adventure. Veteran mode has its own last slide: Professor Kamarasov died before finishing the
  quantum anchor. The last sentence carries the pilot's name. Up / Down (or the pad) change the
  scroll speed smoothly, as in the credits. The journal always starts with "Watch the introduction
  again". French text first (other languages show the same text until translated)
- Adventure Bestiary: a new screen left of the journal. Each enemy shows up once you have destroyed
  one (picture), then at 50 (picture twice as big), 100 (animated), 150 (presentation text) and 200
  (every such enemy is worth +10 points, the Veteran bonus of the arcade game). Bosses use a short
  table: 1, 2, 3, 5 and 10 defeats, the last one adding +1000 points per boss. Enemies destroyed
  count even when you lose a mission, but not when you leave one by choice. Names are drawn smaller
- The boss is now in the Bestiary: not the saucer but the life form that commands it, the alien at its heart
  ("Avioid Commander"). It shows up once you have destroyed it (the end of Act 1, mission "Gateway to Act 2"), then at
  2 (picture twice as big), 3 (animated with the game's own frames), 5 (presentation text, a draft to review) and
  10 defeats (+1000 points per boss). The boss of any Adventure mission counts
- The four Bestiary sorties of Act 1 are "hunt" missions that can be flown again as often as you like
  (shown as REPLAYABLE). The journal writes, under each one, how many enemies were destroyed in all
  its runs

- Adventure journal: only "Watch the introduction again" can be selected; Up / Down scroll the other
  lines (mission comments and kill totals are not selectable)
- Adventure cheat UNLK (typed on the mission map): every mission can be played without unlocking it.
  While it is on, nothing is saved (a small red banner at the top left says so); loading the save again starts clean

- Adventure, dome series (Act 1): four chained missions after the Bestiary sorties. Each one flies three
  waves in a row of one enemy kind at the speed of arcade levels 1 / 6 / 11 (Blues), 2 / 7 / 12 (Khakis),
  3 / 8 / 13 (Gargoyles) and 4 / 9 / 14 (Dark Gargoyles). Clearing one opens the next; a cleared one
  cannot be flown again (the four Bestiary sorties stay replayable). The old "chapter relief" mission is
  replaced by this series

- Adventure, Dome V "the swarm": the four enemies at once (levels 11 to 14, speed of level 11), each kind
  replaced as it falls, up to twice its normal count in all (26 / 44 / 14 / 20 = 104), but only a third of
  a normal screen at once (4 / 7 / 2 / 3 on screen). It is won when all of them are down; a counter shows how many are left. It brings the dome online and opens the
  first dome upgrade in the workshop
- Adventure, levels of the Bestiary sorties: each victory raises the mission one level (1, 2, 3...). Level 2
  flies the same enemies as arcade level +5 (a little faster each time, no limit). The level is shown on
  the mission map, in the journal and on the screen during the mission. A lost run keeps the level
- Adventure, Act 2: after the gateway the map changes (title "ACT 2"): the four Bestiary sorties stay (with their
  level), the dome missions are gone, and a series of five missions appears, each one opened by the previous
  and flown once only (arcade levels 16 and up, x1.3 speed): the signal (16-17), the jamming (the swarm at
  level 16), the relay (18-19), the approach (16-19) and the awakening (16-20, boss). The last one hands
  over the Phenix: slot 2 of the hangar opens, with its own workshop (speed 80 %, lives 2, walls, and the
  Phenix gauge 60 % -> 80 %: the Phenix form lasts 60 % of the arcade one at first)
- Adventure, Act 2 paint series: three optional missions flown in order, each a Space Invaders clone with our
  own enemies: 4 rows of 11 (bottom to top: blue birds, khaki birds, gargoyles, dark gargoyles, all animated)
  march in step from side to side and drop one line together when a wall is touched, then turn back; the
  march speeds up as the grid empties. Now and then a miniature of the boss saucer crosses the top: 500 to 1000
  points, the more centred the killing shot, the more it pays (it does not have to be killed to win). An enemy
  reaching the ship's line ends the run. The three missions are levels 1, 2, 3 (faster and lower each time);
  flown again as a whole series (to change colour again) they are levels 4, 5, 6, then 7, 8, 9, and so on.
  The 2nd and 3rd missions of a pass start one and two lines (grid rows) lower; the wings flap at a steady pace.
  Sounds: a step sound for every march step (very slightly higher the faster the march) and the saucer sound,
  waved to last as long as the saucer takes to cross the screen. Both are in stereo (the saucer by its position,
  the steps by the centre of the group); the saucer sound is tied to the saucer on screen (paused with the game,
  cut as soon as the saucer is gone).
  The saucer is a 72 x 30 miniature of a dark cracked-hull saucer picture (assets/sprites/saucer_mini.png), the hull
  lightened so it shows on the sky, its red parts (band, lights) pulsing in brightness once a second with a red
  halo; it crosses either way at random, can only be hit once its centre is on screen, and its fade-out no
  longer alters the shared picture (that made every later saucer see-through: a sound with nothing to see).
  Winning the third opens the paint shop in the Shield workshop for ONE change of colour (red, green, violet),
  which costs 500 points (nothing is spent if the colour is kept, or when leaving the shop).
  The level is shown on the map, in the journal and on screen
- Adventure menus: the panel backgrounds (slots, hangar, workshop, map, journal, Bestiary, paint shop...) are slightly
  see-through (about 76 % opaque, `MENU_ALPHA` in story.py): the starfield shows through a little
- Points: from level 6, every enemy (birds, gargoyles, boss core, saucer decorations; Adventure included) is worth
  +10 more per 5-level round: the old prices in levels 1-5, +10 in 6-10, +20 in 11-15... Armor bricks stay at
  1 point. Veteran and Bestiary bonuses still come on top. The Space Invaders saucer keeps its 500 to 1000
- Faster drawing, same picture: the adventure menu texts are rendered once instead of every frame; the story
  screens (intro, mission scenes) no longer rebuild their dark band and text window each frame and no longer
  draw the starfield under the full-screen picture (about 2.5 times faster); the invader saucer is painted when the
  mission starts, so its first appearance no longer makes the game stutter for a moment
- Adventure scenes: a mission can come with a story scene (a picture and a scrolling text, like the intro), told
  once, the first time the mission is launched; A on the last slide then flies the mission, B / Esc skips it
  (back to the map). Once seen, it gets a line in the journal, right under "Watch the introduction again",
  to watch it again (Up / Down go through these lines, then scroll). First scene: Dome I, the wreck of a Shield
  drifting around Jupiter. French text first, as for the intro
- Adventure scenes: second scene, Paint I (first launch of the first paint mission): Wallems' clandestine workshop
  dug into 434-Hungaria. Same mechanism, told once, replayable from the journal (listed after the Dome I line)
- Adventure scenes: the Paint I text now says "l'astéroïde 434-Hungaria" and its two typos are fixed (teintes uniques,
  ça serait)
- Adventure scenes: a slide picture can be a looping video clip, `assets/story/<name>.mp4` (see "Video clips" below),
  with the same shading, reading band and scrolling text; a missing or broken clip shows the still picture. First
  clip: the blue birds of the first sortie (10 s, picture only, the video's sound is not used)
- Adventure intro: the four slides (Huygens, its destruction, Phobos, Kamarasov) and the Veteran's last one (Kamarasov's
  death) are now video clips instead of stills: `assets/story/huygens.mp4`, `huygens_destroyed.mp4`, `phobos.mp4`,
  `kamarasov.mp4`, `kamarasov_veteran.mp4`, made with `tools/encode_clip.py` from the 752x416 videos given (6 s, Phobos 10 s;
  no sound, 24 fps, a loop without a seam, 0.3 to 0.7 MB each). Nothing in the code changed: a slide whose picture has a
  clip plays it (see above), so the same applies to the replay from the journal. The stills stay as posters (shown while
  a clip starts, or without ffmpeg). Tests: `tests/test_intro_videos.py`
- Adventure scenes: Wallems' workshop (Paint I) is now a video too: `assets/story/atelier_wallems.mp4` (the 752x416 video given,
  6 s, no sound, loop without a seam, 0.2 MB), made with `tools/encode_clip.py`; the still stays as the poster. No code
  change (a slide with a clip plays it). Tests: `tests/test_story_scene_paint.py`
- Adventure intro read aloud (French only): each of the four slides has a recorded voice (`assets/story/voice/story_intro_1.ogg`,
  `_2`, `_3`, `_4` (Normal) and `_4v` (Veteran: Kamarasov's death); recorded with ElevenLabs, voice "Eliott"; the name of the
  pilot is not said: "moi, j'en suis maintenant certain"). The voice starts 1.6 s after the slide appears; the music steps back
  (the announcer channel). The text no longer scrolls at its own speed: it follows the voice, the line being said is kept near
  the middle of the screen (it comes down slowly, 380 to 500 px), the text first rises into place in 3.2 s, and it goes on rising
  until the voice ends (so the text is longer than the screen or not, the line said is on screen). `assets/story/voice/marks.json`
  says when each line is said (start, end, in seconds), made by `tools/make_intro_voice.py story_intro_1=take.mp3 ...`: it
  evens out the level, cuts the silence at both ends, writes the ogg and finds the times of the lines from the pauses of the
  recording (printed, to be read: run it again if a time is wrong). A missing or damaged `marks.json` or a recording that
  cannot play gives the old scroll at its own speed (as do the other languages, the muted sound, `sfx_muted`). Up / Down still
  speed the text up or back, which then comes back to the voice in a moment. The slide being left (A, B / Esc, the end of the
  story) stops the voice with a short fade. Replaying the intro from the journal reads it again. Code: `StoryHub._tick_voice`,
  `_voice_target`, `_voice_scroll`, `SoundManager.play_narration` / `stop_narration` / `narration_busy`,
  `story_state.intro_voice`. The Credits name the service (the free plan asks for it): "Voix de l'introduction : ElevenLabs
  (elevenlabs.io)". Two takes of slide 3 were given (files 3 and 4): the newer one (4) is the one used. Tests: `tests/test_intro_voice.py`
- Adventure: four save slots instead of three (`SLOT_COUNT = 4`, `story_4.json`); the slot list shows four cards
- Adventure: a mission no longer says the next level out loud when its boss falls (the arcade still does)
- Adventure scenes: the Paint I text uses the "…" sign instead of three dots, like the other scenes
- Adventure scenes: third scene, the very first sortie (Bestiary, blue birds over Mars, `assets/story/oiseaux_bleus.jpg`):
  told the first time "Première sortie" is launched, replayable from the journal (first line after the introduction)
- Adventure paint shop: a victory fanfare (trumpets, `assets/sounds/paint_fanfare.wav`) plays when the Shield is
  painted. The hub only asks for sounds (`sound_events` / `take_sounds`); the game plays them
- Fix: a mission of the Adventure lost for good went back to the map without the soft restart that "Quit game" does, so the dead ship of the mission (and its speed, lives, score, stage and any pending game over) stayed in the game and the next arcade game began with it: its game over ran at once. `game_init.reset_run` now forgets the whole run when a mission ends (`Game._end_adventure`). Tests: `tests/test_run_cleared_after_mission.py`
- Adventure, Act 1: the dome swarm (Dôme V) is easier after the beta testers' feedback: each kind comes 1.6 times its normal count in all (`SWARM_SCREENS = 1.6`: 21 / 35 / 11 / 16 = 83 enemies instead of 104). Still a third of a screen shown at once. The Phenix swarm (52) is unchanged
- Adventure scenes: the second Bestiary hunt (khaki birds, `best_s2`) has its own scene, told the first time it is launched and replayable from the journal right after the first sortie: picture `assets/story/oiseaux_kaki.jpg` and clip `assets/story/oiseaux_kaki.mp4` (made with `tools/encode_clip.py`), text `story_scene_best2` (draft by Claude). Tests: `tests/test_story_scene_kaki.py`
- Adventure paint shop: the background music fades down to 12 % in half a second while the trumpets play and comes back
  over their last 2 seconds (`SoundManager.MUSIC_FADE`, `fade_music`, smooth curve, product with the announcer duck;
  nothing when the sound is muted or does not play). Tests: `tests/test_music_fade.py`
- Adventure, loot items: four single-use objects that fall during a mission (`src/story_items.py` for the rules, `src/loot.py` for the
  falling sprite and the pictures, tests `tests/test_story_items.py` and `tests/test_loot_in_mission.py`). **Singularity Core**
  (6000 PTS, fire rate x2: the bullets fly twice as fast, so the ship fires twice as often), **Noyau Genesis** (6000, one more
  life), **Réacteur Hyperion** (4000, speed +40 %: the speed of the workshop x 1.4), **Tesla Seal** (2000, the electric walls
  do nothing, Shield and Phenix form). Life of an item in one Act: lootable -> found (caught during a mission, on sale in the
  hangar workshop until bought) -> installed (bought: works in the next mission that ends, shown top right) -> used (gone for
  the Act, never falls again). One copy at a time, never twice in an Act; a new Act gives them all back. Loot is rare: at most one
  mission in three carries an item (a drop needs two missions without one before it, then 40 % per mission), and it falls 6 to
  30 s into the mission, from the top of the screen to the bottom (130 px/s) at a place the ship can still reach. Caught = touched
  by the ship. Recorded when the mission ends, win or lose (`record_result(..., loot=, used=)`); leaving a mission by choice records
  nothing and uses nothing, like the points. Sprites: `assets/items/<id>.png` (36 frames, about 44 px, the size of the birds of
  the stages 1 and 2) and `<id>_icon.png` (the workshop), made from the videos and pictures given with
  `tools/make_item_sprites.py`. The workshop shows a picture, the effect and the price per item, and the description of the
  focused item under the list (six rows at a time). Save: `items` key (additive, version 4 unchanged). The replay reference
  of the `adventure` scenario was regenerated (the drop draw uses the random generator)
- Adventure, loot items: the paint missions (Space Invaders) never carry an item and do not count in the gap between two drops; an item bought still works in them, like in any other mission. Tests: `tests/test_loot_in_mission.py`
- Adventure: the first mission is now called "Bestiaire : Premiere sortie" (like the other Bestiary hunts, in every language; `story_m_sortie`). Its scene title ("Première sortie : les oiseaux bleus") is unchanged
- Adventure, Act 2: new Bestiary hunt "the Avioid commander" (`best_boss`), right after the four Bestiary hunts. It
  flies the arcade boss level (stage 5), can be replayed, and goes up one level at each victory (boss of stage 5, 10,
  15...), like the other hunts. It counts for the Bestiary boss entry
- Adventure, hangar: the two hulls are drawn like the ship select screen (portrait in a frame, gold frame and
  slight bob for the chosen one, the other one dimmed the same way), without the Phenix / dome animations.
  The chosen hull flies every mission (the map shows "SHIP: ..."); a mission can impose a hull later
  (`ship` field of a mission, none uses it yet)
- Adventure, cheat code 2222 on the mission map: jumps to Act 2 (every Act 1 mission counts as won, the Phenix
  is not given). Nothing is saved any more afterwards (red banner, like UNLK); reloading the slot goes back
  to the real save
- Adventure, Phenix swarm (mission 2 of the Phenix series): one normal screen of each enemy in all (52), not three
- Adventure, cheat code NIX2 in the hangar: Act 2 on, the five Phenix missions won, the Phenix unlocked; nothing saved
- Adventure, gateway to Act 2: a full run of arcade levels 11 to 15 (wave counter on screen). The death of
  the boss starts Act 2 (the save shows ACT 2). The mission map scrolls now that it is longer

### Planned for 1.5.0 (Adventure, 3 acts)

- Done: 3 save slots (name, date, act, mode), name entry with keyboard or gamepad (on-screen
  keyboard), Normal / Veteran choice, delete with confirmation
- Done: failed mission = back to the workshop, no gain and 5 % of your points lost (rounded,
  never below 0); Veteran = permanent death (the save becomes a memorial).
  Quitting a mission by choice changes nothing (no gain, no loss, back to the hangar)
- Act 1: weak Shield upgraded to about 80 % of the arcade ship. Done: the Act 1 hangar and workshop
  (speed, lives, walls); to come: the Act 1 missions and story
- Act 2: quests to obtain the Phenix (boss at the end) and first upgrades
- Act 3: both ships up to 100 %, epic final quest
- Story written together, French first, translations later

## Done in 1.4.5

- 144 Hz option (Options: 60 / 75 / 120 / 144) with an exact frame limiter
  (60 / 75 / 120 / 144 images per second instead of about 62 / 77 / 125 / 166)
- Smoother fullscreen on ultrawide screens: bezels no longer rebuilt every frame,
  the frame is drawn straight onto the screen (no 5 MB copy) and the redundant clear is gone
- No more stutter when a haut-fait progresses: achievements are saved in the background
- Title menu no longer rescans the Add-on (MAME) folders on every frame
- Explosions look the same at any refresh rate (60 / 75 / 120 / 144 Hz)
- Safer saves: settings, high scores, achievements and story are written atomically
  (a crash or power cut can no longer leave a truncated file); an unreadable file is kept as `.corrupt`
- `errors.log` next to the game records unexpected errors that used to be silent
- Developer tools: `tools/bench.py` (smoothness benchmark, `--profile`) and `tools/probe_present.py`

## Done in 1.4.4

- Starfield comet update
- New Add-on menu

## Done in 1.4.3

- Title-only seasonal overlays (Christmas / Halloween)
- April Fools logo gag (boot, 1 April)
- Starfield comet (1 per cycle, stages 1–4, rare on menus)

## Done in 1.4.0

- Stage-1 intro: ship arrives from the bottom (same as mid-run transitions)
- English announcer VO for stages 1–15 (5 / 10 / 15 include warning)
- Ship select: Welcome aboard Phenix / Shield
- Boss saucer rebuilt from photo tiles (rotating 2-row shield, pair-deco systems)
- Boss 500 / 1000 pts; ports glow; destructible keel beacon
- LVL5 draw cache (band, glows, living hit-order)
- i18n pass: UI still 13 languages; announcer remains English audio

## Done in 1.3.0

- Shield ship + select screen (solo / hot-seat / coop combos)
- Achievements page
- Jukebox + PHEQ1 visualizer + ID3 titles
- In-game music track option
- Stereo SFX, extra OST tracks
- Help page 2: Phenix and Shield
- Starfield: two extra asteroids (Dinkinesh pair + Pallas)
- Credits OST list uses the five ID3 titles
- i18n: jukebox hints and locked achievements in all 13 languages

## Done in 1.2.1

- Attract keeps the menu theme; session-only in-game audio mix (SFX / SFX+music / music / off)
- Music loops natively (no MP3 reload hitch)
- Help: animated stage-1/2 birds, looping Phenix, looping boss core
- Boss core tentacle cycle in the saucer (preloaded frames, centered blit)
- HUD: Novice / Veteran label (solo top-right, coop & hot seat centered under lives)
- Input swallows: quit-confirm No, attract Exit, Options/Credits Esc = back
- Help pages 13 s each; FPS counter shifted off the difficulty label

## Done in 1.2.0

- GPU present via pygame.SCALED (60 FPS with bezels on ultrawide)
- Refresh cap 60 / 75 / 120 Hz + VSync On / Adaptive / Off
- Options help panel (focused row)
- Packed pause Options list
- Stage-clear: leftover enemy shots removed before fly-up
- Collision restore + swept player / enemy bullets
- High-score cheats no longer abort on empty unicode (LVL2–5, LIVE, PHEN)
- Credits: hold to speed / reverse / drift; D-pad no longer leaves the screen
- Credits: beta testers, GPU line, GitHub + itch links
- Desktop cover + pad refocus when rebuilding the display

## Done in 1.1.0

- 2-player hot-seat and coop
- Autofire option, rumble, coop high-score mark
- Bezel GPU path experiments (superseded in 1.2.0)

## Done in 1.0.0

- PHENIX transform mode (gauge, morph, dual fire, cancel + cooldown)
- Ship / firebird art, boss core, enemy pass
- CRT scanlines (3 levels)
- Ultrawide bezels (Phenix, Tesla, Blue, Flame)
- Two-page help + starfield (planets & galaxies)
- i18n (13 languages), pause, difficulties
- Windows build via `build_exe.bat`

## Done earlier

- **0.2.0-rc.1** — feature-complete release candidate
- **0.1.0** — stages 1–5, boss, difficulties, high scores, 13 languages, attract mode

## Planned (post-1.2.1)

### Play & feel
- [ ] Native **144 Hz** path (cap already easy; exclusive modes still report 60 on some GPUs)
- [ ] Attract AI polish
- [ ] Optional separate lives in coop

### Packaging
- [ ] Optional one-file Windows build
- [ ] Linux package notes
- [ ] Batocera / `.pygame` pack (after a final PC freeze)

### Code health
- [ ] Split `src/game.py` into menus / combat / present modules
- [ ] Broader automated tests

### Meta
- [ ] Additional languages from contributors

Suggestions welcome via GitHub Issues.
- Video clips, done properly (`src/videoclip.py`): ffmpeg is now part of the game. It comes from `bin/ffmpeg(.exe)` if
  present, else from the `imageio-ffmpeg` package (in `requirements.txt`, packed into the exe by `build_exe.bat` and
  `PhenixRebirth.spec`), else from the PATH. The jukebox and add-on clips use the same lookup
- Video clips: a clip is one small silent H.264 file (24 fps, a loop without a seam) instead of a folder of JPEG frames.
  ffmpeg runs beside the game at a low priority, loops the file by itself and scales it to the canvas; the game copies
  one finished picture per frame and darkens it with a single multiply (about 1 ms per frame, against 5 ms before);
  frames wait in a six-frame queue, which also hides the short pause ffmpeg makes at each loop point
- Video clips: `tools/encode_clip.py SOURCE.mp4 NAME` turns any video into a clip (no sound, 24 fps, `--crf 27`, width
  capped at 1280, last half second dissolved into the first so the loop has no cut) and makes the poster `NAME.jpg`.
  The first sortie clip went from 8.9 MB of frames (6.5 MB with its sound as an mp4) to a 1.25 MB file
- Video clips: a clip is picked up as soon as `assets/story/<picture>.mp4` exists next to `<picture>.jpg` (no list to
  update); the poster shows during the quarter second ffmpeg needs to start, and when ffmpeg is missing or fails
- Boot intro and jukebox video on the same player (`src/intro.py`, `src/videoclip.py`): `assets/video/intro.mp4` (silent
  H.264, 6.2 MB, from the original video) replaces the 433 JPEG frames (16 MB); its music stays `intro.ogg`. The picture
  and the music start together (ffmpeg first, the music with the first picture), `main.py` starts ffmpeg on the intro
  before the game loads, the picture is shrunk to the canvas without cropping, and a late decoder skips frames rather
  than fall behind the sound. The jukebox entry plays the same clip (`open_clip`, `start_audio`). Without ffmpeg the
  boot intro is left out and the jukebox shows nothing for that entry
- Video clips: the player now also plays a clip once (`loop=False`, `ended`), fits it in a box (`fit="contain"`, size
  read from the mp4 header by `videoclip.mp4_info`) and can keep a hard clock; `tools/encode_clip.py` got `--no-poster`
- Phenix wing tips: the eight flight frames (`assets/sprites/phenix/phenix_NN.png`) were cut by the edge of their canvas
  on both sides (and at the top, on the flame frames). They now sit on a canvas 16 px wider on each side and 12 px taller
  above and below (105x134 instead of 73x110), the wings going on past the old edge and ending in a point. The margin is
  even on every side, so the ship keeps its size and its place: drawn in the game, every pixel of the old ship is at the
  same screen position with the same colour. The help page, which scaled the Phenix by the height of its picture, now
  scales it by the ship (`src/phenix_art.py`), so it does not shrink. The wing tips are an extrapolation made by
  `tools/extend_wings.py` (the originals are in git, commit f5fdcf4), not the lost drawing
- Smooth Phenix transformation, both ways: the change was 4 drawn pictures in 0.45 s (the last one never shown), began
  on the second picture and popped in from the ship and out into the flight. It is now the ship, the 4 drawn pictures and
  the first flight picture, with 4 cross-dissolves between each two (26 pictures, `phenix_art.morph_sequence`), so every
  screen frame brings a new picture; the way back is the same pictures reversed, opened by 3 pictures that fade the flight
  picture on show into it (`lead_in`), and a change cancelled half way goes back from the picture on show. The ship select
  preview plays the same pictures over the same time. The Shield ship change is as it was. The in-between pictures are
  computed, not drawn
- Back from a MAME session, the game window did not always get the focus: Windows only lets the program in front
  take the foreground, and the single `SetForegroundWindow` call was never checked. `src/window_focus.py` now joins
  the input of the window in front, brings the game window up, checks that it is really the foreground window, tries
  again up to 6 times (an Alt tap as a last resort), and the game asks once more after the black cover is removed.
  A failure is written to `errors.log` ("the game window could not be put in front"). Written from the code and tested
  with a fake Windows, not seen on a real one
- Flash in the Phenix transformation: the pictures in the middle of the change (ship to Phenix, and back) are lightened and
  have a soft round halo behind them, strongest when the wings open and exactly nil at both ends, so the change starts and
  ends on the plain pictures (`phenix_art.flash_level`, `FLASH_*`). The colour of the halo is taken from the fire of the
  Phenix picture (`flash_colour`): orange, golden or blue by tint. It is baked into the pictures (a canvas 220x220, still
  centred, so the ship does not move). In the ship select preview the halo is smaller (`PREVIEW_FLASH_RADIUS`) and the
  panel keeps its size (`preview_extent`, `core_size`)
- Ship select screen: the Phenix transformation plays a little slower there (0.65 s in, 0.60 s out instead of 0.45 and
  0.40; `PREVIEW_MORPH_IN_SEC` / `PREVIEW_MORPH_OUT_SEC` in `src/phenix_art.py`). The game itself is not slowed
- Shield dome, smoother and in the right order: the way out played the drawn pictures backwards (the dome vanished at
  once, came back to half its size, then vanished again). It now fades from the dome on show into the first picture of the
  way out and shrinks to nothing in order. Pictures are added between the drawn ones as for the Phenix (8 drawn make 15 for
  the forming, 6 make 16 for the going away: `phenix_art.dissolve`, `SHIELD_*`), so a new picture shows at almost every screen
  frame (6 of 14 before). The durations are unchanged (0.22 s forming, 0.26 s going away): the 2 s countdown of the
  bubble waits for the forming and its 5 s cooldown starts after the going away, so longer durations would change the
  game, not only the look (a test holds the 0.22 + 2 + 0.26 s). A forming cancelled half way goes away from the picture
  on show. Without numpy the drawn pictures are used (the way out in the right order all the same). The ship select
  preview is as it was
- Phenix transformation, pictures between the drawn ones made by motion instead of a plain fade: a cross-dissolve leaves the
  hull showing through the wings as a ghost. `tools/bake_morph_flow.py` (the only place that needs OpenCV) measures with
  optical flow how each picture of the change moves into the next and saves it in `assets/sprites/morph_flow.npz` (0.5 MB,
  made once on the silver ship: the three colours have the same shape). The game applies it with numpy only
  (`phenix_art.morph_flow`, `_warp`, `_mix_flow`): the details are moved along the flow, then faded. The last pair, where the
  wings come out of nothing, uses 60 % of the flow (all of it stretches the feathers to the corners). Same 26 pictures,
  same durations, same ends. Without the file, with a canvas that does not fit or without numpy, the pictures are plain
  cross-dissolves. Run the tool again if the drawn pictures change. The Shield dome is as it was
- Adventure: Options, Jukebox and Credits are reachable from the Adventure, in ONE tab at the far left, "Extras" (left of
  the Bestiary), with three paragraphs, one for each screen. It first was three tabs, which was three screens for nothing.
  Up / Down choose the paragraph, A / Enter opens the real screen of the main menu, which works as from the main menu (Left /
  Right change a value there, so they could not also change tab). B / Esc, or the screen's own way out ("Retour" line,
  Esc in the reset question, B on the gamepad), brings the Adventure back on the Extras tab, on the same paragraph, same
  save, nothing reloaded. From the Adventure, Left / Right in the Jukebox do not go on to the high scores. The main menu
  is as it was. Code: `story.DOORS`, `StoryHub._draw_extras`, `Game._open_story_door`, `Game._story_door_tick`
- Adventure, quantum anchor: the whirlwind is now a vortex of space. What is behind the picture is the colour of the scrolling
  background (no more blue arms of light or blue tint), and 500 stars of the scrolling's colours are drawn into the spiral,
  each with a short curved trail that gets longer as it goes faster; the light of the middle and the flash are white. Same
  timing, same sound. The stars are always the same ones (a generator of their own: the game's random numbers are untouched)
- Adventure: return to base by the quantum anchor when a mission is lost (Normal mode only: a fallen Veteran has no anchor,
  the anchor was never finished, so the memorial and slot list come at once as before). The last picture of the mission is
  taken (`Game._anchor_snapshot`), then, in 3.1 s (`src/anchor_fx.py`): 1.6 s of whirlwind (the picture turns, more in the
  middle than outside, shrinks to a point; the legend "ANCRAGE QUANTIQUE / Retour à la base..." comes in the
  second half), 0.3 s of flash that opens from the middle, 0.9 s where the flash fades and shows the mission map. The result
  is banked at once as before (nothing is lost if the game is closed). During the whirlwind and the flash keys and the pad do
  nothing, except Enter / Space / Esc or a pad button, which skip to the end of the flash (and F12 for a screenshot); the map
  keeps a 0.3 s grace so a held key does not act on it. The whirlwind is computed by numpy on a 400x225 picture (about 7 ms a
  frame) and scaled up; the real picture shows through for the first 0.15 s so nothing jumps. Without numpy there is no
  effect (the map comes back at once, as before). Sound `assets/sounds/anchor_return.wav`, made by
  `tools/make_anchor_sound.py` (numpy only). Code: `anchor_fx.AnchorReturn`, `Game._start_anchor_return`,
  `Game._tick_anchor_fx`, `Game._anchor_blocks`. Tests: `tests/test_anchor_return.py`
