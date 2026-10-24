"""SimpleTool: Windows tweaks. System overview, privacy, system, File Explorer, context menu."""
import collections
import ctypes
import datetime
import gc
import json
import os
import platform
import queue
import subprocess
import sys
import threading
import time
import traceback
import tkinter as tk
import tkinter.font as tkfont
import urllib.parse
from ctypes import wintypes
from tkinter import ttk

import diagnostics
import engine
import i18n
import limiter
import programs
import services
import terms
import theme
import tray
import tweaks
import sysinfo
import updater
import updates
import whatsnew
from theme import C, CATEGORY_COLORS, lerp, mix
from widgets import (Animator, Card, CheckBox, Flow, GradientButton, Meter, Pill, ScanRings, Segmented, Spinner,
                     Stepper, Toast, Toggle, descendants, ease_in_out, fade_in)

VERSION = "0.8"
SUPPORT_EMAIL = "service@blagotech.uk"  # bug reports and questions
UPDATE_CHECK_EVERY = datetime.timedelta(days=1)  # the automatic check at start, unless turned off in Help
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(BASE_DIR, "assets", "app.ico")
PAGES = ["overview", "diagnostics"] + tweaks.CATEGORIES + ["memory", "snapshots"]
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
DIAG_ITEMS = 15  # lines under a troubleshooting finding; the rest are counted

# Icons from the Segoe Fluent Icons / Segoe MDL2 Assets font
ICONS = {"overview": "", "privacy": "", "system": "", "explorer": "", "context": "",
         "telemetry": "", "location": "", "performance": "", "gaming": "", "security": "",
         "globe": "", "palette": "", "shield": "", "down": "", "up": "",
         "warning": "", "check": "", "circle": "", "unknown": "", "dash": "",
         "info": "", "refresh": "", "dots": "", "snapshots": "", "folder": "", "memory": "",
         "add": "", "apps": "", "help": "",
         "diagnostics": "", "speed": "", "drive": "", "bug": ""}
# The icon of each group of troubleshooting checks
GROUP_ICONS = {"performance": "speed", "storage": "drive", "stability": "bug", "security": "shield"}


def status_color(state):
    return {"applied": C["ok"], "partial": C["warn"], "not_applied": C["muted"], "unknown": C["warn"],
            "unavailable": C["dim"], "admin": C["warn"], "checking": C["dim"]}[state]


def service_color(state):
    return {"on": C["accent"], "off": C["muted"], "missing": C["dim"], "unknown": C["warn"]}[state]


def severity_color(severity):
    return {"problem": C["bad"], "warning": C["warn"], "info": C["accent"], "ok": C["ok"], "unknown": C["dim"]}[severity]


def load_settings():
    try:
        with open(os.path.join(engine.data_dir(), "settings.json"), encoding="utf-8") as f:
            settings = json.load(f)
        return settings if isinstance(settings, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    try:
        engine.write_json(os.path.join(engine.data_dir(), "settings.json"), settings)
    except OSError:
        pass


def error_log_path():
    return os.path.join(engine.data_dir(), "error.log")


def log_error(text):
    """Appends an error to error.log: a windowed exe has no console to print it to."""
    try:
        path = error_log_path()
        if os.path.exists(path) and os.path.getsize(path) > 512 * 1024:  # the log stays small
            os.replace(path, path + ".old")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S}  SimpleTool {VERSION}  "
                    f"Windows {platform.version()}\n{text.rstrip()}\n")
    except OSError:
        pass


def effect_keys(effects):
    """Text keys for what applied changes still need: an Explorer restart has been done, a PC restart covers signing
    out."""
    keys = ["after_explorer"] if "explorer" in effects else []
    if "restart" in effects:
        keys.append("after_restart")
    elif "signout" in effects:
        keys.append("after_signout")
    return keys


def relaunch_as_admin():
    """Restarts the program as administrator. Returns the ShellExecute code (above 32 means success)."""
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, sys.argv[1:]
        # Not BASE_DIR: the new copy must not hold this copy's temporary folder, or it cannot be deleted on exit
        folder = os.path.dirname(sys.executable)
        # The new copy gets this environment when Windows does not ask for consent (UAC off): it must unpack
        # itself anew rather than take itself for part of this copy (see updater)
        os.environ.update(updater.fresh_environment({}))
    else:
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        exe = pythonw if os.path.exists(pythonw) else sys.executable
        args = [os.path.abspath(sys.argv[0])] + sys.argv[1:]
        folder = BASE_DIR
    return ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, subprocess.list2cmdline(args), folder, 1)


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
        self.other_account = engine.other_account()  # started with another account's password: (it, signed in)
        self.error_shown = False  # an unexpected error is shown once per session, every one goes to error.log
        self.checking_updates = False
        self.available_update = None  # what a check found: shown as a dot on Help and an Update item in its menu
        root.report_callback_exception = self.report_error
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
        self.diag_cards = {}
        self.action_buttons = []  # (button, needs administrator rights) — disabled while the window is busy
        self.snapshots = engine.list_snapshots()
        self.diag = None          # troubleshooting findings; the check runs the first time its page is opened
        self.diag_time = None
        self.diag_running = False
        self.diag_done = set()
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
        # What's new: shown once after an update. A first run (no terms accepted yet) is not an update
        seen = self.settings.get("seen_version")
        self.whats_new = whatsnew.since(seen, VERSION) if seen != VERSION and (seen or self.settings.get("terms")) else []
        if seen != VERSION:
            self.settings["seen_version"] = VERSION
            save_settings(self.settings)
        if self.settings.get("terms") != terms.VERSION:
            root.after(300, lambda: self.show_terms(first_run=True))
        else:
            root.after(600, self.startup_dialogs)
        self.start_jobs = [root.after(1500, self.remove_previous_exe), root.after(4000, self.daily_update_check)]

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
        self.nav_compact = False

        def fit(event):
            # In a short window the menu items move closer together, so the bottom of the sidebar stays in view
            compact = event.height < px(660)
            if compact != self.nav_compact:
                self.nav_compact = compact
                for widgets in self.nav.values():
                    widgets["icon"].pack_configure(pady=px(6) if compact else px(9))

        side.bind("<Configure>", fit, add="+")

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
        self.link(bottom, self.t("terms_link"), self.show_terms, font="small", color=C["side_dim"]).pack(
            anchor="w", pady=(px(4), 0))

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
        # Compact buttons: help has its name, theme is an icon only, language is a code; the rest is in the menus
        help_button = self.drop_button(controls, ICONS["help"], self.t("help"), self.help_menu, badge=True)
        help_button.pack(side="left", padx=(0, px(8)))
        self.help_badge = help_button.badge
        self.paint_update_badge()
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
                                      justify="left")
        self.message_label.pack(side="left", fill="x", expand=True)

    def drop_button(self, parent, icon, label, build_menu, badge=False):
        """A button with a drop-down menu (help, theme, language). With badge, card.badge is a dot that is empty
        until something in the menu wants attention."""
        px = self.px
        card = Card(parent, self.scale, fill=C["surface"], border=C["border"], radius=10, pad=3)
        parts = [tk.Label(card.body, text=icon, font=self.fonts["icon_small"], fg=C["accent"], bg=card.fill)]
        parts[0].pack(side="left", padx=(px(10), px(6)), pady=px(5))
        if label:
            parts.append(tk.Label(card.body, text=label, font=self.fonts["small_bold"], fg=C["text"], bg=card.fill))
            parts[-1].pack(side="left", padx=(0, px(2)))
        if badge:
            card.badge = tk.Label(card.body, text="", font=self.fonts["small_bold"], fg=C["ok"], bg=card.fill)
            card.badge.pack(side="left", padx=(px(4), 0))
            parts.append(card.badge)
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

    def menu(self, title):
        menu = tk.Menu(self.root, tearoff=False, bg=C["surface"], fg=C["text"], activebackground=C["primary"],
                       activeforeground="#FFFFFF", disabledforeground=C["dim"], selectcolor=C["accent"],
                       font=self.fonts["body"], bd=0)
        menu.add_command(label=title, state="disabled")
        return menu

    def popup_menu(self, title, items, current, command):
        menu = self.menu(title)
        menu.add_separator()
        variable = tk.StringVar(menu, value=current)
        for value, label in items:
            menu.add_radiobutton(label=label, value=value, variable=variable, command=lambda v=value: command(v))
        menu.variable = variable  # keep a reference so the garbage collector does not collect the variable
        return menu

    def help_menu(self):
        menu = self.menu(f"SimpleTool {VERSION} {self.t('beta').lower()}")
        menu.add_separator()
        if self.available_update:
            info = self.available_update
            menu.add_command(label="● " + self.t("update_install_menu", version=info["version"]),
                             command=lambda: self.show_update(info))
        for key, command in (("update_link", self.check_updates), ("whatsnew_link", self.show_whats_new),
                             ("report_link", self.show_report), ("terms_link", self.show_terms)):
            menu.add_command(label=self.t(key), command=command)
        menu.add_separator()
        daily = tk.BooleanVar(menu, value=self.settings.get("auto_update_check", True))
        menu.add_checkbutton(label=self.t("update_daily"), variable=daily,
                             command=lambda: self.set_daily_check(daily.get()))
        menu.variable = daily  # keep a reference so the garbage collector does not collect the variable
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
        # The footer message wraps instead of running under the buttons, which take about px(300)
        self.message_label.configure(wraplength=max(self.px(160), self.content_width - self.px(300)))
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
        # Troubleshooting: how many findings need attention, red if one of them is a problem
        found = diagnostics.counts(self.diag or [])
        attention = found["problem"] + found["warning"]
        light = C["name"] == "light"  # the sidebar is dark in every theme
        color = ("#FCA5A5" if light else C["bad"]) if found["problem"] else ("#F0B783" if light else C["warn"])
        self.nav["diagnostics"]["count"].configure(text=str(attention) if attention else "", fg=color)
        if not self.scan:
            for page, widgets in self.nav.items():
                if page not in ("memory", "diagnostics"):
                    widgets["count"].configure(text="")
            return
        for page, widgets in self.nav.items():
            if page in ("memory", "diagnostics"):
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
                                                                C["bg"], strength, step=max(2, round(2 * self.scale))))
        for widget in self.links.winfo_children():
            widget.destroy()
        if page == "overview":
            self.link(self.links, self.t("rescan"), self.rescan).pack(side="left")
        elif page == "snapshots":
            self.link(self.links, self.t("snap_folder"), lambda: os.startfile(engine.snapshots_dir())).pack(side="left")
        elif page == "memory":
            self.link(self.links, self.t("mem_pick"), self.pick_running).pack(side="left")
        elif page == "diagnostics":
            self.link(self.links, self.t("rescan"), self.rescan_diagnostics).pack(side="left")
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
        self.diag_cards = {}
        self.action_buttons = []
        self.mem = {}
        if page == "overview":
            self.build_overview()
        elif page == "snapshots":
            self.build_snapshots_page()
        elif page == "memory":
            self.build_memory_page()
        elif page == "diagnostics":
            self.build_diagnostics_page()
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
            self.scan_rows = self.build_scan_panel(ICONS["overview"], self.t("scan_title"), self.t("scan_text"),
                                                   [(step, self.t("scan_" + step)) for step in SCAN_STEPS],
                                                   self.scan_done)
            return
        self.build_summary()
        self.build_callout()
        for group in services.GROUPS:
            self.section_head(ICONS[group], self.text("groups", group))
            for svc_group, name, tweak_id in services.SERVICES:
                if svc_group == group and name in self.scan["services"]:  # a failed scan has no services
                    self.service_cards[name] = self.build_service_card(name, tweak_id)

    def section_head(self, icon, text):
        """A heading for a group of cards."""
        head = tk.Frame(self.list_frame, bg=C["bg"])
        head.pack(fill="x", padx=(self.px(18), 0), pady=(self.px(18), self.px(8)))
        tk.Label(head, text=icon, font=self.fonts["icon_small"], fg=C["accent"], bg=C["bg"]).pack(side="left")
        tk.Label(head, text=text, font=self.fonts["small_bold"], fg=C["muted"], bg=C["bg"]).pack(
            side="left", padx=(self.px(8), 0))

    def build_scan_panel(self, icon, title, text, steps, done):
        """Rings and the list of steps while something is being read. Returns {step: (glyph, label)}."""
        px = self.px
        card = Card(self.list_frame, self.scale, radius=16, pad=8)
        card.pack(fill="x")
        body = card.body
        rings = ScanRings(body, px(150), self.scale, icon, self.fonts["icon_scan"])
        rings.pack(pady=(px(18), px(6)))
        rings.start()
        tk.Label(body, text=title, font=self.fonts["dialog"], fg=C["text"], bg=card.fill).pack()
        tk.Label(body, text=text, font=self.fonts["small"], fg=C["muted"], bg=card.fill,
                 wraplength=px(440), justify="center").pack(pady=(px(4), px(14)))
        holder = tk.Frame(body, bg=card.fill)
        holder.pack(pady=(0, px(22)))
        rows = {}
        for step, name in steps:
            row = tk.Frame(holder, bg=card.fill)
            row.pack(anchor="w", pady=px(3))
            finished = step in done
            glyph = tk.Label(row, text=ICONS["check"] if finished else ICONS["dots"], font=self.fonts["icon_small"],
                             fg=C["ok"] if finished else C["dim"], bg=card.fill, width=2)
            glyph.pack(side="left")
            label = tk.Label(row, text=name, font=self.fonts["body"], fg=C["text"] if finished else C["muted"],
                             bg=card.fill)
            label.pack(side="left", padx=(px(6), 0))
            rows[step] = (glyph, label)
        self.page_cards = [card]
        return rows

    def mark_step(self, rows, step):
        """A step of the scan panel is done: its dots turn into a green check."""
        if step in rows:
            glyph, label = rows[step]
            try:
                glyph.configure(text=ICONS["check"])
                self.animator.color(("step", step), lambda c: glyph.configure(fg=c), C["dim"], C["ok"], 0.3)
                self.animator.color(("steplabel", step), lambda c: label.configure(fg=c), C["muted"], C["text"], 0.3)
            except tk.TclError:
                pass

    def build_summary(self):
        px = self.px
        infos = list(self.scan["services"].values())
        counts = collections.Counter(info.state for info in infos)
        unknown = sum(self.unknown_reasons().values())  # the same number as in the tips block below
        applied = sum(status == "applied" for status in self.status_map().values())
        self.build_tiles([("summary_on", counts["on"], None, C["accent"], ICONS["check"]),
                          ("summary_off", counts["off"], None, C["muted"], ICONS["circle"]),
                          ("summary_missing", counts["missing"], None, C["dim"], ICONS["dash"]),
                          ("summary_unknown", unknown, None, C["warn"] if unknown else C["dim"], ICONS["unknown"]),
                          ("summary_tweaks", applied, len(tweaks.TWEAKS), C["ok"], ICONS["overview"])])

    def build_tiles(self, tiles):
        """A row of tiles with numbers that count up: [(text key, number, total or None, color, icon)]."""
        px = self.px
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
        pill.grid(row=2, column=1, sticky="e", padx=px(12), pady=(px(5), px(8)))  # on the "Details" line
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

    # --- Troubleshooting ---

    def build_diagnostics_page(self):
        if self.diag is None:
            if not self.diag_running:  # the first visit starts the check
                self.begin_diagnostics()
            self.diag_rows = self.build_scan_panel(ICONS["diagnostics"], self.t("diag_scan_title"),
                                                   self.t("diag_scan_text"),
                                                   [(g, self.t("diag_step_" + g)) for g in diagnostics.GROUPS],
                                                   self.diag_done)
            return
        px = self.px
        found = diagnostics.counts(self.diag)
        self.build_tiles([("diag_tile_problem", found["problem"], None, C["bad"] if found["problem"] else C["dim"],
                           ICONS["warning"]),
                          ("diag_tile_warning", found["warning"], None, C["warn"] if found["warning"] else C["dim"],
                           ICONS["unknown"]),
                          ("diag_tile_info", found["info"], None, C["accent"] if found["info"] else C["dim"],
                           ICONS["info"]),
                          ("diag_tile_ok", found["ok"], None, C["ok"], ICONS["check"])])
        if self.diag_time:
            note = tk.Label(self.list_frame, text=self.t("diag_checked", time=f"{self.diag_time:%H:%M}"),
                            font=self.fonts["small"], fg=C["dim"], bg=C["bg"], anchor="w", justify="left")
            note.pack(fill="x", padx=px(18), pady=(px(6), 0))
            self.wrap(note, px(36))
        if not found["problem"] + found["warning"]:
            self.build_diag_all_clear()
        order = {check: i for i, (check, _) in enumerate(diagnostics.CHECKS)}
        for key, severities in (("diag_sec_attention", ("problem", "warning")), ("diag_sec_info", ("info",)),
                                ("diag_sec_ok", ("ok",)), ("diag_sec_unknown", ("unknown",))):
            group = sorted((f for f in self.diag if f.severity in severities),
                           key=lambda f: (diagnostics.SEVERITIES.index(f.severity), order[f.check]))
            if not group:
                continue
            icon = {"diag_sec_attention": "warning", "diag_sec_info": "info", "diag_sec_ok": "check",
                    "diag_sec_unknown": "unknown"}[key]
            self.section_head(ICONS[icon], f"{self.t(key)}  ·  {len(group)}")
            if key in ("diag_sec_ok", "diag_sec_unknown"):  # what is fine takes one line each
                self.build_finding_list(group)
                continue
            for finding in group:
                self.build_finding_card(finding)

    def build_diag_all_clear(self):
        px = self.px
        card = Card(self.list_frame, self.scale, border=mix(C["ok"], C["surface"], 0.5), radius=14, pad=6)
        card.pack(fill="x", pady=(px(10), 0))
        head = tk.Frame(card.body, bg=card.fill)
        head.pack(fill="x", padx=px(12), pady=(px(10), 0))
        tk.Label(head, text=ICONS["check"], font=self.fonts["icon"], fg=C["ok"], bg=card.fill).pack(side="left")
        tk.Label(head, text=self.t("diag_clear_title"), font=self.fonts["h2"], fg=C["text"], bg=card.fill).pack(
            side="left", padx=(px(10), 0))
        text = tk.Label(card.body, text=self.t("diag_clear_text"), font=self.fonts["small"], fg=C["muted"],
                        bg=card.fill, anchor="w", justify="left")
        text.pack(fill="x", padx=(px(40), px(12)), pady=(px(2), px(12)))
        self.wrap(text, px(72))
        self.page_cards.append(card)

    def diag_text(self, key, params):
        """A troubleshooting line with its numbers, sizes, dates and nested texts in the window's language."""
        values = {}
        for name, value in params.items():
            if isinstance(value, diagnostics.Size):
                value = self.size_text(value)
            elif isinstance(value, datetime.date):
                value = self.format_day(value)
            elif isinstance(value, diagnostics.Text):  # filled in with the other values, never with itself
                value = self.diag_text(value, {n: v for n, v in params.items() if not isinstance(v, diagnostics.Text)})
            values[name] = value
        return self.text("diag_lines", key).format(**values)

    def format_day(self, day):
        return f"{day.day} {day:%b %Y}" if self.lang == "en" else f"{day:%d.%m.%Y}"

    def build_finding_card(self, finding):
        px = self.px
        color = severity_color(finding.severity)
        card = Card(self.list_frame, self.scale,
                    border=mix(color, C["surface"], 0.55) if finding.severity == "problem" else None)
        card.pack(fill="x", pady=(0, px(10)))
        body = card.body
        body.columnconfigure(1, weight=1)
        badge = Card(body, self.scale, fill=mix(color, card.fill, 0.14), border=mix(color, card.fill, 0.35), radius=12,
                     pad=3)
        badge.grid(row=0, column=0, rowspan=2, sticky="nw", padx=px(12), pady=(px(10), 0))
        tk.Label(badge.body, text=ICONS[GROUP_ICONS[finding.group]], font=self.fonts["icon"], fg=color,
                 bg=badge.fill).pack(padx=px(7), pady=px(5))
        title = tk.Label(body, text=self.text("diag", finding.check)[0], font=self.fonts["h2"], fg=C["text"],
                         bg=card.fill, anchor="w", justify="left")
        title.grid(row=0, column=1, sticky="ew", pady=(px(9), 0))
        line = tk.Label(body, text=self.diag_text(finding.line, finding.params), font=self.fonts["small"],
                        fg=C["muted"], bg=card.fill, anchor="w", justify="left")
        line.grid(row=1, column=1, sticky="ew", pady=(px(1), 0))
        pill = Pill(body, self.fonts["pill"], self.scale, self.animator)
        pill.grid(row=2, column=2, sticky="e", padx=px(12), pady=(px(5), px(8)))  # on the "Details" line
        pill.set(self.t("diag_" + finding.severity), color, animate=False)
        self.wrap(title, px(232))
        self.wrap(line, px(232))
        widgets = {"card": card}
        self.details_toggle(body, widgets, ("d", finding.check),
                            lambda holder: self.build_finding_details(holder, finding), column=1, indent=0)
        self.page_cards.append(card)
        self.diag_cards[finding.check] = widgets

    def build_finding_list(self, findings):
        """One card with a line per finding: icon, name, result and its own Details."""
        px = self.px
        card = Card(self.list_frame, self.scale, radius=14, pad=6)
        card.pack(fill="x", pady=(0, px(10)))
        body = card.body
        body.columnconfigure(2, weight=1)
        # The results wrap in what the icons, the widest name and the widest Details link leave of the line
        bold = tkfont.Font(font=self.fonts["small_bold"])
        names = max(bold.measure(self.text("diag", f.check)[0]) for f in findings)
        link = max(bold.measure(self.t(key)) for key in ("details_show", "details_hide"))
        offset = names + link + px(122)
        for i, finding in enumerate(findings):
            top = 3 * i
            if i:
                tk.Frame(body, bg=C["border"], height=1).grid(row=top, column=0, columnspan=4, sticky="ew",
                                                              padx=px(12))
            color = severity_color(finding.severity)
            tk.Label(body, text=ICONS[GROUP_ICONS[finding.group]], font=self.fonts["icon_small"], fg=color,
                     bg=card.fill).grid(row=top + 1, column=0, sticky="w", padx=(px(14), px(10)), pady=px(8))
            tk.Label(body, text=self.text("diag", finding.check)[0], font=self.fonts["small_bold"], fg=C["text"],
                     bg=card.fill, anchor="w").grid(row=top + 1, column=1, sticky="w", padx=(0, px(12)))
            line = tk.Label(body, text=self.diag_text(finding.line, finding.params), font=self.fonts["small"],
                            fg=C["muted"], bg=card.fill, anchor="w", justify="left")
            line.grid(row=top + 1, column=2, sticky="ew")
            self.wrap(line, offset)
            widgets = {"card": card}
            self.details_toggle(body, widgets, ("d", finding.check),
                                lambda holder, f=finding: self.build_finding_details(holder, f, compact=True),
                                column=3, indent=12, row=top + 1, span=4, sticky="e", pady=(6, 6))
            widgets["toggle"].master.grid_configure(padx=(px(12), px(14)))
            self.diag_cards[finding.check] = widgets
        self.page_cards.append(card)

    def build_finding_details(self, holder, finding, compact=False):
        px = self.px
        bg = holder.cget("bg")
        inner = tk.Frame(holder, bg=bg)
        # Under the name, past the badge of a card or the icon of a line
        indent = (px(44) if compact else px(66), px(16))
        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=(indent[0], px(12)), pady=(0, px(10)))
        text = tk.Label(inner, text=self.text("diag", finding.check)[1], font=self.fonts["body"], fg=C["text"],
                        bg=bg, anchor="w", justify="left")
        text.pack(fill="x", padx=indent)
        self.wrap(text, px(102))
        if finding.items:
            items = tk.Frame(inner, bg=bg)
            items.pack(fill="x", padx=indent, pady=(px(10), 0))
            shown = finding.items[:DIAG_ITEMS]
            if len(finding.items) > DIAG_ITEMS:
                shown.append(("item_more", {"n": len(finding.items) - DIAG_ITEMS}))
            for key, params in shown:
                line = tk.Frame(items, bg=bg)
                line.pack(fill="x", pady=px(1))
                tk.Label(line, text="•", font=self.fonts["small_bold"], fg=severity_color(finding.severity),
                         bg=bg).pack(side="left", anchor="n")
                label = tk.Label(line, text=self.diag_text(key, params), font=self.fonts["small"], fg=C["muted"],
                                 bg=bg, anchor="w", justify="left")
                label.pack(side="left", fill="x", expand=True, padx=(px(8), 0))
                self.wrap(label, px(124))
        if finding.actions:  # at most two, so they fit on one line
            buttons = tk.Frame(inner, bg=bg)
            buttons.pack(fill="x", padx=indent, pady=(px(14), 0))
            for action in finding.actions:
                GradientButton(buttons, self.t("act_" + action), lambda a=action: self.open_tool(a),
                               self.fonts["button"], self.scale, self.animator, primary=False, pad=(14, 6)).pack(
                    side="left", padx=(0, px(8)))
        tk.Frame(inner, bg=bg, height=px(12)).pack()
        return inner

    def open_tool(self, action):
        """Opens what a finding suggests: a page of SimpleTool, a Windows settings page or a Windows tool."""
        kind, target, args = diagnostics.action_target(action)
        if kind == "page":
            self.show_page(target)
            return
        if not self.shell_open(target, args):
            self.notify(self.t("diag_open_failed"), C["warn"], ICONS["warning"])

    def shell_open(self, target, args=None):
        """Opens a program, a document or a settings address the way Explorer would. False if Windows refuses."""
        try:
            return ctypes.windll.shell32.ShellExecuteW(None, "open", target, args, None, 1) > 32
        except (AttributeError, OSError):
            return False

    def begin_diagnostics(self):
        self.diag_running = True
        self.diag_done = set()
        self.diag_started = time.perf_counter()

        def step(group):
            self.jobs.put((self.on_diag_step, group))

        self.run_job(lambda: diagnostics.evaluate(diagnostics.gather(step)), self.on_diag_done)
        self.update_footer()

    def rescan_diagnostics(self):
        if self.diag_running:
            return
        self.diag = None
        self.begin_diagnostics()
        self.update_nav_counts()
        if self.page == "diagnostics":
            self.show_page("diagnostics", animate=False)

    def on_diag_step(self, group):
        self.diag_done.add(group)
        if self.page == "diagnostics":
            self.mark_step(getattr(self, "diag_rows", {}), group)

    def on_diag_done(self, result):
        wait = MIN_SCAN_SECONDS - (time.perf_counter() - self.diag_started)
        if wait > 0:
            self.root.after(int(wait * 1000), lambda: self.finish_diagnostics(result))
        else:
            self.finish_diagnostics(result)

    def finish_diagnostics(self, result):
        self.diag_running = False
        if isinstance(result, Exception):
            # Nothing was read: every check says so, rather than an empty list that would look like a healthy PC
            self.diag, self.diag_time = diagnostics.evaluate({"now": datetime.datetime.now()}), None
            self.show_errors([str(result)])
        else:
            self.diag, self.diag_time = result, datetime.datetime.now()
        self.update_nav_counts()
        if self.page == "diagnostics":
            self.show_page("diagnostics")
        else:
            self.update_footer()

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
            self.link(actions, self.t("snap_delete"), lambda: self.confirm_delete(path, data), font="small",
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

    def create_restore_point(self, then=None, failed=None):
        """Creates a Windows restore point in the background. Then calls then(), or failed(Windows message)."""
        def done(result):
            self.message = None
            ok, detail, enabled = (False, str(result), False) if isinstance(result, Exception) else result
            self.update_footer()
            if ok:
                self.notify(self.t("rp_done_enabled" if enabled else "rp_done"), C["ok"], ICONS["check"])
                if then:
                    then()
            elif failed:
                failed(detail)
            else:
                self.notify(self.t("rp_failed"), C["warn"], ICONS["warning"])
                self.show_errors([self.t("rp_failed") + (f"\n{detail}" if detail else "")])

        # Not "acting": closing SimpleTool while Windows creates the point interrupts nothing
        self.run_action("rp_working", engine.create_restore_point, done, acting=False)

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
            self.snapshots = engine.list_snapshots()
            if isinstance(result, Exception):
                self.start_scan()  # the restore stopped halfway: the system is read again
                self.notify(self.t("errors_title"), C["warn"], ICONS["warning"])
                self.show_errors([str(result)])
                return
            errors, self.scan = result
            self.message = ("snap_restored", {"date": date})
            self.refresh_view()
            if errors:
                self.notify(self.t("errors_title"), C["warn"], ICONS["warning"])
                self.show_errors(errors)
            else:
                self.notify(self.t("snap_restored", date=date), C["ok"], ICONS["check"])

        self.run_action("snap_working", work, done)

    def confirm_delete(self, path, data):
        date = self.format_date(data.get("created"))
        win, content = self.dialog(self.t("snap_delete_title"), ICONS["snapshots"], C["warn"],
                                   self.t("snap_delete_title"), self.t("snap_delete_text", date=date))

        def go():
            win.destroy()
            self.delete_snapshot(path)

        GradientButton(content, self.t("snap_delete_ok"), go, self.fonts["button"], self.scale, self.animator,
                       pad=(18, 8), danger=True).pack(side="right")
        GradientButton(content, self.t("cancel"), win.destroy, self.fonts["button"], self.scale, self.animator,
                       primary=False, pad=(18, 8)).pack(side="right", padx=(0, self.px(10)))
        self.present(win)

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
        if not on:
            text = self.t("mem_off_text")
        elif self.limiter.active():
            text = self.t("mem_on_text", seconds=config["interval"])
        else:  # nothing to limit: closing the window exits instead of going to the tray
            text = self.t("mem_on_idle_text")
        self.mem["text"].configure(text=text)
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
                # With administrator rights only processes protected by Windows stay out of reach
                key = "mem_denied_protected" if self.admin else "mem_denied"
                widgets["denied"].configure(text=self.t(key, count=stat["denied"]))
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
        pill.grid(row=2, column=2, sticky="e", padx=px(12), pady=(px(5), px(8)))  # on the "Details" line
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

    def details_toggle(self, body, widgets, key, builder, column=0, indent=12, row=2, span=3, sticky="w", pady=(5, 8)):
        """A "Details" link at (row, column) and an animated expanding block in the grid row under it."""
        px = self.px
        bg = body.cget("bg")
        link_row = row
        row = tk.Frame(body, bg=bg, cursor="hand2")
        row.grid(row=link_row, column=column, sticky=sticky, padx=(px(indent), 0), pady=(px(pady[0]), px(pady[1])))
        label = tk.Label(row, text=self.t("details_show"), font=self.fonts["small_bold"], fg=C["accent"], bg=bg,
                         cursor="hand2")
        label.pack(side="left")
        chevron = tk.Label(row, text=ICONS["down"], font=self.fonts["icon_tiny"], fg=C["accent"], bg=bg, cursor="hand2")
        chevron.pack(side="left", padx=(px(6), 0), pady=(px(2), 0))
        holder = tk.Frame(body, bg=bg, height=1)
        holder.grid(row=link_row + 1, column=0, columnspan=span, sticky="ew")
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

        rows = (self.scan["checks"][tweak.id][1] if self.scan and tweak.id in self.scan["checks"]
                else [(op, None, None) for op in tweak.ops])
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
        elif self.page == "diagnostics":
            text = self.t("diag_running" if self.diag_running else "diag_footer")
        else:
            text = self.t("hint_select")
        self.message_label.configure(text=text)
        if self.busy or self.page == "diagnostics" and self.diag_running:
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
        if self.page in ("memory", "diagnostics"):
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
        self.mark_step(getattr(self, "scan_rows", {}), step)

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
            # The original snapshot is kept forever, so it is taken only when everything can be read: with
            # administrator rights and the scheduled task list. Snapshots taken before that do not replace it
            has_initial = any(data.get("kind") == "initial" for _, data in self.snapshots)
            if not has_initial and self.admin and result["ctx"].tasks is not None:
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

        def apply():
            lang, ctx = self.lang, self.scan["ctx"]
            self.start_work(chosen, lambda t: engine.apply(t, lang, ctx), "working_apply", "done_apply",
                            "before_apply")

        self.ensure_restore_point(apply)

    def ensure_restore_point(self, proceed):
        """Tweaks are applied only after a Windows restore point: one from the last 24 hours, a new one, or the
        user's explicit decision to go on without one."""
        if not self.admin:  # Windows lists and creates restore points only for administrators
            self.show_restore_point_dialog(proceed)
            return

        def recent():
            try:
                return engine.recent_restore_point()
            except RuntimeError:
                return None  # cannot tell: the dialog offers to create one

        def done(point):
            self.message = None
            self.update_footer()
            if point:
                proceed()
            else:
                self.show_restore_point_dialog(proceed)

        self.run_action("rp_checking", recent, done, acting=False)

    def revert_selected(self):
        chosen = [t for t in tweaks.TWEAKS if t.id in self.selected and self.card_state(t) in REVERTIBLE]
        if not chosen:
            self.message = ("nothing_to_revert", {})
            self.update_footer()
            return
        ctx = self.scan["ctx"]
        self.start_work(chosen, lambda t: engine.revert(t, ctx), "working_revert", "done_revert", "before_revert")

    def run_action(self, working_key, work, on_done, acting=True):
        """A long action in the background: the window is busy, the footer shows a spinner. While it is acting
        (changing the system) SimpleTool cannot be closed."""
        self.busy, self.acting = True, acting
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
        explorer_failed = self.t("explorer_restart_failed")

        def work():
            errors, broken = [], set()
            try:
                engine.take_snapshot(tweaks.TWEAKS, ctx or engine.Context(), snapshot_kind, statuses, VERSION)
            except OSError as exc:
                errors.append(f"{failed} {exc}")
            for tweak in chosen:
                tweak_errors = action(tweak)
                if tweak_errors:
                    broken.add(tweak.id)
                errors += [f"{names[tweak.id]}: {error}" for error in tweak_errors]
            engine.notify_shell()
            # What the changes still need before they show; a tweak that failed does not count
            effects = {t.effect for t in chosen if t.effect and t.id not in broken}
            if "explorer" in effects:
                try:
                    restarted = engine.restart_explorer()
                except OSError as exc:
                    errors.append(f"{explorer_failed} {exc}")
                    restarted = False
                if not restarted:
                    effects.discard("explorer")
                    effects.add("signout")
            return errors, effects, collect_scan()

        def done(result):
            self.selected.clear()
            self.snapshots = engine.list_snapshots()
            if isinstance(result, Exception):
                # The work stopped halfway: what was changed is unknown, so the system is read again
                self.start_scan()
                self.notify(self.t("errors_title"), C["warn"], ICONS["warning"])
                self.show_errors([str(result)])
                return
            errors, effects, self.scan = result
            after = "".join(self.t(key) for key in effect_keys(effects))
            self.message = (done_key, {"n": len(chosen), "after": after})
            self.refresh_view()
            text = self.t(done_key, n=len(chosen), after=after)
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
                log_error(traceback.format_exc())
                result = exc
            self.jobs.put((done, result))

        threading.Thread(target=target, daemon=True).start()

    def post(self, callback):
        """Runs callback on the window thread: other threads (tray, limiter) never touch Tk themselves."""
        self.jobs.put((lambda _: callback(), None))

    def poll(self):
        try:
            while True:
                try:
                    callback, payload = self.jobs.get_nowait()
                except queue.Empty:
                    break
                try:
                    callback(payload)
                except Exception:  # one failed callback must not stop the queue: the tray and the limiter use it too
                    self.report_error(*sys.exc_info())
            # Same thresholds as automatic garbage collection, but on the window thread
            counts, thresholds = gc.get_count(), gc.get_threshold()
            for generation in (2, 1, 0):
                if thresholds[generation] and counts[generation] > thresholds[generation]:
                    gc.collect(generation)
                    break
        finally:
            try:
                self.poll_job = self.root.after(40, self.poll)
            except tk.TclError:
                pass  # a callback closed the window

    def report_error(self, exc_type, exc, tb):
        """An unexpected error: it goes to error.log, and the first one in a session is also shown."""
        log_error("".join(traceback.format_exception(exc_type, exc, tb)))
        if self.error_shown:
            return
        self.error_shown = True
        try:
            self.show_errors([f"{exc_type.__name__}: {exc}", error_log_path()], "crash_title", "crash_intro",
                             report=True)
        except Exception:  # the window itself may be what is broken
            pass

    def on_destroy(self, event):
        # The window is closed: cancel the queue polling, otherwise Tk calls it after the window is gone
        if event.widget is self.root:
            self.animator.stop()
            for job in [getattr(self, "poll_job", None), getattr(self, "memory_job", None)] + self.start_jobs:
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

    def dialog(self, title, icon, color, heading, text, heading_color=None):
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
        tk.Label(body, text=heading, font=self.fonts["dialog"], fg=heading_color or C["text"], bg=C["surface"],
                 anchor="w").grid(row=0, column=1, sticky="w", padx=(px(16), 0))
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

    def startup_dialogs(self):
        """After the terms are accepted: what is new after an update, then a warning about another account or the
        offer of administrator rights. One window at a time: the next opens when the previous one closes."""
        if self.whats_new:
            notes, self.whats_new = self.whats_new, []
            self.show_whats_new(notes, then=self.startup_dialogs)
            return
        if self.other_account:
            self.show_other_account_dialog()
        elif not self.admin:
            self.show_admin_dialog()

    def show_whats_new(self, notes=None, then=None):
        """The notes of the versions that came with an update, newest first; from Help, this version's."""
        px = self.px
        notes = notes or whatsnew.since(None, VERSION)
        win, content = self.dialog(self.t("whatsnew_link"), ICONS["help"], C["accent"],
                                   self.t("whatsnew_title", version=VERSION), self.t("whatsnew_intro"))
        for version, texts in notes:
            if len(notes) > 1:
                tk.Label(content, text=version, font=self.fonts["small_bold"], fg=C["muted"], bg=C["surface"],
                         anchor="w").pack(fill="x", pady=(px(6), px(2)))
            for line in texts.get(self.lang, texts["en"]):
                row = tk.Frame(content, bg=C["surface"])
                row.pack(fill="x", pady=(0, px(6)))
                tk.Label(row, text="•", font=self.fonts["body"], fg=C["accent"], bg=C["surface"]).pack(
                    side="left", anchor="n", padx=(0, px(8)))
                tk.Label(row, text=line, font=self.fonts["body"], fg=C["text"], bg=C["surface"], anchor="w",
                         justify="left", wraplength=px(440)).pack(side="left", fill="x")
        buttons = tk.Frame(content, bg=C["surface"])
        buttons.pack(fill="x", pady=(px(12), 0))
        page = f"https://github.com/danilablagorodniy37/SimpleTool/releases/tag/v{VERSION}"
        self.link(buttons, self.t("whatsnew_all"), lambda: self.open_url(page), font="small").pack(side="left")
        GradientButton(buttons, self.t("whatsnew_ok"), win.destroy, self.fonts["button"], self.scale,
                       self.animator, pad=(18, 8)).pack(side="right")
        if then:
            # Whichever way the window closes (the button, Escape, the title bar), the next one follows
            win.bind("<Destroy>", lambda e: self.root.after(150, then) if e.widget is win else None)
        self.present(win)

    def show_other_account_dialog(self):
        running, signed_in = self.other_account
        win, content = self.dialog(self.t("other_account_title"), ICONS["warning"], C["warn"],
                                   self.t("other_account_title"),
                                   self.t("other_account_text", account=running, user=signed_in))
        GradientButton(content, self.t("close"), win.destroy, self.fonts["button"], self.scale, self.animator,
                       pad=(18, 8)).pack(side="right")
        self.present(win)

    def show_terms(self, first_run=False):
        """The terms of use. On the first run, and when the terms change, SimpleTool works only after "I accept"."""
        px = self.px
        text = terms.TERMS[self.lang]
        win, content = self.dialog(text["title"], ICONS["info"], C["accent"], text["title"], text["intro"])
        frame = tk.Frame(content, bg=C["bg"])
        frame.pack(fill="both", expand=True)
        box = tk.Text(frame, font=self.fonts["small"], fg=C["text"], bg=C["bg"], relief="flat", wrap="word", width=74,
                      height=min(18, max(10, (self.root.winfo_screenheight() - px(360)) // px(17))), padx=px(14),
                      pady=px(12), highlightthickness=0, cursor="arrow", spacing2=px(1))
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=box.yview, style="Brand.Vertical.TScrollbar")
        box.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        box.pack(side="left", fill="both", expand=True)
        box.tag_configure("muted", foreground=C["muted"])
        box.tag_configure("heading", font=self.fonts["small_bold"], spacing1=px(10), spacing3=px(3))
        box.insert("end", text["updated"], "muted")
        for number, (heading, body) in enumerate(text["sections"], 1):
            box.insert("end", f"\n{number}. {heading}\n", "heading")
            box.insert("end", body)
        box.configure(state="disabled")
        bottom = tk.Frame(content, bg=C["surface"])
        bottom.pack(fill="x", pady=(px(16), 0))
        # The terms in another language: the window opens again, and the whole program switches language
        for code, name in i18n.LANGUAGES:
            if code != self.lang:
                self.link(bottom, name, lambda c=code: self.reopen_terms(win, c, first_run), font="small").pack(
                    side="left", padx=(0, px(12)))
        if first_run:
            GradientButton(bottom, self.t("terms_accept"), lambda: self.accept_terms(win), self.fonts["button"],
                           self.scale, self.animator, pad=(18, 8)).pack(side="right")
            GradientButton(bottom, self.t("terms_exit"), self.quit, self.fonts["button"], self.scale, self.animator,
                           primary=False, pad=(18, 8)).pack(side="right", padx=(0, px(10)))
        else:
            GradientButton(bottom, self.t("close"), win.destroy, self.fonts["button"], self.scale, self.animator,
                           pad=(18, 8)).pack(side="right")
        self.present(win)
        if first_run:  # closing the window without accepting means not using SimpleTool
            win.protocol("WM_DELETE_WINDOW", self.quit)
            win.bind("<Escape>", lambda e: self.quit())

    def reopen_terms(self, win, lang, first_run):
        win.destroy()
        self.set_language(lang)
        self.show_terms(first_run)

    def accept_terms(self, win):
        self.settings["terms"] = terms.VERSION
        save_settings(self.settings)
        win.destroy()
        self.startup_dialogs()

    def show_errors(self, errors, title_key="errors_title", intro_key="errors_intro", report=False):
        px = self.px
        win, content = self.dialog(self.t(title_key), ICONS["warning"], C["warn"], self.t(title_key),
                                   self.t(intro_key, email=SUPPORT_EMAIL))
        text = tk.Text(content, font=self.fonts["small"], fg=C["text"], bg=C["bg"], relief="flat", wrap="word",
                       width=72, height=min(12, 2 * len(errors) + 1), padx=px(12), pady=px(10), highlightthickness=0)
        text.insert("1.0", "\n\n".join(errors))
        text.configure(state="disabled")
        text.pack(fill="x")
        GradientButton(content, self.t("close"), win.destroy, self.fonts["button"], self.scale, self.animator,
                       pad=(18, 8)).pack(side="right", pady=(px(16), 0))
        if report:
            def report_it():
                win.destroy()
                self.show_report()

            GradientButton(content, self.t("report_link"), report_it, self.fonts["button"], self.scale,
                           self.animator, primary=False, pad=(18, 8)).pack(side="right", padx=(0, px(10)),
                                                                          pady=(px(16), 0))
        self.present(win)

    # --- Restore point before Apply ---

    def show_restore_point_dialog(self, proceed, error=None):
        """Asks for a restore point before tweaks are applied. Going on without one takes a second, scarier
        dialog (show_no_restore_point_dialog)."""
        px = self.px
        win, content = self.dialog(self.t("rp_gate_title"), ICONS["shield"], C["warn"], self.t("rp_gate_title"),
                                   self.t("rp_gate_text" if self.admin else "rp_gate_admin_text"))
        if error is not None:
            failure = tk.Label(content, text=self.t("rp_failed") + (f"\n{error}" if error else ""),
                               font=self.fonts["small"], fg=C["bad"], bg=C["surface"], anchor="w", justify="left",
                               wraplength=px(500))
            failure.pack(fill="x")
            self.link(content, self.t("rp_open_protection"), self.open_system_protection, font="small").pack(
                anchor="w", pady=(px(6), 0))
        buttons = tk.Frame(content, bg=C["surface"])
        buttons.pack(fill="x", pady=(px(16) if error is not None else 0, 0))

        def create():
            win.destroy()
            self.create_restore_point(then=proceed,
                                      failed=lambda detail: self.show_restore_point_dialog(proceed, detail))

        def skip():
            win.destroy()
            self.show_no_restore_point_dialog(proceed)

        if self.admin:
            GradientButton(buttons, self.t("rp_gate_create"), create, self.fonts["button"], self.scale,
                           self.animator, pad=(18, 8)).pack(side="right")
        else:
            error_label = tk.Label(content, text="", font=self.fonts["small"], fg=C["warn"], bg=C["surface"],
                                   anchor="w")
            error_label.pack(fill="x", before=buttons)
            GradientButton(buttons, self.t("admin_restart"), lambda: self.restart_as_admin(error_label),
                           self.fonts["button"], self.scale, self.animator, pad=(18, 8)).pack(side="right")
        GradientButton(buttons, self.t("cancel"), win.destroy, self.fonts["button"], self.scale, self.animator,
                       primary=False, pad=(18, 8)).pack(side="right", padx=(0, px(10)))
        self.link(buttons, self.t("rp_gate_skip"), skip, font="small", color=C["dim"]).pack(side="left")
        self.present(win)

    def show_no_restore_point_dialog(self, proceed):
        """Going on without a restore point: the risk is spelled out, and the button works only after the user
        ticks that they take it."""
        px = self.px
        red = GradientButton.DANGER[0]
        win, content = self.dialog(self.t("rp_skip_title"), ICONS["warning"], red, self.t("rp_skip_title"),
                                   self.t("rp_skip_text"), heading_color=red)
        row = tk.Frame(content, bg=C["surface"], cursor="hand2")
        row.pack(fill="x")
        box = CheckBox(row, px(18), self.animator)
        box.pack(side="left", anchor="n", pady=(px(2), 0))
        label = tk.Label(row, text=self.t("rp_skip_confirm"), font=self.fonts["small_bold"], fg=C["text"],
                         bg=C["surface"], anchor="w", justify="left", wraplength=px(470))
        label.pack(side="left", fill="x", padx=(px(10), 0))
        buttons = tk.Frame(content, bg=C["surface"])
        buttons.pack(fill="x", pady=(px(18), 0))

        def go():
            win.destroy()
            proceed()

        def back():
            win.destroy()
            self.show_restore_point_dialog(proceed)

        apply = GradientButton(buttons, self.t("rp_skip_apply"), go, self.fonts["button"], self.scale, self.animator,
                               pad=(18, 8), danger=True)
        apply.pack(side="right")
        apply.set_enabled(False)
        GradientButton(buttons, self.t("back"), back, self.fonts["button"], self.scale, self.animator,
                       primary=False, pad=(18, 8)).pack(side="right", padx=(0, px(10)))

        def toggle(event=None):
            checked = box.progress < 0.5
            box.set(checked, True)
            apply.set_enabled(checked)

        for widget in (row, box, label):
            widget.bind("<Button-1>", toggle)
        self.present(win)

    def open_system_protection(self):
        """The System Protection tab of System Properties: turning it on, disk space, restore points."""
        try:
            subprocess.Popen(["SystemPropertiesProtection.exe"], creationflags=engine.CREATE_NO_WINDOW)
        except OSError as exc:
            self.show_errors([str(exc)])

    # --- Updates and problem reports ---

    def open_url(self, url):
        try:
            os.startfile(url)
            return True
        except OSError:
            return False

    def check_updates(self):
        """Asks blagotech.uk for the newest version, when the user asks."""
        if self.checking_updates:
            return
        self.checking_updates = True
        self.notify(self.t("update_checking"), C["accent"], ICONS["refresh"])

        def work():
            try:
                return updates.check(VERSION)
            except updates.CheckFailed as exc:
                return exc

        def done(result):
            self.checking_updates = False
            if isinstance(result, Exception):
                self.show_update_failed(str(result))
            elif result["newer"]:
                self.set_available_update(result)
                self.show_update(result)
            else:
                self.notify(self.t("update_latest", version=VERSION), C["ok"], ICONS["check"])

        self.run_job(work, done)

    def daily_update_check(self):
        """Once a day at start, quietly: a newer version shows as a dot on Help and a notification, nothing more.
        A failed check is tried again at the next start."""
        if not self.settings.get("auto_update_check", True) or self.checking_updates:
            return
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            last = datetime.datetime.fromisoformat(self.settings.get("update_checked", ""))
        except (TypeError, ValueError):
            last = None
        if last and last.tzinfo and now - last < UPDATE_CHECK_EVERY:
            return
        self.checking_updates = True

        def work():
            try:
                return updates.check(VERSION)
            except updates.CheckFailed as exc:
                return exc

        def done(result):
            self.checking_updates = False
            if isinstance(result, Exception):
                return
            self.settings["update_checked"] = now.isoformat(timespec="seconds")
            save_settings(self.settings)
            if result["newer"]:
                self.set_available_update(result)
                self.notify(self.t("update_available_toast", version=result["version"]), C["ok"], ICONS["refresh"])

        self.run_job(work, done)

    def set_daily_check(self, on):
        self.settings["auto_update_check"] = bool(on)
        save_settings(self.settings)

    def set_available_update(self, info):
        self.available_update = info
        self.paint_update_badge()

    def paint_update_badge(self):
        try:
            self.help_badge.configure(text="●" if self.available_update else "")
        except (AttributeError, tk.TclError):
            pass

    def show_update(self, info):
        px = self.px
        installable = updater.can_install(info)
        win, content = self.dialog(self.t("update_title"), ICONS["refresh"], C["accent"],
                                   self.t("update_heading", version=info["version"]),
                                   self.t("update_text_install" if installable else "update_text", current=VERSION))
        site = updates.PAGES.get(self.lang, updates.PAGES["en"])

        def go():
            win.destroy()
            if installable:
                self.install_update(info)
            else:
                self.open_url(info["url"] or site)

        GradientButton(content, self.t("update_install" if installable else "update_download"), go,
                       self.fonts["button"], self.scale, self.animator, pad=(18, 8)).pack(side="right")
        GradientButton(content, self.t("update_later"), win.destroy, self.fonts["button"], self.scale, self.animator,
                       primary=False, pad=(18, 8)).pack(side="right", padx=(0, px(10)))
        self.link(content, self.t("update_notes"), lambda: self.open_url(info["page"] or site), font="small").pack(
            side="left")
        self.present(win)

    def install_update(self, info):
        """Downloads and checks the new exe, puts it in place of this one and restarts into it. "Acting" all the
        way: closing SimpleTool halfway through the swap would leave no SimpleTool.exe in place."""
        if self.busy:
            self.notify(self.t("update_busy"), C["warn"], ICONS["warning"])
            return
        shown = [-1]

        def progress(done, total):
            percent = int(done * 100 / total) if total else 0
            if percent != shown[0]:
                shown[0] = percent
                self.post(lambda: self.show_progress(percent))

        def finished(result):
            self.message = None
            self.update_footer()
            if isinstance(result, Exception):
                self.show_install_failed(str(result), info)
                return
            if self.instance:  # the new copy must not take this one for an already running copy and exit
                self.instance.release()
            try:
                updater.start(result)
            except OSError as exc:
                if self.instance and self.instance.acquire():
                    self.instance.listen(lambda: self.post(self.show_window))
                self.show_errors([self.t("update_restart_failed", error=exc)])
                return
            self.root.destroy()

        def work():
            try:
                return updater.install(info, progress)
            except updater.UpdateFailed as exc:
                return exc

        self.run_action("update_preparing", work, finished)

    def show_progress(self, percent):
        if self.acting:
            self.message = ("update_downloading", {"percent": percent})
            self.update_footer()

    def show_install_failed(self, error, info):
        px = self.px
        win, content = self.dialog(self.t("update_install_failed_title"), ICONS["warning"], C["warn"],
                                   self.t("update_install_failed_title"),
                                   self.t("update_install_failed_text", error=error))

        def manual():
            win.destroy()
            self.open_url(info.get("url") or updates.PAGES.get(self.lang, updates.PAGES["en"]))

        GradientButton(content, self.t("update_download_manual"), manual, self.fonts["button"], self.scale,
                       self.animator, pad=(18, 8)).pack(side="right")
        GradientButton(content, self.t("close"), win.destroy, self.fonts["button"], self.scale, self.animator,
                       primary=False, pad=(18, 8)).pack(side="right", padx=(0, px(10)))
        self.present(win)

    def remove_previous_exe(self, tries=6):
        """After an update the previous exe is still exiting for a moment: its file goes once it is free."""
        if not updater.cleanup() and tries > 1:
            self.start_jobs.append(self.root.after(5000, lambda: self.remove_previous_exe(tries - 1)))

    def show_update_failed(self, error):
        px = self.px
        win, content = self.dialog(self.t("update_failed_title"), ICONS["warning"], C["warn"],
                                   self.t("update_failed_title"), self.t("update_failed_text", error=error))

        def site():
            win.destroy()
            self.open_url(updates.PAGES.get(self.lang, updates.PAGES["en"]))

        GradientButton(content, self.t("update_open_site"), site, self.fonts["button"], self.scale, self.animator,
                       pad=(18, 8)).pack(side="right")
        GradientButton(content, self.t("close"), win.destroy, self.fonts["button"], self.scale, self.animator,
                       primary=False, pad=(18, 8)).pack(side="right", padx=(0, px(10)))
        self.present(win)

    def show_report(self):
        """Where to send a bug report: an email to SUPPORT_EMAIL with the versions filled in, and the error log."""
        px = self.px
        win, content = self.dialog(self.t("report_title"), ICONS["info"], C["accent"], self.t("report_title"),
                                   self.t("report_text", email=SUPPORT_EMAIL))
        line = tk.Frame(content, bg=C["surface"])
        line.pack(fill="x")
        # A read-only field: the address can be selected and copied by hand too
        address = tk.Entry(line, font=self.fonts["mono"], fg=C["text"], bg=C["bg"], relief="flat",
                           readonlybackground=C["bg"], highlightthickness=0, width=len(SUPPORT_EMAIL) + 2)
        address.insert(0, SUPPORT_EMAIL)
        address.configure(state="readonly")
        address.pack(side="left", ipady=px(6), ipadx=px(8))
        self.link(line, self.t("report_copy"), self.copy_address, font="small").pack(side="left", padx=(px(12), 0))
        # What the letter will say about the PC, so nothing goes in it unseen
        specs = "\n".join(self.system_summary())
        head = tk.Frame(content, bg=C["surface"])
        head.pack(fill="x", pady=(px(14), px(4)))
        tk.Label(head, text=self.t("report_specs"), font=self.fonts["small_bold"], fg=C["muted"], bg=C["surface"],
                 anchor="w").pack(side="left")
        self.link(head, self.t("report_copy_specs"), lambda: self.copy_text(specs, self.t("report_copied_specs")),
                  font="small").pack(side="left", padx=(px(12), 0))
        box = tk.Text(content, font=self.fonts["mono"], fg=C["text"], bg=C["bg"], relief="flat", wrap="word",
                      width=72, height=min(9, specs.count("\n") + 1), padx=px(10), pady=px(8), highlightthickness=0)
        box.insert("1.0", specs)
        box.configure(state="disabled")
        box.pack(fill="x")
        buttons = tk.Frame(content, bg=C["surface"])
        buttons.pack(fill="x", pady=(px(18), 0))

        def write():
            win.destroy()
            self.write_report()

        GradientButton(buttons, self.t("report_write"), write, self.fonts["button"], self.scale, self.animator,
                       pad=(18, 8)).pack(side="right")
        GradientButton(buttons, self.t("report_log"), self.open_error_log, self.fonts["button"], self.scale,
                       self.animator, primary=False, pad=(18, 8)).pack(side="right", padx=(0, px(10)))
        self.present(win)

    def system_summary(self):
        """SimpleTool's own state, then the PC's specifications (sysinfo)."""
        app = (f"SimpleTool: {VERSION}, {'administrator' if self.admin else 'limited mode'}, "
               f"scale {round(self.scale * 100)}%, language {self.lang}, theme {C['name']}")
        try:
            return sysinfo.summary(app)
        except Exception:  # a report must open even if Windows answers something unexpected
            log_error(traceback.format_exc())
            return [app, f"Windows {platform.version()}"]

    def write_report(self):
        subject = self.t("report_subject", version=VERSION)
        body = self.t("report_body", system="\n".join(self.system_summary()))
        url = f"mailto:{SUPPORT_EMAIL}?" + urllib.parse.urlencode({"subject": subject, "body": body},
                                                                  quote_via=urllib.parse.quote)
        if not self.open_url(url):  # no email program is set up: the address goes to the clipboard instead
            self.copy_address()

    def copy_address(self):
        self.copy_text(SUPPORT_EMAIL, self.t("report_copied", email=SUPPORT_EMAIL))

    def copy_text(self, text, message):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.notify(message, C["ok"], ICONS["check"])

    def open_error_log(self):
        """Shows error.log selected in File Explorer, or the data folder if there have been no errors."""
        path = error_log_path()
        try:
            if os.path.exists(path):
                subprocess.Popen(f'explorer.exe /select,"{path}"')
            else:
                os.startfile(engine.data_dir())
        except OSError as exc:
            self.show_errors([str(exc)])


def work_area(root):
    """(left, top, width, height) of the screen without the taskbar."""
    rect = wintypes.RECT()
    try:
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
            return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    except (AttributeError, OSError):
        pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def start_failed(exc):
    """SimpleTool could not open its window: a plain Windows message, because Tk itself may be what failed."""
    log_error(traceback.format_exc())
    lang = i18n.detect_language()
    text = i18n.TEXTS[lang]["ui"]["start_failed"].format(error=f"{type(exc).__name__}: {exc}", path=error_log_path(),
                                                         email=SUPPORT_EMAIL)
    ctypes.windll.user32.MessageBoxW(None, text, "SimpleTool", 0x10)  # MB_ICONERROR


def main():
    # Errors in background threads (the limiter, the tray) go to error.log: a windowed exe has no console
    threading.excepthook = lambda args: log_error("".join(traceback.format_exception(
        args.exc_type, args.exc_value, args.exc_traceback)))
    if updater.needs_fresh_start():
        # Started by 0.6.3's update, inside its temporary folder: start once more on our own and step aside
        try:
            updater.start(updater.target())
            return
        except OSError:
            log_error(traceback.format_exc())  # carry on as we are: it works, it only leaves the old exe behind
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
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.iconbitmap(default=ICON_PATH)
        except tk.TclError:
            pass
        app = App(root, instance)
    except Exception as exc:
        start_failed(exc)
        return
    # The window fits the screen without the taskbar; px(40) is the title bar and the frame
    left, top, area_width, area_height = work_area(root)
    width = min(app.px(1080), area_width - app.px(40))
    height = min(app.px(740), area_height - app.px(48))
    root.minsize(min(app.px(900), width), min(app.px(580), height))
    root.geometry(f"{width}x{height}+{left + (area_width - width) // 2}+{top + max(0, (area_height - height - app.px(40)) // 3)}")
    theme.style_title_bar(root)
    theme.set_window_icon(root, ICON_PATH)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
