"""What changed in each version, in the three languages. After an update SimpleTool shows the notes of every
version newer than the one that ran before, once; Help → What's new shows them again.

CHANGELOG.md has the full list for GitHub; these are the few lines a user wants to know.
"""
from updates import parse_version

NOTES = {
    "0.12": {
        "en": [
            "Troubleshooting checks protection and recovery: threats Microsoft Defender did not remove and risky "
            "exclusions, browser settings forced by adware, added root certificates, risky accounts, the firewall, "
            "SMB1 and Remote Desktop, remote control programs scammers ask for, BitLocker and its recovery key, the "
            "recovery environment, the clock and the new Secure Boot certificates.",
        ],
        "ru": [
            "«Поиск проблем» проверяет защиту и восстановление: угрозы, которые Microsoft Defender не удалил, и "
            "опасные исключения, навязанные рекламными программами настройки браузеров, добавленные корневые "
            "сертификаты, опасные учётные записи, брандмауэр, SMB1 и удалённый рабочий стол, программы удалённого "
            "управления, о которых просят мошенники, BitLocker и ключ восстановления, среду восстановления, часы и "
            "новые сертификаты безопасной загрузки.",
        ],
        "uk": [
            "«Пошук проблем» перевіряє захист і відновлення: загрози, які Microsoft Defender не видалив, і небезпечні "
            "виключення, нав’язані рекламними програмами налаштування браузерів, додані кореневі сертифікати, "
            "небезпечні облікові записи, брандмауер, SMB1 і віддалений робочий стіл, програми віддаленого керування, "
            "про які просять шахраї, BitLocker і ключ відновлення, середовище відновлення, годинник і нові "
            "сертифікати безпечного завантаження.",
        ],
    },
    "0.11": {
        "en": [
            "Troubleshooting finds what other tweaking tools broke: programs blocked from starting (such as Windows "
            "Security), protection turned off by policies, blocked updates, removed parts of Windows such as the "
            "Store or WebView2, sleep taken away and the network settings Xbox games need.",
            "Drives report their own health, as CrystalDiskInfo reads it, and an NVMe drive in a slower slot is "
            "noticed. New checks show what slows the start of Windows down, the startup programs that cost the "
            "most, interrupts that make sound crackle and file system errors Windows found.",
        ],
        "ru": [
            "«Поиск проблем» находит, что сломали другие твикеры: программы, которым запрещён запуск (например, "
            "«Безопасность Windows»), защиту, отключённую политиками, заблокированные обновления, удалённые части "
            "Windows вроде Store или WebView2, отключённый сон и сетевые настройки, нужные играм Xbox.",
            "Диски сообщают своё состояние напрямую, как в CrystalDiskInfo, и замечается NVMe-диск в более "
            "медленном слоте. Новые проверки показывают, что замедляет запуск Windows, самые «дорогие» программы "
            "автозагрузки, прерывания, из-за которых трещит звук, и ошибки файловой системы.",
        ],
        "uk": [
            "«Пошук проблем» знаходить, що зламали інші твікери: програми, яким заборонено запуск (наприклад, "
            "«Безпека Windows»), захист, вимкнений політиками, заблоковані оновлення, видалені частини Windows на "
            "кшталт Store або WebView2, вимкнений сон і мережеві налаштування, потрібні іграм Xbox.",
            "Диски повідомляють свій стан напряму, як у CrystalDiskInfo, і помічається NVMe-диск у повільнішому "
            "слоті. Нові перевірки показують, що сповільнює запуск Windows, найбільш «дорогі» програми "
            "автозавантаження, переривання, через які тріщить звук, і помилки файлової системи.",
        ],
    },
    "0.10.3": {
        "en": [
            "Smooth circles: the ring on the tweaks tile, the scan animation and the activity indicator are drawn "
            "with antialiasing now, instead of the jagged circles Tk draws by itself.",
        ],
        "ru": [
            "Гладкие круги: кольцо на плитке твиков, анимация сканирования и индикатор активности теперь рисуются "
            "со сглаживанием вместо зубчатых кругов, которые Tk рисует сам.",
        ],
        "uk": [
            "Гладкі кола: кільце на плитці твіків, анімація сканування та індикатор активності тепер малюються зі "
            "згладжуванням замість зубчастих кіл, які Tk малює сам.",
        ],
    },
    "0.10.2": {
        "en": [
            "Colored tiles: the counters at the top of System overview and Troubleshooting are tinted in their own "
            "color, and the tweaks tile shows the share of applied tweaks as a ring in the brand gradient.",
        ],
        "ru": [
            "Цветные плитки: счётчики вверху «Обзора системы» и «Поиска проблем» подкрашены своим цветом, а плитка "
            "твиков показывает долю применённых кольцом в фирменном градиенте.",
        ],
        "uk": [
            "Кольорові плитки: лічильники вгорі «Огляду системи» та «Пошуку проблем» підфарбовані своїм кольором, а "
            "плитка твіків показує частку застосованих кільцем у фірмовому градієнті.",
        ],
    },
    "0.10.1": {
        "en": [
            "Crisper text: on Windows 11 the interface uses Segoe UI Variable Text, the system font made for small "
            "sizes; descriptions, notes and the sidebar are one step larger, and secondary text and card borders "
            "have more contrast in every theme.",
            "System overview: the card of a running service carries a blue bar along its left edge, like applied "
            "tweaks carry a teal one; a service that could not be checked carries an orange bar.",
        ],
        "ru": [
            "Чётче текст: в Windows 11 интерфейс использует Segoe UI Variable Text, системный шрифт для мелких "
            "размеров; описания, заметки и боковая панель стали на шаг крупнее, а второстепенный текст и границы "
            "карточек контрастнее во всех темах.",
            "Обзор системы: у карточки работающей службы слева синяя полоса, как бирюзовая у применённых твиков; у "
            "службы, которую не удалось проверить, — оранжевая.",
        ],
        "uk": [
            "Чіткіший текст: у Windows 11 інтерфейс використовує Segoe UI Variable Text, системний шрифт для дрібних "
            "розмірів; описи, нотатки й бічна панель стали на крок більшими, а другорядний текст і межі карток "
            "контрастніші в усіх темах.",
            "Огляд системи: у картки працюючої служби ліворуч синя смуга, як бірюзова в застосованих твіків; у "
            "служби, яку не вдалося перевірити, — помаранчева.",
        ],
    },
    "0.10": {
        "en": [
            "Pages read at a glance: every tweak page starts with “Applied: N of M” and a bar that fills up, applied "
            "tweaks get a teal bar along the left edge of their card, partly applied ones an orange bar, and "
            "troubleshooting findings a bar in the color of their severity.",
            "Turn off settings sync now also sets the Windows policy, so it works for Windows 11's “Remember my "
            "preferences” too; applied with an earlier version it shows Partly: select it and press Apply. Turn off "
            "Microsoft experiments warns that it also turns off Known Issue Rollback.",
            "Drive errors of a memory stick or phone unplugged since are a note, not a problem.",
        ],
        "ru": [
            "Страницы читаются с первого взгляда: каждая страница твиков начинается с «Применено: N из M» и полоски, "
            "которая заполняется; у применённых твиков слева от карточки бирюзовая полоса, у частично применённых — "
            "оранжевая, а у находок «Поиска проблем» — полоса цвета их серьёзности.",
            "«Отключить синхронизацию настроек» теперь задаёт и политику Windows, поэтому работает и для «Запоминать "
            "мои настройки» в Windows 11; применённый прежней версией твик показывает «Частично» — выберите его и "
            "нажмите «Применить». «Отключить эксперименты Microsoft» предупреждает, что отключает и Known Issue "
            "Rollback.",
            "Ошибки диска от флешки или телефона, которые с тех пор отключили, — заметка, а не проблема.",
        ],
        "uk": [
            "Сторінки читаються з першого погляду: кожна сторінка твіків починається із «Застосовано: N з M» і "
            "смужки, що заповнюється; у застосованих твіків ліворуч від картки бірюзова смуга, у частково "
            "застосованих — помаранчева, а в знахідок «Пошуку проблем» — смуга кольору їхньої серйозності.",
            "«Вимкнути синхронізацію налаштувань» тепер задає й політику Windows, тому працює і для «Запам’ятати мої "
            "параметри» у Windows 11; застосований попередньою версією твік показує «Частково» — виберіть його й "
            "натисніть «Застосувати». «Вимкнути експерименти Microsoft» попереджає, що вимикає й Known Issue "
            "Rollback.",
            "Помилки диска від флешки або телефона, які відтоді відключили, — нотатка, а не проблема.",
        ],
    },
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
