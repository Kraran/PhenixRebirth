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

- Two waves of three Sentinelles, one vulnerable body per enemy.
- Charge warning: 0.95 seconds. The shooter stops moving during the warning.
- Finite downward laser bolt: 144 pixels long, 780 pixels/second.
- Collision core: 10 pixels wide, narrower than the decorative flames.
- One laser in flight per Guardian (up to three in a wave). Charge starts are
  spaced by at least 0.32 seconds; emissions by at least 0.18 seconds, including
  at a low frame rate. Each enemy has its own 1.1-second minimum cooldown.
- No homing or instantaneous beam. Destroying a charging enemy cancels its shot.
- Patrols pursue the player's horizontal position. A dive locks the player's
  current position, shows its line and target for 0.55 seconds, then attacks at
  340 pixels/second. The Guardian flies back to its patrol position at 300 px/s
  without teleporting. It cannot shoot during a dive or its return.
- Minimum three lives and safe screen edges. The owned ship and its speed are kept.
- Simulation: no credits, loot, item consumption, bestiary, story/VN progression,
  flawless achievement or permanent Veteran death.

Tuning constants are in `src/guardian.py`. No Python dependency was added.
