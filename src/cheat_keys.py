"""The character a key press stands for when a secret code is typed (menus of the game, mission map of the Adventure).

On a French (AZERTY) keyboard the digit row gives "&", "é", '"' ... without Shift: the digits of the codes (LV02, 2222,
3333, NIX2) must come from the physical key, not from the character. Letters come from the character, as before."""

_DIGIT_ROW = {30 + i: str((i + 1) % 10) for i in range(10)}          # SDL scancodes of 1 2 3 ... 9 0
_KEYPAD = {89 + i: str(i + 1) for i in range(9)}
_KEYPAD[98] = "0"


def cheat_char(event):
    """The letter or digit typed by a key event ("" when it is none)."""
    ch = getattr(event, "unicode", "") or ""
    if len(ch) == 1 and ch.isascii() and ch.isalnum():
        return ch
    scan = int(getattr(event, "scancode", 0) or 0)
    digit = _DIGIT_ROW.get(scan) or _KEYPAD.get(scan)
    if digit:
        return digit
    return ch if len(ch) == 1 and ch.isalnum() else ""
