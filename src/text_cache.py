"""Text rendering cache (moved out of game.py)."""


class TextCache:
    """Cache font.render results — rebuild only when (font, text, color) changes."""
    __slots__ = ("_data",)

    def __init__(self):
        self._data = {}

    def get(self, font, text, color):
        key = (id(font), text, color)
        surf = self._data.get(key)
        if surf is None:
            if len(self._data) > 1200:
                # Drop oldest half — a full clear hitch-spikes menus/credits
                for k in list(self._data)[:600]:
                    self._data.pop(k, None)
            surf = font.render(str(text), True, color)
            self._data[key] = surf
        return surf

    def clear(self):
        self._data.clear()
