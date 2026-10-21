"""What changed in each version, in the three languages. After an update SimpleTool shows the notes of every
version newer than the one that ran before, once; Help → What's new shows them again.

CHANGELOG.md has the full list for GitHub; these are the few lines a user wants to know.
"""
from updates import parse_version

NOTES = {
    "0.6.3": {
        "en": [
            "Updates in one click: when a new version is out, SimpleTool downloads it, checks it against the "
            "published checksum and restarts into it. Settings, backups and snapshots stay where they are.",
            "Once a day at start SimpleTool quietly checks for a new version and marks Help with a dot when there is "
            "one. Help → Check for updates daily turns this off.",
            "The terms of use now describe the updates, which is why SimpleTool asked you to accept them again.",
        ],
        "ru": [
            "Обновление в один клик: когда выходит новая версия, SimpleTool сам скачивает её, сверяет с "
            "опубликованной контрольной суммой и перезапускается. Настройки, резервные копии и снимки остаются на "
            "месте.",
            "Раз в день при запуске SimpleTool тихо проверяет, вышла ли новая версия, и отмечает «Справку» точкой. "
            "Выключить: «Справка» → «Проверять обновления раз в день».",
            "Пользовательское соглашение теперь описывает обновления, поэтому SimpleTool попросил принять его заново.",
        ],
        "uk": [
            "Оновлення в один клік: коли виходить нова версія, SimpleTool сам завантажує її, звіряє з опублікованою "
            "контрольною сумою і перезапускається. Налаштування, резервні копії та знімки залишаються на місці.",
            "Раз на день під час запуску SimpleTool тихо перевіряє, чи вийшла нова версія, і позначає «Довідку» "
            "крапкою. Вимкнути: «Довідка» → «Перевіряти оновлення щодня».",
            "Угода користувача тепер описує оновлення, тому SimpleTool попросив прийняти її знову.",
        ],
    },
    "0.6.2": {
        "en": [
            "The Help button at the top of the window (before, an ⓘ icon without a name) has Check for updates, "
            "Report a problem, What's new and the terms of use.",
            "After an update SimpleTool shows what is new, like now. Help → What's new opens it again.",
            "Report a problem adds the PC's specifications to the letter (processor, graphics card, memory, "
            "Windows version) and shows them before you send it.",
        ],
        "ru": [
            "Кнопка «Справка» вверху окна (раньше — значок ⓘ без подписи): в ней «Проверить обновления», "
            "«Сообщить о проблеме», «Что нового» и пользовательское соглашение.",
            "После обновления SimpleTool показывает, что нового, — как сейчас. «Справка» → «Что нового» откроет это "
            "окно снова.",
            "«Сообщить о проблеме» добавляет в письмо характеристики компьютера (процессор, видеокарту, память, "
            "версию Windows) и показывает их до отправки.",
        ],
        "uk": [
            "Кнопка «Довідка» вгорі вікна (раніше — значок ⓘ без підпису): у ній «Перевірити оновлення», "
            "«Повідомити про проблему», «Що нового» та угода користувача.",
            "Після оновлення SimpleTool показує, що нового, — як зараз. «Довідка» → «Що нового» відкриє це вікно "
            "знову.",
            "«Повідомити про проблему» додає до листа характеристики комп’ютера (процесор, відеокарту, пам’ять, "
            "версію Windows) і показує їх до надсилання.",
        ],
    },
}


def since(seen, current):
    """[(version, notes by language)] newer than seen and not newer than current, newest first. With seen
    unknown (an update from a version that did not record itself) only the current version's notes."""
    now = parse_version(current)
    before = parse_version(seen) if seen else None
    found = []
    for version, notes in NOTES.items():
        number = parse_version(version)
        if number is None or number > now:
            continue
        if (before is None and number == now) or (before is not None and number > before):
            found.append((number, version, notes))
    return [(version, notes) for _, version, notes in sorted(found, reverse=True)]
