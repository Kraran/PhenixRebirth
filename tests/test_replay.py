"""
Gameplay regression test: replay scripted games and compare, every 10 frames,
a fingerprint of the full game state with the saved one (golden_replay.json).

If this test fails after a refactoring, the gameplay changed (even slightly).
If the change is wanted (new feature, balance change), regenerate the file:

    python tests/replay.py tests/golden_replay.json

The saved fingerprints were produced on Linux (what GitHub CI uses). Other
systems may differ in the last bits of math functions, so the test is skipped
there unless you set PHENIX_REPLAY=1.
"""
import json
import os
import sys

import pytest

import replay

GOLDEN = os.path.join(os.path.dirname(__file__), "golden_replay.json")

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux") and not os.environ.get("PHENIX_REPLAY"),
    reason="golden fingerprints are made on Linux; set PHENIX_REPLAY=1 to force",
)

with open(GOLDEN, encoding="utf-8") as fh:
    _GOLDEN = json.load(fh)

# What was drawn (hash of the pixels, every 10 frames). Optional: set PHENIX_PIXELS=1.
# The hashes were made on the author's Linux machine. Image scaling / rotation can give
# slightly different pixels on another CPU or library build (GitHub's runners differ on a
# few frames of explosions or the boss, while the game state is identical), so this check
# is not part of the default run: it is used locally when moving drawing code around.
CHECK_PIXELS = bool(os.environ.get("PHENIX_PIXELS"))
GOLDEN_PIXELS = os.path.join(os.path.dirname(__file__), "golden_pixels.json")
_GOLDEN_PIXELS = {}
if CHECK_PIXELS:
    with open(GOLDEN_PIXELS, encoding="utf-8") as fh:
        _GOLDEN_PIXELS = json.load(fh)


@pytest.mark.parametrize("name", sorted(replay.SCENARIOS))
def test_replay_matches_golden(name):
    pixels = [] if CHECK_PIXELS else None
    got = replay.run_scenario(name, pixels_out=pixels, **replay.SCENARIOS[name])
    want = _GOLDEN[name]
    assert len(got) == len(want), f"{name}: {len(got)} samples, expected {len(want)}"
    for i, (a, b) in enumerate(zip(got, want)):
        assert a == b, (
            f"{name}: gameplay differs from frame {i * replay.SAMPLE_EVERY} "
            f"(got {a}, expected {b})"
        )
    if not CHECK_PIXELS:
        return
    want_px = _GOLDEN_PIXELS[name]
    assert len(pixels) == len(want_px), f"{name}: {len(pixels)} images, expected {len(want_px)}"
    for i, (a, b) in enumerate(zip(pixels, want_px)):
        assert a == b, (
            f"{name}: the picture differs from frame {i * replay.SAMPLE_EVERY} "
            f"(got {a}, expected {b})"
        )
