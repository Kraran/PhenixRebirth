# Development log — Phenix Rebirth 1.6.1

The detailed notes kept while the menus of the Adventure were rebuilt as the station of Phobos, the Lunar Lander got its five settings
and the four endings of the visual novel were written. The short version is in the [ROADMAP](../ROADMAP.md) ("Done in 1.6.1"). Some game
texts are quoted in French, the language they were first written in.

- **Menus of the Adventure, station of Phobos (steps 1 to 3 of the upgrade).** The hub wears riveted black steel: plates with a hazard
  strip, a copper cartouche for the title, steel badges for the pilot and the hull, lit rows with a gold edge, steel tabs and a steel
  help bar with copper keys. Each pane has its own picture behind it (the bar of Phobos for the map, the hangar, the corridor, the cabin and the
  walkway), made by `tools/make_ui_backdrops.py` and loaded on first use; the starfield is no longer drawn under the hub. The classic
  menus are untouched. The insides of the hangar, bestiary, journal and extras follow in the next steps. Tests: `tests/test_phobos_ui.py`.

- **Menus of the Adventure, step 4: the hangar.** The two hulls are holographic cards (blue glass, a grid, cut corners; the chosen hull is
  lit in gold), the stats are steel plates with a row of small cells for the lives and the speed, the points sit on a steel badge at the
  top right, the cards moved down so they no longer touch the badge of the pilot, the paint shop uses the lit row. Tests: `tests/test_phobos_ui.py`.

- **Menus of the Adventure, step 5: the bestiary.** The list of enemies and the sheet are two CRT terminals (dark green glass, scan lines,
  a steel bezel); the chosen entry is lit phosphor with dark letters, the picture of the enemy sits in a framed screen and the text is
  read in phosphor green. Tests: `tests/test_phobos_ui.py`.

- **Menus of the Adventure, step 6: the journal and the extras.** In the journal, what happened is read on a CRT terminal under the scenes
  to watch again (which keep the steel and the lit row). The Extras are holographic signs, like the ones of the corridor: blue glass with a
  grid, the chosen one lit in gold. Tests: `tests/test_phobos_ui.py`.

- **Menus of the Adventure, step 7: the screens before the hub.** The saves, the pilot name, the mode, the choice of the hull, the YES / NO
  questions and the Lunar Lander menu wear the steel too, on the picture of the pilot's quarters: steel cards (the chosen one lit in
  gold, DELETE and the destroying YES in red), the name typed on a CRT terminal with steel keys, the two hulls as holograms, the questions on
  a hazard plate, the preview of the Lander in a hologram, and the scenes of the visual novel on a solid blue glass panel. The
  toasts keep their coloured plates (their colour tells the type of the message). Tests: `tests/test_phobos_ui.py`.

- **Menus of the Adventure, airier.** The hub and the screens before it use smaller letters (24 for the text and the descriptions, 28 for the
  titles, instead of 28 and 32), the rows of the map are taller, and the plates keep a wider margin around their text (map, workshop,
  stat plates of the hangar, bestiary, journal, extras, mode and hull cards, Lander menu). The descriptions of the Extras get smaller
  the more paragraphs there are. The Jukebox and the Add-On, when opened from the Extras of the Adventure, now show the bar of the station
  behind them (with the steel help bar, and a little more room in the Jukebox list); from the main menu they are unchanged.
  Tests: `tests/test_phobos_ui.py`.

- **Menus of the Adventure, finishing (step 8).** The blurb under the mission under the cursor is no longer squeezed into one shrunk
  line: it is written in up to four lines and the row grows to hold them (long texts in the 13 languages were shrunk to 35 %). A new
  test (`tests/test_phobos_fit.py`) draws every pane of the hub and every screen before it in the 13 languages and fails when a text is
  shrunk below 70 %, goes out of the screen or touches another text. Drawing a pane takes about 2 ms (the budget of 60 FPS is 16.7 ms).

- **Lunar Lander test: five settings and a menu to choose one.** Europa (bright ice with long red-brown fractures, Jupiter in the sky),
  Deimos (dark dusty rock with worn craters, Mars in the sky; almost no gravity) and Triton (pinkish "cantaloupe" ice with dark
  streaks, Neptune in the sky) join Titan (Saturn in the sky) and the asteroid (other asteroids in the sky). The mother planets
  come from the photographs of the game. A menu before the flight picks the setting (to be taken out of the final missions).
  Tests: `tests/test_lander_bodies.py`.

- **Review of the texts of the Adventure.** Veteran variants of the four scenes that counted on the quantum anchor (Kamarasov is dead
  there: "there is no anchor to bring me back"); "Acte" everywhere, never "chapitre"; the dead texts of the old gate mission
  (it unlocked the dome, Dôme V does now) taken out; the NX01 sleeps "in orbit of Mars, on Phobos"; the khaki birds have a
  metallic skin (no plumage); "Bleus"/"Kakis" written the same way; the VIP thanks you for what you did "near Phobos"; "more
  than two years after the silence"; the Guardians and the Lander speak to "tu"; the paint shop names the hull it paints
  (Shield or Phenix); Dôme I is named after its scene ("l'épave du Shield"); Alcyone is 440 light-years away; small fixes
  (Sentinelle I, "Phenix" without accent, Peinture I). French and English; the other languages follow where the change is
  mechanical. Tests: `tests/test_text_review_1_6_1.py`.

- **BONUS - Lunar Lander.** The same level as the test, with its menu of five settings (the menu stays), but for real: a landing
  pays its points (plus the fuel left) in credits, a crash costs what a failure costs. Secret until the game is finished (the
  open ending told), then on the map of every act, replayable. The test mission stays a test (nothing won, nothing lost).
  Also: the stars of Europa, Deimos and Triton now pass BEHIND the mother planet, and the pictures of the menu load about twice
  as fast (faster noise and cells, same pixels) and are made in the background while the menu is read.
  Tests: `tests/test_lander_bodies.py`.

- **Visual novel: the four endings.** After the reaction to the last scene, an ending is told on the same picture, chosen by the
  total of points: Fâcherie (5–8), Distance (9–12), Amitié (13–16), Romance (17–20), each ending on its last line.
  Amitié and Romance: Lyra gives points × 500 credits (paid once). Romance: every price of the workshop (upgrades, items,
  launcher, missiles, paint) is 10 % lower, for good. A save that had already answered the last scene gets its ending after
  its next story mission. The cheat VNOV tells the ending without gift nor sale. Tests: `tests/test_vn_endings.py`.
