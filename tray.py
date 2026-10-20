"""SimpleTool tray icon (Win32 Shell_NotifyIcon via ctypes, no third-party libraries).

The icon lives in its own thread with its own hidden window and message loop. Menu commands go to the
SimpleTool window through post(function): Tk must not be touched from another thread.
"""
import ctypes
import threading
from ctypes import wintypes

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

WM_DESTROY, WM_CLOSE, WM_COMMAND, WM_NULL = 0x0002, 0x0010, 0x0111, 0x0000
WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x0202, 0x0203, 0x0205
WM_TRAY = 0x8000 + 1  # WM_APP + 1
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
MF_STRING, MF_CHECKED, MF_SEPARATOR = 0x0, 0x8, 0x800
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x2, 0x100


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", ctypes.c_wchar * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", ctypes.c_wchar * 256), ("uVersion", wintypes.UINT), ("szInfoTitle", ctypes.c_wchar * 64),
                ("dwInfoFlags", wintypes.DWORD), ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wintypes.HICON)]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_shell32 = ctypes.WinDLL("shell32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32.DefWindowProcW.restype = LRESULT
_user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.CreateWindowExW.restype = wintypes.HWND
_user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU,
                                    wintypes.HINSTANCE, wintypes.LPVOID]
_user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
_user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
_user32.LoadImageW.restype = wintypes.HANDLE
_user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                               wintypes.UINT]
_user32.CreatePopupMenu.restype = wintypes.HMENU
_user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
_user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, wintypes.LPVOID]
_user32.DestroyMenu.argtypes = [wintypes.HMENU]
_user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
_user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
_user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
_user32.DestroyWindow.argtypes = [wintypes.HWND]
_user32.DestroyIcon.argtypes = [wintypes.HICON]
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
_kernel32.GetModuleHandleW.restype = wintypes.HMODULE
_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


class TrayIcon:
    """menu() returns the items [(id, label, checked) or None for a separator];
    on_command(id) and on_open() are called on the window thread via post."""

    def __init__(self, icon_path, tooltip, menu, on_command, on_open, post):
        self.icon_path, self.tooltip = icon_path, tooltip
        self.menu, self.on_command, self.on_open, self.post = menu, on_command, on_open, post
        self.hwnd = None
        self._ready = threading.Event()
        self._thread = None
        self._class = f"SimpleToolTray{id(self)}"
        self._proc = WNDPROC(self._wndproc)  # keep a reference, or the GC deletes the handler

    def show(self):
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._loop, name="tray", daemon=True)
        self._thread.start()
        self._ready.wait(5)

    def hide(self):
        if self.hwnd:
            _user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
        if self._thread:
            self._thread.join(timeout=5)
        self.hwnd = None

    def visible(self):
        return bool(self.hwnd)

    def set_tooltip(self, text):
        self.tooltip = text
        if self.hwnd:
            data = self._data(NIF_TIP)
            _shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data))

    def balloon(self, title, text):
        if self.hwnd:
            data = self._data(NIF_INFO)
            data.szInfoTitle, data.szInfo = title[:63], text[:255]
            _shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data))

    # --- tray thread ---

    def _data(self, flags):
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(data)
        data.hWnd, data.uID, data.uFlags = self.hwnd, 1, flags
        data.uCallbackMessage, data.hIcon, data.szTip = WM_TRAY, self._icon, self.tooltip[:127]
        return data

    def _add(self):
        data = self._data(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        _shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data))

    def _loop(self):
        instance = _kernel32.GetModuleHandleW(None)
        window_class = WNDCLASSW(lpfnWndProc=self._proc, hInstance=instance, lpszClassName=self._class)
        _user32.RegisterClassW(ctypes.byref(window_class))
        self._taskbar_created = _user32.RegisterWindowMessageW("TaskbarCreated")
        size = _user32.GetSystemMetrics(49)  # SM_CXSMICON: an icon of the right size for the current DPI
        self._icon = _user32.LoadImageW(None, self.icon_path, 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
        # A regular hidden window, not message-only: only it receives TaskbarCreated after Explorer restarts
        self.hwnd = _user32.CreateWindowExW(0, self._class, "SimpleTool tray", 0, 0, 0, 0, 0, None, None, instance, None)
        self._add()
        self._ready.set()
        message = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(message))
            _user32.DispatchMessageW(ctypes.byref(message))
        if self._icon:
            _user32.DestroyIcon(self._icon)
        _user32.UnregisterClassW(self._class, instance)

    def _show_menu(self, hwnd):
        menu = _user32.CreatePopupMenu()
        for item in self.menu():
            if item is None:
                _user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            else:
                command, label, checked = item
                _user32.AppendMenuW(menu, MF_STRING | (MF_CHECKED if checked else 0), command, label)
        point = wintypes.POINT()
        _user32.GetCursorPos(ctypes.byref(point))
        _user32.SetForegroundWindow(hwnd)  # otherwise the menu does not close when clicking elsewhere
        command = _user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, point.x, point.y, 0, hwnd, None)
        _user32.PostMessageW(hwnd, WM_NULL, 0, 0)
        _user32.DestroyMenu(menu)
        if command:
            self.post(lambda: self.on_command(command))

    def _wndproc(self, hwnd, message, wparam, lparam):
        if message == WM_TRAY:
            if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self.post(self.on_open)
            elif lparam == WM_RBUTTONUP:
                self._show_menu(hwnd)
            return 0
        if message == self._taskbar_created:  # Explorer restarted: the icon has to be added again
            self._add()
            return 0
        if message == WM_CLOSE:
            data = self._data(0)
            _shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
            _user32.DestroyWindow(hwnd)
            return 0
        if message == WM_DESTROY:
            _user32.PostQuitMessage(0)
            return 0
        return _user32.DefWindowProcW(hwnd, message, wparam, lparam)


_kernel32.CreateEventW.restype = wintypes.HANDLE
_kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.SetEvent.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.WaitForSingleObject.restype = wintypes.DWORD
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    """One copy of SimpleTool per session: otherwise two memory limiters would get in each other's way.
    A second launch wakes the first copy (it shows its window, even from the tray) and exits."""

    def __init__(self, name="Local\blagotech.SimpleTool.show"):
        self.name = name
        self.handle = None

    def acquire(self):
        """True: this is the first copy. False: SimpleTool is already running and was asked to show its window."""
        handle = _kernel32.CreateEventW(None, False, False, self.name)
        exists = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        if handle and not exists:
            self.handle = handle
            return True
        if handle:
            _kernel32.SetEvent(handle)
            _kernel32.CloseHandle(handle)
            return False
        return True  # no access to the event (a copy with different rights created it): run as usual

    def listen(self, on_signal):
        """on_signal() is called from a background thread when SimpleTool is started again."""
        handle = self.handle

        def wait():
            while self.handle == handle:
                if _kernel32.WaitForSingleObject(handle, 300) == 0 and self.handle == handle:
                    on_signal()

        if handle:
            self._thread = threading.Thread(target=wait, name="single-instance", daemon=True)
            self._thread.start()

    def release(self):
        """Releases the name: the next SimpleTool launch becomes the first copy."""
        handle, self.handle = self.handle, None
        thread = getattr(self, "_thread", None)
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2)  # the handle must not be closed while the thread is waiting on it
        if handle:
            _kernel32.CloseHandle(handle)
