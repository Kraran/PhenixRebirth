# Short frame hitches after PR #163

Isolated headless measurements on Windows, Python 3.13 / Pygame 2.6.1.
These are CPU operation timings, not measurements of the player's GPU frame rate.

| Operation | Cold, before | Prepared |
| --- | ---: | ---: |
| First animated asteroid creation (PNG strip decoding included) | 52.874 ms | 0.824 ms |
| First nebula creation (10 assets) | 4.302–10.139 ms | 0.633–1.748 ms |
| Text-cache boundary miss | 0.518 ms | 0.009 ms |

The scenery images are decoded once during non-soft Game initialization, after display
and settings initialization and before combat. Preparation took 221.831 ms in this
measurement. Images occupy memory earlier; raw nebula images are removed when their
scaled cached versions are created. Planet and comet caches retain their existing
lifetime. Missing optional images keep their existing fallback behavior.

Preparation consumes no random numbers. Nebula random scaling remains deferred to
its original first-spawn moment. Comparing the old and new code with identical
seeds preserved random state, nebula geometry and all RGBA pixels: 10 nebula
images and 144 animated asteroid frame samples. No further image loads occurred
during those prepared actor creations.

The text cache retains FIFO behavior, but replaces at most one oldest entry on a
miss once full, instead of freeing 600 entries together. Its maximum size is 1200.
It retains more entries on average, without raising the previous peak entry count.

Regression tests cover random-state preservation, identical nebula pixels,
idempotent preparation, no subsequent scenery decoding, and single-entry FIFO
eviction. These changes address measured sources of stalls; they do not establish
that every intermittent hitch on the player's hardware has been eliminated.
