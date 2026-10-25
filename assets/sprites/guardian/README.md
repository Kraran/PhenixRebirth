# Avioïde Gardien — Sentinelle

Selected concept: Sentinelle, generated with ImageGen from the user's reference
and the game's existing gargoyle sprite. The Cuirassé and Séraphin concepts are
reserved for later; they are not loaded by this encounter.

`sentinelle.png` is a transparent 640 × 320 sheet, four 160 × 160 frames per row:
flight, then charge/fire. The source concept was cropped, aligned and resized
for the game. `laser.png` is the separate 32 × 144 fire-laser sprite. All frames
are loaded and cached once; drawing does not load or scale images.

## Test mission

Adventure map → Extras/Bonus group → **TEST - Avioïdes Gardiens**. Available
without an unlock in acts I–III, replayable before and after a victory.

- Two waves of three Sentinelles, one vulnerable body per enemy.
- Charge warning: 0.95 seconds. The shooter stops moving during the warning.
- Finite downward laser bolt: 144 pixels long, 260 pixels/second.
- Collision core: 10 pixels wide, narrower than the decorative flames.
- One laser in flight at most; 1.1 seconds of calm before the next charge.
- No homing or instantaneous beam. Destroying a charging enemy cancels its shot.
- Minimum three lives and safe screen edges. The owned ship and its speed are kept.
- Simulation: no credits, loot, item consumption, bestiary, story/VN progression,
  flawless achievement or permanent Veteran death.

Tuning constants are in `src/guardian.py`. No Python dependency was added.
