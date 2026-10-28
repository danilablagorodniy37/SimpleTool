"""blagotech palettes, color utilities and images Tk cannot draw itself: gradients and glow."""
import ctypes
import math
import tkinter as tk

# blagotech brand colors: navy #0A1B33, blue #2F8CF5 / #5FB4FF, teal #34D8A8,
# plates #12294A / #16345C, light grey #E3E9F1. The accent gradient goes from blue to teal.
_SIDEBAR = {
    "side": "#081628", "side_hover": "#0F2341", "side_active": "#16345C", "side_border": "#1A2F50",
    "side_text": "#E8EEFC", "side_muted": "#A9B9DC", "side_dim": "#8090B8",
}

# Secondary text and borders are kept well above 4.5:1 against their background, so small text stays crisp
PALETTES = {
    "navy": dict(_SIDEBAR,
                 bg="#0A1B33", surface="#12294A", raised="#16345C", border="#2A4670", border_hover="#4A6EA0",
                 text="#EEF3FF", muted="#C3CDEB", dim="#9AA8CC",
                 accent="#5FB4FF", primary="#2F8CF5", grad_a="#2F8CF5", grad_b="#34D8A8", on_primary="#FFFFFF",
                 ok="#34D8A8", warn="#F0B783", bad="#FCA5A5", caption="#081628"),
    "midnight": dict(side="#040A15", side_hover="#0B172B", side_active="#12264A", side_border="#0F1D35",
                     side_text="#EEF3FF", side_muted="#A0B0D2", side_dim="#7585AA",
                     bg="#070F1E", surface="#0D1B33", raised="#132748", border="#24406A", border_hover="#2C6E78",
                     text="#F2F6FF", muted="#B6C2DF", dim="#8A99BF",
                     accent="#34D8A8", primary="#2F8CF5", grad_a="#2F8CF5", grad_b="#34D8A8", on_primary="#FFFFFF",
                     ok="#34D8A8", warn="#F0B783", bad="#FCA5A5", caption="#040A15"),
    "light": dict(_SIDEBAR,
                  bg="#F2F5FA", surface="#FFFFFF", raised="#E3E9F1", border="#CBD5E3", border_hover="#8FB3E6",
                  text="#0A1B33", muted="#3C4D68", dim="#6B7A93",
                  accent="#2F8CF5", primary="#2F8CF5", grad_a="#2F8CF5", grad_b="#2BC79A", on_primary="#FFFFFF",
                  ok="#0E9F74", warn="#C2701A", bad="#D64545", caption="#081628"),
}
THEMES = list(PALETTES)

# Color of each section: menu icon, header glow
CATEGORY_COLORS = {"overview": "#5FB4FF", "diagnostics": "#FF8FA3", "privacy": "#34D8A8", "system": "#7C9CFF",
                   "explorer": "#86D9BD", "context": "#F0B783", "snapshots": "#4AC6D4", "memory": "#A48BFF"}

# Current palette; use() replaces its contents, and every module sees the new colors
C = dict(PALETTES["navy"])


def use(name):
    C.clear()
    C.update(PALETTES.get(name, PALETTES["navy"]))
    C["name"] = name if name in PALETTES else "navy"


def rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def hex_color(r, g, b):
    return "#%02X%02X%02X" % (round(r), round(g), round(b))


def mix(color, background, alpha):
    """color with opacity alpha over background."""
    return hex_color(*(c * alpha + b * (1 - alpha) for c, b in zip(rgb(color), rgb(background))))


def lerp(start, end, t):
    """A color on the line from start to end."""
    return mix(end, start, t)


def style_title_bar(window, caption=None):
    """A dark window title bar matching the sidebar (Windows 10 1809+, the color needs Windows 11)."""
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        color = caption or C["caption"]
        colorref = int(color[5:7] + color[3:5] + color[1:3], 16)  # 0x00BBGGRR
        for attribute, value in ((20, 1), (35, colorref)):  # DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_CAPTION_COLOR
            data = ctypes.c_int(value)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data))
    except (AttributeError, OSError):
        pass


def set_window_icon(window, path):
    """Gives the window icons of exactly the sizes Windows asks for at the current DPI.

    Tk sets only the window class icon, and the taskbar stretches its small frame, so the icon
    looks blurry. Window icons (WM_SETICON) of the right size are taken from the .ico without scaling.
    """
    try:
        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_uint]
        user32.SendMessageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        window.update_idletasks()
        hwnd = user32.GetParent(window.winfo_id())
        try:
            dpi = user32.GetDpiForWindow(hwnd) or 96
            sizes = {1: user32.GetSystemMetricsForDpi(11, dpi), 0: user32.GetSystemMetricsForDpi(49, dpi)}
        except AttributeError:  # Windows 10 before 1607
            sizes = {1: user32.GetSystemMetrics(11), 0: user32.GetSystemMetrics(49)}
        for kind, size in sizes.items():  # 1 is ICON_BIG (taskbar, Alt+Tab), 0 is ICON_SMALL (title bar)
            icon = user32.LoadImageW(None, path, 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if icon:
                user32.SendMessageW(hwnd, 0x80, kind, icon)  # WM_SETICON
    except (AttributeError, OSError):
        pass


# --- Images ---

_cache = {}


def _image(key, width, height, pixel):
    """A PhotoImage where pixel(x, y) gives the color of each point. The result is cached by key."""
    if key not in _cache:
        image = tk.PhotoImage(width=width, height=height)
        rows = ("{" + " ".join(pixel(x, y) for x in range(width)) + "}" for y in range(height))
        image.put(" ".join(rows))
        _cache[key] = image
    return _cache[key]


def _coverage(x, y, width, height, radius):
    """How much a point is covered by a rounded rectangle (0-1, with an antialiased edge)."""
    cx = min(max(x + 0.5, radius), width - radius)
    cy = min(max(y + 0.5, radius), height - radius)
    distance = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
    return max(0.0, min(1.0, radius - distance + 0.5))


def gradient_pill(width, height, radius, start, end, background, glow=0.0):
    """A rounded plate with a horizontal gradient; glow brightens it on hover."""
    width, height = max(int(width), 2), max(int(height), 2)
    lighter = [mix("#FFFFFF", c, glow) for c in (start, end)]
    columns = [lerp(lighter[0], lighter[1], x / max(width - 1, 1)) for x in range(width)]

    def pixel(x, y):
        cover = _coverage(x, y, width, height, radius)
        return columns[x] if cover >= 1 else mix(columns[x], background, cover)

    return _image(("pill", width, height, radius, start, end, background, round(glow, 2)), width, height, pixel)


GLOW_SHADES = 128  # the spot is mixed from this many shades: finer than one step of an 8-bit color


def glow(width, height, color, background, strength=0.22, step=2):
    """A soft elliptical color spot like the glow on the blagotech website: brightest at the top center
    and fading to every edge, so the image can go anywhere without visible borders.

    Drawn at 1/step of the size and zoomed: the spot is so soft that the blocks cannot be seen. The caller grows
    step with the display scale, so drawing (pure Python, pixel by pixel) takes as long at 200% as at 100%."""
    small_w, small_h = max(width // step, 1), max(height // step, 1)
    last = GLOW_SHADES - 1
    shades = [mix(color, background, strength * (i / last) ** 2) for i in range(GLOW_SHADES)]

    def pixel(x, y):
        dx = (x + 0.5) / small_w * 2 - 1
        dy = (y + 0.5) / small_h * 1.25
        return shades[round(max(0.0, 1.0 - math.hypot(dx, dy)) * last)]

    key = ("glow", small_w, small_h, color, background, strength)
    if key + ("zoom", step) not in _cache:
        _cache[key + ("zoom", step)] = _image(key, small_w, small_h, pixel).zoom(step, step)
    return _cache[key + ("zoom", step)]


def gradient_line(width, height, start, end):
    width, height = max(int(width), 1), max(int(height), 1)
    return _image(("line", width, height, start, end), width, height,
                  lambda x, y: lerp(start, end, x / max(width - 1, 1)))


def clear_cache():
    _cache.clear()
