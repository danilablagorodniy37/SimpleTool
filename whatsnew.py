"""What changed in each version, in the three languages. After an update SimpleTool shows the notes of every
version newer than the one that ran before, once; Help → What's new shows them again.

CHANGELOG.md has the full list for GitHub; these are the few lines a user wants to know.
"""
from updates import parse_version

NOTES = {
    "0.9": {
        "en": [
            "Troubleshooting now sees crashes that never reach the Windows log: the crash reports Chromium browsers, "
            "Electron apps (Discord, VS Code, Teams), Steam, Epic, Riot and others keep themselves, and the live kernel "
            "dumps of drivers that hung without a blue screen.",
            "A new check names installed programs and drivers with documented problems: Nahimic, the inpoutx64 driver, "
            "Killer, cFosSpeed, an old RivaTuner next to Overwolf, unwanted “optimizers” and more. Temporary files say "
            "who litters, and program crashes list the saved dumps.",
        ],
        "ru": [
            "«Поиск проблем» видит сбои, которых нет в журнале Windows: отчёты, которые браузеры на Chromium, программы "
            "на Electron (Discord, VS Code, Teams), Steam, Epic, Riot и другие хранят сами, и живые дампы ядра от "
            "драйверов, зависших без синего экрана.",
            "Новая проверка называет установленные программы и драйверы с известными проблемами: Nahimic, драйвер "
            "inpoutx64, Killer, cFosSpeed, старый RivaTuner рядом с Overwolf, нежелательные «оптимизаторы» и другие. "
            "Временные файлы говорят, кто мусорит, а сбои программ показывают сохранённые дампы.",
        ],
        "uk": [
            "«Пошук проблем» бачить збої, яких немає в журналі Windows: звіти, які браузери на Chromium, програми на "
            "Electron (Discord, VS Code, Teams), Steam, Epic, Riot та інші зберігають самі, і живі дампи ядра від "
            "драйверів, що зависли без синього екрана.",
            "Нова перевірка називає встановлені програми й драйвери з відомими проблемами: Nahimic, драйвер inpoutx64, "
            "Killer, cFosSpeed, старий RivaTuner поруч з Overwolf, небажані «оптимізатори» та інші. Тимчасові файли "
            "кажуть, хто смітить, а збої програм показують збережені дампи.",
        ],
    },
    "0.8": {
        "en": [
            "Six new tweaks: the classic right-click menu of Windows 11 (SimpleTool restarts Explorer, so it shows at "
            "once), Copy to folder and Move to folder, no Microsoft Store in Open with, no “Learn about this picture” "
            "icon, automatic registry backups and detailed sign-in and shutdown messages.",
            "After Apply, SimpleTool says exactly what a change still needs: Explorer was restarted, sign out and back "
            "in, or restart the PC.",
        ],
        "ru": [
            "Шесть новых твиков: классическое контекстное меню Windows 11 (SimpleTool перезапускает Проводник, и оно "
            "появляется сразу), «Копировать в папку» и «Переместить в папку», без Microsoft Store в «Открыть с "
            "помощью», без значка «Подробнее об этом изображении», автоматические копии реестра и подробные сообщения "
            "при входе и выключении.",
            "После применения SimpleTool говорит точно, что ещё нужно изменению: Проводник перезапущен, выйти из "
            "системы и войти снова или перезагрузить компьютер.",
        ],
        "uk": [
            "Шість нових твіків: класичне контекстне меню Windows 11 (SimpleTool перезапускає Провідник, і воно "
            "з’являється одразу), «Копіювати до папки» та «Перемістити до папки», без Microsoft Store у «Відкрити за "
            "допомогою», без значка «Докладніше про це зображення», автоматичні копії реєстру та докладні повідомлення "
            "під час входу й вимкнення.",
            "Після застосування SimpleTool каже точно, що ще потрібно зміні: Провідник перезапущено, вийти із системи й "
            "увійти знову або перезавантажити комп’ютер.",
        ],
    },
    "0.7": {
        "en": [
            "New Troubleshooting page: almost fifty checks look for what makes the PC lag, freeze or crash — memory, "
            "the processor, drives, drivers, the graphics card, the event logs, conflicting programs and settings "
            "left behind by “optimizers”.",
            "Every finding explains what it means and how to fix it, with a button that opens the right Windows tool. "
            "The check only reads and changes nothing.",
        ],
        "ru": [
            "Новая страница «Поиск проблем»: почти пятьдесят проверок ищут, из-за чего компьютер тормозит, зависает "
            "или падает, — память, процессор, диски, драйверы, видеокарта, журналы событий, конфликтующие программы "
            "и настройки, оставленные «оптимизаторами».",
            "Каждая находка объясняет, что она значит и как это исправить, а кнопка открывает нужный инструмент "
            "Windows. Проверка только читает и ничего не меняет.",
        ],
        "uk": [
            "Нова сторінка «Пошук проблем»: майже п’ятдесят перевірок шукають, через що комп’ютер гальмує, зависає "
            "або падає, — пам’ять, процесор, диски, драйвери, відеокарта, журнали подій, конфліктні програми й "
            "налаштування, залишені «оптимізаторами».",
            "Кожна знахідка пояснює, що вона означає і як це виправити, а кнопка відкриває потрібний інструмент "
            "Windows. Перевірка лише читає й нічого не змінює.",
        ],
    },
    "0.6.4": {
        "en": [
            "Updating from inside SimpleTool now starts the new version cleanly: before, the previous version could "
            "linger in the background and its file stayed next to the new one.",
            "Restart as administrator starts SimpleTool cleanly in the same way.",
        ],
        "ru": [
            "Обновление из SimpleTool теперь запускает новую версию начисто: раньше прежняя версия могла остаться "
            "висеть в фоне, а её файл — лежать рядом с новым.",
            "«Перезапустить от имени администратора» так же запускает SimpleTool начисто.",
        ],
        "uk": [
            "Оновлення з SimpleTool тепер запускає нову версію начисто: раніше попередня версія могла залишатися у "
            "фоні, а її файл — лежати поруч із новим.",
            "«Перезапустити від імені адміністратора» так само запускає SimpleTool начисто.",
        ],
    },
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
