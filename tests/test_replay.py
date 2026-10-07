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


@pytest.mark.parametrize("name", sorted(replay.SCENARIOS))
def test_replay_matches_golden(name):
    got = replay.run_scenario(name, **replay.SCENARIOS[name])
    want = _GOLDEN[name]
    assert len(got) == len(want), f"{name}: {len(got)} samples, expected {len(want)}"
    for i, (a, b) in enumerate(zip(got, want)):
        assert a == b, (
            f"{name}: gameplay differs from frame {i * replay.SAMPLE_EVERY} "
            f"(got {a}, expected {b})"
        )
