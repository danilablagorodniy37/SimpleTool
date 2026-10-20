"""UI texts in English, Russian and Ukrainian (the strings themselves are in locales/)."""
import ctypes

from locales import en, ru, uk

LANGUAGES = [("en", "English"), ("ru", "Русский"), ("uk", "Українська")]
TEXTS = {"en": en.TEXTS, "ru": ru.TEXTS, "uk": uk.TEXTS}


def detect_language():
    """The Windows display language: Russian, Ukrainian, otherwise English."""
    try:
        primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
    except (AttributeError, OSError):
        return "en"
    return {0x19: "ru", 0x22: "uk"}.get(primary, "en")


def menu_label(key, *args):
    """A registry label in the language chosen when applying."""
    return lambda lang: TEXTS[lang]["menu"][key].format(*args)
