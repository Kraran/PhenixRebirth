"""The language of the system, for the very first start of the game (no settings.json yet, or one without a language):
the game starts in it when it is one of its languages (i18n.LANGS), else in English.

    sys_lang.detect()   "fr", "de"... (a code of i18n.LANG_CODES), "en" when it cannot be found or is not one of them

Windows: the language of the interface of the user (GetUserDefaultUILanguage), then the language of the locale. The
others (and Windows if that failed): the variables LANGUAGE, LC_ALL, LC_MESSAGES, LANG, then the locale of Python.
"""
import locale
import os
import sys

from i18n import LANG_CODES

FALLBACK = "en"
# a few codes of the systems that are not those of the game
ALIASES = {"nb": "no", "nn": "no", "se": "sv", "dk": "da"}


def code_of(name):
    """The game's code for a language name of the system ("fr_FR.UTF-8", "de-DE", "French_France", "nb_NO"), or None."""
    if not name or not isinstance(name, str):
        return None
    head = name.strip().split(".")[0].split("@")[0].replace("-", "_").split("_")[0].lower()
    if head in ("c", "posix", ""):
        return None
    head = ALIASES.get(head, head)
    if head in LANG_CODES:
        return head
    # a Windows locale name ("French_France", "Norwegian Bokmål_Norway"...): its language in English
    english = {"french": "fr", "english": "en", "spanish": "es", "german": "de", "italian": "it", "portuguese": "pt",
               "dutch": "nl", "polish": "pl", "turkish": "tr", "swedish": "sv", "norwegian": "no", "danish": "da",
               "russian": "ru"}
    word = name.strip().split("_")[0].split(" ")[0].lower()
    return english.get(word)


def _windows():
    """The language of the Windows interface (then of the user's locale), as a name like "fr_FR", or None."""
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        for get in (kernel.GetUserDefaultUILanguage, kernel.GetUserDefaultLCID):
            name = locale.windows_locale.get(int(get()))
            if code_of(name):
                return name
    except Exception:
        pass
    return None


def _environment():
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            for part in value.split(":"):            # (LANGUAGE can list several, by preference)
                if code_of(part):
                    return part
    return None


def _python_locale():
    try:
        name = locale.getlocale()[0]
        if code_of(name):
            return name
    except Exception:
        pass
    try:
        name = locale.setlocale(locale.LC_CTYPE, None)
        if code_of(name):
            return name
    except Exception:
        pass
    return None


def detect():
    """The code of the system's language among the game's, or FALLBACK (English)."""
    try:
        finders = (_windows, _environment, _python_locale) if sys.platform == "win32" else (_environment, _python_locale)
        for find in finders:
            code = code_of(find())
            if code:
                return code
    except Exception:
        pass
    return FALLBACK
