"""Text rendering cache (moved out of game.py)."""
from collections import OrderedDict

MAX_ENTRIES = 1200


class TextCache:
    """Cache font.render results — rebuild only when (font, text, color) changes."""
    __slots__ = ("_data",)

    def __init__(self):
        self._data = OrderedDict()

    def get(self, font, text, color):
        key = (font, text, color)          # the font itself, not its id: a freed font's id can be reused by another
        surf = self._data.get(key)
        if surf is None:
            if len(self._data) >= MAX_ENTRIES:
                # One eviction per miss: never release hundreds of surfaces in
                # the same frame. Hits retain the existing FIFO semantics.
                self._data.popitem(last=False)
            surf = font.render(str(text), True, color)
            self._data[key] = surf
        return surf

    def clear(self):
        self._data.clear()
