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
def parse(spec):
    parts = spec.split(":")
    return parts[0], (parts[1] if len(parts) > 1 and parts[1] else None), (float(parts[2]) if len(parts) > 2 else 0.0)


SPECS = [parse(spec) for spec in sys.argv[3:]] or [("overview", None, 0.0)]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA = os.path.join(OUT, "data")
os.makedirs(os.path.join(DATA, "SimpleTool"), exist_ok=True)
os.environ["LOCALAPPDATA"] = DATA

sys.path.insert(0, REPO)
os.chdir(REPO)
import tkinter as tk  # noqa: E402
from PIL import Image  # noqa: E402
import main  # noqa: E402
import terms  # noqa: E402

with open(os.path.join(DATA, "SimpleTool", "settings.json"), "w", encoding="utf-8") as f:
    json.dump({"lang": LANG, "terms": terms.VERSION, "seen_version": main.VERSION, "tray_hint_shown": True,
               "auto_update_check": False, "theme": os.environ.get("ST_THEME", "navy")}, f)

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


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def shoot(name):
    """PrintWindow of the window itself: works when other windows cover it (the user keeps working meanwhile)."""
    root.update()
    gdi32 = ctypes.windll.gdi32
    user32.GetWindowDC.restype = gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleBitmap.restype = gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.DeleteObject.argtypes, gdi32.DeleteDC.argtypes = [wintypes.HGDIOBJ], [wintypes.HDC]
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HGDIOBJ, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                ctypes.c_void_p, wintypes.UINT]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    hwnd = user32.GetAncestor(root.winfo_id(), 2)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    memory = gdi32.CreateCompatibleDC(hdc)
    bitmap = gdi32.CreateCompatibleBitmap(hdc, width, height)
    previous = gdi32.SelectObject(memory, bitmap)
    user32.PrintWindow(hwnd, memory, 2)  # PW_RENDERFULLCONTENT
    info = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=width, biHeight=-height, biPlanes=1,
                            biBitCount=32)
    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memory, bitmap, 0, height, buffer, ctypes.byref(info), 0)
    image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)
    gdi32.SelectObject(memory, previous)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory)
    user32.ReleaseDC(hwnd, hdc)
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
    if page == "diagnostics":
        root.after(1500, wait_diagnostics, i, scroll, 0)
    else:
        root.after(900, lambda: (app.canvas.yview_moveto(float(scroll)), root.after(600, finish, i)))


def wait_diagnostics(i, scroll, waited):
    """The Troubleshooting page runs its check when opened; the picture is taken when it is done."""
    if getattr(app, "diag_running", False) and waited < 90:
        root.after(500, wait_diagnostics, i, scroll, waited + 0.5)
        return
    root.after(800, lambda: (app.canvas.yview_moveto(float(scroll)), root.after(600, finish, i)))


def finish(i):
    shoot(SPECS[i][0])
    root.after(200, step, i + 1)


root.after(500, step, 0)
root.mainloop()
