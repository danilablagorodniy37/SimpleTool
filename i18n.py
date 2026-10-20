"""Тексты интерфейса на английском, русском и украинском (сами строки — в locales/)."""
import ctypes

from locales import en, ru, uk

LANGUAGES = [("en", "English"), ("ru", "Русский"), ("uk", "Українська")]
TEXTS = {"en": en.TEXTS, "ru": ru.TEXTS, "uk": uk.TEXTS}


def detect_language():
    """Язык интерфейса Windows: русский, украинский, иначе английский."""
    try:
        primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
    except (AttributeError, OSError):
        return "en"
    return {0x19: "ru", 0x22: "uk"}.get(primary, "en")


def menu_label(key, *args):
    """Подпись для реестра на выбранном при применении языке."""
    return lambda lang: TEXTS[lang]["menu"][key].format(*args)
