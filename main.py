import tkinter as tk
from tkinter import ttk


# Функция для отображения соответствующих опций
def show_options(category):
    # Очистить правую панель перед отображением новых опций
    for widget in options_frame.winfo_children():
        widget.destroy()

    # Опции для каждой категории
    options = {
        "Конфиденциальность": [
            "Отключение рекламного идентификатора и рекламы",
            "Отключение всех видов синхронизаций Windows",
            "Отключение всех видов телеметрий Windows"
        ],
        "Система": [
            "Отключение телеметрии NVIDIA",
            "Отключение сбора данных через события планировщика",
            "Отключение сбора данных об установленных приложениях"
        ],
        "Интерфейс": [
            "Нормальный цвет всплывающей подсказки",
            "Уменьшение кнопок Закрыть, Свернуть, Развернуть",
            "Удаление объемных объектов из проводника"
        ]
    }

    # Если не выбрана категория, отображаем текст описания приложения
    if not category:
        description_label.config(text="Добро пожаловать в SimpleTool!\nВыберите категорию слева, чтобы начать настройку.")
        description_label.pack(padx=10, pady=10)
        return
    else:
        description_label.pack_forget()

    # Отображаем соответствующие опции для выбранной категории
    for option in options.get(category, []):
        if option not in checkbox_states:
            checkbox_states[option] = tk.BooleanVar(value=False)
        chk = ttk.Checkbutton(options_frame, text=option, variable=checkbox_states[option])
        chk.pack(anchor='w')

# Функция для применения выбранных настроек
def apply_settings():
    applied_settings = [option for option, var in checkbox_states.items() if var.get()]
    if applied_settings:
        print(f"Примененные настройки: {', '.join(applied_settings)}")
    else:
        print("Нет примененных настроек.")

# Создаем главное окно
root = tk.Tk()
root.title("Win10 Tweaker Аналог")
root.geometry("600x400")

# Словарь для хранения состояний чекбоксов
checkbox_states = {}

# Создаем фрейм для левой панели категорий
categories_frame = ttk.Frame(root)
categories_frame.pack(side="left", fill="y", padx=10, pady=10)

# Создаем фрейм для правой панели с опциями
options_frame = ttk.Frame(root)
options_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

# Текстовое описание на главной странице
description_label = ttk.Label(options_frame, text="Добро пожаловать в SimpleTool!\nВыберите категорию слева, чтобы начать настройку.")
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
