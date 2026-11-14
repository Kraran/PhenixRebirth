# Development log — Phenix Rebirth 1.7.2

The detailed notes kept while Défense de Phobos, Sacha the wingman and BONUS FINAL - Nuée were made, and while the
fixes of a full playthrough of the Adventure were done. The short version is in the [ROADMAP](../ROADMAP.md) ("Done in
1.7.2"). Some game texts are quoted in French, the language they were first written in.

- **Sacha, the wingman** (`src/wingman.py`). A young pilot of Phobos in his own ship, an EDF-17 C (the interceptor of
  the generation before the Shield, `assets/sprites/sacha/`: intact, after one hit, after two), flown by the computer.
  Every 1/`DECIDE_HZ` s he weighs the places of the line he could reach: the shots of the birds, the lasers of the
  Guardians (and those still charging), the divers, the edges, the pilot's own place and a bird above to shoot at. A
  good pilot, not a perfect one: he notices a shot `REACTION` s late and looks `HORIZON` s ahead. He flies smoothly
  (`SWITCH_GAIN`, `MIN_HOP`, `HOLD`, `ACCEL`, `EASE`; measured in a simulation: direction changes 0.82 → 0.38 a second)
  and no longer stops dead at the end of a quick dodge. He comes in from below `ENTER_DELAY` s into the first wave,
  with the landing dust of the ships. He cannot die: a shot or a laser damages his ship (`HITS` = 3), a collision takes
  it straight to its last level; its two jets (`engine_flame` "edf17") smoke more and more. After the last hit he
  takes off, turns about and dives off the bottom of the screen. His points are his own (not in the pilot's score).
  His five radio lines have his voice (`assets/sounds/sacha/`, recorded with ElevenLabs and put through a small radio;
  `sounds.play_radio`, a channel of its own, held during the pause). Tests: `tests/test_wingman.py`.

- **His skill** (`wingman.SKILLS`, the `wingman_skill` of a mission). Level 1 for Défense de Phobos I, 2 for II, 3 for
  III; the ace of BONUS FINAL - Nuée (`wingman.ACE`) above them. Measured in the same swarm: 3.1, 2.4 and 1.7 hits a
  minute (0.8 for the ace): he stays touchable.

- **Défense de Phobos I, II and III** (`story_state.MISSIONS` `phobos_1` to `phobos_3`). One compulsory mission per
  act, with Sacha: after Dôme V (level 11; no Guardians in Act 1, the dark gargoyles ×1.5 in the last wave instead),
  after Phenix II (level 16, 30 % more enemies on screen and in all, 3 Guardians in the last wave) and after Gardiens III
  (level 21, 50 % more on screen and in all, 3 Guardians). Four waves, each adding a kind (`enemy.spawn_swarm`
  `kinds`, `crowd`, `boost`). Each has its scene; the scene « Sacha » is told after the first victory (`SACHA_SCENE`). A
  save already further on gets the flags it needs (`PHOBOS_SKIPS`). Tests: `tests/test_defense_phobos.py`.

- **BONUS FINAL - Nuée** (`src/swarm_bonus.py`, mission `bonus_swarm`). Once the game is finished: the last wave of
  Défense de Phobos II without an end (level 16, 30 % more on screen, the fallen always come back), growing to its full
  screen in a minute (`RAMP`), then three Guardians, and three more each time the last one falls. Five versions, chosen
  in a menu: alone; with Sacha flown by the computer (the ace; he comes back repaired `COMEBACK` s after his retreat);
  two players (Sacha's EDF-17 C flown by player 2); Sacha alone (the player flies the EDF-17 C: three hits); Sacha
  leading (the computer flies the pilot's ship). At the GAME OVER, 10 % of the score in credits (5 % of the two scores
  at two); one record per version (`ENDLESS_BEST` `bonus_swarm:<version>`); leaving gains nothing. The Guardians, the
  burnt ship and the ash of the gargoyles are made behind the loading bar, not at their first arrival. Tests:
  `tests/test_swarm_bonus.py`.

- **Faster without a visible change.** `fire_death.render` is vectorised with numpy (the same pixels, about twice as
  fast). The big glows of the explosion of the ship (`asteroids._add_glow`, radius ≥ 150) are cropped from a map of rings
  made once at the start (`asteroids.warm_glows`) and only their visible part is drawn: the same pixels, the slowest
  frame of the explosion about 65 ms → 25 ms in a software-rendered test. Tests: `tests/test_glow_rings.py`.

- **Infinite lives against the invaders.** With the LIVE code, a grid of invaders reaching the ship, or the boss saucer
  reaching the floor, left the mission stuck (a blast and a shake every frame). The ship now blows up once, becomes
  invulnerable for a moment and the grid (`InvaderFormation.push_back`) or the saucer (`BossSaucer.push_back`) goes back
  up. Tests: `tests/test_invaders.py`.

- **A full playthrough of the Adventure** (Normal mode, the computer at the controls of the player's ship). What it
  found, and what changed:
  - the map suggested la Riposte before Silent Sentinels III and IV: the Sentinels are now listed and suggested before
    it (they stay optional), and the text of Sentinelle IV holds after the victory too;
  - the map suggested optional missions (the paint series, a BONUS) once the game was finished: `next_mission` now
    only suggests the story and the hunts;
  - the scene of Bestiaire V spoke of « gargouilles vertes » round the saucer: it names the blue and khaki birds that
    really come (13 languages);
  - straight apostrophes in the Act IV text and in Peinture I;
  - the achievement banners: a new one replaced the one on screen. They now wait in one queue (`Game._show_ach`,
    `_tick_banners`), and one cut by a 1UP, a code or the pad comes back after it. Tests: `tests/test_banner_queue.py`;
  - « Échec  aucune perte » had two spaces: « Échec · aucune perte », and the same middle dot in the other results.
  Tests: `tests/test_story_coherence_1_7.py`.

- **Clean-up before 1.7.2.** The training mode written for the TEST - Sacha mission (removed when Défense de Phobos
  came) is gone with it, with its two texts; an unused import; the conftest fixture that kept TEST missions out of the
  tests; « … » for « ... » in a line of Sacha's radio. The manuals and `docs/STORY_MISSIONS.md` follow the game at 1.7.2.
