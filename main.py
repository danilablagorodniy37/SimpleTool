"""SimpleTool — твики Windows: конфиденциальность, система, Проводник, контекстное меню."""
import ctypes
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import engine
import i18n
import tweaks

VERSION = "0.3"
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

# Палитра из фирменного стиля blagotech
NAVY = "#0A1B33"    # основной тёмно-синий: фон
CARD = "#12294A"    # средний синий: карточки и панели
PLATE = "#16345C"   # плашка на тёмном: активные элементы
BORDER = "#223B60"
TEXT = "#E8EEFC"
MUTED = "#B8C3E6"
DIM = "#7F8DB0"
ACCENT = "#5FB4FF"  # акцент на тёмном фоне
BLUE = "#2F8CF5"    # акцентный синий: кнопки
TEAL = "#34D8A8"    # бирюзовый: «применено»
AMBER = "#F0B783"   # предупреждения

STATUS_COLORS = {"applied": TEAL, "partial": AMBER, "not_applied": MUTED,
                 "unavailable": DIM, "admin": AMBER, "checking": DIM}

# Значки из шрифта Segoe Fluent Icons / Segoe MDL2 Assets
ICONS = {"privacy": "\uE72E", "system": "\uE770", "explorer": "\uEC50", "context": "\uE8FD",
         "globe": "\uE774", "shield": "\uEA18", "chevron": "\uE70D", "warning": "\uE7BA"}


def mix(color, background, alpha):
    """Цвет color с непрозрачностью alpha поверх background."""
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(background[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * alpha + y * (1 - alpha)):02X}" for x, y in zip(a, b))


def load_settings():
    try:
        with open(os.path.join(engine.data_dir(), "settings.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    try:
        with open(os.path.join(engine.data_dir(), "settings.json"), "w", encoding="utf-8") as f:
            json.dump(settings, f)
    except OSError:
        pass


def relaunch_as_admin():
    """Перезапускает программу от имени администратора. Возвращает код ShellExecute (больше 32 — успех)."""
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, sys.argv[1:]
    else:
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        exe = pythonw if os.path.exists(pythonw) else sys.executable
        args = [os.path.abspath(sys.argv[0])] + sys.argv[1:]
    return ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, subprocess.list2cmdline(args), BASE_DIR, 1)


def style_title_bar(window):
    """Тёмный заголовок окна в цвет фона (Windows 10 1809+, цвет — Windows 11)."""
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        caption = int(NAVY[5:7] + NAVY[3:5] + NAVY[1:3], 16)  # COLORREF: 0x00BBGGRR
        for attribute, value in ((20, 1), (35, caption)):  # DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_CAPTION_COLOR
            data = ctypes.c_int(value)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data))
    except (AttributeError, OSError):
        pass


def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
              x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(points, smooth=True, **kw)


class FlatButton(tk.Label):
    """Плоская кнопка в цветах blagotech."""

    def __init__(self, parent, text, command, font, padding, primary=True):
        self.colors = (BLUE, "#FFFFFF", "#4A9EF7") if primary else (PLATE, TEXT, "#1E4573")
        super().__init__(parent, text=text, font=font, bg=self.colors[0], fg=self.colors[1],
                         padx=padding[0], pady=padding[1], cursor="hand2")
        self.command, self.enabled = command, True
        self.bind("<Enter>", lambda e: self.enabled and self.config(bg=self.colors[2]))
        self.bind("<Leave>", lambda e: self.enabled and self.config(bg=self.colors[0]))
        self.bind("<Button-1>", lambda e: self.enabled and self.command())

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.config(bg=self.colors[0] if enabled else mix(self.colors[0], CARD, 0.35),
                    fg=self.colors[1] if enabled else DIM, cursor="hand2" if enabled else "arrow")


class CheckBox(tk.Canvas):
    def __init__(self, parent, size):
        super().__init__(parent, width=size, height=size, bg=CARD, highlightthickness=0)
        self.size, self.checked, self.enabled = size, False, True
        self.draw()

    def set(self, checked, enabled):
        if (checked, enabled) != (self.checked, self.enabled):
            self.checked, self.enabled = checked, enabled
            self.draw()

    def draw(self):
        self.delete("all")
        s = self.size
        if not self.enabled:
            fill, outline = CARD, BORDER
        elif self.checked:
            fill = outline = BLUE
        else:
            fill, outline = NAVY, "#4A6491"
        rounded_rect(self, 1, 1, s - 1, s - 1, s * 0.28, fill=fill, outline=outline, width=1.5)
        if self.checked and self.enabled:
            self.create_line(s * 0.27, s * 0.52, s * 0.43, s * 0.68, s * 0.74, s * 0.34, fill="white",
                             width=max(2, s / 9), capstyle="round", joinstyle="round")


class App:
    def __init__(self, root):
        self.root = root
        self.admin = engine.is_admin()
        self.settings = load_settings()
        lang = self.settings.get("lang")
        self.lang = lang if lang in i18n.TEXTS else i18n.detect_language()
        self.scale = root.winfo_fpixels("1i") / 96
        self.tweak_by_id = {t.id: t for t in tweaks.TWEAKS}
        self.category = tweaks.CATEGORIES[0]
        self.selected = set()
        self.statuses = {}  # id твика -> applied / partial / not_applied / unavailable
        self.ctx = None
        self.busy = True    # до окончания первой проверки
        self.message = ("checking", {})
        self.hovered = None
        self.cards = {}
        self.desc_wrap = self.px(520)
        self.jobs = queue.Queue()
        self.setup_fonts()
        self.setup_styles()
        name = "logo-80.png" if self.scale >= 1.75 else "logo-40.png"
        try:
            self.logo = tk.PhotoImage(file=os.path.join(BASE_DIR, "assets", name))
        except tk.TclError:
            self.logo = None
        self.build()
        self.run_job(self.check_all, self.on_checked)
        self.poll()
        if not self.admin:
            root.after(400, self.show_admin_dialog)

    # --- Оформление ---

    def px(self, n):
        return int(round(n * self.scale))

    def setup_fonts(self):
        families = set(tkfont.families(self.root))
        icons = "Segoe Fluent Icons" if "Segoe Fluent Icons" in families else "Segoe MDL2 Assets"
        semibold = "Segoe UI Semibold" if "Segoe UI Semibold" in families else "Segoe UI"
        self.fonts = {
            "brand": (semibold, 14), "title": (semibold, 19), "h2": (semibold, 11), "dialog": (semibold, 13),
            "nav": ("Segoe UI", 10), "nav_active": (semibold, 10), "body": ("Segoe UI", 10),
            "small": ("Segoe UI", 9), "small_bold": (semibold, 9), "pill": (semibold, 8), "button": (semibold, 10),
            "icon": (icons, 13), "icon_small": (icons, 10), "icon_tiny": (icons, 7), "icon_big": (icons, 20),
        }

    def setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.layout("Brand.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        style.configure("Brand.Vertical.TScrollbar", troughcolor=NAVY, background=PLATE, bordercolor=NAVY,
                        lightcolor=PLATE, darkcolor=PLATE, arrowsize=self.px(8), gripcount=0, relief="flat")
        style.map("Brand.Vertical.TScrollbar", background=[("pressed", BLUE), ("active", "#24508A")])

    def t(self, key, **kw):
        return i18n.TEXTS[self.lang]["ui"][key].format(**kw)

    def tweak_text(self, tweak):
        return i18n.TEXTS[self.lang]["tweaks"][tweak.id]

    def pointer_inside(self, widget):
        target = self.root.winfo_containing(*self.root.winfo_pointerxy())
        while target is not None:
            if target is widget:
                return True
            target = target.master
        return False

    # --- Построение окна ---

    def build(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.title("SimpleTool")
        self.root.configure(bg=NAVY)
        self.root.columnconfigure(2, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.build_sidebar()
        tk.Frame(self.root, bg=BORDER, width=1).grid(row=0, column=1, sticky="ns")
        self.build_main()
        self.show_category(self.category)

    def build_sidebar(self):
        px = self.px
        side = tk.Frame(self.root, bg=NAVY, width=px(264))
        side.grid(row=0, column=0, sticky="ns")
        side.pack_propagate(False)

        # Логотип и название
        brand = tk.Frame(side, bg=NAVY)
        brand.pack(fill="x", padx=px(20), pady=(px(22), px(26)))
        if self.logo:
            tk.Label(brand, image=self.logo, bg=NAVY).pack(side="left")
        names = tk.Frame(brand, bg=NAVY)
        names.pack(side="left", padx=(px(12), 0))
        tk.Label(names, text="SimpleTool", font=self.fonts["brand"], fg=TEXT, bg=NAVY, bd=0).pack(anchor="w")
        maker = tk.Frame(names, bg=NAVY)
        maker.pack(anchor="w")
        for text, font, color in ((self.t("by") + " ", "small", DIM), ("blago", "small_bold", TEXT),
                                  ("tech", "small_bold", ACCENT)):
            tk.Label(maker, text=text, font=self.fonts[font], fg=color, bg=NAVY, bd=0, padx=0).pack(side="left")

        # Категории
        self.nav = {}
        for cat in tweaks.CATEGORIES:
            item = tk.Frame(side, bg=NAVY, cursor="hand2")
            item.pack(fill="x", padx=px(12), pady=px(2))
            bar = tk.Frame(item, bg=NAVY, width=px(3))
            bar.pack(side="left", fill="y")
            icon = tk.Label(item, text=ICONS[cat], font=self.fonts["icon"], bg=NAVY, width=2)
            icon.pack(side="left", padx=(px(8), px(6)), pady=px(9))
            # Счётчик пакуется раньше названия, чтобы длинное название не наезжало на него
            count = tk.Label(item, text="", font=self.fonts["small"], fg=DIM, bg=NAVY)
            count.pack(side="right", padx=(px(6), px(10)))
            name = tk.Label(item, text=i18n.TEXTS[self.lang]["categories"][cat][0], bg=NAVY, anchor="w")
            name.pack(side="left", fill="x", expand=True)
            for widget in (item, bar, icon, name, count):
                widget.bind("<Button-1>", lambda e, c=cat: self.show_category(c))
                widget.bind("<Enter>", lambda e, c=cat: self.paint_nav(hover=c))
                widget.bind("<Leave>", lambda e, w=item: None if self.pointer_inside(w) else self.paint_nav())
            self.nav[cat] = (item, bar, icon, name, count)

        # Права и версия
        bottom = tk.Frame(side, bg=NAVY)
        bottom.pack(side="bottom", fill="x", padx=px(20), pady=(0, px(18)))
        color = TEAL if self.admin else AMBER
        badge_bg = mix(color, NAVY, 0.14)
        badge = tk.Frame(bottom, bg=badge_bg)
        badge.pack(anchor="w")
        parts = [tk.Label(badge, text=ICONS["shield"], font=self.fonts["icon_small"], fg=color, bg=badge_bg),
                 tk.Label(badge, text=self.t("admin_yes" if self.admin else "admin_no"),
                          font=self.fonts["small_bold"], fg=color, bg=badge_bg)]
        parts[0].pack(side="left", padx=(px(10), px(6)), pady=px(6))
        parts[1].pack(side="left", padx=(0, px(12)))
        if not self.admin:
            for widget in [badge] + parts:
                widget.config(cursor="hand2")
                widget.bind("<Button-1>", lambda e: self.show_admin_dialog())
        tk.Label(bottom, text="v" + VERSION, font=self.fonts["small"], fg=DIM, bg=NAVY).pack(anchor="w", pady=(px(10), 0))

    def build_main(self):
        px = self.px
        main = tk.Frame(self.root, bg=NAVY)
        main.grid(row=0, column=2, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        # Шапка: название категории, описание, язык, выбор
        header = tk.Frame(main, bg=NAVY)
        header.grid(row=0, column=0, sticky="ew", padx=(px(32), px(24)), pady=(px(22), px(14)))
        header.columnconfigure(0, weight=1)
        self.title_label = tk.Label(header, font=self.fonts["title"], fg=TEXT, bg=NAVY, anchor="w")
        self.title_label.grid(row=0, column=0, sticky="w")
        self.desc_label = tk.Label(header, font=self.fonts["body"], fg=MUTED, bg=NAVY, anchor="w", justify="left")
        self.desc_label.grid(row=1, column=0, sticky="w", pady=(px(4), 0))
        self.build_language_menu(header).grid(row=0, column=1, sticky="ne")
        links = tk.Frame(header, bg=NAVY)
        links.grid(row=1, column=1, sticky="se")
        for key, action in (("select_all", self.select_all), ("clear", self.clear_selection)):
            link = tk.Label(links, text=self.t(key), font=self.fonts["small_bold"], fg=ACCENT, bg=NAVY, cursor="hand2")
            link.pack(side="left", padx=(px(16), 0))
            link.bind("<Button-1>", lambda e, a=action: a())
            link.bind("<Enter>", lambda e, w=link: w.config(fg=TEXT))
            link.bind("<Leave>", lambda e, w=link: w.config(fg=ACCENT))

        # Список твиков с прокруткой
        holder = tk.Frame(main, bg=NAVY)
        holder.grid(row=1, column=0, sticky="nsew")
        self.canvas = tk.Canvas(holder, bg=NAVY, highlightthickness=0, bd=0, yscrollincrement=px(24))
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview,
                                  style="Brand.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, px(6)), pady=px(2))
        self.canvas.pack(side="left", fill="both", expand=True)
        self.list_frame = tk.Frame(self.canvas, bg=NAVY)
        self.list_window = self.canvas.create_window(0, 0, window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.root.bind_all("<MouseWheel>", self.on_wheel)

        # Подвал: сообщение и кнопки
        footer = tk.Frame(main, bg=CARD)
        footer.grid(row=2, column=0, sticky="ew")
        tk.Frame(footer, bg=BORDER, height=1).pack(fill="x")
        inner = tk.Frame(footer, bg=CARD)
        inner.pack(fill="x", padx=(px(32), px(24)), pady=px(14))
        padding = (px(20), px(8))
        self.apply_button = FlatButton(inner, self.t("apply"), self.apply_selected, self.fonts["button"], padding)
        self.apply_button.pack(side="right")
        self.revert_button = FlatButton(inner, self.t("revert"), self.revert_selected, self.fonts["button"], padding,
                                        primary=False)
        self.revert_button.pack(side="right", padx=(0, px(10)))
        self.message_label = tk.Label(inner, font=self.fonts["body"], fg=MUTED, bg=CARD, anchor="w", justify="left",
                                      wraplength=px(440))
        self.message_label.pack(side="left", fill="x", expand=True)

    def build_language_menu(self, parent):
        """Отдельное меню выбора языка в шапке."""
        px = self.px
        button = tk.Frame(parent, bg=CARD, cursor="hand2", highlightthickness=1, highlightbackground=BORDER)
        parts = [tk.Label(button, text=ICONS["globe"], font=self.fonts["icon_small"], fg=ACCENT, bg=CARD),
                 tk.Label(button, text=dict(i18n.LANGUAGES)[self.lang], font=self.fonts["small_bold"], fg=TEXT, bg=CARD),
                 tk.Label(button, text=ICONS["chevron"], font=self.fonts["icon_tiny"], fg=MUTED, bg=CARD)]
        parts[0].pack(side="left", padx=(px(12), px(8)), pady=px(7))
        parts[1].pack(side="left")
        parts[2].pack(side="left", padx=(px(10), px(12)))

        menu = tk.Menu(self.root, tearoff=False, bg=CARD, fg=TEXT, activebackground=BLUE, activeforeground="#FFFFFF",
                       disabledforeground=DIM, selectcolor=ACCENT, font=self.fonts["body"], bd=0)
        menu.add_command(label=self.t("language"), state="disabled")
        menu.add_separator()
        self.lang_var = tk.StringVar(value=self.lang)
        for code, name in i18n.LANGUAGES:
            menu.add_radiobutton(label=name, value=code, variable=self.lang_var,
                                 command=lambda c=code: self.set_language(c))

        def popup(event):
            menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height() + px(4))

        for widget in [button] + parts:
            widget.bind("<Button-1>", popup)
            widget.bind("<Enter>", lambda e: button.config(highlightbackground=ACCENT))
            widget.bind("<Leave>", lambda e: None if self.pointer_inside(button) else button.config(highlightbackground=BORDER))
        return button

    def show_category(self, cat):
        self.category = cat
        name, desc = i18n.TEXTS[self.lang]["categories"][cat]
        self.title_label.config(text=name)
        self.desc_label.config(text=desc)
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self.cards = {t.id: self.build_card(t) for t in tweaks.TWEAKS if t.category == cat}
        tk.Frame(self.list_frame, bg=NAVY, height=self.px(8)).pack()
        self.canvas.yview_moveto(0)
        self.update_view()

    def build_card(self, tweak):
        px = self.px
        name, desc = self.tweak_text(tweak)
        card = tk.Frame(self.list_frame, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=(px(32), px(14)), pady=(0, px(10)))
        card.columnconfigure(1, weight=1)
        check = CheckBox(card, px(20))
        check.grid(row=0, column=0, rowspan=2, sticky="n", padx=(px(18), px(14)), pady=(px(16), 0))
        title = tk.Label(card, text=name, font=self.fonts["h2"], bg=CARD, anchor="w", justify="left",
                         wraplength=self.desc_wrap)
        title.grid(row=0, column=1, sticky="ew", pady=(px(13), 0))
        body = tk.Label(card, text=desc, font=self.fonts["small"], fg=MUTED, bg=CARD, anchor="w", justify="left",
                        wraplength=self.desc_wrap)
        body.grid(row=1, column=1, sticky="ew", pady=(px(3), px(14)))
        pill = tk.Label(card, font=self.fonts["pill"], padx=px(10), pady=px(3))
        pill.grid(row=0, column=2, rowspan=2, sticky="e", padx=(px(12), px(18)))
        for widget in (card, check, title, body, pill):
            widget.bind("<Button-1>", lambda e, t=tweak: self.toggle(t))
            widget.bind("<Enter>", lambda e, t=tweak: self.hover_card(t, True))
            widget.bind("<Leave>", lambda e, t=tweak, c=card: None if self.pointer_inside(c) else self.hover_card(t, False))
        return {"card": card, "check": check, "title": title, "body": body, "pill": pill}

    # --- Состояние ---

    def card_state(self, tweak):
        status = self.statuses.get(tweak.id)
        if status is None:
            return "checking"
        if status != "unavailable" and tweak.admin and not self.admin:
            return "admin"
        return status

    def selectable(self, tweak):
        return not self.busy and self.card_state(tweak) in ("applied", "partial", "not_applied")

    def update_view(self):
        for tweak_id in self.cards:
            self.paint_card(self.tweak_by_id[tweak_id])
        self.paint_nav()
        self.update_footer()

    def paint_card(self, tweak):
        widgets = self.cards[tweak.id]
        state = self.card_state(tweak)
        enabled = self.selectable(tweak)
        selected = tweak.id in self.selected
        color = STATUS_COLORS[state]
        widgets["pill"].config(text=self.t("status_" + state), fg=color, bg=mix(color, CARD, 0.16))
        widgets["check"].set(selected, enabled or state in ("applied", "partial", "not_applied"))
        border = BLUE if selected else ("#3A5A86" if self.hovered == tweak.id and enabled else BORDER)
        widgets["card"].config(highlightbackground=border, highlightcolor=border)
        widgets["title"].config(fg=TEXT if state not in ("unavailable", "admin") else DIM)
        for widget in widgets.values():
            widget.config(cursor="hand2" if enabled else "arrow")

    def paint_nav(self, hover=None):
        for cat, (item, bar, icon, name, count) in self.nav.items():
            active = cat == self.category
            bg = PLATE if active else (CARD if cat == hover else NAVY)
            for widget in (item, icon, name, count):
                widget.config(bg=bg)
            bar.config(bg=ACCENT if active else bg)
            icon.config(fg=ACCENT if active else MUTED)
            name.config(fg=TEXT if active else MUTED, font=self.fonts["nav_active" if active else "nav"])
            items = [t for t in tweaks.TWEAKS if t.category == cat]
            applied = sum(self.statuses.get(t.id) == "applied" for t in items)
            count.config(text=f"{applied}/{len(items)}" if self.statuses else "")

    def update_footer(self):
        if self.message:
            key, kw = self.message
            text = self.t(key, **kw)
        elif self.selected:
            text = self.t("selected", n=len(self.selected))
        else:
            text = self.t("hint_select")
        self.message_label.config(text=text)
        enabled = not self.busy and bool(self.selected)
        self.apply_button.set_enabled(enabled)
        self.revert_button.set_enabled(enabled)

    # --- Действия пользователя ---

    def hover_card(self, tweak, inside):
        self.hovered = tweak.id if inside else None
        if tweak.id in self.cards:
            self.paint_card(tweak)

    def toggle(self, tweak):
        if not self.selectable(tweak):
            return
        self.selected ^= {tweak.id}
        self.message = None
        self.paint_card(tweak)
        self.update_footer()

    def select_all(self):
        if self.busy:
            return
        self.selected |= {i for i in self.cards if self.selectable(self.tweak_by_id[i])}
        self.message = None
        self.update_view()

    def clear_selection(self):
        self.selected -= set(self.cards)
        self.message = None
        self.update_view()

    def set_language(self, lang):
        if lang == self.lang:
            return
        self.lang = lang
        self.settings["lang"] = lang
        save_settings(self.settings)
        self.build()

    def on_canvas_resize(self, event):
        px = self.px
        self.canvas.itemconfigure(self.list_window, width=event.width)
        self.desc_wrap = max(px(220), event.width - px(270))
        for widgets in self.cards.values():
            widgets["title"].config(wraplength=self.desc_wrap)
            widgets["body"].config(wraplength=self.desc_wrap)
        self.desc_label.config(wraplength=max(px(220), event.width - px(240)))

    def on_wheel(self, event):
        try:
            if event.widget.winfo_toplevel() is not self.root:
                return
        except (AttributeError, KeyError, tk.TclError):
            return
        if self.list_frame.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-event.delta / 120) * 2, "units")

    def apply_selected(self):
        chosen = [t for t in tweaks.TWEAKS if t.id in self.selected and self.statuses.get(t.id) != "applied"]
        if not chosen:
            self.message = ("nothing_to_apply", {})
            self.update_footer()
            return
        lang, ctx = self.lang, self.ctx
        self.start_work(chosen, lambda t: engine.apply(t, lang, ctx), "working_apply", "done_apply")

    def revert_selected(self):
        chosen = [t for t in tweaks.TWEAKS if t.id in self.selected and self.statuses.get(t.id) in ("applied", "partial")]
        if not chosen:
            self.message = ("nothing_to_revert", {})
            self.update_footer()
            return
        ctx = self.ctx
        self.start_work(chosen, lambda t: engine.revert(t, ctx), "working_revert", "done_revert")

    def start_work(self, chosen, action, working_key, done_key):
        """Применяет или откатывает твики в фоне, затем заново проверяет их состояние."""
        self.busy = True
        self.message = (working_key, {})
        self.update_view()
        names = {t.id: self.tweak_text(t)[0] for t in chosen}

        def work():
            errors = []
            for tweak in chosen:
                errors += [f"{names[tweak.id]}: {error}" for error in action(tweak)]
            engine.notify_shell()
            return errors, self.check_all()

        def done(result):
            self.busy = False
            self.selected.clear()
            if isinstance(result, Exception):
                errors = [str(result)]
                self.run_job(self.check_all, self.on_checked)
            else:
                errors, (self.ctx, self.statuses) = result
            self.message = (done_key, {"n": len(chosen)})
            self.update_view()
            if errors:
                self.show_errors(errors)

        self.run_job(work, done)

    # --- Фоновые задачи ---

    @staticmethod
    def check_all():
        ctx = engine.Context()
        return ctx, {t.id: engine.status(t, ctx) for t in tweaks.TWEAKS}

    def on_checked(self, result):
        self.busy = False
        if self.message == ("checking", {}):
            self.message = None
        if isinstance(result, Exception):
            self.update_view()
            self.show_errors([str(result)])
            return
        self.ctx, self.statuses = result
        self.update_view()

    def run_job(self, work, done):
        def target():
            try:
                result = work()
            except Exception as exc:  # ошибка в фоне не должна молча оставить окно в состоянии «занято»
                result = exc
            self.jobs.put((done, result))

        threading.Thread(target=target, daemon=True).start()

    def poll(self):
        while True:
            try:
                done, result = self.jobs.get_nowait()
            except queue.Empty:
                break
            done(result)
        self.root.after(50, self.poll)

    # --- Диалоги ---

    def dialog(self, title, icon, color, heading, text):
        """Окно в стиле blagotech: значок, заголовок, текст. Возвращает (окно, рамка для содержимого)."""
        px = self.px
        win = tk.Toplevel(self.root, bg=CARD)
        win.withdraw()
        win.title(title)
        win.transient(self.root)
        win.resizable(False, False)
        body = tk.Frame(win, bg=CARD)
        body.pack(padx=px(28), pady=(px(24), px(22)))
        body.columnconfigure(1, weight=1)  # лишняя ширина достаётся тексту, а не колонке значка
        tk.Label(body, text=icon, font=self.fonts["icon_big"], fg=color, bg=mix(color, CARD, 0.14),
                 width=2, pady=px(6)).grid(row=0, column=0, rowspan=2, sticky="nw")
        tk.Label(body, text=heading, font=self.fonts["dialog"], fg=TEXT, bg=CARD, anchor="w").grid(
            row=0, column=1, sticky="w", padx=(px(16), 0))
        tk.Label(body, text=text, font=self.fonts["body"], fg=MUTED, bg=CARD, justify="left", anchor="w",
                 wraplength=px(440)).grid(row=1, column=1, sticky="w", padx=(px(16), 0), pady=(px(6), 0))
        content = tk.Frame(body, bg=CARD)
        content.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(px(18), 0))
        return win, content

    def present(self, win):
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_reqheight()) // 3
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        style_title_bar(win)
        win.deiconify()
        win.grab_set()
        win.focus_set()

    def show_admin_dialog(self):
        px = self.px
        win, content = self.dialog(self.t("admin_title"), ICONS["shield"], AMBER, self.t("admin_title"),
                                   self.t("admin_text"))
        error = tk.Label(content, text="", font=self.fonts["small"], fg=AMBER, bg=CARD, anchor="w")
        error.pack(fill="x")

        def restart():
            code = relaunch_as_admin()
            if code > 32:
                self.root.destroy()
            elif code != 5:  # 5 — пользователь отменил запрос UAC
                error.config(text=self.t("admin_failed"))

        padding = (px(18), px(8))
        FlatButton(content, self.t("admin_restart"), restart, self.fonts["button"], padding).pack(side="right")
        FlatButton(content, self.t("admin_continue"), win.destroy, self.fonts["button"], padding,
                   primary=False).pack(side="right", padx=(0, px(10)))
        self.present(win)

    def show_errors(self, errors):
        px = self.px
        win, content = self.dialog(self.t("errors_title"), ICONS["warning"], AMBER, self.t("errors_title"),
                                   self.t("errors_intro"))
        text = tk.Text(content, font=self.fonts["small"], fg=TEXT, bg=NAVY, relief="flat", wrap="word",
                       width=72, height=min(12, 2 * len(errors) + 1), padx=px(12), pady=px(10),
                       highlightthickness=0)
        text.insert("1.0", "\n\n".join(errors))
        text.config(state="disabled")
        text.pack(fill="x")
        FlatButton(content, self.t("close"), win.destroy, self.fonts["button"], (px(18), px(8))).pack(
            side="right", pady=(px(16), 0))
        self.present(win)


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("blagotech.SimpleTool")
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    root.withdraw()
    try:
        root.iconbitmap(default=os.path.join(BASE_DIR, "assets", "app.ico"))
    except tk.TclError:
        pass
    app = App(root)
    width = min(app.px(1060), root.winfo_screenwidth() - app.px(40))
    height = min(app.px(720), root.winfo_screenheight() - app.px(80))
    root.minsize(app.px(880), app.px(560))
    root.geometry(f"{width}x{height}+{(root.winfo_screenwidth() - width) // 2}+{(root.winfo_screenheight() - height) // 3}")
    style_title_bar(root)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
