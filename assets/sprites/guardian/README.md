# Avioïde Gardien — Sentinelle

Selected concept: Sentinelle, generated with ImageGen from the user's reference
and the game's existing gargoyle sprite. The Cuirassé and Séraphin concepts are
reserved for later; they are not loaded by this encounter.

`sentinelle.png` is a transparent 640 × 320 sheet, four 160 × 160 frames per row:
flight, then charge/fire. The original concept was reworked with ImageGen for
complete wing tips, then each full silhouette was aligned on its eyes and
resized with at least six transparent pixels on every edge of its cell. The
intact horizontal pose is reused for the return phase of the wingbeat; no
neighbouring-cell strips or wing tips are trimmed. `laser.png` is the separate
32 × 144 fire-laser sprite. All frames
are loaded and cached once; drawing does not load or scale images.

## Test mission

Adventure map → Extras/Bonus group → **TEST - Avioïdes Gardiens**. Available
without an unlock in acts I–III, replayable before and after a victory.

- One encounter: five Sentinelles, five ordinary blue birds and five green birds.
  The counter includes all 15 enemies; there is no second wave.
- Charge warning: 0.95 seconds. The shooter stops moving during the warning.
- The shooter also stays fixed on both axes while its own growing laser is
  attached to its mouth. Movement and dives resume as soon as the tail leaves
  the emission point (144 / 780 seconds, about 0.185 s), or the bolt is removed.
  Other Guardians are not frozen, and the shooter need not wait for the laser
  to leave the screen.
- Finite downward laser bolt: 144 pixels long, 780 pixels/second.
- Collision core: 10 pixels wide, narrower than the decorative flames.
- One laser in flight per Guardian (up to five simultaneously). Charge starts are
  spaced by at least 0.32 seconds; emissions by at least 0.18 seconds, including
  at a low frame rate. Each enemy has its own 1.1-second minimum cooldown.
- No homing or instantaneous beam. Destroying a charging enemy cancels its shot.
- Patrols pursue the player's horizontal position. A dive locks the player's
  current position, prepares for 0.55 seconds without a target marker, trajectory
  line or explanatory message, then attacks at 340 pixels/second. Once fully
  off-screen, it wraps to above the top edge like the gargoyles and descends to
  its patrol position at 300 px/s. It never climbs back through the playfield
  from below, and cannot shoot during a dive or its return.
- Minimum three lives and safe screen edges. The owned ship and its speed are kept.
- Simulation: no credits, loot, item consumption, bestiary, story/VN progression,
  flawless achievement or permanent Veteran death.

Tuning constants are in `src/guardian.py`. No Python dependency was added.

## Friendly fire and combustion

Guardian lasers pierce birds of both colours, including divers, without being
consumed. Regular bird bullets do not burn other enemies. Burning removes the
bird from combat immediately and awards no player score, combo, loot or kill
credit. A dead/dying bird cannot burn twice. Guardian bodies are immune to their
own lasers. The encounter waits for ordinary death, burning/ash effects and all
remaining projectiles before ending.

The 1.35-second effect has 24 transparent frames per colour: the original bird
silhouette heats orange, chars and breaks into rising grey ash with fading
embers. Frames derive from the existing blue/green sprites and are cached once
per colour at encounter creation; drawing only blits. No new image files or
dependencies are required. Birds keep their normal wing animation, regular shots
and dives; their return wraps invisibly above the screen.

## Lasers against the player's ship

In this mission only, a Guardian laser destroys one life on contact, bypassing
the Shield dome, Phenix mode, morph transitions, temporary invulnerability and
infinite-life cheats. It keeps travelling after contact. Ordinary enemy shots,
divers and every other mission keep their usual damage rules.

Both hulls have distinct normal/active destruction silhouettes: the normal
Shield, Shield with dome, normal Phoenix hull, and transformed Phenix wings.
The 32 cached frames heat the original form, engulf it in flames, carbonise it
and disperse it into embers and ash over 1.4 seconds. Both forms of the selected
hull/tint are prepared on mission entry; impact and drawing only use the cache.

The destroyed ship cannot move, shoot, collide or clear the mission during this
animation. A remaining life respawns the normal hull at the starting position.
Respawn protection still works for ordinary attacks; Guardian lasers bypass it.
The final life returns to the adventure map after the full animation. Training
save/progression rules are unchanged.
