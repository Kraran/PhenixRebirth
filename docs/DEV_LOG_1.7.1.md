# Development log — Phenix Rebirth 1.7.1

The detailed notes kept while FINAL BONUS - Space War, the Guardians option of the Adventure style, the tighter gate after
Bestiary I, the tighter landing tanks and the intros of the asteroid belt were made. The short version is in the
[ROADMAP](../ROADMAP.md) ("Done in 1.7.1"). Some game texts are quoted in French, the language they were first written in.

- **The boss saucer.** Destroying both dishes (`saucer_deco_dish`) no longer stops the descent: it halves `descend_speed`
  (`src/boss.py` `_apply_pair_effects`). Tests: `tests/test_boss_dish_descent.py`.

- **Options > GAMEPLAY, Guardians** (`src/arcade_style.py`). In the Adventure style of a solo arcade game, a Guardians
  option (off by default, saved as `gp_guardians`) brings the Guardians of BONUS FINAL - Gardiens with every level, the
  boss levels too, in the same numbers (`story_state.endless_guardians`: one more each level up to five, then from level 6
  one Alpha Guardian more every five levels). `Game._setup_guardian_squad` makes them, as for the mission; their flames
  and the ash of the gargoyles are prepared behind the loading bar at the start of the game. The row is greyed while the
  classic style is chosen. The game always starts in Classic. Tests: `tests/test_arcade_guardians.py`.

- **FINAL BONUS - Space War** (`src/spacewar.py`). Secret until the game is finished, then at the end of Act IV (END
  BONUS), like the other FINAL BONUS missions. The gas giant is chosen in a menu like Lunar Lander (Jupiter, Saturn,
  Uranus or Neptune, each with its gravity). Level after level: L1 one blue bird, L2 two blue, L3 two blue and one green,
  then two blue and two green, and a saucer every multiple of 5. 20 torpedoes, renewed at each level; one life; the
  workshop antimatter missile, if it is unlocked, is one per run. The run ends when the ship is lost, or when the player
  has no missile left while enemies remain (after the last shots in the air have resolved): its points pay in credits,
  without a penalty. Nothing is won if it is left from the pause. One record per planet (`ENDLESS_BEST`
  `bonus_spacewar:<planet>`). Tests: `tests/test_bonus_spacewar.py`.

- **The tighter gate after Bestiary I.** Ceinture d'astéroïdes I and EDF - Sentinelles silencieuses I : Jupiter are no
  longer open from the start: they wait for Bestiaire I - Première sortie (`story_state.CH1_SIDES`). A save that already
  won that sortie, or already flew or won either mission, keeps them open (`migrate_state`). Tests:
  `tests/test_unlock_after_bestiary1.py`.

- **Tighter landing tanks.** The starting fuel of the five landings, and of FINAL BONUS - Lunar Lander, is lower: Déimos
  90, the asteroid 80, Europe and Titan 70, Triton 60, and 90 at the start of the bonus (`lander.FUEL_START`; the +50 or
  +25 of a landing of the bonus is unchanged). The descriptions on the map and in the briefing scenes follow, in French
  and in English. Tests: `tests/test_lander_fuel.py`.

- **The intros of the asteroid belt.** Ceinture d'astéroïdes I, II and III each have their picture and a looping clip
  (`assets/story/ceinture_asteroides_1` to `_3`, 752×416, no sound), like the other scenes of the Adventure.
