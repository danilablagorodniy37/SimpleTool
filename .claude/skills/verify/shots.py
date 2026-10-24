"""Screenshots of SimpleTool pages without the mouse: builds the window from source with its own data folder,
switches pages and expands cards programmatically.

    python .claude/skills/verify/shots.py <lang> <out dir> <page>[:<tweak id to expand>[:<scroll 0..1>]] ...
    python .claude/skills/verify/shots.py en %TEMP%\\st-shots context:classic_menu system:registry_backup:1

Settings go to <out dir>\\data (LOCALAPPDATA), so the user's own settings, backups and snapshots stay untouched.
"""
import ctypes
import json
import os
import sys
from ctypes import wintypes

LANG, OUT = sys.argv[1], os.path.abspath(sys.argv[2])
SPECS = [(spec.split(":") + [None, "0"])[:3] for spec in sys.argv[3:]] or [["overview", None, "0"]]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA = os.path.join(OUT, "data")
os.makedirs(os.path.join(DATA, "SimpleTool"), exist_ok=True)
os.environ["LOCALAPPDATA"] = DATA

sys.path.insert(0, REPO)
os.chdir(REPO)
import tkinter as tk  # noqa: E402
from PIL import ImageGrab  # noqa: E402
import main  # noqa: E402
import terms  # noqa: E402

with open(os.path.join(DATA, "SimpleTool", "settings.json"), "w", encoding="utf-8") as f:
    json.dump({"lang": LANG, "terms": terms.VERSION, "seen_version": main.VERSION, "tray_hint_shown": True,
               "auto_update_check": False}, f)

ctypes.windll.shcore.SetProcessDpiAwareness(1)
root = tk.Tk()
root.withdraw()
app = main.App(root)
left, top, area_width, area_height = main.work_area(root)
width = min(app.px(1080), area_width - app.px(40))
height = min(app.px(740), area_height - app.px(48))
root.geometry(f"{width}x{height}+{left + (area_width - width) // 2}+{top + 20}")
main.theme.style_title_bar(root)
root.deiconify()
user32 = ctypes.windll.user32


def shoot(name):
    root.update()
    hwnd = user32.GetAncestor(root.winfo_id(), 2)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    image = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True)
    path = os.path.join(OUT, f"{LANG}_{name}.png")
    image.save(path)
    print("saved", path, image.size)


def step(i):
    if app.scan is None:
        root.after(300, step, i)  # the first scan is still running: cards say "Checking…"
        return
    if i >= len(SPECS):
        root.after(200, root.destroy)
        return
    page, expand, scroll = SPECS[i]
    if expand:
        app.expanded.add(("t", expand))
    app.show_page(page, animate=False)
    root.after(900, lambda: (app.canvas.yview_moveto(float(scroll)), root.after(600, finish, i)))


def finish(i):
    shoot(SPECS[i][0])
    root.after(200, step, i + 1)


root.after(500, step, 0)
root.mainloop()
