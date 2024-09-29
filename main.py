import tkinter as tk
from tkinter import ttk
import subprocess  # Для выполнения системных команд


# Функция для проверки состояния службы
def check_service_status(service_name):
    command = f'powershell Get-Service -Name {service_name} | Select-Object -ExpandProperty Status'
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    return result.stdout.strip() == "Stopped"


# Функции для каждой настройки
def disable_ads():
    command = 'powershell Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\AdvertisingInfo" -Name Enabled -Value 0'
    subprocess.run(command, shell=True)
    print("Рекламный идентификатор и реклама отключены.")


def disable_sync():
    command = 'powershell Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\SyncSettings" -Name SyncSettings -Value 0'
    subprocess.run(command, shell=True)
    print("Синхронизация Windows отключена.")


def disable_telemetry():
    command = 'powershell Set-ItemProperty -Path "HKLM:\\Software\\Policies\\Microsoft\\Windows\\DataCollection" -Name AllowTelemetry -Value 0'
    subprocess.run(command, shell=True)
    print("Телеметрия Windows отключена.")


def disable_nvidia_telemetry():
    command = 'powershell Stop-Service -Name "NvTelemetryContainer" -Force'
    subprocess.run(command, shell=True)
    print("Телеметрия NVIDIA отключена.")


def disable_event_log():
    command = 'powershell Stop-Service -Name "EventLog" -Force'
    subprocess.run(command, shell=True)
    print("Сбор данных через планировщик отключен.")


# Словарь для хранения опций и соответствующих функций
options_functions = {
    "Отключение рекламного идентификатора и рекламы": disable_ads,
    "Отключение всех видов синхронизаций Windows": disable_sync,
    "Отключение всех видов телеметрий Windows": disable_telemetry,
    "Отключение телеметрии NVIDIA": disable_nvidia_telemetry,
    "Отключение сбора данных через события планировщика": disable_event_log,
}

# Словарь для хранения состояний чекбоксов
checkbox_states = {}


# Функция для отображения соответствующих опций
def show_options(category):
    # Очистить правую панель перед отображением новых опций
    for widget in options_frame.winfo_children():
        widget.destroy()

    # Опции для каждой категории
    options = {
        "Конфиденциальность": [
            {"name": "Отключение рекламного идентификатора и рекламы", "service": None},
            {"name": "Отключение всех видов синхронизаций Windows", "service": None},
            {"name": "Отключение всех видов телеметрий Windows", "service": "DiagTrack"}
        ],
        "Система": [
            {"name": "Отключение телеметрии NVIDIA", "service": "NvTelemetryContainer"},
            {"name": "Отключение сбора данных через события планировщика", "service": "EventLog"}
        ],
        "Интерфейс": [
            {"name": "Нормальный цвет всплывающей подсказки", "service": None},
            {"name": "Уменьшение кнопок Закрыть, Свернуть, Развернуть", "service": None},
            {"name": "Удаление объемных объектов из проводника", "service": None}
        ]
    }

    # Если не выбрана категория, отображаем текст описания приложения
    if not category:
        description_label.config(
            text="Добро пожаловать в SimpleTool!\nВыберите категорию слева, чтобы начать настройку.")
        description_label.pack(padx=10, pady=10)
        return
    else:
        description_label.pack_forget()

    # Отображаем соответствующие опции для выбранной категории
    for option in options.get(category, []):
        option_name = option["name"]
        service_name = option.get("service", None)

        # Проверяем состояние службы, если она указана
        if service_name:
            if check_service_status(service_name):
                option_text = f"{option_name}"
                status_color = "green"
                status_text = "Применено"
            else:
                option_text = f"{option_name}"
                status_color = "red"
                status_text = "Не применено"
        else:
            option_text = option_name
            status_color = "grey"
            status_text = "Не поддерживается"

        frame = ttk.Frame(options_frame)
        frame.pack(anchor='w', pady=2)

        if option_name not in checkbox_states:
            checkbox_states[option_name] = tk.BooleanVar(value=False)

        chk = ttk.Checkbutton(frame, text=option_text, variable=checkbox_states[option_name])
        chk.pack(side='left')

        status_label = tk.Label(frame, text=status_text, fg=status_color)
        status_label.pack(side='left', padx=10)


# Функция для применения выбранных настроек
def apply_settings():
    for option, var in checkbox_states.items():
        if var.get() and option in options_functions:
            options_functions[option]()  # Вызов соответствующей функции

    # Сброс галочек
    for var in checkbox_states.values():
        var.set(False)

    # Обновляем отображение опций после применения изменений
    show_options(current_category)


# Создаем главное окно
root = tk.Tk()
root.title("Win10 Tweaker Аналог")
root.geometry("650x400")


# Центрируем окно
def center_window(root, width, height):
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')


center_window(root, 650, 400)

current_category = None

# Создаем фрейм для левой панели категорий
categories_frame = ttk.Frame(root)
categories_frame.pack(side="left", fill="y", padx=10, pady=10)

# Создаем фрейм для правой панели с опциями
options_frame = ttk.Frame(root)
options_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

# Текстовое описание на главной странице
description_label = ttk.Label(options_frame,
                              text="Добро пожаловать в SimpleTool!\nВыберите категорию слева, чтобы начать настройку.")
description_label.pack(padx=10, pady=10)

# Список категорий
categories = ["Конфиденциальность", "Система", "Интерфейс"]

# Кнопки для категорий
for category in categories:
    btn = ttk.Button(categories_frame, text=category, command=lambda c=category: show_options(c))
    btn.pack(fill="x", pady=5)

# Кнопка "Применить" с дополнительными стилями и отступом
apply_button = ttk.Button(categories_frame, text="Применить", command=apply_settings, style="Apply.TButton")
apply_button.pack(fill="x", padx=30, pady=20)

# Настройка стиля для кнопки "Применить"
style = ttk.Style()
style.configure("Apply.TButton", font=("Helvetica", 10, "bold"), foreground="#99CCFF")

root.mainloop()
