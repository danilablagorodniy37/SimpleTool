"""The terms of use in English, Russian and Ukrainian. SimpleTool asks to accept them on the first run.

Change VERSION whenever the text changes: SimpleTool then shows the terms again and asks to accept the new version.
TERMS.md in the repository root is generated from this file: python tools/terms_md.py
"""

VERSION = "2026-10-20"

TERMS = {
    "en": {
        "title": "Terms of use",
        "updated": "Last updated: 20 October 2026",
        "intro": "Please read these terms before you use SimpleTool. By pressing “I accept” you agree to them. If "
                 "you do not agree, press “Exit” and do not use SimpleTool.",
        "sections": [
            ("What SimpleTool is",
             "SimpleTool is a free program for Windows 10 and 11 made by blagotech (blagotech.uk). It changes Windows "
             "settings: registry values, services, scheduled tasks and the context menu, and it can limit how much "
             "memory other programs use. This is a beta version: it is still being tested and may contain errors."),
            ("You use it at your own risk",
             "SimpleTool is provided “as is” and “as available”, without warranty of any kind, express or implied, "
             "including any warranty that it is fit for a particular purpose, works without errors or suits your "
             "computer. You choose which changes to make, and you are responsible for that choice and its "
             "consequences."),
            ("Before you change anything",
             "Back up your important files and create a Windows restore point: the System snapshots page has a "
             "button for it. Read the description of every tweak before you apply it. Use SimpleTool only on a "
             "computer that you own or are allowed to change. On a work or school computer, ask your administrator "
             "first."),
            ("What can go wrong",
             "Changing system settings can make Windows, drivers or other programs behave differently or stop "
             "working, turn off features you rely on, or leave you needing to restore settings or reinstall Windows. "
             "Revert and snapshots try to put the original values back but cannot guarantee it in every case, for "
             "example after a Windows update or when another program has changed the same settings. A program whose "
             "memory is limited can slow down."),
            ("Liability",
             "To the fullest extent permitted by law, blagotech is not liable for any loss or damage that arises from "
             "using SimpleTool or being unable to use it, including loss of data, damage to Windows or other "
             "software, time your computer cannot be used, lost income and the cost of repair, data recovery or "
             "reinstalling Windows."),
            ("Your statutory rights",
             "Nothing in these terms excludes or limits liability for death or personal injury caused by negligence, "
             "for fraud, or any other liability that the law does not allow to be excluded or limited. If you use "
             "SimpleTool as a consumer, these terms do not affect your statutory rights."),
            ("Your data",
             "SimpleTool does not collect personal data and sends nothing over the internet. Its settings, backups "
             "and snapshots stay on your computer in %LOCALAPPDATA%\\SimpleTool; delete that folder to remove them."),
            ("Licence and trademarks",
             "The source code of SimpleTool is released under the MIT License, and nothing in these terms limits the "
             "rights that licence gives you. The blagotech name, the b!t mark and the logo are not covered by the "
             "MIT License."),
            ("Changes to these terms",
             "Later versions of SimpleTool may come with new terms. If the terms change, SimpleTool shows them again "
             "and asks you to accept them."),
            ("Law",
             "These terms are governed by the law of England and Wales. If you are a consumer living in Scotland or "
             "Northern Ireland, you may also bring proceedings in your local courts. If a translation of these terms "
             "differs from the English version, the English version applies."),
            ("Contact",
             "Questions about SimpleTool or these terms: service@blagotech.uk."),
        ],
    },
    "ru": {
        "title": "Пользовательское соглашение",
        "updated": "Последнее обновление: 20 октября 2026 г.",
        "intro": "Прочитайте это соглашение, прежде чем пользоваться SimpleTool. Нажимая «Принимаю», вы соглашаетесь "
                 "с его условиями. Если вы не согласны, нажмите «Выход» и не используйте SimpleTool.",
        "sections": [
            ("Что такое SimpleTool",
             "SimpleTool — бесплатная программа для Windows 10 и 11 от blagotech (blagotech.uk). Она меняет "
             "настройки Windows: параметры реестра, службы, задачи планировщика и контекстное меню, а также может "
             "ограничивать объём памяти, который используют другие программы. Это бета-версия: она ещё тестируется "
             "и может содержать ошибки."),
            ("Вы используете программу на свой страх и риск",
             "SimpleTool предоставляется «как есть» и «по мере доступности», без каких-либо гарантий, явных или "
             "подразумеваемых, в том числе гарантий того, что программа подходит для определённой цели, работает без "
             "ошибок или подходит для вашего компьютера. Вы сами выбираете, какие изменения вносить, и сами отвечаете "
             "за этот выбор и его последствия."),
            ("Прежде чем что-то менять",
             "Сделайте резервную копию важных файлов и создайте точку восстановления Windows: на странице «Снимки "
             "системы» для этого есть кнопка. Прочитайте описание каждого твика, прежде чем применять его. "
             "Используйте SimpleTool только на компьютере, который принадлежит вам или который вам разрешено "
             "настраивать. На рабочем или учебном компьютере сначала спросите администратора."),
            ("Что может пойти не так",
             "Изменение системных настроек может привести к тому, что Windows, драйверы или другие программы начнут "
             "работать иначе или перестанут работать, отключатся нужные вам функции или придётся восстанавливать "
             "настройки либо переустанавливать Windows. «Откатить» и снимки системы стараются вернуть исходные "
             "значения, но не могут гарантировать этого в каждом случае — например, после обновления Windows или "
             "если те же настройки изменила другая программа. Программа с ограниченной памятью может работать "
             "медленнее."),
            ("Ответственность",
             "В максимальной степени, допустимой законом, blagotech не несёт ответственности за любые убытки или "
             "ущерб, возникшие в связи с использованием SimpleTool или невозможностью его использовать, включая "
             "потерю данных, повреждение Windows или других программ, время, когда компьютером нельзя пользоваться, "
             "упущенный доход и расходы на ремонт, восстановление данных или переустановку Windows."),
            ("Ваши права по закону",
             "Ничто в этом соглашении не исключает и не ограничивает ответственность за смерть или вред здоровью, "
             "причинённые по неосторожности, за мошенничество, а также любую другую ответственность, которую закон не "
             "позволяет исключить или ограничить. Если вы используете SimpleTool как потребитель, это соглашение не "
             "затрагивает ваших прав, предусмотренных законом."),
            ("Ваши данные",
             "SimpleTool не собирает персональные данные и ничего не отправляет через интернет. Его настройки, "
             "резервные копии и снимки хранятся на вашем компьютере в папке %LOCALAPPDATA%\\SimpleTool; чтобы "
             "удалить их, удалите эту папку."),
            ("Лицензия и товарные знаки",
             "Исходный код SimpleTool распространяется по лицензии MIT, и это соглашение не ограничивает права, "
             "которые она вам даёт. Название blagotech, знак b!t и логотип лицензией MIT не охватываются."),
            ("Изменения соглашения",
             "Следующие версии SimpleTool могут выходить с новой редакцией соглашения. Если соглашение изменится, "
             "SimpleTool покажет его снова и попросит принять."),
            ("Применимое право",
             "Это соглашение регулируется правом Англии и Уэльса. Если вы потребитель и живёте в Шотландии или "
             "Северной Ирландии, вы также можете обратиться в суд по месту жительства. Если перевод соглашения "
             "расходится с английской версией, действует английская версия."),
            ("Контакты",
             "Вопросы о SimpleTool и этом соглашении: service@blagotech.uk."),
        ],
    },
    "uk": {
        "title": "Угода користувача",
        "updated": "Останнє оновлення: 20 жовтня 2026 р.",
        "intro": "Прочитайте цю угоду, перш ніж користуватися SimpleTool. Натискаючи «Приймаю», ви погоджуєтеся з її "
                 "умовами. Якщо ви не згодні, натисніть «Вихід» і не використовуйте SimpleTool.",
        "sections": [
            ("Що таке SimpleTool",
             "SimpleTool — безкоштовна програма для Windows 10 і 11 від blagotech (blagotech.uk). Вона змінює "
             "налаштування Windows: параметри реєстру, служби, завдання планувальника та контекстне меню, а також "
             "може обмежувати обсяг пам'яті, який використовують інші програми. Це бета-версія: вона ще тестується "
             "і може містити помилки."),
            ("Ви використовуєте програму на власний ризик",
             "SimpleTool надається «як є» і «в міру доступності», без будь-яких гарантій, явних чи неявних, зокрема "
             "гарантій того, що програма придатна для певної мети, працює без помилок або підходить для вашого "
             "комп'ютера. Ви самі обираєте, які зміни вносити, і самі відповідаєте за цей вибір та його наслідки."),
            ("Перш ніж щось змінювати",
             "Зробіть резервну копію важливих файлів і створіть точку відновлення Windows: на сторінці «Знімки "
             "системи» для цього є кнопка. Прочитайте опис кожного твіка, перш ніж застосовувати його. "
             "Використовуйте SimpleTool лише на комп'ютері, який належить вам або який вам дозволено налаштовувати. "
             "На робочому чи навчальному комп'ютері спершу запитайте адміністратора."),
            ("Що може піти не так",
             "Зміна системних налаштувань може призвести до того, що Windows, драйвери чи інші програми почнуть "
             "працювати інакше або перестануть працювати, вимкнуться потрібні вам функції або доведеться відновлювати "
             "налаштування чи перевстановлювати Windows. «Відкотити» та знімки системи намагаються повернути "
             "початкові значення, але не можуть гарантувати цього в кожному випадку — наприклад, після оновлення "
             "Windows або якщо ті самі налаштування змінила інша програма. Програма з обмеженою пам'яттю може "
             "працювати повільніше."),
            ("Відповідальність",
             "У максимальному обсязі, дозволеному законом, blagotech не несе відповідальності за будь-які збитки чи "
             "шкоду, що виникли у зв'язку з використанням SimpleTool або неможливістю його використовувати, зокрема "
             "втрату даних, пошкодження Windows чи інших програм, час, коли комп'ютером неможливо користуватися, "
             "втрачений дохід і витрати на ремонт, відновлення даних або перевстановлення Windows."),
            ("Ваші права за законом",
             "Ніщо в цій угоді не виключає і не обмежує відповідальність за смерть або шкоду здоров'ю, заподіяні "
             "через недбалість, за шахрайство, а також будь-яку іншу відповідальність, яку закон не дозволяє виключити "
             "чи обмежити. Якщо ви використовуєте SimpleTool як споживач, ця угода не зачіпає ваших прав, "
             "передбачених законом."),
            ("Ваші дані",
             "SimpleTool не збирає персональні дані й нічого не надсилає через інтернет. Його налаштування, резервні "
             "копії та знімки зберігаються на вашому комп'ютері в папці %LOCALAPPDATA%\\SimpleTool; щоб видалити їх, "
             "видаліть цю папку."),
            ("Ліцензія та торговельні марки",
             "Вихідний код SimpleTool поширюється за ліцензією MIT, і ця угода не обмежує права, які вона вам надає. "
             "Назва blagotech, знак b!t і логотип ліцензією MIT не охоплюються."),
            ("Зміни угоди",
             "Наступні версії SimpleTool можуть виходити з новою редакцією угоди. Якщо угода зміниться, SimpleTool "
             "покаже її знову й попросить прийняти."),
            ("Застосовне право",
             "Ця угода регулюється правом Англії та Уельсу. Якщо ви споживач і проживаєте в Шотландії чи Північній "
             "Ірландії, ви також можете звернутися до суду за місцем проживання. Якщо переклад угоди відрізняється "
             "від англійської версії, діє англійська версія."),
            ("Контакти",
             "Питання про SimpleTool і цю угоду: service@blagotech.uk."),
        ],
    },
}
