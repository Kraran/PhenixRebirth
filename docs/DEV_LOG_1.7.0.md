# Development log — Phenix Rebirth 1.7.0

The detailed notes kept while the escort modules, the landings and raids, the Guardians series, the END BONUS missions and the
Adventure style of the arcade game were made. The short version is in the [ROADMAP](../ROADMAP.md) ("Done in 1.7.0"). Some game
texts are quoted in French, the language they were first written in.

- **A loading bar.** At the start of the game and when a mission of the Adventure starts (`src/loading.py`): steps with the share
  of the bar they fill, kept moving by `loading.report()` from the heavy loops (flames of the Guardians, textures of the Lander and
  Scramble, sounds, logo, ship pictures), redrawn at most 30 times a second, the window kept alive. The start of the game shows the
  animated logo and an amber bar; a mission, the hangar of Phobos, its name in the copper cartouche and a phosphor bar, only when it
  takes more than 0.25 s. The first picture of a mission is drawn behind the bar; keys pressed while it loads are dropped. The
  setting menus of Lunar Lander and Scramble make the pictures of the five settings behind it. Tests: `tests/test_loading.py`.

- **Escort modules** (`src/gyro.py`). Two gyroscope satellites (an open ring turning, a sphere banded with light, a cannon;
  silver-blue for the Phenix, copper-amber for the Shield) follow a point by the cockpit a little late. Each salvo of the ship gets
  one more shot from each module in working order (×2, then ×3); a shot of a module that hits charges the Phenix gauge. A module stands
  in the way of what would hit the ship: the shots of the birds and of the boss take a point of its armour, a diving bird takes both
  down, the hull of the boss or a laser of the Guardians destroy it at once; sheltered in the dome or the Phenix form, nothing touches
  it. In the Adventure their pieces are found in the landings and raids (Deimos: module 1, Europa: module 2, the asteroid: the
  assembly plans, -40 %, and the armour plating, 2 shots), they are assembled at the workshop (3000 and 5000 credits) and a destroyed
  one is bought again at half price. Tests: `tests/test_gyro.py`, `tests/test_modules_workshop.py`.

- **Landings and raids.** Five optional Lunar Lander missions with a fixed setting and their own tank, and five raids on the Avioid
  bases with five steps of difficulty of the Scramble (the red commander takes 3, 3, 4, 4 and 5 hits); each one has its scene and
  its picture. Tests: `tests/test_landers.py`, `tests/test_raids.py`.

- **The Guardians.** The series Guardians I (the first fire), II (the wall of lasers), III (the Alpha Guardian) and Bestiary VI. Won,
  Guardians III gives the reflective coating: a laser that meets the dome of the Shield or the Phenix form splits where it touches,
  two halves sliding on a golden film round the ship then falling straight, thicker on the side touched (`src/laser_split.py`). The
  Guardians also come as reinforcements in some waves of the Adventure (Phenix III, the great raid, the repairs, la Riposte).
  Gargoyles burnt by a laser fall in ashes like the birds. Tests: `tests/test_guardian_squad.py`, `tests/test_guardian_ship_burn.py`.

- **End of a level.** The ship only flies up to the next level once the explosions of the last enemies are over, the debris of the
  Guardians and the birds still burning included (`update_play.guardian_blasts_running`).

- **END BONUS.** Secret missions at the end of Act IV, under "BONUS DE FIN": FINAL BONUS - Asteroids (4, 6, 8, 10 then 11 big
  asteroids a level, a faster saucer each level, two saucers every five levels), - Guardians (the classic game with one more Guardian
  each level, an Alpha more every five levels), - Lunar Lander (landing after landing with the fuel left, +50 / +25, the zones getting
  rarer) and - Scramble (run after run with 10 % more enemies, the first one at 80 %). Each one: the real GAME OVER at the end, the
  points paid in credits without a penalty, nothing won nor lost when it is left from the pause, a record kept and shown at the top,
  the voice announcing every level. Credits are capped at 99 999 (`story_state.CREDITS_MAX`). Tests: `tests/test_scramble.py`,
  `tests/test_lander.py`, `tests/test_asteroids*.py`.

- **Asteroids.** Three shapes of rock per size (`tools/make_asteroids.py`), one at random each time; the saucer crosses the screen once
  and never wraps round; its sound is no longer stopped by the sound manager of the Space Invaders missions.

- **Scramble.** Treacherous comets come from the left, behind the ship, after the first quarter of the comets section. The red
  commander's cry sounds once on the way to the base, with reverb and echoes (`assets/sounds/boss_yell_far.wav`, made by
  `tools/make_boss_yell_far.py`), 2 s after the last missile station has left the screen. The missile launchers of the base are
  armoured casemates: a first shot leaves a wreck that stops the ship's shots (not the fortress's), a second one blows it away.

- **The boss alien.** Solid: no see-through body or tentacles, and the inside of its mouth opaque black, for the green saucer
  commander and the red Scramble commander (`assets/sprites/boss_core*.png`).

- **Options > GAMEPLAY** (`src/arcade_style.py`). The Adventure style of a solo arcade game: two escort modules, antimatter missiles
  for the whole game (0 to 20) and the 2D reactor, with no high score. Never saved: the game always starts in Classic.

- **Voices.** The scenes of Bestiary I and of the VIP rescue are read aloud (French), like the intro of the Adventure.

- **The TEST missions are gone.** TEST - Guardians, - Lunar Lander, - Scramble and - Modules, and the training code behind them; a
  save keeps working (`story_state.REMOVED_MISSIONS`). The Adventure is no longer marked "(Beta)" in the main menu.

- **Review before the release.** Dead code taken out (unused imports, locals, functions and translation keys never read); the
  GAMEPLAY options, the key of the antimatter missile and the codes typed on the high scores translated in the 13 languages; the
  help of the refresh cap lists 144 Hz; the README follows the game (five tabs of options, the missile at 1000 credits, the new
  missions). The replay fingerprint of `boss_fight` is made with Python 3.12, the version of the CI: the test is skipped on other
  versions of Python (`tests/test_replay.py`).
