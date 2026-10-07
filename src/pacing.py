"""
Frame-rate limiter.

pygame's Clock.tick(n) waits a whole number of milliseconds: tick(144) waits
1000 // 144 = 6 ms, i.e. about 166 images/s, tick(120) gives 125, tick(60) gives
62.5. This limiter waits for the exact interval (sleep for most of it, then a
short precise wait), so "144 Hz" really is 144 images per second.
It is a no-op whenever a frame already took longer than the interval (heavy
frame, or the presentation is blocked by VSync).
"""
import time

SPIN_SEC = 0.0008   # last stretch waited by polling (time.sleep is too coarse for it)


class FramePacer:
    def __init__(self, clock=time.perf_counter, sleep=time.sleep):
        self._clock = clock
        self._sleep = sleep
        self._last = None

    def reset(self):
        self._last = None

    def wait(self, cap):
        """Wait until one frame interval has passed since the previous call.

        Returns the real time since the previous call, in seconds, or None on
        the very first call (the caller then falls back to its own clock)."""
        cap = max(1, int(cap))
        now = self._clock()
        last = self._last
        if last is None:
            self._last = now
            return None
        target = last + 1.0 / cap
        remaining = target - now
        if remaining > SPIN_SEC:
            self._sleep(remaining - SPIN_SEC)
        while self._clock() < target:
            pass
        now = self._clock()
        self._last = now
        return now - last
