"""SimpleTool: Windows tweaks. System overview, privacy, system, File Explorer, context menu."""
import collections
import ctypes
import datetime
import gc
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import engine
import i18n
import limiter
import programs
import services
import theme
import tray
import tweaks
from theme import C, CATEGORY_COLORS, lerp, mix
from widgets import (Animator, Card, CheckBox, Flow, GradientButton, Meter, Pill, ScanRings, Segmented, Spinner,
                     Stepper, Toast, Toggle, descendants, ease_in_out, fade_in)

VERSION = "0.5"
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(BASE_DIR, "assets", "app.ico")
PAGES = ["overview"] + tweaks.CATEGORIES + ["memory", "snapshots"]
TRAY_OPEN, TRAY_LIMITER, TRAY_EXIT = 1, 2, 3  # tray icon menu items
SELECTABLE = ("applied", "partial", "not_applied", "unknown")
REVERTIBLE = ("applied", "partial", "unknown")
SCAN_STEPS = ["services", "tasks", "registry"]
MIN_SCAN_SECONDS = 1.0  # the scan screen does not flash even if everything is read instantly
# Content column: header, list and footer share the same edges; in a wide window the column is centered
CONTENT_MAX = 1000
GUTTER = 32
MISSING_SUMMARY = 3  # from this many items missing on the PC they collapse into one line
GLOW_WIDTH = 900
LANGUAGE_CODES = {"en": "EN", "ru": "RU", "uk": "UA"}
INSTALLED_VISIBLE = 15  # this many installed programs are shown at once, the rest behind the "Show all" button

# Icons from the Segoe Fluent Icons / Segoe MDL2 Assets font
ICONS = {"overview": "", "privacy": "", "system": "", "explorer": "", "context": "",
         "telemetry": "", "location": "", "performance": "", "gaming": "", "security": "",
         "globe": "", "palette": "", "shield": "", "down": "", "up": "",
         "warning": "", "check": "", "circle": "", "unknown": "", "dash": "",
         "info": "", "refresh": "", "dots": "", "snapshots": "", "folder": "", "memory": "",
         "add": "", "apps": ""}


def status_color(state):
    return {"applied": C["ok"], "partial": C["warn"], "not_applied": C["muted"], "unknown": C["warn"],
            "unavailable": C["dim"], "admin": C["warn"], "checking": C["dim"]}[state]


def service_color(state):
    return {"on": C["accent"], "off": C["muted"], "missing": C["dim"], "unknown": C["warn"]}[state]


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
    """Restarts the program as administrator. Returns the ShellExecute code (above 32 means success)."""
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, sys.argv[1:]
    else:
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        exe = pythonw if os.path.exists(pythonw) else sys.executable
        args = [os.path.abspath(sys.argv[0])] + sys.argv[1:]
    return ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, subprocess.list2cmdline(args), BASE_DIR, 1)


def collect_scan(report=lambda step: None):
    """Reads the system state. report(step) is called after each step for the scan screen."""
    result = {"services": services.scan()}
    report("services")
    result["ctx"] = engine.Context()
    report("tasks")
    result["checks"] = {t.id: engine.check(t, result["ctx"]) for t in tweaks.TWEAKS}
    report("registry")
    return result


class App:
    def __init__(self, root, instance=None):
        self.root = root
        self.instance = instance  # tray.SingleInstance: starting SimpleTool again shows this window
        self.admin = engine.is_admin()
        self.settings = load_settings()
        lang = self.settings.get("lang")
        self.lang = lang if lang in i18n.TEXTS else i18n.detect_language()
        theme.use(self.settings.get("theme", "navy"))
        self.scale = root.winfo_fpixels("1i") / 96
        self.animator = Animator(root)
        self.tweak_by_id = {t.id: t for t in tweaks.TWEAKS}
        self.page = "overview"
        self.selected = set()
        self.expanded = set()
        self.scan = None          # result of the last scan (collect_scan)
        self.scan_done = set()
        self.scan_started = 0.0
        self.busy = True
        self.message = ("checking", {})
        self.hovered = None
        self.cards, self.service_cards, self.page_cards, self.wraps = {}, {}, [], []
        self.action_buttons = []  # (button, needs administrator rights) — disabled while the window is busy
        self.snapshots = engine.list_snapshots()
        self.content_width = self.px(700)
        self.jobs = queue.Queue()
        self.acting = False       # applying, reverting or restoring is in progress: exiting is not allowed
        self.hidden = False       # the window is hidden to the tray
        self.tray = None
        self.mem = {}
        self.installed = None     # [(process, title)] of programs installed on the PC; found once in the background
        self.installed_sizes = {}  # how much memory the running ones used at the time of the search
        self.show_all_installed = False
        # Tk objects may only be deleted from the window thread, but the cyclic garbage collector runs in whichever
        # thread is allocating memory, such as the limiter thread. So only poll() collects garbage
        gc.disable()
        self.limiter = limiter.Limiter()
        self.limiter.start()
        self.setup_fonts()
        self.build()
        self.start_scan()
        self.poll()
        self.memory_tick()
        self.update_tray()
        if instance:
            instance.listen(lambda: self.post(self.show_window))
        root.bind("<Destroy>", self.on_destroy, add="+")
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        if not self.admin:
            root.after(600, self.show_admin_dialog)

    # --- Appearance ---

    def px(self, n):
        return int(round(n * self.scale))

    def setup_fonts(self):
        families = set(tkfont.families(self.root))
        icons = "Segoe Fluent Icons" if "Segoe Fluent Icons" in families else "Segoe MDL2 Assets"
        semibold = "Segoe UI Semibold" if "Segoe UI Semibold" in families else "Segoe UI"
        mono = "Cascadia Mono" if "Cascadia Mono" in families else "Consolas"
        self.fonts = {
            "brand": (semibold, 14), "title": (semibold, 20), "h2": (semibold, 11), "dialog": (semibold, 13),
            "number": (semibold, 22), "nav": ("Segoe UI", 10), "nav_active": (semibold, 10),
            "body": ("Segoe UI", 10), "small": ("Segoe UI", 9), "small_bold": (semibold, 9), "pill": (semibold, 8),
            "button": (semibold, 10), "mono": (mono, 9),
            "icon": (icons, 13), "icon_small": (icons, 10), "icon_tiny": (icons, 7), "icon_big": (icons, 20),
            "icon_scan": (icons, 26),
        }

    def setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.layout("Brand.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        style.configure("Brand.Vertical.TScrollbar", troughcolor=C["bg"], background=C["raised"], bordercolor=C["bg"],
                        lightcolor=C["raised"], darkcolor=C["raised"], arrowsize=self.px(8), gripcount=0, relief="flat")
        style.map("Brand.Vertical.TScrollbar", background=[("pressed", C["primary"]), ("active", C["border_hover"])])

    def t(self, key, **kw):
        return i18n.TEXTS[self.lang]["ui"][key].format(**kw)

    def text(self, section, key):
        return i18n.TEXTS[self.lang][section][key]

    def pointer_inside(self, widget):
        target = self.root.winfo_containing(*self.root.winfo_pointerxy())
        while target is not None:
            if target is widget:
                return True
            target = target.master
        return False

    def wrap(self, label, offset):
        """Wraps a label to the content column width minus offset."""
        self.wraps.append((label, offset))
        label.configure(wraplength=max(self.px(200), self.content_width - offset))

    def notify(self, text, color, icon):
        """A notification at the right edge of the content column."""
        right = self.column()[1]
        self.toaster.show(text, color, icon, margin=self.root.winfo_width() - (self.main.winfo_x() + right))

    def link(self, parent, text, command, font="small_bold", color=None):
        color = color or C["accent"]
        label = tk.Label(parent, text=text, font=self.fonts[font], fg=color, bg=parent.cget("bg"), cursor="hand2")
        label.bind("<Button-1>", lambda e: command())
        label.bind("<Enter>", lambda e: self.animator.color(("link", id(label)), lambda c: label.configure(fg=c),
                                                            label.cget("fg"), C["text"], 0.15))
        label.bind("<Leave>", lambda e: self.animator.color(("link", id(label)), lambda c: label.configure(fg=c),
                                                            label.cget("fg"), color, 0.2))
        return label

    # --- Window layout ---

    def build(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.title("SimpleTool")
        self.root.configure(bg=C["bg"])
        self.setup_styles()
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.build_sidebar()
        self.build_main()
        self.toaster = Toast(self.root, self.animator, self.scale, self.fonts)
        self.show_page(self.page, animate=False)

    def build_sidebar(self):
        px = self.px
        side = tk.Frame(self.root, bg=C["side"], width=px(264))
        side.grid(row=0, column=0, sticky="ns")
        side.pack_propagate(False)
        tk.Frame(side, bg=C["side_border"], width=1).pack(side="right", fill="y")

        brand = tk.Frame(side, bg=C["side"])
        brand.pack(fill="x", padx=px(20), pady=(px(22), px(26)))
        names = tk.Frame(brand, bg=C["side"])
        names.pack(side="left")
        tk.Label(names, text="SimpleTool", font=self.fonts["brand"], fg=C["side_text"], bg=C["side"], bd=0).pack(anchor="w")
        maker = tk.Frame(names, bg=C["side"])
        maker.pack(anchor="w")
        for text, font, color in ((self.t("by") + " ", "small", C["side_dim"]), ("blago", "small_bold", C["side_text"]),
                                  ("tech", "small_bold", "#5FB4FF")):
            tk.Label(maker, text=text, font=self.fonts[font], fg=color, bg=C["side"], bd=0, padx=0).pack(side="left")

        nav = tk.Frame(side, bg=C["side"])
        nav.pack(fill="x", padx=px(12))
        self.nav = {}
        for page in PAGES:
            item = tk.Frame(nav, bg=C["side"], cursor="hand2")
            item.pack(fill="x", pady=px(2))
            icon = tk.Label(item, text=ICONS[page], font=self.fonts["icon"], bg=C["side"], width=2)
            icon.pack(side="left", padx=(px(12), px(6)), pady=px(9))
            # The counter is packed before the name so a long name does not run into it
            count = tk.Label(item, text="", font=self.fonts["small"], fg=C["side_dim"], bg=C["side"])
            count.pack(side="right", padx=(px(6), px(12)))
            name = tk.Label(item, text=self.text("categories", page)[0], bg=C["side"], anchor="w")
            name.pack(side="left", fill="x", expand=True)
            parts = (item, icon, count, name)
            # Until the window is shown the item height is unknown: the indicator is placed once the item gets its size
            item.bind("<Configure>", lambda e, p=page: self.move_indicator(False) if p == self.page else None, add="+")
            for widget in parts:
                widget.bind("<Button-1>", lambda e, p=page: self.show_page(p))
                widget.bind("<Enter>", lambda e, p=page: self.hover_nav(p, True))
                widget.bind("<Leave>", lambda e, p=page, w=item: None if self.pointer_inside(w) else self.hover_nav(p, False))
            self.nav[page] = {"item": item, "icon": icon, "count": count, "name": name, "parts": parts}
        self.indicator = tk.Frame(nav, bg=CATEGORY_COLORS[self.page], width=px(3))

        bottom = tk.Frame(side, bg=C["side"])
        bottom.pack(side="bottom", fill="x", padx=px(20), pady=(0, px(20)))  # left edge lines up with the logo
        color = C["ok"] if self.admin else C["warn"]
        if C["name"] == "light":  # the sidebar is dark in every theme
            color = "#34D8A8" if self.admin else "#F0B783"
        chip = Card(bottom, self.scale, fill=mix(color, C["side"], 0.14), border=mix(color, C["side"], 0.4), radius=10, pad=3)
        chip.pack(anchor="w")
        parts = [tk.Label(chip.body, text=ICONS["shield"], font=self.fonts["icon_small"], fg=color, bg=chip.fill),
                 tk.Label(chip.body, text=self.t("admin_yes" if self.admin else "admin_no"), font=self.fonts["small_bold"],
                          fg=color, bg=chip.fill)]
        parts[0].pack(side="left", padx=(px(8), px(6)), pady=px(4))
        parts[1].pack(side="left", padx=(0, px(10)))
        if not self.admin:
            for widget in [chip, chip.body] + parts:
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda e: self.show_admin_dialog())
        # Version with a note about the test status
        version = tk.Frame(bottom, bg=C["side"])
        version.pack(anchor="w", pady=(px(12), 0))
        tk.Label(version, text="v" + VERSION, font=self.fonts["small"], fg=C["side_dim"], bg=C["side"]).pack(side="left")
        beta = Pill(version, self.fonts["pill"], self.scale, self.animator)
        beta.set(self.t("beta"), "#F0B783", animate=False)
        beta.pack(side="left", padx=(px(8), 0))
        tk.Label(bottom, text=self.t("beta_note"), font=self.fonts["small"], fg=C["side_dim"], bg=C["side"],
                 anchor="w", justify="left", wraplength=px(220)).pack(fill="x", pady=(px(6), 0))

    def build_main(self):
        px = self.px
        main = tk.Frame(self.root, bg=C["bg"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)
        self.main = main

        # Header: section color glow, title, accent bar, description, language and theme
        self.header = tk.Canvas(main, bg=C["bg"], height=px(120), highlightthickness=0, bd=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.h_glow = self.header.create_image(0, 0, anchor="nw")
        self.h_title = self.header.create_text(px(GUTTER), px(22), anchor="nw", font=self.fonts["title"], fill=C["text"])
        self.h_bar = self.header.create_image(px(GUTTER), px(66), anchor="nw",
                                              image=theme.gradient_line(px(44), px(3), C["grad_a"], C["grad_b"]))
        self.h_desc = self.header.create_text(px(GUTTER), px(80), anchor="nw", font=self.fonts["body"], fill=C["muted"])
        controls = tk.Frame(self.header, bg=C["bg"])
        # Compact buttons: theme is an icon only, language is a code; the full names are in the menus
        self.drop_button(controls, ICONS["palette"], None, self.theme_menu).pack(side="left", padx=(0, px(8)))
        self.drop_button(controls, ICONS["globe"], LANGUAGE_CODES[self.lang], self.language_menu).pack(side="left")
        self.h_controls = self.header.create_window(0, 0, window=controls, anchor="e")
        self.controls = controls
        self.links = tk.Frame(self.header, bg=C["bg"])
        self.h_links = self.header.create_window(0, 0, window=self.links, anchor="se")
        main.bind("<Configure>", self.layout)

        # Scrolling list
        holder = tk.Frame(main, bg=C["bg"])
        holder.grid(row=1, column=0, sticky="nsew")
        self.canvas = tk.Canvas(holder, bg=C["bg"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview, style="Brand.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, px(6)), pady=px(2))
        self.canvas.pack(side="left", fill="both", expand=True)
        self.list_frame = tk.Frame(self.canvas, bg=C["bg"])
        self.list_window = self.canvas.create_window(0, 0, window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", lambda e: self.update_scrollregion())
        self.canvas.bind("<Configure>", self.layout)
        self.root.bind_all("<MouseWheel>", self.on_wheel)

        # Footer: activity indicator, message, buttons
        footer = tk.Frame(main, bg=C["surface"])
        footer.grid(row=2, column=0, sticky="ew")
        tk.Frame(footer, bg=C["border"], height=1).pack(fill="x")
        inner = tk.Frame(footer, bg=C["surface"])
        inner.pack(fill="x", padx=px(GUTTER), pady=px(14))
        self.footer_inner = inner
        self.apply_button = GradientButton(inner, self.t("apply"), self.apply_selected, self.fonts["button"], self.scale,
                                           self.animator)
        self.apply_button.pack(side="right")
        self.revert_button = GradientButton(inner, self.t("revert"), self.revert_selected, self.fonts["button"], self.scale,
                                            self.animator, primary=False)
        self.revert_button.pack(side="right", padx=(0, px(10)))
        self.spinner = Spinner(inner, px(18), self.scale)
        self.message_label = tk.Label(inner, font=self.fonts["body"], fg=C["muted"], bg=C["surface"], anchor="w",
                                      justify="left", wraplength=px(440))
        self.message_label.pack(side="left", fill="x", expand=True)

    def drop_button(self, parent, icon, label, build_menu):
        """A button with a drop-down menu (theme, language)."""
        px = self.px
        card = Card(parent, self.scale, fill=C["surface"], border=C["border"], radius=10, pad=3)
        parts = [tk.Label(card.body, text=icon, font=self.fonts["icon_small"], fg=C["accent"], bg=card.fill)]
        parts[0].pack(side="left", padx=(px(10), px(6)), pady=px(5))
        if label:
            parts.append(tk.Label(card.body, text=label, font=self.fonts["small_bold"], fg=C["text"], bg=card.fill))
            parts[-1].pack(side="left", padx=(0, px(2)))
        parts.append(tk.Label(card.body, text=ICONS["down"], font=self.fonts["icon_tiny"], fg=C["muted"], bg=card.fill))
        parts[-1].pack(side="left", padx=(px(4), px(10)))

        def popup(event):
            menu = build_menu()
            menu.tk_popup(card.winfo_rootx(), card.winfo_rooty() + card.winfo_height() + px(4))

        def border(color):
            self.animator.color(("drop", id(card)), card.set_border, card.border, color, 0.18)

        for widget in [card, card.body] + parts:
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", popup)
            widget.bind("<Enter>", lambda e: border(C["accent"]))
            widget.bind("<Leave>", lambda e: None if self.pointer_inside(card) else border(C["border"]))
        return card

    def popup_menu(self, title, items, current, command):
        menu = tk.Menu(self.root, tearoff=False, bg=C["surface"], fg=C["text"], activebackground=C["primary"],
                       activeforeground="#FFFFFF", disabledforeground=C["dim"], selectcolor=C["accent"],
                       font=self.fonts["body"], bd=0)
        menu.add_command(label=title, state="disabled")
        menu.add_separator()
        variable = tk.StringVar(menu, value=current)
        for value, label in items:
            menu.add_radiobutton(label=label, value=value, variable=variable, command=lambda v=value: command(v))
        menu.variable = variable  # keep a reference so the garbage collector does not collect the variable
        return menu

    def language_menu(self):
        return self.popup_menu(self.t("language"), i18n.LANGUAGES, self.lang, self.set_language)

    def theme_menu(self):
        items = [(name, self.text("themes", name)) for name in theme.THEMES]
        return self.popup_menu(self.t("theme"), items, C["name"], self.set_theme)

    def column(self):
        """Left and right edges of the content column in main area coordinates."""
        width = self.main.winfo_width()
        gutter = self.px(GUTTER)
        content = max(self.px(320), min(width - 2 * gutter, self.px(CONTENT_MAX)))
        left = max(gutter, (width - content) // 2)
        return left, left + content

    def update_scrollregion(self):
        # The scroll region starts at zero, not at the content bbox: otherwise Tk shifts the view
        # and eats the column margin
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), self.list_frame.winfo_height()))

    def layout(self, event=None):
        """Aligns the header, list and footer to the content column."""
        width = self.main.winfo_width()
        if width <= 1:
            return
        left, right = self.column()
        self.content_width = right - left
        self.canvas.coords(self.list_window, left, 0)
        self.canvas.itemconfigure(self.list_window, width=self.content_width)
        self.update_scrollregion()
        for label, offset in self.wraps:
            try:
                label.configure(wraplength=max(self.px(200), self.content_width - offset))
            except tk.TclError:
                pass
        self.footer_inner.pack_configure(padx=(left, width - right))
        self.layout_header()

    def layout_header(self):
        px = self.px
        if self.header.winfo_width() <= 1:
            return
        left, right = self.column()
        self.header.coords(self.h_glow, left + px(140) - px(GLOW_WIDTH) // 2, 0)  # glow center is above the title
        self.header.coords(self.h_title, left, px(22))
        title = self.header.bbox(self.h_title)
        self.header.coords(self.h_bar, left + 1, title[3] + px(6))
        self.header.coords(self.h_desc, left, title[3] + px(20))
        # Theme and language buttons are centered on the title line
        self.header.coords(self.h_controls, right, (title[1] + title[3]) / 2)
        # The description sits below the buttons, so it shares its line only with the links on the right
        links = self.links.winfo_reqwidth()
        self.header.itemconfigure(self.h_desc, width=max(px(240), right - left - links - px(24)))
        bottom = self.header.bbox(self.h_desc)[3]
        self.header.coords(self.h_links, right, bottom + px(1))
        height = bottom + px(18)
        if int(float(self.header.cget("height"))) != height:
            self.header.configure(height=height)

    # --- Navigation ---

    def hover_nav(self, page, inside):
        self.hovered_nav = page if inside else None
        if page != self.page:
            parts = self.nav[page]["parts"]
            target = C["side_hover"] if inside else C["side"]
            self.animator.color(("nav", page), lambda c: [w.configure(bg=c) for w in parts],
                                parts[0].cget("bg"), target, 0.16)

    def paint_nav(self):
        for page, widgets in self.nav.items():
            active = page == self.page
            self.animator.cancel(("nav", page))
            for widget in widgets["parts"]:
                widget.configure(bg=C["side_active"] if active else C["side"])
            widgets["icon"].configure(fg=CATEGORY_COLORS[page] if active else C["side_muted"])
            widgets["name"].configure(fg=C["side_text"] if active else C["side_muted"],
                                      font=self.fonts["nav_active" if active else "nav"])
        self.update_nav_counts()

    def update_nav_counts(self):
        # The memory limiter shows the number of programs it keeps within limits instead of a counter
        active = [r for r in self.limiter.snapshot()["config"]["rules"] if r["enabled"]] if self.limiter.active() else []
        self.nav["memory"]["count"].configure(text=str(len(active)) if active else "", fg=C["side_muted"])
        if not self.scan:
            for page, widgets in self.nav.items():
                if page != "memory":
                    widgets["count"].configure(text="")
            return
        for page, widgets in self.nav.items():
            if page == "memory":
                continue
            if page == "overview":
                problems = sum(self.unknown_reasons().values())
                widgets["count"].configure(text="!" if problems else "", fg=C["warn"] if C["name"] != "light" else "#F0B783")
                continue
            if page == "snapshots":
                widgets["count"].configure(text=str(len(self.snapshots)) if self.snapshots else "", fg=C["side_dim"])
                continue
            # The counter shows the real system state, even if a tweak cannot be changed without rights
            statuses = self.status_map()
            items = [t for t in tweaks.TWEAKS if t.category == page]
            applied = sum(statuses.get(t.id) == "applied" for t in items)
            widgets["count"].configure(text=f"{applied}/{len(items)}", fg=C["side_dim"])

    def move_indicator(self, animate=True):
        px = self.px
        item = self.nav[self.page]["item"]
        if animate:
            self.root.update_idletasks()
        y, height = item.winfo_y() + px(8), max(item.winfo_height() - px(16), px(12))
        color = CATEGORY_COLORS[self.page]
        info = self.indicator.place_info()
        self.indicator.lift()
        if animate and info:
            start_y, start_h, start_color = float(info["y"]), float(info["height"]), self.indicator.cget("bg")

            def step(t):
                self.indicator.place_configure(y=start_y + (y - start_y) * t, height=start_h + (height - start_h) * t)
                self.indicator.configure(bg=lerp(start_color, color, t))

            self.animator.animate("indicator", 0.32, step)
        else:
            self.indicator.configure(bg=color)
            self.indicator.place(x=0, y=y, width=px(3), height=height)

    def show_page(self, page, animate=True):
        self.page = page
        name, desc = self.text("categories", page)
        self.header.itemconfigure(self.h_title, text=name)
        self.header.itemconfigure(self.h_desc, text=desc)
        strength = 0.18 if C["name"] == "light" else 0.26
        self.header.itemconfigure(self.h_glow, image=theme.glow(self.px(GLOW_WIDTH), self.px(190), CATEGORY_COLORS[page],
                                                                C["bg"], strength))
        for widget in self.links.winfo_children():
            widget.destroy()
        if page == "overview":
            self.link(self.links, self.t("rescan"), self.rescan).pack(side="left")
        elif page == "snapshots":
            self.link(self.links, self.t("snap_folder"), lambda: os.startfile(engine.snapshots_dir())).pack(side="left")
        elif page == "memory":
            self.link(self.links, self.t("mem_pick"), self.pick_running).pack(side="left")
        else:
            for key, action in (("select_all", self.select_all), ("clear", self.clear_selection)):
                self.link(self.links, self.t(key), action).pack(side="left", padx=(self.px(16), 0))
        if animate:
            for item, color in ((self.h_title, C["text"]), (self.h_desc, C["muted"])):
                self.animator.color(("header", item), lambda c, i=item: self.header.itemconfigure(i, fill=c),
                                    C["bg"], color, 0.35)

        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self.cards, self.service_cards, self.page_cards, self.wraps = {}, {}, [], []
        self.action_buttons = []
        self.mem = {}
        if page == "overview":
            self.build_overview()
        elif page == "snapshots":
            self.build_snapshots_page()
        elif page == "memory":
            self.build_memory_page()
        else:
            self.build_tweak_page(page)
        tk.Frame(self.list_frame, bg=C["bg"], height=self.px(12)).pack()
        self.canvas.yview_moveto(0)
        self.paint_nav()
        self.root.after_idle(self.layout)
        self.root.after_idle(lambda: self.move_indicator(animate))
        self.update_footer()
        if animate:
            self.reveal()

    def reveal(self):
        """The page cards fade in one after another."""
        for i, card in enumerate(self.page_cards):
            delay = min(i, 14) * 0.035
            fade_in(self.animator, ("fade", id(card)), descendants(card), delay=delay)
            self.animator.color(("cardborder", id(card)), card.set_border, C["bg"], card.border, 0.4, delay=delay)

    # --- System overview ---

    def build_overview(self):
        if self.scan is None:
            self.build_scan_panel()
            return
        self.build_summary()
        self.build_callout()
        for group in services.GROUPS:
            self.section_head(ICONS[group], self.text("groups", group))
            for svc_group, name, tweak_id in services.SERVICES:
                if svc_group == group:
                    self.service_cards[name] = self.build_service_card(name, tweak_id)

    def section_head(self, icon, text):
        """A heading for a group of cards."""
        head = tk.Frame(self.list_frame, bg=C["bg"])
        head.pack(fill="x", padx=(self.px(18), 0), pady=(self.px(18), self.px(8)))
        tk.Label(head, text=icon, font=self.fonts["icon_small"], fg=C["accent"], bg=C["bg"]).pack(side="left")
        tk.Label(head, text=text, font=self.fonts["small_bold"], fg=C["muted"], bg=C["bg"]).pack(
            side="left", padx=(self.px(8), 0))

    def build_scan_panel(self):
        px = self.px
        card = Card(self.list_frame, self.scale, radius=16, pad=8)
        card.pack(fill="x")
        body = card.body
        rings = ScanRings(body, px(150), self.scale, ICONS["overview"], self.fonts["icon_scan"])
        rings.pack(pady=(px(18), px(6)))
        rings.start()
        tk.Label(body, text=self.t("scan_title"), font=self.fonts["dialog"], fg=C["text"], bg=card.fill).pack()
        tk.Label(body, text=self.t("scan_text"), font=self.fonts["small"], fg=C["muted"], bg=card.fill,
                 wraplength=px(440), justify="center").pack(pady=(px(4), px(14)))
        steps = tk.Frame(body, bg=card.fill)
        steps.pack(pady=(0, px(22)))
        self.scan_rows = {}
        for step in SCAN_STEPS:
            row = tk.Frame(steps, bg=card.fill)
            row.pack(anchor="w", pady=px(3))
            done = step in self.scan_done
            glyph = tk.Label(row, text=ICONS["check"] if done else ICONS["dots"], font=self.fonts["icon_small"],
                             fg=C["ok"] if done else C["dim"], bg=card.fill, width=2)
            glyph.pack(side="left")
            label = tk.Label(row, text=self.t("scan_" + step), font=self.fonts["body"],
                             fg=C["text"] if done else C["muted"], bg=card.fill)
            label.pack(side="left", padx=(px(6), 0))
            self.scan_rows[step] = (glyph, label)
        self.page_cards = [card]

    def build_summary(self):
        px = self.px
        infos = list(self.scan["services"].values())
        counts = collections.Counter(info.state for info in infos)
        unknown = sum(self.unknown_reasons().values())  # the same number as in the tips block below
        applied = sum(status == "applied" for status in self.status_map().values())
        tiles = [("summary_on", counts["on"], None, C["accent"], ICONS["check"]),
                 ("summary_off", counts["off"], None, C["muted"], ICONS["circle"]),
                 ("summary_missing", counts["missing"], None, C["dim"], ICONS["dash"]),
                 ("summary_unknown", unknown, None, C["warn"] if unknown else C["dim"], ICONS["unknown"]),
                 ("summary_tweaks", applied, len(tweaks.TWEAKS), C["ok"], ICONS["overview"])]
        row = tk.Frame(self.list_frame, bg=C["bg"])
        row.pack(fill="x", pady=(0, px(4)))
        for i, (key, value, total, color, icon) in enumerate(tiles):
            # Tiles sit in even columns of equal width, gaps are separate narrow columns between them:
            # padding inside a column would make every tile except the first narrower
            row.columnconfigure(2 * i, weight=1, uniform="tile")
            if i:
                row.columnconfigure(2 * i - 1, minsize=px(8))
            card = Card(row, self.scale, radius=14, pad=6)
            card.grid(row=0, column=2 * i, sticky="nsew")
            body = card.body
            top = tk.Frame(body, bg=card.fill)
            top.pack(fill="x", padx=px(12), pady=(px(8), 0))
            number = tk.Label(top, text="0", font=self.fonts["number"], fg=color, bg=card.fill)
            number.pack(side="left")
            glyph = tk.Label(top, text=icon, font=self.fonts["icon_small"], fg=mix(color, card.fill, 0.7), bg=card.fill)
            glyph.pack(side="right", anchor="n", pady=(px(6), 0))
            # bd and padx are 0: then the wrap width matches the text area width and the line is not clipped
            caption = tk.Label(body, text=self.t(key), font=self.fonts["small"], fg=C["muted"], bg=card.fill,
                               anchor="w", justify="left", wraplength=px(110), bd=0, padx=0)
            caption.pack(fill="x", padx=px(12), pady=(0, px(10)))

            def fit_tile(event, caption=caption, glyph=glyph, number=number):
                caption.configure(wraplength=max(px(60), event.width - px(24)))
                # On a narrow tile the icon hides so it does not overlap the number
                if event.width < px(118):
                    glyph.pack_forget()
                elif not glyph.winfo_ismapped():
                    glyph.pack(side="right", anchor="n", pady=(px(6), 0), before=number)

            body.bind("<Configure>", fit_tile)

            def count_up(t, label=number, value=value, total=total):
                shown = round(value * t)
                label.configure(text=f"{shown}/{total}" if total else str(shown))

            self.animator.animate(("count", key), 0.9, count_up, delay=0.15 + i * 0.07)
            self.page_cards.append(card)

    def unknown_reasons(self):
        """Reasons why something could not be checked, and how often each one occurred."""
        reasons = collections.Counter()
        if not self.scan:
            return reasons
        for info in self.scan["services"].values():
            if info.state == "unknown" and info.reason:
                reasons[info.reason] += 1
        for status, rows in self.scan["checks"].values():
            for reason in {reason for _, _, reason in rows if reason and reason != "missing"}:
                reasons[reason] += 1
        return reasons

    def build_callout(self):
        px = self.px
        reasons = self.unknown_reasons()
        if not reasons:
            return
        card = Card(self.list_frame, self.scale, border=mix(C["warn"], C["surface"], 0.6), radius=14, pad=6)
        card.pack(fill="x", pady=(px(10), 0))
        body = card.body
        head = tk.Frame(body, bg=card.fill)
        head.pack(fill="x", padx=px(12), pady=(px(10), 0))
        tk.Label(head, text=ICONS["warning"], font=self.fonts["icon"], fg=C["warn"], bg=card.fill).pack(side="left")
        tk.Label(head, text=self.t("unknown_title"), font=self.fonts["h2"], fg=C["text"], bg=card.fill).pack(
            side="left", padx=(px(10), 0))
        intro = tk.Label(body, text=self.t("unknown_intro"), font=self.fonts["small"], fg=C["muted"], bg=card.fill,
                         anchor="w", justify="left")
        intro.pack(fill="x", padx=(px(40), px(12)), pady=(px(2), px(6)))
        self.wrap(intro, px(72))
        for reason, count in reasons.most_common():
            problem, tip = self.text("reasons", reason)
            line = tk.Label(body, text=f"{problem}  ×{count}", font=self.fonts["small_bold"], fg=C["text"], bg=card.fill,
                            anchor="w", justify="left")
            line.pack(fill="x", padx=(px(40), px(12)), pady=(px(4), 0))
            hint = tk.Label(body, text=tip, font=self.fonts["small"], fg=C["muted"], bg=card.fill, anchor="w",
                            justify="left")
            hint.pack(fill="x", padx=(px(40), px(12)))
            self.wrap(line, px(72))
            self.wrap(hint, px(72))
        buttons = tk.Frame(body, bg=card.fill)
        buttons.pack(fill="x", padx=(px(40), px(12)), pady=(px(12), px(12)))
        if "access_denied" in reasons and not self.admin:
            GradientButton(buttons, self.t("admin_restart"), self.restart_as_admin, self.fonts["button"], self.scale,
                           self.animator, pad=(16, 6)).pack(side="left", padx=(0, px(8)))
        GradientButton(buttons, self.t("rescan"), self.rescan, self.fonts["button"], self.scale, self.animator,
                       primary=False, pad=(16, 6)).pack(side="left")
        self.page_cards.append(card)

    def service_meta(self, info):
        if info.state == "missing":
            return self.t("service_name", name=info.name)
        start = ("start_2d" if info.start == 2 and info.delayed else
                 f"start_{info.start}" if info.start in (0, 1, 2, 3, 4) else "start_unknown")
        running = f"run_{info.running}" if info.running in range(1, 8) else "run_unknown"
        return f"{self.t('startup', start=self.t(start))}  ·  {self.t('now', state=self.t(running))}"

    def build_service_card(self, name, tweak_id):
        px = self.px
        info = self.scan["services"][name]
        title, details = self.text("services", name)
        card = Card(self.list_frame, self.scale)
        card.pack(fill="x", pady=(0, px(10)))
        body = card.body
        body.columnconfigure(0, weight=1)
        title_label = tk.Label(body, text=title, font=self.fonts["h2"], bg=card.fill, anchor="w", justify="left",
                               fg=C["text"] if info.state != "missing" else C["dim"])
        title_label.grid(row=0, column=0, sticky="ew", padx=(px(12), 0), pady=(px(7), 0))
        meta = tk.Label(body, text=self.service_meta(info), font=self.fonts["small"], fg=C["muted"], bg=card.fill,
                        anchor="w", justify="left")
        meta.grid(row=1, column=0, sticky="ew", padx=(px(12), 0), pady=(px(1), 0))
        pill = Pill(body, self.fonts["pill"], self.scale, self.animator)
        pill.grid(row=0, column=1, sticky="ne", padx=px(12), pady=(px(8), 0))  # on the title line
        pill.set(self.t("service_" + info.state), service_color(info.state), animate=False)
        self.wrap(title_label, px(172))
        self.wrap(meta, px(172))
        widgets = {"card": card}
        self.details_toggle(body, widgets, ("s", name), lambda holder: self.build_service_details(holder, info, details,
                                                                                                   tweak_id), indent=12)
        self.page_cards.append(card)
        return widgets

    def build_service_details(self, holder, info, details, tweak_id):
        px = self.px
        bg = holder.cget("bg")
        inner = tk.Frame(holder, bg=bg)
        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=(px(12), px(12)), pady=(0, px(10)))
        text = tk.Label(inner, text=details, font=self.fonts["body"], fg=C["text"], bg=bg, anchor="w", justify="left")
        text.pack(fill="x", padx=(px(12), px(16)))
        self.wrap(text, px(62))
        tk.Label(inner, text=self.t("service_name", name=info.name), font=self.fonts["mono"], fg=C["dim"], bg=bg,
                 anchor="w").pack(fill="x", padx=(px(12), px(16)), pady=(px(8), 0))
        if info.reason:
            problem, tip = self.text("reasons", info.reason)
            hint = tk.Label(inner, text=f"{problem} {tip}", font=self.fonts["small"], fg=C["warn"], bg=bg, anchor="w",
                            justify="left")
            hint.pack(fill="x", padx=(px(12), px(16)), pady=(px(6), 0))
            self.wrap(hint, px(62))
        if tweak_id:
            name = self.text("tweaks", tweak_id)[0]
            self.link(inner, self.t("managed_by", name=name), lambda: self.open_tweak(tweak_id)).pack(
                anchor="w", padx=(px(12), px(16)), pady=(px(8), 0))
        tk.Frame(inner, bg=bg, height=px(10)).pack()
        return inner

    def open_tweak(self, tweak_id):
        """Goes to a tweak and expands its details."""
        self.expanded.add(("t", tweak_id))
        self.show_page(self.tweak_by_id[tweak_id].category)

        def scroll():
            card = self.cards.get(tweak_id, {}).get("card")
            total = self.list_frame.winfo_height()
            if card and total > 0:
                self.canvas.yview_moveto(max(0.0, (card.winfo_y() - self.px(8)) / total))
                self.animator.color(("flash", tweak_id), card.set_border, C["accent"], C["border"], 1.2, delay=0.3)

        self.root.after(80, scroll)

    # --- System snapshots ---

    def format_date(self, iso):
        try:
            moment = datetime.datetime.fromisoformat(iso)
        except (TypeError, ValueError):
            return iso or "?"
        return f"{moment.day} {moment:%b %Y, %H:%M}" if self.lang == "en" else f"{moment:%d.%m.%Y, %H:%M}"

    def build_snapshots_page(self):
        px = self.px
        card = Card(self.list_frame, self.scale, radius=14, pad=6)
        card.pack(fill="x", pady=(0, px(12)))
        body = card.body
        intro = tk.Label(body, text=self.t("snap_intro"), font=self.fonts["body"], fg=C["text"], bg=card.fill,
                         anchor="w", justify="left")
        intro.pack(fill="x", padx=px(12), pady=(px(12), 0))
        self.wrap(intro, px(62))
        buttons = tk.Frame(body, bg=card.fill)
        buttons.pack(fill="x", padx=px(12), pady=(px(14), 0))
        take = GradientButton(buttons, self.t("snap_create"), self.take_manual_snapshot, self.fonts["button"],
                              self.scale, self.animator, pad=(16, 7))
        take.pack(side="left")
        point = GradientButton(buttons, self.t("snap_restore_point"), self.create_restore_point, self.fonts["button"],
                               self.scale, self.animator, primary=False, pad=(16, 7))
        point.pack(side="left", padx=(px(10), 0))
        self.action_buttons += [(take, False), (point, True)]
        hint = tk.Label(body, text=self.t("snap_rp_hint"), font=self.fonts["small"], fg=C["muted"], bg=card.fill,
                        anchor="w", justify="left")
        hint.pack(fill="x", padx=px(12), pady=(px(12), px(12) if self.admin else 0))
        self.wrap(hint, px(62))
        if not self.admin:
            note = tk.Label(body, text=self.t("snap_admin"), font=self.fonts["small_bold"], fg=C["warn"], bg=card.fill,
                            anchor="w", justify="left")
            note.pack(fill="x", padx=px(12), pady=(px(8), px(12)))
            self.wrap(note, px(62))
        self.page_cards.append(card)
        if not self.snapshots:
            empty = tk.Label(self.list_frame, text=self.t("snap_empty" if self.admin else "snap_empty_limited"),
                             font=self.fonts["body"], fg=C["muted"], bg=C["bg"], anchor="w", justify="left")
            empty.pack(fill="x", padx=px(18), pady=px(8))
            self.wrap(empty, px(36))
        for path, data in self.snapshots:
            self.build_snapshot_card(path, data)

    def build_snapshot_card(self, path, data):
        px = self.px
        kind = data.get("kind", "manual")
        entries = data.get("tweaks", {})
        applied = sum(entry.get("status") == "applied" for entry in entries.values())
        saved = sum(len(entry.get("ops", {})) for entry in entries.values())
        initial = kind == "initial"
        color = C["accent"] if initial else CATEGORY_COLORS["snapshots"]
        card = Card(self.list_frame, self.scale, border=mix(C["accent"], C["surface"], 0.55) if initial else None)
        card.pack(fill="x", pady=(0, px(10)))
        body = card.body
        body.columnconfigure(1, weight=1)
        badge = Card(body, self.scale, fill=mix(color, card.fill, 0.14), border=mix(color, card.fill, 0.35), radius=12, pad=3)
        badge.grid(row=0, column=0, rowspan=2, sticky="nw", padx=px(12), pady=px(10))
        tk.Label(badge.body, text=ICONS["snapshots"], font=self.fonts["icon"], fg=color, bg=badge.fill).pack(
            padx=px(7), pady=px(5))
        head = tk.Frame(body, bg=card.fill)
        head.grid(row=0, column=1, sticky="ew", pady=(px(10), 0))
        tk.Label(head, text=self.format_date(data.get("created")), font=self.fonts["h2"], fg=C["text"],
                 bg=card.fill).pack(side="left")
        pill = Pill(head, self.fonts["pill"], self.scale, self.animator)
        pill.set(self.t("kind_" + kind) if "kind_" + kind in i18n.TEXTS[self.lang]["ui"] else kind, color, animate=False)
        pill.pack(side="left", padx=(px(10), 0))
        summary = self.t("snap_summary", applied=applied, total=len(entries), ops=saved)
        info = tk.Label(body, text=(self.t("snap_initial_note") + "\n" + summary) if initial else summary,
                        font=self.fonts["small"], fg=C["muted"], bg=card.fill, anchor="w", justify="left")
        info.grid(row=1, column=1, sticky="ew", pady=(px(3), px(10)))
        self.wrap(info, px(312))
        actions = tk.Frame(body, bg=card.fill)
        actions.grid(row=0, column=2, rowspan=2, sticky="e", padx=px(12))
        restore = GradientButton(actions, self.t("snap_restore"), lambda: self.confirm_restore(data), self.fonts["button"],
                                 self.scale, self.animator, primary=False, pad=(14, 6))
        restore.pack(side="left")
        self.action_buttons.append((restore, True))
        if not initial:
            self.link(actions, self.t("snap_delete"), lambda: self.delete_snapshot(path), font="small",
                      color=C["dim"]).pack(side="left", padx=(px(12), 0))
        self.page_cards.append(card)

    def status_map(self):
        return {i: check[0] for i, check in self.scan["checks"].items()} if self.scan else {}

    def take_manual_snapshot(self):
        ctx, statuses = self.scan and self.scan.get("ctx"), self.status_map()

        def done(result):
            self.message = None
            if isinstance(result, Exception):
                self.notify(self.t("snap_failed"), C["warn"], ICONS["warning"])
                self.show_errors([str(result)])
            else:
                self.notify(self.t("snap_saved"), C["ok"], ICONS["check"])
            self.snapshots = engine.list_snapshots()
            self.refresh_view()

        self.run_action("snap_saving", lambda: engine.take_snapshot(tweaks.TWEAKS, ctx or engine.Context(), "manual",
                                                                    statuses, VERSION), done)

    def create_restore_point(self):
        def done(result):
            self.message = None
            ok, detail = (False, str(result)) if isinstance(result, Exception) else result
            if ok:
                self.notify(self.t("rp_done"), C["ok"], ICONS["check"])
            else:
                self.notify(self.t("rp_failed"), C["warn"], ICONS["warning"])
                self.show_errors([self.t("rp_failed") + (f"\n{detail}" if detail else "")])
            self.update_footer()

        self.run_action("rp_working", engine.create_restore_point, done)

    def confirm_restore(self, data):
        date = self.format_date(data.get("created"))
        win, content = self.dialog(self.t("snap_confirm_title"), ICONS["snapshots"], CATEGORY_COLORS["snapshots"],
                                   self.t("snap_confirm_title"), self.t("snap_confirm_text", date=date))

        def go():
            win.destroy()
            self.restore_snapshot(data, date)

        GradientButton(content, self.t("snap_confirm_ok"), go, self.fonts["button"], self.scale, self.animator,
                       pad=(18, 8)).pack(side="right")
        GradientButton(content, self.t("cancel"), win.destroy, self.fonts["button"], self.scale, self.animator,
                       primary=False, pad=(18, 8)).pack(side="right", padx=(0, self.px(10)))
        self.present(win)

    def restore_snapshot(self, data, date):
        statuses, failed = self.status_map(), self.t("snap_failed")

        def work():
            ctx = engine.Context()
            errors = []
            try:
                engine.take_snapshot(tweaks.TWEAKS, ctx, "before_restore", statuses, VERSION)
            except OSError as exc:
                errors.append(f"{failed} {exc}")
            errors += engine.restore_snapshot(tweaks.TWEAKS, data, ctx)
            engine.notify_shell()
            scan = collect_scan()
            # Backups of reverted tweaks no longer describe their original state
            engine.forget_backups({i for i, (status, _) in scan["checks"].items() if status in REVERTIBLE})
            return errors, scan

        def done(result):
            self.selected.clear()
            if isinstance(result, Exception):
                errors = [str(result)]
            else:
                errors, self.scan = result
            self.snapshots = engine.list_snapshots()
            self.message = ("snap_restored", {"date": date})
            self.refresh_view()
            if errors:
                self.notify(self.t("errors_title"), C["warn"], ICONS["warning"])
                self.show_errors(errors)
            else:
                self.notify(self.t("snap_restored", date=date), C["ok"], ICONS["check"])

        self.run_action("snap_working", work, done)

    def delete_snapshot(self, path):
        if self.busy:
            return
        try:
            os.remove(path)
        except OSError as exc:
            self.show_errors([str(exc)])
        self.snapshots = engine.list_snapshots()
        self.refresh_view()

    # --- Memory limiter ---

    def size_text(self, size, digits=1):
        """A size for people: "640 MB", "1.4 GB"."""
        mb = size / limiter.MB
        if mb < 1000:
            return self.t("mem_size_mb", n=round(mb))
        gb = f"{mb / 1024:.{digits}f}".rstrip("0").rstrip(".")
        return self.t("mem_size_gb", n=gb if self.lang == "en" else gb.replace(".", ","))

    def limit_text(self, mb):
        return self.size_text(mb * limiter.MB, digits=2)

    def build_memory_page(self):
        px = self.px
        config = self.limiter.snapshot()["config"]
        color = CATEGORY_COLORS["memory"]
        # Main switch, check interval and how much memory has been freed
        card = Card(self.list_frame, self.scale, radius=14, pad=6)
        card.pack(fill="x", pady=(0, px(10)))
        body = card.body
        body.columnconfigure(1, weight=1)
        badge = Card(body, self.scale, fill=mix(color, card.fill, 0.14), border=mix(color, card.fill, 0.35), radius=12,
                     pad=3)
        badge.grid(row=0, column=0, rowspan=2, sticky="nw", padx=px(12), pady=(px(12), 0))
        tk.Label(badge.body, text=ICONS["memory"], font=self.fonts["icon"], fg=color, bg=badge.fill).pack(
            padx=px(7), pady=px(5))
        title = tk.Label(body, font=self.fonts["h2"], fg=C["text"], bg=card.fill, anchor="w")
        title.grid(row=0, column=1, sticky="ew", pady=(px(12), 0))
        text = tk.Label(body, font=self.fonts["small"], fg=C["muted"], bg=card.fill, anchor="w", justify="left")
        text.grid(row=1, column=1, sticky="ew", pady=(px(2), 0))
        self.wrap(text, px(150))
        toggle = Toggle(body, self.scale, self.animator, on=config["enabled"], command=self.set_limiter_enabled)
        toggle.grid(row=0, column=2, sticky="ne", padx=px(14), pady=(px(14), 0))
        tk.Frame(body, bg=C["border"], height=1).grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, px(14)),
                                                     pady=px(12))
        row = tk.Frame(body, bg=card.fill)
        row.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(0, px(14)), pady=(0, px(12)))
        tk.Label(row, text=self.t("mem_interval"), font=self.fonts["small"], fg=C["muted"], bg=card.fill).pack(
            side="left")
        Segmented(row, [(n, self.t("mem_seconds", n=n)) for n in limiter.INTERVALS], config["interval"],
                  self.fonts["small_bold"], self.scale, self.animator, command=self.set_limiter_interval).pack(
            side="left", padx=(px(10), 0))
        freed = tk.Label(row, font=self.fonts["small_bold"], fg=C["ok"], bg=card.fill)
        freed.pack(side="right")
        tk.Label(row, text=self.t("mem_freed"), font=self.fonts["small"], fg=C["muted"], bg=card.fill).pack(
            side="right", padx=(0, px(8)))
        self.mem = {"title": title, "text": text, "toggle": toggle, "freed": freed, "rules": {}}
        self.page_cards.append(card)

        # How it works
        how = Card(self.list_frame, self.scale)
        how.pack(fill="x")
        head = tk.Frame(how.body, bg=how.fill)
        head.grid(row=0, column=0, sticky="w", padx=px(12), pady=(px(9), 0))
        tk.Label(head, text=ICONS["info"], font=self.fonts["icon_small"], fg=C["accent"], bg=how.fill).pack(side="left")
        tk.Label(head, text=self.t("mem_how_title"), font=self.fonts["h2"], fg=C["text"], bg=how.fill).pack(
            side="left", padx=(px(8), 0))
        how.body.columnconfigure(0, weight=1)
        self.mem["how"] = {"card": how}
        self.details_toggle(how.body, self.mem["how"], ("m", "how"), self.build_memory_how, indent=12)
        self.page_cards.append(how)

        # Programs being limited
        self.section_head(ICONS["apps"], self.t("mem_apps"))
        if not config["rules"]:
            empty = tk.Label(self.list_frame, text=self.t("mem_empty"), font=self.fonts["body"], fg=C["muted"],
                             bg=C["bg"], anchor="w", justify="left")
            empty.pack(fill="x", padx=px(18), pady=(0, px(4)))
            self.wrap(empty, px(36))
        for rule in config["rules"]:
            self.mem["rules"][rule["name"]] = self.build_rule_card(rule)

        # Add: programs installed on this PC and a picker of running programs
        self.section_head(ICONS["add"], self.t("mem_add"))
        added = {rule["name"] for rule in config["rules"]}
        choices = [item for item in self.installed or [] if item[0] not in added]
        if self.installed is None:
            key = "mem_installed_loading"
            self.load_installed()
        else:
            key = "mem_installed_hint" if choices else "mem_installed_empty"
        hint = tk.Label(self.list_frame, text=self.t(key), font=self.fonts["small"], fg=C["muted"], bg=C["bg"],
                        anchor="w", justify="left")
        hint.pack(fill="x", padx=px(18), pady=(0, px(10)))
        self.wrap(hint, px(36))
        flow = Flow(self.list_frame, px(8), px(8))
        flow.pack(fill="x")
        # Running ones first, heaviest at the front; the rest alphabetically
        choices.sort(key=lambda item: (-self.installed_sizes.get(item[0], 0), item[1].lower()))
        visible = choices if self.show_all_installed else choices[:INSTALLED_VISIBLE]
        for name, title in visible:
            size = self.installed_sizes.get(name)
            flow.add(self.chip(flow, title if len(title) <= 34 else title[:33] + "…",
                               lambda n=name, t=title: self.add_rule(n, limiter.default_limit(n), t), ICONS["add"],
                               note=self.size_text(size) if size else None))
        if len(choices) > INSTALLED_VISIBLE:
            label = self.t("mem_show_less") if self.show_all_installed else self.t("mem_show_all", n=len(choices))
            flow.add(self.chip(flow, label, self.toggle_installed, ICONS["up" if self.show_all_installed else "down"]))
        flow.add(self.chip(flow, self.t("mem_pick"), self.pick_running, ICONS["apps"], accent=True))
        self.update_memory_view(animate=False)

    def load_installed(self):
        """Finds installed programs in the background: on sleeping drives checking files can take seconds."""
        if getattr(self, "installed_loading", False):
            return
        self.installed_loading = True

        def work():
            sizes = {name: size for name, _, size in limiter.running_programs()}
            return programs.installed(), sizes

        def done(result):
            self.installed_loading = False
            self.installed, self.installed_sizes = ([], {}) if isinstance(result, Exception) else result
            if self.page == "memory":
                self.rebuild_memory()

        self.run_job(work, done)

    def toggle_installed(self):
        self.show_all_installed = not self.show_all_installed
        self.rebuild_memory()

    def program_title(self, name):
        return dict(self.installed or []).get(name)

    def build_memory_how(self, holder):
        px = self.px
        bg = holder.cget("bg")
        inner = tk.Frame(holder, bg=bg)
        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=px(12), pady=(0, px(10)))
        text = tk.Label(inner, text=self.t("mem_how"), font=self.fonts["body"], fg=C["text"], bg=bg, anchor="w",
                        justify="left")
        text.pack(fill="x", padx=(px(12), px(16)))
        self.wrap(text, px(62))
        tk.Frame(inner, bg=bg, height=px(12)).pack()
        return inner

    def chip(self, parent, text, command, icon, accent=False, note=None):
        """A small chip button with an icon and, if needed, a dimmed note on the right."""
        px = self.px
        color = C["accent"] if accent else C["muted"]
        card = Card(parent, self.scale, fill=C["surface"], border=mix(C["accent"], C["surface"], 0.5) if accent else
                    C["border"], radius=10, pad=3)
        parts = [tk.Label(card.body, text=icon, font=self.fonts["icon_tiny"], fg=color, bg=card.fill),
                 tk.Label(card.body, text=text, font=self.fonts["small_bold"], fg=C["accent"] if accent else C["text"],
                          bg=card.fill)]
        parts[0].pack(side="left", padx=(px(10), px(6)), pady=px(5))
        parts[1].pack(side="left", padx=(0, px(12)))
        if note:
            parts.append(tk.Label(card.body, text=note, font=self.fonts["small"], fg=C["dim"], bg=card.fill))
            parts[1].pack_configure(padx=(0, px(6)))
            parts[2].pack(side="left", padx=(0, px(12)))
        rest = card.border

        def border(target):
            self.animator.color(("chip", id(card)), card.set_border, card.border, target, 0.18)

        for widget in [card, card.body] + parts:
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", lambda e: command())
            widget.bind("<Enter>", lambda e: border(C["accent"]))
            widget.bind("<Leave>", lambda e: None if self.pointer_inside(card) else border(rest))
        return card

    def build_rule_card(self, rule):
        px = self.px
        name = rule["name"]
        card = Card(self.list_frame, self.scale)
        card.pack(fill="x", pady=(0, px(10)))
        body = card.body
        body.columnconfigure(0, weight=1)
        head = tk.Frame(body, bg=card.fill)
        head.grid(row=0, column=0, sticky="ew", padx=px(12), pady=(px(9), 0))
        title = rule.get("title")
        tk.Label(head, text=title or name + ".exe", font=self.fonts["h2"], fg=C["text"], bg=card.fill).pack(side="left")
        if title:
            tk.Label(head, text=name + ".exe", font=self.fonts["mono"], fg=C["dim"], bg=card.fill).pack(
                side="left", padx=(px(10), 0), pady=(px(2), 0))
        toggle = Toggle(body, self.scale, self.animator, on=rule["enabled"],
                        command=lambda on: self.change_rule(name, enabled=on))
        toggle.grid(row=0, column=1, sticky="ne", padx=px(14), pady=(px(11), 0))
        status = tk.Label(body, font=self.fonts["small"], fg=C["muted"], bg=card.fill, anchor="w", justify="left")
        status.grid(row=1, column=0, columnspan=2, sticky="ew", padx=px(12), pady=(px(2), px(8)))
        meter = Meter(body, self.scale, self.animator)
        meter.grid(row=2, column=0, columnspan=2, sticky="ew", padx=px(12))
        controls = tk.Frame(body, bg=card.fill)
        controls.grid(row=3, column=0, columnspan=2, sticky="ew", padx=px(12), pady=(px(12), 0))
        tk.Label(controls, text=self.t("mem_limit"), font=self.fonts["small"], fg=C["muted"], bg=card.fill).pack(
            side="left")
        Stepper(controls, rule["limit_mb"], limiter.LIMIT_STEPS, self.limit_text, self.fonts["small_bold"], self.scale,
                command=lambda mb: self.change_rule(name, limit_mb=mb)).pack(side="left", padx=(px(10), px(20)))
        Segmented(controls, [("soft", self.t("mem_soft")), ("hard", self.t("mem_hard"))], rule["mode"],
                  self.fonts["small_bold"], self.scale, self.animator,
                  command=lambda mode: self.change_rule(name, mode=mode)).pack(side="left")
        self.link(controls, self.t("mem_remove"), lambda: self.remove_rule(name), font="small", color=C["dim"]).pack(
            side="right")
        hint = tk.Label(body, font=self.fonts["small"], fg=C["muted"], bg=card.fill, anchor="w", justify="left")
        hint.grid(row=4, column=0, columnspan=2, sticky="ew", padx=px(12), pady=(px(10), 0))
        self.wrap(hint, px(62))
        denied = tk.Label(body, font=self.fonts["small_bold"], fg=C["warn"], bg=card.fill, anchor="w", justify="left")
        denied.grid(row=5, column=0, columnspan=2, sticky="ew", padx=px(12), pady=(px(6), 0))
        denied.grid_remove()
        self.wrap(denied, px(62))
        tk.Frame(body, bg=card.fill, height=px(10)).grid(row=6, column=0)
        self.page_cards.append(card)
        return {"card": card, "status": status, "meter": meter, "hint": hint, "denied": denied, "toggle": toggle}

    def update_memory_view(self, animate=True):
        """Updates the limiter page with the latest measurements without rebuilding it."""
        if not self.mem:
            return
        snap = self.limiter.snapshot()
        config, stats = snap["config"], snap["stats"]
        on = config["enabled"]
        self.mem["title"].configure(text=self.t("mem_on" if on else "mem_off"))
        self.mem["text"].configure(text=self.t("mem_on_text", seconds=config["interval"]) if on else
                                   self.t("mem_off_text"))
        self.mem["freed"].configure(text=self.size_text(snap["freed"]))
        if self.mem["toggle"].on != on:  # switched from the tray menu
            self.mem["toggle"].set(on)
        for rule in config["rules"]:
            widgets = self.mem["rules"].get(rule["name"])
            if not widgets:
                continue
            stat, hard = stats.get(rule["name"]), rule["mode"] == "hard"
            limit = rule["limit_mb"] * limiter.MB
            if not stat:
                text, ratio = "", 0.0
            elif not stat["count"]:
                text, ratio = self.t("mem_idle"), 0.0
            else:
                text = self.t("mem_now", size=self.size_text(stat["bytes"]), count=stat["count"])
                if hard:
                    text += "  ·  " + self.t("mem_largest", size=self.size_text(stat["largest"]))
                ratio = (stat["largest"] if hard else stat["bytes"]) / limit
            working = on and rule["enabled"]
            widgets["status"].configure(text=text, fg=C["muted"] if working else C["dim"])
            if abs(widgets["meter"].ratio - ratio) > 0.001 or not animate:
                widgets["meter"].set(ratio, animate)
            widgets["hint"].configure(text=self.t("mem_hard_hint" if hard else "mem_soft_hint"))
            if stat and stat["denied"]:
                widgets["denied"].configure(text=self.t("mem_denied", count=stat["denied"]))
                widgets["denied"].grid()
            else:
                widgets["denied"].grid_remove()

    def memory_tick(self):
        """Shows fresh limiter measurements every second (the limiter checks programs in its own thread)."""
        if self.page == "memory" and not self.hidden:
            self.update_memory_view()
        self.memory_job = self.root.after(1000, self.memory_tick)

    def limiter_changed(self):
        self.update_memory_view()
        self.update_nav_counts()
        self.update_footer()
        self.update_tray()

    def set_limiter_enabled(self, on):
        self.limiter.update(lambda config: config.update(enabled=on))
        self.limiter_changed()

    def set_limiter_interval(self, seconds):
        self.limiter.update(lambda config: config.update(interval=seconds))
        self.limiter_changed()

    def change_rule(self, name, **changes):
        def change(config):
            for rule in config["rules"]:
                if rule["name"] == name:
                    rule.update(changes)

        self.limiter.update(change)
        self.limiter_changed()

    def add_rule(self, name, limit_mb, title=None):
        name = limiter.normalize(name)
        if not name or limiter.is_protected(name):
            return
        rule = {"name": name, "limit_mb": limiter.clamp_limit(limit_mb), "mode": "soft", "enabled": True}
        if title:
            rule["title"] = title

        def change(config):
            if all(r["name"] != name for r in config["rules"]):
                config["rules"].append(rule)

        self.limiter.update(change)
        self.rebuild_memory(focus=name)
        self.limiter_changed()

    def remove_rule(self, name):
        self.limiter.update(lambda config: config.update(rules=[r for r in config["rules"] if r["name"] != name]))
        self.rebuild_memory()
        self.limiter_changed()

    def rebuild_memory(self, focus=None):
        """Rebuilds the page after a program is added or removed, keeping the scroll position."""
        top = self.canvas.yview()[0]
        self.show_page("memory", animate=False)

        def restore():
            card = self.mem.get("rules", {}).get(focus, {}).get("card")
            total = self.list_frame.winfo_height()
            if card and total > 0:  # the new card is scrolled into view and highlighted
                view = self.canvas.winfo_height()
                bottom = (card.winfo_y() + card.winfo_height() + self.px(8) - view) / total
                self.canvas.yview_moveto(max(top, bottom, 0.0))
                self.animator.color(("flash", focus), card.set_border, C["accent"], C["border"], 1.2, delay=0.2)
            else:
                self.canvas.yview_moveto(top)

        self.root.after(60, restore)

    def pick_running(self):
        """A window listing running programs: a click puts the program under a limit."""
        px = self.px
        programs = limiter.running_programs()
        added = {rule["name"] for rule in self.limiter.snapshot()["config"]["rules"]}
        win, content = self.dialog(self.t("mem_pick_title"), ICONS["memory"], CATEGORY_COLORS["memory"],
                                   self.t("mem_pick_title"), self.t("mem_pick_text"))
        frame = tk.Frame(content, bg=C["bg"])
        frame.pack(fill="x")
        canvas = tk.Canvas(frame, bg=C["bg"], highlightthickness=0, bd=0, width=px(480), height=px(320),
                           yscrollincrement=px(20))
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview, style="Brand.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", pady=px(2))
        canvas.pack(side="left", fill="both", expand=True)
        rows = tk.Frame(canvas, bg=C["bg"])
        window = canvas.create_window(0, 0, window=rows, anchor="nw")
        rows.bind("<Configure>", lambda e: canvas.configure(scrollregion=(0, 0, e.width, e.height)))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-3 * round(e.delta / 120), "units"))

        def choose(name):
            win.destroy()
            self.add_rule(name, limiter.default_limit(name), self.program_title(name))

        if not programs:
            tk.Label(rows, text=self.t("mem_pick_empty"), font=self.fonts["body"], fg=C["muted"], bg=C["bg"]).pack(
                anchor="w", padx=px(12), pady=px(10))
        for name, count, size in programs:
            row = tk.Frame(rows, bg=C["bg"])
            row.pack(fill="x")
            is_added = name in added
            title = self.program_title(name)
            label = tk.Label(row, text=title or name + ".exe", font=self.fonts["body"],
                             fg=C["dim"] if is_added else C["text"], bg=C["bg"], anchor="w")
            label.pack(side="left", padx=(px(12), 0), pady=px(6))
            info = tk.Label(row, text=self.t("mem_added") if is_added else
                            f"{self.size_text(size)}  ·  {self.t('mem_procs', n=count)}",
                            font=self.fonts["small"], fg=C["dim"] if is_added else C["muted"], bg=C["bg"])
            info.pack(side="right", padx=px(12))
            if is_added:
                continue
            parts = (row, label, info)

            def paint(color, parts=parts):
                for widget in parts:
                    widget.configure(bg=color)

            for widget in parts:
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda e, n=name: choose(n))
                widget.bind("<Enter>", lambda e, p=paint: p(C["raised"]))
                widget.bind("<Leave>", lambda e, p=paint, r=row: None if self.pointer_inside(r) else p(C["bg"]))
        GradientButton(content, self.t("cancel"), win.destroy, self.fonts["button"], self.scale, self.animator,
                       primary=False, pad=(18, 8)).pack(side="right", pady=(px(16), 0))
        self.present(win)

    # --- Tray ---

    def update_tray(self):
        """The tray icon is visible while the limiter works or the window is hidden."""
        active = self.limiter.active()
        if self.hidden or active:
            tip = self.t("tray_tip_on" if active else "tray_tip_off")
            if self.tray is None:
                self.tray = tray.TrayIcon(ICON_PATH, tip, self.tray_menu, self.on_tray_command, self.show_window,
                                          self.post)
            if self.tray.visible():
                self.tray.set_tooltip(tip)
            else:
                self.tray.tooltip = tip
                self.tray.show()
        elif self.tray and self.tray.visible():
            self.tray.hide()

    def tray_menu(self):
        # Called from the tray thread: only reads the settings
        return [(TRAY_OPEN, self.t("tray_open"), False),
                (TRAY_LIMITER, self.t("tray_limiter"), self.limiter.snapshot()["config"]["enabled"]),
                None, (TRAY_EXIT, self.t("tray_exit"), False)]

    def on_tray_command(self, command):
        if command == TRAY_OPEN:
            self.show_window()
        elif command == TRAY_LIMITER:
            self.set_limiter_enabled(not self.limiter.snapshot()["config"]["enabled"])
        elif command == TRAY_EXIT:
            self.quit()

    def show_window(self):
        self.hidden = False
        self.root.deiconify()
        if self.root.state() == "iconic":
            self.root.state("normal")
        self.root.lift()
        self.root.focus_force()
        self.update_memory_view()
        self.update_tray()

    def hide_to_tray(self):
        self.hidden = True
        self.root.withdraw()
        self.update_tray()
        if not self.settings.get("tray_hint_shown"):  # the tray hint is shown only the first time
            self.tray.balloon(self.t("tray_hidden_title"), self.t("tray_hidden_text"))
            self.settings["tray_hint_shown"] = True
            save_settings(self.settings)

    def on_close(self):
        """The window close button: with the limiter on, SimpleTool goes to the tray, otherwise it exits."""
        if self.limiter.active() and not self.acting:
            self.hide_to_tray()
        else:
            self.quit()

    def quit(self):
        if self.acting:  # an interrupted apply would leave the system half changed
            self.show_window()
            self.notify(self.t("busy_wait"), C["warn"], ICONS["warning"])
            return
        self.root.destroy()

    # --- Tweak pages ---

    def build_tweak_page(self, page):
        for tweak in tweaks.TWEAKS:
            if tweak.category == page:
                self.cards[tweak.id] = self.build_tweak_card(tweak)

    def build_tweak_card(self, tweak):
        px = self.px
        name, short, _ = self.text("tweaks", tweak.id)
        card = Card(self.list_frame, self.scale)
        card.pack(fill="x", pady=(0, px(10)))
        body = card.body
        body.columnconfigure(1, weight=1)
        check = CheckBox(body, px(20), self.animator)
        check.grid(row=0, column=0, rowspan=2, sticky="n", padx=(px(12), px(14)), pady=(px(10), 0))
        title = tk.Label(body, text=name, font=self.fonts["h2"], fg=C["text"], bg=card.fill, anchor="w", justify="left")
        title.grid(row=0, column=1, sticky="ew", pady=(px(7), 0))
        short_label = tk.Label(body, text=short, font=self.fonts["small"], fg=C["muted"], bg=card.fill, anchor="w",
                               justify="left")
        short_label.grid(row=1, column=1, sticky="ew", pady=(px(2), 0))
        pill = Pill(body, self.fonts["pill"], self.scale, self.animator)
        pill.grid(row=0, column=2, sticky="ne", padx=px(12), pady=(px(8), 0))  # on the title line
        self.wrap(title, px(212))
        self.wrap(short_label, px(212))
        widgets = {"card": card, "check": check, "title": title, "pill": pill}
        for widget in (card, body, check, title, short_label, pill):
            widget.bind("<Button-1>", lambda e, t=tweak: self.toggle_select(t))
            widget.bind("<Enter>", lambda e, t=tweak: self.hover_card(t, True))
            widget.bind("<Leave>", lambda e, t=tweak, c=card: None if self.pointer_inside(c) else self.hover_card(t, False))
        self.details_toggle(body, widgets, ("t", tweak.id), lambda holder: self.build_tweak_details(holder, tweak),
                            column=1, indent=0)
        self.page_cards.append(card)
        self.cards[tweak.id] = widgets
        self.paint_card(tweak, animate=False)
        return widgets

    def details_toggle(self, body, widgets, key, builder, column=0, indent=12):
        """A "Details" link and an animated expanding block under it."""
        px = self.px
        bg = body.cget("bg")
        row = tk.Frame(body, bg=bg, cursor="hand2")
        row.grid(row=2, column=column, sticky="w", padx=(px(indent), 0), pady=(px(5), px(8)))
        label = tk.Label(row, text=self.t("details_show"), font=self.fonts["small_bold"], fg=C["accent"], bg=bg,
                         cursor="hand2")
        label.pack(side="left")
        chevron = tk.Label(row, text=ICONS["down"], font=self.fonts["icon_tiny"], fg=C["accent"], bg=bg, cursor="hand2")
        chevron.pack(side="left", padx=(px(6), 0), pady=(px(2), 0))
        holder = tk.Frame(body, bg=bg, height=1)
        holder.grid(row=3, column=0, columnspan=3, sticky="ew")
        holder.grid_remove()
        widgets.update(holder=holder, inner=None, toggle=label, chevron=chevron, builder=builder)
        for widget in (row, label, chevron):
            widget.bind("<Button-1>", lambda e: self.toggle_details(key, widgets))
        if key in self.expanded:
            self.expand(key, widgets, animate=False)

    def expand(self, key, widgets, animate=True):
        holder = widgets["holder"]
        if widgets["inner"] is None:
            widgets["inner"] = widgets["builder"](holder)
            widgets["inner"].pack(fill="x", anchor="n")
        widgets["toggle"].configure(text=self.t("details_hide"))
        widgets["chevron"].configure(text=ICONS["up"])
        holder.grid()
        if not animate:
            holder.pack_propagate(True)
            return
        holder.pack_propagate(False)
        holder.configure(height=1)
        self.root.update_idletasks()
        target = widgets["inner"].winfo_reqheight()
        self.animator.animate(("details", key), 0.34, lambda t: holder.configure(height=max(1, round(target * t))),
                              done=lambda: holder.pack_propagate(True), ease=ease_in_out)
        fade_in(self.animator, ("detailsfade", key), descendants(widgets["inner"]), delay=0.08, duration=0.35)

    def toggle_details(self, key, widgets):
        holder = widgets["holder"]
        if key not in self.expanded:
            self.expanded.add(key)
            self.expand(key, widgets)
            return
        self.expanded.discard(key)
        widgets["toggle"].configure(text=self.t("details_show"))
        widgets["chevron"].configure(text=ICONS["down"])
        start = holder.winfo_height()
        holder.pack_propagate(False)
        self.animator.animate(("details", key), 0.26, lambda t: holder.configure(height=max(1, round(start * (1 - t)))),
                              done=holder.grid_remove, ease=ease_in_out)

    def describe(self, op):
        if isinstance(op, engine.Value):
            data = op.data
            if callable(data):
                data = "‹" + self.t("op_label") + "›"
            elif isinstance(data, str):
                data = f'"{data}"'
            return self.t("op_value", path=op.path, name=op.name or self.t("op_default_name"), data=data)
        if isinstance(op, engine.OwnedKey):
            return self.t("op_key", path=op.path)
        if isinstance(op, engine.Service):
            return self.t("op_service", name=op.name)
        if isinstance(op, engine.Task):
            return self.t("op_task", path=op.path)
        if isinstance(op, engine.Shortcut):
            return self.t("op_shortcut", name=op.names[self.lang])
        return str(op)

    def build_tweak_details(self, holder, tweak):
        px = self.px
        bg = holder.cget("bg")
        inner = tk.Frame(holder, bg=bg)
        indent = (px(46), px(16))
        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=(px(46), px(12)), pady=(0, px(12)))
        text = tk.Label(inner, text=self.text("tweaks", tweak.id)[2], font=self.fonts["body"], fg=C["text"], bg=bg,
                        anchor="w", justify="left")
        text.pack(fill="x", padx=indent)
        self.wrap(text, px(82))
        tk.Label(inner, text=self.t("what_changes"), font=self.fonts["small_bold"], fg=C["dim"], bg=bg, anchor="w").pack(
            fill="x", padx=indent, pady=(px(14), px(6)))

        rows = self.scan["checks"][tweak.id][1] if self.scan else [(op, None, None) for op in tweak.ops]
        # Values inside owned keys (menu items) are not listed: the key itself is enough
        owned = [op.path + "\\" for op in tweak.ops if isinstance(op, engine.OwnedKey)]
        reasons = set()
        missing = sum(reason == "missing" for _, _, reason in rows)
        summarize = missing >= MISSING_SUMMARY  # a long "not on this PC" list collapses into one line
        for op, state, reason in rows:
            if isinstance(op, engine.Value) and any((op.path + "\\").startswith(prefix) for prefix in owned):
                continue
            if isinstance(op, engine.OwnedKey) and any(op.path.startswith(p) and op.path + "\\" != p for p in owned):
                continue  # an item of a nested submenu: showing the submenu itself is enough
            if reason == "missing" and summarize:
                continue
            if reason == "missing":
                glyph, color, suffix = ICONS["dash"], C["dim"], self.t("op_missing")
            elif reason:
                glyph, color, suffix = ICONS["unknown"], C["warn"], self.t("op_unknown")
                reasons.add(reason)
            elif state:
                glyph, color, suffix = ICONS["check"], C["ok"], ""
            else:
                glyph, color, suffix = ICONS["circle"], C["dim"], ""
            line = tk.Frame(inner, bg=bg)
            line.pack(fill="x", padx=indent, pady=px(2))
            tk.Label(line, text=glyph, font=self.fonts["icon_small"], fg=color, bg=bg, width=2).pack(side="left", anchor="n")
            label = tk.Label(line, text=self.describe(op) + (f"  — {suffix}" if suffix else ""), font=self.fonts["mono"],
                             fg=C["text"] if state else C["muted"], bg=bg, anchor="w", justify="left")
            label.pack(side="left", fill="x", expand=True, padx=(px(4), 0))
            self.wrap(label, px(122))
        if summarize:
            line = tk.Frame(inner, bg=bg)
            line.pack(fill="x", padx=indent, pady=px(2))
            tk.Label(line, text=ICONS["dash"], font=self.fonts["icon_small"], fg=C["dim"], bg=bg, width=2).pack(side="left")
            tk.Label(line, text=self.t("op_missing_many", n=missing), font=self.fonts["small"], fg=C["muted"],
                     bg=bg, anchor="w").pack(side="left", padx=(px(4), 0))

        note = tk.Frame(inner, bg=bg)
        note.pack(fill="x", padx=indent, pady=(px(12), 0))
        saved = tweak.id in engine.load_backup()
        tk.Label(note, text=ICONS["info"], font=self.fonts["icon_small"], fg=C["accent"], bg=bg, width=2).pack(
            side="left", anchor="n")
        backup = tk.Label(note, text=self.t("backup_saved" if saved else "backup_none"), font=self.fonts["small"],
                          fg=C["muted"], bg=bg, anchor="w", justify="left")
        backup.pack(side="left", fill="x", expand=True, padx=(px(4), 0))
        self.wrap(backup, px(122))
        for reason in sorted(reasons):
            problem, tip = self.text("reasons", reason)
            hint = tk.Label(inner, text=f"{problem} {tip}", font=self.fonts["small"], fg=C["warn"], bg=bg, anchor="w",
                            justify="left")
            hint.pack(fill="x", padx=indent, pady=(px(8), 0))
            self.wrap(hint, px(82))
        tk.Frame(inner, bg=bg, height=px(12)).pack()
        return inner

    # --- Tweak state ---

    def card_state(self, tweak):
        if not self.scan or tweak.id not in self.scan["checks"]:
            return "checking"
        status = self.scan["checks"][tweak.id][0]
        if status != "unavailable" and tweak.admin and not self.admin:
            return "admin"
        return status

    def selectable(self, tweak):
        return not self.busy and self.card_state(tweak) in SELECTABLE

    def paint_card(self, tweak, animate=True):
        widgets = self.cards[tweak.id]
        state = self.card_state(tweak)
        enabled = self.selectable(tweak)
        selected = tweak.id in self.selected
        widgets["pill"].set(self.t("status_" + state), status_color(state), animate)
        widgets["check"].set(selected, state in SELECTABLE, animate)
        border = C["primary"] if selected else (C["border_hover"] if self.hovered == tweak.id and enabled else C["border"])
        card = widgets["card"]
        if animate:
            self.animator.color(("border", tweak.id), card.set_border, card.border, border, 0.2)
        else:
            card.set_border(border)
        widgets["title"].configure(fg=C["dim"] if state in ("unavailable", "admin") else C["text"])
        for key in ("card", "check", "title", "pill"):
            widgets[key].configure(cursor="hand2" if enabled else "arrow")

    def hover_card(self, tweak, inside):
        self.hovered = tweak.id if inside else None
        if tweak.id in self.cards:
            self.paint_card(tweak)

    def toggle_select(self, tweak):
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
        for tweak_id in self.cards:
            self.paint_card(self.tweak_by_id[tweak_id])
        self.update_footer()

    def clear_selection(self):
        self.selected -= set(self.cards)
        self.message = None
        for tweak_id in self.cards:
            self.paint_card(self.tweak_by_id[tweak_id])
        self.update_footer()

    def update_footer(self):
        if self.message:
            key, kw = self.message
            text = self.t(key, **kw)
        elif self.selected:
            text = self.t("selected", n=len(self.selected))
        elif self.page == "memory":
            text = self.t("mem_on" if self.limiter.active() else "mem_off")
        else:
            text = self.t("hint_select")
        self.message_label.configure(text=text)
        if self.busy:
            if not self.spinner.winfo_ismapped():
                self.spinner.pack(side="left", padx=(0, self.px(10)), before=self.message_label)
            self.spinner.start()
        else:
            self.spinner.stop()
            self.spinner.pack_forget()
        enabled = not self.busy and bool(self.selected)
        self.apply_button.set_enabled(enabled)
        self.revert_button.set_enabled(enabled)
        for button, needs_admin in self.action_buttons:
            try:
                button.set_enabled(not self.busy and (self.admin or not needs_admin))
            except tk.TclError:
                pass

    def refresh_view(self):
        """Updates the page after a new scan without rebuilding it unless needed."""
        if self.page in ("overview", "snapshots"):
            self.show_page(self.page)
            return
        if self.page == "memory":
            self.update_nav_counts()
            self.update_footer()
            return
        for tweak_id, widgets in self.cards.items():
            self.paint_card(self.tweak_by_id[tweak_id])
            if widgets["inner"] is not None:  # the details depend on the scan results
                widgets["inner"].destroy()
                widgets["inner"] = None
                if ("t", tweak_id) in self.expanded:
                    self.expand(("t", tweak_id), widgets, animate=False)
        self.update_nav_counts()
        self.update_footer()

    # --- Window settings ---

    def set_language(self, lang):
        if lang != self.lang:
            self.lang = lang
            self.settings["lang"] = lang
            save_settings(self.settings)
            self.build()
            self.update_tray()

    def set_theme(self, name):
        if name != C["name"]:
            theme.use(name)
            theme.clear_cache()
            self.settings["theme"] = name
            save_settings(self.settings)
            theme.style_title_bar(self.root)
            self.build()

    def on_wheel(self, event):
        """Smooth mouse wheel scrolling."""
        try:
            if event.widget.winfo_toplevel() is not self.root:
                return
        except (AttributeError, KeyError, tk.TclError):
            return
        total, view = self.list_frame.winfo_height(), self.canvas.winfo_height()
        if total <= view:
            return
        top = self.canvas.yview()[0]
        base = getattr(self, "scroll_target", top) if "scroll" in self.animator.tweens else top
        target = min(max(base - event.delta / 120 * self.px(110) / total, 0.0), 1.0 - view / total)
        self.scroll_target = target
        self.animator.animate("scroll", 0.24, lambda t: self.canvas.yview_moveto(top + (target - top) * t))

    # --- Scan, apply, revert ---

    def start_scan(self):
        self.scan = None
        self.scan_done = set()
        self.scan_started = time.perf_counter()
        self.busy = True
        self.message = ("checking", {})
        if self.page == "overview":
            self.show_page("overview", animate=False)
        else:
            self.refresh_view()
        self.update_footer()
        self.run_job(lambda: collect_scan(lambda step: self.jobs.put((self.on_scan_step, step))), self.on_scan_done)

    def rescan(self):
        if not self.busy:
            self.start_scan()

    def on_scan_step(self, step):
        self.scan_done.add(step)
        rows = getattr(self, "scan_rows", {})
        if step in rows:
            glyph, label = rows[step]
            try:
                glyph.configure(text=ICONS["check"])
                self.animator.color(("step", step), lambda c: glyph.configure(fg=c), C["dim"], C["ok"], 0.3)
                self.animator.color(("steplabel", step), lambda c: label.configure(fg=c), C["muted"], C["text"], 0.3)
            except tk.TclError:
                pass

    def on_scan_done(self, result):
        wait = MIN_SCAN_SECONDS - (time.perf_counter() - self.scan_started)
        if wait > 0:
            self.root.after(int(wait * 1000), lambda: self.finish_scan(result))
        else:
            self.finish_scan(result)

    def finish_scan(self, result):
        self.busy = False
        if self.message == ("checking", {}):
            self.message = None
        if isinstance(result, Exception):
            self.scan = {"services": {}, "checks": {}, "ctx": None}
            self.show_errors([str(result)])
        else:
            self.scan = result
            # Without administrator rights some values cannot be read, and the original snapshot is kept forever
            if not self.snapshots and self.admin:
                self.take_initial_snapshot()
        self.selected = {i for i in self.selected if self.selectable(self.tweak_by_id[i])}
        self.refresh_view()

    def take_initial_snapshot(self):
        """The very first snapshot: how things were before SimpleTool. Taken in the background after the first scan."""
        ctx, statuses = self.scan["ctx"], self.status_map()

        def done(result):
            self.snapshots = engine.list_snapshots()
            if self.page == "snapshots" and not self.busy:
                self.refresh_view()
            else:
                self.update_nav_counts()

        self.run_job(lambda: engine.take_snapshot(tweaks.TWEAKS, ctx, "initial", statuses, VERSION), done)

    def apply_selected(self):
        chosen = [t for t in tweaks.TWEAKS if t.id in self.selected and self.card_state(t) != "applied"]
        if not chosen:
            self.message = ("nothing_to_apply", {})
            self.update_footer()
            return
        lang, ctx = self.lang, self.scan["ctx"]
        self.start_work(chosen, lambda t: engine.apply(t, lang, ctx), "working_apply", "done_apply", "before_apply")

    def revert_selected(self):
        chosen = [t for t in tweaks.TWEAKS if t.id in self.selected and self.card_state(t) in REVERTIBLE]
        if not chosen:
            self.message = ("nothing_to_revert", {})
            self.update_footer()
            return
        ctx = self.scan["ctx"]
        self.start_work(chosen, lambda t: engine.revert(t, ctx), "working_revert", "done_revert", "before_revert")

    def run_action(self, working_key, work, on_done):
        """A long action in the background: the window is busy, the footer shows a spinner."""
        self.busy = self.acting = True
        self.message = (working_key, {})
        for tweak_id in self.cards:
            self.paint_card(self.tweak_by_id[tweak_id])
        self.update_footer()

        def done(result):
            self.busy = self.acting = False
            on_done(result)

        self.run_job(work, done)

    def start_work(self, chosen, action, working_key, done_key, snapshot_kind):
        """Takes a "before" snapshot, applies or reverts tweaks in the background, then scans the system again."""
        names = {t.id: self.text("tweaks", t.id)[0] for t in chosen}
        ctx, statuses, failed = self.scan["ctx"], self.status_map(), self.t("snap_failed")

        def work():
            errors = []
            try:
                engine.take_snapshot(tweaks.TWEAKS, ctx or engine.Context(), snapshot_kind, statuses, VERSION)
            except OSError as exc:
                errors.append(f"{failed} {exc}")
            for tweak in chosen:
                errors += [f"{names[tweak.id]}: {error}" for error in action(tweak)]
            engine.notify_shell()
            return errors, collect_scan()

        def done(result):
            self.selected.clear()
            self.snapshots = engine.list_snapshots()
            if isinstance(result, Exception):
                errors = [str(result)]
                self.start_scan()
            else:
                errors, self.scan = result
            self.message = (done_key, {"n": len(chosen)})
            self.refresh_view()
            text = self.t(done_key, n=len(chosen))
            if errors:
                self.notify(self.t("errors_title"), C["warn"], ICONS["warning"])
                self.show_errors(errors)
            else:
                self.notify(text, C["ok"], ICONS["check"])

        self.run_action(working_key, work, done)

    def run_job(self, work, done):
        def target():
            try:
                result = work()
            except Exception as exc:  # an error in the background must not silently leave the window busy
                result = exc
            self.jobs.put((done, result))

        threading.Thread(target=target, daemon=True).start()

    def post(self, callback):
        """Runs callback on the window thread: other threads (tray, limiter) never touch Tk themselves."""
        self.jobs.put((lambda _: callback(), None))

    def poll(self):
        while True:
            try:
                callback, payload = self.jobs.get_nowait()
            except queue.Empty:
                break
            callback(payload)
        # Same thresholds as automatic garbage collection, but on the window thread
        counts, thresholds = gc.get_count(), gc.get_threshold()
        for generation in (2, 1, 0):
            if thresholds[generation] and counts[generation] > thresholds[generation]:
                gc.collect(generation)
                break
        self.poll_job = self.root.after(40, self.poll)

    def on_destroy(self, event):
        # The window is closed: cancel the queue polling, otherwise Tk calls it after the window is gone
        if event.widget is self.root:
            self.animator.stop()
            for job in (getattr(self, "poll_job", None), getattr(self, "memory_job", None)):
                if job:
                    self.root.after_cancel(job)
            # The limiter removes its hard caps, the icon leaves the tray
            self.limiter.stop()
            if self.tray:
                self.tray.hide()
            if self.instance:
                self.instance.release()
            gc.enable()  # background threads are stopped: garbage can be collected anywhere again

    # --- Dialogs ---

    def dialog(self, title, icon, color, heading, text):
        """A blagotech-style window: icon, heading, text. Returns (window, content frame)."""
        px = self.px
        win = tk.Toplevel(self.root, bg=C["surface"])
        win.withdraw()
        win.title(title)
        win.transient(self.root)
        win.resizable(False, False)
        body = tk.Frame(win, bg=C["surface"])
        body.pack(padx=px(28), pady=(px(24), px(22)))
        body.columnconfigure(1, weight=1)  # extra width goes to the text, not to the icon column
        badge = Card(body, self.scale, fill=mix(color, C["surface"], 0.14), border=mix(color, C["surface"], 0.4),
                     radius=14, pad=4)
        badge.grid(row=0, column=0, rowspan=2, sticky="nw")
        tk.Label(badge.body, text=icon, font=self.fonts["icon_big"], fg=color, bg=badge.fill).pack(padx=px(8), pady=px(6))
        tk.Label(body, text=heading, font=self.fonts["dialog"], fg=C["text"], bg=C["surface"], anchor="w").grid(
            row=0, column=1, sticky="w", padx=(px(16), 0))
        tk.Label(body, text=text, font=self.fonts["body"], fg=C["muted"], bg=C["surface"], justify="left", anchor="w",
                 wraplength=px(440)).grid(row=1, column=1, sticky="w", padx=(px(16), 0), pady=(px(6), 0))
        content = tk.Frame(body, bg=C["surface"])
        content.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(px(18), 0))
        return win, content

    def present(self, win):
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_reqheight()) // 3
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        theme.style_title_bar(win)
        theme.set_window_icon(win, ICON_PATH)
        win.bind("<Escape>", lambda e: win.destroy())
        win.deiconify()
        win.grab_set()
        win.focus_set()

    def restart_as_admin(self, error_label=None):
        if self.acting:
            return
        # The new copy must not mistake this one for an already running copy and exit
        if self.instance:
            self.instance.release()
        code = relaunch_as_admin()
        if code > 32:
            self.root.destroy()
            return
        if self.instance and self.instance.acquire():
            self.instance.listen(lambda: self.post(self.show_window))
        if code != 5 and error_label is not None:  # 5 means the user cancelled the UAC prompt
            error_label.configure(text=self.t("admin_failed"))

    def show_admin_dialog(self):
        px = self.px
        win, content = self.dialog(self.t("admin_title"), ICONS["shield"], C["warn"], self.t("admin_title"),
                                   self.t("admin_text"))
        error = tk.Label(content, text="", font=self.fonts["small"], fg=C["warn"], bg=C["surface"], anchor="w")
        error.pack(fill="x")
        GradientButton(content, self.t("admin_restart"), lambda: self.restart_as_admin(error), self.fonts["button"],
                       self.scale, self.animator, pad=(18, 8)).pack(side="right")
        GradientButton(content, self.t("admin_continue"), win.destroy, self.fonts["button"], self.scale, self.animator,
                       primary=False, pad=(18, 8)).pack(side="right", padx=(0, px(10)))
        self.present(win)

    def show_errors(self, errors):
        px = self.px
        win, content = self.dialog(self.t("errors_title"), ICONS["warning"], C["warn"], self.t("errors_title"),
                                   self.t("errors_intro"))
        text = tk.Text(content, font=self.fonts["small"], fg=C["text"], bg=C["bg"], relief="flat", wrap="word",
                       width=72, height=min(12, 2 * len(errors) + 1), padx=px(12), pady=px(10), highlightthickness=0)
        text.insert("1.0", "\n\n".join(errors))
        text.configure(state="disabled")
        text.pack(fill="x")
        GradientButton(content, self.t("close"), win.destroy, self.fonts["button"], self.scale, self.animator,
                       pad=(18, 8)).pack(side="right", pady=(px(16), 0))
        self.present(win)


def main():
    instance = tray.SingleInstance()
    if not instance.acquire():
        return  # SimpleTool is already running: its window shows itself
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
        root.iconbitmap(default=ICON_PATH)
    except tk.TclError:
        pass
    app = App(root, instance)
    width = min(app.px(1080), root.winfo_screenwidth() - app.px(40))
    height = min(app.px(740), root.winfo_screenheight() - app.px(80))
    root.minsize(app.px(900), app.px(580))
    root.geometry(f"{width}x{height}+{(root.winfo_screenwidth() - width) // 2}+{(root.winfo_screenheight() - height) // 3}")
    theme.style_title_bar(root)
    theme.set_window_icon(root, ICON_PATH)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
